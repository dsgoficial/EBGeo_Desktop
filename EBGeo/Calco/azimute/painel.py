# -*- coding: utf-8 -*-
"""
Painel "Azimute e Distância": a caderneta de campanha do EBGeo Web (azimuth_distance_panel.js)
num painel do QGIS, para criar uma construção polar e para editar uma já gravada.

Criar: ponto de referência (clique no mapa ou coordenadas digitadas), unidades, saída (Ponto,
Rota, Área), norte em que os azimutes são digitados (NM | NQ | NV), declinação do WMM2025 no
ponto (editável) e convergência do fuso, as pernas, a leitura da perna ativa nos três nortes
e a tabela NV | NQ | NM | Distância de todas as pernas.
Editar: o mesmo painel, preenchido com a construção da feição selecionada; a saída não muda.
"""
import csv
import math
import re
import unicodedata

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDockWidget, QFileDialog, QFormLayout, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from . import geometria as G
from ..motor import declinacao as _decl

CRIAR = 'criar'
EDITAR = 'editar'

_VERMELHO = QColor(254, 226, 226)


def ler_numero(texto):
    """Número digitado com vírgula ou ponto; None quando vazio; ValueError quando inválido."""
    t = (texto or '').strip().replace(' ', '')
    if not t:
        return None
    if t.count(',') == 1 and '.' not in t:
        t = t.replace(',', '.')
    f = float(t)
    if not math.isfinite(f):
        raise ValueError(texto)
    return f


def ler_azimute(texto):
    """Azimute em graus decimais ou em GG.MM.SS / GG°MM'SS" (o formato da ferramenta antiga)."""
    t = (texto or '').strip()
    m = re.fullmatch(r"\s*(\d+)\s*[°º.\s]\s*(\d+)\s*['’.\s]\s*(\d+(?:[.,]\d+)?)\s*(?:\"|'')?\s*", t)
    if m and (t.count('.') >= 2 or '°' in t or 'º' in t):
        g, mi, s = float(m.group(1)), float(m.group(2)), float(m.group(3).replace(',', '.'))
        return g + mi / 60 + s / 3600
    return ler_numero(t)


def _sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '') if unicodedata.category(c) != 'Mn').lower()


def ler_csv_pernas(caminho):
    """
    Pernas de um CSV (o lote da ferramenta antiga): colunas de azimute e de distância achadas
    pelo cabeçalho ('azim...', 'dist...', 'obs...'), ou as duas primeiras sem cabeçalho.
    Devolve (pernas, linhas ignoradas).
    """
    with open(caminho, newline='', encoding='utf-8-sig') as fh:
        texto = fh.read()
    try:
        dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=';,\t|:')
        delim = dialeto.delimiter
    except csv.Error:
        delim = ';' if ';' in texto else ','
    linhas = [l for l in csv.reader(texto.splitlines(), delimiter=delim) if any(c.strip() for c in l)]
    if not linhas:
        return [], 0
    cab = [_sem_acento(c) for c in linhas[0]]
    i_az = next((i for i, c in enumerate(cab) if 'azim' in c or c in ('az', 'rumo')), None)
    i_d = next((i for i, c in enumerate(cab) if 'dist' in c), None)
    i_o = next((i for i, c in enumerate(cab) if 'obs' in c), None)
    corpo = linhas[1:] if (i_az is not None or i_d is not None) else linhas
    if i_az is None:
        i_az = 0
    if i_d is None:
        i_d = 1 if i_az != 1 else 0
    pernas, ruins = [], 0
    for l in corpo:
        try:
            az = ler_azimute(l[i_az])
            d = ler_numero(l[i_d])
        except (ValueError, IndexError):
            ruins += 1
            continue
        if az is None or d is None:
            ruins += 1
            continue
        obs = l[i_o].strip() if i_o is not None and i_o < len(l) else ''
        pernas.append({'azimuth': G.limpo(az), 'distance': G.limpo(d), 'observation': obs[:12]})
    return pernas, ruins


def perna_vazia():
    return {'azimuth': '', 'distance': '', 'observation': ''}


def estado_inicial():
    return {
        'referencePoint': None,
        'angularUnit': G.GRAUS,
        'distanceUnit': G.METROS,
        'northReference': G.NM,
        'magneticDeclination': G.DECLINACAO_INICIAL,
        'autoDeclinationValue': None,
        'autoDeclinationWarning': None,
        'meridianConvergence': None,
        'manuallyEdited': False,
        'outputMode': G.ROTA,
        'activeIndex': 0,
        'legs': [perna_vazia()],
    }


class PainelAzimute(QDockWidget):
    estadoMudou = pyqtSignal(dict)       # para o preview no mapa
    pedirCliqueMapa = pyqtSignal()       # "Clicar no mapa"
    criarPedido = pyqtSignal(dict)       # botão Criar
    salvarPedido = pyqtSignal(dict)      # botão Salvar alterações (modo edição)
    cancelarPedido = pyqtSignal()        # Cancelar / Esc
    novaPedida = pyqtSignal()            # "Nova construção" a partir do modo edição

    def __init__(self, parent=None):
        super().__init__('Azimute e Distância', parent)
        self.setObjectName('EBGeoAzimuteDistancia')
        self.modo = CRIAR
        self.alvo = None          # (camada, fid) no modo edição
        self.estado = estado_inicial()
        self.aguardando_clique = True
        self._montando = False
        self._montar()
        self._atualizar_tudo()

    # ------------------------------------------------------------------ montagem
    def _montar(self):
        base = QWidget()
        v = QVBoxLayout(base)

        self.titulo = QLabel()
        self.titulo.setWordWrap(True)
        v.addWidget(self.titulo)

        # ponto de referência
        v.addWidget(self._secao('Ponto de Referência (Origem)'))
        self.lbl_ponto = QLabel()
        self.lbl_ponto.setWordWrap(True)
        v.addWidget(self.lbl_ponto)
        g = QGridLayout()
        g.addWidget(QLabel('Lat'), 0, 0)
        self.ed_lat = QLineEdit()
        self.ed_lat.setPlaceholderText('-15,750000')
        g.addWidget(self.ed_lat, 0, 1)
        g.addWidget(QLabel('Lon'), 0, 2)
        self.ed_lon = QLineEdit()
        self.ed_lon.setPlaceholderText('-47,800000')
        g.addWidget(self.ed_lon, 0, 3)
        v.addLayout(g)
        self.ed_lat.editingFinished.connect(self._coordenadas_digitadas)
        self.ed_lon.editingFinished.connect(self._coordenadas_digitadas)
        h = QHBoxLayout()
        self.bt_mapa = QPushButton('Clicar no mapa')
        self.bt_mapa.setToolTip('Clique no mapa para definir o ponto de referência (com atração, se ligada)')
        self.bt_mapa.clicked.connect(self._pedir_clique)
        self.bt_limpar = QPushButton('Limpar')
        self.bt_limpar.clicked.connect(self._limpar_ponto)
        h.addWidget(self.bt_mapa)
        h.addWidget(self.bt_limpar)
        v.addLayout(h)

        # unidades
        form = QFormLayout()
        self.cb_ang = QComboBox()
        self.cb_ang.addItem('Graus (°)', G.GRAUS)
        self.cb_ang.addItem('Milésimos (₥)', G.MILESIMOS)
        self.cb_ang.currentIndexChanged.connect(self._unidade_angular)
        self.cb_dist = QComboBox()
        self.cb_dist.addItem('Metros (m)', G.METROS)
        self.cb_dist.addItem('Quilômetros (km)', G.QUILOMETROS)
        self.cb_dist.currentIndexChanged.connect(self._unidade_distancia)
        form.addRow('Ângulo', self.cb_ang)
        form.addRow('Distância', self.cb_dist)
        v.addLayout(form)

        # saída
        v.addWidget(self._secao('Saída'))
        h = QHBoxLayout()
        self.grupo_modo = QButtonGroup(self)
        self.bt_modo = {}
        for modo, extra in ((G.PONTO, 'gera um ponto na origem e no fim de cada perna'),
                            (G.ROTA, 'gera uma linha ligando as pernas'),
                            (G.AREA, 'gera um polígono que fecha na origem; requer ao menos duas pernas')):
            b = QToolButton()
            b.setText(G.ROTULO_MODO[modo])
            b.setCheckable(True)
            b.setToolTip('{}: {}'.format(G.DESCRICAO_MODO[modo], extra))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            b.clicked.connect(lambda _c=False, m=modo: self._definir_modo(m))
            self.grupo_modo.addButton(b)
            self.bt_modo[modo] = b
            h.addWidget(b)
        v.addLayout(h)

        # norte de referência e declinação
        v.addWidget(self._secao('Norte de Referência'))
        h = QHBoxLayout()
        self.grupo_norte = QButtonGroup(self)
        self.bt_norte = {}
        for norte, rotulo, dica in ((G.NM, 'NM', 'Norte Magnético (bússola)'),
                                    (G.NQ, 'NQ', 'Norte de Quadrícula (UTM)'),
                                    (G.NV, 'NV', 'Norte Verdadeiro (geográfico)')):
            b = QToolButton()
            b.setText(rotulo)
            b.setToolTip(dica)
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, n=norte: self._definir_norte(n))
            self.grupo_norte.addButton(b)
            self.bt_norte[norte] = b
            h.addWidget(b)
        h.addSpacing(8)
        h.addWidget(QLabel('Decl:'))
        self.ed_decl = QLineEdit()
        self.ed_decl.setMaximumWidth(70)
        self.ed_decl.setToolTip('Oeste (−) / Leste (+), em graus')
        self.ed_decl.textEdited.connect(self._declinacao_digitada)
        h.addWidget(self.ed_decl)
        h.addWidget(QLabel('°'))
        self.bt_wmm = QToolButton()
        self.bt_wmm.setText('WMM')
        self.bt_wmm.setToolTip('Calcular declinação automática (WMM2025)')
        self.bt_wmm.clicked.connect(self._aplicar_wmm)
        h.addWidget(self.bt_wmm)
        h.addStretch(1)
        v.addLayout(h)
        self.lbl_auto = QLabel()
        self.lbl_conv = QLabel()
        self.lbl_corr = QLabel()
        for w in (self.lbl_auto, self.lbl_conv, self.lbl_corr):
            w.setWordWrap(True)
            v.addWidget(w)

        # pernas
        v.addWidget(self._secao('Pernas'))
        self.tab_pernas = QTableWidget(0, 3)
        self.tab_pernas.verticalHeader().setVisible(True)
        self.tab_pernas.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tab_pernas.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tab_pernas.setMinimumHeight(110)
        self.tab_pernas.setMaximumHeight(190)
        self.tab_pernas.itemChanged.connect(self._perna_editada)
        self.tab_pernas.currentCellChanged.connect(lambda r, *_: self._definir_ativa(r))
        v.addWidget(self.tab_pernas)
        h = QHBoxLayout()
        self.bt_mais = QPushButton('+ Perna')
        self.bt_mais.clicked.connect(self._adicionar_perna)
        self.bt_menos = QPushButton('Remover perna')
        self.bt_menos.clicked.connect(self._remover_perna)
        self.bt_csv = QPushButton('Importar CSV...')
        self.bt_csv.setToolTip('Pernas de um CSV com colunas de azimute e distância (e observação)')
        self.bt_csv.clicked.connect(self._importar_csv)
        for b in (self.bt_mais, self.bt_menos, self.bt_csv):
            h.addWidget(b)
        v.addLayout(h)

        # leitura da perna ativa nos três nortes
        self.lbl_leitura = QLabel()
        self.lbl_leitura.setWordWrap(True)
        v.addWidget(self.lbl_leitura)

        # azimute rápido
        self.lbl_rapido = self._secao('')
        v.addWidget(self.lbl_rapido)
        g = QGridLayout()
        self.bt_rapido = []
        for k, (rotulo, graus) in enumerate(G.PRESETS):
            b = QToolButton()
            b.clicked.connect(lambda _c=False, gr=graus: self._azimute_rapido(gr))
            g.addWidget(b, k // 4, k % 4)
            self.bt_rapido.append((b, rotulo, graus))
        v.addLayout(g)

        # tabela dos três nortes
        v.addWidget(self._secao('Três nortes (NV, NQ, NM)'))
        self.tab_nortes = QTableWidget(0, 5)
        self.tab_nortes.setHorizontalHeaderLabels(['Perna', 'NV', 'NQ', 'NM', 'Distância'])
        self.tab_nortes.verticalHeader().setVisible(False)
        self.tab_nortes.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tab_nortes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tab_nortes.setMinimumHeight(90)
        self.tab_nortes.setMaximumHeight(190)
        v.addWidget(self.tab_nortes)

        self.lbl_resumo = QLabel()
        v.addWidget(self.lbl_resumo)
        self.lbl_aviso = QLabel()
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setVisible(False)
        v.addWidget(self.lbl_aviso)

        h = QHBoxLayout()
        self.bt_nova = QPushButton('Nova construção')
        self.bt_nova.clicked.connect(self.novaPedida.emit)
        self.bt_cancelar = QPushButton('Cancelar')
        self.bt_cancelar.clicked.connect(self.cancelarPedido.emit)
        self.bt_criar = QPushButton()
        self.bt_criar.setDefault(True)
        self.bt_criar.clicked.connect(self._confirmar)
        h.addWidget(self.bt_nova)
        h.addWidget(self.bt_cancelar)
        h.addWidget(self.bt_criar)
        v.addLayout(h)
        v.addStretch(1)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(base)
        self.setWidget(sc)

    @staticmethod
    def _secao(texto):
        l = QLabel('<b>{}</b>'.format(texto))
        return l

    # ------------------------------------------------------------------ API
    def novo(self):
        """Volta ao modo criação, com o estado do Web na abertura."""
        self.modo = CRIAR
        self.alvo = None
        self.estado = estado_inicial()
        self.aguardando_clique = True
        self.avisar('')
        self._atualizar_tudo()

    def editar(self, layer, fid, polar, nome=''):
        """Abre a construção gravada de uma feição para editar."""
        self.modo = EDITAR
        self.alvo = (layer, fid)
        self.nome_alvo = nome
        ponto = polar.get('referencePoint')
        legs = [dict(perna_vazia(), **{k: l.get(k, '') for k in ('azimuth', 'distance', 'observation')})
                for l in polar.get('legs') or []] or [perna_vazia()]
        self.estado = estado_inicial()
        self.estado.update({
            'referencePoint': [float(ponto[0]), float(ponto[1])],
            'angularUnit': polar.get('angularUnit') or G.GRAUS,
            'distanceUnit': polar.get('distanceUnit') or G.METROS,
            'northReference': polar.get('northReference') if polar.get('northReference') in (G.NM, G.NQ, G.NV) else G.NV,
            'meridianConvergence': G.resolver_convergencia(polar),
            'manuallyEdited': True,
            'outputMode': polar.get('outputMode') or G.ROTA,
            'legs': legs,
        })
        d = G.declinacao_exibida(polar)
        self.estado['magneticDeclination'] = d if d is not None else (G.numero(polar.get('magneticDeclination')) or 0)
        self._calcular_auto()
        self.aguardando_clique = False
        self.avisar('')
        self._atualizar_tudo()

    def definir_ponto(self, lon, lat):
        """setReferencePoint do Web: declinação WMM2025 e convergência do fuso calculadas no ponto."""
        self.estado['referencePoint'] = [lon, lat]
        self._calcular_auto()
        self.estado['meridianConvergence'] = G.convergencia_no_ponto(lat, lon)
        if self.estado['autoDeclinationValue'] is not None and not self.estado['manuallyEdited']:
            self.estado['magneticDeclination'] = self.estado['autoDeclinationValue']
        self.aguardando_clique = False
        self._atualizar_tudo()

    def estado_publico(self):
        e = dict(self.estado)
        e['legs'] = [dict(l) for l in self.estado['legs']]
        return e

    def avisar(self, texto, erro=False):
        """Aviso no próprio painel (sem caixa modal)."""
        self.lbl_aviso.setText(texto)
        self.lbl_aviso.setStyleSheet('color: #b91c1c;' if erro else 'color: #15803d;')
        self.lbl_aviso.setVisible(bool(texto))

    # ------------------------------------------------------------------ ações
    def _pedir_clique(self):
        self.aguardando_clique = True
        self._atualizar_ponto()
        self.pedirCliqueMapa.emit()

    def _limpar_ponto(self):
        self.estado['referencePoint'] = None
        self.estado['autoDeclinationValue'] = None
        self.estado['meridianConvergence'] = None
        self._atualizar_tudo()

    def _coordenadas_digitadas(self):
        if self._montando:
            return
        try:
            lat = ler_numero(self.ed_lat.text())
            lon = ler_numero(self.ed_lon.text())
        except ValueError:
            return
        if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return
        atual = self.estado.get('referencePoint')
        if atual and abs(atual[0] - lon) < 1e-9 and abs(atual[1] - lat) < 1e-9:
            return
        self.definir_ponto(lon, lat)

    def _unidade_angular(self, _i):
        if self._montando:
            return
        nova = self.cb_ang.currentData()
        velha = self.estado['angularUnit']
        if nova == velha:
            return
        for l in self.estado['legs']:
            n = G.numero(l.get('azimuth'))
            l['azimuth'] = '' if n is None else G.limpo(G.converter_azimute(n, velha, nova))
        self.estado['angularUnit'] = nova
        self._atualizar_tudo()

    def _unidade_distancia(self, _i):
        if self._montando:
            return
        nova = self.cb_dist.currentData()
        velha = self.estado['distanceUnit']
        if nova == velha:
            return
        for l in self.estado['legs']:
            n = G.numero(l.get('distance'))
            l['distance'] = '' if not n else G.limpo(G.converter_distancia(n, velha, nova))
        self.estado['distanceUnit'] = nova
        self._atualizar_tudo()

    def _definir_modo(self, modo):
        if self.modo == EDITAR:
            return
        self.estado['outputMode'] = modo
        self._atualizar_tudo()

    def _definir_norte(self, norte):
        self.estado['northReference'] = norte
        self._atualizar_tudo()

    def _declinacao_digitada(self, texto):
        try:
            v = ler_numero(texto)
        except ValueError:
            return
        if v is None:
            return
        self.estado['magneticDeclination'] = max(-G.MAX_DECLINACAO, min(G.MAX_DECLINACAO, v))
        self.estado['manuallyEdited'] = True
        self._atualizar_derivados()

    def _calcular_auto(self):
        p = self.estado.get('referencePoint')
        if not p:
            return
        r = _decl.calcular_declinacao(p[1], p[0])
        if r:
            self.estado['autoDeclinationValue'] = r['declination']
            self.estado['autoDeclinationWarning'] = r['warning']

    def _aplicar_wmm(self):
        self._calcular_auto()
        if self.estado['autoDeclinationValue'] is not None:
            self.estado['magneticDeclination'] = self.estado['autoDeclinationValue']
            self.estado['manuallyEdited'] = False
            self._atualizar_tudo()

    def _perna_editada(self, item):
        if self._montando:
            return
        r, c = item.row(), item.column()
        if r >= len(self.estado['legs']):
            return
        campo = ('azimuth', 'distance', 'observation')[c]
        texto = item.text()
        perna = self.estado['legs'][r]
        ok = True
        if campo == 'observation':
            perna[campo] = texto[:12]
        else:
            try:
                v = ler_azimute(texto) if campo == 'azimuth' else ler_numero(texto)
            except ValueError:
                v, ok = None, False
            perna[campo] = '' if v is None else G.limpo(v)
            if ok and G.validar_perna({campo: perna[campo]}, self.estado['angularUnit']):
                ok = False
                perna[campo] = ''
        self._montando = True
        item.setBackground(QColor(0, 0, 0, 0) if ok else _VERMELHO)
        item.setToolTip('' if ok else 'Valor inválido: {}'.format(
            'azimute entre 0 e {}'.format(G.MILS_PER_CIRCLE if self.estado['angularUnit'] == G.MILESIMOS else 360)
            if campo == 'azimuth' else 'distância maior ou igual a 0'))
        self._montando = False
        self.estado['activeIndex'] = r
        self._atualizar_derivados()

    def _definir_ativa(self, r):
        if self._montando or r < 0 or r >= len(self.estado['legs']):
            return
        self.estado['activeIndex'] = r
        self._atualizar_leitura()
        self._atualizar_rapido()

    def _adicionar_perna(self):
        self.estado['legs'].append(perna_vazia())
        self.estado['activeIndex'] = len(self.estado['legs']) - 1
        self._atualizar_tudo()

    def _remover_perna(self):
        if len(self.estado['legs']) <= 1:
            return
        i = self.tab_pernas.currentRow()
        i = i if 0 <= i < len(self.estado['legs']) else len(self.estado['legs']) - 1
        self.estado['legs'].pop(i)
        self.estado['activeIndex'] = min(self.estado['activeIndex'], len(self.estado['legs']) - 1)
        self._atualizar_tudo()

    def _azimute_rapido(self, graus):
        valor = G.converter_azimute(graus, G.GRAUS, self.estado['angularUnit'])
        self.estado['legs'][self.estado['activeIndex']]['azimuth'] = G.limpo(float(valor))
        self._atualizar_tudo()

    def _importar_csv(self, caminho=None):
        if not caminho:
            caminho, _ = QFileDialog.getOpenFileName(self, 'Importar pernas', '', 'CSV (*.csv *.txt)')
        if not caminho:
            return 0
        try:
            pernas, ruins = ler_csv_pernas(caminho)
        except (OSError, UnicodeDecodeError) as e:
            self.avisar('Não foi possível ler o CSV: {}'.format(e), erro=True)
            return 0
        if not pernas:
            self.avisar('Nenhuma perna com azimute e distância no CSV.', erro=True)
            return 0
        vazias = all(not G.perna_completa(l) and not l.get('observation') for l in self.estado['legs'])
        self.estado['legs'] = pernas if vazias else self.estado['legs'] + pernas
        self.estado['activeIndex'] = len(self.estado['legs']) - 1
        self._atualizar_tudo()
        self.avisar('{} perna{} importada{} do CSV{}.'.format(
            len(pernas), 's' if len(pernas) != 1 else '', 's' if len(pernas) != 1 else '',
            '; {} linha{} ignorada{}'.format(ruins, 's' if ruins != 1 else '', 's' if ruins != 1 else '') if ruins else ''))
        return len(pernas)

    def _confirmar(self):
        pode, motivo = G.pode_criar(self.estado['referencePoint'], self.estado['legs'], self.estado['outputMode'])
        if not pode:
            self.avisar('Dados incompletos: {}.'.format(motivo), erro=True)
            return
        self.avisar('')
        if self.modo == EDITAR:
            self.salvarPedido.emit(self.estado_publico())
        else:
            self.criarPedido.emit(self.estado_publico())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancelarPedido.emit()
            e.accept()
            return
        super().keyPressEvent(e)

    # ------------------------------------------------------------------ redesenho
    def _atualizar_tudo(self):
        self._montando = True
        try:
            e = self.estado
            if self.modo == EDITAR:
                self.titulo.setText('<b>Editando:</b> {} ({})'.format(
                    getattr(self, 'nome_alvo', '') or 'construção', G.ROTULO_MODO.get(e['outputMode'], '')))
            else:
                self.titulo.setText('<b>Nova construção polar</b>')
            self.cb_ang.setCurrentIndex(self.cb_ang.findData(e['angularUnit']))
            self.cb_dist.setCurrentIndex(self.cb_dist.findData(e['distanceUnit']))
            for modo, b in self.bt_modo.items():
                b.setChecked(modo == e['outputMode'])
                b.setEnabled(self.modo == CRIAR or modo == e['outputMode'])
            for norte, b in self.bt_norte.items():
                b.setChecked(norte == e['northReference'])
            self.ed_decl.setText(G.texto_numero(e['magneticDeclination']))
            unidade_az = '₥' if e['angularUnit'] == G.MILESIMOS else '°'
            unidade_d = 'km' if e['distanceUnit'] == G.QUILOMETROS else 'm'
            self.tab_pernas.setHorizontalHeaderLabels(
                ['Azimute ({})'.format(unidade_az), 'Distância ({})'.format(unidade_d), 'Observação'])
            self.tab_pernas.setRowCount(len(e['legs']))
            for r, perna in enumerate(e['legs']):
                for c, campo in enumerate(('azimuth', 'distance', 'observation')):
                    v = perna.get(campo, '')
                    texto = v if campo == 'observation' else (G.texto_numero(G.numero(v)) if G.numero(v) is not None else '')
                    it = QTableWidgetItem(texto)
                    self.tab_pernas.setItem(r, c, it)
            self.tab_pernas.setCurrentCell(e['activeIndex'], self.tab_pernas.currentColumn() if self.tab_pernas.currentColumn() >= 0 else 0)
            self.bt_menos.setEnabled(len(e['legs']) > 1)
            self.bt_nova.setVisible(self.modo == EDITAR)
            self.bt_criar.setText('Salvar alterações' if self.modo == EDITAR else 'Criar {}'.format(G.ROTULO_MODO[e['outputMode']]))
            self.bt_cancelar.setText('Descartar' if self.modo == EDITAR else 'Cancelar')
        finally:
            self._montando = False
        self._atualizar_ponto()
        self._atualizar_derivados()

    def _atualizar_ponto(self):
        p = self.estado.get('referencePoint')
        self._montando = True
        try:
            if p:
                self.lbl_ponto.setText('{}, {}'.format(_decl.js_to_fixed(p[1], 6).replace('.', ','),
                                                       _decl.js_to_fixed(p[0], 6).replace('.', ',')))
                self.ed_lat.setText(_decl.js_to_fixed(p[1], 6).replace('.', ','))
                self.ed_lon.setText(_decl.js_to_fixed(p[0], 6).replace('.', ','))
            else:
                self.lbl_ponto.setText('Clique no mapa para definir o ponto de referência.'
                                       if self.aguardando_clique else 'Ponto de referência não definido.')
                self.ed_lat.clear()
                self.ed_lon.clear()
            if self.aguardando_clique and p:
                self.lbl_ponto.setText(self.lbl_ponto.text() + '  (clique no mapa para mudar)')
            self.bt_wmm.setEnabled(bool(p))
        finally:
            self._montando = False

    def _atualizar_derivados(self):
        e = self.estado
        p = e.get('referencePoint')
        if not p or e['autoDeclinationValue'] is None:
            self.lbl_auto.setText('▸ Defina o ponto de referência')
        else:
            v = e['autoDeclinationValue']
            un = '°'
            if e['angularUnit'] == G.MILESIMOS:
                v = float(_decl.js_to_fixed(v * G.DEG_TO_MIL, 1))
                un = '₥'
            self.lbl_auto.setText('▸ Auto: {}{} ({})'.format(
                G.texto_numero(v), un, 'WMM2025, expirado' if e['autoDeclinationWarning'] else 'WMM2025'))
        if not p:
            self.lbl_conv.setText('Conv: defina o ponto de referência')
        else:
            self.lbl_conv.setText('Conv: {} (auto, fuso {})'.format(
                G.texto_correcao(e['meridianConvergence']), G.zona_utm(p[0])))
        if e['northReference'] == G.NM and e['magneticDeclination'] != 0:
            sinal = '+' if e['magneticDeclination'] > 0 else ''
            self.lbl_corr.setText('Correção ativa: {}{}°'.format(sinal, G.texto_numero(e['magneticDeclination'])))
            self.lbl_corr.setVisible(True)
        elif e['northReference'] == G.NQ and p:
            self.lbl_corr.setText('Correção ativa: convergência {}'.format(G.texto_correcao(e['meridianConvergence'])))
            self.lbl_corr.setVisible(True)
        else:
            self.lbl_corr.setVisible(False)
        self._atualizar_leitura()
        self._atualizar_rapido()
        self._atualizar_tabela_nortes()
        n = len(e['legs'])
        self.lbl_resumo.setText('<b>{}</b> perna{} · Total: <b>{}</b>'.format(
            n, '' if n == 1 else 's', G.texto_total(G.distancia_total(e['legs']), e['distanceUnit'])))
        self.estadoMudou.emit(self.estado_publico())

    def leituras(self):
        e = self.estado
        return G.pernas_tres_nortes(e['legs'], e['angularUnit'], e['northReference'], e['magneticDeclination'],
                                    e['meridianConvergence'] if e['meridianConvergence'] is not None else 0)

    def _atualizar_leitura(self):
        e = self.estado
        i = e['activeIndex']
        leitura = self.leituras()[i] if i < len(e['legs']) else None
        if leitura is None:
            self.lbl_leitura.setText('')
        elif not e.get('referencePoint'):
            self.lbl_leitura.setText('Perna {}: defina o ponto de referência para ler os três nortes'.format(i + 1))
        else:
            u = e['angularUnit']
            self.lbl_leitura.setText('Perna {}: NV {} · NQ {} · NM {}'.format(
                i + 1, G.texto_angulo(leitura['nv'], u), G.texto_angulo(leitura['nq'], u), G.texto_angulo(leitura['nm'], u)))

    def _atualizar_rapido(self):
        e = self.estado
        self.lbl_rapido.setText('<b>Azimute rápido → Perna {}</b>'.format(e['activeIndex'] + 1))
        for b, rotulo, graus in self.bt_rapido:
            if e['angularUnit'] == G.MILESIMOS:
                b.setText('{} {}₥'.format(rotulo, _decl.js_round(graus * G.DEG_TO_MIL)))
            else:
                b.setText('{} {}°'.format(rotulo, graus))

    def _atualizar_tabela_nortes(self):
        e = self.estado
        leituras = self.leituras() if e.get('referencePoint') else [None] * len(e['legs'])
        u = e['angularUnit']
        self.tab_nortes.setRowCount(len(e['legs']))
        for r, perna in enumerate(e['legs']):
            leitura = leituras[r]
            d = G.numero(perna.get('distance'))
            celulas = [str(r + 1)]
            if leitura is None:
                celulas += ['-', '-', '-']
            else:
                celulas += [G.texto_azimute_tabela(leitura[k], u) for k in ('nv', 'nq', 'nm')]
            celulas.append(G.texto_distancia(G.distancia_em_metros(d, e['distanceUnit'])) if d else '-')
            for c, t in enumerate(celulas):
                it = QTableWidgetItem(t)
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tab_nortes.setItem(r, c, it)
