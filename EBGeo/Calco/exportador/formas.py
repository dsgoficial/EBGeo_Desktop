# -*- coding: utf-8 -*-
"""
Formas paramétricas do Web (círculo, elipse, retângulo e setor) editadas no QGIS: se a geometria
editada ainda é a forma, os parâmetros que o Web edita (centro, raios, ângulo) são recalculados.

O Web desenha a forma a partir dos parâmetros e só a eles edita (as alças de centro e raio); a
geometria gravada é o desenho deles. No QGIS a forma é um polígono, e escalar ou girar a feição
inteira (as ferramentas nativas, que andam vértice a vértice com a mesma ordem) dá outro polígono
que ainda pode ser a mesma forma com outros parâmetros. Aqui:

1. os geradores do Web, portados com a esfera e a contagem de vértices de cada um
   (add_circle_geometry.js e add_sector_geometry.js por destinationPoint, R 6.371.000 m;
   add_ellipse_geometry.js pelo turf.ellipse 7.4 e add_rectangle_geometry.js pelo turf.destination,
   R 6.371.008,8 m);
2. o ajuste: a semelhança (escala, giro e translação) que leva o anel original ao editado, vértice
   a vértice, dá o ponto de partida (Procrustes), e Levenberg-Marquardt refina os parâmetros contra o
   anel editado, no plano azimutal equidistante local;
3. a prova: a forma regenerada pelos parâmetros, com o gerador do Web, fica a no máximo a
   tolerância do anel editado (Hausdorff). Senão, a geometria deixou de ser a forma, e o exportador
   a manda como desenhada, com o aviso.

Python puro (numpy, pyproj): sem QGIS.
"""
import math

import numpy as np

R_WEB = 6371000.0        # EARTH_RADIUS_METERS de geometry-utils.js (destinationPoint)
R_TURF = 6371008.8       # earthRadius do turf (destination, ellipse)
TIPOS = ('circle', 'ellipse', 'rectangle', 'sector')

# Tolerância (Hausdorff entre o anel editado e a forma regenerada): o maior entre um piso absoluto e
# uma fração do tamanho da forma (raio, semieixo maior, meia diagonal). Medida em 2026-10-05 nas 34
# formas da fixture 06 (testes/test_formas_editadas.py, TestAjuste): a forma do Web como veio fica a
# até 0,035 % do tamanho (0,08 m, o arredondamento a 6 casas); escalada em graus, como a ferramenta
# Escalar do QGIS na camada em EPSG:4326, a até 0,045 %; um vértice só puxado de 0,3 % do tamanho para
# fora, a 0,15 % ou mais. Girada em graus (a ferramenta Girar, na camada em EPSG:4326) a 15 a 24 graus
# de latitude, fica a 0,6 a 10 % do tamanho, porque o grau de longitude vale cos(lat) do de latitude:
# deixou de ser a forma, salvo perto do equador.
TOL_PISO_M = 0.5
TOL_FRACAO = 0.001


# ---------------------------------------------------------------- esfera

def _destino(lon, lat, dist_m, rumo_graus, raio):
    la1, lo1, b = math.radians(lat), math.radians(lon), math.radians(rumo_graus)
    d = dist_m / raio
    s = math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b)
    la2 = math.asin(max(-1.0, min(1.0, s)))
    lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * s)
    return math.degrees(lo2), math.degrees(la2)


def destination_point(centro, dist_m, rumo):
    """destinationPoint de geometry-utils.js (R 6.371.000 m, longitude no lado do centro)."""
    lon, lat = _destino(centro[0], centro[1], dist_m, rumo, R_WEB)
    return [centro[0] + (((lon - centro[0]) + 540) % 360) - 180, lat]


def turf_destination(centro, dist_m, rumo):
    """turf.destination (R 6.371.008,8 m)."""
    return list(_destino(centro[0], centro[1], dist_m, rumo, R_TURF))


def _round_js(x):
    return math.floor(x + 0.5)


# ---------------------------------------------------------------- geradores do Web

def gerar_circulo(centro, raio_m):
    """generateCircleGeometry: 64 passos a partir do leste, anti-horário, anel fechado exato."""
    pts = [destination_point(centro, raio_m, 90 - i * 360 / 64) for i in range(65)]
    pts[64] = pts[0]
    return pts


def gerar_setor(centro, raio_m, rumo, abertura):
    """generateSectorGeometry: centro, arco de rumo - abertura/2 a rumo + abertura/2, centro."""
    n = max(16, _round_js(64 * abertura / 360))
    ini, fim = rumo - abertura / 2, rumo + abertura / 2
    pts = [[centro[0], centro[1]]]
    pts += [destination_point(centro, raio_m, ini + i * (fim - ini) / n) for i in range(n + 1)]
    pts.append([centro[0], centro[1]])
    return pts


def gerar_elipse(centro, maior_km, menor_km, rumo):
    """generateEllipseGeometry: turf.ellipse 7.4 com angle = rumo - 90 e 64 passos."""
    angulo = -90 + (rumo - 90)
    passos = math.ceil(64 / 4)
    a, b = maior_km, menor_km
    c = b
    m = (a - b) / (math.pi / 2)
    A = (a + b) * math.pi / 4
    v, k = 0.5, passos
    w = x = 0.0
    quadrante = []
    for _ in range(passos):
        x += w
        if m == 0:
            w = A / k / c
        else:
            w = (-(m * x + c) + math.sqrt((m * x + c) ** 2 - 4 * (v * m) * -(A / k))) / (2 * (v * m))
        if x != 0:
            quadrante.append(x)
    par = [0.0] + quadrante + [math.pi / 2]
    par += [math.pi - q for q in reversed(quadrante)] + [math.pi]
    par += [math.pi + q for q in quadrante] + [3 * math.pi / 2]
    par += [2 * math.pi - q for q in reversed(quadrante)] + [0.0]
    pts = []
    for t in par:
        th = math.atan2(b * math.sin(t), a * math.cos(t))
        r = math.sqrt(a * a * b * b / ((a * math.sin(th)) ** 2 + (b * math.cos(th)) ** 2))
        pts.append(turf_destination(centro, r * 1000, angulo + math.degrees(th)))
    return pts


def _girar_transladar(x, y, centro, rumo):
    """rotateAndTranslate de add_rectangle_geometry.js."""
    d = math.sqrt(x * x + y * y)
    return turf_destination(centro, d, math.degrees(math.atan2(y, x)) + rumo)


def gerar_retangulo(centro, largura, altura, raio_borda, rumo):
    """generateRotatedRectangleGeometry (e generateRoundedRotatedRectangle com borderRadius > 0)."""
    hw, hh = largura / 2, altura / 2
    if raio_borda and raio_borda > 0:
        menor = min(largura, altura)
        r = min(menor * (raio_borda / 10) * 0.5, menor / 2)
        cantos = (((hw - r, hh - r), 0.0, math.pi / 2), ((-(hw - r), hh - r), math.pi / 2, math.pi),
                  ((-(hw - r), -(hh - r)), math.pi, 3 * math.pi / 2), ((hw - r, -(hh - r)), 3 * math.pi / 2, 2 * math.pi))
        locais = []
        for (cx, cy), a0, a1 in cantos:
            for i in range(9):
                ang = a0 + i / 8 * (a1 - a0)
                locais.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    else:
        locais = [(hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
    pts = [_girar_transladar(x, y, centro, rumo) for x, y in locais]
    pts.append(pts[0])
    return pts


def gerar(tipo, p):
    """O anel externo que o Web desenha para as propriedades p da forma."""
    c = p['center']
    if tipo == 'circle':
        return gerar_circulo(c, p['radius'])
    if tipo == 'sector':
        return gerar_setor(c, p['radius'], p.get('bearing') or 0, p['aperture'])
    if tipo == 'ellipse':
        return gerar_elipse(c, p['majorRadius'], p['minorRadius'], p.get('bearing') or 0)
    return gerar_retangulo(c, p['width'], p['height'], p.get('borderRadius') or 0, p.get('bearing') or 0)


# ---------------------------------------------------------------- plano local

class _Plano:
    """Azimutal equidistante esférico (R do turf) no ponto dado: x leste, y norte, em metros."""

    def __init__(self, lon, lat):
        from pyproj import Transformer
        crs = '+proj=aeqd +lat_0={} +lon_0={} +R={} +units=m +no_defs'.format(lat, lon, R_TURF)
        self.ida = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
        self.volta = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)

    def xy(self, pts):
        a = np.asarray(pts, dtype=float)
        x, y = self.ida.transform(a[:, 0], a[:, 1])
        return np.column_stack([x, y])

    def lonlat(self, x, y):
        lon, lat = self.volta.transform(x, y)
        return [float(lon), float(lat)]


def _hausdorff(a, b):
    """Hausdorff (m) entre dois anéis no plano, pelos segmentos (não só pelos vértices)."""
    def dist_pts_anel(p, anel):
        s0, s1 = anel[:-1], anel[1:]
        d = s1 - s0
        l2 = np.maximum((d ** 2).sum(1), 1e-18)
        out = np.empty(len(p))
        for i, q in enumerate(p):
            t = np.clip(((q - s0) * d).sum(1) / l2, 0, 1)
            proj = s0 + t[:, None] * d
            out[i] = np.sqrt(((proj - q) ** 2).sum(1)).min()
        return out.max()
    return max(dist_pts_anel(a, b), dist_pts_anel(b, a))


def _densificar(anel, passo):
    out = [anel[0]]
    for p, q in zip(anel[:-1], anel[1:]):
        n = max(1, int(math.ceil(np.hypot(*(q - p)) / passo)))
        out.extend(p + (q - p) * (i / n) for i in range(1, n + 1))
    return np.array(out)


def _semelhanca(x, y):
    """Procrustes com escala: (s, phi, t) com y ~ s R(phi) x + t (phi anti-horário, rad)."""
    mx, my = x.mean(0), y.mean(0)
    a, b = x - mx, y - my
    num = (a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]).sum()
    den = (a * b).sum()
    phi = math.atan2(num, den)
    s = math.hypot(num, den) / max((a ** 2).sum(), 1e-18)
    rot = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
    t = my - s * rot.dot(mx)
    return s, phi, rot, t


# ---------------------------------------------------------------- ajuste

_LIVRES = {
    'circle': ('radius',),
    'sector': ('radius', 'bearing', 'aperture'),
    'ellipse': ('majorRadius', 'minorRadius', 'bearing'),
    'rectangle': ('width', 'height', 'bearing'),
}


def tamanho(tipo, p):
    """O tamanho de referência da tolerância, em metros."""
    if tipo in ('circle', 'sector'):
        return float(p['radius'])
    if tipo == 'ellipse':
        return max(p['majorRadius'], p['minorRadius']) * 1000
    return math.hypot(p['width'], p['height']) / 2


def tolerancia(tipo, p):
    return max(TOL_PISO_M, TOL_FRACAO * tamanho(tipo, p))


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _parametros_validos(tipo, p):
    c = p.get('center')
    if not (isinstance(c, (list, tuple)) and len(c) >= 2 and _numero(c[0]) and _numero(c[1])):
        return False
    for k in _LIVRES[tipo]:
        if k == 'bearing':
            if k in p and p[k] is not None and not _numero(p[k]):
                return False
        elif not (_numero(p.get(k)) and p[k] > 0):
            return False
    return True


def ajustar(tipo, props0, anel0, anel):
    """
    Os parâmetros do Web para o anel editado `anel` ([[lon, lat], ...], fechado), partindo das
    propriedades originais `props0` e do anel original `anel0`. Devolve (parâmetros, anel regenerado,
    desvio em m, tolerância em m) ou None quando não dá para ajustar (tipo, propriedades ou anel
    incompatíveis). Os parâmetros valem quando desvio <= tolerância.
    """
    if tipo not in TIPOS or not _parametros_validos(tipo, props0):
        return None
    p0 = {k: props0[k] for k in ('center', 'borderRadius') + _LIVRES[tipo] if k in props0}
    p0['center'] = [float(props0['center'][0]), float(props0['center'][1])]
    p0['bearing'] = float(props0.get('bearing') or 0.0)
    if len(anel) < 4 or len(anel0) < 4:
        return None
    lon_c = float(np.mean([q[0] for q in anel[:-1]]))
    lat_c = float(np.mean([q[1] for q in anel[:-1]]))
    plano = _Plano(lon_c, lat_c)
    Y = plano.xy(anel)
    X0 = plano.xy(anel0)

    # ponto de partida: a semelhança que leva o anel original ao editado (vértice a vértice)
    if len(anel0) == len(anel):
        s, phi, rot, t = _semelhanca(X0[:-1], Y[:-1])
    else:
        s, phi, rot = 1.0, 0.0, np.eye(2)
        t = Y[:-1].mean(0) - X0[:-1].mean(0)
    c0 = rot.dot(plano.xy([p0['center']])[0]) * s + t
    inicio = dict(p0)
    for k in _LIVRES[tipo]:
        if k == 'bearing':
            inicio[k] = p0['bearing'] - math.degrees(phi)
        elif k != 'aperture':
            inicio[k] = p0[k] * s

    nomes = list(_LIVRES[tipo])

    def montar(v):
        q = dict(inicio)
        q['center'] = plano.lonlat(v[0], v[1])
        for i, k in enumerate(nomes):
            q[k] = float(v[2 + i])
        return q

    if tipo == 'circle':
        # o círculo do Web não tem giro (o anel começa sempre a leste): a correspondência de vértices
        # não vale depois de girar, e o ajuste é o algébrico (Kåsa), refeito no plano do centro achado
        p = dict(inicio)
        for _ in range(2):
            cx, cy, r = _circulo_algebrico(Y[:-1])
            p['center'], p['radius'] = plano.lonlat(cx, cy), r
            plano = _Plano(*p['center'])
            Y = plano.xy(anel)
    else:
        v = np.array([c0[0], c0[1]] + [inicio[k] for k in nomes], dtype=float)
        if len(gerar(tipo, montar(v))) == len(anel):
            v = _levenberg_marquardt(lambda w: (plano.xy(gerar(tipo, montar(w))) - Y).ravel()
                                     if len(gerar(tipo, montar(w))) == len(anel) else None, v)
        p = montar(v)
    for k in nomes:
        if k == 'bearing':
            p[k] = p0['bearing'] + ((p[k] - p0['bearing'] + 180) % 360) - 180   # o giro mais perto do original
        elif not (p[k] > 0):
            return None
    if tipo == 'sector' and not (0 < p['aperture'] <= 360):
        return None
    if tipo == 'ellipse' and p['minorRadius'] > p['majorRadius']:
        # o Web desenha o semieixo maior no rumo: troca e gira de 90 graus
        p['majorRadius'], p['minorRadius'] = p['minorRadius'], p['majorRadius']
        p['bearing'] = p['bearing'] + 90
    novo = gerar(tipo, p)
    passo = max(1.0, tamanho(tipo, p) / 200)
    desvio = _hausdorff(_densificar(plano.xy(novo), passo), _densificar(Y, passo))
    return p, novo, desvio, tolerancia(tipo, p)


def _circulo_algebrico(pts):
    """Círculo de mínimos quadrados algébrico (Kåsa): (cx, cy, r) no plano."""
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones(len(x))])
    (cx, cy, c), *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
    return float(cx), float(cy), float(math.sqrt(max(c + cx * cx + cy * cy, 0.0)))


def _levenberg_marquardt(residuo, v, iteracoes=40):
    """Mínimos quadrados não lineares com jacobiano numérico; residuo(v) None é passo recusado."""
    r = residuo(v)
    if r is None:
        return v
    custo = float(r.dot(r))
    lam = 1e-3
    for _ in range(iteracoes):
        J = np.empty((len(r), len(v)))
        for j in range(len(v)):
            h = 1e-6 * max(1.0, abs(v[j]))
            w = v.copy()
            w[j] += h
            rj = residuo(w)
            if rj is None:
                return v
            J[:, j] = (rj - r) / h
        A = J.T.dot(J)
        g = J.T.dot(r)
        melhorou = False
        for _ in range(10):
            try:
                dv = -np.linalg.solve(A + lam * np.diag(np.maximum(np.diag(A), 1e-12)), g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            w = v + dv
            rw = residuo(w)
            if rw is not None and float(rw.dot(rw)) < custo:
                v, r, custo = w, rw, float(rw.dot(rw))
                lam = max(lam / 10, 1e-12)
                melhorou = True
                break
            lam *= 10
        if not melhorou or np.abs(dv).max() < 1e-9:
            break
    return v
