# -*- coding: utf-8 -*-
"""
Ferramentas de captura das 8 ferramentas militares do EBGeo Web.

As lineares seguem o gesto do Web: clique esquerdo acrescenta vértice, clique
direito acrescenta o ponto sob o cursor e finaliza, Backspace desfaz o último
vértice, Esc cancela. As pontuais criam o símbolo com um clique. O desenho em
si vem do estilo da camada; a ferramenta só grava o eixo e os atributos.
"""
import math
import uuid
from datetime import datetime, timezone

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsDistanceArea,
    QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsWkbTypes,
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor

from . import schema, zoom
from .calco import calco_ativo

DISTANCIA_MINIMA_M = {'arrow': 10.0}  # o Web rejeita vértice a menos de 5 m (10 m na seta)
WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')


def _distancia_m(p1, p2):
    da = QgsDistanceArea()
    da.setSourceCrs(WGS84, QgsProject.instance().transformContext())
    da.setEllipsoid('WGS84')
    return da.measureLine(p1, p2)


def _rumo_e_destino(p1, p2):
    """Rumo geodésico p1->p2 em graus e função destino(ponto, distância_m, rumo_graus)."""
    da = QgsDistanceArea()
    da.setSourceCrs(WGS84, QgsProject.instance().transformContext())
    da.setEllipsoid('WGS84')
    rumo = math.degrees(da.bearing(p1, p2))

    def destino(p, d, r):
        return da.computeSpheroidProject(p, d, math.radians(r))
    return rumo, destino


def atributos_iniciais(tipo, canvas):
    """Padrões do esquema mais os tamanhos que o Web calcula na criação a partir do zoom."""
    attrs = dict(schema.padroes(tipo))
    attrs['ebgeo_id'] = str(uuid.uuid4())
    agora = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    attrs['criado_em'] = agora
    attrs['atualizado_em'] = agora
    z, _lat = zoom.zoom_do_canvas(canvas)
    if z is not None and 'created_zoom' in schema.nomes_campos(tipo):
        attrs['created_zoom'] = z
    if z is not None:
        if tipo == 'coordination_line':
            s = zoom.tamanho_simbolo_linha_coordenacao_km(z)
            attrs['symbol_size_km'] = round(s, 4)
            attrs['symbol_spacing_km'] = round(3 * s, 4)
        elif tipo == 'boundary':
            attrs['symbol_size_km'] = round(zoom.tamanho_simbolo_limite_km(z), 4)
        elif tipo == 'arrow':
            attrs['width_m'] = round(zoom.largura_seta_m(z), 1)
        elif tipo == 'coordination_area':
            # _creationProperties do Web: 18 px na tela no zoom do clique que fecha a área
            from .estilos_area import tamanho_inicial_km
            attrs['symbol_size_km'] = tamanho_inicial_km(_lat, z)
    if tipo == 'coordination_area':
        from .estilos_area import posicao_padrao
        attrs['text_position'] = posicao_padrao(attrs.get('symbol_code'))
    return attrs


def gravar_feicao(layer, tipo, geometria_wgs84, atributos):
    """
    Grava a feição na camada. Tipos de símbolo pontual recebem o SVG gerado pelo motor.
    Se a camada já está em edição, entra no buffer (desfazível); senão, grava direto.
    Devolve o ebgeo_id gravado (ou None em falha).
    """
    attrs = dict(atributos)
    if schema.TIPOS[tipo]['desenho'] == 'svg':
        try:
            from . import simbolos
            attrs.update(simbolos.renderizar(tipo, attrs))
        except Exception as e:  # motor ausente ou símbolo inválido: grava sem SVG
            from qgis.core import QgsMessageLog
            QgsMessageLog.logMessage('Símbolo sem SVG: {}'.format(e), 'EBGeo', Qgis.MessageLevel.Warning)
    if layer.crs() != WGS84:
        g = QgsGeometry(geometria_wgs84)
        g.transform(QgsCoordinateTransform(WGS84, layer.crs(), QgsProject.instance()))
    else:
        g = geometria_wgs84
    f = QgsFeature(layer.fields())
    # coluna JSON recebe o objeto: o texto viraria string JSON escapada no GeoPackage
    for nome, valor in schema.atributos_para_qgis(tipo, attrs).items():
        i = layer.fields().indexOf(nome)
        if i >= 0:
            f.setAttribute(i, valor)
    f.setGeometry(g)
    estava_editando = layer.isEditable()
    if not estava_editando:
        layer.startEditing()
    ok = layer.addFeature(f)
    if not estava_editando:
        ok = layer.commitChanges() and ok
    layer.triggerRepaint()
    return attrs.get('ebgeo_id') if ok else None


class _Base(QgsMapTool):
    feicaoCriada = pyqtSignal(object, str, str)  # layer, tipo, ebgeo_id

    def __init__(self, canvas, tipo, iface=None):
        super().__init__(canvas)
        self.tipo = tipo
        self.iface = iface
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _camada(self):
        c = calco_ativo()
        if c is None:
            if self.iface:
                self.iface.messageBar().pushWarning('EBGeo', 'Crie ou abra um calco antes de desenhar.')
            return None
        return c.camada(self.tipo)

    def _wgs(self, ponto_mapa):
        crs = self.canvas().mapSettings().destinationCrs()
        if crs == WGS84:
            return QgsPointXY(ponto_mapa)
        return QgsCoordinateTransform(crs, WGS84, QgsProject.instance()).transform(QgsPointXY(ponto_mapa))

    def _ponto_evento(self, e):
        """Ponto do evento com atração (snapping) quando ligada no projeto."""
        m = self.canvas().snappingUtils().snapToMap(e.pos())
        return m.point() if m.isValid() else self.toMapCoordinates(e.pos())


class FerramentaPonto(_Base):
    """Símbolo Militar, Medida de Coordenação, Símbolo de Engenharia, Declinação Magnética."""

    def __init__(self, canvas, tipo, iface=None, preparar_atributos=None):
        super().__init__(canvas, tipo, iface)
        self.preparar_atributos = preparar_atributos  # callable(tipo, ponto_wgs, attrs) -> attrs

    def canvasReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        layer = self._camada()
        if layer is None:
            return
        p = self._wgs(self._ponto_evento(e))
        attrs = atributos_iniciais(self.tipo, self.canvas())
        if self.preparar_atributos:
            attrs = self.preparar_atributos(self.tipo, p, attrs)
        eid = gravar_feicao(layer, self.tipo, QgsGeometry.fromPointXY(p), attrs)
        if eid is not None:
            self.feicaoCriada.emit(layer, self.tipo, eid)


class FerramentaLinha(_Base):
    """Linha de Limite, Linha de Coordenação, Seta e Frente Ocupada."""

    def __init__(self, canvas, tipo, iface=None):
        super().__init__(canvas, tipo, iface)
        self.vertices = []  # em coordenadas do mapa
        self.banda = None
        self.max_vertices = 2 if tipo == 'occupied_front' else None

    def _banda(self):
        if self.banda is None:
            self.banda = QgsRubberBand(self.canvas(), Qgis.GeometryType.Line)
            self.banda.setColor(QColor(255, 0, 0, 180))
            self.banda.setWidth(2)
        return self.banda

    def _atualizar(self, cursor=None):
        pts = list(self.vertices) + ([cursor] if cursor is not None else [])
        self._banda().reset(Qgis.GeometryType.Line)
        for p in pts:
            self._banda().addPoint(QgsPointXY(p), False)
        self._banda().updatePosition()
        # o reset() esconde a banda e o addPoint não a mostra de volta (medido no QGIS 4.0.0)
        self._banda().setVisible(len(pts) >= 2)
        self._banda().update()

    def _aceita(self, p):
        if not self.vertices:
            return True
        minimo = DISTANCIA_MINIMA_M.get(self.tipo, 5.0)
        return _distancia_m(self._wgs(self.vertices[-1]), self._wgs(p)) >= minimo

    def canvasMoveEvent(self, e):
        if self.vertices:
            self._atualizar(self._ponto_evento(e))

    def canvasReleaseEvent(self, e):
        p = self._ponto_evento(e)
        if e.button() == Qt.MouseButton.LeftButton:
            if self._aceita(p):
                self.vertices.append(p)
            if self.max_vertices and len(self.vertices) >= self.max_vertices:
                self.finalizar()
            else:
                self._atualizar()
        elif e.button() == Qt.MouseButton.RightButton:
            if self._aceita(p):
                self.vertices.append(p)
            self.finalizar()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.cancelar()
            e.accept()
        elif e.key() == Qt.Key.Key_Backspace and self.vertices:
            self.vertices.pop()
            self._atualizar()
            e.accept()

    def cancelar(self):
        self.vertices = []
        if self.banda is not None:
            self.banda.reset(Qgis.GeometryType.Line)

    def deactivate(self):
        self.cancelar()
        super().deactivate()

    def geometria_wgs(self, vertices_mapa):
        pts = [self._wgs(p) for p in vertices_mapa]
        if self.tipo == 'occupied_front':
            # o Web nasce o terceiro ponto a rumo(p1->p2)+50 graus, à mesma distância
            p1, p2 = pts[0], pts[1]
            rumo, destino = _rumo_e_destino(p1, p2)
            p3 = destino(p1, _distancia_m(p1, p2), rumo + 50.0)
            pts = [p1, p2, QgsPointXY(p3)]
        g = QgsGeometry.fromPolylineXY(pts)
        if schema.TIPOS[self.tipo]['geometria'] == 'MultiLineString':
            g.convertToMultiType()
        return g

    def finalizar(self):
        verts = list(self.vertices)
        self.cancelar()
        if len(verts) < 2:
            return
        layer = self._camada()
        if layer is None:
            return
        attrs = atributos_iniciais(self.tipo, self.canvas())
        eid = gravar_feicao(layer, self.tipo, self.geometria_wgs(verts), attrs)
        if eid is not None:
            self.feicaoCriada.emit(layer, self.tipo, eid)


class FerramentaPoligono(FerramentaLinha):
    """
    Área de Coordenação: o gesto do polígono comum do Web (clique acrescenta vértice, clique
    direito acrescenta o ponto sob o cursor e fecha, Backspace desfaz, Esc cancela), com a
    área inteira de pré-visualização. Fecha com 3 vértices ou mais.
    """

    def __init__(self, canvas, tipo, iface=None, preparar_atributos=None):
        super().__init__(canvas, tipo, iface)
        self.preparar_atributos = preparar_atributos  # callable(tipo, attrs) -> attrs

    def _banda(self):
        if self.banda is None:
            self.banda = QgsRubberBand(self.canvas(), Qgis.GeometryType.Polygon)
            self.banda.setColor(QColor(255, 0, 0, 180))
            self.banda.setFillColor(QColor(255, 0, 0, 40))
            self.banda.setWidth(2)
        return self.banda

    def _atualizar(self, cursor=None):
        pts = list(self.vertices) + ([cursor] if cursor is not None else [])
        self._banda().reset(Qgis.GeometryType.Polygon)
        for p in pts:
            self._banda().addPoint(QgsPointXY(p), False)
        self._banda().updatePosition()
        self._banda().setVisible(len(pts) >= 2)
        self._banda().update()

    def cancelar(self):
        self.vertices = []
        if self.banda is not None:
            self.banda.reset(Qgis.GeometryType.Polygon)

    def geometria_wgs(self, vertices_mapa):
        pts = [self._wgs(p) for p in vertices_mapa]
        g = QgsGeometry.fromPolygonXY([pts + [pts[0]]])
        g.convertToMultiType()
        return g

    def finalizar(self):
        verts = list(self.vertices)
        if len(verts) < 3:
            # o Web não fecha área com menos de 3 vértices: a captura continua
            self._atualizar()
            return
        self.cancelar()
        layer = self._camada()
        if layer is None:
            return
        attrs = atributos_iniciais(self.tipo, self.canvas())
        if attrs.get('created_zoom') is not None:
            # o Web mede os 18 px na latitude do primeiro vértice
            from .estilos_area import tamanho_inicial_km
            attrs['symbol_size_km'] = tamanho_inicial_km(self._wgs(verts[0]).y(), attrs['created_zoom'])
        if self.preparar_atributos:
            attrs = self.preparar_atributos(self.tipo, attrs)
        eid = gravar_feicao(layer, self.tipo, self.geometria_wgs(verts), attrs)
        if eid is not None:
            self.feicaoCriada.emit(layer, self.tipo, eid)
