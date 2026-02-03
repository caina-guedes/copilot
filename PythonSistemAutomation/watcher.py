import threading
import asyncio
import warnings
from copy import copy
from datetime import datetime, timezone
from time import time
from PythonServer import serverConfig
from PythonSistemAutomation.watcher_utils.default_callback import default_callback, treat_key_as_string
from pynput import mouse, keyboard

from PythonSistemAutomation.watcher_utils.GlobalMacroExecutor import  GlobalExecutor
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
logger = LoggerManager.get_logger(__name__)

class EventObserver:
    """
    Observes mouse and keyboard events and triggers a callback for each one.
    Supports macro recording and background mode.
    """
    already_init = False
    definition_thread = threading.current_thread().name
    def __init__(self, system):
        if self.__class__.already_init:
            warnings.warn("iniciando o eventObserver quando ja foi iniciado!")
            return
        already_init = True
        self.init_thread = threading.current_thread().name
        self.system = system
        self._on_event_callback = default_callback
        self.listener_mouse = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll,on_move=self._on_move)
        self.listener_keyboard = keyboard.Listener(on_press = self._on_press, on_release = self._on_release)
        self._current_macro = None
        self._pressed_keys = set()  # To keep track of pressed keys
        self._pressed_buttons = set()
        GlobalExecutor.set_pressed(self._pressed_keys,self._pressed_buttons)
        self.last_movement = datetime.now()
        self._callback_lock = asyncio.Semaphore(20) 
        self.listeners_running = False
        self.event_queue = asyncio.Queue() # para liberar o listener e organizar o processamento
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
        self.thread_do_start = None
        self.thread_do_evento = None
    
    def should_process_event(self, event):
        # print(f"[_process_event] event: {event}")
        # async with self._callback_lock:
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
                    print(f"the event is a macro event and will not be sent it is:",convenientEventToCompare)
                    # if convenientEventToCompare in self.system.controlsToIgnore:
                    try:
                        self.system.controlsToIgnore.remove(convenientEventToCompare)
                        self.events_from_macro.append(convenientEventToCompare)
                        self.counter["send_macro_events"] += 1
                        return True
                        # await self._on_event_callback(event, self.system)

                    except:
                        self.counter["ignored_not_macro_events"] += 1

                self.counter["ignored_events"] +=1
                return False
            
            self.counter["send_to_process_events"] +=1
            return True
            # self._on_event_callback(event, self.system)

        except Exception as e:
            warnings.warn(f"[shoul_process_event] deu erro e foi{e}")
            logger.warning(f"Erro ao processar evento: {e}")
            logger.debug("Finished processing one event")
            warnings.warn(e)


    async def _event_consumer(self):
        """
        O único trabalhador: processa a fila um por um.
        """
        print("[EventObserver] Consumer Task iniciada.")
        self.thread_do_consumer = threading.current_thread().name
        while self.listeners_running:
            try:
                # Espera o próximo evento sem bloquear o loop
                event , inicio = await self.event_queue.get()
                chegou_da_queue = time()
                # print(f"thread da definição da classe é: {self.__class__.definition_thread}")
                # print(f"thread do init da classe é: {self.init_thread}")
                # print(f"thread do start: {self.thread_do_start}")
                # print(f"thread do evento: {self.thread_do_evento}")
                # print(f"thread do consumer: {self.thread_do_consumer}")


                if self.should_process_event(event):
                    logo_antes_de_enviar = time()
                    await self._on_event_callback(event, self.system)
                    depois_de_enviar = time()
                    print(f"event {event} ")
                    print(f"took {chegou_da_queue - inicio} in the queue")
                    print(f"took  {logo_antes_de_enviar - chegou_da_queue} to decide to send it")
                    time_to_send = depois_de_enviar - logo_antes_de_enviar
                    print(f"took {time_to_send}  to send event !!!")
                    total_time = depois_de_enviar -inicio
                    print(f" took total time : {total_time }")
                    print(f"of that {(time_to_send/total_time)*100} % is just to send ")
                self.event_queue.task_done()
            except Exception as e:
                warnings.warn(str(e))

    def put_in_queue(self, event):
        """
        Rápido como um raio: apenas coloca na fila.
        Não cria tasks, não acessa o Monitor.
        """
        # Filtro Síncrono (Opcional, mas recomendado para performance)
        # Se for macro, você pode dar return aqui e nem sujar a fila
        if self.thread_do_evento is None:
            self.thread_do_evento = threading.current_thread().name
    
        resp = (event,time())
        LifecycleMaster.call_soon(
            self.event_queue.put_nowait, 
            resp
            )

    def add_event(self, event):
        if self._current_macro is None:
            self._current_macro = copy([])
        if isinstance(event, dict):
            self._current_macro.append(event)
        else:
            logger.info("Event must be a dict and is : ",type(event), " and the value is : ", event)

    def get_current_macro(self):
        return self._current_macro if self._current_macro is not None else copy([])
    
    def clear_current_macro(self):
        self._current_macro = None
        
    def _on_move(self, x, y):
        from PythonSistemAutomation.main import AutomationSystem
        if (datetime.now() - self.last_movement ).total_seconds() < serverConfig.mouseMovementMinimumDelay or not AutomationSystem.config.send_position:
            return
        self.last_movement = datetime.now()
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': 'mouse',
            'action': 'move',
            'position': (x, y)
        }
        
        # self.put_in_queue(event)

    def _on_click(self, x, y, button, pressed):
        if pressed:
            event_type = 'press'
            self._pressed_buttons.add(str(button))
        else:
            event_type = 'release'
        event = {
            'timestamp' : datetime.now(timezone.utc).isoformat(),
            'type'  : "mouse",
            'action': event_type,   
             'x'    : x, 
             "y"    : y,
            'button': str(button),
        }
        self.put_in_queue(event)

    def _on_scroll(self, x, y, dx, dy):
        event = {
            'timestamp':datetime.now(timezone.utc).isoformat(),
            'type': 'mouse',
            'action': 'scroll',
            'position': {'x': x, 'y': y},
            'delta': {'dx': dx, 'dy': dy}
        }
        self.put_in_queue(event)

        
    def _on_press(self, key):
        from PythonSistemAutomation.main import AutomationSystem
        key = treat_key_as_string(key)
        event = {
            'timestamp':datetime.now(timezone.utc).isoformat(),
            'type': 'keyboard',
            'action': 'press',
            'key': key
        }

        if AutomationSystem.config.dont_want_repetition() and key in self._pressed_keys:
            return # ignoring duplicate key presses
        
        self._pressed_keys.add(key)
        
        if key == AutomationSystem.config.toggleRecordKey:
            print("toggleRecording")
            # event["action"] = "toggleRecording"
            event['details'] = {"MacroTime": int(time()* 1000)}
        if key == AutomationSystem.config.ExecutaMacroKey:
            # print("ExecuteMacro")
            # event["action"] = "ExecCurrentMacro"
            event['details'] = {"RequestToExecuteMacro": True}

        self.put_in_queue(event)

        
        if key == AutomationSystem.config.stopKey:
            print("Stop key pressed. but stopping command is comment for now")
            logger.info("Stop key pressed. Stopping observer.")
        
            
    def _on_release(self, key):
        key = treat_key_as_string(key)
        event = {
            'timestamp':datetime.now(timezone.utc).isoformat(),
            'type': 'keyboard',
            'action': 'release',
            'key': key
        }
        if key in self._pressed_keys:
            self._pressed_keys.remove(key)
        else:
            logger.info(f"Attempting to release a key that was not pressed: {key}")
        
        self.put_in_queue(event)

    def set_event_callback(self,callback):
        """Defines the function that will be called for each captured event."""
        logger.info(f"Setting event callback: {callback}")
        self._on_event_callback = callback


    def start(self):
        if self._on_event_callback is None:
            self.set_event_callback(default_callback)

        if self.listeners_running:# pra previnir reentrada!
            warnings.warn("tentando iniciar os listeners no observer quando eles ja foram iniciados!")
            return
        else:
            self.listeners_running = True
            self.listener_mouse.start()
            self.listener_keyboard.start()
            self.on_event_consumer_task = LifecycleMaster.run_async(self._event_consumer,name = "on_event_consumer")
            print(f"o tipo do self.on_event_consumer_task é: {type(self.on_event_consumer_task)}")
            print(f" e o self.on_event_consumer_task em si é: {self.on_event_consumer_task}")
            self.thread_do_start = threading.current_thread().name
    
    def stop(self):
        print("[EventObserver]stop called ")
        self.listener_mouse.stop()
        self.listener_keyboard.stop()
        for metric in self.counter:
            print(metric)
            if isinstance(self.counter[metric],int ):
                print(self.counter[metric])
            else:
                print(len(self.counter[metric]))
                for ev in self.counter[metric]:
                    print(ev)
        print("macro events not send:")
        for ev in self.events_from_macro:
            print(ev)
