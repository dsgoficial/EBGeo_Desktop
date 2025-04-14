# -*- coding: utf-8 -*-
from qgis.core import (
    QgsMapLayer, 
    QgsDistanceArea,
    QgsCoordinateTransformContext,
    QgsUnitTypes,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsCoordinateTransform,
    QgsVectorFileWriter,
    QgsGeometry,
    QgsVectorLayer,
    QgsFeature,
    QgsWkbTypes,
    QgsField,
    QgsPointXY,
)
from qgis.gui import QgsMapToolIdentifyFeature, QgsMapToolIdentify
from qgis.PyQt import uic, QtWidgets, QtCore
from qgis.PyQt.QtWidgets import QFileDialog, QTreeWidgetItem, QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
from qgis.PyQt.QtCore import QVariant, pyqtSignal, Qt, QEvent
import os
from math import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'azimuthGenerator_dockwidget_base.ui'))

BOX_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'fontSizeBox.ui'))

class FontSizeDialog(QDialog, BOX_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.spinBox.valueChanged.connect(self.updateValidation)
        self.updateValidation()

    def updateValidation(self):
        
        current_value = int(self.spinBox.value())
        if 6 <= current_value <= 96:
            self.error.setVisible(False)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.error.setVisible(True)
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
    
    def getFontSize(self):
        return self.spinBox.value()

class Main(QtWidgets.QDockWidget, FORM_CLASS):

    closingDock = pyqtSignal()

    def __init__(self, iface):
        super(Main, self).__init__()
        '''Constructor'''
        self.setupUi(self)
        self.iface = iface
        self.isOpen = False
        self.vertices = None

    def initGui(self):
        self.initVariables()
        self.initSignals()
        self.openWindow()
        self.isOpen = True
        self.displayXYCheckBox = self.findChild(QtWidgets.QCheckBox, "displayXYCheckBox")

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
        self.htmlButton.clicked.connect(self.exportHtml)
        self.gpxButton.clicked.connect(self.exportGpx)
        self.displayXYCheckBox.toggled.connect(self.updateColumnVisibility)

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
    
    def updateColumnVisibility(self):
        is_checked = self.displayXYCheckBox.isChecked()
        self.mapList.setColumnHidden(1, not is_checked)
        self.mapList.setColumnHidden(2, not is_checked)

    def doWork(self, pointList):
        self.mapList.clear()
        item = []
        for i in range (0, len(pointList)-1):
            dist = pointList[i].distance(pointList[i + 1])
            if dist == 0:
                continue
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
        self.vertices = pointList

    def exportCsv(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar arquivo de saída", "", u"Arquivo CSV (*.csv)")[0]
        
        if filePath != "" and filePath[-4:].lower() != ".csv":
            filePath += ".csv"
        
        if filePath != "":
            csvFile = open(filePath, 'w')
        else:
            return
        
        if self.displayXYCheckBox.isChecked():
            csvFile.write(u'Ponto;X;Y;Azimute;Distancia;Destino\n')
            for i in range(0, self.mapList.topLevelItemCount()):
                csvFile.write(u'{};{};{};{};{};{}\n'.format(
                    self.mapList.topLevelItem(i).data(0, 0),
                    self.mapList.topLevelItem(i).data(1, 0),
                    self.mapList.topLevelItem(i).data(2, 0),
                    self.mapList.topLevelItem(i).data(3, 0),
                    self.mapList.topLevelItem(i).data(4, 0),
                    self.mapList.topLevelItem(i).data(5, 0)))
        else:
            csvFile.write(u'Ponto;Azimute;Distancia;Destino\n')
            for i in range(0, self.mapList.topLevelItemCount()):
                csvFile.write(u'{};{};{};{}\n'.format(
                    self.mapList.topLevelItem(i).data(0, 0),
                    self.mapList.topLevelItem(i).data(3, 0),
                    self.mapList.topLevelItem(i).data(4, 0),
                    self.mapList.topLevelItem(i).data(5, 0)))
        
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
        
        if self.displayXYCheckBox.isChecked():
            txtFile.write(u'Ponto;X;Y;Azimute;Distancia;Destino\n')
            for i in range(0, self.mapList.topLevelItemCount()):
                txtFile.write(u'{};{};{};{};{};{}\n'.format(
                    self.mapList.topLevelItem(i).data(0, 0),
                    self.mapList.topLevelItem(i).data(1, 0),
                    self.mapList.topLevelItem(i).data(2, 0),
                    self.mapList.topLevelItem(i).data(3, 0),
                    self.mapList.topLevelItem(i).data(4, 0),
                    self.mapList.topLevelItem(i).data(5, 0)))
        else:
            txtFile.write(u'Ponto;Azimute;Distancia;Destino\n')
            for i in range(0, self.mapList.topLevelItemCount()):
                txtFile.write(u'{};{};{};{}\n'.format(
                    self.mapList.topLevelItem(i).data(0, 0),
                    self.mapList.topLevelItem(i).data(3, 0),
                    self.mapList.topLevelItem(i).data(4, 0),
                    self.mapList.topLevelItem(i).data(5, 0)))
        
        txtFile.close()

    def exportHtml(self):
        fontSizeDlg = FontSizeDialog(self)
        if fontSizeDlg.exec_() == QDialog.Accepted:
            fontSize = fontSizeDlg.getFontSize()
        else:
            return
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecionar arquivo de saída", "", u"Arquivo HTML (*.html)")[0]
        
        if filePath != "" and filePath[-4:].lower() != ".html":
            filePath += ".html"
        
        if filePath != "":
            htmlFile = open(filePath, 'w')
        else:
            return

        htmlFile.write(u'<html>\n<head>\n<title>Dados Azimute Distancia</title>\n')
        htmlFile.write(u'<style>\n')
        htmlFile.write(f'th, td {{ font-size: {fontSize}px; }}\n')
        htmlFile.write(u'</style>\n')
        htmlFile.write(u'</head>\n<body>\n')
        htmlFile.write(u'<table border="1" cellspacing="0" cellpadding="5">\n')

        if self.displayXYCheckBox.isChecked():
            htmlFile.write(u'<tr><th>Ponto</th><th>X</th><th>Y</th><th>Azimute</th><th>Distancia</th><th>Destino</th></tr>\n')
            for i in range(self.mapList.topLevelItemCount()):
                htmlFile.write(u'<tr>')
                for j in range(6):
                    data = self.mapList.topLevelItem(i).data(j, 0)
                    htmlFile.write(u'<td>{}</td>'.format(data if data is not None else ''))
                htmlFile.write(u'</tr>\n')
        else:
            htmlFile.write(u'<tr><th>Ponto</th><th>Azimute</th><th>Distancia</th><th>Destino</th></tr>\n')
            for i in range(self.mapList.topLevelItemCount()):
                htmlFile.write(u'<tr>')
                for j in [0, 3, 4, 5]:
                    data = self.mapList.topLevelItem(i).data(j, 0)
                    htmlFile.write(u'<td>{}</td>'.format(data if data is not None else ''))
                htmlFile.write(u'</tr>\n')
        
        htmlFile.write(u'</table>\n</body>\n</html>')
        htmlFile.close()
    
    def exportGpx(self):
        fileDlg = QFileDialog()
        filePath = fileDlg.getSaveFileName(None, u"Selecione arquivo de saída", "", u"Arquivo GPX (*.gpx)")[0]

        if filePath != "" and filePath[-4:].lower() != ".gpx":
            filePath += ".gpx"
        
        if not filePath:
            return
        
        if filePath != "":
            gpxFile = open(filePath, 'w')
        
        gpxFile.write(u'<?xml version="1.0"?>\n<gpx version="1.1" creator="GDAL 3.10.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ogr="http://osgeo.org/gdal" xmlns="http://www.topografix.com/GPX/1/1" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">\n')
        gpxFile.write(u'<metadata>\n')

        crs = QgsProject.instance().crs()
        crsWgs84 = QgsCoordinateReferenceSystem('EPSG:4326')

        transform = QgsCoordinateTransform(crs, crsWgs84, QgsProject.instance().transformContext())

        dictPoints = dict()
        minlat, maxlat, minlon, maxlon = (9999, -9999, 9999, -9999)

        for i in range(0, self.mapList.topLevelItemCount()):
            pointName = self.mapList.topLevelItem(i).data(0, 0)
            azimute = self.mapList.topLevelItem(i).data(3, 0)
            distance = self.mapList.topLevelItem(i).data(4, 0)
            destino = self.mapList.topLevelItem(i).data(5, 0)
            featVertice = self.vertices[i]
            geomTrans = transform.transform(QgsPointXY(featVertice.x(), featVertice.y()))

            lat = geomTrans.y()
            lon = geomTrans.x()

            if lat < minlat:
                minlat = lat
            elif lat > maxlat:
                maxlat = lat
            elif lon < minlon:
                minlon = lon
            elif lon > maxlon:
                maxlon = lon
        
            if self.displayXYCheckBox.isChecked():
                dictPoints[i] = [lat, lon, pointName, str(featVertice.x()), str(featVertice.y()), azimute, distance, destino]
            else:
                dictPoints[i] = [lat, lon, pointName, azimute, distance, destino]
    
        gpxFile.write(f'<bounds minlat="{minlat}" minlon="{minlon}" maxlat="{maxlat}" maxlon="{maxlon}"/>\n')
        gpxFile.write(u'</metadata>\n')

        for i, infoPoint in dictPoints.items():
            gpxFile.write(f'<wpt lat="{infoPoint[0]}" lon="{infoPoint[1]}">\n')
            gpxFile.write(f'<name>{infoPoint[2]}</name>\n')
            gpxFile.write(u'<cmt>')
            if self.displayXYCheckBox.isChecked():
                gpxFile.write(f'Coord X: {infoPoint[3]}\n')
                gpxFile.write(f'Coord Y: {infoPoint[4]}\n')
                gpxFile.write(f'Azimute: {infoPoint[5]}\n')
                gpxFile.write(f'Distancia: {infoPoint[6]}\n')
                gpxFile.write(f'Ponto de Destino: {infoPoint[7]}\n')
            else:
                gpxFile.write(f'Azimute: {infoPoint[3]}\n')
                gpxFile.write(f'Distancia: {infoPoint[4]}\n')
                gpxFile.write(f'Ponto de Destino: {infoPoint[5]}')
            gpxFile.write(u'</cmt>\n')
            gpxFile.write(u'</wpt>\n')
        
        gpxFile.close()      

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
