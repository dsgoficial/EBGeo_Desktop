# -*- coding: utf-8 -*-
"""
Motor de visibilidade do EBGeo sobre o GDAL que vem no QGIS, sem GRASS.

Serve as três frentes do plugin:
  - Mapa de visibilidade (um observador, saída 0/1);
  - Análise de Visibilidade por setor (soma dos observadores que veem cada célula do seu setor);
  - Cobertura de radar ou sensor (alvo em altitude fixa, contagem de sensores por célula).

O que o motor garante, nesta ordem:
  1. guarda de extensão: observador fora do MDE, ou numa célula sem dado, é erro claro (ErroVisada);
  2. SRC métrico: MDE em graus (ou em pés, ou no Pseudo-Mercator, que estica as distâncias) é
     reprojetado para o UTM do centro da área, SIRGAS 2000 quando o MDE é SIRGAS 2000;
  3. recorte à área de interesse: só as células ao alcance entram no cálculo; sem reprojeção o
     recorte copia as células do MDE sem reamostrar;
  4. visada pelo `gdal.ViewshedGenerate` com o coeficiente de curvatura 1 - k, k de refracao.py.

Funções puras (GDAL e numpy, sem camada do QGIS): rodam em QgsTask ou em algoritmo de Processing.
O chamador transforma os pontos e as geometrias para o SRC do MDE antes de chamar.
"""
import math

import numpy as np
from osgeo import gdal, ogr, osr

from .refracao import K_OPTICO, K_RADAR, coeficiente_curvatura

#: Valor de "sem dado" das matrizes de contagem (soma por setor e cobertura).
SEM_DADO_CONTAGEM = -1
#: Valor de "sem dado" do mapa 0/1 de visibilidade (o mesmo do GRASS r.viewshed -b em Byte).
SEM_DADO_MAPA = 255
#: Teto de células da grade de cálculo antes de engrossar a resolução sozinho (cobertura de radar).
TETO_CELULAS = 16_000_000


class ErroVisada(Exception):
    """Erro de entrada com mensagem para o operador (em português)."""


class Cancelado(Exception):
    """O cálculo foi cancelado pelo operador (a tarefa em segundo plano)."""


def _parar_se_cancelado(cancelado):
    if cancelado is not None and cancelado():
        raise Cancelado()


def _avanco(progresso, cancelado, inicio, fim):
    """Callback de progresso do GDAL que leva 0..1 a inicio..fim e devolve 0 (para) se cancelado."""
    if progresso is None and cancelado is None:
        return None

    def cb(completo, _mensagem=None, _dados=None):
        if progresso is not None:
            progresso(inicio + (fim - inicio) * float(completo))
        return 0 if (cancelado is not None and cancelado()) else 1
    return cb


class _Excecoes:
    """Liga as exceções do GDAL, OGR e OSR só durante o cálculo, sem mexer no resto do QGIS."""

    def __enter__(self):
        self._gerentes = [gdal.ExceptionMgr(useExceptions=True), ogr.ExceptionMgr(useExceptions=True),
                          osr.ExceptionMgr(useExceptions=True)]
        for g in self._gerentes:
            g.__enter__()
        return self

    def __exit__(self, *exc):
        for g in reversed(self._gerentes):
            g.__exit__(*exc)
        return False


def _srs(wkt):
    s = osr.SpatialReference()
    s.SetFromUserInput(wkt)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def _transformar(origem, destino, pontos):
    if origem.IsSame(destino):
        return [(float(x), float(y)) for x, y in pontos]
    ct = osr.CoordinateTransformation(origem, destino)
    return [tuple(ct.TransformPoint(float(x), float(y))[:2]) for x, y in pontos]


def precisa_reprojetar(srs):
    """Verdadeiro quando o SRC não mede distância em metros sem distorção grosseira."""
    if srs.IsGeographic():
        return True
    if srs.IsLocal():
        return False
    if abs(srs.GetLinearUnits() - 1.0) > 1e-9:
        return True
    proj = (srs.GetAttrValue('PROJECTION') or '').lower()
    return 'mercator' in proj and 'transverse' not in proj


def src_utm(lon, lat, srs_mde):
    """UTM do ponto (lon, lat): SIRGAS 2000 quando o MDE é SIRGAS 2000 e a zona existe, senão WGS 84."""
    zona = min(60, max(1, int(math.floor((lon + 180.0) / 6.0)) + 1))
    sul = lat < 0
    nomes = ' '.join((srs_mde.GetAttrValue(c) or '') for c in ('GEOGCS', 'DATUM')).upper()
    candidatos = []
    if 'SIRGAS' in nomes and '2000' in nomes:
        candidatos.append((31960 if sul else 31954) + zona)
    candidatos.append((32700 if sul else 32600) + zona)
    sufixo = 'zone {}{}'.format(zona, 'S' if sul else 'N')
    for codigo in candidatos:
        s = osr.SpatialReference()
        try:
            s.ImportFromEPSG(codigo)
        except Exception:
            continue
        if sufixo in (s.GetName() or ''):
            s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            return s
    s = osr.SpatialReference()
    s.SetProjCS('UTM {}'.format(sufixo))
    s.SetWellKnownGeogCS('WGS84')
    s.SetUTM(zona, not sul)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


class Grade:
    """O MDE recortado (e, se preciso, reprojetado) na área de interesse, num SRC métrico."""

    def __init__(self, ds, srs, valido, reprojetado, pontos, srs_mde):
        self.ds = ds
        self.banda = ds.GetRasterBand(1)
        self.srs = srs
        self.srs_mde = srs_mde
        self.gt = ds.GetGeoTransform()
        self.largura = ds.RasterXSize
        self.altura = ds.RasterYSize
        self.valido = valido
        self.reprojetado = reprojetado
        #: os pontos pedidos, no SRC da grade
        self.pontos = pontos
        self.z = self.banda.ReadAsArray().astype(np.float64)
        self._centros = None

    @property
    def wkt(self):
        return self.srs.ExportToWkt()

    @property
    def resolucao(self):
        return (abs(self.gt[1]), abs(self.gt[5]))

    def centros(self):
        """Coordenadas X e Y dos centros das células (matrizes do tamanho da grade)."""
        if self._centros is None:
            gt = self.gt
            col = np.arange(self.largura) + 0.5
            lin = np.arange(self.altura) + 0.5
            x = gt[0] + col * gt[1]
            y = gt[3] + lin * gt[5]
            self._centros = np.meshgrid(x, y)
        return self._centros

    def distancia(self, x, y):
        cx, cy = self.centros()
        return np.hypot(cx - x, cy - y)

    def de_mde(self, pontos):
        """Pontos no SRC do MDE para o SRC da grade."""
        return _transformar(self.srs_mde, self.srs, pontos)

    def geometria(self, wkb):
        """Geometria (WKB no SRC do MDE) no SRC da grade."""
        g = ogr.CreateGeometryFromWkb(bytes(wkb))
        if not self.srs_mde.IsSame(self.srs):
            g.Transform(osr.CoordinateTransformation(self.srs_mde, self.srs))
        return g


def _abrir(fonte, banda):
    try:
        ds = gdal.Open(fonte)
    except Exception:
        ds = None
    if ds is None:
        raise ErroVisada('Não foi possível abrir o MDE pelo GDAL. Use um raster em arquivo (GeoTIFF, por exemplo).')
    if banda < 1 or banda > ds.RasterCount:
        raise ErroVisada('O MDE não tem a banda {}.'.format(banda))
    gt = ds.GetGeoTransform()
    if gt[2] != 0 or gt[4] != 0:
        raise ErroVisada('O MDE está rotacionado; reamostre-o para uma grade norte acima antes da análise.')
    if not ds.GetProjection():
        raise ErroVisada('O MDE não tem sistema de referência definido.')
    return ds


def _num(v):
    return '{:.6f}'.format(v) if abs(v) < 1000 else '{:.1f}'.format(v)


def _guarda(ds, banda, pontos, rotulo):
    """Ponto fora do MDE, ou sobre célula sem dado, é erro claro."""
    gt = ds.GetGeoTransform()
    w, h = ds.RasterXSize, ds.RasterYSize
    b = ds.GetRasterBand(banda)
    nd = b.GetNoDataValue()
    x0, x1 = sorted((gt[0], gt[0] + w * gt[1]))
    y0, y1 = sorted((gt[3], gt[3] + h * gt[5]))
    for i, (x, y) in enumerate(pontos):
        col = (x - gt[0]) / gt[1]
        lin = (y - gt[3]) / gt[5]
        nome = '{} {}'.format(rotulo, i + 1) if len(pontos) > 1 else 'O {}'.format(rotulo.lower())
        if not (0 <= col < w and 0 <= lin < h):
            raise ErroVisada(
                '{} está fora do MDE: ({}; {}), e o MDE cobre X de {} a {} e Y de {} a {} no SRC '
                'dele. Escolha um ponto dentro do MDE.'.format(
                    nome, _num(x), _num(y), _num(x0), _num(x1), _num(y0), _num(y1)))
        v = float(b.ReadAsArray(int(col), int(lin), 1, 1)[0, 0])
        if math.isnan(v) or (nd is not None and v == nd):
            raise ErroVisada('{} cai numa célula sem dado do MDE ({}; {}).'.format(nome, _num(x), _num(y)))


def _extensao_em(ds, srs_mde, srs_destino):
    """Envelope da extensão do MDE no SRC de destino (borda adensada antes de transformar)."""
    gt = ds.GetGeoTransform()
    w, h = ds.RasterXSize, ds.RasterYSize
    xs = [gt[0] + gt[1] * w * i / 32.0 for i in range(33)]
    ys = [gt[3] + gt[5] * h * i / 32.0 for i in range(33)]
    borda = ([(x, ys[0]) for x in xs] + [(x, ys[-1]) for x in xs]
             + [(xs[0], y) for y in ys] + [(xs[-1], y) for y in ys])
    t = _transformar(srs_mde, srs_destino, borda)
    tx = [p[0] for p in t if all(map(math.isfinite, p))]
    ty = [p[1] for p in t if all(map(math.isfinite, p))]
    return min(tx), min(ty), max(tx), max(ty)


def preparar_grade(fonte, pontos, raios, banda=1, geometrias=(), resolucao=None, rotulo='Observador',
                   teto_celulas=None, avisos=None):
    """
    Abre o MDE, confere a extensão, escolhe o SRC métrico e recorta a área de interesse.

    pontos: [(x, y)] no SRC do MDE; raios: um raio (m) por ponto, ou um número para todos;
    geometrias: WKB (SRC do MDE) que também têm de caber na grade; resolucao: força a célula (m);
    teto_celulas: engrossa a resolução quando a grade passaria do teto (e avisa em `avisos`).
    """
    with _Excecoes():
        return _preparar_grade(fonte, pontos, raios, banda, geometrias, resolucao, rotulo,
                               teto_celulas, avisos if avisos is not None else [])


def _preparar_grade(fonte, pontos, raios, banda, geometrias, resolucao, rotulo, teto_celulas, avisos):
    ds = _abrir(fonte, banda)
    if ds.RasterCount > 1 or banda != 1:
        ds = gdal.Translate('', ds, format='VRT', bandList=[banda])
    srs_mde = _srs(ds.GetProjection())
    _guarda(ds, 1, pontos, rotulo)
    if not isinstance(raios, (list, tuple)):
        raios = [float(raios)] * len(pontos)
    reprojetar = precisa_reprojetar(srs_mde)
    if reprojetar:
        geo = srs_mde.CloneGeogCS()
        geo.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        ref = pontos[0] if pontos else None
        if ref is None:
            gt = ds.GetGeoTransform()
            ref = (gt[0] + gt[1] * ds.RasterXSize / 2.0, gt[3] + gt[5] * ds.RasterYSize / 2.0)
        lons, lats = zip(*_transformar(srs_mde, geo, list(pontos) or [ref]))
        srs_t = src_utm(sum(lons) / len(lons), sum(lats) / len(lats), srs_mde)
    else:
        srs_t = srs_mde
    pts_t = _transformar(srs_mde, srs_t, pontos)

    # área de interesse: cada ponto com o seu raio, mais as geometrias
    caixas = [(x - r, y - r, x + r, y + r) for (x, y), r in zip(pts_t, raios)]
    for wkb in geometrias:
        g = ogr.CreateGeometryFromWkb(bytes(wkb))
        if not srs_mde.IsSame(srs_t):
            g.Transform(osr.CoordinateTransformation(srs_mde, srs_t))
        e = g.GetEnvelope()
        caixas.append((e[0], e[2], e[1], e[3]))
    xmin = min(c[0] for c in caixas)
    ymin = min(c[1] for c in caixas)
    xmax = max(c[2] for c in caixas)
    ymax = max(c[3] for c in caixas)
    ex = _extensao_em(ds, srs_mde, srs_t)
    if xmin < ex[0] or ymin < ex[1] or xmax > ex[2] or ymax > ex[3]:
        avisos.append('Parte da área de interesse fica fora do MDE: ali não há cálculo.')
    xmin, ymin, xmax, ymax = max(xmin, ex[0]), max(ymin, ex[1]), min(xmax, ex[2]), min(ymax, ex[3])
    if xmin >= xmax or ymin >= ymax:
        raise ErroVisada('A área de interesse não cruza o MDE.')

    gt = ds.GetGeoTransform()
    if reprojetar:
        cx, cy = gt[0] + gt[1] * ds.RasterXSize / 2.0, gt[3] + gt[5] * ds.RasterYSize / 2.0
        p = _transformar(srs_mde, srs_t, [(cx, cy), (cx + gt[1], cy), (cx, cy + gt[5])])
        res_nativa = math.sqrt(math.dist(p[0], p[1]) * math.dist(p[0], p[2]))
    else:
        res_nativa = math.sqrt(abs(gt[1] * gt[5]))
    res = float(resolucao) if resolucao else res_nativa
    if teto_celulas:
        celulas = (xmax - xmin) * (ymax - ymin) / (res * res)
        if celulas > teto_celulas:
            res = math.sqrt((xmax - xmin) * (ymax - ymin) / teto_celulas)
            res = math.ceil(res)
            avisos.append('A área pediria {:.0f} milhões de células; o cálculo usa células de {:.0f} m '
                          '(o MDE tem {:.1f} m).'.format(celulas / 1e6, res, res_nativa))

    nd = ds.GetRasterBand(1).GetNoDataValue()
    if not reprojetar and abs(res - res_nativa) < 1e-9 * res_nativa:
        # recorte exato: copia as células do MDE, sem reamostrar
        c0 = max(0, int(math.floor((xmin - gt[0]) / gt[1])))
        c1 = min(ds.RasterXSize, int(math.ceil((xmax - gt[0]) / gt[1])))
        ya, yb = (ymax, ymin) if gt[5] < 0 else (ymin, ymax)
        r0 = max(0, int(math.floor((ya - gt[3]) / gt[5])))
        r1 = min(ds.RasterYSize, int(math.ceil((yb - gt[3]) / gt[5])))
        out = gdal.Translate('', ds, format='MEM', srcWin=[c0, r0, c1 - c0, r1 - r0],
                             outputType=gdal.GDT_Float32)
    else:
        nd_dst = nd if nd is not None else -32768.0
        out = gdal.Warp('', ds, format='MEM', dstSRS=srs_t.ExportToWkt(), outputBounds=(xmin, ymin, xmax, ymax),
                        xRes=res, yRes=res, targetAlignedPixels=True, resampleAlg='bilinear',
                        srcNodata=nd, dstNodata=nd_dst, outputType=gdal.GDT_Float32)
        nd = nd_dst
    b = out.GetRasterBand(1)
    z = b.ReadAsArray().astype(np.float64)
    valido = np.isfinite(z)
    if nd is not None:
        valido &= z != nd
    if not valido.any():
        raise ErroVisada('O MDE não tem dado na área de interesse.')
    # o viewshed do GDAL toma o "sem dado" como cota (e avisa que a saída fica errada): a célula
    # sem dado vira a menor cota válida, que não bloqueia nada, e sai mascarada no fim
    z_cheio = np.where(valido, z, z[valido].min()).astype(np.float32)
    b.WriteArray(z_cheio)
    b.DeleteNoDataValue()
    return Grade(out, srs_t, valido, reprojetar or out.GetProjection() != ds.GetProjection(), pts_t, srs_mde)


def visada(grade, x, y, altura_obs, raio, k=K_OPTICO, altura_alvo=0.0, modo='normal', progresso=None,
           cancelado=None):
    """
    Visada de um observador em (x, y), no SRC da grade.

    modo 'normal': matriz booleana (visível); 'chao': altura mínima do alvo acima do terreno para
    ser visto (m), infinita fora do alcance ou sem dado; 'mde': a mesma altura somada à cota.
    progresso(p) recebe de 0 a 100 durante o GDAL; cancelado() verdadeiro levanta Cancelado.
    """
    _parar_se_cancelado(cancelado)
    cb = _avanco(progresso, cancelado, 0.0, 100.0)
    with _Excecoes():
        modos = {'normal': gdal.GVOT_NORMAL, 'chao': gdal.GVOT_MIN_TARGET_HEIGHT_FROM_GROUND,
                 'mde': gdal.GVOT_MIN_TARGET_HEIGHT_FROM_DEM}
        passo = max(grade.resolucao)
        try:
            v = gdal.ViewshedGenerate(grade.banda, 'MEM', '', [], float(x), float(y), float(altura_obs),
                                      float(altura_alvo), 1, 0, 0, 0, coeficiente_curvatura(k), gdal.GVM_Edge,
                                      float(raio) + 2 * passo, callback=cb, heightMode=modos[modo])
        except RuntimeError:
            _parar_se_cancelado(cancelado)
            raise
        _parar_se_cancelado(cancelado)
        a = v.GetRasterBand(1).ReadAsArray()
        gv = v.GetGeoTransform()
    gt = grade.gt
    c0 = int(round((gv[0] - gt[0]) / gt[1]))
    r0 = int(round((gv[3] - gt[3]) / gt[5]))
    fora = (grade.distancia(x, y) > raio) | ~grade.valido
    if modo == 'normal':
        saida = np.zeros((grade.altura, grade.largura), dtype=bool)
        _colar(saida, a == 1, r0, c0)
        saida[fora] = False
    else:
        saida = np.full((grade.altura, grade.largura), np.inf)
        _colar(saida, a.astype(np.float64), r0, c0)
        saida[fora] = np.inf
    return saida


def _colar(destino, origem, r0, c0):
    h, w = origem.shape
    rd0, cd0 = max(0, r0), max(0, c0)
    rd1, cd1 = min(destino.shape[0], r0 + h), min(destino.shape[1], c0 + w)
    if rd1 > rd0 and cd1 > cd0:
        destino[rd0:rd1, cd0:cd1] = origem[rd0 - r0:rd1 - r0, cd0 - c0:cd1 - c0]


def mascara(grade, geometria):
    """Células da grade cujo centro cai na geometria (OGR, no SRC da grade)."""
    with _Excecoes():
        m = gdal.GetDriverByName('MEM').Create('', grade.largura, grade.altura, 1, gdal.GDT_Byte)
        m.SetGeoTransform(grade.gt)
        m.SetProjection(grade.wkt)
        vds = gdal.GetDriverByName('MEM').Create('', 0, 0, 0, gdal.GDT_Unknown)
        lyr = vds.CreateLayer('m', grade.srs, ogr.wkbUnknown)
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetGeometry(geometria)
        lyr.CreateFeature(f)
        gdal.RasterizeLayer(m, [1], lyr, burn_values=[1])
        return m.GetRasterBand(1).ReadAsArray().astype(bool)


class Resultado:
    def __init__(self, grade, matriz, avisos):
        self.grade = grade
        self.matriz = matriz
        self.avisos = avisos


def mapa_visibilidade(fonte, x, y, altura_obs, raio, banda=1, k=K_OPTICO, progresso=None, cancelado=None):
    """
    Mapa 0/1 de um observador (x, y no SRC do MDE); célula sem dado do MDE = SEM_DADO_MAPA.
    Raio zero ou negativo é alcance ilimitado (o -1 do r.viewshed): o MDE inteiro.
    progresso(p) recebe de 0 a 100; cancelado() verdadeiro levanta Cancelado.
    """
    avisos = []
    ilimitado = not raio or raio <= 0
    if ilimitado:
        raio = 1.0e7
    grade = preparar_grade(fonte, [(x, y)], raio, banda=banda, avisos=avisos)
    if ilimitado:
        avisos.clear()
    ox, oy = grade.pontos[0]
    if progresso is not None:
        progresso(5.0)
    vis = visada(grade, ox, oy, altura_obs, raio, k, cancelado=cancelado,
                 progresso=None if progresso is None else (lambda p: progresso(5.0 + 0.9 * p)))
    m = vis.astype(np.uint8)
    m[~grade.valido] = SEM_DADO_MAPA
    return Resultado(grade, m, avisos)


def _primeiro_vertice(g):
    """O observador do setor: o primeiro vértice do anel externo (o centro desenhado pela ferramenta)."""
    if g.GetGeometryType() in (ogr.wkbMultiPolygon, ogr.wkbMultiPolygon25D):
        g = g.GetGeometryRef(0)
    anel = g.GetGeometryRef(0)
    return anel.GetX(0), anel.GetY(0), anel


def soma_por_setor(fonte, setores, banda=1, k=K_OPTICO, progresso=None, cancelado=None):
    """
    A Análise de Visibilidade por setor: cada setor (WKB no SRC do MDE, altura do observador)
    tem o observador no primeiro vértice e alcance até o vértice mais distante. A célula vale o
    número de observadores que a veem DENTRO do próprio setor; fora de todos os setores, ou sem
    dado no MDE, vale SEM_DADO_CONTAGEM. progresso(p) recebe de 0 a 100; cancelado() verdadeiro
    levanta Cancelado.
    """
    if not setores:
        raise ErroVisada('Não há nenhum setor de visada adquirido.')
    avisos = []
    with _Excecoes():
        centros = []
        for wkb, _ in setores:
            x, y, _anel = _primeiro_vertice(ogr.CreateGeometryFromWkb(bytes(wkb)))
            centros.append((x, y))
    grade = preparar_grade(fonte, centros, 0.0, banda=banda, geometrias=[w for w, _ in setores],
                           avisos=avisos)
    contagem = np.zeros((grade.altura, grade.largura), dtype=np.int16)
    uniao = np.zeros_like(grade.valido)
    n = len(setores)
    for i, (wkb, altura) in enumerate(setores):
        _parar_se_cancelado(cancelado)
        g = grade.geometria(wkb)
        cx, cy, anel = _primeiro_vertice(g)
        raio = max(math.hypot(anel.GetX(j) - cx, anel.GetY(j) - cy) for j in range(anel.GetPointCount()))
        dentro = mascara(grade, g)
        vis = visada(grade, cx, cy, altura, raio, k, cancelado=cancelado,
                     progresso=None if progresso is None else (lambda p, i=i: progresso(5.0 + 90.0 * (i + p / 100.0) / n)))
        contagem += (vis & dentro).astype(np.int16)
        uniao |= dentro
    contagem[~(uniao & grade.valido)] = SEM_DADO_CONTAGEM
    return Resultado(grade, contagem, avisos)


def cobertura(fonte, sensores, altitude_alvo, referencia='terreno', banda=1, k=K_RADAR, resolucao=None,
              teto_celulas=TETO_CELULAS, progresso=None, cancelado=None):
    """
    Cobertura de sensores para um alvo em altitude fixa.

    sensores: [(x, y, altura_antena_m, alcance_m)] no SRC do MDE; referencia 'terreno' (altitude
    acima do terreno) ou 'mar' (acima do nível do mar, a cota do MDE). A célula vale o número de
    sensores que veem um alvo na altitude pedida sobre ela (0 = sem cobertura); sem dado no MDE
    vale SEM_DADO_CONTAGEM. Com alvo acima do nível do mar, célula com terreno acima do alvo não
    tem cobertura.
    """
    if not sensores:
        raise ErroVisada('Não há sensor na camada de entrada.')
    if referencia not in ('terreno', 'mar'):
        raise ValueError(referencia)
    for i, s in enumerate(sensores):
        if s[3] <= 0:
            raise ErroVisada('O sensor {} tem alcance nulo ou negativo.'.format(i + 1))
        if s[2] < 0:
            raise ErroVisada('O sensor {} tem altura de antena negativa.'.format(i + 1))
    avisos = []
    grade = preparar_grade(fonte, [(s[0], s[1]) for s in sensores], [float(s[3]) for s in sensores],
                           banda=banda, resolucao=resolucao, rotulo='Sensor', teto_celulas=teto_celulas,
                           avisos=avisos)
    if referencia == 'terreno':
        altura_alvo = float(altitude_alvo)
    else:
        altura_alvo = float(altitude_alvo) - grade.z
    contagem = np.zeros((grade.altura, grade.largura), dtype=np.int16)
    for i, ((x, y), s) in enumerate(zip(grade.pontos, sensores)):
        if cancelado is not None and cancelado():
            break
        minima = visada(grade, x, y, s[2], s[3], k, modo='chao')
        contagem += ((altura_alvo >= minima) & np.isfinite(minima)).astype(np.int16)
        if progresso is not None:
            progresso(100.0 * (i + 1) / len(sensores))
    contagem[~grade.valido] = SEM_DADO_CONTAGEM
    return Resultado(grade, contagem, avisos)


def salvar_geotiff(grade, matriz, caminho, tipo, sem_dado=None):
    """Grava a matriz no GeoTIFF com a georreferência da grade."""
    with _Excecoes():
        ds = gdal.GetDriverByName('GTiff').Create(caminho, grade.largura, grade.altura, 1, tipo,
                                                  options=['COMPRESS=DEFLATE'])
        ds.SetGeoTransform(grade.gt)
        ds.SetProjection(grade.wkt)
        b = ds.GetRasterBand(1)
        if sem_dado is not None:
            b.SetNoDataValue(sem_dado)
        b.WriteArray(matriz)
        b.FlushCache()
        ds = None
    return caminho


def poligonizar(grade, matriz, caminho, campo, nome_camada, incluir=None, formato='GPKG'):
    """
    Polígonos das regiões de mesmo valor (conectividade de 4, como o r.to.vect do GRASS).
    incluir: máscara booleana das células a poligonizar (padrão: o que não é SEM_DADO_CONTAGEM).
    """
    if incluir is None:
        incluir = matriz != SEM_DADO_CONTAGEM
    with _Excecoes():
        r = gdal.GetDriverByName('MEM').Create('', grade.largura, grade.altura, 2, gdal.GDT_Int32)
        r.SetGeoTransform(grade.gt)
        r.SetProjection(grade.wkt)
        r.GetRasterBand(1).WriteArray(matriz.astype(np.int32))
        r.GetRasterBand(2).WriteArray(incluir.astype(np.int32))
        drv = ogr.GetDriverByName(formato)
        vds = drv.CreateDataSource(caminho)
        lyr = vds.CreateLayer(nome_camada, grade.srs, ogr.wkbPolygon)
        lyr.CreateField(ogr.FieldDefn(campo, ogr.OFTInteger))
        gdal.Polygonize(r.GetRasterBand(1), r.GetRasterBand(2), lyr, 0, [])
        lyr = None
        vds = None
    return caminho
