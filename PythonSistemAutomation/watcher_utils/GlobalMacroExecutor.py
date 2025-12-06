import asyncio
from asyncio import QueueEmpty 
import json
import sys
from pathlib import Path
import time

from sharedResources.pythonLoggerSistem.logger import LoggerManager
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.generalUtils.aprint import aprint
from PythonSistemAutomation.watcher_utils.default_receiving_function import default_receiving_function

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
    _ExecutingMacro = {'value': False}
    _internalStartMacroTime = None
    _internalStopMacroTime = None
    _wait_for_server = False
    _stop_running_macro_flag = Flag(False)

    @classmethod
    def _reset_macro_state(cls):
        cls._stop_running_macro_flag.set_value(False)
        cls._internalStartMacroTime = None
        cls._internalStopMacroTime = None
        cls._wait_for_server = False
        cls._ExecutingMacro['value'] = False
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
        cls._task = asyncio.create_task(cls._executor_loop())
        print("[GlobalExecutor] Started (auto-start).")

    @classmethod
    async def stop(cls):
        """Para o loop global e aguarda conclusão das tarefas."""
        if not cls._running:
            return
        cls._running = False
        await cls._queue.join()  # Espera a fila esvaziar
        if cls._task:
            cls._task.cancel()
            try:
                await cls._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error stopping executor: {e}",e)
                print(f"[GlobalExecutor] Error stopping executor: {e}")
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
                command,scheduledTime = await cls._queue.get()
                if cls._stop_running_macro_flag.get_value():
                    print(f"quase executei o comando só que a flag ja estava True e o comando é:    {command} ")
                    cls._queue.task_done()
                    continue
                # timeWaitingInQueue.append(time.perf_counter() - scheduledTime)
                if command:
                    command_data = json.loads(command)
                else:
                    print("empty command received: ",command)
                    cls._queue.task_done()
                    continue

                time_it_should_take += command_data.get("deltaTime", 0)
                startingTimeOfEachCommand.append([time.perf_counter()])
                internalBefore = time.perf_counter()
                response  = await cls._execute_command(command)
                before, after , waitForServer = response
                if waitForServer is not None:
                    if waitForServer == "killmacro":
                        # Detectar killMacro
                        print("[Executor] KillMacro recebido. Limpando fila até EndMacro...")

                        # Limpar FIFO até achar EndMacro
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
                            except Exception:
                                # comando quebrado? ignora e continua
                                continue

                        # Resetar estados da macro
                        cls._wait_for_server = False
                        # cls._killed = True
                        print("[Executor] Macro cancelada com sucesso.")

                        cls._queue.task_done()   # dá task_done no comando KillMacro
                        continue  # volta ao topo sem executar nada

                    if cls._wait_for_server:
                        if waitForServer:
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
                    cls._internalStartMacroTime = time.perf_counter()
                elif command_data.get("action") == "endMacro":
                    cls._internalStopMacroTime = time.perf_counter()
                    if cls._internalStartMacroTime is not None:
                        try:
                            total_macro_time_really_taken = cls._internalStopMacroTime - cls._internalStartMacroTime
                            print(f"[GlobalExecutor] Macro execution time was: {total_macro_time_really_taken} seconds.")
                            print(f"[GlobalExecutor] Macro accumulated interaction time with the OS was: {macroAcumulatedInteractionWithSOTime} seconds.")
                            print(f"[GlobalExecutor] Time it Should Take was: {time_it_should_take} seconds.")
                            # print(f"[GlobalExecutor] Time spent waiting in queue was: {sum(timeWaitingInQueue)} seconds.")
                            print(f"[GlobalExecutor] Time spent executing internal processing was: {sum([t[1]-t[0] for t in internalTimeOfEachCommand])} seconds.")
                            # print("startedTime , dont remember, command, time waited in queue, internal processing time:")
                            # for index,timeRegistry in enumerate(startingTimeOfEachCommand):
                                # print(f"{index+1}, {timeRegistry[0]- cls._internalStartMacroTime}  {timeRegistry[1]}     {timeWaitingInQueue[index]}   {internalTimeOfEachCommand[index][1] - internalTimeOfEachCommand[index][0]}")
                                # print(f"{index+1} Command started at {timeRegistry[0]- cls._internalStartMacroTime} seconds. and ", timeRegistry[1], " and waited in queue for ", timeWaitingInQueue[index], " seconds.",f" took {internalTimeOfEachCommand[index][1] - internalTimeOfEachCommand[index][0]} seconds of internal processing time.")
                        except Exception as e:
                            LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error calculating macro times: {e}",e)
                            # print(f"[GlobalExecutor] Error calculating macro times: {e}")
                        time_it_should_take = 0.0
                        macroAcumulatedInteractionWithSOTime = 0.0
                        cls._reset_macro_state()
                    else:
                        LoggerManager.log_exception_with_context(f"[GlobalExecutor] endMacro received without a matching startMacro.")
                cls._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                LoggerManager.log_exception_with_context(f"[GlobalExecutor] Error executing command: {e}",e)
                print(f"[GlobalExecutor] Error executing command: {e}")

    @classmethod
    async def _execute_command(cls, command: dict):
        resp = await default_receiving_function(command, cls)
        before,after, waitForServer = resp.start_time, resp.endTime , resp.waitForServer
        return before,after, waitForServer