import builtins
import threading
import queue
import time

DEBUG = True
# Guarda referência ao print original
_original_print = builtins.print

# Fila de mensagens para prints
_print_queue = queue.Queue()

def _print_worker():
    while True:
        StopSign, args, kwargs = _print_queue.get()
        if StopSign:
            break
        try:
            _original_print(*args, **{**kwargs, "flush": True})
        except Exception as e:
            _original_print(f"[aprint error] {e}")
            if DEBUG:
                raise e
        finally:
            _print_queue.task_done()

# Thread dedicada que consome a fila
_thread = threading.Thread(target=_print_worker, daemon=True, name="AprintThread")
_thread.start()

def aprint(*args, **kwargs):
    """
    Print não bloqueante, ordenado e thread-safe.
    """
    if DEBUG:
        _print_queue.put((False, args, {**kwargs}))

def stop_aprint():
    """
    Encerra a thread de prints (opcional, ao finalizar o programa).
    """
    _print_queue.put((True, None, None))
    _print_queue.join()
    _thread.join()
