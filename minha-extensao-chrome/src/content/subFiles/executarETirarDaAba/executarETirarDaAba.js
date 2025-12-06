// para usar quando não for interessante deixar o script rodando na aba
(function() {
    'use strict';

    let script = document.createElement("script");
    script.innerHTML = `
        setTimeout(() => {
            document.querySelector("#campo_nome").value = "João";
        }, 2000);
    `;
    document.documentElement.appendChild(script);
    document.documentElement.removeChild(script); // Remove para esconder a modificação
})();
