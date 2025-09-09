# -*- coding: utf-8 -*-

import os
import tempfile
from typing import List
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsProject,
                       QgsVectorLayer,
                       QgsProcessingAlgorithm,
                       QgsProcessingException,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterVectorLayer,
                       QgsFeature,
                       QgsFeatureRequest,
                       QgsFeatureSink,
                       QgsField,
                       QgsFields,
                       QgsGeometry,
                       QgsProcessingMultiStepFeedback,
                       QgsProject,
                       QgsProcessingParameterRasterDestination,
                       QgsRasterLayer
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
        stopScaleIdxUser = self.parameterAsEnum(parameters, self.STOP_SCALE, context)
        inputFrameUser = self.parameterAsVectorLayer(parameters, self.INPUT_FRAME, context)
    
        user_scales = [250000, 100000, 50000, 25000]  
        stopScale = user_scales[stopScaleIdxUser]
        crs = layers[0].crs()

        frameGrid = self.getInputFrame(crs, layers, stopScale, feedback, context)

        multiStepFeedback = QgsProcessingMultiStepFeedback(4, feedback)
        multiStepFeedback.setCurrentStep(0)
        multiStepFeedback.pushInfo(self.tr("Selecionando camadas"))

        mergeLayers = self.mergeLayers(context, multiStepFeedback, frameGrid, layers)
            
        multiStepFeedback.setCurrentStep(1)
        multiStepFeedback.pushInfo(self.tr("Mesclado camadas"))
        merged = self.mergeAll(context, multiStepFeedback, mergeLayers)

        if inputFrameUser and inputFrameUser.featureCount():
            multiStepFeedback.setCurrentStep(2)
            multiStepFeedback.pushInfo(self.tr("Aplicando moldura final do usuário"))

            userFrameReproj = self.reprojectLayer(inputFrameUser, crs)
            mask_file = os.path.join(tempfile.gettempdir(), "mask.shp")
            processing.run(
                "native:savefeatures",
                {"INPUT": userFrameReproj, "OUTPUT": mask_file},
                context=context,
                feedback=multiStepFeedback
            )

            merged = processing.run(
                "gdal:cliprasterbymasklayer",
                {
                    "INPUT": merged,
                    "MASK": mask_file,
                    "CROP_TO_CUTLINE": True,
                    "KEEP_RESOLUTION": True,
                    "OUTPUT": "TEMPORARY_OUTPUT"
                },
                context=context,
                feedback=multiStepFeedback
            )["OUTPUT"]
        else:
            QgsProject.instance().removeMapLayer(frameGrid.id())
        
        multiStepFeedback.setCurrentStep(3)
        multiStepFeedback.pushInfo(self.tr("Comprimindo saída"))
        compressed = self.compress(context, parameters, multiStepFeedback, merged)

        return {"OUTPUT": compressed}


    def mergeLayers(self, context, feedback:QgsProcessingMultiStepFeedback, frameGrid:QgsVectorLayer, layers:List[QgsVectorLayer])->List[QgsVectorLayer]:
        for i, r in enumerate(layers):
            if isinstance(r, str):
                name = os.path.basename(r).rsplit('.', 1)[0]
                layers[i] = QgsRasterLayer(r, name)
            elif not isinstance(r, QgsRasterLayer):
                raise TypeError(f"Elemento inválido em layers: {r} (esperado QgsRasterLayer)")
            
        clipped_outputs = []
        total = len(layers)
        local_feedback = QgsProcessingMultiStepFeedback(max(1,total), feedback)
        step = 0

        for raster in layers:
            if feedback.isCanceled():
                return[]
            else:
                center = raster.extent().center()
                point = QgsGeometry.fromPointXY(center)

                request = QgsFeatureRequest().setFilterRect(raster.extent())
                frameSelected = frameGrid.materialize(
                    QgsFeatureRequest().setFilterFids([
                        f.id() for f in frameGrid.getFeatures(request) if f.geometry().contains(point)
                    ])
                )
                if frameSelected.featureCount() == 0:
                    raise QgsProcessingException(f"Nenhuma feição do frameGrid contém o raster {raster.name()}")
                rgbLayer = self.pctToRgb(context, raster, local_feedback) if raster.bandCount() == 1 else raster
                clipped = self.clipLayer(context, rgbLayer, frameSelected, local_feedback)
                clipped_outputs.append(clipped)

                step += 1
                local_feedback.setCurrentStep(step)

        
        return clipped_outputs

    def getInputFrame(self, crs, layers, stopScale, feedback, context):
        raster_points = QgsVectorLayer(f"Point?crs={crs.authid()}", "raster_points", "memory")
        prov = raster_points.dataProvider()
        fields = QgsFields()
        fields.append(QgsField("mi", QVariant.String))
        prov.addAttributes(fields)
        raster_points.updateFields()

        for raster in layers:
            feat = QgsFeature()
            center = raster.extent().center()
            feat.setGeometry(QgsGeometry.fromPointXY(center))
            feat.setAttributes([raster.name()])
            prov.addFeature(feat, QgsFeatureSink.FastInsert)

        raster_points.updateExtents()

        internal_scales = ["1000k", "500k", "250k", "100k", "50k", "25k", "10k", "5k", "2k", "1k"]
        stopScaleStr = f"{(stopScale//1000)}k"
        if stopScaleStr not in internal_scales:
            stopScaleStr = internal_scales[0] 
        stopScaleIdx = internal_scales.index(stopScaleStr)

        result = processing.run(
            "EBGeoProvider:frame",
            {
                "INPUT": raster_points,
                "STOP_SCALE": stopScaleIdx,
                "XSUBDIVISIONS": 1,
                "YSUBDIVISIONS": 1,
                "OUTPUT": "TEMPORARY_OUTPUT"
            },
            context=context,
            feedback=feedback
        )

        inputFrame = result["OUTPUT"]

        if inputFrame is None:
            raise QgsProcessingException("Falha ao criar a moldura automática (OUTPUT nulo).")

        return inputFrame

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
        vrt_file = os.path.join(tempfile.gettempdir(), "temp_mosaic.vrt")
        processing.run(
            "gdal:buildvirtualraster",
            {
                "INPUT": mergeLayers,
                "RESOLUTION": 0,
                "SEPARATE": False,
                "OUTPUT": vrt_file
            },
            context=context,
            feedback=feedback
        )
        merged_tif = processing.run(
            "gdal:translate",
            {
                "INPUT": vrt_file,
                "OUTPUT": "TEMPORARY_OUTPUT",
                "OPTIONS": "",
                "DATA_TYPE": 0 
            },
            context=context,
            feedback=feedback
        )["OUTPUT"]

        return merged_tif
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
