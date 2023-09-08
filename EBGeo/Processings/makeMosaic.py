# -*- coding: utf-8 -*-

from EBGeo.Utils.featureHandler import FeatureHandler
from qgis.PyQt.Qt import QVariant
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProject,
                       QgsVectorLayer,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterVectorLayer,
                       QgsFeatureRequest,
                       QgsField,
                       QgsFields,
                       QgsGeometry,
                       QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem,
                       QgsFeatureSink,
                       QgsProcessingMultiStepFeedback,
                       QgsFeature,
                       QgsSpatialIndex,
                       QgsProcessingParameterRasterDestination,
                       QgsProcessingParameterField
                       )
from qgis import processing

class MakeMosaic(QgsProcessingAlgorithm): 

    INPUT_LAYERS = 'INPUT_LAYERS'
    """INPUT_FRAME = 'INPUT_FRAME'"""
    INPUT_NAME_FIELD = 'INPUT_NAME_FIELD'
    CHECKBOX_MATCH_LAYERS = 'CHECKBOX_MATCH_LAYERS'
    STOP_SCALE = 'STOP_SCALE'
    CHECKBOX_PCT = 'CHECKBOX_PCT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_LAYERS,
                self.tr('Selecionar camadas'),
                QgsProcessing.TypeRaster,
                optional=False
            )
        )

        self.scales = [
            "250k",
            "100k",
            "50k",
            "25k",
        ]

        self.addParameter(
            QgsProcessingParameterEnum(
                self.STOP_SCALE,
                self.tr("Desired scale"),
                options = self.scales,
                defaultValue=0,
            )
        )
        
        self.addParameter(
            QgsProcessingParameterRasterDestination(
                self.OUTPUT,
                self.tr('Mosaico'),
            )
        ) 
        
    def processAlgorithm(self, parameters, context, feedback):      
        feedback.setProgressText('Construindo mosaico...')
        layers = self.parameterAsLayerList(parameters, self.INPUT_LAYERS, context)
        stopScaleIdx = self.parameterAsEnum(parameters, self.STOP_SCALE, context)

        featureHandler = FeatureHandler()
        
        # Scale
        stopScale = self.scales[stopScaleIdx]
        stopScale = int(stopScale.replace("k", ""))

        # Crs raster layer
        crs = layers[1].crs()
        stringCrs = str(crs).split(" ")[1].split(">")[0]
        rasterRange = QgsVectorLayer("Polygon?crs=" + stringCrs, "raster_range", "memory")
        QgsProject.instance().addMapLayer(rasterRange)
        inputFrame = QgsVectorLayer("Polygon?crs=" + stringCrs, "grid_poligono", "memory")
        QgsProject.instance().addMapLayer(inputFrame)
        inputFrame.startEditing()
        
        # x and y of rasters
        coordX = []
        coordY = []
        for raster in layers:
            extentRaster = raster.extent()
            centerRaster = extentRaster.center()
            xRaster = centerRaster.x()
            yRaster = centerRaster.y()
            coordX.append(xRaster)
            coordY.append(yRaster)
        sortedX = sorted(coordX)
        sortedY = sorted(coordY)
        xMin = sortedX[0]
        xMax = sortedX[-1]
        yMin = sortedY[0]
        yMax = sortedY[-1]
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromWkt(f"POLYGON (({xMin} {yMin}, {xMin} {yMax}, {xMax} {yMax}, {xMax} {yMin}, {xMin} {yMin}))"))
        rasterRange.startEditing()
        rasterRange.addFeature(feat, QgsFeatureSink.FastInsert)
        rasterRange.commitChanges()
        crs = rasterRange.crs()
        featureList = []
        coordinateTransformer = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem(crs.geographicCrsAuthId()),
            crs,
            QgsProject.instance(),
        )
        featureHandler.getSystematicGridFeaturesWithConstraint(
            featureList,
            rasterRange,
            stopScale,
            coordinateTransformer,
            xSubdivisions=1,
            ySubdivisions=1,
            feedback=feedback,
        )
        inputFrame.startEditing()
        list(
            map(
                lambda x: inputFrame.addFeature(x, QgsFeatureSink.FastInsert),
                featureList,
            )
        )

        frameGrid = inputFrame
        frameLayer = self.matchLayerAndFrame(inputFrame, layers)
        nameField = 'nome'
        frameGrid = frameLayer
        countGrid = frameGrid.featureCount()

        QgsProject.instance().removeMapLayer(rasterRange.id())
        QgsProject.instance().removeMapLayer(inputFrame.id())
        
        listLayerSize = len(layers)
        listSize = listLayerSize*countGrid+1
        progressStep = 100/listSize if listSize else 0
        
        mergeLayers = []
        i=1
        for feat in frameGrid.getFeatures():
            frameGrid.removeSelection()
            for step,pctLayer in enumerate(layers):
                if feedback.isCanceled():
                        return {self.OUTPUT: 'cancelado'}
                if (feat[nameField] == pctLayer.name()):
                    frameGrid.select(feat.id())
                    frameSelected = frameGrid.materialize(QgsFeatureRequest().setFilterFids(frameGrid.selectedFeatureIds()))
                    if pctLayer.bandCount() == 1:
                        rgbLayer = self.pctToRgb(context, feedback, pctLayer)
                    else:
                        rgbLayer = pctLayer
                    clippedLayer = self.clipLayer(context, feedback, rgbLayer, frameSelected)
                    mergeLayers.append(clippedLayer)
                    frameGrid.removeSelection()
                feedback.setProgress( ((i-1)*listLayerSize+step+1)  * progressStep )
            i+=1
        merged = self.mergeAll(context, parameters, feedback, mergeLayers)
        return{"OUTPUT": merged}
    

    
    def matchLayerAndFrame(self, inputFrame, layers):
        frameLayer = processing.run('EBGeoProvider:matchlayerandframe',
                {
                    'INPUT_LAYERS': layers,
                    'INPUT_FRAME': inputFrame,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })['OUTPUT']
        return frameLayer
        
    
    def pctToRgb(self, context, feedback, inputlayer):
        rgbLayer =processing.run('gdal:pcttorgb', 
                {
                    'INPUT': inputlayer,
                    'BAND': 1,
                    'RGBA': False,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback)['OUTPUT']
        return rgbLayer
    def clipLayer(self, context, feedback, inputlayer, inputGrid):
        clippedLayer = processing.run('gdal:cliprasterbymasklayer', 
                {
                    'INPUT': inputlayer,
                    'ALPHA_BAND': False,
                    'CROP_TO_CUTLINE': True,
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'KEEP_RESOLUTION': True,
                    'MASK': inputGrid,
                    'MULTITHREADING': False,
                    'NODATA': None,
                    'OPTIONS': '',
                    'SET_RESOLUTION' : False, 
                    'SOURCE_CRS' : None, 
                    'TARGET_CRS' : None, 
                    'X_RESOLUTION' : None, 
                    'Y_RESOLUTION' : None,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback)['OUTPUT']
        return clippedLayer
    def mergeAll(self, context, parameters, feedback, mergeLayers):
        rgbLayer =processing.run('gdal:merge', 
                {
                    'INPUT': mergeLayers,
                    'DATA_TYPE': 5,
                    'EXTRA': '',
                    'NODATA_INPUT' : None, 
                    'NODATA_OUTPUT' : None, 
                    'OPTIONS' : '', 
                    'PCT' : False, 
                    'SEPARATE' : False ,
                    'OUTPUT': parameters['OUTPUT']
                },
                context=context,
                feedback=feedback)
        return rgbLayer['OUTPUT']
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MakeMosaic()

    def name(self):
        return 'mosaic'

    def displayName(self):
        return self.tr('Mosaicar')

    def group(self):
        return self.tr('Vetor e Raster')

    def groupId(self):
        return 'vetoreraster'

    def shortHelpString(self):
        return self.tr("""
        Mosaica as camadas selcionadas baseada na camada de póligono 'moldura', que é responsável por limitar a área a ser mosaicada de cada imagem. Portanto, deve existir um polígono associado a cada imagem.

        Pode-se associar a imagem aos polígonos de forma automática ou informando o campo da camada de moldura que contém o nome da imagem, nesse caso será usado o campo 'nome' na moldura, portanto, é necessário que este campo já esteja preenchido com o nome da imagem correspondente. 
        
        No caso de imagens com paleta pode-se corrigir automaticamente. 
        
        Atenção: não corrigir paleta automaticamente quando selecionar outras camadas de apenas uma banda sem ser paleta, como MDS ou MDT.
        """)
