# -*- coding: utf-8 -*-
"""
Constantes compartilhadas entre os modulos do painel (mixins).

CAMPOS_RESULTADO / CAMPOS_BACIA definem os campos que o plugin cria/usa
nas camadas de coletores e de bacias, respectivamente. Cada item e uma
tupla (nome_do_campo, tipo_QVariant, descricao).

IMPORTANTE: nomes de campo tem no maximo 10 caracteres de proposito -
Shapefile (.shp) trunca nomes maiores que isso, o que ja causou um bug
serio (ver CHANGELOG.md, correcao "S_USADA_PCT -> S_USO_PCT"). Se for
adicionar um campo novo aqui, mantenha esse limite.
"""

from qgis.PyQt.QtCore import QVariant

CAMPOS_RESULTADO = [
    ("VAZAO_ACM", QVariant.Double, "Vazao acumulada (L/s)"),
    ("DN_CALC", QVariant.Double, "Diametro calculado (m)"),
    ("CRITICO", QVariant.Int, "1 = precisa trocar/melhorar"),
    ("COL_JUSANT", QVariant.String, "Coletor de jusante vinculado"),
    ("COTA_INIC", QVariant.Double, "Cota de inicio do trecho (m)"),
    ("COTA_FIN", QVariant.Double, "Cota de saida do trecho (m)"),
    ("COMPR_M", QVariant.Double, "Comprimento do trecho (m)"),
    ("DECLIV_PCT", QVariant.Double, "Declividade media do trecho (%)"),
    ("DN_EXIST_M", QVariant.Double, "DN existente, normalizado para metros"),
    ("STATUS", QVariant.String, "ATENDE ou CRITICO"),
    ("DIRECAO_OK", QVariant.Int, "1 = linha digitalizada no sentido do fluxo, 0 = ao contrario"),
    ("S_USO_PCT", QVariant.Double, "Inclinacao efetivamente usada no calculo (%)"),
    ("IMIN_PCT", QVariant.Double, "Declividade minima NBR 9649 (%)"),
    ("OK_IMIN", QVariant.Int, "1 = declividade adotada atende a minima da NBR 9649"),
    ("TRAT_CPA", QVariant.Double, "Tensao trativa (Pa) usando o DN calculado"),
    ("OK_TRATC", QVariant.Int, "1 = tensao trativa (DN calculado) atende >= 1,0 Pa"),
    ("TRAT_EPA", QVariant.Double, "Tensao trativa (Pa) usando o DN existente"),
    ("OK_TRATE", QVariant.Int, "1 = tensao trativa (DN existente) atende >= 1,0 Pa"),
    ("DN_ADOT", QVariant.Double, "DN adotado = max(DN calculado, DN minimo de norma)"),
    ("VF_CALC", QVariant.Double, "Velocidade final (m/s) - DN adotado"),
    ("VC_CALC", QVariant.Double, "Velocidade critica (m/s) - DN adotado"),
    ("OK_VELC", QVariant.Int, "1 = velocidade final NAO excede a critica (DN adotado)"),
    ("VF_EXIST", QVariant.Double, "Velocidade final (m/s) - DN existente"),
    ("VC_EXIST", QVariant.Double, "Velocidade critica (m/s) - DN existente"),
    ("OK_VELE", QVariant.Int, "1 = velocidade final NAO excede a critica (DN existente)"),
    ("OK_ESPAC", QVariant.Int, "1 = comprimento do trecho atende ao espacamento maximo entre PVs"),
    ("LAMRED_C", QVariant.Int, "1 = lamina reduzida a 50% automaticamente (DN adotado)"),
    ("LAMRED_E", QVariant.Int, "1 = lamina reduzida a 50% automaticamente (DN existente)"),
]

CAMPOS_BACIA = [
    ("COL_DEST", QVariant.String, "Coletor vinculado"),
    ("DENS_HAB", QVariant.Double, "Densidade adotada (hab/ha)"),
    ("AREA_CALC", QVariant.Double, "Area (ha) usada no calculo"),
    ("POP_EST", QVariant.Double, "Populacao estimada"),
    ("VAZAO_PROP", QVariant.Double, "Vazao propria da bacia (L/s)"),
    ("USA_MICRO", QVariant.Int, "1 = usa vazao por micromedicao em vez de area/densidade"),
    ("CONS_MICR", QVariant.Double, "Soma do consumo medido dos pontos dentro da bacia (L/s)"),
]
