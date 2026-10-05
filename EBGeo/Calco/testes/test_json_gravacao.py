# -*- coding: utf-8 -*-
"""
Coluna JSON gravada pelo QGIS: o valor CRU no GeoPackage tem de ser o JSON de verdade.

    python-qgis.bat EBGeo/Calco/testes/test_json_gravacao.py

Pelo provedor ogr do QGIS, um TEXTO JSON numa coluna JSON vira uma STRING JSON com as aspas
escapadas ('"[{\\"ratio\\": 0.5, ...}]"'), e o importador (OGR) grava o JSON de verdade. O
schema.atributos_para_qgis entrega o objeto ao provedor; a régua é a leitura crua por sqlite3,
que reprova o caminho antigo. O desenho não muda: Limite com instâncias, Área VAB com portões e
Área minada criados pela ferramenta e editados pelo painel, renderizados pelo caminho antigo
(calco antigo, string escapada) e pelo novo, saem iguais.

EBGEO_IMAGENS (pasta) guarda os PNGs; sem ela, vão para uma pasta temporária.
"""
import json
import os
import sqlite3
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
IMAGENS = os.environ.get('EBGEO_IMAGENS') or tempfile.mkdtemp(prefix='ebgeo_json_')
os.makedirs(IMAGENS, exist_ok=True)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsMapRendererParallelJob, QgsMapSettings, QgsProject,
    QgsRectangle,
)

_app = QgsApplication.instance()
if _app is None:
    _app = QgsApplication([], True)
    _app.initQgis()

from qgis.gui import QgsMapCanvas, QgsMapMouseEvent  # noqa: E402
from qgis.testing.mocked import get_iface  # noqa: E402
from qgis.PyQt.QtCore import QEvent, QPoint, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

from Calco import schema  # noqa: E402
from Calco.calco import Calco, aplicar_estilo, definir_calco_ativo  # noqa: E402
from Calco.ferramentas import FerramentaLinha, FerramentaPoligono  # noqa: E402
from Calco.ui.painel import PainelCalco  # noqa: E402

EXTENSAO = QgsRectangle(-47.90, -15.84, -47.70, -15.70)


def cru(caminho, tabela, coluna, ebgeo_id):
    """O valor como está no arquivo, sem QGIS nem OGR no meio."""
    con = sqlite3.connect(caminho)
    try:
        return con.execute('SELECT {} FROM {} WHERE ebgeo_id = ?'.format(coluna, tabela), (ebgeo_id,)).fetchone()[0]
    finally:
        con.close()


def json_de_verdade(texto):
    """O JSON cru decodifica num objeto ou lista (e não numa string que contém JSON)."""
    v = json.loads(texto)
    return v if isinstance(v, (dict, list)) else None


class _Cenario:
    """Um calco com Limite, Área VAB e Área minada, criados pela ferramenta e editados pelo painel."""

    def __init__(self, nome):
        self.caminho = os.path.join(tempfile.mkdtemp(prefix='ebgeo_json_'), nome + '.gpkg')
        self.calco = Calco(self.caminho)
        self.calco.criar()
        self.calco.carregar(estilizar_novas=False)
        definir_calco_ativo(self.calco)
        self.canvas = QgsMapCanvas()
        self.canvas.resize(800, 560)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        self.canvas.setExtent(EXTENSAO)
        self.iface = get_iface()
        self.painel = PainelCalco(self.iface)
        self.ids = {}

    def _clique(self, ft, x, y, botao=Qt.MouseButton.LeftButton):
        ev = QgsMapMouseEvent(self.canvas, QEvent.Type.MouseButtonRelease, QPoint(x, y), botao, botao,
                              Qt.KeyboardModifier.NoModifier)
        ft.canvasReleaseEvent(ev)

    def _selecionar(self, tipo, eid):
        lyr = self.calco.camada(tipo)
        self.painel._camada_mudou(lyr)
        self.painel.mostrar_feicao(lyr, eid)
        self.painel._selecao_mudou()
        return lyr

    def _area(self, pts, codigo):
        ft = FerramentaPoligono(self.canvas, 'coordination_area')
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append(e))
        for x, y in pts[:-1]:
            self._clique(ft, x, y)
        self._clique(ft, *pts[-1], botao=Qt.MouseButton.RightButton)
        eid = criadas[0]
        self._selecionar('coordination_area', eid)
        cb = self.painel.widgets['symbol_code']
        cb.setCurrentIndex(cb.findData(codigo))
        _app.processEvents()
        self.painel._gravar_pendentes()
        self._selecionar('coordination_area', eid)  # o formulário do tipo novo
        return eid

    def montar(self):
        # Limite: dois cliques e o direito; o painel muda as posições para 25, 50 e 80 %
        ft = FerramentaLinha(self.canvas, 'boundary')
        criadas = []
        ft.feicaoCriada.connect(lambda l, t, e: criadas.append(e))
        self._clique(ft, 60, 480)
        self._clique(ft, 380, 430)
        self._clique(ft, 740, 500, Qt.MouseButton.RightButton)
        self.ids['boundary'] = criadas[0]
        self._selecionar('boundary', criadas[0])
        w = self.painel.widgets['symbol_instances']  # o editor de posições do dock (ui/blocos/taticos.py)
        w.repeticoes.setValue(3)
        _app.processEvents()
        for pos, valor in zip(w.posicoes, (25, 50, 80)):
            pos.setValue(valor)
        self.painel._gravar_pendentes()
        self.painel.salvar()  # o Limite edita no buffer do dock: grava no Salvar
        _app.processEvents()
        # Área VAB (170999-01) com dois portões pelo painel
        self.ids['vab'] = self._area([(80, 80), (330, 70), (340, 300), (90, 320)], '170999-01')
        self.painel.widgets['portoes'].acrescentar(0.25)
        self.painel.widgets['portoes'].acrescentar(0.7)
        self.painel._gravar_pendentes()
        # Área minada (270800): a troca de tipo grava as minas padrão; o painel muda a posição 1
        self.ids['minada'] = self._area([(450, 80), (720, 90), (700, 320), (460, 300)], '270800')
        cb = self.painel.widgets['minas'].combos[0]
        cb.setCurrentIndex(cb.findData('ac'))
        self.painel._gravar_pendentes()
        self.painel.salvar()  # a Área de Coordenação edita no buffer do dock: grava no Salvar
        _app.processEvents()
        return self

    def render(self, nome):
        camadas = []
        for tipo in ('coordination_area', 'boundary'):
            lyr = self.calco.camada(tipo)
            aplicar_estilo(lyr, tipo)
            lyr.removeSelection()
            camadas.append(lyr)
        ms = QgsMapSettings()
        ms.setLayers(camadas)
        ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        ms.setExtent(self.canvas.extent().buffered(0.03))  # a vista em que os cliques caíram
        ms.setOutputSize(QSize(900, 680))
        ms.setBackgroundColor(QColor(255, 255, 255))
        job = QgsMapRendererParallelJob(ms)
        job.start()
        job.waitForFinished()
        img = job.renderedImage()
        img.save(os.path.join(IMAGENS, nome))
        return img

    def desmontar(self):
        self.painel.deleteLater()
        QgsProject.instance().removeAllMapLayers()


class TesteJsonCru(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        from qgis.core import QgsSettings
        from Calco.estilos_area import CHAVE_ULTIMO_TIPO
        QgsSettings().remove(CHAVE_ULTIMO_TIPO)

    def _antigo(self):
        """O caminho de hoje: o texto JSON vai direto ao provedor."""
        original = schema.atributos_para_qgis
        schema.atributos_para_qgis = lambda tipo, atributos: dict(atributos)
        try:
            return _Cenario('antigo').montar()
        finally:
            schema.atributos_para_qgis = original

    def test_valor_cru_e_json_de_verdade(self):
        c = _Cenario('novo').montar()
        esperados = [
            ('boundary', 'symbol_instances', c.ids['boundary'],
             [{'ratio': 0.25, 'showLabels': True}, {'ratio': 0.5, 'showLabels': True}, {'ratio': 0.8, 'showLabels': True}]),
            ('coordination_area', 'portoes', c.ids['vab'], None),
            ('coordination_area', 'minas', c.ids['minada'], ['ac', 'ap', 'ac']),
        ]
        for tabela, coluna, eid, valor in esperados:
            with self.subTest(coluna=coluna):
                texto = cru(c.caminho, tabela, coluna, eid)
                self.assertFalse(texto.startswith('"'), texto)
                obj = json_de_verdade(texto)
                self.assertIsNotNone(obj, texto)
                if valor is not None:
                    self.assertEqual(obj, valor)
        portoes = json_de_verdade(cru(c.caminho, 'coordination_area', 'portoes', c.ids['vab']))
        self.assertEqual([round(p['ratio'], 2) for p in portoes], [0.25, 0.7])
        c.desmontar()

    def test_regua_reprova_o_caminho_antigo(self):
        """O caminho antigo grava a string escapada: a régua acima tem de reprovar."""
        c = self._antigo()
        texto = cru(c.caminho, 'boundary', 'symbol_instances', c.ids['boundary'])
        self.assertTrue(texto.startswith('"'), texto)
        self.assertIsNone(json_de_verdade(texto))
        self.assertIsInstance(json.loads(json.loads(texto)), list)
        c.desmontar()

    def test_ferramenta_comum_e_motor(self):
        """Engenharia (JSON do motor) e o props do Azimute e Distância pela gravar_feicao e pela gravacao."""
        import uuid
        from qgis.core import QgsGeometry, QgsPointXY
        from Calco.ferramentas import gravar_feicao
        c = _Cenario('motor')
        a = dict(schema.padroes('engineering_symbol'))
        a['ebgeo_id'] = str(uuid.uuid4())
        try:
            from Calco.motor.motor import Motor
            a['engineering'] = json.dumps(Motor.instancia().engenharia_rascunho('9'))
        except Exception as e:  # pragma: no cover
            self.skipTest('motor indisponível: {}'.format(e))
        eid = gravar_feicao(c.calco.camada('engineering_symbol'), 'engineering_symbol',
                            QgsGeometry.fromPointXY(QgsPointXY(-47.8, -15.77)), a)
        self.assertIsInstance(json_de_verdade(cru(c.caminho, 'engineering_symbol', 'engineering', eid)), dict)
        from Calco.azimute import gravacao
        estado = {'referencePoint': [-47.8, -15.75], 'outputMode': 'route', 'angularUnit': 'degrees',
                  'distanceUnit': 'meters', 'northReference': 'true', 'magneticDeclination': -22.0,
                  'meridianConvergence': 0.76, 'legs': [{'azimuth': 45, 'distance': 1000}]}
        _lyr, ids = gravacao.criar(c.calco, estado)
        for col in ('props', 'azimute_distancia'):
            self.assertIsInstance(json_de_verdade(cru(c.caminho, 'line', col, ids[0])), dict, col)
        c.desmontar()


class TesteDesenhoIgual(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        from qgis.core import QgsSettings
        from Calco.estilos_area import CHAVE_ULTIMO_TIPO
        QgsSettings().remove(CHAVE_ULTIMO_TIPO)

    def test_antes_e_depois_desenham_igual(self):
        original = schema.atributos_para_qgis
        schema.atributos_para_qgis = lambda tipo, atributos: dict(atributos)
        try:
            antes = _Cenario('antes').montar()
        finally:
            schema.atributos_para_qgis = original
        self.assertTrue(cru(antes.caminho, 'coordination_area', 'portoes', antes.ids['vab']).startswith('"'))
        img_antes = antes.render('json_antes.png')
        antes.desmontar()
        depois = _Cenario('depois').montar()
        self.assertFalse(cru(depois.caminho, 'coordination_area', 'portoes', depois.ids['vab']).startswith('"'))
        img_depois = depois.render('json_depois.png')
        depois.desmontar()
        diferentes = tinta = 0
        for x in range(img_antes.width()):
            for y in range(img_antes.height()):
                a, b = img_antes.pixel(x, y), img_depois.pixel(x, y)
                if a != b:
                    diferentes += 1
                if (a & 0xFFFFFF) != 0xFFFFFF:
                    tinta += 1
        print('\n  render: {} pixels com tinta; {} diferentes entre antes e depois'.format(tinta, diferentes))
        self.assertGreater(tinta, 5000)  # os três desenhos estão na imagem
        self.assertEqual(diferentes, 0)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    QgsProject.instance().removeAllMapLayers()
    sys.exit(0 if r.wasSuccessful() else 1)
