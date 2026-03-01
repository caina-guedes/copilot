# -------------------- Funções utilitárias Desatualizadas!!!!! --------------------
import asyncio
import threading


def print_thread_status():
    print("=== THREAD STATUS ===")
    # logger.info("=== THREAD STATUS ===")
    for t in threading.enumerate():

        print(f"Thread: {t.name}, alive: {t.is_alive()}, daemon: {t.daemon}")
        # logger.info(f"Thread: {t.name}, alive: {t.is_alive()}, daemon: {t.daemon}")


def print_async_tasks_status():
    print("=== ASYNC TASKS STATUS ===")
    # logger.info("=== ASYNC TASKS STATUS ===")

    for t in asyncio.all_tasks():
        if t is asyncio.current_task():
            continue
        try:
            name = t.get_name()
        except AttributeError:
            name = str(t)
        print(f"Task: {name}, done: {t.done()}")
        # logger.info(f"Task: {name}, done: {t.done()}")
