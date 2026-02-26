import logging
import sys
import queue
import atexit
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler, QueueHandler, QueueListener
from sharedResources.debuggingResources.unified_monitor import monitor_class
# Tenta usar rich para console se disponível, senão fallback para padrão
try:
    from rich.logging import RichHandler
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

BASE_DIR = Path(__file__).resolve().parent

@monitor_class
class LoggerManager:
    """
    Gerenciador central de logs assíncronos (Non-blocking I/O).
    Usa QueueHandler + QueueListener para não travar a thread principal escrevendo em disco.
    """
    
    # Fila Thread-Safe (Infinite size)
    _log_queue = queue.Queue(-1)
    
    _listener: QueueListener = None
    _is_listener_running = False
    
    # Configurações Padrão
    _logs_path = BASE_DIR / "logs"
    _general_level = logging.INFO
    _general_filename = "default.log"
    
    # Cache para evitar recriação de objetos
    _active_file_handlers = {}  # { 'caminho/completo/log': HandlerObj }
    _console_handler = None
    
    @classmethod
    def setup(cls, logs_path=None, level=logging.INFO, filename="default.log"):
        """Configuração inicial opcional."""
        if logs_path: 
            cls.set_logs_path(logs_path)
        cls.set_general_level(level)
        cls.set_general_filename(filename)

    @classmethod
    def set_logs_path(cls, path):
        if path:
            cls._logs_path = Path(path)
            cls._logs_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def set_general_level(cls, level):
        cls._general_level = level

    @classmethod
    def set_general_filename(cls, filename):
        cls._general_filename = filename

    @classmethod
    def _get_console_handler(cls):
        """Retorna o handler de console (Singleton), com Rich se possível."""
        if cls._console_handler is None:
            if HAS_RICH:
                # RichHandler já formata bonito, não precisa de setFormatter complexo
                cls._console_handler = RichHandler(
                    rich_tracebacks=True, 
                    markup=True,
                    show_time=True,
                    omit_repeated_times=False
                )
            else:
                cls._console_handler = logging.StreamHandler(sys.stdout)
                formatter = logging.Formatter(
                    "[%(levelname)s] %(asctime)s | %(module)s:%(lineno)d | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                cls._console_handler.setFormatter(formatter)
            
            cls._console_handler.setLevel(cls._general_level)
        
        return cls._console_handler

    @classmethod
    def _update_listener(cls):
        """
        Reinicia o Listener se houver novos handlers.
        Isso é crucial para garantir que novos arquivos de log sejam reconhecidos
        mesmo se o sistema já estiver rodando.
        """
        # Coleta todos os handlers ativos (Console + Todos os Arquivos)
        all_handlers = [cls._get_console_handler()] + list(cls._active_file_handlers.values())
        
        # Se já existe listener, paramos ele antes de recriar
        if cls._listener:
            cls._listener.stop()
        
        # Cria um novo listener com a lista atualizada de handlers
        cls._listener = QueueListener(cls._log_queue, *all_handlers, respect_handler_level=True)
        cls._listener.start()
        cls._is_listener_running = True

    @classmethod
    def get_logger(cls, name="default", filename=None, level=None):
        """
        Cria ou recupera um logger.
        Automaticamente gerencia os handlers de arquivo e reinicia o listener se necessário.
        """
        # 1. Garante diretório
        if not cls._logs_path.exists():
            cls._logs_path.mkdir(parents=True, exist_ok=True)

        # 2. Configura Níveis e Nomes
        target_level = level if level is not None else cls._general_level
        target_filename = filename if filename else cls._general_filename
        file_path = cls._logs_path / target_filename
        
        # 3. Gerencia o Handler de Arquivo (Singleton por caminho)
        str_path = str(file_path.absolute())
        handler_was_created = False
        
        if str_path not in cls._active_file_handlers:
            # Cria handler de rotação diária
            file_handler = TimedRotatingFileHandler(
                str_path, when="midnight", interval=1, backupCount=7, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG) # O handler aceita tudo, o logger filtra
            
            # Formatter para arquivo (sempre detalhado)
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(threadName)s] %(module)s:%(lineno)d - %(message)s"
            )
            file_handler.setFormatter(formatter)
            
            cls._active_file_handlers[str_path] = file_handler
            handler_was_created = True

        # 4. Configura o Logger do Python
        logger = logging.getLogger(name)
        logger.setLevel(target_level)
        
        # Limpa handlers antigos do logger para evitar duplicação ou handlers síncronos velhos
        if logger.hasHandlers():
            logger.handlers.clear()
        
        # O logger SÓ tem o QueueHandler. Ele joga pra fila, e a fila joga pros arquivos.
        # Isso garante que a thread principal nunca toque no disco.
        logger.addHandler(QueueHandler(cls._log_queue))
        
        # Não propaga para o root logger para evitar duplicatas no console
        logger.propagate = False

        # 5. Se criamos um arquivo novo, precisamos avisar o Listener
        if handler_was_created or not cls._is_listener_running:
            cls._update_listener()

        return logger
    
    @classmethod
    def stop_listener(cls):
        """
        Encerramento gracioso. Processa o restante da fila e fecha arquivos.
        """
        if cls._listener:
            print("[LoggerManager] Parando listener e descarregando fila...")
            cls._listener.stop() # Isso bloqueia até a fila esvaziar
            cls._is_listener_running = False
            cls._listener = None
            
        # Fecha os handlers de arquivo para liberar lock do SO
        for path, handler in cls._active_file_handlers.items():
            try:
                handler.close()
            except Exception:
                pass
        cls._active_file_handlers.clear()
        print("[LoggerManager] Logs encerrados.")

    @staticmethod
    def log_exception_with_context(msg, exc):
        """Helper para logar exceções formatadas"""
        logger = LoggerManager.get_logger("error_tracker")
        logger.error(f"{msg} -> {str(exc)}", exc_info=True)

# Garante que o stop_listener rode ao fechar o Python (mesmo sem chamar explícito)
atexit.register(LoggerManager.stop_listener)

# ==========================================
# TESTE
# ==========================================
if __name__ == "__main__":
    # Teste 1: Logger padrão
    log1 = LoggerManager.get_logger("main", "app.log", logging.INFO)
    log1.info("Iniciando sistema...")
    
    # Teste 2: Logger secundário em OUTRO arquivo (O listener vai reiniciar para aceitar isso)
    log2 = LoggerManager.get_logger("database", "db.log", logging.DEBUG)
    log2.debug("Conectando ao banco...") # Isso vai pro db.log
    log1.warning("Aviso geral")         # Isso continua indo pro app.log
    
    # Teste 3: Exceção
    try:
        1 / 0
    except Exception as e:
        LoggerManager.log_exception_with_context("Erro fatal no teste", e)
    
    print("Fim do script. O atexit vai fechar o logger.")