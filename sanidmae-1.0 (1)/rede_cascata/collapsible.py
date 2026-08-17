# -*- coding: utf-8 -*-
"""
QGroupBox que pode ser recolhido/expandido clicando na caixinha do titulo,
escondendo o conteudo da secao. Util quando o painel do plugin fica
pequeno na tela e o usuario quer ver so os titulos das secoes, abrindo so
a que precisa no momento.
"""

from qgis.PyQt.QtWidgets import QGroupBox


class GrupoRecolhivel(QGroupBox):
    def __init__(self, titulo, parent=None):
        super().__init__(titulo, parent)
        self.setCheckable(True)
        self.setChecked(True)
        self.setStyleSheet(
            "QGroupBox { font-weight: bold; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 6px; padding: 0 3px; }"
        )
        self.toggled.connect(self._alternar_visibilidade)

    def _alternar_visibilidade(self, aberto):
        layout = self.layout()
        if layout is not None:
            self._alternar_layout(layout, aberto)
        # forca o recalculo de tamanho, senao a QScrollArea que envolve o
        # painel as vezes nao percebe que a altura total mudou
        self.updateGeometry()
        pai = self.parentWidget()
        if pai is not None:
            pai.updateGeometry()
            if pai.layout() is not None:
                pai.layout().activate()

    def _alternar_layout(self, layout, aberto):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(aberto)
            elif item.layout() is not None:
                self._alternar_layout(item.layout(), aberto)
