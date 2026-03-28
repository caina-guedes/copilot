import asyncio
import struct
import subprocess
import threading
import platform
import socket
import psutil
import signal
import queue
import time
import sys
import os
import io

env = os.environ.copy()
env["IS_SUBPROCESS"] = "1"

# subprocess.Popen(["python", "script.py"], env=env)
system_name = platform.system().lower()
is_windows = system_name.find('win') != -1

from colorama import init, Fore, Style


flush_interval = 0.5
last_flush_time = 0


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

last_stream_output_prefix ={ 'current': None}

log_queue = queue.Queue()



def stream_output(prefix, stream, stdin_pipe, show = True):
    temp_msg = b'' if prefix.lower().find('front') == -1 else ''
    size_still_waiting_for = 0
    waiting_confirmation = False
    MAGIC_NUMBER = b'\xaa\x55'
    msg_size = 0
    global system_name 
    quebra_de_linha = b"\r\n" if is_windows else b'\n'
    CHUNK_SIZE  = 8192
    not_front_end = prefix.find("FRONTEND") == -1
    while True:
    # with _STDOUT_LOCK:
    # .read(n) lê ATÉ n bytes. Se o pipe estiver vazio, ele espera.
    # Se o processo fechar, ele retorna uma string/byte vazio.
        if not_front_end: # não é vindo do front_end ou seja, vem do python!
            try:
                # Obtém o file descriptor do pipe (stdout do subprocesso)
                fd = stream.fileno()
                # os.read(fd, n) no Windows retorna o que estiver disponível no buffer interno
                chunk = os.read(fd, CHUNK_SIZE)
                if not chunk:
                    break
                if not show:
                    continue
                
                if chunk == quebra_de_linha:
                    # print("peguei a quebra de linha de boa ")
                    log_queue.put(( prefix , chunk.decode('utf-8', errors='replace')))
                    continue
                
                start_idx = chunk.find(MAGIC_NUMBER)

                # print("the original chunk type is:",type(chunk))
                # chunk = chunk.decode('utf-8', errors='replace')
                # print("the  chunk type after decode is:",type(chunk))
                # print("and the value is:",chunk)
                
                
                if size_still_waiting_for != 0:
                    print("entrei na parte onde mensagens se partiram!")
                    temp_msg += chunk[:size_still_waiting_for]
                    if len(temp_msg) == msg_size:
                        print(f"mensagem({temp_msg.decode('utf-8', errors='replace')}) partiu mas eu peguei o resto corretamente!")
                        msg_content = temp_msg
                        temp_msg = '' 
                        size_still_waiting_for = 0
                        log_queue.put(( prefix , chunk.decode('utf-8', errors='replace')))
                        try:
                            stdin_pipe.write("ACK\n")
                            stdin_pipe.flush()
                        except BrokenPipeError:
                            break
                    elif len(temp_msg) > msg_size:
                        print(f"temp_msg({temp_msg}) ficou maior que o msg_size({msg_size}) ")
                    chunk = chunk[size_still_waiting_for:]
                    if not chunk:
                        continue   
                else:
                    pass
                    # print("não estão faltando partes anteriores")
                        
                if start_idx == -1: # didn't find the magic number !!!
                    # print("não achei o numero mágico!")
                    log_queue.put(( prefix , chunk.decode('utf-8', errors='replace')))
                    continue
                else:
                    # print("achei o numero mágico!")
                    size_bytes = chunk[start_idx+2 : start_idx+6]
                    msg_size = struct.unpack('I', size_bytes)[0]
                    # print('o tamanho da mensagem declarado é:',msg_size)
                    msg_content = chunk[start_idx+6 : start_idx+6+msg_size]
                    # print('o conteudo que veio é:' ,msg_content.decode('utf-8', errors='replace'))

                    if len(msg_content) < msg_size: # msg não chegou inteira!
                        temp_msg += msg_content
                        size_still_waiting_for = abs(len(msg_content) - msg_size)
                        print(f"mensagem({temp_msg}) não veio inteira, ainda esperando {size_still_waiting_for} bytes")
                        continue
                    else:
                        temp_msg = ''
                        size_still_waiting_for = 0
                        msg_size = 0
                        log_queue.put(( prefix , msg_content.decode('utf-8', errors='replace')))
            except EOFError:
                print("deu erro lendo o fd dentro do stream_output")
                break
        else:
            chunk = stream.readline()
        # print("chunk chegou: ",chunk)
            if not chunk:
                break
            if not show:
                continue
                
        

        # Envia o ACK para o PrintInterceptor continuar
        try:
            stdin_pipe.write("ACK\n")
            stdin_pipe.flush()
        except BrokenPipeError:
            break

def display_worker():
    """Thread única que cuida da saúde do seu terminal"""
    global last_stream_output_prefix, last_flush_time, flush_interval
       
    while True:
        first_msg = log_queue.get()
        # Usa StringIO para concatenar grandes volumes (como seus relatórios) sem perda de performance
        buffer = io.StringIO()
        # buffer.write(first_msg)
        batch = [first_msg]
        
        # 3. "Drena" o restante da fila sem esperar (non-blocking)
        try:
            while True:
                msg = log_queue.get_nowait()
                batch.append(msg)
                log_queue.task_done()
        except queue.Empty:
            # A fila esvaziou por enquanto
            pass
        
        for prefix , line in  batch:
            line = str(line)
            color = PROCESS_COLORS.get(prefix, "")  # padrão se algo desconhecido aparecer
            # Aqui você pode implementar lógica de 'batch' 
            # para escrever várias mensagens de uma vez se a fila estiver grande
            if prefix  == last_stream_output_prefix["current"]:
                display_prefix = ""
            else:
                last_stream_output_prefix["current"] = prefix
                display_prefix = prefix
            
            line = str(line)
            line = line.replace("Core.__holder__",f"{color}") if "Core.__holder__" in line else line

            msg = f"{color}[{display_prefix}] {line}\033[0m" if display_prefix else f"{color} {line}\033[0m"
        
            buffer.write(msg)

        sys.stdout.write(buffer.getvalue())
        if time.perf_counter() - last_flush_time   > flush_interval:
            sys.stdout.flush()
            last_flush_time = time.perf_counter()
            

# Inicia o trabalhador de tela
threading.Thread(target=display_worker, daemon=True).start()

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

def check_port_in_use(port: int, host="0.0.0.0"):
    
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port and conn.laddr.ip == host:
            return conn
        if conn.laddr and conn.laddr.port == port:
            print("[check_port_in_use] got in the second if, not the first ")
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

python_exe = "python" if is_windows else "python3"
# -------------------------
# Start dos processos
# -------------------------
def start_server():
    free_port(8765)
    print("[orchestrator] Iniciando server...")
    p = subprocess.Popen(
        [python_exe,"-u", "PythonServer/server.py"],
        stdout=subprocess.PIPE,
        stdin= subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0, # buffering para evitar delay
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows else 0,
        env=env
    )
    print(f'pro server o whatToShow["server"] é: {whatToShow["server"]}')
    serverThread= threading.Thread(
        target=stream_output,
        args=("SERVER", p.stdout, p.stdin, whatToShow["server"]),
        daemon=True
    )
    serverThread.start()
    serverThread.name = "ServerOutputStreamThread"

    print(f'pro serverError o whatToShow["serverError"] é: {whatToShow["serverError"]}')
    serverErrorThread = threading.Thread(
        target=stream_output,
        args=("SERVER_ERR", p.stderr, p.stdin, whatToShow["serverError"]),
        daemon=True
    )
    serverErrorThread.start()
    serverErrorThread.name = "ServerErrorStreamThread"

    return p


def start_watcher():
    print("[orchestrator] Iniciando watcher...")
    p = subprocess.Popen(
        [python_exe, "-u", "PythonSistemAutomation/main.py"],
        stdout=subprocess.PIPE,
        stdin = subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0, # buffering para evitar delay
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if is_windows  else 0,
        env=env
    )

    watcherThread = threading.Thread(
        target=stream_output,
        args=("WATCHER", p.stdout, p.stdin, whatToShow["watcher"]),
        daemon=True
    )
    watcherThread.start()
    watcherThread.name = "WatcherOutputStreamThread"

    watcherErrorThread = threading.Thread(
        target=stream_output,
        args=("WATCHER_ERR", p.stderr, p.stdin, whatToShow["watcherError"]),
        daemon=True
    )
    watcherErrorThread.start()  
    watcherErrorThread.name = "WatcherErrorStreamThread"
    print("[orchestrator] Iniciei o watcher...")
    return p


def start_frontend():
    print("[orchestrator] Iniciando frontend...")
    if is_windows :
        npm_path = r"C:\Program Files\nodejs\npm.cmd"
    else:
        npm_path = "npm"
    p = subprocess.Popen(
        [npm_path, "run", "tauri", "dev"],
        cwd="automation-ui-tauri/src-tauri",
        stdout=subprocess.PIPE,
        stdin = subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    frontendThread = threading.Thread(
        target=stream_output,
        args=("FRONTEND", p.stdout, p.stdin, whatToShow["frontEnd"]),
        daemon=True
    )
    frontendThread.start()
    frontendThread.name = "FrontEndOutputStreamThread"

    frontendErrorThread = threading.Thread(
        target=stream_output,
        args=("FRONTEND_ERR", p.stderr, p.stdin, whatToShow["frontEndError"]),
        daemon=True
    )
    frontendErrorThread.start()
    frontendErrorThread.name = "FrontEndErrorStreamThread"
    return p

async def encerrar_processo_educadamente(p):
    if is_windows:
        # Envia um sinal de CTRL_BREAK ou CTRL_C que o seu 
        # pluga_sinal_de_parada (via signal.SIGBREAK ou SIGINT) vai capturar
        print("enviando sinal educado de parada pro processo")
        try:
            os.kill(p.pid, signal.CTRL_BREAK_EVENT)
            # p.send_signal(signal.CTRL_BREAK_EVENT) 
        except Exception as e:
            print("deu erro enviando o sinal e foi:",str(e))
        try:
            # Dá um tempo para o Watcher/Server rodar o cleanup
            timeout = 5
            print(f"vou esperar ate {timeout} segundos")
            # Loop de espera não-bloqueante
            for _ in range(int(timeout / 0.5)):
                if p.poll() is not None:
                    break
                print('dormindo')
                await asyncio.sleep(0.5) # Deixa o loop de eventos respirar
                print('acordando')
            else:
                # Se o loop terminar sem o break, deu timeout
                raise asyncio.TimeoutError
                
            print("Processo encerrou graciosamente.")
            # def run():
            #     while p.poll() is None: # Se o processo ainda estiver vivo
            #         print("ainda vivo")
            #         time.sleep(0.3)

            #     # p.wait(timeout=timeout)
            # await asyncio.wait_for(run, timeout=timeout)
            # p.wait(timeout=timeout)
            print("processo parou como devia")
        except Exception as e:
            # Se não fechou em 5s, aí sim mata no peito
            print("processo deu timeout, vou matar")
            p.stdout.close()
            p.stderr.close()
            p.stdin.close()
            p.kill()
        
        if p.poll() is None: # Se o processo ainda estiver vivo
            try:
                # /T mata a árvore de processos (filhos também)
                # /F força a finalização
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Erro ao matar processo {p.pid}: {e}")
                p.kill() # Fallback
    else:
        p.terminate()
        p.wait(timeout=5)


# -------------------------
# Main
# -------------------------
async def main():
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
        while server.poll() is None:
            time.sleep(0.5) 
        print("frontend se foi ")
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[orchestrator] Interrompido pelo usuário")

    finally:
        print(Style.RESET_ALL + "[orchestrator] Encerrando processos...")
        for p in reversed(processes):
            try:
                threads = threading.enumerate()

                for t in threads:
                    print(t.name, t.ident, t.is_alive())
                await encerrar_processo_educadamente(p)

                # if is_windows:
                #     # No Windows, terminate() é o mesmo que kill(). 
                #     # Usar CTRL_C_EVENT é mais "educado" mas complexo.
                #     p.kill() 
                # else:
                #     p.terminate()
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
    asyncio.run(main())