import sys
import os

# Ajusta o sys.path para incluir o diretório raiz do projeto
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Agora importe seu módulo principal (troque pelo caminho do seu arquivo principal)
from PythonSistemAutomation.main  import *
from sharedResources.generalUtils.aprint import aprint
# Se quiser rodar alguma função principal, pode fazer aqui
if __name__ == '__main__':
    print(dir())
