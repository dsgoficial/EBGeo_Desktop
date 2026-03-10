# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'layerselector.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel

_translate = QtCore.QCoreApplication.translate

class Ui_LayerSelector(object):
    def setupUi(self, LayerSelector):
        LayerSelector.setObjectName("LayerSelector")
        LayerSelector.resize(400, 153)
        self.verticalLayout = QtWidgets.QVBoxLayout(LayerSelector)
        self.verticalLayout.setObjectName("verticalLayout")
        self.label = QtWidgets.QLabel(LayerSelector)
        self.label.setObjectName("label")
        self.verticalLayout.addWidget(self.label)
        self.layerCombo = QgsMapLayerComboBox(LayerSelector)
        self.layerCombo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        self.layerCombo.setObjectName("layerCombo")
        self.verticalLayout.addWidget(self.layerCombo)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtWidgets.QDialogButtonBox(LayerSelector)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel|QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setCenterButtons(True)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(LayerSelector)
        self.buttonBox.accepted.connect(LayerSelector.accept)
        self.buttonBox.rejected.connect(LayerSelector.reject)
        QtCore.QMetaObject.connectSlotsByName(LayerSelector)

    def retranslateUi(self, LayerSelector):
        LayerSelector.setWindowTitle(_translate("LayerSelector", "Selecionar camada"))
        self.label.setText(_translate("LayerSelector", "Selecione a camada para tracar o perfil"))
