import time
import threading
import asyncio
import logging
# sharedResources/generalUtils
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.shutdownThreadUtils import TrackedThread
from sharedResources.lifecycle.shutdownTaskUtils import Tracked_task
from sharedResources.lifecycle.cleanup_function import execute_cleanup_function
from sharedResources.lifecycle.printUtils import print_thread_status, print_async_tasks_status
from sharedResources.lifecycle.utils import wait_event


# Setup básico de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("LifecycleTracker")




class ShutdownMaster():
    """
    mapa para rastrear as threads e tasks com nomes iguais ou não"""
    # ------- events -------
    shutdown_event = threading.Event() #tem que setar esse evento em runtime pelo processo principal
    shutDownComplete = threading.Event()
    byebye           = threading.Event()
    # ----------------------
    # ------- locks --------
    shutdown_lock = threading.Lock()
    shutDownExternalLock = threading.Lock() # para o uso externo acontecer apenas uma vez
    # ---------------------
    running_loop = []
    # -------- maps -------
    threadsMap = {}
    tasksMap = {"unnamedTasks":[]}
    logsMap = {"threads":[],"tasks":[], 'general': []}
    # ---------------------

    task_shutdown_function   = Tracked_task.shutdown_tasks
    thread_shutdown_function = TrackedThread.shutdown_threads
    @classmethod
    def register_log(cls,string,key):
        print(string)
        ShutdownMaster.logsMap[key].append([time.time(),string])

    @classmethod
    def set_loop(cls, loop=None):
        print("the received loop in the ShutdownMaster is: ",loop)

        if len(cls.running_loop) > 0 and loop == cls.running_loop[0]:
            print("it is already this loop exactly!")
            return
        try:
            currentLoop = asyncio.get_running_loop() # get the current running loop, if exists
        except:
            currentLoop = None          # function called with no running loop active
            print("No running loop found.")
        if loop is not None:            # se um loop foi fornecido
            if currentLoop is not None and loop != currentLoop:     # se o loop fornecido é diferente do atual avise
                print("loop provided is diferent from current loop")
            if isinstance(loop, asyncio.AbstractEventLoop): # se o loop fornecido é válido seta ele
                cls.running_loop.clear()
                cls.running_loop.append(loop)
                print("Using provided loop")
            else:
                raise TypeError("Provided loop is not an instance of AbstractEventLoop")
        else:                          # se nenhum loop foi fornecido
            if cls.running_loop is not None:
                cls.running_loop.clear()
                cls.running_loop.append(currentLoop)
                print("Using current running loop because no loop was provided")
            else:
                print("No loop provided and no running loop stored.")

    

    @classmethod
    def autoShutdown(cls):
        """Função para iniciar o shutdown automático de threads e tasks"""
        # if cls.shutdown_event.is_set():
        try:
            cls.register_log("Initiating automatic shutdown...","general")
            if len(cls.running_loop)>0:
                cls.register_log("iniciating tasks shutdown","general")
                res = asyncio.run_coroutine_threadsafe(cls.task_shutdown_function(), cls.running_loop[0])
                res.result(timeout = 5)
            else:
                print("o loop é algo vazio e é: ",cls.running_loop)
            with cls.shutdown_lock:
                cls.shutDownComplete.clear() # reset the event before shutdown
                # Shutdown async tasks
                # Shutdown threads
                cls.register_log("iniciating thread shutdown","general")
                cls.thread_shutdown_function()
                # cls.set_loop() # ensure the loop is set
            print("Automatic shutdown complete.")
        except Exception as e:
            print("[autoShutdown] the exception is:", e)
        finally:
            print("vou setar o shutdownComplete")
            cls.shutDownComplete.set()
            print("setei o shutdownComplete")
        # else:
        #     print("Shutdown already initiated.")

    @classmethod
    def waitMyShutdown(cls):
        """Função para esperar o shutdown ser completado"""
        try:
            print("Waiting for shutdown to begin...")
            wait_event(cls.shutdown_event,"ShutdownMaster.shutdown_event")
            cls.register_log("Shutdown event detected, proceeding with shutdown...","general")
            cls.autoShutdown()
        finally:
            if not cls.shutDownComplete.is_set():
                try:
                    wait_event(cls.shutDownComplete," ShutdownMaster.shutDownComplete event")
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
    
    @classmethod
    def prepare_dependencies(cls):
        TrackedThread.set_threadsMap( cls.threadsMap)
        TrackedThread.set_default_cleanup_event( cls.shutdown_event)
        TrackedThread.set_register_log( cls.register_log)
        TrackedThread.set_running_loop(cls.running_loop)
        # TrackedThread.set_shutdown_event(cls.shutdown_event)

        Tracked_task.set_tasksMap(cls.tasksMap)
        Tracked_task.set_default_cleanup_event( cls.shutdown_event)
        Tracked_task.set_register_log( cls.register_log)
        Tracked_task.set_running_loop( cls.running_loop)
    

ShutdownMaster.prepare_dependencies()


threading.Thread(target=ShutdownMaster.waitMyShutdown).start()




# ShutdownMaster.set_task_shutdown_function(shutdown_tasks)

if __name__ == "__main__":
    # texts are made here
    pass

# async def shutdown_all_async():
#     print("Cancelling all async tasks...")
#     # logger.info("Cancelling all async tasks...")
#     tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
#     for t in tasks:
#         try:
#             t.cancel()
#             print(f"Cancelled {t.get_name() if hasattr(t, 'get_name') else t}")
#             # logger.info(f"Cancelled {t.get_name() if hasattr(t, 'get_name') else t}")
#         except Exception as e:
#             print(f"Error cancelling task {t}: {e}")
#             # logger.warning(f"Error cancelling task {t}: {e}")
#     await asyncio.gather(*tasks, return_exceptions=True)
#     print("All async tasks cleaned up.")
#     # logger.info("All async tasks cleaned up.")


# def shutdown_all_threads(threads):
#     print("Stopping all threads...")
#     # logger.info("Stopping all threads...")
#     for t in threads:
#         if hasattr(t, "stop"):
#             t.stop()
#     for t in threads:
#         t.join()
#     print("All threads cleaned up.")
#     # logger.info("All threads cleaned up.")


