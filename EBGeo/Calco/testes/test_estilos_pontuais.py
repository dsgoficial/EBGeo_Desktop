# -*- coding: utf-8 -*-
"""
Testes de simbolos.py e estilos_pontuais.py: assinatura recalculável por expressão, estilo
salvo no GeoPackage e desenhado por um processo SEM o código do plugin, reserva raster, aviso
de SVG velho, âncora, tamanho e regeneração por sinal.

Rodar com o Python do QGIS 4 (PowerShell):
    & 'C:\\Program Files\\QGIS 4.0.0\\bin\\python-qgis.bat' EBGeo/Calco/testes/test_estilos_pontuais.py
As imagens vão para EBGEO_TESTE_SAIDA (ou uma pasta temporária, impressa no fim).
"""
import base64
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(os.path.dirname(AQUI))  # .../EBGeo
if PACOTE not in sys.path:
    sys.path.insert(0, PACOTE)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsExpression, QgsExpressionContext,
    QgsExpressionContextScope, QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsMapRendererCustomPainterJob,
    QgsMapSettings, QgsPointXY, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage, QPainter  # noqa: E402
from qgis.PyQt.QtSvg import QSvgRenderer  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], False)
    _APP.initQgis()

from Calco import estilos_pontuais, gpkg, schema, simbolos  # noqa: E402
from osgeo import ogr  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo-estilos-')
os.makedirs(SAIDA, exist_ok=True)

LON0, LAT0 = -47.88, -15.79
INFANTARIA = '10031000161211000000'
PC = '10031002161211000000'  # posto de comando: âncora no pé do mastro


def ext(entidade=0, comando=False, especial=0, m1=0, m2=0):
    v = (entidade << 14) | (int(bool(comando)) << 13) | (especial << 10) | (m1 << 5) | m2
    return '076' + str(v).zfill(7)


def camada(caminho, tipo):
    lyr = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), tipo, 'ogr')
    assert lyr.isValid(), tipo
    return lyr


def adicionar(lyr, tipo, lista, renderizar=True):
    """lista: [(lon, lat, atributos)]. Preenche padrões do esquema e, se pedido, o desenho."""
    lyr.startEditing()
    padroes = schema.padroes(tipo)
    for lon, lat, atr in lista:
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
        valores = dict(padroes)
        valores.update(atr)
        if renderizar and 'svg' not in atr:
            valores.update(simbolos.renderizar(tipo, valores))
        for k, v in valores.items():
            if k in ('grupos', 'atributos', 'props', 'parametros'):
                continue
            f[k] = v
        assert lyr.addFeature(f)
    assert lyr.commitChanges(), lyr.commitErrors()


def png_b64_de_svg(svg, largura, altura):
    img = QImage(QSize(int(largura), int(altura)), QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    QSvgRenderer(QByteArray(svg.encode('utf-8'))).render(p, QRectF(0, 0, largura, altura))
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    return base64.b64encode(bytes(buf.data())).decode('ascii')


def contexto(lyr, feicao=None, escala=None):
    ctx = QgsExpressionContext()
    ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(lyr))
    if escala is not None:
        # escala de TERRENO pedida; o mapa simulado é EPSG:3857, cujo @map_scale vale a escala
        # de terreno dividida por cos(lat), como o QGIS calcula (ver _escala_terreno.exp)
        lat = LAT0
        if feicao is not None and not feicao.geometry().isNull():
            lat = feicao.geometry().centroid().asPoint().y()
        s = QgsExpressionContextScope()
        s.setVariable('map_scale', escala / math.cos(math.radians(lat)))
        s.setVariable('map_crs', 'EPSG:3857')
        s.setVariable('map_units', 'meters')
        ctx.appendScope(s)
    if feicao is not None:
        ctx.setFeature(feicao)
        ctx.setGeometry(feicao.geometry())
    return ctx


def render(camadas, centro, largura_m=3000, tamanho=(1000, 700), dpi=96, arquivo=None):
    ms = QgsMapSettings()
    ms.setLayers(camadas)
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(*tamanho))
    ms.setOutputDpi(dpi)
    ms.setBackgroundColor(QColor(255, 255, 255))
    from qgis.core import QgsCoordinateTransform, QgsProject
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), QgsCoordinateReferenceSystem('EPSG:3857'),
                                QgsProject.instance())
    c = tr.transform(QgsPointXY(*centro))
    alt = largura_m * tamanho[1] / tamanho[0]
    ms.setExtent(QgsRectangle(c.x() - largura_m / 2, c.y() - alt / 2, c.x() + largura_m / 2, c.y() + alt / 2))
    img = QImage(QSize(*tamanho), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start()
    job.waitForFinished()
    p.end()
    if arquivo:
        img.save(arquivo)

    def pixel(lon, lat):
        q = ms.mapToPixel().transform(tr.transform(QgsPointXY(lon, lat)))
        return q.x(), q.y()
    return img, pixel


def tinta(img, cx, cy, raio):
    n = vermelho = 0
    for y in range(max(0, int(cy - raio)), min(img.height(), int(cy + raio))):
        for x in range(max(0, int(cx - raio)), min(img.width(), int(cx + raio))):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                n += 1
                if c.red() > 180 and c.green() < 60 and c.blue() < 60:
                    vermelho += 1
    return n, vermelho


def caixa_escura(img, cx, cy, raio, limiar=110):
    xs, ys = [], []
    for y in range(max(0, int(cy - raio)), min(img.height(), int(cy + raio))):
        for x in range(max(0, int(cx - raio)), min(img.width(), int(cx + raio))):
            c = img.pixelColor(x, y)
            if c.red() < limiar and c.green() < limiar and c.blue() < limiar:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def caixa_tinta(img, cx, cy, raio, limiar=200):
    """Caixa dos pixels com algum canal abaixo do limiar (pega o azul da declinação e o contorno)."""
    xs, ys = [], []
    for y in range(max(0, int(cy - raio)), min(img.height(), int(cy + raio))):
        for x in range(max(0, int(cx - raio)), min(img.width(), int(cx + raio))):
            c = img.pixelColor(x, y)
            if min(c.red(), c.green(), c.blue()) < limiar:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


# Script do processo SEM o plugin: abre o GeoPackage, deixa o QGIS carregar o estilo padrão
# de layer_styles e desenha. Não importa nada de Calco.
SCRIPT_SEM_PLUGIN = r'''
import sys, json
from qgis.core import (QgsApplication, QgsVectorLayer, QgsMapSettings, QgsCoordinateReferenceSystem,
    QgsMapRendererCustomPainterJob, QgsRectangle, QgsCoordinateTransform, QgsProject, QgsPointXY)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QImage, QPainter, QColor
app = QgsApplication([], False); app.initQgis()
caminho, saida, pontos = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
assert 'Calco' not in sys.modules
camadas, info = [], {}
for t in ('military_symbol', 'coordination_measure', 'magnetic_declination'):
    lyr = QgsVectorLayer(caminho + '|layername=' + t, t, 'ogr')
    r = lyr.renderer()
    tipos = []
    if r is not None and r.type() == 'RuleRenderer':
        for regra in r.rootRule().children():
            tipos += [sl.layerType() for sl in regra.symbol().symbolLayers()]
    info[t] = {'renderer': r.type() if r else None, 'camadas_simbolo': tipos, 'feicoes': lyr.featureCount()}
    camadas.append(lyr)
crs = QgsCoordinateReferenceSystem('EPSG:3857')
tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
c = tr.transform(QgsPointXY(%f, %f))
ms = QgsMapSettings(); ms.setLayers(camadas); ms.setDestinationCrs(crs); ms.setOutputSize(QSize(1000, 700))
ms.setOutputDpi(96); ms.setExtent(QgsRectangle(c.x()-1500, c.y()-1050, c.x()+1500, c.y()+1050))
img = QImage(QSize(1000, 700), QImage.Format.Format_ARGB32); img.fill(QColor(255, 255, 255))
p = QPainter(img); job = QgsMapRendererCustomPainterJob(ms, p); job.start(); job.waitForFinished(); p.end()
img.save(saida)
res = {}
for nome, (lon, lat) in pontos.items():
    q = ms.mapToPixel().transform(tr.transform(QgsPointXY(lon, lat)))
    n = v = 0
    for y in range(int(q.y()) - 45, int(q.y()) + 45):
        for x in range(int(q.x()) - 45, int(q.x()) + 45):
            if 0 <= x < 1000 and 0 <= y < 700:
                k = img.pixelColor(x, y)
                if k.red() < 250 or k.green() < 250 or k.blue() < 250:
                    n += 1
                    if k.red() > 180 and k.green() < 60 and k.blue() < 60:
                        v += 1
    res[nome] = [n, v]
print(json.dumps({'info': info, 'tinta': res}))
''' % (LON0, LAT0)


class TestAssinatura(unittest.TestCase):
    """A assinatura em Python e a expressão do estilo têm de dar o mesmo md5 em cada feição."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix='ebgeo-assinatura-')
        cls.caminho = os.path.join(cls.dir, 'calco.gpkg')
        gpkg.criar_calco(cls.caminho)
        m = [
            {'sidc': INFANTARIA},
            {'sidc': '100310001616349900000760001024', 'unique_designation': 'Ação 1', 'fill_color': '#11FF00'},
            {'sidc': INFANTARIA, 'unique_designation': '', 'higher_formation': None, 'quantity': '0'},
            {'sidc': INFANTARIA, 'engagement_bar': 'ENG:M:1', 'direction': '45', 'is_command': True},
        ]
        med = [
            {'point_code': 'ECHELON', 'echelon_code': 'ECHELON_18', 'identificacao': 'X', 'status': 'preparado'},
            {'point_code': '130500', 'numero': '0', 'fill_color': None},
            {'point_code': '130100', 'tipo': 'P|Lib', 'gdh_ini': '121400Z', 'fill_color': '#cc0000'},
        ]
        dec = [
            {'declination': -21.25, 'convergence': 0.62},
            {'declination': 0.1 + 0.2, 'convergence': 0.0, 'fill_color': '#AA0000'},
            {'declination': 1.0, 'convergence': None},
            {'declination': 1e-7, 'convergence': -12.345678901234},
        ]
        eng = [
            {'point_code': '9', 'engineering': json.dumps({'variant': 0, 'values': {'class': '80', 'order': '40'}}),
             'svg': 'eA=='},
        ]
        adicionar(camada(cls.caminho, 'military_symbol'), 'military_symbol', [(LON0, LAT0, a) for a in m], False)
        adicionar(camada(cls.caminho, 'coordination_measure'), 'coordination_measure', [(LON0, LAT0, a) for a in med], False)
        adicionar(camada(cls.caminho, 'magnetic_declination'), 'magnetic_declination', [(LON0, LAT0, a) for a in dec], False)
        adicionar(camada(cls.caminho, 'engineering_symbol'), 'engineering_symbol', [(LON0, LAT0, a) for a in eng], False)

    def test_python_igual_a_expressao(self):
        total = 0
        for tipo in simbolos.TIPOS_SVG:
            lyr = camada(self.caminho, tipo)
            expr = QgsExpression(simbolos.expressao_assinatura(tipo))
            self.assertFalse(expr.hasParserError(), expr.parserErrorString())
            for f in lyr.getFeatures():
                atributos = {n: f[n] for n in f.fields().names()}
                valor = expr.evaluate(contexto(lyr, f))
                self.assertFalse(expr.hasEvalError(), expr.evalErrorString())
                self.assertEqual(valor, simbolos.assinatura(tipo, atributos),
                                 '{} fid {}: {}'.format(tipo, f.id(), simbolos.texto_assinatura(tipo, atributos)))
                total += 1
        print('\n[assinatura] {} feições: Python e expressão iguais'.format(total))
        self.assertEqual(total, 12)

    def test_pior_caso_campo_que_desenha_muda_a_assinatura(self):
        base = {'sidc': INFANTARIA, 'unique_designation': '1'}
        a = simbolos.assinatura('military_symbol', base)
        for mudanca in ({'sidc': PC}, {'unique_designation': '2'}, {'fill_color': '#000001'},
                        {'engagement_bar': 'x'}, {'unique_designation': None}):
            self.assertNotEqual(a, simbolos.assinatura('military_symbol', dict(base, **mudanca)), mudanca)
        # Campos que NÃO desenham não mudam a assinatura.
        for mudanca in ({'nome': 'outro'}, {'size': 3.0}, {'rotation': 45.0}, {'opacity': 0.2}, {'visivel': False}):
            self.assertEqual(a, simbolos.assinatura('military_symbol', dict(base, **mudanca)), mudanca)
        # Nulo e texto vazio desenham igual e assinam igual.
        self.assertEqual(simbolos.assinatura('military_symbol', dict(base, higher_formation='')),
                         simbolos.assinatura('military_symbol', dict(base, higher_formation=None)))

    def test_props_web(self):
        p = simbolos.props_web_de_atributos('military_symbol', {
            'sidc': INFANTARIA, 'type_amplifier': 'T', 'date_time_group': 'DTG', 'is_command': 1,
            'unique_designation': None, 'size': 2, 'nome': 'n'})
        self.assertEqual(p, {'sidc': INFANTARIA, 'type': 'T', 'dateTimeGroup': 'DTG', 'isCommand': True,
                             'size': 2.0, 'nome': 'n'})
        p = simbolos.props_web_de_atributos('coordination_measure', {'point_code': 'ECHELON', 'echelon_code': 'ECHELON_16',
                                                                     'gdh_ini': 'x', 'numero_concentracao': 'HA'})
        self.assertEqual(p, {'pointCode': 'ECHELON', 'echelonCode': 'ECHELON_16', 'gdhIni': 'x', 'numeroConcentracao': 'HA'})


class TestPersistencia(unittest.TestCase):
    """Calco gravado, estilo salvo, reaberto e desenhado por um processo sem o plugin."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix='ebgeo-persistencia-')
        cls.caminho = os.path.join(cls.dir, 'calco.gpkg')
        gpkg.criar_calco(cls.caminho)
        d = 0.0045  # cerca de 480 m
        cls.pontos = {
            'infantaria': (LON0 - 2 * d, LAT0 + d),
            'pc': (LON0 - d, LAT0 + d),
            'brasileiro': (LON0, LAT0 + d),
            'texto': (LON0 + d, LAT0 + d),
            'raster': (LON0 + 2 * d, LAT0 + d),
            'sem_desenho': (LON0 - 2 * d, LAT0 - d),
            'invisivel': (LON0 - d, LAT0 - d),
            'medida': (LON0, LAT0 - d),
            'nucleo': (LON0 + d, LAT0 - d),
            'declinacao': (LON0 + 2 * d, LAT0 - d),
        }
        sem_zoom = {'zoom_corr': False}
        lyr = camada(cls.caminho, 'military_symbol')
        raster = simbolos.renderizar('military_symbol', {'sidc': INFANTARIA})
        svg_raster = simbolos.svg_de_coluna(raster['svg'])
        adicionar(lyr, 'military_symbol', [
            cls.pontos['infantaria'] + (dict(sem_zoom, nome='infantaria', sidc=INFANTARIA),),
            cls.pontos['pc'] + (dict(sem_zoom, nome='pc', sidc=PC),),
            cls.pontos['brasileiro'] + (dict(sem_zoom, nome='brasileiro', sidc='1003100016163499' + '0000' + ext(5)),),
            cls.pontos['texto'] + (dict(sem_zoom, nome='texto', sidc=INFANTARIA, unique_designation='1',
                                        higher_formation='3 BIB'),),
        ])
        # Reserva raster: sem svg, com o PNG que veio do .ebgeo.
        adicionar(lyr, 'military_symbol', [
            cls.pontos['raster'] + (dict(sem_zoom, nome='raster', sidc=INFANTARIA, svg=None,
                                         bitmap_b64=png_b64_de_svg(svg_raster, 200, 187), bitmap_mime='image/png',
                                         largura_px=raster['largura_px'], altura_px=raster['altura_px']),),
            cls.pontos['sem_desenho'] + (dict(sem_zoom, nome='sem_desenho', sidc=INFANTARIA, svg=None),),
        ], renderizar=False)
        adicionar(lyr, 'military_symbol', [
            cls.pontos['invisivel'] + (dict(sem_zoom, nome='invisivel', sidc=INFANTARIA, visivel=False),),
        ])
        estilos_pontuais.aplicar_estilo(lyr, 'military_symbol')
        cls.erro_estilo = [estilos_pontuais.salvar_estilo_padrao(lyr)]

        med = camada(cls.caminho, 'coordination_measure')
        adicionar(med, 'coordination_measure', [
            cls.pontos['medida'] + (dict(sem_zoom, point_code='130100', identificacao='ALFA'),),
            cls.pontos['nucleo'] + (dict(sem_zoom, point_code='ECHELON', echelon_code='ECHELON_16',
                                         identificacao='1 BIB', status='preparado'),),
        ])
        estilos_pontuais.aplicar_estilo(med, 'coordination_measure')
        cls.erro_estilo.append(estilos_pontuais.salvar_estilo_padrao(med))

        dec = camada(cls.caminho, 'magnetic_declination')
        adicionar(dec, 'magnetic_declination', [
            cls.pontos['declinacao'] + (dict(sem_zoom, declination=-21.3, convergence=0.6, size=0.6),),
        ])
        estilos_pontuais.aplicar_estilo(dec, 'magnetic_declination')
        cls.erro_estilo.append(estilos_pontuais.salvar_estilo_padrao(dec))

    def rodar_sem_plugin(self, arquivo):
        script = os.path.join(self.dir, 'sem_plugin.py')
        with open(script, 'w', encoding='utf-8') as f:
            f.write(SCRIPT_SEM_PLUGIN)
        # O ambiente do QGIS é herdado (PYTHONPATH do python-qgis.bat); a pasta do plugin não está
        # nele, e o script confere que Calco não foi importado.
        r = subprocess.run([sys.executable, script, self.caminho, arquivo, json.dumps(self.pontos)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_1_estilo_salvo_e_desenho_sem_plugin(self):
        self.assertEqual(self.erro_estilo, ['', '', ''])
        arquivo = os.path.join(SAIDA, 'calco_sem_plugin.png')
        r = self.rodar_sem_plugin(arquivo)
        print('\n[persistência] ' + json.dumps(r['info'], ensure_ascii=False))
        print('[persistência] tinta e vermelho por feição: ' + json.dumps(r['tinta']))
        print('[render] ' + arquivo)
        for t, info in r['info'].items():
            self.assertEqual(info['renderer'], 'RuleRenderer', t)
            self.assertEqual(info['camadas_simbolo'], ['SvgMarker', 'RasterMarker', 'EllipseMarker', 'SimpleMarker'], t)
        tinta_ = r['tinta']
        for nome in ('infantaria', 'pc', 'brasileiro', 'texto', 'medida', 'nucleo', 'declinacao'):
            self.assertGreater(tinta_[nome][0], 300, nome)
            self.assertEqual(tinta_[nome][1], 0, nome + ': aviso vermelho com assinatura certa')
        self.assertGreater(tinta_['raster'][0], 300, 'reserva raster não desenhou')
        self.assertEqual(tinta_['raster'][1], 0)
        self.assertGreater(tinta_['sem_desenho'][1], 10, 'sem svg nem bitmap: tem de aparecer o x vermelho')
        self.assertEqual(tinta_['invisivel'][0], 0, 'visivel falso desenhou')

    def test_2_pior_caso_sidc_editado_sem_plugin_acende_o_aviso(self):
        # Edita o SIDC por OGR, como faria alguém sem o plugin: o svg fica velho.
        ds = ogr.Open(self.caminho, 1)
        lyr = ds.GetLayerByName('military_symbol')
        lyr.SetAttributeFilter("nome = 'brasileiro'")
        f = lyr.GetNextFeature()
        f.SetField('sidc', PC)
        lyr.SetFeature(f)
        ds = None
        arquivo = os.path.join(SAIDA, 'calco_sem_plugin_sidc_velho.png')
        r = self.rodar_sem_plugin(arquivo)
        print('\n[aviso] tinta e vermelho depois de editar o SIDC sem regenerar: ' + json.dumps(r['tinta']['brasileiro']))
        self.assertGreater(r['tinta']['brasileiro'][1], 50)
        self.assertEqual(r['tinta']['infantaria'][1], 0)


class TestGeometriaDoDesenho(unittest.TestCase):
    """Âncora, tamanho, rotação e opacidade, medidos em pixel."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix='ebgeo-geometria-')
        cls.caminho = os.path.join(cls.dir, 'calco.gpkg')
        gpkg.criar_calco(cls.caminho)

    def _uma(self, nome, atributos, tipo='military_symbol', largura_m=600):
        caminho = os.path.join(self.dir, nome + '.gpkg')
        gpkg.criar_calco(caminho)
        lyr = camada(caminho, tipo)
        adicionar(lyr, tipo, [(LON0, LAT0, atributos)])
        lyr = camada(caminho, tipo)
        estilos_pontuais.aplicar_estilo(lyr, tipo)
        img, px = render([lyr], (LON0, LAT0), largura_m=largura_m, arquivo=os.path.join(SAIDA, nome + '.png'))
        return lyr, img, px(LON0, LAT0)

    def test_ancora_do_posto_de_comando(self):
        lyr, img, (cx, cy) = self._uma('ancora_pc', {'sidc': PC, 'zoom_corr': False})
        caixa = caixa_escura(img, cx, cy, 160)
        f = next(lyr.getFeatures())
        print('\n[âncora] ponto ({:.1f}, {:.1f}); tinta escura x {}..{} y {}..{}; largura_px {} altura_px {} '
              'ancora ({}, {})'.format(cx, cy, caixa[0], caixa[2], caixa[1], caixa[3], f['largura_px'], f['altura_px'],
                                       f['ancora_dx'], f['ancora_dy']))
        # O pé do mastro fica no ponto: tinta termina na linha do ponto, e começa na coluna dele.
        self.assertLessEqual(abs(caixa[3] - cy), 3)
        self.assertLessEqual(abs(caixa[0] - cx), 3)
        # Pior caso: sem o deslocamento, o centro do desenho cairia no ponto e o pé ficaria longe.
        dy_px = f['ancora_dy'] * estilos_pontuais.MM_POR_PX * 96 / 25.4
        self.assertGreater(abs(dy_px), 20)

    def test_ancora_com_rotacao(self):
        _lyr, img, (cx, cy) = self._uma('ancora_pc_90', {'sidc': PC, 'zoom_corr': False, 'rotation': 90.0})
        caixa = caixa_escura(img, cx, cy, 160)
        # Girado 90 graus no sentido horário em torno do pé: o mastro deita para a direita, o
        # quadro desce a partir da linha do ponto, e o pé continua no ponto (canto superior esquerdo).
        self.assertLessEqual(abs(caixa[0] - cx), 3)
        self.assertLessEqual(abs(caixa[1] - cy), 3)
        self.assertGreater(caixa[3] - cy, 30)

    def test_tamanho_em_mm(self):
        lyr, img, (cx, cy) = self._uma('tamanho_mm', {'sidc': INFANTARIA, 'zoom_corr': False, 'size': 1.0})
        f = next(lyr.getFeatures())
        caixa = caixa_escura(img, cx, cy, 200)
        largura_px = caixa[2] - caixa[0] + 1
        esperado = f['largura_px'] * estilos_pontuais.MM_POR_PX * 96 / 25.4
        print('\n[tamanho] tinta {} px, marcador {:.1f} px (largura_px {} × 0,2646 mm a 96 dpi)'.format(
            largura_px, esperado, f['largura_px']))
        # O SVG do milsymbol tem uma margem pequena em volta do quadro.
        self.assertGreater(largura_px, 0.85 * esperado)
        self.assertLessEqual(largura_px, esperado + 2)

    def test_tamanho_preso_ao_terreno(self):
        lyr = camada(self.caminho, 'military_symbol')
        adicionar(lyr, 'military_symbol', [(LON0, LAT0, {'sidc': INFANTARIA, 'size': 1.5, 'zoom_corr': True,
                                                         'created_zoom': 14.0})])
        lyr = camada(self.caminho, 'military_symbol')
        f = next(lyr.getFeatures())
        expr = QgsExpression(estilos_pontuais.expressao_largura('military_symbol'))
        m_px = estilos_pontuais.METROS_POR_PX_ZOOM0 * math.cos(math.radians(LAT0))
        # Escala em que um pixel de tela (0,2646 mm) vale um pixel do MapLibre no zoom z.
        escala = lambda z: m_px / 2 ** z / (estilos_pontuais.MM_POR_PX / 1000)  # noqa: E731
        mm14 = expr.evaluate(contexto(lyr, f, escala(14)))
        mm16 = expr.evaluate(contexto(lyr, f, escala(16)))
        mm20 = expr.evaluate(contexto(lyr, f, escala(20)))
        base = 1.5 * f['largura_px'] * estilos_pontuais.MM_POR_PX
        print('\n[zoom] largura em mm: z14 {:.2f} (esperado {:.2f}), z16 {:.2f}, z20 {:.2f} (teto {:.2f})'.format(
            mm14, base, mm16, mm20, 10 * f['largura_px'] * estilos_pontuais.MM_POR_PX))
        self.assertAlmostEqual(mm14, base, places=6)              # no zoom de criação, o tamanho do Web
        self.assertAlmostEqual(mm16, 4 * base, places=6)          # dois níveis acima, 4 vezes
        self.assertAlmostEqual(mm20, 10 * f['largura_px'] * estilos_pontuais.MM_POR_PX, places=6)  # teto do Web
        # Desligada a correção, volta ao tamanho de tela.
        f.setAttribute('zoom_corr', False)
        self.assertAlmostEqual(expr.evaluate(contexto(lyr, f, escala(20))), base, places=6)

    def test_opacidade(self):
        _l, img1, (cx, cy) = self._uma('opaco', {'sidc': INFANTARIA, 'zoom_corr': False, 'fill_color': '#000080'})
        _l, img2, _p = self._uma('translucido', {'sidc': INFANTARIA, 'zoom_corr': False, 'fill_color': '#000080',
                                                 'opacity': 0.3})
        c1 = img1.pixelColor(int(cx) + 18, int(cy))
        c2 = img2.pixelColor(int(cx) + 18, int(cy))
        print('\n[opacidade] centro opaco {} translúcido {}'.format(c1.name(), c2.name()))
        self.assertGreater(c2.red(), c1.red() + 100)


def ler_ebgeo(caminho):
    """Leitor mínimo do .ebgeo (cabeçalho EBGXOR, ZIP com XOR 0xAA): data.json e images/."""
    import io
    import zipfile
    with open(caminho, 'rb') as f:
        bruto = f.read()
    corpo = bytes(b ^ 0xAA for b in bruto[6:]) if bruto[:6] == b'EBGXOR' else bruto
    z = zipfile.ZipFile(io.BytesIO(corpo))
    return json.loads(z.read('data.json')), {n[len('images/'):]: z.read(n) for n in z.namelist()
                                             if n.startswith('images/') and not n.endswith('/')}


class TestFixture03SvgERaster(unittest.TestCase):
    """
    Critério da importação: o mesmo símbolo do .ebgeo desenhado pelo svg regenerado e só pelo
    PNG do arquivo tem de cair do MESMO tamanho e no MESMO lugar. A fixture fica no ebgeo_web
    (privado) e é lida de lá; nada dela entra neste repositório.
    """

    PREFIXOS = ['Inf Btl amigo', 'Inf Btl hostil', 'Núcleo de batalhão ocupado', 'Ponto genérico',
                'Ponto de coordenação', 'Declinação']

    @classmethod
    def setUpClass(cls):
        web = os.environ.get('EBGEO_WEB')
        arq = web and os.path.join(web, 'frontend', 'tests', 'fixtures', 'ebgeo-2.2', '03-completo-2.4.ebgeo')
        if not arq or not os.path.exists(arq):
            raise unittest.SkipTest('EBGEO_WEB sem a fixture 03-completo-2.4.ebgeo')
        dados, imagens = ler_ebgeo(arq)
        cls.casos = []
        vistos = set()
        for mapa in dados['maps'].values():
            for balde, tipo in (('military_symbols', 'military_symbol'), ('coordination_measures', 'coordination_measure'),
                                ('magnetic_declinations', 'magnetic_declination')):
                for f in mapa['features'].get(balde) or []:
                    p = f['properties']
                    alvo = next((e for e in cls.PREFIXOS if p.get('nome', '').startswith(e)), None)
                    png = imagens.get(p['id'] + '.png')
                    if alvo and alvo not in vistos and png:
                        vistos.add(alvo)
                        cls.casos.append((p['nome'], tipo, p, base64.b64encode(png).decode('ascii')))
        cls.dir = tempfile.mkdtemp(prefix='ebgeo-fixture03-')

    @staticmethod
    def _colunas(tipo, p):
        tipos = {c: tp for c, tp, _d, _w in schema.campos(tipo)}
        return {col: p[web] for web, col in schema.mapa_web(tipo).items()
                if web in p and tipos[col] in ('str', 'real', 'bool', 'int') and col != 'ebgeo_id'}

    def test_mesmo_tamanho_e_posicao(self):
        self.assertGreaterEqual(len(self.casos), 4, [c[0] for c in self.casos])
        mosaico, relatorio, falhas, antigos = [], [], [], []
        for k, (nome, tipo, p, png) in enumerate(self.casos):
            img_png = QImage.fromData(base64.b64decode(png))
            atr = self._colunas(tipo, p)
            camadas = {}
            for via in ('svg', 'raster'):
                caminho = os.path.join(self.dir, '{}_{}.gpkg'.format(k, via))
                gpkg.criar_calco(caminho)
                lyr = camada(caminho, tipo)
                if via == 'svg':
                    adicionar(lyr, tipo, [(LON0, LAT0, dict(atr))])
                else:
                    col = simbolos.colunas_do_bitmap_web(tipo, p, png, img_png.width(), img_png.height())
                    adicionar(lyr, tipo, [(LON0, LAT0, dict(atr, svg=None, **col))], renderizar=False)
                lyr = camada(caminho, tipo)
                estilos_pontuais.aplicar_estilo(lyr, tipo)
                camadas[via] = lyr
            # Mapa na escala do zoom de criação, com a correção de zoom do arquivo ligada: o
            # símbolo sai no tamanho de tela que o Web dá naquele zoom.
            z = p.get('createdAtZoom') or 12
            m_px = estilos_pontuais.METROS_POR_PX_ZOOM0 * math.cos(math.radians(LAT0)) / 2 ** z
            largura_m = 900 * m_px * (25.4 / 96) / estilos_pontuais.MM_POR_PX
            res = {}
            for via, lyr in camadas.items():
                img, px = render([lyr], (LON0, LAT0), largura_m=largura_m, tamanho=(900, 700),
                                 arquivo=os.path.join(SAIDA, 'fixture03_{}_{}.png'.format(k, via)))
                cx, cy = px(LON0, LAT0)
                res[via] = (img, caixa_tinta(img, cx, cy, 440, limiar=128), cx, cy, next(lyr.getFeatures()))
            (ia, ca, cx, cy, fa), (ib, cb, _x, _y, fb) = res['svg'], res['raster']
            if tipo == 'magnetic_declination':
                # a borda direita é o fim do texto da legenda, que o QSvgRenderer escreve com a
                # fonte do Qt e o Chrome (PNG do arquivo) com a dele: setas, arcos e linha de base
                # coincidem (conferido em imagem, 2026-10-04), então a régua usa esquerda, topo e base
                dif = max(abs(ca[i] - cb[i]) for i in (0, 1, 3))
            else:
                dif = max(abs(a - b) for a, b in zip(ca, cb))
            relatorio.append('{} ({}, bitmapVersion {}): tinta svg {} raster {}; largura_px {} / {}; '
                             'âncora ({}, {}) / ({}, {}); maior diferença {} px'.format(
                                 nome, tipo, p.get('bitmapVersion'), ca, cb, fa['largura_px'], fb['largura_px'],
                                 fa['ancora_dx'], fa['ancora_dy'], fb['ancora_dx'], fb['ancora_dy'], dif))
            # PNG de desenho ANTIGO: o tamanho lógico gravado pelo Web difere do que o gerador
            # atual produz para as mesmas propriedades. O Web de hoje redesenha esse bitmap ao
            # abrir (bitmapVersion menor que 4), então a referência é o svg do motor e o PNG só
            # vale como reserva. Para o mesmo desenho, a régua é de 3 px.
            antigo = abs(fa['largura_px'] - fb['largura_px']) > 1 or abs(fa['altura_px'] - fb['altura_px']) > 1
            if antigo:
                relatorio[-1] += ' [PNG de gerador antigo: o Web redesenha]'
                antigos.append(nome)
            elif dif > 3:
                falhas.append(relatorio[-1])
            mosaico.append((ia.copy(int(cx) - 300, int(cy) - 250, 600, 500), 'svg do motor: ' + nome))
            mosaico.append((ib.copy(int(cx) - 300, int(cy) - 250, 600, 500), 'PNG do .ebgeo'))
        print('\n[fixture 03] svg regenerado contra PNG do arquivo (caixa de tinta x0, y0, x1, y1 em px):')
        for linha in relatorio:
            print('  ' + linha)
        img = QImage(QSize(1200, 500 * len(self.casos)), QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        pintor = QPainter(img)
        for i, (parte, rotulo) in enumerate(mosaico):
            x0, y0 = (i % 2) * 600, (i // 2) * 500
            pintor.drawImage(x0, y0, parte)
            pintor.setPen(QColor(255, 0, 255))  # o ponto da feição
            pintor.drawLine(x0 + 288, y0 + 250, x0 + 312, y0 + 250)
            pintor.drawLine(x0 + 300, y0 + 238, x0 + 300, y0 + 262)
            pintor.setPen(QColor(0, 0, 0))
            pintor.drawText(x0 + 6, y0 + 16, rotulo)
            pintor.drawRect(x0, y0, 599, 499)
        pintor.end()
        arq = os.path.join(SAIDA, 'fixture03_lado_a_lado.png')
        img.save(arq)
        print('[render] ' + arq)
        self.assertEqual(falhas, [])
        self.assertGreaterEqual(len(self.casos) - len(antigos), 4, 'casos com o mesmo desenho insuficientes')

    def test_pior_caso_sem_ancora_desloca(self):
        """A régua tem de reprovar o PNG militar antigo posto pelo centro (sem a âncora do motor)."""
        nome, tipo, p, png = next(c for c in self.casos if c[0].startswith('Inf Btl hostil'))
        col = simbolos.colunas_do_bitmap_web(tipo, p, png)
        svg = simbolos.renderizar(tipo, self._colunas(tipo, p))
        self.assertAlmostEqual(col['ancora_dy'], svg['ancora_dy'], delta=1.0)
        self.assertGreater(abs(svg['ancora_dy']), 3, nome + ': sem âncora o PNG ficaria deslocado')


class TestGuardiaoRedesenha(unittest.TestCase):
    """O SVG em dia pelo guardião da camada (guardiao.py), em comandos de edição e no commit."""

    def setUp(self):
        from Calco import guardiao
        self.caminho = os.path.join(tempfile.mkdtemp(prefix='ebgeo-regen-'), 'calco.gpkg')
        gpkg.criar_calco(self.caminho)
        self.lyr = camada(self.caminho, 'military_symbol')
        self.g = guardiao.Guardiao(self.lyr, 'military_symbol')

    def tearDown(self):
        self.g.desconectar()
        if self.lyr.isEditable():
            self.lyr.rollBack()

    def _nova(self, **atr):
        f = QgsFeature(self.lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(LON0, LAT0)))
        for k, v in dict(schema.padroes('military_symbol'), **atr).items():
            f[k] = v
        self.assertTrue(self.lyr.addFeature(f))
        return f.id()

    def _comando(self, acao):
        self.lyr.beginEditCommand('teste')
        r = acao()
        self.lyr.endEditCommand()
        return r

    def test_nascer_mudar_e_lote(self):
        self.lyr.startEditing()
        fid = self._comando(lambda: self._nova(sidc=INFANTARIA))
        self.assertEqual(self.g.regeneradas, 1)
        f = self.lyr.getFeature(fid)
        self.assertIsNotNone(f['svg'])
        self.assertEqual(f['svg_assinatura'], simbolos.assinatura('military_symbol', {n: f[n] for n in f.fields().names()}))
        svg1 = f['svg']

        # Mudar um amplificador redesenha; mudar o tamanho não.
        idx = self.lyr.fields().indexOf('unique_designation')
        self._comando(lambda: self.lyr.changeAttributeValue(fid, idx, '7'))
        self._comando(lambda: self.lyr.changeAttributeValue(fid, self.lyr.fields().indexOf('size'), 2.0))
        self.assertEqual(self.g.regeneradas, 2)
        f = self.lyr.getFeature(fid)
        self.assertNotEqual(f['svg'], svg1)
        self.assertIn('>7<', simbolos.svg_de_coluna(f['svg']))

        # Lote: 40 feições num comando (colar) e uma mudança em todas num comando (calculadora).
        fids = self._comando(lambda: [self._nova(sidc=INFANTARIA, unique_designation=str(k)) for k in range(40)])
        self.assertEqual(self.g.regeneradas, 42)
        self._comando(lambda: [self.lyr.changeAttributeValue(k, idx, 'L') for k in fids])
        self.assertEqual(self.g.regeneradas, 82)

        # Mexer à mão numa coluna de saída não redesenha (sem recursão).
        self._comando(lambda: self.lyr.changeAttributeValue(fid, self.lyr.fields().indexOf('svg_assinatura'), 'x'))
        self.assertEqual(self.g.regeneradas, 82)

    def test_sidc_invalido_nao_grava_e_registra(self):
        self.lyr.startEditing()
        fid = self._comando(lambda: self._nova(sidc='XXXX'))
        self.assertIsNone(self.lyr.getFeature(fid)['svg'])
        self.assertEqual(len(self.g.erros_svg), 1)

    def test_commit_desenha_o_que_entrou_fora_de_comando(self):
        self.lyr.startEditing()
        self._nova(sidc=PC)  # pela API, sem comando
        self.assertTrue(self.lyr.commitChanges())
        lyr = camada(self.caminho, 'military_symbol')
        f = next(lyr.getFeatures())
        self.assertIsNotNone(f['svg'])
        self.assertEqual(f['svg_assinatura'], simbolos.assinatura('military_symbol', {n: f[n] for n in f.fields().names()}))


if __name__ == '__main__':
    unittest.main(verbosity=2, exit=False)
    print('\nImagens em: ' + SAIDA)
