# -*- coding: utf-8 -*-
"""
Chave AUSENTE e chave NULA no .ebgeo, em TODO tipo e em TODA propriedade que o importador grava
em coluna: o Desktop desenha o que o Web desenha.

A fixture é o data.json da 06 (feições nascidas pela ferramenta do Web): para cada tipo, as
feições de base, e para cada chave de schema.mapa_web, variantes com a chave ausente, com a chave
nula e com valores de referência (o da fixture, o padrão do esquema, o que o estilo do Desktop dá
ao nulo, e os neutros 1, falso e verdadeiro), gravadas no contêiner do Web.

O Web lê o arquivo pelo próprio código em node (portão, normalização, as camadas MapLibre que ele
registra avaliadas pelo compilador de expressões do MapLibre, as fontes de rótulo e as derivadas:
decorações da Área, desenho da Linha de Coordenação, do Limite, da Seta e da Frente, e o SVG da
declinação), e o gerador de símbolo pontual do Web (o bundle do motor, que é o código do Web)
desenha o militar, a medida e a engenharia com as propriedades como o Web as leu. Duas variantes
com a mesma assinatura desenham igual no Web. O Desktop importa o mesmo arquivo, estiliza como o
importador e desenha cada variante sozinha: duas variantes com os mesmos pixels desenham igual.

A régua é RELACIONAL, e por isso não precisa saber o padrão de ninguém: para cada par de
variantes (ausente e nula, ausente e cada referência, nula e cada referência), "desenha igual" no
Web tem de ser "desenha igual" no Desktop. Divergência é um par em que os dois discordam.

Rodar com o Python do QGIS 4, da raiz do repositório, com EBGEO_WEB (ou EBGEO_WEB_DIR) e node:
    python-qgis.bat EBGeo/Calco/testes/test_chaves_ausentes.py
Variáveis: EBGEO_FIXTURES, EBGEO_WEB, EBGEO_WEB_DIR, EBGEO_NODE, EBGEO_TESTE_SAIDA (a tabela).
"""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
RAIZ_REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpressionContext,
    QgsExpressionContextUtils, QgsMapRendererSequentialJob, QgsMapSettings, QgsProject, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import gpkg, schema  # noqa: E402
from Calco.importador import arvore, escritor, leitor  # noqa: E402
from Calco.exportador import arquivo  # noqa: E402

FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_chaves_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_chaves_calco_')
MEDIDAS = []
ZOOM = 13
SEP = '§'  # separa base, chave e variante no id

# Propriedades que não são da feição desenhada: a identidade e a camada (estrutura do arquivo).
FORA = {'id', 'layerId'}
TIPOS_SVG = ('military_symbol', 'coordination_measure', 'engineering_symbol')
# Bases a mais, quando a chave só desenha num tipo do catálogo (portões no VAB, minas na área
# minada, escalão no Ponto Forte; textos e segunda cor na Linha de Coordenação).
_ROTULO = dict(showLabel=True, labelText='ROTULO', labelOutlineColor='#0000ff')
ATIVADORES = {t: dict(_ROTULO, hatchEnabled=True, hatchType='cross') for t in ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')}
ATIVADORES.update({
    'point': dict(_ROTULO),
    'coordination_area': dict(hatchEnabled=True, hatchType='cross', opacity=1),
    'text': dict(showBackground=True, backgroundFillColor='#ff0000', backgroundBorderColor='#0000ff'),
    'arrow': dict(airmobile=True),
})
BASES_POR_CODIGO = {
    'coordination_area': ('symbol_code', ('151203', '170999-01', '270800', '150000')),
    'coordination_line': ('symbol_code', ('140000', '140200', '290199')),
}


# ---------------------------------------------------------------- o Web em node

def _web_e_node():
    web = os.environ.get('EBGEO_WEB') or os.environ.get('EBGEO_WEB_DIR')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    padrao = os.path.join(os.environ.get('ProgramFiles', ''), 'nodejs', 'node.exe')
    if not node and os.path.exists(padrao):
        node = padrao
    if not web or not os.path.isdir(os.path.join(web, 'frontend')):
        return None, None, 'EBGEO_WEB ausente'
    if not node:
        return None, None, 'node ausente (EBGEO_NODE)'
    return web, node, None


def web_assinaturas(caminho_ebgeo):
    """{id: {'balde', 'props', 'assinatura'}} do arquivo, lido e desenhado pelo Web em node."""
    web, node, motivo = _web_e_node()
    if motivo:
        return None, motivo
    d = tempfile.mkdtemp(prefix='ebgeo_chaves_node_')
    saida = os.path.join(d, 'saida.json')
    r = subprocess.run([node, os.path.join(AQUI, 'web_assinatura.mjs'), os.path.join(web, 'frontend'), caminho_ebgeo,
                        saida, str(ZOOM)], capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-3000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh), None


def assinatura_simbolo(tipo, props):
    """O bitmap que o gerador do Web (bundle do motor) desenha com as propriedades como o Web as leu."""
    from Calco.motor.motor import Motor
    m = Motor.instancia()
    f = {'military_symbol': m.simbolo_militar, 'coordination_measure': m.medida,
         'engineering_symbol': m.engenharia}[tipo]
    try:
        r = f(copy.deepcopy(props))
    except Exception:  # o gerador do Web recusa (qualquer que seja a mensagem): o Web guarda o bitmap de antes
        return 'recusa'
    # os pixels do SVG, não o texto: a cor explícita igual à nativa desenha igual
    from qgis.PyQt.QtCore import QByteArray
    from qgis.PyQt.QtGui import QPainter
    from qgis.PyQt.QtSvg import QSvgRenderer
    w, h = max(1, int(round(2 * r.get('largura', 32)))), max(1, int(round(2 * r.get('altura', 32))))
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(0)
    pintor = QPainter(img)
    QSvgRenderer(QByteArray(r.get('svgWeb', '').encode('utf-8'))).render(pintor)
    pintor.end()
    return json.dumps([_hash(img), r.get('largura'), r.get('altura'), r.get('iconOffset')])


# ---------------------------------------------------------------- variantes

def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


def _literais_do_estilo(texto, coluna):
    """O que o estilo do Desktop dá à coluna nula: número, lógico ou texto (coalesce e CASE)."""
    from Calco.ui import padrao_estilo as pe
    out = list(pe.candidatos(texto, coluna)) + list(pe.candidatos_logicos(texto, coluna))
    out += re.findall(r"coalesce\(\s*\"{}\"\s*,\s*'([^']*)'\s*\)".format(re.escape(coluna)), texto)
    return out


def referencias(tipo, web, coluna, tp, padrao, original, literais):
    """Valores de referência da chave, sem repetição, na grafia do Web."""
    vals = []
    if original is not None:
        vals.append(original)
    if padrao is not None:
        vals.append(json.loads(padrao) if tp == 'json' and isinstance(padrao, str) else padrao)
    vals += literais
    # 1 é o padrão do MapLibre para espessura e opacidade nulas; zero e texto vazio não entram:
    # eles medem como o valor desenha, não como desenha a chave ausente ou nula
    vals += {'real': [1], 'int': [1], 'bool': [False, True]}.get(tp, [])
    # um valor a mais, que desenha diferente dos padrões: sem ele, a chave cujos padrões coincidem
    # nos dois lados pareceria não lida
    if tp == 'real':
        vals.append(2.5)
    elif tp == 'str' and ('olor' in web or web.endswith('Color')):
        vals += ['#ff00ff', '#000000']  # e o preto, o padrão do MapLibre para cor nula
    out = []
    for v in vals:
        if tp == 'real' and isinstance(v, (int, float)) and not isinstance(v, bool):
            v = float(v)
        if not any(type(v) is type(x) and v == x for x in out):
            out.append(v)
    return out[:8]


def bases(doc):
    """{tipo: [feições de base]}: a mais completa de cada tipo, e as de código quando a chave depende dele."""
    por_tipo = {}
    for nome, m in doc['maps'].items():
        for balde, lista in (m.get('features') or {}).items():
            tipo = schema.BALDE_PARA_TIPO.get(balde)
            if tipo is None:
                continue
            for f in lista:
                p = f.get('properties') or {}
                if escritor.geometria_qgis(tipo, f.get('geometry'), copy.deepcopy(p)) is None:
                    continue
                por_tipo.setdefault(tipo, []).append(f)
    out = {}
    for tipo, lista in por_tipo.items():
        chaves = set(schema.mapa_web(tipo))
        rica = max(lista, key=lambda f: sum(1 for k, v in f['properties'].items() if k in chaves and v not in (None, '', [], {})))
        escolhidas = [rica]
        if tipo in BASES_POR_CODIGO:
            k, codigos = BASES_POR_CODIGO[tipo]
            for c in codigos:
                f = next((f for f in lista if f['properties'].get(k) == c), None)
                if f is not None and f is not rica:
                    escolhidas.append(f)
        if tipo in ATIVADORES:
            # a mesma base com o que liga o desenho das chaves que só desenham assim (hachura,
            # rótulo, fundo do texto, aeromóvel)
            f = copy.deepcopy(rica)
            f['properties'].update(ATIVADORES[tipo])
            f['properties']['id'] = rica['properties']['id'] + '-ativada'
            escolhidas.append(f)
        out[tipo] = escolhidas
    return out


def montar_variantes(doc, literais_por_tipo):
    """(data do .ebgeo, imagens, {id: (tipo, id da base, chave, rótulo da variante, valor)})."""
    baldes, mapa_ids = {}, {}
    for tipo, lista in bases(doc).items():
        balde = schema.TIPOS[tipo]['balde']
        tps = {c: (tp, p) for c, tp, p, _w in schema.campos(tipo)}
        for f0 in lista:
            base_id = f0['properties']['id']
            for web, coluna in sorted(schema.mapa_web(tipo).items()):
                if web in FORA:
                    continue
                tp, padrao = tps[coluna]
                lit = literais_por_tipo.get(tipo, {}).get(coluna, [])
                refs = referencias(tipo, web, coluna, tp, padrao, f0['properties'].get(web), lit)
                variantes = [('ausente', None, True), ('nula', None, False)] + \
                    [('ref{}'.format(i), v, False) for i, v in enumerate(refs)]
                for rot, valor, ausente in variantes:
                    f = copy.deepcopy(f0)
                    p = f['properties']
                    vid = SEP.join((base_id, web, rot))
                    p['id'] = vid
                    p['layerId'] = 'default'
                    if ausente:
                        p.pop(web, None)
                    else:
                        p[web] = valor
                    baldes.setdefault(balde, []).append(f)
                    mapa_ids[vid] = (tipo, base_id, web, rot, valor)
    data = {'version': doc['version'], 'mapOrder': ['Auditoria'], 'currentMap': 'Auditoria',
            'maps': {'Auditoria': {'features': baldes, 'layers': {'default': {'name': 'Padrão', 'visible': True, 'order': 0}}}}}
    return data, mapa_ids


# ---------------------------------------------------------------- o Desktop

def desktop_assinaturas(caminho_gpkg, mapa_ids):
    """{id: hash dos pixels} de cada variante desenhada sozinha com o estilo do importador."""
    out = {}
    por_tipo = {}
    for vid, (tipo, base_id, *_r) in mapa_ids.items():
        por_tipo.setdefault(tipo, {}).setdefault(base_id, []).append(vid)
    for tipo, porbase in por_tipo.items():
        vl = QgsVectorLayer(gpkg.uri_camada(caminho_gpkg, tipo), tipo, 'ogr')
        assert vl.isValid(), tipo
        for base_id, vids in porbase.items():
            ext = None
            for vid in vids:
                vl.setSubsetString('"ebgeo_id" = \'{}\''.format(vid.replace("'", "''")))
                for f in vl.getFeatures():
                    bb = f.geometry().boundingBox()
                    if ext is None:
                        ext = QgsRectangle(bb)
                    else:
                        ext.combineExtentWith(bb)
            for vid in vids:
                vl.setSubsetString('"ebgeo_id" = \'{}\''.format(vid.replace("'", "''")))
                out[vid] = _hash(_render(vl, ext))
        vl.setSubsetString('')
    return out


def _render(vl, ext_wgs):
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(360, 270))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    # a escala do zoom em que o Web foi avaliado (ZOOM), centrada na feição: o desenho que muda
    # com o zoom (correção de zoom, tamanho do símbolo) sai na mesma escala dos dois lados
    tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
    c = tr.transformBoundingBox(ext_wgs).center()
    res = 156543.03392804097 / 2 ** ZOOM
    ms.setExtent(QgsRectangle(c.x() - 180 * res, c.y() - 135 * res, c.x() + 180 * res, c.y() + 135 * res))
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.globalScope())
    ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererSequentialJob(ms)
    job.start()
    job.waitForFinished()
    return job.renderedImage()


def _hash(img):
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    return hashlib.sha1(bytes(img.constBits().asarray(img.sizeInBytes()))).hexdigest()


def literais_do_estilo_desktop():
    """{tipo: {coluna: [literais]}} lidos do estilo que o importador grava (arvore.salvar_estilos)."""
    from Calco.ui import padrao_estilo as pe
    cam = os.path.join(TMP, 'estilos.gpkg')
    gpkg.criar_calco(cam, list(schema.TIPOS))
    arvore.salvar_estilos(cam)
    out = {}
    for tipo in schema.TIPOS:
        vl = QgsVectorLayer(gpkg.uri_camada(cam, tipo), tipo, 'ogr')
        if not vl.isValid():
            continue
        texto = pe.texto_do_estilo(vl)
        out[tipo] = {c: _literais_do_estilo(texto, c) for c, tp, _p, _w in schema.campos(tipo)
                     if tp in ('real', 'int', 'bool', 'str')}
    return out


# ---------------------------------------------------------------- a régua

def _classe(sig, g, rot):
    """As variantes que desenham como `rot` (ela inclusive), pelo rótulo."""
    return frozenset(r for r in g if sig[g[r]] == sig[g[rot]])


def comparar(mapa_ids, web, desk):
    """
    Por chave (tipo, base, chave): o que cada lado lê e, quando os DOIS a leem, a classe da
    ausente e a da nula (as variantes que desenham igual a ela) no Web e no Desktop. Divergência é
    classe diferente. Devolve (divergências, lidas pelos dois, só pelo Web, só pelo Desktop,
    comparadas), com a divergência como (tipo, base, chave, variante, classe no Web, classe no Desktop).
    """
    grupos = {}
    for vid, (tipo, base_id, chave, rot, valor) in mapa_ids.items():
        grupos.setdefault((tipo, base_id, chave), {})[rot] = vid
    div, ambos, so_web, so_desk, comparadas, valor = [], set(), set(), set(), set(), []
    for (tipo, base_id, chave), g in sorted(grupos.items()):
        comparadas.add((tipo, chave))
        le_w = len({web[v] for v in g.values()}) > 1
        le_d = len({desk[v] for v in g.values()}) > 1
        if le_w and le_d:
            ambos.add((tipo, chave))
        elif le_w:
            so_web.add((tipo, chave))
            continue
        elif le_d:
            so_desk.add((tipo, chave))
            continue
        else:
            continue
        # referência que os dois lados desenham com regra diferente (o zoom 0 que o Desktop lê como
        # sem âncora, a opacidade 2,5 que um corta e o outro não) mede o VALOR, não a ausência:
        # sai da comparação e vai para a lista à parte
        refs = [r for r in g if r.startswith('ref')]
        ruins = set()
        for i, a in enumerate(refs):
            for b in refs[i + 1:]:
                if (web[g[a]] == web[g[b]]) != (desk[g[a]] == desk[g[b]]):
                    ruins |= {a, b}
        if ruins:
            valor.append((tipo, base_id, chave, sorted(ruins)))
        g2 = {r: v for r, v in g.items() if r not in ruins}
        for rot in ('ausente', 'nula'):
            cw, cd = _classe(web, g2, rot), _classe(desk, g2, rot)
            if cw != cd:
                div.append((tipo, base_id, chave, rot, cw, cd))
    so_web -= ambos
    so_desk -= ambos
    return div, ambos, so_web, so_desk, comparadas, valor


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente (EBGEO_FIXTURES)')
class TesteChavesAusentes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.web_motivo = _web_e_node()[2]
        if cls.web_motivo:
            return
        doc = leitor.abrir(FIXTURE_06)
        cls.literais = literais_do_estilo_desktop()
        cls.data, cls.ids = montar_variantes(doc.data, cls.literais)
        imagens = {}
        for vid, (tipo, base_id, *_r) in cls.ids.items():
            origem = base_id[:-len('-ativada')] if base_id.endswith('-ativada') else base_id
            if origem in doc.imagens:
                imagens[vid] = doc.imagens[origem]
        cls.arquivo = os.path.join(TMP, 'chaves.ebgeo')
        arquivo.gravar(cls.arquivo, cls.data, imagens)
        cls.gpkg = os.path.join(TMP, 'chaves.gpkg')
        escritor.importar(cls.arquivo, cls.gpkg)
        arvore.salvar_estilos(cls.gpkg)
        web, _m = web_assinaturas(cls.arquivo)
        for vid, w in web.items():
            tipo = cls.ids[vid][0]
            if tipo in TIPOS_SVG:
                w['assinatura'] += '|' + assinatura_simbolo(tipo, w['props'])
        cls.web = {vid: w['assinatura'] for vid, w in web.items()}
        cls.web_props = {vid: w['props'] for vid, w in web.items()}
        cls.desk = desktop_assinaturas(cls.gpkg, cls.ids)
        cls.div, cls.ambos, cls.so_web, cls.so_desk, cls.comparadas, cls.valor = comparar(cls.ids, cls.web, cls.desk)
        cls._gravar_tabela()

    @classmethod
    def _gravar_tabela(cls):
        valor = {}
        for vid, (tipo, base_id, chave, rot, v) in cls.ids.items():
            valor[(tipo, base_id, chave, rot)] = v

        def nomes(tipo, base_id, chave, classe):
            return ', '.join(sorted(r if r in ('ausente', 'nula') else repr(valor[(tipo, base_id, chave, r)])
                                    for r in classe))
        linhas = ['\t'.join([t, b, c, rot, nomes(t, b, c, cw), nomes(t, b, c, cd)]) for t, b, c, rot, cw, cd in cls.div]
        with open(os.path.join(SAIDA, 'divergencias.tsv'), 'w', encoding='utf-8') as fh:
            fh.write('tipo\tbase\tchave\tvariante\tdesenha igual no Web\tdesenha igual no Desktop\n')
            fh.write('\n'.join(linhas) + '\n')
            fh.write('\nsó o Web lê: ' + ', '.join(' '.join(x) for x in sorted(cls.so_web)))
            fh.write('\nsó o Desktop lê: ' + ', '.join(' '.join(x) for x in sorted(cls.so_desk)) + '\n')
            fh.write('\nreferências com regra de valor diferente (fora da comparação): ' + '; '.join(
                '{} {} {}'.format(t, c, ', '.join(repr(valor[(t, b, c, r)]) for r in rs)) for t, b, c, rs in cls.valor) + '\n')
        with open(os.path.join(SAIDA, 'variantes.json'), 'w', encoding='utf-8') as fh:
            json.dump({'ids': {k: list(v) for k, v in cls.ids.items()}, 'web': cls.web, 'desk': cls.desk,
                       'web_props': cls.web_props}, fh, ensure_ascii=False, default=str)
        shutil.copy(cls.arquivo, os.path.join(SAIDA, 'chaves.ebgeo'))
        MEDIDAS.append('{} chaves em {} tipos comparadas ({} variantes): {} lidas pelos dois, {} só pelo Web, {} só pelo '
                       'Desktop; {} classes divergentes em {} chaves'.format(
                           len(cls.comparadas), len({t for t, _c in cls.comparadas}), len(cls.ids), len(cls.ambos),
                           len(cls.so_web), len(cls.so_desk), len(cls.div), len({(d[0], d[2]) for d in cls.div})))

    def setUp(self):
        if self.web_motivo:
            self.skipTest(self.web_motivo)

    def test_desktop_desenha_como_o_web(self):
        chaves = {(d[0], d[2]) for d in self.div}
        self.assertEqual(sorted(chaves - set(PENDENTES)), [])
        # a pendência que deixou de divergir sai da lista (a lista não envelhece em silêncio)
        self.assertEqual(sorted(set(PENDENTES) - chaves), [])

    def test_regua_exercita_e_compara_todas_as_chaves(self):
        todas = {(t, w) for t in schema.TIPOS for w in schema.mapa_web(t) if w not in FORA}
        self.assertEqual(todas - self.comparadas, set())
        self.assertGreater(len(self.ambos), 150)

    def test_ida_e_volta_devolve_a_chave_ausente_ausente(self):
        """A feição não editada volta do exportador como veio: sem a chave, com a nula nula."""
        from Calco.exportador import desenho, montador
        exp = montador.montar(self.gpkg, montador.ESCOPO_TUDO, None, desenho.GeradorDesenho())
        volta_arq = os.path.join(TMP, 'chaves_volta.ebgeo')
        arquivo.gravar(volta_arq, exp.data, exp.imagens)
        volta = {f['properties']['id']: f['properties'] for m in leitor.abrir(volta_arq).data['maps'].values()
                 for lista in (m.get('features') or {}).values() for f in lista}
        ida = {f['properties']['id']: f['properties'] for lista in self.data['maps']['Auditoria']['features'].values()
               for f in lista}
        self.assertEqual(set(volta), set(ida))
        dif = sorted(k for k in ida if ida[k] != volta[k])
        self.assertEqual(dif, [])
        ausentes = sum(1 for k, (t, b, chave, rot, v) in self.ids.items() if rot == 'ausente' and chave not in volta[k])
        self.assertEqual(ausentes, sum(1 for v in self.ids.values() if v[3] == 'ausente'))
        MEDIDAS.append('ida e volta: {} feições iguais, {} chaves ausentes voltaram ausentes'.format(len(ida), ausentes))


# Divergência conhecida que espera o aval do chefe: o Web desenha hatchType nulo (e vazio) como
# 'diagonal-right' quando hatchEnabled é verdadeiro (orDefault de HATCH_IMAGE_EXPRESSION); o estilo
# do Desktop não desenha a hachura sem tipo, como registra a decisão de 2026-10-05 sobre a hachura
# (ARQUITETURA.md, seção 11). O importador não resolve: a nula tem de ficar nula.
PENDENTES = {(t, 'hatchType'): 'hachura sem tipo: decisão do chefe' for t in ('circle', 'ellipse', 'polygon', 'rectangle', 'sector')}
# O Web lê a âncora nula do tamanho do Ponto como zoom 0 (POINT_SIZE com anchorDefault 0, e
# `props.sizeCreatedAtZoom || 0` em AddPointControl.applyZoomCorrections): com a correção ligada, o
# ponto sem âncora sai no teto de 500 px. O rótulo do mesmo ponto lê a âncora ausente como "não
# escala" (labelCreatedAtZoom). O Desktop desenha o ponto sem âncora sem escala. Portar exige o teto
# de 500 px no tamanho no terreno do Desktop, que hoje não tem teto, ou o Web pode estar errado:
# fica para o chefe.
PENDENTES[('point', 'sizeCreatedAtZoom')] = 'âncora nula do Ponto: o Web satura em 500 px; corrigir o Web ou portar o teto'


def tearDownModule():
    print('\n--- medidas ---')
    for t in MEDIDAS:
        print(t)
    print('tabela em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
