import asyncio
import json
import time
from pynput.keyboard import Key, Controller as KeyboardController
from pynput.mouse import Button, Controller as MouseController
import warnings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.generalUtils.aprint import aprint

from sharedResources.pythonLoggerSistem.logger import LoggerManager

keyboard = KeyboardController()
mouse    = MouseController()



def mouseExecCommand(message, action, controlsToIgnore):
    print(f"vou executar um comando de mouse e é: {message}")
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
    if action == "click":
        mouse.click(getattr(Button, button),1)
        print(f"Mouse clicked {button} button")
    elif action == "double_click":
        mouse.click(getattr(Button, button),2)
        print(f"Mouse double clicked {button} button")
    elif action == "press":
        mouse.press(getattr(Button, button))
        print(f"Mouse button {button} pressed")
    elif action == "release":
        mouse.release(getattr(Button, button))
        print(f"Mouse button {button} released")
    elif action in  ["roll","scroll"]:
        delta = message.get("delta", 0)
        mouse.scroll(0, delta)
        print(f"Mouse scrolled with delta {delta}")
    else:
        print(f"action {action} not recognized for mouse")
    after = time.perf_counter()

    return (before,after)

def kbPressOrRelease(message, action, controlsToIgnore):
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
        after = time.perf_counter()
        print("Executed keyboard action: ", action, "for key:", key_name)
        return (before, after)

    except Exception as e:
        
        print(f"Error processing keyboard action {action} for key {key_name}: {e}")
        warnings.warn(str(e))

class  InternalResponse:
    def __init__(self,start_time,endTime,waitForServer = None):
        self.start_time = start_time
        self.endTime = endTime
        self.waitForServer = waitForServer




def exec_mouse_or_kb(message, macroExecutor,frozen_controls_to_ignore = None ):
    if isinstance(message, str): 
        message = json.loads(message)

    controlsToIgnore = frozen_controls_to_ignore or macroExecutor._controlsToIgnore
        # controlsToIgnore = frozen_controls_to_ignore or macroExecutor._controlsToIgnore
    if controlsToIgnore is None :
        print("[default_receiving_function] controlsToIgnore to ignore is none inside ")
        print(f"[default_receiving_function] the message received here is: {message}")
    if message is None:
        print("Received None message, ignoring but maybe the connection has ended")
        return InternalResponse(0,0)

    action   = message['action']
    ExecutingMacro   = macroExecutor._ExecutingMacro

    if action == "endMacro":
        ExecutingMacro["value"] = False
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
            
        except Exception as e:
            print(f"Error processing keyboard command: {e}")
            warnings.warn(str(e))
            LoggerManager.log_exception_with_context(f"Error processing keyboard command: {e}",e)

    elif equipment == "mouse":
        try:
            before,after = mouseExecCommand(message, action, controlsToIgnore)
    
            return InternalResponse(before,after)
    
        except Exception as e:
            print(f"Error processing mouse command: {e}")
            warnings.warn(str(e))
            LoggerManager.log_exception_with_context(f"Error processing mouse command: {e}",e)

    else:
        print(f"equipment {equipment} not recognized")
        LoggerManager.log_exception_with_context(f"equipment {equipment} not recognized")


    return InternalResponse(0,0)

    
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
            loop_time = asyncio.get_running_loop().time()
            # print(f"[{loop_time:.3f}] Aguardando {timeToWait}s")
            await asyncio.sleep(timeToWait)
            # print("o valor da flag na iminência da execução do comando é: ",macroExecutor._stop_running_macro_flag.get_value())
        
        if macroExecutor._stop_running_macro_flag.get_value():
            print("quase executei o comando só que a flag ja estava True e o comando dentro da receivingFunction é: ",message)
            macroExecutor._reset_macro_state()
            return InternalResponse( 0 , 0 , "killmacro" )

        return exec_mouse_or_kb(message, macroExecutor,frozen_controls_to_ignore)
        
    except Exception as e:
        print("[default_receiving_function] a exceção é: ",e)
        print("[default_receiving_function] a mensagem recebida na função é: ",message)
        warnings.warn(str(e))
        LoggerManager.log_exception_with_context(f"[WATCHER] ❌ Error in default receiving function: {str(e)}")
    
        return InternalResponse(0,0)

# async def old_default_receiving_function(message, macroExecutor,frozen_controls_to_ignore = None ):
#     """
#     this functions needs the message to be [deltaTime,[equipment,action,key],modifiers]
#     """
#     controlsToIgnore = frozen_controls_to_ignore or macroExecutor._controlsToIgnore
#     if controlsToIgnore is None :
#         print("[default_receiving_function] controlsToIgnore to ignore is none inside ")
#         print(f"[default_receiving_function] the message received here is: {message}")
#     ExecutingMacro   = macroExecutor._ExecutingMacro
#     if message is None:
#         print("Received None message, ignoring but maybe the connection has ended")
#         return InternalResponse(0,0)
#     try:
#         message = json.loads(message)
#         action   = message['action']

#         if action == "endMacro":
#             ExecutingMacro["value"] = False
#             print("Macro execution ended.")
#             return InternalResponse(0,0)

#         elif action == "startMacro":
#             ExecutingMacro["value"] = True
#             print("Macro execution started.") 
#             return InternalResponse(0,0)

#         elif action == "WaitForServer":
#             return InternalResponse(0,0,True)
        
#         elif action == "continueMacro":
#             return InternalResponse(0,0,False)

#         elif action not in ["press","release","click","double_click","scroll","move"]:
#             print(f"action {action} not recognized, will be ignored")
#             return InternalResponse(0,0)
#             # pass
        
#         timeToWait = message['deltaTime']
#         loop_time = asyncio.get_running_loop().time()
#         # print(f"[{loop_time:.3f}] Aguardando {timeToWait}s")
#         await asyncio.sleep(timeToWait)
#         # print("o valor da flag na iminência da execução do comando é: ",macroExecutor._stop_running_macro_flag.get_value())
#         if macroExecutor._stop_running_macro_flag.get_value():
#             print("quase executei o comando só que a flag ja estava True e o comando dentro da receivingFunction é: ",message)
#             macroExecutor._reset_macro_state()
#             return InternalResponse( 0 , 0 , "killmacro" )

#         equipment = message["equipment"].lower()
#         if equipment == "keyboard":
#             try:
#                 key_name = message['key'][4:] if 'key.' in message['key'].lower() else message['key']
                
#                 before,after = kbPressOrRelease(key_name, action, controlsToIgnore)
        
#                 return InternalResponse(before,after)
                
#             except Exception as e:
#                 print(f"Error processing keyboard command: {e}")
#                 warnings.warn(str(e))
#                 LoggerManager.log_exception_with_context(f"Error processing keyboard command: {e}",e)

#         elif equipment == "mouse":
#             try:
#                 before,after = mouseExecCommand(message, action, controlsToIgnore)
        
#                 return InternalResponse(before,after)
        
#             except Exception as e:
#                 print(f"Error processing mouse command: {e}")
#                 warnings.warn(str(e))
#                 LoggerManager.log_exception_with_context(f"Error processing mouse command: {e}",e)

#         else:
#             print(f"equipment {equipment} not recognized")
#             LoggerManager.log_exception_with_context(f"equipment {equipment} not recognized")

    
#         return InternalResponse(0,0)
    
#     except Exception as e:
#         warnings.warn(str(e))
#         LoggerManager.log_exception_with_context(f"[WATCHER] ❌ Error in default receiving function: {str(e)}")
    
#         return InternalResponse(0,0)

if __name__ == "__main__":
    kbPressOrRelease("a","press",set())
    kbPressOrRelease("a","release",set())
    kbPressOrRelease("v","press",set())
    kbPressOrRelease("v","release",set())
    kbPressOrRelease("Ctrl","release",set())
    
    
