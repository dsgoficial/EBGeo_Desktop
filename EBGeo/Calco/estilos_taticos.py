# -*- coding: utf-8 -*-
"""
Estilos QGIS das linhas táticas do calco: Linha de Coordenação, Linha de Limite,
Seta e Frente Ocupada.

A camada guarda só o EIXO e os atributos (schema.py); o desenho é estilo nativo,
feito de Geometry Generators cujas expressões portam o algoritmo do EBGeo Web
(frontend/src/js/military_tools/ do ebgeo_web). Nada aqui depende do plugin na hora
de desenhar: o estilo gravado no layer_styles do GeoPackage desenha num QGIS limpo.

As expressões vivem em expressoes/*.exp, em pedaços com marcadores @@NOME@@ que o
compositor deste módulo substitui. A expressão final de cada Geometry Generator é
autocontida.

Unidades e escala (regra confirmada com o chefe em 2026-10-04, a mesma dos estilos
pontuais e de formas):
  - Distâncias do Web são geodésicas na esfera do turf (R = 6.371.008,8 m). A expressão
    projeta o eixo para uma Transversa de Mercator local ESFÉRICA (mesmo R), centrada no
    centroide da feição arredondado a 0,1 grau, e trabalha em metros no plano; o fator
    k de metro de terreno para unidade do plano vale 1. A variante em EPSG:3857 com
    k = 1 / cos(lat do centroide) continua disponível (PROJECAO = '3857').
  - Pixel do Web vira 0,26 mm de papel (MM_POR_PX, o mesmo de estilos_pontuais.py).
  - Metros de terreno por pixel do Web no zoom de criação z0 (convenção MapLibre de
    512 px): 78271,517 x cos(lat) / 2^z0.
  - Escala de TERRENO na feição: @map_scale dividido pelo fator do SRC do mapa medido
    na própria feição (_escala_terreno.exp), para o resultado não variar com o SRC do
    projeto (Mercator, UTM ou geográfico).
  - zoom_corr ligado com âncora (created_zoom > 0): preso ao TERRENO. Glifos em km de
    terreno; traço e texto valem px x metros-por-px(z0) de terreno, convertidos em mm
    pela escala de terreno, com os tetos do Web (traço 60 px, texto 255 px).
  - zoom_corr desligado com âncora: preso à TELA. Traço e texto fixos em mm (px x 0,26);
    glifos fixos em mm também: o km de criação vira px no zoom de criação e o px vira
    km de terreno pela escala atual (o 2^(z0 - z) do Web), entre 0,001 e 50 km
    (espaçamento entre 0,002 e 500 km).
  - Sem âncora (created_zoom nulo ou 0), como no Web: traço e texto fixos em mm e
    glifos no km gravado.
"""
import os
import re

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsGeometryGeneratorSymbolLayer,
    QgsLabelLineSettings,
    QgsLineSymbol,
    QgsMapLayer,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsSymbolLayer,
    QgsTextBufferSettings,
    QgsTextFormat,
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

DIR_EXPRESSOES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'expressoes')

# px do Web em mm de papel (a mesma constante de estilos_pontuais.py e estilos_formas.py).
MM_POR_PX = 0.26

# 'tmerc' (Transversa de Mercator local esférica) ou '3857' (Mercator com fator k).
PROJECAO = 'tmerc'

TIPOS_ESTILO = ('coordination_line', 'boundary', 'arrow', 'occupied_front')

# Catálogo MD33 de coordination_line_catalog.js (LINEAR_SYMBOLS), chaveado pelo id.
CATALOGO_LINHA = {
    '290100': {'nome': 'Linha de obstáculos', 'glifo': 'peak', 'interrompe': True, 'span': 1},
    '290199': {'nome': 'Linha de barreiras', 'glifo': 'diamond', 'interrompe': True, 'span': 1},
    '290202': {'nome': 'Fosso anticarro', 'glifo': 'teeth', 'interrompe': True, 'continuo': True,
               'preenchido': True, 'span': 1, 'prof': 0.82, 'flat': 0},
    '290302': {'nome': 'Cerca de arame', 'glifo': 'asterisk', 'interrompe': False, 'span': 1},
    '290303': {'nome': 'Cerca de arame dupla', 'glifo': 'double-asterisk', 'interrompe': False, 'span': 1.6},
    '290307': {'nome': 'Concertina', 'glifo': 'coil', 'interrompe': False, 'span': 0.8},
    '290308': {'nome': 'Concertina dupla', 'glifo': 'coil-double', 'interrompe': False, 'span': 1,
               'trilhos': 1, 'gap': 0.7},
    '290309': {'nome': 'Concertina tripla', 'glifo': 'coil-triple', 'interrompe': False, 'span': 1,
               'trilhos': 1, 'gap': 1.35},
    '290999-01': {'nome': 'Sapa', 'glifo': 'zigzag', 'interrompe': True, 'continuo': True,
                  'span': 1, 'prof': 0.6, 'flat': 0},
    '290999-02': {'nome': 'Trincheira', 'glifo': 'zigzag', 'interrompe': True, 'continuo': True,
                  'span': 1, 'prof': 0.7, 'flat': 0.41},
}
SIMBOLO_PADRAO = '290199'

_MARCADOR_SIMPLES = re.compile(r'@@([A-Z_]+)@@')
_MARCADOR_INCLUSAO = re.compile(r'@@([A-Z_]+):(.*?)@@', re.S)
_COMENTARIO = re.compile(r'/\*.*?\*/', re.S)
_LIGACAO = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(::=|:=)\s*(.*)$')
_BLOCO_TOKEN = re.compile(r'@@(SEJA|EM|FIM)@@')
_RESERVADOS = {'SEJA', 'EM', 'FIM'}
_contador_blocos = [0]


# ---------------------------------------------------------------------------
# Compositor de expressões
#
# Por que blocos SEJA e não uma cadeia de with_variable: medido no QGIS 4.0.0 em
# 2026-10-04, o tempo de PARSE de uma expressão dobra a cada nível de função com
# parâmetros declarados aninhada (with_variable, if, array_foreach, project...):
# 0,035 s com 16 with_variable aninhados, 0,59 s com 20, 9,2 s com 24. Funções
# variádicas (array, map, coalesce, min, max, array_cat, collect_geometries), CASE,
# operadores e o índice [] não dobram. O QGIS reparseia a expressão a cada clone do
# símbolo, então a profundidade vira custo de desenho.
#
# Um bloco
#     @@SEJA@@
#     nome := expressão
#     outro := expressão que usa @nome
#     @@EM@@
#     corpo que usa @nome e @outro
#     @@FIM@@
# vira UM with_variable cujo valor é um mapa montado por etapas: as ligações que não
# dependem umas das outras entram na mesma etapa (um map), e cada etapa nova é um
# with_variable sobre o mapa anterior. @nome vira @ebgN['nome']. O corpo fica sob um
# único nível, e só a cadeia curta das etapas aninha.
# ---------------------------------------------------------------------------

def ler_expressao(nome):
    """Texto do arquivo expressoes/<nome>.exp sem os comentários /* */."""
    with open(os.path.join(DIR_EXPRESSOES, nome + '.exp'), encoding='utf-8') as f:
        return _COMENTARIO.sub('', f.read()).strip()


def _padroes(projecao):
    return {
        'PROJ': ler_expressao('_projecao' if projecao == 'tmerc' else '_projecao_3857'),
        'ESCALA_TERRENO': ler_expressao('_escala_terreno'),
        'M_POR_PX_CRIACAO': ler_expressao('_m_por_px_criacao'),
        'FATOR_SOLO': ler_expressao('_fator_solo'),
        'FATOR_PIXEL': ler_expressao('_fator_pixel'),
    }


def _referencias(expr, nomes):
    return {n for n in re.findall(r'@([A-Za-z_][A-Za-z0-9_]*)', expr) if n in nomes}


def _compilar_bloco(ligacoes_txt, corpo):
    """
    Ligação 'nome := expr' vira entrada do mapa; macro 'nome ::= expr' é inlinada no
    texto (entre parênteses) onde @nome aparecer, sem custo de etapa, para aritmética
    barata que só existe para ser lida.
    """
    ligacoes = []
    for linha in ligacoes_txt.splitlines():
        m = _LIGACAO.match(linha)
        if m:
            ligacoes.append([m.group(1), m.group(2) == '::=', m.group(3)])
        elif linha.strip():
            if not ligacoes:
                raise ValueError('ligação sem nome: ' + linha.strip())
            ligacoes[-1][2] += ' ' + linha.strip()
    nomes = [n for n, _, _ in ligacoes]
    if not nomes:
        raise ValueError('bloco SEJA sem ligações')
    if len(set(nomes)) != len(nomes):
        raise ValueError('nome repetido no bloco: {}'.format(nomes))
    _contador_blocos[0] += 1
    h = 'ebg{}'.format(_contador_blocos[0])
    ligados = [n for n, macro, _ in ligacoes if not macro]
    macros = {}        # nome -> texto expandido
    deps_macro = {}    # nome -> ligações (não macros) de que a macro depende

    def expandir(texto):
        for n, txt in macros.items():
            texto = re.sub(r'@' + n + r'(?![A-Za-z0-9_])', lambda _m, t=txt: '(' + t + ')', texto)
        for n in ligados:
            texto = re.sub(r'@' + n + r'(?![A-Za-z0-9_])', "@{}['{}']".format(h, n), texto)
        return texto

    etapas, atual = [], []
    for i, (n, macro, e) in enumerate(ligacoes):
        refs = _referencias(e, nomes)
        posteriores = refs - set(nomes[:i])
        if posteriores:
            raise ValueError('{} usa nomes ainda não ligados: {}'.format(n, posteriores))
        deps = set()
        for r in refs:
            deps |= deps_macro[r] if r in macros else {r}
        texto = expandir(e.strip())
        if macro:
            macros[n] = texto
            deps_macro[n] = deps
            continue
        if deps & {x for x, _ in atual}:
            etapas.append(atual)
            atual = []
        atual.append((n, texto))
    if atual:
        etapas.append(atual)

    corpo = expandir(corpo.strip())
    if not etapas:
        return corpo

    def mapa(etapa):
        return 'map(' + ', '.join("'{}', {}".format(n, e) for n, e in etapa) + ')'

    tubo = mapa(etapas[0])
    for etapa in etapas[1:]:
        tubo = "with_variable('{h}', {t}, map_concat(@{h}, {m}))".format(h=h, t=tubo, m=mapa(etapa))
    return "with_variable('{h}', {t},{q}{c})".format(h=h, t=tubo, c=corpo, q=chr(10))


def _compilar_blocos(texto):
    """Compila os blocos SEJA/EM/FIM, do mais interno para fora."""
    while True:
        pilha, alvo = [], None
        for m in _BLOCO_TOKEN.finditer(texto):
            tipo = m.group(1)
            if tipo == 'SEJA':
                pilha.append([m.start(), m.end(), None, None])
            elif tipo == 'EM':
                if not pilha:
                    raise ValueError('@@EM@@ sem @@SEJA@@')
                pilha[-1][2], pilha[-1][3] = m.start(), m.end()
            else:
                if not pilha or pilha[-1][2] is None:
                    raise ValueError('@@FIM@@ sem @@SEJA@@ e @@EM@@')
                ini, fim_seja, ini_em, fim_em = pilha.pop()
                alvo = (ini, fim_seja, ini_em, fim_em, m.start(), m.end())
                break  # o primeiro FIM fecha o bloco mais interno
        if alvo is None:
            if pilha:
                raise ValueError('@@SEJA@@ sem @@FIM@@')
            return texto
        ini, fim_seja, ini_em, fim_em, ini_fim, fim_fim = alvo
        compilado = _compilar_bloco(texto[fim_seja:ini_em], texto[fim_em:ini_fim])
        texto = texto[:ini] + compilado + texto[fim_fim:]


def compor(nome, projecao=None, **subs):
    """
    Monta o texto do arquivo <nome>.exp substituindo os marcadores (sem compilar blocos).

    @@CHAVE@@ recebe subs['CHAVE'] ou um padrão (PROJ, ESCALA_TERRENO, M_POR_PX_CRIACAO,
    FATOR_SOLO, FATOR_PIXEL). Com nome None, compõe o texto dado em _TEXTO.
    @@NOME:K=V;K=V@@ inclui _<nome>.exp com aqueles marcadores, entre parênteses
    quando é expressão e cru quando é lista de ligações. Marcador sem
    valor é erro, para não sair expressão truncada.
    """
    projecao = projecao or PROJECAO
    valores = _padroes(projecao)
    valores.update({k: str(v) for k, v in subs.items()})

    def simples(m):
        chave = m.group(1)
        if chave in _RESERVADOS:
            return m.group(0)
        if chave not in valores:
            raise KeyError('marcador sem valor: @@{}@@ em {}'.format(chave, nome))
        return valores[chave]

    def inclusao(m):
        sub = {}
        for par in m.group(2).split(';'):
            k, v = par.split('=', 1)
            sub[k.strip()] = v.strip()
        txt = compor('_' + m.group(1).lower(), projecao, **sub)
        return txt if ':=' in txt else '(' + txt + ')'

    texto = ler_expressao(nome) if nome else valores.pop('_TEXTO')
    for _ in range(10):
        novo = _MARCADOR_INCLUSAO.sub(inclusao, _MARCADOR_SIMPLES.sub(simples, texto))
        if novo == texto:
            break
        texto = novo
    return texto


def finalizar(texto):
    """Compila os blocos e renumera os nomes internos (ebg1, ebg2...) por ordem de aparição."""
    texto = _compilar_blocos(texto)
    if '@@' in texto:
        raise ValueError('marcador não resolvido: ' + texto[texto.index('@@'):][:60])
    ordem = {}
    for m in re.finditer(r'\bebg(\d+)\b', texto):
        ordem.setdefault(m.group(0), 'ebg{}'.format(len(ordem) + 1))
    return re.sub(r'\bebg\d+\b', lambda m: ordem[m.group(0)], texto)


def _offset(linha, dist, lado, projecao):
    return compor('_offset_pontos', projecao, LINHA=linha, DIST=dist, LADO=lado)


# ---------------------------------------------------------------------------
# Expressões por tipo
# ---------------------------------------------------------------------------

def expr_linha_coordenacao(codigo, projecao=None):
    """
    Expressões da Linha de Coordenação de um símbolo do catálogo (código desconhecido
    cai na 290199, como resolveSymbol do Web). Devolve {'linha': expr,
    'preenchimento': expr ou None}. No símbolo preenchido (290202), 'linha' só desenha
    o eixo cru quando nenhum dente cabe.
    """
    sim = CATALOGO_LINHA.get(codigo, CATALOGO_LINHA[SIMBOLO_PADRAO])
    if sim.get('continuo'):
        comum = dict(FLAT=sim['flat'], PROF=sim['prof'])
        if sim.get('preenchido'):
            return {
                'linha': finalizar(compor('linha_coordenacao_continua', projecao, VAZIO='@g',
                                          CORPO='NULL', DENTE='NULL', **comum)),
                'preenchimento': finalizar(compor('linha_coordenacao_continua', projecao, VAZIO='NULL',
                                                  CORPO='1', DENTE=compor('dente_preenchido', projecao),
                                                  **comum)),
            }
        return {
            'linha': finalizar(compor('linha_coordenacao_continua', projecao, VAZIO='@g', CORPO='1',
                                      DENTE=compor('dente_aberto', projecao), **comum)),
            'preenchimento': None,
        }

    glifo = compor('glifo_' + sim['glifo'].replace('-', '_'), projecao)
    eixo = compor('eixo_interrompido', projecao) if sim['interrompe'] else 'array(@g)'
    if sim.get('trilhos'):
        trilhos = compor('trilho', projecao,
                         OFFSET=_offset('@g', '@s * {}'.format(sim['gap']), '-90', projecao))
    else:
        trilhos = 'array()'
    expr = compor('linha_coordenacao_glifos', projecao, SPAN=sim['span'], EIXO=eixo,
                  TRILHOS=trilhos, GLIFO=glifo)
    return {'linha': finalizar(expr), 'preenchimento': None}


def _limite_subs(projecao):
    return {'LIMITE': compor('_limite', projecao)}


def expr_limite_linhas(projecao=None):
    escalao = compor('_limite_escalao', projecao, FORMA=compor('limite_forma_linhas', projecao))
    return finalizar(compor('limite_linhas', projecao, ESCALAO_LINHAS=escalao, **_limite_subs(projecao)))


def expr_limite_circulos(projecao=None):
    escalao = compor('_limite_escalao', projecao, FORMA=compor('limite_forma_circulo', projecao))
    return finalizar(compor('limite_circulos', projecao, ESCALAO_CIRCULOS=escalao, **_limite_subs(projecao)))


def expr_limite_rotulo(lado, norte, projecao=None):
    """
    Expressões dos rótulos de um lado da Linha de Limite: 'top' (text_top, à esquerda,
    rumo - 90) ou 'bottom' (text_bottom, à direita, rumo + 90). Com norte=False a
    geometria é um segmento paralelo ao eixo por instância (o QGIS assenta o rótulo
    sobre ele, girado e de pé); com norte=True é um ponto por instância.
    """
    graus = '-90' if lado == 'top' else '90'
    campo = '"text_top"' if lado == 'top' else '"text_bottom"'
    forma = '@pt' if norte else 'make_line(project(@pt, @s, @az + pi()), project(@pt, @s, @az))'
    subs = _limite_subs(projecao)
    ex = {
        'texto': campo,
        'filtro': finalizar(compor('limite_rotulo_filtro', projecao, CAMPO=campo,
                                   NORTE='true' if norte else 'false')),
        'geometria': finalizar(compor('limite_rotulo_geometria', projecao, LADO=graus,
                                      FORMA_ROTULO=forma, **subs)),
    }
    if norte:
        ex['quadrante'] = finalizar(compor('limite_rotulo_quadrante', projecao, LADO=graus, **subs))
    return ex


def expr_seta(projecao=None):
    meio = '@w / 2'
    ramo = compor('seta_ramo', projecao,
                  OFFSET_D=_offset('@ax', meio, '90', projecao),
                  OFFSET_E=_offset('@ax', meio, '-90', projecao),
                  AEROMOVEL=compor('seta_aeromovel', projecao))
    return finalizar(compor('seta', projecao, RAMO=ramo))


def expr_frente_ocupada(projecao=None):
    return finalizar(compor('frente_ocupada', projecao))


def expr_largura_px(coluna, padrao, teto, zoom=True):
    """
    Largura em mm de um tamanho em px do Web. Com zoom, e zoom_corr ligado com âncora,
    vale px x 2^(z - z0) (preso ao terreno) até o teto em px; senão, px x 0,26 mm.
    """
    base = 'CASE WHEN "{c}" > 0 THEN "{c}" ELSE {p} END'.format(c=coluna, p=padrao) if coluna else str(padrao)
    if not zoom:
        return '{} * {}'.format(base, MM_POR_PX)
    return finalizar(compor(None, _TEXTO='min({t}, {b} * (@@FATOR_PIXEL@@)) * {mm}'.format(
        t=teto, b=base, mm=MM_POR_PX)))


def expr_cor(coluna_cor, coluna_opacidade, cor_padrao='#000000'):
    """Cor com a opacidade da coluna no canal alfa."""
    return ("set_color_part(coalesce(\"{c}\", '{p}'), 'alpha', 255 * min(1, max(0, coalesce(\"{o}\", 1))))"
            .format(c=coluna_cor, p=cor_padrao, o=coluna_opacidade))


# ---------------------------------------------------------------------------
# Símbolos
# ---------------------------------------------------------------------------

def _linha(largura, cor, arredondada=True):
    sl = QgsSimpleLineSymbolLayer()
    sl.setWidthUnit(Qgis.RenderUnit.Millimeters)
    if arredondada:
        sl.setPenCapStyle(Qt.PenCapStyle.RoundCap)
        sl.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, QgsProperty.fromExpression(largura))
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, QgsProperty.fromExpression(cor))
    return QgsLineSymbol([sl])


def _preenchimento(cor_fundo, cor_borda, largura_borda, arredondada=True):
    sl = QgsSimpleFillSymbolLayer()
    sl.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
    if arredondada:
        sl.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, QgsProperty.fromExpression(cor_fundo))
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, QgsProperty.fromExpression(cor_borda))
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, QgsProperty.fromExpression(largura_borda))
    return QgsFillSymbol([sl])


def _gerador(expr, subsimbolo):
    gg = QgsGeometryGeneratorSymbolLayer.create({'geometryModifier': expr})
    gg.setSymbolType(subsimbolo.type())
    gg.setSubSymbol(subsimbolo)
    return gg


def _simbolo_linha(camadas):
    """QgsLineSymbol só com os Geometry Generators dados (sem a linha padrão)."""
    sym = QgsLineSymbol()
    sym.deleteSymbolLayer(0)
    for c in camadas:
        sym.appendSymbolLayer(c)
    return sym


def simbolo_linha_coordenacao(codigo, projecao=None):
    ex = expr_linha_coordenacao(codigo, projecao)
    largura = expr_largura_px('line_width', 4, 60)
    cor = expr_cor('color', 'opacity')
    camadas = []
    if ex['preenchimento']:
        camadas.append(_gerador(ex['preenchimento'], _preenchimento(cor, cor, largura)))
    camadas.append(_gerador(ex['linha'], _linha(largura, cor)))
    return _simbolo_linha(camadas)


def renderer_linha_coordenacao(projecao=None):
    raiz = QgsRuleBasedRenderer.Rule(None)
    for codigo, sim in CATALOGO_LINHA.items():
        regra = QgsRuleBasedRenderer.Rule(simbolo_linha_coordenacao(codigo, projecao), 0, 0,
                                          "\"symbol_code\" = '{}'".format(codigo),
                                          '{} ({})'.format(sim['nome'], codigo))
        raiz.appendChild(regra)
    # resolveSymbol do Web: código desconhecido ou vazio desenha a Linha de barreiras.
    senao = QgsRuleBasedRenderer.Rule(simbolo_linha_coordenacao(SIMBOLO_PADRAO, projecao), 0, 0,
                                      'ELSE', 'Código desconhecido ({})'.format(SIMBOLO_PADRAO))
    senao.setIsElse(True)
    raiz.appendChild(senao)
    return QgsRuleBasedRenderer(raiz)


def renderer_limite(projecao=None):
    largura = expr_largura_px('line_width', 4, 60)
    cor = expr_cor('color', 'opacity')
    borda_circulo = expr_largura_px(None, 2, 60)
    sym = _simbolo_linha([
        _gerador(expr_limite_circulos(projecao), _preenchimento(cor, cor, borda_circulo, arredondada=False)),
        _gerador(expr_limite_linhas(projecao), _linha(largura, cor)),
    ])
    return QgsSingleSymbolRenderer(sym)


def renderer_seta(projecao=None):
    fundo = expr_cor('fill_color', 'fill_opacity', '#3f4fb5')
    borda = expr_cor('line_color', 'line_opacity', '#3f4fb5')
    largura = expr_largura_px('line_width', 3, 60, zoom=False)
    poly = _preenchimento(fundo, borda, largura, arredondada=False)
    poly.symbolLayer(0).setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)
    return QgsSingleSymbolRenderer(_simbolo_linha([_gerador(expr_seta(projecao), poly)]))


def renderer_frente_ocupada(projecao=None):
    largura = expr_largura_px('line_width', 4, 60, zoom=False)
    cor = expr_cor('color', 'opacity')
    return QgsSingleSymbolRenderer(_simbolo_linha([_gerador(expr_frente_ocupada(projecao), _linha(largura, cor))]))


# ---------------------------------------------------------------------------
# Rotulagem da Linha de Limite
# ---------------------------------------------------------------------------

def _config_rotulo(ex, norte):
    s = QgsPalLayerSettings()
    s.fieldName = ex['texto']
    s.isExpression = True
    s.geometryGenerator = ex['geometria']
    s.geometryGeneratorEnabled = True
    s.labelPerPart = True
    if norte:
        # Voltado ao norte: rotação 0 e a caixa ancorada pela borda que encara a linha.
        s.geometryGeneratorType = Qgis.GeometryType.Point
        s.placement = Qgis.LabelPlacement.OverPoint
    else:
        # Colado à linha: o rótulo corre centrado sobre um segmento paralelo ao eixo, e o
        # QGIS o gira com o segmento e o mantém de pé na tela (computeTextRotation).
        s.geometryGeneratorType = Qgis.GeometryType.Line
        s.placement = Qgis.LabelPlacement.Line
        ls = s.lineSettings()
        ls.setPlacementFlags(Qgis.LabelLinePlacementFlag.OnLine)
        ls.setLineAnchorPercent(0.5)
        ls.setAnchorType(QgsLabelLineSettings.AnchorType.Strict)
        ls.setAnchorTextPoint(QgsLabelLineSettings.AnchorTextPoint.CenterOfText)
        ls.setOverrunDistance(1000)
        ls.setOverrunDistanceUnit(Qgis.RenderUnit.Millimeters)
        s.upsidedownLabels = Qgis.UpsideDownLabelHandling.FlipUpsideDownLabels

    fmt = QgsTextFormat()
    fmt.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setSize(35 * MM_POR_PX)
    fmt.setColor(QColor('#000000'))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSizeUnit(Qgis.RenderUnit.Millimeters)
    buf.setSize(2 * MM_POR_PX)  # text-halo-width: 2 px
    buf.setColor(QColor('#ffffff'))
    fmt.setBuffer(buf)
    s.setFormat(fmt)

    tamanho = expr_largura_px('text_size', 35, 255)
    opacidade = '100 * min(1, max(0, coalesce("opacity", 1)))'
    P = QgsPalLayerSettings.Property
    props = s.dataDefinedProperties()
    props.setProperty(P.Size, QgsProperty.fromExpression(tamanho))
    props.setProperty(P.Color, QgsProperty.fromExpression("coalesce(\"color\", '#000000')"))
    props.setProperty(P.FontOpacity, QgsProperty.fromExpression(opacidade))
    props.setProperty(P.BufferOpacity, QgsProperty.fromExpression(opacidade))
    if norte:
        props.setProperty(P.OffsetQuad, QgsProperty.fromExpression(ex['quadrante']))
    s.setDataDefinedProperties(props)

    # text-allow-overlap e text-ignore-placement do Web: o rótulo sempre aparece.
    s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapAtNoCost)
    s.placementSettings().setAllowDegradedPlacement(True)
    s.obstacleSettings().setIsObstacle(False)
    return s


def rotulagem_limite(projecao=None):
    """Quatro regras: text_top e text_bottom, colados à linha ou voltados ao norte."""
    raiz = QgsRuleBasedLabeling.Rule(None)
    for norte in (False, True):
        for lado in ('top', 'bottom'):
            ex = expr_limite_rotulo(lado, norte, projecao)
            regra = QgsRuleBasedLabeling.Rule(_config_rotulo(ex, norte))
            regra.setFilterExpression(ex['filtro'])
            regra.setDescription('text_{}{}'.format(lado, ' voltado ao norte' if norte else ''))
            raiz.appendChild(regra)
    return QgsRuleBasedLabeling(raiz)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def aplicar_estilo(layer, tipo, projecao=None):
    """Aplica à camada o renderer (e a rotulagem, na Linha de Limite) do tipo."""
    if tipo == 'coordination_line':
        layer.setRenderer(renderer_linha_coordenacao(projecao))
        layer.setLabelsEnabled(False)
    elif tipo == 'boundary':
        layer.setRenderer(renderer_limite(projecao))
        layer.setLabeling(rotulagem_limite(projecao))
        layer.setLabelsEnabled(True)
    elif tipo == 'arrow':
        layer.setRenderer(renderer_seta(projecao))
        layer.setLabelsEnabled(False)
    elif tipo == 'occupied_front':
        layer.setRenderer(renderer_frente_ocupada(projecao))
        layer.setLabelsEnabled(False)
    else:
        raise ValueError('tipo sem estilo tático: {}'.format(tipo))
    layer.triggerRepaint()


def salvar_estilo_padrao(layer, nome=None, descricao='Estilo tático do EBGeo Desktop'):
    """
    Grava o estilo atual da camada no layer_styles do GeoPackage como padrão
    (useAsDefault=True), para a camada abrir desenhada sem o plugin.
    Devolve (sucesso, mensagem).
    """
    nome = nome or layer.dataProvider().uri().table() or layer.name()
    if hasattr(layer, 'saveStyleToDatabaseV2'):
        res, msg = layer.saveStyleToDatabaseV2(nome, descricao, True, '')
        R = QgsMapLayer.SaveStyleResult
        # O SLD não exprime Geometry Generator; só a QML e a gravação no banco importam.
        valor = getattr(res, 'value', res)
        ok = not (int(valor) & (R.DatabaseWriteFailed.value | R.QmlGenerationFailed.value))
        return ok, msg
    msg = layer.saveStyleToDatabase(nome, descricao, True, '')
    return not msg, msg
