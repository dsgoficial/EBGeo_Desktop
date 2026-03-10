# -*- coding: utf-8 -*-

"""
Gerador de Pontos por Quilometragem
Cria pontos ao longo de linhas com base em quilometragem inicial e intervalo definido
Funciona com qualquer sistema de coordenadas (geográfico ou projetado)
"""
import os

from qgis.PyQt.QtCore import QCoreApplication, QMetaType
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterFeatureSink,
                       QgsFeature,
                       QgsFeatureSink,
                       QgsGeometry,
                       QgsPointXY,
                       QgsWkbTypes,
                       QgsField,
                       QgsFields,
                       QgsProcessingException,
                       QgsDistanceArea,
                       QgsProject,
                       QgsCoordinateReferenceSystem,
                       QgsUnitTypes)
import math


class GeradorPontosQuilometragem(QgsProcessingAlgorithm):
    
    # Constantes para parâmetros
    INPUT = 'INPUT'
    KM_INICIAL_FIELD = 'KM_INICIAL_FIELD'
    KM_FINAL_FIELD = 'KM_FINAL_FIELD'
    NOME_FIELD = 'NOME_FIELD'
    INTERVALO = 'INTERVALO'
    OUTPUT = 'OUTPUT'
    
    def initAlgorithm(self, config=None):
        # Camada de entrada (linhas)
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Camada de linhas (rodovias)'),
                [QgsProcessing.TypeVectorLine]
            )
        )
        
        # Campo com KM inicial
        self.addParameter(
            QgsProcessingParameterField(
                self.KM_INICIAL_FIELD,
                self.tr('Campo com KM inicial'),
                None,
                self.INPUT,
                QgsProcessingParameterField.Numeric
            )
        )
        
        # Campo com KM final (opcional)
        self.addParameter(
            QgsProcessingParameterField(
                self.KM_FINAL_FIELD,
                self.tr('Campo com KM final (opcional)'),
                None,
                self.INPUT,
                QgsProcessingParameterField.Numeric,
                optional=True
            )
        )
        
        # Campo com nome da rodovia
        self.addParameter(
            QgsProcessingParameterField(
                self.NOME_FIELD,
                self.tr('Campo com nome da rodovia'),
                None,
                self.INPUT,
                QgsProcessingParameterField.String
            )
        )
        
        # Intervalo entre pontos
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INTERVALO,
                self.tr('Intervalo entre pontos (km)'),
                QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.001
            )
        )
        
        # Camada de saída
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Pontos por quilometragem')
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        # Obter parâmetros
        source = self.parameterAsSource(parameters, self.INPUT, context)
        km_inicial_field = self.parameterAsString(parameters, self.KM_INICIAL_FIELD, context)
        km_final_field = self.parameterAsString(parameters, self.KM_FINAL_FIELD, context) if self.KM_FINAL_FIELD in parameters else None
        nome_field = self.parameterAsString(parameters, self.NOME_FIELD, context)
        intervalo = self.parameterAsDouble(parameters, self.INTERVALO, context)
        
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        
        # Criar campos de saída
        fields = QgsFields()
        fields.append(QgsField('id', QMetaType.Type.Int))
        fields.append(QgsField('nome_rodovia', QMetaType.Type.QString))
        fields.append(QgsField('km', QMetaType.Type.Double))
        fields.append(QgsField('km_formatado', QMetaType.Type.QString))
        
        # Criar sink de saída
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, QgsWkbTypes.Point, source.sourceCrs()
        )
        
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        
        # Configurar medição de distância
        distance_calc = QgsDistanceArea()
        distance_calc.setSourceCrs(source.sourceCrs(), context.transformContext())
        
        # Usar elipsoide do projeto para cálculos geodésicos
        if QgsProject.instance().ellipsoid():
            distance_calc.setEllipsoid(QgsProject.instance().ellipsoid())
        else:
            # Usar WGS84 como padrão se não houver elipsoide definido
            distance_calc.setEllipsoid('EPSG:7030')
        
        # Informar qual método de cálculo será usado
        crs = source.sourceCrs()
        if crs.isGeographic():
            feedback.pushInfo('Sistema de coordenadas geográfico detectado - usando cálculos geodésicos')
        else:
            feedback.pushInfo('Sistema de coordenadas projetado detectado - usando cálculos planares com correção elipsoidal')
        
        # Processar feições
        total = 100.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()
        
        point_id = 1
        
        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break
            
            # Obter geometria primeiro para validar
            geom = feature.geometry()
            if geom.isEmpty() or geom.isNull():
                raise QgsProcessingException(
                    f'Erro: Feição {feature.id()} possui geometria nula ou vazia!'
                )
            
            # Obter valores dos campos
            km_inicial = feature[km_inicial_field]
            nome_rodovia = feature[nome_field]
            km_final_campo = None
            
            # Tentar obter KM final se o campo foi especificado
            if km_final_field:
                try:
                    km_final_campo = feature[km_final_field]
                    if km_final_campo is not None:
                        km_final_campo = float(km_final_campo)
                except (ValueError, TypeError, KeyError):
                    km_final_campo = None
                    feedback.pushWarning(f'KM final inválido na feição {feature.id()}, usando cálculo por distância')
            
            # Se KM inicial for None, usar 0
            if km_inicial is None:
                km_inicial = 0.0
                feedback.pushInfo(f'Feição {feature.id()}: KM inicial não definido, usando 0')
            else:
                # Tentar converter para float
                try:
                    km_inicial = float(km_inicial)
                except (ValueError, TypeError):
                    raise QgsProcessingException(
                        f'Erro: KM inicial inválido na feição {feature.id()}: "{km_inicial}"'
                    )
            
            # Para multipart, processar cada parte
            if geom.isMultipart():
                lines = geom.asMultiPolyline()
            else:
                lines = [geom.asPolyline()]
            
            for line_idx, line in enumerate(lines):
                # Validar linha (precisa ter pelo menos 2 pontos)
                if len(line) < 2:
                    feedback.pushWarning(
                        f'Linha {line_idx} na feição {feature.id()} tem menos de 2 pontos, pulando...'
                    )
                    continue
                
                # Calcular comprimento total da linha
                total_length = self.calculate_line_length(line, distance_calc, crs)
                
                # Converter para km
                total_length_km = total_length / 1000.0
                
                # Determinar KM final e fator de escala
                if km_final_campo is not None and km_final_campo > km_inicial:
                    # Usar KM final fornecido
                    km_final = km_final_campo
                    km_oficial = km_final - km_inicial
                    # Fator de escala para ajustar distâncias
                    fator_escala = km_oficial / total_length_km
                    feedback.pushInfo(
                        f'Feição {feature.id()}: Usando KM final fornecido. '
                        f'Distância real: {total_length_km:.3f} km, '
                        f'Distância oficial: {km_oficial:.3f} km, '
                        f'Fator de ajuste: {fator_escala:.4f}'
                    )
                else:
                    # Calcular KM final baseado na distância
                    km_final = km_inicial + total_length_km
                    fator_escala = 1.0
                
                feedback.pushDebugInfo(
                    f'Feição {feature.id()}: KM {km_inicial:.3f} até {km_final:.3f}'
                )
                
                # Calcular primeiro KM redondo
                if km_inicial % intervalo == 0:
                    primeiro_km = km_inicial
                else:
                    primeiro_km = km_inicial + (intervalo - (km_inicial % intervalo))
                
                # Gerar pontos apenas nos KMs redondos
                current_km = primeiro_km
                
                while current_km <= km_final:
                    # Calcular distância desde o início da linha
                    distance_from_start_km = current_km - km_inicial
                    
                    # Verificar se o ponto está dentro da linha
                    if distance_from_start_km >= 0:
                        # Ajustar distância real baseado no fator de escala
                        if fator_escala != 1.0:
                            # Distância real necessária para chegar no KM oficial
                            distance_real_km = distance_from_start_km / fator_escala
                        else:
                            distance_real_km = distance_from_start_km
                        
                        # Verificar se ainda está dentro da linha
                        if distance_real_km <= total_length_km:
                            # Calcular distância em metros
                            distance_from_start_m = distance_real_km * 1000
                            
                            # Interpolar ponto na linha
                            point = self.interpolate_point_by_distance(
                                line, distance_from_start_m, distance_calc, crs
                            )
                            
                            if point:
                                # Criar feição de ponto
                                feat = QgsFeature(fields)
                                feat.setGeometry(QgsGeometry.fromPointXY(point))
                                feat.setAttributes([
                                    point_id,
                                    nome_rodovia if nome_rodovia else '',
                                    float(current_km),
                                    f'KM {int(current_km)}'
                                ])
                                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                                point_id += 1
                                
                                feedback.pushDebugInfo(
                                    f'Ponto criado: {nome_rodovia} KM {current_km}'
                                )
                    
                    # Próximo KM redondo
                    current_km += intervalo
            
            # Atualizar progresso
            feedback.setProgress(int(current * total))
        
        # Informar total de pontos criados
        feedback.pushInfo(f'Total de pontos criados: {point_id - 1}')

        output_layer = context.getMapLayer(dest_id)

        if output_layer is not None:
            caminho_atual = os.path.dirname(os.path.realpath(__file__))
            pasta_estilos = os.path.join(caminho_atual, 'styles')
            path_qml = os.path.join(pasta_estilos, 'style_gerador_pontos_rodovia.qml')
            output_layer.loadNamedStyle(path_qml)
            output_layer.triggerRepaint()
            feedback.pushInfo('Estilo aplicado com sucesso!')
        else:
            feedback.pushWarning('Não foi possível aplicar o estilo: camada de saída não encontrada.')
            
        
        return {self.OUTPUT: dest_id}
    
    def calculate_line_length(self, line, distance_calc, crs):
        """
        Calcula o comprimento total de uma linha considerando o CRS
        Retorna distância em metros
        """
        total_length = 0
        
        if crs.isGeographic():
            # Para coordenadas geográficas, usar cálculo geodésico
            for i in range(len(line) - 1):
                total_length += distance_calc.measureLine(line[i], line[i + 1])
        else:
            # Para coordenadas projetadas, pode usar cálculo direto
            # mas ainda assim usar distance_calc para consistência
            for i in range(len(line) - 1):
                total_length += distance_calc.measureLine(line[i], line[i + 1])
        
        return total_length
    
    def interpolate_point_by_distance(self, line, target_distance, distance_calc, crs):
        """
        Interpola um ponto ao longo de uma linha baseado em distância (metros)
        Considera o sistema de coordenadas para cálculos precisos
        """
        if target_distance <= 0:
            return line[0]
        
        # Calcular distâncias acumuladas
        accumulated_distance = 0
        
        for i in range(len(line) - 1):
            # Calcular comprimento do segmento
            if crs.isGeographic():
                segment_length = distance_calc.measureLine(line[i], line[i + 1])
            else:
                segment_length = distance_calc.measureLine(line[i], line[i + 1])
            
            # Verificar se o ponto está neste segmento
            if accumulated_distance + segment_length >= target_distance:
                # Calcular razão dentro do segmento
                remaining_distance = target_distance - accumulated_distance
                
                if segment_length > 0:
                    ratio = remaining_distance / segment_length
                else:
                    ratio = 0
                
                # Interpolar coordenadas
                # Para coordenadas geográficas, a interpolação linear é uma aproximação
                # mas é suficiente para segmentos pequenos
                x = line[i].x() + (line[i + 1].x() - line[i].x()) * ratio
                y = line[i].y() + (line[i + 1].y() - line[i].y()) * ratio
                
                return QgsPointXY(x, y)
            
            accumulated_distance += segment_length
        
        # Se chegou aqui, retornar último ponto
        return line[-1]

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return GeradorPontosQuilometragem()

    def name(self):
        return 'geradorpontosquilometragem'

    def displayName(self):
        return self.tr("Gerador de Pontos por Quilometragem")

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'Rodovia'

    def shortHelpString(self):
        return self.tr("""
        Este algoritmo gera pontos ao longo de linhas (rodovias) com base em:
        - Quilometragem inicial de cada segmento
        - Quilometragem final (opcional) para distribuição precisa
        - Intervalo definido entre pontos
        - Direção da linha
        
        Retorna uma camada de pontos com:
        - ID sequencial
        - Nome da rodovia
        - Quilometragem calculada
        
        IMPORTANTE: 
        - Os pontos são gerados em valores redondos
        - Funciona com qualquer sistema de coordenadas (lat/long ou projetado)
        - Se KM final for fornecido, ajusta a distribuição dos pontos proporcionalmente
        - Se KM final não for fornecido, calcula baseado no comprimento real
        
        Ex: Se KM inicial = 75 e intervalo = 10, gera: 80, 90, 100...
        """)