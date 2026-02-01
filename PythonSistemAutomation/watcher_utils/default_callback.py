from .event_utils import print_event
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
import warnings
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from PythonSistemAutomation.watcher_utils.windowWatcher.windowManager import WindowManager
# from PythonSistemAutomation.watcher_utils.windowWatcher.WindowManager import WindowManager

window = WindowManager()

logger = LoggerManager.get_logger(__name__)

async def default_callback(event,father):
    """this function check for changes in the current window and sends the event"""
    # print("[default_callback] Event captured:", event)
    try:
        currentWindow, changed = window.get_active_window()
        if changed:
            # print("houve atualização de janela!!!")
            event["windowChange"] = True
            event["newCurrentWindow"] = currentWindow.to_dict()
        else:
            event["windowChange"] = False
        
        try:
            await father.ws_client.connection.send(event, True)
        
        except Exception as ex:
            await father.ws_client.reconnect()  # Reset the connection if it fails
            try:
                await father.not_sent_db.save_event(event)
                print(f"Event saved to not sent database: {event}")
            except Exception as e:
                warnings.warn(str(e))
                LoggerManager.log_exception_with_context(f"Error saving event to database: {e}")
            LoggerManager.log_exception_with_context(f"Error adding event to about_to_send: {ex}")

    except Exception as e:
        warnings.warn(str(e))
        print(f"Error in defaultcallback: {e}")
        LoggerManager.log_exception_with_context(f"Error in default callback: {e}")
        logger.info(f"Error in default callback: {e}")

        
def treat_key_as_string(key):
    if hasattr(key, 'char'):
        return key.char    
    return str(key)
