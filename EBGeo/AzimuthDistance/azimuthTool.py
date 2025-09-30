# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
import os
from math import *
import csv
from qgis.PyQt import uic
import re

class AzimuthTool(QObject):

    def __init__(self, iface: QgisInterface):
        QObject.__init__(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.initVariables()
        self.initSignals()

    def initGui(self, az_action):
        self.az_action = az_action
        self.loadUnload(True)

    def unload(self):
        self.loadUnload(False)

    def loadUnload(self, ver):
        if ver:
            self.canvas.setMapTool(self.myTool)
            self.canvas.mapToolSet.connect(self.maptoolChanged)
        else:
            self.canvas.unsetMapTool(self.myTool)
            try:
                self.canvas.mapToolSet.disconnect(self.maptoolChanged)
            except TypeError:
                pass
            try:
                self.myTool.canvasClicked.disconnect(self.maptoolChanged)
            except TypeError:
                pass
            self.az_action.setChecked(False)

    def maptoolChanged(self, m1):
        if not bool(m1==self.myTool):
            self.loadUnload(False)

    def initVariables(self):
        self.myTool = QgsMapToolEmitPoint(self.canvas)
        self.currentTool = self.canvas.mapTool()
        self.clickedPoint = ''

    def initSignals(self):
        self.myTool.canvasClicked.connect(self.doWork)

    def getInput(self):
            qid = QInputDialog()
            dist_check = True
            ang_check = True
            while dist_check:
                inp_dist = QInputDialog.getText(qid, "Digite a distância", "Distância (unidades da camada): ", QLineEdit.Normal)[0]
                if not inp_dist:
                    self.calculating = False
                    return
                try:
                    dist = float(inp_dist.replace(",", "."))
                    dist_check = False
                except:
                    QMessageBox.critical(None , u"Erro", u"Entre um valor numérico para a distância.")
            while ang_check:
                inp_ang = QInputDialog.getText(qid, "Digite o azimute", "Azimute (GG.MM.SS ou Decimal): ", QLineEdit.Normal)[0]
                if not inp_ang:
                    self.calculating = False
                    return
                if len(inp_ang.split(".")) == 3:
                    try:
                        ang = float(inp_ang.split(".")[0]) + float(inp_ang.split(".")[1])/60 + float(inp_ang.split(".")[2].replace(",", "."))/3600
                        ang_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o azimute.")
                else:
                    try:
                        ang = float(inp_ang.replace(",", "."))
                        ang_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o azimute.")
            return dist, ang

    def getLayerFeature(self, point):
        if self.canvas.mapSettings().destinationCrs().isGeographic():
            d = 2 * pow(10,-8) * self.canvas.scale()
        else:
            d = 0.002 * self.canvas.scale()
        bufferRect = QgsRectangle(point.x() - d, point.y() - d, point.x() + d, point.y() + d)
        layerlist = self.iface.mapCanvas().layers()
        for layer in layerlist:
            if not isinstance(layer, QgsVectorLayer):
                continue
            if layer.geometryType() == 0:
                for feature in layer.getFeatures():
                    transf = QgsCoordinateTransform(layer.crs(), self.canvas.mapSettings().destinationCrs(), QgsProject.instance())
                    workgeom = self.getWorkgeom(feature)
                    geom = QgsPoint(workgeom)
                    geom.transform(transf)
                    geom = QgsGeometry.fromPointXY(QgsPointXY(geom))
                    if geom.intersects(bufferRect):
                        return layer, workgeom
            else:
                continue
    def getFile(self):
        qfd = QFileDialog()
        result = self.showDialog()
        if not result:
            return
        inp_csv,_ = QFileDialog.getOpenFileName(qfd, "Selecione o arquivo csv", filter="*.csv")
        return inp_csv
    
    def workOnCsv(self, worklayer, workgeom):
        nP = 0
        with open(self.csvpath, 'r') as file:
            csv_reader = csv.reader(file, delimiter=self.delimiter)
            for rowNumber, row in enumerate(csv_reader):
                if len(row)<2:
                    continue
                if rowNumber ==0:
                    angId = row.index(self.azimColumn)
                    dId = row.index(self.distColumn)
                ang = row[angId]
                d = row[dId]
                if re.search(r'[a-zA-Z]', ang) or re.search(r'[a-zA-Z]', d):
                    continue
                if ',' in ang:
                    ang = ang.replace(',', '.')
                if ',' in d:
                    d = d.replace(',', '.')
                ang=float(ang)
                d=float(d)
                feat_new = self.calcNewFeat(worklayer, workgeom, d, ang)
                workgeom = feat_new.geometry().asPoint()
                nP+=1
        return nP

    def getWorkgeom(self, feature):
        if feature.geometry().isMultipart():
            workgeom = feature.geometry().coerceToType(1)[0].asPoint()
        else:
            workgeom = feature.geometry().asPoint()
        return workgeom

    def doWork(self, point, button):
        if button == QtCore.Qt.LeftButton:
            layerFeat = self.getLayerFeature(point)
            if not layerFeat:
                QMessageBox.warning(None, "Aviso", "Clique em uma geometria de ponto existente.")
                return
            else:
                worklayer, workgeom = layerFeat
            inputs = self.getInput()
            if not inputs:
                return
            else:
                d, ang = inputs
            self.calcNewFeat(worklayer, workgeom, d, ang)
            worklayer.triggerRepaint()
            QMessageBox.information(None , u"Aviso", u"Ponto criado com\n\nAzimute: {} º\n\nDistância: {}".format(ang, d))
            return
        elif button == QtCore.Qt.RightButton:
            
            layerFeat = self.getLayerFeature(point)
            if not layerFeat:
                QMessageBox.warning(None, "Aviso", "Clique em uma geometria de ponto existente.")
                return
            else:
                self.worklayer, self.workgeom = layerFeat
            self.csvpath = False
            self.window = CSVPreviewer()
            self.window.results.connect(self.handleResult)
            self.window.setWindowTitle('CSV Previewer')
            self.window.show()            
        else:
            return
        
    def handleResult(self, result):
        if not result:
            return
        else:
            self.csvpath, self.delimiter, self.azimColumn, self.distColumn = result
        nP = self.workOnCsv(self.worklayer, self.workgeom)
        self.worklayer.triggerRepaint()
        QMessageBox.information(None , u"Aviso", f"{nP} pontos criados")
            
        


    def calcNewFeat(self, worklayer, workgeom, d, ang):
        pt_new = QgsPointXY(workgeom.x() + d * sin(radians(ang)), workgeom.y() + d * cos(radians(ang)))
        fields = worklayer.fields()
        feat_new = QgsFeature(fields)
        feat_new.setGeometry(QgsGeometry.fromPointXY(pt_new))
        worklayer.startEditing()
        worklayer.addFeature(feat_new)
        return feat_new

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'preview_csv.ui'))
class CSVPreviewer(QMainWindow, FORM_CLASS):
    results = pyqtSignal(list)
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Initialize the UI
        self.loadButton.clicked.connect(self.load_csv)
        self.delimiterDict = {
            ",": self.delim_virg_button.isChecked(), 
            ":": self.delim_2p_button.isChecked(), 
            " ": self.delim_esp_button.isChecked(), 
            ";": self.delim_ptovirg_button.isChecked(), 
            "\t": self.delim_tab_button.isChecked(),}
        self.delimiterLine = self.delimitador_group.checkedButton()
        self.csvpath = ""
        self.delimitador_group.buttonToggled.connect(self.update_preview)
        self.cancelButton.pressed.connect(self.close)
        self.okButton.pressed.connect(self.returnValues)

    def load_csv(self):
        qfd = QFileDialog()
        self.csvpath, _ = QFileDialog.getOpenFileName(qfd, "Selecione o arquivo csv", filter="*.csv")
        if not os.path.isfile(self.csvpath):
            self.okButton.setEnabled(False)
        else:
            self.okButton.setEnabled(True)
        self.filepath.setText(self.csvpath)
        self.update_preview()

    def update_preview(self):
        self.previewTable.clear()
        self.previewTable.setRowCount(0)
        self.previewTable.setColumnCount(0)
        self.azimuteComboBox.clear()
        self.distanciaComboBox.clear()
        if not os.path.isfile(self.csvpath):
            return
        
        self.delimiterDict = {
            ",": self.delim_virg_button.isChecked(), 
            ":": self.delim_2p_button.isChecked(), 
            " ": self.delim_esp_button.isChecked(), 
            ";": self.delim_ptovirg_button.isChecked(), 
            "\t": self.delim_tab_button.isChecked(),}
        for key, value in self.delimiterDict.items():
            if value==1:
                self.delimiterLine=key
                break
        with open(self.csvpath, 'r') as file:
            csv_reader = csv.reader(file, delimiter=str(self.delimiterLine))
            for rowNumber, row in enumerate(csv_reader):
                self.previewTable.insertRow(rowNumber)
                if rowNumber==0:
                    self.azimuteComboBox.addItems(row)
                    self.distanciaComboBox.addItems(row)
                for colNumber, itemValue in enumerate(row):
                    if rowNumber==0:
                        self.previewTable.insertColumn(colNumber)
                    item = QTableWidgetItem(itemValue)
                    self.previewTable.setItem(rowNumber, colNumber, item)
    def returnValues(self):
        self.delimiterDict = {
            ",": self.delim_virg_button.isChecked(), 
            ":": self.delim_2p_button.isChecked(), 
            " ": self.delim_esp_button.isChecked(), 
            ";": self.delim_ptovirg_button.isChecked(), 
            "\t": self.delim_tab_button.isChecked(),}
        for key, value in self.delimiterDict.items():
            if value==1:
                self.delimiterLine=key
                break
        self.results.emit([self.csvpath, self.delimiterLine, self.azimuteComboBox.currentText(), self.distanciaComboBox.currentText()])
        self.close()
