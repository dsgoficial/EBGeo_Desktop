# -*- coding: utf-8 -*-

from typing import List
from EBGeo.Utils.featureHandler import FeatureHandler
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

    INPUT_FRAME = 'INPUT_FRAME'
    INPUT_LAYERS = 'INPUT_LAYERS'
    STOP_SCALE = 'STOP_SCALE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT_FRAME,
                self.tr('Selecionar camada de moldura'),
                [QgsProcessing.TypeVectorPolygon],
                optional=True
            )
        )

        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT_LAYERS,
                self.tr('Selecionar camadas'),
                QgsProcessing.TypeRaster,
                optional=False
            )
        )

        self.scales = [
            "1:250.000",
            "1:100.000",
            "1:50.000",
            "1:25.000",
        ]

        self.addParameter(
            QgsProcessingParameterEnum(
                self.STOP_SCALE,
                self.tr("Escala das cartas:"),
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
        inputFrameUser = self.parameterAsVectorLayer(parameters, self.INPUT_FRAME, context)

        featureHandler = FeatureHandler()
        
        # Scale
        stopScale = self.scales[stopScaleIdx]
        stopScale = stopScale[2:]
        stopScale = int(stopScale.replace(".", ""))/1000
        crs = layers[1].crs()

        # Crs raster layer
        if not inputFrameUser or inputFrameUser.featureCount()==0:
            inputFrame = self.getInputFrame(crs, layers, featureHandler, stopScale, feedback)
        else:
            inputFrame = self.reprojectLayer(inputFrameUser, crs)

        frameLayer = self.matchLayerAndFrame(inputFrame, layers)
        nameField = 'nome'
        frameGrid = frameLayer
        

        if not inputFrameUser or inputFrameUser.featureCount()==0:
            QgsProject.instance().removeMapLayer(inputFrame.id())
        
        
        
        
        
        multiStepFeedback = QgsProcessingMultiStepFeedback(3, feedback)
        multiStepFeedback.setCurrentStep(0)
        multiStepFeedback.pushInfo(self.tr("Selecionando camadas"))

        mergeLayers = self.mergeLayers(context, multiStepFeedback, frameGrid, layers, nameField)
        
        multiStepFeedback.setCurrentStep(1)
        multiStepFeedback.pushInfo(self.tr("Mesclado camadas"))
        merged = self.mergeAll(context, multiStepFeedback, mergeLayers)
        multiStepFeedback.setCurrentStep(2)
        multiStepFeedback.pushInfo(self.tr("Comprimindo saída"))
        compressed = self.compress(context, parameters, multiStepFeedback, merged)
        return {"OUTPUT": compressed}

    def mergeLayers(self, context, feedback:QgsProcessingMultiStepFeedback, frameGrid:QgsVectorLayer, layers:List[QgsVectorLayer], nameField)->List[QgsVectorLayer]:
        mergeLayers = []
        countGrid = frameGrid.featureCount()
        listLayerSize = len(layers)
        listSize = listLayerSize*countGrid
        progressStep = 100/listSize if listSize else 0
        i = 0
        multiStepFeedback = QgsProcessingMultiStepFeedback(listSize, feedback)
        for feat in frameGrid.getFeatures():
            frameGrid.removeSelection()
            for step, pctLayer in enumerate(layers):
                if feedback.isCanceled():
                    return {self.OUTPUT: 'cancelado'}
                if (feat[nameField] == pctLayer.name()):
                    frameGrid.select(feat.id())
                    frameSelected = frameGrid.materialize(QgsFeatureRequest().setFilterFids(frameGrid.selectedFeatureIds()))
                    if pctLayer.bandCount() == 1:
                        rgbLayer = self.pctToRgb(context, pctLayer, multiStepFeedback)
                    else:
                        rgbLayer = pctLayer
                    clippedLayer = self.clipLayer(context, rgbLayer, frameSelected, multiStepFeedback)
                    mergeLayers.append(clippedLayer)
                    frameGrid.removeSelection()
                multiStepFeedback.setCurrentStep((i-1)*listLayerSize + step + 1)
            i += 1
        return mergeLayers

    def getInputFrame(self, crs, layers, featureHandler, stopScale, feedback):
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
        QgsProject.instance().removeMapLayer(rasterRange.id())
        return inputFrame
    

    
    def matchLayerAndFrame(self, inputFrame, layers)->QgsVectorLayer:
        frameLayer = processing.run('EBGeoProvider:matchlayerandframe',
                {
                    'INPUT_LAYERS': layers,
                    'INPUT_FRAME': inputFrame,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })['OUTPUT']
        return frameLayer
    
    def reprojectLayer(self, layer, crs):
        reprojLayer = processing.run('native:reprojectlayer',
                {
                    'INPUT': layer,
                    'TARGET_CRS': crs,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                })['OUTPUT']
        return reprojLayer
        
    
    def pctToRgb(self, context, inputlayer, feedback=None):
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
    def clipLayer(self, context, inputlayer, inputGrid, feedback=None):
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
    def mergeAll(self, context, feedback, mergeLayers):
        rgbLayer =processing.run('gdal:merge', 
                {
                    'INPUT': mergeLayers,
                    'DATA_TYPE': 0,
                    'EXTRA': '',
                    'NODATA_INPUT' : None, 
                    'NODATA_OUTPUT' : None, 
                    'OPTIONS' : '', 
                    'PCT' : False, 
                    'SEPARATE' : False ,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                },
                context=context,
                feedback=feedback)
        return rgbLayer['OUTPUT']
    def compress(self, context, parameters, feedback, layer):
        compressedLayer = processing.run("gdal:translate", 
                       {'INPUT':layer,
                        'TARGET_CRS':None,
                        'NODATA':None,
                        'COPY_SUBDATASETS':False,
                        'OPTIONS':'COMPRESS=JPEG',
                        'EXTRA':'-co PHOTOMETRIC=YCBCR -co TILED=YES -b 1 -b 2 -b 3',
                        'DATA_TYPE':0,
                        'OUTPUT':parameters['OUTPUT']
                        },
                context=context,
                feedback=feedback)
        return compressedLayer['OUTPUT']
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
        Mosaica as camadas selecionadas baseada na camada de polígono 'moldura', que é responsável por limitar a área a ser mosaicada de cada imagem. Caso não seja colocado nenhuma moldura, a moldura será calculada automaticamente, o que pode resultar em problemas para cartas mais antigas que não estão em SAD69.
        
        No caso de imagens com paleta será corrigido automaticamente. 
        
        Atenção: não mosaicar cartas com outras camadas como MDS ou MDT.
        """)
