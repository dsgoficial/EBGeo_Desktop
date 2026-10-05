# -*- coding: utf-8 -*-
"""
Formulários das linhas táticas sem catálogo de símbolos: Linha de Limite (`boundary`), Seta
(`arrow`) e Frente Ocupada (`occupied_front`).

O que depende do desenho sai do ESTILO, nunca de lista à mão:
  - o que vale quando a coluna booleana da Seta está nula (mostrar ponta, ponta dupla,
    aeromóvel) é lido da expressão do estilo (expressoes/seta.exp), e por ele aparecem os campos
    que só valem com a ponta ou com o aeromóvel;
  - os escalões do Limite são os do catálogo do Desktop (estilos_area.ESCALOES, com o rótulo
    do Web, rotulo_escalao), os mesmos que o glifo do estilo desenha;
  - as posições do símbolo ao longo do Limite (`symbol_instances`, lista JSON) aparecem no
    formulário nativo como um resumo só de leitura, calculado pelas MESMAS ligações com que o
    estilo as lê (`ij` e `rs` de _limite.exp, `sl` de limite_rotulo_geometria.exp), e por isso
    servem à coluna que chega como lista (importador) ou como texto (camada aberta à mão). A
    coluna fica oculta no formulário e na tabela: editar JSON à mão quebra o desenho, e o
    editor da lista é o do dock (ui/blocos/taticos.py).

Salvar o formulário nativo por uma mudança qualquer não pode mudar o desenho. Os widgets são os
comuns de especificacao.py (caixa, número, cabeçalho, correção de zoom), que respondem por guardar
o nulo e as casas; a régua é testes/test_formulario_taticos.py, que edita o nome pelo formulário e
compara o desenho pixel a pixel em feições com valores do Web e com as propriedades nulas do
importador.

Este módulo não importa QGIS nem a especificação na carga, para o registro em especificacao.py
não fazer ciclo; as peças são lidas ao montar cada formulário.
"""
import re

TIPOS = ('boundary', 'arrow', 'occupied_front')

# O Texto do resumo das posições: o dock troca este elemento pelo editor da lista.
RESUMO_POSICOES = 'posicoes_limite'
# Widget rico do dock: a caixa booleana que mostra o padrão do estilo quando a coluna é nula.
CAIXA_PADRAO = 'caixa_padrao'
AVISO_ROTULOS_LIMITE = ('O rótulo superior fica à esquerda do sentido do traçado e o inferior à direita. '
                        'Cada símbolo mostra os dois, salvo os de rótulo desligado no painel do calco.')


def padrao_no_estilo(nome_exp, coluna):
    """O valor que a expressão do estilo dá à coluna booleana nula: `coalesce("col", true|false)`."""
    from ... import estilos_taticos as et
    achados = set(re.findall(r'coalesce\("{}",\s*(true|false)\)'.format(re.escape(coluna)), et.ler_expressao(nome_exp)))
    if len(achados) != 1:
        raise ValueError('padrão de {} em {}.exp: {}'.format(coluna, nome_exp, sorted(achados) or 'ausente'))
    return achados.pop() == 'true'


def _ligacao(nome_exp, nome):
    """A ligação `nome := ...` (ou `::=`) do arquivo de expressão, com as linhas de continuação."""
    from ... import estilos_taticos as et
    linhas = et.ler_expressao(nome_exp).splitlines()
    inicio = re.compile(r'^\s*{}\s*(::=|:=)'.format(re.escape(nome)))
    outra = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*\s*(::=|:=)|@@)')
    for i, linha in enumerate(linhas):
        if inicio.match(linha):
            corpo = [linha.strip()]
            for seguinte in linhas[i + 1:]:
                if outra.match(seguinte):
                    break
                corpo.append(seguinte.strip())
            return ' '.join(corpo)
    raise ValueError('ligação {} ausente em {}.exp'.format(nome, nome_exp))


def expressao_posicoes():
    """
    As posições do símbolo como o estilo as desenha: '25 %, 50 % (sem rótulos), 75 %'. A posição
    nula ou ilegível vale 50 %, a fora da linha vai a 1 % ou 99 %, e a lista vazia ou nula é uma
    instância a 50 %, como em _limite.exp.
    """
    from ... import estilos_taticos as et
    texto = '\n'.join([
        '@@SEJA@@',
        _ligacao('_limite', 'ij'),
        _ligacao('_limite', 'rs'),
        _ligacao('limite_rotulo_geometria', 'sl'),
        '@@EM@@',
        "array_to_string(array_foreach(generate_series(0, array_length(@rs) - 1), "
        "to_string(round(@rs[@element] * 100)) || ' %' || "
        "CASE WHEN @sl[@element] THEN '' ELSE ' (sem rótulos)' END), ', ')",
        '@@FIM@@',
    ])
    return ' '.join(et.finalizar(et.compor(None, _TEXTO=texto)).split('\n'))


def texto_posicoes():
    """O texto do resumo, com a expressão entre [% %] (elemento de texto nativo, sem código)."""
    return ('Posições do símbolo ao longo da linha: [% {} %] do comprimento. Para mudar as posições '
            'e os rótulos de cada símbolo, use o painel do calco.').format(expressao_posicoes())


def _caixa(coluna, rotulo, padrao, condicao=None):
    """
    Caixa da coluna booleana que o estilo lê com padrão. O widget nativo é o comum
    (especificacao.caixa, que é quem decide como o nulo se guarda); no dock, a caixa nula mostra o
    que o estilo desenha (`padrao`) e só grava quando o operador a muda.
    """
    from .. import especificacao as esp
    return esp.Campo(coluna, rotulo, esp.caixa(), condicao=condicao, rico=CAIXA_PADRAO, rico_config=(padrao,))


def _opcoes_escalao():
    from ...estilos_area import ESCALOES, rotulo_escalao
    return [(e, rotulo_escalao(e)) for e in ESCALOES]


def _limite():
    from .. import especificacao as esp
    simbolo = esp.Aba('Símbolo', [
        esp.Campo('echelon', 'Escalão', esp.lista(_opcoes_escalao())),
        esp.Campo('symbol_size_km', 'Tamanho do símbolo', esp.numero(0.001, 50, 0.01, 3, ' km'),
                  rico='km_em_m', rico_config=(1, 50000, 10)),
        esp.Texto(RESUMO_POSICOES, texto_posicoes()),
        esp.descricao(),
    ])
    rotulos = esp.Aba('Rótulos', [
        esp.Campo('text_top', 'Rótulo superior', esp.texto()),
        esp.Campo('text_bottom', 'Rótulo inferior', esp.texto()),
        esp.Texto('aviso_rotulos_limite', AVISO_ROTULOS_LIMITE),
        esp.Campo('text_size', 'Tamanho do texto', esp.numero(8, 80, 1, 0, ' px')),
        esp.Campo('text_distance_ratio', 'Distância do texto (× tamanho do símbolo)', esp.numero(0.1, 3, 0.1, 2, ' ×')),
        _caixa('text_north_facing', 'Texto sempre para o norte', padrao_no_estilo('limite_rotulo_filtro', 'text_north_facing')),
    ])
    aparencia = esp.Aba('Aparência', [
        esp.Campo('color', 'Cor', esp.cor()),
        esp.Campo('line_width', 'Espessura', esp.numero(1, 10, 1, 0, ' px')),
        esp.Campo('opacity', 'Opacidade', esp.numero(0, 1, 0.05, 2)),
        esp.grupo_zoom(),
    ])
    return esp.Formulario('boundary', esp.cabecalho(), [simbolo, rotulos, aparencia, esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + ('geom_desenho', 'symbol_instances'))


def _seta():
    from .. import especificacao as esp
    ponta = esp.Ligado('show_arrow_head', padrao_no_estilo('seta', 'show_arrow_head'))
    aeromovel = esp.Ligado('airmobile', padrao_no_estilo('seta', 'airmobile'))
    seta = esp.Aba('Seta', [
        esp.Campo('width_m', 'Largura', esp.numero(10, 10000, 10, 0, ' m')),
        _caixa('show_arrow_head', 'Mostrar Seta', ponta.padrao),
        _caixa('double_headed', 'Seta nas Duas Pontas', padrao_no_estilo('seta', 'double_headed'), condicao=ponta),
        esp.Campo('head_length_ratio', 'Comprimento da ponta (× base)', esp.numero(0.2, 5, 0.1, 2, ' ×'), condicao=ponta),
        _caixa('airmobile', 'Aeromóvel / Aeroterrestre', aeromovel.padrao),
        esp.Campo('airmobile_position', 'Posição do aeromóvel (fração do eixo)', esp.numero(0.05, 0.95, 0.05, 2),
                  condicao=aeromovel),
        esp.descricao(),
    ])
    aparencia = esp.Aba('Aparência', [
        esp.Campo('fill_color', 'Preenchimento', esp.cor()),
        esp.Campo('fill_opacity', 'Opacidade do Preenchimento', esp.numero(0, 1, 0.05, 2)),
        esp.Campo('line_color', 'Borda', esp.cor()),
        esp.Campo('line_width', 'Espessura da Borda', esp.numero(1, 10, 1, 0, ' px')),
        esp.Campo('line_opacity', 'Opacidade da Borda', esp.numero(0, 1, 0.05, 2)),
    ])
    return esp.Formulario('arrow', esp.cabecalho(), [seta, aparencia, esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + ('geom_desenho',))


def _frente_ocupada():
    from .. import especificacao as esp
    aparencia = esp.Aba('Aparência', [
        esp.Campo('color', 'Cor', esp.cor()),
        esp.Campo('line_width', 'Espessura', esp.numero(1, 10, 1, 0, ' px')),
        esp.Campo('opacity', 'Opacidade', esp.numero(0, 1, 0.05, 2)),
        esp.descricao(),
    ])
    return esp.Formulario('occupied_front', esp.cabecalho(), [aparencia, esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + ('geom_desenho',))


CONSTRUTORES = {'boundary': _limite, 'arrow': _seta, 'occupied_front': _frente_ocupada}
