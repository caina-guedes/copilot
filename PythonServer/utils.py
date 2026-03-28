import copy 
import sys
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sharedResources.generalUtils.aprint import aprint


def resumedMesssage(message):
    
    if message["type"] == "keyboard":
        return message["type"], message["action"], message["key"] 
    elif message["type"] == "mouse":
        return  message["type"],message["action"],  message["button"], message["x"], message["y"]

def handleSpecialCommand(message,specialCommands, commandsMap, conditionsMap):
    # print("entrei na handleSpecialCommand")
    press = False
    isSpecialCommand = False

    if message["type"] == "keyboard":
        try:        
            key = message["key"].replace("Key.","")
            command = None

            if message["action"] == "press":
                press = True

            for specialKey,value in specialCommands.items():
                if key == value.value:
                    command = specialKey
                    isSpecialCommand = True
                    break
            if command is not None:
                # print(f"isso aqui é o comando : ",command)
                if  message["action"] == "press" :
                    if command in commandsMap:
                        if conditionsMap[command]:
                            print("retornou True a condição para o comando: ",command)
                        
                        print("o command que vou executar é:", command)
                        func= commandsMap[command]

                        # dispara a função sem bloquear
                        if "details" in message:
                            commandsMap[command](message['details'])# se tem detalhe envia se não vai sem mesmo
                        else:
                            commandsMap[command]()
                    else:
                        print("esse troço está listado como um comando mas não está mapeado na variável correta")
                        # return False
                # else:
                #     return True
            # else:
            #     return False
            # return isSpecialCommand, press
            
        except Exception as excecaoDaqui:
            print("tentei pegar a key em um evento que não tem e o erro foi: ",excecaoDaqui)
            print("o command é:",command)
            print("a key é: ",key)
            print("a mensagem que chegou nessa função foi: ",message)
    # print("o isSpecialCommand deu: ",isSpecialCommand)
    # print("o press deu: ",press)
    # print("pra mensagem : ",message)
    return isSpecialCommand, press
            
class connections:

    class OS:
        unique = None
        sender = None
        receiver = None
    class front_end:
        unique = None
        sender = None
        receiver = None
    class browser:
        unique = None
        sender = None
        receiver = None
    
    @classmethod
    def active_clients(cls):
        active = []
        # print(f"[connections.active_clients] init!")
        for group_name, group in cls.__dict__.items(): # nome vai ser OS ou front_end ou browser
            # attr = getattr(cls, attr_name)

            # só classes internas
            if not isinstance(group, type):
                # print(f"[connections.active_clients] {group_name} is not a internal class")
                continue

            # ignora coisas privadas
            if group_name.startswith("_"):
                # print(f"[connections.active_clients]{group_name} is private! ")
                continue

            for conn_name in ("unique", "sender", "receiver"):
                conn = getattr(group, conn_name, None)
                if conn is not None:
                    register= [group_name,conn_name,conn]
                    # print(f"[connections.active_clients] appending {register}")
                    active.append(register)
                else:
                    pass
                    # print(f"[connections.active_clients] {group_name}.{conn_name} is {conn} ")
        # print(f"[connections.active_clients] number of active conns  is:",len(active))
        # if active:
        #     for part in active:
        #         pass
                # print(f"[connections.active_clients] con:  " , part)
        return active

        
