# -*- coding: utf-8 -*-
"""
Testes do importador .ebgeo, rodáveis com o Python do QGIS 4:

    python-qgis.bat EBGeo/Calco/testes/test_importador.py

As fixtures vêm da variável de ambiente EBGEO_FIXTURES; sem ela, do diretório
irmão ../_ebgeo_dados_teste relativo à raiz do repositório. Os PNGs de render
ficam em pasta temporária (o caminho é impresso) para conferência visual.

Toda conferência relê o GeoPackage gravado (nunca o retorno do escritor) e cada
régua é provada contra um pior caso que ela tem de reprovar.
"""
import base64
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, os.path.join(RAIZ_REPO, 'EBGeo'))

FIXTURES = os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste')
FIXTURES = os.path.abspath(FIXTURES)

from osgeo import ogr  # noqa: E402

ogr.UseExceptions()

from qgis.core import (  # noqa: E402
    QgsApplication, QgsProject, QgsVectorLayer, QgsMapSettings, QgsMapRendererSequentialJob,
    QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRenderContext,
    QgsRuleBasedRenderer, QgsSingleSymbolRenderer, QgsLayerTreeGroup, QgsFeatureRequest,
)
from qgis.PyQt.QtCore import QSize, QCoreApplication  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], False)
    _APP.initQgis()

from Calco import schema  # noqa: E402
from Calco.importador import leitor, escritor, arvore  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_importador_')

# Contagem por balde medida nas cinco fixtures da linha 2.x (01, 02, 03, 04, 05); None = balde ausente.
CONTAGEM_POR_BALDE = {
    'points': (168, 1, 381, 381, 381), 'lines': (42, 0, 80, 80, 80), 'polygons': (7, 0, 68, 68, 68),
    'texts': (2, 0, 19, 19, 19), 'images': (4, 0, 11, 11, 11), 'circles': (22, 0, 42, 42, 42),
    'ellipses': (1, 0, 5, 5, 5), 'rectangles': (1, 0, 5, 5, 5), 'setores': (1, 0, 6, 6, 6),
    'brushes': (1, 0, 5, 5, 5), 'arrows': (1, 0, 8, 8, 8), 'boundarys': (1, 0, 7, 7, 7),
    'occupied_fronts': (1, 0, 4, 4, 4), 'coordination_lines': (0, 0, 11, 11, None),
    'military_symbols': (6, 0, 93, 93, 93), 'coordination_measures': (1, 0, 38, 20, 20),
    'magnetic_declinations': (1, 0, 4, 4, 4), 'los': (1, 0, 3, 3, 3), 'visibility': (1, 0, 3, 3, 3),
    'processed_los': (0, 0, 6, 6, 6), 'processed_visibility': (0, 0, 6, 6, 6),
}
ARQUIVOS = ['01-completo.ebgeo', '02-minimo.ebgeo', '03-completo-2.4.ebgeo',
            '04-completo-2.3.ebgeo', '05-completo-2.2.ebgeo']
FIXTURE_30 = '06-completo-3.0.ebgeo'
RELATORIO_30 = '_relatorio-de-geracao-3.0.json'


def esperado_por_balde(i):
    out = {}
    for balde, ns in CONTAGEM_POR_BALDE.items():
        if ns[i]:
            out[schema.BALDE_PARA_TIPO[balde]] = ns[i]
    return out


def _gravar(caminho, b):
    with open(caminho, 'wb') as fh:
        fh.write(b)


def _ler(caminho):
    with open(caminho, 'rb') as fh:
        return fh.read()


def fixture(nome):
    return os.path.join(FIXTURES, nome)


def bruto_do_arquivo(caminho):
    """Abre o .ebgeo SEM o leitor do plugin (instrumento independente)."""
    with open(caminho, 'rb') as fh:
        raw = fh.read()
    corpo = bytes(b ^ 0xAA for b in raw[6:]) if raw[:6] == b'EBGXOR' else raw
    z = zipfile.ZipFile(io.BytesIO(corpo))
    return z, json.loads(z.read('data.json').decode('utf-8'))


def contagem_bruta(data):
    """balde -> n direto do data.json, com barrier_lines contando como coordination_line."""
    out = {}
    for m in data['maps'].values():
        for balde, lst in (m.get('features') or {}).items():
            if balde == 'coordenadas' or not lst:
                continue
            tipo = 'coordination_line' if balde == 'barrier_lines' else schema.BALDE_PARA_TIPO.get(balde)
            if tipo:
                out[tipo] = out.get(tipo, 0) + len(lst)
    return out


def montar_ebgeo(data, imagens=(), mascarar=True, sem_data=False, guardar=zipfile.ZIP_DEFLATED):
    """Monta um .ebgeo (pior caso) a partir de um data.json e de [(nome, bytes)]."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', guardar) as z:
        if not sem_data:
            z.writestr('data.json', json.dumps(data, ensure_ascii=False).encode('utf-8'))
        for nome, b in imagens:
            z.writestr(nome, b)
    corpo = buf.getvalue()
    return b'EBGXOR' + bytes(b ^ 0xAA for b in corpo) if mascarar else corpo


def importar(nome_fixture, sufixo=''):
    destino = os.path.join(TMP, os.path.splitext(os.path.basename(nome_fixture))[0] + sufixo + '.gpkg')
    rel = escritor.importar(nome_fixture if os.path.isabs(nome_fixture) else fixture(nome_fixture), destino)
    return destino, rel


def linha_gpkg(caminho, tabela, ebgeo_id):
    ds = ogr.Open(caminho)
    lyr = ds.GetLayerByName(tabela)
    lyr.SetAttributeFilter("ebgeo_id = '{}'".format(ebgeo_id.replace("'", "''")))
    f = lyr.GetNextFeature()
    if f is None:
        return None, None
    d = {lyr.GetLayerDefn().GetFieldDefn(i).GetName(): f.GetField(i) for i in range(f.GetFieldCount())}
    g = f.GetGeometryRef()
    return d, (json.loads(g.ExportToJson()) if g else None)


def _iso_ms(v):
    import datetime
    s = str(v).replace('/', '-')
    if s.endswith('+00'):
        s = s[:-3] + '+00:00'
    return int(round(datetime.datetime.fromisoformat(s).timestamp() * 1000))


def divergencias(tipo, props, linha):
    """Confere coluna a coluna (schema.mapa_web) contra as properties do data.json. Lista de divergências."""
    erros = []
    tipos = {c[0]: (c[1], c[2]) for c in schema.campos(tipo)}
    for web, col in schema.mapa_web(tipo).items():
        tp, padrao = tipos[col]
        obtido = linha.get(col)
        if web == 'layerId':
            esperado = props.get('layerId') or 'default'
        elif web in props:
            esperado = props[web]
        else:
            esperado = json.loads(padrao) if (tp == 'json' and isinstance(padrao, str)) else padrao
        if esperado is None:
            if obtido is not None:
                erros.append((col, None, obtido))
            continue
        if tp == 'json':
            ok = obtido is not None and json.loads(obtido) == esperado
        elif tp == 'bool':
            ok = obtido is not None and bool(obtido) == bool(esperado)
        elif tp == 'real':
            try:
                ok = obtido is not None and math.isclose(float(obtido), float(esperado), rel_tol=1e-9, abs_tol=1e-9)
            except (TypeError, ValueError):
                ok = obtido is None
        elif tp == 'datetime':
            ok = obtido is not None and _iso_ms(obtido) == int(esperado)
        else:
            ok = obtido == (esperado if isinstance(esperado, str) else
                            json.dumps(esperado, ensure_ascii=False) if isinstance(esperado, (dict, list)) else str(esperado))
        if not ok:
            erros.append((col, esperado, obtido))
    if json.loads(linha['props']) != props:
        erros.append(('props', '...', '...'))
    return erros


# ---------------------------------------------------------------- leitor: piores casos

class TestLeitorPioresCasos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.z03, cls.d03 = bruto_do_arquivo(fixture('03-completo-2.4.ebgeo'))
        with open(fixture('03-completo-2.4.ebgeo'), 'rb') as fh:
            cls.raw03 = fh.read()
        cls.z02, cls.d02 = bruto_do_arquivo(fixture('02-minimo.ebgeo'))

    def test_arquivo_real_abre(self):
        doc = leitor.abrir_bytes(self.raw03, '03.ebgeo')
        self.assertEqual(doc.versao, '2.4')
        self.assertEqual(len(doc.imagens), 149)

    def test_truncado(self):
        for corte in (len(self.raw03) // 2, len(self.raw03) - 10):
            with self.assertRaises(leitor.ErroEbgeo) as cm:
                leitor.abrir_bytes(self.raw03[:corte], 'truncado.ebgeo')
            self.assertIn('corrompido', str(cm.exception))

    def test_versao_31_recusada(self):
        for chave in ('version', 'schemaVersion'):
            d = dict(self.d02)
            d[chave] = '3.1'
            with self.assertRaises(leitor.ErroEbgeo) as cm:
                leitor.abrir_bytes(montar_ebgeo(d), 'v31.ebgeo')
            self.assertIn('mais nova que o plugin', str(cm.exception))
        d = dict(self.d02, atlas={'schemaVersion': '3.1'})
        with self.assertRaises(leitor.ErroEbgeo):
            leitor.abrir_bytes(montar_ebgeo(d), 'atlas31.ebgeo')
        # a régua aprova a fronteira: 3.0 e 1.3 passam, 1.2 e '2.x' não
        for v, passa in (('3.0', True), ('1.3', True), ('1.2', False), ('2.x', False)):
            d = dict(self.d02, version=v)
            if passa:
                leitor.abrir_bytes(montar_ebgeo(d), 'v.ebgeo')
            else:
                self.assertRaises(leitor.ErroEbgeo, leitor.abrir_bytes, montar_ebgeo(d), 'v.ebgeo')

    def test_zip_sem_data_json(self):
        with self.assertRaises(leitor.ErroEbgeo) as cm:
            leitor.abrir_bytes(montar_ebgeo({}, [('images/x.png', b'\x89PNG\r\n\x1a\n')], sem_data=True), 's.ebgeo')
        self.assertIn('data.json não encontrado', str(cm.exception))

    def test_imagem_duplicada(self):
        nome = [n for n in self.z03.namelist() if n.startswith('images/') and n.endswith('.png')][0]
        b = self.z03.read(nome)
        dup = nome[:-4] + '.jpg'
        with self.assertRaises(leitor.ErroEbgeo) as cm:
            leitor.abrir_bytes(montar_ebgeo(self.d03, [(nome, b), (dup, b)]), 'dup.ebgeo')
        self.assertIn('ambíguo', str(cm.exception))
        # sem o duplicado, o mesmo arquivo abre (a régua não reprova por outro motivo)
        leitor.abrir_bytes(montar_ebgeo(self.d03, [(nome, b)]), 'ok.ebgeo')

    def test_crc(self):
        corpo = montar_ebgeo(self.d02, [('images/a.png', b'\x89PNG\r\n\x1a\n' + b'A' * 200)],
                             mascarar=False, guardar=zipfile.ZIP_STORED)
        i = corpo.find(b'A' * 200)
        ruim = corpo[:i] + b'B' + corpo[i + 1:]
        with self.assertRaises(leitor.ErroEbgeo) as cm:
            leitor.abrir_bytes(ruim, 'crc.ebgeo')
        self.assertIn('CRC', str(cm.exception))
        leitor.abrir_bytes(corpo, 'crc_ok.ebgeo')

    def test_mime_farejado(self):
        jpeg = b'\xff\xd8\xff\xe0' + b'0' * 20
        doc = leitor.abrir_bytes(montar_ebgeo(self.d02, [('images/j.png', jpeg)]), 'm.ebgeo')
        self.assertEqual(doc.imagens['j'][1], 'image/jpeg')

    def test_barreira_e_balde_decide(self):
        d = json.loads(json.dumps(self.d02))
        mapa = d['maps']['Principal']['features']
        mapa['barrier_lines'] = [{'type': 'Feature', 'properties': {'id': 'b1', 'source': 'barrier_line'},
                                  'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}}]
        mapa['processed_los'] = [{'type': 'Feature', 'properties': {'id': 'p1-visible', 'source': 'los'},
                                  'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}}]
        doc = leitor.abrir_bytes(montar_ebgeo(d), 'b.ebgeo')
        c = leitor.contar_por_tipo(doc)
        self.assertEqual(c.get('coordination_line'), 1)
        self.assertEqual(c.get('processed_los'), 1)
        self.assertNotIn('los', c)
        ft = leitor.normalizar_baldes(mapa)['coordination_line'][0]['properties']
        self.assertEqual((ft['symbol_code'], ft['baseCoordinates']), ('290199', [[0, 0], [1, 1]]))


# ---------------------------------------------------------------- contagem relida do GPKG

class TestContagem(unittest.TestCase):

    def test_contagem_por_balde_nas_cinco(self):
        for i, nome in enumerate(ARQUIVOS):
            with self.subTest(fixture=nome):
                destino, rel = importar(nome)
                relido = escritor.contar_gpkg(destino)          # a prova: releitura
                self.assertEqual(relido, esperado_por_balde(i))
                # instrumento independente do leitor: o data.json cru
                self.assertEqual(relido, contagem_bruta(bruto_do_arquivo(fixture(nome))[1]))
                self.assertEqual(rel.descartadas, [])
                print('  {}: {} feições relidas, {} por tipo'.format(nome, sum(relido.values()), len(relido)))

    def test_regua_reprova_perda(self):
        """Pior caso: apagar uma feição do GPKG real tem de fazer a régua divergir."""
        destino, _ = importar('03-completo-2.4.ebgeo', '_perda')
        ds = ogr.Open(destino, 1)
        ds.ExecuteSQL('DELETE FROM point WHERE fid = (SELECT min(fid) FROM point)')
        ds = None
        self.assertNotEqual(escritor.contar_gpkg(destino), esperado_por_balde(2))

    def test_fixture_30(self):
        caminho = fixture(FIXTURE_30)
        if not os.path.exists(caminho):
            self.skipTest('fixture {} ausente em {}: gere-a e rode de novo'.format(FIXTURE_30, FIXTURES))
        destino, rel = importar(FIXTURE_30)
        relido = escritor.contar_gpkg(destino)
        esperado = contagens_do_relatorio(fixture(RELATORIO_30))
        bruto = contagem_bruta(bruto_do_arquivo(caminho)[1])
        if esperado is None:
            print('  AVISO: {} sem contagem por balde legível; conferido contra o data.json cru'.format(RELATORIO_30))
            esperado = bruto
        self.assertEqual(relido, esperado)
        self.assertEqual(relido, bruto)
        self.assertEqual(rel.descartadas, [])
        print('  {}: {} feições relidas'.format(FIXTURE_30, sum(relido.values())))


def contagens_do_relatorio(caminho):
    """Procura no relatório de geração um dicionário balde -> n (formato não fixado). None se não achar."""
    if not os.path.exists(caminho):
        return None
    rel = json.load(open(caminho, encoding='utf-8'))
    conhecidos = set(schema.BALDE_PARA_TIPO) | {'barrier_lines', 'coordenadas'}
    achados = []

    def busca(x):
        if isinstance(x, dict):
            chaves = [k for k in x if k in conhecidos]
            if len(chaves) >= 3 and all(isinstance(x[k], int) for k in chaves):
                achados.append(x)
            for v in x.values():
                busca(v)
        elif isinstance(x, list):
            for v in x:
                busca(v)
    busca(rel)
    if not achados:
        return None
    melhor = max(achados, key=lambda d: sum(1 for k in d if k in conhecidos))
    out = {}
    for balde, n in melhor.items():
        tipo = 'coordination_line' if balde == 'barrier_lines' else schema.BALDE_PARA_TIPO.get(balde)
        if tipo and n:
            out[tipo] = out.get(tipo, 0) + n
    return out


# ---------------------------------------------------------------- campo a campo

class TestCampoACampo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.destino, _ = importar('03-completo-2.4.ebgeo', '_campos')
        cls.zip, cls.data = bruto_do_arquivo(fixture('03-completo-2.4.ebgeo'))
        cls.primeira = {}
        for nome in cls.data['mapOrder']:
            for balde, lst in cls.data['maps'][nome]['features'].items():
                tipo = schema.BALDE_PARA_TIPO.get(balde)
                if tipo and lst and tipo not in cls.primeira:
                    cls.primeira[tipo] = (nome, lst[0])

    def test_uma_feicao_por_tipo(self):
        # a fixture 03 (esquema 2.4) é anterior à Engenharia e à Área de Coordenação
        presentes = [t for t in schema.TIPOS if t not in ('engineering_symbol', 'coordination_area')]
        self.assertEqual(sorted(self.primeira), sorted(presentes))
        for tipo, (mapa, ft) in self.primeira.items():
            with self.subTest(tipo=tipo):
                p = ft['properties']
                linha, geom = linha_gpkg(self.destino, schema.TIPOS[tipo]['tabela'], p['id'])
                self.assertIsNotNone(linha, 'feição {} não está no GPKG'.format(p['id']))
                self.assertEqual(linha['mapa'], mapa)
                self.assertEqual(divergencias(tipo, p, linha), [])
                self._geometria(tipo, ft, p, linha, geom)
                if 'bitmap_b64' in linha:
                    nomes = [n for n in self.zip.namelist() if n.startswith('images/' + p['id'] + '.')]
                    if nomes:
                        self.assertEqual(base64.b64decode(linha['bitmap_b64']), self.zip.read(nomes[0]))

    def _geometria(self, tipo, ft, p, linha, geom):
        g = ft['geometry']
        if tipo in ('boundary', 'coordination_line', 'occupied_front'):
            self.assertEqual(geom['type'], 'LineString')
            self.assertEqual([c[:2] for c in geom['coordinates']], [[float(x), float(y)] for x, y in p['baseCoordinates']])
            self.assertEqual(json.loads(ogr.CreateGeometryFromWkt(linha['geom_desenho']).ExportToJson())['type'], g['type'])
        elif tipo == 'arrow':
            self.assertEqual(geom['type'], 'MultiLineString')
            self.assertEqual(geom['coordinates'][0], [[float(x), float(y)] for x, y in p['baseCoordinates']])
        elif g['type'] == 'Point':
            self.assertEqual(geom['coordinates'][:2], g['coordinates'])
        elif g['type'] == 'Polygon':
            self.assertEqual(geom['type'], 'MultiPolygon')
            self.assertEqual(geom['coordinates'][0][0][:3], g['coordinates'][0][:3])
        elif g['type'] == 'LineString' and schema.TIPOS[tipo]['geometria'] == 'MultiLineString':
            self.assertEqual(geom['coordinates'][0], g['coordinates'])

    def test_regua_reprova_linha_trocada(self):
        """Pior caso: conferir a linha de uma feição contra as properties de OUTRA reprova."""
        pts = [m['features']['points'] for m in self.data['maps'].values() if len(m['features'].get('points', [])) > 1][0]
        ft, outra = pts[0], pts[1]['properties']
        linha, _ = linha_gpkg(self.destino, 'point', ft['properties']['id'])
        self.assertTrue(divergencias('point', outra, linha))
        # e cada eixo (str, real, bool, json, datetime) reprova sozinho
        for col, val in (('fill_color', '#000001'), ('size', 999.0), ('show_label', 0 if linha['show_label'] else 1),
                         ('atributos', '{"x": "y"}'), ('criado_em', '2001/01/01 00:00:00+00')):
            ruim = dict(linha, **{col: val})
            cols = [e[0] for e in divergencias('point', ft['properties'], ruim)]
            self.assertIn(col, cols)

    def test_tabelas_de_apoio(self):
        ds = ogr.Open(self.destino)
        n = lambda t: ds.GetLayerByName(t).GetFeatureCount()
        self.assertEqual(n('ebgeo_mapa'), len(self.data['maps']))
        self.assertEqual(n('ebgeo_icone'), len(self.data['customIcons']))
        self.assertEqual(n('ebgeo_grupo'), sum(len(g) for g in self.data['groups'].values()))
        doc = ds.GetLayerByName('ebgeo_documento').GetNextFeature()
        self.assertEqual(json.loads(doc.GetField('data_json')), self.data)
        import hashlib
        self.assertEqual(doc.GetField('sha256'),
                         hashlib.sha256(_ler(fixture('03-completo-2.4.ebgeo'))).hexdigest())
        fotos = sum(len(f['properties'].get('images') or []) for m in self.data['maps'].values()
                    for lst in m['features'].values() for f in lst)
        self.assertEqual(n('ebgeo_foto'), fotos)
        lyr = ds.GetLayerByName('ebgeo_foto')
        self.assertEqual(sum(1 for f in lyr if f.GetField('bitmap_b64')), fotos)

    def test_pior_caso_01(self):
        """A 01 (nomes que o Web não lê, formas como Point) entra inteira e regenera as formas."""
        destino, rel = importar('01-completo.ebgeo', '_campos')
        ds = ogr.Open(destino)
        for t in ('circle', 'ellipse', 'sector', 'visibility'):
            lyr = ds.GetLayerByName(t)
            for f in lyr:
                g = f.GetGeometryRef()
                self.assertEqual(g.GetGeometryName(), 'MULTIPOLYGON', t)
                self.assertGreater(g.GetGeometryRef(0).GetGeometryRef(0).GetPointCount(), 16, t)
                self.assertIn('regenerado_de_ponto', json.loads(f.GetField('parametros')))

    def test_antimeridiano(self):
        ds = ogr.Open(self.destino)
        lyr = ds.GetLayerByName('line')
        lyr.SetAttributeFilter("mapa = '14 Bordas'")
        larguras = [f.GetGeometryRef().GetEnvelope() for f in lyr]
        envs = [e for e in larguras if max(abs(e[0]), abs(e[1])) > 179]
        self.assertTrue(envs)
        for e in envs:
            self.assertLess(e[1] - e[0], 1.0, 'linha atravessa o mundo: {}'.format(e))


# ---------------------------------------------------------------- árvore

def _projeto_limpo():
    p = QgsProject.instance()
    p.clear()
    return p


def _grupo_mapa(atlas, nome):
    return [c for c in atlas.children() if c.customProperty(arvore.PROP_MAPA) == nome][0]


def _processar_eventos():
    for _ in range(5):
        QCoreApplication.processEvents()


class TestArvore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.destino, _ = importar('03-completo-2.4.ebgeo', '_arvore')
        cls.estilos = arvore.salvar_estilos(cls.destino)
        print('  estilos por tipo:', cls.estilos)

    def setUp(self):
        self.proj = _projeto_limpo()
        self.atlas = arvore.montar_arvore(self.destino, self.proj)

    def test_grupos_por_mapa_e_preguica(self):
        self.assertTrue(self.atlas.isMutuallyExclusive())
        mapas = [c for c in self.atlas.children() if isinstance(c, QgsLayerTreeGroup)]
        self.assertEqual(len(mapas), 14)
        ligados = [c.customProperty(arvore.PROP_MAPA) for c in mapas if c.itemVisibilityChecked()]
        self.assertEqual(ligados, ['Principal'])
        g10 = _grupo_mapa(self.atlas, '10 Camadas')
        self.assertTrue(g10.customProperty(arvore.PROP_PENDENTE))
        self.assertEqual(g10.findLayers(), [])
        n_antes = len(self.proj.mapLayers())
        g10.setItemVisibilityChecked(True)            # ligar o grupo materializa
        _processar_eventos()
        self.assertFalse(g10.customProperty(arvore.PROP_PENDENTE))
        self.assertGreater(len(self.proj.mapLayers()), n_antes)
        self.assertFalse(_grupo_mapa(self.atlas, 'Principal').itemVisibilityChecked())
        print('  camadas: Principal {}, depois de ligar "10 Camadas" {}'.format(n_antes, len(self.proj.mapLayers())))
        # a entrada da linha de visada nasce desligada (o Web a desenha com opacidade zero)
        nos_los = [n for n in _grupo_mapa(self.atlas, 'Principal').findLayers()
                   if n.layer().customProperty(arvore.PROP_TIPO) == 'los']
        self.assertTrue(nos_los)
        self.assertFalse(any(n.itemVisibilityChecked() for n in nos_los))

    def test_religar_depois_de_reabrir_o_projeto(self):
        qgz = os.path.join(TMP, 'projeto_atlas.qgz')
        self.assertTrue(self.proj.write(qgz))
        self.proj.clear()
        self.assertTrue(self.proj.read(qgz))
        atlas = [g for g in self.proj.layerTreeRoot().children() if g.customProperty(arvore.PROP_ATLAS)][0]
        self.assertEqual(arvore.religar(self.proj), 1)
        g = _grupo_mapa(atlas, '06 Medidas')
        self.assertEqual(g.findLayers(), [])
        g.setItemVisibilityChecked(True)
        _processar_eventos()
        self.assertTrue(g.findLayers())

    def test_mapa_10_camadas(self):
        g10 = _grupo_mapa(self.atlas, '10 Camadas')
        arvore.materializar_mapa(g10, self.proj)
        subs = {c.name(): c for c in g10.children()}
        self.assertEqual(list(subs), ['Inteligência (S2)', 'Vazia', 'Semitransparente', 'Manobra',
                                      'Bloqueada', 'Logística', 'Oculta', 'Padrão'])
        for nome, sub in subs.items():
            camadas = [n.layer() for n in sub.findLayers()]
            if nome == 'Vazia':
                self.assertEqual(camadas, [])
                continue
            self.assertTrue(camadas, nome)
            self.assertEqual(sub.itemVisibilityChecked(), nome != 'Oculta', nome)
            for l in camadas:
                self.assertEqual(l.readOnly(), nome == 'Bloqueada', (nome, l.name()))
                self.assertAlmostEqual(l.opacity(), 0.35 if nome == 'Semitransparente' else 1.0, msg=nome)
                self.assertGreater(l.featureCount(), 0)
                self.assertIn('"camada_id"', l.subsetString())
        # ordem customizada igual à pilha do Web (topo primeiro)
        ordem = [l.customProperty(arvore.PROP_TIPO) for l in self.proj.layerTreeRoot().customLayerOrder()
                 if l.customProperty(arvore.PROP_MAPA) == '10 Camadas']
        idx = [schema.PILHA_DESENHO.index(t) for t in ordem]
        self.assertTrue(self.proj.layerTreeRoot().hasCustomLayerOrder())
        self.assertEqual(idx, sorted(idx, reverse=True), ordem)
        # pior caso: a régua de ordem reprova a ordem da árvore (camada por camada)
        arv = [n.layer().customProperty(arvore.PROP_TIPO) for n in g10.findLayers()]
        idx_arv = [schema.PILHA_DESENHO.index(t) for t in arv]
        self.assertNotEqual(idx_arv, sorted(idx_arv, reverse=True))

    def test_regra_visivel_e_grupo_oculto(self):
        """Pior caso degradado do arquivo real: 1 ponto com visivel falso e o Grupo 1 oculto."""
        _z, data = bruto_do_arquivo(fixture('03-completo-2.4.ebgeo'))
        mapa_pts = [n for n in data['mapOrder'] if len(data['maps'][n]['features'].get('points', [])) > 1][0]
        pontos = data['maps'][mapa_pts]['features']['points']
        pontos[0]['properties']['visivel'] = False
        alvo_oculto, alvo_visivel = pontos[0]['properties']['id'], pontos[1]['properties']['id']
        g1 = [g for g in data['groups']['11 Grupos'].values() if g['name'] == 'Grupo 1'][0]
        g1['visible'] = False
        membros = {r['id'] for r in g1['features']}
        caminho = os.path.join(TMP, 'degradado.ebgeo')
        _gravar(caminho, montar_ebgeo(data, [(n, _z.read(n)) for n in _z.namelist()
                                                      if n.startswith('images/') and not n.endswith('/')]))
        destino, _ = importar(caminho)
        proj = _projeto_limpo()
        atlas = arvore.montar_arvore(destino, proj, materializar='todos')

        def desenhadas(mapa, tipo):
            out = set()
            for no in _grupo_mapa(atlas, mapa).findLayers():
                l = no.layer()
                if l.customProperty(arvore.PROP_TIPO) != tipo:
                    continue
                ctx = QgsRenderContext()
                r = l.renderer().clone()
                r.startRender(ctx, l.fields())
                for f in l.getFeatures():
                    ctx.expressionContext().setFeature(f)
                    if r.willRenderFeature(f, ctx):
                        out.add(f['ebgeo_id'])
                r.stopRender(ctx)
            return out

        principal = desenhadas(mapa_pts, 'point')
        self.assertNotIn(alvo_oculto, principal)
        self.assertIn(alvo_visivel, principal)
        grupos = desenhadas('11 Grupos', 'point')
        self.assertTrue(grupos)
        self.assertFalse(grupos & membros)
        # a mesma régua no GPKG sem degradação desenha o ponto e os membros
        proj = _projeto_limpo()
        atlas = arvore.montar_arvore(self.destino, proj, materializar='todos')
        self.assertIn(alvo_oculto, desenhadas(mapa_pts, 'point'))
        self.assertTrue(desenhadas('11 Grupos', 'point') & membros)


# ---------------------------------------------------------------- render e estilo salvo

def _render(proj, atlas, mapa, png, tamanho=(1400, 1000)):
    g = _grupo_mapa(atlas, mapa)
    arvore.materializar_mapa(g, proj)
    camadas = [n.layer() for n in g.findLayers()
               if n.itemVisibilityChecked() and n.parent().itemVisibilityChecked()]
    ordem = [l for l in proj.layerTreeRoot().customLayerOrder() if l in camadas]
    ext = QgsRectangle()
    for l in ordem:
        ext.combineExtentWith(l.extent())
    ext.scale(1.1)
    merc = QgsCoordinateReferenceSystem('EPSG:3857')
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), merc, proj)
    ms = QgsMapSettings()
    ms.setLayers(ordem)
    ms.setDestinationCrs(merc)
    ms.setExtent(tr.transformBoundingBox(ext))
    ms.setOutputSize(QSize(*tamanho))
    ms.setBackgroundColor(QColor('#f4f1e8'))
    job = QgsMapRendererSequentialJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    img.save(png)
    return img, len(ordem)


def _tinta(img):
    fundo = QColor('#f4f1e8').rgb()
    n = 0
    for y in range(0, img.height(), 4):
        for x in range(0, img.width(), 4):
            if img.pixel(x, y) != fundo:
                n += 1
    return n


class TestRenderEEstiloSalvo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.destino, _ = importar('03-completo-2.4.ebgeo', '_render')
        arvore.salvar_estilos(cls.destino)

    def test_render_tres_mapas(self):
        proj = _projeto_limpo()
        atlas = arvore.montar_arvore(self.destino, proj)
        pasta = os.path.join(TMP, 'render')
        os.makedirs(pasta, exist_ok=True)
        for mapa in ('Principal', '02 Estilos', '07 Táticas'):
            png = os.path.join(pasta, mapa.replace(' ', '_') + '.png')
            img, n = _render(proj, atlas, mapa, png)
            tinta = _tinta(img)
            print('  render {}: {} camadas, {} amostras com tinta -> {}'.format(mapa, n, tinta, png))
            self.assertGreater(tinta, 500, mapa)
        # pior caso: o mesmo quadro sem camadas não tem tinta
        ms = QgsMapSettings()
        ms.setOutputSize(QSize(400, 300))
        ms.setBackgroundColor(QColor('#f4f1e8'))
        ms.setExtent(QgsRectangle(0, 0, 1, 1))
        job = QgsMapRendererSequentialJob(ms)
        job.start()
        job.waitForFinished()
        self.assertEqual(_tinta(job.renderedImage()), 0)

    def test_estilo_salvo_reabre_sem_plugin(self):
        for tabela, classe in (('polygon', 'QgsRuleBasedRenderer'), ('point', 'QgsRuleBasedRenderer'),
                               ('line', 'QgsRuleBasedRenderer')):
            l = QgsVectorLayer('{}|layername={}'.format(self.destino, tabela), tabela, 'ogr')
            self.assertTrue(l.isValid())
            self.assertEqual(type(l.renderer()).__name__, classe, tabela)
            xml = l.renderer().dump() if hasattr(l.renderer(), 'dump') else ''
            n, _ids, _nomes, _d, _m = l.listStylesInDatabase()
            self.assertGreaterEqual(n, 1)
        l = QgsVectorLayer('{}|layername=text'.format(self.destino), 'text', 'ogr')
        self.assertTrue(l.labelsEnabled())
        # pior caso: o mesmo GPKG sem layer_styles reabre com o símbolo único padrão
        cru, _ = importar('03-completo-2.4.ebgeo', '_cru')
        l = QgsVectorLayer('{}|layername=polygon'.format(cru), 'polygon', 'ogr')
        self.assertIsInstance(l.renderer(), QgsSingleSymbolRenderer)


# ---------------------------------------------------------------- estilo: cada propriedade desenha

def _sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _expressoes_do_estilo(layer):
    """Todas as expressões definidas por dado do renderer e do rótulo da camada."""
    from qgis.core import QgsPalLayerSettings
    out = []

    def do_simbolo(sim):
        if sim is None:
            return
        props = sim.dataDefinedProperties()
        out.extend(props.property(k).expressionString() for k in props.propertyKeys())
        for sl in sim.symbolLayers():
            p = sl.dataDefinedProperties()
            out.extend(p.property(k).expressionString() for k in p.propertyKeys())
            do_simbolo(sl.subSymbol())

    r = layer.renderer()
    ctx = QgsRenderContext()
    for sim in (r.symbols(ctx) if r else []):
        do_simbolo(sim)
    if isinstance(r, QgsRuleBasedRenderer):
        out.extend(x.filterExpression() for x in r.rootRule().descendants())
    lab = layer.labeling()
    if lab is not None:
        for prov in lab.subProviders() or ['']:
            s = lab.settings(prov)
            dd = s.dataDefinedProperties()
            out.extend(dd.property(k).expressionString() for k in dd.propertyKeys())
    return [e for e in out if e]


class TestExpressoesDoEstilo(unittest.TestCase):
    """Toda expressão de estilo dos tipos comuns tem de ser válida (CASE simples não existe no QGIS)."""

    def test_sem_erro_de_sintaxe(self):
        from qgis.core import QgsExpression
        from Calco import estilos_formas
        destino, _ = importar('03-completo-2.4.ebgeo', '_expr')
        erros, total = [], 0
        for tipo in estilos_formas.TIPOS + ('military_symbol', 'boundary'):
            l = QgsVectorLayer('{}|layername={}'.format(destino, tipo), tipo, 'ogr')
            if tipo in estilos_formas.TIPOS:
                estilos_formas.aplicar_estilo(l, tipo)
            else:
                estilos_formas.estilo_simples(l, tipo)
            for e in _expressoes_do_estilo(l):
                total += 1
                q = QgsExpression(e)
                if q.hasParserError():
                    erros.append((tipo, q.parserErrorString(), e[:80]))
        print('  {} expressões de estilo verificadas'.format(total))
        self.assertGreater(total, 50)
        self.assertEqual(erros, [])
        # pior caso: a régua acusa o CASE simples
        self.assertTrue(QgsExpression("CASE \"a\" WHEN 'x' THEN 1 END").hasParserError())


class TestEstiloPorPropriedade(unittest.TestCase):
    """
    Para cada propriedade de estilo que o Web desenha: duas versões da MESMA feição real
    (controle e alterada) renderizadas sozinhas têm de dar imagens diferentes.
    """

    BASE = {
        'point': {'zoom_corr': 0, 'marker_symbol': 'circle', 'show_label': 1, 'label_text': 'Ab',
                  'opacity': 1, 'size': 12, 'line_width': 2},
        'line': {'line_style': 'solid', 'opacity': 1, 'line_width': 4},
        'polygon': {'hatch_enabled': 0, 'hatch_type': 'none', 'line_style': 'solid', 'opacity': 0.5,
                    'show_label': 0, 'line_width': 3},
        'text': {'zoom_corr': 0, 'show_background': 0, 'rotation': 0, 'size': 22, 'halo_width': 2,
                 'halo_color': '#ffcc00'},
        'image': {'zoom_corr': 0, 'rotation': 0, 'opacity': 1, 'size': 0.5},
        'brush': {'zoom_corr': 0, 'line_width': 6},
    }

    @classmethod
    def setUpClass(cls):
        cls.destino, _ = importar('03-completo-2.4.ebgeo', '_estilo')
        _z, data = bruto_do_arquivo(fixture('03-completo-2.4.ebgeo'))
        cls.icone = data['customIcons'][0]['id']
        ds = ogr.Open(cls.destino, 1)
        cls.fid = {}
        for tipo, base in cls.BASE.items():
            r = ds.ExecuteSQL("SELECT min(fid) FROM {} WHERE mapa = 'Principal'".format(tipo))
            cls.fid[tipo] = r.GetNextFeature().GetField(0)
            ds.ReleaseResultSet(r)
            sets = ', '.join('{} = {}'.format(k, _sql_val(v)) for k, v in base.items())
            ds.ExecuteSQL('UPDATE {} SET {} WHERE fid = {}'.format(tipo, sets, cls.fid[tipo]))
        ds = None
        cls.pasta = os.path.join(TMP, 'estilo_por_propriedade')
        os.makedirs(cls.pasta, exist_ok=True)

    def _render(self, tipo, mudanca, nome):
        ds = ogr.Open(self.destino, 1)
        antigos = {}
        lyr = ds.GetLayerByName(tipo)
        f = lyr.GetFeature(self.fid[tipo])
        for k in mudanca:
            antigos[k] = f.GetField(k)
        if mudanca:
            ds.ExecuteSQL('UPDATE {} SET {} WHERE fid = {}'.format(
                tipo, ', '.join('{} = {}'.format(k, _sql_val(v)) for k, v in mudanca.items()), self.fid[tipo]))
        ds = None
        try:
            l = QgsVectorLayer('{}|layername={}|subset="fid" = {}'.format(self.destino, tipo, self.fid[tipo]), tipo, 'ogr')
            arvore.estilizar(l, tipo)
            ext = l.extent()
            if ext.width() < 1e-6:
                ext = QgsRectangle(ext.xMinimum() - 0.01, ext.yMinimum() - 0.01, ext.xMaximum() + 0.01, ext.yMaximum() + 0.01)
            else:
                ext.scale(1.3)
            ms = QgsMapSettings()
            ms.setLayers([l])
            ms.setDestinationCrs(l.crs())
            ms.setExtent(ext)
            ms.setOutputSize(QSize(300, 300))
            ms.setBackgroundColor(QColor('#ffffff'))
            job = QgsMapRendererSequentialJob(ms)
            job.start()
            job.waitForFinished()
            img = job.renderedImage()
            img.save(os.path.join(self.pasta, '{}_{}.png'.format(tipo, nome)))
            return img
        finally:
            if mudanca:
                ds = ogr.Open(self.destino, 1)
                ds.ExecuteSQL('UPDATE {} SET {} WHERE fid = {}'.format(
                    tipo, ', '.join('{} = {}'.format(k, _sql_val(v)) for k, v in antigos.items()), self.fid[tipo]))
                ds = None

    @staticmethod
    def _diferenca(a, b):
        n = 0
        for y in range(0, a.height(), 2):
            for x in range(0, a.width(), 2):
                if a.pixel(x, y) != b.pixel(x, y):
                    n += 1
        return n

    def _pares(self):
        hd = {'hatch_enabled': 1, 'hatch_type': 'diagonal-right'}
        return {
            'point': [
                ('fill_color', {}, {'fill_color': '#ff0000'}), ('line_color', {}, {'line_color': '#00ff00'}),
                ('line_width', {}, {'line_width': 8}), ('size', {}, {'size': 25}), ('opacity', {}, {'opacity': 0.3}),
                ('forma', {}, {'marker_symbol': 'square'}), ('forma_x', {}, {'marker_symbol': 'x-mark'}),
                ('icone', {'marker_symbol': 'car'}, {'marker_symbol': 'plane'}),
                ('icone_vs_circulo', {}, {'marker_symbol': 'fire'}),
                ('custom', {}, {'marker_symbol': 'custom:' + self.icone}),
                ('label_text', {}, {'label_text': 'Zz'}), ('label_color', {}, {'label_color': '#ff0000'}),
                ('label_size', {}, {'label_size': 30}), ('label_outline_color', {}, {'label_outline_color': '#ff00ff'}),
                ('label_outline_width', {}, {'label_outline_width': 5}), ('show_label', {}, {'show_label': 0}),
            ],
            'line': [
                ('line_color', {}, {'line_color': '#ff0000'}), ('line_width', {}, {'line_width': 10}),
                ('line_style', {}, {'line_style': 'dashed'}), ('opacity', {}, {'opacity': 0.3}),
                ('dashed_vs_dotted', {'line_style': 'dashed'}, {'line_style': 'dotted'}),
            ],
            'polygon': [
                ('fill_color', {}, {'fill_color': '#ff0000'}), ('line_color', {}, {'line_color': '#ff0000'}),
                ('line_width', {}, {'line_width': 8}), ('line_style', {}, {'line_style': 'dashed'}),
                ('opacity', {}, {'opacity': 0.9}), ('hachura', {}, hd),
                ('hatch_type', hd, dict(hd, hatch_type='cross')), ('hatch_dots', hd, dict(hd, hatch_type='dots')),
                ('hatch_spacing', hd, dict(hd, hatch_spacing=20)), ('hatch_line_width', hd, dict(hd, hatch_line_width=5)),
                ('rotulo', {}, {'show_label': 1, 'label_text': 'Área'}),
            ],
            'text': [
                ('text', {}, {'text': 'Outro texto'}), ('size', {}, {'size': 40}), ('color', {}, {'color': '#ff0000'}),
                ('halo_color', {}, {'halo_color': '#ff00ff'}), ('halo_width', {}, {'halo_width': 6}),
                ('rotation', {}, {'rotation': 45}), ('show_background', {}, {'show_background': 1}),
                ('bg_fill_color', {'show_background': 1}, {'show_background': 1, 'bg_fill_color': '#ff0000'}),
            ],
            'image': [
                ('size', {}, {'size': 1.0}), ('rotation', {}, {'rotation': 45}), ('opacity', {}, {'opacity': 0.3}),
            ],
            'brush': [
                ('line_color', {}, {'line_color': '#0000ff'}), ('line_width', {}, {'line_width': 14}),
            ],
        }

    def test_cada_propriedade_desenha(self):
        falhas = []
        for tipo, pares in self._pares().items():
            for nome, a, b in pares:
                ia = self._render(tipo, a, nome + '_a')
                ib = self._render(tipo, b, nome + '_b')
                d = self._diferenca(ia, ib)
                if d == 0:
                    falhas.append('{}.{}'.format(tipo, nome))
        print('  {} pares de estilo renderizados em {}'.format(sum(len(p) for p in self._pares().values()), self.pasta))
        self.assertEqual(falhas, [], 'propriedades gravadas que não mudam o desenho')

    def test_regua_reprova_propriedade_ignorada(self):
        """Pior caso: mudar uma coluna que nenhum estilo lê ('descricao') não altera o render."""
        a = self._render('point', {}, 'ctrl')
        b = self._render('point', {'descricao': 'outra coisa'}, 'descricao')
        self.assertEqual(self._diferenca(a, b), 0)

    def test_opacidade_so_no_preenchimento(self):
        img = self._render('polygon', {'opacity': 0}, 'opacidade_zero')
        self.assertGreater(_tinta_branco(img), 50, 'o contorno sumiu com opacity 0')


def _tinta_branco(img):
    n = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            if img.pixel(x, y) != QColor('#ffffff').rgb():
                n += 1
    return n


# ---------------------------------------------------------------- atributos livres e fotos

class TestAtributosEFotos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.destino, cls.rel = importar('03-completo-2.4.ebgeo', '_attr')
        cls.zip, cls.data = bruto_do_arquivo(fixture('03-completo-2.4.ebgeo'))

    def _alias_para_coluna(self, tabela):
        ds = ogr.Open(self.destino)
        defn = ds.GetLayerByName(tabela).GetLayerDefn()
        out = {}
        for i in range(defn.GetFieldCount()):
            fd = defn.GetFieldDefn(i)
            if fd.GetName().startswith('attr_'):
                out[fd.GetAlternativeName()] = fd.GetName()
        return out

    def test_atributos_viram_colunas(self):
        conferidos = 0
        for tipo in schema.TIPOS:
            balde = schema.TIPOS[tipo]['balde']
            alias = None
            for m in self.data['maps'].values():
                for ft in m['features'].get(balde, [])[:5]:
                    attrs = ft['properties'].get('attributes') or {}
                    if not attrs:
                        continue
                    alias = alias or self._alias_para_coluna(schema.TIPOS[tipo]['tabela'])
                    linha, _ = linha_gpkg(self.destino, schema.TIPOS[tipo]['tabela'], ft['properties']['id'])
                    for k, v in attrs.items():
                        self.assertIn(k, alias, (tipo, k))
                        self.assertEqual(linha[alias[k]], v, (tipo, k))
                        conferidos += 1
                    self.assertEqual(linha['nome'], ft['properties'].get('nome', ''))
                    self.assertEqual(linha['descricao'], ft['properties'].get('descricao', ''))
                    self.assertEqual(json.loads(linha['atributos']), attrs)
        self.assertGreater(conferidos, 100)
        print('  {} pares chave/valor de atributos conferidos no GPKG'.format(conferidos))
        # no QGIS a coluna aparece com o nome original como alias
        l = QgsVectorLayer('{}|layername=point'.format(self.destino), 'p', 'ogr')
        aliases = {f.alias() for f in l.fields() if f.name().startswith('attr_')}
        self.assertIn('Situação', aliases)

    def test_fotos_bytes_identicos(self):
        import hashlib
        ds = ogr.Open(self.destino)
        no_gpkg = {f.GetField('foto_id'): f.GetField('bitmap_b64') for f in ds.GetLayerByName('ebgeo_foto')}
        fotos = [im for m in self.data['maps'].values() for lst in m['features'].values()
                 for ft in lst for im in (ft['properties'].get('images') or [])]
        self.assertEqual(len(no_gpkg), len(fotos))
        for im in fotos:
            esperado = hashlib.sha256(base64.b64decode(im['data'].split(',', 1)[1])).hexdigest()
            self.assertEqual(hashlib.sha256(base64.b64decode(no_gpkg[im['id']])).hexdigest(), esperado, im['id'])
        print('  {} fotos com sha256 idêntico ao data.json'.format(len(fotos)))

    def test_foto_por_referencia_30(self):
        """Forma 3.0: a foto sem 'data' vem por referência em images/<id>."""
        z, data = self.zip, json.loads(json.dumps(self.data))
        ft = data['maps']['Principal']['features']['polygons'][0]
        foto = ft['properties']['images'][0]
        bytes_foto = base64.b64decode(foto.pop('data').split(',', 1)[1])
        imagens = [(n, z.read(n)) for n in z.namelist() if n.startswith('images/') and not n.endswith('/')]
        imagens.append(('images/{}.png'.format(foto['id']), bytes_foto))
        caminho = os.path.join(TMP, 'foto_ref.ebgeo')
        _gravar(caminho, montar_ebgeo(dict(data, version='3.0'), imagens))
        destino, _ = importar(caminho)
        ds = ogr.Open(destino)
        lyr = ds.GetLayerByName('ebgeo_foto')
        lyr.SetAttributeFilter("foto_id = '{}'".format(foto['id']))
        self.assertEqual(base64.b64decode(lyr.GetNextFeature().GetField('bitmap_b64')), bytes_foto)

    def test_fotos_visiveis_no_qgis(self):
        from qgis.PyQt.QtGui import QTextDocument
        from qgis.PyQt.QtCore import QUrl
        from qgis.core import QgsExpressionContext, QgsExpressionContextUtils, QgsExpression
        proj = _projeto_limpo()
        atlas = arvore.montar_arvore(self.destino, proj)
        fotos = arvore.camada_fotos(self.destino, proj, criar=False)
        self.assertIsNotNone(fotos)
        self.assertIsNotNone(proj.layerTreeRoot().findLayer(fotos.id()))
        ft = self.data['maps']['Principal']['features']['polygons'][0]['properties']
        camada = [n.layer() for n in _grupo_mapa(atlas, 'Principal').findLayers()
                  if n.layer().customProperty(arvore.PROP_TIPO) == 'polygon'
                  and n.layer().customProperty(arvore.PROP_CAMADA) == ft['layerId']][0]
        rels = proj.relationManager().referencedRelations(camada)
        self.assertEqual(len(rels), 1)
        f = next(camada.getFeatures("\"ebgeo_id\" = '{}'".format(ft['id'])))
        self.assertEqual(len(list(rels[0].getRelatedFeatures(f))), len(ft['images']))
        ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(camada))
        ctx.setFeature(f)
        html = QgsExpression.replaceExpressionText(camada.mapTipTemplate(), ctx)
        self.assertEqual(html.count('<img'), len(ft['images']))
        # o Qt decodifica a data URL que o maptip e o formulário usam
        src = html.split('src="', 1)[1].split('"', 1)[0]
        doc = QTextDocument()
        doc.setHtml(html)
        img = doc.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(src))
        self.assertTrue(img is not None and not QImage(img).isNull())
        # pior caso: feição sem foto não tem imagem no maptip
        com_foto = {x['ebgeo_id'] for x in fotos.getFeatures()}
        dona, outra = next((no.layer(), g) for no in atlas.findLayers() for g in no.layer().getFeatures()
                           if g['ebgeo_id'] not in com_foto)
        ctx2 = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(dona))
        ctx2.setFeature(outra)
        self.assertNotIn('<img', QgsExpression.replaceExpressionText(dona.mapTipTemplate(), ctx2))


# ---------------------------------------------------------------- algoritmo de Processing

class TestAlgoritmo(unittest.TestCase):

    def test_roda_o_algoritmo(self):
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback, QgsProcessingException
        from Calco.importador.algoritmo import ImportarEbgeo
        proj = _projeto_limpo()
        alg = ImportarEbgeo().create()
        alg.initAlgorithm()
        self.assertEqual((alg.name(), alg.displayName()), ('importarebgeo', 'Importar arquivo .ebgeo'))
        ctx = QgsProcessingContext()
        ctx.setProject(proj)
        fb = QgsProcessingFeedback()
        saida = os.path.join(TMP, 'algoritmo.gpkg')
        res, ok = alg.run({'ARQUIVO': fixture('03-completo-2.4.ebgeo'), 'SAIDA': saida, 'CARREGAR': True}, ctx, fb)
        self.assertTrue(ok)
        self.assertEqual(res['FEICOES'], 805)
        self.assertEqual(sum(escritor.contar_gpkg(saida).values()), 805)
        atlas = [g for g in proj.layerTreeRoot().children() if g.customProperty(arvore.PROP_ATLAS)]
        self.assertEqual(len(atlas), 1)
        self.assertGreater(len(proj.mapLayers()), 10)
        # pior caso: arquivo recusado não grava e devolve a mensagem do leitor
        ruim = os.path.join(TMP, 'ruim.ebgeo')
        with open(ruim, 'wb') as fh:
            fh.write(b'EBGXOR' + b'\x00' * 100)
        alg2 = ImportarEbgeo().create()
        alg2.initAlgorithm()
        fb2 = QgsProcessingFeedback()
        try:
            _res2, ok2 = alg2.run({'ARQUIVO': ruim, 'SAIDA': os.path.join(TMP, 'ruim.gpkg'), 'CARREGAR': False},
                                  ctx, fb2)
            self.assertFalse(ok2)
        except QgsProcessingException as e:
            self.assertIn('corrompido', str(e))
        self.assertFalse(os.path.exists(os.path.join(TMP, 'ruim.gpkg')))


if __name__ == '__main__':
    print('fixtures:', FIXTURES)
    print('saída temporária:', TMP)
    unittest.main(verbosity=2, exit=False)
