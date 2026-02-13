# PythonServer/core/state.py
from PythonServer.utils import connections

# Variáveis que antes ficavam soltas no server.py
commands_per_connection = {}

# Singletons (serão inicializados no startup do server e acessados pelos handlers)
mainDb = None
macro_manager = None
server_config = None
watcher_configs = None
commands = None
conditions_map = None