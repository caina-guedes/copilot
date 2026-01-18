use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tokio::sync::Notify;
use once_cell::sync::OnceCell;


pub static WS_EVENTS: OnceCell<WsEvents> = OnceCell::new();

// pub let events = WsEvents::new();
// WS_EVENTS.set(events.clone()).ok();

pub fn init_ws_events() {
    let events = WsEvents::new();
    WS_EVENTS.set(events).ok();
}


#[derive(Clone)]
pub struct WsEvents {
    notifiers: Arc<Mutex<HashMap<String, Arc<Notify>>>>,
}

impl WsEvents {
    pub fn new() -> Self {
        Self {
            notifiers: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn notify_event(&self, event: &str) {
        if let Some(n) = self.notifiers.lock().unwrap().get(event) {
            n.notify_waiters();
        }
    }

    pub async fn wait_for(&self, event: &str) {
        let notify = {
            let mut map = self.notifiers.lock().unwrap();
            map.entry(event.to_string())
                .or_insert_with(|| Arc::new(Notify::new()))
                .clone()
        };
        println!("Waiting for WS event: {}", event);
        notify.notified().await;
        println!("WS event received: {}", event);
    }
}
