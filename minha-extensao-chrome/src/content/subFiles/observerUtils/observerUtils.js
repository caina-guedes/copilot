
export class observerUtils {


static obterAtributosImportantes(el) {
    const importantes = ['href', 'type', 'name', 'value', 'data-*', 'role', 'aria-*'];
    const atributos = {};
    for (let attr of el.attributes) {
      if (importantes.some(chave => attr.name.startsWith(chave.replace('*', '')))) {
        atributos[attr.name] = attr.value;
      }
    }
    return atributos;
  }
  

/**
 * Gera um seletor CSS “único” para um dado elemento,
 * usando ID se existir ou sub-seletores com tag, classes e nth-of-type.
 *
 * @param {Element} element
 * @returns {string|null} Um seletor CSS que identifica exclusivamente o elemento, ou null se inválido.
 */
static gerarSeletorUnico(element) {
    if (!(element instanceof Element)) return null;
  
    // Se tiver ID, usamos ele direto
    if (element.id) {
      return `#${element.id}`;
    }
  
    const parts = [];
    let el = element;
    while (el && el.nodeType === Node.ELEMENT_NODE) {
      let selector = el.tagName.toLowerCase();
  
      // Adiciona classes, se existirem
      const classList = Array.from(el.classList).filter(Boolean);
      if (classList.length) {
        selector += '.' + classList.join('.');
      }
  
      // Se houver irmãos do mesmo tipo, usamos nth-of-type
      const parent = el.parentNode;
      if (parent instanceof Element) {
        const sameTagSiblings = Array.from(parent.children)
          .filter(child => child.tagName === el.tagName);
        if (sameTagSiblings.length > 1) {
          const index = sameTagSiblings.indexOf(el) + 1;
          selector += `:nth-of-type(${index})`;
        }
      }
  
      parts.unshift(selector);
      el = parent instanceof Element ? parent : null;
    }
  
    return parts.join(' > ');
  }
}