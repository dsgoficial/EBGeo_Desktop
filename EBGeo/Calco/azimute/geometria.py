# -*- coding: utf-8 -*-
"""
Azimute e Distância: a geometria do EBGeo Web em Python puro (sem Qt), porte linha a linha de
azimuth_distance_tool/azimuth_distance_geometry.js e azimuth_distance_constants.js.

- As pernas são digitadas num dos três nortes (NM, NQ, NV) e viram azimute VERDADEIRO pela
  mesma convenção do Web: NV = NM + declinação (leste positiva) e NV = NQ + convergência
  (norte de quadrícula a leste do verdadeiro positiva).
- Cada perna anda no círculo máximo, como o turf.destination do Web (esfera de raio
  6.371.008,8 m), e as arestas da rota e da área ganham vértices no círculo máximo a cada
  1 km no máximo (densifyGreatCircle, haversine de raio 6.371.000 m), para o QGIS desenhar a
  mesma linha que o Web.
- A construção fica gravada com as chaves do Web (azimuthDistanceData), para ida e volta com o
  arquivo .ebgeo.

testes/test_azimute.py confere os vértices contra o código do Web rodado em node.
"""
import math

from ..motor import declinacao as _decl

# ---------------------------------------------------------------- constantes do Web

MILS_PER_CIRCLE = 6400
DEGREES_PER_CIRCLE = 360
MIL_TO_DEG = DEGREES_PER_CIRCLE / MILS_PER_CIRCLE
DEG_TO_MIL = MILS_PER_CIRCLE / DEGREES_PER_CIRCLE

GRAUS = 'degrees'
MILESIMOS = 'mils'
METROS = 'meters'
QUILOMETROS = 'kilometers'

NM = 'magnetic'
NQ = 'grid'
NV = 'true'

PONTO = 'point'
ROTA = 'route'
AREA = 'area'

ROTULO_MODO = {PONTO: 'Ponto', ROTA: 'Rota', AREA: 'Área'}
DESCRICAO_MODO = {PONTO: 'Observação, alvo, referência', ROTA: 'Itinerário, patrulha, marcha',
                  AREA: 'Setor, zona, perímetro'}
ROTULO_NORTE = {NM: 'Norte Magnético (NM)', NQ: 'Norte de Quadrícula (NQ)', NV: 'Norte Verdadeiro (NV)'}

# Rosa dos ventos do painel (COMPASS_PRESETS)
PRESETS = [('N', 0), ('NE', 45), ('E', 90), ('SE', 135), ('S', 180), ('SO', 225), ('O', 270), ('NO', 315)]

COR = '#16a34a'  # DEFAULT_PROPERTIES.strokeColor / fillColor
DECLINACAO_INICIAL = -21.5  # o painel do Web nasce com ela, antes do ponto de referência
MIN_PERNAS_AREA = 2
MAX_DECLINACAO = 45.0

AZIMUTE_PASSO_MAXIMO_M = 1000
AZIMUTE_VERTICES_POR_ARESTA = 64

RAIO_TURF_M = 6371008.8      # @turf/helpers earthRadius
RAIO_HAVERSINE_M = 6371000   # utilities/geometry-utils.js EARTH_RADIUS_METERS
_DEG_TO_RAD = math.pi / 180
_RAD_TO_DEG = 180 / math.pi


# ---------------------------------------------------------------- números

def numero(v):
    """Number(v) do JS para o valor de uma perna: None quando vazio ou não numérico."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
    else:
        s = str(v).strip().replace(',', '.')
        if not s:
            return None
        try:
            f = float(s)
        except ValueError:
            return None
    return f if math.isfinite(f) else None


def _vazio(v):
    return v is None or (isinstance(v, str) and v.strip() == '')


def limpo(v):
    """Número para o JSON: inteiro quando é inteiro (45 em vez de 45.0, como o Web grava)."""
    if isinstance(v, float) and math.isfinite(v) and v.is_integer():
        return int(v)
    return v


# ---------------------------------------------------------------- unidades

def azimute_em_graus(valor, unidade):
    return valor * MIL_TO_DEG if unidade == MILESIMOS else valor


def distancia_em_metros(valor, unidade):
    return valor * 1000 if unidade == QUILOMETROS else valor


def converter_azimute(valor, de, para):
    """convertAzimuth (o toggle de unidade do painel): milésimos inteiros, graus com 1 casa."""
    if de == para:
        return valor
    if de == GRAUS and para == MILESIMOS:
        return _decl.js_round(valor * DEG_TO_MIL)
    if de == MILESIMOS and para == GRAUS:
        return float(_decl.js_to_fixed(valor * MIL_TO_DEG, 1))
    return valor


def converter_distancia(valor, de, para):
    if de == para:
        return valor
    if de == METROS and para == QUILOMETROS:
        return float(_decl.js_to_fixed(valor / 1000, 3))
    if de == QUILOMETROS and para == METROS:
        return _decl.js_round(valor * 1000)
    return valor


# ---------------------------------------------------------------- nortes

def normalizar_azimute(a):
    """normalizeAzimuth: [0, 360), idempotente e sem -0."""
    if a is None or not math.isfinite(a):
        return float('nan')
    r = math.fmod(a, DEGREES_PER_CIRCLE)
    if r < 0:
        r += DEGREES_PER_CIRCLE
    if r >= DEGREES_PER_CIRCLE:
        r -= DEGREES_PER_CIRCLE
    if r == 0:
        return 0.0
    return r


def _finito(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def aplicar_declinacao(azimute, declinacao, norte, convergencia=0.0):
    """applyDeclination: o azimute digitado no seu norte vira azimute verdadeiro."""
    if norte == NV:
        return normalizar_azimute(azimute)
    if norte == NQ:
        return normalizar_azimute(azimute + (convergencia if _finito(convergencia) else 0))
    return normalizar_azimute(azimute + (declinacao if _finito(declinacao) else 0))


def convergencia_no_ponto(lat, lon):
    return _decl.calcular_convergencia(lat, lon)


def resolver_convergencia(polar):
    """resolveConvergence: a gravada, ou a do ponto de referência (construção antiga)."""
    polar = polar or {}
    c = polar.get('meridianConvergence')
    if _finito(c):
        return float(c)
    p = polar.get('referencePoint')
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        return 0.0
    v = convergencia_no_ponto(p[1], p[0])
    return float(v) if v is not None else 0.0


def declinacao_modelo(lat, lon):
    r = _decl.calcular_declinacao(lat, lon)
    d = r.get('declination') if r else None
    return float(d) if _finito(d) else None


def declinacao_exibida(polar, modelo=declinacao_modelo):
    """
    displayDeclination: a construção digitada em NM (ou feita depois que o NQ existiu, que grava a
    convergência) guarda a declinação com que foi feita; a ANTIGA em NV guarda um valor que o
    painel nunca deixou mudar, e a leitura em NM usa a do modelo no ponto.
    """
    polar = polar or {}
    guardada = numero(polar.get('magneticDeclination'))
    if polar.get('northReference') == NM or _finito(polar.get('meridianConvergence')):
        return guardada
    p = polar.get('referencePoint')
    if not isinstance(p, (list, tuple)) or len(p) < 2 or modelo is None:
        return None
    v = modelo(p[1], p[0])
    return float(v) if _finito(v) else None


def tres_nortes(verdadeiro, declinacao=None, convergencia=None):
    """threeNorths: {'nv', 'nq', 'nm'} em graus; nm None sem declinação."""
    return {
        'nv': normalizar_azimute(verdadeiro),
        'nq': normalizar_azimute(verdadeiro - (convergencia if _finito(convergencia) else 0)),
        'nm': normalizar_azimute(verdadeiro - declinacao) if _finito(declinacao) else None,
    }


def pernas_tres_nortes(pernas, unidade_angular, norte, declinacao, convergencia):
    """legsInThreeNorths: cada perna nos três nortes, a partir do azimute DIGITADO no seu norte."""
    out = []
    for perna in pernas or []:
        az = numero((perna or {}).get('azimuth'))
        if az is None:
            out.append(None)
            continue
        verdadeiro = aplicar_declinacao(azimute_em_graus(az, unidade_angular),
                                        declinacao if _finito(declinacao) else 0, norte, convergencia)
        out.append(tres_nortes(verdadeiro, declinacao, convergencia))
    return out


# ---------------------------------------------------------------- textos (vírgula decimal)

def texto_angulo(graus, unidade=GRAUS):
    """formatAngleReading: '23,4°' ou '416₥', '-' quando desconhecido."""
    if not _finito(graus):
        return '-'
    if unidade == MILESIMOS:
        return '{}₥'.format(int(_decl.js_round(graus * DEG_TO_MIL)) % MILS_PER_CIRCLE)
    decimo = _decl.js_round(graus * 10) / 10
    v = decimo - DEGREES_PER_CIRCLE if decimo >= DEGREES_PER_CIRCLE else decimo
    return '{}°'.format(_decl.js_to_fixed(v, 1).replace('.', ','))


def texto_azimute_tabela(graus, unidade=GRAUS):
    """legAzimuthText da aba Azimutes (duas casas); em milésimos, o inteiro do painel."""
    if not _finito(graus):
        return '-'
    if unidade == MILESIMOS:
        return texto_angulo(graus, MILESIMOS)
    return '{}°'.format(_decl.js_to_fixed(graus, 2).replace('.', ','))


def texto_correcao(graus):
    """formatCorrection: '+0,8°', '-21,6°'."""
    if not _finito(graus):
        return '-'
    decimo = _decl.js_round(graus * 10) / 10
    sinal = '+' if decimo > 0 else ''
    return '{}{}°'.format(sinal, _decl.js_to_fixed(0 if decimo == 0 else decimo, 1).replace('.', ','))


def texto_numero(v):
    """decimalComma(v) sem casas fixas: o número como o JS o escreve, com vírgula."""
    if not _finito(v):
        return ''
    return _decl.js_num(v).replace('.', ',')


def texto_distancia(metros):
    """distanceText da aba Azimutes: '800,0 m', '1,40 km'."""
    if not _finito(metros):
        return '-'
    if metros >= 1000:
        return '{} km'.format(_decl.js_to_fixed(metros / 1000, 2).replace('.', ','))
    return '{} m'.format(_decl.js_to_fixed(metros, 1).replace('.', ','))


def distancia_total(pernas):
    """calculateTotalDistance: soma das distâncias como digitadas."""
    total = 0.0
    for perna in pernas or []:
        d = numero((perna or {}).get('distance'))
        if d:
            total += d
    return total


def texto_total(total, unidade):
    """formatTotalDistance: '1,50 km' ou '800 m'."""
    if unidade == QUILOMETROS:
        return '{} km'.format(_decl.js_to_fixed(total, 2).replace('.', ','))
    if total >= 1000:
        return '{} km'.format(_decl.js_to_fixed(total / 1000, 2).replace('.', ','))
    return '{} m'.format(texto_numero(total))


def zona_utm(lon):
    return int(round((_decl.meridiano_central_utm(lon) + 183) / 6))


# ---------------------------------------------------------------- validação

def validar_perna(perna, unidade_angular):
    """validateLeg: lista de erros (vazia quando a perna está boa)."""
    erros = []
    az = perna.get('azimuth')
    if not _vazio(az):
        n = numero(az)
        maximo = MILS_PER_CIRCLE if unidade_angular == MILESIMOS else DEGREES_PER_CIRCLE
        if n is None or n < 0 or n > maximo:
            erros.append('Azimute deve estar entre 0 e {}'.format(maximo))
    d = perna.get('distance')
    if not _vazio(d):
        n = numero(d)
        if n is None or n < 0:
            erros.append('Distância deve ser maior ou igual a 0')
    return erros


def perna_completa(perna):
    """A perna que o Web usa: azimute presente e distância verdadeira (diferente de zero)."""
    if _vazio(perna.get('azimuth')) or numero(perna.get('azimuth')) is None:
        return False
    return bool(numero(perna.get('distance')))


def pode_criar(ponto, pernas, modo):
    """canCreateFeature: (pode, motivo)."""
    if not ponto or len(ponto) < 2:
        return False, 'Defina o ponto de referência'
    completas = [p for p in pernas or [] if perna_completa(p)]
    if not completas:
        return False, 'Adicione pelo menos uma perna completa'
    if modo == AREA and len(completas) < MIN_PERNAS_AREA:
        return False, 'Área requer pelo menos 2 pernas'
    return True, None


# ---------------------------------------------------------------- geodésia (turf e geometry-utils)

def _graus_para_rad(g):
    return math.fmod(g, 360) * math.pi / 180


def _rad_para_graus(r):
    return math.fmod(r, 2 * math.pi) * 180 / math.pi


def destino(ponto, distancia_m, rumo):
    """turf.destination(ponto, distância em km, rumo, {units: 'kilometers'}) do Web."""
    lon1 = _graus_para_rad(ponto[0])
    lat1 = _graus_para_rad(ponto[1])
    b = _graus_para_rad(rumo)
    r = (distancia_m / 1000) / (RAIO_TURF_M / 1e3)
    lat2 = math.asin(math.sin(lat1) * math.cos(r) + math.cos(lat1) * math.sin(r) * math.cos(b))
    lon2 = lon1 + math.atan2(math.sin(b) * math.sin(r) * math.cos(lat1),
                             math.cos(r) - math.sin(lat1) * math.sin(lat2))
    return [_rad_para_graus(lon2), _rad_para_graus(lat2)]


def distancia_haversine(p1, p2):
    """calculateDistance de utilities/geometry-utils.js (raio 6.371.000 m)."""
    lat1 = p1[1] * _DEG_TO_RAD
    lat2 = p2[1] * _DEG_TO_RAD
    dlat = (p2[1] - p1[1]) * _DEG_TO_RAD
    dlon = (p2[0] - p1[0]) * _DEG_TO_RAD
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
        math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return RAIO_HAVERSINE_M * c


def densificar_circulo_maximo(coords, passo_m, max_por_aresta=512):
    """densifyGreatCircle: vértices no círculo máximo, no máximo a cada passo_m."""
    if not isinstance(coords, list) or len(coords) < 2 or not passo_m > 0:
        return coords

    def vetor(p):
        la = p[1] * _DEG_TO_RAD
        lo = p[0] * _DEG_TO_RAD
        return [math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)]

    out = [coords[0]]
    for i in range(1, len(coords)):
        a = coords[i - 1]
        b = coords[i]
        angulo = distancia_haversine(a, b) / RAIO_HAVERSINE_M
        pedacos = min(max_por_aresta + 1, math.ceil((angulo * RAIO_HAVERSINE_M) / passo_m))
        if pedacos > 1 and math.sin(angulo) > 1e-12:
            va = vetor(a)
            vb = vetor(b)
            for k in range(1, pedacos):
                f = k / pedacos
                wa = math.sin((1 - f) * angulo) / math.sin(angulo)
                wb = math.sin(f * angulo) / math.sin(angulo)
                x = wa * va[0] + wb * vb[0]
                y = wa * va[1] + wb * vb[1]
                z = wa * va[2] + wb * vb[2]
                lat = math.atan2(z, math.hypot(x, y)) * _RAD_TO_DEG
                lon = math.atan2(y, x) * _RAD_TO_DEG
                anterior = out[-1][0]
                out.append([anterior + (math.fmod((lon - anterior) + 540, 360) - 180), lat])
        out.append(b)
    return out


# ---------------------------------------------------------------- construção

def calcular_vertices(ponto, pernas, declinacao, norte, unidade_angular=GRAUS, unidade_distancia=METROS,
                      convergencia=0.0):
    """calculateWaypoints: [ponto, fim da perna 1, ...] em [lon, lat]; perna incompleta é pulada."""
    if not ponto or len(ponto) < 2:
        return []
    vertices = [list(ponto)]
    atual = list(ponto)
    for perna in pernas or []:
        if not perna_completa(perna):
            continue
        az = azimute_em_graus(numero(perna['azimuth']), unidade_angular)
        az = aplicar_declinacao(az, declinacao, norte, convergencia)
        dist = distancia_em_metros(numero(perna['distance']), unidade_distancia)
        atual = destino(atual, dist, az)
        vertices.append(atual)
    return vertices


def gerar_geometria(vertices, modo):
    """generateGeometry: GeoJSON da rota (LineString) ou da área (Polygon); None no modo ponto."""
    if not vertices:
        return None
    if modo == ROTA:
        if len(vertices) < 2:
            return None
        return {'type': 'LineString',
                'coordinates': densificar_circulo_maximo(vertices, AZIMUTE_PASSO_MAXIMO_M, AZIMUTE_VERTICES_POR_ARESTA)}
    if modo == AREA:
        if len(vertices) < 3:
            return None
        anel = densificar_circulo_maximo(list(vertices) + [vertices[0]], AZIMUTE_PASSO_MAXIMO_M,
                                         AZIMUTE_VERTICES_POR_ARESTA)
        return {'type': 'Polygon', 'coordinates': [anel]}
    return None


def pernas_guardadas(pernas):
    """As pernas como o Web as grava (azimuth, distance, observation), com o valor digitado."""
    out = []
    for p in pernas or []:
        az = p.get('azimuth')
        d = p.get('distance')
        out.append({'azimuth': '' if _vazio(az) else limpo(numero(az) if numero(az) is not None else az),
                    'distance': '' if _vazio(d) else limpo(numero(d) if numero(d) is not None else d),
                    'observation': p.get('observation') or ''})
    return out


def dados_polares(estado):
    """polarData do Web (properties.azimuthDistanceData), sem os vértices."""
    ponto = estado.get('referencePoint')
    return {
        'referencePoint': [ponto[0], ponto[1]] if ponto else None,
        'outputMode': estado.get('outputMode', ROTA),
        'angularUnit': estado.get('angularUnit', GRAUS),
        'distanceUnit': estado.get('distanceUnit', METROS),
        'northReference': estado.get('northReference', NM),
        'magneticDeclination': limpo(estado.get('magneticDeclination', 0)),
        'meridianConvergence': limpo(resolver_convergencia(estado)),
        'legs': pernas_guardadas(estado.get('legs')),
    }


def vertices_da_construcao(polar):
    """Os vértices de uma construção gravada (o _recalculateGeometry do Web)."""
    polar = polar or {}
    return calcular_vertices(
        polar.get('referencePoint'), polar.get('legs') or [],
        numero(polar.get('magneticDeclination')) or 0, polar.get('northReference'),
        polar.get('angularUnit') or GRAUS, polar.get('distanceUnit') or METROS,
        resolver_convergencia(polar))


def propriedades_web(estado, nome, agora_ms, zoom=None):
    """
    As properties que o Web grava para a construção (generateFeature / generatePointFeatures):
    uma por feição; no modo ponto, uma por vértice. Devolve (lista de (geometria GeoJSON,
    properties)), na ordem dos vértices.
    """
    polar = dados_polares(estado)
    vertices = vertices_da_construcao(polar)
    modo = polar['outputMode']
    obs = [p['observation'] for p in polar['legs']]
    comum = {'layerId': 'default', 'featureType': 'azimuth_distance', 'descricao': '', 'visivel': True,
             'bloqueado': False, 'createdAt': agora_ms, 'updatedAt': agora_ms}
    if modo == PONTO:
        saida = []
        for i, v in enumerate(vertices):
            p = dict(comum)
            nome_i = (obs[i - 1] if i > 0 and i - 1 < len(obs) else '') or nome(i)
            p.update({'source': 'point', 'nome': nome_i, 'fillColor': COR, 'size': 10, 'opacity': 1,
                      'sizeCreatedAtZoom': zoom if zoom is not None else 0, 'calculatedSize': 10,
                      'labelCreatedAtZoom': zoom if zoom is not None else 0, 'labelCalculatedSize': 14,
                      'azimuthDistanceData': dict({'waypointIndex': i, 'isReferencePoint': i == 0}, **polar)})
            saida.append(({'type': 'Point', 'coordinates': v}, p))
        return saida
    geo = gerar_geometria(vertices, modo)
    if geo is None:
        return []
    p = dict(comum)
    p['nome'] = nome(0)
    if modo == ROTA:
        p.update({'source': 'line', 'lineColor': COR, 'lineWidth': 5, 'opacity': 0.7, 'lineStyle': 'solid',
                  'measure': False, 'profile': False, 'profileData': None})
    else:
        p.update({'source': 'polygon', 'fillColor': COR, 'lineColor': COR, 'lineWidth': 2, 'opacity': 0.5,
                  'lineStyle': 'solid', 'measure': False, 'hatchEnabled': False, 'hatchType': 'none',
                  'hatchColor': '#000000', 'hatchSpacing': 8, 'hatchLineWidth': 2})
    p.update({'baseCoordinates': vertices, 'observations': obs, 'azimuthDistanceData': polar})
    return [(geo, p)]


def chave_conjunto(polar):
    """O que identifica os pontos de UMA construção no modo ponto (o Web não grava id dela)."""
    import json
    polar = dict(polar or {})
    polar.pop('waypointIndex', None)
    polar.pop('isReferencePoint', None)
    return json.dumps(polar, sort_keys=True)
