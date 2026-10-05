# -*- coding: utf-8 -*-
"""
Regras de troca do calco, como funções puras: o que mais muda numa feição quando o operador
muda um campo (a cor padrão ao trocar o símbolo, e, na escala, os padrões da área, o escalão da
família da medida). Saíram do dock para valer em QUALQUER caminho de edição: o guardião
(guardiao.py) as aplica ao formulário nativo, à tabela de atributos, à calculadora de campo e
ao próprio dock. Sem o plugin, o formulário nativo grava e as regras não rodam.

Contrato: `ao_mudar(tipo, anterior, mudadas)` recebe os atributos ANTES da edição e as colunas
que a edição gravou ({coluna: valor novo}) e devolve as mudanças a mais ({coluna: valor}), vazio
quando nada muda. Campo que o próprio operador mudou na mesma edição nunca é sobrescrito.

O formulário nativo, ao gravar uma mudança, regrava também campos que o operador não tocou
quando o valor do widget difere do gravado só na forma: a cor volta como QColor (e o GeoPackage
a guarda em minúsculas), o texto multilinha vazio vem como "não definido" (medido no QGIS 4.0.0).
Por isso a regra compara pelo VALOR (`mudou`), e não pela presença da coluna na edição.
"""

# As colunas cujo valor anterior as regras do tipo precisam ler.
CAMPOS_VIGIADOS = {
    'coordination_line': ('symbol_code', 'color'),
}
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)


def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


def valor(v):
    """O valor comparável: nulo vira None, cor (QColor) vira o '#rrggbb'."""
    if _nulo(v):
        return None
    if hasattr(v, 'name') and hasattr(v, 'isValid') and callable(v.name):
        return v.name()
    return v


def nao_definido(v):
    """O marcador do formulário para "campo não definido" (QgsUnsetAttributeValue): não é mudança."""
    return type(v).__name__ == 'QgsUnsetAttributeValue'


def iguais(a, b):
    a, b = valor(a), valor(b)
    if isinstance(a, str) and isinstance(b, str) and a.startswith('#') and b.startswith('#'):
        return a.lower() == b.lower()  # cor: o GeoPackage pode guardá-la em outra caixa
    return a == b


def mudou(anterior, mudadas, coluna):
    """A edição mudou de fato o valor da coluna."""
    return coluna in mudadas and not nao_definido(mudadas[coluna]) and not iguais(anterior.get(coluna), mudadas[coluna])


def _simbolo_linha(codigo):
    from .estilos_taticos import CATALOGO_LINHA, SIMBOLO_PADRAO
    return CATALOGO_LINHA.get('' if _nulo(codigo) else str(codigo), CATALOGO_LINHA[SIMBOLO_PADRAO])


def cor_ao_trocar_simbolo_linha(anterior, novo, atual):
    """
    A cor nova ao trocar o símbolo da Linha de Coordenação, ou None para manter: só troca a
    linha que ainda veste a cor padrão do símbolo anterior (código desconhecido conta como a
    290199, a do Web); obstáculo nasce verde, manobra e fogos pretos; cor escolhida fica.
    """
    def igual(a, b):
        return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()
    atual = valor(atual)
    atual = None if atual is None else str(atual)
    padrao_novo = _simbolo_linha(novo)['cor']
    if igual(atual, _simbolo_linha(anterior)['cor']) and not igual(atual, padrao_novo):
        return padrao_novo
    return None


def _linha_coordenacao(anterior, mudadas):
    extra = {}
    if mudou(anterior, mudadas, 'symbol_code') and not mudou(anterior, mudadas, 'color'):
        cor = cor_ao_trocar_simbolo_linha(anterior.get('symbol_code'), mudadas['symbol_code'], anterior.get('color'))
        if cor:
            extra['color'] = cor
    return extra


_REGRAS = {'coordination_line': _linha_coordenacao}


def ao_mudar(tipo, anterior, mudadas):
    regra = _REGRAS.get(tipo)
    return regra(anterior, mudadas) if regra else {}
