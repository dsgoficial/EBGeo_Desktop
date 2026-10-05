# -*- coding: utf-8 -*-
"""
Painel de propriedades do calco: espelha os painéis do EBGeo Web para a feição
selecionada na camada ativa.

Tipos com especificação de formulário (formulario/especificacao.py; no piloto, a Linha de
Coordenação): o painel é montado da especificação, a mesma do formulário nativo assado no estilo,
e cada mudança entra no BUFFER de edição da camada como um comando (Ctrl+Z desfaz), aberto pelo
painel se preciso; nada vai ao disco até "Salvar", e "Descartar" volta ao estado de antes. As
regras de troca (cor padrão ao trocar o símbolo) são do guardião da camada (guardiao.py).

Demais tipos, até a escala: cada mudança grava na camada (no buffer de edição, se a camada
estiver em edição; senão, direto) e, nos símbolos pontuais, regera o SVG.
"""
import json
import math

from qgis.core import (
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeatureRequest, QgsProject,
    QgsVectorLayer, QgsGeometry,
)
from qgis.gui import QgsCollapsibleGroupBoxBasic, QgsColorButton
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from .. import schema
from ..calco import tipo_da_camada
from ..formulario import especificacao as esp
from ..regras import cor_ao_trocar_simbolo_linha  # noqa: F401 (as regras saíram do painel para regras.py)

# Ø (Equipe/Guarnição) e ++ (Valor indeterminado) entraram em 2026-10-04 (MD33-C-01 A.3.5.7);
# o XXXXX fica por decisão do chefe.
ESCALOES_LIMITE = ['XXXXXX', 'XXXXX', 'XXXX', 'XXX', 'XX', 'X', 'III', 'II', 'I', 'ooo', 'oo', 'o', 'Ø', '++']

# Escolhas de desenho que valem só para o tipo que as tem (desenhos-parametricos.js do Web).
CAMPOS_MINA = ('mina1', 'mina2', 'mina3')
ANGULO_SECUNDARIO_PADRAO = -45.0

STATUS_NUCLEO = [('ocupado', 'Ocupado'), ('preparado', 'Preparado'),
                 ('preparado-nao-ocupado', 'Preparado, não ocupado')]

# Widgets: ('texto'), ('cor'), ('num', min, max, passo, casas), ('bool'),
# ('combo', [(valor, rótulo)]), ('km_em_m', min_m, max_m, passo_m), ('texto_multilinha')
_COMUNS = [('nome', 'Nome', ('texto',)), ('descricao', 'Descrição', ('texto',))]
_ZOOM = [('zoom_corr', 'Correção de zoom (preso ao terreno)', ('bool',)),
         ('created_zoom', 'Zoom de referência', ('num', 0, 22, 0.1, 1))]
_ICONE = [('size', 'Tamanho', ('num', 0.1, 5, 0.1, 2)),
          ('rotation', 'Rotação (graus)', ('num', -180, 180, 15, 0)),
          ('opacity', 'Opacidade', ('num', 0, 1, 0.05, 2)),
          ('fill_color', 'Cor de preenchimento', ('cor',))] + _ZOOM
_TRACO = [('color', 'Cor', ('cor',)),
          ('line_width', 'Espessura (px)', ('num', 1, 10, 1, 0)),
          ('opacity', 'Opacidade', ('num', 0, 1, 0.05, 2))]

PAINEIS = {
    'military_symbol': [('sidc', 'SIDC', ('sidc',))]
    + [(c, rot, ('texto',)) for c, rot in [
        ('unique_designation', 'Designação (T)'), ('higher_formation', 'Escalão superior (M)'),
        ('additional_information', 'Informação adicional (H)'), ('reinforced_reduced', 'Reforço/redução (F)'),
        ('quantity', 'Quantidade (C)'), ('date_time_group', 'Grupo data-hora (W)'),
        ('location', 'Localização (Y)'), ('speed', 'Velocidade (Z)'), ('direction', 'Direção (Q)'),
        ('altitude_depth', 'Altitude (X)'), ('special_headquarters', 'QG especial (AA)'),
        ('type_amplifier', 'Tipo (V)'), ('iff_sif', 'IFF/SIF (P)'), ('credibility', 'Avaliação (J)'),
        ('equipment_teardown_time', 'Tempo de desmontagem (AE)'), ('engagement_bar', 'Barra de engajamento (AO)')]]
    + _ICONE,
    'coordination_measure': [('point_code', 'Medida', ('medida',)), ('echelon_code', 'Escalão', ('escalao_medida',)),
                             ('status', 'Situação do núcleo', ('combo', STATUS_NUCLEO))]
    + [(c, rot, ('texto',)) for c, rot in [
        ('tipo', 'Tipo'), ('identificacao', 'Identificação'), ('gdh_ini', 'GDH início'), ('gdh_fim', 'GDH fim'),
        ('numero', 'Número'), ('numero_concentracao', 'Número da concentração'), ('altitude', 'Altitude')]]
    + _ICONE,
    'engineering_symbol': [('point_code', 'Símbolo (C 5-36)', ('engenharia',))] + _ICONE,
    'magnetic_declination': [('declination', 'Declinação (graus)', ('leitura',)),
                             ('convergence', 'Convergência (graus)', ('leitura',)),
                             ('calculation_date', 'Data do cálculo', ('leitura',)),
                             ('size', 'Tamanho', ('num', 0.1, 5, 0.1, 2)),
                             ('fill_color', 'Cor', ('cor',))] + _ZOOM,
    'boundary': [('echelon', 'Escalão', ('combo', [(e, e) for e in ESCALOES_LIMITE])),
                 ('symbol_size_km', 'Tamanho do símbolo (m)', ('km_em_m', 1, 50000, 10)),
                 ('symbol_instances', 'Posições (% do comprimento)', ('instancias',)),
                 ('text_top', 'Rótulo superior', ('texto',)),
                 ('text_bottom', 'Rótulo inferior', ('texto',)),
                 ('text_size', 'Tamanho do texto', ('num', 8, 80, 1, 0)),
                 ('text_distance_ratio', 'Distância do texto', ('num', 0.1, 3.0, 0.1, 1)),
                 ('text_north_facing', 'Texto sempre para o norte', ('bool',))] + _TRACO + _ZOOM,
    'arrow': [('width_m', 'Largura (m)', ('num', 10, 10000, 10, 0)),
              ('head_length_ratio', 'Comprimento da ponta', ('num', 0.2, 5, 0.1, 1)),
              ('show_arrow_head', 'Mostrar ponta', ('bool',)),
              ('double_headed', 'Seta nas duas pontas', ('bool',)),
              ('airmobile', 'Aeromóvel / aeroterrestre', ('bool',)),
              ('airmobile_position', 'Posição do aeromóvel', ('num', 0.05, 0.95, 0.05, 2)),
              ('fill_color', 'Preenchimento', ('cor',)),
              ('line_color', 'Borda', ('cor',)),
              ('fill_opacity', 'Opacidade do preenchimento', ('num', 0, 1, 0.05, 2)),
              ('line_width', 'Espessura da borda (px)', ('num', 1, 10, 1, 0))],
    'occupied_front': list(_TRACO),
}
PAINEIS['coordination_area'] = []  # o formulário depende do tipo: ui/painel_area.linhas_area


def tem_painel(tipo):
    return tipo in PAINEIS or tipo in esp.TIPOS_COM_FORMULARIO


class PainelCalco(QDockWidget):
    def __init__(self, iface, abrir_construtor_sidc=None, parent=None):
        super().__init__('Calco: propriedades', parent or iface.mainWindow())
        self.setObjectName('EBGeoCalcoPainel')
        self.iface = iface
        self.abrir_construtor_sidc = abrir_construtor_sidc
        self.layer = None
        self.tipo = None
        self.fid = None
        self._carregando = False
        self.widgets = {}
        self._setor = None      # [principal, secundária] do Setor de Tiro, em azimute
        self._abertura = None   # QLabel "Abertura do setor"
        base = QWidget()
        self.vbox = QVBoxLayout(base)
        self.titulo = QLabel('Selecione uma feição do calco.')
        self.titulo.setWordWrap(True)
        self.vbox.addWidget(self.titulo)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.vbox.addWidget(self.form_host)
        self.acoes = QHBoxLayout()
        self.vbox.addLayout(self.acoes)
        self.vbox.addStretch(1)
        # Salvar e Descartar, como no Web: só nos tipos montados da especificação
        self.barra_edicao = QWidget()
        h = QHBoxLayout(self.barra_edicao)
        h.setContentsMargins(4, 4, 4, 4)
        self.estado_edicao = QLabel('')
        h.addWidget(self.estado_edicao, 1)
        self.botao_descartar = QPushButton('Descartar')
        self.botao_descartar.setToolTip('Volta a camada ao estado de antes das mudanças feitas no painel.')
        self.botao_descartar.clicked.connect(self.descartar)
        self.botao_salvar = QPushButton('Salvar')
        self.botao_salvar.setToolTip('Grava no calco as mudanças da camada.')
        self.botao_salvar.clicked.connect(self.salvar)
        h.addWidget(self.botao_descartar)
        h.addWidget(self.botao_salvar)
        self.barra_edicao.hide()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(base)
        corpo = QWidget()
        v = QVBoxLayout(corpo)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(sc, 1)
        v.addWidget(self.barra_edicao)
        self.setWidget(corpo)
        self._sessoes = {}      # id da camada -> {'indice': da pilha de desfazer, 'abriu': a edição}
        self._spec = None       # especificação do tipo montado (None nos tipos de antes)
        self._linhas = []       # (elemento, condições, layout, widget, rótulo) do painel da especificação
        self._secoes = []       # (caixa, condições, layout pai)
        self._expressoes = {}
        self._gravar_timer = QTimer(self)
        self._gravar_timer.setSingleShot(True)
        self._gravar_timer.setInterval(350)
        self._gravar_timer.timeout.connect(self._gravar_pendentes)
        self._pendentes = {}
        iface.currentLayerChanged.connect(self._camada_mudou)
        self._camada_mudou(iface.activeLayer())

    # ---------- seleção ----------
    def _camada_mudou(self, layer):
        if self.layer is not None:
            for sinal, slot in ((self.layer.selectionChanged, self._selecao_mudou),
                                (self.layer.editingStopped, self._edicao_parou)):
                try:
                    sinal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
        self.layer = layer if isinstance(layer, QgsVectorLayer) else None
        self.tipo = tipo_da_camada(self.layer)
        if self.layer is not None and tem_painel(self.tipo):
            self.layer.selectionChanged.connect(self._selecao_mudou)
            self.layer.editingStopped.connect(self._edicao_parou)
            if self.tipo in esp.TIPOS_COM_FORMULARIO:
                from .. import guardiao
                guardiao.garantir(self.layer, self.tipo)
        self._selecao_mudou()

    def mostrar_feicao(self, layer, ebgeo_id):
        """Seleciona e mostra a feição recém-criada."""
        if self.iface.activeLayer() is not layer:
            self.iface.setActiveLayer(layer)
        req = QgsFeatureRequest().setFilterExpression('"ebgeo_id" = \'{}\''.format(ebgeo_id))
        ids = [f.id() for f in layer.getFeatures(req)]
        layer.selectByIds(ids)

    def _selecao_mudou(self, *args):
        self._gravar_pendentes()
        self._limpar()
        self._atualizar_barra()
        if self.layer is None or not tem_painel(self.tipo):
            self.titulo.setText('Selecione uma feição do calco.')
            return
        sel = self.layer.selectedFeatureIds()
        if len(sel) != 1:
            self.titulo.setText('{}: selecione uma feição ({} selecionadas).'.format(
                schema.TIPOS[self.tipo]['nome_pt'], len(sel)))
            return
        self.fid = sel[0]
        feat = self.layer.getFeature(self.fid)
        self.titulo.setText('<b>{}</b>'.format(schema.TIPOS[self.tipo]['nome_pt']))
        if self.tipo in esp.TIPOS_COM_FORMULARIO:
            self._montar_spec(feat)
        else:
            self._montar(feat)

    def _limpar(self):
        self.fid = None
        self.widgets = {}
        self._setor = None
        self._abertura = None
        self._spec = None
        self._linhas = []
        self._secoes = []
        while self.form.rowCount():
            self.form.removeRow(0)
        while self.acoes.count():
            w = self.acoes.takeAt(0).widget()
            if w:
                w.hide()  # o deleteLater só apaga na volta ao laço de eventos
                w.setParent(None)
                w.deleteLater()

    # ---------- formulário ----------
    def _montar(self, feat):
        self._carregando = True
        try:
            linhas = PAINEIS[self.tipo]
            if self.tipo == 'coordination_measure':
                linhas = linhas_medida(feat['point_code'])
                if self.layer.fields().indexOf('angulo_secundario') >= 0:
                    self._setor = list(direcoes_do_setor(feat['rotation'], feat['angulo_secundario']))
            elif self.tipo == 'coordination_area':
                from .painel_area import linhas_area
                linhas = linhas_area(feat)
            for col, rotulo, spec in _COMUNS + linhas:
                if self.layer.fields().indexOf(col) < 0:
                    continue
                w = self._widget(col, spec, feat[col])
                if w is not None:
                    self.form.addRow(rotulo, w)
                    if spec[0] == 'dir_secundaria':
                        self._abertura = QLabel(texto_abertura(*self._setor))
                        self.form.addRow('', self._abertura)
            if self.tipo in ('boundary', 'arrow'):
                b = QPushButton('Inverter sentido')
                b.clicked.connect(self._inverter)
                self.acoes.addWidget(b)
            if self.tipo == 'magnetic_declination':
                b = QPushButton('Recalcular')
                b.clicked.connect(self._recalcular_declinacao)
                self.acoes.addWidget(b)
        finally:
            self._carregando = False

    def _widget(self, col, spec, valor):
        kind = spec[0]
        nulo = valor is None or (hasattr(valor, 'isNull') and valor.isNull())
        if kind == 'texto':
            w = QLineEdit('' if nulo else str(valor))
            w.editingFinished.connect(lambda c=col, w=w: self._mudou(c, w.text() or None))
        elif kind == 'texto_multilinha':
            w = QPlainTextEdit('' if nulo else str(valor))
            w.setFixedHeight(64)
            w.textChanged.connect(lambda c=col, w=w: self._mudou(c, w.toPlainText() or None))
        elif kind == 'leitura':
            w = QLabel('' if nulo else _texto_leitura(valor))
            w.setWordWrap(True)
        elif kind == 'cor':
            w = QgsColorButton()
            w.setAllowOpacity(False)
            w.setShowNull(True)
            if nulo:
                w.setToNull()
            else:
                w.setColor(QColor(str(valor)))
            w.colorChanged.connect(lambda cor, c=col, w=w: self._mudou(c, None if w.isNull() else cor.name()))
        elif kind == 'num':
            w = QDoubleSpinBox()
            w.setRange(spec[1], spec[2])
            w.setSingleStep(spec[3])
            w.setDecimals(spec[4])
            if len(spec) > 5 and spec[5]:
                w.setSuffix(spec[5])
            w.setValue(spec[1] if nulo else float(valor))
            w.valueChanged.connect(lambda v, c=col: self._mudou(c, v))
        elif kind == 'km_em_m':
            w = QDoubleSpinBox()
            w.setRange(spec[1], spec[2])
            w.setSingleStep(spec[3])
            w.setDecimals(0)
            w.setValue(spec[1] if nulo else float(valor) * 1000.0)
            w.valueChanged.connect(lambda v, c=col: self._mudou(c, v / 1000.0))
        elif kind == 'bool':
            w = QCheckBox()
            w.setChecked(False if nulo else bool(valor))
            w.toggled.connect(lambda v, c=col: self._mudou(c, v))
        elif kind == 'combo':
            w = QComboBox()
            for v, rot in spec[1]:
                w.addItem(rot, v)
            i = w.findData(None if nulo else str(valor))
            if i < 0 and not nulo:
                w.addItem(str(valor), str(valor))
                i = w.count() - 1
            w.setCurrentIndex(max(i, 0))
            w.currentIndexChanged.connect(lambda _i, c=col, w=w: self._mudou(c, w.currentData()))
        elif kind == 'simbolo_linha':
            # Combo agrupado como o do Web: um cabeçalho desabilitado por grupo.
            w = QComboBox()
            for grupo, opcoes in opcoes_simbolo_linha():
                w.addItem(grupo, None)
                cab = w.model().item(w.count() - 1)
                cab.setEnabled(False)
                fonte = cab.font()
                fonte.setBold(True)
                cab.setFont(fonte)
                for v, rot in opcoes:
                    w.addItem(rot, v)
            alvo = str(valor) if not nulo and str(valor) else None
            i = w.findData(alvo) if alvo else -1
            if i < 0 and alvo:
                w.addItem(alvo, alvo)
                i = w.count() - 1
            w.setCurrentIndex(i if i >= 0 else w.findData(SIMBOLO_LINHA_PADRAO))
            w.currentIndexChanged.connect(lambda _i, w=w: self._simbolo_linha_mudou(w.currentData()))
        elif kind == 'instancias':
            try:
                inst = json.loads(valor) if isinstance(valor, str) else (valor or [])
            except ValueError:
                inst = []
            texto = ', '.join(str(round(float(i.get('ratio', 0.5)) * 100)) for i in inst) or '50'
            w = QLineEdit(texto)
            w.setToolTip('Uma posição por repetição, de 1 a 99, separadas por vírgula (até 6).')
            w.editingFinished.connect(lambda c=col, w=w, inst=inst: self._mudou(c, _instancias(w.text(), inst)))
        elif kind == 'sidc':
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            ed = QLineEdit('' if nulo else str(valor))
            ed.setMaxLength(30)
            ed.editingFinished.connect(lambda c=col, ed=ed: self._mudou_sidc(ed.text()))
            h.addWidget(ed, 1)
            if self.abrir_construtor_sidc:
                b = QPushButton('Configurar...')
                b.clicked.connect(lambda _=False, ed=ed: self._construtor(ed))
                h.addWidget(b)
        elif kind == 'engenharia':
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            rot = QLabel(_rotulo_engenharia(None if nulo else str(valor)))
            rot.setWordWrap(True)
            h.addWidget(rot, 1)
            b = QPushButton('Configurar...')
            b.clicked.connect(self._seletor_engenharia)
            h.addWidget(b)
        elif kind == 'medida':
            w = QComboBox()
            for codigo, rotulo in opcoes_medida():
                w.addItem(rotulo, codigo)
            i = w.findData(None if nulo else str(valor))
            if i < 0 and not nulo:
                # Código fora do seletor (a Área minada pontual, 270800): mostra o nome e segue desenhando.
                e = entrada_medida(str(valor))
                w.addItem('{}: {}'.format(e.get('categoria'), e.get('nome')) if e else str(valor), str(valor))
                i = w.count() - 1
            w.setCurrentIndex(max(i, 0))
            w.currentIndexChanged.connect(lambda _i, w=w: self._medida_mudou(w.currentData()))
        elif kind == 'azimute':
            w = _spin_azimute(0 if nulo else valor)
            w.valueChanged.connect(lambda v, c=col: self._mudou(c, float(v)))
        elif kind in ('dir_principal', 'dir_secundaria'):
            i = 0 if kind == 'dir_principal' else 1
            w = _spin_azimute(self._setor[i])
            w.valueChanged.connect(lambda v, i=i: self._setor_mudou(i, v))
        elif kind == 'mina':
            d = definicao_campo(col)
            w = QComboBox()
            rotulos = d.get('optionLabels') or {}
            for v in d.get('options') or []:
                w.addItem(rotulos.get(v, v), v)
            # Sem valor gravado, mostra o desenho padrão (antipessoal) sem gravá-lo.
            i = w.findData(d.get('defaultValue') if nulo or not str(valor) else str(valor))
            w.setCurrentIndex(max(i, 0))
            w.currentIndexChanged.connect(lambda _i, c=col, w=w: self._mudou(c, w.currentData()))
        elif kind == 'escalao_medida':
            feat = self.layer.getFeature(self.fid)
            prefixo = prefixo_familia(feat['point_code'])
            w = QComboBox()
            if prefixo is None:
                w.addItem('Não se aplica', None)
                w.setEnabled(False)
            else:
                for nn, rotulo in escaloes_medida():
                    w.addItem(rotulo, '{}_{}'.format(prefixo, nn))
                i = w.findData(None if nulo else str(valor))
                w.setCurrentIndex(max(i, 0))
                w.currentIndexChanged.connect(lambda _i, c=col, w=w: self._mudou(c, w.currentData()))
        elif kind.startswith('area_'):
            from .painel_area import widget_area
            w = widget_area(self, col, spec, valor, nulo)
            if w is None:
                return None
        else:
            return None
        self.widgets[col] = w
        return w

    def _seletor_engenharia(self):
        from .seletor_engenharia import SeletorEngenharia
        feat = self.layer.getFeature(self.fid)
        dlg = SeletorEngenharia(feat['point_code'], feat['engineering'], self)
        if dlg.exec():
            self._pendentes.update(dlg.valores())
            self._gravar_pendentes()
            QTimer.singleShot(0, self._selecao_mudou)

    def _medida_mudou(self, codigo):
        """Troca de medida: nas famílias de escalão (Núcleo, Escalão, com ou sem FT) o escalão
        acompanha a família, mantendo o número; o painel é remontado para o escalão certo."""
        if self._carregando or self.fid is None:
            return
        feat = self.layer.getFeature(self.fid)
        prefixo = prefixo_familia(codigo)
        mud = {'point_code': codigo}
        # As escolhas de desenho de um tipo (minas, seta secundária) não valem para outro.
        for c in CAMPOS_MINA + ('angulo_secundario',):
            if self.layer.fields().indexOf(c) >= 0:
                mud[c] = None
        cor = cor_ao_trocar_medida(feat['point_code'], codigo, feat['fill_color'])
        if cor is not False:
            mud['fill_color'] = cor
        if prefixo:
            atual = str(feat['echelon_code'] or '')
            nn = atual.rsplit('_', 1)[-1] if atual[-2:].isdigit() else _escalao_padrao()
            mud['echelon_code'] = '{}_{}'.format(prefixo, nn)
        self._pendentes.update(mud)
        self._gravar_pendentes()
        # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
        QTimer.singleShot(0, self._selecao_mudou)

    def _simbolo_linha_mudou(self, codigo):
        """
        Troca do símbolo da Linha de Coordenação. A cor padrão do símbolo novo (obstáculo verde,
        manobra e fogos pretos) é regra do guardião da camada, que vale também para o formulário
        nativo e a tabela de atributos. O painel se remonta, porque os campos seguem o símbolo.
        """
        if self._carregando or self.fid is None or not codigo:
            return
        self._pendentes['symbol_code'] = codigo
        self._gravar_pendentes()
        # remontar fora do sinal (ver _medida_mudou)
        QTimer.singleShot(0, self._selecao_mudou)

    def _setor_mudou(self, indice, valor):
        """
        Direções do Setor de Tiro, lidas e escritas como AZIMUTES; grava a principal em rotation e
        a secundária RELATIVA a ela em angulo_secundario. Girar a principal deixa a secundária no
        mesmo azimute (decisão do chefe, 2026-10-04): as duas colunas mudam e o relativo compensa.
        O estado fica no painel e cada gravação sai dele, como no Web.
        """
        if self._carregando or self.fid is None or self._setor is None:
            return
        self._setor[indice] = normalizar_azimute(valor)
        principal, secundaria = self._setor
        self._pendentes['angulo_secundario'] = normalizar_relativo(secundaria - principal)
        if indice == 0:
            self._pendentes['rotation'] = principal
        if self._abertura is not None:
            self._abertura.setText(texto_abertura(principal, secundaria))
        self._gravar_timer.start()

    def _construtor(self, editor):
        feat = self.layer.getFeature(self.fid)
        novo = self.abrir_construtor_sidc(feat, self.layer)
        if novo:
            for col, val in novo.items():
                self._mudou(col, val)
            if 'sidc' in novo:
                editor.setText(novo['sidc'])

    def _mudou_sidc(self, texto):
        t = ''.join(ch for ch in texto if ch.isdigit())
        if len(t) not in (20, 30):
            self.iface.messageBar().pushWarning('EBGeo', 'O SIDC precisa ter 20 ou 30 dígitos.')
            return
        self._mudou('sidc', t)

    # ---------- gravação ----------
    def _mudou(self, col, valor):
        if self._carregando or self.fid is None:
            return
        self._pendentes[col] = valor
        self._gravar_timer.start()

    def _gravar_pendentes(self):
        if not self._pendentes or self.layer is None or self.fid is None:
            self._pendentes = {}
            return
        mudancas, self._pendentes = self._pendentes, {}
        if self.tipo in esp.TIPOS_COM_FORMULARIO:
            self._gravar_no_buffer(mudancas)
            return
        feat = self.layer.getFeature(self.fid)
        if schema.TIPOS[self.tipo]['desenho'] == 'svg':
            attrs = {f.name(): feat[f.name()] for f in self.layer.fields()}
            attrs.update(mudancas)
            try:
                from .. import simbolos
                mudancas.update(simbolos.renderizar(self.tipo, attrs))
            except Exception as e:
                self.iface.messageBar().pushWarning('EBGeo', 'Não foi possível gerar o símbolo: {}'.format(e))
        gravar_atributos(self.layer, self.fid, mudancas)

    def _inverter(self):
        if self.fid is None:
            return
        feat = self.layer.getFeature(self.fid)
        g = feat.geometry()
        partes = []
        for parte in g.constParts():
            pts = [p for p in parte.vertices()]
            partes.append(list(reversed(pts)))
        from qgis.core import QgsLineString, QgsMultiLineString
        if g.isMultipart():
            ml = QgsMultiLineString()
            for pts in partes:
                ml.addGeometry(QgsLineString(pts))
            nova = QgsGeometry(ml)
        else:
            nova = QgsGeometry(QgsLineString(partes[0]))
        if self.tipo in esp.TIPOS_COM_FORMULARIO:
            fid = self.fid
            self._no_buffer(lambda: self.layer.changeGeometry(fid, nova), 'Calco: inverter sentido')
            return
        gravar_geometria(self.layer, self.fid, nova)

    def _recalcular_declinacao(self):
        if self.fid is None:
            return
        feat = self.layer.getFeature(self.fid)
        try:
            from ..motor import declinacao
        except ImportError:
            return
        p = feat.geometry().asPoint()
        web = declinacao.calcular(p.y(), p.x()) or {}
        m = schema.mapa_web(self.tipo)
        valores = {m[k]: v for k, v in web.items() if k in m}
        attrs = {f.name(): feat[f.name()] for f in self.layer.fields()}
        attrs.update(valores)
        try:
            from .. import simbolos
            valores.update(simbolos.renderizar(self.tipo, attrs))
        except Exception as e:
            self.iface.messageBar().pushWarning('EBGeo', 'Não foi possível gerar o símbolo: {}'.format(e))
        gravar_atributos(self.layer, self.fid, valores)
        QTimer.singleShot(0, self._selecao_mudou)

    # ---------- painel montado da especificação ----------
    def _montar_spec(self, feat):
        """
        Cabeçalho, uma seção por aba e os campos da especificação do tipo, com os widgets ricos
        onde ela os indica. Campo que não vale para o símbolo some (linha oculta), pela mesma
        expressão que o formulário nativo avalia.
        """
        self._carregando = True
        try:
            self._spec = esp.formulario(self.tipo)
            nomes = self.layer.fields().names()
            attrs = {n: feat[n] for n in nomes}
            travada = esp.Bloqueada().avaliar(attrs)
            for el in self._spec.cabecalho:
                self._elemento(self.form, el, [], attrs, travada)
            for aba in self._spec.abas:
                filhos = aba.filhos
                if aba.prefixo:
                    filhos = [esp.Campo(n, self.layer.attributeAlias(self.layer.fields().indexOf(n)) or n, esp.texto())
                              for n in nomes if n.startswith(aba.prefixo)]
                if not filhos:
                    continue
                conds = [aba.condicao] if aba.condicao is not None else []
                caixa, fl = self._secao(self.form, aba.nome, aba.nome == 'Avançado', conds)
                for el in filhos:
                    self._elemento(fl, el, conds, attrs, travada)
            if self.tipo == 'coordination_line':
                b = QPushButton('Inverter sentido')
                b.clicked.connect(self._inverter)
                b.setEnabled(not travada)
                self.acoes.addWidget(b)
            self._aplicar_condicoes()
        finally:
            self._carregando = False

    def _secao(self, fl_pai, titulo, recolhida, conds):
        caixa = QgsCollapsibleGroupBoxBasic(titulo)  # o não-Basic relê o recolhido salvo nas configurações
        fl = QFormLayout(caixa)
        fl_pai.addRow(caixa)
        if recolhida:
            # o grupo só recolhe visível (setCollapsed volta cedo antes de ele aparecer)
            QTimer.singleShot(0, lambda c=caixa: _recolher(c))
        self._secoes.append((caixa, conds, fl_pai))
        return caixa, fl

    def _elemento(self, fl, el, conds, attrs, travada):
        if isinstance(el, esp.Grupo):
            proprias = conds + ([el.condicao] if el.condicao is not None else [])
            if el.titulo:
                _caixa, fl = self._secao(fl, el.nome, el.recolhido, proprias)
            for filho in el.filhos:
                self._elemento(fl, filho, proprias, attrs, travada)
            return
        if isinstance(el, esp.Texto):
            lb = QLabel(el.texto)
            lb.setWordWrap(True)
            fl.addRow(lb)
            self._linhas.append((el, conds, fl, lb, None))
            return
        if el.coluna not in attrs:
            return
        w = self._widget(el.coluna, _spec_do_campo(el), attrs[el.coluna])
        if w is None:
            return
        if el.coluna == 'visivel' and esp._nulo(attrs[el.coluna]):
            w.setChecked(True)  # nulo vale "mostrar", como no estilo e no Web
        rotulo = QLabel(el.rotulo_para(attrs, rico=bool(el.rico)))
        fl.addRow(rotulo, w)
        if travada:
            w.setEnabled(False)
        self._linhas.append((el, conds + ([el.condicao] if el.condicao is not None else []), fl, w, rotulo))

    def _expressao(self, texto):
        e = self._expressoes.get(texto)
        if e is None:
            e = self._expressoes[texto] = QgsExpression(texto)
        return e

    def _aplicar_condicoes(self):
        if self._spec is None or self.fid is None:
            return
        feat = self.layer.getFeature(self.fid)
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.layer))
        ctx.setFeature(feat)

        def vale(cond):
            return bool(self._expressao(cond.expressao()).evaluate(ctx))
        self._visiveis = set()
        for el, conds, fl, w, rotulo in self._linhas:
            vis = all(vale(c) for c in conds)
            fl.setRowVisible(w, vis)
            if isinstance(el, esp.Campo):
                if vis:
                    self._visiveis.add(el.coluna)
                if rotulo is not None and el.expressao_rotulo():
                    rotulo.setText(str(self._expressao(el.expressao_rotulo()).evaluate(ctx)))
        for caixa, conds, fl in self._secoes:
            fl.setRowVisible(caixa, all(vale(c) for c in conds))

    def campos_visiveis(self):
        """As colunas que o painel da especificação mostra para a feição atual."""
        return set(getattr(self, '_visiveis', set())) if self._spec is not None else set()

    # ---------- buffer de edição, Salvar e Descartar ----------
    def _gravar_no_buffer(self, mudancas):
        fid = self.fid
        idx = self.layer.fields().indexOf
        valores = {idx(c): v for c, v in schema.atributos_para_qgis(self.tipo, mudancas).items() if idx(c) >= 0}

        def mudar():
            for i, v in valores.items():
                self.layer.changeAttributeValue(fid, i, v)
        self._no_buffer(mudar)
        self._aplicar_condicoes()

    def _no_buffer(self, acao, texto='Calco: propriedades'):
        """Executa `acao` num comando de edição da camada, abrindo a edição (e a sessão) se preciso."""
        lyr = self.layer
        s = self._sessoes.get(lyr.id())
        if s is None or not lyr.isEditable():
            abriu = not lyr.isEditable()
            if abriu and not lyr.startEditing():
                self.iface.messageBar().pushWarning('EBGeo', 'A camada {} não pode ser editada.'.format(lyr.name()))
                return False
            s = self._sessoes[lyr.id()] = {'indice': lyr.undoStack().index(), 'abriu': abriu}
        lyr.beginEditCommand(texto)
        try:
            acao()
        except Exception:
            lyr.destroyEditCommand()
            raise
        lyr.endEditCommand()  # o guardião da camada aplica as regras de troca aqui
        lyr.triggerRepaint()
        self._atualizar_barra()
        return True

    def salvar(self):
        """Grava no calco as mudanças da camada; fecha a edição se foi o painel que a abriu."""
        self._gravar_timer.stop()
        self._gravar_pendentes()
        lyr = self.layer
        s = self._sessoes.get(lyr.id()) if lyr is not None else None
        if s is None or not lyr.isEditable():
            self._atualizar_barra()
            return False
        if not lyr.commitChanges(s['abriu']):
            self.iface.messageBar().pushCritical('EBGeo', 'O calco não foi salvo: {}'.format('; '.join(lyr.commitErrors())))
            return False
        self._sessoes.pop(lyr.id(), None)
        self._atualizar_barra()
        QTimer.singleShot(0, self._selecao_mudou)
        return True

    def descartar(self):
        """Volta a camada ao estado de antes da primeira mudança feita pelo painel."""
        self._gravar_timer.stop()
        self._pendentes = {}
        lyr = self.layer
        s = self._sessoes.pop(lyr.id(), None) if lyr is not None else None
        if s is None:
            self._atualizar_barra()
            return False
        if lyr.isEditable():
            lyr.undoStack().setIndex(s['indice'])
            if s['abriu']:
                lyr.rollBack()
        lyr.triggerRepaint()
        self._atualizar_barra()
        QTimer.singleShot(0, self._selecao_mudou)
        return True

    def _edicao_parou(self):
        if self.layer is not None:
            self._sessoes.pop(self.layer.id(), None)
        self._atualizar_barra()
        QTimer.singleShot(0, self._selecao_mudou)

    def _atualizar_barra(self):
        com_barra = self.layer is not None and self.tipo in esp.TIPOS_COM_FORMULARIO
        self.barra_edicao.setVisible(com_barra)
        pendente = com_barra and self.layer.id() in self._sessoes and self.layer.isEditable()
        self.botao_salvar.setEnabled(pendente)
        self.botao_descartar.setEnabled(pendente)
        self.estado_edicao.setText('Mudanças não salvas.' if pendente else ('Nada a salvar.' if com_barra else ''))


def _recolher(caixa):
    try:
        caixa.setCollapsed(True)
    except RuntimeError:  # o painel já foi remontado
        pass


def _spec_do_campo(campo):
    """O widget do painel para o campo da especificação: o rico, quando há, ou o par do nativo."""
    if campo.somente_leitura:
        return ('leitura',)
    if campo.rico == 'simbolo_linha':
        return ('simbolo_linha',)
    if campo.rico == 'km_em_m':
        return ('km_em_m',) + tuple(campo.rico_config)
    w, c = campo.widget, campo.widget.config
    if w.tipo == 'TextEdit':
        return ('texto_multilinha',) if c.get('IsMultiline') else ('texto',)
    if w.tipo == 'Color':
        return ('cor',)
    if w.tipo == 'Range':
        return ('num', c['Min'], c['Max'], c['Step'], c['Precision'], c.get('Suffix', ''))
    if w.tipo == 'CheckBox':
        return ('bool',)
    if w.tipo == 'ValueMap':
        return ('combo', [(v, k) for par in c['map'] for k, v in par.items()])
    return ('leitura',)


def _texto_leitura(valor):
    if hasattr(valor, 'toString') and hasattr(valor, 'isValid'):
        return valor.toString('dd/MM/yyyy HH:mm:ss')
    if isinstance(valor, bool):
        return 'Sim' if valor else 'Não'
    if isinstance(valor, float):
        return '%.4f' % valor
    return str(valor)


# ---------- Linha de Coordenação ----------
SIMBOLO_LINHA_PADRAO = '290199'


def opcoes_simbolo_linha():
    """[(grupo, [(código, 'Nome (designação)')])] na ordem do combo do Web (symbolOptionGroups)."""
    from .. import estilos_taticos as et
    return [(g, [(c, '{} ({})'.format(s['nome'], et.designacao_linha(c)))
                 for c, s in et.CATALOGO_LINHA.items() if s['grupo'] == g])
            for g in et.GRUPOS_LINHA]


def _rotulo_engenharia(codigo):
    try:
        from .construtor_sidc import catalogos
        for it in catalogos()['engenharia']['itens']:
            if str(it['codigo']) == str(codigo):
                return '{}. {}'.format(it['numero'], it['titulo'])
    except Exception:
        pass
    return str(codigo or '')


def _catalogo_medida():
    try:
        from .construtor_sidc import catalogos
        return catalogos()['medida']
    except Exception:
        return None


def _escalao_padrao():
    c = _catalogo_medida()
    return (c or {}).get('escalaoPadrao', '16')


def opcoes_medida():
    """(código, rótulo) das medidas do catálogo, mais as quatro famílias de escalão."""
    c = _catalogo_medida()
    if not c:
        return []
    ops = [('ECHELON', 'Núcleo: Núcleo (escolha o escalão)'), ('ECHELON_FT', 'Núcleo: Núcleo de Força-Tarefa'),
           ('ESCALAO', 'Escalão: Escalão'), ('ESCALAO_FT', 'Escalão: Escalão de Força-Tarefa')]
    for item in c['lista']:
        ops.append((item['code'], '{}: {}'.format(item['category'], item['label'])))
    return ops


def entrada_medida(codigo):
    """Entrada do catálogo (porCodigo) da medida, ou None (famílias de escalão, código desconhecido)."""
    c = _catalogo_medida()
    return ((c or {}).get('porCodigo') or {}).get(str(codigo or ''))


def definicao_campo(campo):
    c = _catalogo_medida()
    return ((c or {}).get('definicoesCampos') or {}).get(campo) or {}


def linhas_medida(codigo):
    """
    As linhas do painel da Medida de Coordenação para o tipo `codigo`. A medida com direção (Base
    de fogos) troca a Rotação por um azimute de 1 grau com o rótulo do catálogo; o Setor de Tiro
    troca por Direção principal e Direção secundária; o campo minado (270701) ganha as três minas.
    As demais ficam como sempre.
    """
    e = entrada_medida(codigo) or {}
    linhas = []
    for col, rotulo, spec in PAINEIS['coordination_measure']:
        if col == 'rotation' and e.get('setorDeTiro'):
            linhas += [('rotation', 'Direção principal', ('dir_principal',)),
                       ('angulo_secundario', 'Direção secundária', ('dir_secundaria',))]
            continue
        if col == 'rotation' and e.get('direcao'):
            linhas.append(('rotation', e['direcao'].get('rotulo') or 'Direção', ('azimute',)))
            continue
        linhas.append((col, rotulo, spec))
        if col == 'altitude':
            for m in CAMPOS_MINA:
                if m in (e.get('campos') or []):
                    linhas.append((m, definicao_campo(m).get('label') or m, ('mina',)))
    return linhas


def _numero_finito(v):
    if v is None or (hasattr(v, 'isNull') and v.isNull()):
        return False
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def normalizar_azimute(graus):
    """Ângulo em [0, 360), como se lê um azimute (normalizarAzimute do Web)."""
    return float(graus) % 360.0 + 0.0


def normalizar_relativo(graus):
    """Ângulo em [-180, 180) (normalizarRelativo do Web)."""
    return (float(graus) + 180.0) % 360.0 - 180.0 + 0.0


def direcoes_do_setor(rotacao, angulo_secundario):
    """(principal, secundária) em azimute; sem valor, a secundária fica a -45 graus da principal."""
    principal = normalizar_azimute(rotacao if _numero_finito(rotacao) else 0.0)
    relativo = normalizar_relativo(angulo_secundario if _numero_finito(angulo_secundario) else ANGULO_SECUNDARIO_PADRAO)
    return principal, normalizar_azimute(principal + relativo)


def texto_abertura(principal, secundaria):
    return 'Abertura do setor: {}°'.format(int(math.floor(abs(normalizar_relativo(secundaria - principal)) + 0.5)))


def cor_ao_trocar_medida(anterior, novo, atual):
    """
    Cor da medida que troca de tipo: o tipo com cor própria (as destruições nascem verdes,
    MD33-C-01 7.4.1) a impõe, salvo se o operador já escolheu outra; sair dele devolve a cor
    padrão (nula). Devolve False quando a cor fica como está (_aplicarCorPadraoDoTipo do Web).
    """
    def igual(a, b):
        return (a or '').lower() == (b or '').lower()
    padrao_anterior = (entrada_medida(anterior) or {}).get('corPadrao')
    padrao_novo = (entrada_medida(novo) or {}).get('corPadrao')
    vazio = atual is None or (hasattr(atual, 'isNull') and atual.isNull()) or atual == ''
    atual = None if vazio else str(atual)
    if atual is not None and not igual(atual, padrao_anterior):
        return False
    if igual(atual, padrao_novo):
        return False
    return padrao_novo


def _spin_azimute(graus):
    w = QSpinBox()
    w.setRange(0, 359)
    w.setSingleStep(1)
    w.setWrapping(True)
    w.setSuffix('°')
    w.setValue(int(math.floor(normalizar_azimute(graus if _numero_finito(graus) else 0.0) + 0.5)) % 360)
    return w


def prefixo_familia(codigo):
    """Prefixo do echelonCode para as famílias de escalão; None para as demais medidas."""
    return {'ECHELON': 'ECHELON', 'ECHELON_FT': 'ECHELON_FT',
            'ESCALAO': 'ESCALAO', 'ESCALAO_FT': 'ESCALAO_FT'}.get(str(codigo or ''))


def escaloes_medida():
    c = _catalogo_medida()
    return sorted((c or {}).get('escaloes', {}).items())


def _instancias(texto, antigas):
    vals = []
    for parte in texto.replace(';', ',').split(','):
        parte = parte.strip()
        if not parte:
            continue
        try:
            v = min(99.0, max(1.0, float(parte.replace('%', ''))))
        except ValueError:
            continue
        vals.append(v / 100.0)
    vals = vals[:6] or [0.5]
    res = []
    for i, r in enumerate(vals):
        show = antigas[i].get('showLabels', True) if i < len(antigas) and isinstance(antigas[i], dict) else True
        res.append({'ratio': round(r, 4), 'showLabels': show})
    return json.dumps(res)


def gravar_atributos(layer, fid, mudancas):
    estava = layer.isEditable()
    if not estava:
        layer.startEditing()
    if estava:
        layer.beginEditCommand('Calco: propriedades')
    # coluna JSON recebe o objeto: o texto viraria string JSON escapada no GeoPackage
    for col, val in schema.atributos_para_qgis(tipo_da_camada(layer), mudancas).items():
        i = layer.fields().indexOf(col)
        if i >= 0:
            layer.changeAttributeValue(fid, i, val)
    if estava:
        layer.endEditCommand()
    else:
        layer.commitChanges()
    layer.triggerRepaint()


def gravar_geometria(layer, fid, geom):
    estava = layer.isEditable()
    if not estava:
        layer.startEditing()
    layer.changeGeometry(fid, geom)
    if not estava:
        layer.commitChanges()
    layer.triggerRepaint()
