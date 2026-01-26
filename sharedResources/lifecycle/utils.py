DEBUG_SHUTDOWN = True

def wait_event(evt, name, timeout = 10):
    if not evt.wait(timeout):
        print(f"[DEADLOCK] waiting for {name}")
