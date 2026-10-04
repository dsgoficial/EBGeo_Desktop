# -*- coding: utf-8 -*-
"""
Barra "Simbologia Militar" e submenu do EBGeo: criar/abrir calco, as 8 ferramentas
do EBGeo Web, o painel de propriedades e a importação do .ebgeo.
"""
import os

from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QActionGroup, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QMenu

from . import schema
from .calco import Calco, calco_ativo, definir_calco_ativo
from .ferramentas import FerramentaLinha, FerramentaPonto

ICONES = os.path.join(os.path.dirname(__file__), 'icones')

FERRAMENTAS = [
    # tipo, ícone, rótulo
    ('military_symbol', 'simbolo_militar.svg', 'Símbolo Militar'),
    ('coordination_measure', 'medida_coordenacao.svg', 'Medida de Coordenação'),
    ('engineering_symbol', 'simbolo_engenharia.svg', 'Símbolos de Engenharia'),
    ('boundary', 'linha_limite.svg', 'Linha de Limite'),
    ('coordination_line', 'linha_coordenacao.svg', 'Linha de Coordenação'),
    ('arrow', 'seta.svg', 'Seta (manobra / eixo)'),
    ('occupied_front', 'frente_ocupada.svg', 'Frente Ocupada'),
    ('magnetic_declination', 'declinacao.svg', 'Declinação Magnética'),
]

CHAVE_SIDC = 'EBGeo/calco/ultimo_sidc'


def _icone(nome):
    return QIcon(os.path.join(ICONES, nome))


class GerenciadorCalco:
    def __init__(self, iface, menu_pai):
        self.iface = iface
        self.menu_pai = menu_pai
        self.toolbar = None
        self.menu = None
        self.acoes = []
        self.ferramentas = {}
        self.painel = None

    # ---------- montagem ----------
    def initGui(self):
        self.toolbar = self.iface.addToolBar('EBGeo: Simbologia Militar')
        self.toolbar.setObjectName('EBGeoSimbologiaMilitar')
        self.menu = QMenu('Simbologia Militar (EBGeo Web)', self.menu_pai)
        self.menu.setIcon(_icone('simbolo_militar.svg'))
        self.menu_pai.addMenu(self.menu)

        self._acao('calco_novo.svg', 'Novo calco...', self.novo_calco)
        self._acao('calco_abrir.svg', 'Abrir calco...', self.abrir_calco)
        self._acao('importar_ebgeo.svg', 'Importar arquivo .ebgeo...', self.importar_ebgeo)
        self.toolbar.addSeparator()
        self.menu.addSeparator()

        grupo = QActionGroup(self.iface.mainWindow())
        grupo.setExclusive(True)
        canvas = self.iface.mapCanvas()
        for tipo, icone, rotulo in FERRAMENTAS:
            a = self._acao(icone, rotulo, None)
            a.setCheckable(True)
            grupo.addAction(a)
            if schema.TIPOS[tipo]['geometria'] == 'Point':
                ft = FerramentaPonto(canvas, tipo, self.iface, preparar_atributos=self._preparar_ponto)
            else:
                ft = FerramentaLinha(canvas, tipo, self.iface)
            ft.setAction(a)
            ft.feicaoCriada.connect(self._feicao_criada)
            a.triggered.connect(lambda _c=False, ft=ft: self._ativar(ft))
            self.ferramentas[tipo] = ft

        self.toolbar.addSeparator()
        self.menu.addSeparator()
        self.acao_painel = self._acao('propriedades.svg', 'Painel de propriedades', self.alternar_painel)
        self.acao_painel.setCheckable(True)

    def _acao(self, icone, texto, callback):
        a = QAction(_icone(icone), texto, self.iface.mainWindow())
        if callback:
            a.triggered.connect(callback)
        self.toolbar.addAction(a)
        self.menu.addAction(a)
        self.acoes.append(a)
        return a

    def unload(self):
        canvas = self.iface.mapCanvas()
        for ft in self.ferramentas.values():
            if canvas.mapTool() is ft:
                canvas.unsetMapTool(ft)
        if self.painel is not None:
            self.iface.removeDockWidget(self.painel)
            self.painel.deleteLater()
            self.painel = None
        for a in self.acoes:
            a.deleteLater()
        if self.menu is not None:
            self.menu_pai.removeAction(self.menu.menuAction())
        if self.toolbar is not None:
            self.toolbar.deleteLater()

    # ---------- calco ----------
    def _pasta_padrao(self):
        return QgsSettings().value('EBGeo/calco/pasta', os.path.expanduser('~'))

    def novo_calco(self):
        caminho, _ = QFileDialog.getSaveFileName(self.iface.mainWindow(), 'Novo calco',
                                                 os.path.join(self._pasta_padrao(), 'calco.gpkg'),
                                                 'GeoPackage (*.gpkg)')
        if not caminho:
            return None
        if not caminho.lower().endswith('.gpkg'):
            caminho += '.gpkg'
        return self._usar_calco(caminho)

    def abrir_calco(self):
        caminho, _ = QFileDialog.getOpenFileName(self.iface.mainWindow(), 'Abrir calco',
                                                 self._pasta_padrao(), 'GeoPackage (*.gpkg)')
        if not caminho:
            return None
        return self._usar_calco(caminho)

    def _usar_calco(self, caminho):
        QgsSettings().setValue('EBGeo/calco/pasta', os.path.dirname(caminho))
        c = Calco(caminho)
        c.criar()
        c.carregar()
        definir_calco_ativo(c)
        self.iface.messageBar().pushSuccess('EBGeo', 'Calco ativo: {}'.format(c.nome))
        return c

    def _garantir_calco(self):
        c = calco_ativo()
        if c is None:
            c = self.novo_calco()
        return c

    # ---------- ferramentas ----------
    def _ativar(self, ft):
        if self._garantir_calco() is None:
            if ft.action():
                ft.action().setChecked(False)
            return
        self.iface.mapCanvas().setMapTool(ft)

    def _preparar_ponto(self, tipo, ponto_wgs, attrs):
        if tipo == 'military_symbol':
            ultimo = QgsSettings().value(CHAVE_SIDC, '')
            if ultimo:
                attrs['sidc'] = ultimo
        elif tipo == 'magnetic_declination':
            try:
                from .motor import declinacao
                web = declinacao.calcular(ponto_wgs.y(), ponto_wgs.x()) or {}
                m = schema.mapa_web(tipo)
                attrs.update({m[k]: v for k, v in web.items() if k in m})
            except Exception as e:
                self.iface.messageBar().pushWarning('EBGeo', 'Declinação não calculada: {}'.format(e))
        return attrs

    def _feicao_criada(self, layer, tipo, ebgeo_id):
        self.mostrar_painel()
        self.painel.mostrar_feicao(layer, ebgeo_id)

    # ---------- painel ----------
    def mostrar_painel(self):
        if self.painel is None:
            from .ui.painel import PainelCalco
            self.painel = PainelCalco(self.iface, abrir_construtor_sidc=self.construtor_sidc)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.painel)
            self.painel.visibilityChanged.connect(self.acao_painel.setChecked)
        self.painel.show()
        self.painel.raise_()

    def alternar_painel(self, ligado):
        if ligado:
            self.mostrar_painel()
        elif self.painel is not None:
            self.painel.hide()

    def construtor_sidc(self, feat, layer):
        try:
            from .ui.construtor_sidc import ConstrutorSidc
        except ImportError:
            self.iface.messageBar().pushWarning('EBGeo', 'Construtor de SIDC indisponível; digite o SIDC.')
            return None
        dlg = ConstrutorSidc(feat, self.iface.mainWindow())
        if dlg.exec():
            novo = dlg.valores()
            if novo.get('sidc'):
                QgsSettings().setValue(CHAVE_SIDC, novo['sidc'])
            return novo
        return None

    # ---------- importação ----------
    def importar_ebgeo(self):
        from qgis import processing
        try:
            processing.execAlgorithmDialog('EBGeoProvider:importarebgeo')
        except Exception as e:
            self.iface.messageBar().pushCritical('EBGeo', 'Importador indisponível: {}'.format(e))
