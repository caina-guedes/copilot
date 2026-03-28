import threading


class ExecutionContext:
    def __init__(self, execution_id):
        self.id = execution_id
        self.finished = threading.Event()
        self.error = None
        self.result = None

    def wait(self):
        self.finished.wait()

    def finish(self, result=None):
        self.result = result
        self.finished.set()

    def fail(self, error):
        self.error = error
        self.finished.set()
