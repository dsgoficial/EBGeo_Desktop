# -*- coding: utf-8 -*-

from qgis.PyQt import QtWidgets
from qgis import processing


class Mosaic(QtWidgets.QWidget):

    def __init__(self, iface):
        super(Mosaic, self).__init__()
        '''Constructor'''
        processing.execAlgorithmDialog('EBGeoProvider:mosaic')

    def cancel(self):
        self.close()
