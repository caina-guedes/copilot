import threading
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.trackedItem import TrackedItem
from sharedResources.lifecycle.cleanup_function import  execute_cleanup_function

# -------------------- Thread wrapper --------------------
class TrackedThread(threading.Thread):
    threadsMap = None
    cleanup_event = None
    register_log = None
    shutdown_event = None
    running_loop = None 
    problematicThreads  = []


    @classmethod
    def set_running_loop(cls,loop):
        if cls.running_loop is None:
            cls.running_loop = loop
            print("setei o loop na classe da thread e é: ",loop)
        else:
            print("ja tem loop setado aqui! não vou setar outro!")
   
    @classmethod
    def set_threadsMap(cls,map):
        """"""
        if cls.threadsMap is None:
            cls.threadsMap = map
        else: print("[TrackedThread] threadsMap already set!")
    
    @classmethod
    def set_default_cleanup_event(cls,event):
        """used to set the cleanup event for all threads"""
        if cls.cleanup_event is None:
            cls.cleanup_event = event
        else: 
            print("[TrackedThread] cleanup_event already set!")
        
    @classmethod
    def set_register_log(cls,register:callable):
        if cls.register_log is None:
            cls.register_log = register
        else:
            print("[TrackedThread] register_log already set!")
    
    @classmethod
    def safe_join(cls, thread_obj, timeout=2):
        cls.register_log(f"[Shutdown] Waiting thread {thread_obj.name} to exit...","threads")
                    
        try:
            thread_obj.join(timeout)
        except Exception as e:
            cls.register_log(f"[Shutdown] join erro: {e}", "threads")
        finally:
            if thread_obj.is_alive():
                cls.register_log(f"[Shutdown] Thread {thread_obj.name} ainda viva após timeout", "threads")

                return False
            else:
                cls.register_log(f"[Shutdown] Thread {thread_obj.name} finalizada", "threads")
                return True

    def __init__(self, target, name, created_from,daemon = False,cleanup_event = None ,cleanup_function = None, *args, **kwargs):
        """created_from é um campo pra que eu consiga humanamente entender onde ela foi criada por exemplo:
            "EventBuffer.start" 
            ou algo parecido.
            vai ser uma string capaz de me fazer entender o contexto e onde localizar no codigo
        """
        super().__init__(target = target, 
                         name   = name, 
                         daemon = daemon,  
                         args   = args, 
                         kwargs = kwargs)
        
        selfCleanUpEvent = cleanup_event if cleanup_event is not None else self.__class__.shutdown_event #pensado para fazer operações internas de limpeza na thread
        selfCleanUpEventUse = False #se a thread vai usar o evento de self cleanup
        internalTrackedThread = TrackedItem(
            self,
            selfCleanUpEvent, 
            selfCleanUpEventUse,
            name = name, 
            kind = "thread",
            created_from = created_from, 
            cleanup_function = cleanup_function) 
        if name:
            self.__class__.threadsMap.setdefault(name, []).append(internalTrackedThread)
        else:
            print("thread veio com nome que deu false e foi: ",name," registrando como 'unnamedThread'")
            self.__class__.threadsMap.setdefault("unnamedThread", []).append(internalTrackedThread)
        self.__class__.register_log(f"[Thread Created] {self.name}","threads")
        # # logger.info(f"[Thread Created] {self.name}")

    def run(self):
        self.__class__.register_log(f"[Thread Started] {self.name}","threads")
        
        # logger.info(f"[Thread Started] {self.name}")
        try:
            super().run()
        finally:
            self.__class__.register_log(f"[Thread Exited] {self.name}","threads")
            # logger.info(f"[Thread Exited] {self.name}")
            if self.name in self.__class__.threadsMap:
                self.__class__.threadsMap[self.name] = [
                    t for t in self.__class__.threadsMap[self.name] if t.obj != self
                ]
                if not self.__class__.threadsMap[self.name]:
                    del self.__class__.threadsMap[self.name]

    @classmethod
    def personalized_stop(cls, clean_event,clean_function):
        worked = False
        if clean_event != cls.shutdown_event: # has personalized shutdown event
            # print("[Shutdown] this thread has personalized shutdown!")
            if not clean_event.is_set():
                cls.register_log("[Shutdown] setting it now!","threads")
                clean_event.set()
                worked = True
            else:
                cls.register_log("[Shutdown] but is already set!","threads")

        if callable(clean_function): # has personalized shutdown function
            cls.register_log("[Shutdown] trying to execute cleanup_function!","threads")
            execute_cleanup_function(clean_function,cls.running_loop[0])
            worked = True
        return worked

    @classmethod
    def shutdown_threads(cls, timeout = 2):
        cls.register_log("[Shutdown] Signaling all threads to stop...","general")
        
        if len(cls.threadsMap)<1:
            cls.register_log("threadsMap está vazia no shutdown")
        else:
            print("o tamanho do threadsMap é: ",len(cls.threadsMap))

        for name, threads in list(cls.threadsMap.items()):
            for tracked in threads:
                thread_obj, clean_event, use_flag , clean_function = tracked.obj, tracked.cleanup_event, tracked.cleanup_enabled, tracked.cleanup_function
                personalized_worked = cls.personalized_stop(clean_event,clean_function)

                if thread_obj.is_alive(): # is still active
                    if not  cls.safe_join(thread_obj):
                        cls.problematicThreads.append([name,tracked])

                    
            # Limpa a lista
            try:
                print("[Shutdown] trying to clean the threads Registry")
                cls.threadsMap[name] = [t for t in threads if t.obj.is_alive()]
                if not cls.threadsMap[name]:
                    del cls.threadsMap[name]
                print("[Shutdown] got it !")
            except Exception as e:
                print("[Shutdown] deu erro e foi:  ",e)
        print("[Shutdown] All threads signaled.")
        if len(cls.problematicThreads)>0:
            print("tem thread dando problema e é:")
            for uncooperativeThread in cls.problematicThreads:
                print("o nome da thread problemática é: " ,uncooperativeThread[0], "e ela é: " , uncooperativeThread[1])
        else:
            print("todas as threads cooperaram direitinho!")                
        # logger.info("[Shutdown] All threads signaled.")
    # ShutdownMaster.set_thread_shutdown_function(shutdown_threads)
