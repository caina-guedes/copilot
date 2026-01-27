import asyncio
import threading

def call_soon(cls, fn, *args):

    if not cls._can_interact():
        return False

    try:
        print("Current thread:", threading.current_thread())
        print("Loop thread:", cls._thread)
        if threading.current_thread() is cls._thread:
            print("Calling call_soon directly")
            cls._current.call_soon(fn, *args)
        else:
            print("Calling call_soon_threadsafe")
            cls._current.call_soon_threadsafe(fn, *args)
        return True
    except Exception as e:
        cls._log(f"call_soon failed: {e}","loop")
        return False


def submit(cls, fn_or_coro):
    if not cls._can_interact():
        return None
    if asyncio.iscoroutinefunction(fn_or_coro):
        coro = fn_or_coro()
    if not asyncio.iscoroutine(coro):
        cls._log("submit received non-coroutine","loop")
        return None

    try:
        return asyncio.run_coroutine_threadsafe(coro, cls._current)
    except Exception as e:
        cls._log(f"submit failed: {e}","loop")
        cls._log(f"the coro was: {coro}","loop")
        cls._log(f"the current thread is: {threading.current_thread()} and loop thread id is: {cls._thread}","loop")
        return None


def gather(cls, *coros, return_exceptions=False):
    async def _inner():
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    return cls.submit(_inner())
