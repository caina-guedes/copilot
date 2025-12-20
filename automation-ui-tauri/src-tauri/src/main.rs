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
// use std::process::Command;
use crate::window::events::handle_window_event;
use crate::commands::{hello, ping,play_macro,record};
use tauri::{Manager};

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
        .run(tauri::generate_context!())
        .expect("erro ao rodar app");
}
