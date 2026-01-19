import asyncio
from copy import copy
from datetime import datetime, timezone
from time import time
from PythonServer import serverConfig
from PythonSistemAutomation.watcher_utils.default_callback import default_callback, treat_key_as_string
from pynput import mouse, keyboard
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
logger = LoggerManager.get_logger(__name__)

class EventObserver:
    """
    Observes mouse and keyboard events and triggers a callback for each one.
    Supports macro recording and background mode.
    """
    def __init__(self,loop, system):
        self.loop = loop
        self.system = system
        self._on_event_callback = default_callback
        self.listener_mouse = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll,on_move=self._on_move)
        self.listener_keyboard = keyboard.Listener(on_press = self._on_press, on_release = self._on_release)
        self._current_macro = None
        self._pressed_keys = set()  # To keep track of pressed keys
        self.last_movement = datetime.now()
        self._callback_lock = asyncio.Semaphore(1) 
        
    async def _process_event(self, event):
        # print(f"[_process_event] event: {event}")
        async with self._callback_lock:
            try:
                if event["type"] == "keyboard":
                    convenientEventToCompare = (event["type"] ,event["key"].replace("Key.","") ,event["action"] )
                elif event["type"] == "mouse":
                    convenientEventToCompare = (event["type"] ,event["button"].replace("Button.","") ,event["action"],event['x'],event['y'] )
                if self.system.ExecutingMacro["value"] or convenientEventToCompare in self.system.controlsToIgnore:
                    # print("o controlstoIgnore logo antes de decidir sobre remover algo é: ",self.system.controlsToIgnore)
                    print(f"the controlsToIgnore are: ",self.system.controlsToIgnore)
                    if convenientEventToCompare in self.system.controlsToIgnore:
                        print(f"the event is a macro event and will not be sent it is:",convenientEventToCompare)
                        self.system.controlsToIgnore.remove(convenientEventToCompare)
                        # return 
                    else:
                        pass
                await self._on_event_callback(event, self.system)
            except Exception as e:
                logger.warning(f"Erro ao processar evento: {e}")
                logger.debug("Finished processing one event")


    def on_click_wrapper(self,x, y, button, pressed):

        task = asyncio.create_task(self._on_click(x, y, button, pressed),name = "_on_click_task")            
        print("Created on_click task and the name is: ")
        print(task.get_name())
    def use_on_event_callback(self, event):
        # print(f"[on_event_callback] for event: {event}")
        if self._on_event_callback is None:
            self._on_event_callback = default_callback
        
        def schedule():
            task = asyncio.create_task(self._process_event(event),name = "_process_event_task")
            print("Created _process_event_task and the name is:")
            print(task.get_name())
        self.loop.call_soon_threadsafe(schedule)
    
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
        self.use_on_event_callback(event)

    def _on_click(self, x, y, button, pressed):
        if pressed:
            event_type = 'press'
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
        self.listener_mouse.start()
        self.listener_keyboard.start()

    def stop(self):
        self.listener_mouse.stop()
        self.listener_keyboard.stop()
