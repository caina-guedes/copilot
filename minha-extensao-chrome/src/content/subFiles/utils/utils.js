// aqui ficarão as funcoes auxiliares para o content.js


export function digitarComoHumano(elemento, texto) {
    let i = 0;
    if (i < texto.length) {
        elemento.value += texto[i];
        elemento.dispatchEvent(new Event("input", { bubbles: true }));
        i++;
        setTimeout(digitar, Math.random() * 200 + 50); // Delay aleatório
    }
}

export function digitarComoHumanoRandom(elemento, texto) {
    let i = 0;
    function digitar() {
        if (i < texto.length) {
            elemento.value += texto[i];
            elemento.dispatchEvent(new Event("input", { bubbles: true }));
            i++;
            setTimeout(digitar, Math.random() * 200 + 50); // Delay aleatório
        }
    }
    digitar();
}

let campo = document.querySelector("#campo_nome");
digitarComoHumano(campo, "João da Silva");

// let campo = document.querySelector("#campo_nome");
// digitarComoHumano(campo, "João da Silva");


// pesquisar mais sobre dispatchEvent

// let input = document.querySelector("#campo_nome");
// input.value = "João da Silva";
// input.dispatchEvent(new Event("input", { bubbles: true }));