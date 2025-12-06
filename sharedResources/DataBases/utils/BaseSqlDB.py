BaseDbCommands = [
    """CREATE TABLE IF NOT EXISTS macros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NULL,
    hotkey TEXT UNIQUE
);
""",
    
            """-- Tabelas de códigos (compactação de strings repetidas)
CREATE TABLE IF NOT EXISTS type_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL  -- 'keyboard','mouse','browser'
);"""
            ,
            """

CREATE TABLE IF NOT EXISTS key_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL  -- 'Key.esc','f8','a','Enter'
);"""
            ,
            """
CREATE TABLE IF NOT EXISTS action_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL  -- 'press','release','move','click','scroll'
);"""
            ,
            """

CREATE TABLE IF NOT EXISTS source_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL  -- 'background','macro','extension'
);"""
            ,
            """

CREATE TABLE IF NOT EXISTS device_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL  -- opcional: 'touchpad','mouse','keyboard','browser-ext'
);"""
            ,
"""CREATE TABLE IF NOT EXISTS window_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    app TEXT NULL,
    class_name TEXT NULL ,
    pid INTEGER NULL ,
    win_id INTEGER NULL ,
    title TEXT NULL,
    details TEXT NULL
);"""       
,

            """

-- Tabela unificada de eventos (leve)
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,          -- unix epoch (ms ou s) — escolha ms se precisar de subsegundos
    session_id TEXT,              -- opcional: identificar execução/instância do programa
    type_id INTEGER NOT NULL,     -- ref type_codes
    key_id INTEGER,               -- ref key_codes (nullable)
    macro_id INTEGER,             -- ref macros.id (nullable)
    action_id INTEGER NOT NULL,   -- ref action_codes
    device_id INTEGER,            -- ref device_codes
    source_id INTEGER NOT NULL,   -- ref source_codes (background/macros/ext)
    details_id INTEGER,           -- FK opcional para tabela de detalhes (ver abaixo)
    details_table TEXT,           -- nome da tabela de detalhes ('mouse_details', 'keyboard_details', 'browser_events') ou NULL
    -- campos gerais (economizar espaço evitando TEXT longos)
    x INTEGER,                    -- pos X (nullable)
    y INTEGER,                    -- pos Y (nullable)
    value REAL,                   -- valor genérico (ex: wheel delta) ou NULL
    details_json TEXT,        -- JSON string com detalhes extras (opcional, pode ser NULL)
    window_event_id INTEGER DEFAULT -1,

    FOREIGN KEY(window_event_id) REFERENCES window_events(id) ON DELETE SET DEFAULT,
    FOREIGN KEY (type_id) REFERENCES type_codes(id),
    FOREIGN KEY (key_id) REFERENCES key_codes(id),
    FOREIGN KEY (action_id) REFERENCES action_codes(id),
    FOREIGN KEY (source_id) REFERENCES source_codes(id),
    FOREIGN KEY (device_id) REFERENCES device_codes(id),
    FOREIGN KEY (macro_id) REFERENCES macros(id) ON DELETE SET NULL

);"""
                ,
                """CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);"""
                ,
                """
                CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events (type_id, ts);
                """
                ,
                """
                CREATE INDEX IF NOT EXISTS idx_events_session_ts ON events (session_id, ts);
                """
                ,
                """
-- Tabelas de detalhes (só quando necessário)
CREATE TABLE IF NOT EXISTS mouse_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER UNIQUE,       -- opcional redundância; ou mantenha details_id na events
    button TEXT,                   -- 'left','right','middle'
    clicks INTEGER,
    wheel_delta INTEGER,
    movement_dx INTEGER,
    movement_dy INTEGER,
    FOREIGN KEY (event_id) REFERENCES events(id)
);"""
                    ,
                    """

CREATE TABLE IF NOT EXISTS keyboard_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER UNIQUE,
    raw_key TEXT,                  -- por segurança, string bruta se precisar
    modifiers INTEGER,             -- bitmap p/ shift/ctrl/alt
    FOREIGN KEY (event_id) REFERENCES events(id)
);"""
                ,
                """

CREATE TABLE IF NOT EXISTS browser_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER UNIQUE,
    url TEXT,
    title TEXT,
    js_payload TEXT,               -- JSON string com dados do extension emit
    FOREIGN KEY (event_id) REFERENCES events(id)
);
"""
        ]