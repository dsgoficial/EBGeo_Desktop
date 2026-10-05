# -*- coding: utf-8 -*-
"""
Formulário da Medida de Coordenação (formulario/tipos/medida.py, ui/blocos/medida.py e a regra
de troca em regras.py), nos 132 códigos do catálogo e nos casos de borda:

  - a especificação mostra, para cada código, os campos que o dock de antes mostrava
    (RETRATO_DOCK, medido no dock de 86f7d3b em 2026-10-05) nos campos que ele já filtrava
    (minas, direção da Base de fogos, par do Setor de Tiro, escalão só nas famílias), e os
    textos e a Situação só onde o catálogo do Web os lista (o dock de antes os mostrava em todos);
  - a expressão QGIS de cada condição e do rótulo da rotação dá o mesmo que a regra em Python;
  - o formulário nativo aberto num processo NOVO e SEM o plugin confere com a especificação em
    todas as feições (uma por código), salva sem mudar nada, e é o mesmo com o plugin;
  - o dock mostra os mesmos campos que a especificação nos 132 códigos, busca a medida pelo
    nome sem acento e edita no buffer, com Salvar;
  - o guardião aplica ao trocar a medida, em qualquer caminho, o escalão da família, a cor
    padrão do tipo e a limpeza das minas e da seta secundária;
  - os campos que mudam o desenho estão na assinatura que o regenerador do SVG vigia.
Cada régua é provada contra a saída real degradada, que ela tem de reprovar.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_medida.py
Variáveis: EBGEO_TESTE_SAIDA (pasta das capturas; padrão: temporária). Com
QT_QPA_PLATFORM=offscreen, o texto das capturas só sai legível com QT_QPA_FONTDIR apontando a
pasta de fontes do sistema.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, PLUGIN)
sys.path.insert(0, AQUI)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsEditorWidgetSetup, QgsExpression, QgsExpressionContext, QgsFeature, QgsField,
    QgsFields, QgsGeometry, QgsPointXY, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import calco as C, gpkg, schema, simbolos, regras  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402

TIPO = 'coordination_measure'
TMP = tempfile.mkdtemp(prefix='ebgeo_medida_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []

with open(os.path.join(PLUGIN, 'Calco', 'motor', 'catalogos.json'), encoding='utf-8') as _fh:
    CATALOGO = json.load(_fh)['medida']
POR_CODIGO = CATALOGO['porCodigo']
WEB_COLUNA = {w: c for w, c in schema.mapa_web(TIPO).items()}
VERDE = '#00b04e'


def _tela(chave):
    """O código de tela com que o Web grava a chave de família (ECHELON_FT_16 -> ECHELON_FT)."""
    for fam in CATALOGO['familias'].values():
        for prefixo, tela in ((fam['prefixoFT'], fam['telaFT']), (fam['prefixo'], fam['tela'])):
            if chave.startswith(prefixo + '_') and chave[len(prefixo) + 1:] in CATALOGO['escaloes']:
                return tela
    return None


# Uma feição por código do catálogo, gravada como o Web grava (a família em código de tela mais a
# chave no escalão), e os casos de borda. caso -> (point_code, echelon_code, chave que desenha).
CASOS = {}
for _k in POR_CODIGO:
    CASOS[_k] = (_tela(_k) or _k, _k if _tela(_k) else None, _k)
CASOS.update({
    'tela_direta': ('ECHELON_16', None, 'ECHELON_16'),          # a chave de família direto em point_code
    'incoerente': ('ESCALAO', 'ECHELON_FT_18', 'ESCALAO_16'),   # escalão de outra família: o Web desenha o padrão
    'desconhecido': ('999999', None, None),
    'nulo': (None, None, None),
})
FAMILIAS = {k for k in POR_CODIGO if _tela(k)} | {'incoerente'}

# O dock de 86f7d3b (o de antes da escala) medido em todos os casos acima: nome, descrição,
# medida, escalão, situação, os sete textos, tamanho, rotação, opacidade, cor e zoom apareciam
# em TODOS; o escalão vinha habilitado só nas famílias (FAMILIAS) e desabilitado ("Não se
# aplica") nas demais. O que variava por código:
RETRATO_DOCK = {
    '140500': ({'angulo_secundario'}, 'Direção principal'),
    '152000': (set(), 'Direção dos fogos'),
    '270701': ({'mina1', 'mina2', 'mina3'}, 'Rotação'),
}
RETRATO_PADRAO = (set(), 'Rotação')
# Mudanças deliberadas: o escalão desabilitado some (campo que não vale some), os textos e a
# Situação seguem o catálogo do Web, e entram Mostrar no mapa e a aba Avançado.
SEMPRE = ('nome', 'visivel', 'descricao', 'point_code', 'size', 'rotation', 'opacity', 'fill_color', 'zoom_corr',
          'created_zoom', 'ebgeo_id', 'mapa', 'camada_id', 'criado_em', 'atualizado_em', 'bloqueado')
CONDICIONAIS = ('echelon_code', 'status', 'tipo', 'identificacao', 'gdh_ini', 'gdh_fim', 'numero',
                'numero_concentracao', 'altitude', 'mina1', 'mina2', 'mina3', 'angulo_secundario', 'classe_suprimento')


def esperado(caso):
    """(campos visíveis, rótulo da rotação) que a feição do caso deve mostrar."""
    _pc, _ec, chave = CASOS[caso]
    extra, rotulo = RETRATO_DOCK.get(caso, RETRATO_PADRAO)
    vis = set(SEMPRE) | extra
    if caso in FAMILIAS:
        vis.add('echelon_code')
    vis |= {WEB_COLUNA[w] for w in (POR_CODIGO.get(chave) or {}).get('campos', []) if not w.startswith('mina')}
    return vis, rotulo


def attrs_de(caso, bloqueado=None):
    pc, ec, _k = CASOS[caso]
    return {'point_code': pc, 'echelon_code': ec, 'bloqueado': bloqueado}


def divergencias(spec):
    """[(caso, esperado, obtido)] onde a especificação discorda do retrato e do catálogo."""
    erros = []
    for caso in CASOS:
        a = attrs_de(caso)
        vis = {c for c in SEMPRE + CONDICIONAIS if spec.visivel(c, a)}
        exp, rotulo = esperado(caso)
        if vis != exp:
            erros.append((caso, sorted(exp - vis), sorted(vis - exp)))
        if spec.campo('rotation').rotulo_para(a) != rotulo:
            erros.append((caso, rotulo, spec.campo('rotation').rotulo_para(a)))
    return erros


def condicoes(spec):
    vistas = []

    def junta(c):
        if c is not None and c not in vistas:
            vistas.append(c)
    for _el, conds in spec.percorrer():
        for c in conds:
            junta(c)
    for c in spec.campos():
        for cond, _r in getattr(c, 'rotulos', ()):
            junta(cond)
    return vistas


def feicao_qgis(caso, bloqueado=None):
    campos = QgsFields()
    for n in ('point_code', 'echelon_code'):
        campos.append(QgsField(n, QMetaType.Type.QString))
    campos.append(QgsField('bloqueado', QMetaType.Type.Bool))
    f = QgsFeature(campos)
    pc, ec, _k = CASOS[caso]
    f.setAttributes([pc, ec, bloqueado])
    return f


def avaliar_no_qgis(expressao, f):
    ctx = QgsExpressionContext()
    ctx.setFeature(f)
    e = QgsExpression(expressao)
    v = e.evaluate(ctx)
    assert not e.hasEvalError(), (expressao, e.evalErrorString())
    return v


# ---------------------------------------------------------------------------------------------
# Especificação
# ---------------------------------------------------------------------------------------------

class TesteEspecificacaoMedida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario(TIPO)

    def test_tem_especificacao(self):
        self.assertIsNotNone(self.spec, 'a Medida de Coordenação não tem especificação')
        self.assertIn(TIPO, esp.TIPOS_COM_FORMULARIO)

    def test_casos_cobrem_o_catalogo(self):
        self.assertEqual(len(POR_CODIGO), 132)
        self.assertEqual(len(CASOS), 136)
        self.assertEqual(len(FAMILIAS), 53)

    def test_condicoes_seguem_o_retrato_e_o_catalogo(self):
        self.assertIsNotNone(self.spec)
        erros = divergencias(self.spec)
        self.assertEqual(erros, [], erros[:10])
        com_texto = sum(1 for k in POR_CODIGO if self.spec.visivel('identificacao', attrs_de(k)))
        MEDIDAS.append('especificação: {} casos conferidos; Identificação em {} dos 132 códigos'.format(len(CASOS), com_texto))

    def test_regua_reprova_especificacao_degradada(self):
        self.assertIsNotNone(self.spec)
        # pior caso 1: a mina perde o 270701
        ruim = copy.deepcopy(self.spec)
        c = ruim.campo('mina2')
        c.condicao = esp.Condicao(c.condicao.coluna, c.condicao.valores - {'270701'}, c.condicao.negar)
        self.assertTrue(any(e[0] == '270701' for e in divergencias(ruim)))
        # pior caso 2: o texto sem condição, como no dock de antes (aparece em todos os códigos)
        ruim = copy.deepcopy(self.spec)
        ruim.campo('gdh_ini').condicao = None
        [a for a in ruim.abas if a.nome == 'Textos'][0].condicao = None
        self.assertGreaterEqual(len(divergencias(ruim)), 100)
        # pior caso 3: o Setor de Tiro perde o rótulo da direção principal
        ruim = copy.deepcopy(self.spec)
        ruim.campo('rotation').rotulos = ruim.campo('rotation').rotulos[1:]
        self.assertIn(('140500', 'Direção principal', 'Rotação'), divergencias(ruim))
        # pior caso 4: o escalão sem condição (o "Não se aplica" de antes, agora visível)
        ruim = copy.deepcopy(self.spec)
        ruim.campo('echelon_code').condicao = None
        self.assertGreaterEqual(len(divergencias(ruim)), 80)

    def test_expressao_qgis_igual_a_regra_python(self):
        self.assertIsNotNone(self.spec)
        conds = condicoes(self.spec)
        self.assertGreaterEqual(len(conds), 10)
        for cond in conds:
            for caso in CASOS:
                for bloq in (None, True):
                    py = cond.avaliar(attrs_de(caso, bloq))
                    qg = bool(avaliar_no_qgis(cond.expressao(), feicao_qgis(caso, bloq)))
                    self.assertEqual(py, qg, (cond.expressao()[:80], caso, bloq))
        campo = self.spec.campo('rotation')
        for caso in CASOS:
            self.assertEqual(avaliar_no_qgis(campo.expressao_rotulo(), feicao_qgis(caso)), campo.rotulo_para(attrs_de(caso)))

    def test_regua_qgis_reprova_expressao_degradada(self):
        self.assertIsNotNone(self.spec)
        cond = self.spec.campo('status').condicao
        ruim = cond.expressao().replace("'ECHELON_FT'", "'ECHELON_FTX'")
        self.assertNotEqual(bool(avaliar_no_qgis(ruim, feicao_qgis('ECHELON_FT_21'))), cond.avaliar(attrs_de('ECHELON_FT_21')))

    def test_toda_coluna_no_formulario_ou_oculta_e_so_nativos(self):
        self.assertIsNotNone(self.spec)
        colunas = [c.coluna for c in self.spec.campos()]
        self.assertEqual(len(colunas), len(set(colunas)), 'coluna repetida no formulário')
        ocultos = set(self.spec.ocultos)
        self.assertFalse(set(colunas) & ocultos)
        self.assertEqual(set(schema.nomes_campos(TIPO)) - set(colunas) - ocultos, set())
        self.assertEqual(set(colunas) - set(schema.nomes_campos(TIPO)), set())
        self.assertTrue({'svg', 'svg_assinatura', 'anchor', 'classe_suprimento', 'fid'} <= ocultos)
        for c in self.spec.campos():
            self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, c.coluna)

    def test_listas_nativas_legiveis(self):
        from qgis.core import QgsValueMapFieldFormatter
        self.assertIsNotNone(self.spec)
        mapa = [list(d.items())[0] for d in self.spec.campo('point_code').widget.config['map']]
        rotulos = dict((v, r) for r, v in mapa)
        self.assertEqual(rotulos['152000'], 'Fogos: Base de fogos')
        self.assertEqual(rotulos['ECHELON_FT'], 'Núcleo Força-Tarefa: Núcleo (requer escalão)')
        self.assertIn('270800', rotulos)  # fora do seletor do Web, mas a feição antiga mostra o nome
        self.assertEqual(set(v for _r, v in mapa), {i['code'] for i in CATALOGO['lista']} | {'270800', 'ECHELON',
                         'ECHELON_FT', 'ESCALAO', 'ESCALAO_FT'})
        for col, padrao in (('status', 'Ocupado (padrão)'), ('mina1', 'Antipessoal (padrão)'),
                            ('echelon_code', 'Batalhão (padrão)')):
            primeiro = list(self.spec.campo(col).widget.config['map'][0].items())[0]
            self.assertEqual(primeiro, (padrao, QgsValueMapFieldFormatter.NULL_VALUE), col)

    def test_campos_que_desenham_estao_na_assinatura(self):
        """Todo campo condicional que o catálogo usa e muda o desenho está na assinatura do SVG."""
        from Calco.motor.motor import Motor
        self.assertIsNotNone(self.spec)
        vigiados = set(simbolos.campos_que_desenham(TIPO))
        provas = {'status': ('ECHELON', {'echelon_code': 'ECHELON_16'}, 'preparado'),
                  'mina1': ('270701', {}, 'ac'), 'angulo_secundario': ('140500', {}, 80.0),
                  'echelon_code': ('ESCALAO', {'echelon_code': 'ESCALAO_16'}, 'ESCALAO_21'),
                  'identificacao': ('130100', {}, 'ALFA'), 'numero_concentracao': ('240601', {}, 'AB0101'),
                  'fill_color': ('130100', {}, '#cc0000'), 'point_code': ('130100', {}, '130600')}
        for col, (codigo, base, valor) in provas.items():
            self.assertIn(col, vigiados, col)
            a = dict(base, point_code=codigo)
            b = dict(a, **{col: valor})
            svg_a = Motor.instancia().medida(simbolos.props_web_de_atributos(TIPO, a))['svg']
            svg_b = Motor.instancia().medida(simbolos.props_web_de_atributos(TIPO, b))['svg']
            self.assertNotEqual(svg_a, svg_b, '{} não muda o desenho'.format(col))
            self.assertNotEqual(simbolos.assinatura(TIPO, a), simbolos.assinatura(TIPO, b), col)
        for c in self.spec.campos():
            if c.condicao is not None and c.coluna in CONDICIONAIS:
                self.assertIn(c.coluna, vigiados, c.coluna)
        # pior caso: a assinatura sem a Situação não acusa a troca
        orig = simbolos.CAMPOS_DESENHO[TIPO]
        try:
            simbolos.CAMPOS_DESENHO[TIPO] = [c for c in orig if c != 'status']
            a = {'point_code': 'ECHELON', 'echelon_code': 'ECHELON_16'}
            self.assertEqual(simbolos.assinatura(TIPO, a), simbolos.assinatura(TIPO, dict(a, status='preparado')))
        finally:
            simbolos.CAMPOS_DESENHO[TIPO] = orig


# ---------------------------------------------------------------------------------------------
# Regras de troca
# ---------------------------------------------------------------------------------------------

class TesteRegrasMedida(unittest.TestCase):
    def test_escalao_acompanha_a_familia(self):
        r = regras.ao_mudar(TIPO, {'point_code': 'ECHELON', 'echelon_code': 'ECHELON_21'}, {'point_code': 'ESCALAO_FT'})
        self.assertEqual(r.get('echelon_code'), 'ESCALAO_FT_21')
        r = regras.ao_mudar(TIPO, {'point_code': '130100', 'echelon_code': None}, {'point_code': 'ECHELON'})
        self.assertEqual(r.get('echelon_code'), 'ECHELON_16')
        r = regras.ao_mudar(TIPO, {'point_code': 'ESCALAO', 'echelon_code': 'ESCALAO_18'}, {'point_code': '130100'})
        self.assertIn('echelon_code', r)
        self.assertIsNone(r['echelon_code'])
        # o escalão que o operador escolheu na mesma edição fica
        r = regras.ao_mudar(TIPO, {'point_code': 'ECHELON', 'echelon_code': 'ECHELON_21'},
                            {'point_code': 'ESCALAO', 'echelon_code': 'ESCALAO_12'})
        self.assertNotIn('echelon_code', r)

    def test_cor_padrao_do_tipo(self):
        self.assertEqual(regras.ao_mudar(TIPO, {'point_code': '130100'}, {'point_code': '271201'}).get('fill_color'), '#00B04E')
        r = regras.ao_mudar(TIPO, {'point_code': '271201', 'fill_color': '#00b04e'}, {'point_code': '130100'})
        self.assertIn('fill_color', r)
        self.assertIsNone(r['fill_color'])
        self.assertNotIn('fill_color', regras.ao_mudar(TIPO, {'point_code': '130100', 'fill_color': '#cc0000'},
                                                       {'point_code': '271203'}))
        self.assertNotIn('fill_color', regras.ao_mudar(TIPO, {'point_code': '271201', 'fill_color': '#00B04E'},
                                                       {'point_code': '271204'}))

    def test_minas_e_seta_nao_passam_de_um_tipo_a_outro(self):
        r = regras.ao_mudar(TIPO, {'point_code': '270701', 'mina1': 'ac', 'angulo_secundario': 20.0, 'mina2': None},
                            {'point_code': '140500'})
        self.assertEqual({k: r[k] for k in ('mina1', 'angulo_secundario')}, {'mina1': None, 'angulo_secundario': None})
        self.assertNotIn('mina2', r)  # já nula: nada a gravar
        self.assertEqual(regras.ao_mudar(TIPO, {'point_code': '270701', 'mina1': 'ac'}, {'mina1': 'vazia'}), {})


# ---------------------------------------------------------------------------------------------
# Formulário nativo sem o plugin (processo novo)
# ---------------------------------------------------------------------------------------------

CAPTURAS = ('152000', '140500', '270701', '130100', 'ECHELON_FT_18')

# Roda num processo novo, sem o caminho do plugin. argv: gpkg, json de saída, pasta de capturas
# ('' sem), casos a montar ('*' todos), capturas... Com EBGEO_PLUGIN, importa o plugin e liga o
# guardião (a captura "com o plugin").
SCRIPT = r'''
import sys, os, json, time
gp, saida, pasta, quais = sys.argv[1:5]
capturar = set(sys.argv[5:])
res = {'etapa': 'inicio'}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
plugin = os.environ.get('EBGEO_PLUGIN')
if plugin:
    sys.path.insert(0, plugin)
from qgis.core import QgsApplication, QgsVectorLayer
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QComboBox, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
QgsGui.editorWidgetRegistry().initEditors()
L = QgsVectorLayer(gp + '|layername=coordination_measure', 'Medida de Coordenação', 'ogr')
if plugin:
    from Calco import guardiao
    guardiao.garantir(L, 'coordination_measure')
fc = L.editFormConfig()
nomes = L.fields().names()
res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
res['layout'] = fc.layout().name
res['init'] = fc.initCodeSource().name
res['init_codigo'] = len(fc.initCode() or '') + len(fc.initFunction() or '')
res['ui'] = fc.uiForm()
res['acoes'] = len(L.actions().actions())
res['widgets'] = {n: L.editorWidgetSetup(i).type() for i, n in enumerate(nomes)}
res['aliases'] = {n: L.attributeAlias(i) for i, n in enumerate(nomes)}
res['tabela_ocultas'] = sorted(c.name for c in L.attributeTableConfig().columns() if c.hidden and c.name)
res['etapa'] = 'estatico'
gravar()
L.startEditing()
res['formularios'] = {}
for f in L.getFeatures():
    chave = f['nome']
    if quais != '*' and chave not in quais.split(','):
        continue
    res['etapa'] = 'montando ' + chave
    gravar()
    t = time.perf_counter()
    form = QgsAttributeForm(L, f)
    form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
    ms = (time.perf_counter() - t) * 1000
    form.resize(500, 640)
    form.show(); app.processEvents()
    tabs = form.findChildren(QTabWidget)
    abas, vis, rotulos, travados, listas, imgs = [], set(), set(), {}, {}, []
    tw = tabs[0] if tabs else None
    indices = [k for k in range(tw.count()) if tw.isTabVisible(k)] if tw else [None]
    for k in indices:
        if tw is not None:
            tw.setCurrentIndex(k); app.processEvents()
            abas.append(tw.tabText(k))
        # abre o grupo recolhido pelo botão dele (o Python o vê como QGroupBox, sem setCollapsed),
        # e só na aba à mostra, onde o grupo está visível
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
                if isinstance(w, QComboBox):
                    listas[n] = w.currentText()
        rotulos |= {lb.text() for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text()}
        if pasta and chave in capturar:
            imgs.append(form.grab().toImage())
    salvo = form.save()
    mudou = {str(k): sorted(L.fields().at(i).name() for i in v) for k, v in L.editBuffer().changedAttributeValues().items()}
    res['formularios'][chave] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
                                 'travados': travados, 'listas': listas, 'salvo': salvo, 'mudou_ao_salvar': mudou}
    if imgs:
        W = sum(im.width() for im in imgs) + 8 * (len(imgs) - 1)
        H = max(im.height() for im in imgs) + 26
        out = QImage(W, H, QImage.Format.Format_ARGB32); out.fill(QColor('white'))
        p = QPainter(out); x = 0
        p.setFont(QFont('Segoe UI', 10))
        p.drawText(4, 17, '{}: formulário nativo {} o plugin, uma imagem por aba visível; montado em {:.0f} ms'.format(
            f['point_code'], 'COM' if plugin else 'SEM', ms))
        for im in imgs:
            p.drawImage(x, 26, im); x += im.width() + 8
        p.end()
        out.save(os.path.join(pasta, 'nativo_{}_{}.png'.format(chave, 'com_plugin' if plugin else 'sem_plugin')))
    form.close(); form.deleteLater(); app.processEvents()
L.rollBack()
res['etapa'] = 'fim'
gravar()
'''


def _exe():
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    return exe if os.path.exists(exe) else sys.executable


def rodar_sem_plugin(caminho, quais='*', capturas=(), pasta='', com_plugin=False, timeout=300):
    script = os.path.join(TMP, 'sem_plugin_medida.py')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(SCRIPT)
    saida = os.path.join(TMP, 'res_{}.json'.format(uuid.uuid4().hex[:8]))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if com_plugin:
        env['EBGEO_PLUGIN'] = PLUGIN
    else:
        env.pop('EBGEO_PLUGIN', None)
    args = [_exe(), script, caminho, saida, pasta, quais] + list(capturas)
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


# Casos extras do GeoPackage: a bloqueada e a de colunas nulas (salvar sem mudar não as preenche).
EXTRAS = {'bloqueada': ('130100', None), 'nulos': ('ECHELON', None)}


def atributos_do_caso(caso):
    if caso in EXTRAS:
        pc, ec = EXTRAS[caso]
    else:
        pc, ec, _k = CASOS[caso]
    a = dict(schema.padroes(TIPO))
    a.update(ebgeo_id=str(uuid.uuid4()), nome=caso, point_code=pc, echelon_code=ec, created_zoom=13.0,
             criado_em='2026-10-05T09:00:00+00:00', atualizado_em='2026-10-05T09:00:00+00:00',
             bloqueado=(caso == 'bloqueada'))
    if caso == 'nulos':
        for col in ('size', 'rotation', 'opacity', 'fill_color', 'zoom_corr', 'created_zoom', 'status', 'visivel'):
            a[col] = None
    else:
        a.update(rotation=30.0, fill_color=VERDE if (POR_CODIGO.get(CASOS.get(caso, (0, 0, ''))[2]) or {}).get('corPadrao') else None)
    if caso == '130100':
        a.update(tipo='P Lib', identificacao='ALFA', gdh_ini='121400Z OUT', gdh_fim='121800Z OUT')
    if caso == '270701':
        a.update(mina1='ac', mina3='vazia')
    if caso == '140500':
        a.update(angulo_secundario=60.0)
    return a


def criar_calco(caminho):
    gpkg.criar_calco(caminho, [TIPO])
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, TIPO), 'Medida de Coordenação', 'ogr')
    idx = vl.fields().indexOf
    vl.startEditing()
    for caso in list(CASOS) + list(EXTRAS):
        f = QgsFeature(vl.fields())
        for k, v in schema.atributos_para_qgis(TIPO, atributos_do_caso(caso)).items():
            if idx(k) >= 0:
                f.setAttribute(idx(k), v)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-51.2, -30.0)))
        vl.addFeature(f)
    assert vl.commitChanges()
    return vl


def reprovacoes(res, codigo, spec, casos=None):
    erros = []
    if codigo != 0:
        erros.append('processo saiu com {} na etapa {}'.format(codigo, res.get('etapa')))
    if not res:
        return erros + ['sem resultado']
    if res.get('modulos_ebgeo'):
        erros.append('o plugin estava carregado: {}'.format(res['modulos_ebgeo']))
    if res.get('layout') != 'DragAndDrop':
        erros.append('layout {}'.format(res.get('layout')))
    if res.get('init') != 'NoSource' or res.get('init_codigo') or res.get('ui') or res.get('acoes'):
        erros.append('formulário com código')
    for col, tipo in (res.get('widgets') or {}).items():
        if tipo not in esp.WIDGETS_NATIVOS:
            erros.append('widget não nativo em {}: {}'.format(col, tipo))
    for c in spec.campos():
        if (res.get('aliases') or {}).get(c.coluna) != c.rotulo:
            erros.append('alias de {}: {!r}'.format(c.coluna, (res.get('aliases') or {}).get(c.coluna)))
    if set(res.get('tabela_ocultas') or []) != set(spec.ocultos):
        erros.append('ocultas na tabela: {}'.format(res.get('tabela_ocultas')))
    forms = res.get('formularios') or {}
    so_leitura = {c.coluna for c in spec.campos() if c.somente_leitura}
    for caso in casos or (list(CASOS) + list(EXTRAS)):
        if caso not in forms:
            erros.append('formulário de {} não montado'.format(caso))
            continue
        fo = forms[caso]
        a = atributos_do_caso(caso)
        vis = {c.coluna for c in spec.campos() if spec.visivel(c.coluna, a)}
        if set(fo['visiveis']) != vis:
            erros.append('{}: visíveis a mais {} a menos {}'.format(
                caso, sorted(set(fo['visiveis']) - vis), sorted(vis - set(fo['visiveis']))))
        abas = [ab.nome for ab in spec.abas if ab.prefixo is None and (ab.condicao is None or ab.condicao.avaliar(a))]
        if fo['abas'] != abas:
            erros.append('{}: abas {} (esperadas {})'.format(caso, fo['abas'], abas))
        rotulos = {c.rotulo_para(a) for c in spec.campos() if c.coluna in vis}
        if not rotulos <= set(fo['rotulos']):
            erros.append('{}: rótulos ausentes {}'.format(caso, sorted(rotulos - set(fo['rotulos']))))
        if (esp.AVISO_BLOQUEADA in fo['rotulos']) != (caso == 'bloqueada'):
            erros.append('{}: aviso de bloqueio errado'.format(caso))
        for col, travado in fo['travados'].items():
            if travado != (caso == 'bloqueada' or col in so_leitura):
                erros.append('{}: {} {}'.format(caso, col, 'travado' if travado else 'editável'))
        if not fo['salvo'] or fo['mudou_ao_salvar']:
            erros.append('{}: salvar sem mudar gravou {}'.format(caso, fo['mudou_ao_salvar']))
    return erros


def _degradar(nome, alterar):
    destino = os.path.join(TMP, 'pior_{}.gpkg'.format(nome))
    shutil.copy(TesteNativoMedida.caminho, destino)
    vl = QgsVectorLayer(gpkg.uri_camada(destino, TIPO), 'Medida de Coordenação', 'ogr')
    alterar(vl)
    vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
    return destino


class TesteNativoMedida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario(TIPO)
        cls.caminho = os.path.join(TMP, 'calco_medida.gpkg')
        vl = criar_calco(cls.caminho)
        t = time.perf_counter()
        C.aplicar_estilo(vl, TIPO)
        MEDIDAS.append('aplicar o estilo com o formulário: {:.2f} s'.format(time.perf_counter() - t))
        C.salvar_estilo_padrao(vl)
        cls.res, cls.codigo = rodar_sem_plugin(cls.caminho, '*', CAPTURAS, SAIDA)
        cls.res_com, cls.codigo_com = rodar_sem_plugin(cls.caminho, '*', CAPTURAS, SAIDA, com_plugin=True)

    def test_sem_plugin_confere_com_a_especificacao(self):
        self.assertIsNotNone(self.spec)
        erros = reprovacoes(self.res, self.codigo, self.spec)
        self.assertEqual(erros, [], ' | '.join(erros[:15]))
        forms = self.res['formularios']
        ms = sorted(f['ms'] for f in forms.values())
        MEDIDAS.append('sem o plugin: {} formulários montados, {:.0f} a {:.0f} ms (mediana {:.0f})'.format(
            len(forms), ms[0], ms[-1], ms[len(ms) // 2]))
        self.assertEqual(forms['130100']['abas'], ['Símbolo', 'Textos', 'Aparência', 'Avançado'])
        self.assertEqual(forms['152000']['abas'], ['Símbolo', 'Aparência', 'Avançado'])
        self.assertIn('Direção dos fogos', forms['152000']['rotulos'])
        self.assertIn('Direção principal', forms['140500']['rotulos'])
        self.assertEqual(forms['ECHELON_FT_18']['listas']['echelon_code'], 'Núcleo FT - Brigada')
        self.assertEqual(forms['nulos']['listas']['status'], 'Ocupado (padrão)')
        self.assertEqual(forms['270701']['listas']['mina1'], 'Anticarro')
        self.assertEqual(forms['270701']['listas']['mina2'], 'Antipessoal (padrão)')
        self.assertEqual(forms['270800']['listas']['point_code'], 'Proteção - Minas: Área minada (fora do seletor do EBGeo Web)')

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(self.codigo_com, 0, self.res_com.get('etapa'))
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        for caso, fo in self.res['formularios'].items():
            com = self.res_com['formularios'][caso]
            self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos'], fo['listas']),
                             (com['abas'], com['visiveis'], com['rotulos'], com['listas']), caso)
            self.assertFalse(com['mudou_ao_salvar'], caso)
        from qgis.PyQt.QtGui import QImage
        iguais = 0
        for caso in CAPTURAS:
            a = QImage(os.path.join(SAIDA, 'nativo_{}_sem_plugin.png'.format(caso)))
            b = QImage(os.path.join(SAIDA, 'nativo_{}_com_plugin.png'.format(caso)))
            self.assertFalse(a.isNull() or b.isNull(), caso)
            dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                      if a.pixel(x, y) != b.pixel(x, y))
            iguais += dif == 0
        MEDIDAS.append('capturas com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, len(CAPTURAS)))
        self.assertEqual(iguais, len(CAPTURAS))

    def test_pior_caso_widget_do_plugin_reprova(self):
        def injeta(vl):
            vl.setEditorWidgetSetup(vl.fields().indexOf('point_code'), QgsEditorWidgetSetup('EBGeoSeletorMedida', {}))
        res, codigo = rodar_sem_plugin(_degradar('widget', injeta), '130100', timeout=90)
        erros = reprovacoes(res, codigo, self.spec, ['130100'])
        MEDIDAS.append('pior caso, widget do plugin no estilo: saída {}, etapa "{}", {} reprovações'.format(
            codigo, res.get('etapa'), len(erros)))
        self.assertTrue(any('widget não nativo em point_code' in e for e in erros), erros)

    def test_pior_caso_condicoes_apagadas_reprovam(self):
        def apaga(vl):
            from qgis.core import QgsAttributeEditorContainer, QgsOptionalExpression

            def andar(cont):
                for el in cont.children():
                    if isinstance(el, QgsAttributeEditorContainer):
                        if el.name() in ('Textos', 'Minas'):
                            el.setVisibilityExpression(QgsOptionalExpression())
                        andar(el)
            fc = vl.editFormConfig()
            andar(fc.invisibleRootContainer())
            vl.setEditFormConfig(fc)
        casos = ['152000', '270800', '140500']
        res, codigo = rodar_sem_plugin(_degradar('condicao', apaga), ','.join(casos))
        erros = reprovacoes(res, codigo, self.spec, casos)
        # o campo condicional ainda some pela linha dele; a aba sem condição aparece vazia, e a régua acusa
        self.assertTrue(any(e.startswith('152000: abas') for e in erros), erros)
        self.assertTrue(any(e.startswith('270800: abas') for e in erros), erros)


# ---------------------------------------------------------------------------------------------
# Guardião: as regras pelo formulário nativo e pela tabela
# ---------------------------------------------------------------------------------------------

def camada_guardiao(nome, casos):
    caminho = os.path.join(TMP, nome + '.gpkg')
    gpkg.criar_calco(caminho, [TIPO])
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, TIPO), 'Medida de Coordenação', 'ogr')
    idx = vl.fields().indexOf
    vl.startEditing()
    for i, a in enumerate(casos):
        nulas = [k for k, v in a.items() if v is None]
        a = dict(schema.padroes(TIPO), ebgeo_id=str(uuid.uuid4()), **a)
        a.update(simbolos.renderizar(TIPO, a))
        f = QgsFeature(vl.fields())
        for k, v in schema.atributos_para_qgis(TIPO, a).items():  # como o plugin grava (cor em minúsculas)
            if idx(k) >= 0:
                f.setAttribute(idx(k), None if k in nulas else v)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-51.2 + 0.01 * (i % 4), -30.0 + 0.01 * (i // 4))))
        vl.addFeature(f)
    assert vl.commitChanges()
    C.aplicar_estilo(vl, TIPO)
    return vl


def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


class TesteGuardiaoMedida(unittest.TestCase):
    def test_formulario_nativo_troca_a_familia_e_a_cor(self):
        from test_guardiao import pelo_formulario
        from Calco import guardiao
        vl = camada_guardiao('guard', [{'point_code': 'ECHELON', 'echelon_code': 'ECHELON_21', 'nome': 'a'},
                                       {'point_code': '270701', 'mina1': 'ac', 'nome': 'b'}])
        guardiao.garantir(vl, TIPO)
        fids = {f['nome']: f.id() for f in vl.getFeatures()}
        vl.startEditing()
        pelo_formulario(vl, fids['a'], {'point_code': 'ESCALAO_FT'})
        f = vl.getFeature(fids['a'])
        self.assertEqual((f['point_code'], f['echelon_code']), ('ESCALAO_FT', 'ESCALAO_FT_21'))
        pelo_formulario(vl, fids['b'], {'point_code': '271201'})
        f = vl.getFeature(fids['b'])
        self.assertEqual(str(f['fill_color']).lower(), VERDE)
        self.assertTrue(_nulo(f['mina1']))
        vl.undoStack().undo()   # desfaz a regra
        f = vl.getFeature(fids['b'])
        self.assertEqual((f['point_code'], f['mina1']), ('271201', 'ac'))
        vl.rollBack()

    def test_pior_caso_sem_guardiao_a_familia_fica_velha(self):
        from test_guardiao import pelo_formulario
        vl = camada_guardiao('sem', [{'point_code': 'ECHELON', 'echelon_code': 'ECHELON_21', 'nome': 'a'}])
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pelo_formulario(vl, fid, {'point_code': 'ESCALAO_FT'})
        self.assertEqual(vl.getFeature(fid)['echelon_code'], 'ECHELON_21')  # a régua acima reprovaria
        vl.rollBack()


def renderizar_camada(vl, lado=400):
    """A camada desenhada numa imagem, na extensão das feições (para comparar pixel a pixel)."""
    from qgis.core import QgsMapRendererCustomPainterJob, QgsMapSettings, QgsRectangle
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor, QImage, QPainter
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(vl.crs())
    ms.setOutputSize(QSize(lado, lado))
    ms.setOutputDpi(96)
    ms.setExtent(QgsRectangle(-51.21, -30.01, -51.16, -29.96))
    img = QImage(QSize(lado, lado), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start()
    job.waitForFinished()
    p.end()
    return img


# Valores que o operador e o Web gravam e que um widget nativo mal configurado regrava ao salvar
# QUALQUER mudança: colunas nulas (tamanho, rotação, opacidade, cor, zoom, situação, mostrar no
# mapa), números com mais casas que o widget, rotação fora de -180 a 180 e a cor do Web em caixa alta.
CASOS_SO_NOME = [
    {'nome': 'nulos', 'point_code': 'ECHELON', 'echelon_code': None, 'size': None, 'rotation': None, 'opacity': None,
     'fill_color': None, 'zoom_corr': None, 'created_zoom': None, 'status': None, 'visivel': None},
    {'nome': 'casas', 'point_code': '130100', 'size': 1.237, 'rotation': 12.345, 'opacity': 0.875, 'created_zoom': 13.37,
     'zoom_corr': False, 'tipo': 'P Lib', 'identificacao': 'ALFA'},
    {'nome': 'azimute', 'point_code': '152000', 'rotation': 330.0, 'zoom_corr': False},
    {'nome': 'setor', 'point_code': '140500', 'rotation': -30.0, 'angulo_secundario': None, 'zoom_corr': False},
    {'nome': 'minas', 'point_code': '270701', 'mina1': 'ac', 'mina2': None, 'zoom_corr': False},
    {'nome': 'destruicao', 'point_code': '271201', 'fill_color': '#00B04E', 'zoom_corr': False},
    {'nome': 'escalao', 'point_code': 'ESCALAO_FT', 'echelon_code': 'ESCALAO_FT_21', 'zoom_corr': False},
]


def mudancas_ao_salvar_so_o_nome(vl):
    """[(nome, coluna, antes, depois)] das colunas (fora nome e atualizado_em) que mudam quando o
    nome de cada feição é salvo pelo formulário nativo; e os pixels do desenho que mudam."""
    from test_guardiao import pelo_formulario
    nomes = vl.fields().names()
    antes = {f.id(): {n: regras.valor(f[n]) for n in nomes} for f in vl.getFeatures()}
    img0 = renderizar_camada(vl)
    vl.startEditing()
    for fid, a in antes.items():
        pelo_formulario(vl, fid, {'nome': a['nome'] + ' (renomeada)'})
    assert vl.commitChanges(), vl.commitErrors()
    lida = QgsVectorLayer(vl.source(), 'r', 'ogr')
    mud = []
    for f in lida.getFeatures():
        for n in nomes:
            if n in ('nome', 'atualizado_em'):
                continue
            a, d = antes[f.id()][n], regras.valor(f[n])
            if a != d:
                mud.append((antes[f.id()]['nome'], n, a, d))
    img1 = renderizar_camada(vl)
    pixels = sum(1 for y in range(img0.height()) for x in range(img0.width()) if img0.pixel(x, y) != img1.pixel(x, y))
    tinta = sum(1 for y in range(img0.height()) for x in range(img0.width()) if img0.pixelColor(x, y).red() < 200)
    return mud, pixels, tinta


class TesteSalvarSoONome(unittest.TestCase):
    def test_salvar_so_o_nome_nao_muda_coluna_nem_pixel(self):
        vl = camada_guardiao('so_nome', CASOS_SO_NOME)
        mud, pixels, tinta = mudancas_ao_salvar_so_o_nome(vl)
        MEDIDAS.append('salvar só o nome pelo nativo em {} feições: {} colunas mudaram, {} pixels mudaram de {} '
                       'desenhados'.format(len(CASOS_SO_NOME), len(mud), pixels, tinta))
        self.assertGreater(tinta, 500)
        self.assertEqual(mud, [])
        self.assertEqual(pixels, 0)

    def test_pior_caso_widget_que_corta_reprova(self):
        """O mesmo estilo com o tamanho em 0 casas e sem nulo (a saída real degradada) tem de reprovar."""
        vl = camada_guardiao('so_nome_pior', CASOS_SO_NOME)
        i = vl.fields().indexOf('size')
        cfg = dict(vl.editorWidgetSetup(i).config())
        cfg.update(Precision=0, AllowNull=False)
        vl.setEditorWidgetSetup(i, QgsEditorWidgetSetup('Range', cfg))
        mud, pixels, _t = mudancas_ao_salvar_so_o_nome(vl)
        self.assertTrue(any(c == 'size' for _n, c, _a, _d in mud), mud)
        self.assertGreater(pixels, 0)


# ---------------------------------------------------------------------------------------------
# Dock
# ---------------------------------------------------------------------------------------------

class TesteDockMedida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_dock_medida.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar()
        definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())
        cls.painel.setParent(None)
        cls.painel.resize(440, 980)
        cls.painel.show()
        cls.lyr = cls.calco.camada(TIPO)
        cls.spec = esp.formulario(TIPO)

    def tearDown(self):
        if self.lyr.isEditable():
            self.lyr.rollBack()
        _app.processEvents()

    def _nova(self, **attrs):
        from Calco.ferramentas import gravar_feicao
        a = dict(schema.padroes(TIPO), ebgeo_id=str(uuid.uuid4()), nome='Medida do teste')
        a.update(attrs)
        eid = gravar_feicao(self.lyr, TIPO, QgsGeometry.fromPointXY(QgsPointXY(-51.2, -30.0)), a)
        self.painel._camada_mudou(self.lyr)
        self.painel.mostrar_feicao(self.lyr, eid)
        self.painel._selecao_mudou()
        return eid

    def _disco(self, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, TIPO), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _capturar(self, nome):
        self.painel.show()
        _app.processEvents()
        from Calco.ui.blocos.previa import esperar
        esperar(self.painel)  # a amostra do estilo desenha fora da interface
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def _rotulos(self):
        from qgis.PyQt.QtWidgets import QLabel
        return {lb.text() for lb in self.painel.form_host.findChildren(QLabel) if lb.isVisibleTo(self.painel.form_host)}

    def test_campos_do_dock_iguais_aos_da_especificacao(self):
        erros = []
        for caso, (pc, ec, _k) in CASOS.items():
            self._nova(point_code=pc, echelon_code=ec)
            vis = self.painel.campos_visiveis()
            exp, rotulo = esperado(caso)
            if vis & set(SEMPRE + CONDICIONAIS) != exp:
                erros.append((caso, sorted(exp - vis), sorted(vis - exp)))
            for col in set(CONDICIONAIS) - exp:
                if col in self.painel.widgets and not self.painel.widgets[col].isHidden():
                    erros.append((caso, col, 'à mostra'))
            if rotulo not in self._rotulos():
                erros.append((caso, rotulo))
        MEDIDAS.append('dock: {} casos montados, {} divergências'.format(len(CASOS), len(erros)))
        self.assertEqual(erros, [], erros[:10])

    def test_busca_da_medida(self):
        from qgis.PyQt.QtCore import QModelIndex
        self._nova(point_code='130100')
        cb = self.painel.widgets['point_code']
        self.assertTrue(cb.isEditable())
        self.assertNotIn('270800', [cb.itemData(i) for i in range(cb.count())])
        comp = cb.completer()
        achados = {}
        for busca in ('base de fogos', 'obstaculo', 'PROTEÇÃO - QBRN', '152000', 'forca-tarefa'):
            comp.setCompletionPrefix(busca)
            m = comp.completionModel()
            achados[busca] = [m.index(i, 0).data() for i in range(m.rowCount())]
        self.assertEqual(achados['base de fogos'], ['Fogos: Base de fogos'])
        self.assertEqual(achados['152000'], ['Fogos: Base de fogos'])
        self.assertTrue(achados['obstaculo'] and all('Obstáculos' in a for a in achados['obstaculo']), achados['obstaculo'])
        self.assertEqual(len(achados['PROTEÇÃO - QBRN']), 4)
        self.assertEqual(len(achados['forca-tarefa']), 2)
        # escolher na lista da busca troca a medida
        comp.setCompletionPrefix('base de fogos')
        comp.activated[QModelIndex].emit(comp.completionModel().index(0, 0))
        _app.processEvents()
        self.assertEqual(self.lyr.getFeature(self.painel.fid)['point_code'], '152000')
        self.assertEqual(self.painel.widgets['point_code'].currentText(), 'Fogos: Base de fogos')

    def test_buffer_salvar_com_as_regras(self):
        eid = self._nova(point_code='ECHELON', echelon_code='ECHELON_21')
        self.assertFalse(self.lyr.isEditable())
        cb = self.painel.widgets['point_code']
        cb.setCurrentIndex(cb.findData('ESCALAO_FT'))
        _app.processEvents()
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual((f['point_code'], f['echelon_code']), ('ESCALAO_FT', 'ESCALAO_FT_21'))
        self.assertEqual(self._disco(eid)['point_code'], 'ECHELON')
        esc = self.painel.widgets['echelon_code']
        self.assertEqual((esc.count(), esc.currentText()), (13, 'Divisão'))
        self.assertNotIn('status', self.painel.campos_visiveis())
        cb = self.painel.widgets['point_code']
        cb.setCurrentIndex(cb.findData('271201'))
        _app.processEvents()
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual(str(f['fill_color']).lower(), VERDE)
        self.assertTrue(_nulo(f['echelon_code']))
        self.assertTrue(self.painel.salvar())
        d = self._disco(eid)
        self.assertEqual((d['point_code'], str(d['fill_color']).lower()), ('271201', VERDE))
        self.assertEqual(simbolos.svg_de_coluna(d['svg']),
                         simbolos.renderizar(TIPO, {n: d[n] for n in d.fields().names()}, detalhes=True)[1]['svg'],
                         'o SVG salvo não é o da medida nova')

    def test_capturas_e_widgets_ricos(self):
        from qgis.PyQt.QtWidgets import QSpinBox, QLineEdit
        self._nova(point_code='152000', rotation=-30.0)
        w = self.painel.widgets['rotation']
        self.assertIsInstance(w, QSpinBox)
        self.assertEqual((w.minimum(), w.maximum(), w.value()), (0, 359, 330))
        self._capturar('dock_152000.png')
        self._nova(point_code='140500', rotation=0.0)
        sec = self.painel.widgets['angulo_secundario'].spin
        self.assertEqual(sec.value(), 315)
        self.assertIn('Abertura do setor: 45°', self._rotulos())
        sec.setValue(70)
        self.painel._gravar_pendentes()
        self.assertIn('Abertura do setor: 70°', self._rotulos())
        self.assertEqual(self.lyr.getFeature(self.painel.fid)['angulo_secundario'], 70.0)
        self._capturar('dock_140500.png')
        self.lyr.rollBack()
        self._nova(point_code='270701', mina1='ac')
        self.assertEqual([self.painel.widgets['mina{}'.format(i)].currentText() for i in (1, 2, 3)],
                         ['Anticarro', 'Antipessoal', 'Antipessoal'])
        self._capturar('dock_270701.png')
        self._nova(point_code='130100', tipo='P Lib', identificacao='ALFA')
        ed = self.painel.widgets['gdh_ini']
        self.assertIsInstance(ed, QLineEdit)
        self.assertEqual(ed.placeholderText(), 'Ex: 121400Z JUN')
        self.assertIn('ddhhmmZ', ed.toolTip())
        self._capturar('dock_130100.png')
        self._nova(point_code='ECHELON_FT', echelon_code='ECHELON_FT_18', status='preparado')
        self.assertEqual(self.painel.widgets['status'].currentData(), 'preparado')
        self._capturar('dock_ECHELON_FT_18.png')


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
