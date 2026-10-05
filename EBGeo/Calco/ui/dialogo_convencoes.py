# -*- coding: utf-8 -*-
"""Diálogo da ação "Quadro de convenções no layout": o layout, o mapa e o recorte."""
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                                 QVBoxLayout)

from ..convencoes import mapas_do_layout


class DialogoConvencoes(QDialog):
    def __init__(self, projeto, layout_inicial=None, mapa_inicial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Quadro de convenções do calco')
        self.projeto = projeto
        caixa = QVBoxLayout(self)
        explicacao = QLabel('Insere no layout um quadro "Convenções" com uma linha por símbolo do calco que o '
                            'mapa desenha: a figura e o nome. Rodar de novo refaz o quadro no mesmo lugar.')
        explicacao.setWordWrap(True)
        caixa.addWidget(explicacao)
        form = QFormLayout()
        self.cb_layout = QComboBox()
        self.cb_mapa = QComboBox()
        self.ck_extensao = QCheckBox('Só os símbolos das feições visíveis na extensão do mapa')
        form.addRow('Layout', self.cb_layout)
        form.addRow('Mapa', self.cb_mapa)
        caixa.addLayout(form)
        caixa.addWidget(self.ck_extensao)
        self.botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        caixa.addWidget(self.botoes)

        self.layouts = list(projeto.layoutManager().printLayouts())
        for lay in self.layouts:
            self.cb_layout.addItem(lay.name())
        self.cb_layout.currentIndexChanged.connect(self._layout_mudou)
        if layout_inicial is not None and layout_inicial in self.layouts:
            self.cb_layout.setCurrentIndex(self.layouts.index(layout_inicial))
        self._layout_mudou()
        if mapa_inicial is not None and mapa_inicial in self.mapas:
            self.cb_mapa.setCurrentIndex(self.mapas.index(mapa_inicial))

    def _layout_mudou(self, *_):
        self.cb_mapa.clear()
        lay = self.layout_escolhido()
        self.mapas = mapas_do_layout(lay) if lay is not None else []
        for m in self.mapas:
            self.cb_mapa.addItem(m.displayName())
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self.mapas))

    def layout_escolhido(self):
        i = self.cb_layout.currentIndex()
        return self.layouts[i] if 0 <= i < len(self.layouts) else None

    def mapa_escolhido(self):
        i = self.cb_mapa.currentIndex()
        return self.mapas[i] if 0 <= i < len(self.mapas) else None

    def so_extensao(self):
        return self.ck_extensao.isChecked()
