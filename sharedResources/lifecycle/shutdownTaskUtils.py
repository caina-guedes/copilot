import asyncio

import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.trackedItem import TrackedItem

class Tracked_task:
    register_log = None
    default_cleanup_event = None
    tasksMap = None
    running_loop = None

    @classmethod
    def set_running_loop(cls,loop):
        if cls.running_loop is None:
            # print("setting loop in tracked task and it is: ", loop )
            cls.running_loop = loop
        else:
            print("[Tracked_task] running_loop already set!")
        
    @classmethod
    def set_register_log(cls,register):
        if cls.register_log is None:
            cls.register_log = register
        else:
            print("[tracked_task] register_log already set!")

    @classmethod
    def set_default_cleanup_event(cls,cleanup_event):
        if cls.default_cleanup_event is None:
            cls.default_cleanup_event  = cleanup_event
        else:
            print("[Tracked_task] default_cleanup_event already set!")
    
    @classmethod
    def set_tasksMap(cls,map):
        if cls.tasksMap is None:
            cls.tasksMap = map
        else:
            print("[Tracked_task] tasks_map already set!")
    
    # -------------------- Async Task wrapper --------------------
    @classmethod
    def create(cls,coro, name, created_from, cleanup_event = None,cleanup_function = None):
        """
        Cria uma async task com logging
        
        created_from é um campo pra que eu consiga humanamente entender onde ela foi criada por exemplo:
        "EventBuffer.start" 
        ou algo parecido.
        vai ser uma string capaz de me fazer entender o contexto e onde localizar no codigo
        """
        task_name = name or str(asyncio.current_task())
        
        async def wrapper():
            cls.register_log(f"[Async Task Started] {task_name}","tasks")
            # logger.info(f"[Async Task Started] {task_name}")
            try:
                return await coro
            except asyncio.CancelledError:
                cls.register_log(f"[Async Task Cancelled] {task_name}","tasks")
                # logger.info(f"[Async Task Cancelled] {task_name}")
                raise
            finally:
                cls.register_log(f"[Async Task Exited] {task_name}","tasks")
                # logger.info(f"[Async Task Exited] {task_name}")
        ######### criando elementos do trackedItem #########
        task = asyncio.create_task(wrapper(),name = task_name) # cria a task async
        selfCleanUpEvent    = cleanup_event or Tracked_task.default_cleanup_event   # pensado para fazer operações internas de limpeza
        selfCleanUpEventUse = False                      # flag para  a task usar o evento de self cleanup
        ######### creating the tracked item #########
        currentTaskItem     = TrackedItem(
            task,
            selfCleanUpEvent, 
            selfCleanUpEventUse,
            name = name, 
            kind = "task",
            created_from = created_from,
            cleanup_function = None)
        ######################## setando a task no mapa de tasks ########################
        if name:
            cls.tasksMap.setdefault(task_name, []).append(currentTaskItem) # cria a lista se não existir e seta a task
        else:
            cls.tasksMap["unnamedTasks"].append(currentTaskItem)
        
        cls.register_log(f"[Async Task Created] {task_name}","tasks")
        # logger.info(f"[Async Task Created] {task_name}")
        
        
        return task

    @classmethod
    async def shutdown_tasks(cls):
        cls.register_log("[Shutdown] Cancelling all async tasks...","tasks")
        # logger.info("[Shutdown] Cancelling all async tasks...")
        
        all_tasks = []
        print("o tamanho de tasksMaps durante a shutdown_tasks é:" ,len(cls.tasksMap))
        for name, task_list in cls.tasksMap.items():
            for tracked in task_list: # para cada tarefa rastreada
                task_obj, clean_event, use_flag = tracked.obj, tracked.cleanup_event, tracked.cleanup_enabled
                if not task_obj.done():
                    cls.register_log(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}","tasks")
                    # logger.info(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}")
                    if cls.running_loop.get() is not None:
                        if cls.running_loop._loop_is_ok():
                            cls.running_loop.get().call_soon_threadsafe(task_obj.cancel)
                        else:
                            print("loop is not okay already!")
                    else:
                        cls.register_log("No running loop set in LifecycleMaster, cannot cancel task properly. the task was: "+ str(task_obj),"tasks")
                    all_tasks.append(task_obj)
        
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
        else:
            print("no tasks to wait finishing")
        # Limpa tasks concluídas
        for name in list(cls.tasksMap.keys()):
            cls.tasksMap[name] = [t for t in cls.tasksMap[name] if not t.obj.done()]
            if not cls.tasksMap[name] and name != "unnamedTasks":
                del cls.tasksMap[name]
        cls.register_log("[Shutdown] All async tasks cancelled.","tasks")
        if len(cls.tasksMap) > 1:
            cls.register_log("[Shutdown] Some async tasks could not be cancelled","tasks")
            for task_name in cls.tasksMap.keys():
                if task_name != "unnamedTasks":
                    print("the task is: ",task_name)
            
            # logger.info("[Shutdown] Some async tasks could not be cancelled")
            return False
        else:
            cls.register_log("[Shutdown] All async tasks handled.","tasks")
            # logger.info("[Shutdown] All async tasks handled.")
            return True
