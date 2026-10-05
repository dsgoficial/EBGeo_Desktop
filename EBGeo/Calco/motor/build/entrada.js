// Entrada do bundle ebgeo-simbologia.js: os geradores de símbolo pontual do EBGeo Web, sem DOM,
// para rodar no QJSEngine do QGIS. Os módulos do Web entram INTACTOS pelo alias @js; o que está
// aqui é só o caminho síncrono que o Web faz dentro de funções assíncronas (a rasterização em
// canvas fica de fora: o QGIS desenha o SVG). A paridade com o Web é medida por
// testes/test_motor.py contra o próprio Web rodando no Chromium (build/paridade.mjs).

import { colherAvisos } from './polyfills.js';
import ms from 'milsymbol';
import { normalizeSIDC, getBaseSIDC } from '@js/military_tools/military_symbol_tool/brazilian_sidc_extension.js';
import { applyBrazilianModifications } from '@js/military_tools/military_symbol_tool/brazilian_svg_postprocessing.js';
import { hasExtensions } from '@js/military_tools/military_symbol_tool/brazilian_extension_catalog.js';
import { extractTextModifiers } from '@js/military_tools/military_symbol_tool/text-modifiers-mapping.js';
import { militaryIconOffset } from '@js/military_tools/military_symbol_tool/military-symbol-anchor.js';
import { fitDrawSize } from '@js/military_tools/svg-to-png.js';
import { SYMBOL_BITMAP_PIXEL_RATIO } from '@js/layers/bitmap-version.js';
import { CoordinationMeasureGenerator, iconOffsetFor } from '@js/military_tools/coordination_measure_tool/coordination_measure_generator.js';
import { codigoDesenhavel } from '@js/military_tools/coordination_measure_tool/familias-de-escalao.js';
import { engineeringSvg, engineeringDraft, engineeringItem } from '@js/military_tools/engineering_symbol_tool/engineering_generator.js';
import { errorsFor } from '@js/military_tools/engineering_symbol_tool/engineering_drawing.js';
import { rampChevronCount } from '@js/military_tools/engineering_symbol_tool/engineering_fields.js';
import { instalarDomTemporario } from './dom-minimo.js';

// ---------------------------------------------------------------------------------------------
// Correção de texto para o QSvgRenderer
// ---------------------------------------------------------------------------------------------

// O QSvgRenderer ignora dominant-baseline (medido no QGIS 4.0.0): todo texto cai na linha de
// base alfabética. O milsymbol emite dominant-baseline="middle" nos rótulos de ícone, e o
// catálogo brasileiro copia essa forma. Desloca-se o y pelo mesmo tanto que o navegador
// desloca, MEDIDO no Chromium com Arial (build/paridade.mjs, função baseline): em frações do
// font-size, middle 0,2592 (meia altura-x), central 0,35, hanging 0,728, mathematical 0,455,
// text-before-edge 0,91.
const DESLOCAMENTO_BASELINE = {
    'middle': 0.2592,
    'central': 0.35,
    'hanging': 0.728,
    'mathematical': 0.455,
    'text-before-edge': 0.91,
    'before-edge': 0.91,
    'auto': 0,
    'alphabetic': 0,
};

function numeroDoAtributo(tag, nome) {
    const m = tag.match(new RegExp('\\s' + nome + '="([^"]*)"'));
    return m ? parseFloat(m[1]) : NaN;
}

function arredondar(valor) {
    return Math.round(valor * 1000) / 1000;
}

export function corrigirTextoParaQt(svg) {
    return svg.replace(/<text\b[^>]*>/g, (tag) => {
        const base = tag.match(/\s(?:dominant-baseline|alignment-baseline)="([^"]*)"/);
        if (!base) return tag;
        const fator = DESLOCAMENTO_BASELINE[base[1]];
        const tamanho = numeroDoAtributo(tag, 'font-size');
        let y = numeroDoAtributo(tag, 'y');
        let semBase = tag.replace(base[0], '');
        if (fator === undefined || !Number.isFinite(tamanho)) return semBase;
        if (!Number.isFinite(y)) {
            y = 0;
            semBase = semBase.replace(/^<text\b/, '<text y="0"');
        }
        return semBase.replace(/\sy="[^"]*"/, ' y="' + arredondar(y + fator * tamanho) + '"');
    });
}

// ---------------------------------------------------------------------------------------------
// Símbolo militar: generateSymbol de military_symbol_generator.js, sem o canvas
// ---------------------------------------------------------------------------------------------

// military_symbol_generator.js: DEFAULT_SIZE e generateSymbolBlob, que passa DEFAULT_SIZE, a
// cor de properties.fillColor e SYMBOL_BITMAP_PIXEL_RATIO.
const TAMANHO_PADRAO = 100;

function viewBoxDe(svgString) {
    const match = svgString.match(/viewBox="([^"]+)"/);
    if (!match) return null;
    const [x, y, width, height] = match[1].split(' ').map(Number);
    return { x, y, width, height };
}

// Tamanho natural do SVG como o <img> do navegador o lê (naturalWidth/naturalHeight): os
// atributos width e height da raiz ARREDONDADOS para inteiro. Medido no Chromium 149 pela
// paridade: 129,5 vira 130, 78,5 vira 79 e 323,33 vira 323; sem o arredondamento, 4 de 80
// símbolos saíam meio pixel lógico diferentes do Web.
function tamanhoNatural(svg) {
    const raiz = (svg.match(/<svg\b[^>]*>/) || [''])[0];
    const w = numeroDoAtributo(raiz, 'width');
    const h = numeroDoAtributo(raiz, 'height');
    if (Number.isFinite(w) && Number.isFinite(h)) return { width: Math.round(w), height: Math.round(h) };
    const vb = viewBoxDe(raiz);
    return vb ? { width: vb.width, height: vb.height } : { width: NaN, height: NaN };
}

export function gerarSimboloMilitar(props) {
    props = props || {};
    colherAvisos();
    const sidcBruto = typeof props.sidc === 'string' ? props.sidc : (props.sidc == null ? '' : String(props.sidc));
    const sidc30 = normalizeSIDC(sidcBruto);
    if (!sidc30) {
        throw new Error('SIDC inválido: precisa de 20 ou 30 dígitos, veio "' + sidcBruto + '"');
    }
    const soDigitos = /^\d{30}$/.test(sidc30);

    const sidc20 = getBaseSIDC(sidc30);
    const symbolSetCode = sidc20.substring(4, 6);
    const mainIcon = sidc20.substring(10, 16);
    const modifier1 = sidc20.substring(16, 18);
    const modifier2 = sidc20.substring(18, 20);

    // Zera os códigos brasileiros antes do milsymbol, como o Web.
    let renderSIDC = sidc20;
    if (hasExtensions(symbolSetCode, 'mainIcon', mainIcon)) {
        renderSIDC = renderSIDC.substring(0, 10) + '000000' + renderSIDC.substring(16, 20);
    }
    if (hasExtensions(symbolSetCode, 'modifier1', modifier1)) {
        renderSIDC = renderSIDC.substring(0, 16) + '00' + renderSIDC.substring(18, 20);
    }
    if (hasExtensions(symbolSetCode, 'modifier2', modifier2)) {
        renderSIDC = renderSIDC.substring(0, 18) + '00';
    }

    const targetSize = TAMANHO_PADRAO;
    // generateSymbol(sidc30, properties, targetSize, customColor = null): fillColor ausente vira null.
    const customColor = props.fillColor === undefined ? null : props.fillColor;
    const baseOptions = { size: targetSize * 0.5, frame: true, fill: true, strokeWidth: 3, colorMode: 'Light' };
    if (customColor) baseOptions.fillColor = customColor;

    const symbolBase = new ms.Symbol(renderSIDC, baseOptions);
    const svgBase = symbolBase.asSVG();
    const viewBoxBase = viewBoxDe(svgBase);

    const textModifiers = extractTextModifiers(props);
    const hasText = Object.keys(textModifiers).length > 0;

    let svgString;
    let boxWidth = targetSize;
    let boxHeight = targetSize;
    let drawnSymbol = symbolBase;

    if (!hasText) {
        svgString = svgBase;
    } else {
        const optionsWithText = Object.assign({}, baseOptions, textModifiers);
        const symbolWithText = new ms.Symbol(renderSIDC, optionsWithText);
        drawnSymbol = symbolWithText;
        svgString = symbolWithText.asSVG();
        const viewBoxExpanded = viewBoxDe(svgString);
        const growthFactorX = viewBoxExpanded.width / viewBoxBase.width;
        const growthFactorY = viewBoxExpanded.height / viewBoxBase.height;
        if (growthFactorX > 1.01) boxWidth = Math.round(targetSize * growthFactorX);
        if (growthFactorY > 1.01) boxHeight = Math.round(targetSize * growthFactorY);
    }

    svgString = applyBrazilianModifications(svgString, sidc30, symbolSetCode, customColor);

    // O canvas do Web tem o tamanho de fitDrawSize(natural, caixa × nitidez); a largura lógica é
    // esse tamanho dividido pela nitidez (svg-to-png.js e generateSymbol).
    const nitidez = SYMBOL_BITMAP_PIXEL_RATIO;
    const natural = tamanhoNatural(svgString);
    const desenho = fitDrawSize(natural.width, natural.height, boxWidth * nitidez, boxHeight * nitidez);
    const width = desenho.width / nitidez;
    const height = desenho.height / nitidez;
    const iconOffset = militaryIconOffset(drawnSymbol.getAnchor(), drawnSymbol.getSize(), { width, height });

    return {
        svg: corrigirTextoParaQt(svgString),
        svgWeb: svgString,
        largura: width,
        altura: height,
        ancoraX: iconOffset ? iconOffset[0] : 0,
        ancoraY: iconOffset ? iconOffset[1] : 0,
        iconOffset: iconOffset || null,
        valido: soDigitos && drawnSymbol.isValid() === true,
        sidc: sidc30,
        avisos: colherAvisos(),
    };
}

// ---------------------------------------------------------------------------------------------
// Medida de coordenação: generateSymbolBlob de coordination_measure_generator.js, sem o canvas
// ---------------------------------------------------------------------------------------------

// Cópia de DEFAULT_SIZE e de escalaLogicaDe (privados no módulo do Web); a paridade os testa.
const TAMANHO_PADRAO_MEDIDA = 80;

function escalaLogicaDe(pointData, baseViewBox) {
    if (Number.isFinite(pointData.escalaLogica) && pointData.escalaLogica > 0) {
        return pointData.escalaLogica;
    }
    const maiorMedida = Math.max(baseViewBox.width, baseViewBox.height);
    if (!Number.isFinite(maiorMedida) || maiorMedida <= 0) {
        throw new Error('Point ' + pointData.code + ' has an unusable viewBox');
    }
    return (pointData.tamanhoBase || TAMANHO_PADRAO_MEDIDA) / maiorMedida;
}

const geradorMedida = new CoordinationMeasureGenerator();

// O MapLibre põe o ponto do ícone indicado por icon-anchor sobre a coordenada e depois desloca
// por icon-offset. O marcador do QGIS centra o desenho no ponto: o deslocamento do CENTRO é o
// icon-offset mais a distância do centro ao ponto de ancoragem.
function deslocamentoDoCentro(anchor, iconOffset, largura, altura) {
    let dx = iconOffset[0];
    let dy = iconOffset[1];
    const a = anchor || 'center';
    if (a.indexOf('bottom') >= 0) dy -= altura / 2;
    if (a.indexOf('top') >= 0) dy += altura / 2;
    if (a.indexOf('left') >= 0) dx += largura / 2;
    if (a.indexOf('right') >= 0) dx -= largura / 2;
    return [Math.round(dx * 100) / 100 || 0, Math.round(dy * 100) / 100 || 0];
}

export function gerarMedida(props) {
    props = props || {};
    colherAvisos();
    const g = geradorMedida;
    const pointCode = codigoDesenhavel(props.pointCode, props.echelonCode);
    if (!pointCode) throw new Error('Property pointCode is required');
    const pointData = g.catalog[pointCode];
    if (!pointData) throw new Error('Point ' + pointCode + ' not found in catalog');

    // generateSymbolBlob: o ponto que desenha a partir das propriedades (Setor de Tiro, campo
    // minado por tipo de mina) monta o SVG por montarSvg; o svg estático é só o padrão dele.
    let svg = typeof pointData.montarSvg === 'function' ? pointData.montarSvg(props) : pointData.svg;
    svg = g.applyCustomColor(svg, props.fillColor || 'none');
    if (pointData.isNucleo) svg = g.aplicarSituacaoDoNucleo(svg, props.status);

    const escala = escalaLogicaDe(pointData, g.extractDimensions(svg));
    if (g.hasExternalText(props, pointData)) svg = g.addExternalTexts(svg, props, pointData);

    const viewBox = g.extractDimensions(svg);
    const nitidez = SYMBOL_BITMAP_PIXEL_RATIO;
    const largura = Math.max(1, Math.round(viewBox.width * escala * nitidez));
    const altura = Math.max(1, Math.round(viewBox.height * escala * nitidez));
    const natural = tamanhoNatural(svg);
    const desenho = fitDrawSize(natural.width, natural.height, largura, altura);
    const width = desenho.width / nitidez;
    const height = desenho.height / nitidez;
    const iconOffset = iconOffsetFor(viewBox, pointData.anchorSvg, escala);
    const centro = deslocamentoDoCentro(pointData.anchor, iconOffset, width, height);

    return {
        svg: corrigirTextoParaQt(svg),
        svgWeb: svg,
        largura: width,
        altura: height,
        ancoraX: centro[0],
        ancoraY: centro[1],
        anchor: pointData.anchor || 'center',
        iconOffset,
        codigo: pointCode,
        valido: true,
        avisos: colherAvisos(),
    };
}

// ---------------------------------------------------------------------------------------------
// Símbolo de engenharia: engineeringSvg do Web, INTACTO, sobre o DOM mínimo (dom-minimo.js),
// e o tamanho do generate() sem o canvas
// ---------------------------------------------------------------------------------------------

export function gerarEngenharia(props) {
    props = props || {};
    colherAvisos();
    const codigo = props.pointCode;
    const desfazer = instalarDomTemporario();
    let d;
    try {
        d = engineeringSvg(codigo, props);
    } finally {
        desfazer();
    }
    // EngineeringSymbolGenerator.generate: convertSvgToPngBlob(svg, round(w × nitidez), round(h × nitidez)).
    const nitidez = SYMBOL_BITMAP_PIXEL_RATIO;
    const natural = tamanhoNatural(d.svg);
    const desenho = fitDrawSize(natural.width, natural.height,
        Math.max(1, Math.round(d.width * nitidez)), Math.max(1, Math.round(d.height * nitidez)));
    const iconOffset = d.iconOffset;
    return {
        svg: d.svg,
        svgWeb: d.svg,
        largura: desenho.width / nitidez,
        altura: desenho.height / nitidez,
        // anchor 'center': o deslocamento do centro é o próprio iconOffset.
        ancoraX: Math.round(iconOffset[0] * 100) / 100 || 0,
        ancoraY: Math.round(iconOffset[1] * 100) / 100 || 0,
        anchor: 'center',
        iconOffset,
        larguraDesenho: d.width,
        alturaDesenho: d.height,
        rascunho: engineeringDraft(codigo, props.engineering),
        valido: true,
        avisos: colherAvisos(),
    };
}

// Rascunho normalizado (padrões, campos permitidos, texto cortado em 40) e erros de validação
// do formulário: as mesmas funções que o painel do Web usa.
export function rascunhoEngenharia(codigo, dados) {
    return engineeringDraft(codigo, dados);
}

export function errosEngenharia(codigo, valores) {
    return errorsFor(engineeringItem(codigo), valores || {});
}

export function marcasDeRampa(inclinacao) {
    return rampChevronCount(inclinacao);
}

// SVG do milsymbol SEM o pós-processamento brasileiro, com as opções do gerador. Serve ao
// teste de pior caso (o comparador de paridade tem de reprovar este desenho para um SIDC
// brasileiro) e à depuração; o plugin não o usa para desenhar.
export function svgMilsymbolBruto(sidc, opcoes) {
    const base = { size: TAMANHO_PADRAO * 0.5, frame: true, fill: true, strokeWidth: 3, colorMode: 'Light' };
    return new ms.Symbol(getBaseSIDC(normalizeSIDC(sidc)), Object.assign(base, opcoes || {})).asSVG();
}

export function codigosDeMedida() {
    return Object.keys(geradorMedida.catalog);
}

export const versao = {
    milsymbol: ms.version || null,
    razaoDePixel: SYMBOL_BITMAP_PIXEL_RATIO,
};
