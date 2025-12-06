export function isInjectableUrl(url) {
    // console.log('url a ser testada: ', url);
    const resultado = (
        url &&
        !url.startsWith('chrome://') &&
        !url.startsWith('chrome-extension://') &&
        !url.startsWith('edge://') &&
        !url.startsWith('moz-extension://')
      )
        // console.log('resultado do teste: ', resultado);
        return resultado;
      }


      