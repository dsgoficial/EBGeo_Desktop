# -*- coding: utf-8 -*-
"""
Painel de propriedades do calco: espelha os painéis do EBGeo Web para a feição
selecionada na camada ativa.

Todo tipo do calco é montado da sua especificação (formulario/especificacao.py), a mesma do
formulário nativo assado no estilo, com os widgets ricos dos blocos (ui/blocos/, ui/painel_area.py).
Cada mudança entra no BUFFER de edição da camada como um comando (Ctrl+Z desfaz), aberto pelo
painel se preciso; nada vai ao disco até "Salvar", e "Descartar" volta ao estado de antes. As
regras de troca e o SVG dos símbolos pontuais são do guardião da camada (guardiao.py).
"""
import math

from qgis.core import (
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeatureRequest,
    QgsVectorLayer, QgsGeometry,
)
from qgis.gui import QgsCollapsibleGroupBoxBasic, QgsColorButton
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from .. import regras, schema
from ..calco import tipo_da_camada
from ..formulario import especificacao as esp

# A secundária do Setor de Tiro sem valor (desenhos-parametricos.js do Web).
ANGULO_SECUNDARIO_PADRAO = -45.0


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
        self._tipos_widget = {}  # coluna -> o tipo do widget do dock (spec[0] de _widget)
        self._setor = None      # [principal, secundária] do Setor de Tiro, em azimute
        self._abertura = None   # QLabel "Abertura do setor"
        base = QWidget()
        self.vbox = QVBoxLayout(base)
        # o conteúdo nunca encolhe abaixo do tamanho pedido: a área de rolagem rola, em vez de
        # apertar o passo das linhas da seção mais longa (medido: 24 px contra 29 nas demais)
        self.vbox.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        self.titulo = QLabel('Selecione uma feição do calco.')
        self.titulo.setWordWrap(True)
        self.vbox.addWidget(self.titulo)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.vbox.addWidget(self.form_host)
        self.acoes = QHBoxLayout()
        self.vbox.addLayout(self.acoes)
        self.vbox.addStretch(1)
        # Salvar e Descartar, como no Web
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
        self._spec = None       # especificação do tipo montado
        self._amostra = None    # amostra da feição com o estilo da camada (blocos/previa.py)
        self._linhas = []       # (elemento, condições, layout, widget, rótulo) do painel da especificação
        self._secoes = []       # (caixa, condições, layout pai)
        self._expressoes = {}
        self._padroes = None    # o número que o estilo da camada desenha na coluna nula (padrao_estilo.py)
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
                                (self.layer.editingStopped, self._edicao_parou),
                                (self.layer.rendererChanged, self._estilo_mudou),
                                (self.layer.styleChanged, self._estilo_mudou)):
                try:
                    sinal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
        # a expressão avaliada guarda o índice da coluna da camada em que foi preparada: a mesma
        # condição ("show_label" ligado) na camada de outro tipo leria outra coluna
        self._expressoes = {}
        self._padroes = None
        self.layer = layer if isinstance(layer, QgsVectorLayer) else None
        self.tipo = tipo_da_camada(self.layer)
        if self.layer is not None and self.tipo in esp.TIPOS_COM_FORMULARIO:
            self.layer.selectionChanged.connect(self._selecao_mudou)
            self.layer.editingStopped.connect(self._edicao_parou)
            self.layer.rendererChanged.connect(self._estilo_mudou)
            self.layer.styleChanged.connect(self._estilo_mudou)
            from .. import guardiao
            guardiao.garantir(self.layer, self.tipo)
        self._selecao_mudou()

    def _estilo_mudou(self, *args):
        self._padroes = None

    def padrao_do_estilo(self, col):
        """
        O número que o estilo da camada desenha com a coluna nula, para a feição do dock, ou None
        quando o estilo não dá número ao nulo (padrao_estilo.py). O dock o mostra, sem gravar.
        """
        if self.layer is None or self.fid is None:
            return None
        if self._padroes is None:
            from .padrao_estilo import PadroesDoEstilo
            self._padroes = PadroesDoEstilo(self.layer)
        return self._padroes.valor(col, self.layer.getFeature(self.fid))

    def _mostrar_nulo(self, col, w, fator=1.0):
        """
        A caixa giratória da coluna nula mostra o que o desenho usa: o número do estilo (a faixa se
        abre para ele, se preciso) ou, sem número, "Não definido" um passo abaixo da faixa, que
        grava nulo se o operador o escolher.
        """
        n = self.padrao_do_estilo(col)
        if n is None:
            _abrir_nulo(w)
            w.setValue(w.minimum())
            return
        n *= fator
        if not w.minimum() <= n <= w.maximum():
            w.setRange(min(w.minimum(), n), max(w.maximum(), n))
        w.setValue(n)

    def _mostrar_logico_nulo(self, col, w):
        """
        A caixa da coluna lógica nula mostra o que o desenho usa (o "mostrar no mapa" nulo é
        mostrar, a Correção de Zoom nula é corrigir), sem gravar; sem forma no estilo, o terceiro
        estado, "Não definido", que grava nulo se o operador voltar a ele.
        """
        v = None
        if self.layer is not None and self.fid is not None:
            if self._padroes is None:
                from .padrao_estilo import PadroesDoEstilo
                self._padroes = PadroesDoEstilo(self.layer)
            v = self._padroes.valor(col, self.layer.getFeature(self.fid), logico=True)
        if v is None:
            w.setTristate(True)  # o terceiro estado é o nulo, a que o operador pode voltar
            w.setCheckState(Qt.CheckState.PartiallyChecked)
        else:
            w.setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)
        _texto_da_caixa(w)

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
        if self.layer is None or not self.tipo in esp.TIPOS_COM_FORMULARIO:
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
        self._montar_spec(feat)

    def _limpar(self):
        self.fid = None
        self.widgets = {}
        self._tipos_widget = {}
        self._setor = None
        self._abertura = None
        self._spec = None
        self._amostra = None
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
            if nulo:
                self._mostrar_nulo(col, w)
            else:
                w.setValue(float(valor))
            w.valueChanged.connect(lambda v, c=col, w=w: self._mudou(c, _valor_do_spin(w, v)))
        elif kind == 'km_em_m':
            w = QDoubleSpinBox()
            w.setRange(spec[1], spec[2])
            w.setSingleStep(spec[3])
            w.setDecimals(0)
            w.setSuffix(' m')
            if nulo:
                self._mostrar_nulo(col, w, 1000.0)
            else:
                w.setValue(float(valor) * 1000.0)
            w.valueChanged.connect(lambda v, c=col, w=w: self._mudou(c, _valor_do_spin(w, v, 1000.0)))
        elif kind == 'bool':
            w = QCheckBox()
            if nulo:
                self._mostrar_logico_nulo(col, w)
            else:
                w.setChecked(bool(valor))
            w.stateChanged.connect(lambda _s, c=col, w=w: self._mudou(c, _valor_da_caixa(w)))
        elif kind == 'combo':
            w = QComboBox()
            imagens = spec[2] if len(spec) > 2 else {}
            for v, rot in spec[1]:
                w.addItem(rot, v)
                if imagens.get(v):
                    w.setItemIcon(w.count() - 1, _icone(*imagens[v]))
            i = w.findData(None if nulo else str(valor))
            if i < 0 and not nulo:
                from ..formulario.tipos.comuns import PREFIXO_ICONE, ROTULO_ICONE
                # ícone próprio que o arquivo não tem mais: legível, sem o código cru
                w.addItem(ROTULO_ICONE if str(valor).startswith(PREFIXO_ICONE) else str(valor), str(valor))
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
        elif kind == 'azimute':
            w = _spin_azimute(self.padrao_do_estilo(col) if nulo else valor)
            w.valueChanged.connect(lambda v, c=col: self._mudou(c, float(v)))
        elif kind in ('dir_principal', 'dir_secundaria'):
            i = 0 if kind == 'dir_principal' else 1
            w = _spin_azimute(self._setor[i])
            w.valueChanged.connect(lambda v, i=i: self._setor_mudou(i, v))
        elif kind.startswith('area_'):
            from .painel_area import widget_area
            w = widget_area(self, col, spec, valor, nulo)
            if w is None:
                return None
        elif kind.startswith('medida_'):
            from .blocos.medida import widget_medida
            w = widget_medida(self, col, spec, valor, nulo)
            if w is None:
                return None
        else:
            return None
        self.widgets[col] = w
        self._tipos_widget[col] = kind
        return w

    def _seletor_engenharia(self):
        from .seletor_engenharia import SeletorEngenharia
        feat = self.layer.getFeature(self.fid)
        dlg = SeletorEngenharia(feat['point_code'], feat['engineering'], self)
        if dlg.exec():
            self._pendentes.update(dlg.valores())
            self._gravar_pendentes()
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
        # remontar fora do sinal: apagar o combo dentro do próprio currentIndexChanged derruba o QGIS
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
            from .blocos.militar import aplicar_construtor  # no buffer, e o painel remontado
            aplicar_construtor(self, novo)

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
        self._gravar_no_buffer(mudancas)

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
        fid = self.fid
        self._no_buffer(lambda: self.layer.changeGeometry(fid, nova), 'Calco: inverter sentido')

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
            from .blocos.previa import amostra_no_topo  # linhas, áreas, táticos e comuns
            self._amostra = amostra_no_topo(self)
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
            from .blocos.taticos import TIPOS_INVERTER
            if self.tipo == 'coordination_line' or self.tipo in TIPOS_INVERTER:
                b = QPushButton('Inverter sentido')
                b.clicked.connect(self._inverter)
                b.setEnabled(not travada)
                self.acoes.addWidget(b)
            from .blocos import militar as bloco_militar  # Recalcular da declinação
            bloco_militar.acoes(self, travada)
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
        if getattr(el, 'campo_rico', None) is not None:
            el = el.campo_rico  # resumo só de leitura do nativo (tipos/area.Resumo): no dock, o editor rico
        if isinstance(el, esp.Grupo):
            proprias = conds + ([el.condicao] if el.condicao is not None else [])
            if el.titulo:
                _caixa, fl = self._secao(fl, el.nome, el.recolhido, proprias)
            for filho in el.filhos:
                self._elemento(fl, filho, proprias, attrs, travada)
            return
        from .blocos.taticos import elemento_rico as rico_taticos  # posições do Limite, caixas de nulo
        if rico_taticos(self, fl, el, conds, attrs, travada):
            return
        if isinstance(el, esp.Texto):
            from .blocos.previa import elemento_rico as rico_previa  # prévia do símbolo pontual
            if rico_previa(self, fl, el, conds, attrs, travada):
                return
            from .blocos.comuns import elemento_rico as rico_comuns  # Fotos e Azimute e Distância
            if rico_comuns(self, fl, el, conds, attrs, travada):
                return
            from .blocos.militar import texto_avaliado  # [% %] da especificação, na feição do buffer
            lb = QLabel(texto_avaliado(self, el.texto))
            lb.setWordWrap(True)
            fl.addRow(lb)
            self._linhas.append((el, conds, fl, lb, None))
            return
        if el.coluna not in attrs:
            return
        spec = _spec_do_campo(el)
        if el.opcoes_da_camada is not None and spec[0] == 'combo':
            extras = el.opcoes_da_camada(self.layer)
            spec = ('combo', list(spec[1]) + [(v, r) for v, r, _img in extras], {v: img for v, _r, img in extras if img})
        w = self._widget(el.coluna, spec, attrs[el.coluna])
        if w is None:
            return
        altura_uniforme(w)
        rotulo = QLabel(el.rotulo_para(attrs, rico=bool(el.rico)))
        dica = el.dica_para(attrs)
        if dica:  # a dica do Web, no rótulo e no campo
            rotulo.setToolTip(dica)
            w.setToolTip(dica)
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
                if rotulo is not None and el.expressao_rotulo_dock():
                    rotulo.setText(str(self._expressao(el.expressao_rotulo_dock()).evaluate(ctx)))
                if rotulo is not None and el.dica_por is not None:
                    dica = el.dica_para({n: feat[n] for n in feat.fields().names()}) or ''
                    rotulo.setToolTip(dica)
                    w.setToolTip(dica)
            elif hasattr(w, 'atualizar'):  # a prévia do símbolo (blocos/previa.py)
                w.atualizar(self)
            elif isinstance(el, esp.Texto) and '[%' in el.texto:
                from .blocos.militar import texto_avaliado
                w.setText(texto_avaliado(self, el.texto))
        for caixa, conds, fl in self._secoes:
            fl.setRowVisible(caixa, all(vale(c) for c in conds))
        if self._amostra is not None:
            self._amostra.atualizar(self)

    def campos_visiveis(self):
        """As colunas que o painel da especificação mostra para a feição atual."""
        return set(getattr(self, '_visiveis', set())) if self._spec is not None else set()

    # ---------- buffer de edição, Salvar e Descartar ----------
    def _gravar_no_buffer(self, mudancas):
        fid = self.fid
        idx = self.layer.fields().indexOf
        valores = {idx(c): v for c, v in schema.atributos_para_qgis(self.tipo, mudancas).items() if idx(c) >= 0}
        mostrados = [c for c in self._tipos_widget if c not in mudancas and idx(c) >= 0]
        antes = self.layer.getFeature(fid)
        antes = {c: antes[c] for c in mostrados} if antes.isValid() else {}

        def mudar():
            for i, v in valores.items():
                self.layer.changeAttributeValue(fid, i, v)
        self._no_buffer(mudar)
        self._mostrar_regras(fid, antes)
        ramos = self.widgets.get('ramos')
        if ramos is not None and hasattr(ramos, 'reler') and 'ramos' not in mudancas:
            ramos.reler()  # a seta inteira mudou: o que cada ramo desenha
        self._aplicar_condicoes()

    def _mostrar_regras(self, fid, antes):
        """
        O que o guardião mudou no mesmo passo (as regras de troca: a opacidade que vai a 1 com a
        hachura, a cor do tipo) aparece nos widgets do dock, sem gravar de novo.
        """
        depois = self.layer.getFeature(fid)
        if not depois.isValid():
            return
        self._carregando = True
        try:
            for col, v in antes.items():
                if regras.nao_definido(v) or regras.nao_definido(depois[col]):
                    continue
                if not regras.iguais(v, depois[col]):
                    self._mostrar_valor(col, depois[col])
        finally:
            self._carregando = False

    def _mostrar_valor(self, col, valor):
        """Põe o valor no widget simples do dock (os ricos se remontam por conta própria)."""
        w, kind = self.widgets.get(col), self._tipos_widget.get(col)
        nulo = esp._nulo(valor)
        if kind == 'num':
            if nulo:
                self._mostrar_nulo(col, w)
            else:
                w.setValue(float(valor))
        elif kind == 'km_em_m':
            if nulo:
                self._mostrar_nulo(col, w, 1000.0)
            else:
                w.setValue(float(valor) * 1000.0)
        elif kind == 'bool':
            if nulo:
                self._mostrar_logico_nulo(col, w)
            else:
                w.setCheckState(Qt.CheckState.Checked if bool(valor) else Qt.CheckState.Unchecked)
                _texto_da_caixa(w)
        elif kind == 'combo':
            i = w.findData(None if nulo else str(valor))
            if i >= 0:
                w.setCurrentIndex(i)
        elif kind == 'cor':
            if nulo:
                w.setToNull()
            else:
                w.setColor(QColor(str(regras.valor(valor))))
        elif kind == 'texto':
            w.setText('' if nulo else str(valor))

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
    if campo.rico in ('sidc', 'engenharia'):  # construtor de SIDC e seletor do C 5-36 (blocos/militar.py)
        return (campo.rico,)
    if campo.rico and campo.rico.startswith('medida_'):
        return (campo.rico,) + tuple(campo.rico_config)
    if campo.rico and campo.rico.startswith('area_'):  # Área de Coordenação: ui/painel_area.widget_area
        return (campo.rico,) + tuple(campo.rico_config)
    w, c = campo.widget, campo.widget.config
    if getattr(w, 'faixa', None) is not None:  # número (esp.numero): caixa giratória no dock
        return ('num',) + tuple(w.faixa)
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


_ALTURA = []


def altura_uniforme(w):
    """
    Campo de uma linha com a altura da maior caixa de uma linha (o botão de cor é mais alto que a
    caixa de texto, e a caixa de marcar mais baixa): as linhas da seção ficam com o mesmo passo.
    """
    if not isinstance(w, (QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QgsColorButton, QCheckBox)):
        return
    if not _ALTURA:
        _ALTURA.append(max(c().sizeHint().height() for c in (QLineEdit, QComboBox, QDoubleSpinBox, QgsColorButton)))
    w.setFixedHeight(_ALTURA[0])


def _icone(mime, b64):
    """QIcon da imagem em base64 (a miniatura do ícone próprio na lista)."""
    import base64
    from qgis.PyQt.QtGui import QIcon, QPixmap
    pm = QPixmap()
    pm.loadFromData(base64.b64decode(b64))
    return QIcon(pm)


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


def _valor_da_caixa(w):
    """O valor da caixa de marcar; o terceiro estado ("Não definido") é nulo."""
    _texto_da_caixa(w)
    estado = w.checkState()
    if estado == Qt.CheckState.PartiallyChecked:
        return None
    return estado == Qt.CheckState.Checked


def _texto_da_caixa(w):
    from .padrao_estilo import TEXTO_NULO
    w.setText(TEXTO_NULO if w.checkState() == Qt.CheckState.PartiallyChecked else '')


def _abrir_nulo(w):
    """Um passo abaixo da faixa, a caixa giratória mostra "Não definido" e vale nulo."""
    from .padrao_estilo import TEXTO_NULO
    if not w.property('ebgeo_nulo'):
        w.setMinimum(w.minimum() - w.singleStep())
        w.setSpecialValueText(TEXTO_NULO)
        w.setProperty('ebgeo_nulo', True)


def _valor_do_spin(w, v, fator=1.0):
    """O valor da caixa giratória na unidade da coluna; "Não definido" é nulo."""
    if w.property('ebgeo_nulo') and v == w.minimum():
        return None
    return v / fator


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


def _spin_azimute(graus):
    w = QSpinBox()
    w.setRange(0, 359)
    w.setSingleStep(1)
    w.setWrapping(True)
    w.setSuffix('°')
    w.setValue(int(math.floor(normalizar_azimute(graus if _numero_finito(graus) else 0.0) + 0.5)) % 360)
    return w
