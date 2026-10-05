# -*- coding: utf-8 -*-
"""
Testes da Área de Coordenação (capítulo VII do MD33-C-01): esquema, estilo nativo por tipo,
Correção de Zoom, ferramenta de captura, painel, importador e gerenciador.

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/Calco/testes/test_area_coordenacao.py

Variáveis de ambiente opcionais:
    EBGEO_WEB (ou EBGEO_WEB_DIR)  raiz do ebgeo_web; padrão: a pasta irmã ebgeo_web. Com ela e
                       com o node, o modelo de decoração do Web (coordination_area_drawing.js)
                       roda em node e as posições são comparadas com as do QGIS.
    EBGEO_NODE         executável do node, quando o python-qgis.bat o tira do PATH.
    EBGEO_TESTE_SAIDA  pasta para os PNG de conferência (padrão: pasta temporária).

O que cada classe prova:
    TestEsquema       a tabela, as chaves do Web e a pilha de desenho;
    TestExpressoes    toda expressão parseia em menos de 0,5 s;
    TestContraWeb     cada decoração (dentes, elos, portões, borda minada, minas, chamada,
                      textos, escalão, "M", nomes de portão) contra o Web rodado em node, em
                      polígono convexo e côncavo, nos dois sentidos de traçado, com a régua
                      provada antes contra a saída real degradada (contagem, posição, lado);
    TestZoom          Correção de Zoom ligada (terreno) e desligada (tela), e o piso da hachura;
    TestRender        PNG de cada tipo, estilo salvo no layer_styles reaberto sem o plugin,
                      tempo de 30 áreas e a seleção pelo interior;
    TestFerramenta, TestPainel, TestImportador, TestGerenciador: o resto do tipo.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, '..', '..'))
RAIZ_REPO = os.path.dirname(PLUGIN)
if PLUGIN not in sys.path:
    sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression,
    QgsExpressionContext, QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsMapRendererParallelJob,
    QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle, QgsRuleBasedRenderer, QgsVectorLayer,
    QgsFillSymbol, QgsSingleSymbolRenderer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from Calco import gpkg, schema  # noqa: E402

MM_POR_PX = 25.4 / 96
R_TURF = 6371008.8
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_area_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_area_calco_')
MEDIDAS = []


def medir(t):
    MEDIDAS.append(t)


def ea():
    """O módulo do estilo da área (importado aqui para a falha ser por teste, não do arquivo)."""
    from Calco import estilos_area
    return estilos_area


# Polígonos de teste (EPSG:4326), perto do Rio de Janeiro, como as capturas do Web.
QUADRA = [(-43.08, -22.92), (-43.04, -22.93), (-43.035, -22.90), (-43.075, -22.89)]   # anti-horário
# Côncavo (um U aberto ao norte), com latitudes empatadas: prova o desempate do início do anel.
CONCAVO = [(-43.10, -22.95), (-43.04, -22.95), (-43.04, -22.90), (-43.06, -22.90),
           (-43.06, -22.93), (-43.08, -22.93), (-43.08, -22.90), (-43.10, -22.90)]
Z0 = 13.0

# ---------------------------------------------------------------- feições


def _calco(nome):
    caminho = os.path.join(TMP, nome + '.gpkg')
    if os.path.exists(caminho):
        os.remove(caminho)
    gpkg.criar_calco(caminho)
    return caminho


CALCO = None


def camada(caminho=None):
    return QgsVectorLayer(gpkg.uri_camada(caminho or CALCO, 'coordination_area'), 'area', 'ogr')


def nova_area(coords, caminho=None, **attrs):
    """Grava a área e a devolve relida do GeoPackage."""
    global CALCO
    if CALCO is None:
        CALCO = _calco('area_teste')
    vl = camada(caminho)
    f = QgsFeature(vl.fields())
    f.setGeometry(QgsGeometry.fromMultiPolygonXY([[[QgsPointXY(*p) for p in coords + [coords[0]]]]]))
    valores = dict(schema.padroes('coordination_area'))
    valores.update(ebgeo_id=str(uuid.uuid4()), created_zoom=Z0, symbol_size_km=0.2)
    valores.update(attrs)
    for k, v in valores.items():
        f[k] = v
    ok, novas = vl.dataProvider().addFeatures([f])
    assert ok
    vl = camada(caminho)
    return vl, vl.getFeature(novas[0].id())


def escala_do_zoom(z):
    return 78271.517 / (2 ** z) / (MM_POR_PX / 1000)


def mapa(centro, z=Z0, crs='EPSG:3857', tamanho=(1000, 800)):
    ms = QgsMapSettings()
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(96)
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(), QgsProject.instance())
    c = tr.transform(QgsPointXY(*centro))
    upp = escala_do_zoom(z) * 0.0254 / 96
    if not ms.destinationCrs().isGeographic() and crs != 'EPSG:3857':
        upp *= math.cos(math.radians(centro[1]))  # UTM: metro de terreno
    w, h = tamanho[0] * upp / 2, tamanho[1] * upp / 2
    ms.setExtent(QgsRectangle(c.x() - w, c.y() - h, c.x() + w, c.y() + h))
    return ms


def centro_de(f):
    c = f.geometry().centroid().asPoint()
    return (c.x(), c.y())


def avaliar(expr, vl, f, ms=None):
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms or mapa(centro_de(f))))
    ctx.setFeature(f)
    e = QgsExpression(expr)
    if e.hasParserError():
        raise AssertionError('parse: ' + e.parserErrorString())
    e.prepare(ctx)
    v = e.evaluate(ctx)
    if e.hasEvalError():
        raise AssertionError('avaliação: ' + e.evalErrorString())
    return v


def plano(lon, lat):
    crs = QgsCoordinateReferenceSystem(
        'PROJ:+proj=tmerc +lat_0={} +lon_0={} +R={} +units=m +no_defs'.format(lat, lon, R_TURF))
    return QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())


def metrico(g, tr):
    g = QgsGeometry(g)
    g.transform(tr)
    return g


def partes(g):
    """Lista de QgsGeometry simples (linha, polígono ou ponto)."""
    if g is None or g.isNull() or g.isEmpty():
        return []
    return [QgsGeometry(p) for p in g.asGeometryCollection()]


def geojson_para_geom(g):
    return QgsGeometry.fromWkt(_wkt(g))


def _wkt(g):
    from osgeo import ogr
    return ogr.CreateGeometryFromJson(json.dumps(g)).ExportToWkt()


# ---------------------------------------------------------------- o Web em node

NODE_HARNESS = r'''
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const [frontend, entrada, saida] = process.argv.slice(2);
const m = await import(pathToFileURL(join(frontend, 'src/js/military_tools/coordination_area_tool/coordination_area_drawing.js')).href);
const casos = JSON.parse(readFileSync(entrada, 'utf8'));
writeFileSync(saida, JSON.stringify(casos.map((c) => m.buildAreaDecorations(
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [c.coords] }, properties: c.props }, c.zoom))));
'''


def _web_e_node():
    web = os.environ.get('EBGEO_WEB') or os.environ.get('EBGEO_WEB_DIR') or \
        os.path.join(os.path.dirname(RAIZ_REPO), 'ebgeo_web')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    padrao = os.path.join(os.environ.get('ProgramFiles', ''), 'nodejs', 'node.exe')
    if not node and os.path.exists(padrao):  # o .bat do QGIS tira o node do PATH
        node = padrao
    if not os.path.isdir(os.path.join(web, 'frontend')):
        return None, None, 'ebgeo_web ausente (EBGEO_WEB)'
    if not node:
        return None, None, 'node ausente (EBGEO_NODE)'
    return web, node, None


def rodar_web(casos):
    web, node, motivo = _web_e_node()
    if motivo:
        return None, motivo
    d = tempfile.mkdtemp(prefix='ebgeo_area_node_')
    script = os.path.join(d, 'area.mjs')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    ent, sai = os.path.join(d, 'in.json'), os.path.join(d, 'out.json')
    with open(ent, 'w', encoding='utf-8') as fh:
        json.dump(casos, fh)
    r = subprocess.run([node, script, os.path.join(web, 'frontend'), ent, sai], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-2000:])
    with open(sai, encoding='utf-8') as fh:
        return json.load(fh), None


def props_web(attrs):
    """Colunas do calco -> properties do Web (schema.mapa_web invertido)."""
    inv = {c: w for w, c in schema.mapa_web('coordination_area').items()}
    out = {}
    for c, v in attrs.items():
        if c in inv:
            out[inv[c]] = json.loads(v) if c in ('portoes', 'minas') and isinstance(v, str) else v
    return out


# ---------------------------------------------------------------- 1. esquema

class TestEsquema(unittest.TestCase):

    def test_tabela_e_chaves_do_web(self):
        self.assertIn('coordination_area', schema.TIPOS)
        d = schema.TIPOS['coordination_area']
        self.assertEqual(d['balde'], 'coordination_areas')
        self.assertEqual(schema.BALDE_PARA_TIPO['coordination_areas'], 'coordination_area')
        self.assertIn('coordination_area', schema.TIPOS_MILITARES)
        web = schema.mapa_web('coordination_area')
        # AREA_PROPERTY_KEYS e o polígono do Web (add_coordination_area_control.js)
        for chave in ('symbol_code', 'symbol_size', 'tipo', 'identificacao', 'gdhIni', 'gdhFim', 'outrasInfo',
                      'escalao', 'text_position', 'text_ratio', 'text_size', 'text_north_facing', 'createdAtZoom',
                      'zoomCorrectionEnabled', 'altitudeMax', 'altitudeMin', 'portoes', 'portoes_ocultos', 'minas',
                      'fillColor', 'lineColor', 'lineWidth', 'lineStyle', 'opacity', 'hatchEnabled', 'hatchType',
                      'hatchColor', 'hatchSpacing', 'hatchLineWidth', 'nome', 'descricao', 'visivel'):
            self.assertIn(chave, web, chave)
        tipos = {c[0]: c[1] for c in schema.campos('coordination_area')}
        self.assertEqual(tipos['portoes'], 'json')
        self.assertEqual(tipos['minas'], 'json')
        # pilha do Web: acima das formas, abaixo de toda linha (layer_setup.js)
        p = schema.PILHA_DESENHO
        self.assertEqual(p.index('coordination_area'), p.index('sector') + 1)
        self.assertLess(p.index('coordination_area'), p.index('arrow'))

    def test_gpkg_cria_a_tabela(self):
        caminho = _calco('esquema')
        self.assertIn('coordination_area', gpkg.tabelas_presentes(caminho))
        vl = camada(caminho)
        self.assertTrue(vl.isValid())
        self.assertEqual(vl.geometryType(), Qgis.GeometryType.Polygon)


# ---------------------------------------------------------------- 2. expressões

NOMES_EXPR = ['area_dentes', 'area_elos', 'area_portoes', 'area_minada_borda', 'area_letras_m',
              'area_minas_cheias', 'area_minas_contorno', 'area_chamada', 'area_rotulo_ponto',
              'area_rotulo_quadrante', 'area_rotulo_rotacao', 'area_escalao_ponto']


class TestExpressoes(unittest.TestCase):

    def test_parse(self):
        m = ea()
        exprs = {n: m.expr(n) for n in NOMES_EXPR}
        exprs['portao_ponto'] = m.expr('area_portao_ponto', J=0)
        exprs['portao_quadrante'] = m.expr('area_portao_quadrante', J=0)
        exprs['hachura'] = m.expr_distancia_hachura(0.7071)
        pior = 0
        for nome, txt in exprs.items():
            t = time.perf_counter()
            e = QgsExpression(txt)
            dt = time.perf_counter() - t
            pior = max(pior, dt)
            self.assertFalse(e.hasParserError(), '{}: {}'.format(nome, e.parserErrorString()))
            self.assertLess(dt, 0.5, nome)
        medir('parse: {} expressões da área, a mais lenta em {:.0f} ms'.format(len(exprs), pior * 1000))

    def test_teto_de_nomes_de_portao(self):
        """Seis portões com nome (cada regra custa preparo a cada desenho); os traços não têm teto."""
        m = ea()
        lab = m.rotulagem_area()
        portoes = [r for r in lab.rootRule().children() if r.description().startswith('Portão')]
        self.assertEqual(len(portoes), 6)
        gs = json.dumps([{'ratio': i / 8, 'nome': 'P{}'.format(i)} for i in range(8)])
        vl, f = nova_area(QUADRA, symbol_code='170999-01', portoes=gs)
        self.assertEqual(len(partes(avaliar(m.expr('area_portoes'), vl, f))), 16)


# ---------------------------------------------------------------- 3. contra o Web

def _casos():
    """(nome, coords, colunas do calco) de cada caso comparado com o Web."""
    portoes = json.dumps([{'ratio': 0.62, 'nome': 'PORTÃO ALFA'}, {'ratio': 0.38, 'nome': 'PORTÃO BRAVO'},
                          {'ratio': 0.05, 'nome': 'PORTÃO CHARLIE'}])
    textos = dict(tipo='Obj', identificacao='BAGRE', gdh_ini='121400Z JUN', gdh_fim='121800Z JUN', outras_info='Outras info')
    out = []
    for nome_g, g in (('quadra', QUADRA), ('quadra invertida', QUADRA[::-1]), ('côncavo', CONCAVO),
                      ('côncavo invertido', CONCAVO[::-1])):
        out += [
            ('151203 ' + nome_g, g, dict(symbol_code='151203', escalao='II', text_ratio=0.3, line_width=5.0,
                                         tipo='PF', identificacao='1', gdh_ini='121400Z JUN')),
            ('151000 ' + nome_g, g, dict(symbol_code='151000', **textos)),
            ('170999-01 ' + nome_g, g, dict(symbol_code='170999-01', portoes=portoes, tipo='VAB', identificacao='CONDOR',
                                            altitude_max='5000 ft', altitude_min='1500 ft', gdh_ini='121400Z JUN',
                                            line_width=4.0)),
            ('270800 ' + nome_g, g, dict(symbol_code='270800', minas=json.dumps(['qualquer', 'ap', 'ac']),
                                         line_color='#00B04E', fill_color='#00B04E', tipo='Obj')),
            ('150000 externa ' + nome_g, g, dict(symbol_code='150000', text_position='externa', text_ratio=0.25, **textos)),
            ('150000 borda ' + nome_g, g, dict(symbol_code='150000', text_position='borda', text_ratio=0.5, **textos)),
            ('150000 interna ' + nome_g, g, dict(symbol_code='150000', text_position='interna', **textos)),
        ]
    out += [
        ('270800 minas ap-vazia-ac', QUADRA, dict(symbol_code='270800', minas=json.dumps(['ap', 'vazia', 'ac']))),
        ('151203 sem escalão', QUADRA, dict(symbol_code='151203', tipo='PF')),
        ('150000 externa a leste', QUADRA, dict(symbol_code='150000', text_position='externa', text_ratio=0.3, **textos)),
        ('150000 externa a oeste', QUADRA, dict(symbol_code='150000', text_position='externa', text_ratio=0.8, **textos)),
        ('151203 borda com escalão', QUADRA, dict(symbol_code='151203', text_position='borda', escalao='XX',
                                                  text_ratio=0.1, tipo='PF')),
        ('150000 razão nula', QUADRA, dict(symbol_code='150000', tipo='Obj')),
    ]
    return out


# Tolerância de posição contra o Web: o Web calcula num plano equirretangular local em km e o
# QGIS numa Transversa de Mercator local; num perímetro de 20 km o arco diverge cerca de 1 m.
TOL_M = 3.0


def _web_textos(deco, papel):
    return [d for d in deco if d['properties']['decoKind'] == 'text' and papel(d['properties'])]


def _lin(deco, role, kind='line'):
    return [d for d in deco if d['properties'].get('role') == role and d['properties']['decoKind'] == kind]


def _hausdorff(a, b, tr):
    return metrico(a, tr).hausdorffDistance(metrico(b, tr))


def _colecao(gs):
    gs = [g for g in gs if g is not None and not g.isNull() and not g.isEmpty()]
    return QgsGeometry.collectGeometry(gs) if gs else None


def _pareados(web, qgis, tr):
    """Maior distância de cada parte do Web à parte do QGIS mais próxima, e vice-versa (m)."""
    wm = [metrico(g, tr) for g in web]
    qm = [metrico(g, tr) for g in qgis]
    d = 0.0
    for a, bs in ((wm, qm), (qm, wm)):
        for x in a:
            d = max(d, min(x.hausdorffDistance(y) for y in bs))
    return d


class TestContraWeb(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.casos = []
        for nome, coords, attrs in _casos():
            vl, f = nova_area(coords, **attrs)
            cls.casos.append((nome, coords, attrs, vl, f))
        entrada = []
        for nome, coords, attrs, vl, f in cls.casos:
            col = dict(schema.padroes('coordination_area'))
            col.update(created_zoom=Z0, symbol_size_km=0.2)
            col.update(attrs)
            p = props_web(col)
            if 'text_ratio' not in attrs:
                p['text_ratio'] = None
            entrada.append({'coords': [list(c) for c in coords] + [list(coords[0])], 'props': p, 'zoom': Z0})
        cls.web, cls.motivo = rodar_web(entrada)

    def setUp(self):
        if self.web is None:
            self.skipTest(self.motivo)

    def _tr(self, f):
        c = centro_de(f)
        return plano(*c)

    def _comparar(self, nome, web_partes, qgis_partes, tr, contar=True):
        self.assertTrue(web_partes or qgis_partes, nome + ': nada dos dois lados')
        if contar:
            self.assertEqual(len(qgis_partes), len(web_partes), nome + ': número de partes')
        d = _pareados(web_partes, qgis_partes, tr)
        self.assertLess(d, TOL_M, nome)
        return d

    def test_decoracoes(self):
        m = ea()
        pior = {}
        for (nome, coords, attrs, vl, f), deco in zip(self.casos, self.web):
            cod = attrs['symbol_code']
            tr = self._tr(f)
            with self.subTest(caso=nome):
                if cod == '151203':
                    w = [geojson_para_geom(d['geometry']) for d in _lin(deco, 'ticks')]
                    w = [p for g in w for p in partes(g)]
                    q = partes(avaliar(m.expr('area_dentes'), vl, f))
                    pior['dentes'] = max(pior.get('dentes', 0), self._comparar(nome, w, q, tr))
                if cod == '151000':
                    w = [p for d in _lin(deco, 'links') for p in partes(geojson_para_geom(d['geometry']))]
                    q = partes(avaliar(m.expr('area_elos'), vl, f))
                    pior['elos'] = max(pior.get('elos', 0), self._comparar(nome, w, q, tr))
                if cod == '170999-01':
                    w = [p for d in _lin(deco, 'gates') for p in partes(geojson_para_geom(d['geometry']))]
                    q = partes(avaliar(m.expr('area_portoes'), vl, f))
                    pior['portões'] = max(pior.get('portões', 0), self._comparar(nome, w, q, tr))
                    nomes = _web_textos(deco, lambda p: p['text'].startswith('PORTÃO'))
                    for j, t in enumerate(nomes):
                        pq = avaliar(m.expr('area_portao_ponto', J=j), vl, f)
                        self.assertLess(_hausdorff(geojson_para_geom(t['geometry']), pq, tr), TOL_M, 'nome do portão')
                        quad = avaliar(m.expr('area_portao_quadrante', J=j), vl, f)
                        self.assertEqual(quad, ANCORA_QUADRANTE[t['properties']['anchor']], 'âncora do portão')
                if cod == '270800':
                    w = [geojson_para_geom(d['geometry']) for d in _lin(deco, 'border')]
                    q = avaliar(m.expr('area_minada_borda'), vl, f)
                    # o trecho que passa pelo fim do anel é uma parte no Web e duas no QGIS
                    d = _hausdorff(_colecao(w), q, tr)
                    self.assertLess(d, TOL_M, nome + ' borda')
                    pior['borda minada'] = max(pior.get('borda minada', 0), d)
                    w = [p for d in _lin(deco, 'mines', 'fill') for p in partes(geojson_para_geom(d['geometry']))]
                    q = partes(avaliar(m.expr('area_minas_cheias'), vl, f))
                    pior['minas'] = max(pior.get('minas', 0), self._comparar(nome + ' minas cheias', w, q, tr))
                    w = [p for d in _lin(deco, 'mines') for p in partes(geojson_para_geom(d['geometry']))]
                    q = partes(avaliar(m.expr('area_minas_contorno'), vl, f))
                    pior['minas'] = max(pior.get('minas', 0), self._comparar(nome + ' contorno', w, q, tr))
                    letras = _web_textos(deco, lambda p: p['text'] == 'M')
                    q = partes(avaliar(m.expr('area_letras_m'), vl, f))
                    pior['M'] = max(pior.get('M', 0), self._comparar(
                        nome + ' M', [geojson_para_geom(t['geometry']) for t in letras], q, tr))
                # linha de chamada e bloco de texto (todos os tipos)
                w = [geojson_para_geom(d['geometry']) for d in _lin(deco, 'leader')]
                q = avaliar(m.expr('area_chamada'), vl, f)
                if w:
                    pior['chamada'] = max(pior.get('chamada', 0), self._comparar(nome + ' chamada', w, partes(q), tr))
                else:
                    self.assertTrue(q is None or q.isNull(), nome + ': chamada que o Web não desenha')
                linhas = '\n'.join(avaliar(m.expr_linhas(), vl, f) or [])
                blocos = _web_textos(deco, lambda p: p.get('boxed') and '\n' in p['text'] or p['text'] == linhas)
                blocos = [b for b in blocos if b['properties']['text'] == linhas]
                if linhas:
                    self.assertEqual(len(blocos), 1, nome + ': o bloco do Web')
                    b = blocos[0]
                    pq = avaliar(m.expr('area_rotulo_ponto'), vl, f)
                    d = _hausdorff(geojson_para_geom(b['geometry']), pq, tr)
                    self.assertLess(d, TOL_M, nome + ' bloco')
                    pior['bloco'] = max(pior.get('bloco', 0), d)
                    quad = avaliar(m.expr('area_rotulo_quadrante'), vl, f)
                    self.assertEqual(quad, ANCORA_QUADRANTE[b['properties']['anchor']], nome + ' âncora do bloco')
                    rot = avaliar(m.expr('area_rotulo_rotacao'), vl, f)
                    self.assertAlmostEqual(rot, b['properties']['rotate'], delta=1.0)
                ech = _web_textos(deco, lambda p: p.get('bold') and p.get('boxed'))
                pe = avaliar(m.expr('area_escalao_ponto'), vl, f)
                if ech:
                    self.assertEqual(len(ech), 1)
                    d = _hausdorff(geojson_para_geom(ech[0]['geometry']), pe, tr)
                    self.assertLess(d, TOL_M, nome + ' escalão')
                    pior['escalão'] = max(pior.get('escalão', 0), d)
                else:
                    self.assertTrue(pe is None or pe.isNull(), nome + ': escalão que o Web não desenha')
        medir('contra o Web ({} casos): desvio máximo por decoração, m: {}'.format(
            len(self.casos), ', '.join('{} {:.2f}'.format(k, v) for k, v in sorted(pior.items()))))

    def test_regua_reprova_saida_degradada(self):
        """Pior caso: a saída REAL do QGIS degradada em cada eixo que a régua mede."""
        m = ea()
        nome, coords, attrs, vl, f = self.casos[0]          # 151203 quadra
        deco = self.web[0]
        tr = self._tr(f)
        w = [p for d in _lin(deco, 'ticks') for p in partes(geojson_para_geom(d['geometry']))]
        q = partes(avaliar(m.expr('area_dentes'), vl, f))
        self.assertLess(_pareados(w, q, tr), TOL_M)               # a real passa
        s_graus = 0.2 / 111.0
        # posição: meia unidade para leste
        movida = [QgsGeometry(g) for g in q]
        for g in movida:
            g.translate(0.5 * s_graus, 0)
        self.assertGreater(_pareados(w, movida, tr), TOL_M)
        # lado: cada dente refletido para dentro
        refletida = []
        for g in q:
            a, b = g.asPolyline()
            refletida.append(QgsGeometry.fromPolylineXY([a, QgsPointXY(2 * a.x() - b.x(), 2 * a.y() - b.y())]))
        self.assertGreater(_pareados(w, refletida, tr), TOL_M)
        self.assertFalse(dentes_para_fora(f, refletida))
        # contagem: um dente a menos
        with self.assertRaises(AssertionError):
            self._comparar('degradada', w, q[:-1], tr)

    def test_dentes_para_fora_nos_dois_sentidos(self):
        m = ea()
        for nome, coords, attrs, vl, f in self.casos:
            if attrs['symbol_code'] in ('151203', '170999-01'):
                with self.subTest(caso=nome):
                    e = 'area_dentes' if attrs['symbol_code'] == '151203' else 'area_portoes'
                    self.assertTrue(dentes_para_fora(f, partes(avaliar(m.expr(e), vl, f))), nome)


ANCORA_QUADRANTE = {'left': 5, 'bottom-left': 2, 'bottom': 1, 'bottom-right': 0, 'right': 3,
                    'top-right': 6, 'top': 7, 'top-left': 8, 'center': 4}


def dentes_para_fora(f, tracos):
    """Todo traço começa na borda (a menos de 0,5 m, no plano local) e termina fora da área."""
    tr = plano(*centro_de(f))
    g = metrico(f.geometry(), tr)
    borda = QgsGeometry(g.constGet().boundary())
    if not tracos:
        return False
    for t in tracos:
        t = metrico(t, tr)
        a, b = t.asPolyline()[0], t.asPolyline()[-1]
        if borda.distance(QgsGeometry.fromPointXY(a)) > 0.5:
            return False
        if g.contains(QgsGeometry.fromPointXY(b)):
            return False
    return True


# ---------------------------------------------------------------- 4. zoom

def _comprimento_m(g, f):
    return metrico(g, plano(*centro_de(f))).length()


class TestZoom(unittest.TestCase):

    def _dente(self, vl, f, z):
        g = partes(avaliar(ea().expr('area_dentes'), vl, f, mapa(centro_de(f), z)))
        return _comprimento_m(g[0], f), len(g)

    def test_desenho_preso_ao_terreno_e_a_tela(self):
        vl, f = nova_area(QUADRA, symbol_code='151203', zoom_corr=True)
        a, na = self._dente(vl, f, Z0)
        b, nb = self._dente(vl, f, Z0 + 2)
        self.assertAlmostEqual(a, 0.6 * 200, delta=1)      # 0,6 s, s = 200 m
        self.assertAlmostEqual(b, a, delta=0.5)            # ligada: o mesmo no terreno
        vl, f = nova_area(QUADRA, symbol_code='151203', zoom_corr=False)
        c, nc = self._dente(vl, f, Z0)
        d, nd = self._dente(vl, f, Z0 + 2)
        self.assertAlmostEqual(c, a, delta=1)              # no zoom de criação os dois coincidem
        self.assertAlmostEqual(d, c / 4, delta=0.5)        # desligada: 2^(z0 - z) no terreno, fixo na tela
        self.assertGreater(nd, nc)
        medir('zoom: dente {:.1f} m em z{} e z{} ligado; {:.1f} e {:.1f} m desligado'.format(a, Z0, Z0 + 2, c, d))

    def test_texto_escala_com_a_carta(self):
        m = ea()
        vl, f = nova_area(QUADRA, symbol_code='150000', zoom_corr=True, tipo='A')
        t0 = avaliar(m.expr_tamanho_px(m.TS), vl, f, mapa(centro_de(f), Z0))
        t1 = avaliar(m.expr_tamanho_px(m.TS), vl, f, mapa(centro_de(f), Z0 + 1))
        self.assertAlmostEqual(t0, 14 * MM_POR_PX, delta=0.01)
        self.assertAlmostEqual(t1, 2 * t0, delta=0.02)
        vl, f = nova_area(QUADRA, symbol_code='150000', zoom_corr=False, tipo='A')
        t2 = avaliar(m.expr_tamanho_px(m.TS), vl, f, mapa(centro_de(f), Z0 + 1))
        self.assertAlmostEqual(t2, t0, delta=0.01)

    def test_piso_da_hachura(self):
        """Com a carta: no terreno até o piso de 4 px (2,5 espessuras); abaixo dele, dobra."""
        m = ea()
        e = m.expr_distancia_hachura(math.sqrt(0.5))
        vl, f = nova_area(QUADRA, symbol_code='151199-01', hatch_enabled=True, hatch_type='cross-diagonal',
                          hatch_spacing=8.0, hatch_line_width=1.5)
        mm = [avaliar(e, vl, f, mapa(centro_de(f), Z0 + dz)) for dz in (0, 1, -1, -2, -3)]
        px = [v / MM_POR_PX for v in mm]
        self.assertAlmostEqual(px[0], 8 * math.sqrt(0.5), delta=0.05)
        self.assertAlmostEqual(px[1], 2 * px[0], delta=0.1)          # aproximar: cresce com a carta
        for v in px:
            self.assertGreaterEqual(v, 4 - 1e-6)                     # nunca abaixo do piso
        self.assertAlmostEqual(px[2], px[0], delta=0.1)              # z-1: 2,83 px dobra para 5,66
        medir('hachura 151199-01 (8 px, traço 1,5): período em px nos zooms z0, +1, -1, -2, -3: '
              + ', '.join('{:.2f}'.format(v) for v in px))
        vl, f = nova_area(QUADRA, symbol_code='151199-01', hatch_enabled=True, hatch_type='cross-diagonal',
                          hatch_spacing=8.0, zoom_corr=False)
        fixo = [avaliar(e, vl, f, mapa(centro_de(f), Z0 + dz)) / MM_POR_PX for dz in (0, 2)]
        self.assertAlmostEqual(fixo[0], fixo[1], delta=1e-6)          # desligada: padrão fixo na tela


# ---------------------------------------------------------------- 5. render

def renderizar(vl, caminho, ms):
    ms.setLayers([vl])
    ms.setBackgroundColor(QColor('white'))
    # como o QgsMapCanvas: sem o escopo do mapa, @map_scale é nulo e a Correção de Zoom não age
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.globalScope())
    ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererParallelJob(ms)
    t = time.perf_counter()
    job.start()
    job.waitForFinished()
    dt = time.perf_counter() - t
    img = job.renderedImage()
    if caminho:
        img.save(caminho)
    return img, dt


def diferenca_max(a, b):
    """Maior diferença de canal entre duas imagens do mesmo tamanho."""
    d = 0
    for y in range(a.height()):
        for x in range(a.width()):
            pa, pb = a.pixel(x, y), b.pixel(x, y)
            if pa != pb:
                ca, cb = QColor(pa), QColor(pb)
                d = max(d, abs(ca.red() - cb.red()), abs(ca.green() - cb.green()), abs(ca.blue() - cb.blue()))
    return d


def tinta(img):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            if QColor(img.pixel(x, y)).lightness() < 200:
                n += 1
    return n


def _popular(caminho, feicoes):
    vl = camada(caminho)
    fs = []
    for coords, attrs in feicoes:
        f = QgsFeature(vl.fields())
        f.setGeometry(QgsGeometry.fromMultiPolygonXY([[[QgsPointXY(*p) for p in coords + [coords[0]]]]]))
        valores = dict(schema.padroes('coordination_area'))
        valores.update(ebgeo_id=str(uuid.uuid4()), created_zoom=Z0, symbol_size_km=0.2)
        valores.update(attrs)
        for k, v in valores.items():
            f[k] = v
        fs.append(f)
    assert vl.dataProvider().addFeatures(fs)[0]
    return camada(caminho)


def _sete(dx=0.0, dy=0.0):
    t = dict(tipo='Obj', identificacao='BAGRE', gdh_ini='121400Z JUN', gdh_fim='121800Z JUN')
    q = [(x + dx, y + dy) for x, y in QUADRA]
    return [
        (q, dict(symbol_code='150000', **t)),
        ([(x + 0.06, y) for x, y in q], dict(symbol_code='151100', opacity=1.0, hatch_enabled=True,
                                             hatch_type='diagonal-right')),
        ([(x + 0.12, y) for x, y in q], dict(symbol_code='151199-01', opacity=1.0, hatch_enabled=True,
                                             hatch_type='cross-diagonal')),
        ([(x, y - 0.05) for x, y in q], dict(symbol_code='151203', escalao='II', line_width=5.0, tipo='PF', identificacao='1')),
        ([(x + 0.06, y - 0.05) for x, y in q], dict(symbol_code='151000', **t)),
        ([(x + 0.12, y - 0.05) for x, y in q], dict(symbol_code='170999-01', line_width=4.0, tipo='VAB', identificacao='CONDOR',
                                                    altitude_max='5000 ft', altitude_min='1500 ft',
                                                    portoes=json.dumps([{'ratio': 0.62, 'nome': 'PORTÃO ALFA'}]))),
        ([(x + 0.18, y - 0.025) for x, y in q], dict(symbol_code='270800', line_color='#00B04E', fill_color='#00B04E',
                                                     tipo='Obj', identificacao='BAGRE')),
    ]


class TestRender(unittest.TestCase):

    def test_sete_tipos_desenham_mais_que_o_contorno(self):
        m = ea()
        caminho = _calco('render7')
        vl = _popular(caminho, _sete())
        ext = vl.extent()
        c = ext.center()
        vl.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
            {'color': '0,0,0,0', 'outline_color': '0,0,0', 'outline_width': str(3 * MM_POR_PX)})))
        pura, _ = renderizar(vl, os.path.join(SAIDA, 'area_7_tipos_so_contorno.png'),
                             mapa((c.x(), c.y()), 11.5, tamanho=(1100, 800)))
        m.aplicar_estilo(vl, 'coordination_area')
        img, dt = renderizar(vl, os.path.join(SAIDA, 'area_7_tipos.png'), mapa((c.x(), c.y()), 11.5, tamanho=(1100, 800)))
        self.assertGreater(tinta(img), tinta(pura))
        medir('render dos 7 tipos 1100x800: {:.2f} s; PNG em {}'.format(dt, SAIDA))

    def test_estilo_salvo_reabre_sem_plugin(self):
        from Calco.estilos_taticos import salvar_estilo_padrao
        m = ea()
        caminho = _calco('persistencia_area')
        vl = _popular(caminho, _sete())
        c = vl.extent().center()
        ms = lambda: mapa((c.x(), c.y()), 11.5, tamanho=(900, 700))  # noqa: E731
        antes, _ = renderizar(vl, None, ms())
        m.aplicar_estilo(vl, 'coordination_area')
        ok, msg = salvar_estilo_padrao(vl)
        self.assertTrue(ok, msg)
        img, _ = renderizar(vl, None, ms())
        # reaberta só com qgis.core: o estilo padrão do layer_styles vem sozinho
        novo = QgsVectorLayer('{}|layername=coordination_area'.format(caminho), 'reaberta', 'ogr')
        self.assertIsInstance(novo.renderer(), QgsRuleBasedRenderer)
        self.assertEqual(len(novo.renderer().rootRule().children()), 9)
        self.assertTrue(novo.labelsEnabled())
        img2, _ = renderizar(novo, os.path.join(SAIDA, 'area_reaberta_sem_plugin.png'), ms())
        # medido em 2026-10-04: a reaberta difere da original em até 2 níveis de cor por canal
        # (suavização), e a régua reprova a camada sem o estilo (diferença de 255)
        self.assertLessEqual(diferenca_max(img2, img), 3)
        self.assertGreater(diferenca_max(antes, img), 64)

    def test_desempenho_30_areas(self):
        import random
        random.seed(3)
        m = ea()
        caminho = _calco('desempenho_area')
        sete = _sete()
        feicoes = []
        for i in range(30):
            dx, dy = (i % 6) * 0.25, (i // 6) * 0.12
            coords, attrs = sete[i % 7]
            feicoes.append(([(x + dx, y + dy) for x, y in coords], attrs))
        vl = _popular(caminho, feicoes)
        c = vl.extent().center()
        _, t_puro = renderizar(vl, None, mapa((c.x(), c.y()), 10, tamanho=(1200, 900)))
        m.aplicar_estilo(vl, 'coordination_area')
        tempos = [renderizar(vl, None, mapa((c.x(), c.y()), 10, tamanho=(1200, 900)))[1] for _ in range(3)]
        renderizar(vl, os.path.join(SAIDA, 'area_30.png'), mapa((c.x(), c.y()), 10, tamanho=(1200, 900)))
        medir('desempenho: 30 áreas (7 tipos), 1200x900: sem estilo {:.2f} s; com estilo {}'.format(
            t_puro, ' / '.join('{:.2f} s'.format(t) for t in tempos)))
        self.assertLess(min(tempos), 30)

    def test_interior_seleciona(self):
        """No QGIS a seleção é pela geometria: clicar no meio de uma área sem preenchimento seleciona."""
        vl, f = nova_area(QUADRA, symbol_code='151100', opacity=1.0, hatch_enabled=True, hatch_type='diagonal-right')
        ea().aplicar_estilo(vl, 'coordination_area')
        c = f.geometry().pointOnSurface().asPoint()
        r = QgsRectangle(c.x() - 1e-5, c.y() - 1e-5, c.x() + 1e-5, c.y() + 1e-5)
        vl.selectByRect(r)
        self.assertIn(f.id(), vl.selectedFeatureIds())


# ---------------------------------------------------------------- 6. ferramenta, painel, importador, gerenciador

class TestFerramenta(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from qgis.gui import QgsMapCanvas
        from Calco.calco import Calco, definir_calco_ativo
        cls.calco = Calco(os.path.join(TMP, 'ferramenta_area.gpkg'))
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.canvas = QgsMapCanvas()
        cls.canvas.resize(800, 600)
        cls.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        cls.canvas.setExtent(QgsRectangle(-43.12, -22.96, -43.02, -22.88))
        cls.canvas.refresh()

    def _clique(self, ft, x, y, botao=None):
        from qgis.gui import QgsMapMouseEvent
        from qgis.PyQt.QtCore import QEvent, QPoint, Qt
        botao = botao or Qt.MouseButton.LeftButton
        ev = QgsMapMouseEvent(self.canvas, QEvent.Type.MouseButtonRelease, QPoint(x, y), botao, botao,
                              Qt.KeyboardModifier.NoModifier)
        ft.canvasReleaseEvent(ev)

    def test_captura_e_atributos_de_nascimento(self):
        from qgis.PyQt.QtCore import Qt
        from Calco.ferramentas import FerramentaPoligono
        from Calco import zoom
        ft = FerramentaPoligono(self.canvas, 'coordination_area')
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append(e))
        lyr = self.calco.camada('coordination_area')
        antes = lyr.featureCount()
        self._clique(ft, 100, 100)
        self._clique(ft, 600, 120)
        self.assertEqual(lyr.featureCount(), antes)                  # dois vértices não fecham
        self._clique(ft, 650, 500, Qt.MouseButton.RightButton)
        self.assertEqual(lyr.featureCount(), antes + 1)
        f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(criadas[0])))
        g = f.geometry()
        self.assertEqual(g.type(), Qgis.GeometryType.Polygon)
        self.assertEqual(len(list(g.vertices())), 4)                 # 3 vértices e o fecho
        self.assertEqual(f['symbol_code'], '150000')
        z = f['created_zoom']
        self.assertIsNotNone(z)
        lat = g.centroid().asPoint().y()
        esperado = ea().tamanho_inicial_km(g.vertexAt(0).y(), z)
        self.assertAlmostEqual(f['symbol_size_km'], esperado, places=3)
        self.assertAlmostEqual(f['symbol_size_km'] * 1000 / zoom.metros_por_pixel_de_zoom(z, lat), 18, delta=0.5)
        self.assertEqual(f['text_position'], 'borda')
        self.assertTrue(f['zoom_corr'])

    def test_preview_e_teclas(self):
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt.QtGui import QKeyEvent
        from qgis.PyQt.QtCore import QEvent
        from Calco.ferramentas import FerramentaPoligono
        ft = FerramentaPoligono(self.canvas, 'coordination_area')
        self.canvas.setMapTool(ft)
        self._clique(ft, 100, 100)
        self._clique(ft, 400, 120)
        self.assertTrue(ft.banda.isVisible())
        self.assertEqual(ft.banda.numberOfVertices(), 2)
        ft.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(len(ft.vertices), 1)
        ft.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        self.assertEqual(len(ft.vertices), 0)

    def test_razao_na_borda(self):
        """ratioAlongBorder: o vértice mais ao norte é 0, e o sentido do traçado não muda a razão."""
        m = ea()
        for coords in (QUADRA, QUADRA[::-1]):
            g = QgsGeometry.fromPolygonXY([[QgsPointXY(*p) for p in coords + [coords[0]]]])
            self.assertAlmostEqual(m.razao_na_borda(g, QgsPointXY(-43.075, -22.89)), 0.0, places=3)
            # a leste do norte, no sentido horário: o lado NE vem antes do lado S
            r_ne = m.razao_na_borda(g, QgsPointXY(-43.055, -22.895))
            r_s = m.razao_na_borda(g, QgsPointXY(-43.06, -22.925))
            self.assertLess(r_ne, r_s)
            self.assertLess(r_ne, 0.25)


class TestPainel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(TMP, 'painel_area.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.iface = get_iface()
        cls.painel = PainelCalco(cls.iface)

    @classmethod
    def tearDownClass(cls):
        # a troca de tipo grava o último tipo no QgsSettings: o teste não deixa rastro no perfil
        from qgis.core import QgsSettings
        QgsSettings().remove(ea().CHAVE_ULTIMO_TIPO)

    def _nova(self, **attrs):
        from Calco.ferramentas import gravar_feicao
        a = dict(schema.padroes('coordination_area'))
        a.update(ebgeo_id=str(uuid.uuid4()), created_zoom=Z0)
        a.update(attrs)
        lyr = self.calco.camada('coordination_area')
        g = QgsGeometry.fromPolygonXY([[QgsPointXY(*p) for p in QUADRA + [QUADRA[0]]]])
        eid = gravar_feicao(lyr, 'coordination_area', g, a)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        return lyr, eid

    def _reler(self, eid):
        # o dock edita no buffer da camada (Salvar e Descartar): relê o disco depois do Salvar
        self.painel.salvar()
        _APP.processEvents()
        nova = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_area'), 'r', 'ogr')
        return next(nova.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def test_campos_por_tipo(self):
        esperados = {
            '150000': {'symbol_code', 'symbol_size_km', 'zoom_corr', 'tipo', 'identificacao', 'gdh_ini', 'gdh_fim',
                       'outras_info', 'text_position', 'text_ratio', 'text_size', 'line_color', 'fill_color', 'hatch_type'},
            '151203': {'escalao'},
            '170999-01': {'portoes', 'portoes_ocultos', 'altitude_max', 'altitude_min'},
            '270800': {'minas'},
        }
        for cod, cols in esperados.items():
            with self.subTest(cod=cod):
                self._nova(symbol_code=cod)
                # o dock da especificação monta todas as linhas e esconde as que não valem para o tipo
                vis = self.painel.campos_visiveis()
                self.assertTrue(cols <= vis, cols - vis)
        self._nova(symbol_code='150000')
        self.assertNotIn('escalao', self.painel.campos_visiveis())
        self.assertNotIn('portoes', self.painel.campos_visiveis())
        cb = self.painel.widgets['symbol_code']
        self.assertEqual(cb.count(), 7)

    def test_troca_de_tipo_aplica_os_padroes(self):
        lyr, eid = self._nova(symbol_code='150000')
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('270800'))
        _APP.processEvents()
        f = self._reler(eid)
        self.assertEqual(f['symbol_code'], '270800')
        self.assertEqual(f['line_color'].lower(), '#00b04e')
        # cor escolhida pela pessoa fica
        lyr, eid = self._nova(symbol_code='150000', line_color='#123456')
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('151100'))
        _APP.processEvents()
        f = self._reler(eid)
        self.assertEqual(f['line_color'], '#123456')
        self.assertTrue(f['hatch_enabled'])
        self.assertEqual(f['hatch_type'], 'diagonal-right')

    def test_portao_pelo_painel(self):
        lyr, eid = self._nova(symbol_code='170999-01')
        self.painel.widgets['portoes'].acrescentar()
        self.painel._gravar_pendentes()
        f = self._reler(eid)
        # o painel grava o objeto: o QGIS relê lista (texto só em calco antigo, com a string escapada)
        gs = f['portoes'] if isinstance(f['portoes'], list) else json.loads(f['portoes'])
        self.assertEqual(len(gs), 1)
        self.assertEqual(gs[0]['nome'], 'PORTÃO ALFA')
        self.assertAlmostEqual(gs[0]['ratio'], 0.5)


class TestImportador(unittest.TestCase):

    def test_balde_coordination_areas(self):
        import io
        import zipfile
        from Calco.importador import escritor, arvore
        props = {'id': 'area-1', 'layerId': 'default', 'nome': 'VAB CONDOR', 'symbol_code': '170999-01',
                 'symbol_size': 0.158, 'createdAtZoom': 13, 'zoomCorrectionEnabled': True, 'tipo': 'VAB',
                 'identificacao': 'CONDOR', 'altitudeMax': '5000 ft', 'altitudeMin': '1500 ft',
                 'gdhIni': '121400Z JUN', 'gdhFim': '121800Z JUN', 'text_position': 'externa', 'text_ratio': None,
                 'portoes': [{'ratio': 0.6265, 'nome': 'PORTÃO ALFA'}], 'portoes_ocultos': False,
                 'minas': ['qualquer', 'ap', 'ac'], 'lineColor': '#000000', 'lineWidth': 4, 'fillColor': '#000000',
                 'opacity': 0, 'hatchType': 'none', 'hatchEnabled': False, 'visivel': True,
                 'baseCoordinates': [list(p) for p in QUADRA]}
        feat = {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [[list(p) for p in QUADRA + [QUADRA[0]]]]},
                'properties': props}
        data = {'version': '3.0', 'mapOrder': ['Principal'], 'currentMap': 'Principal',
                'maps': {'Principal': {'features': {'coordination_areas': [feat]},
                                       'layers': {'default': {'name': 'Padrão', 'visible': True, 'order': 0}}}}}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('data.json', json.dumps(data, ensure_ascii=False).encode('utf-8'))
        arquivo = os.path.join(TMP, 'area.ebgeo')
        with open(arquivo, 'wb') as fh:
            fh.write(buf.getvalue())
        destino = os.path.join(TMP, 'area_importada.gpkg')
        escritor.importar(arquivo, destino)
        vl = QgsVectorLayer('{}|layername=coordination_area'.format(destino), 'a', 'ogr')
        self.assertEqual(vl.featureCount(), 1)
        f = next(vl.getFeatures())
        self.assertEqual(f['symbol_code'], '170999-01')
        self.assertAlmostEqual(f['symbol_size_km'], 0.158)
        self.assertEqual(f['altitude_max'], '5000 ft')
        self.assertEqual(f['text_position'], 'externa')
        v = f['portoes']
        gs = json.loads(v) if isinstance(v, str) else v
        self.assertEqual(gs[0]['nome'], 'PORTÃO ALFA')
        self.assertEqual(f.geometry().type(), Qgis.GeometryType.Polygon)
        # a árvore estiliza a camada com o estilo da área
        projeto = QgsProject.instance()
        grupo = arvore.montar_arvore(destino, projeto)
        camadas = [n.layer() for n in grupo.findLayers() if n.layer().customProperty('ebgeo_calco/tipo') == 'coordination_area']
        self.assertEqual(len(camadas), 1)
        r = camadas[0].renderer()
        self.assertIsInstance(r, QgsRuleBasedRenderer)
        descricoes = [x.label() for x in r.rootRule().children()[0].children()]
        self.assertIn('Volume de aproximação de base (170999-01)', descricoes)
        # Na camada da árvore a coluna JSON chega como LISTA (na camada aberta à mão, como texto):
        # os portões, as minas e os nomes têm de ler os dois (medido em 2026-10-04 na fixture 06).
        lyr = camadas[0]
        f = next(lyr.getFeatures())
        self.assertIsInstance(f['portoes'], list)
        m = ea()
        tracos = partes(avaliar(m.expr('area_portoes'), lyr, f))
        self.assertEqual(len(tracos), 2)
        self.assertEqual(avaliar(m.expr_nome_portao(0), lyr, f), 'PORTÃO ALFA')
        self.assertEqual(avaliar(m.expr_lista_json('minas'), lyr, f), ['qualquer', 'ap', 'ac'])
        # e na camada aberta à mão sobre o mesmo GeoPackage (o caminho do texto é o de TestContraWeb)
        vl2 = QgsVectorLayer('{}|layername=coordination_area'.format(destino), 'texto', 'ogr')
        f2 = next(vl2.getFeatures())
        self.assertEqual(len(partes(avaliar(m.expr('area_portoes'), vl2, f2))), 2)
        self.assertEqual(avaliar(m.expr_nome_portao(0), vl2, f2), 'PORTÃO ALFA')


class TestGerenciador(unittest.TestCase):

    def test_ferramenta_depois_da_linha_de_coordenacao_sem_atalho(self):
        from Calco.gerenciador import FERRAMENTAS
        tipos = [t for t, _i, _r in FERRAMENTAS]
        self.assertIn('coordination_area', tipos)
        self.assertEqual(tipos.index('coordination_area'), tipos.index('coordination_line') + 1)
        rot = dict((t, r) for t, _i, r in FERRAMENTAS)['coordination_area']
        self.assertEqual(rot, 'Área de Coordenação')
        from qgis.testing.mocked import get_iface
        from qgis.PyQt.QtWidgets import QMenu
        from Calco.gerenciador import GerenciadorCalco
        from Calco.ferramentas import FerramentaPoligono
        g = GerenciadorCalco(get_iface(), QMenu('EBGeo'))
        g.initGui()
        try:
            ft = g.ferramentas['coordination_area']
            self.assertIsInstance(ft, FerramentaPoligono)
            self.assertTrue(ft.action().shortcut().isEmpty())
            self.assertFalse(ft.action().icon().isNull())
        finally:
            g.unload()


def tearDownModule():
    print('\n--- medidas ---')
    for t in MEDIDAS:
        print(t)


if __name__ == '__main__':
    r = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if r.wasSuccessful() else 1)
