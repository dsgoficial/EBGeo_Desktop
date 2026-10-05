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


# ---------------------------------------------------------------------------------------------
# Linhas táticas sem catálogo: Linha de Limite, Seta e Frente Ocupada
# ---------------------------------------------------------------------------------------------
# As três entram no guardião (feição bloqueada, atualizado_em) mesmo sem regra de troca. A do
# Limite protege as posições do símbolo (symbol_instances, lista JSON), que só o dock edita: a
# gravação ilegível por outro caminho (calculadora de campo, tabela) volta ao valor anterior, em
# vez de o desenho cair em silêncio na instância padrão.
MAX_INSTANCIAS_LIMITE = 6  # o Web oferece de 1 a 6 repetições


def _razao_limite(r):
    """clampRatio do Web e `rs` de _limite.exp: nula ou ilegível vale 0,5; fora da linha, 0,01 a 0,99."""
    try:
        r = float(r)
    except (TypeError, ValueError):
        return 0.5
    if r != r:  # NaN
        return 0.5
    return min(0.99, max(0.01, r))


def ler_instancias_limite(bruto):
    """
    As posições do símbolo da Linha de Limite como o desenho as lê (getSymbolInstances do Web):
    devolve (lista de {'ratio', 'showLabels'}, legível). A coluna chega como lista (importador)
    ou texto JSON (gravada pelo QGIS); nula ou lista vazia é a instância padrão, legível. Texto
    que não é lista JSON, ou lista sem nenhum objeto, é ilegível, e também dá a padrão.
    """
    import json
    padrao = [{'ratio': 0.5, 'showLabels': True}]
    v = None if _nulo(bruto) else bruto
    if v is None or (isinstance(v, str) and not v.strip()):
        return padrao, True
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return padrao, False
    if not isinstance(v, (list, tuple)):
        return padrao, False
    if not v:
        return padrao, True
    lista = [{'ratio': _razao_limite(i.get('ratio')), 'showLabels': i.get('showLabels') is not False}
             for i in v if isinstance(i, dict)]
    return (lista, True) if lista else (padrao, False)


def redistribuir_instancias(atuais, n):
    """Repetições do Web: n posições igualmente espaçadas, (i + 1) / (n + 1), mantendo os rótulos."""
    n = max(1, min(MAX_INSTANCIAS_LIMITE, int(n)))
    return [{'ratio': round((i + 1) / (n + 1), 4),
             'showLabels': atuais[i]['showLabels'] if i < len(atuais) else True} for i in range(n)]


def _linha_de_limite(anterior, mudadas):
    if not mudou(anterior, mudadas, 'symbol_instances'):
        return {}
    _lista, legivel = ler_instancias_limite(mudadas['symbol_instances'])
    if legivel:
        return {}
    volta, _ok = ler_instancias_limite(anterior.get('symbol_instances'))
    return {'symbol_instances': volta}


CAMPOS_VIGIADOS.update({'boundary': ('symbol_instances',), 'arrow': (), 'occupied_front': ()})
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
_REGRAS['boundary'] = _linha_de_limite


# ---------------------------------------------------------------------------------------------
# Medida de Coordenação
# ---------------------------------------------------------------------------------------------
# Ao trocar a medida (`point_code`), como o seletor do Web e o dock de antes: o escalão acompanha
# a família, mantendo o número (fora de família, fica nulo); a cor padrão do tipo (destruições
# verdes) entra só em quem ainda veste a do tipo anterior; e as escolhas de desenho de um tipo
# (minas do 270701, seta secundária do 140500) não valem para outro. O catálogo e as funções
# puras são as do formulário (formulario/tipos/medida.py).

def _medida_de_coordenacao(anterior, mudadas):
    if not mudou(anterior, mudadas, 'point_code'):
        return {}
    from .formulario.tipos import medida as m
    extra = {}
    novo = mudadas['point_code']
    echelon = anterior.get('echelon_code')
    if mudou(anterior, mudadas, 'echelon_code'):
        echelon = mudadas['echelon_code']
    else:
        escalao = m.escalao_ao_trocar(anterior.get('echelon_code'), novo)
        if not iguais(escalao, anterior.get('echelon_code')):
            extra['echelon_code'] = escalao
            echelon = escalao
    if not mudou(anterior, mudadas, 'fill_color'):
        cor = m.cor_ao_trocar(m.codigo_desenhavel(anterior.get('point_code'), anterior.get('echelon_code')),
                              m.codigo_desenhavel(novo, echelon), anterior.get('fill_color'))
        if cor is not False:
            extra['fill_color'] = cor
    for col in m.escolhas_de_desenho():
        if valor(anterior.get(col)) not in (None, '') and not mudou(anterior, mudadas, col):
            extra[col] = None
    return extra


CAMPOS_VIGIADOS.update({'coordination_measure': ('point_code', 'echelon_code', 'fill_color', 'mina1', 'mina2', 'mina3',
                                                 'angulo_secundario')})
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
_REGRAS['coordination_measure'] = _medida_de_coordenacao


# ---------------------------------------------------------------------------------------------
# Área de Coordenação: os padrões do tipo na troca de símbolo e a hachura que acompanha o tipo
# ---------------------------------------------------------------------------------------------
# Saíram do dock (ui/painel_area.py) e de estilos_area.troca_de_simbolo. O mesmo par vale sem o
# plugin pela metade: hatch_enabled também é valor padrão na atualização do estilo da camada
# (estilos_area.hachura_acompanha_o_tipo); os padrões do tipo, só com o guardião.

def _catalogo_area():
    from .estilos_area import CATALOGO_AREA, MINAS_PADRAO, SIMBOLO_PADRAO
    return CATALOGO_AREA, MINAS_PADRAO, SIMBOLO_PADRAO


def codigo_area(codigo):
    """O código como o estilo o desenha: nulo, vazio e desconhecido valem a Área genérica."""
    catalogo, _m, padrao = _catalogo_area()
    codigo = '' if _nulo(codigo) else str(codigo)
    return codigo if codigo in catalogo else padrao


def _mesmo_padrao(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-9
        except (TypeError, ValueError):
            return False
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    return a == b


def minas_validas(v):
    """A lista das três minas, lida do texto JSON ou da lista; None quando o desenho a troca pela padrão."""
    import json
    v = valor(v)
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return None
    return list(v) if isinstance(v, (list, tuple)) and len(v) == 3 else None


def padroes_da_troca_area(atuais, novo):
    """
    updateSymbol do Web: {coluna: valor} a gravar quando a área passa ao tipo `novo`, com o
    symbol_code. Cada valor de aparência que a área ainda tem no padrão do tipo ANTERIOR (ou nulo)
    passa ao padrão do novo; valor escolhido fica. A posição do texto que estava no padrão do tipo
    anterior (ou nula) vai à do novo, e a Área minada sem as três minas ganha as padrão.
    """
    catalogo, minas_padrao, _p = _catalogo_area()
    ant = catalogo[codigo_area(atuais.get('symbol_code'))]
    cod = codigo_area(novo)
    nov = catalogo[cod]
    mud = {'symbol_code': cod}
    for col, padrao in nov['padroes'].items():
        atual = valor(atuais.get(col))
        if atual is None or _mesmo_padrao(atual, ant['padroes'].get(col)):
            mud[col] = padrao
    posicao = valor(atuais.get('text_position'))
    if not posicao or posicao == ant.get('posicao', 'borda'):
        mud['text_position'] = nov.get('posicao', 'borda')
    if nov.get('minas') and minas_validas(atuais.get('minas')) is None:
        mud['minas'] = list(minas_padrao)
    return mud


def hachura_ligada(tipo_hachura):
    """updateHatchType do Web: a hachura liga com qualquer tipo que não seja 'none'."""
    tipo_hachura = valor(tipo_hachura)
    return tipo_hachura is not None and str(tipo_hachura) not in ('', 'none')


def _area_coordenacao(anterior, mudadas):
    extra = {}
    if mudou(anterior, mudadas, 'symbol_code'):
        for col, v in padroes_da_troca_area(anterior, mudadas['symbol_code']).items():
            if col == 'symbol_code' or mudou(anterior, mudadas, col):
                continue
            atual = anterior.get(col)
            if col == 'minas' or not (atual is not None and _mesmo_padrao(valor(atual), v)):
                extra[col] = v
    tipo_hachura = extra.get('hatch_type', mudadas.get('hatch_type') if mudou(anterior, mudadas, 'hatch_type') else None)
    if tipo_hachura is not None and 'hatch_enabled' not in extra and not mudou(anterior, mudadas, 'hatch_enabled'):
        ligada = hachura_ligada(tipo_hachura)
        if valor(anterior.get('hatch_enabled')) != ligada:
            extra['hatch_enabled'] = ligada
    return extra


CAMPOS_VIGIADOS['coordination_area'] = ('symbol_code', 'line_color', 'line_width', 'fill_color', 'opacity',
                                        'hatch_type', 'hatch_enabled', 'text_position', 'minas')
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
_REGRAS['coordination_area'] = _area_coordenacao


# ---------------------------------------------------------------------------------------------
# Símbolo Militar e Símbolo de Engenharia
# ---------------------------------------------------------------------------------------------
# O construtor de SIDC grava, junto com o SIDC, o modificador especial e o elemento de comando
# que a extensão brasileira dele traz (dígitos 21 a 30); o SIDC mudado por outro caminho
# (formulário nativo, tabela) os acerta igual. O seletor de engenharia, ao trocar de item, volta o
# formulário do item aos padrões (engineeringDraft do Web); a troca de item por outro caminho
# grava o mesmo rascunho, para o JSON não guardar os valores do item anterior.

def derivados_do_sidc(sidc):
    """{'special_modifier', 'is_command'} da extensão do SIDC, ou None para SIDC inválido."""
    from .ui.construtor_sidc import desmontar_sidc
    d = desmontar_sidc(None if _nulo(sidc) else str(sidc))
    if d is None:
        return None
    return {'special_modifier': str(d['especial']) if d['especial'] else None, 'is_command': bool(d['comando'])}


def _simbolo_militar(anterior, mudadas):
    if not mudou(anterior, mudadas, 'sidc'):
        return {}
    derivados = derivados_do_sidc(mudadas['sidc']) or {}
    return {c: v for c, v in derivados.items() if not mudou(anterior, mudadas, c) and not iguais(anterior.get(c), v)}


def rascunho_engenharia(codigo):
    """O formulário do item com os padrões (engineeringDraft do motor; sem ele, o do catálogo)."""
    codigo = '' if _nulo(codigo) else str(codigo)
    try:
        from .motor.motor import Motor
        return Motor.instancia().engenharia_rascunho(codigo, {})
    except Exception:
        from .formulario.tipos.militar import catalogos
        for it in catalogos()['engenharia']['itens']:
            if str(it['codigo']) == codigo:
                return {'variant': 0, 'values': {c['chave']: c.get('padrao') for c in it['campos']}}
    return None


def _simbolo_engenharia(anterior, mudadas):
    if not mudou(anterior, mudadas, 'point_code') or mudou(anterior, mudadas, 'engineering'):
        return {}
    rascunho = rascunho_engenharia(mudadas['point_code'])
    return {'engineering': rascunho} if rascunho is not None else {}


CAMPOS_VIGIADOS.update({'military_symbol': ('sidc', 'special_modifier', 'is_command'),
                        'engineering_symbol': ('point_code', 'engineering'),
                        'magnetic_declination': ()})
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
_REGRAS.update({'military_symbol': _simbolo_militar, 'engineering_symbol': _simbolo_engenharia})


# ---------------------------------------------------------------------------------------------
# Feições comuns do mapa 2D (formulario/tipos/comuns.py): sem regra de troca, mas no guardião,
# que reverte a edição da feição bloqueada no EBGeo Web pela tabela de atributos e renova
# atualizado_em na camada sem o valor padrão.
# ---------------------------------------------------------------------------------------------
CAMPOS_VIGIADOS.update({t: () for t in ('point', 'line', 'polygon', 'circle', 'ellipse', 'rectangle', 'sector', 'text',
                                         'image', 'brush', 'los', 'visibility', 'processed_los', 'processed_visibility')})
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
