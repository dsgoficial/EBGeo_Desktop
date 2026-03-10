# -*- coding: utf-8 -*-

from qgis.PyQt import QtWidgets
from qgis import processing


class Frame(QtWidgets.QWidget):

    def __init__(self, iface):
        super(Frame, self).__init__()
        '''Constructor'''
        processing.execAlgorithmDialog('EBGeoProvider:frame')

    def cancel(self):
        self.close()
