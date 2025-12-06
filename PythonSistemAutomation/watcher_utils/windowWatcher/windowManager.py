import platform
import time 
import sys
import copy
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
from utils.OSSpecificUtils.linux_backend import LinuxWindowBackend
from sharedResources.generalUtils.aprint import aprint  # my assyncronous aprint function
# from .windows_backend import WindowsWindowBackend
# from .mac_backend import MacWindowBackend


class WindowManager:
    current_window = None
    lastKnowWindow = None
    lastKnowWindowId = None

    def __init__(self):
        system = platform.system().lower()
        if system == "linux":
            self.backend = LinuxWindowBackend()
        elif system == "windows":
            self.backend = WindowsWindowBackend()
        elif system == "darwin":
            self.backend = MacWindowBackend()
        else:
            raise Exception(f"Sistema operacional não suportado: {system}")

        
    def list_windows(self,printar = False):
        return self.backend.list_windows(printar)

    def get_window_by_id(self,id= None):
        if id is None:
            id = self.__class__.lastKnowWindowId

        return self.backend.get_window_by_id(id)
    
    def get_active_window(self):
        #### has to threat if the window changed in a better way!! but for now it's ok
        changed = False
        oldWindow = self.get_window_by_id()
        # oldWindow = copy.deepcopy(self.__class__.lastKnowWindow)
        # print(f"the old window is:{oldWindow}")
        self.__class__.current_window = self.backend.get_active_window(self.__class__.lastKnowWindowId)
        
        if self.__class__.current_window is None:
            print("o current_window deu None mesmo depois da função de pegar a janela ativa")
            return self.__class__.lastKnowWindow , changed 
        else:
            self.__class__.lastKnowWindow = copy.deepcopy(self.__class__.current_window)
            self.__class__.lastKnowWindowId = copy.deepcopy(self.__class__.lastKnowWindow.win_id)
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
                print("deu uma exceção na la get_active_window e foi: " , e)
                print("o oldWindow é:",oldWindow)
                print("o tipo do oldWindow é:", type(oldWindow))
                print("o self.__class__.current_window que fica la na classe :",self.__class__.current_window)
                print("o current é: ",current)
                print("o tipo do current é: ",type(current))
                # return self.__class__.current_window, False
                return False
        else:
            changed =  True
        return self.__class__.current_window , changed

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
    
