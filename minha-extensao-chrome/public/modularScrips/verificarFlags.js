(() => {
  const flags = {};
  for (const chave in window) {
    if (chave.startsWith('__script_injetado_')) {
      flags[chave] = true;
    }
  }

  chrome.runtime.sendMessage({
    tipo: 'flags_detectadas',
    flags
  });
})();
