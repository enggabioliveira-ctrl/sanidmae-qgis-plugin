# -*- coding: utf-8 -*-
"""
Construcao da interface do painel (secoes, widgets) e recolher/expandir secoes.

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


class UIMixin:
    def _novo_combo_estreito(self, largura_caracteres=16):
        """QComboBox que nao cresce sem limite com nomes de camada/campo
        compridos - fica com reticencias e mostra o nome completo no
        tooltip, pra caber em docks estreitos."""
        combo = QComboBox()
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(largura_caracteres)
        combo.setMaximumWidth(260)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.currentIndexChanged.connect(lambda _=None, c=combo: c.setToolTip(c.currentText()))
        return combo

    def _montar_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        self._grupos = []  # lista de secoes recolhiveis, pra recolher/expandir tudo de uma vez

        lbl_titulo = QLabel("saniDmae - DSES")
        lbl_titulo.setStyleSheet("font-size: 13pt; font-weight: bold;")
        layout.addWidget(lbl_titulo)

        lbl_slogan = QLabel("Simulação em redes de esgoto")
        lbl_slogan.setStyleSheet("font-style: italic; color: #555; margin-bottom: 6px;")
        layout.addWidget(lbl_slogan)

        linha_topo = QVBoxLayout()
        btn_recolher_tudo = QPushButton("Recolher tudo")
        btn_recolher_tudo.clicked.connect(lambda: self._alternar_todos_grupos(False))
        btn_expandir_tudo = QPushButton("Expandir tudo")
        btn_expandir_tudo.clicked.connect(lambda: self._alternar_todos_grupos(True))
        linha_topo.addWidget(btn_recolher_tudo)
        linha_topo.addWidget(btn_expandir_tudo)
        layout.addLayout(linha_topo)

        # ---- grupo: configuracao do projeto de calculo ----
        grp_config = GrupoRecolhivel("1) Configuracao do projeto de calculo")
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.cb_layer_bacias = self._novo_combo_estreito()
        self.cb_campo_id_bacia = self._novo_combo_estreito()
        self.cb_layer_bacias.currentIndexChanged.connect(self._on_layer_bacias_changed)
        btn_escolher_bacia = QPushButton("Usar camada da arvore")
        btn_escolher_bacia.setToolTip(
            "Clique na camada de bacias no painel 'Camadas' do QGIS "
            "(a arvore de camadas a esquerda) e depois clique aqui."
        )
        btn_escolher_bacia.clicked.connect(lambda: self._usar_camada_da_arvore(self.cb_layer_bacias, "bacias"))
        v_bacia = QVBoxLayout()
        v_bacia.addWidget(self.cb_layer_bacias)
        v_bacia.addWidget(btn_escolher_bacia)
        form.addRow("Camada de bacias:", v_bacia)
        form.addRow("Campo ID da bacia:", self.cb_campo_id_bacia)

        self.cb_layer_coletores = self._novo_combo_estreito()
        self.cb_campo_id_coletor = self._novo_combo_estreito()
        self.cb_campo_dn_existente = self._novo_combo_estreito()
        self.cb_layer_coletores.currentIndexChanged.connect(self._on_layer_coletores_changed)
        btn_escolher_coletor = QPushButton("Usar camada da arvore")
        btn_escolher_coletor.setToolTip(
            "Clique na camada de coletores no painel 'Camadas' do QGIS "
            "(a arvore de camadas a esquerda) e depois clique aqui."
        )
        btn_escolher_coletor.clicked.connect(lambda: self._usar_camada_da_arvore(self.cb_layer_coletores, "coletores"))
        v_coletor = QVBoxLayout()
        v_coletor.addWidget(self.cb_layer_coletores)
        v_coletor.addWidget(btn_escolher_coletor)
        form.addRow("Camada de coletores:", v_coletor)
        form.addRow("Campo ID do coletor:", self.cb_campo_id_coletor)
        form.addRow("Campo DN existente:", self.cb_campo_dn_existente)

        self.cb_unidade_dn = self._novo_combo_estreito()
        self.cb_unidade_dn.addItems(["Metros (m)", "Milimetros (mm)"])
        self.cb_unidade_dn.setToolTip(
            "O plugin tenta adivinhar sozinho pelo valor dos dados, mas confira: "
            "diametro de rede de esgoto tipicamente fica entre 0.1 e 2 m "
            "(ex: 0.3, 0.4, 1.5), ou entre 100 e 2000 mm (ex: 150, 300, 800)."
        )
        form.addRow("Unidade do DN existente:", self.cb_unidade_dn)
        self.cb_campo_dn_existente.currentIndexChanged.connect(self._sugerir_unidade_dn)

        btn_recarregar = QPushButton("Recarregar camadas do projeto")
        btn_recarregar.clicked.connect(self._popular_combos_camadas)
        form.addRow(btn_recarregar)

        btn_criar_novo = QPushButton("Criar novo banco de calculo (.sqlite)")
        btn_criar_novo.clicked.connect(self._criar_novo_banco)
        form.addRow(btn_criar_novo)

        btn_abrir_existente = QPushButton("Abrir banco de calculo existente (.sqlite)")
        btn_abrir_existente.setToolTip(
            "Reabre um banco ja criado antes, pra continuar de onde parou "
            "sem refazer a vinculacao e os parametros. O plugin tenta "
            "lembrar sozinho quais camadas e campos voce usou da ultima vez."
        )
        btn_abrir_existente.clicked.connect(self._abrir_banco_existente)
        form.addRow(btn_abrir_existente)

        self.lbl_status_banco = QLabel("Nenhum banco aberto.")
        self.lbl_status_banco.setWordWrap(True)
        form.addRow(self.lbl_status_banco)

        grp_config.setLayout(form)
        layout.addWidget(grp_config)
        self._grupos.append(grp_config)

        # ---- grupo: vinculos (cascata) ----
        grp_vinculos = GrupoRecolhivel("2) Vinculos (clique no mapa)")
        v = QVBoxLayout()

        self.btn_vincular_bacia = QPushButton("Vincular bacia(s) -> coletor")
        self.btn_vincular_bacia.setCheckable(True)
        self.btn_vincular_bacia.clicked.connect(self._ativar_vincular_bacia)
        v.addWidget(self.btn_vincular_bacia)

        self.btn_vincular_coletor = QPushButton("Vincular coletor(es) -> jusante")
        self.btn_vincular_coletor.setCheckable(True)
        self.btn_vincular_coletor.setToolTip("Vincula coletor(es) de montante ao coletor de jusante (cascata).")
        self.btn_vincular_coletor.clicked.connect(self._ativar_vincular_coletor)
        v.addWidget(self.btn_vincular_coletor)

        btn_desvincular_bacia = QPushButton("Desvincular bacia(s) selecionada(s)")
        btn_desvincular_bacia.setToolTip(
            "Selecione uma ou mais bacias na camada (Ctrl+clique ou retangulo de "
            "selecao) e clique aqui pra remover o vinculo delas com o coletor - "
            "util pra reprocessar o calculo de outro jeito, sem precisar apagar "
            "o banco inteiro."
        )
        btn_desvincular_bacia.clicked.connect(self._desvincular_bacias_selecionadas)
        v.addWidget(btn_desvincular_bacia)

        btn_desvincular_coletor = QPushButton("Desvincular coletor(es) do jusante")
        btn_desvincular_coletor.setToolTip(
            "Selecione um ou mais coletores na camada e clique aqui pra remover "
            "o vinculo deles com o coletor de jusante (cascata)."
        )
        btn_desvincular_coletor.clicked.connect(self._desvincular_coletores_selecionados)
        v.addWidget(btn_desvincular_coletor)

        info = QLabel(
            "Dica: clique em uma ou varias origens e depois clique no destino "
            "para vincular todas de uma vez. Botao direito ou ESC limpa a "
            "selecao pendente."
        )
        info.setWordWrap(True)
        v.addWidget(info)

        self.lbl_status_vinculo = QLabel("Nenhuma ferramenta de vinculo ativa.")
        self.lbl_status_vinculo.setWordWrap(True)
        self.lbl_status_vinculo.setStyleSheet(
            "background-color: #fff3cd; border: 1px solid #d9b44a; "
            "padding: 6px; font-weight: bold;"
        )
        v.addWidget(self.lbl_status_vinculo)

        grp_vinculos.setLayout(v)
        layout.addWidget(grp_vinculos)
        self._grupos.append(grp_vinculos)

        # ---- grupo: densidade da bacia selecionada ----
        grp_densidade = GrupoRecolhivel("3) Densidade / Micromedicao (bacia selecionada na camada)")
        v2 = QVBoxLayout()
        self.cb_densidade = self._novo_combo_estreito()
        v2.addWidget(self.cb_densidade)
        self.sp_densidade_manual = QDoubleSpinBox()
        self.sp_densidade_manual.setRange(0, 5000)
        self.sp_densidade_manual.setSuffix(" hab/ha")
        self.sp_densidade_manual.setToolTip("Preencha para usar um valor manual em vez da lista acima.")
        v2.addWidget(self.sp_densidade_manual)
        btn_aplicar_densidade = QPushButton("Aplicar a bacia(s) selecionada(s)")
        btn_aplicar_densidade.clicked.connect(self._aplicar_densidade_selecao)
        v2.addWidget(btn_aplicar_densidade)

        linha_micro = QLabel(
            "Micromedicao (opcional): importe o CSV de pontos com consumo medido, "
            "depois escolha por bacia se ela deve usar a soma desses pontos em vez "
            "da estimativa por area/densidade."
        )
        linha_micro.setWordWrap(True)
        v2.addWidget(linha_micro)

        btn_importar_csv = QPushButton("Importar CSV de micromedicao")
        btn_importar_csv.setToolTip(
            "CSV com um ponto por imovel: ID, coordenada X, coordenada Y e consumo "
            "medido em L/s. O plugin cruza automaticamente cada ponto com a bacia "
            "onde ele cai."
        )
        btn_importar_csv.clicked.connect(self._importar_csv_micromedicao)
        v2.addWidget(btn_importar_csv)

        btn_usar_micro = QPushButton("Usar micromedicao na(s) bacia(s) selecionada(s)")
        btn_usar_micro.clicked.connect(self._alternar_usar_micromedicao_selecao)
        v2.addWidget(btn_usar_micro)

        btn_voltar_area = QPushButton("Voltar para area/densidade na(s) bacia(s) selecionada(s)")
        btn_voltar_area.clicked.connect(self._desativar_micromedicao_selecao)
        v2.addWidget(btn_voltar_area)

        grp_densidade.setLayout(v2)
        layout.addWidget(grp_densidade)
        self._grupos.append(grp_densidade)

        # ---- grupo: parametros e excecoes ----
        grp_param = GrupoRecolhivel("4) Parametros de calculo")
        v3 = QVBoxLayout()
        btn_param_globais = QPushButton("Editar parametros globais")
        btn_param_globais.setToolTip("qf, C, k1, k2, inclinacao (S), lamina relativa (h/D), rugosidade (n) e a formula do diametro.")
        btn_param_globais.clicked.connect(self._editar_parametros_globais)
        v3.addWidget(btn_param_globais)
        btn_excecao = QPushButton("Editar excecao do coletor")
        btn_excecao.setToolTip("Sobrescreve inclinacao/lamina/rugosidade so para o coletor selecionado na camada.")
        btn_excecao.clicked.connect(self._editar_excecao_coletor)
        v3.addWidget(btn_excecao)

        btn_declividade = QPushButton("Definir declividade por trecho")
        btn_declividade.setToolTip(
            "Selecione varios coletores na camada (Ctrl+clique ou retangulo de "
            "selecao) e clique aqui: o plugin passa um a um pedindo a "
            "declividade media do trecho, em %."
        )
        btn_declividade.clicked.connect(self._definir_declividade_por_trecho)
        v3.addWidget(btn_declividade)

        grp_param.setLayout(v3)
        layout.addWidget(grp_param)
        self._grupos.append(grp_param)

        # ---- grupo: calcular ----
        grp_calc = GrupoRecolhivel("5) Calcular e exportar")
        v4 = QVBoxLayout()
        btn_calcular = QPushButton("Calcular tudo (cascata completa)")
        btn_calcular.clicked.connect(self._calcular_tudo)
        v4.addWidget(btn_calcular)

        self.tabela_resultado = QTableWidget(0, 6)
        self.tabela_resultado.setHorizontalHeaderLabels(
            ["Coletor", "Vazao (L/s)", "Declividade (%)", "DN calc.(m)", "DN exist.(m)", "NBR 9649"]
        )
        self.tabela_resultado.setToolTip(
            "NBR 9649: 'Imin!' = declividade abaixo da minima recomendada; "
            "'Trat!' = tensao trativa (DN adotado) abaixo de 1,0 Pa; "
            "'Vel!' = velocidade final ainda excede a critica mesmo apos a "
            "reducao automatica de lamina; 'Espac!' = trecho mais longo que "
            "o espacamento maximo entre PVs; '(lam.50%)' = a lamina foi "
            "reduzida a 50% automaticamente porque a velocidade excedia a "
            "critica; 'OK' = atende tudo."
        )
        self.tabela_resultado.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela_resultado.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tabela_resultado.setMinimumHeight(160)
        self.tabela_resultado.setMaximumHeight(220)
        v4.addWidget(self.tabela_resultado)

        btn_exportar = QPushButton("Exportar so os trechos criticos (CSV)")
        btn_exportar.clicked.connect(self._exportar_relatorio)
        v4.addWidget(btn_exportar)

        btn_diagnostico = QPushButton("Exportar relatorio completo (CSV)")
        btn_diagnostico.setToolTip(
            "Gera um relatorio completo: parametros adotados, excecoes por "
            "trecho, densidades e vazao propria de cada bacia, a cascata "
            "coletor->coletor e o resultado de TODOS os coletores (nao so "
            "os criticos). Alem do CSV, o 'Calcular tudo' ja grava esses "
            "mesmos dados como atributos direto nas camadas de bacias e "
            "coletores - assim, se voce mudar algo (densidade, vinculo, "
            "parametro) e recalcular, nao precisa refazer a vinculacao."
        )
        btn_diagnostico.clicked.connect(self._gerar_relatorio_diagnostico)
        v4.addWidget(btn_diagnostico)

        grp_calc.setLayout(v4)
        layout.addWidget(grp_calc)
        self._grupos.append(grp_calc)

        # ---- grupo: resumo e rotulos no mapa ----
        grp_resumo = GrupoRecolhivel("6) Resumo e rotulos no mapa")
        v5 = QVBoxLayout()

        self.txt_resumo = QPlainTextEdit()
        self.txt_resumo.setReadOnly(True)
        self.txt_resumo.setMaximumHeight(160)
        self.txt_resumo.setPlainText("Abra um banco e calcule para ver o resumo aqui.")
        v5.addWidget(self.txt_resumo)

        btn_atualizar_resumo = QPushButton("Atualizar resumo")
        btn_atualizar_resumo.clicked.connect(self._atualizar_resumo)
        v5.addWidget(btn_atualizar_resumo)

        btn_rotulos_on = QPushButton("Ativar rotulos no mapa (vinculos e parametros)")
        btn_rotulos_on.setToolTip(
            "Mostra direto no mapa, em cada bacia e coletor, o vinculo, a "
            "densidade e os principais resultados calculados."
        )
        btn_rotulos_on.clicked.connect(self._ativar_rotulos_mapa)
        v5.addWidget(btn_rotulos_on)

        btn_rotulos_off = QPushButton("Desativar rotulos no mapa")
        btn_rotulos_off.clicked.connect(self._desativar_rotulos_mapa)
        v5.addWidget(btn_rotulos_off)

        self.chk_apresentacao = QCheckBox("Modo apresentacao (simbolos e rotulos menores)")
        self.chk_apresentacao.setToolTip(
            "Deixa a linha da rede, os marcadores de inicio/fim de trecho e o "
            "texto dos rotulos menores e mais discretos - melhor pra compor "
            "um mapa de apresentacao."
        )
        self.chk_apresentacao.stateChanged.connect(self._on_modo_apresentacao_mudou)
        v5.addWidget(self.chk_apresentacao)

        btn_layout = QPushButton("Gerar mapa de apresentacao (layout pronto)")
        btn_layout.setToolTip(
            "Cria um layout de impressao (mapa + legenda + escala + titulo) "
            "pronto pra ajustar e exportar como PDF/imagem. Usa a area das "
            "feicoes selecionadas no mapa (bacias ou coletores), se houver "
            "alguma selecionada - senao usa a vista atual do mapa."
        )
        btn_layout.clicked.connect(self._gerar_layout_apresentacao)
        v5.addWidget(btn_layout)

        grp_resumo.setLayout(v5)
        layout.addWidget(grp_resumo)
        self._grupos.append(grp_resumo)

        layout.addStretch()
        container.setLayout(layout)
        container.setMinimumWidth(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.setWidget(scroll)

    def _alternar_todos_grupos(self, aberto):
        for grupo in self._grupos:
            grupo.setChecked(aberto)

    # ------------------------------------------------------ camadas ----
    # palavras usadas para "adivinhar" a camada e os campos certos, em
    # ordem de prioridade (a primeira que bater primeiro em algum item vence)
    PALAVRAS_LAYER_BACIA = ["subbacia", "sub_bacia", "sub-bacia", "bacia"]
    PALAVRAS_LAYER_COLETOR = ["coletor", "rede", "esgoto"]
    PALAVRAS_CAMPO_ID_BACIA = ["nome", "sigla", "bacia_id", "id"]
    PALAVRAS_CAMPO_ID_COLETOR = ["nome", "sigla", "coletor", "id"]
    PALAVRAS_CAMPO_DN_EXISTENTE = [
        "dn_existente", "dn_exist", "diametro_existente", "diam_existente",
        "d_exist", "existente", "dn",
    ]

