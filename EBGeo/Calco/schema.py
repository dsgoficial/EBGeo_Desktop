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
                   ('symbol_spacing_km', 'real', 1.5, 'symbol_spacing')]
                  + _LINHA_TATICA,
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
                  + _ROTULO,
    },
    'line': {
        'balde': 'lines', 'tabela': 'line', 'geometria': 'LineString',
        'nome_pt': 'Linha', 'grupo': 'forma', 'desenho': 'estilo',
        'campos': [('line_color', 'str', '#3388ff', 'lineColor'),
                   ('line_width', 'real', 3.0, 'lineWidth'),
                   ('opacity', 'real', 1.0, 'opacity'),
                   ('line_style', 'str', 'solid', 'lineStyle')],
    },
    'polygon': {'balde': 'polygons', 'tabela': 'polygon', 'geometria': 'MultiPolygon',
                'nome_pt': 'Polígono', 'grupo': 'forma', 'desenho': 'estilo', 'campos': list(_FORMA)},
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
    'image', 'polygon', 'ellipse', 'circle', 'rectangle', 'sector', 'arrow',
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
