import threading
import time
import asyncio
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.shutdownMaster import Tracked_task, ShutdownMaster, TrackedThread
from sharedResources.lifecycle.utils import wait_event

async def dummy_task(x):
    await asyncio.sleep(0.1)
    return x * 2

async def test_tracked_task():
    t = tracked_task(dummy_task(5), name="test")
    assert t in [item.obj for item in ShutdownMaster.tasksMap["test"]]
    result = await t
    assert result == 10
    print("✅ tracked_task basic test passed")


async def cancellable_task():
    try:
        while not ShutdownMaster.shutdown_event.is_set():
            await asyncio.sleep(0.1)
        print("done")
    finally:
        print("[cleanup] Task finalizando")
# def generate_task(name):
#     return {task" = cancellable_task,
#         selfCleanUpEvent, 
#         selfCleanUpEventUse,
#         name = name, 
#         kind = "task",
#         created_from = created_from}

async def test_task_shutdown():
    t1 = tracked_task(cancellable_task(), name="task1", created_from = "test_task_shutdown")
    t2 = tracked_task(cancellable_task(), name="task2", created_from = "test_task_shutdown")

    await asyncio.sleep(0.3)  # deixa as tasks rodarem um pouco
    ShutdownMaster.shutdown_event.set()  # sinaliza shutdown
    await asyncio.gather(t1, t2, return_exceptions=True)
    print("✅ shutdown test passed")

def dummy_thread():
    while not ShutdownMaster.shutdown_event.is_set():
        time.sleep(0.1)
    print("[cleanup] Thread finalizando")

def test_thread_shutdown():
    t = TrackedThread(target=dummy_thread, name="thread1", created_from = "test_thread_shutdown")
    t.start()

    time.sleep(0.3)
    ShutdownMaster.shutdown_event.set()
    # t.join()

# ---------------- Test integrado ----------------
async def test_integrated():
    # Define loop principal
    loop = asyncio.get_running_loop()
    ShutdownMaster.set_loop(loop )
    ev =threading.Event()
    # -------- Threads --------
    def thread_job(name):
        while not ev.is_set():
            print(f"[Thread Running] {name}")
            time.sleep(0.7)
        print(f"[Thread Cleanup] {name}")
    
    t1 = TrackedThread(target = lambda: thread_job("T1"), name="T1", created_from = "test_integrated")
    t2 = TrackedThread(target = lambda: thread_job("T2"), name="T2", created_from = "test_integrated")
    t1.start()
    t2.start()

    # -------- Async Tasks --------
    async def async_job(name):
        while not ShutdownMaster.shutdown_event.is_set():
            print(f"[Task Running] {name}")
            await asyncio.sleep(0.7)
        print(f"[Task Cleanup] {name}")
    
    a1 = Tracked_task.create(coro = async_job("A1"), name="A1", created_from = "test_integrated")
    a2 = Tracked_task.create(coro = async_job("A2"), name="A2", created_from = "test_integrated")

    # -------- Deixa rodar um pouco --------
    await asyncio.sleep(1)

    # -------- Sinaliza shutdown --------
    print("[Test] Triggering shutdown")
    ShutdownMaster.shutdown_event.set()

    # -------- Espera async tasks --------
    # await shutdown_tasks()

    # # -------- Espera threads --------
    # for name, threads in ShutdownMaster.threadsMap.items():
    #     for t in threads:
    #         t.join()
    #         print(f"[Thread Joined] {t.name}")


# ---------------- Run ----------------
# if __name__ == "__main__":


if __name__ == "__main__":
    def start_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=start_loop, args=(loop,), daemon=True, name ="AsyncLoopThread")
    loop_thread.start()

    ShutdownMaster.set_loop( loop)

    #teste 1
    # asyncio.run(test_tracked_task())
    # teste 2
    # test_thread_shutdown()

    future = asyncio.run_coroutine_threadsafe(
        test_integrated(),
        loop
    )
    future.result()

    # ESPERA shutdown terminar
    wait_event(ShutdownMaster.shutDownComplete,"ShutdownMaster.shutDownComplete in tests")
    print("[Test] Integrated test completed successfully!")
    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join()
    loop.close()
    print("fechei o loop corretamente!")

