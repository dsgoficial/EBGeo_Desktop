# -*- coding: utf-8 -*-
"""
Algoritmo de Processing "Importar arquivo .ebgeo" (id importarebgeo).

Lê o .ebgeo do EBGeo Web, grava o calco num GeoPackage (uma tabela por tipo,
estilo padrão de cada tipo no layer_styles) e, se pedido, monta a árvore de
camadas no projeto. A gravação roda no processamento; estilo e árvore mexem
em objetos de interface e por isso ficam no postProcessAlgorithm, que o
QGIS executa na thread principal.

A classe não se registra sozinha: o provider do plugin a adiciona.
"""
import logging
import os

from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingParameterFile, QgsProcessingParameterFileDestination,
    QgsProcessingParameterBoolean, QgsProcessingException, QgsProject, QgsProcessingOutputNumber,
)
from qgis.PyQt.QtCore import QCoreApplication

from . import leitor, escritor


class _LogFeedback(logging.Handler):
    """Encaminha o log do importador para o feedback do Processing."""

    def __init__(self, feedback):
        super().__init__(logging.INFO)
        self.feedback = feedback

    def emit(self, record):
        msg = record.getMessage()
        if record.levelno >= logging.WARNING:
            self.feedback.pushWarning(msg)
        else:
            self.feedback.pushInfo(msg)


class ImportarEbgeo(QgsProcessingAlgorithm):
    ARQUIVO = 'ARQUIVO'
    SAIDA = 'SAIDA'
    CARREGAR = 'CARREGAR'

    def tr(self, s):
        return QCoreApplication.translate('ImportarEbgeo', s)

    def createInstance(self):
        return ImportarEbgeo()

    def name(self):
        return 'importarebgeo'

    def displayName(self):
        return self.tr('Importar arquivo .ebgeo')

    def group(self):
        return self.tr('Calco')

    def groupId(self):
        return 'calco'

    def shortHelpString(self):
        return self.tr(
            'Importa o arquivo .ebgeo exportado pelo EBGeo Web (versões 1.3 a 3.0) para um calco em '
            'GeoPackage, com uma tabela por tipo de feição do mapa 2D. Cada mapa do atlas vira um grupo '
            '(um ligado por vez, como no Web), cada camada do EBGeo um subgrupo, e a ordem de desenho segue '
            'a do Web. 360, 3D, briefings, temporal e comentários não viram camada, mas o data.json inteiro '
            'fica preservado na tabela ebgeo_documento.')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.ARQUIVO, self.tr('Arquivo .ebgeo'), extension='ebgeo'))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.SAIDA, self.tr('GeoPackage de saída'), self.tr('GeoPackage (*.gpkg)')))
        self.addParameter(QgsProcessingParameterBoolean(
            self.CARREGAR, self.tr('Carregar no projeto'), defaultValue=True))
        for nome, rotulo in (('FEICOES', 'Feições gravadas'), ('MAPAS', 'Mapas'), ('DESCARTADAS', 'Feições descartadas')):
            self.addOutput(QgsProcessingOutputNumber(nome, self.tr(rotulo)))

    def processAlgorithm(self, parameters, context, feedback):
        arquivo = self.parameterAsFile(parameters, self.ARQUIVO, context)
        saida = self.parameterAsFileOutput(parameters, self.SAIDA, context)
        if not saida.lower().endswith('.gpkg'):
            saida += '.gpkg'
        self._carregar = self.parameterAsBoolean(parameters, self.CARREGAR, context)
        self._saida = saida

        log = logging.getLogger('EBGeo.Calco.importador')
        h = _LogFeedback(feedback)
        log.addHandler(h)
        log.setLevel(logging.INFO)
        try:
            rel = escritor.importar(arquivo, saida, log=log,
                                    feedback=lambda f: feedback.setProgress(int(90 * f)))
        except leitor.ErroEbgeo as e:
            raise QgsProcessingException(str(e))
        finally:
            log.removeHandler(h)

        conferido = escritor.contar_gpkg(saida)
        feedback.pushInfo(self.tr('{} feições gravadas em {} mapas ({} descartadas). Relido do GeoPackage: {}').format(
            rel.total(), rel.mapas, len(rel.descartadas), sum(conferido.values())))
        if sum(conferido.values()) != rel.total():
            raise QgsProcessingException(self.tr(
                'A releitura do GeoPackage não confere: {} gravadas, {} relidas.').format(
                rel.total(), sum(conferido.values())))
        for mapa, tipo, ident, motivo in rel.descartadas:
            feedback.pushWarning(self.tr('Descartada: mapa "{}", {} {}: {}').format(mapa, tipo, ident, motivo))
        if rel.motor_simbolos is False:
            feedback.pushInfo(self.tr('Motor de símbolos indisponível: os símbolos militares usam o bitmap do arquivo.'))
        self._resultados = {self.SAIDA: saida, 'FEICOES': rel.total(), 'MAPAS': rel.mapas,
                            'DESCARTADAS': len(rel.descartadas)}
        return dict(self._resultados)

    def postProcessAlgorithm(self, context, feedback):
        from . import arvore
        saida = getattr(self, '_saida', None)
        if not saida or not os.path.exists(saida):
            return {}
        usados = arvore.salvar_estilos(saida)
        simples = sorted(t for t, m in usados.items() if m == 'estilo_simples')
        if simples:
            feedback.pushInfo(self.tr('Estilo simples (módulo próprio ausente) em: {}').format(', '.join(simples)))
        if getattr(self, '_carregar', False):
            projeto = context.project() or QgsProject.instance()
            arvore.montar_arvore(saida, projeto)
        return dict(getattr(self, '_resultados', {self.SAIDA: saida}))
