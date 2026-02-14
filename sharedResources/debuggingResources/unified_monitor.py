# from sharedResources.debuggingResources.unified_monitor import sys_monitor, monitor_class

import functools
import asyncio
import inspect
import time
from typing import Callable, Any, Optional

from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Imports dos seus recursos existentes
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
# Certifique-se que CallRegistry está acessível aqui
from sharedResources.debuggingResources.exec_monitor import CallRegistry 
# (Ou mova a classe CallRegistry para este arquivo para ficar tudo junto)
errors_list = []
# ==============================================================================
# UNIFIED MONITOR - O "One Ring to Rule Them All"
# ==============================================================================

def sys_monitor(
    _func: Optional[Callable] = None, 
    *, 
    stats: bool = True, 
    errors: bool = True,
    scope: str = 'auto', # 'auto', 'func', 'method'
    group: str = None    # Nome da classe (se for método)
):
    """
    Decorator Unificado para Monitoramento de Performance e Erros.
    
    Uso:
        @sys_monitor                     -> Monitora TUDO (padrão)
        @sys_monitor(stats=False)        -> Monitora só erros
        @sys_monitor(errors=False)       -> Monitora só estatísticas
    """
    
    def decorator_factory(func: Callable) -> Callable:
        # 1. Detecção de Metadados
        is_coroutine = inspect.iscoroutinefunction(func) or (hasattr(func, '__wrapped__') and inspect.iscoroutinefunction(func.__wrapped__))
        
        # Determina o escopo (Function vs Method) para o CallRegistry
        real_scope = scope
        real_group = group
        
        if real_scope == 'auto':
            # Tenta adivinhar baseado no nome qualificado
            if '.' in func.__qualname__:
                real_scope = 'method'
                # Tenta extrair o nome da classe do qualname (ex: ClassName.method_name)
                if not real_group:
                    real_group = func.__qualname__.split('.')[-2]
            else:
                real_scope = 'func'
                real_group = None

        func_name = func.__name__ # Ou __qualname__ se preferir nomes completos
        
        # Registra a função no CallRegistry imediatamente (para aparecer no relatório zerada)
        if stats:
            # Assumindo que você importou CallRegistry
            # from sharedResources.debuggingResources.exec_monitor import CallRegistry
            CallRegistry.register(real_scope, real_group, func_name)

        # ----------------------------------------------------------------------
        # WRAPPER ASSÍNCRONO (ASYNC)
        # ----------------------------------------------------------------------
        if is_coroutine:
            @functools.wraps(func)
            async def unified_async_wrapper(*args, **kwargs):
                token = None
                start_time = 0
                elapsed = None
                # A. Início do Tracking (Stats)
                if stats:
                    # from sharedResources.debuggingResources.exec_monitor import CallRegistry
                    token, start_time = CallRegistry.start_track(real_scope, real_group, func_name)
                
                try:
                    # B. Execução Real
                    return await func(*args, **kwargs)
                
                except asyncio.CancelledError:
                    # Cancelamento não é erro, apenas repassa
                    if stats and token:
                        elapsed = time.perf_counter() - start_time
                    raise
                except Exception as e:
                    # C. Tratamento de Erro
                    if stats and token:
                        elapsed = time.perf_counter() - start_time
                    if errors:
                        # --- FUTURO MAPA DE ERROS ENTRA AQUI ---
                        # ErrorRegistry.register(real_group, func_name, e)
                        error_report =log_error_forensics_plus(e , retornar = True)
                        errors_list.append(error_report)
                    raise e
                finally:
                    # D. Fim do Tracking (Stats)
                    if elapsed is None:
                        elapsed = time.perf_counter() - start_time
                    if stats and token:
                        CallRegistry.end_track(token, elapsed)
                        

            
            return unified_async_wrapper

        # ----------------------------------------------------------------------
        # WRAPPER SÍNCRONO (SYNC)
        # ----------------------------------------------------------------------
        else:
            @functools.wraps(func)
            def unified_sync_wrapper(*args, **kwargs):
                token = None
                start_time = 0
                elapsed = None
                
                if stats:
                    from sharedResources.debuggingResources.exec_monitor import CallRegistry
                    token, start_time = CallRegistry.start_track(real_scope, real_group, func_name)
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                     # C. Tratamento de Erro
                    if stats and token:
                        elapsed = time.perf_counter() - start_time
                    if errors:
                        # --- FUTURO MAPA DE ERROS ENTRA AQUI ---
                        # ErrorRegistry.register(real_group, func_name, e)
                        error_report = log_error_forensics_plus(e,retornar = True)
                        errors_list.append(error_report)
                    raise e
                
                finally:
                    if elapsed is None:
                        elapsed = time.perf_counter() - start_time
                    if stats and token:
                        elapsed = time.perf_counter() - start_time
                        CallRegistry.end_track(token, elapsed)
            
            return unified_sync_wrapper

    # Lógica para permitir uso com ou sem parênteses: @sys_monitor ou @sys_monitor(stats=False)
    if _func is None:
        return decorator_factory
    else:
        return decorator_factory(_func)

# ==============================================================================
# CLASS DECORATOR (Para aplicar em tudo automaticamente)
# ==============================================================================

def monitor_class(cls=None, *, stats=True, errors=True):
    """
    Aplica o @sys_monitor em todos os métodos da classe.
    Uso:
        @monitor_class
        class MinhaClasse: ...
    """
    
    def _apply_to_class(target_cls):
        class_name = target_cls.__name__
        
        # Itera sobre o __dict__ para pegar o que está definido explicitamente
        # (Se quiser herança, use dir(target_cls) e filtro de setatrr)
        for attr_name, attr in list(target_cls.__dict__.items()):
            
            if attr_name.startswith("__") and attr_name != "__init__":
                continue

            # Wrapper Factory Helper
            def apply_monitor(method_func, is_static=False, is_class=False):
                # Aplicamos o sys_monitor forçando o escopo 'method' e o grupo (Nome da Classe)
                return sys_monitor(
                    method_func, 
                    stats=stats, 
                    errors=errors, 
                    scope='method', 
                    group=class_name
                )

            # 1. Class Method
            if isinstance(attr, classmethod):
                if hasattr(attr, "__func__"):
                    wrapped = apply_monitor(attr.__func__, is_class=True)
                    setattr(target_cls, attr_name, classmethod(wrapped))

            # 2. Static Method
            elif isinstance(attr, staticmethod):
                if hasattr(attr, "__func__"):
                    wrapped = apply_monitor(attr.__func__, is_static=True)
                    setattr(target_cls, attr_name, staticmethod(wrapped))

            # 3. Métodos Normais (Sync ou Async)
            elif inspect.isfunction(attr):
                wrapped = apply_monitor(attr)
                setattr(target_cls, attr_name, wrapped)
        
        # Injeta método de report de conveniência
        if stats:
            def report_calls(self_or_cls=None):
                from sharedResources.debuggingResources.exec_monitor import CallRegistry
                CallRegistry.report()
            setattr(target_cls, "report_calls", report_calls)
            
        return target_cls

    if cls is None:
        return _apply_to_class
    else:
        return _apply_to_class(cls)




if __name__ == "__main__":
    import asyncio
    import time
    from sharedResources.debuggingResources.exec_monitor import CallRegistry

    print("\n" + "="*60)
    print("🚀 INICIANDO BATERIA DE TESTES: SYS_MONITOR & MONITOR_CLASS")
    print("="*60 + "\n")

    # ==========================================
    # 1. DEFINIÇÃO DOS CENÁRIOS
    # ==========================================

    # --- Caso A: Funções Soltas (Sync/Async) ---
    @sys_monitor
    def teste_sync_sucesso(x, y):
        time.sleep(0.01) # Simula delay
        return x + y

    @sys_monitor
    async def teste_async_sucesso(x, y):
        await asyncio.sleep(0.01) # Simula await
        return x * y

    @sys_monitor
    def teste_sync_erro():
        raise ValueError("Simulação de Erro Síncrono")

    @sys_monitor
    async def teste_async_erro():
        await asyncio.sleep(0.01)
        raise ValueError("Simulação de Erro Assíncrono")

    # --- Caso B: Classe Decorada (Todos os tipos de métodos) ---
    def func_ruim(a):
        return a/0
    
    @monitor_class
    class TesteClasse:
        def __init__(self):
            # Init não deve ser decorado
            pass

        def metodo_instancia(self):
            time.sleep(0.01)
            return "instance_ok"

        async def metodo_async(self):
            await asyncio.sleep(0.01)
            return "async_ok"

        @classmethod
        def metodo_classe(cls):
            return "class_method_ok"

        @staticmethod
        def metodo_estatico():
            return "static_method_ok"
        
        def metodo_com_erro(self):
            func_ruim(2)
            # raise RuntimeError("Erro dentro da classe")

    # --- Caso C: Configurações Específicas ---
    @sys_monitor(stats=False) # Não deve aparecer no report (ou aparecer zerado dependendo da implementação)
    def teste_sem_stats():
        return "rodou_sem_stats"

    # ==========================================
    # 2. EXECUÇÃO
    # ==========================================

    async def runner():
        print("--- [1] Testando Funções Soltas ---")
        
        res = teste_sync_sucesso(10, 20)
        print(f"✅ Sync Sucesso (Esperado 30): {res}")

        res = await teste_async_sucesso(10, 20)
        print(f"✅ Async Sucesso (Esperado 200): {res}")

        print("--- [2] Testando Captura de Erros ---")
        try:
            teste_sync_erro()
        except ValueError:
            print("✅ Erro Síncrono capturado e relançado com sucesso.")

        try:
            await teste_async_erro()
        except ValueError:
            print("✅ Erro Assíncrono capturado e relançado com sucesso.")

        print("\n--- [3] Testando Classe (@monitor_class) ---")
        obj = TesteClasse()
        
        print(f"🔹 Instância: {obj.metodo_instancia()}")
        print(f"🔹 Async:     {await obj.metodo_async()}")
        print(f"🔹 ClassMeth: {TesteClasse.metodo_classe()}")
        print(f"🔹 Static:    {TesteClasse.metodo_estatico()}")

        try:
            obj.metodo_com_erro()
        except :
            print("✅ Erro no método capturado com sucesso.")

        print("\n--- [4] Testando Flags (Stats=False) ---")
        teste_sem_stats()
        print("✅ Função sem stats executada.")

        print("\n" + "="*60)
        print("📊 RELATÓRIO FINAL (Verifique se todos aparecem abaixo)")
        print("="*60)
        
        # Gera o relatório para provar que o CallRegistry capturou tudo
        CallRegistry.report()

    # Roda o loop de teste
    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        pass