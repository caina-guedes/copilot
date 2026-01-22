import asyncio
import websockets
import threading
import json
import copy
from datetime import datetime
import time
import sys

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import builtins
from sharedResources.generalUtils.aprint import aprint  # my assyncronous aprint function
# builtins.print = aprint # Override the built-in aprint with asynchronous aprint

from PythonServer.serverReactions import answerMapping
from sharedResources.DataBases.mainDatabase.main_db import MainDatabase as mainDb
from PythonServer.validador_comandos import validar_comando
from PythonServer.serverConfig import serverConfig, connection_types, SOWatcherActions
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from PythonServer.utils import connections, handleSpecialCommand, resumedMesssage
from PythonServer.macroManager.macroManager import macroManager

# Flag global de shutdown
serverShutdown_event = threading.Event()


a = macroManager(serverConfig)

watcherConfigs = SOWatcherActions()
commands = watcherConfigs.actionDispatch
conditionsMap = watcherConfigs.actionConditions

commands_per_connection = {}

front_end_connection = []


logger = LoggerManager.get_logger(__name__)
mainDb = mainDb(serverConfig = serverConfig)

def get_current_time(format: str = "%X"):
    """
    Returns the current time formatted as a string.
    """
    current_time = datetime.now()
    return current_time.strftime(format)


async def server(websocket):
    try:
        msg = await websocket.recv()
        initial_data = json.loads(msg)
        # print(f"initial message: {initial_data}")
        tipo = initial_data.get("tipo",None)
        # print(f'tipo : {tipo}')
        
        
        if tipo == connection_types['ping']:
            logger.info(f"🔄 {get_current_time()} Received ping from browser.")
            response = {
                "status": "sucesso",
                "mensagem": "Ping recebido com sucesso!"
            }
            await websocket.send(json.dumps(response))
            logger.warning(f"📥-({get_current_time()})response sent to browser: {response}")

        elif tipo in [ connection_types['OSwatcherSender'] , connection_types['OSwatcherReceiver']]:
            if tipo == connection_types['OSwatcherSender']:
                connections.OS.sender = websocket
            elif tipo == connection_types["OSwatcherReceiver"]:
                connections.OS.receiver = websocket
            # SOWatcher_connection.add((tipo,websocket))
            if connections.OS.sender and connections.OS.receiver:
                logger.warning(f"🖥️ {get_current_time()}  SOWatcher Conection Started!")
            # Sends a confirmation message
            response = {
                "status": "sucesso",
                "mensagem": "Conexão SOWatcher estabelecida!"
            }
            await websocket.send(json.dumps(response))
            # logger.info(f"📥-({get_current_time()})response send to SOWatcher:", response)
            # Loop listening to messages from SOWatcher 
            if connections.OS.sender == websocket:
                while True:
                    try:
                        message = await websocket.recv()
                        message = json.loads(message)
                        if isinstance(message, str):
                            message = json.loads(message)
  

                        if macroManager.handlePendingMacroCommand(message):
                            # print("macro command being ignored ",resumedMesssage(message))
                            continue    #if is command from the current executing macro, stops processing here
                        
                        print(f"📩 {get_current_time()} Do SOWatcher: {message}")
                        
                        isSpecialCommand , isPress = handleSpecialCommand(message,serverConfig.specialCommands, commands, conditionsMap)
                        if isSpecialCommand:
                            if not isPress:
                                continue
                            print("deu que é comando especial")
                            if serverConfig.MacroConfig.get_flag("stopRunningMacroFlag"):
                                try:
                                    print("vou enviar o killmacro")
                                    await connections.OS.receiver.send(json.dumps({"action":"killmacro"}))
                                except Exception as e:
                                    print("o server deveria mandar o comando de parar a macro deu erro e foi:" , e)
                            serverConfig.MacroConfig.set_flag("stopRunningMacroFlag", False)
                            
                        mainDb.log_background_event(message,isSpecialCommand)

                        if mainDb.answer is not None: ## futuramente quero trocar isso para um while para que seja possível usar recorrentemente
                            mapping =  await answerMapping.create(mainDb.answer,serverConfig,connections)

                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(f"❌ {get_current_time()} Conexão encerrada com o SOWatcher Sender.")
                        connections.OS.sender = None
                        logger.warning("connection was not discarded correctly")
                        break
                    except asyncio.CancelledError:
                        logger.info(f"⚠️ {get_current_time()} Loop do SOWatcher Sender cancelado.")
                        connections.OS.sender = None
                        break
                    except Exception as e:
                        logger.exception(f"❌ {get_current_time()} Erro ao receber mensagem do SOWatcher: {e}")
                        await asyncio.sleep(0.3)
            elif connections.OS.receiver == websocket:
                try:    
                    message = await websocket.recv()
                    LoggerManager.log_exception_with_context(f"o receiver do SO está mandando mensagem e não devia! e é: {message}")
                except websockets.exceptions.ConnectionClosed:
                    connections.OS.receiver = None
                except asyncio.CancelledError:
                    connections.OS.receiver = None
                except Exception as e:
                    connections.OS.receiver = None
                    LoggerManager.log_exception_with_context(f"erro inesperado no receiver e é: {e}",e)
                
        # Verifica o tipo de conexão
        elif tipo == connection_types['extension']:
            connections.browser.unique = websocket
            allowed_commands = initial_data.get("comandos", [])
            commands_per_connection[websocket] = allowed_commands
            logger.warning(f"🌐 {get_current_time()} Connected browser extension !")
            # Loop listening to browser messages
            while True:
                try:
                    message = await websocket.recv()
                    logger.info(f"📩 {get_current_time()} Do navegador: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"❌ {get_current_time()} Conexão encerrada com {tipo}.")
                    # limpa referência
                    connections.browser.unique = None
                    break  # sai do loop
                except asyncio.CancelledError:
                    logger.info(f"⚠️ {get_current_time()} Loop de {tipo} cancelado.")
                    connections.browser.unique = None
                    break
                except Exception as e:
                    connections.browser.unique = None
                    LoggerManager.log_exception_with_context(f"[server.py] Erro no loop de {tipo}: {e}", e)
                    await asyncio.sleep(0.5)

        elif tipo == connection_types['front_end']:
            print(f"conexão do front end estabelecida")
            logger.info(f"🛠️ {get_current_time()} Conexão de controle iniciada!")
            front_end_connection.append(websocket)

            while True:
                try:
                    error = True
                    message = await websocket.recv()
                    print(f"Do Front_end: {message}")
                    message = json.loads(message)
  
                    if "payload" in message and "ts" in message["payload"] and message["payload"]["ts"] != 0 :
                        payload = message["payload"]
                        click_to_ignore = payload.get("click", None) 
                        prepared_command_toIgnore = {
                            "ts": payload.get("ts",0) , 
                            "type":"mouse" , 
                            "button": click_to_ignore.get("button","left") , 
                            "action":"click" , "x": click_to_ignore.get("x",0) , 
                            "y": click_to_ignore.get("y",0) } if click_to_ignore else None
    
                        # print("the prepared_command_toIgnore is: ", prepared_command_toIgnore)
                        if click_to_ignore:
                            # print("click to ignore added to the commandsToNotFlush list")
                            mouseCmd = serverConfig.mouseCommmand(prepared_command_toIgnore)
                            serverConfig.FlushConfig.commandsToNotFlush.append(mouseCmd)
                            # print(f"the list is now: {serverConfig.FlushConfig.commandsToNotFlush}")
                        else:
                            print("no click to ignore found in the payload")

                    command_name = message.get("command", None)
                    # if command_name:
                    #     print(f"o command_name é: {command_name}")
                    if not commands:
                        print(f"⚠️ Nenhum comando disponível para execução.")
                    
                    if command_name in commands:
                        # Executa a função correspondente
                        print(f"executando o comando: {command_name}")
                        # continue 
                        # if False:  # Placeholder para validação futura    
                        response = commands[command_name]()
                        logger.info(f"✅ {get_current_time()} Comando {command_name} executado com sucesso!")
                        if callable(response):
                            print("response is a callable, awaiting it...")
                            resp = await response()
                            print("the awaited response is: ", resp)
                            await front_end_connection[0].send(json.dumps(resp))
                        
                        # ainda falta implementar ações mais complexas aqui, da mesma forma como ja acontece na interação direta com o watcher

                        # Opcional: enviar confirmação para o front-end
                        await websocket.send_json({"status": "ok", "command": command_name})
                    else:
                        print(f"⚠️ Comando desconhecido recebido do front-end: {command_name}")
                        logger.warning(f"⚠️ Comando desconhecido: {command_name}")
                    error = False


                
                except websockets.exceptions.ConnectionClosed:
                    logger.warning(f"❌ {get_current_time()} Conexão encerrada com {tipo}.")
                    
                    # break  # sai do loop
                except asyncio.CancelledError:
                    logger.info(f"⚠️ {get_current_time()} Loop de {tipo} cancelado.")
                    # break
                except Exception as e:
                    logger.error(f"❌ Erro ao processar comando: {e}")
                    # break
                if error:
                    await asyncio.sleep(0.3)
        else:
            print(f"⚠️ {get_current_time()} Unknown connection type. info: {initial_data}")

                
                    # ok, err = validar_comando(json.loads(message))
                    # if ok:
                    #     logger.info(f"✅ {get_current_time()} Comando válido.  {message}")

                    # else:
                    #     logger.info(f"❌ {get_current_time()} Comando inválido.  {message}")
                    #     logger.info(f"❌ {get_current_time()} Erro: {err}")
                    #     # Envia uma resposta de erro para o controlador
                    #     response = {
                    #         "status": "falha",
                    #         "mensagem": "Comando inválido."
                    #     }
                    #     await websocket.send(json.dumps(response))
                    #     continue
                    # response = { 
                    #     "status": "falha",
                    #     "mensagem": "nenhum navegador conectado."
                    # }
                    # # for nav in browser_connections.copy():
                    # try:
                    #     await connections.browser.unique.send(message)
                    #     logger.info(f"📤 {get_current_time()} Comando enviado ao navegador")
                    #     response = {
                    #             "status": "sucesso",
                    #             "mensagem": "Comando enviado com sucesso!"
                    #         }
                    # except websockets.exceptions.ConnectionClosed:
                    #     logger.warning(f"❌ {get_current_time()} Conexão encerrada com o navegador.")
                    #     response = {
                    #         "status": "falha",
                    #         "mensagem": "Comando falhou ao ser enviado."
                    #         }
                    # finally:
                    #     pass
                    # # Envia uma resposta de volta para o controlador
                    
                    # await websocket.send(json.dumps(response))
                    # logger.info(f"📥 {get_current_time()} Response sent to the controller: {response}")
            

    except websockets.exceptions.ConnectionClosed:
        logger.warning(f"❌ {get_current_time()} Connection closed.")
    except Exception as e:
        LoggerManager.log_exception_with_context(e)    
    finally:

        connections.browser.unique = None


async def check_connections(period = 10):
    while True:
        await asyncio.sleep(period)
        # for conn in list(browser_connections):
        try:
            if connections.browser.unique:
                pong_waiter = await connections.browser.unique.ping()
                await asyncio.wait_for(pong_waiter, timeout=5)
        except Exception as e:
            logger.warning(f"⚠️ Conexão inativa detectada e removida: ")
            connections.browser.unique = None
            commands_per_connection={}

async def start_ws_server():
    async with websockets.serve(server, "localhost", 8765):
        logger.warning(f"🚀 {get_current_time()} server WebSocket rodando em ws://localhost:{serverConfig.serverPort}")
        await asyncio.gather(
            asyncio.Future(),  # Mantém o server ativo
            check_connections()  # Verifica as conexões periodicamente
            )

# Roda o server em uma thread separada
def iniciar_server():
    asyncio.run(start_ws_server())

# Envia comandos para todos os navegadores conectados
async def enviar_comando(comandoInicial  =  ''  ):
    if comandoInicial:
        message = {
            "acao": comandoInicial,
        }
        logger.info(f"recebi o comando , {comandoInicial}")
        logger.info(f"tenho {len([connections.browser.unique])} conexões ativas")
        data = json.dumps(message)
        
        if connections.browser.unique is None:
            logger.info(f"⚠️ {get_current_time()} Nenhum navegador conectado para enviar o comando.")
            return
        logger.info(f" {get_current_time()} Enviando comando para navegador conectado...")
        await connections.browser.unique.send(data)
        logger.info(f"📤 Comando enviado: {data}")
    else:
        while True:
            comando = input("💻 Digite o comando para enviar ao navegador (ex: preencher_formulario):\n> ")
            if comando.lower() == "list":
                logger.info(f"Conexões ativas: {len([connections.browser.unique])}")
                for conn in connections.browser.unique:
                    logger.info(f"Conexão ativa: {conn}")
                continue
            elif comando.lower() == "exit":
                logger.info("Saindo...")
                break
            message = {
                "acao": comando,
                "dados": {
                    "nome": "João",
                    "email": "joao@email.com",
                    "telefone": "123456789"
                }
            }
            data = json.dumps(message)
            await connections.browser.unique.send(data)
            logger.info(f"📤 Comando enviado: {data}")

def main():
    # Inicializa o server na thread principal ou não-daemon
    try:
        server_thread = threading.Thread(target=iniciar_server, name="ServerThread")
        server_thread.start()
        print("created thread  and the name is:", server_thread.name)
    except KeyboardInterrupt:
        print("❌ Interrompido pelo usuário.")
        # serverShutdownEvent.set()
    except Exception as e:
        print("❌ Erro ao iniciar o servidor WebSocket:", e)

    # Aguarda server estar pronto (opcional: pode colocar sleep ou flag)
    # asyncio.run(enviar_comando())
    finally:
        # Fecha listener do logger quando tudo terminar
        LoggerManager.stop_listener()

        # Espera server terminar se necessário
        server_thread.join()

if __name__ == "__main__":
    # threading.Thread(target=iniciar_server, daemon=True).start()
    # asyncio.run(enviar_comando())
    # LoggerManager.stop_listener()  # Stop logger listener when script ends
    main()
    # iniciar_server()
    # while True:
    #     time.sleep(5)
    
    # Inicia o server WebSocket

# # Inicia o server em uma thread paralela
# threading.Thread(target=iniciar_server, daemon=True).start()

# # Inicia o input de comandos
# enviar_comando()

