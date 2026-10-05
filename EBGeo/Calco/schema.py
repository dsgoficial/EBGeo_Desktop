# -*- coding: utf-8 -*-
"""
Esquema único do calco do EBGeo Desktop.

É o contrato entre as ferramentas de desenho, os estilos e o importador .ebgeo:
uma tabela por tipo de feição do EBGeo Web, com geometria única e colunas
promovidas a partir das propriedades do Web. Este módulo não importa QGIS,
para poder ser usado e testado em Python puro.

Cada campo é (coluna, tipo, padrão, propriedade_web). A propriedade_web é o
nome em properties do GeoJSON do .ebgeo; None quando a coluna não vem do Web.
Tipos: 'str', 'real', 'int', 'bool', 'json', 'datetime'.

Além das colunas fixas, o importador cria colunas dinâmicas `attr_<chave saneada>` com os
`attributes` livres das feições (o nome original fica como alias do campo); o JSON `atributos`
continua sendo a fonte para o caminho de volta.
"""

CRS = 'EPSG:4326'

# Colunas comuns a toda tabela de feição.
CAMPOS_COMUNS = [
    ('ebgeo_id', 'str', None, 'id'),
    ('mapa', 'str', 'Principal', None),
    ('camada_id', 'str', 'default', 'layerId'),
    ('nome', 'str', '', 'nome'),
    ('descricao', 'str', '', 'descricao'),
    ('visivel', 'bool', True, 'visivel'),
    ('bloqueado', 'bool', False, 'bloqueado'),
    ('grupos', 'json', None, None),
    ('criado_em', 'datetime', None, 'createdAt'),
    ('atualizado_em', 'datetime', None, 'updatedAt'),
    ('atributos', 'json', None, 'attributes'),
    ('props', 'json', None, None),
]

_ZOOM = [
    ('zoom_corr', 'bool', True, 'zoomCorrectionEnabled'),
    ('created_zoom', 'real', None, 'createdAtZoom'),
]

# Azimute e Distância (Calco/azimute): a construção polar que o Web grava em
# properties.azimuthDistanceData das feições de featureType 'azimuth_distance' (ponto, linha ou
# polígono), para a ferramenta reabrir e editar as pernas.
_AZIMUTE = [('azimute_distancia', 'json', None, 'azimuthDistanceData')]

# Símbolos pontuais gerados por SVG (assado no campo svg).
_SIMBOLO = [
    ('size', 'real', 1.0, 'size'),
    ('rotation', 'real', 0.0, 'rotation'),
    ('opacity', 'real', 1.0, 'opacity'),
    ('fill_color', 'str', None, 'fillColor'),
] + _ZOOM + [
    ('svg', 'str', None, None),
    ('svg_assinatura', 'str', None, None),
    ('largura_px', 'real', None, None),
    ('altura_px', 'real', None, None),
    ('ancora_dx', 'real', 0.0, None),
    ('ancora_dy', 'real', 0.0, None),
    ('bitmap_b64', 'str', None, None),
    ('bitmap_mime', 'str', None, None),
]

_LINHA_TATICA = [
    ('color', 'str', '#000000', 'color'),
    ('line_width', 'real', 4.0, 'lineWidth'),
    ('opacity', 'real', 1.0, 'opacity'),
] + _ZOOM + [
    ('geom_desenho', 'str', None, None),
]

_ROTULO = [
    ('show_label', 'bool', False, 'showLabel'),
    ('label_text', 'str', None, 'labelText'),
    ('label_color', 'str', '#000000', 'labelColor'),
    ('label_size', 'real', 14.0, 'labelSize'),
    ('label_outline_color', 'str', '#ffffff', 'labelOutlineColor'),
    ('label_outline_width', 'real', 1.0, 'labelOutlineWidth'),
    ('label_zoom_corr', 'bool', None, 'labelZoomCorrectionEnabled'),
    ('label_created_zoom', 'real', None, 'labelCreatedAtZoom'),
]

_FORMA = [
    ('fill_color', 'str', '#3388ff', 'fillColor'),
    ('line_color', 'str', '#3388ff', 'lineColor'),
    ('line_width', 'real', 2.0, 'lineWidth'),
    ('line_style', 'str', 'solid', 'lineStyle'),
    ('opacity', 'real', 0.3, 'opacity'),
    ('hatch_enabled', 'bool', False, 'hatchEnabled'),
    ('hatch_type', 'str', 'none', 'hatchType'),
    ('hatch_color', 'str', None, 'hatchColor'),
    ('hatch_spacing', 'real', None, 'hatchSpacing'),
    ('hatch_line_width', 'real', None, 'hatchLineWidth'),
] + _ROTULO + [
    ('parametros', 'json', None, None),
]

AMPLIFICADORES = [
    # coluna, propriedade do Web
    ('unique_designation', 'uniqueDesignation'),
    ('higher_formation', 'higherFormation'),
    ('quantity', 'quantity'),
    ('reinforced_reduced', 'reinforcedReduced'),
    ('additional_information', 'additionalInformation'),
    ('credibility', 'credibility'),
    ('type_amplifier', 'type'),
    ('iff_sif', 'iffSif'),
    ('date_time_group', 'dateTimeGroup'),
    ('altitude_depth', 'altitudeDepth'),
    ('equipment_teardown_time', 'equipmentTeardownTime'),
    ('location', 'location'),
    ('speed', 'speed'),
    ('special_headquarters', 'specialHeadquarters'),
    ('direction', 'direction'),
    ('engagement_bar', 'engagementBar'),
]

TEXTOS_MEDIDA = [
    ('tipo', 'tipo'),
    ('identificacao', 'identificacao'),
    ('gdh_ini', 'gdhIni'),
    ('gdh_fim', 'gdhFim'),
    ('numero', 'numero'),
    ('classe_suprimento', 'classeSuprimento'),
    ('status', 'status'),
    ('numero_concentracao', 'numeroConcentracao'),
    ('altitude', 'altitude'),
]

# Escolhas de desenho de duas medidas (desenhos-parametricos.js do Web): o tipo de mina de cada
# posição do 270701 ('ap', 'ac', 'qualquer', 'vazia') e a seta secundária do Setor de Tiro
# (140500), RELATIVA à principal (rotation), em graus no sentido horário. Nulo é o desenho
# padrão (mina antipessoal; secundária a -45 graus).
DESENHO_MEDIDA = [
    ('mina1', 'str', 'mina1'),
    ('mina2', 'str', 'mina2'),
    ('mina3', 'str', 'mina3'),
    ('angulo_secundario', 'real', 'anguloSecundario'),
]

# tipo -> definição. 'balde' é a chave em maps[nome].features do .ebgeo;
# 'tabela' é o nome da tabela no GeoPackage; 'geometria' é o tipo QGIS/OGR.
TIPOS = {
    # Simbologia militar (ferramentas de desenho do plugin)
    'military_symbol': {
        'balde': 'military_symbols', 'tabela': 'military_symbol', 'geometria': 'Point',
        'nome_pt': 'Símbolo Militar', 'grupo': 'militar', 'desenho': 'svg',
        'campos': [('sidc', 'str', '10031000161211000000', 'sidc')]
                  + [(c, 'str', None, w) for c, w in AMPLIFICADORES]
                  + [('special_modifier', 'str', None, 'specialModifier'),
                     ('is_command', 'bool', False, 'isCommand')]
                  + _SIMBOLO,
    },
    'coordination_measure': {
        'balde': 'coordination_measures', 'tabela': 'coordination_measure', 'geometria': 'Point',
        'nome_pt': 'Medida de Coordenação', 'grupo': 'militar', 'desenho': 'svg',
        'campos': [('point_code', 'str', 'ECHELON', 'pointCode'),
                   ('echelon_code', 'str', 'ECHELON_16', 'echelonCode')]
                  + [(c, 'str', None, w) for c, w in TEXTOS_MEDIDA]
                  + [(c, tp, None, w) for c, tp, w in DESENHO_MEDIDA]
                  + [('anchor', 'str', 'center', 'anchor')]
                  + _SIMBOLO,
    },
    'engineering_symbol': {
        'balde': 'engineering_symbols', 'tabela': 'engineering_symbol', 'geometria': 'Point',
        'nome_pt': 'Símbolo de Engenharia', 'grupo': 'militar', 'desenho': 'svg',
        'campos': [('point_code', 'str', '9', 'pointCode'),
                   ('engineering', 'json', None, 'engineering')]
                  + _SIMBOLO,
    },
    'magnetic_declination': {
        'balde': 'magnetic_declinations', 'tabela': 'magnetic_declination', 'geometria': 'Point',
        'nome_pt': 'Declinação Magnética', 'grupo': 'militar', 'desenho': 'svg',
        'campos': [('declination', 'real', 0.0, 'declination'),
                   ('convergence', 'real', 0.0, 'convergence'),
                   ('inclination', 'real', None, 'inclination'),
                   ('intensity', 'real', None, 'intensity'),
                   ('calculation_date', 'str', None, 'calculationDate')]
                  + _SIMBOLO,
    },
    'boundary': {
        'balde': 'boundarys', 'tabela': 'boundary', 'geometria': 'LineString',
        'nome_pt': 'Linha de Limite', 'grupo': 'militar', 'desenho': 'estilo',
        'campos': [('echelon', 'str', 'XXX', 'echelon'),
                   ('symbol_instances', 'json', '[{"ratio": 0.5, "showLabels": true}]', 'symbol_instances'),
                   ('symbol_size_km', 'real', 1.0, 'symbol_size'),
                   ('text_top', 'str', '', 'text_top'),
                   ('text_bottom', 'str', '', 'text_bottom'),
                   ('text_size', 'real', 35.0, 'text_size'),
                   ('text_distance_ratio', 'real', 0.9, 'text_distance_ratio'),
                   ('text_north_facing', 'bool', False, 'text_north_facing')]
                  + _LINHA_TATICA,
    },
    'coordination_line': {
        'balde': 'coordination_lines', 'tabela': 'coordination_line', 'geometria': 'LineString',
        'nome_pt': 'Linha de Coordenação', 'grupo': 'militar', 'desenho': 'estilo',
        'campos': [('symbol_code', 'str', '290199', 'symbol_code'),
                   ('symbol_size_km', 'real', 0.5, 'symbol_size'),
                   ('symbol_spacing_km', 'real', 1.5, 'symbol_spacing'),
                   # Cap. VII do MD33-C-01: os textos da 140000 e da 240701 e o lado inimigo
                   # da 140200, com as chaves que o Web grava (coordination_line_catalog.js).
                   ('tipo', 'str', None, 'tipo'),
                   ('identificacao', 'str', None, 'identificacao'),
                   ('gdh_ini', 'str', None, 'gdhIni'),
                   ('gdh_fim', 'str', None, 'gdhFim'),
                   ('numero_concentracao', 'str', None, 'numeroConcentracao'),
                   ('text_size', 'real', 14.0, 'text_size'),
                   ('text_north_facing', 'bool', False, 'text_north_facing'),
                   ('enemy_color', 'str', '#ff0000', 'enemy_color')]
                  # o símbolo padrão (290199) é obstáculo, e obstáculo nasce verde (7.4.1)
                  + [('color', 'str', '#00B04E', 'color') if c[0] == 'color' else c for c in _LINHA_TATICA],
    },
    # Área de Coordenação (cap. VII do MD33-C-01): o polígono e os atributos; o desenho de cada
    # tipo é estilo nativo (estilos_area.py). portoes e minas são JSON como o Web os grava.
    'coordination_area': {
        'balde': 'coordination_areas', 'tabela': 'coordination_area', 'geometria': 'MultiPolygon',
        'nome_pt': 'Área de Coordenação', 'grupo': 'militar', 'desenho': 'estilo',
        'campos': [('symbol_code', 'str', '150000', 'symbol_code'),
                   ('symbol_size_km', 'real', 0.3, 'symbol_size'),
                   ('tipo', 'str', '', 'tipo'),
                   ('identificacao', 'str', '', 'identificacao'),
                   ('gdh_ini', 'str', '', 'gdhIni'),
                   ('gdh_fim', 'str', '', 'gdhFim'),
                   ('outras_info', 'str', '', 'outrasInfo'),
                   ('escalao', 'str', '', 'escalao'),
                   ('text_position', 'str', None, 'text_position'),
                   ('text_ratio', 'real', None, 'text_ratio'),
                   ('text_size', 'real', 14.0, 'text_size'),
                   ('text_north_facing', 'bool', True, 'text_north_facing'),
                   ('altitude_max', 'str', '', 'altitudeMax'),
                   ('altitude_min', 'str', '', 'altitudeMin'),
                   ('portoes', 'json', '[]', 'portoes'),
                   ('portoes_ocultos', 'bool', False, 'portoes_ocultos'),
                   ('minas', 'json', '["qualquer", "ap", "ac"]', 'minas'),
                   ('fill_color', 'str', '#000000', 'fillColor'),
                   ('line_color', 'str', '#000000', 'lineColor'),
                   ('line_width', 'real', 3.0, 'lineWidth'),
                   ('line_style', 'str', 'solid', 'lineStyle'),
                   ('opacity', 'real', 0.0, 'opacity'),
                   ('hatch_enabled', 'bool', False, 'hatchEnabled'),
                   ('hatch_type', 'str', 'none', 'hatchType'),
                   ('hatch_color', 'str', '#000000', 'hatchColor'),
                   ('hatch_spacing', 'real', 8.0, 'hatchSpacing'),
                   ('hatch_line_width', 'real', 1.5, 'hatchLineWidth')]
                  + _ZOOM,
    },
    'arrow': {
        'balde': 'arrows', 'tabela': 'arrow', 'geometria': 'MultiLineString',
        'nome_pt': 'Seta', 'grupo': 'militar', 'desenho': 'estilo',
        'campos': [('width_m', 'real', 500.0, 'width'),
                   ('head_length_ratio', 'real', 1.5, 'headLengthRatio'),
                   ('show_arrow_head', 'bool', True, 'showArrowHead'),
                   ('double_headed', 'bool', False, 'doubleHeaded'),
                   ('airmobile', 'bool', False, 'airmobile'),
                   ('airmobile_position', 'real', 0.7, 'airmobilePosition'),
                   ('fill_color', 'str', '#3f4fb5', 'fillColor'),
                   ('line_color', 'str', '#3f4fb5', 'lineColor'),
                   ('line_width', 'real', 3.0, 'lineWidth'),
                   ('fill_opacity', 'real', 0.8, 'fillOpacity'),
                   ('line_opacity', 'real', 1.0, 'lineOpacity'),
                   ('geom_desenho', 'str', None, None)],
    },
    'occupied_front': {
        'balde': 'occupied_fronts', 'tabela': 'occupied_front', 'geometria': 'LineString',
        'nome_pt': 'Frente Ocupada', 'grupo': 'militar', 'desenho': 'estilo',
        'campos': [('color', 'str', '#000000', 'color'),
                   ('line_width', 'real', 4.0, 'lineWidth'),
                   ('opacity', 'real', 1.0, 'opacity'),
                   ('geom_desenho', 'str', None, None)],
    },

    # Feições comuns do mapa 2D (entram pelo importador .ebgeo)
    'point': {
        'balde': 'points', 'tabela': 'point', 'geometria': 'Point',
        'nome_pt': 'Ponto', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('fill_color', 'str', '#3388ff', 'fillColor'),
                   ('line_color', 'str', '#ffffff', 'lineColor'),
                   ('line_width', 'real', 2.0, 'lineWidth'),
                   ('size', 'real', 10.0, 'size'),
                   ('opacity', 'real', 1.0, 'opacity'),
                   ('marker_symbol', 'str', 'circle', 'markerSymbol'),
                   ('zoom_corr', 'bool', True, 'sizeZoomCorrectionEnabled'),  # ausente = ligada no Web
                   ('created_zoom', 'real', None, 'sizeCreatedAtZoom')]
                  + _ROTULO + _AZIMUTE,
    },
    'line': {
        'balde': 'lines', 'tabela': 'line', 'geometria': 'LineString',
        'nome_pt': 'Linha', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('line_color', 'str', '#3388ff', 'lineColor'),
                   ('line_width', 'real', 3.0, 'lineWidth'),
                   ('opacity', 'real', 1.0, 'opacity'),
                   ('line_style', 'str', 'solid', 'lineStyle')] + _AZIMUTE,
    },
    'polygon': {'balde': 'polygons', 'tabela': 'polygon', 'geometria': 'MultiPolygon',
                'nome_pt': 'Polígono', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA) + _AZIMUTE},
    'circle': {'balde': 'circles', 'tabela': 'circle', 'geometria': 'MultiPolygon',
               'nome_pt': 'Círculo', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA)},
    'ellipse': {'balde': 'ellipses', 'tabela': 'ellipse', 'geometria': 'MultiPolygon',
                'nome_pt': 'Elipse', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA)},
    'rectangle': {'balde': 'rectangles', 'tabela': 'rectangle', 'geometria': 'MultiPolygon',
                  'nome_pt': 'Retângulo', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA)},
    'sector': {'balde': 'setores', 'tabela': 'sector', 'geometria': 'MultiPolygon',
               'nome_pt': 'Setor', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA)},
    'text': {
        'balde': 'texts', 'tabela': 'text', 'geometria': 'Point',
        'nome_pt': 'Texto', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('text', 'str', '', 'text'),
                   ('size', 'real', 16.0, 'size'),
                   ('color', 'str', '#000000', 'color'),
                   ('halo_color', 'str', '#ffffff', 'backgroundColor'),
                   ('halo_width', 'real', 1.0, 'textHaloWidth'),
                   ('rotation', 'real', 0.0, 'rotation'),
                   ('justify', 'str', 'center', 'justify'),
                   ('show_background', 'bool', False, 'showBackground'),
                   ('bg_fill_color', 'str', None, 'backgroundFillColor'),
                   ('bg_fill_opacity', 'real', None, 'backgroundFillOpacity'),
                   ('bg_border_color', 'str', None, 'backgroundBorderColor'),
                   ('bg_border_opacity', 'real', None, 'backgroundBorderOpacity'),
                   ('bg_border_width', 'real', None, 'backgroundBorderWidth')]
                  + _ZOOM,
    },
    'image': {
        'balde': 'images', 'tabela': 'image', 'geometria': 'Point',
        'nome_pt': 'Imagem', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('size', 'real', 1.0, 'size'),
                   ('rotation', 'real', 0.0, 'rotation'),
                   ('opacity', 'real', 1.0, 'opacity'),
                   ('largura_px', 'real', None, 'width'),
                   ('altura_px', 'real', None, 'height')]
                  + _ZOOM
                  + [('bitmap_b64', 'str', None, None),
                     ('bitmap_mime', 'str', None, None)],
    },
    'brush': {
        'balde': 'brushes', 'tabela': 'brush', 'geometria': 'LineString',
        'nome_pt': 'Pincel', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('line_color', 'str', '#ff0000', 'lineColor'),
                   ('line_width', 'real', 5.0, 'lineWidth')]
                  + _ZOOM,
    },
    'los': {'balde': 'los', 'tabela': 'los', 'geometria': 'MultiLineString',
            'nome_pt': 'Linha de Visada (entrada)', 'grupo': 'analise', 'desenho': 'estilo',
            'campos': [('opacity', 'real', 0.0, 'opacity'), ('parametros', 'json', None, None)]},
    'visibility': {'balde': 'visibility', 'tabela': 'visibility', 'geometria': 'MultiPolygon',
                   'nome_pt': 'Visibilidade (entrada)', 'grupo': 'analise', 'desenho': 'estilo',
                   'campos': [('opacity', 'real', 0.5, 'opacity'), ('parametros', 'json', None, None)]},
    'processed_los': {'balde': 'processed_los', 'tabela': 'processed_los', 'geometria': 'MultiLineString',
                      'nome_pt': 'Linha de Visada', 'grupo': 'analise', 'desenho': 'estilo',
                      'campos': [('color', 'str', '#00FF00', 'color'), ('opacity', 'real', 1.0, 'opacity'),
                                 ('parametros', 'json', None, None)]},
    'processed_visibility': {'balde': 'processed_visibility', 'tabela': 'processed_visibility',
                             'geometria': 'MultiPolygon', 'nome_pt': 'Visibilidade',
                             'grupo': 'analise', 'desenho': 'estilo',
                             'campos': [('color', 'str', '#00FF00', 'color'), ('opacity', 'real', 0.5, 'opacity'),
                                        ('parametros', 'json', None, None)]},
}

# Pilha de desenho do EBGeo Web, de baixo para cima (layers/layer_setup.js:702-721).
PILHA_DESENHO = [
    'image', 'polygon', 'ellipse', 'circle', 'rectangle', 'sector', 'coordination_area', 'arrow',
    'visibility', 'processed_visibility', 'occupied_front', 'coordination_line',
    'boundary', 'line', 'brush', 'los', 'processed_los', 'point', 'military_symbol',
    'coordination_measure', 'engineering_symbol', 'magnetic_declination', 'text',
]

BALDE_PARA_TIPO = {d['balde']: t for t, d in TIPOS.items()}
TIPOS_MILITARES = [t for t, d in TIPOS.items() if d['grupo'] == 'militar']

# Tabelas de apoio, sem geometria.
TABELAS_APOIO = {
    'ebgeo_documento': [('arquivo', 'str'), ('sha256', 'str'), ('versao', 'str'),
                        ('importado_em', 'datetime'), ('data_json', 'json')],
    'ebgeo_mapa': [('nome', 'str'), ('ordem', 'int'), ('base_layer', 'str'),
                   ('notas_titulo', 'str'), ('notas_descricao', 'str'), ('atual', 'bool')],
    'ebgeo_camada': [('mapa', 'str'), ('camada_id', 'str'), ('nome', 'str'), ('visivel', 'bool'),
                     ('bloqueada', 'bool'), ('opacidade', 'real'), ('ordem', 'int')],
    'ebgeo_grupo': [('mapa', 'str'), ('grupo_id', 'str'), ('nome', 'str'), ('visivel', 'bool'),
                    ('bloqueado', 'bool')],
    'ebgeo_grupo_membro': [('mapa', 'str'), ('grupo_id', 'str'), ('tipo', 'str'), ('ebgeo_id', 'str')],
    'ebgeo_icone': [('icone_id', 'str'), ('nome', 'str'), ('mime', 'str'), ('bitmap_b64', 'str')],
    'ebgeo_foto': [('ebgeo_id', 'str'), ('foto_id', 'str'), ('nome', 'str'), ('mime', 'str'),
                   ('bitmap_b64', 'str'), ('miniatura_b64', 'str')],
    # As imagens do arquivo que nenhuma tabela acima guardou (fotos de itens 3D e 360, figuras de
    # slide, bitmap de feição descartada): o exportador as devolve em images/ (ida e volta sem perda).
    'ebgeo_imagem': [('imagem_id', 'str'), ('mime', 'str'), ('bitmap_b64', 'str')],
}


def campos(tipo):
    """Lista completa de campos (comuns + específicos) de um tipo."""
    return CAMPOS_COMUNS + TIPOS[tipo]['campos']


def nomes_campos(tipo):
    return [c[0] for c in campos(tipo)]


def padroes(tipo):
    """Dicionário coluna -> valor padrão (só os que têm padrão)."""
    return {c[0]: c[2] for c in campos(tipo) if c[2] is not None}


def mapa_web(tipo):
    """Dicionário propriedade_web -> coluna, para importar e exportar."""
    return {c[3]: c[0] for c in campos(tipo) if c[3]}


def colunas_json(tipo):
    """As colunas do tipo gravadas como JSON no GeoPackage."""
    return {c[0] for c in campos(tipo) if c[1] == 'json'}


def valor_json_para_qgis(valor):
    """
    Valor de coluna JSON para gravar pelo QGIS (provedor ogr): o objeto, não o texto.

    O provedor serializa o que recebe: um dict ou lista vira o JSON de verdade, igual ao que o
    OGR e o importador gravam; um TEXTO JSON vira uma STRING JSON, com as aspas escapadas
    (medido no QGIS 4.0.0: '"[{\\"ratio\\": 0.5, ...}]"' no GeoPackage). Texto que não é
    objeto nem lista JSON passa como veio.
    """
    if isinstance(valor, str) and valor.strip()[:1] in ('[', '{'):
        import json
        try:
            objeto = json.loads(valor)
        except ValueError:
            return valor
        if isinstance(objeto, (dict, list)):
            return objeto
    return valor


def coluna_de_cor(nome):
    """A coluna guarda uma cor do esquema ('color', '*_color'); as attr_* do usuário ficam de fora."""
    return not nome.startswith('attr_') and (nome == 'color' or nome.endswith('_color'))


def cor_canonica(valor):
    """
    A cor '#rrggbb' em minúsculas, como o widget nativo de cor a regrava (QColor.name()) ao salvar
    QUALQUER mudança no formulário (medido no QGIS 4.0.0): gravada assim, salvar o nome pelo
    formulário não muda a coluna. O que não é '#hex' passa como veio.
    """
    return valor.lower() if isinstance(valor, str) and valor.startswith('#') else valor


def atributos_para_qgis(tipo, atributos):
    """
    Cópia de {coluna: valor} pronta para o provedor do QGIS: as colunas JSON do tipo como objeto
    e as cores em minúsculas (cor_canonica).
    """
    if tipo not in TIPOS:
        return dict(atributos)
    js = colunas_json(tipo)
    return {k: (valor_json_para_qgis(v) if k in js else cor_canonica(v) if coluna_de_cor(k) else v)
            for k, v in atributos.items()}


# ---------------------------------------------------------------- Área de Coordenação: text_ratio

# Os brancos que o Number() do JavaScript tira das pontas de um texto (StrWhiteSpaceChar).
_BRANCOS_JS = '\t\n\x0b\x0c\r \xa0            ' \
              '    　﻿'


def _texto_js(v):
    """String(v) do JavaScript, para o Number() de uma lista ([0.3] vale 0,3; [] vale 0)."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (list, tuple)):
        return ','.join(_texto_js(x) for x in v)
    if isinstance(v, dict):
        return '[object Object]'
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e21:
        return str(int(v))
    return repr(v) if isinstance(v, float) else str(v)


def numero_js(v):
    """
    Number(v) do JavaScript, ou None quando o resultado não é finito (NaN ou ±Infinity), que é o
    teste Number.isFinite do Web. Nulo vale 0, lógico vale 1 ou 0, texto vazio vale 0, e texto só
    é número na grafia do JavaScript: '0,4' e '1_0' não são ('0x1A' é).
    """
    import math
    import re
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        try:
            f = float(v)
        except OverflowError:
            return None
        return f if math.isfinite(f) else None
    if isinstance(v, (list, tuple)):
        return numero_js(_texto_js(v))
    if not isinstance(v, str):
        return None
    s = v.strip(_BRANCOS_JS)
    if s == '':
        return 0.0
    if re.fullmatch(r'[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?', s):
        f = float(s)
        return f if math.isfinite(f) else None
    for prefixo, base in (('0x', 16), ('0o', 8), ('0b', 2)):
        if s[:2].lower() == prefixo and s[2:] and all(c in '0123456789abcdef'[:base] for c in s[2:].lower()):
            return float(int(s[2:], base))
    return None


# A posição do texto que o Web resolve quando text_position não é uma das três: a
# defaultTextPosition do tipo, ou 'interna' no innerAnchor 'centro' (o Ponto Forte), e 'borda' nos
# demais e no código desconhecido (coordination_area_catalog.js; o mesmo de _area_posicao.exp).
POSICOES_TEXTO_AREA = ('borda', 'interna', 'externa')
POSICAO_TEXTO_DO_TIPO_AREA = {'151203': 'interna', '170999-01': 'externa'}


def razao_texto_area(p):
    """
    A coluna text_ratio a partir das properties do Web: a razão que o Web desenha (areaTextRatio).
    A chave NULA fica nula (o desenho, no Web e no estilo, a lê como 0, o vértice mais ao norte);
    o número fica como veio (o desenho o corta a [0, 1]); a chave AUSENTE, ou o que Number() não lê
    como finito, vale o padrão da posição, 0,25 com o texto externo e 0,5 nas demais, que o Web
    desenha e que o estilo do Desktop, lendo nulo como 0, não desenharia.
    """
    if 'text_ratio' in p:
        if p['text_ratio'] is None:
            return None
        r = numero_js(p['text_ratio'])
        if r is not None:
            return r
    posicao = p.get('text_position')
    if not isinstance(posicao, str) or posicao not in POSICOES_TEXTO_AREA:
        codigo = p.get('symbol_code')
        posicao = POSICAO_TEXTO_DO_TIPO_AREA.get(_texto_js(codigo) if codigo is not None else None, 'borda')
    return 0.25 if posicao == 'externa' else 0.5


def razao_desenhada_area(valor):
    """A razão na borda que o desenho usa para o valor da coluna: nula vale 0, cortada a [0, 1]."""
    return min(1.0, max(0.0, 0.0 if valor is None else float(valor)))


# ---------------------------------------------------------------- chave ausente no .ebgeo

_FORMA_AUSENTE = frozenset({'fillColor', 'lineColor', 'lineWidth', 'opacity', 'labelColor', 'labelOutlineColor',
                            'labelOutlineWidth'})
# A chave AUSENTE que o Web desenha como a NULA: a camada MapLibre lê a propriedade crua e o nulo
# cai no padrão do MapLibre (cor preta, espessura e opacidade 1) ou no coalesce da expressão, e o
# gerador de símbolo recusa e o Web guarda o bitmap do arquivo. O padrão do esquema (o da
# ferramenta de criação do Web, que o Web só aplica ao criar) desenharia outra coisa: para estas,
# o importador grava NULL, e o estilo desenha o nulo como o Web. Lista medida pela auditoria
# testes/test_chaves_ausentes.py (fixture 06, o Web em node): chave que falta aqui e diverge
# reprova lá.
AUSENTE_COMO_NULA = {
    'arrow': frozenset({'fillColor', 'fillOpacity', 'lineColor', 'lineWidth', 'width'}),
    'boundary': frozenset({'echelon'}),
    'brush': frozenset({'lineColor', 'lineWidth'}),
    'circle': _FORMA_AUSENTE,
    'ellipse': _FORMA_AUSENTE,
    'polygon': _FORMA_AUSENTE,
    'rectangle': _FORMA_AUSENTE,
    'sector': _FORMA_AUSENTE,
    'coordination_area': frozenset({'hatchLineWidth', 'opacity'}),
    'coordination_line': frozenset({'color', 'symbol_spacing'}),
    'coordination_measure': frozenset({'pointCode'}),
    'engineering_symbol': frozenset({'pointCode'}),
    'line': frozenset({'lineColor', 'lineWidth'}),
    'magnetic_declination': frozenset({'declination', 'size'}),
    'military_symbol': frozenset({'sidc'}),
    'occupied_front': frozenset({'lineWidth'}),
    'point': frozenset({'fillColor', 'lineColor', 'lineWidth', 'labelColor', 'labelOutlineColor', 'labelOutlineWidth'}),
    'processed_los': frozenset({'color'}),
    'processed_visibility': frozenset({'color', 'opacity'}),
}
