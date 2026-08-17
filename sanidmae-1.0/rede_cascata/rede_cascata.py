# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction


class RedeCascataPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dockwidget = None
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icone = QIcon(os.path.join(self.plugin_dir, "icon.png"))
        self.action = QAction(icone, "saniDmae - DSES", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&saniDmae - DSES", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        self.iface.removePluginMenu("&saniDmae - DSES", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dockwidget is not None:
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget = None

    def run(self):
        if self.dockwidget is None:
            from .rede_cascata_dockwidget import RedeCascataDockWidget
            self.dockwidget = RedeCascataDockWidget(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
        self.dockwidget.show()
        self.dockwidget.raise_()
