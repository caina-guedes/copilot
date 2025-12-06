import types
import asyncio
from copy import copy
from sharedResources.pythonLoggerSistem.logger  import LoggerManager
logger = LoggerManager.get_logger("concurrencySafeObject")

import threading
import asyncio
import inspect
import functools

class HybridLock:
    def __init__(self):
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    async def __aenter__(self):
        # Para ambientes assíncronos, adquirir o lock assíncrono
        await self._async_lock.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self._async_lock.release()

    def __enter__(self):
        # Para ambientes síncronos, adquirir o lock síncrono
        self._sync_lock.acquire()

    def __exit__(self, exc_type, exc, tb):
        self._sync_lock.release()

    async def acquire(self):
        # Método para adquirir o lock dependendo do contexto
        if self._is_coroutine():
            await self._async_lock.acquire()
        else:
            self._sync_lock.acquire()

    def release(self):
        if self._is_coroutine():
            self._async_lock.release()
        else:
            self._sync_lock.release()

    def _is_coroutine(self):
        # Detecta se o contexto atual é assíncrono
        return inspect.iscoroutinefunction(inspect.currentframe().f_back.f_code)

# Exemplo de uma classe wrapper que gerencia ambos os contextos
class ThreadAsyncSafeWrapper:
    def __init__(self, obj):
        self._obj = obj
        self._lock = HybridLock()

    def __getitem__(self,index):
        with self._lock:
            return self._obj[index]
    def __getattr__(self, name):
        attr = getattr(self._obj, name)

        if callable(attr):
            if inspect.iscoroutinefunction(attr):
                # Para métodos assíncronos
                @functools.wraps(attr)
                async def async_wrapper(*args, **kwargs):
                    async with self._lock:
                        return await attr(*args, **kwargs)
                return async_wrapper
            else:
                # Para métodos síncronos
                @functools.wraps(attr)
                def sync_wrapper(*args, **kwargs):
                    with self._lock:
                        return attr(*args, **kwargs)
                return sync_wrapper
        else:
            # Para atributos normais, proteger leitura/alteração
            # Aqui podemos decidir se protegemos com lock, dependendo do uso
            # Para simplificar, deixamos sem lock
            return attr

    def __setattr__(self, name, value):
        if name in ('_obj', '_lock'):
            super().__setattr__(name, value)
        else:
            # Protege a alteração de atributos
            # Pode-se usar lock aqui também
            with self._lock:
                setattr(self._obj, name, value)
    def __len__(self):
        with self._lock:
            return len(self._obj)















class AsyncLockedWrapper:
    def __init__(self, target):
        self._target = target
        self._lock = asyncio.Lock()
        self._wrap_methods()

    def _wrap_methods(self):
        # Pega todos os atributos (inclusive dunder) do objeto original
        for attr_name in dir(self._target):
            if attr_name.startswith("__") and attr_name.endswith("__"):
                # Dunder methods: tentamos reencaminhar
                self._wrap_dunder(attr_name)
            elif not hasattr(self, attr_name):
                attr = getattr(self._target, attr_name)
                if callable(attr):
                    # Métodos normais: criamos wrappers async com lock
                    async def make_locked_method(attr=attr):
                        async def method(*args, **kwargs):
                            async with self._lock:
                                return attr(*args, **kwargs)
                        return method
                    # Bind o método ao wrapper
                    setattr(self, attr_name, types.MethodType(asyncio.run(make_locked_method()), self))

    def _wrap_dunder(self, attr_name):
        try:
            attr = getattr(self._target, attr_name)
            if callable(attr):
                # Define dinamicamente o método no wrapper
                async def method(self, *args, **kwargs):
                    async with self._lock:
                        return attr(*args, **kwargs)
                setattr(self, attr_name, types.MethodType(method, self))
        except AttributeError:
            pass

    async def __aenter__(self):
        await self._lock.acquire()
        return self._target

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()







class AsyncSafeDeque:
    def __init__(self,deque = None):
        
        if isinstance(deque,AsyncSafeDeque):
            self._queue = deque
        else:
            self._queue = deque()
            if deque is not None:
                logger.warning('wrong manipulation of AsyncSafeDeque,initialized with: '+str(deque))

        self._lock = asyncio.Lock()

    async def values(self):
        async with self.lock:
            return copy.deepcopy(self._queue)
    
    async def append(self, item):
        async with self._lock:
            self._queue.append(item)

    async def popleft(self):
        async with self._lock:
            if self._queue:
                return self._queue.popleft()
            return None

    async def peek(self):
        async with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    async def is_empty(self):
        async with self._lock:
            return not self._queue

    async def __len__(self):
        async with self._lock:
            return len(self._queue)

    async def clear(self):
        async with self._lock:
            self._queue.clear()

    # Outros métodos úteis (opcional):
    async def get_all(self):
        async with self._lock:
            return list(self._queue)

if __name__ =="main":
    # Uso:
    # Suponha que temos uma classe
    class MinhaClasse:
        def __init__(self):
            self.valor = 0

        def incrementar(self):
            self.valor += 1

        async def async_incrementar(self):
            self.valor += 1

    # Envolver
    obj = MinhaClasse()
    seguro = ThreadAsyncSafeWrapper(obj)

    # Em código síncrono
    seguro.incrementar()

    # Em código assíncrono
    async def exemplo():
        await seguro.async_incrementar()

    # Assim, a sua classe consegue lidar com ambos os casos
