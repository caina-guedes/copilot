import time
import threading
from collections import deque

history_size = 10

class SafePressedTracker:
    active_instances = set()  # Para monitorar todas as instâncias ativas, se necessário
    all_pressed = set()  # Set global para rastrear todas as teclas pressionadas em todas as instâncias
    all_history = deque(maxlen=history_size)  # Histórico global para rastrear eventos recentes
    
    @classmethod
    def get_global_pressed(cls):
        """Retorna uma cópia do set global de teclas pressionadas."""
        with threading.Lock():  # Lock global para acessar o set global
            global_instance= SafePressedTracker()
            for key in cls.all_pressed:
                global_instance.add(key)
            return global_instance
        
    def __init__(self):
        self._lock = threading.Lock()
        self._pressed = set()
            # Guarda os últimos X eventos para análise de rastro (trace)
        self.__class__.active_instances.add(self)

    def __add__(self, other):
        new = SafePressedTracker()
        for key in self.get_all_pressed():
            new.add(key)
        for key in other.get_all_pressed():
            new.add(key)
        return new


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
            self.__class__.all_history.append({"key": key, "action": "press", "time": time.time()})
            self.__class__.all_pressed.add(key)  # Adiciona ao set global
            return True
        return False  # Se por algum motivo não conseguiu adicionar (deve ser raro, só se tiver um erro de concorrência)

    
    def remove(self, key):
        key = self._normalize(key)
        with self._lock:
            if key not in self._pressed:
                return False  # Tentativa de soltar algo que já está solto
            
            self._pressed.remove(key)
            # self.__class__.all_pressed.remove(key)  # Remove do set global
            self.__class__.all_history.append({"key": key, "action": "release", "time": time.time()})
            self.__class__.all_pressed.discard(key)  # Remove do set global
            return True
        return False  # Se por algum motivo não conseguiu remover (deve ser raro, só se tiver um erro de concorrência)
    
    def is_pressed(self,key):
        key = self._normalize(key)
        with self._lock:
            return key in self.__class__.all_pressed  # Verifica no set global para refletir o estado real do sistema
    
    
    def is_modifier_active_or_recent(self, seconds=0.2):
        """
        Verifica se um modificador está pressionado AGORA 
        ou se foi solto nos últimos 'seconds' milissegundos.
        """
        global_pressed = self.__class__.get_global_pressed()  # Pega o estado global atual
        with self._lock:
            # 1. Checagem imediata (está pressionado?)
            modifiers = {"ctrl", "alt", "shift", "super", "cmd", "win"}
            if any(m in str(global_pressed).lower() for m in modifiers):
                return True

            # 2. Checagem histórica (foi solto recentemente?)
            agora = time.time()
            for event in reversed(self.__class__.all_history):
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
                self._pressed.discard(clean_key)
                self.__class__.all_pressed.discard(clean_key)  # Remove do set global
                # Opcional: Adiciona ao histórico para o rastro forense
                self.__class__.all_history.append({
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
