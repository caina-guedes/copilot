
import json
import time
from pathlib import Path
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.generalUtils.aprint import aprint

"""
Responsável por: _log_keyboard, _log_mouse, _log_browser_event

Função: Criar os dicionários de eventos e chamar add_event().
"""


def _log_browser_event(self, url, title, js_payload, device='browser-ext', source='extension', windowEvent = None):
    print(f"browser event: url={url}, title={title}, js_payload={js_payload}, device={device}, source={source}")
    details = {
        'url': url,
        'title': title,
        'js_payload': js_payload
    }
    event_dict = {
        'ts': int(time.time() * 1000),
        'type': 'browser',
        'key': None,
        'action': 'event',
        'device': device,
        'source': source,
        'details': json.dumps(details),
    }
    with self.serverConfig.MacroConfig._threading_lock:
        event_dict['macro_id']: self.recordingMacroId

    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de browser!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]

    self.add_event(event_dict)


def _log_mouse(self, x, y, action, button=None, clicks=None, wheel_delta=None,
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
        'ts': int(time.time() * 1000),
        'type': 'mouse',
        'key': button,
        'action': action,
        'device': device,
        'source': source,
        # 'details': json.dumps(details),
        'x': x,
        'y': y,
    }
    with self.serverConfig.MacroConfig._threading_lock:
        event_dict['macro_id']: self.recordingMacroId

    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de mouse!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]
    # print("o evento que será adicionado a lista de flush na função de mouse é: ", event_dict)
    
    self.add_event(event_dict)


def _log_keyboard(self, key, action, modifiers=None, device='keyboard', source='background', windowEvent = None , isSpecialCommand = False):
    # print(f"keyboard event: key={key}, action={action}, modifiers={modifiers}, device={device}, source={source}")
    details = {'modifiers': modifiers or []}
    event_dict = {
        'ts': int(time.time() * 1000),
        'type': 'keyboard',
        'key': key,
        'action': action,
        'device': device,
        'source': source,
        'details': json.dumps(details),
    }
    with self.serverConfig.MacroConfig._threading_lock:
        event_dict['macro_id']: self.recordingMacroId

    # print("o event_dict na log_keyboard  nesse ponto é: ",event_dict)
    if windowEvent["windowChange"]:
        # print("a janela mudou nesse evento de keyboard!")
        # print(windowEvent["newCurrentWindow"])
        event_dict["newCurrentWindow"] = windowEvent["newCurrentWindow"]
    # print("o event_dict na log_keyboard  nesse outro ponto é: ",event_dict)
    # print("o evento que será adicionado a lista de flush na função de teclado é: ", event_dict)
    self.add_event(event_dict, isSpecialCommand)

def log_background_event(self, event, isSpecialCommand):
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
    type_ = event.get('type').lower()
    windowEvent = {"windowChange":event["windowChange"]}
    # print("the var windowEvent is:", windowEvent)
    if event["windowChange"]:

        windowEvent["newCurrentWindow"] = event["newCurrentWindow"]
        # print("the var windowEvent is:", windowEvent)
        # print('the windowEvent["newCurrentWindow"] is ',windowEvent["newCurrentWindow"])

    if type_.find('keyboard') != -1:
        # print("keyboard event came to the event logger to be aved in the main db")
        _log_keyboard(self,
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
    # print("o windowChange no evento chegou ao server é:",event.get("windowChange"))
    