from qgis.PyQt import QtCore, QtWidgets
from qgis.gui import QgsMapToolEmitPoint, QgsVertexMarker
from qgis.core import QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPointXY
from . import mgrs
from . import utmLatLon

class CopyCoordTool(QgsMapToolEmitPoint):
    def __init__(self, iface, parent_widget, mgrs_precision=5, coord_format="MGRS"):
        super().__init__(iface.mapCanvas())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.parent_widget = parent_widget
        self.marker = None
        self.mgrs_precision = mgrs_precision  # precisão MGRS (1-5)
        self.coord_format = coord_format

    def activate(self):
        self.canvas.setCursor(QtCore.Qt.CrossCursor)

    def deactivate(self):
        self.removeMarker()
        self.canvas.unsetMapTool(self)
        if hasattr(self.parent_widget, 'CopyButton'):
            self.parent_widget.CopyButton.setDown(False)
        self.canvas.setCursor(QtCore.Qt.ArrowCursor)

    def canvasReleaseEvent(self, event):
        pt = self.toMapCoordinates(event.pos())
        srcCrs = self.canvas.mapSettings().destinationCrs()
        destCrs = QgsCoordinateReferenceSystem(4326)
        transform = QgsCoordinateTransform(srcCrs, destCrs, QgsProject.instance())
        pt4326 = transform.transform(pt)

        # Coordenadas em WGS84
        lat, lon = pt4326.y(), pt4326.x()

        try:
            coord_text = self.format_coord(lat, lon)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "", f"Erro ao converter coordenada: {e}", level=2, duration=3
            )
            self.deactivate()
            return

        # Copiar para clipboard
        QtWidgets.QApplication.clipboard().setText(coord_text)

        if self.coord_format == "CUSTOM":
            crs_name = self.parent_widget.projSelector.crs().description()
            label = f"{crs_name}"
        else:
            label = self.coord_format

        self.iface.messageBar().pushMessage(
            "", f"Coordenada {label} copiada: {coord_text}",
            level=0, duration=5
        )

        self.removeMarker()
        self.marker = QgsVertexMarker(self.canvas)
        self.marker.setCenter(pt)
        self.marker.setColor(QtCore.Qt.red)
        self.marker.setIconType(QgsVertexMarker.ICON_CROSS)
        self.marker.setIconSize(12)
        self.marker.setPenWidth(2)

        self.deactivate()

    def format_coord(self, lat, lon):
        """Formata coordenadas em diferentes sistemas"""
        if self.coord_format == "MGRS":
            return mgrs.toMgrs(lat, lon, self.mgrs_precision)
        elif self.coord_format == "UTM":
            zone_num, zone_letter, easting, northing = utmLatLon.latLon2UtmParameters(lat, lon)
            return f"{zone_num}{zone_letter} {int(easting)} {int(northing)}"
        elif self.coord_format == "Lat/Lon":
            return f"{lat:.6f}, {lon:.6f}"
        elif self.coord_format == "CUSTOM":
            try:
                # 1. pega o CRS selecionado no widget
                customCrs = self.parent_widget.projSelector.crs()
                srcCrs = QgsCoordinateReferenceSystem(4326)  
                transform = QgsCoordinateTransform(srcCrs, customCrs, QgsProject.instance())
                pt_custom = transform.transform(QgsPointXY(lon, lat))
                return f"{pt_custom.x():.3f} {pt_custom.y():.3f}"
            
            except Exception as e:
                self.iface.messageBar().pushMessage(
                    "", f"Erro ao converter para CRS custom: {e}", level=2, duration=3
                )
                self.deactivate()
                return
        else:
            raise ValueError(f"Formato não suportado: {self.coord_format}")

    def to_dms(self, lat, lon):
        """Converte decimal para graus/min/seg"""
        def dms(value, is_lat=True):
            degrees = int(abs(value))
            minutes = int((abs(value) - degrees) * 60)
            seconds = (abs(value) - degrees - minutes/60) * 3600
            hemi = 'N' if (value >= 0 and is_lat) else 'S' if is_lat else 'E' if value >= 0 else 'W'
            return f"{degrees}°{minutes}'{seconds:.2f}\"{hemi}"
        return f"{dms(lat, True)} {dms(lon, False)}"

    def removeMarker(self):
        if self.marker is not None:
            self.canvas.scene().removeItem(self.marker)
            self.marker = None


# --- função que pode ser chamada como slot pelo DockWidget ---
def activate_copy_tool(iface, parent_widget, mgrs_precision=5, coord_format="mgrs"):
    """Ativa a ferramenta de copiar coordenadas."""
    tool = CopyCoordTool(iface, parent_widget, mgrs_precision, coord_format)
    parent_widget.canvas.setMapTool(tool)
    if hasattr(parent_widget, 'CopyButton'):
        parent_widget.CopyButton.setDown(True)
