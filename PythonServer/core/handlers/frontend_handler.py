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
###################

from PythonServer.serverConfig import connection_types
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.debuggingResources.error_tracker import monitor_error , log_error_forensics_plus
from PythonServer.core import state # Acesso ao  server_config
from PythonServer.utils import connections

logger = LoggerManager.get_logger(__name__)

def get_current_time():
    return datetime.now().strftime("%X")

@monitor_error
async def handle_frontend(websocket):
    """Gerencia a conexão do painel de controle (Front-end)"""
    tipo = connection_types['front_end']
    
    print(f"conexão do front end estabelecida")
    logger.info(f"🛠️ {get_current_time()} Conexão de controle iniciada!")
    connections.front_end.unique = websocket

    while True:
        try:
            error = True
            message_raw = await websocket.recv()
            # print(f"Do Front_end: {message_raw}")
            message = json.loads(message_raw)

            # 1. Tratamento de Click-to-Ignore (Payload)
            if "payload" in message and "ts" in message["payload"] and message["payload"]["ts"] != 0:
                payload = message["payload"]
                click_to_ignore = payload.get("click", None)
                ts=payload.get("ts",0)/1000  # Convertendo de ms para s
                prepared_command_toIgnore = {
                    "ts": ts,
                    "type": "mouse",
                    "button": click_to_ignore.get("button", "left"),
                    "action": "click",
                    "x": click_to_ignore.get("x", 0),
                    "y": click_to_ignore.get("y", 0)
                } if click_to_ignore else None

                if click_to_ignore:
                    mouseCmd = state.server_config.mouseCommmand(prepared_command_toIgnore)
                    state.server_config.FlushConfig.addcommandToNotFlush(mouseCmd)
                    # state.server_config.FlushConfig.commandsToNotFlush.append(mouseCmd)
                else:
                    print("no click to ignore found in the payload")
                    if ts == 0:
                        ts = time.time()
            else:
                print("no payload  found in the frontend message, using current time as ts")
                ts = str(time.time())
            # print("o ts vindo do frontend é: ",ts)
            ts = float(ts) # normalização pra comparar com o que vem do OS Watcher
            # print("depois ele vira: ",ts)

            # 2. Execução de Comandos
            command_name = message.get("command", None)
            
            if not state.commands:
                print(f"⚠️ Nenhum comando disponível para execução.")

            if command_name and command_name in state.commands:
                print(f"executando o comando: {command_name}")
                
                # Executa a função do comando
                funcao_correta = state.commands[command_name]
                # print(" a função que vou usar é: ")
                # print(funcao_correta)
                # print(funcao_correta.__name__)
                response = state.commands[command_name](MacroTime = ts , front_end_comand = True)
                logger.info(f"✅ {get_current_time()} Comando {command_name} executado!")
                
                # Se o retorno for assíncrono (callable/awaitable)
                if callable(response):
                    print("response is a callable, awaiting it...")
                    resp = await response()
                    print("the awaited response is: ", resp)
                    # Envia a resposta para O PRIMEIRO front conectado (cuidado com múltiplos fronts)
                    
                    if connections.front_end.unique:
                        print("sending response back to front end")
                        print(f"the object i'm trying to knwo what is it is: {connections.front_end.unique}  and its type is: {type(connections.front_end.unique)}")
                        await connections.front_end.unique.send(json.dumps(resp))

                # Confirmação simples
                await websocket.send(json.dumps({"status": "ok", "command": command_name}))
            
            elif command_name:
                print(f"⚠️ Comando desconhecido recebido do front-end: {command_name}")
                logger.warning(f"⚠️ Comando desconhecido: {command_name}")
            
            error = False

        except websockets.exceptions.ConnectionClosedOK:
            print(" recebi ConnectionClosedOK ")
            if not LifecycleMaster.first_shutdown_event.is_set():
                LifecycleMaster.first_shutdown_event.set()
            break
        except websockets.exceptions.ConnectionClosedError:
            print(" recebi ConnectionClosedError ")
            logger.warning(f"❌ {get_current_time()} Conexão encerrada com {tipo}.")
            if websocket in [connections.front_end.unique]:
                connections.front_end.unique = None
            break 
            
        except asyncio.CancelledError:
            logger.info(f"⚠️ {get_current_time()} Loop de {tipo} cancelado.")
            break
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar comando Front: {e}")
            log_error_forensics_plus(e)
            if error:
                await asyncio.sleep(0.3)