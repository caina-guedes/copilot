# from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
import traceback
import functools
import warnings
import asyncio
import inspect
import time
import reprlib
import threading
from datetime import datetime

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.pythonLoggerSistem.logger import LoggerManager
r = reprlib.Repr()
r.maxstring = 100 # Limita strings
r.maxother = 60   # Limita outros objetos


def monitor_error(func):
    # Verifica se é async antes de envolver para manter a assinatura correta
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                # NÃO LOGA ERRO AQUI!
                # Apenas repassa o cancelamento para o loop saber que terminou ok.
                raise 
            except Exception as e:
                log_error_forensics_plus(e)
                raise e # Ou trate como preferir
        
        # --- O SEGREDO ESTÁ AQUI ---
        # Quando o wrapper é chamado, ele retorna uma corrotina. 
        # Vamos criar um "falso chamador" para que a corrotina se identifique como a original.
        @functools.wraps(func)
        def wrapper_dispatcher(*args, **kwargs):
            coro = wrapper(*args, **kwargs)
            # Forçamos a corrotina a ter o nome da função original no rastro
            coro.__qualname__ = func.__qualname__
            coro.__name__ = func.__name__
            return coro
            
        return wrapper_dispatcher
    else:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error_forensics_plus(e)
                raise e
        return wrapper


def log_error_forensics_plus(e: Exception, extra_message: str = ""):
    # --- O Pulo do Gato: Capturando a Task do Asyncio ---
    # Loop_Lag = None
    try:
        current_task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        # Loop_Lag =  loop.time() - time.time()
        # print("o Loop_Lag calculado foi: ",Loop_Lag)
        if current_task:
            task_info = (
                f"ID: {id(current_task)} | "
                f"Nome: {current_task.get_name()} | "
                f"Coro: {current_task.get_coro().__name__ if hasattr(current_task.get_coro(), '__name__') else 'N/A'}"
            )
            # Se você usou setattr(task, 'protected', ...), pegamos aqui:
            is_protected = getattr(current_task, 'protected', 'N/A')
            task_info += f" | Protected: {is_protected}"
            task_info += f" | Total Tasks Vivas: {len(asyncio.all_tasks())}"
        else:
            task_info = "Nenhuma Task (Código Síncrono/Thread Pura)"
    except RuntimeError:
        task_info = "Fora de um Event Loop"
    
    # if Loop_Lag is not None:
    #     print("o Loop_Lag é: ",Loop_Lag)
    #     task_info += f"  Loop_Lag: {Loop_Lag}"
    #     print("a task_info é: ", task_info)
    # else:
    #     print("o Loop_Lag é None")
    
    tb = e.__traceback__
    
    # 1. Localiza o frame do ERRO (onde explodiu)
    error_traceback = tb
    while error_traceback.tb_next:
        error_traceback = error_traceback.tb_next
    error_frame = error_traceback.tb_frame
     
    # 2. Localiza o frame da CHAMADA (quem chamou a função que deu erro)
    # O f_back nos leva para um nível acima na pilha
    caller_frame = error_frame.f_back
    while caller_frame and (caller_frame.f_code.co_name == "run_async" or "wrapper" in caller_frame.f_code.co_name.lower()):
        caller_frame = caller_frame.f_back

    def format_vars(frame_obj):
        if not frame_obj: return "    Nenhum frame disponível"
        return "\n".join([f"    {k} = {r.repr(v)}" for k, v in frame_obj.f_locals.items() if not k.startswith('__')])

    # Extração de dados para o cabeçalho
    extract = traceback.extract_tb(tb)[-1]

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    thread_info = threading.current_thread().name

    full_message = (

        f"\n{'='*70}\n"
        f"🕵️ INVESTIGAÇÃO PROFUNDA: [{type(e).__name__}]\n"

        f"📍 No arquivo: {extract.filename} | Linha: {extract.lineno}\n"
        f"💻 Código: `{extract.line}`\n"
        f"🕒 Horário: {agora} | 🧵 Thread: {thread_info}  Task: {task_info}\n "
        f"💬 Mensagem: {str(e)}\n"
        f"{'-'*30}\n"
        f"📦 VARIÁVEIS NO MOMENTO DO ERRO (Local):\n{format_vars(error_frame)}\n"
        f"{'-'*30}\n"
        f"🏗️ VARIÁVEIS NO MOMENTO DA CHAMADA (Caller - {caller_frame.f_code.co_name if caller_frame else 'N/A'}):\n{format_vars(caller_frame)}\n"
        f"{'='*70}"
        f"📜 STACK TRACE:\n"
        f"{''.join(traceback.format_exception(type(e), e, tb))}"
        f"{'X'*60}"
    )

    print(full_message)


if __name__ == "__main__":

    @monitor_error
    def div(a,b):
        print("comecei a função")
        return a/b
    div(3,2)
    div(6,1)
    div(2,0)

