from enum import Enum
from threading import Condition
import threading
import time
 
class State(Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    EMERGENCY = "EMERGENCY"

    def __eq__(self, other):
        """
        Comparação Estrita:
        Só permite comparar State com State.
        Qualquer outra coisa (String, Int, None, Boolean) lança erro.
        """
        # Verifica se o objeto comparado é EXATAMENTE da mesma classe (State)
        if not isinstance(other, State):

            # Permite verificar 'is not None' com segurança
            if other is None: 
                return False
            
            raise TypeError(
                f"⛔ COMPARAÇÃO ILEGAL DETECTADA:\n"
                f"   Tentativa de comparar 'State.{self.name}' com um objeto do tipo '{type(other).__name__}' ({repr(other)}).\n"
                f"   Solução: Compare apenas com membros do Enum (ex: State.RUNNING)."
            )
        
        # Se for do tipo certo, deixa o Enum fazer a comparação normal de valores
        return super().__eq__(other)

    def __hash__(self):
        """
        Restaura a capacidade de usar o State como chave de dicionário
        (necessário pois sobrescrevemos o __eq__).
        """
        return hash(self._name_)
    
    def __str__(self):
        return self.name  # Retorna "RUNNING" em vez de "State.RUNNING"

    # Helpers de leitura rápida (Sintax Sugar)
    @property
    def is_running(cls):
        with cls._cond: return cls._state == State.RUNNING

    @property
    def is_shutting_down(cls):
        with cls._cond: return cls._state == State.SHUTTING_DOWN
    

# Regras de transição
_ALLOWED_TRANSITIONS = {
    State.INIT: {State.RUNNING, State.EMERGENCY}, # Pode falhar no init direto pra emergency
    State.RUNNING: {State.SHUTTING_DOWN, State.EMERGENCY},
    State.SHUTTING_DOWN: {State.EMERGENCY}, # Importante: Se falhar o shutdown, vai pra emergency
    State.EMERGENCY: set(), # Fim da linha
}

class StateManagerMeta(type):
    """
    Metaclasse para permitir properties estáticas com setters robustos.
    Isso permite usar StateManager.state = ... com validação.
    """
    _state = State.INIT
    # _lock = RLock()
    # 1. Substituímos RLock por Condition (que já tem um RLock dentro)
    _cond = Condition() 

    @property
    def state(cls) -> State:
        with cls._cond: # Garante que a leitura do estado seja thread-safe
            return cls._state

    @state.setter
    def state(cls, new_state: State):
        with cls._cond:  # Garante que a validação e a mudança de estado sejam atômicas
            current = cls._state
            
            # Se já for o mesmo estado, ignora (idempotência)
            if current == new_state:
                return

            # Validação ATÔMICA (dentro do Lock)
            if new_state not in _ALLOWED_TRANSITIONS[current]:
                 # Log de erro crítico aqui seria bem-vindo
                raise RuntimeError( f"⛔ [LIFECYCLE] Transição de Estado Ilegal: [{current.name}] -> [{new_state.name}] " f"(Permitidos: {[s.name for s in _ALLOWED_TRANSITIONS[current]]})"
                )
            cls._state = new_state
            print(f"🔄 [LIFECYCLE] Mudança de Estado:  {current.name}   ➡️   {new_state.name}     ")
            # --- AQUI ESTÁ O PULO DO GATO ---
            # Avisa: "Ei, mudei o estado! Quem estiver dormindo esperando, acorde e verifique."
            # Se ninguém estiver esperando, isso não faz nada (custo zero).
            cls._cond.notify_all() 

    # --- Método Bônus (O motivo de usarmos Condition) ---
    def wait_for_state(cls, target_state: State, timeout=None) -> bool:
        """
        Bloqueia a execução até que o estado seja igual ao target_state.
        Retorna True se chegou no estado, False se deu timeout.
        """
        with cls._cond:
            # O wait_for gerencia o lock automaticamente:
            # 1. Libera o lock e dorme.
            # 2. Acorda quando alguém chama notify_all().
            # 3. Readquire o lock e checa a condição (lambda).
            return cls._cond.wait_for(lambda: cls._state == target_state, timeout=timeout)

class StateManager(metaclass=StateManagerMeta):
    """
    Classe estática para gerenciar o estado global do Lifecycle.
    Uso:
        StateManager.state = State.RUNNING
        print(StateManager.state)
    """
    pass


# ==========================================
# 2. O TESTE DE CONCORRÊNCIA
# ==========================================


# if __name__ == "__main__":
#     def worker_espera_running(id):
#         print(f"[{time.strftime('%X')}] 👷 Worker {id}: Iniciado. Dormindo até ficar RUNNING...")
        
#         # Esta linha vai BLOQUEAR a thread. Ela não gasta CPU.
#         chegou = StateManager.wait_for_state(State.RUNNING, timeout=5)
        
#         if chegou:
#             print(f"[{time.strftime('%X')}] ✅ Worker {id}: ACORDOU! O sistema está RUNNING.")
#         else:
#             print(f"[{time.strftime('%X')}] ❌ Worker {id}: Cansou de esperar (Timeout).")

#     def worker_espera_shutdown(id):
#         print(f"[{time.strftime('%X')}] 💀 Reaper {id}: Iniciado. Dormindo até ficar SHUTTING_DOWN...")
        
#         # Bloqueia até desligar
#         StateManager.wait_for_state(State.SHUTTING_DOWN)
        
#         print(f"[{time.strftime('%X')}] ✅ Reaper {id}: ACORDOU! Hora de limpar a sujeira.")

#     print(f"--- ESTADO INICIAL: {StateManager.state} ---\n")

#     # 1. Iniciamos threads que vão ficar esperando (Bloqueadas)
#     t1 = threading.Thread(target=worker_espera_running, args=(1,))
#     t2 = threading.Thread(target=worker_espera_running, args=(2,))
#     t3 = threading.Thread(target=worker_espera_shutdown, args=(3,))

#     t1.start()
#     t2.start()
#     t3.start()

#     # Dá um tempo para provar que elas estão dormindo
#     print("\n... Main thread vai esperar 2 segundos antes de iniciar o sistema ...\n")
#     time.sleep(2)

#     # 2. Mudança de Estado -> RUNNING
#     print(f"[{time.strftime('%X')}] 👑 Main: Alterando estado para RUNNING!")
#     StateManager.state = State.RUNNING
#     # EXPECTATIVA: t1 e t2 devem acordar IMEDIATAMENTE. t3 continua dormindo.

#     print("\n... Main thread vai esperar mais 2 segundos rodando ...\n")
#     time.sleep(2)

#     # 3. Mudança de Estado -> SHUTTING_DOWN
#     print(f"[{time.strftime('%X')}] 👑 Main: Alterando estado para SHUTTING_DOWN!")
#     StateManager.state = State.SHUTTING_DOWN
#     # EXPECTATIVA: t3 deve acordar IMEDIATAMENTE.

#     # Limpeza
#     t1.join()
#     t2.join()
#     t3.join()
#     print("\n--- TESTE FINALIZADO COM SUCESSO ---")
# --- TESTE RÁPIDO PARA VC VALIDAR ---

if __name__ == "__main__":
    class testClass():
        innerState = StateManager.state
    try:
        print(f"Estado Inicial: {testClass.innerState}")
        if testClass.innerState is State.INIT:
            print("comparação com is funciona perfeitamente para enums, ótimo!")
        # 1. Transição Válida

        testClass.innerState = State.RUNNING

        print(f"Mudou  na classe de texte para: {testClass.innerState}")
        print(f"Estado Atual do StateManager: {StateManager.state}")

        
        # 2. Transição Válida
        testClass.innerState = State.SHUTTING_DOWN
        print(f"Mudou  na classe de texte para: {testClass.innerState}")
        print(f"Mudou para: {StateManager.state}")
        try:

            if StateManager.state == "SHUTTING_DOWN":  # Teste de comparação com string
                print("Comparação com string funcionou (não deveria)")
            else:
                print("Comparação com string falhou como esperado.")
        except Exception as e:
            print(f"✅ Erro Capturado Corretamente ao comparar com string:\n{e}")
            # print("Comparação com string falhou como esperado.")
        # 3. Transição INVÁLIDA (Shutdown -> Running)
        print("Tentando voltar para RUNNING (deve falhar)...")
        StateManager.state = State.RUNNING
        
    except RuntimeError as e:
        print(f"\n✅ Erro Capturado Corretamente:\n{e}")

    # 4. Emergency (Sempre permitido do Shutdown na minha correção)
    StateManager.state = State.EMERGENCY
    print(f"\nEstado Final: {StateManager.state}")

