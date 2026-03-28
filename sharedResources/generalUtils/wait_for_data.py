import asyncio
import inspect
import queue


async def wait_for_data(source,timeout):
    """
    Espera por dados de diferentes tipos de fontes:
    - asyncio.Queue
    - queue.Queue (threading)
    - WebSocket (async)
    """

    # 🔹 asyncio.Queue
    if isinstance(source, asyncio.Queue):
        try:
            return await asyncio.wait_for(source.get(), timeout)
        except asyncio.TimeoutError:
            raise 
            # return None

    # 🔹 queue.Queue (thread-safe)
    elif isinstance(source, queue.Queue):
        try:
            # roda o get em thread pra não bloquear o loop
            return await asyncio.to_thread(source.get, True, timeout)
        except queue.Empty:
            raise
            # return None
        

    # 🔹 WebSocket (async)
    elif hasattr(source, "recv") and inspect.iscoroutinefunction(source.recv):
        try:
            return await asyncio.wait_for(source.recv(), timeout)
        except asyncio.TimeoutError:
            raise
            # return None

    # 🔹 fallback genérico (callable async)
    elif inspect.iscoroutinefunction(source):
        try:
            return await asyncio.wait_for(source(), timeout)
        except asyncio.TimeoutError:
            raise
            # return None

    else:
        raise TypeError(f"Tipo não suportado: {type(source)}")
