// Arnês de PARIDADE: o caminho do próprio EBGeo Web (MilitarySymbolGenerator e
// CoordinationMeasureGenerator, intactos, com a rasterização em canvas de verdade), para rodar
// no Chromium pelo build/paridade.mjs. Não vai para o plugin: o build o gera numa pasta
// temporária só quando os testes pedem.

import '@js/vendor/milsymbol.js';
import { MilitarySymbolGenerator } from '@js/military_tools/military_symbol_tool/military_symbol_generator.js';
import { CoordinationMeasureGenerator } from '@js/military_tools/coordination_measure_tool/coordination_measure_generator.js';
import { generateDeclinationSvg } from '@js/military_tools/declination_tool/declination_svg_generator.js';
import { calculateMagneticDeclination } from '@utils/geomagnetic/wmm_calculator.js';
import { calculateMeridianConvergence } from '@utils/geomagnetic/meridian_convergence.js';

import { engineeringSvg, EngineeringSymbolGenerator } from '@js/military_tools/engineering_symbol_tool/engineering_generator.js';

async function engenharia(p) {
    try {
        const d = engineeringSvg(p.pointCode, p);
        const r = await new EngineeringSymbolGenerator().generate(p.pointCode, p);
        // O PNG que o Web registra no mapa (nitidez 2), em base64, para a comparação de pixels.
        const png = await new Promise((ok) => {
            const leitor = new FileReader();
            leitor.onload = () => ok(String(leitor.result).split(',')[1]);
            leitor.readAsDataURL(r.blob);
        });
        return { svg: d.svg, larguraDesenho: d.width, alturaDesenho: d.height, largura: r.width, altura: r.height,
            iconOffset: r.iconOffset, png, pixelRatio: r.pixelRatio };
    } catch (erro) {
        return { erro: String(erro && erro.message || erro) };
    }
}

async function declinacao(p) {
    return { svg: generateDeclinationSvg(p.declination, p.convergence, p.fillColor) };
}

async function wmm(p) {
    const r = calculateMagneticDeclination(p.lat, p.lon, 0, new Date(p.data));
    return Object.assign({}, r, { convergence: calculateMeridianConvergence(p.lat, p.lon) });
}

function capturar(gerador) {
    const original = gerador.convertToPngBlob.bind(gerador);
    const captura = { svg: null };
    gerador.convertToPngBlob = async (fonte, largura, altura) => {
        // O militar passa uma data URL; a medida passa o SVG cru.
        captura.svg = fonte.startsWith('data:') ? decodeURIComponent(fonte.slice(fonte.indexOf(',') + 1)) : fonte;
        return original(fonte, largura, altura);
    };
    return captura;
}

async function simbolo(props) {
    const gerador = new MilitarySymbolGenerator();
    const captura = capturar(gerador);
    try {
        const r = await gerador.generateSymbolBlob(props);
        return { svg: captura.svg, largura: r.width, altura: r.height, iconOffset: r.iconOffset || null };
    } catch (erro) {
        return { erro: String(erro && erro.message || erro) };
    }
}

async function medida(props) {
    const gerador = new CoordinationMeasureGenerator();
    const captura = capturar(gerador);
    try {
        const r = await gerador.generateSymbolBlob(props);
        return { svg: captura.svg, largura: r.width, altura: r.height, anchor: r.anchor, iconOffset: r.iconOffset };
    } catch (erro) {
        return { erro: String(erro && erro.message || erro) };
    }
}

// Deslocamento que o navegador aplica a cada dominant-baseline, em frações do font-size.
function baseline() {
    const NS = 'http://www.w3.org/2000/svg';
    const saida = {};
    for (const peso of ['bold', 'normal']) {
        for (const base of ['middle', 'central', 'hanging', 'mathematical', 'text-before-edge']) {
            const svg = document.createElementNS(NS, 'svg');
            svg.setAttribute('width', '400');
            svg.setAttribute('height', '400');
            document.body.appendChild(svg);
            const caixa = (valor) => {
                const t = document.createElementNS(NS, 'text');
                t.setAttribute('x', '100');
                t.setAttribute('y', '200');
                t.setAttribute('font-size', '100');
                t.setAttribute('font-family', 'Arial');
                t.setAttribute('font-weight', peso);
                if (valor) t.setAttribute('dominant-baseline', valor);
                t.textContent = 'HQx';
                svg.appendChild(t);
                return t.getBBox();
            };
            const a = caixa(null);
            const b = caixa(base);
            saida[peso + '/' + base] = Math.round((b.y - a.y) * 100) / 10000;
            svg.remove();
        }
    }
    return saida;
}

window.paridadeWeb = { simbolo, medida, engenharia, declinacao, wmm, baseline };
