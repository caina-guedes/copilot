


"""startNewMacro, stopMacro, GetCurrentMacroFunction functions implementation."""
from pathlib import Path
RootDir = str(Path(__file__).resolve().parent.parent.parent.parent)
from sharedResources.generalUtils.aprint import aprint
from sharedResources.DataBases.utils.mainDbUtils import preparedQuerryes


def startNewMacro(self):
    with self.serverConfig.MacroConfig._threading_lock:
        self.cursor.execute("select id from macros where end_time is null ")
        row = self.cursor.fetchone()
        if row:
            print(f"Macro em andamento com ID: {row[0]} setarei esse id como o atual")
            self.recordingMacroId = row[0]
        else:
            print("Nenhuma macro em andamento.isso é bom")
            name = "Minha Macro"
            self.cursor.execute("INSERT INTO macros (name, start_time) VALUES (?, ?)", (name, self.serverConfig.MacroConfig.startMacroTime))
            self.recordingMacroId = self.cursor.lastrowid
            self.conn.commit()

def stopMacro(self):
    self.cursor.execute("select id from macros where end_time is null ")
    row = self.cursor.fetchone()
    if not row:
        print(f"nenhuma macro em andamento. setarei recordingMacroId para None")
        with self.serverConfig.MacroConfig._threading_lock:
            self.recordingMacroId = None
    else:
        print("macro em andamento.isso é bom. vou parar ela")
        self.cursor.execute("UPDATE macros SET end_time = ? WHERE end_time IS NULL", (self.serverConfig.MacroConfig.stopMacroTime,))
        with self.serverConfig.MacroConfig._threading_lock:
            self.recordingMacroId = None
        self.conn.commit()


def GetCurrentMacroFunction(self , *args,**kargs):
    """Get the current macro."""
    try: 
        self.cursor.execute("select id from macros order by ID desc limit 1")
        row = self.cursor.fetchone()
        if row:
            identifier = row[0]
            print(f"Current macro ID: {identifier}")
            self.cursor.execute(preparedQuerryes.translated_events_per_macro_id, (identifier,))
            currentMacro = self.cursor.fetchall()
            # print('o numero de comandos é: ',len(currentMacro))
            # for comando in currentMacro:
            #     print(comando)
            return currentMacro
        else:
            print("no registered macro yet")
    except Exception as e:
        print("exception occurrent while trying to get the current macro : (?)",e)
