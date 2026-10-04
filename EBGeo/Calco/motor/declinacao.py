# -*- coding: utf-8 -*-
"""
Declinação magnética do calco, em Python puro (sem Qt):

- gerar_svg(declinacao, convergencia, cor): o diagrama dos três nortes, porte linha a linha de
  declination_tool/declination_svg_generator.js do EBGeo Web, com a mesma escrita de números
  do JavaScript, para o SVG sair igual byte a byte (testes/test_motor.py compara);
- o SVG vai para o QGIS como o Web o escreve: o QSvgRenderer do Qt 6.8 desenha o <marker> das
  pontas e o currentColor (medido: 537 pixels de tinta na ponta NM com o marcador, 246 sem);
- calcular(lat, lon, data): declinação, inclinação e intensidade pelo WMM2025 (coeficientes em
  WMM2025.COF, da NOAA, domínio público), porte do pacote npm geomagnetism que o Web usa,
  e a convergência meridiana UTM de utilities/geomagnetic/meridian_convergence.js.
"""
import datetime
import math
import os
from decimal import Decimal, ROUND_HALF_UP

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_COF = os.path.join(PASTA, 'WMM2025.COF')

# ---------------------------------------------------------------------------------------------
# Números como o JavaScript os escreve
# ---------------------------------------------------------------------------------------------


def js_num(valor):
    """Number.prototype.toString do ECMAScript (o que `${x}` produz num template)."""
    v = float(valor)
    if v != v:
        return 'NaN'
    if v in (float('inf'), float('-inf')):
        return 'Infinity' if v > 0 else '-Infinity'
    if v == 0:
        return '0'
    sinal = '-' if v < 0 else ''
    # repr dá os dígitos mínimos que reconstroem o double, o mesmo critério do ECMAScript.
    _, digitos, expoente = Decimal(repr(abs(v))).as_tuple()
    s = ''.join(map(str, digitos)).rstrip('0') or '0'
    k = len(s)
    n = expoente + len(digitos)
    if k <= n <= 21:
        texto = s + '0' * (n - k)
    elif 0 < n <= 21:
        texto = s[:n] + '.' + s[n:]
    elif -6 < n <= 0:
        texto = '0.' + '0' * (-n) + s
    else:
        e = n - 1
        texto = s[0] + ('.' + s[1:] if k > 1 else '') + 'e' + ('+' if e >= 0 else '-') + str(abs(e))
    return sinal + texto


def js_to_fixed(valor, casas):
    """Number.prototype.toFixed: valor binário exato, empate para o maior n."""
    d = Decimal(float(valor))
    q = Decimal(1).scaleb(-casas)
    r = abs(d).quantize(q, rounding=ROUND_HALF_UP)
    texto = format(r, 'f')
    return ('-' + texto) if d < 0 and r != 0 else texto


def js_round(valor):
    """Math.round: metade sobe em direção a +infinito."""
    return math.floor(valor + 0.5)


def formatar_graus(graus, longo=False):
    """formatSignedDegrees de utilities/angle-format.js."""
    valor = 0 if graus is None else graus
    magnitude = js_to_fixed(abs(valor), 1).replace('.', ',')
    leste, oeste = ('Leste', 'Oeste') if longo else ('E', 'W')
    return '{}° {}'.format(magnitude, leste if valor >= 0 else oeste)


# ---------------------------------------------------------------------------------------------
# Diagrama dos três nortes (declination_svg_generator.js)
# ---------------------------------------------------------------------------------------------

SVG_WIDTH = 400
SVG_HEIGHT = 500
ORIGIN_X = SVG_WIDTH / 2
ORIGIN_Y = 380
ARROW_LENGTH = 300
COR_PADRAO = '#0077CC'
ARROW_HEAD_SIZE = 12
BASE_LINE_HALF = 80
ARC_RADIUS_CONV = 48
ARC_RADIUS_DECL = 80
LABEL_SEPARATION_DEG = 8
LABEL_NUDGE = 18
TAMANHO_PADRAO = 0.6  # DEFAULT_PROPERTIES.size da ferramenta do Web


def _hex6(cor):
    import re
    return isinstance(cor, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', cor) is not None


def _ponta(angulo):
    a = (angulo * math.pi) / 180
    sin_a = math.sin(a)
    cos_a = math.cos(a)
    return {'x': ORIGIN_X + sin_a * ARROW_LENGTH, 'y': ORIGIN_Y - cos_a * ARROW_LENGTH,
            'sinA': sin_a, 'cosA': cos_a}


def _linhas_base():
    y = ORIGIN_Y
    return ('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="currentColor" stroke-width="1.5" '
            'stroke-dasharray="6,3"/>').format(js_num(ORIGIN_X - BASE_LINE_HALF), js_num(y),
                                                js_num(ORIGIN_X + BASE_LINE_HALF), js_num(y))


def _seta(x2, y2):
    return ('<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="currentColor" stroke-width="2" '
            'marker-end="url(#arrowHead)"/>').format(js_num(ORIGIN_X), js_num(ORIGIN_Y), js_num(x2), js_num(y2))


def _arco(angulo, raio):
    if abs(angulo) < 0.1:
        return ''
    inicio = -math.pi / 2
    fim = inicio + (angulo * math.pi) / 180
    sx = ORIGIN_X + math.cos(inicio) * raio
    sy = ORIGIN_Y + math.sin(inicio) * raio
    ex = ORIGIN_X + math.cos(fim) * raio
    ey = ORIGIN_Y + math.sin(fim) * raio
    grande = 1 if abs(angulo) > 180 else 0
    sentido = 1 if angulo > 0 else 0
    return '<path d="M {} {} A {} {} 0 {} {} {} {}" fill="none" stroke="currentColor" stroke-width="1.5"/>'.format(
        js_num(sx), js_num(sy), js_num(raio), js_num(raio), grande, sentido, js_num(ex), js_num(ey))


def _rotulo(ponta, texto, dx=0):
    off = 22
    x = ponta['x'] + ponta['sinA'] * off + dx
    y = ponta['y'] - ponta['cosA'] * off + 8
    return ('<text x="{}" y="{}" font-family="Arial, sans-serif" font-size="22" font-weight="bold" '
            'fill="currentColor" text-anchor="middle">{}</text>').format(js_num(x), js_num(y), texto)


def _legenda(declinacao, convergencia):
    fs = 20
    x = 20
    return ('\n  <text x="{x}" y="22" font-family="Arial, sans-serif" font-size="{fs}" font-weight="bold" '
            'fill="currentColor">Conv. (NV-NQ): {c}</text>\n'
            '  <text x="{x}" y="46" font-family="Arial, sans-serif" font-size="{fs}" font-weight="bold" '
            'fill="currentColor">Decl. (NV-NM): {d}</text>').format(
        x=x, fs=fs, c=formatar_graus(convergencia), d=formatar_graus(declinacao))


def gerar_svg(declinacao, convergencia=0, cor=COR_PADRAO):
    """generateDeclinationSvg do Web: o mesmo texto, byte a byte."""
    cor_diagrama = cor if _hex6(cor) else COR_PADRAO
    nv = _ponta(0)
    nq = _ponta(convergencia)
    nm = _ponta(declinacao)
    nv_dx = 0
    nq_dx = 0
    if abs(convergencia) < LABEL_SEPARATION_DEG:
        leste = convergencia >= 0
        nv_dx = -LABEL_NUDGE if leste else LABEL_NUDGE
        nq_dx = LABEL_NUDGE if leste else -LABEL_NUDGE
    h = ARROW_HEAD_SIZE
    return ('<svg xmlns="http://www.w3.org/2000/svg" color="{cor}" width="{w}" height="{hh}" viewBox="0 0 {w} {hh}">\n'
            '  <defs>\n'
            '    <marker id="arrowHead" markerWidth="{h}" markerHeight="{h}" refX="{h2}" refY="{h2}" orient="auto-start-reverse">\n'
            '      <polygon points="0,0 {h},{h2} 0,{h}" fill="currentColor"/>\n'
            '    </marker>\n'
            '  </defs>\n'
            '  {base}\n  {a1}\n  {a2}\n  {a3}\n  {c1}\n  {c2}\n  {r1}\n  {r2}\n  {r3}\n  {leg}\n'
            '</svg>').format(
        cor=cor_diagrama, w=SVG_WIDTH, hh=SVG_HEIGHT, h=js_num(h), h2=js_num(h / 2),
        base=_linhas_base(), a1=_seta(nv['x'], nv['y']), a2=_seta(nq['x'], nq['y']), a3=_seta(nm['x'], nm['y']),
        c1=_arco(convergencia, ARC_RADIUS_CONV), c2=_arco(declinacao, ARC_RADIUS_DECL),
        r1=_rotulo(nv, 'NV', nv_dx), r2=_rotulo(nq, 'NQ', nq_dx), r3=_rotulo(nm, 'NM'),
        leg=_legenda(declinacao, convergencia))


def renderizar(declinacao, convergencia=0, cor=None):
    """Desenho pronto para o calco: svg (o mesmo do Web), tamanho e âncora em px lógicos."""
    svg_web = gerar_svg(declinacao, convergencia or 0, cor or COR_PADRAO)
    return {
        'svg': svg_web,
        'svgWeb': svg_web,
        # O Web recorta o PNG na tinta e devolve o deslocamento que mantém o CENTRO do quadro
        # 400 x 500 sobre a coordenada (cropPngToDrawing). Desenhar o quadro inteiro centrado
        # dá a mesma posição e a mesma escala, sem o recorte.
        'largura': SVG_WIDTH,
        'altura': SVG_HEIGHT,
        'ancoraX': 0,
        'ancoraY': 0,
        'valido': True,
    }


# ---------------------------------------------------------------------------------------------
# WMM2025 (porte do pacote npm geomagnetism 0.2.0, que o Web usa)
# ---------------------------------------------------------------------------------------------

WMM_EPOCA = 2025.0
WMM_EXPIRA = 2030.0

_modelo = None


def _ler_cof(caminho=ARQUIVO_COF):
    g = [0.0]
    h = [0.0]
    dg = [0.0]
    dh = [0.0]
    epoca = None
    n_max = 0
    with open(caminho, encoding='ascii') as f:
        for linha in f:
            v = linha.split()
            if len(v) == 3 and epoca is None:
                epoca = float(v[0])
            elif len(v) == 6:
                n, m = int(v[0]), int(v[1])
                if m <= n:
                    i = n * (n + 1) // 2 + m
                    for lista, valor in ((g, v[2]), (h, v[3]), (dg, v[4]), (dh, v[5])):
                        while len(lista) <= i:
                            lista.append(0.0)
                        lista[i] = float(valor)
                n_max = max(n_max, n)
    return {'epoca': epoca, 'n_max': n_max, 'g': g, 'h': h, 'dg': dg, 'dh': dh}


def _ano_decimal_geomagnetism(data):
    # Model.getTimedModel: (data - 1º de janeiro UTC) / (365 dias), mesmo em ano bissexto.
    if isinstance(data, datetime.datetime):
        dt = data if data.tzinfo else data.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = datetime.datetime(data.year, data.month, data.day, tzinfo=datetime.timezone.utc)
    inicio = datetime.datetime(dt.year, 1, 1, tzinfo=datetime.timezone.utc)
    return dt.year + (dt - inicio).total_seconds() / (3600 * 24 * 365)


def _pcup_low(x, n_max):
    pcup = {0: 1.0}
    dpcup = {0: 0.0}
    z = math.sqrt((1 - x) * (1 + x))
    for n in range(1, n_max + 1):
        for m in range(0, n + 1):
            i = n * (n + 1) // 2 + m
            if n == m:
                i1 = (n - 1) * n // 2 + m - 1
                pcup[i] = z * pcup[i1]
                dpcup[i] = z * dpcup[i1] + x * pcup[i1]
            elif n == 1 and m == 0:
                i1 = (n - 1) * n // 2 + m
                pcup[i] = x * pcup[i1]
                dpcup[i] = x * dpcup[i1] - z * pcup[i1]
            elif n > 1 and n != m:
                i1 = (n - 2) * (n - 1) // 2 + m
                i2 = (n - 1) * n // 2 + m
                if m > n - 2:
                    pcup[i] = x * pcup[i2]
                    dpcup[i] = x * dpcup[i2] - z * pcup[i2]
                else:
                    k = ((n - 1) * (n - 1) - m * m) / ((2 * n - 1) * (2 * n - 3))
                    pcup[i] = x * pcup[i2] - k * pcup[i1]
                    dpcup[i] = x * dpcup[i2] - z * pcup[i2] - k * dpcup[i1]
    norma = {0: 1.0}
    for n in range(1, n_max + 1):
        i = n * (n + 1) // 2
        i1 = (n - 1) * n // 2
        norma[i] = norma[i1] * (2 * n - 1) / n
        for m in range(1, n + 1):
            i = n * (n + 1) // 2 + m
            i1 = n * (n + 1) // 2 + m - 1
            norma[i] = norma[i1] * math.sqrt(((n - m + 1) * (2 if m == 1 else 1)) / (n + m))
    for n in range(1, n_max + 1):
        for m in range(0, n + 1):
            i = n * (n + 1) // 2 + m
            pcup[i] *= norma[i]
            dpcup[i] *= -norma[i]
    return pcup, dpcup


def campo_magnetico(lat, lon, altitude_km=0.0, data=None):
    """Elementos do campo pelo WMM2025: decl, incl (graus), f, h, x, y, z (nT)."""
    global _modelo
    if _modelo is None:
        _modelo = _ler_cof()
    mod = _modelo
    data = data or datetime.datetime.now(datetime.timezone.utc)
    dano = _ano_decimal_geomagnetism(data) - mod['epoca']
    n_max = mod['n_max']
    g = [mod['g'][i] + dano * mod['dg'][i] for i in range(len(mod['g']))]
    h = [mod['h'][i] + dano * mod['dh'][i] for i in range(len(mod['h']))]

    # Elipsoide WGS 84 e raio de referência do WMM (km).
    a, b, re_ = 6378.137, 6356.7523142, 6371.2
    epssq = 1 - (b * b) / (a * a)
    lat = lat or 0.0
    lon = lon or 0.0
    coslat = math.cos(math.radians(lat))
    sinlat = math.sin(math.radians(lat))
    rc = a / math.sqrt(1 - epssq * sinlat * sinlat)
    xp = (rc + altitude_km) * coslat
    zp = (rc * (1 - epssq) + altitude_km) * sinlat
    r = math.sqrt(xp * xp + zp * zp)
    phig = math.degrees(math.asin(zp / r))

    pcup, dpcup = _pcup_low(math.sin(math.radians(phig)), n_max)
    cos_l = math.cos(math.radians(lon))
    sin_l = math.sin(math.radians(lon))
    cos_m = [1.0, cos_l]
    sin_m = [0.0, sin_l]
    for m in range(2, n_max + 1):
        cos_m.append(cos_m[m - 1] * cos_l - sin_m[m - 1] * sin_l)
        sin_m.append(cos_m[m - 1] * sin_l + sin_m[m - 1] * cos_l)
    potencia = [(re_ / r) * (re_ / r)]
    for n in range(1, n_max + 1):
        potencia.append(potencia[n - 1] * (re_ / r))

    bx = by = bz = 0.0
    for n in range(1, n_max + 1):
        for m in range(0, n + 1):
            i = n * (n + 1) // 2 + m
            bz -= potencia[n] * (g[i] * cos_m[m] + h[i] * sin_m[m]) * (n + 1) * pcup[i]
            by += potencia[n] * (g[i] * sin_m[m] - h[i] * cos_m[m]) * m * pcup[i]
            bx -= potencia[n] * (g[i] * cos_m[m] + h[i] * sin_m[m]) * dpcup[i]
    cos_phi = math.cos(math.radians(phig))
    if abs(cos_phi) > 1e-10:
        by = by / cos_phi
    else:  # perto dos polos, como no geomagnetism
        by = 0.0
        q1 = 1.0
        ps = [1.0]
        sin_phi = math.sin(math.radians(phig))
        for n in range(1, n_max + 1):
            i = n * (n + 1) // 2 + 1
            q2 = q1 * (2 * n - 1) / n
            q3 = q2 * math.sqrt(2 * n / (n + 1))
            q1 = q2
            if n == 1:
                ps.append(ps[n - 1])
            else:
                k = ((n - 1) * (n - 1) - 1) / ((2 * n - 1) * (2 * n - 3))
                ps.append(sin_phi * ps[n - 1] - k * ps[n - 2])
            by += potencia[n] * (g[i] * sin_m[1] - h[i] * cos_m[1]) * ps[n] * q3

    psi = math.radians(phig - lat)
    gx = bx * math.cos(psi) - bz * math.sin(psi)
    gz = bx * math.sin(psi) + bz * math.cos(psi)
    gy = by
    hh = math.sqrt(gx * gx + gy * gy)
    return {'x': gx, 'y': gy, 'z': gz, 'h': hh, 'f': math.sqrt(hh * hh + gz * gz),
            'decl': math.degrees(math.atan2(gy, gx)), 'incl': math.degrees(math.atan2(gz, hh))}


def _arredondar(valor, casas):
    f = 10 ** casas
    return js_round(valor * f) / f


def validade_wmm(data=None):
    """checkWMMValidity do Web: aviso fora de 2025,0 a 2030,0 (ano civil local)."""
    data = data or datetime.date.today()
    inicio = datetime.date(data.year, 1, 1)
    fim = datetime.date(data.year + 1, 1, 1)
    d = data.date() if isinstance(data, datetime.datetime) else data
    ano = data.year + (d - inicio).days / (fim - inicio).days
    if ano < WMM_EPOCA:
        return False, 'Data anterior ao modelo WMM2025 (válido a partir de {})'.format(js_num(WMM_EPOCA))
    if ano >= WMM_EXPIRA:
        return False, 'Coeficientes WMM2025 expirados. Precisão da declinação degradada.'
    return True, None


def calcular_declinacao(lat, lon, altitude_km=0.0, data=None):
    """calculateMagneticDeclination do Web: declination e inclination com 2 casas, intensity com 1."""
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None
    data = data or datetime.datetime.now(datetime.timezone.utc)
    valido, aviso = validade_wmm(data)
    r = campo_magnetico(lat, lon, max(0.0, altitude_km), data)
    return {'declination': _arredondar(r['decl'], 2), 'inclination': _arredondar(r['incl'], 2),
            'intensity': _arredondar(r['f'], 1), 'warning': aviso}


# ---------------------------------------------------------------------------------------------
# Convergência meridiana (utilities/geomagnetic/meridian_convergence.js)
# ---------------------------------------------------------------------------------------------

_E_PRIME_SQ = 0.00673949674228


def meridiano_central_utm(lon):
    return (math.floor((lon + 180) / 6) + 1) * 6 - 183


def calcular_convergencia(lat, lon, lambda0=None):
    if lat is None or lon is None or not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None
    if lambda0 is None:
        lambda0 = meridiano_central_utm(lon)
    phi = math.radians(lat)
    dl = math.radians(lon - lambda0)
    cos2 = math.cos(phi) ** 2
    gama = dl * math.sin(phi) * (1 + (dl ** 2 / 3) * cos2 * (1 + 3 * _E_PRIME_SQ * cos2))
    r = js_round(math.degrees(gama) * 100) / 100
    return 0 if r == 0 else r


def calcular(lat, lon, data=None, altitude_km=0.0):
    """Os atributos que a ferramenta do Web grava na criação (sem o desenho)."""
    data = data or datetime.datetime.now(datetime.timezone.utc)
    w = calcular_declinacao(lat, lon, altitude_km, data)
    if w is None:
        return None
    dia = data.date() if isinstance(data, datetime.datetime) else data
    return {'declination': w['declination'], 'convergence': calcular_convergencia(lat, lon) or 0,
            'inclination': w['inclination'], 'intensity': w['intensity'],
            'calculationDate': dia.isoformat(), 'wmmWarning': w['warning']}
