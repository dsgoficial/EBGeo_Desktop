# -*- coding: utf-8 -*-
"""
MDE sintético e referência analítica de visada para os testes da Visada.

A referência NÃO usa o GDAL: amostra a linha de visada sobre a superfície analítica (a função
z(x, y), não a grade), com a queda da curvatura e da refração, e decide cada alvo por conta
própria. As diferenças contra o GDAL ficam só na borda das sombras, onde a grade discreta e a
superfície contínua divergem por meia célula.
"""
import math
import os

import numpy as np
from osgeo import gdal, osr

#: Raio que o GDAL usa (semieixo maior do GRS80/WGS 84), para a referência falar a mesma língua.
R_GDAL = 6378137.0
X0, Y0 = 500000.0, 8250000.0   # canto NO da grade em SIRGAS 2000 / UTM 23S (EPSG:31983)


def gravar_mde(caminho, z, res, x0=X0, y0=Y0, epsg=31983, sem_dado=-9999.0):
    """GeoTIFF Float32. O "sem dado" entra ANTES dos dados: o GTiff não grava bloco todo zero de
    arquivo novo, e com o "sem dado" definido depois esse bloco volta lido como "sem dado"."""
    ds = gdal.GetDriverByName('GTiff').Create(caminho, z.shape[1], z.shape[0], 1, gdal.GDT_Float32)
    ds.SetGeoTransform((x0, res, 0, y0, 0, -res))
    s = osr.SpatialReference()
    s.ImportFromEPSG(epsg)
    ds.SetProjection(s.ExportToWkt())
    b = ds.GetRasterBand(1)
    if sem_dado is not None:
        b.SetNoDataValue(sem_dado)
    b.WriteArray(np.asarray(z, dtype=np.float32))
    b.FlushCache()
    ds = None
    return caminho


def centros(n_lin, n_col, res, x0=X0, y0=Y0):
    x = x0 + (np.arange(n_col) + 0.5) * res
    y = y0 - (np.arange(n_lin) + 0.5) * res
    return np.meshgrid(x, y)


def gaussiana(cx, cy, altura, sigma, base=0.0):
    return lambda x, y: base + altura * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))


def plano(cota):
    return lambda x, y: np.full(np.broadcast(x, y).shape, float(cota))


def altura_minima(zfun, ox, oy, h_obs, tx, ty, k, raio_terra=R_GDAL, amostras=600):
    """
    Altura mínima acima do terreno para o alvo em (tx, ty) ser visto do observador em (ox, oy)
    a h_obs m do chão, com a Terra de raio raio_terra / (1 - k). Vetorizado nos alvos.
    """
    tx = np.asarray(tx, dtype=np.float64)
    ty = np.asarray(ty, dtype=np.float64)
    D = np.hypot(tx - ox, ty - oy)
    c = (1.0 - k) / (2.0 * raio_terra)
    zo = float(zfun(np.array(ox), np.array(oy))) + h_obs
    zt = zfun(tx, ty) - c * D * D
    req = np.zeros_like(D)
    for t in (np.arange(1, amostras) / amostras):
        xs = ox + t * (tx - ox)
        ys = oy + t * (ty - oy)
        ds = t * D
        zs = zfun(xs, ys) - c * ds * ds
        req = np.maximum(req, (zs - zo) / t + zo - zt)
    req[D == 0] = 0.0
    return np.maximum(req, 0.0)


def visivel(zfun, ox, oy, h_obs, tx, ty, k, h_alvo=0.0, **kw):
    return altura_minima(zfun, ox, oy, h_obs, tx, ty, k, **kw) <= h_alvo + 1e-6


def pasta_imagens():
    p = os.environ.get('EBGEO_IMAGENS')
    if not p:
        import tempfile
        p = tempfile.mkdtemp(prefix='ebgeo_visada_')
    os.makedirs(p, exist_ok=True)
    return p
