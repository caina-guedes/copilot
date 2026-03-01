import atexit
import multiprocessing
import threading
import asyncio
import os
import sys
# Adicione isso dentro do seu loop de FDs para ser mais específico
import socket
import stat

# def get_detailed_info(fd):
#     try:
#         # Pega as estatísticas do File Descriptor
#         mode = os.fstat(fd).st_mode
        
#         # 1. É um SOCKET?
#         if stat.S_ISSOCK(mode):
#             try:
#                 # Criamos o objeto socket para investigar
#                 s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
#                 try:
#                     peer = s.getpeername()
#                     return f"[SOCKET] Conectado a {peer[0]}:{peer[1]}"
#                 except:
#                     laddr = s.getsockname()
#                     return f"[SOCKET] Ouvindo em {laddr[0]}:{laddr[1]}"
#             except:
#                 return "[SOCKET] Unix Domain ou Outro"

#         # 2. É um PIPE? (Comunicação entre processos ou Stdout/Stderr)
#         elif stat.S_ISFIFO(mode):
#             return "[PIPE] Canal de comunicação"

#         # 3. É um ARQUIVO comum? (Logs, DBs, etc)
#         elif stat.S_ISREG(mode):
#             return "[FILE] Arquivo regular"

#         # 4. É um TERMINAL/DISPOSITIVO?
#         elif stat.S_ISCHR(mode):
#             return "[CHAR] Terminal/Dispositivo"

#         return "[OUTRO] Tipo desconhecido"
#     except Exception as e:
#         return f"[ERRO] Não acessível ({e})"

get_loop = None

def get_detailed_info(fd):
    try:
        mode = os.fstat(fd).st_mode
        
        # if stat.S_ISSOCK(mode):
        #     # 1. Tenta ver se é Internet (TCP/UDP)
        #     try:
        #         s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        #         peer = s.getpeername()
        #         return f"[TCP] Peer: {peer}"
        #     except:
        #         pass # Não é TCP/IP
        #     finally:
        #         s.close()

        #     # 2. Tenta ver se é Unix Domain (Local)
        #     try:
        #         # Criamos o socket usando AF_UNIX agora
        #         s = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
        #         path = s.getsockname()
        #         if isinstance(path, bytes):
        #             path = path.decode(errors='replace')
        #         s.close() # Fecha o socket criado só para inspeção
        #         if not path:
        #             return "[UNIX] Socket anônimo (comunicação interna)"
        #         return f"[UNIX] Path: {path}"
        #     except:
        #         return "[SOCKET] Tipo desconhecido (Raw/Netlink)"
        #     finally:
        #         s.close() # Fecha o socket criado só para inspeção
        if stat.S_ISSOCK(mode):
            # Tenta Internet (TCP)
            try:
                s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
                try:
                    peer = s.getpeername() # Isso retorna (IP, PORTA)
                    return f"[TCP] Destino: {peer[0]}:{peer[1]}"
                finally:
                    s.close()
            except:
                pass
            
            # Tenta ver se é um socket que está APENAS OUVINDO (Server Socket)
            try:
                s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
                try:
                    laddr = s.getsockname()
                    return f"[TCP] LISN: {laddr[0]}:{laddr[1]}"
                finally:
                    s.close()
            except: pass        

        elif stat.S_ISFIFO(mode): return "[PIPE] Canal de comunicação"
        elif stat.S_ISREG(mode):  return "[FILE] Arquivo regular"
        elif stat.S_ISCHR(mode):  return "[CHAR] Terminal/Dispositivo"
        
        return "[OUTRO] Recurso do Kernel"
    except Exception as e:
        return f"[ERRO] {e}"

def dump_fds():
    if os.name != "posix": return
    
    print(f"\n[atexit] Detalhamento de FDs:")
    fd_path = "/proc/self/fd"
    try:
        for fd_str in sorted(os.listdir(fd_path), key=int):
            fd = int(fd_str)
            try:
                target = os.readlink(f"{fd_path}/{fd_str}")
                info = get_detailed_info(fd)
                print(f" FD {fd:2} -> {info:30} | Path: {target}")
            except:
                continue
    except Exception:
        print("Erro ao ler /proc")
        
# def dump_fds():
#     if os.name != "posix":
#         return
#     try:
#         fd_path = "/proc/self/fd"
#         fds = os.listdir(fd_path)
#         print(f"[atexit] FDs abertos: {len(fds)}")
        
#         for fd in fds:
#             try:
#                 target = os.readlink(f"{fd_path}/{fd}")
#                 info = get_detailed_info(int(fd))
#                 print(f" {info}  - FD {fd} -> {target}")
#             except: pass
#     except Exception:
#         print("[atexit] Não foi possível ler /proc/self/fd")

def dump_threads():
    threads = threading.enumerate()
    print(f"\n[atexit] Threads ainda ativas ({len(threads)}):")
    current_thread = threading.current_thread()
    for t in threads:
        status = "REGULAR" if not t.daemon else "DAEMON"
        # Indica se a thread que está rodando o diagnóstico é a mesma da lista
        suffix = " (Self)" if t is current_thread else ""
        print(f" - [{status}] {t.name} (ID: {t.ident}){suffix}")

def dump_asyncio():
    try:
        # Pega o loop atual sem criar um novo
        loop = get_loop()
        if not loop:
            print("\n[atexit] get_loop() não retornou um loop válido pra função do MyLoop.")

            loop = asyncio.get_running_loop() # fallback para o loop atual se get_loop não estiver setado
        else:
            print("\n[atexit] get_loop() retornou um loop válido para a função do MyLoop.")

        if loop.is_running():
            print("\n[atexit] Event loop ainda em execução!")
            tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if tasks:
                print(f"\n[atexit] {len(tasks)} Tarefas Asyncio pendentes:")
                for t in tasks:
                    print(f" - Task: {t.get_coro()}")
        else:
            print("\n[atexit] Event loop não está mais em execução.")
        if loop.is_closed():
            print("\n[atexit] Event loop já fechado.")
        else:
            print("\n[atexit] Event loop ainda não está fechado.")
        
        # O mais importante: tarefas que ficaram "penduradas"
    except (RuntimeError, NameError):
        # RuntimeError acontece se não houver loop no thread atual
        print("\n[atexit] Nenhum event loop ativo (provavelmente estamos fora do contexto async)")
        pass

def dump_processes():
    children = multiprocessing.active_children()
    if children:
        print(f"\n[atexit] {len(children)} Processos filhos ativos:")
        for p in children:
            # Verifica se o processo ainda está vivo de fato
            status = "Vivo" if p.is_alive() else "Zumbi/Terminado"
            print(f" - PID={p.pid}, Name={p.name}, Status={status}")
    else:
        print("\n[atexit] Nenhum processo filho ativo.")

# Flags de controle (idealmente viriam do seu manager real)
shutdown_iniciated = False
shutdown_finalized = False

def atexit_diagnostics():
    # Tenta garantir que o output saia mesmo se o stdout estiver sendo fechado
    sys.stdout.flush() 
    
    print("\n" + "="*40)
    print("      ATEXIT DIAGNOSTICS REPORT")
    print("="*40)
    
    dump_threads()
    dump_asyncio()
    dump_processes()
    dump_fds()

    print("\n--- Lifecycle Check ---")
    if not shutdown_iniciated:
        print("[AVISO] shutdown_iniciated é False! (Crash ou fechamento forçado)")
    elif not shutdown_finalized:
        print("[AVISO] shutdown_finalized é False! (O shutdown começou mas travou no meio)")
    else:
        print("[OK] Ciclo de vida encerrado corretamente.")
    
    print("="*40 + "\n")

atexit.register(atexit_diagnostics)