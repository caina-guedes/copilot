use crate::websocket::client::send_command;
#[tauri::command]
pub async fn play_macro() {
    println!("Play macro activated!");
    send_command("ExecCurrentMacro")
    .await;
    // enviar evento pro server via WebSocket
}