# -*- coding: utf-8 -*-
"""
Barra "Simbologia Militar" e submenu do EBGeo: criar/abrir calco, as 8 ferramentas
do EBGeo Web, o painel de propriedades, a importação e a exportação do .ebgeo.
"""
import os

from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QAction, QActionGroup, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QMenu

from . import schema
from .calco import Calco, calco_ativo, definir_calco_ativo
from .ferramentas import FerramentaLinha, FerramentaPoligono, FerramentaPonto

ICONES = os.path.join(os.path.dirname(__file__), 'icones')

FERRAMENTAS = [
    # tipo, ícone, rótulo
    ('military_symbol', 'simbolo_militar.svg', 'Símbolo Militar'),
    ('coordination_measure', 'medida_coordenacao.svg', 'Medida de Coordenação'),
    ('engineering_symbol', 'simbolo_engenharia.svg', 'Símbolos de Engenharia'),
    ('boundary', 'linha_limite.svg', 'Linha de Limite'),
    ('coordination_line', 'linha_coordenacao.svg', 'Linha de Coordenação'),
    ('coordination_area', 'area_coordenacao.svg', 'Área de Coordenação'),  # sem atalho, como no Web
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
        self._acao('exportar_ebgeo.svg', 'Exportar arquivo .ebgeo...', self.exportar_ebgeo)
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
            elif 'Polygon' in schema.TIPOS[tipo]['geometria']:
                ft = FerramentaPoligono(canvas, tipo, self.iface, preparar_atributos=self._preparar_area)
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
        self.acao_convencoes = self._acao('convencoes.svg', 'Quadro de convenções no layout...',
                                          lambda *_: self.quadro_convencoes())
        # atlas importados de .ebgeo: a carga preguiçosa dos mapas volta a funcionar ao reabrir o projeto
        QgsProject.instance().readProject.connect(self._religar_atlas)
        # guardião das camadas do calco: regras de troca e bloqueio em qualquer caminho de edição
        from . import guardiao
        guardiao.ligar_projeto(QgsProject.instance())
        # no designer de layout, a mesma ação no menu Itens, já com o layout aberto
        self.acoes_designer = []
        if hasattr(self.iface, 'layoutDesignerOpened'):
            self.iface.layoutDesignerOpened.connect(self._designer_aberto)

    def _religar_atlas(self, *_):
        try:
            from .importador import arvore
            arvore.religar(QgsProject.instance())
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage('Atlas .ebgeo não religado: {}'.format(e), 'EBGeo', Qgis.MessageLevel.Warning)

    def _acao(self, icone, texto, callback):
        a = QAction(_icone(icone), texto, self.iface.mainWindow())
        if callback:
            a.triggered.connect(callback)
        self.toolbar.addAction(a)
        self.menu.addAction(a)
        self.acoes.append(a)
        return a

    def unload(self):
        try:
            QgsProject.instance().readProject.disconnect(self._religar_atlas)
        except (TypeError, RuntimeError):
            pass
        from . import guardiao
        guardiao.desligar_todos()
        if hasattr(self.iface, 'layoutDesignerOpened'):
            try:
                self.iface.layoutDesignerOpened.disconnect(self._designer_aberto)
            except (TypeError, RuntimeError):
                pass
        for menu, a in getattr(self, 'acoes_designer', []):
            try:
                menu.removeAction(a)
                a.deleteLater()
            except RuntimeError:  # o designer já fechou
                pass
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
        elif tipo == 'engineering_symbol' and not attrs.get('engineering'):
            try:
                import json
                from .motor.motor import Motor
                attrs['engineering'] = json.dumps(Motor.instancia().engenharia_rascunho(attrs.get('point_code') or '9'))
            except Exception as e:
                self.iface.messageBar().pushWarning('EBGeo', 'Engenharia sem rascunho: {}'.format(e))
        elif tipo == 'magnetic_declination':
            try:
                from .motor import declinacao
                web = declinacao.calcular(ponto_wgs.y(), ponto_wgs.x()) or {}
                m = schema.mapa_web(tipo)
                attrs.update({m[k]: v for k, v in web.items() if k in m})
            except Exception as e:
                self.iface.messageBar().pushWarning('EBGeo', 'Declinação não calculada: {}'.format(e))
        return attrs

    def _preparar_area(self, tipo, attrs):
        """A área nova nasce no último tipo escolhido no painel, com a aparência dele."""
        from .estilos_area import CHAVE_ULTIMO_TIPO, troca_de_simbolo
        ultimo = QgsSettings().value(CHAVE_ULTIMO_TIPO, '')
        if ultimo and ultimo != attrs.get('symbol_code'):
            attrs.update(troca_de_simbolo(attrs, ultimo))
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

    def calco_para_exportar(self):
        """O GeoPackage da camada selecionada, se for de um calco ou atlas; senão, o do calco ativo."""
        from .calco import PROP_CAMINHO
        ativa = self.iface.activeLayer()
        caminho = ativa.customProperty(PROP_CAMINHO) if ativa is not None else None
        if isinstance(caminho, str) and os.path.exists(caminho):
            return caminho
        c = calco_ativo()
        return c.caminho if c is not None else None

    def exportar_ebgeo(self, *_args, perguntar=None):
        """
        Abre o diálogo do algoritmo "Exportar arquivo .ebgeo" com o calco preenchido. O arquivo sai
        do que está GRAVADO no GeoPackage: com edição pendente, pergunta se salva antes.
        `perguntar` substitui a caixa de mensagem (testes).
        """
        from qgis import processing
        from qgis.PyQt.QtWidgets import QMessageBox
        from .exportador.desenho import edicoes_pendentes
        caminho = self.calco_para_exportar()
        if caminho:
            pendentes = edicoes_pendentes(caminho, QgsProject.instance())
            if pendentes:
                texto = ('Há edições não salvas em {}.\n\nO arquivo .ebgeo sai do que está gravado no '
                         'GeoPackage. Salvar as edições antes de exportar?').format(
                    ', '.join(sorted({l.name() for l in pendentes})))
                botoes = QMessageBox.StandardButton
                if perguntar is not None:
                    r = perguntar(texto)
                else:
                    r = QMessageBox.question(self.iface.mainWindow(), 'Exportar arquivo .ebgeo', texto,
                                             botoes.Save | botoes.Ignore | botoes.Cancel, botoes.Save)
                if r == botoes.Cancel:
                    return None
                if r == botoes.Save:
                    for l in pendentes:
                        if not l.commitChanges(False):
                            self.iface.messageBar().pushCritical(
                                'EBGeo', 'Não foi possível salvar {}: {}'.format(l.name(), '; '.join(l.commitErrors())))
                            return None
        try:
            return processing.execAlgorithmDialog('EBGeoProvider:exportarebgeo',
                                                  {'CALCO': caminho} if caminho else {})
        except Exception as e:
            self.iface.messageBar().pushCritical('EBGeo', 'Exportador indisponível: {}'.format(e))
            return None

    # ---------- quadro de convenções ----------
    def _designer_aberto(self, designer):
        a = QAction(_icone('convencoes.svg'), 'Quadro de convenções do calco...', designer.window())
        a.triggered.connect(lambda *_: self.quadro_convencoes(designer.layout(), self._mapa_selecionado(designer)))
        menu = designer.itemsMenu() if hasattr(designer, 'itemsMenu') else designer.layoutMenu()
        menu.addSeparator()
        menu.addAction(a)
        self.acoes_designer.append((menu, a))

    @staticmethod
    def _mapa_selecionado(designer):
        from qgis.core import QgsLayoutItemMap
        try:
            for item in designer.layout().selectedLayoutItems():
                if isinstance(item, QgsLayoutItemMap):
                    return item
        except RuntimeError:
            pass
        return None

    def quadro_convencoes(self, layout=None, mapa=None, dialogo=None):
        """
        Pergunta o layout, o mapa e o recorte e insere (ou refaz) o quadro de convenções.
        `dialogo` é a fábrica do diálogo (o teste passa uma que aceita sem mostrar).
        """
        from .ui.dialogo_convencoes import DialogoConvencoes
        from . import convencoes
        projeto = QgsProject.instance()
        if not projeto.layoutManager().printLayouts():
            self.iface.messageBar().pushWarning(
                'EBGeo', 'Crie antes um layout de impressão com um mapa (Projeto > Novo layout de impressão).')
            return None
        dlg = (dialogo or DialogoConvencoes)(projeto, layout, mapa, self.iface.mainWindow())
        if not dlg.exec():
            return None
        layout, mapa = dlg.layout_escolhido(), dlg.mapa_escolhido()
        if layout is None or mapa is None:
            self.iface.messageBar().pushWarning('EBGeo', 'O layout escolhido não tem mapa.')
            return None
        grupo, entradas = convencoes.montar_quadro(layout, mapa, so_extensao=dlg.so_extensao())
        if grupo is None:
            self.iface.messageBar().pushWarning(
                'EBGeo', 'O mapa "{}" não desenha nenhum símbolo do calco{}.'.format(
                    mapa.displayName(), ' na extensão dele' if dlg.so_extensao() else ''))
            return None
        self.iface.messageBar().pushSuccess(
            'EBGeo', 'Quadro de convenções com {} símbolos no layout "{}".'.format(len(entradas), layout.name()))
        return grupo
