// use sysinfo::{ProcessExt, SystemExt, Signal, System};
use std::process::Command;

pub fn kill_port(port: u16) {
    // Monta o comando para matar o processo na porta
    let output = Command::new("sh")
        .arg("-c")
        .arg(format!("sudo fuser -k {}/tcp", port))
        .output()
        .expect("Falha ao executar o comando para limpar a porta");

    if !output.status.success() {
        eprintln!("Erro ao matar o processo na porta {}: {:?}", port, output);
    } else {
        println!("Porta {} liberada com sucesso.", port);
    }
}

pub fn start_server() {
    // inicia o server.py
    kill_port(8765); // libera a porta 8765 antes de iniciar o servidor
    println!("Starting server...");
    let _ = Command::new("python3")
        .arg("/home/cain/Documentos/automacaoPythonJs/PythonServer/server.py") // caminho pro seu server.py
        .spawn()
        .expect("Falha ao iniciar server.py");
    println!("server started");}

pub fn start_watcher() {
    // inicia o watcher.py
    println!("Starting watcher...");
    let _ = Command::new("python3")
        .arg("/home/cain/Documentos/automacaoPythonJs/PythonSistemAutomation/main.py") // caminho pro seu watcher.py
        .spawn()
        .expect("Falha ao iniciar watcher.py");
    println!("watcher started");
}
