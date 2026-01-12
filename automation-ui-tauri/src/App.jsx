import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  const [recording, setRecording] = useState("");
  const [playing, setPlaying] = useState("");
  const [response, setResponse] = useState("");


  async function handle_start_recording(e) {
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
    setPlaying(res);
  setResponse(res);
}

return (
  <div style={{ padding: 20 }}>
      <h1>Automation UI</h1>

      <button onClick={handle_play_macro}>
        play macro
      </button>
      <button onClick={handle_start_recording}>
        start recording
      </button>

      {response && <p>{response}</p>}
    </div>
  );
}


export default App;
