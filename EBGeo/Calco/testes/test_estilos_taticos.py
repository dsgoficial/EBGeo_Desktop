# -*- coding: utf-8 -*-
"""
Testes dos estilos táticos do calco (estilos_taticos.py e expressoes/*.exp).

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/Calco/testes/test_estilos_taticos.py

Variáveis de ambiente opcionais:
    EBGEO_WEB_DIR      raiz do repositório ebgeo_web; com ela (e node no PATH) o teste
                       roda o código de geometria do Web em node e compara as posições
                       com as do QGIS. Sem ela, esses testes são pulados.
    EBGEO_NODE         executável do node, quando o python-qgis.bat o tira do PATH.
    EBGEO_TESTE_SAIDA  pasta para os PNG de conferência (padrão: pasta temporária).

O que cada classe prova:
    (a) a expressão avalia sem erro;
    (b) invariantes contra o algoritmo do Web: número de glifos pela fórmula do Web
        (linha comum, linha menor que o glifo, linha longa no teto de 120), período dos
        contínuos, vãos, tamanho efetivo, áreas;
    (c) pior caso: a mesma verificação aplicada à linha pura ($geometry) reprova;
    (d) render em PNG de cada tipo, para conferência visual;
    (e) persistência: estilo gravado no GeoPackage e reaberto num QgsVectorLayer novo,
        sem código do plugin, com o mesmo renderer e o mesmo desenho.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, '..', '..'))
if PLUGIN not in sys.path:
    sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsGeometry,
    QgsMapRendererSequentialJob,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsRuleBasedLabeling,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

QGS = QgsApplication([], False)
QGS.initQgis()

from Calco import estilos_taticos as et  # noqa: E402
from Calco import gpkg, schema  # noqa: E402

R_TURF = 6371008.8          # raio do turf (earthRadius), m
MM_POR_PX = 25.4 / 96
LIMITE_DESVIO_M = 2.0       # tolerância de posição contra o Web, m (ver relatório)

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_estilos_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_calco_')
CALCO = os.path.join(TMP, 'calco_teste.gpkg')
gpkg.criar_calco(CALCO)
MEDIDAS = []                # linhas do resumo impresso no fim


def medir(texto):
    MEDIDAS.append(texto)


# ---------------------------------------------------------------------------
# Geodésia do turf (esfera R_TURF) e o algoritmo do Web portado para a expectativa
# ---------------------------------------------------------------------------

def hav_m(a, b):
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R_TURF * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def destino(p, dist_m, rumo_graus):
    la1, lo1, br = math.radians(p[1]), math.radians(p[0]), math.radians(rumo_graus)
    d = dist_m / R_TURF
    la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(br))
    lo2 = lo1 + math.atan2(math.sin(br) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
    return (math.degrees(lo2), math.degrees(la2))


def rumo(a, b):
    la1, la2, dlo = math.radians(a[1]), math.radians(b[1]), math.radians(b[0] - a[0])
    y = math.sin(dlo) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return math.degrees(math.atan2(y, x))


def comprimento_km(coords):
    return sum(hav_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1)) / 1000


def web_layout_glifos(L, size, spacing):
    """resolveGlyphLayout (coordination-line-zoom.model.js), em km."""
    if L <= 0 or size <= 0 or spacing <= 0 or size > L:
        return 0, 0.0
    spacing = max(spacing, size / 0.5)
    usable = L - size
    count = math.floor(usable / spacing) + 1
    if count > 120:
        count, spacing = 120, usable / 119
    return count, spacing


def web_layout_continuo(L, period):
    """resolveContinuousLayout, em km."""
    if L <= 0 or period <= 0 or period > L:
        return 0, 0.0
    count = min(120, max(1, int(math.floor(L / period + 0.5))))
    return count, L / count


def web_tamanhos_linha(size_km, spacing_km, fator_solo=1.0):
    """computeCoordinationLineZoomSizes: clamps sempre aplicados."""
    s = min(50, max(0.001, (size_km if size_km and size_km > 0 else 0.5) * fator_solo))
    e = min(500, max(0.002, (spacing_km if spacing_km and spacing_km > 0 else 2) * fator_solo))
    return s, e


# ---------------------------------------------------------------------------
# Camadas, feições, contexto de expressão
# ---------------------------------------------------------------------------

def camada(tipo):
    vl = QgsVectorLayer(gpkg.uri_camada(CALCO, tipo), tipo, 'ogr')
    assert vl.isValid(), tipo
    return vl


def nova_feicao(tipo, coords, **attrs):
    """Grava a feição no calco e a devolve relida do GeoPackage."""
    vl = camada(tipo)
    f = QgsFeature(vl.fields())
    if schema.TIPOS[tipo]['geometria'] == 'MultiLineString':
        partes = coords if isinstance(coords[0][0], (list, tuple)) else [coords]
        f.setGeometry(QgsGeometry.fromMultiPolylineXY([[QgsPointXY(*p) for p in parte] for parte in partes]))
    else:
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in coords]))
    valores = dict(schema.padroes(tipo))
    valores.update(attrs)
    for k, v in valores.items():
        f[k] = v
    ok, novas = vl.dataProvider().addFeatures([f])
    assert ok
    # Relida numa camada nova: medido em 2026-10-04 no QGIS 4.0.0, a mesma camada devolve
    # NULL na coluna JSON da primeira feição logo depois do addFeatures (no disco está certo).
    vl = camada(tipo)
    return vl, vl.getFeature(novas[0].id())


def mapa(centro, escala=50000, crs='EPSG:3857', tamanho=(1000, 800)):
    ms = QgsMapSettings()
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(96)
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(), QgsProject.instance())
    c = tr.transform(QgsPointXY(*centro))
    if ms.destinationCrs().isGeographic():
        upp = escala * 0.0254 / 96 / 111319.49 / math.cos(math.radians(centro[1]))
    else:
        upp = escala * 0.0254 / 96  # o QGIS calcula a escala com o dpi de saída (96)
    w, h = tamanho[0] * upp / 2, tamanho[1] * upp / 2
    ms.setExtent(QgsRectangle(c.x() - w, c.y() - h, c.x() + w, c.y() + h))
    return ms


def escala_do_zoom(z):
    """
    Escala de um mapa em EPSG:3857 equivalente ao zoom z do MapLibre (512 px), com o px do
    Web a 0,2646 mm (96 dpi): terreno 78271,517 x cos(lat) / 2^z m/px, e a escala Mercator do QGIS é
    a de terreno dividida por cos(lat).
    """
    return 78271.517 / (2 ** z) / (MM_POR_PX / 1000)


def avaliar(expr, vl, f, ms=None):
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
    ms = ms or mapa(centro_feicao(f))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ctx.setFeature(f)
    e = QgsExpression(expr)
    if e.hasParserError():
        raise AssertionError('parse: ' + e.parserErrorString())
    e.prepare(ctx)
    v = e.evaluate(ctx)
    if e.hasEvalError():
        raise AssertionError('avaliação: ' + e.evalErrorString())
    return v


def centro_feicao(f):
    c = f.geometry().centroid().asPoint()
    return (c.x(), c.y())


def partes(g):
    """Lista de listas de (x, y): cada linha, ou o anel externo de cada polígono."""
    if g is None or g.isNull() or g.isEmpty():
        return []
    out = []
    for p in g.asGeometryCollection():
        if p.type() == Qgis.GeometryType.Polygon:
            out.append([(v.x(), v.y()) for v in p.asPolygon()[0]])
        elif p.type() == Qgis.GeometryType.Line:
            out.append([(v.x(), v.y()) for v in p.asPolyline()])
        else:
            pt = p.asPoint()
            out.append([(pt.x(), pt.y())])
    return out


def eixo_de_referencia(vl, f):
    """
    O eixo como a expressão o vê: reto no plano local (e não em lon/lat), adensado a
    cada 20 m. Medido em 2026-10-04: um trecho de 10 km reto em lon/lat se afasta até
    0,5 m da reta no plano local, e um de 165 km até 145 m; contra o eixo cru a régua
    tomava trechos do próprio eixo por glifo.
    """
    txt = chr(10).join(['@@SEJA@@', '@@PROJ@@', '@@EM@@',
                        'transform(densify_by_distance(@g, 20), @crs_loc, @layer_crs)', '@@FIM@@'])
    return avaliar(et.finalizar(et.compor(None, _TEXTO=txt)), vl, f)


def fora_do_eixo(parte, eixo, tol_graus=2e-6):
    return any(eixo.distance(QgsGeometry.fromPointXY(QgsPointXY(*v))) > tol_graus for v in parte)


def comprimento_partes_km(lista):
    return sum(comprimento_km(p) for p in lista)


# Traços fora do eixo por glifo e trilhos, para contar glifos a partir da geometria.
TRACOS_POR_GLIFO = {'peak': 1, 'diamond': 1, 'asterisk': 2, 'double-asterisk': 4, 'coil': 1,
                    'coil-double': 1, 'coil-triple': 1, 'teeth': 1, 'zigzag': 1, 'tripwire': 2}
# Os símbolos que esta régua conta (glifo repetido ou dente). A 140000, a 140200 e a 240701 do
# capítulo VII não têm glifo repetido: a prova delas está em test_linha_coordenacao_vii.py.
CATALOGO_GLIFOS = {c: s for c, s in et.CATALOGO_LINHA.items() if s['glifo'] in TRACOS_POR_GLIFO}


def contar_glifos(codigo, g, eixo):
    sim = et.CATALOGO_LINHA[codigo]
    fora = [p for p in partes(g) if fora_do_eixo(p, eixo)]
    n = max(0, len(fora) - sim.get('trilhos', 0))
    return n / TRACOS_POR_GLIFO[sim['glifo']]


def geometria_linha_coordenacao(codigo, vl, f, ms=None):
    ex = et.expr_linha_coordenacao(codigo)
    if ex['preenchimento']:
        g = avaliar(ex['preenchimento'], vl, f, ms)
        if g is None or g.isNull():
            g = avaliar(ex['linha'], vl, f, ms)
        return g
    return avaliar(ex['linha'], vl, f, ms)


# Linhas de teste (EPSG:4326), perto de Brasília.
LINHA_COMUM = [(-47.95, -15.80), (-47.85, -15.83), (-47.76, -15.80)]   # ~20,8 km, com dobra
LINHA_CURTA = [(-47.95, -15.80), (-47.9491, -15.80)]                  # ~0,10 km
LINHA_LONGA = [(-49.50, -15.00), (-47.70, -15.40), (-46.50, -15.10)]  # ~330 km


class TestParse(unittest.TestCase):
    """Toda expressão composta parseia, e rápido (o QGIS reparseia a cada desenho)."""

    def test_parse(self):
        exprs = {}
        for c in et.CATALOGO_LINHA:
            for k, v in et.expr_linha_coordenacao(c).items():
                if v:
                    exprs['{}_{}'.format(c, k)] = v
        exprs['limite_linhas'] = et.expr_limite_linhas()
        exprs['limite_circulos'] = et.expr_limite_circulos()
        for norte in (False, True):
            for lado in ('top', 'bottom'):
                for k, v in et.expr_limite_rotulo(lado, norte).items():
                    exprs['rotulo_{}_{}_{}'.format(lado, norte, k)] = v
        exprs['seta'] = et.expr_seta()
        exprs['frente'] = et.expr_frente_ocupada()
        exprs['largura'] = et.expr_largura_px('line_width', 4, 60)
        pior = 0
        for nome, txt in exprs.items():
            t = time.perf_counter()
            e = QgsExpression(txt)
            dt = time.perf_counter() - t
            pior = max(pior, dt)
            self.assertFalse(e.hasParserError(), '{}: {}'.format(nome, e.parserErrorString()))
            self.assertLess(dt, 0.5, nome)
        medir('parse: {} expressões, a mais lenta em {:.1f} ms'.format(len(exprs), pior * 1000))


class TestLinhaCoordenacao(unittest.TestCase):

    def _caso(self, codigo, coords, size, spacing):
        vl, f = nova_feicao('coordination_line', coords, symbol_code=codigo,
                            symbol_size_km=size, symbol_spacing_km=spacing)
        eixo = eixo_de_referencia(vl, f)
        g = geometria_linha_coordenacao(codigo, vl, f)
        L = comprimento_km(coords)
        sim = et.CATALOGO_LINHA[codigo]
        s, e = web_tamanhos_linha(size, spacing)
        if sim.get('continuo'):
            esperado, passo = web_layout_continuo(L, s)
        else:
            esperado, passo = web_layout_glifos(L, s * sim['span'], e)
        obtido = contar_glifos(codigo, g, eixo)
        puro = contar_glifos(codigo, avaliar('$geometry', vl, f), eixo)
        return dict(vl=vl, f=f, g=g, eixo=eixo, L=L, esperado=esperado, obtido=obtido, puro=puro, passo=passo)

    def test_contagem_tres_casos(self):
        for codigo, sim in CATALOGO_GLIFOS.items():
            for nome, coords in (('comum', LINHA_COMUM), ('curta', LINHA_CURTA), ('longa', LINHA_LONGA)):
                with self.subTest(codigo=codigo, caso=nome):
                    r = self._caso(codigo, coords, 0.5, 1.5)
                    self.assertEqual(r['obtido'], r['esperado'])
                    if nome == 'curta':
                        self.assertEqual(r['esperado'], 0)
                        # sem glifo, só o eixo cru
                        self.assertEqual(len(partes(r['g'])), 1)
                    elif nome == 'longa':
                        self.assertEqual(r['esperado'], 120)
                    else:
                        self.assertGreater(r['esperado'], 5)
                    if r['esperado'] > 0:
                        # (c) pior caso: a linha pura reprova a mesma régua
                        self.assertNotEqual(r['puro'], r['esperado'])
                    medir('{} {}: L={:.2f} km, Web={} QGIS={} linha pura={}'.format(
                        codigo, nome, r['L'], r['esperado'], r['obtido'], r['puro']))

    def test_eixo_interrompido_tem_vaos(self):
        for codigo, sim in CATALOGO_GLIFOS.items():
            if sim.get('continuo'):
                continue
            with self.subTest(codigo=codigo):
                r = self._caso(codigo, LINHA_COMUM, 0.5, 1.5)
                no_eixo = [p for p in partes(r['g']) if not fora_do_eixo(p, r['eixo'])]
                coberto = comprimento_partes_km(no_eixo)
                if sim['interrompe']:
                    # o eixo perde exatamente um glifo por glifo (span 1)
                    esperado = r['L'] - r['esperado'] * 0.5 * sim['span']
                    self.assertAlmostEqual(coberto, esperado, delta=0.005)
                else:
                    # o eixo segue inteiro sob o glifo (o traço a 0 grau do asterisco
                    # também fica sobre o eixo e é descontado)
                    self.assertGreaterEqual(coberto, r['L'] - 0.005)
                puro_coberto = comprimento_partes_km(partes(avaliar('$geometry', r['vl'], r['f'])))
                if sim['interrompe']:
                    self.assertNotAlmostEqual(puro_coberto, esperado, delta=0.005)

    def test_periodo_continuos(self):
        for codigo in ('290202', '290999-01', '290999-02'):
            with self.subTest(codigo=codigo):
                r = self._caso(codigo, LINHA_COMUM, 0.5, 1.5)
                dentes = partes(r['g'])
                # início de cada dente medido ao longo do eixo
                inicios = sorted(r['eixo'].lineLocatePoint(QgsGeometry.fromPointXY(QgsPointXY(*d[0])))
                                 for d in dentes)
                eixo_m = sum(hav_m(LINHA_COMUM[i], LINHA_COMUM[i + 1]) for i in range(2))
                comp_graus = r['eixo'].length()
                passos = [(inicios[i + 1] - inicios[i]) / comp_graus * eixo_m for i in range(len(inicios) - 1)]
                esperado_m = r['passo'] * 1000
                desvio = max(abs(p - esperado_m) for p in passos)
                self.assertLess(desvio, 0.01 * esperado_m)
                medir('{} período: Web {:.1f} m, QGIS {:.1f} a {:.1f} m'.format(
                    codigo, esperado_m, min(passos), max(passos)))

    def test_zoom_preso_a_tela(self):
        """zoom_corr falso: o tamanho em km cai por 2^(z0 - z); verdadeiro: não muda."""
        z0 = 13.0
        for corr, fator in ((False, 0.5), (True, 1.0)):
            with self.subTest(zoom_corr=corr):
                vl, f = nova_feicao('coordination_line', LINHA_COMUM, symbol_code='290199', symbol_size_km=0.5,
                                    symbol_spacing_km=1.5, zoom_corr=corr, created_zoom=z0)
                ms = mapa(centro_feicao(f), escala=escala_do_zoom(z0 + 1))
                g = geometria_linha_coordenacao('290199', vl, f, ms)
                s, e = web_tamanhos_linha(0.5, 1.5, fator)
                esperado, _ = web_layout_glifos(comprimento_km(LINHA_COMUM), s, e)
                self.assertEqual(contar_glifos('290199', g, eixo_de_referencia(vl, f)), esperado)
                losangos = [p for p in partes(g) if len(p) == 5]
                diag = hav_m(losangos[0][0], losangos[0][2])
                self.assertAlmostEqual(diag, s * 1000, delta=0.01 * s * 1000)
                medir('290199 zoom_corr={} em z0+1: {} glifos, diagonal {:.1f} m (Web {:.1f} m)'.format(
                    corr, esperado, diag, s * 1000))

    def test_camada_em_outro_src(self):
        """@layer_crs no lugar de 'EPSG:4326': a mesma linha numa camada UTM dá o mesmo desenho."""
        vl4, f4 = nova_feicao('coordination_line', LINHA_COMUM, symbol_code='290199',
                              symbol_size_km=0.5, symbol_spacing_km=1.5)
        g4 = geometria_linha_coordenacao('290199', vl4, f4)
        utm = QgsCoordinateReferenceSystem('EPSG:31983')
        tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), utm, QgsProject.instance())
        vlu = QgsVectorLayer('LineString?crs=EPSG:31983&field=symbol_code:string&field=symbol_size_km:double'
                             '&field=symbol_spacing_km:double&field=zoom_corr:integer&field=created_zoom:double',
                             'utm', 'memory')
        fu = QgsFeature(vlu.fields())
        gu = QgsGeometry(f4.geometry())
        gu.transform(tr)
        fu.setGeometry(gu)
        fu.setAttributes(['290199', 0.5, 1.5, 1, None])
        g = geometria_linha_coordenacao('290199', vlu, fu, mapa(centro_feicao(f4)))
        g.transform(tr, Qgis.TransformDirection.Reverse)
        pa, pb = partes(g4), partes(g)
        self.assertEqual(len(pa), len(pb))
        desvio = max(hav_m(a, b) for x, y in zip(pa, pb) for a, b in zip(x, y))
        self.assertLess(desvio, 0.05)
        medir('camada em EPSG:31983: {} partes, desvio máximo {:.4f} m contra a camada em 4326'.format(
            len(pb), desvio))

    def test_largura_independe_do_src_do_mapa(self):
        """O traço preso ao terreno sai com os mesmos mm em mapa Mercator, UTM e geográfico."""
        z0 = 13.0
        vl, f = nova_feicao('coordination_line', LINHA_COMUM, zoom_corr=True, created_zoom=z0, line_width=4)
        c = centro_feicao(f)
        s_merc = escala_do_zoom(z0 + 1)
        s_terreno = s_merc * math.cos(math.radians(c[1]))
        larguras = {}
        for crs, escala in (('EPSG:3857', s_merc), ('EPSG:31983', s_terreno), ('EPSG:4326', s_terreno)):
            ms = mapa(c, escala=escala, crs=crs)
            larguras[crs] = avaliar(et.expr_largura_px('line_width', 4, 60), vl, f, ms)
        for crs, mm in larguras.items():
            self.assertAlmostEqual(mm, 8 * MM_POR_PX, delta=0.01 * 8 * MM_POR_PX, msg=crs)
        medir('traço preso ao terreno, 4 px em z0+1: ' + ', '.join(
            '{} {:.4f} mm'.format(k, v) for k, v in larguras.items()) + ' (esperado {:.4f})'.format(8 * MM_POR_PX))

    def test_largura_traco(self):
        z0 = 13.0
        casos = [(True, z0 + 1, 4 * 2), (False, z0 + 1, 4), (True, z0 + 5, 60), (True, None, 4)]
        for corr, z, px in casos:
            with self.subTest(zoom_corr=corr, z=z):
                vl, f = nova_feicao('coordination_line', LINHA_COMUM, zoom_corr=corr,
                                    created_zoom=z0 if z else None, line_width=4)
                ms = mapa(centro_feicao(f), escala=escala_do_zoom(z or 14))
                mm = avaliar(et.expr_largura_px('line_width', 4, 60), vl, f, ms)
                self.assertAlmostEqual(mm, px * MM_POR_PX, places=4)
        medir('largura: 4 px criado em z13 vale {:.3f} mm em z14 (corr), {:.3f} mm (sem corr), teto 60 px'
              .format(8 * MM_POR_PX, 4 * MM_POR_PX))


class TestLimite(unittest.TestCase):

    def _limite(self, coords, **attrs):
        vl, f = nova_feicao('boundary', coords, **attrs)
        return vl, f, avaliar(et.expr_limite_linhas(), vl, f), avaliar(et.expr_limite_circulos(), vl, f)

    def test_vaos_glifos_e_teto(self):
        reta = [(-47.95, -15.80), (-47.76, -15.80)]       # ~20,3 km
        L = comprimento_km(reta)
        vl, f, g, c = self._limite(reta, echelon='XX', symbol_size_km=1.0,
                                   symbol_instances='[{"ratio": 0.3, "showLabels": true}, {"ratio": 0.7}]')
        ps = partes(g)
        eixo = eixo_de_referencia(vl, f)
        no_eixo = [p for p in ps if not fora_do_eixo(p, eixo)]
        tracos = [p for p in ps if fora_do_eixo(p, eixo)]
        self.assertEqual(len(no_eixo), 3)                  # dois vãos
        self.assertEqual(len(tracos), 2 * 2 * 2)           # 2 instâncias x 2 X x 2 retas
        vao = 2 * 1.0 * 1.5 * 1.2
        self.assertAlmostEqual(comprimento_partes_km(no_eixo), L - 2 * vao, delta=0.005)
        for t in tracos:
            self.assertAlmostEqual(hav_m(t[0], t[1]), 1000, delta=5)
        self.assertTrue(c is None or c.isNull())
        # (c) a linha pura reprova: uma parte só, sem vão
        self.assertEqual(len(partes(avaliar('$geometry', vl, f))), 1)
        medir('Limite comum: L={:.2f} km, 3 trechos (Web 3), 8 traços de {:.0f} m (Web 1000 m)'.format(
            L, hav_m(tracos[0][0], tracos[0][1])))

        # teto do tamanho: linha de 2 km, 'XXX', 1 instância -> L x 0,5 / (1 x 3 x 1,8)
        curta = [(-47.95, -15.80), (-47.9313, -15.80)]
        Lc = comprimento_km(curta)
        vl, f, g, c = self._limite(curta, echelon='XXX', symbol_size_km=1.0)
        teto = Lc * 0.5 / (1 * 3 * 1.8)
        eixo = eixo_de_referencia(vl, f)
        tracos = [p for p in partes(g) if fora_do_eixo(p, eixo)]
        self.assertEqual(len(tracos), 6)
        self.assertAlmostEqual(hav_m(tracos[0][0], tracos[0][1]) / 1000, teto, delta=0.002)
        no_eixo = [p for p in partes(g) if not fora_do_eixo(p, eixo)]
        self.assertAlmostEqual(comprimento_partes_km(no_eixo), Lc * 0.5, delta=0.003)
        medir('Limite curta: L={:.2f} km, tamanho efetivo {:.0f} m (teto do Web {:.0f} m)'.format(
            Lc, hav_m(tracos[0][0], tracos[0][1]), teto * 1000))

        # vãos sobrepostos se fundem; 'oII' dá 1 círculo e 2 traços I por instância
        vl, f, g, c = self._limite(reta, echelon='oII', symbol_size_km=0.5,
                                   symbol_instances='[{"ratio": 0.5}, {"ratio": 0.52}]')
        eixo = eixo_de_referencia(vl, f)
        no_eixo = [p for p in partes(g) if not fora_do_eixo(p, eixo)]
        self.assertEqual(len(no_eixo), 2)
        self.assertEqual(len(partes(c)), 2)
        self.assertEqual(len([p for p in partes(g) if fora_do_eixo(p, eixo)]), 4)
        raio = hav_m(centro_partes(partes(c)[0]), partes(c)[0][0])
        self.assertAlmostEqual(raio, 500 / 4, delta=1)

    def test_escalao_so_de_circulos(self):
        """
        K2: 'o', 'oo' e 'ooo' não têm traço, e o eixo com os vãos tem de sair assim mesmo. Antes, a
        instância sem traço dava a geometria nula, o collect do eixo com ela dava nulo, e o Limite
        não desenhava eixo nenhum no QGIS (só os círculos) nem ia ao .ebgeo com o vão.
        """
        reta = [(-47.95, -15.80), (-47.76, -15.80)]
        L = comprimento_km(reta)
        for ech in ('o', 'oo', 'ooo'):
            with self.subTest(ech=ech):
                vl, f, g, c = self._limite(reta, echelon=ech, symbol_size_km=1.0,
                                           symbol_instances='[{"ratio": 0.3}, {"ratio": 0.7}]')
                self.assertTrue(g is not None and not g.isNull(), ech)
                eixo = eixo_de_referencia(vl, f)
                no_eixo = [p for p in partes(g) if not fora_do_eixo(p, eixo)]
                self.assertEqual(len(no_eixo), 3)                      # dois vãos
                self.assertEqual(len(partes(g)), 3)                    # e nenhum traço
                s = min(1.0, L * 0.5 / (2 * len(ech) * 1.8))          # teto do tamanho (maxSymbolSizeForLine)
                vao = len(ech) * s * 1.5 * 1.2
                self.assertAlmostEqual(comprimento_partes_km(no_eixo), L - 2 * vao, delta=0.005)
                self.assertEqual(len(partes(c)), 2 * len(ech))

    def test_rotulos(self):
        reta = [(-47.95, -15.80), (-47.76, -15.80)]       # rumo 90 (leste)
        vl, f = nova_feicao('boundary', reta, echelon='XX', symbol_size_km=1.0, text_top='NORTE',
                            text_bottom='SUL', symbol_instances='[{"ratio": 0.5}, {"ratio": 0.8, "showLabels": false}]')
        topo = partes(avaliar(et.expr_limite_rotulo('top', True)['geometria'], vl, f))
        base = partes(avaliar(et.expr_limite_rotulo('bottom', True)['geometria'], vl, f))
        self.assertEqual(len(topo), 1)                     # a 2a instância não mostra rótulo
        # Web: centro pelo grande círculo (turf.along), rumo local, rótulo a 900 m à esquerda
        centro = destino(reta[0], hav_m(*reta) / 2, rumo(reta[0], reta[1]))
        esperado_topo = destino(centro, 1000 * 0.9, rumo(centro, reta[1]) - 90)
        self.assertLess(hav_m(topo[0][0], esperado_topo), 2)
        self.assertGreater(topo[0][0][1], -15.80)
        self.assertLess(base[0][0][1], -15.80)
        quad = avaliar(et.expr_limite_rotulo('top', True)['quadrante'], vl, f)
        self.assertEqual(quad, 1)                          # rótulo ao norte: ancorado embaixo ("Above")
        seg = partes(avaliar(et.expr_limite_rotulo('top', False)['geometria'], vl, f))
        self.assertEqual(len(seg), 1)
        meio = ((seg[0][0][0] + seg[0][1][0]) / 2, (seg[0][0][1] + seg[0][1][1]) / 2)
        self.assertLess(hav_m(meio, esperado_topo), 2)
        medir('Rótulo text_top: a {:.2f} m do ponto do Web (tamanho x 0,9 a norte do centro)'.format(
            hav_m(topo[0][0], esperado_topo)))


def centro_partes(anel):
    xs = [p[0] for p in anel[:-1]]
    ys = [p[1] for p in anel[:-1]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def area_m2(g):
    """Área na esfera do turf, por projeção local de área igual."""
    c = g.centroid().asPoint()
    crs = QgsCoordinateReferenceSystem('PROJ:+proj=laea +lat_0={} +lon_0={} +R={} +units=m'.format(c.y(), c.x(), R_TURF))
    g2 = QgsGeometry(g)
    g2.transform(QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance()))
    return g2.area()


class TestSeta(unittest.TestCase):

    def test_area_ponta_e_variantes(self):
        reta = [(-47.95, -15.80), (-47.85, -15.80)]
        L = hav_m(*reta)
        w = 500.0
        hb, hl = 2.5 * w, 2.5 * w * 1.5
        vl, f = nova_feicao('arrow', reta, width_m=w)
        g = avaliar(et.expr_seta(), vl, f)
        esperado = L * w + hb * hl / 2
        self.assertAlmostEqual(area_m2(g), esperado, delta=0.003 * esperado)
        ponta = max(partes(g)[0], key=lambda p: p[0])
        self.assertAlmostEqual(hav_m(reta[1], ponta), hl, delta=2)
        medir('Seta simples: área {:.0f} m2 (Web {:.0f}), ponta a {:.1f} m (Web {:.1f})'.format(
            area_m2(g), esperado, hav_m(reta[1], ponta), hl))

        # (c) a linha pura não tem área
        self.assertEqual(QgsGeometry(avaliar('$geometry', vl, f)).area(), 0)

        # ponta dupla em eixo curto: as duas pontas somadas não passam do eixo
        curta = [(-47.95, -15.80), (-47.922, -15.80)]
        Lc = hav_m(*curta)
        vl, f = nova_feicao('arrow', curta, width_m=w, double_headed=True)
        g = avaliar(et.expr_seta(), vl, f)
        hl2 = Lc / 2                                        # 2 x 1875 > Lc
        esperado = Lc * w + 2 * hb * hl2 / 2
        self.assertAlmostEqual(area_m2(g), esperado, delta=0.003 * esperado)

        # aeromóvel: dois polígonos
        vl, f = nova_feicao('arrow', reta, width_m=w, airmobile=True)
        g = avaliar(et.expr_seta(), vl, f)
        self.assertEqual(len(partes(g)), 2)

        # seta combinada: dois ramos unidos num polígono só
        vl, f = nova_feicao('arrow', [reta, [(-47.95, -15.85), (-47.88, -15.82), (-47.85, -15.80)]], width_m=w)
        g = avaliar(et.expr_seta(), vl, f)
        self.assertEqual(len(partes(g)), 1)


class TestFrenteOcupada(unittest.TestCase):

    def test_bracos(self):
        p1, p2 = (-47.95, -15.80), (-47.90, -15.75)
        p3 = destino(p1, hav_m(p1, p2), 45 + 50)
        vl, f = nova_feicao('occupied_front', [p1, p2, p3])
        g = avaliar(et.expr_frente_ocupada(), vl, f)
        ps = partes(g)
        self.assertEqual(len(ps), 10)
        d = hav_m(p1, p2)
        self.assertAlmostEqual(hav_m(ps[0][0], ps[0][1]), 0.6 * d, delta=0.002 * d)
        self.assertAlmostEqual(hav_m(ps[1][0], ps[1][1]), 0.1 * d, delta=0.002 * d)
        self.assertAlmostEqual(hav_m(ps[3][0], ps[3][1]), 0.1 * d, delta=0.002 * d)
        self.assertEqual(len(partes(avaliar('$geometry', vl, f))), 1)


# ---------------------------------------------------------------------------
# Comparação com o código do Web em node
# ---------------------------------------------------------------------------

NODE_HARNESS = r'''
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
const [frontend, entrada, saida] = process.argv.slice(2);
const js = join(frontend, 'src', 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-web-'));
const stub = join(dir, 'tools.mjs');
writeFileSync(stub, `export { default as BaseGeometry } from ${JSON.stringify(pathToFileURL(join(js, 'tool_manager', 'base_geometry.js')).href)};\n`);
const hooks = join(dir, 'hooks.mjs');
const mapa = { '@tools/helpers/': join(js, 'tool_manager', 'helpers'), '@utils/': join(js, 'utilities'), '@layers/': join(js, 'layers') };
writeFileSync(hooks, `
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const STUB = ${JSON.stringify(pathToFileURL(stub).href)};
const MAPA = ${JSON.stringify(mapa)};
export async function resolve(spec, ctx, next) {
  if (spec === '@tools') return { url: STUB, shortCircuit: true };
  for (const [p, d] of Object.entries(MAPA)) {
    if (spec.startsWith(p)) return { url: pathToFileURL(join(d, spec.slice(p.length))).href, shortCircuit: true };
  }
  return next(spec, ctx);
}
`);
register(pathToFileURL(hooks).href);
const req = createRequire(join(frontend, 'package.json'));
const turfMod = await import(pathToFileURL(req.resolve('@turf/turf')).href);
globalThis.turf = { ...(turfMod.default ?? turfMod) };
const imp = (p) => import(pathToFileURL(join(js, ...p.split('/'))).href).then((m) => m.default);
const CL = await imp('military_tools/coordination_line_tool/add_coordination_line_geometry.js');
const BD = await imp('military_tools/boundary_tool/add_boundary_geometry.js');
const AR = await imp('military_tools/arrow_tool/add_arrow_geometry.js');
const OF = await imp('military_tools/occupied_front_tool/add_occupied_front_geometry.js');
const cl = new CL(), bd = new BD(), ar = new AR(), of = new OF();
const casos = JSON.parse(readFileSync(entrada, 'utf8'));
const out = casos.map((c) => {
  const p = { ...c.props, baseCoordinates: c.coords };
  if (c.tipo === 'coordination_line') return { geom: cl.generate(p, c.zoom), layout: cl.describeLayout(p, c.zoom) };
  if (c.tipo === 'boundary') {
    const f = { properties: { id: 'x', ...p } };
    return { geom: bd.generate(p, c.zoom), circulos: bd.generateBoundaryCircles(f, c.zoom).map((x) => x.geometry),
             textos: bd.generateBoundaryTexts(f, c.zoom, 0).map((x) => ({ coords: x.geometry.coordinates, text: x.properties.text })) };
  }
  if (c.tipo === 'arrow') return { geom: ar.generate(c.coords, c.props) };
  if (c.tipo === 'occupied_front') return { geom: of.generate(c.coords) };
  return null;
});
writeFileSync(saida, JSON.stringify(out));
'''


def rodar_web(casos):
    web = os.environ.get('EBGEO_WEB_DIR')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    if not web:
        return None, 'EBGEO_WEB_DIR ausente'
    if not node:
        return None, 'node fora do PATH do Python do QGIS (defina EBGEO_NODE)'
    frontend = os.path.join(web, 'frontend')
    d = tempfile.mkdtemp(prefix='ebgeo_node_')
    script = os.path.join(d, 'web_geom.mjs')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    entrada, saida = os.path.join(d, 'in.json'), os.path.join(d, 'out.json')
    with open(entrada, 'w', encoding='utf-8') as fh:
        json.dump(casos, fh)
    r = subprocess.run([node, script, frontend, entrada, saida], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-2000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh), None


def partes_geojson(g):
    if g is None:
        return []
    t, c = g['type'], g['coordinates']
    if t == 'LineString':
        return [[tuple(p[:2]) for p in c]]
    if t == 'MultiLineString':
        return [[tuple(p[:2]) for p in l] for l in c]
    if t == 'Polygon':
        return [[tuple(p[:2]) for p in c[0]]]
    if t == 'MultiPolygon':
        return [[tuple(p[:2]) for p in pol[0]] for pol in c]
    return []


def hausdorff_m(a, b):
    """Hausdorff entre duas polilinhas em metros (projeção local esférica)."""
    lat = a[0][1]
    lon = a[0][0]
    crs = QgsCoordinateReferenceSystem('PROJ:+proj=tmerc +lat_0={} +lon_0={} +R={} +units=m'.format(lat, lon, R_TURF))
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())

    def geo(p):
        if len(p) == 1:
            return QgsGeometry.fromPointXY(QgsPointXY(*p[0]))
        g = QgsGeometry.fromPolylineXY([QgsPointXY(*v) for v in p])
        return g
    ga, gb = geo(a), geo(b)
    ga.transform(tr)
    gb.transform(tr)
    return ga.hausdorffDistance(gb)


def comparar_partes(web_partes, qgis_partes):
    """Desvio máximo (m) entre partes correspondentes, na mesma ordem."""
    if len(web_partes) != len(qgis_partes):
        return None
    return max(hausdorff_m(a, b) for a, b in zip(web_partes, qgis_partes))


class TestContraWeb(unittest.TestCase):
    """Mesma linha no código do Web (node) e na expressão do QGIS: posições comparadas."""

    @classmethod
    def setUpClass(cls):
        cls.casos, cls.feicoes = [], []
        for codigo in CATALOGO_GLIFOS:
            for nome, coords in (('comum', LINHA_COMUM), ('longa', LINHA_LONGA)):
                props = dict(symbol_code=codigo, symbol_size=0.5, symbol_spacing=1.5)
                cls.casos.append(dict(tipo='coordination_line', coords=coords, props=props))
                cls.feicoes.append(('coordination_line', codigo + ' ' + nome,
                                    nova_feicao('coordination_line', coords, symbol_code=codigo,
                                                symbol_size_km=0.5, symbol_spacing_km=1.5)))
        reta = [(-47.95, -15.80), (-47.85, -15.82), (-47.76, -15.80)]
        for ech, inst in (('XX', [{'ratio': 0.3, 'showLabels': True}, {'ratio': 0.7}]), ('oII', [{'ratio': 0.5}]),
                          ('XXXX', [{'ratio': 0.4}]), ('Ø', [{'ratio': 0.5}, {'ratio': 0.8}]),
                          ('++', [{'ratio': 0.35}])):
            props = dict(echelon=ech, symbol_size=1.0, symbol_instances=inst, text_top='A', text_bottom='B')
            cls.casos.append(dict(tipo='boundary', coords=reta, props=props))
            cls.feicoes.append(('boundary', 'limite ' + ech, nova_feicao(
                'boundary', reta, echelon=ech, symbol_size_km=1.0, symbol_instances=json.dumps(inst),
                text_top='A', text_bottom='B')))
        for nome, coords, props in (
                ('seta simples', reta, dict(width=500)),
                ('seta dupla', reta, dict(width=500, doubleHeaded=True)),
                ('seta sem ponta', reta, dict(width=500, showArrowHead=False)),
                ('seta aeromóvel', reta, dict(width=500, airmobile=True)),
                ('seta aeromóvel 2 vértices', [reta[0], reta[2]], dict(width=500, airmobile=True))):
            cls.casos.append(dict(tipo='arrow', coords=coords, props=props))
            cls.feicoes.append(('arrow', nome, nova_feicao(
                'arrow', coords, width_m=props['width'], double_headed=props.get('doubleHeaded', False),
                show_arrow_head=props.get('showArrowHead', True), airmobile=props.get('airmobile', False))))
        p1, p2 = (-47.95, -15.80), (-47.90, -15.75)
        fr = [p1, p2, destino(p1, hav_m(p1, p2), 95)]
        cls.casos.append(dict(tipo='occupied_front', coords=fr, props={}))
        cls.feicoes.append(('occupied_front', 'frente', nova_feicao('occupied_front', fr)))
        cls.web, cls.motivo = rodar_web(cls.casos)

    def setUp(self):
        if self.web is None:
            self.skipTest(self.motivo)

    def test_posicoes(self):
        for caso, (tipo, nome, (vl, f)), web in zip(self.casos, self.feicoes, self.web):
            with self.subTest(caso=nome):
                if tipo == 'coordination_line':
                    codigo = caso['props']['symbol_code']
                    g = geometria_linha_coordenacao(codigo, vl, f)
                    eixo = eixo_de_referencia(vl, f)
                    self.assertEqual(web['layout']['count'], contar_glifos(codigo, g, eixo))
                    if 'longa' in nome:
                        # Num trecho de 165 km o grande círculo do Web e a reta do mapa
                        # se afastam até ~145 m: aqui só a contagem do Web é comparada.
                        medir('Web x QGIS {}: {} glifos nos dois'.format(nome, web['layout']['count']))
                        continue
                    # 3 m: o grande círculo do Web e a reta local diferem até ~0,5 m em 10 km
                    wq = [p for p in partes(g) if fora_do_eixo(p, eixo, 3e-5)]
                    ww = [p for p in partes_geojson(web['geom']) if fora_do_eixo(p, eixo, 3e-5)]
                elif tipo == 'boundary':
                    wq = partes(avaliar(et.expr_limite_linhas(), vl, f))
                    ww = partes_geojson(web['geom'])
                    circ_q = partes(avaliar(et.expr_limite_circulos(), vl, f))
                    circ_w = [partes_geojson(c)[0] for c in web['circulos']]
                    wq, ww = wq + circ_q, ww + circ_w
                    pts = partes(avaliar(et.expr_limite_rotulo('top', True)['geometria'], vl, f)) + \
                        partes(avaliar(et.expr_limite_rotulo('bottom', True)['geometria'], vl, f))
                    textos = [[tuple(t['coords'])] for t in web['textos']]
                    textos.sort(key=lambda p: -p[0][1])
                    pts.sort(key=lambda p: -p[0][1])
                    wq, ww = wq + pts, ww + textos
                elif tipo == 'arrow':
                    wq = partes(avaliar(et.expr_seta(), vl, f))
                    ww = partes_geojson(web['geom'])
                else:
                    wq = partes(avaliar(et.expr_frente_ocupada(), vl, f))
                    ww = partes_geojson(web['geom'])
                self.assertEqual(len(wq), len(ww), 'número de partes')
                desvio = comparar_partes(ww, wq)
                medir('Web x QGIS {}: {} partes, desvio máximo {:.2f} m'.format(nome, len(wq), desvio))
                self.assertLess(desvio, LIMITE_DESVIO_M if 'longa' not in nome else 150)


# ---------------------------------------------------------------------------
# Render, persistência e desempenho
# ---------------------------------------------------------------------------

def renderizar(vl, caminho, extensao=None, escala=None, crs='EPSG:3857', tamanho=(900, 500)):
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem(crs))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    tr = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance())
    ext = tr.transformBoundingBox(extensao or vl.extent())
    ext.scale(1.2)
    ms.setExtent(ext)
    job = QgsMapRendererSequentialJob(ms)
    t = time.perf_counter()
    job.start()
    job.waitForFinished()
    dt = time.perf_counter() - t
    img = job.renderedImage()
    if caminho:
        img.save(caminho)
    return img, dt


def tinta(img):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            if QColor(img.pixel(x, y)).lightness() < 200:
                n += 1
    return n


class TestRenderPersistencia(unittest.TestCase):

    def _calco_novo(self, nome):
        caminho = os.path.join(TMP, nome + '.gpkg')
        if os.path.exists(caminho):
            os.remove(caminho)
        gpkg.criar_calco(caminho)
        return caminho

    def _popular(self, caminho, tipo, feicoes):
        vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), tipo, 'ogr')
        fs = []
        for coords, attrs in feicoes:
            f = QgsFeature(vl.fields())
            if schema.TIPOS[tipo]['geometria'] == 'MultiLineString':
                pp = coords if isinstance(coords[0][0], (list, tuple)) else [coords]
                f.setGeometry(QgsGeometry.fromMultiPolylineXY([[QgsPointXY(*p) for p in parte] for parte in pp]))
            else:
                f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in coords]))
            valores = dict(schema.padroes(tipo))
            valores.update(attrs)
            for k, v in valores.items():
                f[k] = v
            fs.append(f)
        self.assertTrue(vl.dataProvider().addFeatures(fs)[0])
        vl.updateExtents()
        return QgsVectorLayer(gpkg.uri_camada(caminho, tipo), tipo, 'ogr')

    def test_render_13_tipos(self):
        """(d) Um PNG por símbolo e tipo, e cada um com mais tinta que a linha pura."""
        linha = [(-47.95, -15.80), (-47.90, -15.815), (-47.85, -15.80)]   # ~10,9 km
        for codigo in et.CATALOGO_LINHA:
            with self.subTest(codigo=codigo):
                caminho = self._calco_novo('r_' + codigo)
                vl = self._popular(caminho, 'coordination_line', [
                    (linha, dict(symbol_code=codigo, symbol_size_km=0.5, symbol_spacing_km=1.5, color='#c00000')),
                    ([(x, y - 0.03) for x, y in linha],
                     dict(symbol_code=codigo, symbol_size_km=0.3, symbol_spacing_km=1.0, line_width=2)),
                ])
                pura, _ = renderizar(vl, None)
                et.aplicar_estilo(vl, 'coordination_line')
                img, _ = renderizar(vl, os.path.join(SAIDA, 'linha_coordenacao_{}.png'.format(codigo)))
                self.assertGreater(tinta(img), tinta(pura))

        caminho = self._calco_novo('r_limite')
        reta = [(-47.95, -15.80), (-47.85, -15.82), (-47.76, -15.80)]
        vl = self._popular(caminho, 'boundary', [
            (reta, dict(echelon='XX', symbol_size_km=0.8, text_top='1ª DE', text_bottom='2ª DE',
                        symbol_instances='[{"ratio": 0.3, "showLabels": true}, {"ratio": 0.75, "showLabels": true}]')),
            ([(x, y - 0.06) for x, y in reta][::-1], dict(echelon='oII', symbol_size_km=0.8, text_top='OESTE',
                                                          text_bottom='LESTE', color='#0000c0')),
            ([(x, y - 0.12) for x, y in reta], dict(echelon='XXX', symbol_size_km=0.8, text_top='N1',
                                                     text_bottom='S1', text_north_facing=True)),
        ])
        pura, _ = renderizar(vl, None)
        et.aplicar_estilo(vl, 'boundary')
        img, _ = renderizar(vl, os.path.join(SAIDA, 'limite.png'), tamanho=(1000, 700))
        self.assertGreater(tinta(img), tinta(pura))

        caminho = self._calco_novo('r_seta')
        vl = self._popular(caminho, 'arrow', [
            (reta, dict(width_m=500)),
            ([(x, y - 0.05) for x, y in reta], dict(width_m=500, double_headed=True, fill_color='#c03030')),
            ([(x, y - 0.10) for x, y in reta], dict(width_m=500, airmobile=True)),
            ([[(x, y - 0.15) for x, y in reta], [(-47.95, -16.0), (-47.85, -15.97)]], dict(width_m=400)),
        ])
        pura, _ = renderizar(vl, None)
        et.aplicar_estilo(vl, 'arrow')
        img, _ = renderizar(vl, os.path.join(SAIDA, 'seta.png'), tamanho=(1000, 700))
        self.assertGreater(tinta(img), tinta(pura))

        caminho = self._calco_novo('r_frente')
        p1, p2 = (-47.95, -15.80), (-47.90, -15.76)
        vl = self._popular(caminho, 'occupied_front', [([p1, p2, destino(p1, hav_m(p1, p2), 42 + 50)], {})])
        pura, _ = renderizar(vl, None)
        et.aplicar_estilo(vl, 'occupied_front')
        img, _ = renderizar(vl, os.path.join(SAIDA, 'frente_ocupada.png'), tamanho=(700, 700))
        self.assertGreater(tinta(img), tinta(pura))
        medir('PNGs em ' + SAIDA)

    def test_persistencia(self):
        """(e) Estilo no layer_styles, reaberto num QgsVectorLayer novo, sem o plugin."""
        reta = [(-47.95, -15.80), (-47.85, -15.82), (-47.76, -15.80)]
        caminho = self._calco_novo('persistencia')
        dados = {
            'coordination_line': [(reta, dict(symbol_code='290308')), ([(x, y - 0.05) for x, y in reta],
                                                                     dict(symbol_code='290202'))],
            'boundary': [(reta, dict(echelon='XX', text_top='A', text_bottom='B'))],
            'arrow': [(reta, dict(width_m=500))],
            'occupied_front': [([reta[0], reta[1], (-47.80, -15.70)], {})],
        }
        for tipo, feicoes in dados.items():
            with self.subTest(tipo=tipo):
                vl = self._popular(caminho, tipo, feicoes)
                antes_img, _ = renderizar(vl, None)
                et.aplicar_estilo(vl, tipo)
                ok, msg = et.salvar_estilo_padrao(vl)
                self.assertTrue(ok, msg)
                img_estilo, _ = renderizar(vl, None)

                # Reabertura só com qgis.core: nada do plugin participa daqui em diante.
                novo = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), tipo + '_reaberta', 'ogr')
                r0, r1 = vl.renderer(), novo.renderer()
                self.assertEqual(type(r1), type(r0))
                if isinstance(r0, QgsRuleBasedRenderer):
                    regras0 = r0.rootRule().children()
                    regras1 = r1.rootRule().children()
                    self.assertEqual(len(regras1), len(regras0))
                    pares = [(a.symbol(), b.symbol()) for a, b in zip(regras0, regras1)]
                    self.assertEqual([b.filterExpression() for b in regras1], [a.filterExpression() for a in regras0])
                else:
                    pares = [(r0.symbol(), r1.symbol())]
                for s0, s1 in pares:
                    self.assertEqual(s1.symbolLayerCount(), s0.symbolLayerCount())
                    for i in range(s0.symbolLayerCount()):
                        self.assertEqual(s1.symbolLayer(i).layerType(), 'GeometryGenerator')
                        self.assertEqual(s1.symbolLayer(i).geometryExpression(), s0.symbolLayer(i).geometryExpression())
                if tipo == 'boundary':
                    self.assertIsInstance(novo.labeling(), QgsRuleBasedLabeling)
                    self.assertEqual(len(novo.labeling().rootRule().children()), 4)
                    self.assertTrue(novo.labelsEnabled())
                img_reaberta, _ = renderizar(novo, None)
                self.assertEqual(img_reaberta, img_estilo)
                self.assertNotEqual(antes_img, img_estilo)
        medir('persistência: 4 camadas reabertas com o mesmo renderer, expressões e imagem idêntica')

    def test_desempenho_200(self):
        """Tempo de render de 200 Linhas de Coordenação de ~20 km (medido, não decide aprovação)."""
        import random
        random.seed(1)
        caminho = self._calco_novo('desempenho')
        feicoes = []
        codigos = list(et.CATALOGO_LINHA)
        for i in range(200):
            x0, y0 = -48.5 + random.random(), -16.3 + random.random()
            linha = [(x0, y0), (x0 + 0.09, y0 + 0.03), (x0 + 0.18, y0)]
            feicoes.append((linha, dict(symbol_code=codigos[i % len(codigos)], symbol_size_km=0.5,
                                        symbol_spacing_km=1.5)))
        vl = self._popular(caminho, 'coordination_line', feicoes)
        _, t_puro = renderizar(vl, None, tamanho=(1200, 900))
        et.aplicar_estilo(vl, 'coordination_line')
        tempos = [renderizar(vl, None, tamanho=(1200, 900))[1] for _ in range(3)]
        renderizar(vl, os.path.join(SAIDA, 'desempenho_200.png'), tamanho=(1200, 900))
        so_290199 = self._calco_novo('desempenho_290199')
        vl2 = self._popular(so_290199, 'coordination_line', [(c, dict(a, symbol_code='290199')) for c, a in feicoes])
        et.aplicar_estilo(vl2, 'coordination_line')
        t2 = [renderizar(vl2, None, tamanho=(1200, 900))[1] for _ in range(3)]
        medir('desempenho: 200 linhas de ~20 km, render 1200x900: linha pura {:.2f} s; '
              '10 símbolos misturados {:.2f}/{:.2f}/{:.2f} s; só 290199 {:.2f}/{:.2f}/{:.2f} s'
              .format(t_puro, *(tempos + t2)))
        self.assertLess(min(tempos), 60)


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)


if __name__ == '__main__':
    unittest.main(verbosity=2, exit=False)
    QGS.exitQgis()
