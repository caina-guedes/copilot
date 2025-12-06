import { print } from '../utils/generalUtils.js';


/**
 * Classe de comunicação entre background e content scripts.
 * Permite injetar scripts em abas, escutar e controlar mensagens, com suporte a múltiplas respostas.
 */
export class Mensageria {
    /**
   * Armazena o estado de cada canal de comunicação ativo, indexado por um ID único.
   * Cada estado contém:
   * - respostas: array de respostas recebidas
   * - encerrado: indica se o canal foi fechado
   */
    static estados = {};
  
    /**
   * Injeta um script em uma aba e gerencia a escuta de mensagens de resposta.
   *
   * @param {Object} options - Opções de execução.
   * @param {number} options.tabId - ID da aba de destino.
   * @param {Function|string} options.script - Função a ser executada ou caminho do arquivo JS.
   * @param {Array<any>} [options.args=[]] - Argumentos a serem passados para a função, se for o caso.
   * @param {string} options.tipoEsperado - Tipo de mensagem esperada para considerar resposta válida.
   * @param {number} [options.timeoutMs=2000] - Tempo máximo de espera por resposta(s), em milissegundos.
   * @param {number} [options.modoResposta=1] -
   *    0: sem listener, apenas injeta.
   *    1: uma única resposta e fecha o canal (padrão).
   *   -1: canal permanente, mantém aberto até ser encerrado manualmente.
   *    N > 1: aguarda N respostas, então encerra automaticamente.
   * @param {string} [options.idComunicacao] - ID único (gerado automaticamente se não informado).
   * @returns {Promise<any>} - Promessa que resolve com a(s) resposta(s), ou rejeita em caso de erro/timeout.
   */
    static async executarScriptComResposta({
      tabId = -1,
      script,
      args = [],
      tipoEsperado,
      timeoutMs = 2000,
      modoResposta = 1,
      idComunicacao = crypto.randomUUID(),
    }) {
        // Se não for necessário escutar resposta, apenas injeta e sai
      if (modoResposta === 0) {
        return this._injetar(tabId, script, args);
      }
      
      // Inicializa o estado do canal
      this.estados[idComunicacao] = {
        respostas: [],
        encerrado: false,
      };
  
      return new Promise((resolve, reject) => {
        //estado específico desse canal
        const estado = this.estados[idComunicacao];
         /**
       * Finaliza a comunicação, limpa listener e timeout.
       * @param {any} [respostaFinal=null]
       * @param {Error|null} [erro=null]
       */
        const finalizar = (respostaFinal = null, erro = null) => {
          clearTimeout(estado.timeout);
          chrome.runtime.onMessage.removeListener(estado.listener);
          estado.encerrado = true;
          if (erro) reject(erro);
          else resolve(respostaFinal);
        };
        
        // zera o timeout
        const resetarTimeout = () => {
          clearTimeout(estado.timeout);
            // caso em que o canal se mantem aberto indefinidamente
            if (modoResposta !== -1) {
            estado.timeout = setTimeout(() => {
              finalizar(null, new Error(`⏰ Timeout esperando '${tipoEsperado}'`));
            }, timeoutMs);
          }
        };
        
        // função auxiliar para por a resposta da aba na variável correta
        const armazenarResposta = (tipo,payload) => {
          if (!estado.respostas[tipo]) {
            estado.respostas[tipo] = [];
          }
          estado.respostas[tipo].push(payload);
        };

        
        estado.listener = (msg, sender) => {
            
            if (msg?.tipo          === tipoEsperado && 
                sender?.tab?.id    === tabId) {
            armazenarResposta(msg.tipo,msg.payload);
            
            //modo de resposta única
            if (modoResposta === 1) {
              finalizar(msg.payload);
            } 
            //modo de multiplas respostas
            else if (modoResposta > 1) {
              if (estado.respostas.length >= modoResposta) {
                finalizar([...estado.respostas]);
              } else {
                resetarTimeout();
              }
            }
            // modo de canal aberto indefinidamente 
            else if (modoResposta === -1) {
              resetarTimeout();
            }
          }
        };
  
        chrome.runtime.onMessage.addListener(estado.listener);
        resetarTimeout();
        this._injetar(tabId, script, args).catch((err) => finalizar(null, err));
      });
    }

      /**
     * Injeta um script (função ou arquivo) em uma aba.
     * @private
     * @param {number} tabId
     * @param {Function|string} script
     * @param {Array<any>} args
     */
    static async _injetar(tabId, script, args) {
        // injeta ou função ou arquivo, o que vier no script
        try{
          if (!tabId || tabId === -1) {
            // Se tabId for -1, injeta na aba ativa
            tabId = await chrome.tabs.query({ active: true, currentWindow: true })[0].id;
          }

      if (typeof script === "function") {
        await chrome.scripting.executeScript({
          target: { tabId },
          func: script,
          args,
        });
      } else {
        await chrome.scripting.executeScript({
          target: { tabId },
          files: [script],
        });
      }
    }catch (err) {
      print(err,'err')
    }
    }
    
      /**
     * Retorna o estado atual de um canal de comunicação, incluindo respostas acumuladas.
     * @param {string} idComunicacao
     * @returns {Object|null}
     */
    static getEstado(idComunicacao) {
        // da acesso ao estado parcial ou ao estado depois de encerrar
      return this.estados[idComunicacao] || null;
    }
  
    static encerrarComunicacao(idComunicacao) {
        // retira o listener e coloca encerrado no estado
      const estado = this.estados[idComunicacao];
      if (estado?.listener) chrome.runtime.onMessage.removeListener(estado.listener);
      this.estados[idComunicacao].encerrado = true ;
    }
  }
  