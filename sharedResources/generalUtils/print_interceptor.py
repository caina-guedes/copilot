# from sharedResources.generalUtils.print_interceptor import PrintInterceptor
import sys
import inspect
import os
import threading

from sharedResources.debuggingResources.unified_monitor import monitor_class

def _get_real_function(func):
    """made to dig the wrappers to the real function"""

    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func

import inspect, os

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
    log_error_forensics_plus = None
    last_context = {"file":"",
                    "func": ""}
    def __init__(self, active=True):
        if self.__class__.log_error_forensics_plus is None:
            from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
            self.__class__.log_error_forencis_plus = log_error_forensics_plus
        self.original_stdout = sys.stdout
        self.lock = threading.Lock()
        self.active = active  # Controle de produção
        self._is_newline = True # Flag para controlar o prefixo

    def get_prefix(self):
        file,func,line = _get_caller_info()
        if file == self.__class__.last_context['file'] and func == self.__class__.last_context['func']:
            return ""
        self.__class__.last_context['file'] = file
        self.__class__.last_context['func'] = func

        prefix = f"(\033[94m{file}:{func}:{line}Core.__holder__) "
        return prefix
                    
    def write(self, text):
        # Se estiver desativado, não faz nada
        # self.original_stdout.write("[PrintInterceptor.write] write init!")
        if not self.active:
            return

        with self.lock:
            # Se o texto for apenas uma quebra de linha, printa direto
            if text == '\n':
                self.original_stdout.write(text)
                self._is_newline = True
                # self.original_stdout.write("[PrintInterceptor.write] self._is_newline set to True and the text is: ,",)
                return

            # Só adiciona o prefixo se for o início de uma nova linha
            else:
                try:
                    # filename, func, line = _get_caller_info()
                    
                    prefix = self.get_prefix()
                    # self.original_stdout.write("[PrintInterceptor.write] vou printar com prefixo!")
                    resposta = prefix + text
                    self.original_stdout.write(resposta)
                except  Exception as e:
                    self.log_error(e)
                    # self.__class__.log_error_forensics_plus(e)
                    raise
                    # pass
                self._is_newline = False


            # self.original_stdout.write(text)

    def log_error(self, e):
        if self.__class__.log_error_forensics_plus is not None:
            self.__class__.log_error_forensics_plus(e)
        
    def flush(self):
        self.original_stdout.flush()

    def enable(self):
        self.active = True

    def disable(self):
        self.active = False

    def install(self):
        self.original_stdout.write("PrintInterceptor installed!")
        sys.stdout = self

    def uninstall(self):
        self.original_stdout.write("PrintInterceptor uninstalled!")
        
        sys.stdout = self.original_stdout
    # def 

