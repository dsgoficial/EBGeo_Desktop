# -*- coding: utf-8 -*-

from uuid import uuid4
from EBGeo.VisibilityAnalysis.viewshedTool import ViewshedTool
from qgis.PyQt.QtCore import QObject, pyqtSlot, QMetaType
from qgis.PyQt.QtGui import *
from qgis.core import *
from qgis.gui import *
from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsField,
    QgsCoordinateReferenceSystem,
    QgsProcessing,
    QgsProject,
    QgsProcessingUtils,
    QgsProject,
    QgsProcessingFeatureSourceDefinition,
    QgsGeometry,
    QgsRasterShader,
    QgsColorRampShader,
    QgsCoordinateTransform,
    QgsSingleBandPseudoColorRenderer,
    QgsStyle,
    QgsRendererCategory,
    QgsWkbTypes,
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsSymbol
)
from typing import Optional
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDockWidget,
    QMessageBox,
)
from qgis.gui import QgisInterface
from EBGeo.VisibilityAnalysis.visibilityAnalysis_ui import (
    Ui_VisibilityAnalysisDockWidget,
)
from EBGeo.Visada import nucleo
from EBGeo.Visada.refracao import K_OPTICO
from EBGeo.Visada.tarefa import TarefaVisada
import os

class VisibilityAnalysis(
    QDockWidget, Ui_VisibilityAnalysisDockWidget
):

    def __init__(self, iface: QgisInterface, parent: Optional[QObject] = None):
        super(VisibilityAnalysis, self).__init__(parent)
        self.setupUi(self)
        self.parent: Optional[QObject] = parent
        self.iface: QgisInterface = iface
        self.canvas = self.iface.mapCanvas()
        self.projeto = QgsProject.instance()
        self.clickedPoint = ''
        self.myTool = None
        self.eventFilter = None
        self.viewshedLyrId = None
        self.targetSectorMapLayerComboBox.setAllowEmptyLayer(True)
        self.targetSectorMapLayerComboBox.setCurrentIndex(-1)
        self.targetSectorMapLayerComboBox.layerChanged.connect(self.onLayerChanged)
        self.elevationModelMapLayerComboBox.setAllowEmptyLayer(True)
        self.elevationModelMapLayerComboBox.setCurrentIndex(-1)
        self.elevationModelMapLayerComboBox.layerChanged.connect(self.sectorTargetAndElevationModelLayer)
        QgsProject.instance().layersWillBeRemoved.connect(self.onLayersWillBeRemoved)
        QgsProject.instance().layerRemoved.connect(self.onLayerRemoved)
        self.canvas.mapToolSet.connect(self.onMapToolChanged)
        self.ativarButton.toggled.connect(self.doWork)
        self.processarButton.clicked.connect(self.runTest)
        self.initButton()
    
    def initButton(self):
        self.ativarButton.setEnabled(False)
        self.processarButton.setEnabled(False)

    def onLayerChanged(self, layer):
        """Quando a camada é alterada no combobox, verifica se precisamos desativar a ferramenta"""
        if self.myTool is not None and (layer is None or self.myTool.layer.id() != layer.id()):
            # Desativa o botão
            self.ativarButton.setChecked(False)
            
            # Importante: desativa a ferramenta explicitamente
            self.deactivateTool()
            
            # Reseta o cursor do mapa para o cursor padrão
            self.canvas.unsetMapTool(self.myTool)
            self.canvas.setMapTool(self.canvas.mapTool())
        
        self.sectorTargetAndElevationModelLayer()
        
    def sectorTargetAndElevationModelLayer(self):
        if self.targetSectorMapLayerComboBox.currentLayer() == None or self.elevationModelMapLayerComboBox.currentLayer() == None:
            self.ativarButton.setEnabled(False)
            self.processarButton.setEnabled(False)
            return
        else:
            self.ativarButton.setEnabled(True)
            self.processarButton.setEnabled(True)
            return
    
    def desactiveButtons(self):
        if self.ativarButton.isChecked():
            self.ativarButton.setChecked(False)
            return
        
    def onLayerRemoved(self, layerRemovedId):
        if layerRemovedId != self.viewshedLyrId:
            return
        self.ativarButton.setEnabled(False) 
        self.processarButton.setEnabled(False) 
        self.targetSectorMapLayerComboBox.setCurrentIndex(-1)
        
    def onLayersWillBeRemoved(self, layerIds):
        """
        Manipula o evento de remoção de camadas.
        Desativa a ferramenta e limpa os comboboxes apenas se as camadas 
        atualmente selecionadas forem removidas.
    
        Args:
            layerIds: Lista de IDs das camadas que serão removidas
        """
        # Verificar se a ferramenta está ativa com uma camada que será removida
        if self.myTool is not None and hasattr(self.myTool, 'layer') and self.myTool.layer is not None:
            # Verificar se a camada atual da ferramenta está na lista de camadas a serem removidas
            if self.myTool.layer.id() in layerIds:
                # Desativa o botão
                self.ativarButton.setChecked(False)
                # Limpa a referência à ferramenta
                self.deactivateTool()

    def onMapToolChanged(self, tool):
        """Manipula o evento de mudança de ferramenta do mapa"""
        if self.myTool is not None and tool is not self.myTool:
            # Se outra ferramenta foi ativada, desmarque nosso botão
            self.ativarButton.setChecked(False)
    
    def verifyTool(self, tool):
        if tool != self.myTool:
            self.ativarButton.setChecked(False)
    
    def createVertexMarker(self):
        self.clickedPoint = QgsVertexMarker(self.canvas)
    
    def deactivateTool(self):
        """Desativa a ferramenta atual e limpa as referências"""
        if self.myTool is not None:
            self.canvas.unsetMapTool(self.myTool)
            
            # Desconectar sinais específicos da ferramenta
            if hasattr(self.myTool, 'toolDeactivatedByLayerRemoval'):
                try:
                    self.myTool.toolDeactivatedByLayerRemoval.disconnect()
                except:
                    pass
            
            # Remover marcadores de vértice, se houver
            if hasattr(self, 'clickedPoint') and self.clickedPoint and not isinstance(self.clickedPoint, str):
                self.canvas.scene().removeItem(self.clickedPoint)
                self.clickedPoint = ''
            
            # Limpar a referência da ferramenta
            self.myTool = None

    def doWork(self, state):
        """
        Ativa ou desativa a ferramenta de visibilidade (ViewshedTool) quando o botão 'Ativar' é clicado.
        Inclui a validação de SRC entre setor e projeto (o MDE pode estar em qualquer SRC).
        """
        # Obtém a camada de visada selecionada
        viewshedLyr = self.targetSectorMapLayerComboBox.currentLayer()
        self.sectorTargetAndElevationModelLayer()  # Atualiza estado dos botões

        if viewshedLyr is None:
            self.resetAtivarButton()
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Selecione uma camada de visada.")
            )
            return

        # Verifica se a camada tem o campo 'altura_obs'
        if "altura_obs" not in [f.name() for f in viewshedLyr.fields()]:
            self.resetAtivarButton()
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("A camada deve ter um campo chamado 'altura_obs'.")
            )
            return

        # Verifica se o botão foi desmarcado (desativação)
        if not state:
            if self.myTool is not None:
                self.canvas.unsetMapTool(self.myTool)
            return

        # Habilita o botão apenas se ambas camadas estiverem presentes
        self.ativarButton.setEnabled(True)
        self.viewshedLyrId = viewshedLyr.id()

        # Obtém o MDE selecionado
        mde_layer = self.elevationModelMapLayerComboBox.currentLayer()
        if not mde_layer:
            self.resetAtivarButton()
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Selecione um Modelo Digital de Elevação (MDE).")
            )
            return

        # --- VALIDAÇÃO DE SRC ---
        # A ferramenta desenha o setor nas coordenadas do mapa e grava na camada sem transformar:
        # setor e projeto têm de ter o mesmo SRC. O MDE pode estar em qualquer SRC (o motor de
        # visada reprojeta para um SRC métrico quando ele está em graus).
        setor_epsg = viewshedLyr.crs().authid()
        projeto_epsg = self.canvas.mapSettings().destinationCrs().authid()

        if viewshedLyr.crs() != self.canvas.mapSettings().destinationCrs():
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Erro de Projeção",
                f"Combinação de projeções inválida!\n"
                f"Setor: {setor_epsg}\n"
                f"Projeto: {projeto_epsg}\n\n"
                "A camada de setores deve ter o mesmo SRC do projeto."
            )
            self.resetAtivarButton()
            return
        # --- FIM VALIDAÇÃO DE SRC ---

        # Aplica estilo de visada
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_estilos = os.path.join(caminho_atual, 'style')
        path_qml = os.path.join(pasta_estilos, 'style_target_sector.qml')
        viewshedLyr.loadNamedStyle(path_qml)
        viewshedLyr.triggerRepaint()

        # Cria e ativa a ferramenta ViewshedTool
        self.myTool = ViewshedTool(
            canvas=self.canvas,
            layer=viewshedLyr,
            observer_height_field_name="altura_obs",
        )
        self.canvas.setMapTool(self.myTool)

    
    def resetAtivarButton(self):
        """Reseta o botão de ativar quando a ferramenta é desativada externamente"""
        self.ativarButton.blockSignals(True)
        self.ativarButton.setChecked(False)
        self.ativarButton.blockSignals(False)
    
    def runTest(self):
        # Primeiro, desativa o botão ativar se estiver ligado
        if self.ativarButton.isChecked():
            self.ativarButton.setChecked(False)
            # Se o botão for desativado, a ferramenta também deve ser desativada
            self.deactivateTool()

        # Pega a camada do combo de setor de visada
        viewshedLyr = self.targetSectorMapLayerComboBox.currentLayer()
        mds = self.elevationModelMapLayerComboBox.currentLayer()

        if "altura_obs" not in [f.name() for f in viewshedLyr.fields()]:
            self.resetAtivarButton()
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr(
                    "A camada deve ter um campo chamado altura_obs"
                ),
            )
            return

        # Verifica se as camadas foram selecionadas
        if not viewshedLyr or not mds:
            self.ativarButton.setChecked(False)
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Selecione uma camada de visada e um modelo de elevação")
            )
            return

        if viewshedLyr.isEditable():
            # Salva as edições na camada
            viewshedLyr.commitChanges()

        # Continua com o processamento normal
        self.viewshedOfFeatTargetSector(viewshedLyr, mds)
    
    def viewshedOfFeatTargetSector(self, layer, mds):
        """
        Soma dos observadores por setor, pelo GDAL (sem GRASS): cada setor tem o observador no
        primeiro vértice e alcance até o vértice mais distante; a célula vale quantos observadores
        a veem dentro do próprio setor. Saída: polígonos com o campo "value", como a do r.to.vect.
        """
        self.iface.setActiveLayer(layer)

        if mds.bandCount() != 1:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Verifique o raster colocado como Modelo Digital de Superfície, pois esse possui apenas 1 banda.")
            )
            return
        if mds.providerType() != 'gdal':
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("O Modelo Digital de Elevação precisa ser um raster em arquivo lido pelo GDAL.")
            )
            return

        transform = QgsCoordinateTransform(layer.crs(), mds.crs(), QgsProject.instance())
        setores = []
        for feat in layer.getFeatures():
            try:
                altura_obs = float(feat["altura_obs"])
            except (TypeError, ValueError):
                altura_obs = float("nan")
            if altura_obs != altura_obs:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Erro!"),
                    self.tr("Há setor de visada sem altura do observador (altura_obs).")
                )
                return
            featGeom = QgsGeometry(feat.geometry())
            featGeom.transform(transform)
            setores.append((bytes(featGeom.asWkb()), altura_obs))

        if len(setores) == 0:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Não há nenhum setor de visada adquirido."),
            )
            return

        # O cálculo roda numa QgsTask (progresso e cancelamento no gerenciador de tarefas); a
        # camada, o estilo e a ordem das camadas entram no fim, na linha da interface.
        fonte = mds.source()
        caminho = QgsProcessingUtils.generateTempFilename(f"visada_setores_{uuid4().hex}.gpkg")

        def calcular(progresso, cancelado):
            resultado = nucleo.soma_por_setor(fonte, setores, k=K_OPTICO, progresso=progresso,
                                              cancelado=cancelado)
            if cancelado():
                raise nucleo.Cancelado()
            nucleo.poligonizar(resultado.grade, resultado.matriz, caminho, "value", "visada_setores")
            progresso(100.0)
            return resultado

        self.tarefa = TarefaVisada.iniciar(
            self.tr("Análise de Visibilidade"), calcular,
            lambda resultado, erro: self.concluirSetores(resultado, erro, caminho, layer))
        return self.tarefa

    def concluirSetores(self, resultado, erro, caminho, layer):
        """Fim da tarefa, na linha da interface: a camada, o estilo e a ordem, ou o aviso."""
        if erro == 'cancelado':
            self.iface.messageBar().pushInfo(self.tr("Análise de Visibilidade"), self.tr("Cálculo cancelado."))
            return
        if erro is not None:
            QMessageBox.warning(self.iface.mainWindow(), self.tr("Erro!"), erro)
            return
        for aviso in resultado.avisos:
            self.iface.messageBar().pushWarning(self.tr("Análise de Visibilidade"), aviso)

        vectorColoredFinalRasterLayer = QgsVectorLayer(
            f"{caminho}|layername=visada_setores", "Vetor Resultante da Linha de Visada", "ogr")
        QgsProject.instance().addMapLayer(vectorColoredFinalRasterLayer)

        self.apply_red_to_green_gradient_style(vectorColoredFinalRasterLayer, "value")

        self.arrangeLayersInSpecificOrder([layer, vectorColoredFinalRasterLayer])

    def apply_red_to_green_gradient_style(self, layer, field_name):
        """
        Aplica um estilo categorizado com gradiente do vermelho ao verde,
        adaptando-se automaticamente à quantidade de valores presentes na camada.

        Args:
            layer: Camada para aplicar o estilo (QgsVectorLayer)
            field_name: Nome do campo para categorizar

        Returns:
            bool: True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            if not layer or not isinstance(layer, QgsVectorLayer):
                return False

            # Obter os valores únicos presentes no campo
            unique_values = set()
            for feature in layer.getFeatures():
                value = feature[field_name]
                unique_values.add(value)

            # Converter para lista e ordenar
            unique_values = sorted(list(unique_values))

            # Criar categorias para cada valor único
            categories = []

            # Definir o gradiente de vermelho para verde
            red_color = QColor(255, 0, 0)    # Vermelho para o valor 0
            green_color = QColor(0, 255, 0)  # Verde para o valor máximo

            # Número de valores
            num_values = len(unique_values)

            # Criar categorias para cada valor único
            for i, value in enumerate(unique_values):
                # Calcular a cor no gradiente de vermelho para verde
                if num_values > 1:
                    # Calcular a proporção entre vermelho e verde
                    ratio = i / (num_values - 1)

                    # Interpolar a cor
                    r = int(red_color.red() * (1 - ratio) + green_color.red() * ratio)
                    g = int(red_color.green() * (1 - ratio) + green_color.green() * ratio)
                    b = int(red_color.blue() * (1 - ratio) + green_color.blue() * ratio)

                    color = QColor(r, g, b)
                else:
                    # Se houver apenas um valor, usar vermelho
                    color = red_color

                # Criar um símbolo para esta categoria
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                symbol.setColor(color)

                # Para polígonos, definir borda preta
                if layer.geometryType() == QgsWkbTypes.GeometryType.PolygonGeometry:
                    symbol = QgsFillSymbol.createSimple({
                        'color': color.name(),
                        'outline_color': '#000000',
                        'outline_width': '0.25'
                    })

                # Criar a categoria
                label = f"Valor {value}" if value != 0 else "Não visível"
                category = QgsRendererCategory(value, symbol, label, True)

                # Adicionar à lista de categorias
                categories.append(category)

            # Criar o renderizador categorizado
            renderer = QgsCategorizedSymbolRenderer(field_name, categories)

            # Aplicar o renderizador à camada
            layer.setRenderer(renderer)

            # Atualizar a camada
            layer.triggerRepaint()

            # Atualizar a legenda
            self.iface.layerTreeView().refreshLayerSymbology(layer.id())

            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            return False
    
    def arrangeLayersInSpecificOrder(self, layers_list):
        root = QgsProject.instance().layerTreeRoot()

        # Converter string para objeto de camada, se necessário
        layer_objects = []
        for layer in layers_list:
            if isinstance(layer, str):
                layer_obj = QgsProject.instance().mapLayersByName(layer)
                if layer_obj:
                    layer_objects.append(layer_obj[0])
                else:
                    return False
            else:
                layer_objects.append(layer)

        # Remover todas as camadas do projeto e criar clones
        cloned_layers = []
        for layer in layer_objects:
            clone = layer.clone()
            cloned_layers.append(clone)
            QgsProject.instance().removeMapLayer(layer.id())

        # Adicionar as camadas clonadas de volta ao projeto, mas sem adicioná-las à legenda
        for layer in cloned_layers:
            QgsProject.instance().addMapLayer(layer, False)

        # Adicionar as camadas à legenda na ordem correta
        # As primeiras na lista ficam no topo da legenda (último a desenhar)
        for i, layer in enumerate(cloned_layers):
            if i == 0:
                self.targetSectorMapLayerComboBox.setLayer(layer)
                self.viewshedLyrId = layer.id()
            root.insertLayer(i, layer)

        return True
        
    def getCentralPointTargetSector(self, feat):
        geom = feat.geometry()
        polygon = geom.asPolygon()
        centralPoint = polygon[0][0]
        return centralPoint

    def getMaxDistance(self, feat):
        geom = feat.geometry()
        polygon = geom.asPolygon()
        return max(
            polygon[0][0].distance(polygon[0][i]) for i in range(len(polygon[0]))
        )

    def makeTargetSectorLayer(self):
        targetSectorLayer = self.targetSectorMapLayerComboBox.currentLayer()
        if targetSectorLayer is not None:
            return targetSectorLayer, None
        output_layer = QgsVectorLayer(f"Polygon?crs={self.projeto.crs().authid()}", "Setor de Visada", "memory")
        QgsProject.instance().addMapLayer(output_layer)
        dtprovider = output_layer.dataProvider()
        dtprovider.addAttributes([QgsField("altura_obs", QMetaType.Type.Double)])
        output_layer.updateFields()
        return output_layer, dtprovider
    
    @pyqtSlot(bool)
    def on_makeLayerTargetSectorPushButton_clicked(self) -> None:
        output_layer, dtprovider = self.makeTargetSectorLayer()
        self.targetSectorMapLayerComboBox.setLayer(output_layer)
        self.viewshedLyrId = output_layer.id()
    
    @pyqtSlot(bool)
    def on_refreshElevationModelPushButton_clicked(self) -> None:
        activeLayer = self.iface.activeLayer()
        if not isinstance(activeLayer, QgsRasterLayer):
            return
        self.elevationModelMapLayerComboBox.setLayer(activeLayer)
    
    def closeEvent(self, event):
        """
        Sobrescreve o método closeEvent para garantir que a ferramenta seja resetada
        quando o dockwidget for fechado.
        """
        # Desativa o botão se estiver ligado
        if self.ativarButton.isChecked():
            self.ativarButton.setChecked(False)

        # Certifica-se de que a ferramenta seja desativada
        self.deactivateTool()

        # Continua com o comportamento padrão de fechamento
        super(VisibilityAnalysis, self).closeEvent(event)
    
    def unload(self):
        """Chamado quando o plugin é descarregado"""
        # Desativar a ferramenta
        if self.ativarButton.isChecked():
            self.ativarButton.setChecked(False)
            
        # Desconectar sinais
        try:
            QgsProject.instance().layersWillBeRemoved.disconnect(self.onLayersWillBeRemoved)
            self.canvas.mapToolSet.disconnect(self.onMapToolChanged)
            QgsProject.instance().layerRemoved.disconnect(self.onLayerRemoved)
            self.targetSectorMapLayerComboBox.layerChanged.disconnect(self.onLayerChanged)
            self.elevationModelMapLayerComboBox.layerChanged.disconnect(self.sectorTargetAndElevationModelLayer)
        except:
            pass
            
        # Limpar referências
        self.deactivateTool()
