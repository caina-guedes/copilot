import comandos from '../shared_config/comandos.json';

export function comandoEhValido(comando) {
    // Verifica se o comando existe no esquema de comandos
    // Verifica se o comando tem permissão de usuário
    // se tiver os dois retorna true
    // se não tiver retorna false


  if(!comandos.comandos.hasOwnProperty(comando)){
    console.warn("⚠️ Comando inválido recebido:", comando);
    return false
  };
    // Verifica se o comando tem permissão de usuário
  const permUsuario = comandos.comandos[comando]["permissao_usuario"] === true; // evita indefined e só autoriza se for true no modelo
  if(!permUsuario){
    console.warn("⚠️  ", comando, " não tem permissão de usuário");

    return false
  };

  console.log("✅ Comando válido recebido:", comando);
  return true
}

export function validarParametrosDoComando(recebido) {
  console.log("começando a validação dos dados do comando")
  const tipo = recebido.tipo;
  const esquema = comandos.comandos[tipo];

  if (!esquema) {
    return [false, `Comando '${tipo}' não existe.`];
  }

  const esperados = esquema.parametros || {};
  const recebidos = recebido.dados || {};

  for (const chave in esperados) {
    const definicao = esperados[chave];
    const tipoEsperado = typeof definicao === "object" ? definicao.tipo : definicao;

    const valor = recebidos[chave];

    if (valor === undefined) {
      return [false, `Parâmetro '${chave}' está faltando.`];
    }

    if (tipoEsperado === "string" && typeof valor !== "string") {
      return [false, `Parâmetro '${chave}' deveria ser uma string.`];
    }

    if (tipoEsperado === "object" && typeof valor !== "object") {
      return [false, `Parâmetro '${chave}' deveria ser um objeto.`];
    }

    // Adicione aqui outros tipos se quiser
  }

  return [true, "Comando válido."];
}
