import psutil
import time
from pathlib import Path
import sys
# pip install pywinauto psutil pywin32 quando estiver no windows

sys.path.append(str(Path(__file__).resolve().parent.parent))
from abstractClassBase import BaseWindowBackend


class WindowsWindowBackend(BaseWindowBackend):
    try:
        from pywinauto import Desktop, Application
        Desktop = Desktop
        Application = Application
    except:
        pass
    def __init__(self):
        super().__init__()
        self.desktop = self.__class__.Desktop(backend="uia")

    def enrich_with_process(self, windows):
        for w in windows:
            try:
                proc = psutil.Process(int(w["pid"]))
                w["app"] = proc.name()
            except Exception:
                w["app"] = None
        return windows

    def list_windows(self, printar=False):
        windows = []
        try:
            for win in self.desktop.windows():
                try:
                    hwnd = win.handle
                    pid = win.process_id()
                    title = win.window_text()

                    if not title.strip():
                        continue

                    windows.append({
                        "id": hex(hwnd),
                        "pid": str(pid),
                        "title": title,
                    })
                except:
                    pass

            windows = self.enrich_with_process(windows)

            if printar:
                for w in windows:
                    print(w)
            return windows

        except Exception as e:
            self.log.error(f"Error listing windows: {e}")
            return []

    def _get_active_window_id(self):
        try:
            import win32gui  # lazy import to avoid issues if not installed
            hwnd = win32gui.GetForegroundWindow()
            return hex(hwnd) if hwnd else None
        except Exception as e:
            self.log.error(f"Error getting active window: {e}")
            return None

    def get_active_window(self):
        active_id = self._get_active_window_id()
        if not active_id:
            return None

        for w in self.list_windows():
            if w["id"].lower() == active_id.lower():
                return w

        return {"id": active_id, "pid": None, "title": None, "app": None}

    def focus_window(self, win_id, verify=True, timeout=1.0, frequency=0.05):
        try:
            hwnd = int(win_id, 16)
        except ValueError:
            self.log.error(f"Invalid window id format: {win_id}")
            return False

        try:
            import win32gui
            import win32con
            import win32com.client

            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%')  # this helps bypass some UAC focus issues

            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

            if not verify:
                return True

            deadline = time.time() + timeout
            while time.time() < deadline:
                active = self._get_active_window_id()
                if active and active.lower() == win_id.lower():
                    return True
                time.sleep(frequency)

            return False

        except Exception as e:
            self.log.error(f"Error focusing window: {e}")
            return False


if __name__ == "__main__":
    manager = WindowsWindowBackend()

    print("✅ Windows detectadas:")
    windows = manager.list_windows(printar=True)

    print("\n✅ Ativa agora:")
    active = manager.get_active_window()
    print(active)

    if len(windows) > 1:
        print("\n➡️ Mudando foco para a segunda janela...")
        manager.focus_window(windows[1]["id"])
        time.sleep(2)
