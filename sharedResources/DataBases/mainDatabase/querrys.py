# from sharedResources.DataBases.mainDatabase.querrys import querrys 

table_repr = "__table__"
def put_table_in_querry(querry, table):
    new_querry = querry.replace(table_repr, table)
    # print(new_querry) 
    return new_querry

querrys = {
    "selectMacroAtiva": "select id from macros where end_time is null",
    "registroInicialMacro": "INSERT INTO macros (name, start_time) VALUES (?, ?)",
    "registroFimDeMacro" : "UPDATE macros SET end_time = ? WHERE end_time IS NULL",
    "selectUltimoIdDeMacro" : "select id from macros order by ID desc limit 1",
    "get_all_macros" : """SELECT * FROM macros ORDER BY id DESC;""",
    "selectEventosComMudançaDeJanela" : "select * from events where window_event_id is not null",
    "IdNameFromTable" : f"SELECT id, name FROM {table_repr} ", # só pra pegar id, name de tabelas específicas
    "insertOuIgnoreName" : f"INSERT OR IGNORE INTO {table_repr} (name) VALUES (?)",
    "selectIdDaTabelaPeloNome" : f"SELECT id FROM {table_repr} WHERE name = ?",

    "dinamic_insert_querrys" : set(),
    "_configure_connection" : [ #commands beeins used only in the _configure_connection function
                 "PRAGMA foreign_keys = ON;",
         "PRAGMA journal_mode = WAL;",
         "PRAGMA synchronous = NORMAL;",
         "PRAGMA cache_size = -10000;",  # ~10MB
         "PRAGMA temp_store = MEMORY;",
         "PRAGMA busy_timeout = 10000;",  # evita 'database is locked'
         "PRAGMA mmap_size = 268435456;",  # ativa mmap até 256MB, melhora leitura
    ],
    "insertEvent": '''
                INSERT INTO events (ts, type_id, key_id,macro_id, action_id, device_id, source_id, details_id, details_table, x, y, value, details_json,window_event_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
            ''',

    "querry_traduzida" : """SELECT 
    e.id,
    e.ts,
    e.session_id,
    t.name      AS type_name,
    k.name      AS key_name,
    a.name      AS action_name,
    s.name      AS source_name,
    d.name      AS device_name,
    m.name      AS macro_name,
    e.x,
    e.y,
    e.value,
    e.details_json,
    e.window_event_id
    FROM events e
    LEFT JOIN type_codes   t ON e.type_id   = t.id
    LEFT JOIN key_codes    k ON e.key_id    = k.id
    LEFT JOIN action_codes a ON e.action_id = a.id
    LEFT JOIN source_codes s ON e.source_id = s.id
    LEFT JOIN device_codes d ON e.device_id = d.id
    LEFT JOIN macros       m ON e.macro_id  = m.id
    where macro_id = (?)
    ORDER BY e.ts ASC;
    """,


    "translated_events_per_macro_id" : """SELECT 
    e.id,
    e.ts,
    e.session_id,
    t.name      AS type_name,
    k.name      AS key_name,
    a.name      AS action_name,
    s.name      AS source_name,
    d.name      AS device_name,
    m.name      AS macro_name,
    e.x,
    e.y,
    e.value,
    e.details_json,
    
    CASE 
    WHEN we.id IS NULL THEN '{}'
    ELSE json_object(
        'app',         we.app,
        'class_name',  we.class_name,
        'pid',         we.pid,
        'win_id',      we.win_id,
        'title',       we.title,
        'details',     we.details,
        'ts',          we.timestamp
    )
END AS window_event


FROM events e
LEFT JOIN type_codes   t ON e.type_id   = t.id
LEFT JOIN key_codes    k ON e.key_id    = k.id
LEFT JOIN action_codes a ON e.action_id = a.id
LEFT JOIN source_codes s ON e.source_id = s.id
LEFT JOIN device_codes d ON e.device_id = d.id
LEFT JOIN macros       m ON e.macro_id  = m.id
LEFT JOIN window_events we ON e.window_event_id = we.id

where macro_id = (?)
ORDER BY e.ts ASC;
""", 
    

}