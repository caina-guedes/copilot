import copy 
import sys

from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from sharedResources.generalUtils.aprint import aprint
"""
preciso criar a função "prepare" que vai receber a variável serverConfig e setar todos os 
atributos de classe que serão necessários vindos dela

Alem disso preciso transformar as funções que estão como funções de instância em funções de classe
e tambem preciso adaptar a função que de fato vai ser usada la no server pra não precisar mais receber tantas variáveis

"""

class macroManager:
    serverConf = None
    macroConf  = None
    lock = None
    pendingCommands = None


    def __init__(self,serverConf):
        self.__class__.serverConf = serverConf
        self.__class__.macroConf  = serverConf.MacroConfig
        self.__class__.lock = serverConf.MacroConfig._threading_lock
        self.__class__.pendingCommands = serverConf.MacroConfig.currentPendingCommands


    @classmethod
    def _getSpecificsFromWatcher(cls,message):
        """this function threats the message that 
        comes from the SOWatcher in a way that i 
        can compare to the current pending commands"""
        
        interesting = {}
        interesting["equipment"] = message["type"]
        for x in message:
            if x not in ["timestamp" , "type" , "targetTable", "windowChange", "newCurrentWindow"]:
                interesting[x] = message[x]
        return interesting


    @classmethod
    def _getSpecificFromPendingCommands(cls):
        convenientPendingCommands = {}
        # print("o currentPendingCommands do macro config é: ",pendingCommands)

        for pendingKey, targetPendingCommand in cls.pendingCommands["current"].items():
            if targetPendingCommand["status"] == "done":
                continue
            realPendingCommand = targetPendingCommand["command"]
            # print("o pendingCommandItem é: ",pendingKey)
            # print(pendingKey,"  ",realPendingCommand)
            convenientPendingCommand = {}
            # print('the realPendingCommand is: ',realPendingCommand)

            for key in realPendingCommand:
                if key not in ["modifiers","deltaTime","window_event", "newCurrentWindow"]:
                    convenientPendingCommand[key] = realPendingCommand[key]
                    # print("not ignored key to append in de convenientPendingCommands is : ",key)
                    # print("the key is: " , key)
                    # print("the convenientPendingCommand is: ",convenientPendingCommand)
                    # print("the realPendingCommand is: ",realPendingCommand)
            convenientPendingCommands[pendingKey] = copy.deepcopy(convenientPendingCommand)
        convenientPendingListOfCommands = []
        for keyIndex in convenientPendingCommands:
            convenientPendingListOfCommands.append(convenientPendingCommands[keyIndex])
        # print(convenientPendingCommands)
        # print("o tamanho da convenientPendingListOfCommands é :", len(convenientPendingListOfCommands))
        # print("o tamanho da convenientPendingCommands é: ",len(convenientPendingCommands))
        return convenientPendingListOfCommands,convenientPendingCommands


    @classmethod
    def handlePendingMacroCommand(cls,message):
        with cls.lock:
            # print("entrei na handlePendingMacroCommand")
        
            if cls.pendingCommands["current"] is not None and len(cls.pendingCommands["current"]) > 0:
                convenientWatcherInfo = cls._getSpecificsFromWatcher(message)
                convenientPendingListOfCommands,convenientPendingCommandsDict = cls._getSpecificFromPendingCommands()

                if convenientWatcherInfo in convenientPendingListOfCommands:
                    realKey = None
                    for x in convenientPendingCommandsDict:
                        if convenientWatcherInfo == convenientPendingCommandsDict[x]:
                            realKey = x
                    # print("deu match")                
                    cls.pendingCommands["current"][realKey]["status"] = "done"
                    doneCommands = 0
                    for key,element in cls.pendingCommands["current"].items():
                        if element["status"] == "done":
                            doneCommands += 1

                    percentage = doneCommands/float(len(cls.pendingCommands["current"]))
                    print("quantidade de comandos feitos até agora é:", doneCommands, f"  ou seja {percentage}  of the task done")

                    # deletePendingCommand(convenientWatcherInfo,pendingCommands)
                    return True
                else:
                    # print("não deu match")
                    # print("o comando que não deu match foi: ", convenientWatcherInfo)
                    # print(" e a lista de comandos de macro pendentes ja filtrada de forma conveniente é:", convenientPendingListOfCommands)
                    return False
            else:
                # print("não tem nenhum comando de macro pendente e a lista é:",cls.pendingCommands["current"])
                return False

    

    
