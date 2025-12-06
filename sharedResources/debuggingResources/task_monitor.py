import asyncio
import inspect
import logging
from pathlib import Path
import time

logger = logging.getLogger("TaskMonitor")
logger.setLevel(logging.DEBUG)  # Mude para INFO se quiser menos verboso

handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
stop_event = asyncio.Event()

project_root = Path(__file__).resolve().parent.parent.parent.parent  #  muat be the root of the project
    

async def task_monitor(interval=5.0, stop_event: asyncio.Event = None, filter_path=project_root):
    """Monitora todas as tasks vivas no asyncio loop a cada intervalo de tempo."""
    while stop_event and not stop_event.is_set():
        logger.info("📡 Verificando tarefas asyncio vivas...")
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current]
        logger.info(f"🔍 {len(tasks)} task(s) encontradas.")
        for task in tasks:
            # Se filter_path definido, ignora tasks fora do seu código
            
            coro = task.get_coro()
            try:
                file_path = Path(inspect.getfile(coro))
            except TypeError:
                continue
            # filtra apenas arquivos dentro do projeto e .py
            if project_root not in file_path.parents or not file_path.suffix == ".py":
                continue

            name = task.get_name() if hasattr(task, "get_name") else repr(coro)
            logger.debug(f"➡️ Task: {name}")
            logger.debug(f"    Status: Done={task.done()}, Cancelled={task.cancelled()}")
            stack = task.get_stack()
            if not stack:
                logger.debug("    📍 Stack: [vazia ou aguardando await]")
            else:

                logger.debug("    📍 Stack:")
                frame_info = stack[0] if stack else None
                file_path = frame_info.f_code.co_filename if frame_info else "<unknown>"

                if filter_path and not Path(file_path).resolve().as_posix().startswith(Path(filter_path).resolve().as_posix()):
                    continue
                
                 # Tempo aproximado que a task está rodando
                start_time = getattr(task, "_start_time", None)
                if start_time is None:
                    # Marca a primeira vez que vemos essa task
                    start_time = time.time()
                    setattr(task, "_start_time", start_time)
                elapsed = time.time() - start_time
                status = "done" if task.done() else "pending"
                cancelled = task.cancelled()
                logger.info(f"➡️ Task: {name} | Status: {status} | Cancelled: {cancelled} | Tempo rodando: {elapsed:.3f}s | Arquivo: {file_path}")


                # for frame in stack:
                #     filename = frame.f_code.co_filename
                #     lineno = frame.f_lineno
                #     funcname = frame.f_code.co_name
                #     logger.debug(f"      ↳ {filename}:{lineno} → {funcname}")
        await asyncio.sleep(interval)
