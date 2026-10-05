# -*- coding: utf-8 -*-
"""
Testes do exportador .ebgeo (Calco/exportador), rodáveis com o Python do QGIS 4:

    python-qgis.bat EBGeo/Calco/testes/test_exportador.py

Fixtures em EBGEO_FIXTURES (padrão ../_ebgeo_dados_teste ao lado do repositório). Com EBGEO_WEB ou
EBGEO_WEB_DIR (checkout do ebgeo_web, com o frontend/node_modules) e node no PATH (ou EBGEO_NODE),
o arquivo exportado passa também pelo leitor, pelo portão de versão e pela normalização do próprio
Web, em node; sem elas, esses casos são pulados.

O que cada classe prova (a conferência relê o arquivo GRAVADO, nunca o documento montado):
    TestIdaEVolta06     a fixture 06 importada e exportada sem edição volta igual ao original, feição a
                        feição e chave a chave, com as imagens byte a byte; a régua reprova o pior caso
                        degradado da própria saída (uma chave a menos, cor trocada, coordenada mexida,
                        imagem faltando) e o exportador ingênuo que remonta as propriedades só das colunas;
    TestEdicoes         só o que se editou no Desktop muda no arquivo, e cada edição chega no formato do
                        Web (nome, atributo livre, SIDC e as chaves dele, cor, escalão com o desenho refeito,
                        vértice da Seta com o contorno refeito, translação do círculo, feição apagada);
    TestCriadasNoDesktop uma feição de cada ferramenta (ponto militar, medida, linha de coordenação, área,
                        limite, seta, azimute) criada pelo gesto da ferramenta sai com as chaves e a
                        geometria que o Web lê; a desenhada numa camada do atlas vai ao mapa e à camada dela;
    TestArvore          o mapa ligado, o check, a opacidade e o bloqueio das camadas EBGeo na árvore vão ao
                        arquivo; sem a árvore, ficam os da tabela;
    TestAlgoritmo       o algoritmo de Processing e a ação do menu (com a pergunta de salvar edições);
    TestWeb             o leitor, o portão e a normalização do Web (node) aceitam os arquivos e veem nos
                        mapas da volta exatamente o que veem nos do original.
"""
import base64
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import io

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, os.path.join(RAIZ_REPO, 'EBGeo'))

FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsGeometry, QgsPointXY, QgsProcessingContext,
    QgsProcessingFeedback, QgsProject, QgsRectangle, QgsVectorLayer,
)

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from qgis.gui import QgsMapCanvas, QgsMapMouseEvent  # noqa: E402
from qgis.PyQt.QtCore import QEvent, QPoint, Qt  # noqa: E402

from Calco import schema  # noqa: E402
from Calco.importador import escritor, leitor  # noqa: E402
from Calco.exportador import arquivo, desenho, montador  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_exportador_')
_CACHE = {}


def calco_06():
    """O GeoPackage da fixture 06 importada (uma vez por execução); cada teste usa uma cópia."""
    if 'gpkg' not in _CACHE:
        cam = os.path.join(TMP, 'f06.gpkg')
        escritor.importar(FIXTURE_06, cam)
        _CACHE['gpkg'] = cam
    return _CACHE['gpkg']


def copia_06(nome):
    cam = os.path.join(TMP, nome + '.gpkg')
    shutil.copy(calco_06(), cam)
    return cam


def exportar(cam, escopo=montador.ESCOPO_TUDO, estado=None, nome=None):
    """Monta, grava e RELÊ pelo leitor do importador. Devolve (Documento relido, Exportacao)."""
    exp = montador.montar(cam, escopo, estado, desenho.GeradorDesenho())
    saida = os.path.join(TMP, (nome or os.path.splitext(os.path.basename(cam))[0]) + '.ebgeo')
    arquivo.gravar(saida, exp.data, exp.imagens)
    return leitor.abrir(saida), exp


# ---------------------------------------------------------------- a régua

def divergencias(a, b, caminho='', out=None):
    """Toda diferença entre dois JSON: chave a menos ou a mais, valor, tipo (int contra bool), tamanho."""
    out = [] if out is None else out
    num = (int, float)
    if isinstance(a, bool) != isinstance(b, bool) or (
            type(a) is not type(b) and not (isinstance(a, num) and isinstance(b, num))):
        out.append((caminho, 'tipo', a, b))
    elif isinstance(a, dict):
        for k in a:
            if k not in b:
                out.append((caminho + '.' + k, 'falta', a[k], None))
            else:
                divergencias(a[k], b[k], caminho + '.' + k, out)
        out.extend((caminho + '.' + k, 'sobra', None, b[k]) for k in b if k not in a)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((caminho, 'tamanho', len(a), len(b)))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                divergencias(x, y, '{}[{}]'.format(caminho, i), out)
    elif a != b:
        out.append((caminho, 'valor', a, b))
    return out


def feicoes_2d(data):
    """{(mapa, balde, id): feição} dos baldes do 2D que o Desktop conhece."""
    out = {}
    for nome, m in (data.get('maps') or {}).items():
        for balde, lista in (m.get('features') or {}).items():
            if balde not in montador.BALDES_DESKTOP:
                continue
            for i, f in enumerate(lista):
                out[(nome, balde, (f.get('properties') or {}).get('id') or i)] = f
    return out


def comparar_feicoes(orig, novo):
    """Feição a feição e chave a chave: {(mapa, balde, id): [divergências]} e o número de chaves comparadas."""
    fo, fn = feicoes_2d(orig), feicoes_2d(novo)
    dif, chaves = {}, 0
    for k in set(fo) | set(fn):
        if k not in fn or k not in fo:
            dif[k] = [('', 'feição ausente' if k not in fn else 'feição a mais', None, None)]
            continue
        chaves += len(fo[k].get('properties') or {})
        d = divergencias(fo[k], fn[k])
        if d:
            dif[k] = d
    return dif, chaves


def bytes_imagens(caminho):
    with open(caminho, 'rb') as fh:
        raw = leitor.desmascarar(fh.read())
    z = zipfile.ZipFile(io.BytesIO(raw))
    return {n[len('images/'):].rsplit('.', 1)[0]: z.read(n) for n in z.namelist()
            if n.startswith('images/') and not n.endswith('/')}


def degradar(data, imagens):
    """Os piores casos, da saída REAL: uma chave a menos, cor trocada, coordenada mexida, imagem faltando."""
    casos = []
    feicoes = sorted(feicoes_2d(data).items(), key=lambda kv: str(kv[0]))
    alvo = next(f for k, f in feicoes if k[1] == 'coordination_lines')
    d = copy.deepcopy(data)
    fd = feicoes_2d(d)
    chave = next(k for k in fd if k[2] == alvo['properties']['id'])
    del fd[chave]['properties']['symbol_size']
    casos.append(('chave a menos', d, imagens))
    d = copy.deepcopy(data)
    fd = feicoes_2d(d)
    fd[chave]['properties']['color'] = '#00ff00'
    casos.append(('cor trocada', d, imagens))
    d = copy.deepcopy(data)
    fd = feicoes_2d(d)
    ponto = next(f for k, f in fd.items() if k[1] == 'military_symbols')
    ponto['geometry']['coordinates'][0] += 1e-5
    casos.append(('coordenada mexida', d, imagens))
    im = dict(imagens)
    im.pop(next(iter(sorted(im))))
    casos.append(('imagem faltando', data, im))
    return casos


# ---------------------------------------------------------------- testes

@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestIdaEVolta06(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = leitor.abrir(FIXTURE_06)
        cls.volta, cls.exp = exportar(copia_06('ida_volta'))
        cls.caminho = os.path.join(TMP, 'ida_volta.ebgeo')

    def test_feicao_a_feicao(self):
        dif, chaves = comparar_feicoes(self.orig.data, self.volta.data)
        print('\nida e volta da 06: {} feições, {} chaves comparadas, {} feições divergentes'.format(
            len(feicoes_2d(self.orig.data)), chaves, len(dif)))
        self.assertEqual(len(feicoes_2d(self.orig.data)), 1605)
        self.assertEqual(dif, {})
        r = self.exp.relatorio
        self.assertEqual((r.iguais, r.editadas, r.novas, r.apagadas), (1605, 0, 0, 0))

    def test_documento_inteiro_e_imagens(self):
        # 360, 3D, briefings, temporal, comentários, camadas, grupos, ordem: o documento inteiro
        self.assertEqual(divergencias(self.orig.data, self.volta.data), [])
        a, b = bytes_imagens(FIXTURE_06), bytes_imagens(self.caminho)
        self.assertEqual(len(a), 1305)
        self.assertEqual(set(a), set(b))
        self.assertEqual([k for k in a if a[k] != b[k]], [])

    def test_regua_reprova_pior_caso(self):
        for nome, data, imagens in degradar(self.exp.data, self.exp.imagens):
            cam = os.path.join(TMP, 'pior.ebgeo')
            arquivo.gravar(cam, data, imagens)
            doc = leitor.abrir(cam)
            dif, _ = comparar_feicoes(self.orig.data, doc.data)
            faltam = set(bytes_imagens(FIXTURE_06)) - set(bytes_imagens(cam))
            self.assertTrue(dif or faltam, nome)
            # e a conferência do próprio exportador reprova o arquivo que não é o montado
            self.assertTrue(arquivo.conferir(cam, self.exp.data, self.exp.imagens), nome)

    def test_regua_reprova_exportador_ingenuo(self):
        """O caminho que não guarda o original (props montado só das colunas) perde chaves do Web."""
        class Ingenuo(montador.Montador):
            def feicao(self, tipo, linha):
                linha = dict(linha)
                linha['props'] = None
                return super().feicao(tipo, linha)
        exp = Ingenuo(montador.Calco(copia_06('ingenuo'))).montar()
        dif, _ = comparar_feicoes(self.orig.data, json.loads(json.dumps(exp.data)))
        print('\nexportador ingênuo: {} de 1605 feições divergem'.format(len(dif)))
        self.assertGreater(len(dif), 1500)


def _primeira(layer, expressao=None):
    return next(iter(layer.getFeatures(expressao) if expressao else layer.getFeatures()))


def _camada(cam, tipo):
    l = QgsVectorLayer('{}|layername={}'.format(cam, schema.TIPOS[tipo]['tabela']), tipo, 'ogr')
    assert l.isValid(), tipo
    return l


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestEdicoes(unittest.TestCase):
    """Edições pelo QgsVectorLayer (o caminho do formulário e da tabela), depois exporta."""

    @classmethod
    def setUpClass(cls):
        cam = copia_06('edicoes')
        cls.ids = ids = {}

        def editar(tipo, fn, expressao=None):
            l = _camada(cam, tipo)
            f = _primeira(l, expressao)
            l.startEditing()
            fn(l, f)
            assert l.commitChanges(), l.commitErrors()
            ids[tipo] = f['ebgeo_id']
            return f

        def mover_vertice(i, dx, dy):
            def fn(l, f):
                g = QgsGeometry(f.geometry())
                v = g.vertexAt(i)
                g.moveVertex(v.x() + dx, v.y() + dy, i)
                l.changeGeometry(f.id(), g)
            return fn

        editar('point', lambda l, f: (
            l.changeAttributeValue(f.id(), l.fields().indexOf('nome'), 'Renomeado no Desktop'),
            l.changeAttributeValue(f.id(), l.fields().indexOf('attr_unidade'), 'valor novo')),
            '"attr_unidade" IS NOT NULL')
        editar('coordination_line', lambda l, f: l.changeAttributeValue(f.id(), l.fields().indexOf('color'), '#123456'))
        editar('boundary', lambda l, f: l.changeAttributeValue(f.id(), l.fields().indexOf('echelon'), 'III'))
        editar('arrow', mover_vertice(1, 0.01, 0.01), '"props" NOT LIKE \'%isMerged%\'')
        editar('occupied_front', mover_vertice(2, 0.005, 0))

        def sidc(l, f):
            p = f.geometry().asPoint()
            l.changeGeometry(f.id(), QgsGeometry.fromPointXY(QgsPointXY(p.x() + 0.001, p.y())))
            l.changeAttributeValue(f.id(), l.fields().indexOf('sidc'), '100610001612110000000760000000')
        editar('military_symbol', sidc)

        def transladar(l, f):
            g = QgsGeometry(f.geometry())
            g.translate(0.002, -0.001)
            l.changeGeometry(f.id(), g)
        editar('circle', transladar)
        editar('text', lambda l, f: l.deleteFeature(f.id()))
        cls.orig = leitor.abrir(FIXTURE_06)
        cls.doc, cls.exp = exportar(cam)
        cls.dif, _ = comparar_feicoes(cls.orig.data, cls.doc.data)
        cls.por_id = {k[2]: v for k, v in cls.dif.items()}

    def _props(self, tipo):
        return next(f for k, f in feicoes_2d(self.doc.data).items() if k[2] == self.ids[tipo])['properties']

    def test_so_o_editado_muda(self):
        self.assertEqual(set(self.por_id), set(self.ids.values()))
        r = self.exp.relatorio
        self.assertEqual((r.editadas, r.apagadas, r.iguais), (7, 1, 1597))

    def test_cada_edicao_no_formato_do_web(self):
        caminhos = lambda tipo: {d[0].split('.properties.')[-1].split('[')[0] if '.properties.' in d[0]
                                 else d[0].split('.')[-1].split('[')[0] for d in self.por_id[self.ids[tipo]]}
        self.assertEqual(caminhos('point'), {'nome', 'attributes.Unidade'})
        self.assertEqual(self._props('point')['nome'], 'Renomeado no Desktop')
        self.assertEqual(self._props('point')['attributes']['Unidade'], 'valor novo')
        # a cor muda e o desenho fica (cor não muda geometria)
        self.assertEqual(caminhos('coordination_line'), {'color'})
        self.assertEqual(self._props('coordination_line')['color'], '#123456')
        # o escalão refaz o desenho (III: o eixo partido e três traços)
        self.assertEqual(self._props('boundary')['echelon'], 'III')
        g = next(f for k, f in feicoes_2d(self.doc.data).items() if k[2] == self.ids['boundary'])['geometry']
        self.assertEqual((g['type'], len(g['coordinates'])), ('MultiLineString', 5))
        # SIDC: as chaves do painel do Web acompanham, e o bitmap velho não viaja
        p = self._props('military_symbol')
        self.assertEqual((p['sidc'][3], p['standardIdentity']), ('6', '6'))
        self.assertNotIn(self.ids['military_symbol'], self.doc.imagens)
        # Seta: o eixo novo em baseCoordinates e o contorno refeito pelo estilo (Polygon arredondado)
        p = self._props('arrow')
        self.assertAlmostEqual(p['baseCoordinates'][1][0], -48.06 + 0.01, places=9)
        g = next(f for k, f in feicoes_2d(self.doc.data).items() if k[2] == self.ids['arrow'])['geometry']
        self.assertEqual(g['type'], 'Polygon')
        self.assertTrue(all(round(c[0], 6) == c[0] for c in g['coordinates'][0]))
        # círculo transladado: o centro anda junto
        c0 = next(f for k, f in feicoes_2d(self.orig.data).items() if k[2] == self.ids['circle'])['properties']['center']
        c1 = self._props('circle')['center']
        self.assertAlmostEqual(c1[0] - c0[0], 0.002, places=9)
        self.assertAlmostEqual(c1[1] - c0[1], -0.001, places=9)
        # apagada
        self.assertEqual(self.por_id[self.ids['text']][0][1], 'feição ausente')

    def test_regua_reprova_edicao_perdida(self):
        """Pior caso: o arquivo exportado SEM as edições (o original) não passa nas asserções acima."""
        dif, _ = comparar_feicoes(self.orig.data, self.orig.data)
        self.assertNotEqual(set(k[2] for k in dif), set(self.ids.values()))


def _canvas():
    cv = QgsMapCanvas()
    cv.resize(800, 600)
    cv.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    cv.setExtent(QgsRectangle(-47.95, -15.83, -47.85, -15.755))
    cv.refresh()
    return cv


def _clique(cv, ft, x, y, botao=Qt.MouseButton.LeftButton):
    ft.canvasReleaseEvent(QgsMapMouseEvent(cv, QEvent.Type.MouseButtonRelease, QPoint(x, y), botao, botao,
                                           Qt.KeyboardModifier.NoModifier))


def calco_desktop():
    """Um calco novo com uma feição de cada ferramenta, criada pelo gesto dela (uma vez por execução)."""
    if 'desktop' in _CACHE:
        return _CACHE['desktop']
    from Calco.calco import Calco, definir_calco_ativo
    from Calco.ferramentas import FerramentaLinha, FerramentaPoligono, FerramentaPonto
    from Calco.azimute import gravacao, geometria as G
    cam = os.path.join(TMP, 'desktop.gpkg')
    c = Calco(cam)
    c.criar()
    c.carregar(estilizar_novas=False)
    definir_calco_ativo(c)
    cv = _canvas()

    def preparar(tipo, _p, a):
        if tipo == 'military_symbol':
            a['sidc'], a['unique_designation'] = '10031000161211000000', '1 BI'
        return a
    _clique(cv, FerramentaPonto(cv, 'military_symbol', preparar_atributos=preparar), 150, 120)
    _clique(cv, FerramentaPonto(cv, 'coordination_measure'), 300, 120)
    ft = FerramentaLinha(cv, 'coordination_line')
    _clique(cv, ft, 80, 220), _clique(cv, ft, 300, 240), _clique(cv, ft, 500, 220, Qt.MouseButton.RightButton)
    ft = FerramentaPoligono(cv, 'coordination_area')
    for x, y in ((520, 80), (720, 90), (700, 230)):
        _clique(cv, ft, x, y)
    _clique(cv, ft, 540, 220, Qt.MouseButton.RightButton)
    ft = FerramentaLinha(cv, 'boundary')
    _clique(cv, ft, 80, 330), _clique(cv, ft, 400, 350), _clique(cv, ft, 720, 320, Qt.MouseButton.RightButton)
    ft = FerramentaLinha(cv, 'arrow')
    _clique(cv, ft, 100, 470), _clique(cv, ft, 350, 430), _clique(cv, ft, 600, 470, Qt.MouseButton.RightButton)
    gravacao.criar(c, {'referencePoint': [-47.88, -15.815], 'outputMode': G.ROTA, 'angularUnit': G.GRAUS,
                       'distanceUnit': G.METROS, 'northReference': G.NV, 'magneticDeclination': -22.0,
                       'meridianConvergence': 0.76,
                       'legs': [{'azimuth': 45, 'distance': 1500}, {'azimuth': 120, 'distance': 1200}]}, 13.0)
    del ft
    _CACHE['desktop'] = cam
    return cam


class TestCriadasNoDesktop(unittest.TestCase):
    """Uma feição de cada ferramenta, pelo gesto da ferramenta, num calco novo."""

    ESPERADO = {
        'military_symbols': ('Point', ['sidc', 'standardIdentity', 'mainIcon', 'echelon', 'createdAtZoom', 'size']),
        'coordination_measures': ('Point', ['pointCode', 'echelonCode', 'size', 'createdAtZoom']),
        'coordination_lines': ('MultiLineString', ['baseCoordinates', 'symbol_code', 'symbol_size', 'color']),
        'coordination_areas': ('Polygon', ['baseCoordinates', 'symbol_code', 'symbol_size', 'minas']),
        'boundarys': ('MultiLineString', ['baseCoordinates', 'echelon', 'symbol_instances', 'symbol_size']),
        'arrows': ('Polygon', ['baseCoordinates', 'width', 'geometryType']),
        'lines': ('LineString', ['baseCoordinates', 'featureType', 'azimuthDistanceData']),
    }
    COMUNS = ['id', 'source', 'layerId', 'nome', 'visivel', 'bloqueado', 'createdAt', 'updatedAt', 'attributes',
              'images']

    @classmethod
    def setUpClass(cls):
        cls.cam = calco_desktop()
        cls.doc, cls.exp = exportar(cls.cam)

    def test_uma_de_cada_no_formato_do_web(self):
        m = self.doc.data['maps']['Principal']['features']
        print('\ncriadas no Desktop:', {b: len(l) for b, l in m.items() if l})
        for balde, (tipo_geo, chaves) in self.ESPERADO.items():
            self.assertEqual(len(m[balde]), 1, balde)
            f = m[balde][0]
            self.assertEqual(f['geometry']['type'], tipo_geo, balde)
            # a feição do Azimute leva as chaves que o Web grava nela (sem attributes nem images)
            comuns = [k for k in self.COMUNS if balde != 'lines' or k not in ('attributes', 'images')]
            faltam = [k for k in comuns + chaves if k not in f['properties']]
            self.assertEqual(faltam, [], balde)
            self.assertEqual(f['properties']['layerId'], 'default')
            self.assertEqual(f['properties']['source'], schema.BALDE_PARA_TIPO[balde])
        self.assertEqual(self.exp.relatorio.total(), 7)

    def test_desenho_da_seta_e_do_limite(self):
        m = self.doc.data['maps']['Principal']['features']
        seta = QgsGeometry.fromWkt(_wkt(m['arrows'][0]['geometry']))
        eixo = m['arrows'][0]['properties']['baseCoordinates']
        self.assertTrue(seta.contains(QgsGeometry.fromPointXY(QgsPointXY(*eixo[1]))))
        self.assertGreater(len(m['boundarys'][0]['geometry']['coordinates']), 2)  # eixo partido e o XXX

    def test_regua_de_chaves_reprova_pior_caso(self):
        f = copy.deepcopy(self.doc.data['maps']['Principal']['features']['boundarys'][0])
        del f['properties']['baseCoordinates']
        self.assertIn('baseCoordinates', [k for k in self.COMUNS + self.ESPERADO['boundarys'][1]
                                          if k not in f['properties']])


def _wkt(g):
    from osgeo import ogr
    return ogr.CreateGeometryFromJson(json.dumps(g)).ExportToIsoWkt()


def _hausdorff_m(a, b):
    """Hausdorff (m) entre duas geometrias GeoJSON, numa Transversa de Mercator local (R do turf)."""
    from qgis.core import QgsCoordinateTransform
    ga, gb = QgsGeometry.fromWkt(_wkt(a)), QgsGeometry.fromWkt(_wkt(b))
    c = ga.centroid().asPoint()
    crs = QgsCoordinateReferenceSystem('PROJ:+proj=tmerc +lat_0={} +lon_0={} +R=6371008.8 +units=m'.format(c.y(), c.x()))
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), crs, QgsProject.instance())
    ga.transform(tr)
    gb.transform(tr)
    return ga.hausdorffDistance(gb)


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestLimiteDeCirculo(unittest.TestCase):
    """
    K2: o Limite de escalão em círculo ('o', 'oo', 'ooo') criado no Desktop vai ao .ebgeo com o vão em
    volta do símbolo, como o Web o grava (createLineWithGaps de add_boundary_geometry.js). Os três da
    fixture 06 viram feições do Desktop (id novo, sem props) e o desenho exportado é comparado com a
    geometria que o próprio Web gravou neles: o mesmo número de trechos e o desvio da paridade do Limite.
    """

    ESCALOES = ('o', 'oo', 'ooo')

    @classmethod
    def setUpClass(cls):
        import uuid
        cam = copia_06('limite_circulo')
        l = _camada(cam, 'boundary')
        cls.web = {}
        l.startEditing()
        for f in l.getFeatures():
            if f['echelon'] in cls.ESCALOES:
                novo = str(uuid.uuid4())
                cls.web[novo] = f['echelon']
                l.changeAttributeValue(f.id(), l.fields().indexOf('ebgeo_id'), novo)
                l.changeAttributeValue(f.id(), l.fields().indexOf('props'), None)
        assert l.commitChanges(), l.commitErrors()
        orig = leitor.abrir(FIXTURE_06)
        cls.gravado = {}
        for k, f in feicoes_2d(orig.data).items():
            if k[1] == 'boundarys' and f['properties'].get('echelon') in cls.ESCALOES:
                cls.gravado[f['properties']['echelon']] = f['geometry']
        cls.doc, cls.exp = exportar(cam)

    def test_vao_como_o_web(self):
        self.assertEqual(sorted(self.web.values()), sorted(self.ESCALOES))
        saida = {k[2]: f for k, f in feicoes_2d(self.doc.data).items() if k[2] in self.web}
        self.assertEqual(set(saida), set(self.web))
        for eid, ech in self.web.items():
            g, w = saida[eid]['geometry'], self.gravado[ech]
            d = _hausdorff_m(w, g)
            print('\nLimite {!r} criado no Desktop: {} trechos (Web {}), Hausdorff {:.2f} m'.format(
                ech, len(g['coordinates']), len(w['coordinates']), d))
            self.assertEqual((g['type'], len(g['coordinates'])), (w['type'], len(w['coordinates'])), ech)
            self.assertLess(d, 1.5, ech)
        self.assertEqual([a for a in self.exp.relatorio.avisos if 'Limite' in a], [])

    def test_regua_reprova_eixo_inteiro(self):
        """Pior caso: o eixo inteiro (a reserva de antes) tem um trecho só e passa longe do vão."""
        for eid, ech in self.web.items():
            p = next(f for k, f in feicoes_2d(self.doc.data).items() if k[2] == eid)['properties']
            eixo = {'type': 'MultiLineString', 'coordinates': [p['baseCoordinates']]}
            w = self.gravado[ech]
            self.assertTrue(len(eixo['coordinates']) != len(w['coordinates']) or _hausdorff_m(w, eixo) >= 1.5, ech)


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestArvore(unittest.TestCase):
    """O atlas no projeto: estado das camadas, mapa atual e a feição desenhada numa camada dele."""

    MAPA = '10 Camadas e grupos'

    @classmethod
    def setUpClass(cls):
        from Calco.importador import arvore
        cls.arvore = arvore
        cls.cam = copia_06('arvore')
        cls.projeto = QgsProject.instance()
        cls.atlas = arvore.montar_arvore(cls.cam, cls.projeto)
        g = next(x for x in cls.atlas.children() if x.customProperty(arvore.PROP_MAPA) == cls.MAPA)
        arvore.materializar_mapa(g, cls.projeto)
        g.setItemVisibilityChecked(True)  # o grupo do atlas é exclusivo: liga este e desliga o atual
        cls.grupo = g

    def test_estado_vai_ao_arquivo(self):
        subs = [s for s in self.grupo.children() if s.customProperty(self.arvore.PROP_CAMADA)]
        sub = subs[-1]
        cid = sub.customProperty(self.arvore.PROP_CAMADA)
        sub.setItemVisibilityChecked(False)
        for n in sub.findLayers():
            n.layer().setOpacity(0.5)
            n.layer().setReadOnly(True)
        estado = desenho.estado_da_arvore(self.cam, self.projeto)
        self.assertEqual(estado['mapa_atual'], self.MAPA)
        doc, _ = exportar(self.cam, estado=estado, nome='arvore_estado')
        camada = next(l for l in doc.data['layers'][self.MAPA] if l['id'] == cid)
        self.assertEqual((camada['visible'], camada['opacity'], camada['locked']), (False, 0.5, True))
        self.assertEqual(doc.data['currentMap'], self.MAPA)
        # sem a árvore, ficam os valores da tabela (o original): a régua reprova o estado anterior
        doc2, _ = exportar(self.cam, nome='arvore_sem_estado')
        camada2 = next(l for l in doc2.data['layers'][self.MAPA] if l['id'] == cid)
        self.assertNotEqual((camada2['visible'], camada2['opacity'], camada2['locked']), (False, 0.5, True))
        self.assertEqual(doc2.data['currentMap'], 'Principal')
        sub.setItemVisibilityChecked(True)
        for n in sub.findLayers():
            n.layer().setOpacity(1.0)
            n.layer().setReadOnly(False)

    def test_desenhada_na_camada_do_atlas_vai_ao_mapa_e_a_camada_dela(self):
        from Calco.calco import Calco, definir_calco_ativo, PROP_TIPO
        from Calco.ferramentas import FerramentaPonto
        alvo = next(n.layer() for n in self.grupo.findLayers()
                    if n.layer().customProperty(PROP_TIPO) == 'military_symbol')
        cid = alvo.customProperty(self.arvore.PROP_CAMADA)
        definir_calco_ativo(Calco(self.cam))

        class Iface:
            def activeLayer(self):
                return alvo
        cv = _canvas()
        p = alvo.getFeatures().__next__().geometry().asPoint()
        cv.setExtent(QgsRectangle(p.x() - 0.05, p.y() - 0.05, p.x() + 0.05, p.y() + 0.05))
        ft = FerramentaPonto(cv, 'military_symbol', Iface())
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append((l, e)))
        _clique(cv, ft, 400, 300)
        self.assertEqual(len(criadas), 1)
        self.assertIs(criadas[0][0], alvo)
        doc, _ = exportar(self.cam, nome='arvore_desenhada')
        achadas = [(k[0], f['properties']['layerId']) for k, f in feicoes_2d(doc.data).items() if k[2] == criadas[0][1]]
        self.assertEqual(achadas, [(self.MAPA, cid)])
        # e o filtro da camada em que foi desenhada a mostra (antes ela nascia em Principal/default e sumia)
        self.assertIn(criadas[0][1], [f['ebgeo_id'] for f in alvo.getFeatures()])


class TestAlgoritmo(unittest.TestCase):
    def test_algoritmo_e_conferencia(self):
        from Calco.exportador.algoritmo import ExportarEbgeo
        cam = calco_desktop()
        alg = ExportarEbgeo().create()
        alg.initAlgorithm()
        ctx, fb = QgsProcessingContext(), QgsProcessingFeedback()
        ctx.setProject(QgsProject.instance())
        saida = os.path.join(TMP, 'algoritmo.ebgeo')
        res, ok = alg.run({'CALCO': cam, 'ESCOPO': 1, 'SAIDA': saida}, ctx, fb)
        self.assertTrue(ok)
        self.assertEqual((res['FEICOES'], res['NOVAS']), (7, 6))
        self.assertEqual(leitor.abrir(saida).data['version'], '3.0')
        # pior caso: GeoPackage que não existe recusa com a mensagem do exportador
        try:
            _r, ok2 = alg.run({'CALCO': os.path.join(TMP, 'nao.gpkg'), 'ESCOPO': 0,
                               'SAIDA': os.path.join(TMP, 'nao.ebgeo')}, ctx, fb)
            self.assertFalse(ok2)
        except Exception as e:
            self.assertIn('GeoPackage', str(e))

    def test_acao_do_menu(self):
        from qgis.testing.mocked import get_iface
        from qgis.PyQt.QtWidgets import QMenu, QMessageBox
        from qgis import processing
        from Calco.calco import Calco, definir_calco_ativo
        from Calco.gerenciador import GerenciadorCalco
        cam = os.path.join(TMP, 'menu.gpkg')
        c = Calco(cam)
        c.criar()
        lyr = c.carregar(estilizar_novas=False)['military_symbol']
        definir_calco_ativo(c)
        g = GerenciadorCalco(get_iface(), QMenu('EBGeo'))
        g.initGui()
        acao = next(a for a in g.acoes if a.text() == 'Exportar arquivo .ebgeo...')
        self.assertFalse(acao.icon().isNull())
        chamadas = []
        original = processing.execAlgorithmDialog
        processing.execAlgorithmDialog = lambda alg, params=None: chamadas.append((alg, params))
        try:
            acao.trigger()
            self.assertEqual(chamadas, [('EBGeoProvider:exportarebgeo', {'CALCO': c.caminho})])
            # edição pendente: Cancelar não abre o diálogo; Salvar grava e abre
            lyr.startEditing()
            from qgis.core import QgsFeature
            nova = QgsFeature(lyr.fields())
            nova.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(-47.9, -15.8)))
            nova.setAttribute(lyr.fields().indexOf('ebgeo_id'), 'pendente')
            lyr.addFeature(nova)
            botoes = QMessageBox.StandardButton
            self.assertIsNone(g.exportar_ebgeo(perguntar=lambda _t: botoes.Cancel))
            self.assertEqual(len(chamadas), 1)
            g.exportar_ebgeo(perguntar=lambda _t: botoes.Save)
            self.assertEqual(len(chamadas), 2)
            self.assertFalse(lyr.isModified())
            self.assertEqual([x['ebgeo_id'] for x in _camada(cam, 'military_symbol').getFeatures()], ['pendente'])
        finally:
            processing.execAlgorithmDialog = original
            if lyr.isEditable():
                lyr.rollBack()
            g.unload()


# ---------------------------------------------------------------- o Web, em node

NODE_HARNESS = r'''
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join, basename } from 'node:path';
import { tmpdir } from 'node:os';
import { createHash } from 'node:crypto';
const [frontend, saida, ...arquivos] = process.argv.slice(2);
const js = join(frontend, 'src', 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-web-'));
const req = createRequire(join(frontend, 'package.json'));
const ALIAS = { '@js/': js, '@store/': join(js, 'store'), '@utils/': join(js, 'utilities'), '@state/': join(js, 'state'),
  '@tools/': join(js, 'tool_manager'), '@layers/': join(js, 'layers'), '@events/': join(js, 'events'), '@ui/': join(js, 'ui') };
const hooks = join(dir, 'hooks.mjs');
writeFileSync(hooks, `
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const ALIAS = ${JSON.stringify(ALIAS)};
const JSZIP = ${JSON.stringify(pathToFileURL(req.resolve('jszip')).href)};
export async function resolve(spec, ctx, next) {
  if (spec === 'jszip') return { url: JSZIP, shortCircuit: true };
  for (const [p, d] of Object.entries(ALIAS)) {
    if (spec.startsWith(p)) return { url: pathToFileURL(join(d, spec.slice(p.length))).href, shortCircuit: true };
  }
  return next(spec, ctx);
}
`);
register(pathToFileURL(hooks).href);
const imp = (p) => import(pathToFileURL(join(js, ...p.split('/'))).href);
const gate = await imp('import_export/ebgeo-file-gate.js');
const norm = await imp('import_export/import-normalize.js');
const out = [];
for (const caminho of arquivos) {
  const bytes = readFileSync(caminho);
  const { zip, data } = await gate.readEbgeoArchive(new File([bytes], basename(caminho)));
  const maps = {};
  for (const [nome, mapa] of Object.entries(data.maps)) {
    const r = norm.normalizeMapDataForCurrentVersion(structuredClone(mapa), (l) => ({ processed: l, unavailableCount: 0 }));
    delete r.mapData.sync;
    maps[nome] = r.mapData;
  }
  const imagens = {};
  for (const n of Object.keys(zip.files)) {
    const m = /^images\/([^/]+)\.(png|jpe?g|svg|webp)$/i.exec(n);
    if (m) imagens[m[1]] = createHash('sha256').update(Buffer.from(await zip.file(n).async('uint8array'))).digest('hex');
  }
  const { maps: _m, ...secoes } = data;
  out.push({ recusa: gate.importVersionRefusal(data), v1: gate.isV1Format(data), maps, secoes, imagens });
}
writeFileSync(saida, JSON.stringify(out));
'''


def rodar_web(arquivos):
    web = os.environ.get('EBGEO_WEB') or os.environ.get('EBGEO_WEB_DIR')
    node = os.environ.get('EBGEO_NODE') or shutil.which('node')
    if not web or not node:
        return None
    d = tempfile.mkdtemp(prefix='ebgeo_web_')
    script, saida = os.path.join(d, 'importar.mjs'), os.path.join(d, 'saida.json')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(NODE_HARNESS)
    r = subprocess.run([node, script, os.path.join(web, 'frontend'), saida] + list(arquivos),
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        raise AssertionError('node falhou: ' + r.stderr[-3000:])
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh)


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06 ausente')
class TestWeb(unittest.TestCase):
    def test_o_web_le_igual(self):
        exportar(copia_06('web'))
        exportar(calco_desktop())
        arquivos = [FIXTURE_06, os.path.join(TMP, 'web.ebgeo'), os.path.join(TMP, 'desktop.ebgeo')]
        r = rodar_web(arquivos)
        if r is None:
            self.skipTest('EBGEO_WEB/EBGEO_WEB_DIR ou node ausente')
        orig, volta = r[0], r[1]
        for x in r:
            self.assertIsNone(x['recusa'])
            self.assertFalse(x['v1'])
        self.assertEqual(divergencias(orig['maps'], volta['maps']), [])
        self.assertEqual(divergencias(orig['secoes'], volta['secoes']), [])
        self.assertEqual(orig['imagens'], volta['imagens'])
        self.assertEqual(sum(len(l) for l in r[2]['maps']['Principal']['features'].values()), 7)
        # pior caso: um mapa com uma chave a menos o Web vê diferente
        degradado = copy.deepcopy(volta['maps'])
        next(iter(degradado.values()))['features']['points'][0]['properties'].pop('nome')
        self.assertTrue(divergencias(orig['maps'], degradado))


if __name__ == '__main__':
    print('fixtures:', FIXTURES)
    print('saída temporária:', TMP)
    r = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if r.wasSuccessful() else 1)
