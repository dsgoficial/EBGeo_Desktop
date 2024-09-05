# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2018-12-18
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Philipe Borba - Cartographic Engineer @ Brazilian Army
        email                : borba.philipe@eb.mil.br
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from DsgTools.core.GeometricTools.featureHandler import FeatureHandler
from qgis.PyQt.Qt import QVariant
from PyQt5.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterVectorLayer,
    QgsWkbTypes,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingException,
    QgsCoordinateTransform,
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsField,
    QgsFields,
)


class MakeFrame(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    STOP_SCALE = "STOP_SCALE"
    OUTPUT = "OUTPUT"

    def initAlgorithm(self, config=None):
        """
        Parameter setting.
        """

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr("Camada de entrada"),
                [QgsProcessing.TypeVectorPolygon],
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
                options=self.scales,
                defaultValue=0,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, self.tr("Created Frames"))
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        featureHandler = FeatureHandler()
        inputLyr = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if inputLyr is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT)
            )
        inputLyr.updateExtents()
        stopScaleIdx = self.parameterAsEnum(parameters, self.STOP_SCALE, context)
        # Scale
        stopScale = self.scales[stopScaleIdx]
        stopScale = stopScale[2:]
        stopScale = int(stopScale.replace(".", ""))/1000

        fields = QgsFields()
        fields.append(QgsField("inom", QVariant.String))
        fields.append(QgsField("mi", QVariant.String))
        crs = inputLyr.crs()
        (output_sink, output_sink_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields, QgsWkbTypes.Polygon, crs
        )
        featureList = []
        coordinateTransformer = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem(crs.geographicCrsAuthId()),
            crs,
            QgsProject.instance(),
        )
        featureHandler.getSystematicGridFeaturesWithConstraint(
            featureList,
            inputLyr,
            stopScale,
            coordinateTransformer,
            fields,
            feedback=feedback,
        )
        list(
            map(
                lambda x: output_sink.addFeature(x, QgsFeatureSink.FastInsert),
                featureList,
            )
        )

        return {"OUTPUT": output_sink_id}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "frame"

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr("Gerar moldura sistemática associada à camada")

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr("Grid Algorithms")

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return "EBGeo - Grid Algoritmo de Molduras"

    def tr(self, string):
        return QCoreApplication.translate("makeFrame", string)

    def createInstance(self):
        return MakeFrame()
