#!/usr/bin/env node
// Gera, a partir de um checkout do EBGeo Web, os artefatos do motor de símbolos do plugin:
//
//   ../ebgeo-simbologia.js  bundle IIFE minificado para o QJSEngine (global EBGeoSimbologia)
//   ../catalogos.json       catálogos da interface (conjuntos, ícones, medidas)
//   ../WMM2025.COF          coeficientes do World Magnetic Model 2025 (NOAA, domínio público)
//
// Uso:
//   node build.mjs --web <raiz do ebgeo_web>
//   EBGEO_WEB=<raiz do ebgeo_web> node build.mjs
//   node build.mjs --web <raiz> --paridade <pasta>   gera também o arnês de paridade (testes)
//   node build.mjs --web <raiz> --paridade <pasta> --apenas-paridade   só o arnês
//
// O bundler é o rolldown que o Vite do ebgeo_web já instala em frontend/node_modules; nada é
// instalado no repositório do plugin. Ver README.md desta pasta.

import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const MOTOR = path.resolve(AQUI, '..');

function argumento(nome) {
    const i = process.argv.indexOf(nome);
    return i >= 0 ? process.argv[i + 1] : undefined;
}

const raizWeb = argumento('--web') || process.env.EBGEO_WEB;
if (!raizWeb) {
    console.error('Informe a raiz do ebgeo_web por --web <pasta> ou pela variável EBGEO_WEB.');
    process.exit(2);
}
const FRONTEND = path.resolve(raizWeb, 'frontend');
const SRC = path.join(FRONTEND, 'src');
const MODULOS = path.join(FRONTEND, 'node_modules');
if (!fs.existsSync(path.join(SRC, 'js', 'military_tools'))) {
    console.error('Não achei frontend/src/js/military_tools em ' + raizWeb);
    process.exit(2);
}

const requireWeb = createRequire(path.join(FRONTEND, 'package.json'));
const { build } = await import(pathToFileURL(requireWeb.resolve('rolldown')).href);

// Os mesmos aliases do vite.config.js do ebgeo_web.
const ALIASES = {
    '@js': path.join(SRC, 'js'),
    '@css': path.join(SRC, 'css'),
    '@store': path.join(SRC, 'js', 'store'),
    '@state': path.join(SRC, 'js', 'state'),
    '@utils': path.join(SRC, 'js', 'utilities'),
    '@tools': path.join(SRC, 'js', 'tool_manager'),
    '@toolbar': path.join(SRC, 'js', 'toolbar'),
    '@modals': path.join(SRC, 'js', 'modals'),
    '@sidebar': path.join(SRC, 'js', 'sidebar'),
    '@layers': path.join(SRC, 'js', 'layers'),
    '@catalog': path.join(SRC, 'js', 'catalog'),
    '@ui': path.join(SRC, 'js', 'ui'),
    '@events': path.join(SRC, 'js', 'events'),
    '@': SRC,
};

function versaoDoPacote(nome) {
    return JSON.parse(fs.readFileSync(path.join(MODULOS, nome, 'package.json'), 'utf8')).version;
}

function commitDoWeb() {
    try {
        return execFileSync('git', ['-C', raizWeb, 'rev-parse', '--short=12', 'HEAD'], { encoding: 'utf8' }).trim();
    } catch {
        return 'desconhecido';
    }
}

const versaoMilsymbol = versaoDoPacote('milsymbol');
const commit = commitDoWeb();
const geradoEm = new Date().toISOString().slice(0, 10);

const entradaComum = {
    resolve: { alias: ALIASES, modules: [MODULOS, 'node_modules'] },
    // O QJSEngine do Qt 6.8 não entende espalhamento de objeto nem campos de classe: ES2016.
    transform: { target: 'es2016' },
    logLevel: 'warn',
    // O gerador de engenharia importa engineering.css (estilo do painel): fora do navegador o
    // CSS não serve, e o módulo vira vazio.
    plugins: [{
        name: 'css-vazio',
        load(id) {
            return id.endsWith('.css') ? { code: 'export {};', moduleType: 'js' } : null;
        },
    }],
};

// O milsymbol é MIT: o aviso de licença acompanha o código. Os comentários do fonte do Web
// (privado) não entram: minificado, sem source map, sem comentários.
const LICENCA_MILSYMBOL = `/*! milsymbol ${versaoMilsymbol} | The MIT License (MIT) | Copyright (c) 2017 Måns Beckman - www.spatialillusions.com
 Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. */`;

const CABECALHO = `${LICENCA_MILSYMBOL}
/* ebgeo-simbologia.js: gerado por EBGeo/Calco/motor/build/build.mjs a partir do EBGeo Web ${commit} em ${geradoEm}. Não editar. */`;

async function gerarBundle() {
    const destino = path.join(MOTOR, 'ebgeo-simbologia.js');
    await build({
        ...entradaComum,
        input: path.join(AQUI, 'entrada.js'),
        platform: 'neutral',
        write: true,
        output: {
            file: destino,
            format: 'iife',
            name: 'EBGeoSimbologia',
            minify: true,
            sourcemap: false,
            comments: false,
            footer: `EBGeoSimbologia.versao.web=${JSON.stringify(commit)};EBGeoSimbologia.versao.gerado=${JSON.stringify(geradoEm)};`,
        },
    });
    // O cabeçalho entra depois do minificador, que descartaria um banner de comentário.
    const texto = CABECALHO + '\n' + fs.readFileSync(destino, 'utf8');
    fs.writeFileSync(destino, texto, 'utf8');
    // Prova barata de que nada do fonte vazou: nenhum comentário além do cabeçalho, nenhum
    // caminho de máquina e nenhum mapa de fonte.
    const semCabecalho = texto.slice(CABECALHO.length + 1);
    const vazamentos = [];
    if (/sourceMappingURL/.test(texto)) vazamentos.push('sourceMappingURL');
    if (/\/\*[\s\S]*?\*\//.test(semCabecalho.replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`/g, '""'))) {
        vazamentos.push('comentário de bloco');
    }
    for (const marca of [raizWeb, FRONTEND.replace(/\\/g, '/'), os.homedir()]) {
        if (marca && texto.includes(marca)) vazamentos.push('caminho ' + marca);
    }
    if (vazamentos.length) {
        throw new Error('O bundle carrega o que não devia: ' + vazamentos.join(', '));
    }
    console.log(`bundle: ${path.relative(process.cwd(), destino)} (${(texto.length / 1024).toFixed(1)} KiB)`);
}

async function gerarCatalogos() {
    const temporaria = fs.mkdtempSync(path.join(os.tmpdir(), 'ebgeo-catalogos-'));
    const arquivo = path.join(temporaria, 'catalogos.mjs');
    try {
        await build({
            ...entradaComum,
            input: path.join(AQUI, 'entrada-catalogos.js'),
            platform: 'node',
            write: true,
            output: { file: arquivo, format: 'esm' },
        });
        const { montarCatalogos } = await import(pathToFileURL(arquivo).href);
        const catalogos = montarCatalogos();
        catalogos.versao = { web: commit, milsymbol: versaoMilsymbol, gerado: geradoEm };
        const destino = path.join(MOTOR, 'catalogos.json');
        fs.writeFileSync(destino, JSON.stringify(catalogos) + '\n', 'utf8');
        console.log(`catálogos: ${path.relative(process.cwd(), destino)} (${(fs.statSync(destino).size / 1024).toFixed(1)} KiB)`);
    } finally {
        fs.rmSync(temporaria, { recursive: true, force: true });
    }
}

// WMM2025.COF reescrito no formato da NOAA a partir dos coeficientes do pacote geomagnetism
// (o mesmo que o Web usa). O WMM é obra do governo dos EUA, domínio público.
function gerarCof() {
    const dados = JSON.parse(fs.readFileSync(path.join(MODULOS, 'geomagnetism', 'data', 'wmm-2025.json'), 'utf8'));
    const f = (v, w) => v.toFixed(1).padStart(w);
    const linhas = [`    ${dados.epoch.toFixed(1)}            WMM-2025     11/13/2024`];
    for (let n = 1; n <= dados.n_max; n++) {
        for (let m = 0; m <= n; m++) {
            const i = n * (n + 1) / 2 + m;
            linhas.push(`${String(n).padStart(3)}${String(m).padStart(3)}${f(dados.main_field_coeff_g[i], 10)}${f(dados.main_field_coeff_h[i], 10)}${f(dados.secular_var_coeff_g[i], 11)}${f(dados.secular_var_coeff_h[i], 11)}`);
        }
    }
    linhas.push('9'.repeat(48), '9'.repeat(48));
    const destino = path.join(MOTOR, 'WMM2025.COF');
    fs.writeFileSync(destino, linhas.join('\n') + '\n', 'utf8');
    console.log(`wmm: ${path.relative(process.cwd(), destino)} (${linhas.length - 3} coeficientes)`);
}

async function gerarParidade(pasta) {
    fs.mkdirSync(pasta, { recursive: true });
    const destino = path.join(pasta, 'paridade-web.js');
    await build({
        ...entradaComum,
        input: path.join(AQUI, 'entrada-paridade.js'),
        platform: 'browser',
        write: true,
        // O Chromium entende o JavaScript do Web como ele é: sem rebaixar o alvo.
        transform: {},
        output: { file: destino, format: 'iife', name: 'ParidadeWeb', minify: false, sourcemap: false },
    });
    console.log(`paridade: ${destino}`);
}

// --apenas-paridade: só o arnês (os testes usam isto para não reescrever os artefatos do plugin).
const pastaParidade = argumento('--paridade');
if (!process.argv.includes('--apenas-paridade')) {
    await gerarBundle();
    await gerarCatalogos();
    gerarCof();
}
if (pastaParidade) await gerarParidade(path.resolve(pastaParidade));
