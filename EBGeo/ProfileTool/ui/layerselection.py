# -*- coding: utf-8 -*-

from qgis.PyQt import uic, QtWidgets
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.core import QgsMapLayer, QgsMapLayerProxyModel
import platform
import os
#from layerselector import Ui_LayerSelector

GUI, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'layerselector.ui'))

class LayerSelection(QtWidgets.QDialog, GUI):

	selected = pyqtSignal(QgsMapLayer)
	
	def __init__(self):
		super(LayerSelection, self).__init__()
		self.setupUi(self)
		self.buttonBox.clicked.connect(self.getSelectedLayer)
		self.layerCombo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
		
	def getSelectedLayer(self, b):
		if b == QDialogButtonBox.StandardButton.Ok:
			return self.layerCombo.currentLayer()
		else:
			return None
		
		self.close()