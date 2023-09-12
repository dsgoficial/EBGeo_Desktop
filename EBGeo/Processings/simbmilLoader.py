from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (QgsProcessing, QgsProcessingException,
                       QgsProcessingAlgorithm, QgsProcessingParameterVectorLayer, QgsProcessingParameterFile)
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
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorPoint]
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
        
        # Get info about files in INPUT_FOLDER
        paths = []
        for file_name in os.listdir(inputFolder):
            file_path = os.path.join(inputFolder, file_name)
            paths.append(file_path)

        # Get layer information
        layer = self.parameterAsLayer(parameters, self.INPUT, context)
        layer.startEditing()
        field_index = layer.fields().indexFromName('path')
        for feat in layer.getFeatures():
            path_destination_png = os.path.join(inputFolder, (str((feat['nome']))+'.png'))
            path_destination_PNG = os.path.join(inputFolder, (str((feat['nome']))+'.PNG'))
            if path_destination_png in paths or path_destination_PNG in paths:
                path_destination = path_destination_png if path_destination_png in paths else path_destination_PNG
                layer.changeAttributeValue(feat.id(), field_index, path_destination)
        
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
        return 'Carregar Simbologia Militar'

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
        Selecione a camada de pontos de simbologia militar e em seguida a pasta onde foram salvos os arquivos .png, o arquivo deve ter o mesmo nome do campo 'nome'
        """)

    def createInstance(self):
        return SimbMilAlgorithm()
