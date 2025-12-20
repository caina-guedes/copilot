#[tauri::command]
pub async fn say_hello(name: String) -> String {
    format!("Olá, {name}")
}
