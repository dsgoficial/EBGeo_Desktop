def classFactory(iface):
    from .simplify_interface import QGISLightPlugin
    return QGISLightPlugin(iface)