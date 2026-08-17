# -*- coding: utf-8 -*-
"""
Ferramenta de mapa: clique numa ou mais feicoes de "origem" (bacias, ou
coletores de montante) e depois clique numa feicao de "destino" (o coletor)
para criar o vinculo. Suporta clicar varias origens antes de finalizar no
destino, exatamente o fluxo pedido: "vou clicando na bacia ou bacias e
clicando no coletor que ela cai".

Esc ou clique direito limpa a selecao pendente.
"""

from qgis.core import QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from .geo_utils import identificar_feicao


class VincularMapTool(QgsMapTool):
    def __init__(self, canvas, layer_origem, layer_destino, id_field_origem,
                 id_field_destino, on_vincular, status=None, rotulo_origem="origem",
                 rotulo_destino="destino"):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer_origem = layer_origem
        self.layer_destino = layer_destino
        self.id_field_origem = id_field_origem
        self.id_field_destino = id_field_destino
        self.on_vincular = on_vincular
        self.status = status  # callback(str) para status persistente na tela
        self.rotulo_origem = rotulo_origem
        self.rotulo_destino = rotulo_destino

        self.pendentes_ids = []   # ids (valor do campo) das origens marcadas
        self.pendentes_fids = []  # ids internos (fid) para sincronizar selecao da camada

        self.rubber_origem = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_origem.setColor(QColor(255, 165, 0, 150))
        self.rubber_origem.setWidth(3)

        self.rubber_destino = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_destino.setColor(QColor(0, 120, 255, 150))
        self.rubber_destino.setWidth(3)

        self._mostrar_instrucoes_iniciais()

    # ------------------------------------------------------------ status ----
    def _mostrar_instrucoes_iniciais(self):
        self._status(
            f"Clique na(s) {self.rotulo_origem} desejada(s) e depois clique "
            f"no(a) {self.rotulo_destino}. | Selecionadas: 0"
        )

    def _status(self, texto):
        if self.status:
            self.status(texto)

    # -------------------------------------------------------- identificar ----
    def _identificar(self, layer, ponto_mapa):
        return identificar_feicao(self.canvas, layer, ponto_mapa)

    # ------------------------------------------------------------- eventos ----
    def canvasReleaseEvent(self, event):
        ponto_mapa = self.toMapCoordinates(event.pos())

        if event.button() == Qt.RightButton:
            self._limpar_pendentes()
            self._status("Selecao pendente limpa. | Selecionadas: 0")
            return

        if event.button() != Qt.LeftButton:
            return

        feicao_destino = self._identificar(self.layer_destino, ponto_mapa)
        feicao_origem = self._identificar(self.layer_origem, ponto_mapa)

        # se ja ha pendentes e o clique caiu sobre uma feicao de destino
        # (diferente das ja marcadas como origem), finaliza o vinculo
        if self.pendentes_ids and feicao_destino is not None and (
            self.layer_origem.id() != self.layer_destino.id() or
            feicao_destino.attribute(self.id_field_destino) not in self.pendentes_ids
        ):
            destino_id = feicao_destino.attribute(self.id_field_destino)
            self.rubber_destino.setToGeometry(feicao_destino.geometry(), self.layer_destino)
            qtd = len(self.pendentes_ids)
            for origem_id in self.pendentes_ids:
                self.on_vincular(origem_id, destino_id)
            self._status(
                f"{qtd} vinculo(s) criado(s) -> destino '{destino_id}'. | Selecionadas: 0"
            )
            self._limpar_pendentes()
            return

        if feicao_origem is not None:
            origem_id = feicao_origem.attribute(self.id_field_origem)
            if origem_id not in self.pendentes_ids:
                self.pendentes_ids.append(origem_id)
                self.pendentes_fids.append(feicao_origem.id())
                self._atualizar_rubber_origem()
                self._atualizar_selecao_camada()
                self._status(
                    f"Clique na(s) {self.rotulo_origem} desejada(s) e depois clique "
                    f"no(a) {self.rotulo_destino} para vincular. "
                    f"(botao direito ou ESC limpa) | Selecionadas: {len(self.pendentes_ids)}"
                )
            return

        self._status(
            f"Nenhuma feicao encontrada nesse ponto. | Selecionadas: {len(self.pendentes_ids)}"
        )

    def _atualizar_rubber_origem(self):
        self.rubber_origem.reset(QgsWkbTypes.PolygonGeometry)
        for feicao in self.layer_origem.getFeatures():
            if feicao.attribute(self.id_field_origem) in self.pendentes_ids:
                self.rubber_origem.addGeometry(feicao.geometry(), self.layer_origem)

    def _atualizar_selecao_camada(self):
        """Seleciona de verdade as feicoes de origem pendentes (destaque
        nativo do QGIS, alem do retangulo laranja)."""
        self.layer_origem.selectByIds(self.pendentes_fids)

    def _limpar_pendentes(self):
        self.pendentes_ids = []
        self.pendentes_fids = []
        self.rubber_origem.reset(QgsWkbTypes.PolygonGeometry)
        self.rubber_destino.reset(QgsWkbTypes.PolygonGeometry)
        self.layer_origem.removeSelection()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._limpar_pendentes()
            self._status("Selecao pendente limpa. | Selecionadas: 0")

    def deactivate(self):
        self._limpar_pendentes()
        super().deactivate()
