document.addEventListener('click', (e) => {
  const target = e.target;
  const path = e.composedPath(); // caminho completo no DOM
  const selector = gerarSeletorUnico(target); // função que você pode implementar

  const dadosClique = {
    tipo: 'click',
    tag: target.tagName,
    id: target.id,
    classes: target.className,
    textContent: target.textContent?.trim(),
    atributos: obterAtributosImportantes(target),
    seletorUnico: selector,
    posicao: {
      x: e.clientX,
      y: e.clientY,
    },
    boundingBox: target.getBoundingClientRect(),
    timestamp: Date.now(),
    path: path.map(el => el.tagName || el.nodeName).filter(Boolean),
  };

  console.log('[🔥 Clique capturado]', dadosClique);
});
