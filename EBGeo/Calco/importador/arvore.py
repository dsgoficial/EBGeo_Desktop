# -*- coding: utf-8 -*-
"""
Árvore de camadas do calco importado (QGIS): armazenar por tipo, apresentar
por camada EBGeo (seção 2 de EBGeo/Calco/ARQUITETURA.md).

- grupo do atlas (nome do arquivo), mutuamente exclusivo: o Web mostra um
  mapa por vez, e o currentMap abre ligado;
- um grupo por mapa, na ordem de mapOrder unida às chaves;
- um subgrupo por camada EBGeo, em ordem crescente de `order` de cima para
  baixo; visible é o check do subgrupo, opacity vira setOpacity e locked
  vira setReadOnly;
- dentro do subgrupo, uma QgsVectorLayer por tipo não vazio, apontando para
  a tabela do tipo com filtro de mapa e camada;
- materialização preguiçosa: só o mapa ativo nasce com camadas; os outros
  ficam como grupo vazio "(carregar)" e são criados ao ligar o grupo;
- ordem de desenho customizada pela pilha por tipo do Web (PILHA_DESENHO);
- feição com visivel falso e membro de grupo EBGeo oculto saem por regra
  no renderer (e na condição de exibição do rótulo).
"""
import importlib
import logging
import os

from osgeo import ogr

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsLayerTreeGroup, QgsLayerTreeLayer, QgsRuleBasedRenderer,
    QgsNullSymbolRenderer, QgsVectorLayerSimpleLabeling, QgsRuleBasedLabeling, QgsPalLayerSettings,
    QgsProperty, QgsMapLayer,
)

from .. import schema, gpkg

_log = logging.getLogger('EBGeo.Calco.importador')

# mesmas chaves de Calco/calco.py, para as ferramentas reconhecerem a camada
PROP_CAMINHO = 'ebgeo_calco/caminho'
PROP_TIPO = 'ebgeo_calco/tipo'
PROP_ATLAS = 'ebgeo/atlas'
PROP_MAPA = 'ebgeo/mapa'
PROP_CAMADA = 'ebgeo/camada_id'
PROP_ORDEM_MAPA = 'ebgeo/ordem_mapa'
PROP_ORDEM_CAMADA = 'ebgeo/ordem_camada'
PROP_PENDENTE = 'ebgeo/pendente'
PROP_NOTAS = 'ebgeo/notas'
SUFIXO_PENDENTE = ' (carregar)'

TIPOS_TATICOS = ('coordination_line', 'boundary', 'arrow', 'occupied_front')
TIPOS_DESLIGADOS = ('los',)  # o Web desenha a entrada da visada com opacidade zero

COND_VISIVEL = 'if("visivel" IS NULL, true, "visivel")'

_CACHE_ESTILO = {}  # caminho do GPKG -> {tipo: (QML, módulo)}; o ícone custom depende do GPKG
_LIGACOES = {}  # id do grupo do atlas -> função ligada ao sinal (evita coleta pelo GC)


# ---------------------------------------------------------------- leitura das tabelas de apoio

def _linhas(ds, tabela, campos):
    lyr = ds.GetLayerByName(tabela)
    if lyr is None:
        return []
    lyr.ResetReading()
    return [{c: f.GetField(c) for c in campos} for f in lyr]


def ler_apoio(caminho):
    """Mapas, camadas, grupos ocultos e contagens por (mapa, camada, tipo), relendo o GPKG."""
    ds = ogr.Open(caminho)
    if ds is None:
        raise IOError('Não foi possível abrir o GeoPackage {}'.format(caminho))
    try:
        mapas = sorted(_linhas(ds, 'ebgeo_mapa', ['nome', 'ordem', 'base_layer', 'notas_titulo',
                                                  'notas_descricao', 'atual']),
                       key=lambda m: (m['ordem'] if m['ordem'] is not None else 1e9))
        camadas = {}
        for c in _linhas(ds, 'ebgeo_camada', ['mapa', 'camada_id', 'nome', 'visivel', 'bloqueada',
                                              'opacidade', 'ordem']):
            camadas.setdefault(c['mapa'], []).append(c)
        for lst in camadas.values():
            lst.sort(key=lambda c: (c['ordem'] if c['ordem'] is not None else 1e9))
        ocultos = {}
        for g in _linhas(ds, 'ebgeo_grupo', ['mapa', 'grupo_id', 'visivel']):
            if g['visivel'] in (0, False):
                ocultos.setdefault(g['mapa'], []).append(g['grupo_id'])
        contagens = {}
        for tipo, d in schema.TIPOS.items():
            if ds.GetLayerByName(d['tabela']) is None:
                continue
            sql = 'SELECT mapa, camada_id, COUNT(*) AS n FROM "{}" GROUP BY mapa, camada_id'.format(d['tabela'])
            r = ds.ExecuteSQL(sql)
            for f in r:
                contagens.setdefault((f.GetField(0), f.GetField(1)), {})[tipo] = f.GetField(2)
            ds.ReleaseResultSet(r)
        docs = _linhas(ds, 'ebgeo_documento', ['arquivo', 'versao'])
        arquivo = docs[0]['arquivo'] if docs else os.path.basename(caminho)
        return {'mapas': mapas, 'camadas': camadas, 'grupos_ocultos': ocultos,
                'contagens': contagens, 'arquivo': arquivo}
    finally:
        ds = None


# ---------------------------------------------------------------- estilo

def estilizar(layer, tipo, log=None, cache=None):
    """
    Estilo do tipo: estilos_taticos, estilos_pontuais (outros módulos, opcionais)
    ou estilos_formas. Sem o módulo próprio, cai no estilo simples. Devolve o nome do usado.
    Com `cache` (dict), o estilo de um tipo é montado uma vez e copiado como QML para as
    demais camadas do mesmo tipo (o estilo tático leva segundos para montar). A cópia vai sem
    as propriedades personalizadas: com elas, toda camada do tipo herdava o mapa, a camada do
    EBGeo e as ordens da primeira (medido em 2026-10-05 na fixture 06, 80 de 103 camadas).
    """
    if cache is not None and tipo in cache:
        doc_xml, nome = cache[tipo]
        layer.importNamedStyle(doc_xml, _CATEGORIAS_COPIA)
        return nome
    nome = _estilizar(layer, tipo, log or _log)
    from ..calco import aplicar_formulario  # formulário nativo do tipo, quando ele já o tem
    aplicar_formulario(layer, tipo)
    if cache is not None:
        from qgis.core import QgsReadWriteContext
        from qgis.PyQt.QtXml import QDomDocument
        doc_xml = QDomDocument()
        layer.exportNamedStyle(doc_xml, QgsReadWriteContext(), _CATEGORIAS_COPIA)
        cache[tipo] = (doc_xml, nome)
    return nome


# Todas as categorias de estilo menos as propriedades personalizadas (no QGIS 4 a combinação é
# um StyleCategory; o `&` com `~` dá int, que o exportNamedStyle recusa).
_CATEGORIAS_COPIA = QgsMapLayer.StyleCategory(
    QgsMapLayer.StyleCategory.AllStyleCategories.value & ~QgsMapLayer.StyleCategory.CustomProperties.value)


def _estilizar(layer, tipo, log):
    if tipo in TIPOS_TATICOS:
        nome = 'estilos_taticos'
    elif tipo == 'coordination_area':
        nome = 'estilos_area'
    elif schema.TIPOS[tipo]['desenho'] == 'svg':
        nome = 'estilos_pontuais'
    else:
        nome = 'estilos_formas'
    try:
        mod = importlib.import_module('..' + nome, __package__)
        if mod.aplicar_estilo(layer, tipo) is not False:
            return nome
    except ImportError:
        pass
    except Exception as e:  # módulo de outro agente com defeito não derruba a importação
        log.warning('%s falhou no tipo %s (%s); usado o estilo simples', nome, tipo, e)
    from .. import estilos_formas
    estilos_formas.estilo_simples(layer, tipo)
    return 'estilo_simples'


def condicao_exibir(grupos_ocultos=None):
    """Expressão que é verdadeira para a feição que o Web desenha."""
    partes = [COND_VISIVEL]
    # "grupos" é a lista JSON dos ids dos grupos da feição, e chega como LISTA (gravada pelo OGR do
    # importador) ou como TEXTO (gravada pelo QGIS com uma str); from_json(lista) dá nulo sem erro
    grupos = 'CASE WHEN try(array_length("grupos"), -1) >= 0 THEN "grupos" ELSE try(from_json("grupos")) END'
    for gid in grupos_ocultos or []:
        partes.append("NOT coalesce(array_contains({}, '{}'), false)".format(grupos, str(gid).replace("'", "''")))
    return ' AND '.join(partes)


def esconder_por_regra(layer, condicao):
    """Embrulha o renderer e o rótulo da camada numa regra raiz com a condição."""
    r = layer.renderer()
    if r is not None and not isinstance(r, QgsNullSymbolRenderer):
        rb = r.clone() if isinstance(r, QgsRuleBasedRenderer) else QgsRuleBasedRenderer.convertFromRenderer(r)
        if rb is None:
            sub = layer.subsetString()
            layer.setSubsetString('({}) AND ({})'.format(sub, condicao) if sub else condicao)
            return 'subset'
        velha = rb.rootRule()
        raiz = QgsRuleBasedRenderer.Rule(None)
        env = QgsRuleBasedRenderer.Rule(None, 0, 0, condicao, 'Visível no EBGeo')
        for filho in velha.children():
            env.appendChild(filho.clone())
        raiz.appendChild(env)
        novo = QgsRuleBasedRenderer(raiz)
        layer.setRenderer(novo)
    lab = layer.labeling()
    if lab is not None and layer.labelsEnabled():
        if isinstance(lab, QgsVectorLayerSimpleLabeling):
            s = QgsPalLayerSettings(lab.settings())
            dd = s.dataDefinedProperties()
            atual = dd.property(QgsPalLayerSettings.Property.Show)
            expr = condicao
            if atual is not None and atual.isActive() and atual.expressionString():
                expr = '({}) AND ({})'.format(condicao, atual.expressionString())
            dd.setProperty(QgsPalLayerSettings.Property.Show, QgsProperty.fromExpression(expr))
            s.setDataDefinedProperties(dd)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
        elif isinstance(lab, QgsRuleBasedLabeling):
            velha = lab.rootRule()
            raiz = QgsRuleBasedLabeling.Rule(None)
            env = QgsRuleBasedLabeling.Rule(None)
            env.setFilterExpression(condicao)
            env.setDescription('Visível no EBGeo')
            for filho in velha.children():
                env.appendChild(filho.clone())
            raiz.appendChild(env)
            layer.setLabeling(QgsRuleBasedLabeling(raiz))
    return 'regra'


def _salvar_estilo_padrao(layer):
    try:
        res, msg = layer.saveStyleToDatabaseV2(layer.name(), 'EBGeo Desktop: estilo do tipo', True, '')
        ok = not msg
    except AttributeError:
        msg = layer.saveStyleToDatabase(layer.name(), 'EBGeo Desktop: estilo do tipo', True, '')
        ok = not msg
    return ok, msg


def salvar_estilos(caminho, tipos=None, log=None):
    """
    Grava o estilo de cada tipo como padrão no layer_styles do próprio GPKG,
    para a tabela reabrir estilizada num QGIS sem o plugin. Devolve {tipo: módulo usado}.
    """
    log = log or _log
    _CACHE_ESTILO.pop(os.path.abspath(caminho), None)  # GPKG regravado: ícones podem ter mudado
    usados = {}
    for tipo in tipos or list(schema.TIPOS):
        d = schema.TIPOS[tipo]
        lyr = QgsVectorLayer('{}|layername={}'.format(caminho, d['tabela']), d['nome_pt'], 'ogr')
        if not lyr.isValid():
            continue
        modulo = estilizar(lyr, tipo, log)
        esconder_por_regra(lyr, COND_VISIVEL)
        lyr.setDisplayExpression('"nome"')
        lyr.setMapTipTemplate('<b>[% "nome" %]</b><br/>[% "descricao" %]')
        ok, msg = _salvar_estilo_padrao(lyr)
        if not ok:
            log.warning('estilo do tipo %s não foi salvo no GeoPackage: %s', tipo, msg)
        usados[tipo] = modulo
    return usados


# ---------------------------------------------------------------- árvore

def montar_arvore(caminho, projeto=None, nome=None, materializar='atual', log=None):
    """
    Monta a árvore do atlas no projeto e devolve o grupo do atlas.
    materializar: 'atual' (só o mapa ativo) ou 'todos'.
    """
    log = log or _log
    projeto = projeto or QgsProject.instance()
    caminho = os.path.abspath(caminho)
    apoio = ler_apoio(caminho)
    nome = nome or os.path.splitext(apoio['arquivo'])[0]
    raiz = projeto.layerTreeRoot()
    atlas = raiz.insertGroup(0, nome)
    atlas.setCustomProperty(PROP_ATLAS, caminho)

    idx_atual = 0
    for i, m in enumerate(apoio['mapas']):
        atual = bool(m['atual'])
        if atual:
            idx_atual = i
        g = atlas.addGroup(m['nome'])
        g.setCustomProperty(PROP_ATLAS, caminho)
        g.setCustomProperty(PROP_MAPA, m['nome'])
        g.setCustomProperty(PROP_ORDEM_MAPA, i)
        if m['notas_titulo'] or m['notas_descricao']:
            g.setCustomProperty(PROP_NOTAS, '\n\n'.join(x for x in (m['notas_titulo'], m['notas_descricao']) if x))
        if atual or materializar == 'todos':
            _materializar(g, projeto, apoio, log)
        else:
            g.setCustomProperty(PROP_PENDENTE, True)
            g.setName(m['nome'] + SUFIXO_PENDENTE)
        g.setItemVisibilityChecked(atual)
    atlas.setIsMutuallyExclusive(True, idx_atual)
    _ligar(atlas, projeto, log)
    _relacionar_fotos_atlas(atlas, projeto)
    reordenar(projeto)
    return atlas


# ---------------------------------------------------------------- fotos anexas

NOME_FOTOS = 'Fotos anexas'


def camada_fotos(caminho, projeto=None, criar=True):
    """A camada ebgeo_foto do atlas no projeto (sem geometria), com formulário que mostra a foto."""
    projeto = projeto or QgsProject.instance()
    for l in projeto.mapLayers().values():
        if l.customProperty(PROP_TIPO) == 'ebgeo_foto' and l.customProperty(PROP_CAMINHO) == caminho:
            return l
    if not criar:
        return None
    l = QgsVectorLayer('{}|layername=ebgeo_foto'.format(caminho), NOME_FOTOS, 'ogr')
    if not l.isValid() or l.featureCount() == 0:
        return None
    l.setCustomProperty(PROP_TIPO, 'ebgeo_foto')
    l.setCustomProperty(PROP_CAMINHO, caminho)
    _configurar_form_fotos(l)
    projeto.addMapLayer(l, False)
    return l


def _configurar_form_fotos(l):
    from qgis.core import (QgsEditFormConfig, QgsAttributeEditorField, QgsAttributeEditorHtmlElement,
                           QgsEditorWidgetSetup, Qgis)
    nomes = l.fields().names()
    for col, alias in (('ebgeo_id', 'Feição (id EBGeo)'), ('foto_id', 'Foto (id)'), ('nome', 'Nome'),
                       ('mime', 'Tipo'), ('bitmap_b64', 'Imagem (base64)'), ('miniatura_b64', 'Miniatura (base64)')):
        if col in nomes:
            l.setFieldAlias(nomes.index(col), alias)
    for col in ('bitmap_b64', 'miniatura_b64'):
        if col in nomes:
            l.setEditorWidgetSetup(nomes.index(col), QgsEditorWidgetSetup('Hidden', {}))
    fc = l.editFormConfig()
    fc.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    raiz = fc.invisibleRootContainer()
    raiz.clear()
    for col in ('nome', 'mime', 'ebgeo_id', 'foto_id'):
        if col in nomes:
            raiz.addChildElement(QgsAttributeEditorField(col, nomes.index(col), raiz))
    html = QgsAttributeEditorHtmlElement('Foto', raiz)
    html.setHtmlCode(HTML_FOTO)
    raiz.addChildElement(html)
    l.setEditFormConfig(fc)
    l.setDisplayExpression('"nome"')
    l.setMapTipTemplate(HTML_FOTO)


HTML_FOTO = ('<img style="max-width:100%" src="data:[% coalesce("mime", \'image/png\') %];base64,'
             '[% "bitmap_b64" %]"/>')


def html_dica(id_relacao):
    """Maptip da feição: nome, descrição e as miniaturas das fotos anexas pela relação."""
    return ('<b>[% "nome" %]</b><br/>[% "descricao" %]<br/>'
            '[% relation_aggregate(\'{r}\', \'concatenate\', '
            '\'<img height="64" src="data:image/png;base64,\' || coalesce("miniatura_b64", "bitmap_b64") || \'"/> \', '
            'concatenator:=\'\') %]').format(r=id_relacao)


def relacionar_fotos(layer, projeto=None):
    """Relação 1:N camada -> fotos (ebgeo_id), que o formulário automático do QGIS mostra; e o maptip."""
    from qgis.core import QgsRelation
    projeto = projeto or QgsProject.instance()
    fotos = camada_fotos(layer.customProperty(PROP_CAMINHO), projeto)
    if fotos is None:
        layer.setMapTipTemplate('<b>[% "nome" %]</b><br/>[% "descricao" %]')
        return None
    rid = 'ebgeo_fotos_' + layer.id()
    rm = projeto.relationManager()
    if rm.relation(rid).isValid():
        return rm.relation(rid)
    r = QgsRelation()
    r.setId(rid)
    r.setName('Fotos anexas')
    r.setReferencingLayer(fotos.id())
    r.setReferencedLayer(layer.id())
    r.addFieldPair('ebgeo_id', 'ebgeo_id')
    if not r.isValid():
        return None
    rm.addRelation(r)
    layer.setMapTipTemplate(html_dica(rid))
    return r


def _relacionar_fotos_atlas(atlas, projeto):
    caminho = atlas.customProperty(PROP_ATLAS)
    fotos = camada_fotos(caminho, projeto)
    if fotos is not None and projeto.layerTreeRoot().findLayer(fotos.id()) is None:
        pai = atlas.parent() or projeto.layerTreeRoot()
        pai.insertLayer(pai.children().index(atlas) + 1, fotos)
    for no in atlas.findLayers():
        relacionar_fotos(no.layer(), projeto)


def _materializar(g, projeto, apoio, log):
    caminho = g.customProperty(PROP_ATLAS)
    mapa = g.customProperty(PROP_MAPA)
    ordem_mapa = int(g.customProperty(PROP_ORDEM_MAPA) or 0)
    ocultos = apoio['grupos_ocultos'].get(mapa, [])
    cond = condicao_exibir(ocultos)
    pilha_de_cima = list(reversed(schema.PILHA_DESENHO))
    criadas = 0
    for oc, c in enumerate(apoio['camadas'].get(mapa, [])):
        sub = g.addGroup(c['nome'] or c['camada_id'])
        sub.setCustomProperty(PROP_CAMADA, c['camada_id'])
        sub.setItemVisibilityChecked(c['visivel'] not in (0, False))
        n_tipo = apoio['contagens'].get((mapa, c['camada_id']), {})
        for tipo in pilha_de_cima:
            if not n_tipo.get(tipo):
                continue
            d = schema.TIPOS[tipo]
            lyr = QgsVectorLayer(gpkg.uri_camada(caminho, tipo, mapa, c['camada_id']), d['nome_pt'], 'ogr')
            if not lyr.isValid():
                log.warning('camada %s de "%s"/"%s" inválida', tipo, mapa, c['nome'])
                continue
            for k, v in ((PROP_CAMINHO, caminho), (PROP_TIPO, tipo), (PROP_MAPA, mapa),
                         (PROP_CAMADA, c['camada_id']), (PROP_ORDEM_MAPA, ordem_mapa),
                         (PROP_ORDEM_CAMADA, oc)):
                lyr.setCustomProperty(k, v)
            estilizar(lyr, tipo, log, _CACHE_ESTILO.setdefault(caminho, {}))
            esconder_por_regra(lyr, cond)
            op = c['opacidade']
            lyr.setOpacity(1.0 if op is None else max(0.0, min(1.0, float(op))))
            if c['bloqueada'] not in (0, False, None):
                lyr.setReadOnly(True)
            projeto.addMapLayer(lyr, False)
            no = sub.addLayer(lyr)
            if tipo in TIPOS_DESLIGADOS:
                no.setItemVisibilityChecked(False)
            criadas += 1
    g.removeCustomProperty(PROP_PENDENTE)
    g.setName(mapa)
    return criadas


def materializar_mapa(grupo_mapa, projeto=None, log=None):
    """Cria as camadas de um mapa ainda não carregado. Devolve quantas camadas criou."""
    log = log or _log
    projeto = projeto or QgsProject.instance()
    if not grupo_mapa.customProperty(PROP_PENDENTE):
        return 0
    apoio = ler_apoio(grupo_mapa.customProperty(PROP_ATLAS))
    n = _materializar(grupo_mapa, projeto, apoio, log)
    for no in grupo_mapa.findLayers():
        relacionar_fotos(no.layer(), projeto)
    reordenar(projeto)
    return n


def _ligar(atlas, projeto, log):
    """Ao ligar o grupo de um mapa pendente, materializa-o (fora do sinal, pelo laço de eventos)."""
    from qgis.PyQt.QtCore import QTimer

    def ao_mudar(no):
        if isinstance(no, QgsLayerTreeGroup) and no.customProperty(PROP_PENDENTE) and no.itemVisibilityChecked():
            QTimer.singleShot(0, lambda: materializar_mapa(no, projeto, log))

    atlas.visibilityChanged.connect(ao_mudar)
    _LIGACOES[id(atlas)] = (atlas, ao_mudar)


def religar(projeto=None, log=None):
    """Depois de abrir um projeto salvo, religa a materialização preguiçosa dos atlas."""
    projeto = projeto or QgsProject.instance()
    n = 0
    for g in projeto.layerTreeRoot().findGroups(True):
        if g.customProperty(PROP_ATLAS) and isinstance(g.parent(), QgsLayerTreeGroup) \
                and not g.parent().customProperty(PROP_ATLAS) and g.isMutuallyExclusive():
            _ligar(g, projeto, log or _log)
            n += 1
    return n


def reordenar(projeto=None):
    """
    Ordem de desenho customizada: camadas do calco pela pilha por tipo do Web
    (topo primeiro), as demais abaixo, na ordem relativa que já tinham.
    """
    projeto = projeto or QgsProject.instance()
    raiz = projeto.layerTreeRoot()
    atual = raiz.customLayerOrder() if raiz.hasCustomLayerOrder() else raiz.layerOrder()
    vistas = set()
    todas = []
    for l in list(atual) + [n.layer() for n in raiz.findLayers()]:
        if l is not None and l.id() not in vistas:
            vistas.add(l.id())
            todas.append(l)
    pilha = {t: i for i, t in enumerate(schema.PILHA_DESENHO)}
    nossas = [l for l in todas if l.customProperty(PROP_TIPO) in pilha]
    outras = [l for l in todas if l.customProperty(PROP_TIPO) not in pilha]

    def chave(l):
        return (-pilha[l.customProperty(PROP_TIPO)], str(l.customProperty(PROP_CAMINHO) or ''),
                int(l.customProperty(PROP_ORDEM_MAPA) or 0), int(l.customProperty(PROP_ORDEM_CAMADA) or 0))

    nossas.sort(key=chave)
    raiz.setHasCustomLayerOrder(True)
    raiz.setCustomLayerOrder(nossas + outras)
    return nossas + outras


def carregar(caminho, projeto=None, materializar='atual', log=None):
    """Atalho: monta a árvore do GPKG já gravado e devolve o grupo do atlas."""
    return montar_arvore(caminho, projeto, materializar=materializar, log=log)
