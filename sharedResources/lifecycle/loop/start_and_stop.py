import threading
import asyncio
import warnings
from pathlib import Path
import sys
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.loop.state import LoopState
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus

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
            log_error_forensics_plus(e)
        finally:
            cls._current.close()
            cls._stop_loop_event.set()
            cls.change_state(LoopState.CLOSED)


    t = threading.Thread(target=_run, name="AsyncioLoopThread", daemon=False)
    t.start()
    if not loop_ready.wait(timeout=5):  # wait until the loop is ready
        cls._log("loop failed to start within timeout","loop")
        return False
    return True

async def _cancel_all_tasks(cls, timeout = 5):
    current_task = asyncio.current_task()
    # tasks = [t for t in asyncio.all_tasks(loop=cls._current) if t is not current_task and t]
    tasks = []
    for t in asyncio.all_tasks(loop=cls._current):
        if t is current_task:
            # print("not using this task because is it the  current task")
            continue
        if getattr(t, "protected", False):# não pega tasks protegidas!
            cls._log(f" this task is protected so I wont cancell it : {t}","loop")
            continue
        tasks.append(t)
    if not tasks:
        return
    cls._log(f"Cancelling {len(tasks)} tasks","loop")
    cls._log(f"the current_task is: {current_task}","loop")
    try:
        for t in tasks:
            cls._log(f"canceling task {t}","loop")
        for t in tasks:
            t.cancel()
        # Espera com timeout
        done, pending = await asyncio.wait(tasks, timeout=timeout)

        # Tasks que finalizaram
        for t in done:
            if t.cancelled():
                cls._log(f"task cancelled successfully: {t}", "loop")
            elif t.exception():
                cls._log(f"task finished with exception: {t.exception()}", "loop")
            else:
                cls._log(f"task finished normally: {t}", "loop")

        # Tasks que NÃO finalizaram
        if pending:
            cls._log(f"{len(pending)} task(s) did not cancel within {timeout}s", "loop" )
            for t in pending:
                cls._log(f"PENDING task -> {t}, state={t._state}, coro={t.get_coro()}","loop")

        cls._log("[_cancel_all_tasks] function end")

    except Exception as e:
        cls._log(f"[_cancel_all_tasks] error is:  {e}")
        log_error_forensics_plus(e)



def stop_loop(cls, graceful=True):
    cls._log("stop_loop function called!!!!!","loop")
    try:
        if cls.loop_is_none() or not cls.is_running():
            cls._log("stop loop called but loop not running","loop")
            return
        loop_stopped = threading.Event()
        async def _stop():
            cls.change_state(LoopState.STOPPING)
            cls._log("stopping event loop","loop")
            
            if graceful:
                await _cancel_all_tasks(cls)
            
            cls._current.stop()
            cls._log("loop really stopped!!!")
            # cls._current.close()
            cls.change_state(LoopState.CLOSED)
            loop_stopped.set()
        
        future = cls.submit(_stop(),name="stop",protected = True)
        try:
            future.result(timeout=5)
            return True
        except TimeoutError:
            cls._log("[stop_loop] loop failed to stop within timeout","loop")
            return False
        

        # if not loop_stopped.wait(timeout=5):
    except Exception as e:
        cls._log(f"[stop_loop] deu exceção  e foi: {e}","loop")
        log_error_forensics_plus(e)

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

