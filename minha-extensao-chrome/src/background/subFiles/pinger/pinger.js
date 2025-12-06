import { enviarMensagemPorURL } from '../tabMessenger/tabMessenger.js';
import { isInjectableUrl } from '../utils/utils.js';
import { TIPOS_MENSAGEM } from '../../../shared_config/constants.js';
import { print } from '../../../utils/generalUtils.js';

export async function enviarPingParaAba(aba) {
    try {
      const mensagemPing = { tipo: TIPOS_MENSAGEM.PING };
  
      const resposta = await new Promise((resolve, reject) => {
        chrome.tabs.query({}, async (abas) => {
          const abaAlvo = abas.find((a) => a.id === aba.id);
          if (!abaAlvo || !abaAlvo.url) {
            console.warn("❌ Aba inválida ao tentar pingar:", aba);
            return resolve(null); // Resolve com null para indicar erro
          }
  
          // Envia o ping via URL
          await enviarMensagemPorURL(abaAlvo.url, mensagemPing);
  
          // Espera por uma resposta via sendMessage
          chrome.tabs.sendMessage(abaAlvo.id, mensagemPing, (res) => {
            if (chrome.runtime.lastError) {
              console.error("Erro ao enviar mensagem:", chrome.runtime.lastError);
              return resolve(null); // Resolve com null para indicar erro
            }
  
            // Se não houver resposta válida, resolve com null
            if (!res || res.tipo !== TIPOS_MENSAGEM.PONG) {
              // console.warn("⚠️ Aba NÃO respondeu ao ping ou resposta inválida:", aba.url);
              // console.log("Resposta recebida:", res);
              return resolve(null); // Resolve com null
            }
  
            resolve(res);
          });
        });
      });
  
      // Verifica se a resposta é válida antes de tentar acessar 'respondeu'
      if (resposta && resposta.tipo === TIPOS_MENSAGEM.PONG) {
        // console.log("✅ Aba respondeu ao ping:", aba.url);
        return { aba, respondeu: true };
      } else {
        // console.warn("⚠️ Aba NÃO respondeu ao ping:", aba.url);
        return { aba, respondeu: false };
      }
    } catch (erro) {
      print("Erro ao enviar ping:", erro);
      return { aba, respondeu: false };
    }
  }
  
  

export function iniciarMonitoramentoDasAbas(intervalo = 15000) {
  setInterval(async () => {
    chrome.tabs.query({}, async (abas) => {
      const abasInjetaveis = abas.filter((aba) => isInjectableUrl(aba.url));

      const resultados = await Promise.all(
        abasInjetaveis.map((aba) => enviarPingParaAba(aba))
      );

      const responderam = resultados.filter(r => r.respondeu);
      const naoResponderam = resultados.filter(r => !r.respondeu);

      responderam.forEach(r => console.log("✅", r.aba.url));
      naoResponderam.forEach(r => console.log("❌", r.aba.url));

      console.log("Resumo:");
      console.log("✅ Abas que responderam:", responderam.map(r => r.aba.url));
      console.log("❌ Abas que não responderam:", naoResponderam.map(r => r.aba.url));
    });
  }, intervalo);
}

export  async function injetaScriptPagina(tab) {
    //// preciso usar essa função ainda!!!
    return new Promise((resolve, reject) => {
      if (!isInjectableUrl(tab.url)) {
        console.warn("🚫 Aba não elegível para injeção:", tab.url);
        return resolve(false);
      }
      console.log('tentando injetar script na aba: ', tab.url);
      chrome.scripting.executeScript(
        {
          target: { tabId: tab.id },
          files: ["content.js"]
        },
        (results) => {
          if (chrome.runtime.lastError) {
            console.error("❌ Erro ao injetar script:", chrome.runtime.lastError.message);
            return reject(chrome.runtime.lastError);
          }
  
          console.log("✅ Script injetado com sucesso na aba:", tab.url);
          resolve(true);
        }
      );
    });
  }
