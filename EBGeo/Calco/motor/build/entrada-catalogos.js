// Entrada que monta o catalogos.json da interface (construtor de SIDC e seletor de medida) a
// partir dos módulos do EBGeo Web. Roda em node no build; o resultado é dado puro, sem código.

import { SYMBOL_SET_TABLES } from '@js/military_tools/military_symbol_tool/data/index.js';
import {
    MILITARY_DATA, ENGAGEMENT_BAR_DATA, getEchelonData, getSpecialModifierData, isCommandApplicable,
    isModifier1Applicable, isModifier2Applicable, isEngagementBarApplicable, isEchelonApplicable,
    isHqTfApplicable, getTextModifiersConfig,
} from '@js/military_tools/military_symbol_tool/military_constants.js';
import { getExtensionNumbers, hasExtensions } from '@js/military_tools/military_symbol_tool/brazilian_extension_catalog.js';
import { COORDINATION_POINTS_CATALOG, getAvailableTextFields } from '@js/military_tools/coordination_measure_tool/coordination_points_catalog.js';
import { ECHELON_CODES, SUPPLY_CLASSES, UI_DATA } from '@js/military_tools/coordination_measure_tool/coordination_measure_constants.js';
import { FAMILIAS_DE_ESCALAO, ESCALAO_PADRAO } from '@js/military_tools/coordination_measure_tool/familias-de-escalao.js';
import { ENGINEERING_CATALOG } from '@js/military_tools/engineering_symbol_tool/engineering_catalog.js';
import { engineeringFields } from '@js/military_tools/engineering_symbol_tool/engineering_fields.js';
import { engineeringDraft } from '@js/military_tools/engineering_symbol_tool/engineering_generator.js';

// Formulário de cada item de engenharia (engineering_fields.js), com o rascunho padrão de
// engineeringDraft. A validação de verdade é a função errorsFor, exposta no bundle
// (Motor.engenharia_erros); aqui vão as regras como dado, para a interface marcar o campo.
function engenharia() {
    const itens = ENGINEERING_CATALOG.map((item) => {
        const f = engineeringFields[item.number] || { fields: [] };
        return {
            numero: item.number,
            codigo: String(item.number),
            titulo: item.title,
            variantes: item.variants.map((v, i) => ({ indice: i, rotulo: v.label, ancora: v.anchor })),
            rotuloVariante: f.variant || null,
            fixo: f.fixed || '',
            extra: f.extra || '',
            campos: f.fields.map((c) => ({
                chave: c.key, rotulo: c.label, tipo: c.kind, padrao: c.value, ajuda: c.help || '',
                opcoes: c.options ? c.options.map(([valor, rotulo]) => ({ valor, rotulo })) : undefined,
                quando: c.when ? { campo: c.when[0], valor: c.when[1] } : undefined,
            })),
            rascunhoPadrao: engineeringDraft(item.number),
        };
    });
    return {
        itens,
        totalVariantes: itens.reduce((n, i) => n + i.variantes.length, 0),
        validacao: {
            inteiro: '^(?:\d+|\?)?$',
            decimal: '^(?:\d+(?:[.,]\d+)?|\?)?$',
            textoMaximo: 40,
            regras: [
                { item: 16, campo: 'maximum', regra: 'minimum <= maximum', mensagem: 'O gabarito máximo deve ser igual ou maior que o mínimo.' },
                { item: 17, campo: 'totalWidth', regra: 'roadWidth <= totalWidth', mensagem: 'A largura total não pode ser menor que a largura da pista.' },
                { item: 18, campo: 'totalWidth', regra: 'roadWidth <= totalWidth', mensagem: 'A largura total não pode ser menor que a largura da pista.' },
            ],
            rampa: 'marcas: 0 abaixo de 5% ou sem valor; 1 até 7%; 2 até 10%; 3 até 14%; 4 acima de 14%',
        },
    };
}

function entradaDeTabela(e) {
    const saida = {
        codigo: e.code,
        nome: e.entity_portugues || e.entity || e.name || '',
        nome_en: e.entity || e.name || '',
    };
    for (const [orig, dest] of [
        ['entity_type_portugues', 'tipo'], ['entity_subtype_portugues', 'subtipo'],
        ['entity_type', 'tipo_en'], ['entity_subtype', 'subtipo_en'],
        ['modifier_portugues', 'nome'], ['modifier', 'nome_en'], ['category', 'categoria'],
        ['description', 'descricao'], ['extension', 'extensao'],
    ]) {
        if (e[orig] !== undefined && e[orig] !== null && e[orig] !== '') saida[dest] = e[orig];
    }
    return saida;
}

function extensoes(conjunto, tipo, lista) {
    const saida = {};
    for (const e of lista || []) {
        if (e.code && hasExtensions(conjunto, tipo, e.code) && !(e.code in saida)) {
            saida[e.code] = getExtensionNumbers(conjunto, tipo, e.code);
        }
    }
    return saida;
}

export function montarCatalogos() {
    const porConjunto = {};
    for (const { value: codigo, label } of MILITARY_DATA.symbolSets) {
        const tabela = SYMBOL_SET_TABLES[codigo] || {};
        const icones = tabela['main icon'] || [];
        const mod1 = tabela['modifier 1'] || [];
        const mod2 = tabela['modifier 2'] || [];
        porConjunto[codigo] = {
            nome: label,
            nome_tabela: tabela.nome_portugues || tabela.name || '',
            icones: icones.map(entradaDeTabela),
            mod1: mod1.map(entradaDeTabela),
            mod2: mod2.map(entradaDeTabela),
            extensoes: {
                icone: extensoes(codigo, 'mainIcon', icones),
                mod1: extensoes(codigo, 'modifier1', mod1),
                mod2: extensoes(codigo, 'modifier2', mod2),
            },
            escalao: getEchelonData(codigo),
            modificadorEspecial: getSpecialModifierData(codigo),
            aplicavel: {
                comando: isCommandApplicable(codigo),
                mod1: isModifier1Applicable(codigo),
                mod2: isModifier2Applicable(codigo),
                barraEngajamento: isEngagementBarApplicable(codigo),
                escalao: isEchelonApplicable(codigo),
                qgFt: isHqTfApplicable(codigo),
            },
            camposTexto: getTextModifiersConfig(codigo),
        };
    }

    const medidas = {};
    for (const [codigo, p] of Object.entries(COORDINATION_POINTS_CATALOG)) {
        medidas[codigo] = {
            nome: p.name,
            categoria: p.category || '',
            ancora: p.anchor || 'center',
            campos: getAvailableTextFields(codigo),
            nucleo: p.isNucleo === true,
            forcaTarefa: p.isForcaTarefa === true,
        };
        // Capítulo VII (2026-10-04): a cor com que o tipo nasce (destruições em verde), a
        // direção da Base de fogos e o par de direções do Setor de Tiro, que o painel lê.
        if (p.corPadrao) medidas[codigo].corPadrao = p.corPadrao;
        if (p.direcao) medidas[codigo].direcao = { rotulo: p.direcao.rotulo };
        if (p.setorDeTiro) medidas[codigo].setorDeTiro = true;
    }
    const categorias = {};
    for (const [codigo, m] of Object.entries(medidas)) {
        (categorias[m.categoria] = categorias[m.categoria] || []).push(codigo);
    }

    return {
        militar: {
            formato: MILITARY_DATA.format,
            identidades: MILITARY_DATA.standardIdentity,
            conjuntos: MILITARY_DATA.symbolSets,
            status: MILITARY_DATA.status,
            qgFtSimulado: MILITARY_DATA.hqTfDummy,
            escaloes: MILITARY_DATA.echelon,
            mobilidade: MILITARY_DATA.mobility,
            lideranca: MILITARY_DATA.leadership,
            modificadorEspecial: MILITARY_DATA.specialModifier,
            modificadorEspecialEquipamento: MILITARY_DATA.specialModifierEquipment,
            barraEngajamento: ENGAGEMENT_BAR_DATA,
            porConjunto,
        },
        engenharia: engenharia(),
        medida: {
            lista: UI_DATA.pointsList,
            subtiposNucleo: UI_DATA.echelonSubtypes,
            subtiposNucleoFT: UI_DATA.echelonFTSubtypes,
            definicoesCampos: UI_DATA.textFieldDefinitions,
            escaloes: ECHELON_CODES,
            classesSuprimento: SUPPLY_CLASSES,
            familias: FAMILIAS_DE_ESCALAO,
            escalaoPadrao: ESCALAO_PADRAO,
            porCodigo: medidas,
            categorias,
        },
    };
}
