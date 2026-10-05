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


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
