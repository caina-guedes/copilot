
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tokio_tungstenite::tungstenite::Error as WsError;
use futures_util::{SinkExt, StreamExt};
use once_cell::sync::OnceCell;
use serde_json::{json,Value};
use tokio::sync::Mutex;
use std::sync::Arc;
use url::Url;
use crate::commands::command_utils::click_structures::CommandPayload;
// -------------------------
// Global WS sender
// -------------------------
pub static WS_SENDER: OnceCell<WsSender> = OnceCell::new();

// -------------------------
// Tipo do sender
// -------------------------
#[derive(Clone)]
pub struct WsSender(pub Arc<Mutex<
    futures_util::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        Message
    >
>>);


impl WsSender {

    // -------------------------
    // Métodos do WsSender
    // -------------------------

    /// Envia qualquer JSON como mensagem WS
    pub async fn send_message(&self, msg: Value) -> Result<(), WsError>{
        println!("Enviando mensagem WS: {}", msg);
        let mut locked = self.0.lock().await;
        locked.send(Message::Text(msg.to_string())).await 

    }

    pub async fn send_command(&self, cmd: &str, payload: CommandPayload) -> Result<(), WsError> {
        self.send_message(json!({"command": cmd, "payload": payload})).await
    }
    // Envia comando no formato {"command": "..."}
    // pub async fn send_command(&self, cmd: &str) {
    //     self.send_message(json!({"command": cmd})).await;
    // }
}

// -------------------------
// Inicializa conexão WS e armazena globalmente
// -------------------------
pub async fn connect_ws() -> Result<WsSender, WsError> {
    let url = Url::parse("ws://localhost:8765").unwrap();
    let (ws_stream, _) = connect_async(url).await?;
    let (write, mut read) = ws_stream.split();

    let sender = WsSender(Arc::new(Mutex::new(write)));

    // spawn task para ler mensagens (apenas para evitar bloqueio)
    tokio::spawn(async move {
        while let Some(msg) = read.next().await {
            match msg {
                Ok(m) => println!("WS recv: {:?}", m),
                Err(e) => {
                    eprintln!("WS read error: {:?}", e);
                    break;
                }
            }
        }
    });
    // envia handshake inicial
    sender.send_message(json!({"tipo": "front_end"})).await?;

    // armazena globalmente
    WS_SENDER.set(sender.clone()).ok();

    Ok(sender)
}


// -------------------------
// Função de conveniência usando global
// -------------------------
pub async fn send_command_global(cmd: &str, payload: CommandPayload) -> Result<(), WsError> {
    println!("send_command_global: {}", cmd);
    if let Some(sender) = WS_SENDER.get() {
        sender.send_command(cmd, payload).await
    } else {
        eprintln!("WS não inicializado!");
        Err(WsError::AlreadyClosed)
    }
}

