# from sharedResources.generalUtils.print_interceptor import PrintInterceptor
import asyncio
import platform
import threading
import inspect
import struct
import queue
import sys
import os


import sys
from pathlib import Path
caminho = Path(__file__).resolve().parent.parent.parent
print("the path is:",caminho)
sys.path.append(caminho)

from sharedResources.debuggingResources.unified_monitor import monitor_class

MAGIC_NUMBER = b'\xaa\x55'

def _get_real_function(func):
    """made to dig the wrappers to the real function"""

    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func



def _get_caller_info(ignore_files=None, ignore_funcs=None):
    if ignore_files is None:
        ignore_files = {os.path.basename(__file__), "unified_monitor.py", "console.py"}
    if ignore_funcs is None:
        ignore_funcs = {"unified_sync_wrapper", "wrapper","_write_buffer"}

    frame = inspect.currentframe().f_back  # frame de quem chamou o print
    while frame:
        filename = os.path.basename(frame.f_code.co_filename)
        funcname = frame.f_code.co_name

        if filename not in ignore_files and funcname not in ignore_funcs:
            break  # achei o frame “real”
        frame = frame.f_back

    if not frame:
        return ("<unknown>", "<unknown>", 0)

    # Tenta pegar a função real se existir
    func_obj = frame.f_globals.get(frame.f_code.co_name)
    if func_obj:
        real_func = _get_real_function(func_obj)
        func_name = real_func.__name__
    else:
        func_name = frame.f_code.co_name
    fileName= os.path.basename(frame.f_code.co_filename)
    fileName = os.path.splitext(fileName)[0]
    func_name = " - " if func_name == "<module>" else func_name

    return (fileName, func_name, frame.f_lineno)


@monitor_class
class PrintInterceptor:
    os_sistem = platform.system().lower()
    log_error_forensics_plus = None
    last_context = {"file":"",
                    "func": ""}
    first_instance = None
    error_instance = None
    # locks
    stdout_lock = threading.Lock()
    stderr_lock = threading.Lock()
    stdin_lock = threading.Lock()
    active_flag_lock = threading.Lock()

    global_active = True

    original_stdout = None
    original_stderr = None
    
    queue_stdout = queue.Queue()
    queue_stderr = queue.Queue()
    
    stdout_thread = None
    stderr_thread = None
    
    CHUNK_SIZE_BYTES = 8192

    _is_new_line     = True
    _is_new_line_err = True

    stdin_excedente  = ''
    stdin_confirmacoes_excedentes = 0
    close_event = threading.Event()

    @classmethod
    def start_worker(cls,is_error ):
        """Inicia a thread que realmente escreve no stdout original."""
        try:
            right_queue = cls.queue_stderr if is_error else cls.queue_stdout
            async def worker(right_queue=right_queue,is_error = is_error):
                try:
                    while not cls.close_event.is_set():
                        # Pega o texto da fila (bloqueia aqui se estiver vazia)
                        try:
                            # dados_bytes = right_queue.get()
                            dados_bytes = await asyncio.wait_for(right_queue.get(), timeout=1.0)
                            if dados_bytes is None: break # Sinal de parada
                            cls.realWriter(dados_bytes,is_error)
                        except asyncio.TimeoutError:
                            pass
                        except Exception as e:
                            cls.log_error(e,is_error)
                            cls.close()
                        finally:
                            right_queue.task_done()  
                finally:
                    cls.close()
            
            def run():
                asyncio.run(worker(right_queue=right_queue,is_error = is_error))
            
            thread_name = 'stdout_thread' if not is_error else 'stderr_thread'
            
            if not is_error:
                if cls.stdout_thread is None:
                    if cls.original_stdout is None:
                        cls.original_stdout = sys.stdout
                    cls.stdout_thread = threading.Thread(target=run, daemon=True,name = thread_name)
                    cls.stdout_thread.start()
            else:
                if cls.stderr_thread is None:
                    if cls.original_stderr is None:
                        cls.original_stderr = sys.stderr
            
                    cls.stderr_thread = threading.Thread(target=run, daemon=True,name = thread_name)
                    cls.stderr_thread.start()
        except Exception as e:
            cls.log_error(e,is_error)
               
    @classmethod
    def get_active_flag(cls):
        try:
            with cls.active_flag_lock:
                return cls.global_active
        except Exception as e:
            cls.log_error(e)
               
    @classmethod
    def set_active_flag(cls, flag_value):
        try:
            with cls.active_flag_lock:
                cls.global_active = flag_value
        except Exception as e:
            cls.log_error(e)

    def __init__(self, active=True, is_error = False):
        try:
            if self.__class__.log_error_forensics_plus is None:
                # only to not have importing conflitcs that this is made here
                from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
                self.__class__.log_error_forensics_plus = log_error_forensics_plus
            if self.__class__.first_instance is None:
                self.__class__.first_instance = self
            
            self.active = active  # Controle de produção
            self._is_newline = True # Flag para controlar o prefixo
            self.is_error = is_error
            self.__class__.start_worker(is_error)
        except Exception as e:
            self.__class__.log_error(e)

    @classmethod
    def get_prefix(cls):
        try:
            file,func,line = _get_caller_info()
            if file == cls.last_context['file'] and func == cls.last_context['func']:
                return ""
            cls.last_context['file'] = file
            cls.last_context['func'] = func

            prefix = f"(\033[94m{file}:{func}:{line}Core.__holder__) "
            return prefix
        except Exception as e:
            cls.log_error(e)

    @classmethod                
    def flush_e_espera_resposta(cls,is_error):
        try:
            if not is_error:
                cls.original_stdout.flush()
            else:
                cls.original_stderr.flush()
                return  # para só esperar resposta se for print comum, se for erro mete o pé!
            with cls.stdin_lock:
                if cls.stdin_confirmacoes_excedentes>0:
                    cls.stdin_confirmacoes_excedentes -= 1
                    return True
                if "ACK" in cls.stdin_excedente :
                    while "ACK" in cls.stdin_excedente :
                        cls.stdin_excedente = cls.stdin_excedente.replace("ACK","",1)
                        cls.stdin_confirmacoes_excedentes += 1
                    cls.stdin_confirmacoes_excedentes -= 1
                    return True 
                elif len(cls.stdin_excedente) > 200:
                    cls.stdin_excedente ='' ## reseta a string caso tenha lixo

                ack = sys.stdin.readline()
                temp_string = cls.stdin_excedente +  ack.strip()  
                if temp_string.find("ACK") != -1:
                    sobra = temp_string.replace("ACK", "", 1)
                    if sobra != "":
                        cls.stdin_excedente += sobra
                    return True
                else:
                    return False
        except Exception as e:
            cls.log_error(e)    

    @classmethod
    def sendAndHandshake(cls,text,is_error):
        global MAGIC_NUMBER
        try:
            if not is_error: #aqui é print comum!
                # Prepara o header: Magic (2) + Size (4)
                header = MAGIC_NUMBER + struct.pack('I', len(text))
                cls.original_stdout.buffer.write(header + text)
                if cls.flush_e_espera_resposta(is_error):
                    ### aqui recebeu a resposta corrreta!
                    pass
                else:
                    ### aqui recebeu resposta diferente!!!!!
                    pass
            else: # aqui pro caso de ser erro!
                cls.original_stderr.buffer.write(text)
                cls.original_stderr.flush()
        except Exception as e:
            cls.log_error(e)
    @classmethod
    def realWriter(cls,text, is_error = False):
        try:
            lock_certo = cls.stdout_lock if not is_error else cls.stderr_lock
            right_new_line = cls._is_new_line if not is_error else cls._is_new_line_err 
            target = cls.original_stdout  if not is_error else cls.original_stderr 
                    
            with lock_certo:
                # Se o texto for apenas uma quebra de linha, printa direto
                quebra_de_linha = "\r\n" if cls.os_sistem.find("win") != -1 else '\n' 
                if text == quebra_de_linha:
                    target.write(text)
                    
                    target.flush()
                    if is_error:
                        cls._is_new_line_err = True
                    else:
                        cls._is_new_line     = True
                    return

                # else: # Só adiciona o prefixo se for o início de uma nova linha
                try:
                    prefix = cls.get_prefix() if right_new_line else ""
                    # cls.original_stdout.write("[PrintInterceptor.write] vou printar com prefixo!")
                    resposta = prefix + text 
                    dados_bytes = resposta.encode('utf-8', errors='replace')
                    if is_error:
                        cls._is_new_line_err = text.endswith('\n')
                    else:
                        cls._is_new_line = text.endswith('\n')
                    
                    if len(dados_bytes) <= cls.CHUNK_SIZE_BYTES:
                        cls.sendAndHandshake(dados_bytes,is_error)
                        # cls.original_stdout.buffer.write(dados_bytes)

                    else:
                        for i in range(0, len(dados_bytes), cls.CHUNK_SIZE_BYTES):
                            chunk = dados_bytes[i:i + cls.CHUNK_SIZE_BYTES]
                            cls.sendAndHandshake(chunk,is_error)
                            
                    
                except  Exception as e:
                    cls.log_error(e,is_error)
                    raise
        except Exception as e:
            cls.log_error(e)

    def write(self, text):
        # Se estiver desativado, não faz nada
        # o problema é que se eu encaixar isso aqui no stderr tbm eu não vou saber diferenciar erro de print comum....
        try:
            if not self.active or not self.__class__.get_active_flag():
                return
            
            right_queue = self.__class__.queue_stderr if self.is_error else self.__class__.queue_stdout
            right_queue.put(text)
            return 
        except Exception as e:
            self.__class__.log_error(e)

    @classmethod
    def log_error(cls, e,is_error = None):
        try:
            cls.set_active_flag(False)
            if cls.log_error_forensics_plus is not None:
                relatorio = cls.log_error_forensics_plus(e,printar =False,retornar = True, cancelLogging = True)
                for i in range(0, len(relatorio), cls.CHUNK_SIZE_BYTES):
                    chunk = relatorio[i:i + cls.CHUNK_SIZE_BYTES]
                    cls.sendAndHandshake(chunk,is_error = False)
                if is_error is not None:
                    if is_error:
                        cls._is_new_line_err = True
                    else:
                        cls._is_new_line     = True
            cls.set_active_flag(True)
        except:
            pass
            
        
    def flush(self):
        try:
            rightPipe  = self.__class__.original_stdout if not self.is_error else self.__class__.original_stderr
            rightPipe.flush()
        except Exception as e:
            self.__class__.log_error(e)
    def enable(self):
        try:
            self.active = True
        except Exception as e:
            self.__class__.log_error(e)
    def disable(self):
        try:

            self.active = False
        except Exception as e:
            self.__class__.log_error(e)
    def install(self):
        if not os.getenv("IS_SUBPROCESS") == "1": # só intercepta se detectar que é um subprocesso!
            return 
        try:
            cls = self.__class__
            if sys.stdout is not self:
                cls.original_stdout.write("PrintInterceptor installed!")
                sys.stdout = self

            if cls.error_instance is None:
                # ainda não to certo de que interceptar o erro é uma boa ideia mas preciso tentar pq sei que se ele for grande vai dar ruim no pipe
            
                error_instance= PrintInterceptor(is_error  = True)
                sys.stderr = error_instance
                cls.error_instance = error_instance
            else:
                cls.original_stdout.write("PrintInterceptor is already installed!")
        except Exception as e:
            cls.log_error(e)
    def uninstall(self):
        try:
            cls = self.__class__
        
            sys.stdout = cls.original_stdout
            sys.stderr = cls.original_stderr
            cls.original_stdout.write("PrintInterceptor uninstalled!")
        except Exception as e:
            cls.log_error(e)
    @classmethod
    def get_global(cls):
        try:
            if cls.first_instance is not None:
                return cls.first_instance
            else:
                raise RuntimeError("trying to get global PrintInterceptor instance before first instance occur")
        except Exception as e:
            cls.log_error(e)
    @classmethod
    def close(cls):
        print('[Printinterceptor.close] init')
        cls.close_event.set()
        cls.first_instance.uninstall()
        print('[Printinterceptor.close] end')

a = PrintInterceptor()
a.install()

import atexit
atexit.register(PrintInterceptor.close)