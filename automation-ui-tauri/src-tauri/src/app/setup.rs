use tauri::{App, Manager };
use crate::process::launcher::{AppProcesses};
use crate::websocket::client::{connect_ws,WsSender,send_command_global};
use crate::commands::command_utils::click_structures::{CommandPayload, ClickInfo};
// use std::process::Child;
// use tokio_tungstenite::tungstenite::Message;
pub struct WsState(pub WsSender);
// use serde_json::json;

pub fn setup_app(app: &App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle(); // cria um AppHandle 'static
    if cfg!(debug_assertions) {
        let processes = AppProcesses::new();
        // processes.start_server();
        // processes.start_watcher();
        app_handle.manage(processes);
    };

    println!("setup_app sendo executado!");
    tauri::async_runtime::spawn(async move {
     match connect_ws().await {
        Ok(ws) => {
            println!("WS conectado com sucesso!");
            // envia mensagem inicial
            if let Err(e) = send_command_global("Conexão do front-end estabelecida", CommandPayload { ts: 0, click: ClickInfo { x: 0, y: 0, button: "left".into() }, source: "front_end".into() }).await {
                eprintln!("Erro ao enviar mensagem inicial: {:?}", e);
            }
            // registra WSState no Tauri
            println!("registrando o WsState no Tauri");
            app_handle.manage(WsState(ws));
            println!("WsState registrado com sucesso!");
        }
        Err(e) => eprintln!("Falha ao conectar WS: {:?}", e),
    
    }});

    println!("websocket inicializado!");

    Ok(())
}