# -*- coding: utf-8 -*-
"""
Criar/abrir o banco de calculo (.sqlite), restaurar a configuracao salva
(camadas/campos usados da ultima vez) e garantir que os campos de resultado
existem nas camadas.

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


class BancoMixin:
    def _criar_novo_banco(self):
        self._abrir_banco(novo=True)

    def _abrir_banco_existente(self):
        self._abrir_banco(novo=False)

    def _abrir_banco(self, novo):
        projeto_path = QgsProject.instance().fileName()
        pasta_padrao = os.path.dirname(projeto_path) if projeto_path else os.path.expanduser("~")

        if novo:
            caminho, _ = QFileDialog.getSaveFileName(
                self,
                "Criar novo banco de calculo",
                os.path.join(pasta_padrao, "calculo_rede.sqlite"),
                "SQLite (*.sqlite)",
            )
        else:
            caminho, _ = QFileDialog.getOpenFileName(
                self, "Abrir banco de calculo existente", pasta_padrao, "SQLite (*.sqlite)"
            )
        if not caminho:
            return

        self.db = RedeDB(caminho)

        # tenta restaurar automaticamente quais camadas/campos foram usados
        # da ultima vez que esse banco foi salvo (assim nao precisa
        # reconfigurar o passo 1 toda vez que reabrir)
        config = self.db.get_config()
        relatorio_restauro = self._restaurar_config(config) if config else None

        self.layer_bacias = self._layer_por_combo(self.cb_layer_bacias)
        self.layer_coletores = self._layer_por_combo(self.cb_layer_coletores)
        self.campo_id_bacia = self.cb_campo_id_bacia.currentText()
        self.campo_id_coletor = self.cb_campo_id_coletor.currentText()
        self.campo_dn_existente = self.cb_campo_dn_existente.currentText()

        if not self.layer_bacias or not self.layer_coletores:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione a camada de bacias e de coletores. "
                "Se este banco ja tinha uma configuracao salva, confira se as "
                "camadas com aqueles nomes estao carregadas no projeto (use "
                "'Recarregar camadas do projeto' se acabou de adicionar alguma) "
                "e abra o banco de novo.",
            )
            return

        self.lbl_status_banco.setText(f"Banco aberto: {caminho}")

        # garante que os campos de resultado existem nas camadas
        self._garantir_campos_resultado()
        self._garantir_campos_bacia()

        self._salvar_config_atual()
        self._atualizar_resumo()

        if relatorio_restauro is not None:
            self._mostrar_relatorio_restauro(relatorio_restauro)

    def _selecionar_por_texto(self, combo, texto):
        """Seleciona o item do combo cujo texto bate com `texto`. Tenta
        primeiro correspondencia exata, depois exata ignorando
        maiusculas/minusculas e espacos nas pontas (cobre pequenas
        diferencas, tipo a camada ter sido renomeada com espacos extras)."""
        if not texto:
            return False

        idx = combo.findText(texto)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return True

        alvo = texto.strip().lower()
        for i in range(combo.count()):
            if combo.itemText(i).strip().lower() == alvo:
                combo.setCurrentIndex(i)
                return True

        return False

    def _restaurar_config(self, config):
        """Tenta restaurar cada item da configuracao salva e devolve um
        relatorio (lista de tuplas: rotulo, valor_salvo, conseguiu_ou_nao)
        pra mostrar pro usuario exatamente o que funcionou."""
        relatorio = []

        valor = config.get("layer_bacias_nome")
        ok_bacia = self._selecionar_por_texto(self.cb_layer_bacias, valor)
        relatorio.append(("Camada de bacias", valor, ok_bacia))
        if ok_bacia:
            valor_campo = config.get("campo_id_bacia")
            ok = self._selecionar_por_texto(self.cb_campo_id_bacia, valor_campo)
            relatorio.append(("Campo ID da bacia", valor_campo, ok))

        valor = config.get("layer_coletores_nome")
        ok_coletor = self._selecionar_por_texto(self.cb_layer_coletores, valor)
        relatorio.append(("Camada de coletores", valor, ok_coletor))
        if ok_coletor:
            valor_campo = config.get("campo_id_coletor")
            ok = self._selecionar_por_texto(self.cb_campo_id_coletor, valor_campo)
            relatorio.append(("Campo ID do coletor", valor_campo, ok))

            valor_campo = config.get("campo_dn_existente")
            ok = self._selecionar_por_texto(self.cb_campo_dn_existente, valor_campo)
            relatorio.append(("Campo DN existente", valor_campo, ok))

            unidade = config.get("unidade_dn")
            if unidade is not None:
                try:
                    self.cb_unidade_dn.setCurrentIndex(int(unidade))
                    relatorio.append(("Unidade do DN existente", unidade, True))
                except ValueError:
                    relatorio.append(("Unidade do DN existente", unidade, False))

        return relatorio

    def _mostrar_relatorio_restauro(self, relatorio):
        linhas = []
        algum_falhou = False
        for rotulo, valor_salvo, ok in relatorio:
            if ok:
                linhas.append(f"OK - {rotulo}: '{valor_salvo}'")
            else:
                algum_falhou = True
                linhas.append(
                    f"NAO ENCONTRADO - {rotulo}: '{valor_salvo}' "
                    "(confira se a camada/campo com esse nome existe no projeto atual)"
                )
        texto = "\n".join(linhas)
        if algum_falhou:
            QMessageBox.warning(
                self,
                "Restauracao parcial da configuracao salva",
                "Alguns itens da configuracao salva neste banco nao foram "
                "encontrados no projeto atual:\n\n" + texto,
            )
        else:
            self.iface.messageBar().pushMessage(
                "saniDmae - DSES",
                "Configuracao salva neste banco foi restaurada com sucesso.",
                level=0,
                duration=4,
            )

    def _salvar_config_atual(self):
        if self.db is None:
            return
        self.db.set_config("layer_bacias_nome", self.layer_bacias.name() if self.layer_bacias else "")
        self.db.set_config("campo_id_bacia", self.campo_id_bacia or "")
        self.db.set_config(
            "layer_coletores_nome", self.layer_coletores.name() if self.layer_coletores else ""
        )
        self.db.set_config("campo_id_coletor", self.campo_id_coletor or "")
        self.db.set_config("campo_dn_existente", self.campo_dn_existente or "")
        self.db.set_config("unidade_dn", self.cb_unidade_dn.currentIndex())

    def _garantir_campos(self, layer, campos):
        if layer is None:
            return
        nomes_existentes = [f.name() for f in layer.fields()]
        faltantes = [c for c in campos if c[0] not in nomes_existentes]
        if not faltantes:
            return
        layer.startEditing()
        for nome, tipo, _desc in faltantes:
            layer.addAttribute(QgsField(nome, tipo))
        layer.commitChanges()

        # alguns formatos (principalmente Shapefile .shp) truncam nomes de
        # campo com mais de 10 caracteres - se isso acontecer, o campo
        # criado fica com outro nome e o plugin ficaria tentando criar ele
        # de novo a cada calculo (gerando duplicatas vazias tipo CAMPO_1,
        # CAMPO_2...). Detecta e avisa em vez de deixar isso silencioso.
        nomes_apos = [f.name() for f in layer.fields()]
        truncados = [c[0] for c in faltantes if c[0] not in nomes_apos]
        if truncados:
            QMessageBox.warning(
                self,
                "Aviso - nomes de campo truncados",
                "A camada '" + layer.name() + "' truncou/alterou o nome de alguns "
                "campos que o plugin tentou criar: " + ", ".join(truncados) + ". "
                "Isso e comum em Shapefile (.shp), que limita nomes de campo a 10 "
                "caracteres. Os dados podem nao aparecer corretamente nos rotulos ate "
                "isso ser corrigido. Se possivel, prefira usar uma camada em GeoPackage "
                "(.gpkg) em vez de Shapefile para essa parte do projeto.",
            )

    def _garantir_campos_resultado(self):
        self._garantir_campos(self.layer_coletores, CAMPOS_RESULTADO)

    def _garantir_campos_bacia(self):
        self._garantir_campos(self.layer_bacias, CAMPOS_BACIA)

    # ------------------------------------------------------ vinculos ----
    def _checar_banco(self):
        if self.db is None:
            QMessageBox.warning(self, "Aviso", "Crie/abra o banco de calculo primeiro (passo 1).")
            return False
        return True

