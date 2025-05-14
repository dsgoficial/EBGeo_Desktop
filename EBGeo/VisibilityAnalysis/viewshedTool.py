from qgis.PyQt import QtGui, QtCore
from qgis import core, gui
from PyQt5.QtWidgets import QToolTip
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt, QPointF
from qgis.core import (QgsPointXY, QgsGeometry, QgsFeature, 
                      QgsProject, QgsWkbTypes, QgsCoordinateTransform, 
                      QgsPolygon, QgsPoint)
from qgis.gui import QgsMapTool, QgsRubberBand
import math
import sip

class ViewshedTool(QgsMapTool):
    def __init__(self, canvas, layer, observer_height_field_name):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.observer_height_field_name = observer_height_field_name
        # Estado da ferramenta
        self.phase = 0  # 0: esperando primeiro clique, 1: esperando segundo clique, 2: esperando terceiro clique
        self.center_point = None
        self.direction_point = None
        self.angle_point = None
        self.is_active = True
        
        # Configurando o RubberBand para visualização
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0, 40))
        self.rubber_band.setWidth(2)
        
        # Linha temporária para mostrar a direção
        self.temp_line = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.temp_line.setColor(QColor(0, 0, 255, 200))
        self.temp_line.setWidth(2)

        self.center_marker = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.center_marker.setColor(QColor(144, 238, 144))  # Verde claro
        self.center_marker.setWidth(5)

        self.permanent_center_markers = []
        
        # Configurações do setor circular
        self.num_segments = 30  # Número de segmentos no arco para suavidade

        
        # Conectar ao sinal de remoção de camadas
        QgsProject.instance().layersWillBeRemoved.connect(self.check_layer_removal)
    
    def is_layer_valid(self):
        """Verifica se a camada ainda é válida"""
        try:
            # sip.isdeleted verifica se o objeto C++ foi excluído
            if self.layer is None or sip.isdeleted(self.layer):
                return False
            return True
        except:
            return False
    
    def check_layer_removal(self, layer_ids):
        """Verifica se a camada associada está sendo removida"""
        try:
            if self.layer and self.layer.id() in layer_ids:
                self.is_active = False
                self.reset()
                self.deactivate()
        except:
            self.is_active = False
            self.reset()
        
    def reset(self):
        """Reseta a ferramenta para o estado inicial"""
        try:
            self.phase = 0
            self.center_point = None
            self.direction_point = None
            self.angle_point = None
            
            # Verificar se os objetos rubberbands ainda existem
            if hasattr(self, 'rubber_band') and self.rubber_band and not sip.isdeleted(self.rubber_band):
                self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            
            if hasattr(self, 'temp_line') and self.temp_line and not sip.isdeleted(self.temp_line):
                self.temp_line.reset(QgsWkbTypes.LineGeometry)
            
        except Exception as e:
            print(f"Erro ao resetar: {str(e)}")
        
    def canvasPressEvent(self, event):
        """Captura os eventos de clique no canvas"""
        # Verificar se a ferramenta ainda está ativa
        if not self.is_active:
            return
            
        # Verificar se a camada ainda é válida
        if not self.is_layer_valid():
            self.is_active = False
            self.reset()
            return
            
        try:
            point = self.toMapCoordinates(event.pos())
            
            if self.phase == 0:  # Primeiro clique - define o centro do setor
                self.center_point = point
                
                if hasattr(self, 'rubber_band') and self.rubber_band and not sip.isdeleted(self.rubber_band):
                    self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
                    self.rubber_band.addPoint(point)
                
                # Não adicionamos o marker para não destacar o primeiro vértice
                
                self.phase = 1
                
            elif self.phase == 1:  # Segundo clique - define a direção inicial
                self.direction_point = point
                
                if hasattr(self, 'temp_line') and self.temp_line and not sip.isdeleted(self.temp_line):
                    self.temp_line.reset(QgsWkbTypes.LineGeometry)
                    self.temp_line.addPoint(self.center_point)
                    self.temp_line.addPoint(point)
                
                self.phase = 2
                
            elif self.phase == 2:  # Terceiro clique - define o ângulo e cria o setor
                self.angle_point = point
                self.create_sector()
                self.reset()
        except Exception as e:
            print(f"Erro no canvasPressEvent: {str(e)}")
            self.reset()
        
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reset()
            return
        
    def textDistanceToolTip(self, txt, distance, event):
        txt = f"<b>Raio: {distance:.2f}{txt}</b>"
        QToolTip.showText(
            self.canvas.mapToGlobal(event.pos()),
            txt,
            self.canvas
        )
    
    def canvasMoveEvent(self, event):
        """Captura o movimento do mouse no canvas"""
        # Verificar se a ferramenta ainda está ativa
        if not self.is_active:
            return

        # Verificar se a camada ainda é válida
        if not self.is_layer_valid():
            self.is_active = False
            self.reset()
            return

        try:
            if self.phase == 0:
                return

            current_point = self.toMapCoordinates(event.pos())

            if self.phase == 1 and self.center_point:  # Mostrando linha do centro até a posição atual do mouse
                if hasattr(self, 'temp_line') and self.temp_line and not sip.isdeleted(self.temp_line):
                    self.temp_line.reset(QgsWkbTypes.LineGeometry)
                    self.temp_line.addPoint(self.center_point)
                    self.temp_line.addPoint(current_point)

                    distance = self.center_point.distance(current_point)
                    if self.layer.crs().isGeographic():
                        self.textDistanceToolTip("°", distance, event)
                    else:
                        self.textDistanceToolTip("m", distance, event)

            elif self.phase == 2:  # Pré-visualizando o setor circular
                # Atualiza o setor de visualização
                self.update_sector_preview(current_point)

                # Calcular o ângulo em graus para exibição
                if self.center_point and self.direction_point:
                    base_angle = self.calculate_angle(self.center_point, self.direction_point)
                    current_angle = self.calculate_angle(self.center_point, current_point)

                    if base_angle is not None and current_angle is not None:
                        # Calcular a diferença de ângulo
                        angle_diff = current_angle - base_angle

                        # Normalizar para -π a π
                        while angle_diff > math.pi:
                            angle_diff -= 2 * math.pi
                        while angle_diff < -math.pi:
                            angle_diff += 2 * math.pi

                        # Converter para graus (valor absoluto)
                        angle_degrees = abs(angle_diff) * 180 / math.pi

                        # Mostrar o tooltip com o ângulo exato, sem limites
                        txt = f"<b>Ângulo: {angle_degrees:.1f}°</b>"
                        QToolTip.showText(
                            self.canvas.mapToGlobal(event.pos()),
                            txt,
                            self.canvas,
                        )
        except Exception as e:
            print(f"Erro no canvasMoveEvent: {str(e)}")
    
    def create_sector(self):
        """Cria o polígono do setor circular e o adiciona à camada"""
        # Verificar se a ferramenta ainda está ativa
        if not self.is_active:
            return
            
        # Verificar se a camada ainda é válida
        if not self.is_layer_valid():
            self.is_active = False
            self.reset()
            return
            
        try:
            # Verificamos se todos os pontos necessários estão definidos
            if not self.center_point or not self.direction_point or not self.angle_point:
                print("Pontos incompletos para criar setor")
                self.reset()
                return
                
            # Cria a geometria do setor usando o ângulo definido pelo terceiro clique
            sector_geometry = self.calculate_sector_geometry(self.angle_point)
            if not sector_geometry:
                print("Falha ao calcular geometria do setor")
                self.reset()
                return
            
            # Não criamos marcador permanente para não destacar vértices
            
            # Cria a feature e a adiciona à camada
            feature = QgsFeature()
            feature.setGeometry(sector_geometry)
            
            # Se a camada tiver campos, inicialize-os com valores padrão
            if self.layer.fields().count() > 0:
                feature.setFields(self.layer.fields())
            
            # Adiciona a feature à camada
            self.layer.startEditing()
            self.add_feature(self.layer, feature)
            
            # Atualiza o canvas
            self.canvas.refresh()
        except Exception as e:
            print(f"Erro ao criar setor: {str(e)}")
        
        self.reset()
    
    def add_feature(self, layer, feature):
        try:
            # Verificar se a camada ainda é válida
            if not self.is_layer_valid():
                return 0
                
            # Método para adicionar a feição com formulário
            layer.beginEditCommand("new viewshed")
            attrDialog = gui.QgsAttributeDialog(layer, feature, False)
            attrDialog.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            attrDialog.setMode(int(gui.QgsAttributeForm.AddFeatureMode))
            res = attrDialog.exec_()
            if res == 0:
                layer.destroyEditCommand()
            else:
                layer.endEditCommand()
            return res
        except Exception as e:
            print(f"Erro ao adicionar feição: {str(e)}")
            return 0
    
    def update_sector_preview(self, current_point):
        """Atualiza a pré-visualização do setor circular"""
        # Verificar se a ferramenta ainda está ativa
        if not self.is_active:
            return
            
        try:
            # Verificamos se todos os pontos necessários estão definidos
            if not self.center_point or not self.direction_point or not current_point:
                return
                
            # Verificar se o rubberband ainda existe
            if not hasattr(self, 'rubber_band') or not self.rubber_band or sip.isdeleted(self.rubber_band):
                return
                
            # Calculamos os pontos do setor
            sector_points = self.calculate_sector_points(current_point)
            
            # Verificamos se os pontos foram calculados com sucesso
            if not sector_points:
                return
                
            # Atualizamos o rubber band
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            for point in sector_points:
                self.rubber_band.addPoint(point)
        except Exception as e:
            print(f"Erro ao atualizar preview: {str(e)}")
    
    def calculate_sector_points(self, angle_point):
        """Calcula os pontos que formam o setor circular com a linha azul tangente a uma das extremidades"""
        try:
            # Verificações explícitas para evitar erros
            if not self.center_point or not self.direction_point or not angle_point:
                return None

            # Calculando o raio com base na distância do centro ao ponto de direção
            radius = self.center_point.distance(self.direction_point)

            # Calculando o ângulo da linha azul (direção inicial)
            base_angle = self.calculate_angle(self.center_point, self.direction_point)
            if base_angle is None:
                return None

            # Calculando o ângulo do ponto do mouse em relação ao centro
            mouse_angle = self.calculate_angle(self.center_point, angle_point)
            if mouse_angle is None:
                return None

            # Calculando a diferença de ângulo (quanto o mouse está desviando da linha azul)
            angle_diff = mouse_angle - base_angle

            # Normalizando o ângulo para estar entre -π e π
            while angle_diff > math.pi:
                angle_diff -= 2 * math.pi
            while angle_diff < -math.pi:
                angle_diff += 2 * math.pi

            # A abertura do setor será baseada na diferença de ângulo (sem limites)
            opening_angle = abs(angle_diff)

            # Determinando o lado em que o setor estará baseado no sinal da diferença de ângulo
            if angle_diff > 0:
                # Mouse está à direita da linha azul, o setor estará à direita da linha
                start_angle = base_angle  # A linha azul é a borda esquerda do setor
                end_angle = base_angle + opening_angle
            else:
                # Mouse está à esquerda da linha azul, o setor estará à esquerda da linha
                start_angle = base_angle - opening_angle
                end_angle = base_angle  # A linha azul é a borda direita do setor

            # Lista para armazenar os pontos do setor
            sector_points = [self.center_point]  # Começa com o ponto central

            # Número de segmentos no arco para suavidade
            num_segments = 30

            # Adiciona pontos ao longo do arco
            angle_step = (end_angle - start_angle) / num_segments

            for i in range(num_segments + 1):
                angle = start_angle + i * angle_step
                x = self.center_point.x() + radius * math.cos(angle)
                y = self.center_point.y() + radius * math.sin(angle)
                sector_points.append(QgsPointXY(x, y))

            # Fecha o polígono retornando ao centro
            sector_points.append(self.center_point)

            return sector_points
        except Exception as e:
            print(f"Erro ao calcular pontos do setor: {str(e)}")
            return None
    
    def calculate_sector_geometry(self, angle_point):
        """Calcula a geometria do setor"""
        try:
            sector_points = self.calculate_sector_points(angle_point)
            if not sector_points:
                return None
            return QgsGeometry.fromPolygonXY([sector_points])
        except Exception as e:
            print(f"Erro ao calcular geometria do setor: {str(e)}")
            return None
    
    def calculate_angle(self, center, point):
        """Calcula o ângulo entre o eixo x e a linha formada pelo centro e o ponto"""
        try:
            if not center or not point:
                return None
                
            dx = point.x() - center.x()
            dy = point.y() - center.y()
            
            # Verifica se os valores são válidos para evitar NaN
            if dx == 0 and dy == 0:
                return 0
                
            return math.atan2(dy, dx)
        except Exception as e:
            print(f"Erro ao calcular ângulo: {str(e)}")
            return None
    
    def is_clockwise(self, center, dir_point, angle_point):
        """Determina se o terceiro ponto está no sentido horário em relação ao vetor direção"""
        try:
            if not center or not dir_point or not angle_point:
                return False
                
            # Vetor direção
            dir_x = dir_point.x() - center.x()
            dir_y = dir_point.y() - center.y()
            
            # Vetor para o ponto de ângulo
            angle_x = angle_point.x() - center.x()
            angle_y = angle_point.y() - center.y()
            
            # Produto vetorial para determinar se angle_point está à direita (clockwise) 
            # ou à esquerda (counter-clockwise) do vetor direção
            cross_product = dir_x * angle_y - dir_y * angle_x
            
            # Se o produto vetorial for negativo, o ponto está no sentido horário
            return cross_product < 0
        except Exception as e:
            print(f"Erro ao verificar sentido horário: {str(e)}")
            return False
    
    def deactivate(self):
        """Ativa quando a ferramenta é desativada"""
        try:
            self.is_active = False
            
            # Verificar se os objetos ainda existem antes de usá-los
            if hasattr(self, 'rubber_band') and self.rubber_band and not sip.isdeleted(self.rubber_band):
                self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
                
            if hasattr(self, 'temp_line') and self.temp_line and not sip.isdeleted(self.temp_line):
                self.temp_line.reset(QgsWkbTypes.LineGeometry)
                
            if hasattr(self, 'center_marker') and self.center_marker and not sip.isdeleted(self.center_marker):
                self.center_marker.reset(QgsWkbTypes.PointGeometry)
        
            # Limpa todos os marcadores centrais permanentes
            if hasattr(self, 'permanent_center_markers'):
                for marker in self.permanent_center_markers:
                    if marker and not sip.isdeleted(marker):
                        marker.reset()
                self.permanent_center_markers = []
            
            # Desconectar do sinal quando a ferramenta for desativada
            try:
                QgsProject.instance().layersWillBeRemoved.disconnect(self.check_layer_removal)
            except:
                pass
        except Exception as e:
            print(f"Erro ao desativar ferramenta: {str(e)}")
        
        try:
            super().deactivate()
        except:
            pass