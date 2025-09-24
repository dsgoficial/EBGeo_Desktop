from qgis.PyQt.QtCore import QObject, QEvent
from qgis.PyQt.QtWidgets import QToolBar, QMenuBar
from qgis.gui import QgsMapCanvas
from qgis.core import QgsSettings
from Protector.protector import _CloseGuard

class HideToolbar(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.canvas = None
        self.toolbars = []
        self.active = False
        self.visible_toolbars = []
        self.mainwindow = self.iface.mainWindow()
        self.menu_bar = self.mainwindow.menuBar()  
        self.menu_visible = self.menu_bar.isVisible()
        self.settings = QgsSettings()
        self._close_guard = _CloseGuard(self)
        self.mainwindow.installEventFilter(self._close_guard)

    def unload(self):
        try:
            if self._close_guard:
                self.mainwindow.removeEventFilter(self._close_guard)
                self._close_guard.deleteLater()
                self._close_guard = None
        except Exception as e:
            print(f"Erro no unload do HideToolbar: {e}")

    def enable(self):
        self.canvas = self.iface.mapCanvas()
        self.toolbars = self.mainwindow.findChildren(QToolBar)
        self.visible_toolbars = [tb for tb in self.toolbars if tb.isVisible()]
        self.menu_visible = self.menu_bar.isVisible()

        self.canvas.installEventFilter(self)
        self.active = True
        self.settings.setValue("hidetoolbar/enabled", "true")

    def disable(self, store=False):
        if self.canvas and self.active:
            self.canvas.removeEventFilter(self)

        for tb in self.toolbars:
            if tb in self.visible_toolbars:
                tb.show()
            else:
                tb.hide()

        if self.menu_visible:
            self.menu_bar.show()
        else:
            self.menu_bar.hide()

        self.active = False
        self.visible_toolbars = []

        if store:
            self.settings.setValue("hidetoolbar/enabled", "false")

    def eventFilter(self, obj, event):
        if obj is self.canvas and self.active:
            if event.type() == QEvent.Enter:
                for tb in self.visible_toolbars:
                    tb.hide()
                self.menu_bar.hide()
            elif event.type() == QEvent.Leave:
                for tb in self.visible_toolbars:
                    tb.show()
                if self.menu_visible:
                    self.menu_bar.show()
        return False
