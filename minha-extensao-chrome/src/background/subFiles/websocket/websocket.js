// Responsável por estabelecer e manter a conexão com o WebSocket
import { tratarMensagemRecebida } from '../serverHandlers/serverHandlers.js';
console.log("passei do import no websocket" )
let socket = null;
let tentandoReconectar = false;
const reconnectTimeout = 2000;

let tentativasDeReconexao = 0;


export function conectarWebSocket() {
  socket = new WebSocket("ws://localhost:8765");
  console.log("🔌 Tentando conectar ao WebSocket...");

  socket.onopen = () => {
    console.log("✅ Conectado ao WebSocket");
    tentandoReconectar = false;
    tentativasDeReconexao = 0; // Reinicia o contador de tentativas
    socket.send(JSON.stringify({ tipo: "extensao" }));
  };

  socket.onmessage = (event) => {
    try {
      const mensagem = JSON.parse(event.data);
      tratarMensagemRecebida(mensagem);
    } catch (err) {
      console.error("❌ Erro ao processar mensagem recebida:", err);
    }
  };

  socket.onclose = () => {
    console.warn("🔌 Conexão encerrada. Reconnectando em 2s...");
    tentarReconectar();
  };

  socket.onerror = (err) => {
    console.error("❌ Erro na conexão WebSocket:", err.message);
    tentarReconectar();
  };
}
function tentarReconectar() {
  if (!tentandoReconectar) {
    tentandoReconectar = true;
    tentativasDeReconexao++;
    console.warn(`🔁 Tentativa de reconexão #${tentativasDeReconexao} em 2s...`);
    setTimeout(() => {
      tentandoReconectar = false; // Permitir novas tentativas
      conectarWebSocket();
    }, reconnectTimeout);
  }
}

export function enviarPingParaServidor() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ tipo: "ping" }));
    console.log("🔄 Ping enviado ao servidor WebSocket.");
    return true;
  } else {
    console.warn("⚠️ WebSocket não está conectado. Tentando reconectar...");
    conectarWebSocket();
    return false;
  }
}

