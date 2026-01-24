from dataclasses import dataclass, field
from typing import Literal, Optional, Callable, Any 
import time
import threading


@dataclass
class TrackedItem:
    obj: object
    cleanup_event: object
    cleanup_enabled: bool
    name: str | None 
    kind: Literal["thread", "task"]
    created_from: str | None
    cleanup_function: Optional[Callable[..., Any]] = None
    created_at: float = field(default_factory=time.time)
    thread_name: str = field(default_factory=lambda: threading.current_thread().name)