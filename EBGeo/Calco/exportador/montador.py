# -*- coding: utf-8 -*-
"""
Montador do .ebgeo: lê o calco (GeoPackage) e monta o data.json e as imagens que o EBGeo Web
importa, sem QGIS (só GDAL/OGR), para ser testável em Python puro.

Regras (seção 12 de EBGeo/Calco/ARQUITETURA.md):
- a base de cada feição é o `props` guardado na importação; só a coluna EDITADA é reescrita.
  "Editada" é a coluna cujo valor difere do que o próprio importador gravaria a partir do props
  (escritor.linha_feicao), com tolerância só onde há conversão numérica (real, data em ms, cor
  sem caixa). Coluna igual deixa a chave original intocada, com o tipo e a grafia de origem;
- a geometria igual à que o importador gravou do original volta como a original, exata; a
  mudada é refeita no formato do Web (arredondada a 6 casas, como o optimizeFeature do Web) e
  as chaves derivadas dela (baseCoordinates, branches, center) acompanham;
- o documento original guardado em ebgeo_documento é a base do arquivo: 360, 3D, briefings,
  temporal, comentários e baldes que o Desktop não conhece voltam como vieram; a feição que o
  importador descartou volta como veio, e a imagem sem dono no 2D sai de ebgeo_imagem.
"""
import base64
import copy
import datetime
import json
import logging
import math
import time
import uuid

from osgeo import ogr

from .. import schema
from ..importador import leitor, escritor

ogr.UseExceptions()

_log = logging.getLogger('EBGeo.Calco.exportador')

VERSAO = leitor.VERSAO_MAX
ESCOPO_TUDO = 'tudo'
ESCOPO_ATUAL = 'atual'

# Seções do data.json chaveadas pelo NOME do mapa (export-import.service.js, _buildExportDataOnce).
SECOES_POR_MAPA = ('colorUsage', 'mapNotes', 'groups', 'layers', 'cesium3d', 'streetview360', 'temporal',
                   'gridStyle', 'comments', 'mapLocks', 'mapBadgeColors')
BALDES_DESKTOP = {d['balde'] for d in schema.TIPOS.values()}
# Baldes de um mapa novo, na ordem de getEmptyMapData (repository.utils.js).
BALDES_MAPA_NOVO = ['polygons', 'lines', 'points', 'texts', 'images', 'los', 'visibility', 'processed_los',
                    'processed_visibility', 'brushes', 'rectangles', 'circles', 'ellipses', 'arrows', 'boundarys',
                    'occupied_fronts', 'coordination_lines', 'coordination_areas', 'military_symbols', 'setores',
                    'coordenadas', 'coordination_measures', 'engineering_symbols', 'magnetic_declinations']

COLUNAS_FORA = {'ebgeo_id', 'mapa', 'camada_id', 'grupos', 'props', 'atributos'}
# Colunas cuja edição não muda o desenho: o bitmap do símbolo e o desenho tático continuam valendo.
NEUTRAS = {'nome', 'descricao', 'visivel', 'bloqueado', 'criado_em', 'atualizado_em', 'camada_id'}

TATICOS_EIXO = escritor.TIPOS_TATICOS_EIXO
FORMAS_PARAMETRICAS = escritor.TIPOS_FORMA_PARAMETRICA
TIPOS_SIMBOLO = escritor.TIPOS_SIMBOLO
PARAMETROS_PONTO = ('center', 'corner1', 'corner2', 'coordinationPoint')
# As colunas que mudam a GEOMETRIA gravada de cada tático (a cor, por exemplo, não muda).
DESENHO_TATICO = {
    'boundary': ('echelon', 'symbol_instances', 'symbol_size_km', 'created_zoom', 'zoom_corr'),
    'coordination_line': ('symbol_code', 'symbol_size_km', 'symbol_spacing_km', 'created_zoom', 'zoom_corr'),
    'arrow': ('width_m', 'head_length_ratio', 'show_arrow_head', 'double_headed', 'airmobile',
              'airmobile_position', 'ramos'),
    'occupied_front': (),
}
# Propriedades de cada ramo da Seta combinada (branches[] de arrow-merge.js).
RAMO_SETA = schema.RAMO_SETA

EXTENSAO = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/svg+xml': 'svg', 'image/webp': 'webp'}
TOL_GRAUS = 1e-9
TOL_REAL = 1e-12


class ErroExportacao(Exception):
    """Exportação recusada. A mensagem é a que o operador lê."""


class Relatorio:
    """O que a montagem fez; a prova da escrita é reler o arquivo (arquivo.conferir)."""

    def __init__(self):
        self.por_balde = {}       # balde -> feições no arquivo
        self.iguais = 0           # feição do calco sem nenhuma coluna nem geometria mudada
        self.editadas = 0
        self.novas = 0
        self.apagadas = 0         # no arquivo original e fora do calco (apagadas no Desktop)
        self.repassadas = 0       # descartadas na importação, devolvidas como vieram
        self.colunas_editadas = {}  # coluna -> quantas feições
        self.avisos = []
        self.mapas = []
        self.imagens = 0
        self.segundos = 0.0
        self.recuperadas = 0      # imagens tiradas do .ebgeo original (calco anterior à ebgeo_imagem)

    def total(self):
        return sum(self.por_balde.values())


class Exportacao:
    def __init__(self, data, imagens, relatorio):
        self.data = data            # o data.json
        self.imagens = imagens      # id -> (bytes, mime)
        self.relatorio = relatorio


# ---------------------------------------------------------------- valores

def _json(v):
    """Coluna JSON lida (texto, ou string JSON escapada pelo provedor do QGIS) -> objeto."""
    for _ in range(2):
        if not isinstance(v, str):
            return v
        s = v.strip()
        if not s:
            return None
        try:
            v = json.loads(s)
        except ValueError:
            return v
    return v


def _ms(d):
    return int(round(d.timestamp() * 1000)) if isinstance(d, datetime.datetime) else None


def _norm(tp, v, coluna=''):
    """Valor de coluna (lido do GeoPackage ou calculado pelo importador) na forma comparável."""
    if v is None:
        return None
    if tp == 'json':
        return _json(v)
    if tp == 'bool':
        if isinstance(v, str):
            return v.strip().lower() in ('true', '1', 'sim', 'yes')
        return bool(v)
    if tp in ('real', 'int'):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None
    if tp == 'datetime':
        if isinstance(v, datetime.datetime):
            return _ms(v)
        return _ms(escritor._datahora(v))
    s = v if isinstance(v, str) else str(v)
    return s.lower() if schema.coluna_de_cor(coluna) and s.startswith('#') else s


def _iguais_prof(a, b):
    """Igualdade de JSON com tolerância nos números (o objeto relido do GeoPackage)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b and type(a) is type(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL_REAL * max(1.0, abs(a), abs(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_iguais_prof(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_iguais_prof(x, y) for x, y in zip(a, b))
    return a == b


def _iguais(tp, a, b):
    if tp == 'str':
        return (a or '') == (b or '')
    if a is None or b is None:
        return a is None and b is None
    if tp in ('real', 'int'):
        return abs(a - b) <= TOL_REAL * max(1.0, abs(a), abs(b))
    if tp == 'datetime':
        return abs(a - b) <= 1
    if tp == 'json':
        return _iguais_prof(a, b)
    return a == b


def _iso(ms):
    d = datetime.datetime.fromtimestamp(ms / 1000.0, tz=datetime.timezone.utc)
    return d.strftime('%Y-%m-%dT%H:%M:%S.') + '{:03d}Z'.format(d.microsecond // 1000)


def _para_web(tp, v, original, tem_original):
    """Valor de coluna editada -> propriedade do Web, no tipo do original quando havia."""
    if v is None:
        return None
    n = _norm(tp, v)
    if n is None:
        return None
    if tp == 'real':
        inteiro_antes = tem_original and isinstance(original, int) and not isinstance(original, bool)
        if n.is_integer() and (inteiro_antes or not tem_original or original is None):
            return int(n)
        return n
    if tp == 'int':
        return int(n)
    if tp == 'datetime':
        return _iso(n) if isinstance(original, str) else n
    if tp == 'str':
        return v if isinstance(v, str) else str(v)
    return n


def _arredondar(c):
    """Math.round(c * 1e6) / 1e6 do roundCoordinates do Web, em listas aninhadas."""
    if isinstance(c, (list, tuple)):
        return [_arredondar(x) for x in c]
    if isinstance(c, (int, float)) and math.isfinite(c):
        return math.floor(c * 1e6 + 0.5) / 1e6
    return c


def _coords_iguais(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_coords_iguais(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL_GRAUS
    return a == b


def _geo_iguais(g1, g2):
    return (isinstance(g1, dict) and isinstance(g2, dict) and g1.get('type') == g2.get('type')
            and _coords_iguais(g1.get('coordinates'), g2.get('coordinates')))


def _xy(c):
    return [float(c[0]), float(c[1])]


def _translacao(g_base, g_atual):
    """(dx, dy) se g_atual é g_base deslocada por inteiro, senão None."""
    pa, pb = [], []

    def achatar(c, out):
        if c and isinstance(c[0], (int, float)):
            out.append(c)
        else:
            for x in c:
                achatar(x, out)
    achatar(g_base.get('coordinates') or [], pa)
    achatar(g_atual.get('coordinates') or [], pb)
    if not pa or len(pa) != len(pb):
        return None
    dx, dy = pb[0][0] - pa[0][0], pb[0][1] - pa[0][1]
    if all(abs(b[0] - a[0] - dx) <= TOL_GRAUS and abs(b[1] - a[1] - dy) <= TOL_GRAUS for a, b in zip(pa, pb)):
        return dx, dy
    return None


def _deslocar(c, dx, dy):
    if c and isinstance(c[0], (int, float)):
        return [c[0] + dx, c[1] + dy] + list(c[2:])
    return [_deslocar(x, dx, dy) for x in c]


def partes_sidc(sidc):
    """As chaves que o painel do Web lê do SIDC (parseSIDC de military_symbol_generator.js)."""
    s = ''.join(ch for ch in (sidc or '') if ch.isdigit())
    if len(s) == 20:
        s += '0760000000'
    if len(s) != 30:
        return {}
    d = {'context': s[2], 'standardIdentity': s[3], 'symbolSet': s[4:6], 'status': s[6], 'hqTfDummy': s[7],
         'echelon': s[8:10], 'mainIcon': s[10:16], 'modifier1': s[16:18], 'modifier2': s[18:20]}
    ext = s[20:]
    ent = m1 = m2 = 0
    if ext[:3] == '076':
        v = int(ext[3:])
        ent, m1, m2 = (v >> 14) & 31, (v >> 5) & 31, v & 31
    d['mainIconExtension'] = ent or None
    d['modifier1Extension'] = m1 or None
    d['modifier2Extension'] = m2 or None
    return d


# ---------------------------------------------------------------- leitura do GeoPackage

def _geojson(g):
    """Geometria OGR -> GeoJSON com as coordenadas exatas (o ExportToJson corta dígitos)."""
    if g is None or g.IsEmpty():
        return None
    nome = g.GetGeometryName().upper()

    def pontos(x):
        return [[x.GetX(i), x.GetY(i)] for i in range(x.GetPointCount())]

    def filhos(x):
        return [x.GetGeometryRef(i) for i in range(x.GetGeometryCount())]

    if nome == 'POINT':
        return {'type': 'Point', 'coordinates': [g.GetX(), g.GetY()]}
    if nome == 'LINESTRING':
        return {'type': 'LineString', 'coordinates': pontos(g)}
    if nome == 'POLYGON':
        return {'type': 'Polygon', 'coordinates': [pontos(a) for a in filhos(g)]}
    if nome == 'MULTIPOINT':
        return {'type': 'MultiPoint', 'coordinates': [[p.GetX(), p.GetY()] for p in filhos(g)]}
    if nome == 'MULTILINESTRING':
        return {'type': 'MultiLineString', 'coordinates': [pontos(l) for l in filhos(g)]}
    if nome == 'MULTIPOLYGON':
        return {'type': 'MultiPolygon', 'coordinates': [[pontos(a) for a in filhos(p)] for p in filhos(g)]}
    return json.loads(g.ExportToJson())


def _valor_ogr(f, i, fd):
    if not f.IsFieldSetAndNotNull(i):
        return None
    t = fd.GetType()
    if t == ogr.OFTDateTime or t == ogr.OFTDate:
        a, mes, d, h, mi, s, tz = f.GetFieldAsDateTime(i)
        seg = int(s)
        us = int(round((s - seg) * 1e6))
        off = (tz - 100) * 15 if tz > 1 else 0
        return datetime.datetime(a, mes, d, h, mi, seg, min(us, 999999),
                                 tzinfo=datetime.timezone(datetime.timedelta(minutes=off)))
    if t == ogr.OFTInteger or t == ogr.OFTInteger64:
        v = f.GetFieldAsInteger64(i)
        return bool(v) if fd.GetSubType() == ogr.OFSTBoolean else v
    if t == ogr.OFTReal:
        return f.GetFieldAsDouble(i)
    return f.GetField(i)


def _linhas(ds, tabela):
    lyr = ds.GetLayerByName(tabela)
    if lyr is None:
        return []
    defn = lyr.GetLayerDefn()
    fds = [defn.GetFieldDefn(i) for i in range(defn.GetFieldCount())]
    lyr.ResetReading()
    out = []
    for f in lyr:
        linha = {fd.GetName(): _valor_ogr(f, i, fd) for i, fd in enumerate(fds)}
        linha['_fid'] = f.GetFID()
        if defn.GetGeomFieldCount():
            linha['_geo'] = _geojson(f.GetGeometryRef())
        out.append(linha)
    return out


def _colunas_attr(ds, tabela):
    """{chave original: coluna attr_*}, pelo nome alternativo que o importador gravou."""
    lyr = ds.GetLayerByName(tabela)
    if lyr is None:
        return {}
    defn = lyr.GetLayerDefn()
    out = {}
    for i in range(defn.GetFieldCount()):
        fd = defn.GetFieldDefn(i)
        nome = fd.GetName()
        if nome.startswith(escritor.PREFIXO_ATRIBUTO):
            try:
                chave = fd.GetAlternativeName()
            except AttributeError:
                chave = ''
            out[chave or nome[len(escritor.PREFIXO_ATRIBUTO):]] = nome
    return out


class Calco:
    """O GeoPackage lido inteiro (feições por tipo e tabelas de apoio)."""

    def __init__(self, caminho):
        ds = ogr.Open(caminho)
        if ds is None:
            raise ErroExportacao('Não foi possível abrir o GeoPackage {}.'.format(caminho))
        try:
            docs = _linhas(ds, 'ebgeo_documento')
            self.documento = _json(docs[0]['data_json']) if docs and docs[0].get('data_json') else None
            if self.documento is not None and not isinstance(self.documento, dict):
                raise ErroExportacao('O documento original guardado no calco está corrompido.')
            self.arquivo_origem = docs[0].get('arquivo') if docs else None
            self.sha256_origem = docs[0].get('sha256') if docs else None
            self.mapas = sorted(_linhas(ds, 'ebgeo_mapa'),
                                key=lambda m: (m['ordem'] if m.get('ordem') is not None else 1e9, m['_fid']))
            self.camadas = _linhas(ds, 'ebgeo_camada')
            self.grupos = _linhas(ds, 'ebgeo_grupo')
            self.membros = _linhas(ds, 'ebgeo_grupo_membro')
            self.icones = _linhas(ds, 'ebgeo_icone')
            self.fotos = _linhas(ds, 'ebgeo_foto')
            self.imagens_extra = _linhas(ds, 'ebgeo_imagem')
            self.tem_imagens_extra = ds.GetLayerByName('ebgeo_imagem') is not None
            self.feicoes = {}       # tipo -> [linha]
            self.attr = {}          # tipo -> {chave: coluna}
            for tipo, d in schema.TIPOS.items():
                if ds.GetLayerByName(d['tabela']) is None:
                    continue
                self.feicoes[tipo] = _linhas(ds, d['tabela'])
                self.attr[tipo] = _colunas_attr(ds, d['tabela'])
        finally:
            ds = None


# ---------------------------------------------------------------- montagem

def _b64(s):
    try:
        return base64.b64decode(s) if s else None
    except (ValueError, TypeError):
        return None


def _agora_ms():
    return int(time.time() * 1000)


class Montador:
    def __init__(self, calco, gerar_desenho=None, log=None, original=None):
        self.c = calco
        self.gerar_desenho = gerar_desenho
        self.log = log or _log
        self.original = original  # o .ebgeo importado, para o calco anterior à ebgeo_imagem
        self.rel = Relatorio()
        self.imagens = {}
        self.doc0 = calco.documento or {}
        silencioso = logging.getLogger('EBGeo.Calco.exportador.silencioso')
        silencioso.propagate = False
        # o original normalizado como o importador o viu: (mapa) -> {tipo: [feição]}
        self.orig_baldes = {}
        self.orig_por_id = {}   # (tipo, id) -> feição normalizada
        if self.doc0.get('maps'):
            for nome in leitor.ordem_mapas(self.doc0):
                m = self.doc0['maps'][nome]
                baldes = leitor.normalizar_baldes((m or {}).get('features'), nome, silencioso)
                self.orig_baldes[nome] = baldes
                for tipo, lista in baldes.items():
                    for f in lista:
                        i = (f.get('properties') or {}).get('id')
                        if i is not None:
                            self.orig_por_id.setdefault((tipo, i), f)
        self.ids_calco = {l.get('ebgeo_id') for ls in calco.feicoes.values() for l in ls}
        self.fotos_por_feicao = {}
        for r in calco.fotos:
            self.fotos_por_feicao.setdefault(r.get('ebgeo_id'), []).append(r)

    # ---------------------------------------------------- avisos
    def _aviso(self, msg):
        self.rel.avisos.append(msg)
        self.log.warning(msg)

    def _imagem(self, ident, b, mime):
        if ident and b and ident not in self.imagens:
            self.imagens[ident] = (b, mime or leitor.farejar_mime(b) or 'image/png')

    # ---------------------------------------------------- feição
    @staticmethod
    def descartada_na_importacao(tipo, f):
        """O veredito do importador: geometria que ele não grava (feição repassada como veio)."""
        return escritor.geometria_qgis(tipo, f.get('geometry'), copy.deepcopy(f.get('properties') or {})) is None

    @staticmethod
    def _razao_texto_area(linha, p, props0, editadas, novo):
        """
        A posição do texto da área que o Web vai desenhar é a que o Desktop desenha. Sem a chave
        text_ratio (ou com o que o Number() do Web não lê), o Web resolve o padrão da posição a
        partir do text_position e do tipo; quando a edição no Desktop muda essa resolução, ou a
        área nova tem a razão nula, a chave vai com o valor da coluna. A feição não editada
        sai como veio: o importador gravou na coluna o mesmo padrão.
        """
        coluna = _norm('real', linha['text_ratio'])
        web = schema.razao_texto_area(p)
        if abs(schema.razao_desenhada_area(web) - schema.razao_desenhada_area(coluna)) <= TOL_REAL:
            return
        p['text_ratio'] = None if coluna is None else _para_web(
            'real', coluna, None if novo else props0.get('text_ratio'), not novo and 'text_ratio' in props0)
        if not novo and 'text_ratio' not in editadas:
            editadas.append('text_ratio')

    def feicao(self, tipo, linha):
        """(feição GeoJSON do Web, situação) a partir da linha do calco."""
        props0 = _json(linha.get('props'))
        novo = not isinstance(props0, dict)
        eid = linha.get('ebgeo_id') or (None if novo else props0.get('id')) or str(uuid.uuid4())
        p = {} if novo else copy.deepcopy(props0)
        base = {} if novo else escritor.linha_feicao(tipo, linha.get('mapa'), copy.deepcopy(props0), None)
        editadas = []
        for col, tp, _padrao, web in schema.campos(tipo):
            if web is None or col in COLUNAS_FORA or col not in linha:
                continue
            atual = linha[col]
            if novo:
                if atual is not None:
                    p[web] = _para_web(tp, atual, None, False)
                continue
            if _iguais(tp, _norm(tp, atual, col), _norm(tp, base.get(col), col)):
                continue
            editadas.append(col)
            p[web] = _para_web(tp, atual, props0.get(web), web in props0)
        if tipo == 'coordination_area' and 'text_ratio' in linha:
            self._razao_texto_area(linha, p, props0, editadas, novo)
        if tipo == 'arrow' and not novo and 'ramos' in linha and not _iguais_prof(
                _json(linha['ramos']), _json(base.get('ramos'))):
            editadas.append('ramos')  # as propriedades de um ramo, editadas na coluna (Montador._ramos)

        p['id'] = eid
        camada = linha.get('camada_id') or 'default'
        if novo:
            p['layerId'] = camada
            p.setdefault('source', tipo)
        elif (props0.get('layerId') or 'default') != camada:
            p['layerId'] = camada
            editadas.append('camada_id')

        extra = self._atributos(tipo, linha, p, props0, base, novo)
        extra |= self._fotos(eid, p, props0, novo)
        if tipo == 'military_symbol' and (novo or 'sidc' in editadas):
            for k, v in partes_sidc(p.get('sidc')).items():
                if v is not None or k in p:
                    p[k] = v
        if novo:
            agora = _agora_ms()
            p.setdefault('createdAt', agora)
            p.setdefault('updatedAt', p['createdAt'])
            p.setdefault('visivel', True)
            p.setdefault('bloqueado', False)
            p.setdefault('nome', '')
            p.setdefault('descricao', '')
            if tipo == 'arrow':
                p.setdefault('geometryType', 'arrow')

        orig = self.orig_por_id.get((tipo, eid))
        geometria, geo_mudou = self._geometria(tipo, linha, p, orig, editadas, novo)
        desenho_mudou = any(c not in NEUTRAS for c in editadas)

        # bitmaps: a Imagem leva os bytes sempre; o símbolo leva o do arquivo se não mudou o desenho
        b = _b64(linha.get('bitmap_b64'))
        if tipo == 'image':
            if b:
                self._imagem(eid, b, linha.get('bitmap_mime'))
            else:
                self._aviso('Imagem "{}" ({}) sem os bytes no calco: sai sem a figura.'.format(p.get('nome'), eid))
        elif tipo in TIPOS_SIMBOLO and b and not novo and not desenho_mudou:
            self._imagem(eid, b, linha.get('bitmap_mime'))

        for c in editadas:
            self.rel.colunas_editadas[c] = self.rel.colunas_editadas.get(c, 0) + 1
        if novo:
            situacao = 'nova'
        elif editadas or geo_mudou or extra:
            situacao = 'editada'
        else:
            situacao = 'igual'
        if orig is not None:
            f = {}
            for k, v in orig.items():
                f[k] = p if k == 'properties' else geometria if k == 'geometry' else copy.deepcopy(v)
            f.setdefault('properties', p)
            f.setdefault('geometry', geometria)
        else:
            f = {'type': 'Feature', 'id': eid, 'properties': p, 'geometry': geometria}
        return f, situacao

    def _atributos(self, tipo, linha, p, props0, base, novo):
        """attributes: o JSON `atributos` com as colunas attr_* editadas por cima. Devolve {mudou}."""
        attrs0 = None if novo else props0.get('attributes')
        atual = _json(linha.get('atributos'))
        mudou = False
        if novo:
            attrs = dict(atual) if isinstance(atual, dict) else {}
        elif not _iguais_prof(atual, _json(base.get('atributos'))):
            attrs = dict(atual) if isinstance(atual, dict) else {}
            mudou = True
        else:
            attrs = copy.deepcopy(attrs0) if isinstance(attrs0, dict) else None
        for chave, col in self.c.attr.get(tipo, {}).items():
            if col not in linha:
                continue
            v = linha[col]
            if novo:
                if v not in (None, ''):
                    attrs[chave] = v
                continue
            b = escritor.valor_coluna('str', attrs0[chave]) if isinstance(attrs0, dict) and chave in attrs0 else None
            if _iguais('str', v, b):
                continue
            mudou = True
            attrs = attrs if attrs is not None else {}
            if v is None:
                attrs.pop(chave, None)
            else:
                attrs[chave] = v
        if novo or mudou:
            p['attributes'] = attrs
        return {'atributos'} if mudou else set()

    def _fotos(self, eid, p, props0, novo):
        """properties.images e os bytes das fotos anexas (ebgeo_foto). Devolve {mudou}."""
        linhas = self.fotos_por_feicao.get(eid, [])
        lista0 = None if novo else props0.get('images')
        if not isinstance(lista0, list):
            lista0 = None
        por_id = {r.get('foto_id'): r for r in linhas}
        saida, vistos, mudou = [], set(), False
        for e in lista0 or []:
            fid = e if isinstance(e, str) else (e.get('id') if isinstance(e, dict) else None)
            r = por_id.get(fid)
            if r is None:
                mudou = True  # foto tirada no Desktop
                continue
            vistos.add(fid)
            saida.append(e)
            inline = isinstance(e, dict) and isinstance(e.get('data'), str) and e['data'].startswith('data:')
            if not inline:
                b = _b64(r.get('bitmap_b64'))
                if b:
                    self._imagem(fid, b, r.get('mime'))
                else:
                    self._aviso('Foto "{}" da feição {} sem os bytes no calco.'.format(r.get('nome'), eid))
        for r in linhas:
            fid = r.get('foto_id') or str(uuid.uuid4())
            if fid in vistos:
                continue
            b = _b64(r.get('bitmap_b64'))
            if not b:
                continue
            mudou = True
            mime = r.get('mime') or leitor.farejar_mime(b) or 'image/png'
            e = {'id': fid, 'name': r.get('nome') or fid, 'type': mime, 'size': len(b)}
            mini = _b64(r.get('miniatura_b64'))
            if mini:
                e['thumbnail'] = 'data:{};base64,{}'.format(leitor.farejar_mime(mini) or 'image/jpeg',
                                                           r['miniatura_b64'])
            saida.append(e)
            self._imagem(fid, b, mime)
        if novo:
            p['images'] = saida
        elif mudou:
            p['images'] = saida
        return {'fotos'} if mudou else set()

    # ---------------------------------------------------- geometria
    def _desenho(self, tipo, linha, geo, p=None):
        """A geometria desenhada pelo estilo do calco (gerar_desenho), arredondada como o Web grava."""
        if self.gerar_desenho is None:
            return None
        if (tipo == 'arrow' and p is not None and p.get('isMerged') and isinstance(p.get('branches'), list)
                and len(p['branches']) > 1):
            linha = dict(linha)
            linha['_ramos'] = [(self._colunas_do_ramo(linha, r), r.get('baseCoordinates'))
                               for r in p['branches'] if isinstance(r, dict) and r.get('baseCoordinates')]
        try:
            g = self.gerar_desenho(tipo, linha, geo)
        except Exception as e:  # o desenho que falha não derruba a exportação
            self._aviso('{} {}: desenho não refeito ({}).'.format(schema.TIPOS[tipo]['nome_pt'],
                                                                 linha.get('ebgeo_id'), e))
            return None
        if not isinstance(g, dict) or not g.get('coordinates'):
            return None
        return {'type': g['type'], 'coordinates': _arredondar(g['coordinates'])}

    @staticmethod
    def _colunas_do_ramo(linha, ramo):
        """
        As colunas com que o estilo desenha um ramo sozinho, pela regra de generateMergedGeometry do
        Web: largura e razão da cabeça falsas caem na da feição (branch.width || properties.width),
        as demais não caem (showArrowHead !== false, doubleHeaded === true, airmobile || false,
        airmobilePosition || 0,7). A coluna `ramos` sai: o ramo desenhado sozinho é uma seta simples.
        """
        cols = dict(linha)
        cols['ramos'] = None
        if ramo.get('width'):
            cols['width_m'] = ramo['width']
        if ramo.get('headLengthRatio'):
            cols['head_length_ratio'] = ramo['headLengthRatio']
        cols['show_arrow_head'] = ramo.get('showArrowHead') is not False
        cols['double_headed'] = ramo.get('doubleHeaded') is True
        cols['airmobile'] = bool(ramo.get('airmobile'))
        cols['airmobile_position'] = ramo.get('airmobilePosition') or 0.7
        return cols

    def _geometria(self, tipo, linha, p, orig, editadas, novo):
        """(geometria GeoJSON do Web, mudou?) e as chaves derivadas atualizadas em p."""
        geo = linha.get('_geo')
        if geo is None:
            raise ErroExportacao('{} {} sem geometria no calco.'.format(schema.TIPOS[tipo]['nome_pt'],
                                                                      linha.get('ebgeo_id')))
        base = None
        if orig is not None:
            base = escritor.geometria_qgis(tipo, orig.get('geometry'), copy.deepcopy(orig.get('properties') or {}))
        refaz = any(c in DESENHO_TATICO.get(tipo, ()) for c in editadas)
        co = geo['coordinates']
        if base is not None and _geo_iguais(base, geo):
            g = copy.deepcopy(orig.get('geometry'))
            if refaz:
                if tipo == 'arrow':
                    self._ramos(p, co, editadas, linha)
                g = self._desenho(tipo, linha, geo, p) or self._reserva(tipo, linha, co, g)
            return g, False

        alvo = schema.TIPOS[tipo]['geometria']
        if tipo in TATICOS_EIXO:
            p['baseCoordinates'] = [_xy(c) for c in co]
            g = self._desenho(tipo, linha, geo, p)
            return g or self._reserva(tipo, linha, co, None), True
        if tipo == 'arrow':
            self._ramos(p, co, editadas, linha)
            g = self._desenho(tipo, linha, geo, p)
            return g or self._reserva(tipo, linha, co, orig.get('geometry') if orig else None), True
        if alvo == 'Point':
            if tipo == 'magnetic_declination' and (novo or 'latitude' in p or 'longitude' in p):
                p['longitude'], p['latitude'] = co[0], co[1]
            return {'type': 'Point', 'coordinates': _arredondar(_xy(co))}, True
        if tipo in ('line', 'brush'):
            if tipo == 'line' or 'baseCoordinates' in p:
                p['baseCoordinates'] = [_xy(c) for c in co]
            if p.get('profileData') is not None:
                p['profileData'] = None  # perfil de elevação do traçado antigo
            return {'type': 'LineString', 'coordinates': _arredondar(co)}, True
        if alvo == 'MultiPolygon':
            if tipo in FORMAS_PARAMETRICAS and base is not None:
                d = _translacao(base, geo)
                if d is not None:
                    for k in PARAMETROS_PONTO:
                        v = p.get(k)
                        if isinstance(v, list) and len(v) >= 2:
                            p[k] = _deslocar(v, *d)
                    g = copy.deepcopy(orig.get('geometry'))
                    g['coordinates'] = _arredondar(_deslocar(g['coordinates'], *d))
                    return g, True
                g, motivo = self._forma_ajustada(tipo, p, orig, geo)
                if g is not None:
                    return g, True
                self._aviso('{} "{}" editada vértice a vértice: {}; o Web a mostra como desenhada, mas a edita '
                            'pelos parâmetros (centro, raio).'.format(schema.TIPOS[tipo]['nome_pt'], p.get('nome'),
                                                                      motivo))
            partes = co
            if tipo in ('polygon', 'coordination_area'):
                if tipo == 'coordination_area' or 'baseCoordinates' in p or novo:
                    anel = partes[0][0]
                    fechado = len(anel) > 1 and anel[0] == anel[-1]
                    p['baseCoordinates'] = [_xy(c) for c in (anel[:-1] if fechado else anel)]
                if len(partes) > 1:
                    self._aviso('{} "{}" com {} partes: o Web desenha, mas edita só polígono simples.'.format(
                        schema.TIPOS[tipo]['nome_pt'], p.get('nome'), len(partes)))
            if len(partes) == 1 and (orig is None or (orig.get('geometry') or {}).get('type') != 'MultiPolygon'):
                return {'type': 'Polygon', 'coordinates': _arredondar(partes[0])}, True
            return {'type': 'MultiPolygon', 'coordinates': _arredondar(partes)}, True
        if alvo == 'MultiLineString':
            if len(co) == 1 and orig is not None and (orig.get('geometry') or {}).get('type') == 'LineString':
                return {'type': 'LineString', 'coordinates': _arredondar(co[0])}, True
            return {'type': 'MultiLineString', 'coordinates': _arredondar(co)}, True
        return {'type': geo['type'], 'coordinates': _arredondar(co)}, True

    def _forma_ajustada(self, tipo, p, orig, geo):
        """
        Forma paramétrica editada no QGIS (escalada, girada): se o polígono ainda é a forma, os
        parâmetros do Web são recalculados (formas.ajustar) e a geometria sai regenerada por eles,
        com o gerador do Web. Devolve (geometria, None), ou (None, motivo) quando deixou de ser a forma.
        """
        from . import formas
        nome = schema.TIPOS[tipo]['nome_pt'].lower()
        g0 = orig.get('geometry') or {}
        anel0 = (g0.get('coordinates') or [[]])[0] if g0.get('type') == 'Polygon' else (
            ((g0.get('coordinates') or [[[]]])[0] or [[]])[0] if g0.get('type') == 'MultiPolygon' else None)
        partes = geo.get('coordinates') or []
        if not anel0 or len(partes) != 1 or len(partes[0]) != 1:
            return None, 'com mais de uma parte ou com furo, não é mais {}'.format(nome)
        r = formas.ajustar(tipo, p, anel0, partes[0][0])
        if r is None:
            return None, 'os parâmetros do {} não se recalculam por ela'.format(nome)
        q, anel, desvio, tol = r
        if desvio > tol:
            return None, 'não é mais {} (fica a {:.1f} m do mais próximo, tolerância de {:.1f} m)'.format(
                nome, desvio, tol).replace('.', ',')
        q['center'] = [q['center'][0], q['center'][1]]
        for k in formas._LIVRES[tipo]:
            q[k] = round(q[k], 6 if k in ('bearing', 'aperture', 'majorRadius', 'minorRadius') else 3)
        anel = formas.gerar(tipo, q)
        p['center'] = q['center']
        for k in formas._LIVRES[tipo]:
            p[k] = q[k]
        if tipo == 'rectangle':
            # buildFromModel do Web: os cantos que o modelo põe em (+w/2, +h/2) e (-w/2, -h/2)
            p['corner1'] = formas._girar_transladar(q['width'] / 2, q['height'] / 2, q['center'], q['bearing'])
            p['corner2'] = formas._girar_transladar(-q['width'] / 2, -q['height'] / 2, q['center'], q['bearing'])
        tipo_geo = g0.get('type') or 'Polygon'
        coords = [_arredondar(anel)]
        return {'type': tipo_geo, 'coordinates': coords if tipo_geo == 'Polygon' else [coords]}, None

    def _reserva(self, tipo, linha, co, anterior):
        """Sem o desenho refeito: o eixo (que o Web redesenha no Limite e na Linha) ou o contorno antigo."""
        if tipo in TATICOS_EIXO:
            return {'type': 'MultiLineString', 'coordinates': [_arredondar(co)]}
        self._aviso('{} {}: o desenho não foi refeito; o Web a mostra com o contorno anterior.'.format(
            schema.TIPOS[tipo]['nome_pt'], linha.get('ebgeo_id')))
        return anterior

    def _ramos(self, p, partes, editadas, linha=None):
        """
        Seta: baseCoordinates e, na combinada, os ramos. Cada ramo guarda as propriedades dele
        (no Web cada um tem a sua ponta dupla, largura...), as da coluna `ramos` quando ela foi
        editada; a coluna da feição editada no Desktop vai a todos, como o updateFeaturesProperty
        do Web, que a grava em cada ramo (o estilo desenha assim, seta_ramo.exp). O ramo 0 editado
        na coluna `ramos` volta também ao topo da feição, o espelho que o Web mantém
        (_updateBranchProperty), salvo na chave cuja coluna da feição foi editada.
        """
        p['baseCoordinates'] = [_xy(c) for c in partes[0]]
        if len(partes) == 1:
            if p.get('isMerged'):
                p['isMerged'] = False
                p.pop('branches', None)
            return
        web = {c: w for w, c in schema.mapa_web('arrow').items()}
        mudadas = {web[c] for c in editadas if c in web}
        antigos = p.get('branches') if isinstance(p.get('branches'), list) else []
        coluna = _json((linha or {}).get('ramos')) if 'ramos' in editadas else None
        da_coluna = coluna.get('ramos') if isinstance(coluna, dict) and isinstance(coluna.get('ramos'), list) else []
        ramos = []
        for i, parte in enumerate(partes):
            velho = i < len(antigos) and isinstance(antigos[i], dict)
            r = copy.deepcopy(antigos[i]) if velho else {}
            r['baseCoordinates'] = [_xy(c) for c in parte]
            if not velho:
                r.update({k: p[k] for k in RAMO_SETA if k in p})  # ramo novo: o da feição
            if i < len(da_coluna) and isinstance(da_coluna[i], dict):
                for k in RAMO_SETA:
                    if k in da_coluna[i]:
                        r[k] = da_coluna[i][k]
                    else:
                        r.pop(k, None)
                if i == 0:
                    for k in RAMO_SETA:
                        if k in r and k not in mudadas and (k not in p or not _iguais_prof(p[k], r[k])):
                            p[k] = r[k]
            for k in RAMO_SETA:
                if k in p and k in mudadas:
                    r[k] = p[k]
            ramos.append(r)
        p['isMerged'] = True
        p['branches'] = ramos

    # ---------------------------------------------------- documento
    def montar(self, escopo=ESCOPO_TUDO, estado=None):
        t0 = time.time()
        estado = estado or {}
        doc0 = self.doc0
        data = copy.deepcopy(doc0) if doc0 else {}

        # mapas do calco, na ordem: os de ebgeo_mapa, depois os citados por feição e ausentes
        nomes = [m['nome'] for m in self.c.mapas if m.get('nome')]
        por_mapa = {}
        for tipo, linhas in self.c.feicoes.items():
            for l in linhas:
                por_mapa.setdefault(l.get('mapa') or 'Principal', {}).setdefault(tipo, []).append(l)
        for nome in por_mapa:
            if nome not in nomes:
                if self.c.mapas:
                    self._aviso('Mapa "{}" citado por feições e ausente do atlas: criado no fim da ordem.'.format(nome))
                nomes.append(nome)
        if not nomes:
            nomes = ['Principal']
        atual = estado.get('mapa_atual')
        if atual not in nomes:
            atual = next((m['nome'] for m in self.c.mapas if m.get('atual')), None)
        if atual not in nomes:
            atual = doc0.get('currentMap') if doc0.get('currentMap') in nomes else nomes[0]
        exportar = [atual] if escopo == ESCOPO_ATUAL else list(nomes)
        self.rel.mapas = exportar

        maps0 = doc0.get('maps') or {}
        data['version'] = VERSAO
        if 'schemaVersion' in data:
            data['schemaVersion'] = VERSAO
        if isinstance(data.get('atlas'), dict) and 'schemaVersion' in data['atlas']:
            data['atlas']['schemaVersion'] = VERSAO
        data['currentMap'] = atual
        ordem0 = leitor.ordem_mapas(doc0) if maps0 else []
        if escopo == ESCOPO_TUDO and exportar == ordem0 and isinstance(doc0.get('mapOrder'), list):
            data['mapOrder'] = copy.deepcopy(doc0['mapOrder'])
        else:
            data['mapOrder'] = list(exportar)

        ids_por_mapa = {}
        mapas = {}
        for nome in exportar:
            mapas[nome], ids_por_mapa[nome] = self._mapa(nome, maps0.get(nome), por_mapa.get(nome, {}))
        data['maps'] = mapas

        for sec in SECOES_POR_MAPA:
            if isinstance(data.get(sec), dict):
                data[sec] = {k: v for k, v in data[sec].items() if k in mapas}
        data.setdefault('layers', {})
        data.setdefault('groups', {})
        for nome in exportar:
            self._notas(data, nome)
            camadas = self._camadas(nome, estado, por_mapa.get(nome, {}))
            if camadas is not None:
                data['layers'][nome] = camadas
            grupos = self._grupos(nome, ids_por_mapa[nome])
            if grupos is not None:
                data['groups'][nome] = grupos
        for sec in ('layers', 'groups'):
            if not data[sec] and sec not in doc0:
                del data[sec]
        self._icones(data)
        self._imagens_extra(data)
        self.rel.imagens = len(self.imagens)
        self.rel.segundos = time.time() - t0
        return Exportacao(data, dict(self.imagens), self.rel)

    def _mapa(self, nome, m0, linhas_por_tipo):
        novo_mapa = m0 is None
        m = copy.deepcopy(m0) if m0 else {'baseLayer': None, 'analysisLayers': {},
                                          'features': {b: [] for b in BALDES_MAPA_NOVO}}
        feats0 = (m0 or {}).get('features') or {}
        orig = self.orig_baldes.get(nome, {})
        ids = set()
        feicoes = {}
        chaves = [b for b in feats0 if b != leitor.BALDE_LEGADO_BARREIRA]
        if leitor.BALDE_LEGADO_BARREIRA in feats0 and 'coordination_lines' not in chaves:
            chaves.append('coordination_lines')
        chaves += [b for b in (BALDES_MAPA_NOVO if novo_mapa else []) if b not in chaves]
        for tipo in linhas_por_tipo:
            b = schema.TIPOS[tipo]['balde']
            if b not in chaves:
                chaves.append(b)
        for balde in chaves:
            tipo = schema.BALDE_PARA_TIPO.get(balde)
            if tipo is None:
                feicoes[balde] = copy.deepcopy(feats0.get(balde, []))  # balde que o Desktop não conhece
                continue
            lista = self._balde(tipo, orig.get(tipo, []), linhas_por_tipo.get(tipo, []))
            feicoes[balde] = lista
            self.rel.por_balde[balde] = self.rel.por_balde.get(balde, 0) + len(lista)
            ids.update((f.get('properties') or {}).get('id') for f in lista)
        m['features'] = feicoes

        linha_mapa = next((r for r in self.c.mapas if r.get('nome') == nome), None)
        if linha_mapa is not None:
            bl = linha_mapa.get('base_layer')
            if (bl or None) != (escritor.valor_coluna('str', (m0 or {}).get('baseLayer')) or None):
                m['baseLayer'] = bl
        if novo_mapa:
            self._enquadrar(m)
        return m, ids

    def _balde(self, tipo, originais, linhas):
        por_id = {}
        for l in linhas:
            por_id.setdefault(l.get('ebgeo_id'), l)
        lista, usados = [], set()
        for f0 in originais:
            i = (f0.get('properties') or {}).get('id')
            if i is not None and i in por_id and i not in usados:
                lista.append(self._contar(*self.feicao(tipo, por_id[i])))
                usados.add(i)
            elif self.descartada_na_importacao(tipo, f0):
                lista.append(copy.deepcopy(f0))
                self.rel.repassadas += 1
            elif i is not None and i not in self.ids_calco:
                self.rel.apagadas += 1
        for l in linhas:
            if l.get('ebgeo_id') not in usados or l.get('ebgeo_id') is None:
                lista.append(self._contar(*self.feicao(tipo, l)))
                usados.add(l.get('ebgeo_id'))
        return lista

    def _contar(self, f, situacao):
        if situacao == 'igual':
            self.rel.iguais += 1
        elif situacao == 'nova':
            self.rel.novas += 1
        else:
            self.rel.editadas += 1
        return f

    @staticmethod
    def _enquadrar(m):
        """Mapa novo: centro e zoom pela extensão das feições, para o Web abrir sobre elas."""
        xs, ys = [], []

        def junta(c):
            if c and isinstance(c[0], (int, float)):
                xs.append(c[0])
                ys.append(c[1])
            elif isinstance(c, list):
                for x in c:
                    junta(x)
        for lista in m['features'].values():
            for f in lista:
                junta((f.get('geometry') or {}).get('coordinates') or [])
        if not xs:
            return
        cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
        larg = max(max(xs) - min(xs), (max(ys) - min(ys)) / max(0.2, math.cos(math.radians(cy))), 1e-4)
        m['center_long'], m['center_lat'] = cx, cy
        m['zoom'] = max(1.0, min(17.0, round(math.log2(360.0 / larg) + 0.5, 1)))
        m['bearing'], m['pitch'] = 0, 0

    def _notas(self, data, nome):
        r = next((x for x in self.c.mapas if x.get('nome') == nome), None)
        if r is None:
            return
        notas = data.get('mapNotes') if isinstance(data.get('mapNotes'), dict) else {}
        n0 = notas.get(nome) if isinstance(notas.get(nome), dict) else {}
        t, d = r.get('notas_titulo'), r.get('notas_descricao')
        if (t or '') == (n0.get('title') or '') and (d or '') == (n0.get('description') or ''):
            return
        n = copy.deepcopy(n0)
        n['title'], n['description'] = t or '', d or ''
        notas[nome] = n
        data['mapNotes'] = notas

    def _camadas(self, nome, estado, linhas_por_tipo):
        linhas = [r for r in self.c.camadas if r.get('mapa') == nome]
        layers0 = (self.doc0.get('layers') or {}).get(nome)
        lista0 = [l for l in layers0 if isinstance(l, dict)] if isinstance(layers0, list) else None
        por_id0 = {l.get('id'): l for l in lista0 or []}
        arvore = estado.get('camadas') or {}
        usadas = {l.get('camada_id') or 'default' for ls in linhas_por_tipo.values() for l in ls}
        saida, vistas = [], set()

        def valores(r):
            v = {'name': r.get('nome') or r.get('camada_id'), 'visible': r.get('visivel') is not False,
                 'locked': bool(r.get('bloqueada')),
                 'opacity': 1.0 if r.get('opacidade') is None else float(r['opacidade']),
                 'order': int(r.get('ordem') or 0)}
            a = arvore.get((nome, r.get('camada_id')))
            if a:
                for k_arv, k_web in (('visivel', 'visible'), ('opacidade', 'opacity'), ('bloqueada', 'locked')):
                    if a.get(k_arv) is not None:
                        v[k_web] = a[k_arv]
            return v

        por_id = {r.get('camada_id'): r for r in linhas}
        for l0 in lista0 or []:
            r = por_id.get(l0.get('id'))
            l = copy.deepcopy(l0)
            if r is not None:
                vistas.add(l0.get('id'))
                v = valores(r)
                base = {'name': l0.get('name'), 'visible': l0.get('visible', True) is not False,
                        'locked': bool(l0.get('locked')),
                        'opacity': float(l0.get('opacity', 1) if l0.get('opacity') is not None else 1),
                        'order': l0.get('order', 0)}
                for k, val in v.items():
                    if k == 'opacity':
                        if abs(val - base[k]) > 1e-9:
                            l[k] = val
                    elif val != base[k]:
                        l[k] = val
            saida.append(l)
        agora = _agora_ms()
        for r in sorted(linhas, key=lambda x: (x.get('ordem') or 0, x['_fid'])):
            cid = r.get('camada_id')
            if cid in vistas or cid in por_id0:
                continue
            v = valores(r)
            padrao = leitor.CAMADA_PADRAO
            sintetica = (cid == 'default' and v['name'] == padrao['name'] and v['visible'] and not v['locked']
                         and abs(v['opacity'] - 1) < 1e-9)
            if sintetica and (lista0 is None or cid not in usadas):
                continue  # a camada Padrão que o importador inventou para o mapa sem a lista
            l = {'id': cid}
            l.update(v)
            l.update({'createdAt': agora, 'updatedAt': agora, 'version': 1})
            saida.append(l)
        if lista0 is None and not saida:
            return None
        return saida

    def _grupos(self, nome, ids_mapa):
        g0s = (self.doc0.get('groups') or {}).get(nome)
        g0s = g0s if isinstance(g0s, dict) else None
        linhas = {r.get('grupo_id'): r for r in self.c.grupos if r.get('mapa') == nome}
        membros = {}
        for r in self.c.membros:
            if r.get('mapa') == nome:
                membros.setdefault(r.get('grupo_id'), []).append({'type': r.get('tipo'), 'id': r.get('ebgeo_id')})
        saida, vistos = {}, set()
        for chave, g0 in (g0s or {}).items():
            if not isinstance(g0, dict):
                saida[chave] = copy.deepcopy(g0)
                continue
            gid = g0.get('id') or chave
            vistos.add(gid)
            g = copy.deepcopy(g0)
            r = linhas.get(gid)
            if r is not None:
                for k, val, b in (('name', r.get('nome'), g0.get('name')),
                                  ('visible', r.get('visivel') is not False, g0.get('visible', True) is not False),
                                  ('locked', bool(r.get('bloqueado')), bool(g0.get('locked')))):
                    if val != b:
                        g[k] = val
            refs0 = g0.get('features') if isinstance(g0.get('features'), list) else None
            novos = membros.get(gid, [])
            if refs0 is not None and [x.get('id') for x in refs0 if isinstance(x, dict)] == [x['id'] for x in novos]:
                refs = refs0
            else:
                refs = novos
            if refs is not None:
                g['features'] = [x for x in refs if not isinstance(x, dict) or x.get('id') in ids_mapa]
            saida[chave] = g
        for gid, r in linhas.items():
            if gid in vistos:
                continue
            saida[gid] = {'id': gid, 'name': r.get('nome') or gid,
                          'features': [x for x in membros.get(gid, []) if x['id'] in ids_mapa],
                          'visible': r.get('visivel') is not False, 'locked': bool(r.get('bloqueado'))}
        if g0s is None and not saida:
            return None
        return saida

    def _icones(self, data):
        lista0 = self.doc0.get('customIcons') if isinstance(self.doc0.get('customIcons'), list) else None
        por_id0 = {i.get('id'): i for i in lista0 or [] if isinstance(i, dict)}
        saida = [copy.deepcopy(i) for i in lista0 or []]
        for r in self.c.icones:
            iid = r.get('icone_id')
            if not iid:
                continue
            self._imagem(iid, _b64(r.get('bitmap_b64')), r.get('mime'))
            if iid not in por_id0:
                saida.append({'id': iid, 'name': r.get('nome') or iid})
        if saida or lista0 is not None:
            data['customIcons'] = saida

    def _imagens_extra(self, data):
        """As imagens sem dono no 2D voltam se o documento as cita (3D, 360, slides, feição repassada)."""
        texto = json.dumps(data, ensure_ascii=False)
        for r in self.c.imagens_extra:
            iid = r.get('imagem_id')
            if iid and iid not in self.imagens and iid in texto:
                self._imagem(iid, _b64(r.get('bitmap_b64')), r.get('mime'))
        if self.c.documento is not None and not self.c.tem_imagens_extra:
            if self.original and self._recuperar_do_original(texto):
                return
            self._aviso('Calco importado antes da tabela ebgeo_imagem: as fotos de 3D e 360 e as figuras de '
                        'slide do arquivo original não estão nele e saem sem os bytes. Para recuperá-las, '
                        'aponte o .ebgeo de que o calco foi importado no campo "Arquivo .ebgeo original".')

    def _recuperar_do_original(self, texto):
        """
        Os bytes que o calco antigo não guardou, tirados do .ebgeo de que ele foi importado: só se o
        arquivo é o mesmo, pelo SHA-256 do arquivo inteiro que o importador gravou em ebgeo_documento.
        Devolve se recuperou.
        """
        try:
            doc = leitor.abrir(self.original)
        except leitor.ErroEbgeo as e:
            self._aviso('O .ebgeo original não abriu ({}): as imagens não foram recuperadas.'.format(e))
            return False
        if not self.c.sha256_origem or doc.sha256 != self.c.sha256_origem:
            self._aviso('O arquivo {} não é o .ebgeo de que este calco foi importado ({}; o SHA-256 difere): as '
                        'imagens não foram recuperadas.'.format(doc.arquivo, self.c.arquivo_origem or 'origem sem nome'))
            return False
        n = 0
        for iid, (b, mime) in doc.imagens.items():
            if iid not in self.imagens and iid in texto:
                self._imagem(iid, b, mime)
                n += 1
        self.rel.recuperadas = n
        self.log.info('%d imagens recuperadas do .ebgeo original %s (SHA-256 conferido).', n, doc.arquivo)
        return True


def montar(caminho_gpkg, escopo=ESCOPO_TUDO, estado=None, gerar_desenho=None, log=None, original=None):
    """
    Lê o calco e devolve a Exportacao (data.json, imagens, relatório). `original`: o .ebgeo de que o
    calco foi importado, de onde o calco anterior à tabela ebgeo_imagem recupera os bytes que não guardou.
    """
    return Montador(Calco(caminho_gpkg), gerar_desenho, log, original).montar(escopo, estado)
