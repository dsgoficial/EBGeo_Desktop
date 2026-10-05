# -*- coding: utf-8 -*-
"""
Editores ricos do dock para a Área de Coordenação. O dock é montado da especificação
(formulario/tipos/area.py), a mesma do formulário nativo; aqui ficam só os widgets que o nativo
não tem, chamados por `widget_area` para os campos com rico 'area_*':

  area_tipo     o tipo da área; grava só o symbol_code (os padrões do tipo são regra do guardião,
                regras.padroes_da_troca_area), lembra o último tipo para a área nova e remonta o dock
  area_pct      a posição na borda em % (a coluna guarda de 0 a 1); a nula mostra 0 %, como o desenho
  area_lista    lista com o nulo como opção (a posição do texto: "Padrão do tipo")
  area_portoes  os portões do VAB: nome e posição na borda em %, remover, "Acrescentar portão" na
                metade da borda e "Marcar portão na borda", que espera um clique no mapa e o põe
                no ponto da borda mais próximo (Esc cancela)
  area_minas    as três posições da Área minada

Tudo grava pelo dock, no buffer de edição da camada (Salvar e Descartar).
"""
import json

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsSettings
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .. import estilos_area as ea


def _lista_json(valor):
    if valor is None or (hasattr(valor, 'isNull') and valor.isNull()):
        return []
    if isinstance(valor, (list, tuple)):
        return [dict(v) if isinstance(v, dict) else v for v in valor]
    try:
        v = json.loads(valor)
        return v if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def widget_area(painel, col, spec, valor, nulo):
    """Widget dos campos ricos da área; None para os que o painel comum monta."""
    kind = spec[0]
    if kind == 'area_tipo':
        w = QComboBox()
        for cod, sim in ea.CATALOGO_AREA.items():
            w.addItem('{} ({})'.format(sim['nome'], cod), cod)
        i = w.findData(None if nulo else str(valor))
        w.setCurrentIndex(max(i, 0))
        w.currentIndexChanged.connect(lambda _i, w=w: _tipo_mudou(painel, w.currentData()))
        return w
    if kind == 'area_lista':
        w = QComboBox()
        for v, rot in spec[1:]:
            w.addItem(rot, v)
        i = w.findData(None if nulo else str(valor))
        if i < 0 and not nulo:
            w.addItem(str(valor), str(valor))
            i = w.count() - 1
        w.setCurrentIndex(max(i, 0))
        w.currentIndexChanged.connect(lambda _i, c=col, w=w: painel._mudou(c, w.currentData()))
        return w
    if kind == 'area_pct':
        from ..formulario.tipos.area import percentual_na_borda
        w = QSpinBox()
        w.setRange(0, 100)
        w.setSuffix(' %')
        # a posição que o desenho usa, sem gravá-la: a nula é 0 %, o vértice mais ao norte
        w.setValue(percentual_na_borda(None if nulo else valor))
        w.valueChanged.connect(lambda v, c=col: painel._mudou(c, v / 100.0))
        return w
    if kind == 'area_minas':
        return EditorMinas(painel, col, valor)
    if kind == 'area_portoes':
        return EditorPortoes(painel, col, valor)
    return None


def _tipo_mudou(painel, codigo):
    if painel._carregando or painel.fid is None or not codigo:
        return
    painel._pendentes['symbol_code'] = codigo
    painel._gravar_pendentes()  # o guardião da camada aplica os padrões do tipo no mesmo passo
    QgsSettings().setValue(ea.CHAVE_ULTIMO_TIPO, codigo)
    # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
    QTimer.singleShot(0, painel._selecao_mudou)


class EditorMinas(QWidget):
    """As três posições da Área minada (Antipessoal, Anticarro, Qualquer tipo, Vazia)."""

    def __init__(self, painel, col, valor):
        super().__init__()
        self.painel, self.col = painel, col
        minas = _lista_json(valor)
        self.minas = minas if len(minas) == 3 else list(ea.MINAS_PADRAO)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.combos = []
        for i, tipo in enumerate(self.minas):
            cb = QComboBox()
            for v, rot in ea.TIPOS_MINA:
                cb.addItem(rot, v)
            cb.setCurrentIndex(max(cb.findData(tipo), 0))
            cb.currentIndexChanged.connect(lambda _i, i=i, cb=cb: self._mudou(i, cb.currentData()))
            form.addRow('Posição {}'.format(i + 1), cb)
            self.combos.append(cb)

    def _mudou(self, i, tipo):
        self.minas[i] = tipo
        self.painel._mudou(self.col, json.dumps(self.minas))


class EditorPortoes(QWidget):
    """Lista de portões: nome e posição na borda em %, remover, acrescentar e marcar no mapa."""

    def __init__(self, painel, col, valor):
        super().__init__()
        self.painel, self.col = painel, col
        self.portoes = [g for g in _lista_json(valor) if isinstance(g, dict)]
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        for i, g in enumerate(self.portoes):
            linha = QHBoxLayout()
            nome = QLineEdit(str(g.get('nome') or ''))
            nome.setPlaceholderText('Ex: PORTÃO ALFA')
            nome.editingFinished.connect(lambda i=i, ed=nome: self._editar(i, 'nome', ed.text()))
            pos = QSpinBox()
            pos.setRange(0, 100)
            pos.setSuffix(' %')
            try:
                pos.setValue(int(round(float(g.get('ratio', 0)) * 100)))
            except (TypeError, ValueError):
                pos.setValue(0)
            pos.valueChanged.connect(lambda val, i=i: self._editar(i, 'ratio', val / 100.0))
            rem = QPushButton('Remover')
            rem.clicked.connect(lambda _=False, i=i: self._remover(i))
            linha.addWidget(nome, 1)
            linha.addWidget(pos)
            linha.addWidget(rem)
            v.addLayout(linha)
        botoes = QHBoxLayout()
        b = QPushButton('Acrescentar portão')
        b.clicked.connect(lambda: self.acrescentar())
        botoes.addWidget(b)
        b = QPushButton('Marcar portão na borda')
        b.clicked.connect(self.marcar)
        botoes.addWidget(b)
        v.addLayout(botoes)
        self._ferramenta = None

    def _gravar(self, remontar=False):
        self.painel._mudou(self.col, json.dumps(self.portoes, ensure_ascii=False))
        if remontar:
            self.painel._gravar_pendentes()
            QTimer.singleShot(0, self.painel._selecao_mudou)

    def _editar(self, i, chave, valor):
        if i < len(self.portoes):
            self.portoes[i][chave] = valor
            self._gravar()

    def _remover(self, i):
        if i < len(self.portoes):
            del self.portoes[i]
            self._gravar(remontar=True)

    def acrescentar(self, ratio=0.5):
        n = len(self.portoes)
        nome = 'PORTÃO {}'.format(ea.NOMES_PORTAO[n] if n < len(ea.NOMES_PORTAO) else n + 1)
        self.portoes.append({'ratio': round(float(ratio), 4), 'nome': nome})
        self._gravar(remontar=True)

    def marcar(self):
        canvas = self.painel.iface.mapCanvas()
        feat = self.painel.layer.getFeature(self.painel.fid)
        geom = feat.geometry()
        wgs = QgsCoordinateReferenceSystem('EPSG:4326')
        if self.painel.layer.crs() != wgs:
            geom.transform(QgsCoordinateTransform(self.painel.layer.crs(), wgs, QgsProject.instance()))
        anterior = canvas.mapTool()
        ft = _MarcarPortao(canvas, anterior)

        def clicou(ponto, _botao):
            p = QgsCoordinateTransform(canvas.mapSettings().destinationCrs(), wgs, QgsProject.instance()).transform(ponto)
            r = ea.razao_na_borda(geom, p)
            ft.restaurar()
            if r is None:
                self.painel.iface.messageBar().pushWarning('EBGeo', 'Não foi possível marcar o portão nesta área.')
                return
            self.acrescentar(r)
        ft.canvasClicked.connect(clicou)
        self._ferramenta = ft
        canvas.setMapTool(ft)


class _MarcarPortao(QgsMapToolEmitPoint):
    """Um clique no mapa marca o portão; Esc cancela e volta à ferramenta anterior."""

    def __init__(self, canvas, anterior):
        super().__init__(canvas)
        self.anterior = anterior
        self.setCursor(Qt.CursorShape.CrossCursor)

    def restaurar(self):
        c = self.canvas()
        if c.mapTool() is self:
            if self.anterior is not None:
                c.setMapTool(self.anterior)
            else:
                c.unsetMapTool(self)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.restaurar()
            e.accept()
