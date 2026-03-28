import time
import psutil
import win32gui
import win32process
import win32con
from typing import Optional
from pathlib import Path
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
# # print("the basePath is: ",basePath)
sys.path.append(str(basePath))

second_base_path = Path(__file__).resolve().parent.parent
sys.path.append(str(second_base_path))



from PythonSistemAutomation.watcher_utils.windowWatcher.utils.windowFingerPrint import WindowFingerPrint
from abstractClassBase import BaseWindowBackend

# Mantendo sua estrutura de monitoramento
# from sharedResources.debuggingResources.unified_monitor import monitor_class
# @monitor_class 
class WindowsWindowBackend(BaseWindowBackend):
    def __init__(self):
        super().__init__()
        self.last_active_windows = []
        self.last_active_windows_last_update = None
        self.last_active_window_ip = None
        self.last_active_window_ip_last_update = None
        self.update_interval = 0.1
        self.os_call_counter = 0

    
    def _increment_call(self):
        self.os_call_counter += 1
        self.last_os_request_time = time.perf_counter()

    def get_active_window_id(self) -> Optional[str]:
        """Retorna o HWND (Handle) da janela ativa como string hex."""
        if self.last_active_window_ip_last_update:
            if (time.perf_counter() - self.last_active_window_ip_last_update) < self.update_interval:
                return self.last_active_window_ip

        self._increment_call()
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None
        
        # Normalizamos para o mesmo padrão 0xXXXXXXXX que você usa no Linux
        win_id = hex(hwnd)
        self.last_active_window_ip = win_id
        self.last_active_window_ip_last_update = time.perf_counter()
        return win_id

    def list_windows(self) -> list:
        """Lista todas as janelas visíveis usando a Win32 API."""
        if self.last_active_windows_last_update:
            if (time.perf_counter() - self.last_active_windows_last_update) < self.update_interval:
                return self.last_active_windows

        windows = []

        def enum_handler(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                self._increment_call()
                
                # Coleta de dados básicos
                win_id = hex(hwnd)
                title = win32gui.GetWindowText(hwnd)
                
                # PID e Nome do App (via psutil)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                app_name = None
                try:
                    proc = psutil.Process(pid)
                    app_name = normalizar_nome_app( proc.name())
                except:
                    pass

                # No Windows, o 'class_name' é equivalente ao WM_CLASS
                class_name = win32gui.GetClassName(hwnd)

                fp = WindowFingerPrint(
                    os_name="windows",
                    win_id=win_id,
                    pid=pid,
                    app=app_name,
                )
                fp.update_title(title)
                fp.class_name = class_name
                windows.append(fp)

        win32gui.EnumWindows(enum_handler, None)
        
        self.last_active_windows = windows
        self.last_active_windows_last_update = time.perf_counter()
        return windows

    def focus_window(self, win_id: str, verify=True, timeout=1.2, frequency=0.05) -> bool:
        """Foca a janela no Windows. Lida com o detalhe de janelas minimizadas."""
        try:
            hwnd = int(win_id, 16)
            self._increment_call()

            # Se estiver minimizada, restaura
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            # Traz para frente
            win32gui.SetForegroundWindow(hwnd)

            if verify:
                deadline = time.perf_counter() + timeout
                while time.perf_counter() < deadline:
                    if self.get_active_window_id() == win_id:
                        return True
                    time.sleep(frequency)
                return False
            return True
        except Exception as e:
            # log_error_forensics_plus(e)
            return False

    def get_active_window(self) -> Optional[WindowFingerPrint]:
        active_id = self.get_active_window_id()
        if not active_id: return None
        
        for w in self.list_windows():
            if w.win_id == active_id:
                return w
        return None

    def normalizar_nome_app(self, nome):
        return nome.lower().replace(".exe", "")