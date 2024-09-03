# -*- coding: utf-8 -*-
from .ebgeo import EBGeo
from .auxiliar import sunposition

def classFactory(iface):
    return EBGeo(iface)
