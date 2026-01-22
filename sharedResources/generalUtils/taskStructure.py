from typing import Literal, Optional, Callable, Any 
import time
from dataclasses import dataclass, field
import threading
import asyncio
import logging
from dataclasses import dataclass
# sharedResources/generalUtils
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

# from sharedResources.generalUtils.taskStrutureTests.tests import test_tracked_task

@dataclass
class TrackedItem:
    obj: object
    cleanup_event: object
    cleanup_enabled: bool
    name: str | None 
    kind: Literal["thread", "task"]
    created_from: str | None
    cleanup_function: Optional[Callable[..., Any]] = None
    created_at: float = field(default_factory=time.time)
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)

# Setup básico de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("LifecycleTracker")




class shutdownMaster():
    """
    mapa para rastrear as threads e tasks com nomes iguais ou não"""
    shutdown_event = threading.Event() #tem que setar esse evento em runtime pelo processo principal
    shutDownComplete = threading.Event()
    byebye           = threading.Event()
    shutdown_lock = threading.Lock()
    shutDownExternalLock = threading.Lock() # para o uso externo acontecer apenas uma vez
    running_loop = None
    threadsMap = {}
    tasksMap = {"unnamedTasks":[]}
    logsMap = {"threads":[],"tasks":[]}

    @classmethod
    def set_loop(cls, loop=None):
        print("the received loop in the shutdownMaster is: ",loop)
        try:
            currentLoop = asyncio.get_running_loop() # get the current running loop, if exists
        except:
            currentLoop = None          # function called with no running loop active
            print("No running loop found.")
        if loop is not None:            # se um loop foi fornecido
            if loop != currentLoop:     # se o loop fornecido é diferente do atual avise
                print("loop provided is diferent from current loop")
            if isinstance(loop, asyncio.AbstractEventLoop): # se o loop fornecido é válido seta ele
                cls.running_loop = loop
                # print("Using provided loop")
            else:
                raise TypeError("Provided loop is not an instance of AbstractEventLoop")
        else:                          # se nenhum loop foi fornecido
            if cls.running_loop is not None:
                cls.running_loop = currentLoop
                print("Using current running loop because no loop was provided")
            else:
                print("No loop provided and no running loop stored.")

    @classmethod
    def set_thread_shutdown_function(cls,function ):
        cls.thread_shutdown_function = function

    @classmethod
    def set_task_shutdown_function(cls,function ):
        cls.task_shutdown_function = function

    @classmethod
    def autoShutdown(cls):
        """Função para iniciar o shutdown automático de threads e tasks"""
        # if cls.shutdown_event.is_set():
        try:
            with cls.shutdown_lock:
                print("Initiating automatic shutdown...")
                cls.shutDownComplete.clear() # reset the event before shutdown
                # Shutdown threads
                cls.thread_shutdown_function()
                # Shutdown async tasks
                # cls.set_loop() # ensure the loop is set
            if cls.running_loop is not None:
                res = asyncio.run_coroutine_threadsafe(cls.task_shutdown_function(), cls.running_loop).result()
            print("Automatic shutdown complete.")
        except exception as e:
            print("[autoShutdown] the exception is:", e)
        cls.shutDownComplete.set()
        # else:
        #     print("Shutdown already initiated.")

    @classmethod
    def waitMyShutdown(cls):
        """Função para esperar o shutdown ser completado"""
        try:
            print("Waiting for shutdown to begin...")
            cls.shutdown_event.wait()
            print("Shutdown event detected, proceeding with shutdown...")
            cls.autoShutdown()
        finally:
            if not cls.shutDownComplete.is_set():
                try:
                    cls.shutDownComplete.wait()
                except Exception as e:
                    print("deu ruim no evento shutdownComplete e foi:",e)
            
            logs = []
            for key in cls.logsMap:
                for event in cls.logsMap[key]:
                    logs.append(event)
            logs = sorted(logs, key = lambda x: x[0])
            last_time =0
            for ev in logs:
                if last_time ==0:
                    print(round(ev[0],6)," - ",ev[1])
                    last_time = ev[0]
                else:
                    delta = round(ev[0]- last_time,6)
                    last_time =ev[0]
                    print(delta," - ",ev[1])
            print("Shutdown complete.")
            cls.byebye.set()
    
def print_and_register(string,key):
    # print(string)
    shutdownMaster.logsMap[key].append([time.time(),string])

threading.Thread(target=shutdownMaster.waitMyShutdown).start()
# -------------------- Thread wrapper --------------------
class TrackedThread(threading.Thread):
    threadsMap = shutdownMaster.threadsMap

    def __init__(self, target, name, created_from,daemon = False,cleanup_event = None ,cleanup_function = None, *args, **kwargs):
        """created_from é um campo pra que eu consiga humanamente entender onde ela foi criada por exemplo:
            "EventBuffer.start" 
            ou algo parecido.
            vai ser uma string capaz de me fazer entender o contexto e onde localizar no codigo
        """
        super().__init__(target = target, 
                         name   = name, 
                         daemon = daemon,  
                         args   = args, 
                         kwargs = kwargs)
        selfCleanUpEvent = cleanup_event if cleanup_event is not None else shutdownMaster.shutdown_event #pensado para fazer operações internas de limpeza
        selfCleanUpEventUse = False #se a thread vai usar o evento de self cleanup
        trackedThread = TrackedItem(
            self,
            selfCleanUpEvent, 
            selfCleanUpEventUse,
            name = name, 
            kind = "thread",
            created_from = created_from, 
            cleanup_function = cleanup_function) 
        if not name:
            print("thread veio com nome que deu false e foi: ",name," registrando como 'unnamedThread'")
            TrackedThread.threadsMap.setdefault("unnamedThread", []).append(trackedThread)
        else:
            TrackedThread.threadsMap.setdefault(name, []).append(trackedThread)
        print_and_register(f"[Thread Created] {self.name}","threads")
        # # logger.info(f"[Thread Created] {self.name}")

    def run(self):
        print_and_register(f"[Thread Started] {self.name}","threads")
        
        # logger.info(f"[Thread Started] {self.name}")
        try:
            super().run()
        finally:
            print_and_register(f"[Thread Exited] {self.name}","threads")
            # logger.info(f"[Thread Exited] {self.name}")
            if self.name in TrackedThread.threadsMap:
                TrackedThread.threadsMap[self.name] = [
                    t for t in TrackedThread.threadsMap[self.name] if t.obj != self
                ]
                if not TrackedThread.threadsMap[self.name]:
                    del TrackedThread.threadsMap[self.name]

    @classmethod
    def shutdown_threads(cls, timeout=None):
        print("[Shutdown] Signaling all threads to stop...")
        # logger.info("[Shutdown] Signaling all threads to stop...")
        
        # Sinaliza o evento de shutdown
        # shutdownMaster.shutdown_event.set()
        
        # Espera cada thread encerrar
        for name, threads in list(cls.threadsMap.items()):
            for tracked in threads:
                thread_obj, clean_event, use_flag , clean_function = tracked.obj, tracked.cleanup_event, tracked.cleanup_enabled, tracked.cleanup_function
                if clean_event != cls.shutdown_event:
                    print("[Shutdown] this thread has personalized shutdown!")
                    if not clean_event.is_set():
                        print("[Shutdown] setting it now!")
                        clean_event.set()
                    else:
                        print("[Shutdown] but is already set!")

                if callable(clean_function):
                    print_and_register("[Shutdown] trying to execute cleanup_function!","threads")
                    execute_cleanup_function(clean_function)

                if thread_obj.is_alive():
                    print_and_register(f"[Shutdown] Waiting thread {thread_obj.name} to exit...","threads")
                    # logger.info(f"[Shutdown] Waiting thread {thread_obj.name} to exit...")
                    try:
                        thread_obj.join(timeout)
                    except Exception as e:
                        print_and_register("deu erro e foi: "+str(e),"threads")

                    print_and_register(f"[Shutdown] thread {thread_obj.name} just finished","threads")

            # Limpa a lista
            try:
                print("[Shutdown] trying to clean the threads Registry")
                cls.threadsMap[name] = [t for t in threads if t.obj.is_alive()]
                if not cls.threadsMap[name]:
                    del cls.threadsMap[name]
                print("[Shutdown] got it !")
            except Exception as e:
                print("[Shutdown] deu erro e foi:  ",e)
        print("[Shutdown] All threads signaled.")
        # logger.info("[Shutdown] All threads signaled.")
    shutdownMaster.set_thread_shutdown_function(shutdown_threads)



# -------------------- Async Task wrapper --------------------
def tracked_task(coro, name, created_from, cleanup_event = None,cleanup_function = None):
    """
    Cria uma async task com logging
    
    created_from é um campo pra que eu consiga humanamente entender onde ela foi criada por exemplo:
    "EventBuffer.start" 
    ou algo parecido.
     vai ser uma string capaz de me fazer entender o contexto e onde localizar no codigo
    """
    task_name = name or str(asyncio.current_task())
    
    async def wrapper():
        print_and_register(f"[Async Task Started] {task_name}","tasks")
        # logger.info(f"[Async Task Started] {task_name}")
        try:
            return await coro
        except asyncio.CancelledError:
            print_and_register(f"[Async Task Cancelled] {task_name}","tasks")
            # logger.info(f"[Async Task Cancelled] {task_name}")
            raise
        finally:
            print_and_register(f"[Async Task Exited] {task_name}","tasks")
            # logger.info(f"[Async Task Exited] {task_name}")
    ######### criando elementos do trackedItem #########
    task = asyncio.create_task(wrapper(),name = task_name) # cria a task async
    selfCleanUpEvent    = shutdownMaster.shutdown_event   # pensado para fazer operações internas de limpeza
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
        shutdownMaster.tasksMap.setdefault(task_name, []).append(currentTaskItem) # cria a lista se não existir e seta a task
    else:
        shutdownMaster.tasksMap["unnamedTasks"].append(currentTaskItem)
    
    print_and_register(f"[Async Task Created] {task_name}","tasks")
    # logger.info(f"[Async Task Created] {task_name}")
    
    
    return task

async def shutdown_tasks():
    print_and_register("[Shutdown] Cancelling all async tasks...","tasks")
    # logger.info("[Shutdown] Cancelling all async tasks...")
    
    all_tasks = []
    for name, task_list in shutdownMaster.tasksMap.items():
        for tracked in task_list:
            task_obj, clean_event, use_flag = tracked.obj, tracked.cleanup_event, tracked.cleanup_enabled
            if not task_obj.done():
                print_and_register(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}","tasks")
                # logger.info(f"[Shutdown] Cancelling task {task_obj.get_name() if name else task_obj}")
                if shutdownMaster.running_loop is not None:
                    shutdownMaster.running_loop.call_soon_threadsafe(task_obj.cancel)
                else:
                    print_and_register("No running loop set in shutdownMaster, cannot cancel task properly. the task was: "+ str(task_obj),"tasks")
                all_tasks.append(task_obj)
    
    if all_tasks:
        await asyncio.gather(*all_tasks, return_exceptions=True)
    
    # Limpa tasks concluídas
    for name in list(shutdownMaster.tasksMap.keys()):
        shutdownMaster.tasksMap[name] = [t for t in shutdownMaster.tasksMap[name] if not t.obj.done()]
        if not shutdownMaster.tasksMap[name] and name != "unnamedTasks":
            del shutdownMaster.tasksMap[name]
    print_and_register("[Shutdown] All async tasks cancelled.","tasks")
    if len(shutdownMaster.tasksMap) > 1:
        print_and_register("[Shutdown] Some async tasks could not be cancelled","tasks")
        for task_name in shutdownMaster.tasksMap.keys():
            if task_name != "unnamedTasks":
                print("the task is: ",task_name)
        
        # logger.info("[Shutdown] Some async tasks could not be cancelled")
        return False
    else:
        print_and_register("[Shutdown] All async tasks handled.","tasks")
        # logger.info("[Shutdown] All async tasks handled.")
        return True

shutdownMaster.set_task_shutdown_function(shutdown_tasks)
# -------------------- Funções utilitárias Desatualizadas!!!!! --------------------
def print_thread_status():
    print("=== THREAD STATUS ===")
    # logger.info("=== THREAD STATUS ===")
    for t in threading.enumerate():

        print(f"Thread: {t.name}, alive: {t.is_alive()}, daemon: {t.daemon}")
        # logger.info(f"Thread: {t.name}, alive: {t.is_alive()}, daemon: {t.daemon}")


def print_async_tasks_status():
    print("=== ASYNC TASKS STATUS ===")
    # logger.info("=== ASYNC TASKS STATUS ===")

    for t in asyncio.all_tasks():
        if t is asyncio.current_task():
            continue
        try:
            name = t.get_name()
        except AttributeError:
            name = str(t)
        print(f"Task: {name}, done: {t.done()}")
        # logger.info(f"Task: {name}, done: {t.done()}")


async def shutdown_all_async():
    print("Cancelling all async tasks...")
    # logger.info("Cancelling all async tasks...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in tasks:
        try:
            t.cancel()
            print(f"Cancelled {t.get_name() if hasattr(t, 'get_name') else t}")
            # logger.info(f"Cancelled {t.get_name() if hasattr(t, 'get_name') else t}")
        except Exception as e:
            print(f"Error cancelling task {t}: {e}")
            # logger.warning(f"Error cancelling task {t}: {e}")
    await asyncio.gather(*tasks, return_exceptions=True)
    print("All async tasks cleaned up.")
    # logger.info("All async tasks cleaned up.")


def shutdown_all_threads(threads):
    print("Stopping all threads...")
    # logger.info("Stopping all threads...")
    for t in threads:
        if hasattr(t, "stop"):
            t.stop()
    for t in threads:
        t.join()
    print("All threads cleaned up.")
    # logger.info("All threads cleaned up.")


if __name__ == "__main__":
    # texts are made here
    pass
