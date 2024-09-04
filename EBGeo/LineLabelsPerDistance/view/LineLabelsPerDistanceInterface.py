# -*- coding: utf-8 -*-
from qgis.PyQt import uic, QtCore, QtGui, QtWidgets
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer, QgsProject, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsMapLayer, QgsTextFormat, QgsTextBufferSettings
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog, QDialogButtonBox
from qgis.gui import QgsProjectionSelectionDialog
from qgis.PyQt.QtCore import pyqtSlot, pyqtSignal, Qt, QObject
from PyQt5.QtGui import QFont
from qgis.PyQt.QtGui import QColor
import os
import math
from qgis import processing

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'LineLabelsPerDistance.ui'))

class LineLabelsPerDistance(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self):
        super(LineLabelsPerDistance, self).__init__()
        self.setupUi(self)
        self.mapLayerSelection.layerChanged.connect(self.mudarCamada)
        self.mudarCamada()
        self.initVariables()

    def initVariables(self):
        self.name = None
        self.folder = None
        self.epsg = None
        self.LineLabelsPerDistanceInterface = None

    def showDialog(self):
        self.show()
    
    def calcular(self, camada: QgsVectorLayer, distancia):
        camadaReprojetada = self.camadaEmMetros(camada)

        camadaPontos = self.createPointsAlongLine(camadaReprojetada, distancia)   

        self.setLayerLabels(camadaPontos, "distance")    

        QgsProject.instance().addMapLayer(camadaPontos)
        return 
          
    def camadaEmMetros(self, camada: QgsVectorLayer)->QgsVectorLayer:
        crs = camada.crs()
        if not crs.isGeographic():
            return camada
        return self.reprojetarCamada(camada)

    def reprojetarCamada(self, camada: QgsVectorLayer)->QgsVectorLayer:
        crsEmMetros = self.crsEmMetros(camada)
        output = processing.run(
            "native:reprojectlayer",
            {"INPUT": camada, "TARGET_CRS": crsEmMetros, "OUTPUT": "TEMPORARY_OUTPUT"}
        )
        return output["OUTPUT"]
    
    def crsEmMetros(self, camada: QgsVectorLayer)->QgsVectorLayer:
        extent = camada.extent()
        crs1 = self.getSirgasAuthIdByPointLatLong(extent.yMinimum(), extent.xMinimum())
        crs2 = self.getSirgasAuthIdByPointLatLong(extent.yMaximum(), extent.xMaximum())
        crs = crs1 if crs1==crs2 else "EPSG:3857"
        return crs
    
    def createPointsAlongLine(self, camadaReprojetada, distancia):
        return processing.run(
            "native:pointsalonglines", 
            {
                'INPUT': camadaReprojetada,
                'DISTANCE': distancia,
                'START_OFFSET': 0,
                'END_OFFSET': 0,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
        )['OUTPUT']
    
    def setLayerLabels(self, camadaPontos, field_name):
        layer_settings = QgsPalLayerSettings()
        text_format = QgsTextFormat()
        
        # Font
        text_format.setFont(QFont("Arial", 12))
        text_format.setSize(12)
        
        # Buffer
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor("white"))

        text_format.setBuffer(buffer_settings)
        layer_settings.setFormat(text_format)
        
        layer_settings.fieldName = field_name
        layer_settings.enabled = True
        layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
        
        camadaPontos.setLabelsEnabled(True)
        camadaPontos.setLabeling(layer_settings)
        camadaPontos.triggerRepaint()

    def getSirgasAuthIdByPointLatLong(self, lat, long):
        """
        Calculates SIRGAS 2000 epsg.
        <h2>Example usage:</h2>
        <ul>
        <li>Found: getSirgarAuthIdByPointLatLong(-8.05389, -34.881111) -> 'ESPG:31985'</li>
        <li>Not found: getSirgarAuthIdByPointLatLong(lat, long) -> ''</li>
        </ul>
        """
        zone_number = math.floor(((long + 180) / 6) % 60) + 1
        if lat >= 0:
            zone_letter = "N"
        else:
            zone_letter = "S"
        return self.getSirgasEpsg("{0}{1}".format(zone_number, zone_letter))

    def getSirgasEpsg(self, key):
        options = {
            "11N": "EPSG:31965",
            "12N": "EPSG:31966",
            "13N": "EPSG:31967",
            "14N": "EPSG:31968",
            "15N": "EPSG:31969",
            "16N": "EPSG:31970",
            "17N": "EPSG:31971",
            "18N": "EPSG:31972",
            "19N": "EPSG:31973",
            "20N": "EPSG:31974",
            "21N": "EPSG:31975",
            "22N": "EPSG:31976",
            "17S": "EPSG:31977",
            "18S": "EPSG:31978",
            "19S": "EPSG:31979",
            "20S": "EPSG:31980",
            "21S": "EPSG:31981",
            "22S": "EPSG:31982",
            "23S": "EPSG:31983",
            "24S": "EPSG:31984",
            "25S": "EPSG:31985",
            "26S": "EPSG:5396",
        }
        return options[key] if key in options else "EPSG:3857"

    @pyqtSlot()
    def on_buttonBox_accepted(self):
        layer = self.mapLayerSelection.currentLayer()
        distancia = self.doubleSpinBox.value()

        #Verificação de erros
        if not self.validaInput(layer, distancia):
            LineLabelsPerDistance().exec()
            return
        
        
        self.calcular(layer, distancia)
        return 
    
    def validaInput(self, layer: QgsVectorLayer, distancia):
        crs = layer.crs()
        if layer.featureCount() == 0:
            QMessageBox.warning(self, "Camada Vazia", "A camada selecionada está vazia.")
            return False
        if not crs.isValid():
            QMessageBox.warning(self, "CRS Inválido", f"O CRS da camada é inválido.")
            return False
        if distancia == 0:
            QMessageBox.warning(self, "Distância inválida",  "Insira uma distância diferente de zero.")
            return False
        return True
    
    def mudarCamada(self):
        if self.mapLayerSelection.currentLayer() is None:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        else:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)

    
           
    
