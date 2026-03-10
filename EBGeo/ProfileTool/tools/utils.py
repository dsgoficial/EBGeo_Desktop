# -*- coding: utf-8 -*-

import qgis

def isProfilable(layer):
    return (layer.type() == layer.LayerType.RasterLayer) or \
            (layer.type() == layer.LayerType.PluginLayer and layer.LAYER_TYPE == 'crayfish_viewer') or \
            (layer.type() == layer.LayerType.PluginLayer and layer.LAYER_TYPE == 'selafin_viewer') or \
            (layer.type() == layer.LayerType.VectorLayer and layer.geometryType() == qgis.core.QgsWkbTypes.GeometryType.PointGeometry)
