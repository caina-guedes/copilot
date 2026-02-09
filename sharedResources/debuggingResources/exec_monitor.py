import time
import inspect
from functools import wraps
from collections import defaultdict
from threading import Lock
import math
import threading

# --- ESTRUTURAS DE DADOS ---

def _new_stats():
    return {
        "calls": 0,
        "total": 0.0,
        "min": math.inf,
        "max": 0.0,
        "active": 0  # Nova métrica: quantos estão rodando agora
    }

def _update_stats(stats, elapsed):
    """Atualiza estatísticas de chamadas FINALIZADAS."""
    stats["calls"] += 1
    stats["total"] += elapsed
    if elapsed < stats["min"]: stats["min"] = elapsed
    if elapsed > stats["max"]: stats["max"] = elapsed

# --- GERADOR DE TABELA (COM SUPORTE A ATIVOS) ---

def _generate_table(title, data_dict):
    if not data_dict:
        return ""

    # Preparar lista
    rows = []
    for name, stats in data_dict.items():
        # Se nunca foi chamado e não está ativo, ignora
        if stats["calls"] == 0 and stats["active"] == 0:
            continue
        
        calls = stats["calls"]
        active = stats["active"]
        
        # Converte para ms
        total_ms = stats["total"] * 1000
        # Média considera apenas chamadas finalizadas para não distorcer
        avg_ms = (total_ms / calls) if calls > 0 else 0 
        
        min_ms = stats["min"] * 1000 if stats["min"] != math.inf else 0
        max_ms = stats["max"] * 1000
        
        rows.append({
            "name": name,
            "calls": calls,
            "active": active,
            "total": total_ms,
            "avg": avg_ms,
            "min": min_ms,
            "max": max_ms
        })

    # Ordena pelo Tempo Total (O que consome mais recursos fica no topo)
    rows.sort(key=lambda x: x["total"], reverse=True)

    buffer = []
    # Layout da Tabela
    w_name = 35
    header_top = f"\n╔{'═'*98}╗"
    title_row  = f"║ {title:<97}║"
    col_def    = f"╠{'═'*w_name}╦{'═'*9}╦{'═'*8}╦{'═'*12}╦{'═'*12}╦{'═'*16}╣"
    header_txt = f"║ {'MÉTODO / FUNÇÃO':<{w_name}} ║ {'CALLS':>7} ║ {'ACTIVE':>6} ║ {'TOTAL(ms)':>10} ║ {'AVG(ms)':>10} ║ {'MIN/MAX(ms)':>14} ║"
    
    buffer.append(header_top)
    buffer.append(title_row)
    buffer.append(col_def)
    buffer.append(header_txt)
    buffer.append(col_def)

    for r in rows:
        name_display = (r['name'][:w_name-2] + '..') if len(r['name']) > w_name else r['name']
        min_max_str = f"{r['min']:.1f}/{r['max']:.1f}"

        # Destaque visual se estiver rodando (Active > 0)
        active_str = f"{r['active']}"
        if r['active'] > 0:
            active_str = f"*{r['active']}*" # Asterisco indica atividade

        line = (
            f"║ {name_display:<{w_name}} ║ "
            f"{r['calls']:>7} ║ "
            f"{active_str:>6} ║ " # Coluna nova
            f"{r['total']:>10.3f} ║ "
            f"{r['avg']:>10.3f} ║ "
            f"{min_max_str:>14} ║"
        )
        buffer.append(line)

    buffer.append(f"╚{'═'*w_name}╩{'═'*9}╩{'═'*8}╩{'═'*12}╩{'═'*12}╩{'═'*16}╝")
    return "\n".join(buffer)


# --- REGISTRY CENTRAL ---

class CallRegistry:
    _lock = Lock()
    
    # Armazenamento persistente (Histórico)
    _functions = defaultdict(lambda: _new_stats())
    _classes = defaultdict(lambda: defaultdict(lambda: _new_stats()))
    
    # Armazenamento volátil (O que está rodando AGORA)
    # Key: Token (Objeto único) -> Value: (tipo, grupo, nome, start_time)
    _active_calls = {} 

    @classmethod
    def start_track(cls, type_scope, group, name):
        """Registra que uma função começou."""
        token = object() # Identificador único para esta execução específica
        start_time = time.perf_counter()
        with cls._lock:
            cls._active_calls[token] = (type_scope, group, name, start_time)
        return token, start_time

    @classmethod
    def end_track(cls, token, elapsed):
        """Finaliza o registro e move para o histórico."""
        with cls._lock:
            # Recupera info e remove da lista de ativos
            if token in cls._active_calls:
                type_scope, group, name, _ = cls._active_calls.pop(token)
                
                # Atualiza histórico
                if type_scope == 'func':
                    _update_stats(cls._functions[name], elapsed)
                elif type_scope == 'method':
                    _update_stats(cls._classes[group][name], elapsed)

    @classmethod
    def _get_snapshot(cls):
        """
        Cria uma visão unificada do histórico + chamadas ativas.
        Calcula o tempo 'parcial' de quem ainda está rodando.
        """
        with cls._lock:
            # 1. Copia profunda o suficiente para não alterar o original
            # (Dict comprehension cria novos dicts de stats)
            snapshot_funcs = {k: v.copy() for k, v in cls._functions.items()}
            snapshot_classes = {}
            for c_name, methods in cls._classes.items():
                snapshot_classes[c_name] = {m_name: stats.copy() for m_name, stats in methods.items()}

            # 2. Itera sobre ativos e 'simula' que eles acabaram agora
            now = time.perf_counter()
            for (scope, group, name, start_time) in cls._active_calls.values():
                elapsed_so_far = now - start_time
                
                # Seleciona onde injetar o dado temporário
                if scope == 'func':
                    target = snapshot_funcs.setdefault(name, _new_stats())
                else: # method
                    if group not in snapshot_classes:
                        snapshot_classes[group] = {}
                    target = snapshot_classes[group].setdefault(name, _new_stats())

                # Adiciona estatística temporária
                # (Não incrementamos 'calls' para indicar que ainda não acabou, 
                # ou incrementamos? Melhor manter calls fixo e usar 'active')
                target["active"] += 1
                target["total"] += elapsed_so_far
                
                # Atualiza Max se o tempo decorrido já for maior que o recorde
                if elapsed_so_far > target["max"]:
                    target["max"] = elapsed_so_far

            return snapshot_funcs, snapshot_classes

    @classmethod
    def report(cls):
        """Gera e imprime o relatório considerando processos em andamento."""
        # Pega o snapshot thread-safe
        funcs_data, classes_data = cls._get_snapshot()
        
        full_buffer = []

        # Relatório de Funções
        if funcs_data:
            full_buffer.append(_generate_table("📊 REPORT: STANDALONE FUNCTIONS", funcs_data))
        
        # Relatório de Classes
        for class_name in sorted(classes_data.keys()):
            full_buffer.append(_generate_table(f"📊 REPORT: CLASS [{class_name}]", classes_data[class_name]))
            
        if not full_buffer:
            print("[CallRegistry] Sem dados para exibir.")
            return

        print("\n".join(full_buffer))


# --- DECORATORS (ATUALIZADOS) ---

def count_calls(func):
    """Para funções soltas (standalone)."""
    # Descobre nome qualificado (Module.func)
    name = func.__qualname__
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. Avisa que começou
        token, start = CallRegistry.start_track('func', None, name)
        try:
            return func(*args, **kwargs)
        finally:
            # 2. Avisa que terminou (mesmo com erro)
            elapsed = time.perf_counter() - start
            CallRegistry.end_track(token, elapsed)
    return wrapper

def _monitor_method(func, class_name):
    """Para métodos de classe."""
    method_name = func.__name__
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        token, start = CallRegistry.start_track('method', class_name, method_name)
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            CallRegistry.end_track(token, elapsed)
    return wrapper

def count_methods(cls):
    """Decorator de Classe."""
    class_name = cls.__name__

    for attr_name, attr in cls.__dict__.items():
        if attr_name.startswith("__") and attr_name != "__init__":
            continue

        if inspect.isfunction(attr):
            setattr(cls, attr_name, _monitor_method(attr, class_name))
        elif isinstance(attr, classmethod):
            original = attr.__func__
            wrapped = _monitor_method(original, class_name)
            setattr(cls, attr_name, classmethod(wrapped))
        elif isinstance(attr, staticmethod):
            original = attr.__func__
            wrapped = _monitor_method(original, class_name)
            setattr(cls, attr_name, staticmethod(wrapped))

    # Injeta método de report na instância
    def report_calls(self_or_cls=None):
        CallRegistry.report()

    setattr(cls, "report_calls", report_calls)
    return cls

# --- TESTE RÁPIDO ---
if __name__ == "__main__":
    print("Iniciando simulação de processos longos...")

    @count_methods
    class Watcher:
        def __init__(self):
            time.sleep(0.1)
        
        def run_forever(self):
            print("   -> Watcher rodando (vai dormir 2s)...")
            time.sleep(2) # Simula processo longo
            print("   -> Watcher acordou.")

        def quick_check(self):
            time.sleep(0.05)

    # Thread separada para rodar a função longa
    w = Watcher()
    t = threading.Thread(target=w.run_forever)
    t.start()

    time.sleep(0.5) # Espera a thread começar
    w.quick_check() # Faz uma chamada rápida no meio
    
    print("\n--- TIRANDO REPORT NO MEIO DA EXECUÇÃO ---")
    print("Espere ver 'run_forever' com status ACTIVE e tempo parcial alto.")
    CallRegistry.report()
    
    t.join() # Espera acabar
    print("\n--- TIRANDO REPORT FINAL ---")
    CallRegistry.report()