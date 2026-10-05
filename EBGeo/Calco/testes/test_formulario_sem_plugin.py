# -*- coding: utf-8 -*-
"""
Régua do formulário nativo assado no estilo (formulario/nativo.py), piloto da Linha de
Coordenação: o GeoPackage aberto num processo NOVO e SEM o plugin monta o QgsAttributeForm de
cada feição (sem queda e sem diálogo de confiança), e o que ele mostra confere com a
especificação para os 14 símbolos, o código desconhecido e a feição bloqueada: campos visíveis,
aliases, rótulo por dados, ocultos (também na tabela de atributos), só widgets nativos, nenhum
código (ação, função de inicialização), e salvar sem mudar não muda nada.

A régua é provada contra a saída REAL degradada, que ela tem de reprovar: o mesmo estilo com um
widget do plugin injetado (o QGIS sem o plugin cai, medido), com uma função de inicialização, e
com a condição de uma aba apagada. E o calco antigo (estilo do plugin sem formulário) ganha o
formulário ao abrir.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_sem_plugin.py
Variáveis: EBGEO_TESTE_SAIDA (pasta das capturas do formulário; padrão: temporária). Com
QT_QPA_PLATFORM=offscreen, o texto das capturas só sai legível com QT_QPA_FONTDIR apontando a
pasta de fontes do sistema.
"""
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

from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsVectorLayer, QgsEditorWidgetSetup, Qgis  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import calco as C, gpkg, schema, estilos_taticos as et  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_form_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []
CAPTURAS = ('290199', '140000', '140200', '240701', 'bloqueada')
ATTR = (('attr_capacidade', 'Capacidade', '400'), ('attr_agua_potavel', 'Água potável', 'sim'))

# Roda num processo novo, sem o caminho do plugin. argv: gpkg, json de saída, pasta de capturas ('' sem).
# Com EBGEO_PLUGIN apontando a pasta do plugin, o importa e liga o guardião (a captura "com o plugin").
SCRIPT = r'''
import sys, os, json, time
gp, saida, pasta = sys.argv[1:4]
res = {'etapa': 'inicio'}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
plugin = os.environ.get('EBGEO_PLUGIN')
if plugin:
    sys.path.insert(0, plugin)
from qgis.core import QgsApplication, QgsVectorLayer, QgsEditFormConfig, Qgis
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
QgsGui.editorWidgetRegistry().initEditors()
L = QgsVectorLayer(gp + '|layername=coordination_line', 'Linha de Coordenação', 'ogr')
if plugin:
    from Calco import guardiao
    guardiao.garantir(L, 'coordination_line')
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
tab = L.attributeTableConfig()
res['tabela_ocultas'] = sorted(c.name for c in tab.columns() if c.hidden and c.name)
res['etapa'] = 'estatico'
gravar()
L.startEditing()
feicoes = {}
for f in L.getFeatures():
    chave = 'bloqueada' if f['bloqueado'] else str(f['symbol_code'])
    feicoes.setdefault(chave, f)
res['formularios'] = {}
for chave, f in feicoes.items():
    res['etapa'] = 'montando ' + chave
    gravar()
    t = time.perf_counter()
    form = QgsAttributeForm(L, f)
    form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
    ms = (time.perf_counter() - t) * 1000
    form.resize(470, 600)
    form.show(); app.processEvents()
    tabs = form.findChildren(QTabWidget)
    abas, vis, rotulos, travados, imgs = [], set(), set(), {}, []
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
        rotulos |= {lb.text() for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text()}
        if pasta and chave in sys.argv[4:]:
            imgs.append(form.grab().toImage())
    salvo = form.save()
    mudou = {str(k): sorted(L.fields().at(i).name() for i in v) for k, v in L.editBuffer().changedAttributeValues().items()}
    res['formularios'][chave] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
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
res['etapa'] = 'fim'
gravar()
'''


def _exe():
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    return exe if os.path.exists(exe) else sys.executable


def rodar_sem_plugin(caminho, capturas=(), pasta='', com_plugin=False, timeout=120):
    """Roda o SCRIPT em processo novo. Devolve (resultado, código de saída ou 'tempo esgotado')."""
    script = os.path.join(TMP, 'sem_plugin.py')
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


def hachura_desenhada(layer):
    """
    A régua da hachura lida do ESTILO da camada: devolve f(atributos) -> o estilo desenha hachura.
    Junta a expressão "camada ligada" das camadas de padrão (linhas e pontos) de todos os símbolos
    do renderer e a avalia numa feição com os atributos dados (os demais nulos).
    """
    from qgis.core import (QgsExpression, QgsExpressionContext, QgsLinePatternFillSymbolLayer,
                           QgsPointPatternFillSymbolLayer, QgsRenderContext, QgsSymbolLayer)
    exprs = []
    for sym in layer.renderer().symbols(QgsRenderContext()):
        for sl in sym.symbolLayers():
            if isinstance(sl, (QgsLinePatternFillSymbolLayer, QgsPointPatternFillSymbolLayer)):
                p = sl.dataDefinedProperties().property(QgsSymbolLayer.Property.LayerEnabled)
                exprs.append(p.expressionString() if p.isActive() else 'TRUE')
    if not exprs:
        raise AssertionError('o estilo de {} não tem camada de hachura'.format(layer.name()))
    expressao = QgsExpression(' OR '.join('({})'.format(e) for e in exprs))
    campos = layer.fields()

    def desenha(atributos):
        f = QgsFeature(campos)
        for col, v in atributos.items():
            if campos.indexOf(col) >= 0:
                f.setAttribute(campos.indexOf(col), v)
        ctx = QgsExpressionContext()
        ctx.setFeature(f)
        v = expressao.evaluate(ctx)
        assert not expressao.hasEvalError(), expressao.evalErrorString()
        return bool(v)
    desenha.expressoes = exprs
    return desenha


# Passos ao vivo no formulário nativo, num processo novo SEM o plugin: abre a feição de nome dado,
# muda as colunas passo a passo pelo widget (como o operador) e anota, a cada passo, quais das
# colunas observadas estão à mostra na aba e os rótulos à mostra; captura a aba nos passos pedidos.
# argv: gpkg, json de saída, pasta; EBGEO_PASSOS no ambiente (json).
SCRIPT_PASSOS = r'''
import sys, os, json
gp, saida, pasta = sys.argv[1:4]
cfg = json.loads(os.environ['EBGEO_PASSOS'])
res = {'etapa': 'inicio', 'passos': []}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
from qgis.core import QgsApplication, QgsVectorLayer
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel
QgsGui.editorWidgetRegistry().initEditors()
L = QgsVectorLayer(gp + '|layername=' + cfg['camada'], cfg['camada'], 'ogr')
L.startEditing()
f = next(L.getFeatures('"nome" = \'{}\''.format(cfg['nome'])))
form = QgsAttributeForm(L, f)
form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
form.resize(470, 640); form.show(); app.processEvents()
tw = form.findChildren(QTabWidget)[0]
for k in range(tw.count()):
    if tw.tabText(k) == cfg['aba']:
        tw.setCurrentIndex(k)
app.processEvents()
wrappers = {L.fields().at(wr.fieldIdx()).name(): wr for wr in form.findChildren(QgsEditorWidgetWrapper)}
def vistos():
    return sorted(c for c in cfg['observar'] if c in wrappers and wrappers[c].widget().isVisibleTo(form))
def rotulos():
    return sorted(lb.text() for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text())
res['passos'].append({'passo': 'abrir', 'visiveis': vistos(), 'rotulos': rotulos()})
for k, (col, valor, captura) in enumerate(cfg['passos']):
    res['etapa'] = 'passo {}'.format(k)
    gravar()
    wrappers[col].setValues(valor, []); wrappers[col].emitValueChanged()
    app.processEvents()
    res['passos'].append({'passo': '{} = {}'.format(col, valor), 'visiveis': vistos(), 'rotulos': rotulos()})
    if captura and pasta:
        form.grab().save(os.path.join(pasta, captura))
res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
L.rollBack()
res['etapa'] = 'fim'
gravar()
'''


def rodar_passos(caminho, camada, nome, aba, observar, passos, pasta='', timeout=120):
    """Roda o SCRIPT_PASSOS sem o plugin. passos: [(coluna, valor, arquivo da captura ou '')]."""
    global SCRIPT
    original = SCRIPT
    SCRIPT = SCRIPT_PASSOS
    os.environ['EBGEO_PASSOS'] = json.dumps({'camada': camada, 'nome': nome, 'aba': aba, 'observar': list(observar),
                                             'passos': [list(p) for p in passos]}, ensure_ascii=False)
    try:
        return rodar_sem_plugin(caminho, (), pasta, timeout=timeout)
    finally:
        SCRIPT = original
        os.environ.pop('EBGEO_PASSOS', None)


def esperado(spec, chave, proprias):
    """Campos visíveis e rótulos que a especificação manda mostrar para a feição da chave."""
    attrs = {'symbol_code': '290199' if chave == 'bloqueada' else chave, 'bloqueado': chave == 'bloqueada'}
    vis = {c.coluna for c in spec.campos() if spec.visivel(c.coluna, attrs)} | set(proprias)
    rotulos = {c.rotulo_para(attrs) for c in spec.campos() if c.coluna in vis}
    return vis, rotulos, attrs


def reprovacoes(res, codigo, spec, proprias):
    """Tudo o que reprova o formulário lido sem o plugin; lista vazia é aprovação."""
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
        erros.append('formulário com código: init {} ({} caracteres), ui {!r}, {} ações'.format(
            res.get('init'), res.get('init_codigo'), res.get('ui'), res.get('acoes')))
    for col, tipo in (res.get('widgets') or {}).items():
        if tipo not in esp.WIDGETS_NATIVOS:
            erros.append('widget não nativo em {}: {}'.format(col, tipo))
    for c in spec.campos():
        if (res.get('aliases') or {}).get(c.coluna) != c.rotulo:
            erros.append('alias de {}: {!r}'.format(c.coluna, (res.get('aliases') or {}).get(c.coluna)))
    if set(res.get('tabela_ocultas') or []) != set(spec.ocultos):
        erros.append('ocultas na tabela: {}'.format(res.get('tabela_ocultas')))
    forms = res.get('formularios') or {}
    for chave in list(et.CATALOGO_LINHA) + ['999999', 'bloqueada']:
        if chave not in forms:
            erros.append('formulário de {} não montado'.format(chave))
            continue
        fo = forms[chave]
        vis, rotulos, attrs = esperado(spec, chave, proprias)
        if set(fo['visiveis']) != vis:
            erros.append('{}: visíveis a mais {} a menos {}'.format(
                chave, sorted(set(fo['visiveis']) - vis), sorted(vis - set(fo['visiveis']))))
        if not rotulos <= set(fo['rotulos']):
            erros.append('{}: rótulos ausentes {}'.format(chave, sorted(rotulos - set(fo['rotulos']))))
        if ('Cor do lado amigo' in fo['rotulos']) != (chave == '140200'):
            erros.append('{}: rótulo da cor errado'.format(chave))
        if (esp.AVISO_BLOQUEADA in fo['rotulos']) != (chave == 'bloqueada'):
            erros.append('{}: aviso de bloqueio errado'.format(chave))
        if (esp.AVISO_LADO_INIMIGO in fo['rotulos']) != (chave == '140200'):
            erros.append('{}: aviso do lado inimigo errado'.format(chave))
        so_leitura = {c.coluna for c in spec.campos() if c.somente_leitura}
        for col, travado in fo['travados'].items():
            deve = chave == 'bloqueada' or col in so_leitura
            if travado != deve:
                erros.append('{}: {} {}'.format(chave, col, 'travado' if travado else 'editável'))
        if not fo['salvo'] or fo['mudou_ao_salvar']:
            erros.append('{}: salvar sem mudar gravou {}'.format(chave, fo['mudou_ao_salvar']))
    return erros


def criar_calco(caminho):
    """Calco com uma Linha de Coordenação por símbolo, uma de código desconhecido, uma bloqueada e duas attr_."""
    gpkg.criar_calco(caminho, ['coordination_line'])
    from osgeo import ogr
    ds = ogr.Open(caminho, 1)
    lo = ds.GetLayerByName('coordination_line')
    for col, alias, _v in ATTR:
        fd = ogr.FieldDefn(col, ogr.OFTString)
        fd.SetAlternativeName(alias)
        lo.CreateField(fd)
    ds = None
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_line'), 'Linha de Coordenação', 'ogr')
    idx = vl.fields().indexOf
    vl.startEditing()
    for codigo in list(et.CATALOGO_LINHA) + ['999999', 'bloqueada']:
        a = dict(schema.padroes('coordination_line'))
        cod = '290199' if codigo == 'bloqueada' else codigo
        a.update(ebgeo_id=str(uuid.uuid4()), symbol_code=cod, nome='Linha {}'.format(codigo), created_zoom=13.0,
                 criado_em='2026-10-05T09:00:00+00:00', atualizado_em='2026-10-05T09:00:00+00:00',
                 color=et.CATALOGO_LINHA.get(cod, et.CATALOGO_LINHA[et.SIMBOLO_PADRAO])['cor'],
                 bloqueado=(codigo == 'bloqueada'))
        if cod == '140000':
            a.update(tipo='LCAF', identificacao='ALFA', gdh_ini='051200Z OUT', gdh_fim='061800Z OUT')
        if cod == '240701':
            a['numero_concentracao'] = 'AB0101'
        for col, _alias, v in ATTR:
            a[col] = v
        f = QgsFeature(vl.fields())
        for k, v in schema.atributos_para_qgis('coordination_line', a).items():
            if idx(k) >= 0:
                f.setAttribute(idx(k), v)
        f.setGeometry(QgsGeometry.fromWkt('LINESTRING(-47 -15, -46.9 -15.02)'))
        vl.addFeature(f)
    assert vl.commitChanges()
    return vl


def _qml_salvo(caminho):
    import sqlite3
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT styleQML, description FROM layer_styles WHERE f_table_name='coordination_line' "
                           "ORDER BY useAsDefault DESC, update_time DESC LIMIT 1").fetchone()
    finally:
        con.close()


def _degradar(nome, alterar):
    """Cópia do calco real com o estilo salvo degradado por `alterar(camada)`."""
    destino = os.path.join(TMP, 'pior_{}.gpkg'.format(nome))
    shutil.copy(TesteFormularioSemPlugin.caminho, destino)
    vl = QgsVectorLayer(gpkg.uri_camada(destino, 'coordination_line'), 'Linha de Coordenação', 'ogr')
    alterar(vl)
    vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
    return destino


class TesteFormularioSemPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario('coordination_line')
        cls.caminho = os.path.join(TMP, 'calco_form.gpkg')
        vl = criar_calco(cls.caminho)
        cls.proprias = [c for c, _a, _v in ATTR]
        t = time.perf_counter()
        C.aplicar_estilo(vl, 'coordination_line')
        t_estilo = time.perf_counter() - t
        from Calco.formulario.nativo import aplicar_formulario
        t = time.perf_counter()
        aplicar_formulario(vl, 'coordination_line')
        t_form = time.perf_counter() - t
        C.salvar_estilo_padrao(vl)
        qml, _d = _qml_salvo(cls.caminho)
        # o mesmo estilo sem o formulário, para medir o quanto ele pesa
        sem = os.path.join(TMP, 'sem_form.gpkg')
        criar_calco(sem)
        vs = QgsVectorLayer(gpkg.uri_camada(sem, 'coordination_line'), 'Linha de Coordenação', 'ogr')
        et.aplicar_estilo(vs, 'coordination_line')
        vs.saveStyleToDatabaseV2(vs.name(), 'sem formulário', True, '')
        qml_sem, _d = _qml_salvo(sem)
        MEDIDAS.append('estilo salvo: {} caracteres com o formulário, {} sem ({:+d}); aplicar o estilo {:.2f} s, '
                       'o formulário {:.1f} ms'.format(len(qml), len(qml_sem), len(qml) - len(qml_sem), t_estilo,
                                                       t_form * 1000))
        cls.res, cls.codigo = rodar_sem_plugin(cls.caminho, CAPTURAS, SAIDA)
        cls.res_com, cls.codigo_com = rodar_sem_plugin(cls.caminho, CAPTURAS, SAIDA, com_plugin=True)

    def test_sem_plugin_confere_com_a_especificacao(self):
        erros = reprovacoes(self.res, self.codigo, self.spec, self.proprias)
        self.assertEqual(erros, [], ' | '.join(erros))
        forms = self.res['formularios']
        ms = sorted(f['ms'] for f in forms.values())
        MEDIDAS.append('sem o plugin: {} formulários montados, {:.0f} a {:.0f} ms (mediana {:.0f}); abas da 140000: {}'.format(
            len(forms), ms[0], ms[-1], ms[len(ms) // 2], forms['140000']['abas']))
        self.assertEqual(forms['290199']['abas'], ['Símbolo', 'Aparência', 'Atributos', 'Avançado'])
        self.assertEqual(forms['140000']['abas'], ['Símbolo', 'Textos', 'Aparência', 'Atributos', 'Avançado'])
        self.assertIn('Capacidade', forms['290199']['rotulos'])
        self.assertIn('Água potável', forms['290199']['rotulos'])

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(self.codigo_com, 0, self.res_com.get('etapa'))
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        for chave, fo in self.res['formularios'].items():
            com = self.res_com['formularios'][chave]
            self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos']), (com['abas'], com['visiveis'], com['rotulos']), chave)
        from qgis.PyQt.QtGui import QImage
        iguais = 0
        for chave in CAPTURAS:
            a = QImage(os.path.join(SAIDA, 'nativo_{}_sem_plugin.png'.format(chave)))
            b = QImage(os.path.join(SAIDA, 'nativo_{}_com_plugin.png'.format(chave)))
            self.assertFalse(a.isNull() or b.isNull(), chave)
            # o cabeçalho escrito pelo teste difere (COM/SEM e o tempo); o formulário, abaixo dele, não
            dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                      if a.pixel(x, y) != b.pixel(x, y))
            iguais += dif == 0
        MEDIDAS.append('capturas com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, len(CAPTURAS)))
        self.assertEqual(iguais, len(CAPTURAS))

    def test_pior_caso_widget_do_plugin_reprova(self):
        def injeta(vl):
            vl.setEditorWidgetSetup(vl.fields().indexOf('tipo'), QgsEditorWidgetSetup('EBGeoSidc', {}))
        caminho = _degradar('widget', injeta)
        res, codigo = rodar_sem_plugin(caminho, timeout=90)
        erros = reprovacoes(res, codigo, self.spec, self.proprias)
        MEDIDAS.append('pior caso, widget do plugin no estilo: saída {}, etapa "{}", {} reprovações'.format(
            codigo, res.get('etapa'), len(erros)))
        self.assertTrue(any('widget não nativo em tipo' in e for e in erros), erros)

    def test_pior_caso_funcao_de_inicializacao_reprova(self):
        def injeta(vl):
            fc = vl.editFormConfig()
            fc.setInitCodeSource(Qgis.AttributeFormPythonInitCodeSource.Dialog)
            fc.setInitFunction('ebgeo_form_init')
            fc.setInitCode('def ebgeo_form_init(dialog, layer, feature):\n    pass\n')
            vl.setEditFormConfig(fc)
        caminho = _degradar('init', injeta)
        res, codigo = rodar_sem_plugin(caminho, timeout=45)
        erros = reprovacoes(res, codigo, self.spec, self.proprias)
        MEDIDAS.append('pior caso, função de inicialização: saída {}, etapa "{}", {} reprovações'.format(
            codigo, res.get('etapa'), len(erros)))
        self.assertTrue(any('formulário com código' in e for e in erros), erros)

    def test_pior_caso_condicao_apagada_reprova(self):
        def apaga(vl):
            from qgis.core import QgsOptionalExpression
            fc = vl.editFormConfig()
            for aba in fc.tabs():
                if aba.name() == 'Textos':
                    aba.setVisibilityExpression(QgsOptionalExpression())
            vl.setEditFormConfig(fc)
        caminho = _degradar('condicao', apaga)
        res, codigo = rodar_sem_plugin(caminho)
        erros = reprovacoes(res, codigo, self.spec, self.proprias)
        self.assertTrue(any(e.startswith('290199: visíveis a mais') for e in erros), erros)

    def test_calco_antigo_ganha_o_formulario_ao_abrir(self):
        """Estilo do plugin de antes do piloto (sem formulário, impressão só de simbologia e rótulos)."""
        import hashlib
        import re
        from qgis.core import QgsMapLayer, QgsReadWriteContext, QgsProject
        from qgis.PyQt.QtXml import QDomDocument
        caminho = os.path.join(TMP, 'antigo.gpkg')
        criar_calco(caminho)
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_line'), 'Linha de Coordenação', 'ogr')
        et.aplicar_estilo(vl, 'coordination_line')
        from Calco.importador.arvore import condicao_exibir, esconder_por_regra
        esconder_por_regra(vl, condicao_exibir())
        doc = QDomDocument()
        Cat = QgsMapLayer.StyleCategory
        vl.exportNamedStyle(doc, QgsReadWriteContext(), Cat.Symbology | Cat.Labeling)
        antiga = hashlib.md5(re.sub(r' (?:key|id)="\{[0-9a-fA-F-]{36}\}"', '', doc.toString()).encode('utf-8')).hexdigest()[:12]
        vl.saveStyleToDatabaseV2(vl.name(), '{} [{}]'.format(C.MARCA_ESTILO, antiga), True, '')
        antes, _ = rodar_sem_plugin(caminho)
        self.assertEqual(antes.get('layout'), 'AutoGenerated')
        calco = C.Calco(caminho)
        camadas = calco.carregar()
        self.assertEqual(calco.estilos['coordination_line'], 'atualizado')
        QgsProject.instance().removeMapLayers([l.id() for l in camadas.values()])
        depois, codigo = rodar_sem_plugin(caminho)
        self.assertEqual(reprovacoes(depois, codigo, self.spec, self.proprias), [])
        c2 = C.Calco(caminho)
        camadas = c2.carregar()
        self.assertEqual(c2.estilos['coordination_line'], 'em dia')
        QgsProject.instance().removeMapLayers([l.id() for l in camadas.values()])


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
