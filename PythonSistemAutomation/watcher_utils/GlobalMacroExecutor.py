import copy
from asyncio import QueueEmpty 
import warnings 
import asyncio
import time
import json

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))


from sharedResources.generalUtils.aprint import aprint
from PythonSistemAutomation.watcher_utils.default_receiving_function import default_receiving_function, exec_mouse_or_kb
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus

from sharedResources.lifecycle.shutdownMaster import LifecycleMaster

class Flag:
    def __init__(self,value):
        self.value = value
    def get_value(self):
        return self.value
    def set_value(self, value ):
        self.value = value 

class GlobalExecutor:
    _queue = asyncio.Queue()
    _running = False
    _task = None
    _controlsToIgnore = None
    # _ExecutingMacro = {'value': False}
    _ExecutingMacro = None
    _internalStartMacroTime = None
    _internalStopMacroTime = None
    _wait_for_server = False
    _stop_running_macro_flag = Flag(False)
    _pressed_keys = None
    _pressed_buttons  = None
    @classmethod
    def set_pressed(cls,pressed_keys, pressed_buttons):
        if cls._pressed_keys is None:
            # print("seeting _pressed_keys to: ",pressed_keys)
            cls._pressed_keys = pressed_keys
        if cls._pressed_buttons is None:
            cls._pressed_buttons = pressed_buttons

    
    @classmethod
    def umpress_keys(cls, controls_to_ignore = None):
        frozen_controls_to_ignore = copy.deepcopy(controls_to_ignore) 
        
        # if len(cls._pressed_keys)> 0:
        #     print("printing umpressed_keys")
        if cls._pressed_keys is not None and len(cls._pressed_keys)>0:
            for original_key in list(cls._pressed_keys):# formata e tenta desapertar o botão
                print("the original_key is: ",original_key)
                command = {
                    "key" : original_key, 
                    "action" : "release", 
                    "equipment" : "keyboard",
                    "deltaTime": 0}
                exec_mouse_or_kb(command,cls,frozen_controls_to_ignore)                
                cls._pressed_keys.discard(original_key)
                
        # if len(cls._pressed_buttons)>0:
        #     print("umpressing buttons")
        if cls._pressed_buttons is not None and len(cls._pressed_buttons)>0:
            for original_button in list(cls._pressed_buttons): # tenta apertar
                print("the button is originaly: ",original_button)
                command = {
                    "button" : original_button, 
                    "action" : "release", 
                    "equipment" : "mouse",
                    "deltaTime": 0}
                exec_mouse_or_kb(command,cls,frozen_controls_to_ignore)
                cls._pressed_buttons.discard(original_button)
                
    @classmethod
    def _reset_macro_state(cls):
        cls._stop_running_macro_flag.set_value(False)
        cls._internalStartMacroTime = None
        cls._internalStopMacroTime = None
        cls._wait_for_server = False
        cls._ExecutingMacro['value'] = False
        cls.umpress_keys(cls._controlsToIgnore)
        cls._controlsToIgnore.clear()
        print("[GlobalExecutor] Macro state reset.")

    @classmethod
    async def _clear_queue(cls):
        counter = 0
        canceledCommands =[]
        try:
            while True:
                item = cls._queue.get_nowait()
                counter+=1
                canceledCommands.append(item)
                print(f"cancelando o comando {item} , {counter} comandos cancelados")
                cls._queue.task_done()
        except asyncio.QueueEmpty:
                pass
        print(f"cancelei {counter} comandos")
        print(f"a lista de comandos é: {canceledCommands}")
    
  

    @classmethod
    async def enqueue(cls, command: dict,controlsToIgnore, ExecutingMacro):
        """
        Adiciona um comando à fila global.
        Se o executor não estiver rodando, inicia automaticamente.
        """
        if "killmacro" in str(command):
            print("killmacro received!")
            cls._stop_running_macro_flag.set_value(True)
            print("o valor da flag de parada foi setado e agora é: ",cls._stop_running_macro_flag.get_value() )
            await cls._clear_queue()
            # cls._reset_macro_state()
            print("kill macro executed successfully")
            return

        await cls._queue.put([command,time.perf_counter()])
        print(f"[GlobalExecutor] Enqueued: {command}")

        # Auto-start se ainda não estiver rodando
        if not cls._running:
            cls._controlsToIgnore = controlsToIgnore
            cls._ExecutingMacro = ExecutingMacro
            await cls._start()

    @classmethod
    async def _start(cls):
        """Inicia o loop de execução se ainda não estiver rodando."""
        if cls._running:
            return
        cls._running = True
        cls._task = LifecycleMaster.run_async(cls._executor_loop(),name = "GlobalExecutorLoopTask")
        # cls._task = asyncio.create_task(cls._executor_loop(),name = "GlobalExecutorLoopTask")
        print("created task and the name is: ",cls._task.get_name())
        print("[GlobalExecutor] Started (auto-start).")

    @classmethod
    async def stop(cls):
        """Para o loop global e aguarda conclusão das tarefas."""
        if not cls._running:
            return
        cls._running = False

        await cls._queue.join(timeout = 3)  # Espera a fila esvaziar
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[GlobalExecutor] Error stopping executor: {e}")
                log_error_forensics_plus(e)
                LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error stopping executor: {e}",e)
        cls._reset_macro_state()
        print("[GlobalExecutor] Stopped.")

    @classmethod
    async def _executor_loop(cls):
        """Loop global que consome comandos da fila."""
        print("[GlobalExecutor] Executor loop running.")
        # start_time = time.perf_counter()  # Marca o início do loop
        # last_command_time = start_time
        macroAcumulatedInteractionWithSOTime = 0.0
        internalTimeOfEachCommand = []
        time_it_should_take = 0.0
        startingTimeOfEachCommand = []
        # timeWaitingInQueue = []
        while cls._running:
            try:
                # command,scheduledTime = await cls._queue.get()
                try:
                    command, scheduledTime = await asyncio.wait_for(cls._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    print("tarefa do loop da macro cancelada, encerrando")
                    cls._reset_macro_state()
                    break
                if cls._stop_running_macro_flag.get_value():
                    print(f"quase executei o comando só que a flag ja estava True e o comando é:    {command} ")
                    cls._reset_macro_state()
                    cls._queue.task_done()
                    continue
                # timeWaitingInQueue.append(time.perf_counter() - scheduledTime)
                
                if command:
                    command_data = json.loads(command) if isinstance(command, str) else command
                    # command_data = json.loads(command)
                else:
                    print("empty command received: ",command)
                    cls._queue.task_done()
                    continue

                try:
                    time_it_should_take += command_data.get("deltaTime", 0)
                except Exception as e:
                    print("o command_data no momento da exceção é:",command_data)
                    print("a exceção é: ",e)
                    raise
                startingTimeOfEachCommand.append([time.perf_counter()])
                internalBefore = time.perf_counter()
                response  = await cls._execute_command(command)
                before, after , waitForServer = response
                if waitForServer is not None:
                    if waitForServer == "killmacro":
                        # Detectar killMacro
                        # cls.umpress_keys()
                        print("[Executor] KillMacro recebido. Limpando fila até EndMacro...")

                        # Limpar FIFO até achar EndMacro ou limpar a queue
                        while True:
                            try:
                                next_cmd = cls._queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break  # Nada mais para limpar

                            cls._queue.task_done()
                            try:
                                next_cmd_data = json.loads(next_cmd)
                                if next_cmd_data.get("type") == "EndMacro":
                                    print("[Executor] EndMacro encontrado. Macro finalizada.")
                                    break
                            except Exception as e:
                                # comando quebrado? ignora e continua
                                log_error_forensics_plus(e)
                                continue
                        
                        print("[Executor] Macro cancelada com sucesso.")
                        cls._queue.task_done()   # dá task_done no comando KillMacro
                        continue  # volta ao topo sem executar nada

                    if cls._wait_for_server: # se o watcher ja estava esperando
                        if waitForServer: # se o comando de esperar o server veio agora
                            print("waitForServer is already true but received the command again!")
                        else:
                            cls._wait_for_server = False
                            print("waitForServer is now False and the Macro will continue")    
                    else:    
                        if waitForServer:
                            print("waitForServer is now True... waiting")
                            cls._wait_for_server = True
                        else:
                            print("waitForServer is already False and received the command to make it false again")
                if cls._wait_for_server:
                    if waitForServer is None:
                        print("trying to execute commands while the server told us to wait!! ")
                        print(f"the command is: {command}")
                        raise Exception(f"trying to execute commands while the server told us to wait!!/n the command is: {command})")
                    cls._queue.task_done()
                    continue

                internalAfter = time.perf_counter()
                if before != after:
                    internalTimeOfEachCommand.append([internalBefore,internalAfter])
                    macroAcumulatedInteractionWithSOTime += (after - before)
                    startingTimeOfEachCommand[-1].append(" took " + str(after - before) + " seconds with the SO")
                    # print(f"[GlobalExecutor] Command executed. Initial time {before} and final time: {after} , it took {after - before} seconds to execute the command" )
                else:
                    startingTimeOfEachCommand.pop()  # Remove se não houve interação

                if command_data.get("action") == "startMacro":
                    cls.umpress_keys()
                    cls._internalStartMacroTime = time.perf_counter()
                elif command_data.get("action") == "endMacro":
                    cls.umpress_keys()
                    cls._internalStopMacroTime = time.perf_counter()
                    if cls._internalStartMacroTime is not None:
                        try:
                            total_macro_time_really_taken = cls._internalStopMacroTime - cls._internalStartMacroTime
                        
                        except Exception as e:
                            log_error_forensics_plus(e)
                            LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error calculating macro times: {e}",e)
                        
                        time_it_should_take = 0.0
                        macroAcumulatedInteractionWithSOTime = 0.0
                        cls._reset_macro_state()
                    else:
                        LoggerManager.log_exception_with_context(f"[GlobalExecutor] endMacro received without a matching startMacro.")
                cls._queue.task_done()
            except asyncio.CancelledError:
                warnings.warn(" GlobalExecutorLoopTask task cancelled!")
                cls._reset_macro_state()
                break
            except Exception as e:
                print(f"[GlobalExecutor] Error executing command: {e}")
                cls.umpress_keys()
                log_error_forensics_plus(e)
                LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error executing command: {e}",e)

    @classmethod
    async def _execute_command(cls, command: dict, frozen_controls_to_ignore = None):
        resp = await default_receiving_function(command, cls)
        before,after, waitForServer = resp.start_time, resp.endTime , resp.waitForServer
        return before,after, waitForServer