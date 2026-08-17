# -*- coding: utf-8 -*-
"""
Selecao de camada/campo: combos, auto-deteccao por nome, 'usar camada da arvore',
deteccao de unidade do DN existente, preview de densidade ao selecionar bacia.

Parte do RedeCascataDockWidget, dividido em mixins por assunto so pra
organizacao/leitura - continua sendo tudo a mesma classe/instancia em tempo
de execucao (ver rede_cascata_dockwidget.py, onde os mixins sao combinados).
"""
import csv
import os
from datetime import datetime

from qgis.core import (
    QgsProject,
    QgsField,
    QgsFeatureRequest,
    QgsSymbol,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBackgroundSettings,
    QgsVectorLayerSimpleLabeling,
    QgsProperty,
    QgsWkbTypes,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsMarkerLineSymbolLayer,
    QgsSymbolLayer,
    QgsCoordinateTransform,
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutItemLegend,
    QgsLayoutItemScaleBar,
    QgsLayoutItemLabel,
    QgsLayoutPoint,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import Qt, QVariant, QEventLoop, QRectF
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QInputDialog,
    QPlainTextEdit,
    QCheckBox,
)

from .db import RedeDB
from .calculo import calcular_tudo, calcular_vazao_bacia, ErroTopologia
from .maptool_link import VincularMapTool
from .geo_utils import calcular_area_ha, calcular_comprimento_m, nova_distance_area
from .collapsible import GrupoRecolhivel
from .constantes import CAMPOS_RESULTADO, CAMPOS_BACIA


class CamadasMixin:
    def _popular_combos_camadas(self):
        self.cb_layer_bacias.clear()
        self.cb_layer_coletores.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == layer.VectorLayer:
                self.cb_layer_bacias.addItem(layer.name(), layer.id())
                self.cb_layer_coletores.addItem(layer.name(), layer.id())

        # se ja tem um banco aberto com configuracao salva, ela tem
        # prioridade sobre o "chute" por palavra-chave - senao, toda vez
        # que o usuario clicasse em "Recarregar camadas do projeto" com o
        # banco ja aberto, a camada certa seria trocada pela adivinhada
        # (ex: "INTERCEPTORES-BACIAS E SUBBACIAS" tambem contem a palavra
        # "bacia" e podia vencer "SUBBACIAS_ESGOTO" sem avisar nada)
        ok_bacia = False
        ok_coletor = False
        if self.db is not None:
            config = self.db.get_config()
            if config:
                relatorio = self._restaurar_config(config)
                status = {rotulo: ok for rotulo, _valor, ok in relatorio}
                ok_bacia = status.get("Camada de bacias", False)
                ok_coletor = status.get("Camada de coletores", False)

        if not ok_bacia:
            self._selecionar_item_por_palavras(self.cb_layer_bacias, self.PALAVRAS_LAYER_BACIA)
        if not ok_coletor:
            self._selecionar_item_por_palavras(self.cb_layer_coletores, self.PALAVRAS_LAYER_COLETOR)

        self._on_layer_bacias_changed()
        self._on_layer_coletores_changed()

        if self.cb_densidade.count() == 0:
            densidades_iniciais = [
                "Residencial de luxo (lote 800 m2) - 100",
                "Residencial medio (lote 450 m2) - 120",
                "Misto popular (lote 250 m2) - 150",
                "Misto residencial/comercial central (predios 3-4 pav.) - 300",
            ]
            self.cb_densidade.addItems(densidades_iniciais)

    def _selecionar_item_por_palavras(self, combo, palavras_chave):
        """Escolhe automaticamente, no combo de CAMADAS, o item cujo nome
        bate com a primeira palavra-chave encontrada (ex: camada
        'SUBBACIAS_ESGOTO' bate com 'bacia')."""
        textos = [combo.itemText(i).lower() for i in range(combo.count())]
        for palavra in palavras_chave:
            for i, texto in enumerate(textos):
                if palavra in texto:
                    combo.setCurrentIndex(i)
                    return True
        return False

    def _selecionar_campo_por_palavras(self, combo, palavras_chave):
        """Mesma ideia, mas para os combos de CAMPO (colunas da tabela de
        atributos)."""
        textos = [combo.itemText(i).lower() for i in range(combo.count())]
        for palavra in palavras_chave:
            for i, texto in enumerate(textos):
                if palavra == texto or palavra in texto:
                    combo.setCurrentIndex(i)
                    return True
        return False

    def _popular_campos(self, combo_layer, combo_campo, palavras_chave=None):
        combo_campo.clear()
        layer = self._layer_por_combo(combo_layer)
        if layer is None:
            return
        for field in layer.fields():
            combo_campo.addItem(field.name())
        if palavras_chave:
            self._selecionar_campo_por_palavras(combo_campo, palavras_chave)

    def _on_layer_bacias_changed(self):
        self._popular_campos(
            self.cb_layer_bacias, self.cb_campo_id_bacia, self.PALAVRAS_CAMPO_ID_BACIA
        )
        self._reconectar_selecao_bacias()

    def _reconectar_selecao_bacias(self):
        """Escuta a selecao da camada de bacias pra, ao clicar numa bacia
        que ja tem densidade salva, mostrar esse valor na secao 3 em vez
        de deixar parecer que "resetou" pra 0."""
        layer_atual = self._layer_por_combo(self.cb_layer_bacias)
        anterior = getattr(self, "_layer_bacias_conectada", None)
        if anterior is not None and anterior is not layer_atual:
            try:
                anterior.selectionChanged.disconnect(self._ao_selecionar_bacia)
            except (TypeError, RuntimeError):
                pass
            self._layer_bacias_conectada = None

        if layer_atual is not None and layer_atual is not anterior:
            layer_atual.selectionChanged.connect(self._ao_selecionar_bacia)
            self._layer_bacias_conectada = layer_atual

    def _ao_selecionar_bacia(self, *_args):
        """Mostra a densidade ja salva da bacia selecionada (se so uma
        estiver selecionada e o banco estiver aberto)."""
        if self.db is None:
            return
        layer = self._layer_por_combo(self.cb_layer_bacias)
        if layer is None:
            return
        selecionadas = layer.selectedFeatures()
        if len(selecionadas) != 1:
            return
        bacia_id = str(selecionadas[0].attribute(self.campo_id_bacia))
        info = self.db.get_bacia_dados(bacia_id)
        if info and info.get("densidade_hab_ha") is not None:
            self.sp_densidade_manual.setValue(float(info["densidade_hab_ha"]))
            self.iface.messageBar().pushMessage(
                "saniDmae - DSES",
                f"Bacia '{bacia_id}' ja tem densidade salva: {info['densidade_hab_ha']} hab/ha.",
                level=0,
                duration=3,
            )
        else:
            self.sp_densidade_manual.setValue(0.0)

    def _on_layer_coletores_changed(self):
        self._popular_campos(
            self.cb_layer_coletores, self.cb_campo_id_coletor, self.PALAVRAS_CAMPO_ID_COLETOR
        )
        self._popular_campos(
            self.cb_layer_coletores, self.cb_campo_dn_existente, self.PALAVRAS_CAMPO_DN_EXISTENTE
        )
        self._sugerir_unidade_dn()

    def _sugerir_unidade_dn(self):
        """Amostra alguns valores do campo de DN existente e adivinha se
        esta em metros ou milimetros (diametro real de rede de esgoto:
        tipicamente 0.1-2 m, ou 100-2000 mm - a diferenca de escala e bem
        clara)."""
        layer = self._layer_por_combo(self.cb_layer_coletores)
        campo = self.cb_campo_dn_existente.currentText()
        if layer is None or not campo:
            return
        if layer.fields().indexOf(campo) < 0:
            return

        valores = []
        for i, feicao in enumerate(layer.getFeatures()):
            valor = feicao.attribute(campo)
            try:
                valores.append(float(valor))
            except (TypeError, ValueError):
                pass
            if i >= 300:  # amostra - nao precisa ler a camada inteira
                break

        if not valores:
            return
        valores.sort()
        mediana = valores[len(valores) // 2]
        self.cb_unidade_dn.setCurrentIndex(1 if mediana > 10 else 0)

    def _layer_por_combo(self, combo):
        layer_id = combo.currentData()
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    def _usar_camada_da_arvore(self, combo_alvo, rotulo):
        """Le a camada atualmente selecionada (destacada) no painel
        'Camadas' do QGIS e seleciona ela no combo. Muito mais confiavel
        que clicar no mapa (nao depende de CRS, zoom ou visibilidade)."""
        layer = self.iface.activeLayer()
        if layer is None:
            QMessageBox.information(
                self,
                "Info",
                f"Clique primeiro na camada de {rotulo} no painel 'Camadas' do QGIS "
                "(a arvore de camadas a esquerda) para ela ficar destacada/selecionada, "
                "e so entao clique neste botao.",
            )
            return

        idx = combo_alvo.findData(layer.id())
        if idx < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                f"A camada '{layer.name()}' esta selecionada na arvore, mas nao e uma "
                "camada vetorial valida (ou nao esta neste projeto). Escolha outra camada "
                "no painel 'Camadas' e clique de novo.",
            )
            return

        combo_alvo.setCurrentIndex(idx)
        self.iface.messageBar().pushMessage(
            "saniDmae - DSES", f"Camada de {rotulo} definida: {layer.name()}", level=0, duration=3
        )

    # ------------------------------------------------------- banco ----
