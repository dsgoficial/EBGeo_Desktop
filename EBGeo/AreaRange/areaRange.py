from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from math import *
import os

class AreaRange(QObject):

    def __init__(self, iface: QgisInterface):
        QObject.__init__(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.initVariables()
        self.initSignals()
        self.firstAreaRangeLayerCrs = None

    # Definir caminho de imagem e texto auxiliar.
    def initGui(self, ar_action):
        self.ar_action = ar_action
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
            self.ar_action.setChecked(False)

    def maptoolChanged(self, m1):
        if not bool(m1 == self.myTool):
            self.loadUnload(False)

    def initVariables(self):
        self.myTool = QgsMapToolEmitPoint(self.canvas)
        self.currentTool = self.canvas.mapTool()
        self.clickedPoint = ''

    def initSignals(self):
        self.myTool.canvasClicked.connect(self.doWork)

    # Criar camada vetorial do tipo polígono com as informações de Alcance, Azimute e Abertura.
    def createlayer(self, worklayer):
        fields = worklayer.fields()
        existingLayers = QgsProject.instance().mapLayersByName("Alcance do Armamento")
        if existingLayers:
            output_layer = existingLayers[0]
            self.firstAreaRangeLayerCrs = output_layer.crs()
            dtprovider = output_layer.dataProvider()
            existing_field_names = [f.name() for f in output_layer.fields()]
            new_fields = []
            #Garantir que sempre existam esses parâmetros
            fixed_fields = [
                QgsField("Alcance", QVariant.Double),
                QgsField("Azimute", QVariant.Double),
                QgsField("Abertura", QVariant.Double)
            ]
            for f in fixed_fields + [f for f in fields]:
                if f.name() not in existing_field_names:
                    new_fields.append(f)
            if new_fields:
                dtprovider.addAttributes(new_fields)
                output_layer.updateFields()
            return output_layer, dtprovider
        output_layer = QgsVectorLayer("Polygon?crs={}".format(worklayer.crs().authid()), "Alcance do Armamento", "memory")
        self.firstAreaRangeLayerCrs = output_layer.crs()
        dtprovider = output_layer.dataProvider()
        QgsProject.instance().addMapLayer(output_layer)
        dtprovider.addAttributes([QgsField("Alcance", QVariant.Double),
        QgsField("Azimute", QVariant.Double),
        QgsField("Abertura", QVariant.Double)] + [f for f in fields])
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
                inp_ang = QInputDialog.getText(qid, "Digite o azimute de disparo", "Azimute (GG.MM.SS ou Decimal): ", QLineEdit.Normal)[0]
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
                inp_op_ang = QInputDialog.getText(qid, "Digite o ângulo de abertura", "Ângulo de abertura (GG.MM.SS ou Decimal): ", QLineEdit.Normal)[0]
                if not inp_op_ang:
                    return
                if len(inp_op_ang.split(".")) == 3:
                    try:
                        ang_op = float(inp_op_ang.split(".")[0]) + float(inp_op_ang.split(".")[1])/60 + float(inp_op_ang.split(".")[2].replace(",", "."))/3600
                        if ang_op < 0:
                            QMessageBox.warning(None, "Aviso", "O ângulo de abertura não pode ser negativo.")
                            continue
                        ang_op_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o ângulo de abertura.")
                else:
                    try:
                        ang_op = float(inp_op_ang.replace(",", "."))
                        if ang_op < 0:
                            QMessageBox.warning(None, "Aviso", "O ângulo de abertura não pode ser negativo.")
                            continue
                        ang_op_check = False
                    except:
                        QMessageBox.critical(None , u"Erro", u"Entre um formato válido para o ângulo de abertura.")
            return dist, ang, ang_op

    # Coletar informações do usuário, para clique com o botão direito do mouse e preenchimento do nome da camada com a tabela de alcances.
    def getInputRightButton(self):
        qid = QInputDialog()
        name_check = True
        same_crs = True
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
                if activeLayer.crs().isGeographic() != self.canvas.mapSettings().destinationCrs().isGeographic():
                    same_crs = False
        if not same_crs:
            QMessageBox.warning(None, "Aviso",
                    "A camada selecionada tem sistema de coordenadas diferente do mapa (graus x metros).")    
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
                    same_crs = True
                    transf = QgsCoordinateTransform(layer.crs(), self.canvas.mapSettings().destinationCrs(), QgsProject.instance())
                    if layer.crs().isGeographic() != self.canvas.mapSettings().destinationCrs().isGeographic():
                        same_crs = False
                    if feature.geometry().isMultipart():
                        workgeom = feature.geometry().coerceToType(QgsWkbTypes.Point)[0].asPoint()
                    else:
                        workgeom = feature.geometry().asPoint()
                    geom = QgsPoint(workgeom)
                    geom.transform(transf)
                    geom = QgsGeometry.fromPointXY(QgsPointXY(geom))
                    if geom.intersects(bufferRect):
                        if not same_crs:
                            QMessageBox.warning(None, "Aviso", 
                        "A camada selecionada tem sistema de coordenadas diferente do mapa (graus x metros)." )
                        return layer, workgeom, feature
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
                values = []
                for field in output_layer.fields():
                    fname = field.name()
                    if fname == "Alcance":
                        values.append(alcance)
                    elif fname == "Azimute":
                        values.append(azimute)
                    elif fname == "Abertura":
                        values.append(abertura)
                    elif fname in activeLayer.fields().names():  
                        values.append(feature[fname])        
                    else:
                        values.append(None)
                output_feature.setAttributes(values)
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
                worklayer, workgeom, workfeat = layerFeat

            inputs = self.getInput()
            if not inputs:
                return
            else:
                d, ang, op = inputs

            area_geom = self.generateArea(workgeom, d, ang, op)
            if self.firstAreaRangeLayerCrs != None:
                transf = QgsCoordinateTransform(worklayer.crs(), self.firstAreaRangeLayerCrs, QgsProject.instance())
                area_geom.transform(transf)
            output_layer, dtprovider = self.createlayer(worklayer)
            output_feature = QgsFeature()
            output_feature.setGeometry(area_geom)
            values = []
            for field in output_layer.fields():
                fname = field.name()
                if fname == "Alcance":
                     values.append(d)
                elif fname == "Azimute":
                    values.append(ang)
                elif fname == "Abertura":
                    values.append(op)
                elif fname in worklayer.fields().names():  
                    values.append(workfeat[fname])        
                else:
                    values.append(None)
            output_feature.setAttributes(values)
            dtprovider.addFeatures([output_feature])
            output_layer.updateExtents()
            QMessageBox.information(None , u"Aviso", u"Ponto criado com\n\nAzimute: {} º\n\nDistância: {}\n\nAbertura: {} º".format(ang, d, op))
            return

        else:
            return
