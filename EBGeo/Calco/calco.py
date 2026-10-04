# -*- coding: utf-8 -*-
"""
O calco ativo no projeto: um GeoPackage com uma tabela por tipo militar,
carregado num grupo da árvore de camadas.
"""
import os

from qgis.core import QgsProject, QgsVectorLayer, QgsLayerTreeGroup

from . import schema, gpkg

PROP_CAMINHO = 'ebgeo_calco/caminho'
PROP_TIPO = 'ebgeo_calco/tipo'


def aplicar_estilo(layer, tipo):
    """Estilo do tipo: táticos e pontuais vêm dos módulos próprios; o resto, de estilos_formas."""
    try:
        if tipo in ('coordination_line', 'boundary', 'arrow', 'occupied_front'):
            from . import estilos_taticos as m
        elif schema.TIPOS[tipo]['desenho'] == 'svg':
            from . import estilos_pontuais as m
        else:
            from . import estilos_formas as m
    except Exception as e:  # módulo ausente ou com erro: a camada fica com o estilo padrão do QGIS
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage('Estilo de {} indisponível: {}'.format(tipo, e), 'EBGeo', Qgis.MessageLevel.Warning)
        return False
    m.aplicar_estilo(layer, tipo)
    if tipo in ('coordination_line', 'boundary', 'arrow', 'occupied_front'):
        # como nos pontuais: feição com "visivel" falso não é desenhada (o Web filtra igual)
        from .importador.arvore import condicao_exibir, esconder_por_regra
        esconder_por_regra(layer, condicao_exibir())
    return True


def salvar_estilo_padrao(layer):
    """Grava o estilo atual como padrão no layer_styles do GeoPackage."""
    try:
        res = layer.saveStyleToDatabaseV2(layer.name(), '', True, '')
        ok = res[0] if isinstance(res, tuple) else res
        return bool(ok == 0 or ok is True or getattr(ok, 'value', 1) == 0)
    except AttributeError:
        layer.saveStyleToDatabase(layer.name(), '', True, '')
        return True


class Calco:
    def __init__(self, caminho):
        self.caminho = os.path.abspath(caminho)

    @property
    def nome(self):
        return os.path.splitext(os.path.basename(self.caminho))[0]

    def criar(self):
        novo = not os.path.exists(self.caminho)
        gpkg.criar_calco(self.caminho, schema.TIPOS_MILITARES)
        return novo

    def camadas_no_projeto(self):
        """tipo -> QgsVectorLayer já carregada deste calco."""
        res = {}
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.customProperty(PROP_CAMINHO) == self.caminho:
                res[lyr.customProperty(PROP_TIPO)] = lyr
        return res

    def carregar(self, estilizar_novas=True):
        """Carrega no projeto as tabelas militares que faltarem, num grupo com o nome do calco."""
        proj = QgsProject.instance()
        raiz = proj.layerTreeRoot()
        grupo = raiz.findGroup('Calco: ' + self.nome)
        if grupo is None:
            grupo = raiz.insertGroup(0, 'Calco: ' + self.nome)
        existentes = self.camadas_no_projeto()
        # de cima para baixo na árvore = inverso da pilha de desenho
        ordem = [t for t in reversed(schema.PILHA_DESENHO) if t in schema.TIPOS_MILITARES]
        for tipo in ordem:
            if tipo in existentes:
                continue
            lyr = QgsVectorLayer(gpkg.uri_camada(self.caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
            if not lyr.isValid():
                continue
            lyr.setCustomProperty(PROP_CAMINHO, self.caminho)
            lyr.setCustomProperty(PROP_TIPO, tipo)
            # o estilo padrão gravado no GeoPackage já vem carregado; só estiliza se não houver
            if estilizar_novas and not self._tem_estilo_padrao(lyr):
                if aplicar_estilo(lyr, tipo):
                    salvar_estilo_padrao(lyr)
            proj.addMapLayer(lyr, False)
            grupo.addLayer(lyr)
        return self.camadas_no_projeto()

    @staticmethod
    def _tem_estilo_padrao(lyr):
        try:
            n, ids, nomes, descs, msg = lyr.listStylesInDatabase()
            return n > 0
        except Exception:
            return False

    def camada(self, tipo):
        camadas = self.camadas_no_projeto()
        if tipo not in camadas:
            camadas = self.carregar()
        return camadas.get(tipo)


def calco_ativo():
    caminho = QgsProject.instance().readEntry('ebgeo_calco', 'ativo', '')[0]
    if caminho and os.path.exists(caminho):
        return Calco(caminho)
    # sem registro: o primeiro calco carregado no projeto
    for lyr in QgsProject.instance().mapLayers().values():
        c = lyr.customProperty(PROP_CAMINHO)
        if c and os.path.exists(c):
            return Calco(c)
    return None


def definir_calco_ativo(calco):
    QgsProject.instance().writeEntry('ebgeo_calco', 'ativo', calco.caminho if calco else '')


def tipo_da_camada(layer):
    if layer is None or not isinstance(layer, QgsVectorLayer):
        return None
    t = layer.customProperty(PROP_TIPO)
    if t:
        return t
    # camada aberta à mão: reconhece pela tabela do GeoPackage
    src = layer.source()
    if 'layername=' in src:
        tabela = src.split('layername=')[1].split('|')[0]
        for tipo, d in schema.TIPOS.items():
            if d['tabela'] == tabela:
                return tipo
    return None
