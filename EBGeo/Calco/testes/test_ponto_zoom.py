# -*- coding: utf-8 -*-
"""Tamanho e afastamento do Ponto: python-qgis.bat EBGeo/Calco/testes/test_ponto_zoom.py."""
import math
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qgis.core import (
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression,
    QgsExpressionContext, QgsExpressionContextUtils, QgsFeature, QgsGeometry,
    QgsMapRendererSequentialJob, QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import estilos_formas as estilos, zoom


class TestPontoZoom(unittest.TestCase):
    def setUp(self):
        self.layer = QgsVectorLayer('Point?crs=EPSG:4326&field=size:double&field=created_zoom:double'
                                    '&field=zoom_corr:boolean&field=marker_symbol:string&field=line_width:double'
                                    '&field=fill_color:string&field=line_color:string', 'ponto', 'memory')
        self.feature = QgsFeature(self.layer.fields())
        self.feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-43.2, -22.9)))
        self.feature.setAttributes([10, 12, True, 'circle', 0, '#ff0000', '#ff0000'])

    def mapa(self, z, crs='EPSG:3857', dpi=96):
        ms = QgsMapSettings()
        ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
        ms.setOutputSize(QSize(1200, 1200))
        ms.setOutputDpi(dpi)
        ms.setBackgroundColor(QColor('white'))
        tr = QgsCoordinateTransform(self.layer.crs(), ms.destinationCrs(), QgsProject.instance())
        c = tr.transform(self.feature.geometry().asPoint())
        # Unidade projetada por pixel CSS, medida localmente na latitude do ponto.
        leste = tr.transform(QgsPointXY(-43.199, -22.9))
        unidade_por_metro = math.hypot(leste.x() - c.x(), leste.y() - c.y()) / (
            6378137 * math.cos(math.radians(-22.9)) * math.radians(0.001))
        res = zoom.metros_por_pixel_de_zoom(z, -22.9) * unidade_por_metro * 96 / dpi
        ms.setExtent(QgsRectangle(c.x() - 600 * res, c.y() - 600 * res,
                                 c.x() + 600 * res, c.y() + 600 * res))
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))
        ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
        ctx.setFeature(self.feature)
        ms.setExpressionContext(ctx)
        return ms

    def avaliar(self, expr, z=13, crs='EPSG:3857', dpi=96):
        e = QgsExpression(expr)
        valor = e.evaluate(self.mapa(z, crs, dpi).expressionContext())
        self.assertFalse(e.hasParserError(), e.parserErrorString())
        self.assertFalse(e.hasEvalError(), e.evalErrorString())
        return valor

    def test_ancora_nula_zero_e_correcao_desligada(self):
        for ancora, correcao, esperado in ((None, True, 10), (0, True, 500), (12, True, 20),
                                           (0, False, 10), (12, None, 20)):
            self.feature['created_zoom'], self.feature['zoom_corr'] = ancora, correcao
            with self.subTest(ancora=ancora, correcao=correcao):
                self.assertAlmostEqual(self.avaliar(estilos.expr_tamanho_ponto_px()), esperado, places=4)

    def test_teto_escala_e_resolucao_em_dois_crs(self):
        for crs in ('EPSG:3857', 'EPSG:32723'):
            for dpi in (96, 192):
                for z, esperado in ((0, 10 / 4096), (12, 10), (13, 20), (18, 500)):
                    with self.subTest(crs=crs, dpi=dpi, zoom=z):
                        self.assertAlmostEqual(self.avaliar(estilos.expr_tamanho_ponto_px(), z, crs, dpi),
                                               esperado, places=3)

    def test_raio_com_contorno_e_forma_para_afastar_rotulo(self):
        self.feature['line_width'] = 3
        for forma, esperado in (('circle', 23), ('square', 20 * 43 / 48), ('custom:teste', 20)):
            self.feature['marker_symbol'] = forma
            self.assertAlmostEqual(self.avaliar(estilos.expr_raio_ponto_px()), esperado, places=4)

    def test_pixels_do_estilo_no_teto_e_sem_ancora(self):
        import numpy as np
        for ancora, forma, borda, esperado in ((0, 'circle', 0, 1000), (None, 'circle', 0, 20),
                                               (12, 'circle', 0, 40), (12, 'circle', 3, 46),
                                               (12, 'square', 3, 40 * 43 / 48)):
            self.feature['created_zoom'] = ancora
            self.feature['marker_symbol'] = forma
            self.feature['line_width'] = borda
            self.layer.dataProvider().truncate()
            self.layer.dataProvider().addFeatures([self.feature])
            estilos.aplicar_estilo(self.layer, 'point')
            self.layer.setLabelsEnabled(False)
            ms = self.mapa(13)
            ms.setLayers([self.layer])
            job = QgsMapRendererSequentialJob(ms)
            job.start()
            job.waitForFinished()
            img = job.renderedImage()
            bits = img.constBits().asarray(img.sizeInBytes())
            pixels = np.frombuffer(bits, dtype=np.uint8).reshape(img.height(), img.bytesPerLine())
            pixels = pixels[:, :img.width() * 4].reshape(img.height(), img.width(), 4)
            ys, xs = np.nonzero((pixels[:, :, 2] > 200) & (pixels[:, :, 1] < 50))
            self.assertTrue(len(xs), ancora)
            self.assertLessEqual(abs(int(xs.max() - xs.min() + 1) - esperado), 2, ancora)
            self.assertLessEqual(abs(int(ys.max() - ys.min() + 1) - esperado), 2, ancora)


if __name__ == '__main__':
    unittest.main(verbosity=2)
