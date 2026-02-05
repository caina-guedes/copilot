from datetime import datetime, timezone
from copy import deepcopy
import json
import uuid
from sharedResources.pythonLoggerSistem.logger import LoggerManager

# logger = LoggerManager.get_logger("event_utils", "event_utils.log")
logger = LoggerManager.get_logger(__name__)

class Event:
    def __init__(self, raw_event = "", *, id=None, timestamp=None, type=None, targetTable=None, **extra_fields):
        """
        Cria um evento a partir de um dicionário.
        """
        if raw_event:
            if isinstance(raw_event, str):
                raw_event = json.loads(raw_event)

            elif isinstance(raw_event,self.__class__):
                self.raw_event = dict(raw_event.raw_event)
            
            elif not isinstance(raw_event, dict):
                raise ValueError("Evento deve ser um dicionário ou JSON válido.")

        self.id = raw_event.get("id", id or None)
        self.timestamp = date_serializer(raw_event.get("timestamp", timestamp or self._now()))
        self.type = raw_event.get("type", "unknown")
        self.targetTable = raw_event.get("targetTable", "unknown")
        self.data = {k: v for k, v in raw_event.items() if k not in ["id", "timestamp", "type", "targetTable"]}
 
    def _now(self):
        return datetime.now(timezone.utc).isoformat() + "Z"

    def set_target_table(self, table_name):
        self.targetTable = table_name

    def to_dict(self, include_id):
        base = {
            "timestamp": self.timestamp,
            "type": self.type,
            "targetTable": self.targetTable,
            **self.data
        }
        if include_id and self.id is not None:
            base["id"] = self.id
        return deepcopy(base)

    def to_json(self, include_id= False):
        return json.dumps(self.to_dict(include_id=include_id))

    def to_string(self,include_id):
        return str(self.to_json(include_id))
    
    def set_id(self,id):
        self.id = id

    def remove_id(self):
        self.id = None

    def update_data(self, **kwargs):
        self.data.update(kwargs)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return f"<Evento type={self.type} id={self.id}>"

    # @classmethod
    # def from_serialized(cls, serialized):
    #     """
    #     Permite criar um evento diretamente de um JSON ou dicionário.
    #     """
    #     if isinstance(serialized, str):
    #         serialized = json.loads(serialized)
    #     return cls(serialized)


def date_serializer(date):
    """
    Serializes a datetime object or ISO 8601 string to an ISO 8601 string.
    If input is already a string, returns it as-is.
    """
    if isinstance(date, datetime):
        return date.isoformat()
    elif isinstance(date, str):
        return date  # Assume already in ISO format
    else:
        raise TypeError(f"Expected datetime or str, got {type(date)}")

# def date_serializer(date):
#     """
#     Serializes an event dictionary to a JSON string.
#     Converts datetime objects to ISO format strings.
#     """
#     # event_copy = event.copy()
#     # if isinstance(date, datetime):
#     return date.isoformat()

    # return json.dumps(event_copy)

# def event_deserializer(json_event):
#     event = json.loads(json_event)
#     if 'date-time' in event:
#         try:
#             event['date-time'] = datetime.fromisoformat(event['date-time'])
#         except ValueError:
#             LoggerManager().log_exception_with_context(f"Invalid date-time format in event: {event['date-time']}, and the event is: {event}")
#             pass  # ou lançar erro se preferir
#     return event

