import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  const [recording, setRecording] = useState(false);
  const recordingText = recording ? "Recording..." : "Start Recording";
  
  const [playing, setPlaying] = useState(false);
  const playingText = playing ? "Playing..." : "Start Playing";
  
  const [response, setResponse] = useState("");

  async function handle_start_recording(e) {
  setRecording(!recording);
  const response = await invoke("start_recording", {
    payload: {
      ts: Date.now(),
      click: {
        x: e.screenX,
        y: e.screenY,
        button: e.button === 0 ? "left" : "other"
      },
      source: "frontend"
    }
  });
  console.log(response);
  setResponse(response);
};
  
  async function handle_play_macro(e) {
    setPlaying(!playing);
    const res = await invoke("play_macro" , {
      payload: {
        ts: Date.now(),
        click: {
        x: e.screenX,
        y: e.screenY,
        button: e.button === 0 ? "left" : "other"
      },
      source: "frontend"
      }
      
    });
    console.log({res});
  setResponse(res);
}

return (
  <div style={{ padding: 20 }}>
      <h1>Automation UI</h1>

      <button onClick={handle_play_macro} disabled={recording}>
        { playingText }
      </button>
      <button onClick={handle_start_recording} disabled = {playing}>
        { recordingText }
      </button>

      {response && <p>{response}</p>}
    </div>
  );
}


export default App;
