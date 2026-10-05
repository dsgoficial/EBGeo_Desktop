# -*- coding: utf-8 -*-
"""
O que o exportador precisa do QGIS: a geometria desenhada dos táticos e o estado da árvore.

Desenho. O Web não refaz no carregamento o contorno da Seta nem os braços da Frente Ocupada
(setupArrowLayers e setupOccupiedFrontLayers gravam a fonte como veio), e o Limite e a Linha de
Coordenação só se refazem quando o controle da ferramenta já carregou (o substituto de
tool-registry.js devolve só os números). Então a feição criada ou mudada no Desktop leva o
desenho, e ele sai do próprio Geometry Generator do estilo do calco (estilos_taticos, porte do
algoritmo do Web com paridade medida), avaliado na feição em EPSG:4326 e, no que depende da
escala (o preso à tela), na escala do zoom de criação. A Seta combinada é desenhada ramo a
ramo, cada um com as propriedades dele, e unida, como o turf.union do Web.

Árvore. Com o atlas no projeto, o mapa ligado é o currentMap, e o check, a opacidade e o
somente-leitura do subgrupo de cada camada EBGeo são o estado dela (seção 2 da ARQUITETURA).
"""
import json
import os

from qgis.core import (
    QgsExpression, QgsExpressionContext, QgsExpressionContextScope, QgsExpressionContextUtils, QgsFeature, QgsField, QgsFields,
    QgsGeometry, QgsGeometryCollection, QgsLineString, QgsPointXY, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType

from .. import schema

_TIPO_CAMPO = {'str': QMetaType.Type.QString, 'json': QMetaType.Type.QString, 'real': QMetaType.Type.Double,
               'int': QMetaType.Type.Int, 'bool': QMetaType.Type.Bool, 'datetime': QMetaType.Type.QDateTime}


class GeradorDesenho:
    """gerar(tipo, linha, geo) -> GeoJSON da geometria desenhada, ou None (sem desenho a refazer)."""

    TIPOS = ('arrow', 'occupied_front', 'boundary', 'coordination_line')

    def __init__(self):
        self._camadas = {}
        self._expr = {}

    def _camada(self, tipo):
        if tipo not in self._camadas:
            camada = QgsVectorLayer('{}?crs=EPSG:4326'.format(schema.TIPOS[tipo]['geometria']), tipo, 'memory')
            campos = QgsFields()
            for col, tp, _p, _w in schema.campos(tipo):
                campos.append(QgsField(col, _TIPO_CAMPO[tp]))
            camada.dataProvider().addAttributes(campos.toList())
            camada.updateFields()
            self._camadas[tipo] = camada
        return self._camadas[tipo]

    def _expressao(self, tipo, linha):
        """(expressão, poligonal?) do desenho que o Web grava como geometria da feição."""
        from .. import estilos_taticos as et
        if tipo == 'arrow':
            chave, poligono = 'arrow', True
        elif tipo == 'occupied_front':
            chave, poligono = 'occupied_front', False
        elif tipo == 'boundary':
            chave, poligono = 'boundary', False
        else:
            codigo = linha.get('symbol_code') if linha.get('symbol_code') in et.CATALOGO_LINHA else et.SIMBOLO_PADRAO
            chave = ('coordination_line', codigo)
            poligono = bool(et.CATALOGO_LINHA[codigo].get('preenchido'))
        if chave not in self._expr:
            if tipo == 'arrow':
                texto = et.expr_seta()
            elif tipo == 'occupied_front':
                texto = et.expr_frente_ocupada()
            elif tipo == 'boundary':
                texto = et.expr_limite_linhas()
            else:
                ex = et.expr_linha_coordenacao(chave[1])
                texto = ex['preenchimento'] if poligono else ex['linha']
            self._expr[chave] = QgsExpression(texto)
        return self._expr[chave], poligono

    def _avaliar(self, tipo, linha, geo):
        camada = self._camada(tipo)
        expr, poligono = self._expressao(tipo, linha)
        f = QgsFeature(camada.fields())
        for i, campo in enumerate(camada.fields()):
            v = linha.get(campo.name())
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            if v is not None and campo.type() == QMetaType.Type.QDateTime:
                v = None  # data não entra no desenho
            f.setAttribute(i, v)
        g = QgsGeometry.fromWkt(_wkt(geo))
        if g.isNull():
            return None, poligono
        f.setGeometry(g)
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(camada))
        ctx.appendScope(_escopo_mapa(linha, g))
        ctx.setFeature(f)
        if not expr.prepare(ctx) and expr.hasParserError():
            raise RuntimeError(expr.parserErrorString())
        r = expr.evaluate(ctx)
        if expr.hasEvalError():
            raise RuntimeError(expr.evalErrorString())
        if not isinstance(r, QgsGeometry) or r.isNull() or r.isEmpty():
            return None, poligono
        return r, poligono

    def __call__(self, tipo, linha, geo):
        if tipo not in self.TIPOS:
            return None
        ramos = linha.get('_ramos') if tipo == 'arrow' else None
        if ramos:
            pecas = [self._avaliar(tipo, l, {'type': 'MultiLineString', 'coordinates': [c]})[0] for l, c in ramos]
            pecas = [p for p in pecas if p is not None]
            if not pecas:
                return None
            r = QgsGeometry.unaryUnion(pecas) if len(pecas) > 1 else pecas[0]
            poligono = True
        else:
            r, poligono = self._avaliar(tipo, linha, geo)
            if r is None:
                return None
        if not poligono:
            r = _multilinha(r)
            if r.isEmpty():
                return None
        elif tipo == 'coordination_line':
            r.convertToMultiType()
        return json.loads(r.asJson(17))


def _escopo_mapa(linha, g):
    """@map_crs e @map_scale de um mapa em EPSG:3857 no zoom de criação da feição (o preso à tela)."""
    import math
    from .. import zoom
    s = QgsExpressionContextScope('EBGeo: zoom de criação')
    lat = g.centroid().asPoint().y() if not g.isEmpty() else 0.0
    z = linha.get('created_zoom') or 12
    escala = zoom.metros_por_pixel_de_zoom(z, lat) / math.cos(math.radians(lat)) / (0.0254 / 96)
    s.setVariable('map_crs', 'EPSG:3857')
    s.setVariable('map_scale', escala)
    return s


def _wkt(geo):
    from osgeo import ogr
    return ogr.CreateGeometryFromJson(json.dumps(geo)).ExportToIsoWkt()


def _multilinha(g):
    """O desenho da Frente vem como coleção de braços; o Web grava MultiLineString."""
    partes = []

    def junta(a):
        if isinstance(a, QgsGeometryCollection):
            for i in range(a.numGeometries()):
                junta(a.geometryN(i))
        elif isinstance(a, QgsLineString) and a.numPoints() >= 2:
            partes.append([QgsPointXY(p.x(), p.y()) for p in a.points()])
    junta(g.constGet())
    return QgsGeometry.fromMultiPolylineXY(partes)


def estado_da_arvore(caminho, projeto):
    """
    {'mapa_atual', 'camadas': {(mapa, camada_id): {visivel, opacidade, bloqueada}}} do atlas do
    GeoPackage no projeto, ou {} se ele não está lá. Lê a árvore: só na thread principal.
    """
    from ..importador import arvore
    if projeto is None:
        return {}
    alvo = os.path.normcase(os.path.abspath(caminho))
    for g in projeto.layerTreeRoot().findGroups(True):
        atlas = g.customProperty(arvore.PROP_ATLAS)
        if not atlas or os.path.normcase(os.path.abspath(atlas)) != alvo:
            continue
        if g.customProperty(arvore.PROP_MAPA) is not None:
            continue  # grupo de mapa, não o do atlas
        estado = {'camadas': {}}
        for gm in g.children():
            mapa = gm.customProperty(arvore.PROP_MAPA) if hasattr(gm, 'customProperty') else None
            if mapa is None:
                continue
            if gm.itemVisibilityChecked():
                estado.setdefault('mapa_atual', mapa)
            for sub in gm.children():
                cid = sub.customProperty(arvore.PROP_CAMADA) if hasattr(sub, 'customProperty') else None
                if cid is None or not hasattr(sub, 'findLayers'):
                    continue
                e = {'visivel': sub.itemVisibilityChecked()}
                camadas = [n.layer() for n in sub.findLayers() if n.layer() is not None]
                if camadas:
                    e['opacidade'] = float(camadas[0].opacity())
                    e['bloqueada'] = bool(camadas[0].readOnly())
                estado['camadas'][(mapa, cid)] = e
        return estado
    return {}


def edicoes_pendentes(caminho, projeto):
    """As camadas do projeto que apontam para o GeoPackage e têm edição não salva."""
    alvo = os.path.normcase(os.path.abspath(caminho))
    out = []
    for l in projeto.mapLayers().values():
        if not isinstance(l, QgsVectorLayer) or not l.isModified():
            continue
        fonte = l.source().split('|')[0]
        if os.path.normcase(os.path.abspath(fonte)) == alvo:
            out.append(l)
    return out

