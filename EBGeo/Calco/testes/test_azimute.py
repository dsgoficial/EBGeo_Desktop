# -*- coding: utf-8 -*-
"""
Azimute e Distância (Calco/azimute): a ferramenta do EBGeo Web no QGIS 4.

    python-qgis.bat EBGeo/Calco/testes/test_azimute.py

- Paridade com o Web: os vértices das feições azimuth_distance da fixture 06 (gravados pelo
  próprio Web) contra os recalculados aqui; com EBGEO_WEB (raiz do ebgeo_web) e node, também
  os casos de paridade_azimute.mjs rodados no código do Web (vértices, três nortes, textos).
- Ferramenta: cria no calco (ponto, rota, área), relê o GeoPackage pelo OGR e confere geometria
  e construção com as chaves do Web; preview, vírgula decimal, declinação e convergência.
- Edição: a seleção abre a construção, a tabela NV | NQ | NM | Distância e o salvar refaz a
  geometria; vale para a feição importada do .ebgeo.
- Importador: a construção do .ebgeo chega à coluna azimute_distancia.
- Plugin: a ação "Azimute e Distância" existe no menu do EBGeo e abre a ferramenta; o módulo
  antigo AzimuthDistance saiu.

EBGEO_IMAGENS (pasta) guarda os PNGs de conferência; sem ela, vão para uma pasta temporária.
"""
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
PASTA_EBGEO = os.path.dirname(os.path.dirname(AQUI))
RAIZ_REPO = os.path.dirname(PASTA_EBGEO)
sys.path.insert(0, PASTA_EBGEO)

FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_30 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
IMAGENS = os.environ.get('EBGEO_IMAGENS') or tempfile.mkdtemp(prefix='ebgeo_azimute_')
os.makedirs(IMAGENS, exist_ok=True)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsMapRendererParallelJob, QgsMapSettings,
    QgsProject, QgsRectangle, QgsVectorLayer,
)

_app = QgsApplication([], True)
_app.initQgis()

from osgeo import ogr  # noqa: E402
from qgis.testing.mocked import get_iface  # noqa: E402
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

from Calco.azimute import geometria as G  # noqa: E402
from Calco.azimute import gravacao  # noqa: E402
from Calco.azimute.ferramenta import AzimuteDistancia, FerramentaAzimute  # noqa: E402
from Calco.azimute.painel import ler_azimute, ler_csv_pernas, ler_numero  # noqa: E402
from Calco.calco import Calco, definir_calco_ativo  # noqa: E402
from Calco.motor import declinacao  # noqa: E402

ogr.UseExceptions()


def foto_painel(painel, nome):
    """PNG do painel no tamanho de uso (solto na janela simulada ele nasce minúsculo)."""
    painel.setFloating(True)
    painel.resize(460, 1250)
    painel.show()
    _app.processEvents()
    painel.grab().save(os.path.join(IMAGENS, nome))


def metros(a, b):
    return G.distancia_haversine(a, b)


def max_desvio(c1, c2):
    assert len(c1) == len(c2), (len(c1), len(c2))
    return max(metros(a, b) for a, b in zip(c1, c2))


def node_executavel():
    for c in (os.environ.get('EBGEO_NODE'), shutil.which('node'),
              os.path.join(os.environ.get('ProgramFiles', ''), 'nodejs', 'node.exe')):
        if c and os.path.exists(c):
            return c
    return None


def web_no_node(casos):
    """Roda os casos no código do Web; None sem EBGEO_WEB ou sem node."""
    web, node = os.environ.get('EBGEO_WEB'), node_executavel()
    if not web or not node:
        return None
    r = subprocess.run([node, os.path.join(AQUI, 'paridade_azimute.mjs'), '--web', web],
                       input=json.dumps(casos).encode('utf-8'), capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace'))
    return json.loads(r.stdout.decode('utf-8'))


def feicoes_azimute_fixture():
    from Calco.importador import leitor
    doc = leitor.abrir(FIXTURE_30)
    out = []
    for nome, m in doc.data['maps'].items():
        for balde, lst in (m.get('features') or {}).items():
            for ft in lst:
                p = ft.get('properties') or {}
                if p.get('featureType') == 'azimuth_distance':
                    out.append((nome, balde, ft))
    return out


# casos de paridade: os três nortes, as unidades, os três modos, perna longa (densificação),
# perna incompleta e o fuso vizinho (convergência negativa)
CASOS = [
    {'referencePoint': [-47.8, -15.75], 'outputMode': 'route', 'angularUnit': 'degrees', 'distanceUnit': 'meters',
     'northReference': 'grid', 'magneticDeclination': -21.53,
     'legs': [{'azimuth': 45, 'distance': 1500, 'observation': 'a'}, {'azimuth': 120.5, 'distance': 800}]},
    {'referencePoint': [-51.21, -30.03], 'outputMode': 'area', 'angularUnit': 'degrees', 'distanceUnit': 'meters',
     'northReference': 'magnetic', 'magneticDeclination': -17.12,
     'legs': [{'azimuth': 10, 'distance': 2500}, {'azimuth': 100, 'distance': 1800}, {'azimuth': 200, 'distance': 900}]},
    {'referencePoint': [-43.2, -22.9], 'outputMode': 'route', 'angularUnit': 'mils', 'distanceUnit': 'kilometers',
     'northReference': 'true', 'magneticDeclination': -23.0,
     'legs': [{'azimuth': 800, 'distance': 1.5}, {'azimuth': 1600, 'distance': 2}, {'azimuth': 3200, 'distance': 0.8}]},
    {'referencePoint': [-60.02, -3.1], 'outputMode': 'point', 'angularUnit': 'degrees', 'distanceUnit': 'meters',
     'northReference': 'grid', 'magneticDeclination': -14.4,
     'legs': [{'azimuth': 30, 'distance': 1200, 'observation': 'Marco A'}, {'azimuth': 95, 'distance': 900}]},
    {'referencePoint': [-56.1, -15.6], 'outputMode': 'route', 'angularUnit': 'degrees', 'distanceUnit': 'kilometers',
     'northReference': 'grid', 'magneticDeclination': -16.0,
     'legs': [{'azimuth': 300, 'distance': 150}, {'azimuth': '', 'distance': 3}, {'azimuth': 15, 'distance': 0}]},
    {'referencePoint': [-47.95, -15.75], 'outputMode': 'area', 'angularUnit': 'degrees', 'distanceUnit': 'meters',
     'northReference': 'grid', 'magneticDeclination': -21.0, 'meridianConvergence': 0.5,
     'legs': [{'azimuth': 359.95, 'distance': 1000}, {'azimuth': 90, 'distance': 1000}]},
]


def _python_do_caso(c):
    conv = G.resolver_convergencia(c)
    vert = G.calcular_vertices(c['referencePoint'], c['legs'], c['magneticDeclination'], c['northReference'],
                               c['angularUnit'], c['distanceUnit'], conv)
    leit = G.pernas_tres_nortes(c['legs'], c['angularUnit'], c['northReference'], c['magneticDeclination'], conv)
    return {
        'convergencia': conv, 'vertices': vert, 'geometria': G.gerar_geometria(vert, c['outputMode']),
        'polar': None if c['outputMode'] == 'point' else G.dados_polares(c),
        'leituras': leit,
        'textos': [None if r is None else [G.texto_angulo(r[k], c['angularUnit']) for k in ('nv', 'nq', 'nm')] for r in leit],
        'correcoes': [G.texto_correcao(c['magneticDeclination']), G.texto_correcao(conv)],
        'total': G.texto_total(G.distancia_total(c['legs']), c['distanceUnit']),
        'podeCriar': G.pode_criar(c['referencePoint'], c['legs'], c['outputMode']),
    }


class TesteGeometria(unittest.TestCase):
    def test_tres_nortes_do_esboco_aprovado(self):
        """δ -21,6 e γ +0,8: NV 23,4 / NQ 22,6 / NM 45,0, digitado em qualquer norte."""
        for norte, az in ((G.NQ, 22.6), (G.NM, 45.0), (G.NV, 23.4)):
            r = G.pernas_tres_nortes([{'azimuth': az, 'distance': 1}], G.GRAUS, norte, -21.6, 0.8)[0]
            self.assertAlmostEqual(r['nv'], 23.4, places=9)
            self.assertEqual([G.texto_angulo(r[k]) for k in ('nv', 'nq', 'nm')], ['23,4°', '22,6°', '45,0°'])
        # controle negativo: a regra que só testava o NV corrigia o NQ pela declinação
        errado = 22.6 + (-21.6)
        self.assertGreater(abs(errado - G.aplicar_declinacao(22.6, -21.6, G.NQ, 0.8)), 20)

    def test_normalizacao_no_topo_do_circulo(self):
        self.assertEqual(G.normalizar_azimute(359.99999999999994), 359.99999999999994)
        v = G.normalizar_azimute(-1e-14)
        self.assertTrue(0 <= v < 360)
        self.assertEqual(math.copysign(1, G.normalizar_azimute(-720.0)), 1.0)

    def test_virgula_decimal_e_gms(self):
        self.assertEqual(ler_numero('45,5'), 45.5)
        self.assertEqual(ler_numero('1.500'), 1.5)
        self.assertAlmostEqual(ler_azimute('45.30.36'), 45.51, places=9)
        self.assertAlmostEqual(ler_azimute("45°30'36\""), 45.51, places=9)
        self.assertEqual(G.texto_correcao(0.76), '+0,8°')
        self.assertEqual(G.texto_total(2300, G.METROS), '2,30 km')
        self.assertEqual(G.texto_distancia(800), '800,0 m')
        self.assertEqual(G.texto_angulo(45.0, G.MILESIMOS), '800₥')
        with self.assertRaises(ValueError):
            ler_numero('abc')

    @unittest.skipUnless(os.path.exists(FIXTURE_30), 'fixture 06 ausente')
    def test_vertices_iguais_aos_gravados_pelo_web(self):
        """As 6 feições azimuth_distance da fixture 06 (rota, área, pontos; NV e NM; mils/km)."""
        feicoes = feicoes_azimute_fixture()
        self.assertEqual(len(feicoes), 6)
        piores = []
        for nome, balde, ft in feicoes:
            polar = ft['properties']['azimuthDistanceData']
            vert = G.vertices_da_construcao(polar)
            if balde == 'points':
                c = [vert[polar['waypointIndex']]]
                w = [ft['geometry']['coordinates']]
            else:
                geo = G.gerar_geometria(vert, polar['outputMode'])
                c = geo['coordinates'] if geo['type'] == 'LineString' else geo['coordinates'][0]
                w = ft['geometry']['coordinates'] if geo['type'] == 'LineString' else ft['geometry']['coordinates'][0]
                self.assertEqual(len(c), len(w), ft['properties']['nome'])
                self.assertLess(max_desvio(ft['properties']['baseCoordinates'], vert), 0.001)
            piores.append(max_desvio(c, w))
            # a geometria gravada pelo Web vem arredondada a 6 casas (cerca de 11 cm; os
            # baseCoordinates, sem arredondar, batem acima): arredondados igual, os vértices são iguais
            self.assertEqual([[round(x, 6), round(y, 6)] for x, y in c], [[x, y] for x, y in w],
                             ft['properties']['nome'])
        print('\n  fixture 06: {} feições; vértices iguais aos do Web em 6 casas; desvio bruto máximo {:.3f} m '
              '(o arredondamento do Web)'.format(len(piores), max(piores)))
        self.assertLess(max(piores), 0.08)

    def test_paridade_com_o_web_no_node(self):
        web = web_no_node(CASOS)
        if web is None:
            self.skipTest('EBGEO_WEB ou node ausente: paridade não medida')
        pior = 0.0
        for c, w in zip(CASOS, web):
            py = _python_do_caso(c)
            self.assertEqual(py['convergencia'], w['convergencia'])
            pior = max(pior, max_desvio(py['vertices'], w['vertices']))
            if w['geometria']:
                k = py['geometria']['coordinates']
                kw = w['geometria']['coordinates']
                if py['geometria']['type'] == 'Polygon':
                    k, kw = k[0], kw[0]
                pior = max(pior, max_desvio(k, kw))
            for a, b in zip(py['leituras'], w['leituras']):
                if a is None:
                    self.assertIsNone(b)
                    continue
                for n in ('nv', 'nq', 'nm'):
                    self.assertAlmostEqual(a[n], b[n], places=9)
            self.assertEqual(py['textos'], w['textos'])
            self.assertEqual(py['correcoes'], w['correcoes'])
            self.assertEqual(py['total'], w['total'])
            self.assertEqual(list(py['podeCriar']), [w['podeCriar']['canCreate'], w['podeCriar']['reason']])
            if w['polar']:
                self.assertEqual(json.dumps(py['polar'], sort_keys=True), json.dumps(w['polar'], sort_keys=True))
        print('\n  paridade node: {} casos, desvio máximo {:.2e} m'.format(len(CASOS), pior))
        self.assertLess(pior, 0.001)


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='ebgeo_az_')
        cls.caminho = os.path.join(cls.tmp, 'calco_azimute.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.iface = get_iface()
        cls.iface.mainWindow().resize(1200, 900)
        cls.iface.mainWindow().show()
        cls.canvas = cls.iface.mapCanvas()
        cls.canvas.resize(800, 600)
        cls.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        cls.canvas.setExtent(QgsRectangle(-47.84, -15.79, -47.74, -15.71))
        cls.ctl = AzimuteDistancia(cls.iface)

    @classmethod
    def tearDownClass(cls):
        # desmonta antes do fim do processo: painel, bandas e conexões com as camadas
        cls.ctl.unload()
        _app.processEvents()
        QgsProject.instance().removeAllMapLayers()

    def _ler_ogr(self, tabela, filtro=None):
        ds = ogr.Open(self.caminho)
        lyr = ds.GetLayerByName(tabela)
        if filtro:
            lyr.SetAttributeFilter(filtro)
        out = []
        for f in lyr:
            g = json.loads(f.GetGeometryRef().ExportToJson())
            out.append(({k: f.GetField(k) for k in f.keys()}, g))
        ds = None
        return out

    def _digitar(self, linha, coluna, texto):
        p = self.ctl.painel
        while p.tab_pernas.rowCount() <= linha:
            p._adicionar_perna()
        p.tab_pernas.item(linha, coluna).setText(texto)


class TesteFerramenta(_Base):
    def _construir(self, modo, norte, pernas, ponto=(-47.8, -15.75)):
        self.assertTrue(self.ctl.ativar())
        p = self.ctl.painel
        p.novo()
        self.assertIsInstance(self.canvas.mapTool(), FerramentaAzimute)
        p._definir_modo(modo)
        p._definir_norte(norte)
        self.ctl.clique_no_mapa(*ponto)
        for i, (az, d) in enumerate(pernas):
            self._digitar(i, 0, az)
            self._digitar(i, 1, d)
        return p

    def test_cria_rota_em_nq_com_virgula_decimal(self):
        p = self._construir(G.ROTA, G.NQ, [('45,5', '1500'), ('120', '800,5')])
        e = p.estado
        # declinação do WMM2025 e convergência do fuso, calculadas no ponto
        self.assertEqual(e['magneticDeclination'], declinacao.calcular_declinacao(-15.75, -47.8)['declination'])
        self.assertEqual(e['meridianConvergence'], declinacao.calcular_convergencia(-15.75, -47.8))
        self.assertEqual([l['azimuth'] for l in e['legs']], [45.5, 120])
        self.assertEqual(e['legs'][1]['distance'], 800.5)
        self.assertIn(',', p.ed_decl.text())
        self.assertIn('fuso 23', p.lbl_conv.text())
        # a leitura da perna ativa e a tabela dos três nortes
        p._definir_ativa(0)
        r = G.pernas_tres_nortes(e['legs'], G.GRAUS, G.NQ, e['magneticDeclination'], e['meridianConvergence'])[0]
        self.assertEqual(p.lbl_leitura.text(), 'Perna 1: NV {} · NQ {} · NM {}'.format(
            G.texto_angulo(r['nv']), G.texto_angulo(r['nq']), G.texto_angulo(r['nm'])))
        self.assertEqual(p.tab_nortes.item(0, 2).text(), '45,50°')
        self.assertEqual(p.tab_nortes.item(1, 4).text(), '800,5 m')
        # preview: a rota inteira no círculo máximo enquanto se digita
        banda = self.ctl.bandas['linha']
        self.assertTrue(banda.isVisible())
        vert = G.calcular_vertices(e['referencePoint'], e['legs'], e['magneticDeclination'], G.NQ, G.GRAUS, G.METROS,
                                   e['meridianConvergence'])
        self.assertEqual(banda.numberOfVertices(), len(G.gerar_geometria(vert, G.ROTA)['coordinates']))
        self.canvas.grab().save(os.path.join(IMAGENS, 'az_preview_canvas.png'))
        foto_painel(p, 'az_painel_criacao.png')
        antes = len(self._ler_ogr('line')) if 'line' in self._tabelas() else 0
        lyr, ids = self.ctl.criar(p.estado_publico())
        linhas = self._ler_ogr('line', "ebgeo_id = '{}'".format(ids[0]))
        self.assertEqual(len(self._ler_ogr('line')), antes + 1)
        attrs, geo = linhas[0]
        polar = json.loads(attrs['azimute_distancia'])
        self.assertEqual(set(polar), {'referencePoint', 'outputMode', 'angularUnit', 'distanceUnit', 'northReference',
                                      'magneticDeclination', 'meridianConvergence', 'legs'})
        self.assertEqual(polar['northReference'], 'grid')
        self.assertEqual(polar['legs'][0], {'azimuth': 45.5, 'distance': 1500, 'observation': ''})
        props = json.loads(attrs['props'])
        self.assertEqual(props['featureType'], 'azimuth_distance')
        self.assertEqual(props['source'], 'line')
        self.assertEqual(props['azimuthDistanceData'], polar)
        self.assertEqual(attrs['line_color'], G.COR)
        self.assertTrue(attrs['criado_em'])
        self.assertEqual(attrs['nome'][:7], 'Linha #')
        self.assertLess(max_desvio(geo['coordinates'], G.gerar_geometria(vert, G.ROTA)['coordinates']), 1e-6)
        # mesma rota no código do Web
        w = web_no_node([dict(polar)])
        if w is not None:
            self.assertLess(max_desvio(geo['coordinates'], w[0]['geometria']['coordinates']), 0.001)
        # a feição nova fica selecionada e o painel passa a editá-la
        self.ctl._camada_mudou(lyr)
        self.ctl._selecao_mudou()
        _app.processEvents()
        self.assertEqual(self.ctl.painel.modo, 'editar')

    def _tabelas(self):
        from Calco import gpkg
        return gpkg.tabelas_presentes(self.caminho)

    def test_cria_area_e_pontos(self):
        p = self._construir(G.AREA, G.NV, [('0', '1000'), ('90', '1000'), ('180', '1000')])
        lyr, ids = self.ctl.criar(p.estado_publico())
        attrs, geo = self._ler_ogr('polygon', "ebgeo_id = '{}'".format(ids[0]))[0]
        self.assertEqual(geo['type'], 'MultiPolygon')
        anel = geo['coordinates'][0][0]
        self.assertEqual(anel[0], anel[-1])
        self.assertEqual(json.loads(attrs['props'])['source'], 'polygon')
        p = self._construir(G.PONTO, G.NM, [('30', '1200'), ('95', '900')], ponto=(-47.77, -15.73))
        self.ctl.painel.tab_pernas.item(0, 2).setText('Marco A')
        lyr, ids = self.ctl.criar(self.ctl.painel.estado_publico())
        self.assertEqual(len(ids), 3)
        pts = self._ler_ogr('point', "ebgeo_id IN ({})".format(','.join("'{}'".format(i) for i in ids)))
        indices = sorted(json.loads(a['azimute_distancia'])['waypointIndex'] for a, _ in pts)
        self.assertEqual(indices, [0, 1, 2])
        self.assertIn('Marco A', [a['nome'] for a, _ in pts])

    def test_selecao_adiada_nao_derruba_construcao_nova(self):
        """Pior caso medido: a edição adiada da seleção trocava a rota em andamento pelos pontos."""
        p = self._construir(G.PONTO, G.NV, [('30', '500')])
        lyr, ids = self.ctl.criar(p.estado_publico())
        self.assertEqual(p.modo, 'editar')
        p.novo()
        self.ctl._selecao_mudou()           # enfileira a edição da feição ainda selecionada
        p._definir_modo(G.ROTA)
        self.ctl.clique_no_mapa(-47.8, -15.75)
        _app.processEvents()                # a fila roda com a construção nova em andamento
        self.assertEqual(p.modo, 'criar')
        self.assertEqual(p.estado['outputMode'], G.ROTA)

    def test_segundo_clique_so_pelo_botao(self):
        """Como no Web: o primeiro clique define a origem; mudar pede "Clicar no mapa" de novo."""
        p = self._construir(G.ROTA, G.NV, [('90', '1000')])
        self.ctl.clique_no_mapa(-47.76, -15.72)
        self.assertEqual(p.estado['referencePoint'], [-47.8, -15.75])
        p._pedir_clique()
        self.ctl.clique_no_mapa(-47.76, -15.72)
        self.assertEqual(p.estado['referencePoint'], [-47.76, -15.72])
        self.assertEqual(p.ed_lat.text(), '-15,720000')

    def test_area_com_uma_perna_nao_cria(self):
        p = self._construir(G.AREA, G.NV, [('0', '1000')])
        self.assertEqual(G.pode_criar(p.estado['referencePoint'], p.estado['legs'], G.AREA),
                         (False, 'Área requer pelo menos 2 pernas'))

    def test_importa_pernas_de_csv(self):
        csvp = os.path.join(self.tmp, 'pernas.csv')
        with open(csvp, 'w', encoding='utf-8') as fh:
            fh.write('Azimute;Distância;Obs\n45,5;1500;P1\n120.30.00;800;P2\nx;1;ruim\n')
        pernas, ruins = ler_csv_pernas(csvp)
        self.assertEqual(ruins, 1)
        self.assertEqual(pernas[0], {'azimuth': 45.5, 'distance': 1500, 'observation': 'P1'})
        self.assertAlmostEqual(pernas[1]['azimuth'], 120.5)
        self.ctl.ativar()
        self.ctl.painel.novo()
        self.assertEqual(self.ctl.painel._importar_csv(csvp), 2)
        self.assertEqual(len(self.ctl.painel.estado['legs']), 2)


class TesteEdicao(_Base):
    def test_edita_pernas_e_refaz_a_geometria(self):
        self.ctl.ativar()
        p = self.ctl.painel
        p.novo()
        p._definir_modo(G.ROTA)
        p._definir_norte(G.NM)
        self.ctl.clique_no_mapa(-47.8, -15.75)
        self._digitar(0, 0, '45')
        self._digitar(0, 1, '1500')
        lyr, ids = self.ctl.criar(p.estado_publico())
        fid = [f.id() for f in lyr.getFeatures("\"ebgeo_id\" = '{}'".format(ids[0]))][0]
        self.ctl._camada_mudou(lyr)
        lyr.selectByIds([fid])
        _app.processEvents()
        self.assertEqual(p.modo, 'editar')
        self.assertEqual(p.tab_nortes.rowCount(), 1)
        self.assertEqual([p.tab_nortes.horizontalHeaderItem(i).text() for i in range(5)],
                         ['Perna', 'NV', 'NQ', 'NM', 'Distância'])
        self.assertEqual(p.tab_nortes.item(0, 3).text(), '45,00°')
        _a, geo_antes = self._ler_ogr('line', "ebgeo_id = '{}'".format(ids[0]))[0]
        # muda a distância, acrescenta uma perna e passa a digitar em NV
        self._digitar(0, 1, '2000')
        self._digitar(1, 0, '90')
        self._digitar(1, 1, '500')
        p._definir_norte(G.NV)
        foto_painel(p, 'az_painel_edicao.png')
        self.assertTrue(self.ctl.salvar(p.estado_publico()))
        attrs, geo = self._ler_ogr('line', "ebgeo_id = '{}'".format(ids[0]))[0]
        polar = json.loads(attrs['azimute_distancia'])
        self.assertEqual(polar['northReference'], 'true')
        self.assertEqual([l['distance'] for l in polar['legs']], [2000, 500])
        vert = G.vertices_da_construcao(polar)
        self.assertLess(max_desvio(geo['coordinates'], G.gerar_geometria(vert, G.ROTA)['coordinates']), 1e-6)
        self.assertNotEqual(geo['coordinates'], geo_antes['coordinates'])
        self.assertEqual(json.loads(attrs['props'])['azimuthDistanceData'], polar)
        self.assertEqual(json.loads(attrs['props'])['baseCoordinates'], vert)

    def test_edita_pontos_acrescenta_e_remove(self):
        self.ctl.ativar()
        p = self.ctl.painel
        p.novo()
        p._definir_modo(G.PONTO)
        p._definir_norte(G.NV)
        self.ctl.clique_no_mapa(-47.79, -15.74)
        self._digitar(0, 0, '10')
        self._digitar(0, 1, '700')
        lyr, ids = self.ctl.criar(p.estado_publico())
        self.assertEqual(len(ids), 2)
        f = next(lyr.getFeatures("\"ebgeo_id\" = '{}'".format(ids[1])))
        self.assertTrue(self.ctl._abrir_edicao(lyr, f.id()))
        self._digitar(1, 0, '200')
        self._digitar(1, 1, '300')
        self.assertTrue(self.ctl.salvar(p.estado_publico()))
        conj = gravacao.conjunto_de_pontos(lyr, next(lyr.getFeatures("\"ebgeo_id\" = '{}'".format(ids[0]))))
        self.assertEqual(sorted(conj), [0, 1, 2])
        # remove a perna 2: o terceiro ponto sai
        f = conj[1]
        self.ctl._abrir_edicao(lyr, f.id())
        p.tab_pernas.setCurrentCell(1, 0)
        p._remover_perna()
        self.assertTrue(self.ctl.salvar(p.estado_publico()))
        conj = gravacao.conjunto_de_pontos(lyr, next(lyr.getFeatures("\"ebgeo_id\" = '{}'".format(ids[0]))))
        self.assertEqual(sorted(conj), [0, 1])
        pontos = self._ler_ogr('point')
        doc = [a for a, _ in pontos if json.loads(a['azimute_distancia'] or 'null') and
               json.loads(a['azimute_distancia'])['referencePoint'] == [-47.79, -15.74]]
        self.assertEqual(len(doc), 2)


class TesteCalcoAntigo(unittest.TestCase):
    def test_calco_antigo_ganha_a_coluna_e_reabre_com_a_tabela(self):
        """Calco com a tabela line sem azimute_distancia: a coluna entra e a construção é gravada."""
        from Calco import gpkg
        cam = os.path.join(tempfile.mkdtemp(prefix='ebgeo_az_velho_'), 'velho.gpkg')
        c = Calco(cam)
        c.criar()
        gpkg.criar_calco(cam, ['line'], apoio=False)
        ds = ogr.Open(cam, 1)
        ds.ExecuteSQL('ALTER TABLE line DROP COLUMN azimute_distancia')
        ds = None
        c.carregar(estilizar_novas=False)
        definir_calco_ativo(c)
        lyr = c.camadas_no_projeto().get('line')
        self.assertIsNotNone(lyr)  # o calco reaberto carrega a tabela do Azimute e Distância
        self.assertLess(lyr.fields().indexOf('azimute_distancia'), 0)
        estado = {'referencePoint': [-47.8, -15.75], 'outputMode': G.ROTA, 'angularUnit': G.GRAUS,
                  'distanceUnit': G.METROS, 'northReference': G.NV, 'magneticDeclination': -22.0,
                  'meridianConvergence': 0.76, 'legs': [{'azimuth': 45, 'distance': 1000}]}
        lyr2, ids = gravacao.criar(c, estado)
        self.assertIs(lyr2, lyr)
        ds = ogr.Open(cam)
        t = ds.GetLayerByName('line')
        t.SetAttributeFilter("ebgeo_id = '{}'".format(ids[0]))
        polar = json.loads(next(iter(t)).GetField('azimute_distancia'))
        ds = None
        self.assertEqual(polar['legs'], [{'azimuth': 45, 'distance': 1000, 'observation': ''}])


@unittest.skipUnless(os.path.exists(FIXTURE_30), 'fixture 06 ausente')
class TesteImportado(unittest.TestCase):
    def setUp(self):
        from Calco.importador import escritor
        self.gpkg = os.path.join(tempfile.mkdtemp(prefix='ebgeo_az_imp_'), 'importado.gpkg')
        escritor.importar(FIXTURE_30, self.gpkg)

    def test_importador_guarda_a_construcao_na_coluna(self):
        esperado = {ft['properties']['id']: ft['properties']['azimuthDistanceData'] for _n, _b, ft in feicoes_azimute_fixture()}
        ds = ogr.Open(self.gpkg)
        achados = {}
        for tabela in ('point', 'line', 'polygon'):
            lyr = ds.GetLayerByName(tabela)
            self.assertGreaterEqual(lyr.GetLayerDefn().GetFieldIndex('azimute_distancia'), 0, tabela)
            lyr.SetAttributeFilter('azimute_distancia IS NOT NULL')
            for f in lyr:
                achados[f.GetField('ebgeo_id')] = json.loads(f.GetField('azimute_distancia'))
        ds = None
        self.assertEqual(achados, esperado)

    def test_ferramenta_edita_a_feicao_importada(self):
        iface = get_iface()
        iface.mainWindow().show()
        lyr = QgsVectorLayer('{}|layername=line'.format(self.gpkg), 'Linha', 'ogr')
        self.assertTrue(lyr.isValid())
        QgsProject.instance().addMapLayer(lyr)
        definir_calco_ativo(Calco(self.gpkg))
        ctl = AzimuteDistancia(iface)
        f = next(lyr.getFeatures("\"nome\" = 'Rota polar em milésimos e km'"))
        ctl._camada_mudou(lyr)
        lyr.selectByIds([f.id()])
        self.assertTrue(ctl.ativar())
        p = ctl.painel
        self.assertEqual(p.modo, 'editar')
        self.assertEqual(p.estado['angularUnit'], G.MILESIMOS)
        self.assertEqual(p.estado['northReference'], G.NM)
        self.assertEqual(p.estado['magneticDeclination'], -21.5)
        # NM digitado 800 milésimos (45°), declinação -21,5: NV 23,5° = 418 ₥
        self.assertEqual(p.tab_nortes.item(0, 3).text(), '800₥')
        self.assertEqual(p.tab_nortes.item(0, 1).text(), G.texto_angulo(23.5, G.MILESIMOS))
        self.assertEqual(p.tab_nortes.item(0, 4).text(), '1,50 km')
        foto_painel(p, 'az_painel_importado.png')
        p.tab_pernas.item(2, 1).setText('1,2')
        self.assertTrue(ctl.salvar(p.estado_publico()))
        ds = ogr.Open(self.gpkg)
        t = ds.GetLayerByName('line')
        t.SetAttributeFilter("nome = 'Rota polar em milésimos e km'")
        g = next(iter(t))
        polar = json.loads(g.GetField('azimute_distancia'))
        coords = json.loads(g.GetGeometryRef().ExportToJson())['coordinates']
        ds = None
        self.assertEqual(polar['legs'][2]['distance'], 1.2)
        self.assertEqual(polar['angularUnit'], 'mils')
        vert = G.vertices_da_construcao(polar)
        self.assertLess(max_desvio(coords, G.gerar_geometria(vert, G.ROTA)['coordinates']), 1e-6)
        ctl.unload()
        QgsProject.instance().removeMapLayer(lyr.id())


class TestePlugin(unittest.TestCase):
    def test_modulo_antigo_saiu(self):
        self.assertFalse(os.path.exists(os.path.join(PASTA_EBGEO, 'AzimuthDistance')))
        for raiz, _d, arquivos in os.walk(PASTA_EBGEO):
            if '__pycache__' in raiz:
                continue
            for a in arquivos:
                if os.path.join(raiz, a) == os.path.abspath(__file__):
                    continue
                if a.endswith(('.py', '.qrc', '.ui', '.txt')):
                    with open(os.path.join(raiz, a), encoding='utf-8', errors='replace') as fh:
                        texto = fh.read()
                    self.assertNotIn('AzimuthDistance', texto, a)
                    self.assertNotIn('azimuthTool', texto, a)

    def test_acao_do_menu_abre_a_ferramenta(self):
        """Instancia o plugin inteiro com iface simulado e aciona a ação nova uma vez."""
        from qgis.PyQt.QtWidgets import QMenu, QToolBar
        import qgis.utils
        iface = get_iface()
        iface.firstRightStandardMenu.return_value = QMenu()
        iface.addToolBar.side_effect = lambda nome: QToolBar(nome)
        iface.mainWindow().show()
        qgis.utils.iface = iface
        sys.path.append(os.path.join(QgsApplication.prefixPath(), 'python', 'plugins'))  # processing
        from processing.core.Processing import Processing
        Processing.initialize()
        sys.path.insert(0, RAIZ_REPO)
        from EBGeo.ebgeo import EBGeo
        plugin = EBGeo(iface)
        plugin.initGui()
        acoes = [a for a in plugin.ebGeo.actions() if a.text() == 'Azimute e Distância']
        self.assertEqual(len(acoes), 1)
        self.assertFalse(acoes[0].icon().isNull())
        self.assertNotIn('Criação de pontos por azimute e distância', [a.text() for a in plugin.ebGeo.actions()])
        caminho = os.path.join(tempfile.mkdtemp(), 'calco_plugin.gpkg')
        c = Calco(caminho)
        c.criar()
        c.carregar(estilizar_novas=False)
        definir_calco_ativo(c)
        acoes[0].trigger()
        # o plugin importa o pacote como EBGeo.Calco (o teste, como Calco): compara pelo módulo
        ferramenta = iface.mapCanvas().mapTool()
        self.assertEqual(type(ferramenta).__name__, 'FerramentaAzimute')
        self.assertTrue(type(ferramenta).__module__.endswith('Calco.azimute.ferramenta'))
        self.assertTrue(acoes[0].isChecked())
        self.assertTrue(plugin.azimuteDistancia.painel.isVisible())
        self.assertEqual(plugin.azimuteDistancia.painel.windowTitle(), 'Azimute e Distância')
        foto_painel(plugin.azimuteDistancia.painel, 'az_painel_plugin.png')
        plugin.unload()
        self.assertIsNone(plugin.azimuteDistancia.painel)
        QgsProject.instance().removeAllMapLayers()


class TesteImagem(_Base):
    def test_render_do_calco(self):
        """Rota, área e pontos gravados, renderizados pelo QgsMapRendererParallelJob."""
        self.ctl.ativar()
        p = self.ctl.painel
        for modo, ponto, pernas in ((G.ROTA, (-47.83, -15.78), [('45', '3000'), ('120', '2500'), ('30', '2000')]),
                                    (G.AREA, (-47.80, -15.74), [('0', '2000'), ('90', '2500'), ('180', '2000')]),
                                    (G.PONTO, (-47.78, -15.775), [('60', '2000'), ('150', '1500')])):
            p.novo()
            p._definir_modo(modo)
            p._definir_norte(G.NV)
            self.ctl.clique_no_mapa(*ponto)
            for i, (az, d) in enumerate(pernas):
                self._digitar(i, 0, az)
                self._digitar(i, 1, d)
            self.ctl.criar(p.estado_publico())
        from Calco.calco import aplicar_estilo
        camadas = []
        for tipo in ('polygon', 'line', 'point'):
            lyr = self.calco.camada(tipo)
            aplicar_estilo(lyr, tipo)
            lyr.removeSelection()  # a feição recém-criada fica selecionada (amarela)
            camadas.append(lyr)
        ms = QgsMapSettings()
        ms.setLayers(camadas)
        ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        ms.setExtent(QgsRectangle(-47.85, -15.80, -47.72, -15.70))
        ms.setOutputSize(QSize(900, 700))
        ms.setBackgroundColor(QColor(255, 255, 255))
        job = QgsMapRendererParallelJob(ms)
        job.start()
        job.waitForFinished()
        img = job.renderedImage()
        img.save(os.path.join(IMAGENS, 'az_render_calco.png'))
        def verde(c):
            return c.green() - c.red() > 40 and c.green() - c.blue() > 30
        verdes = sum(1 for x in range(0, img.width(), 3) for y in range(0, img.height(), 3)
                     if verde(img.pixelColor(x, y)))
        amarelos = sum(1 for x in range(0, img.width(), 3) for y in range(0, img.height(), 3)
                       if img.pixelColor(x, y).red() > 200 and img.pixelColor(x, y).green() > 200
                       and img.pixelColor(x, y).blue() < 60)
        print('\n  render: {} pixels verdes, {} amarelos (amostra 1:9)'.format(verdes, amarelos))
        self.assertGreater(verdes, 1000)
        self.assertEqual(amarelos, 0)
        print('\n  imagens em', IMAGENS)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
