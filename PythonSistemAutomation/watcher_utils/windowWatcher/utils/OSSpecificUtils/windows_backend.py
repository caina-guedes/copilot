import time
import psutil
import win32gui
import win32process
import win32con
from typing import Optional

import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
# # print("the basePath is: ",basePath)
sys.path.append(str(basePath))

second_base_path = Path(__file__).resolve().parent.parent
sys.path.append(str(second_base_path))
from PythonSistemAutomation.watcher_utils.windowWatcher.utils.abstractClassBase import BaseWindowBackend
from PythonSistemAutomation.watcher_utils.windowWatcher.utils.windowFingerPrint import WindowFingerPrint

# Mantendo exatamente a mesma herança e decorators que você usa
# from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
# from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class

# @monitor_class
class WindowsWindowBackend(BaseWindowBackend):
    def __init__(self):
        super().__init__()
        # Mesma estrutura de cache do seu arquivo Linux
        self.last_active_windows = []
        self.last_active_windows_last_update = None
        self.last_active_window_ip = None
        self.last_active_window_ip_last_update = None

        self.update_interval = 0.1 
        self.os_call_counter = 0
        self.last_os_request_time = None

    def _increment_call(self):
        self.os_call_counter += 1
        self.last_os_request_time = time.perf_counter()

    def _normalize_id(self, win_id: str):
        """No Windows, win_id é o HWND em hex string."""
        if not win_id:
            return None
        win_id = win_id.lower().strip()
        if win_id.startswith("0x"):
            # Mantemos o zfill(8) para consistência com sua lógica Linux
            return "0x" + win_id[2:].zfill(8)
        return win_id

    def get_active_window_id(self):
        """Sempre chama o SO, mas respeita o intervalo de atualização."""
        if self.last_active_window_ip_last_update is not None:
            time_passed = time.perf_counter() - self.last_active_window_ip_last_update
            if time_passed < self.update_interval:
                return self.last_active_window_ip

        try:
            self._increment_call()
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None
            
            active_id = self._normalize_id(hex(hwnd))
            self.last_active_window_ip = active_id
            self.last_active_window_ip_last_update = time.perf_counter()
            return active_id
        except Exception as e:
            # log_error_forensics_plus(e)
            return None

    def list_windows(self, printar=False):
        """Versão Windows equivalente ao wmctrl -l -p"""
        if self.last_active_windows_last_update is not None:
            time_passed = time.perf_counter() - self.last_active_windows_last_update
            if time_passed < self.update_interval:
                return self.last_active_windows

        windows = []
        
        def enum_handler(hwnd, _):
            # Filtro básico: apenas janelas visíveis e com título (como o wmctrl faz)
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if not title: return

                win_id = self._normalize_id(hex(hwnd))
                
                # Verifica se já conhecemos a janela no cache para economizar processamento
                already_known = False
                if self.last_active_windows:
                    for old_fp in self.last_active_windows:
                        if old_fp.win_id == win_id:
                            windows.append(old_fp)
                            already_known = True
                            break
                
                if not already_known:
                    self._increment_call()
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    
                    try:
                        proc = psutil.Process(pid)
                        # Aplicando a normalização que discutimos (lower e sem .exe)
                        app_name = proc.name().lower().replace(".exe", "")
                    except:
                        app_name = None

                    # O ClassName do Windows é o equivalente ao WM_CLASS
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

    def get_active_window(self) -> Optional[WindowFingerPrint]:
        active_id = self.get_active_window_id()
        if not active_id:
            return None
        
        current_windows = self.list_windows()
        for window in current_windows:
            if window.win_id.lower() == active_id.lower():
                return window
        return None

    def get_window_by_id(self, Id) -> Optional[WindowFingerPrint]:
        """Exatamente a mesma lógica de busca que você tinha no Linux."""
        if Id is None:
            return None
        
        Id = self._normalize_id(str(Id))

        try:
            # 1. Tenta no cache atual
            for window in self.last_active_windows:
                if window.win_id.lower() == Id.lower():
                    return window
            
            # 2. Se não achou, atualiza a lista e tenta de novo
            for window in self.list_windows():
                if window.win_id.lower() == Id.lower():
                    return window
        except Exception as e:
            if hasattr(self, 'log_error_forensics_plus'):
                log_error_forensics_plus(e)
        
        return None

    def focus_window(self, win_id, verify=True, timeout=1.2, frequency=0.05):
        win_id = self._normalize_id(win_id)
        if not win_id: return False

        def is_active():
            active = self.get_active_window_id()
            return active is not None and active.lower() == win_id.lower()

        try:
            hwnd = int(win_id, 16)
            self._increment_call()

            # No Windows, se a janela estiver minimizada, SetForegroundWindow falha.
            # Precisamos restaurar primeiro.
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            
            win32gui.SetForegroundWindow(hwnd)

            if verify:
                deadline = time.perf_counter() + timeout
                while time.perf_counter() < deadline:
                    if is_active():
                        return True
                    time.sleep(frequency)
                return is_active()
            return True
        except Exception:
            return False