import subprocess
import psutil
import shutil
import time
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from abstractClassBase import BaseWindowBackend
from windowFingerPrint import WindowFingerPrint
from typing import Optional
from sharedResources.generalUtils.aprint import aprint

class LinuxWindowBackend(BaseWindowBackend):
    def __init__(self):
        super().__init__()
        self.has_xdotool = shutil.which("xdotool") is not None
        self.has_wmctrl = shutil.which("wmctrl") is not None
    # requer: wmctrl, xprop; recomendado: xdotool
    def _run(self,cmd):
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    def _normalize_id(self, win_id: str):
        """Converte para formato padronizado 0xXXXXXXXX."""
        if not win_id:
            return None
        win_id = win_id.lower().strip()
        if win_id.startswith("0x"):
            return "0x" + win_id[2:].zfill(8)
        return win_id


    def _get_class_name(self, win_id: str):
        """Obtém o class_name (WM_CLASS), muito mais estável que título."""
        try:
            out = subprocess.check_output(["xprop", "-id", win_id, "WM_CLASS"]).decode()
            match = re.search(r'"([^"]+)"\s*,\s*"([^"]+)"', out)
            if match:
                return match.group(1)  # normal: name
        except Exception:
            pass
        return None


    def enrich_with_process(self, windows):
        for w in windows:
            try:
                proc = psutil.Process(int(w["pid"]))
                w["app"] = proc.name()
            except Exception:
                w["app"] = None

            # add class_name
            w["class_name"] = self._get_class_name(w["id"])
        return windows


    def get_active_window_id(self,lastKnowId):
        sucess = False
        erro = None
        try:
            output = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"]
            ).decode()
            # print("get_active_window_id output var:", output )
            sucess = True
        except subprocess.CalledProcessError as e:
            print(f"[WARN] get_active_window_id failed: {e}")
            erro = e
            # return None
        except KeyboardInterrupt:
            # SIGINT chegou só no subprocess, não no Python
            erro = KeyboardInterrupt
            print("[WARN] SIGINT interrompeu o xprop")
            raise
            
        except Exception as e:
            erro = e
            print("deu exception na get_active_window_id e é:",e)
            log_error_forensics_plus(e)
            # pass
        if not sucess:
            #decido o que fazer com esse erro depois
            return None
        
        
        if "window id #" in output:
            # print("found the string for id in the output var")
            ActiveWindow_ip = output.split("window id #")[-1].strip()
            # print("and it is: ",ActiveWindow_ip)
            
            if ActiveWindow_ip.lower() in ("0x0", "0x00000000"):
                # print("[WARN] Nenhuma janela ativa real detectada")
                # print("[WARN] and the ActiveWindow_ip is:",ActiveWindow_ip)
                # print("[WARN] and the output is: ",output)
                return None
            # Padroniza o formato do ID retornado pelo xprop
            if ActiveWindow_ip.startswith("0x"):
                # print("stripped a part of the ActiveWindow_ip var")
                ActiveWindow_ip = "0x" + ActiveWindow_ip[2:].zfill(8)
            # print("and i'm returning: ",ActiveWindow_ip)
            return ActiveWindow_ip
        else:
            self.log.error("got nothing trying to get the window active id")
        
        return None


    def list_windows(self, printar=False):
        """versão com windowFingerPrint"""
        if not self.has_wmctrl:
            raise RuntimeError("wmctrl não instalado — necessário no Linux")

        windows = []
        try:
            output = subprocess.check_output(["wmctrl", "-l", "-p"]).decode().splitlines()
        except Exception as e:
            # print(f'deu erro no comando  ["wmctrl", "-l", "-p"] e foi: {e}, vou retornar uma lista vazia pras janelas ativas')
            return []
        for line in output:
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue

            win_id, desk, pid, host, title = parts

            # Em alguns casos, o PID vem como "-"
            try:
                pid = int(pid)
            except:
                pid = None

            # Tentamos pegar nome do executável (não 100% confiável)
            try:
                app = psutil.Process(pid).name() if pid else None
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
                xprop_output = subprocess.check_output(["xprop", "-id", win_id]).decode()
                for line in xprop_output.splitlines():
                    if "WM_CLASS" in line:
                        # Exemplo: WM_CLASS(STRING) = "google-chrome", "Google-chrome"
                        class_val = line.split("=")[-1].strip().strip('"')
                        fp.class_name = class_val.split(",")[0].replace('"', '').strip()
                        break
            except:
                pass

            windows.append(fp)

        if printar:
            for w in windows:
                print(w)
            # return None
        
        return windows


    def get_active_window(self,lastKnowId) -> Optional[WindowFingerPrint]:
        """with WindowFingerPrint"""
        active_id = self.get_active_window_id(lastKnowId)
        if not active_id:
            # print("couldn't find an active id")
            return None
        currentWindows = self.list_windows()
        if len(currentWindows)==0:
            return None
        for window in currentWindows:
            if window.win_id.lower() == active_id.lower():
                return window
        print("couldn't find an id that matches the active ID")
        return None
    
    def get_window_by_id(self,Id) -> Optional[WindowFingerPrint]:
        # """with WindowFingerPrint"""
        # active_id = self.get_active_window_id(lastKnowId)
        # if not active_id:
        #     print("couldn't find an active id")
        #     return None
        if Id is None:
            return None
        try:    
            for window in self.list_windows():
                if str(window.win_id).lower() == str(Id).lower():
                    return window
        except Exception as e:
            print(" deu ruim na get_window_by_id e foi:  ",e)
            log_error_forensics_plus(e)
        print("couldn't find a window that matches the ID: ",Id)
        return None




 

    def focus_window(self, win_id, verify=True, timeout=1.2, frequency=0.05):
        """versão nova """
        win_id = self._normalize_id(win_id)

        if not win_id:
            self.log.error("focus_window recebeu win_id inválido")
            return False

        def is_active():
            active = self.get_active_window_id(None)
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
            deadline = time.time() + timeout
            while time.time() < deadline:
                if is_active():
                    return True
                time.sleep(frequency)

            self.log.warning(f"focus_window falhou para {win_id}")

            return is_active()

        return True
 

if __name__ == "__main__":
    print("✅ Janelas abertas:")
    manager = LinuxWindowBackend()
    open_windows = manager.list_windows()
    for w in open_windows:
        print(w)

    active = manager.get_active_window()
    print("\n✅ Janela ativa:")
    if len(open_windows) > 1:
        for window in open_windows:
            # target = open_windows[1]  # exemplo: muda pra segunda janela da lista
            print("\n➡️ Mudando foco para:", window["title"])
            manager.focus_window(window["id"])
            time.sleep(2)

    print(active)


    # def list_windows(self, printar = False):
    #     """versão antiga"""
    #     windows = []
    #     output = subprocess.check_output(["wmctrl", "-l", "-p"]).decode().splitlines()

    #     for line in output:
    #         parts = line.split(None, 4)
    #         if len(parts) < 5:
    #             continue

    #         win_id, desk, pid, host, title = parts
    #         windows.append({
    #             "id": win_id,
    #             "pid": pid,
    #             "title": title,
    #         })
    #     window = self.enrich_with_process(windows)
    #     if printar:
    #         for x in window:
    #             print(x)
    #     else:
    #         return window

    

#    def get_active_window(self):
#         """versão antiga"""
#         active_id = self.get_active_window_id()
#         if not active_id:
#             self.log.error(f"somehow the id was false and it is: {active_id}")
#             return None
#         else:
#             for window in self.list_windows():
#                 if active_id.lower() == window["id"].lower() :
#                     return window
            
#             self.log.error("the id i got was not in any of the active windows ")
#             return active_id

   # def focus_window(self,win_id, verify=True, timeout=1.0,frequency = 0.05):
    #     """versão antiga"""
    #     """
    #     Tenta trazer a janela win_id para frente.
    #     Retorna True se, ao final (ou imediatamente se verify=False), a janela estiver ativa.
    #     Estratégia:
    #     1) wmctrl -ia <winid>
    #     2) xdotool windowactivate --sync <winid> + windowraise <winid> (se disponível)
    #     3) wmctrl -a <title> (tentativa por título, util se win_id variar)
    #     """


    #     win_id = win_id.lower()

    #     # Helper para verificar se virou ativa
    #     def is_active(delay = 0.01):
    #         # time.sleep(delay)
    #         active = self.get_active_window_id()
    #         return active is not None and active.lower() == win_id.lower()

    #     # 1) wmctrl -ia
    #     if shutil.which("wmctrl"):
    #         self._run(["wmctrl", "-ia", win_id])

    #     # Se xdotool disponível, use como fallback/auxiliar (muitas vezes mais confiável)
    #     if not is_active() and shutil.which("xdotool"):
    #         self._run(["xdotool", "windowactivate", "--sync", win_id])
    #         self._run(["xdotool", "windowraise", win_id])

    #     # Outro wmctrl attempt (por segurança) - tentar usar -a com título pode ser útil
    #     # (somente se não ativou) - aqui não sabemos o título, então pulamos por padrão.

    #     # Verificação com retries (intervalo curto)
    #     if verify:
    #         deadline = time.time() + timeout
            
    #         while time.time() < deadline:
    #             if is_active():
    #                 return True
    #             time.sleep(frequency)
    #         # última checagem
    #         return is_active()

    #     return True


    # def list_windows(self, printar=False):
    #     """"esse aqui é o novo"""
    #     if not self.has_wmctrl:
    #         raise RuntimeError("wmctrl não instalado — necessário no Linux")

    #     windows = []
    #     output = subprocess.check_output(["wmctrl", "-l", "-p"]).decode().splitlines()

    #     for line in output:
    #         parts = line.split(None, 4)
    #         if len(parts) < 5:
    #             continue

    #         win_id, desk, pid, host, title = parts
    #         windows.append({
    #             "id": self._normalize_id(win_id),
    #             "pid": pid,
    #             "title": title or "",
    #         })

    #     windows = self.enrich_with_process(windows)

    #     if printar:
    #         for x in windows:
    #             print(x)

    #     return windows


    #   def get_active_window(self):
    #     """nova versão """
    #     active_id = self.get_active_window_id()
    #     if not active_id:
    #         return None

    #     for win in self.list_windows():
    #         if win["id"] == active_id:
    #             return win

    #     return {
    #         "id": active_id,
    #         "pid": None,
    #         "title": None,
    #         "class_name": None,
    #         "app": None
    #     }
  



    # def get_active_window_id(self):
    #     try:
    #         output = subprocess.check_output(
    #             ["xprop", "-root", "_NET_ACTIVE_WINDOW"]
    #         ).decode()

    #         if "window id #" in output:
    #             win_id = output.split("window id #")[-1].strip()
    #             return self._normalize_id(win_id)
    #         return None
    #     except Exception:
    #         return None

    #     return None