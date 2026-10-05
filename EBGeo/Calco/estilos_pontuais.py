# -*- coding: utf-8 -*-
"""
Estilos nativos dos quatro tipos pontuais do calco (símbolo militar, medida de coordenação,
símbolo de engenharia e declinação magnética). Tudo é expressão nativa: o GeoPackage com o
estilo salvo em layer_styles desenha num QGIS sem o plugin.

Camadas do símbolo, de baixo para cima:
  1. marcador SVG com nome 'base64:' || "svg" (ligado quando há svg);
  2. marcador raster com nome 'base64:' || "bitmap_b64" (reserva: sem svg e com o PNG do .ebgeo);
  3. aviso vermelho (retângulo em volta do desenho e um x no ponto) quando svg_assinatura não
     bate com a assinatura recalculada dos campos que desenham, ou quando não há desenho algum.
O renderer só desenha as feições com "visivel" verdadeiro (nulo conta como verdadeiro).

TAMANHO. O Web desenha o ícone com icon-size = size, ou, com a correção de zoom ligada e o
zoom de referência gravado, min(10, size × 2^(zoom − createdAtZoom)): preso ao TERRENO até
dez vezes o tamanho de criação. Aqui isso vira milímetros por pixel lógico do desenho:
  correção ligada: min(10 × 0,2646, size × 78271,517 × cos(lat) / 2^created_zoom × 1000 / escala de terreno)
  (a escala de terreno vem de expressoes/_escala_terreno.exp, independente do SRC do mapa)
  correção desligada (ou created_zoom nulo ou 0): size × 0,2646
O fator 78271,517 m/px no zoom 0 é a convenção de 512 px do MapLibre (A CONFIRMAR lado a lado
com o Web: o KMZ do Web usa a de 256 px), e 0,2646 mm por pixel lógico é a tela de 96 dpi. A
largura do marcador é largura_px × fator, e o deslocamento é (ancora_dx, ancora_dy) × fator,
girado junto com o símbolo, como o icon-offset do MapLibre.
"""
from qgis.core import (
    QgsEllipseSymbolLayer, QgsMarkerSymbol, QgsProperty, QgsRasterMarkerSymbolLayer,
    QgsRuleBasedRenderer, QgsSimpleMarkerSymbolLayer, QgsSvgMarkerSymbolLayer, QgsSymbol,
    QgsSymbolLayer, Qgis,
)
from qgis.PyQt.QtGui import QColor

from . import simbolos

TIPOS = simbolos.TIPOS_SVG

# Tamanho padrão do Web quando "size" é nulo (symbol.layers.js: SYMBOL_SIZE e DECLINATION_SIZE).
TAMANHO_PADRAO = {'magnetic_declination': 0.6}
MM_POR_PX = 25.4 / 96  # um pixel lógico (CSS) a 96 dpi: 0,2646 mm
METROS_POR_PX_ZOOM0 = 78271.517
TETO_ICON_SIZE = 10
NOME_ESTILO = 'EBGeo calco'


def expressao_mm_por_px(tipo):
    """Milímetros na página por pixel lógico do desenho (ver o cabeçalho do módulo)."""
    s = TAMANHO_PADRAO.get(tipo, 1)
    return (
        "with_variable('s', coalesce(\"size\", {s}), "
        "if(coalesce(\"zoom_corr\", true) AND coalesce(\"created_zoom\", 0) > 0 AND coalesce(@map_scale, 0) > 0, "
        "min({teto}, @s * {m0} * cos(radians(y(transform(@geometry, @layer_crs, 'EPSG:4326')))) "
        "/ (2 ^ \"created_zoom\") * 1000 / ({escala})), "
        "@s * {mm}))"
    ).format(s=s, teto=TETO_ICON_SIZE * MM_POR_PX, m0=METROS_POR_PX_ZOOM0, mm=MM_POR_PX,
             escala=_escala_terreno())


def _escala_terreno():
    """
    Escala de TERRENO na feição, a mesma das linhas táticas (expressoes/_escala_terreno.exp).
    O @map_scale cru está nas unidades do SRC do mapa: em EPSG:3857 ele vale a escala de terreno
    dividida por cos(lat), e o símbolo saía 8 % menor a 23 graus S (medido na fixture 06).
    """
    from .estilos_taticos import compor, finalizar
    return finalizar(compor('_escala_terreno'))


def expressao_largura(tipo):
    return 'coalesce("largura_px", 0) * ({})'.format(expressao_mm_por_px(tipo))


def expressao_altura(tipo):
    return 'coalesce("altura_px", 0) * ({})'.format(expressao_mm_por_px(tipo))


def expressao_deslocamento(tipo):
    k = expressao_mm_por_px(tipo)
    return 'array(coalesce("ancora_dx", 0) * ({k}), coalesce("ancora_dy", 0) * ({k}))'.format(k=k)


def expressao_divergente(tipo):
    """
    Verdadeiro quando o desenho gravado não corresponde aos campos atuais (ou não existe). A
    assinatura da cor em maiúsculas (desenho gravado antes da cor sem caixa, simbolos.COLUNAS_COR)
    só é calculada quando a canônica não bate.
    """
    return ('CASE WHEN "svg" IS NULL THEN "bitmap_b64" IS NULL '
            'WHEN coalesce("svg_assinatura", \'\') = {a} THEN FALSE '
            'ELSE coalesce("svg_assinatura", \'\') <> {b} END').format(
                a=simbolos.expressao_assinatura(tipo), b=simbolos.expressao_assinatura(tipo, 'alta'))


def _girar(camada, tipo):
    if tipo != 'magnetic_declination':  # o Web não gira a declinação (setupDeclinationLayers)
        camada.setDataDefinedProperty(QgsSymbolLayer.Property.Angle,
                                      QgsProperty.fromExpression('coalesce("rotation", 0)'))


def _comum(camada, tipo, ligada):
    camada.setSizeUnit(Qgis.RenderUnit.Millimeters)
    camada.setOffsetUnit(Qgis.RenderUnit.Millimeters)
    camada.setDataDefinedProperty(QgsSymbolLayer.Property.Size, QgsProperty.fromExpression(expressao_largura(tipo)))
    camada.setDataDefinedProperty(QgsSymbolLayer.Property.Offset, QgsProperty.fromExpression(expressao_deslocamento(tipo)))
    camada.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, QgsProperty.fromExpression(ligada))
    _girar(camada, tipo)


def criar_simbolo(tipo):
    if tipo not in TIPOS:
        raise ValueError('Tipo pontual sem estilo: {}'.format(tipo))
    simbolo = QgsMarkerSymbol()
    simbolo.deleteSymbolLayer(0)

    svg = QgsSvgMarkerSymbolLayer('')
    _comum(svg, tipo, '"svg" IS NOT NULL')
    svg.setDataDefinedProperty(QgsSymbolLayer.Property.Name, QgsProperty.fromExpression("'base64:' || \"svg\""))
    simbolo.appendSymbolLayer(svg)

    raster = QgsRasterMarkerSymbolLayer('')
    _comum(raster, tipo, '"svg" IS NULL AND "bitmap_b64" IS NOT NULL')
    raster.setFixedAspectRatio(0)  # proporção da própria imagem
    raster.setDataDefinedProperty(QgsSymbolLayer.Property.Name, QgsProperty.fromExpression("'base64:' || \"bitmap_b64\""))
    simbolo.appendSymbolLayer(raster)

    divergente = expressao_divergente(tipo)
    vermelho = QColor(220, 0, 0)

    caixa = QgsEllipseSymbolLayer()
    caixa.setShape(QgsEllipseSymbolLayer.Shape.Rectangle)
    caixa.setFillColor(QColor(0, 0, 0, 0))
    caixa.setStrokeColor(vermelho)
    caixa.setStrokeWidth(0.5)
    caixa.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
    caixa.setSymbolWidthUnit(Qgis.RenderUnit.Millimeters)
    caixa.setSymbolHeightUnit(Qgis.RenderUnit.Millimeters)
    caixa.setOffsetUnit(Qgis.RenderUnit.Millimeters)
    caixa.setDataDefinedProperty(QgsSymbolLayer.Property.Width, QgsProperty.fromExpression(
        'max(2, {})'.format(expressao_largura(tipo))))
    caixa.setDataDefinedProperty(QgsSymbolLayer.Property.Height, QgsProperty.fromExpression(
        'max(2, {})'.format(expressao_altura(tipo))))
    caixa.setDataDefinedProperty(QgsSymbolLayer.Property.Offset, QgsProperty.fromExpression(expressao_deslocamento(tipo)))
    caixa.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, QgsProperty.fromExpression(divergente))
    _girar(caixa, tipo)
    simbolo.appendSymbolLayer(caixa)

    cruz = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Cross2, 4)
    cruz.setColor(vermelho)
    cruz.setStrokeColor(vermelho)
    cruz.setStrokeWidth(0.6)
    cruz.setSizeUnit(Qgis.RenderUnit.Millimeters)
    cruz.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, QgsProperty.fromExpression(divergente))
    simbolo.appendSymbolLayer(cruz)

    simbolo.setDataDefinedProperty(QgsSymbol.Property.Opacity,
                                   QgsProperty.fromExpression('coalesce("opacity", 1) * 100'))
    return simbolo


def criar_renderer(tipo):
    raiz = QgsRuleBasedRenderer.Rule(None)
    regra = QgsRuleBasedRenderer.Rule(criar_simbolo(tipo), 0, 0, 'coalesce("visivel", true)',
                                      'Visível', 'Feições com visivel verdadeiro')
    raiz.appendChild(regra)
    return QgsRuleBasedRenderer(raiz)


def aplicar_estilo(layer, tipo):
    """Aplica o estilo do tipo à camada (não salva; ver salvar_estilo_padrao)."""
    layer.setRenderer(criar_renderer(tipo))
    layer.triggerRepaint()
    return layer.renderer()


def salvar_estilo_padrao(layer, nome=NOME_ESTILO, descricao='Estilo do calco EBGeo (abre sem o plugin)'):
    """
    Grava o estilo atual em layer_styles do GeoPackage como padrão da tabela, com a prova da
    escrita (calco.gravar_estilo). Devolve a mensagem de erro ('' quando o arquivo o guardou).
    """
    from .calco import gravar_estilo, EstiloNaoGravado
    try:
        return gravar_estilo(layer, nome, descricao)[1]
    except EstiloNaoGravado as e:
        return str(e)
