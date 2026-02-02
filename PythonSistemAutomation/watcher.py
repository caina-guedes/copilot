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
    def __init__(self, system):
        if self.__class__.already_init:
            warnings.warn("iniciando o eventObserver quando ja foi iniciado!")
            return
        already_init = True
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
        ###### tenho que implementar esse dicionário e printar no lugar certo!
        self.counter        = {
            "ignored_events":0,
            "ignored_macro_events":0 ,
            "executing_macro_events":0,
            "not_executing_macro_events":0,
            "send_to_process_events":0,
            }
        # self.ignored_events_counter = 0
        # self.ignored_macro_events_counter = 0 

    def _process_event(self, event):
        # print(f"[_process_event] event: {event}")
        # async with self._callback_lock:
        try:
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

                self.counter["ignored_events"] += 1
                if convenientEventToCompare in self.system.controlsToIgnore:
                    print(f"the event is a macro event and will not be sent it is:",convenientEventToCompare)
                    
                    self.system.controlsToIgnore.discard(convenientEventToCompare)
                    
                    self.counter["ignored_macro_events"] += 1
                #     print(" o contador de eventos ignorados do watcher está em: " , self.counter["ignored_macro_events"] )
                #     print("e o contador de chamadas do process_event é: " , self.counter["ignored_events"])
                return 
                # else:
                #     pass
            self.counter["send_to_process_events"] +=1 
            LifecycleMaster.run_async(self._on_event_callback(event, self.system),name = "_process_real_event")

            # await self._on_event_callback(event, self.system)
        except Exception as e:
            logger.warning(f"Erro ao processar evento: {e}")
            logger.debug("Finished processing one event")
            warnings.warn(e)


    def use_on_event_callback(self, event):
        # print(f"[on_event_callback] for event: {event}")
        if self._on_event_callback is None:
            self._on_event_callback = default_callback
        
        self._process_event(event)
        # LifecycleMaster.run_async(self._process_event(event),name = "_process_event")

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
        
        # self.use_on_event_callback(event)

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
        self.use_on_event_callback(event)

    def _on_scroll(self, x, y, dx, dy):
        event = {
            'timestamp':datetime.now(timezone.utc).isoformat(),
            'type': 'mouse',
            'action': 'scroll',
            'position': {'x': x, 'y': y},
            'delta': {'dx': dx, 'dy': dy}
        }
        self.use_on_event_callback(event)

        
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

        self.use_on_event_callback(event)

        
        if key == AutomationSystem.config.stopKey:
            print("Stop key pressed. but stopping command is comment for now")
            logger.info("Stop key pressed. Stopping observer.")
            # self.stop()
        
            
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
        
        self.use_on_event_callback(event)

    def set_event_callback(self,callback):
        """Defines the function that will be called for each captured event."""
        logger.info(f"Setting event callback: {callback}")
        self._on_event_callback = callback

    def start(self):
        if self.listeners_running:# pra previnir reentrada!
            warnings.warn("tentando iniciar os listeners no observer quando eles ja foram iniciados!")
            return
        else:
            self.listeners_running = True
            self.listener_mouse.start()
            self.listener_keyboard.start()

    def stop(self):
        print("[EventObserver]stop called ")
        self.listener_mouse.stop()
        self.listener_keyboard.stop()
        for counter in self.counter:
            print(counter,"  ",self.counter[counter])
