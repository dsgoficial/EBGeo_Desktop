# -*- coding: UTF-8 -*-
import os
from MilitarySimbologyTools.view.selectLayersInterface import SelectLayersInterface
from PyQt5 import uic, QtCore, QtWidgets
from qgis.PyQt.QtCore import pyqtSlot, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from .createDataBaseInterface import CreateDataBaseInterface
from ..model.baseDeDados import BaseDeDados

GUI, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'militarySimbologyInterface.ui'))

class MilitarySimbologyInterface(QtWidgets.QFrame, GUI):
    def __init__(self):
        super(MilitarySimbologyInterface, self).__init__()
        self.setupUi(self)
        self.initVariables()
        self.setCreateDataBaseInterface(CreateDataBaseInterface(self))

    def initVariables(self):
        self.controller = None
        self.dataBasePath = None
        self.createDataBaseInterface = None
        self.currentScale = None
        self.baseDeDados = BaseDeDados()

    def setCreateDataBaseInterface(self, i):
        self.createDataBaseInterface = i

    def getCreateDataBaseInterface(self):
        return self.createDataBaseInterface

    def msg(self, msg):
        QMessageBox.warning(self, u"Aviso:", msg, QMessageBox.Close)

    def setDataBase(self):
        dataBasePath = QFileDialog.getOpenFileName(self, 'Selecionar Geopackage', '', "Selecione banco de dados (*.gpkg)")[0]
        if dataBasePath:
            self.dataBasePath = dataBasePath
            self.baseDeDados.setCurrentDatabase(self.dataBasePath)

            # Verificar se é um projeto ou camadas soltas
            projects = self.baseDeDados.checkTableFromDatabase('qgis_projects')
            if projects[0] != 'table not available':
                # Se for um projeto, carregá-lo diretamente
                loadResult = self.baseDeDados.loadProject()
                if loadResult == 2:
                    self.msg(u'Projeto carregado com sucesso!')
                    return 1
                else:
                    self.msg(u'Erro ao carregar o projeto!')
                    return 0

            # Se forem camadas soltas, mostrar diálogo de seleção
            # Obter lista de camadas disponíveis
            vector_layers = self.baseDeDados.getLayerList()
            raster_layers = self.baseDeDados.getRasterLayerList()
            print("Camadas vetoriais encontradas:")
            print(vector_layers)
            all_layers = vector_layers + raster_layers

            if all_layers:
                # Exibir diálogo de seleção de camadas
                select_dialog = SelectLayersInterface(self, all_layers)
                select_dialog.setWindowTitle("Selecionar Camadas para Carregamento")
                select_dialog.setEditMode(False)

                if select_dialog.exec_():
                    # Se o usuário confirmar a seleção
                    selected_layers = select_dialog.selectedLayers
                    duplicate_info = select_dialog.get_duplicate_info()

                    if selected_layers:
                        # IMPORTANTE: Passar existing_geopackage=True para usar a lógica correta
                        loadResult = self.baseDeDados.loadSelectedLayersWithDuplicates(
                            selected_layers, 
                            duplicate_info, 
                            existing_geopackage=True  # Flag crucial para geopackages existentes
                        )
                        if loadResult == 1:
                            self.msg(u'Camadas selecionadas carregadas com sucesso!')
                            return 1
                        else:
                            self.msg(u'Erro ao carregar as camadas selecionadas!')
                            return 0
                    else:
                        self.msg(u'Nenhuma camada foi selecionada.')
                        return 0
                else:
                    # Se o usuário cancelar a seleção
                    return 0
            else:
                # Se não houver camadas ou ocorrer erro ao obter as camadas
                self.msg(u'Não foi possível obter a lista de camadas do banco de dados.')
                return 0
        else:
            return 0
        
    def layersSelectedForAddInGeopackage(self, template_layers):
        # Exibir diálogo de seleção de camadas diretamente
        select_dialog = SelectLayersInterface(self, template_layers)
        select_dialog.setWindowTitle("Selecionar Camadas para Criação")
        select_dialog.setEditMode(True)

        # Se o usuário cancelar a seleção
        if not select_dialog.exec_():
            return 0

        selected_layers = select_dialog.selectedLayers
        duplicate_info = select_dialog.get_duplicate_info()

        if not selected_layers:
            QMessageBox.warning(self, u"Aviso:", u"Nenhuma camada foi selecionada.")
            return 0
    
        return select_dialog, duplicate_info

    @pyqtSlot(bool)
    def on_createDatabaseButton_clicked(self): #modificado para criar e já carregar
        self.getCreateDataBaseInterface().showDialog()

    @pyqtSlot(bool)
    def on_loadDatabaseButton_clicked(self): #seleciona o banco e já carrega
        if self.setDataBase():
            self.close()

    @pyqtSlot(bool)
    def on_addToExistingButton_clicked(self):
        """Adiciona camadas de simbologia militar a um arquivo existente"""
        # Selecionar arquivo existente
        dataBasePath = QFileDialog.getOpenFileName(self, 'Selecionar Geopackage Existente', '', 
                                                   "Arquivos Geopackage (*.gpkg)")[0]
        if not dataBasePath:
            return
    
        print(f"=== ADICIONAR A GEOPACKAGE EXISTENTE ===")
        print(f"Arquivo selecionado: {dataBasePath}")
    
        # Definir o banco de dados de destino temporariamente para ler as camadas existentes
        current_db = self.baseDeDados.Database  # Salvar o estado atual
        self.baseDeDados.setCurrentDatabase(dataBasePath)
    
        try:
            # Obter camadas que já existem no geopackage de destino
            existing_layers = self.baseDeDados.getLayerList()
            print(f"Camadas existentes no destino: {existing_layers}")
    
            # Obter lista de camadas do template
            template_layers = self.baseDeDados.getTemplateLayerList()
            print(f"Camadas do template: {template_layers}")
    
            # Combinar ambas as listas, marcando a origem
            all_available_layers = []
    
            # Adicionar camadas existentes com prefixo indicativo
            for layer in existing_layers:
                all_available_layers.append(f"[EXISTENTE] {layer}")
    
            # Adicionar camadas do template com prefixo indicativo
            for layer in template_layers:
                all_available_layers.append(f"[TEMPLATE] {layer}")
    
            print(f"Todas as camadas disponíveis: {all_available_layers}")
    
            if not all_available_layers:
                QMessageBox.warning(self, u"Aviso:", u"Nenhuma camada disponível encontrada.")
                return
    
            # Exibir diálogo de seleção com todas as camadas
            select_dialog = SelectLayersInterface(self, all_available_layers)
            select_dialog.setWindowTitle("Selecionar Camadas para Adicionar")
            select_dialog.setEditMode(True)
    
            if not select_dialog.exec_():
                return
    
            selected_layers = select_dialog.selectedLayers
            duplicate_info = select_dialog.get_duplicate_info()
    
            if not selected_layers:
                QMessageBox.warning(self, u"Aviso:", u"Nenhuma camada foi selecionada.")
                return
    
            print(f"Camadas selecionadas: {selected_layers}")
            print(f"Info de duplicatas: {duplicate_info}")
    
            # Separar camadas por tipo e ação
            template_selections = []
            existing_to_load = []      # Camadas existentes para carregar (sem modificar)
            existing_to_rename = []    # Camadas existentes para renomear
            existing_to_duplicate = [] # Camadas existentes para duplicar
    
            for layer_name in selected_layers:
                # Verificar se tem prefixo e remover
                if layer_name.startswith("[TEMPLATE] "):
                    clean_name = layer_name.replace("[TEMPLATE] ", "")
                    template_selections.append(clean_name)
                elif layer_name.startswith("[EXISTENTE] "):
                    clean_name = layer_name.replace("[EXISTENTE] ", "")
    
                    # Verificar se houve modificação
                    if layer_name in duplicate_info:
                        info = duplicate_info[layer_name]
                        custom_name = info.get('custom_name', clean_name)
                        
                        # Se o nome foi modificado
                        if custom_name != clean_name:
                            # Verificar se é uma duplicata intencional (com sufixo número)
                            if '_' in custom_name and custom_name.split('_')[-1].isdigit():
                                existing_to_duplicate.append(clean_name)
                                print(f"Camada existente '{clean_name}' será duplicada como '{custom_name}'")
                            else:
                                # É uma renomeação simples
                                existing_to_rename.append(clean_name)
                                print(f"Camada existente '{clean_name}' será RENOMEADA para '{custom_name}'")
                        else:
                            # Nome não foi modificado, apenas carregar
                            existing_to_load.append(clean_name)
                    else:
                        # Sem info especial, apenas carregar
                        existing_to_load.append(clean_name)
                else:
                    # Fallback: assumir que é do template se não tem prefixo
                    template_selections.append(layer_name)
    
            print(f"Seleções do template: {template_selections}")
            print(f"Existentes para carregar: {existing_to_load}")
            print(f"Existentes para renomear: {existing_to_rename}")
            print(f"Existentes para duplicar: {existing_to_duplicate}")
    
            # Processar duplicate_info para remover prefixos
            cleaned_duplicate_info = {}
            for key, value in duplicate_info.items():
                # Remover prefixo da chave
                clean_key = key
                if key.startswith("[TEMPLATE] "):
                    clean_key = key.replace("[TEMPLATE] ", "")
                elif key.startswith("[EXISTENTE] "):
                    clean_key = key.replace("[EXISTENTE] ", "")
    
                # Remover prefixo do original_layer se existir
                if 'original_layer' in value:
                    original = value['original_layer']
                    if original.startswith("[TEMPLATE] "):
                        value['original_layer'] = original.replace("[TEMPLATE] ", "")
                    elif original.startswith("[EXISTENTE] "):
                        value['original_layer'] = original.replace("[EXISTENTE] ", "")
    
                cleaned_duplicate_info[clean_key] = value
    
            print(f"Duplicate info limpo: {cleaned_duplicate_info}")
    
            success_count = 0
    
            # 1. Adicionar/duplicar camadas do template
            if template_selections:
                print(f"\n--- PROCESSANDO CAMADAS DO TEMPLATE ---")
                result = self.baseDeDados.addTemplateLayersToExistingGeopackage(
                    template_selections, cleaned_duplicate_info
                )
                if result:
                    success_count += 1
                    print("✓ Camadas do template adicionadas com sucesso")
    
            # 2. Carregar camadas existentes (SEM modificar)
            if existing_to_load:
                print(f"\n--- CARREGANDO CAMADAS EXISTENTES ---")
                result = self.baseDeDados.loadExistingLayersOnly(
                    existing_to_load, cleaned_duplicate_info
                )
                if result:
                    success_count += 1
                    print("✓ Camadas existentes carregadas com sucesso")
    
            # 3. RENOMEAR camadas existentes (nova função)
            if existing_to_rename:
                print(f"\n--- RENOMEANDO CAMADAS EXISTENTES ---")
                result = self.baseDeDados.renameExistingLayers(
                    existing_to_rename, cleaned_duplicate_info
                )
                if result:
                    success_count += 1
                    print("✓ Camadas existentes renomeadas com sucesso")
    
            # 4. Duplicar camadas existentes (mantém original)
            if existing_to_duplicate:
                print(f"\n--- DUPLICANDO CAMADAS EXISTENTES ---")
                result = self.baseDeDados.duplicateExistingLayers(
                    existing_to_duplicate, cleaned_duplicate_info
                )
                if result:
                    success_count += 1
                    print("✓ Duplicatas de camadas existentes criadas com sucesso")
    
            # Mostrar resultado final
            if success_count > 0:
                message_parts = []
                if template_selections:
                    message_parts.append(f"{len(template_selections)} camadas do template")
                if existing_to_load:
                    message_parts.append(f"{len(existing_to_load)} camadas existentes carregadas")
                if existing_to_rename:
                    message_parts.append(f"{len(existing_to_rename)} camadas renomeadas")
                if existing_to_duplicate:
                    message_parts.append(f"{len(existing_to_duplicate)} duplicatas criadas")
    
                message = f"Operação concluída com sucesso!\n\nProcessadas: {' e '.join(message_parts)}"
                QMessageBox.information(self, u"Sucesso", message)
            else:
                QMessageBox.warning(self, u"Aviso", u"Nenhuma operação foi realizada.")
    
        except Exception as e:
            QMessageBox.critical(self, u"Erro", f"Erro ao processar: {str(e)}")
            print(f"Erro: {str(e)}")
            import traceback
            traceback.print_exc()
    
        finally:
            # Restaurar o banco de dados original
            if current_db:
                self.baseDeDados.setCurrentDatabase(current_db)