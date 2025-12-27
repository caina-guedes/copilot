import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  const [response, setResponse] = useState("");
  async function testPing() {
  const response = await invoke("start_recording");
  console.log(response);
}

  async function handleClick() {
    const res = await invoke("play_macro");

    setResponse(res);
  }

  return (
    <div style={{ padding: 20 }}>
      <h1>Automation UI</h1>

      <button onClick={handleClick}>
        play macro
      </button>
      <button onClick={testPing}>
        start recording
      </button>

      {response && <p>{response}</p>}
    </div>
  );
}

export default App;
