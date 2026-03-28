import subprocess
import psutil
import shutil
import time
import re
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
# # print("the basePath is: ",basePath)
sys.path.append(str(basePath))

second_base_path = Path(__file__).resolve().parent.parent
sys.path.append(str(second_base_path))


from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class
from abstractClassBase import BaseWindowBackend
from windowFingerPrint import WindowFingerPrint
from typing import Optional
# from sharedResources.generalUtils.a# print import a# print

@monitor_class
class LinuxWindowBackend(BaseWindowBackend):

    def __init__(self):
        super().__init__()
        self.has_xdotool = shutil.which("xdotool") is not None
        self.has_wmctrl = shutil.which("wmctrl") is not None
        #### for caching! #########
        self.last_active_windows =[]
        self.last_active_windows_last_update = None
        
        self.last_active_window_ip = None
        self.last_active_window_ip_last_update = None

        self.update_interval = 0.1 ### 
        self.os_call_counter = 0
        self.last_os_request_time = None
        #######
    # requer: wmctrl, xprop; recomendado: xdotool

    def _run(self,cmd):
        self.os_call_counter +=1
        self.last_os_request_time = time.perf_counter()
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    def _normalize_id(self, win_id: str):
        """Converte para formato padronizado 0xXXXXXXXX."""
        if not win_id:
            return None
        win_id = win_id.lower().strip()
        if win_id.startswith("0x"):
            return "0x" + win_id[2:].zfill(8)
        return win_id

    def check_output(self,args):
        inicio = time.perf_counter()
        out = subprocess.check_output(args).decode()
        self.last_os_request_time = time.perf_counter()
        duration = self.last_os_request_time - inicio
        self.os_call_counter +=1 
        return out, duration
    
    def _get_class_name(self, win_id: str):
        """Obtém o class_name (WM_CLASS), muito mais estável que título."""
        try:
            out , duration = self.check_output(["xprop", "-id", win_id, "WM_CLASS"])
            # out = subprocess.check_output(["xprop", "-id", win_id, "WM_CLASS"]).decode()
            # self.last_os_request_time = time.perf_counter()
            # self.os_call_counter +=1 
            match = re.search(r'"([^"]+)"\s*,\s*"([^"]+)"', out)
            if match:
                return match.group(1)  # normal: name
        except Exception:
            pass
        # print("[_get_class_name] 1 OS call made here")
        return None


    def enrich_with_process(self, windows):
        initial_calls = self.os_call_counter
        for w in windows:
            try:
                proc = psutil.Process(int(w["pid"]))
                self.os_call_counter += 1
                self.last_os_request_time = time.perf_counter()
                w["app"] = proc.name()
            except Exception:
                w["app"] = None

            # add class_name
            w["class_name"] = self._get_class_name(w["id"])
        # print("[enrich_with_process] number of os calls made is: ", self.os_call_counter - initial_calls)
        return windows


    def get_active_window_id(self):
        """
        always calls the SO, expensive
        """
        sucess = False
        erro = None
        initial_calls  = self.os_call_counter
        if self.last_active_window_ip_last_update is not None:
            time_passed = time.perf_counter() - self.last_active_window_ip_last_update
            if time_passed < self.update_interval:
                return self.last_active_window_ip
        try:
            # print("[get_active_window_id] inicio os calls: ",self.os_call_counter )
            output, duration  = self.check_output(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
            # output = subprocess.check_output(
            #     ["xprop", "-root", "_NET_ACTIVE_WINDOW"]
            # ).decode()
            # self.last_os_request_time = time.perf_counter()
            # self.os_call_counter +=1 
            # print("[get_active_window_id] 1 os call made here")


            # # print("get_active_window_id output var:", output )
            sucess = True
        except subprocess.CalledProcessError as e:
            # print(f"[WARN] get_active_window_id failed: {e}")
            erro = e
            # return None
        except KeyboardInterrupt:
            # SIGINT chegou só no subprocess, não no Python
            erro = KeyboardInterrupt
            # print("[WARN] SIGINT interrompeu o xprop")
            raise
            
        except Exception as e:
            erro = e
            # print("deu exception na get_active_window_id e é:",e)
            log_error_forensics_plus(e)
            # pass
        if not sucess:
            #decido o que fazer com esse erro depois
            return None
        
        
        if "window id #" in output:
            # # print("found the string for id in the output var")
            ActiveWindow_ip = output.split("window id #")[-1].strip()
            # # print("and it is: ",ActiveWindow_ip)
            
            if ActiveWindow_ip.lower() in ("0x0", "0x00000000"):
                # # print("[WARN] Nenhuma janela ativa real detectada")
                # # print("[WARN] and the ActiveWindow_ip is:",ActiveWindow_ip)
                # # print("[WARN] and the output is: ",output)
                return None
            # Padroniza o formato do ID retornado pelo xprop
            if ActiveWindow_ip.startswith("0x"):
                # # print("stripped a part of the ActiveWindow_ip var")
                ActiveWindow_ip = "0x" + ActiveWindow_ip[2:].zfill(8)
            # # print("and i'm returning: ",ActiveWindow_ip)
            self.last_active_window_ip = ActiveWindow_ip
            self.last_active_widnows_last_uptate = time.perf_counter()
            # print("[get_active_window_id] fim da função, os calls: ",self.os_call_counter )

            return ActiveWindow_ip
        else:
            self.log.error("got nothing trying to get the window active id")
        
        return None


    def list_windows(self, printar=False):
        """
        versão com windowFinger# print

        sempre executa chamada ao SO!!!
        atualiza a ultima lista alem de retornar ela
        """
        if not self.has_wmctrl:
            raise RuntimeError("wmctrl não instalado — necessário no Linux")
        if self.last_active_windows_last_update is not None:
            time_passed = time.perf_counter() - self.last_active_windows_last_update
            if time_passed < self.update_interval:
                return self.last_active_windows
        windows = []
        # print("[list_windows] inicio os calls: ",self.os_call_counter )
        try:
            first_call_time = time.perf_counter()
            output, first_call_duration = self.check_output(["wmctrl", "-l", "-p"])
            output = output.splitlines()
            # output = subprocess.check_output(["wmctrl", "-l", "-p"]).decode().splitlines()
            # self.last_os_request_time = time.perf_counter()
            # first_call_duration = self.last_os_request_time  - first_call_time
            # self.os_call_counter += 1
            # print("[list_windows] 1 OS call made here, took: ",first_call_duration)
        except Exception as e:
            # # print(f'deu erro no comando  ["wmctrl", "-l", "-p"] e foi: {e}, vou retornar uma lista vazia pras janelas ativas')
            return []
        inicio_do_for = time.perf_counter()
        lista_de_duracoes = []
        for line in output:
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue

            win_id, desk, pid, host, title = parts
            already_know_window = False
            if self.last_active_windows:
                for windowFP in self.last_active_windows:
                    dictWindowFP = windowFP.to_dict()

                    if dictWindowFP["win_id"] == win_id:
                        already_know_window = True
                        # # print("ja conheço essa janela aqui ", windowFP)
                        fp = windowFP
            if not already_know_window:
                # Em alguns casos, o PID vem como "-"
                try:
                    pid = int(pid)
                except:
                    pid = None

                # Tentamos pegar nome do executável (não 100% confiável)
                try:
                    # # print("[list_windows] usando psutil.Process")
                    inicio= time.perf_counter()
                    ########### não estou contando esses pois vi que são beem rápidos! 
                    ####         entre 1  e 2 milésimos
                    app = psutil.Process(pid).name() if pid else None
                    duracao_um = time.perf_counter() - inicio
                    # lista_de_duracoes.append(duracao_um)
                    # # print("demorou: ",duracao)
                except:
                    app = None

                fp = WindowFingerPrint(
                    os_name="linux",
                    win_id=win_id,
                    pid=pid,
                    app=app,
                )

                fp.update_title(title)

                # Extra: tentar pegar WM_CLASS via xprop (informação muito estável)
                try:
                    inicio = time.perf_counter()
                    xprop_output, duracao_dois = self.check_output(["xprop", "-id", win_id])
                    # xprop_output = subprocess.check_output(["xprop", "-id", win_id]).decode()
                    # self.last_os_request_time  = time.perf_counter()
                    
                    # duracao_dois = self.last_os_request_time - inicio
                    # self.os_call_counter += 1
                    lista_de_duracoes.append([duracao_um,duracao_dois])
                    for line in xprop_output.splitlines():
                        if "WM_CLASS" in line:
                            # Exemplo: WM_CLASS(STRING) = "google-chrome", "Google-chrome"
                            class_val = line.split("=")[-1].strip().strip('"')
                            fp.class_name = class_val.split(",")[0].replace('"', '').strip()
                            break
                except:
                    pass
            
            windows.append(fp)
        duracao_do_for = time.perf_counter() - inicio_do_for
        # print("[list_windows] duracao do for: ",duracao_do_for)
        soma_por_etapa =[0,0]
        for index , duracao in enumerate(lista_de_duracoes):
            soma_por_etapa[0]+= duracao[0]
            soma_por_etapa[1]+= duracao[1]
            
            # print(f"a duracao da {index+1}interação: ",duracao)
        # print("a primeira etapa durou: ",soma_por_etapa[0])
        # print("a segunda etapa durou: ",soma_por_etapa[1])
        
        if printar:
            for w in windows:
                pass
                # print(w)
            # return None
        self.last_active_windows = windows 
        self.last_active_widnows_last_uptate = time.perf_counter()
        # print("[list_windows] fim da função, os calls: ",self.os_call_counter )

        return windows


    def get_active_window(self) -> Optional[WindowFingerPrint]:
        """with WindowFinger# print"""
        # print("[get_active_window] inicio os calls: ",self.os_call_counter )
        
        active_id = self.get_active_window_id()
        if not active_id:
            # # print("couldn't find an active id")
            return None
        currentWindows = self.list_windows()
        if len(currentWindows)==0:
            return None
        for window in currentWindows:
            if window.win_id.lower() == active_id.lower():
                # print("[get_active_window] fim da função, os calls: ",self.os_call_counter )
                
                return window
        # print("couldn't find an id that matches the active ID")
        return None
    
    def get_window_by_id(self,Id) -> Optional[WindowFingerPrint]:
        # """with WindowFingerPrint"""
        # active_id = self.get_active_window_id(lastKnowId)
        # if not active_id:
        #     # print("couldn't find an active id")
        #     return None
        if Id is None:
            return None
        try:    
            # print("[get_window_by_id] inicio os calls: ",self.os_call_counter )

            for window in self.last_active_windows:
                if str(window.win_id).lower() == str(Id).lower():
                    # print("[get_window_by_id] fim da função, os calls: ",self.os_call_counter )
                    return window
            for window in self.list_windows():
                if str(window.win_id).lower() == str(Id).lower():
                    # print("[get_window_by_id] fim da função, os calls: ",self.os_call_counter )
                    
                    return window
        except Exception as e:
            # print(" deu ruim na get_window_by_id e foi:  ",e)
            log_error_forensics_plus(e)
        # print("couldn't find a window that matches the ID: ",Id)
        return None

        


 

    def focus_window(self, win_id, verify=True, timeout=1.2, frequency=0.05):
        """versão nova """
        win_id = self._normalize_id(win_id)

        if not win_id:
            self.log.error("focus_window recebeu win_id inválido")
            return False

        def is_active():
            active = self.get_active_window_id()
            return active is not None and active == win_id

        # 1️⃣ wmctrl
        if self.has_wmctrl:
            self._run(["wmctrl", "-ia", win_id])

        # 2️⃣ xdotool (opcional)
        if not is_active() and self.has_xdotool:
            self._run(["xdotool", "windowactivate", "--sync", win_id])
            self._run(["xdotool", "windowraise", win_id])

        # 3️⃣ Espera
        if verify:
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                if is_active():
                    return True
                time.sleep(frequency)

            self.log.warning(f"focus_window falhou para {win_id}")

            return is_active()

        return True
 

if __name__ == "__main__":
    print("✅ Janelas abertas:")

    manager = LinuxWindowBackend()
    print("calls counter  = ",manager.os_call_counter)
    open_windows = manager.list_windows()
    open_windows = manager.list_windows()
    
    for w in open_windows:
        print(w)
        print(type(w))

    active = manager.get_active_window()

    print("calls counter  = ",manager.os_call_counter)
    # print("\n✅ Janela ativa:")
    # if len(open_windows) > 1:
    #     for window in open_windows:
    #         # target = open_windows[1]  # exemplo: muda pra segunda janela da lista
    #         window=window.to_dict()
    #         # print("\n➡️ Mudando foco para:", window["title"])
    #         manager.focus_window(window["win_id"])
    #         time.sleep(2)

    # print(active)
    manager.report_calls()
    