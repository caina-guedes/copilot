import { TIPOS_MENSAGEM } from "../../shared_config/constants";    

export function print(...args) {
    // função auxiliar para prints de forma legível !
    // Se o modo_dev não estiver ativo, não faz nada
    // Se o último argumento for um dos modos válidos, usa ele
    // Se não, usa o modo padrão (console.log)

    const modosValidos = ["alert", "warn", "error"];
    const ultimoArg = args[args.length - 1];

    const modo = modosValidos.includes(ultimoArg) ? ultimoArg : null;
    const valoresOriginais = modo ? args.slice(0, -1) : args;

    if (!TIPOS_MENSAGEM.modo_dev) return;

    // Função auxiliar para formatar os argumentos
    const formatar = (valor) => {
        if (typeof valor === "object") {
            try {
                return JSON.stringify(valor, null, 2);
            } catch {
                return String(valor);
            }
        }
        return String(valor);
    };

    const valoresFormatados = valoresOriginais.map(formatar);

    if (modo === "alert") {
        alert(valoresFormatados.join("\n"));
    } else if (modo === "warn") {
        console.warn(...valoresFormatados);
    } else if (modo === "error") {
        console.error(...valoresFormatados);
    } else {
        console.log(...valoresFormatados);
    }
}
