import threading
import time
import asyncio
import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.generalUtils.taskStructure import tracked_task, shutdownMaster, TrackedThread , shutdown_tasks

async def dummy_task(x):
    await asyncio.sleep(0.1)
    return x * 2

async def test_tracked_task():
    t = tracked_task(dummy_task(5), name="test")
    assert t in [item.obj for item in shutdownMaster.tasksMap["test"]]
    result = await t
    assert result == 10
    print("✅ tracked_task basic test passed")


async def cancellable_task():
    try:
        while not shutdownMaster.shutdown_event.is_set():
            await asyncio.sleep(0.1)
        return "done"
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
    shutdownMaster.shutdown_event.set()  # sinaliza shutdown
    await asyncio.gather(t1, t2, return_exceptions=True)
    print("✅ shutdown test passed")

def dummy_thread():
    while not shutdownMaster.shutdown_event.is_set():
        time.sleep(0.1)
    print("[cleanup] Thread finalizando")

def test_thread_shutdown():
    t = TrackedThread(target=dummy_thread, name="thread1", created_from = "test_thread_shutdown")
    t.start()

    time.sleep(0.3)
    shutdownMaster.shutdown_event.set()
    # t.join()

# ---------------- Test integrado ----------------
async def test_integrated():
    # Define loop principal
    shutdownMaster.running_loop = asyncio.get_running_loop()

    # -------- Threads --------
    def thread_job(name):
        while not shutdownMaster.shutdown_event.is_set():
            print(f"[Thread Running] {name}")
            time.sleep(0.2)
        print(f"[Thread Cleanup] {name}")
    
    t1 = TrackedThread(target=lambda: thread_job("T1"), name="T1", created_from = "test_integrated")
    t2 = TrackedThread(target=lambda: thread_job("T2"), name="T2", created_from = "test_integrated")
    t1.start()
    t2.start()

    # -------- Async Tasks --------
    async def async_job(name):
        while not shutdownMaster.shutdown_event.is_set():
            print(f"[Task Running] {name}")
            await asyncio.sleep(0.2)
        print(f"[Task Cleanup] {name}")
    
    a1 = tracked_task(async_job("A1"), name="A1", created_from = "test_integrated")
    a2 = tracked_task(async_job("A2"), name="A2", created_from = "test_integrated")

    # -------- Deixa rodar um pouco --------
    await asyncio.sleep(1)

    # -------- Sinaliza shutdown --------
    print("[Test] Triggering shutdown")
    shutdownMaster.shutdown_event.set()

    # -------- Espera async tasks --------
    # await shutdown_tasks()

    # # -------- Espera threads --------
    # for name, threads in shutdownMaster.threadsMap.items():
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

    shutdownMaster.running_loop = loop

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
    shutdownMaster.shutDownComplete.wait()
    print("[Test] Integrated test completed successfully!")
    loop.call_soon_threadsafe(loop.stop)
    loop_thread.join()
    loop.close()

