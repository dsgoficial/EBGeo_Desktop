# -*- coding: utf-8 -*-
"""
Estilos das feições comuns do mapa 2D do EBGeo Web no QGIS, lidos das colunas
promovidas do calco (schema.py) por propriedades definidas por dado.

Tipos: point, line, polygon, circle, ellipse, rectangle, sector, text, image,
brush, los, visibility, processed_los, processed_visibility. `aplicar_estilo`
devolve False para tipo que não é daqui. `estilo_simples` é o estilo de
reserva dos tipos militares quando estilos_taticos ou estilos_pontuais ainda
não existem: linha pelo eixo e bitmap do arquivo como marcador raster.

Unidades (ANALISE_IMPORTACAO_EBGEO.md, seção 7):
- lineWidth do Web é px fixo na tela: vira milímetros a 0,2646 mm/px;
- tamanho com correção de zoom ligada é fixo NO TERRENO: vira metros pela
  convenção MapLibre de 512 px, m/px = 78271,517 · cos(lat) / 2^z, com
  z = createdAtZoom. A CONFIRMAR lado a lado com o Web: o próprio ebgeo_web
  usa 256 px (156543,03392) no KMZ, e só uma das duas reproduz a tela.
"""
import os

from qgis.core import (
    Qgis, QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer, QgsSimpleMarkerSymbolLayer, QgsRasterMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer, QgsLinePatternFillSymbolLayer, QgsPointPatternFillSymbolLayer,
    QgsProperty, QgsSymbolLayer, QgsSymbol, QgsRuleBasedRenderer, QgsSingleSymbolRenderer,
    QgsNullSymbolRenderer, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsTextBackgroundSettings, QgsVectorLayerSimpleLabeling, QgsRuleBasedLabeling,
)
from qgis.PyQt.QtGui import QColor, QFont

try:
    from .zoom import M_POR_PX_Z0
except ImportError:  # zoom.py é de outro módulo; a constante é a mesma
    M_POR_PX_Z0 = 78271.517

MM_POR_PX = 25.4 / 96  # um pixel lógico (CSS) a 96 dpi: 0,2646 mm
FONTE = 'Noto Sans'

TIPOS = ('point', 'line', 'polygon', 'circle', 'ellipse', 'rectangle', 'sector', 'text', 'image',
         'brush', 'los', 'visibility', 'processed_los', 'processed_visibility')
FORMAS = ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')

# Padrões de traço do Web, em múltiplos da largura (LINE_STYLE_DASHARRAY, layer.helpers.js).
TRACOS = {
    'dashed': (8, 4), 'dotted': (2, 3), 'dash-dot': (8, 4, 2, 4), 'long-dash': (16, 6),
    'short-dash': (4, 4), 'dot-dot-dash': (2, 2, 2, 2, 8, 2),
}
FORMAS_MARCADOR = {  # markerSymbol do Web -> forma do QgsSimpleMarkerSymbolLayer
    'circle': 'circle', 'square': 'square', 'diamond': 'diamond', 'triangle': 'triangle',
    'star': 'star', 'cross': 'cross_fill', 'x-mark': 'cross_fill',
}

# Ícones de ponto do Web, desenhados em branco sobre o círculo da cor de preenchimento.
# Caminhos SVG (viewBox 0 0 100 100) copiados de ICON_PATH_DATA em
# frontend/src/js/draw_tools/point_tool/point-marker-symbols.js do ebgeo_web.
ICONES_WEB = {
    'car': {'paths': ['M73.716,49.418c-0.204-1.99-0.204-1.703-0.954-3.857c-0.765-2.183-2.379-6.455-3.533-8.981c-1.183-2.555-2.435-4.737-3.348-6.083c-0.906-1.344-1.147-1.459-2.003-1.831c-0.886-0.38-2.019-0.315-3.151-0.387c-1.124-0.101-2.301-0.15-3.554-0.15h-14.27c-1.281,0-2.485,0.049-3.611,0.15c-1.139,0.071-2.3,0.007-3.157,0.386c-0.87,0.371-1.118,0.487-2.003,1.832c-0.935,1.346-2.166,3.528-3.342,6.083c-1.168,2.527-2.782,6.799-3.532,8.981c-0.757,2.155-0.785,1.869-0.962,3.858c-0.191,2.003-0.553,5.804-0.185,7.922c0.348,2.047,1.211,3.436,2.287,4.437c1.068,0.995,2.428,1.511,4.105,1.547c-0.092,2.111-0.092,3.742,0,4.922c0.049,1.168-0.036,1.684,0.481,2.126c0.523,0.424,1.862,0.444,2.676,0.479c0.8,0.051,1.664,0.028,2.102-0.286c0.411-0.357,0.291-0.63,0.375-1.84c0.071-1.245,0.113-3.048,0.099-5.495h23.395c0.058,2.447,0.129,4.25,0.242,5.495c0.092,1.21-0.036,1.482,0.381,1.84c0.433,0.314,1.27,0.337,2.096,0.286c0.793-0.035,2.131-0.056,2.676-0.479c0.496-0.442,0.411-0.958,0.481-2.126c0.078-1.18,0.078-2.813,0-4.922c1.671-0.036,3.03-0.552,4.106-1.547c1.068-1.001,1.926-2.39,2.294-4.437C74.234,55.222,73.915,51.421,73.716,49.418z M33.042,58.107c-2.478,0-4.488-2.032-4.488-4.536c0-2.506,2.01-4.538,4.488-4.538c2.477,0,4.488,2.032,4.488,4.538C37.53,56.075,35.519,58.107,33.042,58.107z M56.384,57.238H43.635c-1.332,0-2.411-0.735-2.411-1.642s1.08-1.642,2.411-1.642h12.749c1.332,0,2.411,0.735,2.411,1.642S57.716,57.238,56.384,57.238z M56.384,52.795H43.635c-1.332,0-2.411-0.734-2.411-1.639c0-0.905,1.08-1.638,2.411-1.638h12.749c1.332,0,2.411,0.733,2.411,1.638C58.795,52.061,57.716,52.795,56.384,52.795z M58.426,44.208c-3.717,0.014-13.322,0.014-16.996,0c-3.646-0.029-3.327,0.029-4.778-0.1c-1.466-0.13-3.178-0.251-3.915-0.673c-0.736-0.458-0.652-0.974-0.481-1.933c0.177-0.981,0.792-2.433,1.437-3.864c0.623-1.46,1.536-3.607,2.195-4.731c0.623-1.13,0.927-1.517,1.62-1.932c0.687-0.421,1.544-0.485,2.486-0.58c0.92-0.121,1.939-0.143,3.058-0.094h13.911c1.111-0.049,2.131-0.027,3.058,0.094c0.92,0.093,1.776,0.157,2.484,0.58c0.688,0.416,0.963,0.802,1.622,1.932c0.658,1.124,1.557,3.271,2.2,4.731c0.603,1.432,1.261,2.883,1.43,3.864c0.156,0.958,0.241,1.474-0.48,1.933c-0.757,0.422-2.436,0.544-3.914,0.673C61.874,44.237,62.086,44.179,58.426,44.208z M66.973,58.107c-2.477,0-4.488-2.032-4.488-4.536c0-2.506,2.012-4.538,4.488-4.538s4.488,2.032,4.488,4.538C71.461,56.075,69.45,58.107,66.973,58.107z'], 'tx': 0, 'ty': 0},
    'drone': {'paths': ['M29.1901705,12.5343244 C30.1591197,13.4050355 30.7149987,14.6535155 30.7149987,15.9572787 L30.7149987,27.0431052 C30.7149987,28.3484041 30.1591197,29.5953484 29.1886349,30.4675952 L24.5819034,34.6138387 C23.7035533,35.4046962 22.6010088,35.7993572 21.5,35.7993572 C20.3989912,35.7993572 19.2964467,35.4046962 18.4180966,34.6138387 L13.8113651,30.4675952 C12.8424159,29.5968841 12.2865369,28.3484041 12.2865369,27.0446409 L12.2865369,15.9588143 C12.2865369,14.6535155 12.8424159,13.4065711 13.8129006,12.5343244 L18.4196322,8.38808089 C20.177868,6.80636579 22.8252031,6.80636579 24.583439,8.38808089 L29.1901705,12.5343244 Z M1.53903223,10.7514397 C1.93213999,10.7514397 2.32524775,10.6009464 2.6246853,10.3014955 L5.37797518,7.54808267 L10.168976,12.3392974 C10.5835818,11.5684032 11.0980002,10.8481853 11.7613695,10.2508192 L12.1099455,9.93754743 L7.54928131,5.37667961 L10.3025712,2.62173117 C10.9029819,2.02129369 10.9029819,1.04922995 10.3025712,0.45032811 C9.70216052,-0.15010937 8.73167574,-0.15010937 8.13126507,0.45032811 L0.453379163,8.13009241 C-0.147031515,8.73052989 -0.147031515,9.70259363 0.453379163,10.3014955 C0.752816713,10.6009464 1.14592447,10.7514397 1.53903223,10.7514397 Z M31.2432372,10.2508192 C31.9066066,10.8466497 32.4194893,11.5668676 32.8340952,12.3377617 L37.6235604,7.54808267 L40.3768503,10.3014955 C40.6762878,10.6009464 41.0693956,10.7514397 41.4625033,10.7514397 C41.8556111,10.7514397 42.2487189,10.6009464 42.5481564,10.3014955 C43.1485671,9.70105799 43.1485671,8.72899424 42.5481564,8.13009241 L34.8687349,0.451863756 C34.2683243,-0.148573724 33.2978395,-0.148573724 32.6974288,0.451863756 C32.0970181,1.05230124 32.0970181,2.02436498 32.6974288,2.62326682 L35.4522543,5.37667961 L30.8931256,9.93601179 L31.2432372,10.2508192 Z M11.7582984,32.7495648 C11.094929,32.1537342 10.5820462,31.4335164 10.1674404,30.6626222 L5.3764396,35.4538369 L2.62161414,32.7004241 C2.02120346,32.0999866 1.05071869,32.0999866 0.450308008,32.7004241 C-0.150102669,33.3008616 -0.150102669,34.2729253 0.450308008,34.8718272 L8.12972949,42.5500558 C8.42916704,42.8495067 8.8222748,43 9.21538256,43 C9.60849031,43 10.0015981,42.8495067 10.3010356,42.5500558 C10.9014463,41.9496183 10.9014463,40.9775546 10.3010356,40.3786527 L7.54774574,37.6252399 L12.10841,33.0643721 L11.7582984,32.7495648 L11.7582984,32.7495648 Z M40.3783859,32.6988884 L37.625096,35.4538369 L32.8356307,30.6641579 C32.4210249,31.435052 31.9066066,32.1552699 31.2432372,32.752636 L30.8946612,33.0659078 L35.4537898,37.6252399 L32.7005,40.3786527 C32.1000893,40.9790902 32.1000893,41.951154 32.7005,42.5500558 C32.9999375,42.8495067 33.3930453,43 33.786153,43 C34.1792608,43 34.5723685,42.8495067 34.8718061,42.5500558 L42.549692,34.8702915 C43.1501027,34.269854 43.1501027,33.2977903 42.549692,32.6988884 C41.9492813,32.098451 40.9787965,32.098451 40.3783859,32.6988884 L40.3783859,32.6988884 Z'], 'tx': 28, 'ty': 27},
    'fire': {'paths': ['M68.621,43.951c-8.432-1.103-11.11,3.58-11.11,4.96s-3.042-13.893,5.991-17.506c-8.732,1.204-14.353,6.223-14.353,11.342c0-9.636,1.205-18.268,7.728-22.483c-16.159,1.205-40.651,49.384-12.948,53.6c29.967,4.561,20.778-21.254,20.778-21.254S63.603,46.586,68.621,43.951z M46.614,70.354c-15.453-2.381-14.03-19.188-1.792-24.416c-1.494,4.425-2.849,9.382,1.969,13.106c0-2.854,3.259-7.456,8.13-8.129c-2.408,4.817-1.443,10.047-0.729,10.335c1.634,0.655,3.439,1.559,8.209-4.581C64.255,66.572,57.581,72.043,46.614,70.354z'], 'tx': 0, 'ty': 0},
    'gun': {'paths': ['M74.667,41.78v-4.892c0-0.605-0.495-1.097-1.1-1.097H32.033c-0.605,0-1.099,0.492-1.099,1.097v4.892c0,0.487,0.32,0.904,0.761,1.045h-0.103c-0.604,0-1.097,0.493-1.097,1.1v1.428c0,0.604,0.494,1.096,1.097,1.096h0.084c0.355,0.245,3.887,2.784,3.103,6.925c-0.825,4.354-9.889,14.835-3.625,14.835h10.053c0,0,2.424-8.032,4.761-14.331v0.037h10.96c0.067,0.006,0.214,0.012,0.411,0.012c0.392,0,0.978-0.026,1.573-0.22c0.296-0.094,0.601-0.235,0.876-0.464c0.274-0.229,0.51-0.563,0.608-0.969c0.066-0.269,0.256-0.831,0.494-1.478c0.358-0.977,0.831-2.179,1.216-3.131c0.196-0.492,0.37-0.916,0.491-1.217h10.969c0.604,0,1.098-0.492,1.098-1.096v-1.428c0-0.524-0.369-0.964-0.859-1.071C74.295,42.742,74.667,42.302,74.667,41.78z M60.371,48.158c-0.281,0.72-0.575,1.48-0.82,2.146c-0.246,0.669-0.441,1.233-0.538,1.624c-0.026,0.093-0.06,0.146-0.145,0.217c-0.124,0.108-0.384,0.22-0.683,0.279c-0.296,0.058-11.69,0.061-11.69,0.061c1.292-3.346,2.496-5.92,3.173-6.015c0.05-0.006,0.086-0.016,0.108-0.022h1.207c-0.141,0.674-0.502,3.159,1.578,4.391c2.419,1.429,0.606-0.826,0.164-1.485c-0.425-0.642-0.802-2.118-0.11-2.906h8.441C60.863,46.923,60.622,47.524,60.371,48.158z'], 'tx': 0, 'ty': 0},
    'news': {'paths': ['M75.226,44.4c-1.722-10.877-6.545-19.173-10.741-18.498c-1.857,0.285-3.29,2.258-4.168,5.294c-1.82,1.618-4.603,3.304-7.771,4.906l1.734,3.541l5.396-2.647c-0.152,0.743-0.27,1.585-0.337,2.498c0.017,2.309,0.219,4.771,0.623,7.317c0.439,2.799,1.08,5.43,1.873,7.757c0.271,0.556,0.558,1.046,0.859,1.467l-7.282-0.69l-0.304,3.236c3.658,0.423,7.046,1.18,9.661,2.429c1.854,2.968,3.964,4.64,5.95,4.317C74.922,64.669,76.944,55.293,75.226,44.4z M66.234,55.832c-1.129,0.186-2.714-3.947-3.558-9.208c-0.826-5.245-0.59-9.663,0.538-9.848c1.131-0.168,2.732,3.946,3.561,9.208C67.601,51.245,67.364,55.646,66.234,55.832z', 'M51.16,36.778l-1.552,0.742c-7.874,3.642-16.913,6.661-19.426,7.504c-0.033,0.017-0.05,0.017-0.084,0.017c-3.473,0.54-5.936,3.524-5.936,6.93c0,0.354,0.034,0.726,0.084,1.097c0.608,3.777,4.131,6.39,7.925,5.851l1.603,9.26c0.286,0.808,1.028,1.938,2.714,1.651l3.339-0.287c1.686-0.304,1.939-1.029,1.653-2.716l-1.4-8.582c3.996-0.188,8.853-0.256,13.457,0.167c0.521,0.051,1.063,0.103,1.567,0.169l0.304-3.236l-1.567-0.152L43.47,54.213c0,0,0,0-0.018,0.001c-1.096,0.085-2.176-0.54-2.9-1.584c-0.438-0.625-0.758-1.4-0.894-2.261c-0.05-0.303-0.066-0.588-0.066-0.875c0-0.456,0.05-0.894,0.167-1.299c0.355-1.399,1.282-2.445,2.497-2.648l9.106-4.47l2.917-1.433l-1.736-3.541C52.088,36.323,51.631,36.56,51.16,36.778z'], 'tx': 0, 'ty': 0},
    'plane': {'paths': ['M75.256,38.772H55.284c0-0.003,0-0.007,0-0.01v-0.941h-0.008c-0.021-0.146-0.083-0.317-0.177-0.501c-0.211-1.695-0.657-4.573-1.447-7.065h7.854c0.558,0,1.01-0.451,1.01-1.008c0-0.558-0.452-1.009-1.01-1.009H52.88c-0.743-1.589-1.695-2.714-2.903-2.714c-1.221,0-2.157,1.124-2.871,2.714h-8.41c-0.558,0-1.009,0.451-1.009,1.009c0,0.557,0.451,1.008,1.009,1.008h7.676c-0.779,2.617-1.164,5.659-1.325,7.312c-0.029,0.087-0.052,0.17-0.063,0.243l-0.006,0.517c0,0.003,0,0.006,0,0.008l-0.002,0.379l-0.001,0.049v0.009H24.946c-2.148,0-3.83,1.33-3.83,3.026v4.931c0,1.67,1.631,2.984,3.73,3.026l20.925,3.962c0.216,2.189,0.465,4.479,0.731,6.706l-8.028,1.118v5.982l8.767,0.751c0.028,0.002,0.058,0.004,0.086,0.004c0.057,0,0.107-0.021,0.162-0.031c-0.002,0.227-0.007,0.451-0.007,0.683c0,1.318,0.059,2.568,0.164,3.521c0.105,0.946,0.35,3.161,2.37,3.161s2.265-2.215,2.37-3.161c0.085-0.765,0.138-1.724,0.154-2.753c0.075-0.44,0.152-0.92,0.231-1.435c0.027,0.002,0.048,0.015,0.074,0.015c0.028,0,0.056-0.001,0.085-0.003l8.939-0.75v-5.985l-8.088-1.103c0-0.002,0-0.003,0-0.004c0.25-2.21,0.487-4.511,0.693-6.726l20.88-3.953c2.1-0.042,3.73-1.354,3.73-3.026v-4.931C79.086,40.102,77.404,38.772,75.256,38.772z M46.992,38.133c0.21-0.331,1.123-1.564,3.014-1.564c1.725,0,2.816,1.027,3.191,1.506c0.013,0.13,0.021,0.252,0.028,0.365c-0.332-0.02-0.775-0.104-1.209-0.186c-0.606-0.116-1.232-0.237-1.796-0.237c-0.558,0-1.199,0.122-1.817,0.239c-0.51,0.098-1.04,0.198-1.412,0.205L46.992,38.133z'], 'tx': 0, 'ty': 0},
    'supply': {'paths': ['M26.839,34.492v29.016L50,72.713l23.161-9.205V34.492L50,25.288L26.839,34.492z M65.711,36.235L50,42.48l-15.711-6.245L50,29.991L65.711,36.235z M31.211,39.717l16.603,6.598v20.826l-16.603-6.599V39.717z M52.186,67.139V46.314l16.604-6.597v20.825L52.186,67.139z', 'M55.324,35.663v1.21c0,0.157-0.203,0.289-0.456,0.289h-3.494v2.272c0,0.165-0.202,0.289-0.443,0.289h-1.86c-0.241,0-0.444-0.124-0.444-0.289v-2.272h-3.493c-0.253,0-0.456-0.132-0.456-0.289v-1.21c0-0.164,0.203-0.288,0.456-0.288h3.493v-2.28c0-0.157,0.203-0.289,0.444-0.289h1.86c0.241,0,0.443,0.132,0.443,0.289v2.28h3.494C55.121,35.375,55.324,35.499,55.324,35.663z'], 'tx': 0, 'ty': 0},
}

# condição de tamanho fixo no terreno (correção de zoom ligada e zoom de criação conhecido)
COND_ZOOM = 'coalesce("zoom_corr", false) AND "created_zoom" IS NOT NULL'


def _mm(expr_px):
    return '(({}) * {})'.format(expr_px, MM_POR_PX)


def _metros(expr_px, zoom='"created_zoom"'):
    return '(({}) * {} * cos(radians(y(centroid(@geometry)))) / (2 ^ ({})))'.format(expr_px, M_POR_PX_Z0, zoom)


def _p(expr):
    return QgsProperty.fromExpression(expr)


def _sql_str(s):
    return "'" + str(s).replace("'", "''") + "'"


def _cor_alfa(expr_cor, expr_alfa, padrao='#3388ff'):
    """Expressão de cor com alfa 0..1 aplicado (o Web usa a opacidade só no preenchimento)."""
    return ("set_color_part(coalesce({c}, '{p}'), 'alpha', 255 * coalesce({a}, 1))"
            .format(c=expr_cor, p=padrao, a=expr_alfa))


def _expr_traco(largura_px_expr):
    casos = ' '.join("WHEN \"line_style\" = '{}' THEN '{}'".format(k, ';'.join(str(x) for x in v))
                     for k, v in TRACOS.items())
    return ("array_to_string(array_foreach(string_to_array(CASE {casos} ELSE '1;0' END, ';'), "
            "to_real(@element) * {w}), ';')").format(casos=casos, w=_mm(largura_px_expr))


def _linhas_com_traco(cor_expr, largura_px_expr, unidade=Qgis.RenderUnit.Millimeters, opacidade_expr=None):
    """Dois símbolos de linha: contínuo e tracejado, ligados por line_style."""
    cor = _cor_alfa(cor_expr, opacidade_expr) if opacidade_expr else cor_expr
    camadas = []
    for tracejado in (False, True):
        sl = QgsSimpleLineSymbolLayer()
        sl.setWidthUnit(unidade)
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_mm(largura_px_expr)))
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p(cor))
        sl.setPenCapStyle(_qt_cap('flat'))
        sl.setPenJoinStyle(_qt_join('round'))
        cond = "coalesce(\"line_style\", 'solid') IN ({})".format(', '.join(_sql_str(k) for k in TRACOS))
        if tracejado:
            sl.setUseCustomDashPattern(True)
            sl.setCustomDashPatternUnit(Qgis.RenderUnit.Millimeters)
            sl.setDataDefinedProperty(QgsSymbolLayer.Property.CustomDash, _p(_expr_traco(largura_px_expr)))
            sl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(cond))
        else:
            sl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('NOT ({})'.format(cond)))
        camadas.append(sl)
    return camadas


def _qt_cap(nome):
    from qgis.PyQt.QtCore import Qt
    return {'flat': Qt.PenCapStyle.FlatCap, 'round': Qt.PenCapStyle.RoundCap}[nome]


def _qt_join(nome):
    from qgis.PyQt.QtCore import Qt
    return {'round': Qt.PenJoinStyle.RoundJoin, 'miter': Qt.PenJoinStyle.MiterJoin}[nome]


def _simbolo_limpo(classe):
    s = classe()
    while s.symbolLayerCount():
        s.deleteSymbolLayer(0)
    return s


def _regras_por_zoom(fabrica, rotulo=''):
    """Renderer por regra: tamanho no terreno (metros) ou na tela (mm), conforme a correção de zoom."""
    raiz = QgsRuleBasedRenderer.Rule(None)
    for terreno in (True, False):
        sim = fabrica(terreno)
        regra = QgsRuleBasedRenderer.Rule(sim, 0, 0, COND_ZOOM if terreno else 'NOT ({})'.format(COND_ZOOM),
                                          (rotulo + (' (tamanho no terreno)' if terreno else ' (tamanho na tela)')).strip())
        raiz.appendChild(regra)
    return QgsRuleBasedRenderer(raiz)


def _tamanho(expr_px, terreno, zoom='"created_zoom"'):
    return _metros(expr_px, zoom) if terreno else _mm(expr_px)


def _unidade(terreno):
    return Qgis.RenderUnit.MetersInMapUnits if terreno else Qgis.RenderUnit.Millimeters


def _caminho_gpkg(layer):
    src = layer.source().split('|')[0]
    return src if os.path.isfile(src) else None


def _icones(layer):
    """icone_id -> (mime, base64) da tabela ebgeo_icone do mesmo GeoPackage."""
    caminho = _caminho_gpkg(layer)
    if not caminho:
        return {}
    try:
        from osgeo import ogr
        ds = ogr.Open(caminho)
        lyr = ds.GetLayerByName('ebgeo_icone') if ds else None
        out = {}
        if lyr is not None:
            for f in lyr:
                if f.GetField('icone_id') and f.GetField('bitmap_b64'):
                    out[f.GetField('icone_id')] = (f.GetField('mime'), f.GetField('bitmap_b64'))
        ds = None
        return out
    except Exception:
        return {}


# ---------------------------------------------------------------- ponto

RAZAO_DESENHO = 40.0 / 48.0  # POINT_IMAGE_INNER_PX / POINT_IMAGE_HALF_PX do Web


def _svg_icone_b64(nome):
    import base64
    d = ICONES_WEB[nome]
    caminhos = ''.join('<path fill="#ffffff" d="{}"/>'.format(c) for c in d['paths'])
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">'
           '<g transform="translate({},{})">{}</g></svg>').format(d['tx'], d['ty'], caminhos)
    return base64.b64encode(svg.encode('utf-8')).decode('ascii')


def _estilo_ponto(layer):
    icones = _icones(layer)
    formas = ' '.join("WHEN \"marker_symbol\" = '{}' THEN '{}'".format(k, v) for k, v in FORMAS_MARCADOR.items())
    custom_ok = ['custom:' + i for i in icones]
    cond_custom = '"marker_symbol" IN ({})'.format(', '.join(_sql_str(c) for c in custom_ok)) if custom_ok else 'false'

    def fabrica(terreno):
        s = _simbolo_limpo(QgsMarkerSymbol)
        sm = QgsSimpleMarkerSymbolLayer()
        sm.setSizeUnit(_unidade(terreno))
        sm.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.Name,
                                  _p("CASE {} ELSE 'circle' END".format(formas)))
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.Angle,
                                  _p("CASE WHEN \"marker_symbol\" = 'x-mark' THEN 45 ELSE 0 END"))
        # círculo nativo: raio = size; forma e ícone: o desenho ocupa INNER/HALF (40/48) da imagem
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.Size, _p(_tamanho(
            "2 * coalesce(\"size\", 10) * if(coalesce(\"marker_symbol\", 'circle') = 'circle', 1, {})".format(
                RAZAO_DESENHO), terreno)))
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p("coalesce(\"fill_color\", '#3388ff')"))
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p("coalesce(\"line_color\", '#ffffff')"))
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_mm('coalesce("line_width", 0)')))
        sm.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('NOT ({})'.format(cond_custom)))
        s.appendSymbolLayer(sm)
        # glifo branco do ícone (car, drone, fire, gun, news, plane, supply)
        gl = QgsSvgMarkerSymbolLayer('')
        gl.setSizeUnit(_unidade(terreno))
        casos_gl = ' '.join("WHEN \"marker_symbol\" = '{}' THEN 'base64:{}'".format(k, _svg_icone_b64(k))
                            for k in ICONES_WEB)
        gl.setDataDefinedProperty(QgsSymbolLayer.Property.Name, _p('CASE {} END'.format(casos_gl)))
        gl.setDataDefinedProperty(QgsSymbolLayer.Property.Size, _p(_tamanho('2 * coalesce("size", 10)', terreno)))
        gl.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('"marker_symbol" IN ({})'.format(
            ', '.join(_sql_str(k) for k in ICONES_WEB))))
        s.appendSymbolLayer(gl)
        if icones:
            rm = QgsRasterMarkerSymbolLayer('')
            rm.setSizeUnit(_unidade(terreno))
            rm.setFixedAspectRatio(0)
            casos = ' '.join("WHEN \"marker_symbol\" = 'custom:{}' THEN 'base64:{}'".format(i, b64)
                             for i, (_m, b64) in icones.items())
            rm.setDataDefinedProperty(QgsSymbolLayer.Property.Name, _p('CASE {} END'.format(casos)))
            rm.setDataDefinedProperty(QgsSymbolLayer.Property.Width, _p(_tamanho('2 * coalesce("size", 10)', terreno)))
            rm.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(cond_custom))
            s.appendSymbolLayer(rm)
        s.setDataDefinedProperty(QgsSymbol.Property.Opacity, _p('100 * coalesce("opacity", 1)'))
        return s

    layer.setRenderer(_regras_por_zoom(fabrica, 'Ponto'))
    _rotulo_forma(layer, ponto=True)


def _rotulo_forma(layer, ponto=False):
    """Rótulo de ponto e de forma: label_text em Noto Sans Bold, halo label_outline_*."""
    s = QgsPalLayerSettings()
    s.fieldName = 'label_text'
    s.isExpression = False
    fmt = QgsTextFormat()
    f = QFont(FONTE)
    f.setBold(True)
    fmt.setFont(f)
    fmt.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setSize(14 * MM_POR_PX)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setBuffer(buf)
    s.setFormat(fmt)
    dd = s.dataDefinedProperties()
    dd.setProperty(QgsPalLayerSettings.Property.Show,
                   _p("coalesce(\"show_label\", false) AND coalesce(\"label_text\", '') <> ''"))
    dd.setProperty(QgsPalLayerSettings.Property.Size, _p(_mm('coalesce("label_size", 14)')))
    dd.setProperty(QgsPalLayerSettings.Property.Color, _p("coalesce(\"label_color\", '#ffffff')"))
    dd.setProperty(QgsPalLayerSettings.Property.BufferColor, _p("coalesce(\"label_outline_color\", '#000000')"))
    dd.setProperty(QgsPalLayerSettings.Property.BufferSize, _p(_mm('coalesce("label_outline_width", 2)')))
    if ponto:
        s.placement = Qgis.LabelPlacement.OverPoint
        s.quadOffset = Qgis.LabelQuadrantPosition.AboveRight
        s.offsetUnits = Qgis.RenderUnit.Millimeters
        # deslocamento radial do Web: raio do marcador + 6 px, na diagonal
        dd.setProperty(QgsPalLayerSettings.Property.OffsetXY, _p(
            "concat({d}, ',', -{d})".format(d=_mm('(coalesce("size", 10) + coalesce("line_width", 0) + 6) * 0.7071'))))
    else:
        s.placement = Qgis.LabelPlacement.OverPoint if layer.geometryType() == Qgis.GeometryType.Point \
            else Qgis.LabelPlacement.Horizontal
        try:
            s.centroidInside = True
        except AttributeError:
            pass
    s.setDataDefinedProperties(dd)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(s))
    layer.setLabelsEnabled(True)


# ---------------------------------------------------------------- linha, pincel, visada

def _estilo_linha(layer):
    s = _simbolo_limpo(QgsLineSymbol)
    for sl in _linhas_com_traco("coalesce(\"line_color\", '#3388ff')", 'coalesce("line_width", 3)'):
        s.appendSymbolLayer(sl)
    s.setDataDefinedProperty(QgsSymbol.Property.Opacity, _p('100 * coalesce("opacity", 1)'))
    layer.setRenderer(QgsSingleSymbolRenderer(s))


def _estilo_pincel(layer):
    def fabrica(terreno):
        s = _simbolo_limpo(QgsLineSymbol)
        sl = QgsSimpleLineSymbolLayer()
        sl.setWidthUnit(_unidade(terreno))
        sl.setPenCapStyle(_qt_cap('round'))
        sl.setPenJoinStyle(_qt_join('round'))
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_tamanho('coalesce("line_width", 5)', terreno)))
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p("coalesce(\"line_color\", '#ff0000')"))
        s.appendSymbolLayer(sl)
        return s
    layer.setRenderer(_regras_por_zoom(fabrica, 'Pincel'))


def _estilo_los(layer):
    """Entrada da linha de visada: o Web a desenha com opacidade zero. A árvore a deixa desligada."""
    s = _simbolo_limpo(QgsLineSymbol)
    sl = QgsSimpleLineSymbolLayer(QColor('#808080'), 0.4)
    sl.setPenStyle(_qt_pen('dash'))
    s.appendSymbolLayer(sl)
    layer.setRenderer(QgsSingleSymbolRenderer(s))


def _qt_pen(nome):
    from qgis.PyQt.QtCore import Qt
    return {'dash': Qt.PenStyle.DashLine, 'none': Qt.PenStyle.NoPen, 'solid': Qt.PenStyle.SolidLine}[nome]


def _estilo_processed_los(layer):
    s = _simbolo_limpo(QgsLineSymbol)
    sl = QgsSimpleLineSymbolLayer()
    sl.setWidthUnit(Qgis.RenderUnit.Millimeters)
    sl.setPenCapStyle(_qt_cap('round'))
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p("coalesce(\"color\", '#00FF00')"))
    sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_mm(
        "coalesce(to_real(map_get(json_to_map(to_json(\"parametros\")), 'width')), 4)")))
    s.appendSymbolLayer(sl)
    s.setDataDefinedProperty(QgsSymbol.Property.Opacity, _p('100 * coalesce("opacity", 1)'))
    layer.setRenderer(QgsSingleSymbolRenderer(s))


# ---------------------------------------------------------------- formas

_HACHURAS = [  # (ângulo QGIS, tipos que o ligam)
    (45, ('diagonal-right', 'cross-diagonal')),
    (135, ('diagonal-left', 'cross-diagonal')),
    (0, ('horizontal', 'cross')),
    (90, ('vertical', 'cross')),
]
COND_HACHURA = "coalesce(\"hatch_enabled\", false) AND coalesce(\"hatch_type\", 'none') <> 'none'"


def _estilo_forma(layer):
    s = _simbolo_limpo(QgsFillSymbol)
    # preenchimento liso: opacidade só aqui (polygon.layers.js:72)
    fill = QgsSimpleFillSymbolLayer()
    fill.setStrokeStyle(_qt_pen('none'))
    fill.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor,
                                _p(_cor_alfa('"fill_color"', '"opacity"')))
    fill.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p('NOT ({})'.format(COND_HACHURA)))
    s.appendSymbolLayer(fill)
    # hachura: cor do preenchimento (hatchColor é só reserva), com a mesma opacidade
    cor_h = _cor_alfa('coalesce("fill_color", "hatch_color")', '"opacity"', '#000000')
    for ang, tipos in _HACHURAS:
        lp = QgsLinePatternFillSymbolLayer()
        lp.setLineAngle(ang)
        lp.setDistanceUnit(Qgis.RenderUnit.Millimeters)
        lp.setDataDefinedProperty(QgsSymbolLayer.Property.LineDistance, _p(_mm('coalesce("hatch_spacing", 8)')))
        sub = _simbolo_limpo(QgsLineSymbol)
        ln = QgsSimpleLineSymbolLayer()
        ln.setWidthUnit(Qgis.RenderUnit.Millimeters)
        ln.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_mm('coalesce("hatch_line_width", 2)')))
        ln.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p(cor_h))
        sub.appendSymbolLayer(ln)
        lp.setSubSymbol(sub)
        lp.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(
            "{} AND \"hatch_type\" IN ({})".format(COND_HACHURA, ', '.join(_sql_str(t) for t in tipos))))
        s.appendSymbolLayer(lp)
    pp = QgsPointPatternFillSymbolLayer()
    pp.setDistanceXUnit(Qgis.RenderUnit.Millimeters)
    pp.setDistanceYUnit(Qgis.RenderUnit.Millimeters)
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.DistanceX, _p(_mm('coalesce("hatch_spacing", 8)')))
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.DistanceY, _p(_mm('coalesce("hatch_spacing", 8)')))
    msub = _simbolo_limpo(QgsMarkerSymbol)
    dot = QgsSimpleMarkerSymbolLayer()
    dot.setStrokeStyle(_qt_pen('none'))
    dot.setSizeUnit(Qgis.RenderUnit.Millimeters)
    dot.setDataDefinedProperty(QgsSymbolLayer.Property.Size, _p(_mm('coalesce("hatch_line_width", 2)')))
    dot.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p(cor_h))
    msub.appendSymbolLayer(dot)
    pp.setSubSymbol(msub)
    pp.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p("{} AND \"hatch_type\" = 'dots'".format(COND_HACHURA)))
    s.appendSymbolLayer(pp)
    # contorno com opacidade 1 (polygon.layers.js:117)
    for sl in _linhas_com_traco("coalesce(\"line_color\", '#3388ff')", 'coalesce("line_width", 2)'):
        s.appendSymbolLayer(sl)
    layer.setRenderer(QgsSingleSymbolRenderer(s))
    _rotulo_forma(layer)


def _estilo_visibilidade(layer, processado):
    s = _simbolo_limpo(QgsFillSymbol)
    fill = QgsSimpleFillSymbolLayer()
    if processado:
        fill.setStrokeStyle(_qt_pen('none'))
        fill.setDataDefinedProperty(QgsSymbolLayer.Property.FillColor, _p(_cor_alfa('"color"', '"opacity"', '#00FF00')))
    else:
        fill.setColor(QColor(0, 0, 0, 0))
        fill.setStrokeColor(QColor('#808080'))
        fill.setStrokeWidth(0.3)
        fill.setStrokeStyle(_qt_pen('dash'))
    s.appendSymbolLayer(fill)
    layer.setRenderer(QgsSingleSymbolRenderer(s))


# ---------------------------------------------------------------- texto

def _formato_texto(terreno):
    fmt = QgsTextFormat()
    fmt.setFont(QFont(FONTE))
    fmt.setSizeUnit(_unidade(terreno))
    fmt.setSize(16 * MM_POR_PX)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSizeUnit(Qgis.RenderUnit.Millimeters)
    fmt.setBuffer(buf)
    bg = QgsTextBackgroundSettings()
    bg.setEnabled(True)
    bg.setSizeType(QgsTextBackgroundSettings.SizeType.SizeBuffer)
    bg.setSizeUnit(Qgis.RenderUnit.Millimeters)
    bg.setSize(_qsizef(1.5, 1.0))
    bg.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
    fmt.setBackground(bg)
    return fmt


def _qsizef(w, h):
    from qgis.PyQt.QtCore import QSizeF
    return QSizeF(w, h)


def _rotulo_texto(terreno):
    s = QgsPalLayerSettings()
    s.fieldName = 'text'
    s.isExpression = False
    s.placement = Qgis.LabelPlacement.OverPoint
    s.setFormat(_formato_texto(terreno))
    try:
        s.placementSettings().setAllowDegradedPlacement(True)
        s.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapIfRequired)
    except AttributeError:
        pass
    dd = s.dataDefinedProperties()
    dd.setProperty(QgsPalLayerSettings.Property.Size, _p(_tamanho('coalesce("size", 16)', terreno)))
    dd.setProperty(QgsPalLayerSettings.Property.Color, _p("coalesce(\"color\", '#000000')"))
    dd.setProperty(QgsPalLayerSettings.Property.BufferColor, _p("coalesce(\"halo_color\", '#ffffff')"))
    dd.setProperty(QgsPalLayerSettings.Property.BufferSize, _p(_mm('coalesce("halo_width", 1)')))
    dd.setProperty(QgsPalLayerSettings.Property.BufferDraw, _p('coalesce("halo_width", 1) > 0'))
    dd.setProperty(QgsPalLayerSettings.Property.LabelRotation, _p('coalesce("rotation", 0)'))
    dd.setProperty(QgsPalLayerSettings.Property.MultiLineAlignment,
                   _p("CASE WHEN \"justify\" = 'left' THEN 'Left' WHEN \"justify\" = 'right' THEN 'Right' ELSE 'Center' END"))
    dd.setProperty(QgsPalLayerSettings.Property.ShapeDraw, _p('coalesce("show_background", false)'))
    dd.setProperty(QgsPalLayerSettings.Property.ShapeFillColor,
                   _p(_cor_alfa('"bg_fill_color"', '"bg_fill_opacity"', '#ffffff')))
    dd.setProperty(QgsPalLayerSettings.Property.ShapeStrokeColor,
                   _p(_cor_alfa('"bg_border_color"', '"bg_border_opacity"', '#000000')))
    dd.setProperty(QgsPalLayerSettings.Property.ShapeStrokeWidth, _p(_mm('coalesce("bg_border_width", 1)')))
    s.setDataDefinedProperties(dd)
    return s


def _estilo_texto(layer):
    layer.setRenderer(QgsNullSymbolRenderer())
    raiz = QgsRuleBasedLabeling.Rule(None)
    for terreno in (True, False):
        r = QgsRuleBasedLabeling.Rule(_rotulo_texto(terreno))
        r.setFilterExpression(COND_ZOOM if terreno else 'NOT ({})'.format(COND_ZOOM))
        r.setDescription('tamanho no terreno' if terreno else 'tamanho na tela')
        raiz.appendChild(r)
    layer.setLabeling(QgsRuleBasedLabeling(raiz))
    layer.setLabelsEnabled(True)


# ---------------------------------------------------------------- imagem e bitmaps

def _marcador_bitmap(terreno, largura_px_expr, rotacao=True, svg=True):
    """Bitmap do arquivo como marcador raster base64 (e SVG do motor, quando houver)."""
    s = _simbolo_limpo(QgsMarkerSymbol)
    rm = QgsRasterMarkerSymbolLayer('')
    rm.setSizeUnit(_unidade(terreno))
    rm.setFixedAspectRatio(0)
    rm.setDataDefinedProperty(QgsSymbolLayer.Property.Name, _p("'base64:' || \"bitmap_b64\""))
    rm.setDataDefinedProperty(QgsSymbolLayer.Property.Width, _p(_tamanho(largura_px_expr, terreno)))
    if rotacao:
        rm.setDataDefinedProperty(QgsSymbolLayer.Property.Angle, _p('coalesce("rotation", 0)'))
    cond_svg = '"svg" IS NOT NULL' if svg else 'false'
    rm.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled,
                              _p('"bitmap_b64" IS NOT NULL AND NOT ({})'.format(cond_svg)))
    s.appendSymbolLayer(rm)
    if svg:
        sv = QgsSvgMarkerSymbolLayer('')
        sv.setSizeUnit(_unidade(terreno))
        sv.setDataDefinedProperty(QgsSymbolLayer.Property.Name, _p("'base64:' || \"svg\""))  # a coluna svg já é base64 (simbolos.renderizar)
        sv.setDataDefinedProperty(QgsSymbolLayer.Property.Size, _p(_tamanho(largura_px_expr, terreno)))
        sv.setDataDefinedProperty(QgsSymbolLayer.Property.Angle, _p('coalesce("rotation", 0)'))
        sv.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled, _p(cond_svg))
        s.appendSymbolLayer(sv)
    # sem bitmap nem SVG: marcador de erro (losango vermelho vazado), como a imagem de erro do Web
    erro = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.Diamond, 4)
    erro.setColor(QColor(0, 0, 0, 0))
    erro.setStrokeColor(QColor('#d32f2f'))
    erro.setStrokeWidth(0.5)
    erro.setDataDefinedProperty(QgsSymbolLayer.Property.LayerEnabled,
                                _p('"bitmap_b64" IS NULL AND NOT ({})'.format(cond_svg)))
    s.appendSymbolLayer(erro)
    s.setDataDefinedProperty(QgsSymbol.Property.Opacity, _p('100 * coalesce("opacity", 1)'))
    return s


def _estilo_imagem(layer):
    largura = 'coalesce("largura_px", 64) * coalesce("size", 1)'
    layer.setRenderer(_regras_por_zoom(lambda t: _marcador_bitmap(t, largura, svg=False), 'Imagem'))


# ---------------------------------------------------------------- reserva dos tipos militares

_LARGURA_PROPS = "to_real(map_get(json_to_map(to_json(\"props\")), 'width'))"


def estilo_simples(layer, tipo):
    """Estilo de reserva dos tipos militares, sem os renderizadores vivos."""
    if tipo in ('boundary', 'coordination_line', 'occupied_front', 'arrow'):
        s = _simbolo_limpo(QgsLineSymbol)
        cor = '"line_color"' if tipo == 'arrow' else '"color"'
        opac = '"line_opacity"' if tipo == 'arrow' else '"opacity"'
        sl = QgsSimpleLineSymbolLayer()
        sl.setWidthUnit(Qgis.RenderUnit.Millimeters)
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeColor, _p("coalesce({}, '#000000')".format(cor)))
        sl.setDataDefinedProperty(QgsSymbolLayer.Property.StrokeWidth, _p(_mm('coalesce("line_width", 3)')))
        s.appendSymbolLayer(sl)
        s.setDataDefinedProperty(QgsSymbol.Property.Opacity, _p('100 * coalesce({}, 1)'.format(opac)))
        layer.setRenderer(QgsSingleSymbolRenderer(s))
        return True
    if tipo in ('military_symbol', 'coordination_measure', 'engineering_symbol', 'magnetic_declination'):
        padrao = 400 if tipo == 'magnetic_declination' else 60
        largura = 'coalesce("largura_px", {}, {}) * coalesce("size", 1)'.format(_LARGURA_PROPS, padrao)
        layer.setRenderer(_regras_por_zoom(lambda t: _marcador_bitmap(t, largura), tipo))
        return True
    return False


# ---------------------------------------------------------------- entrada

def aplicar_estilo(layer, tipo):
    """Aplica o estilo do tipo à camada. Devolve False se o tipo não é desta família."""
    if tipo == 'point':
        _estilo_ponto(layer)
    elif tipo == 'line':
        _estilo_linha(layer)
    elif tipo in FORMAS:
        _estilo_forma(layer)
    elif tipo == 'text':
        _estilo_texto(layer)
    elif tipo == 'image':
        _estilo_imagem(layer)
    elif tipo == 'brush':
        _estilo_pincel(layer)
    elif tipo == 'los':
        _estilo_los(layer)
    elif tipo == 'processed_los':
        _estilo_processed_los(layer)
    elif tipo in ('visibility', 'processed_visibility'):
        _estilo_visibilidade(layer, tipo == 'processed_visibility')
    else:
        return False
    layer.triggerRepaint()
    return True
