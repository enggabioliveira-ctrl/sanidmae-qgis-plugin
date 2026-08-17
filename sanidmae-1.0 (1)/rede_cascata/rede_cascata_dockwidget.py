# -*- coding: utf-8 -*-
"""
Painel principal do plugin (dock widget) - "saniDmae - DSES".

Esta classe e montada juntando varios "mixins" (um por assunto), cada um
num arquivo separado so pra organizacao/leitura. Em tempo de execucao e
tudo a MESMA classe/instancia (heranca multipla do Python) - ou seja,
dividir em arquivos aqui NAO muda nenhum comportamento do plugin, e so
reorganiza onde cada pedaco de codigo mora fisicamente, pra ficar mais
facil de achar e editar o que precisar:

    painel_ui.py          -> UIMixin          -> monta a interface (secoes, botoes)
    painel_camadas.py     -> CamadasMixin     -> escolha de camada/campo
    painel_banco.py       -> BancoMixin       -> abrir/criar banco .sqlite, restaurar config
    painel_vinculos.py    -> VinculosMixin    -> vincular/desvincular, densidade, parametros
    painel_calculo.py     -> CalculoMixin     -> roda o calculo e escreve nas camadas
    painel_mapa.py        -> MapaMixin        -> simbologia, rotulos, layout de apresentacao
    painel_relatorios.py  -> RelatoriosMixin  -> exportar Excel/CSV

Se for mexer em alguma funcionalidade especifica, o mapa acima diz em
qual arquivo procurar. Ver tambem GUIA_DE_USO.md (passo a passo pro
usuario final) e FORMULAS_E_PARAMETROS.md (todas as formulas/parametros
usados nos calculos).
"""
from qgis.PyQt.QtWidgets import QDockWidget

from .painel_ui import UIMixin
from .painel_camadas import CamadasMixin
from .painel_banco import BancoMixin
from .painel_vinculos import VinculosMixin
from .painel_calculo import CalculoMixin
from .painel_mapa import MapaMixin
from .painel_relatorios import RelatoriosMixin


class RedeCascataDockWidget(
    QDockWidget,
    UIMixin,
    CamadasMixin,
    BancoMixin,
    VinculosMixin,
    CalculoMixin,
    MapaMixin,
    RelatoriosMixin,
):
    def __init__(self, iface, parent=None):
        super().__init__("saniDmae - DSES", parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.db = None
        self.map_tool = None
        self.campo_area_manual = None  # opcional

        self._montar_ui()
        self._popular_combos_camadas()

    # As 5 propriedades abaixo SEMPRE leem o valor atual dos combos, em vez
    # de guardar uma copia que poderia ficar desatualizada se o usuario
    # trocar a camada/campo no combo depois de ja ter aberto o banco. Os
    # metodos que fazem "self.layer_bacias = ..." em outros pontos do
    # codigo continuam funcionando (o setter so ignora, ja que o getter
    # sempre busca o valor fresco mesmo assim).
    @property
    def layer_bacias(self):
        return self._layer_por_combo(self.cb_layer_bacias) if hasattr(self, "cb_layer_bacias") else None

    @layer_bacias.setter
    def layer_bacias(self, valor):
        pass

    @property
    def layer_coletores(self):
        return self._layer_por_combo(self.cb_layer_coletores) if hasattr(self, "cb_layer_coletores") else None

    @layer_coletores.setter
    def layer_coletores(self, valor):
        pass

    @property
    def campo_id_bacia(self):
        return self.cb_campo_id_bacia.currentText() if hasattr(self, "cb_campo_id_bacia") else None

    @campo_id_bacia.setter
    def campo_id_bacia(self, valor):
        pass

    @property
    def campo_id_coletor(self):
        return self.cb_campo_id_coletor.currentText() if hasattr(self, "cb_campo_id_coletor") else None

    @campo_id_coletor.setter
    def campo_id_coletor(self, valor):
        pass

    @property
    def campo_dn_existente(self):
        return self.cb_campo_dn_existente.currentText() if hasattr(self, "cb_campo_dn_existente") else None

    @campo_dn_existente.setter
    def campo_dn_existente(self, valor):
        pass

