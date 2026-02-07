import time
import inspect
from functools import wraps
from collections import defaultdict
from threading import Lock
import math

def _format_stats(name, stats):
    avg = stats["total"] / stats["calls"]
    return (
        f"{name}: "
        f"calls={stats['calls']} | "
        f"total={stats['total']*1000:.3f} ms | "
        f"avg={avg*1000:.3f} ms | "
        f"min={stats['min']*1000:.3f} ms | "
        f"max={stats['max']*1000:.3f} ms"
    )

def _new_stats():
    return {
        "calls": 0,
        "total": 0.0,
        "min": math.inf,
        "max": 0.0
    }

def _update_stats(stats, elapsed):
    stats["calls"] += 1
    stats["total"] += elapsed
    stats["min"] = min(stats["min"], elapsed)
    stats["max"] = max(stats["max"], elapsed)



class CallRegistry:
    _lock = Lock()

    _functions = defaultdict(lambda: _new_stats())
    _classes = defaultdict(lambda: defaultdict(lambda: _new_stats()))

    @classmethod
    def inc_function(cls, func, elapsed):
        key = f"{func.__module__}.{func.__qualname__}"
        with cls._lock:
            _update_stats(cls._functions[key], elapsed)

    @classmethod
    def inc_method(cls, class_name, method_name, elapsed):
        with cls._lock:
            _update_stats(cls._classes[class_name][method_name], elapsed)

    @classmethod
    def report_class(cls, class_name):
        methods = cls._classes.get(class_name, {})
        print(f"\n=== CALL REPORT [{class_name}] ===")

        for name, stats in methods.items():
            print(_format_stats(name, stats))
    
    @classmethod
    def report_function(cls,func = None):
        """
        essa função precisa receber o nome da função desejada como string
        """
        if func is None:

            print("\n=== FUNCTION CALLS ===")
            for name, stats in sorted(cls._functions.items()):
                print(_format_stats(name, stats))
        else:
            print(F"\n=== FUNCTION {func}")
            print(_format_stats(func,cls._functions[func]))
    
    @classmethod
    def report(cls):
        cls.report_function()

        print("\n=== CLASS METHOD CALLS ===")
        for class_name, methods in cls._classes.items():
            cls.report_class(class_name)

def count_calls(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            CallRegistry.inc_function(func, elapsed)
    return wrapper


def _wrap_method(func, class_name):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            CallRegistry.inc_method(class_name, func.__name__, elapsed)
    return wrapper



def count_methods(cls):
    class_name = cls.__name__

    for attr_name, attr in cls.__dict__.items():
        if attr_name.startswith("__") and attr_name != "__init__":
            continue

        # método normal
        if inspect.isfunction(attr):
            setattr(cls, attr_name, _wrap_method(attr, class_name))

        # classmethod
        elif isinstance(attr, classmethod):
            original = attr.__func__
            wrapped = _wrap_method(original, class_name)
            setattr(cls, attr_name, classmethod(wrapped))

        # staticmethod
        elif isinstance(attr, staticmethod):
            original = attr.__func__
            wrapped = _wrap_method(original, class_name)
            setattr(cls, attr_name, staticmethod(wrapped))

    # injeta report_calls na classe
    def report_calls(self_or_cls=None):
        CallRegistry.report_class(class_name)

    setattr(cls, "report_calls", report_calls)

    return cls



if __name__ == "__main__":
    @count_methods
    class WindowCache:
        def __init__(self,  a ):
            pass
        def get_active_window(self, b):
            pass

        def refresh(self):
            pass

    @count_calls
    def standalone():
        pass
    
    wc = WindowCache(1)

    wc.get_active_window(2)
    wc.get_active_window(3)
    wc.refresh()

    standalone()
    standalone()
    standalone()

    wc.report_calls()
    CallRegistry.report()

