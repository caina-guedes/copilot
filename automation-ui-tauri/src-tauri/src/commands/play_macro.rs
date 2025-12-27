use tauri::{State};
use crate::app::setup::WsState;


#[tauri::command]
pub async fn play_macro(ws: State<'_, WsState>) -> Result<(), String> {
    println!("Play macro activated!");
    ws.0.send_command("ExecCurrentMacro")
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
    // enviar evento pro server via WebSocket
}