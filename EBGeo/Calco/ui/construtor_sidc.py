# -*- coding: utf-8 -*-
"""
Construtor de SIDC: o modal "Configurar Símbolo" do EBGeo Web no QGIS.

Monta o SIDC de 30 dígitos (formato "10" mais a extensão brasileira "076"),
os amplificadores de texto e a cor, com pré-visualização pelo mesmo motor que
desenha no mapa. Os catálogos vêm de motor/catalogos.json, gerado do Web.
"""
import json
import os

from qgis.gui import QgsColorButton
from qgis.PyQt.QtCore import QByteArray, QSize, Qt
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .. import schema

ARQ_CATALOGOS = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'motor', 'catalogos.json')
_CACHE = {}


def catalogos():
    if 'c' not in _CACHE:
        with open(ARQ_CATALOGOS, encoding='utf-8') as f:
            _CACHE['c'] = json.load(f)
    return _CACHE['c']


# ---------------------------------------------------------------- SIDC

def codificar_extensao(entidade=0, comando=False, especial=0, ext_mod1=0, ext_mod2=0):
    """Extensão brasileira, dígitos 21 a 30 (brazilian_sidc_extension.js, encode)."""
    v = (int(entidade or 0) << 14) | (int(bool(comando)) << 13) | (int(especial or 0) << 10) \
        | (int(ext_mod1 or 0) << 5) | int(ext_mod2 or 0)
    return '076' + str(v).zfill(7)


def decodificar_extensao(ext):
    if not ext or len(ext) != 10 or not ext.isdigit() or ext[:3] != '076':
        return {'entidade': 0, 'comando': False, 'especial': 0, 'ext_mod1': 0, 'ext_mod2': 0}
    v = int(ext[3:])
    return {'entidade': (v >> 14) & 31, 'comando': bool((v >> 13) & 1), 'especial': (v >> 10) & 7,
            'ext_mod1': (v >> 5) & 31, 'ext_mod2': v & 31}


def montar_sidc(identidade, conjunto, status, qgft, escalao, icone, mod1, mod2, **ext):
    base = '10' + '0' + identidade + conjunto + status + qgft + escalao + icone + mod1 + mod2
    return base + codificar_extensao(**ext)


def desmontar_sidc(sidc):
    s = ''.join(ch for ch in (sidc or '') if ch.isdigit())
    if len(s) == 20:
        s += '0760000000'
    if len(s) != 30:
        return None
    d = {'identidade': s[3], 'conjunto': s[4:6], 'status': s[6], 'qgft': s[7], 'escalao': s[8:10],
         'icone': s[10:16], 'mod1': s[16:18], 'mod2': s[18:20]}
    d.update(decodificar_extensao(s[20:30]))
    return d


# ---------------------------------------------------------------- diálogo

class ConstrutorSidc(QDialog):
    def __init__(self, feicao=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Configurar símbolo militar')
        self.resize(820, 620)
        self.cat = catalogos()['militar']
        self._carregando = True
        self.textos = {}

        raiz = QHBoxLayout(self)
        esquerda = QVBoxLayout()
        raiz.addLayout(esquerda, 3)
        direita = QVBoxLayout()
        raiz.addLayout(direita, 2)

        abas = QTabWidget()
        esquerda.addWidget(abas)

        # --- aba Símbolo
        aba = QWidget()
        form = QFormLayout(aba)
        self.cb_conjunto = self._combo([(c['value'], '{} {}'.format(c['value'], c['label']))
                                        for c in self.cat['conjuntos']])
        form.addRow('Conjunto', self.cb_conjunto)
        self.cb_identidade = self._combo([(i['value'], i['label']) for i in self.cat['identidades']])
        form.addRow('Identidade', self.cb_identidade)
        self.cb_status = self._combo([(i['value'], i['label']) for i in self.cat['status']])
        form.addRow('Status', self.cb_status)
        self.cb_qgft = self._combo([(i['value'], i['label']) for i in self.cat['qgFtSimulado']])
        self.lb_qgft = QLabel('QG / FT / Simulado')
        form.addRow(self.lb_qgft, self.cb_qgft)
        self.cb_escalao = QComboBox()
        self.lb_escalao = QLabel('Escalão')
        form.addRow(self.lb_escalao, self.cb_escalao)
        self.filtro = QLineEdit()
        self.filtro.setPlaceholderText('Buscar ícone...')
        form.addRow('Ícone principal', self.filtro)
        self.lista_icones = QListWidget()
        self.lista_icones.setMinimumHeight(180)
        form.addRow(self.lista_icones)
        self.cb_mod1 = QComboBox()
        self.lb_mod1 = QLabel('Modificador 1')
        form.addRow(self.lb_mod1, self.cb_mod1)
        self.cb_mod2 = QComboBox()
        self.lb_mod2 = QLabel('Modificador 2')
        form.addRow(self.lb_mod2, self.cb_mod2)
        self.cb_especial = QComboBox()
        self.lb_especial = QLabel('Modificador especial')
        form.addRow(self.lb_especial, self.cb_especial)
        self.ck_comando = QCheckBox('Elemento de comando')
        form.addRow(self.ck_comando)
        self.cor = QgsColorButton()
        self.cor.setAllowOpacity(False)
        self.cor.setShowNull(True)
        self.cor.setToNull()
        form.addRow('Cor de preenchimento', self.cor)
        abas.addTab(aba, 'Símbolo')

        # --- aba Texto
        self.aba_texto = QWidget()
        self.form_texto = QFormLayout(self.aba_texto)
        abas.addTab(self.aba_texto, 'Texto')

        # --- aba Engajamento
        aba_eng = QWidget()
        f_eng = QFormLayout(aba_eng)
        be = self.cat['barraEngajamento']
        self.cb_estagio = self._combo([('', 'Nenhum')] + [(s['value'], s['label']) for s in be['stages']])
        self.cb_arma = self._combo([('', 'Nenhum')] + [(w['value'], w['label']) for w in be['weapons']])
        self.ck_reforco = QCheckBox('Reforço (R:)')
        f_eng.addRow('Estágio', self.cb_estagio)
        f_eng.addRow('Armamento', self.cb_arma)
        f_eng.addRow(self.ck_reforco)
        abas.addTab(aba_eng, 'Engajamento')

        # --- direita: SIDC e prévia
        caixa = QGroupBox('SIDC')
        v = QVBoxLayout(caixa)
        self.ed_sidc = QLineEdit()
        self.ed_sidc.setMaxLength(30)
        v.addWidget(self.ed_sidc)
        self.aviso = QLabel('')
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet('color: #b00020')
        v.addWidget(self.aviso)
        direita.addWidget(caixa)
        self.previa = QLabel()
        self.previa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previa.setMinimumSize(QSize(260, 260))
        self.previa.setStyleSheet('background: white; border: 1px solid #ccc')
        direita.addWidget(self.previa, 1)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        direita.addWidget(botoes)

        # sinais
        self.cb_conjunto.currentIndexChanged.connect(self._conjunto_mudou)
        for w in (self.cb_identidade, self.cb_status, self.cb_qgft, self.cb_escalao, self.cb_mod1,
                  self.cb_mod2, self.cb_especial, self.cb_estagio, self.cb_arma):
            w.currentIndexChanged.connect(self._atualizar)
        self.ck_comando.toggled.connect(self._atualizar)
        self.ck_reforco.toggled.connect(self._atualizar)
        self.cor.colorChanged.connect(self._atualizar)
        self.lista_icones.currentItemChanged.connect(self._atualizar)
        self.filtro.textChanged.connect(self._filtrar)
        self.ed_sidc.editingFinished.connect(self._sidc_digitado)

        self._carregando = False
        self._carregar_feicao(feicao)

    # ---------- utilidades
    @staticmethod
    def _combo(itens):
        cb = QComboBox()
        for valor, rotulo in itens:
            cb.addItem(rotulo, valor)
        return cb

    @staticmethod
    def _escolher(cb, valor):
        i = cb.findData(valor)
        if i >= 0:
            cb.setCurrentIndex(i)
        return i >= 0

    def _conj(self):
        return self.cat['porConjunto'].get(self.cb_conjunto.currentData(), {})

    # ---------- conjunto
    def _conjunto_mudou(self, *_):
        carregando, self._carregando = self._carregando, True
        c = self._conj()
        apl = c.get('aplicavel', {})
        # escalão / mobilidade
        self.cb_escalao.clear()
        esc = c.get('escalao') or {}
        for e in esc.get('data', []) if isinstance(esc, dict) else []:
            self.cb_escalao.addItem(e['label'], e['value'])
        if self.cb_escalao.count() == 0:
            self.cb_escalao.addItem('Não se aplica', '00')
        self.lb_escalao.setText(esc.get('label', 'Escalão') if isinstance(esc, dict) else 'Escalão')
        self.cb_escalao.setEnabled(bool(apl.get('escalao')))
        self.cb_qgft.setEnabled(bool(apl.get('qgFt')))
        # ícones
        self.lista_icones.clear()
        for ic in c.get('icones', []):
            rot = ic['nome'] + (' / ' + ic['subtipo'] if ic.get('subtipo') else '')
            it = QListWidgetItem('{}  ({})'.format(rot, ic['codigo']))
            it.setData(Qt.ItemDataRole.UserRole, (ic['codigo'], ic.get('extensao')))
            it.setToolTip(ic.get('descricao', '') or ic.get('nome_en', ''))
            self.lista_icones.addItem(it)
        if self.lista_icones.count():
            self.lista_icones.setCurrentRow(0)
        # modificadores
        for cb, chave, lb in ((self.cb_mod1, 'mod1', self.lb_mod1), (self.cb_mod2, 'mod2', self.lb_mod2)):
            cb.clear()
            for m in c.get(chave, []):
                rot = m['nome'] + ('  [{}]'.format(m['tipo']) if m.get('tipo') else '')
                cb.addItem(rot, (m['codigo'], m.get('extensao')))
            if cb.count() == 0:
                cb.addItem('Não se aplica', ('00', None))
            cb.setEnabled(bool(apl.get(chave)))
        self.cb_especial.clear()
        me = c.get('modificadorEspecial') or {}
        for m in me.get('data', []):
            self.cb_especial.addItem(m['label'], m['value'])
        if self.cb_especial.count() == 0:
            self.cb_especial.addItem('Não se aplica', '0')
        self.cb_especial.setEnabled(bool(me.get('applicable')))
        self.ck_comando.setEnabled(bool(apl.get('comando')))
        if not apl.get('comando'):
            self.ck_comando.setChecked(False)
        self._montar_textos(c)
        self._filtrar(self.filtro.text())
        self._carregando = carregando
        self._atualizar()

    def _montar_textos(self, c):
        valores = {k: w.text() for k, w in self.textos.items()}
        while self.form_texto.rowCount():
            self.form_texto.removeRow(0)
        self.textos = {}
        for campo in (c.get('camposTexto') or {}).get('fields', []):
            if campo['id'] == 'engagementBar':
                continue
            ed = QLineEdit(valores.get(campo['id'], ''))
            ed.setPlaceholderText(campo.get('placeholder', ''))
            ed.setToolTip(campo.get('tooltip', ''))
            ed.editingFinished.connect(self._atualizar)
            self.form_texto.addRow(campo['label'], ed)  # como o Web, sem a letra da norma
            self.textos[campo['id']] = ed

    def _filtrar(self, texto):
        t = (texto or '').lower()
        for i in range(self.lista_icones.count()):
            it = self.lista_icones.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    # ---------- SIDC <-> controles
    def sidc_atual(self):
        it = self.lista_icones.currentItem()
        icone, ext_ent = it.data(Qt.ItemDataRole.UserRole) if it else ('000000', None)
        m1, ext1 = self.cb_mod1.currentData() or ('00', None)
        m2, ext2 = self.cb_mod2.currentData() or ('00', None)
        return montar_sidc(
            self.cb_identidade.currentData() or '3', self.cb_conjunto.currentData() or '10',
            self.cb_status.currentData() or '0',
            (self.cb_qgft.currentData() or '0') if self.cb_qgft.isEnabled() else '0',
            (self.cb_escalao.currentData() or '00') if self.cb_escalao.isEnabled() else '00',
            icone, m1 if self.cb_mod1.isEnabled() else '00', m2 if self.cb_mod2.isEnabled() else '00',
            entidade=ext_ent or 0, comando=self.ck_comando.isChecked() and self.ck_comando.isEnabled(),
            especial=int(self.cb_especial.currentData() or 0) if self.cb_especial.isEnabled() else 0,
            ext_mod1=ext1 or 0, ext_mod2=ext2 or 0)

    def aplicar_sidc(self, sidc):
        d = desmontar_sidc(sidc)
        if d is None:
            self.aviso.setText('O SIDC precisa ter 20 ou 30 dígitos.')
            return False
        self._carregando = True
        try:
            if not self._escolher(self.cb_conjunto, d['conjunto']):
                self.aviso.setText('Conjunto {} não está no catálogo.'.format(d['conjunto']))
                return False
            self._conjunto_mudou()
            self._carregando = True
            self._escolher(self.cb_identidade, d['identidade'])
            self._escolher(self.cb_status, d['status'])
            self._escolher(self.cb_qgft, d['qgft'])
            self._escolher(self.cb_escalao, d['escalao'])
            alvo = (d['icone'], d['entidade'])
            for i in range(self.lista_icones.count()):
                cod, ext = self.lista_icones.item(i).data(Qt.ItemDataRole.UserRole)
                if cod == d['icone'] and (ext is None or ext == d['entidade']):
                    self.lista_icones.setCurrentRow(i)
                    if ext == alvo[1] or ext is None:
                        break
            for cb, cod, ext in ((self.cb_mod1, d['mod1'], d['ext_mod1']), (self.cb_mod2, d['mod2'], d['ext_mod2'])):
                for i in range(cb.count()):
                    c, e = cb.itemData(i)
                    if c == cod and (e is None or e == ext):
                        cb.setCurrentIndex(i)
                        break
            self._escolher(self.cb_especial, str(d['especial']))
            self.ck_comando.setChecked(d['comando'])
        finally:
            self._carregando = False
        self._atualizar()
        return True

    def _sidc_digitado(self):
        if self.aplicar_sidc(self.ed_sidc.text()):
            self.aviso.setText('')

    def _carregar_feicao(self, feicao):
        sidc = schema.padroes('military_symbol')['sidc']
        if feicao is not None:
            try:
                v = feicao['sidc']
                if v:
                    sidc = str(v)
            except KeyError:
                pass
        if not self.aplicar_sidc(sidc):
            self._conjunto_mudou()
        if feicao is not None:
            nomes = feicao.fields().names()
            for col, web in schema.AMPLIFICADORES:
                if web in self.textos and col in nomes and feicao[col] not in (None, ''):
                    self.textos[web].setText(str(feicao[col]))
            if 'fill_color' in nomes and feicao['fill_color']:
                self.cor.setColor(QColor(str(feicao['fill_color'])))
            if 'engagement_bar' in nomes and feicao['engagement_bar']:
                self._carregar_barra(str(feicao['engagement_bar']))
        self._atualizar()

    def _carregar_barra(self, codigo):
        reforco = codigo.startswith('R:')
        corpo = codigo[2:] if reforco else codigo
        est, _, arma = corpo.partition('-')
        self.ck_reforco.setChecked(reforco)
        self._escolher(self.cb_estagio, est)
        self._escolher(self.cb_arma, arma)

    def _barra(self):
        est = self.cb_estagio.currentData()
        if not est:
            return None
        arma = self.cb_arma.currentData()
        return ('R:' if self.ck_reforco.isChecked() else '') + est + ('-' + arma if arma else '')

    # ---------- resultado
    def valores(self):
        """Colunas do calco a gravar na feição."""
        sidc = self.sidc_atual()
        d = desmontar_sidc(sidc)
        res = {'sidc': sidc, 'special_modifier': str(d['especial']) if d['especial'] else None,
               'is_command': bool(d['comando']),
               'fill_color': None if self.cor.isNull() else self.cor.color().name()}
        web_para_col = {w: c for c, w in schema.AMPLIFICADORES}
        for web, ed in self.textos.items():
            col = web_para_col.get(web)
            if col:
                res[col] = ed.text().strip() or None
        res['engagement_bar'] = self._barra()
        return res

    def _props_web(self):
        v = self.valores()
        props = {'sidc': v['sidc'], 'fillColor': v['fill_color']}
        for col, web in schema.AMPLIFICADORES:
            if v.get(col):
                props[web] = v[col]
        return props

    def _atualizar(self, *_):
        if self._carregando:
            return
        sidc = self.sidc_atual()
        self.ed_sidc.setText(sidc)
        try:
            from ..motor.motor import Motor
            r = Motor.instancia().simbolo_militar(self._props_web())
        except Exception as e:
            self.aviso.setText('Prévia indisponível: {}'.format(e))
            return
        self.aviso.setText('' if r.get('valido', True) else 'O milsymbol considera este SIDC inválido.')
        self.previa.setPixmap(_pixmap_svg(r['svg'], self.previa.size()))


def _pixmap_svg(svg, tamanho):
    from qgis.PyQt.QtSvg import QSvgRenderer
    rend = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    vb = rend.viewBoxF()
    lado = max(10, min(tamanho.width(), tamanho.height()) - 20)
    escala = lado / max(vb.width(), vb.height(), 1)
    img = QImage(max(1, int(vb.width() * escala)), max(1, int(vb.height() * escala)), QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    rend.render(p)
    p.end()
    return QPixmap.fromImage(img)
