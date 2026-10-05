# -*- coding: utf-8 -*-
"""
Formulário do Símbolo Militar, do Símbolo de Engenharia e da Declinação Magnética.

Tudo o que depende do símbolo sai dos catálogos do motor (motor/catalogos.json, gerado do Web),
nunca de lista à mão:

  - Símbolo Militar: os amplificadores de texto aparecem conforme o CONJUNTO do SIDC (dígitos 5 e
    6), pela lista `camposTexto` de cada conjunto, a mesma que o construtor de SIDC monta; a barra
    de engajamento, onde o conjunto a admite (`aplicavel.barraEngajamento`). O rótulo é o do
    catálogo com o código do campo ("Designação (C)"), e o que muda com o conjunto ("Profundidade"
    nos submarinos) muda por dados. O SIDC é texto com restrição forte (20 ou 30 dígitos), e um
    texto por expressão o traduz (identidade, conjunto, status, escalão, ícone). O construtor de
    SIDC é o widget rico do dock.
  - Símbolo de Engenharia: o item como lista "N. título"; a variante e os valores do item, que o
    seletor grava no JSON `engineering`, aparecem legíveis num texto por expressão (o JSON fica
    oculto: o editor nativo dele não representa o formulário do item). O seletor é o rico do dock.
  - Declinação Magnética: os valores do WMM2025 só para leitura, o ângulo de quadrícula calculado
    e a aparência que o Web edita.

Os textos por expressão usam current_value(), que o formulário nativo renova a cada mudança de
campo; o dock avalia o mesmo texto com o escopo de formulário da feição.

Uma regra do Web que não está no catálogo: o campo Direção do modal do símbolo não aparece nos
conjuntos 20 (Instalações) e 40 (Atividades e Eventos) (symbol-form.section.js do EBGeo Web,
createDirectionInput).
"""
import json
import os
from dataclasses import dataclass

from .. import especificacao as esp

ARQ_CATALOGOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             'motor', 'catalogos.json')
CONJUNTOS_SEM_DIRECAO = frozenset({'20', '40'})
# Itens de engenharia em que a variante sai de um dado do item (a inclinação na Rampa, o tipo de
# folhagem na Cobertura e na Coberta; seletor_engenharia.VARIANTE_POR_CAMPO): o texto legível
# mostra o dado, não a variante gravada.
VARIANTE_DERIVADA = frozenset({'5', '20', '21'})
# O SIDC igual ao padrão da coluna no GeoPackage (DEFAULT da tabela) chega à restrição do formulário
# como "valor padrão do provedor" (QgsUnsetAttributeValue), que to_string() devolve nulo sem ser
# nulo; sem o primeiro ramo, o SIDC padrão reprovava e o formulário não gravava nada (medido no
# QGIS 4.0.0).
EXPRESSAO_SIDC_VALIDO = ("CASE WHEN to_string(\"sidc\") IS NULL AND \"sidc\" IS NOT NULL THEN TRUE "
                         "ELSE regexp_match(coalesce(\"sidc\", ''), '^([0-9]{20}|[0-9]{30})$') > 0 END")
AVISO_SIDC = 'O SIDC tem 20 ou 30 dígitos (só números).'
OCULTOS_SVG = ('svg', 'svg_assinatura', 'largura_px', 'altura_px', 'ancora_dx', 'ancora_dy',
               'bitmap_b64', 'bitmap_mime')
_CACHE = {}


def catalogos():
    if 'c' not in _CACHE:
        with open(ARQ_CATALOGOS, encoding='utf-8') as fh:
            _CACHE['c'] = json.load(fh)
    return _CACHE['c']


def _lit(v):
    return esp._literal(v)


def _mapa(pares):
    """Expressão map('chave', 'valor', ...) do QGIS."""
    return 'map({})'.format(', '.join('{}, {}'.format(_lit(k), _lit(v)) for k, v in pares))


# ---------------------------------------------------------------------------------------------
# Condição pelo conjunto do SIDC
# ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class CondicaoConjunto:
    """
    Vale quando o conjunto do SIDC (dígitos 5 e 6) está em `valores` (ou fora, com `negar`). Mesmo
    contrato de especificacao.Condicao: `expressao()` para o QGIS, `avaliar()` em Python.
    """
    valores: frozenset
    negar: bool = False
    coluna: str = 'sidc'

    def expressao(self):
        if not self.valores:
            return 'TRUE' if self.negar else 'FALSE'
        dentro = 'coalesce(substr("{}", 5, 2), \'\') IN ({})'.format(
            self.coluna, ', '.join(_lit(v) for v in sorted(self.valores)))
        return 'NOT ({})'.format(dentro) if self.negar else dentro

    def avaliar(self, atributos):
        v = atributos.get(self.coluna)
        v = '' if esp._nulo(v) else str(v)
        return (v[4:6] in self.valores) != self.negar


def conjunto_padrao():
    from ... import schema
    return dict((c[0], c[2]) for c in schema.TIPOS['military_symbol']['campos'])['sidc'][4:6]


def por_conjunto(predicado):
    """
    "O conjunto do SIDC tem a propriedade", gerada do catálogo; o conjunto fora do catálogo (e o
    SIDC nulo ou curto) vale como o do SIDC padrão, pela negativa quando o padrão a tem.
    """
    por = catalogos()['militar']['porConjunto']
    tem = frozenset(c for c, d in por.items() if predicado(c, d))
    if predicado(conjunto_padrao(), por[conjunto_padrao()]):
        return CondicaoConjunto(frozenset(por) - tem, negar=True)
    return CondicaoConjunto(tem)


# ---------------------------------------------------------------------------------------------
# Símbolo Militar
# ---------------------------------------------------------------------------------------------

def _ids_texto(dados):
    return [f['id'] for f in (dados.get('camposTexto') or {}).get('fields', [])]


def rotulos_amplificadores():
    """
    {propriedade do Web: (rótulo, [(conjuntos, rótulo variante)])} dos campos de texto do
    catálogo (text_modifiers_catalog.js do Web): o rótulo mais comum e, quando algum conjunto o
    chama de outro modo, a variante. Como no Web, sem a letra da norma.
    """
    por = catalogos()['militar']['porConjunto']
    rot = {}
    for conj, dados in por.items():
        for f in (dados.get('camposTexto') or {}).get('fields', []):
            rot.setdefault(f['id'], {}).setdefault(f['label'], set()).add(conj)
    res = {}
    for web, variantes in rot.items():
        ordem = sorted(variantes.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        res[web] = (ordem[0][0], [(frozenset(cs), t) for t, cs in ordem[1:]])
    return res


def dicas_amplificadores():
    """{propriedade do Web: ({conjunto: dica}, dica mais comum)}, as dicas (tooltip) do Web."""
    por = catalogos()['militar']['porConjunto']
    res = {}
    for conj, dados in por.items():
        for f in (dados.get('camposTexto') or {}).get('fields', []):
            if f.get('tooltip'):
                res.setdefault(f['id'], {})[conj] = f['tooltip']
    out = {}
    for web, por_conj in res.items():
        contagem = {}
        for d in por_conj.values():
            contagem[d] = contagem.get(d, 0) + 1
        out[web] = (por_conj, sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])
    return out


def _dica_do_conjunto(por_conj, comum):
    def dica(atributos):
        v = atributos.get('sidc')
        v = '' if esp._nulo(v) else str(v)
        return por_conj.get(v[4:6] if len(v) >= 6 else conjunto_padrao(), comum)
    return dica


def ordem_amplificadores():
    """As propriedades de texto na ordem do catálogo (a de Unidades primeiro, depois as novas)."""
    vistos = []
    for dados in catalogos()['militar']['porConjunto'].values():
        for web in _ids_texto(dados):
            if web not in vistos:
                vistos.append(web)
    return vistos


def campos_amplificadores():
    from ... import schema
    col = {w: c for c, w in schema.AMPLIFICADORES}
    rotulos = rotulos_amplificadores()
    dicas = dicas_amplificadores()
    campos = []
    for web in ordem_amplificadores():
        rotulo, variantes = rotulos[web]
        if len(variantes) > 1:
            raise ValueError('{}: mais de uma variante de rótulo no catálogo'.format(web))
        rotulo_se = (CondicaoConjunto(variantes[0][0]), variantes[0][1]) if variantes else None
        por_conj, comum = dicas.get(web, ({}, None))
        campos.append(esp.Campo(col[web], rotulo, esp.texto(),
                                condicao=por_conjunto(lambda _c, d, w=web: w in _ids_texto(d)),
                                rotulo_se=rotulo_se, dica=comum,
                                dica_por=_dica_do_conjunto(por_conj, comum) if por_conj else None))
    campos.append(esp.Campo(col['direction'], 'Direção (azimute em graus)', esp.texto(),
                            condicao=por_conjunto(lambda c, _d: c not in CONJUNTOS_SEM_DIRECAO)))
    campos.append(esp.Campo(col['engagementBar'], 'Barra de engajamento', esp.texto(),
                            condicao=por_conjunto(lambda _c, d: bool((d.get('aplicavel') or {}).get('barraEngajamento')))))
    faltam = set(col) - {col_web for col_web in ordem_amplificadores()} - {'direction', 'engagementBar'}
    if faltam:
        raise ValueError('amplificadores fora do catálogo: {}'.format(sorted(faltam)))
    return campos


def expressao_sidc_legivel():
    """O texto que traduz o SIDC: identidade, conjunto, status, QG/FT, escalão e ícone."""
    m = catalogos()['militar']
    por = m['porConjunto']
    rot_conj = {c['value']: c['label'] for c in m['conjuntos']}
    escaloes, icones = [], []
    for conj, dados in por.items():
        esc = dados.get('escalao') or {}
        if isinstance(esc, dict) and esc.get('applicable'):
            for e in esc.get('data', []):
                if e['value'] != '00':
                    escaloes.append(('{}|{}'.format(conj, e['value']), '{}: {}'.format(esc.get('label') or 'Escalão', e['label'])))
        vistos = set()
        for ic in dados.get('icones', []):
            chave = '{}|{}'.format(conj, ic['codigo'])
            if chave in vistos:
                continue  # código repetido com extensão de entidade: vale o primeiro, como no construtor
            vistos.add(chave)
            icones.append((chave, ic['nome'] + (' / ' + ic['subtipo'] if ic.get('subtipo') else '')))
    qgft = [(q['value'], q['label']) for q in m['qgFtSimulado'] if q['value'] != '0']
    linhas = [
        "'Identidade: ' || coalesce(map_get({}, substr(@s, 4, 1)), substr(@s, 4, 1))".format(
            _mapa((i['value'], i['label']) for i in m['identidades'])),
        "'Conjunto: ' || coalesce(map_get({}, substr(@s, 5, 2)), substr(@s, 5, 2) || ' (fora do catálogo)')".format(
            _mapa(rot_conj.items())),
        "'Status: ' || coalesce(map_get({}, substr(@s, 7, 1)), substr(@s, 7, 1))".format(
            _mapa((s['value'], s['label']) for s in m['status'])),
    ]
    opcionais = [
        "map_get({}, substr(@s, 8, 1))".format(_mapa(qgft)),
        "map_get({}, substr(@s, 5, 2) || '|' || substr(@s, 9, 2))".format(_mapa(escaloes)),
        "'Ícone: ' || map_get({}, substr(@s, 5, 2) || '|' || substr(@s, 11, 6))".format(_mapa(icones)),
    ]
    corpo = " || '\\n' || ".join(linhas) + ''.join(" || coalesce('\\n' || {}, '')".format(o) for o in opcionais)
    return ("[% with_variable('s', coalesce(to_string(current_value('sidc')), ''), "
            "CASE WHEN regexp_match(@s, '^([0-9]{{20}}|[0-9]{{30}})$') = 0 THEN {aviso} ELSE {corpo} END) %]").format(
        aviso=_lit(AVISO_SIDC), corpo=corpo)


def _aparencia(rotacao=True, rotulo_cor='Cor de preenchimento'):
    """Tamanho, rotação, opacidade, cor e correção de zoom, com os ajudantes comuns da especificação."""
    filhos = [esp.Campo('size', 'Tamanho', esp.numero(0.1, 5, 0.1, 2))]
    if rotacao:
        filhos.append(esp.Campo('rotation', 'Rotação', esp.numero(-360, 360, 15, 2, '°')))
    filhos += [esp.Campo('opacity', 'Opacidade', esp.numero(0, 1, 0.05, 2)),
               esp.Campo('fill_color', rotulo_cor, esp.cor()),
               esp.grupo_zoom()]
    return esp.Aba('Aparência', filhos)


def simbolo_militar():
    simbolo = esp.Aba('Símbolo', [
        esp.previa_simbolo(),
        esp.Campo('sidc', 'SIDC', esp.texto(), rico='sidc', restricao=(EXPRESSAO_SIDC_VALIDO, AVISO_SIDC)),
        esp.Texto('sidc_legivel', expressao_sidc_legivel()),
        esp.descricao(),
    ])
    textos = esp.Aba('Textos', campos_amplificadores())
    return esp.Formulario('military_symbol', esp.cabecalho(),
                          [simbolo, textos, _aparencia(), esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + OCULTOS_SVG + ('special_modifier', 'is_command'))


# ---------------------------------------------------------------------------------------------
# Símbolo de Engenharia
# ---------------------------------------------------------------------------------------------

def itens_engenharia():
    return sorted(catalogos()['engenharia']['itens'], key=lambda it: int(it['numero']))


def _valor_campo(campo):
    """Expressão do valor legível de um campo do item, com o padrão do catálogo quando falta."""
    bruto = "map_get(@v, {})".format(_lit(campo['chave']))
    if campo['tipo'] == 'checkbox':
        return "if(coalesce({}, {}), 'Sim', 'Não')".format(bruto, 'true' if campo.get('padrao') else 'false')
    padrao = '' if campo.get('padrao') is None else str(campo['padrao'])
    texto = "coalesce(to_string({}), {})".format(bruto, _lit(padrao))
    if campo['tipo'] == 'select':
        return "coalesce(map_get({}, {t}), {t})".format(_mapa((o['valor'], o['rotulo']) for o in campo.get('opcoes', [])), t=texto)
    return texto


def expressao_engenharia_legivel():
    """
    A variante e os valores do item, legíveis. Com o item trocado no próprio formulário, mostra os
    padrões do item novo, que é o que o guardião grava ao salvar (regras.py).
    """
    ramos = []
    for it in itens_engenharia():
        partes = []
        if len(it['variantes']) > 1 and str(it['codigo']) not in VARIANTE_DERIVADA:
            partes.append("{} || coalesce(map_get({}, to_string(coalesce(map_get(@e, 'variant'), 0))), '?')".format(
                _lit((it.get('rotuloVariante') or 'Variante') + ': '),
                _mapa((str(v['indice']), v['rotulo']) for v in it['variantes'])))
        for c in it['campos']:
            partes.append('{} || {}'.format(_lit(c['rotulo'] + ': '), _valor_campo(c)))
        corpo = " || '\\n' || ".join(partes) if partes else _lit('Sem dados variáveis neste símbolo.')
        ramos.append('WHEN @c = {} THEN {}'.format(_lit(str(it['codigo'])), corpo))
    eng = "coalesce(try(from_json(current_value('engineering'))), current_value('engineering'))"
    return ("[% with_variable('c', coalesce(to_string(current_value('point_code')), ''), "
            "with_variable('e', if(@c = coalesce(to_string(\"point_code\"), ''), coalesce({eng}, map()), map()), "
            "with_variable('v', coalesce(map_get(@e, 'values'), map()), "
            "CASE {ramos} ELSE 'Item fora do catálogo do C 5-36.' END))) %]").format(eng=eng, ramos=' '.join(ramos))


def simbolo_engenharia():
    opcoes = [(str(it['codigo']), '{}. {}'.format(it['numero'], it['titulo'])) for it in itens_engenharia()]
    simbolo = esp.Aba('Símbolo', [
        esp.previa_simbolo(),
        esp.Campo('point_code', 'Símbolo (C 5-36)', esp.lista(opcoes), rico='engenharia'),
        esp.Texto('engenharia_legivel', expressao_engenharia_legivel()),
        esp.descricao(),
    ])
    return esp.Formulario('engineering_symbol', esp.cabecalho(),
                          [simbolo, _aparencia(), esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + OCULTOS_SVG + ('engineering',))


# ---------------------------------------------------------------------------------------------
# Declinação Magnética
# ---------------------------------------------------------------------------------------------

AVISO_RECALCULAR = ('Os valores são do WMM2025 no ponto. Depois de mover o diagrama, "Recalcular" no '
                    'painel do calco os atualiza para o local novo.')
EXPRESSAO_QUADRICULA = ("[% 'Ângulo de quadrícula (NQ-NM): ' || format_number(coalesce(current_value('declination'), 0) "
                        "- coalesce(current_value('convergence'), 0), 2) || '°' %]")


def declinacao_magnetica():
    nortes = esp.Aba('Diagrama de nortes', [
        esp.previa_simbolo(),
        esp.Campo('declination', 'Declinação magnética (NV-NM)', esp.numero(-180, 180, 0.01, 2, '°'), somente_leitura=True),
        esp.Campo('convergence', 'Convergência meridiana (NV-NQ)', esp.numero(-180, 180, 0.01, 2, '°'), somente_leitura=True),
        esp.Texto('angulo_quadricula', EXPRESSAO_QUADRICULA),
        esp.Campo('inclination', 'Inclinação magnética', esp.numero(-90, 90, 0.01, 2, '°'), somente_leitura=True),
        esp.Campo('intensity', 'Intensidade do campo (nT)', esp.numero(0, 100000, 1, 0, ' nT'), somente_leitura=True),
        esp.Campo('calculation_date', 'Data do cálculo (WMM2025)', esp.texto(), somente_leitura=True),
        esp.Texto('aviso_recalcular', AVISO_RECALCULAR),
        esp.descricao(),
    ])
    return esp.Formulario('magnetic_declination', esp.cabecalho(),
                          [nortes, _aparencia(rotacao=False, rotulo_cor='Cor'), esp.aba_atributos(), esp.aba_avancado()],
                          esp.OCULTOS_COMUNS + OCULTOS_SVG + ('rotation',))


CONSTRUTORES = {
    'military_symbol': simbolo_militar,
    'engineering_symbol': simbolo_engenharia,
    'magnetic_declination': declinacao_magnetica,
}
