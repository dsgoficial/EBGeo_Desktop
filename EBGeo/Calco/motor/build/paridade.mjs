#!/usr/bin/env node
// Roda o caminho do EBGeo Web (arnês gerado por build.mjs --paridade) no Chromium do
// Playwright que o ebgeo_web já instala, e grava a saída de referência dos testes.
//
// Uso: node paridade.mjs --web <raiz do ebgeo_web> --arnes <paridade-web.js> --casos <entrada.json> --saida <saida.json>
//   casos: [{"tipo": "simbolo" | "medida", "props": {...}}, ...]
//   saida: {"resultados": [...], "baseline": {...}}

import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';

function argumento(nome) {
    const i = process.argv.indexOf(nome);
    return i >= 0 ? process.argv[i + 1] : undefined;
}

const raizWeb = argumento('--web') || process.env.EBGEO_WEB;
const arnes = argumento('--arnes');
const casos = JSON.parse(fs.readFileSync(argumento('--casos'), 'utf8'));
const saida = argumento('--saida');

const requireWeb = createRequire(path.join(path.resolve(raizWeb, 'frontend'), 'package.json'));
const { chromium } = requireWeb('@playwright/test');

const navegador = await chromium.launch();
try {
    const pagina = await navegador.newPage();
    await pagina.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body></body></html>');
    await pagina.addScriptTag({ content: fs.readFileSync(arnes, 'utf8') });
    const resultado = await pagina.evaluate(async (lista) => {
        const resultados = [];
        for (const caso of lista) {
            const f = window.paridadeWeb[caso.tipo];
            resultados.push(await f(caso.props));
        }
        return { resultados, baseline: window.paridadeWeb.baseline(), agente: navigator.userAgent };
    }, casos);
    fs.writeFileSync(saida, JSON.stringify(resultado), 'utf8');
    console.log(`paridade: ${resultado.resultados.length} casos no ${resultado.agente.match(/(?:Headless)?Chrome\/[\d.]+/)?.[0] || 'Chromium'}`);
} finally {
    await navegador.close();
}
