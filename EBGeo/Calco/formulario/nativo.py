# -*- coding: utf-8 -*-
"""
Formulário nativo da feição, assado no estilo da camada a partir da especificação.

Vai para o layer_styles do GeoPackage junto com a simbologia (categorias Fields, Forms e
AttributeTable do estilo) e abre num QGIS sem o plugin: layout arrastar-e-soltar com abas,
aliases em português, widgets nativos, campos técnicos ocultos (também na tabela de atributos),
grupos que aparecem conforme o símbolo por expressão de visibilidade, rótulo e "editável" por
dados (a feição bloqueada no EBGeo Web fica só para leitura) e `atualizado_em` renovado pelo
valor padrão na atualização. Nada de código: sem ação Python, sem função de inicialização, sem
arquivo .ui e sem widget registrado por plugin (este derruba o QGIS que abre o arquivo sem o
plugin; ARQUITETURA.md, seção 11).
"""
from qgis.core import (
    Qgis, QgsAttributeEditorContainer, QgsAttributeEditorField, QgsAttributeEditorSpacerElement,
    QgsAttributeEditorTextElement,
    QgsAttributeTableConfig, QgsDefaultValue, QgsEditFormConfig, QgsEditorWidgetSetup, QgsExpression,
    QgsOptionalExpression, QgsProperty, QgsPropertyCollection,
)

from . import especificacao as esp


def aplicar_formulario(layer, tipo):
    """Monta na camada o formulário do tipo. Devolve False para o tipo ainda sem especificação."""
    spec = esp.formulario(tipo)
    if spec is None:
        return False
    campos = layer.fields()
    nomes = set(campos.names())

    # Widgets e aliases ficam na camada; somente leitura, rótulo em cima e propriedades por dados
    # ficam na configuração do formulário, montada depois.
    especificados = [c for c in spec.campos() if c.coluna in nomes]
    for c in especificados:
        i = campos.indexOf(c.coluna)
        config = dict(c.widget.config)
        if c.opcoes_da_camada is not None and 'map' in config:
            # opções do arquivo (os ícones próprios do Ponto), legíveis também sem o plugin
            config['map'] = list(config['map']) + [{rotulo: valor} for valor, rotulo, _img in c.opcoes_da_camada(layer)]
        layer.setEditorWidgetSetup(i, QgsEditorWidgetSetup(c.widget.tipo, config))
        layer.setFieldAlias(i, c.rotulo)
        _restricao(layer, i, c.restricao)
    proprios = colunas_proprias(layer, spec)
    for col in proprios:
        layer.setEditorWidgetSetup(campos.indexOf(col), QgsEditorWidgetSetup('TextEdit', {'IsMultiline': False, 'UseHtml': False}))
    for col in spec.ocultos:
        if col in nomes:
            layer.setEditorWidgetSetup(campos.indexOf(col), QgsEditorWidgetSetup('Hidden', {}))
    if esp.COLUNA_ATUALIZADO in nomes:
        layer.setDefaultValueDefinition(campos.indexOf(esp.COLUNA_ATUALIZADO),
                                        QgsDefaultValue(esp.EXPRESSAO_ATUALIZADO, True))

    fc = layer.editFormConfig()
    fc.setUiForm('')  # antes do layout: caminho vazio volta o layout para o autogerado
    fc.setLayout(Qgis.AttributeFormLayout.DragAndDrop)
    fc.setInitCodeSource(Qgis.AttributeFormPythonInitCodeSource.NoSource)
    fc.setInitFunction('')
    fc.setInitCode('')
    fc.setInitFilePath('')
    for c in especificados:
        i = campos.indexOf(c.coluna)
        fc.setReadOnly(i, c.somente_leitura)
        fc.setLabelOnTop(i, c.rotulo_em_cima)
        fc.setDataDefinedFieldProperties(c.coluna, _propriedades(c.somente_leitura, c.expressao_rotulo()))
    for col in proprios:
        fc.setReadOnly(campos.indexOf(col), False)
        fc.setDataDefinedFieldProperties(col, _propriedades(False, None))

    raiz = fc.invisibleRootContainer()
    raiz.clear()
    _preencher(raiz, spec.cabecalho, campos)
    for aba in spec.abas:
        filhos = [esp.Campo(col, layer.attributeAlias(campos.indexOf(col)) or col, esp.texto()) for col in proprios] \
            if aba.prefixo else aba.filhos
        if not filhos:
            continue
        cont = QgsAttributeEditorContainer(aba.nome, raiz)
        cont.setType(Qgis.AttributeEditorContainerType.Tab)
        _condicao(cont, aba.condicao)
        _preencher(cont, filhos, campos)
        if not _termina_em_texto_longo(filhos):
            # sem ele, as linhas Row se espalham pela altura da aba (medido): o espaçador fica com a sobra
            esp_ = QgsAttributeEditorSpacerElement('Espaço', cont)
            esp_.setVerticalStretch(1)
            cont.addChildElement(esp_)
        raiz.addChildElement(cont)
    layer.setEditFormConfig(fc)
    _tabela_sem_ocultos(layer, spec.ocultos)
    return True


def _restricao(layer, i, restricao):
    """
    Restrição forte por expressão (vai no estilo, categoria Fields, e vale sem o plugin): o
    formulário não grava o valor que a reprova. Campo sem restrição na especificação perde a que
    tiver, para o reaplicar do estilo não deixar uma velha.
    """
    from qgis.core import QgsFieldConstraints
    C = QgsFieldConstraints.Constraint
    if restricao:
        layer.setConstraintExpression(i, restricao[0], restricao[1])
        layer.setFieldConstraint(i, C.ConstraintExpression, QgsFieldConstraints.ConstraintStrength.ConstraintStrengthHard)
    elif layer.constraintExpression(i):
        layer.removeFieldConstraint(i, C.ConstraintExpression)
        layer.setConstraintExpression(i, '')


def _termina_em_texto_longo(filhos):
    """A aba termina num texto multilinha, que já fica com a altura que sobra."""
    ultimo = filhos[-1] if filhos else None
    return isinstance(ultimo, esp.Campo) and ultimo.widget.tipo == 'TextEdit' and ultimo.widget.config.get('IsMultiline')


def colunas_proprias(layer, spec):
    """As colunas da aba de prefixo (attr_* do importador) presentes na camada, na ordem dela."""
    prefixos = [a.prefixo for a in spec.abas if a.prefixo]
    return [n for n in layer.fields().names() if any(n.startswith(p) for p in prefixos)]


def _propriedades(somente_leitura, expressao_rotulo):
    P = QgsEditFormConfig.DataDefinedProperty
    props = QgsPropertyCollection()
    if not somente_leitura:
        props.setProperty(P.Editable, QgsProperty.fromExpression(esp.EXPRESSAO_EDITAVEL))
    if expressao_rotulo:
        props.setProperty(P.Alias, QgsProperty.fromExpression(expressao_rotulo))
    return props


def _condicao(cont, condicao):
    if condicao is not None:
        cont.setVisibilityExpression(QgsOptionalExpression(QgsExpression(condicao.expressao())))


def _preencher(pai, filhos, campos):
    """
    Põe os filhos no contêiner. O QGIS só dá expressão de visibilidade a contêiner, então o campo
    condicional vai sozinho numa linha (contêiner Row, sem título e sem moldura) que carrega a
    condição: o GroupBox sem título ainda desenha moldura e a seta de recolher (medido).
    """
    for el in filhos:
        if isinstance(el, esp.Campo) and el.condicao is not None:
            cont = QgsAttributeEditorContainer('Conforme o símbolo: ' + el.coluna, pai)
            cont.setType(Qgis.AttributeEditorContainerType.Row)
            cont.setShowLabel(False)
            _condicao(cont, el.condicao)
            _campo(cont, el, campos)
            pai.addChildElement(cont)
            continue
        if isinstance(el, esp.Campo):
            _campo(pai, el, campos)
        elif isinstance(el, esp.Texto):
            t = QgsAttributeEditorTextElement(el.nome, pai)
            t.setText(el.texto)
            t.setShowLabel(False)
            pai.addChildElement(t)
        elif isinstance(el, esp.Grupo):
            cont = QgsAttributeEditorContainer(el.nome, pai)
            cont.setType(Qgis.AttributeEditorContainerType.GroupBox if el.titulo else Qgis.AttributeEditorContainerType.Row)
            cont.setShowLabel(el.titulo)
            cont.setCollapsed(el.recolhido)
            _condicao(cont, el.condicao)
            _preencher(cont, el.filhos, campos)
            pai.addChildElement(cont)


def _campo(pai, campo, campos):
    i = campos.indexOf(campo.coluna)
    if i >= 0:
        el = QgsAttributeEditorField(campo.coluna, i, pai)
        pai.addChildElement(el)
        if campo.rotulo_em_cima and campo.widget.config.get('IsMultiline'):
            # o texto longo fica com a sobra da aba; sem o esticamento, o editor de cor da mesma aba
            # cresce junto e fica com 200 px de altura (medido no QGIS 4.0.0, aba Linha da Linha)
            el.setVerticalStretch(1)


def _tabela_sem_ocultos(layer, ocultos):
    cfg = layer.attributeTableConfig()
    cfg.update(layer.fields())
    cols = cfg.columns()
    for c in cols:
        if c.type == QgsAttributeTableConfig.Type.Field:
            c.hidden = c.name in ocultos
    cfg.setColumns(cols)
    layer.setAttributeTableConfig(cfg)
