# -*- coding: utf-8 -*-
"""
K4: círculo, elipse, retângulo e setor editados vértice a vértice no QGIS (exportador/formas.py).

    python-qgis.bat EBGeo/Calco/testes/test_formas_editadas.py

Com EBGEO_WEB_DIR (ou EBGEO_WEB) e node (EBGEO_NODE ou o PATH), os geradores das quatro formas do
próprio Web rodam em node e são a referência; sem eles, essa parte é pulada.

O que cada classe prova:
    TestGeradores       o porte dos geradores do Web (formas.gerar) dá, vértice a vértice, o anel que o Web
                        gera para os mesmos parâmetros (os das 34 formas da fixture 06 e casos de borda);
    TestAjuste          a forma escalada, transladada ou girada (no plano) volta com os parâmetros dela, e
                        a forma com um vértice puxado de 0,3 % do tamanho é reprovada; as medidas que
                        fixam a tolerância (formas.TOL_PISO_M, formas.TOL_FRACAO) são impressas;
    TestExportador      a fixture 06 importada, com as formas escaladas pelo QGIS (QgsGeometry, na camada em
                        EPSG:4326, como a ferramenta Escalar), sai com os parâmetros novos e a geometria que
                        o Web gera para eles, sem aviso; a forma girada em graus (a ferramenta Girar, sem o
                        plugin) sai como a forma girada no terreno, com o giro dado e um aviso; a forma com
                        um vértice puxado sai como desenhada, com o aviso e o desvio; o código de antes (só
                        a translação) reprova, e o exportador sem o reconhecimento do giro também;
    TestGiroEmGraus     a forma girada em graus deixa de ser a forma (fora do equador), e giro_em_graus a
                        devolve girada no terreno: o ajuste a reconhece com o giro dado; a girada e puxada
                        não é reconhecida;
    TestGuardiao        com o plugin, girar a forma na camada (o comando de edição do Girar) a troca, no
                        comando do guardião, pela forma girada no terreno, que o ajuste reconhece no plano;
                        o Ctrl+Z volta ao desenho do Girar; sem o guardião, fica achatada.
"""
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, os.path.join(RAIZ_REPO, 'EBGeo'))
FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')

from qgis.core import QgsApplication, QgsGeometry, QgsPointXY, QgsVectorLayer  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from qgis.PyQt.QtGui import QTransform  # noqa: E402

from Calco import schema  # noqa: E402
from Calco.importador import escritor, leitor  # noqa: E402
from Calco.exportador import desenho, formas, montador  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_formas_')
BALDES = {'circles': 'circle', 'ellipses': 'ellipse', 'rectangles': 'rectangle', 'setores': 'sector'}


def formas_06():
    """[(tipo, props, anel)] das formas paramétricas da fixture 06."""
    out = []
    for m in leitor.abrir(FIXTURE_06).data['maps'].values():
        for balde, tipo in BALDES.items():
            for f in (m.get('features') or {}).get(balde, []):
                p = f['properties']
                if f['geometry']['type'] == 'Polygon' and formas._parametros_validos(tipo, p):
                    out.append((tipo, p, f['geometry']['coordinates'][0]))
    return out


# ---------------------------------------------------------------- o Web em node

NODE_HARNESS = r'''
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
const [frontend, entrada, saida] = process.argv.slice(2);
const js = join(frontend, 'src', 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-formas-'));
const stub = join(dir, 'tools.mjs');
writeFileSync(stub, `export { default as BaseGeometry } from ${JSON.stringify(pathToFileURL(join(js, 'tool_manager', 'base_geometry.js')).href)};\n`);
const hooks = join(dir, 'hooks.mjs');
writeFileSync(hooks, `
const STUB = ${JSON.stringify(pathToFileURL(stub).href)};
export async function resolve(spec, ctx, next) {
  if (spec === '@tools' || /(^|\\/)tool_manager\\/?$/.test(spec)) return { url: STUB, shortCircuit: true };
  return next(spec, ctx);
}
`);
register(pathToFileURL(hooks).href);
const req = createRequire(join(frontend, 'package.json'));
const turfMod = await import(pathToFileURL(req.resolve('@turf/turf')).href);
globalThis.turf = { ...(turfMod.default ?? turfMod) };
const imp = (p) => import(pathToFileURL(join(js, ...p.split('/'))).href).then((m) => m.default);
const CI = new (await imp('draw_tools/circle_tool/add_circle_geometry.js'))();
const EL = new (await imp('draw_tools/ellipse_tool/add_ellipse_geometry.js'))();
const RE = new (await imp('draw_tools/rectangle_tool/add_rectangle_geometry.js'))();
const SE = new (await imp('draw_tools/sector_tool/add_sector_geometry.js'))();
const casos = JSON.parse(readFileSync(entrada, 'utf8'));
const out = casos.map(([tipo, p]) => {
  if (tipo === 'circle') return CI.generate(p.center, p.radius).coordinates[0];
  if (tipo === 'ellipse') return EL.generate(p.center, p.majorRadius, p.minorRadius, p.bearing || 0).coordinates[0];
  if (tipo === 'sector') return SE.generate(p.center, p.radius, p.bearing || 0, p.aperture).coordinates[0];
  return RE.buildFromModel(p.center, p.width, p.height, p.borderRadius || 0, p.bearing || 0).geometry.coordinates[0];
});
writeFileSync(saida, JSON.stringify(out));
'''


def rodar_web(casos):
    """Os anéis que o Web gera para [(tipo, props)], ou None sem o Web ou o node."""
    web = os.environ.get('EBGEO_WEB_DIR') or os.environ.get('EBGEO_WEB')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    if not web or not node:
        return None
    d = tempfile.mkdtemp(prefix='ebgeo_formas_node_')
    script, entrada, saida = (os.path.join(d, n) for n in ('formas.mjs', 'in.json', 'out.json'))
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    with open(entrada, 'w', encoding='utf-8') as fh:
        json.dump([[t, {k: v for k, v in p.items() if k in ('center', 'radius', 'majorRadius', 'minorRadius',
                                                                'bearing', 'aperture', 'width', 'height',
                                                                'borderRadius')}] for t, p in casos], fh)
    r = subprocess.run([node, script, os.path.join(web, 'frontend'), entrada, saida],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-3000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh)


def desvio_vertices_m(a, b):
    """Maior distância (m) entre vértices correspondentes, ou infinito se a contagem difere."""
    if len(a) != len(b):
        return float('inf')
    pl = formas._Plano(*a[0])
    import numpy as np
    return float(np.sqrt(((pl.xy(a) - pl.xy(b)) ** 2).sum(1)).max())


BORDAS = [
    ('ellipse', {'center': [-47.9, -15.8], 'majorRadius': 1.2, 'minorRadius': 1.2, 'bearing': 10}),   # m = 0
    ('ellipse', {'center': [10.0, 60.0], 'majorRadius': 5.0, 'minorRadius': 0.4, 'bearing': -30}),
    ('rectangle', {'center': [-47.9, -15.8], 'width': 3000, 'height': 1200, 'borderRadius': 6, 'bearing': 35}),
    ('rectangle', {'center': [179.95, 10.0], 'width': 8000, 'height': 2000, 'borderRadius': 0, 'bearing': 200}),
    ('sector', {'center': [-47.9, -15.8], 'radius': 900, 'bearing': 350, 'aperture': 5}),
    ('sector', {'center': [-47.9, -15.8], 'radius': 900, 'bearing': 10, 'aperture': 197}),
    ('circle', {'center': [179.99, -60.0], 'radius': 5000}),
]


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestGeradores(unittest.TestCase):
    def test_porte_igual_ao_web(self):
        casos = [(t, p) for t, p, _a in formas_06()] + BORDAS
        web = rodar_web(casos)
        if web is None:
            self.skipTest('EBGEO_WEB_DIR/EBGEO_WEB ou node ausente')
        pior = 0.0
        for (t, p), w in zip(casos, web):
            d = desvio_vertices_m(formas.gerar(t, p), w)
            pior = max(pior, d)
            self.assertLess(d, 1e-4, (t, p))
        print('\ngeradores: {} formas, maior desvio vértice a vértice contra o Web {:.2e} m'.format(len(casos), pior))
        # pior caso: o círculo no R do turf (a esfera errada) já reprova
        t, p = casos[0]
        errado = [list(formas._destino(p['center'][0], p['center'][1], p['radius'], 90 - i * 360 / 64, formas.R_TURF))
                  for i in range(65)] if t == 'circle' else None
        if errado:
            self.assertGreater(desvio_vertices_m(errado, web[0]), 1e-4)


def _similar(anel, s=1.0, giro=0.0, dx=0.0, dy=0.0):
    """Escala, gira (graus, anti-horário) e translada o anel no plano local (metros) da forma."""
    import numpy as np
    pl = formas._Plano(*anel[0])
    xy = pl.xy(anel)
    c = xy[:-1].mean(0)
    a = math.radians(giro)
    rot = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    novo = (xy - c).dot(rot.T) * s + c + [dx, dy]
    return [pl.lonlat(x, y) for x, y in novo]


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestAjuste(unittest.TestCase):
    """formas.ajustar sobre as formas da fixture 06."""

    @classmethod
    def setUpClass(cls):
        cls.formas = formas_06()

    def test_semelhanca_volta_com_os_parametros(self):
        for t, p, anel in self.formas:
            with self.subTest(tipo=t, nome=p.get('nome')):
                novo = _similar(anel, 1.4, 25 if t != 'circle' else 0, 300, -120)
                q, _a, desvio, tol = formas.ajustar(t, p, anel, [[round(x, 6), round(y, 6)] for x, y in novo])
                self.assertLessEqual(desvio, tol)
                if t in ('circle', 'sector'):
                    self.assertAlmostEqual(q['radius'], 1.4 * p['radius'], delta=1e-3 * p['radius'])
                if t == 'ellipse':
                    self.assertAlmostEqual(q['majorRadius'], 1.4 * p['majorRadius'], delta=1e-3 * p['majorRadius'])
                if t == 'rectangle':
                    self.assertAlmostEqual(q['width'] * q['height'], 1.96 * p['width'] * p['height'],
                                           delta=3e-3 * p['width'] * p['height'])
                if t in ('ellipse', 'rectangle', 'sector'):
                    d = (q['bearing'] - (p.get('bearing') or 0) + 25 + 180) % 360 - 180
                    if t != 'sector':
                        d = (d + 90) % 180 - 90   # elipse e retângulo valem o mesmo a 180 graus
                    self.assertAlmostEqual(d, 0, delta=0.05)
                if t == 'sector':
                    self.assertAlmostEqual(q['aperture'], p['aperture'], delta=0.01)

    def test_vertice_puxado_reprova(self):
        reprovadas = 0
        for t, p, anel in self.formas:
            r = formas.ajustar(t, p, anel, puxar_vertice(t, p, anel, 0.003))
            reprovadas += r is None or r[2] > r[3]
        self.assertEqual(reprovadas, len(self.formas))

    def test_medidas_da_tolerancia(self):
        """As medidas que fixam TOL_PISO_M e TOL_FRACAO: o igual e o escalado passam, o puxado não."""
        import numpy as np

        def pior(fn):
            vals = []
            for t, p, anel in self.formas:
                r = formas.ajustar(t, p, anel, fn(t, p, anel))
                vals.append(np.inf if r is None else r[2] / formas.tamanho(t, r[0]))
            return min(vals), max(vals)

        def em_graus(anel, s):
            xs = [v[0] for v in anel[:-1]]
            ys = [v[1] for v in anel[:-1]]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            return [[round(cx + s * (x - cx), 6), round(cy + s * (y - cy), 6)] for x, y in anel]

        def puxa(t, p, anel):
            return puxar_vertice(t, p, anel, 0.003)
        igual = pior(lambda t, p, a: a)
        escala = pior(lambda t, p, a: em_graus(a, 1.5))
        puxado = pior(puxa)
        print('\ntolerância: igual até {:.3f} %, escalado em graus até {:.3f} %, um vértice puxado de 0,3 % a partir '
              'de {:.3f} % do tamanho; TOL_FRACAO {:.3f} %'.format(100 * igual[1], 100 * escala[1], 100 * puxado[0],
                                                                    100 * formas.TOL_FRACAO))
        self.assertLess(max(igual[1], escala[1]), formas.TOL_FRACAO)
        self.assertGreater(puxado[0], formas.TOL_FRACAO)

    def test_giro_no_equador(self):
        p = {'center': [-47.9, 0.0], 'majorRadius': 2.0, 'minorRadius': 0.8, 'bearing': 20}
        anel = formas.gerar('ellipse', p)
        xs = [v[0] for v in anel[:-1]]
        ys = [v[1] for v in anel[:-1]]
        g = QgsGeometry.fromPolygonXY([[QgsPointXY(*v) for v in anel]])
        g.rotate(30, QgsPointXY((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))   # horário, como o QGIS
        q, _a, desvio, tol = formas.ajustar('ellipse', p, anel, [[v.x(), v.y()] for v in g.asPolygon()[0]])
        self.assertLessEqual(desvio, tol)
        self.assertAlmostEqual(q['bearing'], 50, delta=0.05)


def girar_em_graus(anel, graus=30):
    """O anel girado como a ferramenta Girar do QGIS na camada em EPSG:4326 (horário, no centro do envolvente)."""
    g = QgsGeometry.fromPolygonXY([[QgsPointXY(*v) for v in anel]])
    g.rotate(graus, g.boundingBox().center())
    return [[v.x(), v.y()] for v in g.asPolygon()[0]]


def _giro_esperado(t, p0, q, graus):
    """O giro do rumo, em graus, além do esperado, reduzido à simetria da forma (meia volta na elipse e no retângulo)."""
    d = (q['bearing'] - (p0.get('bearing') or 0) - graus + 180) % 360 - 180
    return (d + 90) % 180 - 90 if t != 'sector' else d


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestGiroEmGraus(unittest.TestCase):
    """formas.giro_em_graus sobre as formas da fixture 06 (de 15 a 24 graus de latitude sul)."""

    @classmethod
    def setUpClass(cls):
        cls.formas = formas_06()

    def test_girada_em_graus_volta_girada_no_terreno(self):
        achatadas, pior = 0, 0.0
        for t, p, anel in self.formas:
            with self.subTest(tipo=t, nome=p.get('nome')):
                girado = girar_em_graus(anel, 30)
                r = formas.ajustar(t, p, anel, girado)
                achatadas += t != 'circle' and (r is None or r[2] > r[3])
                novo, giro = formas.giro_em_graus(anel, girado, t)
                self.assertAlmostEqual(giro, -30, delta=1e-6)   # anti-horário: o Girar do QGIS é horário
                q, _a, desvio, tol = formas.ajustar(t, p, anel, novo)
                self.assertLessEqual(desvio, tol)
                pior = max(pior, desvio / formas.tamanho(t, q))
                if t != 'circle':
                    self.assertAlmostEqual(_giro_esperado(t, p, q, 30), 0, delta=0.05)
                for k in ('radius', 'majorRadius', 'minorRadius', 'width', 'height', 'aperture'):
                    if k in formas._LIVRES[t]:
                        self.assertAlmostEqual(q[k] / p[k], 1, delta=1e-3)
        n = sum(1 for t, _p, _a in self.formas if t != 'circle')
        print('\ngiro em graus: {} de {} formas que não são círculo deixam de ser a forma; giradas no terreno, '
              'voltam a até {:.3f} % do tamanho'.format(achatadas, n, 100 * pior))
        # a esta latitude, as que não são círculo ficam achatadas, o que o giro em graus conserta; só o
        # "Retângulo girado 30°", girado mais 30 graus, fica a 0,17 m de um retângulo (tolerância de 1,8 m)
        self.assertEqual(achatadas, n - 1)

    def test_girada_e_puxada_nao_e_reconhecida(self):
        for t, p, anel in self.formas:
            with self.subTest(tipo=t, nome=p.get('nome')):
                girado = girar_em_graus(anel, 30)
                self.assertIsNone(formas.giro_em_graus(anel, puxar_vertice(t, p, girado, 0.003), t))
                self.assertIsNone(formas.giro_em_graus(anel, anel, t))   # sem giro, nada a fazer


def puxar_vertice(t, p, anel, frac, i=2):
    """O vértice i puxado para fora do centro do envolvente, de frac do tamanho da forma."""
    xs = [v[0] for v in anel[:-1]]
    ys = [v[1] for v in anel[:-1]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    a = [list(v) for v in anel]
    kx = 111320 * math.cos(math.radians(cy))
    dx, dy = (a[i][0] - cx) * kx, (a[i][1] - cy) * 111320
    n = math.hypot(dx, dy)
    d = formas.tamanho(t, p) * frac
    a[i] = [a[i][0] + d * dx / n / kx, a[i][1] + d * dy / n / 111320]
    if i == 0:
        a[-1] = a[0]
    return a


def _transformar(g, s):
    """Escala a geometria em graus em torno do centro do retângulo envolvente (a ferramenta Escalar do QGIS)."""
    c = g.boundingBox().center()
    t = QTransform()
    t.translate(c.x(), c.y())
    t.scale(s, s)
    t.translate(-c.x(), -c.y())
    g = QgsGeometry(g)
    g.transform(t)
    return g


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestExportador(unittest.TestCase):
    """A fixture 06 importada, as formas editadas pela camada (o caminho do QGIS) e exportada."""

    ESCALA = 1.5
    GIRO = 30

    @classmethod
    def setUpClass(cls):
        cls.cam = os.path.join(TMP, 'f06.gpkg')
        escritor.importar(FIXTURE_06, cls.cam)
        cls.escaladas, cls.puxadas, cls.giradas = {}, {}, {}
        for tipo in BALDES.values():
            l = QgsVectorLayer('{}|layername={}'.format(cls.cam, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
            fs = list(l.getFeatures())
            l.startEditing()
            for i, f in enumerate(fs[:4]):
                g = QgsGeometry(f.geometry())
                if i < 2:
                    l.changeGeometry(f.id(), _transformar(g, cls.ESCALA))
                    cls.escaladas[f['ebgeo_id']] = tipo
                elif i == 3:
                    g.rotate(cls.GIRO, g.boundingBox().center())   # a ferramenta Girar, sem o plugin
                    l.changeGeometry(f.id(), g)
                    cls.giradas[f['ebgeo_id']] = tipo
                else:
                    v = g.vertexAt(2)
                    tam = 0.01 * 111320 * max(g.boundingBox().width(), g.boundingBox().height()) / 2
                    g.moveVertex(v.x() + tam / 111320, v.y(), 2)
                    l.changeGeometry(f.id(), g)
                    cls.puxadas[f['ebgeo_id']] = tipo
            assert l.commitChanges(), l.commitErrors()
        cls.exp = montador.montar(cls.cam, montador.ESCOPO_TUDO, None, desenho.GeradorDesenho())
        cls.orig = {}
        for m in leitor.abrir(FIXTURE_06).data['maps'].values():
            for balde in BALDES:
                for f in (m.get('features') or {}).get(balde, []):
                    cls.orig[f['properties']['id']] = f
        cls.saida = {}
        for m in cls.exp.data['maps'].values():
            for balde in BALDES:
                for f in (m.get('features') or {}).get(balde, []):
                    cls.saida[f['properties']['id']] = f

    def test_escaladas_com_os_parametros_novos(self):
        self.assertEqual(len(self.escaladas), 8)
        casos = []
        for eid, tipo in self.escaladas.items():
            p, p0 = self.saida[eid]['properties'], self.orig[eid]['properties']
            casos.append((tipo, p))
            with self.subTest(tipo=tipo, nome=p.get('nome')):
                for k in ('radius', 'majorRadius', 'minorRadius', 'width', 'height'):
                    if k in p0 and k in formas._LIVRES[tipo]:
                        self.assertAlmostEqual(p[k] / p0[k], self.ESCALA, delta=0.002)
                self.assertEqual(self.saida[eid]['geometry']['coordinates'][0],
                                 montador._arredondar(formas.gerar(tipo, p)))
        avisos = [a for a in self.exp.relatorio.avisos if 'vértice a vértice' in a]
        self.assertEqual(len(avisos), len(self.puxadas))
        web = rodar_web(casos)
        if web is None:
            return
        pior = max(desvio_vertices_m(self.saida[eid]['geometry']['coordinates'][0], w)
                   for (eid, _t), w in zip(self.escaladas.items(), web))
        print('\nformas escaladas: o Web, com os parâmetros exportados, desenha a geometria exportada a até {:.3f} m'
              .format(pior))
        self.assertLess(pior, 0.1)

    def test_puxadas_saem_como_desenhadas_com_aviso(self):
        for eid, tipo in self.puxadas.items():
            with self.subTest(tipo=tipo):
                p, p0 = self.saida[eid]['properties'], self.orig[eid]['properties']
                self.assertEqual(p.get('center'), p0.get('center'))
                nome = p0.get('nome')
                aviso = [a for a in self.exp.relatorio.avisos if '"{}"'.format(nome) in a]
                self.assertTrue(aviso and 'tolerância' in aviso[0], aviso)

    def test_giradas_em_graus_saem_giradas_no_terreno(self):
        """Sem o plugin, a forma girada pela ferramenta Girar sai como a forma girada no terreno, com aviso."""
        self.assertEqual(len(self.giradas), 4)
        casos = []
        for eid, tipo in self.giradas.items():
            p, p0 = self.saida[eid]['properties'], self.orig[eid]['properties']
            casos.append((tipo, p))
            with self.subTest(tipo=tipo, nome=p.get('nome')):
                if tipo != 'circle':
                    self.assertAlmostEqual(_giro_esperado(tipo, p0, p, self.GIRO), 0, delta=0.05)
                    aviso = [a for a in self.exp.relatorio.avisos if '"{}"'.format(p0.get('nome')) in a]
                    self.assertTrue(aviso and 'girad' in aviso[0] and 'vértice a vértice' not in aviso[0], aviso)
                for k in ('radius', 'majorRadius', 'minorRadius', 'width', 'height', 'aperture'):
                    if k in p0 and k in formas._LIVRES[tipo]:
                        self.assertAlmostEqual(p[k] / p0[k], 1, delta=1e-3)
                self.assertEqual(self.saida[eid]['geometry']['coordinates'][0],
                                 montador._arredondar(formas.gerar(tipo, p)))
        web = rodar_web(casos)
        if web is not None:
            pior = max(desvio_vertices_m(self.saida[eid]['geometry']['coordinates'][0], w)
                       for (eid, _t), w in zip(self.giradas.items(), web))
            print('\nformas giradas em graus: o Web, com os parâmetros exportados, desenha a geometria exportada a até '
                  '{:.3f} m'.format(pior))
            self.assertLess(pior, 0.1)

    def test_regua_reprova_so_translacao(self):
        """Pior caso: o exportador de antes (sem o ajuste) avisa nas escaladas e guarda os parâmetros velhos."""
        class Antes(montador.Montador):
            def _forma_ajustada(self, tipo, p, orig, geo):
                return None, 'sem ajuste'
        exp = Antes(montador.Calco(self.cam), desenho.GeradorDesenho()).montar()
        avisos = [a for a in exp.relatorio.avisos if 'vértice a vértice' in a]
        self.assertEqual(len(avisos), len(self.escaladas) + len(self.puxadas) + len(self.giradas))

    def test_regua_reprova_sem_o_giro_em_graus(self):
        """Pior caso: sem giro_em_graus (o exportador de antes), a girada que ficou achatada sai como desenhada."""
        from unittest import mock
        with mock.patch.object(formas, 'giro_em_graus', lambda *a: None):
            exp = montador.montar(self.cam, montador.ESCOPO_TUDO, None, desenho.GeradorDesenho())
        achatadas = [eid for eid, t in self.giradas.items() if t != 'circle']
        nomes = ['"{}"'.format(self.orig[eid]['properties'].get('nome')) for eid in achatadas]
        avisos = [a for a in exp.relatorio.avisos if 'vértice a vértice' in a and any(n in a for n in nomes)]
        self.assertEqual(len(avisos), len(achatadas))


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestGuardiao(unittest.TestCase):
    """Com o plugin, o guardião troca a forma girada em graus pela forma girada no terreno."""

    @classmethod
    def setUpClass(cls):
        cls.cam = os.path.join(TMP, 'guardiao.gpkg')
        escritor.importar(FIXTURE_06, cls.cam)
        cls.orig = {}
        for m in leitor.abrir(FIXTURE_06).data['maps'].values():
            for balde in BALDES:
                for f in (m.get('features') or {}).get(balde, []):
                    cls.orig[f['properties']['id']] = f['properties']

    def _girar(self, tipo, com_guardiao=True):
        """Gira a primeira forma do tipo como o Girar do QGIS (um comando de edição)."""
        from unittest import mock
        from Calco import guardiao
        l = QgsVectorLayer('{}|layername={}'.format(self.cam, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
        g = guardiao.Guardiao(l, tipo)
        f = next(l.getFeatures())
        antes = QgsGeometry(f.geometry())
        girada = QgsGeometry(antes)
        girada.rotate(30, girada.boundingBox().center())
        l.startEditing()
        sem = mock.patch.object(g, '_desgirar', return_value=None)
        if not com_guardiao:
            sem.start()
        l.beginEditCommand('Feições giradas')
        l.changeGeometry(f.id(), girada)
        l.endEditCommand()
        if not com_guardiao:
            sem.stop()
        self.addCleanup(lambda: (g.desconectar(), l.rollBack()))
        return l, g, f, antes, girada

    @staticmethod
    def _anel(geom):
        partes = geom.asMultiPolygon() if geom.isMultipart() else [geom.asPolygon()]
        return [[v.x(), v.y()] for v in partes[0][0]]

    def test_girar_vira_a_forma_girada_no_terreno(self):
        for tipo in ('circle', 'ellipse', 'rectangle', 'sector'):
            with self.subTest(tipo=tipo):
                l, g, f, antes, girada = self._girar(tipo)
                agora = l.getFeature(f.id()).geometry()
                self.assertEqual(g.desgiradas, 1)
                esperado, _giro = formas.giro_em_graus(self._anel(antes), self._anel(girada), tipo)
                self.assertEqual(self._anel(agora), [[x, y] for x, y in esperado])
                self.assertEqual(agora.isMultipart(), antes.isMultipart())
                # o ajuste a reconhece no plano, sem o giro em graus: é a forma, com o giro dado
                p0 = self.orig[f['ebgeo_id']]
                q, _a, desvio, tol = formas.ajustar(tipo, p0, self._anel(antes), self._anel(agora))
                self.assertLessEqual(desvio, tol)
                if tipo != 'circle':
                    self.assertAlmostEqual(_giro_esperado(tipo, p0, q, 30), 0, delta=0.05)
                r = formas.ajustar(tipo, p0, self._anel(antes), self._anel(girada))
                self.assertGreater(r[2], r[3])   # o desenho do Girar não era a forma
                # Ctrl+Z desfaz a troca do guardião e volta ao desenho do Girar
                l.undoStack().undo()
                self.assertEqual(self._anel(l.getFeature(f.id()).geometry()), self._anel(girada))

    def test_pior_caso_sem_o_guardiao_fica_achatada(self):
        l, g, f, antes, girada = self._girar('ellipse', com_guardiao=False)
        self.assertEqual(g.desgiradas, 0)
        self.assertEqual(self._anel(l.getFeature(f.id()).geometry()), self._anel(girada))


if __name__ == '__main__':
    print('fixtures:', FIXTURES)
    r = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if r.wasSuccessful() else 1)
