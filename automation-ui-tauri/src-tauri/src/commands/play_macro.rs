use tauri::{State};
use crate::app::setup::WsState;
use crate::commands::command_utils::click_structures::{CommandPayload};


#[tauri::command]
pub async fn play_macro(payload: CommandPayload, ws: State<'_, WsState>) -> Result<(), String> {
    println!("Play macro activated!");
    ws.0.send_command("ExecCurrentMacro", payload)
        .await
        .map_err(|e| e.to_string())?;

    println!("Waiting for macro execution to finish...");
    ws.0.wait_for_event("MacroExecutionFinished").await;
    println!("Macro execution finished in the frontend.");
    Ok(())
    // enviar evento pro server via WebSocket
}