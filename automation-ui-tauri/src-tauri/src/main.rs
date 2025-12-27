// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// const DEV_MODE: bool = cfg!(debug_assertions);
mod app;
mod commands;
mod process;
mod tray;
mod websocket;
mod window;

use tray::tray::{create_tray, handle_tray_event};
use app::setup::setup_app;
use process::launcher::AppProcesses;
// use std::process::Command;
use crate::window::events::handle_window_event;
use crate::commands::{hello, ping,play_macro,record};
use tauri::{Manager,RunEvent};

fn main() {
    // Itens do menu
    let tray = create_tray();
    
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![hello::say_hello,
            ping::ping,
            play_macro::play_macro,
            record::start_recording ])
        
        .setup(|app| setup_app(app))

        .system_tray(tray)

        .on_system_tray_event(|app, event| {
            handle_tray_event(app, event);
        })
        
        .on_window_event(|event| {
            handle_window_event(event.window().app_handle(), event.window().clone(), event.event().clone());
        })
        // .on_exit(|app_handle| {
        //     // pega o estado com os processos
        //     let processes = app_handle.state::<AppProcesses>();
        //     processes.stop_all();
        //     println!("Server e watcher finalizados ao fechar o programa");
        // })
        .build(tauri::generate_context!())
    .expect("error while building tauri application")
    .run(|app_handle, event| {
        match event {
            RunEvent::Exit => {
                // AQUI é o fechamento REAL do app
                println!("App está encerrando");

                if let Some(processes) = app_handle.try_state::<AppProcesses>() {
                    // let mut processes = processes.inner().lock().unwrap();
                    processes.stop_all();
                }
            }
            _ => {}
        }
    });
        // .run(tauri::generate_context!())
        // .expect("erro ao rodar app");

}
