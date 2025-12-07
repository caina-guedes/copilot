import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  return (
    <div style={{ padding: 20 }}>
      <h1>Tauri is working ✅</h1>
      <button>Call backend</button>
    </div>
  )
}

export default App
