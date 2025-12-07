import { useState } from "react";
import reactLogo from "./assets/react.svg";
import { invoke } from "@tauri-apps/api/tauri";
import "./App.css";

function App() {
  return (
    <div style={{ padding: 20 }}>
      <h1>Automation UI</h1>
      <p>App rodando via System Tray.</p>
      <p>Feche a janela e tente usar o ícone.</p>
    </div>
  );
}



export default App
