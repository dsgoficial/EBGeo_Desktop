from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from math import *
import os

class AreaRange(QObject):

    def __init__(self, iface):
        QObject.__init__(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.initVariables()
        self.initSignals()

    # Definir caminho de imagem e texto auxiliar.
    def initGui(self):
        iconPath = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons', 'arearange.png')
        self.enableAction = QAction(QIcon(iconPath), u"Ativar geração de área de alcance de armamento", self.iface.mainWindow())
        self.enableAction.setCheckable(True)
        self.toolbar = self.iface.addToolBar(u'Alcance do Armamento')
        self.toolbar.addAction(self.enableAction)
        self.enableAction.changed.connect(self.maptoolChanged)

    def unload(self):
        self.toolbar.removeAction(self.enableAction)
        del self.toolbar

    def maptoolChanged(self):
        if self.enableAction.isChecked():
            self.canvas.setMapTool(self.myTool)
        else:
            self.canvas.unsetMapTool(self.myTool)

    def initVariables(self):
        self.myTool = QgsMapToolEmitPoint(self.canvas)
        self.currentTool = self.canvas.mapTool()
        self.clickedPoint = ''

    def initSignals(self):
        self.myTool.canvasClicked.connect(self.doWork)

    # Criar camada vetorial do tipo polígono com as informações de Alcance, Azimute e Abertura.
    def createlayer(self, worklayer):
        output_layer = QgsVectorLayer("Polygon?crs={}".format(worklayer.crs().authid()), "Alcance do Armamento", "memory")
        dtprovider = output_layer.dataProvider()
        QgsProject.instance().addMapLayer(output_layer)
        dtprovider.addAttributes([QgsField("Alcance", QVariant.Double),
        QgsField("Azimute", QVariant.Double),
        QgsField("Abertura", QVariant.Double)])
        output_layer.updateFields()
        return output_layer, dtprovider
    
    # Coletar informações do usuário, para clique com o botão esquerdo do mouse e preenchimento das informações por ponto.
    def getInput(self):
            qid = QInputDialog()
            dist_check = True
            ang_check = True
            ang_op_check = True
            while dist_check:
                inp_dist = QInputDialog.getText(qid, "Digite o alcance", "Alcance (em unidades do mapa): ", QLineEdit.Normal)[0]
                if not inp_dist:
                    return
                try:
                    dist = float(inp_dist.replace(",", "."))
                    dist_check = False
                except:
                    QMessageBox.critical(None , u"Erro", u"Entre um valor numérico para a distância.")
            while ang_check:
                inp_ang = QInputDialog.getText(qid, "Digite o azimute de disparo", "Azimute (GG.MM.SS,SSS, GG.MM.SS ou Decimal): ", QLineEdit.Normal)[0]
                if not inp_ang:
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
            while ang_op_check:
                inp_op_ang = QInputDialog.getText(qid, "Digite o ângulo de abertura", "Ângulo de abertura (GG.MM.SS,SSS, GG.MM.SS ou Decimal): ", QLineEdit.Normal)[0]
                if not inp_op_ang:
                    return
                if len(inp_op_ang.split(".")) == 3:
                    try:
                        ang_op = float(inp_op_ang.split(".")[0]) + float(inp_op_ang.split(".")[1])/60 + float(inp_op_ang.split(".")[2].replace(",", "."))/3600
                        ang_op_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o ângulo de abertura.")
                else:
                    try:
                        ang_op = float(inp_op_ang.replace(",", "."))
                        ang_op_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o ângulo de abertura.")
            return dist, ang, ang_op

    # Coletar informações do usuário, para clique com o botão direito do mouse e preenchimento do nome da camada com a tabela de alcances.
    def getInputRightButton(self):
        qid = QInputDialog()
        name_check = True
        while name_check:
            input_name = QInputDialog.getText(qid, "Selecione a Camada", "Digite o nome da Camada de Pontos contendo os campos 'Alcance', 'Azimute' e 'Abertura'", QLineEdit.Normal)[0]
            if not input_name:
                return 
            layerlist = self.iface.mapCanvas().layers()
            for layer in layerlist:
                if layer.name() == input_name:
                    name_check = False
                    activeLayer = layer
                    worklayer = activeLayer
                    output_layer, dtprovider = self.createlayer(worklayer)
        return output_layer, dtprovider, activeLayer

    # Coletar as informações da layer de pontos selecionada pelo usuário caso clique com o botão esquerdo do mouse.
    def getLayerFeature(self, point):
        if self.canvas.mapSettings().destinationCrs().isGeographic():
            d = 2 * pow(10, -8) * self.canvas.scale()
        else:
            d = 0.002 * self.canvas.scale()
        bufferRect = QgsRectangle(point.x() - d, point.y() - d, point.x() + d, point.y() + d)
        layerlist = self.iface.mapCanvas().layers()
        for layer in layerlist:
            if layer.type() == QgsMapLayer.RasterLayer:
                QMessageBox.information(None, u"Aviso", u"Selecione uma camada vetorial de pontos.")
                continue
            if layer.geometryType() == 0:
                for feature in layer.getFeatures():
                    transf = QgsCoordinateTransform(layer.crs(), self.canvas.mapSettings().destinationCrs(), QgsProject.instance())
                    if feature.geometry().isMultipart():
                        workgeom = feature.geometry().coerceToType(1)[0].asPoint()
                    else:
                        workgeom = feature.geometry().asPoint()
                    geom = QgsPoint(workgeom)
                    geom.transform(transf)
                    geom = QgsGeometry.fromPointXY(QgsPointXY(geom))
                    if geom.intersects(bufferRect):
                        return layer, workgeom
            else:
                continue

    # Gerar área de alcance do armamento.
    def generateArea(self, point:QgsPointXY, dist, azimuth, op_angle):
        if op_angle>=360:
            p = QgsGeometry.fromPointXY(point)
            return p.buffer(dist, 90)
        divisions = 10+int(op_angle)+int(op_angle%2)
        points = []
        points.append(point)
        for i in reversed(range(1, int(divisions/2+1))):
            alpha = 360+azimuth-i*op_angle/divisions
            xneg = point.x()+dist*(sin(radians(alpha)))
            yneg = point.y()+dist*(cos(radians(alpha)))
            pneg = QgsPointXY(xneg, yneg)
            points.append(pneg)
        for i in range(0, int(divisions/2)+1):
            alpha = azimuth+i*op_angle/divisions
            xpos = point.x()+dist*(sin(radians(alpha)))
            ypos = point.y()+dist*(cos(radians(alpha)))
            ppos = QgsPointXY(xpos, ypos)
            points.append(ppos)
        points.append(point)
        poly = QgsGeometry.fromPolygonXY([points])
        return poly

    # Realiza ações de gerenciamento do clique do mouse.
    def doWork(self, point, button):
        # Caso botão direito clicado:
        if button == QtCore.Qt.RightButton:
            resultInput = self.getInputRightButton()
            if not resultInput:
                return
            output_layer, dtprovider, activeLayer = resultInput
            for feature in activeLayer.getFeatures():
                geo = QgsGeometry.asPoint(feature.geometry())
                point = QgsPointXY(geo)
                alcance, azimute, abertura = feature["Alcance"], feature["Azimute"], feature["Abertura"]
                area_geom = self.generateArea(point, alcance, azimute, abertura)
                output_feature = QgsFeature()
                output_feature.setGeometry(area_geom)
                output_feature.setAttributes([alcance, azimute, abertura])
                dtprovider.addFeatures([output_feature])
            output_layer.updateExtents()
            QMessageBox.information(None , u"Aviso", u"Camada de alcances criada com sucesso.")
            return

        # Caso botão esquerdo clicado:
        if button == QtCore.Qt.LeftButton:
            layerFeat = self.getLayerFeature(point)
            if not layerFeat:
                return
            else:
                worklayer, workgeom = layerFeat

            inputs = self.getInput()
            if not inputs:
                return
            else:
                d, ang, op = inputs

            area_geom = self.generateArea(workgeom, d, ang, op)
            output_layer, dtprovider = self.createlayer(worklayer)
            output_feature = QgsFeature()
            output_feature.setGeometry(area_geom)
            output_feature.setAttributes([d, ang, op])
            dtprovider.addFeatures([output_feature])
            output_layer.updateExtents()
            QMessageBox.information(None , u"Aviso", u"Ponto criado com\n\nAzimute: {} º\n\nDistância: {}\n\nAbertura: {} º".format(ang, d, op))
            return

        else:
            return
