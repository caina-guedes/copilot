import json
import sys

from sharedResources.generalUtils.aprint import aprint

def printaESai(mensagem, status = 1):
    """
    Imprime uma mensagem e sai do programa.
    :param mensagem: Mensagem a ser impressa.
    """
    print(mensagem)
    sys.exit(status)

def json_or_exit(mensagem, status = 1):
    try:
        dados = json.loads(mensagem)
        return dados
    except json.JSONDecodeError:
        print(f"❌ JSON inválido nos dados! JSON recebido: {mensagem}")
        sys.exit(status)