from sharedResources.pythonLoggerSistem.logger import LoggerManager
from PythonServer.serverConfig import connection_types
import json

logger = LoggerManager.get_logger(__name__)

async def threatHandShake(cls,connection,isReceiver=True):
        # Send initial message with tipo
        # logger.info('cheguei na função do threathandshakeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!1')
        if isReceiver:
            tipo = connection_types["OSwatcherReceiver"]
        else:
            tipo = connection_types["OSwatcherSender"]
        msg = {
                "tipo": tipo
            }
        # async with cls.sender_lock:

        await connection.send(json.dumps(msg))
        # logger.info('consegui enviar a resposta')
        if isReceiver:
            # logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!! o lock do receiver é: ',cls.connection.receiver_lock)
            async with cls.connection._receiver_lock:
                response = await connection.recv()
        else:
            # logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!! o lock do sender é: ',cls.connection.sender_lock)
            async with cls.connection._sender_lock:
                response = await connection.recv()
        # logger.info('recebi resposta da resposta de volta !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        status = json.loads(response).get('status', 'unknown')

        if json.loads(response)['status'] == "sucesso":
            logger.info(f"[{__name__}] 🖥️ {tipo} Connection Started!")
        elif status == "falha":
            logger.info(f"[{__name__}] ❌ Message processing failed.")
            raise ConnectionError("Handshake failed")
        else:
            logger.info(f"[{__name__}] ⚠️ Unhandled status in message. {status} and response: {response}")
            raise ConnectionError("Unexpected handshake response")
        # if isReceiver:
        #     ##start receiver loop here!!!
        #     pass|
