# -*- coding: utf-8 -*-
"""
O estilo que o plugin grava no layer_styles chega inteiro, e a gravação o prova relendo.

Medido em 2026-10-05: cerca de 1 importação da fixture 06 em 3 gravava o estilo do Ponto CORTADO
(cerca de 77 mil de 198 mil caracteres, no meio da expressão do rótulo), com o salvar dizendo
sucesso. A gravação não cortava nada: o QML já saía da memória com quatro caracteres nulos no fim
da expressão "mostrar" do rótulo, e o OGR guarda o texto até o primeiro nulo. Quem zerava a
memória era o `esconder_por_regra`: a referência Python ao renderer velho, que o `setRenderer`
já tinha apagado, era solta no fim da função e o SIP escrevia oito bytes zero na memória já
reaproveitada pela expressão nova do rótulo.

  - A expressão do rótulo do Ponto sai sem nulo em muitas repetições do estilizar e do
    esconder_por_regra (reprova o código anterior em cerca de 4 de cada 10 repetições).
  - O caminho de produção do importador (escritor.importar + arvore.salvar_estilos, todos os
    tipos comuns) grava cada estilo igual ao que a camada exporta, em várias importações.
  - A prova da escrita (calco.gravar_estilo): uma gravação que diz sucesso e deixa o registro
    cortado é regravada; se o corte persiste, a gravação falha alto. Vale para os quatro
    caminhos que gravam estilo (calco, importador, estilos_pontuais, estilos_taticos).

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_estilo_gravado.py
A fixture 06 vem de EBGEO_FIXTURES (padrão: ../_ebgeo_dados_teste, irmão do repositório).
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
RAIZ_REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, PLUGIN)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsMapLayer, QgsPalLayerSettings, QgsReadWriteContext, QgsVectorLayer,
)
from qgis.PyQt.QtXml import QDomDocument  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import calco as C, schema  # noqa: E402
from Calco.importador import arvore, escritor  # noqa: E402
from Calco.formulario import especificacao  # noqa: E402,F401 (antes dos tipos: eles a importam)
from Calco.formulario.tipos import comuns as CM  # noqa: E402

FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
TMP = tempfile.mkdtemp(prefix='ebgeo_estilo_gravado_')
COMUNS = list(CM.TIPOS)
REPETICOES_ROTULO = 40
IMPORTACOES = 10
MEDIDAS = []


def exportado(layer):
    doc = QDomDocument()
    layer.exportNamedStyle(doc, QgsReadWriteContext(), QgsMapLayer.StyleCategory.AllStyleCategories)
    return doc.toString()


def gravado(caminho, tabela):
    salvo = C.estilo_padrao_salvo(caminho, tabela)
    return salvo['qml'] if salvo else ''


def expressao_mostrar(layer):
    st = layer.labeling().settings()  # guardado: dataDefinedProperties devolve referência a ele
    dd = st.dataDefinedProperties()
    p = dd.property(QgsPalLayerSettings.Property.Show)
    return p.expressionString()


class CamadaQueCorta(QgsVectorLayer):
    """Grava o estilo pelo QGIS e depois corta o registro no arquivo: o salvar diz sucesso."""

    def __init__(self, *a, cortes=1):
        super().__init__(*a)
        self.cortes = cortes
        self.gravacoes = 0

    def saveStyleToDatabaseV2(self, *a):
        res = super().saveStyleToDatabaseV2(*a)
        self.gravacoes += 1
        if self.cortes:
            self.cortes -= 1
            from osgeo import ogr
            caminho, tabela = self.source().split('|layername=')
            ds = ogr.Open(caminho, 1)
            ds.ExecuteSQL("UPDATE layer_styles SET styleQML = substr(styleQML, 1, 77000) "
                          "WHERE f_table_name = '{}'".format(tabela))
            ds = None
        return res


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'sem a fixture 06 (EBGEO_FIXTURES)')
class TestEstiloGravado(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = os.path.join(TMP, 'base.gpkg')
        escritor.importar(FIXTURE_06, cls.base)

    def test_1_rotulo_do_ponto_sem_nulo(self):
        ruins = []
        for i in range(REPETICOES_ROTULO):
            lyr = QgsVectorLayer(self.base + '|layername=point', 'Ponto', 'ogr')
            arvore.estilizar(lyr, 'point')
            arvore.esconder_por_regra(lyr, arvore.COND_VISIVEL)
            e = expressao_mostrar(lyr)
            if '\x00' in e or not e.endswith("<> '')"):
                ruins.append((i, e[-30:]))
        MEDIDAS.append('expressão do rótulo do Ponto com nulo: {} de {}'.format(len(ruins), REPETICOES_ROTULO))
        self.assertEqual(ruins, [])

    def test_2_importador_grava_estilo_inteiro(self):
        ruins = []
        for i in range(IMPORTACOES):
            cam = os.path.join(TMP, 'imp{}.gpkg'.format(i))
            escritor.importar(FIXTURE_06, cam)
            arvore.salvar_estilos(cam, tipos=COMUNS)
            for tipo in COMUNS:
                tabela = schema.TIPOS[tipo]['tabela']
                q = gravado(cam, tabela)
                doc = QDomDocument()
                if not q.rstrip().endswith('</qgis>') or '\x00' in q or not doc.setContent(q)[0] \
                        or '<editorlayout>tablayout</editorlayout>' not in q:
                    ruins.append((i, tipo, len(q)))
        MEDIDAS.append('importações com estilo cortado: {} de {} ({})'.format(
            len({r[0] for r in ruins}), IMPORTACOES, ruins))
        self.assertEqual(ruins, [])

    def _camada(self, nome, tipo, cortes):
        cam = os.path.join(TMP, nome + '.gpkg')
        escritor.importar(FIXTURE_06, cam)
        lyr = CamadaQueCorta('{}|layername={}'.format(cam, schema.TIPOS[tipo]['tabela']), 'Ponto', 'ogr', cortes=cortes)
        C.aplicar_estilo(lyr, tipo)
        return cam, lyr

    def test_3_prova_regrava_o_cortado(self):
        cam, lyr = self._camada('regrava', 'point', cortes=1)
        quis = exportado(lyr)
        ok, msg = C.gravar_estilo(lyr, lyr.name(), 'teste')
        self.assertTrue(ok, msg)
        self.assertEqual(lyr.gravacoes, 2, 'o corte devia ser visto e regravado')
        self.assertEqual(gravado(cam, 'point'), quis)

    def test_4_prova_falha_alto_se_o_corte_persiste(self):
        cam, lyr = self._camada('persiste', 'point', cortes=5)
        with self.assertRaises(C.EstiloNaoGravado):
            C.gravar_estilo(lyr, lyr.name(), 'teste')

    def test_5_todos_os_caminhos_provam(self):
        """calco.salvar_estilo_padrao, o importador e as funções dos módulos de estilo regravam o corte."""
        from Calco import estilos_pontuais, estilos_taticos
        casos = []
        cam, lyr = self._camada('c_calco', 'point', cortes=1)
        casos.append(('calco', lyr, cam, 'point', lambda l: C.salvar_estilo_padrao(l)))
        cam, lyr = self._camada('c_pontuais', 'military_symbol', cortes=1)
        casos.append(('estilos_pontuais', lyr, cam, 'military_symbol', estilos_pontuais.salvar_estilo_padrao))
        cam, lyr = self._camada('c_taticos', 'boundary', cortes=1)
        casos.append(('estilos_taticos', lyr, cam, 'boundary', estilos_taticos.salvar_estilo_padrao))
        for nome, lyr, cam, tipo, gravar in casos:
            gravar(lyr)
            self.assertEqual(lyr.gravacoes, 2, nome)
            self.assertEqual(gravado(cam, schema.TIPOS[tipo]['tabela']), exportado(lyr), nome)
        # o importador cria as camadas dele: troca a classe da camada no módulo
        cam = os.path.join(TMP, 'c_imp.gpkg')
        escritor.importar(FIXTURE_06, cam)
        criadas = []
        orig = arvore.QgsVectorLayer

        def fabrica(*a):
            c = CamadaQueCorta(*a, cortes=1)
            criadas.append(c)
            return c
        arvore.QgsVectorLayer = fabrica
        try:
            arvore.salvar_estilos(cam, tipos=['point'])
        finally:
            arvore.QgsVectorLayer = orig
        self.assertEqual([c.gravacoes for c in criadas], [2])
        self.assertEqual(gravado(cam, 'point'), exportado(criadas[0]))


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'sem a fixture 06 (EBGEO_FIXTURES)')
class TestZMedidas(unittest.TestCase):
    def test_medidas(self):
        print('\nMEDIDAS:\n  ' + '\n  '.join(MEDIDAS))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
