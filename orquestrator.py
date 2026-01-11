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

def stream_output(prefix, stream):
    color = PROCESS_COLORS.get(prefix, "")
    for line in iter(stream.readline, ''):
        if line:
            print(f"{color}[{prefix}] {line}", end='')

# # cores normais
# SERVER_COLOR = "\033[92m"   # verde
# WATCHER_COLOR = "\033[94m"  # azul
# FRONTEND_COLOR = "\033[93m" # amarelo

# # cores de erro
# SERVER_ERR_COLOR = "\033[91m"     # vermelho intenso
# WATCHER_ERR_COLOR = "\033[95m"    # magenta (mistura de azul+vermelho)
# FRONTEND_ERR_COLOR = "\033[31m"   # vermelho clássico


# PROCESS_COLORS = {
#     "SERVER": SERVER_COLOR,
#     "SERVER_ERR": SERVER_ERR_COLOR,
#     "WATCHER": WATCHER_COLOR,
#     "WATCHER_ERR": WATCHER_ERR_COLOR,
#     "FRONTEND": FRONTEND_COLOR,
#     "FRONTEND_ERR": FRONTEND_ERR_COLOR
# }


def stream_output(prefix, stream):
    color = PROCESS_COLORS.get(prefix, "")  # padrão se algo desconhecido aparecer
    for line in iter(stream.readline, ''):
        if line:
            print(f"{color}[{prefix}] {line}\033[0m", end='')

# def stream_output(prefix, stream,color):
#     for line in iter(stream.readline, ''):
#         if line:
#             print(f"{color}[{prefix}]{line}\033[0m", end='')
            # print(f"[{prefix}] {line}", end='')


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
    return False


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

    threading.Thread(
        target=stream_output,
        args=("SERVER", p.stdout),
        daemon=True
    ).start()

    threading.Thread(
        target=stream_output,
        args=("SERVER_ERR", p.stderr),
        daemon=True
    ).start()

    return p

# def start_server():
#     print("[orchestrator] Iniciando server...")
#     return subprocess.Popen(
#         ["python3", "-u", "PythonServer/server.py"],
#         stdout=sys.stdout,
#         stderr=sys.stderr
#     )


def start_watcher():
    print("[orchestrator] Iniciando watcher...")
    p = subprocess.Popen(
        ["python3", "-u", "PythonSistemAutomation/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    threading.Thread(
        target=stream_output,
        args=("WATCHER", p.stdout),
        daemon=True
    ).start()

    threading.Thread(
        target=stream_output,
        args=("WATCHER_ERR", p.stderr),
        daemon=True
    ).start()

    return p


# def start_watcher():
#     print("[orchestrator] Iniciando watcher...")
#     return subprocess.Popen(
#         ["python3", "-u", "PythonSistemAutomation/main.py"],
#         stdout=sys.stdout,
#         stderr=sys.stderr
#     )

def start_frontend():
    print("[orchestrator] Iniciando frontend...")
    p = subprocess.Popen(
        ["npm", "run", "tauri", "dev"],
        cwd="automation-ui-tauri/src-tauri",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    threading.Thread(
        target=stream_output,
        args=("FRONTEND", p.stdout),
        daemon=True
    ).start()

    threading.Thread(
        target=stream_output,
        args=("FRONTEND_ERR", p.stderr),
        daemon=True
    ).start()

    return p


# def start_frontend():
#     print("[orchestrator] Iniciando frontend (Tauri)...")
#     return subprocess.Popen(
#         ["npm", "run", "tauri", "dev"],
#         cwd="automation-ui-tauri/src-tauri"
#     )


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
