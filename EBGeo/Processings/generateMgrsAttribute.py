# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import QCoreApplication, QMetaType
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsFeatureSink,
                       QgsFields,
                       QgsField,
                       QgsFeature,
                       QgsWkbTypes,
                       QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform)

from ..ZoomCoordenadas import mgrs


class GenerateMgrsAttribute(QgsProcessingAlgorithm):
    """Gera, para cada feição, a coordenada MGRS de um ponto representativo
    e a grava em um novo atributo de texto.

    Ponto representativo por tipo de geometria:
        - Ponto:    o próprio ponto (centróide se multiponto)
        - Linha:    o ponto médio (na metade do comprimento)
        - Polígono: point on surface (ponto interno garantido)
    """

    INPUT = 'INPUT'
    PRECISION = 'PRECISION'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Camada de entrada'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PRECISION,
                self.tr('Precisão MGRS (0=100km ... 5=1m)'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=5,
                minValue=0,
                maxValue=5,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Camada com atributo MGRS')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        precision = self.parameterAsInt(parameters, self.PRECISION, context)

        # Campos de saída = campos da entrada + campo MGRS (nome único)
        outFields = QgsFields()
        for f in source.fields():
            outFields.append(f)
        mgrsFieldName = self._unique_field_name('mgrs', source.fields())
        outFields.append(QgsField(mgrsFieldName, QMetaType.Type.QString))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            outFields,
            source.wkbType(),
            source.sourceCrs()
        )

        # Transformação para WGS84 (entrada do conversor MGRS)
        wgs84 = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        xform = QgsCoordinateTransform(source.sourceCrs(), wgs84, context.transformContext())

        count = source.featureCount()
        step = 100.0 / count if count else 0

        for current, feature in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break

            mgrsValue = None
            point = self._representative_point(feature.geometry())
            if point is None:
                feedback.pushWarning(
                    self.tr('Feição {}: geometria vazia/inválida, MGRS não gerado.').format(feature.id())
                )
            else:
                try:
                    ptWgs = xform.transform(point)
                    mgrsValue = mgrs.toMgrs(ptWgs.y(), ptWgs.x(), precision)
                except Exception as e:
                    feedback.pushWarning(
                        self.tr('Feição {}: não foi possível gerar MGRS ({}).').format(feature.id(), e)
                    )

            outFeat = QgsFeature(outFields)
            outFeat.setGeometry(feature.geometry())
            attrs = feature.attributes()
            attrs.append(mgrsValue)
            outFeat.setAttributes(attrs)
            sink.addFeature(outFeat, QgsFeatureSink.FastInsert)

            if step:
                feedback.setProgress(int((current + 1) * step))

        return {self.OUTPUT: dest_id}

    def _representative_point(self, geom):
        """Retorna um QgsPointXY representativo conforme o tipo de geometria,
        ou None se a geometria for vazia/inválida."""
        if geom is None or geom.isEmpty():
            return None
        gtype = geom.type()
        try:
            if gtype == QgsWkbTypes.GeometryType.PointGeometry:
                if geom.isMultipart():
                    return geom.centroid().asPoint()
                return geom.asPoint()
            if gtype == QgsWkbTypes.GeometryType.LineGeometry:
                length = geom.length()
                if length <= 0:
                    return geom.centroid().asPoint()
                mid = geom.interpolate(length / 2.0)
                if mid is None or mid.isEmpty():
                    return geom.centroid().asPoint()
                return mid.asPoint()
            if gtype == QgsWkbTypes.GeometryType.PolygonGeometry:
                pos = geom.pointOnSurface()
                if pos is None or pos.isEmpty():
                    return geom.centroid().asPoint()
                return pos.asPoint()
        except Exception:
            pass
        centroid = geom.centroid()
        if centroid is not None and not centroid.isEmpty():
            return centroid.asPoint()
        return None

    def _unique_field_name(self, base, fields):
        existing = {f.name().lower() for f in fields}
        if base.lower() not in existing:
            return base
        i = 1
        while '{}_{}'.format(base, i).lower() in existing:
            i += 1
        return '{}_{}'.format(base, i)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GenerateMgrsAttribute()

    def name(self):
        return 'generatemgrsattribute'

    def displayName(self):
        return self.tr('Gerar atributo MGRS')

    def group(self):
        return self.tr('Coordenadas')

    def groupId(self):
        return 'coordenadas'

    def shortHelpString(self):
        return self.tr(
            'Gera um atributo de texto com a coordenada MGRS de um ponto '
            'representativo de cada feição.\n\n'
            'Ponto representativo:\n'
            '• Ponto: o próprio ponto (centróide se multiponto)\n'
            '• Linha: o ponto médio\n'
            '• Polígono: point on surface\n\n'
            'A geometria original é preservada na saída.'
        )
