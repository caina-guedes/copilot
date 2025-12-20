use tauri::{WindowEvent, Window, AppHandle,Manager};

use crate::tray::tray::toggle_window;


pub fn handle_window_event(app: AppHandle, window: Window, event: WindowEvent) {
    match event {
        WindowEvent::CloseRequested { api, .. } => {
            // impede fechar de verdade
            api.prevent_close();
            
            // esconde a janela
            window.hide().unwrap();
            toggle_window(&app);
        }
        WindowEvent::Focused(focused) => {
            if focused {
                app.emit_all("janela_mostrada", {}).ok();
            }
        }
        
        _ => {}
    }
}
