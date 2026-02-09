import time
import inspect
from functools import wraps
from collections import defaultdict
from threading import Lock
import math



def _generate_table(title, data_dict):
    """
    Recebe um dicionário de stats e retorna UMA STRING GIGANTE
    com a tabela formatada e ordenada por tempo total.
    """
    if not data_dict:
        return ""

    # 1. Preparar lista para ordenação
    rows = []
    for name, stats in data_dict.items():
        calls = stats["calls"]
        if calls == 0: continue
        
        total_ms = stats["total"] * 1000
        avg_ms = total_ms / calls
        min_ms = stats["min"] * 1000 if stats["min"] != math.inf else 0
        max_ms = stats["max"] * 1000
        
        rows.append({
            "name": name,
            "calls": calls,
            "total": total_ms,
            "avg": avg_ms,
            "min": min_ms,
            "max": max_ms
        })

    # 2. Ordenar: Quem gasta mais tempo total fica no topo (Gargalos)
    rows.sort(key=lambda x: x["total"], reverse=True)

    # 3. Construir a String da Tabela (Buffer)
    buffer = []
    width_name = 35 # Largura da coluna de nomes
    
    # Cabeçalho
    buffer.append(f"\n╔{'═'*88}╗")
    buffer.append(f"║ {title:<87}║")
    buffer.append(f"╠{'═'*width_name}╦{'═'*9}╦{'═'*12}╦{'═'*12}╦{'═'*16}╣")
    buffer.append(f"║ {'MÉTODO / FUNÇÃO':<{width_name}} ║ {'CALLS':>7} ║ {'TOTAL(ms)':>10} ║ {'AVG(ms)':>10} ║ {'MIN/MAX(ms)':>14} ║")
    buffer.append(f"╠{'═'*width_name}╬{'═'*9}╬{'═'*12}╬{'═'*12}╬{'═'*16}╣")

    # Linhas de Dados
    for r in rows:
        name_display = (r['name'][:width_name-2] + '..') if len(r['name']) > width_name else r['name']
        
        # Formata min/max juntos para economizar espaço horizontal
        min_max_str = f"{r['min']:.1f}/{r['max']:.1f}"

        line = (
            f"║ {name_display:<{width_name}} ║ "
            f"{r['calls']:>7} ║ "
            f"{r['total']:>10.3f} ║ "
            f"{r['avg']:>10.3f} ║ "
            f"{min_max_str:>14} ║"
        )
        buffer.append(line)

    # Rodapé
    buffer.append(f"╚{'═'*width_name}╩{'═'*9}╩{'═'*12}╩{'═'*12}╩{'═'*16}╝")
    
    return "\n".join(buffer)


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
    def get_class_report_string(cls, class_name):
        """Retorna a string da tabela da classe, sem printar."""
        methods = cls._classes.get(class_name, {})
        if not methods:
            return ""
        return _generate_table(f"📊 REPORT: CLASS [{class_name}]", methods)

    @classmethod
    def get_function_report_string(cls):
        """Retorna a string da tabela de funções soltas, sem printar."""
        if not cls._functions:
            return ""
        return _generate_table("📊 REPORT: STANDALONE FUNCTIONS", cls._functions)

    @classmethod
    def report(cls):
        """
        Gera TODO o relatório de uma vez e faz UM ÚNICO print.
        Ideal para ambientes multiprocesso/multithread.
        """
        full_report_buffer = []
        
        # 1. Adiciona relatório de Funções (se houver)
        func_str = cls.get_function_report_string()
        if func_str:
            full_report_buffer.append(func_str)
        
        # 2. Adiciona relatório de cada Classe
        # Ordenamos as classes por nome para ficar consistente
        for class_name in sorted(cls._classes.keys()):
            class_str = cls.get_class_report_string(class_name)
            if class_str:
                full_report_buffer.append(class_str)
        
        if not full_report_buffer:
            print("[CallRegistry] Nenhum dado coletado ainda.")
            return

        # 3. O GRANDE PRINT ATÔMICO
        final_output = "\n".join(full_report_buffer)
        print(final_output)

    # @classmethod
    # def report_class(cls, class_name):
    #     methods = cls._classes.get(class_name, {})
    #     print(f"\n=== CALL REPORT [{class_name}] ===")

    #     for name, stats in methods.items():
    #         print(_format_stats(name, stats))
    
    # @classmethod
    # def report_function(cls,func = None):
    #     """
    #     essa função precisa receber o nome da função desejada como string
    #     """
    #     if func is None:

    #         print("\n=== FUNCTION CALLS ===")
    #         for name, stats in sorted(cls._functions.items()):
    #             print(_format_stats(name, stats))
    #     else:
    #         print(F"\n=== FUNCTION {func}")
    #         print(_format_stats(func,cls._functions[func]))
    
    # @classmethod
    # def report(cls):
    #     cls.report_function()

    #     print("\n=== CLASS METHOD CALLS ===")
    #     for class_name, methods in cls._classes.items():
    #         cls.report_class(class_name)

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


def _monitor_method(func, class_name):
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
            setattr(cls, attr_name, _monitor_method(attr, class_name))

        # classmethod
        elif isinstance(attr, classmethod):
            original = attr.__func__
            wrapped = _monitor_method(original, class_name)
            setattr(cls, attr_name, classmethod(wrapped))

        # staticmethod
        elif isinstance(attr, staticmethod):
            original = attr.__func__
            wrapped = _monitor_method(original, class_name)
            setattr(cls, attr_name, staticmethod(wrapped))

    # injeta report_calls na classe
    def report_calls(self_or_cls=None):
        CallRegistry.report_class(class_name)

    setattr(cls, "report_calls", report_calls)

    return cls

print("Rodando simulação...")

if __name__ == "__main__":
    @count_methods
    class WindowCache:
        def __init__(self, a):
            time.sleep(0.01) # Simulando trabalho
        
        def get_active_window(self, b):
            time.sleep(0.05) # Simulando syscall lenta

        def refresh(self):
            time.sleep(0.002) # Rápido

    @count_calls
    def funcao_pesada_solta():
        time.sleep(0.1)

    wc = WindowCache(1)
    wc.get_active_window(2)
    wc.get_active_window(3)
    wc.get_active_window(3) # + chamadas para testar ordenação
    wc.refresh()
    
    funcao_pesada_solta()
    funcao_pesada_solta()

    print("\n" + "="*30 + " IMPRIMINDO RELATÓRIO FINAL " + "="*30)
    # Chama o report global (print único para tudo)
    CallRegistry.report()

