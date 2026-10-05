# -*- coding: utf-8 -*-
"""
Cobertura de radar ou sensor para alvo em altitude fixa (algoritmo de Processing).

Para cada sensor (ponto, altura da antena acima do terreno, alcance máximo) o motor do GDAL dá,
célula a célula, a altura mínima acima do terreno em que um alvo passa a ser visto, com a
curvatura da Terra e a refração de rádio (k = 0,25, a Terra de 4/3; ver refracao.py). A célula
tem cobertura do sensor quando a altitude pedida do alvo fica acima dessa altura mínima. As
coberturas dos sensores se somam: a saída raster dá o número de sensores por célula (0 = sem
cobertura) e a saída vetorial, os polígonos de cada contagem (a união é a área coberta).

Roda como algoritmo de Processing, em segundo plano, sem congelar a interface; o estilo das
duas saídas entra no fim, no fio principal, por pós-processador.
"""
import math
import os

from qgis.core import (
    QgsCategorizedSymbolRenderer, QgsCoordinateTransform, QgsFeatureRequest, QgsFillSymbol,
    QgsPalettedRasterRenderer, QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingLayerPostProcessorInterface, QgsProcessingParameterEnum, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber, QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer, QgsProcessingParameterVectorDestination, QgsRasterLayer,
    QgsRendererCategory, QgsVectorLayer, QgsWkbTypes,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QIcon

from . import nucleo
from .refracao import K_RADAR

#: Rampa das contagens (1, 2, 3, 4 ou mais sensores): azul claro ao azul-marinho.
CORES_CONTAGEM = ['#9ecae1', '#4292c6', '#2166ac', '#08306b']
REFERENCIAS = ['terreno', 'mar']
CAMPO_SAIDA = 'sensores'


def cor_da_contagem(n):
    return QColor(CORES_CONTAGEM[min(n, len(CORES_CONTAGEM)) - 1])


def rotulo_da_contagem(n, maximo):
    if n >= len(CORES_CONTAGEM) and maximo > len(CORES_CONTAGEM):
        return '{} sensores ou mais'.format(n)
    return '1 sensor' if n == 1 else '{} sensores'.format(n)


def estilizar_raster(camada, maximo=None):
    """Paleta da contagem: 0 transparente, 1 a 4 ou mais sensores em azul crescente."""
    if maximo is None:
        st = camada.dataProvider().bandStatistics(1)
        maximo = int(st.maximumValue) if st.maximumValue == st.maximumValue else 1
    classes = [QgsPalettedRasterRenderer.Class(0, QColor(0, 0, 0, 0), 'Sem cobertura')]
    for n in range(1, max(1, maximo) + 1):
        classes.append(QgsPalettedRasterRenderer.Class(n, cor_da_contagem(n), rotulo_da_contagem(n, maximo)))
    r = QgsPalettedRasterRenderer(camada.dataProvider(), 1, classes)
    r.setOpacity(0.7)
    camada.setRenderer(r)
    camada.triggerRepaint()


def estilizar_poligonos(camada):
    """Categorizado pelo número de sensores, preenchimento translúcido e borda da mesma cor."""
    idx = camada.fields().indexOf(CAMPO_SAIDA)
    valores = sorted(v for v in camada.uniqueValues(idx) if v is not None)
    maximo = max(valores) if valores else 1
    categorias = []
    for n in valores:
        c = cor_da_contagem(int(n))
        s = QgsFillSymbol.createSimple({
            'color': '{},{},{},110'.format(c.red(), c.green(), c.blue()),
            'outline_color': c.darker(130).name(), 'outline_width': '0.4'})
        categorias.append(QgsRendererCategory(n, s, rotulo_da_contagem(int(n), maximo)))
    camada.setRenderer(QgsCategorizedSymbolRenderer(CAMPO_SAIDA, categorias))
    camada.triggerRepaint()


class _Estilo(QgsProcessingLayerPostProcessorInterface):
    """Estiliza a saída quando o Processing a carrega no projeto (fio principal)."""

    vivos = []

    def __init__(self, tipo):
        super().__init__()
        self.tipo = tipo

    @classmethod
    def criar(cls, tipo):
        p = cls(tipo)
        cls.vivos.append(p)
        del cls.vivos[:-8]
        return p

    def postProcessLayer(self, layer, context, feedback):
        if self.tipo == 'raster' and isinstance(layer, QgsRasterLayer):
            estilizar_raster(layer)
        elif self.tipo == 'vetor' and isinstance(layer, QgsVectorLayer):
            estilizar_poligonos(layer)


class CoberturaRadar(QgsProcessingAlgorithm):
    MDE = 'MDE'
    SENSORES = 'SENSORES'
    ALTURA_ANTENA = 'ALTURA_ANTENA'
    CAMPO_ALTURA = 'CAMPO_ALTURA'
    ALCANCE = 'ALCANCE'
    CAMPO_ALCANCE = 'CAMPO_ALCANCE'
    ALTITUDE_ALVO = 'ALTITUDE_ALVO'
    REFERENCIA = 'REFERENCIA'
    RESOLUCAO = 'RESOLUCAO'
    SAIDA_RASTER = 'SAIDA_RASTER'
    SAIDA_POLIGONOS = 'SAIDA_POLIGONOS'

    def tr(self, texto):
        return QCoreApplication.translate('Processing', texto)

    def createInstance(self):
        return CoberturaRadar()

    def name(self):
        return 'coberturaradar'

    def displayName(self):
        return self.tr('Cobertura de radar ou sensor')

    def group(self):
        return self.tr('Vetor e Raster')

    def groupId(self):
        return 'vetoreraster'

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'icons', 'radar.svg'))

    def shortHelpString(self):
        return self.tr(
            'Calcula onde um alvo numa altitude fixa (aeronave, drone) é visto por um ou mais sensores '
            '(radar, sensor óptico ou de rádio) sobre um Modelo Digital de Elevação.\n\n'
            'Cada sensor é um ponto com a altura da antena acima do terreno e o alcance máximo; os dois '
            'podem vir de campos da camada ou valer para todos. A altitude do alvo é contada acima do '
            'terreno ou acima do nível do mar (a cota do MDE), à escolha.\n\n'
            'O cálculo considera a curvatura da Terra e a refração de rádio da atmosfera padrão '
            '(coeficiente 0,25, a Terra de 4/3 do raio, Recomendação ITU-R P.834). Sobre terreno plano, '
            'o alcance no horizonte vale cerca de 4,12 (√h + √H) km, com h a altura da antena e H a do '
            'alvo, em metros. Acima de 1 000 m o fator 4/3 é aproximação.\n\n'
            'MDE em graus é reprojetado para o UTM da área; a análise recorta o MDE ao alcance dos '
            'sensores. Sensor fora do MDE é erro.\n\n'
            'Saídas: raster com o número de sensores que cobrem cada célula (0 = sem cobertura) e '
            'polígonos de cada contagem, no campo "sensores".')

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.MDE, self.tr('Modelo Digital de Elevação (MDE)')))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.SENSORES, self.tr('Sensores (pontos)'), [QgsProcessing.SourceType.TypeVectorPoint]))
        self.addParameter(QgsProcessingParameterNumber(
            self.ALTURA_ANTENA, self.tr('Altura da antena acima do terreno (m)'),
            QgsProcessingParameterNumber.Type.Double, defaultValue=10.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterField(
            self.CAMPO_ALTURA, self.tr('Campo com a altura da antena (m), se variar por sensor'),
            parentLayerParameterName=self.SENSORES, type=QgsProcessingParameterField.DataType.Numeric,
            optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.ALCANCE, self.tr('Alcance máximo do sensor (km)'),
            QgsProcessingParameterNumber.Type.Double, defaultValue=30.0, minValue=0.001))
        self.addParameter(QgsProcessingParameterField(
            self.CAMPO_ALCANCE, self.tr('Campo com o alcance (km), se variar por sensor'),
            parentLayerParameterName=self.SENSORES, type=QgsProcessingParameterField.DataType.Numeric,
            optional=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.ALTITUDE_ALVO, self.tr('Altitude do alvo (m)'),
            QgsProcessingParameterNumber.Type.Double, defaultValue=150.0))
        self.addParameter(QgsProcessingParameterEnum(
            self.REFERENCIA, self.tr('A altitude do alvo é contada'),
            options=[self.tr('acima do terreno'), self.tr('acima do nível do mar (cota do MDE)')],
            defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUCAO, self.tr('Célula de cálculo (m); 0 usa a do MDE'),
            QgsProcessingParameterNumber.Type.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.SAIDA_RASTER, self.tr('Cobertura (sensores por célula)')))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.SAIDA_POLIGONOS, self.tr('Cobertura (polígonos)'), QgsProcessing.SourceType.TypeVectorPolygon))

    def _numero(self, valor, padrao, nome, i):
        if valor is None or valor == '':
            return padrao
        try:
            v = float(valor)
        except (TypeError, ValueError):
            raise QgsProcessingException(self.tr('O sensor {} tem {} inválido: {}.').format(i, nome, valor))
        if math.isnan(v):
            return padrao
        return v

    def processAlgorithm(self, parameters, context, feedback):
        mde = self.parameterAsRasterLayer(parameters, self.MDE, context)
        if mde is None:
            raise QgsProcessingException(self.tr('Escolha um MDE.'))
        if mde.providerType() != 'gdal':
            raise QgsProcessingException(self.tr('O MDE precisa ser um raster em arquivo lido pelo GDAL.'))
        fonte = self.parameterAsSource(parameters, self.SENSORES, context)
        if fonte is None:
            raise QgsProcessingException(self.tr('Escolha a camada de sensores.'))
        altura_padrao = self.parameterAsDouble(parameters, self.ALTURA_ANTENA, context)
        alcance_padrao = self.parameterAsDouble(parameters, self.ALCANCE, context)
        campo_altura = self.parameterAsString(parameters, self.CAMPO_ALTURA, context)
        campo_alcance = self.parameterAsString(parameters, self.CAMPO_ALCANCE, context)
        altitude = self.parameterAsDouble(parameters, self.ALTITUDE_ALVO, context)
        referencia = REFERENCIAS[self.parameterAsEnum(parameters, self.REFERENCIA, context)]
        resolucao = self.parameterAsDouble(parameters, self.RESOLUCAO, context) or None

        tr = QgsCoordinateTransform(fonte.sourceCrs(), mde.crs(), context.transformContext())
        sensores = []
        for i, f in enumerate(fonte.getFeatures(QgsFeatureRequest()), start=1):
            g = f.geometry()
            if g is None or g.isEmpty():
                feedback.pushWarning(self.tr('Sensor {} sem geometria: ignorado.').format(i))
                continue
            p = g.vertexAt(0) if QgsWkbTypes.isMultiType(g.wkbType()) else g.constGet()
            pt = tr.transform(p.x(), p.y())
            h = self._numero(f[campo_altura] if campo_altura else None, altura_padrao, 'altura', i)
            alc = self._numero(f[campo_alcance] if campo_alcance else None, alcance_padrao, 'alcance', i)
            sensores.append((pt.x(), pt.y(), h, alc * 1000.0))
        if not sensores:
            raise QgsProcessingException(self.tr('Não há sensor na camada de entrada.'))
        if altitude > 1000 or max(s[2] for s in sensores) > 1000:
            feedback.pushWarning(self.tr(
                'Altura acima de 1 000 m: o fator 4/3 da ITU-R P.834 vale abaixo disso; o resultado é aproximado.'))

        feedback.pushInfo(self.tr('{} sensor(es), alvo a {} m {}; refração de rádio k = {}.').format(
            len(sensores), altitude, 'acima do terreno' if referencia == 'terreno' else 'acima do nível do mar',
            K_RADAR))
        try:
            res = nucleo.cobertura(
                mde.source(), sensores, altitude, referencia, resolucao=resolucao,
                progresso=lambda p: feedback.setProgress(0.9 * p), cancelado=feedback.isCanceled)
        except nucleo.ErroVisada as e:
            raise QgsProcessingException(str(e))
        for a in res.avisos:
            feedback.pushWarning(a)
        if feedback.isCanceled():
            return {}

        import numpy as np
        from osgeo import gdal
        m = res.matriz
        area_celula = res.grade.resolucao[0] * res.grade.resolucao[1] / 1e6
        coberta = float((m > 0).sum() * area_celula)
        feedback.pushInfo(self.tr('SRC de cálculo: {}; célula de {:.1f} m; área coberta: {:.1f} km².').format(
            res.grade.srs.GetName(), res.grade.resolucao[0], coberta))
        maximo = int(m.max()) if m.size else 0

        saida_raster = self.parameterAsOutputLayer(parameters, self.SAIDA_RASTER, context)
        nucleo.salvar_geotiff(res.grade, m.astype(np.int16), saida_raster, gdal.GDT_Int16,
                              nucleo.SEM_DADO_CONTAGEM)
        saida_vetor = self.parameterAsOutputLayer(parameters, self.SAIDA_POLIGONOS, context)
        ext = os.path.splitext(saida_vetor)[1].lower()
        driver = {'.shp': 'ESRI Shapefile', '.geojson': 'GeoJSON', '.json': 'GeoJSON'}.get(ext, 'GPKG')
        if os.path.exists(saida_vetor):
            os.remove(saida_vetor)
        nucleo.poligonizar(res.grade, m, saida_vetor, CAMPO_SAIDA, 'cobertura', incluir=m > 0, formato=driver)
        feedback.setProgress(100)

        nome = self.tr('Cobertura de radar, alvo a {:g} m {}').format(
            altitude, 'acima do terreno' if referencia == 'terreno' else 'acima do nível do mar')
        for chave, saida, tipo, sufixo in ((self.SAIDA_RASTER, saida_raster, 'raster', ' (sensores por célula)'),
                                           (self.SAIDA_POLIGONOS, saida_vetor, 'vetor', '')):
            if context.willLoadLayerOnCompletion(saida):
                d = context.layerToLoadOnCompletionDetails(saida)
                d.name = nome + sufixo
                d.setPostProcessor(_Estilo.criar(tipo))
        return {self.SAIDA_RASTER: saida_raster, self.SAIDA_POLIGONOS: saida_vetor,
                'AREA_COBERTA_KM2': coberta, 'MAXIMO_SENSORES': maximo}
