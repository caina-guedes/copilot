import subprocess
import time
import signal
import sys
import socket
import threading
import psutil

from colorama import init, Fore, Style

_STDOUT_LOCK = threading.Lock()
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
    "serverError"  : True,
    "watcher"  : True and (not onlyErrors),
    "watcherError" : True
}

def stream_output(prefix, stream,show = True):
    color = PROCESS_COLORS.get(prefix, "")  # padrão se algo desconhecido aparecer
    for line in iter(stream.readline, ''):
        if not line or not show:
            continue

        msg = f"{color}[{prefix}] {line}\033[0m"

        with _STDOUT_LOCK:
            print(msg, end='', flush=True)
        # if line and show:

        #     print(f"{color}[{prefix}] {line}\033[0m", end='')


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

def check_port_in_use(port: int, host="0.0.0.0"):
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port:
            return conn
    return None


def free_port(port: int):
    conn = check_port_in_use(port)

    if not conn:
        print(f"[OK] Porta {port} está livre")
        return

    pid = conn.pid

    # CASO 1: TIME_WAIT ou Sem Permissão
    if pid is None:
        print(f"[WARN] Porta {port} está ocupada (Status: {conn.status}), mas não consegui identificar o PID.")
        print("[HINT] Pode ser uma conexão em TIME_WAIT ou falta de permissão (tente rodar como sudo).")
        # Não temos como matar um processo sem PID. 
        # Se for TIME_WAIT, só esperando.
        return
    try:
        proc = psutil.Process(pid)
        print(
            f"[WARN] Porta {port} em uso por PID={pid} "
            f"({proc.name()})"
        )

        proc.terminate()   # tenta encerrar educadamente
        proc.wait(timeout=3)

        print(f"[OK] Processo {pid} finalizado, porta liberada")

    except psutil.TimeoutExpired:
        print(f"[WARN] Processo {pid} não respondeu, forçando kill")
        proc.kill()

    except Exception as e:
        print(f"[ERROR] Falha ao liberar porta {port}: {e}")
    finally:
        time.sleep(0.2)


# -------------------------
# Start dos processos
# -------------------------
def start_server():
    free_port(8765)
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
    serverThread.name = "ServerOutputStreamThread"

    print(f'pro serverErros o whatToShow["serverError"] é: {whatToShow["serverError"]}')
    serverErrorThread = threading.Thread(
        target=stream_output,
        args=("SERVER_ERR", p.stderr, whatToShow["serverError"]),
        daemon=True
    )
    serverErrorThread.start()
    serverErrorThread.name = "ServerErrorStreamThread"

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
    watcherThread.name = "WatcherOutputStreamThread"

    watcherErrorThread = threading.Thread(
        target=stream_output,
        args=("WATCHER_ERR", p.stderr, whatToShow["watcherError"]),
        daemon=True
    )
    watcherErrorThread.start()  
    watcherErrorThread.name = "WatcherErrorStreamThread"
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
    frontendThread.name = "FrontEndOutputStreamThread"

    frontendErrorThread = threading.Thread(
        target=stream_output,
        args=("FRONTEND_ERR", p.stderr, whatToShow["frontEndError"]),
        daemon=True
    )
    frontendErrorThread.start()
    frontendErrorThread.name = "FrontEndErrorStreamThread"
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
        free_port(8765)
    


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