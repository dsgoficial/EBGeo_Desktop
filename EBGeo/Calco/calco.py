# -*- coding: utf-8 -*-
"""
O calco ativo no projeto: um GeoPackage com uma tabela por tipo militar,
carregado num grupo da árvore de camadas.
"""
import os

from qgis.core import QgsProject, QgsVectorLayer

from . import schema, gpkg

PROP_CAMINHO = 'ebgeo_calco/caminho'
PROP_TIPO = 'ebgeo_calco/tipo'
# Tabelas comuns que a ferramenta Azimute e Distância (Calco/azimute) cria no calco sob demanda.
TIPOS_AZIMUTE = ('point', 'line', 'polygon')


def aplicar_estilo(layer, tipo):
    """Estilo do tipo: táticos e pontuais vêm dos módulos próprios; o resto, de estilos_formas."""
    try:
        if tipo in ('coordination_line', 'boundary', 'arrow', 'occupied_front'):
            from . import estilos_taticos as m
        elif tipo == 'coordination_area':
            from . import estilos_area as m
        elif schema.TIPOS[tipo]['desenho'] == 'svg':
            from . import estilos_pontuais as m
        else:
            from . import estilos_formas as m
    except Exception as e:  # módulo ausente ou com erro: a camada fica com o estilo padrão do QGIS
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage('Estilo de {} indisponível: {}'.format(tipo, e), 'EBGeo', Qgis.MessageLevel.Warning)
        return False
    m.aplicar_estilo(layer, tipo)
    if tipo in ('coordination_line', 'boundary', 'arrow', 'occupied_front', 'coordination_area'):
        # como nos pontuais: feição com "visivel" falso não é desenhada (o Web filtra igual)
        from .importador.arvore import condicao_exibir, esconder_por_regra
        esconder_por_regra(layer, condicao_exibir())
    aplicar_formulario(layer, tipo)
    return True


def aplicar_formulario(layer, tipo):
    """O formulário nativo do tipo (formulario/nativo.py), quando ele já tem especificação."""
    try:
        from .formulario.nativo import aplicar_formulario as aplicar
        return aplicar(layer, tipo)
    except Exception as e:  # formulário com defeito não impede a camada de desenhar
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage('Formulário de {} indisponível: {}'.format(tipo, e), 'EBGeo', Qgis.MessageLevel.Warning)
        return False


def salvar_estilo_padrao(layer, descricao=None):
    """
    Grava o estilo atual como padrão no layer_styles do GeoPackage, provado por gravar_estilo. A
    descrição leva a marca do plugin e a impressão digital do estilo (descricao_estilo), que o
    carregar compara depois. Devolve False, com o erro no log do EBGeo, se o arquivo não o guardou.
    """
    descricao = descricao_estilo(layer) if descricao is None else descricao
    try:
        return gravar_estilo(layer, layer.name(), descricao)[0]
    except EstiloNaoGravado as e:
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(str(e), 'EBGeo', Qgis.MessageLevel.Critical)
        return False


# ---------------------------------------------------------------------------------------------
# Prova da escrita do estilo
#
# O saveStyleToDatabaseV2 diz sucesso pelo que mandou gravar, não pelo que o arquivo guardou: o
# OGR guarda o texto até o primeiro caractere nulo, e um estilo com nulo na memória saía cortado
# com o salvar dizendo sucesso (medido em 2026-10-05, o Ponto com 77 mil de 198 mil caracteres;
# a causa era a do esconder_por_regra, no importador). Toda gravação de estilo do plugin passa
# por gravar_estilo, que relê o styleQML e o compara com o QML que a camada exporta, o mesmo que
# o QGIS manda gravar (medido igual caractere a caractere).
# ---------------------------------------------------------------------------------------------

class EstiloNaoGravado(RuntimeError):
    """O layer_styles não guardou o estilo que se quis gravar."""


def qml_do_estilo(layer):
    """O QML que o saveStyleToDatabaseV2 manda gravar (todas as categorias)."""
    from qgis.core import QgsMapLayer, QgsReadWriteContext
    from qgis.PyQt.QtXml import QDomDocument
    doc = QDomDocument()
    layer.exportNamedStyle(doc, QgsReadWriteContext(), QgsMapLayer.StyleCategory.AllStyleCategories)
    return doc.toString()


def _arquivo_e_tabela(layer):
    from qgis.core import QgsProviderRegistry
    partes = QgsProviderRegistry.instance().decodeUri(layer.providerType(), layer.source())
    caminho = partes.get('path') or ''
    return (caminho, partes.get('layerName') or '') if os.path.isfile(caminho) else (None, None)


def estilo_gravado(caminho, tabela, nome):
    """O styleQML do estilo `nome` da tabela no layer_styles, relido pelo OGR ('' se não há)."""
    from osgeo import ogr
    ds = ogr.Open(caminho)
    if ds is None or ds.GetLayerByName('layer_styles') is None:
        return ''
    try:
        sql = ("SELECT styleQML FROM layer_styles WHERE f_table_name = '{}' AND styleName = '{}' "
               "ORDER BY update_time DESC LIMIT 1").format(tabela.replace("'", "''"), nome.replace("'", "''"))
        res = ds.ExecuteSQL(sql)
        try:
            f = res.GetNextFeature() if res is not None else None
            return (f.GetField(0) or '') if f is not None else ''
        finally:
            if res is not None:
                ds.ReleaseResultSet(res)
    finally:
        ds = None


def _salvar_no_banco(layer, nome, descricao):
    """saveStyleToDatabaseV2 como padrão; devolve a mensagem de falha que o QGIS acusar ('' sem)."""
    from qgis.core import QgsMapLayer
    if not hasattr(layer, 'saveStyleToDatabaseV2'):
        return layer.saveStyleToDatabase(nome, descricao, True, '') or ''
    res, msg = layer.saveStyleToDatabaseV2(nome, descricao, True, '')
    valor = res.value if hasattr(res, 'value') else int(res)
    # o SLD é cópia de cortesia e não exprime o Geometry Generator: só QML e banco contam
    falhas = [n for n in ('QmlGenerationFailed', 'DatabaseWriteFailed')
              if valor & getattr(QgsMapLayer.SaveStyleResult, n).value]
    return '{}: {}'.format(', '.join(falhas), msg) if falhas else ''


def gravar_estilo(layer, nome, descricao, tentativas=2):
    """
    Grava o estilo atual como padrão da tabela e PROVA a escrita: relê o styleQML no arquivo e o
    compara com o QML que se quis gravar. Divergiu, regrava; persistiu, EstiloNaoGravado. Camada
    que não é de arquivo não tem o que reler e devolve o que o QGIS disse. Devolve (True, '').
    """
    quis = qml_do_estilo(layer)
    if '\x00' in quis:
        raise EstiloNaoGravado('o estilo de {} tem caractere nulo na memória, na posição {}: o GeoPackage '
                               'o guardaria cortado ali'.format(layer.name(), quis.index('\x00')))
    caminho, tabela = _arquivo_e_tabela(layer)
    msg = ''
    for _ in range(max(1, tentativas)):
        msg = _salvar_no_banco(layer, nome, descricao)
        if caminho is None:
            return not msg, msg
        relido = estilo_gravado(caminho, tabela, nome)
        if relido == quis:
            return True, ''
    raise EstiloNaoGravado(
        'o layer_styles de {} não guardou o estilo de {}: {} caracteres relidos de {} gravados{}'.format(
            os.path.basename(caminho), tabela, len(relido), len(quis), ' ({})'.format(msg) if msg else ''))


# ---------------------------------------------------------------------------------------------
# Versão do estilo padrão gravado no GeoPackage
#
# O estilo que o plugin grava no layer_styles é o que desenha o calco num QGIS sem o plugin, e
# fica velho quando o código dos estilos muda (uma coluna nova na assinatura do símbolo, um
# glifo novo de linha ou de área). A descrição do estilo gravado leva MARCA_ESTILO e a impressão
# digital do estilo que o código gerou; ao abrir o calco, o estilo do plugin de impressão
# diferente é refeito e regravado. A impressão sai do próprio estilo gerado (QML de simbologia e
# rótulos sem os identificadores aleatórios), então qualquer mudança de código a renova, sem
# número de versão para lembrar de subir. Estilo que não é do plugin fica intocado.
# ---------------------------------------------------------------------------------------------

MARCA_ESTILO = 'EBGeo Desktop: estilo do calco'
# O que o plugin gravava antes da marca: o calco novo (descrição vazia, que o QGIS troca pela
# data da gravação, ex. 'Sun Oct 4 21:12:38 2026'), o importador e as funções de estilo dos módulos.
DESCRICOES_ANTIGAS = ('', 'EBGeo Desktop: estilo do tipo', 'Estilo do calco EBGeo (abre sem o plugin)',
                      'Estilo tático do EBGeo Desktop')
DATA_DO_QGIS = r'^[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}$'


def impressao_estilo(layer):
    """
    md5 curto da simbologia, dos rótulos e do formulário da camada (campos, formulário, tabela de
    atributos e ações), sem as chaves aleatórias de regra e camada. O formulário entra para que
    formulário mudado no código também regrave o estilo do calco antigo ao abrir.
    """
    import hashlib
    import re
    from qgis.core import QgsMapLayer, QgsReadWriteContext
    from qgis.PyQt.QtXml import QDomDocument
    doc = QDomDocument()
    C = QgsMapLayer.StyleCategory
    layer.exportNamedStyle(doc, QgsReadWriteContext(),
                           C.Symbology | C.Labeling | C.Fields | C.Forms | C.AttributeTable | C.Actions)
    # também o id escapado do símbolo que o rótulo guarda como texto (lineSymbol do callout), que
    # mudava a cada montagem e impedia o "em dia" da Linha de Coordenação (medido em 2026-10-05)
    texto = re.sub(r' (?:key|id)=(?:"|&quot;)\{[0-9a-fA-F-]{36}\}(?:"|&quot;)', '', doc.toString())
    return hashlib.md5(texto.encode('utf-8')).hexdigest()[:12]


def descricao_estilo(layer):
    return '{} [{}]'.format(MARCA_ESTILO, impressao_estilo(layer))


def estilo_padrao_salvo(caminho, tabela):
    """{'nome', 'descricao', 'qml'} do estilo padrão da tabela no layer_styles, ou None."""
    from osgeo import ogr
    ds = ogr.Open(caminho)
    if ds is None or ds.GetLayerByName('layer_styles') is None:
        return None
    try:
        sql = ("SELECT styleName, description, styleQML FROM layer_styles WHERE f_table_name = '{}' "
               "ORDER BY useAsDefault DESC, update_time DESC LIMIT 1").format(tabela.replace("'", "''"))
        res = ds.ExecuteSQL(sql)
        try:
            f = res.GetNextFeature() if res is not None else None
            if f is None:
                return None
            return {'nome': f.GetField(0) or '', 'descricao': f.GetField(1) or '', 'qml': f.GetField(2) or ''}
        finally:
            if res is not None:
                ds.ReleaseResultSet(res)
    finally:
        ds = None


def estilo_e_do_plugin(salvo, tipo):
    """
    O estilo gravado é do plugin: tem a marca, ou é um dos que o plugin gravava antes dela (nome
    da camada ou da tabela, descrição conhecida e a regra de visibilidade que todo estilo do
    plugin traz). Outro nome, outra descrição ou sem a regra: estilo do operador.
    """
    if salvo['descricao'].startswith(MARCA_ESTILO):
        return True
    import re
    d = schema.TIPOS[tipo]
    antiga = salvo['descricao'] in DESCRICOES_ANTIGAS or re.match(DATA_DO_QGIS, salvo['descricao'])
    if not antiga or salvo['nome'] not in (d['nome_pt'], d['tabela'], 'EBGeo calco'):
        return False
    return 'visivel' in salvo['qml']


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
        # mais as tabelas do Azimute e Distância (ponto, linha, polígono), quando o calco já as tem
        presentes = set(gpkg.tabelas_presentes(self.caminho)) if os.path.exists(self.caminho) else set()
        ordem = [t for t in reversed(schema.PILHA_DESENHO) if t in schema.TIPOS_MILITARES
                 or (t in TIPOS_AZIMUTE and schema.TIPOS[t]['tabela'] in presentes)]
        self.estilos = {}
        for tipo in ordem:
            if tipo in existentes:
                # Já no projeto: o estilo só é refeito se a camada ainda desenha com o que está
                # gravado (o operador não o mudou no projeto).
                if estilizar_novas:
                    self.estilos[tipo] = self.atualizar_estilo(existentes[tipo], tipo, so_se_igual_ao_salvo=True)
                continue
            lyr = QgsVectorLayer(gpkg.uri_camada(self.caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
            if not lyr.isValid():
                continue
            lyr.setCustomProperty(PROP_CAMINHO, self.caminho)
            lyr.setCustomProperty(PROP_TIPO, tipo)
            # o estilo padrão gravado no GeoPackage já vem carregado; estiliza se não houver ou
            # se o gravado for do plugin e de outro código
            if estilizar_novas:
                self.estilos[tipo] = self.atualizar_estilo(lyr, tipo)
            proj.addMapLayer(lyr, False)
            grupo.addLayer(lyr)
        return self.camadas_no_projeto()

    def atualizar_estilo(self, lyr, tipo, so_se_igual_ao_salvo=False):
        """
        Põe na camada o estilo do código atual e o grava como padrão, salvo quando o estilo
        gravado é do operador. Devolve 'novo', 'atualizado', 'em dia', 'personalizado',
        'mudado no projeto' ou 'falhou'.
        """
        salvo = estilo_padrao_salvo(self.caminho, schema.TIPOS[tipo]['tabela'])
        if salvo is not None and not estilo_e_do_plugin(salvo, tipo):
            return 'personalizado'
        if so_se_igual_ao_salvo and salvo is not None:
            gravado = QgsVectorLayer(lyr.source(), 'estilo gravado', 'ogr')
            if gravado.isValid() and impressao_estilo(gravado) != impressao_estilo(lyr):
                return 'mudado no projeto'
        if not aplicar_estilo(lyr, tipo):
            return 'falhou'
        descricao = descricao_estilo(lyr)
        if salvo is not None and salvo['descricao'] == descricao:
            return 'em dia'
        salvar_estilo_padrao(lyr, descricao)
        return 'novo' if salvo is None else 'atualizado'

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
