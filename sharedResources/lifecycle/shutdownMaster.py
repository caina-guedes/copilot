import os
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
from sharedResources.lifecycle.printUtils import print_thread_status, print_async_tasks_status
from sharedResources.lifecycle.utils import wait_event
from sharedResources.lifecycle.loop.loop_class import MyLoop

# Setup básico de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("LifecycleTracker")




class LifecycleMaster():
    """
        dono do ciclo de vida de tudo que precisa ser controlado 
        para organizar inicialização e shutdown
    """
    
    running_loop = MyLoop() # loop principal único!
    state = "INIT" #  

    #flag para modo de testes
    testing = False

    # ------- events -------
    shutdown_event = threading.Event() #tem que setar esse evento em runtime pelo processo principal
    shutDownComplete = threading.Event()
    byebye           = threading.Event()
    # ----------------------
    # ------- locks --------
    shutdown_lock = threading.Lock()
    shutDownExternalLock = threading.Lock() # para o uso externo acontecer apenas uma vez
    logsLock             = threading.Lock() # para não haver concorrência no registro de logs
    # ---------------------
    # -------- maps -------
    threadsMap = {}
    tasksMap = {"unnamedTasks":[]}
    logsMap = {"threads":[],"tasks":[], 'general': []}
    # ---------------------

    task_shutdown_function   = Tracked_task.shutdown_tasks
    thread_shutdown_function = TrackedThread.shutdown_threads


    @classmethod
    def register_log(cls,string,key = "general", emergency = False):
        print(string)
        if not emergency:
            with cls.logsLock:
                LifecycleMaster.logsMap.setdefault(key,[]).append([time.time(),string])
        else:
            LifecycleMaster.logsMap.setdefault(key,[]).append([time.time(),string])
    
    @classmethod
    def _loop_is_ok(cls):
        return cls.running_loop._loop_is_ok()
        
    @classmethod
    def emergency_shutdown(cls,erro):
        #previne reentrada!
        if cls.state == "EMERGENCY":
            return
        cls.state = "EMERGENCY"
        
        mensagem = "[Emergency] deu merda no loop principal e foi: " + str(erro)
        try:
            cls.register_log(mensagem, "general", emergency = True)
        except:
            pass
            

        shutdown_event.set()
        # task_shutdown_event.set()
        # thread_shutdown_event.set()

        # fechar o loop se existir
        try:
            if cls._loop_is_ok():
                print("setando o stop do loop durante emergencia... boa sorte")
                cls.schedule(MyLoop.stop_loop)

                # cls.running_loop.get().call_soon_threadsafe(cls.running_loop.get().stop)
            else:
                print("não tem mais loop funcionando!")
        except:
            pass

        # DO NOT WAIT
        try:
            os._exit(1)
        except:
            pass




    @classmethod
    def start_runtime(cls, main_coro):
        cls.running_loop.start_loop()
        # print("Main loop started:", cls.running_loop.get())
        # print("Submitting main to the loop...")
        if asyncio.iscoroutine(main_coro) or asyncio.iscoroutinefunction(main_coro):
            # print("Main coroutine is a coroutine or coroutine function.")
            res = cls.running_loop.submit(main_coro, protected = True)
        else:
            # print("Main coroutine is a regular function, scheduling it.")
            res  = cls.running_loop.call_soon(main_coro)
        print("Main coroutine submitted:", res)
    

    @classmethod
    def autoShutdown(cls):
        """Função para iniciar o shutdown automático de threads e tasks"""
        # if cls.shutdown_event.is_set():
        if cls.state == "SHUTTING_DOWN":
            cls.register_log("algo fez autoshutdown ser chamada mais de uma vez!","general")
        else:
            state = "SHUTTING_DOWN"
            cls.register_log("iniciando o autoshutdown","general")
        try:
            cls.register_log("Initiating automatic shutdown...","general")
            if cls.running_loop.get() is not None:
                if not cls._loop_is_ok():
                    cls.register_log("[autoShutDown] loop is not ok just before task_shutdown_function be called!","general")
                else:
                    cls.register_log("iniciating tasks shutdown","general")
                    res = asyncio.run_coroutine_threadsafe(cls.task_shutdown_function(), cls.running_loop.get())
                    res.result(timeout = 5)
            else:
                print("o loop é algo vazio e é: ",cls.running_loop.get())
            with cls.shutdown_lock:
                cls.shutDownComplete.clear() # reset the event before shutdown
                # Shutdown async tasks
                # Shutdown threads
                cls.register_log("iniciating thread shutdown","general")
                cls.thread_shutdown_function()
                # cls.set_loop() # ensure the loop is set
            if cls._loop_is_ok():
                print("setando o stop do loop... boa sorte")
                MyLoop.stop_loop()
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
            if cls.testing:
                wait_event(cls.shutdown_event,"LifecycleMaster.shutdown_event")
            else:
                cls.shutdown_event.wait()
            cls.register_log("Shutdown event detected, proceeding with shutdown...","general")
            cls.autoShutdown()
        finally:
            if not cls.shutDownComplete.is_set():
                try:
                    wait_event(cls.shutDownComplete," LifecycleMaster.shutDownComplete event")
                except Exception as e:
                    print("deu ruim no evento shutdownComplete e foi:",e)
            else:
                print("shutdownComplete Event is set properly")
            
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
    # -------------------------------
    # Wrappers de execução de coroutines
    # -------------------------------

    @staticmethod
    def run_async(coro):
        """Submete uma coroutine para execução segura no loop"""
        return MyLoop.submit(coro)

    @staticmethod
    def gather(*coros, return_exceptions=False):
        """Garante thread-safe para asyncio.gather"""
        async def _inner():
            return await asyncio.gather(*coros, return_exceptions=return_exceptions)
        return MyLoop.submit(_inner())

    # -------------------------------
    # Wrappers de callbacks síncronos
    # -------------------------------

    @staticmethod
    def schedule(fn, *args):
        """Agenda uma função sync no loop (thread-safe)"""
        return MyLoop.call_soon(fn, *args)

    # -------------------------------
    # Wrappers de controle do loop
    # -------------------------------

    @staticmethod
    def shutdown_loop(graceful=True):
        """Encerra o loop de forma segura"""
        return MyLoop.stop(graceful=graceful)


    @classmethod
    def prepare_dependencies(cls):
        # preparando as dependências para o lifecycle master

        # setting up the register log functions
        MyLoop.set_register_log(cls.register_log)
        TrackedThread.set_register_log( cls.register_log)
        Tracked_task.set_register_log( cls.register_log)

        #setting up the maps
        TrackedThread.set_threadsMap( cls.threadsMap)
        Tracked_task.set_tasksMap(cls.tasksMap)

        #setting up the cleanup events
        TrackedThread.set_default_cleanup_event( cls.shutdown_event)
        Tracked_task.set_default_cleanup_event( cls.shutdown_event)

        #setting up the loop
        TrackedThread.set_running_loop(cls.running_loop)
        Tracked_task.set_running_loop( cls.running_loop)
    

LifecycleMaster.prepare_dependencies()


threading.Thread(target=LifecycleMaster.waitMyShutdown).start()




# LifecycleMaster.set_task_shutdown_function(shutdown_tasks)

if __name__ == "__main__":
    # texts are made here
    pass







    # -------------------------------
    # Opcional: wrapper para run_in_executor
    # # -------------------------------

    # @staticmethod
    # def run_in_executor(fn, *args, executor=None):
    #     """Executa uma função em um executor thread-safe no loop"""
    #     async def _inner():
    #         loop = MyLoop.get()
    #         if loop is None:
    #             MyLoop._log("Cannot run in executor: loop is None")
    #             return None
    #         return await loop.run_in_executor(executor, fn, *args)
    #     return MyLoop.submit(_inner())