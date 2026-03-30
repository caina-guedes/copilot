import queue
import warnings




STRICT_MODE = True
if STRICT_MODE:
    warnings.simplefilter("error")
    warnings.filterwarnings(
        "ignore",
        message="unclosed file .*Xauthority.*",
        category=ResourceWarning,
    )


import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# wait_for_data is just a helper function for waiting for data in a queue with a timeout
from sharedResources.generalUtils.wait_for_data import wait_for_data, WaitTimeoutError
# import builtins
# from sharedResources.generalUtils.aprint import aprint  # my assyncronous print function
# builtins.print = aprint # Override the built-in print with asynchronous print
from sharedResources.pythonLoggerSistem.logger import LoggerManager
# LoggerManager.complement_logs_path("PythonSistemAutomation")
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster

from sharedResources.debuggingResources.exec_monitor import CallRegistry
# o lifecycleMaster tem que ser o primeiro aser improtado por causa do print_interceptor!!!!! 
from PythonSistemAutomation.watcher_utils.GlobalMacroExecutor import GlobalExecutor

from PythonSistemAutomation.sistem_utils.Watcher_config import EventObserverConfig
from PythonSistemAutomation.watcher import EventObserver
# from PythonSistemAutomation.watcher_utils.concurrencySafeObjects import ThreadAsyncSafeWrapper
# from PythonSistemAutomation.watcher_utils.event_utils import Event
from PythonSistemAutomation.watcher_utils.WatcherWebSocket import WebSocketClient
import PythonServer.serverConfig as serverConfig
from sharedResources.DataBases.watcherDatabase import WatcherNotsentEventsDatabase
import asyncio 

from sharedResources.lifecycle.shutdownThreadUtils  import TrackedThread 
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class

from sharedResources.lifecycle.printUtils import print_thread_status, print_async_tasks_status
# from sharedResources.debuggingResources.task_monitor import task_monitor
print("começando o watcher!!!!")
        
logger = LoggerManager.get_logger(__name__)

shutDownNotComplete = True

@monitor_class
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
    
    watcher_shutdown_event = LifecycleMaster.first_shutdown_event
    shutDownComplete = LifecycleMaster.shutDownComplete
    shutDownIniciated = False
    main_instance = None


    @staticmethod
    def shutdown(a,b):
        AutomationSystem.myShutdown()

    @classmethod
    def myShutdown(cls):
        """Sets the shutdown event to signal all components to stop."""
        print("AutomationSystem shutdown called.")
        if not cls.watcher_shutdown_event.is_set() and not cls.shutDownIniciated:
            try:
                with LifecycleMaster.shutDownExternalLock:
                    print("Setting watcher shutdown event.")
                    cls.shutDownIniciated = True
                    # cls.shutDownComplete.clear() # reset the event before shutdown
                    # AutomationSystem.main_instance.stop_observer()
                    # Chamadas assíncronas
                    GlobalExecutor.umpress_keys()

                    if LifecycleMaster.run_async( AutomationSystem.main_instance.not_sent_db.close(),name = "not_sent_db.close", protected = True):
                        pass
                    else:
                        print("não entrou no if que eu queria")
                        print("myLoop = ", LifecycleMaster.running_loop.get())
                        print("o loop está fechado é: ", LifecycleMaster.running_loop.is_closed())
                    # await AutomationSystem.main_instance.not_sent_db.close()
                    
                    cls.watcher_shutdown_event.set() # Signal shutdown to all components
                    # Wait for all threads and async tasks to finish
                    print("Waiting for all threads and tasks to finish...")
                    cls.shutDownComplete.wait()
                    CallRegistry.report()
                    print("AutomationSystem shutdown complete.")
            except Exception as e:
                print("deu erro no shutDown do automation system e foi: ",e)
                raise

        else:
            print("Watcher shutdown event is still happening, please wait.")
    
    def __init__(self, not_sent_db, sendingQueue = None,receivingQueue = None):
        
        print(f"inicializando o automationSystem o argumento é: not_sent_db : {not_sent_db}")
        AutomationSystem.main_instance = self
        self.sendingQueue = sendingQueue
        self.receivingQueue = receivingQueue
        # self.actions = serverConfig.SOWatcherActions(not_sent_db).actionDispatch  # Assuming actionDispatch is a dictionary of actions
        self.ExecutingMacro = {"value":False}
        self.controlsToIgnore = set()  # Set of controls to ignore during macro execution
        # print("logo antes de mexer com o websocket!")
        if receivingQueue is not None:
            print("vou iniciar o listener da receivingQueue")
            self.start_listening_receivingQueue()
            print("iniciei o listener da receivingQueue")
        else :
            self.ws_client = WebSocketClient
            self.ws_client.prepareClass(self)
            print("preparei o websocket do watcher pois não recebi queues")

        print("logo antes do observer!")
        self.observer = EventObserver(self,sendingQueue = sendingQueue)
        print("logo depois do observer")
        self.not_sent_db = not_sent_db  # Initialize the database for not sent events
        self._not_sent_db_is_empty_last_check = True  # Flag to check if the database is empty
        
    def start_listening_receivingQueue(self):
        # this task is intended to be cancelled normally by standard procedure using asyncio.CancelledError.

        async def receivingQueue_worker():
            while not self.__class__.watcher_shutdown_event.is_set() :
                # item = q.get(
                try:
                    try:
                        msg = await wait_for_data(self.receivingQueue, timeout=0.2)
                        # msg = self.receivingQueue.get(timeout=0.5)
                    except WaitTimeoutError:
                        continue
                    except asyncio.CancelledError:
                        print("receivingQueue_worker was cancelled.")
                        break
                    GlobalExecutor.enqueue(msg,self.controlsToIgnore,self,self.ExecutingMacro)
                except Exception as e:
                    log_error_forensics_plus(e, extra_message=f"Error in receivingQueue_worker")
                    
        LifecycleMaster.run_async(receivingQueue_worker, name = "watcher_receivingQueue_worker")

    async def is_not_sent_db_empty(self):
        """
        Checks if the not sent events database is empty.
        """
        try:
            quant = await self.not_sent_db.show_not_sent_events(only_quantity=True)
        except Exception as e:
            raise
            # LoggerManager.log_exception_with_context(f"Error checking not sent events database: {e}")
            # logger.error(f"Error checking not sent events database: {e}")
            # raise e
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
            raise
            # LoggerManager.log_exception_with_context(f"Error saving event to database: {e}")
            # logger.info(f"Error saving event to database: {e}")

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
            raise
            # LoggerManager.log_exception_with_context(f"Error deleting event from database: {e}")
            # logger.info(f"Error deleting event from database: {e}")    

    async def initializeWebsocket(self, internalQueue = None):
        """
        Initializes the WebSocket client connection.
        """
        try:
            if internalQueue is not None:
                self.internalQueue = internalQueue
                print('internal queue detected! no websocket needed!')
            else:
                # print("estou no inicializeWebsocket")
                await self.ws_client.connect()
                logger.info("WebSocket client initialized.")
        except Exception as e:
            log_error_forensics_plus(e)
            # LoggerManager.log_exception_with_context(f"Error initializing WebSocket client: {e}")
            # logger.error(f"Error initializing WebSocket client: {e}")
            raise 

    # def set_event_callback(self, callback):
    #     self.observer.set_event_callback(self,callback)

    def start_observer(self):
        self.observer.start()

    # def start_observer_in_thread(self):
    #     # tenho que mudar isso aqui pra TrackedThread
    #     Thread(target=self.start_observer, daemon=True, name = "ObserverThread").start()

    def stop_observer(self):
        self.observer.stop()


async def main(sendinQueue = None,receivingQueue = None):
    # loop = asyncio.get_running_loop()
    # LifecycleMaster.set_loop(loop)
    
    # print("comecei a executar a main function do watcher!")
    try:
        not_sent_db = await WatcherNotsentEventsDatabase.create()  # Initialize the not sent events database
        print("inicializei o not_sent_db")
        autoSystem = AutomationSystem(not_sent_db, sendinQueue, receivingQueue)
        print("inicializei o automationSystem")
        logger.info("Starting event observer...")
        autoSystem.start_observer()
        print("comecei o start_observer")
        if not sendinQueue or not receivingQueue:
            await autoSystem.initializeWebsocket()
            print("comecei o websocket")
        else:
            print("não usarei o websocket pois recebi as queues para comunicação interna")
        LifecycleMaster.register_cleanup_function(autoSystem.stop_observer,
                                                  priority = 100,
                                                  name = "AutomationSistem.stop_observer",
                                                  register_in_atexit = True)
        
        await AutomationSystem.stop_event.wait()  # Aguarda sinal de parada

    
    except Exception as e:
        log_error_forensics_plus( e , extra_message = "Error in main watcher function")
        # print(f"Error in main: {e}")

    finally:
        print("entrou no finally da main...")
        try:
            print()
            GlobalExecutor.umpress_keys()

            if not LifecycleMaster.byebye.is_set():
                print("esperando o byebye")
                if LifecycleMaster.byebye.wait(timeout = 15):
                    print("veio estou saindo")
                else:
                    print(" deu timeout mas estou saindo de qualquer forma")
            else:
                print("byebye ja foi setado então tchau")
        except Exception as e:
            print(f" deu exceção no finally da main e foi: {e}")
            log_error_forensics_plus(e)

        print_thread_status()
        print_async_tasks_status()

if __name__ == "__main__":
    try:
    
        LifecycleMaster.prepare_for_start_runtime(main)
        LifecycleMaster.espera_pelo_tchau()
        
    except Exception as e:
        print(f"deu erro fora da main e foi: {e}")
        warnings.warn(str(e))


    print("byebye de vez!")


    # import threading
    # # import traceback

    # print("Threads ativas:")
    # for thread in threading.enumerate():
    #     # print(f"\nThread: {thread.name}")
    #     if thread is threading.current_thread():
    #         print(str(thread)+"(self)", "daemon:", thread.daemon)        
    #     else:print(thread, "daemon:", thread.daemon)
        # try:
        #     stack = sys._current_frames().get(thread.ident)

        #     if stack:
        #         traceback.print_stack(stack)
        # except Exception as e:
        #     print(f"deu erro na parte do print_stack e foi:{str(e)}")
    # for t in threading.enumerate():
    #     if t is threading.current_thread():
    #         print(str(t)+"(self)", "daemon:", t.daemon)        
    #     print(t, "daemon:", t.daemon)