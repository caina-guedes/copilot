import { injetarScripts } from '../../../pageScrips/injectScripts.js';
import { Mensageria } from '../../../mensageria/mensageria.js';
import { TIPOS_MENSAGEM } from '../../../shared_config/constants.js';
import { print } from '../../../utils/generalUtils.js';


export async function configurarListenersDoChrome() {

  await Mensageria.executarScriptComResposta({
    tabId: -1, // -1 para todas as abas
    script: 'scripts/observador-clique.js', // ou uma função inline
    tipoEsperado: TIPOS_MENSAGEM.observadorCliques,
    modoResposta: -1, // canal permanente
  });
    // listener temporário para testes
    chrome.action.onClicked.addListener(async (tab) => {
        if (tab.id) {
          await injetarScripts(tab.id, ['teste.js']); // Injeta o script
        }
      });

  chrome.runtime.onInstalled.addListener(() => {
    injetarScripts(); // injeta content.js por padrão
  });

  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (mensagem.tipo === "flags_detectadas") {
        print(`🚦 Flags da aba ${sender.tab?.id}:`);
        console.log(mensagem.flags); // ou usa print se quiser
    }
    
    if (msg.acao === 'injetar_observadores') {
      const { tabId, observadores } = msg;
      injetarScripts(tabId, observadores);
    }
  });

  // Aqui você pode ir adicionando mais:
  // chrome.tabs.onActivated.addListener(...)
  // chrome.alarms.onAlarm.addListener(...)
  // chrome.storage.onChanged.addListener(...)
}
