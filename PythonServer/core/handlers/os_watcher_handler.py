import json
import asyncio
import time
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
from PythonServer.serverConfig import connection_types,serverConfig
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class
from PythonServer.utils import handleSpecialCommand
from PythonServer.serverReactions import answerMapping

# Import do Estado Global (Onde guardamos as referências)
from PythonServer.core import state
from PythonServer.utils import connections

answerMapping.set_connections(connections)

answerMapping.set_serverConfig(serverConfig)
serverConfig.set_flag("answerMapping" , answerMapping)

logger = LoggerManager.get_logger(__name__)

def get_current_time():
    return datetime.now().strftime("%X")




@monitor_class
class OSProcessorClass():
    """
    classe criada para extruturar melhor os 
    loops e o processamento dos eventos 
    vindos do watcher do SO
    """
    receiver_loop_task = None
    receiver_conn = None
    sender_conn = None
    first_closed_ok_received = False

    @classmethod
    async def start_receiver(cls,websocket):
        print(f"[OSProcessorClass.start_receiver] starting")
        # print("just set the answermapping to the serverConfig")
        if cls.receiver_conn is None:
            cls.receiver_conn = websocket
            cls. receiver_loop_task = LifecycleMaster.run_async(cls.receiver_loop(websocket), name="loop do receiver do watcher")
            # await websocket.wait_closed()
    @classmethod
    async def receiver_loop(cls,websocket):
        while True:
            try:
                message = await websocket.recv()
                message_data = json.loads(message)
                
                if isinstance(message_data, str):
                    message_data = json.loads(message_data)
                
                if isinstance(message_data, list):
                    for msg in message_data:
                        print(f"📩 {get_current_time()} Do SOWatcher: {msg}")
                        await cls.process_watcher_msg(msg)
                else:
                    logger.warning(f"Formato inesperado do SOWatcher: {message_data}")
                    # O código original tinha um erro forçado aqui (1.0/0.0), removi por segurança
            except websockets.exceptions.ConnectionClosedOK:
                horario = time.perf_counter()
                print(f"[handle_os_connection {horario}] recebi ConnectionClosedOK no sender")
                if not cls.first_closed_ok_received:# esse erro está vindo no inicio da conexão com o watcher então vou ver se ele ignorando a primeira ve é suficiente
                    
                    cls.first_closed_ok_received = True
                    await asyncio.sleep(0.1)
                    continue
                if not LifecycleMaster.first_shutdown_event.is_set():
                    LifecycleMaster.first_shutdown_event.set()
                connections.OS.sender = None
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
        
    @classmethod
    async def handle_os_connection(cls,websocket, tipo):

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
        try:
            await websocket.send(json.dumps(response))
        except Exception as e:
            print(f"[OSProcessorClass.handle_os_connection] deu erro e foi:{str(e)}")
            log_error_forensics_plus(e)
        # Loop de escuta (Apenas para o Sender)
        if connections.OS.sender == websocket:
            if cls.receiver_conn is None and cls.receiver_loop_task is None:
                await cls.start_receiver(websocket)
            else:
                print("tentaram iniciar o receiver loop do watcher indevidamente!!!")
                try:
                    1/0
                except Exception as e:
                    log_error_forensics_plus(e)
        
        # Loop de escuta (Receiver - não deveria receber nada, mas tratamos erros)
        elif connections.OS.receiver == websocket:
            if cls.sender_conn is None:
                cls.sender_conn = websocket
                try:    
                    message = await websocket.recv()
                    # LoggerManager.log_exception_with_context(f"Receiver mandou msg inesperada: {message}")
                
                except websockets.exceptions.ConnectionClosedOK:
                    print("[handle_os_connection] recebi ConnectionClosedOK no receiver")
                    connections.OS.receiver = None
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
            else:
                print("tentaram colocar um websocket como o sender_conn dessa classe mas ja existe um aqui !!")
                try:
                    1/0
                except Exception as e:
                    log_error_forensics_plus(e)
    @classmethod
    async def process_watcher_msg(cls,message):
        """Lógica processamento de mensagens vindas do OS Watcher"""
        # 1. Verifica se é comando de  Macro
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
        if state.mainDb.answer is not None :
            print(f"[OSProcessorClass.process_watcher_msg] the Db,answer is: {state.mainDb.answer}",)
            await answerMapping.create(state.mainDb.answer, state.server_config, connections)
            state.mainDb.clean_answer()