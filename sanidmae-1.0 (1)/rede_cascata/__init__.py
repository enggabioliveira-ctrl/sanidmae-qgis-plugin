# -*- coding: utf-8 -*-
"""
Ponto de entrada do plugin. O QGIS chama classFactory() ao carregar o plugin.
"""


def classFactory(iface):
    from .rede_cascata import RedeCascataPlugin
    return RedeCascataPlugin(iface)
