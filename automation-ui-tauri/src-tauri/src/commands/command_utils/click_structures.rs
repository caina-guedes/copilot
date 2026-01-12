use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize, Serialize)]
pub struct ClickInfo {
    pub x: i32,
    pub y: i32,
    pub button: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct CommandPayload {
    pub ts: u64,
    pub click: ClickInfo,
    pub source: String,
}
