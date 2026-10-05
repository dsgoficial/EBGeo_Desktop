# -*- coding: utf-8 -*-
"""
Dock das linhas táticas sem catálogo (Linha de Limite, Seta, Frente Ocupada): o que o painel
da especificação monta além dos widgets comuns.

  - Linha de Limite: o editor das posições do símbolo (`symbol_instances`), como o do Web:
    Repetições de 1 a 6 (redistribui as posições por igual), e uma linha por símbolo com a
    posição de 1 % a 99 %, Mostrar rótulos e Remover. Ocupa o lugar do resumo só de leitura que
    o formulário nativo mostra (formulario/tipos/taticos.py, RESUMO_POSICOES). A leitura e a
    normalização da lista são as funções puras de regras.py, as mesmas do guardião.
  - Caixas das colunas booleanas que o estilo lê com padrão (Mostrar ponta, Seta nas duas
    pontas, Aeromóvel, Texto sempre para o norte): a coluna nula aparece no estado que o estilo
    desenha, e nada se grava até o operador mudar a caixa.
  - Linha de Limite e Seta: o botão "Inverter sentido", como no dock de antes.
"""
import json

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from ... import regras
from ...formulario import especificacao as esp
from ...formulario.tipos.taticos import CAIXA_PADRAO, RESUMO_POSICOES

TIPOS_INVERTER = ('boundary', 'arrow')
ROTULO_POSICOES = 'Posições do símbolo'


class EditorPosicoes(QWidget):
    """A lista de posições do símbolo do Limite. `ao_mudar(texto_json)` recebe a lista nova."""

    def __init__(self, valor, ao_mudar, parent=None):
        super().__init__(parent)
        self.setObjectName('EBGeoEditorPosicoes')
        self.ao_mudar = ao_mudar
        self.lista, self.legivel = regras.ler_instancias_limite(valor)
        self._montando = False
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        topo = QHBoxLayout()
        topo.addWidget(QLabel('Repetições'))
        self.repeticoes = QSpinBox()
        self.repeticoes.setRange(1, regras.MAX_INSTANCIAS_LIMITE)
        self.repeticoes.setToolTip('Quantos símbolos de escalão ao longo da linha; muda as posições para '
                                   'espaçá-los por igual, como no EBGeo Web.')
        self.repeticoes.valueChanged.connect(self._repeticoes_mudou)
        topo.addWidget(self.repeticoes)
        topo.addStretch(1)
        v.addLayout(topo)
        self.linhas = QVBoxLayout()
        self.linhas.setContentsMargins(0, 0, 0, 0)
        v.addLayout(self.linhas)
        self.posicoes, self.rotulos, self.remover = [], [], []
        self._montar()

    def _montar(self):
        self._montando = True
        try:
            while self.linhas.count():
                w = self.linhas.takeAt(0).widget()
                if w is not None:
                    w.hide()
                    w.setParent(None)
                    w.deleteLater()
            self.posicoes, self.rotulos, self.remover = [], [], []
            self.repeticoes.setValue(min(len(self.lista), regras.MAX_INSTANCIAS_LIMITE))
            for i, inst in enumerate(self.lista):
                linha = QWidget()
                h = QHBoxLayout(linha)
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(QLabel('Símbolo {}'.format(i + 1)))
                pos = QSpinBox()
                pos.setRange(1, 99)
                pos.setSuffix(' %')
                pos.setToolTip('Posição do símbolo, em % do comprimento da linha a partir do início.')
                pos.setValue(int(round(inst['ratio'] * 100)))
                pos.valueChanged.connect(lambda val, i=i: self._posicao_mudou(i, val))
                h.addWidget(pos)
                cb = QCheckBox('Rótulos')
                cb.setToolTip('Mostra o rótulo superior e o inferior junto deste símbolo.')
                cb.setChecked(inst['showLabels'])
                cb.toggled.connect(lambda val, i=i: self._rotulo_mudou(i, val))
                h.addWidget(cb)
                rm = QToolButton()
                rm.setText('✕')
                rm.setToolTip('Remover este símbolo')
                rm.setEnabled(len(self.lista) > 1)
                rm.clicked.connect(lambda _=False, i=i: self._remover(i))
                h.addWidget(rm)
                h.addStretch(1)
                self.linhas.addWidget(linha)
                self.posicoes.append(pos)
                self.rotulos.append(cb)
                self.remover.append(rm)
        finally:
            self._montando = False

    def _emitir(self):
        self.ao_mudar(json.dumps(self.lista))

    def _repeticoes_mudou(self, n):
        if self._montando or n == len(self.lista):
            return
        self.lista = regras.redistribuir_instancias(self.lista, n)
        self._emitir()
        QTimer.singleShot(0, self._montar)  # as linhas são remontadas fora do sinal

    def _posicao_mudou(self, i, val):
        if self._montando or i >= len(self.lista):
            return
        self.lista[i] = dict(self.lista[i], ratio=val / 100.0)
        self._emitir()

    def _rotulo_mudou(self, i, val):
        if self._montando or i >= len(self.lista):
            return
        self.lista[i] = dict(self.lista[i], showLabels=bool(val))
        self._emitir()

    def _remover(self, i):
        if self._montando or len(self.lista) <= 1 or i >= len(self.lista):
            return
        self.lista = [inst for k, inst in enumerate(self.lista) if k != i]
        self._emitir()
        # apagar o botão dentro do próprio clique derruba o QGIS: remonta fora do sinal
        QTimer.singleShot(0, self._montar)


def elemento_rico(painel, fl, el, conds, attrs, travada):
    """
    Monta no dock o widget rico que substitui um elemento da especificação. Devolve False quando o
    elemento não é deste bloco (o painel o monta como sempre).
    """
    if isinstance(el, esp.Campo) and el.rico == CAIXA_PADRAO:
        return _caixa_padrao(painel, fl, el, conds, attrs, travada)
    if not (isinstance(el, esp.Texto) and el.nome == RESUMO_POSICOES):
        return False
    if 'symbol_instances' not in attrs:
        return True
    caixa = QWidget()
    v = QVBoxLayout(caixa)
    v.setContentsMargins(0, 4, 0, 4)
    v.addWidget(QLabel(ROTULO_POSICOES))
    editor = EditorPosicoes(attrs['symbol_instances'], lambda texto: painel._mudou('symbol_instances', texto))
    v.addWidget(editor)
    if not editor.legivel:
        aviso = QLabel('As posições gravadas não se leem; o desenho usa um símbolo no meio da linha.')
        aviso.setWordWrap(True)
        v.addWidget(aviso)
    fl.addRow(caixa)
    if travada:
        editor.setEnabled(False)
    painel.widgets['symbol_instances'] = editor
    # entra nas linhas do painel como campo, para valer a condição e contar entre os visíveis
    campo = esp.Campo('symbol_instances', ROTULO_POSICOES, esp.oculto(), rico=RESUMO_POSICOES)
    painel._linhas.append((campo, list(conds), fl, caixa, None))
    return True


def _caixa_padrao(painel, fl, el, conds, attrs, travada):
    """A caixa da coluna booleana: nula mostra o padrão do estilo (rico_config[0]) sem gravá-lo."""
    if el.coluna not in attrs:
        return True
    v = attrs[el.coluna]
    cb = QCheckBox()
    cb.setChecked(bool(el.rico_config[0]) if esp._nulo(v) else bool(v))
    cb.toggled.connect(lambda val, c=el.coluna: painel._mudou(c, bool(val)))
    if travada:
        cb.setEnabled(False)
    from ..painel import altura_uniforme  # o passo das linhas da seção, como os demais campos
    altura_uniforme(cb)
    rotulo = QLabel(el.rotulo_para(attrs, rico=True))
    fl.addRow(rotulo, cb)
    painel.widgets[el.coluna] = cb
    painel._linhas.append((el, list(conds) + ([el.condicao] if el.condicao is not None else []), fl, cb, rotulo))
    return True
