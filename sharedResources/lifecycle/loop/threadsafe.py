import asyncio
import warnings
import threading
import concurrent.futures
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.trackedUtils.trackedItem import TrackedItem, TaskFinishRecord
from sharedResources.lifecycle.shutdownTaskUtils import TrackedTask
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
from sharedResources.lifecycle.stateManager import State
def call_soon(cls, fn, *args):

    if not cls._can_interact():
        return False

    try:
        # print("Current thread:", threading.current_thread())
        # print("Loop thread:", cls._thread)
        if threading.current_thread() is cls._thread:
            # print("Calling call_soon directly")
            cls._current.call_soon(fn, *args)
        else:
            # print("Calling call_soon_threadsafe")
            cls._current.call_soon_threadsafe(fn, *args)
        return True
    except Exception as e:
        cls._log(f"call_soon failed: {e}","loop")
        log_error_forensics_plus(e)
        return False



def submit(
    cls,
    fn_or_coro,
    *,
    name: str | None = None,
    created_from: str = "unknown",
    protected: bool   = False,
    cleanup_event     = None,
    cleanup_function        = None,
    state = None
):
    if not cls._can_interact():
        return None

    # normaliza para coroutine
    if asyncio.iscoroutinefunction(fn_or_coro):
        coro = fn_or_coro()
    else:
        coro = fn_or_coro

    if not asyncio.iscoroutine(coro):
        cls._log(
            f"submit received non-coroutine: {type(coro)} -> {coro} , 'state' : {state}",
            "loop"
        )
        # print()
        if state in (State.INIT, State.SHUTTING_DOWN):
            return None # coloquei isso aqui pq durante  o shutdown estou tentando usar funções que ja foram fechadas, é mais pra se eu fizer alguma merda e isso mudar ai avisar
        
        else:
            1/0 # aqui eu injeto um erro de propósito pro meu sistema de monitoramento me mostrar o traceback caso isso ocorra

    try:
        # ===========================
        # CASO 1: já estamos no loop
        # ===========================
        if threading.current_thread() is cls._thread:
            # print("estamos na mesma thread, tentando retornar o o asyncio.create_task")
            task = asyncio.create_task(coro, name=name)
            setattr(task, "protected", protected)
            task.add_done_callback(cls.tasksMap._on_task_finish)
            cls._log(f"creating task in loop thread: {task}", "loop")
            cls.tasksMap.register_task(
                task=task,
                name=name,
                created_from=created_from,
                protected=protected,
                cleanup_function = cleanup_function,
                cleanup_event = cleanup_event,
            )
            # cls._log(f"task registered: {name}", "loop")

            return task

        # ==================================
        # CASO 2: estamos fora da thread
        # ==================================
        fut = concurrent.futures.Future()

        def _create_task_in_loop():
            try:
                task = asyncio.create_task(coro, name=name)
                task.add_done_callback(cls.tasksMap._on_task_finish)
                setattr(task, "protected", protected)
                cls._log(f"creating task in loop thread: {task}", "loop")
                cls.tasksMap.register_task(
                    task          =  task,
                    name          =  name,
                    created_from  =  created_from,
                    protected     =  protected,
                    cleanup_function = cleanup_function,
                    cleanup_event = cleanup_event,
                )
                # cls._log(f"task registered: {task}", "loop")
                fut.set_result(task)

            except Exception as e:
                cls._log("o erro dentro da _create_Task_in_loop foi: ",e)
                fut.set_exception(e)
                log_error_forensics_plus(e)
                # raise e

        cls._current.call_soon_threadsafe(_create_task_in_loop)
        return fut

    except Exception as e:
        cls._log(f"submit failed: {e}", "loop")
        cls._log(f"coro was: {coro}", "loop")
        cls._log(
            f"current thread: {threading.current_thread()} | loop thread: {cls._thread}",
            "loop",
        )
        log_error_forensics_plus(e)
        return None

def gather(cls, *coros, return_exceptions=False):
    async def _inner():
        return await asyncio.gather(*coros, return_exceptions=return_exceptions)
    return cls.submit(_inner())






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
#             setattr(task, "protected", protected)
#             return task
#         else:
#             # estamos fora do loop → agendar a criação thread-safe
#             fut = concurrent.futures.Future()

#             def wrapper():
#                 try:
#                     task = asyncio.create_task(coro)
#                     setattr(task, "protected", protected)
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

# def submit(
#     cls, 
#     fn_or_coro, 
#     name=None, 
#     created_from=None, 
#     protected=False, 
#     cleanup_event=None, 
#     cleanup_function=None):
#     """
#     Submete uma coroutine ao loop, garantindo que ela vire uma TrackedTask.
#     Se chamado fora da thread do loop, é agendado thread-safe.
#     """
#     if not cls._can_interact():
#         return None

#     # Transforma função em coroutine
#     if asyncio.iscoroutinefunction(fn_or_coro):
#         coro = fn_or_coro()
#     else:
#         coro = fn_or_coro

#     if not asyncio.iscoroutine(coro):
#         cls._log(f"submit received non-coroutine, it is: {type(coro)} and value: {coro}", "loop")
#         return None

#     # Função interna para criar a tracked task
#     def _create_TrackedTask():
#         # Wrapper da task para logging e tracking
#         try:
#             task_name = name or str(asyncio.current_task())
#             cls._log(f"entrei na _create_TrackedTask e o nome da task é: {task_name}","tasks")
#             async def wrapper():

#                 cls._log(f"[TrackedTask Started] {task_name}", "tasks")
#                 try:
#                     return await coro
#                 except asyncio.CancelledError:
#                     cls._log(f"[TrackedTask Cancelled] {task_name}", "tasks")
#                     raise
#                 finally:
#                     cls._log(f"[TrackedTask Exited] {task_name}", "tasks")

#             # Cria a task real dentro do loop
#             task = asyncio.create_task(wrapper(), name=task_name)
#             setattr(task, "protected", protected)  # marca se é protegida
#             # Cria o item de tracking
#             tracked_item = TrackedItem(
#                 task,
#                 cleanup_event or cls.default_shutdown_event,
#                 False,
#                 name              =  task_name,
#                 kind              =  "task",
#                 created_from      =  created_from,
#                 cleanup_function  =  cleanup_function
#             )
#             # Guarda no mapa de tasks
#             if task_name:
#                 cls.tasksMap.setdefault(task_name, []).append(tracked_item)
#             else:
#                 cls.tasksMap["unnamedTasks"].append(tracked_item)
            
#             cls._log(f"[TrackedTask Created] {task_name}", "tasks")
#             cls._log(f"the task to be returned is: {task}")
#             return task
#         except Exception as e:
#             cls._log(f"deu erro na _create_TrackedTask e é: {e}","tasks")
    
#     try:
#         # Se estamos na thread do loop
#         if threading.current_thread() is cls._thread:
#             print("estamos na mesma thread, tentando retornar o o asyncio.create_task")
#             result  = asyncio.create_task(_create_TrackedTask())
#             print("o resultado é: ",result) 
#             return result
#         else:
#             # Fora do loop → thread-safe
#             print("estamos em thread diferente!")
#             fut = concurrent.futures.Future()

#             def wrapper_threadsafe():
#                 try:
#                     cls._log("estou no wrepper do threadsafe em tread diferente","tasks")
#                     task = _create_TrackedTask()
#                     cls._log(f"a task é: {task}","tasks")
#                     fut.set_result(task)
#                 except Exception as e:
#                     fut.set_exception(e)

#             cls._current.call_soon_threadsafe(wrapper_threadsafe)
#             cls._log(f"o future que eu vou retornar é: {fut}","tasks")
#             return fut
#     except Exception as e:
#         cls._log(f"submit failed: {e}","loop")
#         cls._log(f"the coro was: {coro}","loop")
#         cls._log(f"the current thread is: {threading.current_thread()} and loop thread id is: {cls._thread}","loop")
#         return None

# def _on_task_finish(task:asyncio.Task):
#     # get trackedItem on live map
#     tracked = tasksMap.get_alive_tracked_from_task(task)

# def _remove_from_alive_map( task: asyncio.Task):
#     task_name = task.get_name()
#     items = TrackedTask.tasksMap.get(task_name, [])
#     items = [item for item in items if item.obj is not task]
#     if items:
#         TrackedTask.tasksMap[task_name] = items
#     else:
#         TrackedTask.tasksMap.pop(task_name, None)
#     TrackedTask.register_log(f"Task {task_name} removed from tasksMap", "tasks")

# task.add_done_callback(_remove_from_map)

