# -*- coding: utf-8 -*-

# Importar as bibliotecas necessárias:
import glob
import itertools
import os
import shutil
import zipfile

from qgis import processing
from qgis.core import (QgsProcessingAlgorithm, QgsProcessingMultiStepFeedback,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingUtils)
from qgis.PyQt.QtCore import QCoreApplication


class ConvertBDGExZIPtoMASACODE(QgsProcessingAlgorithm):
    INPUT_FOLDER = 'INPUT_FOLDER'
    KEEP_ATTRIBUTES = 'KEEP_ATTRIBUTES'
    OUTPUT_FOLDER = 'OUTPUT_FOLDER'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT_MODE_OPTIONS = [
        'Criar uma pasta no destino para cada zip',
        'Consolidar todos os zips em uma única pasta de saída',
    ]

    def initAlgorithm(self, config = None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                self.tr('Pasta com os arquivos no formato zip'),
                behavior=QgsProcessingParameterFile.Folder,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.KEEP_ATTRIBUTES,
                self.tr('Manter atributos da modelagem original'),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT_FOLDER,
                self.tr('Pasta para salvar os arquivos exportados')
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_MODE,
                self.tr('Modo de saída'),
                options=self.OUTPUT_MODE_OPTIONS,
                defaultValue=0,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):         
        self.outputFolderPath = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        keepAttributes = self.parameterAsBool(parameters, self.KEEP_ATTRIBUTES, context)
        consolidateOutput = self.parameterAsEnum(parameters, self.OUTPUT_MODE, context) == 1
        inputFolder = self.parameterAsFile(
            parameters, self.INPUT_FOLDER, context)
        inputFiles = list(
            set(
                [
                    i for i in itertools.chain.from_iterable(
                        [glob.glob(f'{inputFolder}/**/*.zip'), glob.glob(f'{inputFolder}/*.zip')]
                    )
                ]
            )
        )
        nInputs = len(inputFiles)
        if nInputs == 0:
            return {self.OUTPUT_FOLDER: 'Não foi possível localizar os arquivos no formato zip na pasta informada'}
        multiStepFeedback = QgsProcessingMultiStepFeedback(nInputs, feedback)
        for current, file in enumerate(inputFiles):
            if feedback.isCanceled():
                break
            multiStepFeedback.setProgressText(f"Convertendo arquivo {current+1}/{nInputs}")
            multiStepFeedback.setCurrentStep(current)
            self.tempFolder = QgsProcessingUtils.tempFolder()
            with zipfile.ZipFile(file, 'r') as zip_ref:
                zip_ref.extractall(self.tempFolder)
            zip_ref.close()
            fileList = [i for i in glob.glob(f'{self.tempFolder}/**/*.shp')]
            if consolidateOutput:
                outputFolder = self.outputFolderPath
                appendToExisting = current > 0
            else:
                zipName = os.path.splitext(os.path.basename(file))[0]
                outputFolder = os.path.join(self.outputFolderPath, zipName)
                appendToExisting = False
            processing.run(
                "EBGeoProvider:convertedgvtomasacode",
                {
                    "INPUT": fileList,
                    "KEEP_ATTRIBUTES": keepAttributes,
                    "OUTPUT_FOLDER": outputFolder,
                    "APPEND_TO_EXISTING": appendToExisting,
                },
                context=context,
                feedback=multiStepFeedback
            )

        return {self.OUTPUT_FOLDER: 'Conversão concluída'}


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ConvertBDGExZIPtoMASACODE()

    def name(self):
        return 'convertbdgexziptomasacode'

    def displayName(self):
        return self.tr("Zips BDGEx para o formato MASACODE")

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return 'MASACODE'

    def shortHelpString(self):
        return self.tr('Converte em lote os zips contendo shapefiles no formato EDGV para o formato MASACODE')
