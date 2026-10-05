# -*- coding: utf-8 -*-
"""
Guardião de camada (guardiao.py) e regras de troca (regras.py), piloto da Linha de Coordenação:
a cor padrão ao trocar o símbolo vale em qualquer caminho de edição (formulário nativo, tabela
de atributos, edição em lote como a da calculadora de campo), desfazer não reaplica a regra, a
feição bloqueada no EBGeo Web não se edita pela tabela, e `atualizado_em` se renova.

O pior caso é a mesma edição sem o guardião ligado: a cor fica, e a régua tem de acusar.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_guardiao.py
"""
import os
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsVectorLayer  # noqa: E402
from qgis.PyQt.QtCore import Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from qgis.gui import (  # noqa: E402
    QgsGui, QgsAttributeForm, QgsAttributeEditorContext, QgsAttributeTableModel, QgsDualView, QgsEditorWidgetWrapper,
    QgsMapCanvas,
)
from qgis.PyQt.QtWidgets import QStyleOptionViewItem  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from Calco import calco as C, gpkg, schema, regras, guardiao  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_guardiao_')
VERDE, PRETO = '#00b04e', '#000000'


def camada(nome, estilizar=True, feicoes=(('290199', '#00B04E', False),)):
    caminho = os.path.join(TMP, nome + '.gpkg')
    gpkg.criar_calco(caminho, ['coordination_line'])
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_line'), 'Linha de Coordenação', 'ogr')
    idx = vl.fields().indexOf
    vl.startEditing()
    for codigo, cor, bloq in feicoes:
        a = dict(schema.padroes('coordination_line'), ebgeo_id=str(uuid.uuid4()), symbol_code=codigo, color=cor,
                 bloqueado=bloq, atualizado_em='2026-10-05T09:00:00+00:00', nome='linha ' + codigo)
        f = QgsFeature(vl.fields())
        for k, v in a.items():
            if idx(k) >= 0:
                f.setAttribute(idx(k), v)
        f.setGeometry(QgsGeometry.fromWkt('LINESTRING(-47 -15, -46.9 -15)'))
        vl.addFeature(f)
    assert vl.commitChanges()
    if estilizar:
        C.aplicar_estilo(vl, 'coordination_line')
    return vl


def pelo_formulario(vl, fid, mudancas):
    """Edita como o operador no formulário nativo: muda os widgets e salva."""
    form = QgsAttributeForm(vl, vl.getFeature(fid))
    form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
    for wr in form.findChildren(QgsEditorWidgetWrapper):
        col = vl.fields().at(wr.fieldIdx()).name()
        if col in mudancas:
            wr.setValues(mudancas[col], [])
            wr.emitValueChanged()
    assert form.save()
    form.deleteLater()


def pela_tabela(vl, fid, coluna, valor):
    """
    Edita uma célula como a tabela de atributos: o delegado da própria tabela cria o editor e grava
    (QgsAttributeTableModel.setData não grava; quem grava é o setModelData do delegado).
    """
    canvas = QgsMapCanvas()
    dv = QgsDualView()
    dv.init(vl, canvas)
    tv = dv.tableView()
    m = tv.model()
    nome = vl.attributeDisplayName(vl.fields().indexOf(coluna))
    col = [c for c in range(m.columnCount()) if m.headerData(c, Qt.Orientation.Horizontal) == nome][0]
    linha = [r for r in range(m.rowCount()) if m.data(m.index(r, 0), QgsAttributeTableModel.Role.FeatureId) == fid][0]
    ix = m.index(linha, col)
    d = tv.itemDelegateForIndex(ix)
    ed = d.createEditor(tv.viewport(), QStyleOptionViewItem(), ix)
    QgsEditorWidgetWrapper.fromWidget(ed).setValues(valor, [])
    d.setModelData(ed, m, ix)
    dv.deleteLater()


def cor(vl, fid):
    return str(regras.valor(vl.getFeature(fid)['color'])).lower()


class TesteRegras(unittest.TestCase):
    def test_cor_padrao_so_para_quem_veste_a_do_anterior(self):
        self.assertEqual(regras.ao_mudar('coordination_line', {'symbol_code': '290199', 'color': '#00B04E'},
                                         {'symbol_code': '140000'}), {'color': '#000000'})
        self.assertEqual(regras.ao_mudar('coordination_line', {'symbol_code': '290199', 'color': '#123456'},
                                         {'symbol_code': '140000'}), {})
        # o formulário regrava a cor (QColor, outra caixa) sem o operador mexer: não é escolha dele
        self.assertEqual(regras.ao_mudar('coordination_line', {'symbol_code': '290199', 'color': '#00B04E'},
                                         {'symbol_code': '140000', 'color': QColor('#00b04e')}), {'color': '#000000'})
        # a cor escolhida na mesma edição fica
        self.assertEqual(regras.ao_mudar('coordination_line', {'symbol_code': '290199', 'color': '#00B04E'},
                                         {'symbol_code': '140000', 'color': '#abcdef'}), {})
        self.assertEqual(regras.ao_mudar('military_symbol', {}, {'sidc': 'x'}), {})


class TesteGuardiao(unittest.TestCase):
    def test_formulario_nativo_aplica_a_cor_e_desfazer_volta(self):
        vl = camada('form')
        g = guardiao.garantir(vl, 'coordination_line')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        n0 = vl.undoStack().count()
        pelo_formulario(vl, fid, {'symbol_code': '140000'})
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '140000')
        self.assertEqual(cor(vl, fid), PRETO)
        self.assertEqual(g.aplicadas, 1)
        self.assertEqual(vl.undoStack().count(), n0 + 2)  # a edição do operador e a da regra
        vl.undoStack().undo()   # desfaz a regra
        self.assertEqual(cor(vl, fid), VERDE)
        vl.undoStack().undo()   # desfaz o símbolo, sem reaplicar regra
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '290199')
        self.assertEqual(cor(vl, fid), VERDE)
        self.assertEqual(vl.undoStack().count(), n0 + 2)
        vl.undoStack().redo()
        vl.undoStack().redo()
        self.assertEqual(cor(vl, fid), PRETO)
        self.assertTrue(vl.commitChanges())
        lida = QgsVectorLayer(vl.source(), 'r', 'ogr')
        self.assertEqual(str(lida.getFeature(fid)['color']).lower(), PRETO)

    def test_pior_caso_sem_guardiao_a_cor_fica(self):
        vl = camada('sem')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pelo_formulario(vl, fid, {'symbol_code': '140000'})
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '140000')
        self.assertEqual(cor(vl, fid), VERDE)  # a régua (cor preta) reprovaria este estado
        vl.rollBack()

    def test_tabela_de_atributos_e_lote(self):
        vl = camada('tabela', feicoes=[('290199', '#00B04E', False), ('290302', '#123456', False), ('140000', '#000000', False)])
        guardiao.garantir(vl, 'coordination_line')
        fids = {f['symbol_code']: f.id() for f in vl.getFeatures()}
        vl.startEditing()
        pela_tabela(vl, fids['290199'], 'symbol_code', '240701')
        self.assertEqual(vl.getFeature(fids['290199'])['symbol_code'], '240701')
        self.assertEqual(cor(vl, fids['290199']), PRETO)
        # em lote, como a calculadora de campo: um comando, três feições
        vl.beginEditCommand('Calculadora de campo')
        for fid in fids.values():
            vl.changeAttributeValue(fid, vl.fields().indexOf('symbol_code'), '290100')
        vl.endEditCommand()
        self.assertEqual(cor(vl, fids['290199']), VERDE)    # estava na padrão (preta) da 240701
        self.assertEqual(cor(vl, fids['290302']), '#123456')  # cor escolhida fica
        self.assertEqual(cor(vl, fids['140000']), VERDE)
        vl.rollBack()

    def test_bloqueada_nao_se_edita_pela_tabela(self):
        vl = camada('bloq', feicoes=[('290199', '#00B04E', True)])
        g = guardiao.garantir(vl, 'coordination_line')
        fid = next(vl.getFeatures()).id()
        antes = vl.getFeature(fid)['atualizado_em']
        vl.startEditing()
        pela_tabela(vl, fid, 'symbol_code', '140000')
        f = vl.getFeature(fid)
        self.assertEqual(f['symbol_code'], '290199')
        self.assertEqual(f['atualizado_em'], antes)
        self.assertEqual(g.revertidas, 1)
        # desbloquear pela tabela vale, e a edição seguinte passa
        pela_tabela(vl, fid, 'bloqueado', False)
        self.assertFalse(vl.getFeature(fid)['bloqueado'])
        pela_tabela(vl, fid, 'symbol_code', '140000')
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '140000')
        vl.rollBack()

    def test_pior_caso_bloqueada_sem_guardiao_muda(self):
        vl = camada('bloq_sem', feicoes=[('290199', '#00B04E', True)])
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'symbol_code', '140000')
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '140000')  # a tabela não respeita o bloqueio
        vl.rollBack()

    def test_atualizado_em(self):
        # com o estilo do plugin: o valor padrão na atualização, sem o guardião
        vl = camada('atual')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'nome', 'outro')
        self.assertGreater(vl.getFeature(fid)['atualizado_em'].toUTC().toString('yyyy-MM-ddTHH:mm:ss'), '2026-10-05T09:00:00')
        vl.rollBack()
        # camada sem o estilo do plugin: o guardião renova
        vl = camada('atual_sem_estilo', estilizar=False)
        guardiao.garantir(vl, 'coordination_line')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'nome', 'outro')
        v = vl.getFeature(fid)['atualizado_em']
        v = v.toUTC().toString('yyyy-MM-ddTHH:mm:ss') if hasattr(v, 'toUTC') else str(v)
        self.assertGreater(v, '2026-10-05T09:00:00')
        vl.rollBack()
        # pior caso: sem estilo e sem guardião, a data fica congelada (a régua acima a acusaria)
        vl = camada('atual_nada', estilizar=False)
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'nome', 'outro')
        self.assertEqual(vl.getFeature(fid)['atualizado_em'].toUTC().toString('yyyy-MM-ddTHH:mm:ss'), '2026-10-05T09:00:00')
        vl.rollBack()


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
