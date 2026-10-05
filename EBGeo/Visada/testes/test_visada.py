# -*- coding: utf-8 -*-
"""
Visibilidade sem GRASS (item F5) e coeficiente de refração único (item F6).

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/Visada/testes/test_visada.py

EBGEO_IMAGENS (pasta) guarda os PNGs de conferência; sem ela, vão para uma pasta temporária.

O que cada classe prova:
    TestRefracao       um k óptico e um k de rádio, com fonte, e nenhum número espalhado: a linha de
                       visada, o Mapa de visibilidade e a Análise por setor usam 1/7;
    TestMotor          o motor do GDAL contra a referência analítica (plano, morro gaussiano,
                       parede), a guarda de extensão e a reprojeção do MDE em graus;
    TestMapaVisibilidade  a ferramenta do painel, sem GRASS, em SRC métrico e em graus, observador
                       fora do MDE e coordenada digitada noutro SRC;
    TestAnaliseSetores a soma de observadores por setor, sem GRASS, contra a referência, com o MDE
                       em graus, e a saída no formato de antes (campo "value", estilo vermelho-verde);
    TestContraGrass    o r.viewshed do GRASS contra o motor novo (só roda com o GRASS configurado,
                       como no QGIS aberto pelo atalho, que define GISBASE);
    TestPlugin         as ações do menu abrem as ferramentas.
"""
import glob
import math
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(os.path.dirname(AQUI))      # .../EBGeo
RAIZ_REPO = os.path.dirname(PACOTE)
for p in (RAIZ_REPO, AQUI):
    if p not in sys.path:
        sys.path.insert(0, p)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsFeature, QgsField, QgsGeometry, QgsHillshadeRenderer,
    QgsMapRendererParallelJob, QgsMapSettings, QgsPointXY, QgsProject, QgsRasterLayer, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType, QSize  # noqa: E402
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

import numpy as np  # noqa: E402
import shapely  # noqa: E402
from osgeo import gdal, osr  # noqa: E402
from qgis.PyQt.QtWidgets import QMessageBox  # noqa: E402

import sintetico as S  # noqa: E402
from EBGeo.Visada import nucleo, refracao  # noqa: E402
from EBGeo.Visada.refracao import K_OPTICO, K_RADAR  # noqa: E402

gdal.UseExceptions()
TMP = tempfile.mkdtemp(prefix='ebgeo_visada_')
IMAGENS = S.pasta_imagens()
EPSG = 'EPSG:31983'
RES = 30.0
N = 241
H_OBS = 10.0
ALCANCE = 3000.0
C = (S.X0 + (N / 2) * RES, S.Y0 - (N / 2) * RES)      # centro da célula 120,120
MEDIDAS = []

MORRO = S.gaussiana(C[0] + 900, C[1] + 150, 120.0, 220.0, base=100.0)


def parede_fun(x, y):
    """Plano a 100 m com uma parede N-S de 60 m, 2 células de largura, 600 m a leste do centro."""
    z = np.full(np.broadcast(x, y).shape, 100.0)
    xp = C[0] + 600
    return np.where((np.asarray(x) >= xp) & (np.asarray(x) < xp + 2 * RES), 160.0, z)


def mde_de(fun, nome, n=N, res=RES):
    cx, cy = S.centros(n, n, res)
    return S.gravar_mde(os.path.join(TMP, nome + '.tif'), fun(cx, cy), res)


def mde_geografico(fun, nome, res_seg=1.0, margem=200.0):
    """O mesmo terreno analítico num MDE em graus (SIRGAS 2000, EPSG:4674), amostrado no UTM."""
    utm = osr.SpatialReference()
    utm.ImportFromEPSG(31983)
    utm.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    geo = osr.SpatialReference()
    geo.ImportFromEPSG(4674)
    geo.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    a_geo = osr.CoordinateTransformation(utm, geo)
    xs = [S.X0 + margem, S.X0 + N * RES - margem]
    ys = [S.Y0 - margem, S.Y0 - N * RES + margem]
    cantos = [a_geo.TransformPoint(x, y)[:2] for x in xs for y in ys]
    lon0, lon1 = min(c[0] for c in cantos), max(c[0] for c in cantos)
    lat0, lat1 = min(c[1] for c in cantos), max(c[1] for c in cantos)
    d = res_seg / 3600.0
    nx, ny = int((lon1 - lon0) / d), int((lat1 - lat0) / d)
    lon = lon0 + (np.arange(nx) + 0.5) * d
    lat = lat1 - (np.arange(ny) + 0.5) * d
    LON, LAT = np.meshgrid(lon, lat)
    para_utm = osr.CoordinateTransformation(geo, utm)
    pts = np.array(para_utm.TransformPoints(np.column_stack([LON.ravel(), LAT.ravel()]).tolist()))
    z = fun(pts[:, 0], pts[:, 1]).reshape(LON.shape)
    caminho = os.path.join(TMP, nome + '_geo.tif')
    return S.gravar_mde(caminho, z, d, x0=lon0, y0=lat1, epsg=4674)


def em_geografico(x, y):
    utm = QgsCoordinateReferenceSystem(EPSG)
    from qgis.core import QgsCoordinateTransform
    t = QgsCoordinateTransform(utm, QgsCoordinateReferenceSystem('EPSG:4674'), QgsProject.instance())
    return t.transform(QgsPointXY(x, y))


def ler_grade_de(caminho):
    ds = gdal.Open(caminho)
    return ds.GetRasterBand(1).ReadAsArray(), ds.GetGeoTransform(), ds.GetProjection()


def pct(a, b):
    return 100.0 * float(np.mean(a == b))


def setor(cx, cy, raio, ang0_graus, ang1_graus, segmentos=30):
    """O polígono que a ferramenta de setor desenha: centro, arco em sentido anti-horário, centro."""
    a0, a1 = math.radians(ang0_graus), math.radians(ang1_graus)
    pts = [QgsPointXY(cx, cy)]
    for i in range(segmentos + 1):
        a = a0 + (a1 - a0) * i / segmentos
        pts.append(QgsPointXY(cx + raio * math.cos(a), cy + raio * math.sin(a)))
    pts.append(QgsPointXY(cx, cy))
    return QgsGeometry.fromPolygonXY([pts])


SETORES = [  # (centro, raio, ângulos, altura do observador)
    ((C[0], C[1]), 1800.0, (-60, 60), 10.0),
    ((C[0], C[1] - 1200.0), 1800.0, (30, 150), 5.0),
]


def camada_setores(crs=EPSG):
    lyr = QgsVectorLayer('Polygon?crs={}'.format(crs), 'Setor de Visada', 'memory')
    lyr.dataProvider().addAttributes([QgsField('altura_obs', QMetaType.Type.Double)])
    lyr.updateFields()
    feats = []
    for (cx, cy), r, (a0, a1), h in SETORES:
        f = QgsFeature(lyr.fields())
        f.setGeometry(setor(cx, cy, r, a0, a1))
        f['altura_obs'] = h
        feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    QgsProject.instance().addMapLayer(lyr)
    return lyr


def referencia_setores(fun, cx_grade, cy_grade):
    """Contagem analítica por célula: observadores que a veem dentro do próprio setor."""
    cont = np.zeros(cx_grade.shape, dtype=int)
    uniao = np.zeros(cx_grade.shape, dtype=bool)
    for (ox, oy), r, (a0, a1), h in SETORES:
        poly = shapely.from_wkt(setor(ox, oy, r, a0, a1).asWkt())
        dentro = shapely.contains_xy(poly, cx_grade, cy_grade)
        vis = np.zeros(cx_grade.shape, dtype=bool)
        vis[dentro] = S.visivel(fun, ox, oy, h, cx_grade[dentro], cy_grade[dentro], K_OPTICO)
        cont += vis & dentro
        uniao |= dentro
    return cont, uniao


def rasterizar_value(caminho_gpkg, gt, largura, altura, wkt):
    ds = gdal.GetDriverByName('MEM').Create('', largura, altura, 1, gdal.GDT_Int32)
    ds.SetGeoTransform(gt)
    ds.SetProjection(wkt)
    ds.GetRasterBand(1).Fill(-1)
    v = gdal.OpenEx(caminho_gpkg, gdal.OF_VECTOR)
    gdal.RasterizeLayer(ds, [1], v.GetLayer(0), options=['ATTRIBUTE=value'])
    return ds.GetRasterBand(1).ReadAsArray()


def render(camadas, nome, extensao=None, crs=EPSG, tamanho=(800, 800)):
    ms = QgsMapSettings()
    ms.setLayers(camadas)
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setExtent(extensao or camadas[-1].extent())
    ms.setOutputSize(QSize(*tamanho))
    ms.setBackgroundColor(QColor(255, 255, 255))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    caminho = os.path.join(IMAGENS, nome)
    img.save(caminho)
    return img, caminho


def relevo(caminho, nome='MDE'):
    lyr = QgsRasterLayer(caminho, nome)
    sombra = QgsHillshadeRenderer(lyr.dataProvider(), 1, 315, 45)
    sombra.setZFactor(4)
    lyr.setRenderer(sombra)
    return lyr


class Gravador:
    """Envolve gdal.ViewshedGenerate e anota o coeficiente de curvatura de cada chamada."""

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


def mapa_visibilidade(caminho_mde, x, y, crs_ponto, saida, h=H_OBS, alcance=ALCANCE):
    """Aciona a ferramenta do painel "Mapa de visibilidade" como o operador (sem o clique)."""
    from EBGeo.Visibility.UI.interface_window import Interface
    mde = QgsRasterLayer(caminho_mde, 'MDT')
    QgsProject.instance().addMapLayer(mde)
    w = Interface(IFACE)
    w.layerCombo.setLayer(mde)
    w.outputFile.setFilePath(saida)
    w.heightSpinBox.setValue(h)
    w.rangeSpinBox.setValue(alcance)
    avisos = []
    with mock.patch.object(QMessageBox, 'warning', side_effect=lambda *a: avisos.append(a[-1])), \
            mock.patch.object(QMessageBox, 'critical', side_effect=lambda *a: avisos.append(a[-1])):
        w.doWork(QgsPointXY(x, y), QgsCoordinateReferenceSystem(crs_ponto))
    return avisos


def analise_setores(caminho_mde, setores_lyr):
    from EBGeo.VisibilityAnalysis.visibilityAnalysis import VisibilityAnalysis
    mde = QgsRasterLayer(caminho_mde, 'MDE')
    QgsProject.instance().addMapLayer(mde)
    va = VisibilityAnalysis(IFACE)
    avisos = []
    with mock.patch.object(QMessageBox, 'warning', side_effect=lambda *a: avisos.append(a[-1])):
        va.viewshedOfFeatTargetSector(setores_lyr, mde)
    saidas = QgsProject.instance().mapLayersByName('Vetor Resultante da Linha de Visada')
    return (saidas[-1] if saidas else None), avisos, mde


class TestRefracao(unittest.TestCase):
    def test_um_valor_optico_e_um_de_radio_com_fonte(self):
        self.assertEqual(K_OPTICO, 1.0 / 7.0)
        self.assertEqual(K_RADAR, 0.25)
        self.assertAlmostEqual(refracao.coeficiente_curvatura(K_RADAR), 0.75)
        doc = refracao.__doc__
        for fonte in ('gdal_viewshed', 'r.viewshed', 'ITU-R P.834'):
            self.assertIn(fonte, doc)

    def test_nenhum_coeficiente_espalhado_nas_ferramentas(self):
        """Nenhum número de refração escrito à mão fora de refracao.py (reprova 0.13 e 0.14286)."""
        arquivos = (glob.glob(os.path.join(PACOTE, 'Visibility', '**', '*.py'), recursive=True)
                    + glob.glob(os.path.join(PACOTE, 'VisibilityAnalysis', '*.py'))
                    + [os.path.join(PACOTE, 'Processings', 'lineOfSight.py')]
                    + [p for p in glob.glob(os.path.join(PACOTE, 'Visada', '*.py'))
                       if not p.endswith('refracao.py')])
        padrao = re.compile(r'''(?<![\d.'"])0\.(13|1428\d*|857\d*|75|25|325)(?!\d)|refraction_coeff|6371000''')
        achados = []
        for a in arquivos:
            with open(a, encoding='utf-8') as fh:
                for i, linha in enumerate(fh, 1):
                    if padrao.search(linha.split('#')[0]):
                        achados.append('{}:{}: {}'.format(os.path.relpath(a, PACOTE), i, linha.strip()))
        self.assertEqual(achados, [])

    def test_linha_de_visada_usa_o_k_optico(self):
        from EBGeo.Processings.lineOfSight import LineOfSight
        alg = LineOfSight()
        for d in (1000.0, 10000.0, 40000.0):
            self.assertAlmostEqual(alg.curvature_refraction_correction(d), refracao.queda(d, K_OPTICO), places=6)
        MEDIDAS.append('queda a 10 km com k = 1/7: {:.3f} m (com 0,13 seria {:.3f} m)'.format(
            refracao.queda(10000.0, K_OPTICO), refracao.queda(10000.0, 0.13)))

    def test_linha_de_visada_roda_e_a_parede_corta(self):
        """O algoritmo inteiro ainda roda com o k central: a visada atravessa a parede e é cortada nela."""
        import processing
        from qgis.core import QgsProcessingContext
        from EBGeo.Processings.lineOfSight import LineOfSight
        linhas = QgsVectorLayer('LineString?crs={}'.format(EPSG), 'linhas', 'memory')
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(C[0], C[1]), QgsPointXY(C[0] + 1500, C[1])]))
        linhas.dataProvider().addFeatures([f])
        ctx = QgsProcessingContext()
        ctx.setProject(QgsProject.instance())
        alg = LineOfSight()
        alg.initAlgorithm()
        r = processing.run(alg, {'DemRaster': mde_de(parede_fun, 'los_parede'), 'LinesLayer': linhas,
                                 'ObserverHeight': 2.0, 'TargetHeight': 0.0, 'OutputLayer': 'TEMPORARY_OUTPUT'},
                           context=ctx)
        saida = r['OutputLayer']
        if not isinstance(saida, QgsVectorLayer):
            saida = QgsProject.instance().mapLayer(saida) or ctx.getMapLayer(saida)
        feicoes = sorted(((ft['visible'], ft.geometry().length()) for ft in saida.getFeatures()), reverse=True)
        self.assertEqual([v for v, _ in feicoes], [1, 0])
        self.assertAlmostEqual(feicoes[0][1], 600.0, delta=2 * RES)   # visível até a face da parede

    def test_mapa_e_analise_por_setor_passam_o_k_optico_ao_gdal(self):
        caminho = mde_de(MORRO, 'k_morro')
        with Gravador() as g:
            mapa_visibilidade(caminho, C[0], C[1], EPSG, os.path.join(TMP, 'k_mapa.tif'))
            analise_setores(caminho, camada_setores())
        self.assertGreaterEqual(len(g.ccs), 3)
        self.assertEqual(set(g.ccs), {round(1 - K_OPTICO, 9)})


class TestMotor(unittest.TestCase):
    def test_plano_horizonte(self):
        """Plano a 0 m, observador a 10 m: o horizonte cai em sqrt(2 R h / (1 - k))."""
        res, n = 100.0, 401
        caminho = S.gravar_mde(os.path.join(TMP, 'plano.tif'), np.zeros((n, n)), res)
        cx, cy = S.X0 + (n // 2 + 0.5) * res, S.Y0 - (n // 2 + 0.5) * res
        r = nucleo.mapa_visibilidade(caminho, cx, cy, 10.0, 19000.0)
        m = r.matriz
        gt = r.grade.gt
        lin, col = int((cy - gt[3]) / gt[5]), int((cx - gt[0]) / gt[1])   # o observador na grade recortada
        teoria = refracao.horizonte(10.0, K_OPTICO, S.R_GDAL)
        medidos = []
        for perfil in (m[lin, col:], m[lin, col::-1], m[lin:, col], m[lin::-1, col]):
            medidos.append(np.where(perfil == 1)[0].max() * res)
        MEDIDAS.append('plano, h = 10 m: horizonte medido {} m, teoria {:.0f} m'.format(medidos, teoria))
        for d in medidos:
            self.assertLessEqual(abs(d - teoria), res)

    def test_morro_contra_referencia(self):
        caminho = mde_de(MORRO, 'morro')
        r = nucleo.mapa_visibilidade(caminho, C[0], C[1], H_OBS, ALCANCE)
        gx, gy = r.grade.centros()
        alcance = np.hypot(gx - C[0], gy - C[1]) <= ALCANCE - RES
        ref = S.visivel(MORRO, C[0], C[1], H_OBS, gx[alcance], gy[alcance], K_OPTICO)
        p = pct(r.matriz[alcance] == 1, ref)
        MEDIDAS.append('morro gaussiano: {:.2f} % de {} células iguais à referência analítica'.format(
            p, int(alcance.sum())))
        self.assertGreater(p, 99.0)
        self.assertGreater((~ref).sum(), 500)   # a sombra existe e é grande

    def test_parede_contra_referencia(self):
        caminho = mde_de(parede_fun, 'parede')
        r = nucleo.mapa_visibilidade(caminho, C[0], C[1], H_OBS, ALCANCE)
        gx, gy = r.grade.centros()
        alcance = np.hypot(gx - C[0], gy - C[1]) <= ALCANCE - RES
        ref = S.visivel(parede_fun, C[0], C[1], H_OBS, gx[alcance], gy[alcance], K_OPTICO)
        p = pct(r.matriz[alcance] == 1, ref)
        MEDIDAS.append('parede: {:.2f} % de {} células iguais à referência analítica'.format(p, int(alcance.sum())))
        self.assertGreater(p, 99.5)
        atras = alcance & (gx > C[0] + 600 + 2 * RES)
        self.assertEqual(int(r.matriz[atras].sum()), 0)
        frente = alcance & (gx < C[0] + 600)
        self.assertEqual(int((r.matriz[frente] == 0).sum()), 0)

    def test_guarda_de_extensao(self):
        caminho = mde_de(MORRO, 'guarda')
        with self.assertRaises(nucleo.ErroVisada) as e:
            nucleo.mapa_visibilidade(caminho, C[0] + 50000, C[1], H_OBS, ALCANCE)
        self.assertIn('fora do MDE', str(e.exception))
        z = MORRO(*S.centros(N, N, RES))
        z[120, 120] = -9999
        buraco = S.gravar_mde(os.path.join(TMP, 'buraco.tif'), z, RES)
        with self.assertRaises(nucleo.ErroVisada) as e:
            nucleo.mapa_visibilidade(buraco, C[0], C[1], H_OBS, ALCANCE)
        self.assertIn('sem dado', str(e.exception))

    def test_mde_em_graus_vai_ao_utm_e_bate_com_o_metrico(self):
        utm = nucleo.mapa_visibilidade(mde_de(MORRO, 'g_morro'), C[0], C[1], H_OBS, ALCANCE)
        g = em_geografico(*C)
        geo = nucleo.mapa_visibilidade(mde_geografico(MORRO, 'g_morro'), g.x(), g.y(), H_OBS, ALCANCE)
        self.assertTrue(geo.grade.reprojetado)
        self.assertIn('SIRGAS 2000 / UTM zone 23S', geo.grade.srs.GetName())
        a_utm = (utm.matriz == 1).sum() * RES * RES
        a_geo = (geo.matriz == 1).sum() * geo.grade.resolucao[0] * geo.grade.resolucao[1]
        MEDIDAS.append('MDE em graus: área visível {:.3f} km² contra {:.3f} km² no UTM ({:+.2f} %)'.format(
            a_geo / 1e6, a_utm / 1e6, 100 * (a_geo / a_utm - 1)))
        self.assertLess(abs(a_geo / a_utm - 1), 0.02)

    def test_pseudo_mercator_vai_ao_utm(self):
        merc = gdal.Warp(os.path.join(TMP, 'merc.tif'), mde_de(MORRO, 'm_morro'), dstSRS='EPSG:3857')
        merc = None
        osr_ = osr.SpatialReference()
        osr_.ImportFromEPSG(3857)
        self.assertTrue(nucleo.precisa_reprojetar(osr_))
        from qgis.core import QgsCoordinateTransform
        t = QgsCoordinateTransform(QgsCoordinateReferenceSystem(EPSG), QgsCoordinateReferenceSystem('EPSG:3857'),
                                   QgsProject.instance())
        p = t.transform(QgsPointXY(*C))
        r = nucleo.mapa_visibilidade(os.path.join(TMP, 'merc.tif'), p.x(), p.y(), H_OBS, ALCANCE)
        self.assertIn('UTM', r.grade.srs.GetName())


class TestMapaVisibilidade(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().removeAllMapLayers()

    def test_mapa_sem_grass_contra_referencia_e_no_formato_de_antes(self):
        caminho = mde_de(MORRO, 'mapa_morro')
        saida = os.path.join(TMP, 'mapa_morro_vis.tif')
        avisos = mapa_visibilidade(caminho, C[0], C[1], EPSG, saida)
        self.assertEqual(avisos, [])
        a, gt, _ = ler_grade_de(saida)
        self.assertEqual(set(np.unique(a)) - {nucleo.SEM_DADO_MAPA}, {0, 1})
        lyr = QgsProject.instance().mapLayersByName('Mapa de visibilidade')[0]
        itens = lyr.renderer().shader().rasterShaderFunction().colorRampItemList()
        self.assertEqual([(i.value, i.label, i.color.name()) for i in itens],
                         [(0, 'Sem visada', '#000000'), (1, 'Visível', '#00ff00')])
        cx, cy = S.centros(a.shape[0], a.shape[1], gt[1], gt[0], gt[3])
        alcance = np.hypot(cx - C[0], cy - C[1]) <= ALCANCE - RES
        ref = S.visivel(MORRO, C[0], C[1], H_OBS, cx[alcance], cy[alcance], K_OPTICO)
        p = pct(a[alcance] == 1, ref)
        MEDIDAS.append('Mapa de visibilidade (painel), morro: {:.2f} % iguais à referência'.format(p))
        self.assertGreater(p, 99.0)
        render([lyr, relevo(caminho)], 'visada_mapa_visibilidade.png')

    def test_mapa_com_mde_em_graus(self):
        g = em_geografico(*C)
        saida = os.path.join(TMP, 'mapa_geo_vis.tif')
        avisos = mapa_visibilidade(mde_geografico(MORRO, 'mapa'), g.x(), g.y(), 'EPSG:4674', saida)
        self.assertEqual(avisos, [])
        a, gt, wkt = ler_grade_de(saida)
        self.assertIn('UTM zone 23S', wkt)
        self.assertGreater(int((a == 1).sum()), 1000)

    def test_observador_fora_do_mde_avisa(self):
        avisos = mapa_visibilidade(mde_de(MORRO, 'fora'), C[0] + 90000, C[1], EPSG, os.path.join(TMP, 'fora.tif'))
        self.assertEqual(len(avisos), 1)
        self.assertIn('fora do MDE', avisos[0])
        self.assertEqual(QgsProject.instance().mapLayersByName('Mapa de visibilidade'), [])

    def test_coordenada_digitada_noutro_src(self):
        """Mapa em UTM, coordenada digitada em graus: o ponto chega uma vez transformado."""
        from EBGeo.Visibility.UI.interface_dialog import InterfaceDialog
        d = InterfaceDialog()
        d.setCoords([C[0], C[1], QgsCoordinateReferenceSystem(EPSG)])
        g = em_geografico(*C)
        d.projectionCombo.setCrs(QgsCoordinateReferenceSystem('EPSG:4674'))
        d.longitudeEdit.setText('{:.8f}'.format(g.x()))
        d.latitudeEdit.setText('{:.8f}'.format(g.y()))
        recebido = []
        d.finished.connect(lambda p, crs: recebido.append((p, crs)))
        d.sendCoords()
        p, crs = recebido[0]
        from qgis.core import QgsCoordinateTransform
        t = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem(EPSG), QgsProject.instance())
        q = t.transform(p)
        self.assertLess(math.hypot(q.x() - C[0], q.y() - C[1]), 1.0)


class TestAnaliseSetores(unittest.TestCase):
    def setUp(self):
        QgsProject.instance().removeAllMapLayers()

    def _conferir(self, saida, fun, rotulo):
        self.assertIsNotNone(saida)
        self.assertEqual([f.name() for f in saida.fields()], ['fid', 'value'])
        gt = (S.X0, RES, 0, S.Y0, 0, -RES)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(31983)
        if saida.crs().authid() != EPSG:
            # saída num UTM de outro datum ou na grade reprojetada: leva-se ao mesmo grid
            tmp = os.path.join(TMP, 'setores_{}_31983.gpkg'.format(rotulo))
            gdal.VectorTranslate(tmp, saida.source().split('|')[0], dstSRS='EPSG:31983')
            fonte = tmp
        else:
            fonte = saida.source().split('|')[0]
        v = rasterizar_value(fonte, gt, N, N, srs.ExportToWkt())
        cx, cy = S.centros(N, N, RES)
        ref, uniao = referencia_setores(fun, cx, cy)
        p = pct(v[uniao], ref[uniao])
        MEDIDAS.append('Análise por setor ({}): {:.2f} % de {} células iguais à contagem analítica; '
                       'valores {}'.format(rotulo, p, int(uniao.sum()), sorted(set(np.unique(v[uniao])))))
        return p, v, uniao

    def test_soma_por_setor_sem_grass_contra_referencia(self):
        caminho = mde_de(parede_fun, 'setores_parede')
        lyr = camada_setores()
        saida, avisos, mde = analise_setores(caminho, lyr)
        self.assertEqual(avisos, [])
        p, v, uniao = self._conferir(saida, parede_fun, 'parede, UTM')
        self.assertGreater(p, 99.0)
        self.assertEqual(set(np.unique(v[uniao])), {0, 1, 2})
        # estilo de antes: categorizado em "value", 0 = "Não visível", do vermelho ao verde
        r = saida.renderer()
        self.assertEqual(r.classAttribute(), 'value')
        cats = {c.value(): (c.label(), c.symbol().color().name()) for c in r.categories()}
        self.assertEqual(cats[0], ('Não visível', '#ff0000'))
        self.assertEqual(cats[max(cats)][1], '#00ff00')
        setores_lyr = QgsProject.instance().mapLayersByName('Setor de Visada')[0]
        setores_lyr.loadNamedStyle(os.path.join(PACOTE, 'VisibilityAnalysis', 'style', 'style_target_sector.qml'))
        render([setores_lyr, saida, relevo(caminho)], 'visada_setores_parede.png')

    def test_soma_por_setor_com_mde_em_graus(self):
        lyr = camada_setores()
        saida, avisos, _ = analise_setores(mde_geografico(MORRO, 'setores'), lyr)
        self.assertEqual(avisos, [])
        p, _, _ = self._conferir(saida, MORRO, 'morro, MDE em graus')
        self.assertGreater(p, 97.0)

    def test_setor_com_observador_fora_do_mde_avisa(self):
        lyr = QgsVectorLayer('Polygon?crs={}'.format(EPSG), 'Setor de Visada', 'memory')
        lyr.dataProvider().addAttributes([QgsField('altura_obs', QMetaType.Type.Double)])
        lyr.updateFields()
        f = QgsFeature(lyr.fields())
        f.setGeometry(setor(C[0] + 80000, C[1], 1000, 0, 90))
        f['altura_obs'] = 2.0
        lyr.dataProvider().addFeatures([f])
        saida, avisos, _ = analise_setores(mde_de(MORRO, 'setor_fora'), lyr)
        self.assertIsNone(saida)
        self.assertEqual(len(avisos), 1)
        self.assertRegex(avisos[0], 'fora do (MDE|Modelo Digital)')


def grass_configurado():
    try:
        from grassprovider.grass_utils import GrassUtils
        return bool(GrassUtils.grassPath())
    except Exception:
        return False


@unittest.skipUnless(grass_configurado(), 'GRASS não configurado neste ambiente (falta GISBASE)')
class TestContraGrass(unittest.TestCase):
    """O r.viewshed com os parâmetros que o Mapa de visibilidade usava contra o motor novo."""

    def test_r_viewshed_contra_gdal(self):
        import processing
        for nome, fun in (('morro', MORRO), ('parede', parede_fun)):
            caminho = mde_de(fun, 'grass_' + nome)
            out = os.path.join(TMP, 'grass_{}_rv.tif'.format(nome))
            processing.run('grass7:r.viewshed', {
                'input': caminho, 'coordinates': '{},{}'.format(*C), 'observer_elevation': H_OBS,
                'target_elevation': 0, 'max_distance': ALCANCE, 'refraction_coeff': K_OPTICO,
                '-c': True, '-r': True, '-b': True, 'output': out})
            g, _, _ = ler_grade_de(out)
            r = nucleo.mapa_visibilidade(caminho, C[0], C[1], H_OBS, ALCANCE)
            gt = r.grade.gt   # a grade do motor é o MDE recortado ao alcance: o mesmo recorte no GRASS
            r0, c0 = int(round((S.Y0 - gt[3]) / RES)), int(round((gt[0] - S.X0) / RES))
            g = g[r0:r0 + r.grade.altura, c0:c0 + r.grade.largura]
            cx, cy = r.grade.centros()
            alcance = np.hypot(cx - C[0], cy - C[1]) <= ALCANCE - RES
            p = pct(g[alcance] == 1, r.matriz[alcance] == 1)
            MEDIDAS.append('GRASS r.viewshed contra o GDAL ({}): {:.2f} % de {} células iguais'.format(
                nome, p, int(alcance.sum())))
            self.assertGreater(p, 99.5)


def caixas_de_mensagem_soltas():
    """As caixas de mensagem de topo vivas (sem pai), por identidade."""
    from qgis.PyQt.QtWidgets import QApplication
    return {id(w) for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox)}


class TestPlugin(unittest.TestCase):
    def test_acoes_de_visibilidade_abrem(self):
        from qgis.PyQt.QtWidgets import QMenu, QToolBar
        IFACE.firstRightStandardMenu.return_value = QMenu()
        IFACE.addToolBar.side_effect = lambda nome: QToolBar(nome)
        from EBGeo.ebgeo import EBGeo
        plugin = EBGeo(IFACE)
        plugin.initGui()
        acoes = {a.text(): a for a in plugin.ebGeo.actions()}
        IFACE.addDockWidget.reset_mock()
        caixas_antes = caixas_de_mensagem_soltas()
        acoes['Mapa de visibilidade'].trigger()
        self.assertTrue(plugin.mainVisib.isOpen)
        acoes['Análise de Visibilidade'].trigger()
        self.assertIsNotNone(plugin.visibilityAnalysisToolBox)
        self.assertEqual(IFACE.addDockWidget.call_count, 2)
        # K7: o Mapa de visibilidade criava um QMessageBox() sem pai que ninguém usava; a janela de
        # topo viva no fim do processo é destruída pelo sip em ordem que varia de uma execução para
        # outra, e o processo saía com 139 depois do OK (medido em 2026-10-05: 20 de 30 execuções;
        # sem a caixa, 0 de 30)
        self.assertEqual(caixas_de_mensagem_soltas() - caixas_antes, set())


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('\nMedidas:')
    for m in MEDIDAS:
        print('  ' + m)
    print('Imagens em', IMAGENS)
    sys.exit(0 if r.wasSuccessful() else 1)
