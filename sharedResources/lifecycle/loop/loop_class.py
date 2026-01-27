from concurrent.futures import Future
import asyncio
import threading
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))

from sharedResources.lifecycle.loop.state import LoopState , change_state
from sharedResources.lifecycle.loop.logging_utils import set_register_log, _log
from sharedResources.lifecycle.loop.checks import instance_check, loop_is_none, is_running, is_closed, _loop_is_ok, _can_interact
from sharedResources.lifecycle.loop.start_and_stop import start_loop, stop_loop
from sharedResources.lifecycle.loop.threadsafe import call_soon, submit, gather

class MyLoop():
    """ 
        em breve mudarei o loop pra ser uma classe com o 
        atributo currrent, por enquanto é uma lista com o primeiro elemento 
        sendo o loop de fato
    """
    _current = None # variável que vai conter o verdadeiro loop!
    _register_log = None  # esta função tem que ser setada pelo lifecicleMaster por isso começa assim
    _state = LoopState.EMPTY # estado inicial do loop é Empty
    _thread = None
    # _loop_started = False # flag para sinalizar que o loop começou
    _stop_loop_event = threading.Event() # usado para sinalizar que o run_forever dentro da thread do loop ja acabou
    # _first_set = True

    #from logging_utils.py
    set_register_log = classmethod(set_register_log)
    _log             = classmethod(_log)
    change_state     = classmethod(change_state)

    #from checks.py
    loop_is_none     = classmethod(loop_is_none)
    instance_check   = classmethod(instance_check)
    is_running       = classmethod(is_running)
    is_closed        = classmethod(is_closed)
    _loop_is_ok      = classmethod(_loop_is_ok)
    _can_interact    = classmethod(_can_interact)
    
    #from start_and_stop.py
    start_loop       = classmethod(start_loop)
    stop_loop        = classmethod(stop_loop)

    #from threadsafe.py
    call_soon        = classmethod(call_soon)
    submit           = classmethod(submit)
    gather           = classmethod(gather)

    @classmethod
    def get(cls):
        return cls._current

    
    # @classmethod
    # def set(cls,loop):
    #     try:
    #         current_loop = asyncio.get_running_loop() # tenta pegar o loop da thread atual
    #     except RuntimeError:
    #         current_loop = None
        
    #     if loop is None:
    #         loop = current_loop
        

    #     if loop is None: # NÃO PODE SETAR NONE
    #         cls._log("cannot set None as the main loop","loop")
    #         return False

    #     if not cls.loop_is_none(): # SE JA SETOU NÃO SETA DE NOVO   
    #         cls._log("current loop already set!")
    #         return False


    #     if loop != current_loop and cls._thread is not None:
    #         cls._log("tentativa de set loop fora da thread correta","loop")
    #         cls._log(f"current loop is: {current_loop} and trying to set loop: {loop}","loop")
    #         cls._log(f"the current thread is: {threading.current_thread()} and the loop._thread is: {cls._thread}","loop")
    #         return False

    #     if not cls.instance_check(loop): # SE NÃO FOR UM LOOP VÁLIDO
    #         cls._log("the argument is not a proper loop to set in the main loop","loop")
    #         return False

    #     cls._current = loop
    #     #cls._first_set = False
    #     cls.change_state(LoopState.SET)
    #     return True


    

    
  

