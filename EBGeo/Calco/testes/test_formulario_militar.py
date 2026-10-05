# -*- coding: utf-8 -*-
"""
Formulário do Símbolo Militar, do Símbolo de Engenharia e da Declinação Magnética
(formulario/tipos/militar.py), e o SVG redesenhado pelo guardião em qualquer caminho de edição
dos quatro símbolos pontuais (guardiao.py).

  - Especificação: para cada conjunto do catálogo (e para o conjunto desconhecido e o SIDC nulo,
    que valem como o do SIDC padrão), os amplificadores que aparecem são os do construtor de SIDC
    (medidos no próprio diálogo), mais a Direção fora de Instalações e Atividades (regra do Web) e
    a barra de engajamento onde o catálogo a admite; os demais campos do dock de antes
    (DOCK_ANTES, medido no dock de 86f7d3b em 2026-10-05) continuam lá. Os rótulos que mudam com
    o conjunto são os do construtor. A expressão QGIS de cada condição dá o mesmo que a regra em
    Python. Engenharia e declinação mantêm o que o dock de antes mostrava.
  - Régua sem o plugin: o GeoPackage aberto num processo NOVO e SEM o plugin monta o formulário
    de cada feição (3 SIDC de conjuntos diferentes, uma bloqueada, 2 itens de engenharia, a
    declinação) e confere visíveis, rótulos (inclusive os por dados e os textos legíveis por
    expressão), travados, a restrição do SIDC, ocultos e "salvar sem mudar não muda nada". O
    mesmo com o plugin dá o mesmo formulário. Pior caso, a saída REAL degradada (condição de um
    amplificador apagada, restrição apagada, texto legível trocado), que a régua tem de reprovar.
  - Guardião: editar o SIDC pelo formulário nativo e pela tabela de atributos, a medida pela
    tabela, o item de engenharia, a feição colada e a gravação fora de comando redesenham o
    símbolo (assinatura em dia, o estilo sem aviso), num comando que o Ctrl+Z desfaz; sem o
    guardião, o aviso fica (pior caso).
  - Dock: os campos conforme o SIDC, a edição no buffer com o SVG redesenhado, o construtor de
    SIDC, o seletor de engenharia e o Recalcular da declinação no buffer.

Capturas em EBGEO_TESTE_SAIDA (padrão: temporária); com QT_QPA_PLATFORM=offscreen, o texto só sai
legível com QT_QPA_FONTDIR apontando a pasta de fontes do sistema.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_militar.py
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
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression, QgsExpressionContext,
    QgsExpressionContextUtils, QgsFeature, QgsFieldConstraints, QgsGeometry, QgsMapRendererCustomPainterJob,
    QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage, QPainter  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from qgis.gui import QgsGui  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from Calco import calco as C, gpkg, schema, simbolos, guardiao, regras, estilos_pontuais  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402
from Calco.formulario.tipos import militar as fm  # noqa: E402
from test_guardiao import pelo_formulario, pela_tabela  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_form_militar_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []
TIPOS = ('military_symbol', 'engineering_symbol', 'magnetic_declination')
AMPLIFICADORES = {c for c, _w in schema.AMPLIFICADORES}
_ICONE = {'size', 'rotation', 'opacity', 'fill_color', 'zoom_corr', 'created_zoom'}
# O dock de 86f7d3b, montado para uma feição de cada tipo (PainelCalco, widgets à mostra; medido em
# 2026-10-05): o militar mostrava os 16 amplificadores sempre, qualquer que fosse o SIDC.
DOCK_ANTES = {
    'military_symbol': {'nome', 'descricao', 'sidc'} | AMPLIFICADORES | _ICONE,
    'engineering_symbol': {'nome', 'descricao', 'point_code'} | _ICONE,
    'magnetic_declination': {'nome', 'descricao', 'declination', 'convergence', 'calculation_date', 'size', 'fill_color',
                             'zoom_corr', 'created_zoom'},
}
SIDC_10 = '10031000161211000000'          # Amigo, Unidades, Batalhão, Infantaria
SIDC_15 = '10061500331101000000'          # Hostil, Equipamentos e Viaturas, sobre lagartas, Fuzil
SIDC_40 = '10034000001100000000'          # Amigo, Atividades e Eventos, Incidente


def _sidc_do_conjunto(conj):
    return '1003' + conj + '0000' + '000000' + '0000'


def conjuntos():
    return list(fm.catalogos()['militar']['porConjunto'])


# ---------------------------------------------------------------------------------------------
# Retrato do construtor de SIDC (o diálogo de verdade, por conjunto)
# ---------------------------------------------------------------------------------------------

_RETRATO = {}


def retrato_construtor():
    """{conjunto: ({colunas de texto}, {coluna: rótulo})} lidos do ConstrutorSidc montado."""
    if not _RETRATO:
        from Calco.ui.construtor_sidc import ConstrutorSidc
        col = {w: c for c, w in schema.AMPLIFICADORES}
        for conj in conjuntos():
            d = ConstrutorSidc()
            assert d.aplicar_sidc(_sidc_do_conjunto(conj)), conj
            rot = {}
            for i in range(d.form_texto.rowCount()):
                lb = d.form_texto.itemAt(i, d.form_texto.ItemRole.LabelRole).widget()
                ed = d.form_texto.itemAt(i, d.form_texto.ItemRole.FieldRole).widget()
                web = [w for w, e in d.textos.items() if e is ed][0]
                rot[col[web]] = lb.text()
            _RETRATO[conj] = (set(rot), rot)
            d.deleteLater()
    return _RETRATO


def esperado_militar(sidc):
    """Os campos do dock de antes e os amplificadores que o conjunto do SIDC deve mostrar."""
    conj = '' if sidc is None else str(sidc)[4:6]
    por = fm.catalogos()['militar']['porConjunto']
    if conj not in por:
        conj = fm.conjunto_padrao()
    vis = (DOCK_ANTES['military_symbol'] - AMPLIFICADORES) | retrato_construtor()[conj][0]
    if conj not in ('20', '40'):
        vis.add('direction')
    if por[conj]['aplicavel'].get('barraEngajamento'):
        vis.add('engagement_bar')
    return vis


AMOSTRAS_SIDC = [_sidc_do_conjunto(c) for c in conjuntos()] + [SIDC_10, SIDC_15, SIDC_40, '10039900001100000000', None, '', '123']


def divergencias_militar(spec):
    """[(sidc, esperado, obtido)] onde a especificação discorda do retrato."""
    erros = []
    olhados = DOCK_ANTES['military_symbol'] | AMPLIFICADORES
    for sidc in AMOSTRAS_SIDC:
        attrs = {'sidc': sidc}
        vistos = {c for c in olhados if spec.visivel(c, attrs)}
        esperado = esperado_militar(sidc)
        if vistos != esperado:
            erros.append((sidc, sorted(esperado - vistos), sorted(vistos - esperado)))
        conj = (sidc or '')[4:6]
        if conj in retrato_construtor():
            for col, rot in retrato_construtor()[conj][1].items():
                if spec.campo(col).rotulo_para(attrs) != rot:
                    erros.append((sidc, col, rot, spec.campo(col).rotulo_para(attrs)))
    return erros


def condicoes(spec):
    vistas = []
    for el, conds in spec.percorrer():
        for c in conds + ([el.rotulo_se[0]] if isinstance(el, esp.Campo) and el.rotulo_se else []):
            if c not in vistas:
                vistas.append(c)
    return vistas


def contexto_formulario(f):
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.formScope(f))
    ctx.setFeature(f)
    return ctx


def feicao_memoria(tipo, attrs):
    vl = QgsVectorLayer('Point?crs=EPSG:4326', 'm', 'memory')
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QMetaType
    tp = {'str': QMetaType.Type.QString, 'real': QMetaType.Type.Double, 'bool': QMetaType.Type.Bool,
          'datetime': QMetaType.Type.QDateTime}
    vl.dataProvider().addAttributes([QgsField(n, tp.get(t, QMetaType.Type.QString)) for n, t, _p, _w in schema.campos(tipo)])
    vl.updateFields()
    f = QgsFeature(vl.fields())
    for k, v in attrs.items():
        f[k] = v
    return f


def textos_legiveis(spec, f):
    """{nome do Texto: texto avaliado} das expressões [% %] da especificação, na feição."""
    ctx = contexto_formulario(f)
    return {el.nome: QgsExpression.replaceExpressionText(el.texto, ctx) for el, _c in spec.percorrer()
            if isinstance(el, esp.Texto) and '[%' in el.texto and el.nome != esp.NOME_PREVIA}  # a prévia é imagem (test_previa.py)


class TesteEspecificacao(unittest.TestCase):
    def test_registrados(self):
        for tipo in TIPOS:
            self.assertIn(tipo, esp.TIPOS_COM_FORMULARIO)
            self.assertIsNotNone(esp.formulario(tipo), tipo)

    def test_militar_conforme_o_construtor(self):
        spec = esp.formulario('military_symbol')
        self.assertEqual(len(retrato_construtor()), 11)
        self.assertEqual(divergencias_militar(spec), [])
        n = {c: len(esperado_militar(_sidc_do_conjunto(c)) & AMPLIFICADORES) for c in conjuntos()}
        MEDIDAS.append('amplificadores por conjunto (dock de antes: 16 em todos): {}'.format(n))
        # rótulos por dados medidos no construtor: Profundidade nos submarinos, Identificação AIS nos de superfície
        self.assertEqual(spec.campo('altitude_depth').rotulo_para({'sidc': _sidc_do_conjunto('35')}), 'Profundidade')
        self.assertEqual(spec.campo('type_amplifier').rotulo_para({'sidc': _sidc_do_conjunto('30')}), 'Identificação AIS')

    def test_regua_militar_reprova_especificacao_degradada(self):
        spec = esp.formulario('military_symbol')
        # pior caso 1: a condição real da Subordinação perde Equipamentos e Viaturas
        ruim = copy.deepcopy(spec)
        c = ruim.campo('higher_formation')
        tira = (c.condicao.valores | {'15'}) if c.condicao.negar else (c.condicao.valores - {'15'})
        c.condicao = fm.CondicaoConjunto(tira, c.condicao.negar)
        self.assertTrue(any(e[0] == _sidc_do_conjunto('15') for e in divergencias_militar(ruim)))
        # pior caso 2: a do Reforço com o lado trocado
        ruim = copy.deepcopy(spec)
        c = ruim.campo('reinforced_reduced')
        c.condicao = fm.CondicaoConjunto(c.condicao.valores, not c.condicao.negar)
        self.assertGreaterEqual(len(divergencias_militar(ruim)), 11)
        # pior caso 3: sem o rótulo por dados, os submarinos dizem Altitude
        ruim = copy.deepcopy(spec)
        ruim.campo('altitude_depth').rotulo_se = None
        self.assertTrue(any('altitude_depth' in e for e in divergencias_militar(ruim)))
        # pior caso 4: a Direção sem condição aparece nas Instalações
        ruim = copy.deepcopy(spec)
        ruim.campo('direction').condicao = None
        self.assertTrue(any(e[0] == _sidc_do_conjunto('20') for e in divergencias_militar(ruim)))

    def test_engenharia_e_declinacao_mantem_o_dock_de_antes(self):
        for tipo, attrs in (('engineering_symbol', {'point_code': '13'}), ('magnetic_declination', {})):
            spec = esp.formulario(tipo)
            vis = {c.coluna for c in spec.campos() if spec.visivel(c.coluna, attrs)}
            self.assertEqual(DOCK_ANTES[tipo] - vis, set(), tipo)
        # os 23 itens do C 5-36, na ordem do número, rotulados "N. título"
        mapa = esp.formulario('engineering_symbol').campo('point_code').widget.config['map']
        itens = fm.itens_engenharia()
        self.assertEqual(len(mapa), 23)
        self.assertEqual([list(d.values())[0] for d in mapa], [str(it['codigo']) for it in itens])
        self.assertIn('13. Vau', [list(d)[0] for d in mapa])

    def test_expressao_qgis_igual_a_regra_python(self):
        spec = esp.formulario('military_symbol')
        conds = condicoes(spec)
        self.assertGreaterEqual(len(conds), 12)
        for cond in conds:
            for sidc in AMOSTRAS_SIDC:
                f = feicao_memoria('military_symbol', {'sidc': sidc})
                ctx = QgsExpressionContext()
                ctx.setFeature(f)
                e = QgsExpression(cond.expressao())
                qg = bool(e.evaluate(ctx))
                self.assertFalse(e.hasEvalError(), e.evalErrorString())
                self.assertEqual(qg, cond.avaliar({'sidc': sidc}), (cond.expressao(), sidc))
        campo = spec.campo('altitude_depth')
        for conj in ('35', '10'):
            f = feicao_memoria('military_symbol', {'sidc': _sidc_do_conjunto(conj)})
            ctx = QgsExpressionContext()
            ctx.setFeature(f)
            self.assertEqual(QgsExpression(campo.expressao_rotulo()).evaluate(ctx), campo.rotulo_para({'sidc': _sidc_do_conjunto(conj)}))

    def test_textos_legiveis(self):
        spec = esp.formulario('military_symbol')
        t = time.perf_counter()
        txt = textos_legiveis(spec, feicao_memoria('military_symbol', {'sidc': SIDC_10}))['sidc_legivel']
        ms = (time.perf_counter() - t) * 1000
        self.assertEqual(txt.split('\n'), ['Identidade: Amigo', 'Conjunto: Unidades', 'Status: Posição atual ou confirmada',
                                           'Escalão: Batalhão', 'Ícone: Infantaria'])
        txt = textos_legiveis(spec, feicao_memoria('military_symbol', {'sidc': SIDC_15}))['sidc_legivel']
        self.assertIn('Mobilidade: Sobre lagartas', txt)
        self.assertIn('Identidade: Hostil', txt)
        self.assertEqual(textos_legiveis(spec, feicao_memoria('military_symbol', {'sidc': '123'}))['sidc_legivel'], fm.AVISO_SIDC)
        tamanho = len([el for el, _c in spec.percorrer() if isinstance(el, esp.Texto) and el.nome == 'sidc_legivel'][0].texto)
        MEDIDAS.append('texto legível do SIDC: {} caracteres de expressão, avaliado em {:.1f} ms'.format(tamanho, ms))
        spec = esp.formulario('engineering_symbol')
        eng = {'variant': 1, 'values': {'order': '7', 'material': 'R', 'access': 'both'}}
        txt = textos_legiveis(spec, feicao_memoria('engineering_symbol', {'point_code': '13', 'engineering': json.dumps(eng)}))
        linhas = txt['engenharia_legivel'].split('\n')
        self.assertEqual(linhas[0], 'Variante: Acesso difícil à esquerda')
        self.assertIn('Número de ordem: 7', linhas)
        self.assertIn('Material do fundo: R · rocha', linhas)
        self.assertIn('Acesso difícil: Nos dois lados', linhas)
        self.assertIn('Tipo de vau: V · viaturas', linhas)   # o padrão do catálogo quando falta
        self.assertEqual(len(linhas), 1 + len([it for it in fm.itens_engenharia() if it['codigo'] == '13'][0]['campos']))
        spec = esp.formulario('magnetic_declination')
        txt = textos_legiveis(spec, feicao_memoria('magnetic_declination', {'declination': -21.5, 'convergence': 0.25}))
        self.assertEqual(txt['angulo_quadricula'], 'Ângulo de quadrícula (NQ-NM): -21,75°')

    def test_toda_coluna_no_formulario_ou_oculta(self):
        for tipo in TIPOS:
            spec = esp.formulario(tipo)
            colunas = [c.coluna for c in spec.campos()]
            self.assertEqual(len(colunas), len(set(colunas)), tipo)
            esquema = set(schema.nomes_campos(tipo))
            self.assertFalse(set(colunas) & set(spec.ocultos), tipo)
            self.assertEqual(esquema - set(colunas) - set(spec.ocultos), set(), tipo)
            self.assertEqual(set(colunas) - esquema, set(), tipo)
            for c in spec.campos():
                self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, c.coluna)
                if c.rico:
                    self.assertIn(c.rico, ('sidc', 'engenharia'), c.coluna)
            self.assertIn('svg', spec.ocultos)
        self.assertEqual(esp.formulario('military_symbol').campo('sidc').restricao[0], fm.EXPRESSAO_SIDC_VALIDO)


# ---------------------------------------------------------------------------------------------
# Régua sem o plugin
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
from qgis.core import QgsApplication, QgsVectorLayer, QgsFieldConstraints
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
QgsGui.editorWidgetRegistry().initEditors()
FORTE = QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard
for tabela in ('military_symbol', 'engineering_symbol', 'magnetic_declination'):
    L = QgsVectorLayer(gp + '|layername=' + tabela, tabela, 'ogr')
    if plugin:
        from Calco import guardiao
        guardiao.garantir(L, tabela)
    r = res['camadas'][tabela] = {}
    fc = L.editFormConfig()
    nomes = L.fields().names()
    res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
    r['layout'] = fc.layout().name
    r['init'] = fc.initCodeSource().name
    r['init_codigo'] = len(fc.initCode() or '') + len(fc.initFunction() or '')
    r['ui'] = fc.uiForm()
    r['acoes'] = len(L.actions().actions())
    r['widgets'] = {n: L.editorWidgetSetup(i).type() for i, n in enumerate(nomes)}
    r['aliases'] = {n: L.attributeAlias(i) for i, n in enumerate(nomes)}
    r['restricoes'] = {n: [L.constraintExpression(i),
                           L.fields().at(i).constraints().constraintStrength(QgsFieldConstraints.Constraint.ConstraintExpression) == FORTE]
                       for i, n in enumerate(nomes) if L.constraintExpression(i)}
    r['tabela_ocultas'] = sorted(c.name for c in L.attributeTableConfig().columns() if c.hidden and c.name)
    res['etapa'] = 'estatico ' + tabela
    gravar()
    L.startEditing()
    r['formularios'] = {}
    for f in L.getFeatures():
        chave = f['nome']
        res['etapa'] = 'montando ' + chave
        gravar()
        t = time.perf_counter()
        form = QgsAttributeForm(L, f)
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        ms = (time.perf_counter() - t) * 1000
        form.resize(470, 640)
        form.show(); app.processEvents()
        tabs = form.findChildren(QTabWidget)
        abas, vis, rotulos, travados, imgs, falhando = [], set(), set(), {}, [], set()
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
                    if not wr.isValidConstraint():
                        falhando.add(n)
            rotulos |= {lb.text() for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text()}
            if pasta and chave in capturas:
                imgs.append(form.grab().toImage())
        salvo = form.save()
        mudou = {str(k): sorted(L.fields().at(i).name() for i in v) for k, v in L.editBuffer().changedAttributeValues().items()
                 if k == f.id()}
        # salvar com OUTRA mudança (o nome) não pode regravar o que o operador não tocou
        regravados = {}
        if not f['bloqueado']:
            for wr in form.findChildren(QgsEditorWidgetWrapper):
                if L.fields().at(wr.fieldIdx()).name() == 'nome':
                    wr.setValues(chave + ' renomeada', [])
                    wr.emitValueChanged()
            form.save()
            g = L.getFeature(f.id())
            for n in nomes:
                a, b = f[n], g[n]
                if n in ('nome', 'atualizado_em') or type(b).__name__ == 'QgsUnsetAttributeValue' or repr(a) == repr(b):
                    continue
                regravados[n] = [repr(a), repr(b)]
        r['formularios'][chave] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
                                   'travados': travados, 'salvo': salvo, 'mudou_ao_salvar': mudou,
                                   'restricao_falhando': sorted(falhando), 'regravados': regravados}
        if imgs:
            W = sum(im.width() for im in imgs) + 8 * (len(imgs) - 1)
            H = max(im.height() for im in imgs) + 26
            out = QImage(W, H, QImage.Format.Format_ARGB32); out.fill(QColor('white'))
            p = QPainter(out); x = 0
            p.setFont(QFont('Segoe UI', 10))
            p.drawText(4, 17, '{}: formulário nativo {} o plugin, uma imagem por aba visível; montado em {:.0f} ms'.format(
                chave, 'COM' if plugin else 'SEM', ms))
            for im in imgs:
                p.drawImage(x, 26, im); x += im.width() + 8
            p.end()
            out.save(os.path.join(pasta, 'nativo_{}_{}.png'.format(chave.replace(' ', '_'), 'com_plugin' if plugin else 'sem_plugin')))
        form.close(); form.deleteLater(); app.processEvents()
    L.rollBack()
res['etapa'] = 'fim'
gravar()
'''


def _exe():
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    return exe if os.path.exists(exe) else sys.executable


def rodar_sem_plugin(caminho, capturas=(), pasta='', com_plugin=False, timeout=180):
    script = os.path.join(TMP, 'sem_plugin_militar.py')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(SCRIPT)
    saida = os.path.join(TMP, 'res_{}.json'.format(uuid.uuid4().hex[:8]))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if com_plugin:
        env['EBGEO_PLUGIN'] = PLUGIN
    else:
        env.pop('EBGEO_PLUGIN', None)
    args = [_exe(), script, caminho, saida, pasta] + list(capturas)
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=TMP,
                         shell=args[0].endswith('.bat'))
    erro = b''
    try:
        _saida, erro = p.communicate(timeout=timeout)
        codigo = p.returncode
    except subprocess.TimeoutExpired:
        if os.name == 'nt':  # encerra só a árvore do processo que ESTE teste abriu
            subprocess.run(['taskkill', '/T', '/F', '/PID', str(p.pid)], capture_output=True)
        else:
            p.kill()
        p.communicate()
        codigo = 'tempo esgotado'
    res = {}
    if os.path.exists(saida):
        with open(saida, encoding='utf-8') as fh:
            res = json.load(fh)
    if codigo != 0:
        res['stderr'] = (erro or b'').decode('utf-8', 'replace')[-3000:]
    return res, codigo


# As feições do calco da régua: (tipo, nome, atributos)
FEICOES = [
    ('military_symbol', 'Militar 10', {'sidc': SIDC_10, 'unique_designation': '2', 'higher_formation': '4ª Bda Inf'}),
    # valores como o Web e a ferramenta gravam: rotação do arrasto, zoom do mapa, correção de zoom nula
    ('military_symbol', 'Militar 15', {'sidc': SIDC_15, 'type_amplifier': 'Guarani', 'rotation': 37.48291}),
    ('military_symbol', 'Militar 40', {'sidc': SIDC_40, 'date_time_group': '051200Z OUT', 'created_zoom': 13.456789123,
                                       'zoom_corr': None, 'size': 1.2, 'opacity': 0.85}),
    ('military_symbol', 'Militar 30', {'sidc': _sidc_do_conjunto('30')}),
    ('military_symbol', 'Militar bloqueado', {'sidc': SIDC_10, 'bloqueado': True}),
    ('engineering_symbol', 'Engenharia 13', {'point_code': '13',
                                             'engineering': {'variant': 1, 'values': {'order': '4', 'material': 'R'}}}),
    ('engineering_symbol', 'Engenharia 9', {'point_code': '9', 'engineering': {'variant': 0, 'values': {'class': '60', 'order': '12'}}}),
    ('magnetic_declination', 'Declinação', {'declination': -21.37, 'convergence': 0.42, 'inclination': -11.2,
                                            'intensity': 22950.0, 'calculation_date': '2026-10-05', 'size': 0.6}),
]
CAPTURAS = ('Militar 10', 'Militar 15', 'Militar 40', 'Engenharia 13', 'Engenharia 9', 'Declinação', 'Militar bloqueado')


def criar_calco(caminho, estilizar=True):
    gpkg.criar_calco(caminho, list(TIPOS))
    camadas = {}
    for tipo in TIPOS:
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
        idx = vl.fields().indexOf
        vl.startEditing()
        for k, (t, nome, extra) in enumerate(FEICOES):
            if t != tipo:
                continue
            a = dict(schema.padroes(tipo), ebgeo_id=str(uuid.uuid4()), nome=nome, created_zoom=13.0,
                     criado_em='2026-10-05T09:00:00+00:00', atualizado_em='2026-10-05T09:00:00+00:00')
            a.update(extra)
            a = {k: v for k, v in a.items() if v is not None}
            a.update(simbolos.renderizar(tipo, a))
            f = QgsFeature(vl.fields())
            for c, v in schema.atributos_para_qgis(tipo, a).items():
                if idx(c) >= 0:
                    f.setAttribute(idx(c), v)
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-47.9 + 0.01 * k, -15.8)))
            vl.addFeature(f)
        assert vl.commitChanges(), vl.commitErrors()
        if estilizar:
            C.aplicar_estilo(vl, tipo)
            C.salvar_estilo_padrao(vl)
        camadas[tipo] = vl
    return camadas


def esperados(tipo, nome, attrs):
    """Visíveis, rótulos e textos legíveis que a especificação manda mostrar para a feição."""
    spec = esp.formulario(tipo)
    vis = {c.coluna for c in spec.campos() if spec.visivel(c.coluna, attrs)}
    rotulos = {c.rotulo_para(attrs) for c in spec.campos() if c.coluna in vis}
    f = feicao_memoria(tipo, {k: (json.dumps(v) if isinstance(v, dict) else v) for k, v in attrs.items()})
    textos = set(textos_legiveis(spec, f).values())
    return vis, rotulos, textos


def reprovacoes(res, codigo):
    """Tudo o que reprova os formulários lidos sem o plugin; lista vazia é aprovação."""
    erros = []
    if codigo != 0:
        erros.append('processo saiu com {} na etapa {}: {}'.format(codigo, res.get('etapa'), res.get('stderr', '')))
    if not res:
        return erros + ['sem resultado']
    if res.get('modulos_ebgeo'):
        erros.append('o plugin estava carregado: {}'.format(res['modulos_ebgeo']))
    for tipo in TIPOS:
        spec = esp.formulario(tipo)
        r = (res.get('camadas') or {}).get(tipo)
        if not r:
            erros.append('{}: camada não lida'.format(tipo))
            continue
        if r.get('layout') != 'DragAndDrop':
            erros.append('{}: layout {}'.format(tipo, r.get('layout')))
        if r.get('init') != 'NoSource' or r.get('init_codigo') or r.get('ui') or r.get('acoes'):
            erros.append('{}: formulário com código'.format(tipo))
        for col, w in (r.get('widgets') or {}).items():
            if w not in esp.WIDGETS_NATIVOS:
                erros.append('{}: widget não nativo em {}: {}'.format(tipo, col, w))
        for c in spec.campos():
            if r['aliases'].get(c.coluna) != c.rotulo:
                erros.append('{}: alias de {}: {!r}'.format(tipo, c.coluna, r['aliases'].get(c.coluna)))
        restricoes = {c.coluna: [c.restricao[0], True] for c in spec.campos() if c.restricao}
        if r.get('restricoes') != restricoes:
            erros.append('{}: restrições {}'.format(tipo, r.get('restricoes')))
        if set(r.get('tabela_ocultas') or []) != set(spec.ocultos):
            erros.append('{}: ocultas na tabela {}'.format(tipo, r.get('tabela_ocultas')))
        so_leitura = {c.coluna for c in spec.campos() if c.somente_leitura}
        for t, nome, extra in FEICOES:
            if t != tipo:
                continue
            fo = r['formularios'].get(nome)
            if fo is None:
                erros.append('{}: formulário não montado'.format(nome))
                continue
            vis, rotulos, textos = esperados(tipo, nome, extra)
            if set(fo['visiveis']) != vis:
                erros.append('{}: visíveis a mais {} a menos {}'.format(nome, sorted(set(fo['visiveis']) - vis),
                                                                        sorted(vis - set(fo['visiveis']))))
            if not rotulos <= set(fo['rotulos']):
                erros.append('{}: rótulos ausentes {}'.format(nome, sorted(rotulos - set(fo['rotulos']))))
            if not textos <= set(fo['rotulos']):
                erros.append('{}: texto legível ausente {}'.format(nome, sorted(textos - set(fo['rotulos']))))
            bloqueada = bool(extra.get('bloqueado'))
            if (esp.AVISO_BLOQUEADA in fo['rotulos']) != bloqueada:
                erros.append('{}: aviso de bloqueio errado'.format(nome))
            for col, travado in fo['travados'].items():
                if travado != (bloqueada or col in so_leitura):
                    erros.append('{}: {} {}'.format(nome, col, 'travado' if travado else 'editável'))
            if not fo['salvo'] or fo['mudou_ao_salvar']:
                erros.append('{}: salvar sem mudar gravou {}'.format(nome, fo['mudou_ao_salvar']))
            if fo.get('regravados'):
                erros.append('{}: salvar o nome regravou {}'.format(nome, fo['regravados']))
            if fo.get('restricao_falhando'):  # valor válido reprovado: o formulário não grava nada
                erros.append('{}: restrição reprova o valor gravado em {}'.format(nome, fo['restricao_falhando']))
    return erros


def _degradar(nome, tipo, alterar):
    destino = os.path.join(TMP, 'pior_{}.gpkg'.format(nome))
    shutil.copy(TesteNativoSemPlugin.caminho, destino)
    vl = QgsVectorLayer(gpkg.uri_camada(destino, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
    alterar(vl)
    vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
    return destino


def _elementos(cont):
    from qgis.core import QgsAttributeEditorContainer
    for el in cont.children():
        yield el
        if isinstance(el, QgsAttributeEditorContainer):
            yield from _elementos(el)


class TesteNativoSemPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(TMP, 'calco_militar.gpkg')
        criar_calco(cls.caminho)
        cls.res, cls.codigo = rodar_sem_plugin(cls.caminho, CAPTURAS, SAIDA)
        cls.res_com, cls.codigo_com = rodar_sem_plugin(cls.caminho, CAPTURAS, SAIDA, com_plugin=True)

    def test_sem_plugin_confere_com_a_especificacao(self):
        erros = reprovacoes(self.res, self.codigo)
        self.assertEqual(erros, [], ' | '.join(erros))
        forms = {n: fo for r in self.res['camadas'].values() for n, fo in r['formularios'].items()}
        ms = sorted(f['ms'] for f in forms.values())
        MEDIDAS.append('sem o plugin: {} formulários montados, {:.0f} a {:.0f} ms; abas do militar: {}; da declinação: {}'.format(
            len(forms), ms[0], ms[-1], forms['Militar 10']['abas'], forms['Declinação']['abas']))
        self.assertEqual(forms['Militar 10']['abas'], ['Símbolo', 'Textos', 'Aparência', 'Avançado'])
        self.assertEqual(forms['Engenharia 13']['abas'], ['Símbolo', 'Aparência', 'Avançado'])
        n = {k: len(set(forms[k]['visiveis']) & AMPLIFICADORES) for k in ('Militar 10', 'Militar 15', 'Militar 40')}
        MEDIDAS.append('amplificadores no nativo sem o plugin: {}'.format(n))
        self.assertEqual(n, {'Militar 10': 12, 'Militar 15': 12, 'Militar 40': 4})
        self.assertIn('Identificação AIS', forms['Militar 30']['rotulos'])

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(self.codigo_com, 0, self.res_com.get('etapa'))
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        for tipo in TIPOS:
            for chave, fo in self.res['camadas'][tipo]['formularios'].items():
                com = self.res_com['camadas'][tipo]['formularios'][chave]
                self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos']), (com['abas'], com['visiveis'], com['rotulos']), chave)
        iguais = 0
        for chave in CAPTURAS:
            a = QImage(os.path.join(SAIDA, 'nativo_{}_sem_plugin.png'.format(chave.replace(' ', '_'))))
            b = QImage(os.path.join(SAIDA, 'nativo_{}_com_plugin.png'.format(chave.replace(' ', '_'))))
            self.assertFalse(a.isNull() or b.isNull(), chave)
            dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                      if a.pixel(x, y) != b.pixel(x, y))
            iguais += dif == 0
        MEDIDAS.append('capturas com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, len(CAPTURAS)))
        self.assertEqual(iguais, len(CAPTURAS))

    def test_pior_caso_condicao_de_amplificador_apagada_reprova(self):
        def apaga(vl):
            from qgis.core import QgsOptionalExpression
            fc = vl.editFormConfig()
            for el in _elementos(fc.invisibleRootContainer()):
                if el.name() == 'Conforme o símbolo: reinforced_reduced':
                    el.setVisibilityExpression(QgsOptionalExpression())
            vl.setEditFormConfig(fc)
        res, codigo = rodar_sem_plugin(_degradar('condicao', 'military_symbol', apaga))
        erros = reprovacoes(res, codigo)
        self.assertTrue(any(e.startswith('Militar 15: visíveis a mais') and 'reinforced_reduced' in e for e in erros), erros)

    def test_pior_caso_restricao_apagada_reprova(self):
        def apaga(vl):
            i = vl.fields().indexOf('sidc')
            vl.removeFieldConstraint(i, QgsFieldConstraints.Constraint.ConstraintExpression)
            vl.setConstraintExpression(i, '')
        res, codigo = rodar_sem_plugin(_degradar('restricao', 'military_symbol', apaga))
        erros = reprovacoes(res, codigo)
        self.assertTrue(any(e.startswith('military_symbol: restrições') for e in erros), erros)

    def test_pior_caso_restricao_que_ignora_o_padrao_do_provedor_reprova(self):
        """A restrição só pela expressão regular reprova o SIDC igual ao DEFAULT da coluna (medido)."""
        def so_regex(vl):
            i = vl.fields().indexOf('sidc')
            vl.setConstraintExpression(i, "regexp_match(coalesce(\"sidc\", ''), '^([0-9]{20}|[0-9]{30})$') > 0", fm.AVISO_SIDC)
        res, codigo = rodar_sem_plugin(_degradar('restricao_regex', 'military_symbol', so_regex))
        erros = reprovacoes(res, codigo)
        self.assertTrue(any(e.startswith('Militar 10: restrição reprova o valor gravado') for e in erros), erros)
        self.assertFalse(any(e.startswith('Militar 15: restrição reprova') for e in erros), erros)

    def test_pior_caso_numero_com_casas_cortadas_reprova(self):
        """O zoom de referência numa caixa de uma casa e sem nulo é regravado cortado ao salvar o nome."""
        def uma_casa(vl):
            from qgis.core import QgsEditorWidgetSetup
            # o grupo comum do piloto antes do conserto: uma casa, sem nulo, caixa sem estado nulo
            vl.setEditorWidgetSetup(vl.fields().indexOf('created_zoom'), QgsEditorWidgetSetup('Range', {
                'Style': 'SpinBox', 'Min': 0, 'Max': 22, 'Step': 0.1, 'Precision': 1, 'Suffix': '', 'AllowNull': False}))
            vl.setEditorWidgetSetup(vl.fields().indexOf('zoom_corr'), QgsEditorWidgetSetup('CheckBox', {
                'CheckedState': '', 'UncheckedState': '', 'TextDisplayMethod': 0, 'AllowNullState': False}))
        res, codigo = rodar_sem_plugin(_degradar('casas', 'military_symbol', uma_casa))
        erros = [e for e in reprovacoes(res, codigo) if e.startswith('Militar 40: salvar o nome regravou')]
        self.assertTrue(erros and 'created_zoom' in erros[0] and 'zoom_corr' in erros[0], reprovacoes(res, codigo))

    def test_pior_caso_texto_legivel_trocado_reprova(self):
        # o Python não desce o elemento de texto ao tipo dele: a degradação vai no QML salvo
        import re
        import sqlite3
        destino = os.path.join(TMP, 'pior_texto.gpkg')
        shutil.copy(self.caminho, destino)
        con = sqlite3.connect(destino)
        try:
            qml, = con.execute("SELECT styleQML FROM layer_styles WHERE f_table_name='engineering_symbol' AND useAsDefault").fetchone()
            # o texto do elemento vem depois do estilo do rótulo, como conteúdo do nó
            ruim, n = re.subn(r'(<attributeEditorTextElement[^>]*name="engenharia_legivel"[^>]*>.*?</labelStyle>)(.*?)'
                              r'(</attributeEditorTextElement>)', r'Variante e valores do item', qml, flags=re.S)
            self.assertEqual(n, 1)
            con.execute("UPDATE layer_styles SET styleQML=? WHERE f_table_name='engineering_symbol' AND useAsDefault", (ruim,))
            con.commit()
        finally:
            con.close()
        res, codigo = rodar_sem_plugin(destino)
        erros = reprovacoes(res, codigo)
        self.assertTrue(any(e.startswith('Engenharia 13: texto legível ausente') for e in erros), erros)


class TesteSalvarSoONome(unittest.TestCase):
    """Salvar só o nome pelo formulário nativo não muda nenhuma outra coluna nem um pixel do mapa."""

    def _render(self, camadas, arquivo):
        ms = QgsMapSettings()
        ms.setLayers(list(camadas.values()))
        crs = QgsCoordinateReferenceSystem('EPSG:3857')
        ms.setDestinationCrs(crs)
        ms.setOutputSize(QSize(900, 260))
        ms.setBackgroundColor(QColor(255, 255, 255))
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
        a, b = tr.transform(QgsPointXY(-47.91, -15.81)), tr.transform(QgsPointXY(-47.82, -15.79))
        ms.setExtent(QgsRectangle(a.x(), a.y(), b.x(), b.y()))
        img = QImage(QSize(900, 260), QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        job = QgsMapRendererCustomPainterJob(ms, p)
        job.start()
        job.waitForFinished()
        p.end()
        img.save(os.path.join(SAIDA, arquivo))
        return img

    def _pelo_nome(self, com_guardiao):
        caminho = os.path.join(TMP, 'so_nome_{}.gpkg'.format(com_guardiao))
        criar_calco(caminho)
        camadas = {t: QgsVectorLayer(gpkg.uri_camada(caminho, t), t, 'ogr') for t in TIPOS}
        for t, vl in camadas.items():
            C.aplicar_estilo(vl, t)  # o estilo salvo, com o formulário nativo
        antes = {t: {f.id(): {n: repr(f[n]) for n in vl.fields().names()} for f in vl.getFeatures()} for t, vl in camadas.items()}
        img0 = self._render(camadas, 'so_nome_antes_{}.png'.format('com' if com_guardiao else 'sem'))
        diferencas = []
        for t, vl in camadas.items():
            if com_guardiao:
                guardiao.garantir(vl, t)
            vl.startEditing()
            for f in list(vl.getFeatures()):
                if not f['bloqueado']:
                    pelo_formulario(vl, f.id(), {'nome': f['nome'] + ' renomeada'})
            self.assertTrue(vl.commitChanges(), vl.commitErrors())
            lida = QgsVectorLayer(vl.source(), t, 'ogr')
            for f in lida.getFeatures():
                for n in lida.fields().names():
                    if n not in ('nome', 'atualizado_em') and repr(f[n]) != antes[t][f.id()][n]:
                        diferencas.append('{} {}: {} {} -> {}'.format(t, f['nome'], n, antes[t][f.id()][n][:40], repr(f[n])[:40]))
        img1 = self._render(camadas, 'so_nome_depois_{}.png'.format('com' if com_guardiao else 'sem'))
        pixels = sum(1 for y in range(img0.height()) for x in range(img0.width()) if img0.pixel(x, y) != img1.pixel(x, y))
        MEDIDAS.append('salvar só o nome pelo nativo ({} o guardião): {} colunas mudadas, {} pixels diferentes'.format(
            'com' if com_guardiao else 'sem', len(diferencas), pixels))
        return diferencas, pixels

    def test_sem_o_plugin(self):
        diferencas, pixels = self._pelo_nome(False)
        self.assertEqual(diferencas, [])
        self.assertEqual(pixels, 0)

    def test_com_o_guardiao(self):
        diferencas, pixels = self._pelo_nome(True)
        self.assertEqual(diferencas, [])
        self.assertEqual(pixels, 0)


def expressao_divergente_antiga(tipo):
    """A régua de antes da cor sem caixa: a cor crua na assinatura (pior caso)."""
    a = simbolos.expressao_assinatura(tipo).replace('lower(coalesce(to_string("fill_color"), \'\'))',
                                                     'coalesce(to_string("fill_color"), \'\')')
    assert a != simbolos.expressao_assinatura(tipo)
    return ('CASE WHEN "svg" IS NOT NULL THEN coalesce("svg_assinatura", \'\') <> {a} '
            'ELSE "bitmap_b64" IS NULL END').format(a=a)


def hashlib_md5(texto):
    import hashlib
    return hashlib.md5(texto.encode('utf-8')).hexdigest()


class TesteCorSemCaixa(unittest.TestCase):
    """
    O widget nativo de cor regrava '#00B04E' como '#00b04e' ao salvar QUALQUER mudança. A
    assinatura leva a cor sem a caixa, e o desenho gravado antes (assinado com a cor do Web crua,
    em maiúsculas) segue em dia: salvar só o nome, sem o plugin, não acende o aviso nem muda pixel.
    """
    CASOS = [('coordination_measure', 'Destruição planejada', {'point_code': '271201', 'fill_color': '#00B04E'}),
             ('military_symbol', 'Militar cor alta', {'sidc': SIDC_15, 'fill_color': '#C0FFEE'})]

    def test_assinatura_sem_caixa(self):
        for tipo, _n, attrs in self.CASOS:
            baixa = dict(attrs, fill_color=attrs['fill_color'].lower())
            self.assertEqual(simbolos.assinatura(tipo, attrs), simbolos.assinatura(tipo, baixa))
            for a in (attrs, baixa):
                f = feicao_memoria(tipo, a)
                ctx = QgsExpressionContext()
                ctx.setFeature(f)
                self.assertEqual(QgsExpression(simbolos.expressao_assinatura(tipo)).evaluate(ctx), simbolos.assinatura(tipo, a))
            # o desenho assinado antes, com a cor crua em maiúsculas, segue em dia
            antiga = simbolos.assinaturas_aceitas(tipo, attrs) - {simbolos.assinatura(tipo, attrs)}
            self.assertEqual(len(antiga), 1)
            self.assertTrue(simbolos.assinatura_em_dia(tipo, dict(baixa, svg_assinatura=antiga.pop())))

    def _calco(self, assinatura_antiga):
        caminho = os.path.join(TMP, 'cor_{}.gpkg'.format(assinatura_antiga))
        gpkg.criar_calco(caminho, [t for t, _n, _a in self.CASOS])
        camadas = {}
        for k, (tipo, nome, extra) in enumerate(self.CASOS):
            vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), tipo, 'ogr')
            a = dict(schema.padroes(tipo), ebgeo_id=str(uuid.uuid4()), nome=nome, created_zoom=13.0)
            a.update(extra)
            a.update(simbolos.renderizar(tipo, a))
            if assinatura_antiga:  # como o importador gravava: a cor do Web crua na assinatura
                a['svg_assinatura'] = hashlib_md5(simbolos.texto_assinatura(tipo, a, 'alta'))
            f = QgsFeature(vl.fields())
            for c, v in schema.atributos_para_qgis(tipo, a).items():
                if vl.fields().indexOf(c) >= 0:
                    f.setAttribute(vl.fields().indexOf(c), v)
            if assinatura_antiga:  # o calco de antes da normalização guarda a cor do Web crua
                f.setAttribute(vl.fields().indexOf('fill_color'), extra['fill_color'])
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-47.9 + 0.006 * k, -15.8)))
            vl.startEditing()
            vl.addFeature(f)
            self.assertTrue(vl.commitChanges())
            C.aplicar_estilo(vl, tipo)
            camadas[tipo] = vl
        return camadas

    def _render(self, camadas, arquivo):
        ms = QgsMapSettings()
        ms.setLayers(list(camadas.values()))
        crs = QgsCoordinateReferenceSystem('EPSG:3857')
        ms.setDestinationCrs(crs)
        ms.setOutputSize(QSize(500, 260))
        ms.setBackgroundColor(QColor(255, 255, 255))
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
        a, b = tr.transform(QgsPointXY(-47.905, -15.803)), tr.transform(QgsPointXY(-47.889, -15.797))
        ms.setExtent(QgsRectangle(a.x(), a.y(), b.x(), b.y()))
        img = QImage(QSize(500, 260), QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        job = QgsMapRendererCustomPainterJob(ms, p)
        job.start()
        job.waitForFinished()
        p.end()
        img.save(os.path.join(SAIDA, arquivo))
        return img

    def _salvar_so_o_nome(self, assinatura_antiga):
        camadas = self._calco(assinatura_antiga)
        rotulo = 'antiga' if assinatura_antiga else 'nova'
        img0 = self._render(camadas, 'cor_{}_antes.png'.format(rotulo))
        colunas, divergentes, divergentes_antes = [], [], []
        for tipo, vl in camadas.items():
            antes = {f.id(): {n: f[n] for n in vl.fields().names()} for f in vl.getFeatures()}
            vl.startEditing()  # sem o guardião: o QGIS sem o plugin
            for fid in antes:
                pelo_formulario(vl, fid, {'nome': 'renomeada'})
            self.assertTrue(vl.commitChanges())
            lida = QgsVectorLayer(vl.source(), tipo, 'ogr')
            for f in lida.getFeatures():
                for n in lida.fields().names():
                    a, b = antes[f.id()][n], f[n]
                    if n in ('nome', 'atualizado_em') or repr(a) == repr(b):
                        continue
                    if n == 'fill_color' and assinatura_antiga and str(a).lower() == str(b).lower():
                        continue  # calco antigo: o widget põe a cor em minúsculas, o mesmo desenho
                    colunas.append('{} {}: {!r} -> {!r}'.format(tipo, n, a, b))
                ctx = QgsExpressionContext()
                ctx.setFeature(f)
                if QgsExpression(estilos_pontuais.expressao_divergente(tipo)).evaluate(ctx):
                    divergentes.append(tipo)
                if QgsExpression(expressao_divergente_antiga(tipo)).evaluate(ctx):
                    divergentes_antes.append(tipo)
                self.assertEqual(str(f['fill_color']), str(antes[f.id()]['fill_color']).lower())  # o widget regravou
        img1 = self._render(camadas, 'cor_{}_depois_do_nome.png'.format(rotulo))
        pixels = sum(1 for y in range(img0.height()) for x in range(img0.width()) if img0.pixel(x, y) != img1.pixel(x, y))
        MEDIDAS.append('cor em caixa alta, assinatura {}: salvar só o nome sem o plugin muda {} colunas e {} pixels; '
                       'aviso na régua nova em {}, na de antes em {}'.format(rotulo, len(colunas), pixels, divergentes,
                                                                            divergentes_antes))
        return colunas, pixels, divergentes, divergentes_antes

    def test_salvar_so_o_nome_com_a_assinatura_antiga(self):
        colunas, pixels, divergentes, antes = self._salvar_so_o_nome(True)
        self.assertEqual((colunas, pixels, divergentes), ([], 0, []))
        self.assertEqual(sorted(antes), sorted(t for t, _n, _a in self.CASOS))  # a régua de antes acendia o aviso

    def test_gravacao_normaliza_a_cor(self):
        """Ferramenta, dock e guardião (schema.atributos_para_qgis) e importador gravam a cor em minúsculas."""
        from Calco.ferramentas import gravar_feicao
        from Calco.importador import escritor
        self.assertEqual(schema.atributos_para_qgis('coordination_measure', {'fill_color': '#00B04E', 'attr_cor': '#ABC'}),
                         {'fill_color': '#00b04e', 'attr_cor': '#ABC'})
        caminho = os.path.join(TMP, 'cor_gravacao.gpkg')
        gpkg.criar_calco(caminho, ['coordination_measure'])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_measure'), 'm', 'ogr')
        a = dict(schema.padroes('coordination_measure'), ebgeo_id=str(uuid.uuid4()), point_code='271201', fill_color='#00B04E')
        gravar_feicao(vl, 'coordination_measure', QgsGeometry.fromPointXY(QgsPointXY(-47.9, -15.8)), a)
        self.assertEqual(QgsVectorLayer(vl.source(), 'r', 'ogr').getFeature(1)['fill_color'], '#00b04e')
        from osgeo import ogr
        ds = ogr.Open(caminho, 1)
        lyr = ds.GetLayerByName('coordination_measure')
        feat = escritor._novo_registro(lyr, {'fill_color': '#00B04E', 'nome': 'Imp'}, {'fill_color': 'str', 'nome': 'str'})
        self.assertEqual(feat.GetField('fill_color'), '#00b04e')
        ds = None

    def test_salvar_so_o_nome_com_a_assinatura_nova(self):
        colunas, pixels, divergentes, _antes = self._salvar_so_o_nome(False)
        self.assertEqual((colunas, pixels, divergentes), ([], 0, []))


# ---------------------------------------------------------------------------------------------
# Guardião: o SVG redesenhado em qualquer caminho
# ---------------------------------------------------------------------------------------------

def divergente(vl, fid):
    """O que o estilo avalia para o aviso vermelho (estilos_pontuais.expressao_divergente)."""
    tipo = C.tipo_da_camada(vl) if hasattr(C, 'tipo_da_camada') else None
    tipo = tipo or vl.customProperty('ebgeo_teste_tipo')
    ctx = QgsExpressionContext()
    ctx.setFeature(vl.getFeature(fid))
    return bool(QgsExpression(estilos_pontuais.expressao_divergente(tipo)).evaluate(ctx))


def camada_svg(nome, tipo, feicoes):
    caminho = os.path.join(TMP, nome + '.gpkg')
    gpkg.criar_calco(caminho, [tipo])
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
    vl.setCustomProperty('ebgeo_teste_tipo', tipo)
    idx = vl.fields().indexOf
    vl.startEditing()
    for k, extra in enumerate(feicoes):
        a = dict(schema.padroes(tipo), ebgeo_id=str(uuid.uuid4()), nome='{} {}'.format(nome, k),
                 atualizado_em='2026-10-05T09:00:00+00:00')
        a.update(extra)
        a.update(simbolos.renderizar(tipo, a))
        f = QgsFeature(vl.fields())
        for c, v in schema.atributos_para_qgis(tipo, a).items():
            if idx(c) >= 0:
                f.setAttribute(idx(c), v)
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-47.9 + 0.004 * k, -15.8)))
        vl.addFeature(f)
    assert vl.commitChanges()
    C.aplicar_estilo(vl, tipo)
    return vl


def render(vl, arquivo, rotulo):
    ms = QgsMapSettings()
    ms.setLayers([vl])
    crs = QgsCoordinateReferenceSystem('EPSG:3857')
    ms.setDestinationCrs(crs)
    ms.setOutputSize(QSize(420, 300))
    ms.setBackgroundColor(QColor(255, 255, 255))
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    c = tr.transform(QgsPointXY(-47.9, -15.8))
    ms.setExtent(QgsRectangle(c.x() - 600, c.y() - 430, c.x() + 600, c.y() + 430))
    img = QImage(QSize(420, 300), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start()
    job.waitForFinished()
    p.setPen(QColor(0, 0, 0))
    p.drawText(6, 16, rotulo)
    p.end()
    img.save(os.path.join(SAIDA, arquivo))
    return img


def vermelhos(img):
    """Pixels do vermelho do aviso (220, 0, 0) na imagem."""
    alvo = QColor(220, 0, 0).rgb()
    return sum(1 for y in range(20, img.height()) for x in range(img.width()) if img.pixel(x, y) == alvo)


class TesteGuardiaoSvg(unittest.TestCase):
    def _assinatura_em_dia(self, vl, fid, tipo):
        f = vl.getFeature(fid)
        attrs = {n: f[n] for n in f.fields().names()}
        self.assertEqual(f['svg_assinatura'], simbolos.assinatura(tipo, attrs))
        self.assertFalse(divergente(vl, fid))

    def test_sidc_pelo_formulario_nativo_redesenha_e_desfaz(self):
        vl = camada_svg('nativo', 'military_symbol', [{'sidc': SIDC_10}])
        g = guardiao.garantir(vl, 'military_symbol')
        self.assertIsNotNone(g, 'o guardião não vale para o Símbolo Militar')
        fid = next(vl.getFeatures()).id()
        svg0 = vl.getFeature(fid)['svg']
        antes = render(vl, 'guardiao_militar_0_antes.png', 'Antes: SIDC de Unidades (Infantaria)')
        vl.startEditing()
        n0 = vl.undoStack().count()
        sidc = SIDC_10 + '0760008192'  # 30 dígitos: elemento de comando (bit 13 da extensão 076)
        pelo_formulario(vl, fid, {'sidc': sidc})
        f = vl.getFeature(fid)
        self.assertEqual(f['sidc'], sidc)
        self.assertNotEqual(f['svg'], svg0)
        self._assinatura_em_dia(vl, fid, 'military_symbol')
        self.assertEqual(f['is_command'], regras.derivados_do_sidc(sidc)['is_command'])
        self.assertEqual(vl.undoStack().count(), n0 + 2)
        depois = render(vl, 'guardiao_militar_1_nativo.png', 'SIDC editado no formulário nativo, com o guardião')
        self.assertEqual(vermelhos(antes), 0)
        self.assertEqual(vermelhos(depois), 0)
        self.assertNotEqual(antes, depois)
        vl.undoStack().undo()   # o desenho e a regra, juntos
        self.assertEqual(vl.getFeature(fid)['svg'], svg0)
        self.assertTrue(divergente(vl, fid))  # o SIDC novo com o desenho velho
        vl.undoStack().undo()
        self.assertFalse(divergente(vl, fid))
        self.assertEqual(vl.undoStack().count(), n0 + 2)  # desfazer não redesenha
        vl.undoStack().redo()
        vl.undoStack().redo()
        self.assertTrue(vl.commitChanges())
        lida = QgsVectorLayer(vl.source(), 'r', 'ogr')
        lida.setCustomProperty('ebgeo_teste_tipo', 'military_symbol')
        self.assertFalse(divergente(lida, fid))
        self.assertEqual(lida.getFeature(fid)['sidc'], sidc)

    def test_nome_pelo_nativo_com_o_sidc_padrao_nao_acende_o_aviso(self):
        """Salvar o nome grava o SIDC igual ao DEFAULT da coluna como "valor padrão do provedor"."""
        for com_guardiao in (True, False):
            vl = camada_svg('padrao_{}'.format(com_guardiao), 'military_symbol', [{'sidc': SIDC_10}])
            if com_guardiao:
                guardiao.garantir(vl, 'military_symbol')
            fid = next(vl.getFeatures()).id()
            vl.startEditing()
            pelo_formulario(vl, fid, {'nome': 'outro nome'})
            sidc = vl.getFeature(fid)['sidc']
            if com_guardiao:
                self.assertEqual(sidc, SIDC_10)
                self.assertFalse(divergente(vl, fid))
            else:  # pior caso: o aviso vermelho acende no buffer, com o SIDC certo
                self.assertTrue(regras.nao_definido(sidc), repr(sidc))
                self.assertTrue(divergente(vl, fid))
            vl.rollBack()

    def test_pior_caso_sem_guardiao_fica_o_aviso(self):
        vl = camada_svg('nativo_sem', 'military_symbol', [{'sidc': SIDC_10}])
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pelo_formulario(vl, fid, {'sidc': SIDC_15})
        self.assertTrue(divergente(vl, fid))  # a régua acima reprovaria este estado
        img = render(vl, 'guardiao_militar_2_sem_guardiao.png', 'Pior caso: o mesmo SIDC sem o guardião')
        MEDIDAS.append('pior caso sem o guardião: {} pixels do vermelho do aviso'.format(vermelhos(img)))
        self.assertGreater(vermelhos(img), 50)
        vl.rollBack()

    def test_sidc_invalido_o_formulario_nao_grava(self):
        vl = camada_svg('invalido', 'military_symbol', [{'sidc': SIDC_10}])
        from Calco.formulario.nativo import aplicar_formulario
        aplicar_formulario(vl, 'military_symbol')
        guardiao.garantir(vl, 'military_symbol')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        try:
            pelo_formulario(vl, fid, {'sidc': '12345'})
        except AssertionError:
            pass
        self.assertEqual(vl.getFeature(fid)['sidc'], SIDC_10)
        self.assertFalse(divergente(vl, fid))
        vl.rollBack()

    def test_tabela_de_atributos_e_lote(self):
        vl = camada_svg('tabela', 'military_symbol', [{'sidc': SIDC_10}, {'sidc': SIDC_40}])
        g = guardiao.garantir(vl, 'military_symbol')
        fids = [f.id() for f in vl.getFeatures()]
        vl.startEditing()
        pela_tabela(vl, fids[0], 'sidc', SIDC_15)
        self.assertEqual(vl.getFeature(fids[0])['sidc'], SIDC_15)
        self._assinatura_em_dia(vl, fids[0], 'military_symbol')
        render(vl, 'guardiao_militar_3_tabela.png', 'SIDC editado na tabela de atributos, com o guardião')
        pela_tabela(vl, fids[0], 'unique_designation', 'ALFA')  # amplificador: redesenha
        self.assertIn('ALFA', simbolos.svg_de_coluna(vl.getFeature(fids[0])['svg']))
        n = g.regeneradas
        pela_tabela(vl, fids[1], 'size', 2.0)  # não desenha: nada a regravar
        self.assertEqual(g.regeneradas, n)
        # em lote, como a calculadora de campo: um comando, duas feições
        vl.beginEditCommand('Calculadora de campo')
        for fid in fids:
            vl.changeAttributeValue(fid, vl.fields().indexOf('fill_color'), '#00aa00')
        vl.endEditCommand()
        for fid in fids:
            self._assinatura_em_dia(vl, fid, 'military_symbol')
        vl.rollBack()

    def test_medida_e_declinacao(self):
        vl = camada_svg('medida', 'coordination_measure', [{'point_code': 'ECHELON'}])
        guardiao.garantir(vl, 'coordination_measure')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        vl.beginEditCommand('Calculadora de campo')
        vl.changeAttributeValue(fid, vl.fields().indexOf('tipo'), 'BRAVO')
        vl.endEditCommand()
        self._assinatura_em_dia(vl, fid, 'coordination_measure')
        vl.rollBack()
        vl = camada_svg('declinacao', 'magnetic_declination', [{'declination': -21.0, 'convergence': 0.4}])
        guardiao.garantir(vl, 'magnetic_declination')
        fid = next(vl.getFeatures()).id()
        svg0 = vl.getFeature(fid)['svg']
        vl.startEditing()
        vl.beginEditCommand('Calculadora de campo')
        vl.changeAttributeValue(fid, vl.fields().indexOf('declination'), -5.0)
        vl.endEditCommand()
        self.assertNotEqual(vl.getFeature(fid)['svg'], svg0)
        self._assinatura_em_dia(vl, fid, 'magnetic_declination')
        vl.rollBack()

    def test_engenharia_troca_de_item_volta_aos_padroes(self):
        vl = camada_svg('engenharia', 'engineering_symbol',
                        [{'point_code': '13', 'engineering': {'variant': 1, 'values': {'order': '9', 'material': 'R'}}}])
        guardiao.garantir(vl, 'engineering_symbol')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'point_code', '9')
        f = vl.getFeature(fid)
        eng = f['engineering']
        eng = json.loads(eng) if isinstance(eng, str) else dict(eng)
        self.assertEqual(eng, regras.rascunho_engenharia('9'))
        self.assertEqual(eng['values']['class'], '80')
        self._assinatura_em_dia(vl, fid, 'engineering_symbol')
        vl.rollBack()

    def test_colada_e_gravada_fora_de_comando(self):
        vl = camada_svg('colada', 'military_symbol', [{'sidc': SIDC_10}])
        guardiao.garantir(vl, 'military_symbol')
        vl.startEditing()
        # colar: feição nova sem desenho, dentro de um comando
        f = QgsFeature(vl.fields())
        for k, v in dict(schema.padroes('military_symbol'), sidc=SIDC_40, ebgeo_id=str(uuid.uuid4())).items():
            f[k] = v
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-47.89, -15.8)))
        vl.beginEditCommand('Colar feições')
        vl.addFeature(f)
        vl.endEditCommand()
        nova = [g for g in vl.getFeatures() if g['sidc'] == SIDC_40][0]
        self.assertIsNotNone(nova['svg'])
        self._assinatura_em_dia(vl, nova.id(), 'military_symbol')
        # gravação pela API fora de comando: o commit redesenha
        fid = [g for g in vl.getFeatures() if g['sidc'] == SIDC_10][0].id()
        vl.changeAttributeValue(fid, vl.fields().indexOf('sidc'), SIDC_15)
        self.assertTrue(divergente(vl, fid))
        self.assertTrue(vl.commitChanges())
        lida = QgsVectorLayer(vl.source(), 'r', 'ogr')
        lida.setCustomProperty('ebgeo_teste_tipo', 'military_symbol')
        for g in lida.getFeatures():
            self.assertFalse(divergente(lida, g.id()), g['sidc'])

    def test_bloqueada_nao_redesenha(self):
        vl = camada_svg('bloqueada', 'military_symbol', [{'sidc': SIDC_10, 'bloqueado': True}])
        g = guardiao.garantir(vl, 'military_symbol')
        fid = next(vl.getFeatures()).id()
        vl.startEditing()
        pela_tabela(vl, fid, 'sidc', SIDC_15)
        self.assertEqual(vl.getFeature(fid)['sidc'], SIDC_10)
        self.assertEqual(g.regeneradas, 0)
        self.assertFalse(divergente(vl, fid))
        vl.rollBack()


# ---------------------------------------------------------------------------------------------
# Dock
# ---------------------------------------------------------------------------------------------

class TesteDock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_dock_militar.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar()
        definir_calco_ativo(cls.calco)
        cls.construtor = []

        def construtor(feat, layer):
            return cls.construtor.pop(0) if cls.construtor else None
        cls.painel = PainelCalco(get_iface(), abrir_construtor_sidc=construtor)
        cls.painel.setParent(None)
        cls.painel.resize(440, 980)
        cls.painel.show()

    def tearDown(self):
        for tipo in TIPOS:
            lyr = self.calco.camada(tipo)
            if lyr.isEditable():
                lyr.rollBack()
        _app.processEvents()

    def _nova(self, tipo, **attrs):
        from Calco.ferramentas import gravar_feicao
        lyr = self.calco.camada(tipo)
        a = dict(schema.padroes(tipo), ebgeo_id=str(uuid.uuid4()), nome='{} do teste'.format(schema.TIPOS[tipo]['nome_pt']))
        a.update(attrs)
        eid = gravar_feicao(lyr, tipo, QgsGeometry.fromPointXY(QgsPointXY(-51.2, -30.0)), a)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        _app.processEvents()
        return lyr, eid

    def _disco(self, tipo, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, tipo), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _capturar(self, nome):
        self.painel.show()
        _app.processEvents()
        from Calco.ui.blocos.previa import esperar
        esperar(self.painel)  # a amostra do estilo desenha fora da interface
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def _textos(self):
        from qgis.PyQt.QtWidgets import QLabel
        return [lb.text() for lb in self.painel.form_host.findChildren(QLabel) if lb.isVisibleTo(self.painel.form_host)]

    def test_campos_conforme_o_sidc(self):
        olhados = DOCK_ANTES['military_symbol'] | AMPLIFICADORES
        for sidc, nome in ((SIDC_10, 'dock_militar_10.png'), (SIDC_15, 'dock_militar_15.png'), (SIDC_40, 'dock_militar_40.png'),
                           (_sidc_do_conjunto('35'), None), ('10039900001100000000', None)):
            self._nova('military_symbol', sidc=sidc)
            vis = self.painel.campos_visiveis()
            self.assertEqual(vis & olhados, esperado_militar(sidc), sidc)
            for col in AMPLIFICADORES - esperado_militar(sidc):
                self.assertTrue(self.painel.widgets[col].isHidden(), (sidc, col))
            legivel = textos_legiveis(esp.formulario('military_symbol'), feicao_memoria('military_symbol', {'sidc': sidc}))
            self.assertIn(legivel['sidc_legivel'], self._textos())
            if nome:
                self._capturar(nome)

    def test_sidc_no_buffer_redesenha_e_salva(self):
        lyr, eid = self._nova('military_symbol', sidc=SIDC_10)
        g = guardiao.guardiao_de(lyr)
        self.assertIsNotNone(g)
        svg0 = self._disco('military_symbol', eid)['svg']
        ed = self.painel.widgets['sidc'].findChild(type(self.painel.widgets['unique_designation']))
        ed.setText(SIDC_40)
        ed.editingFinished.emit()
        self.painel._gravar_pendentes()
        _app.processEvents()
        f = lyr.getFeature(self.painel.fid)
        self.assertEqual(f['sidc'], SIDC_40)
        self.assertNotEqual(f['svg'], svg0)
        attrs = {n: f[n] for n in f.fields().names()}
        self.assertEqual(f['svg_assinatura'], simbolos.assinatura('military_symbol', attrs))
        self.assertEqual(self._disco('military_symbol', eid)['sidc'], SIDC_10)  # nada no disco antes do Salvar
        self.assertEqual(self.painel.campos_visiveis() & AMPLIFICADORES, esperado_militar(SIDC_40) & AMPLIFICADORES)
        self.assertEqual(self.painel.estado_edicao.text(), 'Mudanças não salvas.')
        self._capturar('dock_militar_40_mudancas_nao_salvas.png')
        self.assertTrue(self.painel.salvar())
        d = self._disco('military_symbol', eid)
        self.assertEqual(d['sidc'], SIDC_40)
        self.assertEqual(d['svg_assinatura'], f['svg_assinatura'])

    def test_construtor_no_buffer(self):
        lyr, eid = self._nova('military_symbol', sidc=SIDC_10)
        self.construtor.append({'sidc': SIDC_15, 'type_amplifier': 'Guarani', 'special_modifier': None,
                                'is_command': False, 'fill_color': None, 'engagement_bar': None})
        self.painel._construtor(None)
        _app.processEvents()
        f = lyr.getFeature(self.painel.fid)
        self.assertEqual((f['sidc'], f['type_amplifier']), (SIDC_15, 'Guarani'))
        self.assertFalse(estilos_pontuais_divergente(lyr, f))
        self.assertEqual(self.painel.widgets['type_amplifier'].text(), 'Guarani')  # remontado
        self.assertTrue(self.painel.descartar())
        self.assertEqual(self._disco('military_symbol', eid)['sidc'], SIDC_10)

    def test_engenharia(self):
        import Calco.ui.seletor_engenharia as se

        class Falso:
            def __init__(self, *a, **k):
                pass

            def exec(self):
                return True

            def valores(self):
                return {'point_code': '13', 'engineering': json.dumps({'variant': 1, 'values': {'order': '5', 'material': 'S'}})}
        lyr, eid = self._nova('engineering_symbol', point_code='9')
        self._capturar('dock_engenharia_9.png')
        textos = self._textos()
        self.assertTrue(any(t.startswith('Classe da ponte: 80') for t in textos), textos)
        original = se.SeletorEngenharia
        se.SeletorEngenharia = Falso
        try:
            self.painel._seletor_engenharia()
        finally:
            se.SeletorEngenharia = original
        _app.processEvents()
        f = lyr.getFeature(self.painel.fid)
        self.assertEqual(f['point_code'], '13')
        self.assertFalse(estilos_pontuais_divergente(lyr, f))
        self.assertTrue(any('Material do fundo: S · areia' in t for t in self._textos()))
        self._capturar('dock_engenharia_13.png')
        self.assertEqual(self._disco('engineering_symbol', eid)['point_code'], '9')

    def test_declinacao_recalcular_no_buffer(self):
        from qgis.PyQt.QtWidgets import QPushButton
        lyr, eid = self._nova('magnetic_declination', declination=0.0, convergence=0.0)
        botoes = [b for b in self.painel.findChildren(QPushButton) if b.text() == 'Recalcular' and b.isVisibleTo(self.painel)]
        self.assertEqual(len(botoes), 1)
        botoes[0].click()
        _app.processEvents()
        f = lyr.getFeature(self.painel.fid)
        self.assertLess(f['declination'], -10)  # Porto Alegre, WMM2025: cerca de -17 graus
        self.assertFalse(estilos_pontuais_divergente(lyr, f))
        self.assertEqual(self._disco('magnetic_declination', eid)['declination'], 0.0)
        _app.processEvents()
        self.assertTrue(any(t.startswith('Ângulo de quadrícula (NQ-NM): -') for t in self._textos()))
        self._capturar('dock_declinacao_recalculada.png')

    def test_bloqueada(self):
        from qgis.PyQt.QtWidgets import QPushButton
        self._nova('magnetic_declination', bloqueado=True)
        botoes = [b for b in self.painel.findChildren(QPushButton) if b.text() == 'Recalcular' and b.isVisibleTo(self.painel)]
        self.assertTrue(botoes and not botoes[0].isEnabled())
        self._nova('military_symbol', sidc=SIDC_10, bloqueado=True)
        for col in ('sidc', 'unique_designation', 'size'):
            self.assertFalse(self.painel.widgets[col].isEnabled(), col)
        self.assertIn(esp.AVISO_BLOQUEADA, self._textos())


def estilos_pontuais_divergente(vl, f):
    ctx = QgsExpressionContext()
    ctx.setFeature(f)
    return bool(QgsExpression(estilos_pontuais.expressao_divergente(C.tipo_da_camada(vl))).evaluate(ctx))


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
