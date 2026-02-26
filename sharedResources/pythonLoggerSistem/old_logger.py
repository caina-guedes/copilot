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
# from sharedResources.generalUtils.aprint import aprint

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
        

    

if "__name__" == "__main__":
    logger = LoggerManager.get_logger("test_logger", "test.log", logging.DEBUG)
    try:
        1 / 0
    except Exception as e:
        LoggerManager.log_exception_with_context("An error occurred in main", e)
