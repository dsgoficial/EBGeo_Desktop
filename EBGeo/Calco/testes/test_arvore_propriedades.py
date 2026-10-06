# -*- coding: utf-8 -*-
"""
Propriedades de cada camada da árvore do importador (importador/arvore.py).

`_materializar` grava em cada camada o mapa, a camada do EBGeo e as duas ordens (ebgeo/mapa,
ebgeo/camada_id, ebgeo/ordem_mapa, ebgeo/ordem_camada) e depois a estiliza. O estilo de um tipo
é montado uma vez e copiado por QML para as demais camadas do tipo; copiado com todas as
categorias, o QML levava junto as propriedades personalizadas da PRIMEIRA camada, e toda camada
do tipo passava a dizer o mapa e a camada dela (medido em 2026-10-05 na fixture 06: a Linha de
Coordenação do mapa 08 com ebgeo/mapa = 'Principal'), o que desarrumava o `reordenar`.

O instrumento independente é o filtro (subset) da camada, que o importador monta com o mapa e a
camada do EBGeo, e a posição do grupo e do subgrupo na árvore.

TestDesenhoNoAtlas: a ferramenta de desenho num atlas importado, num tipo que o mapa ainda não
tem (K3). A camada do tipo nasce no subgrupo da camada do EBGeo ativa na
árvore, com as propriedades e a ordem do importador, e a feição desenhada sai do exportador no
mapa e na camada do EBGeo certos. O Azimute e Distância passa pelo mesmo caminho
(`ferramentas.camada_para_gravar`; antes pedia `calco.camada(tipo)`). O instrumento é o .ebgeo
exportado, relido pelo leitor.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_arvore_propriedades.py
"""
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ_REPO = os.path.abspath(os.path.join(AQUI, '..', '..', '..'))
sys.path.insert(0, os.path.join(RAIZ_REPO, 'EBGeo'))
FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_30 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')

from qgis.core import QgsApplication, QgsProject  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()

from Calco import schema  # noqa: E402
from Calco.importador import arvore, escritor  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_arvore_props_')
GPKG = os.path.join(TMP, 'f06.gpkg')

_FILTRO = re.compile(r'"mapa" = \'((?:[^\']|\'\')*)\' AND "camada_id" = \'((?:[^\']|\'\')*)\'')


def do_filtro(layer):
    """(mapa, camada_id) lidos do subset que o importador montou."""
    m = _FILTRO.search(layer.subsetString())
    return (m.group(1).replace("''", "'"), m.group(2).replace("''", "'")) if m else None


@unittest.skipUnless(os.path.exists(FIXTURE_30), 'fixture 06-completo-3.0.ebgeo ausente')
class TestPropriedadesDaArvore(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        escritor.importar(FIXTURE_30, GPKG)
        arvore.salvar_estilos(GPKG)
        cls.proj = QgsProject.instance()
        cls.atlas = arvore.montar_arvore(GPKG, cls.proj, materializar='todos')
        # posição verdadeira de cada camada: (índice do mapa no atlas, índice do subgrupo no mapa)
        cls.posicao = {}
        for i, g in enumerate(cls.atlas.children()):
            for oc, sub in enumerate(g.children()):
                for no in sub.findLayers():
                    cls.posicao[no.layer().id()] = (g.name(), i, sub, oc)
        cls.camadas = [l for l in cls.proj.mapLayers().values() if l.customProperty(arvore.PROP_TIPO) in schema.TIPOS]

    def test_mesmo_tipo_em_varios_mapas(self):
        # o caso que pega o defeito: um tipo com camadas em mais de um mapa
        por_tipo = {}
        for l in self.camadas:
            por_tipo.setdefault(l.customProperty(arvore.PROP_TIPO), set()).add(do_filtro(l)[0])
        self.assertTrue(any(len(m) > 1 for m in por_tipo.values()))

    def test_cada_camada_com_o_proprio_mapa_e_camada(self):
        erradas = []
        for l in self.camadas:
            mapa, camada_id = do_filtro(l)
            nome_grupo, i, sub, oc = self.posicao[l.id()]
            esperado = (mapa, camada_id, i, oc)
            obtido = (l.customProperty(arvore.PROP_MAPA), l.customProperty(arvore.PROP_CAMADA),
                      int(l.customProperty(arvore.PROP_ORDEM_MAPA)), int(l.customProperty(arvore.PROP_ORDEM_CAMADA)))
            if obtido != esperado:
                erradas.append((l.name(), esperado, obtido))
            self.assertEqual(sub.customProperty(arvore.PROP_CAMADA), camada_id)
            self.assertEqual(nome_grupo, mapa)
        self.assertEqual(erradas[:5], [], '{} de {} camadas com propriedades de outra'.format(
            len(erradas), len(self.camadas)))

    def test_reordenar_pela_pilha_do_web(self):
        """
        Carga preguiçosa: o mapa ativo nasce com as camadas, e os outros entram quando o operador
        os liga (materializar_mapa, que chama o reordenar), aqui fora da ordem do atlas (08 antes
        de 02). A ordem de desenho tem de ser a da pilha do Web por tipo e, dentro do tipo, a do
        atlas e a das camadas do EBGeo, qualquer que seja a ordem em que os mapas carregaram e
        a ordem de que o reordenar parte.
        """
        proj = QgsProject()
        atlas = arvore.montar_arvore(GPKG, proj, materializar='atual')
        grupos = {g.customProperty(arvore.PROP_MAPA): g for g in atlas.children()}
        for prefixo in ('08 ', '02 ', '10 '):
            g = [g for m, g in grupos.items() if m.startswith(prefixo)][0]
            self.assertGreater(arvore.materializar_mapa(g, proj), 0)
        posicao = {}
        for i, g in enumerate(atlas.children()):
            for oc, sub in enumerate(g.children()):
                for no in sub.findLayers():
                    posicao[no.layer().id()] = (i, oc)
        camadas = [l for l in proj.mapLayers().values() if l.customProperty(arvore.PROP_TIPO) in schema.TIPOS]
        pilha = {t: k for k, t in enumerate(schema.PILHA_DESENHO)}
        esperado = [l.id() for l in sorted(camadas, key=lambda l: (-pilha[l.customProperty(arvore.PROP_TIPO)],)
                                           + posicao[l.id()])]
        ids = set(esperado)
        obtido = [l.id() for l in proj.layerTreeRoot().customLayerOrder() if l.id() in ids]
        nomes = {l.id(): '{} / {}'.format(l.name(), do_filtro(l)[0]) for l in camadas}
        self.assertEqual([nomes[i] for i in obtido], [nomes[i] for i in esperado])
        # partindo de outra ordem (o operador mexeu no painel de ordem), o reordenar volta à do
        # Web: com as propriedades copiadas da primeira camada, todas as do tipo empatavam, e o
        # empate guardava a ordem de partida
        raiz = proj.layerTreeRoot()
        raiz.setCustomLayerOrder(list(reversed(raiz.customLayerOrder())))
        arvore.reordenar(proj)
        obtido = [l.id() for l in raiz.customLayerOrder() if l.id() in ids]
        self.assertEqual([nomes[i] for i in obtido], [nomes[i] for i in esperado])
        proj.clear()


class _Arvore:
    def __init__(self, no):
        self.no = no

    def currentNode(self):
        return self.no


class _Iface:
    """O que a ferramenta lê da interface: a camada ativa e o nó selecionado no painel de camadas."""
    def __init__(self, ativa=None, no=None):
        self.ativa, self.no = ativa, no

    def activeLayer(self):
        return self.ativa

    def layerTreeView(self):
        return _Arvore(self.no)

    def messageBar(self):
        import types
        return types.SimpleNamespace(pushWarning=lambda *a: None, pushSuccess=lambda *a: None)


@unittest.skipUnless(os.path.exists(FIXTURE_30), 'fixture 06-completo-3.0.ebgeo ausente')
class TestDesenhoNoAtlas(unittest.TestCase):
    """
    Num atlas importado, sem camada do tipo selecionada, a ferramenta criava o grupo "Calco: nome"
    fora do atlas com as tabelas inteiras, e a feição nascia em 'Principal'/'default', fora do
    mapa e da camada do EBGeo em que o operador desenhava.
    """
    @classmethod
    def setUpClass(cls):
        from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle
        from qgis.gui import QgsMapCanvas
        from Calco.calco import Calco, definir_calco_ativo
        cls.gpkg = os.path.join(TMP, 'k3.gpkg')
        escritor.importar(FIXTURE_30, cls.gpkg)
        arvore.salvar_estilos(cls.gpkg)
        cls.proj = QgsProject.instance()
        cls.proj.clear()
        cls.atlas = arvore.montar_arvore(cls.gpkg, cls.proj, materializar='atual')
        definir_calco_ativo(Calco(cls.gpkg))
        cls.canvas = QgsMapCanvas()
        cls.canvas.resize(800, 600)
        cls.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        cls.canvas.setExtent(QgsRectangle(-43.30, -22.95, -43.10, -22.80))
        cls.canvas.refresh()

    @classmethod
    def tearDownClass(cls):
        from Calco.calco import definir_calco_ativo
        definir_calco_ativo(None)
        cls.proj.clear()

    def _mapas(self):
        return [g for g in self.atlas.children() if g.customProperty(arvore.PROP_MAPA) is not None]

    PONTUAIS = ('military_symbol', 'coordination_measure', 'engineering_symbol', 'magnetic_declination')

    def _alvo(self, evitar=(), candidatos=PONTUAIS):
        """
        (grupo do mapa, subgrupo, camada irmã, tipo): uma camada do EBGeo com alguma camada e sem a
        de um dos `candidatos` (os tipos pontuais), no mapa ligado ou, sem ela, no primeiro mapa já
        carregado que a tenha.
        """
        mapas = sorted(self._mapas(), key=lambda g: not g.itemVisibilityChecked())
        for g in mapas:
            arvore.materializar_mapa(g, self.proj)  # o mapa ainda "(carregar)" carrega; o carregado fica
            for sub in g.children():
                tipos = {n.layer().customProperty(arvore.PROP_TIPO): n.layer() for n in sub.findLayers()}
                for tipo in candidatos:
                    if tipos and tipo not in tipos and (sub, tipo) not in evitar:
                        return g, sub, next(iter(tipos.values())), tipo
        return None, None, None, None

    def _desenhar(self, tipo, iface):
        from qgis.gui import QgsMapMouseEvent
        from qgis.PyQt.QtCore import QEvent, QPoint, Qt
        from Calco.ferramentas import FerramentaPonto
        ft = FerramentaPonto(self.canvas, tipo, iface)
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append((l, e)))
        ev = QgsMapMouseEvent(self.canvas, QEvent.Type.MouseButtonRelease, QPoint(400, 300), Qt.MouseButton.LeftButton,
                              Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        ft.canvasReleaseEvent(ev)
        self.assertEqual(len(criadas), 1)
        return criadas[0]

    def _azimute(self, tipo, iface):
        """A construção do Azimute e Distância gravada pela ferramenta: (camada, ebgeo_id)."""
        from Calco import zoom
        from Calco.azimute import geometria as G, gravacao
        from Calco.azimute.painel import estado_inicial
        from Calco.calco import calco_ativo
        e = estado_inicial()
        e['outputMode'] = gravacao.MODO_DO_TIPO[tipo]
        e['referencePoint'] = [-43.2, -22.875]
        e['meridianConvergence'] = 0.0
        e['legs'] = [{'azimuth': az, 'distance': 800, 'observation': ''} for az in (0, 120, 240)]
        z, _lat = zoom.zoom_do_canvas(self.canvas)
        lyr, ids = gravacao.criar(calco_ativo(), e, z, iface)
        self.assertTrue(ids)
        return lyr, ids[0]

    def _exportado(self):
        """{ebgeo_id: (mapa, balde, layerId)} do .ebgeo exportado do calco e relido pelo leitor."""
        from Calco.exportador import arquivo, desenho, montador
        from Calco.importador import leitor
        exp = montador.montar(self.gpkg, montador.ESCOPO_TUDO, None, desenho.GeradorDesenho())
        saida = os.path.join(TMP, 'k3.ebgeo')
        arquivo.gravar(saida, exp.data, exp.imagens)
        out = {}
        for nome, m in leitor.abrir(saida).data['maps'].items():
            for balde, lista in (m.get('features') or {}).items():
                for f in lista:
                    out[f['properties']['id']] = (nome, balde, f['properties'].get('layerId'))
        return out

    def _conferir_camada(self, lyr, grupo_mapa, sub, tipo):
        mapa, camada_id = grupo_mapa.customProperty(arvore.PROP_MAPA), sub.customProperty(arvore.PROP_CAMADA)
        no = self.proj.layerTreeRoot().findLayer(lyr.id())
        self.assertIs(no.parent(), sub)
        self.assertEqual(do_filtro(lyr), (mapa, camada_id))
        self.assertEqual((lyr.customProperty(arvore.PROP_CAMINHO), lyr.customProperty(arvore.PROP_TIPO),
                          lyr.customProperty(arvore.PROP_MAPA), lyr.customProperty(arvore.PROP_CAMADA),
                          int(lyr.customProperty(arvore.PROP_ORDEM_MAPA)), int(lyr.customProperty(arvore.PROP_ORDEM_CAMADA))),
                         (os.path.abspath(self.gpkg), tipo, mapa, camada_id,
                          self.atlas.children().index(grupo_mapa), grupo_mapa.children().index(sub)))
        # a posição no subgrupo é a da pilha de desenho do Web (de cima para baixo, o inverso)
        pilha = list(reversed(schema.PILHA_DESENHO))
        tipos = [n.layer().customProperty(arvore.PROP_TIPO) for n in sub.findLayers()]
        self.assertEqual(tipos, sorted(tipos, key=pilha.index))
        # e a ordem de desenho do projeto, a do reordenar
        ordem = [l for l in self.proj.layerTreeRoot().customLayerOrder() if l.customProperty(arvore.PROP_TIPO) in schema.PILHA_DESENHO]
        self.assertIn(lyr, ordem)
        chave = [(-schema.PILHA_DESENHO.index(l.customProperty(arvore.PROP_TIPO)), int(l.customProperty(arvore.PROP_ORDEM_MAPA) or 0),
                  int(l.customProperty(arvore.PROP_ORDEM_CAMADA) or 0)) for l in ordem]
        self.assertEqual(chave, sorted(chave))

    def test_camada_nova_no_subgrupo_ativo(self):
        mapa_atual, sub, irma, tipo = self._alvo()
        self.assertIsNotNone(sub, 'nenhuma camada do EBGeo carregada sem um tipo pontual')
        antes = set(self.proj.mapLayers())
        lyr, eid = self._desenhar(tipo, _Iface(ativa=irma, no=self.proj.layerTreeRoot().findLayer(irma.id())))
        novas = set(self.proj.mapLayers()) - antes
        self.assertEqual(novas, {lyr.id()})
        self.assertIsNone(self.proj.layerTreeRoot().findGroup('Calco: k3'))
        self._conferir_camada(lyr, mapa_atual, sub, tipo)
        self.assertAlmostEqual(lyr.opacity(), irma.opacity())
        self.assertEqual(lyr.readOnly(), irma.readOnly())
        f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
        self.assertEqual((f['mapa'], f['camada_id']), (mapa_atual.customProperty(arvore.PROP_MAPA), sub.customProperty(arvore.PROP_CAMADA)))
        # o segundo desenho no mesmo lugar usa a mesma camada
        lyr2, eid2 = self._desenhar(tipo, _Iface(ativa=irma, no=self.proj.layerTreeRoot().findLayer(irma.id())))
        self.assertIs(lyr2, lyr)
        exp = self._exportado()
        balde = schema.TIPOS[tipo]['balde']
        esperado = (mapa_atual.customProperty(arvore.PROP_MAPA), balde, sub.customProperty(arvore.PROP_CAMADA))
        self.assertEqual(exp[eid], esperado)
        self.assertEqual(exp[eid2], esperado)

    def test_grupo_de_mapa_nao_carregado(self):
        """O nó ativo é o grupo de um mapa ainda "(carregar)": ele carrega, e a feição vai à primeira camada dele."""
        tipo = 'coordination_measure'
        pendente = [g for g in self._mapas() if g.customProperty(arvore.PROP_PENDENTE)][0]
        mapa = pendente.customProperty(arvore.PROP_MAPA)
        lyr, eid = self._desenhar(tipo, _Iface(ativa=None, no=pendente))
        self.assertFalse(pendente.customProperty(arvore.PROP_PENDENTE))
        sub = [g for g in pendente.children() if g.customProperty(arvore.PROP_CAMADA) is not None][0]
        self.assertEqual(lyr.customProperty(arvore.PROP_TIPO), tipo)
        no = self.proj.layerTreeRoot().findLayer(lyr.id())
        self.assertIs(no.parent(), sub)
        self.assertEqual(do_filtro(lyr), (mapa, sub.customProperty(arvore.PROP_CAMADA)))
        self.assertEqual(self._exportado()[eid], (mapa, schema.TIPOS[tipo]['balde'], sub.customProperty(arvore.PROP_CAMADA)))

    LINEARES = ('line', 'polygon', 'point')

    def test_azimute_e_distancia_no_subgrupo_ativo(self):
        """O Azimute e Distância grava no mapa e na camada do EBGeo ativos, como as ferramentas militares."""
        mapa_atual, sub, irma, tipo = self._alvo(candidatos=self.LINEARES)
        self.assertIsNotNone(sub, 'nenhuma camada do EBGeo carregada sem a linha, o polígono ou o ponto')
        lyr, eid = self._azimute(tipo, _Iface(ativa=irma, no=self.proj.layerTreeRoot().findLayer(irma.id())))
        self.assertIsNone(self.proj.layerTreeRoot().findGroup('Calco: k3'))
        self._conferir_camada(lyr, mapa_atual, sub, tipo)
        f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
        self.assertEqual((f['mapa'], f['camada_id']), (mapa_atual.customProperty(arvore.PROP_MAPA), sub.customProperty(arvore.PROP_CAMADA)))
        self.assertEqual(self._exportado()[eid], (mapa_atual.customProperty(arvore.PROP_MAPA), schema.TIPOS[tipo]['balde'],
                                                  sub.customProperty(arvore.PROP_CAMADA)))

    def test_azimute_pior_caso_o_caminho_de_antes_reprova(self):
        """Com a camada pedida a `calco.camada(tipo)` (o código de antes), a régua acusa o mapa e a camada errados."""
        from unittest import mock
        from Calco import ferramentas
        mapa_atual, sub, irma, tipo = self._alvo(candidatos=self.LINEARES)
        self.assertIsNotNone(sub)
        with mock.patch.object(ferramentas, 'camada_para_gravar', lambda calco, t, iface=None: calco.camada(t)):
            lyr, eid = self._azimute(tipo, _Iface(ativa=irma, no=self.proj.layerTreeRoot().findLayer(irma.id())))
        try:
            esperado = (mapa_atual.customProperty(arvore.PROP_MAPA), schema.TIPOS[tipo]['balde'],
                        sub.customProperty(arvore.PROP_CAMADA))
            self.assertNotEqual(self._exportado()[eid], esperado)
            self.assertIsNot(self.proj.layerTreeRoot().findLayer(lyr.id()).parent(), sub)
        finally:
            g = self.proj.layerTreeRoot().findGroup('Calco: k3')
            ids = [n.layer().id() for n in g.findLayers()] if g is not None else []
            if g is not None:
                g.parent().removeChildNode(g)
            self.proj.removeMapLayers(ids)
            lyr = None

    def test_pior_caso_o_caminho_de_antes_reprova(self):
        """Sem camada_para_desenho (o código de antes), a régua acusa o mapa e a camada errados."""
        from unittest import mock
        mapa_atual, sub, irma, tipo = self._alvo()
        self.assertIsNotNone(sub)
        with mock.patch.object(arvore, 'camada_para_desenho', lambda *a, **k: None):
            lyr, eid = self._desenhar(tipo, _Iface(ativa=irma, no=self.proj.layerTreeRoot().findLayer(irma.id())))
        try:
            esperado = (mapa_atual.customProperty(arvore.PROP_MAPA), schema.TIPOS[tipo]['balde'],
                        sub.customProperty(arvore.PROP_CAMADA))
            # a feição ia à camada do tipo de outro mapa (a primeira que o calco achava no projeto)
            # ou ao grupo "Calco: k3" criado fora do atlas
            self.assertNotEqual(self._exportado()[eid], esperado)
            self.assertIsNot(self.proj.layerTreeRoot().findLayer(lyr.id()).parent(), sub)
        finally:
            g = self.proj.layerTreeRoot().findGroup('Calco: k3')
            ids = [n.layer().id() for n in g.findLayers()] if g is not None else []
            if g is not None:
                g.parent().removeChildNode(g)
            self.proj.removeMapLayers(ids)
            lyr = None


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
