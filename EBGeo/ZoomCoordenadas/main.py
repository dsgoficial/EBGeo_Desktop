from qgis.PyQt import QtWidgets, uic, QtGui
from qgis.PyQt.QtGui import QIcon, QKeySequence
from qgis.PyQt.QtCore import Qt, QTimer, pyqtSlot
from qgis.gui import QgsVertexMarker, QgsRubberBand, QgsProjectionSelectionDialog
from qgis.core import QgsPointXY, QgsPoint, QgsRectangle, QgsCoordinateTransform, QgsProject, QgsWkbTypes, QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu, QDockWidget, QShortcut

from .zoomCoord_ui import Ui_ZoomDockWidgetBase  
from . import mgrs  
from .copyCoord import activate_copy_tool
from ZoomCoordenadas import utmLatLon
from .utmLatLon import dms_to_decimal
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'zoomCoord.ui'))

class ZoomToDockWidget(QtWidgets.QDockWidget, Ui_ZoomDockWidgetBase, FORM_CLASS):
    def __init__(self, iface, plugin, parent=None):
        # super().__init__(parent)
        super(ZoomToDockWidget, self).__init__()
        self.iface = iface
        self.plugin = plugin
        self.canvas = iface.mapCanvas()
        self.setupUi(self)
        
        shortcut = QShortcut(QKeySequence("Return"), self)
        shortcut.activated.connect(self.on_zoomToolButton_clicked)

        # Inicializa o marcador do ponto e o marcador da cruz como atributos
        self.point_marker = None

        self.SrcBox.clear()
        self.SrcBox.addItem("Lat/Lon", userData="Lat/Lon")
        self.SrcBox.addItem("UTM", userData="UTM")
        self.SrcBox.addItem("MGRS", userData="MGRS")
        self.SrcBox.addItem("Outros...", userData="CUSTOM")

    def closeEvent(self, event):
        # Quando o usuário fecha o dock, zera a referência no plugin
        if self.point_marker:
            self.canvas.scene().removeItem(self.point_marker)
            self.point_marker = None
        self.plugin.zoom_to = None
        super().closeEvent(event)


    def on_SrcBox_currentIndexChanged(self, text):
        if text == "UTM":
            self.coordTxt.clear()
            self.coordTxt.setPlaceholderText("Ex: 23S 683473 7464820")
            self.label.setText("Digite coordenadas UTM")
        elif text == "MGRS":
            self.coordTxt.clear()
            self.coordTxt.setPlaceholderText("Ex: 22J FQ 33813 87992")
            self.label.setText("Digite coordenadas MGRS")
        elif text == "Lat/Lon":
            self.coordTxt.clear()
            self.coordTxt.setPlaceholderText("Ex: -23.55783, -46.63290 (Decimal)   ou   30°07'24\"S, 51°14'04\"O (Grau, Min, Seg)")
            self.label.setText("Digite coordenadas Lat/Lon")
        elif text == "Outros...":
            self.coordTxt.clear()
            self.coordTxt.setPlaceholderText("Digite coordenadas no SRC escolhido")
            self.projSelector.setVisible(True)  # mostra o widget
            self.label.setText("Digite coordenadas")
        else:
            self.projSelector.setVisible(False)
            self.coordTxt.setPlaceholderText("")
            self.label.setText("")

    def zoom_to_mgrs(self):
        """Faz zoom para a coordenada MGRS digitada no widget, independente do CRS do canvas."""
        mgrs_text = self.coordTxt.text().strip()
        if not mgrs_text:
            QtWidgets.QMessageBox.warning(self, "Erro", "Digite uma coordenada MGRS!")
            return

        try:
            lat, lon = mgrs.toWgs(mgrs_text)
            srcCrs = QgsCoordinateReferenceSystem.fromEpsgId(4326) 
            destCrs = self.canvas.mapSettings().destinationCrs()  
            transform = QgsCoordinateTransform(srcCrs, destCrs, QgsProject.instance())
            pt_canvas = transform.transform(float(lon), float(lat))  
            self._zoom_to_point(pt_canvas)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Não foi possível fazer o zoom:\n{e}")

    def zoom_to_utm(self):
        text = self.coordTxt.text().strip()
        if utmLatLon.isUtm(text):
            pt = utmLatLon.utm2Point(text)  
            srcCrs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
            destCrs = self.canvas.mapSettings().destinationCrs()
            transform = QgsCoordinateTransform(srcCrs, destCrs, QgsProject.instance())
            pt_canvas = transform.transform(pt.x(), pt.y())
            self._zoom_to_point(pt_canvas)
        else:
            QtWidgets.QMessageBox.warning(self, "Erro", "Coordenada UTM inválida.")
        
    def zoom_to_latlon(self):
        text = self.coordTxt.text().strip()
        try:
            latlon = [s.strip() for s in text.split(',')]
            if len(latlon) != 2:
                raise ValueError("Formato inválido")

            try:
                # Tenta decimal
                lat = float(latlon[0])
                lon = float(latlon[1])
            except ValueError:
                # Tenta DMS multilingue
                lat = dms_to_decimal(latlon[0])
                lon = dms_to_decimal(latlon[1])

            srcCrs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
            destCrs = self.canvas.mapSettings().destinationCrs()
            transform = QgsCoordinateTransform(srcCrs, destCrs, QgsProject.instance())
            pt_canvas = transform.transform(lon, lat)

            self._zoom_to_point(pt_canvas)

        except Exception:
            QtWidgets.QMessageBox.warning(self, "Erro", "Coordenada Lat/Lon inválida.")

    def zoom_to_customCrs(self):
        text = self.coordTxt.text().strip()
        coords = [s.strip() for s in text.replace(",", " ").split()]
        if len(coords) != 2:
            QtWidgets.QMessageBox.warning(self, "Erro", "Digite no formato: X Y")
            return

        try:
            x = float(coords[0])
            y = float(coords[1])
            customCrs = self.projSelector.crs()
            destCrs = self.canvas.mapSettings().destinationCrs()
            transform = QgsCoordinateTransform(customCrs, destCrs, QgsProject.instance())
            pt_canvas = transform.transform(x, y)
            self._zoom_to_point(pt_canvas)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Não foi possível converter a coordenada:\n{e}")


    def _zoom_to_point(self, pt):
        """Centraliza o canvas e destaca o ponto."""
        self.canvas.setCenter(pt)
        
        current_scale = self.canvas.scale()
        if current_scale <= 10000000:
            self.canvas.zoomScale(current_scale)
        else:
            self.canvas.zoomScale(10000000)

        self._highlight(pt)
        self.canvas.refresh()


    def _highlight(self, point):
        self.remove_highlight()
        
        # Cria e configura o marcador de ponto (a bolinha vermelha)
        self.point_marker = QgsVertexMarker(self.canvas)
        self.point_marker.setCenter(point)
        self.point_marker.setColor(Qt.red)
        self.point_marker.setPenWidth(2)
        self.point_marker.show()
        
        # Se já existir um timer anterior, cancela
        if hasattr(self, "_highlight_timer") and self._highlight_timer.isActive():
            self._highlight_timer.stop()

        # Cria e guarda o timer para este highlight
        self._highlight_timer = QTimer()
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.timeout.connect(self.remove_highlight)
        self._highlight_timer.start(6000)

    def remove_highlight(self):
        """Remove o marcador do ponto e o marcador da cruz."""
        if self.point_marker:
            self.canvas.scene().removeItem(self.point_marker)
            self.point_marker = None
        

    @pyqtSlot()
    def on_zoomToolButton_clicked(self) -> None:
        src = self.SrcBox.currentText()
        if src == "MGRS":
            self.zoom_to_mgrs()
        elif src == "UTM":
            self.zoom_to_utm()
        elif src == "Lat/Lon":
            self.zoom_to_latlon()
        elif src == "Outros...":
            self.zoom_to_customCrs()


    @pyqtSlot(bool)
    def on_CopyButton_clicked(self):
        coord_format = self.SrcBox.currentData()
        activate_copy_tool(self.iface, self, coord_format=coord_format)
