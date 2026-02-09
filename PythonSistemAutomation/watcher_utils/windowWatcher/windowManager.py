import platform
import time 
import sys
import copy
import warnings
from pathlib import Path
basePath = str(Path(__file__).resolve().parent.parent.parent.parent)
print("the basePath is: ",basePath)
sys.path.append(basePath)
from PythonSistemAutomation.watcher_utils.windowWatcher.utils.OSSpecificUtils.windows_backend import WindowsWindowBackend
from PythonSistemAutomation.watcher_utils.windowWatcher.utils.OSSpecificUtils.linux_backend import LinuxWindowBackend
from sharedResources.generalUtils.aprint import aprint  # my assyncronous aprint function
from sharedResources.debuggingResources.error_tracker import monitor_error, log_error_forensics_plus


class WindowManager:
    current_window = None
    lastKnowWindow = None
    lastKnowWindowId = None
    last_check_time = 0
    check_interval = 0.4  # Delay de 400ms entre chamadas ao SO
    last_window_data = None

    def __init__(self):
        system = platform.system().lower()
        if system == "linux":
            self.backend = LinuxWindowBackend()
        elif system == "windows":
            self.backend = WindowsWindowBackend()
        elif system == "darwin":
            print("backend do mac não implementado")
            self.backend = None
            # self.backend = MacWindowBackend()
        else:
            raise Exception(f"Sistema operacional não suportado: {system}")

    @monitor_error
    def should_check(self, event,pressed_keys):
        """
        Decide síncronamente se este evento justifica uma chamada ao SO.
        """
        action = event.get("action")
        etype  = event.get("type")
        key    = str(event.get("key", "")) # Garante que é string

        # 1. MOUSE: Foco no contato inicial
        if etype == "mouse":
            return action in ["press", "click"]
        
        if etype == "keyboard":
        # Regra 1: Teclas especiais (Tab, Alt, Enter, etc)
            if len(key) > 1:
                return True
            
            # Regra 2: Atalhos (Se Ctrl ou Alt estão pressionados, mesmo 'n' pode mudar janela)
            if pressed_keys: # Você já tem esse set!
                if any(m in str(pressed_keys) for m in ["ctrl", "alt", "cmd"]):
                    return True
                    
        return False    
        # 1. Movimentos de mouse são ignorados para economizar SO
        # if event.get("action") == "move":
        #     return False
        
        # 2. Verifica se passou o tempo mínimo (Throttle)
        # agora = time.time()
        # if agora - self.__class__.last_check_time < self.__class__.check_interval:
        #     # Se for uma tecla de sistema (Alt/Tab), ignoramos o timer para ser instantâneo
        #     if event.get("type") == "keyboard" and event.get("key") in ["Key.alt", "Key.tab", "Key.cmd"]:
        #         pass 
        #     else:
        #         return False
        
        # return True

    def list_windows(self,printar = False):
        return self.backend.list_windows(printar)

    def get_window_by_id(self,id= None):

        if id is None:
            id = self.__class__.lastKnowWindowId

        return self.backend.get_window_by_id(id)
    
    @monitor_error
    def get_active_window(self,event,pressed_keys):
        #### has to threat if the window changed in a better way!! but for now it's ok
        try:
            made_os_call = False
            if not self.should_check(event,pressed_keys):
                return None, False, made_os_call
            changed = False
            oldWindow = self.get_window_by_id()
            # oldWindow = copy.deepcopy(self.__class__.lastKnowWindow)
            # print(f"the old window is:{oldWindow}")
            self.__class__.current_window = self.backend.get_active_window()
            made_os_call = True
            if self.__class__.current_window is None:
                # print("o current_window deu None mesmo depois da função de pegar a janela ativa")
                return self.__class__.lastKnowWindow , changed ,made_os_call
            else:
                inicio_da_copia = time.perf_counter()
                self.__class__.lastKnowWindow = copy.copy(self.__class__.current_window)
                # print("a copia do currentWindow demorou: ",time.perf_counter() - inicio_da_copia)
                self.__class__.lastKnowWindowId = self.__class__.lastKnowWindow.win_id
                # print("o id da janela é:", self.__class__.lastKnowWindowId)
                # print("o tipo dele é: ",type(self.__class__.lastKnowWindowId))
            if oldWindow is not None :
                try:
                    oldWindow = oldWindow.to_dict()
                    current = self.__class__.current_window.to_dict()
                    for x in oldWindow:
                        if x not in ["first_seen","last_seen","confidence_score", "priority_fields","details"]:
                            if oldWindow[x] != current[x]:
                                # print(f"o campo que deu diferente foi: {x}")
                                # print(f'e os valores desse campo são: {oldWindow[x]}   e   {current[x]}')
                                changed = True
                    
                    
                except Exception as e:
                    "isso aqui pode falhar por conta do SO"
                    print("deu uma exceção na get_active_window  do windowManager e foi: " , e)
                    print("o oldWindow é:",oldWindow)
                    print("o tipo do oldWindow é:", type(oldWindow))
                    print("o self.__class__.current_window que fica la na classe :",self.__class__.current_window)
                    print("o current é: ",current)
                    print("o tipo do current é: ",type(current))
                    # return self.__class__.current_window, False
                    return None,False,False # para não quebrar a função por fora
            else:
                changed =  True
            return self.__class__.current_window , changed, made_os_call
        except Exception as e:
            print(f"deu ruim na get_active_window do windowManager e foi: {e}")
            # warnings.warn(str(e))
            log_error_forensics_plus(e)

    def focus_window(self, window_id):
        return self.backend.focus_window(window_id)


if __name__ == "__main__":
    a = WindowManager()
    # print(a)
    a.list_windows(True)
    window_list = a.list_windows()

    for window in window_list:
        time.sleep(1)
        a.focus_window(window.win_id)   
        print("a.get_window_by_id() é: ",a.get_window_by_id(window.win_id).win_id)
        print("window.win_id é: ",window.win_id)

        print("eles são iguais deu: ", a.get_window_by_id(window.win_id).win_id == window.win_id)
    
