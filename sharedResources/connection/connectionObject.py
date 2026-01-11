import json
from websockets.exceptions import ConnectionClosedError
import time, traceback

# from websockets import ConnectionClosedError
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.generalUtils.aprint import aprint
import asyncio
import inspect
logger = LoggerManager.get_logger(__name__)
import threading


class TwoWayConnection:
    def __init__(self, sender=None, receiver=None):
        self.sender = sender
        self._sender_lock = asyncio.Lock()
        
        self.receiver = receiver
        
        self._receiver_task = None
        self._receiver_lock = asyncio.Lock()
        self._receiver_task_cancel_event = asyncio.Event()
        self.receiver_loop_running = False

        self.ExecutingMacro = None
        self.controlsToIgnore = None            

        self._handle_message_function = self.send
        self.logger = logger

    def set_handle_message(self, handle_message_function):
        # print("[TwoWayConnection] Setting handle_message_function...")
        if callable(handle_message_function):
            self._handle_message_function = handle_message_function
            # print('got it !!!')
        else:
            raise TypeError("handle_message_function must be callable")

    def set_sender(self, sender):
        LoggerManager.get_logger().info("[TwoWayConnection] Setting sender...")
        self.sender = sender
        

    def set_receiver(self, receiver, handle_message_function= None, controlsToIgnore = None,ExecutingMacro = None ):
        LoggerManager.get_logger().info("[TwoWayConnection] setting receiver function")
        self.receiver = receiver
        self.controlsToIgnore = controlsToIgnore
        self.ExecutingMacro = ExecutingMacro
        if handle_message_function is not None:
            # print("[TwoWayConnection] Setting handle_message_function for receiver...")   
            self.set_handle_message(handle_message_function)

    def start_receiving(self):
        # print("[TwoWayConnection] called start_receiving function")
        # self.receiver.set_websocket()
        if self.receiver:
            if not self._receiver_task or self._receiver_task.done():
                logger.info("[TwoWayConnection] Starting receiver loop task...")
                self._receiver_task_cancel_event.clear()
                try:
                    # with self.receiver_lock: 
                    # print("antes de criar a task do receiver loop")
                    self._receiver_task = asyncio.create_task(self.receiver_loop())
                    # print('acho que a função de começar a receber começou')
                except Exception as e:
                    print("[TwoWayConnection] Failed to start receiver loop task")
                    self.logger.error(f"Failed to start receiver loop task: {e}")
                    # self._receiver_task = None <<<<<<<<<<<< veirificar se é necessário
            else:
                logger.warning("[TwoWayConnection] Receiver task is already running.")
        else:
            self.logger.warning("Receiver is not set, cannot start receiving loop")

    async def is_ws_alive(self, ws):
        # print("[TwoWayConnection] is_ws_alive function")
        return True
    
        # try:
        #     pong = await ws.ping()
        #     await asyncio.wait_for(pong, timeout=3)
        #     return True
        # except Exception:
        #     return False

    async def is_running(self):
        LoggerManager.get_logger().info("[TwoWayConnection] is_running function")
        
        # A verificação de 'open' depende da lib (ex: websockets, aiohttp)
        try:
            # logger.info("!!!!!!!!!!! o tipo do sender é: ",type(self.sender))
            # logger.info('o sender é: ',self.sender, ' o receiver é: ',self.receiver,' o receiver is closed é: ',self.receiver.protocol.closed,' e o sender  closed é:',self.sender.protocol.closed)
            # sender_ok = await self.is_ws_alive(self.sender)
            receiver_ok = await self.is_ws_alive(self.receiver)
            result = self.sender and  self.receiver and receiver_ok 
            if not result:
                print("self.sender é: ",self.sender)
                # print("sender_ok é: ",sender_ok)
                print("self.receiver é: ",self.receiver)
                print("receiver_ok é: ",receiver_ok)
                print("e a união deles retornou ",result)
            return result
        
        except AttributeError:
            logger.info(str(type(self.sender)))
            logger.info(f"o sender é:{self.sender}")
            logger.info(f'o receiver é: {self.receiver}')
            return False


    async def stop_receiving(self):
        if self._receiver_task:
            print("stop_receiving function was called!!!")
            logger.info("[TwoWayConnection] Stopping receiver task...")
            self._receiver_task_cancel_event.set()
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                logger.info("[TwoWayConnection] Receiver task cancelled successfully.")
            self._receiver_task = None
        else:
            logger.info("[TwoWayConnection] No receiver task to cancel.")

    async def receiver_loop(self):
        LoggerManager.get_logger().info("[TwoWayConnection] receiver_loop function called ")
        print("[TwoWayConnection] receiver_loop function called ")
        
        try:
            async with self._receiver_lock:
                if self.receiver_loop_running:
                    print("[TwoWayConnection] Receiver loop already running. Exiting new loop.")
                    logger.warning("[TwoWayConnection] Receiver loop already running. Exiting new loop.")
                    return
                self.receiver_loop_running = True
            logger.info("[TwoWayConnection] Receiver loop started.")
            Error = False
            while not self._receiver_task_cancel_event.is_set() and await self.is_running():
            
                try:
                    # print("antes do receiver lock")
                    message = None
                    async with self._receiver_lock:
                        # print("depois do receiver lock")
                    # logger.info("[TwoWayConnection] Receiver loop is really running...")
                        message = None
                        noError = False
                        try:
                            # message = await asyncio.wait_for(self.receiver.recv(), timeout=5)
                            message = await self.receiver.recv()
                            noError = True
                        # except asyncio.TimeoutError:
                        #     pass
                        except ConnectionClosedError:
                            # message = "the connection was closed"
                            pass
                        except Exception as e:
                            LoggerManager.log_exception_with_context(f"deu exceção recebendo mensagem no receiver e é: {e}",e)
                            # print("deu exceção recebendo mensagem no receiver e é: ",e)
                        # print("ultima linha do receiver lock")
                    # message = await self.receiver.recv()
                    print(f"[RECEIVE LOOP] Received message: {message}")
                    self.logger.info(f"[RECEIVE LOOP] Received message: {message}")
                    if noError:
                        await self._handle_message_from_server(message)
                    else:
                        await asyncio.sleep(1)

                except asyncio.TimeoutError:
                    Error = True
                    logger.info("[TwoWayConnection] Timeout waiting for message, continuing...")
                    continue
                except asyncio.CancelledError:
                    Error = True
                    logger.warning("[TwoWayConnection] Receiver loop was cancelled.")
                    break
                except ConnectionRefusedError:
                    Error = True
                    logger.info("[TwoWayConnection] ConnectionRefusedError: Receiver connection refused, retrying...")
                    
                except ConnectionClosedError:
                    Error = True
                    logger.info("[TwoWayConnection] ConnectionClosedError: Receiver connection closed, retrying...")

                except Exception as e:
                    Error = True
                    print(f"deu exceção no receiver_loop e é : {e}")
                    LoggerManager.log_exception_with_context(f"deu exceção no receiver_loop e é : {e}")
                
                if Error:
                    await asyncio.sleep(1)  # evita loop infinito rápido em caso de falha
                    Error = False
                await asyncio.sleep(0)                    
        except Exception as e:
            LoggerManager.log_exception_with_context(f"deu ruim no receiver_loop {e}")
        finally:
            async with self._receiver_lock:
                self.receiver_loop_running = False
            logger.info("[TwoWayConnection] Receiver loop finished, cleaning up...")

    async def _handle_message_from_server(self, message):
        # print("[TwoWayConnection] _handle_message_from_server function")
        # LoggerManager.get_logger().info("[TwoWayConnection] _handle_message function")
        
        try:
            if self._handle_message_function:
                if inspect.iscoroutinefunction(self._handle_message_function):
                    await self._handle_message_function(message, self.controlsToIgnore,self.ExecutingMacro)
                else:
                    self._handle_message_function(message,self.controlsToIgnore,self.ExecutingMacro)
            else:
                LoggerManager.log("No handler defined for received message")
        except Exception as e:
            LoggerManager.log_exception_with_context(f"deu ruim na _handle_message e foi : {e}")

    async def close(self):
        LoggerManager.get_logger().info("[TwoWayConnection] close function")
        if any([self.sender, self.receiver]):
            try:
                if self.sender:
                    async with self._sender_lock:
                        await self.sender.close()
                        logger.info("[TwoWayConnection] Sender connection actually closed")
                        self.sender = None
                if self.receiver:
                    async with self._receiver_lock:
                        await self.stop_receiving()
                        await self.receiver.close()
                        self.receiver = None
                        print("[TwoWayConnection] Receiver connection actually closed")
            except Exception as e:
                LoggerManager.log_exception_with_context(e)
            finally:
                self.receiver_loop_running = False
        else:
            logger.info("[TwoWayConnection] No connections to close, sender or receiver is None")

            # self.sender = None
        

    async def send(self,message):
        # logger.warning("[TwoWayConnection] send function")

            
        if self.sender:
            logger.info(f"[TwoWayConnection] the sender is:  {self.sender}")
            # error = False
            try:
                # print("right before the sender lock")
                async with self._sender_lock:
                    # print("right after the sender lock")
                    await self.sender.send(json.dumps(message))
                # print("CALL STACK:", traceback.format_stack())

                # print(f"[TwoWayConnection] type of Message sent: {type(json.dumps(message))}")
                # traceback.print_stack(limit=6)
                # print(f"Message sent: {json.dumps(message)}")
                # print(f"[TwoWayConnection {time.time()}] Message sent: {json.dumps(message)}")
                return True

            except ConnectionRefusedError:
                print("[TwoWayConnection] Connection refused, retrying...")
                raise

            except asyncio.TimeoutError:
                print("[TwoWayConnection] Timeout while sending message, retrying...")
                raise

            except json.JSONDecodeError as e:
                print(f"[TwoWayConnection] JSON decode error: {e}")
                raise

            except Exception as e:
                print(f"Error sending message: {e}")
                raise
            # return False

        else:
            print("[TwoWayConnection] No sender connection available, cannot send message")
            # raise  
            # LoggerManager.log_exception_with_context("tried to send message with no sender connection ")
            return False
        


