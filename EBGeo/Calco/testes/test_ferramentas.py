# -*- coding: utf-8 -*-
"""
Testes das ferramentas de captura do calco, com canvas fora da tela.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_ferramentas.py
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))  # pasta EBGeo

from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsPointXY, QgsProject, QgsRectangle  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()

from qgis.gui import QgsMapCanvas, QgsMapMouseEvent  # noqa: E402
from qgis.PyQt.QtCore import QEvent, QPoint, Qt  # noqa: E402

from Calco import schema  # noqa: E402
from Calco.calco import Calco, definir_calco_ativo  # noqa: E402
from Calco.ferramentas import FerramentaLinha, FerramentaPonto  # noqa: E402


def _clique(canvas, ferramenta, x, y, botao=Qt.MouseButton.LeftButton):
    ev = QgsMapMouseEvent(canvas, QEvent.Type.MouseButtonRelease, QPoint(x, y), botao, botao,
                          Qt.KeyboardModifier.NoModifier)
    ferramenta.canvasReleaseEvent(ev)


class TesteFerramentas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.caminho = os.path.join(cls.tmp, 'calco_teste.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.canvas = QgsMapCanvas()
        cls.canvas.resize(800, 600)
        cls.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        # cerca de 10 km de largura em torno de Porto Alegre
        cls.canvas.setExtent(QgsRectangle(-51.28, -30.07, -51.18, -29.99))
        cls.canvas.refresh()

    def _contar(self, tipo):
        return self.calco.camada(tipo).featureCount()

    def test_linha_coordenacao_dois_cliques_e_direito(self):
        ft = FerramentaLinha(self.canvas, 'coordination_line')
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append(e))
        antes = self._contar('coordination_line')
        _clique(self.canvas, ft, 100, 300)
        _clique(self.canvas, ft, 400, 250)
        _clique(self.canvas, ft, 700, 320, Qt.MouseButton.RightButton)
        lyr = self.calco.camada('coordination_line')
        self.assertEqual(lyr.featureCount(), antes + 1)
        self.assertEqual(len(criadas), 1)
        f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(criadas[0])))
        self.assertEqual(len(list(f.geometry().vertices())), 3)
        # tamanho inicial pelo zoom, como no Web: max(0,03, 2^(16-z)*0,03) km, espaçamento 3x
        z = f['created_zoom']
        self.assertIsNotNone(z)
        esperado = max(0.03, 2 ** (16 - z) * 0.03)
        self.assertAlmostEqual(f['symbol_size_km'], esperado, places=3)
        self.assertAlmostEqual(f['symbol_spacing_km'], 3 * f['symbol_size_km'], places=3)
        self.assertEqual(f['symbol_code'], '290199')

    def test_linha_com_um_ponto_nao_grava(self):
        ft = FerramentaLinha(self.canvas, 'boundary')
        antes = self._contar('boundary')
        _clique(self.canvas, ft, 100, 300, Qt.MouseButton.RightButton)
        self.assertEqual(self._contar('boundary'), antes)

    def test_vertice_proximo_demais_e_rejeitado(self):
        ft = FerramentaLinha(self.canvas, 'arrow')
        _clique(self.canvas, ft, 100, 300)
        _clique(self.canvas, ft, 100, 300)  # mesmo pixel: menos de 10 m
        self.assertEqual(len(ft.vertices), 1)
        ft.cancelar()

    def test_seta_e_multilinha(self):
        ft = FerramentaLinha(self.canvas, 'arrow')
        _clique(self.canvas, ft, 100, 300)
        _clique(self.canvas, ft, 600, 300, Qt.MouseButton.RightButton)
        lyr = self.calco.camada('arrow')
        f = list(lyr.getFeatures())[-1]
        self.assertTrue(f.geometry().isMultipart())
        self.assertGreaterEqual(f['width_m'], 50)

    def test_frente_ocupada_nasce_com_tres_pontos(self):
        ft = FerramentaLinha(self.canvas, 'occupied_front')
        _clique(self.canvas, ft, 300, 300)
        _clique(self.canvas, ft, 500, 200)  # o segundo clique já finaliza
        lyr = self.calco.camada('occupied_front')
        f = list(lyr.getFeatures())[-1]
        pts = [QgsPointXY(p) for p in f.geometry().vertices()]
        self.assertEqual(len(pts), 3)
        from qgis.core import QgsDistanceArea
        da = QgsDistanceArea()
        da.setSourceCrs(QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject.instance().transformContext())
        da.setEllipsoid('WGS84')
        d12, d13 = da.measureLine(pts[0], pts[1]), da.measureLine(pts[0], pts[2])
        self.assertAlmostEqual(d12, d13, delta=d12 * 0.001)
        import math
        b12 = math.degrees(da.bearing(pts[0], pts[1]))
        b13 = math.degrees(da.bearing(pts[0], pts[2]))
        self.assertAlmostEqual(((b13 - b12) + 360) % 360, 50.0, delta=0.1)

    def test_simbolo_pontual_um_clique(self):
        ft = FerramentaPonto(self.canvas, 'military_symbol')
        antes = self._contar('military_symbol')
        _clique(self.canvas, ft, 400, 300)
        lyr = self.calco.camada('military_symbol')
        self.assertEqual(lyr.featureCount(), antes + 1)
        f = list(lyr.getFeatures())[-1]
        self.assertEqual(f['sidc'], schema.padroes('military_symbol')['sidc'])
        self.assertTrue(f['ebgeo_id'])
        # o motor gerou o SVG na criação, com a assinatura dos campos que desenham
        from Calco import simbolos
        self.assertTrue(f['svg'])
        attrs = {c.name(): f[c.name()] for c in lyr.fields()}
        self.assertEqual(f['svg_assinatura'], simbolos.assinatura('military_symbol', attrs))
        self.assertGreater(f['largura_px'], 0)


class TesteFerramentasOutroSrc(unittest.TestCase):
    """O mesmo gesto num mapa em UTM 22S (EPSG:31982) e em Web Mercator: o calco grava em
    graus, no lugar certo, e o zoom de criação não depende do SRC do mapa."""

    def _gesto(self, epsg):
        caminho = os.path.join(tempfile.mkdtemp(), 'calco_{}.gpkg'.format(epsg.replace(':', '_')))
        calco = Calco(caminho)
        calco.criar()
        calco.carregar(estilizar_novas=False)
        definir_calco_ativo(calco)
        canvas = QgsMapCanvas()
        canvas.resize(800, 600)
        crs = QgsCoordinateReferenceSystem(epsg)
        canvas.setDestinationCrs(crs)
        from qgis.core import QgsCoordinateTransform
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
        canvas.setExtent(tr.transformBoundingBox(QgsRectangle(-51.28, -30.07, -51.18, -29.99)))
        canvas.refresh()
        ft = FerramentaLinha(canvas, 'coordination_line')
        _clique(canvas, ft, 400, 300)
        _clique(canvas, ft, 600, 300, Qt.MouseButton.RightButton)
        f = list(calco.camada('coordination_line').getFeatures())[-1]
        centro = canvas.getCoordinateTransform().toMapCoordinates(400, 300)
        esperado = QgsCoordinateTransform(crs, QgsCoordinateReferenceSystem('EPSG:4326'), QgsProject.instance()).transform(centro)
        p0 = QgsPointXY(next(f.geometry().vertices()))
        return f, p0, esperado

    def test_utm_e_mercator(self):
        zooms = {}
        for epsg in ('EPSG:31982', 'EPSG:3857', 'EPSG:4326'):
            f, p0, esperado = self._gesto(epsg)
            self.assertAlmostEqual(p0.x(), esperado.x(), places=6, msg=epsg)
            self.assertAlmostEqual(p0.y(), esperado.y(), places=6, msg=epsg)
            self.assertTrue(-52 < p0.x() < -51 and -31 < p0.y() < -29, (epsg, p0))  # gravado em graus
            zooms[epsg] = f['created_zoom']
        print('\n[src] zoom de criação por SRC do mapa:', zooms)
        # projetados: mesmo zoom; em graus o mapa estica o eixo x por 1/cos(lat) e o canvas ajusta
        # a extensão ao formato da janela, então a escala horizontal vista muda um pouco (0,2 medido)
        self.assertLessEqual(abs(zooms['EPSG:31982'] - zooms['EPSG:3857']), 0.1, zooms)
        self.assertLessEqual(max(zooms.values()) - min(zooms.values()), 0.3, zooms)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
