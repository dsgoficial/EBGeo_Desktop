from qgis.PyQt.QtCore import Qt, QObject, QEvent

class _CloseGuard(QObject):
    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Close:
            enabled = self.plugin.settings.value("qgislight/enabled", "false") == "true"
            if enabled:
                try:
                    self.plugin.disable(store=True)
                except Exception as e:
                    self.plugin.log(f"Erro ao desativar antes de fechar: {e}", "warning")
            return False  
        return super().eventFilter(obj, event)