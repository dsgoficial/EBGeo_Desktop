# -*- coding: utf-8 -*-
"""
Algoritmo de Processing "Exportar arquivo .ebgeo" (id exportarebgeo).

Lê o calco (GeoPackage), monta o .ebgeo que o EBGeo Web importa e o grava. O estado da árvore
(mapa ligado, camadas EBGeo ligadas, opacidade, bloqueio) é lido no prepareAlgorithm, que o
QGIS roda na thread principal; a montagem e a gravação rodam no processamento. A conferência
relê o arquivo gravado pelo leitor do importador e compara com o que se montou.

A classe não se registra sozinha: o provider do plugin a adiciona.
"""
import logging

from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingOutputNumber, QgsProcessingParameterEnum,
    QgsProcessingParameterFile, QgsProcessingParameterFileDestination,
)
from qgis.PyQt.QtCore import QCoreApplication

from . import arquivo, montador

ESCOPOS = [montador.ESCOPO_TUDO, montador.ESCOPO_ATUAL]


class _LogFeedback(logging.Handler):
    def __init__(self, feedback):
        super().__init__(logging.INFO)
        self.feedback = feedback

    def emit(self, record):
        (self.feedback.pushWarning if record.levelno >= logging.WARNING else self.feedback.pushInfo)(
            record.getMessage())


class ExportarEbgeo(QgsProcessingAlgorithm):
    CALCO = 'CALCO'
    ESCOPO = 'ESCOPO'
    SAIDA = 'SAIDA'
    ORIGINAL = 'ORIGINAL'

    def tr(self, s):
        return QCoreApplication.translate('ExportarEbgeo', s)

    def createInstance(self):
        return ExportarEbgeo()

    def name(self):
        return 'exportarebgeo'

    def displayName(self):
        return self.tr('Exportar arquivo .ebgeo')

    def group(self):
        return self.tr('Calco')

    def groupId(self):
        return 'calco'

    def shortHelpString(self):
        return self.tr(
            'Grava o calco num arquivo .ebgeo (esquema 3.0) que o EBGeo Web importa. Um atlas importado volta '
            'com os mesmos mapas, camadas, grupos e ordem, e o que o Desktop não mostra (360, 3D, briefings, '
            'temporal, comentários) volta como veio. Só as propriedades editadas no Desktop são reescritas; a '
            'feição desenhada no Desktop vai para o mapa e a camada em que foi desenhada. Com o atlas no '
            'projeto, o mapa ligado é o mapa atual do arquivo e o estado das camadas é o da árvore. Salve as '
            'edições antes de exportar: o arquivo sai do que está gravado no GeoPackage. Calco importado antes de '
            '2026-10-05: aponte o .ebgeo original para recuperar as fotos de 3D e 360 e as figuras de slide.')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.CALCO, self.tr('Calco (GeoPackage)'), extension='gpkg'))
        self.addParameter(QgsProcessingParameterEnum(
            self.ESCOPO, self.tr('O que exportar'),
            options=[self.tr('Todos os mapas do calco'), self.tr('Só o mapa atual')], defaultValue=0))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.SAIDA, self.tr('Arquivo .ebgeo de saída'), self.tr('Arquivo do EBGeo (*.ebgeo)')))
        original = QgsProcessingParameterFile(
            self.ORIGINAL, self.tr('Arquivo .ebgeo original (só para calco importado antes de 2026-10-05)'),
            extension='ebgeo', optional=True)
        original.setHelp(self.tr(
            'O calco importado antes de 2026-10-05 não guardou os bytes das fotos de 3D e 360 e das figuras de '
            'slide. Aponte o .ebgeo de que ele foi importado para recuperá-los: o arquivo só é usado se for o '
            'mesmo da importação (SHA-256 conferido).'))
        self.addParameter(original)
        for nome, rotulo in (('FEICOES', 'Feições no arquivo'), ('EDITADAS', 'Feições editadas no Desktop'),
                             ('NOVAS', 'Feições criadas no Desktop'), ('IMAGENS', 'Imagens no arquivo'),
                             ('RECUPERADAS', 'Imagens recuperadas do .ebgeo original')):
            self.addOutput(QgsProcessingOutputNumber(nome, self.tr(rotulo)))

    def prepareAlgorithm(self, parameters, context, feedback):
        from qgis.core import QgsProject
        from . import desenho
        self._estado = {}
        caminho = self.parameterAsFile(parameters, self.CALCO, context)
        projeto = context.project() or QgsProject.instance()
        if caminho and projeto is not None:
            pendentes = desenho.edicoes_pendentes(caminho, projeto)
            if pendentes:
                feedback.pushWarning(self.tr('Edições não salvas em {}: o arquivo sai do que está gravado.').format(
                    ', '.join(sorted({l.name() for l in pendentes}))))
            self._estado = desenho.estado_da_arvore(caminho, projeto)
        return True

    def processAlgorithm(self, parameters, context, feedback):
        from . import desenho
        caminho = self.parameterAsFile(parameters, self.CALCO, context)
        escopo = ESCOPOS[self.parameterAsEnum(parameters, self.ESCOPO, context)]
        saida = self.parameterAsFileOutput(parameters, self.SAIDA, context)
        if not saida.lower().endswith('.ebgeo'):
            saida += '.ebgeo'
        log = logging.getLogger('EBGeo.Calco.exportador')
        h = _LogFeedback(feedback)
        log.addHandler(h)
        log.setLevel(logging.INFO)
        try:
            original = self.parameterAsFile(parameters, self.ORIGINAL, context) or None
            exp = montador.montar(caminho, escopo, getattr(self, '_estado', {}), desenho.GeradorDesenho(), log,
                                  original)
            feedback.setProgress(70)
            arquivo.gravar(saida, exp.data, exp.imagens)
        except montador.ErroExportacao as e:
            raise QgsProcessingException(str(e))
        finally:
            log.removeHandler(h)
        erros = arquivo.conferir(saida, exp.data, exp.imagens)
        if erros:
            raise QgsProcessingException(self.tr('O arquivo gravado não confere: {}').format('; '.join(erros)))
        r = exp.relatorio
        feedback.pushInfo(self.tr(
            '{} feições em {} mapa(s): {} sem mudança, {} editadas, {} criadas no Desktop, {} apagadas no '
            'Desktop, {} devolvidas como vieram; {} imagens. Relido e conferido.').format(
            r.total(), len(r.mapas), r.iguais, r.editadas, r.novas, r.apagadas, r.repassadas, r.imagens))
        if r.recuperadas:
            feedback.pushInfo(self.tr('{} imagens recuperadas do .ebgeo original.').format(r.recuperadas))
        return {self.SAIDA: saida, 'FEICOES': r.total(), 'EDITADAS': r.editadas, 'NOVAS': r.novas,
                'IMAGENS': r.imagens, 'RECUPERADAS': r.recuperadas}
