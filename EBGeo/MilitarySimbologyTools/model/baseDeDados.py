#! -*- coding: UTF-8 -*-
from qgis.PyQt.QtCore import QObject
from qgis.PyQt.QtSql import QSqlDatabase
from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsProject, QgsProjectBadLayerHandler, QgsVectorFileWriter, QgsLayerTreeNode
from qgis.utils import iface
import os, re
import processing
from osgeo import ogr, gdal

class BaseDeDados(QObject):
    def __init__(self):
        super(BaseDeDados, self).__init__()
        self.initVariables()

    def initVariables(self):
        self.listName = {
            'coord_ap_fogo': u'Coordenação de Apoio de Fogo',
            'eixo_de_direcao': u'Eixo de direcao',
            'fortificacoes_pf': u'Fortificações - Pontos Fortes',
            'limite_entre_fracoes': u'Limite entre frações',
            'linha_de_controle': u'Linha de controle',
            'seta_situacao': u'Seta de situação',
            'simbolos_pontos': u'Símbolos (pontos)',
            'barragem_grupo_concentracao': u'Barragem e Grupo de Concentração',
            'barreiras': u'Barreiras',
            'redes': u'Redes',
            'fortificacoes_ot': u'Fortificações - Outras Tropas',
            'obstaculos': u'Obstáculos',
        }
        self.Database = None

    def checkTableFromDatabase(self, tablename):
        allTables = [l.GetName() for l in ogr.Open(self.Database)]
        if tablename in allTables:
            layer = QgsVectorLayer(self.Database + "|layername=" + tablename, '', 'ogr')
            attrList = []
            for i in layer.getFeatures():
                attrList.append(i[0])
        else:
            attrList = ['table not available']
        return attrList

    def setCurrentDatabase(self, pathDatabase):
        pathDatabase.replace('\\','/')
        self.Database =  pathDatabase

    def getListDataBaseLayerNameOfTemplate(self):
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_template = os.path.join(caminho_atual, 'templates', 'dataBase.gpkg')

        ds = ogr.Open(pasta_template)

        listOfNames = [l.GetName() for l in ds]
        ds = None  # Liberar recursos
            
        # Filtrar quaisquer nomes vazios ou None
        listOfNames = [name for name in listOfNames if name]

        return listOfNames

    def getDataBaseLayerName(self):
        """
        Obtém todos os nomes de camadas do banco de dados GeoPackage.
        Retorna apenas os nomes técnicos internos, não os nomes de exibição.
        
        Returns:
            list: Lista com os nomes de todas as camadas no banco de dados.
        """
        try:
            if not self.Database or not os.path.exists(self.Database):
                print(f"Erro: O banco de dados não existe: {self.Database}")
                return []
                
            # Usar OGR para obter os nomes das camadas
            ds = ogr.Open(self.Database)
            if ds is None:
                print(f"Erro: Não foi possível abrir o banco de dados: {self.Database}")
                return []
                
            # Obter apenas os nomes internos das camadas (não os nomes de exibição)
            listOfNames = [l.GetName() for l in ds]
            ds = None  # Liberar recursos
            
            # Filtrar quaisquer nomes vazios ou None
            listOfNames = [name for name in listOfNames if name]
            
            print(f"Camadas brutas encontradas no GeoPackage: {listOfNames}")
            return listOfNames
        except Exception as e:
            print(f"Erro no getDataBaseLayerName: {str(e)}")
            return []

    def getTemplateDatabase(self):
        path  = os.path.join(os.path.dirname(__file__), 'templates', 'dataBase.gpkg')
        return path

    def createDataBase(self, path):
        f = open(self.getTemplateDatabase(),'rb')
        g = open(path,'wb')
        x = f.readline()
        while x:
            g.write(x)
            x = f.readline()
        g.close()

    def loadDatabase(self):
        projects = self.checkTableFromDatabase('qgis_projects')
        if projects[0] == 'table not available':
            return self.loadSymbLayers()
        else:
            return self.loadProject()

    def loadProject(self):
        file_path = self.Database.replace('\\','/')
        gpkgname = file_path.split('/')[-1]

        projectList = self.checkTableFromDatabase('qgis_projects')
        projectName = projectList[0]

        tempProject = QgsProject.instance()
        tempProject.setBadLayerHandler(QgsProjectBadLayerHandler())
        tempProject.read('geopackage:' + file_path + '?projectName=' + projectName)

        layersList = QgsProject.instance().mapLayers()
        for layer_id in layersList:
            layer = QgsProject.instance().mapLayer(layer_id)
            layerPath = layer.dataProvider().dataSourceUri()

            if gpkgname in layerPath:
                if layer.providerType() == 'gdal':
                    if layerPath.endswith('.gpkg'):
                        newPath = file_path
                    else:
                        newPath = layerPath.replace(layerPath[:layerPath.rfind(':')], 'GPKG:' + file_path)
                else:
                    newPath = layerPath.replace(layerPath[:layerPath.find('|')], file_path)

                layer.dataProvider().setDataSourceUri(newPath)
                layer.setDataSource(newPath, layer.name(), layer.providerType(), layer.dataProvider().ProviderOptions())

        QgsProject.instance().write('geopackage:' + file_path + '?projectName=' + projectName)
        return 2

    def getLayerList(self):
        """
        Versão filtrada que exclui camadas indesejadas
        """
        try:
            if not self.Database or not os.path.exists(self.Database):
                print(f"Erro: O banco de dados não existe: {self.Database}")
                return []

            # Usar OGR para obter os nomes das camadas
            ds = ogr.Open(self.Database)
            if ds is None:
                print(f"Erro: Não foi possível abrir o banco de dados: {self.Database}")
                return []

            # Obter todos os nomes das camadas
            all_layer_names = [l.GetName() for l in ds]
            ds = None  # Liberar recursos

            print(f"Todas as camadas encontradas no geopackage: {all_layer_names}")

            # Lista de tabelas do sistema que devem ser excluídas
            system_tables = {
                'gpkg_contents', 'gpkg_geometry_columns', 'gpkg_spatial_ref_sys', 
                'gpkg_tile_matrix', 'gpkg_tile_matrix_set', 'gpkg_extensions',
                'metadata', 'layer_styles', 'qgis_projects', 'sqlite_sequence'
            }

            # Filtrar apenas tabelas do sistema conhecidas
            valid_layers = []
            for name in all_layer_names:
                # Verificar se é exatamente uma tabela do sistema
                if name in system_tables:
                    print(f"Excluindo tabela do sistema: {name}")
                    continue
                
                # Verificar prefixos problemáticos
                if name.startswith(('rtree_', 'idx_', 'trigger_')):
                    print(f"Excluindo tabela com prefixo de sistema: {name}")
                    continue
                
                # Filtrar nomes vazios ou None
                if not name or name.strip() == '':
                    continue
                
                # Se chegou até aqui, é uma camada válida
                valid_layers.append(name)
                print(f"Incluindo camada válida: {name}")

            # FILTRO REMOVIDO: Não remover mais as camadas "outras"
            # As camadas barragem_grupo_concentracao, barreiras, redes, fortificacoes_ot
            # agora são incluídas normalmente

            print(f"Camadas finais válidas para seleção: {valid_layers}")
            return valid_layers

        except Exception as e:
            print(f"Erro no getLayerList: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def getRasterLayerList(self):
        """
        Retorna uma lista com os nomes das camadas raster disponíveis no banco de dados.
        
        Returns:
            list: Lista de nomes de camadas raster disponíveis.
        """
        
        raster_names = []
        
        # Verificar se o atributo Database está definido
        if not hasattr(self, 'Database') or not self.Database:
            return raster_names
        
        try:
            # Obter informações sobre camadas raster no banco de dados
            raster_info = gdal.Info(self.Database)
            
            if not raster_info:
                return raster_names
            
            # Tentar encontrar camadas raster no formato GPKG:caminho:nome
            raster_layers = re.findall("GPKG:.*", raster_info)
            
            if not raster_layers:
                # Tentar o formato alternativo com IDENTIFIER
                raster_layers = re.findall("IDENTIFIER=.*", raster_info)
                if raster_layers:
                    raster_layer = raster_layers[0].replace('IDENTIFIER=', '')
                    raster_names.append('raster_' + raster_layer)
            else:
                # Processar cada camada raster encontrada
                for raster in raster_layers:
                    raster_name = raster[raster.rfind(':') + 1:]
                    raster_names.append('raster_' + raster_name)
            
            return raster_names
        except Exception as e:
            print(f"Erro ao obter lista de camadas raster: {str(e)}")
            return []

    def getTemplateLayerList(self):
        """Retorna a lista de camadas disponíveis no template, filtrada"""        
        try:
            # Método original: usar listName para obter as camadas
            available_layers = list(self.listName.keys())

            print(f"Template - Camadas antes do filtro: {available_layers}")

            return available_layers

        except Exception as e:
            print(f"Erro ao obter lista de camadas do template: {str(e)}")
            # Lista de emergência (já sem as excluídas)
            return [
                'coord_ap_fogo', 
                'eixo_de_direcao', 
                'fortificacoes_pf',
                'limite_entre_fracoes',
                'linha_de_controle',
                'seta_situacao',
                'simbolos_pontos',
                'barragem_grupo_concentracao',
                'barreiras',
                'redes',
                'fortificacao_ot'
            ]
        
    def layerNotSelected(self, selectedLayers, listName):
        listLayersNotSelected = []
        for name in listName:
            if name in selectedLayers:
                continue
            listLayersNotSelected.append(name)
        return listLayersNotSelected
    
    def removeLayersOfGeopackage(self, pathGeopackage, layerName):
        driver = ogr.GetDriverByName('GPKG')
        datasource = driver.Open(pathGeopackage, 1)

        if datasource is None:
            print('Não foi possivel abrir o arquivo')
            return False
        
        layer_exists = False
        for i in range(datasource.GetLayerCount()):
            if datasource.GetLayerByIndex(i).GetName() != layerName:
                continue
            layer_exists = True
            break

        if not layer_exists:
            print(f"A camada {layerName} não existe no Geopackage")
            datasource = None
            return False
        
        result = datasource.DeleteLayer(datasource.GetLayerByName(layerName).GetLayerDefn().GetName())

        # Fechar o datasource e liberar recursos
        datasource = None

        if result == 0:
            print(f"Camada '{layerName}' removida com sucesso!")
            return True
        else:
            print(f"Erro ao remover a camada '{layerName}'")
            return False
        
    def loadSelectedLayersWithDuplicates(self, selected_layers, duplicate_info=None, existing_geopackage=False):
        """
        Versão corrigida que salva fisicamente as camadas duplicadas no geopackage
        E agora também renomeia fisicamente as camadas originais quando renomeadas
        """
        print(f"=== CARREGANDO CAMADAS COM DUPLICATAS FÍSICAS ===")
        print(f"Camadas selecionadas: {selected_layers}")
        print(f"É geopackage existente: {existing_geopackage}")
        print(f"Info de duplicatas: {duplicate_info}")

        fileNameFull = self.Database
        fileName = fileNameFull.split('/')[-1].split('.')[0]
        dictLayerAndYourName = dict()  # APENAS para camadas normais
        root = QgsProject.instance().layerTreeRoot()
        self.groupMain = root.insertGroup(0, fileName)

        # Lista de tabelas de sistema que NUNCA devem ser carregadas
        system_tables = {'metadata', 'layer_styles', 'qgis_projects', 'gpkg_contents', 
                         'gpkg_geometry_columns', 'gpkg_spatial_ref_sys', 'gpkg_tile_matrix',
                         'gpkg_tile_matrix_set', 'gpkg_extensions', 'sqlite_sequence'}

        if duplicate_info is None:
            duplicate_info = {}

        # FUNÇÃO AUXILIAR para identificar camadas "outras"
        def is_outras_camada(layer_name):
            """Verifica se uma camada é do tipo 'outras' - VERSÃO MAIS ROBUSTA"""
            print(f"Verificando se '{layer_name}' é camada 'outras'...")

            # 1. NOMES TÉCNICOS ORIGINAIS (como aparecem no template)
            nomes_tecnicos = [
                'barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot'
            ]

            # 2. NOMES DE EXIBIÇÃO (como podem aparecer no geopackage)
            nomes_exibicao = [
                'Barragem e Grupo de Concentração', 'Barreiras', 'Redes', 
                'Fortificações - Outras Tropas', 'Fortificacoes - Outras Tropas'
            ]

            # 3. PALAVRAS-CHAVE para identificação flexível
            palavras_chave = [
                'barragem', 'grupo', 'concentracao', 'concentração',
                'barreiras', 'redes', 'fortificacoes_ot', 'outras tropas'
            ]

            # Converter para minúsculas para comparação
            layer_lower = layer_name.lower()

            # VERIFICAÇÃO 1: Nome exato (técnico)
            if layer_name in nomes_tecnicos:
                print(f"  ✓ Identificada por nome técnico: {layer_name}")
                return True

            # VERIFICAÇÃO 2: Nome de exibição exato
            if layer_name in nomes_exibicao:
                print(f"  ✓ Identificada por nome de exibição: {layer_name}")
                return True

            # VERIFICAÇÃO 3: Contém palavra-chave
            for palavra in palavras_chave:
                if palavra.lower() in layer_lower:
                    print(f"  ✓ Identificada por palavra-chave '{palavra}': {layer_name}")
                    return True

            # VERIFICAÇÃO 4: Começa com algum dos nomes técnicos (para duplicatas numeradas)
            for nome_tecnico in nomes_tecnicos:
                if layer_name.startswith(nome_tecnico):
                    print(f"  ✓ Identificada por prefixo '{nome_tecnico}': {layer_name}")
                    return True

            # VERIFICAÇÃO 5: Padrões específicos conhecidos
            padroes_especiais = [
                'barragem_grupo_concentracao_', 'barreiras_', 'redes_', 'fortificacoes_ot_'
            ]

            for padrao in padroes_especiais:
                if padrao in layer_name:
                    print(f"  ✓ Identificada por padrão '{padrao}': {layer_name}")
                    return True

            print(f"  ✗ NÃO identificada como 'outras': {layer_name}")
            return False

        if existing_geopackage:
            print("Carregando camadas de geopackage existente...")

            # Obter lista real de camadas no arquivo
            ds = ogr.Open(fileNameFull)
            if ds:
                actual_layers_in_file = [l.GetName() for l in ds]
                print(f"Camadas disponíveis no arquivo: {actual_layers_in_file}")
                ds = None
            else:
                print("ERRO: Não foi possível abrir o arquivo!")
                return 0

            # Filtrar camadas de sistema
            available_layers = [layer for layer in actual_layers_in_file 
                               if layer not in system_tables and 
                               not any(layer.startswith(prefix) for prefix in ['rtree_', 'idx_', 'trigger_'])]

            # FUNÇÃO AUXILIAR LOCAL para identificar camadas "outras"
            def verificar_se_e_outras(layer_name):
                """Verifica se uma camada é do tipo 'outras'"""
                print(f"Verificando: {layer_name}")

                # Lista de identificadores para camadas "outras"
                identificadores_outras = [
                    # Nomes técnicos exatos
                    'barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot', 'drenagem',
                    # Nomes de exibição
                    'Barragem e Grupo de Concentração', 'Barreiras', 'Redes', 'Fortificações - Outras Tropas', 'Drenagem',
                    # Variações sem acentos
                    'Fortificacoes - Outras Tropas'
                ]

                # Palavras-chave para busca flexível
                palavras_chave_outras = ['barragem', 'barreiras', 'redes', 'drenagem', 'outras tropas']

                # Verificação 1: Nome exato
                if layer_name in identificadores_outras:
                    print(f"  ✓ Identificada como OUTRAS (nome exato): {layer_name}")
                    return True

                # Verificação 2: Contém palavra-chave
                layer_lower = layer_name.lower()
                for palavra in palavras_chave_outras:
                    if palavra in layer_lower:
                        print(f"  ✓ Identificada como OUTRAS (palavra-chave '{palavra}'): {layer_name}")
                        return True

                # Verificação 3: Começa com nome técnico (para duplicatas)
                nomes_tecnicos = ['barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot', 'drenagem']
                for nome_tecnico in nomes_tecnicos:
                    if layer_name.startswith(nome_tecnico):
                        print(f"  ✓ Identificada como OUTRAS (prefixo '{nome_tecnico}'): {layer_name}")
                        return True

                print(f"  → Identificada como NORMAL: {layer_name}")
                return False

            # SEPARAR camadas "outras" das demais ANTES de carregar
            outras_camadas = []
            camadas_normais = []

            print(f"\n=== SEPARANDO CAMADAS ===")
            for selected_name in selected_layers:
                if selected_name.startswith('raster_'):
                    continue  # Processar rasters separadamente
                
                if selected_name in available_layers:
                    # Usar função local para identificação
                    if verificar_se_e_outras(selected_name):
                        outras_camadas.append(selected_name)
                    else:
                        camadas_normais.append(selected_name)
                else:
                    print(f"  ⚠ Camada não encontrada: {selected_name}")

            print(f"\nRESULTADO DA SEPARAÇÃO:")
            print(f"  Camadas normais ({len(camadas_normais)}): {camadas_normais}")
            print(f"  Outras camadas ({len(outras_camadas)}): {outras_camadas}")

            # 1. CARREGAR CAMADAS NORMAIS no grupo principal
            if camadas_normais:
                print(f"\n--- CARREGANDO {len(camadas_normais)} CAMADAS NORMAIS ---")
                for selected_name in camadas_normais:
                    print(f"Carregando camada normal: {selected_name}")

                    original_type_for_style = selected_name

                    # Determinar nome de exibição
                    if selected_name in duplicate_info:
                        info = duplicate_info[selected_name]
                        display_name = info.get('custom_name', selected_name)
                        if 'original_layer' in info:
                            original_type_for_style = info['original_layer']
                    else:
                        display_name = self.listName.get(selected_name, selected_name)

                    layer = QgsVectorLayer(self.Database + "|layername=" + selected_name, display_name, 'ogr')

                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer, False)
                        # IMPORTANTE: Adicionar ao dictLayerAndYourName APENAS se for camada normal
                        dictLayerAndYourName[layer.name()] = layer

                        self.applyStyleToLayer(layer, original_type_for_style)
                        print(f"  ✓ Carregada normal: {display_name}")
                    else:
                        print(f"  ✗ ERRO ao carregar: {selected_name}")

            # 2. CARREGAR CAMADAS "OUTRAS" em grupo separado
            if outras_camadas:
                print(f"\n--- CARREGANDO {len(outras_camadas)} OUTRAS CAMADAS ---")
                print("Criando grupo OUTRAS CAMADAS...")
                outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')

                for selected_name in outras_camadas:
                    print(f"Carregando camada 'outras': {selected_name}")

                    original_type_for_style = selected_name

                    # Determinar nome de exibição
                    if selected_name in duplicate_info:
                        info = duplicate_info[selected_name]
                        display_name = info.get('custom_name', selected_name)

                        if 'original_layer' in info:
                            original_type_for_style = info['original_layer']
                    else:
                        display_name = self.listName.get(selected_name, selected_name)

                    layer = QgsVectorLayer(self.Database + "|layername=" + selected_name, display_name, 'ogr')

                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer, False)
                        # IMPORTANTE: Adicionar direto ao grupo OUTRAS, NÃO ao dictLayerAndYourName
                        outras_group.addLayer(layer)

                        self.applyStyleToLayer(layer, original_type_for_style)

                        print(f"  ✓ Carregada no grupo OUTRAS: {display_name}")
                    else:
                        print(f"  ✗ ERRO ao carregar: {selected_name}")
            else:
                print(f"\n--- NENHUMA CAMADA 'OUTRAS' SELECIONADA ---")

        else:
            # RESTO DO CÓDIGO PARA GEOPACKAGES NOVOS...
            # (mantém toda a lógica existente, mas aplicando a mesma correção)

            print("Processando geopackage novo - salvando duplicatas e renomeações fisicamente...")

            # Primeiro: remover camadas não selecionadas do template
            listLayersNotSelected = self.layerNotSelected(selected_layers, self.listName)
            for name in listLayersNotSelected:
                self.removeLayersOfGeopackage(fileNameFull, name)

            # Segundo: identificar e processar camadas duplicadas
            layers_to_duplicate = {}  # {original_layer: [list of custom_names]}
            normal_layers = []

            for layer_name in selected_layers:
                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    original_layer = info.get('original_layer', layer_name)
                    custom_name = info.get('custom_name', layer_name)

                    # Se é uma duplicata (não é original renomeado)
                    if not info.get('is_original_renamed'):
                        if original_layer not in layers_to_duplicate:
                            layers_to_duplicate[original_layer] = []
                        layers_to_duplicate[original_layer].append({
                            'duplicate_name': layer_name,
                            'custom_name': custom_name
                        })
                    else:
                        # É original renomeado
                        normal_layers.append((layer_name, custom_name))
                else:
                    # Camada normal sem customização
                    normal_layers.append((layer_name, None))

            print(f"Camadas para duplicar: {layers_to_duplicate}")
            print(f"Camadas normais: {normal_layers}")

            # Terceiro: copiar duplicatas fisicamente
            for original_layer, duplicates in layers_to_duplicate.items():
                print(f"Criando duplicatas físicas para: {original_layer}")

                for duplicate_info_item in duplicates:
                    custom_name = duplicate_info_item['custom_name']
                    print(f"  Criando duplicata física: {custom_name}")

                    # Copiar a camada original para uma nova camada com nome personalizado
                    success = self.copyLayerWithinGeopackage(
                        fileNameFull, 
                        original_layer, 
                        custom_name
                    )

                    if success:
                        print(f"    ✓ Duplicata física criada: {custom_name}")
                    else:
                        print(f"    ✗ Erro ao criar duplicata: {custom_name}")

            # Terceiro-B: Renomear originais fisicamente
            print("Processando renomeação de originais...")
            for layer_name in selected_layers:
                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    if info.get('is_original_renamed'):
                        custom_name = info.get('custom_name')
                        print(f"Renomeando original fisicamente: {layer_name} → {custom_name}")

                        # Copiar camada original com novo nome
                        success = self.copyLayerWithinGeopackage(
                            fileNameFull,
                            layer_name,  # nome original
                            custom_name  # nome personalizado
                        )

                        if success:
                            # Remover a camada original (agora temos duas: original e renomeada)
                            self.removeLayersOfGeopackage(fileNameFull, layer_name)
                            print(f"    ✓ Original renomeado fisicamente para: {custom_name}")
                        else:
                            print(f"    ✗ Erro ao renomear original: {layer_name}")

            # Quarto: carregar todas as camadas (originais, renomeadas e duplicatas)
            # Obter lista atualizada de camadas no arquivo
            ds = ogr.Open(fileNameFull)
            if ds:
                actual_layers_in_file = [l.GetName() for l in ds]
                ds = None
            else:
                print("ERRO: Não foi possível abrir o arquivo após duplicação!")
                return 0

            # Filtrar camadas de sistema
            available_layers = [layer for layer in actual_layers_in_file 
                               if layer not in system_tables and 
                               not any(layer.startswith(prefix) for prefix in ['rtree_', 'idx_', 'trigger_'])]

            print(f"Camadas disponíveis após duplicação e renomeação: {available_layers}")

            # Separar camadas "outras" das demais
            outras_camadas_para_carregar = []
            camadas_normais_para_carregar = []

            # Carregar todas as camadas selecionadas
            for layer_name in selected_layers:
                if layer_name.startswith('raster_'):
                    continue  # Processar rasters separadamente

                original_base_type = None

                # Determinar o nome da camada no arquivo e o nome de exibição
                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    custom_name = info.get('custom_name', layer_name)

                    original_base_type = info['original_layer']

                    if info.get('is_original_renamed'):
                        # CORREÇÃO: Original renomeado - usar nome personalizado no arquivo
                        file_layer_name = custom_name
                        display_name = custom_name
                    else:
                        # Duplicata - usar nome customizado no arquivo
                        file_layer_name = custom_name
                        display_name = custom_name
                else:
                    # Camada normal
                    file_layer_name = layer_name
                    display_name = self.listName.get(layer_name, layer_name)
                    original_base_type = layer_name

                print(f"Carregando: arquivo={file_layer_name}, exibição={display_name}")

                if file_layer_name in available_layers:
                    
                    if is_outras_camada(original_base_type) or is_outras_camada(file_layer_name):
                        outras_camadas_para_carregar.append((file_layer_name, display_name, original_base_type))
                    else:
                        camadas_normais_para_carregar.append((file_layer_name, display_name, layer_name))

            # Carregar camadas normais
            for file_layer_name, display_name, original_base_type  in camadas_normais_para_carregar:
                layer = QgsVectorLayer(
                    self.Database + "|layername=" + file_layer_name, 
                    display_name, 
                    'ogr'
                )

                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer, False)
                    # IMPORTANTE: Adicionar ao dictLayerAndYourName APENAS se for camada normal
                    dictLayerAndYourName[layer.name()] = layer

                    # Aplicar estilo baseado no tipo original
                    self.applyStyleToLayer(layer, original_base_type)
                    print(f"  ✓ Carregada: {display_name}")
                else:
                    print(f"  ✗ ERRO ao carregar: {file_layer_name}")

            # Carregar camadas "outras" em grupo separado
            if outras_camadas_para_carregar:
                print("Criando grupo OUTRAS CAMADAS...")
                outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')

                for file_layer_name, display_name, original_base_type in outras_camadas_para_carregar:
                    layer = QgsVectorLayer(
                        self.Database + "|layername=" + file_layer_name, 
                        display_name, 
                        'ogr'
                    )

                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer, False)
                        # IMPORTANTE: Adicionar direto ao grupo OUTRAS, NÃO ao dictLayerAndYourName
                        outras_group.addLayer(layer)

                        # Aplicar estilo se existir
                        self.applyStyleToLayer(layer, original_base_type)
                        print(f"  ✓ Carregada no grupo OUTRAS: {display_name}")
                    else:
                        print(f"  ✗ ERRO ao carregar: {file_layer_name}")

        # CORREÇÃO CRÍTICA: Organizar no grupo principal APENAS as camadas que estão em dictLayerAndYourName
        # (que agora são APENAS as camadas normais, não as "outras")
        print(f"\n=== ORGANIZANDO GRUPO PRINCIPAL ===")
        print(f"Camadas para grupo principal: {list(dictLayerAndYourName.keys())}")

        dictLayerAndYourName = {k: dictLayerAndYourName[k] for k in sorted(dictLayerAndYourName.keys())}

        for layerName in dictLayerAndYourName:
            layer = dictLayerAndYourName[layerName]
            self.groupMain.addLayer(layer)
            print(f"  ✓ Adicionada ao grupo principal: {layerName}")

        # Carregar camadas raster selecionadas
        raster_layers = [layer for layer in selected_layers if layer.startswith('raster_')]
        if raster_layers:
            self.loadSelectedRasterLayers(raster_layers)

        # Limpeza
        self.groupMain.removeChildrenGroupWithoutLayers()
        iface.mapCanvas().refresh()

        print(f"=== CARREGAMENTO CONCLUÍDO ===")
        print(f"Camadas no grupo principal: {len(dictLayerAndYourName)}")

        return 1
    
    def identifyLayerTypeForStyling(self, layer_name):
        """
        Tenta identificar o tipo original da camada para aplicar o estilo correto
        """
        # Converter o nome para minúsculas para comparação
        name_lower = layer_name.lower()

        # Mapear palavras-chave para tipos de camada
        style_keywords = {
            'coord': 'coord_ap_fogo',
            'apoio': 'coord_ap_fogo',
            'fogo': 'coord_ap_fogo',
            'eixo': 'eixo_de_direcao',
            'direção': 'eixo_de_direcao',
            'direcao': 'eixo_de_direcao',
            'fortificaç': 'fortificacoes_pf',
            'fortes': 'fortificacoes_pf',
            'limite': 'limite_entre_fracoes',
            'fraç': 'limite_entre_fracoes',
            'fracoes': 'limite_entre_fracoes',
            'linha': 'linha_de_controle',
            'controle': 'linha_de_controle',
            'seta': 'seta_situacao',
            'situação': 'seta_situacao',
            'situacao': 'seta_situacao',
            'símbolo': 'simbolos_pontos',
            'simbolo': 'simbolos_pontos',
            'obstáculo': 'obstaculos',
            'obstaculo': 'obstaculos',
            'obstáculos': 'obstaculos',
            'obstaculos': 'obstaculos'
        }

        # Procurar por palavras-chave no nome da camada
        for keyword, layer_type in style_keywords.items():
            if keyword in name_lower:
                print(f"Tipo identificado para '{layer_name}': {layer_type} (palavra-chave: {keyword})")
                return layer_type

        print(f"Tipo não identificado para '{layer_name}'")
        return None
    
    def copyLayerWithinGeopackage(self, geopackage_path, source_layer_name, target_layer_name):
        """
        Copia uma camada dentro do mesmo geopackage com um novo nome

        Args:
            geopackage_path: Caminho do geopackage
            source_layer_name: Nome da camada origem
            target_layer_name: Nome da nova camada

        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            print(f"Copiando {source_layer_name} -> {target_layer_name}")

            # Carregar a camada origem
            source_layer = QgsVectorLayer(
                geopackage_path + "|layername=" + source_layer_name, 
                "temp_source", 
                'ogr'
            )

            if not source_layer.isValid():
                print(f"Erro: Camada origem {source_layer_name} não é válida")
                return False

            # Adicionar temporariamente ao projeto
            QgsProject.instance().addMapLayer(source_layer, False)

            # Configurar opções de escrita
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            options.layerName = target_layer_name
            options.saveStyles = False  # Aplicaremos o estilo depois

            # Copiar a camada para o mesmo geopackage com novo nome
            error = QgsVectorFileWriter.writeAsVectorFormat(
                source_layer,
                geopackage_path,
                options
            )

            # Remover a camada temporária
            QgsProject.instance().removeMapLayer(source_layer.id())

            if error[0] == QgsVectorFileWriter.NoError:
                print(f"Duplicata criada com sucesso: {target_layer_name}")
                return True
            else:
                print(f"Erro ao criar duplicata {target_layer_name}: {error}")
                return False

        except Exception as e:
            print(f"Erro em copyLayerWithinGeopackage: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def loadSelectedRasterLayers(self, selected_raster_layers):
        """
        Carrega apenas as camadas raster selecionadas

        Args:
            selected_raster_layers: Lista de camadas raster selecionadas (com prefixo 'raster_')
        """
        try:
            # Criar grupo para rasters se houver camadas selecionadas
            if not selected_raster_layers:
                return

            symbolGroupR = self.groupMain.insertGroup(1, 'CAMADAS RASTER')
            raster_info = gdal.Info(self.Database)

            if not raster_info:
                print("Nenhuma informação raster encontrada no banco de dados")
                return

            # Processar rasters do geopackage
            raster_layers = re.findall("GPKG:.*", raster_info)

            if not raster_layers:
                # Tentar formato alternativo
                raster_layers = re.findall("IDENTIFIER=.*", raster_info)
                if raster_layers:
                    raster_layer = raster_layers[0].replace('IDENTIFIER=', '')

                    # Verificar se este raster foi selecionado
                    if f'raster_{raster_layer}' in selected_raster_layers:
                        layer = QgsRasterLayer(
                            "GPKG:" + self.Database + ":" + raster_layer, 
                            raster_layer, 
                            'gdal'
                        )
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer, False)
                            symbolGroupR.addLayer(layer)
                        else:
                            print(f"Erro ao carregar raster: {raster_layer}")
            else:
                # Processar múltiplos rasters
                for raster in raster_layers:
                    raster_name = raster[raster.rfind(':') + 1:]

                    # Verificar se este raster foi selecionado
                    if f'raster_{raster_name}' in selected_raster_layers:
                        layer = QgsRasterLayer(raster, raster_name, 'gdal')
                        if layer.isValid():
                            QgsProject.instance().addMapLayer(layer, False)
                            symbolGroupR.addLayer(layer)
                        else:
                            print(f"Erro ao carregar raster: {raster_name}")

            # Remover grupo se vazio
            if len(symbolGroupR.findLayerIds()) == 0:
                self.groupMain.removeChildNode(symbolGroupR)

        except Exception as e:
            print(f"Erro ao carregar camadas raster: {str(e)}")
    
    def addStyleInLayersInGroup(self):
        file_path = self.Database.replace('\\','/')
        gpkgname = file_path.split('/')[-1]
        groupName = gpkgname.split('.')[0]

        root = QgsProject.instance().layerTreeRoot()

        # Encontrar o grupo pelo nome
        found_group = None
        for child in root.children():
            if child.nodeType() == QgsLayerTreeNode.NodeGroup and child.name() == groupName:
                found_group = child
                break

        # Verificar se o grupo foi encontrado
        if not found_group:
            print(f"Grupo '{groupName}' não encontrado!")
            return False

        # Função recursiva para obter camadas de um grupo e seus subgrupos
        def get_layers_from_group(group):
            for child in group.children():
                if child.nodeType() == QgsLayerTreeNode.NodeLayer:
                    # É uma camada
                    layer = child.layer()
                    if layer:
                        self.styleInLayer(layer)
                elif child.nodeType() == QgsLayerTreeNode.NodeGroup:
                    # É um subgrupo, processar recursivamente
                    get_layers_from_group(child)

        # Chamar a função para obter todas as camadas
        get_layers_from_group(found_group)
        return True

    def styleInLayer(self, layer):
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_estilos = os.path.join(caminho_atual, 'styles')
        if "Coordenação" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_coord_apoio_fogo.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Eixo" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_eixo_direcao.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Fortificações" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_fort_pontos_fortes.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Limite" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_limite_entre_fracoes.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Linha" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_linha_controle.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Seta" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_seta_situacao.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Símbolos" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_simbolos.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
        elif "Obstáculos" in layer.name():
            path_qml = os.path.join(pasta_estilos, 'style_obstaculos.qml')
            layer.loadNamedStyle(path_qml)
            layer.triggerRepaint()
    
    def addLayerInGeopackage(self, pathGeopackage, layer):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
        options.layerName = layer.name()
        options.saveStyles = True       # Salvar estilos da camada

        error = QgsVectorFileWriter.writeAsVectorFormat(
            layer,
            pathGeopackage,
            options
        )

        if error[0] == QgsVectorFileWriter.NoError:
            print("Camada adicionada com sucesso ao geopackage!")

            return True
        else:
           print(f"Erro ao adicionar camada: {error}") 
    
    def loadDatabaseWithFilter(self):
        """Carrega o banco de dados aplicando filtro das camadas selecionadas"""
        projects = self.checkTableFromDatabase('qgis_projects')
        if projects[0] == 'table not available':
            return self.loadSymbLayersWithFilter()
        else:
            # Para projetos, ainda carregamos tudo (podemos filtrar depois se necessário)
            return self.loadProject()

    def loadRasterLayersWithFilter(self):
        """Versão modificada de loadRasterLayers que aplica filtro"""
        symbolGroupR = self.groupMain.insertGroup(3, 'CAMADAS RASTER')
        raster_info = gdal.Info(self.Database)

        if not not raster_info:
            selected_layers = getattr(self, 'selected_layers', [])

            raster_layers = re.findall("GPKG:.*", raster_info)
            if not raster_layers:
                raster_layers = re.findall("IDENTIFIER=.*", raster_info)
                if raster_layers:
                    raster_layer = raster_layers[0].replace('IDENTIFIER=', '')

                    # Verificar se este raster foi selecionado
                    if f'raster_{raster_layer}' in selected_layers:
                        layer = QgsRasterLayer("GPKG:" + self.Database + ":" + raster_layer, raster_layer, 'gdal')
                        QgsProject.instance().addMapLayer(layer, False)
                        symbolGroupR.addLayer(layer)
            else:
                for raster in raster_layers:
                    raster_name = raster[raster.rfind(':') + 1:]

                    # Verificar se este raster foi selecionado
                    if f'raster_{raster_name}' in selected_layers:
                        layer = QgsRasterLayer(raster, raster_name, 'gdal')
                        QgsProject.instance().addMapLayer(layer, False)
                        symbolGroupR.addLayer(layer)

    def  copySelectedRasters(self, src_path, dst_path, selected_layers):
        """Copia camadas raster selecionadas do template para o novo banco de dados"""
        # Verificar se há rasters no template
        raster_info = gdal.Info(src_path)
        if not raster_info:
            return

        try:
            # Identificar rasters no template
            raster_layers = re.findall("GPKG:.*", raster_info)
            if not raster_layers:
                raster_layers = re.findall("IDENTIFIER=.*", raster_info)
                if raster_layers:
                    raster_layer = raster_layers[0].replace('IDENTIFIER=', '')
                    if f'raster_{raster_layer}' in selected_layers:
                        # Copiar o raster
                        src_raster = gdal.Open(f"GPKG:{src_path}:{raster_layer}")
                        driver = gdal.GetDriverByName('GPKG')
                        dst_raster = driver.CreateCopy(f"GPKG:{dst_path}:{raster_layer}", src_raster)
                        dst_raster = None
                        src_raster = None
            else:
                for raster in raster_layers:
                    raster_name = raster[raster.rfind(':') + 1:]
                    if f'raster_{raster_name}' in selected_layers:
                        # Copiar o raster
                        src_raster = gdal.Open(raster)
                        driver = gdal.GetDriverByName('GPKG')
                        dst_raster = driver.CreateCopy(f"GPKG:{dst_path}:{raster_name}", src_raster)
                        dst_raster = None
                        src_raster = None
        except Exception as e:
            print(f"Erro ao copiar rasters: {str(e)}")

    def copyLayerFromTemplate(self, template_path, target_path, source_name, display_name, original_type):
        """
        Copia uma camada do template para o arquivo de destino

        Args:
            template_path: Caminho do template
            target_path: Caminho do arquivo de destino
            source_name: Nome da camada no template
            display_name: Nome de exibição a ser usado
            original_type: Tipo original da camada (para configurações específicas)

        Returns:
            bool: Sucesso ou falha
        """
        try:
            # Abrir a camada do template
            layer_uri = f"{template_path}|layername={source_name}"
            layer = QgsVectorLayer(layer_uri, display_name, 'ogr')

            if not layer.isValid():
                print(f"Erro: Camada {source_name} não é válida no template")
                return False

            # Adicionar temporariamente ao projeto
            QgsProject.instance().addMapLayer(layer, False)

            # Copiar para o arquivo de destino
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
            options.layerName = display_name
            options.saveStyles = True

            error = QgsVectorFileWriter.writeAsVectorFormat(
                layer, target_path, options)

            # Remover a camada temporária
            QgsProject.instance().removeMapLayer(layer.id())

            if error[0] == QgsVectorFileWriter.NoError:
                print(f"Camada '{display_name}' copiada com sucesso")
                return True
            else:
                print(f"Erro ao copiar camada '{display_name}': {error}")
                return False

        except Exception as e:
            print(f"Erro ao copiar camada {source_name}: {str(e)}")
            return False

    def addTemplateLayersToExistingGeopackage(self, selected_layers, duplicate_info=None):
        """
        Adiciona camadas selecionadas do template a um geopackage existente
        Agora com suporte corrigido para o grupo "OUTRAS CAMADAS"
        """
        try:
            # Obter o caminho do template
            template_path = self.getTemplateDatabase()
            target_path = self.Database
    
            if not os.path.exists(template_path):
                print(f"Erro: Template não encontrado em {template_path}")
                return False
    
            if not os.path.exists(target_path):
                print(f"Erro: Arquivo de destino não encontrado em {target_path}")
                return False
    
            # Obter nome do arquivo para o grupo
            fileName = target_path.split('/')[-1].split('.')[0]
            root = QgsProject.instance().layerTreeRoot()
            self.groupMain = root.insertGroup(0, fileName)
    
            # Dicionário para armazenar camadas adicionadas
            added_layers = {}
            outras_camadas_adicionadas = {}
    
            # IMPORTANTE: Definir lista de camadas "outras" aqui
            outras_layer_names = [
                'barragem_grupo_concentracao', 
                'barreiras', 
                'redes', 
                'fortificacoes_ot'
            ]
    
            # Processar camadas normais e duplicadas
            for layer_name in selected_layers:
                # Determinar o nome da camada de origem e destino
                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    original_layer = info.get('original_layer', layer_name)
                    custom_name = info.get('custom_name', layer_name)
                else:
                    original_layer = layer_name
                    custom_name = self.listName.get(layer_name, layer_name)
    
                # Verificar se é uma camada numerada (duplicata)
                if '_' in layer_name and layer_name.split('_')[-1].isdigit():
                    # Para duplicatas, usar o nome base
                    base_name = '_'.join(layer_name.split('_')[:-1])
                    source_layer_name = base_name
                else:
                    source_layer_name = original_layer
    
                print(f"Processando camada: layer_name={layer_name}, source_layer_name={source_layer_name}, custom_name={custom_name}")
    
                # Carregar a camada do template
                template_layer_uri = f"{template_path}|layername={source_layer_name}"
                template_layer = QgsVectorLayer(template_layer_uri, custom_name, 'ogr')
    
                if not template_layer.isValid():
                    print(f"Erro: Camada {source_layer_name} não é válida no template")
                    continue
                
                # Adicionar temporariamente ao projeto para copiar
                QgsProject.instance().addMapLayer(template_layer, False)
    
                # Copiar para o geopackage existente
                options = QgsVectorFileWriter.SaveVectorOptions()
                options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                options.layerName = custom_name
                options.saveStyles = False  # Vamos aplicar o estilo depois
    
                error = QgsVectorFileWriter.writeAsVectorFormat(
                    template_layer, target_path, options
                )
    
                # Remover a camada temporária do template
                QgsProject.instance().removeMapLayer(template_layer.id())
    
                if error[0] == QgsVectorFileWriter.NoError:
                    print(f"Camada '{custom_name}' copiada com sucesso")
    
                    # Agora carregar a camada do geopackage de destino
                    new_layer_uri = f"{target_path}|layername={custom_name}"
                    new_layer = QgsVectorLayer(new_layer_uri, custom_name, 'ogr')
    
                    if new_layer.isValid():
                        # Adicionar ao projeto
                        QgsProject.instance().addMapLayer(new_layer, False)
    
                        # CORREÇÃO: Verificar se é uma das camadas "outras" de forma mais robusta
                        is_outras_camada = False
                        
                        # Verificar pelo nome da camada fonte
                        if source_layer_name in outras_layer_names:
                            is_outras_camada = True
                            print(f"  ✓ Identificada como OUTRAS pelo nome fonte: {source_layer_name}")
                        
                        # Verificar pelo nome original da camada
                        elif original_layer in outras_layer_names:
                            is_outras_camada = True
                            print(f"  ✓ Identificada como OUTRAS pelo nome original: {original_layer}")
                        
                        # Verificar se é uma duplicata de uma camada "outras"
                        elif '_' in layer_name and layer_name.split('_')[-1].isdigit():
                            base_name = '_'.join(layer_name.split('_')[:-1])
                            if base_name in outras_layer_names:
                                is_outras_camada = True
                                print(f"  ✓ Identificada como OUTRAS por ser duplicata de: {base_name}")
    
                        if is_outras_camada:
                            # Adicionar ao grupo "OUTRAS CAMADAS"
                            if not hasattr(self, 'outras_group') or self.outras_group is None:
                                self.outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')
                            self.outras_group.addLayer(new_layer)
                            outras_camadas_adicionadas[custom_name] = new_layer
                            print(f"  → Adicionada ao grupo OUTRAS CAMADAS: {custom_name}")
                        else:
                            # Adicionar ao grupo principal
                            self.groupMain.addLayer(new_layer)
                            added_layers[custom_name] = new_layer
                            print(f"  → Adicionada ao grupo principal: {custom_name}")
    
                        # Aplicar estilo
                        self.applyStyleToLayer(new_layer, source_layer_name)
                    else:
                        print(f"Erro ao carregar camada '{custom_name}' do geopackage")
                else:
                    print(f"Erro ao copiar camada '{custom_name}': {error}")
    
            # Atualizar o canvas
            iface.mapCanvas().refresh()
    
            # Remover grupo se vazio
            total_added = len(added_layers) + len(outras_camadas_adicionadas)
            if total_added == 0:
                root.removeChildNode(self.groupMain)
                return False
    
            print(f"\nTotal de camadas adicionadas: {total_added}")
            print(f"  - Grupo principal: {len(added_layers)} camadas")
            print(f"  - Grupo OUTRAS CAMADAS: {len(outras_camadas_adicionadas)} camadas")
            
            return True
    
        except Exception as e:
            print(f"Erro em addTemplateLayersToExistingGeopackage: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def applyStyleToLayer(self, layer, original_name):
        """
        Aplica o estilo apropriado a uma camada baseado no nome original

        Args:
            layer: Camada QgsVectorLayer
            original_name: Nome original da camada no template
        """
        caminho_atual = os.path.dirname(os.path.realpath(__file__))
        pasta_estilos = os.path.join(caminho_atual, 'styles')

        # Se o nome tem sufixo numérico (ex: coord_ap_fogo_2), remover o sufixo
        base_name = original_name
        if '_' in original_name and original_name.split('_')[-1].isdigit():
            # Remover o sufixo numérico para obter o nome base
            base_name = '_'.join(original_name.split('_')[:-1])
            print(f"Nome com sufixo detectado: {original_name} → base: {base_name}")

        # Mapear nomes de camadas para arquivos de estilo
        style_mapping = {
            'coord_ap_fogo': 'style_coord_apoio_fogo.qml',
            'eixo_de_direcao': 'style_eixo_direcao.qml',
            'fortificacoes_pf': 'style_fort_pontos_fortes.qml',
            'limite_entre_fracoes': 'style_limite_entre_fracoes.qml',
            'linha_de_controle': 'style_linha_controle.qml',
            'seta_situacao': 'style_seta_situacao.qml',
            'simbolos_pontos': 'style_simbolos.qml',
            'obstaculos': 'style_obstaculos.qml',
        }

        # Tentar aplicar estilo usando o nome base
        if base_name in style_mapping:
            style_file = style_mapping[base_name]
            path_qml = os.path.join(pasta_estilos, style_file)

            if os.path.exists(path_qml):
                layer.loadNamedStyle(path_qml)
                layer.triggerRepaint()
                print(f"✓ Estilo '{style_file}' aplicado para camada: {layer.name()}")
            else:
                print(f"✗ Arquivo de estilo não encontrado: {path_qml}")
        else:
            # Se não encontrou pelo nome exato, tentar identificar pelo tipo
            identified_type = self.identifyLayerTypeForStyling(base_name)
            if identified_type and identified_type in style_mapping:
                style_file = style_mapping[identified_type]
                path_qml = os.path.join(pasta_estilos, style_file)

                if os.path.exists(path_qml):
                    layer.loadNamedStyle(path_qml)
                    layer.triggerRepaint()
                    print(f"✓ Estilo '{style_file}' aplicado (por identificação) para camada: {layer.name()}")
                else:
                    print(f"✗ Arquivo de estilo não encontrado: {path_qml}")
            else:
                print(f"⚠ Nenhum estilo encontrado para: {original_name} (base: {base_name})")

    def duplicateExistingLayers(self, selected_layers, duplicate_info=None):
        """
        Duplica camadas que já existem no geopackage atual
        Agora com suporte para o grupo "OUTRAS CAMADAS"
        """
        try:
            print(f"=== DUPLICANDO CAMADAS EXISTENTES ===")
            target_path = self.Database

            if not target_path or not os.path.exists(target_path):
                print(f"Erro: Arquivo de destino inválido: {target_path}")
                return False

            if duplicate_info is None:
                duplicate_info = {}

            print(f"Camadas para duplicar: {selected_layers}")
            print(f"Info de duplicatas: {duplicate_info}")

            # Obter nome do arquivo para o grupo
            fileName = target_path.split('/')[-1].split('.')[0]
            root = QgsProject.instance().layerTreeRoot()

            # Tentar encontrar grupo existente ou criar novo
            existing_group = None
            for child in root.children():
                if hasattr(child, 'name') and child.name() == fileName:
                    existing_group = child
                    break
                
            if existing_group:
                self.groupMain = existing_group
            else:
                self.groupMain = root.insertGroup(0, fileName)

            # Verificar quais camadas realmente existem no arquivo
            ds = ogr.Open(target_path)
            if ds:
                actual_layers_in_file = [l.GetName() for l in ds]
                ds = None
            else:
                print("Erro: Não foi possível abrir o geopackage")
                return False

            print(f"Camadas disponíveis no arquivo: {actual_layers_in_file}")

            success_count = 0
            outras_count = 0

            # Processar cada camada selecionada
            for layer_name in selected_layers:
                print(f"\n--- PROCESSANDO: {layer_name} ---")

                # Verificar se a camada existe no arquivo
                if layer_name not in actual_layers_in_file:
                    print(f"Erro: Camada {layer_name} não existe no arquivo")
                    continue
                
                # CORREÇÃO: Garantir que sempre usa o nome customizado para renomeações
                target_layer_name = layer_name  # Valor padrão

                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    custom_name = info.get('custom_name', layer_name)

                    # SEMPRE usar o nome customizado como destino
                    target_layer_name = custom_name
                    print(f"Usando nome customizado: {layer_name} → {target_layer_name}")
                else:
                    # Se não tem info de duplicata, adicionar sufixo padrão
                    target_layer_name = f"{layer_name} - Cópia"
                    print(f"Sem nome customizado, usando padrão: {target_layer_name}")

                # Verificar se já existe uma camada com o nome de destino
                if target_layer_name in actual_layers_in_file and target_layer_name != layer_name:
                    print(f"Aviso: Camada {target_layer_name} já existe, será sobrescrita")

                # Criar a duplicata física apenas se o nome for diferente
                if target_layer_name != layer_name:
                    success = self.copyLayerWithinGeopackage(
                        target_path,
                        layer_name,  # origem
                        target_layer_name  # destino
                    )

                    if not success:
                        print(f"✗ Erro ao criar duplicata física: {target_layer_name}")
                        continue
                    else:
                        print(f"✓ Duplicata física criada: {target_layer_name}")

                # Carregar a camada no projeto
                new_layer_uri = f"{target_path}|layername={target_layer_name}"
                new_layer = QgsVectorLayer(new_layer_uri, target_layer_name, 'ogr')

                if new_layer.isValid():
                    QgsProject.instance().addMapLayer(new_layer, False)

                    # Verificar se é uma das camadas "outras"
                    if any(layer_name.startswith(outras) for outras in [
                        'barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot'
                    ]):
                        # Adicionar ao grupo "OUTRAS CAMADAS"
                        if not hasattr(self, 'outras_group'):
                            self.outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')
                        self.outras_group.addLayer(new_layer)
                        outras_count += 1
                    else:
                        # Adicionar ao grupo principal
                        self.groupMain.addLayer(new_layer)

                    # Aplicar estilo baseado na camada original
                    original_type = self.identifyLayerTypeForStyling(layer_name)
                    if original_type:
                        self.applyStyleToLayer(new_layer, original_type)
                    else:
                        # Tentar aplicar estilo baseado no nome da camada original
                        self.applyStyleToLayer(new_layer, layer_name)

                    success_count += 1
                    print(f"✓ Camada carregada no projeto: {target_layer_name}")
                else:
                    print(f"✗ Erro ao carregar duplicata no projeto: {target_layer_name}")

            # Atualizar interface
            iface.mapCanvas().refresh()

            print(f"\n=== RESULTADO ===")
            print(f"Duplicatas criadas com sucesso: {success_count}/{len(selected_layers)} (Outras: {outras_count})")

            return success_count > 0

        except Exception as e:
            print(f"Erro em duplicateExistingLayers: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
    def loadExistingLayersOnly(self, selected_layers, duplicate_info=None):
        """
        Carrega camadas que já existem no geopackage SEM criar cópias físicas
        Agora com suporte para o grupo "OUTRAS CAMADAS"
        """
        try:
            print(f"=== CARREGANDO CAMADAS EXISTENTES (SEM DUPLICAR) ===")
            target_path = self.Database

            if not target_path or not os.path.exists(target_path):
                print(f"Erro: Arquivo inválido: {target_path}")
                return False

            if duplicate_info is None:
                duplicate_info = {}

            print(f"Camadas para carregar: {selected_layers}")
            print(f"Info de duplicatas: {duplicate_info}")

            # Obter nome do arquivo para o grupo
            fileName = target_path.split('/')[-1].split('.')[0]
            root = QgsProject.instance().layerTreeRoot()

            # Tentar encontrar grupo existente ou criar novo
            existing_group = None
            for child in root.children():
                if hasattr(child, 'name') and child.name() == fileName:
                    existing_group = child
                    break
                
            if existing_group:
                self.groupMain = existing_group
            else:
                self.groupMain = root.insertGroup(0, fileName)

            # Verificar quais camadas realmente existem no arquivo
            ds = ogr.Open(target_path)
            if ds:
                actual_layers_in_file = [l.GetName() for l in ds]
                ds = None
            else:
                print("Erro: Não foi possível abrir o geopackage")
                return False

            print(f"Camadas disponíveis no arquivo: {actual_layers_in_file}")

            success_count = 0
            outras_count = 0

            # Carregar cada camada selecionada
            for layer_name in selected_layers:
                print(f"\n--- CARREGANDO: {layer_name} ---")

                # Verificar se a camada existe no arquivo
                if layer_name not in actual_layers_in_file:
                    print(f"Erro: Camada {layer_name} não existe no arquivo")
                    continue
                
                # Determinar nome de exibição
                if layer_name in duplicate_info:
                    info = duplicate_info[layer_name]
                    display_name = info.get('custom_name', layer_name)
                else:
                    display_name = self.listName.get(layer_name, layer_name)

                print(f"Carregando camada: {layer_name} como '{display_name}'")

                # Carregar a camada diretamente do geopackage (SEM CRIAR CÓPIA)
                layer_uri = f"{target_path}|layername={layer_name}"
                layer = QgsVectorLayer(layer_uri, display_name, 'ogr')

                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer, False)

                    # Verificar se é uma das camadas "outras"
                    if any(layer_name.startswith(outras) for outras in [
                        'barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot'
                    ]):
                        # Adicionar ao grupo "OUTRAS CAMADAS"
                        if not hasattr(self, 'outras_group'):
                            self.outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')
                        self.outras_group.addLayer(layer)
                        outras_count += 1
                    else:
                        # Adicionar ao grupo principal
                        self.groupMain.addLayer(layer)

                    # Aplicar estilo baseado no tipo original
                    original_type = self.identifyLayerTypeForStyling(layer_name)
                    if original_type:
                        self.applyStyleToLayer(layer, original_type)
                    else:
                        self.applyStyleToLayer(layer, layer_name)

                    success_count += 1
                    print(f"✓ Camada carregada: {display_name}")
                else:
                    print(f"✗ Erro ao carregar camada: {layer_name}")

            # Atualizar interface
            iface.mapCanvas().refresh()

            print(f"\n=== RESULTADO ===")
            print(f"Camadas carregadas com sucesso: {success_count}/{len(selected_layers)} (Outras: {outras_count})")

            return success_count > 0

        except Exception as e:
            print(f"Erro em loadExistingLayersOnly: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
    def renameExistingLayers(self, selected_layers, duplicate_info=None):
        """
        Renomeia camadas existentes no geopackage (substitui a original)
        """
        try:
            print(f"=== RENOMEANDO CAMADAS EXISTENTES ===")
            target_path = self.Database

            if not target_path or not os.path.exists(target_path):
                print(f"Erro: Arquivo de destino inválido: {target_path}")
                return False

            if duplicate_info is None:
                duplicate_info = {}

            print(f"Camadas para renomear: {selected_layers}")
            print(f"Info de renomeação: {duplicate_info}")

            # Obter nome do arquivo para o grupo
            fileName = target_path.split('/')[-1].split('.')[0]
            root = QgsProject.instance().layerTreeRoot()

            # Tentar encontrar grupo existente ou criar novo
            existing_group = None
            for child in root.children():
                if hasattr(child, 'name') and child.name() == fileName:
                    existing_group = child
                    break
                
            if existing_group:
                self.groupMain = existing_group
            else:
                self.groupMain = root.insertGroup(0, fileName)

            # Verificar quais camadas realmente existem no arquivo
            ds = ogr.Open(target_path)
            if ds:
                actual_layers_in_file = [l.GetName() for l in ds]
                ds = None
            else:
                print("Erro: Não foi possível abrir o geopackage")
                return False

            print(f"Camadas disponíveis no arquivo: {actual_layers_in_file}")

            success_count = 0
            outras_count = 0
            layers_to_remove = []  # Lista de camadas antigas para remover

            # Processar cada camada selecionada
            for layer_name in selected_layers:
                print(f"\n--- RENOMEANDO: {layer_name} ---")

                # Verificar se a camada existe no arquivo
                if layer_name not in actual_layers_in_file:
                    print(f"Erro: Camada {layer_name} não existe no arquivo")
                    continue
                
                # Obter o novo nome
                if layer_name not in duplicate_info:
                    print(f"Erro: Sem informação de novo nome para {layer_name}")
                    continue

                info = duplicate_info[layer_name]
                new_name = info.get('custom_name', layer_name)

                if new_name == layer_name:
                    print(f"Aviso: Nome não foi alterado para {layer_name}")
                    continue

                print(f"Renomeando: {layer_name} → {new_name}")

                # Verificar se já existe uma camada com o novo nome
                if new_name in actual_layers_in_file:
                    print(f"Aviso: Camada {new_name} já existe, será sobrescrita")

                # PASSO 1: Copiar a camada com o novo nome
                success = self.copyLayerWithinGeopackage(
                    target_path,
                    layer_name,  # origem
                    new_name     # destino
                )

                if not success:
                    print(f"✗ Erro ao criar cópia com novo nome: {new_name}")
                    continue

                print(f"✓ Cópia criada com novo nome: {new_name}")

                # PASSO 2: Marcar a camada original para remoção
                layers_to_remove.append(layer_name)

                # PASSO 3: Carregar apenas a camada com novo nome no projeto
                new_layer_uri = f"{target_path}|layername={new_name}"
                new_layer = QgsVectorLayer(new_layer_uri, new_name, 'ogr')

                if new_layer.isValid():
                    QgsProject.instance().addMapLayer(new_layer, False)

                    # Verificar se é uma das camadas "outras"
                    if any(layer_name.startswith(outras) for outras in [
                        'barragem_grupo_concentracao', 'barreiras', 'redes', 'fortificacoes_ot'
                    ]):
                        # Adicionar ao grupo "OUTRAS CAMADAS"
                        if not hasattr(self, 'outras_group'):
                            self.outras_group = self.groupMain.insertGroup(0, 'OUTRAS CAMADAS')
                        self.outras_group.addLayer(new_layer)
                        outras_count += 1
                    else:
                        # Adicionar ao grupo principal
                        self.groupMain.addLayer(new_layer)

                    # Aplicar estilo baseado na camada original
                    original_type = self.identifyLayerTypeForStyling(layer_name)
                    if original_type:
                        self.applyStyleToLayer(new_layer, original_type)
                    else:
                        self.applyStyleToLayer(new_layer, layer_name)

                    success_count += 1
                    print(f"✓ Camada carregada no projeto: {new_name}")
                else:
                    print(f"✗ Erro ao carregar camada renomeada no projeto: {new_name}")

            # PASSO 4: Remover as camadas originais após todas as cópias serem criadas
            print(f"\n--- REMOVENDO CAMADAS ORIGINAIS ---")
            for old_layer_name in layers_to_remove:
                print(f"Removendo camada antiga: {old_layer_name}")

                # Remover a camada do projeto se estiver carregada
                layers_in_project = QgsProject.instance().mapLayers()
                for layer_id, layer in layers_in_project.items():
                    if layer.name() == old_layer_name:
                        QgsProject.instance().removeMapLayer(layer_id)
                        print(f"  ✓ Removida do projeto: {old_layer_name}")
                        break
                    
                # Remover fisicamente do geopackage
                if self.removeLayersOfGeopackage(target_path, old_layer_name):
                    print(f"  ✓ Removida do arquivo: {old_layer_name}")
                else:
                    print(f"  ✗ Erro ao remover do arquivo: {old_layer_name}")

            # Atualizar interface
            iface.mapCanvas().refresh()

            print(f"\n=== RESULTADO ===")
            print(f"Camadas renomeadas com sucesso: {success_count}/{len(selected_layers)} (Outras: {outras_count})")

            return success_count > 0

        except Exception as e:
            print(f"Erro em renameExistingLayers: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
