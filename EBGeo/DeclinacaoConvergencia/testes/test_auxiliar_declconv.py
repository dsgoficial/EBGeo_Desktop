# -*- coding: utf-8 -*-
"""
Calculadora de Declinação magnética e convergência meridiana (menu EBGeo) sem `mapRenderer()`.

O `QgsMapCanvas.mapRenderer()` saiu no QGIS 3. Em `auxiliar/auxDeclConv.py` ele só aparecia
em dois métodos que ninguém chamava (as transformações planar e geográfica); o caminho vivo da
calculadora é `Interface.doWork` -> `AuxiliarDeclConv.calculateConvergence`. Os outros dois
métodos sem chamador (calculateKappa e getReprojection) também saíram. O teste confere
que nenhum código do plugin chama mais `mapRenderer()` e aciona o clique da calculadora num
canvas de verdade.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/DeclinacaoConvergencia/testes/test_auxiliar_declconv.py
"""
import ast
import math
import os
import sys
import types
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_PLUGIN = os.path.dirname(os.path.dirname(AQUI))

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY, QgsProject,
)

_app = QgsApplication.instance()
if _app is None:
    _app = QgsApplication([], True)
    _app.initQgis()

from qgis.gui import QgsMapCanvas  # noqa: E402
from qgis.PyQt.QtCore import Qt  # noqa: E402

# Pacote EBGeo sem rodar o __init__ (que monta o plugin inteiro), para os imports relativos.
_pkg = types.ModuleType('EBGeo')
_pkg.__path__ = [RAIZ_PLUGIN]
sys.modules.setdefault('EBGeo', _pkg)

from EBGeo.auxiliar.auxDeclConv import AuxiliarDeclConv  # noqa: E402
from EBGeo.DeclinacaoConvergencia.UI.interface import Interface  # noqa: E402


class _Iface:
    def __init__(self, canvas):
        self._canvas = canvas

    def mapCanvas(self):
        return self._canvas


def _chamadas_map_renderer():
    achados = []
    for raiz, pastas, arquivos in os.walk(RAIZ_PLUGIN):
        pastas[:] = [p for p in pastas if p not in ('pyqtgraph', '__pycache__')]
        for nome in arquivos:
            if not nome.endswith('.py'):
                continue
            caminho = os.path.join(raiz, nome)
            with open(caminho, encoding='utf-8', errors='replace') as f:
                try:
                    arvore = ast.parse(f.read())
                except SyntaxError:
                    continue
            for no in ast.walk(arvore):
                if isinstance(no, ast.Attribute) and no.attr == 'mapRenderer':
                    achados.append('%s:%d' % (os.path.relpath(caminho, RAIZ_PLUGIN), no.lineno))
    return achados


class TesteAuxiliarDeclConv(unittest.TestCase):

    def test_nenhuma_chamada_a_map_renderer(self):
        self.assertEqual(_chamadas_map_renderer(), [])

    def test_so_os_metodos_com_chamador(self):
        # calculateKappa e getReprojection não tinham chamador em todo o plugin (grep de 2026-10-05)
        metodos = sorted(m for m in vars(AuxiliarDeclConv) if not m.startswith('__'))
        self.assertEqual(metodos, ['calculateConvergence', 'getCentralMeridian', 'getSemiMajorAndSemiMinorAxis'])

    def test_clique_da_calculadora_preenche_convergencia(self):
        canvas = QgsMapCanvas()
        utm = QgsCoordinateReferenceSystem('EPSG:31983')  # SIRGAS 2000 / UTM 23S, MC -45
        canvas.setDestinationCrs(utm)
        aux = AuxiliarDeclConv(_Iface(canvas))
        tela = Interface(canvas, aux)
        tela.getPoint(True)
        geo = QgsPointXY(-47.93, -15.78)  # Brasília, a 2,93 graus a oeste do MC
        pt = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), utm,
                                    QgsProject.instance()).transform(geo)
        tela.doWork(pt, Qt.MouseButton.LeftButton)
        conv = QgsProject.instance().customVariables()['convergenciaGD']
        # Convergência no hemisfério sul a oeste do MC: positiva, próxima de dl*sen(lat) = 0,797 grau.
        self.assertAlmostEqual(float(conv), 2.93 * math.sin(math.radians(15.78)), delta=0.01)
        self.assertTrue(tela.convergenciaEdit.text().startswith('0° 47'))
        tela.getPoint(False)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
