use tauri::{
    AppHandle,
    CustomMenuItem,
    SystemTray,
    SystemTrayEvent,
    SystemTrayMenu,
    Manager,
};

pub fn create_tray() -> SystemTray {
    let show_hide = CustomMenuItem::new("toggle".to_string(), "Esconder");
    let quit = CustomMenuItem::new("quit".to_string(), "Fechar");

    let menu = SystemTrayMenu::new()
        .add_item(show_hide)
        .add_item(quit);

    SystemTray::new().with_menu(menu)
}

pub fn handle_tray_event(app: &AppHandle, event: SystemTrayEvent) {
    match event {
        SystemTrayEvent::MenuItemClick { id, .. } => {
            match id.as_str() {
                "toggle" => toggle_window(app),
                "quit" => {
                    app.exit(0);
                }
                _ => {}
            }
        }
        _ => {}
    }
}

pub fn toggle_window(app: &AppHandle) {
    let window = app.get_window("main").unwrap();

    if window.is_visible().unwrap() {
        window.hide().unwrap();
        app.tray_handle()
            .get_item("toggle")
            .set_title("Mostrar")
            .unwrap();

    } else {
        window.show().unwrap();
        window.set_focus().unwrap();
        app.tray_handle()
            .get_item("toggle")
            .set_title("Esconder")
            .unwrap();

    }
}
