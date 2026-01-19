import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  const [response, setResponse] = useState("");
  const [mode, setMode] = useState("idle"); // "idle" | "playing" | "recording"

  const recordingText = mode === "recording" ? "Recording..." : "Start Recording";
  const playingText = mode === "playing" ? "Playing..." : "Start Playing";
  




  const validTransitions = {
  idle: ["playing", "recording"],
  playing: ["idle", "error"],
  recording: ["idle", "error"],
  error: ["idle"]
};


  function setModeSafe(next) {
    console.log("Attempting to set mode to:", next);
    console.log("Current mode is:", mode);
  setMode(prev => {
    if (!validTransitions[prev].includes(next)) {
      console.error(`Invalid transition: ${prev} → ${next}`);
      return prev;
    }
    console.log(`MODE: ${prev} → ${next} is okay.`);
    return next;
  });
}


  async function handle_start_recording(e) {
  if (mode === "playing"){
    console.log("Cannot start recording while playing.");
    return;
  }
  console.log("Toggling recording mode. Current mode:", mode);
  const start = Date.now();
  console.log("Invoking start_recording the time is: ", start);
  setModeSafe(mode === "recording" ? "idle" : "recording");

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
  console.log("Response from start_recording:", response);
  console.log("the time it took was: ", Date.now() - start, " ms");
  console.log(response); 
  setResponse(response);
};
  
  async function handle_play_macro(e) {
    if (mode === "playing" || mode === "recording"){
      console.log("Already playing or recording, action ignored.");
      return;
    } ;

    setModeSafe("playing");

    const start = Date.now();
    let end = null;
    try {
      console.log("Invoking play_macro the time is ...", start);
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
      end = Date.now();
      console.log(`play_macro took ${end - start} ms`);
      console.log("Response from play_macro:", res);
      setResponse(res);
    }
    catch (error) {
      console.error("Error during play_macro invocation:", error);
      setResponse(`Error: ${error.message}`);
    }
    finally {
      console.log("Setting mode back to idle. it took ", Date.now() - start, " ms");
      setModeSafe("idle");
    }
}

return (
  <div style={{ padding: 20 }}>
      <h1>Automation UI</h1>

      <button onClick   = { handle_play_macro} 
              disabled  = { mode !== "idle"}
              className = { `btn ${mode !== "idle" ? "btn-disabled" : ""}`}
      >
        { playingText }
      </button>

      <button onClick   = { handle_start_recording } 
              disabled  = { mode === "playing" }
              className = { `btn ${mode === "playing" ? "btn-disabled" : ""}`}>
        { recordingText }
      </button>

      {response && <p>{response}</p>}
    </div>
  );
}


export default App;
