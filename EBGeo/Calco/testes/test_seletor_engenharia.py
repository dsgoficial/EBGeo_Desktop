# -*- coding: utf-8 -*-
"""
Seletor de engenharia: todo item abre, desenha e devolve colunas que o motor aceita.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_seletor_engenharia.py
"""
import json
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()

from Calco import simbolos  # noqa: E402
from Calco.ui.seletor_engenharia import SeletorEngenharia, _itens  # noqa: E402


class TesteSeletor(unittest.TestCase):
    def test_todos_os_itens_e_variantes(self):
        dlg = SeletorEngenharia()
        n = 0
        for cod, it in _itens().items():
            dlg.cb_item.setCurrentIndex(dlg.cb_item.findData(cod))
            for i in range(dlg.cb_variante.count()):
                dlg.cb_variante.setCurrentIndex(i)
                v = dlg.valores()
                self.assertEqual(v['point_code'], cod)
                cols = simbolos.renderizar('engineering_symbol', {'point_code': v['point_code'],
                                                                  'engineering': v['engineering']})
                self.assertTrue(cols['svg'])
                pm = dlg.previa.pixmap()
                self.assertFalse(pm is None or pm.isNull(), (cod, i))
                n += 1
        print('\n[engenharia] variantes desenhadas pelo seletor:', n)
        self.assertEqual(n, 34)

    def test_folhagem_casa_variante_e_campo(self):
        dlg = SeletorEngenharia(point_code='20')
        dlg.cb_variante.setCurrentIndex(1)
        self.assertEqual(dlg.valores_campos()['foliage'], 'permanent')
        w = dlg.campos['foliage'][1]
        w.setCurrentIndex(w.findData('temporary'))
        self.assertEqual(dlg.cb_variante.currentData(), 0)

    def test_validacao_bloqueia_ok(self):
        """Pior caso: gabarito máximo menor que o mínimo (regra do Web para o item 16)."""
        dlg = SeletorEngenharia(point_code='16')
        campos = dlg.campos
        if 'minimum' in campos and 'maximum' in campos:
            campos['minimum'][1].setText('9')
            campos['maximum'][1].setText('3')
            from qgis.PyQt.QtWidgets import QDialogButtonBox
            self.assertFalse(dlg.botoes.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            self.assertTrue(dlg.erros.text())
            campos['maximum'][1].setText('12')
            self.assertTrue(dlg.botoes.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        else:
            self.skipTest('item 16 sem campos minimum/maximum no catálogo')

    def test_reabre_com_valores_da_feicao(self):
        eng = json.dumps({'variant': 0, 'values': {'order': '7', 'fillBackground': True}})
        dlg = SeletorEngenharia(point_code='2', engineering=eng)
        self.assertEqual(dlg.valores_campos()['order'], '7')
        self.assertTrue(dlg.valores_campos()['fillBackground'])


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
