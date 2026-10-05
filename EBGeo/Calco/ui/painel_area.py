# -*- coding: utf-8 -*-
"""
Painel da Área de Coordenação, espelho de coordination_area_attributes_panel.js do EBGeo
Web: as linhas do formulário dependem do tipo (escalão no Ponto Forte, portões no Volume de
aproximação de base, minas na Área minada, altitudes só no Volume). O PainelCalco chama
`linhas_area` para montar o formulário e `widget_area` para os campos próprios do tipo.

Portões: "Acrescentar portão" põe um na metade da borda e "Marcar portão na borda" espera um
clique no mapa e o põe no ponto da borda mais próximo (Esc cancela); cada portão tem nome e
posição na borda em %, como no Web.
"""
import json

from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsSettings
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .. import estilos_area as ea

ESTILOS_TRACO = [('solid', 'Sólida'), ('dashed', 'Tracejada'), ('dotted', 'Pontilhada'), ('dash-dot', 'Traço-ponto'),
                 ('long-dash', 'Traço longo'), ('short-dash', 'Traço curto'), ('dot-dot-dash', 'Ponto-ponto-traço')]
HACHURAS = [('none', 'Nenhuma'), ('diagonal-right', 'Diagonal /'), ('diagonal-left', 'Diagonal \\'),
            ('horizontal', 'Horizontal'), ('vertical', 'Vertical'), ('cross', 'Cruz +'),
            ('cross-diagonal', 'Cruz X'), ('dots', 'Pontos')]


def linhas_area(feat):
    """(coluna, rótulo, spec) do formulário para o tipo da área."""
    cod = feat['symbol_code'] if feat['symbol_code'] in ea.CATALOGO_AREA else ea.SIMBOLO_PADRAO
    sim = ea.CATALOGO_AREA[cod]
    out = [('symbol_code', 'Símbolo', ('area_tipo',)),
           ('symbol_size_km', 'Tamanho do símbolo (m)', ('km_em_m', 10, 50000, 10)),
           ('zoom_corr', 'Correção de Zoom', ('bool',)),
           ('created_zoom', 'Zoom de referência', ('num', 0, 22, 0.1, 1)),
           ('line_color', 'Borda', ('cor',)),
           ('line_width', 'Espessura da borda (px)', ('num', 1, 10, 1, 0))]
    if sim['borda'] != 'elos':
        out.append(('line_style', 'Estilo da borda', ('combo', ESTILOS_TRACO)))
    out += [('fill_color', 'Preenchimento', ('cor',)),
            ('opacity', 'Opacidade do preenchimento', ('num', 0, 1, 0.05, 2)),
            ('hatch_type', 'Hachura', ('area_hachura',)),
            ('hatch_spacing', 'Espaçamento da hachura (px)', ('num', 2, 40, 1, 0)),
            ('hatch_line_width', 'Espessura da hachura (px)', ('num', 0.5, 10, 0.5, 1))]
    if sim.get('escalao'):
        out.append(('escalao', 'Escalão', ('combo', [('', 'Nenhum')] + [(e, ea.rotulo_escalao(e)) for e in ea.ESCALOES])))
    if sim.get('portoes'):
        out += [('portoes', 'Portões', ('area_portoes',)), ('portoes_ocultos', 'Ocultar portões', ('bool',))]
    if sim.get('minas'):
        out.append(('minas', 'Minas', ('area_minas',)))
    out += [('tipo', 'Tipo', ('texto',)), ('identificacao', 'Identificação', ('texto',))]
    if sim.get('portoes'):
        out += [('altitude_max', 'Altitude máxima', ('texto',)), ('altitude_min', 'Altitude mínima', ('texto',))]
    out += [('gdh_ini', 'GDH Início', ('texto',)), ('gdh_fim', 'GDH Fim', ('texto',))]
    if not sim.get('portoes'):
        out.append(('outras_info', 'Outras informações', ('texto',)))
    out += [('text_position', 'Posição do texto', ('combo', ea.POSICOES_TEXTO)),
            ('text_ratio', 'Posição do escalão na borda (%)' if sim.get('escalao') else 'Posição na borda (%)',
             ('area_pct',)),
            ('text_north_facing', 'Texto sempre para o norte', ('bool',)),
            ('text_size', 'Tamanho do texto (px)', ('num', 8, 40, 1, 0))]
    return out


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
    """Widget dos campos próprios da área; None para os que o painel comum monta."""
    kind = spec[0]
    if kind == 'area_tipo':
        w = QComboBox()
        for cod, sim in ea.CATALOGO_AREA.items():
            w.addItem('{} ({})'.format(sim['nome'], cod), cod)
        i = w.findData(None if nulo else str(valor))
        w.setCurrentIndex(max(i, 0))
        w.currentIndexChanged.connect(lambda _i, w=w: _tipo_mudou(painel, w.currentData()))
        return w
    if kind == 'area_hachura':
        w = QComboBox()
        for v, rot in HACHURAS:
            w.addItem(rot, v)
        w.setCurrentIndex(max(w.findData('none' if nulo else str(valor)), 0))
        w.currentIndexChanged.connect(lambda _i, w=w: _hachura_mudou(painel, w.currentData()))
        return w
    if kind == 'area_pct':
        w = QSpinBox()
        w.setRange(0, 100)
        w.setSuffix(' %')
        w.setValue(0 if nulo else int(round(float(valor) * 100)))
        w.valueChanged.connect(lambda v, c=col: painel._mudou(c, v / 100.0))
        return w
    if kind == 'area_minas':
        return EditorMinas(painel, col, valor)
    if kind == 'area_portoes':
        return EditorPortoes(painel, col, valor)
    return None


def _tipo_mudou(painel, codigo):
    if painel._carregando or painel.fid is None:
        return
    feat = painel.layer.getFeature(painel.fid)
    atuais = {f.name(): (None if feat[f.name()] is None or (hasattr(feat[f.name()], 'isNull') and feat[f.name()].isNull())
                         else feat[f.name()]) for f in painel.layer.fields()}
    painel._pendentes.update(ea.troca_de_simbolo(atuais, codigo))
    painel._gravar_pendentes()
    QgsSettings().setValue(ea.CHAVE_ULTIMO_TIPO, codigo)
    # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
    QTimer.singleShot(0, painel._selecao_mudou)


def _hachura_mudou(painel, tipo):
    painel._mudou('hatch_type', tipo)
    painel._mudou('hatch_enabled', tipo != 'none')


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
