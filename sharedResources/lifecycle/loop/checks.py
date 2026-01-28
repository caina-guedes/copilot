import asyncio
from pathlib import Path
import sys
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.loop.state import LoopState


def loop_is_none(cls):
    if cls._current is None:
        cls.change_state(LoopState.EMPTY)
        cls._log("the current loop is None","loop")
        return True
    else:
        return False

def instance_check(cls, loop = None):
    if loop is None:# check the current loop internal loop is none is provided!
        loop = cls.get()
    if not isinstance(loop, asyncio.AbstractEventLoop): # se não for uma instancia de loop
        tem_att = all(hasattr(loop, attrib) for attrib in ["is_running","is_closed"]) # checa se tem os atributos básicos de um loop

        e_da_classe    = loop.__class__ in (asyncio.BaseEventLoop, asyncio.SelectorEventLoop, asyncio.ProactorEventLoop)
        e_da_subclasse = issubclass(loop.__class__, asyncio.AbstractEventLoop)
        if tem_att or e_da_classe or e_da_subclasse:
            return True
        else:
            try:

                return  loop == asyncio.get_running_loop()

            except RuntimeError:
                return False
    else:
        return True
    
def is_running(cls):
    if cls.loop_is_none():
        cls._log("o current loop ainda é None enquanto tentaram ver se ele estava rodando")

    elif cls.instance_check():
        running = cls._current.is_running()
        cls.change_state(LoopState.RUNNING if running else cls._state)

    else:
        cls.change_state(LoopState.NOT_A_LOOP)
        cls._log("tentaram ver se o loop estava rodando mas ele nem é um loop")

    return cls._state == LoopState.RUNNING

def is_closed(cls):
    # answer = []
    if cls.loop_is_none():
        cls._log("o current loop ainda é None enquanto tentaram ver se ele estava fechado")
        # return answer
    if cls.instance_check():
        is_closed = cls._current.is_closed()
        cls.change_state(LoopState.CLOSED if is_closed else cls._state)
        # answer.append(is_closed)
    else:
        cls.change_state(LoopState.NOT_A_LOOP)
        cls._log("tentaram ver se o loop está fechado mas ele não é um loop!")
    
    return cls._state == LoopState.CLOSED


def _loop_is_ok(cls):

    if cls.loop_is_none():
        cls._log("[loop_is_ok] cls.running_loop is empty!")
        return False
    
    if cls.instance_check():# é loop 
        if not cls.is_running(): # não está rodando
            if not cls.is_closed(): # não está fechado
                if cls._state != LoopState.SET:
                    cls.change_state(LoopState.STOPPING)
                cls._log("[loop_is_ok] loop is not running")
                return False

        if cls.is_closed():
            cls.change_state(LoopState.CLOSED)
            cls._log("[loop_is_ok] loop is closed")
            return False
        else:
            cls.change_state(LoopState.RUNNING)
            return True
    else:
        cls._log(f"[loop_is_ok] loop is not what it is supposed to be and it is: {type(cls.get())}")
        cls.change_state(LoopState.NOT_A_LOOP)
        return False


def _can_interact(cls):
    # print("Checking if loop can interact...")
    if not cls._loop_is_ok():
        cls._log("loop not available for interaction","loop")
        return False
    return True
