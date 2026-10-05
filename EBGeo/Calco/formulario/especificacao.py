# -*- coding: utf-8 -*-
"""
Especificação única do formulário de feição do calco.

Uma especificação por tipo diz o que o operador vê: o cabeçalho, as abas, os grupos e os
campos, com o rótulo em português, o widget NATIVO do QGIS (tipo do editor e configuração), a
condição em que o campo aparece e, quando há, o widget RICO que só o dock do plugin monta. Três
consumidores leem a mesma especificação, e por isso nunca discordam:

  - formulario/nativo.py assa o formulário no estilo da camada (layer_styles do GeoPackage), que
    abre num QGIS sem o plugin: só widgets nativos, sem ação Python, sem função de inicialização;
  - ui/painel.py monta o dock de propriedades, com os widgets ricos e Salvar/Descartar;
  - os testes conferem a condição contra o dock de antes e contra o formulário montado sem o
    plugin (testes/test_formulario_sem_plugin.py).

Contrato (o que cada consumidor pode supor):

  Formulario(tipo, cabecalho, abas, ocultos)
    cabecalho  campos e grupos acima das abas (nome, mostrar no mapa, aviso de bloqueio; a
               descrição multilinha vai no fim da primeira aba)
    abas       Aba(nome, filhos, condicao, prefixo): filhos são Campo, Grupo ou Texto; com
               `prefixo`, a aba é preenchida com as colunas da camada que começam por ele (as
               attr_* do importador, só o valor, com o alias que a camada já tem) e some sem elas
    ocultos    colunas técnicas: widget Hidden, fora do formulário, do Identificar e da tabela
  Grupo(nome, filhos, condicao, recolhido, titulo): sem título, o grupo só carrega a condição
  Campo(coluna, rotulo, widget, condicao, rotulo_se, rico, rotulo_rico, rico_config,
        somente_leitura, rotulo_em_cima, restricao)
  Texto(nome, texto): aviso fixo, sem campo; pode ter expressões [% %], que o nativo avalia e o
        dock também (current_value() lê o valor do formulário em edição)
  Condicao(coluna, valores, negar): vale quando o código da coluna está em `valores` (ou fora,
        com `negar`); nulo, vazio e código desconhecido valem como o código padrão do catálogo,
        que é como o estilo desenha. `expressao()` dá a expressão QGIS que o formulário nativo e
        o dock avaliam; `avaliar(atributos)` é a mesma regra em Python, para os testes.
  Ligado(coluna, padrao): a caixa marcada (nula vale o padrão do estilo); Todas(condicoes): a
        conjunção, no mesmo contrato.
  Bloqueada(): a feição travada no EBGeo Web (`bloqueado`). Todo campo editável ganha a
        propriedade "editável" por dados EXPRESSAO_EDITAVEL.

A assinatura do consumidor nativo é `nativo.aplicar_formulario(layer, tipo) -> bool`.

Este módulo não importa QGIS; o catálogo de cada tipo só é lido ao montar a especificação dele.
"""
from dataclasses import dataclass, field

# Os editores nativos do QGIS 4.0.0 que o formulário assado pode usar. Widget registrado por
# plugin derruba o QGIS que abre o arquivo sem o plugin (medido; ARQUITETURA.md, seção 11), por
# isso a lista é fechada e a régua sem plugin reprova qualquer outro.
WIDGETS_NATIVOS = frozenset({'TextEdit', 'Color', 'Range', 'CheckBox', 'ValueMap', 'DateTime', 'Hidden'})

EXPRESSAO_BLOQUEADA = 'coalesce("bloqueado", false)'
EXPRESSAO_EDITAVEL = 'NOT ' + EXPRESSAO_BLOQUEADA
# Atualizado a cada mudança da feição, por qualquer caminho de edição e sem o plugin: valor
# padrão do QGIS aplicado na atualização (grava ISO em UTC no GeoPackage, medido).
COLUNA_ATUALIZADO = 'atualizado_em'
EXPRESSAO_ATUALIZADO = 'now()'
PREFIXO_ATRIBUTOS = 'attr_'


# ---------------------------------------------------------------------------------------------
# Widgets nativos
# ---------------------------------------------------------------------------------------------

@dataclass
class Widget:
    tipo: str
    config: dict = field(default_factory=dict)
    faixa: tuple = None   # número: (mínimo, máximo, passo, casas, sufixo) da caixa giratória do dock


def texto(multilinha=False):
    return Widget('TextEdit', {'IsMultiline': multilinha, 'UseHtml': False})


def cor():
    return Widget('Color', {})


def numero(minimo, maximo, passo, casas, sufixo=''):
    """
    Número. No formulário nativo é a caixa de texto numérica (TextEdit em coluna real: o QGIS põe
    o validador de número, o nulo fica nulo e o valor volta EXATO, '0,30000000000000004' ou
    '12,345678901234567'). O Range não serve: a caixa giratória corta à faixa e arredonda às
    casas, e o formulário regrava o valor cortado ao salvar QUALQUER outra mudança (medido no QGIS
    4.0.0: created_zoom 23,4 vira 22, line_width 2,5 vira 3, 0,30000000000000004 vira 0,3; sem
    AllowNull, o nulo vira o mínimo). O Web grava doubles crus (o zoom da criação sem arredondar na
    medida, na declinação, no texto, na imagem e no pincel; 0,30000000000000004 na opacidade de um
    polígono da fixture 06), então nenhuma faixa com casas fixas é segura. A faixa, o passo, as
    casas e o sufixo ficam para a caixa giratória do dock, que só grava o que o operador muda.
    """
    return Widget('TextEdit', {'IsMultiline': False, 'UseHtml': False}, faixa=(minimo, maximo, passo, casas, sufixo))


def caixa():
    """
    Caixa de marcar com o estado nulo (AllowNullState): sem ele, o formulário nativo grava False na
    coluna nula ao salvar QUALQUER outra mudança (medido no QGIS 4.0.0), e o nulo quer dizer o
    padrão do desenho (`visivel` nulo é mostrar, `zoom_corr` nulo é corrigir).
    """
    return Widget('CheckBox', {'CheckedState': '', 'UncheckedState': '', 'TextDisplayMethod': 0, 'AllowNullState': True})


def lista(opcoes):
    """ValueMap: [(valor gravado, rótulo)] na ordem de exibição."""
    return Widget('ValueMap', {'map': [{rotulo: valor} for valor, rotulo in opcoes]})


def data_hora():
    return Widget('DateTime', {'display_format': 'dd/MM/yyyy HH:mm:ss', 'calendar_popup': False,
                               'allow_null': True})


def oculto():
    return Widget('Hidden', {})


# ---------------------------------------------------------------------------------------------
# Condições
# ---------------------------------------------------------------------------------------------

def _literal(valor):
    return "'{}'".format(str(valor).replace("'", "''"))


def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


@dataclass(frozen=True)
class Condicao:
    coluna: str
    valores: frozenset
    negar: bool = False

    def expressao(self):
        if not self.valores:
            return 'TRUE' if self.negar else 'FALSE'
        dentro = 'coalesce("{}", \'\') IN ({})'.format(
            self.coluna, ', '.join(_literal(v) for v in sorted(self.valores)))
        return 'NOT ({})'.format(dentro) if self.negar else dentro

    def avaliar(self, atributos):
        v = atributos.get(self.coluna)
        v = '' if _nulo(v) else str(v)
        return (v in self.valores) != self.negar


@dataclass(frozen=True)
class Ligado:
    """
    A caixa da coluna booleana está marcada; nula vale `padrao`, o valor que o estilo assume (a
    Seta o lê do próprio .exp, tipos/taticos.padrao_no_estilo). Mesmo contrato de Condicao.
    """
    coluna: str
    padrao: bool = False

    def expressao(self):
        return 'coalesce("{}", {})'.format(self.coluna, 'true' if self.padrao else 'false')

    def avaliar(self, atributos):
        v = atributos.get(self.coluna)
        return self.padrao if _nulo(v) else bool(v)


@dataclass(frozen=True)
class Todas:
    """
    Vale quando todas as condições valem (a hachura do Polígono desenha com a caixa marcada E um
    tipo desenhado). O contêiner Row do nativo só leva uma expressão, então a conjunção vai nela.
    """
    condicoes: tuple

    def expressao(self):
        return ' AND '.join('({})'.format(c.expressao()) for c in self.condicoes)

    def avaliar(self, atributos):
        return all(c.avaliar(atributos) for c in self.condicoes)


@dataclass(frozen=True)
class Bloqueada:
    def expressao(self):
        return EXPRESSAO_BLOQUEADA

    def avaliar(self, atributos):
        v = atributos.get('bloqueado')
        return False if _nulo(v) else bool(v)


def por_codigo(coluna, catalogo, padrao, predicado):
    """
    A condição "o símbolo da coluna tem a propriedade `predicado`", gerada do catálogo. O código
    fora do catálogo vale como `padrao`: quando o padrão tem a propriedade, a condição é escrita
    pela negativa (fora dos que não têm), para o desconhecido cair do mesmo lado.
    """
    tem = frozenset(c for c, d in catalogo.items() if predicado(d))
    if predicado(catalogo[padrao]):
        return Condicao(coluna, frozenset(catalogo) - tem, negar=True)
    return Condicao(coluna, tem)


# ---------------------------------------------------------------------------------------------
# Elementos
# ---------------------------------------------------------------------------------------------

@dataclass
class Campo:
    coluna: str
    rotulo: str
    widget: Widget
    condicao: object = None
    rotulo_se: tuple = None       # (condição, rótulo) quando a condição vale (rótulo por dados)
    rico: str = None              # widget que só o dock monta (simbolo_linha, km_em_m)
    rotulo_rico: str = None       # rótulo do dock quando o widget rico mostra outra unidade
    rico_config: tuple = ()
    somente_leitura: bool = False
    rotulo_em_cima: bool = False
    restricao: tuple = None       # (expressão, descrição): restrição forte do nativo (valor que quebra o desenho)
    # opções da lista que dependem do arquivo (os ícones próprios do Ponto): função(camada) ->
    # [(valor, rótulo, (mime, base64) ou None)], somadas às da especificação no nativo e no dock
    opcoes_da_camada: object = None
    # dica do campo, como a do Web: no nativo vai como comentário da coluna no GeoPackage (o QGIS a
    # mostra no rótulo, sem código; gpkg.garantir_tabela_tipo); `dica_por(atributos)`, a que muda
    # com a feição (o conjunto do SIDC), só no dock
    dica: str = None
    dica_por: object = None

    def rotulo_para(self, atributos, rico=False):
        if self.rotulo_se is not None and self.rotulo_se[0].avaliar(atributos):
            return self.rotulo_se[1]
        return (self.rotulo_rico or self.rotulo) if rico else self.rotulo

    def dica_para(self, atributos):
        return (self.dica_por(atributos) if self.dica_por is not None else None) or self.dica

    def expressao_rotulo(self):
        """Expressão do rótulo por dados, ou None quando o rótulo é fixo."""
        if self.rotulo_se is None:
            return None
        return 'if({}, {}, {})'.format(self.rotulo_se[0].expressao(), _literal(self.rotulo_se[1]),
                                       _literal(self.rotulo))


@dataclass
class Texto:
    nome: str
    texto: str


@dataclass
class Grupo:
    nome: str
    filhos: list
    condicao: object = None
    recolhido: bool = False
    titulo: bool = True


@dataclass
class Aba:
    nome: str
    filhos: list
    condicao: object = None
    prefixo: str = None


@dataclass
class Formulario:
    tipo: str
    cabecalho: list
    abas: list
    ocultos: tuple

    def percorrer(self):
        """(elemento, condições dos ancestrais e dele) de todo Campo e Texto, na ordem de exibição."""
        def andar(filhos, conds):
            for el in filhos:
                proprias = conds + ([el.condicao] if getattr(el, 'condicao', None) is not None else [])
                if isinstance(el, (Grupo, Aba)):
                    yield from andar(el.filhos, proprias)
                else:
                    yield el, proprias
        yield from andar(self.cabecalho, [])
        for aba in self.abas:
            yield from andar(aba.filhos, [aba.condicao] if aba.condicao is not None else [])

    def campos(self):
        return [el for el, _c in self.percorrer() if isinstance(el, Campo)]

    def campo(self, coluna):
        for c in self.campos():
            if c.coluna == coluna:
                return c
        return None

    def visivel(self, coluna, atributos):
        """O campo aparece para a feição com estes atributos (todas as condições do caminho valem)."""
        for el, conds in self.percorrer():
            if isinstance(el, Campo) and el.coluna == coluna:
                return all(c.avaliar(atributos) for c in conds)
        return False


# ---------------------------------------------------------------------------------------------
# Partes comuns a todos os tipos
# ---------------------------------------------------------------------------------------------

AVISO_BLOQUEADA = 'Feição bloqueada no EBGeo Web: os campos ficam só para leitura.'
OCULTOS_COMUNS = ('fid', 'grupos', 'atributos', 'props')


def cabecalho():
    """
    Cabeçalho compacto acima das abas. A Descrição multilinha não fica aqui: no formulário nativo
    ela toma toda a altura que sobra (o QPlainTextEdit expande, e o esticamento vertical do
    elemento, que persiste no estilo, não a encolhe; medido no QGIS 4.0.0), empurrando as abas
    para baixo. Ela vai no fim da primeira aba (descricao()).
    """
    return [
        Campo('nome', 'Nome', texto()),
        Campo('visivel', 'Mostrar no mapa', caixa()),
        Grupo('Bloqueada', [Texto('aviso_bloqueada', AVISO_BLOQUEADA)], condicao=Bloqueada(), titulo=False),
    ]


def descricao():
    """A Descrição, no fim da primeira aba, com o rótulo em cima para o texto ter a largura toda."""
    return Campo('descricao', 'Descrição', texto(multilinha=True), rotulo_em_cima=True)


def aba_atributos():
    return Aba('Atributos', [], prefixo=PREFIXO_ATRIBUTOS)


def aba_avancado():
    return Aba('Avançado', [
        Campo('ebgeo_id', 'Identificador no EBGeo', texto(), somente_leitura=True),
        Campo('mapa', 'Mapa', texto(), somente_leitura=True),
        Campo('camada_id', 'Camada do EBGeo', texto(), somente_leitura=True),
        Campo('criado_em', 'Criado em', data_hora(), somente_leitura=True),
        Campo('atualizado_em', 'Atualizado em', data_hora(), somente_leitura=True),
        Campo('bloqueado', 'Bloqueado no EBGeo Web', caixa(), somente_leitura=True),
    ])


def grupo_zoom(prefixo='', titulo='Correção de Zoom', condicao=None):
    """O grupo recolhido da correção de zoom; com prefixo e condição, o do rótulo dos comuns."""
    return Grupo(titulo, [
        Campo(prefixo + 'zoom_corr', 'Correção de Zoom', caixa()),
        Campo(prefixo + 'created_zoom', 'Zoom de Referência', numero(0, 22, 0.1, 1)),
    ], condicao=condicao, recolhido=True)


# ---------------------------------------------------------------------------------------------
# Linha de Coordenação
# ---------------------------------------------------------------------------------------------

AVISO_LADO_INIMIGO = ('O lado inimigo fica à esquerda do sentido do traçado. Para trocar os lados, '
                      'inverta a linha: "Inverter sentido" no painel do calco ou a ferramenta '
                      '"Inverter linha" do QGIS.')
# Rótulos dos textos como o Web os mostra (textFieldDefinitions de coordination_line_catalog.js).
ROTULOS_TEXTO_LINHA = (('tipo', 'Tipo'), ('identificacao', 'Identificação'), ('gdh_ini', 'GDH Início'),
                       ('gdh_fim', 'GDH Fim'), ('numero_concentracao', 'Nº Concentração'))


def _linha_coordenacao():
    from ..estilos_taticos import CATALOGO_LINHA, GRUPOS_LINHA, SIMBOLO_PADRAO, designacao_linha

    def cond(predicado):
        return por_codigo('symbol_code', CATALOGO_LINHA, SIMBOLO_PADRAO, predicado)

    def texto_do_simbolo(col):
        return cond(lambda s: col in (s.get('textos') or []))

    segunda_cor = cond(lambda s: s.get('segunda_cor') == 'enemy_color')
    opcoes = [(c, '{}: {} ({})'.format(g, s['nome'], designacao_linha(c)))
              for g in GRUPOS_LINHA for c, s in CATALOGO_LINHA.items() if s['grupo'] == g]
    simbolo = Aba('Símbolo', [
        Campo('symbol_code', 'Símbolo', lista(opcoes), rico='simbolo_linha'),
        Campo('symbol_size_km', 'Tamanho do símbolo', numero(0.01, 50, 0.01, 3, ' km'),
              condicao=cond(lambda s: s['glifo'] != 'none'),
              rico='km_em_m', rico_config=(10, 50000, 5)),
        Campo('symbol_spacing_km', 'Distância entre símbolos', numero(0.01, 500, 0.01, 3, ' km'),
              condicao=cond(lambda s: not (s.get('fixo') or s.get('continuo'))),
              rico='km_em_m', rico_config=(10, 500000, 5)),
        Grupo('Lado inimigo', [Texto('aviso_lado_inimigo', AVISO_LADO_INIMIGO)], condicao=segunda_cor,
              titulo=False),
        descricao(),
    ])
    textos = Aba('Textos', [Campo(col, rot, texto(), condicao=texto_do_simbolo(col)) for col, rot in ROTULOS_TEXTO_LINHA] + [
        Campo('text_size', 'Tamanho do texto', numero(8, 80, 1, 0, ' px')),
        Campo('text_north_facing', 'Texto sempre para o norte', caixa()),
    ], condicao=cond(lambda s: bool(s.get('textos'))))
    aparencia = Aba('Aparência', [
        Campo('color', 'Cor', cor(), rotulo_se=(segunda_cor, 'Cor do lado amigo')),
        Campo('enemy_color', 'Cor do lado inimigo', cor(), condicao=segunda_cor),
        Campo('line_width', 'Espessura', numero(1, 10, 1, 0, ' px')),
        Campo('opacity', 'Opacidade', numero(0, 1, 0.05, 2)),
        grupo_zoom(),
    ])
    return Formulario('coordination_line', cabecalho(), [simbolo, textos, aparencia, aba_atributos(), aba_avancado()],
                      OCULTOS_COMUNS + ('geom_desenho',))


# Os tipos com formulário próprio; os demais seguem com o formulário autogerado do QGIS e com o
# dock de antes até a escala do piloto.
_CONSTRUTORES = {'coordination_line': _linha_coordenacao}
from .tipos import militar as _militar; _CONSTRUTORES.update(_militar.CONSTRUTORES)  # noqa: E402,E702 (Militar, Engenharia, Declinação)
from .tipos import medida as _medida; _CONSTRUTORES[_medida.TIPO] = _medida.formulario  # noqa: E402,E702 (Medida de Coordenação)
from .tipos import area as _area; _CONSTRUTORES['coordination_area'] = _area.formulario  # noqa: E402,E702 (Área de Coordenação)
from .tipos import taticos as _taticos; _CONSTRUTORES.update(_taticos.CONSTRUTORES)  # noqa: E402,E702 (Limite, Seta, Frente Ocupada)
from .tipos import comuns as _comuns; _CONSTRUTORES.update(_comuns.CONSTRUTORES)  # noqa: E402,E702 (os 14 comuns do mapa 2D)
TIPOS_COM_FORMULARIO = frozenset(_CONSTRUTORES)


def formulario(tipo):
    """A especificação do tipo, ou None para o tipo ainda sem formulário próprio."""
    construtor = _CONSTRUTORES.get(tipo)
    return construtor() if construtor else None


# A prévia do símbolo pontual no formulário nativo, como no painel do Web: o SVG gravado na feição
# (ou o PNG do .ebgeo, no símbolo que o Web só mandou como imagem) num elemento de texto, que o QGIS
# desenha sem o plugin (imagem data:) e renova a cada mudança de campo (current_value). O dock põe
# no lugar o desenho do mesmo SVG (ui/blocos/previa.py).
NOME_PREVIA = 'previa_simbolo'
ALTURA_PREVIA = 96
EXPRESSAO_PREVIA = (
    "[% CASE WHEN coalesce(current_value('svg'), '') <> '' "
    "THEN '<img src=\"data:image/svg+xml;base64,' || current_value('svg') || '\" height=\"{a}\"/>' "
    "WHEN coalesce(current_value('bitmap_b64'), '') <> '' "
    "THEN '<img src=\"data:' || coalesce(current_value('bitmap_mime'), 'image/png') || ';base64,' "
    "|| current_value('bitmap_b64') || '\" height=\"{a}\"/>' ELSE '' END %]").format(a=ALTURA_PREVIA)


def previa_simbolo():
    return Texto(NOME_PREVIA, EXPRESSAO_PREVIA)


def dicas(tipo):
    """{coluna: dica} dos campos do tipo que têm dica (o comentário da coluna no GeoPackage)."""
    spec = formulario(tipo)
    return {c.coluna: c.dica for c in spec.campos() if c.dica} if spec is not None else {}
