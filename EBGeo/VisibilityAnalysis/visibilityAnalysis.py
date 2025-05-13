# -*- coding: utf-8 -*-

import random
from uuid import uuid4
import processing
from EBGeo.VisibilityAnalysis.viewshedTool import ViewshedTool
from qgis.PyQt.QtCore import QObject, pyqtSlot, QVariant
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
from PyQt5.QtGui import QColor
from typing import Optional
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QMessageBox,
)
from qgis.gui import QgisInterface
from EBGeo.VisibilityAnalysis.visibilityAnalysis_ui import (
    Ui_VisibilityAnalysisDockWidget,
)
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
        viewshedLyr = self.targetSectorMapLayerComboBox.currentLayer()
        self.sectorTargetAndElevationModelLayer()
        if viewshedLyr is None:
            self.resetAtivarButton()
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr(
                    "Selecione uma camada de visada"
                ),
            )
            return
        
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
        
        if not state:
            self.canvas.unsetMapTool(self.myTool)
            return
        self.ativarButton.setEnabled(True)
        self.viewshedLyrId = viewshedLyr.id()
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_estilos = os.path.join(caminho_atual, 'style')
        path_qml = os.path.join(pasta_estilos, 'style_target_sector.qml')
        viewshedLyr.loadNamedStyle(path_qml)
        viewshedLyr.triggerRepaint()
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
        self.iface.setActiveLayer(layer)
        rasterList = []
        
        if mds.bandCount() != 1:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr("Verifique o raster colocado como Modelo Digital de Superfície, pois esse possui apenas 1 banda.")
            )
            return

        for feat in layer.getFeatures():
            altura_obs = feat["altura_obs"]
            central_point = self.getCentralPointTargetSector(feat)
            max_distance = self.getMaxDistance(feat)

            centralPointGeometry = QgsGeometry.fromPointXY(central_point)
            transform = QgsCoordinateTransform(
                layer.crs(), mds.crs(), QgsProject.instance()
            )
            centralPointGeometry.transform(transform)
            extentRaster = mds.extent()
            geomExtentRaster = QgsGeometry.fromRect(extentRaster)
            if not centralPointGeometry.intersects(geomExtentRaster):
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Erro!"),
                    self.tr("Há setores de visada fora do Modelo Digital de Superfície")
                )
                return

            temp_mask_layer = processing.run(
                "native:polygonfromlayerextent",
                {
                    'INPUT':layer,
                    'ROUND_TO':0,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                },
            )["OUTPUT"]

            reproject_layer = processing.run("native:reprojectlayer", 
                {
                    'INPUT':temp_mask_layer,
                    'TARGET_CRS':QgsCoordinateReferenceSystem('EPSG:3857'),
                    'CONVERT_CURVED_GEOMETRIES':False,
                    'OPERATION':'+proj=noop',
                    'OUTPUT':'TEMPORARY_OUTPUT'
                }
            )["OUTPUT"]

            buffer_layer = processing.run("native:buffer", 
                {
                    'INPUT':reproject_layer,
                    'DISTANCE':90,
                    'SEGMENTS':5,
                    'END_CAP_STYLE':0,
                    'JOIN_STYLE':0,
                    'MITER_LIMIT':2,
                    'DISSOLVE':False,
                    'SEPARATE_DISJOINT':False,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                }
            )["OUTPUT"]

            clip_result_path = processing.run("gdal:cliprasterbymasklayer",
                {
                    'INPUT': mds,
                    'MASK': buffer_layer,
                    'SOURCE_CRS': None,
                    'TARGET_CRS': None,
                    'NODATA': None,
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': True,
                    'KEEP_RESOLUTION': False,
                    'SET_RESOLUTION': False,
                    'X_RESOLUTION': None,
                    'Y_RESOLUTION': None,
                    'MULTITHREADING': False,
                    'OPTIONS': '',
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                },
            )['OUTPUT']

            temp_output = QgsProcessingUtils.generateTempFilename(
                    f"local_viewshed_{str(uuid4().hex)}.tif"
                )
            try:
                viewshed_result = processing.run(
                    "gdal:viewshed",
                    {
                        'INPUT': clip_result_path,
                        'BAND' : 1,
                        'EXTRA' : '',
                        'MAX_DISTANCE' : max_distance,
                        'OBSERVER': f"{central_point.x()},{central_point.y()} [{layer.crs().authid()}]",
                        'OBSERVER_HEIGHT': altura_obs,
                        'TARGET_HEIGHT': 0.0,
                        'OPTIONS' : None,
                        'OUTPUT': temp_output,
                    },
                )['OUTPUT']
            except:
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    self.tr("Erro!"),
                    self.tr("Verifique o Modelo Digital de Elevação se está correto.")
                )
                return
            viewshed_result = QgsRasterLayer(viewshed_result)
 
            tempLyrForEachFeat = QgsVectorLayer("Polygon?crs={}".format(layer.crs().authid()), "featLayer", "memory")
            provider = tempLyrForEachFeat.dataProvider()
            provider.addFeature(feat)
            clip_result_path = processing.run("gdal:cliprasterbymasklayer",
                {
                    'INPUT': viewshed_result,
                    'MASK': tempLyrForEachFeat,
                    'SOURCE_CRS': mds.crs(),
                    'TARGET_CRS': tempLyrForEachFeat.crs(),
                    'NODATA': None,
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': False,
                    'KEEP_RESOLUTION': False,
                    'SET_RESOLUTION': False,
                    'X_RESOLUTION': None,
                    'Y_RESOLUTION': None,
                    'MULTITHREADING': False,
                    'OPTIONS': '',
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                },
            )['OUTPUT']
            clip_result = QgsRasterLayer(clip_result_path)
            rasterList.append(clip_result)

        if len(rasterList) == 0:
            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Erro!"),
                self.tr(
                    "Não há nenhum setor de visada adquirido."
                ),
            )
            return
            
        finalRasterLayer = self.sumRasters(rasterList)

        clip_result_path = processing.run("gdal:cliprasterbymasklayer",
            {
                'INPUT': finalRasterLayer,
                'MASK': layer,
                'SOURCE_CRS': finalRasterLayer.crs(),
                'TARGET_CRS': layer.crs(),
                'NODATA': None,
                'ALPHA_BAND': False,
                'CROP_TO_CUTLINE': False,
                'KEEP_RESOLUTION': False,
                'SET_RESOLUTION': False,
                'X_RESOLUTION': None,
                'Y_RESOLUTION': None,
                'MULTITHREADING': False,
                'OPTIONS': '',
                'DATA_TYPE': 0,
                'EXTRA': '',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            },
        )['OUTPUT']
        clip_result = QgsRasterLayer(clip_result_path)
            
        coloredFinalRasterLayer = self.colorSummedRaster(clip_result, rasterList)

        vectorColoredFinalRasterLayer = processing.run("grass:r.to.vect", 
            {
                'input':coloredFinalRasterLayer,
                'type':2,
                'column':'value',
                '-s':False,
                '-v':False,
                '-z':False,
                '-b':False,
                '-t':False,
                'output':'TEMPORARY_OUTPUT','GRASS_REGION_PARAMETER':None,
                'GRASS_REGION_CELLSIZE_PARAMETER':0,
                'GRASS_OUTPUT_TYPE_PARAMETER':0,
                'GRASS_VECTOR_DSCO':'',
                'GRASS_VECTOR_LCO':'',
                'GRASS_VECTOR_EXPORT_NOCAT':False
            }
        )['output']
        vectorColoredFinalRasterLayer = QgsVectorLayer(vectorColoredFinalRasterLayer, "Vetor Resultante da Linha de Visada")
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
                if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
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
        
    def sumRasters(self, rasterList):
        # Criar expressões e entradas para o QgsRasterCalculator
        entries = []
        expression = ""
        for i, raster in enumerate(rasterList):
            entry = QgsRasterCalculatorEntry()
            entry.ref = f"layer{i}@1"
            entry.raster = raster
            entry.bandNumber = 1
            entries.append(entry)

            expression += f"{entry.ref}"
            if i < len(rasterList) - 1:
                expression += " + "

        # Modificação: Normalizar a soma dividindo por 255
        # Isso transformará valores como 0, 255, 510 em 0, 1, 2...
        expression = f"({expression}) / 255"

        # Criar raster temporário
        temp_output = QgsProcessingUtils.generateTempFilename(
                    f"normalized_sum_{str(uuid4().hex)}.tif"
                )

        # Usar QgsRasterCalculator para somar os rasters e normalizar
        calc = QgsRasterCalculator(
            expression,
            temp_output,
            "GTiff",
            rasterList[0].extent(),
            rasterList[0].width(),
            rasterList[0].height(),
            entries
        )

        result = calc.processCalculation()
        if result == 0:
            # Adiciona o raster normalizado ao QGIS como camada temporária
            crs = rasterList[0].crs()
            summed_layer = QgsRasterLayer(temp_output, "Soma Normalizada", "gdal")
            summed_layer.setCrs(crs)
            return summed_layer
        else:
            return

    def colorSummedRaster(self, finalRasterLayer, rasterList):
        # Criação do shader
        shader = QgsRasterShader()
        color_ramp = QgsColorRampShader()
        color_ramp.setColorRampType(QgsColorRampShader.Exact)

        # Lista de valores de pixel possíveis (ex: 0 a 5)
        max_value = len(rasterList)  # ajuste conforme o número máximo de interseções possíveis
        entries = []

        # Valor 0 = vermelho
        entries.append(QgsColorRampShader.ColorRampItem(0, QColor('red'), "Nenhuma"))

        # Demais valores = cores aleatórias
        for i in range(1, max_value + 1):
            color = QColor.fromRgb(
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
            entries.append(QgsColorRampShader.ColorRampItem(float(i), color, f"{i}"))

        # Aplicar entradas ao shader
        color_ramp.setColorRampItemList(entries)
        shader.setRasterShaderFunction(color_ramp)

        # Aplicar renderer ao raster
        renderer = QgsSingleBandPseudoColorRenderer(finalRasterLayer.dataProvider(), 1, shader)
        finalRasterLayer.setRenderer(renderer)
        finalRasterLayer.triggerRepaint()
        return finalRasterLayer

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
        dtprovider.addAttributes([QgsField("altura_obs", QVariant.Double)])
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
