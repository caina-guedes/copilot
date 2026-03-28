from sharedResources.debuggingResources.unified_monitor import monitor_class, sys_monitor
from sharedResources.DataBases.mainDatabase.querrys import querrys, put_table_in_querry


"""
_cache_codes, _load_cache, get_or_create_code functions for managing cache codes in the main database.
"""

# @sys_monitor
def _cache_codes_external(self):
    self.key_cache = _load_cache(self , 'key_codes')
    self.type_cache = _load_cache(self , 'type_codes')
    self.action_cache = _load_cache(self , 'action_codes')
    self.source_cache = _load_cache(self , 'source_codes')
    self.device_cache = _load_cache(self , 'device_codes')

# @sys_monitor
def _load_cache(self, table):
    cache = {}
    result = self.exec(put_table_in_querry(querrys["IdNameFromTable"],table))
    for id_, name in result:
        cache[name] = id_
    return cache

# @sys_monitor
def get_or_create_code_external(self, table, cache, name):
    # print(f"the table is:{table}")
    # print(f"the original querry before putting the table name is:{querrys["insertOuIgnoreName"]}")
    if name in cache:
        return cache[name]
    if not name:
        raise ValueError(f"Tentativa de inserir código vazio na tabela {table}")
    correct_querry = put_table_in_querry(querrys["insertOuIgnoreName"] , table)
    # print(f"the correct querry is: {correct_querry}")
    # print(f"the name is: {name}") 
    # return 0 ####
    # print("init")
    try:
        # self.cursor.execute(correct_querry , (name,))
        # self.conn.commit()
        self.exec(correct_querry,(name,),fetch = None,commit = True)
    except Exception as e:
        print(f"erro na primeira querry e foi: {str(e)}")
        raise
    try:
        # self.cursor.execute(put_table_in_querry(querrys["selectIdDaTabelaPeloNome"] , table) , (name,))
        # row = self.cursor.fetchone()
        row = self.exec(put_table_in_querry(querrys["selectIdDaTabelaPeloNome"] , table), (name,), fetch = 'one')
    except Exception as e:
        print(f"erro na segunda querry e foi: {str(e)}" )
        raise 
    if row is None:
        raise ValueError(f"Falha ao inserir ou recuperar código '{name}' na tabela {table}")
    # new_id = self.cursor.lastrowid
    new_id = row[0]
    cache[name] = new_id
    # print("id que será retornado é: ",new_id)
    return new_id
