# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'dialog.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from qgis.PyQt import QtCore, QtGui, QtWidgets
from qgis.gui import QgsProjectionSelectionWidget

_translate = QtCore.QCoreApplication.translate

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(373, 186)
        Dialog.setMinimumSize(QtCore.QSize(373, 186))
        Dialog.setMaximumSize(QtCore.QSize(373, 186))
        Dialog.setSizeGripEnabled(False)
        Dialog.setModal(True)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setObjectName("label")
        self.verticalLayout_3.addWidget(self.label)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_2.addWidget(self.label_2)
        self.label_3 = QtWidgets.QLabel(Dialog)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_2.addWidget(self.label_3)
        self.label_4 = QtWidgets.QLabel(Dialog)
        self.label_4.setObjectName("label_4")
        self.verticalLayout_2.addWidget(self.label_4)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.latitudeEdit = QtWidgets.QLineEdit(Dialog)
        self.latitudeEdit.setPlaceholderText("")
        self.latitudeEdit.setObjectName("latitudeEdit")
        self.verticalLayout.addWidget(self.latitudeEdit)
        self.longitudeEdit = QtWidgets.QLineEdit(Dialog)
        self.longitudeEdit.setObjectName("longitudeEdit")
        self.verticalLayout.addWidget(self.longitudeEdit)
        self.projectionCombo = QgsProjectionSelectionWidget(Dialog)
        self.projectionCombo.setMinimumSize(QtCore.QSize(129, 0))
        self.projectionCombo.setObjectName("projectionCombo")
        self.verticalLayout.addWidget(self.projectionCombo)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_3.addLayout(self.horizontalLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.StandardButton.Cancel|QtWidgets.QDialogButtonBox.StandardButton.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout_3.addWidget(self.buttonBox)

        self.retranslateUi(Dialog)
        self.buttonBox.accepted.connect(Dialog.accept)
        self.buttonBox.rejected.connect(Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(_translate("Dialog", "Mover ponto"))
        self.label.setText(_translate("Dialog", "Digite as novas coordenadas do ponto"))
        self.label_2.setText(_translate("Dialog", "Latitude (Y)"))
        self.label_3.setText(_translate("Dialog", "Longitude (X)"))
        self.label_4.setText(_translate("Dialog", "SRC"))
        self.latitudeEdit.setInputMask(_translate("Dialog", "########.######; "))
        self.longitudeEdit.setInputMask(_translate("Dialog", "########.######; "))
