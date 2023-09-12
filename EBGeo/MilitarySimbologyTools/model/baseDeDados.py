#! -*- coding: UTF-8 -*-
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtSql import QSqlDatabase
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject, QgsProjectBadLayerHandler
from qgis.utils import iface
import os, re
from osgeo import ogr, gdal

class BaseDeDados(QObject):
    def __init__(self):
        super(BaseDeDados, self).__init__()
        self.initVariables()

    def initVariables(self):
        self.listName = {
                    'coord_ap_fogo': u'Coordenação de Apoio de Fogo',
                    'eixo_de_direcao': u'Eixo de direcao',
                    'fortificacoes_pf': u'Fortificações - Pontos Fortes',
                    'limite_entre_fracoes_direito': u'Limite entre frações - texto direito',
                    'limite_entre_fracoes_esquerdo': u'Limite entre frações - texto esquerdo',
                    'linha_de_controle': u'Linha de controle',
                    'seta_situacao': u'Seta de situação',
                    'simbolos_pontos': u'Símbolos (pontos)',
                   }
        self.Database = None

    def checkTableFromDatabase(self, tablename):
        allTables = [l.GetName() for l in ogr.Open(self.Database)]
        if tablename in allTables:
            layer = QgsVectorLayer(self.Database + "|layername=" + tablename, '', 'ogr')
            attrList = []
            for i in layer.getFeatures():
                attrList.append(i[0])
        else:
            attrList = ['table not available']
        return attrList

    def setCurrentDatabase(self, pathDatabase):
        pathDatabase.replace('\\','/')
        self.Database =  pathDatabase

    def getDataBaseLayerName(self):
        listOfNames = [l.GetName() for l in ogr.Open(self.Database)]
        return listOfNames

    def getTemplateDatabase(self):
        path  = os.path.join(os.path.dirname(__file__), 'templates', 'dataBase.gpkg')
        return path

    def createDataBase(self, path):
        f = open(self.getTemplateDatabase(),'rb')
        g = open(path,'wb')
        x = f.readline()
        while x:
            g.write(x)
            x = f.readline()
        g.close()

    def loadDatabase(self):
        projects = self.checkTableFromDatabase('qgis_projects')
        if projects[0] == 'table not available':
            return self.loadSymbLayers()
        else:
            return self.loadProject()

    def loadSymbLayers(self):
        fileNameFull = self.Database
        fileName = fileNameFull.split('/')[-1].split('.')[0]
        root = QgsProject.instance().layerTreeRoot()
        self.groupMain = root.insertGroup(0, fileName)
        symbolGroupO = self.groupMain.insertGroup(2, 'OUTRAS CAMADAS')
        for name in self.getDataBaseLayerName():
            if name == 'limite_entre_fracoes':
                workname = ['limite_entre_fracoes_esquerdo','limite_entre_fracoes_direito']
            else:
                workname = [name]
            for i in workname:
                if i in self.listName:
                    layer = QgsVectorLayer(self.Database + "|layername=" + name, self.listName[i], 'ogr')
                    QgsProject.instance().addMapLayer(layer, False)
                    if i == 'limite_entre_fracoes_esquerdo':
                        for labels in layer.labeling().rootRule().children():
                            if 'direita' in labels.description():
                                labels.setActive(False)
                    elif i == 'limite_entre_fracoes_direito':
                        for labels in layer.labeling().rootRule().children():
                            if 'esquerda' in labels.description():
                                labels.setActive(False)
                    self.groupMain.addLayer(layer)
                elif i not in ['metadata', 'layer_styles']:
                    layer = QgsVectorLayer(self.Database + "|layername=" + i, i, 'ogr')
                    QgsProject.instance().addMapLayer(layer, False)
                    symbolGroupO.addLayer(layer)
        self.loadRasterLayers()
        self.groupMain.removeChildrenGroupWithoutLayers()
        iface.mapCanvas().refresh()
        return 1

    def loadRasterLayers(self):
        symbolGroupR = self.groupMain.insertGroup(3, 'CAMADAS RASTER')
        raster_info=gdal.Info(self.Database)
        if not not raster_info:
            raster_layers = re.findall("GPKG:.*", raster_info)
            if not raster_layers:
                raster_layers = re.findall("IDENTIFIER=.*", raster_info)
                raster_layer = raster_layers[0].replace('IDENTIFIER=','')
                layer = QgsRasterLayer("GPKG:" + self.Database + ":" + raster_layer, raster_layer, 'gdal')
                QgsProject.instance().addMapLayer(layer, False)
                symbolGroupR.addLayer(layer)
            else:
                for raster in raster_layers:
                    layer = QgsRasterLayer(raster, raster[raster.rfind(':')+1:], 'gdal')
                    QgsProject.instance().addMapLayer(layer, False)
                    symbolGroupR.addLayer(layer)

    def loadProject(self):
        file_path = self.Database.replace('\\','/')
        gpkgname=file_path.split('/')[-1]

        projectList = self.checkTableFromDatabase('qgis_projects')
        projectName = projectList[0]

        tempProject=QgsProject.instance()
        tempProject.setBadLayerHandler(QgsProjectBadLayerHandler())
        tempProject.read('geopackage:' + file_path + '?projectName=' + projectName)

        layersList=QgsProject.instance().mapLayers()
        for i in layersList:
            layer = QgsProject.instance().mapLayer(i)
            layerPath = layer.dataProvider().dataSourceUri()
            if gpkgname in layerPath:
                if layer.providerType() == 'gdal':
                    if layerPath.endswith('.gpkg'):
                        newPath = file_path
                    else:
                        newPath = layerPath.replace(layerPath[:layerPath.rfind(':')], 'GPKG:' + file_path)
                else:
                    newPath = layerPath.replace(layerPath[:layerPath.find('|')],file_path)
                layer.dataProvider().setDataSourceUri(newPath)
                layer.setDataSource(newPath, layer.name(), layer.providerType(), layer.dataProvider().ProviderOptions())

        QgsProject.instance().write('geopackage:' + file_path + '?projectName=' + projectName)
        return 2
