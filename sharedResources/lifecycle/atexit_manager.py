# from sharedResources.lifecycle.atexit_manager import AtexitShutdownMonitor


import functools
import inspect
import multiprocessing
import threading
import asyncio
import socket
import atexit
import stat
import sys
import os
import time
import uuid
import warnings
import sys

get_loop = None # Será setado pelo MyLoop para evitar dependência circular
# mas a função real de get_loop deve ser definida no MyLoop para garantir que o loop 
# correto seja retornado 
log_error_forencis_plus = None # Será setado pelo errorExtruture para evitar dependência circular

class AtexitShutdownMonitor():
    """
        class intended to be used as a checkpoint system for the atexit diagnostics, 
        you can register checkpoints with a name and how many times they are supposed to occur, 
        then you can check them when they occur and at the end you can have a report of how many 
        checkpoints were checked and how many were supposed to be checked, 
        this is useful to track if certain parts of the shutdown process were reached or not.
    """
    checkpoints = {}
    funcRefs = {} # opcional: pode guardar referências para as funções decoradas se quiser (mas cuidado com memória se for muita coisa)
    _log_history =[] # aqui ficará registrada, como string a sucessao dos registros e ocorrências, para que no relatório final do atexit eu possa mostrar o caminho percorrido durante o shutdown,
    _checkpoint_inicial_format = {"occurrences": "undefined", "checked": 0}
    _lock = threading.Lock() # log threadsafe
    _report_only_problems = False # controla se mostra apenas checkpoints que falharam ou todos!
    _imprevisto_ocorreu = False # flag para sinalizar de imprimir o log inteiro
    

    # --- Nova Infraestrutura de Watchdog ---
    _pending_tasks = {} # {task_id: {"deadline": float, "name": str}}
    _watchdog_thread = None
    _stop_watchdog = False
    _maintain_alarm = True # flag to remove or not the function that is taking to long from the pending_tasks after it triggers the alarm, useful to avoid multiple alarms for the same task if it's taking too long but we already know that, but can cause alarm spam if the task is really stuck and we want to be notified about it multiple times during the shutdown process

    @classmethod
    def start_watchdog(cls):
        """Inicia a thread única de monitoramento global."""
        if cls._watchdog_thread and cls._watchdog_thread.is_alive():
            return
        
        cls._stop_watchdog = False
        cls._watchdog_thread = threading.Thread(target=cls._watchdog_loop, daemon=True, name="ShutdownWatchdog")
        cls._watchdog_thread.start()
        cls._log("Watchdog Central iniciado.")

    @classmethod
    def _watchdog_loop(cls):
        print("[AtexitShutdownMonitor] Watchdog Central rodando...")
        while not cls._stop_watchdog : # Continua rodando até o final da finalização do interpretador para garantir que checa as tarefas mesmo durante a finalização
            now = time.perf_counter()
            to_remove = []
            
            with cls._lock:
                for task_id, info in list(cls._pending_tasks.items()):
                    if now > info["deadline"]:
                        msg = f"🚨 TIMEOUT CRÍTICO: '{info['name']}' travada há > {now - (info['deadline'] - 5):.2f}s!"
                        cls._log(msg)
                        print(f"\n{msg}") # Print imediato para não depender do report final
                        cls._imprevisto_ocorreu = True
                        if not cls._maintain_alarm:
                            to_remove.append(task_id)
                
                for tid in to_remove:
                    cls._pending_tasks.pop(tid, None)
            
            time.sleep(0.5) # Frequência de checagem
        print("[AtexitShutdownMonitor] Watchdog Central finalizado.")



    @classmethod
    def _get_iniciated_checkpoint_format_copy(cls,ocurrencies = 1):
        return {"occurrences": ocurrencies, "checked": 0}

    @classmethod
    def _log(cls, msg):
        with cls._lock:
            cls._log_history.append(f"[{time.perf_counter():.4f}] {msg}")

    @classmethod
    def print_log_history(cls):
        print("\n[atexit] Log History during shutdown:")
        for entry in cls._log_history:
            print(f" - {entry}")

    @classmethod
    def _register_function_checkpoints(cls, base, occurrences = 1 ):
        """
             para registrar checkpoints de função automaticamente .
             se ela ja for registrada da erro!!!
        """
        ####### preciso garantir que essa função não faça nada além de registrar os checkpoints e 
        ## não tenha efeitos colaterais, e que ela não registre se a coisa ja foi registrada!
        ###    para evitar confusão no relatório final do atexit,
        if base in cls.checkpoints:
            raise RuntimeError(f"trying to register function checkpoints but this {base} function already has checkpoints registered!!!")
        
        cls.checkpoints[base] = {
            attr: cls._get_iniciated_checkpoint_format_copy(occurrences)
            for attr in ["enter", "success", "error", "finally"]
        }
        
        cls._log(f"registrada a função {base} com {occurrences} ocorrências esperadas.")

    @classmethod
    def _get_func_checks(cls, base): # função para obter os dados de checkpoints de uma função registrada, usada para debug e para o relatório final do atexit
        func_checks = cls.checkpoints.get(base, None)
        if func_checks is None:
            cls._log(f"[AtexitShutdownMonitor] Function {base} has no checkpoints registered.")
            raise RuntimeError(f"trying to get function checkpoints but this {base} function has no checkpoints registered!!!")
        else:
            expected_occurrences = func_checks.get("enter", {}).get("occurrences", "undefined")
            return {**func_checks, "expected_occurrences": expected_occurrences}
    

    @classmethod
    def _print_function_report(cls, base, data):
        report = f" - {base}: "
        occur = data.get("success", {}).get("occurrences", "undefined")
        n_success = data.get("success", {}).get("checked", "undefined")
        n_enter = data.get("enter", {}).get("checked", "undefined")
        n_error = data.get("error", {}).get("checked", "undefined")
        n_finally = data.get("finally", {}).get("checked", "undefined")
        perfect = False
        if n_enter == occur and n_success == occur and n_error == 0 and n_finally == occur:
            report += f"✅ Função executou perfeitamente todas as vezes({occur}). "
            perfect = True
        if  n_error > 0 :
            report += f" lançou exceção(s): {n_error} erro(s), {n_success} sucesso(s)"
        if n_enter > occur:
            report += f" entrou mais vezes do que o esperado: entrou {n_enter} vezes de {occur} ocorrências esperadas. "
        if n_enter < occur:
            report += f" não entrou todas as vezes esperadas: entrou {n_enter} vezes de {occur} ocorrências esperadas. "
        if n_enter > n_finally:
            report += f" não chegou ao finally todas as vezes que entrou: finalizou {n_finally} vezes de {n_enter} entradas. "        
        if n_enter != n_success + n_error:
            report += f" tem um número de entradas ({n_enter}) diferente do número de saídas (success: {n_success} + error: {n_error}). "
        if n_finally > n_enter or  n_success + n_error > n_enter:
            report += f""" inconsistência no finally ({n_finally}) ou no número de saídas (success + error: {n_success + n_error}) algum deles é maior do que o número de entradas ({n_enter})."""
        
        if not perfect:
            report += f"\n ❌ (enter: {n_enter}/{occur}, success: {n_success}/{occur}, error: {n_error}/0, finally: {n_finally}/{occur})"
            cls._imprevisto_ocorreu = True
        if cls._report_only_problems:
            if not perfect:
                 print(report)
        else:
            print(report)

    @classmethod
    def register_checkpoint(cls,name, occurrences = 1):
        """
        usada para registrar checkpoints manuais, ou seja, não relacionados a funções decoradas,
        para isso basta chamar a função check com o nome do checkpoint registrado quando o evento ocorrer,
        se o checkpoint ja existir ela da erro! não podem haver checkpoints manuais com o mesmo nome, 
        para evitar confusão no relatório final do atexit.
        """
        if name in cls.checkpoints:
            raise RuntimeError(f"trying to register checkpoint but this {name} checkpoint already exists!!!")
        else:
            cls.checkpoints[name] = {"occurrences" : occurrences, "checked": 0}
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint registrado: {name} com {occurrences} ocorrências esperadas.")
    
    @classmethod
    def check(cls,name,phase = None):
        if name not in cls.checkpoints:# segurança para evitar de quebrar o shutdown
            warnings.warn(f"trying to check checkpoint {name} but it doesn't exist!!!")
            return
            # raise RuntimeError(f"trying to check checkpoint {name} but it doesn't exist!!!")
        if sys.is_finalizing():
            print("[Warning] trying to check checkpoint during interpreter finalization, this check will be ignored to avoid potential issues!!!")
            return # segurança para evitar de tentar registrar checkpoints durante a finalização do interpretador
        if phase is None: # checkpoint manual, sem fases, só conta as ocorrências
            with cls._lock:
                cls.checkpoints[name]["checked"] += 1
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint ocorrido: {name} ({cls.checkpoints[name]['checked']}/{cls.checkpoints[name]['occurrences']} ocorrências verificadas).")
        else: # checkpoint de função, com fases enter, success, error e finally, conta as ocorrências de cada fase separadamente para ter um relatório mais detalhado no final do atexit
            if phase not in ["enter", "success", "error", "finally"]:
                raise ValueError(name = f"invalid phase {phase} for checkpoint {name}!!!")
            with cls._lock:
                cls.checkpoints[name][phase]["checked"] += 1
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint ocorrido: {name} - {phase} ({cls.checkpoints[name][phase]['checked']}/{cls.checkpoints[name][phase]['occurrences']} ocorrências verificadas).")

    @classmethod
    def _get_meta_for_functions(cls,base): # função para obter os dados de checkpoints e da função decorada, usada para debug e para o relatório final
        
        if base in cls.checkpoints and "enter" in cls.checkpoints[base] and "occurrences" in cls.checkpoints[base]["enter"]:
            occurrences = cls.checkpoints[base]["enter"]["occurrences"] 
        else:
            occurrences = "undefined"

        wrapper = cls.funcRefs[base]["wrapper"] if base in cls.funcRefs else None
        if wrapper is None:
            result = {"occurrences": occurrences, 
                      "properties": "undefined (function not registered or no wrapper reference)"
                      }
        else:
            result = {"occurrences": occurrences, 
                      "properties": {
                          "_shutdown_checkpointed": wrapper._shutdown_checkpointed, 
                          "allow_multiple": wrapper.allow_multiple
                        }
                    }    
        # wrapper._shutdown_checkpointed = True # Marca a função para evitar dupla decoração
        # wrapper.allow_multiple
        # result = {"occurrences": occurrences, "properties": {"_shutdown_checkpointed": cls.funcRefs[base]["wrapper"].}}
        return str(result)

    @classmethod
    def tracker(cls,func,*, occurrences = 1 ,allow_multiple = False,timeout=5):
        """
        usada para decorar funções que se quer monitorar durante o shutdown, 
        ela registra automaticamente checkpoints para a função decorada,
        se usada em função que ja foi decorada, ou registrada da erro
        """
        if not callable(func): #🔒 Garantia: apenas funções
            raise TypeError(
                f"shutdown_checkpoint só pode ser usado em funções e isso é: {type(func)} com valor {func}"
            )
        
        if inspect.iscoroutinefunction(func):# 🔒 Garantia: apenas funções sync, por enquanto, talvez eu mude isso
            raise TypeError(
                f"shutdown_checkpoint não suporta funções async: {func.__name__}"
            )
        
        base = f"{func.__module__}.{func.__qualname__}"

        if getattr(func, "_shutdown_checkpointed", False): 
            if not func.allow_multiple: # Evita dupla decoração
                raise RuntimeError(f"{func} já decorada!")
            else: # registra a dupla decoração mas avisa que isso aconteceu sem decorar de novo (para evitar confusão no relatório final)
                stringg = f"[AtexitShutdownMonitor] Função {base} já decorada, mas allow_multiple=True então permitindo múltiplas decorações."
                cls._log(stringg)
                # cls.register_checkpoint(stringg, occurrences = 1)
                # cls.check(stringg) # Conta a ocorrência extra para o relatório final
                return func # Retorna a função original sem redecorar para evitar confusão no relatório (mas a ocorrência extra já foi registrada)
        
    
        try:
            # Registro automático dos checkpoints
            cls._register_function_checkpoints(base, occurrences = occurrences) # Registra os checkpoints para essa função 
        except Exception as e: 
            """ caso tenha entrado a função original mas ja tenha sido registrada antes
            ela não vem com o wrapper que tem a flag de _shutdown_checkpointed, 
            (preciso investigar esse tipo de caso, caso ocorra!), 
            retorno a função decorada que eu ja tinha registrada para evitar redecorar 
            e bagunçar o relatório, mas sem contar ocorrências extras, 
            porque já foram contadas na primeira decoração)"""

            stringg = f"""[AtexitShutdownMonitor] Tentativa de registrar checkpoint para {base} mas já estava registrado, 
            meta: {cls._get_meta_for_functions(base)},
            """
            cls._log(stringg)

            if base in cls.funcRefs:
                if cls.funcRefs[base]["wrapper"] is not None:
                    if cls.funcRefs[base]["wrapper"].allow_multiple:
                        return cls.funcRefs[base]["wrapper"] # Retorna a função já decorada para evitar redecorar 
                    else:
                        raise RuntimeError(f"{base} já decorada e allow_multiple=False, múltiplas decorações não permitidas! Meta: {cls._get_meta_for_functions(base)}")
                else:
                    raise RuntimeError(f"{base} já decorada mas sem referência de wrapper para verificar allow_multiple! Meta: {cls._get_meta_for_functions(base)}")
            else:
                if log_error_forencis_plus:
                    log_error_forencis_plus(e, extra_message = f"""[AtexitShutdownMonitor] Erro ao registrar 
                                        checkpoint para {base} e não foi possível determinar se 
                                        múltiplas decorações são permitidas. Meta: {cls._get_meta_for_functions(base)}"""
                                        )
                else:
                    raise

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            task_id = str(uuid.uuid4())
            
            try:
            # Registra o início no Watchdog
                cls.check(base,"enter")
                inicio = time.perf_counter()
                if not sys.is_finalizing():
                    with cls._lock:
                        cls._pending_tasks[task_id] = {
                            "deadline": inicio + timeout,
                            "name": base
                        }
                result = func(*args, **kwargs)
                duracao = time.perf_counter() - inicio

                if timeout is not None and duracao > timeout:
                    cls._log(f"⚠️ [AtexitShutdownMonitor] Função {base} demorou {duracao:.2f}s para executar, o timeout era {timeout} segundos")
                cls.check(base,"success")
                return result
            except Exception:
                cls.check(base,"error")
                raise
            finally:
                with cls._lock:
                    cls._pending_tasks.pop(task_id, None)
                cls.check(base,"finally")

        wrapper._shutdown_checkpointed = True # Marca a função para evitar dupla decoração
        wrapper.allow_multiple = allow_multiple # Permite múltiplas decorações se necessário (mas só a primeira vai ser realmente decorada)
        
        cls.funcRefs[base] = {"original": func, "wrapper": wrapper} # Guarda referência para a função original (opcional, cuidado com memória se for muita coisa)
        
        return wrapper


    @classmethod
    def _print_standalone_checkpoint_report(cls, name, data):
        status = "OK" if data["checked"] == data["occurrences"] else "❌ FALHOU"
        if status != "OK":
            cls._imprevisto_ocorreu = True
            if data['checked'] > data['occurrences']:
                reason = " excesso "
            elif data['checked'] < data['occurrences']:
                reason = " falta "
        result = f" - {name}: {data['checked']}/{data['occurrences']} ocorrências (Status: {status}  {' - ' + reason if status != 'OK' else ''}) "
        if cls._report_only_problems:
            if status != "OK":
                print(result)
        else:
            print(result)

    @classmethod
    def report(cls, only_fails = False):
        cls._report_only_problems = only_fails
        # cls._imprevisto_ocorreu = False
        if not cls.checkpoints:
            print("\n[atexit] No checkpoints registered.")
            return

        print(f"\n[atexit] Checkpoint Report ({len(cls.checkpoints)} points):")
        for name, data in cls.checkpoints.items():
            if "occurrences" in data:
                cls._print_standalone_checkpoint_report(name, data)
            else:# aqui vou cuidar de imprimir o relatório das funções
                cls._print_function_report(base = name, data = data)
        if cls._imprevisto_ocorreu:
            cls.print_log_history()
            cls._stop_watchdog = True # Para a thread de monitoramento, mas o relatório só é gerado no final do atexit, 
            

    

def get_detailed_info(fd):
    try:
        mode = os.fstat(fd).st_mode
        
        if stat.S_ISSOCK(mode):
            # 1. Tenta ver se é Internet (TCP/UDP)
            try:
                s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
                peer = s.getpeername()
                return f"[TCP] Peer: {peer}"
            except:
                pass # Não é TCP/IP
            finally:
                s.close()

            # 2. Tenta ver se é Unix Domain (Local)
            try:
                # Criamos o socket usando AF_UNIX agora
                s = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
                path = s.getsockname()
                if isinstance(path, bytes):
                    path = path.decode(errors='replace')
                s.close() # Fecha o socket criado só para inspeção
                if not path:
                    return "[UNIX] Socket anônimo (comunicação interna)"
                return f"[UNIX] Path: {path}"
            except:
                return "[SOCKET] Tipo desconhecido (Raw/Netlink)"
            finally:
                s.close() # Fecha o socket criado só para inspeção

        elif stat.S_ISFIFO(mode): return "[PIPE] Canal de comunicação"
        elif stat.S_ISREG(mode):  return "[FILE] Arquivo regular"
        elif stat.S_ISCHR(mode):  return "[CHAR] Terminal/Dispositivo"
        
        return "[OUTRO] Recurso do Kernel"
    except Exception as e:
        return f"[ERRO] {e}"
       

def dump_fds():
    if os.name != "posix": return
    
    print(f"\n[atexit] Detalhamento de FDs:")
    fd_path = "/proc/self/fd"
    try:
        for fd_str in sorted(os.listdir(fd_path), key=int):
            fd = int(fd_str)
            try:
                target = os.readlink(f"{fd_path}/{fd_str}")
                info = get_detailed_info(fd)
                print(f" FD {fd:2} -> {info:30} | Path: {target}")
            except:
                continue
    except Exception:
        print("Erro ao ler /proc")

def dump_threads():
    threads = threading.enumerate()
    print(f"\n[atexit] Threads ainda ativas ({len(threads)}):")
    current_thread = threading.current_thread()
    for t in threads:
        status = "REGULAR" if not t.daemon else "DAEMON"
        # Indica se a thread que está rodando o diagnóstico é a mesma da lista
        suffix = " (Self)" if t is current_thread else ""
        print(f" - [{status}] {t.name} (ID: {t.ident}){suffix}")

def dump_asyncio():
    try:
        # Pega o loop atual sem criar um novo
        loop = get_loop()
        if not loop:
            print("\n[atexit] get_loop() não retornou um loop válido pra função do MyLoop.")

            loop = asyncio.get_running_loop() # fallback para o loop atual se get_loop não estiver setado
        else:
            print("\n[atexit] get_loop() retornou um loop válido para a função do MyLoop.")

        if loop.is_running():
            print("\n[atexit] Event loop ainda em execução!")
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if tasks:
                print(f"\n[atexit] {len(tasks)} Tarefas Asyncio pendentes:")
                for t in tasks:
                    print(f" - Task: {t.get_coro()}")
        else:
            pass
            # print("\n[atexit] Event loop não está mais em execução.")
        if loop.is_closed():
            print("\n[atexit] Event loop já fechado como eu queria!")
        else:
            print("\n[atexit] Event loop ainda não está fechado.")
        
        # O mais importante: tarefas que ficaram "penduradas"
    except (RuntimeError, NameError):
        # RuntimeError acontece se não houver loop no thread atual
        print("\n[atexit] Nenhum event loop ativo (provavelmente estamos fora do contexto async)")
        pass

def dump_processes():
    children = multiprocessing.active_children()
    if children:
        print(f"\n[atexit] {len(children)} Processos filhos ativos:")
        for p in children:
            # Verifica se o processo ainda está vivo de fato
            status = "Vivo" if p.is_alive() else "Zumbi/Terminado"
            print(f" - PID={p.pid}, Name={p.name}, Status={status}")
    else:
        print("\n[atexit] Nenhum processo filho ativo.")

# Flags de controle (idealmente viriam do seu manager real)
shutdown_iniciated = False # Sinaliza que o processo de shutdown começou (auto ou manual)
shutdown_finalized = False # Sinaliza que o processo de shutdown foi concluído (tudo finalizado)

def atexit_diagnostics():
    # Tenta garantir que o output saia mesmo se o stdout estiver sendo fechado
    sys.stdout.flush() 
    # AtexitShutdownMonitor.report() # Imprime o relatório de checkpoints do shutdown
    print("\n" + "="*40)
    print("      ATEXIT DIAGNOSTICS REPORT")
    print("="*40)
    
    dump_threads()
    dump_asyncio()
    dump_processes()
    dump_fds()

    print("\n--- Lifecycle Check ---")
    if not shutdown_iniciated:
        print("[AVISO] shutdown_iniciated é False! (Crash ou fechamento forçado)")
    elif not shutdown_finalized:
        print("[AVISO] shutdown_finalized é False! (O shutdown começou mas travou no meio)")
    else:
        print("[OK] Ciclo de vida encerrado corretamente.")
    
    print("="*40 + "\n")

atexit.register(AtexitShutdownMonitor.report, only_fails = False) # Registra o relatório de checkpoints do shutdown para rodar no atexit, mostrando apenas os que falharam
atexit.register(atexit_diagnostics)