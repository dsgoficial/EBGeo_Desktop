# -*- coding: utf-8 -*-
"""
Dock do Símbolo Militar, do Símbolo de Engenharia e da Declinação Magnética (especificação em
formulario/tipos/militar.py).

Os widgets ricos são os de sempre do painel: o SIDC com "Configurar..." (construtor de SIDC) e o
item de engenharia com "Configurar..." (seletor do C 5-36). O que muda é o caminho da gravação:
tudo entra no buffer de edição pelo painel, e o SVG é redesenhado pelo guardião da camada no
mesmo comando (guardiao.py), como no formulário nativo e na tabela de atributos.

Aqui também moram o texto por expressão da especificação ([% %], com current_value() lendo a
feição do buffer) e a ação "Recalcular" da declinação.
"""
from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QPushButton

from ... import schema


def tem_expressao(texto):
    return '[%' in (texto or '')


def texto_avaliado(painel, texto):
    """O texto da especificação com as expressões avaliadas na feição do painel (buffer incluído)."""
    if not tem_expressao(texto) or painel.layer is None or painel.fid is None:
        return texto
    feat = painel.layer.getFeature(painel.fid)
    ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(painel.layer))
    ctx.appendScope(QgsExpressionContextUtils.formScope(feat))
    ctx.setFeature(feat)
    return QgsExpression.replaceExpressionText(texto, ctx)


def acoes(painel, travada):
    """Os botões de ação do tipo no painel da especificação."""
    if painel.tipo == 'magnetic_declination':
        b = QPushButton('Recalcular')
        b.setToolTip('Recalcula declinação, convergência e campo magnético (WMM2025) na posição atual do diagrama.')
        b.clicked.connect(lambda *_: recalcular_declinacao(painel))
        b.setEnabled(not travada)
        painel.acoes.addWidget(b)


def valores_declinacao(feat):
    """As colunas da declinação recalculadas na posição da feição (WGS84, como o calco)."""
    from ...motor import declinacao
    p = feat.geometry().asPoint()
    web = declinacao.calcular(p.y(), p.x()) or {}
    m = schema.mapa_web('magnetic_declination')
    return {m[k]: v for k, v in web.items() if k in m}


def recalcular_declinacao(painel):
    """Recalcula no buffer de edição; o guardião redesenha o diagrama no mesmo comando."""
    if painel.fid is None:
        return
    try:
        valores = valores_declinacao(painel.layer.getFeature(painel.fid))
    except ImportError:
        return
    painel._pendentes.update(valores)
    painel._gravar_pendentes()
    QTimer.singleShot(0, painel._selecao_mudou)


def aplicar_construtor(painel, novo):
    """As colunas que o construtor de SIDC devolveu, no buffer, e o painel remontado (os textos seguem o conjunto)."""
    if not novo or painel.fid is None:
        return
    painel._pendentes.update(novo)
    painel._gravar_pendentes()
    QTimer.singleShot(0, painel._selecao_mudou)
