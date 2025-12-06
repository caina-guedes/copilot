from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time
import hashlib


@dataclass
class WindowFingerPrint:
    # ---- Identidade Universal ----
    app: Optional[str] = None               # ex: "chrome"
    class_name: Optional[str] = None        # ex: "google-chrome"
    
    # Histórico de títulos da janela
    titles_history: List[str] = field(default_factory=list)
    
    # Pontos auxiliares comuns
    os_name: Optional[str] = None           # "linux", "windows", "macos"
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    
    # ---- Identificadores flutuantes (não 100% estáveis) ----
    pid: Optional[int] = None               # pode mudar se app reabre
    win_id: Optional[str] = None            # X11 id, HWND, etc
    
    # ---- Campos específicos por SO (OPCIONAIS) ----
    # Linux
    wm_class: Optional[str] = None
    x11_type: Optional[str] = None
    
    # Windows
    hwnd: Optional[str] = None
    exe_path: Optional[str] = None
    
    # macOS
    bundle_id: Optional[str] = None
    ns_window_id: Optional[str] = None

    # ---- Scores Dinâmicos ----
    confidence_score: float = 1.0  # vai mudando conforme validação acontece
    priority_fields: Dict[str, float] = field(default_factory=dict)

    # ----------------------------------------------------

    def update_title(self, title: str):
        """Adiciona título ao histórico se for novidade."""
        if title and title not in self.titles_history:
            self.titles_history.append(title)
        self.last_seen = time.time()

    def compute_identity_hash(self) -> str:
        """Gera um hash estável baseado nos dados mais robustos"""
        identity_core = f"{self.app}|{self.class_name}|{self.os_name}"
        return hashlib.sha256(identity_core.encode()).hexdigest()

    def similarity(self, other: "WindowFingerprint") -> float:
        """Calcula quanto esta janela se parece com outra."""
        score = 0.0
        total = 3.0  # pesos somados (mínimo)
        
        if self.app and other.app and self.app == other.app:
            score += 1.0
        if self.class_name and other.class_name and self.class_name == other.class_name:
            score += 1.0

        # Bonus se títulos coincidem com histórico
        if any(title in other.titles_history for title in self.titles_history):
            score += 1.0
        
        return score / total  # retorna 0 -> 1

            # "os_name": self.os_name,
            # "win_id": self.win_id,
            # "pid": self.pid,
            # "app": self.app,
            # "class_name": self.class_name,
            # "titles_history": list(self.titles_history),

    def to_dict(self,complete = False) -> dict:
        significant_data = {
            "app": self.app,
            "class_name": self.class_name,
            
            "pid": self.pid,
            "win_id": self.win_id,
            "os_name": self.os_name,
            }
        if not complete:
            significant_data["title"] =  self.titles_history[-1] if self.titles_history else ""
        else:
            significant_data["titles_history"]  =  self.titles_history,
        significant_data["details"] = {}
        for attr, value in self.__dict__.items():
            if attr not in significant_data and value is not None:
                significant_data["details"][attr] = value 
        return significant_data       

    @classmethod
    def from_dict(cls, data: dict) -> "WindowFingerprint":
        return cls(**data)


    def __repr__(self):
        """
        Apenas para depuração/impressão.
        Mostra os campos principais e
        mostra título mais recente + contagem.
        """
        base = {
            "os_name": self.os_name,
            "win_id": self.win_id
        }

        if self.pid: 
            base["pid"] = self.pid
        
        if self.app: 
            base["app"] = self.app
        
        if self.class_name: 
            base["class_name"] = self.class_name


        if self.titles_history:
            base["title"] = self.titles_history[-1]  # título atual
            base["titles_count"] = len(self.titles_history)

        return f"WindowFingerprint({base})"