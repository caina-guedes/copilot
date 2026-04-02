import asyncio
import queue
import websockets
import threading
import json
import sys
from pathlib import Path
from datetime import datetime

# Adiciona o caminho base ao path (mantido do original)
sys.path.append(str(Path(__file__).resolve().parent.parent))


# Imports Utilitários e Debug
# from PythonServer.port_handler import free_port
from sharedResources.pythonLoggerSistem.logger import LoggerManager
# LoggerManager.complement_logs_path("Server")
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
### o lifecycleMaster tem que ser o primeiro a ser importado por causa do print interceptor!!!!!
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus

from sharedResources.generalUtils.aprint import aprint

# Imports de Configuração e Banco
from PythonServer.serverConfig import serverConfig, connection_types, SOWatcherActions
from sharedResources.DataBases.mainDatabase.main_db import MainDatabase as MainDbClass
from PythonServer.macroManager.macroManager import macroManager

# --- NOVOS IMPORTS (A Mágica da Refatoração) ---
from PythonServer.core import state  # Onde guardamos as variáveis globais
from PythonServer.core.handlers import os_watcher_handler, browser_handler, frontend_handler
from PythonServer.utils import connections # Ainda precisamos disso para o check_connections antigo
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class
from PythonSistemAutomation.main import main as watcher_main_function

# Logger Setup
logger = LoggerManager.get_logger(__name__)

# ==============================================================================
# 1. INICIALIZAÇÃO DE ESTADO (BOOTSTRAP)
# ==============================================================================
@sys_monitor
def initialize_server_state():
    """
    Inicializa todos os componentes pesados e os injeta no módulo de estado.
    Isso substitui as variáveis globais soltas.
    """
    print("🔄 Inicializando estado do servidor...")
    
    # 1. Macro Manager
    macroManager(serverConfig) # No seu código original parecia ser uma chamada de função ou init
    # Assumindo que macroManager é um módulo ou classe singleton, vamos guardar a referência
    state.macro_manager = macroManager 
    
    # 3. Configurações do Servidor
    state.server_config = serverConfig
    
    # 4. Banco de Dados
    # Instancia e guarda no estado global para os handlers usarem
    state.mainDb = MainDbClass(serverConfig=serverConfig)
    
    # 2. Configurações do Watcher
    watcher_configs = SOWatcherActions(state.mainDb)
    state.watcher_configs = watcher_configs
    state.commands = watcher_configs.actionDispatch
    state.conditions_map = watcher_configs.actionConditions
    
    
    # print("✅ Estado do servidor inicializado e injetado em 'core.state'.")

# Chama a inicialização imediatamente ao importar/rodar este script
initialize_server_state()

# ==============================================================================
# 2. ROTEADOR DE CONEXÕES (O ANTIGO server())
# ==============================================================================
def get_current_time(format: str = "%X"):
    return datetime.now().strftime(format)

@sys_monitor
async def server_router(websocket):
    """
    Função principal que recebe a conexão e roteia para o handler correto.
    Substitui a antiga função monolítica 'server'.
    """
    try:
        # Lê a primeira mensagem para identificar quem é
        msg = await websocket.recv()
        initial_data = json.loads(msg)
        tipo = initial_data.get("tipo", None)
        
        # --- ROTEAMENTO ---
         
        # 1. PING (Healthcheck simples)
        if tipo == connection_types['ping']:
            # logger.info(f"🔄 {get_current_time()} Ping recebido.")
            response = {"status": "sucesso", "mensagem": "Ping recebido com sucesso!"}
            await websocket.send(json.dumps(response))
            logger.warning(f"📥 Response sent to browser: {response}")

        # 2. OS WATCHER (Sender ou Receiver)
        elif tipo in [connection_types['OSwatcherSender'], connection_types['OSwatcherReceiver']]:
            await os_watcher_handler.OSProcessorClass.handle_os_connection(websocket, tipo)
            await websocket.wait_closed()
        # 3. EXTENSÃO DO BROWSER
        elif tipo == connection_types['extension']:
            await browser_handler.handle_browser_extension(websocket, initial_data)
            await websocket.wait_closed()

        # 4. FRONT-END (Controle)
        elif tipo == connection_types['front_end']:
            await frontend_handler.handle_frontend(websocket)
            await websocket.wait_closed() # O handler do front-end é o único que mantém a conexão aberta para receber comandos, então esperamos ele fechar aqui.

        # 5. DESCONHECIDO
        else:
            logger.warning(f"⚠️ {get_current_time()} Tipo de conexão desconhecido: {initial_data}")
            await websocket.close()

    except websockets.exceptions.ConnectionClosed:
        print(" Conexão fechada durante o handshake ou comunicação. Isso é normal se o cliente desconectar rapidamente.")
        pass # Conexão fechada durante o handshake é normal
    # except Exception as e:
        # LoggerManager.log_exception_with_context(e)
        # raise 

# ==============================================================================
# 3. GERENCIAMENTO DE CICLO DE VIDA (SERVER MANAGER)
# ==============================================================================
# (Mantivemos a classe aqui por enquanto, mas ela usa a nova função router)

@monitor_class
class WebSocketServerManager:
    

    def __init__(self, watcher_is_internal = False):
        self.server_task = None
        self.check_conn_task = None
        self.ws_server = None
        if watcher_is_internal == True:
            self.senderQueue = asyncio.Queue()
            self.receiverQueue = asyncio.Queue()
        else:
            self.senderQueue = None
            self.receiverQueue = None

    async def start(self):
        """Método principal que o LifecycleMaster vai submeter"""
        try:
            # Note que agora passamos 'server_router' em vez de 'server'
            # free_port(8765)
            async with websockets.serve(server_router, "localhost", 8765) as ws_server:
                LifecycleMaster.register_cleanup_function(self.stop_procedure, 
                                                          priority = 100,
                                                          name = "WebSocketServerManager.stop_procedure",
                                                          register_in_atexit= False
                                                          )
                # Registra hooks de limpeza
                # Usando o novo hook do LifecycleMaster que implementamos antes!
                # LifecycleMaster.register_cleanup_function(ws_server.close, priority=90)
                
                LifecycleMaster.register_log(f"🚀 Server WebSocket rodando em ws://localhost:8765", "server")
                self.ws_server = ws_server
                
                # Lança verificação de conexões
                self.check_conn_task = LifecycleMaster.run_async(
                    self.check_connections(period=10), 
                    name="ServerConnectionCheck"
                )

                if self.senderQueue and self.receiverQueue:
                    self.os_internal_communication_task = LifecycleMaster.run_async(
                        os_watcher_handler.OSProcessorClass.handle_internal_os_connection(self.receiverQueue, "receiver"),
                        name = "OSWatcherInternalQueueListener")
                    await os_watcher_handler.OSProcessorClass.handle_internal_os_connection(self.senderQueue, "sender")
                # Loop de espera do Shutdown
                LifecycleMaster.shutdown_event.clear()
                while not LifecycleMaster.shutdown_event.is_set():
                    await asyncio.sleep(0.05)
                
                # print("Sinal de shutdown recebido no Server Manager...")
                print("Servidor WebSocket fechado com sucesso.")
                
        except Exception as e:
            log_error_forensics_plus(e, "Falha na inicialização do Servidor")
            LifecycleMaster.emergency_shutdown(e)
        finally:
            # Segurança extra no finally
            try:
                # free_port(8765)
                await self.stop_procedure()
                if 'ws_server' in locals() and ws_server.is_serving():

                    ws_server.close()
                    await ws_server.wait_closed()
            except Exception:
                pass
    
    async def stop_procedure(self):
        """Rotina de limpeza explícita para liberar a porta rápido"""
        # print("🛑 Executando stop_procedure do WebSocket...")
        
        # 1. Cancela a tarefa de check (para não pingar em socket fechando)
        if self.check_conn_task and not self.check_conn_task.done():
            self.check_conn_task.cancel()
            try:
                print("cancelando a check_conn_task")
                await self.check_conn_task
            except asyncio.CancelledError:
                print("cancelei  a check_conn_task")
                pass
        else:
            print("não precisei cancelar a check_conn_task pq ja não existe ou ja está como done.")
        # 2. Desconecta clientes ativos na força (Isso evita o TIME_WAIT)
        # Importamos as conexões do core.utils ou state
        # from PythonServer.utils import connections 
        
        active_clients = connections.active_clients()
        
        for client_register in active_clients:
            group_name, conn_name , conn = client_register
            try:
                # if conn.open:
                print(f"closing conn {group_name} - {conn_name}")
                await conn.close(code=1000, reason="Server Shutdown")
                # else:
                #     print(f"[stop_procedure] connection {group_name}.{conn_name} already closed ")
            except Exception as e:
                print(" deu erro e foi:  ",str(e))

                # pass
        
        # 3. Fecha o servidor
        if self.ws_server:
            try:
                # print("printando atributos do ws_server")
                # print([attr for attr in dir(self.ws_server) if not attr.startswith("_")])
                # print(type(self.ws_server.connections))
                    
                # print(len(self.ws_server.connections))
                if len(self.ws_server.connections)>0:
                    for conn in self.ws_server.connections:
                        print(type(conn))
                ainda_ativas = list(self.ws_server.connections) 
                ###'Server' object has no attribute 'websockets'## está acusando essa linha aqui !!!!
                
                if len(ainda_ativas)>0:
                    print(f"numero de conexões ainda ativas depois do .close() é:",len(ainda_ativas))
                    for ws in ainda_ativas:
                        print(f"conexão ainda ativa depois de eu ter dado .close() nas do active clients e é: {ws}")
                        try:
                            await ws.close()
                        except:
                            pass
                else:
                    print("conexões fecharam direitinho! 0 ativas no momento!")
            except:
                pass

            self.ws_server.close()
            await self.ws_server.wait_closed()
            self.ws_server = None
            print("socket do servidor fechado e liberado.")
        else:
            print("servidor ja foi fechado!")


    async def check_connections(self, period=10):
        """Verifica conexões ativas (Ping/Pong)"""
        while not LifecycleMaster.shutdown_event.is_set():
            try:
                await asyncio.sleep(period)
                if connections.browser.unique:
                    pong_waiter = await connections.browser.unique.ping()
                    await asyncio.wait_for(pong_waiter, timeout=5)
            except asyncio.TimeoutError:
                LifecycleMaster.register_log("⚠️ Conexão browser timeout", "server")
                connections.browser.unique = None
            except asyncio.CancelledError:
                print("cancelled successfully")
                break
            except Exception as e:
                log_error_forensics_plus(e, "Erro no check_connections")
                break
    
    @staticmethod
    def shutdown(a, b):
        print("Sinal de SO recebido (SIGINT/SIGTERM)")
        if not LifecycleMaster.first_shutdown_event.is_set():
            LifecycleMaster.first_shutdown_event.set() # Apenas avisa a thread principal
        else:
            print("ja mandei o sinal de fechamento antes!")
if __name__ == "__main__":
    # Configura sinais de SO
    # for sig in (signal.SIGINT, signal.SIGTERM):
    #     signal.signal(sig, WebSocketServerManager.shutdown)
    try:    
        manager = WebSocketServerManager(watcher_is_internal = True)
        
        # Inicia o runtime via LifecycleMaster
        LifecycleMaster.prepare_for_start_runtime(manager.start())


        LifecycleMaster.prepare_for_start_runtime(watcher_main_function(senderQueue = manager.receiverQueue , receiverQueue = manager.senderQueue))
        # LifecycleMaster.start_runtime(manager.start())
        
        # Bloqueia thread principal
        LifecycleMaster.espera_pelo_tchau()
        # try:
        #     LifecycleMaster.byebye.wait()

        #     print("Aplicação encerrada. Bye bye!")
        # except:
        #     LifecycleMaster.cls.first_shutdown_event.set()
        # free_port(8765)
    except Exception as e:
        print("deu erro fora da main e foi:",str(e))

print("byebye de vez!")
threads_ativas= threading.enumerate()
for thread in threads_ativas:
    if thread is not threading.current_thread() and thread.daemon == False: 

        print(f"Thread potencialmente problemática: {thread.name} (daemon: {thread.daemon})")
# import threading
# import sys
# import traceback    
#     # import traceback

# print("Threads ativas:")
# for thread in threading.enumerate():
#     # print(f"\nThread: {thread.name}")
#     if thread is threading.current_thread():
#         print(str(thread)+"(self)", "daemon:", thread.daemon)        
#     else:
#         print(thread, "daemon:", thread.daemon)


# for thread_id, frame in sys._current_frames().items():
#     print("\nTHREAD ID:", thread_id)
#     traceback.print_stack(frame)