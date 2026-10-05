# -*- coding: utf-8 -*-
"""
O zoom do EBGeo Web no Desktop: a convenção de 512 px do MapLibre, conferida contra a tela do Web.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_zoom.py

Medido em 2026-10-05 no EBGeo Web (Playwright no app real, backend com o banco do e2e, viewport
1200 x 900, devicePixelRatio 1): um Símbolo Militar desenhado pela ferramenta no zoom 14 em
(-43,2; -22,9), com a correção de zoom ligada; a tela foi fotografada nos zooms 12, 14, 15,5 e 17,
e os metros de terreno por pixel CSS saíram do `unproject` de dois pontos a 400 px um do outro.
O QGIS desenhou a mesma feição (importada do .ebgeo) na MESMA resolução de terreno: o retângulo
azul da moldura mediu 94 x 62 px no Web e 94 x 61 no QGIS no zoom 14, 264 x 174 e 266 x 175 no
15,5 (no 12, 24 x 16 e 23 x 14, a quantização de um símbolo de 24 px). Pela convenção de 256 px
do KMZ do Web, o símbolo do Desktop sairia com o dobro.

O que se prova:
    TesteConvencao  o metro por pixel do zoom é o mundo de 512 px do MapLibre e bate com os quatro
                    zooms medidos na tela do Web; a de 256 px reprova; toda cópia do fator no
                    desenho (Python e expressões) é a mesma, e nenhuma usa a de 256 px;
    TesteSimbolo    o símbolo militar do Web, importado e desenhado pelo estilo do importador na
                    resolução de terreno da tela do Web, sai do tamanho medido no Web (exige a
                    fixture 06, EBGEO_FIXTURES, para o esqueleto do .ebgeo).
"""
import copy
import glob
import math
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
CALCO = os.path.join(PLUGIN, 'Calco')
RAIZ_REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpressionContext,
    QgsExpressionContextUtils, QgsMapRendererSequentialJob, QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import zoom  # noqa: E402

R_MAPLIBRE = 6378137.0
LON, LAT = -43.2, -22.9
#: zoom do MapLibre -> metros de terreno por pixel CSS, medidos na tela do Web em (LON, LAT)
MEDIDO_NO_WEB = {12: 17.603168725235932, 14: 4.400792181472924, 15.5: 1.5559149969833277, 17: 0.550099022664989}
#: zoom -> (largura, altura) em px do retângulo azul da moldura do símbolo, medidos no Web
SIMBOLO_NO_WEB = {14: (94, 62), 15.5: (264, 174)}
FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
MEDIDAS = []


class TesteConvencao(unittest.TestCase):
    def test_mundo_de_512_px(self):
        self.assertAlmostEqual(zoom.M_POR_PX_Z0, 2 * math.pi * R_MAPLIBRE / 512, places=3)

    def test_bate_com_a_tela_do_web(self):
        for z, medido in MEDIDO_NO_WEB.items():
            calculado = zoom.metros_por_pixel_de_zoom(z, LAT)
            MEDIDAS.append('zoom {}: {:.5f} m/px no Desktop, {:.5f} na tela do Web'.format(z, calculado, medido))
            self.assertLess(abs(calculado / medido - 1), 1e-4, z)
            self.assertEqual(zoom.zoom_de_metros_por_pixel(medido, LAT), round(z, 1))

    def test_a_convencao_de_256_px_reprova(self):
        """O pior caso: o fator do KMZ do Web (256 px) dá o dobro do metro por pixel da tela."""
        m256 = 2 * math.pi * R_MAPLIBRE / 256 * math.cos(math.radians(LAT)) / 2 ** 14
        self.assertGreater(abs(m256 / MEDIDO_NO_WEB[14] - 1), 0.5)

    def test_toda_copia_do_fator_e_a_mesma(self):
        """Os literais numéricos do desenho (Python e expressões, sem comentário): toda cópia do
        fator é 78271,517, e nenhum é o 156543,03 da convenção de 256 px."""
        import io
        import tokenize
        copias, de_256 = [], []
        arquivos = [p for p in glob.glob(os.path.join(CALCO, '**', '*.py'), recursive=True)
                    + glob.glob(os.path.join(CALCO, 'expressoes', '*.exp'))
                    if os.sep + 'testes' + os.sep not in p and os.sep + 'motor' + os.sep not in p]
        for a in arquivos:
            with open(a, encoding='utf-8') as fh:
                texto = fh.read()
            if a.endswith('.py'):
                numeros = [t.string for t in tokenize.generate_tokens(io.StringIO(texto).readline)
                           if t.type == tokenize.NUMBER]
                # o fator também mora em texto de expressão montado pelo Python
                numeros += [n for t in tokenize.generate_tokens(io.StringIO(texto).readline)
                            if t.type == tokenize.STRING for n in re.findall(r'\d+\.\d+', t.string)]
            else:
                numeros = re.findall(r'\d+\.\d+', re.sub(r'/\*.*?\*/', '', texto, flags=re.S))
            for n in numeros:
                if n.startswith('78271'):
                    copias.append((os.path.relpath(a, CALCO), n))
                if n.startswith('156543'):
                    de_256.append((os.path.relpath(a, CALCO), n))
        self.assertGreaterEqual(len(copias), 5, copias)
        self.assertEqual(sorted({v for _a, v in copias}), ['78271.517'], copias)
        self.assertEqual(de_256, [])


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente (EBGEO_FIXTURES)')
class TesteSimbolo(unittest.TestCase):
    """A feição que a ferramenta do Web gravou, com as propriedades que desenham."""

    FEICAO = {
        'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [LON, LAT]},
        'properties': {
            'id': 'b7a1f1d2-5f0c-4b8e-9b1a-000000000512', 'source': 'military_symbol', 'layerId': 'default',
            'sidc': '100310001612110000000760000000', 'size': 1, 'opacity': 1, 'rotation': 0, 'fillColor': None,
            'createdAtZoom': 14, 'zoomCorrectionEnabled': True, 'iconOffset': [0, -12.81], 'width': 100,
            'height': 93.5, 'nome': 'Símbolo Militar #1', 'descricao': '', 'visivel': True, 'bloqueado': False,
        },
    }

    @classmethod
    def setUpClass(cls):
        from Calco import gpkg
        from Calco.exportador import arquivo
        from Calco.importador import arvore, escritor, leitor
        data = copy.deepcopy(leitor.abrir(FIXTURE_06).data)
        for i, m in enumerate(data['maps'].values()):
            m['features'] = {'military_symbols': [copy.deepcopy(cls.FEICAO)]} if i == 0 else {}
        d = tempfile.mkdtemp(prefix='ebgeo_zoom_')
        arq = os.path.join(d, 'zoom.ebgeo')
        arquivo.gravar(arq, data, {})
        cls.gpkg = os.path.join(d, 'zoom.gpkg')
        escritor.importar(arq, cls.gpkg)
        arvore.salvar_estilos(cls.gpkg)
        cls.vl = QgsVectorLayer(gpkg.uri_camada(cls.gpkg, 'military_symbol'), 'ms', 'ogr')
        cls.saida = os.environ.get('EBGEO_TESTE_SAIDA') or d

    def _retangulo_azul(self, metros_por_px):
        """Largura e altura (px) do azul da moldura, desenhado na resolução de terreno pedida."""
        import numpy as np
        c = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), QgsCoordinateReferenceSystem('EPSG:3857'),
                                   QgsProject.instance()).transform(QgsPointXY(LON, LAT))
        res = metros_por_px / math.cos(math.radians(LAT))
        ms = QgsMapSettings()
        ms.setLayers([self.vl])
        ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        ms.setOutputSize(QSize(400, 400))
        ms.setOutputDpi(96)
        ms.setBackgroundColor(QColor('white'))
        ms.setExtent(QgsRectangle(c.x() - 200 * res, c.y() - 200 * res, c.x() + 200 * res, c.y() + 200 * res))
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.globalScope())
        ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
        ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
        ms.setExpressionContext(ctx)
        job = QgsMapRendererSequentialJob(ms)
        job.start()
        job.waitForFinished()
        img = job.renderedImage()
        img.save(os.path.join(self.saida, 'zoom_simbolo_{:.0f}cm.png'.format(metros_por_px * 100)))
        b = img.constBits()
        b.setsize(img.sizeInBytes())
        a = np.frombuffer(bytes(b), dtype=np.uint8).reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4]
        a = a.reshape(img.height(), img.width(), 4).astype(int)   # BGRA
        azul = (abs(a[:, :, 2] - 128) < 20) & (abs(a[:, :, 1] - 224) < 20) & (abs(a[:, :, 0] - 255) < 15)
        ys, xs = np.nonzero(azul)
        return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)

    def test_tamanho_do_web_na_resolucao_da_tela_do_web(self):
        self.assertEqual(self.vl.featureCount(), 1)
        for z, (lw, hw) in SIMBOLO_NO_WEB.items():
            ld, hd = self._retangulo_azul(MEDIDO_NO_WEB[z])
            MEDIDAS.append('símbolo no zoom {}: {} x {} px no Desktop, {} x {} no Web'.format(z, ld, hd, lw, hw))
            self.assertLessEqual(abs(ld - lw), 3, z)
            self.assertLessEqual(abs(hd - hw), 3, z)

    def test_na_resolucao_de_256_px_sai_com_a_metade(self):
        """Controle do instrumento: na resolução que a convenção de 256 px daria, o símbolo sai com
        a metade do que o Web mostra, e a régua acima reprovaria."""
        ld, _hd = self._retangulo_azul(2 * MEDIDO_NO_WEB[15.5])
        self.assertLess(ld, SIMBOLO_NO_WEB[15.5][0] * 0.6)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('\nMedidas:')
    for m in MEDIDAS:
        print('  ' + m)
    sys.exit(0 if r.wasSuccessful() else 1)
