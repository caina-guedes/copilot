// Função para injetar scripts em abas
import { solicitarPermissoes } from '../permissions/index.js';
import { isInjectableUrl } from '../background/subFiles/utils/utils.js';
import { print } from '../utils/generalUtils.js'


  
// Função para injetar scripts em abas
async function injetarEmAba(tabId, scripts) {
    for (const arquivo of scripts) {
         // 1) Verifica permissão de injeção
        if (! await solicitarPermissoes(arquivo, tabId)) {
            print(`🚫 Sem permissão para injetar ${arquivo} na aba ${tabId}`,'warn');
            continue;
        }
    
        // 2) Verifica se a URL da aba é elegível (você pode adaptar para aba.url)
        if (!isInjectableUrl(arquivo)) {
            print('🚫 URL não elegível para injeção de ${arquivo} ' , 'warn');
            continue;
        }
      // Extraindo o nome do script de maneira segura
      const nomeDoScript = arquivo.split('/').pop().replace(/\W/g, '_'); // Ex: observadorCliques_js
      const flagName = `__script_injetado_${nomeDoScript}`;
      const isContent = "content.js" === arquivo;
      let urlAbsoluta;

      if (isContent) {
        // content.js vive na raiz do dist/
        urlAbsoluta = chrome.runtime.getURL('content.js');
      } else {
  
      urlAbsoluta = chrome.runtime.getURL("modularScrips/" + arquivo); // Obtemos a URL absoluta do arquivo a ser injetado
      }
      try {
        if (isContent){
            await chrome.scripting.executeScript({
                target: { tabId },
                files: ['content.js'],
              });
              console.log(`✅ content.js injetado na aba ${tabId}`);
            } else {
        
        await chrome.scripting.executeScript({
          target: { tabId },
          func: (url, flagName) => {
            // daqui em diante esse codigo roda no contexto da página, não do background

            // Verificação se o script já foi injetado
            if (window[flagName]) {
              console.warn(`⚠️ Script já injetado: ${url}`);
              return;
            }
  
            // Criando o elemento <script> para injeção do arquivo
            const script = document.createElement('script');
            script.src = url;
            script.onload = () => {
                window[flagName] = true;
                console.log(`✅ Script carregado: ${url}`);
                };

            script.onerror = () => console.log(`❌ Erro ao carregar: ${url}`,'error');
            document.documentElement.appendChild(script);
          },
          args: [urlAbsoluta, flagName], // Passando a URL e o nome da flag para a função
        });
    }
        
  
        print(`✅ Script injetado: ${arquivo} na aba ${tabId}`);
      } catch (err) {
        print(`❌ Erro ao injetar ${arquivo} na aba ${tabId}: ` + err , 'error');
      }
    }
  }
  
  // Função para injetar scripts em todas as abas ou em uma aba específica
  export async function injetarScripts(tabId = null, scriptsPermitidos = []) {
    const arquivosBase = ['content.js']; // sempre injeta esse
   
    function ignorarContentJs(script) {
        return !script.endsWith('content.js');
      }
      
      const scriptsAInjetar = ['content.js', ...scriptsPermitidos.filter(ignorarContentJs)];
  
    try {
      if (tabId !== null) {
        await injetarEmAba(tabId, scriptsAInjetar); // Injeta o script na aba específica
      } else {
        // Injeta em todas as abas abertas
        print("Injetando scripts em todas as abas abertas...");
        const abas = await chrome.tabs.query({
          status: "complete",
          url: ["http://*/*", "https://*/*"],
        });
  
        for (const aba of abas) {
          if (!aba.id || aba.url?.startsWith('chrome://')) continue; // Ignora abas não elegíveis
          await injetarEmAba(aba.id, scriptsAInjetar);
        }
      }
    } catch (err) {
      print("❌ Erro ao injetar scripts:" + err,'error');
    }
  }
  




  export function listaDeFlagsInjetadas(tabId) {
    return new Promise((resolve, reject) => {
      let resolved = false;
  
      const listener = (msg, sender) => {
        if (
          msg?.tipo === "flags_detectadas" &&
          sender?.tab?.id === tabId &&
          !resolved
        ) {
          resolved = true;
          chrome.runtime.onMessage.removeListener(listener);
          clearTimeout(timeout);
          resolve(msg.flags);
        }
      };
  
      chrome.runtime.onMessage.addListener(listener);
  
      // Injetar o script que coleta as flags
      chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          const flags = {};
          for (const chave in window) {
            if (chave.startsWith("__script_injetado_")) {
              flags[chave] = true;
            }
          }
  
          // Envia de volta para o background
          chrome.runtime.sendMessage({
            tipo: "flags_detectadas",
            flags,
          });
        },
      }).catch((err) => {
        print("❌ Erro ao injetar script para coletar flags:", err, 'error');
        if (!resolved) {
          resolved = true;
          chrome.runtime.onMessage.removeListener(listener);
          clearTimeout(timeout);
          reject(err);
        }
      });
  
      const timeout = setTimeout(() => {
        if (!resolved) {
          // Timeout após 10 segundos
          print("⏰ Timeout demorou demais para retornar a resposta pro background", 'error');
          resolved = true;
          chrome.runtime.onMessage.removeListener(listener);
          reject(new Error("⏰ Timeout ao aguardar flags da aba " + tabId));
        }
      }, 10000);
    });
  }
  