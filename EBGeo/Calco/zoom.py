# -*- coding: utf-8 -*-
"""
Conversão entre a escala do QGIS e o zoom do EBGeo Web (MapLibre, tiles de 512 px).

No zoom z, um pixel CSS do MapLibre vale 78271,517 x cos(lat) / 2^z metros.
O EBGeo Web grava o zoom de criação (createdAtZoom) com uma casa decimal e
dimensiona os símbolos novos por ele; o plugin reproduz a mesma regra. Conferido lado a
lado com a tela do Web em 2026-10-05 (testes/test_zoom.py).
"""
import math

M_POR_PX_Z0 = 78271.517  # metros por pixel no zoom 0, no equador (mundo de 512 px)


def zoom_de_metros_por_pixel(metros_por_pixel, latitude):
    if metros_por_pixel <= 0:
        return None
    z = math.log2(M_POR_PX_Z0 * math.cos(math.radians(latitude)) / metros_por_pixel)
    return round(z, 1)


def metros_por_pixel_de_zoom(z, latitude):
    return M_POR_PX_Z0 * math.cos(math.radians(latitude)) / (2 ** z)


def zoom_do_canvas(canvas):
    """Zoom equivalente do canvas no centro da vista (pixel lógico, como o CSS do navegador)."""
    from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject, QgsDistanceArea, QgsPointXY

    ext = canvas.extent()
    crs = canvas.mapSettings().destinationCrs()
    centro = ext.center()
    wgs = QgsCoordinateReferenceSystem('EPSG:4326')
    tr = QgsCoordinateTransform(crs, wgs, QgsProject.instance())
    c = tr.transform(centro)
    da = QgsDistanceArea()
    da.setSourceCrs(crs, QgsProject.instance().transformContext())
    da.setEllipsoid('WGS84')
    largura_m = da.measureLine(QgsPointXY(ext.xMinimum(), centro.y()), QgsPointXY(ext.xMaximum(), centro.y()))
    largura_px = canvas.width() / max(canvas.devicePixelRatioF(), 1.0)
    if largura_px <= 0 or largura_m <= 0:
        return None, c.y()
    return zoom_de_metros_por_pixel(largura_m / largura_px, c.y()), c.y()


# Tamanhos iniciais do EBGeo Web na criação, em função do zoom.
def tamanho_simbolo_linha_coordenacao_km(z):
    return max(0.03, (2 ** (16 - z)) * 0.03)


def tamanho_simbolo_limite_km(z):
    return max(0.05, (2 ** (16 - z)) * 0.05)


def largura_seta_m(z):
    return max(50.0, (2 ** (16 - z)) * 25.0)
