# -*- coding: utf-8 -*-
"""
Formulário das feições comuns do mapa 2D (formulario/tipos/comuns.py), da aba Fotos
(formulario/fotos.py) e dos blocos do dock (ui/blocos/comuns.py): os 14 tipos de grupo 'forma' e
'analise' do esquema, que entram pelo importador .ebgeo e pelo Azimute e Distância.

  - Especificação: toda coluna do esquema está no formulário ou entre os ocultos; as condições
    próprias (Ligado, Preenchida) dão em Python o mesmo que a expressão QGIS; as expressões dos
    textos (fotos, resumo do Azimute, prévia da imagem) se leem.
  - Formulário nativo, num processo NOVO e SEM o plugin (e de novo com ele), sobre a saída REAL:
    a fixture 06 importada pelo importador (estilos gravados por arvore.salvar_estilos) e as
    construções do Azimute gravadas pela ferramenta num calco. Em TODAS as feições dos 14 tipos:
    layout arrastar-e-soltar sem código e só widgets nativos, aliases da especificação, ocultos
    também na tabela, as abas e os campos visíveis que a especificação manda, a feição bloqueada
    só para leitura, as fotos da feição na aba Fotos (e a aba ausente sem foto), o resumo do
    Azimute com uma linha por perna, a prévia da imagem, e salvar sem mudar não muda nada.
  - O retrato de antes (o código de 86f7d3b, sem especificação destes tipos: formulário
    autogerado com colunas técnicas, base64 e JSON à mostra) é REPROVADO pela mesma régua, e
    também a saída real degradada: widget do plugin no estilo, aba Fotos sem a condição, a lista
    de fotos apagada, o rótulo sem condição.
  - Dock: os mesmos campos que a especificação, a seção Fotos lida do GeoPackage (miniaturas,
    Abrir sem apagar nada), o resumo do Azimute e o "Editar pernas..." que abre o painel do
    Azimute em edição, e Salvar e Descartar no buffer.

Capturas do formulário nativo (com e sem o plugin) e do dock em EBGEO_TESTE_SAIDA (padrão:
temporária); com QT_QPA_PLATFORM=offscreen, o texto só sai legível com QT_QPA_FONTDIR apontando
as fontes do sistema. A fixture vem de EBGEO_FIXTURES (padrão: ../_ebgeo_dados_teste, irmão do
repositório).

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_comuns.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
RAIZ_REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsEditorWidgetSetup, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils,
    QgsFeature, QgsField, QgsFields, QgsOptionalExpression, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import schema  # noqa: E402
from Calco.calco import Calco, PROP_CAMINHO, PROP_TIPO, definir_calco_ativo  # noqa: E402
from Calco.formulario import especificacao as esp, fotos as F  # noqa: E402
from Calco.formulario import nativo  # noqa: E402,F401 (carregado já: o estilizar o importa sob demanda)
from Calco.formulario.tipos import comuns as CM  # noqa: E402

FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
TMP = tempfile.mkdtemp(prefix='ebgeo_form_comuns_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []
TIPOS = CM.TIPOS
JSON_COLS = {t: schema.colunas_json(t) for t in TIPOS}

# As capturas: (arquivo, tipo, nome da feição na fixture ou no calco do Azimute)
CAPTURAS = (('ponto', 'point', 'Posto de Comando Avançado'), ('texto', 'text', None),
            ('poligono_hachura', 'polygon', 'Hachura cross'), ('rota_azimute', 'line', 'Rota polar'),
            ('fotos', 'point', 'Ponto com três fotos'))

# Roda num processo novo, sem o caminho do plugin. argv: gpkg, json de saída, pasta de capturas; no
# ambiente, EBGEO_TABELAS {tipo: tabela} e EBGEO_CAPTURAS {tipo: [ebgeo_id]}. Com EBGEO_PLUGIN,
# importa o plugin e liga o guardião.
SCRIPT = r'''
import sys, os, json, time
gp, saida, pasta = sys.argv[1:4]
caps = json.loads(os.environ.get('EBGEO_CAPTURAS') or '{}')
res = {'etapa': 'inicio', 'tipos': {}}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
plugin = os.environ.get('EBGEO_PLUGIN')
if plugin:
    sys.path.insert(0, plugin)
from qgis.core import QgsApplication, QgsVectorLayer, QgsProject
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
from qgis.PyQt.QtWidgets import QTabWidget, QLabel, QGroupBox, QToolButton
from qgis.PyQt.QtGui import QImage, QPainter, QColor, QFont
QgsGui.editorWidgetRegistry().initEditors()
P = QgsProject.instance()
tabelas = json.loads(os.environ['EBGEO_TABELAS'])
mudar_nome = bool(os.environ.get('EBGEO_MUDAR_NOME'))
# a tabela de fotos aberta como o operador a abriria: pelo nome da tabela
fotos = QgsVectorLayer(gp + '|layername=ebgeo_foto', 'ebgeo_foto', 'ogr')
if fotos.isValid():
    P.addMapLayer(fotos)
res['modulos_ebgeo'] = []
for tipo, tabela in tabelas.items():
    L = QgsVectorLayer(gp + '|layername=' + tabela, tabela, 'ogr')
    if not L.isValid():
        continue
    P.addMapLayer(L)
    if plugin:
        from Calco import guardiao
        guardiao.garantir(L, tipo)
    fc = L.editFormConfig()
    nomes = L.fields().names()
    r = res['tipos'][tipo] = {
        'layout': fc.layout().name, 'init': fc.initCodeSource().name,
        'init_codigo': len(fc.initCode() or '') + len(fc.initFunction() or ''), 'ui': fc.uiForm(),
        'acoes': len(L.actions().actions()),
        'widgets': {n: L.editorWidgetSetup(i).type() for i, n in enumerate(nomes)},
        'aliases': {n: L.attributeAlias(i) for i, n in enumerate(nomes)},
        'tabela_ocultas': sorted(c.name for c in L.attributeTableConfig().columns() if c.hidden and c.name),
        'formularios': {}}
    res['etapa'] = 'estatico ' + tipo
    gravar()
    L.startEditing()
    for f in L.getFeatures():
        eid = str(f['ebgeo_id'])
        res['etapa'] = 'montando {} {}'.format(tipo, eid)
        t = time.perf_counter()
        form = QgsAttributeForm(L, f)
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        ms = (time.perf_counter() - t) * 1000
        form.resize(480, 640)
        form.show(); app.processEvents()
        tabs = form.findChildren(QTabWidget)
        tw = tabs[0] if tabs else None
        indices = [k for k in range(tw.count()) if tw.isTabVisible(k)] if tw else [None]
        abas, vis, rotulos, travados, imgs, longos, grab, textos = [], set(), set(), {}, {}, [], [], {}
        for k in indices:
            nome_aba = tw.tabText(k) if tw is not None else ''
            if tw is not None:
                tw.setCurrentIndex(k); app.processEvents()
                abas.append(nome_aba)
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
                    if hasattr(w, 'currentText'):
                        textos[n] = w.currentText()
            for lb in form.findChildren(QLabel):
                if not (lb.isVisibleTo(form) and lb.text()):
                    continue
                tx = lb.text()
                if '<img' in tx or '<table' in tx:
                    imgs[nome_aba] = imgs.get(nome_aba, 0) + tx.count('<img')
                    longos.append({'aba': nome_aba, 'imgs': tx.count('<img'), 'linhas': tx.count('<tr>'),
                                   'texto': tx if '<img' not in tx else ''})
                else:
                    rotulos.add(tx)
            if pasta and eid in caps.get(tipo, []):
                grab.append(form.grab().toImage())
        salvo = form.save()
        def mudadas():
            return sorted(L.fields().at(i).name() for i in L.editBuffer().changedAttributeValues().get(f.id(), {}))
        mudou = {eid: mudadas()} if mudadas() else {}
        mudou_nome = None
        if mudar_nome:  # o operador muda só o nome pelo formulário e salva
            form.changeAttribute('nome', '{} (editado)'.format(f['nome'] or ''))
            form.save()
            mudou_nome = mudadas()
        r['formularios'][eid] = {'ms': round(ms, 1), 'abas': abas, 'visiveis': sorted(vis), 'rotulos': sorted(rotulos),
                                 'travados': travados, 'textos': textos, 'imgs': imgs, 'longos': longos, 'salvo': salvo,
                                 'mudou_ao_salvar': mudou, 'mudou_ao_mudar_o_nome': mudou_nome}
        if grab:
            W = sum(im.width() for im in grab) + 8 * (len(grab) - 1)
            H = max(im.height() for im in grab) + 26
            out = QImage(W, H, QImage.Format.Format_ARGB32); out.fill(QColor('white'))
            p = QPainter(out); x = 0
            p.setFont(QFont('Segoe UI', 10))
            p.drawText(4, 17, '{}: formulário nativo {} o plugin, uma imagem por aba visível; montado em {:.0f} ms'.format(
                f['nome'], 'COM' if plugin else 'SEM', ms))
            for im in grab:
                p.drawImage(x, 26, im); x += im.width() + 8
            p.end()
            out.save(os.path.join(pasta, 'nativo_{}_{}_{}.png'.format(tipo, eid[:8], 'com_plugin' if plugin else 'sem_plugin')))
        form.close(); form.deleteLater(); app.processEvents()
    if mudar_nome:
        res['gravado_' + tipo] = L.commitChanges()
    else:
        L.rollBack()
    gravar()
res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
res['etapa'] = 'fim'
gravar()
'''


def _exe():
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    return exe if os.path.exists(exe) else sys.executable


def rodar_sem_plugin(caminho, tipos=TIPOS, capturas=None, pasta='', com_plugin=False, timeout=600, mudar_nome=False):
    """Roda o SCRIPT em processo novo. Devolve (resultado, código de saída ou 'tempo esgotado')."""
    script = os.path.join(TMP, 'sem_plugin_comuns.py')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(SCRIPT)
    saida = os.path.join(TMP, 'res_{}.json'.format(uuid.uuid4().hex[:8]))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['EBGEO_TABELAS'] = json.dumps({t: schema.TIPOS[t]['tabela'] for t in tipos})
    env['EBGEO_CAPTURAS'] = json.dumps(capturas or {})
    if mudar_nome:
        env['EBGEO_MUDAR_NOME'] = '1'
    else:
        env.pop('EBGEO_MUDAR_NOME', None)
    if com_plugin:
        env['EBGEO_PLUGIN'] = PLUGIN
    else:
        env.pop('EBGEO_PLUGIN', None)
    args = [_exe(), script, caminho, saida, pasta]
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=TMP,
                         shell=args[0].endswith('.bat'))
    try:
        p.communicate(timeout=timeout)
        codigo = p.returncode
    except subprocess.TimeoutExpired:
        # preso: encerra a árvore do processo que ESTE teste abriu
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


# ---------------------------------------------------------------------------------------------
# O esperado, lido do GeoPackage no processo do teste
# ---------------------------------------------------------------------------------------------

def contagem_fotos(caminho):
    con = sqlite3.connect(caminho)
    try:
        return dict(con.execute('SELECT ebgeo_id, count(*) FROM ebgeo_foto GROUP BY ebgeo_id').fetchall())
    except sqlite3.Error:
        return {}
    finally:
        con.close()


def feicoes(caminho, tipo):
    """{ebgeo_id: atributos (com a contagem de fotos)} de todas as feições do tipo no arquivo."""
    vl = QgsVectorLayer('{}|layername={}'.format(caminho, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
    nfotos = contagem_fotos(caminho)
    res = {}
    for f in vl.getFeatures():
        a = {n: f[n] for n in vl.fields().names()}
        a[F.TemFotos.CHAVE_CONTAGEM] = nfotos.get(str(f['ebgeo_id']), 0)
        res[str(f['ebgeo_id'])] = a
    return res, vl.fields().names()


def _pernas(attrs):
    v = attrs.get(CM.COLUNA_AZIMUTE)
    if v is None or (hasattr(v, 'isNull') and v.isNull()):
        return None
    if isinstance(v, str):
        v = json.loads(v)
    return len(v.get('legs') or [])


def esperado(spec, attrs, nomes):
    proprias = [n for n in nomes if n.startswith(esp.PREFIXO_ATRIBUTOS)]
    vis = {c.coluna for c in spec.campos() if c.coluna in nomes and spec.visivel(c.coluna, attrs)} | set(proprias)
    rotulos = {c.rotulo_para(attrs) for c in spec.campos() if c.coluna in vis}
    abas = []
    for a in spec.abas:
        tem = bool(proprias) if a.prefixo else any(
            (isinstance(el, esp.Campo) and el.coluna in nomes) or isinstance(el, esp.Texto) for el, _c in
            esp.Formulario('x', [], [a], ()).percorrer())
        if tem and (a.condicao is None or a.condicao.avaliar(attrs)):
            abas.append(a.nome)
    return vis, rotulos, abas


def reprovacoes(res, codigo, caminho, tipos=TIPOS):
    """Tudo o que reprova o formulário lido sem o plugin; lista vazia é aprovação."""
    erros = []
    if codigo != 0:
        erros.append('processo saiu com {} na etapa {}'.format(codigo, res.get('etapa')))
    if not res or not res.get('tipos'):
        return erros + ['sem resultado']
    if res.get('modulos_ebgeo') and not os.environ.get('EBGEO_PLUGIN'):
        pass  # o com-plugin é conferido no próprio teste
    for tipo in tipos:
        r = res['tipos'].get(tipo)
        if r is None:
            erros.append('{}: camada não lida'.format(tipo))
            continue
        spec = esp.formulario(tipo)
        if r['layout'] != 'DragAndDrop':
            erros.append('{}: layout {}'.format(tipo, r['layout']))
        if r['init'] != 'NoSource' or r['init_codigo'] or r['ui'] or r['acoes']:
            erros.append('{}: formulário com código'.format(tipo))
        for col, w in r['widgets'].items():
            if w not in esp.WIDGETS_NATIVOS:
                erros.append('{}: widget não nativo em {}: {}'.format(tipo, col, w))
        for c in spec.campos():
            if c.coluna in r['aliases'] and r['aliases'][c.coluna] != c.rotulo:
                erros.append('{}: alias de {}: {!r}'.format(tipo, c.coluna, r['aliases'][c.coluna]))
        ocultos = {c for c in spec.ocultos if c in r['aliases']}
        if set(r['tabela_ocultas']) != ocultos:
            erros.append('{}: ocultas na tabela {}'.format(tipo, r['tabela_ocultas']))
        atributos, nomes = feicoes(caminho, tipo)
        so_leitura = {c.coluna for c in spec.campos() if c.somente_leitura}
        for eid, attrs in atributos.items():
            fo = r['formularios'].get(eid)
            if fo is None:
                erros.append('{} {}: formulário não montado'.format(tipo, eid))
                continue
            vis, rotulos, abas = esperado(spec, attrs, nomes)
            if set(fo['visiveis']) != vis:
                erros.append('{} {}: visíveis a mais {} a menos {}'.format(
                    tipo, eid[:8], sorted(set(fo['visiveis']) - vis), sorted(vis - set(fo['visiveis']))))
            if fo['abas'] != abas:
                erros.append('{} {}: abas {} (esperadas {})'.format(tipo, eid[:8], fo['abas'], abas))
            if not rotulos <= set(fo['rotulos']):
                erros.append('{} {}: rótulos ausentes {}'.format(tipo, eid[:8], sorted(rotulos - set(fo['rotulos']))))
            travada = bool(attrs.get('bloqueado'))
            if (esp.AVISO_BLOQUEADA in fo['rotulos']) != travada:
                erros.append('{} {}: aviso de bloqueio errado'.format(tipo, eid[:8]))
            for col, travado in fo['travados'].items():
                if travado != (travada or col in so_leitura):
                    erros.append('{} {}: {} {}'.format(tipo, eid[:8], col, 'travado' if travado else 'editável'))
            n = attrs[F.TemFotos.CHAVE_CONTAGEM]
            if fo['imgs'].get(F.NOME_ABA, 0) != n:
                erros.append('{} {}: {} foto(s) na aba Fotos, esperadas {}'.format(tipo, eid[:8], fo['imgs'].get(F.NOME_ABA, 0), n))
            pernas = _pernas(attrs)
            resumo = [l for l in fo['longos'] if l['aba'] == CM.NOME_ABA_AZIMUTE]
            if pernas is not None and (len(resumo) != 1 or resumo[0]['linhas'] != pernas + 1
                                       or '{} perna(s)'.format(pernas) not in resumo[0]['texto']):
                erros.append('{} {}: resumo do Azimute {} (esperadas {} pernas)'.format(tipo, eid[:8], resumo, pernas))
            if tipo == 'image' and attrs.get('bitmap_b64') and fo['imgs'].get('Imagem', 0) != 1:
                erros.append('{} {}: sem a prévia da imagem'.format(tipo, eid[:8]))
            if not fo['salvo'] or fo['mudou_ao_salvar']:
                erros.append('{} {}: salvar sem mudar gravou {}'.format(tipo, eid[:8], fo['mudou_ao_salvar']))
    return erros


# ---------------------------------------------------------------------------------------------
# Preparação: a saída real do importador e do Azimute
# ---------------------------------------------------------------------------------------------

def importar(destino):
    from Calco.importador import escritor
    escritor.importar(FIXTURE_06, destino)
    # uma feição bloqueada no EBGeo Web entre as comuns (a fixture não traz)
    from osgeo import ogr
    ds = ogr.Open(destino, 1)  # pelo OGR: os gatilhos do GeoPackage pedem as funções ST_ dele
    ds.ExecuteSQL("UPDATE polygon SET bloqueado = 1 WHERE nome = 'Hachura vertical'")
    ds = None


def estilizar_importado(caminho, com_formulario=True):
    """Os estilos gravados pelo importador; confere no arquivo que cada tipo levou o formulário."""
    from Calco.importador import arvore
    avisos = []
    log = QgsApplication.messageLog()
    pegar = lambda msg, tag, _nivel: avisos.append(msg) if tag == 'EBGeo' else None
    log.messageReceived.connect(pegar)
    try:
        usados = arvore.salvar_estilos(caminho, tipos=list(TIPOS))
    finally:
        log.messageReceived.disconnect(pegar)
    if com_formulario:
        sem = sem_formulario(caminho)
        assert not sem, 'estilo gravado sem o formulário: {}; avisos: {}'.format(sem, avisos)
    return usados


def sem_formulario(caminho, tipos=TIPOS):
    con = sqlite3.connect(caminho)
    try:
        return [t for t in tipos if '<editorlayout>tablayout</editorlayout>' not in (con.execute(
            'SELECT styleQML FROM layer_styles WHERE f_table_name = ? ORDER BY update_time DESC LIMIT 1',
            (schema.TIPOS[t]['tabela'],)).fetchone() or [''])[0]]
    finally:
        con.close()


ESTADOS_AZIMUTE = {
    'route': {'referencePoint': [-47.8, -15.75], 'outputMode': 'route', 'angularUnit': 'degrees',
              'distanceUnit': 'meters', 'northReference': 'true', 'magneticDeclination': -22.0,
              'meridianConvergence': 0.76, 'legs': [{'azimuth': 45, 'distance': 1000, 'observation': 'P1'},
                                                     {'azimuth': 120, 'distance': 800, 'observation': ''}]},
    'area': {'referencePoint': [-47.85, -15.8], 'outputMode': 'area', 'angularUnit': 'mils',
             'distanceUnit': 'kilometers', 'northReference': 'magnetic', 'magneticDeclination': -21.5,
             'meridianConvergence': 0.78, 'legs': [{'azimuth': 0, 'distance': 1}, {'azimuth': 1600, 'distance': 1},
                                                    {'azimuth': 3200, 'distance': 1}]},
    'point': {'referencePoint': [-47.9, -15.7], 'outputMode': 'point', 'angularUnit': 'degrees',
              'distanceUnit': 'meters', 'northReference': 'grid', 'magneticDeclination': 0,
              'meridianConvergence': 0.7, 'legs': [{'azimuth': 30, 'distance': 500, 'observation': 'Marco'}]},
}


def calco_do_azimute(caminho):
    """Um calco com as três saídas do Azimute gravadas pela ferramenta (gravacao.criar)."""
    from Calco.azimute import gravacao
    c = Calco(caminho)
    c.criar()
    c.carregar()
    definir_calco_ativo(c)
    for estado in ESTADOS_AZIMUTE.values():
        lyr, ids = gravacao.criar(c, dict(estado))
        assert ids, estado['outputMode']
    c.carregar()  # estilo e formulário dos tipos do Azimute gravados no arquivo
    assert not sem_formulario(caminho, ('point', 'line', 'polygon'))
    QgsProject.instance().removeAllMapLayers()
    return c


def _json(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def _iguais(a, b):
    nulo = lambda v: v is None or (hasattr(v, 'isNull') and v.isNull())
    if nulo(a) or nulo(b):
        return nulo(a) and nulo(b)
    if isinstance(a, float) or isinstance(b, float):
        return abs(float(a) - float(b)) < 1e-9
    return a == b  # cor também: a caixa gravada é a do arquivo


def _pixels_diferentes(a, b):
    """Pixels diferentes entre as duas imagens, todos (bytes do quadro inteiro, linha a linha)."""
    if a.size() != b.size():
        return a.width() * a.height()
    n = 0
    for y in range(a.height()):
        la, lb = bytes(a.constScanLine(y).asarray(a.bytesPerLine())), bytes(b.constScanLine(y).asarray(b.bytesPerLine()))
        if la != lb:
            n += sum(1 for x in range(0, len(la), 4) if la[x:x + 4] != lb[x:x + 4])
    return n


def desenhar(caminho, tipo, extensao=None):
    """A camada do tipo desenhada com o estilo gravado no arquivo, na extensão dada (ou na das feições)."""
    from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsMapRendererSequentialJob,
                           QgsMapSettings)
    from qgis.PyQt.QtCore import QSize
    vl = QgsVectorLayer('{}|layername={}'.format(caminho, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
    ms = QgsMapSettings()
    web = QgsCoordinateReferenceSystem('EPSG:3857')
    ms.setDestinationCrs(web)
    ms.setLayers([vl])
    ms.setOutputSize(QSize(700, 700))
    ms.setOutputDpi(96)
    if extensao is None:
        extensao = QgsCoordinateTransform(vl.crs(), web, QgsProject.instance()).transformBoundingBox(vl.extent())
        extensao.scale(1.2)
        if extensao.width() == 0 or extensao.height() == 0:
            extensao.grow(1000)
    ms.setExtent(extensao)
    ctx = QgsExpressionContext()
    ctx.appendScopes([QgsExpressionContextUtils.globalScope(), QgsExpressionContextUtils.projectScope(QgsProject.instance()),
                      QgsExpressionContextUtils.mapSettingsScope(ms)])
    ms.setExpressionContext(ctx)
    job = QgsMapRendererSequentialJob(ms)
    job.start()
    job.waitForFinished()
    return job.renderedImage(), extensao


def _degradar(origem, nome, tipo, alterar):
    """Cópia do arquivo com o estilo real do tipo degradado por `alterar(camada)`."""
    destino = os.path.join(TMP, 'pior_{}.gpkg'.format(nome))
    shutil.copy(origem, destino)
    vl = QgsVectorLayer('{}|layername={}'.format(destino, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
    alterar(vl)
    vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
    return destino


def _ids_por_nome(caminho, tipo, nome):
    con = sqlite3.connect(caminho)
    try:
        if nome is None:
            return [r[0] for r in con.execute('SELECT ebgeo_id FROM "{}" ORDER BY fid LIMIT 1'.format(schema.TIPOS[tipo]['tabela']))]
        return [r[0] for r in con.execute('SELECT ebgeo_id FROM "{}" WHERE nome = ?'.format(schema.TIPOS[tipo]['tabela']), (nome,))]
    finally:
        con.close()


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06-completo-3.0.ebgeo ausente')
class TesteEspecificacao(unittest.TestCase):
    def test_toda_coluna_no_formulario_ou_oculta(self):
        for tipo in TIPOS:
            spec = esp.formulario(tipo)
            self.assertIsNotNone(spec, tipo)
            cols = [c.coluna for c in spec.campos()]
            self.assertEqual(len(cols), len(set(cols)), tipo)
            falta = set(schema.nomes_campos(tipo)) - set(cols) - set(spec.ocultos)
            self.assertEqual(falta, set(), tipo)
            self.assertEqual(set(cols) - set(schema.nomes_campos(tipo)), set(), tipo)
            for c in spec.campos():
                self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, (tipo, c.coluna))
            # as técnicas nunca à mostra
            for col in ('svg', 'bitmap_b64', 'bitmap_mime', 'props', 'atributos', 'grupos', 'parametros', CM.COLUNA_AZIMUTE):
                self.assertNotIn(col, cols, (tipo, col))
            self.assertEqual([a.nome for a in spec.abas][-3:], ['Atributos', 'Fotos', 'Avançado'], tipo)

    def test_pior_caso_coluna_esquecida_reprova(self):
        spec = esp.formulario('text')
        spec.abas[1].filhos = spec.abas[1].filhos[:1]  # a caixa de fundo perde os campos
        falta = set(schema.nomes_campos('text')) - {c.coluna for c in spec.campos()} - set(spec.ocultos)
        self.assertIn('bg_fill_color', falta)

    def test_condicoes_python_iguais_a_expressao(self):
        campos = QgsFields()
        for n, t in (('show_label', QMetaType.Type.Bool), ('hatch_enabled', QMetaType.Type.Bool),
                     ('show_background', QMetaType.Type.Bool), (CM.COLUNA_AZIMUTE, QMetaType.Type.QString)):
            campos.append(QgsField(n, t))
        conds = [CM.Ligado('show_label'), CM.Ligado('hatch_enabled'), CM.Ligado('show_background'),
                 CM.Preenchida(CM.COLUNA_AZIMUTE)]
        n = 0
        for v in (True, False, None):
            for az in ('{"legs": []}', None):
                f = QgsFeature(campos)
                f.setAttributes([v, v, v, az])
                attrs = {'show_label': v, 'hatch_enabled': v, 'show_background': v, CM.COLUNA_AZIMUTE: az}
                ctx = QgsExpressionContext()
                ctx.setFeature(f)
                for c in conds:
                    e = QgsExpression(c.expressao())
                    self.assertEqual(bool(e.evaluate(ctx)), c.avaliar(attrs), (c, v, az))
                    n += 1
        MEDIDAS.append('condições próprias: {} avaliações, Python igual à expressão QGIS'.format(n))

    def test_expressoes_dos_textos_se_leem(self):
        for tipo in TIPOS:
            spec = esp.formulario(tipo)
            for el, conds in spec.percorrer():
                if isinstance(el, esp.Texto) and '[%' in el.texto:
                    e = QgsExpression(el.texto.strip()[3:-3])
                    self.assertFalse(e.hasParserError(), (tipo, el.nome, e.parserErrorString()))
                for c in conds:
                    self.assertFalse(QgsExpression(c.expressao()).hasParserError(), (tipo, c))


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06-completo-3.0.ebgeo ausente')
class TesteNativoSemPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.importado = os.path.join(TMP, 'importado.gpkg')
        t = time.perf_counter()
        importar(cls.importado)
        # o retrato de antes: o MESMO arquivo estilizado sem a especificação dos comuns (86f7d3b)
        cls.antes = os.path.join(TMP, 'antes.gpkg')
        shutil.copy(cls.importado, cls.antes)
        guardados = {t: esp._CONSTRUTORES.pop(t) for t in TIPOS}
        try:
            estilizar_importado(cls.antes, com_formulario=False)
        finally:
            esp._CONSTRUTORES.update(guardados)
        estilizar_importado(cls.importado)
        cls.calco = os.path.join(TMP, 'calco_azimute.gpkg')
        calco_do_azimute(cls.calco)
        MEDIDAS.append('preparo (importar a fixture 06, estilos e o calco do Azimute): {:.1f} s'.format(time.perf_counter() - t))
        cls.caps = {}
        for _arq, tipo, nome in CAPTURAS:
            cls.caps.setdefault(tipo, []).extend(_ids_por_nome(cls.importado, tipo, nome))
        cls.caps_calco = {'line': _ids_por_nome(cls.calco, 'line', None), 'polygon': _ids_por_nome(cls.calco, 'polygon', None)}
        t = time.perf_counter()
        cls.res, cls.codigo = rodar_sem_plugin(cls.importado, capturas=cls.caps, pasta=SAIDA)
        cls.t_sem = time.perf_counter() - t
        cls.res_com, cls.codigo_com = rodar_sem_plugin(cls.importado, capturas=cls.caps, pasta=SAIDA, com_plugin=True)
        cls.tipos_calco = ('point', 'line', 'polygon')
        cls.res_calco, cls.codigo_calco = rodar_sem_plugin(cls.calco, tipos=cls.tipos_calco, capturas=cls.caps_calco,
                                                           pasta=SAIDA)

    def test_importado_sem_plugin_confere_com_a_especificacao(self):
        erros = reprovacoes(self.res, self.codigo, self.importado)
        self.assertEqual(erros, [], ' | '.join(erros[:40]))
        self.assertEqual(self.res['modulos_ebgeo'], [])
        forms = [fo for r in self.res['tipos'].values() for fo in r['formularios'].values()]
        ms = sorted(fo['ms'] for fo in forms)
        com_fotos = sum(1 for fo in forms if F.NOME_ABA in fo['abas'])
        com_az = sum(1 for fo in forms if CM.NOME_ABA_AZIMUTE in fo['abas'])
        MEDIDAS.append('sem o plugin, fixture 06: {} formulários de {} tipos montados e salvos sem mudança em {:.0f} s; '
                       'montagem de {:.0f} a {:.0f} ms (mediana {:.0f}); {} com a aba Fotos, {} com a do Azimute'.format(
                           len(forms), len(self.res['tipos']), self.t_sem, ms[0], ms[-1], ms[len(ms) // 2], com_fotos, com_az))
        tres = self.res['tipos']['point']['formularios'][self.caps['point'][-1]]
        self.assertEqual(tres['imgs'][F.NOME_ABA], 3)
        self.assertEqual(tres['abas'], ['Marcador', 'Etiqueta', 'Atributos', 'Fotos', 'Avançado'])

    def test_icone_personalizado_legivel_sem_plugin(self):
        """O ponto com ícone próprio (`custom:<id>`) mostra o nome do ícone, não o código."""
        nomes = dict(sqlite3.connect(self.importado).execute('SELECT icone_id, nome FROM ebgeo_icone').fetchall())
        vistos = 0
        for eid, attrs in feicoes(self.importado, 'point')[0].items():
            simbolo = str(attrs.get('marker_symbol') or '')
            if not simbolo.startswith('custom:'):
                continue
            texto = self.res['tipos']['point']['formularios'][eid]['textos'].get('marker_symbol')
            self.assertEqual(texto, 'Ícone personalizado: ' + nomes[simbolo[len('custom:'):]], (eid, texto))
            vistos += 1
        self.assertGreater(vistos, 0)
        MEDIDAS.append('sem o plugin, {} pontos com ícone próprio mostram o nome do ícone'.format(vistos))

    def test_calco_do_azimute_sem_plugin(self):
        erros = reprovacoes(self.res_calco, self.codigo_calco, self.calco, self.tipos_calco)
        self.assertEqual(erros, [], ' | '.join(erros[:40]))
        rota = self.res_calco['tipos']['line']['formularios'][self.caps_calco['line'][0]]
        self.assertIn(CM.NOME_ABA_AZIMUTE, rota['abas'])
        self.assertNotIn(F.NOME_ABA, rota['abas'])  # o calco não tem tabela de fotos

    def test_com_plugin_o_mesmo_formulario(self):
        self.assertEqual(self.codigo_com, 0, self.res_com.get('etapa'))
        self.assertIn('Calco.guardiao', self.res_com['modulos_ebgeo'])
        for tipo, r in self.res['tipos'].items():
            for eid, fo in r['formularios'].items():
                com = self.res_com['tipos'][tipo]['formularios'][eid]
                self.assertEqual((fo['abas'], fo['visiveis'], fo['rotulos'], fo['imgs']),
                                 (com['abas'], com['visiveis'], com['rotulos'], com['imgs']), (tipo, eid))
                self.assertEqual(com['mudou_ao_salvar'], {}, (tipo, eid))
        from qgis.PyQt.QtGui import QImage
        iguais, total = 0, 0
        for tipo, ids in self.caps.items():
            for eid in ids:
                a = QImage(os.path.join(SAIDA, 'nativo_{}_{}_sem_plugin.png'.format(tipo, eid[:8])))
                b = QImage(os.path.join(SAIDA, 'nativo_{}_{}_com_plugin.png'.format(tipo, eid[:8])))
                self.assertFalse(a.isNull() or b.isNull(), (tipo, eid))
                total += 1
                dif = sum(1 for y in range(30, min(a.height(), b.height()), 2) for x in range(0, min(a.width(), b.width()), 2)
                          if a.pixel(x, y) != b.pixel(x, y))
                iguais += dif == 0
        MEDIDAS.append('capturas com e sem o plugin: {} de {} idênticas abaixo do cabeçalho'.format(iguais, total))
        self.assertEqual(iguais, total)

    def test_mudar_so_o_nome_nao_muda_outra_coluna_nem_pixel(self):
        """
        Em todas as feições: o nome mudado pelo nativo e salvo no arquivo; atualizado_em avança
        (valor padrão now() na atualização); nenhuma outra coluna muda, nem a caixa da cor; o
        desenho fica igual pixel a pixel.
        """
        editado = os.path.join(TMP, 'nome_editado.gpkg')
        shutil.copy(self.importado, editado)
        res, codigo = rodar_sem_plugin(editado, mudar_nome=True)
        self.assertEqual(codigo, 0, res.get('etapa'))
        erros, n, por_coluna, pixels = [], 0, {}, {}
        for tipo in TIPOS:
            self.assertTrue(res.get('gravado_' + tipo), tipo)
            antes, _n = feicoes(self.importado, tipo)
            depois, _n = feicoes(editado, tipo)
            geometrias = [{str(f['ebgeo_id']): f.geometry().asWkt(8) for f in QgsVectorLayer(
                '{}|layername={}'.format(c, schema.TIPOS[tipo]['tabela']), tipo, 'ogr').getFeatures()}
                for c in (self.importado, editado)]
            for eid in res['tipos'][tipo]['formularios']:
                n += 1
                a, d = antes[eid], depois[eid]
                for col in a:
                    if col in ('nome', 'atualizado_em') or col.startswith('__'):
                        continue
                    va, vd = a[col], d[col]
                    if col in JSON_COLS[tipo]:
                        va, vd = _json(va), _json(vd)
                    if not _iguais(va, vd):
                        por_coluna[tipo + '.' + col] = por_coluna.get(tipo + '.' + col, 0) + 1
                        erros.append('{} {}: {} {!r} virou {!r}'.format(tipo, eid[:8], col, va, vd))
                if geometrias[0].get(eid) != geometrias[1].get(eid):
                    erros.append('{} {}: geometria mudou'.format(tipo, eid[:8]))
                if d['nome'] != '{} (editado)'.format(a['nome'] or ''):
                    erros.append('{} {}: nome {!r}'.format(tipo, eid[:8], d['nome']))
                ta, td = a['atualizado_em'], d['atualizado_em']
                if td is None or (hasattr(td, 'isNull') and td.isNull()) or not (ta is None or td > ta):
                    erros.append('{} {}: atualizado_em não avançou ({} para {})'.format(tipo, eid[:8], ta, td))
            ia, ext = desenhar(self.importado, tipo)
            idp, _e = desenhar(editado, tipo, ext)  # a mesma janela nos dois
            dif = _pixels_diferentes(ia, idp)
            if dif:
                pixels[tipo] = dif
                erros.append('{}: {} pixels diferentes no desenho'.format(tipo, dif))
        MEDIDAS.append('mudar só o nome pelo nativo e salvar, {} feições dos 14 tipos: {} reprovações; colunas mudadas '
                       '{}; pixels diferentes por tipo {}'.format(n, len(erros), por_coluna or 'nenhuma', pixels or 'nenhum'))
        self.assertEqual(erros, [], ' | '.join(erros[:30]))
        # a régua do desenho reprova a saída real degradada: uma borda engrossada num polígono
        pior = os.path.join(TMP, 'nome_editado_pior.gpkg')
        shutil.copy(editado, pior)
        from osgeo import ogr
        ds = ogr.Open(pior, 1)
        ds.ExecuteSQL("UPDATE polygon SET line_width = 9 WHERE nome LIKE 'Hachura cross%'")
        ds = None
        ia, ext = desenhar(editado, 'polygon')
        ip, _e = desenhar(pior, 'polygon', ext)
        dif = _pixels_diferentes(ia, ip)
        MEDIDAS.append('pior caso do desenho (borda de 2 para 9 px num polígono): {} pixels diferentes'.format(dif))
        self.assertGreater(dif, 0)

    def test_retrato_de_antes_reprova(self):
        """O código de 86f7d3b (formulário autogerado) não passa na régua."""
        res, codigo = rodar_sem_plugin(self.antes)
        erros = reprovacoes(res, codigo, self.antes)
        por_tipo = {t: sum(1 for e in erros if e.startswith(t + ' ') or e.startswith(t + ':')) for t in TIPOS}
        visiveis = {t: len(next(iter(res['tipos'][t]['formularios'].values()))['visiveis']) for t in TIPOS
                    if res['tipos'].get(t, {}).get('formularios')}
        MEDIDAS.append('retrato de antes: {} reprovações, todos os 14 tipos reprovados: {}; campos à mostra por '
                       'feição antes: {}'.format(len(erros), all(por_tipo.values()), visiveis))
        self.assertTrue(all(por_tipo.values()), por_tipo)
        self.assertTrue(any('layout AutoGenerated' in e for e in erros))
        self.assertTrue(any("visíveis a mais ['atributos'" in e or "'bitmap_b64'" in e for e in erros))

    def test_pior_caso_widget_do_plugin_reprova(self):
        def injeta(vl):
            vl.setEditorWidgetSetup(vl.fields().indexOf('label_text'), QgsEditorWidgetSetup('EBGeoSidc', {}))
        caminho = _degradar(self.importado, 'widget', 'point', injeta)
        res, codigo = rodar_sem_plugin(caminho, tipos=('point',), timeout=180)
        erros = reprovacoes(res, codigo, caminho, ('point',))
        MEDIDAS.append('pior caso, widget do plugin no estilo do Ponto: saída {}, etapa "{}", {} reprovações'.format(
            codigo, res.get('etapa'), len(erros)))
        self.assertTrue(erros)
        self.assertTrue(any('widget não nativo em label_text' in e or 'processo saiu' in e for e in erros), erros[:5])

    def _aba(self, vl, nome):
        fc = vl.editFormConfig()
        return fc, [a for a in fc.tabs() if a.name() == nome][0]

    def test_pior_caso_aba_fotos_sem_condicao_reprova(self):
        def apaga(vl):
            fc, aba = self._aba(vl, F.NOME_ABA)
            aba.setVisibilityExpression(QgsOptionalExpression())
            vl.setEditFormConfig(fc)
        caminho = _degradar(self.importado, 'fotos_condicao', 'point', apaga)
        res, codigo = rodar_sem_plugin(caminho, tipos=('point',))
        erros = reprovacoes(res, codigo, caminho, ('point',))
        self.assertTrue(any(e.startswith('point ') and 'abas' in e for e in erros), erros[:5])

    def test_pior_caso_lista_de_fotos_apagada_reprova(self):
        def apaga(vl):
            from qgis.core import QgsAttributeEditorTextElement
            fc, aba = self._aba(vl, F.NOME_ABA)
            self.assertEqual(len(aba.children()), 2)  # o texto com a lista e o espaçador
            aba.clear()  # o texto com a lista das fotos vira um texto fixo
            t = QgsAttributeEditorTextElement('Fotos', aba)
            t.setText('Fotos anexas')
            aba.addChildElement(t)
            vl.setEditFormConfig(fc)
        caminho = _degradar(self.importado, 'fotos_lista', 'point', apaga)
        res, codigo = rodar_sem_plugin(caminho, tipos=('point',))
        erros = reprovacoes(res, codigo, caminho, ('point',))
        self.assertTrue(any('0 foto(s) na aba Fotos, esperadas 3' in e for e in erros), erros[:5])

    def test_pior_caso_rotulo_sem_condicao_reprova(self):
        def apaga(vl):
            fc, aba = self._aba(vl, 'Etiqueta')
            for filho in aba.children():
                if hasattr(filho, 'setVisibilityExpression'):
                    filho.setVisibilityExpression(QgsOptionalExpression())
            vl.setEditFormConfig(fc)
        caminho = _degradar(self.importado, 'rotulo', 'polygon', apaga)
        res, codigo = rodar_sem_plugin(caminho, tipos=('polygon',))
        erros = reprovacoes(res, codigo, caminho, ('polygon',))
        self.assertTrue(any("visíveis a mais ['label_" in e for e in erros), erros[:5])


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06-completo-3.0.ebgeo ausente')
class TesteDock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(TMP, 'dock.gpkg')
        importar(cls.caminho)
        estilizar_importado(cls.caminho)
        cls.iface = get_iface()
        cls.camadas = {}
        for tipo in TIPOS:
            vl = QgsVectorLayer('{}|layername={}'.format(cls.caminho, schema.TIPOS[tipo]['tabela']), schema.TIPOS[tipo]['nome_pt'], 'ogr')
            vl.setCustomProperty(PROP_CAMINHO, cls.caminho)
            vl.setCustomProperty(PROP_TIPO, tipo)
            QgsProject.instance().addMapLayer(vl)
            cls.camadas[tipo] = vl
        cls.painel = PainelCalco(cls.iface)
        cls.painel.setParent(None)
        cls.painel.resize(440, 980)
        cls.painel.show()

    def tearDown(self):
        for vl in self.camadas.values():
            if vl.isEditable():
                vl.rollBack()
        _app.processEvents()

    def _mostrar(self, tipo, nome=None, eid=None):
        vl = self.camadas[tipo]
        if eid is None:
            eid = _ids_por_nome(self.caminho, tipo, nome)[0]
        self.painel._camada_mudou(vl)
        self.painel.mostrar_feicao(vl, eid)
        self.painel._selecao_mudou()
        _app.processEvents()
        return vl, eid

    def _capturar(self, nome, alvo=None):
        from qgis.PyQt.QtWidgets import QScrollArea
        self.painel.show()
        _app.processEvents()
        sc = self.painel.findChild(QScrollArea)
        if alvo is not None:  # o bloco rico fica abaixo dos atributos: rola até ele
            sc.verticalScrollBar().setValue(alvo.mapTo(sc.widget(), alvo.rect().topLeft()).y() - 120)
        else:
            sc.verticalScrollBar().setValue(0)
        _app.processEvents()
        from Calco.ui.blocos.previa import esperar
        esperar(self.painel)  # a amostra do estilo desenha fora da interface
        self.painel.grab().save(os.path.join(SAIDA, nome))

    def _blocos(self, nome):
        from qgis.PyQt.QtWidgets import QWidget
        return [w for w in self.painel.form_host.findChildren(QWidget, nome) if w.isVisibleTo(self.painel.form_host)]

    def test_campos_conforme_a_especificacao(self):
        n = 0
        for tipo in TIPOS:
            spec = esp.formulario(tipo)
            atributos, nomes = feicoes(self.caminho, tipo)
            for eid, attrs in list(atributos.items())[:6]:
                self._mostrar(tipo, eid=eid)
                vis, _rot, _abas = esperado(spec, attrs, nomes)
                self.assertEqual(self.painel.campos_visiveis(), vis, (tipo, eid))
                self.assertFalse(self.painel.barra_edicao.isHidden(), tipo)
                n += 1
        MEDIDAS.append('dock: {} feições dos 14 tipos com os campos da especificação'.format(n))

    def test_fotos_no_dock(self):
        from Calco.ui.blocos import comuns as B
        self._mostrar('point', 'Ponto com três fotos')
        blocos = self._blocos('EBGeoFotos')
        self.assertEqual(len(blocos), 1)
        self.assertEqual([f['nome'] for f in blocos[0].fotos],
                         ['Foto da posição (JPEG).jpg', 'Croqui à mão.png', 'Vista aérea.jpg'])
        self._capturar('dock_point_fotos.png', blocos[0])
        abertas = []
        original = B.QDesktopServices

        class Falso:
            @staticmethod
            def openUrl(url):
                abertas.append(url.toLocalFile())
                return True
        B.QDesktopServices = Falso
        try:
            blocos[0].botoes_abrir[1].click()
        finally:
            B.QDesktopServices = original
        self.assertEqual(len(abertas), 1)
        with open(abertas[0], 'rb') as fh:
            self.assertEqual(fh.read()[:8], b'\x89PNG\r\n\x1a\n')
        self.assertTrue(abertas[0].endswith('Croqui à mão.png'))
        # nada se apaga: a foto continua no calco e a camada não entrou em edição
        self.assertEqual(len(F.fotos_da_feicao(self.caminho, _ids_por_nome(self.caminho, 'point', 'Ponto com três fotos')[0])), 3)
        self.assertFalse(self.camadas['point'].isEditable())
        textos = [b.text() for b in self.painel.findChildren(type(blocos[0].botoes_abrir[0]))]
        self.assertFalse([t for t in textos if 'pagar' in t or 'xcluir' in t or 'emover' in t], textos)
        # sem foto, a seção some
        self._mostrar('point', 'Posto de Comando Avançado')
        self.assertEqual(self._blocos('EBGeoFotos'), [])
        MEDIDAS.append('dock, fotos: 3 miniaturas lidas do GeoPackage, Abrir gravou {} bytes e a foto ficou no calco'.format(
            os.path.getsize(abertas[0])))

    def test_azimute_no_dock_abre_o_painel_em_edicao(self):
        from qgis.utils import plugins
        from Calco.azimute.ferramenta import AzimuteDistancia
        from Calco.azimute.painel import EDITAR
        ctl = AzimuteDistancia(self.iface)
        plugins['ebgeo_teste_comuns'] = types.SimpleNamespace(azimuteDistancia=ctl)
        try:
            vl, eid = self._mostrar('line', 'Rota polar em milésimos e km')
            blocos = self._blocos('EBGeoResumoAzimute')
            self.assertEqual(len(blocos), 1)
            self.assertIn('Rota</b>: 3 perna(s), azimutes em milésimos no Norte Magnético (NM), distâncias em km',
                          blocos[0].resumo.text())
            self._capturar('dock_line_rota_azimute.png', blocos[0])
            blocos[0].botao.click()
            _app.processEvents()
            p = ctl.painel
            self.assertIsNotNone(p)
            self.assertEqual(p.modo, EDITAR)
            self.assertEqual(p.alvo, (vl, self.painel.fid))
            self.assertEqual([(l['azimuth'], l['distance']) for l in p.estado['legs']], [(800, 1.5), (1600, 2), (3200, 0.8)])
            self.assertEqual(p.estado['angularUnit'], 'mils')
            # sem construção, sem a seção
            linhas, _nomes = feicoes(self.caminho, 'line')
            self._mostrar('line', eid=[e for e, a in linhas.items() if _pernas(a) is None][0])
            self.assertEqual(self._blocos('EBGeoResumoAzimute'), [])
        finally:
            plugins.pop('ebgeo_teste_comuns', None)
            ctl.unload()

    def test_azimute_aberto_pelo_dock_grava_no_buffer(self):
        """O Salvar do Azimute aberto pelo "Editar pernas..." entra no buffer do dock: Descartar
        volta, e só o Salvar do dock grava no calco. A ferramenta solta segue gravando direto."""
        from qgis.utils import plugins
        from Calco.azimute.ferramenta import AzimuteDistancia
        ctl = AzimuteDistancia(self.iface)
        plugins['ebgeo_teste_comuns'] = types.SimpleNamespace(azimuteDistancia=ctl)

        def pernas(v):
            v = json.loads(v) if isinstance(v, str) else v
            return [(l['azimuth'], l['distance']) for l in v['legs']]

        def disco(eid):
            lyr = QgsVectorLayer('{}|layername=line'.format(self.caminho), 'r', 'ogr')
            return pernas(next(lyr.getFeatures("\"ebgeo_id\" = '{}'".format(eid)))['azimute_distancia'])
        buffer = lambda vl, eid: pernas(next(vl.getFeatures("\"ebgeo_id\" = '{}'".format(eid)))['azimute_distancia'])
        try:
            vl, eid = self._mostrar('line', 'Rota polar em milésimos e km')
            antes = disco(eid)
            self._blocos('EBGeoResumoAzimute')[0].botao.click()
            _app.processEvents()
            p = ctl.painel
            estado = p.estado_publico()
            estado['legs'][0]['distance'] = 9.5
            p.salvarPedido.emit(estado)
            _app.processEvents()
            self.assertTrue(vl.isEditable(), 'o Salvar do Azimute devia entrar no buffer do dock')
            self.assertEqual(disco(eid), antes, 'nada vai ao disco antes do Salvar do dock')
            self.assertEqual(buffer(vl, eid)[0][1], 9.5)
            self.assertFalse(self.painel.botao_descartar.isHidden())
            self.assertTrue(self.painel.botao_descartar.isEnabled())
            self.assertTrue(self.painel.descartar())
            _app.processEvents()
            self.assertFalse(vl.isEditable())
            self.assertEqual(disco(eid), antes)
            self.assertEqual(buffer(vl, eid), antes)
            # de novo, e o Salvar do dock grava
            self._mostrar('line', 'Rota polar em milésimos e km')
            self._blocos('EBGeoResumoAzimute')[0].botao.click()
            _app.processEvents()
            estado = ctl.painel.estado_publico()
            estado['legs'][0]['distance'] = 7.25
            ctl.painel.salvarPedido.emit(estado)
            _app.processEvents()
            self.assertEqual(disco(eid), antes)
            self.assertTrue(self.painel.salvar())
            _app.processEvents()
            self.assertEqual(disco(eid)[0][1], 7.25)
            self.assertFalse(vl.isEditable())
            # a ferramenta solta (seleção no mapa, sem o dock) grava direto, como antes; e devolve
            # a construção da fixture para os outros testes
            ctl._abrir_edicao(vl, next(vl.getFeatures("\"ebgeo_id\" = '{}'".format(eid))).id())
            estado = ctl.painel.estado_publico()
            estado['legs'][0]['distance'] = antes[0][1]
            ctl.painel.salvarPedido.emit(estado)
            _app.processEvents()
            self.assertFalse(vl.isEditable())
            self.assertEqual(disco(eid), antes)
        finally:
            plugins.pop('ebgeo_teste_comuns', None)
            ctl.unload()

    def test_buffer_salvar_e_descartar(self):
        vl, eid = self._mostrar('polygon', 'Hachura cross')
        self._capturar('dock_polygon_hachura.png')
        w = self.painel.widgets['line_width']
        w.setValue(4)
        self.painel._gravar_pendentes()
        self.assertTrue(vl.isEditable())
        disco = lambda: next(QgsVectorLayer('{}|layername=polygon'.format(self.caminho), 'r', 'ogr').getFeatures(
            "\"ebgeo_id\" = '{}'".format(eid)))['line_width']
        antes = disco()
        self.assertNotEqual(antes, 4)
        self.assertTrue(self.painel.salvar())
        _app.processEvents()
        self.assertEqual(disco(), 4)
        self.assertFalse(vl.isEditable())
        self._mostrar('polygon', 'Hachura cross')
        self.painel.widgets['hatch_enabled'].setChecked(False)
        self.painel._gravar_pendentes()
        self.assertNotIn('hatch_type', self.painel.campos_visiveis())
        self.assertTrue(self.painel.descartar())
        _app.processEvents()
        self.assertFalse(vl.isEditable())
        self.assertTrue(next(vl.getFeatures("\"ebgeo_id\" = '{}'".format(eid)))['hatch_enabled'])

    def test_guardiao_reverte_a_bloqueada_editada_pela_tabela(self):
        from Calco import guardiao
        vl = self.camadas['polygon']
        g = guardiao.garantir(vl, 'polygon')
        self.assertIsNotNone(g)
        f = next(vl.getFeatures("\"nome\" = 'Hachura vertical'"))
        antes = f['line_width']
        vl.startEditing()
        vl.beginEditCommand('tabela de atributos')  # o delegado da tabela grava assim
        vl.changeAttributeValue(f.id(), vl.fields().indexOf('line_width'), 9)
        vl.endEditCommand()
        self.assertEqual(vl.getFeature(f.id())['line_width'], antes)
        self.assertEqual(g.revertidas, 1)
        # a não bloqueada passa
        f2 = next(vl.getFeatures("\"nome\" = 'Hachura cross'"))
        vl.beginEditCommand('tabela de atributos')
        vl.changeAttributeValue(f2.id(), vl.fields().indexOf('line_width'), 9)
        vl.endEditCommand()
        self.assertEqual(vl.getFeature(f2.id())['line_width'], 9)

    def test_icone_personalizado_legivel_no_dock(self):
        vl, eid = self._mostrar('point', 'Ponto com Ícone Alfa')
        cb = self.painel.widgets['marker_symbol']
        self.assertEqual(cb.currentText(), 'Ícone personalizado: Ícone Alfa')
        self.assertFalse(cb.itemIcon(cb.currentIndex()).isNull(), 'a miniatura do ícone devia aparecer no dock')
        self._capturar('dock_point_icone_personalizado.png')

    def test_linhas_de_altura_uniforme(self):
        """Na seção do dock, os campos de uma linha (texto, número, lista, cor) têm a mesma altura e o
        mesmo passo entre si: o botão de cor não alarga a linha dele (Marcador do Ponto, Texto)."""
        from qgis.PyQt.QtWidgets import QPlainTextEdit
        medidas = []
        for tipo, nome in (('point', 'Posto de Comando Avançado'), ('text', None)):
            if nome is None:
                self._mostrar(tipo, eid=_ids_por_nome(self.caminho, tipo, None)[0])
            else:
                self._mostrar(tipo, nome)
            por_layout = {}
            for el, _c, fl, w, _r in self.painel._linhas:
                if w.isVisibleTo(self.painel) and isinstance(el, esp.Campo) and not isinstance(w, QPlainTextEdit)                         and type(w).__name__ != 'QLabel':
                    y = w.mapTo(self.painel, w.rect().topLeft()).y()
                    por_layout.setdefault(id(fl), []).append((y, w.height(), el.coluna))
            for linhas in por_layout.values():
                linhas.sort()
                alturas = {h for _y, h, _c in linhas}
                passos = {b[0] - a[0] for a, b in zip(linhas, linhas[1:])}
                medidas.append((tipo, sorted(alturas), sorted(passos)))
                self.assertEqual(len(alturas), 1, (tipo, linhas))
                self.assertLessEqual(len(passos), 1, (tipo, linhas))
        MEDIDAS.append('dock, altura e passo das linhas por seção: {}'.format(medidas))

    def test_capturas_do_dock(self):
        self._mostrar('point', 'Posto de Comando Avançado')
        self._capturar('dock_point.png')
        self._mostrar('text', eid=_ids_por_nome(self.caminho, 'text', None)[0])
        self._capturar('dock_text.png')
        vl, eid = self._mostrar('polygon', 'Hachura vertical')  # bloqueada
        self.assertFalse(self.painel.widgets['fill_color'].isEnabled())
        self._capturar('dock_polygon_bloqueada.png')


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
