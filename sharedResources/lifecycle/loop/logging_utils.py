import sys
from pathlib import Path
basePath = Path(__file__).resolve().parent.parent.parent.parent
# print("Path added to sys.path:", str(basePath))
sys.path.append(str(basePath))
from sharedResources.lifecycle.loop.state import LoopState

def set_register_log(cls,register):
    if cls._register_log is None:
        cls._register_log = register
    else:
        print("[MyLoop] register_log already set!")

def _log(cls, msg, tag="loop"):
    if cls._state != LoopState.RUNNING:
        msg = f"[MyLoop - State: {cls._state.name}] {msg}"
    if cls._register_log:
        cls._register_log(msg, tag)
    else:
        print(f"[MyLoop - {tag}] {msg}")
        print("No register_log set to log messages properly.")
