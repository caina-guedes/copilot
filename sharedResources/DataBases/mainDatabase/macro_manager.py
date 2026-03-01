


"""startNewMacro, stopMacro, GetCurrentMacroFunction functions implementation."""
from pathlib import Path
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.generalUtils.aprint import aprint
# from sharedResources.DataBases.utils.mainDbUtils import preparedQuerryes
from sharedResources.DataBases.mainDatabase.querrys import querrys

def startRecordingNewMacro_external(self):
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
                self.cursor.execute(querrys["registroInicialMacro"], (name, self.serverConfig.MacroConfig.startMacroTime))
                self.recordingMacroId = self.cursor.lastrowid
                self.conn.commit()
                print(f"Nova macro iniciada com ID: {self.recordingMacroId}")
        except Exception as e:
            print("exception occurrent while trying to start a new macro: (?)",e)

def stopRecordingMacro_external(self):
    self.cursor.execute(querrys["selectMacroAtiva"])
    row = self.cursor.fetchone()
    if not row:
        print(f"nenhuma macro em andamento. setarei recordingMacroId para None")
        with self.serverConfig.MacroConfig._threading_lock:
            self.recordingMacroId = None
    else:
        print("macro em andamento.isso é bom. vou parar ela")
        self.cursor.execute(querrys["registroFimDeMacro"], (self.serverConfig.MacroConfig.stopMacroTime,))
        with self.serverConfig.MacroConfig._threading_lock:
            self.recordingMacroId = None
        self.conn.commit()


def GetCurrentMacroFunction_external(self , *args,**kargs):
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
            return currentMacro
        else:
            print("no registered macro yet")
    except Exception as e:
        print("exception occurrent while trying to get the current macro : (?)",e)
