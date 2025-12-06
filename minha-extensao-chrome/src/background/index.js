// index.js
// Arquivo principal que conecta todos os módulos do background
import { conectarWebSocket, enviarPingParaServidor } from "./websocket/websocket.js";
import { iniciarMonitoramentoDasAbas } from './subFiles/pinger/pinger.js';
import {configurarListenersDoChrome} from "./subFiles/chromeEvents/chromeEvents.js";
// console.log("passei dos imports no index")

// Configura os listeners do Chrome
configurarListenersDoChrome(); 

// Inicia a conexão WebSocket com o servidor
conectarWebSocket();

// Inicia o sistema de ping para monitorar abas ativas e injetáveis
iniciarMonitoramentoDasAbas(); // padrão: 15 segundos


  
setInterval(() => {
    console.log('foi carregado')
},6000)