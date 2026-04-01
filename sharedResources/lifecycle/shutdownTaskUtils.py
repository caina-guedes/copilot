import asyncio
import warnings
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

# from sharedResources.lifecycle.trackedUtils.trackedItem import TrackedItem
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus

class TrackedTask:
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
            print("[TrackedTask] running_loop already set!")


    @classmethod
    def set_register_log(cls,register):
        if cls.register_log is None:
            cls.register_log = register
        else:
            print("[TrackedTask] register_log already set!")


    @classmethod
    def set_default_cleanup_event(cls,cleanup_event):
        if cls.default_cleanup_event is None:
            cls.default_cleanup_event  = cleanup_event
        else:
            print("[TrackedTask] default_cleanup_event already set!")
    

    @classmethod
    def set_tasksMap(cls,map):
        if cls.tasksMap is None:
            cls.tasksMap = map
        else:
            print("[TrackedTask] tasks_map already set!")
    

    @classmethod
    async def shutdown_tasks(cls):
        try:
            print("[shutdown_tasks] init")
            cls.register_log("[Shutdown] Cancelling all async tasks...","tasks")
            # logger.info("[Shutdown] Cancelling all async tasks...")
            
            all_tasks = []
            # print("o tamanho de tasksMaps durante a shutdown_tasks é:" ,len(cls.tasksMap.get_alive()))
            for name, task_list in cls.tasksMap.get_alive().items():
                print(f"o nome é:{name}")
                # print(f"a task_list é: {task_list}")
                for tracked in task_list: # para cada tarefa rastreada
                    # print("entrei no for nessa tasklist")

                    task_obj, clean_event, use_flag = tracked.obj, tracked.cleanup_event, tracked.cleanup_enabled
                    # print("peguei os atributos")
                    if task_obj.protected:
                        print(f"protegida: {task_obj.protected}")
                        print(f"não vou cancelar essa")
                        continue
                    if task_obj is asyncio.current_task:
                        print("essa é a task atual, não vou cancelar")
                        continue

                    if not task_obj.done():
                        # logger.info(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}")
                        if cls.running_loop.get() is not None:
                            if cls.running_loop._loop_is_ok():
                                cls.register_log(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}","tasks")
                                # print("chamando o cancel via thread safe")
                                cls.running_loop.get().call_soon_threadsafe(task_obj.cancel)
                            else:
                                cls.register_log("loop is not okay already!","tasks")
                        else:
                            cls.register_log("No running loop set in LifecycleMaster, cannot cancel task properly. the task was: "+ str(task_obj),"tasks")
                        all_tasks.append(task_obj)
                    else:
                        cls.register_log(f"task already done! {task_obj}")
            
            if all_tasks:
                await asyncio.gather(*all_tasks, return_exceptions=True)
            else:
                print("no tasks to wait finishing")
            # Limpa tasks concluídas
            ###### tenho que refazer essa parte toda respeitando  a manipulação interna da classe TasksMap
            for name in list(cls.tasksMap.get_alive().keys()):
                cls.tasksMap.get_alive()[name] = [t for t in cls.tasksMap.get_alive()[name] if not t.obj.done()]
                if not cls.tasksMap.get_alive()[name] and name != "unnamedTasks":
                    del cls.tasksMap.get_alive()[name]
            cls.register_log("[Shutdown] All async tasks cancelled.","tasks")
            if len(cls.tasksMap.get_alive()) > 1:
                cls.register_log("[Shutdown] Some async tasks could not be cancelled","tasks")
                for task_name in cls.tasksMap.get_alive().keys():
                    if task_name != "unnamedTasks":
                        print("the task is: ",task_name)
                
                # logger.info("[Shutdown] Some async tasks could not be cancelled")
                return False
            else:
                cls.register_log("[Shutdown] All async tasks handled.","tasks")
                # logger.info("[Shutdown] All async tasks handled.")
                return True
        except Exception as e:
            cls.register_log(f"[shutdown_tasks] deu erro e foi: {e}")
            log_error_forensics_plus(e)


    