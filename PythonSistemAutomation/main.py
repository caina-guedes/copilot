
import signal 
import json
import logging
from threading import Thread
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# import builtins
from sharedResources.generalUtils.aprint import aprint  # my assyncronous print function
# builtins.print = aprint # Override the built-in print with asynchronous print

from PythonSistemAutomation.sistem_utils.Watcher_config import EventObserverConfig
from PythonSistemAutomation.watcher import EventObserver
# from PythonSistemAutomation.watcher_utils.concurrencySafeObjects import ThreadAsyncSafeWrapper
# from PythonSistemAutomation.watcher_utils.event_utils import Event
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from PythonSistemAutomation.watcher_utils.WatcherWebSocket import WebSocketClient
import PythonServer.serverConfig as serverConfig
from sharedResources.DataBases.watcherDatabase import WatcherNotsentEventsDatabase
import asyncio 

from sharedResources.lifecycle.shutdownMaster import ShutdownMaster
from sharedResources.lifecycle.shutdownThreadUtils  import TrackedThread 

from sharedResources.lifecycle.printUtils import print_thread_status, print_async_tasks_status
# from sharedResources.debuggingResources.task_monitor import task_monitor

logger = LoggerManager.get_logger(__name__)

shutDownNotComplete = True

class AutomationSystem:
    """AutomationSystem class that manages the event observer and WebSocket client.
    It handles saving events to a database and sending them through a WebSocket connection.
    It also provides methods to start and stop the observer, initialize the WebSocket client,
    and manage events in a queue for sending.
    """
    # about_to_send = ThreadAsyncSafeWrapper(deque()) # Queue for events that are about to be sent
    config = EventObserverConfig()
    current_macro = None  # To store the current macro being recorded
    # sender_task   = None
    stop_event = asyncio.Event() #used in the main function 
    
    watcher_shutdown_event = ShutdownMaster.shutdown_event
    shutDownComplete = ShutdownMaster.shutDownComplete
    shutDownIniciated = False
    main_instance = None

    @classmethod
    def shutdown(cls):
        """Sets the shutdown event to signal all components to stop."""
        print("AutomationSystem shutdown called.")
        if not cls.watcher_shutdown_event.is_set() and not cls.shutDownIniciated:
            try:
                with ShutdownMaster.shutDownExternalLock:
                    print("Setting watcher shutdown event.")
                    # ShutdownMaster.set_loop(loop) # ensure the loop is set
                    cls.shutDownIniciated = True
                    # cls.shutDownComplete.clear() # reset the event before shutdown
                    AutomationSystem.main_instance.stop_observer()
                    LoggerManager.stop_listener()
                    # Chamadas assíncronas
                    if ShutdownMaster.running_loop and not ShutdownMaster.running_loop[0].is_closed():
                        asyncio.run_coroutine_threadsafe(
                            AutomationSystem.main_instance.not_sent_db.close(),
                            ShutdownMaster.running_loop[0]
                        )
                    else:
                        print("não entrou no if que eu queria")
                        print("tem loop = ", ShutdownMaster.running_loop != None)
                        print("o loop está fechado é: ", ShutdownMaster.running_loop.is_closed())
                    # await AutomationSystem.main_instance.not_sent_db.close()
                    
                    cls.watcher_shutdown_event.set() # Signal shutdown to all components
                    # Wait for all threads and async tasks to finish
                    print("Waiting for all threads and tasks to finish...")
                    cls.shutDownComplete.wait()
                    print("AutomationSystem shutdown complete.")
            except Exception as e:
                print("deu erro no shutDown do automation system e foi: ",e)
        else:
            print("Watcher shutdown event is still happening, please wait.")
    
    def __init__(self,loop, not_sent_db):
        AutomationSystem.main_instance = self
        self.loop = loop
        self.actions = serverConfig.SOWatcherActions().actionDispatch  # Assuming actionDispatch is a dictionary of actions
        self.ws_client = WebSocketClient
        self.ExecutingMacro = {"value":False}
        self.controlsToIgnore = set()  # Set of controls to ignore during macro execution
        self.ws_client.prepareClass(self)
        self.observer = EventObserver(loop,self)
        self.not_sent_db = not_sent_db  # Initialize the database for not sent events
        self._not_sent_db_is_empty_last_check = True  # Flag to check if the database is empty
        
    async def is_not_sent_db_empty(self):
        """
        Checks if the not sent events database is empty.
        """
        try:
            quant = await self.not_sent_db.show_not_sent_events(only_quantity=True)
        except Exception as e:
            LoggerManager.log_exception_with_context(f"Error checking not sent events database: {e}")
            logger.error(f"Error checking not sent events database: {e}")
            raise e
            # return self._not_sent_db_is_empty_last_check
        if quant == 0:
            self._not_sent_db_is_empty_last_check = True
        else:
            self._not_sent_db_is_empty_last_check = False
        return self._not_sent_db_is_empty_last_check
        
        
    async def save_event(self, event):
        """
        Saves an event to the not sent events database and 
        to the about_to_send queue.
        """
        logger.info('the event to be saved is: ', event)
        try:
            if isinstance(event,str):
                event = json.loads(event)
            event['id'] = None  # Initialize id to None
            self.__class__.about_to_send.append(event)  # Add the event back to the queue for sending
            event['id'] = await self.not_sent_db.save_event(event,retrieve_id=True)
            if event['id'] is not None:
                logger.info(f"Event saved to database: {event}")

            else:
                logger.info("Event not saved to database, id is None.")

        except Exception as e:
            LoggerManager.log_exception_with_context(f"Error saving event to database: {e}")
            logger.info(f"Error saving event to database: {e}")

    async def delete_event(self, event_id):
        """ Deletes an event from the not sent events database and 
        removes it from the about_to_send queue.
        """
        try:
            if await self.not_sent_db.delete_event(event_id):
                logger.info(f"Event with id {event_id} deleted from database.")
                # Remove the event from the about_to_send queue
                # async with self.about_to_send_lock:
                # self.__class__.about_to_send = ThreadAsyncSafeWrapper([event for event in self.__class__.about_to_send if event.get('id') != event_id])
        except Exception as e:
            LoggerManager.log_exception_with_context(f"Error deleting event from database: {e}")
            logger.info(f"Error deleting event from database: {e}")    

    async def initializeWebsocket(self):
        """
        Initializes the WebSocket client connection.
        """
        try:
            # print("estou no inicializeWebsocket")
            await self.ws_client.connect()
            logger.info("WebSocket client initialized.")
        except Exception as e:
            LoggerManager.log_exception_with_context(f"Error initializing WebSocket client: {e}")
            logger.error(f"Error initializing WebSocket client: {e}")
            raise e

    def set_event_callback(self, callback):
        self.observer.set_event_callback(self,callback)

    def start_observer(self):
        self.observer.start()

    def start_observer_in_thread(self):
        Thread(target=self.start_observer, daemon=True, name = "ObserverThread").start()

    def stop_observer(self):
        self.observer.stop()



async def main():
    loop = asyncio.get_running_loop()
    ShutdownMaster.set_loop(loop)
    not_sent_db = await WatcherNotsentEventsDatabase.create()  # Initialize the not sent events database
    


    # Captura Ctrl+C ou sinal de término
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, AutomationSystem.shutdown)

    autoSystem = AutomationSystem(loop,not_sent_db)

    try:
        logger.info("Starting event observer...")
        autoSystem.start_observer_in_thread()
        await autoSystem.initializeWebsocket()
        await AutomationSystem.stop_event.wait()  # Aguarda sinal de parada

    # except KeyboardInterrupt:
    #     print("KeyboardInterrupt received, shutting down...")
    #     AutomationSystem.shutdown(loop)
    except Exception as e:
        print(f"Error in main: {e}",level=logging.critical)
    finally:
        print("Finalizing system...")
        print_thread_status()
        print_async_tasks_status()
        # autoSystem.stop_observer()
        # await not_sent_db.close()
        # LoggerManager.stop_listener()
        print_thread_status()
        print_async_tasks_status()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # try:
    #     asyncio.run(main())
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
            print("stopped observer.")
    finally:
        loop.run_until_complete(ShutdownMaster.byebye.wait())
        loop.close()
        print("bye bye")
        # print("beginning shutdown Process")
        # while shutDownNotComplete:
        #     if AutomationSystem.shutdown_event.is_set() is False:
        #         print("shutdownEvent set!")
        #         AutomationSystem.shutdown_event.set()
        #     print("sleeping while shuttingdown")
        #     print_thread_status()
        #     time.sleep(1)
            

    print("Aplicação encerrando...")
    # LoggerManager.stop_listener() 
