# error_handler.py
import traceback
import sys
from sharedResources.pythonLoggerSistem.logger import logger
import logging
from pprint import pformat

def get_error_frame(tb):
    while tb:
        frame = tb.tb_frame
        tb = tb.tb_next
    return frame  # Último frame da stack, onde o erro ocorreu


def collect_debug_info(custom_message=None):
    exc_type, exc_value, exc_tb = sys.exc_info()
    if not exc_type:
        return "❗ Nenhuma exceção ativa foi detectada."
    
    tb = traceback.extract_tb(exc_tb)
    stack_summary = traceback.format_exception(exc_type, exc_value, exc_tb)

    # Última chamada da stack
    last_frame = tb[-1] if tb else None

    # Informações do contexto
    file_name = last_frame.filename if last_frame else "<unknown>"
    line_no = last_frame.lineno if last_frame else -1
    function_name = last_frame.name if last_frame else "<unknown>"

    # Variáveis locais do frame onde ocorreu a exceção
    frame = get_error_frame(exc_tb)
    local_vars = frame.f_locals if frame else {}
    # while frame:
    #     if frame.f_code.co_filename == file_name and frame.f_lineno == line_no:
    #         local_vars = frame.f_locals
    #         break
    #     frame = frame.f_back
    # else:
    #     local_vars = {}

    formatted_vars = pformat(local_vars, indent=4, width=80)

    return (
        f"\n❗ {custom_message or 'Erro capturado'}\n"
        f"→ Tipo do erro: {exc_type.__name__}\n"
        f"→ Mensagem: {exc_value}\n"
        f"→ Arquivo: {file_name}\n"
        f"→ Linha: {line_no}\n"
        f"→ Função: {function_name}\n"
        f"→ Variáveis locais:\n{formatted_vars}\n"
        f"→ Stack completa:\n{''.join(stack_summary)}"
    )



class loggingClass:
    def __init__(self, fileName= "app.log", level=logging.INFO):
        self.logger = logger
        self.fileName = fileName
        self.level = level
        self.logger.setLevel(level)


    def log_exception(self,msg=None,level= None):
        if level is None:
            level=self.level
        

        context_msg = collect_debug_info(custom_message=msg)

        if level == logging.ERROR:
            logger.error(context_msg)

        elif level == logging.WARNING:
            logger.warning(context_msg)
        
        elif level == logging.INFO:
            logger.info(context_msg)
        
        elif level == logging.DEBUG:
            logger.debug(context_msg)
        
        elif level == logging.CRITICAL:
            logger.critical(context_msg)
        
        else:
            logger.error(f"Unknown logging level {level} for message: {context_msg}")
        