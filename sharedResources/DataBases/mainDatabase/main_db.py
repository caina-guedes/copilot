import atexit
import sqlite3

from pathlib import Path
import sys
from threading import Event, Thread, Lock
import time
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
print(RootDir)

DBDir = RootDir + '/sharedResources/DataBases/DBs'
sys.path.append(RootDir)
print(f'RootDir set to: {RootDir}')

"""
doiufdoiufdoiufdddffggdfgdfgdfgdrfdrf
diugd

"""



from PythonServer.serverConfig import serverConfig
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import sys_monitor , monitor_class
from sharedResources.generalUtils.aprint import aprint
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.DataBases.utils.BaseSqlDB import BaseDbCommands
from sharedResources.DataBases.mainDatabase.macro_manager import startRecordingNewMacroOnDb_external, stopRecordingMacroOnDB_external, GetCurrentMacroOnDb_external
from sharedResources.DataBases.mainDatabase.cache_manager import _cache_codes_external  , get_or_create_code_external
from sharedResources.DataBases.mainDatabase.event_logger import log_background_event_external
from sharedResources.DataBases.mainDatabase.flush_worker import _flush_external, _flush_worker_external
from sharedResources.DataBases.mainDatabase.querrys import querrys

# @monitor_class
class MainDatabase:
        # from cache_manager
    _cache_codes = _cache_codes_external
    get_or_create_code = get_or_create_code_external

        #from flush_worker
    _flush = _flush_external
    _flush_worker = _flush_worker_external

    #from macro_manager
    GetCurrentMacroFunction = GetCurrentMacroOnDb_external
    startNewMacro = startRecordingNewMacroOnDb_external
    stopMacro = stopRecordingMacroOnDB_external

    # from event_logger
    log_background_event = log_background_event_external
    main_instance = None

    def clean_answer(self):
        self.answer = None

    def __init__(self, serverConfig = serverConfig, db_path = DBDir ,batch_size = 100, flush_interval=5):
        self.recordingMacroId_is_none_while_recording_counter = 0
        self.recordingMacroId_is_not_None_while_Not_recording_counter = 0
        self.db_path = db_path + '/main.db'
        self.serverConfig = serverConfig
        self.MacroStarted = False
        self.MacroStopped = False
        self.recordingMacroId = None
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.conn = sqlite3.connect(
            self.db_path , 
            check_same_thread = False ,
            isolation_level = None ,  # autocommit mode
            timeout = 10 )
        self.cursor = self.conn.cursor()
        self._configure_connection()
        self._initialize_main_bank()
        self._cache_codes()
        # Buffer de eventos
        self._buffer_lock = Lock()
        with self._buffer_lock:
            self._pending_events = []
            self._last_flush = time.time()
        self._stop_event = Event()

        # Thread de flush periódico
        self._flush_thread = Thread(target=self._flush_worker, daemon=True)
        self._flush_thread.start()
        self.answer = None
        if MainDatabase.main_instance is not None:
            print("[MainDatabase.__init__] Aviso: Tentativa de criar uma nova instância de MainDatabase, mas uma instância já existe. ")
        MainDatabase.main_instance = self
        

    def _initialize_main_bank(self):
        for command in BaseDbCommands:
            # print(command)
            try:
                self.cursor.execute(command)
            except Exception as e:
                log_error_forensics_plus(e)
                # LoggerManager.log_exception_with_context(f'Exception during creation of main DB occurred, {e}',e)
        self.conn.commit()

    def _configure_connection(self):
        for configCommand in querrys["_configure_connection"]:
            try:
                self.cursor.execute(configCommand)
            except Exception as e:
                print("[MainDatabase._configure_connection] deu erro configurando conexão do main db e foi: ", str(e))


    def exec(self,querry, fetchOne = False,argsTuple=None ):
        try:
            if argsTuple is None:
                self.cursor.execute(querry)
            else:
                self.cursor.execute(querry,argsTuple)
            return self.cursor.fetchall()
        except Exception as e:
            print("the error querry is: ",querry)
            print('the argsTuple is: ' ,argsTuple )
            raise 
    
    ### Event Buffering and Insertion ###
    def add_event(self, event_dict,isSpecialCommand = False):
        """
        event_dict deve conter:
        {
            'ts': timestamp,
            'type': 'keyboard'/'mouse'/etc,
            'key': 'F8'/None,
            'action': 'press'/'release'/etc,
            'device': 'keyboard'/'mouse'/etc,
            'source': 'background'/'macro'/etc,
            'details': JSON string ou None
        }
        """
        if self.serverConfig.MacroConfig.isRecording:
            if self.recordingMacroId is None :

                self.startNewMacro()
            event_dict['macro_id'] = self.recordingMacroId
            # print("the key beeing recorded is: ",event_dict['key'])
            if str(event_dict['key']) == str(self.serverConfig.MacroConfig.stoppingKey) :
                event_dict['macro_id'] = None
        else:
            if self.recordingMacroId is not None:
                self.stopMacro()
            self.recordingMacroId = None

        # if self.serverConfig.MacroConfig.requestToExecuteMacro:
        #     self.serverConfig.MacroConfig.currentMacro = self.GetCurrentMacroFunction()
            
        #     if self.serverConfig.MacroConfig.currentMacro is not None:
        #         self.answer = {"MacroreadyToUse": True}
        ### tenho que adicionar uma flag pra saber que a macro ja terminou de ser executada pra fazer as devidas mudanças
        timeToFlush = False
        
        if isSpecialCommand: # this makes special commands don't be saved in the main db when this command triggered the execution.
            return 
        
        with self._buffer_lock:
            self._pending_events.append(event_dict)
            if len(self._pending_events) >= self.batch_size:
                timeToFlush = True
        if timeToFlush:
            self._flush()    
    
    @classmethod
    def close(cls):
        self = cls.main_instance
        if self:
            print("[MainDatabase.close] Fechando o banco de dados principal...")
            if not self._stop_event.is_set():
                # print("[MainDatabase.close] Sinalizando a thread de flush para parar...")
                self._stop_event.set()
                # print("[MainDatabase.close] Aguardando a thread de flush terminar...")
                self._flush_thread.join(timeout=self.flush_interval + 0.5)
                # print("[MainDatabase.close] Thread de flush finalizada. Realizando o flush final...")
                self._flush()
                print("[MainDatabase.close] Flush finalizado.")
            else:
                pass
                # print("[MainDatabase.close] Aviso: O evento de parada já estava sinalizado. Isso pode indicar que o processo de fechamento já foi iniciado anteriormente.")
            
            if self.conn:
                try:
                    self.conn.commit()
                    self.conn.close()   
                    print("[MainDatabase.close] Conexão com o banco de dados fechada com sucesso.")
                except Exception as e:
                    pass
                    # print("[MainDatabase.close] Aviso: A conexão com o banco de dados já estava fechada.")
                    # print(f"[MainDatabase.close] Detalhes do erro ao fechar a conexão: {str(e)}")
        else:
            print("[MainDatabase.close] Aviso: Tentativa de fechar o banco de dados, mas a instância é None. " \
            "Isso pode indicar que o banco de dados já foi fechado ou " \
            "não foi inicializado corretamente."   )

LifecycleMaster.register_cleanup_function(MainDatabase.close, 
                                          name = "MainDatabase.close" , 
                                          priority = 10,
                                          register_in_atexit = True,
                                        #   args=(MainDatabase.main_instance)
                                          ) 

# prioridade 10 para garantir que seja chamado depois de outras funções de limpeza 
# que possam depender do main database ainda estar aberto
if __name__ == "__main__":
    db = MainDatabase(batch_size=10, flush_interval=3)

    def limpaMacros(todas = False):
        a= db.exec("select * from macros")
        if todas:
            db.exec(f"delete from macros")
        else:
            db.exec(f"delete from macros where id != {a[-1][0]}")

    def winChange():
        return db.exec(f"""select * from window_events""")
    
    limpaMacros()
    
    print("valores da tabela macros:")
    db.cursor.execute("select * from macros")
    a=db.cursor.fetchall()
    # import sqlite3

    def quant_registros_tabelas():

        # pegar todas as tabelas
        tables= db.exec("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        """)


        print(f"{'Tabela':30} | Registros")
        print("-"*45)

        for (table,) in tables:
            count = db.exec(f"SELECT COUNT(*) FROM {table}")
            print(f"{table:30} | {count}")

    def tamanho_KBs_tabelas():
        result=db.exec("""SELECT
        name,
        SUM(pgsize)/1024 as size_kb
        FROM dbstat
        GROUP BY name
        ORDER BY size_kb DESC;""")

        for x in result:
            print(x)

    b=db.exec(querrys["selectEventosComMudançaDeJanela"])
    c = winChange()
    winChangeIdsInCurrentMacro = []
    for x in a:
        print(x)
        identifier=x[0]
        db.cursor.execute(querrys["querry_traduzida"],(identifier,))
        for comando in db.cursor.fetchall():
            if comando[-1] is not None:
                winChangeIdsInCurrentMacro.append(comando[-1])
            print(comando)
    #for ev in b:
    #           print(ev)
    quant_registros_tabelas()
    tamanho_KBs_tabelas()
    # a=db.exec("select * from events where window_event_id is not null")
    # events = db.exec("select * from events")
    # import sqlite3

    # conn = sqlite3.connect("database.db")
    # cur = conn.cursor()

    # # 1️⃣ Adiciona a coluna occurrences se ainda não existir
    # try:
    #     cur.execute("ALTER TABLE window_events ADD COLUMN occurrences INTEGER DEFAULT 1")
    # except sqlite3.OperationalError:
    #     pass  # já existe

    # 2️⃣ Agrupar duplicados e somar ocorrências
    duplicates = db.exec("""
SELECT app, class_name, pid, win_id, title,
       MIN(id) as first_id, COUNT(*) as cnt
FROM window_events
GROUP BY app, class_name, pid, win_id, title 
HAVING cnt > 1
""")


    print(f"Encontrados {len(duplicates)} grupos duplicados.")

    # 3️⃣ Para cada grupo duplicado:
    total_duplicate_registers = 0
    for row in duplicates:
        app, class_name, pid, win_id, title, min_id, cnt = row

        # soma as ocorrências existentes (aqui cada duplicado vale 1)
        total_occurrences = cnt
        total_duplicate_registers += total_occurrences - 1
        # print(total_occurrences)
        continue ### só pra ver as ocorrencias agora mesmo !
        # deleta os registros antigos do grupo
        db.cursor.execute("""
            DELETE FROM window_events
            WHERE timestamp=? AND app=? AND class_name=? AND pid=? AND win_id=? AND title=? AND details=? 
                    AND id != ?
        """, (app, class_name, pid, win_id, title, details,min_id))

        db.cursor.execute("""
        UPDATE window_events
        SET occurrences = ?
        WHERE id = ?
    """, (total_occurrences, min_id))
        # # insere 1 registro com occurrences = total_occurrences
        # cur.execute("""
        #     INSERT INTO window_events (timestamp, app, class_name, pid, win_id, title, details, occurrences)
        #     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        # """, (timestamp, app, class_name, pid, win_id, title, details, total_occurrences))

        db.conn.commit()
        # db.conn.close()
    print("o total de registros duplicados é: ",total_duplicate_registers)
    print("Tabela limpa e pronta para criar UNIQUE index.")
    quant_registros_tabelas()
    tamanho_KBs_tabelas()
    


    # 1️⃣ Pega todos os grupos de eventos únicos
    groups = db.exec("""
    SELECT app, class_name, pid, win_id, title, MIN(id) as kept_id
    FROM window_events
    GROUP BY app, class_name, pid, win_id, title
    """)

    for group in groups:
        app, class_name, pid, win_id, title, kept_id = group

        # 2️⃣ Pega todos os ids antigos que correspondem a esse evento
        
        old_ids = [row[0] for row in db.exec("""
        SELECT id FROM window_events
        WHERE app=? AND class_name=? AND pid=? AND win_id=? AND title=? AND id != ?
        """, argsTuple = (app, class_name, pid, win_id, title, kept_id))]

        if old_ids:
            # 3️⃣ Atualiza a tabela events para apontar para o kept_id
            db.exec(f"""
            UPDATE events 
            SET window_event_id = ?
            WHERE window_event_id IN ({','.join('?'*len(old_ids))})
            """, argsTuple = [kept_id] + old_ids)
    
    