# -*- coding: utf-8 -*-
"""
Estilo nativo da Área de Coordenação (capítulo VII do MD33-C-01), o tipo
`coordination_area` do calco.

A camada guarda só o POLÍGONO e os atributos (schema.py); o desenho de cada tipo
(dentes, elos, portões, minas, os "M", a linha de chamada e os textos) é feito por
Geometry Generators e por rótulos com gerador de geometria, cujas expressões portam
`coordination_area_drawing.js` e `coordination_area_catalog.js` do EBGeo Web. Nada aqui
depende do plugin na hora de desenhar: gravado no layer_styles, o estilo desenha num QGIS
sem o plugin. As expressões vivem em expressoes/_area*.exp e area_*.exp e passam pelo
mesmo compositor das linhas táticas (estilos_taticos.compor e finalizar).

A Correção de Zoom (`zoom_corr`, zoomCorrectionEnabled do Web) é UMA só para o desenho e
para os textos: ligada, a unidade s fica em metros de TERRENO e o texto cresce com a carta a
partir do zoom de criação; desligada, tudo fica fixo na tela. A hachura com a carta tem
piso de 4 px (ou 2,5 espessuras) na tela: abaixo dele o período dobra, como no Web. As
espessuras de traço são px fixos na tela nos dois casos, como no Web.

O interior é selecionável: no QGIS a seleção e a identificação são pela geometria, não pelo
estilo, então a área com preenchimento transparente ou só com hachura seleciona por dentro.
"""
import math

from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsGeometryGeneratorSymbolLayer,
    QgsLinePatternFillSymbolLayer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsPalLayerSettings,
    QgsPointPatternFillSymbolLayer,
    QgsProperty,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbolLayer,
    QgsTextBackgroundSettings,
    QgsTextBufferSettings,
    QgsTextFormat,
)
from qgis.PyQt.QtCore import QSizeF, Qt
from qgis.PyQt.QtGui import QColor, QFont

from .estilos_taticos import compor, finalizar

MM_POR_PX = 25.4 / 96
FONTE = 'Noto Sans'

# Catálogo do Web (COORDINATION_AREA_SYMBOLS), chaveado pelo id. 'padroes' são os valores de
# aparência que o tipo impõe ao trocar de símbolo (updateSymbol), nas colunas do calco.
_BASE = {'line_color': '#000000', 'line_width': 3.0, 'fill_color': '#000000', 'opacity': 0.0,
         'hatch_type': 'none', 'hatch_enabled': False}
VERDE_OBSTACULO = '#00B04E'
CATALOGO_AREA = {
    '150000': {'nome': 'Área genérica', 'borda': 'linha', 'padroes': dict(_BASE)},
    '151100': {'nome': 'Terreno Restritivo', 'borda': 'linha',
               'padroes': dict(_BASE, opacity=1.0, hatch_type='diagonal-right', hatch_enabled=True)},
    '151199-01': {'nome': 'Terreno Impeditivo', 'borda': 'linha',
                  'padroes': dict(_BASE, opacity=1.0, hatch_type='cross-diagonal', hatch_enabled=True)},
    '151203': {'nome': 'Ponto Forte', 'borda': 'dentes', 'escalao': True, 'posicao': 'interna',
               'padroes': dict(_BASE, line_width=5.0)},
    '151000': {'nome': 'Zona fortificada', 'borda': 'elos', 'padroes': dict(_BASE)},
    '170999-01': {'nome': 'Volume de aproximação de base', 'borda': 'linha', 'portoes': True,
                  'posicao': 'externa', 'padroes': dict(_BASE, line_width=4.0)},
    '270800': {'nome': 'Área minada', 'borda': 'minada', 'minas': True,
               'padroes': dict(_BASE, line_color=VERDE_OBSTACULO, fill_color=VERDE_OBSTACULO)},
}
SIMBOLO_PADRAO = '150000'
CHAVE_ULTIMO_TIPO = 'EBGeo/calco/ultimo_tipo_area'  # QgsSettings: a área nova nasce no último tipo
BORDA_DA_DECORACAO = ('151000', '270800')  # a decoração desenha a borda (OUTLINE_HIDDEN_CODES)

POSICOES_TEXTO = [('borda', 'Sobre a borda'), ('interna', 'Interna'), ('externa', 'Externa')]
ESTILOS_TRACO = [('solid', 'Sólida'), ('dashed', 'Tracejada'), ('dotted', 'Pontilhada'), ('dash-dot', 'Traço-ponto'),
                 ('long-dash', 'Traço longo'), ('short-dash', 'Traço curto'), ('dot-dot-dash', 'Ponto-ponto-traço')]
HACHURAS = [('none', 'Nenhuma'), ('diagonal-right', 'Diagonal /'), ('diagonal-left', 'Diagonal \\'),
            ('horizontal', 'Horizontal'), ('vertical', 'Vertical'), ('cross', 'Cruz +'),
            ('cross-diagonal', 'Cruz X'), ('dots', 'Pontos')]
TIPOS_MINA = [('ap', 'Antipessoal'), ('ac', 'Anticarro'), ('qualquer', 'Qualquer tipo'), ('vazia', 'Vazia')]
MINAS_PADRAO = ['qualquer', 'ap', 'ac']
ESCALOES = ['XXXXXX', 'XXXXX', 'XXXX', 'XXX', 'XX', 'X', 'III', 'II', 'I', 'ooo', 'oo', 'o', 'Ø', '++']
NOMES_PORTAO = ['ALFA', 'BRAVO', 'CHARLIE', 'DELTA', 'ECHO', 'FOXTROT', 'GOLF', 'HOTEL', 'INDIA', 'JULIETT']
# Um rótulo por regra, e cada regra custa ~17 ms de preparo a CADA desenho, haja ou não VAB na
# camada (medido em 2026-10-04: 30 áreas, 0,44 s com 12 e 0,34 s com 6; pôr as regras como filhas
# de uma regra-mãe filtrada pelo código não poupa nada). O manual mostra 3 portões; os traços
# dos portões além do sexto continuam desenhados, só sem o nome.
MAX_ROTULOS_PORTAO = 6

# Período perpendicular da hachura em múltiplos de hatch_spacing (HATCH_GEOMETRY do Web):
# ângulo do QGIS -> (fator, tipos que o ligam).
_HACHURAS = [
    (45, math.sqrt(0.5), ('diagonal-right', 'cross-diagonal')),
    (135, math.sqrt(0.5), ('diagonal-left', 'cross-diagonal')),
    (0, 2.0, ('horizontal', 'cross')),
    (90, 2.0, ('vertical', 'cross')),
]
COND_HACHURA = "coalesce(\"hatch_enabled\", false) AND coalesce(\"hatch_type\", 'none') <> 'none'"


def posicao_padrao(codigo):
    return CATALOGO_AREA.get(codigo, CATALOGO_AREA[SIMBOLO_PADRAO]).get('posicao', 'borda')


def rotulo_escalao(valor):
    """echelonLabel: os pontos gravados como 'o' viram bolinhas."""
    return {'ooo': '•••', 'oo': '••', 'o': '•'}.get(valor or '', valor or '')


def tamanho_inicial_km(latitude, z, px=18):
    """defaultSymbolSizeKm: 18 px na tela no zoom da criação, arredondado ao metro."""
    metros = round(px * 78271.517 * math.cos(math.radians(latitude)) / (2 ** z))
    return min(200.0, max(0.001, metros / 1000.0))


def troca_de_simbolo(atuais, novo):
    """
    Atributos a gravar ao trocar o tipo (updateSymbol do Web), com o symbol_code: cada valor de
    aparência que a área ainda tem no padrão do tipo ANTERIOR passa ao padrão do novo; valor
    escolhido fica. A regra é de regras.py, que o guardião aplica em qualquer edição; aqui ela
    serve à área que nasce no último tipo (gerenciador).
    """
    from .regras import padroes_da_troca_area
    return padroes_da_troca_area(atuais, novo)


# ---------------------------------------------------------------------------
# Expressões
# ---------------------------------------------------------------------------

def expr_linhas():
    """areaTextLines: as linhas do bloco, na ordem, sem as vazias (lista de texto)."""
    cod = ("CASE WHEN \"symbol_code\" IN ('150000', '151100', '151199-01', '151203', '151000', '170999-01', "
           "'270800') THEN \"symbol_code\" ELSE '150000' END")
    ini = "trim(coalesce(\"gdh_ini\", ''))"
    fim = "trim(coalesce(\"gdh_fim\", ''))"
    return ("array_filter(array("
            "array_to_string(array_filter(array(trim(coalesce(\"tipo\", '')), trim(coalesce(\"identificacao\", ''))), "
            "@element <> ''), '  '), "
            "CASE WHEN ({c}) = '170999-01' AND trim(coalesce(\"altitude_max\", '')) <> '' "
            "THEN 'Altu Máx  ' || trim(\"altitude_max\") END, "
            "CASE WHEN ({c}) = '170999-01' AND trim(coalesce(\"altitude_min\", '')) <> '' "
            "THEN 'Altu Min  ' || trim(\"altitude_min\") END, "
            "CASE WHEN {i} <> '' AND {f} <> '' THEN {i} || ' - ' || {f} ELSE {i} || {f} END, "
            "CASE WHEN ({c}) <> '170999-01' THEN trim(coalesce(\"outras_info\", '')) END"
            "), coalesce(@element, '') <> '')").format(c=cod, i=ini, f=fim)


def _subs(projecao=None, **extra):
    linhas = expr_linhas()
    subs = {
        'AREA': compor('_area', projecao),
        'AREA_POSICAO': compor('_area_posicao', projecao),
        'AREA_CENTRO': compor('_area_centro', projecao),
        'AREA_CRUZAMENTOS': compor('_area_cruzamentos', projecao),
        'AREA_PORTOES': compor('_area_portoes', projecao),
        'AREA_MINAS': compor('_area_minas', projecao),
        'AREA_EXTERNA': compor('_area_externa', projecao, LINHAS=linhas),
        'MINA_ELIPSE': compor('_mina_elipse', projecao),
        'LINHAS': linhas,
    }
    subs.update(extra)
    return subs


def expr(nome, projecao=None, **extra):
    """Expressão final (autocontida) do arquivo expressoes/<nome>.exp."""
    return finalizar(compor(nome, projecao, **_subs(projecao, **extra)))


DECORACOES = {
    # código -> geradores de linha (nome da expressão, largura em px, tracejado da borda?)
    '151203': [('area_dentes', 'largura', False)],
    '151000': [('area_elos', 'largura', False)],
    '170999-01': [('area_portoes', 'portao', False)],
    '270800': [('area_minada_borda', 'largura', True), ('area_minas_contorno', 'portao', False)],
}


def expr_tamanho_px(base_px, teto=255):
    """mm de um tamanho em px do Web que escala com a carta (Correção de Zoom ligada e âncora)."""
    return finalizar(compor(None, _TEXTO='min({t}, ({b}) * (@@FATOR_PIXEL@@)) * {mm}'.format(
        t=teto, b=base_px, mm=MM_POR_PX)))


def expr_fator_texto(base_px, teto=255):
    """Razão tamanho escalado / tamanho base (icon-size da caixa do Web)."""
    return finalizar(compor(None, _TEXTO='min({t} / ({b}), (@@FATOR_PIXEL@@))'.format(t=teto, b=base_px)))


def expr_letra_px():
    """decorationUnitPx x 1,2: a unidade s em px no zoom de criação (4 a 160 px)."""
    txt = ('1.2 * min(160, max(4, min(200, max(0.001, CASE WHEN "symbol_size_km" > 0 THEN "symbol_size_km" '
           'ELSE 0.3 END)) * 1000 / CASE WHEN coalesce("created_zoom", 0) > 0 THEN (@@M_POR_PX_CRIACAO@@) '
           'ELSE (@@ESCALA_TERRENO@@) * 0.00026458333 END))')
    return finalizar(compor(None, _TEXTO=txt))


def expr_distancia_hachura(fator):
    """
    mm entre as linhas da hachura: hatch_spacing x fator px. Com a Correção de Zoom ligada a
    hachura fica no terreno (x 2^(z - z0)) e dobra até passar do piso de max(4, 2,5 x
    espessura) px (groundHatchPeriodKm); desligada, fica fixa na tela (padrão de pixels).
    """
    txt = ('with_variable(\'p0\', CASE WHEN "hatch_spacing" > 0 THEN "hatch_spacing" ELSE 8 END * {f}, '
           'CASE WHEN "zoom_corr" IS NOT NULL AND NOT "zoom_corr" THEN @p0 ELSE '
           'with_variable(\'pz\', @p0 * (@@FATOR_PIXEL@@), with_variable(\'fl\', max(4, 2.5 * CASE WHEN '
           '"hatch_line_width" > 0 THEN "hatch_line_width" ELSE 2 END), '
           'CASE WHEN @pz < @fl THEN @pz * 2 ^ ceil(log(2, @fl / @pz) - 1e-9) ELSE @pz END)) END) * {mm}'
           ).format(f=fator, mm=MM_POR_PX)
    return finalizar(compor(None, _TEXTO=txt))


def expr_cor_alfa(col_cor, alfa, padrao='#000000'):
    return "set_color_part(coalesce(\"{c}\", '{p}'), 'alpha', 255 * min(1, max(0, {a})))".format(
        c=col_cor, p=padrao, a=alfa)


# ---------------------------------------------------------------------------
# Símbolos
# ---------------------------------------------------------------------------

def _p(e):
    return QgsProperty.fromExpression(e)


_TRACOS = {
    'dashed': (8, 4), 'dotted': (2, 3), 'dash-dot': (8, 4, 2, 4), 'long-dash': (16, 6),
    'short-dash': (4, 4), 'dot-dot-dash': (2, 2, 2, 2, 8, 2),
}


def _camadas_linha(cor, largura_px, tracejado):
    """Camadas de linha: contínua e, com tracejado, a tracejada por line_style (LINE_STYLE_DASHARRAY)."""
    mm = '({}) * {}'.format(largura_px, MM_POR_PX)
    cond = "coalesce(\"line_style\", 'solid') IN ({})".format(', '.join("'{}'".format(k) for k in _TRACOS))
    casos = ' '.join("WHEN \"line_style\" = '{}' THEN '{}'".format(k, ';'.join(str(x) for x in v))
                     for k, v in _TRACOS.items())
    camadas = []
    for tr in ((False, True) if tracejado else (False,)):
        sl = QgsSimpleLineSymbolLayer()
        sl.setWidthUnit(Qgis.RenderUnit.Millimeters)
        sl.setPenCapStyle(Qt.PenCapStyle.FlatCap)
        sl.setPenJoinStyle(Qt.PenJoinStyle.RoundJoin)
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(mm))
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p(cor))
        if tracejado:
            if tr:
                sl.setUseCustomDashPattern(True)
                sl.setCustomDashPatternUnit(Qgis.RenderUnit.Millimeters)
                sl.setDataDefinedProperty(QgsSymbolLayer.Property.CustomDash, _p(
                    "array_to_string(array_foreach(string_to_array(CASE {} ELSE '1;0' END, ';'), "
                    "to_real(@element) * {}), ';')".format(casos, mm)))
                sl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(cond))
            else:
                sl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('NOT ({})'.format(cond)))
        camadas.append(sl)
    return camadas


def _gerador(expressao, simbolo):
    gg = QgsGeometryGeneratorSymbolLayer.create({'geometryModifier': expressao})
    gg.setSymbolType(simbolo.type())
    gg.setSubSymbol(simbolo)
    return gg


LARGURA = 'CASE WHEN "line_width" > 0 THEN "line_width" ELSE 3 END'
LARGURA_PORTAO = 'max(2, 0.75 * ({}))'.format(LARGURA)
COR = "coalesce(\"line_color\", '#000000')"


def _simbolo_vazio(classe):
    s = classe()
    s.deleteSymbolLayer(0)
    return s


def simbolo_base():
    """
    Preenchimento, hachura e contorno, comuns a todos os tipos (uma regra só: o QGIS reparseia
    as expressões de cada regra a cada desenho, medido em 2026-10-04).
    """
    sym = _simbolo_vazio(QgsFillSymbol)
    # preenchimento liso: alvo do clique por dentro no Web; sob hachura, opacidade zero
    fill = QgsSimpleFillSymbolLayer()
    fill.setStrokeStyle(Qt.PenStyle.NoPen)
    fill.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p(expr_cor_alfa(
        'fill_color', 'CASE WHEN coalesce("hatch_enabled", false) THEN 0 ELSE coalesce("opacity", 0) END')))
    sym.appendSymbolLayer(fill)
    # hachura: cor do preenchimento (hatchColor é reserva) com a opacidade da área
    cor_h = "set_color_part(coalesce(\"fill_color\", \"hatch_color\", '#000000'), 'alpha', "             "255 * min(1, max(0, coalesce(\"opacity\", 1))))"
    largura_h = 'CASE WHEN "hatch_line_width" > 0 THEN "hatch_line_width" ELSE 2 END * {}'.format(MM_POR_PX)
    for ang, fator, tipos in _HACHURAS:
        lp = QgsLinePatternFillSymbolLayer()
        lp.setLineAngle(ang)
        lp.setDistanceUnit(Qgis.RenderUnit.Millimeters)
        lp.setDataDefinedProperty(QgsSymbolLayer.Property.LineDistance, _p(expr_distancia_hachura(fator)))
        sub = _simbolo_vazio(QgsLineSymbol)
        ln = QgsSimpleLineSymbolLayer()
        ln.setWidthUnit(Qgis.RenderUnit.Millimeters)
        ln.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(largura_h))
        ln.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p(cor_h))
        sub.appendSymbolLayer(ln)
        lp.setSubSymbol(sub)
        lp.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(
            '{} AND "hatch_type" IN ({})'.format(COND_HACHURA, ', '.join("'{}'".format(t) for t in tipos))))
        sym.appendSymbolLayer(lp)
    pp = QgsPointPatternFillSymbolLayer()
    pp.setDistanceXUnit(Qgis.RenderUnit.Millimeters)
    pp.setDistanceYUnit(Qgis.RenderUnit.Millimeters)
    passo = '(CASE WHEN "hatch_spacing" > 0 THEN "hatch_spacing" ELSE 8 END) * {}'.format(MM_POR_PX)
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.DistanceX, _p(passo))
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.DistanceY, _p(passo))
    msub = _simbolo_vazio(QgsMarkerSymbol)
    dot = QgsSimpleMarkerSymbolLayer()
    dot.setStrokeStyle(Qt.PenStyle.NoPen)
    dot.setSizeUnit(Qgis.RenderUnit.Millimeters)
    dot.setDataDefinedProperty(QgsSymbolLayer.Property.Size, _p(largura_h))
    dot.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p(cor_h))
    msub.appendSymbolLayer(dot)
    pp.setSubSymbol(msub)
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p("{} AND \"hatch_type\" = 'dots'".format(COND_HACHURA)))
    sym.appendSymbolLayer(pp)
    # contorno, menos onde a decoração é a borda (elos, borda minada): no Web a camada do
    # contorno fica com opacidade zero nesses tipos
    dono = '"symbol_code" IN ({})'.format(', '.join("'{}'".format(c) for c in BORDA_DA_DECORACAO))
    for sl in _camadas_linha(COR, LARGURA, True):
        cond = sl.dataDefinedProperties().property(QgsSymbolLayer.Property.LayerEnabled).expressionString()
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('NOT ({}) AND ({})'.format(dono, cond)))
        sym.appendSymbolLayer(sl)
    return sym


def simbolo_decoracao(codigo, projecao=None):
    """As decorações do tipo (dentes, elos, portões, borda minada, minas); None se não há."""
    if codigo not in DECORACOES:
        return None
    sym = _simbolo_vazio(QgsFillSymbol)
    if codigo == '270800':  # minas cheias (AP, AC) por baixo das linhas
        sub = _simbolo_vazio(QgsFillSymbol)
        f = QgsSimpleFillSymbolLayer()
        f.setStrokeStyle(Qt.PenStyle.NoPen)
        f.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p(COR))
        sub.appendSymbolLayer(f)
        sym.appendSymbolLayer(_gerador(expr('area_minas_cheias', projecao), sub))
    for nome, largura, tracejado in DECORACOES[codigo]:
        sub = _simbolo_vazio(QgsLineSymbol)
        for sl in _camadas_linha(COR, LARGURA if largura == 'largura' else LARGURA_PORTAO, tracejado):
            sub.appendSymbolLayer(sl)
        sym.appendSymbolLayer(_gerador(expr(nome, projecao), sub))
    return sym


def simbolo_chamada(projecao=None):
    """A linha de chamada do texto externo (1,5 px), de qualquer tipo."""
    sym = _simbolo_vazio(QgsFillSymbol)
    sub = _simbolo_vazio(QgsLineSymbol)
    for sl in _camadas_linha(COR, '1.5', False):
        sub.appendSymbolLayer(sl)
    sym.appendSymbolLayer(_gerador(expr('area_chamada', projecao), sub))
    return sym


def renderer_area(projecao=None):
    """
    Regras: a área (preenchimento, hachura, contorno), uma regra por tipo com as decorações
    dele (os tipos sem decoração ficam como regra vazia, para a legenda) e a linha de chamada.
    Código desconhecido desenha como a Área genérica, que não tem decoração.
    """
    raiz = QgsRuleBasedRenderer.Rule(None)
    raiz.appendChild(QgsRuleBasedRenderer.Rule(simbolo_base(), 0, 0, '', 'Área'))
    for codigo, sim in CATALOGO_AREA.items():
        raiz.appendChild(QgsRuleBasedRenderer.Rule(simbolo_decoracao(codigo, projecao), 0, 0,
                                                   "\"symbol_code\" = '{}'".format(codigo),
                                                   '{} ({})'.format(sim['nome'], codigo)))
    raiz.appendChild(QgsRuleBasedRenderer.Rule(simbolo_chamada(projecao), 0, 0, '', 'Linha de chamada do texto externo'))
    return QgsRuleBasedRenderer(raiz)


# ---------------------------------------------------------------------------
# Rótulos
# ---------------------------------------------------------------------------

def _rotulo(texto, geometria, tamanho_mm, negrito=False, caixa=False, por_parte=False,
            quadrante=None, rotacao=None, alinhamento=None, fator_caixa=None):
    s = QgsPalLayerSettings()
    s.fieldName = texto
    s.isExpression = True
    s.geometryGenerator = geometria
    s.geometryGeneratorEnabled = True
    s.geometryGeneratorType = Qgis.GeometryType.Point
    s.placement = Qgis.LabelPlacement.OverPoint
    s.labelPerPart = por_parte
    fmt = QgsTextFormat()
    f = QFont(FONTE)
    f.setBold(negrito)
    fmt.setFont(f)
    fmt.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setSize(14 * MM_POR_PX)
    fmt.setColor(QColor('#000000'))
    fmt.setLineHeight(1.2)
    buf = QgsTextBufferSettings()
    buf.setEnabled(not caixa)
    buf.setSizeUnit(Qgis.RenderUnit.Millimeters)
    buf.setSize(1.5 * MM_POR_PX)  # text-halo-width 1,5 px do Web onde não há caixa
    buf.setColor(QColor('#ffffff'))
    fmt.setBuffer(buf)
    if caixa:
        bg = QgsTextBackgroundSettings()
        bg.setEnabled(True)
        bg.setType(QgsTextBackgroundSettings.ShapeType.ShapeRectangle)
        bg.setSizeType(QgsTextBackgroundSettings.SizeType.SizeBuffer)
        bg.setSizeUnit(Qgis.RenderUnit.Millimeters)
        bg.setSize(QSizeF(4 * MM_POR_PX, 2 * MM_POR_PX))
        bg.setFillColor(QColor('#ffffff'))
        bg.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
        bg.setStrokeWidth(MM_POR_PX)  # borda de 1 px em qualquer zoom
        bg.setStrokeColor(QColor('#000000'))
        fmt.setBackground(bg)
    s.setFormat(fmt)
    P = QgsPalLayerSettings.Property
    dd = s.dataDefinedProperties()
    dd.setProperty(P.Size, _p(tamanho_mm))
    dd.setProperty(P.Color, _p(COR))
    if caixa:
        dd.setProperty(P.ShapeStrokeColor, _p(COR))
        if fator_caixa:
            dd.setProperty(P.ShapeSizeX, _p('4 * {} * ({})'.format(MM_POR_PX, fator_caixa)))
            dd.setProperty(P.ShapeSizeY, _p('2 * {} * ({})'.format(MM_POR_PX, fator_caixa)))
    if quadrante:
        dd.setProperty(P.OffsetQuad, _p(quadrante))
    if rotacao:
        dd.setProperty(P.LabelRotation, _p(rotacao))
    if alinhamento:
        dd.setProperty(P.MultiLineAlignment, _p(alinhamento))
    s.setDataDefinedProperties(dd)
    # text-allow-overlap e text-ignore-placement do Web: o rótulo sempre aparece
    s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapAtNoCost)
    s.placementSettings().setAllowDegradedPlacement(True)
    s.obstacleSettings().setIsObstacle(False)
    return s


TS = 'CASE WHEN "text_size" > 0 THEN "text_size" ELSE 14 END'


def expr_lista_json(coluna):
    """A coluna JSON como lista: ela chega como texto ou como lista, conforme a camada."""
    return ('CASE WHEN try(array_length("{c}"), -1) >= 0 THEN "{c}" ELSE try(from_json("{c}")) END'
            .format(c=coluna))


def expr_nome_portao(j):
    return "trim(coalesce(try(({})[{}]['nome']), ''))".format(expr_lista_json('portoes'), j)
COD = ("CASE WHEN \"symbol_code\" IN ('150000', '151100', '151199-01', '151203', '151000', '170999-01', "
       "'270800') THEN \"symbol_code\" ELSE '150000' END")


def rotulagem_area(projecao=None):
    raiz = QgsRuleBasedLabeling.Rule(None)
    linhas = expr_linhas()

    def regra(settings, filtro, descricao):
        r = QgsRuleBasedLabeling.Rule(settings)
        r.setFilterExpression(filtro)
        r.setDescription(descricao)
        raiz.appendChild(r)

    pos = ("CASE WHEN \"text_position\" IN ('borda', 'interna', 'externa') THEN \"text_position\" "
           "WHEN ({c}) = '170999-01' THEN 'externa' WHEN ({c}) = '151203' THEN 'interna' ELSE 'borda' END"
           ).format(c=COD)
    alinhamento = ("CASE WHEN ({p}) = 'externa' OR (({p}) = 'interna' AND ({c}) <> '151203') "
                   "THEN 'Left' ELSE 'Center' END").format(p=pos, c=COD)
    regra(_rotulo('array_to_string({}, char(10))'.format(linhas), expr('area_rotulo_ponto', projecao),
                  expr_tamanho_px(TS), caixa=True,
                  quadrante=expr('area_rotulo_quadrante', projecao),
                  rotacao=expr('area_rotulo_rotacao', projecao), alinhamento=alinhamento,
                  fator_caixa=expr_fator_texto(TS)),
          'array_length({}) > 0'.format(linhas), 'Texto (Tipo, Identificação, GDH)')
    e = "trim(coalesce(\"escalao\", ''))"
    escalao = ("CASE WHEN {e} = 'ooo' THEN '•••' WHEN {e} = 'oo' THEN '••' WHEN {e} = 'o' THEN '•' "
               "ELSE {e} END").format(e=e)
    regra(_rotulo(escalao, expr('area_escalao_ponto', projecao), expr_tamanho_px(TS), negrito=True, caixa=True,
                  fator_caixa=expr_fator_texto(TS)),
          "({}) = '151203' AND trim(coalesce(\"escalao\", '')) <> ''".format(COD), 'Escalão (Ponto Forte)')
    regra(_rotulo("'M'", expr('area_letras_m', projecao), expr_tamanho_px(expr_letra_px()), negrito=True,
                  por_parte=True),
          "({}) = '270800'".format(COD), 'Letras M (Área minada)')
    for j in range(MAX_ROTULOS_PORTAO):
        regra(_rotulo(expr_nome_portao(j), expr('area_portao_ponto', projecao, J=j),
                      expr_tamanho_px('0.85 * ({})'.format(TS)), negrito=True,
                      quadrante=expr('area_portao_quadrante', projecao, J=j)),
              "({c}) = '170999-01' AND NOT coalesce(\"portoes_ocultos\", false) AND {n} <> ''".format(
                  c=COD, n=expr_nome_portao(j)),
              'Portão {}'.format(j + 1))
    return QgsRuleBasedLabeling(raiz)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

EXPRESSAO_HACHURA_LIGADA = "coalesce(\"hatch_type\", 'none') <> 'none'"


def hachura_acompanha_o_tipo(layer):
    """
    hatch_enabled segue hatch_type (updateHatchType do Web): valor padrão aplicado na
    atualização, que o QGIS renova em qualquer caminho de edição, com ou sem o plugin. O
    formulário nativo só mostra o tipo de hachura; sem isto, escolher a hachura nele não a
    desenharia (o estilo pede as duas colunas, COND_HACHURA).
    """
    from qgis.core import QgsDefaultValue
    i = layer.fields().indexOf('hatch_enabled')
    if i >= 0:
        layer.setDefaultValueDefinition(i, QgsDefaultValue(EXPRESSAO_HACHURA_LIGADA, True))


def aplicar_estilo(layer, tipo='coordination_area', projecao=None):
    if tipo != 'coordination_area':
        return False
    layer.setRenderer(renderer_area(projecao))
    layer.setLabeling(rotulagem_area(projecao))
    layer.setLabelsEnabled(True)
    hachura_acompanha_o_tipo(layer)
    layer.triggerRepaint()
    return True


# ---------------------------------------------------------------------------
# Posição na borda (marcar portão), em Python puro sobre QgsGeometry
# ---------------------------------------------------------------------------

def razao_na_borda(geometria_wgs84, ponto_wgs84):
    """
    ratioAlongBorder: a razão (0 a 1, 4 casas) do ponto da borda mais próximo do ponto dado,
    medida do vértice mais ao norte no sentido horário, no mesmo plano local das expressões.
    """
    from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry,
                           QgsPointXY, QgsProject)
    g = QgsGeometry(geometria_wgs84)
    if g.isNull() or g.isEmpty():
        return None
    c = g.centroid().asPoint()
    crs = QgsCoordinateReferenceSystem(
        'PROJ:+proj=tmerc +lat_0={} +lon_0={} +k=1 +x_0=0 +y_0=0 +R=6371008.8 +units=m +no_defs'.format(
            round(c.y(), 1), round(c.x(), 1)))
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    pol = g.constGet()
    if hasattr(pol, 'geometryN'):
        pol = pol.geometryN(0)
    pol = pol.clone()
    gl = QgsGeometry(pol)
    gl.transform(tr)
    gl = gl.forcePolygonClockwise() if hasattr(gl, 'forcePolygonClockwise') else gl
    anel4326 = QgsGeometry(gl.constGet().exteriorRing().clone())
    anel = QgsGeometry(anel4326)
    anel4326.transform(tr, Qgis.TransformDirection.Reverse)
    pts = list(anel4326.vertices())[:-1]
    if len(pts) < 3:
        return None
    ymax = max(p.y() for p in pts)
    i0 = min((p.x(), i) for i, p in enumerate(pts) if p.y() >= ymax)[1]
    vs = list(anel.vertices())
    off = sum(math.hypot(vs[i + 1].x() - vs[i].x(), vs[i + 1].y() - vs[i].y()) for i in range(i0))
    L = anel.length()
    q = QgsGeometry.fromPointXY(QgsPointXY(ponto_wgs84))
    q.transform(tr)
    loc = anel.lineLocatePoint(q)
    if L <= 0 or loc < 0:
        return None
    return round(((loc - off) % L) / L, 4)
