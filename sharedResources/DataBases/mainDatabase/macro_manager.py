


"""startNewMacro, stopMacro, GetCurrentMacroFunction functions implementation."""
from pathlib import Path
import time
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.debuggingResources.error_tracker import log_error_forensics_plus
from sharedResources.generalUtils.aprint import aprint
# from sharedResources.DataBases.utils.mainDbUtils import preparedQuerryes
from sharedResources.DataBases.mainDatabase.querrys import querrys

def startRecordingNewMacroOnDb_external(self):
    with self.serverConfig.MacroConfig._threading_lock:
        try:
            self.cursor.execute(querrys["selectMacroAtiva"])
            row = self.cursor.fetchone()
            if row:
                print(f"Macro em andamento com ID: {row[0]} setarei esse id como o atual")
                self.recordingMacroId = row[0]
            else:
                print("Nenhuma macro em andamento.isso é bom")
                name = "Minha Macro"
                
                # if not self.serverConfig.MacroConfig.startMacroRecordingTime:
                #     self.serverConfig.MacroConfig.startMacroRecordingTime = time.time()

                self.cursor.execute(querrys["registroInicialMacro"], (name, self.serverConfig.MacroConfig.startMacroRecordingTime))
                self.recordingMacroId = self.cursor.lastrowid
                self.conn.commit()
                print(f"Nova macro iniciada com ID: {self.recordingMacroId}")
        except Exception as e:
            print("exception occurrent while trying to start a new macro: (?)",e)
            log_error_forensics_plus(e)

def stopRecordingMacroOnDB_external(self):
    try:
        with self.serverConfig.MacroConfig._threading_lock:
            #seta a configuração na memória antes de mexer no DB
            self.recordingMacroId = None 
        
        self.cursor.execute(querrys["selectMacroAtiva"])
        row = self.cursor.fetchone()
        if not row:
            print(f"nenhuma macro em andamento, isso não deveria ter sido executado!!")
            1/0 # forçando erro para ver o relatório da forensics
        else:
            print("macro em andamento no DB.isso é bom. vou registrar a parada nele")
            self.cursor.execute(querrys["registroFimDeMacro"], (self.serverConfig.MacroConfig.stopMacroRecordingTime,))                
            self.conn.commit()
    
    except Exception as e:
        log_error_forensics_plus(e)


def GetCurrentMacroOnDb_external(self , *args,**kargs):
    """Get the current macro."""
    try: 
        self.cursor.execute(querrys["selectUltimoIdDeMacro"])
        row = self.cursor.fetchone()
        if row:
            identifier = row[0]
            print(f"Current macro ID: {identifier}")
            self.cursor.execute(querrys["translated_events_per_macro_id"], (identifier,))
            currentMacro = self.cursor.fetchall()
            # print('o numero de comandos é: ',len(currentMacro))
            # for comando in currentMacro:
            #     print(comando)
            self.serverConfig.MacroConfig.currentMacro = currentMacro
            if currentMacro is  not None:
                self.answer = {"MacroreadyToUse": True}
                print("macro ready to use!")
                print('and it is: ',currentMacro)

            return currentMacro
        else:
            print("no registered macro yet")
    except Exception as e:
        print("exception occurrent while trying to get the current macro : (?)",e)
        log_error_forensics_plus(e,extra_message= "dentro da GetCurrentMacroOnDb_external")
