

from PythonSistemAutomation.watcher_utils.default_callback import treat_key_as_string
from pynput import mouse, keyboard
from sharedResources.pythonLoggerSistem.logger import LoggerManager
import warnings 
# logger = LoggerManager.get_logger(__name__,filename = __name__+'.log')
logger = LoggerManager.get_logger(__name__)
"""
preciso resolver a questão de arquivos de configurações diferentes, vou precisar centralizar e unificar
"""

class EventObserverConfig:
    def __init__(self, is_macro_recording = True, bgRecording = True):
        self.is_macro_recording = is_macro_recording
        self.bgRecording = bgRecording
        self.stopKey = treat_key_as_string(keyboard.Key.esc)
        self.toggleRecordKey = "Key.f1"
        self.repetition = True  # Default value, can be changed later
        self.send_position = False  # Default value, can be changed later
        self.ExecutaMacroKey = "Key.f2"

    def dont_want_repetition(self):
        return not self.repetition
    
    def update_config(self, is_macro_recording=None, bgRecording=None):
        if is_macro_recording is not None:
            self.is_macro_recording = is_macro_recording
        if bgRecording is not None:
            self.bgRecording = bgRecording

    def get_stopKey(self):
        return self.stopKey
    
    def set_stopKey(self, key):
        try:
            if isinstance(key, keyboard.Key) or isinstance(key, str):
                self.stopKey = key
                return True
            else:
                logger.info("Invalid key type. Must be a keyboard.Key or a string.")
                return False
        except Exception as e:
            logger.error(f"Error setting stop key: {e}")
            # logger.info(f"Error setting stop key: {e}")
            warnings.warn(e)
            return False
        
    def is_macro_recording_enabled(self):
        return self.is_macro_recording
    
    def toggle_macro_recording(self):
        self.is_macro_recording = not self.is_macro_recording

    def is_bgRecording_enabled(self):
        return self.bgRecording
    
    def toggle_bgRecording(self):
        self.bgRecording = not self.bgRecording

