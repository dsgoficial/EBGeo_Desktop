# -*- coding: utf-8 -*-
"""
Dock da Medida de Coordenação: os widgets ricos que o painel da especificação monta para os
campos de `rico='medida_*'` (formulario/tipos/medida.py).

  - medida_ponto: o seletor de medida com BUSCA (por parte do nome, com ou sem acento, pela
    categoria ou pelo código), que o ValueMap nativo de 84 entradas não tem; trocar a medida
    remonta o painel, e o escalão da família, a cor padrão e a limpeza das minas e da seta
    secundária são do guardião (regras.py), como em qualquer caminho de edição;
  - medida_escalao: os 13 escalões da família da feição, mostrando o que o símbolo desenha;
  - medida_lista: a Situação do núcleo e as minas, com o desenho padrão à mostra sem gravá-lo;
  - medida_texto: o texto com o exemplo e a ajuda do catálogo do Web;
  - medida_rotacao e medida_dir_secundaria: a direção da Base de fogos e o par de azimutes do
    Setor de Tiro com a abertura, os do dock de antes.
"""
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QComboBox, QCompleter, QLabel, QVBoxLayout, QWidget

from ...formulario.tipos import medida as m

PAPEL_BUSCA = Qt.ItemDataRole.UserRole + 1


class _Completador(QCompleter):
    """Compara pelo texto de busca, mas devolve à caixa o rótulo da medida."""

    def pathFromIndex(self, index):
        return index.data(Qt.ItemDataRole.DisplayRole)


def widget_medida(painel, col, spec, valor, nulo):
    kind = spec[0]
    feat = painel.layer.getFeature(painel.fid)
    if kind == 'medida_ponto':
        return seletor_de_medida(painel, valor, nulo)
    if kind == 'medida_escalao':
        return _escalao(painel, feat, col)
    if kind == 'medida_lista':
        return _lista(painel, col, valor, nulo)
    if kind == 'medida_texto':
        w = painel._widget(col, ('texto',), valor)
        d = m.definicao(col)
        if d.get('placeholder'):
            w.setPlaceholderText(d['placeholder'])
        if d.get('help'):
            w.setToolTip(d['help'])
        return w
    e = m.entrada(feat['point_code'], feat['echelon_code']) or {}
    if kind == 'medida_rotacao':
        if e.get('setorDeTiro'):
            _setor(painel, feat)
            return painel._widget(col, ('dir_principal',), valor)
        if e.get('direcao'):
            return painel._widget(col, ('azimute',), valor)
        return painel._widget(col, ('num', -180, 180, 15, 0), valor)
    if kind == 'medida_dir_secundaria':
        if not e.get('setorDeTiro'):
            return painel._widget(col, ('num', -180, 180, 1, 0), valor)  # oculto: só o Setor de Tiro o usa
        from ..painel import texto_abertura
        _setor(painel, feat)
        spin = painel._widget(col, ('dir_secundaria',), valor)
        caixa = QWidget()
        v = QVBoxLayout(caixa)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(spin)
        painel._abertura = QLabel(texto_abertura(*painel._setor))
        v.addWidget(painel._abertura)
        caixa.spin = spin
        return caixa
    return None


def _setor(painel, feat):
    """As duas direções do Setor de Tiro em azimute, estado do painel como no dock de antes."""
    if painel._setor is None:
        from ..painel import direcoes_do_setor
        painel._setor = list(direcoes_do_setor(feat['rotation'], feat['angulo_secundario']))


def seletor_de_medida(painel, valor, nulo):
    cb = QComboBox()
    cb.setObjectName('EBGeoSeletorMedida')
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    cb.setMaxVisibleItems(20)
    for codigo, rotulo in m.opcoes_ponto(fora_do_seletor=False):
        cb.addItem(rotulo, codigo)
        cb.setItemData(cb.count() - 1, m.texto_de_busca(codigo, rotulo), PAPEL_BUSCA)
    atual = '' if nulo else str(valor)
    i = cb.findData(atual) if atual else -1
    if i < 0 and atual:
        # código fora do seletor (a Área minada pontual, 270800): mostra o nome e segue desenhando
        rotulo = m.rotulo_ponto(atual)
        cb.addItem(rotulo, atual)
        cb.setItemData(cb.count() - 1, m.texto_de_busca(atual, rotulo), PAPEL_BUSCA)
        i = cb.count() - 1
    comp = _Completador(cb.model(), cb)
    comp.setCompletionRole(PAPEL_BUSCA)
    comp.setFilterMode(Qt.MatchFlag.MatchContains)
    comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    comp.setMaxVisibleItems(15)
    cb.setCompleter(comp)
    cb.setCurrentIndex(i)
    cb.lineEdit().setPlaceholderText('Busque pelo nome, pela categoria ou pelo código')
    cb.setToolTip('Digite parte do nome (com ou sem acento), da categoria ou o código, e escolha na lista.')

    def restaurar():
        # texto digitado sem escolher: a caixa volta a mostrar a medida da feição
        if cb.currentIndex() >= 0 and cb.currentText() != cb.itemText(cb.currentIndex()):
            cb.setEditText(cb.itemText(cb.currentIndex()))
    cb.lineEdit().editingFinished.connect(restaurar)
    cb.currentIndexChanged.connect(lambda _i: _medida_mudou(painel, cb.currentData()))
    return cb


def _medida_mudou(painel, codigo):
    if painel._carregando or painel.fid is None or not codigo:
        return
    painel._pendentes['point_code'] = codigo
    painel._gravar_pendentes()
    # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
    QTimer.singleShot(0, painel._selecao_mudou)


def _escalao(painel, feat, col):
    cb = QComboBox()
    onde = m.familia_de_tela(feat['point_code'])
    if onde is None:
        cb.addItem('Não se aplica', None)  # oculto: só as famílias de escalão o usam
        cb.setEnabled(False)
        return cb
    fam, ft = onde
    for nn, rotulo in m.escaloes():
        cb.addItem(rotulo, m.chave_do_escalao(fam, nn, ft))
    # o escalão que o símbolo desenha (o padrão, quando o gravado é de outra família)
    i = cb.findData(m.codigo_desenhavel(feat['point_code'], feat['echelon_code']))
    cb.setCurrentIndex(max(i, 0))
    cb.currentIndexChanged.connect(lambda _i: painel._mudou(col, cb.currentData()))
    return cb


def _lista(painel, col, valor, nulo):
    cb = QComboBox()
    for v, rotulo in m.opcoes_lista(col):
        cb.addItem(rotulo, v)
    # sem valor gravado, mostra o desenho padrão sem gravá-lo
    i = cb.findData(m.padrao_lista(col) if nulo or not str(valor) else str(valor))
    cb.setCurrentIndex(max(i, 0))
    if m.definicao(col).get('help'):
        cb.setToolTip(m.definicao(col)['help'])
    cb.currentIndexChanged.connect(lambda _i: painel._mudou(col, cb.currentData()))
    return cb
