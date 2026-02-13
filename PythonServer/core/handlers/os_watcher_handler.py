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

# Imports do sistema existente
from PythonServer.serverConfig import connection_types
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus
from PythonServer.utils import handleSpecialCommand
from PythonServer.serverReactions import answerMapping

# Import do Estado Global (Onde guardamos as referências)
from PythonServer.core import state
from PythonServer.utils import connections

logger = LoggerManager.get_logger(__name__)

def get_current_time():
    return datetime.now().strftime("%X")


@monitor_error
async def process_watcher_msg(message):
    """Lógica processamento de mensagens vindas do OS Watcher"""
    # 1. Verifica Macro
    if state.macro_manager.handlePendingMacroCommand(message):
        return

    # 2. Verifica Comandos Especiais
    isSpecialCommand, isPress = handleSpecialCommand(
        message, 
        state.server_config.specialCommands, 
        state.commands, 
        state.conditions_map
    )

    if isSpecialCommand:
        if not isPress: return
        print("deu que é comando especial")
        
        if state.server_config.MacroConfig.get_flag("stopRunningMacroFlag"):
            try:
                print("vou enviar o killmacro")
                await connections.OS.receiver.send(json.dumps({"action": "killmacro"}))
            except Exception as e:
                print("Erro ao enviar killmacro:", e)
        state.server_config.MacroConfig.set_flag("stopRunningMacroFlag", False)
        
    # 3. Log no Banco
    state.mainDb.log_background_event(message, isSpecialCommand)

    # 4. Reações (Answer Mapping)
    if state.mainDb.answer is not None:
        await answerMapping.create(state.mainDb.answer, state.server_config, connections)

@monitor_error
async def handle_os_connection(websocket, tipo):
    """Gerencia conexões do tipo OSwatchSender e OSwatchReceiver"""
    
    # Configuração Inicial
    if tipo == connection_types['OSwatcherSender']:
        connections.OS.sender = websocket
    elif tipo == connection_types["OSwatcherReceiver"]:
        connections.OS.receiver = websocket

    if connections.OS.sender and connections.OS.receiver:
        logger.warning(f"🖥️ {get_current_time()} SOWatcher Connection Started!")

    # Envia confirmação
    response = {"status": "sucesso", "mensagem": "Conexão SOWatcher estabelecida!"}
    await websocket.send(json.dumps(response))

    # Loop de escuta (Apenas para o Sender)
    if connections.OS.sender == websocket:
        while True:
            try:
                message = await websocket.recv()
                message_data = json.loads(message)
                
                if isinstance(message_data, str):
                    message_data = json.loads(message_data)
                
                if isinstance(message_data, list):
                    for msg in message_data:
                        print(f"📩 {get_current_time()} Do SOWatcher: {msg}")
                        await process_watcher_msg(msg)
                else:
                    logger.warning(f"Formato inesperado do SOWatcher: {message_data}")
                    # O código original tinha um erro forçado aqui (1.0/0.0), removi por segurança
            except websockets.exceptions.ConnectionClosedOK:
                print("[handle_os_connection] recebi ConnectionClosedOK no sender")
                if not LifecycleMaster.first_shutdown_event.is_set():
                    LifecycleMaster.first_shutdown_event.set()
                break
            except websockets.exceptions.ConnectionClosedError:
                logger.warning(f"❌ {get_current_time()} Conexão encerrada com o SOWatcher Sender. this is not for shutdown!!!!!")
                connections.OS.sender = None
                break
            
            except asyncio.CancelledError:
                logger.info(f"⚠️ {get_current_time()} Loop do SOWatcher Sender cancelado.")
                connections.OS.sender = None
                break
            except Exception as e:
                log_error_forensics_plus(e)
                logger.exception(f"❌ Erro no SOWatcher: {e}")
                await asyncio.sleep(0.3)
    
    # Loop de escuta (Receiver - não deveria receber nada, mas tratamos erros)
    elif connections.OS.receiver == websocket:
        try:    
            message = await websocket.recv()
            LoggerManager.log_exception_with_context(f"Receiver mandou msg inesperada: {message}")
        
        except websockets.exceptions.ConnectionClosedOK:
                print("[handle_os_connection] recebi ConnectionClosedOK no receiver")
                if not LifecycleMaster.first_shutdown_event.is_set():
                    LifecycleMaster.first_shutdown_event.set()
        except websockets.exceptions.ConnectionClosedError:
            logger.warning(f"❌ {get_current_time()} Conexão encerrada com o SOWatcher Sender. this is not for shutdown!!!!!")
            connections.OS.receiver = None

        except asyncio.CancelledError:
            logger.info(f"⚠️ {get_current_time()} Loop do SOWatcher Sender cancelado.")
            connections.OS.receiver = None

        except Exception as e:
            log_error_forensics_plus(e)
            connections.OS.receiver = None