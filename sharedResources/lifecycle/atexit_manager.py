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
    # _checkpoint_inicial_format = {"occurrences": "undefined", "checked": {"counter":0, "ts_history": []}} # formato inicial para os checkpoints, usado para garantir que todos os checkpoints tenham o mesmo formato e evitar erros de chave, o ts_history é uma lista de timestamps de quando o checkpoint foi checado, para ter uma visão temporal do shutdown no relatório final do atexit
    checkpoints = {}
    funcRefs = {} # opcional: pode guardar referências para as funções decoradas se quiser (mas cuidado com memória se for muita coisa)
    _log_history =[] # aqui ficará registrada, como string a sucessao dos registros e ocorrências, para que no relatório final do atexit eu possa mostrar o caminho percorrido durante o shutdown,
    _lock = threading.Lock() # log threadsafe
    _report_only_fails = False # flag controla se mostra apenas checkpoints que falharam ou todos!
    _imprevisto_ocorreu = False # flag para sinalizar de imprimir o log inteiro
    _sufixo_pos_atexit = "_atexit" # sufixo que é adicionado automaticamente aos checkpoints registrados durante a finalização do interpretador para evitar confusão no relatório final do atexit, e para garantir que eles sejam registrados mesmo se a função check for chamada sem o checkpoint ter sido registrado antes (o que pode acontecer se a função check for chamada durante a finalização do interpretador e o checkpoint não tiver sido registrado antes, nesse caso ele é registrado automaticamente com o sufixo e a ocorrência é contada normalmente, mas com um aviso no log para evitar confusão)
    _allowed_phases = ["enter", "success", "error", "finally"] # fases permitidas para checkpoints de função, para garantir consistência no relatório final do atexit e evitar erros de digitação
    _is_already_finalizing = False
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
    def is_finalizing(cls):
        # if not cls._is_already_finalizing and sys.is_finalizing():
        #     print("detectei o is_finalizing")
        #     cls._is_already_finalizing = True
        return cls._is_already_finalizing
    
    @classmethod
    def _get_iniciated_checkpoint_format_copy(cls,occurrences = 1):
        return {
                "occurrences": occurrences, 
                "checked": {
                        "counter":0, 
                        "ts_history": list()
                           },
                "has_atexit_copy":False,
                "is_atexit_copy": False
                }

    @classmethod
    def get_names(cls,name):
        # normalized_name, finalizing_name = cls.get_names(name)
        normalized_name = name[:-len(cls._sufixo_pos_atexit)] if name.endswith(cls._sufixo_pos_atexit) else name
        finalizing_name = normalized_name + cls._sufixo_pos_atexit
        return normalized_name,finalizing_name
    
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
    def register(cls,func,*args,**kwargs):
        """
        usada para ativar o controle da flag do inicio do processo do atexit
        ao registrar as funções por aqui
        """
        @functools.wraps(func)
        def wrapper():
            cls._is_already_finalizing = True
            return func(*args,**kwargs)
        
        atexit.register(wrapper)

    @classmethod
    def _register_function_checkpoints(cls, base, occurrences = 1 ):
        """
             para registrar checkpoints de função automaticamente .
             se ela ja for registrada da erro!!!
             se tentar registrar durante finalização sem ter registrado antes da erro tbm!
        """
        ####### preciso garantir que essa função não faça nada além de registrar os checkpoints e 
        ## não tenha efeitos colaterais, e que ela não registre se a coisa ja foi registrada!
        ###    para evitar confusão no relatório final do atexit,
        # print("[_register_function_checkpoints] init")
        normal_base, final_base = cls.get_names(base)
        
        if cls.is_finalizing(): # trata sufixo e da erro se estiver tentando registrar depois do atexit algo que não foi registrado antes
            if normal_base not in cls.checkpoints:# impede registro de função, durante o atexit, que não tenha sido registrada antes
                raise RuntimeError(f"trying to register function checkpoints for normal_base: {normal_base} - base :  {base} but the interpreter is already finalizing, only normal execution is allowed!!!")
        
            if final_base in cls.checkpoints: # durante o atexit não quero que dê erro tentar registro duplicado, apenas ignoro
                # print("[_register_function_checkpoints] returning on finilizing already registered")
                return
            correct_base = final_base
        else:
            correct_base = normal_base
            if correct_base in cls.checkpoints: # evita que registros sejam repetidamente criados fora do atexit!
                raise RuntimeError(f"trying to register function checkpoints but this {base} function already has checkpoints registered!!!")

        # aqui o registro é efetivamente feito!   
        # print(f"[_register_function_checkpoints] trying to really register {base}")
        cls.checkpoints[correct_base] = {
            attr: cls._get_iniciated_checkpoint_format_copy(occurrences)
            for attr in cls._allowed_phases
        }
        # print("[_register_function_checkpoints] register made")
        if correct_base == final_base: #registra os links entre os checkpoints normais e pós atexit
            # print("[_register_function_checkpoints] and its final!!")
            cls.checkpoints[final_base]["is_atexit_copy"]   = True
            cls.checkpoints[normal_base]["has_atexit_copy"] = True
            cls._log(f"registrada a atexit copy da função {normal_base}")
        else: #registra os links com valor padrão.
            # print("[_register_function_checkpoints] and its normal")
            cls.checkpoints[normal_base]["is_atexit_copy"]  = False
            cls.checkpoints[normal_base]["has_atexit_copy"] = False 
            cls._log(f"registrada a função {correct_base} com {occurrences} ocorrências esperadas.")
        # print("[_register_function_checkpoints] end")

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
        if data["is_atexit_copy"]:
            # print(f" {base} is atexit_copy ")
            return # para não printar sobre as copias de atexit
        report = f" - {base}: "
        base_pieces = base.split('.')
        simple_base = base_pieces[-2] + "." + base_pieces[-1] #mostra apenas os dois ultimos pedaços da base

        occur = data['success']['occurrences']

        n_success = data['success']['checked']['counter']
        n_enter = data['enter']['checked']['counter']
        n_error = data['error']['checked']['counter']
        n_finally = data['finally']['checked']['counter']
        # if data["has_atexit_copy"]:
        #     n_success += 1
        #     n_enter   += 1 
        #     n_finally += 1
        perfect = False

        if n_enter == occur and n_success == occur and n_error == 0 and n_finally == occur:
            report = ""
            report = f" - {simple_base}: ✅ Função executou perfeitamente todas as vezes({occur}) normalmente"
            perfect = True

        final_base = f"{base}{cls._sufixo_pos_atexit}"
        if final_base in cls.checkpoints: # se tiver um checkpoint de finalização automático registrado para essa função
            n_success += cls.checkpoints[final_base]['success']['checked']['counter']
            n_enter += cls.checkpoints[final_base]['enter']['checked']['counter']
            n_error += cls.checkpoints[final_base]['error']['checked']['counter']
            n_finally += cls.checkpoints[final_base]['finally']['checked']['counter']
            if n_enter == occur and n_success == occur and n_error == 0 and n_finally == occur:
                report = ""
                report += f" - {simple_base}: ✅ Função executou perfeitamente todas as vezes({occur}). Com execução no atexit "
                perfect = True
            else:
                report += f"\n Função tinha final_base registrada mas as ocorrencias não bateram direito"
                
        
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
            report += f""" inconsistência no finally (quant:{n_finally}) ou no número de saídas (success + error: {n_success + n_error}) algum deles é maior do que o número de entradas ({n_enter})."""
        
        if not perfect:
            report += f"\n ❌ (enter: {n_enter}/{occur}, success: {n_success}/{occur}, error: {n_error}/0, finally: {n_finally}/{occur})"
            cls._imprevisto_ocorreu = True
        if not perfect or not cls._report_only_fails:
            print(report)

    @classmethod
    def register_checkpoint(cls,name, occurrences = 1):
        """
        usada para registrar checkpoints manuais, ou seja, não relacionados a funções decoradas,
        para isso basta chamar a função check com o nome do checkpoint registrado quando o evento ocorrer,
        se o checkpoint ja existir ela da erro! não podem haver checkpoints manuais com o mesmo nome, 
        para evitar confusão no relatório final do atexit.
        """
        normalized_name, finalizing_name = cls.get_names(name)        

        if cls.is_finalizing():
            if normalized_name not in cls.checkpoints: #não permite registro de ponto novo no atexit
                raise RuntimeError("trying to register on atexit what as not registered before")
            if finalizing_name not in cls.checkpoints: # registra o finalizing caso ainda não exista
                cls.checkpoints[finalizing_name] = cls._get_iniciated_checkpoint_format_copy(occurrences)
                # registra as ancoras devidas nos registros comuns e de finalizing
                cls.checkpoints[finalizing_name]["is_atexit_copy"] = True
                cls.checkpoints[normalized_name]["has_atexit_copy"] = True
                cls._log(f"[atexitShutdownMonitor - {time.perf_counter()}] registro de checkpoint durante o atexit feito")
             
        else:    
            if name in cls.checkpoints:
                raise RuntimeError(f"trying to register checkpoint but this {name} checkpoint already exists!!!")
            else:
                cls.checkpoints[name] = cls._get_iniciated_checkpoint_format_copy(occurrences)
                cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint registrado: {name} com {occurrences} ocorrências esperadas.")
    
    @classmethod
    def _register_finalizing_name(cls,name,phase = None):
        # print("[_register_finalizing_name] init")
        normalized_name, finalizing_name = cls.get_names(name)
        
        if finalizing_name not in cls.checkpoints: # registra o checkpoint de finalização automaticamente se ele ainda não tiver sido registrado
            # print("[_register_finalizing_name] vou registrar")
            if phase is None:
                # print("[_register_finalizing_name] é ponto avulto")
                cls.register_checkpoint(finalizing_name) #registro de ponto normal
            else:
                # print("[_register_finalizing_name] é ponto de função")
                cls._register_function_checkpoints(finalizing_name) #registro de todos os pontos da função
            
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint feito para {name} como {finalizing_name} durante a finalização do interpretador.")
        # print("[_register_finalizing_name] end-")
        return finalizing_name
    
    @classmethod
    def check(cls,name,phase = None):
        if cls.is_finalizing():
            # print("check occurring during is_finalizing")
            name = cls._register_finalizing_name(name,phase)
        else:
            pass
            # print("check occurring while not finalizing")
        
        if name not in cls.checkpoints:# segurança para evitar de quebrar o shutdown
            warnings.warn(f"trying to check checkpoint {name} but it doesn't exist!!!")
            return
            # raise RuntimeError(f"trying to check checkpoint {name} but it doesn't exist!!!")

        if phase is None: # checkpoint manual, sem fases, só conta as ocorrências
            with cls._lock:
                cls.checkpoints[name]["checked"]["counter"] += 1
                cls.checkpoints[name]["checked"]["ts_history"].append(time.perf_counter())
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint ocorrido: {name} ({cls.checkpoints[name]['checked']['counter']}/{cls.checkpoints[name]['occurrences']} ocorrências verificadas).")
        else: # checkpoint de função, com fases enter, success, error e finally, conta as ocorrências de cada fase separadamente para ter um relatório mais detalhado no final do atexit
            if phase not in cls._allowed_phases:
                raise ValueError(f"invalid phase {phase} for checkpoint {name}!!!")
            with cls._lock:
                cls.checkpoints[name][phase]["checked"]["counter"] += 1
                cls.checkpoints[name][phase]["checked"]["ts_history"].append(time.perf_counter())
            cls._log(f"[AtexitShutdownMonitor - {time.perf_counter()}] Checkpoint ocorrido: {name} - {phase} ({cls.checkpoints[name][phase]['checked']['counter']}/{cls.checkpoints[name][phase]['occurrences']} ocorrências verificadas).")

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
        print("[tracker] init")
        if not callable(func): #🔒 Garantia: apenas funções
            raise TypeError(
                f"shutdown_checkpoint só pode ser usado em funções e isso é: {type(func)} com valor {func}"
            )
        
        if inspect.iscoroutinefunction(func):# 🔒 Garantia: apenas funções sync, por enquanto, talvez eu mude isso
            # não monitora funções async dessa forma!
            return func
            # raise TypeError(
            #     f"shutdown_checkpoint não suporta funções async: {func.__name__}"
            # )
        
        base = f"{func.__module__}.{func.__qualname__}"
        print("[tracker] the base is:",base)

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
            print("!!!! tentando registrar funcao no controle de atexit!!!!")
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
                if not cls.is_finalizing():
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
        # print(f"entrei no _print_standalone_checkpoint_report e a name é:{name} e a data é:{data}")
        try:
            if data["is_atexit_copy"]:
                print(f"{name } isso aqui é uma atexit_copy!")
                print("data is: ",str(data))
                return # para não printar coisas repetidas
            else:
                pass
                # print('não é atexit_copy, continuando')
            
            incidencias = data["checked"]["counter"]
            # print("incidencias inicialmente é:",incidencias)
            if data["has_atexit_copy"]:
                print("corrigindo incidencias por causa de atexit")
                incidencias += cls.checkpoints[name + cls._sufixo_pos_atexit]["checked"]["counter"]
                print("incidencias pos correcao de atexit é: ",incidencias)
            espectativa = data["occurrences"]
            # print("espectativa de incidências é: ",espectativa)

            status = "OK" if incidencias == espectativa else "❌ FALHOU"
            # print("status é: " , status)
            if status != "OK":
                cls._imprevisto_ocorreu = True
                if incidencias > data['occurrences']:
                    reason = " excesso "
                elif incidencias < data['occurrences']:
                    reason = " falta "
                print("razao é: ",reason)

            result = f" - {name}: {incidencias}/{data['occurrences']} ocorrências (Status: {status}  {' - ' + reason if status != 'OK' else ''}) "
            # print("resultado é: ",result)
            if status != "OK" or not cls._report_only_fails:
                print(result)
        except Exception as e:
            if log_error_forencis_plus:
                log_error_forencis_plus(e)
            else:
                print("[_print_standalone_checkpoint_report] deu erro e foi: ",str(e))
                print("name: ",name)
                print("data: ",str(data))
                print("espectativa: ",espectativa)
                print("incidencias: ",incidencias)
                print("status: ",status)
                print('result: ',result)
                raise
    @classmethod
    def report(cls, only_fails = False):
        try:
            cls._report_only_fails = only_fails
            # cls._imprevisto_ocorreu = False
            if not cls.checkpoints:
                print("\n[atexit] No checkpoints registered.")
                return

            print(f"\n[atexit] Checkpoint Report ({len(cls.checkpoints)} points):")
            for name, data in cls.checkpoints.items():
                if "occurrences" in data:
                    # print(f"tentando acessar relatório de checkpoint standalone,name ={name} e data = {data}")
                    cls._print_standalone_checkpoint_report(name, data)
                    # print
                else:# aqui vou cuidar de imprimir o relatório das funções
                    # print("tentando printar relatório de função")
                    cls._print_function_report(base = name, data = data)
            if cls._imprevisto_ocorreu:
                cls.print_log_history()
                cls._stop_watchdog = True # Para a thread de monitoramento, mas o relatório só é gerado no final do atexit, 
        except Exception as e:
            if log_error_forencis_plus: 
                log_error_forencis_plus(e) 
            else:
                print("deu erro no report e a log_erro_forencis_plus ja se foi então o erro é: ",str(e))   

    

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
            pass
            # print("\n[atexit] get_loop() retornou um loop válido para a função do MyLoop.")

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
    # print("the sistem is finalizing: ",sys.is_finalizing())
    print("="*40 + "\n")

AtexitShutdownMonitor.register(AtexitShutdownMonitor.report, only_fails = False) # Registra o relatório de checkpoints do shutdown para rodar no atexit, mostrando apenas os que falharam
AtexitShutdownMonitor.register(atexit_diagnostics)