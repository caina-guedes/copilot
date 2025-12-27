use tauri::{State};
use crate::app::setup::WsState;
// use futures_util::SinkExt;


 #[tauri::command]
pub async fn start_recording(ws: State<'_, WsState>) -> Result<(), String> {
    println!("Start recording activated!");
    ws.0.send_command("toggleRecording")
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}

// #[tauri::command]
// pub async fn start_recording(
//     ws: State<'_, WsState>
// ) -> Result<(), String> {
//     // let mut socket = ws.0.lock().await;
//     // socket
//     ws.0.send_command("start_recording")
//         // .send(Message::Text(r#"{"command":"start_recording"}"#.into()))
//         .await;
//         // .map_err(|e| e.to_string())?; // converte erro em String e propaga
//         Ok(())
// }
