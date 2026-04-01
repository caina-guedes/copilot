import asyncio
import json
import time
import pynput
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
import warnings
import sys
from pathlib import Path

# from rich.live import source
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.generalUtils.aprint import aprint
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor
from sharedResources.pythonLoggerSistem.logger import LoggerManager

keyboard = KeyboardController()
mouse    = MouseController()

class InadequateMessage(Exception):
    def __init__(self, msg, motherFunction):
        super().__init__(f"Mensagem inadequada ({msg}) para a função {motherFunction}")
        self.msg = msg
        self.motherFunction = motherFunction


# @sys_monitor
def mouseExecCommand(message, action, controlsToIgnore):
    print(f"vou executar um comando de mouse e é: {message}")
    if 'button' not in message:
        raise InadequateMessage(str(message) + " - button key not found in this message", "mouseExecCommand")
    
    button = message["button"][7:] if 'button.' in message['button'].lower() else message['button'] 
    action = message["action"]
    event = (
    "mouse",
    button,
    action, 
    message.get("x",None), 
    message.get("y",None)
    )
    if controlsToIgnore is not None:
        controlsToIgnore.add(event)

    before = time.perf_counter()
    if "x" in message and "y" in message:
        x = message["x"]
        y = message["y"]
        mouse.position = (x, y)
        # print(f"Mouse moved to ({x}, {y})")
    try:
        real_button = getattr(Button, button)
    except AttributeError:
        raise InadequateMessage(str(message) + f" - button {button} not recognized", "mouseExecCommand")
   
    if action == "click":
        mouse.click(real_button,1)
        print(f"Mouse clicked {button} button")
    elif action == "double_click":
        mouse.click(real_button,2)
        print(f"Mouse double clicked {button} button")
    elif action == "press":
        mouse.press(real_button)
        print(f"Mouse button {button} pressed")
    elif action == "release":
        mouse.release(real_button)
        print(f"Mouse button {button} released")
    elif action in  ["roll","scroll"]:
        delta = message.get("delta", 0)
        mouse.scroll(0, delta)
        print(f"Mouse scrolled with delta {delta}")
    else:
        print(f"action {action} not recognized for mouse")
    
    after = time.perf_counter()

    return (before,after)

# @sys_monitor
def kbPressOrRelease(message, action, controlsToIgnore):
    if 'key' not in message:
        raise InadequateMessage(str(message) + " - key keyword not found this message", "kbPressOrRelease")
    
    key_name = message['key'][4:] if 'key.' in message['key'].lower() else message['key']

    if hasattr(Key, key_name):
        key = getattr(Key, key_name)
    elif key_name.isupper():
            print("the key is uppercase, pressing shift too")
            if controlsToIgnore is not None:
                controlsToIgnore.update([
                ("keyboard", Key.shift, "press" ),
                ("keyboard", Key.shift, "release")
                ])
            with keyboard.press(Key.shift):
                before,after = kbPressOrRelease(key_name.lower(),action,controlsToIgnore)
                return before,after
    else:
        key = key_name
    if controlsToIgnore is not None:
        controlsToIgnore.add((
        "keyboard",
        str(key).replace("Key.",""),
        action
        ))
    try:
        before = time.perf_counter()
        # print("Executing keyboard action:", action, "for key:", key_name)
        if action == "press":
            keyboard.press(key)
        elif action == "release":
            keyboard.release(key)
        else:
            print(f"action {action} not recognized for keyboard")
            # raise InadequateMessage(str(message) + f" - action {action} not recognized for keyboard", "kbPressOrRelease")
        
        after = time.perf_counter()
        print("Executed keyboard action: ", action, " for key: ", key," and the key type is: ",type(key))
        return (before, after)
    except pynput.keyboard._base.Controller.InvalidKeyException as e:
        raise InadequateMessage(str(message) + " foi no pynput.keyboard._base.Controller.InvalidKeyException - " + str(e),"kbPressOrRelease")
    except ValueError as e:
        raise InadequateMessage(str(message) + " foi no ValueError " + str(e),"kbPressOrRelease")
    except Exception as e:
        
        print(f"Error processing keyboard action {action} for key {key_name}: {e}")
        log_error_forensics_plus(e)

class  InternalResponse:
    def __init__(self,start_time,endTime,waitForServer = None):
        self.start_time = start_time
        self.endTime = endTime
        self.waitForServer = waitForServer



# @sys_monitor
def exec_mouse_or_kb(message, macroExecutor,frozen_controls_to_ignore = None ):
    if isinstance(message, str): 
        message = json.loads(message)

    controlsToIgnore = frozen_controls_to_ignore or macroExecutor._controlsToIgnore
        # controlsToIgnore = frozen_controls_to_ignore or macroExecutor._controlsToIgnore
    if controlsToIgnore is None :
        print(" controlsToIgnore to ignore is none inside ")
        print(f" the message received here is: {message}")
    if message is None:
        print("Received None message, ignoring but maybe the connection has ended")
        return InternalResponse(0,0)

    action   = message['action']
    ExecutingMacro   = macroExecutor._ExecutingMacro

    if action == "endMacro":
        ExecutingMacro["value"] = False
        # como colocar a função umpress aqui? 
        print("Macro execution ended.")
        return InternalResponse(0,0)

    elif action == "startMacro":
        ExecutingMacro["value"] = True
        print("Macro execution started.") 
        return InternalResponse(0,0)

    elif action == "WaitForServer":
        return InternalResponse(0,0,True)
    
    elif action == "continueMacro":
        return InternalResponse(0,0,False)

    elif action not in ["press","release","click","double_click","scroll","move"]:
        print(f"action {action} not recognized, will be ignored")
        return InternalResponse(0,0)
        
    equipment = message["equipment"].lower()
    if equipment == "keyboard":
        try:
            before,after = kbPressOrRelease(message, action, controlsToIgnore)
    
            return InternalResponse(before,after)
        
        except InadequateMessage as im:
            raise im
        except Exception as e:
            print(f"Error processing keyboard command: {e}")
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"Error processing keyboard command: {e}",e)

    elif equipment == "mouse":
        try:
            before,after = mouseExecCommand(message, action, controlsToIgnore)
    
            return InternalResponse(before,after)

        except InadequateMessage as im:
            raise im

        except Exception as e:
            print(f"Error processing mouse command: {e}")
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"Error processing mouse command: {e}",e)

    else:
        print(f"equipment {equipment} not recognized")
        1/0
        # LoggerManager.log_exception_with_context(f"equipment {equipment} not recognized")


    return InternalResponse(0,0)

@sys_monitor
async def default_receiving_function(message, macroExecutor,frozen_controls_to_ignore = None ):
    """
    this functions needs the message to be [deltaTime,[equipment,action,key],modifiers]
    """
    try:
        if isinstance(message, str): 
            message = json.loads(message)
            # pass
        if "deltaTime" in message:
            timeToWait = message['deltaTime']
            # loop_time = asyncio.get_running_loop().time()
            # print(f" Aguardando {timeToWait}s")
            await asyncio.sleep(timeToWait)
            # print("o valor da flag na iminência da execução do comando é: ",macroExecutor._stop_running_macro_flag.get_value())
        
        if macroExecutor._stop_running_macro_flag.get_value():
            print("quase executei o comando só que a flag ja estava True e o comando dentro da receivingFunction é: ",message)
            macroExecutor._reset_macro_state()
            return InternalResponse( 0 , 0 , "killmacro" )

        return exec_mouse_or_kb(message, macroExecutor,frozen_controls_to_ignore)
        
    except Exception as e:
        print(" a exceção é: ",e)
        print(" a mensagem recebida na função é: ",message)
        log_error_forensics_plus(e)
        # LoggerManager.log_exception_with_context(f"[WATCHER] ❌ Error in default receiving function: {str(e)}")
    
        return InternalResponse(0,0)


if __name__ == "__main__":
    # kbPressOrRelease("a","press",set())
    # kbPressOrRelease("a","release",set())
    # kbPressOrRelease("v","press",set())
    # kbPressOrRelease("v","release",set())
    # kbPressOrRelease("Ctrl","release",set())
    class MockMacroExecutor:
        _controlsToIgnore = set()
        _ExecutingMacro = {"value": False}
        def __init__(self):
            self._controlsToIgnore = set()
            self._ExecutingMacro = {"value": False}
    _pressed = set(["ctrl","a","v",'cain','left',"right","shift",'1'])
    frozen_controls_to_ignore = set()
    for original_key in list(_pressed):# formata e tenta desapertar
        print("the original_key is: ",original_key)
        command = {
            "key" : original_key, 
            "action" : "release", 
            "equipment" : "keyboard",
            "deltaTime": 0}
        
        try:
            exec_mouse_or_kb(command,MockMacroExecutor,frozen_controls_to_ignore) 
        except InadequateMessage as im:
            print("peguei o inadequate message e a mensagem é: ",im)
            command_for_mouse = {
            "button" : original_key, 
            "action" : "release", 
            "equipment" : "mouse",
            "deltaTime": 0}
            try:
                exec_mouse_or_kb(command_for_mouse,MockMacroExecutor,frozen_controls_to_ignore)
            except InadequateMessage as im2:
                print("também não era um comando de mouse, mensagem: ",im2)