// use once_cell::sync::OnceCell;
// use std::sync::Mutex;
// use tokio::net::TcpStream;
// use futures_util::SinkExt;
// use tokio_tungstenite::tungstenite::Message;



// static WS: OnceCell<Mutex<tokio_tungstenite::WebSocketStream<TcpStream>>> = OnceCell::new();

// pub fn send_command(cmd: &str) {
//     let msg = serde_json::json!({
//         "command": cmd
//     });

//     if let Some(ws) = WS.get() {
//         let _ = ws.lock().unwrap().send(Message::Text(msg.to_string()));
//     }
// }
