# envia_comando.py
import asyncio
import websockets
import json
import sys
from envia_comando_utils import printaESai, json_or_exit
with open("./comandoTexte.json", encoding="utf-8") as f:
    texte = json.load(f)["texte1"]
from sharedResources.generalUtils.aprint import aprint

async def enviar_comando_para_servidor(comando, parametros = None, pagina = None):
    """
    Envia um comando para o servidor WebSocket.
    :param comando: O comando a ser enviado.
    :param dados: Dados adicionais a serem enviados (opcional).
    """
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        # Informa ao servidor que é um cliente do tipo "controle"
        await websocket.send(json.dumps({"tipo": "controle"}))

        mensagem = {
            "url"   : pagina,
            "tipo"  : comando,
            "parametros" : parametros 
            
        }

        await websocket.send(json.dumps(mensagem))
        print("📤 Comando enviado ao servidor WebSocket.")
        # Aguarda a resposta do servidor
        try:
            resposta = await websocket.recv()
            print("📥 Resposta do servidor:", resposta)
        except websockets.exceptions.ConnectionClosed:
            print("❌ Conexão encerrada pelo servidor.")
        except Exception as e:
            print("❌ Erro ao receber resposta:", e)
        # Encerra a conexão

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Uso: python3 envia_comando.py <comando> [<dados_json>]")
        print("farei textes automáticos então")
        asyncio.run(enviar_comando_para_servidor(texte["tipo"], texte["dados"], texte["url"]))
        sys.exit(1)

    comando = sys.argv[1]
    dados = None
    
    for x , y in enumerate(sys.argv):
        print(x,'  ', type(x), '  ', y)

    if len(sys.argv) >= 3:
        
        dados = json_or_exit(sys.argv[2])
        
    if len(sys.argv) >= 4:
        print('cheguei no len >= 4')
        pagina = sys.argv[3]
        try:
            pagina = sys.argv[3]
        except json.JSONDecodeError:
            print(f"❌ JSON inválido nos dados! JSON recebido: {sys.argv[3]}")
            sys.exit(1)
    try:
        # Envia o comando para o servidor WebSocket
        asyncio.run(enviar_comando_para_servidor(comando, dados, pagina ))
    except KeyboardInterrupt:
        printaESai("❌ Interrompido pelo usuário.")
    except websockets.exceptions.InvalidURI:
        printaESai("❌ URI inválida! Verifique o endereço do servidor.")
    except websockets.exceptions.InvalidHandshake:
        printaESai("❌ Falha na conexão! O servidor está ativo?")
    except websockets.exceptions.ConnectionClosed:
        printaESai("❌ Conexão encerrada pelo servidor.")
    except websockets.exceptions.InvalidStatusCode:
        printaESai("❌ Código de status inválido! O servidor está ativo?")

"""
python3 envia_comando.py "execute_steps" {"steps": [{"action": "alert", "message": "cheguei aqui"}]} chatgpt.com/
"""
