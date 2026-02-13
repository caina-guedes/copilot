# from sharedResources.lifecycle.gracious_cleanup_manager import GraciousCleanupManager
# --- NOVA CLASSE INTERNA PARA GERENCIAR HOOKS ---
import asyncio
import threading
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus, monitor_error


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
    def register_hook(cls, func, priority=10, *args, **kwargs):
        """
        Registra uma função para rodar no shutdown.
        priority: Quanto MAIOR, mais cedo roda (100 roda antes de 10).
        """
        with cls._lock:
            # Usamos partial para "congelar" os argumentos
            # Mas guardamos separado para debug se precisar
            cls._hooks.append({
                'priority': priority,
                'func': func,
                'args': args,
                'kwargs': kwargs,
                'name': getattr(func, '__name__', str(func))
            })
            cls._log(f"[GraciousCleanupManager] Hook registrado: {getattr(func, '__name__', str(func))} (Prio: {priority})", "general")

    @classmethod
    async def _run_hook_async(cls, func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)


    @classmethod
    def execute_hooks(cls):
        """Executa hooks agrupados por prioridade (Híbrido: Sequencial entre grupos, Paralelo dentro do grupo)."""
        cls._log("[ShutdownManager] Iniciando execução dos hooks...", "general")
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
                func = hook['func']
                args = hook['args']
                kwargs = hook['kwargs']
                name = hook['name']

                try:
                    if asyncio.iscoroutinefunction(func):
                        # Se for async, preparamos para o gather
                        async_coros.append(func(*args, **kwargs))
                    else:
                        # Se for sync, rodamos imediatamente (não tem jeito, bloqueia o lote)
                        # Ou poderíamos rodar em thread separada, mas manter simples é melhor no shutdown
                        cls._log(f"[ShutdownManager] Executando sync: {name}", "general")
                        func(*args, **kwargs)
                except Exception as e:
                    log_error_forensics_plus(e)

            # Se tivermos coroutines async neste lote, rodamos elas em GATHER
            if async_coros and cls.LifecycleMaster._loop_is_ok():
                try:
                    cls._log(f"[ShutdownManager] Aguardando {len(async_coros)} tarefas async do lote {prio}...", "general")
                    
                    # Função auxiliar para rodar o gather dentro do loop
                    async def run_batch():
                        # return_exceptions=True impede que um erro cancele os outros do mesmo lote
                        return await asyncio.gather(*async_coros, return_exceptions=True)

                    future = asyncio.run_coroutine_threadsafe(run_batch(), cls.LifecycleMaster.running_loop.get())
                    
                    # Timeout por lote (ex: 10 segundos por nível de prioridade)
                    results = future.result(timeout=10)
                    
                    # Logar erros do gather
                    for res in results:
                        if isinstance(res, Exception):
                            log_error_forensics_plus(res)

                except Exception as e:
                    cls._log(f"[ShutdownManager] Erro/Timeout no lote async {prio}: {e}", "general")
            
        cls._log("[ShutdownManager] Todos os hooks finalizados.", "general")
    
    @classmethod
    def prepare_class(cls,register_log,lifecycleMaster):
        cls._log = register_log
        cls.LifecycleMaster = lifecycleMaster
    # ------------------------------------------------


if __name__ == "__main__":
    manager = GraciousCleanupManager
    # a.prepapre_class(lambda x:print(x),)