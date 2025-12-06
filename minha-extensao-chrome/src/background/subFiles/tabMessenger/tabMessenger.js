// Responsável por enviar mensagens para abas específicas por URL ou ID
export async function enviarMensagemPorURL(url, mensagem) {
    try {
      chrome.tabs.query({}, (abas) => {
        const abaAlvo = abas.find((a) => a.url && a.url.includes(url));
        if (abaAlvo) {
          chrome.tabs.sendMessage(abaAlvo.id, mensagem);
          // console.log("📤 Mensagem enviada para aba com URL:", url);
        } else {
          console.warn("❌ Nenhuma aba encontrada com URL:", url);
        }
      });
    } catch (err) {
      console.error("Erro ao enviar mensagem por URL:", err);
    }
  }
  
  export async function enviarMensagemParaAba(id, mensagem) {
    try {
      chrome.tabs.sendMessage(id, mensagem);
      console.log("📤 Mensagem enviada para aba com ID:", id);
    } catch (err) {
      console.error("Erro ao enviar mensagem para aba:", err);
    }
  }
  