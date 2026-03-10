import json
import asyncio
import websockets
from datetime import datetime

# for safe importing and unit testing!
import sys
from pathlib import Path

from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
basePath = str(Path(__file__).resolve().parent.parent.parent.parent)
# print("the base path is: ",basePath)
sys.path.append(basePath)

from PythonServer.serverConfig import connection_types
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
from PythonServer.utils import connections
from PythonServer.core import state # Acesso ao commands_per_connection

logger = LoggerManager.get_logger(__name__)

def get_current_time():
    return datetime.now().strftime("%X")

@monitor_error
async def handle_browser_extension(websocket, initial_data):
    """Gerencia a conexão da extensão do navegador"""
    tipo = connection_types['extension']
    
    # Registro
    connections.browser.unique = websocket
    allowed_commands = initial_data.get("comandos", [])
    state.commands_per_connection[websocket] = allowed_commands
    
    logger.warning(f"🌐 {get_current_time()} Connected browser extension!")

    # Loop Principal
    while True:
        try:
            message = await websocket.recv()
            logger.info(f"📩 {get_current_time()} Do navegador: {message}")
        except websockets.exceptions.ConnectionClosedOK:
            print(" recebi ConnectionClosedOK ")
            if not LifecycleMaster.first_shutdown_event.is_set():
                LifecycleMaster.first_shutdown_event.set()
            break
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"❌ {get_current_time()} Conexão encerrada com {tipo}.")
            connections.browser.unique = None
            if websocket in state.commands_per_connection:
                del state.commands_per_connection[websocket]
            break
        
        except asyncio.CancelledError:
            logger.info(f"⚠️ {get_current_time()} Loop de {tipo} cancelado.")
            connections.browser.unique = None
            break
        
        except Exception as e:
            connections.browser.unique = None
            logger.error(f"Erro no loop de {tipo}: {e}")
            log_error_forensics_plus(e)
            await asyncio.sleep(0.5)