# -*- coding: utf-8 -*-
"""
Painel de propriedades do calco: espelha os painéis do EBGeo Web para a feição
selecionada na camada ativa. Cada mudança grava na camada (no buffer de edição,
se a camada estiver em edição; senão, direto) e, nos símbolos pontuais, regera o SVG.
"""
import json

from qgis.core import QgsFeatureRequest, QgsProject, QgsVectorLayer, QgsGeometry
from qgis.gui import QgsColorButton
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .. import schema
from ..calco import tipo_da_camada

ESCALOES_LIMITE = ['XXXXXX', 'XXXXX', 'XXXX', 'XXX', 'XX', 'X', 'III', 'II', 'I', 'ooo', 'oo', 'o']

SIMBOLOS_LINHA = [
    ('290100', 'Linha de obstáculos'),
    ('290199', 'Linha de barreiras'),
    ('290202', 'Fosso anticarro'),
    ('290302', 'Cerca de arame'),
    ('290303', 'Cerca de arame dupla'),
    ('290307', 'Concertina'),
    ('290308', 'Concertina dupla'),
    ('290309', 'Concertina tripla'),
    ('290999-01', 'Sapa'),
    ('290999-02', 'Trincheira'),
]

STATUS_NUCLEO = [('ocupado', 'Ocupado'), ('preparado', 'Preparado'),
                 ('preparado-nao-ocupado', 'Preparado, não ocupado')]

# Widgets: ('texto'), ('cor'), ('num', min, max, passo, casas), ('bool'),
# ('combo', [(valor, rótulo)]), ('km_em_m', min_m, max_m, passo_m)
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
    'engineering_symbol': [('point_code', 'Item (C 5-36)', ('texto',)),
                           ('engineering', 'Valores (JSON)', ('texto',))] + _ICONE,
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
    'coordination_line': [('symbol_code', 'Símbolo', ('combo', SIMBOLOS_LINHA)),
                          ('symbol_size_km', 'Tamanho do símbolo (m)', ('km_em_m', 10, 50000, 5)),
                          ('symbol_spacing_km', 'Distância entre símbolos (m)', ('km_em_m', 10, 500000, 5))]
    + _TRACO + _ZOOM,
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
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(base)
        self.setWidget(sc)
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
            try:
                self.layer.selectionChanged.disconnect(self._selecao_mudou)
            except (TypeError, RuntimeError):
                pass
        self.layer = layer if isinstance(layer, QgsVectorLayer) else None
        self.tipo = tipo_da_camada(self.layer)
        if self.layer is not None and self.tipo in PAINEIS:
            self.layer.selectionChanged.connect(self._selecao_mudou)
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
        if self.layer is None or self.tipo not in PAINEIS:
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
        self._montar(feat)

    def _limpar(self):
        self.fid = None
        self.widgets = {}
        while self.form.rowCount():
            self.form.removeRow(0)
        while self.acoes.count():
            w = self.acoes.takeAt(0).widget()
            if w:
                w.deleteLater()

    # ---------- formulário ----------
    def _montar(self, feat):
        self._carregando = True
        try:
            for col, rotulo, spec in _COMUNS + PAINEIS[self.tipo]:
                if self.layer.fields().indexOf(col) < 0:
                    continue
                w = self._widget(col, spec, feat[col])
                if w is not None:
                    self.form.addRow(rotulo, w)
            if self.tipo in ('coordination_line', 'boundary', 'arrow'):
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
        elif kind == 'leitura':
            w = QLabel('' if nulo else (('%.4f' % valor) if isinstance(valor, float) else str(valor)))
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
        elif kind == 'medida':
            w = QComboBox()
            for codigo, rotulo in opcoes_medida():
                w.addItem(rotulo, codigo)
            i = w.findData(None if nulo else str(valor))
            if i < 0 and not nulo:
                w.addItem(str(valor), str(valor))
                i = w.count() - 1
            w.setCurrentIndex(max(i, 0))
            w.currentIndexChanged.connect(lambda _i, w=w: self._medida_mudou(w.currentData()))
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
        else:
            return None
        self.widgets[col] = w
        return w

    def _medida_mudou(self, codigo):
        """Troca de medida: nas famílias de escalão (Núcleo, Escalão, com ou sem FT) o escalão
        acompanha a família, mantendo o número; o painel é remontado para o escalão certo."""
        if self._carregando or self.fid is None:
            return
        feat = self.layer.getFeature(self.fid)
        prefixo = prefixo_familia(codigo)
        mud = {'point_code': codigo}
        if prefixo:
            atual = str(feat['echelon_code'] or '')
            nn = atual.rsplit('_', 1)[-1] if atual[-2:].isdigit() else _escalao_padrao()
            mud['echelon_code'] = '{}_{}'.format(prefixo, nn)
        self._pendentes.update(mud)
        self._gravar_pendentes()
        # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
        QTimer.singleShot(0, self._selecao_mudou)

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
    for col, val in mudancas.items():
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
