# from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
import traceback
import functools
import asyncio
import inspect
import reprlib
import threading
from datetime import datetime

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

class errorExtruture():
    lifeCycleMaster = None
    lifecycleState = None
    # stateEnum = None
    # loggerManager = None
    logger = None
    devMode = None # isso tem que vir da origem pra que eu não tenha um monte de bandeiras diferentes
    Logging = True

    @classmethod
    def set_lifecycle_master(cls, lifecycleMaster, loggerManager):
        try:
            cls.lifeCycleMaster = lifecycleMaster 
            cls.lifecycleState = lambda :  lifecycleMaster.lifecycleState.state
            # cls.loggerManager = loggerManager
            cls.logger = loggerManager.get_logger(name = "forensics_error", filename = "forensics_error.txt")

            # print("[errorExtruture.set_lifecycle_master] LifecycleMaster ,State e logger configurados no errorExtruture")
            # cls.stateEnum = lifecycleMaster.stateEnum 
        except Exception as e:
            log_error_forensics_plus(e,extra_message="[errorExtruture.set_lifecycle_master] Erro ao configurar o LifecycleMaster no errorExtruture")

# from sharedResources.pythonLoggerSistem.logger import LoggerManager
r = reprlib.Repr()
r.maxstring = 100 # Limita strings
r.maxother = 100   # Limita outros objetos

def monitor_error(func):
    # Detecta se a função original é async
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func) # 1. Copia o nome 'enqueue' para 'async_wrapper'
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                raise 
            except Exception as e:
                log_error_forensics_plus(e)
                raise e 
        
        # 2. (Opcional/Paranóia) Se você quiser ter 1000% de certeza 
        # que o objeto função tem o nome certo, o wraps já fez isso.
        # async_wrapper.__name__ já é igual a func.__name__ aqui.
        
        return async_wrapper # Retorna uma FUNÇÃO async (count_calls entende isso!)
        
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error_forensics_plus(e)
                raise e
        return sync_wrapper
  



def log_error_forensics_plus(e: Exception, 
                             extra_message: str = "",*,  
                             printar = True , 
                             retornar = False,
                             cancelLogging = True):
    
    try:
        try:
            if not errorExtruture.Logging:

                return 
            current_task = asyncio.current_task()
            if current_task:
                task_info = (
                    f"ID: {id(current_task)} | "
                    f"Nome: {current_task.get_name()} | "
                    f"Coro: {current_task.get_coro().__name__ if hasattr(current_task.get_coro(), '__name__') else 'N/A'}"
                )
                # Tenta pegar flag protected se existir
                is_protected = getattr(current_task, 'protected', 'N/A')
                task_info += f" | Protected: {is_protected}"
                task_info += f" | Total Tasks Vivas: {len(asyncio.all_tasks())}"
            else:
                task_info = "Nenhuma Task (Código Síncrono/Thread Pura)"
        except RuntimeError:
            task_info = "Fora de um Event Loop"
        
        
        tb = e.__traceback__
        
        # 1. Localiza o frame do ERRO (onde explodiu)
        error_traceback = tb
        while error_traceback.tb_next:
            error_traceback = error_traceback.tb_next
        error_frame = error_traceback.tb_frame
        
        # 2. Localiza o frame da CHAMADA (quem chamou a função que deu erro)
        caller_frame = error_frame.f_back
        while caller_frame and (caller_frame.f_code.co_name == "run_async" or "wrapper" in caller_frame.f_code.co_name.lower()):
            caller_frame = caller_frame.f_back

        def format_vars(frame_obj):
            if not frame_obj: return "    Nenhum frame disponível"
            return "\n".join([f"    {k} = {r.repr(v)}" for k, v in frame_obj.f_locals.items() if not k.startswith('__')])

        # Extração de dados para o cabeçalho
        try:
            extract = traceback.extract_tb(tb)[-1]
            filename = extract.filename
            lineno = extract.lineno
            line_code = extract.line
        except IndexError:
            filename = "Desconhecido"
            lineno = "?"
            line_code = "N/A"

        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        thread_info = threading.current_thread().name

        current_stack = traceback.extract_stack()[:-1]

        # 2. Pega o local exato do erro (Traceback do objeto de exceção)
        # É aqui que mora a linha 'raise ValueError(...)' que você quer ver!
        exception_stack = traceback.extract_tb(e.__traceback__)

        # 3. Junta as duas listas para criar a história completa
        full_raw_stack = current_stack + exception_stack

        # 4. Filtra: Remove bibliotecas do sistema E o próprio arquivo do monitor/wrapper
        excluded_path_terms = [
            "site-packages", "dist-packages", "/usr/lib/", "lib/python", 
            "<frozen", "threading.py", "asyncio",
            # ADIÇÃO IMPORTANTE: O nome do arquivo do seu monitor para esconder o wrapper
            # "unified_monitor.py", 
            # "error_tracker.py"
        ]

        # Lista de nomes de funções que queremos esconder explicitamente (os wrappers)
        excluded_functions = [
            "unified_sync_wrapper", 
            "unified_async_wrapper", 
            "wrapper", 
            "log_error_forensics_plus"
        ]

        filtered_frames = []
        seen_frames = set() # Para evitar duplicatas na emenda das listas

        for frame in full_raw_stack:
            # Cria uma chave única para o frame (arquivo + linha)
            frame_id = (frame.filename, frame.lineno)
            
            # Se já vimos esse frame ou ele é "proibido", pula
            if frame_id in seen_frames:
                continue
                
            # Filtro de Arquivos de Sistema / Monitor
            if any(term in frame.filename for term in excluded_path_terms):
                continue
                
            # Filtro de Nomes de Função (Esconde o wrapper)
            if frame.name in excluded_functions:
                continue

            seen_frames.add(frame_id)
            filtered_frames.append(frame)

        # # 5. Formata
        # if filtered_frames:
        #     call_stack = "".join(traceback.format_list(filtered_frames))
        # else:
        #     call_stack = "    [Nenhum frame de código do usuário encontrado]\n"

        # 3. Formata apenas os frames que sobraram (o seu código)
        if filtered_frames:
            call_stack = "".join(traceback.format_list(filtered_frames))
        else:
            call_stack = "    [Nenhum frame de código do usuário encontrado na pilha]\n"
        # Traceback do erro (Do ponto da falha para baixo)
        exception_trace = "".join(traceback.format_exception(type(e), e, tb))
        ciclo_de_vida = "undefined"
        try:
            ciclo_de_vida = errorExtruture.lifecycleState()
        except Exception as e:
            print("[log_error_forensics_plus] Erro ao obter o estado do ciclo de vida e foi: ",str(e))
            # print("errorExtruture.lifecycleState is None or not callable")

        full_message = (
            f"\n{'='*70}\n"
            f"🕵️ INVESTIGAÇÃO PROFUNDA: [{type(e).__name__}]\n"
            f"📍 No arquivo: {filename} | Linha: {lineno}\n"
            f"💻 Código: `{line_code}`\n"
            f"🕒 Horário: {agora} | 🧵 Thread: {thread_info}  Task: {task_info}\n "
            f"💬 Mensagem: {str(e)}\n"
            f"extra_message = {extra_message}\n"
            f"internal vars from log_error_forencis_plus:\n"
            f"errorExtruture.devMode : {errorExtruture.devMode}\n"
            f"printar : {printar}\n"
            f"retornar : {retornar}\n\n"
            f"Estado do ciclo de vida: {ciclo_de_vida}\n"
            f"{'-'*30}\n"
            f"📦 VARIÁVEIS NO MOMENTO DO ERRO (Local):\n{format_vars(error_frame)}\n"
            f"{'-'*30}\n"
            f"🏗️ VARIÁVEIS NO MOMENTO DA CHAMADA (Caller - {caller_frame.f_code.co_name if caller_frame else 'N/A'}):\n{format_vars(caller_frame)}\n"
            f"{'='*70}\n"
            f"📜 RASTRO COMPLETO (Call Stack + Error):\n"
            f"{call_stack}"  # Mostra o caminho até o wrapper (incluindo o runner)
            f"{'-'*20} [Ponto de Captura do Erro] {'-'*20}\n"
            f"{exception_trace}" # Mostra o erro em si
            f"{'X'*60}"
        )
    except:
        pass    
    if hasattr(errorExtruture,'logger') and errorExtruture.logger is not None:
        try:
            if errorExtruture.Logging:
                errorExtruture.logger.warning(full_message)
            
        except Exception as e:
            pass
            # print(f"[Profunda] - Erro ao registrar o log na forensics: {e}")
        finally:
            if cancelLogging: # apos o comando de parar de logar ela não loga mais, porém na chamada que veio o comando ela ainda vai logar

                errorExtruture.Logging = False
        

    else:
        print("[Profunda] - não consegui registrar o log na forensics!")
        print(full_message)

    if errorExtruture.devMode == True:
        if printar:
            print(full_message)

    if retornar:
        return full_message

if __name__ == "__main__":

    @monitor_error
    def div(a,b):
        print("comecei a função")
        return a/b
    div(3,2)
    div(6,1)
    div(2,0)


  
