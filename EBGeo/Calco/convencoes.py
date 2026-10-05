# -*- coding: utf-8 -*-
"""
Quadro de convenções do calco num layout de impressão do QGIS.

Uma linha por símbolo DISTINTO das camadas do calco que o mapa do layout desenha (opcionalmente
só das feições na extensão do mapa), com a figura do símbolo e o nome em português, agrupada por
tipo (Símbolos Militares, Medidas de Coordenação, Símbolos de Engenharia, Linhas, Áreas, Outros)
e ordenada pelo nome.

Por que itens de layout e não a legenda nativa (QgsLayoutItemLegend): os estilos do calco são
um símbolo só por camada (pontuais: marcador SVG com o desenho lido do campo "svg") ou regras
cujo desenho é Geometry Generator sobre os atributos da feição. A legenda desenha a amostra SEM
feição, então os campos chegam nulos: medido no QGIS 4.0.0 com a fixture 06, a legenda com
"Filtrar legenda pelo conteúdo do mapa" dá uma linha por camada nos pontuais (com o x vermelho
de símbolo sem desenho), um traço reto ou um retângulo azul em cada regra das linhas, e nenhuma
linha por SIDC. O quadro, então, é feito de itens nativos do layout:
  - figura do símbolo pontual: QgsLayoutItemPicture com o SVG já gravado na feição, embutido
    como 'base64:' (o motor não é chamado; sem SVG, o PNG do .ebgeo);
  - figura de linha e de área: o PRÓPRIO estilo nativo da camada (renderer e rótulos) desenhado
    sobre uma geometria de amostra curta, com os atributos de desenho da feição, num PNG
    embutido no QgsLayoutItemPicture;
  - nome e títulos: QgsLayoutItemLabel; moldura: QgsLayoutItemShape; tudo num QgsLayoutItemGroup.
Itens nativos com o conteúdo embutido: o quadro sobrevive a salvar e reabrir o projeto e abre
num QGIS sem o plugin. Ele não se atualiza sozinho: a ação de novo o refaz no mesmo lugar.
"""
import base64
import json
import math
import unicodedata

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpressionContext,
    QgsExpressionContextUtils, QgsFeature, QgsFeatureRequest, QgsField, QgsFields, QgsFillSymbol,
    QgsGeometry, QgsLayoutItem, QgsLayoutItemGroup, QgsLayoutItemLabel, QgsLayoutItemMap,
    QgsLayoutItemPicture, QgsLayoutItemShape, QgsLayoutPoint, QgsLayoutSize, QgsLayoutUtils,
    QgsMapRendererSequentialJob, QgsMapSettings, QgsMemoryProviderUtils, QgsPointXY, QgsProject,
    QgsRectangle, QgsRenderContext, QgsTextFormat, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QMetaType, QRect, QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont

TITULO = 'Convenções'
# Propriedade dos itens do quadro: o uuid do mapa do layout a que o quadro pertence.
PROP_QUADRO = 'ebgeo/convencoes_mapa'
PROP_EXTENSAO = 'ebgeo/convencoes_so_extensao'
# Papel do item no quadro: 'moldura', 'titulo', 'grupo', 'figura' ou 'nome'.
PROP_PAPEL = 'ebgeo/convencoes_papel'
ID_GRUPO = 'Convenções do calco'

GRUPOS = [
    ('militar', 'Símbolos Militares'),
    ('medida', 'Medidas de Coordenação'),
    ('engenharia', 'Símbolos de Engenharia'),
    ('linha', 'Linhas'),
    ('area', 'Áreas'),
    ('outro', 'Outros'),
]
GRUPO_DO_TIPO = {
    'military_symbol': 'militar', 'coordination_measure': 'medida', 'engineering_symbol': 'engenharia',
    'coordination_line': 'linha', 'boundary': 'linha', 'arrow': 'linha', 'occupied_front': 'linha',
    'coordination_area': 'area', 'magnetic_declination': 'outro',
}
# Dentro de Linhas, os tipos na ordem da barra de ferramentas.
ORDEM_TIPO = {'coordination_line': 0, 'boundary': 1, 'arrow': 2, 'occupied_front': 3}
TIPOS_PONTUAIS = ('military_symbol', 'coordination_measure', 'engineering_symbol', 'magnetic_declination')

# Medidas do quadro, em mm.
MARGEM = 3.0
FIG_L, FIG_A = 16.0, 8.0          # célula da figura
VAO = 2.0                         # entre a figura e o nome
TEXTO_L = 50.0                    # largura do nome (quebra em linhas)
ENTRE_LINHAS = 1.2
ENTRE_COLUNAS = 4.0
PONTOS_TITULO, PONTOS_GRUPO, PONTOS_ITEM = 12.0, 9.0, 8.0
DPI_AMOSTRA = 300
FONTE = 'Arial'  # o Qt cai na fonte sem serifa do sistema quando não há Arial


# ---------------------------------------------------------------------------------------------
# Catálogos e nomes
# ---------------------------------------------------------------------------------------------

def _catalogos():
    from .motor.motor import catalogos
    return catalogos()


def _texto(valor):
    if valor is None:
        return ''
    try:
        from qgis.PyQt.QtCore import QVariant
        if isinstance(valor, QVariant) and valor.isNull():
            return ''
    except ImportError:
        pass
    return str(valor)


def _json(valor):
    """Coluna JSON em qualquer dos três formatos (texto, lista, mapa) como objeto Python."""
    if isinstance(valor, (dict, list)):
        return valor
    t = _texto(valor).strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except ValueError:
        return None


def _sem_travessao(s):
    em, en = chr(0x2014), chr(0x2013)  # travessão e meia-risca
    return s.replace(' ' + em + ' ', ', ').replace(em, ', ').replace(' ' + en + ' ', ', ').replace(en, '-')


def _rotulo(lista, valor):
    for e in lista or []:
        if str(e.get('value')) == str(valor):
            return e.get('label', '')
    return ''


def nome_sidc(sidc, cat=None):
    """
    Descrição em português de um SIDC de 20 ou 30 dígitos, montada dos catálogos do construtor
    de SIDC (motor/catalogos.json, gerado do Web): o ícone (e o subtipo), os modificadores e,
    entre parênteses, a identidade, o escalão, QG/FT, o modificador especial e o status quando
    não é a posição atual. Ex.: 'Infantaria, Motorizado (Amigo, Batalhão)'.
    """
    from .ui.construtor_sidc import desmontar_sidc
    cat = cat or _catalogos()['militar']
    d = desmontar_sidc(sidc)
    if d is None:
        return 'SIDC {}'.format(sidc)
    conj = (cat.get('porConjunto') or {}).get(d['conjunto'], {})
    icone = None
    for ic in conj.get('icones', []):
        if ic['codigo'] == d['icone'] and (ic.get('extensao') is None or ic.get('extensao') == d['entidade']):
            icone = ic
            if ic.get('extensao') == d['entidade']:
                break
    if icone is not None:
        nome = icone['nome'] + (' / ' + icone['subtipo'] if icone.get('subtipo') else '')
    else:
        nome = conj.get('nome_tabela') or conj.get('nome') or 'Símbolo militar'
    apl = conj.get('aplicavel') or {}
    mods = []
    for chave, cod, ext in (('mod1', d['mod1'], d['ext_mod1']), ('mod2', d['mod2'], d['ext_mod2'])):
        if cod == '00' and not ext:
            continue
        for m in conj.get(chave, []):
            if m['codigo'] == cod and (m.get('extensao') is None or m.get('extensao') == ext):
                mods.append(m['nome'])
                break
    partes = [_rotulo(cat.get('identidades'), d['identidade'])]
    esc = conj.get('escalao') or {}
    if apl.get('escalao') and d['escalao'] != '00':
        partes.append(_rotulo(esc.get('data') if isinstance(esc, dict) else None, d['escalao']))
    if apl.get('qgFt') and d['qgft'] != '0':
        partes.append(_rotulo(cat.get('qgFtSimulado'), d['qgft']))
    me = conj.get('modificadorEspecial') or {}
    if me.get('applicable') and d['especial']:
        partes.append(_rotulo(me.get('data'), str(d['especial'])))
    if apl.get('comando') and d['comando']:
        partes.append('Comando')
    if d['status'] != '0':
        partes.append(_rotulo(cat.get('status'), d['status']))
    partes = [p for p in partes if p]
    texto = nome + (', ' + ', '.join(mods) if mods else '')
    if partes:
        texto += ' ({})'.format(', '.join(partes))
    return _sem_travessao(texto)


def nome_medida(point_code, echelon_code=None, cat=None):
    """Nome do catálogo de medidas (porCodigo); as famílias de escalão pelo echelon_code."""
    cat = cat or _catalogos()['medida']
    pc = cat.get('porCodigo') or {}
    cod = _texto(point_code)
    if cod in (cat.get('familias') or {}):
        ent = pc.get(_texto(echelon_code))
        if ent:
            return _sem_travessao(ent['nome'])
        return _sem_travessao((cat['familias'][cod] or {}).get('rotulo') or cod)
    ent = pc.get(cod)
    return _sem_travessao(ent['nome']) if ent else 'Medida {}'.format(cod)


def nome_engenharia(point_code, variante=None, cat=None):
    cat = cat or _catalogos()['engenharia']
    for it in cat.get('itens', []):
        if str(it['codigo']) == _texto(point_code):
            nome = _sem_travessao(it['titulo'])
            vs = it.get('variantes') or []
            if len(vs) > 1:
                for v in vs:
                    if v.get('indice') == variante:
                        nome += ' ({})'.format(_sem_travessao(v['rotulo']))
                        break
            return nome
    return 'Símbolo de engenharia {}'.format(_texto(point_code))


def variante_engenharia(item, valor):
    """
    Índice da variante do desenho. Em geral é o `variant` gravado; mas quando um campo de
    escolha do item repete as variantes (Cobertura e Coberta: "foliage" com os mesmos rótulos),
    é esse campo que o gerador desenha, e o `variant` gravado não muda a figura (medido na
    fixture 06: variant 1 com foliage temporária sai com círculos).
    """
    obj = _json(valor)
    obj = obj if isinstance(obj, dict) else {}
    vs = (item or {}).get('variantes') or []
    if len(vs) <= 1:
        return 0
    rotulos = [v_['rotulo'] for v_ in vs]
    for campo in (item or {}).get('campos') or []:
        ops = campo.get('opcoes') or []
        if campo.get('tipo') == 'select' and [o['rotulo'] for o in ops] == rotulos:
            escolhido = ((obj.get('values') or {}).get(campo['chave'])) or campo.get('padrao')
            for i, o in enumerate(ops):
                if o['valor'] == escolhido:
                    return i
            return 0
    try:
        return int(obj.get('variant') or 0)
    except (TypeError, ValueError):
        return 0


def _escalao_limite(e):
    return {'ooo': '•••', 'oo': '••', 'o': '•'}.get(e, e)


def _bool(v, padrao):
    if v is None or _texto(v) == '':
        return padrao
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 't', 'sim')
    return bool(v)


def chave_e_nome(tipo, f, cats=None):
    """
    (chave, nome, ordem) do símbolo da feição. A chave decide o que é o MESMO símbolo: o SIDC,
    o código da medida (e o escalão nas famílias de escalão), o código e a variante da
    engenharia, o código da Linha de Coordenação e da Área de Coordenação, o escalão do Limite,
    a forma da Seta. Cor e textos da instância não fazem símbolo novo.
    """
    cats = cats or _catalogos()

    def v(c):
        try:
            return f[c]
        except KeyError:
            return None

    if tipo == 'military_symbol':
        sidc = ''.join(ch for ch in _texto(v('sidc')) if ch.isdigit())
        if len(sidc) == 20:
            sidc += '0760000000'
        return sidc, nome_sidc(sidc, cats['militar']), 0
    if tipo == 'coordination_measure':
        pc = _texto(v('point_code'))
        ec = _texto(v('echelon_code')) if pc in (cats['medida'].get('familias') or {}) else ''
        return (pc, ec), nome_medida(pc, ec, cats['medida']), 0
    if tipo == 'engineering_symbol':
        pc = _texto(v('point_code'))
        item = [i for i in cats['engenharia'].get('itens', []) if str(i['codigo']) == pc]
        var = variante_engenharia(item[0] if item else None, v('engineering'))
        return (pc, var), nome_engenharia(pc, var, cats['engenharia']), 0
    if tipo == 'coordination_line':
        from .estilos_taticos import CATALOGO_LINHA, SIMBOLO_PADRAO
        cod = _texto(v('symbol_code'))
        cod = cod if cod in CATALOGO_LINHA else SIMBOLO_PADRAO
        return cod, CATALOGO_LINHA[cod]['nome'], 0
    if tipo == 'boundary':
        from .estilos_area import ESCALOES
        e = _texto(v('echelon')) or 'XXX'
        ordem = ESCALOES.index(e) if e in ESCALOES else len(ESCALOES)
        return e, 'Linha de Limite ({})'.format(_escalao_limite(e)), ordem
    if tipo == 'arrow':
        am, dh, hd = _bool(v('airmobile'), False), _bool(v('double_headed'), False), _bool(v('show_arrow_head'), True)
        nome = 'Seta'
        qual = []
        if am:
            qual.append('aeromóvel / aeroterrestre')
        if not hd:
            qual.append('sem ponta')
        elif dh:
            qual.append('nas duas pontas')
        if qual:
            nome += ' ' + ', '.join(qual)
        return (am, dh and hd, hd), nome, 0
    if tipo == 'occupied_front':
        return 'frente', 'Frente Ocupada', 0
    if tipo == 'coordination_area':
        from .estilos_area import CATALOGO_AREA, SIMBOLO_PADRAO
        cod = _texto(v('symbol_code'))
        cod = cod if cod in CATALOGO_AREA else SIMBOLO_PADRAO
        return cod, CATALOGO_AREA[cod]['nome'], 0
    if tipo == 'magnetic_declination':
        return 'declinacao', 'Declinação Magnética', 0
    return None


def _chave_ordem(nome):
    s = unicodedata.normalize('NFKD', nome)
    return ''.join(c for c in s if not unicodedata.combining(c)).casefold()


# ---------------------------------------------------------------------------------------------
# Coleta das feições
# ---------------------------------------------------------------------------------------------

class Entrada:
    def __init__(self, grupo, tipo, chave, nome, ordem, camada, feicao):
        self.grupo, self.tipo, self.chave, self.nome, self.ordem = grupo, tipo, chave, nome, ordem
        self.camada, self.feicao = camada, feicao

    def __repr__(self):
        return 'Entrada({!r}, {!r})'.format(self.grupo, self.nome)


def _tipo_da_camada(layer):
    from .calco import tipo_da_camada
    t = tipo_da_camada(layer)
    return t if t in GRUPO_DO_TIPO else None


def camadas_do_mapa(mapa):
    """Camadas do calco que o mapa do layout desenha, na ordem dele."""
    return [l for l in mapa.layersToRender() if isinstance(l, QgsVectorLayer) and _tipo_da_camada(l)]


def _tamanho_figura(tipo, f):
    """Para escolher, entre feições do mesmo símbolo, a de desenho mais enxuto (menos amplificadores)."""
    if tipo in TIPOS_PONTUAIS:
        try:
            return len(_texto(f['svg']) or _texto(f['bitmap_b64'])) or 10 ** 9
        except KeyError:
            return 10 ** 9
    return 0


def coletar(camadas, extensao=None, crs_extensao=None, projeto=None):
    """
    Entradas do quadro, uma por símbolo distinto, ordenadas por grupo e nome. Só conta a
    feição que o estilo da camada desenha (regra de "visivel" e dos grupos ocultos do EBGeo,
    pelo willRenderFeature do próprio renderer) e, com `extensao` (QgsGeometry no SRC
    `crs_extensao`), só a que a toca.
    """
    projeto = projeto or QgsProject.instance()
    cats = _catalogos()
    achadas = {}
    for layer in camadas:
        tipo = _tipo_da_camada(layer)
        if tipo is None or layer.renderer() is None:
            continue
        req = QgsFeatureRequest()
        recorte = None
        if extensao is not None:
            recorte = QgsGeometry(extensao)
            if crs_extensao is not None and crs_extensao != layer.crs():
                recorte.transform(QgsCoordinateTransform(crs_extensao, layer.crs(), projeto))
            req.setFilterRect(recorte.boundingBox())
        renderer = layer.renderer().clone()
        ctx = QgsRenderContext()
        ctx.setExpressionContext(QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer)))
        renderer.startRender(ctx, layer.fields())
        try:
            for f in layer.getFeatures(req):
                if recorte is not None and not recorte.intersects(f.geometry()):
                    continue
                ctx.expressionContext().setFeature(f)
                if not renderer.willRenderFeature(f, ctx):
                    continue
                kn = chave_e_nome(tipo, f, cats)
                if kn is None:
                    continue
                chave, nome, ordem = kn
                k = (tipo, chave)
                atual = achadas.get(k)
                if atual is None or _tamanho_figura(tipo, f) < _tamanho_figura(tipo, atual.feicao):
                    achadas[k] = Entrada(GRUPO_DO_TIPO[tipo], tipo, chave, nome, ordem, layer, QgsFeature(f))
        finally:
            renderer.stopRender(ctx)
    entradas = list(achadas.values())
    # nomes iguais de símbolos diferentes (SIDC com bit da extensão fora do catálogo, por ex.)
    vistos = {}
    for e in entradas:
        vistos.setdefault((e.grupo, e.nome), []).append(e)
    for lst in vistos.values():
        if len(lst) > 1:
            for e in lst:
                e.nome = '{} [{}]'.format(e.nome, e.chave if isinstance(e.chave, str) else '/'.join(map(str, e.chave)))
    ordem_grupo = {g: i for i, (g, _r) in enumerate(GRUPOS)}
    entradas.sort(key=lambda e: (ordem_grupo[e.grupo], ORDEM_TIPO.get(e.tipo, 0), e.ordem, _chave_ordem(e.nome)))
    return entradas


def coletar_do_mapa(mapa, so_extensao=False, projeto=None):
    extensao = QgsGeometry.fromQPolygonF(mapa.visibleExtentPolygon()) if so_extensao else None
    return coletar(camadas_do_mapa(mapa), extensao, mapa.crs(), projeto or mapa.layout().project())


# ---------------------------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------------------------

def figura_pontual(entrada):
    """('svg' | 'raster', base64) do símbolo pontual: o SVG gravado na feição, ou o PNG do .ebgeo."""
    f = entrada.feicao
    svg = _texto(f['svg'])
    if svg:
        return 'svg', svg
    try:
        png = _texto(f['bitmap_b64'])
    except KeyError:
        png = ''
    return ('raster', png) if png else None


def figuras(entradas, largura_mm=FIG_L, altura_mm=FIG_A, dpi=DPI_AMOSTRA):
    """
    {id(entrada): ('svg' | 'raster', base64)}. Pontuais leem o campo; linhas e áreas são
    desenhadas em lote, UM desenho por camada (o QGIS reparseia as expressões do estilo a cada
    desenho da camada, com custo fixo: 0,65 s por amostra da Linha de Coordenação, uma a uma).
    """
    out = {}
    por_camada = {}
    for e in entradas:
        if e.tipo in TIPOS_PONTUAIS:
            fig = figura_pontual(e)
            if fig:
                out[id(e)] = fig
        else:
            por_camada.setdefault(e.camada.id(), []).append(e)
    for lote in por_camada.values():
        pngs = amostras_png(lote[0].camada, lote[0].tipo, [e.feicao for e in lote], largura_mm, altura_mm, dpi)
        for e, png in zip(lote, pngs):
            if png:
                out[id(e)] = ('raster', png)
    return out


# Colunas de texto da instância: ficam vazias na amostra (o nome do símbolo está no quadro).
_TEXTOS_INSTANCIA = ('nome', 'descricao', 'tipo', 'identificacao', 'gdh_ini', 'gdh_fim', 'numero_concentracao',
                     'outras_info', 'altitude_max', 'altitude_min', 'text_top', 'text_bottom', 'label_text')


def _crs_local(lat, lon):
    return QgsCoordinateReferenceSystem(
        'PROJ:+proj=tmerc +lat_0={:.4f} +lon_0={:.4f} +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs'.format(lat, lon))


def _num(v, padrao):
    try:
        x = float(v)
        return x if math.isfinite(x) and x != 0 else padrao
    except (TypeError, ValueError):
        return padrao


# Tamanho único de glifo nas amostras, em metros: as figuras do quadro saem na mesma escala de
# desenho, qualquer que seja o tamanho gravado em cada feição.
PEGADA_LINHA_M = 500.0
GLIFO_LIMITE_M = 1000.0
LARGURA_SETA_M = 500.0
FRENTE_M = 1000.0
DECORACAO_AREA_M = 300.0


def geometria_amostra(tipo, f):
    """
    (geometria no plano local em metros centrada na origem, atributos sobrescritos, janela)
    da amostra do tipo: reta com três glifos na Linha de Coordenação, reta longa com o escalão
    no meio no Limite (a janela mostra o trecho central), seta reta, Frente Ocupada com os dois
    braços e um retângulo na Área. A janela é o retângulo que a figura mostra.
    """
    def v(c):
        try:
            return f[c]
        except KeyError:
            return None

    extra = {}
    if tipo == 'coordination_line':
        from .estilos_taticos import CATALOGO_LINHA, SIMBOLO_PADRAO
        sim = CATALOGO_LINHA.get(_texto(v('symbol_code')), CATALOGO_LINHA[SIMBOLO_PADRAO])
        span = sim.get('span', 1) or 1
        P = PEGADA_LINHA_M
        extra['symbol_size_km'] = P / span / 1000
        extra['symbol_spacing_km'] = 2 * P / 1000   # o mínimo do Web: pegada / 0,5
        L = 6 * P
        g = QgsGeometry.fromPolylineXY([QgsPointXY(-L / 2, 0), QgsPointXY(L / 2, 0)])
        return g, extra, QgsRectangle(-L / 2 - 0.1 * P, -1.2 * P, L / 2 + 0.1 * P, 1.2 * P)
    if tipo == 'boundary':
        S = GLIFO_LIMITE_M
        e = _texto(v('echelon')) or 'XXX'
        glifos = max(1, len(e) if e not in ('Ø', '++') else 1)
        # o Web limita o glifo a L x 0,5 / (instâncias x glifos x 1,8): a linha tem de ser longa,
        # e a janela mostra só o trecho central, com o escalão (a linha segue além da borda)
        L = max(S * glifos * 1.8 / 0.5 * 1.15 + 2 * S, 30 * S)  # mais longa que a janela do lote
        extra['symbol_size_km'] = S / 1000
        extra['symbol_instances'] = json.dumps([{'ratio': 0.5, 'showLabels': False}])
        meia = (S * glifos * 1.8 + 3 * S) / 2
        g = QgsGeometry.fromPolylineXY([QgsPointXY(-L / 2, 0), QgsPointXY(L / 2, 0)])
        return g, extra, QgsRectangle(-meia, -1.1 * S, meia, 1.1 * S)
    if tipo == 'arrow':
        w = LARGURA_SETA_M
        extra['width_m'] = w
        L = 8 * w
        g = QgsGeometry.fromMultiPolylineXY([[QgsPointXY(-L / 2, 0), QgsPointXY(L / 2, 0)]])
        return g, extra, QgsRectangle(-L / 2 - 0.3 * w, -1.5 * w, L / 2 + 0.3 * w, 1.5 * w)
    if tipo == 'occupied_front':
        L = FRENTE_M
        g = QgsGeometry.fromPolylineXY([QgsPointXY(0, 0), QgsPointXY(-L / 2, 0), QgsPointXY(L / 2, 0)])
        return g, extra, QgsRectangle(-0.55 * L, -0.12 * L, 0.55 * L, 0.12 * L)
    if tipo == 'coordination_area':
        s = DECORACAO_AREA_M
        extra['symbol_size_km'] = s / 1000
        W, H = 12 * s, 4 * s
        portoes = _json(v('portoes'))
        if isinstance(portoes, list):
            extra['portoes'] = json.dumps([dict(p, nome='') if isinstance(p, dict) else p for p in portoes])
        anel = [QgsPointXY(-W / 2, -H / 2), QgsPointXY(-W / 2, H / 2), QgsPointXY(W / 2, H / 2),
                QgsPointXY(W / 2, -H / 2), QgsPointXY(-W / 2, -H / 2)]
        g = QgsGeometry.fromMultiPolygonXY([[anel]])
        return g, extra, QgsRectangle(-W / 2 - 2 * s, -H / 2 - 2 * s, W / 2 + 2 * s, H / 2 + 2 * s)
    return None, extra, None


def _campo_texto(campo):
    """Coluna JSON vira texto na camada de memória (as expressões leem os três formatos)."""
    if campo.type() in (QMetaType.Type.QVariantMap, QMetaType.Type.QVariantList, QMetaType.Type.QStringList):
        return QgsField(campo.name(), QMetaType.Type.QString)
    return QgsField(campo)


def _valor_memoria(valor):
    if isinstance(valor, (dict, list)):
        return json.dumps(valor)
    return valor


def _png_base64(img):
    buf = QByteArray()
    dispositivo = QBuffer(buf)
    dispositivo.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(dispositivo, 'PNG')
    dispositivo.close()
    return base64.b64encode(bytes(buf)).decode('ascii')


def amostras_png(camada, tipo, feicoes, largura_mm=FIG_L, altura_mm=FIG_A, dpi=DPI_AMOSTRA):
    """
    PNG (base64) da amostra de cada feição, desenhadas com o renderer e os rótulos da própria
    camada, numa camada de memória com o mesmo esquema e os atributos de desenho da feição.
    As amostras ficam empilhadas no plano local, um desenho só, e cada figura é recortada da
    sua janela. Âncora de zoom desligada (created_zoom nulo): traço e texto em mm, glifo nos
    metros da amostra, como o Web sem âncora.
    """
    if not feicoes:
        return []
    c = QgsGeometry(feicoes[0].geometry())
    lat, lon = 0.0, 0.0
    if not c.isNull() and not c.isEmpty():
        p = QgsCoordinateTransform(camada.crs(), QgsCoordinateReferenceSystem('EPSG:4326'),
                                   QgsProject.instance()).transform(c.centroid().asPoint())
        lat, lon = p.y(), p.x()
    crs_local = _crs_local(lat, lon)
    para_camada = QgsCoordinateTransform(crs_local, camada.crs(), QgsProject.instance())

    campos = QgsFields()
    for campo in camada.fields():
        campos.append(_campo_texto(campo))
    vl = QgsMemoryProviderUtils.createMemoryLayer('amostra', campos, camada.wkbType(), camada.crs())
    nomes_origem = camada.fields().names()
    px_l = max(8, int(round(largura_mm / 25.4 * dpi)))
    px_a = max(8, int(round(altura_mm / 25.4 * dpi)))
    amostras = [geometria_amostra(tipo, f) for f in feicoes]
    validas = [a[2] for a in amostras if a[0] is not None]
    if not validas:
        return [None] * len(feicoes)
    # Uma janela só, no formato da célula, para o lote inteiro: traço e texto são mm de papel,
    # então cada figura tem de sair na MESMA escala, recortada já no tamanho da célula (janela
    # menor ampliada no quadro engrossaria o traço).
    jl = max(j.width() for j in validas)
    ja = max(j.height() for j in validas)
    if jl / ja < px_l / px_a:
        jl = ja * px_l / px_a
    else:
        ja = jl * px_a / px_l
    janelas, novas, y = [], [], 0.0
    for f, (geom, extra, janela) in zip(feicoes, amostras):
        if geom is None:
            janelas.append(None)
            continue
        janela = QgsRectangle.fromCenterAndSize(janela.center(), jl, ja)
        # empilhadas para baixo, com folga de uma janela inteira entre elas
        dy = y - janela.yMaximum()
        y = dy + janela.yMinimum() - janela.height()
        geom = QgsGeometry(geom)
        geom.translate(0, dy)
        janelas.append(QgsRectangle(janela.xMinimum(), janela.yMinimum() + dy,
                                    janela.xMaximum(), janela.yMaximum() + dy))
        nova = QgsFeature(vl.fields())
        for nome in nomes_origem:
            if nome == 'fid':
                continue
            nova.setAttribute(vl.fields().indexOf(nome), _valor_memoria(f[nome]))
        sobrescritos = {'visivel': True, 'grupos': None, 'created_zoom': None, 'label_created_zoom': None}
        sobrescritos.update({col: '' for col in _TEXTOS_INSTANCIA})
        sobrescritos.update(extra)
        for nome, valor in sobrescritos.items():
            i = vl.fields().indexOf(nome)
            if i >= 0:
                nova.setAttribute(i, valor)
        geom.transform(para_camada)
        nova.setGeometry(geom)
        novas.append(nova)
    if not novas:
        return [None] * len(feicoes)
    vl.dataProvider().addFeatures(novas)
    vl.updateExtents()
    vl.setRenderer(camada.renderer().clone())
    if camada.labeling() is not None:
        vl.setLabeling(camada.labeling().clone())
        vl.setLabelsEnabled(camada.labelsEnabled())

    validas = [j for j in janelas if j is not None]
    mpp = jl / px_l  # metros por pixel, comum ao lote
    total = QgsRectangle(validas[0])
    for j in validas[1:]:
        total.combineExtentWith(j)
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(crs_local)
    ms.setOutputSize(QSize(int(math.ceil(total.width() / mpp)), int(math.ceil(total.height() / mpp))))
    ms.setOutputDpi(dpi)
    ms.setBackgroundColor(QColor(255, 255, 255, 0))
    ms.setExtent(total)
    ms.setFlag(Qgis.MapSettingsFlag.Antialiasing, True)
    ms.setFlag(Qgis.MapSettingsFlag.DrawLabeling, True)
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(None))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererSequentialJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    ext = ms.visibleExtent()
    passo = ext.width() / img.width()
    saida = []
    for j in janelas:
        if j is None:
            saida.append(None)
            continue
        x0 = int(round((j.xMinimum() - ext.xMinimum()) / passo))
        y0 = int(round((ext.yMaximum() - j.yMaximum()) / passo))
        saida.append(_png_base64(img.copy(QRect(x0, y0, px_l, px_a))))
    return saida


# ---------------------------------------------------------------------------------------------
# O quadro no layout
# ---------------------------------------------------------------------------------------------

def _formato(pontos, negrito=False):
    fmt = QgsTextFormat()
    fonte = QFont(FONTE)
    fonte.setPointSizeF(pontos)
    fonte.setBold(negrito)
    fmt.setFont(fonte)
    fmt.setSize(pontos)
    fmt.setSizeUnit(Qgis.RenderUnit.Points)
    fmt.setColor(QColor('black'))
    return fmt, fonte


def quebrar(texto, fonte, largura_mm):
    """Quebra o texto em linhas que cabem na largura (mm), palavra a palavra."""
    linhas, atual = [], ''
    for palavra in texto.split():
        tentativa = (atual + ' ' + palavra).strip()
        if atual and QgsLayoutUtils.textWidthMM(fonte, tentativa) > largura_mm:
            linhas.append(atual)
            atual = palavra
        else:
            atual = tentativa
    if atual:
        linhas.append(atual)
    return linhas or ['']


def _altura_texto(fonte, n_linhas):
    return QgsLayoutUtils.fontHeightMM(fonte) * n_linhas * 1.15


def itens_do_quadro(layout, uuid_mapa):
    return [i for i in layout.items() if isinstance(i, QgsLayoutItem) and i.customProperty(PROP_QUADRO) == uuid_mapa]


def remover_quadro(layout, mapa):
    """Apaga o quadro do mapa e devolve a posição (QgsLayoutPoint) que ele tinha, ou None."""
    itens = itens_do_quadro(layout, mapa.uuid())
    pos = None
    for i in itens:
        if isinstance(i, QgsLayoutItemGroup):
            pos = i.positionWithUnits()
            layout.ungroupItems(i)
    for i in itens_do_quadro(layout, mapa.uuid()):
        if pos is None and isinstance(i, QgsLayoutItemShape):
            pos = i.positionWithUnits()
        layout.removeLayoutItem(i)
    return pos


def _posicao_padrao(layout, mapa, largura):
    """À direita do mapa, se couber na página; senão, no canto superior direito do mapa."""
    pg = layout.pageCollection().page(0)
    larg_pagina = pg.pageSize().width() if pg is not None else 297.0
    x_mapa, y_mapa = mapa.pos().x(), mapa.pos().y()
    direita = x_mapa + mapa.rect().width()
    if direita + 5 + largura <= larg_pagina - 5:
        return direita + 5, y_mapa
    # não cabe: encostado na borda direita da página, por cima do mapa (o operador o arrasta)
    return max(0.0, larg_pagina - 5 - largura), y_mapa


def montar_quadro(layout, mapa, so_extensao=False, posicao=None, entradas=None):
    """
    Monta (ou refaz no mesmo lugar) o quadro de convenções do mapa do layout. Devolve
    (grupo, entradas); grupo None quando não há símbolo do calco a mostrar.
    """
    if entradas is None:
        entradas = coletar_do_mapa(mapa, so_extensao)
    pilha = layout.undoStack()
    pilha.beginMacro('Quadro de convenções')
    try:
        antiga = remover_quadro(layout, mapa)
        if not entradas:
            return None, entradas
        fmt_titulo, f_titulo = _formato(PONTOS_TITULO, True)
        fmt_grupo, f_grupo = _formato(PONTOS_GRUPO, True)
        fmt_item, f_item = _formato(PONTOS_ITEM)
        larg_coluna = FIG_L + VAO + TEXTO_L
        # altura útil: a do mapa (no mínimo 120 mm), sem passar da página
        pg = layout.pageCollection().page(0)
        alt_pagina = pg.pageSize().height() if pg is not None else 210.0
        alt_max = max(120.0, min(mapa.rect().height(), alt_pagina - 10)) - 2 * MARGEM

        # disposição: lista de (coluna, y relativo, tipo, dados)
        blocos = []
        h_titulo = _altura_texto(f_titulo, 1) + 2
        coluna, y = 0, h_titulo
        grupo_atual = None
        nomes_grupo = dict(GRUPOS)
        for e in entradas:
            linhas = quebrar(e.nome, f_item, TEXTO_L)
            h_linha = max(FIG_A, _altura_texto(f_item, len(linhas))) + ENTRE_LINHAS
            h_cab = _altura_texto(f_grupo, 1) + 1.5 if e.grupo != grupo_atual else 0
            if y + h_cab + h_linha > alt_max and y > h_titulo:
                coluna, y = coluna + 1, h_titulo
            if e.grupo != grupo_atual:
                blocos.append((coluna, y, 'grupo', nomes_grupo[e.grupo]))
                y += h_cab
                grupo_atual = e.grupo
            blocos.append((coluna, y, 'item', (e, linhas, h_linha - ENTRE_LINHAS)))
            y += h_linha
        n_colunas = coluna + 1
        alt_total = max([b[1] + (b[3][2] if b[2] == 'item' else 0) for b in blocos] + [h_titulo]) + 2 * MARGEM
        larg_total = n_colunas * larg_coluna + (n_colunas - 1) * ENTRE_COLUNAS + 2 * MARGEM

        if posicao is not None:
            x0, y0 = posicao
        elif antiga is not None:
            x0, y0 = antiga.x(), antiga.y()
        else:
            x0, y0 = _posicao_padrao(layout, mapa, larg_total)

        uuid = mapa.uuid()
        itens = []
        figs = figuras(entradas)

        def marcar(item, ident, papel):
            item.setCustomProperty(PROP_QUADRO, uuid)
            item.setCustomProperty(PROP_PAPEL, papel)
            item.setId(ident)
            layout.addLayoutItem(item)
            itens.append(item)
            return item

        moldura = QgsLayoutItemShape(layout)
        moldura.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
        moldura.setSymbol(QgsFillSymbol.createSimple({'color': '255,255,255,255', 'outline_color': '0,0,0,255',
                                                      'outline_width': '0.3', 'outline_width_unit': 'MM'}))
        moldura.attemptMove(QgsLayoutPoint(x0, y0))
        moldura.attemptResize(QgsLayoutSize(larg_total, alt_total))
        marcar(moldura, 'Convenções: moldura', 'moldura')

        titulo = QgsLayoutItemLabel(layout)
        titulo.setText(TITULO)
        titulo.setTextFormat(fmt_titulo)
        titulo.setHAlign(Qt.AlignmentFlag.AlignHCenter)
        titulo.setVAlign(Qt.AlignmentFlag.AlignVCenter)
        titulo.setMargin(0)
        titulo.attemptMove(QgsLayoutPoint(x0 + MARGEM, y0 + MARGEM))
        titulo.attemptResize(QgsLayoutSize(larg_total - 2 * MARGEM, h_titulo - 1))
        marcar(titulo, 'Convenções: título', 'titulo')

        for col, yr, tipo, dados in blocos:
            x = x0 + MARGEM + col * (larg_coluna + ENTRE_COLUNAS)
            yy = y0 + MARGEM + yr
            if tipo == 'grupo':
                lb = QgsLayoutItemLabel(layout)
                lb.setText(dados)
                lb.setTextFormat(fmt_grupo)
                lb.setVAlign(Qt.AlignmentFlag.AlignVCenter)
                lb.setMargin(0)
                lb.attemptMove(QgsLayoutPoint(x, yy))
                lb.attemptResize(QgsLayoutSize(larg_coluna, _altura_texto(f_grupo, 1)))
                marcar(lb, 'Convenções: {}'.format(dados), 'grupo')
                continue
            e, linhas, h = dados
            fig = figs.get(id(e))
            if fig is not None:
                pic = QgsLayoutItemPicture(layout)
                pic.setResizeMode(QgsLayoutItemPicture.ResizeMode.Zoom)
                pic.setPictureAnchor(QgsLayoutItem.ReferencePoint.Middle)
                pic.attemptMove(QgsLayoutPoint(x, yy + (h - FIG_A) / 2))
                pic.attemptResize(QgsLayoutSize(FIG_L, FIG_A))
                pic.setPicturePath('base64:' + fig[1],
                                   Qgis.PictureFormat.SVG if fig[0] == 'svg' else Qgis.PictureFormat.Raster)
                marcar(pic, 'Convenções: figura de {}'.format(e.nome), 'figura')
            lb = QgsLayoutItemLabel(layout)
            lb.setText('\n'.join(linhas))
            lb.setTextFormat(fmt_item)
            lb.setVAlign(Qt.AlignmentFlag.AlignVCenter)
            lb.setMargin(0)
            lb.attemptMove(QgsLayoutPoint(x + FIG_L + VAO, yy))
            lb.attemptResize(QgsLayoutSize(TEXTO_L + 2, h))
            marcar(lb, 'Convenções: {}'.format(e.nome), 'nome')

        grupo = layout.groupItems(itens)
        grupo.setId(ID_GRUPO)
        grupo.setCustomProperty(PROP_QUADRO, uuid)
        grupo.setCustomProperty(PROP_EXTENSAO, bool(so_extensao))
        return grupo, entradas
    finally:
        pilha.endMacro()


def mapas_do_layout(layout):
    return [i for i in layout.items() if isinstance(i, QgsLayoutItemMap)]
