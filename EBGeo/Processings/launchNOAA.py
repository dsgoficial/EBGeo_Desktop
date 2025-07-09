# -*- coding: utf-8 -*-

from qgis import processing
from qgis.PyQt.Qt import QVariant
from qgis.core import (QgsProcessingAlgorithm, QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterNumber,
                       QgsProject,
                       QgsPointXY,
                       QgsWkbTypes,
                       QgsFeature,
                       QgsFields,
                       QgsFeatureSink,
                       QgsField,
                       QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem,
                       QgsGeometry,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingUtils)
from qgis.PyQt.QtCore import QCoreApplication
import math
import os

class LaunchNOAA(QgsProcessingAlgorithm):
    FILE_TXT = 'FILE_TXT'
    AIRCRAFT = 'AIRCRAFT'
    NUMBER_BLOCKS = 'NUMBER_BLOCKS'
    TIME_INTERVAL = 'TIME_INTERVAL'
    MAGNETIC_DECLINATION = 'MAGNETIC_DECLINATION'
    INIT_PRESSURE_FREE_FALL = 'INIT_PRESSURE_FREE_FALL'
    INIT_PRESSURE_OPEN_PARACHUTE = 'INIT_PRESSURE_OPEN_PARACHUTE'
    END_PRESSURE_OPEN_PARACHUTE = 'END_PRESSURE_OPEN_PARACHUTE'
    HEIGHT_FREE_FALL = 'HEIGHT_FREE_FALL'
    HEIGHT_OPEN_PACHUTE = 'HEIGHT_OPEN_PACHUTE'
    DISTANCE_TARGET_AVIATION_AXIS = 'DISTANCE_TARGET_AVIATION_AXIS'
    OUTPUT_POINT = 'OUTPUT_POINT'
    OUTPUT_LINE_CAUDA = 'OUTPUT_LINE_CAUDA'
    OUTPUT_LINE_NARIZ = 'OUTPUT_LINE_NARIZ'
    OUTPUT_LINE_BOCACONE = 'OUTPUT_LINE_BOCACONE'

    def initAlgorithm(self, config = None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.FILE_TXT,
                self.tr('Arquivo de texto com direção e intensidade do vento'),
                behavior=QgsProcessingParameterFile.File,
                fileFilter='Texto (*.txt)'
            )
        )
        self.aircrafts = [
            "C-130",
            "C-105",
            "C-95",
            "KC-390",
            "Caravan",
        ]
        self.addParameter(
            QgsProcessingParameterEnum(
                self.AIRCRAFT,
                self.tr('Aeronave utilizada para o salto'),
                options=self.aircrafts,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NUMBER_BLOCKS,
                self.tr("Número de blocos de saltadores"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TIME_INTERVAL,
                self.tr("Intervalo de tempo entre os blocos em segundos"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MAGNETIC_DECLINATION,
                self.tr("Declinação magnética"),
                minValue=0,
                type=QgsProcessingParameterNumber.Double,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INIT_PRESSURE_FREE_FALL,
                self.tr("Valor da pressão no ínicio da queda livre"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INIT_PRESSURE_OPEN_PARACHUTE,
                self.tr("Valor da pressão no ínicio do velame aberto"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.END_PRESSURE_OPEN_PARACHUTE,
                self.tr("Valor da pressão no final do velame aberto"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HEIGHT_FREE_FALL,
                self.tr("Altura em milhares em queda livre"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HEIGHT_OPEN_PACHUTE,
                self.tr("Altura em milhares com o velame aberto"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DISTANCE_TARGET_AVIATION_AXIS,
                self.tr("Distância entre o alvo e o eixo de aviação para o boca de cone"),
                minValue=0,
                type=QgsProcessingParameterNumber.Integer,
                optional=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_POINT,
                self.tr("Vetores de ponto"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINE_CAUDA,
                self.tr("Vetores de linha cauda"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINE_NARIZ,
                self.tr("Vetores linha nariz"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINE_BOCACONE,
                self.tr("Vetores linha boca do cone"),
            )
        )

    def processAlgorithm(self, parameters, context, feedback):         
        file_txt = self.parameterAsFile(parameters, self.FILE_TXT, context)
        aircraftIdx = self.parameterAsEnum(parameters, self.AIRCRAFT, context)
        aircraft = self.aircrafts[aircraftIdx]
        number_blocks = self.parameterAsInt(parameters, self.NUMBER_BLOCKS, context)
        interval_time = self.parameterAsInt(parameters, self.TIME_INTERVAL, context)
        magnetic_declination = self.parameterAsDouble(parameters, self.MAGNETIC_DECLINATION, context)
        init_pressure_free_fall = self.parameterAsInt(parameters, self.INIT_PRESSURE_FREE_FALL, context)
        init_pressure_open_parachute = self.parameterAsInt(parameters, self.INIT_PRESSURE_OPEN_PARACHUTE, context)
        end_pressure_open_parachute = self.parameterAsInt(parameters, self.END_PRESSURE_OPEN_PARACHUTE, context)
        height_free_fall = self.parameterAsInt(parameters, self.HEIGHT_FREE_FALL, context)
        height_open_parachute = self.parameterAsInt(parameters, self.HEIGHT_OPEN_PACHUTE, context)
        distTargetAviationAxis = self.parameterAsInt(parameters, self.DISTANCE_TARGET_AVIATION_AXIS, context)

        fields = QgsFields()
        fields.append(QgsField("Tipo", QVariant.String))

        crs = QgsCoordinateReferenceSystem("EPSG:4326")

        (output_point, output_point_id) = self.parameterAsSink(
            parameters, self.OUTPUT_POINT, context, fields, QgsWkbTypes.Point, crs
        )

        (output_line_cauda, output_line_cauda_id) = self.parameterAsSink(
            parameters, self.OUTPUT_LINE_CAUDA, context, fields, QgsWkbTypes.LineString, crs
        )

        (output_line_nariz, output_line_nariz_id) = self.parameterAsSink(
            parameters, self.OUTPUT_LINE_NARIZ, context, fields, QgsWkbTypes.LineString, crs
        )

        (output_line_bocacone, output_line_bocacone_id) = self.parameterAsSink(
            parameters, self.OUTPUT_LINE_BOCACONE, context, fields, QgsWkbTypes.LineString, crs
        )

        drag, speed = self.dragAndSpeedAircraft(aircraft)

        with open(file_txt, 'r') as file:
            lines = file.readlines()

        latTarget, longTarget = self.latlongTarget(lines)

        pressureDirectionIntensityWindFreeFallDict, pressureDirectionIntensityWindOpenParachuteDict = self.pressureAndDirectionIntensityWind(
            lines,
            init_pressure_free_fall,
            init_pressure_open_parachute,
            end_pressure_open_parachute,
        )

        directionFreeFallMean, intensityFreeFallMean = self.directionAndIntensityMean(pressureDirectionIntensityWindFreeFallDict)
        directionOpenParachuteMean, intensityOpenParachuteMean = self.directionAndIntensityMean(pressureDirectionIntensityWindOpenParachuteDict)

        distanceOpenParachute = 25 * intensityOpenParachuteMean * height_open_parachute
        distanceFreeFall = 3 * intensityFreeFallMean * height_free_fall

        dispSalt = number_blocks * speed * interval_time
        
        pointTarget = QgsPointXY(longTarget, latTarget)

        lineOpenParachute, pointDestOpenParachute = self.pointAndLineFromPointDistanceAndDirection(pointTarget, distanceOpenParachute, directionOpenParachuteMean)
        lineFreeFall, pointDestFreeFall = self.pointAndLineFromPointDistanceAndDirection(pointTarget, distanceFreeFall, directionFreeFallMean)
        
        lineDragNariz, pointInitNariz = self.pointAndLineFromPointDistanceAndDirection(pointDestFreeFall, drag, directionOpenParachuteMean + 180)

        lineDispCauda, pointInitDisp = self.pointAndLineFromPointDistanceAndDirection(pointDestFreeFall, dispSalt, directionOpenParachuteMean)

        lineDragCauda, pointInitCauda = self.pointAndLineFromPointDistanceAndDirection(pointInitDisp, drag, directionOpenParachuteMean)

        distBocaCone = ((1/2 * dispSalt + drag) ** 2 + distTargetAviationAxis ** 2) ** (1/2)

        lineDispBCRight, pointDispDestBCRight = self.pointAndLineFromPointDistanceAndDirection(pointDestFreeFall, 1/2 * dispSalt, directionOpenParachuteMean + 270)
        lineDispBCLeft, pointDispDestBCLeft = self.pointAndLineFromPointDistanceAndDirection(pointDestFreeFall, 1/2 * dispSalt, directionOpenParachuteMean + 90)

        lineDragBCRight, pointInitBCRight = self.pointAndLineFromPointDistanceAndDirection(pointDispDestBCRight, drag, directionOpenParachuteMean + 270)
        lineDragBCLeft, pointInitBCLeft = self.pointAndLineFromPointDistanceAndDirection(pointDispDestBCLeft, drag, directionOpenParachuteMean + 90)

        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointTarget), "ALVO", output_point)
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointInitNariz), "NARIZ", output_point)
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointInitCauda), "CAUDA", output_point)
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointInitBCLeft), "BC LEFT", output_point)
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointInitBCRight), "BC RIGHT", output_point)

        self.addFeatureInLayer(fields, lineOpenParachute, "VELAME ABERTO", output_line_cauda)
        self.addFeatureInLayer(fields, lineOpenParachute, "VELAME ABERTO", output_line_nariz)

        self.addFeatureInLayer(fields, lineFreeFall, "QUEDA LIVRE", output_line_cauda)
        self.addFeatureInLayer(fields, lineFreeFall, "QUEDA LIVRE", output_line_nariz)

        self.addFeatureInLayer(fields, lineDispCauda, "DISPERSÃO", output_line_cauda)
        self.addFeatureInLayer(fields, lineDispBCRight, "DISPERSÃO", output_line_bocacone)
        self.addFeatureInLayer(fields, lineDispBCLeft, "DISPERSÃO", output_line_bocacone)

        self.addFeatureInLayer(fields, lineDragNariz, "ARRASTO", output_line_nariz)
        self.addFeatureInLayer(fields, lineDragCauda, "ARRASTO", output_line_cauda)
        self.addFeatureInLayer(fields, lineDragBCRight, "ARRASTO", output_line_bocacone)
        self.addFeatureInLayer(fields, lineDragBCLeft, "ARRASTO", output_line_bocacone)

        output_layer_cauda = context.getMapLayer(output_line_cauda_id)
        output_layer_line = context.getMapLayer(output_line_nariz_id)
        output_layer_bocacone = context.getMapLayer(output_line_bocacone_id)
        output_layer_point = context.getMapLayer(output_point_id)
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_estilos = os.path.join(caminho_atual, 'styles')
        path_qml = os.path.join(pasta_estilos, 'style_pqd.qml')
        path_qml_point = os.path.join(pasta_estilos, 'style_pqd_point.qml')
        output_layer_cauda.loadNamedStyle(path_qml)
        output_layer_line.loadNamedStyle(path_qml)
        output_layer_bocacone.loadNamedStyle(path_qml)
        output_layer_point.loadNamedStyle(path_qml_point)
        output_layer_cauda.triggerRepaint()
        output_layer_line.triggerRepaint()
        output_layer_bocacone.triggerRepaint()
        output_layer_point.triggerRepaint()

        return {
            self.OUTPUT_POINT: output_point_id,
            self.OUTPUT_LINE_NARIZ: output_line_nariz_id,
            self.OUTPUT_LINE_CAUDA: output_line_cauda_id,
            self.OUTPUT_LINE_BOCACONE: output_line_bocacone_id
        }
    
    def addFeatureInLayer(self, fields, geometry, tipo, layerOut):
        feat = QgsFeature(fields)
        feat.setGeometry(geometry)
        feat["Tipo"] = tipo
        layerOut.addFeature(feat, QgsFeatureSink.FastInsert)
    
    def pointAndLineFromPointDistanceAndDirection(self, point, distance, direction):
        transform = QgsProject.instance().transformContext()
        coordTransform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem("EPSG:3857"), transform)
        pointTargetProject = coordTransform.transform(point)        
        directionRad = math.radians(direction)
        dx = distance * math.sin(directionRad)
        dy = distance * math.cos(directionRad)
        pointDestProj = QgsPointXY(pointTargetProject.x() + dx, pointTargetProject.y() + dy)
        coordTransformReverse = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:3857"), QgsCoordinateReferenceSystem("EPSG:4326"), transform)
        pointDest = coordTransformReverse.transform(pointDestProj)
        line = QgsGeometry.fromPolylineXY([point, pointDest])
        return line, pointDest
    
    def latlongTarget(self, linesFileTxt):
        for line in linesFileTxt:
            if 'Latitude' not in line:
                continue
            line = line.replace(" ", "")
            lat_part = line.split("Latitude:")[1].split("Longitude:")[0].strip()
            long_part = line.split("Longitude:")[1].split("&")[0].strip()

            lat = float(lat_part)
            long = float(long_part)

        return lat, long

    def directionAndIntensityMean(self, dictPressureDirectionAndIntensity):
        directionMean = 0
        intensityMean = 0
        elements = len(dictPressureDirectionAndIntensity)
        for pressure in dictPressureDirectionAndIntensity:
            directionMean += dictPressureDirectionAndIntensity[pressure][0]
            intensityMean += dictPressureDirectionAndIntensity[pressure][1]
        return directionMean / elements, intensityMean / elements
    
    def dragAndSpeedAircraft(self, aircraft):
        if aircraft in ["C-130", "C-105", "KC-390"]:
            drag = 300
            speed = 70
        elif aircraft == "C-95":
            drag = 150
            speed = 60
        elif aircraft == "Caravan":
            drag = 150
            speed = 40
        return drag, speed
    
    def pressureAndDirectionIntensityWind(
            self, 
            linesFileTxt, 
            init_pressure_free_fall, 
            init_pressure_open_parachute, 
            end_pressure_open_parachute,
        ):
        pressureDirectionIntensityWindFreeFallDict = dict()
        pressureDirectionIntensityWindOpenParachuteDict = dict()
        for line in linesFileTxt:
            if not '.mb' in line:
                continue
            pressure = int(line.split(".mb")[0])
            directionAndIntensity = line.split(".mb")[1].split(" ")[1]
            direction = int(directionAndIntensity.split("@")[0])
            intensity = int(directionAndIntensity.split("@")[1])
            if pressure >= init_pressure_free_fall and pressure < init_pressure_open_parachute:
                pressureDirectionIntensityWindFreeFallDict[pressure] = [direction, intensity]
            elif pressure >= init_pressure_open_parachute and pressure <= end_pressure_open_parachute:
                pressureDirectionIntensityWindOpenParachuteDict[pressure] = [direction, intensity]
        return pressureDirectionIntensityWindFreeFallDict, pressureDirectionIntensityWindOpenParachuteDict

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return LaunchNOAA()

    def name(self):
        return 'launchnoaa'

    def displayName(self):
        return self.tr("Lançamento Paraquedista NOAA")

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'MASACODE'

    def shortHelpString(self):
        return self.tr('Converte em lote os zips contendo shapefiles no formato EDGV para o formato MASACODE')
    
