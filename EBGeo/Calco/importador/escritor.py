# -*- coding: utf-8 -*-
"""
Escritor do calco: grava o .ebgeo aberto pelo leitor num GeoPackage, uma
tabela por tipo (schema.py), só com GDAL/OGR (sem QGIS).

Geometria QGIS por tipo (tabela na seção 2 de EBGeo/Calco/ARQUITETURA.md):
- tipos táticos (boundary, coordination_line, occupied_front) pelo eixo em
  properties.baseCoordinates; a seta (arrow) vira MultiLineString com um ramo
  por parte (branches[] quando isMerged); a geometria gravada pelo Web vai
  para geom_desenho como WKT;
- Polygon, LineString promovidos a Multi* quando a tabela pede;
- círculo, elipse, setor (e visibilidade) gravados como Point (fixture 01)
  são regenerados pelo centro e pelos parâmetros, com pyproj Geod;
- antimeridiano desembrulhado (salto de longitude acima de 180°);
- coordenada nula ou não finita: a feição é descartada com log.
"""
import base64
import datetime
import json
import logging
import math
import os
import time
import uuid

from osgeo import ogr

from .. import schema, gpkg
from . import leitor

ogr.UseExceptions()

_log = logging.getLogger('EBGeo.Calco.importador')

TIPOS_TATICOS_EIXO = ('boundary', 'coordination_line', 'occupied_front')
TIPOS_FORMA_PARAMETRICA = ('circle', 'ellipse', 'rectangle', 'sector')
TIPOS_SIMBOLO = ('military_symbol', 'coordination_measure', 'engineering_symbol', 'magnetic_declination')

# Chaves de properties que viram a coluna 'parametros' (JSON) por tipo.
_PARAM_FORMA = ['center', 'radius', 'majorRadius', 'minorRadius', 'bearing', 'aperture',
                'corner1', 'corner2', 'width', 'height', 'borderRadius', 'coordinationPoint']
_PARAM_ANALISE = ['observerHeight', 'targetHeight', 'samplePoints', 'visibleLength', 'obstructedLength',
                  'totalLength', 'profile', 'measure', 'width', 'center', 'radius', 'bearing', 'aperture']
PARAMETROS = {t: _PARAM_FORMA for t in ('polygon',) + TIPOS_FORMA_PARAMETRICA}
PARAMETROS.update({t: _PARAM_ANALISE for t in ('los', 'visibility', 'processed_los', 'processed_visibility')})

# Padrões das ferramentas do Web para regenerar formas gravadas como Point.
RAIO_PADRAO_M = 1000.0
ELIPSE_PADRAO_KM = (1.0, 0.5)
SETOR_PADRAO = {'aperture': 60.0, 'bearing': 0.0}

_GEOD = None


def _geod():
    global _GEOD
    if _GEOD is None:
        from pyproj import Geod
        _GEOD = Geod(ellps='WGS84')
    return _GEOD


class Relatorio:
    """Resultado da gravação; os números para conferir vêm de RELER o GPKG, não daqui."""

    def __init__(self, caminho):
        self.caminho = caminho
        self.contagem = {}          # tipo -> feições gravadas
        self.descartadas = []       # (mapa, tipo, ebgeo_id, motivo)
        self.avisos = []
        self.mapas = 0
        self.svg_renderizados = 0
        self.colunas_atributos = {}  # tipo -> {chave original: coluna attr_*}
        self.motor_simbolos = None  # None: não tentado; False: indisponível; True: usado
        self.segundos = 0.0

    def total(self):
        return sum(self.contagem.values())


# ---------------------------------------------------------------- coordenadas

def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _posicao_ok(p):
    return isinstance(p, (list, tuple)) and len(p) >= 2 and _num(p[0]) and _num(p[1])


def _lista_posicoes(lst, minimo):
    if not isinstance(lst, (list, tuple)) or len(lst) < minimo:
        return None
    out = []
    for p in lst:
        if not _posicao_ok(p):
            return None
        out.append([float(p[0]), float(p[1])])
    return out


def _desembrulhar(coords):
    """Antimeridiano: cada salto de longitude acima de 180° é corrigido em ±360°."""
    if not coords:
        return coords
    out = [list(coords[0])]
    desloc = 0.0
    for i in range(1, len(coords)):
        dx = coords[i][0] - coords[i - 1][0]
        if dx > 180:
            desloc -= 360.0
        elif dx < -180:
            desloc += 360.0
        out.append([coords[i][0] + desloc, coords[i][1]])
    return out


def _linha(coords):
    c = _lista_posicoes(coords, 2)
    return _desembrulhar(c) if c else None


def _anel(coords):
    c = _lista_posicoes(coords, 4)
    if not c:
        return None
    c = _desembrulhar(c)
    if c[0] != c[-1]:
        c.append(list(c[0]))
    return c


def _poligono(coords):
    if not isinstance(coords, (list, tuple)) or not coords:
        return None
    aneis = [_anel(a) for a in coords]
    if any(a is None for a in aneis):
        return None
    return aneis


# ---------------------------------------------------------------- formas geodésicas

def _destino(lon, lat, azimute, distancia_m):
    x, y, _ = _geod().fwd(lon, lat, azimute, distancia_m)
    return [x, y]


def gerar_circulo(centro, raio_m, passos=64):
    lon, lat = centro
    pts = [_destino(lon, lat, 90.0 - i * 360.0 / passos, raio_m) for i in range(passos)]
    pts.append(list(pts[0]))
    return [_desembrulhar(pts)]


def gerar_elipse(centro, maior_km, menor_km, azimute, passos=64):
    """Eixo maior na direção do azimute (turf.ellipse com angle = bearing - 90)."""
    lon, lat = centro
    a, b = maior_km * 1000.0, menor_km * 1000.0
    pts = []
    for i in range(passos):
        t = 2 * math.pi * i / passos
        u, v = a * math.cos(t), b * math.sin(t)
        d = math.hypot(u, v)
        az = azimute + math.degrees(math.atan2(v, u))
        pts.append(_destino(lon, lat, az, d) if d > 0 else [lon, lat])
    pts.append(list(pts[0]))
    return [_desembrulhar(pts)]


def gerar_setor(centro, raio_m, azimute, abertura):
    """Mesmo desenho de add_sector_geometry.js: centro, arco, volta ao centro."""
    lon, lat = centro
    n = max(16, int(round(64 * abertura / 360.0)))
    ini = azimute - abertura / 2.0
    pts = [[lon, lat]]
    for i in range(n + 1):
        pts.append(_destino(lon, lat, ini + i * abertura / n, raio_m))
    pts.append([lon, lat])
    return [_desembrulhar(pts)]


def _num_ou(p, chave, padrao):
    v = p.get(chave)
    return float(v) if _num(v) else padrao


def _regenerar_forma(tipo, ponto, p, nota):
    """Forma gravada como Point (fixture 01): regenera pelo centro e pelos parâmetros do Web."""
    centro = p.get('center') if _posicao_ok(p.get('center')) else ponto
    centro = [float(centro[0]), float(centro[1])]
    usados = {'center': centro}
    if tipo == 'circle' or (tipo == 'visibility' and not _num(p.get('aperture'))):
        r = _num_ou(p, 'radius', RAIO_PADRAO_M)
        usados['radius'] = r
        nota.append('raio {} m'.format(r) + ('' if _num(p.get('radius')) else ' (padrão, radius ausente)'))
        return gerar_circulo(centro, r), usados
    if tipo in ('sector', 'visibility'):
        r = _num_ou(p, 'radius', RAIO_PADRAO_M)
        ab = _num_ou(p, 'aperture', SETOR_PADRAO['aperture'])
        az = _num_ou(p, 'bearing', SETOR_PADRAO['bearing'])
        usados.update(radius=r, aperture=ab, bearing=az)
        if not _num(p.get('radius')):
            nota.append('raio padrão {} m (radius ausente)'.format(r))
        if ab >= 360:
            return gerar_circulo(centro, r), usados
        return gerar_setor(centro, r, az, ab), usados
    if tipo == 'ellipse':
        a = _num_ou(p, 'majorRadius', ELIPSE_PADRAO_KM[0])
        b = _num_ou(p, 'minorRadius', ELIPSE_PADRAO_KM[1])
        az = _num_ou(p, 'bearing', 0.0)
        usados.update(majorRadius=a, minorRadius=b, bearing=az)
        if not _num(p.get('majorRadius')):
            nota.append('eixos padrão {} x {} km (majorRadius ausente)'.format(a, b))
        return gerar_elipse(centro, a, b, az), usados
    if tipo == 'rectangle':
        c1, c2 = p.get('corner1'), p.get('corner2')
        if _posicao_ok(c1) and _posicao_ok(c2):
            x0, x1 = sorted([float(c1[0]), float(c2[0])])
            y0, y1 = sorted([float(c1[1]), float(c2[1])])
            return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]], usados
        w, h = p.get('width'), p.get('height')
        if _num(w) and _num(h):
            az = _num_ou(p, 'bearing', 0.0)
            d = math.hypot(w, h) / 2.0
            ang = math.degrees(math.atan2(w, h))
            pts = [_destino(centro[0], centro[1], az + s, d) for s in (-ang, ang, 180 - ang, 180 + ang)]
            pts.append(list(pts[0]))
            return [_desembrulhar(pts)], usados
    return None, usados


# ---------------------------------------------------------------- geometria por tipo

def geometria_qgis(tipo, geom, p, nota=None):
    """
    GeoJSON (dict) na geometria da tabela do tipo, ou None (descartar).
    `nota` recebe frases sobre o que foi regenerado ou adaptado.
    """
    nota = nota if nota is not None else []
    alvo = schema.TIPOS[tipo]['geometria']
    g = geom if isinstance(geom, dict) else {}
    gt = g.get('type')
    co = g.get('coordinates')

    if tipo in TIPOS_TATICOS_EIXO:
        eixo = _linha(p.get('baseCoordinates'))
        if eixo is None and p.get('baseCoordinates') is not None:
            return None
        if eixo is None:
            if gt == 'LineString':
                eixo = _linha(co)
                nota.append('eixo pela geometria gravada (sem baseCoordinates)')
            elif gt == 'MultiLineString' and co:
                eixo = _linha(co[0])
                nota.append('eixo pela primeira parte da geometria gravada (sem baseCoordinates)')
        return {'type': 'LineString', 'coordinates': eixo} if eixo else None

    if tipo == 'arrow':
        partes = []
        if p.get('isMerged') and isinstance(p.get('branches'), list) and len(p['branches']) > 1:
            for br in p['branches']:
                ln = _linha((br or {}).get('baseCoordinates'))
                if ln is None:
                    return None
                partes.append(ln)
        elif p.get('baseCoordinates') is not None:
            ln = _linha(p.get('baseCoordinates'))
            if ln is None:
                return None
            partes.append(ln)
        elif gt == 'LineString':
            ln = _linha(co)
            if ln:
                partes.append(ln)
                nota.append('eixo pela geometria gravada (sem baseCoordinates)')
        elif gt == 'MultiLineString':
            partes = [_linha(c) for c in co or []]
            if any(x is None for x in partes):
                return None
        return {'type': 'MultiLineString', 'coordinates': partes} if partes else None

    if alvo == 'Point':
        if gt == 'Point' and _posicao_ok(co):
            return {'type': 'Point', 'coordinates': [float(co[0]), float(co[1])]}
        if gt == 'MultiPoint' and co and _posicao_ok(co[0]):
            nota.append('MultiPoint reduzido ao primeiro ponto')
            return {'type': 'Point', 'coordinates': [float(co[0][0]), float(co[0][1])]}
        return None

    if alvo == 'LineString':
        if gt == 'LineString':
            ln = _linha(co)
            return {'type': 'LineString', 'coordinates': ln} if ln else None
        if gt == 'MultiLineString' and co:
            if len(co) > 1:
                nota.append('MultiLineString de {} partes reduzida à primeira'.format(len(co)))
            ln = _linha(co[0])
            return {'type': 'LineString', 'coordinates': ln} if ln else None
        return None

    if alvo == 'MultiLineString':
        if gt == 'LineString':
            ln = _linha(co)
            return {'type': 'MultiLineString', 'coordinates': [ln]} if ln else None
        if gt == 'MultiLineString' and co:
            partes = [_linha(c) for c in co]
            return None if any(x is None for x in partes) else {'type': 'MultiLineString', 'coordinates': partes}
        return None

    if alvo == 'MultiPolygon':
        if gt == 'Polygon':
            pg = _poligono(co)
            return {'type': 'MultiPolygon', 'coordinates': [pg]} if pg else None
        if gt == 'MultiPolygon' and co:
            pgs = [_poligono(c) for c in co]
            return None if any(x is None for x in pgs) else {'type': 'MultiPolygon', 'coordinates': pgs}
        if gt == 'Point' and _posicao_ok(co) and tipo in TIPOS_FORMA_PARAMETRICA + ('visibility',):
            pg, usados = _regenerar_forma(tipo, co, p, nota)
            if pg:
                nota.insert(0, 'regenerada de Point')
                p.setdefault('_regenerado', usados)
                return {'type': 'MultiPolygon', 'coordinates': [pg]}
        return None
    return None


# ---------------------------------------------------------------- valores

def _datahora(v):
    """createdAt/updatedAt: epoch em ms (2.x) ou texto ISO -> datetime UTC."""
    if _num(v):
        seg = v / 1000.0 if abs(v) > 1e11 else float(v)
        try:
            return datetime.datetime.fromtimestamp(seg, tz=datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(v, str) and v:
        try:
            d = datetime.datetime.fromisoformat(v.replace('Z', '+00:00'))
            return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return None
    return None


def valor_coluna(tp, v):
    """Valor de properties -> valor gravável na coluna do tipo `tp` do schema (None = NULL)."""
    if v is None:
        return None
    if tp == 'json':
        return json.dumps(v, ensure_ascii=False)
    if tp == 'bool':
        if isinstance(v, str):
            return v.strip().lower() in ('true', '1', 'sim', 'yes')
        return bool(v)
    if tp == 'real':
        if isinstance(v, bool):
            return float(v)
        if _num(v):
            return float(v)
        if isinstance(v, str):
            try:
                f = float(v.replace(',', '.'))
                return f if math.isfinite(f) else None
            except ValueError:
                return None
        return None
    if tp == 'int':
        r = valor_coluna('real', v)
        return int(r) if r is not None else None
    if tp == 'datetime':
        return _datahora(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v)


def _set(feat, idx, tp, val):
    if val is None:
        feat.SetFieldNull(idx)
    elif tp == 'bool':
        feat.SetField(idx, 1 if val else 0)
    elif tp == 'datetime':
        feat.SetField(idx, val.year, val.month, val.day, val.hour, val.minute,
                      val.second + val.microsecond / 1e6, 100)
    else:
        feat.SetField(idx, val)


def _wkt(geojson):
    if not isinstance(geojson, dict) or not geojson.get('type'):
        return None
    try:
        return ogr.CreateGeometryFromJson(json.dumps(geojson)).ExportToWkt()
    except Exception:
        return None


def _data_url(s):
    """'data:image/png;base64,AAAA' -> (mime, base64) ou (None, None)."""
    if not isinstance(s, str) or not s.startswith('data:') or ',' not in s:
        return None, None
    cab, dados = s.split(',', 1)
    mime = cab[5:].split(';')[0] or None
    if ';base64' not in cab:
        dados = base64.b64encode(dados.encode('utf-8')).decode('ascii')
    return mime, dados


# ---------------------------------------------------------------- motor de símbolos (opcional)

def _carregar_motor(rel, log):
    """simbolos.renderizar(tipo, atributos), se o módulo do outro agente existir e carregar."""
    try:
        from .. import simbolos
    except Exception as e:  # ImportError ou falha do motor JS
        rel.motor_simbolos = False
        log.info('motor de símbolos indisponível (%s); fica o bitmap do arquivo', e)
        return None
    disp = getattr(simbolos, 'disponivel', None)
    try:
        if callable(disp) and not disp():
            rel.motor_simbolos = False
            log.info('motor de símbolos presente mas não carregou; fica o bitmap do arquivo')
            return None
    except Exception as e:
        rel.motor_simbolos = False
        log.info('motor de símbolos falhou ao iniciar (%s); fica o bitmap do arquivo', e)
        return None
    if not callable(getattr(simbolos, 'renderizar', None)):
        rel.motor_simbolos = False
        return None
    rel.motor_simbolos = True
    return simbolos.renderizar


_CHAVES_RENDER = ('svg', 'svg_assinatura', 'largura_px', 'altura_px', 'ancora_dx', 'ancora_dy')


def _aplicar_render(renderizar, tipo, linha, log):
    try:
        r = renderizar(tipo, dict(linha))
    except Exception as e:
        log.warning('%s %s: o motor de símbolos falhou (%s); fica o bitmap do arquivo',
                    tipo, linha.get('ebgeo_id'), e)
        return False
    if isinstance(r, (bytes, bytearray)):
        r = r.decode('utf-8')
    if isinstance(r, str) and r.strip():
        linha['svg'] = r
        return True
    if isinstance(r, dict) and r.get('svg'):
        for k in _CHAVES_RENDER:
            if k in r:
                linha[k] = r[k]
        return True
    if r is not None and getattr(r, 'svg', None):
        for k in _CHAVES_RENDER:
            if hasattr(r, k):
                linha[k] = getattr(r, k)
        return True
    return False


# ---------------------------------------------------------------- linha da tabela

def linha_feicao(tipo, mapa, p, grupos):
    """Dicionário coluna -> valor para a tabela do tipo, a partir das properties do Web."""
    linha = {}
    for col, tp, padrao, web in schema.campos(tipo):
        if web is not None:
            if web in p:
                linha[col] = valor_coluna(tp, p[web])
            elif web in schema.AUSENTE_COMO_NULA.get(tipo, ()):
                linha[col] = None  # o Web desenha a chave ausente como a nula (schema.AUSENTE_COMO_NULA)
            elif tp == 'json' and isinstance(padrao, str):
                linha[col] = padrao  # o padrão do schema já é JSON em texto
            else:
                linha[col] = valor_coluna(tp, padrao) if padrao is not None else None
        else:
            linha[col] = valor_coluna(tp, padrao) if (padrao is not None and tp != 'json') else None
    if tipo == 'coordination_area':
        # a chave ausente (ou não numérica) é o padrão da posição no Web, não o nulo
        linha['text_ratio'] = schema.razao_texto_area(p)
    if tipo == 'arrow':
        # as propriedades de cada ramo da seta combinada, que o estilo desenha ramo a ramo
        ramos = schema.ramos_seta(p, linha)
        linha['ramos'] = json.dumps(ramos, ensure_ascii=False) if ramos else None
    linha['mapa'] = mapa
    linha['camada_id'] = p.get('layerId') or 'default'
    linha['ebgeo_id'] = p.get('id')
    linha['grupos'] = json.dumps(grupos, ensure_ascii=False) if grupos else None
    props = {k: v for k, v in p.items() if k != '_regenerado'}
    linha['props'] = json.dumps(props, ensure_ascii=False)
    if 'parametros' in linha:
        chaves = PARAMETROS.get(tipo, [])
        par = {k: p[k] for k in chaves if k in p}
        if tipo.startswith('processed_') and isinstance(p.get('id'), str):
            base = p['id']
            for suf in ('-visible', '-obstructed'):
                if base.endswith(suf):
                    par['origem'] = base[:-len(suf)]
                    par['resultado'] = suf[1:]
        if '_regenerado' in p:
            par['regenerado_de_ponto'] = p['_regenerado']
        linha['parametros'] = json.dumps(par, ensure_ascii=False) if par else None
    return linha


# ---------------------------------------------------------------- atributos livres

PREFIXO_ATRIBUTO = 'attr_'


def nome_coluna_atributo(chave, usados):
    """Chave livre do Web ('Água potável') -> coluna GPKG estável ('attr_agua_potavel')."""
    import re
    import unicodedata
    s = unicodedata.normalize('NFKD', str(chave)).encode('ascii', 'ignore').decode('ascii').lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_') or 'campo'
    base = (PREFIXO_ATRIBUTO + s)[:60]
    nome, i = base, 2
    while nome in usados:
        nome = '{}_{}'.format(base[:56], i)
        i += 1
    usados.add(nome)
    return nome


def criar_colunas_atributos(ds, doc, log=None):
    """
    Cria nas tabelas por tipo uma coluna texto por chave livre de properties.attributes
    (união das chaves do tipo no arquivo), com o nome original como alias (alternative name
    do GPKG, que o QGIS lê como alias do campo). Devolve {tipo: {chave: coluna}}.
    """
    chaves = {}
    for _mapa, tipo, ft in leitor.iterar_feicoes(doc, logging.getLogger('silencioso')):
        attrs = (ft.get('properties') or {}).get('attributes')
        if isinstance(attrs, dict):
            lst = chaves.setdefault(tipo, [])
            for k in attrs:
                if str(k) not in lst:
                    lst.append(str(k))
    out = {}
    for tipo, lst in chaves.items():
        lyr = ds.GetLayerByName(schema.TIPOS[tipo]['tabela'])
        defn = lyr.GetLayerDefn()
        usados = {defn.GetFieldDefn(i).GetName().lower() for i in range(defn.GetFieldCount())}
        usados |= {'fid', 'geom'}
        cols = {}
        for k in lst:
            col = nome_coluna_atributo(k, usados)
            fd = ogr.FieldDefn(col, ogr.OFTString)
            try:
                fd.SetAlternativeName(k)
            except AttributeError:  # GDAL < 3.2
                pass
            lyr.CreateField(fd)
            cols[k] = col
        out[tipo] = cols
    return out


# ---------------------------------------------------------------- gravação

def _novo_registro(lyr, valores, tipos):
    defn = lyr.GetLayerDefn()
    feat = ogr.Feature(defn)
    for col, val in valores.items():
        idx = defn.GetFieldIndex(col)
        if idx >= 0:
            if schema.coluna_de_cor(col):
                val = schema.cor_canonica(val)  # como o formulário nativo a regrava (minúsculas)
            _set(feat, idx, tipos.get(col, 'str'), val)
    return feat


def importar(caminho_ebgeo, caminho_gpkg, log=None, sobrescrever=True, feedback=None):
    """
    Lê o .ebgeo e grava o calco em `caminho_gpkg`. Devolve um Relatorio.
    Levanta leitor.ErroEbgeo se o arquivo for recusado.
    `feedback`, opcional, é chamado com (fração 0..1) para progresso.
    """
    log = log or _log
    t0 = time.time()
    doc = leitor.abrir(caminho_ebgeo)
    return gravar_documento(doc, caminho_gpkg, log, sobrescrever, feedback, t0)


def gravar_documento(doc, caminho_gpkg, log=None, sobrescrever=True, feedback=None, t0=None):
    log = log or _log
    t0 = t0 or time.time()
    rel = Relatorio(caminho_gpkg)
    for a in doc.avisos:
        rel.avisos.append(a)
        log.warning(a)

    if os.path.exists(caminho_gpkg):
        if not sobrescrever:
            raise leitor.ErroEbgeo('O GeoPackage {} já existe.'.format(caminho_gpkg))
        try:
            os.remove(caminho_gpkg)
        except OSError as e:
            raise leitor.ErroEbgeo('Não foi possível substituir {} (está aberto no QGIS?): {}'.format(
                caminho_gpkg, e))

    data = doc.data
    gpkg.criar_calco(caminho_gpkg, list(schema.TIPOS), apoio=True)
    ds = ogr.Open(caminho_gpkg, 1)
    if ds is None:
        raise leitor.ErroEbgeo('Não foi possível abrir {} para escrita.'.format(caminho_gpkg))

    tipos_col = {t: {c[0]: c[1] for c in schema.campos(t)} for t in schema.TIPOS}
    # atributos livres viram colunas reais (união das chaves por tabela), com alias = chave original
    colunas_attr = criar_colunas_atributos(ds, doc, log)
    for tipo, mapa_cols in colunas_attr.items():
        for col in mapa_cols.values():
            tipos_col[tipo][col] = 'str'
    rel.colunas_atributos = colunas_attr
    tipos_apoio = {n: dict(cols) for n, cols in schema.TABELAS_APOIO.items()}
    renderizar = None
    guardadas = set()  # ids de images/ que alguma tabela guardou; o resto vai para ebgeo_imagem
    ordem = leitor.ordem_mapas(data)
    atual = leitor.mapa_atual(data)
    total_feicoes = sum(len(l) for m in data['maps'].values() for l in (m.get('features') or {}).values()) or 1
    feitas = 0

    ds.StartTransaction()
    try:
        # documento: o data.json original inteiro, inclusive o que está fora do recorte
        lyr = ds.GetLayerByName('ebgeo_documento')
        lyr.CreateFeature(_novo_registro(lyr, {
            'arquivo': doc.arquivo, 'sha256': doc.sha256, 'versao': doc.versao,
            'importado_em': datetime.datetime.now(datetime.timezone.utc),
            'data_json': doc.texto_json}, tipos_apoio['ebgeo_documento']))

        # ícones personalizados
        lyr = ds.GetLayerByName('ebgeo_icone')
        for ic in data.get('customIcons') or []:
            blob = doc.imagens.get(ic.get('id'))
            if blob:
                guardadas.add(ic.get('id'))
                mime, b64 = blob[1], base64.b64encode(blob[0]).decode('ascii')
            else:
                mime, b64 = _data_url(ic.get('thumbnail'))
                msg = 'ícone personalizado {} ({}) sem imagem no arquivo{}'.format(
                    ic.get('id'), ic.get('name'), '; usada a miniatura' if b64 else '')
                rel.avisos.append(msg)
                log.warning(msg)
            lyr.CreateFeature(_novo_registro(lyr, {
                'icone_id': ic.get('id'), 'nome': ic.get('name'), 'mime': mime, 'bitmap_b64': b64},
                tipos_apoio['ebgeo_icone']))

        notas = data.get('mapNotes') or {}
        for ordem_i, nome in enumerate(ordem):
            m = data['maps'][nome]
            nota = notas.get(nome) if isinstance(notas.get(nome), dict) else {}
            lyr = ds.GetLayerByName('ebgeo_mapa')
            lyr.CreateFeature(_novo_registro(lyr, {
                'nome': nome, 'ordem': ordem_i, 'base_layer': valor_coluna('str', m.get('baseLayer')),
                'notas_titulo': nota.get('title'), 'notas_descricao': nota.get('description'),
                'atual': nome == atual}, tipos_apoio['ebgeo_mapa']))
            rel.mapas += 1

            # camadas EBGeo
            camadas = leitor.camadas_do_mapa(data, nome)
            ids_camadas = {c.get('id') for c in camadas}
            baldes = leitor.normalizar_baldes(m.get('features'), nome, log)
            orfas = []
            for lista in baldes.values():
                for ft in lista:
                    lid = (ft.get('properties') or {}).get('layerId') or 'default'
                    if lid not in ids_camadas and lid not in orfas:
                        orfas.append(lid)
            for lid in orfas:
                msg = 'mapa "{}": camada {} usada por feições mas ausente de layers; criada visível'.format(nome, lid)
                rel.avisos.append(msg)
                log.warning(msg)
                camadas.append({'id': lid, 'name': lid, 'visible': True, 'locked': False, 'opacity': 1,
                                'order': max([c.get('order') or 0 for c in camadas]) + 1})
            lyr = ds.GetLayerByName('ebgeo_camada')
            for c in camadas:
                lyr.CreateFeature(_novo_registro(lyr, {
                    'mapa': nome, 'camada_id': c.get('id'), 'nome': c.get('name'),
                    'visivel': c.get('visible', True) is not False,
                    'bloqueada': bool(c.get('locked')),
                    'opacidade': valor_coluna('real', c.get('opacity', 1)),
                    'ordem': valor_coluna('int', c.get('order', 0))}, tipos_apoio['ebgeo_camada']))

            # grupos EBGeo e pertinência
            membros_por_id = {}
            lyr_g = ds.GetLayerByName('ebgeo_grupo')
            lyr_m = ds.GetLayerByName('ebgeo_grupo_membro')
            for gid, g in ((data.get('groups') or {}).get(nome) or {}).items():
                gid = g.get('id') or gid
                lyr_g.CreateFeature(_novo_registro(lyr_g, {
                    'mapa': nome, 'grupo_id': gid, 'nome': g.get('name'),
                    'visivel': g.get('visible', True) is not False, 'bloqueado': bool(g.get('locked'))},
                    tipos_apoio['ebgeo_grupo']))
                for ref in g.get('features') or []:
                    if not isinstance(ref, dict):
                        continue
                    lyr_m.CreateFeature(_novo_registro(lyr_m, {
                        'mapa': nome, 'grupo_id': gid, 'tipo': ref.get('type'), 'ebgeo_id': ref.get('id')},
                        tipos_apoio['ebgeo_grupo_membro']))
                    membros_por_id.setdefault(ref.get('id'), []).append(gid)

            # feições
            for tipo, lista in baldes.items():
                lyr = ds.GetLayerByName(schema.TIPOS[tipo]['tabela'])
                tem_bitmap = 'bitmap_b64' in tipos_col[tipo]
                for ft in lista:
                    feitas += 1
                    p = dict(ft.get('properties') or {})
                    if not p.get('id'):
                        p['id'] = str(uuid.uuid4())
                        msg = 'mapa "{}": {} sem properties.id; id novo {}'.format(nome, tipo, p['id'])
                        rel.avisos.append(msg)
                        log.warning(msg)
                    nota_g = []
                    geo = geometria_qgis(tipo, ft.get('geometry'), p, nota_g)
                    if geo is None:
                        motivo = 'geometria ausente, nula ou incompatível ({})'.format(
                            (ft.get('geometry') or {}).get('type'))
                        rel.descartadas.append((nome, tipo, p.get('id'), motivo))
                        log.warning('mapa "%s": %s %s descartada: %s', nome, tipo, p.get('id'), motivo)
                        continue
                    if nota_g:
                        log.info('mapa "%s": %s %s: %s', nome, tipo, p.get('id'), '; '.join(nota_g))

                    linha = linha_feicao(tipo, nome, p, membros_por_id.get(p.get('id')))
                    attrs = p.get('attributes')
                    if isinstance(attrs, dict):
                        for k, v in attrs.items():
                            col = colunas_attr.get(tipo, {}).get(str(k))
                            if col:
                                linha[col] = valor_coluna('str', v)
                    if 'geom_desenho' in linha:
                        linha['geom_desenho'] = _wkt(ft.get('geometry'))
                    if tem_bitmap:
                        blob = doc.imagens.get(p.get('id'))
                        if blob:
                            guardadas.add(p.get('id'))
                            linha['bitmap_b64'] = base64.b64encode(blob[0]).decode('ascii')
                            linha['bitmap_mime'] = blob[1]
                            if 'bitmap_largura_px' in tipos_col[tipo]:
                                # o tamanho natural do bitmap, com que o Web desenha a imagem
                                linha['bitmap_largura_px'] = leitor.largura_natural(blob[0], p)
                        elif tipo == 'image':
                            msg = 'mapa "{}": imagem {} ({}) sem bitmap no arquivo: perda'.format(
                                nome, p.get('id'), p.get('nome'))
                            rel.avisos.append(msg)
                            log.warning(msg)
                        if tipo in TIPOS_SIMBOLO and not blob:
                            log.info('mapa "%s": %s %s sem bitmap no arquivo (normal: redesenhado pelo motor)',
                                     nome, tipo, p.get('id'))
                    if tipo in TIPOS_SIMBOLO:
                        if rel.motor_simbolos is None:
                            renderizar = _carregar_motor(rel, log)
                        if renderizar and _aplicar_render(renderizar, tipo, linha, log):
                            rel.svg_renderizados += 1

                    feat = _novo_registro(lyr, linha, tipos_col[tipo])
                    feat.SetGeometry(ogr.CreateGeometryFromJson(json.dumps(geo)))
                    lyr.CreateFeature(feat)
                    rel.contagem[tipo] = rel.contagem.get(tipo, 0) + 1

                    guardadas.update(_gravar_fotos(ds, doc, p, tipos_apoio['ebgeo_foto'], rel, log, nome))
                    if feedback and feitas % 50 == 0:
                        feedback(min(1.0, feitas / total_feicoes))

        # imagens sem dono no 2D (3D, 360, slides, feição descartada): guardadas para o exportador
        lyr = ds.GetLayerByName('ebgeo_imagem')
        for ident, (b, mime) in doc.imagens.items():
            if ident not in guardadas:
                lyr.CreateFeature(_novo_registro(lyr, {
                    'imagem_id': ident, 'mime': mime, 'bitmap_b64': base64.b64encode(b).decode('ascii')},
                    tipos_apoio['ebgeo_imagem']))
        ds.CommitTransaction()
    except Exception:
        try:
            ds.RollbackTransaction()
        except Exception:
            pass
        raise
    finally:
        ds.FlushCache()
        ds = None

    rel.segundos = time.time() - t0
    log.info('importadas %d feições em %d mapas (%d descartadas) em %.1f s',
             rel.total(), rel.mapas, len(rel.descartadas), rel.segundos)
    return rel


def _gravar_fotos(ds, doc, p, tipos, rel, log, mapa):
    """Grava as fotos anexas da feição em ebgeo_foto. Devolve os ids de images/ que usou."""
    usados = set()
    fotos = p.get('images')
    if not isinstance(fotos, list) or not fotos:
        return usados
    lyr = ds.GetLayerByName('ebgeo_foto')
    for f in fotos:
        if isinstance(f, str):
            f = {'id': f}
        if not isinstance(f, dict):
            continue
        mime, b64 = _data_url(f.get('data'))
        if b64 is None and f.get('id') in doc.imagens:
            b, mime = doc.imagens[f['id']]
            b64 = base64.b64encode(b).decode('ascii')
            usados.add(f['id'])
        _mt, mini = _data_url(f.get('thumbnail'))
        if b64 is None:
            msg = 'mapa "{}": foto {} ({}) da feição {} sem bytes no arquivo: perda'.format(
                mapa, f.get('id'), f.get('name'), p.get('id'))
            rel.avisos.append(msg)
            log.warning(msg)
        lyr.CreateFeature(_novo_registro(lyr, {
            'ebgeo_id': p.get('id'), 'foto_id': f.get('id'), 'nome': f.get('name'),
            'mime': mime or f.get('type'), 'bitmap_b64': b64, 'miniatura_b64': mini}, tipos))
    return usados


# ---------------------------------------------------------------- releitura (conferência)

def contar_gpkg(caminho_gpkg):
    """{tipo: n} RELENDO o GeoPackage gravado (a prova; o Relatorio é só eco)."""
    ds = ogr.Open(caminho_gpkg)
    try:
        out = {}
        for tipo, d in schema.TIPOS.items():
            lyr = ds.GetLayerByName(d['tabela'])
            if lyr is not None:
                n = lyr.GetFeatureCount()
                if n:
                    out[tipo] = n
        return out
    finally:
        ds = None
