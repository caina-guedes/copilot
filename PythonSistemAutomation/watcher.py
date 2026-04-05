from collections import deque
import threading
import asyncio
import warnings
# from copy import copy
import time
from PythonServer import serverConfig
from PythonSistemAutomation.watcher_utils.default_callback import default_callback, treat_key_as_string
from pynput import mouse, keyboard

from PythonSistemAutomation.watcher_utils.windowWatcher.windowManager import WindowManager
from PythonSistemAutomation.watcher_utils.GlobalMacroExecutor import  GlobalExecutor
from PythonSistemAutomation.watcher_utils.pressed_key_tracker import SafePressedTracker
from sharedResources.generalUtils.wait_for_data import wait_for_data, WaitTimeoutError
from sharedResources.pythonLoggerSistem.logger import LoggerManager
# from sharedResources.generalUtils.aprint import aprint
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class
from sharedResources.lifecycle.stateManager import State
logger = LoggerManager.get_logger(__name__)
window = WindowManager()

import platform
OS_name = platform.system().lower()

##### tive que comentar esse monitor pq não está funcionando.
@monitor_class 
class EventObserver:
    """
    Observes mouse and keyboard events and triggers a callback for each one.
    Supports macro recording and background mode.
    """
    already_init = False
    # definition_thread = threading.current_thread().name
    
    # # @sys_monitor
    def __init__(self, system, sendingQueue = None):
        # controls for unique __init__ execution
        if self.__class__.already_init:
            warnings.warn("iniciando o eventObserver quando ja foi iniciado!")
            return
        self.__class__.already_init = True
        # ----------------
        
        self.sendingQueue = sendingQueue # queue for when this observer is beeing used in the same process as the server.py
        # --------------------

        
        self.show_macro_event = True # para debug de macro events

        self.system = system # referência para o sistema de automação, para acessar estados e configurações
        
        self._on_event_callback = default_callback
        

        #listeners
        self.listener_mouse = None
        self.listener_keyboard = None
        
        # to control pressed stuff
        self._pressed_keys = SafePressedTracker()
        self._pressed_buttons = SafePressedTracker()
        GlobalExecutor.set_pressed(self._pressed_keys,self._pressed_buttons)
        
        self.last_movement = time.perf_counter() # para controlar o delay mínimo entre movimentos do mouse

        self.listeners_running = False # flag para controlar o estado dos listeners
        
        self.buffer_task = None
        self.on_event_consumer_task = None
        self.event_queue = asyncio.Queue() # para liberar o listener e organizar o processamento inicial
        self.send_queue = asyncio.Queue() # para acumular os eventos ja preparados e enviar em bloco
        
        

        self.macro_commands_counter = 0
        ###### tenho que implementar esse dicionário e printar no lugar certo!
        self.counter        = {
            "total_events" :  0,
            "ignored_events": 0,
            "send_macro_events":0 ,
            "ignored_not_macro_events":0,
            "executing_macro_events":0,
            "not_executing_macro_events":0,
            "send_to_process_events":0,
            }
        self.events_from_macro = []
        # self.thread_do_start = None
        # self.thread_do_evento = None
    
    
    # @sys_monitor
    def should_process_event(self, event):
        # print(f"[_process_event] event: {event}")
        # async with self._callback_lock:
        if not event:
            return False
        try:
            self.counter["total_events"] += 1

            if self.system.ExecutingMacro["value"]:
                self.counter["executing_macro_events"] += 1 
            else:
                self.counter["not_executing_macro_events"] += 1
            
            if event["type"] == "keyboard":
                convenientEventToCompare = (event["type"] ,event["key"].replace("Key.","") ,event["action"] )
            elif event["type"] == "mouse":
                convenientEventToCompare = (event["type"] ,event["button"].replace("Button.","") ,event["action"],event['x'],event['y'] )
            if self.system.ExecutingMacro["value"] or convenientEventToCompare in self.system.controlsToIgnore:
                # print("o controlstoIgnore logo antes de decidir sobre remover algo é: ",self.system.controlsToIgnore)
                # print(f"the controlsToIgnore are: ",self.system.controlsToIgnore)

                if convenientEventToCompare in self.system.controlsToIgnore:
                    # print(f"the event is a macro event and will not be sent it is:",convenientEventToCompare)
                    # if convenientEventToCompare in self.system.controlsToIgnore:
                    try:
                        self.system.controlsToIgnore.remove(convenientEventToCompare)
                        self.events_from_macro.append(convenientEventToCompare)
                        
                        self.counter["send_macro_events"] += 1
                        return True

                    except:
                        ### é nesse ponto aqui que vem os acos da macro certinnho!!!!
                        self.counter["ignored_not_macro_events"] += 1

                self.counter["ignored_events"] +=1
                return False
            
            self.counter["send_to_process_events"] +=1
            return True

        except Exception as e:
            log_error_forensics_plus(e)
            # warnings.warn(f"[shoul_process_event] deu erro e foi{e}")
            # logger.warning(f"Erro ao processar evento: {e}")
            # logger.debug("Finished processing one event")
            # warnings.warn(e)

    # @sys_monitor
    async def _event_consumer(self): # primeiro loop
        """
        O único trabalhador: processa a fila um por um.
        Primeiro loop
        """
        print(" Consumer Task iniciada.")
        self.thread_do_consumer = threading.current_thread().name
        while self.listeners_running or self.system.lifeCycleMaster.lifecycleState.state is State.RUNNING:
            try:
                # Espera o próximo evento sem bloquear o loop
                try:
                    event = await wait_for_data(self.event_queue, timeout=0.5)
                except WaitTimeoutError:
                    continue
                
                chegou_da_queue = time.perf_counter()
                # event['timestamp'] = event['timestamp']
                # print(f"thread da definição da classe é: {self.__class__.definition_thread}")
                # print(f"thread do init da classe é: {self.init_thread}")
                # print(f"thread do start: {self.thread_do_start}")
                # print(f"thread do evento: {self.thread_do_evento}")
                # print(f"thread do consumer: {self.thread_do_consumer}")


                if self.should_process_event(event):
                    logo_antes_de_verificar_janela = time.perf_counter()

                    try:
                        currentWindow, changed , os_call= window.get_active_window(event,SafePressedTracker.get_global_pressed()) # aqui tem que ser o global pressed 
                        logo_depois_de_verificar_janela = time.perf_counter()
                        if changed:
                            # print("houve atualização de janela!!!")
                            event["windowChange"] = True
                            event["newCurrentWindow"] = currentWindow.to_dict()
                        else:
                            event["windowChange"] = False
                    except Exception as e:
                        event["windowChange"] = False
                        log_error_forensics_plus(e)
                        logo_depois_de_verificar_janela = logo_antes_de_verificar_janela
                    
                    logo_antes_de_enviar = time.perf_counter()

                    LifecycleMaster.call_soon(
                        self.send_queue.put_nowait, 
                        event
                        )
                    # depois_de_enviar = time.perf_counter()
                    # total_time = depois_de_enviar -event["timestamp"]
                    # time_to_verify_window = logo_depois_de_verificar_janela - logo_antes_de_verificar_janela 
                    # time_to_send = depois_de_enviar - logo_antes_de_enviar
                    # print(f"event {event} ")
                    # print(f"took {chegou_da_queue - inicio} in the queue")
                    # print(f"took  {logo_antes_de_verificar_janela - chegou_da_queue} to decide to send it")
                    # print(f"took {time_to_verify_window} to {'not' if not os_call else 'really'} verify window, ")
                    # print(f"took {time_to_send}  to send event !!!")
                    # print(f" took total time : {total_time }")
                    # print(f"of that {(time_to_send/total_time)*100} % is just to send ")
                    # print(f"of that {(time_to_verify_window/total_time)*100} % is just to verify window")
                self.event_queue.task_done()
            except asyncio.CancelledError:
                print(" primeiro loop cancelado")
                break
            except Exception as e:
                log_error_forensics_plus(e)

    def put_in_queue(self, event):
        """
        Rápido como um raio: apenas coloca na fila.
        Não cria tasks, não acessa o Monitor.
        """
        # Filtro Síncrono (Opcional, mas recomendado para performance)
        # Se for macro, você pode dar return aqui e nem sujar a fila
        # if self.thread_do_evento is None:
        #     self.thread_do_evento = threading.current_thread().name
    
        # resp = (event,time.perf_counter())
        LifecycleMaster.call_soon(
            self.event_queue.put_nowait, 
            event
            )

    
    # @sys_monitor
    def _on_move(self, x, y, injected):
        if injected:
            # print(f"move enviado por software!({x}, {y}) ")
            if OS_name != "windows":
                return
            else:
                # self.macro_commands_counter +=1
                if self.show_macro_event:
                    print(f"macro event detected  move {x},{y}")
                GlobalExecutor.increase_executed_macro_commands()
        
        from PythonSistemAutomation.main import AutomationSystem
        now = time.time()
        if (now - self.last_movement ) < serverConfig.mouseMovementMinimumDelay or not AutomationSystem.config.send_position:
            return
        self.last_movement = now
        event = {
            # 'timestamp': datetime.now(timezone.utc).isoformat(),
            'timestamp': now,
            'type': 'mouse',
            'action': 'move',
            'position': (x, y)
        }
        
        # self.put_in_queue(event)
    # @sys_monitor
    def _on_click(self, x, y, button, pressed, injected):
        if injected:
            # print(f"click enviado por software!({x}, {y}) ")
            if OS_name != "windows":
                return
            else:
                # self.macro_commands_counter +=1
                if self.show_macro_event:
                    print(f"macro event detected x= {x}, y= {y}, pressed = {pressed}")
                GlobalExecutor.increase_executed_macro_commands()
        if pressed:
            event_type = 'press'
            self._pressed_buttons.add(str(button))
        else:
            self._pressed_buttons.remove(str(button))
            event_type = 'release'
        event = {
            'timestamp' : time.time(),
            'type'  : "mouse",
            'action': event_type,   
             'x'    : x, 
             "y"    : y,
            'button': str(button),
        }
        self.put_in_queue(event)

    # @sys_monitor
    def _on_scroll(self, x, y, dx, dy,injected):
        if injected:
            # print(f"scroll enviado por software!({x} ,{y}, {dx}, {dy}) ")
            if OS_name != "windows":
                return
            else:
                # self.macro_commands_counter +=1
                if self.show_macro_event:
                    print(f"macro event detected scroll x= {x}, y={y}, dx={dx}, dy={dy}")
                GlobalExecutor.increase_executed_macro_commands()
        event = {
            # 'timestamp':datetime.now(timezone.utc).isoformat(),
            'timestamp':time.time(),
            'type': 'mouse',
            'action': 'scroll',
            'position': {'x': x, 'y': y},
            'delta': {'dx': dx, 'dy': dy}
        }
        self.put_in_queue(event)
    
    # @sys_monitor
    def _on_press(self, key,injected):
        if injected:
            # print(f"press enviado por software( {key})")
            if OS_name != "windows":
                return 
            else:
                # self.macro_commands_counter +=1
                if self.show_macro_event:
                    print(f"macro event detected press key = {key}")
                GlobalExecutor.increase_executed_macro_commands()
        from PythonSistemAutomation.main import AutomationSystem
        key = treat_key_as_string(key)
        event = {
            # 'timestamp':datetime.now(timezone.utc).isoformat(),
            'timestamp':time.time(),
            'type': 'keyboard',
            'action': 'press',
            'key': key
        }

        if AutomationSystem.config.dont_want_repetition() and self._pressed_keys.is_pressed(key):
            return # ignoring duplicate key presses
        
        if self._pressed_keys.add(key):
            pass # aqui ele ainda não estava pressionado
        if key == AutomationSystem.config.toggleRecordKey:
            print("toggleRecording")
            # event["action"] = "toggleRecording"
            # aqui eu mando o tempo do evento do frontend pro backend, 
            # pra ter uma base de comparação e evitar problemas de timestamp 
            # vindo do OS watcher e do frontend
            event['details'] = {"MacroTime": int(time.time() * 1000)} 
        if key == AutomationSystem.config.ExecutaMacroKey:
            # print("ExecuteMacro")
            # event["action"] = "ExecCurrentMacro"
            event['details'] = {"RequestToExecuteMacro": True}

        if key == AutomationSystem.config.stopKey:
            print("Stop key pressed. but stopping command is comment for now")
            logger.info("Stop key pressed. Stopping observer.")
        
        
        self.put_in_queue(event)
                
    # @sys_monitor
    def _on_release(self, key,injected):
        if injected:
            # print(f"release enviado por software!({key})")
            if OS_name != "windows":
                return
            else:
                # self.macro_commands_counter +=1
                if self.show_macro_event:
                    print(f"macro event detected release key = {key}")

                GlobalExecutor.increase_executed_macro_commands()
        key = treat_key_as_string(key)
        event = {
            # 'timestamp':datetime.now(timezone.utc).isoformat(),
            'timestamp':time.time(),
            'type': 'keyboard',
            'action': 'release',
            'key': key
        }
        if self._pressed_keys.remove(key):
            pass
        self.put_in_queue(event)
        # else:## this case is an eco!!!!
        #     print("this eent is a eco: ",event)
        


    # @monitor_error
    async def buffer_loop(self): #segundo loop
        """
        Segundo estágio: Agrupa eventos da 'send_queue' e despacha em lotes.
        """
        print(" tarefa iniciada!")
        MAX_BATCH_SIZE = 50
        buffer = deque(maxlen=1000) 
        # buffer = []
        MAX_WAIT_TIME = 0.2  # 100ms de janela de agrupamento

        while self.listeners_running or self.system.lifeCycleMaster.lifecycleState.state is State.RUNNING:
            try:
                # 1. Espera o PRIMEIRO evento do lote (fica dormindo aqui até chegar algo)
                try:
                    event = await wait_for_data(self.send_queue, timeout=0.5)
                except WaitTimeoutError:
                    continue

                buffer.append(event)
                
                # 2. Assim que o primeiro chega, iniciamos a contagem do timer
                start_time = asyncio.get_running_loop().time()
                
                # 3. Tenta coletar o máximo possível nos próximos 100ms
                while len(buffer) < MAX_BATCH_SIZE:
                    #calcula o tempo que ja passou
                    time_already_passed = asyncio.get_running_loop().time() - start_time
                    if time_already_passed >= MAX_WAIT_TIME:
                        break
                    remaining_time = MAX_WAIT_TIME - time_already_passed
                    
                    try:
                        # Tenta pegar mais sem bloquear o loop por muito tempo
                        event = await wait_for_data(self.send_queue, timeout=remaining_time)
                        buffer.append(event)
                    except WaitTimeoutError:
                        break  # Timer estourou, hora de enviar o que temos
                    
                # 4. Envia o Lote (Aqui você pode dar await sem medo)
                if buffer:
                    # print(f"Enviando lote de {len(buffer)} eventos...")
                    confirmation,time_taken = await self._on_event_callback(list(buffer), self.system, self.sendingQueue)
                    for _ in range(len(buffer)):
                        self.send_queue.task_done()
                    if confirmation:
                        # print("envio confirmado, o tempo de envio foi: ",time_taken)
                        for _ in range(len(buffer)):
                            if buffer: buffer.popleft()
            except asyncio.CancelledError:
                print(" segundo loop cancelado")
            except Exception as e:
                print(f"Erro no loop de rede: {e}")
                log_error_forensics_plus(e)
                warnings.warn(e)

    def start(self): # inicia os listeners
        
        if self.listeners_running:# pra previnir reentrada!
            print("tentando iniciar os listeners no observer quando eles ja foram iniciados!")
            return
        else:
            self.listeners_running = True
            self.listener_mouse    = mouse.Listener(on_click    = self._on_click, on_scroll  = self._on_scroll,on_move=self._on_move)
            self.listener_keyboard = keyboard.Listener(on_press = self._on_press, on_release = self._on_release)
        
            self.listener_mouse.start()
            self.listener_keyboard.start()
            print(" called start!")
            if self.buffer_task is None:
                # só acontece no primeiro init e fica ate  a finalização do programa
                self.buffer_task = LifecycleMaster.run_async(self.buffer_loop(),name = "loop do buffer do observer- segundo loop")
            
            if self.on_event_consumer_task is None:
                # só acontece no primeiro init e fica ate  a finalização do programa
                self.on_event_consumer_task = LifecycleMaster.run_async(self._event_consumer(),name = "on_event_consumer - primeiro loop")
            
            # print(f"o tipo do self.on_event_consumer_task é: {type(self.on_event_consumer_task)}")
            # print(f" e o self.on_event_consumer_task em si é: {self.on_event_consumer_task}")
            # # self.thread_do_start = threading.current_thread().name
    
    def stop(self): # para os listeners e atualmente imprime um relatório
        print(" stop observer called ")
        if not self.listeners_running:
            print("os listeners do observer já estão parados!")
            return
        inicio = time.perf_counter()
        
        self.listener_mouse.stop()
        listener_mouse_stopped_time = time.perf_counter()
        # print(f"Tempo de parada do listener_mouse: {listener_mouse_stopped_time - inicio}")
        
        self.listener_mouse.join()
        listener_mouse_joined_time = time.perf_counter()
        # print(f"Tempo de join do listener_mouse: {listener_mouse_joined_time - inicio}")
        
        inicio_do_keyboard_stop = time.perf_counter()
        self.listener_keyboard.stop()
        listener_keyboard_stopped_time = time.perf_counter()
        # print(f"Tempo de parada do listener_keyboard: {listener_keyboard_stopped_time - inicio_do_keyboard_stop}")
        
        self.listener_keyboard.join()
        listener_keyboard_joined_time = time.perf_counter()
        # print(f"Tempo de join do listener_keyboard: {listener_keyboard_joined_time - inicio_do_keyboard_stop}")
        
        # LifecycleMaster.cancel_tracked_task_(self.on_event_consumer_task)
        # LifecycleMaster.cancel_tracked_task_(self.buffer_task)
        
        self.listeners_running = False
        # for metric in self.counter:
        #     print(metric)
        #     if isinstance(self.counter[metric],int ):
        #         print(self.counter[metric])
        #     else:
        #         print(len(self.counter[metric]))
        #         for ev in self.counter[metric]:
        #             print(ev)
        # print("macro events not send:")
        # for ev in self.events_from_macro:
        #     print(ev)


    