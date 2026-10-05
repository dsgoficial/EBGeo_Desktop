# -*- coding: utf-8 -*-
"""
Formulário das linhas táticas sem catálogo: Linha de Limite, Seta e Frente Ocupada
(formulario/tipos/taticos.py, ui/blocos/taticos.py e o bloco do Limite em regras.py).

  - Especificação: mostra, em cada feição de teste, o que o dock de antes mostrava (RETRATO_DOCK,
    medido no dock de 86f7d3b em 2026-10-05), salvo os campos que o ESTILO ignora naquela feição
    (SOME_QUANDO: sem ponta não há ponta dupla nem comprimento da ponta; sem aeromóvel, a posição
    dele). As condições saem da expressão do estilo (seta.exp), e a expressão QGIS de cada uma dá
    o mesmo que a regra em Python. Toda coluna está no formulário ou entre os ocultos.
  - Formulário nativo, aberto num processo NOVO e SEM o plugin (e de novo com ele): nenhum
    código, só widgets nativos, aliases, ocultos também na tabela, campos visíveis por feição, a
    feição bloqueada só para leitura, o resumo das posições do Limite igual ao que o estilo
    desenha (lista do importador e texto JSON), salvar sem mudar não muda nada, e editar o nome
    pelo formulário e salvar deixa o desenho igual pixel a pixel e as demais colunas iguais.
  - Dock: os mesmos campos que a especificação, o editor das posições no buffer (Salvar grava a
    lista que o estilo lê, Descartar volta), Inverter sentido no Limite e na Seta, bloqueada só
    para leitura.
  - Guardião: posições ilegíveis gravadas por outro caminho voltam ao valor anterior; a Seta
    bloqueada não se edita pela calculadora.

Cada régua é provada contra a saída real degradada, que ela tem de reprovar. Capturas do
formulário nativo (com e sem o plugin) e do dock em EBGEO_TESTE_SAIDA (padrão: temporária); com
QT_QPA_PLATFORM=offscreen, o texto só sai legível com QT_QPA_FONTDIR apontando as fontes do sistema.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_taticos.py
"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDefaultValue, QgsEditorWidgetSetup,
    QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsMapSettings,
    QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import calco as C, gpkg, schema, regras, estilos_taticos as et  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402

TIPOS = ('boundary', 'arrow', 'occupied_front')
TMP = tempfile.mkdtemp(prefix='ebgeo_form_taticos_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []

# O dock de 86f7d3b, montado para uma feição de cada tipo (as colunas com widget; ele as mostrava
# sempre, sem condição) e os botões de ação dele.
RETRATO_DOCK = {
    'boundary': {'nome', 'descricao', 'echelon', 'symbol_size_km', 'symbol_instances', 'text_top', 'text_bottom',
                 'text_size', 'text_distance_ratio', 'text_north_facing', 'color', 'line_width', 'opacity',
                 'zoom_corr', 'created_zoom'},
    'arrow': {'nome', 'descricao', 'width_m', 'head_length_ratio', 'show_arrow_head', 'double_headed', 'airmobile',
              'airmobile_position', 'fill_color', 'line_color', 'fill_opacity', 'line_width'},
    'occupied_front': {'nome', 'descricao', 'color', 'line_width', 'opacity'},
}
BOTOES_DOCK = {'boundary': ['Inverter sentido'], 'arrow': ['Inverter sentido'], 'occupied_front': []}
# O que a escala deixa de mostrar onde o estilo ignora o valor (seta.exp): coluna -> {coluna: valor}.
SOME_QUANDO = {
    'arrow': {'double_headed': {'show_arrow_head': False}, 'head_length_ratio': {'show_arrow_head': False},
              'airmobile_position': {'airmobile': False}},
}
# O valor que seta.exp dá à coluna booleana nula (lido do arquivo pela régua, não pela especificação).
NULO_NA_SETA = {c: v == 'true' for c, v in re.findall(r'coalesce\("(\w+)", (true|false)\)', et.ler_expressao('seta'))}
INSTANCIAS = [{'ratio': 0.25, 'showLabels': True}, {'ratio': 0.5, 'showLabels': False}, {'ratio': 0.8, 'showLabels': True}]
RESUMO_3 = '25 %, 50 % (sem rótulos), 80 %'
ATTR = (('attr_capacidade', 'Capacidade', '400'), ('attr_agua_potavel', 'Água potável', 'sim'))

# As feições de teste, chaveadas pelo ebgeo_id (ASCII: vai na linha de comando do processo novo).
FEICOES = {
    'boundary': {
        'limite_3': dict(nome='Limite com 3 símbolos', echelon='XX', symbol_instances=INSTANCIAS, text_top='1ª DE',
                         text_bottom='2ª DE', text_north_facing=True),
        'limite_texto': dict(nome='Limite com as posições em texto', echelon='III', symbol_instances=json.dumps(INSTANCIAS),
                             text_top='ALFA'),
        'limite_nulo': dict(nome='Limite de equipe sem posições', echelon='Ø', symbol_instances=None),
        'limite_bloqueada': dict(nome='Limite bloqueado', echelon='XXX', bloqueado=True),
        # como o Web grava pelas alças (tamanho pelo zoom, distância do texto arrastada): casas à vontade
        'limite_web': dict(nome='Limite com valores do Web', echelon='X', symbol_size_km=0.6103515625,
                           text_distance_ratio=1.2345678901, text_size=37, created_zoom=12.3, text_top='B',
                           text_north_facing=True),
        # como o importador grava a feição sem as propriedades (fixtures: uma por tipo)
        'limite_nulos': dict(nome='Limite sem propriedades', echelon=None, symbol_size_km=None, text_size=None,
                             text_distance_ratio=None, text_north_facing=None, color=None, line_width=None,
                             opacity=None, zoom_corr=None, created_zoom=None, text_top='C', visivel=None),
    },
    'arrow': {
        'seta_aeromovel_dupla': dict(nome='Seta aeromóvel com duas pontas', airmobile=True, double_headed=True,
                                     airmobile_position=0.4, fill_color='#c0392b', line_color='#7b241c'),
        'seta_sem_ponta': dict(nome='Seta sem ponta', show_arrow_head=False, width_m=800),
        'seta_padrao': dict(nome='Seta padrão'),
        'seta_nula': dict(nome='Seta de booleanos nulos', show_arrow_head=None, double_headed=None, airmobile=None),
        'seta_web': dict(nome='Seta com valores do Web', width_m=1234.5678, head_length_ratio=1.8765432,
                         airmobile=True, airmobile_position=0.43219876, fill_opacity=0.35, line_opacity=0.65),
        'seta_nulos': dict(nome='Seta sem propriedades', width_m=None, head_length_ratio=None, airmobile_position=None,
                           fill_color=None, line_color=None, line_width=None, fill_opacity=None, line_opacity=None,
                           visivel=None),
    },
    'occupied_front': {
        'frente': dict(nome='Frente Ocupada', color='#1f618d', line_width=5),
        'frente_nula': dict(nome='Frente sem propriedades', color=None, line_width=None, opacity=None, visivel=None),
    },
}
CAPTURAS = ('limite_3', 'seta_aeromovel_dupla', 'seta_sem_ponta', 'frente', 'limite_bloqueada')
GEOMETRIA = {'boundary': 'LINESTRING(-47 -15, -46.93 -15.02, -46.86 -15.0)',
             'arrow': 'MULTILINESTRING((-47 -15, -46.93 -15.02, -46.86 -15.0))',
             'occupied_front': 'LINESTRING(-47 -15, -46.93 -15.02, -46.86 -15.0)'}


def specs():
    return {t: esp.formulario(t) for t in TIPOS}


def atributos(tipo, eid):
    a = dict(schema.padroes(tipo))
    a.update(FEICOES[tipo][eid])
    a['ebgeo_id'] = eid
    return a


def _vale(attrs, quando):
    for col, alvo in quando.items():
        v = attrs.get(col)
        if v is None:
            v = NULO_NA_SETA[col]
        if bool(v) != alvo:
            return False
    return True


def esperado_retrato(tipo, attrs):
    """O que o dock de antes mostrava, menos o que o estilo ignora nesta feição."""
    some = {col for col, quando in SOME_QUANDO.get(tipo, {}).items() if _vale(attrs, quando)}
    return RETRATO_DOCK[tipo] - some


def divergencias(spec, tipo, attrs):
    """[(feição, esperado, obtido)]: a especificação contra o retrato do dock de antes."""
    colunas = RETRATO_DOCK[tipo] | {c.coluna for c in spec.campos()}
    vistos = {c for c in colunas if spec.visivel(c, attrs)}
    if tipo == 'boundary' and _resumo_presente(spec):
        vistos.add('symbol_instances')  # no lugar do campo: o resumo no nativo, o editor no dock
    esperado = esperado_retrato(tipo, attrs)
    erros = []
    if not esperado <= vistos:
        erros.append((attrs.get('ebgeo_id'), 'faltam', sorted(esperado - vistos)))
    for col in RETRATO_DOCK[tipo] - esperado:
        if col in vistos:
            erros.append((attrs.get('ebgeo_id'), 'sobra', col))
    return erros


def resumo_esperado(valor):
    """O resumo das posições escrito em Python, das funções puras que o dock usa."""
    lista, _ok = regras.ler_instancias_limite(valor)
    return ', '.join('{} %{}'.format(int(round(i['ratio'] * 100)), '' if i['showLabels'] else ' (sem rótulos)')
                     for i in lista)


def _resumo_presente(spec):
    from Calco.formulario.tipos.taticos import RESUMO_POSICOES
    return [all(c.avaliar({}) for c in conds) for el, conds in spec.percorrer()
            if isinstance(el, esp.Texto) and el.nome == RESUMO_POSICOES] == [True]


def condicoes(spec):
    vistas = []
    for el, conds in spec.percorrer():
        for c in conds:
            if c not in vistas:
                vistas.append(c)
    return vistas


def avaliar(expressao, campos_valores):
    from qgis.core import QgsField, QgsFields
    from qgis.PyQt.QtCore import QMetaType
    campos = QgsFields()
    for nome in campos_valores:
        campos.append(QgsField(nome, QMetaType.Type.Bool))
    f = QgsFeature(campos)
    for i, v in enumerate(campos_valores.values()):
        f.setAttribute(i, v)
    ctx = QgsExpressionContext()
    ctx.setFeature(f)
    e = QgsExpression(expressao)
    v = e.evaluate(ctx)
    assert not e.hasEvalError(), (expressao, e.evalErrorString())
    return v


def avaliar_no_mapa(expr, vl, f):
    """A expressão do estilo com o mapa montado (o @map_scale do desenho)."""
    ms = QgsMapSettings()
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(1000, 800))
    ms.setOutputDpi(96)
    c = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(),
                               QgsProject.instance()).transform(QgsPointXY(-46.93, -15.01))
    ms.setExtent(QgsRectangle(c.x() - 15000, c.y() - 12000, c.x() + 15000, c.y() + 12000))
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ctx.setFeature(f)
    e = QgsExpression(expr)
    e.prepare(ctx)
    v = e.evaluate(ctx)
    assert not e.hasEvalError(), e.evalErrorString()
    return v


# ---------------------------------------------------------------------------------------------
# Especificação
# ---------------------------------------------------------------------------------------------

class TesteEspecificacao(unittest.TestCase):
    def test_os_tres_tem_formulario(self):
        self.assertTrue(set(TIPOS) <= esp.TIPOS_COM_FORMULARIO)
        for t in TIPOS:
            self.assertIsNotNone(esp.formulario(t), t)

    def test_mostra_o_que_o_dock_mostrava(self):
        sp = specs()
        erros = [e for t in TIPOS for eid in FEICOES[t] for e in divergencias(sp[t], t, atributos(t, eid))]
        self.assertEqual(erros, [])

    def test_regua_reprova_especificacao_degradada(self):
        sp = specs()
        # pior caso 1: a posição do aeromóvel perde a condição (aparece na seta comum)
        ruim = copy.deepcopy(sp['arrow'])
        ruim.campo('airmobile_position').condicao = None
        self.assertTrue(any(e[1] == 'sobra' for e in divergencias(ruim, 'arrow', atributos('arrow', 'seta_padrao'))))
        # pior caso 2: o padrão da ponta com o lado trocado (a seta de booleanos nulos perde a ponta dupla)
        ruim = copy.deepcopy(sp['arrow'])
        c = ruim.campo('double_headed')
        c.condicao = type(c.condicao)(c.condicao.coluna, not c.condicao.padrao)
        self.assertTrue(divergencias(ruim, 'arrow', atributos('arrow', 'seta_nula')))
        # pior caso 3: o Limite sem o resumo das posições
        ruim = copy.deepcopy(sp['boundary'])
        for aba in ruim.abas:
            aba.filhos = [f for f in aba.filhos if not (isinstance(f, esp.Texto) and f.nome == 'posicoes_limite')]
        self.assertTrue(divergencias(ruim, 'boundary', atributos('boundary', 'limite_3')))
        # pior caso 4: a Frente Ocupada sem a espessura
        ruim = copy.deepcopy(sp['occupied_front'])
        ruim.abas[0].filhos = [f for f in ruim.abas[0].filhos if getattr(f, 'coluna', '') != 'line_width']
        self.assertTrue(divergencias(ruim, 'occupied_front', atributos('occupied_front', 'frente')))

    def test_condicoes_saem_do_estilo_e_o_qgis_concorda(self):
        sp = specs()
        conds = condicoes(sp['arrow'])
        self.assertEqual({(c.coluna, c.padrao) for c in conds if hasattr(c, 'padrao')},
                         {('show_arrow_head', NULO_NA_SETA['show_arrow_head']), ('airmobile', NULO_NA_SETA['airmobile'])})
        n = 0
        for cond in conds + condicoes(sp['boundary']) + condicoes(sp['occupied_front']):
            for v in (None, False, True):
                for bloq in (None, False, True):
                    col = getattr(cond, 'coluna', 'bloqueado')
                    vals = {col: v} if col == 'bloqueado' else {col: v, 'bloqueado': bloq}
                    py = cond.avaliar(vals)
                    qg = bool(avaliar(cond.expressao(), vals))
                    self.assertEqual(py, qg, (cond.expressao(), vals))
                    n += 1
        MEDIDAS.append('condições conferidas no QGIS contra o Python: {} casos'.format(n))
        # régua: a expressão com o padrão trocado discorda
        c = sp['arrow'].campo('airmobile_position').condicao
        self.assertNotEqual(bool(avaliar(c.expressao().replace('false', 'true'), {'airmobile': None})),
                            c.avaliar({'airmobile': None}))

    def test_toda_coluna_no_formulario_ou_oculta_e_so_nativos(self):
        for t, s in specs().items():
            colunas = [c.coluna for c in s.campos()]
            self.assertEqual(len(colunas), len(set(colunas)), t)
            esquema = set(schema.nomes_campos(t))
            self.assertFalse(set(colunas) & set(s.ocultos), t)
            self.assertEqual(esquema - set(colunas) - set(s.ocultos), set(), t)
            self.assertEqual(set(colunas) - esquema, set(), t)
            for c in s.campos():
                self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, (t, c.coluna))
                self.assertIn(c.rico, (None, 'km_em_m', 'caixa_padrao', 'num'), (t, c.coluna))
        # pior caso: tirar symbol_instances dos ocultos deixa coluna sem lugar
        s = specs()['boundary']
        self.assertIn('symbol_instances', set(schema.nomes_campos('boundary')) - {c.coluna for c in s.campos()}
                      - (set(s.ocultos) - {'symbol_instances'}))

    def test_escaloes_do_dock_com_o_rotulo_do_web(self):
        from Calco.estilos_area import ESCALOES
        mapa = esp.formulario('boundary').campo('echelon').widget.config['map']
        self.assertEqual([list(d.values())[0] for d in mapa], ESCALOES)
        rot = {list(d.values())[0]: list(d)[0] for d in mapa}
        self.assertEqual((rot['Ø'], rot['++'], rot['ooo'], rot['o'], rot['XXXXX']), ('Ø', '++', '•••', '•', 'XXXXX'))

    def test_resumo_das_posicoes_le_como_o_estilo(self):
        from Calco.formulario.tipos.taticos import expressao_posicoes
        ex = expressao_posicoes()
        casos = [(INSTANCIAS, RESUMO_3), (json.dumps(INSTANCIAS), RESUMO_3), (None, '50 %'), ('[]', '50 %'),
                 ([{'ratio': 1.7}, {'ratio': None}, {'ratio': -1}], '99 %, 50 %, 1 %'), ('lixo', '50 %')]
        caminho = os.path.join(TMP, 'resumo.gpkg')
        gpkg.criar_calco(caminho, ['boundary'])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'boundary'), 'b', 'ogr')
        for valor, esperado in casos:
            f = QgsFeature(vl.fields())
            f['symbol_instances'] = valor
            ctx = QgsExpressionContext()
            ctx.setFeature(f)
            e = QgsExpression(ex)
            self.assertEqual(e.evaluate(ctx), esperado, valor)
            self.assertFalse(e.hasEvalError(), e.evalErrorString())
        # régua: a leitura só por from_json (o defeito de 2026-10-04) perde a lista do importador
        ruim = ex.replace(_IJ, 'try(from_json("symbol_instances"))')
        self.assertNotEqual(ruim, ex)
        f = QgsFeature(vl.fields())
        f['symbol_instances'] = INSTANCIAS
        ctx = QgsExpressionContext()
        ctx.setFeature(f)
        self.assertNotEqual(QgsExpression(ruim).evaluate(ctx), RESUMO_3)


_IJ = ('CASE WHEN try(array_length("symbol_instances"), -1) >= 0 THEN "symbol_instances" '
       'ELSE try(from_json("symbol_instances")) END')


# ---------------------------------------------------------------------------------------------
# Formulário nativo, sem o plugin
# ---------------------------------------------------------------------------------------------

SCRIPT = r'''
import sys, os, json, time
gp, saida, pasta = sys.argv[1:4]
capturas = sys.argv[4:]
res = {'etapa': 'inicio', 'camadas': {}}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
plugin = os.environ.get('EBGEO_PLUGIN')
if plugin:
    sys.path.insert(0, plugin)
from qgis.core import (QgsApplication, QgsVectorLayer, QgsMapSettings, QgsMapRendererSequentialJob,
                       QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject)
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
from qgis.PyQt.QtCore import QSize
QgsGui.editorWidgetRegistry().initEditors()
NOMES = {'boundary': 'Linha de Limite', 'arrow': 'Seta', 'occupied_front': 'Frente Ocupada'}

def desenhar(L):
    ms = QgsMapSettings()
    ms.setLayers([L])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(900, 420)); ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    ext = QgsCoordinateTransform(L.crs(), ms.destinationCrs(), QgsProject.instance()).transformBoundingBox(L.extent())
    ext.scale(1.4)
    ms.setExtent(ext)
    job = QgsMapRendererSequentialJob(ms); job.start(); job.waitForFinished()
    return job.renderedImage()

for tipo in ('boundary', 'arrow', 'occupied_front'):
    L = QgsVectorLayer(gp + '|layername=' + tipo, NOMES[tipo], 'ogr')
    if plugin:
        from Calco import guardiao
        guardiao.garantir(L, tipo)
    c = res['camadas'][tipo] = {}
    fc = L.editFormConfig()
    nomes = L.fields().names()
    res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
    c['layout'] = fc.layout().name
    c['init'] = fc.initCodeSource().name
    c['init_codigo'] = len(fc.initCode() or '') + len(fc.initFunction() or '')
    c['ui'] = fc.uiForm()
    c['acoes'] = len(L.actions().actions())
    c['widgets'] = {n: L.editorWidgetSetup(i).type() for i, n in enumerate(nomes)}
    c['aliases'] = {n: L.attributeAlias(i) for i, n in enumerate(nomes)}
    c['tabela_ocultas'] = sorted(x.name for x in L.attributeTableConfig().columns() if x.hidden and x.name)
    c['tipo_instancias'] = {}
    res['etapa'] = 'estatico ' + tipo
    gravar()
    L.startEditing()
    c['formularios'] = {}
    for f in L.getFeatures():
        chave = f['ebgeo_id']
        if 'symbol_instances' in nomes:
            c['tipo_instancias'][chave] = type(f['symbol_instances']).__name__
        res['etapa'] = 'montando ' + chave
        gravar()
        t = time.perf_counter()
        form = QgsAttributeForm(L, f)
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        ms = (time.perf_counter() - t) * 1000
        form.resize(470, 620)
        form.show(); app.processEvents()
        tabs = form.findChildren(QTabWidget)
        abas, vis, rotulos, travados, imgs = [], set(), set(), {}, []
        tw = tabs[0] if tabs else None
        indices = [k for k in range(tw.count()) if tw.isTabVisible(k)] if tw else [None]
        for k in indices:
            if tw is not None:
                tw.setCurrentIndex(k); app.processEvents()
                abas.append(tw.tabText(k))
            for g in form.findChildren(QGroupBox):
                b = g.findChild(QToolButton)
                if g.isVisibleTo(form) and b is not None and all(not w.isVisibleTo(form) for w in g.findChildren(QLabel)):
                    b.click(); app.processEvents()
            for wr in form.findChildren(QgsEditorWidgetWrapper):
                w = wr.widget()
                if w is not None and w.isVisibleTo(form):
                    n = L.fields().at(wr.fieldIdx()).name()
                    vis.add(n)
                    ro = getattr(w, 'isReadOnly', None)
                    travados[n] = (not w.isEnabled()) or bool(ro() if ro else False)
            rotulos |= {lb.text() for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text()}
            if pasta and chave in capturas:
                imgs.append(form.grab().toImage())
        salvo = form.save()
        mudou = {str(k): sorted(L.fields().at(i).name() for i in v) for k, v in L.editBuffer().changedAttributeValues().items()}
        c['formularios'][chave] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
                                   'travados': travados, 'salvo': salvo, 'mudou_ao_salvar': mudou}
        if imgs:
            W = sum(im.width() for im in imgs) + 8 * (len(imgs) - 1)
            H = max(im.height() for im in imgs) + 26
            out = QImage(W, H, QImage.Format.Format_ARGB32); out.fill(QColor('white'))
            p = QPainter(out); x = 0
            p.setFont(QFont('Segoe UI', 10))
            p.drawText(4, 17, '{}: formulário nativo {} o plugin, uma imagem por aba visível; montado em {:.0f} ms'.format(
                f['nome'], 'COM' if plugin else 'SEM', ms))
            for im in imgs:
                p.drawImage(x, 26, im); x += im.width() + 8
            p.end()
            out.save(os.path.join(pasta, 'nativo_{}_{}.png'.format(chave, 'com_plugin' if plugin else 'sem_plugin')))
        form.close(); form.deleteLater(); app.processEvents()
    L.rollBack()
    # editar o nome pelo formulário e salvar: o desenho e as outras colunas não podem mudar
    res['etapa'] = 'editando ' + tipo
    gravar()
    antes_img = desenhar(L)
    antes = {f['ebgeo_id']: {n: repr(f[n]) for n in nomes} for f in L.getFeatures()}
    L.startEditing()
    salvos = 0
    for f in L.getFeatures():
        if f['bloqueado']:
            continue
        form = QgsAttributeForm(L, f)
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        for wr in form.findChildren(QgsEditorWidgetWrapper):
            if L.fields().at(wr.fieldIdx()).name() == 'nome':
                wr.setValues(f['nome'] + ' (editado)', []); wr.emitValueChanged()
        salvos += bool(form.save())
        form.deleteLater()
    commit = L.commitChanges()
    L2 = QgsVectorLayer(gp + '|layername=' + tipo, NOMES[tipo], 'ogr')
    depois_img = desenhar(L2)
    dif = []
    editados = 0
    for f in L2.getFeatures():
        a = antes.get(f['ebgeo_id'], {})
        editados += str(f['nome']).endswith(' (editado)')
        for n in nomes:
            if n not in ('nome', 'atualizado_em') and repr(f[n]) != a.get(n):
                dif.append([f['ebgeo_id'], n, a.get(n), repr(f[n])])
    pix = sum(1 for y in range(0, antes_img.height(), 2) for x in range(0, antes_img.width(), 2)
              if antes_img.pixel(x, y) != depois_img.pixel(x, y))
    tinta = sum(1 for y in range(0, antes_img.height(), 2) for x in range(0, antes_img.width(), 2)
                if antes_img.pixel(x, y) != QColor('white').rgb())
    c['edicao'] = {'salvos': salvos, 'editados': editados, 'commit': commit, 'pixels_diferentes': pix,
                   'pixels_desenhados': tinta, 'colunas_diferentes': dif}
    if pasta:
        antes_img.save(os.path.join(pasta, 'desenho_{}_antes_{}.png'.format(tipo, 'com_plugin' if plugin else 'sem_plugin')))
        depois_img.save(os.path.join(pasta, 'desenho_{}_depois_{}.png'.format(tipo, 'com_plugin' if plugin else 'sem_plugin')))
res['etapa'] = 'fim'
gravar()
'''


def _exe():
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    return exe if os.path.exists(exe) else sys.executable


def copiar_gpkg(origem, destino):
    """
    Cópia do GeoPackage COM o diário WAL: enquanto uma camada o tem aberto, o estilo recém-gravado
    ainda está no -wal, e a cópia só do arquivo principal abre sem ele (medido: formulário
    autogerado na cópia).
    """
    shutil.copy(origem, destino)
    for ext in ('-wal', '-shm'):
        if os.path.exists(origem + ext):
            shutil.copy(origem + ext, destino + ext)


def rodar(caminho, capturas=(), pasta='', com_plugin=False, timeout=180):
    """Roda o SCRIPT num processo novo, sobre uma CÓPIA do calco (o script grava)."""
    copia = os.path.join(TMP, 'rodada_{}.gpkg'.format(uuid.uuid4().hex[:8]))
    copiar_gpkg(caminho, copia)
    script = os.path.join(TMP, 'taticos_sem_plugin.py')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(SCRIPT)
    saida = os.path.join(TMP, 'res_{}.json'.format(uuid.uuid4().hex[:8]))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if com_plugin:
        env['EBGEO_PLUGIN'] = PLUGIN
    else:
        env.pop('EBGEO_PLUGIN', None)
    args = [_exe(), script, copia, saida, pasta] + list(capturas)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=TMP,
                         shell=args[0].endswith('.bat'))
    try:
        p.communicate(timeout=timeout)
        codigo = p.returncode
    except subprocess.TimeoutExpired:
        # preso (no diálogo de confiança): encerra a árvore do processo que ESTE teste abriu
        if os.name == 'nt':
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
        else:
            p.kill()
        p.communicate()
        codigo = 'tempo esgotado'
    res = {}
    if os.path.exists(saida):
        with open(saida, encoding='utf-8') as fh:
            res = json.load(fh)
    return res, codigo


def reprovacoes(res, codigo, sp):
    """Tudo o que reprova o formulário lido no processo novo; lista vazia é aprovação."""
    erros = []
    if codigo != 0:
        erros.append('processo saiu com {} na etapa {}'.format(codigo, res.get('etapa')))
    if not res:
        return erros + ['sem resultado']
    if res.get('etapa') != 'fim':
        erros.append('parou na etapa {}'.format(res.get('etapa')))
    proprias = [c for c, _a, _v in ATTR]
    for tipo in TIPOS:
        c = (res.get('camadas') or {}).get(tipo)
        if not c:
            erros.append('{}: camada não lida'.format(tipo))
            continue
        s = sp[tipo]
        if c.get('layout') != 'DragAndDrop':
            erros.append('{}: layout {}'.format(tipo, c.get('layout')))
        if c.get('init') != 'NoSource' or c.get('init_codigo') or c.get('ui') or c.get('acoes'):
            erros.append('{}: formulário com código: init {} ({} caracteres), ui {!r}, {} ações'.format(
                tipo, c.get('init'), c.get('init_codigo'), c.get('ui'), c.get('acoes')))
        for col, w in (c.get('widgets') or {}).items():
            if w not in esp.WIDGETS_NATIVOS:
                erros.append('{}: widget não nativo em {}: {}'.format(tipo, col, w))
        for campo in s.campos():
            if (c.get('aliases') or {}).get(campo.coluna) != campo.rotulo:
                erros.append('{}: alias de {}: {!r}'.format(tipo, campo.coluna, (c.get('aliases') or {}).get(campo.coluna)))
        if set(c.get('tabela_ocultas') or []) != set(s.ocultos):
            erros.append('{}: ocultas na tabela: {}'.format(tipo, c.get('tabela_ocultas')))
        forms = c.get('formularios') or {}
        so_leitura = {x.coluna for x in s.campos() if x.somente_leitura}
        for eid in FEICOES[tipo]:
            if eid not in forms:
                erros.append('{}: formulário não montado'.format(eid))
                continue
            fo = forms[eid]
            attrs = atributos(tipo, eid)
            vis = {x.coluna for x in s.campos() if s.visivel(x.coluna, attrs)} | set(proprias)
            if set(fo['visiveis']) != vis:
                erros.append('{}: visíveis a mais {} a menos {}'.format(
                    eid, sorted(set(fo['visiveis']) - vis), sorted(vis - set(fo['visiveis']))))
            faltam_retrato = esperado_retrato(tipo, attrs) - set(fo['visiveis']) - {'symbol_instances'}
            if faltam_retrato:
                erros.append('{}: some o que o dock de antes mostrava: {}'.format(eid, sorted(faltam_retrato)))
            rotulos = {x.rotulo_para(attrs) for x in s.campos() if x.coluna in vis}
            if not rotulos <= set(fo['rotulos']):
                erros.append('{}: rótulos ausentes {}'.format(eid, sorted(rotulos - set(fo['rotulos']))))
            travada = bool(attrs.get('bloqueado'))
            if (esp.AVISO_BLOQUEADA in fo['rotulos']) != travada:
                erros.append('{}: aviso de bloqueio errado'.format(eid))
            for col, trav in fo['travados'].items():
                if trav != (travada or col in so_leitura):
                    erros.append('{}: {} {}'.format(eid, col, 'travado' if trav else 'editável'))
            if tipo == 'boundary':
                resumo = resumo_esperado(attrs.get('symbol_instances'))
                achados = [r for r in fo['rotulos'] if r.startswith('Posições do símbolo ao longo da linha')]
                if len(achados) != 1 or ': {} do comprimento'.format(resumo) not in achados[0]:
                    erros.append('{}: resumo das posições {}'.format(eid, achados))
            if not fo['salvo'] or fo['mudou_ao_salvar']:
                erros.append('{}: salvar sem mudar gravou {}'.format(eid, fo['mudou_ao_salvar']))
        ed = c.get('edicao') or {}
        livres = len([e for e in FEICOES[tipo] if not FEICOES[tipo][e].get('bloqueado')])
        if (ed.get('salvos'), ed.get('editados'), ed.get('commit')) != (livres, livres, True):
            erros.append('{}: edição pelo formulário {}'.format(tipo, ed))
        if ed.get('pixels_diferentes') != 0 or not ed.get('pixels_desenhados'):
            erros.append('{}: desenho mudou ao salvar ({} pixels diferentes de {} desenhados)'.format(
                tipo, ed.get('pixels_diferentes'), ed.get('pixels_desenhados')))
        if ed.get('colunas_diferentes'):
            erros.append('{}: colunas mudaram ao salvar {}'.format(tipo, ed.get('colunas_diferentes')))
    return erros


def criar_calco(caminho):
    """Um calco com as feições de FEICOES nos três tipos, e duas attr_ em cada tabela."""
    gpkg.criar_calco(caminho, list(TIPOS))
    from osgeo import ogr
    ds = ogr.Open(caminho, 1)
    for tipo in TIPOS:
        lo = ds.GetLayerByName(tipo)
        for col, alias, _v in ATTR:
            fd = ogr.FieldDefn(col, ogr.OFTString)
            fd.SetAlternativeName(alias)
            lo.CreateField(fd)
    ds = None
    camadas = {}
    for tipo in TIPOS:
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
        idx = vl.fields().indexOf
        vl.startEditing()
        for eid in FEICOES[tipo]:
            a = atributos(tipo, eid)
            a.update(created_zoom=12.0, criado_em='2026-10-05T09:00:00+00:00', atualizado_em='2026-10-05T09:00:00+00:00')
            for col, _alias, v in ATTR:
                a[col] = v
            f = QgsFeature(vl.fields())
            for k, v in a.items():
                if idx(k) < 0:
                    continue
                # a lista vai como objeto (JSON de verdade); o texto, como veio (volta como texto)
                f.setAttribute(idx(k), v)
            f.setGeometry(QgsGeometry.fromWkt(GEOMETRIA[tipo]))
            vl.addFeature(f)
        assert vl.commitChanges(), vl.commitErrors()
        camadas[tipo] = vl
    return camadas


def _degradar(nome, tipo, alterar):
    """Cópia do calco real com o estilo salvo do tipo degradado por `alterar(camada)`."""
    destino = os.path.join(TMP, 'pior_{}.gpkg'.format(nome))
    copiar_gpkg(TesteNativo.caminho, destino)
    vl = QgsVectorLayer(gpkg.uri_camada(destino, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
    alterar(vl)
    vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
    return destino


class TesteNativo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sp = specs()
        cls.caminho = os.path.join(TMP, 'calco_taticos.gpkg')
        for tipo, vl in criar_calco(cls.caminho).items():
            C.aplicar_estilo(vl, tipo)
            C.salvar_estilo_padrao(vl)
        cls.res, cls.codigo = rodar(cls.caminho, CAPTURAS, SAIDA)
        cls.res_com, cls.codigo_com = rodar(cls.caminho, CAPTURAS, SAIDA, com_plugin=True)

    def test_sem_plugin_confere(self):
        erros = reprovacoes(self.res, self.codigo, self.sp)
        self.assertEqual(erros, [], '\n'.join(erros))
        self.assertFalse(self.res.get('modulos_ebgeo'))
        tipos = self.res['camadas']['boundary']['tipo_instancias']
        MEDIDAS.append('posições do Limite lidas como {}'.format(tipos))
        # os dois formatos da coluna JSON exercitados
        self.assertEqual((tipos['limite_3'], tipos['limite_texto']), ('list', 'str'))
        forms = {e: fo for c in self.res['camadas'].values() for e, fo in c['formularios'].items()}
        ms = sorted(fo['ms'] for fo in forms.values())
        MEDIDAS.append('sem o plugin: {} formulários, {:.0f} a {:.0f} ms; abas do Limite {}, da Seta {}, da Frente {}'.format(
            len(ms), ms[0], ms[-1], forms['limite_3']['abas'], forms['seta_padrao']['abas'], forms['frente']['abas']))
        for t in TIPOS:
            ed = self.res['camadas'][t]['edicao']
            MEDIDAS.append('{}: nome editado em {} feições pelo formulário, {} pixels desenhados, {} diferentes'.format(
                t, ed['editados'], ed['pixels_desenhados'], ed['pixels_diferentes']))
        self.assertEqual(forms['limite_3']['abas'], ['Símbolo', 'Rótulos', 'Aparência', 'Atributos', 'Avançado'])
        self.assertEqual(forms['seta_padrao']['abas'], ['Seta', 'Aparência', 'Atributos', 'Avançado'])
        self.assertEqual(forms['frente']['abas'], ['Aparência', 'Atributos', 'Avançado'])
        self.assertIn('Capacidade', forms['frente']['rotulos'])

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(reprovacoes(self.res_com, self.codigo_com, self.sp), [])
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        from qgis.PyQt.QtGui import QImage
        for t in TIPOS:
            for eid, fo in self.res['camadas'][t]['formularios'].items():
                com = self.res_com['camadas'][t]['formularios'][eid]
                self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos']), (com['abas'], com['visiveis'], com['rotulos']), eid)
        iguais = 0
        for chave in CAPTURAS:
            a = QImage(os.path.join(SAIDA, 'nativo_{}_sem_plugin.png'.format(chave)))
            b = QImage(os.path.join(SAIDA, 'nativo_{}_com_plugin.png'.format(chave)))
            self.assertFalse(a.isNull() or b.isNull(), chave)
            dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                      if a.pixel(x, y) != b.pixel(x, y))
            iguais += dif == 0
        MEDIDAS.append('capturas com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, len(CAPTURAS)))
        self.assertEqual(iguais, len(CAPTURAS))

    def test_pior_caso_widget_do_plugin_reprova(self):
        def injeta(vl):
            vl.setEditorWidgetSetup(vl.fields().indexOf('text_top'), QgsEditorWidgetSetup('EBGeoSidc', {}))
        res, codigo = rodar(_degradar('widget', 'boundary', injeta), timeout=90)
        erros = reprovacoes(res, codigo, self.sp)
        MEDIDAS.append('pior caso, widget do plugin no Limite: saída {}, etapa "{}", {} reprovações'.format(
            codigo, res.get('etapa'), len(erros)))
        self.assertTrue(any('widget não nativo em text_top' in e for e in erros), erros)

    def test_pior_caso_condicao_apagada_reprova(self):
        def apaga(vl):
            from qgis.core import QgsOptionalExpression
            fc = vl.editFormConfig()

            def andar(cont):
                for el in cont.children():
                    if hasattr(el, 'children') and hasattr(el, 'visibilityExpression'):
                        if 'airmobile' in el.visibilityExpression().data().expression():
                            el.setVisibilityExpression(QgsOptionalExpression())
                        andar(el)
            andar(fc.invisibleRootContainer())
            vl.setEditFormConfig(fc)
        res, codigo = rodar(_degradar('condicao', 'arrow', apaga))
        erros = reprovacoes(res, codigo, self.sp)
        self.assertTrue(any(e.startswith('seta_padrao: visíveis a mais [\'airmobile_position\']') for e in erros), erros)

    def test_pior_caso_resumo_que_perde_a_lista_reprova(self):
        trocas = []

        def degrada(vl):
            # o elemento de texto volta do Python sem o tipo próprio (sem text()): a troca vai no
            # nó dele no QML, e só nele (o desenho, que lê a mesma lista, fica como está)
            from qgis.core import QgsReadWriteContext
            from qgis.PyQt.QtXml import QDomDocument
            doc = QDomDocument()
            vl.exportNamedStyle(doc, QgsReadWriteContext())
            nos = doc.elementsByTagName('attributeEditorTextElement')
            for k in range(nos.count()):
                el = nos.at(k).toElement()
                filho = el.firstChild()
                while not filho.isNull():
                    if filho.isText() and _IJ in filho.nodeValue():
                        filho.setNodeValue(filho.nodeValue().replace(_IJ, 'try(from_json("symbol_instances"))'))
                        trocas.append(el.attribute('name'))
                    filho = filho.nextSibling()
            vl.importNamedStyle(doc)
        res, codigo = rodar(_degradar('resumo', 'boundary', degrada))
        self.assertEqual(trocas, ['posicoes_limite'])
        erros = reprovacoes(res, codigo, self.sp)
        # a lista do importador cai na instância padrão; o texto JSON continua certo
        self.assertTrue(any(e.startswith('limite_3: resumo das posições') for e in erros), erros)
        self.assertFalse(any(e.startswith('limite_texto: resumo') for e in erros), erros)

    def test_pior_caso_caixa_que_perde_o_nulo_reprova(self):
        def degrada(vl):
            # a caixa nativa comum, sem o estado nulo: a seta de ponta nula perde a ponta ao salvar
            i = vl.fields().indexOf('show_arrow_head')
            cfg = dict(vl.editorWidgetSetup(i).config())
            cfg['AllowNullState'] = False
            vl.setEditorWidgetSetup(i, QgsEditorWidgetSetup('CheckBox', cfg))
        res, codigo = rodar(_degradar('caixa', 'arrow', degrada))
        erros = reprovacoes(res, codigo, self.sp)
        ed = res['camadas']['arrow']['edicao']
        MEDIDAS.append('pior caso, caixa sem o nulo na Seta: {} pixels diferentes, colunas {}'.format(
            ed['pixels_diferentes'], ed['colunas_diferentes']))
        self.assertTrue(any(e.startswith('arrow: desenho mudou') for e in erros), erros)
        self.assertIn(['seta_nula', 'show_arrow_head', 'None', 'False'], ed['colunas_diferentes'])

    def test_pior_caso_mostrar_no_mapa_sem_nulo_reprova(self):
        def degrada(vl):
            # a caixa comum do cabeçalho: a frente de visível nulo some do mapa ao salvar o nome
            i = vl.fields().indexOf('visivel')
            cfg = dict(vl.editorWidgetSetup(i).config())
            cfg['AllowNullState'] = False
            vl.setEditorWidgetSetup(i, QgsEditorWidgetSetup('CheckBox', cfg))
        res, codigo = rodar(_degradar('visivel', 'occupied_front', degrada))
        erros = reprovacoes(res, codigo, self.sp)
        ed = res['camadas']['occupied_front']['edicao']
        MEDIDAS.append('pior caso, Mostrar no mapa sem o nulo: {} pixels diferentes, colunas {}'.format(
            ed['pixels_diferentes'], ed['colunas_diferentes']))
        self.assertIn(['frente_nula', 'visivel', 'None', 'False'], ed['colunas_diferentes'])
        self.assertTrue(any(e.startswith('occupied_front: desenho mudou') for e in erros), erros)

    def test_pior_caso_caixa_numerica_que_corta_reprova(self):
        def degrada(vl):
            # a largura da Seta na caixa numérica comum (sem nulo, sem casas): o desenho de antes da correção
            vl.setEditorWidgetSetup(vl.fields().indexOf('width_m'), QgsEditorWidgetSetup('Range', {
                'Style': 'SpinBox', 'Min': 10, 'Max': 10000, 'Step': 10, 'Precision': 0, 'Suffix': ' m', 'AllowNull': False}))
        res, codigo = rodar(_degradar('numero', 'arrow', degrada))
        erros = reprovacoes(res, codigo, self.sp)
        ed = res['camadas']['arrow']['edicao']
        MEDIDAS.append('pior caso, largura da Seta em caixa numérica: {} pixels diferentes, colunas {}'.format(
            ed['pixels_diferentes'], ed['colunas_diferentes']))
        self.assertIn(['seta_web', 'width_m', '1234.5678', '1235.0'], ed['colunas_diferentes'])
        self.assertIn(['seta_nulos', 'width_m', 'None', '10.0'], ed['colunas_diferentes'])
        self.assertTrue(any(e.startswith('arrow: desenho mudou') for e in erros), erros)

    def test_pior_caso_formulario_que_regrava_coluna_desenhada_reprova(self):
        def degrada(vl):
            # o formulário que, ao salvar, regrava uma coluna do desenho (padrão aplicado na atualização)
            vl.setDefaultValueDefinition(vl.fields().indexOf('line_width'), QgsDefaultValue('9', True))
        res, codigo = rodar(_degradar('regrava', 'occupied_front', degrada))
        erros = reprovacoes(res, codigo, self.sp)
        ed = res['camadas']['occupied_front']['edicao']
        MEDIDAS.append('pior caso, formulário que regrava a espessura: {} pixels diferentes'.format(ed['pixels_diferentes']))
        self.assertTrue(any(e.startswith('occupied_front: desenho mudou') for e in erros), erros)
        self.assertTrue(any(e.startswith('occupied_front: colunas mudaram') for e in erros), erros)


# ---------------------------------------------------------------------------------------------
# Dock e guardião
# ---------------------------------------------------------------------------------------------

class TesteDock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_dock_taticos.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar()
        definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())
        cls.painel.setParent(None)
        cls.painel.resize(440, 1000)
        cls.painel.show()
        cls.sp = specs()

    def _nova(self, tipo, eid):
        from Calco.ferramentas import gravar_feicao
        lyr = self.calco.camada(tipo)
        a = atributos(tipo, eid)
        a['ebgeo_id'] = '{}_{}'.format(eid, uuid.uuid4().hex[:6])
        a['created_zoom'] = 12.0
        gravar_feicao(lyr, tipo, QgsGeometry.fromWkt(GEOMETRIA[tipo]), a)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, a['ebgeo_id'])
        self.painel._selecao_mudou()
        _app.processEvents()
        return lyr, a['ebgeo_id']

    def _disco(self, tipo, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, tipo), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _botoes(self):
        itens = [self.painel.acoes.itemAt(i).widget() for i in range(self.painel.acoes.count())]
        return [w.text() for w in itens if w is not None]

    def _capturar(self, nome):
        self.painel.show()
        _app.processEvents()
        from Calco.ui.blocos.previa import esperar
        esperar(self.painel)  # a amostra do estilo desenha fora da interface
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def tearDown(self):
        for t in TIPOS:
            lyr = self.calco.camada(t)
            if lyr is not None and lyr.isEditable():
                lyr.rollBack()
        _app.processEvents()

    def test_campos_conforme_a_especificacao_e_o_retrato(self):
        for tipo in TIPOS:
            for eid in FEICOES[tipo]:
                if eid in ('limite_bloqueada',):
                    continue
                self._nova(tipo, eid)
                vis = self.painel.campos_visiveis()
                attrs = atributos(tipo, eid)
                spec_vis = {c.coluna for c in self.sp[tipo].campos() if self.sp[tipo].visivel(c.coluna, attrs)}
                if tipo == 'boundary':
                    spec_vis.add('symbol_instances')
                self.assertEqual(vis, spec_vis, eid)
                self.assertTrue(esperado_retrato(tipo, attrs) <= vis, (eid, esperado_retrato(tipo, attrs) - vis))
                for col in RETRATO_DOCK[tipo] - vis:
                    self.assertTrue(self.painel.widgets[col].isHidden(), (eid, col))
                self.assertEqual(self._botoes(), BOTOES_DOCK[tipo], eid)
                self.assertTrue(self.painel.barra_edicao.isVisibleTo(self.painel))

    def test_posicoes_no_buffer_salvar_e_o_estilo_le(self):
        lyr, eid = self._nova('boundary', 'limite_nulo')
        lyr_f = lambda: lyr.getFeature(self.painel.fid)  # noqa: E731
        ed = self.painel.widgets['symbol_instances']
        self.assertEqual(len(ed.posicoes), 1)
        ed.repeticoes.setValue(3)
        self.painel._gravar_pendentes()
        _app.processEvents()
        self.assertEqual(len(ed.posicoes), 3)
        lista, legivel = regras.ler_instancias_limite(lyr_f()['symbol_instances'])
        self.assertTrue(legivel)
        self.assertEqual([i['ratio'] for i in lista], [0.25, 0.5, 0.75])
        self.assertIsNone(regras.valor(self._disco('boundary', eid)['symbol_instances']))  # nada no disco
        ed.posicoes[2].setValue(80)
        ed.rotulos[1].setChecked(False)
        self.painel._gravar_pendentes()
        self._capturar('dock_limite_3_nao_salvo.png')
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        d = self._disco('boundary', eid)
        self.assertEqual(regras.ler_instancias_limite(d['symbol_instances'])[0], INSTANCIAS)
        self.assertIsInstance(d['symbol_instances'], list)  # gravado como JSON de verdade
        # o estilo lê a lista gravada: rótulos só nos dois símbolos de rótulo ligado
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'boundary'), 'r', 'ogr')
        f = next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
        f['text_top'] = 'ALFA'
        f['text_north_facing'] = True
        pts = avaliar_no_mapa(et.expr_limite_rotulo('top', True)['geometria'], vl, f)
        self.assertEqual(pts.constGet().numGeometries(), 2)
        self.assertFalse(lyr.isEditable())
        self.painel._selecao_mudou()
        _app.processEvents()
        self._capturar('dock_limite_3_salvo.png')
        # remover o primeiro símbolo
        ed = self.painel.widgets['symbol_instances']
        ed.remover[0].click()
        _app.processEvents()
        self.painel._gravar_pendentes()
        _app.processEvents()
        self.assertEqual([i['ratio'] for i in regras.ler_instancias_limite(lyr_f()['symbol_instances'])[0]], [0.5, 0.8])
        self.assertEqual(len(self.painel.widgets['symbol_instances'].posicoes), 2)
        # Descartar volta à lista salva
        self.assertTrue(self.painel.descartar())
        _app.processEvents()
        self.assertEqual(regras.ler_instancias_limite(lyr.getFeature(self.painel.fid)['symbol_instances'])[0], INSTANCIAS)

    def test_bloqueada_so_leitura(self):
        from qgis.PyQt.QtWidgets import QLabel, QPushButton
        self._nova('boundary', 'limite_bloqueada')
        textos = [lb.text() for lb in self.painel.form_host.findChildren(QLabel) if lb.isVisibleTo(self.painel.form_host)]
        self.assertIn(esp.AVISO_BLOQUEADA, textos)
        self.assertFalse(self.painel.widgets['symbol_instances'].isEnabled())
        for col in ('echelon', 'text_top', 'color'):
            self.assertFalse(self.painel.widgets[col].isEnabled(), col)
        inv = [b for b in self.painel.findChildren(QPushButton) if b.text() == 'Inverter sentido' and not b.isHidden()]
        self.assertTrue(inv and not inv[0].isEnabled())
        self._capturar('dock_limite_bloqueado.png')

    def test_caixa_nula_mostra_o_padrao_do_estilo(self):
        lyr, eid = self._nova('arrow', 'seta_nula')
        self.assertTrue(self.painel.widgets['show_arrow_head'].isChecked())   # o estilo desenha a ponta
        self.assertFalse(self.painel.widgets['airmobile'].isChecked())
        self.assertIn('double_headed', self.painel.campos_visiveis())
        self.painel._gravar_pendentes()
        self.assertFalse(lyr.isEditable())   # mostrar não grava
        self.painel.widgets['show_arrow_head'].setChecked(False)
        self.painel._gravar_pendentes()
        self.assertEqual(lyr.getFeature(self.painel.fid)['show_arrow_head'], False)
        self.assertNotIn('double_headed', self.painel.campos_visiveis())
        self.assertTrue(self.painel.descartar())

    def test_seta_variantes_e_inverter(self):
        lyr, eid = self._nova('arrow', 'seta_padrao')
        self.assertNotIn('airmobile_position', self.painel.campos_visiveis())
        self.painel.widgets['airmobile'].setChecked(True)
        self.painel._gravar_pendentes()
        self.assertIn('airmobile_position', self.painel.campos_visiveis())
        self.painel.widgets['show_arrow_head'].setChecked(False)
        self.painel._gravar_pendentes()
        vis = self.painel.campos_visiveis()
        self.assertFalse({'double_headed', 'head_length_ratio'} & vis)
        self.assertTrue(lyr.isEditable())
        self.assertEqual(self._disco('arrow', eid)['airmobile'], False)
        # a geometria fica numa variável: o iterador de vértices de uma geometria temporária de
        # várias partes não termina (medido no QGIS 4.0.0: a lista cresceu até 6,8 GB)
        g = lyr.getFeature(self.painel.fid).geometry()
        antes = [p.x() for p in g.vertices()]
        self.painel._inverter()
        g = lyr.getFeature(self.painel.fid).geometry()
        depois = [p.x() for p in g.vertices()]
        self.assertEqual(depois, list(reversed(antes)))
        self.assertTrue(self.painel.descartar())

    def test_capturas(self):
        self._nova('boundary', 'limite_3')
        self._capturar('dock_limite_3.png')
        self._nova('arrow', 'seta_aeromovel_dupla')
        self._capturar('dock_seta_aeromovel_dupla.png')
        self._nova('arrow', 'seta_sem_ponta')
        self._capturar('dock_seta_sem_ponta.png')
        self._nova('occupied_front', 'frente')
        self._capturar('dock_frente.png')


class TesteGuardiao(unittest.TestCase):
    def _camada(self, nome, tipo, eids):
        caminho = os.path.join(TMP, 'guardiao_{}.gpkg'.format(nome))
        gpkg.criar_calco(caminho, [tipo])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), 'g', 'ogr')
        vl.startEditing()
        for eid in eids:
            f = QgsFeature(vl.fields())
            for k, v in atributos(tipo, eid).items():
                if vl.fields().indexOf(k) >= 0:
                    f[k] = v
            f.setGeometry(QgsGeometry.fromWkt(GEOMETRIA[tipo]))
            vl.addFeature(f)
        assert vl.commitChanges()
        C.aplicar_estilo(vl, tipo)
        return vl

    def _calculadora(self, vl, fid, col, valor):
        vl.beginEditCommand('Calculadora de campo')
        vl.changeAttributeValue(fid, vl.fields().indexOf(col), valor)
        vl.endEditCommand()

    def test_regras_puras(self):
        self.assertEqual(regras.ler_instancias_limite(INSTANCIAS), (INSTANCIAS, True))
        self.assertEqual(regras.ler_instancias_limite(json.dumps(INSTANCIAS)), (INSTANCIAS, True))
        self.assertEqual(regras.ler_instancias_limite(None), ([{'ratio': 0.5, 'showLabels': True}], True))
        self.assertEqual(regras.ler_instancias_limite('lixo')[1], False)
        self.assertEqual(regras.ler_instancias_limite('{"ratio": 0.3}')[1], False)
        self.assertEqual(regras.ler_instancias_limite([{'ratio': 3}, 5])[0], [{'ratio': 0.99, 'showLabels': True}])
        self.assertEqual([i['ratio'] for i in regras.redistribuir_instancias(INSTANCIAS, 4)], [0.2, 0.4, 0.6, 0.8])
        self.assertEqual([i['showLabels'] for i in regras.redistribuir_instancias(INSTANCIAS, 2)], [True, False])
        self.assertEqual(regras.ao_mudar('boundary', {'symbol_instances': INSTANCIAS}, {'symbol_instances': 'lixo'}),
                         {'symbol_instances': INSTANCIAS})
        self.assertEqual(regras.ao_mudar('boundary', {'symbol_instances': INSTANCIAS}, {'symbol_instances': '[{"ratio": 0.3}]'}), {})
        self.assertTrue({'boundary', 'arrow', 'occupied_front'} <= regras.TIPOS_COM_REGRAS)

    def test_posicoes_ilegiveis_voltam(self):
        from Calco import guardiao
        vl = self._camada('lixo', 'boundary', ['limite_3'])
        g = guardiao.garantir(vl, 'boundary')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        self._calculadora(vl, fid, 'symbol_instances', 'lixo')
        self.assertEqual(regras.ler_instancias_limite(vl.getFeature(fid)['symbol_instances']), (INSTANCIAS, True))
        self.assertEqual(g.aplicadas, 1)
        self._calculadora(vl, fid, 'symbol_instances', [{'ratio': 0.3, 'showLabels': True}])
        self.assertEqual(regras.ler_instancias_limite(vl.getFeature(fid)['symbol_instances'])[0], [{'ratio': 0.3, 'showLabels': True}])
        vl.rollBack()

    def test_pior_caso_sem_guardiao_o_lixo_fica(self):
        vl = self._camada('lixo_sem', 'boundary', ['limite_3'])
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        self._calculadora(vl, fid, 'symbol_instances', 'lixo')
        self.assertFalse(regras.ler_instancias_limite(vl.getFeature(fid)['symbol_instances'])[1])  # a régua acima reprova
        vl.rollBack()

    def test_seta_bloqueada_nao_se_edita(self):
        from Calco import guardiao
        FEICOES['arrow']['seta_bloq'] = dict(nome='Seta bloqueada', bloqueado=True, width_m=500)
        try:
            vl = self._camada('seta_bloq', 'arrow', ['seta_bloq'])
            g = guardiao.garantir(vl, 'arrow')
            fid = next(vl.getFeatures()).id()
            vl.startEditing()
            self._calculadora(vl, fid, 'width_m', 2000.0)
            self.assertEqual(vl.getFeature(fid)['width_m'], 500.0)
            self.assertEqual(g.revertidas, 1)
            vl.rollBack()
            # pior caso: sem o guardião a largura muda
            vl2 = self._camada('seta_bloq_sem', 'arrow', ['seta_bloq'])
            fid = next(vl2.getFeatures()).id()
            vl2.startEditing()
            self._calculadora(vl2, fid, 'width_m', 2000.0)
            self.assertEqual(vl2.getFeature(fid)['width_m'], 2000.0)
            vl2.rollBack()
        finally:
            FEICOES['arrow'].pop('seta_bloq', None)


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
