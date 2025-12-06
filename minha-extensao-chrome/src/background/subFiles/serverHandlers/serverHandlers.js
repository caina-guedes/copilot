// Responsável por lidar com as mensagens recebidas do WebSocket e redirecioná-las para as abas corretas

import { enviarMensagemPorURL, enviarMensagemParaAba } from "../tabMessenger/tabMessenger.js";
import {comandoEhValido, validarParametrosDoComando} from "../../../utils/validadorComandos.js";
import { print } from "../../../utils/generalUtils.js";

export function tratarMensagemRecebida(mensagem) {
  print("📨 Mensagem recebida do servidor:", mensagem);
  // preciso validar as mensagens aqui
  if (!comandoEhValido(mensagem.tipo)) {
    print("⚠️ Comando inválido recebido:" ,   mensagem.tipo, 'warn');
    return;
  }
  let [ok , err] = validarParametrosDoComando(mensagem);
  print('o ok é '  , ok)
  print('o err é ' , err)
  if (!ok) {
    print("⚠️ Parâmetros inválidos recebidos: " , err, 'warn');
    return;
  }
  // Envia para a aba com URL específica
  if (mensagem.url) {
    enviarMensagemPorURL(mensagem.url, mensagem);
  } 
  // Envia para a aba com ID específica
  else if (mensagem.id) {
    enviarMensagemParaAba(mensagem.id, mensagem);
  } 
  else if (mensagem.tipo === "comandBackGround") {
    print("Executando comando de background:" , mensagem);
    // Aqui você pode executar o comando de background
  }
  else{
    print("⚠️ Mensagem sem URL ou ID ou comando para o background, será ignorada:", mensagem, 'warn');
  }
}
