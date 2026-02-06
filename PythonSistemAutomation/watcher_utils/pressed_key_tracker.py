import time
import threading
from collections import deque

history_size = 10

class SafePressedTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._pressed = set()
            # Guarda os últimos X eventos para análise de rastro (trace)
        self._history = deque(maxlen=history_size)

    
    def _normalize(self, key_or_button):
        """
        Limpa a string internamente para garantir consistência.
        Aceita objetos do pynput ou strings puras.
        """
        k = str(key_or_button)
        return k.replace("Key.", "").replace("Button.", "").lower()

    
    def add(self, key):
        key = self._normalize(key)
        with self._lock:
            if key in self._pressed:
                return False  # É um eco ou repetição automática do SO
            
            self._pressed.add(key)
            self._history.append({"key": key, "action": "press", "time": time.time()})
            return True

    
    def remove(self, key):
        key = self._normalize(key)
        with self._lock:
            if key not in self._pressed:
                return False  # Tentativa de soltar algo que já está solto
            
            self._pressed.remove(key)
            self._history.append({"key": key, "action": "release", "time": time.time()})
            return True

    
    def is_pressed(self,key):
        key = self._normalize(key)
        with self._lock:
            return key in self._pressed
    
    
    def is_modifier_active_or_recent(self, seconds=0.2):
        """
        Verifica se um modificador está pressionado AGORA 
        ou se foi solto nos últimos 'seconds' milissegundos.
        """
        with self._lock:
            # 1. Checagem imediata (está pressionado?)
            modifiers = {"ctrl", "alt", "shift", "super", "cmd", "win"}
            if any(m in str(self._pressed).lower() for m in modifiers):
                return True

            # 2. Checagem histórica (foi solto recentemente?)
            agora = time.time()
            for event in reversed(self._history):
                # Se o evento é mais antigo que o limite, paramos de procurar
                if agora - event["time"] > seconds:
                    break
                if any(m in event["key"].lower() for m in modifiers):
                    return True
            
            return False
    
    def discard(self, key):
        """
        Remove a tecla do set se ela estiver presente.
        Se não estiver, não faz nada (mesmo comportamento do set.discard).
        """
        clean_key = self._normalize(key)
        with self._lock:
            if clean_key in self._pressed:
                self._pressed.remove(clean_key)
                # Opcional: Adiciona ao histórico para o rastro forense
                self._history.append({
                    "key": clean_key, 
                    "action": "discard", 
                    "time": time.time()
                })
                # return True
            # return False

    def get_all_pressed(self):
        """Retorna uma cópia do set para evitar erros de iteração externa."""
        with self._lock:
            return list(self._pressed)
    
    def __len__(self):
        """Permite usar len(objeto)"""
        with self._lock:
            return len(self._pressed)

    def __bool__(self):
        """Permite usar 'if objeto:' - retorna True se houver teclas pressionadas"""
        with self._lock:
            return len(self._pressed) > 0
        
    def __iter__(self):
        with self._lock:
            return iter(list(self._pressed))



if __name__ == "__main__":
    
    
    # Instancia o rastreador
    tracker = SafePressedTracker()

    print("--- 1. Teste de Normalização e Adição ---")
    # Testa se ele entende "Key.alt" e "alt" como a mesma coisa
    res1 = tracker.add("Key.alt")
    res2 = tracker.add("alt") 
    print(f"Adicionando 'Key.alt': {res1} (Esperado: True)")
    print(f"Adicionando 'alt' novamente (Eco): {res2} (Esperado: False)")
    print(f"Está pressionado? {tracker.is_pressed('alt')}")

    print("\n--- 2. Teste de Modificadores (Ativo agora) ---")
    # 'alt' é um modificador, então deve retornar True
    print(f"Modificador ativo? {tracker.is_modifier_active_or_recent()} (Esperado: True)")

    print("\n--- 3. Teste de Remoção e Grace Period (Recent) ---")
    tracker.remove("Key.alt")
    print("Removi 'alt'...")
    # Imediatamente após remover, ainda deve ser True por causa do histórico (grace period)
    print(f"Modificador recente (0.5s)? {tracker.is_modifier_active_or_recent(0.5)} (Esperado: True)")
    
    print("Aguardando 0.6 segundos...")
    time.sleep(0.6)
    # Agora deve ser False
    print(f"Modificador recente (0.5s) após espera? {tracker.is_modifier_active_or_recent(0.5)} (Esperado: False)")

    print("\n--- 4. Teste de Mouse e Múltiplas Teclas ---")
    tracker.add("Button.left")
    tracker.add("Key.shift")
    tracker.add("a")
    
    print(f"Lista de pressionados: {tracker.get_all_pressed()}")
    # Deve conter ['left', 'shift', 'a'] (ou em outra ordem, pois é um set)
    
    print(f"Shift está pressionado? {tracker.is_pressed('Key.shift')}")
    print(f"Botão esquerdo está pressionado? {tracker.is_pressed('left')}")

    print("\n--- 5. Teste de Remoção Inexistente ---")
    res_rem = tracker.remove("ctrl")
    print(f"Removendo 'ctrl' que nunca foi apertado: {res_rem} (Esperado: False)")

    print("\n--- Relatório Final ---")
    print(f"Pressionados finais: {tracker.get_all_pressed()}")
