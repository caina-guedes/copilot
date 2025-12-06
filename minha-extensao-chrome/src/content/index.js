// console.log("🚀 Content script carregado!");
import {TIPOS_MENSAGEM} from "../shared_config/constants.js";

// esse import será usado pelos observadores, não pelo content em si
import {observerUtils} from "./subFiles/observerUtils/observerUtils.js";
// content.js

if (window.__script_injetado_content) {
  console.warn('⚠️ content.js já foi injetado e tentaram injetar de novo .');
} else {



function showToast(msg) {
    const div = document.createElement("div");
    div.innerText = msg;
    Object.assign(div.style, {
      position: "fixed", bottom: "20px", right: "20px", background: "#333", color: "#fff",
      padding: "10px 15px", borderRadius: "8px", zIndex: 9999
    });
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
  }

async function digitarTexto(selector, texto) {
    const el = document.querySelector(selector);
    if (el) {
      el.focus();
      el.value = ""; // Limpa o campo antes de digitar
      for (char of texto) {
        el.value += char;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        await new Promise(r => setTimeout(r, 50)); // simula digitação
      }
    }
      else{
        console.log("elemento não encontrado")
      }
    }


// content-script.js ou background.js
async function executeSteps(steps) {
    // Verifica se o steps é um array
    for (const step of steps) {
      try {
        console.log("Executando passo:", step);
        showToast(JSON.stringify(step) || "[passo]");
        switch (step.action) {
          case "alert":
            alert(step.message || "[alert]");
            break;
          case "click":
            document.querySelector(step.selector)?.click();
            break;
  
          case "type":
            await digitarTexto(step.selector, step.text);
            break;
  
          case "wait":
            await new Promise(r => setTimeout(r, step.time));
            break;
  
          case "log":
            console.log(step.message || "[log]");
            break;
  
          default:
            console.warn("Ação desconhecida:", step.action);
        }
      } catch (err) {
        console.error("Erro no passo:", step, err);
      }
    }
  }

  


chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

    console.log("📨 Comando recebido no content.js:", message);
    message.tipo = message.tipo.toLowerCase();
    if (message.tipo === "alerta") {
        // Realiza a ação que você deseja na página da aba
        alert(message.mensagem);  // Exibe um alerta na página da aba
        sendResponse({ status: "sucesso", mensagem: "Mensagem recebida com sucesso!" });
        
    }
    else if (message.tipo === "execute_steps") {
        executeSteps(message.dados.steps)
        .then(() => sendResponse({ status: "completo" }))
        .catch(err => sendResponse({ status: "erro", erro: err.message }));
         }
    else if (message.tipo === TIPOS_MENSAGEM.PING) {
        console.log("📡 recebi ping do background");
        sendResponse({ tipo: TIPOS_MENSAGEM.PONG });
         }
    else if (message.tipo === "log") {
        console.log(message.mensagem || "[log]");
        sendResponse({ status: "ok" });
         }
    
    else {
        console.log(message)
        }
    return true; // mantém canal aberto
    //return true; // Para manter sendResponse assíncrono, se necessário
    // outros comandos aqui...

    sendResponse({ status: "ok" });
});

setInterval(() => {
    console.log("📍 content.js ainda está ativo nesta aba:", window.location.href);
  }, 10000); // 10 segundos
  
// const script = document.createElement("script");
// script.textContent = `
//   function minhaFuncaoNaPagina() {
//     console.log("Executando no contexto da página!");
//   }
//   window.minhaFuncaoNaPagina = minhaFuncaoNaPagina;
// `;
// document.documentElement.appendChild(script);
// script.remove(); // opcional



window.__script_injetado_content = true;

console.log('✅ content.js injetado com sucesso!');

}