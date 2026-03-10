import json
import copy
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.debuggingResources.unified_monitor import monitor_class
from sharedResources.generalUtils.aprint import aprint
from sharedResources.generalUtils.asyncBridge import AsyncBridge
from sharedResources.lifecycle.shutdownMaster import LifecycleMaster

@monitor_class
class answerMapping():
    create_active = True
    main_instance= None
    serverConfig = None
    connections  = None
    def __init__(self, answer = None, serverConfig = None, connections = None, *args,**kargs):
        self.answer = answer
        self.serverConfig = serverConfig
        self.connections = connections
        self.currentMacro = None
        self.__class__.main_instance = self
    
    @classmethod
    def set_serverConfig(cls,serverConfig):
        # print(" a variável que veio como serverConfig é: ",serverConfig)
        if cls.serverConfig is None:
            cls.serverConfig = serverConfig

    @classmethod
    def set_connections(cls,connections):
        if cls.connections is None:
            cls.connections = connections

    @classmethod
    async def create(cls, answer, serverConfig, connections, *args,**kargs):
        cls.answer = answer
        cls.serverConfig = serverConfig
        cls.connections = connections
        cls.currentMacro = None
        if "MacroreadyToUse" in cls.answer:
            cls.MacroReadyToUse = cls.answer["MacroreadyToUse"]
            if cls.MacroReadyToUse:
                # print("a serverConfig.MacroConfig.currentMacro é: ",cls.serverConfig.MacroConfig.currentMacro)
                # cls.currentMacro = cls.serverConfig.MacroConfig.currentMacro
                if cls.create_active:
                    await cls.sendMacroToExecuteInWatcher()
    
    @classmethod
    async def wait_for_macro_execution(cls):
        """
        Wait for the macro execution to finish.
        """
        await AsyncBridge.wait_event(cls.serverConfig.MacroConfig.macroFinishedEvent)
        cls.create_active = True


    @classmethod
    def reset_state(cls):
        cls.serverConfig.MacroConfig.set_flag("requestToExecuteMacro", False)
        cls.answer["MacroreadyToUse"] = False
        ## isso aqui mudarei futuramente pra não precisar buscar ela toda vez, quando houverem varias macros que eu possa executar
        cls.serverConfig.MacroConfig.currentMacro = None
        cls.currentMacro = None
        LifecycleMaster.run_async(cls.wait_for_macro_execution, name="espera pra permitir iniciar macro só quando ela acabar")
        # cls.create_active = True

    @classmethod
    async def sendCommand(cls, command, connection):
        print("the command to be sent is : ", command)
        try:
            await connection.send(json.dumps(command))
        except Exception as e:
            log_error_forensics_plus(e)
            print("deu erro enviando o comando la no server reactions e é: ",e)
  
    @classmethod
    def handleWindowChange(cls,filteredCommand,windowChangeCommand):
        if cls.serverConfig.MacroConfig.checkWindow:
            internalWindowChange = copy.deepcopy(windowChangeCommand)

            while isinstance(internalWindowChange,str):
                internalWindowChange = internalWindowChange.replace("null",'"unknown"')
                # print("convertendo string para json! a string é: ",internalWindowChange)
                try:
                    internalWindowChange = json.loads(internalWindowChange)
                except Exception as e:
                    log_error_forensics_plus(e)
                    print("tentei converter isso aqui com o json.loads e não foi: ",internalWindowChange)
                    break
            if not internalWindowChange:
                # print("caiu no windowChange como dicionario vazio aqui , ele esta assim : ", internalWindowChange)
                return
            else:
                pass
                # print("vou entrar no for nas chaves do internalWindowChange e ele é: ",internalWindowChange)
                # print("o tipo dele é: ",type(internalWindowChange))
            try:    
                for key in internalWindowChange.keys():
                    if internalWindowChange[key] != 'unknown':
                        # print("achei chave não vazia no window_Change event e foi: ",key," e o valor dela é: ",internalWindowChange[key])
                        filteredCommand["window_event"] = internalWindowChange
                        break
            except Exception as e:
                log_error_forensics_plus(e)
                print("deu exceção nessa porra desse for e foi: ", e)

        else:
            print("a config do checkwindow não deu True!!!")

    @classmethod
    def filterCommand(cls, command):
        # "window_event": command[-1] if any(command[-1][x] is not None for x in command[-1]) else {}

        if "keyboard" in command:
            filteredCommand = {
                "deltaTime" : command[1],
                "equipment" : command[3],
                "key"       : command[4],
                "action"    : command[5],
                "modifiers" : command[-2],         
            }
            cls.handleWindowChange(filteredCommand,command[-1])

            # print("o filteredCommand depois de add window_event é: ",filteredCommand)
            
            return ["OS",filteredCommand] ### ja filtrado!!!
        
        if 'mouse' in command:
            filteredCommand = {
                "deltaTime" : command[1],
                "equipment" : command[3],
                "button"    : command[4],
                "action"    : command[5],
                "x"         : command[9],
                "y"         : command[10],
                "details"   : command[-2],
            }
            cls.handleWindowChange(filteredCommand,command[-1])

            return ["OS", filteredCommand ] ### falta filtrar esse aqui !!!!

        if any(["extension","browser","navigator"]) in command:
            return ["browser", command] ### falta filtrar esse aqui !!!!
        if "front_end" in command:
            return ["front_end" , command] ### falta filtrar esse aqui !!!!
    
    @classmethod
    async def sendMacroToExecuteInWatcher(cls):
        try:
            if cls.create_active:
                cls.create_active = False
            else:
                return
            cls.currentMacro = cls.serverConfig.MacroConfig.currentMacro
            if not cls.currentMacro:
                raise RuntimeError(f"tentando enviar ao watcher macro vazia ({cls.currentMacro})")
            await cls.sendCommand({"action":"startMacro"}, getattr(cls.connections, "OS").receiver)
            ### need to send this command above to all connections that will execute the macro
            if cls.serverConfig.MacroConfig.currentPendingCommands["current"] is None and cls.currentMacro is not None:
                cls.serverConfig.MacroConfig.currentPendingCommands["current"] = {}
                # print("iniciated the currentPendingCommands var into ",cls.serverConfig.MacroConfig.currentPendingCommands["current"])
            
            timegap = 0
            # cls.macroPendingCommands = {}

            # cls.currentMacro = macroPendingCommands
            # print("a current macro que vai ser enviada é: ",cls.currentMacro)
            for index ,command in enumerate(cls.currentMacro):
                # print("the command to be sent is : ", command)
                ### aqui vou implementar o envio dos comandos para o sistema de automação
                try:
                    # print("vou tentar iniciar a variavel destiny")
                    destiny,filteredCommand = cls.filterCommand(command)
                    # print("a var destiny é: " ,destiny)
                except Exception as e:
                    print("deu erro filtrando o comando no sendMacroToExecute do server reactions e é: ",e)
                    print("o commando que entrou no filtered command é: ",command)
                    print("o windowChange cru nesse caso é: ", command[-1])
                    log_error_forensics_plus(e)
                    continue
                # if filteredCommand["equipment"] == "mouse":
                    # print("mouse command detected in the macro execution sender")
                if index > 0:
                    timegap = filteredCommand["deltaTime"] - cls.currentMacro[index-1][1]
                # print("o calculo da diferençe de tempo é: ", command[1], " - ", cls.currentMacro[index-1][1], " = ", timegap)
                filteredCommand["deltaTime"] = timegap/1000  ### convertendo para segundos
                if destiny is not None:
                    # print("o destino é : ", destiny, " e o comando é : ", filteredCommand)
                    # print("o atributo achado pelo 'getattr(cls.connections, destiny' é: ",getattr(cls.connections, destiny))
                    with cls.serverConfig.MacroConfig._threading_lock:
                        cls.serverConfig.MacroConfig.currentPendingCommands["current"][index] = {"command": filteredCommand, "status": "pending"}
                        # print(f"added {filteredCommand} into currentPendingCommands")
                    
                    if not cls.serverConfig.MacroConfig.get_flag("stopRunningMacroFlag"):
                        await cls.sendCommand(filteredCommand, getattr(cls.connections, destiny).receiver)
                    else:
                        print("killed macro during the sending process!")
                        break
                    # await cls.sendCommand(filteredCommand, getattr(cls.connections, destiny).sender)
                else:
                    print("não consegui identificar a origem/destino do comando: ", command)

            # reset states after macro execution
            await cls.sendCommand({"action":"endMacro"}, getattr(cls.connections, destiny).receiver)
            # just to see the entirer list of pending commands
            # for PendingCommand in cls.serverConfig.MacroConfig.currentPendingCommands["current"]:
                # print(PendingCommand,"  " , cls.serverConfig.MacroConfig.currentPendingCommands["current"][PendingCommand])           
    
            cls.reset_state()
            # print("the currentPendingCommands after the reset_state is:", cls.serverConfig.MacroConfig.currentPendingCommands["current"])
            # print(f"the answer mapping received is : {cls.answer} and the current macro is : {cls.currentMacro}")
        except Exception as e:
            log_error_forensics_plus(e)
