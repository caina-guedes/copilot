
import builtins
import threading
import queue
import time
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
from sharedResources.lifecycle.shutdownThreadUtils import TrackedThread
import warnings



DEBUG = True
# Guarda referência ao print original
_original_print = builtins.print

# Fila de mensagens para prints
_print_queue = queue.Queue()
_print_cleanUp_event = threading.Event()
def _print_worker():
    while True:
        try:
            StopSign, args, kwargs = _print_queue.get(timeout=0.5)
        except queue.Empty:
            if _print_cleanUp_event.is_set():
                # print("stopping aprint because cleanup_event is set!")
                break
            else:
                continue
        if StopSign:
            break
        try:
            _original_print(*args, **{**kwargs, "flush": True})
        except Exception as e:
            _original_print(f"[aprint error] {e}")
            warnings.warn(str(e))
            if DEBUG:
                raise e
        finally:
            _print_queue.task_done()

# Thread dedicada que consome a fila
_thread = TrackedThread(
    target = _print_worker, 
    cleanup_event =  _print_cleanUp_event , 
    daemon = True ,
    name  = "AprintThread", 
    created_from = "aprint.py module"
    )
# _thread = threading.Thread(target=_print_worker, daemon=True, name="AprintThread")
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
    _print_queue.join(timeout = 5)
    _thread.join(timeout = 5)
