# -*- coding: utf-8 -*-

from qgis import processing
from qgis.PyQt.QtCore import QMetaType, QCoreApplication
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (QgsProcessingAlgorithm, QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterNumber,
                       QgsProject,
                       QgsPointXY,
                       QgsWkbTypes,
                       QgsSymbol,
                       QgsRendererCategory,
                       QgsCategorizedSymbolRenderer,
                       QgsFeature,
                       QgsFields,
                       QgsFeatureSink,
                       QgsField,
                       QgsCoordinateTransform,
                       QgsCoordinateReferenceSystem,
                       QgsGeometry,
                       QgsProcessingParameterFeatureSink,
                       QgsVectorLayer,
                       QgsTextFormat,
                       QgsTextBufferSettings,
                       QgsPalLayerSettings,
                       QgsVectorLayerSimpleLabeling
                        )
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
    CONE_DIRECTION = 'CONE_DIRECTION'
    DISTANCE_TARGET_AVIATION_AXIS = 'DISTANCE_TARGET_AVIATION_AXIS'
    OUTPUT_POINTS_GROUP = 'OUTPUT_POINTS_GROUP'
    OUTPUT_ZL_LINES_GROUP = 'OUTPUT_ZL_LINES_GROUP'
    OUTPUT_FLIGHT_NARIZ = 'OUTPUT_FLIGHT_NARIZ'
    OUTPUT_FLIGHT_CAuda = 'OUTPUT_FLIGHT_CAuda'
    OUTPUT_FLIGHT_CONE = 'OUTPUT_FLIGHT_CONE'

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
        self.flight_type = [
            "Nariz",
            "Cauda",
            "Cone"
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
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_POINTS_GROUP,
                self.tr("ALVO E PS"),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_ZL_LINES_GROUP,
                self.tr("Linhas da ZL"),
            )
        )

        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_FLIGHT_NARIZ, self.tr("Nariz")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_FLIGHT_CAuda, self.tr("Cauda")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_FLIGHT_CONE, self.tr("Cone")))

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

        fields = QgsFields()
        fields.append(QgsField("Tipo", QMetaType.Type.QString))

        crs = QgsCoordinateReferenceSystem("EPSG:4674")

        (output_points, output_points_id) = self.parameterAsSink(parameters, self.OUTPUT_POINTS_GROUP, context, fields, QgsWkbTypes.Point, crs)
        (output_zl_lines, output_zl_lines_id) = self.parameterAsSink(parameters, self.OUTPUT_ZL_LINES_GROUP, context, fields, QgsWkbTypes.LineString, crs)

        (nariz_sink, nariz_id) = self.parameterAsSink(parameters, self.OUTPUT_FLIGHT_NARIZ, context, fields, QgsWkbTypes.LineString, crs)
        (cauda_sink, cauda_id) = self.parameterAsSink(parameters, self.OUTPUT_FLIGHT_CAuda, context, fields, QgsWkbTypes.LineString, crs)
        (cone_sink, cone_id) = self.parameterAsSink(parameters, self.OUTPUT_FLIGHT_CONE, context, fields, QgsWkbTypes.LineString, crs)


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

        pointTarget = QgsPointXY(longTarget, latTarget)
        line_VA, line_QL = self.create_target_outputs(pointTarget, distanceOpenParachute, directionOpenParachuteMean ,distanceFreeFall, directionFreeFallMean)

        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(pointTarget), "ALVO", output_points)

        #NARIZ
        dispSalt = 0
        eixo_anv_nariz = directionOpenParachuteMean + 180
        ps_point_nariz = self.get_ps(pointTarget, distanceFreeFall, directionFreeFallMean, drag + dispSalt, eixo_anv_nariz)
        flight_return = self.flight_line(ps_point_nariz, drag, dispSalt, eixo_anv_nariz)

        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(ps_point_nariz), "PS NARIZ", output_points)

        aeroplane_line = flight_return[0]
        drag_line = flight_return[1]
        self.addFlightFeature(fields, aeroplane_line, "EIXO ANV", nariz_sink, nariz_sink)
        self.addFlightFeature(fields, drag_line, "ARRASTO", nariz_sink, nariz_sink)
        if len(flight_return) == 3:
            dispersion_line = flight_return[2]
            self.addFlightFeature(fields, dispersion_line, "DISPERSÃO", nariz_sink, nariz_sink)
        self.addFeatureInLayer(fields, line_VA, "VA", output_zl_lines)
        self.addFeatureInLayer(fields, line_QL, "QL", output_zl_lines)

        #CAUDA
        dispSalt = number_blocks * speed * interval_time
        eixo_anv_cauda = directionOpenParachuteMean
        ps_point_cauda = self.get_ps(pointTarget, distanceFreeFall, directionFreeFallMean, drag + dispSalt, eixo_anv_cauda)
        flight_return = self.flight_line(ps_point_cauda, drag, dispSalt, eixo_anv_cauda)

        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(ps_point_cauda), "PS CAUDA", output_points)
        aeroplane_line = flight_return[0]
        drag_line = flight_return[1]
        self.addFlightFeature(fields, aeroplane_line, "EIXO ANV", cauda_sink, cauda_sink)
        self.addFlightFeature(fields, drag_line, "ARRASTO", cauda_sink, cauda_sink)
        if len(flight_return) == 3:
            self.addFlightFeature(fields, flight_return[2], "DISPERSÃO", cauda_sink, cauda_sink)
        self.addFeatureInLayer(fields, line_VA, "VA", output_zl_lines)
        self.addFeatureInLayer(fields, line_QL, "QL", output_zl_lines)

        #CONE
        free_fall_angle = math.radians(directionFreeFallMean)
        open_parachute_angle = math.radians(directionOpenParachuteMean)
        distance_chao = 200
        distance_horizont = math.fabs(distance_chao + distanceFreeFall * math.cos(free_fall_angle - open_parachute_angle))
        
        dispSalt = number_blocks * speed * interval_time / 2
        eixo_anv_right = directionOpenParachuteMean + 90
        ps_point_right, ground_line, cone_QL_line = self.get_cone_outputs(pointTarget, distanceFreeFall, directionFreeFallMean, 
                                                    drag + dispSalt, eixo_anv_right, distance_chao, directionOpenParachuteMean)
        flight_return_right = self.flight_line(ps_point_right, drag, dispSalt, eixo_anv_right)

        eixo_anv_left = directionOpenParachuteMean + 270
        ps_point_left, _, _ = self.get_cone_outputs(pointTarget, distanceFreeFall, directionFreeFallMean, 
                                                    drag + dispSalt, eixo_anv_left, distance_chao, directionOpenParachuteMean)
        flight_return_left = self.flight_line(ps_point_left, drag, dispSalt, eixo_anv_left)

        # pontos PS
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(ps_point_left), "PS BC E", output_points)
        self.addFeatureInLayer(fields, QgsGeometry.fromPointXY(ps_point_right), "PS BC D", output_points)

        self.addFeatureInLayer(fields, ground_line, "200m", output_zl_lines)
        self.addFeatureInLayer(fields, cone_QL_line, "cone_QL_line", output_zl_lines)

        aeroplane_line_r = flight_return_right[0]
        drag_line_r = flight_return_right[1]
        self.addFlightFeature(fields, aeroplane_line_r, "EIXO ANV", cone_sink, cone_sink)
        self.addFlightFeature(fields, drag_line_r, "ARRASTO", cone_sink, cone_sink)
        if len(flight_return_right) == 3:
            self.addFlightFeature(fields, flight_return_right[2], "1/2 DISPERSÃO", cone_sink, cone_sink)

        aeroplane_line_l = flight_return_left[0]
        drag_line_l = flight_return_left[1]
        self.addFlightFeature(fields, aeroplane_line_l, "EIXO ANV", cone_sink, cone_sink)
        self.addFlightFeature(fields, drag_line_l, "ARRASTO", cone_sink, cone_sink)
        if len(flight_return_left) == 3:
            self.addFlightFeature(fields, flight_return_left[2], "1/2 DISPERSÃO", cone_sink, cone_sink)

        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        path_qml_point = os.path.join(caminho_atual, "style_pqd_point.qml")
        path_qml_line = os.path.join(caminho_atual, "style_pqd.qml")

        output_layer_points = context.getMapLayer(output_points_id)
        output_layer_zl_lines = context.getMapLayer(output_zl_lines_id)

        nariz_layer = context.getMapLayer(nariz_id)
        cauda_layer = context.getMapLayer(cauda_id)
        cone_layer = context.getMapLayer(cone_id)

        try:
            if output_layer_points is not None and output_layer_points.featureCount() > 0:
                text_format = QgsTextFormat()
                text_format.setFont(QFont("Arial", 12, QFont.Bold))
                text_format.setSize(12)
                text_format.setColor(QColor("black"))

                buffer = QgsTextBufferSettings()
                buffer.setEnabled(True)
                buffer.setSize(1.5)
                buffer.setColor(QColor("white"))
                text_format.setBuffer(buffer)

                pal = QgsPalLayerSettings()
                pal.fieldName = "Tipo"
                pal.setFormat(text_format)
                pal.enabled = True
                pal.drawLabels = True
                pal.placement = QgsPalLayerSettings.OrderedPositionsAroundPoint
                pal.dist = 2.0
                
                pal.predefinedPositionOrder = [
                    QgsPalLayerSettings.TopRight,
                    QgsPalLayerSettings.TopLeft,
                    QgsPalLayerSettings.BottomRight,
                    QgsPalLayerSettings.BottomLeft,
                    QgsPalLayerSettings.MiddleRight,
                    QgsPalLayerSettings.MiddleLeft
                ]

                labeling = QgsVectorLayerSimpleLabeling(pal)
                output_layer_points.setLabeling(labeling)
                output_layer_points.setLabelsEnabled(True)
                output_layer_points.triggerRepaint()
                output_layer_points.reload()
        except Exception as e:
            feedback.pushWarning(f"Aviso ao configurar rótulos: {str(e)}")
            pass        

        mapping_zl_lines = {
            "VA": ("#09D3F7", "VA", 0.9),
            "QL": ("#DDEAEC", "QL", 0.9),
            "200m": ("#000000", "200m", 1.0),
            "cone_QL_line": ("#DDEAEC", "Cone QL", 1.0),
        }

        mapping_flight = {
            "EIXO ANV": ("red", "Eixo ANV", 1.2),
            "ARRASTO": ("yellow", "Arrasto", 0.8),
            "DISPERSÃO": ("#1100FF", "Dispersão", 0.8),
            "1/2 DISPERSÃO": ("#1100FF", "½ Dispersão", 0.8),
        }

        mapping_points = {
            "ALVO": ("#FFFFFF", "Alvo", None),
            "PS NARIZ": ("#FFFFFF", "PS NARIZ", None),
            "PS CAUDA": ("#FFFFFF", "PS CAUDA", None),
            "PS BC E": ("#FFFFFF", "PS BC E", None),
            "PS BC D": ("#FFFFFF", "PS BC D", None),
        }

        def apply_style_or_legend(layer, qml_path, mapping):
            if not layer or layer.featureCount() == 0:
                return
            if os.path.exists(qml_path):
                layer.loadNamedStyle(qml_path)
                layer.triggerRepaint()
            else:
                self._apply_categorized_style(layer, mapping)

        apply_style_or_legend(nariz_layer, path_qml_line, mapping_flight)
        apply_style_or_legend(cauda_layer, path_qml_line, mapping_flight)
        apply_style_or_legend(cone_layer, path_qml_line, mapping_flight)
        apply_style_or_legend(output_layer_points, path_qml_point, mapping_points)
        apply_style_or_legend(output_layer_zl_lines, path_qml_line, mapping_zl_lines)

        project = QgsProject.instance()
        def add_if_missing(layer):
            if not layer:
                return
            try:
                if project.mapLayer(layer.id()) is None:
                    project.addMapLayer(layer)
            except Exception:
                try:
                    project.addMapLayer(layer)
                except Exception:
                    pass

        add_if_missing(output_layer_points)
        add_if_missing(nariz_layer)
        add_if_missing(cauda_layer)
        add_if_missing(cone_layer)
        add_if_missing(output_layer_zl_lines)
        
        results = {}

        if output_layer_points and output_layer_points.featureCount() > 0:
            results[self.OUTPUT_POINTS_GROUP] = output_points_id
        if output_layer_zl_lines and output_layer_zl_lines.featureCount() > 0:
            results[self.OUTPUT_ZL_LINES_GROUP] = output_zl_lines_id

        if nariz_layer and nariz_layer.featureCount() > 0:
            results[self.OUTPUT_FLIGHT_NARIZ] = nariz_id
        if cauda_layer and cauda_layer.featureCount() > 0:
            results[self.OUTPUT_FLIGHT_CAuda] = cauda_id
        if cone_layer and cone_layer.featureCount() > 0:
            results[self.OUTPUT_FLIGHT_CONE] = cone_id

        layer_entradas = QgsVectorLayer("NoGeometry?crs=EPSG:4674", "ENTRADAS ANV", "memory")

        provider = layer_entradas.dataProvider()
        provider.addAttributes([
            QgsField("TIPO", QMetaType.Type.QString),
            QgsField("ENTRADA_ANV", QMetaType.Type.Double),
            QgsField("DISTANCIA_HORIZONTAL", QMetaType.Type.Double)
        ])
        layer_entradas.updateFields()

        entrada_anv_nariz = self.creatre_entry_anv(magnetic_declination, directionOpenParachuteMean)
        entrada_anv_cauda = self.creatre_entry_anv(magnetic_declination, directionOpenParachuteMean + 180)
        entrada_anv_cone = self.creatre_entry_anv(magnetic_declination, directionOpenParachuteMean + 90)

        features = []

        feat_nariz = QgsFeature()
        feat_nariz.setAttributes(["NARIZ", round(entrada_anv_nariz, 2), None])
        features.append(feat_nariz)

        feat_cauda = QgsFeature()
        feat_cauda.setAttributes(["CAUDA", round(entrada_anv_cauda, 2), None])
        features.append(feat_cauda)

        feat_cone = QgsFeature()
        feat_cone.setAttributes(["CONE", round(entrada_anv_cone, 2), round(distance_horizont, 2)])
        features.append(feat_cone)
        
        provider.addFeatures(features)
        layer_entradas.updateExtents()

        QgsProject.instance().addMapLayer(layer_entradas)

        results["ENTRADAS_ANV"] = layer_entradas.id()

        return results

    def _apply_categorized_style(self, layer, mapping, field_name="Tipo"):
        if not layer:
            return

        field_idx = layer.fields().indexFromName(field_name)
        present_values = set()
        if field_idx != -1:
            for f in layer.getFeatures():
                try:
                    val = f[field_idx]
                    if val is None:
                        continue
                    present_values.add(str(val).strip())
                except Exception:
                    continue

        categories = []
        for key, val in mapping.items():
            color_name, label, width = val
            if present_values and (key not in present_values):
                continue
            sym = QgsSymbol.defaultSymbol(layer.geometryType())
            try:
                sym.setColor(QColor(color_name))
            except Exception:
                sym.setColor(QColor("gray"))
            if width is not None:
                try:
                    sym.setWidth(width)
                except Exception:
                    try:
                        for sl in sym.symbolLayers():
                            sl.setWidth(width)
                    except Exception:
                        pass
            try:
                if key == "EIXO ANV":
                    for sl in sym.symbolLayers():
                        sl.setRenderingPass(0)
                else:
                    for sl in sym.symbolLayers():
                        sl.setRenderingPass(1)
            except Exception:
                pass
            categories.append(QgsRendererCategory(key, sym, label))

        if present_values:
            unmapped = [v for v in present_values if v not in mapping.keys()]
            if len(unmapped) > 0:
                sym = QgsSymbol.defaultSymbol(layer.geometryType())
                try:
                    sym.setColor(QColor("lightgray"))
                except Exception:
                    pass
                categories.append(QgsRendererCategory(None, sym, "Outros"))

        if not categories:
            return

        renderer = QgsCategorizedSymbolRenderer(field_name, categories)
        if renderer is not None:
            layer.setRenderer(renderer)
            layer.triggerRepaint()

        try:
            proj = QgsProject.instance()
            if proj.mapLayer(layer.id()) is None:
                proj.addMapLayer(layer)
        except Exception:
            try:
                QgsProject.instance().addMapLayer(layer)
            except Exception:
                pass

    def addFlightFeature(self, fields, geometry, tipo, sink_lines, sink_eixo):
        target = sink_eixo or sink_lines
        if target is None:
            return
        self.addFeatureInLayer(fields, geometry, tipo, target)

    def addFeatureInLayer(self, fields, geometry, tipo, layerOut):
        feat = QgsFeature(fields)
        feat.setGeometry(geometry)
        feat["Tipo"] = tipo
        layerOut.addFeature(feat, QgsFeatureSink.FastInsert)
    
    def pointAndLineFromPointDistanceAndDirection(self, point, distance, direction):
        transform = QgsProject.instance().transformContext()
        coordTransform = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4674"), QgsCoordinateReferenceSystem("EPSG:5880"), transform)
        pointTargetProject = coordTransform.transform(point)
        directionRad = math.radians(direction)
        dx = distance * math.sin(directionRad)
        dy = distance * math.cos(directionRad)
        pointDestProj = QgsPointXY(pointTargetProject.x() + dx, pointTargetProject.y() + dy)
        coordTransformReverse = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:5880"), QgsCoordinateReferenceSystem("EPSG:4674"), transform)
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
        return round(directionMean / elements), round(intensityMean / elements)
    
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

    def get_ps(self, point, distance_1, direction_1, distance_2, direction_2):
        _, open_parachute_point = self.pointAndLineFromPointDistanceAndDirection(point, distance_1, direction_1)
        _, ps_point = self.pointAndLineFromPointDistanceAndDirection(open_parachute_point, distance_2, direction_2)
        return ps_point
    
    def get_cone_outputs(self, point, distance_1, direction_1, distance_2, direction_2, distance_chao, direction_chao):
        ground_line , ql_final_point = self.pointAndLineFromPointDistanceAndDirection(point, distance_chao, direction_chao)
        ql_cone, finish_dispersion_point = self.pointAndLineFromPointDistanceAndDirection(ql_final_point, distance_1, direction_1)
        _, ps_point_cone = self.pointAndLineFromPointDistanceAndDirection(finish_dispersion_point, distance_2, direction_2)
        return ps_point_cone, ground_line, ql_cone

    def create_target_outputs(self, point, distance_1, direction_1, distance_2, direction_2):
        line_VA, _ = self.pointAndLineFromPointDistanceAndDirection(point, distance_1, direction_1)
        line_QL, _ = self.pointAndLineFromPointDistanceAndDirection(point, distance_2, direction_2)
        return line_VA, line_QL
    
    def flight_line(self, ps_point, drag, dispersion, eixo_anv ):
        d = dispersion + drag
        _, aeroplane_start = self.pointAndLineFromPointDistanceAndDirection(ps_point, d, eixo_anv + 180)
        aeroplane_line, _ = self.pointAndLineFromPointDistanceAndDirection(aeroplane_start, 2 * d, eixo_anv)
        if dispersion != 0:
            dispersion_line, drag_start = self.pointAndLineFromPointDistanceAndDirection(aeroplane_start, dispersion, eixo_anv)
            drag_line, _ = self.pointAndLineFromPointDistanceAndDirection(drag_start, drag, eixo_anv)
            return aeroplane_line, drag_line, dispersion_line
        else:
            drag_line, _ = self.pointAndLineFromPointDistanceAndDirection(aeroplane_start, drag, eixo_anv)
            return aeroplane_line, drag_line

    def creatre_entry_anv(self, dm, anv_axe):
        soma = dm + anv_axe
        while soma > 360:
            soma -= 360
        return round(soma / 5) * 5

    def pressureAndDirectionIntensityWind(self, linesFileTxt, init_pressure_free_fall, init_pressure_open_parachute, end_pressure_open_parachute):
        pressureDirectionIntensityWindFreeFallDict = dict()
        pressureDirectionIntensityWindOpenParachuteDict = dict()
        for line in linesFileTxt:
            if not '.mb' in line:
                continue
            pressure = int(line.split(".mb")[0])
            if pressure > 900:
                return pressureDirectionIntensityWindFreeFallDict, pressureDirectionIntensityWindOpenParachuteDict 
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
        return self.tr('Vetor e Raster')

    def groupId(self):
        return 'vetoreraster'

    def shortHelpString(self):
        return self.tr('Converte em lote os zips contendo shapefiles no formato EDGV para o formato MASACODE')
