# -*- coding: UTF-8 -*-
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtWidgets import QMessageBox

class VertexFinderTool(QgsMapToolIdentifyFeature):
    
    pointFound = pyqtSignal(QgsFeature, QgsCoordinateReferenceSystem)
    
    def __init__(self, iface):
        super(VertexFinderTool, self).__init__(iface.mapCanvas())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.iface = iface
        
    def canvasReleaseEvent(self, event):
        found_features = self.identify(event.x(), event.y(), QgsMapToolIdentify.TopDownAll, self.VectorLayer)

        if len(found_features) == 0:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Aviso",                  
                "Nenhum ponto selecionado!"  
            )
            return

        if len(found_features) > 0:
            for feat in found_features:
                feature = feat.mFeature
                layer = feat.mLayer
                if feature.geometry().type() == QgsWkbTypes.GeometryType.PointGeometry:
                    self.iface.layerTreeView().setCurrentLayer(layer)
                    crs = layer.crs()
                    layer.selectByIds([feature.id()])
                    self.pointFound.emit(feature, crs)