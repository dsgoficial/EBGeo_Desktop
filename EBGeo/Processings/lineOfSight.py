# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QMetaType
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsSymbol,
                       QgsRendererCategory,
                       QgsVectorLayer,
                       QgsProject,
                       QgsFeature,
                       QgsFields,
                       QgsField,
                       QgsGeometry,
                       QgsPointXY,
                       QgsWkbTypes,
                       QgsCategorizedSymbolRenderer,
                       Qgis  
                        )
import math
import processing

class LineOfSight(QgsProcessingAlgorithm):
    DEM_RASTER = "DemRaster"
    LINES_LAYER = "LinesLayer"
    OBSERVER_HEIGHT = "ObserverHeight"
    TARGET_HEIGHT = "TargetHeight"
    OUTPUT = "OutputLayer"

    def initAlgorithm(self, configuration=None):
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.DEM_RASTER,
                "Modelo Digital de Elevação (MDE)"
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.LINES_LAYER,
                self.tr("Camada de linhas"),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.OBSERVER_HEIGHT,
                "Altura do Observador acima do Terreno (m)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.TARGET_HEIGHT,
                "Altura do Alvo acima do Terreno (m)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.0,
                minValue=0.0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                "Linha de Visibilidade"
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        dem_raster = self.parameterAsRasterLayer(parameters, self.DEM_RASTER, context)
        lines_layer = self.parameterAsSource(parameters, self.LINES_LAYER, context)
        observer_height = self.parameterAsDouble(parameters, self.OBSERVER_HEIGHT, context)
        target_height = self.parameterAsDouble(parameters, self.TARGET_HEIGHT, context)
        
        if not self.check_inputs(dem_raster, lines_layer, feedback):
            return {}

        fields = QgsFields()
        fields.append(QgsField("obs_idx", QMetaType.Type.Int))
        fields.append(QgsField("tgt_idx", QMetaType.Type.Int))
        fields.append(QgsField("visible", QMetaType.Type.Int)) 

        sink, dest_id = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineString,
            lines_layer.sourceCrs()
        )

        n_feats = lines_layer.featureCount()

        for line_idx, feature in enumerate(lines_layer.getFeatures()):
            if feedback.isCanceled():
                break
            
            progress = int((line_idx / n_feats) * 100)
            feedback.setProgress(progress)
            feedback.setProgressText(f"Processando linha {line_idx+1}/{n_feats}")

            self._process_line_feature(
                feature, dem_raster, observer_height, target_height,
                sink, fields, lines_layer.sourceCrs(),
                context, feedback
            )
        feedback.setProgress(100)
        
        out_layer = context.takeResultLayer(dest_id)
        self._apply_layer_style(out_layer)

        return {self.OUTPUT: dest_id}

    def _process_line_feature(self, feature, dem_raster, observer_height, target_height,
                          sink, fields, crs, context, feedback):
        verts = self._sample_line_vertices(feature, dem_raster, crs, context)
        
        self._process_visibility_for_vertices(
            verts, dem_raster, observer_height, target_height,
            sink, fields, context, feedback
        )

    def _sample_line_vertices(self, feature, dem_raster, crs, context):
        single_layer = QgsVectorLayer(
            f"LineString?crs={crs.authid()}",
            "temp_line",
            "memory"
        )
        prov = single_layer.dataProvider()
        prov.addFeatures([feature])
        single_layer.updateExtents()
        
        verts = processing.run("qgis:extractvertices", {
            "INPUT": single_layer,
            "OUTPUT": "memory:"
        }, context=context, feedback=None)["OUTPUT"]
        
        sampled = processing.run("qgis:rastersampling", {
            "INPUT": verts,
            "RASTERCOPY": dem_raster,
            "COLUMN_PREFIX": "z_",
            "OUTPUT": "memory:"
        }, context=context, feedback=None)["OUTPUT"]
        
        return list(sampled.getFeatures())

    def _process_visibility_for_vertices(self, sampled_feats, dem_raster, observer_height, target_height,
                                        sink, fields, context, feedback):
        for i in range(len(sampled_feats) - 1):
            p_obs = sampled_feats[i]
            p_tgt = sampled_feats[i + 1]

            obs_pt = p_obs.geometry().asPoint()
            tgt_pt = p_tgt.geometry().asPoint()

            obs_xyz = (obs_pt.x(), obs_pt.y(), p_obs["z_1"] + observer_height)
            tgt_xyz = (tgt_pt.x(), tgt_pt.y(), p_tgt["z_1"] + target_height)

            visible, block_xy = self.calculate_visibility(
                obs_xyz, tgt_xyz, dem_raster, context=context, feedback=feedback
            )

            self._add_visibility_features(obs_pt, tgt_pt, block_xy, visible, i, sink, fields)

    def _add_visibility_features(self, obs_pt, tgt_pt, block_xy, visible, idx, sink, fields):
        if visible:
            feat = QgsFeature(fields)
            feat.setGeometry(QgsGeometry.fromPolylineXY([obs_pt, tgt_pt]))
            feat.setAttribute("obs_idx", idx)
            feat.setAttribute("tgt_idx", idx + 1)
            feat.setAttribute("visible", 1)
            sink.addFeature(feat)
        else:
            block_point = QgsPointXY(block_xy[0], block_xy[1])
            feat_vis = QgsFeature(fields)
            feat_vis.setGeometry(QgsGeometry.fromPolylineXY([obs_pt, block_point]))
            feat_vis.setAttribute("obs_idx", idx)
            feat_vis.setAttribute("tgt_idx", idx + 1)
            feat_vis.setAttribute("visible", 1)
            sink.addFeature(feat_vis)

            feat_block = QgsFeature(fields)
            feat_block.setGeometry(QgsGeometry.fromPolylineXY([block_point, tgt_pt]))
            feat_block.setAttribute("obs_idx", idx)
            feat_block.setAttribute("tgt_idx", idx + 1)
            feat_block.setAttribute("visible", 0)
            sink.addFeature(feat_block)

    def sample_dem_height_processing(self, dem_raster, points, context, feedback):

        point_layer = QgsVectorLayer(f"Point?crs={dem_raster.crs().authid()}", "temp_points", "memory")
        prov = point_layer.dataProvider()

        feats = []
        for pt in points:
            f = QgsFeature()
            if isinstance(pt, QgsPointXY):
                f.setGeometry(QgsGeometry.fromPointXY(pt))
            else:
                f.setGeometry(pt.geometry())
            feats.append(f)

        prov.addFeatures(feats)
        point_layer.updateExtents()

        sampled = processing.run("qgis:rastersampling", {
            "INPUT": point_layer,
            "RASTERCOPY": dem_raster,
            "COLUMN_PREFIX": "z_",
            "OUTPUT": "memory:"
        }, context=context, feedback=None)["OUTPUT"]

        heights = [f["z_1"] for f in sampled.getFeatures()]
        return heights

    def curvature_refraction_correction(self, distance):
        refraction_coeff = 0.13
        earth_radius = 6371000
        R_prime = earth_radius / (1 - refraction_coeff)
        delta_h = R_prime * (1 - math.cos(distance / R_prime))
        return delta_h

    def calculate_visibility(self, obs_xyz, tgt_xyz, dem_raster, context=None, feedback=None):
        x0, y0, z0 = obs_xyz
        x1, y1, z1 = tgt_xyz
        line_distance = math.sqrt((x1 - x0)**2 + (y1 - y0)**2 + (z1 - z0)**2)
        if line_distance <= 100:
            n_samples = int(line_distance / 0.5)
        elif 100 < line_distance <= 1000:
            n_samples = int(line_distance)
        elif 1000 < line_distance <= 10000:
            n_samples = int(line_distance / 5)
        elif 10000 < line_distance <= 50000:
            n_samples = int(line_distance / 25)
        else:
            n_samples = int(line_distance / 100)

        points = [
            QgsPointXY(x0 + (i / n_samples) * (x1 - x0),
                       y0 + (i / n_samples) * (y1 - y0))
            for i in range(1, n_samples)
        ]

        z_vals = self.sample_dem_height_processing(dem_raster, points, context, feedback)

        for i, z_dem in enumerate(z_vals):
            t = (i + 1) / n_samples
            z_expected = z0 + t * (z1 - z0)
            distance = math.sqrt((points[i].x() - x0)**2 + (points[i].y() - y0)**2)
            z_dem_corrected = z_dem - self.curvature_refraction_correction(distance)
            if z_dem_corrected > z_expected:
                return False, (points[i].x(), points[i].y())

        return True, None
    
    def _apply_layer_style(self, layer):
        if layer:
            categories = []

            symbol_visible = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol_visible.setColor(QColor("green"))
            categories.append(QgsRendererCategory(1, symbol_visible, "Visível"))

            symbol_invisible = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol_invisible.setColor(QColor("red"))
            categories.append(QgsRendererCategory(0, symbol_invisible, "Não Visível"))

            renderer = QgsCategorizedSymbolRenderer("visible", categories)
            layer.setRenderer(renderer)

            QgsProject.instance().addMapLayer(layer)

    def check_inputs(self, dem_raster, lines_layer, feedback):
        messages = []

        if dem_raster.bandCount() != 1:
            messages.append("O raster de entrada não parece ser um MDE: possui mais de uma banda.")
        else:
            provider = dem_raster.dataProvider()
            band_type = provider.dataType(1)
            if band_type not in [Qgis.Float32, Qgis.Float64,
                                 Qgis.Int16, Qgis.Int32,
                                 Qgis.UInt16, Qgis.UInt32]:
                messages.append("O raster não parece conter dados de elevação válidos (tipo incorreto).")

        if dem_raster.crs().isGeographic():
            messages.append("O CRS do raster é geográfico (lat/long). Reprojete para um CRS projetado.")

        if lines_layer.sourceCrs().isGeographic():
            messages.append("O CRS da camada vetorial é geográfico (lat/long). Reprojete para um CRS projetado.")

        if dem_raster.crs() != lines_layer.sourceCrs():
            messages.append("O CRS da camada vetorial é diferente do CRS do raster. Reprojete os dados.")

        if not dem_raster.extent().contains(lines_layer.sourceExtent()):
            messages.append("A camada de linhas não está inteiramente dentro da extensão do raster.")

        if messages:
            for msg in messages:
                feedback.reportError(msg)
            return False

        return True

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return LineOfSight()

    def name(self):
        return 'lineofsight'

    def displayName(self):
        return self.tr("Linha de Visada")

    def group(self):
        return self.tr('Vetor e Raster')

    def groupId(self):
        return 'vetoreraster'

    def shortHelpString(self):
        return self.tr(
        "Este algoritmo gera linhas de visada a partir de uma camada vetorial "
        "de linhas e de um Modelo Digital de Elevação (MDE). "
        "Cada segmento é classificado como visível ou não visível, "
        "levando em consideração as alturas do observador e do alvo, "
        "bem como correções de curvatura da Terra e refração atmosférica.\n\n"
        "⚠ Importante: O algoritmo funciona apenas com dados em sistemas de coordenadas projetados.\n"
        "⚠ As cores das linhas (verde/vermelho) só são aplicadas em camada temporária em memória.\n\n"
        "Parâmetros de entrada:\n"
        "- MDE (raster projetado)\n"
        "- Camada de linhas (vetor projetado)\n"
        "- Altura do Observador acima do terreno\n"
        "- Altura do Alvo acima do terreno\n\n"
        "Saída:\n"
        "- Camada vetorial de linhas classificadas como visíveis (verde) ou não visíveis (vermelho)."
    )