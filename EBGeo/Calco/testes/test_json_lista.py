# -*- coding: utf-8 -*-
"""
Coluna JSON lida como LISTA: na camada que a árvore do importador monta, a coluna JSON do
GeoPackage chega como lista (ou mapa), e numa camada aberta à mão pode chegar como texto.
`try(from_json(lista), lista)` dá nulo SEM erro, então o try não cai na reserva e a expressão
perde o valor gravado (medido em 2026-10-04: os portões da Área e as instâncias do Limite
importados da fixture 06 sumiam). Cada expressão que lê JSON tem de servir aos dois.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_json_lista.py
"""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression, QgsExpressionContext,
    QgsExpressionContextUtils, QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from Calco import estilos_taticos as et  # noqa: E402
from Calco.importador import arvore, escritor  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_json_lista_')
EIXO = [[-47.95, -15.80], [-47.85, -15.82], [-47.76, -15.80]]
INSTANCIAS = [{'ratio': 0.25, 'showLabels': True}, {'ratio': 0.5, 'showLabels': True}, {'ratio': 0.8, 'showLabels': True}]


def avaliar(expr, vl, f):
    ms = QgsMapSettings()
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(1000, 800))
    ms.setOutputDpi(96)
    c = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(),
                               QgsProject.instance()).transform(QgsPointXY(-47.85, -15.81))
    ms.setExtent(QgsRectangle(c.x() - 15000, c.y() - 12000, c.x() + 15000, c.y() + 12000))
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ctx.setFeature(f)
    e = QgsExpression(expr)
    e.prepare(ctx)
    v = e.evaluate(ctx)
    if e.hasEvalError():
        raise AssertionError(e.evalErrorString())
    return v


def importar_limite():
    props = {'id': 'limite-1', 'layerId': 'default', 'nome': 'Limite', 'echelon': 'XX', 'symbol_instances': INSTANCIAS,
             'symbol_size': 0.8, 'text_top': '1ª DE', 'text_bottom': '2ª DE', 'text_north_facing': True,
             'createdAtZoom': 12, 'zoomCorrectionEnabled': True, 'color': '#000000', 'lineWidth': 4,
             'visivel': True, 'baseCoordinates': EIXO}
    data = {'version': '3.0', 'mapOrder': ['Principal'], 'currentMap': 'Principal',
            'maps': {'Principal': {'features': {'boundarys': [
                {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': EIXO}, 'properties': props}]},
                'layers': {'default': {'name': 'Padrão', 'visible': True, 'order': 0}}}}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('data.json', json.dumps(data, ensure_ascii=False).encode('utf-8'))
    arquivo = os.path.join(TMP, 'limite.ebgeo')
    with open(arquivo, 'wb') as fh:
        fh.write(buf.getvalue())
    destino = os.path.join(TMP, 'limite.gpkg')
    escritor.importar(arquivo, destino)
    grupo = arvore.montar_arvore(destino, QgsProject.instance())
    camadas = [n.layer() for n in grupo.findLayers() if n.layer().customProperty('ebgeo_calco/tipo') == 'boundary']
    return destino, camadas[0]


class TestLimiteComInstanciasEmLista(unittest.TestCase):

    def test_tres_instancias_pela_arvore(self):
        destino, lyr = importar_limite()
        f = next(lyr.getFeatures())
        self.assertIsInstance(f['symbol_instances'], list)          # o caso que o teste exercita
        for norte in (True,):
            pts = avaliar(et.expr_limite_rotulo('top', norte)['geometria'], lyr, f)
            self.assertIsNotNone(pts)
            # um rótulo por instância: com a lista perdida, o padrão do Limite (uma instância) daria 1
            self.assertEqual(pts.constGet().numGeometries(), len(INSTANCIAS))
        # o desenho do escalão: três grupos de glifos XX, afastados ao longo do eixo
        linhas = avaliar(et.expr_limite_linhas(), lyr, f)
        self.assertIsNotNone(linhas)
        c = [p.centroid().asPoint().x() for p in linhas.asGeometryCollection()]
        self.assertGreater(max(c) - min(c), 0.05)                    # 0,25 a 0,8 do eixo: > 0,05 grau

    def test_texto_continua_servindo(self):
        """Na mesma tabela aberta à mão, com a coluna como texto JSON, o resultado é o mesmo."""
        from Calco import gpkg, schema
        from qgis.core import QgsFeature, QgsGeometry
        caminho = os.path.join(TMP, 'texto.gpkg')
        gpkg.criar_calco(caminho, ['boundary'])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'boundary'), 'b', 'ogr')
        f = QgsFeature(vl.fields())
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in EIXO]))
        v = dict(schema.padroes('boundary'))
        v.update(ebgeo_id='t', echelon='XX', symbol_size_km=0.8, text_top='1ª DE', text_north_facing=True,
                 created_zoom=12.0, symbol_instances=json.dumps(INSTANCIAS))
        for k, x in v.items():
            f[k] = x
        self.assertTrue(vl.dataProvider().addFeatures([f])[0])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'boundary'), 'b', 'ogr')
        f = next(vl.getFeatures())
        pts = avaliar(et.expr_limite_rotulo('top', True)['geometria'], vl, f)
        self.assertEqual(pts.constGet().numGeometries(), len(INSTANCIAS))


# ---------------------------------------------------------------- grupos, parametros e props
#
# Medido em 2026-10-04 (QGIS 4.0.0): quem GRAVA decide como a coluna JSON volta. O QGIS, ao gravar
# uma str do Python (o que as ferramentas e o painel do Desktop fazem), guarda um literal de
# string JSON ("\"[...]\"") e a coluna volta como TEXTO; o OGR do importador guarda o JSON cru e
# a coluna volta como LISTA ou MAPA, numa camada aberta à mão ou na da árvore.

def camada_com_os_dois(tipo, colunas):
    """Duas feições iguais no GPKG: 'texto' gravada pelo QGIS com str, 'lista' pelo OGR."""
    from osgeo import ogr
    from Calco import gpkg, schema
    from qgis.core import QgsFeature, QgsGeometry
    import uuid
    caminho = os.path.join(TMP, 'dois_{}_{}.gpkg'.format(tipo, uuid.uuid4().hex[:8]))
    gpkg.criar_calco(caminho, [tipo])
    wkt = {'Point': 'POINT(-47.9 -15.8)', 'MultiLineString': 'MULTILINESTRING((-47.95 -15.8,-47.85 -15.8))',
           'MultiPolygon': 'MULTIPOLYGON(((-47.95 -15.8,-47.85 -15.8,-47.85 -15.75,-47.95 -15.8)))'}[
        schema.TIPOS[tipo]['geometria']]
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), 't', 'ogr')
    f = QgsFeature(vl.fields())
    f.setGeometry(QgsGeometry.fromWkt(wkt))
    for k, v in schema.padroes(tipo).items():
        f[k] = v
    f['ebgeo_id'] = 'texto'
    for c, v in colunas.items():
        f[c] = json.dumps(v)
    assert vl.dataProvider().addFeatures([f])[0]
    ds = ogr.Open(caminho, 1)
    lyr = ds.GetLayerByName(schema.TIPOS[tipo]['tabela'])
    g = ogr.Feature(lyr.GetLayerDefn())
    g.SetField('ebgeo_id', 'lista')
    for c, v in colunas.items():
        g.SetField(c, json.dumps(v))
    g.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
    lyr.CreateFeature(g)
    ds = None
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), 't', 'ogr')
    fs = {x['ebgeo_id']: x for x in vl.getFeatures()}
    return caminho, vl, fs


class TestTextoListaOuMapa(unittest.TestCase):

    def test_os_dois_formatos_existem(self):
        _c, _vl, fs = camada_com_os_dois('polygon', {'grupos': ['g1'], 'parametros': {'width': 9}})
        self.assertIsInstance(fs['texto']['grupos'], str)
        self.assertIsInstance(fs['lista']['grupos'], list)
        self.assertIsInstance(fs['texto']['parametros'], str)
        self.assertIsInstance(fs['lista']['parametros'], dict)

    def test_grupo_oculto_esconde_nos_dois(self):
        cond = arvore.condicao_exibir(['g1'])
        _c, vl, fs = camada_com_os_dois('polygon', {'grupos': ['g1']})
        for k, f in fs.items():
            self.assertFalse(avaliar(cond, vl, f), k + ': membro do grupo oculto aparece')
        _c, vl, fs = camada_com_os_dois('polygon', {'grupos': ['g2']})
        for k, f in fs.items():
            self.assertTrue(avaliar(cond, vl, f), k + ': feição de outro grupo some')

    def test_largura_da_visada_nos_dois(self):
        from Calco import estilos_formas as ef
        _c, vl, fs = camada_com_os_dois('processed_los', {'parametros': {'width': 9}})
        ef.aplicar_estilo(vl, 'processed_los')
        e = vl.renderer().symbol().symbolLayer(0).dataDefinedProperties().property(
            ef.QgsSymbolLayer.Property.StrokeWidth).expressionString()
        for k, f in fs.items():
            self.assertAlmostEqual(avaliar(e, vl, f), 9 * 25.4 / 96, places=4, msg=k)

    def test_largura_de_props_nos_dois(self):
        from Calco import estilos_formas as ef
        _c, vl, fs = camada_com_os_dois('military_symbol', {'props': {'width': 77}})
        for k, f in fs.items():
            self.assertEqual(avaliar(ef._LARGURA_PROPS, vl, f), 77, k)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
