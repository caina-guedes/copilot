
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
// extrutura dos eventos WS
// -------------------------
use crate::websocket::events::{WS_EVENTS, init_ws_events};
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

    pub async fn wait_for_event(&self, event: &str) {
    if let Some(events) = WS_EVENTS.get() {
        events.wait_for(event).await;
    }
}

}

// -------------------------
// Inicializa conexão WS e armazena globalmente
// -------------------------
pub async fn connect_ws() -> Result<WsSender, WsError> {
    init_ws_events();
    let url = Url::parse("ws://localhost:8765").unwrap();
    let (ws_stream, _) = connect_async(url).await?;
    let (write, mut read) = ws_stream.split();

    let sender = WsSender(Arc::new(Mutex::new(write)));

    // spawn task para ler mensagens (apenas para evitar bloqueio)
    tokio::spawn(async move {
        while let Some(msg) = read.next().await {
            match msg {
                Ok(Message::Text(txt)) => {
                    println!("WS recv: {}", txt);

                    if let Ok(json) = serde_json::from_str::<Value>(&txt) {
                        if let Some(event) = json.get("statusUpdate").and_then(|v| v.as_str()) {
                            if let Some(events) = WS_EVENTS.get() {
                                events.notify_event(event);
                            }
                        }
                    }
                },
                Ok(_) => {},
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

