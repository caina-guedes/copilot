import subprocess
import time
import signal
import sys
import socket
import threading

from colorama import init, Fore, Style

init(autoreset=True)  # reseta cores automaticamente

PROCESS_COLORS = {
    "SERVER": Fore.GREEN,
    "SERVER_ERR": Fore.RED,
    "WATCHER": Fore.GREEN,
    "WATCHER_ERR": Fore.RED,
    "FRONTEND": Fore.GREEN,
    "FRONTEND_ERR": Fore.RED
}

"""
Configurações do que mostrar no output
"""
onlyErrors = False
whatToShow = {

    "frontEnd": False and (not onlyErrors),
    "frontEndError" : True,
    "server"   : False and (not onlyErrors),
    "serverError"  : False,
    "watcher"  : True and (not onlyErrors),
    "watcherError" : True
}

def stream_output(prefix, stream,show = True):
    color = PROCESS_COLORS.get(prefix, "")  # padrão se algo desconhecido aparecer
    for line in iter(stream.readline, ''):
        if line and show:
            print(f"{color}[{prefix}] {line}\033[0m", end='')


# -------------------------
# Utilitário: espera porta
# -------------------------
def wait_for_port(port, host="127.0.0.1", timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                print(f"[orchestrator] Porta {port} disponível")
                return True
        except OSError:
            time.sleep(0.2)
    return True


# -------------------------
# Start dos processos
# -------------------------
def start_server():
    print("[orchestrator] Iniciando server...")
    p = subprocess.Popen(
        ["python3","-u", "PythonServer/server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    print(f'pro server o whatToShow["server"] é: {whatToShow["server"]}')
    serverThread= threading.Thread(
        target=stream_output,
        args=("SERVER", p.stdout, whatToShow["server"]),
        daemon=True
    )
    serverThread.start()
    serverThread.setName("ServerOutputStreamThread")

    print(f'pro serverErros o whatToShow["serverError"] é: {whatToShow["serverError"]}')
    serverErrorThread = threading.Thread(
        target=stream_output,
        args=("SERVER_ERR", p.stderr, whatToShow["serverError"]),
        daemon=True
    )
    serverErrorThread.start()
    serverErrorThread.setName("ServerErrorStreamThread")

    return p


def start_watcher():
    print("[orchestrator] Iniciando watcher...")
    p = subprocess.Popen(
        ["python3", "-u", "PythonSistemAutomation/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    watcherThread = threading.Thread(
        target=stream_output,
        args=("WATCHER", p.stdout, whatToShow["watcher"]),
        daemon=True
    )
    watcherThread.start()
    watcherThread.setName("WatcherOutputStreamThread")

    watcherErrorThread = threading.Thread(
        target=stream_output,
        args=("WATCHER_ERR", p.stderr, whatToShow["watcherError"]),
        daemon=True
    )
    watcherErrorThread.start()  
    watcherErrorThread.setName("WatcherErrorStreamThread")
    return p


def start_frontend():
    print("[orchestrator] Iniciando frontend...")
    p = subprocess.Popen(
        ["npm", "run", "tauri", "dev"],
        cwd="automation-ui-tauri/src-tauri",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    frontendThread = threading.Thread(
        target=stream_output,
        args=("FRONTEND", p.stdout, whatToShow["frontEnd"]),
        daemon=True
    )
    frontendThread.start()
    frontendThread.setName("FrontEndOutputStreamThread")

    frontendErrorThread = threading.Thread(
        target=stream_output,
        args=("FRONTEND_ERR", p.stderr, whatToShow["frontEndError"]),
        daemon=True
    )
    frontendErrorThread.start()
    frontendErrorThread.setName("FrontEndErrorStreamThread")
    return p




# -------------------------
# Main
# -------------------------
def main():
    processes = []

    try:
        server = start_server()
        processes.append(server)

        if not wait_for_port(8765):
            print("[orchestrator] Server não iniciou a tempo")
            return

        watcher = start_watcher()
        processes.append(watcher)

        frontend = start_frontend()
        processes.append(frontend)

        print("[orchestrator] Sistema em execução")
        frontend.wait()

    except KeyboardInterrupt:
        print("\n[orchestrator] Interrompido pelo usuário")

    finally:
        print("[orchestrator] Encerrando processos...")
        for p in reversed(processes):
            try:
                p.terminate()
            except Exception:
                pass

        for p in processes:
            try:
                p.wait(timeout=5)
            except Exception:
                pass

        print("[orchestrator] Finalizado")


if __name__ == "__main__":
    main()

#     o comando que não deu match foi:  
#     {
#         'equipment': 'mouse', 
#         'action': 'release', 
#         'x': 318, 
#         'y': 352, 
#         'button': 'Button.left'}
# [SERVER]  e a lista de comandos de macro pendentes ja filtrada de forma conveniente é: [
# {'equipment': 'mouse', 
# 'button': 'Button.left', 
# 'action': 'press', 
# 'x': 318, 
# 'y': 352, 
# 'details': None}, 
# {'equipment': 'mouse', 'button': 'Button.left', 'action': 'release', 'x': 318, 'y': 352, 'details': None}, 
# {'equipment': 'keyboard', 'key': 'd', 'action': 'press'}, 
# {'equipment': 'keyboard', 'key': 'd', 'action': 'release'}, 
# {'equipment': 'keyboard', 'key': 'f', 'action': 'press'}, 
# {'equipment': 'keyboard', 'key': 'f', 'action': 'release'}, 
# {'equipment': 'keyboard', 'key': 'g', 'action': 'press'}, 
# {'equipment': 'keyboard', 'key': 'g', 'action': 'release'}]