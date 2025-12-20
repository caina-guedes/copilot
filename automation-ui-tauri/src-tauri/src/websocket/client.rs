use tokio_tungstenite::{connect_async, tungstenite::Message};
use tokio::sync::Mutex;
use futures_util::{SinkExt, StreamExt};
use std::sync::Arc;
use url::Url;
use once_cell::sync::OnceCell;
use serde_json::json;

// Armazena o sender globalmente
pub static WS_SENDER: OnceCell<WsSender> = OnceCell::new();

// Tipo do sender
pub type WsSender = Arc<Mutex<
    futures_util::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        Message
    >
>>;

// Inicializa a conexão e guarda o sender global
pub async fn connect_ws() -> WsSender {
    let url = Url::parse("ws://localhost:8765").unwrap();
    let (ws_stream, _) = connect_async(url).await.expect("Erro ao conectar WS");
    let (mut write, read) = ws_stream.split();
    // envia a primeira mensagem para registrar como "front_end"
    let handshake = json!({"tipo": "front_end" });
    write.send(Message::Text(handshake.to_string())).await
        .expect("Erro ao enviar handshake para o servidor");

    let sender = Arc::new(Mutex::new(write));
    WS_SENDER.set(sender.clone()).ok(); // armazena globalmente
    sender
}

// Função para enviar comando
pub async fn send_command(cmd: &str) {
    if let Some(sender) = WS_SENDER.get() {
        let msg = json!({ "command": cmd }).to_string();
        let mut locked = sender.lock().await;
        if let Err(e) = locked.send(Message::Text(msg)).await {
            eprintln!("Erro ao enviar comando WS: {:?}", e);
        }
    } else {
        eprintln!("WS não inicializado!");
    }
}
