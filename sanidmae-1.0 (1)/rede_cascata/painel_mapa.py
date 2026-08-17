# -*- coding: utf-8 -*-
"""
Simbologia da rede (linha + marcadores de trecho + seta de sentido), resumo
textual do projeto, rotulos no mapa, geracao do layout de impressao de
apresentacao, e preenchimento da tabela de resultados do painel.

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


class MapaMixin:
    def _construir_simbolo_linha_com_marcadores(self, cor, largura_mm=0.6, marcador_mm=1.4):
        """Linha + um marcador circular no inicio e outro no fim de cada
        trecho (mostra onde um coletor termina e o proximo comeca) + uma
        seta no meio do trecho, rotacionada automaticamente conforme a
        direcao de digitalizacao da linha (que deve ser o sentido do
        escoamento: montante -> jusante)."""
        simbolo = QgsLineSymbol.createSimple(
            {"color": cor.name(), "width": str(largura_mm)}
        )

        marcador = QgsMarkerSymbol.createSimple(
            {
                "name": "circle",
                "color": "255,255,255,255",
                "outline_color": cor.name(),
                "outline_width": "0.35",
                "size": str(marcador_mm),
            }
        )

        camada_inicio = QgsMarkerLineSymbolLayer()
        camada_inicio.setPlacement(
            self._valor_enum(QgsMarkerLineSymbolLayer, "FirstVertex", "Placement")
        )
        camada_inicio.setSubSymbol(marcador.clone())
        simbolo.appendSymbolLayer(camada_inicio)

        camada_fim = QgsMarkerLineSymbolLayer()
        camada_fim.setPlacement(
            self._valor_enum(QgsMarkerLineSymbolLayer, "LastVertex", "Placement")
        )
        camada_fim.setSubSymbol(marcador.clone())
        simbolo.appendSymbolLayer(camada_fim)

        try:
            seta = QgsMarkerSymbol.createSimple(
                {
                    "name": "triangle",
                    "color": cor.name(),
                    "outline_color": cor.name(),
                    "outline_width": "0",
                    "size": str(marcador_mm * 3.0),
                }
            )
            # se a linha foi digitalizada ao contrario do fluxo real
            # (DIRECAO_OK = 0, calculado a partir do vinculo coletor ->
            # jusante), gira a seta 180 graus - sem precisar inverter a
            # geometria da camada original. O +90 deixa a seta perpendicular
            # ao coletor (em vez de alinhada/paralela a ele).
            try:
                propriedade_angulo = self._valor_enum(QgsSymbolLayer, "PropertyAngle", "Property")
                seta.symbolLayer(0).setDataDefinedProperty(
                    propriedade_angulo,
                    QgsProperty.fromExpression("if(\"DIRECAO_OK\" = 0, 270, 90)"),
                )
            except Exception:
                pass

            camada_seta = QgsMarkerLineSymbolLayer()
            camada_seta.setPlacement(
                self._valor_enum(QgsMarkerLineSymbolLayer, "LastVertex", "Placement")
            )
            camada_seta.setRotateMarker(True)  # gira a seta conforme a direcao da linha
            camada_seta.setOffsetAlongLine(0)  # exatamente em cima do ponto, sem deslocar
            camada_seta.setSubSymbol(seta.clone())
            simbolo.appendSymbolLayer(camada_seta)
        except Exception:
            pass  # sem a seta, mas com o resto da simbologia funcionando

        return simbolo

    def _aplicar_simbologia_criticos(self, apresentacao=False):
        layer = self.layer_coletores
        campo = "CRITICO"
        # no modo apresentacao os tracos/marcadores ficam menores, mais
        # discretos, melhor pra compor um mapa de apresentacao
        largura_mm = 0.4 if apresentacao else 0.6
        marcador_mm = 1.0 if apresentacao else 1.4

        try:
            simbolo_critico = self._construir_simbolo_linha_com_marcadores(
                QColor(220, 20, 20), largura_mm, marcador_mm
            )
            simbolo_ok = self._construir_simbolo_linha_com_marcadores(
                QColor(80, 80, 80), largura_mm, marcador_mm
            )
        except Exception:
            # se por algum motivo os marcadores falharem numa versao
            # diferente do QGIS, cai de volta pra linha simples (sem
            # marcador) em vez de deixar sem simbologia nenhuma
            simbolo_critico = QgsSymbol.defaultSymbol(layer.geometryType())
            simbolo_critico.setColor(QColor(220, 20, 20))
            simbolo_critico.setWidth(largura_mm)
            simbolo_ok = QgsSymbol.defaultSymbol(layer.geometryType())
            simbolo_ok.setColor(QColor(80, 80, 80))
            simbolo_ok.setWidth(largura_mm)

        categoria_critico = QgsRendererCategory(1, simbolo_critico, "Precisa trocar/melhorar")
        categoria_ok = QgsRendererCategory(0, simbolo_ok, "Atende")

        renderer = QgsCategorizedSymbolRenderer(campo, [categoria_ok, categoria_critico])
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def _on_modo_apresentacao_mudou(self):
        if self.layer_coletores is None:
            return
        # so reaplica se a camada ja tem os campos de resultado (ou seja,
        # ja rodou "Calcular tudo" pelo menos uma vez)
        if self.layer_coletores.fields().indexOf("CRITICO") >= 0:
            self._aplicar_simbologia_criticos(apresentacao=self.chk_apresentacao.isChecked())
        if self.layer_coletores.labelsEnabled() or (
            self.layer_bacias is not None and self.layer_bacias.labelsEnabled()
        ):
            self._ativar_rotulos_mapa()

    def _atualizar_resumo(self):
        if self.db is None:
            self.txt_resumo.setPlainText("Nenhum banco aberto.")
            return

        bacia_coletor_map = self.db.get_bacia_coletor_map()
        coletor_destino_map = self.db.get_coletor_destino_map()
        bacia_dados = self.db.get_all_bacia_dados()
        parametros = self.db.get_parametros()
        excecoes = self.db.get_all_excecoes()
        resultados = self.db.get_resultados()

        n_com_densidade = len(
            [b for b in bacia_dados.values() if b.get("densidade_hab_ha") is not None]
        )
        n_micromedicao = len([b for b in bacia_dados.values() if b.get("usar_micromedicao")])
        criticos = [r for r in resultados if r.get("critico")]
        fora_imin = [r for r in resultados if r.get("atende_declividade_minima") == 0]
        fora_tensao = [r for r in resultados if r.get("atende_tensao_trativa_calc") == 0]

        try:
            s_pct = float(parametros.get("inclinacao", 0)) * 100
        except (TypeError, ValueError):
            s_pct = 0.0

        linhas = [
            f"Banco: {os.path.basename(self.db.path)}",
            "",
            f"Bacias vinculadas a um coletor: {len(bacia_coletor_map)}",
            f"Bacias com densidade definida: {n_com_densidade}",
            f"Bacias usando micromedicao: {n_micromedicao}",
            f"Vinculos coletor -> jusante (cascata): {len(coletor_destino_map)}",
            f"Trechos com excecao de parametro: {len(excecoes)}",
            f"Coletores ja calculados: {len(resultados)} (criticos DN: {len(criticos)})",
            f"Fora da declividade minima NBR: {len(fora_imin)} | Fora da tensao trativa: {len(fora_tensao)}",
            "",
            "Parametros globais atuais:",
            f"  qf={parametros.get('qf','?')} L/hab.dia | C={parametros.get('C','?')} | "
            f"k1={parametros.get('k1','?')} | k2={parametros.get('k2','?')}",
            f"  Inclinacao padrao={s_pct:.3f}% | h/D={parametros.get('lamina_relativa','?')} | "
            f"n={parametros.get('rugosidade','?')}",
            f"  Cinf={parametros.get('c_inf','?')} L/s/m | Vazao minima={parametros.get('vazao_minima','?')} L/s",
        ]
        self.txt_resumo.setPlainText("\n".join(linhas))

    def _ativar_rotulos_mapa(self):
        try:
            aplicado_bacia = False
            aplicado_coletor = False

            if self.layer_bacias is not None:
                expressao_bacia = (
                    f"'{self.campo_id_bacia}: ' || \"{self.campo_id_bacia}\" || "
                    "'\\nDestino: ' || coalesce(\"COL_DEST\",'-') || "
                    "case when \"USA_MICRO\" = 1 "
                    "then '\\nMicromedicao: ' || coalesce(to_string(round(\"CONS_MICR\",3)),'-') || ' L/s' "
                    "else '\\nDens: ' || coalesce(to_string(\"DENS_HAB\"),'-') || ' hab/ha' end"
                )
                self._aplicar_rotulo(self.layer_bacias, expressao_bacia, QColor(30, 90, 30))
                aplicado_bacia = True

            if self.layer_coletores is not None:
                expressao_coletor = (
                    f"'{self.campo_id_coletor}: ' || \"{self.campo_id_coletor}\" || "
                    "'\\nJusante: ' || coalesce(\"COL_JUSANT\",'-') || "
                    "'\\nQ: ' || coalesce(to_string(round(\"VAZAO_ACM\",2)),'-') || ' L/s' || "
                    "'\\nDeclividade: ' || coalesce(to_string(round(\"S_USO_PCT\",3)),'-') || '%' || "
                    "'\\nDN calc: ' || coalesce(to_string(round(\"DN_CALC\",3)),'-') || ' m' || "
                    "'\\nDN adotado: ' || coalesce(to_string(round(\"DN_ADOT\",3)),'-') || ' m' || "
                    "'\\nDN exist: ' || coalesce(to_string(round(\"DN_EXIST_M\",3)),'-') || ' m' || "
                    "'\\nStatus: ' || coalesce(\"STATUS\",'-') || "
                    "'\\nNBR 9649: ' || "
                    "case when \"OK_IMIN\" = 0 then 'Imin! ' else '' end || "
                    "case when \"OK_TRATC\" = 0 then 'Tensao trativa! ' else '' end || "
                    "case when \"OK_VELC\" = 0 then 'Vel.critica! ' else '' end || "
                    "case when \"OK_ESPAC\" = 0 then 'Espacamento PV!' else '' end || "
                    "case when coalesce(\"OK_IMIN\",1) = 1 and coalesce(\"OK_TRATC\",1) = 1 "
                    "and coalesce(\"OK_VELC\",1) = 1 and coalesce(\"OK_ESPAC\",1) = 1 "
                    "then 'OK' else '' end"
                )
                # texto fica vermelho automaticamente nos trechos criticos,
                # igual a simbologia da linha (mesmo esquema de cor)
                expressao_cor = "if(\"CRITICO\" = 1, '#dc1414', '#14146e')"
                self._aplicar_rotulo(
                    self.layer_coletores, expressao_coletor, QColor(20, 20, 110), expressao_cor
                )
                aplicado_coletor = True

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Erro ao ativar rotulos",
                "Nao consegui ativar os rotulos. Detalhe do erro (pra me mandar se "
                f"precisar de ajuda):\n\n{type(exc).__name__}: {exc}",
            )
            return

        if not aplicado_bacia and not aplicado_coletor:
            QMessageBox.information(
                self, "Info", "Configure as camadas de bacias e coletores primeiro (passo 1)."
            )
            return

        self.iface.messageBar().pushMessage(
            "saniDmae - DSES",
            "Rotulos ativados: bacias (vinculo/densidade) e coletores (simulacao: "
            "jusante, vazao, DN calculado x existente, status).",
            level=0,
            duration=4,
        )

    def _valor_enum(self, classe, nome, sub_enum=None):
        """Pega um valor de enum do PyQGIS de um jeito compativel com
        varias versoes do QGIS - versoes mais novas exigem o enum aninhado
        (ex: QgsPalLayerSettings.Placement.Horizontal), versoes mais
        antigas aceitam direto na classe (ex: QgsPalLayerSettings.Horizontal).
        Tenta as duas formas antes de desistir."""
        if sub_enum:
            aninhado = getattr(classe, sub_enum, None)
            if aninhado is not None and hasattr(aninhado, nome):
                return getattr(aninhado, nome)
        if hasattr(classe, nome):
            return getattr(classe, nome)
        raise AttributeError(f"Nao encontrei '{nome}' em {classe} (nem direto nem em {sub_enum})")

    def _aplicar_rotulo(self, layer, expressao, cor_texto, expressao_cor=None):
        settings = QgsPalLayerSettings()
        settings.fieldName = expressao
        settings.isExpression = True
        settings.priority = 10

        # camadas de LINHA (coletores): em vez de deixar o QGIS escolher
        # onde encaixar o texto ao longo da linha (que muda de posicao
        # dependendo do zoom/espaco disponivel), forcamos o rotulo a
        # ficar sempre fixo no centroide (centro) da geometria, usando um
        # "gerador de geometria" - o rotulo passa a se comportar como se
        # fosse de um ponto fixo, e nao de uma linha.
        if layer.geometryType() == QgsWkbTypes.LineGeometry:
            settings.geometryGeneratorEnabled = True
            settings.geometryGenerator = "centroid($geometry)"
            settings.geometryGeneratorType = QgsWkbTypes.PointGeometry
            settings.placement = self._valor_enum(QgsPalLayerSettings, "OverPoint", "Placement")
        elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
            settings.placement = self._valor_enum(QgsPalLayerSettings, "OverPoint", "Placement")

        formato = QgsTextFormat()
        formato.setSizeUnit(QgsUnitTypes.RenderMapUnits)
        formato.setSize(10)  # em unidades do mapa (ex: metros, se a camada estiver em CRS metrico)
        formato.setColor(cor_texto)

        fundo = QgsTextBackgroundSettings()
        fundo.setEnabled(True)
        fundo.setFillColor(QColor(255, 255, 255, 210))
        formato.setBackground(fundo)

        settings.setFormat(formato)

        if expressao_cor:
            propriedade_cor = self._valor_enum(QgsPalLayerSettings, "Color", "Property")
            propriedades = settings.dataDefinedProperties()
            propriedades.setProperty(
                propriedade_cor, QgsProperty.fromExpression(expressao_cor)
            )
            settings.setDataDefinedProperties(propriedades)

        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()

    def _desativar_rotulos_mapa(self):
        for layer in (self.layer_bacias, self.layer_coletores):
            if layer is not None:
                layer.setLabelsEnabled(False)
                layer.triggerRepaint()
        self.iface.messageBar().pushMessage(
            "saniDmae - DSES", "Rotulos desativados.", level=0, duration=3
        )

    def _extensao_para_layout(self):
        """Usa a area das feicoes selecionadas (bacias e/ou coletores), se
        houver alguma selecionada, com uma margem de respiro. Senao, usa a
        vista atual do mapa."""
        crs_projeto = QgsProject.instance().crs()
        candidatos = []
        for layer in (self.layer_bacias, self.layer_coletores):
            if layer is None or layer.selectedFeatureCount() == 0:
                continue
            bbox = layer.boundingBoxOfSelected()
            if layer.crs() != crs_projeto:
                try:
                    transform = QgsCoordinateTransform(layer.crs(), crs_projeto, QgsProject.instance())
                    bbox = transform.transformBoundingBox(bbox)
                except Exception:
                    continue
            candidatos.append(bbox)

        if candidatos:
            rect = candidatos[0]
            for r in candidatos[1:]:
                rect.combineExtentWith(r)
            rect.scale(1.15)
            return rect

        return self.canvas.extent()

    def _gerar_layout_apresentacao(self):
        try:
            projeto = QgsProject.instance()
            layout = QgsPrintLayout(projeto)
            layout.initializeDefaults()
            nome = f"saniDmae - DSES - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            layout.setName(nome)

            pagina = layout.pageCollection().page(0)
            largura = pagina.pageSize().width()
            altura = pagina.pageSize().height()

            extensao = self._extensao_para_layout()

            mapa = QgsLayoutItemMap(layout)
            layout.addLayoutItem(mapa)
            mapa.attemptSetSceneRect(QRectF(10, 25, largura - 20, altura - 70))
            mapa.setExtent(extensao)
            mapa.setFrameEnabled(True)
            mapa.refresh()

            titulo = QgsLayoutItemLabel(layout)
            titulo.setText("Diagnostico de Rede de Esgoto")
            fonte_titulo = QFont("Arial", 16)
            fonte_titulo.setBold(True)
            titulo.setFont(fonte_titulo)
            titulo.adjustSizeToText()
            layout.addLayoutItem(titulo)
            titulo.attemptMove(QgsLayoutPoint(10, 8, QgsUnitTypes.LayoutMillimeters))

            escala = QgsLayoutItemScaleBar(layout)
            try:
                escala.setStyle("Single Box")
            except Exception:
                pass
            escala.setLinkedMap(mapa)
            escala.applyDefaultSize()
            layout.addLayoutItem(escala)
            escala.attemptMove(QgsLayoutPoint(10, altura - 30, QgsUnitTypes.LayoutMillimeters))

            autor = QgsLayoutItemLabel(layout)
            autor.setText("🚰 Desenho por: Diretoria do Sistema de Esgotamento Sanitário")
            autor.setFont(QFont("Arial", 9))
            autor.adjustSizeToText()
            layout.addLayoutItem(autor)
            autor.attemptMove(QgsLayoutPoint(10, altura - 16, QgsUnitTypes.LayoutMillimeters))

            rodape = QgsLayoutItemLabel(layout)
            rodape.setText(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} - plugin saniDmae - DSES")
            rodape.setFont(QFont("Arial", 8))
            rodape.adjustSizeToText()
            layout.addLayoutItem(rodape)
            rodape.attemptMove(QgsLayoutPoint(10, altura - 10, QgsUnitTypes.LayoutMillimeters))

            gerenciador = projeto.layoutManager()
            existente = gerenciador.layoutByName(nome)
            if existente is not None:
                gerenciador.removeLayout(existente)
            gerenciador.addLayout(layout)

            self.iface.openLayoutDesigner(layout)
            self.iface.messageBar().pushMessage(
                "saniDmae - DSES",
                "Mapa de apresentacao criado e aberto no Compositor de Impressao - "
                "ajuste o que quiser (posicao, fonte, elementos) e exporte como "
                "PDF/imagem por la.",
                level=0,
                duration=6,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Erro ao gerar mapa de apresentacao",
                f"Nao consegui gerar o layout. Detalhe do erro:\n\n{type(exc).__name__}: {exc}",
            )

    def _preencher_tabela(self, resultados):
        self.tabela_resultado.setRowCount(0)
        for r in sorted(resultados, key=lambda x: x["coletor_id"]):
            row = self.tabela_resultado.rowCount()
            self.tabela_resultado.insertRow(row)
            self.tabela_resultado.setItem(row, 0, QTableWidgetItem(r["coletor_id"]))
            self.tabela_resultado.setItem(
                row, 1, QTableWidgetItem(f"{r['vazao_acumulada']:.3f}")
            )
            s_txt = (
                f"{r['inclinacao_usada'] * 100:.3f}" if r.get("inclinacao_usada") is not None else "-"
            )
            self.tabela_resultado.setItem(row, 2, QTableWidgetItem(s_txt))
            dn_txt = f"{r['dn_calculado']:.3f}" if r["dn_calculado"] is not None else "-"
            self.tabela_resultado.setItem(row, 3, QTableWidgetItem(dn_txt))
            dn_e_txt = f"{r['dn_existente']:.3f}" if r["dn_existente"] is not None else "-"
            self.tabela_resultado.setItem(row, 4, QTableWidgetItem(dn_e_txt))

            avisos_nbr = []
            if r.get("atende_declividade_minima") is False:
                avisos_nbr.append("Imin!")
            if r.get("atende_tensao_trativa_calc") is False:
                avisos_nbr.append("Trat!")
            if r.get("excede_velocidade_critica_calc"):
                avisos_nbr.append("Vel!")
            if r.get("excede_espacamento_pv"):
                avisos_nbr.append("Espac!")
            if r.get("lamina_reduzida_calc"):
                avisos_nbr.append("(lam.50%)")
            nbr_txt = " ".join(avisos_nbr) if avisos_nbr else "OK"
            self.tabela_resultado.setItem(row, 5, QTableWidgetItem(nbr_txt))

            if r["critico"]:
                for col in range(5):
                    self.tabela_resultado.item(row, col).setBackground(QColor(255, 200, 200))
            if avisos_nbr:
                self.tabela_resultado.item(row, 5).setBackground(QColor(255, 230, 150))

    # -------------------------------------------------------- exportar ----
