import threading
from pathlib import Path
import sys
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.loop.state import LoopState

def start_loop(cls):
    if cls.loop_is_none():
        cls._log("cannot start loop because it is not set yet","loop")
        return False
    if not cls.instance_check():
        cls._log("cannot start loop because it is not a proper loop","loop")
        return False
    if cls._state == LoopState.SET and not cls.is_running():
        def _run():
            try:
                cls._thread = threading.current_thread()
                cls.change_state(LoopState.RUNNING)
                cls._log("loop started in its own thread","loop")
                cls._current.run_forever()
                cls._log("loop stopped","loop")
            except Exception as e:
                cls._log(f"Exception in loop thread: {e}","loop")
            finally:
                cls.change_state(LoopState.CLOSED)


        t = threading.Thread(target=_run, name="AsyncioLoopThread", daemon=True)
        t.start()
        return True
    else:
        cls._log("loop is already running","loop")
        return False


def stop_loop(cls, graceful=True):
    if cls.loop_is_none() or not cls.is_running():
        cls._log("stop called but loop not running","loop")
        return

    def _stop():
        cls.change_state(LoopState.STOPPING)
        cls._log("stopping event loop","loop")
        cls._current.stop()

        cls.change_state(LoopState.CLOSED)

    cls.call_soon(_stop)  # sempre thread-safe
