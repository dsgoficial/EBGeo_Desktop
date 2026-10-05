# -*- coding: utf-8 -*-
"""
Painel de propriedades: a mudança feita no painel chega à feição gravada e, nos
símbolos pontuais, regera o SVG.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_painel.py
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication, QgsGeometry, QgsPointXY, QgsVectorLayer  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()

from qgis.testing.mocked import get_iface  # noqa: E402
from qgis.PyQt.QtWidgets import QComboBox, QDoubleSpinBox  # noqa: E402

from Calco import gpkg  # noqa: E402
from Calco.calco import Calco, definir_calco_ativo  # noqa: E402
from Calco.ferramentas import atributos_iniciais, gravar_feicao  # noqa: E402
from Calco.ui.painel import PainelCalco  # noqa: E402


class _CanvasFalso:
    """atributos_iniciais só precisa de um canvas para o zoom; sem ele, nada de zoom."""
    def extent(self):
        raise RuntimeError


def _attrs(tipo):
    try:
        return atributos_iniciais(tipo, _CanvasFalso())
    except RuntimeError:
        from Calco import schema
        import uuid
        a = dict(schema.padroes(tipo))
        a['ebgeo_id'] = str(uuid.uuid4())
        return a


class TestePainel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_painel.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.iface = get_iface()
        cls.painel = PainelCalco(cls.iface)

    def _selecionar(self, tipo, ebgeo_id):
        lyr = self.calco.camada(tipo)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, ebgeo_id)
        self.painel._selecao_mudou()
        return lyr

    def _reler(self, lyr, ebgeo_id):
        nova = QgsVectorLayer(gpkg.uri_camada(self.caminho, lyr.customProperty('ebgeo_calco/tipo')), 'r', 'ogr')
        return next(nova.getFeatures('"ebgeo_id" = \'{}\''.format(ebgeo_id)))

    def test_medida_troca_para_escalao_ft(self):
        a = _attrs('coordination_measure')
        eid = gravar_feicao(self.calco.camada('coordination_measure'), 'coordination_measure',
                            QgsGeometry.fromPointXY(QgsPointXY(-51.2, -30.0)), a)
        lyr = self._selecionar('coordination_measure', eid)
        svg_antes = self._reler(lyr, eid)['svg']
        self.assertTrue(svg_antes)
        cb = self.painel.widgets['point_code']
        self.assertIsInstance(cb, QComboBox)
        self.assertGreater(cb.count(), 80)
        cb.setCurrentIndex(cb.findData('ESCALAO_FT'))
        _app.processEvents()  # o painel se remonta no ciclo seguinte
        f = self._reler(lyr, eid)
        self.assertEqual(f['point_code'], 'ESCALAO_FT')
        self.assertEqual(f['echelon_code'], 'ESCALAO_FT_16')
        self.assertTrue(f['svg'])
        self.assertNotEqual(f['svg'], svg_antes)
        # escalão da família agora é combo com os 13 escalões do catálogo
        cb_esc = self.painel.widgets['echelon_code']
        self.assertEqual(cb_esc.count(), 13)
        cb_esc.setCurrentIndex(cb_esc.findData('ESCALAO_FT_18'))
        self.painel._gravar_pendentes()
        self.assertEqual(self._reler(lyr, eid)['echelon_code'], 'ESCALAO_FT_18')

    def test_linha_coordenacao_troca_simbolo_e_tamanho_em_metros(self):
        a = _attrs('coordination_line')
        eid = gravar_feicao(self.calco.camada('coordination_line'), 'coordination_line',
                            QgsGeometry.fromPolylineXY([QgsPointXY(-51.2, -30.0), QgsPointXY(-51.1, -30.0)]), a)
        lyr = self._selecionar('coordination_line', eid)
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('290307'))
        sp = self.painel.widgets['symbol_size_km']
        self.assertIsInstance(sp, QDoubleSpinBox)
        sp.setValue(250)  # metros na tela, km no disco
        self.painel._gravar_pendentes()
        # a Linha de Coordenação edita no buffer: o disco só muda no Salvar
        self.assertEqual(self._reler(lyr, eid)['symbol_code'], '290199')
        self.assertTrue(self.painel.salvar())
        f = self._reler(lyr, eid)
        self.assertEqual(f['symbol_code'], '290307')
        self.assertAlmostEqual(f['symbol_size_km'], 0.25, places=6)

    def test_simbolo_militar_amplificador_regera_svg(self):
        a = _attrs('military_symbol')
        eid = gravar_feicao(self.calco.camada('military_symbol'), 'military_symbol',
                            QgsGeometry.fromPointXY(QgsPointXY(-51.2, -30.0)), a)
        lyr = self._selecionar('military_symbol', eid)
        antes = self._reler(lyr, eid)
        ed = self.painel.widgets['unique_designation']
        ed.setText('3 BIB')
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()
        f = self._reler(lyr, eid)
        self.assertEqual(f['unique_designation'], '3 BIB')
        self.assertNotEqual(f['svg'], antes['svg'])
        self.assertNotEqual(f['svg_assinatura'], antes['svg_assinatura'])

    def test_inverter_linha(self):
        a = _attrs('boundary')
        eid = gravar_feicao(self.calco.camada('boundary'), 'boundary',
                            QgsGeometry.fromPolylineXY([QgsPointXY(-51.2, -30.0), QgsPointXY(-51.1, -30.05)]), a)
        lyr = self._selecionar('boundary', eid)
        self.painel._inverter()
        pts = list(self._reler(lyr, eid).geometry().vertices())
        self.assertAlmostEqual(pts[0].x(), -51.1, places=6)
        self.assertAlmostEqual(pts[-1].x(), -51.2, places=6)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
