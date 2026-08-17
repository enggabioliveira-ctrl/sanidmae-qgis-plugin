# -*- coding: utf-8 -*-
"""
Vincular/desvincular bacia->coletor e coletor->coletor de jusante, aplicar
densidade nas bacias selecionadas, editar parametros globais/excecoes por
trecho, e definir declividade por trecho a partir de cotas.

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
    QgsPointXY,
    QgsGeometry,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsFeature,
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


class VinculosMixin:
    def _status_vinculo(self, texto):
        """Atualiza o status fixo no painel (nao some sozinho) e tambem
        manda uma mensagem rapida na barra do QGIS."""
        self.lbl_status_vinculo.setText(texto)
        self.iface.messageBar().pushMessage("saniDmae - DSES", texto, level=0, duration=2)

    def _ativar_vincular_bacia(self):
        if not self._checar_banco():
            self.btn_vincular_bacia.setChecked(False)
            return
        self.btn_vincular_coletor.setChecked(False)
        self.map_tool = VincularMapTool(
            self.canvas,
            self.layer_bacias,
            self.layer_coletores,
            self.campo_id_bacia,
            self.campo_id_coletor,
            on_vincular=self._on_vincular_bacia,
            status=self._status_vinculo,
            rotulo_origem="bacia(s)",
            rotulo_destino="coletor de destino",
        )
        self.canvas.setMapTool(self.map_tool)

    def _ativar_vincular_coletor(self):
        if not self._checar_banco():
            self.btn_vincular_coletor.setChecked(False)
            return
        self.btn_vincular_bacia.setChecked(False)
        self.map_tool = VincularMapTool(
            self.canvas,
            self.layer_coletores,
            self.layer_coletores,
            self.campo_id_coletor,
            self.campo_id_coletor,
            on_vincular=self._on_vincular_coletor,
            status=self._status_vinculo,
            rotulo_origem="coletor(es) de montante",
            rotulo_destino="coletor de jusante",
        )
        self.canvas.setMapTool(self.map_tool)

    def _on_vincular_bacia(self, bacia_id, coletor_id):
        self.db.set_bacia_coletor(bacia_id, coletor_id)

    def _on_vincular_coletor(self, coletor_id, coletor_destino_id):
        try:
            self.db.set_coletor_destino(coletor_id, coletor_destino_id)
        except ValueError as exc:
            QMessageBox.warning(self, "Aviso", str(exc))

    def _desvincular_bacias_selecionadas(self):
        if not self._checar_banco():
            return
        if self.layer_bacias is None:
            QMessageBox.warning(self, "Aviso", "Configure a camada de bacias primeiro (passo 1).")
            return
        selecionadas = self.layer_bacias.selectedFeatures()
        if not selecionadas:
            QMessageBox.information(
                self,
                "Info",
                "Selecione uma ou mais bacias na camada (clique, Ctrl+clique ou "
                "retangulo de selecao do QGIS) e clique neste botao de novo.",
            )
            return

        idx_col_destino = self.layer_bacias.fields().indexOf("COL_DEST")
        if idx_col_destino >= 0:
            self.layer_bacias.startEditing()

        for feicao in selecionadas:
            bacia_id = str(feicao.attribute(self.campo_id_bacia))
            self.db.remove_bacia_coletor(bacia_id)
            if idx_col_destino >= 0:
                self.layer_bacias.changeAttributeValue(feicao.id(), idx_col_destino, None)

        if idx_col_destino >= 0:
            self.layer_bacias.commitChanges()

        QMessageBox.information(
            self, "OK", f"{len(selecionadas)} bacia(s) desvinculada(s). Rode 'Calcular tudo' de novo para atualizar."
        )

    def _desvincular_coletores_selecionados(self):
        if not self._checar_banco():
            return
        if self.layer_coletores is None:
            QMessageBox.warning(self, "Aviso", "Configure a camada de coletores primeiro (passo 1).")
            return
        selecionadas = self.layer_coletores.selectedFeatures()
        if not selecionadas:
            QMessageBox.information(
                self,
                "Info",
                "Selecione um ou mais coletores na camada (clique, Ctrl+clique ou "
                "retangulo de selecao do QGIS) e clique neste botao de novo.",
            )
            return

        idx_jusante = self.layer_coletores.fields().indexOf("COL_JUSANT")
        if idx_jusante >= 0:
            self.layer_coletores.startEditing()

        for feicao in selecionadas:
            coletor_id = str(feicao.attribute(self.campo_id_coletor))
            self.db.remove_coletor_destino(coletor_id)
            if idx_jusante >= 0:
                self.layer_coletores.changeAttributeValue(feicao.id(), idx_jusante, None)

        if idx_jusante >= 0:
            self.layer_coletores.commitChanges()

        QMessageBox.information(
            self, "OK", f"{len(selecionadas)} coletor(es) desvinculado(s) do jusante. Rode 'Calcular tudo' de novo para atualizar."
        )

    # ----------------------------------------------------- densidade ----
    def _aplicar_densidade_selecao(self):
        if not self._checar_banco():
            return
        if self.layer_bacias is None:
            return
        selecionadas = self.layer_bacias.selectedFeatures()
        if not selecionadas:
            QMessageBox.information(
                self, "Info", "Selecione uma ou mais bacias na camada (ferramenta de selecao do QGIS)."
            )
            return

        texto = self.cb_densidade.currentText()
        try:
            hab_ha = float(texto.split("-")[-1].strip())
        except ValueError:
            hab_ha = None
        if self.sp_densidade_manual.value() > 0:
            hab_ha = self.sp_densidade_manual.value()

        if hab_ha is None:
            QMessageBox.warning(self, "Aviso", "Escolha uma densidade ou informe um valor manual.")
            return

        for feicao in selecionadas:
            bacia_id = feicao.attribute(self.campo_id_bacia)
            self.db.set_bacia_densidade(bacia_id, hab_ha)

        QMessageBox.information(
            self, "OK", f"Densidade {hab_ha} hab/ha aplicada a {len(selecionadas)} bacia(s)."
        )

    # -------------------------------------------------- micromedicao ----
    def _dialogo_mapear_colunas_csv(self, colunas):
        """Pede pro usuario indicar qual coluna do CSV e qual coisa (ID,
        X, Y, consumo), com um palpite automatico por nome, e o CRS das
        coordenadas do CSV."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Mapear colunas do CSV de micromedicao")
        form = QFormLayout(dlg)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)

        cb_id = QComboBox(); cb_id.addItems(colunas)
        cb_x = QComboBox(); cb_x.addItems(colunas)
        cb_y = QComboBox(); cb_y.addItems(colunas)
        cb_consumo = QComboBox(); cb_consumo.addItems(colunas)

        self._selecionar_campo_por_palavras(cb_id, ["id", "matricula", "imovel", "codigo"])
        self._selecionar_campo_por_palavras(cb_x, ["x", "longitude", "long", "lon", "este", "utm_e"])
        self._selecionar_campo_por_palavras(cb_y, ["y", "latitude", "lat", "norte", "utm_n"])
        self._selecionar_campo_por_palavras(
            cb_consumo, ["consumo", "vazao", "q", "l_s", "ls", "medido"]
        )

        form.addRow("Coluna do ID do imovel:", cb_id)
        form.addRow("Coluna de X (longitude/este):", cb_x)
        form.addRow("Coluna de Y (latitude/norte):", cb_y)
        form.addRow("Coluna de consumo (L/s):", cb_consumo)

        txt_epsg = QLineEdit(self.layer_bacias.crs().authid() if self.layer_bacias else "")
        txt_epsg.setToolTip(
            "Codigo EPSG do sistema de coordenadas dos pontos do CSV (ex: EPSG:4326 "
            "pra lat/lon, ou o mesmo codigo da camada de bacias). Se os pontos ja "
            "estiverem no mesmo CRS da camada de bacias, pode deixar como esta."
        )
        form.addRow("CRS das coordenadas do CSV:", txt_epsg)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        form.addRow(botoes)

        if dlg.exec_() != QDialog.Accepted:
            return None

        return (
            cb_id.currentText(),
            cb_x.currentText(),
            cb_y.currentText(),
            cb_consumo.currentText(),
            txt_epsg.text().strip(),
        )

    def _cruzar_pontos_com_bacias(self, pontos, epsg_pontos):
        """Descobre em qual bacia cada ponto cai (point-in-polygon),
        convertendo o CRS se necessario. Se um ponto cair em bacias
        sobrepostas, usa a de menor area (mesma regra ja usada pro clique
        no mapa). Retorna dict ponto_id -> bacia_id (ou None)."""
        crs_bacias = self.layer_bacias.crs()
        crs_pontos = QgsCoordinateReferenceSystem(epsg_pontos) if epsg_pontos else crs_bacias
        if not crs_pontos.isValid():
            crs_pontos = crs_bacias

        transform = None
        if crs_pontos != crs_bacias:
            try:
                transform = QgsCoordinateTransform(crs_pontos, crs_bacias, QgsProject.instance())
            except Exception:
                transform = None

        feicoes_bacias = list(self.layer_bacias.getFeatures())
        mapa = {}
        for p in pontos:
            pt = QgsPointXY(p["x"], p["y"])
            if transform is not None:
                try:
                    pt = transform.transform(pt)
                except Exception:
                    pass
            candidatas = []
            for feicao in feicoes_bacias:
                geom = feicao.geometry()
                if geom is not None and not geom.isEmpty() and geom.contains(pt):
                    candidatas.append(feicao)
            bacia_encontrada = None
            if candidatas:
                melhor = min(candidatas, key=lambda f: f.geometry().area())
                bacia_encontrada = str(melhor.attribute(self.campo_id_bacia))
            mapa[p["ponto_id"]] = bacia_encontrada
        return mapa

    def _criar_camada_pontos_micromedicao(self, pontos, mapa_bacia, epsg_pontos):
        """Cria uma camada de pontos (memoria) no mapa so pra conferencia
        visual - nao e usada pelo calculo (que le do banco .sqlite)."""
        try:
            crs_pontos = epsg_pontos or (self.layer_bacias.crs().authid() if self.layer_bacias else "EPSG:4326")
            uri = f"Point?crs={crs_pontos}&field=ponto_id:string&field=consumo_ls:double&field=bacia_id:string"
            layer = QgsVectorLayer(uri, "Pontos de micromedicao", "memory")
            provider = layer.dataProvider()
            feats = []
            for p in pontos:
                feat = QgsFeature(layer.fields())
                feat.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["x"], p["y"])))
                feat.setAttributes([p["ponto_id"], p["consumo_ls"], mapa_bacia.get(p["ponto_id"])])
                feats.append(feat)
            provider.addFeatures(feats)
            layer.updateExtents()
            QgsProject.instance().addMapLayer(layer)
        except Exception:
            pass  # camada de conferencia visual, nao essencial pro calculo

    def _importar_csv_micromedicao(self):
        if not self._checar_banco():
            return
        if self.layer_bacias is None:
            QMessageBox.warning(self, "Aviso", "Configure a camada de bacias primeiro (passo 1).")
            return

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Importar CSV de micromedicao", "", "CSV (*.csv)"
        )
        if not caminho:
            return

        try:
            with open(caminho, "r", encoding="utf-8-sig") as f:
                amostra = f.read(4096)
            delimitador = ";" if amostra.count(";") >= amostra.count(",") else ","
            with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
                leitor = csv.DictReader(f, delimiter=delimitador)
                colunas = leitor.fieldnames or []
                linhas = list(leitor)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao ler CSV", str(exc))
            return

        if not colunas or not linhas:
            QMessageBox.warning(self, "Aviso", "CSV vazio ou sem cabecalho.")
            return

        mapeamento = self._dialogo_mapear_colunas_csv(colunas)
        if mapeamento is None:
            return
        col_id, col_x, col_y, col_consumo, epsg_pontos = mapeamento

        pontos = []
        erros = 0
        for i, linha in enumerate(linhas):
            try:
                ponto_id = str(linha[col_id]).strip() or f"linha{i + 1}"
                x = float(str(linha[col_x]).replace(",", "."))
                y = float(str(linha[col_y]).replace(",", "."))
                consumo = float(str(linha[col_consumo]).replace(",", "."))
                pontos.append(
                    {"ponto_id": ponto_id, "x": x, "y": y, "consumo_ls": consumo, "bacia_id": None}
                )
            except (ValueError, KeyError):
                erros += 1

        if not pontos:
            QMessageBox.warning(self, "Aviso", "Nenhuma linha valida encontrada no CSV.")
            return

        self.db.substituir_pontos_micromedicao(pontos)
        mapa_bacia = self._cruzar_pontos_com_bacias(pontos, epsg_pontos)
        self.db.atualizar_bacia_dos_pontos(mapa_bacia)
        self._criar_camada_pontos_micromedicao(pontos, mapa_bacia, epsg_pontos)

        sem_bacia = sum(1 for v in mapa_bacia.values() if v is None)
        msg = f"{len(pontos)} ponto(s) importado(s) (nova importacao substitui a anterior)."
        if erros:
            msg += f" {erros} linha(s) ignorada(s) por erro de formato."
        if sem_bacia:
            msg += (
                f" Atencao: {sem_bacia} ponto(s) nao caiu em nenhuma bacia (fora dos "
                "limites ou CRS incorreto) - confira a camada 'Pontos de micromedicao' "
                "adicionada ao mapa."
            )
        QMessageBox.information(self, "OK", msg)
        if hasattr(self, "_atualizar_resumo"):
            self._atualizar_resumo()

    def _alternar_usar_micromedicao_selecao(self):
        if not self._checar_banco():
            return
        if self.layer_bacias is None:
            return
        selecionadas = self.layer_bacias.selectedFeatures()
        if not selecionadas:
            QMessageBox.information(
                self, "Info", "Selecione uma ou mais bacias na camada (ferramenta de selecao do QGIS)."
            )
            return

        soma_por_bacia = self.db.get_soma_consumo_por_bacia()
        sem_pontos = []
        for feicao in selecionadas:
            bacia_id = str(feicao.attribute(self.campo_id_bacia))
            self.db.set_bacia_usar_micromedicao(bacia_id, True)
            if bacia_id not in soma_por_bacia:
                sem_pontos.append(bacia_id)

        msg = f"{len(selecionadas)} bacia(s) marcada(s) para usar micromedicao no proximo calculo."
        if sem_pontos:
            amostra = ", ".join(sem_pontos[:5]) + ("..." if len(sem_pontos) > 5 else "")
            msg += (
                f" Atencao: {len(sem_pontos)} delas ainda nao tem pontos de consumo "
                f"associados ({amostra}) - vao usar vazao 0 ate importar os pontos certos."
            )
        QMessageBox.information(self, "OK", msg)

    def _desativar_micromedicao_selecao(self):
        if not self._checar_banco():
            return
        if self.layer_bacias is None:
            return
        selecionadas = self.layer_bacias.selectedFeatures()
        if not selecionadas:
            QMessageBox.information(
                self, "Info", "Selecione uma ou mais bacias na camada (ferramenta de selecao do QGIS)."
            )
            return
        for feicao in selecionadas:
            bacia_id = str(feicao.attribute(self.campo_id_bacia))
            self.db.set_bacia_usar_micromedicao(bacia_id, False)
        QMessageBox.information(
            self, "OK", f"{len(selecionadas)} bacia(s) voltaram a usar area/densidade."
        )

    # ----------------------------------------------------- parametros ----
    def _editar_parametros_globais(self):
        if not self._checar_banco():
            return
        parametros = self.db.get_parametros()

        dlg = QDialog(self)
        dlg.setWindowTitle("Parametros globais")
        form = QFormLayout(dlg)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        campos = {}
        rotulos = {
            "qf": "Consumo per capita qf (L/hab.dia)",
            "C": "Coef. de retorno C",
            "k1": "Coef. dia de maior consumo k1",
            "k2": "Coef. hora de maior consumo k2",
            "inclinacao": "Inclinacao S (%)",
            "lamina_relativa": "Lamina relativa f(h/D)",
            "rugosidade": "Rugosidade de Manning n",
            "c_inf": "Coef. de infiltracao Cinf (L/s/m)",
            "vazao_minima": "Vazao minima de projeto (L/s)",
            "razao_h_d": "Lamina relativa h/D p/ tensao trativa (0 a 1)",
            "peso_especifico": "Peso especifico do esgoto (N/m3)",
            "dn_minimo": "DN minimo de projeto (m) - ex: 0.15 = DN150",
            "n_pvc": "Rugosidade de Manning do PVC (so p/ velocidade final/critica)",
            "razao_h_d_reduzida": "Lamina reduzida quando vf>vc (0 a 1, padrao 0,50)",
            "espacamento_max_pv": "Espacamento maximo entre PVs (m)",
        }
        for chave, rotulo in rotulos.items():
            if chave == "inclinacao":
                valor_pct = float(parametros.get(chave, 0.004)) * 100
                campo = QLineEdit(f"{valor_pct:.4f}")
                campo.setToolTip("Digitado e mostrado em % - internamente o calculo usa m/m.")
            else:
                campo = QLineEdit(str(parametros.get(chave, "")))
            campos[chave] = campo
            form.addRow(rotulo, campo)

        campo_formula = QLineEdit(str(parametros.get("formula_diametro", "")))
        form.addRow("Formula do diametro (Q,n,S,f):", campo_formula)
        campos["formula_diametro"] = campo_formula

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        form.addRow(botoes)

        if dlg.exec_() == QDialog.Accepted:
            for chave, campo in campos.items():
                texto = campo.text().strip()
                if chave == "inclinacao":
                    try:
                        valor_m_m = float(texto.replace(",", ".")) / 100.0
                    except ValueError:
                        continue
                    self.db.set_parametro(chave, valor_m_m)
                else:
                    self.db.set_parametro(chave, texto)

    def _editar_excecao_coletor(self):
        if not self._checar_banco():
            return
        if self.layer_coletores is None:
            return
        selecionadas = self.layer_coletores.selectedFeatures()
        if len(selecionadas) != 1:
            QMessageBox.information(self, "Info", "Selecione exatamente um coletor na camada.")
            return
        coletor_id = selecionadas[0].attribute(self.campo_id_coletor)
        excecoes_atuais = self.db.get_excecoes(coletor_id)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Excecoes - coletor {coletor_id}")
        form = QFormLayout(dlg)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        campos = {}
        rotulos_exc = {
            "inclinacao": "Inclinacao S (%)",
            "lamina_relativa": "Lamina relativa f(h/D)",
            "rugosidade": "Rugosidade n",
        }
        for chave, rotulo in rotulos_exc.items():
            valor_atual = excecoes_atuais.get(chave)
            if chave == "inclinacao" and valor_atual is not None:
                texto_inicial = f"{float(valor_atual) * 100:.4f}"
            else:
                texto_inicial = str(valor_atual) if valor_atual is not None else ""
            campo = QLineEdit(texto_inicial)
            campo.setPlaceholderText("(vazio = usa o parametro global)")
            campos[chave] = campo
            form.addRow(rotulo, campo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        form.addRow(botoes)

        if dlg.exec_() == QDialog.Accepted:
            for chave, campo in campos.items():
                texto = campo.text().strip()
                if texto == "":
                    self.db.remove_excecao(coletor_id, chave)
                else:
                    try:
                        valor = float(texto.replace(",", "."))
                    except ValueError:
                        continue
                    if chave == "inclinacao":
                        valor = valor / 100.0
                    self.db.set_excecao(coletor_id, chave, valor)

    def _definir_declividade_por_trecho(self):
        """Percorre os coletores selecionados na camada, um por um, e abre
        uma caixinha pedindo a COTA DE INICIO e a COTA DE SAIDA de cada
        trecho. O comprimento e medido direto da geometria da rede, e a
        declividade media (%) e calculada sozinha:
            declividade = (cota_inicio - cota_final) / comprimento
        Salva a cota (pra poder reabrir/ajustar depois) e a declividade
        resultante como excecao de 'inclinacao' (convertida pra m/m)."""
        if not self._checar_banco():
            return
        if self.layer_coletores is None:
            QMessageBox.warning(self, "Aviso", "Configure a camada de coletores primeiro (passo 1).")
            return

        selecionados = self.layer_coletores.selectedFeatures()
        if not selecionados:
            QMessageBox.information(
                self,
                "Info",
                "Selecione um ou mais coletores na camada (clique, Ctrl+clique ou "
                "retangulo de selecao do QGIS) e clique neste botao de novo.",
            )
            return

        self._garantir_campos_resultado()
        total = len(selecionados)
        definidos = 0

        self.layer_coletores.startEditing()
        idx_cota_i = self.layer_coletores.fields().indexOf("COTA_INIC")
        idx_cota_f = self.layer_coletores.fields().indexOf("COTA_FIN")
        idx_compr = self.layer_coletores.fields().indexOf("COMPR_M")
        idx_declividade = self.layer_coletores.fields().indexOf("DECLIV_PCT")

        for i, feicao in enumerate(selecionados, start=1):
            coletor_id = str(feicao.attribute(self.campo_id_coletor))
            comprimento_m = calcular_comprimento_m(self.layer_coletores, feicao.geometry())

            cotas_salvas = self.db.get_cotas(coletor_id) or {}
            cota_inicio_ini = cotas_salvas.get("cota_inicio") or 0.0
            cota_final_ini = cotas_salvas.get("cota_final") or 0.0

            resultado = self._dialogo_cota_trecho(
                coletor_id, i, total, comprimento_m, cota_inicio_ini, cota_final_ini
            )
            if resultado is None:
                resposta = QMessageBox.question(
                    self,
                    "Parar?",
                    f"Trecho '{coletor_id}' pulado (sem alteracao). Continuar para os "
                    f"proximos {total - i} trecho(s) selecionado(s)?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if resposta == QMessageBox.No:
                    break
                continue

            cota_inicio, cota_final, declividade_m_m = resultado
            self.db.set_cotas(coletor_id, cota_inicio, cota_final, comprimento_m)
            self.db.set_excecao(coletor_id, "inclinacao", declividade_m_m)

            self.layer_coletores.changeAttributeValue(feicao.id(), idx_cota_i, cota_inicio)
            self.layer_coletores.changeAttributeValue(feicao.id(), idx_cota_f, cota_final)
            self.layer_coletores.changeAttributeValue(feicao.id(), idx_compr, comprimento_m)
            self.layer_coletores.changeAttributeValue(feicao.id(), idx_declividade, declividade_m_m * 100)

            definidos += 1

        self.layer_coletores.commitChanges()

        QMessageBox.information(
            self, "OK", f"Declividade definida para {definidos} de {total} trecho(s) selecionado(s)."
        )

    def _dialogo_cota_trecho(self, coletor_id, i, total, comprimento_m, cota_inicio_ini, cota_final_ini):
        """Mostra a caixinha de cota inicio/fim de UM trecho, com a
        declividade calculada ao vivo. Retorna (cota_inicio, cota_final,
        declividade_m_m) ou None se o usuario cancelar."""
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Declividade do trecho ({i}/{total})")
        form = QFormLayout(dlg)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)

        form.addRow(QLabel(f"<b>Coletor:</b> {coletor_id}"))

        lbl_comprimento = QLabel(f"{comprimento_m:.2f} m (medido da geometria da rede)")
        form.addRow("Comprimento do trecho:", lbl_comprimento)

        sp_inicio = QDoubleSpinBox()
        sp_inicio.setRange(-1000, 10000)
        sp_inicio.setDecimals(3)
        sp_inicio.setSuffix(" m")
        sp_inicio.setValue(cota_inicio_ini)
        form.addRow("Cota de inicio (montante):", sp_inicio)

        sp_final = QDoubleSpinBox()
        sp_final.setRange(-1000, 10000)
        sp_final.setDecimals(3)
        sp_final.setSuffix(" m")
        sp_final.setValue(cota_final_ini)
        form.addRow("Cota de saida (jusante):", sp_final)

        lbl_resultado = QLabel()
        lbl_resultado.setWordWrap(True)
        lbl_resultado.setStyleSheet("font-weight: bold;")
        form.addRow("Declividade media calculada:", lbl_resultado)

        def atualizar_resultado():
            delta = sp_inicio.value() - sp_final.value()
            if comprimento_m > 0:
                declividade_pct = (delta / comprimento_m) * 100
                texto = f"{declividade_pct:.4f} %"
                if delta < 0:
                    texto += "  (atencao: cota de saida maior que a de inicio - declividade negativa)"
                lbl_resultado.setText(texto)
            else:
                lbl_resultado.setText("N/A - comprimento do trecho e zero/invalido")

        sp_inicio.valueChanged.connect(atualizar_resultado)
        sp_final.valueChanged.connect(atualizar_resultado)
        atualizar_resultado()

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.accepted.connect(dlg.accept)
        botoes.rejected.connect(dlg.reject)
        form.addRow(botoes)

        # nao-modal: da pra continuar arrastando/dando zoom no mapa com a
        # janela aberta, pra conferir a cota do outro lado do trecho antes
        # de digitar. A janela tambem comeca num canto (nao no centro da
        # tela) pra atrapalhar menos a visualizacao do mapa.
        dlg.setWindowModality(Qt.NonModal)
        tela = self.canvas.screen().availableGeometry() if hasattr(self.canvas, "screen") else None
        if tela is not None:
            dlg.move(tela.right() - dlg.sizeHint().width() - 40, tela.top() + 60)
        dlg.show()
        loop = QEventLoop()
        dlg.finished.connect(loop.quit)
        loop.exec_()

        if dlg.result() != QDialog.Accepted:
            return None

        if comprimento_m <= 0:
            QMessageBox.warning(
                self,
                "Aviso",
                f"O trecho '{coletor_id}' tem comprimento zero ou invalido - nao da pra "
                "calcular a declividade a partir das cotas. Use 'Editar excecao do "
                "coletor' pra digitar a inclinacao direto, se precisar.",
            )
            return None

        cota_inicio = sp_inicio.value()
        cota_final = sp_final.value()
        declividade_m_m = (cota_inicio - cota_final) / comprimento_m
        return cota_inicio, cota_final, declividade_m_m

    # -------------------------------------------------------- calculo ----
