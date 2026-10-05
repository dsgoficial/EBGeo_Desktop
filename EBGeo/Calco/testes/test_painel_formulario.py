# -*- coding: utf-8 -*-
"""
Dock de propriedades montado da especificação (ui/painel.py), piloto da Linha de Coordenação:
  - mostra, para cada um dos 14 símbolos, o desconhecido e o nulo, os mesmos campos que o dock de
    antes (RETRATO_DOCK de test_especificacao.py), com o rótulo da cor por dados;
  - edita no BUFFER de edição: o disco só muda no Salvar, Descartar volta ao estado de antes,
    Ctrl+Z desfaz, e a edição aberta pelo operador continua aberta depois do Salvar;
  - a feição bloqueada aparece só para leitura;
  - os demais tipos seguem gravando direto, como antes do piloto.
Grava capturas do dock em EBGEO_TESTE_SAIDA (padrão: temporária).

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_painel_formulario.py
"""
import os
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
sys.path.insert(0, AQUI)

from qgis.core import QgsApplication, QgsGeometry, QgsPointXY, QgsVectorLayer  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from qgis.testing.mocked import get_iface  # noqa: E402

from Calco import gpkg, schema  # noqa: E402
from Calco.calco import Calco, definir_calco_ativo  # noqa: E402
from Calco.ferramentas import gravar_feicao  # noqa: E402
from Calco.ui.painel import PainelCalco  # noqa: E402
from test_especificacao import RETRATO_DOCK, ROTULO_COR, SEMPRE  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_painel_')
os.makedirs(SAIDA, exist_ok=True)


class TestePainelFormulario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_painel_form.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar()   # com o estilo (e o formulário) do plugin
        definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())
        # solto e à mostra: a janela principal do iface de teste nunca aparece, e grupo de painel
        # invisível não recolhe
        cls.painel.setParent(None)
        cls.painel.resize(420, 900)
        cls.painel.show()
        cls.lyr = cls.calco.camada('coordination_line')

    def _nova(self, **attrs):
        a = dict(schema.padroes('coordination_line'), ebgeo_id=str(uuid.uuid4()), nome='Linha do teste')
        a.update(attrs)
        eid = gravar_feicao(self.lyr, 'coordination_line',
                            QgsGeometry.fromPolylineXY([QgsPointXY(-51.2, -30.0), QgsPointXY(-51.1, -30.0)]), a)
        self.painel._camada_mudou(self.lyr)
        self.painel.mostrar_feicao(self.lyr, eid)
        self.painel._selecao_mudou()
        return eid

    def _disco(self, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_line'), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _capturar(self, nome):
        self.painel.show()
        _app.processEvents()
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def tearDown(self):
        if self.lyr.isEditable():
            self.lyr.rollBack()
        _app.processEvents()

    def test_campos_conforme_o_retrato_do_dock(self):
        for codigo, condicionais in RETRATO_DOCK.items():
            self._nova(symbol_code=codigo)
            vis = self.painel.campos_visiveis()
            antigos = set(condicionais) | set(SEMPRE)
            todos_antigos = set(RETRATO_DOCK['140000']) | set(RETRATO_DOCK['140200']) | set(RETRATO_DOCK['240701']) | \
                set(RETRATO_DOCK['290199']) | set(SEMPRE)
            self.assertEqual(vis & todos_antigos, antigos, codigo)
            # o widget fora da condição está oculto de fato
            for col in todos_antigos - antigos:
                self.assertTrue(self.painel.widgets[col].isHidden(), (codigo, col))
            rotulos = {lb.text() for lb in self.painel.form_host.findChildren(type(self.painel.titulo)) if lb.isVisibleTo(self.painel.form_host)}
            self.assertIn(ROTULO_COR[codigo], rotulos)
            self.assertIn('visivel', vis)
            self.assertIn('ebgeo_id', vis)

    def test_buffer_salvar(self):
        eid = self._nova(symbol_code='290199', color='#00B04E')
        self.assertFalse(self.lyr.isEditable())
        self.assertFalse(self.painel.botao_salvar.isEnabled())
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('140200'))
        _app.processEvents()
        # no buffer, com a regra do guardião, e nada no disco
        self.assertTrue(self.lyr.isEditable())
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual(f['symbol_code'], '140200')
        self.assertEqual(str(f['color']).lower(), '#000000')
        self.assertEqual(self._disco(eid)['symbol_code'], '290199')
        self.assertTrue(self.painel.botao_salvar.isEnabled())
        self.assertEqual(self.painel.estado_edicao.text(), 'Mudanças não salvas.')
        self.assertIn('enemy_color', self.painel.campos_visiveis())
        self._capturar('dock_140200_mudancas_nao_salvas.png')
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        d = self._disco(eid)
        self.assertEqual((d['symbol_code'], str(d['color']).lower()), ('140200', '#000000'))
        self.assertFalse(self.lyr.isEditable())  # o painel abriu a edição e a fechou
        self.assertFalse(self.painel.botao_salvar.isEnabled())
        self._capturar('dock_140200_salvo.png')

    def test_descartar_e_desfazer(self):
        eid = self._nova(symbol_code='140000', tipo='LCAF')
        ed = self.painel.widgets['tipo']
        ed.setText('P Lib')
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()
        self.assertEqual(self.lyr.getFeature(self.painel.fid)['tipo'], 'P Lib')
        self.lyr.undoStack().undo()   # Ctrl+Z
        self.assertEqual(self.lyr.getFeature(self.painel.fid)['tipo'], 'LCAF')
        self.lyr.undoStack().redo()
        sp = self.painel.widgets['text_size']
        sp.setValue(30)
        self.painel._gravar_pendentes()
        self.assertTrue(self.painel.descartar())
        _app.processEvents()
        self.assertFalse(self.lyr.isEditable())
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual((f['tipo'], f['text_size']), ('LCAF', 14.0))
        self.assertEqual(self._disco(eid)['tipo'], 'LCAF')

    def _editar_texto(self, col, texto):
        ed = self.painel.widgets[col]
        ed.setText(texto)
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()

    def test_edicao_do_operador_continua_aberta(self):
        eid = self._nova(symbol_code='240701')
        self.lyr.startEditing()
        self._editar_texto('numero_concentracao', 'AB0102')
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        self.assertTrue(self.lyr.isEditable())   # a edição era do operador: continua aberta
        self.assertEqual(self._disco(eid)['numero_concentracao'], 'AB0102')
        # Descartar só desfaz o que o painel fez depois, e a edição continua
        self._editar_texto('numero_concentracao', 'ZZ')
        self.assertTrue(self.painel.descartar())
        _app.processEvents()
        self.assertTrue(self.lyr.isEditable())
        f = next(self.lyr.getFeatures("\"ebgeo_id\" = '{}'".format(eid)))
        self.assertEqual(f['numero_concentracao'], 'AB0102')

    def test_bloqueada_so_leitura(self):
        self._nova(symbol_code='140200', bloqueado=True)
        from qgis.PyQt.QtWidgets import QLabel, QPushButton
        textos = [lb.text() for lb in self.painel.form_host.findChildren(QLabel) if lb.isVisibleTo(self.painel.form_host)]
        self.assertIn('Feição bloqueada no EBGeo Web: os campos ficam só para leitura.', textos)
        for col in ('nome', 'symbol_code', 'color', 'enemy_color', 'line_width'):
            self.assertFalse(self.painel.widgets[col].isEnabled(), col)
        inverter = [b for b in self.painel.findChildren(QPushButton) if b.text() == 'Inverter sentido']
        self.assertTrue(inverter and not inverter[0].isEnabled())
        self._capturar('dock_bloqueada.png')

    def test_inverter_no_buffer(self):
        eid = self._nova(symbol_code='140200')
        self.painel._inverter()
        pts = list(self.lyr.getFeature(self.painel.fid).geometry().vertices())
        self.assertAlmostEqual(pts[0].x(), -51.1, places=6)
        self.assertAlmostEqual(list(self._disco(eid).geometry().vertices())[0].x(), -51.2, places=6)
        self.assertTrue(self.painel.salvar())
        self.assertAlmostEqual(list(self._disco(eid).geometry().vertices())[0].x(), -51.1, places=6)

    def test_outros_tipos_como_antes(self):
        lyr = self.calco.camada('boundary')
        a = dict(schema.padroes('boundary'), ebgeo_id=str(uuid.uuid4()))
        eid = gravar_feicao(lyr, 'boundary', QgsGeometry.fromPolylineXY([QgsPointXY(-51.2, -30.0), QgsPointXY(-51.1, -30.0)]), a)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        self.assertTrue(self.painel.barra_edicao.isHidden())
        ed = self.painel.widgets['text_top']
        ed.setText('ALFA')
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()
        self.assertFalse(lyr.isEditable())
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'boundary'), 'r', 'ogr')
        self.assertEqual(next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))['text_top'], 'ALFA')


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
