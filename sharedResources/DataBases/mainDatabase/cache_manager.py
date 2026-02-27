from sharedResources.debuggingResources.unified_monitor import monitor_class, sys_monitor
from sharedResources.DataBases.mainDatabase.querrys import querrys, put_table_in_querry


"""
_cache_codes, _load_cache, get_or_create_code functions for managing cache codes in the main database.
"""

@sys_monitor
def _cache_codes(self):
    self.key_cache = _load_cache(self , 'key_codes')
    self.type_cache = _load_cache(self , 'type_codes')
    self.action_cache = _load_cache(self , 'action_codes')
    self.source_cache = _load_cache(self , 'source_codes')
    self.device_cache = _load_cache(self , 'device_codes')

@sys_monitor
def _load_cache(self, table):
    cache = {}
    self.cursor.execute(put_table_in_querry(querrys["IdNameFromTable"],table))
    for id_, name in self.cursor.fetchall():
        cache[name] = id_
    return cache

@sys_monitor
def get_or_create_code(self, table, cache, name):
    if name in cache:
        return cache[name]
    if not name:
        raise ValueError(f"Tentativa de inserir código vazio na tabela {table}")

    self.cursor.execute(put_table_in_querry(querrys["insertOuIgnoreName"] , table) , name)
    self.conn.commit()

    self.cursor.execute(put_table_in_querry(querrys["selectIdDaTabelaPeloNome"] , table) , name)
    row = self.cursor.fetchone()
    if row is None:
        raise ValueError(f"Falha ao inserir ou recuperar código '{name}' na tabela {table}")
    # new_id = self.cursor.lastrowid
    new_id = row[0]
    cache[name] = new_id
    return new_id
