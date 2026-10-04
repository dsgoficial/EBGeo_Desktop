# -*- coding: utf-8 -*-
"""
Simplificar Interface no QGIS 4: ligar e desligar várias vezes volta às barras de antes.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/testes/test_simplificar_interface.py
"""
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))  # pasta EBGeo (o módulo usa import absoluto do Protector)

from qgis.core import QgsApplication, QgsSettings  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()
sys.path.insert(0, os.path.join(QgsApplication.pkgDataPath(), 'python', 'plugins'))
from processing.core.Processing import Processing  # noqa: E402

Processing.initialize()

from qgis.PyQt.QtCore import Qt  # noqa: E402
from qgis.PyQt.QtGui import QAction  # noqa: E402
from qgis.PyQt.QtWidgets import QDockWidget, QMenu, QToolBar  # noqa: E402
from qgis.testing.mocked import get_iface  # noqa: E402

from SimplifyInterface.simplify_interface import SimplifyInterface, _widgets_da_acao  # noqa: E402


class TesteSimplificar(unittest.TestCase):
    def setUp(self):
        self.iface = get_iface()
        self.mw = self.iface.mainWindow()
        for nome, acoes in {'mFileToolBar': ['mActionNewProject', 'mActionSaveProject'],
                            'mMapNavToolBar': ['mActionPan', 'mActionZoomIn'],
                            'mLayerToolBar': ['mActionAddOgrLayer']}.items():
            tb = QToolBar(nome, self.mw)
            tb.setObjectName(nome)
            self.mw.addToolBar(tb)
            for a in acoes:
                ac = QAction(a, self.mw)
                ac.setObjectName(a)
                tb.addAction(ac)
            menu = QMenu(self.mw)
            menu.addAction(QAction('x', self.mw))
            ac = QAction('com menu', self.mw)
            ac.setObjectName('mActionComMenu')
            ac.setMenu(menu)
            tb.addAction(ac)
        d = QDockWidget('Camadas', self.mw)
        d.setObjectName('Layers')
        self.mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d)

    def _visiveis(self):
        return sorted(t.objectName() for t in self.mw.findChildren(QToolBar)
                      if t.parent() == self.mw and not t.isHidden())

    def test_widgets_da_acao_no_qt6(self):
        """O erro do chefe: QAction.associatedWidgets não existe no Qt6."""
        ac = self.mw.findChild(QAction, 'mActionComMenu')
        self.assertIn('QToolButton', [type(w).__name__ for w in _widgets_da_acao(ac)])

    def test_liga_e_desliga_tres_vezes(self):
        si = SimplifyInterface(self.iface)
        antes = self._visiveis()
        for _ in range(3):
            si.enable(store=True)
            self.assertNotEqual(self._visiveis(), antes)
            si.disable(store=True)
            self.assertEqual(self._visiveis(), antes)
        self.assertIsNone(QgsSettings().value('qgislight/enabled'))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
