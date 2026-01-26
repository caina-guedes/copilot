from enum import Enum

class LoopState(Enum):
    EMPTY = 0
    SET = 1
    RUNNING = 2
    STOPPING = 3
    CLOSED = 4
    NOT_A_LOOP = 5 


def change_state(cls,new_state):
        if not isinstance(new_state, LoopState):
            cls._log(f"[LoopState] Tried to change to an invalid state: {new_state}","loop")
            return
        elif cls._state != new_state:
            cls._log(f"[LoopState] Changing state from {cls._state} to {new_state}","loop")
            cls._state = new_state
