# from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
from enum import Enum
import os
import time
import threading
import asyncio
import logging
import inspect

# sharedResources/generalUtils
import warnings
import sys
from pathlib import Path

basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.generalUtils.print_interceptor import PrintInterceptor
###  o print interceptor tem que ser o primeiro a ser importado em todos os casos!!!!!
import sharedResources.lifecycle.atexit_manager as atexit_manager
from sharedResources.lifecycle.atexit_manager import (
    AtexitShutdownMonitor as AtexitObserver,
)
from sharedResources.lifecycle.gracious_cleanup_manager import GraciousCleanupManager
from sharedResources.lifecycle.shutdownThreadUtils import TrackedThread
from sharedResources.lifecycle.shutdownTaskUtils import TrackedTask
from sharedResources.lifecycle.printUtils import (
    print_thread_status,
    print_async_tasks_status,
)
from sharedResources.lifecycle.utils import wait_event
from sharedResources.lifecycle.loop.loop_class import MyLoop
from sharedResources.lifecycle.trackedUtils.tasksMapClass import TasksMapClass
from sharedResources.debuggingResources.error_tracker import (
    errorExtruture,
    log_error_forensics_plus,
)
from sharedResources.debuggingResources.unified_monitor import (
    sys_monitor,
    monitor_class,
)
from sharedResources.debuggingResources.exec_monitor import CallRegistry
from sharedResources.lifecycle.stateManager import State, StateManager
from sharedResources.pythonLoggerSistem.logger import LoggerManager

# Setup básico de logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("LifecycleTracker")

# class State (Enum):
#     INIT = "INIT"
#     RUNNING = "RUNNING"
#     SHUTTING_DOWN = "SHUTTING_DOWN"
#     EMERGENCY = "EMERGENCY"
_handler_ref = None
# LifecycleMaster.register_cleanup_function
# LifecycleMaster.register_cleanup_function
checkpoints = [
    "autoShutdown_init",
    "autoShutdown_end",
    "autoShutdown_finally",
    "waitMyShutdown_init",
    "waitMyShutdown_end",
    "waitMyShutdown_finally",
]
for checkpoint in checkpoints:
    AtexitObserver.register_checkpoint(checkpoint)

badCheckpoints = [
    "autoShutdown_error",
    "waitMyShutdown_error",
    "emergency_shutdown_init",
    "emergency_shutdown_end",
]
for checkpoint in badCheckpoints:
    AtexitObserver.register_checkpoint(checkpoint, occurrences=0)


# @monitor_class
class LifecycleMaster:
    """
    dono do ciclo de vida de tudo que precisa ser controlado
    para organizar inicialização e shutdown
    """
    current_main_corro = []
    software_thread = None
    cleanup_manager = GraciousCleanupManager

    running_loop = MyLoop()  # loop principal único!
    lifecycleState = StateManager  #
    stateEnum = State

    # flag para interceptar o print
    print_intercept = True
    print_interceptor = None
    # flag para modo de testes
    testing = False

    # ------- events -------
    first_shutdown_event = threading.Event()
    shutdown_event = (
        threading.Event()
    )  # tem que setar esse evento em runtime pelo processo principal
    shutDownComplete = threading.Event()
    byebye = threading.Event()
    # ----------------------
    # ------- locks --------
    shutdown_lock = threading.Lock()
    shutDownExternalLock = (
        threading.Lock()
    )  # para o uso externo acontecer apenas uma vez
    logsLock = threading.Lock()  # para não haver concorrência no registro de logs
    # ---------------------
    # -------- maps -------
    threadsMap = {}
    tasksMap = TasksMapClass
    logsMap = {"threads": [], "tasks": [], "general": []}
    # ---------------------

    task_shutdown_function = TrackedTask.shutdown_tasks
    thread_shutdown_function = TrackedThread.shutdown_threads

    ### flag de dev mode !!!
    devMode = True

    _sinal_de_parada_plugado = False

    @classmethod
    def set_devMode(cls, mode):
        cls.devMode = mode
        print(f"set to {cls.devMode}")

    @classmethod
    def register_log(cls, string, key="general", emergency=False):
        print(string)
        if not emergency:
            with cls.logsLock:
                LifecycleMaster.logsMap.setdefault(key, []).append(
                    [time.time(), string]
                )
        else:
            LifecycleMaster.logsMap.setdefault(key, []).append([time.time(), string])

    @classmethod
    def _loop_is_ok(cls):
        return cls.running_loop._loop_is_ok()

    @classmethod
    def call_soon(cls, fn, *args):
        cls.running_loop.call_soon(fn, *args)

    @classmethod
    def espera_pelo_tchau(cls):
        try:
            print("esperando byebye na thread principal!")
            cls.byebye.wait()
            print("Aplicação encerrada. Bye bye!")
        except Exception as e:
            print("deu erro esperando pelo byebye na thread principal e foi:",str(e))
            print("vou tentar usar a log_error_forensics_plus e em seguida resetar e ativar o first_shutdown_event ")
            try:
                log_error_forensics_plus(e, cancelLogging = True )
            except:
                pass
            cls.first_shutdown_event.clear()
            cls.first_shutdown_event.set()
            cls.byebye.wait()

    @classmethod
    def pluga_sinal_de_parada(cls):
        try:

            if cls._sinal_de_parada_plugado:
                return
            else:
                cls._sinal_de_parada_plugado = True
            print("init")
            import signal
            import platform

            def set_inicial_shutdown_event(*args):
                print("setting the first_shutdown_event event!")
                cls.first_shutdown_event.set()
                return True

            AtexitObserver.register(set_inicial_shutdown_event)
            # atexit.register(set_inicial_shutdown_event)
            print("registered the  set_inicial_shutdown_event function on  atexit")
            ### coloca os signals básicos
            signal.signal(signal.SIGINT, set_inicial_shutdown_event)
            print("registered the signal.SIGINT")
            ### esse aqui estou mandando do orquestrator 
            
            if platform.system() == "Windows":
                # print("vou registrar o CTRL_BREAK_EVENT")
                # signal.signal(signal.CTRL_BREAK_EVENT,set_inicial_shutdown_event)
                # print("registrei o CTRL_BREAK_EVENT")
                signal.signal(signal.SIGBREAK, set_inicial_shutdown_event)
                print("registered the signal.SIGBREAK on windows ")
            else:
                print("registered the signal.SIGTERM on linux")
                signal.signal(signal.SIGTERM, set_inicial_shutdown_event)
            ###############################################################
            if platform.system() == "Windows":
                global _handler_ref
                import ctypes
                from ctypes import wintypes  # <--- Adicione isso explicitamente

                # Protótipo da função de callback
                PHANDLER_ROUTINE = ctypes.WINFUNCTYPE(
                    wintypes.BOOL, ctypes.wintypes.DWORD
                )

                def console_handler(ctrl_type):
                    # 0: CTRL_C, 2: CLOSE (Botão X), 5: LOGOFF, 6: SHUTDOWN

                    if ctrl_type in (0, 2, 5, 6):
                        print("[win32] Console fechando ou Ctrl+C detectado...")
                        set_inicial_shutdown_event()  # Chama sua função de limpeza diretamente
                        # import _thread
                        # _thread.interrupt_main()
                        return True
                    else:
                        print('[win32] veio código inesperado aqui e foi: ',ctrl_type)
                    return False

                # Registra o handler no Windows
                _handler_ref = PHANDLER_ROUTINE(console_handler)
                print(
                    "registered on windows handler PHANDLER_ROUTINE(console_handler) "
                )
                if not ctypes.windll.kernel32.SetConsoleCtrlHandler(_handler_ref, True):
                    print("Erro ao registrar o handler de fechamento do terminal.")
                else:
                    print("Sucesso ao registrar o handler de fechamento do terminal.")
        except Exception as e:
            log_error_forensics_plus(e)

    @classmethod
    def emergency_shutdown(cls, erro):
        AtexitObserver.check(
            "emergency_shutdown_init"
        )  # checkpoint para monitorar se a função de emergência foi chamada durante o shutdown
        # previne reentrada!
        if cls.lifecycleState.state is State.EMERGENCY:
            return
        cls.lifecycleState.state = State.EMERGENCY

        mensagem = "[Emergency] deu merda no loop principal e foi: " + str(erro)
        try:
            cls.register_log(mensagem, "general", emergency=True)
        except:
            pass

        cls.shutdown_event.set()
        atexit_manager.shutdown_iniciated = True
        # task_shutdown_event.set()
        # thread_shutdown_event.set()

        # fechar o loop se existir
        try:
            if cls._loop_is_ok():
                print("setando o stop do loop durante emergencia... boa sorte")
                cls.call_soon(MyLoop.stop_loop)

                # cls.running_loop.get().call_soon_threadsafe(cls.running_loop.get().stop)
            else:
                print("não tem mais loop funcionando!")
        except:
            pass

        # DO NOT WAIT
        try:
            AtexitObserver.check(
                "emergency_shutdown_end"
            )  # checkpoint para monitorar se a função de emergência foi chamada durante o shutdown

            os._exit(1)
        except:
            pass
    
    @classmethod
    def prepare_for_start_runtime(cls,main_coro):
        cls.current_main_corro.append(main_coro)
        if cls.software_thread is None:
            cls.pluga_sinal_de_parada()
            cls.software_thread = threading.Thread(target = cls.start_runtime)
            cls.software_thread.start()
        else:
            print("preciso implementar o que acontece quando uso a prepare_for_start_runtime pela segunda vez! ")
            1/0
            pass 


    @classmethod
    def start_runtime(cls, main_coro =None):
        print('[start_runtime] init')
        if main_coro is None:
            main_coro = cls.current_main_corro[-1]
        if cls.running_loop.loop_is_none():
            cls.running_loop.start_loop()
        # if cls.print_intercept:
        #     cls.print_interceptor = PrintInterceptor()
        #     cls.print_interceptor.install()
        #     cls.print_interceptor.enable()
        quanto_de_corro = len(cls.current_main_corro)
        correct_name = 'main' + str(quanto_de_corro) if quanto_de_corro > 1 else 'main'
        # print("Main loop started:", cls.running_loop.get())
        # print("Submitting main to the loop...")
        if inspect.iscoroutine(main_coro) or inspect.iscoroutinefunction(main_coro):
            # print("Main coroutine is a coroutine or coroutine function.")
            res = cls.running_loop.submit(main_coro, protected=True, name = correct_name)
        else:
            # print("Main coroutine is a regular function, scheduling it.")
            res = cls.running_loop.call_soon(main_coro)
        if cls.lifecycleState.state == State.INIT:
            cls.lifecycleState.state = State.RUNNING
        
        # print("Main runtime started. the lifecicleState is: ", cls.lifecycleState.state )
        # print("Main coroutine submitted:", res)

    @classmethod
    def autoShutdown(cls):
        """Função para iniciar o shutdown automático de threads e tasks"""
        # if cls.shutdown_event.is_set():
        if cls.lifecycleState.state is State.SHUTTING_DOWN:
            cls.register_log(
                "algo fez autoshutdown ser chamada mais de uma vez!", "general"
            )
        else:
            cls.lifecycleState.state = State.SHUTTING_DOWN
            atexit_manager.shutdown_iniciated = True

            cls.register_log("iniciando o autoshutdown", "general")
        AtexitObserver.check("autoShutdown_init")  # checkpoint para monitorar inicio
        try:
            cls.register_log("Initiating automatic shutdown...", "general")
            if cls.running_loop.get() is not None:
                if not cls._loop_is_ok():
                    cls.register_log(
                        "[autoShutDown] loop is not ok just before task_shutdown_function be called!",
                        "general",
                    )
                else:
                    cls.register_log("iniciating cleanup for shutdown", "general")
                    cls.cleanup_manager.execute_hooks()
                    cls.register_log("finished cleanup before shutdown", "general")
                    cls.shutdown_event.set()
                    cls.register_log("iniciating tasks shutdown", "general")
                    res = asyncio.run_coroutine_threadsafe(
                        cls.task_shutdown_function(), cls.running_loop.get()
                    )
                    res.result(timeout=10)
                    cls.register_log(
                        f"[autoShutdown]esperei o task_shutdown_function e o resultado foi:{res} "
                    )
                    # cls.tasksMap.relatorio()
            else:
                print("o loop é algo vazio e é: ", cls.running_loop.get())
            cls.register_log(f"logo antes do shutdown_lock no autoShutdown")
            with cls.shutdown_lock:
                cls.register_log(f"logo depois do shutdown_lock no autoShutdown")
                cls.shutDownComplete.clear()  # reset the event before shutdown
                # Shutdown async tasks
                # Shutdown threads
                cls.register_log("iniciating thread shutdown", "general")
                cls.thread_shutdown_function()
                # cls.set_loop() # ensure the loop is set
            if cls._loop_is_ok():
                print("setando o stop do loop... boa sorte")
                try:
                    MyLoop.stop_loop()
                except Exception as e:
                    log_error_forensics_plus(e)
            else:
                print("loop is not ok right after thread shutdown!!!! ")
            print("Automatic shutdown complete.")
            atexit_manager.shutdown_finalized = True
            AtexitObserver.check(
                "autoShutdown_end"
            )  # checkpoint para monitorar fim do autoshutdown
        except Exception as e:
            AtexitObserver.check("autoShutdown_error")
            print("[autoShutdown] the exception is:", e)
            log_error_forensics_plus(e)
        finally:
            print("vou setar o shutdownComplete")
            ##### esse é  o lugar certo pro relatório quando eu quiser!
            cls.tasksMap.relatorio()
            cls.shutDownComplete.set()
            print("setei o shutdownComplete")
            AtexitObserver.check("autoShutdown_finally")
        # else:
        #     print("Shutdown already initiated.")

    @classmethod
    def waitMyShutdown(cls):
        """Função para esperar o shutdown ser completado"""
        try:
            AtexitObserver.check(
                "waitMyShutdown_init"
            )  # checkpoint para monitorar inicio do waitMyShutdown
            print("Waiting for shutdown to begin...")
            if cls.testing:  # for isolated tests only!
                wait_event(
                    cls.first_shutdown_event, "LifecycleMaster.first_shutdown_event"
                )
            else:
                cls.first_shutdown_event.wait()
            # AtexitObserver.register(cls.cleanup_manager.atexit_register)
            cls.register_log(
                "Shutdown event detected, proceeding with shutdown...", "general"
            )
            AtexitObserver.start_watchdog()
            cls.autoShutdown()
            AtexitObserver.check(
                "waitMyShutdown_end"
            )  # checkpoint para monitorar fim do waitMyShutdown
        except Exception as e:
            print("deu erro no waitMyShutdown e foi: ", e)
            log_error_forensics_plus(
                e,
                extra_message="[waitMyShutdown] ocorreu um erro inesperado durante o waitMyShutdown",
            )
            AtexitObserver.check("waitMyShutdown_error")
        finally:
            print("estou no finally do waitMyShutdown")
            if not cls.shutDownComplete.is_set():
                try:
                    wait_event(
                        cls.shutDownComplete, " LifecycleMaster.shutDownComplete event"
                    )
                except Exception as e:
                    print("deu ruim no evento shutdownComplete e foi:", e)
                    log_error_forensics_plus(e)
            else:
                print("shutdownComplete Event is set properly")

            logs = []
            for key in cls.logsMap:
                for event in cls.logsMap[key]:
                    logs.append(event)
            logs = sorted(logs, key=lambda x: x[0])
            last_time = 0
            print_detailed = "n"
            # print("logo antes do input o print_detailed é: ",print_detailed)
            # try:
            #     print_detailed = input("quer o log detalhado?(s/n)")
            # except Exception as e:
            #     print("deu erro no input e foi: ",e)
            if (
                print_detailed == "s"
            ):  #### desse jeito não printa o log inteiro do lifecycle
                for ev in logs:
                    if last_time == 0:
                        print(round(ev[0], 6), " - ", ev[1])
                        last_time = ev[0]
                    else:
                        delta = round(ev[0] - last_time, 6)
                        last_time = ev[0]
                        print(delta, " - ", ev[1])
                print("Shutdown complete.")

            CallRegistry.report()
            cls.byebye.set()
            AtexitObserver.check(
                "waitMyShutdown_finally"
            )  # checkpoint para monitorar fim do waitMyShutdown


    # -------------------------------
    # Wrappers de execução de coroutines
    # -------------------------------

    @classmethod
    def register_cleanup_function(
        cls, func, priority, name, register_in_atexit, args=(), kwargs={}
    ):
        cls.cleanup_manager.register_hook(
            func,
            priority=priority,
            name=name,
            register_in_atexit=register_in_atexit,
            args=args,
            kwargs=kwargs,
        )

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

    # @staticmethod
    # def schedule(fn, *args):
    #     """Agenda uma função sync no loop (thread-safe)"""
    #     return MyLoop.call_soon(fn, *args)

    # -------------------------------
    # Wrappers de controle do loop
    # -------------------------------

    # @staticmethod
    # def shutdown_loop(graceful=True):
    #     """Encerra o loop de forma segura"""
    #     return MyLoop.stop(graceful=graceful)

    @classmethod
    def prepare_dependencies(cls):
        # preparando as dependências para o lifecycle master
        cls.cleanup_manager.prepare_class(cls.register_log, cls)

        # setting up the register log functions
        MyLoop.set_register_log(cls.register_log)
        TrackedThread.set_register_log(cls.register_log)
        TrackedTask.set_register_log(cls.register_log)
        cls.tasksMap.set_register_log(cls.register_log)

        # setting up the maps
        TrackedThread.set_threadsMap(cls.threadsMap)
        TrackedTask.set_tasksMap(cls.tasksMap)
        MyLoop.set_tasksMap(cls.tasksMap)

        # setting up the cleanup events
        TrackedThread.set_default_cleanup_event(cls.shutdown_event)
        TrackedTask.set_default_cleanup_event(cls.shutdown_event)
        MyLoop.set_default_shutdown_event(cls.shutdown_event)
        cls.tasksMap.set_default_cleanup_event(cls.shutdown_event)

        # setting up the loop
        TrackedThread.set_running_loop(cls.running_loop)
        TrackedTask.set_running_loop(cls.running_loop)
        errorExtruture.set_lifecycle_master(cls, LoggerManager)
        errorExtruture.devMode = cls.devMode


LifecycleMaster.prepare_dependencies()

LifecycleMaster.register_cleanup_function(
    LoggerManager.stop_listener,
    priority=99,
    name="LoggerManager.stop_listener",
    register_in_atexit=True,
)
# print(f"vou setar o get do myLoop no get_loop do atexit e eles são: MyLoop.get={MyLoop.get} , atexit_manager.get_loop = {atexit_manager.get_loop}")
atexit_manager.get_loop = MyLoop.get
# print(f"agora o atexit_manager.get_loop é: {atexit_manager.get_loop}")
atexit_manager.log_error_forencis_plus = log_error_forensics_plus

threading.Thread(target=LifecycleMaster.waitMyShutdown).start()

# atexit_manager.shutdown_function = LifecycleMaster.autoShutdown


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
