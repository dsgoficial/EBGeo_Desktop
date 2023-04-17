from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing, QgsWkbTypes, QgsVectorLayer,
                       QgsFeatureSink, QgsProcessingException,
                       QgsProcessingAlgorithm, QgsFields, QgsProcessingParameters,
                       QgsProcessingParameterFeatureSource, QgsCoordinateReferenceSystem,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFile)
import os


class SimbMilAlgorithm(QgsProcessingAlgorithm):
    """
    This is an example algorithm that takes a vector layer and
    creates a new identical one.

    It is meant to be used as an example of how to create your own
    algorithms and explain methods and variables used to do it. An
    algorithm like this will be available in all elements, and there
    is not need for additional work.

    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    INPUT = 'INPUT'
    INPUT_FOLDER = 'INPUT_FOLDER'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FOLDER,
                self.tr("Input folder"),
                behavior=QgsProcessingParameterFile.Folder,
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        # Get folder information
        inputFolder = self.parameterAsString(parameters, self.INPUT_FOLDER, context)
        if inputFolder is None:
            raise QgsProcessingException(self.tr("Invalid input folder."))


        # Get layer information
        layer = self.parameterAsLayer(parameters, self.INPUT, context)
        layer.startEditing()
        selected_feats = layer.getFeatures()
        attr = [ feat.attributes() for feat in selected_feats ]
        field_index = layer.fields().indexFromName('path')

        for k in range(len(attr)):
            print(k)
            layer.changeAttributeValue(k+1, field_index, inputFolder + "\\" +  str((attr[k][0])) + '.svg')
        layer.commitChanges()
        
        return {"OUTPUT": inputFolder}
    
    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return '2 - Carregar Simbologia Militar'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Simbologia Militar'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)
    
    def shortHelpString(self):
        return self.tr("""
        Selecione a camada criada no passo 1 - Criar Camada de Simbologia Militar Ponto e em seguida a pasta onde foram salvos os arquivos .svg
        """)

    def createInstance(self):
        return SimbMilAlgorithm()
