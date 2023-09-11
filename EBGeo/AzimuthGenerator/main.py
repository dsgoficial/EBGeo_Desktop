# -*- coding: utf-8 -*-
from qgis.core import (
    QgsCoordinateTransform, 
    QgsVectorLayer, 
    QgsGeometry, 
    QgsProject, 
    QgsRectangle, 
    QgsGeometry, 
    QgsMapLayer, 
    QgsWkbTypes, 
    QgsPointXY,
    QgsDistanceArea,
    QgsCoordinateTransformContext,
    QgsUnitTypes,
    QgsCoordinateReferenceSystem,
)
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker, QgsMapToolIdentifyFeature, QgsMapToolIdentify, QgsMapMouseEvent, QgsRubberBand
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QFileDialog, QTreeWidgetItem, QHeaderView
from qgis.PyQt.QtCore import pyqtSignal, Qt
import os
from math import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'azimuthGenerator_dockwidget_base.ui'))


class Main(QtWidgets.QDockWidget, FORM_CLASS):

    closingDock = pyqtSignal()

    def __init__(self, iface):
        super(Main, self).__init__()
        '''Constructor'''
        self.setupUi(self)
        self.iface = iface
        self.isOpen = False

    def initGui(self):
        self.initVariables()
        self.initSignals()
        self.openWindow()
        self.isOpen = True

    def openWindow(self):
        self.iface.addDockWidget(QtCore.Qt.RightDockWidgetArea, self)
        self.isOpen = True

    def closeDock(self, event):
        layers = self.iface.mapCanvas().layers()
        for l in layers:
            if l.type() == QgsMapLayer.VectorLayer:
                l.removeSelection()
        self.closingDock.emit()
        event.accept()
        self.isOpen = False
        self.mapList.clear()
        self.getFromGeometry(False)

    def initVariables(self):
        self.geomlist = []
        self.crs = None
        self.listFeatureId = list()
        self.canvas = self.iface.mapCanvas()
        self.myToolGeom = GeometryMapTool(self.canvas, self.iface)
        self.currentTool = self.canvas.mapTool()

    def initSignals(self):
        self.closeEvent = self.closeDock
        self.pointsButton.clicked.connect(self.getFromGeometry)
        self.myToolGeom.geometrySelected.connect(self.getWorkGeom)
        self.FinishPointsButton.pressed.connect(self.getWorkPoints)
        self.csvButton.clicked.connect(self.exportCsv)
        self.txtButton.clicked.connect(self.exportTxt)

    def getFromGeometry(self, state):
        if state:
            self.mapList.clear()
            self.canvas.setMapTool(self.myToolGeom)
        else:
            self.canvas.unsetMapTool(self.myToolGeom)
            self.pointsButton.setChecked(False)
            self.clearLayersSelections()

    def clearLayersSelections(self):
        layers = self.iface.mapCanvas().layers()
        for l in layers:
            if l.type() == QgsMapLayer.VectorLayer:
                l.removeSelection()

    def generateDMS(self, ang):
        xg = format( modf( ang )[1], '.0f' )
        
        sign = -1 if ang < 0 else 1
        
        xm = format( sign * modf( modf( ang )[0] * 60 )[1], '.0f' )
        xs = format( sign * modf( modf( ang )[0] * 60 )[0] * 60, '.3f' )
        
        gms = str(xg) + u"° " + str(xm) + "' " + str(xs) + '"'
        gms = gms.encode('utf8')
        return gms.decode('utf8')

    def doWork(self, pointList):
        self.mapList.clear()
        item = []
        for i in range (0, len(pointList)-1):
            dist = pointList[i].distance(pointList[i + 1])
            azimuth = degrees(acos((pointList[i + 1].y() - pointList[i].y()) / dist))
            if pointList[i].x() > pointList[i + 1].x():
                azimuth = 360 - azimuth
            if self.metrosButton.isChecked():
                if self.crs.isGeographic():
                    distMetros = QgsDistanceArea()
                    distMetros.setSourceCrs(self.crs, QgsCoordinateTransformContext())
                    dist = distMetros.convertLengthMeasurement(dist, QgsUnitTypes.DistanceMeters)
                    x = distMetros.convertLengthMeasurement(pointList[i].x(), QgsUnitTypes.DistanceMeters)
                    y = distMetros.convertLengthMeasurement(pointList[i].y(), QgsUnitTypes.DistanceMeters)
                else:
                    x = pointList[i].x()
                    y = pointList[i].y()
                dist = round(dist, 3)
            elif self.grausButton.isChecked():
                if not self.crs.isGeographic():
                    distGraus = QgsDistanceArea()
                    distGraus.setSourceCrs(self.crs, QgsCoordinateTransformContext())
                    dist = distGraus.convertLengthMeasurement(dist, QgsUnitTypes.DistanceDegrees)
                    x = distGraus.convertLengthMeasurement(pointList[i].x(), QgsUnitTypes.DistanceDegrees)
                    y = distGraus.convertLengthMeasurement(pointList[i].y(), QgsUnitTypes.DistanceDegrees)
                else:
                    x = pointList[i].x()
                    y = pointList[i].y()
                dist = round(dist, 8)
            
            if self.decimalButton.isChecked():
                azimuth = str(round(azimuth, 5)).replace(".", ",")
            elif self.dmsButton.isChecked():
                azimuth = self.generateDMS(azimuth)
            if i == 0:
                if self.virgulaButton.isChecked():
                    item = QTreeWidgetItem(['P' + str(i + 1), str(round(x, 3)).replace(".", ","), str(round(y, 3)).replace(".", ","), azimuth.replace(".", ","), str(dist).replace(".", ","), 'P' + str(i + 2)])
                elif self.pontoButton.isChecked():
                    item = QTreeWidgetItem(['P' + str(i + 1), str(round(x, 3)), str(round(y, 3)), azimuth, str(dist), 'P' + str(i + 2)])
            else:
                if self.virgulaButton.isChecked():
                    item = QTreeWidgetItem(['P' + str(i + 1), '', '', azimuth.replace(".", ","), str(dist).replace(".", ","), 'P' + str(i + 2)])
                elif self.virgulaButton.isChecked():
                    item = QTreeWidgetItem(['P' + str(i + 1), '', '', azimuth, str(dist), 'P' + str(i + 2)])
            self.mapList.insertTopLevelItem(i, item)

    def getWorkGeom(self, geomandcrs):
        g, featureId, crs = geomandcrs
        self.crs = crs
        if self.pointsButton.isChecked():
            if len(self.listFeatureId) == 0:
                self.analysisGeom(g, featureId)
            elif featureId != self.listFeatureId[-1]:
                self.analysisGeom(g, featureId)
        elif not self.geomlist:
            return

    def analysisGeom(self, g, featureId):
        self.geomlist.append(g)
        self.listFeatureId.append(featureId)
        if self.geomlist[-1].type() in (1,2):
            self.geomlist = []
            self.geomlist.append(g)
        self.canvas.setMapTool(self.myToolGeom)

    def getWorkPoints(self):
        pointList = []
        for geom in self.geomlist:
            for point in geom.vertices():
                pointList.append(point)
        self.geomlist = []
        self.doWork(pointList)
        self.getFromGeometry(False)
        self.listFeatureId= list()

    def exportCsv(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar arquivo de saída", "", u"Arquivo CSV (*.csv)")[0]
        
        if filePath != "" and filePath[-4:].lower() != ".csv":
            filePath += ".csv"
        
        if filePath != "":
            csvFile = open(filePath, 'w')
        else:
            return

        csvFile.write(u'Ponto;X;Y;Azimute;Distancia;Destino\n')

        for i in range(0, self.mapList.topLevelItemCount()):
            csvFile.write(u'{};{};{};{};{};{}\n'.format(self.mapList.topLevelItem(i).data(0, 0), self.mapList.topLevelItem(i).data(1, 0), self.mapList.topLevelItem(i).data(2, 0), self.mapList.topLevelItem(i).data(3, 0), self.mapList.topLevelItem(i).data(4, 0), self.mapList.topLevelItem(i).data(5, 0)))
            
        csvFile.close()
    
    def exportTxt(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar arquivo de saída", "", u"Arquivo TXT (*.txt)")[0]

        if filePath != "" and filePath[-4:].lower() != ".txt":
            filePath += ".txt"
        
        if filePath != "":
            txtFile = open(filePath, 'w')
        else:
            return
        
        txtFile.write(u'Ponto;X;Y;Azimute;Distancia;Destino\n')

        for i in range(0, self.mapList.topLevelItemCount()):
            txtFile.write(u'{};{};{};{};{};{}\n'.format(self.mapList.topLevelItem(i).data(0, 0), self.mapList.topLevelItem(i).data(1, 0), self.mapList.topLevelItem(i).data(2, 0), self.mapList.topLevelItem(i).data(3, 0), self.mapList.topLevelItem(i).data(4, 0), self.mapList.topLevelItem(i).data(5, 0)))

        txtFile.close()

class GeometryMapTool(QgsMapToolIdentifyFeature):

    geometrySelected = pyqtSignal(list)
    crsEmit = pyqtSignal(QgsCoordinateReferenceSystem)

    def __init__(self, canvas, iface):
        self.canvas = canvas
        self.iface = iface
        QgsMapToolIdentifyFeature.__init__(self,self.canvas)

    def canvasReleaseEvent(self, event):
        event.snapPoint()
        found_features = self.identify(event.x(), event.y(), QgsMapToolIdentify.TopDownStopAtFirst, self.VectorLayer)
        if len(found_features) > 0:
            feature = found_features[0].mFeature
            layer = found_features[0].mLayer
            layer.selectByIds([feature.id()])
            geometry = feature.geometry()
            featureId = feature.id()
        else: 
            return

        self.geometrySelected.emit([geometry, featureId, layer.crs()])
