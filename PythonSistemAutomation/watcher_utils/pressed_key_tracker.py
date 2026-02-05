import threading
from collections import deque

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
    
    
    def get_all_pressed(self):
        """Retorna uma cópia do set para evitar erros de iteração externa."""
        with self._lock:
            return list(self._pressed)
    
    # 
    # def clear(self):
    #     with self._lock:
    #         self._pressed.clear()
    #         self._history.clear()
