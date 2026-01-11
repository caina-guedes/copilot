import threading
from sharedResources.generalUtils.aprint import aprint
import time 


class KeyRef:
    def __init__(self, value):
        self.value = value

class serverConfig:
    """Central configuration for the software"""
    _threading_rlock = threading.RLock()
    serverPort = 8765
    # Comandos especiais de teclado
    specialCommands = {
        "ExecCurrentMacro": KeyRef("f2"),
        "toggleRecording": KeyRef("f1"),
        "stopExecutingMacro": KeyRef("esc"),
    }

    # Configurações de macro
    class MacroConfig:
        
        # multi-threading lock for safety
        _threading_lock = threading.RLock()

        isRecording: bool            = False
        requestToExecuteMacro: bool  = False
        currentMacro: any            = None
        currentPendingCommands: any  = {'current':None}
        macroRecordingId: int | None = None
        macroRunningId: int | None   = None
        stopRunningMacroFlag: bool   = False
        startMacroTime               = None
        stopMacroTime                = None
        # Special keys
        execMacroKey                 = None
        stoppingKey                  = None
        
        checkWindow                  = True

        @classmethod
        def set_flag(cls, name, value):
            with cls._threading_lock:
                if hasattr(cls, name):
                    setattr(cls, name, value)
                else:
                    raise AttributeError(f"{name} não existe em MacroConfig")

        @classmethod
        def get_flag(cls, name):
            with cls._threading_lock:
                if hasattr(cls, name):
                    return getattr(cls, name)
                else:
                    raise AttributeError(f"{name} não existe em MacroConfig")
    # Configurações de flush/buffer
    class FlushConfig:
        batchSize: int = 100
        flushInterval: int = 2  # seconds
        minimumTimeForEventToBeFlushed: int = 1  # seconds

    # Outros parâmetros globais
    debug: bool = False

    @classmethod
    def getSpecialCommand(cls, name: str):
        """Retorna o valor de um comando especial"""
        with cls._threading_rlock:
            ref = cls.specialCommands.get(name)
            return ref.value if ref else None
    
    
    @classmethod
    def setSpecialCommand(cls, name: str, value: str):
        """Define o valor de um comando especial"""
        with cls._threading_rlock:
            if name in cls.specialCommands:
                cls.specialCommands[name].value = value
            else:
                print(f"Comando especial '{name}' não encontrado.")
    
    @classmethod
    def get_flag(cls,name):
        with cls._threading_rlock:
            if hasattr(cls,name):
                return getattr(cls,name)
            else:
                raise AttributeError(f"serverConfig has no attribute named {name}")

    @classmethod
    def set_flag(cls,name,value):
        with cls._threading_rlock:
            if hasattr(cls,name):
                setattr(cls,name,value)
            else:
                raise AttributeError(f"serverConfig has no attribute named {name}")

    # Inicializa os comandos especiais na MacroConfig
    MacroConfig.set_flag("execMacroKey",specialCommands["ExecCurrentMacro"])
    MacroConfig.set_flag("stoppingKey",specialCommands["stopExecutingMacro"])


# Exemplo de uso
if __name__ == "__main__":
    print("Tecla para executar macro:", serverConfig.MacroConfig.execMacroKey)
    print("Batch size:", serverConfig.FlushConfig.batchSize)



class SOWatcherActions:
    """Actions for the SOWatcher WebSocket client."""
    # StartWatcher = "StartWatcher"
    # StopWatcher = "StopWatcher"
    # StartBackgroundRecording = "StartBackgroundRecording"
    # StopBackgroundRecording = "StopBackgroundRecording"
    # StartMacroRecording = "StartMacroRecording"
    # stopExecutingMacro = "stopExecutingMacro"
    # StopMacroRecording = "StopMacroRecording"
    # GetCurrentMacro = "GetCurrentMacro"
    # ClearCurrentMacro = "ClearCurrentMacro"
    # GetConfig = "GetConfig"
    # ChangeConfig = "ChangeConfig"

    def ExecCurrentMacroHasCondition(self):
        return True 
    def StopMacroRecordingHasCondition(self):
        return True
    def stopExecutingMacroHasCondition(self):
        return True
    def StartMacroRecordingHasCondition(self):
        return True
    def StopBackgroundRecordingHasCondition(self):
        return True
    
    def StartBackgroundRecordingHasCondition(self):
        return True
    
    def StopWatcherHasCondition(self):
        return True
    
    def StartWatcherHasCondition(self):
        return True
    
    def ClearCurrentMacroHasCondition(self):
        return True
    
    def GetConfigHasCondition(self):
        return True
    
    def ChangeConfigHasCondition(self):
        return True
    
    def get_stopKeyHasCondition(self):
        return True

    def set_stopKeyHasCondition(self):
        return True
    
    def toggleRecordingHasCondition(self):
        return True

    def __init__(self):

        self.actionConditions = {
        "StartWatcher": self.StartWatcherHasCondition, # has condition
        "StopWatcher": self.StopWatcherHasCondition, # has condition
        "StartBackgroundRecording": self.StartBackgroundRecordingHasCondition, # has condition
        "StopBackgroundRecording": self.StopBackgroundRecordingHasCondition, # has condition
        "StartMacroRecording": self.StartMacroRecordingHasCondition, # has condition
        "stopExecutingMacro": self.stopExecutingMacroHasCondition , #has condition
        "StopMacroRecording": self.StopMacroRecordingHasCondition, # has condition
        "ExecCurrentMacro": self.ExecCurrentMacroHasCondition, # has condition
        "ClearCurrentMacro": self.ClearCurrentMacroHasCondition, # has condition
        "GetConfig": self.GetConfigHasCondition, # has condition
        "ChangeConfig": self.ChangeConfigHasCondition, # has condition
        "get_stopKey": self.get_stopKeyHasCondition, # has condition
        "set_stopKey": self.set_stopKeyHasCondition, # has condition
        "toggleRecording": self.toggleRecordingHasCondition # só para constar essa string na lista de comandos
        }

        self.actionDispatch = {
        "StartWatcher": self.StartWatcherFunction,

        "StopWatcher": self.StopWatcherFunction,
        "StartBackgroundRecording": self.StartBackgroundRecordingFunction,
        "StopBackgroundRecording": self.StopBackgroundRecordingFunction,
        "StartMacroRecording": self.StartMacroRecordingFunction,
        "stopExecutingMacro": self.stopExecutingMacro, 
        "StopMacroRecording": self.StopMacroRecordingFunction,
        "ExecCurrentMacro": self.ExecCurrentMacroFunction,
        "ClearCurrentMacro": self.ClearCurrentMacroFunction,
        "GetConfig": self.GetConfigFunction,
        "ChangeConfig": self.ChangeConfigFunction,
        "get_stopKey": self.get_stopKey,
        "set_stopKey": self.set_stopKey,
        "toggleRecording": self.toggleRecording # só para constar essa string na lista de comandos
        
    }
    
    def stopExecutingMacro(self,*args,**kargs):
        if not serverConfig.MacroConfig.get_flag("stopRunningMacroFlag"):
            serverConfig.MacroConfig.set_flag("stopRunningMacroFlag",True)
            

    def toggleRecording(self,*args,**Kargs):
        try:
            print("comecei a função toggle recording")
            current = serverConfig.MacroConfig.get_flag("isRecording")
            new_state = not current
            serverConfig.MacroConfig.set_flag("isRecording", new_state)
            # serverConfig.MacroConfig.isRecording = not serverConfig.MacroConfig.isRecording
            # print(args)
            # print(args[0])
            macro_time = args[0].get("MacroTime") if args else str(time.time())
            if serverConfig.MacroConfig.isRecording:
                serverConfig.MacroConfig.set_flag("startMacroTime" , macro_time)
                print(f"o valor de startMacroTime é {serverConfig.MacroConfig.startMacroTime} e o tipo é {type(serverConfig.MacroConfig.startMacroTime)}")
            else:
                serverConfig.MacroConfig.set_flag("stopMacroTime" , macro_time)
                print(f"o valor de stopMacroTime é {serverConfig.MacroConfig.stopMacroTime} e o tipo é {type(serverConfig.MacroConfig.stopMacroTime)}")
            print(f'consegui mexer no Isrecording do serverConfig e agora ele é {serverConfig.MacroConfig.isRecording}')
        except Exception as e:
            print(f"Error toggling recording: {e}")
    

    
    def ExecCurrentMacroFunction(self , *args,**kargs):
        """Get the current macro."""
        try:
            serverConfig.MacroConfig.set_flag("requestToExecuteMacro", True)
            
        except Exception as e:
            print(f"Error getting current macro: {e}")
            return None

    
    def StartWatcherFunction(self, *args,**kargs):
        """Start the watcher."""
        try:
            # print("Starting watcher...")
            # system.observer.start()
            # return True
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
        except Exception as e:
            print(f"Error starting watcher: {e}")
            return False

    def StopWatcherFunction(self,*args,**kargs):
        """Stop the watcher."""
        try:
            print("Stopping watcher...")
            # ainda preciso implementar!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            return True
        except Exception as e:
            print(f"Error stopping watcher: {e}")
            return False
        
        

    def get_stopKey(self, *args,**kargs):
        """Get the stop key for the watcher."""
        try:
            print("Retrieving stop key...")
            return self.get_stopKey
        except Exception as e:
            print(f"Error getting stop key: {e}")
            return None


    def set_stopKey(self,*args,**kargs):
        """Set the stop key for the watcher."""
        try:
            if len(args) > 0:
                new_stop_key = args[0]
                # ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1
                print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
                print(f"Stop key set to: {new_stop_key}")
                return True
            else:
                print("No stop key provided.")
                return False
        except Exception as e:
            print(f"Error setting stop key: {e}")
            return False


    def StartBackgroundRecordingFunction(self, *args,**kargs):
        """Start background recording."""
        try:
            #ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
            return True
        except Exception as e:
            print(f"Error starting background recording: {e}")
            return False

    
    def StopBackgroundRecordingFunction(self, *args,**kargs):
        """Stop background recording."""
        try:
            #ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
            return True
        
        except Exception as e:
            print(f"Error stopping background recording: {e}")
            return False


    
    def StartMacroRecordingFunction(self , *args,**kargs):
        """Start recording a macro."""
        try:
            #ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
            return True
        
        except Exception as e:
            print(f"Error starting macro recording: {e}")
            return False

    
    def StopMacroRecordingFunction(self , *args,**kargs):
        """Stop the macro recording."""  
        try:
            #ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
            return True
        
        except Exception as e:
            print(f"Error stopping macro recording: {e}")
            return False  
        
    def ClearCurrentMacroFunction(self , *args,**kargs):
        """Clear the current macro."""
        try:
            print('ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1')
            #     if system.observer._current_macro is not None:
            #         print("Clearing current macro...")
            #         system.observer.clear_current_macro()
            #         return True
            #     else:
            #         print("No current macro to clear.")
            #         return False
            
        except Exception as e:
            print(f"Error clearing current macro: {e}")
            return False

    
    def GetConfigFunction(self ,*args,**kargs):
        """Get the current configuration of the watcher."""
        try:
            # print("Retrieving current configuration...")
            # return system.observer.config
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!1")
        except Exception as e:
            print(f"Error getting configuration: {e}")
            return None

    
    def ChangeConfigFunction(self , *args,**kargs):
        """Change the configuration of the watcher.
        it expects a dictionary with the new configuration values."""
        try:
            # system.observer.config.update_config(*args,**kargs)
            # print("Configuration updated successfully.")
            # return True
            print("ainda tenho que implementar essa parte !!!!!!!!!!!!!!!")
        except Exception as e:
            print(f"Error changing configuration: {e}")
            return False



connection_types = {
    "OSwatcherSender"   : "Operating System Watcher Sender",
    "OSwatcherReceiver" : "Operating System Watcher Receiver",
    "ping": "Ping to check connection",
    "extension": "Browser Extension",
    "front_end": "front_end",
}

mouseMovementMinimumDelay = 0.75
