# -*- coding: UTF-8 -*-
import os
import processing
from qgis.PyQt import QtGui, uic, QtCore, QtWidgets
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsCoordinateTransform, QgsProject, QgsRasterLayer, QgsColorRampShader, QgsRasterShader, QgsSingleBandPseudoColorRenderer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication
from ...Visada import nucleo
from ...Visada.refracao import K_OPTICO
from ...Visada.tarefa import TarefaVisada
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker
from .interface_dialog import InterfaceDialog

GUI, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'window.ui'))

class Interface(QtWidgets.QDockWidget, GUI):
    def __init__(self, iface):
        super(Interface, self).__init__()
        self.setupUi(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.clickedPoint = ''
        self.dialog = InterfaceDialog()
        self.myTool = QgsMapToolEmitPoint(self.canvas)
        self.initSignals()
	
    def initSignals(self):
        self.ativarButton.toggled.connect(self.getPoint)
        self.myTool.canvasClicked.connect(self.openDialog)
        self.dialog.finished.connect(self.doWork)
        self.canvas.mapToolSet.connect(self.verifyTool) 		

    def verifyTool(self, tool):
        if tool != self.myTool:
            self.ativarButton.setChecked(False)
        
    def createVertexMarker(self):
        self.clickedPoint = QgsVertexMarker(self.canvas)
        self.clickedPoint.setIconSize(15)
        self.clickedPoint.setPenWidth(3)
		
    def getPoint(self, state):
        if state:
            self.canvas.setMapTool(self.myTool)
            self.createVertexMarker()
        else:
            self.canvas.unsetMapTool(self.myTool)
            self.canvas.scene().removeItem(self.clickedPoint)

    def openDialog(self, point, button):
        self.clickedPoint.setCenter(point)
        params = []
        params.append(point.x())
        params.append(point.y())
        params.append(self.canvas.mapSettings().destinationCrs())
        self.dialog.setCoords(params)
        self.dialog.exec()

    def setRasterStyle(self, raster_layer):
        shaderType = QgsColorRampShader()
        shaderType.setColorRampType(QgsColorRampShader.Type.Discrete)
        item_list = []
        item_list.append(QgsColorRampShader.ColorRampItem(0, QColor(0, 0, 0), lbl = "Sem visada"))
        item_list.append(QgsColorRampShader.ColorRampItem(1, QColor(0, 255, 0), lbl = "Visível"))
        shaderType.setColorRampItemList(item_list)
        shader = QgsRasterShader()
        shader.setRasterShaderFunction(shaderType)
        renderer = QgsSingleBandPseudoColorRenderer(raster_layer.dataProvider(), 1, shader)
        raster_layer.setRenderer(renderer)
        raster_layer.triggerRepaint()

    def doWork(self, inputPoint, pointCrs):
        if not self.layerCombo.currentLayer():
            QMessageBox.critical(self, u"Erro", u"Nenhuma camada raster selecionada. Selecione uma camada.")
            return

        workingLayer = self.layerCombo.currentLayer()
        outputpath = self.outputFile.filePath()

        if not outputpath:
            QMessageBox.critical(self, u"Erro", u"Nenhum arquivo de saída definido. Escolha um arquivo de saída.")
            return
        if not outputpath.endswith(".tif"):
            outputpath = outputpath + '.tif'

        if workingLayer.providerType() != 'gdal':
            QMessageBox.critical(self, u"Erro", u"O MDT precisa ser um raster em arquivo lido pelo GDAL.")
            return

        transformer = QgsCoordinateTransform(pointCrs, workingLayer.crs(), QgsProject.instance())
        workPoint = transformer.transform(inputPoint)

        # Visada pelo GDAL (sem GRASS): recorte ao alcance, SRC métrico se o MDE estiver em graus,
        # curvatura da Terra e refração óptica (k de Visada/refracao.py). Saída 0/1 como a do
        # r.viewshed -b que esta ferramenta usava. O cálculo roda numa QgsTask (progresso e
        # cancelamento no gerenciador de tarefas); a camada entra no fim, na linha da interface.
        fonte = workingLayer.source()
        x, y = workPoint.x(), workPoint.y()
        altura, alcance = self.heightSpinBox.value(), self.rangeSpinBox.value()

        def calcular(progresso, cancelado):
            from osgeo import gdal
            resultado = nucleo.mapa_visibilidade(fonte, x, y, altura, alcance, k=K_OPTICO,
                                                 progresso=progresso, cancelado=cancelado)
            if cancelado():
                raise nucleo.Cancelado()
            nucleo.salvar_geotiff(resultado.grade, resultado.matriz, outputpath, gdal.GDT_Byte,
                                  nucleo.SEM_DADO_MAPA)
            progresso(100.0)
            return resultado

        self.tarefa = TarefaVisada.iniciar(u"Mapa de visibilidade", calcular,
                                           lambda resultado, erro: self.concluir(resultado, erro, outputpath))
        return self.tarefa

    def concluir(self, resultado, erro, outputpath):
        """Fim da tarefa, na linha da interface: a camada e o estilo, ou o aviso."""
        if erro == 'cancelado':
            self.iface.messageBar().pushInfo(u"Mapa de visibilidade", u"Cálculo cancelado.")
            return
        if erro is not None:
            QMessageBox.warning(self, u"Mapa de visibilidade", erro)
            return
        for aviso in resultado.avisos:
            self.iface.messageBar().pushWarning(u"Mapa de visibilidade", aviso)

        visibLayer = QgsRasterLayer(outputpath, "Mapa de visibilidade")
        QgsProject.instance().addMapLayer(visibLayer)
        self.setRasterStyle(visibLayer)
