# -*- coding: utf-8 -*-
"""
Formulário da Área de Coordenação (formulario/tipos/area.py), nos 7 tipos do CATALOGO_AREA:
  - a especificação mostra, para cada tipo, o código desconhecido e o nulo, os campos que o dock
    mostrava antes dela (RETRATO_DOCK, medido no dock de 86f7d3b em 2026-10-05), e a expressão
    QGIS de cada condição dá o mesmo que a regra em Python;
  - o formulário nativo, aberto num processo NOVO e SEM o plugin, monta sem queda e sem código,
    só com widgets nativos, mostra os campos da especificação, os resumos de portões e minas já
    avaliados, a feição bloqueada só para leitura; salvar sem mudar não grava nada, e salvar uma
    mudança grava só ela: o JSON dos portões e das minas e os campos nulos ficam como estavam, e o
    desenho da camada sai igual pixel a pixel (imagens antes e depois);
  - com o plugin, o mesmo formulário (capturas idênticas);
  - o dock mostra os mesmos campos, com os editores ricos de portões e minas, e edita no buffer
    (Salvar e Descartar); a troca de tipo leva os padrões do tipo pela regra do guardião;
  - as regras de troca (regras.py) são funções puras e valem no formulário nativo e na tabela.
Cada régua é provada contra a saída real degradada, que ela tem de reprovar.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_area.py
Variáveis: EBGEO_TESTE_SAIDA (capturas e imagens; padrão: temporária). Com QT_QPA_PLATFORM=offscreen,
o texto das capturas só sai legível com QT_QPA_FONTDIR apontando a pasta de fontes do sistema.
"""
import copy
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, PLUGIN)
sys.path.insert(0, AQUI)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils,
    QgsFeature, QgsField, QgsFields, QgsGeometry, QgsMapRendererParallelJob, QgsMapSettings, QgsPointXY, QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType, QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from qgis.gui import QgsGui  # noqa: E402

QgsGui.editorWidgetRegistry().initEditors()

from Calco import calco as C, gpkg, schema, regras, guardiao, estilos_area as ea  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402
try:
    from Calco.formulario.tipos import area as fa  # noqa: E402
except ImportError:  # código de antes da especificação da área: cada teste reprova por si
    fa = None
import test_formulario_sem_plugin as tfs  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_form_area_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []

# ------------------------------------------------------------------ o retrato do dock de antes
# O dock de 86f7d3b (ui/painel_area.linhas_area) montado para uma feição de cada código, lidas as
# colunas dos widgets (o dock de antes só montava as linhas do tipo). As 23 da Área genérica:
BASE = frozenset({
    'nome', 'descricao', 'symbol_code', 'symbol_size_km', 'zoom_corr', 'created_zoom', 'line_color', 'line_width',
    'line_style', 'fill_color', 'opacity', 'hatch_type', 'hatch_spacing', 'hatch_line_width', 'tipo', 'identificacao',
    'gdh_ini', 'gdh_fim', 'outras_info', 'text_position', 'text_ratio', 'text_north_facing', 'text_size'})
VAB_A_MAIS = frozenset({'portoes', 'portoes_ocultos', 'altitude_max', 'altitude_min'})
RETRATO_DOCK = {
    '150000': BASE, '151100': BASE, '151199-01': BASE, '151203': BASE | {'escalao'}, '151000': BASE - {'line_style'},
    '170999-01': (BASE - {'outras_info'}) | VAB_A_MAIS, '270800': BASE | {'minas'}, '999999': BASE, None: BASE,
}
TODAS_ANTIGAS = frozenset().union(*RETRATO_DOCK.values())
# o rótulo da posição na borda é o do escalão só no Ponto Forte ('Posição do escalão na borda (%)')
ESCALAO_NO_ROTULO = {c: c == '151203' for c in RETRATO_DOCK}
# o que a especificação acrescenta ao dock de antes, em todo tipo
NOVAS_SEMPRE = frozenset({'visivel', 'ebgeo_id', 'mapa', 'camada_id', 'criado_em', 'atualizado_em', 'bloqueado'})


def colunas_do_dock(spec, attrs):
    """As colunas que o dock da especificação mostra: os campos e os editores ricos dos resumos."""
    vistas = set()
    for el, conds in spec.percorrer():
        campo = el if isinstance(el, esp.Campo) else getattr(el, 'campo_rico', None)
        if campo is not None and all(c.avaliar(attrs) for c in conds + ([campo.condicao] if campo.condicao else [])):
            vistas.add(campo.coluna)
    return vistas


def divergencias(spec):
    """[(código, esperado, obtido)] onde a especificação discorda do retrato do dock de antes."""
    erros = []
    for codigo, antigas in RETRATO_DOCK.items():
        attrs = {'symbol_code': codigo}
        vistas = colunas_do_dock(spec, attrs)
        if vistas & TODAS_ANTIGAS != antigas:
            erros.append((codigo, sorted(antigas - vistas), sorted((vistas & TODAS_ANTIGAS) - antigas)))
        if not NOVAS_SEMPRE <= vistas:
            erros.append((codigo, 'novas', sorted(NOVAS_SEMPRE - vistas)))
        rot = spec.campo('text_ratio').rotulo_para(attrs)
        if ('escalão' in rot) != ESCALAO_NO_ROTULO[codigo]:
            erros.append((codigo, 'rótulo', rot))
    return erros


def condicoes(spec):
    vistas = []
    for el, conds in spec.percorrer():
        extra = []
        if isinstance(el, esp.Campo) and el.rotulo_se:
            extra.append(el.rotulo_se[0])
        for c in conds + extra:
            if c not in vistas:
                vistas.append(c)
    return vistas


# ------------------------------------------------------------------ o calco de teste
QUADRA = [(-43.08, -22.92), (-43.04, -22.93), (-43.035, -22.90), (-43.075, -22.89)]
PORTOES = [{'ratio': 0.12, 'nome': 'PORTÃO ALFA'}, {'ratio': 0.4, 'nome': 'PORTÃO BRAVO'}]
MINAS = ['ac', 'ap', 'vazia']
ATTR = (('attr_capacidade', 'Capacidade', '400'),)
# chave (vai no nome) -> atributos; 'nulos' tem os campos que o desenho lê como padrão gravados nulos
FEICOES = {
    '150000': dict(symbol_code='150000', tipo='Obj', identificacao='BAGRE', outras_info='Outras info'),
    '151100': dict(symbol_code='151100', opacity=1.0, hatch_enabled=True, hatch_type='diagonal-right'),
    '151199-01': dict(symbol_code='151199-01', opacity=1.0, hatch_enabled=True, hatch_type='cross-diagonal'),
    '151203': dict(symbol_code='151203', escalao='II', line_width=5.0, tipo='PF', identificacao='1',
                   text_position='interna'),
    '151000': dict(symbol_code='151000', tipo='Obj', identificacao='3'),
    '170999-01': dict(symbol_code='170999-01', line_width=4.0, tipo='VAB', identificacao='CONDOR',
                      altitude_max='5000 ft', altitude_min='1500 ft', text_position='externa', portoes=PORTOES),
    '270800': dict(symbol_code='270800', line_color='#00B04E', fill_color='#00B04E', minas=MINAS, tipo='Obj'),
    '999999': dict(symbol_code='999999'),
    'bloqueada': dict(symbol_code='170999-01', bloqueado=True, portoes=PORTOES[:1]),
    # zoom de criação gravado: a Correção de Zoom nula (desenha ligada) muda o desenho se virar False
    'nulos': dict(symbol_code='151203', zoom_corr=None, text_ratio=None, text_position=None,
                  text_north_facing=None, visivel=None, escalao='X'),
    'sem_zoom': dict(symbol_code='150000', created_zoom=None, text_ratio=None, tipo='Obj'),
}
CAPTURAS = ('170999-01', '270800', '151203', '150000')


def criar_calco(caminho):
    gpkg.criar_calco(caminho, ['coordination_area'])
    from osgeo import ogr
    ds = ogr.Open(caminho, 1)
    lo = ds.GetLayerByName('coordination_area')
    for col, alias, _v in ATTR:
        fd = ogr.FieldDefn(col, ogr.OFTString)
        fd.SetAlternativeName(alias)
        lo.CreateField(fd)
    ds = None
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_area'), 'Área de Coordenação', 'ogr')
    idx = vl.fields().indexOf
    vl.startEditing()
    for k, (chave, extra) in enumerate(FEICOES.items()):
        a = dict(schema.padroes('coordination_area'))
        a.update(ebgeo_id=str(uuid.uuid4()), nome=chave, created_zoom=12.0, symbol_size_km=0.3,
                 criado_em='2026-10-05T09:00:00+00:00', atualizado_em='2026-10-05T09:00:00+00:00')
        a.update(extra)
        for col, _alias, v in ATTR:
            a[col] = v
        f = QgsFeature(vl.fields())
        for col, v in schema.atributos_para_qgis('coordination_area', a).items():
            if idx(col) >= 0:
                f.setAttribute(idx(col), v)
        dx, dy = (k % 5) * 0.07, (k // 5) * -0.06
        f.setGeometry(QgsGeometry.fromMultiPolygonXY([[[QgsPointXY(x + dx, y + dy) for x, y in QUADRA + [QUADRA[0]]]]]))
        vl.addFeature(f)
    assert vl.commitChanges(), vl.commitErrors()
    return vl


def linhas_cruas(caminho):
    """{nome: {coluna: valor}} como está no arquivo, sem QGIS nem OGR no meio."""
    con = sqlite3.connect(caminho)
    try:
        cur = con.execute('SELECT * FROM coordination_area')
        nomes = [d[0] for d in cur.description]
        return {r[nomes.index('nome')]: dict(zip(nomes, r)) for r in cur.fetchall()}
    finally:
        con.close()


def mudancas_cruas(antes, depois, ignorar=('nome', 'atualizado_em')):
    """{feição: {coluna: (antes, depois)}}, com a cor comparada sem caixa (o GeoPackage a guarda em minúsculas)."""
    out = {}
    for chave, a in antes.items():
        d = depois.get(chave) or depois.get(chave + ' editada') or {}
        for col, va in a.items():
            if col in ignorar or col == 'geom':
                continue
            vd = d.get(col)
            if isinstance(va, str) and isinstance(vd, str) and va.startswith('#') and va.lower() == vd.lower():
                continue
            if va != vd:
                out.setdefault(chave, {})[col] = (va, vd)
    return out


def renderizar(caminho, arquivo=None):
    """A camada reaberta do GeoPackage (o estilo vem do layer_styles), desenhada como no canvas."""
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_area'), 'r', 'ogr')
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(1000, 560))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    from qgis.core import QgsCoordinateTransform
    ext = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance()).transformBoundingBox(vl.extent())
    ms.setExtent(ext.buffered(ext.width() * 0.05))
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.globalScope())
    ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    if arquivo:
        img.save(os.path.join(SAIDA, arquivo))
    return img


def cor(vl, fid, col='line_color'):
    """A cor como o buffer a tem: o formulário pode deixar QColor ou o marcador de não definido."""
    v = vl.getFeature(fid)[col]
    if regras.nao_definido(v):
        v = v.defaultValueClause()
    return str(regras.valor(v)).lower()


def pixels_diferentes(a, b):
    return sum(1 for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y))


# ------------------------------------------------------------------ o formulário nativo sem o plugin
# Processo novo, sem o caminho do plugin (com EBGEO_PLUGIN, importa o plugin e liga o guardião).
# argv: gpkg, json de saída, pasta de capturas ('' sem), chaves a capturar.
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
from qgis.core import QgsApplication, QgsVectorLayer
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
QgsGui.editorWidgetRegistry().initEditors()
L = QgsVectorLayer(gp + '|layername=coordination_area', 'Área de Coordenação', 'ogr')
if plugin:
    from Calco import guardiao
    guardiao.garantir(L, 'coordination_area')
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
d = L.defaultValueDefinition(L.fields().indexOf('hatch_enabled'))
res['padrao_hachura'] = [d.expression(), d.applyOnUpdate()]
res['tabela_ocultas'] = sorted(c.name for c in L.attributeTableConfig().columns() if c.hidden and c.name)
res['etapa'] = 'estatico'
gravar()
L.startEditing()
res['formularios'] = {}

def montar(f):
    form = QgsAttributeForm(L, f)
    form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
    return form

for f in L.getFeatures():
    chave = f['nome']
    res['etapa'] = 'montando ' + chave
    gravar()
    t = time.perf_counter()
    form = montar(f)
    ms = (time.perf_counter() - t) * 1000
    form.resize(470, 640)
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
        if pasta and chave in sys.argv[4:]:
            imgs.append(form.grab().toImage())
    salvo = form.save()
    sem_mudar = sorted(L.fields().at(i).name() for i in L.editBuffer().changedAttributeValues().get(f.id(), {}))
    form.close(); form.deleteLater(); app.processEvents()
    com_mudanca = {}
    if chave != 'bloqueada':
        # salvar UMA mudança (o nome) pelo formulário: o que mais ele grava?
        form = montar(L.getFeature(f.id()))
        for wr in form.findChildren(QgsEditorWidgetWrapper):
            if L.fields().at(wr.fieldIdx()).name() == 'nome':
                wr.setValues(chave + ' editada', []); wr.emitValueChanged()
        form.save()
        mud = L.editBuffer().changedAttributeValues().get(f.id(), {})
        # o marcador de "não definido" (texto vazio) não é gravação
        com_mudanca = {L.fields().at(i).name(): repr(v) for i, v in mud.items() if type(v).__name__ != 'QgsUnsetAttributeValue'}
        form.close(); form.deleteLater(); app.processEvents()
    res['formularios'][chave] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
                                 'travados': travados, 'salvo': salvo, 'mudou_ao_salvar': sem_mudar,
                                 'mudou_com_nome': com_mudanca}
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
        out.save(os.path.join(pasta, 'nativo_area_{}_{}.png'.format(chave, 'com_plugin' if plugin else 'sem_plugin')))
res['etapa'] = 'gravando'
gravar()
res['commit'] = L.commitChanges()
res['etapa'] = 'fim'
gravar()
'''


def rodar(caminho, capturas=(), pasta='', com_plugin=False, timeout=180):
    """Roda o SCRIPT sobre uma CÓPIA do calco (ele grava). Devolve (resultado, código, cópia)."""
    import shutil
    copia = os.path.join(TMP, 'rodada_{}.gpkg'.format(uuid.uuid4().hex[:8]))
    shutil.copy(caminho, copia)
    original = tfs.SCRIPT
    tfs.SCRIPT = SCRIPT
    try:
        res, codigo = tfs.rodar_sem_plugin(copia, capturas, pasta, com_plugin=com_plugin, timeout=timeout)
    finally:
        tfs.SCRIPT = original
    return res, codigo, copia


def esperado(spec, chave):
    attrs = dict(FEICOES[chave])
    campos = {c.coluna for c in spec.campos() if spec.visivel(c.coluna, attrs)}
    rotulos = {c.rotulo_para(attrs) for c in spec.campos() if c.coluna in campos} | {a for _c, a, _v in ATTR}
    return campos | {c for c, _a, _v in ATTR}, rotulos, attrs


# o que o formulário grava a mais ao salvar outra mudança, sem mudar o valor: a cor volta como
# QColor, hatch_enabled sai do valor padrão na atualização (o mesmo), atualizado_em se renova
REGRAVADOS_SEM_EFEITO = {'line_color', 'fill_color', 'hatch_enabled', 'atualizado_em', 'nome'}


def reprovacoes(res, codigo, spec):
    """Tudo o que reprova o formulário nativo lido sem o plugin; lista vazia é aprovação."""
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
    if res.get('padrao_hachura') != [ea.EXPRESSAO_HACHURA_LIGADA, True]:
        erros.append('hatch_enabled sem o valor padrão na atualização: {}'.format(res.get('padrao_hachura')))
    forms = res.get('formularios') or {}
    for chave in FEICOES:
        if chave not in forms:
            erros.append('formulário de {} não montado'.format(chave))
            continue
        fo = forms[chave]
        vis, rotulos, attrs = esperado(spec, chave)
        if set(fo['visiveis']) != vis:
            erros.append('{}: visíveis a mais {} a menos {}'.format(
                chave, sorted(set(fo['visiveis']) - vis), sorted(vis - set(fo['visiveis']))))
        if not rotulos <= set(fo['rotulos']):
            erros.append('{}: rótulos ausentes {}'.format(chave, sorted(rotulos - set(fo['rotulos']))))
        if any('[%' in r for r in fo['rotulos']):
            erros.append('{}: expressão sem avaliar'.format(chave))
        codigo_ = regras.codigo_area(attrs.get('symbol_code'))
        portoes = [r for r in fo['rotulos'] if r.startswith('Portões: ')]
        minas = [r for r in fo['rotulos'] if r.startswith('Minas, posições')]
        if codigo_ == '170999-01':
            nomes = [g['nome'] for g in attrs.get('portoes', [])]
            if len(portoes) != 1 or not all(n in portoes[0] for n in nomes) or ('a 12 %' not in portoes[0]):
                erros.append('{}: resumo dos portões {}'.format(chave, portoes))
        elif portoes:
            erros.append('{}: resumo dos portões fora do VAB'.format(chave))
        if codigo_ == '270800':
            if minas != ['Minas, posições 1, 2 e 3: Anticarro, Antipessoal, Vazia. ' + fa.AVISO_EDITAR_NO_PAINEL]:
                erros.append('{}: resumo das minas {}'.format(chave, minas))
        elif minas:
            erros.append('{}: resumo das minas fora da Área minada'.format(chave))
        if (esp.AVISO_BLOQUEADA in fo['rotulos']) != (chave == 'bloqueada'):
            erros.append('{}: aviso de bloqueio errado'.format(chave))
        so_leitura = {c.coluna for c in spec.campos() if c.somente_leitura}
        for col, travado in fo['travados'].items():
            if travado != (chave == 'bloqueada' or col in so_leitura):
                erros.append('{}: {} {}'.format(chave, col, 'travado' if travado else 'editável'))
        if not fo['salvo'] or fo['mudou_ao_salvar']:
            erros.append('{}: salvar sem mudar gravou {}'.format(chave, fo['mudou_ao_salvar']))
        a_mais = set(fo['mudou_com_nome']) - REGRAVADOS_SEM_EFEITO
        if a_mais:
            erros.append('{}: salvar o nome gravou também {}'.format(
                chave, {c: fo['mudou_com_nome'][c] for c in sorted(a_mais)}))
    if not res.get('commit'):
        erros.append('o calco não foi gravado')
    return erros


def reprovacoes_disco(antes, depois, img_antes, img_depois):
    """O arquivo depois de salvar o nome pelo formulário: só o nome (e a data) mudam, e o desenho não."""
    erros = ['{}: {}'.format(k, v) for k, v in sorted(mudancas_cruas(antes, depois).items())]
    if set(depois) != {k if k == 'bloqueada' else k + ' editada' for k in antes}:
        erros.append('nomes no disco: {}'.format(sorted(depois)))
    dif = pixels_diferentes(img_antes, img_depois)
    if dif:
        erros.append('o desenho mudou em {} pixels'.format(dif))
    return erros


class TesteEspecificacaoArea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario('coordination_area')

    def test_retrato_cobre_o_catalogo(self):
        self.assertEqual(set(RETRATO_DOCK) - {'999999', None}, set(ea.CATALOGO_AREA))
        self.assertEqual(len(ea.CATALOGO_AREA), 7)
        self.assertIn('coordination_area', esp.TIPOS_COM_FORMULARIO)

    def test_campos_conforme_o_dock_de_antes(self):
        self.assertEqual(divergencias(self.spec), [])

    def test_regua_reprova_especificacao_degradada(self):
        # pior caso 1: o estilo da borda perde a condição (aparece na Zona fortificada)
        ruim = copy.deepcopy(self.spec)
        ruim.campo('line_style').condicao = None
        self.assertTrue(any(e[0] == '151000' for e in divergencias(ruim)))
        # pior caso 2: outras_info com o lado trocado (some fora do VAB e aparece nele)
        ruim = copy.deepcopy(self.spec)
        c = ruim.campo('outras_info')
        c.condicao = esp.Condicao(c.condicao.coluna, c.condicao.valores, not c.condicao.negar)
        self.assertEqual(len(divergencias(ruim)), len(RETRATO_DOCK))
        # pior caso 3: o grupo dos portões sem condição mostra o editor em todos os tipos
        ruim = copy.deepcopy(self.spec)
        for el in ruim.abas[0].filhos:
            if isinstance(el, esp.Grupo) and el.nome == 'Portões':
                el.condicao = None
        self.assertTrue(any(e[0] == '150000' for e in divergencias(ruim)))
        # pior caso 4: o rótulo do escalão some
        ruim = copy.deepcopy(self.spec)
        ruim.campo('text_ratio').rotulo_se = None
        self.assertTrue(any(e[0] == '151203' for e in divergencias(ruim)))

    def test_expressao_qgis_igual_a_regra_python(self):
        conds = condicoes(self.spec)
        self.assertGreaterEqual(len(conds), 6)
        campos = QgsFields()
        campos.append(QgsField('symbol_code', QMetaType.Type.QString))
        campos.append(QgsField('bloqueado', QMetaType.Type.Bool))
        for cond in conds:
            for codigo in list(RETRATO_DOCK) + ['']:
                for bloq in (None, False, True):
                    f = QgsFeature(campos)
                    f.setAttributes([codigo, bloq])
                    ctx = QgsExpressionContext()
                    ctx.setFeature(f)
                    e = QgsExpression(cond.expressao())
                    qg = bool(e.evaluate(ctx))
                    self.assertFalse(e.hasEvalError(), e.evalErrorString())
                    self.assertEqual(qg, cond.avaliar({'symbol_code': codigo, 'bloqueado': bloq}), (cond.expressao(), codigo))

    def test_toda_coluna_no_formulario_ou_oculta_e_so_nativos(self):
        nas_abas = [c.coluna for c in self.spec.campos()]
        self.assertEqual(len(nas_abas), len(set(nas_abas)))
        esquema = set(schema.nomes_campos('coordination_area'))
        self.assertEqual(esquema - set(nas_abas) - set(self.spec.ocultos), set())
        self.assertFalse(set(nas_abas) & set(self.spec.ocultos))
        for c in self.spec.campos():
            self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, c.coluna)
            if c.widget.tipo == 'CheckBox':
                self.assertTrue(c.widget.config.get('AllowNullState'), c.coluna)
            self.assertNotEqual(c.widget.tipo, 'Range', c.coluna)  # corta e arredonda ao salvar (esp.numero)
        # as listas JSON só aparecem como resumo no nativo, com o editor rico no dock
        ricos = {el.campo_rico.coluna: el.campo_rico.rico for el, _c in self.spec.percorrer() if isinstance(el, fa.Resumo)}
        self.assertEqual(ricos, {'portoes': 'area_portoes', 'minas': 'area_minas'})
        self.assertTrue({'portoes', 'minas'} <= set(self.spec.ocultos))

    def test_resumos_avaliados_pelo_qgis(self):
        campos = QgsFields()
        campos.append(QgsField('portoes', QMetaType.Type.QString))
        campos.append(QgsField('minas', QMetaType.Type.QString))
        casos = [
            (json.dumps(PORTOES, ensure_ascii=False), None, 'PORTÃO ALFA a 12 %, PORTÃO BRAVO a 40 %', 'Qualquer tipo, Antipessoal, Anticarro'),
            (PORTOES, MINAS, 'PORTÃO ALFA a 12 %, PORTÃO BRAVO a 40 %', 'Anticarro, Antipessoal, Vazia'),
            ('[]', json.dumps(MINAS), 'nenhum', 'Anticarro, Antipessoal, Vazia'),
            (None, '["ap"]', 'nenhum', 'Qualquer tipo, Antipessoal, Anticarro'),
        ]
        from Calco.estilos_area import expr_lista_json
        for portoes, minas, esp_p, esp_m in casos:
            f = QgsFeature(campos)
            f.setAttributes([portoes, minas])
            ctx = QgsExpressionContext()
            ctx.setFeature(f)
            p = QgsExpression(fa.expr_resumo_portoes(expr_lista_json('portoes'))).evaluate(ctx)
            m = QgsExpression(fa.expr_resumo_minas(expr_lista_json('minas'), ea.TIPOS_MINA)).evaluate(ctx)
            self.assertEqual((p, m), (esp_p, esp_m), (portoes, minas))


class TesteNativoArea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario('coordination_area')
        cls.caminho = os.path.join(TMP, 'calco_area.gpkg')
        vl = criar_calco(cls.caminho)
        C.aplicar_estilo(vl, 'coordination_area')
        C.salvar_estilo_padrao(vl)
        cls.antes = linhas_cruas(cls.caminho)
        cls.img_antes = renderizar(cls.caminho, 'area_antes_de_salvar_pelo_nativo.png')
        cls.res, cls.codigo, cls.depois_caminho = rodar(cls.caminho, CAPTURAS, SAIDA)
        cls.depois = linhas_cruas(cls.depois_caminho)
        cls.img_depois = renderizar(cls.depois_caminho, 'area_depois_de_salvar_pelo_nativo.png')
        cls.res_com, cls.codigo_com, _c = rodar(cls.caminho, CAPTURAS, SAIDA, com_plugin=True)

    def test_feicoes_de_teste_como_gravadas(self):
        a = self.antes
        self.assertIsNone(a['nulos']['zoom_corr'])
        self.assertIsNone(a['nulos']['visivel'])
        self.assertIsNone(a['sem_zoom']['created_zoom'])
        self.assertEqual(json.loads(a['170999-01']['portoes']), PORTOES)
        self.assertEqual(json.loads(a['270800']['minas']), MINAS)
        self.assertGreater(sum(1 for y in range(0, self.img_antes.height(), 3) for x in range(0, self.img_antes.width(), 3)
                               if QColor(self.img_antes.pixel(x, y)).lightness() < 200), 500)

    def test_sem_plugin_confere_com_a_especificacao(self):
        erros = reprovacoes(self.res, self.codigo, self.spec)
        self.assertEqual(erros, [], ' | '.join(erros))
        forms = self.res['formularios']
        ms = sorted(f['ms'] for f in forms.values())
        MEDIDAS.append('sem o plugin: {} formulários montados, {:.0f} a {:.0f} ms; abas do VAB: {}'.format(
            len(forms), ms[0], ms[-1], forms['170999-01']['abas']))
        self.assertEqual(forms['150000']['abas'], ['Símbolo', 'Textos', 'Aparência', 'Atributos', 'Avançado'])
        MEDIDAS.append('regravado sem efeito ao salvar o nome: ' + ', '.join(
            '{} {}'.format(k, sorted(set(f['mudou_com_nome']) - {'nome'})) for k, f in forms.items() if f['mudou_com_nome']))

    def test_salvar_pelo_nativo_nao_muda_o_desenho_nem_o_json(self):
        erros = reprovacoes_disco(self.antes, self.depois, self.img_antes, self.img_depois)
        self.assertEqual(erros, [], ' | '.join(erros))
        self.assertEqual(json.loads(self.depois['170999-01 editada']['portoes']), PORTOES)
        self.assertEqual(json.loads(self.depois['270800 editada']['minas']), MINAS)
        MEDIDAS.append('salvar o nome pelo nativo nas {} feições: 0 colunas a mais no disco, 0 pixels diferentes '
                       '(imagens area_antes/depois_de_salvar_pelo_nativo.png)'.format(len(self.depois) - 1))

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(self.codigo_com, 0, self.res_com.get('etapa'))
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        for chave, fo in self.res['formularios'].items():
            com = self.res_com['formularios'][chave]
            self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos']), (com['abas'], com['visiveis'], com['rotulos']), chave)
        iguais = 0
        for chave in CAPTURAS:
            a = QImage(os.path.join(SAIDA, 'nativo_area_{}_sem_plugin.png'.format(chave)))
            b = QImage(os.path.join(SAIDA, 'nativo_area_{}_com_plugin.png'.format(chave)))
            self.assertFalse(a.isNull() or b.isNull(), chave)
            dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                      if a.pixel(x, y) != b.pixel(x, y))
            iguais += dif == 0
        MEDIDAS.append('capturas da área com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, len(CAPTURAS)))
        self.assertEqual(iguais, len(CAPTURAS))

    def test_pior_caso_caixa_sem_nulo_reprova(self):
        """O mesmo estilo com a Correção de Zoom sem o estado nulo: salvar o nome grava False na nula."""
        import shutil
        from qgis.core import QgsEditorWidgetSetup
        destino = os.path.join(TMP, 'pior_caixa.gpkg')
        shutil.copy(self.caminho, destino)
        vl = QgsVectorLayer(gpkg.uri_camada(destino, 'coordination_area'), 'Área de Coordenação', 'ogr')
        i = vl.fields().indexOf('zoom_corr')
        cfg = dict(vl.editorWidgetSetup(i).config())
        cfg.pop('AllowNullState', None)
        vl.setEditorWidgetSetup(i, QgsEditorWidgetSetup('CheckBox', cfg))
        vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
        antes = linhas_cruas(destino)
        img_antes = renderizar(destino)
        res, codigo, copia = rodar(destino)
        erros = reprovacoes(res, codigo, self.spec)
        erros_disco = reprovacoes_disco(antes, linhas_cruas(copia), img_antes, renderizar(copia, 'pior_caso_caixa_depois.png'))
        MEDIDAS.append('pior caso, Correção de Zoom sem estado nulo: {} reprovações do formulário, no disco: {}'.format(
            len(erros), erros_disco))
        self.assertTrue(any(e.startswith('nulos: salvar o nome gravou também') and 'zoom_corr' in e for e in erros), erros)
        self.assertTrue(any(e.startswith('nulos:') and 'zoom_corr' in e for e in erros_disco), erros_disco)
        self.assertTrue(any(e.startswith('o desenho mudou') for e in erros_disco), erros_disco)

    def test_pior_caso_condicao_dos_portoes_apagada_reprova(self):
        import shutil
        from qgis.core import QgsOptionalExpression
        destino = os.path.join(TMP, 'pior_condicao.gpkg')
        shutil.copy(self.caminho, destino)
        vl = QgsVectorLayer(gpkg.uri_camada(destino, 'coordination_area'), 'Área de Coordenação', 'ogr')
        fc = vl.editFormConfig()

        def andar(cont):
            for el in cont.children():
                if hasattr(el, 'children') and el.name() == 'Portões':
                    el.setVisibilityExpression(QgsOptionalExpression())
                elif hasattr(el, 'children'):
                    andar(el)
        andar(fc.invisibleRootContainer())
        vl.setEditFormConfig(fc)
        vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
        res, codigo, _c = rodar(destino)
        erros = reprovacoes(res, codigo, self.spec)
        self.assertTrue(any(e == '150000: resumo dos portões fora do VAB' for e in erros), erros)


class TestePainelArea(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(TMP, 'calco_painel_area.gpkg')
        cls.calco = C.Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar()
        C.definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())
        cls.painel.setParent(None)
        cls.painel.resize(440, 1500)
        cls.painel.show()
        cls.lyr = cls.calco.camada('coordination_area')

    @classmethod
    def tearDownClass(cls):
        from qgis.core import QgsSettings
        QgsSettings().remove(ea.CHAVE_ULTIMO_TIPO)

    def tearDown(self):
        if self.lyr.isEditable():
            self.lyr.rollBack()
        _app.processEvents()

    def _nova(self, **attrs):
        from Calco.ferramentas import gravar_feicao
        a = dict(schema.padroes('coordination_area'), ebgeo_id=str(uuid.uuid4()), created_zoom=12.0, nome='Área do teste')
        a.update(attrs)
        g = QgsGeometry.fromPolygonXY([[QgsPointXY(*p) for p in QUADRA + [QUADRA[0]]]])
        eid = gravar_feicao(self.lyr, 'coordination_area', g, a)
        self.painel._camada_mudou(self.lyr)
        self.painel.mostrar_feicao(self.lyr, eid)
        self.painel._selecao_mudou()
        _app.processEvents()
        return eid

    def _disco(self, eid):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_area'), 'r', 'ogr')
        return next(vl.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))

    def _capturar(self, nome):
        self.painel.show()
        _app.processEvents()
        from Calco.ui.blocos.previa import esperar
        esperar(self.painel)  # a amostra do estilo desenha fora da interface
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def _divergencias_dock(self):
        erros = []
        for codigo, antigas in RETRATO_DOCK.items():
            extra = {'portoes': PORTOES} if codigo == '170999-01' else {}
            self._nova(symbol_code=codigo, **extra)
            vis = self.painel.campos_visiveis()
            if vis & TODAS_ANTIGAS != antigas:
                erros.append((codigo, sorted(antigas - vis), sorted((vis & TODAS_ANTIGAS) - antigas)))
            for col in TODAS_ANTIGAS - antigas:
                w = self.painel.widgets.get(col)
                if w is not None and not w.isHidden():
                    erros.append((codigo, 'à mostra', col))
        return erros

    def test_campos_e_editores_conforme_o_dock_de_antes(self):
        from Calco.ui.painel_area import EditorMinas, EditorPortoes
        self.assertEqual(self._divergencias_dock(), [])
        for codigo in CAPTURAS:
            extra = {'portoes': PORTOES, 'text_position': 'externa'} if codigo == '170999-01' else \
                {'minas': MINAS} if codigo == '270800' else {'escalao': 'II'} if codigo == '151203' else {}
            self._nova(symbol_code=codigo, **extra)
            rotulos = {lb.text() for lb in self.painel.form_host.findChildren(type(self.painel.titulo))
                       if lb.isVisibleTo(self.painel.form_host)}
            self.assertEqual('Posição do escalão na borda' in rotulos, codigo == '151203', codigo)
            self.assertIn(fa.ROTULO_CORRECAO_ZOOM, rotulos)
            self.assertFalse(any('[%' in r for r in rotulos), codigo)
            self._capturar('dock_area_{}.png'.format(codigo))
        self._nova(symbol_code='170999-01', portoes=PORTOES)
        self.assertIsInstance(self.painel.widgets['portoes'], EditorPortoes)
        self.assertEqual(len(self.painel.widgets['portoes'].portoes), 2)
        self._nova(symbol_code='270800', minas=MINAS)
        self.assertIsInstance(self.painel.widgets['minas'], EditorMinas)
        self.assertEqual([c.currentData() for c in self.painel.widgets['minas'].combos], MINAS)
        self.assertEqual(self.painel.widgets['symbol_code'].count(), 7)

    def test_pior_caso_dock_degradado_reprova(self):
        original = esp._CONSTRUTORES['coordination_area']

        def degradada():
            s = original()
            s.campo('line_style').condicao = None
            return s
        esp._CONSTRUTORES['coordination_area'] = degradada
        try:
            erros = self._divergencias_dock()
        finally:
            esp._CONSTRUTORES['coordination_area'] = original
        self.assertTrue(any(e[0] == '151000' for e in erros), erros)

    def test_troca_de_tipo_no_buffer_com_os_padroes(self):
        eid = self._nova(symbol_code='150000', minas=None)
        self.assertFalse(self.lyr.isEditable())
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('270800'))
        _app.processEvents()
        self.assertTrue(self.lyr.isEditable())
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual(f['symbol_code'], '270800')
        self.assertEqual(str(f['line_color']).lower(), '#00b04e')   # regra do guardião, no buffer
        self.assertEqual(regras.minas_validas(f['minas']), ea.MINAS_PADRAO)
        self.assertEqual(self._disco(eid)['symbol_code'], '150000')  # nada no disco
        self.assertEqual(self.painel.estado_edicao.text(), 'Mudanças não salvas.')
        self.assertIn('minas', self.painel.campos_visiveis())        # remontado para o tipo novo
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        d = self._disco(eid)
        self.assertEqual((d['symbol_code'], d['line_color'].lower()), ('270800', '#00b04e'))
        self.assertFalse(self.lyr.isEditable())
        # cor escolhida fica; a hachura do Terreno Restritivo liga
        eid = self._nova(symbol_code='150000', line_color='#123456')
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData('151100'))
        _app.processEvents()
        f = self.lyr.getFeature(self.painel.fid)
        self.assertEqual((f['line_color'], f['hatch_type'], f['hatch_enabled']), ('#123456', 'diagonal-right', True))
        self.assertTrue(self.painel.descartar())
        _app.processEvents()
        self.assertEqual(self._disco(eid)['symbol_code'], '150000')

    def test_portao_pelo_dock_e_hachura(self):
        eid = self._nova(symbol_code='170999-01')
        self.painel.widgets['portoes'].acrescentar()
        _app.processEvents()
        self.assertEqual(self._disco(eid)['portoes'] in ([], '[]', None), True)
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        v = self._disco(eid)['portoes']
        gs = v if isinstance(v, list) else json.loads(v)
        self.assertEqual([(g['nome'], g['ratio']) for g in gs], [('PORTÃO ALFA', 0.5)])
        con = sqlite3.connect(self.caminho)
        cru = con.execute('SELECT portoes FROM coordination_area WHERE ebgeo_id = ?', (eid,)).fetchone()[0]
        con.close()
        self.assertIsInstance(json.loads(cru), list)                 # JSON de verdade, não string escapada
        # a hachura escolhida no dock liga hatch_enabled (o widget só grava o tipo)
        self._nova(symbol_code='150000')
        cb = self.painel.widgets['hatch_type']
        cb.setCurrentIndex(cb.findData('cross'))
        self.painel._gravar_pendentes()
        self.assertTrue(self.lyr.getFeature(self.painel.fid)['hatch_enabled'])

    def test_bloqueada_so_leitura(self):
        self._nova(symbol_code='170999-01', bloqueado=True, portoes=PORTOES)
        for col in ('nome', 'symbol_code', 'line_color', 'portoes', 'text_position'):
            self.assertFalse(self.painel.widgets[col].isEnabled(), col)


class TesteRegrasArea(unittest.TestCase):
    def test_padroes_da_troca(self):
        p = regras.padroes_da_troca_area
        self.assertEqual(p({'symbol_code': '150000', 'line_color': '#000000', 'line_width': 3.0, 'fill_color': '#000000',
                            'opacity': 0.0, 'hatch_type': 'none', 'hatch_enabled': False, 'text_position': 'borda',
                            'minas': None}, '270800'),
                         {'symbol_code': '270800', 'line_color': ea.VERDE_OBSTACULO, 'line_width': 3.0,
                          'fill_color': ea.VERDE_OBSTACULO, 'opacity': 0.0, 'hatch_type': 'none', 'hatch_enabled': False,
                          'text_position': 'borda', 'minas': ea.MINAS_PADRAO})
        # escolha fica; posição escolhida fica; código desconhecido vale a genérica nos dois lados
        m = p({'symbol_code': '999', 'line_color': '#123456', 'line_width': 7.0, 'text_position': 'interna'}, '170999-01')
        self.assertNotIn('line_color', m)
        self.assertNotIn('line_width', m)
        self.assertNotIn('text_position', m)
        self.assertEqual(p({'symbol_code': None}, 'xyz')['symbol_code'], '150000')
        self.assertEqual(p({'symbol_code': '150000', 'text_position': None}, '170999-01')['text_position'], 'externa')
        self.assertNotIn('minas', p({'symbol_code': '150000', 'minas': json.dumps(MINAS)}, '270800'))
        # a delegação do estilo (a área nova que nasce no último tipo) dá o mesmo
        self.assertEqual(ea.troca_de_simbolo({'symbol_code': '150000'}, '151203'), p({'symbol_code': '150000'}, '151203'))

    def test_ao_mudar(self):
        ant = {'symbol_code': '150000', 'line_color': '#000000', 'line_width': 3.0, 'fill_color': '#000000',
               'opacity': 0.0, 'hatch_type': 'none', 'hatch_enabled': False, 'text_position': 'borda', 'minas': MINAS}
        ex = regras.ao_mudar('coordination_area', ant, {'symbol_code': '151100'})
        self.assertEqual(ex, {'opacity': 1.0, 'hatch_type': 'diagonal-right', 'hatch_enabled': True})
        # a cor que o operador escolhe na mesma edição fica; a regravada como QColor (outra caixa) não é escolha
        ex = regras.ao_mudar('coordination_area', ant, {'symbol_code': '270800', 'line_color': QColor('#abcdef')})
        self.assertNotIn('line_color', ex)
        ex = regras.ao_mudar('coordination_area', ant, {'symbol_code': '270800', 'line_color': QColor('#000000')})
        self.assertEqual(ex['line_color'], ea.VERDE_OBSTACULO)
        self.assertNotIn('minas', ex)  # já tem as três
        # a hachura acompanha o tipo
        self.assertEqual(regras.ao_mudar('coordination_area', ant, {'hatch_type': 'dots'}), {'hatch_enabled': True})
        self.assertEqual(regras.ao_mudar('coordination_area', dict(ant, hatch_enabled=True, hatch_type='dots'),
                                         {'hatch_type': 'none'}), {'hatch_enabled': False})
        self.assertEqual(regras.ao_mudar('coordination_area', ant, {'tipo': 'x'}), {})

    def _camada(self, nome, estilizar):
        caminho = os.path.join(TMP, nome + '.gpkg')
        gpkg.criar_calco(caminho, ['coordination_area'])
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_area'), 'Área de Coordenação', 'ogr')
        a = dict(schema.padroes('coordination_area'), ebgeo_id=str(uuid.uuid4()), minas=None)
        f = QgsFeature(vl.fields())
        for k, v in schema.atributos_para_qgis('coordination_area', a).items():
            f.setAttribute(vl.fields().indexOf(k), v)
        f.setGeometry(QgsGeometry.fromMultiPolygonXY([[[QgsPointXY(*p) for p in QUADRA + [QUADRA[0]]]]]))
        vl.startEditing()
        vl.addFeature(f)
        assert vl.commitChanges()
        if estilizar:
            C.aplicar_estilo(vl, 'coordination_area')
        return vl, next(vl.getFeatures()).id()

    def test_guardiao_no_formulario_nativo_e_na_tabela(self):
        from test_guardiao import pela_tabela, pelo_formulario
        vl, fid = self._camada('regra_form', True)
        g = guardiao.garantir(vl, 'coordination_area')
        self.assertIsNotNone(g)
        vl.startEditing()
        pelo_formulario(vl, fid, {'symbol_code': '270800'})
        f = vl.getFeature(fid)
        self.assertEqual((f['symbol_code'], cor(vl, fid)), ('270800', '#00b04e'))
        self.assertEqual(regras.minas_validas(f['minas']), ea.MINAS_PADRAO)
        vl.undoStack().undo()   # desfaz a regra
        self.assertEqual(cor(vl, fid), '#000000')
        vl.rollBack()
        # sem o valor padrão do estilo, a hachura pela tabela liga pelo guardião
        vl, fid = self._camada('regra_tabela', False)
        guardiao.garantir(vl, 'coordination_area')
        vl.startEditing()
        pela_tabela(vl, fid, 'hatch_type', 'cross')
        self.assertTrue(vl.getFeature(fid)['hatch_enabled'])
        vl.rollBack()

    def test_sem_plugin_o_valor_padrao_liga_a_hachura(self):
        from test_guardiao import pela_tabela
        vl, fid = self._camada('hachura_padrao', True)  # sem guardião
        vl.startEditing()
        pela_tabela(vl, fid, 'hatch_type', 'dots')
        self.assertTrue(vl.getFeature(fid)['hatch_enabled'])
        vl.rollBack()

    def test_pior_caso_sem_guardiao_nem_estilo(self):
        from test_guardiao import pela_tabela, pelo_formulario
        vl, fid = self._camada('regra_nada', False)
        vl.startEditing()
        pela_tabela(vl, fid, 'hatch_type', 'cross')
        self.assertFalse(vl.getFeature(fid)['hatch_enabled'])        # a régua (ligada) reprovaria
        pelo_formulario(vl, fid, {'symbol_code': '270800'})
        self.assertEqual(vl.getFeature(fid)['symbol_code'], '270800')
        self.assertEqual(cor(vl, fid), '#000000')  # sem a cor do tipo
        vl.rollBack()


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
