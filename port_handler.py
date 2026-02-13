import time
import psutil
import socket

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
