# -*- coding: utf-8 -*-
"""
Azimute e Distância no calco: grava e reedita as feições que a construção polar gera.

O Web guarda a saída da ferramenta nos baldes comuns (points, lines, polygons) com
featureType 'azimuth_distance' e a construção em properties.azimuthDistanceData; aqui ela vai
para as mesmas tabelas (point, line, polygon) que o importador .ebgeo usa, com a construção na
coluna JSON azimute_distancia (schema.py) e a feição inteira, com as chaves do Web, no JSON props.
Uma feição importada antes da coluna existir ainda é lida pelo props.

No modo ponto a construção vira um ponto por vértice, e o Web não grava um id da construção: os
pontos de uma mesma construção são os que têm a mesma construção gravada (chave_conjunto).
"""
import json
import time
import uuid
from datetime import datetime, timezone

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature, QgsFeatureRequest,
    QgsGeometry, QgsPointXY, QgsProject,
)

from .. import gpkg, schema
from . import geometria as G

COLUNA = 'azimute_distancia'
TIPO_DO_MODO = {G.PONTO: 'point', G.ROTA: 'line', G.AREA: 'polygon'}
MODO_DO_TIPO = {v: k for k, v in TIPO_DO_MODO.items()}
WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')


# ---------------------------------------------------------------- leitura

def _json(v):
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip():
        try:
            r = json.loads(v)
        except ValueError:
            return None
        return r if isinstance(r, dict) else None
    return None


def _valor(feat, campo):
    i = feat.fields().indexOf(campo)
    return feat.attribute(i) if i >= 0 else None


def props_da_feicao(feat):
    return _json(_valor(feat, 'props')) or {}


def construcao_da_feicao(feat):
    """A construção polar (azimuthDistanceData) da feição, ou None se ela não veio da ferramenta."""
    polar = _json(_valor(feat, COLUNA))
    if polar is None:
        p = props_da_feicao(feat)
        if p.get('featureType') == 'azimuth_distance':
            polar = _json(p.get('azimuthDistanceData'))
    if not polar or not isinstance(polar.get('referencePoint'), list) or not isinstance(polar.get('legs'), list):
        return None
    return polar


# ---------------------------------------------------------------- camada

def camada(calco, tipo, iface=None):
    """
    A camada do tipo no calco ativo, criando a tabela (point, line, polygon) se faltar. Num atlas
    importado, a do mapa e da camada do EBGeo em que o operador está, como nas ferramentas
    militares (`ferramentas.camada_para_gravar`).
    """
    # cria a tabela que faltar e acrescenta a coluna azimute_distancia num calco antigo
    gpkg.criar_calco(calco.caminho, [tipo], apoio=False)
    from ..ferramentas import camada_para_gravar
    lyr = camada_para_gravar(calco, tipo, iface)
    if lyr is not None and lyr.fields().indexOf(COLUNA) < 0:
        lyr.dataProvider().reloadData()
        lyr.updateFields()
    return lyr


# ---------------------------------------------------------------- escrita

def _agora():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _geometria_qgis(geo, tipo, layer):
    t = geo['type']
    c = geo['coordinates']
    if t == 'Point':
        g = QgsGeometry.fromPointXY(QgsPointXY(c[0], c[1]))
    elif t == 'LineString':
        g = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in c])
    else:
        g = QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in anel] for anel in c])
    if schema.TIPOS[tipo]['geometria'].startswith('Multi'):
        g.convertToMultiType()
    if layer.crs() != WGS84:
        g.transform(QgsCoordinateTransform(WGS84, layer.crs(), QgsProject.instance()))
    return g


def _linha(tipo, p, mapa='Principal'):
    """properties do Web -> colunas da tabela, pelo mesmo mapeamento do importador."""
    from ..importador.escritor import linha_feicao
    linha = linha_feicao(tipo, mapa, p, None)
    agora = _agora()
    linha['criado_em'] = agora
    linha['atualizado_em'] = agora
    return linha


def _para_qgis(layer, nome, valor):
    """Coluna JSON recebe o objeto (schema.valor_json_para_qgis); as outras, o valor."""
    from ..calco import tipo_da_camada
    tipo = tipo_da_camada(layer)
    if tipo in schema.TIPOS and nome in schema.colunas_json(tipo):
        return schema.valor_json_para_qgis(valor)
    return valor


def _editar(layer, funcao):
    estava = layer.isEditable()
    if not estava:
        layer.startEditing()
    ok = funcao()
    if not estava:
        ok = layer.commitChanges() and ok
        if not ok:
            layer.rollBack()
    layer.triggerRepaint()
    return ok


def criar(calco, estado, zoom=None, iface=None):
    """
    Grava a construção no calco. Devolve (camada, [ebgeo_id]) ou (None, []). `iface` dá a camada
    ativa e o nó da árvore que escolhem o mapa num atlas importado.
    """
    modo = estado.get('outputMode', G.ROTA)
    tipo = TIPO_DO_MODO[modo]
    lyr = camada(calco, tipo, iface)
    if lyr is None:
        return None, []
    base = lyr.featureCount()
    nome_pt = schema.TIPOS[tipo]['nome_pt']
    itens = G.propriedades_web(estado, lambda i: '{} #{}'.format(nome_pt, base + 1 + i),
                               int(time.time() * 1000), zoom)
    feicoes = []
    for geo, p in itens:
        p['id'] = str(uuid.uuid4())
        f = QgsFeature(lyr.fields())
        from ..ferramentas import mapa_e_camada
        alvo = mapa_e_camada(lyr)
        linha = _linha(tipo, p, alvo.get('mapa', 'Principal'))
        if 'camada_id' in alvo:
            linha['camada_id'] = alvo['camada_id']
            p['layerId'] = alvo['camada_id']
            linha['props'] = json.dumps(p, ensure_ascii=False)
        for nome, valor in linha.items():
            i = lyr.fields().indexOf(nome)
            if i >= 0:
                f.setAttribute(i, _para_qgis(lyr, nome, valor))
        f.setGeometry(_geometria_qgis(geo, tipo, lyr))
        feicoes.append((f, p['id']))
    if not feicoes:
        return lyr, []
    ok = _editar(lyr, lambda: all(lyr.addFeature(f) for f, _ in feicoes))
    return lyr, ([eid for _, eid in feicoes] if ok else [])


def _mudar(layer, fid, valores, geometria=None):
    attrs = {}
    for nome, valor in valores.items():
        i = layer.fields().indexOf(nome)
        if i >= 0:
            attrs[i] = _para_qgis(layer, nome, valor)
    ok = layer.changeAttributeValues(fid, attrs) if attrs else True
    if geometria is not None:
        ok = layer.changeGeometry(fid, geometria) and ok
    return ok


def conjunto_de_pontos(layer, feat):
    """Os pontos da mesma construção (modo ponto), {waypointIndex: feição}."""
    polar = construcao_da_feicao(feat)
    if polar is None:
        return {}
    chave = G.chave_conjunto(polar)
    mapa, camada_id = _valor(feat, 'mapa'), _valor(feat, 'camada_id')
    out = {}
    for f in layer.getFeatures(QgsFeatureRequest()):
        q = construcao_da_feicao(f)
        if q is None or G.chave_conjunto(q) != chave:
            continue
        if _valor(f, 'mapa') != mapa or _valor(f, 'camada_id') != camada_id:
            continue
        out.setdefault(int(q.get('waypointIndex') or 0), f)
    return out


def atualizar(layer, fid, estado):
    """Regrava a construção editada (pernas, norte, declinação, ponto) e refaz a geometria."""
    feat = layer.getFeature(fid)
    polar_antigo = construcao_da_feicao(feat)
    if polar_antigo is None:
        return False
    tipo = MODO_DO_TIPO.get(polar_antigo.get('outputMode'))
    from ..calco import tipo_da_camada
    tipo = tipo_da_camada(layer) or tipo
    estado = dict(estado)
    estado['outputMode'] = MODO_DO_TIPO.get(tipo, polar_antigo.get('outputMode'))
    agora_ms = int(time.time() * 1000)
    nome_pt = schema.TIPOS[tipo]['nome_pt']

    if estado['outputMode'] == G.PONTO:
        conjunto = conjunto_de_pontos(layer, feat)
        itens = G.propriedades_web(estado, lambda i: '{} #{}'.format(nome_pt, layer.featureCount() + i),
                                   agora_ms, _valor(feat, 'created_zoom'))

        def aplicar():
            ok = True
            for i, (geo, p_novo) in enumerate(itens):
                existente = conjunto.get(i)
                if existente is None:
                    p_novo['id'] = str(uuid.uuid4())
                    p_novo['layerId'] = _valor(feat, 'camada_id') or 'default'
                    f = QgsFeature(layer.fields())
                    linha = _linha(tipo, p_novo, _valor(feat, 'mapa') or 'Principal')
                    for nome, valor in linha.items():
                        j = layer.fields().indexOf(nome)
                        if j >= 0:
                            f.setAttribute(j, _para_qgis(layer, nome, valor))
                    f.setGeometry(_geometria_qgis(geo, tipo, layer))
                    ok = layer.addFeature(f) and ok
                    continue
                props = props_da_feicao(existente)
                props.update({'azimuthDistanceData': p_novo['azimuthDistanceData'], 'updatedAt': agora_ms})
                ok = _mudar(layer, existente.id(), {
                    COLUNA: json.dumps(p_novo['azimuthDistanceData'], ensure_ascii=False),
                    'props': json.dumps(props, ensure_ascii=False), 'atualizado_em': _agora(),
                }, _geometria_qgis(geo, tipo, layer)) and ok
            for i, existente in conjunto.items():
                if i >= len(itens):
                    ok = layer.deleteFeature(existente.id()) and ok
            return ok
        return _editar(layer, aplicar)

    itens = G.propriedades_web(estado, lambda i: _valor(feat, 'nome') or nome_pt, agora_ms)
    if not itens:
        return False
    geo, p_novo = itens[0]
    props = props_da_feicao(feat)
    props.update({'azimuthDistanceData': p_novo['azimuthDistanceData'], 'baseCoordinates': p_novo['baseCoordinates'],
                  'observations': p_novo['observations'], 'updatedAt': agora_ms})
    props.setdefault('featureType', 'azimuth_distance')
    return _editar(layer, lambda: _mudar(layer, fid, {
        COLUNA: json.dumps(p_novo['azimuthDistanceData'], ensure_ascii=False),
        'props': json.dumps(props, ensure_ascii=False), 'atualizado_em': _agora(),
    }, _geometria_qgis(geo, tipo, layer)))
