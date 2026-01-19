import threading
import asyncio
import logging

# Setup básico de logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger("LifecycleTracker")

# Flag global de shutdown
shutdown_event = threading.Event()


# -------------------- Thread wrapper --------------------
class TrackedThread(threading.Thread):
    threadsMap = {}
    def __init__(self, target, name, *args, **kwargs):
        super().__init__(target=target, name=name, args=args, kwargs=kwargs)
        if name:
            if name not in TrackedThread.threadsMap:
                TrackedThread.threadsMap[name] = [self]
            else:
                TrackedThread.threadsMap[name].append(self)
        print(f"[Thread Created] {self.name}")
        logger.info(f"[Thread Created] {self.name}")

    def run(self):
        print(f"[Thread Started] {self.name}")
        
        logger.info(f"[Thread Started] {self.name}")
        try:
            super().run()
        finally:
            ### talvez aqui seja adequado para excluir a task da lista?
            logger.info(f"[Thread Exited] {self.name}")


class nonLinearMap():
    """
    mapa para rastrear as threads e tasks com nomes iguais ou não"""
    threadsMap = TrackedThread.threadsMap
    tasksMap = {}
# -------------------- Async Task wrapper --------------------
def tracked_task(coro, name=None):
    """Cria uma async task com logging"""
    task = asyncio.create_task(coro,name = name)
    if name:
        if name not in nonLinearMap.tasksMap:
            nonLinearMap.tasksMap[name] = [task]
        else:
            nonLinearMap.tasksMap[name].append(task)
    else:
        nonLinearMap.tasksMap["unnamedTasks"]= nonLinearMap.tasksMap.get("unnamedTasks",[]) + [task]
    # Nome para Python >= 3.8
    # if name:
    #     try:
    #         task.set_name(name)
    #     except AttributeError:
    #         pass
    print(f"[Async Task Created] {task.get_name() if name else task}")
    logger.info(f"[Async Task Created] {task.get_name() if name else task}")
    
    async def wrapper():
        print(f"[Async Task Started] {task.get_name() if name else task}")
        logger.info(f"[Async Task Started] {task.get_name() if name else task}")
        try:
            return await task
        except asyncio.CancelledError:
            print(f"[Async Task Cancelled] {task.get_name() if name else task}")
            logger.info(f"[Async Task Cancelled] {task.get_name() if name else task}")
            raise
        finally:
            print(f"[Async Task Exited] {task.get_name() if name else task}")
            logger.info(f"[Async Task Exited] {task.get_name() if name else task}")
    
    return asyncio.create_task(wrapper())


# -------------------- Funções utilitárias --------------------
def print_thread_status():
    logger.info("=== THREAD STATUS ===")
    for t in threading.enumerate():
        logger.info(f"Thread: {t.name}, alive: {t.is_alive()}, daemon: {t.daemon}")


def print_async_tasks_status():
    logger.info("=== ASYNC TASKS STATUS ===")
    for t in asyncio.all_tasks():
        if t is asyncio.current_task():
            continue
        try:
            name = t.get_name()
        except AttributeError:
            name = str(t)
        logger.info(f"Task: {name}, done: {t.done()}")


async def shutdown_all_async():
    logger.info("Cancelling all async tasks...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for t in tasks:
        try:
            t.cancel()
            logger.info(f"Cancelled {t.get_name() if hasattr(t, 'get_name') else t}")
        except Exception as e:
            logger.warning(f"Error cancelling task {t}: {e}")
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("All async tasks cleaned up.")


def shutdown_all_threads(threads):
    logger.info("Stopping all threads...")
    for t in threads:
        if hasattr(t, "stop"):
            t.stop()
    for t in threads:
        t.join()
    logger.info("All threads cleaned up.")


if __name__ == "__main__":
    # Exemplo de uso
    print_thread_status()
    print_async_tasks_status()
