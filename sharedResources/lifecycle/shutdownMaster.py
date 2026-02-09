import os
import time
import threading
import asyncio
import logging
# sharedResources/generalUtils
import warnings
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.shutdownThreadUtils import TrackedThread
from sharedResources.lifecycle.shutdownTaskUtils import TrackedTask
from sharedResources.lifecycle.printUtils import print_thread_status, print_async_tasks_status
from sharedResources.lifecycle.utils import wait_event
from sharedResources.lifecycle.loop.loop_class import MyLoop
from sharedResources.lifecycle.trackedUtils.tasksMapClass import TasksMapClass
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.exec_monitor import  count_methods

# Setup básico de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("LifecycleTracker")



@count_methods
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
    tasksMap = TasksMapClass
    logsMap = {"threads":[],"tasks":[], 'general': []}
    # ---------------------

    task_shutdown_function   = TrackedTask.shutdown_tasks
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
    def call_soon(cls, fn, *args):
        cls.running_loop.call_soon(fn, *args)
    
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
            

        cls.shutdown_event.set()
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
            res = cls.running_loop.submit(main_coro, protected = True, name = "main")
        else:
            # print("Main coroutine is a regular function, scheduling it.")
            res  = cls.running_loop.call_soon(main_coro)
        # print("Main coroutine submitted:", res)
    

    @classmethod
    def autoShutdown(cls):
        try:
            from PythonSistemAutomation.watcher_utils.GlobalMacroExecutor import GlobalExecutor
        except Exception as e:
            print("falhei no import e deu: " , e )

        """Função para iniciar o shutdown automático de threads e tasks"""
        # if cls.shutdown_event.is_set():
        if cls.state == "SHUTTING_DOWN":
            cls.register_log("algo fez autoshutdown ser chamada mais de uma vez!","general")
        else:
            state = "SHUTTING_DOWN"
            cls.register_log("iniciando o autoshutdown","general")
        try:
            cls.register_log("Initiating automatic shutdown...","general")
            LifecycleMaster.run_async(GlobalExecutor.umpress_keys(), state = cls.state)
            if cls.running_loop.get() is not None:
                if not cls._loop_is_ok():
                    cls.register_log("[autoShutDown] loop is not ok just before task_shutdown_function be called!","general")
                else:
                    cls.register_log("iniciating tasks shutdown","general")
                    res = asyncio.run_coroutine_threadsafe(cls.task_shutdown_function(), cls.running_loop.get())
                    res.result(timeout = 10)
                    cls.register_log(f"[autoShutdown]esperei o task_shutdown_function e o resultado foi:{res} ")
                    cls.tasksMap.relatorio()
            else:     
                print("o loop é algo vazio e é: ",cls.running_loop.get())
            cls.register_log(f"logo antes do shutdown_lock no autoShutdown")
            with cls.shutdown_lock:
                cls.register_log(f"logo depois do shutdown_lock no autoShutdown")
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
            log_error_forensics_plus(e)
        finally:
            print("vou setar o shutdownComplete")
            cls.tasksMap.relatorio()
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
                    log_error_forensics_plus(e)
            else:
                print("shutdownComplete Event is set properly")
            
            logs = []
            for key in cls.logsMap:
                for event in cls.logsMap[key]:
                    logs.append(event)
            logs = sorted(logs, key = lambda x: x[0])
            last_time =0
            print_detailed = 'n'
            # print("logo antes do input o print_detailed é: ",print_detailed)
            # try:
            #     print_detailed = input("quer o log detalhado?(s/n)")
            # except Exception as e:
            #     print("deu erro no input e foi: ",e)
            if print_detailed == 's': #### desse jeito não printa o log inteiro do lifecycle
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
    def run_async(coro, *args, **kargs):
        """Submete uma coroutine para execução segura no loop"""
        return MyLoop.submit(coro, *args, **kargs)

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
        MyLoop.set_register_log(        cls.register_log)
        TrackedThread.set_register_log( cls.register_log)
        TrackedTask.set_register_log(   cls.register_log)
        cls.tasksMap.set_register_log( cls.register_log)
        
        #setting up the maps
        TrackedThread.set_threadsMap( cls.threadsMap)
        TrackedTask.set_tasksMap(cls.tasksMap)
        MyLoop.set_tasksMap(cls.tasksMap)

        #setting up the cleanup events
        TrackedThread.set_default_cleanup_event( cls.shutdown_event)
        TrackedTask.set_default_cleanup_event(   cls.shutdown_event)
        MyLoop.set_default_shutdown_event(       cls.shutdown_event)
        cls.tasksMap.set_default_cleanup_event(  cls.shutdown_event)

        #setting up the loop
        TrackedThread.set_running_loop(cls.running_loop)
        TrackedTask.set_running_loop( cls.running_loop)
    

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