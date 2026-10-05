# -*- coding: utf-8 -*-
"""
O número que o ESTILO da camada desenha quando a coluna é nula, lido do próprio estilo.

O dock mostra numa caixa giratória o valor de cada coluna numérica. Na coluna nula ele mostrava o
mínimo da faixa (o espaçamento da hachura nulo aparecia como 1 px e o estilo desenhava 8; a
espessura, 0,5 px contra 2), e o operador lia um valor que o mapa não usa. Agora mostra o valor
que o desenho usa, sem gravá-lo, como a posição do texto da Área (decisão do chefe, 2026-10-05).

De onde vem o valor: do QML da camada (simbologia e rótulos), com as três formas pelas quais os
estilos do calco dão valor ao nulo, nesta ordem (a primeira contém a terceira):

    CASE WHEN coalesce("c", 0) <> 0 THEN "c" ELSE N END    a Seta: nulo e zero valem N
    CASE WHEN "c" > 0 THEN "c" ELSE N END                  nulo, zero e negativo valem N
    coalesce("c", N)                                        nulo vale N

Com um N só no estilo, é ele. Com mais de um (na Área, a opacidade nula é 0 no preenchimento e 1
na hachura, e o preenchimento some sob a hachura), vale o N que deixa iguais, para ESTA feição,
todas as expressões das camadas de símbolo que desenham (a regra que casa e a camada ligada).
Sem N (a coluna que o estilo não lê, ou o zoom de criação que o estilo das formas trata como
"sem âncora" por `IS NOT NULL`), não há número que o desenho use: o dock mostra "Não definido".

Lido do estilo da camada, e não de uma tabela escrita à mão, o valor segue o estilo que de fato
desenha, inclusive o personalizado. A régua é testes/test_dock_nulos.py: em todo tipo com
especificação e em todo campo numérico, a feição com o nulo e a feição com o valor que o dock
mostra desenham os mesmos pixels.
"""
import html
import re

from qgis.core import (
    Qgis, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeature, QgsMapLayer,
    QgsReadWriteContext, QgsRenderContext, QgsRuleBasedRenderer, QgsSymbolLayer,
)
from qgis.PyQt.QtXml import QDomDocument

TEXTO_NULO = 'Não definido'
_NUMERO = r'(-?\d+(?:\.\d+)?)'
_FORMAS = (
    r'CASE WHEN coalesce\(\s*{c}\s*,\s*0\s*\)\s*<>\s*0 THEN {c} ELSE {n} END',
    r'CASE WHEN {c}\s*>\s*0 THEN {c} ELSE {n} END',
    r'coalesce\(\s*{c}\s*,\s*{n}\s*\)',
)


def texto_do_estilo(layer):
    """O QML da simbologia e dos rótulos da camada, com as entidades do XML desfeitas."""
    doc = QDomDocument()
    layer.exportNamedStyle(doc, QgsReadWriteContext(),
                           QgsMapLayer.StyleCategory.Symbology | QgsMapLayer.StyleCategory.Labeling)
    return html.unescape(doc.toString())


def candidatos(texto, coluna):
    """Os N que o estilo dá à coluna nula, na ordem em que aparecem (com repetição)."""
    c = re.escape('"{}"'.format(coluna))
    achados = []
    for forma in _FORMAS:
        padrao = forma.format(c=c, n=_NUMERO)
        achados += [float(x) for x in re.findall(padrao, texto)]
        texto = re.sub(padrao, ' ', texto)
    return achados


def _verdadeiro(expressao, ctx):
    e = QgsExpression(expressao)
    v = e.evaluate(ctx)
    return not e.hasEvalError() and bool(v) and v is not None and not (hasattr(v, 'isNull') and v.isNull())


def _simbolos_que_desenham(renderer, ctx):
    """Os símbolos que o renderer usa para a feição do contexto (regra que casa; o ELSE sem irmã que case)."""
    if isinstance(renderer, QgsRuleBasedRenderer):
        def andar(regra):
            casou = False
            filhos = [r for r in regra.children() if r.active()]
            for r in filhos:
                if r.isElse() or (r.filterExpression() and not _verdadeiro(r.filterExpression(), ctx)):
                    continue
                casou = True
                if r.symbol() is not None:
                    yield r.symbol()
                yield from andar(r)
            if not casou:
                for r in filhos:
                    if r.isElse():
                        if r.symbol() is not None:
                            yield r.symbol()
                        yield from andar(r)
        yield from andar(renderer.rootRule())
        return
    simbolo = getattr(renderer, 'symbol', None)
    if callable(simbolo) and simbolo() is not None:
        yield simbolo()
        return
    yield from renderer.symbols(QgsRenderContext())


def _expressoes_que_desenham(simbolo, ctx):
    """As expressões das camadas de símbolo LIGADAS para a feição (e dos subsímbolos delas)."""
    out = []
    for sl in simbolo.symbolLayers():
        if not sl.enabled():
            continue
        dd = sl.dataDefinedProperties()
        ligada = dd.property(QgsSymbolLayer.Property.LayerEnabled)
        if ligada.isActive():
            v = ligada.valueAsBool(ctx, True)
            if not (v[0] if isinstance(v, tuple) else v):
                continue
        for chave in dd.propertyKeys():
            p = dd.property(chave)
            if p.isActive() and p.propertyType() == Qgis.PropertyType.Expression:
                out.append(p.expressionString())
        if hasattr(sl, 'geometryExpression'):
            out.append(sl.geometryExpression())
        if sl.subSymbol() is not None:
            out += _expressoes_que_desenham(sl.subSymbol(), ctx)
    return out


def _avaliar(expressoes, ctx):
    out = []
    for texto in expressoes:
        e = QgsExpression(texto)
        v = e.evaluate(ctx)
        if hasattr(v, 'asWkt'):
            v = v.asWkt(9)
        elif hasattr(v, 'name') and callable(v.name):  # QColor
            v = v.name(v.NameFormat.HexArgb) if hasattr(v, 'NameFormat') else v.name()
        out.append((e.hasEvalError(), str(v)))
    return out


def desempatar(layer, coluna, feicao, valores):
    """
    O N que desenha como o nulo nesta feição: o que deixa iguais todas as expressões que desenham e
    leem a coluna. Empate (nenhuma camada que desenha lê a coluna), o que mais aparece no estilo.
    """
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    ctx.setFeature(feicao)
    marca = '"{}"'.format(coluna)
    expressoes = [e for s in _simbolos_que_desenham(layer.renderer(), ctx)
                  for e in _expressoes_que_desenham(s, ctx) if marca in e]
    base = _avaliar(expressoes, ctx)
    iguais = []
    for n in valores:
        f = QgsFeature(feicao)
        f.setAttribute(coluna, n)
        ctx.setFeature(f)
        if _avaliar(expressoes, ctx) == base:
            iguais.append(n)
    if len(iguais) == 1:
        return iguais[0]
    return None if not iguais else iguais[0]


class PadroesDoEstilo:
    """Os candidatos por coluna, lidos uma vez do estilo da camada (o dock zera ao trocar de camada ou de estilo)."""

    def __init__(self, layer):
        self.layer = layer
        self._texto = None
        self._por_coluna = {}

    def candidatos(self, coluna):
        if coluna not in self._por_coluna:
            if self._texto is None:
                self._texto = texto_do_estilo(self.layer)
            achados = candidatos(self._texto, coluna)
            # o mais frequente primeiro: decide o empate de desempatar()
            self._por_coluna[coluna] = sorted(set(achados), key=lambda n: (-achados.count(n), achados.index(n)))
        return self._por_coluna[coluna]

    def valor(self, coluna, feicao):
        """O número que o estilo desenha para a coluna nula nesta feição, ou None (não há)."""
        valores = self.candidatos(coluna)
        if not valores:
            return None
        if len(valores) == 1:
            return valores[0]
        return desempatar(self.layer, coluna, feicao, valores)
