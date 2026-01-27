import threading
import asyncio

from pathlib import Path
import sys
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.loop.state import LoopState

def start_loop(cls):

    if cls._state not in (LoopState.EMPTY, LoopState.CLOSED):
        cls._log("loop already started or starting")
        return False
    loop_ready  = threading.Event()
    def _run():
        try:

            cls._thread = threading.current_thread()
            cls._current = asyncio.new_event_loop()
            asyncio.set_event_loop(cls._current)
            cls.change_state(LoopState.RUNNING)
            cls._log("loop started in its own thread","loop")

            cls._stop_loop_event.clear()
            loop_ready.set()
            cls._current.run_forever()
            cls._log("loop stopped","loop")
        except Exception as e:
            cls._log(f"Exception in loop thread: {e}","loop")
        finally:
            cls._stop_loop_event.set()
            cls.change_state(LoopState.CLOSED)


    t = threading.Thread(target=_run, name="AsyncioLoopThread", daemon=True)
    t.start()
    if not loop_ready.wait(timeout=5):  # wait until the loop is ready
        cls._log("loop failed to start within timeout","loop")
        return False
    return True

async def _cancel_all_tasks():
    tasks = [t for t in asyncio.all_tasks(loop=cls._current) if t is not asyncio.current_task()]
    if not tasks:
        return
    cls._log(f"Cancelling {len(tasks)} tasks","loop")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)



def stop_loop(cls, graceful=True):
    if cls.loop_is_none() or not cls.is_running():
        cls._log("stop loop called but loop not running","loop")
        return
    loop_stopped = threading.Event()
    async def _stop():
        cls.change_state(LoopState.STOPPING)
        cls._log("stopping event loop","loop")
        
        if graceful:
            await _cancel_all_tasks()
        
        cls._current.stop()

        cls.change_state(LoopState.CLOSED)
        loop_stopped.set()

    # cls.call_soon(_stop)  # sempre thread-safe
    cls.call_soon_threadsafe(lambda: asyncio.create_task(_stop())) #sempre thread-safe

    if not loop_stopped.wait(timeout=5):
        cls._log("loop failed to stop within timeout","loop")
        return False
    return True

def kill_loop(cls):
    if cls.loop_is_none():
        cls._log("kill loop called but loop is None","loop")
        return

    cls._stop_loop_event.clear()
    stopped = cls.stop_loop(graceful=True)
    if not stopped:
        cls._log("loop did not stop gracefully so i wont kill it","loop")
        return

    if cls._thread is not None:
        cls._thread.join(timeout=2)
    if cls._stop_loop_event.wait(timeout=10):
        cls._log("loop thread has exited","loop")
        cls._current = None
        cls._thread = None
        cls.change_state(LoopState.EMPTY)
    else:
        cls._log("loop thread did not exit within timeout","loop")
