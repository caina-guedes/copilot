// use sysinfo::{ProcessExt, SystemExt, Signal, System};
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::net::TcpStream;
use std::thread;
use std::time::Duration;


#[derive(Clone)]
pub struct AppProcesses {
    inner: Arc<Mutex<InnerProcesses>>,
}

struct InnerProcesses {
    server: Option<Child>,
    watcher: Option<Child>,
}

impl AppProcesses {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(Mutex::new(InnerProcesses {
                server: None,
                watcher: None,
            })),
        }
    }

    pub fn start_server(&self) {
        let mut processes = self.inner.lock().unwrap();
        kill_port(8765); // libera a porta antes de iniciar
        let child = Command::new("python3")
            .arg("/home/cain/Documentos/automacaoPythonJs/PythonServer/server.py")
            .spawn()
            .expect("Erro ao iniciar o server");
        processes.server = Some(child);
    }

    pub fn wait_for_server(&self, host: &str, port: u16) {
    let addr = format!("{}:{}", host, port);
    while TcpStream::connect(&addr).is_err() {
        println!("Esperando server em {}...", addr);
        thread::sleep(Duration::from_millis(200));
    }
    println!("Server pronto em {}", addr);
}

    pub fn start_watcher(&self) {
        // Antes de iniciar, garante que o server está pronto
        self.wait_for_server("127.0.0.1", 8765);

        let mut processes = self.inner.lock().unwrap();
        let child = Command::new("python3")
            .arg("/home/cain/Documentos/automacaoPythonJs/PythonSistemAutomation/main.py")
            .spawn()
            .expect("Erro ao iniciar o watcher");
        processes.watcher = Some(child);
    }

    pub fn stop_server(&self) {
        let mut processes = self.inner.lock().unwrap();
        if let Some(server) = &mut processes.server {
            let _ = server.kill();
            let _ = server.wait();
        }
        processes.server = None;
    }

    pub fn stop_watcher(&self) {
        let mut processes = self.inner.lock().unwrap();
        if let Some(watcher) = &mut processes.watcher {
            let _ = watcher.kill();
            let _ = watcher.wait();
        }
        processes.watcher = None;
    }

    pub fn stop_all(&self) {
        let mut processes = self.inner.lock().unwrap();
        if let Some(server) = &mut processes.server {
            let _ = server.kill();
            let _ = server.wait();
        }
        processes.server = None;

        if let Some(watcher) = &mut processes.watcher {
            let _ = watcher.kill();
            let _ = watcher.wait();
        }
        processes.watcher = None;
    }
}

pub fn kill_port(port: u16) {
    let output = Command::new("sh")
        .arg("-c")
        .arg(format!("sudo fuser -k {}/tcp", port))
        .output()
        .expect("Falha ao limpar a porta");

    if !output.status.success() {
        eprintln!("Erro ao matar o processo na porta {}: {:?}", port, output);
    } else {
        println!("Porta {} liberada com sucesso.", port);
    }
}



// use std::process::{Child, Command};

// pub struct AppProcesses {
//     server: Option<Child>,
//     watcher: Option<Child>,
// }

// impl AppProcesses {
//     pub fn new() -> Self {
//         Self { server: None, watcher: None }
//     }

//     pub fn start_server(&mut self) {
//         kill_port(8765); // libera a porta 8765 antes de iniciar o servidor
//         let child = Command::new("python3")
//             .arg("/home/cain/Documentos/automacaoPythonJs/PythonServer/server.py") // caminho pro seu server.py
//             .spawn()
//             .expect("Erro ao iniciar o server");
//         self.server = Some(child);
//     }

//     pub fn start_watcher(&mut self) {
//         let child = Command::new("python3")
//             .arg("/home/cain/Documentos/automacaoPythonJs/PythonSistemAutomation/main.py") // caminho pro seu watcher.py
//             .spawn()
//             .expect("Erro ao iniciar o watcher");
//         self.watcher = Some(child);
//     }

//     pub fn stop_server(&mut self) {
//         if let Some(server) = &mut self.server {
//             let _ = server.kill();
//             let _ = server.wait(); // espera o processo terminar
//         }
//     }

//     pub fn stop_watcher(&mut self) {
//         if let Some(watcher) = &mut self.watcher {
//             let _ = watcher.kill();
//             let _ = watcher.wait(); // espera o processo terminar
//         }
//     }
//     pub fn stop_all(&mut self) {
//         self.stop_server();
//         self.stop_watcher();
//     }
//     // fn stop_all(&mut self) {
//     //     if let Some(server) = &mut self.server {
//     //         let _ = server.kill();
//     //     }
//     //     if let Some(watcher) = &mut self.watcher {
//     //         let _ = watcher.kill();
//     //     }
//     // }
// }

// pub fn kill_port(port: u16) {
//     // Monta o comando para matar o processo na porta
//     let output = Command::new("sh")
//         .arg("-c")
//         .arg(format!("sudo fuser -k {}/tcp", port))
//         .output()
//         .expect("Falha ao executar o comando para limpar a porta");

//     if !output.status.success() {
//         eprintln!("Erro ao matar o processo na porta {}: {:?}", port, output);
//     } else {
//         println!("Porta {} liberada com sucesso.", port);
//     }
// }

// pub fn start_server() -> Child {
//     // inicia o server.py
//     kill_port(8765); // libera a porta 8765 antes de iniciar o servidor
//     println!("Starting server...");
//     let _ = Command::new("python3")
//         .arg("/home/cain/Documentos/automacaoPythonJs/PythonServer/server.py") // caminho pro seu server.py
//         .spawn()
//         .expect("Falha ao iniciar server.py");
//     println!("server started");}

// pub fn start_watcher() -> Child {
//     // inicia o watcher.py
//     println!("Starting watcher...");
//     let _ = Command::new("python3")
//         .arg("/home/cain/Documentos/automacaoPythonJs/PythonSistemAutomation/main.py") // caminho pro seu watcher.py
//         .spawn()
//         .expect("Falha ao iniciar watcher.py");
//     println!("watcher started");
// }
