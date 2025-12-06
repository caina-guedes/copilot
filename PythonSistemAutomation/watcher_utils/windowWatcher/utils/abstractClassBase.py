from abc import ABC, abstractmethod
import logging
class BaseWindowBackend(ABC):

    def __init__(self, debug=False):
        self.log = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        self.log.addHandler(handler)
        self.log.setLevel(logging.DEBUG if debug else logging.INFO)

    @abstractmethod
    def list_windows(self):
        raise NotImplementedError

    @abstractmethod
    def get_active_window(self):
        raise NotImplementedError

    @abstractmethod
    def focus_window(self, window_id):
        raise NotImplementedError
