# -*- coding: utf-8 -*-
"""
Linha de Coordenação: os quatro símbolos do capítulo VII do MD33-C-01 que o EBGeo Web
ganhou em 2026-10-04 (290500 Arame de tração, 140000 Linha de manobra genérica, 140200
Linha de Contato, 240701 Concentração de fogos em alvo linear), o esquema, o painel e o
importador.

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/Calco/testes/test_linha_coordenacao_vii.py

Variáveis de ambiente opcionais:
    EBGEO_WEB_DIR      raiz do ebgeo_web; com ela (e node) o desenho do QGIS é comparado ao
                       do código do Web rodado em node. Sem ela, esses testes são pulados.
    EBGEO_NODE         executável do node, quando o python-qgis.bat o tira do PATH.
    EBGEO_TESTE_SAIDA  pasta dos PNG de conferência (padrão: pasta temporária).

Cada régua é provada contra um pior caso degradado da saída real, que ela tem de reprovar.
"""
import io
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
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, '..', '..'))
if PLUGIN not in sys.path:
    sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsGeometry,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRuleBasedLabeling,
    QgsPalLayerSettings,
    QgsProperty,
    QgsRuleBasedRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

QGS = QgsApplication.instance()
if QGS is None:
    QGS = QgsApplication([], True)
    QGS.initQgis()

from Calco import estilos_taticos as et  # noqa: E402
from Calco import gpkg, schema  # noqa: E402

R_TURF = 6371008.8
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_lc7_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_lc7_')
CALCO = os.path.join(TMP, 'calco.gpkg')
gpkg.criar_calco(CALCO, ['coordination_line'])
MEDIDAS = []
NOVOS = ('290500', '140000', '140200', '240701')
QUAD_DA_ANCORA = {'bottom-right': 0, 'bottom': 1, 'bottom-left': 2, 'right': 3, 'center': 4,
                  'left': 5, 'top-right': 6, 'top': 7, 'top-left': 8}


def medir(t):
    MEDIDAS.append(t)


# ---------------------------------------------------------------------------
# Geodésia do turf e linhas de teste
# ---------------------------------------------------------------------------

def hav_m(a, b):
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R_TURF * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def destino(p, d, rumo):
    la1, lo1, br = math.radians(p[1]), math.radians(p[0]), math.radians(rumo)
    dd = d / R_TURF
    la2 = math.asin(math.sin(la1) * math.cos(dd) + math.cos(la1) * math.sin(dd) * math.cos(br))
    lo2 = lo1 + math.atan2(math.sin(br) * math.sin(dd) * math.cos(la1), math.cos(dd) - math.sin(la1) * math.sin(la2))
    return (math.degrees(lo2), math.degrees(la2))


def zigue(p0, rumos, d=3000.0):
    pts = [tuple(p0)]
    for r in rumos:
        pts.append(destino(pts[-1], d, r))
    return pts


# Dobras de 30, 60, 90 e 120 graus, alternando o lado.
DOBRAS = zigue((-47.95, -15.80), [80, 110, 50, 140, 20])


# ---------------------------------------------------------------------------
# Camada, avaliação, partes
# ---------------------------------------------------------------------------

def camada(caminho=CALCO):
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_line'), 'lc', 'ogr')
    assert vl.isValid()
    return vl


def nova_feicao(coords, caminho=CALCO, **attrs):
    vl = camada(caminho)
    f = QgsFeature(vl.fields())
    f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in coords]))
    valores = dict(schema.padroes('coordination_line'))
    valores.update(attrs)
    for k, v in valores.items():
        if vl.fields().indexOf(k) >= 0:
            f[k] = v
    ok, novas = vl.dataProvider().addFeatures([f])
    assert ok
    vl = camada(caminho)
    return vl, vl.getFeature(novas[0].id())


def mapa(centro, escala=50000, crs='EPSG:3857', tamanho=(1000, 800)):
    ms = QgsMapSettings()
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(96)
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(), QgsProject.instance())
    c = tr.transform(QgsPointXY(*centro))
    upp = escala * 0.0254 / 96
    w, h = tamanho[0] * upp / 2, tamanho[1] * upp / 2
    ms.setExtent(QgsRectangle(c.x() - w, c.y() - h, c.x() + w, c.y() + h))
    return ms


def avaliar(expr, vl, f, ms=None):
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
    if ms is None:
        c = f.geometry().centroid().asPoint()
        ms = mapa((c.x(), c.y()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ctx.setFeature(f)
    e = QgsExpression(expr)
    if e.hasParserError():
        raise AssertionError('parse: ' + e.parserErrorString())
    e.prepare(ctx)
    v = e.evaluate(ctx)
    if e.hasEvalError():
        raise AssertionError('avaliação: ' + e.evalErrorString())
    return v


def partes(g):
    if g is None or (hasattr(g, 'isNull') and (g.isNull() or g.isEmpty())):
        return []
    out = []
    for p in g.asGeometryCollection():
        if p.type() == Qgis.GeometryType.Line:
            out.append([(v.x(), v.y()) for v in p.asPolyline()])
        elif p.type() == Qgis.GeometryType.Point:
            pt = p.asPoint()
            out.append([(pt.x(), pt.y())])
    return out


def partes_geojson(g):
    if not g:
        return []
    t, c = g['type'], g['coordinates']
    if t == 'LineString':
        return [[tuple(p[:2]) for p in c]]
    if t == 'MultiLineString':
        return [[tuple(p[:2]) for p in ln] for ln in c]
    if t == 'Point':
        return [[tuple(c[:2])]]
    return []


def _tr_local(p):
    crs = QgsCoordinateReferenceSystem('PROJ:+proj=tmerc +lat_0={} +lon_0={} +R={} +units=m'.format(p[1], p[0], R_TURF))
    return QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())


def hausdorff_m(a, b):
    tr = _tr_local(a[0])

    def geo(p):
        g = QgsGeometry.fromPointXY(QgsPointXY(*p[0])) if len(p) == 1 else \
            QgsGeometry.fromPolylineXY([QgsPointXY(*v) for v in p])
        g.transform(tr)
        return g
    return geo(a).hausdorffDistance(geo(b))


def desvio_partes(web, qgis):
    if len(web) != len(qgis):
        return None
    return max(hausdorff_m(a, b) for a, b in zip(web, qgis))


def geometrias(codigo, vl, f, ms=None):
    """{'linha': partes, 'inimigo': partes} do símbolo, avaliadas como o estilo as desenha."""
    ex = et.expr_linha_coordenacao(codigo)
    out = {'linha': partes(avaliar(ex['linha'], vl, f, ms))}
    if ex.get('inimigo'):
        out['inimigo'] = partes(avaliar(ex['inimigo'], vl, f, ms))
    return out


def regras_texto(codigo):
    return [r for r in et.regras_texto_linha() if r['codigo'] == codigo]


def textos_qgis(codigo, vl, f, ms=None):
    """Os rótulos que o estilo põe na feição: ponto, texto, rotação, quadrante e vão em em."""
    out = []
    for r in regras_texto(codigo):
        if not avaliar(r['filtro'], vl, f, ms):
            continue
        ponto = avaliar(r['geometria'], vl, f, ms)
        tam = float(avaliar(r['tamanho'], vl, f, ms))
        dx, dy = (float(v) for v in str(avaliar(r['deslocamento'], vl, f, ms)).split(','))
        out.append({'onde': r['onde'], 'lado': r['lado'], 'texto': avaliar(r['texto'], vl, f, ms),
                    'ponto': ponto.asPoint(), 'rotacao': float(avaliar(r['rotacao'], vl, f, ms)),
                    'quadrante': int(avaliar(r['quadrante'], vl, f, ms)), 'vao': (dx / tam, dy / tam)})
    return out


# ---------------------------------------------------------------------------
# O Web em node
# ---------------------------------------------------------------------------

NODE_HARNESS = r'''
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
const [frontend, entrada, saida] = process.argv.slice(2);
const js = join(frontend, 'src', 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-web-'));
const stub = join(dir, 'tools.mjs');
writeFileSync(stub, `export { default as BaseGeometry } from ${JSON.stringify(pathToFileURL(join(js, 'tool_manager', 'base_geometry.js')).href)};\n`);
const hooks = join(dir, 'hooks.mjs');
const mapa = { '@tools/helpers/': join(js, 'tool_manager', 'helpers'), '@utils/': join(js, 'utilities'), '@layers/': join(js, 'layers') };
writeFileSync(hooks, `
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const STUB = ${JSON.stringify(pathToFileURL(stub).href)};
const MAPA = ${JSON.stringify(mapa)};
export async function resolve(spec, ctx, next) {
  if (spec === '@tools') return { url: STUB, shortCircuit: true };
  for (const [p, d] of Object.entries(MAPA)) {
    if (spec.startsWith(p)) return { url: pathToFileURL(join(d, spec.slice(p.length))).href, shortCircuit: true };
  }
  return next(spec, ctx);
}
`);
register(pathToFileURL(hooks).href);
const req = createRequire(join(frontend, 'package.json'));
const turfMod = await import(pathToFileURL(req.resolve('@turf/turf')).href);
globalThis.turf = { ...(turfMod.default ?? turfMod) };
const CL = (await import(pathToFileURL(join(js, 'military_tools', 'coordination_line_tool', 'add_coordination_line_geometry.js')).href)).default;
const cat = await import(pathToFileURL(join(js, 'military_tools', 'coordination_line_tool', 'coordination_line_catalog.js')).href);
const cl = new CL();
const casos = JSON.parse(readFileSync(entrada, 'utf8'));
const out = casos.map((c) => {
  const p = { ...c.props, baseCoordinates: c.coords };
  return { geom: cl.generate(p), layout: cl.describeLayout(p),
           extras: cl.buildExtras({ properties: { id: 'x', ...p } }, undefined, 0).map((e) => ({ geometry: e.geometry, properties: e.properties })) };
});
const catalogo = Object.values(cat.LINEAR_SYMBOLS).map((s) => ({ id: s.id, nome: s.name, grupo: s.group, cor: s.defaultColor,
  textos: s.textFields || null, segunda: s.secondColor ? s.secondColor.property : null, segundaPadrao: s.secondColor ? s.secondColor.defaultValue : null,
  fixo: !!s.fixed, continuo: !!s.continuous, glifo: s.glyph }));
writeFileSync(saida, JSON.stringify({ casos: out, catalogo, grupos: cat.SYMBOL_GROUPS }));
'''


def rodar_web(casos):
    web = os.environ.get('EBGEO_WEB_DIR')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    if not web:
        return None, 'EBGEO_WEB_DIR ausente'
    if not node:
        return None, 'node fora do PATH (defina EBGEO_NODE)'
    d = tempfile.mkdtemp(prefix='ebgeo_node_')
    script = os.path.join(d, 'web.mjs')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    entrada, saida = os.path.join(d, 'in.json'), os.path.join(d, 'out.json')
    with open(entrada, 'w', encoding='utf-8') as fh:
        json.dump(casos, fh)
    r = subprocess.run([node, script, os.path.join(web, 'frontend'), entrada, saida], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-2000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh), None


TEXTOS = dict(tipo='LC', identificacao='AZUL', gdhIni='121400Z JUN', gdhFim='Mdt O', numeroConcentracao='AB0101')
COLUNA_DO_WEB = {'tipo': 'tipo', 'identificacao': 'identificacao', 'gdhIni': 'gdh_ini', 'gdhFim': 'gdh_fim',
                 'numeroConcentracao': 'numero_concentracao'}


def _props_web(codigo, **extra):
    p = dict(symbol_code=codigo, symbol_size=0.3, symbol_spacing=1.0, **TEXTOS)
    p.update(extra)
    return p


def _attrs_qgis(codigo, **extra):
    a = dict(symbol_code=codigo, symbol_size_km=0.3, symbol_spacing_km=1.0)
    a.update({COLUNA_DO_WEB[k]: v for k, v in TEXTOS.items()})
    a.update(extra)
    return a


# ---------------------------------------------------------------------------
# 1. Catálogo e esquema
# ---------------------------------------------------------------------------

class TestCatalogoEEsquema(unittest.TestCase):

    def test_catalogo_14_simbolos_em_tres_grupos(self):
        self.assertEqual(len(et.CATALOGO_LINHA), 14)
        for c in NOVOS:
            self.assertIn(c, et.CATALOGO_LINHA)
        grupos = [et.CATALOGO_LINHA[c]['grupo'] for c in et.CATALOGO_LINHA]
        self.assertEqual(sorted(set(grupos)), ['Fogos', 'Manobra', 'Obstáculos'])
        self.assertEqual(grupos.count('Obstáculos'), 11)
        for c, sim in et.CATALOGO_LINHA.items():
            self.assertEqual(sim['cor'], '#00B04E' if sim['grupo'] == 'Obstáculos' else '#000000', c)

    def test_catalogo_igual_ao_do_web(self):
        web, motivo = rodar_web([])
        if web is None:
            self.skipTest(motivo)
        # A ordem do combo do Web é a de symbolOptionGroups: grupo a grupo, e dentro do grupo a
        # de Object.values (no JS as chaves numéricas vêm antes das '290999-0x').
        self.assertEqual(list(et.GRUPOS_LINHA), web['grupos'])
        por_grupo = [s['id'] for g in web['grupos'] for s in web['catalogo'] if s['grupo'] == g]
        self.assertEqual(list(et.CATALOGO_LINHA), por_grupo)
        for s in web['catalogo']:
            d = et.CATALOGO_LINHA[s['id']]
            self.assertEqual((d['nome'], d['grupo'], d['cor']), (s['nome'], s['grupo'], s['cor']), s['id'])
            self.assertEqual([COLUNA_DO_WEB[t] for t in s['textos']] if s['textos'] else None, d.get('textos'))
            self.assertEqual(s['segunda'], d.get('segunda_cor'))

    def test_colunas_novas_com_as_chaves_do_web(self):
        m = schema.mapa_web('coordination_line')
        for web, col in (('tipo', 'tipo'), ('identificacao', 'identificacao'), ('gdhIni', 'gdh_ini'),
                         ('gdhFim', 'gdh_fim'), ('numeroConcentracao', 'numero_concentracao'),
                         ('enemy_color', 'enemy_color'), ('text_size', 'text_size'),
                         ('text_north_facing', 'text_north_facing')):
            self.assertEqual(m.get(web), col, web)
        pad = schema.padroes('coordination_line')
        self.assertEqual(pad['color'], '#00B04E')      # o símbolo padrão (290199) é obstáculo
        self.assertEqual(pad['symbol_code'], '290199')
        # o calco criado tem as colunas
        nomes = camada().fields().names()
        for col in ('tipo', 'identificacao', 'gdh_ini', 'gdh_fim', 'numero_concentracao', 'enemy_color',
                    'text_size', 'text_north_facing'):
            self.assertIn(col, nomes)


# ---------------------------------------------------------------------------
# 2. Desenho contra o Web
# ---------------------------------------------------------------------------

class TestContraWeb(unittest.TestCase):
    """A mesma linha de dobras fortes, nos dois sentidos, no código do Web e no estilo."""

    @classmethod
    def setUpClass(cls):
        cls.casos, cls.feicoes = [], []
        for codigo in NOVOS:
            for nome, coords in (('ida', DOBRAS), ('volta', DOBRAS[::-1])):
                cls.casos.append(dict(coords=[list(p) for p in coords], props=_props_web(codigo)))
                cls.feicoes.append((codigo, nome, nova_feicao(coords, **_attrs_qgis(codigo))))
        cls.web, cls.motivo = rodar_web(cls.casos)

    def setUp(self):
        if self.web is None:
            self.skipTest(self.motivo)

    def _par(self, codigo, nome):
        for caso, (c, n, vf), w in zip(self.casos, self.feicoes, self.web['casos']):
            if (c, n) == (codigo, nome):
                return vf, w
        raise KeyError(codigo)

    def test_geometria_dos_quatro(self):
        for codigo in NOVOS:
            for nome in ('ida', 'volta'):
                with self.subTest(codigo=codigo, sentido=nome):
                    (vl, f), w = self._par(codigo, nome)
                    g = geometrias(codigo, vl, f)
                    ww = partes_geojson(w['geom'])
                    self.assertEqual(len(g['linha']), len(ww), 'partes do traço principal')
                    d = desvio_partes(ww, g['linha'])
                    self.assertLess(d, 2.0)
                    traco = [e for e in w['extras'] if e['properties']['kind'] == 'stroke']
                    if traco:
                        wi = partes_geojson(traco[0]['geometry'])
                        self.assertEqual(len(g.get('inimigo', [])), len(wi), 'festões do lado inimigo')
                        di = desvio_partes(wi, g['inimigo'])
                        self.assertLess(di, 2.0)
                        medir('{} {}: {} festões amigos e {} inimigos nos dois, desvio máximo {:.2f} m / {:.2f} m'
                              .format(codigo, nome, len(ww), len(wi), d, di))
                    else:
                        self.assertFalse(g.get('inimigo'))
                        medir('{} {}: {} partes nos dois, desvio máximo {:.2f} m'.format(codigo, nome, len(ww), d))

    def test_textos(self):
        for codigo in ('140000', '240701'):
            for nome in ('ida', 'volta'):
                with self.subTest(codigo=codigo, sentido=nome):
                    (vl, f), w = self._par(codigo, nome)
                    wt = [e for e in w['extras'] if e['properties']['kind'] == 'text']
                    qt = textos_qgis(codigo, vl, f)
                    self.assertEqual(len(qt), len(wt))
                    chave = lambda t: (t['onde'], t['lado'])  # noqa: E731
                    wt = sorted(wt, key=lambda e: (e['properties']['textAt'], e['properties']['textSide']))
                    qt = sorted(qt, key=chave)
                    for a, b in zip(wt, qt):
                        pa = a['properties']
                        self.assertEqual((pa['textAt'], pa['textSide']), (b['onde'], b['lado']))
                        self.assertEqual(pa['text'], b['texto'])
                        pt = a['geometry']['coordinates']
                        self.assertLess(hav_m(pt, (b['ponto'].x(), b['ponto'].y())), 1.0)
                        dif = (pa['rotation'] - b['rotacao']) % 360
                        self.assertLess(min(dif, 360 - dif), 1.5, 'rotação')
                        self.assertEqual(QUAD_DA_ANCORA[pa['anchor']], b['quadrante'], pa['anchor'])
                        # vão: o Web dá [0, ±0,4] em no quadro do texto; o QGIS na tela
                        r = math.radians(b['rotacao'])
                        ox, oy = pa['offset']
                        esperado = (ox * math.cos(r) - oy * math.sin(r), ox * math.sin(r) + oy * math.cos(r))
                        self.assertAlmostEqual(b['vao'][0], esperado[0], delta=0.01)
                        self.assertAlmostEqual(b['vao'][1], esperado[1], delta=0.01)
                    medir('{} {}: {} textos com o ponto, a rotação, a âncora e o vão do Web'
                          .format(codigo, nome, len(qt)))

    def test_textos_voltados_ao_norte(self):
        casos, feicoes = [], []
        for codigo in ('140000', '240701'):
            for coords in (DOBRAS, DOBRAS[::-1]):
                casos.append(dict(coords=[list(p) for p in coords], props=_props_web(codigo, text_north_facing=True)))
                feicoes.append((codigo, nova_feicao(coords, **_attrs_qgis(codigo, text_north_facing=True))))
        web, _ = rodar_web(casos)
        for (codigo, (vl, f)), w in zip(feicoes, web['casos']):
            wt = sorted([e for e in w['extras'] if e['properties']['kind'] == 'text'],
                        key=lambda e: (e['properties']['textAt'], e['properties']['textSide']))
            qt = sorted(textos_qgis(codigo, vl, f), key=lambda t: (t['onde'], t['lado']))
            self.assertEqual(len(qt), len(wt))
            for a, b in zip(wt, qt):
                pa = a['properties']
                self.assertEqual(b['rotacao'], 0)
                self.assertEqual(QUAD_DA_ANCORA[pa['anchor']], b['quadrante'], (codigo, pa['textAt'], pa['anchor']))
                self.assertAlmostEqual(b['vao'][0], pa['offset'][0], delta=0.01)
                self.assertAlmostEqual(b['vao'][1], pa['offset'][1], delta=0.01)


# ---------------------------------------------------------------------------
# 3. Linha de Contato nas dobras
# ---------------------------------------------------------------------------

def _xy_local(lista, origem):
    tr = _tr_local(origem)
    return [[(lambda q: (q.x(), q.y()))(tr.transform(QgsPointXY(*p))) for p in parte] for parte in lista]


def _cruza(a, b):
    """Pontos onde as polilinhas a e b se cruzam (QGIS/GEOS), no plano local."""
    ga = QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in a])
    gb = QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in b])
    inter = ga.intersection(gb)
    if inter.isEmpty():
        return []
    if inter.type() != Qgis.GeometryType.Point:
        return [(float('inf'), float('inf'))]  # sobreposição em trecho
    return [(p.x(), p.y()) for p in (inter.asMultiPoint() if inter.isMultipart() else [inter.asPoint()])]


def defeitos_cordao(arcos, tol=0.05):
    """
    Defeitos de um cordão de festões, no plano local em metros: vão entre festões vizinhos
    (fim de um longe do início do seguinte) e sobreposição (festões que se cruzam fora da
    junta, vizinhos ou não). Lista vazia é cordão contínuo e limpo.
    """
    erros = []
    for i in range(len(arcos) - 1):
        a, b = arcos[i], arcos[i + 1]
        vao = math.dist(a[-1], b[0])
        if vao > tol:
            erros.append(('vão', i, round(vao, 3)))
    for i in range(len(arcos)):
        for j in range(i + 1, len(arcos)):
            for p in _cruza(arcos[i], arcos[j]):
                junta = arcos[i][-1] if j == i + 1 else None
                if junta is None or math.dist(p, junta) > tol:
                    erros.append(('sobreposição', i, j))
                    break
    return erros


class TestContatoNasDobras(unittest.TestCase):

    def _cordoes(self, coords, **attrs):
        vl, f = nova_feicao(coords, **_attrs_qgis('140200', **attrs))
        g = geometrias('140200', vl, f)
        return _xy_local(g['linha'], coords[0]), _xy_local(g.get('inimigo', []), coords[0])

    def test_dobras_de_30_a_120_sem_vao_nem_sobreposicao(self):
        for angulo in (30, 60, 90, 120):
            for virada in (1, -1):
                with self.subTest(angulo=angulo, virada=virada):
                    coords = zigue((-47.9, -15.8), [90, 90 + virada * angulo], 2000)
                    amigo, inimigo = self._cordoes(coords)
                    self.assertGreater(len(amigo), 5)
                    self.assertGreater(len(inimigo), 5)
                    self.assertEqual(defeitos_cordao(amigo), [])
                    self.assertEqual(defeitos_cordao(inimigo), [])

    def test_regua_reprova_cordao_degradado(self):
        """Pior caso: a saída real com um festão a menos (vão) e um festão deslocado sobre o vizinho."""
        coords = zigue((-47.9, -15.8), [90, 180], 2000)
        amigo, _ = self._cordoes(coords)
        sem_um = amigo[:3] + amigo[4:]
        self.assertTrue([e for e in defeitos_cordao(sem_um) if e[0] == 'vão'])
        dx = (amigo[5][-1][0] - amigo[5][0][0]) * 0.4
        dy = (amigo[5][-1][1] - amigo[5][0][1]) * 0.4
        deslocado = amigo[:5] + [[(x - dx, y - dy) for x, y in amigo[5]]] + amigo[6:]
        self.assertTrue([e for e in defeitos_cordao(deslocado) if e[0] == 'sobreposição'])

    def test_inimigo_a_esquerda_e_inverter_troca(self):
        for coords in (DOBRAS, DOBRAS[::-1]):
            amigo, inimigo = self._cordoes(coords)
            eixo = _xy_local([coords], coords[0])[0]
            ge = QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in eixo])

            def lado(p):
                # lado do ponto em relação ao trecho do eixo mais próximo: + esquerda, - direita
                _, _, depois, lado_ = ge.closestSegmentWithContext(QgsPointXY(*p))
                return -lado_  # o QGIS dá -1 à esquerda
            esq = [lado(p) for arc in inimigo for p in arc[1:-1]]
            dir_ = [lado(p) for arc in amigo for p in arc[1:-1]]
            self.assertEqual(set(esq), {1})
            self.assertEqual(set(dir_), {-1})


# ---------------------------------------------------------------------------
# 4. Estilo, render, persistência sem o plugin, desempenho
# ---------------------------------------------------------------------------

def renderizar(vl, caminho, crs='EPSG:3857', tamanho=(1100, 700), extensao=None, escala=None):
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
    ext = tr.transformBoundingBox(extensao or vl.extent())
    ext.scale(1.15)
    ms.setExtent(ext)
    # como o canvas e o layout: as expressões enxergam o mapa (@map_crs, @map_scale)
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    t = time.perf_counter()
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    dt = time.perf_counter() - t
    img = job.renderedImage()
    if caminho:
        img.save(caminho)
    return img, dt


def rotulos_do_render(vl, crs):
    """{fid: [(texto, rotação horária em graus, polígono do texto)]} do que o render desenhou."""
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(1100, 700))
    ms.setOutputDpi(96)
    tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
    ext = tr.transformBoundingBox(vl.extent())
    ext.scale(1.15)
    ms.setExtent(ext)
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    out = {}
    for lp in job.takeLabelingResults().allLabels():
        # rotação em graus no sentido horário (o QGIS a informa fora de [0, 360): 60 vem -300)
        out.setdefault(lp.featureId, []).append((lp.labelText, lp.rotation % 360, lp.labelGeometry))
    return out, ms


DESIGNACAO, GDH = 'LC  AZUL', '121400Z JUN -' + chr(10) + 'Mdt O'


def defeitos_rotulos(vl, crs):
    """
    Confere os rótulos desenhados: cada texto da 140000 corre com a linha (a rotação do Web),
    fica fora do ponto com vão, cresce para dentro a partir da ponta, e o de cima fica acima
    do de baixo na tela; o número da 240701 fica fora do meio. Devolve (defeitos, rótulos vistos).
    """
    rotulos, ms = rotulos_do_render(vl, crs)
    tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
    feicoes = {f.id(): f for f in vl.getFeatures()}
    um_mm = ms.scale() / 1000.0   # 1 mm de papel em unidades do mapa
    defeitos, vistos = [], 0
    for fid, lista in rotulos.items():
        f = feicoes[fid]
        codigo = f['symbol_code']
        g = QgsGeometry(f.geometry())
        g.transform(tr)
        pts = [QgsPointXY(p.x(), p.y()) for p in g.vertices()]
        por_ponta = {}
        for texto, rot, poli in lista:
            vistos += 1
            c = poli.centroid().asPoint()
            b = None
            if codigo == '140000':
                ponta = 0 if c.distance(pts[0]) < c.distance(pts[-1]) else 1
                ancora, vizinho = (pts[0], pts[1]) if ponta == 0 else (pts[-1], pts[-2])
                dx, dy = vizinho.x() - ancora.x(), vizinho.y() - ancora.y()
                if (c.x() - ancora.x()) * dx + (c.y() - ancora.y()) * dy <= 0:
                    defeitos.append(('não cresce para dentro', texto))
                por_ponta.setdefault(ponta, {})[texto] = c
                b = math.degrees(math.atan2(dx, dy)) % 360          # rumo da ponta para dentro
                if ponta == 1:
                    b = (b + 180) % 360                             # na final, o rumo de chegada
            else:
                ancora = g.interpolate(g.length() / 2).asPoint()
            if poli.contains(QgsGeometry.fromPointXY(ancora)):
                defeitos.append(('texto sobre o ponto', texto))
            elif poli.distance(QgsGeometry.fromPointXY(ancora)) < 0.5 * um_mm:
                defeitos.append(('sem vão', texto))
            if b is not None:
                esperado = b + 90 if (b == 0 or b >= 180) else b - 90
                dif = (rot - esperado) % 360
                if min(dif, 360 - dif) > 1.5:
                    defeitos.append(('rotação', texto, round(rot, 1), round(esperado % 360, 1)))
        for ponta, t in por_ponta.items():
            if set(t) != {DESIGNACAO, GDH}:
                defeitos.append(('textos da ponta', ponta, sorted(t)))
            elif t[DESIGNACAO].y() <= t[GDH].y():
                defeitos.append(('designação abaixo dos GDH', ponta))
    return defeitos, vistos


def contar_cor(img, alvo, tol=60):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = QColor(img.pixel(x, y))
            if abs(c.red() - alvo[0]) + abs(c.green() - alvo[1]) + abs(c.blue() - alvo[2]) < tol:
                n += 1
    return n


def popular(caminho, feicoes):
    if os.path.exists(caminho):
        os.remove(caminho)
    gpkg.criar_calco(caminho, ['coordination_line'])
    vl = camada(caminho)
    fs = []
    for coords, attrs in feicoes:
        f = QgsFeature(vl.fields())
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in coords]))
        v = dict(schema.padroes('coordination_line'))
        v.update(attrs)
        for k, x in v.items():
            if vl.fields().indexOf(k) >= 0:
                f[k] = x
        fs.append(f)
    assert vl.dataProvider().addFeatures(fs)[0]
    return camada(caminho)


def quatro_linhas(deslocar=0.0, volta=False):
    """As quatro linhas novas lado a lado, cada uma com dobras de 30 a 120 graus."""
    out = []
    for i, codigo in enumerate(NOVOS):
        coords = [(x, y - 0.06 * i - deslocar) for x, y in zigue((-47.95, -15.80), [80, 110, 50, 140], 2500)]
        if volta:
            coords = coords[::-1]
        cor = '#00B04E' if codigo == '290500' else '#000000'
        out.append((coords, _attrs_qgis(codigo, symbol_size_km=0.25, color=cor, line_width=3, text_size=16)))
    return out


SCRIPT_SEM_PLUGIN = r'''
import sys, json
from qgis.core import QgsApplication, QgsVectorLayer, QgsMapSettings, QgsMapRendererParallelJob, \
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsExpressionContext, QgsExpressionContextUtils
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor
app = QgsApplication([], True); app.initQgis()
caminho, png = sys.argv[1], sys.argv[2]
vl = QgsVectorLayer(caminho + '|layername=coordination_line', 'lc', 'ogr')
ms = QgsMapSettings(); ms.setLayers([vl]); ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
ms.setOutputSize(QSize(1100, 700)); ms.setOutputDpi(96); ms.setBackgroundColor(QColor('white'))
tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
ext = tr.transformBoundingBox(vl.extent()); ext.scale(1.15); ms.setExtent(ext)
ctx = QgsExpressionContext(); ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms)); ms.setExpressionContext(ctx)
job = QgsMapRendererParallelJob(ms); job.start(); job.waitForFinished(); job.renderedImage().save(png)
lab = vl.labeling()
print(json.dumps({'renderer': vl.renderer().type(), 'regras': len(vl.renderer().rootRule().children()),
                  'rotulos': vl.labelsEnabled(), 'regras_rotulo': len(lab.rootRule().children()) if lab else 0,
                  'modulos_ebgeo': sorted(m for m in sys.modules if 'Calco' in m or 'EBGeo' in m)}))
'''


class TestRenderEPersistencia(unittest.TestCase):

    def test_imagens_3857_e_31983_nos_dois_sentidos(self):
        for volta in (False, True):
            caminho = os.path.join(TMP, 'img_{}.gpkg'.format('volta' if volta else 'ida'))
            vl = popular(caminho, quatro_linhas(volta=volta))
            pura, _ = renderizar(vl, None)
            et.aplicar_estilo(vl, 'coordination_line')
            for crs in ('EPSG:3857', 'EPSG:31983'):
                nome = 'quatro_{}_{}.png'.format('volta' if volta else 'ida', crs.split(':')[1])
                img, _ = renderizar(vl, os.path.join(SAIDA, nome), crs=crs)
                self.assertGreater(contar_cor(img, (255, 0, 0)), 200, 'festões inimigos em vermelho')
                self.assertGreater(contar_cor(img, (0, 176, 78)), 200, 'arame de tração em verde')
                self.assertGreater(contar_cor(img, (0, 0, 0)), contar_cor(pura, (0, 0, 0)))
        medir('PNGs em ' + SAIDA)

    def test_rotulos_desenhados(self):
        """
        Os rótulos que o render DESENHOU (resultados de rotulagem do job), não as expressões,
        nos dois sentidos e nos dois SRC. Pior caso: o mesmo estilo sem a rotação, o quadrante
        e o deslocamento por expressão (texto centrado na ponta) tem de reprovar.
        """
        for volta in (False, True):
            caminho = os.path.join(TMP, 'rot_{}.gpkg'.format('volta' if volta else 'ida'))
            vl = popular(caminho, quatro_linhas(volta=volta))
            et.aplicar_estilo(vl, 'coordination_line')
            for crs in ('EPSG:3857', 'EPSG:31983'):
                with self.subTest(volta=volta, crs=crs):
                    defeitos, vistos = defeitos_rotulos(vl, crs)
                    self.assertEqual(defeitos, [])
                    self.assertEqual(vistos, 5)
        # pior caso, degradando a rotulagem real
        lab = vl.labeling().clone()
        P = QgsPalLayerSettings.Property
        for regra in lab.rootRule().children():
            s = QgsPalLayerSettings(regra.settings())
            dd = s.dataDefinedProperties()
            for prop in (P.LabelRotation, P.OffsetQuad, P.OffsetXY):
                dd.setProperty(prop, QgsProperty())
            s.setDataDefinedProperties(dd)
            regra.setSettings(s)
        vl.setLabeling(lab)
        defeitos, vistos = defeitos_rotulos(vl, 'EPSG:3857')
        self.assertEqual(vistos, 5)
        self.assertGreaterEqual(len(defeitos), 5, defeitos)
        medir('rótulos desenhados: 5 por render, nos dois sentidos, em EPSG:3857 e 31983, sem defeito; '
              'sem a ancoragem por expressão, {} defeitos'.format(len(defeitos)))

    def test_abre_sem_o_plugin(self):
        caminho = os.path.join(TMP, 'sem_plugin.gpkg')
        vl = popular(caminho, quatro_linhas())
        et.aplicar_estilo(vl, 'coordination_line')
        ok, msg = et.salvar_estilo_padrao(vl)
        self.assertTrue(ok, msg)
        img_estilo, _ = renderizar(vl, os.path.join(SAIDA, 'com_plugin.png'))
        png = os.path.join(SAIDA, 'sem_plugin.png')
        exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
        if not os.path.exists(exe):
            exe = sys.executable
        script = os.path.join(TMP, 'sem_plugin.py')
        with open(script, 'w', encoding='utf-8') as fh:
            fh.write(SCRIPT_SEM_PLUGIN)
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        r = subprocess.run([exe, script, caminho, png] if exe.endswith('.bat') else [exe, script, caminho, png],
                           capture_output=True, text=True, env=env, cwd=TMP, shell=exe.endswith('.bat'))
        linhas = [ln for ln in r.stdout.splitlines() if ln.startswith('{')]
        self.assertTrue(linhas, r.stdout[-2000:] + r.stderr[-2000:])
        info = json.loads(linhas[-1])
        self.assertEqual(info['modulos_ebgeo'], [])
        self.assertEqual(info['renderer'], 'RuleRenderer')
        self.assertEqual(info['regras'], len(vl.renderer().rootRule().children()))
        self.assertTrue(info['rotulos'])
        from qgis.PyQt.QtGui import QImage
        img = QImage(png)
        self.assertEqual(img.size(), img_estilo.size())
        self.assertGreater(contar_cor(img, (255, 0, 0)), 200)
        diferentes = sum(1 for y in range(0, img.height(), 3) for x in range(0, img.width(), 3)
                         if img.pixel(x, y) != img_estilo.pixel(x, y))
        self.assertLess(diferentes, 50, 'imagem sem o plugin difere da com o plugin')
        medir('sem o plugin: {} (regras {}, rótulos {}, {} pixels diferentes em 1/9 da imagem)'.format(
            info['renderer'], info['regras'], info['regras_rotulo'], diferentes))

    def test_desempenho_50_linhas(self):
        import random
        random.seed(7)
        feicoes = []
        codigos = list(et.CATALOGO_LINHA)
        for i in range(50):
            x0, y0 = -48.5 + random.random(), -16.3 + random.random()
            coords = [(x0, y0), (x0 + 0.09, y0 + 0.03), (x0 + 0.18, y0), (x0 + 0.22, y0 + 0.05)]
            feicoes.append((coords, _attrs_qgis(codigos[i % len(codigos)], symbol_size_km=0.5, symbol_spacing_km=1.5)))
        vl = popular(os.path.join(TMP, 'desempenho.gpkg'), feicoes)
        et.aplicar_estilo(vl, 'coordination_line')
        tempos = [renderizar(vl, None, tamanho=(1200, 900))[1] for _ in range(3)]
        so = popular(os.path.join(TMP, 'desempenho_contato.gpkg'),
                     [(c, dict(a, symbol_code='140200')) for c, a in feicoes])
        et.aplicar_estilo(so, 'coordination_line')
        t2 = [renderizar(so, None, tamanho=(1200, 900))[1] for _ in range(3)]
        medir('desempenho: 50 linhas de ~25 km, 1200x900: 14 símbolos misturados {:.2f}/{:.2f}/{:.2f} s; '
              'só 140200 {:.2f}/{:.2f}/{:.2f} s'.format(*(tempos + t2)))
        self.assertLess(min(tempos), 20)


# ---------------------------------------------------------------------------
# 5. Painel
# ---------------------------------------------------------------------------

class TestPainel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(TMP, 'painel.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())

    def _nova(self, **attrs):
        from Calco.ferramentas import gravar_feicao
        a = dict(schema.padroes('coordination_line'))
        a['ebgeo_id'] = str(uuid.uuid4())
        a.update(attrs)
        lyr = self.calco.camada('coordination_line')
        eid = gravar_feicao(lyr, 'coordination_line',
                            QgsGeometry.fromPolylineXY([QgsPointXY(-51.2, -30.0), QgsPointXY(-51.1, -30.0)]), a)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        return lyr, eid

    def _reler(self, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_line'), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _visiveis(self):
        return {c for c, w in self.painel.widgets.items() if not w.isHidden()}

    def _trocar(self, codigo):
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData(codigo))
        self.painel._gravar_pendentes()
        QGS.processEvents()  # o painel se remonta no ciclo seguinte
        self.assertTrue(self.painel.salvar())  # o painel edita no buffer; o disco muda no Salvar
        QGS.processEvents()

    def test_combo_agrupado_com_14(self):
        self._nova()
        cb = self.painel.widgets['symbol_code']
        dados = [cb.itemData(i) for i in range(cb.count())]
        codigos = [d for d in dados if d]
        self.assertEqual(codigos, list(et.CATALOGO_LINHA))
        cabecalhos = [cb.itemText(i) for i in range(cb.count()) if not cb.itemData(i)]
        self.assertEqual(cabecalhos, ['Obstáculos', 'Manobra', 'Fogos'])
        for i in range(cb.count()):
            if not cb.itemData(i):
                self.assertFalse(cb.model().item(i).isEnabled())
        self.assertIn('Linha de Contato (140200)', [cb.itemText(i) for i in range(cb.count())])
        self.assertIn('Sapa (290999/01)', [cb.itemText(i) for i in range(cb.count())])

    def test_campos_conforme_o_simbolo(self):
        lyr, eid = self._nova()
        textos = {'tipo', 'identificacao', 'gdh_ini', 'gdh_fim', 'text_size', 'text_north_facing'}
        v = self._visiveis()
        self.assertFalse(v & (textos | {'numero_concentracao', 'enemy_color'}))
        self.assertIn('symbol_size_km', v)
        self._trocar('140000')
        v = self._visiveis()
        self.assertTrue(textos <= v)
        self.assertNotIn('numero_concentracao', v)
        self.assertNotIn('enemy_color', v)
        self.assertNotIn('symbol_size_km', v)
        self.assertNotIn('symbol_spacing_km', v)
        self._trocar('140200')
        v = self._visiveis()
        self.assertIn('enemy_color', v)
        self.assertIn('symbol_size_km', v)
        self.assertFalse(v & textos)
        self._trocar('240701')
        v = self._visiveis()
        self.assertIn('numero_concentracao', v)
        self.assertIn('symbol_size_km', v)
        self.assertNotIn('tipo', v)
        ed = self.painel.widgets['numero_concentracao']
        ed.setText('AB0101')
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()
        self.assertTrue(self.painel.salvar())
        self.assertEqual(self._reler(eid)['numero_concentracao'], 'AB0101')

    def test_cor_so_troca_se_estava_na_padrao(self):
        lyr, eid = self._nova()
        self.assertEqual(self._reler(eid)['color'].upper(), '#00B04E')   # obstáculo nasce verde
        self._trocar('140000')
        self.assertEqual(self._reler(eid)['color'].upper(), '#000000')   # estava na padrão: troca
        self._trocar('290100')
        self.assertEqual(self._reler(eid)['color'].upper(), '#00B04E')
        lyr, eid2 = self._nova(color='#123456')
        self._trocar('140200')
        self.assertEqual(self._reler(eid2)['color'], '#123456')          # cor escolhida: fica
        lyr, eid3 = self._nova(color='#000000', symbol_code='290302')    # linha antiga preta
        self._trocar('290100')
        self.assertEqual(self._reler(eid3)['color'], '#000000')          # obstáculo preto antigo: fica


# ---------------------------------------------------------------------------
# 6. Importador
# ---------------------------------------------------------------------------

class TestImportador(unittest.TestCase):

    def test_propriedades_novas_viram_colunas(self):
        sys.path.insert(0, AQUI)
        import test_importador as ti
        from Calco.importador import escritor
        caminho02 = ti.fixture('02-minimo.ebgeo')
        if not os.path.exists(caminho02):
            self.skipTest('fixture 02 ausente')
        _, d = ti.bruto_do_arquivo(caminho02)
        d = json.loads(json.dumps(d))
        feats = d['maps'][d['mapOrder'][0] if d.get('mapOrder') else 'Principal']['features']
        linhas = []
        for i, codigo in enumerate(NOVOS):
            p = dict(_props_web(codigo), id='lc7-{}'.format(i), source='coordination_line', type='coordination_line',
                     color='#000000', lineWidth=4, opacity=1, createdAtZoom=12, zoomCorrectionEnabled=True,
                     baseCoordinates=[list(c) for c in DOBRAS], text_size=18, text_north_facing=(i % 2 == 1),
                     nome='linha {}'.format(codigo), descricao='', visivel=True, bloqueado=False)
            if codigo == '140200':
                p['enemy_color'] = '#aa0000'
            linhas.append({'type': 'Feature', 'properties': p,
                           'geometry': {'type': 'LineString', 'coordinates': p['baseCoordinates']}})
        feats['coordination_lines'] = linhas
        arq = os.path.join(TMP, 'lc7.ebgeo')
        with open(arq, 'wb') as fh:
            fh.write(ti.montar_ebgeo(d))
        destino = os.path.join(TMP, 'lc7_importado.gpkg')
        escritor.importar(arq, destino)
        for ft in linhas:
            p = ft['properties']
            linha, _ = ti.linha_gpkg(destino, 'coordination_line', p['id'])
            self.assertIsNotNone(linha)
            self.assertEqual(ti.divergencias('coordination_line', p, linha), [], p['symbol_code'])
            for web, col in COLUNA_DO_WEB.items():
                self.assertEqual(linha[col], p[web])
            self.assertEqual(linha['enemy_color'], p.get('enemy_color', '#ff0000'))
            self.assertEqual(linha['text_size'], 18)
            self.assertEqual(bool(linha['text_north_facing']), p['text_north_facing'])


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)


if __name__ == '__main__':
    r = unittest.main(verbosity=2, exit=False).result
    # Sem QGS.exitQgis(): medido em 2026-10-04 no QGIS 4.0.0, ele abortava o processo depois do OK
    # ("Fatal Python error: Aborted" em qgis.testing.exitQgis), e o código de saída virava 127 (ou 3
    # com -X faulthandler) com todos os testes passando; limpar o projeto antes não resolvia.
    sys.exit(0 if r.wasSuccessful() else 1)
