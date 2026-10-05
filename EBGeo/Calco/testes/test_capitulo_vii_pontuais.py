# -*- coding: utf-8 -*-
"""
Capítulo VII do MD33-C-01 no calco (2026-10-04), a parte pontual e a Linha de Limite: o que o
EBGeo Web ganhou e o Desktop tem de acompanhar.

- Base de fogos (152000) e Setor de Tiro (140500): direção em azimute de 1 grau, a secundária do
  setor gravada RELATIVA à principal (coluna angulo_secundario) e parada no terreno quando a
  principal gira; os dois desenham alinhados ao MAPA, também com o mapa girado.
- Indicação pontual de campo minado (270701): o tipo de cada uma das três minas (mina1..mina3).
- Área minada pontual (270800) fora do seletor, desenhando o legado.
- Destruições (271201, 271203, 271204) nascem verdes.
- Linha de Limite: escalões Ø (Equipe/Guarnição) e ++ (Valor indeterminado); XXXXX fica.
- Importador .ebgeo: as propriedades novas viram colunas e desenham.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_capitulo_vii_pontuais.py
As imagens vão para EBGEO_TESTE_SAIDA (ou uma pasta temporária, impressa no fim).
"""
import base64
import io
import json
import math
import os
import sys
import tempfile
import unittest
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(os.path.dirname(AQUI))  # .../EBGeo
if PACOTE not in sys.path:
    sys.path.insert(0, PACOTE)

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression,
    QgsExpressionContext, QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsMapRendererCustomPainterJob,
    QgsMapSettings, QgsPointXY, QgsProject, QgsProperty, QgsRectangle, QgsSymbolLayer, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QPointF, QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QTransform  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from qgis.testing.mocked import get_iface  # noqa: E402
from qgis.PyQt.QtWidgets import QComboBox, QLabel, QSpinBox  # noqa: E402

from Calco import estilos_pontuais, estilos_taticos as et, gpkg, schema, simbolos  # noqa: E402
from Calco.calco import Calco, definir_calco_ativo  # noqa: E402
from Calco.ferramentas import gravar_feicao  # noqa: E402
from Calco.importador import escritor, leitor  # noqa: E402
from Calco.motor.motor import Motor  # noqa: E402
from Calco.ui.painel import PainelCalco  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo-cap7-')
os.makedirs(SAIDA, exist_ok=True)
LON0, LAT0 = -47.88, -15.79
VERDE = '#00B04E'
R_TURF = 6371008.8


def _attrs(tipo, **extra):
    import uuid
    a = dict(schema.padroes(tipo))
    a['ebgeo_id'] = str(uuid.uuid4())
    a.update(extra)
    return a


def _reler(caminho, tipo, ebgeo_id):
    lyr = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), 'r', 'ogr')
    return next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(ebgeo_id)))


def _svg(f):
    return simbolos.svg_de_coluna(f['svg'])


# ---------------------------------------------------------------------------------------------
# Esquema e assinatura
# ---------------------------------------------------------------------------------------------

class TestEsquemaEAssinatura(unittest.TestCase):

    def test_colunas_novas_e_nomes_do_web(self):
        campos = {c[0]: c for c in schema.campos('coordination_measure')}
        for col, web, tp in (('mina1', 'mina1', 'str'), ('mina2', 'mina2', 'str'), ('mina3', 'mina3', 'str'),
                             ('angulo_secundario', 'anguloSecundario', 'real')):
            self.assertIn(col, campos)
            self.assertEqual(campos[col][1], tp, col)
            self.assertIsNone(campos[col][2], col)  # sem valor: o desenho padrão do Web
            self.assertEqual(campos[col][3], web, col)
        p = simbolos.props_web_de_atributos('coordination_measure', {
            'point_code': '140500', 'angulo_secundario': 40, 'mina1': 'ac', 'mina2': None})
        self.assertEqual(p, {'pointCode': '140500', 'anguloSecundario': 40.0, 'mina1': 'ac'})

    def test_assinatura_acompanha_minas_e_angulo(self):
        base = {'point_code': '270701'}
        a = simbolos.assinatura('coordination_measure', base)
        for mud in ({'mina1': 'ac'}, {'mina3': 'vazia'}, {'angulo_secundario': 10.0}):
            self.assertNotEqual(a, simbolos.assinatura('coordination_measure', dict(base, **mud)), mud)
        # A posição conta: ac na posição 1 não assina como ac na posição 2.
        self.assertNotEqual(simbolos.assinatura('coordination_measure', dict(base, mina1='ac')),
                            simbolos.assinatura('coordination_measure', dict(base, mina2='ac')))
        # A rotação continua fora (o QGIS gira o desenho; nada a redesenhar).
        self.assertEqual(a, simbolos.assinatura('coordination_measure', dict(base, rotation=90.0)))

    def test_feicao_antiga_assina_como_antes(self):
        """Sem minas nem ângulo, o texto da assinatura é o de antes: calco antigo sem aviso vermelho."""
        atr = {'point_code': '130100', 'tipo': 'P Lib', 'fill_color': '#cc0000'}
        antigo = ['a1', 'coordination_measure', '130100', '', 'P Lib'] + [''] * 8 + ['#cc0000']
        self.assertEqual(simbolos.texto_assinatura('coordination_measure', atr), '|'.join(antigo))

    def test_expressao_igual_ao_python_com_os_campos_novos(self):
        caminho = os.path.join(tempfile.mkdtemp(), 'assinatura.gpkg')
        gpkg.criar_calco(caminho)
        lyr = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_measure'), 'm', 'ogr')
        casos = [{'point_code': '270701', 'mina1': 'ac', 'mina3': 'vazia'},
                 {'point_code': '140500', 'angulo_secundario': -45.0},
                 {'point_code': '140500', 'angulo_secundario': 12.5, 'fill_color': '#00B04E'},
                 {'point_code': '130100'}]
        lyr.startEditing()
        for c in casos:
            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(LON0, LAT0)))
            for k, v in c.items():
                f[k] = v
            lyr.addFeature(f)
        self.assertTrue(lyr.commitChanges())
        lyr = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_measure'), 'm', 'ogr')
        expr = QgsExpression(simbolos.expressao_assinatura('coordination_measure'))
        self.assertFalse(expr.hasParserError(), expr.parserErrorString())
        n = 0
        for f in lyr.getFeatures():
            ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(lyr))
            ctx.setFeature(f)
            atributos = {k: f[k] for k in f.fields().names()}
            self.assertEqual(expr.evaluate(ctx), simbolos.assinatura('coordination_measure', atributos),
                             simbolos.texto_assinatura('coordination_measure', atributos))
            n += 1
        self.assertEqual(n, 4)


# ---------------------------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------------------------

class TestPainelMedidas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'calco_cap7.gpkg')
        cls.calco = Calco(cls.caminho)
        cls.calco.criar()
        cls.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(cls.calco)
        cls.painel = PainelCalco(get_iface())

    def _nova(self, **atr):
        lyr = self.calco.camada('coordination_measure')
        eid = gravar_feicao(lyr, 'coordination_measure', QgsGeometry.fromPointXY(QgsPointXY(LON0, LAT0)),
                            _attrs('coordination_measure', **atr))
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        return eid

    def _f(self, eid):
        # o painel da Medida edita no buffer (formulário da especificação): Salvar antes de reler o disco
        self.painel._gravar_pendentes()
        self.painel.salvar()
        return _reler(self.caminho, 'coordination_measure', eid)

    def _rotulo(self, col):
        w = self.painel.widgets[col]
        return [rot for _el, _c, _fl, w2, rot in self.painel._linhas if w2 is w][0].text()

    def _trocar_medida(self, codigo):
        cb = self.painel.widgets['point_code']
        i = cb.findData(codigo)
        self.assertGreaterEqual(i, 0, codigo)
        cb.setCurrentIndex(i)
        _APP.processEvents()

    def test_base_de_fogos_direcao_em_passo_de_um_grau(self):
        eid = self._nova(point_code='152000', rotation=-30.0)
        w = self.painel.widgets['rotation']
        self.assertIsInstance(w, QSpinBox)
        self.assertEqual((w.minimum(), w.maximum(), w.singleStep()), (0, 359, 1))
        self.assertEqual(self._rotulo('rotation'), 'Direção dos fogos')
        self.assertEqual(w.value(), 330)  # -30 lido como azimute
        w.setValue(201)
        self.painel._gravar_pendentes()
        self.assertEqual(self._f(eid)['rotation'], 201.0)

    def test_setor_de_tiro_secundaria_parada_no_terreno(self):
        eid = self._nova(point_code='140500', rotation=0.0)
        pri, sec = self.painel.widgets['rotation'], self.painel.widgets['angulo_secundario'].spin
        self.assertEqual(self._rotulo('rotation'), 'Direção principal')
        self.assertEqual(self._rotulo('angulo_secundario'), 'Direção secundária')
        self.assertEqual((pri.value(), sec.value()), (0, 315))  # sem valor: -45 do Web
        self.assertEqual(self.painel._abertura.text(), 'Abertura do setor: 45°')
        svg0 = _svg(self._f(eid))
        sec.setValue(70)
        self.painel._gravar_pendentes()
        f = self._f(eid)
        self.assertEqual((f['rotation'], f['angulo_secundario']), (0.0, 70.0))
        self.assertNotEqual(_svg(f), svg0)
        # Girar a principal deixa a secundária no mesmo azimute: o relativo compensa.
        pri.setValue(30)
        self.painel._gravar_pendentes()
        f = self._f(eid)
        self.assertEqual((f['rotation'], f['angulo_secundario']), (30.0, 40.0))
        self.assertEqual(sec.value(), 70)
        self.assertEqual(self.painel._abertura.text(), 'Abertura do setor: 40°')
        # Atravessando o norte: principal 350, secundária 70 -> relativo +80.
        pri.setValue(350)
        self.painel._gravar_pendentes()
        f = self._f(eid)
        self.assertEqual((f['rotation'], f['angulo_secundario']), (350.0, 80.0))
        self.assertEqual(_svg(f), Motor.instancia().medida({'pointCode': '140500', 'anguloSecundario': 80})['svg'])

    def test_campo_minado_tres_minas(self):
        eid = self._nova(point_code='270701')
        combos = [self.painel.widgets['mina{}'.format(i)] for i in (1, 2, 3)]
        for i, cb in enumerate(combos, 1):
            self.assertIsInstance(cb, QComboBox)
            self.assertEqual([cb.itemText(k) for k in range(cb.count())],
                             ['Antipessoal', 'Anticarro', 'Qualquer tipo', 'Vazia'])
            self.assertEqual(cb.currentData(), 'ap')  # mostra o padrão sem gravar
            self.assertEqual(self._rotulo('mina{}'.format(i)), 'Posição {}'.format(i))
        self.assertTrue(self._f(eid)['mina1'] is None or self._f(eid)['mina1'] == '' or
                        (hasattr(self._f(eid)['mina1'], 'isNull')))
        combos[0].setCurrentIndex(combos[0].findData('ac'))
        combos[2].setCurrentIndex(combos[2].findData('vazia'))
        self.painel._gravar_pendentes()
        f = self._f(eid)
        self.assertEqual((f['mina1'], f['mina3']), ('ac', 'vazia'))
        self.assertEqual(_svg(f).count('<ellipse'), 2)

    def test_demais_medidas_sem_minas_e_com_rotacao_livre(self):
        self._nova(point_code='130100')
        for c in ('mina1', 'mina2', 'mina3', 'angulo_secundario'):
            self.assertNotIn(c, self.painel.campos_visiveis())
        w = self.painel.widgets['rotation']
        self.assertEqual((w.minimum(), w.maximum(), w.singleStep()), (-180, 180, 15))
        self.assertEqual(self._rotulo('rotation'), 'Rotação')  # o rótulo do Web

    def test_seletor_sem_area_minada_pontual(self):
        self._nova(point_code='130100')
        cb = self.painel.widgets['point_code']
        dados = [cb.itemData(i) for i in range(cb.count())]
        self.assertNotIn('270800', dados)
        self.assertIn('152000', dados)
        self.assertIn('140500', dados)
        # A feição antiga 270800 aparece com o nome, e continua desenhando.
        eid = self._nova(point_code='270800')
        cb = self.painel.widgets['point_code']
        self.assertEqual(cb.currentData(), '270800')
        self.assertIn('Área minada', cb.currentText())
        self.assertTrue(self._f(eid)['svg'])

    def test_destruicao_nasce_verde(self):
        eid = self._nova(point_code='130100')
        self._trocar_medida('271201')
        self.assertEqual(str(self._f(eid)['fill_color']).upper(), VERDE)
        self._trocar_medida('271204')  # verde de um tipo para o verde do outro
        self.assertEqual(str(self._f(eid)['fill_color']).upper(), VERDE)
        self._trocar_medida('130100')  # sai do tipo: volta à cor padrão (nula)
        f = self._f(eid)
        self.assertTrue(f['fill_color'] is None or (hasattr(f['fill_color'], 'isNull') and f['fill_color'].isNull()))
        # A cor escolhida pelo operador fica.
        eid = self._nova(point_code='130100', fill_color='#cc0000')
        self._trocar_medida('271203')
        self.assertEqual(self._f(eid)['fill_color'], '#cc0000')

    def test_troca_de_tipo_limpa_minas_e_angulo(self):
        eid = self._nova(point_code='270701', mina1='ac', angulo_secundario=20.0)
        self._trocar_medida('140500')
        f = self._f(eid)
        for c in ('mina1', 'angulo_secundario'):
            v = f[c]
            self.assertTrue(v is None or (hasattr(v, 'isNull') and v.isNull()), c)


# ---------------------------------------------------------------------------------------------
# Alinhamento ao mapa (mapa girado)
# ---------------------------------------------------------------------------------------------

def _render(lyr, rotacao, arquivo=None, lado=420, largura_m=500):
    crs = QgsCoordinateReferenceSystem('EPSG:3857')
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    c = tr.transform(QgsPointXY(LON0, LAT0))
    ms = QgsMapSettings()
    ms.setLayers([lyr])
    ms.setDestinationCrs(crs)
    ms.setOutputSize(QSize(lado, lado))
    ms.setOutputDpi(96)
    ms.setExtent(QgsRectangle(c.x() - largura_m / 2, c.y() - largura_m / 2, c.x() + largura_m / 2, c.y() + largura_m / 2))
    ms.setRotation(rotacao)
    img = QImage(QSize(lado, lado), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    job = QgsMapRendererCustomPainterJob(ms, p)
    job.start()
    job.waitForFinished()
    p.end()
    if arquivo:
        img.save(os.path.join(SAIDA, arquivo))
    q = ms.mapToPixel().transform(c)
    n = ms.mapToPixel().transform(QgsPointXY(c.x(), c.y() + 50))
    norte = math.degrees(math.atan2(n.x() - q.x(), -(n.y() - q.y())))  # norte do terreno na tela
    return img, (q.x(), q.y()), norte


def _tinta(img):
    return {(x, y) for y in range(img.height()) for x in range(img.width()) if img.pixelColor(x, y).red() < 128}


def _girada(ref, centro, graus):
    """O desenho de referência (mapa sem giro, azimute 0) girado na tela em torno do ponto."""
    t = QTransform()
    t.translate(centro[0], centro[1])
    t.rotate(graus)
    t.translate(-centro[0], -centro[1])
    img = QImage(ref.size(), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setTransform(t)
    p.drawImage(QPointF(0, 0), ref)
    p.end()
    return img


def _dilatar(pontos):
    return {(x + dx, y + dy) for x, y in pontos for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


def _iou(a, b):
    """Coincidência de tinta com 1 px de folga: o traço de 2 px girado num raster serrilha."""
    return (len(a & _dilatar(b)) + len(b & _dilatar(a))) / max(1, len(a) + len(b))


class TestAlinhamentoAoMapa(unittest.TestCase):
    """
    Base de fogos e Setor de Tiro apontam o TERRENO com o mapa girado: o desenho na tela é o
    desenho sem giro girado por (azimute + giro do norte na tela). Pior caso: o mesmo desenho
    preso à tela (só o azimute, como as medidas do Web na camada geral) reprova.
    """

    def _camada(self, nome, atr):
        caminho = os.path.join(tempfile.mkdtemp(), nome + '.gpkg')
        gpkg.criar_calco(caminho)
        lyr = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_measure'), nome, 'ogr')
        a = _attrs('coordination_measure', zoom_corr=False, **atr)
        a.update(simbolos.renderizar('coordination_measure', a))
        lyr.startEditing()
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(LON0, LAT0)))
        for k, v in a.items():
            if k not in ('grupos', 'atributos', 'props', 'parametros'):
                f[k] = v
        lyr.addFeature(f)
        self.assertTrue(lyr.commitChanges())
        lyr = QgsVectorLayer(gpkg.uri_camada(caminho, 'coordination_measure'), nome, 'ogr')
        estilos_pontuais.aplicar_estilo(lyr, 'coordination_measure')
        return lyr

    def _conferir(self, codigo, extra):
        ref_lyr = self._camada(codigo + '_ref', dict(point_code=codigo, rotation=0.0, **extra))
        ref, centro, _n = _render(ref_lyr, 0)
        medidas = []
        for azimute, giro in ((0, 0), (0, 90), (120, 0), (120, 30), (300, -75)):
            lyr = self._camada('{}_{}_{}'.format(codigo, azimute, giro), dict(point_code=codigo, rotation=float(azimute), **extra))
            img, c, norte = _render(lyr, giro, 'alinhamento_{}_az{}_mapa{}.png'.format(codigo, azimute, giro))
            self.assertAlmostEqual(c[0], centro[0], delta=0.5)
            tinta = _tinta(img)
            certo = _iou(tinta, _tinta(_girada(ref, centro, azimute + norte)))
            preso_a_tela = _iou(tinta, _tinta(_girada(ref, centro, azimute)))
            medidas.append((azimute, giro, round(norte, 1), round(certo, 3), round(preso_a_tela, 3)))
            self.assertGreater(certo, 0.9, (codigo, azimute, giro, certo))
            if (azimute + norte) % 360 != azimute % 360:
                self.assertLess(preso_a_tela, certo - 0.3, (codigo, azimute, giro, preso_a_tela))
        print('\n[alinhamento] {} (azimute, giro do mapa, norte na tela, IoU terreno, IoU preso à tela): {}'.format(
            codigo, medidas))

    def test_base_de_fogos(self):
        self._conferir('152000', {})

    def test_setor_de_tiro(self):
        self._conferir('140500', {'angulo_secundario': 70.0})

    def test_regua_reprova_estilo_preso_a_tela(self):
        """A régua tem de acusar o estilo que desconta o giro do mapa (desenho preso à tela)."""
        lyr = self._camada('preso', dict(point_code='152000', rotation=120.0))
        ref_lyr = self._camada('preso_ref', dict(point_code='152000', rotation=0.0))
        ref, centro, _n = _render(ref_lyr, 0)
        r = lyr.renderer().clone()
        for regra in r.rootRule().children():
            for sl in regra.symbol().symbolLayers():
                p = sl.dataDefinedProperties().property(QgsSymbolLayer.Property.Angle)
                if p and p.isActive():
                    sl.setDataDefinedProperty(QgsSymbolLayer.Property.Angle,
                                              QgsProperty.fromExpression('coalesce("rotation", 0) - @map_rotation'))
        lyr.setRenderer(r)
        img, _c, norte = _render(lyr, 30, 'alinhamento_pior_caso_preso_a_tela.png')
        certo = _iou(_tinta(img), _tinta(_girada(ref, centro, 120 + norte)))
        print('\n[alinhamento] pior caso preso à tela, mapa a 30 graus: IoU contra o terreno {:.3f}'.format(certo))
        self.assertLess(certo, 0.6, certo)


# ---------------------------------------------------------------------------------------------
# Linha de Limite: Ø e ++
# ---------------------------------------------------------------------------------------------

def _hav_m(a, b):
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dla, dlo = la2 - la1, math.radians(b[0] - a[0])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * R_TURF * math.asin(math.sqrt(h))


def _rumo(a, b):
    la1, la2 = math.radians(a[1]), math.radians(b[1])
    dlo = math.radians(b[0] - a[0])
    y = math.sin(dlo) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlo)
    return math.degrees(math.atan2(y, x))


def _partes(g):
    if g is None or g.isNull() or g.isEmpty():
        return []
    out = []
    for p in g.asGeometryCollection():
        if p.type() == Qgis.GeometryType.Polygon:
            out.append([(v.x(), v.y()) for v in p.asPolygon()[0]])
        elif p.type() == Qgis.GeometryType.Line:
            out.append([(v.x(), v.y()) for v in p.asPolyline()])
    return out


class TestLimiteEquipeEIndeterminado(unittest.TestCase):
    RETA = [(-47.95, -15.80), (-47.76, -15.80)]   # ~20,3 km para leste

    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(tempfile.mkdtemp(), 'limite.gpkg')
        gpkg.criar_calco(cls.caminho)

    def _glifos(self, echelon):
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'boundary'), 'b', 'ogr')
        f = QgsFeature(vl.fields())
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in self.RETA]))
        for k, v in dict(schema.padroes('boundary'), echelon=echelon, symbol_size_km=1.0,
                         symbol_instances='[{"ratio": 0.5, "showLabels": false}]').items():
            f[k] = v
        ok, novas = vl.dataProvider().addFeatures([f])
        self.assertTrue(ok)
        vl = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'boundary'), 'b', 'ogr')
        f = vl.getFeature(novas[0].id())
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(vl))
        ms = QgsMapSettings()
        ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
        ms.setOutputSize(QSize(1000, 800))
        ms.setOutputDpi(96)
        ms.setExtent(QgsRectangle(-5340000, -1785000, -5330000, -1775000))
        ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
        ctx.setFeature(f)
        resultado = {}
        for nome, texto in (('linhas', et.expr_limite_linhas()), ('circulos', et.expr_limite_circulos())):
            e = QgsExpression(texto)
            e.prepare(ctx)
            resultado[nome] = _partes(e.evaluate(ctx))
            self.assertFalse(e.hasEvalError(), e.evalErrorString())
        # Os trechos do eixo tocam uma das pontas da reta; o resto são os glifos, na ordem do Web.
        def no_eixo(p):
            return any(abs(v[0] - x) < 1e-9 and abs(v[1] - y) < 1e-9 for v in (p[0], p[-1]) for x, y in self.RETA)
        resultado['glifos'] = [p for p in resultado['linhas'] if not no_eixo(p)]
        centro = (sum(x for x, _ in self.RETA) / 2, self.RETA[0][1])
        return resultado, centro

    def test_equipe_anel_vazado_e_barra(self):
        r, centro = self._glifos('Ø')
        self.assertEqual(r['circulos'], [])            # nunca o círculo cheio do 'o'
        self.assertEqual(len(r['glifos']), 2, r['glifos'])
        anel, barra = r['glifos']
        self.assertGreater(len(anel), 30)
        self.assertEqual(anel[0], anel[-1])
        for v in anel:
            self.assertAlmostEqual(_hav_m(centro, v), 424, delta=5)
        self.assertEqual(len(barra), 2)
        for v in barra:
            self.assertAlmostEqual(_hav_m(centro, v), 632.8, delta=5)
        # Sobe da esquerda para a direita: rumo 90 - 26,57 numa linha para leste.
        self.assertAlmostEqual(_rumo(barra[0], barra[1]), 90 - 26.57, delta=1)
        # O vão é de um glifo: 1 x 1000 x 1,5 x 1,2 = 1800 m.
        no_eixo = [p for p in r['linhas'] if p not in r['glifos']]
        self.assertEqual(len(no_eixo), 2)
        vao = _hav_m(no_eixo[0][-1], no_eixo[1][0])
        self.assertAlmostEqual(vao, 1800, delta=10)

    def test_indeterminado_duas_cruzes(self):
        r, centro = self._glifos('++')
        self.assertEqual(r['circulos'], [])
        self.assertEqual(len(r['glifos']), 4, r['glifos'])
        for a, b in r['glifos']:
            self.assertAlmostEqual(_hav_m(a, b), 708, delta=5)
        # Em cada cruz um braço ao longo e outro através da linha.
        for i in (0, 2):
            ang = abs(_rumo(*r['glifos'][i]) - _rumo(*r['glifos'][i + 1])) % 180
            self.assertAlmostEqual(ang, 90, delta=0.5)
        meio = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in r['glifos']]
        self.assertAlmostEqual(_hav_m(meio[0], meio[2]), 1500, delta=5)
        # Vão de dois glifos: 2 x 1000 x 1,5 x 1,2 = 3600 m.
        no_eixo = [p for p in r['linhas'] if p not in r['glifos']]
        self.assertAlmostEqual(_hav_m(no_eixo[0][-1], no_eixo[1][0]), 3600, delta=10)

    def test_painel_oferece_os_dois_e_mantem_xxxxx(self):
        from Calco.estilos_area import ESCALOES
        from Calco.formulario import especificacao as esp
        self.assertEqual(ESCALOES,
                         ['XXXXXX', 'XXXXX', 'XXXX', 'XXX', 'XX', 'X', 'III', 'II', 'I', 'ooo', 'oo', 'o', 'Ø', '++'])
        mapa = esp.formulario('boundary').campo('echelon').widget.config['map']
        opcoes = {list(d.values())[0]: list(d)[0] for d in mapa}
        self.assertEqual((opcoes['Ø'], opcoes['++']), ('Ø', '++'))


# ---------------------------------------------------------------------------------------------
# Importador .ebgeo
# ---------------------------------------------------------------------------------------------

def _ebgeo(features):
    data = {'version': '3.0', 'mapOrder': ['Cap VII'],
            'maps': {'Cap VII': {'features': features}}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('data.json', json.dumps(data, ensure_ascii=False))
    return leitor.CABECALHO + bytes(b ^ leitor.CHAVE_XOR for b in buf.getvalue())


def _ponto(ident, **p):
    return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [LON0, LAT0]},
            'properties': dict({'id': ident, 'layerId': 'default'}, **p)}


def _limite(ident, echelon):
    coords = [[-47.95, -15.80], [-47.76, -15.80]]
    return {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords},
            'properties': {'id': ident, 'layerId': 'default', 'echelon': echelon, 'baseCoordinates': coords,
                           'symbol_size': 1, 'symbol_instances': [{'ratio': 0.5, 'showLabels': True}]}}


class TestImportador(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        raw = _ebgeo({
            'coordination_measures': [
                _ponto('fogos', pointCode='152000', rotation=135),
                _ponto('setor', pointCode='140500', rotation=30, anguloSecundario=40),
                _ponto('minas', pointCode='270701', mina1='ac', mina2='qualquer', mina3='vazia'),
                _ponto('legado', pointCode='270800'),
                _ponto('destruicao', pointCode='271203', fillColor=VERDE),
            ],
            'boundarys': [_limite('equipe', 'Ø'), _limite('indeterminado', '++')],
        })
        cls.destino = os.path.join(tempfile.mkdtemp(), 'importado.gpkg')
        cls.rel = escritor.gravar_documento(leitor.abrir_bytes(raw, 'cap7.ebgeo'), cls.destino)

    def _f(self, tipo, eid):
        return _reler(self.destino, tipo, eid)

    def test_propriedades_viram_colunas(self):
        self.assertEqual(self.rel.descartadas, [])
        s = self._f('coordination_measure', 'setor')
        self.assertEqual((s['point_code'], s['rotation'], s['angulo_secundario']), ('140500', 30.0, 40.0))
        m = self._f('coordination_measure', 'minas')
        self.assertEqual((m['mina1'], m['mina2'], m['mina3']), ('ac', 'qualquer', 'vazia'))
        self.assertEqual(self._f('coordination_measure', 'fogos')['rotation'], 135.0)
        # o importador grava a cor na forma canônica (minúsculas), a que o formulário nativo regrava
        self.assertEqual(self._f('coordination_measure', 'destruicao')['fill_color'], schema.cor_canonica(VERDE))
        self.assertEqual(self._f('boundary', 'equipe')['echelon'], 'Ø')
        self.assertEqual(self._f('boundary', 'indeterminado')['echelon'], '++')

    def test_desenho_importado_usa_as_propriedades(self):
        motor = Motor.instancia()
        s = self._f('coordination_measure', 'setor')
        self.assertEqual(_svg(s), motor.medida({'pointCode': '140500', 'anguloSecundario': 40})['svg'])
        self.assertNotEqual(_svg(s), motor.medida({'pointCode': '140500'})['svg'])
        m = self._f('coordination_measure', 'minas')
        self.assertEqual(_svg(m).count('<ellipse'), 2)
        self.assertTrue(_svg(self._f('coordination_measure', 'legado')))
        # A assinatura gravada é a que o estilo recalcula: nada de aviso vermelho.
        for eid in ('setor', 'minas', 'fogos', 'legado'):
            f = self._f('coordination_measure', eid)
            self.assertEqual(f['svg_assinatura'],
                             simbolos.assinatura('coordination_measure', {k: f[k] for k in f.fields().names()}), eid)

    def test_fixture_06_regenerada(self):
        """Na fixture 3.0 regenerada pelo gerador do Web: as variantes do capítulo VII entram iguais."""
        pasta = os.environ.get('EBGEO_FIXTURES') or os.path.join(PACOTE, '..', '..', '_ebgeo_dados_teste')
        caminho = os.path.join(pasta, '06-completo-3.0.ebgeo')
        if not os.path.exists(caminho):
            self.skipTest('fixture 06 ausente')
        doc = leitor.abrir(caminho)
        alvos = {}
        for mapa in doc.data['maps'].values():
            for balde, lst in (mapa.get('features') or {}).items():
                for ft in lst:
                    p = ft.get('properties') or {}
                    if balde == 'coordination_measures' and (p.get('anguloSecundario') is not None or p.get('mina1')):
                        alvos.setdefault('medida', []).append(p)
                    if balde == 'boundarys' and p.get('echelon') in ('Ø', '++'):
                        alvos.setdefault('limite', []).append(p)
        if not alvos.get('medida') or len(alvos.get('limite', [])) < 2:
            self.skipTest('fixture 06 sem as variantes do capítulo VII: regenere-a')
        destino = os.path.join(tempfile.mkdtemp(), 'f06.gpkg')
        escritor.gravar_documento(doc, destino)
        for p in alvos['medida']:
            f = self._reler_em(destino, 'coordination_measure', p['id'])
            for col, web in (('mina1', 'mina1'), ('mina2', 'mina2'), ('mina3', 'mina3'),
                             ('angulo_secundario', 'anguloSecundario')):
                if p.get(web) is not None:
                    self.assertEqual(f[col], p[web], (p['id'], col))
        for p in alvos['limite']:
            self.assertEqual(self._reler_em(destino, 'boundary', p['id'])['echelon'], p['echelon'])
        print('\n[fixture 06] {} medidas com minas ou ângulo e {} limites Ø/++ conferidos'.format(
            len(alvos['medida']), len(alvos['limite'])))

    @staticmethod
    def _reler_em(caminho, tipo, eid):
        return _reler(caminho, tipo, eid)


# ---------------------------------------------------------------------------------------------
# Calco antigo aberto pelo plugin novo: o estilo gravado se atualiza
# ---------------------------------------------------------------------------------------------

COMMIT_ANTIGO = '0792270'  # qgis4 antes do capítulo VII

# Roda o plugin de COMMIT_ANTIGO, extraído numa pasta temporária: cria o calco (fase 'criar') ou
# o abre e desenha a medida (fase 'abrir'), contando o vermelho do aviso perto do ponto.
SCRIPT_PLUGIN_ANTIGO = r'''
import json, os, sys
pasta, caminho, fase, png, lon, lat = sys.argv[1:7]
sys.path.insert(0, pasta)
from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsMapRendererCustomPainterJob,
    QgsMapSettings, QgsPointXY, QgsProject, QgsRectangle)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QImage, QPainter
app = QgsApplication([], False); app.initQgis()
import Calco
assert os.path.normcase(os.path.abspath(Calco.__file__)).startswith(os.path.normcase(os.path.abspath(pasta))), Calco.__file__
from Calco.calco import Calco as C
c = C(caminho); c.criar(); camadas = c.carregar()
saida = {'pacote': Calco.__file__}
if fase == 'abrir':
    lyr = camadas['coordination_measure']
    crs = QgsCoordinateReferenceSystem('EPSG:3857')
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    p = tr.transform(QgsPointXY(float(lon), float(lat)))
    ms = QgsMapSettings(); ms.setLayers([lyr]); ms.setDestinationCrs(crs); ms.setOutputSize(QSize(420, 420)); ms.setOutputDpi(96)
    ms.setExtent(QgsRectangle(p.x() - 250, p.y() - 250, p.x() + 250, p.y() + 250))
    img = QImage(QSize(420, 420), QImage.Format.Format_ARGB32); img.fill(QColor(255, 255, 255))
    pt = QPainter(img); job = QgsMapRendererCustomPainterJob(ms, pt); job.start(); job.waitForFinished(); pt.end()
    img.save(png)
    k = [img.pixelColor(x, y) for y in range(420) for x in range(420)]
    saida['vermelho'] = sum(1 for q in k if q.red() > 180 and q.green() < 60 and q.blue() < 60)
    saida['tinta'] = sum(1 for q in k if q.red() < 128)
print(json.dumps(saida))
'''


def _contar(img):
    k = [img.pixelColor(x, y) for y in range(img.height()) for x in range(img.width())]
    vermelho = sum(1 for q in k if q.red() > 180 and q.green() < 60 and q.blue() < 60)
    return vermelho, sum(1 for q in k if q.red() < 128)


class TestEstiloDoCalcoAntigo(unittest.TestCase):
    """
    Um calco criado pelo plugin de COMMIT_ANTIGO tem no layer_styles o estilo de então, cuja
    assinatura não conhece minas nem ângulo secundário. Aberto pelo plugin novo, a medida 270701
    com minas tem de desenhar sem a caixa vermelha de aviso, também num QGIS sem o plugin; o
    estilo que o operador gravou com outro nome fica como está.
    """

    @classmethod
    def setUpClass(cls):
        import shutil
        import subprocess
        raiz = os.path.dirname(PACOTE)
        cls.dir = tempfile.mkdtemp(prefix='ebgeo-estilo-antigo-')
        arq = os.path.join(cls.dir, 'antigo.zip')
        # o python-qgis.bat troca o PATH: procura também no instalador padrão do Git para Windows
        candidatos = [os.environ.get('EBGEO_GIT'), shutil.which('git')] + [
            os.path.join(os.environ[v], 'Git', 'cmd', 'git.exe') for v in ('ProgramFiles', 'ProgramW6432') if os.environ.get(v)]
        git = next((c for c in candidatos if c and os.path.exists(c)), None)
        if not git:
            raise unittest.SkipTest('git ausente: o plugin antigo não pode ser extraído')
        r = subprocess.run([git, '-C', raiz, 'archive', '--format=zip', '-o', arq, COMMIT_ANTIGO, 'EBGeo/Calco'],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise unittest.SkipTest('git archive falhou: ' + r.stderr[-300:])
        with zipfile.ZipFile(arq) as z:
            z.extractall(os.path.join(cls.dir, 'antigo'))
        cls.pacote_antigo = os.path.join(cls.dir, 'antigo', 'EBGeo')
        cls.script = os.path.join(cls.dir, 'plugin_antigo.py')
        with open(cls.script, 'w', encoding='utf-8') as f:
            f.write(SCRIPT_PLUGIN_ANTIGO)
        cls.caminho = os.path.join(cls.dir, 'calco_antigo.gpkg')
        cls.rodar_antigo('criar')
        # O operador personalizou o Limite e gravou como padrão com nome próprio.
        b = QgsVectorLayer(gpkg.uri_camada(cls.caminho, 'boundary'), 'Linha de Limite', 'ogr')
        from qgis.core import QgsLineSymbol, QgsSingleSymbolRenderer
        b.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({'line_color': '255,0,255', 'line_width': '1.2'})))
        b.saveStyleToDatabaseV2('Meu limite', 'cores da 1ª DE', True, '')
        from Calco.calco import estilo_padrao_salvo
        cls.limite_antes = estilo_padrao_salvo(cls.caminho, 'boundary')
        cls.medida_antes = estilo_padrao_salvo(cls.caminho, 'coordination_measure')
        # O plugin novo acrescenta as colunas (criar) e o operador desenha o campo minado com minas.
        Calco(cls.caminho).criar()
        lyr = QgsVectorLayer(gpkg.uri_camada(cls.caminho, 'coordination_measure'), 'm', 'ogr')
        a = _attrs('coordination_measure', point_code='270701', mina1='ac', mina2='qualquer', mina3='vazia', zoom_corr=False)
        a.update(simbolos.renderizar('coordination_measure', a))
        lyr.startEditing()
        f = QgsFeature(lyr.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(LON0, LAT0)))
        for k, v in a.items():
            if k not in ('grupos', 'atributos', 'props', 'parametros'):
                f[k] = v
        lyr.addFeature(f)
        assert lyr.commitChanges()

    @classmethod
    def rodar_antigo(cls, fase, png=''):
        import subprocess
        r = subprocess.run([sys.executable, cls.script, cls.pacote_antigo, cls.caminho, fase, png, str(LON0), str(LAT0)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-3000:]
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_1_o_plugin_de_hoje_mostra_o_aviso(self):
        """Controle: aberto pelo código antigo (e sem plugin, pelo estilo gravado), a caixa vermelha aparece."""
        # O Calco.carregar antigo gravava descrição vazia, que o QGIS troca pela data.
        from Calco.calco import DATA_DO_QGIS
        self.assertRegex(self.medida_antes['descricao'], DATA_DO_QGIS)
        self.assertEqual(self.medida_antes['nome'], 'Medida de Coordenação')
        r = self.rodar_antigo('abrir', os.path.join(SAIDA, 'calco_antigo_plugin_antigo.png'))
        self.assertIn(os.path.join('antigo', 'EBGeo', 'Calco'), r['pacote'])
        sem_plugin = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_measure'), 'm', 'ogr')
        vermelho, _t = _contar(_render(sem_plugin, 0, 'calco_antigo_sem_plugin_antes.png')[0])
        print('\n[estilo antigo] vermelho do aviso: plugin antigo {} px, estilo gravado sem plugin {} px'.format(
            r['vermelho'], vermelho))
        self.assertGreater(r['vermelho'], 100)
        self.assertGreater(vermelho, 100)

    def test_2_o_plugin_novo_atualiza_e_respeita_o_personalizado(self):
        from Calco.calco import MARCA_ESTILO, estilo_padrao_salvo
        c = Calco(self.caminho)
        camadas = c.carregar()
        vermelho, tinta = _contar(_render(camadas['coordination_measure'], 0, 'calco_antigo_plugin_novo.png')[0])
        # E num QGIS sem o plugin, pelo estilo que ficou gravado.
        sem_plugin = QgsVectorLayer(gpkg.uri_camada(self.caminho, 'coordination_measure'), 'm', 'ogr')
        vermelho_sp, tinta_sp = _contar(_render(sem_plugin, 0, 'calco_antigo_sem_plugin_depois.png')[0])
        print('\n[estilo antigo] depois do plugin novo: vermelho {} px (tinta {}), sem plugin vermelho {} px (tinta {})'.format(
            vermelho, tinta, vermelho_sp, tinta_sp))
        self.assertEqual((vermelho, vermelho_sp), (0, 0))
        self.assertGreater(min(tinta, tinta_sp), 200)
        self.assertEqual(c.estilos['coordination_measure'], 'atualizado')
        self.assertEqual(c.estilos['boundary'], 'personalizado')
        self.assertEqual(c.estilos['coordination_line'], 'atualizado')
        salvo = estilo_padrao_salvo(self.caminho, 'coordination_measure')
        self.assertTrue(salvo['descricao'].startswith(MARCA_ESTILO), salvo['descricao'])
        # O estilo do operador ficou byte a byte, e a camada desenha com ele.
        self.assertEqual(estilo_padrao_salvo(self.caminho, 'boundary'), self.limite_antes)
        self.assertEqual(camadas['boundary'].renderer().type(), 'singleSymbol')
        # Aberto de novo: nada a regravar.
        c2 = Calco(self.caminho)
        QgsProject.instance().removeMapLayers([l.id() for l in camadas.values()])
        c2.carregar()
        self.assertEqual(c2.estilos['coordination_measure'], 'em dia')
        self.assertEqual(c2.estilos['boundary'], 'personalizado')

    def test_3_regua_reprova_estilo_do_plugin_com_outro_nome(self):
        """O reconhecimento do estilo do plugin exige nome e descrição dele: pior caso, outro nome."""
        from Calco.calco import estilo_e_do_plugin
        base = {'nome': 'Medida de Coordenação', 'descricao': '', 'qml': '... coalesce("visivel", true) ...'}
        self.assertTrue(estilo_e_do_plugin(base, 'coordination_measure'))
        self.assertFalse(estilo_e_do_plugin(dict(base, nome='Minhas medidas'), 'coordination_measure'))
        self.assertFalse(estilo_e_do_plugin(dict(base, descricao='ajustado'), 'coordination_measure'))
        self.assertFalse(estilo_e_do_plugin(dict(base, qml='<qgis/>'), 'coordination_measure'))
        self.assertTrue(estilo_e_do_plugin(dict(base, descricao='Sun Oct 4 21:12:38 2026'), 'coordination_measure'))
        self.assertFalse(estilo_e_do_plugin(dict(base, descricao='Sun Oct 4 21:12:38 2026 (meu)'), 'coordination_measure'))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('\nImagens em: ' + SAIDA)
    sys.exit(0 if r.wasSuccessful() else 1)
