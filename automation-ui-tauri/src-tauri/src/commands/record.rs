use tauri::{State};
use crate::app::setup::WsState;
use tokio_tungstenite::tungstenite::Message;
 use futures_util::SinkExt;

#[tauri::command]
pub async fn start_recording(
    ws: State<'_, WsState>
) -> Result<(), String> {
    let mut socket = ws.0.lock().await;
    socket
        .send(Message::Text(r#"{"command":"start_recording"}"#.into()))
        .await
        .map_err(|e| e.to_string())?; // converte erro em String e propaga
        Ok(())
}
