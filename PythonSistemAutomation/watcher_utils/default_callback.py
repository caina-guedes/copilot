import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import (
    monitor_error,
    log_error_forensics_plus,
)

import time

logger = LoggerManager.get_logger(__name__)


@monitor_error
async def default_callback(event, father, sendingQueue = None):
    """this function check for changes in the current window and sends the event"""
    # print(" Event captured:", event)
    inicio = time.perf_counter()
    try:
        if sendingQueue is not None:
            sendingQueue.put(event)
            return 
        else:
            try:
                
                await father.ws_client.connection.send(event, True)
                return True, time.perf_counter() - inicio
            except Exception as ex:
                if await father.ws_client.reconnect():  # Reset the connection if it fails
                    await father.ws_client.connection.send(event, True)
                    return True, time.perf_counter() - inicio
                else:
                    try:
                        await father.not_sent_db.save_event(event)
                        print(f"Event saved to not sent database: {event}")
                    except Exception as e:
                        log_error_forensics_plus(e)
                    return False, time.perf_counter() - inicio

    except Exception as e:
        log_error_forensics_plus(e)

        # warnings.warn(str(e))
        print(f"Error in defaultcallback: {e}")
        # LoggerManager.log_exception_with_context(f"Error in default callback: {e}")
        logger.info(f"Error in default callback: {e}")


def treat_key_as_string(key):
    if hasattr(key, "char"):
        return key.char
    return str(key)
