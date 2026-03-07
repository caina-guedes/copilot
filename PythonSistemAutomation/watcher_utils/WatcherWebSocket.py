import asyncio
import websockets
import warnings
import json
from PythonServer.serverConfig import serverConfig, connection_types
from PythonSistemAutomation.watcher_utils.GlobalMacroExecutor import GlobalExecutor
# from PythonSistemAutomation.watcher_utils.default_receiving_function import default_receiving_function
from sharedResources.debuggingResources.error_tracker import monitor_error , log_error_forensics_plus
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class

from sharedResources.connection.connectionObject import TwoWayConnection
from PythonSistemAutomation.watcher_utils.websocket_utils.threatHandShake import threatHandShake
logger = LoggerManager.get_logger(__name__)
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster

@monitor_class
class WebSocketClient:
    connection = None
    connected = False

    uri = f"ws://localhost:{serverConfig.serverPort}"
    tipo = {"sender":connection_types['OSwatcherSender'],"receiver":connection_types['OSwatcherReceiver']}
    auto_reconnect = True  # Flag to control auto-reconnect behavior
    reconnecting = False


    system = None # needs preparing
    actions = None  # needs preparing assuming actionDispatch is a dictionary of actions
    comandos = None # needs preparing

    @classmethod
    def prepareClass(cls, system):
        # print("websocket client prepareClass method running")
        cls.system = system
        cls.comandos = []
        #linha abaixo não está sendo usada!
        # cls.actions = system.actions  # Assuming actionDispatch is a dictionary of actions

    @classmethod
    async def handle_not_sent_events(cls):
        # Send all events from the not sent database
        for id,event in await cls.system.not_sent_db.show_not_sent_events(show = True):
            logger.info(f"[{__name__}] Sending event from not sent database: {event}")
            try:
                if not cls.connection:
                    break
                sent = await cls.connection.send(event)
                if sent:
                    try:
                        await cls.system.not_sent_db.delete_event(id)  # Delete the event from not sent database if sent
                        logger.info(f"[{__name__}] ✅ Event sent successfully, deleted from not sent")
                    except Exception as e:
                        log_error_forensics_plus(e)
                        logger.error(f"[{__name__}] ❌ Error deleting event from not sent database: {str(e)}")
            except Exception as e:
                cls._ensure_connection()  # Ensure connection is established before sending
                if not cls.connected:
                    await cls.reconnect()  # Attempt to reconnect if sending fails
                log_error_forensics_plus(e)
                # LoggerManager.log_exception_with_context(f"[CLIENT] ❌ Error sending event from not sent database: {str(e)}")
                logger.info(f"[{__name__}] ❌ Error sending event from not sent database: {str(e)}")

    @classmethod
    async def _ensure_connection(cls):
        if not cls.connected or cls.connection is None:
            logger.info(f"[{__name__}] 🔄 Ensuring connection...")
            await cls.connect()
        return cls.connected

    @classmethod
    async def connectDoubleConnection(cls):
        """ Establishes a connection to the WebSocket server using a two-way connection.
        If the connection is already established, it will close the existing connection
        and create a new one.
        """
        string = f"[CLIENT] 🔄 Attempting to connect to the server..."
        print(string)
        logger.info(string)
        try:
            if cls.connection is None:
                print("Initializing a new TwoWayConnection instance.")
                logger.info("Initializing a new TwoWayConnection instance.")
                cls.connection = TwoWayConnection()
            #starting sender connection
            # print("starting sender connection ")
            try:
                # print("trying to connect the sender")
                sender = await websockets.connect(cls.uri)
                # print("sender connected! starting handshake")
            except Exception as e:
                log_error_forensics_plus(e)
                # print("the exception on the sender connect is: ",e)
            # print("setting sender connection")
            cls.connection.set_sender(sender)
            # print("iniciando handshake")
            await threatHandShake(cls,sender,False)
            # print(" sender handShake finished!")
            # starting receiver connection
            receiver = await websockets.connect(cls.uri)
            # print("trying to connect the receiver!")
            cls.connection.set_receiver(receiver,
                                        handle_message_function = GlobalExecutor.enqueue,
                                        controlsToIgnore = cls.system.controlsToIgnore,
                                        ExecutingMacro = cls.system.ExecutingMacro)
            # print("receiver connected! starting handshake!")
            await threatHandShake(cls,receiver,True)
            # print(" receiver handshake finished!")

            assert cls.connection.sender is not None, "Sender connection was not set properly."
            assert cls.connection.receiver is not None, "Receiver connection was not set properly."
            
            cls.connected = True
            cls.connection.start_receiving()  # Start receiving messages
    
        except ConnectionRefusedError:
            logger.info(f"[{__name__}] ❌ Connection refused while trying to connect.")
            cls.connected = False
        except Exception as e:
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"[CLIENT] ❌ Error connecting to the server: {str(e)}")

    @classmethod
    async def connect(cls):
        """ Establishes a connection to the WebSocket server.
        If the connection is already established, it will close the existing connection
        and create a new one.
        """
        # print("[CLIENT] 🔄 Attempting to connect to the server...")
        # logger.info(f"[CLIENT] 🔄 Attempting to connect to the server...")
        try:
            if cls.connection is None:
                # print("initializing a new twoWayConnection instance")
                # logger.info("Initializing a new TwoWayConnection instance.")
                cls.connection = TwoWayConnection()
            await cls.connectDoubleConnection()

            logger.info(f"[{__name__}] ✅ Conected to the server.")
            if not await cls.system.is_not_sent_db_empty():
                logger.info(f"[{__name__}] Not sent database is not empty, sending events...")
                await cls.handle_not_sent_events()  # Handle not sent events if any
            
                
        except ConnectionRefusedError:
            logger.info('connection refused while trying to connect')
            cls.connected = False
        except Exception as e:
            cls.connected = False
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"[CLIENT] ❌ Error connecting to the server: {str(e)}")
            logger.info(f"[{__name__}] ❌ Failed to connect    {str(e)}")
        
        if not cls.connected and cls.auto_reconnect and not cls.reconnecting:
            task = asyncio.create_task(cls.reconnect(), name = "WebSocketClientReconnectTask")
    @classmethod
    async def reconnect(cls):
        logger.info(f"[{__name__}] 🔄 Attempting to reconnect...")
        
        await cls.stop_loops()
        cls.connection = None
        cls.connected = False
        if cls.reconnecting:
            logger.info(f"[{__name__}] Already reconnecting, skipping new attempt.")
            return
        cls.reconnecting = True  # Set reconnecting flag to True
        while cls.auto_reconnect and not cls.connected:
            logger.info(f"[{__name__}] 🔄 Trying to reconnect...")
            await asyncio.sleep(1)  # Wait before retrying
            try:
                await cls._ensure_connection()
                if cls.connected:
                    logger.info(f"[{__name__}] ✅ Reconnected to the server.")
                    cls.reconnecting = False
                    cls.connection.start_receiving()  # Start receiving messages
                    return True # Exit the loop if reconnected successfully
            except Exception as e:
                log_error_forensics_plus(e)
                return False
                # LoggerManager.log_exception_with_context(f"[CLIENT] ❌ Error reconnecting: {str(e)}")
                # logger.info(f"[{__name__}] ❌ Error reconnecting:  {str(e)}")
        
        cls.reconnecting = False
    
    @classmethod
    def handle_server_message(cls, message):
        print("estou no inicio da handle_server_message do watcherWebSocket e a mensagem é: " , message)
        try:
            parsed = json.loads(message)
            action = parsed.get("acao", None)
            args   = parsed.get("args", None) # The value must be a list of args
            1/0 # inseri erro na força pq acho que essa função não está nem sendo usada, ou pelo menos não deveria!!!!!

            # if action and action in cls.actions:
            #     logger.info(f"action received is: {action}")
            #     result = cls.actions[action](cls.system , args)  # Return the action and value
            #     logger.info(f"[CLIENT] 🎯 received action : {action} => result: {result}")
            #     # Execute the action based on the received data


            # else:
            #     logger.info(f"[{__name__}] Generic message : {str(args)}")
        except json.JSONDecodeError as e:
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context("[CLIENT] ⚠️ Received message is not JSON valid.")
            # logger.info(f"[{__name__}] ⚠️ Received message is not JSON valid.")
        except Exception as e:
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"[CLIENT] ❌ Error handling server message: {str(e)}")
            # logger.info(f"[CLIENT] ❌ Error handling server message: {str(e)}")

    @classmethod
    async def close(cls):
        logger.info("função close do websocket foi chamada !")
        if cls.connection:
            try:
                await cls.connection.close()
                cls.connected = False
                cls.connection = None
                await cls.stop_loops()

                # cls.receive_loop.set_websocket(None) # Clear the websocket in the receive loop
                # await cls.receive_loop.stop()  # Stop the receive loop

                logger.info("Connection closed.")
            except Exception as e:
                log_error_forensics_plus(e)
                logger.error(f"Error closing connection: {str(e)}")
    @classmethod
    async def stop_loops(cls):
        """
        Stops the receive and sender loops.
        """

        logger.info(f"[CLIENT] Stopping receiver loop if exists ...")
        try:
            if isinstance(cls.connection, TwoWayConnection):
                await cls.connection.stop_receiving()
            else:
                print(f"""[WebSocketClient.stop_loops] No TwoWayConnection instance found in cls.connection , 
                            now it is:{type(cls.connection)}  and it's type is: {type(cls.connection)} """)
        
        except Exception as e:
            log_error_forensics_plus(e)
            logger.error(f"error stopping receiver loop: {str(e)}")


LifecycleMaster.register_cleanup_function(WebSocketClient.close, 
                                          priority=80, 
                                          name = "WebSocketClient.close",
                                          register_in_atexit = False)
# Isolated usage example (for testing purposes only)):
if __name__ == "__main__":
    client = WebSocketClient

    async def run(event = []):
        if not event:
            event = {"type": "test", "timestamp": "2025-05-26T20:00:00Z"}
        await client.connect()
        await client.send_event(event)
        await client.close()

    asyncio.run(run())
