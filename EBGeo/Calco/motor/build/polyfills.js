// Polyfills para o QJSEngine do Qt 6.8 (motor V4). Medido no QGIS 4.0.0 (Qt 6.8.1): faltam
// globalThis, Object.hasOwn, Object.fromEntries e console; o espalhamento de objeto ({...a})
// não existe como sintaxe, e isso o build resolve rebaixando o alvo para ES2016.
//
// Este módulo é o PRIMEIRO import da entrada: os catálogos do Web chamam Object.fromEntries
// já na carga do módulo, então o polyfill tem de existir antes de eles avaliarem.

const G = Function('return this')();

if (typeof G.globalThis === 'undefined') G.globalThis = G;

if (typeof Object.hasOwn !== 'function') {
    Object.hasOwn = (objeto, chave) => Object.prototype.hasOwnProperty.call(Object(objeto), chave);
}

if (typeof Object.fromEntries !== 'function') {
    Object.fromEntries = (pares) => {
        const saida = {};
        for (const par of pares) saida[par[0]] = par[1];
        return saida;
    };
}

// Avisos que os módulos do Web escrevem no console (extensão não catalogada etc.). No QJSEngine
// não há console; aqui eles são guardados e devolvidos ao Python junto com o desenho.
const avisos = [];
G.__ebgeoAvisos = avisos;

if (typeof G.console === 'undefined') {
    const guardar = (nivel) => (...partes) => {
        avisos.push(nivel + ': ' + partes.map(String).join(' '));
    };
    G.console = { log: () => {}, info: () => {}, debug: () => {}, warn: guardar('aviso'), error: guardar('erro') };
}

export function colherAvisos() {
    return avisos.splice(0, avisos.length);
}
