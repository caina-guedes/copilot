import asyncio
import warnings
from typing import Optional, Callable, Any

from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus

def execute_cleanup_function(
    cleanup_function: Optional[Callable[..., Any]],
    loop = None
):
    """
    Executa uma função de cleanup, tratando casos síncrono ou assíncrono.
    - cleanup_function: função ou coroutine a executar
    - loop: loop asyncio onde a coroutine deve ser agendada
    - name: nome do item para logs
    """
    if not cleanup_function:
        print(f"[Cleanup] No cleanup function")
        return

    try:
        result = cleanup_function()
        # se for coroutine, agenda no loop
        if inspect.iscoroutine(result):
            if loop.get() is not None:
                    if loop._loop_is_ok():
                        asyncio.run_coroutine_threadsafe(result, loop)
                        print(f"[Cleanup] Async cleanup scheduled ")
                    else:
                        print(f"[cleanup] loop is not ok ")
            else:
                print(f"[Cleanup] Cannot run async cleanup function, loop is missing")
        else:
            # função sync executada normalmente
            print(f"[Cleanup] Sync cleanup function executed ")
    except Exception as e:
        log_error_forensics_plus(e)
