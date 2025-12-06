import json
from pathlib import Path
json_path = (Path(__file__).resolve().parent / "../minha-extensao-chrome/src/shared_config/comandos.json").resolve()
from sharedResources.generalUtils.aprint import aprint
with open(json_path, encoding="utf-8") as f:
        ESQUEMA_COMANDOS = json.load(f)["comandos"]
# try:
#     with open("minha-extensao-chrome/src/shared_config/comandos.json", encoding="utf-8") as f:
#         ESQUEMA_COMANDOS = json.load(f)["comandos"]
# except:
#     with open("../minha-extensao-chrome/src/shared_config/comandos.json", encoding="utf-8") as f:
#         ESQUEMA_COMANDOS = json.load(f)["comandos"]

TIPOS_ACEITOS = {
    "string": {"validador": lambda v: isinstance(v, str), "tem_propriedades": False},
    "object": {"validador": lambda v: isinstance(v, dict), "tem_propriedades": True},
    "list":   {"validador": lambda v: isinstance(v, list), "tem_propriedades": True},
    # Futuramente:
    # "number": {"validador": lambda v: isinstance(v, (int, float)), "tem_propriedades": False},
    # "boolean": {"validador": lambda v: isinstance(v, bool), "tem_propriedades": False},
    # "array": {"validador": lambda v: isinstance(v, list), "tem_propriedades": False},
    # "null": {"validador": lambda v: v is None, "tem_propriedades": False},

}

def validador_comando(comando: dict, comandos_json = ESQUEMA_COMANDOS) -> tuple[bool, str]:
    print("comecei a funçãaao")
    def validar_parametros(parametros_definidos, parametros_recebidos, path=''):
        for nome, definicao in parametros_definidos.items():
            if nome not in parametros_recebidos:
                return False, f"Parâmetro obrigatório '{path + nome}' não foi fornecido."
            
            valor = parametros_recebidos[nome]
            tipo = definicao.get("tipo")

            tipo_info = TIPOS_ACEITOS.get(tipo)
            if not tipo_info:
                return False, f"Tipo de parâmetro '{tipo}' em '{path + nome}' não é suportado."

            if not tipo_info["validador"](valor):
                return False, f"Parâmetro '{path + nome}' deve ser do tipo {tipo}."

            if tipo_info["tem_propriedades"]:
                # Se o tipo tem propriedades, verificamos se são definidas
                
                if "propriedades" in definicao:
                    propriedades = definicao["propriedades"]
                else:
                    return False, f"Parâmetro '{path + nome}' do tipo '{tipo}' não tem propriedades definidas."
                
                if tipo == "list":
                    if not isinstance(valor, list):
                        return False, f"Parâmetro '{path + nome}' deve ser uma lista."
                    for i, item in enumerate(valor):
                        valido, erro = validar_parametros(propriedades, item, path + f"{nome}[{i}].")
                        if not valido:
                            return False, erro
                else:
                    valido, erro = validar_parametros(propriedades, valor, path + nome + ".")
                    if not valido:
                        return False, erro
                    
            # if tipo == "string":
            #     if not isinstance(valor, str):
            #         return False, f"Parâmetro '{path + nome}' deve ser do tipo string."

            # elif tipo == "list":
            #     if not isinstance(valor, list):
            #         return False, f"Parâmetro '{path + nome}' deve ser uma lista."
            #     # Se tiver definição de itens internos
            #     if "propriedades" in definicao:
            #         for i, item in enumerate(valor):
            #             valido, erro = validar_parametros(definicao["propriedades"], item, path + f"{nome}[{i}].")
            #             if not valido:
            #                 return False, erro

            # elif tipo == "object":
            #     if not isinstance(valor, dict):
            #         return False, f"Parâmetro '{path + nome}' deve ser um objeto (dict)."
            #     propriedades = definicao.get("propriedades")
            #     if propriedades:
            #         valido, erro = validar_parametros(propriedades, valor, path + nome + ".")
            #         if not valido:
            #             return False, erro

            # else:
            #     return False, f"Tipo de parâmetro '{tipo}' em '{path + nome}' não é suportado."

        return True, ""

    if not isinstance(comando, dict):
        return False, "Comando deve ser um dicionário e foi: " + str(type(comando))

    
    tipo = comando.get("tipo")
    parametros = comando.get("parametros")

    if  tipo is None or parametros is None:
        return False, "Comando deve conter os campos 'tipo' e 'parametros'."

    comando_def = comandos_json.get(tipo)
    if not comando_def:
        return False, f"Comando '{tipo}' não encontrado no JSON de definição."

    parametros_definidos = comando_def.get("parametros", {})
    valido, erro = validar_parametros(parametros_definidos, parametros)
    if not valido:
        return False, erro

    return True, "Comando válido."












def validar_comando(recebido: dict) -> tuple[bool, str]:
    tipo = recebido.get("tipo")
    if tipo not in ESQUEMA_COMANDOS:
        return False, f"Comando '{tipo}' não existe."

    parametros_esperados = ESQUEMA_COMANDOS[tipo].get("parametros", {})
    parametros_recebidos = recebido.get("dados", {})

    for chave, tipo_esperado in parametros_esperados.items():
        if chave not in parametros_recebidos:
            # print(f"dentro de ")
            return False, f"Parâmetro '{chave}' está faltando."
        

        if isinstance(tipo_esperado, dict):  # tipo: { "tipo": "object" }
            tipo_str = tipo_esperado.get("tipo")
        else:
            tipo_str = tipo_esperado  # fallback

        if tipo_str == "string" and not isinstance(parametros_recebidos[chave], str):
            return False, f"Parâmetro '{chave}' deveria ser uma string."

        elif tipo_str == "object" and not isinstance(parametros_recebidos[chave], dict):
            return False, f"Parâmetro '{chave}' deveria ser um objeto (dict)."

        # Adicione aqui mais tipos se quiser (number, array, etc)

    return True, "Comando válido."
