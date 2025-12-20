use tauri::{App, Manager };
use crate::process::launcher::{start_server, start_watcher};
use crate::websocket::client::{connect_ws,WsSender};

pub struct WsState(pub WsSender);

pub fn setup_app(app: &App) -> Result<(), Box<dyn std::error::Error>> {
    let app_handle = app.handle(); // cria um AppHandle 'static
    if cfg!(debug_assertions) {
        start_server();
        start_watcher();
    };

    println!("setup_app foi executado!");
    tauri::async_runtime::spawn(async move {
        let ws = connect_ws().await;
        app_handle.manage(WsState(ws));
    });
    println!("websocket inicializado!");

    // let handle = app.handle();

    // let handle2 = handle.clone();
    // // app.listen_global("tauri://ready", move |_| {

    //     handle.listen_global("janela_escondida", move |_| {
    //         println!("cheguei no codigo de esconder a janela");
    //         let tray = handle2.tray_handle().get_item("toggle");
    //         tray.set_title("Mostrar").ok();
    //     });
    // });
    Ok(())
}