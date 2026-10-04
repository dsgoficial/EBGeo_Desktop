# -*- coding: utf-8 -*-
"""
Seletor de símbolo de engenharia (C 5-36, tabela 6-4): o modal do EBGeo Web no QGIS.

Item, variante e o formulário do item vêm do catalogos.json; o rascunho padrão,
a validação e o desenho vêm do mesmo motor que desenha no mapa.
"""
import json

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QVBoxLayout, QWidget,
)

from .construtor_sidc import _pixmap_svg, catalogos

# Itens em que a variante é o próprio valor de um campo (o desenho segue o campo).
VARIANTE_POR_CAMPO = {20: ('foliage', ['temporary', 'permanent']),
                      21: ('foliage', ['temporary', 'permanent'])}


def _itens():
    return {str(it['codigo']): it for it in catalogos()['engenharia']['itens']}


class SeletorEngenharia(QDialog):
    def __init__(self, point_code=None, engineering=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Símbolo de engenharia (C 5-36)')
        self.resize(760, 520)
        self.itens = _itens()
        self.campos = {}
        self._carregando = True

        raiz = QHBoxLayout(self)
        esq = QVBoxLayout()
        raiz.addLayout(esq, 3)
        dir_ = QVBoxLayout()
        raiz.addLayout(dir_, 2)

        topo = QFormLayout()
        self.cb_item = QComboBox()
        for cod, it in sorted(self.itens.items(), key=lambda kv: int(kv[1]['numero'])):
            self.cb_item.addItem('{}. {}'.format(it['numero'], it['titulo']), cod)
        topo.addRow('Item', self.cb_item)
        self.cb_variante = QComboBox()
        self.lb_variante = QLabel('Variante')
        topo.addRow(self.lb_variante, self.cb_variante)
        esq.addLayout(topo)
        self.descricao = QLabel()
        self.descricao.setWordWrap(True)
        self.descricao.setStyleSheet('color: #555')
        esq.addWidget(self.descricao)
        self.host = QWidget()
        self.form = QFormLayout(self.host)
        esq.addWidget(self.host)
        esq.addStretch(1)

        self.erros = QLabel()
        self.erros.setWordWrap(True)
        self.erros.setStyleSheet('color: #b00020')
        dir_.addWidget(self.erros)
        self.previa = QLabel()
        self.previa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previa.setMinimumSize(QSize(260, 240))
        self.previa.setStyleSheet('background: white; border: 1px solid #ccc')
        dir_.addWidget(self.previa, 1)
        self.botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        dir_.addWidget(self.botoes)

        self.cb_item.currentIndexChanged.connect(self._item_mudou)
        self.cb_variante.currentIndexChanged.connect(self._variante_mudou)

        # estado inicial
        eng = engineering
        if isinstance(eng, str):
            try:
                eng = json.loads(eng)
            except ValueError:
                eng = None
        i = self.cb_item.findData(str(point_code)) if point_code else -1
        self.cb_item.setCurrentIndex(max(i, 0))
        self._carregando = False
        self._item_mudou(dados=eng if i >= 0 else None)

    # ---------- montagem
    def _item(self):
        return self.itens[self.cb_item.currentData()]

    def _item_mudou(self, *_args, dados=None):
        if self._carregando:
            return
        self._carregando = True
        try:
            it = self._item()
            rasc = self._rascunho(it, dados)
            self.cb_variante.clear()
            for v in it['variantes']:
                self.cb_variante.addItem(v['rotulo'], v['indice'])
            self.cb_variante.setCurrentIndex(max(self.cb_variante.findData(rasc.get('variant', 0)), 0))
            muitas = len(it['variantes']) > 1
            self.cb_variante.setVisible(muitas)
            self.lb_variante.setVisible(muitas)
            if it.get('rotuloVariante'):
                self.lb_variante.setText(it['rotuloVariante'])
            self.descricao.setText(' '.join(x for x in (it.get('fixo'), it.get('extra')) if x))
            self._montar_campos(it, rasc.get('values', {}))
        finally:
            self._carregando = False
        self._atualizar()

    def _rascunho(self, it, dados):
        try:
            from ..motor.motor import Motor
            return Motor.instancia().engenharia_rascunho(it['codigo'], dados or {})
        except Exception:
            return dados or it['rascunhoPadrao']

    def _montar_campos(self, it, valores):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.campos = {}
        for c in it['campos']:
            v = valores.get(c['chave'], c.get('padrao'))
            if c['tipo'] == 'checkbox':
                w = QCheckBox()
                w.setChecked(bool(v))
                w.toggled.connect(self._campo_mudou)
            elif c['tipo'] == 'select':
                w = QComboBox()
                for o in c.get('opcoes', []):
                    w.addItem(o['rotulo'], o['valor'])
                w.setCurrentIndex(max(w.findData(v), 0))
                w.currentIndexChanged.connect(self._campo_mudou)
            else:
                w = QLineEdit('' if v is None else str(v))
                w.setPlaceholderText('número ou ?' if c['tipo'] in ('integer', 'decimal') else '')
                w.setMaxLength(40)
                w.textChanged.connect(self._campo_mudou)
            if c.get('ajuda'):
                w.setToolTip(c['ajuda'])
            self.form.addRow(c['rotulo'], w)
            self.campos[c['chave']] = (c, w)

    # ---------- sincronia variante <-> campo (itens 20 e 21)
    def _variante_mudou(self, *_):
        if self._carregando:
            return
        n = int(self._item()['numero'])
        if n in VARIANTE_POR_CAMPO:
            chave, valores = VARIANTE_POR_CAMPO[n]
            idx = self.cb_variante.currentData() or 0
            if chave in self.campos and idx < len(valores):
                w = self.campos[chave][1]
                self._carregando = True
                w.setCurrentIndex(max(w.findData(valores[idx]), 0))
                self._carregando = False
        self._atualizar()

    def _campo_mudou(self, *_):
        if self._carregando:
            return
        n = int(self._item()['numero'])
        if n in VARIANTE_POR_CAMPO:
            chave, valores = VARIANTE_POR_CAMPO[n]
            v = self.valores_campos().get(chave)
            if v in valores:
                self._carregando = True
                self.cb_variante.setCurrentIndex(max(self.cb_variante.findData(valores.index(v)), 0))
                self._carregando = False
        self._atualizar()

    # ---------- resultado
    def valores_campos(self):
        res = {}
        for chave, (c, w) in self.campos.items():
            if c['tipo'] == 'checkbox':
                res[chave] = w.isChecked()
            elif c['tipo'] == 'select':
                res[chave] = w.currentData()
            else:
                res[chave] = w.text().strip()
        return res

    def engineering(self):
        return {'variant': int(self.cb_variante.currentData() or 0), 'values': self.valores_campos()}

    def valores(self):
        """Colunas do calco a gravar na feição."""
        return {'point_code': self.cb_item.currentData(), 'engineering': json.dumps(self.engineering())}

    def _atualizar(self):
        if self._carregando:
            return
        try:
            from ..motor.motor import Motor
            m = Motor.instancia()
            erros = m.engenharia_erros(self.cb_item.currentData(), self.valores_campos()) or []
            r = m.engenharia({'pointCode': self.cb_item.currentData(), 'engineering': self.engineering()})
        except Exception as e:
            self.erros.setText('Prévia indisponível: {}'.format(e))
            return
        self.erros.setText('\n'.join(x.get('message', '') for x in erros))
        self.botoes.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not erros)
        self.previa.setPixmap(_pixmap_svg(r['svg'], self.previa.size()))
