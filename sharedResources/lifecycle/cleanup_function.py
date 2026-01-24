import asyncio
from typing import Optional, Callable, Any

def execute_cleanup_function(
    cleanup_function: Optional[Callable[..., Any]],
    loop: Optional[asyncio.AbstractEventLoop] = None
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
        if asyncio.iscoroutine(result):
            if loop:
                if not loop.is_closed():
                    asyncio.run_coroutine_threadsafe(result, loop)
                    print(f"[Cleanup] Async cleanup scheduled ")
                else:
                    print(f"[cleanup] loop closed ")
            else:
                print(f"[Cleanup] Cannot run async cleanup function, loop is missing")
        else:
            # função sync executada normalmente
            print(f"[Cleanup] Sync cleanup function executed ")
    except Exception as e:
        print(f"[Cleanup Error] {name}: {e}")
