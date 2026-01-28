import asyncio
import threading
import concurrent.futures
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.trackedItem import TrackedItem

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


# def submit(cls, fn_or_coro, protected = False):
#     if not cls._can_interact():
#         return None
#     if asyncio.iscoroutinefunction(fn_or_coro):
#         coro = fn_or_coro()
#     else:
#         coro = fn_or_coro

#     if not asyncio.iscoroutine(coro):
#         cls._log(f"submit received non-coroutine, it is:{type(coro)} and it is:{coro}","loop")
        
#         return None

#     try:
#         if threading.current_thread() is cls._thread:
#             # estamos na thread do loop → cria a Task real
#             task = asyncio.create_task(coro)
#             setattr(task, "_protected", protected)
#             return task
#         else:
#             # estamos fora do loop → agendar a criação thread-safe
#             fut = concurrent.futures.Future()

#             def wrapper():
#                 try:
#                     task = asyncio.create_task(coro)
#                     setattr(task, "_protected", protected)
#                     fut.set_result(task)
#                 except Exception as e:
#                     fut.set_exception(e)

#             cls._current.call_soon_threadsafe(wrapper)
#             return fut  # esse fut é o Future que entrega a Task real
    
#     except Exception as e:
#         cls._log(f"submit failed: {e}","loop")
#         cls._log(f"the coro was: {coro}","loop")
#         cls._log(f"the current thread is: {threading.current_thread()} and loop thread id is: {cls._thread}","loop")
#         return None

def submit(cls, fn_or_coro, name=None, created_from=None, protected=False, cleanup_event=None, cleanup_function=None):
    """
    Submete uma coroutine ao loop, garantindo que ela vire uma TrackedTask.
    Se chamado fora da thread do loop, é agendado thread-safe.
    """
    if not cls._can_interact():
        return None

    # Transforma função em coroutine
    if asyncio.iscoroutinefunction(fn_or_coro):
        coro = fn_or_coro()
    else:
        coro = fn_or_coro

    if not asyncio.iscoroutine(coro):
        cls._log(f"submit received non-coroutine, it is: {type(coro)} and value: {coro}", "loop")
        return None

    # Função interna para criar a tracked task
    def _create_tracked_task():
        # Wrapper da task para logging e tracking
        task_name = name or str(asyncio.current_task())
        
        async def wrapper():
            cls.register_log(f"[TrackedTask Started] {task_name}", "tasks")
            try:
                return await coro
            except asyncio.CancelledError:
                cls.register_log(f"[TrackedTask Cancelled] {task_name}", "tasks")
                raise
            finally:
                cls.register_log(f"[TrackedTask Exited] {task_name}", "tasks")

        # Cria a task real dentro do loop
        task = asyncio.create_task(wrapper(), name=task_name)
        setattr(task, "_protected", protected)  # marca se é protegida
        # Cria o item de tracking
        tracked_item = TrackedItem(
            task,
            cleanup_event or Tracked_task.default_cleanup_event,
            False,
            name=task_name,
            kind="task",
            created_from=created_from,
            cleanup_function=cleanup_function
        )
        # Guarda no mapa de tasks
        if task_name:
            cls.tasksMap.setdefault(task_name, []).append(tracked_item)
        else:
            cls.tasksMap["unnamedTasks"].append(tracked_item)
        cls.register_log(f"[TrackedTask Created] {task_name}", "tasks")
        return task

    try:
        # Se estamos na thread do loop
        if threading.current_thread() is cls._thread:
            return _create_tracked_task()
        else:
            # Fora do loop → thread-safe
            fut = concurrent.futures.Future()

            def wrapper_threadsafe():
                try:
                    task = _create_tracked_task()
                    fut.set_result(task)
                except Exception as e:
                    fut.set_exception(e)

            cls._current.call_soon_threadsafe(wrapper_threadsafe)
            return fut
     except Exception as e:
        cls._log(f"submit failed: {e}","loop")
        cls._log(f"the coro was: {coro}","loop")
        cls._log(f"the current thread is: {threading.current_thread()} and loop thread id is: {cls._thread}","loop")
        return None



def gather(cls, *coros, return_exceptions=False):
    async def _inner():
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    return cls.submit(_inner())
