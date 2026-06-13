# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from typing import List
from dataclasses import MISSING, dataclass, field
import os
from qgis import processing
from qgis.PyQt.QtCore import QMetaType, QCoreApplication
from qgis.core import (QgsProcessing, QgsVectorFileWriter, QgsProcessingAlgorithm,
                       QgsProcessingParameterMultipleLayers, QgsCoordinateTransformContext,
                       QgsProcessingFeatureSourceDefinition,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterBoolean, QgsFields, QgsField,
                       QgsVectorLayer, QgsFeature, QgsWkbTypes
                       )


class MASACODEContext:
    def __init__(self, append_to_existing: bool):
        self.append_to_existing = append_to_existing
        self._files_created_this_run = set()

    def get_write_mode(self, output_file: str):
        file_exists = os.path.exists(output_file)
        if self.append_to_existing or output_file in self._files_created_this_run:
            self._files_created_this_run.add(output_file)
            return QgsVectorFileWriter.AppendToLayerAddFields if file_exists else QgsVectorFileWriter.CreateOrOverwriteFile
        self._files_created_this_run.add(output_file)
        return QgsVectorFileWriter.CreateOrOverwriteFile


class ConvertEDGV3Topo14ToMASACODE(QgsProcessingAlgorithm):
    INPUT = 'INPUT'
    KEEP_ATTRIBUTES = 'KEEP_ATTRIBUTES'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    APPEND_TO_EXISTING = 'APPEND_TO_EXISTING'

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterMultipleLayers(
                self.INPUT,
                self.tr('Camadas de entrada'),
                QgsProcessing.TypeVectorAnyGeometry
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.KEEP_ATTRIBUTES,
                self.tr('Manter atributos da modelagem original'),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr('Pasta para salvar os arquivos exportados')
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.APPEND_TO_EXISTING,
                self.tr('Adicionar feições a arquivos existentes (criação incremental)'),
                defaultValue=False,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        outputFolderPath = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        keepAttributes = self.parameterAsBool(parameters, self.KEEP_ATTRIBUTES, context)
        appendToExisting = self.parameterAsBool(parameters, self.APPEND_TO_EXISTING, context)
        inputLayers = self.parameterAsLayerList(parameters, self.INPUT, context)
        nInputs = len(inputLayers)
        if nInputs == 0:
            return {self.OUTPUT_FOLDER: 'Camadas vazias. Não foi possível converter os dados.'}
        
        masacode_context = MASACODEContext(appendToExisting)

        conversion_factory = {
            'cobter_vegetacao_a': CobterVegetacao(
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Polygon,
                context=masacode_context,
            ),
            'cobter_massa_dagua_a': EDGVClass(
                masacode=10004,
                output_file_name='Water',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Polygon,
                context=masacode_context,
            ),
            'cobter_area_edificada_a': EDGVClass(
                masacode=10003,
                output_file_name='Urban_Area',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Polygon,
                context=masacode_context,
            ),
            'cobter_area_construida_a': EDGVClass(
                masacode=10003,
                output_file_name='Urban_Area',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Polygon,
                context=masacode_context,
            ),
            'llp_localidade_p': EDGVClass(
                masacode=10003,
                output_file_name='Urban_Point',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Point,
                context=masacode_context,
            ),
            'elemnat_trecho_drenagem_l': TrechoDrenagem(
                output_file_name='River',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.LineString,
                context=masacode_context,
            ),
            'elemnat_elemento_fisiografico_l': ElementoFisiograficoL(
                output_file_name='Cliff',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.LineString,
                context=masacode_context,
            ),
            'infra_via_deslocamento_l': ViaDeslocamento(
                output_file_name='Road',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.LineString,
                context=masacode_context,
            ),
            'infra_elemento_viario_l': ElementoViario(
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.LineString,
                context=masacode_context,
            ),
            'elemnat_toponimo_fisiografico_natural_p': ToponimoFisiografico(
                output_file_name='Mountain',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.Point,
                context=masacode_context,
            ),
            'infra_ferrovia_l': EDGVClass(
                masacode=20006,
                output_file_name='Railroad',
                output_file_path=outputFolderPath,
                keep_input_attributes=keepAttributes,
                output_geom_type=QgsWkbTypes.LineString,
                context=masacode_context,
            ),
        }
        stepSize = 100 / nInputs
        for current, layer in enumerate(inputLayers):
            if feedback.isCanceled():
                break
            if layer.name() not in conversion_factory:
                continue
            if layer.featureCount() == 0:
                continue
            fixedLyr = processing.run(
                "native:dropmzvalues",
                {
                    'INPUT': layer,
                    'DROP_M_VALUES': True,
                    'DROP_Z_VALUES': True,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )['OUTPUT']
            fixedLyr = processing.run(
                "native:multiparttosingleparts",
                {
                    'INPUT': fixedLyr,
                    'OUTPUT': 'TEMPORARY_OUTPUT'
                }
            )['OUTPUT']
            conversion_factory[layer.name()].convertFeatures(
                fixedLyr, fixedLyr.getFeatures()
            )
            feedback.setProgress(current * stepSize)

        return {self.OUTPUT_FOLDER: 'Conversão concluída'}

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ConvertEDGV3Topo14ToMASACODE()

    def name(self):
        return 'convertedgv3tomasacode'

    def displayName(self):
        return self.tr('EDGV 3.0 Topo 1.4 para o formato MASACODE')

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'MASACODE'

    def shortHelpString(self):
        return self.tr("Converte camadas da EDGV 3.0 Topo 1.4 para o formato MASACODE")


@dataclass
class AbstractEDGVClass(ABC):
    output_file_path: str
    keep_input_attributes: bool
    output_geom_type: int
    output_file_name: str = MISSING
    masacode: int = MISSING
    context: MASACODEContext = None

    @abstractmethod
    def get_masacode(self, feature):
        pass

    def __post_init__(self):
        pass

    def get_output_fields(self, input_layer):
        fields = QgsFields()
        fields.append(QgsField('MASACODE', QMetaType.Type.Int))
        if not self.keep_input_attributes:
            return fields
        for f in input_layer.fields():
            fields.append(f)
        return fields

    def create_output_file_writer(self, output_fields, output_file, srs):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"
        options.actionOnExistingFile = self.context.get_write_mode(output_file)
        vectorFileWriter = QgsVectorFileWriter.create(
            output_file,
            output_fields,
            self.output_geom_type,
            srs,
            QgsCoordinateTransformContext(),
            options
        )
        return vectorFileWriter

    def convertFeature(self, feature: QgsFeature, output_fields) -> QgsFeature:
        masacode = self.get_masacode(feature)
        if masacode is None:
            return None
        newFeat = QgsFeature(output_fields)
        newFeat.setGeometry(feature.geometry())
        newFeat['MASACODE'] = masacode
        if not self.keep_input_attributes:
            return newFeat
        for f in feature.fields():
            field_name = f.name()
            if field_name not in self.output_field_names:
                continue
            newFeat[field_name] = feature[field_name]
        return newFeat

    def convertFeatures(self, input_layer, featureList: List[QgsFeature]) -> bool:
        output_fields = self.get_output_fields(input_layer)
        self.output_field_names = [f.name() for f in output_fields]
        output_file_writer = self.create_output_file_writer(
            output_fields=output_fields,
            output_file=os.path.join(self.output_file_path, f'{self.output_file_name}.shp'),
            srs=input_layer.crs(),
        )
        convertLambda = lambda x: self.convertFeature(x, output_fields)
        out = output_file_writer.addFeatures(
            list(filter(lambda x: x is not None, map(convertLambda, featureList)))
        )
        del output_file_writer


@dataclass
class EDGVClass(AbstractEDGVClass):
    def get_masacode(self, feature):
        return self.masacode


def _get_field(feature, field_name_lower):
    """Retorna o nome real do campo (case-insensitive) ou None."""
    for f in feature.fields():
        if f.name().lower() == field_name_lower:
            return f.name()
    return None


@dataclass
class CobterVegetacao(AbstractEDGVClass):
    masacode: int = 0
    output_file_name: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.tipo_map = {
            601: (10000, 'Forest'),
            602: (10000, 'Forest'),
            107: (10001, 'Plantation'),
            142: (10001, 'Plantation'),
            150: (10001, 'Plantation'),
            194: (10001, 'Plantation'),
            196: (10001, 'Plantation'),
            197: (10001, 'Plantation'),
            1296: (10001, 'Plantation'),
            301: (10002, 'Swamp'),
            1002: (10005, 'Sand'),
        }

    def get_masacode(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val in self.tipo_map:
            return self.tipo_map[tipo_val][0]
        return None

    def _get_output_file_name(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val in self.tipo_map:
            return self.tipo_map[tipo_val][1]
        return None

    def convertFeatures(self, input_layer, featureList: List[QgsFeature]) -> bool:
        output_fields = self.get_output_fields(input_layer)
        self.output_field_names = [f.name() for f in output_fields]
        writers = {}
        for feat in featureList:
            out_name = self._get_output_file_name(feat)
            if out_name is None:
                continue
            if out_name not in writers:
                out_file = os.path.join(self.output_file_path, out_name + '.shp')
                writers[out_name] = self.create_output_file_writer(
                    output_fields, out_file, input_layer.crs()
                )
            converted = self.convertFeature(feat, output_fields)
            if converted is not None:
                writers[out_name].addFeature(converted)
        for key in list(writers.keys()):
            writers[key] = None
        return True


@dataclass
class TrechoDrenagem(AbstractEDGVClass):
    masacode: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.conversion_map = {
            1: 21002,   # Permanente
            3: 21003,   # Temporário
        }
        self.default_value = 21002

    def get_masacode(self, feature):
        regime_field = _get_field(feature, 'regime')
        if regime_field is None:
            return None
        return self.conversion_map.get(feature[regime_field], self.default_value)


@dataclass
class ElementoFisiograficoL(AbstractEDGVClass):
    masacode: int = 0

    def get_masacode(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val in (8, 13):  # Escarpa, Falésia
            return 21000
        return None


@dataclass
class ViaDeslocamento(AbstractEDGVClass):
    masacode: int = 0

    def get_masacode(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val == 5:  # Arruamento
            return 20004
        if tipo_val in (3, 6):  # Caminho carroçável, Trilha ou Picada
            return 20001
        if tipo_val in (2, 4):  # Estrada/Rodovia, Auto-estrada
            jurisdicao_field = _get_field(feature, 'jurisdicao')
            if jurisdicao_field is None:
                return 20002
            jurisdicao_val = feature[jurisdicao_field]
            if jurisdicao_val == 0:  # Desconhecida
                return 20002
            elif jurisdicao_val in (1, 2):  # Federal, Estadual
                return 20003
            else:
                return 20001
        return None


@dataclass
class ElementoViario(AbstractEDGVClass):
    masacode: int = 0
    output_file_name: str = ''

    def __post_init__(self):
        super().__post_init__()
        self.tipo_map = {
            201: (20005, 'Bridge'),  # Ponte móvel
            202: (20005, 'Bridge'),  # Ponte pênsil
            203: (20005, 'Bridge'),  # Ponte fixa
            204: (20005, 'Bridge'),  # Ponte estaiada
            101: (20007, 'Tunnel'),  # Túnel
            102: (20007, 'Tunnel'),  # Passagem subterrânea
        }

    def get_masacode(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val in self.tipo_map:
            return self.tipo_map[tipo_val][0]
        return None

    def _get_output_file_name(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        tipo_val = feature[tipo_field]
        if tipo_val in self.tipo_map:
            return self.tipo_map[tipo_val][1]
        return None

    def convertFeatures(self, input_layer, featureList: List[QgsFeature]) -> bool:
        output_fields = self.get_output_fields(input_layer)
        self.output_field_names = [f.name() for f in output_fields]
        writers = {}
        for feat in featureList:
            out_name = self._get_output_file_name(feat)
            if out_name is None:
                continue
            if out_name not in writers:
                out_file = os.path.join(self.output_file_path, out_name + '.shp')
                writers[out_name] = self.create_output_file_writer(
                    output_fields, out_file, input_layer.crs()
                )
            converted = self.convertFeature(feat, output_fields)
            if converted is not None:
                writers[out_name].addFeature(converted)
        for key in list(writers.keys()):
            writers[key] = None
        return True


@dataclass
class ToponimoFisiografico(AbstractEDGVClass):
    masacode: int = 0

    def get_masacode(self, feature):
        tipo_field = _get_field(feature, 'tipo')
        if tipo_field is None:
            return None
        if feature[tipo_field] == 3:  # Montanha
            return 10007
        return None
