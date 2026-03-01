from pathlib import Path
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.generalUtils.aprint import aprint
from sharedResources.DataBases.mainDatabase.querrys import querrys
import json
import copy
"""
Responsável por: _flush_worker, _flush

Função: Gerenciar o buffer de eventos e inserir em lote no banco.
"""


import sqlite3
import time
# from .cache_manager import get_or_create_code_external
import json
from PythonServer.serverConfig import serverConfig
FlushConfig = serverConfig.FlushConfig

def _build_insert_query(table, data: dict):
    querrys_ja_existentes = querrys["dinamic_insert_querrys"]
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))

    sql = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
    if sql not in querrys_ja_existentes:
        querrys_ja_existentes.add(sql)
    return sql, tuple(data.values())

def is_duplicate_click(ev,debug = True):
    if debug:
        pass
        # print("checking for duplicate click...")
        # print("the event to check is: ", ev)
    if ev.get("type") != "mouse":
        if debug:
            pass
            # print("not a mouse event, returning False")
        return False
    if len(FlushConfig.commandsToNotFlush) == 0:
        if debug:
            pass
            # print("no commands to not flush, returning False")
        return False

    comparingRecords = []
    try:
        for front_end_ev_class in FlushConfig.commandsToNotFlush:
            front_end_ev = front_end_ev_class.values
            if debug:
                pass
                # print("comparing with front end event: ", front_end_ev)
            # Comparar botões
            if ev.get("key").replace("Button.","") != front_end_ev.get("button", None):
                if debug:
                    pass
                    # print("button mismatch")
                comparingRecords.append(False)
                continue

            # Comparar timestamp
            time_diff = abs(ev["ts"] - front_end_ev["ts"])

            if ev["action"] == "press":
                if time_diff > FlushConfig.MAX_TIME_DIFF:
                    comparingRecords.append(False)
                    if debug:
                        pass
                        # print("timestamp mismatch")
                    continue
                # Comparar coordenadas
                dx = abs(ev.get("x", 0) - front_end_ev.get("x", 0))
                dy = abs(ev.get("y", 0) - front_end_ev.get("y", 0))
                if dx > FlushConfig.MAX_PIXEL_DIFF or dy > FlushConfig.MAX_PIXEL_DIFF:
                    comparingRecords.append(False)
                    if debug:
                        pass
                        # print("press coordinate mismatch ")
                    continue
            elif ev["action"] == "release":
                if ev["ts"] - front_end_ev["ts"] <= 0:
                    comparingRecords.append(False)
                    if debug:
                        pass
                        # print("release timestamp mismatch ")
                    continue
            
            # Se todas as comparações passaram, é um clique duplicado
            if debug:
                pass
                # print("duplicate click detected")
            comparingRecords.append(True)
        for index, front_end_ev_class in enumerate(FlushConfig.commandsToNotFlush):
            if comparingRecords[index]:
                # print("removendo o evento duplicado da lista de comandos a não flushar: ", front_end_ev_class.values)
                if ev["action"] == "press":
                    FlushConfig.commandsToNotFlush[index].pressDetected = True
                if ev["action"] == "release":
                    FlushConfig.commandsToNotFlush[index].releaseDetected = True
                if FlushConfig.commandsToNotFlush[index].pressDetected and FlushConfig.commandsToNotFlush[index].releaseDetected:
                    FlushConfig.commandsToNotFlush.pop(index)
                break

        return any(comparingRecords)
    except Exception as e:
        print("erro ao verificar clique duplicado: ", e)
        return False    


def _flush_windowChange(self,windowEvent,ts):
    # print(f"  a variável que chegou é: {windowEvent}")

    internalWindowEvent = copy.deepcopy(windowEvent)
    internalWindowEvent["timestamp"] = ts
    
    namesToDelete = ["os_name","titles_history","confidence_score","last_seen","first_seen","id"]
    for name in namesToDelete:
        internalWindowEvent.pop(name,None)

    if isinstance(internalWindowEvent['details'], (dict, list)):
        internalWindowEvent['details'] = json.dumps(internalWindowEvent['details'])
    else:
        internalWindowEvent['details'] = str(internalWindowEvent['details'])

    preparedQuerry , values = _build_insert_query("window_events",internalWindowEvent)
    try:
        self.cursor.execute(preparedQuerry, values)
        windowgeratedId = self.cursor.lastrowid
        # print("o id gerado pra mudança de janela foi:",windowgeratedId )
        return windowgeratedId
    except Exception as e:
        print("deu merda no flush_windowChange e é: ",e)
        print("os valores são: ", values)
        print(" a preparedQuerry é: ", preparedQuerry)
        return None


def _prepareEventToFlush(self, ev):
    ts = ev.get('ts')
    type_id = self.get_or_create_code( 'type_codes', self.type_cache, ev.get('type'))
    key_id = None
    if ev.get('key'):
        key_id = self.get_or_create_code(  'key_codes', self.key_cache, ev.get('key'))
    if ev.get('button'):
        key_id = self.get_or_create_code(  'key_codes', self.key_cache, ev.get('button'))
    action_id = self.get_or_create_code( 'action_codes', self.action_cache, ev.get('action'))
    device_id = self.get_or_create_code( 'device_codes', self.device_cache, ev.get('device'))
    source_id = self.get_or_create_code( 'source_codes', self.source_cache, ev.get('source'))
    details_json = ev.get('details', None)
    # Campos extras
    x = ev.get('x')
    y = ev.get('y')
    value = ev.get('value')
    # details_table = None # need to implement this in the future
    macro_id = ev.get("macro_id")

    if ev.get('type') == 'mouse':
        details_table = 'mouse_details'
    elif ev.get('type') == 'keyboard':
        details_table = 'keyboard_details'
    elif ev.get('type') == 'browser':
        details_table = 'browser_events'
    
    # print('the ev is: ',ev)
    # print('the type of ev is : ', type(ev))
    # ev['details'] = json.loads(ev['details'])
    # print("the ev['details'] é: ", ev['details'])
    # print('the type of ev["details"] é: ', type(ev['details']))
    windowChangeId = None
    if "newCurrentWindow" in ev:
        try:
            windowChangeId = _flush_windowChange(self, ev["newCurrentWindow"], ts)
        except Exception as e:
            print("deu merda no flushworker mexendo com o windowChange e é: ",e)
            print("e o ev é: ",ev)
    prepared_event_to_flush = (ts, type_id, key_id,macro_id, action_id, device_id, source_id, None, details_table, x,y,value,details_json, windowChangeId)
    # print("o evento depois de ser preparado para o flush é: ",prepared_event_to_flush) 
    # print("time since event ts: ", (int(str(time.time()*1000).split(".")[0]) - ts)/1000)
    return prepared_event_to_flush


def _flush_external(self, final_flush=False):
    """Executa inserção em bloco de todos os eventos pendentes"""
    if len(self._pending_events) == 0: ## Nada para gravar porém esse atributo debug eu ainda tenho que olhar melhor futuramente
        # print("No pending events to flush.")
        return
    
    with self._buffer_lock:
        events_to_insert = []
        toRecentEvents = []
        # print(f"começando o flush de eventos. o número de eventos pendentes é: {len(self._pending_events)}")
        self._pending_events.sort(key=lambda e: e.get("ts"))
        # print("eventos ordenados por timestamp.")
        timeNow = int(str(time.time()*1000).split(".")[0])
        
        def timePassed(ts,timeNow = timeNow):
            return (timeNow - ts)/1000

        def isTimeToFlush(ts,timeNow = timeNow):
            diference = timePassed(ts,timeNow)
            return diference > self.serverConfig.FlushConfig.minimumTimeForEventToBeFlushed        
        
        duplicate_events_indexes = []
        force = FlushConfig.force_flush.is_set()
        for index , ev in enumerate(self._pending_events):
            # print("processando o evento: ", ev)
            ts = ev.get('ts')
            diference = (timeNow - ts)/1000
            # print(f"the time passed is: {diference} seconds and the minimum time for flush is: ", self.serverConfig.FlushConfig.minimumTimeForEventToBeFlushed)

            if isTimeToFlush(ts) or final_flush or force:
                # print("o evento passou no teste de tempo para flush.")
                prepared_event_to_flush = _prepareEventToFlush(self,ev)
                if is_duplicate_click(ev):
                    duplicate_events_indexes.append(index)
                    # print("evento duplicado detectado, ignorando: ", ev)
                    # print("a lista de comandos a não flushar agora é: ", serverConfig.FlushConfig.commandsToNotFlush)
                    continue
                else:
                    pass
                    # print("evento não é duplicado, processando: ", ev)
                    # print("a lista de comandos a não flushar agora é: ", serverConfig.FlushConfig.commandsToNotFlush)

                events_to_insert.append(prepared_event_to_flush)
            else:
                # print("o evento não passou no teste de tempo para flush, voltando pro buffer.")
                toRecentEvents.append(ev)
        # self._pending_events.clear()
        duplicate_events_indexes.reverse()
        for x in duplicate_events_indexes:
            # print("removendo o evento duplicado do buffer de eventos pendentes: ", self._pending_events[x])
            self._pending_events.pop(x)

    max_retries = 5
    retry_delay = 0.1
    sucess = False
    if len(events_to_insert) == 0:
        # print("nenhum evento passou no teste de tempo para flush, saindo da função.")
        return
    # print(f"tentando inserir {len(events_to_insert)} eventos no banco de dados.")
    for attempt in range(max_retries):
        try:
            print(f"about to flush the events that happend between {timePassed(events_to_insert[0][0])} and {timePassed(events_to_insert[-1][0])}!!!!!")
            self.cursor.executemany('''
                INSERT INTO events (ts, type_id, key_id,macro_id, action_id, device_id, source_id, details_id, details_table, x, y, value, details_json,window_event_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,?)
            ''', events_to_insert)
            self.conn.commit()
            # print("flush de eventos realizado com sucesso.")
            sucess = True
            self._last_flush = time.time()
            print(f"consegui fazer o flush!!!! haviam {len(events_to_insert)} eventos para inserir.")
            break  # Sucesso, sai do loop
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                wait = retry_delay * (2 ** attempt)
                print(f"[WARN] Banco bloqueado, tentativa {attempt + 1}/{max_retries}. Aguardando {wait:.2f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"[ERROR] Erro SQLite inesperado: {e}")
                break
        except sqlite3.IntegrityError as e:
            print("Evento problemático:", events_to_insert)
            raise e
        except Exception as e:
            print(f"[ERROR] Falha ao gravar eventos: {e}")
            break
    # print("saindo do loop de tentativas de flush. e tentando entrar no lock do buffer pra verificar o sucesso")
    with self._buffer_lock:
        # print("verificando sucesso do flush")
        if not sucess:
            print("não deu sucesso no flush de eventos, voltando as coisas pro lugar....")
            # pass
            # print("não deu sucesso no flush de eventos, voltando as coisas pro lugar....")
            # self._pending_events[:0] = events_to_insert
        else:
            print("flush bem sucedido, atualizando eventos pendentes.")
            self._pending_events.clear()
            self._pending_events.extend(toRecentEvents)

def _flush_worker_external(self):
    """Thread de flush periódico"""
    while not self._stop_event.is_set():

        if FlushConfig.force_flush.wait(timeout=FlushConfig.flushInterval/1000):
            # if not serverConfig.MacroConfig.isRecording or serverConfig.MacroConfig.isRecording and serverConfig.MacroConfig.):
            print("force flush event detected.")
            time.sleep(0.05)  # Pequena espera para garantir que eventos recentes sejam capturados
            self._flush() # a definição original usa flush_external mas na instância ela é apenas flush
            FlushConfig.force_flush.clear()
        else:
            self._flush() # a definição original usa flush_external mas na instância ela é apenas flush
        # Espera 0.5s OU até o stop_event ser setado
        if self._stop_event.is_set():
            break  # Evento de parada foi acionado
        
        
    