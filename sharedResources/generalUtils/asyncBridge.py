import asyncio
import threading
from typing import Callable, Union


class AsyncBridge:
    """
    Infraestrutura para integrar threads e async sem travar o servidor.
    """
    @classmethod
    def run_in_thread(cls, func: Callable, *args, **kwargs):
        """
        Roda uma função blocking numa thread separada.
        """
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True,name=f"{func.__name__} asyncBridge Thread")
        thread.start()
        return thread


    EventType = Union[threading.Event, asyncio.Event]

    @classmethod
    async def wait_event(cls, event: EventType, clear : bool = False):
        """
        Espera um evento qualquer sem bloquear o loop principal.
        Funciona para threading.Event ou asyncio.Event.
        """
        if isinstance(event, asyncio.Event):
            await event.wait()
            if clear:
                event.clear()
        elif isinstance(event, threading.Event):
            # polling async para não bloquear o loop
            while not event.is_set():
                await asyncio.sleep(0.01)
            if clear:
                event.clear()
        else:
            raise TypeError("Evento não suportado")

