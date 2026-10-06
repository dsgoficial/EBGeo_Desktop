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
# Seta combinada: o ramo editado no dock
# ---------------------------------------------------------------------------------------------
# O painel do Web edita, em cada ramo da seta combinada, a largura, o aeromóvel, a ponta e a ponta
# dupla (_addBranchGeometryControls de arrow_attributes_panel.js), e o dock faz o mesmo na coluna
# `ramos` ({'ramos': [propriedades de cada ramo], 'topo': {chave: valor das colunas na
# importação}}, schema.ramos_seta). O que o ramo desenha é o que seta_ramo.exp lê: a do ramo vale
# enquanto a coluna da feição é a da importação; editada no Desktop, a coluna vale para todos os
# ramos. A largura do ramo cai na da feição quando falsa; a ponta, a ponta dupla e o aeromóvel não.

# (chave do Web, coluna da feição, o que o estilo desenha com a coluna nula: seta.exp)
CHAVES_RAMO_DOCK = (('width', 'width_m', 1000.0), ('airmobile', 'airmobile', False),
                    ('showArrowHead', 'show_arrow_head', True), ('doubleHeaded', 'double_headed', False))
# as outras duas propriedades do ramo, que o dock não edita por ramo, como o painel do Web
_OUTRAS_RAMO = (('headLengthRatio', 'head_length_ratio'), ('airmobilePosition', 'airmobile_position'))


def ler_ramos_seta(bruto):
    """(lista das propriedades de cada ramo, topo) da coluna `ramos`, lista ou texto JSON; ([], None) sem ela."""
    import json
    v = valor(bruto)
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            v = None
    if not isinstance(v, dict) or not isinstance(v.get('ramos'), list):
        return [], None
    topo = v.get('topo') if isinstance(v.get('topo'), dict) else {}
    return [r if isinstance(r, dict) else {} for r in v['ramos']], topo


def _numero_nao_zero(v):
    v = valor(v)
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0


def _editada(colunas, topo, chave, coluna):
    """A coluna da feição editada no Desktop: diferente da importação (o IS de seta_ramo.exp)."""
    a, b = valor(colunas.get(coluna)), valor(topo.get(chave))
    if a is None or b is None:
        return (a is None) != (b is None)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is not b
    try:
        return float(a) != float(b)
    except (TypeError, ValueError):
        return a != b


def _da_feicao(chave, coluna, nulo, colunas):
    v = valor(colunas.get(coluna))
    if chave == 'width':
        return abs(float(v)) if _numero_nao_zero(v) else nulo
    return nulo if v is None else bool(v)


def ramos_desenhados(bruto, colunas, n):
    """
    [{chave: valor}] dos `n` ramos, como seta_ramo.exp os desenha (CHAVES_RAMO_DOCK): o do ramo
    enquanto a coluna da feição é a da importação, senão o da feição; o ramo além da lista vale o
    da feição.
    """
    lista, topo = ler_ramos_seta(bruto)
    topo = topo or {}
    out = []
    for j in range(n):
        r = {}
        for chave, coluna, nulo in CHAVES_RAMO_DOCK:
            feicao = _da_feicao(chave, coluna, nulo, colunas)
            if j >= len(lista) or _editada(colunas, topo, chave, coluna):
                r[chave] = feicao
            elif chave == 'width':
                r[chave] = abs(float(lista[j]['width'])) if _numero_nao_zero(lista[j].get('width')) else feicao
            elif chave == 'showArrowHead':
                r[chave] = lista[j].get(chave) is not False
            else:
                r[chave] = lista[j].get(chave) is True
        out.append(r)
    return out


def editar_ramo(bruto, colunas, n, i, chave, novo):
    """
    O ramo `i` (de `n`) com `chave` = `novo`, sem mudar o desenho dos outros: devolve (coluna
    `ramos` nova, {coluna da feição: valor a regravar}). Como o _updateBranchProperty do Web, a
    lista inteira é regravada e o ramo 0 é o espelho do topo (o exportador o devolve ao topo,
    Montador._ramos). Quando a coluna da feição da chave foi editada no Desktop (valia para todos os
    ramos), cada ramo passa a guardar o valor dela e a coluna volta à da importação: senão o estilo
    e o exportador seguiriam com a da feição em todos os ramos. Ramo além da lista (parte nova da
    geometria) entra com o que desenhava, o da feição. Sem a coluna, o topo é o valor das colunas.
    """
    lista, topo = ler_ramos_seta(bruto)
    if topo is None:
        topo = {w: valor(colunas.get(c)) for w, c, _n in CHAVES_RAMO_DOCK}
        topo.update({w: valor(colunas.get(c)) for w, c in _OUTRAS_RAMO})
    lista = [dict(r) for r in lista]
    desenhados = ramos_desenhados(bruto, colunas, n)
    for j in range(len(lista), n):
        r = dict(desenhados[j])
        for w, c in _OUTRAS_RAMO:
            if _numero_nao_zero(colunas.get(c)):
                r[w] = valor(colunas.get(c))
        lista.append(r)
    regravar = {}
    coluna = dict((w, c) for w, c, _n in CHAVES_RAMO_DOCK)[chave]
    if _editada(colunas, topo, chave, coluna):
        for j, r in enumerate(lista[:n]):
            r[chave] = desenhados[j][chave]
        regravar[coluna] = topo.get(chave)
    lista[i][chave] = novo
    return {'ramos': lista, 'topo': topo}, regravar


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


# ---------------------------------------------------------------------------------------------
# Hachura visível (decisão do chefe, 2026-10-05): na Área e nas cinco formas comuns, a cor da
# hachura leva a opacidade do preenchimento, e com opacidade 0 (o padrão da Área genérica) a
# hachura escolhida sai invisível. Na transição de sem hachura para com hachura, a opacidade 0
# vai a 1; a feição que já tem hachura não muda, e a opacidade que o operador muda na mesma
# edição fica. "Com hachura" é o que o estilo desenha: a caixa ligada e um dos tipos das camadas
# de padrão (COND_HACHURA e HACHURAS_DESENHADAS do estilo; nas formas também o tipo vazio, que
# desenha diagonal como o Web, VALORES_QUE_DESENHAM).
# ---------------------------------------------------------------------------------------------

def _real(v):
    """O número da coluna; o marcador de "não definido" do formulário vale o DEFAULT da coluna."""
    if nao_definido(v):
        v = v.defaultValueClause()
    v = valor(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def hachura_desenhada(atributos, desenhadas):
    """
    O estilo desenha a hachura: a caixa ligada e um tipo das camadas de padrão (`desenhadas`, na
    grafia das condições do formulário: o tipo nulo é '', que as formas desenham diagonal e a
    Área não desenha). O marcador de "não definido" vale o DEFAULT da coluna.
    """
    ligada, tipo = valor(atributos.get('hatch_enabled')), atributos.get('hatch_type')
    if nao_definido(tipo):
        tipo = str(tipo.defaultValueClause()).strip("'")
    tipo = valor(tipo)
    return bool(ligada) and not nao_definido(ligada) and ('' if tipo is None else str(tipo)) in desenhadas


def opacidade_ao_ligar_hachura(anterior, mudadas, extra, desenhadas):
    """{'opacity': 1.0} quando a edição faz a hachura aparecer na feição de opacidade 0; senão {}."""
    if mudou(anterior, mudadas, 'opacity') or 'opacity' in extra:
        return {}
    depois = dict(anterior)
    depois.update({c: v for c, v in mudadas.items() if not nao_definido(v)})
    depois.update(extra)
    if hachura_desenhada(anterior, desenhadas) or not hachura_desenhada(depois, desenhadas):
        return {}
    return {'opacity': 1.0} if _real(depois.get('opacity')) == 0 else {}


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
    # só quando a edição troca o tipo da hachura (ou o símbolo, que traz o dele): hatch_enabled
    # não tem widget na Área, e o valor padrão na atualização o liga ao salvar QUALQUER mudança
    # da área com tipo e caixa em desacordo; salvar só o nome não pode mudar a opacidade
    if 'hatch_type' in extra or mudou(anterior, mudadas, 'hatch_type'):
        from .estilos_area import HACHURAS_DESENHADAS
        extra.update(opacidade_ao_ligar_hachura(anterior, mudadas, extra, HACHURAS_DESENHADAS))
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
# Feições comuns do mapa 2D (formulario/tipos/comuns.py): no guardião, que reverte a edição da
# feição bloqueada no EBGeo Web pela tabela de atributos e renova atualizado_em na camada sem o
# valor padrão; as formas têm a regra da hachura visível.
# ---------------------------------------------------------------------------------------------
CAMPOS_VIGIADOS.update({t: () for t in ('point', 'line', 'text', 'image', 'brush', 'los', 'visibility', 'processed_los',
                                         'processed_visibility')})


# As cinco formas (Polígono, Círculo, Elipse, Retângulo, Setor): a hachura visível, como na Área.
def _forma(anterior, mudadas):
    from .estilos_formas import VALORES_QUE_DESENHAM
    return opacidade_ao_ligar_hachura(anterior, mudadas, {}, VALORES_QUE_DESENHAM)


CAMPOS_VIGIADOS.update({t: ('opacity', 'hatch_enabled', 'hatch_type')
                        for t in ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')})
_REGRAS.update({t: _forma for t in ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')})
TIPOS_COM_REGRAS = frozenset(CAMPOS_VIGIADOS)
