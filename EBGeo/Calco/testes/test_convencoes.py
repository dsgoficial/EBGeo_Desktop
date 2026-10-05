# -*- coding: utf-8 -*-
"""
Quadro de convenções do calco no layout de impressão (convencoes.py).

A fixture 06 (esquema 3.0) entra pelo importador do Calco, e o layout ganha um mapa com mapas do
atlas. O quadro tem de trazer UMA linha por símbolo distinto que o mapa desenha, com a figura e
o nome certo, agrupada e ordenada, e sobreviver a salvar e reabrir o projeto. A conferência
(`conferir`) lê o LAYOUT montado e compara com o que um instrumento independente tira do
GeoPackage pelo OGR (símbolos distintos das feições visíveis, fora dos grupos e camadas ocultos
do EBGeo); ela é provada antes contra o quadro real degradado (linha duplicada, linha a menos,
nome trocado, figura apagada) e tem de reprovar cada um.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_convencoes.py
Os PNG ficam em EBGEO_TESTE_SAIDA (padrão: pasta temporária, impressa no fim).
"""
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QPA_FONTDIR', os.path.join(os.environ.get('WINDIR', ''), 'Fonts'))
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, os.path.join(RAIZ_REPO, 'EBGeo'))
FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_30 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')

from osgeo import ogr  # noqa: E402

ogr.UseExceptions()

from qgis.core import (  # noqa: E402
    Qgis, QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsLayoutExporter,
    QgsLayoutItemLabel, QgsLayoutItemMap, QgsLayoutPoint, QgsLayoutSize, QgsPrintLayout,
    QgsProject, QgsRectangle,
)
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from Calco import convencoes as cv  # noqa: E402
from Calco.importador import arvore, escritor  # noqa: E402
from Calco.estilos_taticos import CATALOGO_LINHA  # noqa: E402
from Calco.estilos_area import CATALOGO_AREA  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_convencoes_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_convencoes_gpkg_')
GPKG = os.path.join(TMP, 'f06.gpkg')
DPI = 150

# Cena completa: linhas táticas (08), camadas e grupos com camada e grupo ocultos (10), feições
# invisíveis (03) e áreas de coordenação (15). Cena da extensão: símbolos de engenharia (07).
MAPAS_COMPLETO = ('03 ', '08 ', '10 ', '15 ')
MAPA_EXTENSAO = '07 '


def _texto(v):
    return '' if v is None else str(v)


# ---------------------------------------------------------------------------------------------
# Instrumento independente: o GeoPackage pelo OGR
# ---------------------------------------------------------------------------------------------

def _ocultos(ds):
    grupos, camadas = {}, set()
    for f in ds.GetLayerByName('ebgeo_grupo'):
        if f.GetField('visivel') in (0, False):
            grupos.setdefault(f.GetField('mapa'), set()).add(f.GetField('grupo_id'))
    for f in ds.GetLayerByName('ebgeo_camada'):
        if f.GetField('visivel') in (0, False):
            camadas.add((f.GetField('mapa'), f.GetField('camada_id')))
    return grupos, camadas


def _chave_ogr(tipo, f, cats):
    """O símbolo de uma linha do GeoPackage, lido direto das colunas (sem o módulo testado)."""
    g = f.GetField
    if tipo == 'military_symbol':
        s = ''.join(c for c in _texto(g('sidc')) if c.isdigit())
        return s + ('0760000000' if len(s) == 20 else '')
    if tipo == 'coordination_measure':
        pc = g('point_code')
        return (pc, g('echelon_code') if pc in cats['medida']['familias'] else '')
    if tipo == 'engineering_symbol':
        pc = g('point_code')
        item = [i for i in cats['engenharia']['itens'] if str(i['codigo']) == pc][0]
        eng = json.loads(g('engineering') or '{}')
        if len(item['variantes']) <= 1:
            return (pc, 0)
        fol = [c for c in item['campos'] if c['chave'] == 'foliage']
        if fol:  # Cobertura e Coberta: a folhagem decide o desenho
            valor = (eng.get('values') or {}).get('foliage') or fol[0]['padrao']
            return (pc, [o['valor'] for o in fol[0]['opcoes']].index(valor))
        return (pc, int(eng.get('variant') or 0))
    if tipo in ('coordination_line', 'coordination_area'):
        return g('symbol_code')
    if tipo == 'boundary':
        return g('echelon')
    if tipo == 'arrow':
        am, dh, hd = bool(g('airmobile')), bool(g('double_headed')), g('show_arrow_head') not in (0, False)
        return (am, dh and hd, hd)
    return {'occupied_front': 'frente', 'magnetic_declination': 'declinacao'}[tipo]  # um símbolo só


def esperado_ogr(mapas, recorte_4326=None):
    """{(tipo, chave)} das feições desenhadas nos mapas, opcionalmente só as que tocam o recorte."""
    cats = cv._catalogos()
    ds = ogr.Open(GPKG)
    grupos_ocultos, camadas_ocultas = _ocultos(ds)
    out = set()
    for tipo in cv.GRUPO_DO_TIPO:
        lyr = ds.GetLayerByName(tipo)
        if lyr is None:
            continue
        if recorte_4326 is not None:
            lyr.SetSpatialFilter(ogr.CreateGeometryFromWkt(recorte_4326.asWkt()))
        for f in lyr:
            mapa = f.GetField('mapa')
            if not any(mapa.startswith(m) for m in mapas):
                continue
            if f.GetField('visivel') in (0, False) or (mapa, f.GetField('camada_id')) in camadas_ocultas:
                continue
            gr = f.GetField('grupos')
            if gr and set(json.loads(gr)) & grupos_ocultos.get(mapa, set()):
                continue
            out.add((tipo, _chave_ogr(tipo, f, cats)))
        lyr.SetSpatialFilter(None)
    return out


def nome_esperado(tipo, chave):
    """Nome pelo catálogo, para os tipos de catálogo direto; None para os compostos (SIDC etc.)."""
    if tipo == 'coordination_line':
        return CATALOGO_LINHA[chave]['nome']
    if tipo == 'coordination_area':
        return CATALOGO_AREA[chave]['nome']
    if tipo == 'boundary':
        return 'Linha de Limite ({})'.format({'ooo': '•••', 'oo': '••', 'o': '•'}.get(chave, chave))
    if tipo == 'magnetic_declination':
        return 'Declinação Magnética'
    if tipo == 'occupied_front':
        return 'Frente Ocupada'
    if tipo == 'coordination_measure':
        pc, ec = chave
        return cv._catalogos()['medida']['porCodigo'][ec or pc]['nome']
    return None


# ---------------------------------------------------------------------------------------------
# Leitura do layout e conferência
# ---------------------------------------------------------------------------------------------

def itens(layout, mapa, papel):
    return [i for i in cv.itens_do_quadro(layout, mapa.uuid()) if i.customProperty(cv.PROP_PAPEL) == papel]


def linhas_do_quadro(layout, mapa):
    """[(texto do nome, item da figura ou None)], na ordem de leitura (coluna, depois y)."""
    nomes = sorted(itens(layout, mapa, 'nome'), key=lambda i: (round(i.pos().x()), i.pos().y()))
    figs = itens(layout, mapa, 'figura')
    out = []
    for lb in nomes:
        cy = lb.pos().y() + lb.rect().height() / 2
        par = [p for p in figs if abs(p.pos().x() + cv.FIG_L + cv.VAO - lb.pos().x()) < 0.5
               and abs(p.pos().y() + p.rect().height() / 2 - cy) < 0.5]
        out.append((' '.join(lb.text().split()), par[0] if len(par) == 1 else None))
    return out


def tinta(img, rect_mm, dpi):
    """Fração de pixels não brancos e não transparentes no retângulo (mm da página)."""
    f = dpi / 25.4
    x0, y0 = int(rect_mm.left() * f), int(rect_mm.top() * f)
    x1, y1 = int(rect_mm.right() * f), int(rect_mm.bottom() * f)
    n = tot = 0
    for y in range(max(0, y0), min(img.height(), y1), 2):
        for x in range(max(0, x0), min(img.width(), x1), 2):
            tot += 1
            c = QColor(img.pixel(x, y))
            if c.lightness() < 235:
                n += 1
    return n / tot if tot else 0.0


def conferir(layout, mapa, esperadas, img=None, dpi=DPI):
    """
    Problemas do quadro: nome duplicado, nome faltando ou sobrando contra `esperadas` (lista de
    nomes), linha sem figura, figura que não carrega e, com a imagem exportada, figura sem tinta.
    """
    problemas = []
    linhas = linhas_do_quadro(layout, mapa)
    nomes = [n for n, _p in linhas]
    vistos = set()
    for n in nomes:
        if n in vistos:
            problemas.append('duplicado: ' + n)
        vistos.add(n)
    for n in sorted(set(esperadas) - vistos):
        problemas.append('faltando: ' + n)
    for n in sorted(vistos - set(esperadas)):
        problemas.append('sobrando: ' + n)
    for n, pic in linhas:
        if pic is None:
            problemas.append('sem figura: ' + n)
            continue
        if pic.isMissingImage() or not pic.picturePath().startswith('base64:'):
            problemas.append('figura não carrega: ' + n)
        elif img is not None:
            r = pic.sceneBoundingRect()
            if tinta(img, r, dpi) < 0.004:
                problemas.append('figura em branco: ' + n)
    return problemas


def exportar(layout, nome):
    caminho = os.path.join(SAIDA, nome)
    s = QgsLayoutExporter.ImageExportSettings()
    s.dpi = DPI
    res = QgsLayoutExporter(layout).exportToImage(caminho, s)
    assert res == QgsLayoutExporter.ExportResult.Success, res
    img = QImage(caminho)
    assert not img.isNull()
    return img, caminho


# ---------------------------------------------------------------------------------------------
# Cenas
# ---------------------------------------------------------------------------------------------

_ATLAS = {}


def projeto_com_atlas():
    proj = QgsProject.instance()
    if 'atlas' in _ATLAS:
        return proj, _ATLAS['atlas']
    if not os.path.exists(GPKG):
        escritor.importar(FIXTURE_30, GPKG)
        arvore.salvar_estilos(GPKG)
    proj.setCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    _ATLAS['atlas'] = arvore.montar_arvore(GPKG, proj, materializar='todos')
    return proj, _ATLAS['atlas']


def camadas_visiveis_dos_mapas(atlas, prefixos):
    """As camadas dos mapas pedidos cujo subgrupo (camada do EBGeo) está ligado."""
    out = []
    for g in atlas.children():
        if not any(g.name().startswith(p) for p in prefixos):
            continue
        for sub in g.children():
            if not sub.itemVisibilityChecked():
                continue
            for no in sub.findLayers():
                if no.itemVisibilityChecked():
                    out.append(no.layer())
    return out


def novo_layout(proj, nome, largura=420, altura=297):
    lay = QgsPrintLayout(proj)
    lay.initializeDefaults()
    lay.setName(nome)
    lay.pageCollection().page(0).setPageSize(QgsLayoutSize(largura, altura))
    proj.layoutManager().addLayout(lay)
    return lay


def novo_mapa(lay, camadas, extensao_3857, x=10, y=10, largura=180, altura=277):
    m = QgsLayoutItemMap(lay)
    m.attemptMove(QgsLayoutPoint(x, y))
    m.attemptResize(QgsLayoutSize(largura, altura))
    m.setCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    m.setLayers(camadas)
    m.setKeepLayerSet(True)
    m.zoomToExtent(extensao_3857)
    lay.addLayoutItem(m)
    return m


def extensao_3857(camadas, fator=1.05):
    proj = QgsProject.instance()
    ext = QgsRectangle()
    for l in camadas:
        if l.featureCount():
            tr = QgsCoordinateTransform(l.crs(), QgsCoordinateReferenceSystem('EPSG:3857'), proj)
            ext.combineExtentWith(tr.transformBoundingBox(l.extent()))
    ext.scale(fator)
    return ext


def nomes_esperados(esperado, entradas):
    """Nome de cada (tipo, chave) esperado: pelo catálogo quando direto, senão o que o quadro deu."""
    por_chave = {(e.tipo, e.chave): e.nome for e in entradas}
    out = []
    for k in esperado:
        n = nome_esperado(*k)
        out.append(n if n is not None else por_chave.get(k, 'SEM ENTRADA: {}'.format(k)))
    return out


@unittest.skipUnless(os.path.exists(FIXTURE_30), 'fixture 06-completo-3.0.ebgeo ausente')
class TestQuadroConvencoes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.proj, cls.atlas = projeto_com_atlas()

    # ---------- nomes do catálogo ----------
    def test_nomes(self):
        self.assertEqual(cv.nome_sidc('100310001612110000000760000000'), 'Infantaria (Amigo, Batalhão)')
        self.assertEqual(cv.nome_sidc('100310001612110000000760008192'), 'Infantaria (Amigo, Batalhão, Comando)')
        self.assertEqual(cv.nome_sidc('10031000161211000000'), 'Infantaria (Amigo, Batalhão)')  # 20 dígitos
        self.assertEqual(cv.nome_sidc('100610001612110000000760000000'), 'Infantaria (Hostil, Batalhão)')
        self.assertEqual(cv.nome_medida('ECHELON', 'ECHELON_16'), 'Núcleo - Batalhão')
        self.assertEqual(cv.nome_medida('140500', 'ECHELON_16'), 'Setor de Tiro')
        self.assertEqual(cv.nome_engenharia('8'), 'Ponte, símbolo completo')  # sem travessão
        self.assertEqual(cv.nome_engenharia('5', 2), 'Rampas (11 a 14%)')
        item20 = [i for i in cv._catalogos()['engenharia']['itens'] if i['codigo'] == '20'][0]
        # o variant gravado não decide a Cobertura: a folhagem decide
        self.assertEqual(cv.variante_engenharia(item20, {'variant': 1, 'values': {'foliage': 'temporary'}}), 0)
        self.assertEqual(cv.variante_engenharia(item20, '{"variant": 0, "values": {"foliage": "permanent"}}'), 1)
        for nome in [cv.nome_engenharia(i['codigo'], v['indice']) for i in cv._catalogos()['engenharia']['itens']
                     for v in i['variantes']]:
            self.assertNotIn('\u2014', nome)

    # ---------- a régua reprova o quadro degradado ----------
    def test_conferencia_reprova_pior_caso(self):
        proj = self.proj
        camadas = camadas_visiveis_dos_mapas(self.atlas, ('15 ',))
        lay = novo_layout(proj, 'Pior caso')
        m = novo_mapa(lay, camadas, extensao_3857(camadas))
        grupo, entradas = cv.montar_quadro(lay, m)
        esperadas = nomes_esperados(esperado_ogr(('15 ',)), entradas)
        img, _c = exportar(lay, 'pior_caso_real.png')
        self.assertEqual(conferir(lay, m, esperadas, img), [])

        nomes = itens(lay, m, 'nome')
        figs = itens(lay, m, 'figura')
        # 1. linha duplicada
        dup = QgsLayoutItemLabel(lay)
        dup.setText(nomes[0].text())
        dup.setCustomProperty(cv.PROP_QUADRO, m.uuid())
        dup.setCustomProperty(cv.PROP_PAPEL, 'nome')
        dup.attemptMove(QgsLayoutPoint(nomes[0].pos().x(), nomes[-1].pos().y() + 20))
        dup.attemptResize(QgsLayoutSize(40, 8))
        lay.addLayoutItem(dup)
        self.assertTrue(any(p.startswith('duplicado') for p in conferir(lay, m, esperadas)))
        lay.removeLayoutItem(dup)
        # 2. linha a menos
        self.assertTrue(any(p.startswith('faltando') for p in conferir(lay, m, esperadas + ['Campo de minas'])))
        # 3. nome trocado
        original = nomes[1].text()
        nomes[1].setText('Zona fortificada')
        self.assertTrue(any(p.startswith('duplicado') or p.startswith('faltando') for p in conferir(lay, m, esperadas)))
        nomes[1].setText(original)
        # 4. figura apagada: some a imagem e a tinta da célula
        caminho, formato = figs[0].picturePath(), figs[0].mode()
        figs[0].setPicturePath('', Qgis.PictureFormat.Raster)
        img2, _c = exportar(lay, 'pior_caso_figura_apagada.png')
        self.assertTrue(any(p.startswith('figura') for p in conferir(lay, m, esperadas, img2)))
        # e a régua de tinta sozinha também reprova: célula em branco, caminho ainda válido
        figs[0].setPicturePath(caminho, formato)
        img3, _c = exportar(lay, 'pior_caso_restaurado.png')
        self.assertEqual(conferir(lay, m, esperadas, img3), [])
        branca = QImage(img3)
        branca.fill(QColor('white'))
        self.assertTrue(all(p.startswith('figura em branco') for p in conferir(lay, m, esperadas, branca)))
        proj.layoutManager().removeLayout(lay)

    # ---------- cena completa ----------
    def test_quadro_completo_e_reabrir(self):
        proj = self.proj
        camadas = camadas_visiveis_dos_mapas(self.atlas, MAPAS_COMPLETO)
        lay = novo_layout(proj, 'Convenções completo')
        m = novo_mapa(lay, camadas, extensao_3857(camadas))
        grupo, entradas = cv.montar_quadro(lay, m)
        esperado = esperado_ogr(MAPAS_COMPLETO)
        self.assertEqual({(e.tipo, e.chave) for e in entradas}, esperado)
        esperadas = nomes_esperados(esperado, entradas)
        img, caminho = exportar(lay, 'quadro_completo.png')
        print('\n  quadro completo: {} linhas -> {}'.format(len(entradas), caminho))
        self.assertEqual(conferir(lay, m, esperadas, img), [])
        # grupos na ordem e o título
        grupos = [i.text() for i in sorted(itens(lay, m, 'grupo'), key=lambda i: (round(i.pos().x()), i.pos().y()))]
        self.assertEqual(grupos, [r for g, r in cv.GRUPOS if any(e.grupo == g for e in entradas)])
        self.assertEqual([i.text() for i in itens(lay, m, 'titulo')], ['Convenções'])
        # ordem por nome dentro do grupo das Áreas
        areas = [e.nome for e in entradas if e.grupo == 'area']
        self.assertEqual(areas, sorted(areas, key=cv._chave_ordem))
        # feições invisíveis, camada oculta e grupo oculto ficaram fora: o esperado do OGR as
        # exclui, e a coleta sem o filtro de visibilidade teria mais símbolos
        tudo = set()
        for l in camadas:
            t = cv._tipo_da_camada(l)
            if t is None:
                continue
            for f in l.getFeatures():
                tudo.add((t, cv.chave_e_nome(t, f)[0]))
        print('  símbolos sem o filtro de visibilidade: {}; com: {}'.format(len(tudo), len(esperado)))

        # refazer não duplica e fica no mesmo lugar
        grupo.attemptMove(QgsLayoutPoint(215, 12))
        n_itens = len(cv.itens_do_quadro(lay, m.uuid()))
        grupo2, _e = cv.montar_quadro(lay, m)
        self.assertEqual(len(cv.itens_do_quadro(lay, m.uuid())), n_itens)
        self.assertAlmostEqual(grupo2.positionWithUnits().x(), 215, places=3)
        self.assertAlmostEqual(grupo2.positionWithUnits().y(), 12, places=3)
        img_antes, _c = exportar(lay, 'quadro_antes_de_salvar.png')

        # salvar, limpar e reabrir
        qgz = os.path.join(TMP, 'convencoes.qgz')
        self.assertTrue(proj.write(qgz))
        proj.clear()
        _ATLAS.clear()
        self.assertTrue(proj.read(qgz))
        lay2 = proj.layoutManager().layoutByName('Convenções completo')
        self.assertIsNotNone(lay2)
        m2 = [i for i in lay2.items() if isinstance(i, QgsLayoutItemMap)][0]
        grupos2 = [i for i in cv.itens_do_quadro(lay2, m2.uuid()) if i.id() == cv.ID_GRUPO]
        self.assertEqual(len(grupos2), 1)
        img_depois, caminho2 = exportar(lay2, 'quadro_reaberto.png')
        print('  reaberto: {}'.format(caminho2))
        self.assertEqual(conferir(lay2, m2, esperadas, img_depois), [])
        # a página reaberta igual à salva, pixel a pixel (tolerância de antisserrilhado)
        self.assertEqual((img_antes.width(), img_antes.height()), (img_depois.width(), img_depois.height()))
        dif = 0
        for y in range(0, img_antes.height(), 3):
            for x in range(0, img_antes.width(), 3):
                a, b = QColor(img_antes.pixel(x, y)), QColor(img_depois.pixel(x, y))
                if abs(a.red() - b.red()) + abs(a.green() - b.green()) + abs(a.blue() - b.blue()) > 60:
                    dif += 1
        total = (img_antes.height() // 3 + 1) * (img_antes.width() // 3 + 1)
        print('  pixels diferentes depois de reabrir: {} de {}'.format(dif, total))
        self.assertLess(dif / total, 0.002)
        # o próximo teste remonta o atlas no projeto limpo
        proj.clear()

    # ---------- só a extensão do mapa ----------
    def test_so_extensao(self):
        proj, atlas = projeto_com_atlas()
        camadas = camadas_visiveis_dos_mapas(atlas, (MAPA_EXTENSAO,))
        ext_toda = extensao_3857(camadas)
        lay = novo_layout(proj, 'Convenções extensão', 297, 210)
        # o terço superior esquerdo da área dos símbolos de engenharia
        ext = QgsRectangle(ext_toda.xMinimum(), ext_toda.yMaximum() - ext_toda.height() / 3,
                           ext_toda.xMinimum() + ext_toda.width() / 2, ext_toda.yMaximum())
        m = novo_mapa(lay, camadas, ext, 10, 10, 150, 190)
        grupo, entradas = cv.montar_quadro(lay, m, so_extensao=True)
        poligono = QgsGeometry.fromQPolygonF(m.visibleExtentPolygon())
        poligono.transform(QgsCoordinateTransform(m.crs(), QgsCoordinateReferenceSystem('EPSG:4326'), proj))
        esperado = esperado_ogr((MAPA_EXTENSAO,), poligono)
        todos = esperado_ogr((MAPA_EXTENSAO,))
        self.assertEqual({(e.tipo, e.chave) for e in entradas}, esperado)
        self.assertGreater(len(esperado), 0)
        self.assertLess(len(esperado), len(todos))
        img, caminho = exportar(lay, 'quadro_extensao.png')
        print('\n  extensão: {} de {} símbolos -> {}'.format(len(esperado), len(todos), caminho))
        self.assertEqual(conferir(lay, m, nomes_esperados(esperado, entradas), img), [])
        self.assertTrue(grupo.customProperty(cv.PROP_EXTENSAO))

    # ---------- a ação do menu ----------
    def test_acao_do_menu(self):
        from qgis.testing.mocked import get_iface
        from qgis.PyQt.QtWidgets import QMenu
        from Calco.gerenciador import GerenciadorCalco
        from Calco.ui import dialogo_convencoes
        proj, atlas = projeto_com_atlas()
        camadas = camadas_visiveis_dos_mapas(atlas, ('15 ',))
        lay = novo_layout(proj, 'Convenções da ação', 297, 210)
        m = novo_mapa(lay, camadas, extensao_3857(camadas), 10, 10, 150, 190)
        g = GerenciadorCalco(get_iface(), QMenu('EBGeo'))
        g.initGui()
        acao = [a for a in g.acoes if a.text() == 'Quadro de convenções no layout...']
        self.assertEqual(len(acao), 1)
        self.assertFalse(acao[0].icon().isNull())
        escolhas = []
        exec_original = dialogo_convencoes.DialogoConvencoes.exec

        def aceitar(dlg):
            dlg.cb_layout.setCurrentIndex(dlg.layouts.index(lay))
            escolhas.append((dlg.layout_escolhido(), dlg.mapa_escolhido(), dlg.so_extensao()))
            return 1
        dialogo_convencoes.DialogoConvencoes.exec = aceitar
        try:
            acao[0].trigger()
        finally:
            dialogo_convencoes.DialogoConvencoes.exec = exec_original
            g.unload()
        self.assertEqual(escolhas, [(lay, m, False)])
        nomes = [' '.join(i.text().split()) for i in itens(lay, m, 'nome')]
        self.assertEqual(sorted(nomes), sorted(CATALOGO_AREA[c]['nome'] for t, c in esperado_ogr(('15 ',))))
        exportar(lay, 'quadro_acao_menu.png')


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('PNG em', SAIDA)
    sys.exit(0 if r.wasSuccessful() else 1)
