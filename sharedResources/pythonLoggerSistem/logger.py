# logger_manager.py
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler, QueueHandler, QueueListener
from multiprocessing import Queue
import os
from pathlib import Path
import sys
import traceback
from rich.console import Console
from sharedResources.generalUtils.aprint import aprint

BASE_DIR = Path(__file__).resolve().parent

class LoggerManager:
    _log_queue = Queue()
    _listener = None
    _listener_started = False
    _logs_path = BASE_DIR / "logs"
    _general_level = logging.WARN
    _general_filename = "default.log"
    __dev_mode = True
    _file_handlers =[]
    _file_path_already_with_handlers = {}


    @classmethod
    def set_logs_path(cls, path = None):
        """
        Defines the path where logs will be stored.
        """
        cls._logs_path = path or cls._logs_path
        if not os.path.exists(cls._logs_path):
            wanted_path = Path(cls._logs_path)
            wanted_path.mkdir(parents=True, exist_ok=True)
            # os.makedirs(cls._logs_path,exist_ok=True)
    
    @classmethod
    def set_general_level(cls, level):
        """
        Defines general log level for all loggers.
        """
        cls._general_level = level
    
    @classmethod
    def set_general_filename(cls, filename):
        """
        Defines general log filename for all loggers.
        """
        cls._general_filename = filename
    
    @classmethod
    def _start_listener(cls, handlers):
        if not cls._listener_started:
            os.makedirs(cls._logs_path, exist_ok=True)
            cls._listener = QueueListener(cls._log_queue, *handlers)
            cls._listener.start()
            cls._listener_started = True


    @classmethod
    def get_logger(cls, name="default", filename=None,level=None):
        if not os.path.exists(cls._logs_path):
            cls.set_logs_path()

        logger = logging.getLogger(name)
        # print(f"logger:{logger} and the type is : {type(logger)}")
        if level is None:
            level = cls._general_level
            # print(f"the logger level is {level}")
        logger.setLevel(level)
        
        if filename is None:
            filename = cls._general_filename

        file_path = os.path.join(cls._logs_path, filename)
        if file_path not in cls._file_path_already_with_handlers:
            file_handler = TimedRotatingFileHandler(file_path, when="midnight", backupCount=7)
            file_handler.setLevel(level)
            cls._file_path_already_with_handlers[file_path] = file_handler
        else:
            file_handler = cls._file_path_already_with_handlers[file_path]

        formatter = logging.Formatter(
            "%(levelname)s  in %(module)s:%(lineno)d [%(processName)s/%(threadName)s] → %(message)s  [%(asctime)s]"
        )
        file_handler.setFormatter(formatter)


        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)

        # Adiciona handlers se ainda não foram adicionados
        if not any(isinstance(h, QueueHandler) for h in logger.handlers):
        # if not logger.hasHandlers():
            cls._start_listener([file_handler, console_handler])
            cls._file_handlers.append(file_handler)
            logger.addHandler(QueueHandler(cls._log_queue))

        # print(f"in the end the logger:{logger} and the type is : {type(logger)}")
        return logger
    
    @classmethod
    def stop_listener(cls):
        """
        Encerra o listener se ele estiver rodando.
        """
        print("o stop_listener do logger está sendo executado!!!")
        try:
            if cls._listener and cls._listener_started:
                cls._listener.stop()
                cls._listener_started = False
                cls._listener = None
            for handler in cls._file_handlers:
                handler.close()
            print("e foi executado inteiramente!")
        except Exception as e:
            print(f"[LoggerManager.stop_listener] deu erro e foi: {e}")
        

    @classmethod
    def log_exception_with_context(cls, msg="", exception=None, show_tasks=True):
        """
        Loga a exceção atual, mostrando a linha do erro e as variáveis locais.
        Se __dev_mode=True e exception fornecida, levanta a exceção.
        """
        console = Console()
        internalLogger = cls.get_logger()  # Garante que logger padrão exista

        try:
            # Tests if msg is an exception and assigns to exception if so
            if isinstance(msg, BaseException) and exception is None:
                exception = msg
                msg = ""

            exc_type, exc_value, tb = sys.exc_info()
            if tb is None and exception is not None:
                # Se não há exceção ativa, usa a fornecida
                if not isinstance(exception, BaseException):
                    exception = Exception(str(exception))  # transforma string em exceção

                exc_type = type(exception)
                exc_value = exception
                tb = exception.__traceback__

            if tb:
                last_frame = traceback.extract_tb(tb)[-1]
                frame = tb.tb_frame
                local_vars = frame.f_locals
            else:
                last_frame = None
                local_vars = {}

            internalLogger.error(f"Exception occurred: {exc_type.__name__ if exc_type else 'Unknown'} - {str(exc_value)}")
            if last_frame:
                internalLogger.error(f"File: {last_frame.filename}, Line: {last_frame.lineno}, Function: {last_frame.name}")
            internalLogger.error("Locals at error point:")
            MAX_LEN = 200
            for var, val in local_vars.items():
                try:
                    representation = (repr(val)[:MAX_LEN] + "...") if len(repr(val)) > MAX_LEN else repr(val)
                except Exception:
                    representation = "<unprintable>"
                internalLogger.error(f"    {var} = {representation}")

            trace = None

            if exception is not None:
                if not isinstance(exception, BaseException):
                    synthetic_exc = Exception(str(exception))
                    trace = traceback.TracebackException.from_exception(synthetic_exc)
                else:
                    trace = traceback.TracebackException.from_exception(exception)
                # HasException = True
            
            elif sys.exc_info()[0] is not None:
                # HasException = True
                trace = traceback.TracebackException.from_exception(exc_value)
            if trace:
                # for line in trace.format():
                #     internalLogger.error(line.strip())

                # Também exibe no console com rich
                try:
                    if exception:
                        raise Exception(exception)

                except Exception as e:
                    console.print_exception(show_locals=True, width=console.width, extra_lines=1)
                
 

            else:
                internalLogger.info("log_exception_with_context called without an active exception")

            if show_tasks:
                # Tasks asyncio ativas (opcional, só se houver loop)
                try:
                    for task in asyncio.all_tasks():
                        internalLogger.info(f"TASK {task.get_name()} - {task._coro}")
                except Exception:
                    pass

            if cls.__dev_mode:
                # Se __dev_mode e exception passada, levanta
                if exception:
                    raise Exception(exception)
                elif exc_value:
                    raise Exception(exc_value)

        except Exception as e:
            try:
                # Nunca quebrar o logger
                internalLogger.error(f"[LoggerManager] Error inside log_exception_with_context: {e}")
                trace  =  traceback.TracebackException.from_exception(e)
                if exception:
                    try:
                        raise exception
                    except Exception as e:
                        console.print_exception(show_locals=True, width=console.width, extra_lines=1)
                else:
                    print("no logger o exception foi: ",exception) 
                #     console.print_exception()
            except:
                pass


if "__name__" == "__main__":
    logger = LoggerManager.get_logger("test_logger", "test.log", logging.DEBUG)
    try:
        1 / 0
    except Exception as e:
        LoggerManager.log_exception_with_context("An error occurred in main", e)
