import atexit
import sqlite3

from pathlib import Path
import sys
from threading import Event, Thread, Lock
import time
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
print(RootDir)
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster

DBDir = RootDir + '/sharedResources/DataBases/DBs'
sys.path.append(RootDir)
print(f'RootDir set to: {RootDir}')

"""
doiufdoiufdoiufdddffggdfgdfgdfgdrfdrf
diugd

"""



from PythonServer.serverConfig import serverConfig
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.generalUtils.aprint import aprint
from sharedResources.pythonLoggerSistem.logger import LoggerManager
from sharedResources.DataBases.utils.BaseSqlDB import BaseDbCommands
from sharedResources.DataBases.mainDatabase.macro_manager import startRecordingNewMacro_external, stopRecordingMacro_external, GetCurrentMacroFunction_external
from sharedResources.DataBases.mainDatabase.cache_manager import _cache_codes_external  , get_or_create_code_external
from sharedResources.DataBases.mainDatabase.event_logger import log_background_event_external
from sharedResources.DataBases.mainDatabase.flush_worker import _flush_external, _flush_worker_external
from sharedResources.debuggingResources.unified_monitor import sys_monitor , monitor_class
from sharedResources.DataBases.mainDatabase.querrys import querrys

@monitor_class
class MainDatabase:
        # from cache_manager
    _cache_codes = _cache_codes_external
    get_or_create_code = get_or_create_code_external

        #from flush_worker
    _flush = _flush_external
    _flush_worker = _flush_worker_external

    #from macro_manager
    GetCurrentMacroFunction = GetCurrentMacroFunction_external
    startNewMacro = startRecordingNewMacro_external
    stopMacro = stopRecordingMacro_external

    # from event_logger
    log_background_event = log_background_event_external
    main_instance = None

    def __init__(self, serverConfig = serverConfig, db_path = DBDir ,batch_size = 100, flush_interval=5):
        
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
        
        # from cache_manager
        # self._cache_codes = _cache_codes.__get__(self)
        # self._load_cache = _load_cache
        # self.get_or_create_code = get_or_create_code.__get__(self)
        
        #from flush_worker
        # self._flush = sys_monitor(_flush.__get__(self), scope = "method",group = "MainDatabase")
        # self._flush_worker = _flush_worker.__get__(self)

        # from macro_manager
        # self.GetCurrentMacroFunction = GetCurrentMacroFunction.__get__(self)
        # self.startNewMacro = startNewMacro.__get__(self)
        # self.stopMacro = stopMacro.__get__(self)
        
        # from event_logger
        # self.log_background_event = log_background_event.__get__(self)

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


    def exec(self,querry, fetchOne = False, ):
        self.cursor.execute(querry)
        return self.cursor.fetchall()
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

        if self.serverConfig.MacroConfig.requestToExecuteMacro:
            self.serverConfig.MacroConfig.currentMacro = self.GetCurrentMacroFunction()
            # print("logo apos a função GetCurrentMacroFunction do mainDatabase o valor de currentMacro é : ",self.serverConfig.MacroConfig.currentMacro)
            if self.serverConfig.MacroConfig.currentMacro is not None:
                self.answer = {"MacroreadyToUse": True}
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
    # querry_traduzida = """SELECT 
    # e.id,
    # e.ts,
    # e.session_id,
    # t.name      AS type_name,
    # k.name      AS key_name,
    # a.name      AS action_name,
    # s.name      AS source_name,
    # d.name      AS device_name,
    # m.name      AS macro_name,
    # e.x,
    # e.y,
    # e.value,
    # e.details_json,
    # e.window_event_id
    # FROM events e
    # LEFT JOIN type_codes   t ON e.type_id   = t.id
    # LEFT JOIN key_codes    k ON e.key_id    = k.id
    # LEFT JOIN action_codes a ON e.action_id = a.id
    # LEFT JOIN source_codes s ON e.source_id = s.id
    # LEFT JOIN device_codes d ON e.device_id = d.id
    # LEFT JOIN macros       m ON e.macro_id  = m.id
    # where macro_id = (?)
    # ORDER BY e.ts ASC;
    # """
    

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
    
    # a=db.exec("select * from events where window_event_id is not null")
    events = db.exec("select * from events")

#     """
#     SERVER] the command to be sent is :  {'action': 'startMacro'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.0, 'equipment': 'mouse', 'button': 'Button.left', 'action': 'press', 'x': 274, 'y': 218, 'details': None, 'window_event': {'app': 'automation-ui-tauri', 'class_name': 'automation-ui-tauri', 'pid': 139627, 'win_id': '0x05600003', 'title': 'automation-ui-tauri', 'details': '{"titles_history": ["automation-ui-tauri"], "first_seen": 1767912658.7493122, "last_seen": 1767912658.7493176, "confidence_score": 1.0, "priority_fields": {}}', 'ts': 1767912658755}}
# [SERVER] the command to be sent is :  {'deltaTime': 0.091, 'equipment': 'mouse', 'button': 'Button.left', 'action': 'release', 'x': 274, 'y': 218, 'details': None}
# [SERVER] the command to be sent is :  {'deltaTime': 1.649, 'equipment': 'keyboard', 'key': 'Key.alt', 'action': 'press', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.106, 'equipment': 'keyboard', 'key': 'Key.tab', 'action': 'press', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.099, 'equipment': 'keyboard', 'key': 'Key.tab', 'action': 'release', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.136, 'equipment': 'keyboard', 'key': 'Key.alt', 'action': 'release', 'modifiers': '{"modifiers": []}', 'window_event': {'app': 'gnome-terminal-server', 'class_name': 'gnome-terminal-server', 'pid': 36904, 'win_id': '0x03e0000a', 'title': 'cain@cain-Aspire-F5-573: ~/Documentos/automacaoPythonJs', 'details': '{"titles_history": ["cain@cain-Aspire-F5-573: ~/Documentos/automacaoPythonJs"], "first_seen": 1767912660.808087, "last_seen": 1767912660.808092, "confidence_score": 1.0, "priority_fields": {}}', 'ts': 1767912660836}}
# [SERVER] the command to be sent is :  {'deltaTime': 0.429, 'equipment': 'keyboard', 'key': 'Key.alt', 'action': 'press', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.059, 'equipment': 'keyboard', 'key': 'Key.tab', 'action': 'press', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'deltaTime': 0.163, 'equipment': 'keyboard', 'key': 'Key.tab', 'action': 'release', 'modifiers': '{"modifiers": []}', 'window_event': {'app': 'automation-ui-tauri', 'class_name': 'automation-ui-tauri', 'pid': 139627, 'win_id': '0x05600003', 'title': 'automation-ui-tauri', 'details': '{"titles_history": ["automation-ui-tauri"], "first_seen": 1767912661.4821124, "last_seen": 1767912661.4821193, "confidence_score": 1.0, "priority_fields": {}}', 'ts': 1767912661487}}
# [SERVER] the command to be sent is :  {'deltaTime': 0.104, 'equipment': 'keyboard', 'key': 'Key.alt', 'action': 'release', 'modifiers': '{"modifiers": []}'}
# [SERVER] the command to be sent is :  {'action': 'endMacro'}

#     """
        
