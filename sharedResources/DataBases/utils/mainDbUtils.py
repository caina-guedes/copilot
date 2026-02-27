# class preparedQuerryes:
#     translated_events_per_macro_id = """SELECT 
#     e.id,
#     e.ts,
#     e.session_id,
#     t.name      AS type_name,
#     k.name      AS key_name,
#     a.name      AS action_name,
#     s.name      AS source_name,
#     d.name      AS device_name,
#     m.name      AS macro_name,
#     e.x,
#     e.y,
#     e.value,
#     e.details_json,
    
#     CASE 
#     WHEN we.id IS NULL THEN '{}'
#     ELSE json_object(
#         'app',         we.app,
#         'class_name',  we.class_name,
#         'pid',         we.pid,
#         'win_id',      we.win_id,
#         'title',       we.title,
#         'details',     we.details,
#         'ts',          we.timestamp
#     )
# END AS window_event


# FROM events e
# LEFT JOIN type_codes   t ON e.type_id   = t.id
# LEFT JOIN key_codes    k ON e.key_id    = k.id
# LEFT JOIN action_codes a ON e.action_id = a.id
# LEFT JOIN source_codes s ON e.source_id = s.id
# LEFT JOIN device_codes d ON e.device_id = d.id
# LEFT JOIN macros       m ON e.macro_id  = m.id
# LEFT JOIN window_events we ON e.window_event_id = we.id

# where macro_id = (?)
# ORDER BY e.ts ASC;
# """
#     get_all_macros = """SELECT * FROM macros ORDER BY id DESC;"""
    