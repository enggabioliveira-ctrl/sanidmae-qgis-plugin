# -*- coding: utf-8 -*-
"""
Utilitario compartilhado pelas ferramentas de mapa do plugin.

Corrige um problema comum: o projeto do QGIS (canvas) pode estar num CRS
diferente do CRS da camada (ex: projeto em SIRGAS2000 geografico / graus e a
camada de rede em UTM / metros). Se a gente comparar o ponto clicado
diretamente com as geometrias da camada sem converter o CRS, a busca nao
encontra nada mesmo clicando em cima da feicao. Por isso aqui a gente
transforma o ponto (e o raio de tolerancia) para o CRS da camada antes de
procurar.
"""

from qgis.core import (
    QgsGeometry,
    QgsFeatureRequest,
    QgsCoordinateTransform,
    QgsProject,
    QgsPointXY,
    QgsDistanceArea,
    QgsUnitTypes,
)


def calcular_comprimento_m(layer, geometria, da=None):
    """Calcula o comprimento em metros de uma geometria de linha, do mesmo
    jeito que o $length da Calculadora de Campo do QGIS (usa o elipsoide do
    projeto, entao funciona corretamente mesmo se a camada estiver num CRS
    geografico/graus). Aceita um QgsDistanceArea ja configurado via `da`
    pra reaproveitar em loops grandes (ver nova_distance_area)."""
    if geometria is None or geometria.isEmpty():
        return 0.0
    if da is None:
        da = QgsDistanceArea()
        da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
    comprimento = da.measureLength(geometria)
    return da.convertLengthMeasurement(comprimento, QgsUnitTypes.DistanceMeters)


def calcular_area_ha(layer, geometria, da=None):
    """Calcula a area em hectares de uma geometria, do mesmo jeito que o
    $area da Calculadora de Campo do QGIS.

    Importante: NAO da pra usar geometria.area() direto quando a camada
    esta num CRS geografico (graus) - isso retorna a area em graus
    quadrados, um numero sem sentido (tipicamente algo como 1e-8, muito
    menor que a area real em hectares). O QGIS resolve isso internamente
    usando o elipsoide configurado no projeto para calcular a area real em
    metros quadrados mesmo em camadas geograficas. Aqui replicamos esse
    comportamento com QgsDistanceArea.

    Se for chamar isso muitas vezes seguidas (ex: um loop com centenas ou
    milhares de feicoes), monte um QgsDistanceArea uma vez e passe via
    `da` - criar/configurar um novo a cada chamada é o que mais pesa em
    lacos grandes."""
    if geometria is None or geometria.isEmpty():
        return 0.0
    if da is None:
        da = QgsDistanceArea()
        da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
        da.setEllipsoid(QgsProject.instance().ellipsoid())
    area_m2 = da.measureArea(geometria)
    area_m2 = da.convertAreaMeasurement(area_m2, QgsUnitTypes.AreaSquareMeters)
    return area_m2 / 10000.0


def nova_distance_area(layer):
    """Monta um QgsDistanceArea ja configurado pro CRS/elipsoide da
    camada, pra reaproveitar em varias chamadas de calcular_area_ha (ou
    calcular_comprimento_m) num loop, sem reconfigurar toda vez."""
    da = QgsDistanceArea()
    da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
    da.setEllipsoid(QgsProject.instance().ellipsoid())
    return da


def identificar_feicao(canvas, layer, ponto_canvas):
    """Retorna a feicao de `layer` mais proxima do ponto clicado no mapa
    (ponto_canvas, no CRS do canvas), ou None se nao achar nada perto."""
    if layer is None or not layer.isValid():
        return None

    crs_canvas = canvas.mapSettings().destinationCrs()
    crs_layer = layer.crs()
    raio_canvas = canvas.mapUnitsPerPixel() * 6

    ponto = ponto_canvas
    raio = raio_canvas

    if crs_layer.isValid() and crs_canvas.isValid() and crs_layer != crs_canvas:
        transform = QgsCoordinateTransform(crs_canvas, crs_layer, QgsProject.instance())
        try:
            ponto = transform.transform(ponto_canvas)
            ponto_desloc = transform.transform(
                QgsPointXY(ponto_canvas.x() + raio_canvas, ponto_canvas.y())
            )
            raio = ponto.distance(ponto_desloc)
            if raio <= 0:
                raio = raio_canvas
        except Exception:
            ponto = ponto_canvas
            raio = raio_canvas

    geom_ponto = QgsGeometry.fromPointXY(ponto)
    retangulo = geom_ponto.buffer(raio, 4).boundingBox()
    request = QgsFeatureRequest().setFilterRect(retangulo)

    contidas = []   # feicoes cuja geometria contem o ponto (pode haver varias sobrepostas)
    mais_perto = None
    mais_perto_dist = None
    try:
        for feicao in layer.getFeatures(request):
            geom = feicao.geometry()
            if geom is None or geom.isEmpty():
                continue
            if geom.contains(ponto):
                contidas.append(feicao)
                continue
            dist = geom.distance(geom_ponto)
            if mais_perto is None or dist < mais_perto_dist:
                mais_perto = feicao
                mais_perto_dist = dist
    except Exception:
        return None

    if contidas:
        if len(contidas) == 1:
            return contidas[0]
        # varias feicoes sobrepostas no mesmo ponto (ex: uma bacia grande
        # "por baixo" e uma sub-bacia menor "por cima", visivelmente
        # destacada no mapa). A menor area normalmente e a mais especifica
        # e a que esta visivel por cima - e a que o usuario quis clicar.
        try:
            return min(contidas, key=lambda f: f.geometry().area())
        except Exception:
            return contidas[0]

    return mais_perto
