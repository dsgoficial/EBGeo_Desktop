# -*- coding: utf-8 -*-
"""
Coeficientes de refração atmosférica do plugin: UM valor para a propagação óptica (visada do
observador) e UM para a propagação de rádio (radar e sensores). Toda ferramenta de visibilidade
do EBGeo lê daqui; nenhuma escreve o número à mão.

O coeficiente de refração k é a razão entre o raio da Terra e o raio de curvatura do raio de luz
ou de rádio. A refração encurva o raio para baixo e compensa parte da curvatura da Terra, então a
queda aparente do terreno à distância d é

    queda(d) = (1 - k) * d^2 / (2 * R)

o que equivale a uma Terra de raio efetivo R / (1 - k). No GDAL o fator (1 - k) é o coeficiente de
curvatura (`dfCurvCoeff` de `gdal.ViewshedGenerate`, `-cc` do `gdal_viewshed`).

Óptico, k = 1/7 (0,142857):
  - documentação do `gdal_viewshed` (https://gdal.org/en/stable/programs/gdal_viewshed.html),
    opção `-cc`: padrão 0,85714 para SRC terrestre, e a tabela de valores típicos dá, para luz
    visível, coeficiente de refração 1/7 e de curvatura 6/7; e
  - manual do `r.viewshed` do GRASS GIS (https://grass.osgeo.org/grass-stable/manuals/r.viewshed.html),
    `refraction_coeff` padrão 0,14286 (o manual não diz a origem do número).
  O valor clássico de Gauss usado na geodésia e no ArcGIS é 0,13; a diferença para 1/7 é de
  0,013 * d^2 / (2R), cerca de 0,1 m a 10 km, abaixo do erro vertical de qualquer MDE em uso.
  Escolhemos 1/7 porque é o padrão dos dois motores de visada (GDAL e GRASS): o resultado do
  plugin bate com o de quem roda a ferramenta nativa.

Rádio (radar e sensores), k = 0,25, a Terra de 4/3 do raio:
  - Recomendação ITU-R P.834-9 (12/2017), "Effects of tropospheric refraction on radiowave
    propagation", seção 2: a Terra efetiva tem raio Re = k' * a, e "para alturas abaixo de
    1 000 m" o perfil médio do índice de refração (ITU-R P.453) se aproxima de um linear, com
    fator de raio efetivo k' = 4/3; logo o coeficiente de refração é k = 1 - 3/4 = 0,25. Acima de
    1 000 m o 4/3 é aproximação (o perfil real é exponencial), o que a ferramenta avisa; e
  - a mesma tabela do `gdal_viewshed`, `-cc`: ondas de rádio com coeficiente de refração de
    0,25 a 0,325 (curvatura de 0,75 a 0,675); usamos o extremo da atmosfera padrão, 0,25.
  Daí o horizonte de rádio d = sqrt(2 * (4/3) * R * h), ou d ~ 4,12 * sqrt(h) km com h em metros.
"""

#: Coeficiente de refração da propagação óptica (visada de observador).
K_OPTICO = 1.0 / 7.0

#: Coeficiente de refração da propagação de rádio (radar, sensores), Terra de 4/3.
K_RADAR = 0.25

#: Raio médio da Terra (m), usado nas contas do próprio plugin (linha de visada). O GDAL usa o
#: semieixo maior do elipsoide do SRC do MDE (6.378.137 m no GRS80 e no WGS 84): a diferença na
#: queda é de 0,1 %, menos de 1 cm a 10 km.
R_TERRA = 6371000.0


def coeficiente_curvatura(k):
    """O `dfCurvCoeff` do GDAL para o coeficiente de refração k (1 - k)."""
    return 1.0 - k


def raio_efetivo(k, raio=R_TERRA):
    """Raio da Terra efetiva para o coeficiente de refração k."""
    return raio / (1.0 - k)


def queda(distancia, k, raio=R_TERRA):
    """Queda aparente do terreno (m) à distância horizontal `distancia` (m), curvatura e refração."""
    return distancia * distancia / (2.0 * raio_efetivo(k, raio))


def horizonte(altura, k, raio=R_TERRA):
    """Distância (m) ao horizonte de uma antena ou observador a `altura` m sobre a Terra lisa."""
    from math import sqrt
    return sqrt(2.0 * raio_efetivo(k, raio) * max(0.0, altura))
