# -*- coding: utf-8 -*-
"""
Coleta os dados das camadas (area, densidade, DN existente), roda o motor de
calculo (calculo.calcular_tudo) e escreve os resultados de volta nas camadas.

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
from .calculo import calcular_tudo, calcular_vazao_bacia, calcular_vazao_micromedicao, ErroTopologia
from .maptool_link import VincularMapTool
from .geo_utils import calcular_area_ha, calcular_comprimento_m, nova_distance_area
from .collapsible import GrupoRecolhivel
from .constantes import CAMPOS_RESULTADO, CAMPOS_BACIA


class CalculoMixin:
    def _coletar_area_densidade_bacias(self):
        """area_ha vem da geometria da camada (a nao ser que haja override
        no banco), densidade vem do banco."""
        dados = {}
        dados_banco = self.db.get_all_bacia_dados()
        da = nova_distance_area(self.layer_bacias)
        for feicao in self.layer_bacias.getFeatures():
            bacia_id = str(feicao.attribute(self.campo_id_bacia))
            info = dados_banco.get(bacia_id)
            if info is None or info.get("densidade_hab_ha") is None:
                continue
            if info.get("area_ha_manual") is not None:
                area_ha = info["area_ha_manual"]
            else:
                geom = feicao.geometry()
                area_ha = calcular_area_ha(self.layer_bacias, geom, da)
            dados[bacia_id] = (area_ha, info["densidade_hab_ha"])
        return dados

    def _coletar_micromedicao_bacias(self):
        """Retorna (soma_consumo_por_bacia, ids_que_usam_micromedicao),
        pra passar pro motor de calculo. So entram na segunda lista as
        bacias marcadas manualmente (USA_MICRO) que tambem tem pontos de
        consumo somados (senao nao ha o que usar)."""
        soma_por_bacia = self.db.get_soma_consumo_por_bacia()
        dados_banco = self.db.get_all_bacia_dados()
        usar = {
            bacia_id
            for bacia_id, info in dados_banco.items()
            if info.get("usar_micromedicao")
        }
        return soma_por_bacia, usar

    def _coletar_dn_existente(self):
        dn_map = {}
        fator = 0.001 if self.cb_unidade_dn.currentIndex() == 1 else 1.0
        for feicao in self.layer_coletores.getFeatures():
            coletor_id = str(feicao.attribute(self.campo_id_coletor))
            valor = feicao.attribute(self.campo_dn_existente)
            try:
                dn_map[coletor_id] = float(valor) * fator
            except (TypeError, ValueError):
                dn_map[coletor_id] = None
        return dn_map

    def _coletar_comprimentos_trecho(self):
        """Comprimento (m) de cada coletor, usado na vazao de infiltracao
        (Qinf = Lt x Cinf). Prioriza a cota salva no banco (definida em
        'Definir declividade por trecho', ja que ali o comprimento e
        medido junto com as cotas); senao mede direto da geometria."""
        comprimentos = {}
        cotas_banco = {}
        try:
            for feicao in self.layer_coletores.getFeatures():
                coletor_id = str(feicao.attribute(self.campo_id_coletor))
                cotas = self.db.get_cotas(coletor_id)
                if cotas and cotas.get("comprimento_m") is not None:
                    cotas_banco[coletor_id] = cotas["comprimento_m"]
        except Exception:
            pass

        da = nova_distance_area(self.layer_coletores)
        for feicao in self.layer_coletores.getFeatures():
            coletor_id = str(feicao.attribute(self.campo_id_coletor))
            if coletor_id in cotas_banco:
                comprimentos[coletor_id] = cotas_banco[coletor_id]
            else:
                comprimentos[coletor_id] = calcular_comprimento_m(
                    self.layer_coletores, feicao.geometry(), da
                )
        return comprimentos

    def _calcular_tudo(self):
        if not self._checar_banco():
            return
        try:
            bacias_area_densidade = self._coletar_area_densidade_bacias()
            bacia_coletor_map = self.db.get_bacia_coletor_map()
            coletor_destino_map = self.db.get_coletor_destino_map()
            dn_existente_map = self._coletar_dn_existente()
            parametros = self.db.get_parametros()
            excecoes = self.db.get_all_excecoes()
            soma_micromedicao, bacias_usar_micro = self._coletar_micromedicao_bacias()
            comprimentos_trecho = self._coletar_comprimentos_trecho()

            resultados = calcular_tudo(
                bacias_area_densidade,
                bacia_coletor_map,
                coletor_destino_map,
                dn_existente_map,
                parametros,
                excecoes,
                soma_micromedicao,
                bacias_usar_micro,
                comprimentos_trecho,
            )
        except ErroTopologia as exc:
            QMessageBox.critical(self, "Erro de topologia", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Erro no calculo", str(exc))
            return

        self.db.salvar_resultados(resultados)
        self._escrever_resultados_na_camada(resultados, coletor_destino_map)
        self._escrever_dados_na_camada_bacias(
            bacias_area_densidade, bacia_coletor_map, parametros,
            soma_micromedicao, bacias_usar_micro,
        )
        self._aplicar_simbologia_criticos(apresentacao=self.chk_apresentacao.isChecked())
        self._preencher_tabela(resultados)
        self._salvar_config_atual()
        self._atualizar_resumo()
        QMessageBox.information(
            self, "OK",
            f"Calculo concluido para {len(resultados)} coletor(es). "
            "Os dados tambem foram gravados como atributos nas camadas de "
            "bacias e coletores."
        )

    def _extremos_linha(self, geom):
        """Retorna (ponto_inicio, ponto_fim) da geometria de uma linha
        (pega a primeira parte se for multi-linha), ou None se nao der."""
        if geom is None or geom.isEmpty():
            return None
        try:
            if geom.isMultipart():
                partes = geom.asMultiPolyline()
                if not partes or len(partes[0]) < 2:
                    return None
                linha = partes[0]
            else:
                linha = geom.asPolyline()
                if len(linha) < 2:
                    return None
            return linha[0], linha[-1]
        except Exception:
            return None

    def _calcular_direcao_ok(self, layer, coletor_destino_map):
        """Para cada coletor com um coletor de jusante vinculado, descobre
        em qual das duas pontas do trecho atual ele realmente encosta no
        trecho de jusante (compara as 4 combinacoes de pontas possiveis,
        em vez de assumir que o "inicio" do trecho de jusante e o ponto de
        encontro - isso falha se o trecho de jusante tambem estiver
        digitalizado ao contrario). Se o ponto de encontro for o FIM do
        trecho atual, a linha esta no sentido certo (1); se for o INICIO,
        esta invertida (0). Coletores sem jusante vinculado nao entram no
        dict (nao da pra saber sem referencia)."""
        geometrias = {}
        for feicao in layer.getFeatures():
            cid = str(feicao.attribute(self.campo_id_coletor))
            geometrias[cid] = feicao.geometry()

        resultado = {}
        for coletor_id, jusante_id in coletor_destino_map.items():
            geom_atual = geometrias.get(coletor_id)
            geom_jusante = geometrias.get(str(jusante_id))
            if geom_atual is None or geom_jusante is None:
                continue
            extremos_atual = self._extremos_linha(geom_atual)
            extremos_jusante = self._extremos_linha(geom_jusante)
            if extremos_atual is None or extremos_jusante is None:
                continue
            ponto_inicio, ponto_fim = extremos_atual
            inicio_jusante, fim_jusante = extremos_jusante

            # menor distancia do FIM do trecho atual ate qualquer ponta do jusante
            dist_fim = min(ponto_fim.distance(inicio_jusante), ponto_fim.distance(fim_jusante))
            # menor distancia do INICIO do trecho atual ate qualquer ponta do jusante
            dist_inicio = min(
                ponto_inicio.distance(inicio_jusante), ponto_inicio.distance(fim_jusante)
            )

            resultado[coletor_id] = 1 if dist_fim <= dist_inicio else 0

        return resultado

    def _escrever_resultados_na_camada(self, resultados, coletor_destino_map):
        self._garantir_campos_resultado()
        layer = self.layer_coletores
        idx_vazao = layer.fields().indexOf("VAZAO_ACM")
        idx_dn = layer.fields().indexOf("DN_CALC")
        idx_crit = layer.fields().indexOf("CRITICO")
        idx_jusante = layer.fields().indexOf("COL_JUSANT")
        idx_dn_exist = layer.fields().indexOf("DN_EXIST_M")
        idx_status = layer.fields().indexOf("STATUS")
        idx_direcao = layer.fields().indexOf("DIRECAO_OK")
        idx_s_usada = layer.fields().indexOf("S_USO_PCT")
        idx_imin = layer.fields().indexOf("IMIN_PCT")
        idx_ok_imin = layer.fields().indexOf("OK_IMIN")
        idx_trat_c = layer.fields().indexOf("TRAT_CPA")
        idx_ok_tratc = layer.fields().indexOf("OK_TRATC")
        idx_trat_e = layer.fields().indexOf("TRAT_EPA")
        idx_ok_trate = layer.fields().indexOf("OK_TRATE")
        idx_dn_adot = layer.fields().indexOf("DN_ADOT")
        idx_vf_calc = layer.fields().indexOf("VF_CALC")
        idx_vc_calc = layer.fields().indexOf("VC_CALC")
        idx_ok_velc = layer.fields().indexOf("OK_VELC")
        idx_vf_exist = layer.fields().indexOf("VF_EXIST")
        idx_vc_exist = layer.fields().indexOf("VC_EXIST")
        idx_ok_vele = layer.fields().indexOf("OK_VELE")
        idx_ok_espac = layer.fields().indexOf("OK_ESPAC")
        idx_lamred_c = layer.fields().indexOf("LAMRED_C")
        idx_lamred_e = layer.fields().indexOf("LAMRED_E")
        idx_compr = layer.fields().indexOf("COMPR_M")

        by_id = {r["coletor_id"]: r for r in resultados}
        direcao_ok_map = self._calcular_direcao_ok(layer, coletor_destino_map)

        def _bool_int(v):
            return None if v is None else (1 if v else 0)

        layer.startEditing()
        for feicao in layer.getFeatures():
            coletor_id = str(feicao.attribute(self.campo_id_coletor))
            r = by_id.get(coletor_id)
            if r is not None:
                layer.changeAttributeValue(feicao.id(), idx_vazao, r["vazao_acumulada"])
                if r["dn_calculado"] is not None:
                    layer.changeAttributeValue(feicao.id(), idx_dn, r["dn_calculado"])
                layer.changeAttributeValue(feicao.id(), idx_crit, 1 if r["critico"] else 0)
                if r["dn_existente"] is not None:
                    layer.changeAttributeValue(feicao.id(), idx_dn_exist, r["dn_existente"])
                layer.changeAttributeValue(
                    feicao.id(), idx_status, "CRITICO" if r["critico"] else "ATENDE"
                )
                if r.get("inclinacao_usada") is not None:
                    layer.changeAttributeValue(
                        feicao.id(), idx_s_usada, r["inclinacao_usada"] * 100
                    )
                if r.get("declividade_minima") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_imin, r["declividade_minima"] * 100)
                layer.changeAttributeValue(
                    feicao.id(), idx_ok_imin, _bool_int(r.get("atende_declividade_minima"))
                )
                if r.get("tensao_trativa_calc_pa") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_trat_c, r["tensao_trativa_calc_pa"])
                layer.changeAttributeValue(
                    feicao.id(), idx_ok_tratc, _bool_int(r.get("atende_tensao_trativa_calc"))
                )
                if r.get("tensao_trativa_exist_pa") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_trat_e, r["tensao_trativa_exist_pa"])
                layer.changeAttributeValue(
                    feicao.id(), idx_ok_trate, _bool_int(r.get("atende_tensao_trativa_exist"))
                )
                if r.get("dn_adotado") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_dn_adot, r["dn_adotado"])
                if r.get("velocidade_final_calc") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_vf_calc, r["velocidade_final_calc"])
                if r.get("velocidade_critica_calc") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_vc_calc, r["velocidade_critica_calc"])
                excede_calc = r.get("excede_velocidade_critica_calc")
                if excede_calc is not None:
                    layer.changeAttributeValue(feicao.id(), idx_ok_velc, 0 if excede_calc else 1)
                if r.get("velocidade_final_exist") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_vf_exist, r["velocidade_final_exist"])
                if r.get("velocidade_critica_exist") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_vc_exist, r["velocidade_critica_exist"])
                excede_exist = r.get("excede_velocidade_critica_exist")
                if excede_exist is not None:
                    layer.changeAttributeValue(feicao.id(), idx_ok_vele, 0 if excede_exist else 1)
                excede_espac = r.get("excede_espacamento_pv")
                if excede_espac is not None:
                    layer.changeAttributeValue(feicao.id(), idx_ok_espac, 0 if excede_espac else 1)
                if r.get("lamina_reduzida_calc") is not None:
                    layer.changeAttributeValue(
                        feicao.id(), idx_lamred_c, 1 if r["lamina_reduzida_calc"] else 0
                    )
                if r.get("lamina_reduzida_exist") is not None:
                    layer.changeAttributeValue(
                        feicao.id(), idx_lamred_e, 1 if r["lamina_reduzida_exist"] else 0
                    )
                # reaproveita o campo COMPR_M (mesmo campo que "Definir
                # declividade por trecho" preenche) - assim ele fica
                # sempre atualizado, mesmo em trechos onde voce nunca usou
                # aquela ferramenta
                if r.get("comprimento_trecho_m") is not None:
                    layer.changeAttributeValue(feicao.id(), idx_compr, r["comprimento_trecho_m"])
            destino = coletor_destino_map.get(coletor_id)
            if destino is not None:
                layer.changeAttributeValue(feicao.id(), idx_jusante, destino)
            if coletor_id in direcao_ok_map:
                layer.changeAttributeValue(feicao.id(), idx_direcao, direcao_ok_map[coletor_id])
        layer.commitChanges()

    def _escrever_dados_na_camada_bacias(
        self, bacias_area_densidade, bacia_coletor_map, parametros,
        soma_micromedicao=None, bacias_usar_micro=None,
    ):
        self._garantir_campos_bacia()
        layer = self.layer_bacias
        if layer is None:
            return
        soma_micromedicao = soma_micromedicao or {}
        bacias_usar_micro = bacias_usar_micro or set()

        idx_col = layer.fields().indexOf("COL_DEST")
        idx_dens = layer.fields().indexOf("DENS_HAB")
        idx_area = layer.fields().indexOf("AREA_CALC")
        idx_pop = layer.fields().indexOf("POP_EST")
        idx_vazao = layer.fields().indexOf("VAZAO_PROP")
        idx_usa_micro = layer.fields().indexOf("USA_MICRO")
        idx_cons_micro = layer.fields().indexOf("CONS_MICR")

        qf = float(parametros["qf"])
        C = float(parametros["C"])
        k1 = float(parametros["k1"])
        k2 = float(parametros["k2"])

        layer.startEditing()
        for feicao in layer.getFeatures():
            bacia_id = str(feicao.attribute(self.campo_id_bacia))

            destino = bacia_coletor_map.get(bacia_id)
            if destino is not None:
                layer.changeAttributeValue(feicao.id(), idx_col, destino)

            usa_micro = bacia_id in bacias_usar_micro
            consumo = soma_micromedicao.get(bacia_id)
            layer.changeAttributeValue(feicao.id(), idx_usa_micro, 1 if usa_micro else 0)
            if consumo is not None:
                layer.changeAttributeValue(feicao.id(), idx_cons_micro, consumo)

            if usa_micro and consumo is not None:
                q = calcular_vazao_micromedicao(consumo, C, k1, k2)
                layer.changeAttributeValue(feicao.id(), idx_vazao, q)
                # populacao/densidade nao se aplicam nesse modo - deixa como
                # estava (nao apaga um valor que o usuario possa ter usado
                # antes de trocar pra micromedicao)
                continue

            info = bacias_area_densidade.get(bacia_id)
            if info is None:
                continue
            area_ha, densidade = info
            hab, q = calcular_vazao_bacia(area_ha, densidade, qf, C, k1, k2)
            layer.changeAttributeValue(feicao.id(), idx_dens, densidade)
            layer.changeAttributeValue(feicao.id(), idx_area, area_ha)
            layer.changeAttributeValue(feicao.id(), idx_pop, hab)
            layer.changeAttributeValue(feicao.id(), idx_vazao, q)
        layer.commitChanges()

