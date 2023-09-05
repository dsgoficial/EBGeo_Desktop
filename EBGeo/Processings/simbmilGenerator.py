from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing, QgsWkbTypes,
                       QgsFeatureSink, QgsProcessingException,
                       QgsProcessingAlgorithm, QgsFields, QgsMapLayerStyle,
                       QgsProcessingParameterFeatureSource, QgsCoordinateReferenceSystem, QgsVectorLayer,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterFile, QgsField, QgsProject, QgsDefaultValue)
from qgis.gui import (QgsMapCanvas)


class CreateLayerSimbMil(QgsProcessingAlgorithm):
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output Layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        fields = QgsFields()
        fields.append(QgsField('id', QVariant.Int))
        fields.append(QgsField('nome', QVariant.String))
        fields.append(QgsField('simb_rot', QVariant.Double))
        fields.append(QgsField('simb_size', QVariant.Double))
        fields.append(QgsField('path', QVariant.String))

        OUTPUT = QgsVectorLayer("Point?crs=EPSG:4326", "Simb Mil Ponto", "memory")
        OUTPUT.startEditing()
        layerProvider = OUTPUT.dataProvider()

        layerProvider.addAttributes(fields)
        OUTPUT.updateFields()

        default_val = QgsDefaultValue(
                """
                CASE
                WHEN maximum("id") is NULL THEN 0
                WHEN "id" is NULL THEN maximum("id")+1
                ELSE "id"
                END
                """,
                applyOnUpdate=True)
        
        OUTPUT.setDefaultValueDefinition(layerProvider.fields().lookupField('id'), default_val)

        QgsProject.instance().addMapLayer(OUTPUT)

        style_path = r'C:\Users\marcel\Desktop\TESTE.qml'
        OUTPUT.loadNamedStyle(style_path)

        OUTPUT.commitChanges()

        return {"OUTPUT": OUTPUT}

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return '1 - Criar Camada de Simbologia Militar Ponto'

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
        Acesse https://simbologia.eb.mil.br/, na opção Monte Seu Símbolo, realize as modificações necessárias e em seguida salve o arquivo no formato .svg
        Escolha uma pasta onde só irão existir os arquivos baixados.
        Atenção, os arquivos devem ser numerados de acordo com a ID a ser criada de cada ponto, ou seja, o ponto de ID = 1 irá receber o .svg salvo com o nome 1.svg
        """)
    def createInstance(self):
        return CreateLayerSimbMil()
