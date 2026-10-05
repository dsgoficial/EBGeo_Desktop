# -*- coding: utf-8 -*-
"""
Formulário das feições comuns do mapa 2D, as que entram pelo importador .ebgeo e pelo Azimute e
Distância (schema.TIPOS de grupo 'forma' e 'analise'): Ponto, Linha, Polígono, Círculo, Elipse,
Retângulo, Setor, Texto, Imagem, Pincel e as quatro de análise (Linha de Visada e Visibilidade,
de entrada e processadas).

Rótulos, faixas e opções como os painéis do Web os mostram (draw_tools/*_attributes_panel.js,
hatch-control.helpers.js, line-style.helpers.js, point-marker-symbols.js): a opacidade, que o
Web mostra de 0 a 100 %, fica gravada e mostrada de 0 a 1; as faixas numéricas cobrem as do Web
e os valores que os arquivos trazem (a rotação do texto chega a -90 na fixture 06), porque o
editor numérico do QGIS prende o valor na faixa e regravaria a feição que só foi aberta.

Peças próprias:
  - a condição Preenchida (coluna não nula), no mesmo contrato de especificacao.Condicao
    (`expressao()` e `avaliar()`); a de caixa marcada é a comum (especificacao.Ligado);
  - a aba Azimute e Distância (ponto, linha e polígono com a construção polar): no nativo, um
    resumo só de leitura por expressão (TextoAzimute); no dock, o mesmo resumo e o botão que abre
    o painel do Azimute para editar as pernas (ui/blocos/comuns.py);
  - a aba Fotos (formulario/fotos.py), em todos os tipos.

Os widgets são os ajudantes comuns de especificacao.py (caixa, número, lista), sem remendo
local: o estado nulo e a faixa dos números são regra comum a todos os tipos.
"""
import os
from dataclasses import dataclass

from .. import especificacao as esp
from ..fotos import aba_fotos

TIPOS = ('point', 'line', 'polygon', 'circle', 'ellipse', 'rectangle', 'sector', 'text', 'image', 'brush',
         'los', 'visibility', 'processed_los', 'processed_visibility')
FORMAS = ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')
TIPOS_AZIMUTE = ('point', 'line', 'polygon')
COLUNA_AZIMUTE = 'azimute_distancia'
NOME_ABA_AZIMUTE = 'Azimute e Distância'


# ---------------------------------------------------------------------------------------------
# Condições próprias
# ---------------------------------------------------------------------------------------------

Ligado = esp.Ligado


@dataclass(frozen=True)
class Preenchida:
    """A coluna tem valor (a construção do Azimute, por exemplo)."""
    coluna: str

    def expressao(self):
        return '"{}" IS NOT NULL'.format(self.coluna)

    def avaliar(self, atributos):
        v = atributos.get(self.coluna)
        return not (esp._nulo(v) or v == '')


# ---------------------------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------------------------

numero = esp.numero


def opacidade(rotulo='Opacidade'):
    return esp.Campo('opacity', rotulo, numero(0, 1, 0.05, 2))


# Opções como o Web as rotula.
ESTILOS_LINHA = (('solid', 'Sólida'), ('dashed', 'Tracejada'), ('dotted', 'Pontilhada'), ('dash-dot', 'Traço-ponto'),
                 ('long-dash', 'Traço longo'), ('short-dash', 'Traço curto'), ('dot-dot-dash', 'Ponto-ponto-traço'))
HACHURAS = (('none', 'Nenhuma'), ('diagonal-right', 'Diagonal /'), ('diagonal-left', 'Diagonal \\'),
            ('horizontal', 'Horizontal'), ('vertical', 'Vertical'), ('cross', 'Cruz +'),
            ('cross-diagonal', 'Cruz X'), ('dots', 'Pontos'))
MARCADORES = (('circle', 'Forma: Círculo'), ('square', 'Forma: Quadrado'), ('diamond', 'Forma: Losango'),
              ('triangle', 'Forma: Triângulo'), ('star', 'Forma: Estrela'), ('cross', 'Forma: Cruz'),
              ('x-mark', 'Forma: X'), ('car', 'Ícone: Veículo'), ('drone', 'Ícone: Drone'),
              ('fire', 'Ícone: Incêndio'), ('gun', 'Ícone: Armamento'), ('news', 'Ícone: Comunicações'),
              ('plane', 'Ícone: Aeronave'), ('supply', 'Ícone: Suprimento'))
ALINHAMENTOS = (('left', 'Esquerda'), ('center', 'Centro'), ('right', 'Direita'))


grupo_zoom = esp.grupo_zoom


def _se(condicao, campos):
    """Os campos que só valem sob a condição: cada um leva a condição (o contêiner Row do nativo
    põe os filhos lado a lado, então um grupo sem título só serve para um elemento)."""
    for c in campos:
        c.condicao = condicao
    return campos


# ---------------------------------------------------------------------------------------------
# Abas compartilhadas
# ---------------------------------------------------------------------------------------------

def aba_rotulo():
    """Etiqueta (rótulo) de ponto e de forma (_ROTULO do esquema): os campos só valem com o rótulo ligado."""
    return esp.Aba('Etiqueta', [
        esp.Campo('show_label', 'Mostrar Etiqueta', esp.caixa()),
    ] + _se(Ligado('show_label'), [
        esp.Campo('label_text', 'Texto da Etiqueta', esp.texto()),
        esp.Campo('label_color', 'Cor do Texto', esp.cor()),
        esp.Campo('label_size', 'Tamanho da Fonte', numero(1, 72, 1, 0, ' px')),
        esp.Campo('label_outline_color', 'Cor do Contorno', esp.cor()),
        esp.Campo('label_outline_width', 'Espessura do Contorno', numero(0, 10, 1, 0, ' px')),
    ]) + [grupo_zoom('label_', condicao=Ligado('show_label'))])


def expressao_json(coluna):
    """A coluna JSON como mapa, venha como mapa (importador) ou como texto (gravada pelo QGIS)."""
    return ('CASE WHEN try(map_akeys("{c}")) IS NOT NULL THEN "{c}" ELSE try(from_json("{c}")) END'
            .format(c=coluna))


def _rotulos_mapa(pares):
    return "map({})".format(', '.join("'{}', '{}'".format(k, v) for k, v in pares))


# Os rótulos da construção, como o painel do Azimute os mostra (azimute/geometria.py).
MODOS_AZIMUTE = (('point', 'Pontos'), ('route', 'Rota'), ('area', 'Área'))
NORTES_AZIMUTE = (('magnetic', 'Norte Magnético (NM)'), ('grid', 'Norte de Quadrícula (NQ)'),
                  ('true', 'Norte Verdadeiro (NV)'))


def expressao_resumo_azimute():
    """
    Resumo só de leitura da construção polar (azimuthDistanceData do Web): saída, número de
    pernas, unidades, norte, ponto de referência e declinação, e a tabela das pernas. `concat`
    ignora nulo (`||` com nulo dá nulo), e dois níveis de with_variable só (o parse dobra a cada
    nível; wiki ebgeo-desktop).
    """
    perna = "@p[@element - 1]"
    linha = ("concat('<tr><td>', @element, '</td><td>', to_string(map_get({p}, 'azimuth')), "
             "'</td><td>', to_string(map_get({p}, 'distance')), '</td><td>', "
             "replace(coalesce(map_get({p}, 'observation'), ''), '<', '&lt;'), '</td></tr>')").format(p=perna)
    return (
        "[% with_variable('a', " + expressao_json(COLUNA_AZIMUTE) + ", "
        "with_variable('p', coalesce(map_get(@a, 'legs'), array()), concat("
        "'<b>', coalesce(map_get(" + _rotulos_mapa(MODOS_AZIMUTE) + ", map_get(@a, 'outputMode')), 'Construção'), "
        "'</b>: ', array_length(@p), ' perna(s), azimutes em ', "
        "if(map_get(@a, 'angularUnit') = 'mils', 'milésimos', 'graus'), ' no ', "
        "coalesce(map_get(" + _rotulos_mapa(NORTES_AZIMUTE) + ", map_get(@a, 'northReference')), 'Norte Verdadeiro (NV)'), "
        "', distâncias em ', if(map_get(@a, 'distanceUnit') = 'kilometers', 'km', 'm'), '.<br/>', "
        "'Ponto de referência (lat, lon): ', format_number(map_get(@a, 'referencePoint')[1], 6), ', ', "
        "format_number(map_get(@a, 'referencePoint')[0], 6), "
        "'; declinação magnética ', format_number(coalesce(map_get(@a, 'magneticDeclination'), 0), 2), '°.', "
        "CASE WHEN map_get(@a, 'isReferencePoint') THEN '<br/>Este ponto é o ponto de referência.' "
        "WHEN map_get(@a, 'waypointIndex') IS NOT NULL THEN concat('<br/>Este ponto é o fim da perna ', "
        "map_get(@a, 'waypointIndex'), '.') ELSE '' END, "
        "'<table><tr><th>Perna</th><th>Azimute</th><th>Distância</th><th>Observação</th></tr>', "
        "if(array_length(@p) > 0, array_to_string(array_foreach(generate_series(1, array_length(@p)), " + linha + "), ''), ''), "
        "'</table><br/>Para mudar as pernas, use o Azimute e Distância do plugin EBGeo Desktop.'))) %]")


@dataclass
class TextoAzimute(esp.Texto):
    """O resumo da construção: o nativo avalia a expressão; o dock troca-o pelo bloco rico."""
    rico: str = 'azimute'


def aba_azimute():
    return esp.Aba(NOME_ABA_AZIMUTE, [TextoAzimute('resumo_azimute', expressao_resumo_azimute())],
                   condicao=Preenchida(COLUNA_AZIMUTE))


def _formulario(tipo, abas, ocultos=()):
    """Cabeçalho comum, as abas do tipo (a Descrição no fim da primeira), Atributos, Fotos e Avançado."""
    primeira = abas[0]
    primeira.filhos = list(primeira.filhos) + [esp.descricao()]
    return esp.Formulario(tipo, esp.cabecalho(), list(abas) + [esp.aba_atributos(), aba_fotos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + tuple(ocultos))


# ---------------------------------------------------------------------------------------------
# Os tipos
# ---------------------------------------------------------------------------------------------

PREFIXO_ICONE = 'custom:'
ROTULO_ICONE = 'Ícone personalizado'


def rotulo_icone(nome):
    return '{}: {}'.format(ROTULO_ICONE, nome) if nome else ROTULO_ICONE


def opcoes_icones(layer):
    """
    Os ícones próprios do arquivo (tabela ebgeo_icone do mesmo GeoPackage), como opções do
    Símbolo do Ponto: o valor `custom:<id>` que o Web grava, o nome do ícone e a imagem.
    """
    caminho = layer.source().split('|')[0] if layer is not None else ''
    if not caminho or not os.path.isfile(caminho):
        return []
    from osgeo import ogr
    ds = ogr.Open(caminho)
    tab = ds.GetLayerByName('ebgeo_icone') if ds is not None else None
    if tab is None:
        return []
    opcoes = [(PREFIXO_ICONE + f.GetField('icone_id'), rotulo_icone(f.GetField('nome')),
               (f.GetField('mime'), f.GetField('bitmap_b64')) if f.GetField('bitmap_b64') else None)
              for f in tab if f.GetField('icone_id')]
    ds = None
    return opcoes


def ponto():
    marcador = esp.Aba('Marcador', [
        esp.Campo('marker_symbol', 'Símbolo', esp.lista(MARCADORES), opcoes_da_camada=opcoes_icones),
        esp.Campo('size', 'Tamanho', numero(1, 100, 1, 0, ' px')),
        esp.Campo('fill_color', 'Cor', esp.cor()),
        esp.Campo('line_color', 'Borda', esp.cor()),
        esp.Campo('line_width', 'Espessura da Borda', numero(0, 10, 1, 0, ' px')),
        opacidade(),
        grupo_zoom(),
    ])
    return _formulario('point', [marcador, aba_rotulo(), aba_azimute()], (COLUNA_AZIMUTE,))


def linha():
    aba = esp.Aba('Linha', [
        esp.Campo('line_color', 'Cor', esp.cor()),
        esp.Campo('line_width', 'Espessura', numero(1, 50, 1, 0, ' px')),
        esp.Campo('line_style', 'Estilo da linha', esp.lista(ESTILOS_LINHA)),
        opacidade(),
    ])
    return _formulario('line', [aba, aba_azimute()], (COLUNA_AZIMUTE,))


def com_hachura():
    """
    O estilo das formas desenha a hachura com a caixa marcada E um dos tipos das camadas de padrão
    (estilos_formas.COND_HACHURA e HACHURAS_DESENHADAS): só então o espaçamento e a espessura
    valem (decisão do chefe, 2026-10-05). As duas colunas têm widget aqui, e o nativo renova a
    condição a cada mudança delas.
    """
    from ...estilos_formas import HACHURAS_DESENHADAS
    return esp.Todas((Ligado('hatch_enabled'), esp.Condicao('hatch_type', HACHURAS_DESENHADAS)))


def forma(tipo):
    """Polígono, Círculo, Elipse, Retângulo e Setor (_FORMA do esquema)."""
    aparencia = esp.Aba('Aparência', [
        esp.Campo('fill_color', 'Preenchimento', esp.cor()),
        opacidade('Opacidade do Preenchimento'),
        esp.Campo('line_color', 'Borda', esp.cor()),
        esp.Campo('line_width', 'Espessura da Borda', numero(0, 20, 1, 0, ' px')),
        esp.Campo('line_style', 'Estilo da borda', esp.lista(ESTILOS_LINHA)),
        # o Web liga a hachura pelo padrão (hatchEnabled = padrão diferente de nenhuma); o estilo
        # exige as duas colunas, e sem o plugin nada as sincroniza: as duas ficam à mão
        esp.Grupo('Hachura', [esp.Campo('hatch_enabled', 'Com hachura', esp.caixa())] + _se(Ligado('hatch_enabled'), [
            esp.Campo('hatch_type', 'Padrão da hachura', esp.lista(HACHURAS)),
        ]) + _se(com_hachura(), [
            esp.Campo('hatch_spacing', 'Espaçamento da Hachura', numero(1, 50, 1, 0, ' px')),
            esp.Campo('hatch_line_width', 'Espessura da Hachura', numero(0.5, 10, 0.5, 1, ' px')),
        ])),
    ])
    abas = [aparencia, aba_rotulo()]
    ocultos = ('parametros', 'hatch_color')  # a hachura usa a cor do preenchimento; hatchColor é reserva no Web
    if tipo in TIPOS_AZIMUTE:
        abas.append(aba_azimute())
        ocultos += (COLUNA_AZIMUTE,)
    return _formulario(tipo, abas, ocultos)


def texto_():
    texto = esp.Aba('Texto', [
        esp.Campo('text', 'Conteúdo', esp.texto(multilinha=True), rotulo_em_cima=True),
        esp.Campo('size', 'Tamanho da Fonte', numero(1, 200, 1, 0, ' px')),
        esp.Campo('color', 'Cor do Texto', esp.cor()),
        esp.Campo('halo_color', 'Cor do Contorno', esp.cor()),
        esp.Campo('halo_width', 'Espessura do Contorno', numero(0, 10, 1, 0, ' px')),
        esp.Campo('rotation', 'Rotação', numero(-360, 360, 1, 0, '°')),
        esp.Campo('justify', 'Alinhamento', esp.lista(ALINHAMENTOS)),
        grupo_zoom(),
    ])
    fundo = esp.Aba('Caixa de Fundo', [  # a seção do painel de texto do Web
        esp.Campo('show_background', 'Mostrar Caixa de Fundo', esp.caixa()),
    ] + _se(Ligado('show_background'), [
        esp.Campo('bg_fill_color', 'Cor do Preenchimento', esp.cor()),
        esp.Campo('bg_fill_opacity', 'Opacidade do Preenchimento', numero(0, 1, 0.05, 2)),
        esp.Campo('bg_border_color', 'Cor da Borda', esp.cor()),
        esp.Campo('bg_border_opacity', 'Opacidade da Borda', numero(0, 1, 0.05, 2)),
        esp.Campo('bg_border_width', 'Espessura da Borda', numero(0, 10, 1, 0, ' px')),
    ]))
    return _formulario('text', [texto, fundo])


AVISO_SEM_BITMAP = 'Imagem sem bitmap no arquivo.'
EXPRESSAO_PREVIA_IMAGEM = (
    "[% if(\"bitmap_b64\" IS NULL, '" + AVISO_SEM_BITMAP + "', concat('<img width=\"160\" src=\"data:', "
    "coalesce(\"bitmap_mime\", 'image/png'), ';base64,', \"bitmap_b64\", '\"/>')) %]")


def imagem():
    aba = esp.Aba('Imagem', [
        esp.Texto('previa_imagem', EXPRESSAO_PREVIA_IMAGEM),
        esp.Campo('size', 'Tamanho', numero(0.05, 10, 0.1, 2, ' ×')),
        esp.Campo('rotation', 'Rotação', numero(-360, 360, 1, 0, '°')),
        opacidade(),
        esp.Campo('largura_px', 'Largura original (px)', numero(0, 100000, 1, 0, ' px'), somente_leitura=True),
        esp.Campo('altura_px', 'Altura original (px)', numero(0, 100000, 1, 0, ' px'), somente_leitura=True),
        grupo_zoom(),
    ])
    return _formulario('image', [aba], ('bitmap_b64', 'bitmap_mime'))


def pincel():
    aba = esp.Aba('Pincel', [
        esp.Campo('line_color', 'Cor', esp.cor()),
        esp.Campo('line_width', 'Largura', numero(1, 100, 1, 0, ' px')),
        grupo_zoom(),
    ])
    return _formulario('brush', [aba])


AVISO_ANALISE = 'Resultado de análise do EBGeo Web: a geometria e os parâmetros vêm do arquivo e não se editam aqui.'


def analise(tipo):
    """Linha de Visada e Visibilidade, de entrada e processadas: só a aparência se edita."""
    filhos = [esp.Texto('aviso_analise', AVISO_ANALISE)]
    if tipo.startswith('processed_'):
        filhos.append(esp.Campo('color', 'Cor', esp.cor()))
    filhos.append(opacidade())
    return _formulario(tipo, [esp.Aba('Aparência', filhos)], ('parametros',))


CONSTRUTORES = {
    'point': ponto, 'line': linha, 'text': texto_, 'image': imagem, 'brush': pincel,
    **{t: (lambda t=t: forma(t)) for t in FORMAS},
    **{t: (lambda t=t: analise(t)) for t in ('los', 'visibility', 'processed_los', 'processed_visibility')},
}
