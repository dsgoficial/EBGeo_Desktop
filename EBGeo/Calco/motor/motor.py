# -*- coding: utf-8 -*-
"""
Ponte Python do motor de símbolos pontuais: carrega ebgeo-simbologia.js (os geradores do
EBGeo Web empacotados por build/build.mjs) num QJSEngine, uma vez por sessão, e expõe

    Motor.instancia().simbolo_militar(props)  -> dict
    Motor.instancia().medida(props)           -> dict
    Motor.instancia().engenharia(props)       -> NotImplementedError (pendência, ver README)
    Motor.instancia().catalogos()             -> dict (catalogos.json)

`props` usa os NOMES DE PROPRIEDADE do EBGeo Web (sidc, fillColor, uniqueDesignation,
pointCode, echelonCode...). O dict devolvido traz svg (corrigido para o QSvgRenderer),
svgWeb (o SVG exato do Web), largura, altura, ancoraX, ancoraY (deslocamento do centro do
desenho em pixels lógicos, positivo para a direita e para baixo), valido e avisos.

O QJSEngine exige uma QGuiApplication viva (o QgsApplication é uma).
"""
import json
import os
import threading

try:  # QGIS 4 (Qt 6); o shim qgis.PyQt não traz QtQml.
    from PyQt6.QtQml import QJSEngine, QJSValue
except ImportError:  # pragma: no cover - QGIS 3 (Qt 5)
    from PyQt5.QtQml import QJSEngine, QJSValue

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_BUNDLE = os.path.join(PASTA, 'ebgeo-simbologia.js')
ARQUIVO_CATALOGOS = os.path.join(PASTA, 'catalogos.json')


class ErroMotor(Exception):
    """Erro do motor de símbolos, com a mensagem do JavaScript quando houver."""


def _mensagem_de_erro(valor):
    partes = [valor.toString()]
    for prop in ('lineNumber', 'stack'):
        p = valor.property(prop)
        if not p.isUndefined() and p.toString():
            partes.append('{}: {}'.format(prop, p.toString()[:500]))
    return ' | '.join(partes)


class Motor:
    """Singleton preguiçoso: o bundle (cerca de 1 MB) só é avaliado no primeiro uso."""

    _instancia = None
    _trava = threading.Lock()

    @classmethod
    def instancia(cls):
        if cls._instancia is None:
            with cls._trava:
                if cls._instancia is None:
                    cls._instancia = cls()
        return cls._instancia

    @classmethod
    def descartar(cls):
        """Esquece a instância (testes, ou depois de regerar o bundle)."""
        cls._instancia = None

    def __init__(self, caminho_bundle=ARQUIVO_BUNDLE):
        if not os.path.exists(caminho_bundle):
            raise ErroMotor('Bundle do motor não encontrado: {}. Gere-o com motor/build/build.mjs.'.format(
                os.path.basename(caminho_bundle)))
        self._engine = QJSEngine()
        with open(caminho_bundle, encoding='utf-8') as f:
            codigo = f.read()
        r = self._engine.evaluate(codigo, os.path.basename(caminho_bundle))
        if r.isError():
            raise ErroMotor('Falha ao carregar o bundle: ' + _mensagem_de_erro(r))
        self._api = self._engine.globalObject().property('EBGeoSimbologia')
        if not self._api.isObject():
            raise ErroMotor('O bundle não definiu EBGeoSimbologia')
        self._json = self._engine.globalObject().property('JSON')
        self._catalogos = None
        self.versao = self._converter(self._api.property('versao'))

    # -- conversão -------------------------------------------------------------------------

    def _para_js(self, objeto):
        texto = json.dumps(objeto if objeto is not None else {}, ensure_ascii=False, default=str)
        v = self._json.property('parse').callWithInstance(self._json, [texto])
        if v.isError():
            raise ErroMotor('Propriedades não serializáveis: ' + v.toString())
        return v

    def _converter(self, valor):
        if valor.isUndefined() or valor.isNull():
            return None
        texto = self._json.property('stringify').callWithInstance(self._json, [valor])
        if texto.isError() or texto.isUndefined():
            raise ErroMotor('Resultado não serializável: ' + texto.toString())
        return json.loads(texto.toString())

    def _chamar(self, funcao, props):
        f = self._api.property(funcao)
        if not f.isCallable():
            raise ErroMotor('Função {} ausente no bundle'.format(funcao))
        r = f.call([self._para_js(props)])
        if r.isError():
            raise ErroMotor('{}: {}'.format(funcao, _mensagem_de_erro(r)))
        return self._converter(r)

    # -- API -------------------------------------------------------------------------------

    def simbolo_militar(self, props):
        """Símbolo militar por SIDC (20 ou 30 dígitos) e amplificadores, com nomes do Web."""
        return self._chamar('gerarSimboloMilitar', props)

    def medida(self, props):
        """Medida de coordenação por pointCode/echelonCode, textos e fillColor."""
        return self._chamar('gerarMedida', props)

    def engenharia(self, props):
        raise NotImplementedError(
            'Símbolos de engenharia ainda não estão no motor: o gerador do Web monta o desenho com '
            'DOMParser e mede texto e caixas com getComputedTextLength/getBBox (ver motor/build/README.md).')

    def svg_milsymbol_bruto(self, sidc, opcoes=None):
        """milsymbol sem o pós-processamento brasileiro (pior caso dos testes, depuração)."""
        r = self._api.property('svgMilsymbolBruto').call([sidc, self._para_js(opcoes or {})])
        if r.isError():
            raise ErroMotor(_mensagem_de_erro(r))
        return r.toString()

    def codigos_de_medida(self):
        return self._converter(self._api.property('codigosDeMedida').call([]))

    def corrigir_texto_para_qt(self, svg):
        r = self._api.property('corrigirTextoParaQt').call([svg])
        if r.isError():
            raise ErroMotor(_mensagem_de_erro(r))
        return r.toString()

    def catalogos(self):
        """Catálogos da interface (gerados no build, lidos do JSON ao lado do bundle)."""
        if self._catalogos is None:
            with open(ARQUIVO_CATALOGOS, encoding='utf-8') as f:
                self._catalogos = json.load(f)
        return self._catalogos


def catalogos():
    """Atalho que não exige o QJSEngine: os catálogos são JSON puro."""
    with open(ARQUIVO_CATALOGOS, encoding='utf-8') as f:
        return json.load(f)
