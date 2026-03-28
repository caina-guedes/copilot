
import json
import time
from pathlib import Path
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.generalUtils.aprint import aprint

"""
Responsável por: _log_keyboard, _log_mouse, _log_browser_event

Função: Criar os dicionários de eventos e chamar add_event().
"""

def _threat_macro_id(self,event_dict):
    """
    tenho que tratar TODOS OS CASOS!!! relacionados ao startMacroRecordingTime e ao stopMacroRecordingTime
    o self = instancia do mainDb
    
    variáveis que tenho que olhar:
    isRecording
    startMacroRecordingTime
    stopMacroRecordingTime
    recordingMacroId
    """
    try:

        with self.serverConfig.MacroConfig._threading_lock:
            # print(f"nesse ponto o event_dict é:{event_dict}")
            # print(f"MacroConfig é :{self.serverConfig.MacroConfig}")
            
            if self.serverConfig.MacroConfig.isRecording:    
                #está gravando!
                if self.recordingMacroId is None:
                    self.recordingMacroId_is_none_while_recording_counter +=1
                    # raise RuntimeError(f"self.recordingMacroId is {self.recordingMacroId} but self.serverConfig.MacroConfig.isRecording is : {self.serverConfig.MacroConfig.isRecording} this shouldn't happen")
                else:
                    if self.recordingMacroId_is_none_while_recording_counter >0:
                        # print(f"ocorreram {self.recordingMacroId_is_none_while_recording_counter} eventos enquanto recordinMacroId = None e isRecording = True ")
                        self.recordingMacroId_is_none_while_recording_counter = 0
                
                if self.serverConfig.MacroConfig.startMacroRecordingTime< event_dict["ts"]:
                    #setou o inicio da macro antes do evento acontecer!
                    event_dict['macro_id'] = self.recordingMacroId
                    # print(f""" confira o macro_id do event_dict 
                    #     esse evento aconteceu ---- DEPOIS do tempo de inicio ----- da macro registrado
                    #     registro de tempo na MacroConfig:{self.serverConfig.MacroConfig.startMacroRecordingTime}
                    #     e o ts do evento é: {event_dict['ts']}""")
                else:
                    #setou o inicio da macro depois do evento acontecer
                    event_dict["macro_id"] = None
                    # print(f""" confira o macro_id do event_dict 
                    #     esse evento aconteceu ---- ANTES do tempo de inicio ---- da macro registrado
                    #     registro de tempo na MacroConfig:{self.serverConfig.MacroConfig.startMacroRecordingTime}
                    #     e o ts do evento é: {event_dict['ts']}""")
            else:
                #não está gravando
                if self.recordingMacroId is not None:
                    self.recordingMacroId_is_not_None_while_Not_recording_counter += 1
                    # raise RuntimeError(f"self.recordingMacroId is {self.recordingMacroId} but self.serverConfig.MacroConfig.isRecording is : {self.serverConfig.MacroConfig.isRecording} this shouldn't happen")
                else:
                    if self.recordingMacroId_is_not_None_while_Not_recording_counter> 0:
                        # print(f"ocorreram {self.recordingMacroId_is_not_None_while_Not_recording_counter} eventos com o ID != {self.recordingMacroId} while not recording")
                        self.recordingMacroId_is_not_None_while_Not_recording_counter = 0
               
                if self.serverConfig.MacroConfig.stopMacroRecordingTime is None:
                    # print("não está gravando e o stopMacroRecordingTime é None, pois desde o início do programa ainda não tentaram gravar!")
                    event_dict['macro_id'] = None
                    return
                # else:
                #     print(f"não está gravando e o stopMacroRecordingTime é: {self.serverConfig.MacroConfig.stopMacroRecordingTime} pois já houve gravação ")
                if self.serverConfig.MacroConfig.stopMacroRecordingTime <= event_dict["ts"]:

                    event_dict['macro_id'] = None
                    # print(f""" esse evento aconteceu ---- DEPOIS do tempo DO FIM  ---- da macro registrado
                    #     registro de tempo na MacroConfig:{self.serverConfig.MacroConfig.stopMacroRecordingTime}
                    #     e o ts do evento é: {event_dict['ts']}""")
                else:
                    event_dict["macro_id"] = self.recordingMacroId
                    # print(f""" esse evento aconteceu ---- ANTES do tempo DO FIM  ---- da macro registrado
                    #     o registro de tempo na MacroConfig é: {self.serverConfig.MacroConfig.stopMacroRecordingTime}
                    #     e o ts do evento é: {event_dict['ts']}""")
    except Exception as e:
        log_error_forensics_plus(e,extra_message=f"""
case where
isRecording      = {self.serverConfig.MacroConfig.isRecording},
startMacroRecordingTime   = {self.serverConfig.MacroConfig.startMacroRecordingTime},
stopMacroRecordingTime    = {self.serverConfig.MacroConfig.stopMacroRecordingTime}, 
recordingMacroId = {self.recordingMacroId}
""")            

def _log_browser_event(self,timestamp, url, title, js_payload, device='browser-ext', source='extension', windowEvent = None):
    print(f"browser event: url={url}, title={title}, js_payload={js_payload}, device={device}, source={source}")
    details = {
        'url': url,
        'title': title,
        'js_payload': js_payload
    }
    event_dict = {
        'ts': timestamp,
        'type': 'browser',
        'key': None,
        'action': 'event',
        'device': device,
        'source': source,
        'details': json.dumps(details),
    }
    _threat_macro_id(self,event_dict)
    # with self.serverConfig.MacroConfig._threading_lock:
    #     event_dict['macro_id'] = self.recordingMacroId

    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de browser!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]

    self.add_event(event_dict)


def _log_mouse(self,timestamp, x, y, action, button=None, clicks=None, wheel_delta=None,
                device='mouse', source='background', windowEvent = None):
    # print(f"mouse event: x={x}, y={y}, action={action}, button={button}, clicks={clicks}, wheel_delta={wheel_delta}, device={device}, source={source}")
    
    
    
    # details = {
    #     'button': button,
    #     'clicks': clicks,
    #     'wheel_delta': wheel_delta,
    #     'movement_dx': None,
    #     'movement_dy': None
    # }
    event_dict = {
        'ts': timestamp,
        'type': 'mouse',
        'key': button,
        'action': action,
        'device': device,
        'source': source,
        # 'details': json.dumps(details),
        'x': x,
        'y': y,
    }
    _threat_macro_id(self,event_dict)
    # with self.serverConfig.MacroConfig._threading_lock:
        # ponto chave pra ver se o comando pertence a macro ou não!!!!!

        # event_dict['macro_id'] = self.recordingMacroId

    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de mouse!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]
    # print("o evento que será adicionado a lista de flush na função de mouse é: ", event_dict)
    
    self.add_event(event_dict)


def _log_keyboard(self,timestamp , key, action, modifiers=None, device='keyboard', source='background', windowEvent = None , isSpecialCommand = False):
    # print(f"keyboard event: key={key}, action={action}, modifiers={modifiers}, device={device}, source={source}")
    details = {'modifiers': modifiers or []}
    event_dict = {
        'ts': timestamp,
        'type': 'keyboard',
        'key': key,
        'action': action,
        'device': device,
        'source': source,
        'details': json.dumps(details),
    }
    
    _threat_macro_id(self,event_dict)

    # print("o event_dict na log_keyboard  nesse ponto é: ",event_dict)
    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de keyboard!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]
    # print("o event_dict na log_keyboard  nesse outro ponto é: ",event_dict)
    # print("o evento que será adicionado a lista de flush na função de teclado é: ", event_dict)
    self.add_event(event_dict, isSpecialCommand)

def log_background_event_external(self, event, isSpecialCommand):
    """
    Recebe um evento genérico do background e chama a função correta
    event: dicionário com pelo menos:
        {
            'type': 'keyboard' | 'mouse' | 'browser',
            'key': 'F8',           # só para teclado
            'action': 'press',
            'x': 100, 'y': 200,    # só para mouse
            'button': 'left',      # só para mouse
            'clicks': 1,
            'wheel_delta': 0,
            'modifiers': ['shift'], # só para teclado
            'url': '', 'title': '', 'js_payload': {},  # só para browser
            'device': 'keyboard' | 'mouse' | 'browser-ext',
            'source': 'background' | 'macro' | 'extension'
        }
    """
    # print("the event that came in the log_background_event is:" , event)
    # print(f"[INFO] Logging background event: {event}")
    # print("[log_background_event_external] init")
    try:
        type_ = event.get('type').lower()
        windowEvent = {"windowChange":event["windowChange"]}
        # print("the var windowEvent is:", windowEvent)
        if event["windowChange"]:

            windowEvent["newCurrentWindow"] = event["newCurrentWindow"]
            # print("the var windowEvent is:", windowEvent)
            # print('the windowEvent["newCurrentWindow"] is ',windowEvent["newCurrentWindow"])

        if type_.find('keyboard') != -1:
            # print("keyboard event came to the event logger to be saved in the main db")
            _log_keyboard(self,
                timestamp = event.get("timestamp"),
                key=event.get('key'),
                action=event.get('action'),
                modifiers=event.get('modifiers'),
                device=event.get('device', 'keyboard'),
                source=event.get('source', 'background'),
                windowEvent = windowEvent,
                isSpecialCommand = isSpecialCommand
            )

        elif type_.find('mouse') != -1 or type_.find('click') != -1:
            _log_mouse(self,
                timestamp = event.get("timestamp"),
                x            =  event.get('x'),
                y            =  event.get('y'),
                action       =  event.get('action'),
                button       =  event.get('button'),
                clicks       =  event.get('clicks'),
                wheel_delta  =  event.get('wheel_delta'),
                device       =  event.get('device', 'mouse'),
                source       =  event.get('source', 'background'),
                windowEvent = windowEvent
            )

        elif type_.find('browser') != -1 or type_.find('extension') != -1:
            _log_browser_event(self,
                timestamp = event.get("timestamp"),
                url=event.get('url'),
                title=event.get('title'),
                js_payload=event.get('js_payload'),
                device=event.get('device', 'browser-ext'),
                source=event.get('source', 'extension'),
                windowEvent = windowEvent
            )

        else:
            print(f"[WARN] Evento desconhecido: {event}")
            return
        # print("[log_background_event_external] end")

        # print("o windowChange no evento chegou ao server é:",event.get("windowChange"))
    except Exception as e:
        log_error_forensics_plus(e)