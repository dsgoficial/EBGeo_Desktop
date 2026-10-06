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
  - Seta combinada (a geometria com mais de um ramo): uma seção por ramo com a largura, o
    aeromóvel, a ponta e a ponta dupla, como o painel do Web (_addBranchGeometryControls de
    arrow_attributes_panel.js). Grava a coluna `ramos` pelas funções puras de regras.py
    (ramos_desenhados, editar_ramo): mostra o que o estilo desenha em cada ramo e muda só o ramo.
    Ocupa o lugar do resumo que o formulário nativo mostra (RESUMO_RAMOS).
"""
import json

from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import (
    QCheckBox, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from ... import regras
from ...formulario import especificacao as esp
from ...formulario.tipos.taticos import CAIXA_PADRAO, RESUMO_POSICOES, RESUMO_RAMOS

TIPOS_INVERTER = ('boundary', 'arrow')
ROTULO_POSICOES = 'Posições do símbolo'
ROTULO_RAMOS = 'Ramos da seta combinada'


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


class EditorRamos(QWidget):
    """
    Os ramos da Seta combinada, um por parte da geometria: "Ramo N" com Largura, Aeromóvel /
    Aeroterrestre, Mostrar Seta e Seta nas Duas Pontas, os controles e os rótulos do painel do Web.
    `ler()` dá (coluna `ramos`, {coluna da feição: valor}) da feição no buffer; `ao_mudar(ramos,
    regravar)` recebe a coluna `ramos` nova e as colunas da feição que voltam à importação
    (regras.editar_ramo).
    """

    def __init__(self, ler, n, ao_mudar, parent=None):
        super().__init__(parent)
        self.setObjectName('EBGeoEditorRamos')
        self.ler, self.n, self.ao_mudar = ler, n, ao_mudar
        self._montando = True
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.largura, self.caixas = [], []
        for i in range(n):
            v.addWidget(QLabel('<b>Ramo {}</b>'.format(i + 1)))
            fl = QFormLayout()
            fl.setContentsMargins(0, 0, 0, 0)
            larg = QSpinBox()
            larg.setRange(10, 10000)
            larg.setSuffix(' m')
            larg.valueChanged.connect(lambda val, i=i: self._mudou(i, 'width', float(val)))
            fl.addRow('Largura', larg)
            caixas = {}
            for chave, rotulo in ROTULOS_RAMO:
                cb = QCheckBox()
                cb.toggled.connect(lambda val, i=i, chave=chave: self._mudou(i, chave, bool(val)))
                fl.addRow(rotulo, cb)
                caixas[chave] = cb
            v.addLayout(fl)
            self.largura.append(larg)
            self.caixas.append(caixas)
        self.reler()

    def reler(self):
        """Os valores que o estilo desenha em cada ramo, lidos da feição no buffer, sem gravar."""
        self._montando = True
        try:
            ramos, colunas = self.ler()
            for i, r in enumerate(regras.ramos_desenhados(ramos, colunas, self.n)):
                self.largura[i].setValue(int(round(r['width'])))
                for chave, cb in self.caixas[i].items():
                    cb.setChecked(bool(r[chave]))
        finally:
            self._montando = False

    def _mudou(self, i, chave, val):
        if self._montando:
            return
        ramos, colunas = self.ler()
        novo, regravar = regras.editar_ramo(ramos, colunas, self.n, i, chave, val)
        self.ao_mudar(novo, regravar)


# Os rótulos do painel do Web (arrow_attributes_panel.js), na ordem dele, depois da largura.
ROTULOS_RAMO = (('airmobile', 'Aeromóvel / Aeroterrestre'), ('showArrowHead', 'Mostrar Seta'),
                ('doubleHeaded', 'Seta nas Duas Pontas'))


def _partes(painel):
    f = painel.layer.getFeature(painel.fid) if painel.fid is not None else None
    g = f.geometry() if f is not None and f.isValid() else None
    return g.constGet().numGeometries() if g is not None and not g.isEmpty() and g.isMultipart() else 1


def _editor_ramos(painel, fl, el, conds, attrs, travada):
    """O editor dos ramos, só na Seta de mais de um ramo; a seta simples não mostra nada aqui."""
    n = _partes(painel)
    if 'ramos' not in attrs or n < 2:
        return True
    nulos = {c: n0 for _w, c, n0 in regras.CHAVES_RAMO_DOCK}
    colunas = [c for _w, c, _n in regras.CHAVES_RAMO_DOCK] + [c for _w, c in regras._OUTRAS_RAMO]

    def ler():
        painel._gravar_pendentes()  # a mudança da seta inteira ainda no relógio do dock
        f = painel.layer.getFeature(painel.fid)
        return f['ramos'], {c: f[c] for c in colunas}

    def gravar(ramos, regravar):
        painel._mudou('ramos', json.dumps(ramos))
        for col, val in regravar.items():
            painel._mudou(col, val)
        painel._gravar_pendentes()
        # a coluna da feição que voltou à importação aparece no campo da seta inteira, sem gravar de novo
        painel._carregando = True
        try:
            for col, val in regravar.items():
                w = painel.widgets.get(col)
                if isinstance(w, QCheckBox):  # a caixa de padrão do estilo (fora de _tipos_widget)
                    w.setChecked(nulos[col] if esp._nulo(val) else bool(val))
                elif w is not None:
                    painel._mostrar_valor(col, val)
        finally:
            painel._carregando = False
    caixa = QWidget()
    v = QVBoxLayout(caixa)
    v.setContentsMargins(0, 4, 0, 4)
    v.addWidget(QLabel(ROTULO_RAMOS))
    editor = EditorRamos(ler, n, gravar)
    v.addWidget(editor)
    fl.addRow(caixa)
    if travada:
        editor.setEnabled(False)
    painel.widgets['ramos'] = editor
    campo = esp.Campo('ramos', ROTULO_RAMOS, esp.oculto(), rico=RESUMO_RAMOS)
    painel._linhas.append((campo, list(conds), fl, caixa, None))
    return True


def elemento_rico(painel, fl, el, conds, attrs, travada):
    """
    Monta no dock o widget rico que substitui um elemento da especificação. Devolve False quando o
    elemento não é deste bloco (o painel o monta como sempre).
    """
    if isinstance(el, esp.Campo) and el.rico == CAIXA_PADRAO:
        return _caixa_padrao(painel, fl, el, conds, attrs, travada)
    if isinstance(el, esp.Texto) and el.nome == RESUMO_RAMOS:
        return _editor_ramos(painel, fl, el, conds, attrs, travada)
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
