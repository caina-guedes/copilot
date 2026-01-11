# db.py
import sqlite3
from typing import Dict, List, Any
import time
from sharedResources.generalUtils.aprint import aprint

DEFAULT_BATCH = 500

CREATE_SCHEMA_SQL = open("db_schema.sql", "r", encoding="utf-8").read()

def open_db(path: str):
    conn = sqlite3.connect(path, isolation_level=None)  # vamos controlar BEGIN/COMMIT
    conn.execute("PRAGMA journal_mode = WAL;")           # melhora concorrência de leitura/escrita
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(CREATE_SCHEMA_SQL)
    return conn

class CodeCache:
    """
    Cache simples que mantém map name -> id para tabelas de códigos.
    Usa get_or_create internamente.
    """
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cache: Dict[str, Dict[str, int]] = {
            "type_codes": {},
            "key_codes": {},
            "action_codes": {},
            "source_codes": {},
            "device_codes": {}
        }

    def _get(self, table: str, name: str) -> int | None:
        cur = self.conn.execute(f"SELECT id FROM {table} WHERE name = ?", (name,))
        row = cur.fetchone()
        return row[0] if row else None

    def _insert(self, table: str, name: str) -> int:
        cur = self.conn.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,))
        return cur.lastrowid

    def get_or_create(self, table: str, name: str) -> int:
        # primeiro tenta no cache
        tcache = self.cache.get(table)
        if tcache is None:
            # suporte dinâmico: cria entrada de cache se necessário
            self.cache[table] = {}
            tcache = self.cache[table]

        if name in tcache:
            return tcache[name]

        # tenta DB
        rowid = self._get(table, name)
        if rowid is None:
            # inserir (pode ter corrida; capturamos IntegrityError)
            try:
                rowid = self._insert(table, name)
            except sqlite3.IntegrityError:
                # outra thread/processo inseriu antes; buscar de novo
                rowid = self._get(table, name)
        tcache[name] = rowid
        return rowid

def insert_events_batch(conn: sqlite3.Connection, cache: CodeCache, events: List[Dict[str, Any]], batch_size=DEFAULT_BATCH):
    """
    events: lista de dicts com chaves esperadas:
      {
        "ts": 1697050000000,         # ms
        "session_id": "abc",
        "type": "keyboard",
        "key": "Key.esc",            # pode ser None
        "action": "press",
        "device": "keyboard",
        "source": "background",
        "x": None, "y": None, "value": None,
        "details": {...}             # opcional, processar depois
      }
    """
    if not events:
        return

    cur = conn.cursor()
    # We'll do manual transaction for speed
    cur.execute("BEGIN")
    try:
        stmt = ("INSERT INTO events "
                "(ts, session_id, type_id, key_id, action_id, device_id, source_id, details_table, details_id, x, y, value) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
        to_insert = []
        for ev in events:
            ts = int(ev.get("ts", int(time.time() * 1000)))
            session_id = ev.get("session_id")
            type_id = cache.get_or_create("type_codes", ev.get("type", "unknown"))
            key_name = ev.get("key")
            key_id = cache.get_or_create("key_codes", key_name) if key_name else None
            action_id = cache.get_or_create("action_codes", ev.get("action", "unknown"))
            device_id = cache.get_or_create("device_codes", ev.get("device", "unknown")) if ev.get("device") else None
            source_id = cache.get_or_create("source_codes", ev.get("source", "background"))
            details_table = ev.get("details_table")
            details_id = ev.get("details_id")
            x = ev.get("x")
            y = ev.get("y")
            value = ev.get("value")
            to_insert.append((ts, session_id, type_id, key_id, action_id, device_id, source_id, details_table, details_id, x, y, value))

        cur.executemany(stmt, to_insert)
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise

# exemplo de uso mínimo
if __name__ == "__main__":
    conn = open_db("events.db")
    cache = CodeCache(conn)
    evs = [
        {"ts": int(time.time()*1000), "type":"keyboard", "key":"Key.esc", "action":"press", "device":"keyboard", "source":"background"},
        {"ts": int(time.time()*1000), "type":"mouse", "action":"move", "x":100, "y":200, "device":"mouse", "source":"background"},
    ]
    insert_events_batch(conn, cache, evs)
    print("inserido", len(evs))
