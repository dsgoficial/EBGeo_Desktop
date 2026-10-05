# -*- coding: utf-8 -*-
"""
Alças de edição do Web no Desktop (Calco/alcas.py): a instância do escalão e a distância do texto da
Linha de Limite, e a largura da Seta.

    python-qgis.bat EBGeo/Calco/testes/test_alcas.py

Com EBGEO_WEB_DIR (ou EBGEO_WEB) e node (EBGEO_NODE ou o PATH), o cálculo das alças roda no próprio
código do Web (createHandles e updateFromHandle de add_boundary_geometry.js e add_arrow_geometry.js)
e é a referência; sem eles, essa parte é pulada.

O que cada classe prova:
    TestContraWeb   a posição de cada alça e o valor que o arraste grava, em posições sobre o eixo, fora
                    dele, além das pontas (o corte do Web) e dos dois lados da Seta, são os do Web;
    TestFerramenta  a ferramenta no mapa: clique seleciona e mostra as alças, o arraste mostra o desenho
                    novo do estilo na banda, e soltar grava no buffer do dock, que o Descartar desfaz e o
                    Salvar grava no calco; na seta combinada só o ramo arrastado muda, na coluna `ramos`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY,  # noqa: E402
                       QgsRectangle, QgsVectorLayer)

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from qgis.gui import QgsMapCanvas, QgsMapMouseEvent  # noqa: E402
from qgis.PyQt.QtCore import QEvent, QPoint, Qt  # noqa: E402
from qgis.testing.mocked import get_iface  # noqa: E402

from Calco import alcas, gpkg, schema  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_alcas_')
RETA = [[-47.95, -15.80], [-47.85, -15.82], [-47.76, -15.80]]

NODE_HARNESS = r'''
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
const [frontend, entrada, saida] = process.argv.slice(2);
const js = join(frontend, 'src', 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-alcas-'));
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
const imp = (p) => import(pathToFileURL(join(js, ...p.split('/'))).href).then((m) => m.default);
const BD = new (await imp('military_tools/boundary_tool/add_boundary_geometry.js'))();
const AR = new (await imp('military_tools/arrow_tool/add_arrow_geometry.js'))();
const casos = JSON.parse(readFileSync(entrada, 'utf8'));
const out = casos.map((c) => {
  const f = { properties: { id: 'x', ...c.props } };
  const geo = c.tipo === 'boundary' ? BD : AR;
  if (c.op === 'alcas') return geo.createHandles(f).map((h) => [h.properties.handleType, h.properties.index ?? null, h.geometry.coordinates]);
  const r = geo.updateFromHandle(c.handle, c.pos, f, c.indice ?? null);
  return r ? r.properties : null;
});
writeFileSync(saida, JSON.stringify(out));
'''


def rodar_web(casos):
    web = os.environ.get('EBGEO_WEB_DIR') or os.environ.get('EBGEO_WEB')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    if not web or not node:
        return None
    d = tempfile.mkdtemp(prefix='ebgeo_alcas_node_')
    script, entrada, saida = (os.path.join(d, n) for n in ('alcas.mjs', 'in.json', 'out.json'))
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    with open(entrada, 'w', encoding='utf-8') as fh:
        json.dump(casos, fh)
    r = subprocess.run([node, script, os.path.join(web, 'frontend'), entrada, saida],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-3000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh)


def _m(a, b):
    return alcas.turf_distance(a, b) * 1000


LIMITE = {'baseCoordinates': RETA, 'echelon': 'XX', 'symbol_size': 1.0, 'text_top': 'A', 'text_bottom': 'B',
          'symbol_instances': [{'ratio': 0.3, 'showLabels': True}, {'ratio': 0.7, 'showLabels': False}]}
LIMITE_SEM_RAZAO = dict(LIMITE)
LIMITE_COM_RAZAO = dict(LIMITE, text_distance_ratio=1.4)
SETA = {'baseCoordinates': RETA, 'width': 500}
SETA_NEG = {'baseCoordinates': RETA, 'width': -800}
# cursores: sobre o eixo, fora dele, além das duas pontas (corte do Web), dos dois lados
CURSORES = [[-47.90, -15.79], [-47.82, -15.83], [-47.70, -15.79], [-48.10, -15.80], [-47.86, -15.80],
            [-47.765, -15.805], [-47.755, -15.79]]


def _web_limite_tamanho_km(p):
    """resolveSymbolSize sem zoom e sem âncora: o tamanho gravado com o teto pelo comprimento do eixo."""
    L = alcas.turf_length(p['baseCoordinates'])
    n = len(p['symbol_instances'])
    return min(max(p['symbol_size'], 0.001), L * 0.5 / (n * len(p['echelon']) * 1.8))


class TestContraWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.casos = []
        for p in (LIMITE_SEM_RAZAO, LIMITE_COM_RAZAO):
            cls.casos.append({'tipo': 'boundary', 'op': 'alcas', 'props': p})
        cls.casos.append({'tipo': 'arrow', 'op': 'alcas', 'props': SETA})
        cls.casos.append({'tipo': 'arrow', 'op': 'alcas', 'props': SETA_NEG})
        for pos in CURSORES:
            for i in (0, 1):
                cls.casos.append({'tipo': 'boundary', 'op': 'arrastar', 'props': LIMITE, 'handle': 'symbol_handle',
                                  'indice': i, 'pos': pos})
            cls.casos.append({'tipo': 'boundary', 'op': 'arrastar', 'props': LIMITE, 'handle': 'text_distance_handle',
                              'pos': pos})
            cls.casos.append({'tipo': 'arrow', 'op': 'arrastar', 'props': SETA, 'handle': 'width', 'pos': pos})
        cls.web = rodar_web(cls.casos)

    def setUp(self):
        if self.web is None:
            self.skipTest('EBGEO_WEB_DIR/EBGEO_WEB ou node ausente')

    def test_posicao_das_alcas(self):
        pior = 0.0
        for c, w in zip(self.casos, self.web):
            if c['op'] != 'alcas':
                continue
            p = c['props']
            if c['tipo'] == 'boundary':
                nossas = alcas.alcas_limite(p['baseCoordinates'], p, _web_limite_tamanho_km(p))
                deles = [h for h in w if h[0] in ('symbol_handle', 'text_distance_handle')]
                self.assertEqual([t for t, _i, _p in nossas], ['instancia', 'instancia', 'texto'])
                self.assertEqual(len(deles), 3)
                for (_t, _i, q), (_h, _x, r) in zip(nossas, deles):
                    pior = max(pior, _m(q, r))
            else:
                h = next(h for h in w if h[0] == 'width')
                pior = max(pior, _m(alcas.alca_largura(p['baseCoordinates'], p['width']), h[2]))
        print('\nposição das alças contra o Web: até {:.4f} m'.format(pior))
        self.assertLess(pior, 0.01)

    def test_arraste(self):
        dif = {'ratio': 0.0, 'texto': 0.0, 'largura': 0.0}
        for c, w in zip(self.casos, self.web):
            if c['op'] != 'arrastar':
                continue
            p, pos = c['props'], c['pos']
            if c['handle'] == 'symbol_handle':
                nosso = alcas.arrastar_instancia(p['baseCoordinates'], p['symbol_instances'], c['indice'], pos)
                for a, b in zip(nosso, w['symbol_instances']):
                    dif['ratio'] = max(dif['ratio'], abs(a['ratio'] - b['ratio']))
                    self.assertEqual(a['showLabels'], b['showLabels'])
            elif c['handle'] == 'text_distance_handle':
                nosso = alcas.arrastar_texto(p['baseCoordinates'], p['symbol_instances'], _web_limite_tamanho_km(p), pos)
                dif['texto'] = max(dif['texto'], abs(nosso - w['text_distance_ratio']))
            else:
                nosso = alcas.arrastar_largura(p['baseCoordinates'], pos)
                self.assertEqual(nosso < 0, w['width'] < 0, pos)
                dif['largura'] = max(dif['largura'], abs(nosso - w['width']))
        print('\narraste contra o Web: razão {:.2e}, distância do texto {:.2e}, largura {:.3f} m'.format(
            dif['ratio'], dif['texto'], dif['largura']))
        self.assertLess(dif['ratio'], 1e-4)
        self.assertLess(dif['texto'], 1e-4)
        self.assertLess(dif['largura'], 0.5)
        # os cortes foram exercitados: a razão no 0,99 do Web, a distância do texto no 3 e a largura negativa
        razoes = [r['ratio'] for x in self.web if isinstance(x, dict) and 'symbol_instances' in x
                  for r in x['symbol_instances']]
        self.assertIn(0.99, razoes)
        self.assertIn(0.01, razoes)
        self.assertTrue(any(isinstance(x, dict) and x.get('text_distance_ratio') == 3 for x in self.web))
        self.assertTrue(any(isinstance(x, dict) and x.get('width', 1) < 0 for x in self.web))

    def test_regua_reprova_pior_caso(self):
        """Sem o corte do Web a razão além da ponta passa de 0,99; sem o sinal, a largura do outro lado sai positiva."""
        p = LIMITE
        L = alcas.turf_length(p['baseCoordinates'])
        sem_corte = alcas.ponto_mais_perto_km(p['baseCoordinates'], [-47.70, -15.79]) / L
        web = next(w for c, w in zip(self.casos, self.web) if c['op'] == 'arrastar' and c['handle'] == 'symbol_handle'
                   and c['pos'] == [-47.70, -15.79] and c['indice'] == 0)
        self.assertGreater(abs(sem_corte - web['symbol_instances'][0]['ratio']), 1e-3)
        sem_sinal = alcas.distancia_ao_segmento_m(RETA[-2], RETA[-1], [-47.765, -15.805])
        web = next(w for c, w in zip(self.casos, self.web) if c['op'] == 'arrastar' and c['handle'] == 'width'
                   and c['pos'] == [-47.765, -15.805])
        self.assertGreater(abs(sem_sinal - web['width']), 1)


# ---------------------------------------------------------------- a ferramenta no mapa

def _calco():
    from Calco.calco import Calco, definir_calco_ativo
    cam = os.path.join(tempfile.mkdtemp(prefix='ebgeo_alcas_'), 'alcas.gpkg')
    c = Calco(cam)
    c.criar()
    c.carregar(estilizar_novas=True)
    definir_calco_ativo(c)
    return c


def _nova(camada, tipo, partes, **attrs):
    f = QgsFeature(camada.fields())
    if schema.TIPOS[tipo]['geometria'] == 'MultiLineString':
        f.setGeometry(QgsGeometry.fromMultiPolylineXY([[QgsPointXY(*p) for p in parte] for parte in partes]))
    else:
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in partes[0]]))
    valores = dict(schema.padroes(tipo), ebgeo_id=str(uuid.uuid4()))
    valores.update(attrs)
    for k, v in valores.items():
        f[k] = schema.valor_json_para_qgis(v) if isinstance(v, (list, dict)) else v
    ok, novas = camada.dataProvider().addFeatures([f])
    assert ok
    camada.reload()
    return novas[0].id()


def _evento(cv, tipo, ponto, botao=Qt.MouseButton.LeftButton):
    """O evento do mouse no pixel do ponto (lon, lat)."""
    from qgis.core import QgsCoordinateTransform, QgsProject
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), cv.mapSettings().destinationCrs(),
                                QgsProject.instance())
    px = cv.getCoordinateTransform().transform(tr.transform(QgsPointXY(*ponto)))
    return QgsMapMouseEvent(cv, tipo, QPoint(int(round(px.x())), int(round(px.y()))), botao, botao,
                            Qt.KeyboardModifier.NoModifier)


class TestFerramenta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from Calco.ui.painel import PainelCalco
        cls.calco = _calco()
        cls.iface = get_iface()
        cls.painel = PainelCalco(cls.iface)
        cls.cv = QgsMapCanvas()
        cls.cv.resize(1000, 600)
        cls.cv.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        from qgis.core import QgsCoordinateTransform, QgsProject
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), QgsCoordinateReferenceSystem('EPSG:3857'),
                                    QgsProject.instance())
        cls.cv.setExtent(tr.transformBoundingBox(QgsRectangle(-47.97, -15.86, -47.74, -15.74)))
        cls.limite = cls.calco.camada('boundary')
        cls.seta = cls.calco.camada('arrow')
        cls.cv.setLayers([cls.limite, cls.seta])
        cls.ft = alcas.FerramentaAlcas(cls.cv, None, lambda: cls.painel)

    def _arrastar(self, de, para):
        self.ft.canvasPressEvent(_evento(self.cv, QEvent.Type.MouseButtonPress, de))
        self.ft.canvasMoveEvent(_evento(self.cv, QEvent.Type.MouseMove, para))
        preview = self.ft.preview.asGeometry()
        self.ft.canvasReleaseEvent(_evento(self.cv, QEvent.Type.MouseButtonRelease, para))
        return preview

    def _no_pixel(self, ponto):
        """O (lon, lat) do pixel em que o evento cai: o que a ferramenta lê."""
        return self.ft._do_mapa(self.ft.toMapCoordinates(_evento(self.cv, QEvent.Type.MouseMove, ponto).pos()))

    def _reler(self, tipo, fid):
        l = QgsVectorLayer(gpkg.uri_camada(self.calco.caminho, tipo), 'r', 'ogr')
        return l.getFeature(fid)

    def test_instancia_do_limite_descartar_e_salvar(self):
        inst = [{'ratio': 0.3, 'showLabels': True}, {'ratio': 0.7, 'showLabels': True}]
        fid = _nova(self.limite, 'boundary', [RETA], echelon='XX', symbol_size_km=1.0, text_top='A',
                    symbol_instances=inst)
        self.limite.selectByIds([fid])
        self.ft.selecionar(self.limite, fid)
        self.assertEqual([t for t, _i, _p in self.ft.alcas], ['instancia', 'instancia', 'texto'])
        alca = self.ft.alcas[1][2]
        destino = [-47.80, -15.83]
        preview = self._arrastar(alca, destino)
        self.assertFalse(preview.isEmpty())                       # o desenho novo apareceu na banda
        esperado = alcas.arrastar_instancia(RETA, inst, 1, self.ft._do_mapa(self.ft.toMapCoordinates(
            _evento(self.cv, QEvent.Type.MouseMove, destino).pos())))
        buf = json.loads(json.dumps(self.limite.getFeature(fid)['symbol_instances']))
        buf = json.loads(buf) if isinstance(buf, str) else buf
        self.assertAlmostEqual(buf[1]['ratio'], esperado[1]['ratio'], places=9)
        self.assertEqual(buf[0]['ratio'], 0.3)
        self.assertTrue(self.limite.isModified())
        self.assertTrue(self.painel.botao_salvar.isEnabled())     # no buffer do dock
        self.assertTrue(self.painel.descartar())
        self.assertFalse(self.limite.isModified())
        f = self.limite.getFeature(fid)
        v = f['symbol_instances']
        v = json.loads(v) if isinstance(v, str) else v
        self.assertEqual(v[1]['ratio'], 0.7)
        # de novo, e Salvar: no calco
        self.ft.selecionar(self.limite, fid)
        self._arrastar(self.ft.alcas[1][2], destino)
        self.assertTrue(self.painel.salvar())
        v = self._reler('boundary', fid)['symbol_instances']
        v = json.loads(v) if isinstance(v, str) else v
        self.assertAlmostEqual(v[1]['ratio'], esperado[1]['ratio'], places=9)

    def test_distancia_do_texto(self):
        fid = _nova(self.limite, 'boundary', [[[x, y - 0.03] for x, y in RETA]], echelon='XX', symbol_size_km=1.0,
                    text_top='NORTE', symbol_instances=[{'ratio': 0.5, 'showLabels': True}])
        self.limite.selectByIds([fid])
        self.ft.selecionar(self.limite, fid)
        texto = next(p for t, _i, p in self.ft.alcas if t == 'texto')
        f = self.limite.getFeature(fid)
        tam = self.ft.tamanho_km(f)
        self.assertAlmostEqual(tam, 1.0, places=6)                 # o @s do estilo, sem âncora: o gravado
        c = alcas.turf_along([[x, y - 0.03] for x, y in RETA], alcas.turf_length([[x, y - 0.03] for x, y in RETA]) * 0.5)
        destino = alcas.turf_destination(c, 2.0, alcas.turf_bearing(texto, c) + 180)
        self._arrastar(texto, destino)
        v = self.limite.getFeature(fid)['text_distance_ratio']
        self.assertAlmostEqual(v, alcas.arrastar_texto([[x, y - 0.03] for x, y in RETA], f['symbol_instances'], tam,
                                                       self._no_pixel(destino)), places=9)
        self.assertAlmostEqual(v, 2.0, delta=0.05)                # 2 km do centro / 1 km de tamanho, a um pixel
        self.assertTrue(self.painel.salvar())
        self.assertAlmostEqual(self._reler('boundary', fid)['text_distance_ratio'], v, places=9)

    def test_largura_da_seta_simples_e_combinada(self):
        fid = _nova(self.seta, 'arrow', [RETA], width_m=500.0)
        self.seta.selectByIds([fid])
        self.ft.selecionar(self.seta, fid)
        (t, i, alca), = self.ft.alcas
        self.assertEqual((t, i), ('largura', 0))
        destino = alcas.turf_destination(RETA[-1], 0.9, alcas.turf_bearing(RETA[-2], RETA[-1]) - 90)
        self._arrastar(alca, destino)
        w = self.seta.getFeature(fid)['width_m']
        self.assertAlmostEqual(w, alcas.arrastar_largura(RETA, self._no_pixel(destino)), places=6)
        self.assertAlmostEqual(w, 900, delta=self.cv.mapUnitsPerPixel())   # um pixel de 3857
        self.assertTrue(self.painel.salvar())
        self.assertAlmostEqual(self._reler('arrow', fid)['width_m'], w, places=6)
        # combinada: o ramo 1 arrastado muda só na coluna ramos, e o topo fica
        ramos = {'ramos': [{'width': 400}, {'width': 400, 'doubleHeaded': True}], 'topo': {'width': 400.0}}
        r2 = [[x, y + 0.05] for x, y in RETA]
        fid = _nova(self.seta, 'arrow', [RETA, r2], width_m=400.0, ramos=ramos)
        self.seta.selectByIds([fid])
        self.ft.selecionar(self.seta, fid)
        self.assertEqual([t for t, _i, _p in self.ft.alcas], ['largura', 'largura'])
        destino = alcas.turf_destination(r2[-1], 0.6, alcas.turf_bearing(r2[-2], r2[-1]) - 90)
        antes = self.seta.getFeature(fid).geometry()
        self._arrastar(self.ft.alcas[1][2], destino)
        f = self.seta.getFeature(fid)
        v = f['ramos']
        v = json.loads(v) if isinstance(v, str) else v
        self.assertAlmostEqual(v['ramos'][1]['width'], alcas.arrastar_largura(r2, self._no_pixel(destino)), places=6)
        self.assertAlmostEqual(v['ramos'][1]['width'], 600, delta=self.cv.mapUnitsPerPixel())
        self.assertEqual(v['ramos'][0]['width'], 400)
        self.assertEqual(f['width_m'], 400.0)
        self.assertTrue(f.geometry().equals(antes))
        self.assertTrue(self.painel.salvar())


    def test_acao_no_menu(self):
        from qgis.PyQt.QtWidgets import QMenu
        from Calco.gerenciador import GerenciadorCalco
        iface = get_iface()
        g = GerenciadorCalco(iface, QMenu('EBGeo'))
        g.initGui()
        try:
            acao = next(a for a in g.acoes if a.text() == 'Alças de edição (Limite e Seta)')
            self.assertFalse(acao.icon().isNull())
            acao.trigger()
            ft = g.ferramentas['alcas']
            self.assertIs(iface.mapCanvas().mapTool(), ft)
            self.assertIsNotNone(ft.obter_painel())            # o dock que recebe o arraste
            self.assertIs(ft.obter_painel(), g.painel)
        finally:
            iface.mapCanvas().unsetMapTool(g.ferramentas['alcas'])
            g.unload()


if __name__ == '__main__':
    r = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if r.wasSuccessful() else 1)
