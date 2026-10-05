# -*- coding: utf-8 -*-
"""
Especificação do formulário da Área de Coordenação (`coordination_area`, os 7 tipos do
CATALOGO_AREA de estilos_area.py).

Abas Símbolo, Textos, Aparência, Atributos e Avançado. O que depende do tipo sai do catálogo:
escalão só no Ponto Forte, portões e altitudes só no Volume de aproximação de base, minas só na
Área minada, "Outras informações" fora do VAB, estilo da borda fora da Zona fortificada (a borda
dela são os elos) e o rótulo da posição na borda, que no Ponto Forte é a do escalão. É o mesmo
recorte que o dock mostrava antes da especificação (testes/test_formulario_area.py).

Portões e minas são listas JSON. No formulário nativo, cada uma vira um RESUMO só de leitura
(elemento de texto com expressão, que o QGIS avalia sem o plugin) e a coluna fica oculta: nenhum
widget nativo a regrava, e o JSON não se quebra ao salvar. No dock, o resumo dá lugar ao editor
rico (acrescentar, remover, "Marcar portão na borda" no mapa; as três posições de mina).

Caixas e números vêm dos ajudantes comuns (esp.caixa, esp.numero), que preservam o nulo e o valor
exato ao salvar outra mudança; aqui a Correção de Zoom nula, que desenha ligada, ficaria
desligada sem isso (testes/test_formulario_area.py, pior caso).
"""
from dataclasses import dataclass

from .. import especificacao as esp

# Valor do ValueMap que o QGIS lê como nulo (QgsValueMapFieldFormatter::NULL_VALUE).
NULO_VALUEMAP = '{2839923C-8B7D-419E-B84B-CA2FE9B80EC7}'
ROTULO_CORRECAO_ZOOM = 'Correção de Zoom'  # uma só para o desenho e os textos, como no Web
AVISO_EDITAR_NO_PAINEL = 'Edite no painel do calco (plugin EBGeo Desktop).'


@dataclass
class Resumo(esp.Texto):
    """
    Texto com expressão [% ... %] que o formulário nativo avalia (lista JSON em leitura). O dock
    não o mostra: põe no lugar o `campo_rico`, o editor da coluna.
    """
    campo_rico: esp.Campo = None


def _lista_com_nulo(opcoes, rotulo_nulo):
    return esp.lista([(NULO_VALUEMAP, rotulo_nulo)] + list(opcoes))


def expr_resumo_portoes(lista):
    """'PORTÃO ALFA a 12 %, PORTÃO BRAVO a 40 %' (ou 'nenhum'), da lista JSON dos portões."""
    return ("with_variable('g', {l}, CASE WHEN coalesce(try(array_length(@g)), 0) = 0 THEN 'nenhum' ELSE "
            "array_to_string(array_foreach(@g, coalesce(nullif(trim(to_string(@element['nome'])), ''), 'sem nome') "
            "|| ' a ' || round(100 * coalesce(to_real(@element['ratio']), 0)) || ' %'), ', ') END)").format(l=lista)


def expr_resumo_minas(lista, tipos):
    """'Qualquer tipo, Antipessoal, Anticarro': as três posições, lista inválida vale a padrão, como no desenho."""
    casos = ' '.join("WHEN @element = '{}' THEN '{}'".format(v, r) for v, r in tipos)
    return ("with_variable('m', {l}, array_to_string(array_foreach("
            "CASE WHEN try(array_length(@m), 0) = 3 THEN @m ELSE array('qualquer', 'ap', 'ac') END, "
            "CASE {c} ELSE to_string(@element) END), ', '))").format(l=lista, c=casos)


def formulario():
    from ...estilos_area import (
        CATALOGO_AREA, ESCALOES, ESTILOS_TRACO, HACHURAS, POSICOES_TEXTO, SIMBOLO_PADRAO, TIPOS_MINA,
        expr_lista_json, rotulo_escalao,
    )

    def cond(predicado):
        return esp.por_codigo('symbol_code', CATALOGO_AREA, SIMBOLO_PADRAO, predicado)

    vab = cond(lambda s: bool(s.get('portoes')))
    minada = cond(lambda s: bool(s.get('minas')))
    ponto_forte = cond(lambda s: bool(s.get('escalao')))

    resumo_portoes = Resumo(
        'resumo_portoes', 'Portões: [% {} %]. {}'.format(expr_resumo_portoes(expr_lista_json('portoes')),
                                                         AVISO_EDITAR_NO_PAINEL),
        campo_rico=esp.Campo('portoes', 'Portões', esp.oculto(), rico='area_portoes'))
    resumo_minas = Resumo(
        'resumo_minas', 'Minas, posições 1, 2 e 3: [% {} %]. {}'.format(
            expr_resumo_minas(expr_lista_json('minas'), TIPOS_MINA), AVISO_EDITAR_NO_PAINEL),
        campo_rico=esp.Campo('minas', 'Minas', esp.oculto(), rico='area_minas'))

    simbolo = esp.Aba('Símbolo', [
        esp.Campo('symbol_code', 'Símbolo', esp.lista([(c, '{} ({})'.format(s['nome'], c)) for c, s in CATALOGO_AREA.items()]),
                  rico='area_tipo'),
        # 1 m a 200 km: o que a ferramenta grava (tamanho_inicial_km) e o Web (metro inteiro)
        esp.Campo('symbol_size_km', 'Tamanho do símbolo', esp.numero(0.001, 200, 0.01, 3, ' km'),
                  rico='km_em_m', rico_config=(10, 50000, 10)),
        esp.Campo('zoom_corr', ROTULO_CORRECAO_ZOOM, esp.caixa()),
        esp.Campo('created_zoom', 'Zoom de Referência', esp.numero(0, 24, 0.1, 1)),
        esp.Campo('escalao', 'Escalão', esp.lista([('', 'Nenhum')] + [(e, rotulo_escalao(e)) for e in ESCALOES]),
                  condicao=ponto_forte),
        esp.Grupo('Portões', [resumo_portoes, esp.Campo('portoes_ocultos', 'Ocultar portões', esp.caixa())],
                  condicao=vab),
        esp.Grupo('Minas', [resumo_minas], condicao=minada),
        esp.descricao(),
    ])
    textos = esp.Aba('Textos', [
        esp.Campo('tipo', 'Tipo', esp.texto()),
        esp.Campo('identificacao', 'Identificação', esp.texto()),
        esp.Campo('altitude_max', 'Altitude máxima', esp.texto(), condicao=vab),
        esp.Campo('altitude_min', 'Altitude mínima', esp.texto(), condicao=vab),
        esp.Campo('gdh_ini', 'GDH Início', esp.texto()),
        esp.Campo('gdh_fim', 'GDH Fim', esp.texto()),
        esp.Campo('outras_info', 'Outras informações', esp.texto(), condicao=esp.Condicao(vab.coluna, vab.valores, not vab.negar)),
        # nulo é a posição padrão do tipo (externa no VAB, interna no Ponto Forte, sobre a borda nos demais)
        esp.Campo('text_position', 'Posição do texto', _lista_com_nulo(POSICOES_TEXTO, 'Padrão do tipo'),
                  rico='area_lista', rico_config=((None, 'Padrão do tipo'),) + tuple(POSICOES_TEXTO)),
        esp.Campo('text_ratio', 'Posição na borda', esp.numero(0, 1, 0.05, 2),
                  rotulo_se=(ponto_forte, 'Posição do escalão na borda'), rico='area_pct'),
        esp.Campo('text_north_facing', 'Texto sempre para o norte', esp.caixa()),
        esp.Campo('text_size', 'Tamanho do texto', esp.numero(8, 40, 1, 0, ' px')),
    ])
    aparencia = esp.Aba('Aparência', [
        esp.Campo('line_color', 'Borda', esp.cor()),
        esp.Campo('line_width', 'Espessura da Borda', esp.numero(1, 10, 1, 0, ' px')),
        esp.Campo('line_style', 'Estilo da borda', esp.lista(ESTILOS_TRACO), condicao=cond(lambda s: s['borda'] != 'elos')),
        esp.Campo('fill_color', 'Preenchimento', esp.cor()),
        esp.Campo('opacity', 'Opacidade do Preenchimento', esp.numero(0, 1, 0.05, 2)),
        esp.Campo('hatch_type', 'Hachura', esp.lista(HACHURAS)),
        esp.Campo('hatch_spacing', 'Espaçamento da Hachura', esp.numero(2, 40, 1, 0, ' px')),
        esp.Campo('hatch_line_width', 'Espessura da Hachura', esp.numero(0.5, 10, 0.5, 1, ' px')),
    ])
    cabecalho = esp.cabecalho()
    abas = [simbolo, textos, aparencia, esp.aba_atributos(), esp.aba_avancado()]
    # hatch_enabled acompanha hatch_type (valor padrão na atualização, estilos_area.py; e o guardião);
    # hatch_color é reserva do Web, o desenho usa a cor do preenchimento.
    return esp.Formulario('coordination_area', cabecalho, abas,
                          esp.OCULTOS_COMUNS + ('portoes', 'minas', 'hatch_enabled', 'hatch_color'))
