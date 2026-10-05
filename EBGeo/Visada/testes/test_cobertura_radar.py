# -*- coding: utf-8 -*-
"""
Cobertura de radar ou sensor para alvo em altitude fixa (item F2).

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/Visada/testes/test_cobertura_radar.py

EBGEO_IMAGENS (pasta) guarda os PNGs de conferência; sem ela, vão para uma pasta temporária.

O que cada classe prova:
    TestAnalitico     Terra lisa: o alcance no horizonte bate com d ~ 4,12 (sqrt(h) + sqrt(H)) km
                      (k = 0,25); o alcance máximo corta; altitude acima do mar equivale à acima do
                      terreno; morro faz sombra (contra a referência analítica); dois sensores somam;
                      o k de rádio chega ao GDAL;
    TestAlgoritmo     o algoritmo de Processing: saídas raster e polígonos, campos por sensor,
                      sensor fora do MDE, estilo das saídas e execução em segundo plano sem
                      congelar o laço de eventos;
    TestPlugin        a ação do menu existe, tem ícone e abre o diálogo do algoritmo;
    TestImagens       PNGs renderizados no QGIS para conferência visual.
"""
import math
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', ''), 'Fonts'))
AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(os.path.dirname(AQUI))      # .../EBGeo
RAIZ_REPO = os.path.dirname(PACOTE)
for p in (RAIZ_REPO, AQUI):
    if p not in sys.path:
        sys.path.insert(0, p)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsGeometry, QgsHillshadeRenderer,
    QgsMapRendererParallelJob, QgsMapSettings, QgsMarkerSymbol, QgsPointXY, QgsProcessingAlgRunnerTask,
    QgsProcessingContext, QgsProcessingException, QgsProcessingFeedback, QgsProject, QgsRasterLayer,
    QgsRectangle, QgsSingleSymbolRenderer, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType, QSize, QTimer  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()
# o iface simulado antes do Processing (o get_iface reinicia o registro de provedores) e antes de
# importar o plugin (o ebgeo.py lê o iface do qgis.utils ao carregar)
from qgis.testing.mocked import get_iface  # noqa: E402
import qgis.utils  # noqa: E402
IFACE = get_iface()
qgis.utils.iface = IFACE
sys.path.append(os.path.join(QgsApplication.prefixPath(), 'python', 'plugins'))
from processing.core.Processing import Processing  # noqa: E402
Processing.initialize()
import processing  # noqa: E402

import numpy as np  # noqa: E402
from osgeo import gdal  # noqa: E402

import sintetico as S  # noqa: E402
from EBGeo.Visada import nucleo, refracao  # noqa: E402
from EBGeo.Visada.refracao import K_RADAR  # noqa: E402
from EBGeo.Processings.provider import Provider  # noqa: E402

gdal.UseExceptions()
PROVEDOR = Provider()
QgsApplication.processingRegistry().addProvider(PROVEDOR)
ALG = 'EBGeoProvider:coberturaradar'
TMP = tempfile.mkdtemp(prefix='ebgeo_radar_')
IMAGENS = S.pasta_imagens()
EPSG = 'EPSG:31983'
MEDIDAS = []


def grade(n, res):
    """Centro da grade n x n (centro da célula do meio)."""
    return S.X0 + (n // 2 + 0.5) * res, S.Y0 - (n // 2 + 0.5) * res


def mde(fun, nome, n, res):
    cx, cy = S.centros(n, n, res)
    return S.gravar_mde(os.path.join(TMP, nome + '.tif'), fun(cx, cy), res)


def raio_equivalente(m, res):
    return math.sqrt((m > 0).sum() * res * res / math.pi)


def formula_horizonte_km(h, H):
    return 4.12 * (math.sqrt(h) + math.sqrt(H))


def camada_sensores(pontos, campos=None, crs=EPSG, nome='Sensores'):
    lyr = QgsVectorLayer('Point?crs={}'.format(crs), nome, 'memory')
    attrs = [QgsField('altura', QMetaType.Type.Double), QgsField('alcance_km', QMetaType.Type.Double)]
    lyr.dataProvider().addAttributes(attrs)
    lyr.updateFields()
    feats = []
    for i, (x, y) in enumerate(pontos):
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        if campos:
            f['altura'], f['alcance_km'] = campos[i]
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    return lyr


class Gravador:
    def __init__(self):
        self.ccs = []
        self._orig = gdal.ViewshedGenerate

    def __enter__(self):
        def envolto(*args, **kw):
            self.ccs.append(round(args[12], 9))
            return self._orig(*args, **kw)
        gdal.ViewshedGenerate = envolto
        return self

    def __exit__(self, *exc):
        gdal.ViewshedGenerate = self._orig
        return False


class TestAnalitico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res, cls.n = 250.0, 1301          # 325 km de lado, Terra lisa ao nível do mar
        cls.plano = mde(S.plano(0.0), 'plano0', cls.n, cls.res)
        cls.c = grade(cls.n, cls.res)

    def _horizonte(self, h, H):
        r = nucleo.cobertura(self.plano, [(self.c[0], self.c[1], h, 300000.0)], H, 'terreno')
        m = r.matriz
        gt = r.grade.gt
        lin, col = int((self.c[1] - gt[3]) / gt[5]), int((self.c[0] - gt[0]) / gt[1])
        eixos = [np.where(p > 0)[0].max() * self.res / 1000 for p in
                 (m[lin, col:], m[lin, col::-1], m[lin:, col], m[lin::-1, col])]
        req = raio_equivalente(m, self.res) / 1000
        formula = formula_horizonte_km(h, H)
        exato = (refracao.horizonte(h, K_RADAR, S.R_GDAL) + refracao.horizonte(H, K_RADAR, S.R_GDAL)) / 1000
        MEDIDAS.append('Terra lisa, antena {} m, alvo {} m: raio da área coberta {:.2f} km, nos eixos {} km; '
                       '4,12(√h+√H) = {:.2f} km; exato com R = 6.378.137 m: {:.2f} km ({:+.2f} %)'.format(
                           h, H, req, [round(e, 2) for e in eixos], formula, exato, 100 * (req / formula - 1)))
        self.assertLess(abs(req / formula - 1), 0.01)
        for e in eixos:
            self.assertLess(abs(e - exato), 2 * self.res / 1000)

    def test_horizonte_de_radio_antena_30_alvo_1000(self):
        self._horizonte(30.0, 1000.0)

    def test_horizonte_de_radio_antena_10_alvo_100(self):
        self._horizonte(10.0, 100.0)

    def test_horizonte_reprova_k_optico(self):
        """A régua distingue o k: com o k óptico (1/7) o raio cai mais de 5 % abaixo da fórmula."""
        r = nucleo.cobertura(self.plano, [(self.c[0], self.c[1], 30.0, 300000.0)], 1000.0, 'terreno',
                             k=refracao.K_OPTICO)
        req = raio_equivalente(r.matriz, self.res) / 1000
        self.assertGreater(abs(req / formula_horizonte_km(30, 1000) - 1), 0.05)

    def test_alcance_maximo_corta(self):
        r = nucleo.cobertura(self.plano, [(self.c[0], self.c[1], 30.0, 50000.0)], 1000.0, 'terreno')
        req = raio_equivalente(r.matriz, self.res)
        self.assertLess(abs(req / 50000.0 - 1), 0.01)

    def test_altitude_acima_do_mar_equivale_a_acima_do_terreno(self):
        res, n = 250.0, 601
        alto = mde(S.plano(500.0), 'plano500', n, res)
        c = grade(n, res)
        agl = nucleo.cobertura(alto, [(c[0], c[1], 30.0, 70000.0)], 1000.0, 'terreno')
        msl = nucleo.cobertura(alto, [(c[0], c[1], 30.0, 70000.0)], 1500.0, 'mar')
        self.assertEqual(float(np.mean(agl.matriz == msl.matriz)), 1.0)
        abaixo = nucleo.cobertura(alto, [(c[0], c[1], 30.0, 70000.0)], 400.0, 'mar')
        self.assertEqual(int((abaixo.matriz > 0).sum()), 0)

    def test_morro_faz_sombra(self):
        res, n = 100.0, 601
        c = grade(n, res)
        morro = S.gaussiana(c[0] + 15000, c[1], 600.0, 1500.0, base=50.0)
        caminho = mde(morro, 'morro_radar', n, res)
        h, H, alcance = 10.0, 150.0, 28000.0
        r = nucleo.cobertura(caminho, [(c[0], c[1], h, alcance)], H, 'terreno')
        gx, gy = r.grade.centros()
        dentro = np.hypot(gx - c[0], gy - c[1]) <= alcance - res
        minima = S.altura_minima(morro, c[0], c[1], h, gx[dentro], gy[dentro], K_RADAR)
        ref = minima <= H
        p = 100 * float(np.mean((r.matriz[dentro] > 0) == ref))
        MEDIDAS.append('morro de 600 m a 15 km, antena 10 m, alvo a 150 m do terreno: {:.2f} % de {} células '
                       'iguais à referência analítica; sombra de {:.0f} km²'.format(
                           p, int(dentro.sum()), (~ref).sum() * res * res / 1e6))
        self.assertGreater(p, 99.0)
        gt = r.grade.gt

        def valor(x, y):
            return r.matriz[int((y - gt[3]) / gt[5]), int((x - gt[0]) / gt[1])]
        self.assertEqual(valor(c[0] + 25000, c[1]), 0)      # atrás do morro
        self.assertEqual(valor(c[0] - 25000, c[1]), 1)      # mesma distância, do outro lado
        alto = nucleo.cobertura(caminho, [(c[0], c[1], h, alcance)], 2000.0, 'terreno')
        self.assertEqual(int(alto.matriz[dentro].min()), 1)  # alvo alto: tudo coberto

    def test_dois_sensores_somam(self):
        d = 100000.0
        s1 = (self.c[0] - d / 2, self.c[1], 30.0, 300000.0)
        s2 = (self.c[0] + d / 2, self.c[1], 30.0, 300000.0)
        H = 300.0
        r = nucleo.cobertura(self.plano, [s1, s2], H, 'terreno')
        rh = refracao.horizonte(30.0, K_RADAR, S.R_GDAL) + refracao.horizonte(H, K_RADAR, S.R_GDAL)
        gx, gy = r.grade.centros()
        esperado = ((np.hypot(gx - s1[0], gy - s1[1]) <= rh).astype(int)
                    + (np.hypot(gx - s2[0], gy - s2[1]) <= rh).astype(int))
        p = 100 * float(np.mean(r.matriz == esperado))
        MEDIDAS.append('dois sensores a 100 km, alvo a 300 m: {:.2f} % das {} células iguais aos dois discos '
                       'analíticos; contagens {}'.format(p, r.matriz.size, sorted(set(np.unique(r.matriz)))))
        self.assertGreater(p, 99.5)
        self.assertEqual(set(np.unique(r.matriz)), {0, 1, 2})

    def test_k_de_radio_chega_ao_gdal(self):
        with Gravador() as g:
            nucleo.cobertura(self.plano, [(self.c[0], self.c[1], 30.0, 20000.0)], 100.0)
        self.assertEqual(g.ccs, [0.75])

    def test_sensor_fora_do_mde(self):
        with self.assertRaises(nucleo.ErroVisada) as e:
            nucleo.cobertura(self.plano, [(self.c[0], self.c[1], 30, 1000), (0.0, 0.0, 30, 1000)], 100.0)
        self.assertIn('Sensor 2 está fora do MDE', str(e.exception))


class TestAlgoritmo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res, cls.n = 100.0, 401
        cls.c = grade(cls.n, cls.res)
        cls.fun = S.gaussiana(cls.c[0] + 6000, cls.c[1], 400.0, 1000.0, base=80.0)
        cls.mde = mde(cls.fun, 'alg', cls.n, cls.res)

    def _rodar(self, sensores, **extra):
        p = {'MDE': self.mde, 'SENSORES': sensores, 'ALTURA_ANTENA': 10.0, 'ALCANCE': 15.0,
             'ALTITUDE_ALVO': 150.0, 'REFERENCIA': 0, 'RESOLUCAO': 0,
             'SAIDA_RASTER': 'TEMPORARY_OUTPUT', 'SAIDA_POLIGONOS': 'TEMPORARY_OUTPUT'}
        p.update(extra)
        return processing.run(ALG, p)

    def test_saidas_raster_e_poligonos_coerentes(self):
        s = camada_sensores([self.c, (self.c[0], self.c[1] + 8000)])
        res = self._rodar(s)
        ds = gdal.Open(res['SAIDA_RASTER'])
        m = ds.GetRasterBand(1).ReadAsArray()
        self.assertEqual(ds.GetRasterBand(1).GetNoDataValue(), nucleo.SEM_DADO_CONTAGEM)
        self.assertEqual(set(np.unique(m)), {0, 1, 2})
        pol = QgsVectorLayer(res['SAIDA_POLIGONOS'], 'p', 'ogr')
        self.assertIn('sensores', pol.fields().names())
        self.assertEqual(sorted(pol.uniqueValues(pol.fields().indexOf('sensores'))), [1, 2])
        area_pol = sum(f.geometry().area() for f in pol.getFeatures())
        area_ras = float((m > 0).sum() * self.res * self.res)
        self.assertAlmostEqual(area_pol / area_ras, 1.0, places=6)
        self.assertAlmostEqual(res['AREA_COBERTA_KM2'], area_ras / 1e6, places=6)
        self.assertEqual(res['MAXIMO_SENSORES'], 2)

    def test_campos_por_sensor(self):
        s = camada_sensores([self.c, (self.c[0] - 10000, self.c[1])], campos=[(10.0, 3.0), (10.0, 6.0)])
        res = self._rodar(s, CAMPO_ALTURA='altura', CAMPO_ALCANCE='alcance_km', ALTITUDE_ALVO=2000.0)
        m = gdal.Open(res['SAIDA_RASTER']).ReadAsArray()
        area = (m > 0).sum() * self.res * self.res
        esperado = math.pi * (3000 ** 2 + 6000 ** 2)      # alvo alto: os dois discos inteiros, sem sobrepor
        self.assertLess(abs(area / esperado - 1), 0.02)

    def test_sensor_fora_do_mde(self):
        s = camada_sensores([(self.c[0] + 500000, self.c[1])])
        with self.assertRaises(QgsProcessingException) as e:
            self._rodar(s)
        self.assertIn('fora do MDE', str(e.exception))

    def test_estilo_das_saidas(self):
        """O pós-processador estiliza ao carregar: paleta no raster, categorias nos polígonos."""
        s = camada_sensores([self.c, (self.c[0], self.c[1] + 8000)])
        QgsProject.instance().addMapLayer(s)
        res = processing.runAndLoadResults(ALG, {
            'MDE': self.mde, 'SENSORES': s, 'ALTURA_ANTENA': 10.0, 'ALCANCE': 15.0, 'ALTITUDE_ALVO': 150.0,
            'REFERENCIA': 0, 'RESOLUCAO': 0, 'SAIDA_RASTER': 'TEMPORARY_OUTPUT',
            'SAIDA_POLIGONOS': 'TEMPORARY_OUTPUT'})
        self.assertIn('SAIDA_RASTER', res)
        nome = 'Cobertura de radar, alvo a 150 m acima do terreno'
        ras = (QgsProject.instance().mapLayersByName(nome + ' (sensores por célula)') or [None])[0]
        pol = (QgsProject.instance().mapLayersByName(nome) or [None])[0]
        self.assertIsNotNone(ras)
        self.assertIsNotNone(pol)
        self.assertEqual(ras.renderer().type(), 'paletted')
        rotulos = [c.label for c in ras.renderer().classes()]
        self.assertEqual(rotulos, ['Sem cobertura', '1 sensor', '2 sensores'])
        self.assertEqual(pol.renderer().type(), 'categorizedSymbol')
        self.assertEqual([c.label() for c in pol.renderer().categories()], ['1 sensor', '2 sensores'])
        self.assertIn('alvo a 150 m acima do terreno', pol.name())

    def test_roda_em_segundo_plano_sem_congelar(self):
        """Pelo gerenciador de tarefas (como o diálogo do Processing): o cálculo roda noutro fio e o laço
        de eventos da interface continua girando enquanto ele corre."""
        res, n = 50.0, 1601
        caminho = mde(S.gaussiana(*grade(n, res), 300.0, 4000.0, base=50.0), 'pesado', n, res)
        c = grade(n, res)
        s = camada_sensores([(c[0] + dx, c[1] + dy) for dx in (-15000, 0, 15000) for dy in (-15000, 0, 15000)])
        fios = []
        orig = nucleo.cobertura

        def espia(*a, **kw):
            fios.append(threading.get_ident())
            return orig(*a, **kw)
        alg = QgsApplication.processingRegistry().createAlgorithmById(ALG)
        self.assertIsNotNone(alg, 'algoritmo {} não registrado'.format(ALG))
        ctx = QgsProcessingContext()
        ctx.setProject(QgsProject.instance())
        erros = []

        class Retorno(QgsProcessingFeedback):
            def reportError(self, erro, fatal=False):
                erros.append(erro)

            def pushWarning(self, aviso):
                erros.append(aviso)
        fb = Retorno()
        params = {'MDE': caminho, 'SENSORES': s, 'ALTURA_ANTENA': 15.0, 'ALCANCE': 25.0, 'ALTITUDE_ALVO': 100.0,
                  'REFERENCIA': 0, 'RESOLUCAO': 0, 'SAIDA_RASTER': os.path.join(TMP, 'pesado_cobertura.tif'),
                  'SAIDA_POLIGONOS': os.path.join(TMP, 'pesado_cobertura.gpkg')}
        tarefa = QgsProcessingAlgRunnerTask(alg, params, ctx, fb)
        fim = []
        tarefa.executed.connect(lambda ok, r: fim.append((ok, r)))
        batidas = []
        relogio = QTimer()
        relogio.timeout.connect(lambda: batidas.append(time.perf_counter()))
        relogio.start(20)
        t0 = time.perf_counter()
        with mock.patch.object(nucleo, 'cobertura', espia):
            QgsApplication.taskManager().addTask(tarefa)
            while not fim and time.perf_counter() - t0 < 300:
                QgsApplication.processEvents()
                time.sleep(0.005)
        relogio.stop()
        duracao = time.perf_counter() - t0
        self.assertTrue(fim and fim[0][0], (fim, erros))
        self.assertNotEqual(fios[0], threading.get_ident())
        maior_vao = max(np.diff(batidas)) if len(batidas) > 1 else duracao
        MEDIDAS.append('segundo plano: 9 sensores em {} x {} células, {:.2f} s; {} batidas do relógio de 20 ms '
                       'na interface, maior vão {:.0f} ms'.format(n, n, duracao, len(batidas), 1000 * maior_vao))
        self.assertGreater(len(batidas), duracao / 0.02 * 0.5)
        self.assertLess(maior_vao, 0.5)


class TestPlugin(unittest.TestCase):
    def test_acao_do_menu_abre_o_algoritmo(self):
        from qgis.PyQt.QtWidgets import QMenu, QToolBar
        IFACE.firstRightStandardMenu.return_value = QMenu()
        IFACE.addToolBar.side_effect = lambda nome: QToolBar(nome)
        from EBGeo.ebgeo import EBGeo
        plugin = EBGeo(IFACE)
        plugin.initGui()
        acoes = [a for a in plugin.ebGeo.actions() if a.text() == 'Cobertura de radar ou sensor']
        self.assertEqual(len(acoes), 1)
        self.assertFalse(acoes[0].icon().isNull())
        nomes = [a.text() for a in plugin.ebGeo.actions()]
        self.assertEqual(nomes.index('Cobertura de radar ou sensor'), nomes.index('Análise de Visibilidade') + 1)
        from qgis import processing as qp
        abertos = []
        with mock.patch.object(qp, 'execAlgorithmDialog', side_effect=lambda i, *a: abertos.append(i)):
            acoes[0].trigger()
        self.assertEqual(abertos, [ALG])
        # o diálogo de verdade se monta (sem exec, que bloquearia) e vai para PNG; o iface simulado
        # precisa de um modelo do navegador de verdade para o painel de parâmetros
        from qgis.gui import QgsBrowserGuiModel
        modelo = QgsBrowserGuiModel()
        IFACE.browserModel.return_value = modelo
        IFACE.activeLayer.return_value = None
        dlg = qp.createAlgorithmDialog(ALG, {})
        self.assertIsNotNone(dlg)
        dlg.resize(900, 820)
        dlg.show()
        _APP.processEvents()
        dlg.grab().save(os.path.join(IMAGENS, 'radar_dialogo.png'))
        dlg.close()


def relevo(caminho):
    lyr = QgsRasterLayer(caminho, 'MDE')
    sombra = QgsHillshadeRenderer(lyr.dataProvider(), 1, 315, 45)
    sombra.setZFactor(4)
    lyr.setRenderer(sombra)
    return lyr


def render(camadas, nome, extensao, tamanho=(900, 900)):
    ms = QgsMapSettings()
    ms.setLayers(camadas)
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(EPSG))
    ms.setExtent(extensao)
    ms.setOutputSize(QSize(*tamanho))
    ms.setBackgroundColor(QColor(255, 255, 255))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    img.save(os.path.join(IMAGENS, nome))
    return img


class TestImagens(unittest.TestCase):
    def test_cenario_tres_sensores(self):
        from EBGeo.Visada.cobertura_radar import estilizar_poligonos, estilizar_raster
        res, n = 100.0, 801
        c = grade(n, res)
        morros = [S.gaussiana(c[0] + dx, c[1] + dy, a, sg) for dx, dy, a, sg in (
            (8000, 5000, 500, 2500), (-12000, -9000, 650, 3000), (15000, -14000, 400, 2000),
            (-5000, 16000, 450, 3500), (0, -2000, 250, 1200))]
        caminho = mde(lambda x, y: 150 + sum(f(x, y) for f in morros), 'cenario', n, res)
        sensores = camada_sensores([(c[0] - 6000, c[1] + 3000), (c[0] + 12000, c[1] + 12000),
                                    (c[0] + 3000, c[1] - 16000)])
        for alt, ref, nome in ((150.0, 0, 'radar_cenario_150m_terreno.png'), (900.0, 1, 'radar_cenario_900m_mar.png')):
            r = processing.run(ALG, {
                'MDE': caminho, 'SENSORES': sensores, 'ALTURA_ANTENA': 12.0, 'ALCANCE': 22.0,
                'ALTITUDE_ALVO': alt, 'REFERENCIA': ref, 'RESOLUCAO': 0,
                'SAIDA_RASTER': 'TEMPORARY_OUTPUT', 'SAIDA_POLIGONOS': 'TEMPORARY_OUTPUT'})
            ras = QgsRasterLayer(r['SAIDA_RASTER'], 'cobertura')
            estilizar_raster(ras)
            pol = QgsVectorLayer(r['SAIDA_POLIGONOS'], 'cobertura', 'ogr')
            estilizar_poligonos(pol)
            simb = QgsMarkerSymbol.createSimple({'name': 'triangle', 'color': '#c0392b', 'size': '5',
                                                 'outline_color': '#ffffff', 'outline_width': '0.6'})
            sensores.setRenderer(QgsSingleSymbolRenderer(simb))
            img = render([sensores, pol, ras, relevo(caminho)], nome,
                         QgsRectangle(c[0] - 40000, c[1] - 40000, c[0] + 40000, c[1] + 40000))
            azuis = sum(1 for x in range(0, img.width(), 6) for y in range(0, img.height(), 6)
                        if img.pixelColor(x, y).blue() - img.pixelColor(x, y).red() > 40)
            MEDIDAS.append('{}: {} pixels azulados (amostra 1:36), {:.1f} km² cobertos'.format(
                nome, azuis, r['AREA_COBERTA_KM2']))
            self.assertGreater(azuis, 500)

    def test_morro_sombra(self):
        from EBGeo.Visada.cobertura_radar import estilizar_poligonos
        res, n = 100.0, 601
        c = grade(n, res)
        caminho = mde(S.gaussiana(c[0] + 15000, c[1], 600.0, 1500.0, base=50.0), 'morro_img', n, res)
        sensores = camada_sensores([c])
        r = processing.run(ALG, {
            'MDE': caminho, 'SENSORES': sensores, 'ALTURA_ANTENA': 10.0, 'ALCANCE': 28.0, 'ALTITUDE_ALVO': 150.0,
            'REFERENCIA': 0, 'RESOLUCAO': 0, 'SAIDA_RASTER': 'TEMPORARY_OUTPUT',
            'SAIDA_POLIGONOS': 'TEMPORARY_OUTPUT'})
        pol = QgsVectorLayer(r['SAIDA_POLIGONOS'], 'cobertura', 'ogr')
        estilizar_poligonos(pol)
        render([sensores, pol, relevo(caminho)], 'radar_morro_sombra.png',
               QgsRectangle(c[0] - 30000, c[1] - 30000, c[0] + 30000, c[1] + 30000))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('\nMedidas:')
    for m in MEDIDAS:
        print('  ' + m)
    print('Imagens em', IMAGENS)
    sys.exit(0 if r.wasSuccessful() else 1)
