# from sharedResources.lifecycle.gracious_cleanup_manager import GraciousCleanupManager
# --- NOVA CLASSE INTERNA PARA GERENCIAR HOOKS ---
import asyncio
import atexit
import inspect
import threading
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.lifecycle.atexit_manager import AtexitShutdownMonitor as AtexitObserver
checkpoints = ["execute_hooks_init",
               "execute_hooks_end",
               "execute_hooks_finally"]
for checkpoint in checkpoints:
    AtexitObserver.register_checkpoint(checkpoint)

badCheckpoints = ["execute_hooks_error",
                  ]
for checkpoint in badCheckpoints:
    AtexitObserver.register_checkpoint(checkpoint,occurrences = 0)


# @monitor_class
class GraciousCleanupManager:
    """
    Gerencia funções de limpeza que devem rodar ANTES do shutdown total.
    Suporta funções síncronas e assíncronas.
    """
    _hooks = [] # Lista de tuplas: (prioridade, func, args, kwargs)
    _lock = threading.Lock()
    _log = None
    LifecycleMaster = None
    
    
    @classmethod
    def register_hook(cls, func, priority, name  ,register_in_atexit = True ,occurrencies = 1, args = (), kwargs = {}):
        """
        Registra uma função para rodar no shutdown.
        priority: Quanto MAIOR, mais cedo roda (100 roda antes de 10).
        """
        
        with cls._lock:
            # Usamos partial para "congelar" os argumentos
            # Mas guardamos separado para debug se precisar
            hook_name = getattr(func, '__name__', str(func)) if name is None else name
            for hook in cls._hooks:
                if hook['name'] == hook_name:
                    cls._log(
                        f"[GraciousCleanupManager] Hook '{hook_name}' já registrado — ignorando",
                        "general"
                    )
                    return False  # <- importante: sinaliza que não registrou

            # cls._log(f"[GraciousCleanupManager] Hook registrado: {hook_name} (Prio: {priority})", "general")
            # try:
            if register_in_atexit:
                occurrencies +=1 # Incrementa o número de ocorrências esperadas pois ela tbm é chamada no atexit
            func = AtexitObserver.tracker(func, occurrences = occurrencies, allow_multiple = False) # Registra a função para ser monitorada no shutdown, com 1 ocorrência esperada (se for chamada mais vezes, já é sinal de problema)
            # except:
            #     pass # ou ja foi registrada ou é async, por enquanto não quero que isso quebre nada , apenas ignoro
            
            cls._hooks.append({
                'priority': priority,
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'name': hook_name,
                'register_in_atexit' : register_in_atexit
            })
        
            return True  # <- sinaliza que registrou com sucesso
    

    @classmethod
    def atexit_exec(cls):
        """executa no atexit apenas os hooks que pediram para ser registrados lá.
        obs: essa função não aparece a execução dela no monitor de execuções pois ela foi
        feita para ser executada depois do monitor ja ter mostraro o relatório, durante o atexit
        """
        # import atexit
        with cls._lock:
            hooks_map = {}
            for hook in cls._hooks:
                if not inspect.iscoroutinefunction(hook['func']): #só se não for async que registro no atexit, pq o atexit não suporta async
                    if hook['register_in_atexit']:
                        prio = hook['priority']
                        if prio not in hooks_map:
                            hooks_map[prio] = []
                        hooks_map[prio].append(hook)
                        # print(f"[GraciousCleanupManager.atexit_register] sync Hook '{hook['name']}' registrado para atexit: {hook['register_in_atexit']} (Prio: {hook['priority']})")
                    else:
                        pass
                        # print(f"[GraciousCleanupManager.atexit_register] sync Hook '{hook['name']}' NÃO registrado para atexit: {hook['register_in_atexit']} (Prio: {hook['priority']})")
            # Ordenar as prioridades da maior para a menor
            sorted_priorities_to_atexit_register = sorted(hooks_map.keys(), reverse=True)
            # if len(sorted_priorities_to_atexit_register) > 0:
            #     pass
                # print("[GraciousCleanupManager.atexit_register] executando hooks no atexit")
                # print("o sorted_priorities_to_atexit_register é: ", sorted_priorities_to_atexit_register)
            for priority in sorted_priorities_to_atexit_register:
                hook_list = hooks_map[priority]
                for hook in hook_list:
                    try:
                        # print(f"[GraciousCleanupManager.atexit_register] Executando o hook {hook['name']} do lote {hook['priority']} no atexit")
                        hook['func'](*hook['args'], **hook['kwargs'])
                        # print(f"[GraciousCleanupManager.atexit_register] foi sucesso executar o {hook['name']} do lote {hook['priority']} no atexit")
                    except Exception as e:
                        print(f"[GraciousCleanupManager.atexit_register] erro ao executar o hook {hook['name']} do lote {hook['priority']} no atexit: {str(e)}")
                        try:
                            log_error_forensics_plus(e, extra_message = f"[GraciousCleanupManager] Erro no atexit para funções sincronas do lote {hook['priority']}")
                        except Exception:
                            cls._log(f"[GraciousCleanupManager] Erro ao registrar log de erro no atexit para o hook do lote {hook['priority']}", "error")

    @classmethod
    def execute_hooks(cls):
        """Executa hooks agrupados por prioridade (Híbrido: Sequencial entre grupos, Paralelo dentro do grupo)."""
        try:
            cls._log("[ShutdownManager] Iniciando execução dos hooks...", "general")
            AtexitObserver.check("execute_hooks_init") # Checkpoint para monitorar se o execute_hooks foi chamado no shutdown, 
            # espero que seja chamado 1 vez, caso contrário é problema!
            with cls._lock:
                if not cls._hooks:
                    cls._log(f"[GraciousCleanupManager.execute_hooks] hooks está vazio!!!","general")
                    return
                # 1. Agrupar hooks por prioridade
                # hooks_map = { 100: [hookA, hookB], 90: [hookC], ... }
                hooks_map = {}
                for hook in cls._hooks:
                    prio = hook['priority']
                    if prio not in hooks_map:
                        hooks_map[prio] = []
                    hooks_map[prio].append(hook)
                
                # Ordenar as prioridades da maior para a menor
                sorted_priorities = sorted(hooks_map.keys(), reverse=True)

            # 2. Executar Lote a Lote
            for prio in sorted_priorities:
                batch = hooks_map[prio]
                cls._log(f"[ShutdownManager] >>> Rodando lote Prioridade {prio} ({len(batch)} hooks)", "general")
                
                # Separar o que é sync do que é async neste lote
                async_coros = []
                
                for hook in batch:
                    try:
                        func = hook['func']
                        args = hook['args']
                        kwargs = hook['kwargs']
                        name = hook['name']

                        if inspect.iscoroutinefunction(func):
                            # Se for async, preparamos para o gather
                            async_coros.append({name: func(*args, **kwargs)})
                        else:
                            # Se for sync, rodamos imediatamente (não tem jeito, bloqueia o lote)
                            # Ou poderíamos rodar em thread separada, mas manter simples é melhor no shutdown
                            cls._log(f"[ShutdownManager] Executando sync: {name}", "general")
                            func(*args, **kwargs)
                    except Exception as e:
                        log_error_forensics_plus(e, extra_message = f"[ShutdownManager] ocorreu no hook do cleanup manager para funções sincronas do lote {prio}")

                # Se tivermos coroutines async neste lote, rodamos elas em GATHER
                if async_coros and cls.LifecycleMaster._loop_is_ok():
                    try:
                        cls._log(f"[ShutdownManager] Aguardando {len(async_coros)} tarefas async do lote {prio}, são elas:{[[a for a in f][0] for f in async_coros]}", "general")
                        
                        # Função auxiliar para rodar o gather dentro do loop
                        async def run_batch():
                            # return_exceptions=True impede que um erro cancele os outros do mesmo lote
                            functions_list = [[hook for hook in f.values()][0] for f in async_coros]
                            print(f"[ShutdownManager] the functions list for the gather is: {functions_list}")
                            return await asyncio.gather(*functions_list, return_exceptions=True)

                        future = asyncio.run_coroutine_threadsafe(run_batch(), cls.LifecycleMaster.running_loop.get())
                        
                        # Timeout por lote (ex: 10 segundos por nível de prioridade)
                        results = future.result(timeout=10)
                        
                        # Logar erros do gather
                        for res in results:
                            if isinstance(res, Exception):
                                log_error_forensics_plus(res, extra_message = f"[ShutdownManager] ocorreu em uma das funções do gather do lote {prio} , do cleanup manager")

                    except Exception as e:
                        log_error_forensics_plus(e, extra_message = f"[ShutdownManager] ocorreu no gather do lote {prio} , do cleanup manager")
                        cls._log(f"[ShutdownManager] Erro/Timeout no lote async {prio}: {e}", "general")
            AtexitObserver.check("execute_hooks_end") # Checkpoint para monitorar se o execute_hooks foi chamado no shutdown, 
                
            cls._log("[ShutdownManager] Todos os hooks finalizados.", "general")
        except Exception as e:
            AtexitObserver.check("execute_hooks_error") # Checkpoint para monitorar se o execute_hooks deu erro, isso é importante para saber se o shutdown chegou até o fim do execute_hooks mesmo que com erros, ou se travou em algum ponto do processo
            log_error_forensics_plus(e, extra_message = "[ShutdownManager] Erro ao executar os hooks do GraciousCleanupManager")
        finally:
            AtexitObserver.check("execute_hooks_finally") # Checkpoint para monitorar se o execute_hooks chegou no finally, isso é importante para saber se o shutdown chegou até o fim do execute_hooks mesmo que com erros, ou se travou em algum ponto do processo
            cls._log("[ShutdownManager] execute_hooks chegou no bloco finally.", "general")
    @classmethod
    def prepare_class(cls,register_log,lifecycleMaster):
        cls._log = register_log
        cls.LifecycleMaster = lifecycleMaster
    # ------------------------------------------------

AtexitObserver.register(GraciousCleanupManager.atexit_exec)

if __name__ == "__main__":
    manager = GraciousCleanupManager
    # a.prepapre_class(lambda x:print(x),)