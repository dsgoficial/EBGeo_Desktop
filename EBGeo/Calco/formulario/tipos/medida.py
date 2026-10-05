# -*- coding: utf-8 -*-
"""
Formulário da Medida de Coordenação (`coordination_measure`, 132 códigos no catálogo).

Tudo o que depende do código sai do catálogo do EBGeo Web empacotado (motor/catalogos.json,
montado de coordination_points_catalog.js e familias-de-escalao.js), nunca de lista à mão:

  - os textos (Tipo, Identificação, GDH, Número, Nº Concentração, Altitude), a Situação do
    núcleo e as três minas aparecem só nos códigos cujo `campos` (uiFields do Web) os lista;
  - o Escalão aparece só nas famílias montadas por escalão (Núcleo e Escalão, com e sem
    Força-Tarefa), e a lista dele são os escalões do catálogo;
  - a rotação vira "Direção principal" e "Direção secundária" no Setor de Tiro (`setorDeTiro`)
    e leva o rótulo da direção do catálogo onde ela existe (Base de fogos, "Direção dos fogos");
  - a cor padrão do tipo (`corPadrao`, as destruições nascem verdes) e o escalão da família ao
    trocar a medida são regras puras deste módulo, que o guardião aplica (regras.py).

A feição guarda em `point_code` o código de TELA da família (ECHELON, ECHELON_FT, ESCALAO,
ESCALAO_FT) e em `echelon_code` a chave desenhável (ECHELON_16); quem pergunta ao catálogo
resolve antes por `codigo_desenhavel`, a mesma regra do Web. As condições do formulário olham
só `point_code`: dentro de cada metade de família os 13 escalões têm os mesmos campos, cor e
direção (conferido ao montar; o dia em que o catálogo os diferenciar, `_homogeneo` acusa).
Código nulo ou desconhecido não desenha (o gerador recusa) e não mostra campo condicional.

Este módulo não importa QGIS, nem a especificação na carga: as peças de especificacao.py são
lidas ao montar o formulário, para o registro lá não fazer ciclo.
"""
import json
import os
import unicodedata

TIPO = 'coordination_measure'

# Chave que o ValueMap do QGIS usa para o valor nulo (QgsValueMapFieldFormatter.NULL_VALUE; o
# teste confere contra o QGIS): a lista nativa oferece o desenho padrão sem gravar nada.
NULO_VALUEMAP = '{2839923C-8B7D-419E-B84B-CA2FE9B80EC7}'

# As propriedades do catálogo que o formulário e as regras leem de cada código.
_CHAVES_DO_FORMULARIO = ('campos', 'corPadrao', 'direcao', 'setorDeTiro')

_CACHE = {}


# ---------------------------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------------------------

def catalogo():
    """A seção `medida` do catalogos.json empacotado (o mesmo do seletor e do motor)."""
    if 'c' not in _CACHE:
        arq = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           'motor', 'catalogos.json')
        with open(arq, encoding='utf-8') as fh:
            _CACHE['c'] = json.load(fh)['medida']
    return _CACHE['c']


def _texto(v):
    if v is None or (hasattr(v, 'isNull') and v.isNull()):
        return ''
    return str(v)


def _familias():
    return list(catalogo()['familias'].values())


def telas():
    """[(código de tela, família, Força-Tarefa)] na ordem do catálogo: Núcleo, Núcleo FT, Escalão, Escalão FT."""
    saida = []
    for fam in _familias():
        saida += [(fam['tela'], fam, False), (fam['telaFT'], fam, True)]
    return saida


def _classificar(codigo):
    """(família, Força-Tarefa) do código de tela ou da chave; FT testado antes (classificar do Web)."""
    if not codigo:
        return None
    for fam in _familias():
        if codigo == fam['telaFT'] or codigo.startswith(fam['prefixoFT'] + '_'):
            return fam, True
    for fam in _familias():
        if codigo == fam['tela'] or codigo.startswith(fam['prefixo'] + '_'):
            return fam, False
    return None


def eh_codigo_de_tela(codigo):
    return any(codigo == t for t, _f, _ft in telas())


def familia_de_tela(codigo):
    """(família, Força-Tarefa) do código de TELA, ou None para quem não se monta por escalão."""
    codigo = _texto(codigo)
    return _classificar(codigo) if eh_codigo_de_tela(codigo) else None


def escalao_da_chave(chave):
    """O número do escalão da chave (`ESCALAO_FT_21` dá '21'), ou None (escalaoDaChave do Web)."""
    chave = _texto(chave)
    onde = _classificar(chave)
    if not onde:
        return None
    fam, ft = onde
    prefixo = fam['prefixoFT'] if ft else fam['prefixo']
    return (chave[len(prefixo) + 1:] if chave.startswith(prefixo + '_') else '') or None


def chave_do_escalao(fam, escalao, ft):
    return '{}_{}'.format(fam['prefixoFT'] if ft else fam['prefixo'], escalao or catalogo()['escalaoPadrao'])


def codigo_desenhavel(point_code, echelon_code=None):
    """
    A chave do catálogo com que o símbolo é desenhado (codigoDesenhavel do Web): o código de tela
    resolve pelo `echelon_code` da MESMA família e metade, e sem ele pelo escalão padrão; os
    demais passam como vieram.
    """
    pc = _texto(point_code)
    if not eh_codigo_de_tela(pc):
        return pc
    fam, ft = _classificar(pc)
    ec = _texto(echelon_code)
    escalao = escalao_da_chave(ec)
    onde = _classificar(ec)
    coerente = escalao is not None and onde is not None and onde[0]['tela'] == fam['tela'] and onde[1] == ft
    return chave_do_escalao(fam, escalao if coerente else None, ft)


def entrada(point_code, echelon_code=None):
    """A entrada do catálogo (porCodigo) do código desenhável, ou None (nulo, desconhecido)."""
    return catalogo()['porCodigo'].get(codigo_desenhavel(point_code, echelon_code))


def _homogeneo():
    """Confere que os 13 escalões de cada metade de família têm o que o formulário lê iguais."""
    por = catalogo()['porCodigo']
    for tela, fam, ft in telas():
        vistos = {json.dumps({k: por[chave_do_escalao(fam, nn, ft)].get(k) for k in _CHAVES_DO_FORMULARIO},
                             sort_keys=True) for nn in catalogo()['escaloes']}
        if len(vistos) != 1:
            raise ValueError('Os escalões de {} divergem no catálogo; a condição do formulário precisa do '
                             'echelon_code.'.format(tela))


def dominio():
    """Os valores de `point_code` que o catálogo conhece: as 132 chaves e os quatro códigos de tela."""
    return list(catalogo()['porCodigo']) + [t for t, _f, _ft in telas()]


# ---------------------------------------------------------------------------------------------
# Campos por código (nomes do Web e colunas)
# ---------------------------------------------------------------------------------------------

def coluna_de(web):
    from ... import schema
    return {w: c for w, c in schema.mapa_web(TIPO).items()}[web]


def web_de(coluna):
    from ... import schema
    return {c: w for w, c in schema.mapa_web(TIPO).items()}[coluna]


def definicao(coluna):
    """A definição do campo no catálogo (textFieldDefinitions do Web) pela coluna do GeoPackage."""
    return catalogo()['definicoesCampos'].get(web_de(coluna)) or {}


def opcoes_lista(coluna):
    """[(valor, rótulo)] do campo de lista do catálogo (Situação, minas, classe de suprimento)."""
    d = definicao(coluna)
    rotulos = d.get('optionLabels') or (catalogo()['classesSuprimento'] if coluna == 'classe_suprimento' else {})
    return [(v, rotulos.get(v, v)) for v in d.get('options') or []]


def padrao_lista(coluna):
    """O valor que o desenho usa com a coluna nula: o padrão do catálogo, ou a primeira opção
    (a Situação nula desenha como "ocupado", aplicarSituacaoDoNucleo do Web)."""
    d = definicao(coluna)
    return d.get('defaultValue') or (d.get('options') or [None])[0]


def _normalizar(texto):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(ch)).lower()


def texto_de_busca(codigo, rotulo):
    """O que a busca do seletor compara: o rótulo com e sem acento e o código."""
    return '{} {} {}'.format(rotulo, _normalizar(rotulo), codigo)


def rotulo_ponto(codigo):
    """'Categoria: nome' da medida; o código de tela leva o nome da família."""
    codigo = _texto(codigo)
    for tela, fam, ft in telas():
        if codigo == tela:
            rep = catalogo()['porCodigo'][chave_do_escalao(fam, None, ft)]
            return '{}: {}'.format(rep['categoria'], fam['rotulo'])
    for item in catalogo()['lista']:
        if item['code'] == codigo:
            return '{}: {}'.format(item['category'], item['label'])
    e = catalogo()['porCodigo'].get(codigo)
    if e:
        return '{}: {} (fora do seletor do EBGeo Web)'.format(e['categoria'], e['nome'])
    return codigo


def opcoes_ponto(fora_do_seletor=True):
    """
    [(código, rótulo)] do seletor de medida: as quatro famílias de escalão e a lista do Web, na
    ordem dele. Com `fora_do_seletor`, também os códigos que o Web tirou do seletor mas ainda
    desenha (a Área minada pontual, 270800), para a feição antiga mostrar o nome.
    """
    ops = [(t, rotulo_ponto(t)) for t, _f, _ft in telas()]
    ops += [(i['code'], rotulo_ponto(i['code'])) for i in catalogo()['lista']]
    if fora_do_seletor:
        vistos = {c for c, _r in ops}
        ops += [(c, rotulo_ponto(c)) for c in catalogo()['porCodigo']
                if c not in vistos and _classificar(c) is None]
    return ops


def opcoes_escalao():
    """[(chave, nome)] das 52 chaves de família, para a lista nativa (o dock filtra pela família)."""
    por = catalogo()['porCodigo']
    return [(chave_do_escalao(fam, nn, ft), por[chave_do_escalao(fam, nn, ft)]['nome'])
            for _t, fam, ft in telas() for nn in sorted(catalogo()['escaloes'])]


def escaloes():
    """[(número, nome)] dos escalões do catálogo, em ordem."""
    return sorted(catalogo()['escaloes'].items())


# ---------------------------------------------------------------------------------------------
# Regras de troca (puras; o guardião as aplica em qualquer caminho de edição)
# ---------------------------------------------------------------------------------------------

def escolhas_de_desenho():
    """As colunas de desenho que valem só para o tipo que as tem (minas do 270701, ângulo do 140500)."""
    from ... import schema
    return tuple(c for c, _tp, _w in schema.DESENHO_MEDIDA)


def escalao_ao_trocar(echelon_anterior, point_code_novo):
    """
    O `echelon_code` da medida que troca para `point_code_novo` (_handlePointTypeChange do Web):
    na família, mantém o número do escalão anterior (ou o padrão) com o prefixo da família e da
    metade novas; fora de família, nulo.
    """
    onde = familia_de_tela(point_code_novo)
    if onde is None:
        return None
    fam, ft = onde
    return chave_do_escalao(fam, escalao_da_chave(echelon_anterior), ft)


def cor_ao_trocar(codigo_anterior, codigo_novo, atual):
    """
    A cor da medida que troca de tipo (_aplicarCorPadraoDoTipo do Web), pelas chaves desenháveis:
    o tipo com cor própria (as destruições, MD33-C-01 7.4.1) a impõe, salvo se o operador já
    escolheu outra; sair dele devolve a cor padrão (nula). False quando a cor fica como está.
    """
    def igual(a, b):
        return (a or '').lower() == (b or '').lower()
    por = catalogo()['porCodigo']
    padrao_anterior = (por.get(_texto(codigo_anterior)) or {}).get('corPadrao')
    padrao_novo = (por.get(_texto(codigo_novo)) or {}).get('corPadrao')
    atual = _texto(atual) or None
    if atual is not None and not igual(atual, padrao_anterior):
        return False
    if igual(atual, padrao_novo):
        return False
    return padrao_novo


# ---------------------------------------------------------------------------------------------
# Especificação
# ---------------------------------------------------------------------------------------------

def _lista_com_padrao(coluna):
    """ValueMap do campo de lista, com a entrada nula que mostra o desenho padrão sem gravá-lo."""
    from .. import especificacao as esp
    opcoes = opcoes_lista(coluna)
    rotulos = dict(opcoes)
    padrao = padrao_lista(coluna)
    nulo = [(NULO_VALUEMAP, '{} (padrão)'.format(rotulos.get(padrao, padrao)))] if padrao else []
    return esp.lista(nulo + opcoes)


_CLASSES = {}


def campo_com_rotulos():
    """Campo cujo rótulo segue o código por uma CADEIA de condições (o primeiro que vale)."""
    if 'c' not in _CLASSES:
        from dataclasses import dataclass
        from .. import especificacao as esp

        @dataclass
        class CampoRotulos(esp.Campo):
            rotulos: tuple = ()   # ((condição, rótulo), ...): o primeiro que vale; senão, `rotulo`

            def rotulo_para(self, atributos, rico=False):
                for cond, rot in self.rotulos:
                    if cond.avaliar(atributos):
                        return rot
                return esp.Campo.rotulo_para(self, atributos, rico)

            def expressao_rotulo(self):
                if not self.rotulos:
                    return esp.Campo.expressao_rotulo(self)
                texto = esp._literal(self.rotulo)
                for cond, rot in reversed(self.rotulos):
                    texto = 'if({}, {}, {})'.format(cond.expressao(), esp._literal(rot), texto)
                return texto
        _CLASSES['c'] = CampoRotulos
    return _CLASSES['c']


def condicao(predicado):
    """A condição "a medida tem a propriedade `predicado`", gerada do catálogo sobre `point_code`."""
    from .. import especificacao as esp
    _homogeneo()
    return esp.Condicao('point_code', frozenset(c for c in dominio() if predicado(entrada(c) or {})))


def usa(coluna):
    web = web_de(coluna)
    return condicao(lambda e: web in (e.get('campos') or []))


def colunas_de_lista():
    """As colunas de texto do Web que o catálogo define como lista (Situação, classe de suprimento)."""
    from ... import schema
    return [c for c, w in schema.TEXTOS_MEDIDA if catalogo()['definicoesCampos'].get(w, {}).get('type') == 'select']


def colunas_de_texto():
    from ... import schema
    return [c for c, w in schema.TEXTOS_MEDIDA if catalogo()['definicoesCampos'].get(w, {}).get('type') != 'select']


def colunas_usadas():
    """As colunas que algum código do catálogo usa."""
    return {coluna_de(w) for e in catalogo()['porCodigo'].values() for w in e.get('campos') or []}


def ocultos():
    from ... import schema
    from .. import especificacao as esp
    tecnicas = tuple(n for n, _tp, _p, web in schema.TIPOS[TIPO]['campos'] if web is None)
    # sem código que o use, o campo do Web fica fora do formulário (hoje, a classe de suprimento,
    # que o código SUPPLY_* já carrega)
    sem_uso = tuple(c for c in colunas_de_lista() + colunas_de_texto() if c not in colunas_usadas())
    return esp.OCULTOS_COMUNS + ('anchor',) + tecnicas + sem_uso


def formulario():
    from .. import especificacao as esp
    CampoRotulos = campo_com_rotulos()
    usadas = colunas_usadas()

    familia = esp.Condicao('point_code', frozenset(t for t, _f, _ft in telas()))
    setor = condicao(lambda e: bool(e.get('setorDeTiro')))
    direcoes = sorted({e['direcao']['rotulo'] for e in catalogo()['porCodigo'].values() if e.get('direcao')})
    rotulos_rotacao = ((setor, 'Direção principal'),) + tuple(
        (condicao(lambda e, r=r: (e.get('direcao') or {}).get('rotulo') == r), r) for r in direcoes)

    listas = [esp.Campo(c, definicao(c).get('label') or c, _lista_com_padrao(c), condicao=usa(c), rico='medida_lista',
                  dica=definicao(c).get('help'))
              for c in colunas_de_lista() if c in usadas]
    minas = [c for c in escolhas_de_desenho() if c in usadas]
    simbolo = esp.Aba('Símbolo', [
        esp.previa_simbolo(),
        esp.Campo('point_code', 'Medida', esp.lista(opcoes_ponto()), rico='medida_ponto'),
        esp.Campo('echelon_code', 'Escalão', esp.lista([(NULO_VALUEMAP, '{} (padrão)'.format(
            catalogo()['escaloes'][catalogo()['escalaoPadrao']]))] + opcoes_escalao()),
            condicao=familia, rico='medida_escalao'),
    ] + listas + ([esp.Grupo('Minas', [
        esp.Campo(c, definicao(c).get('label') or c, _lista_com_padrao(c), condicao=usa(c), rico='medida_lista',
                  dica=definicao(c).get('help'))
        for c in minas], condicao=condicao(lambda e: any(coluna_de(w) in minas for w in e.get('campos') or [])))]
        if minas else []) + [esp.descricao()])

    textos = [c for c in colunas_de_texto() if c in usadas]
    aba_textos = esp.Aba('Textos', [
        esp.Campo(c, definicao(c).get('label') or c, esp.texto(), condicao=usa(c), rico='medida_texto',
                  dica=definicao(c).get('help')) for c in textos
    ], condicao=condicao(lambda e: any(coluna_de(w) in textos for w in e.get('campos') or [])))

    aparencia = esp.Aba('Aparência', [
        esp.Campo('size', 'Tamanho', esp.numero(0.1, 5, 0.1, 2)),
        CampoRotulos('rotation', 'Rotação', esp.numero(-360, 360, 1, 1, '°'), rico='medida_rotacao',
                     rotulos=rotulos_rotacao),
        esp.Campo('angulo_secundario', 'Direção secundária (relativa à principal)', esp.numero(-180, 180, 1, 1, '°'),
                  condicao=setor, rico='medida_dir_secundaria', rotulo_rico='Direção secundária'),
        esp.Campo('opacity', 'Opacidade', esp.numero(0, 1, 0.05, 2)),
        esp.Campo('fill_color', 'Cor de preenchimento', esp.cor()),
        esp.grupo_zoom(),
    ])
    return esp.Formulario(TIPO, esp.cabecalho(), [simbolo, aba_textos, aparencia, esp.aba_atributos(),
                                                  esp.aba_avancado()], ocultos())
