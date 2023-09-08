# -*- coding: utf-8 -*-
from .ebgeo import EBGeo

def classFactory(iface):
    return EBGeo(iface)
