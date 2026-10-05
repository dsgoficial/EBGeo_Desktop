# -*- coding: utf-8 -*-
"""
Fumaça da barra "Simbologia Militar" com iface simulado do QGIS.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_gerenciador.py
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()

from qgis.testing.mocked import get_iface  # noqa: E402
from qgis.PyQt.QtWidgets import QMenu  # noqa: E402

from Calco.gerenciador import GerenciadorCalco, FERRAMENTAS  # noqa: E402


class TesteGerenciador(unittest.TestCase):
    def test_monta_e_desmonta(self):
        iface = get_iface()
        menu = QMenu('EBGeo')
        g = GerenciadorCalco(iface, menu)
        g.initGui()
        self.assertEqual(len(g.ferramentas), len(FERRAMENTAS))
        rotulos = [a.text() for a in g.acoes]
        for _t, _i, rot in FERRAMENTAS:
            self.assertIn(rot, rotulos)
        for a in g.acoes:
            self.assertFalse(a.icon().isNull(), a.text())
        # calco novo sem diálogo
        c = g._usar_calco(os.path.join(tempfile.mkdtemp(), 'c.gpkg'))
        from Calco import schema
        self.assertEqual(len(c.camadas_no_projeto()), len(schema.TIPOS_MILITARES))
        g.mostrar_painel()
        self.assertIsNotNone(g.painel)
        g.unload()


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
