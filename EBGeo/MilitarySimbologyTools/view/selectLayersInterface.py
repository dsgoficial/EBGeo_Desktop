# -*- coding: UTF-8 -*-
import os
from qgis.PyQt import uic, QtCore, QtWidgets
from qgis.PyQt.QtCore import pyqtSlot, pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (QMessageBox, QFileDialog, QCheckBox, QVBoxLayout, 
                               QHBoxLayout, QGroupBox, QLabel, QPushButton, QLineEdit,
                               QWidget, QSpinBox)
from qgis.PyQt.QtGui import QIcon
from ..model.baseDeDados import BaseDeDados


class SelectLayersInterface(QtWidgets.QDialog):
    layersSelected = pyqtSignal(list)
    
    def __init__(self, parent=None, layerNames=None):
        super(SelectLayersInterface, self).__init__(parent)
        self.layerNames = layerNames or []
        self.selectedLayers = []
        self.edit_mode = None
        
        # Agora todas as camadas são duplicáveis
        self.duplicableLayerTypes = self.layerNames.copy()
            
        self.duplicatedLayers = {}  # Para armazenar camadas duplicadas
        self.nextIndex = {}  # Para armazenar o próximo índice para cada tipo de camada
        self.removedIndices = {}  # Para armazenar índices removidos (para reutilização)
        
        for layer in self.duplicableLayerTypes:
            self.nextIndex[layer] = 2  # Começar com 2 (original = 1)
            self.removedIndices[layer] = []  # Lista de índices removidos que podem ser reutilizados
                    
    def setup_ui(self):
        """Configura a interface programaticamente"""
        # Configurar o diálogo
        self.setWindowTitle("Selecionar Camadas")
        self.resize(600, 650)
        self.setMinimumSize(500, 550)
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        
        # Texto explicativo
        header_label = QLabel("Selecione as camadas que deseja incluir:")
        header_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(header_label)
        
        # Adicionar label explicativo para duplicação
        duplication_label = QLabel("Para adicionar múltiplas instâncias de uma camada, clique no botão + ao lado de cada camada.")
        duplication_label.setStyleSheet("font-style: italic; color: #555;")
        main_layout.addWidget(duplication_label)
        
        # Área de rolagem para as camadas
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        
        # Widget do conteúdo da área de rolagem
        self.content_widget = QtWidgets.QWidget()
        scroll_area.setWidget(self.content_widget)
        
        # Layout do conteúdo (onde adicionaremos as categorias e checkboxes)
        self.content_layout = QVBoxLayout(self.content_widget)
        
        # Adicionar checkboxes organizados por categorias
        self.add_categorized_checkboxes()
        
        # Botões de seleção
        buttons_layout = QHBoxLayout()
        
        self.select_all_button = QtWidgets.QPushButton("Selecionar Todas")
        self.select_all_button.clicked.connect(self.selectAll)
        buttons_layout.addWidget(self.select_all_button)
        
        self.unselect_all_button = QtWidgets.QPushButton("Desmarcar Todas")
        self.unselect_all_button.clicked.connect(self.unselectAll)
        buttons_layout.addWidget(self.unselect_all_button)
        
        main_layout.addLayout(buttons_layout)
        
        # Botões de OK/Cancelar
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.acceptSelection)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
    def add_categorized_checkboxes(self):
        """Adiciona checkboxes organizados por categorias com verificação especial para camadas numeradas"""
        if self.edit_mode is None:
            print("AVISO: edit_mode não foi definido! Usando True como padrão.")
            self.edit_mode = True

        # Organizar camadas em categorias
        categorized_layers = self.categorize_layers()

        if "Símbolos e Pontos" in categorized_layers and len(categorized_layers["Símbolos e Pontos"]) == 2:
            categorized_layers["Símbolos e Pontos"] = ["Símbolos (pontos)"]

        # Debug: imprimir todas as camadas recebidas para diagnóstico
        print(f"Total de camadas recebidas pela interface: {len(self.layerNames)}")
        print(f"Camadas a exibir: {self.layerNames}")

        # Verificar especificamente camadas numeradas
        numbered_layers = [name for name in self.layerNames 
                          if '_' in name and name.split('_')[-1].isdigit()]
        print(f"Camadas numeradas identificadas: {numbered_layers}")

        # Adicionar categorias e camadas
        self.checkboxes = {}
        self.duplicated_widgets = {}  # Para armazenar widgets de camadas duplicadas

        # Lista para rastrear quais camadas já foram adicionadas
        added_layers = set()

        # Primeiro, processar as categorias normais
        for category, layers in categorized_layers.items():
            if not layers:
                continue  # Pular categorias vazias
            
            print(f"Processando categoria {category} com {len(layers)} camadas")

            # Criar grupo para a categoria
            group_box = QGroupBox(category)
            group_layout = QVBoxLayout(group_box)

            # Adicionar camadas da categoria
            for name in layers:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)

                display_name = self.get_display_name(name)

                # Debug: verificar se o nome está sendo formatado corretamente
                print(f"Adicionando camada: {name} -> {display_name}")

                checkbox = QCheckBox(display_name)
                if 'TEMPLATE' in name:
                    checkbox.setChecked(False)  # Por padrão, todas estão selecionadas
                else:
                    checkbox.setChecked(True)
                checkbox.setProperty("layer_name", name)
                self.checkboxes[name] = checkbox
                row_layout.addWidget(checkbox)

                if self.edit_mode:
                    rename_field = QLineEdit(display_name)
                    rename_field.setPlaceholderText("Nome da camada")
                    rename_field.setProperty("layer_name", name)
                    rename_field.textChanged.connect(self.update_original_name)
                    row_layout.addWidget(rename_field)

                    checkbox.setProperty("rename_field", rename_field)

                    if "Template" in category:
                        # Todas as camadas agora têm botão de duplicar
                        add_button = QPushButton("+")
                        add_button.setMaximumWidth(30)
                        add_button.setToolTip(f"Adicionar outra camada de {display_name}")
                        add_button.setProperty("layer_name", name)
                        add_button.clicked.connect(self.duplicate_layer)
                        row_layout.addWidget(add_button)

                row_layout.addStretch()  # Para manter os widgets alinhados à esquerda
                group_layout.addWidget(row_widget)

                # Criar contêiner para as camadas duplicadas deste tipo
                if self.edit_mode:
                    duplicates_container = QWidget()
                    duplicates_layout = QVBoxLayout(duplicates_container)
                    duplicates_layout.setContentsMargins(20, 0, 0, 0)  # Indentação para duplicatas
                    self.duplicated_widgets[name] = duplicates_container
                    group_layout.addWidget(duplicates_container)

                # Marcar esta camada como adicionada
                added_layers.add(name)

            # Adicionar grupo ao layout principal
            self.content_layout.addWidget(group_box)

        # Verificar se alguma camada não foi adicionada
        missing_layers = [layer for layer in self.layerNames if layer not in added_layers]

        # Verificar especialmente se as camadas numeradas foram todas adicionadas
        missing_numbered = [layer for layer in numbered_layers if layer not in added_layers]
        if missing_numbered:
            print(f"ALERTA: {len(missing_numbered)} camadas numeradas não foram adicionadas: {missing_numbered}")

        # Se houver camadas não categorizadas, adicionar em um grupo separado
        if missing_layers:
            # Criar grupo para camadas não categorizadas
            uncategorized_group = QGroupBox("Camadas Não Categorizadas")
            uncategorized_layout = QVBoxLayout(uncategorized_group)

            print(f"Adicionando {len(missing_layers)} camadas não categorizadas: {missing_layers}")

            for name in missing_layers:
                # FILTRO REMOVIDO: Não excluir mais as camadas "outras"
                self.content_layout.addWidget(uncategorized_group)
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)

                # Checkbox para selecionar a camada
                display_name = self.get_display_name(name)
                print(f"Adicionando camada não categorizada: {name} -> {display_name}")

                checkbox = QCheckBox(display_name)
                if 'TEMPLATE' in name:
                    checkbox.setChecked(False)
                else:
                    checkbox.setChecked(True)
                checkbox.setProperty("layer_name", name)
                self.checkboxes[name] = checkbox
                row_layout.addWidget(checkbox)

                if self.edit_mode:
                    # Campo para renomear a camada
                    rename_field = QLineEdit(display_name)
                    rename_field.setPlaceholderText("Nome personalizado")
                    rename_field.setProperty("layer_name", name)
                    rename_field.textChanged.connect(self.update_original_name)
                    row_layout.addWidget(rename_field)

                    if "Template" in category:
                        # Botão de duplicar
                        add_button = QPushButton("+")
                        add_button.setMaximumWidth(30)
                        add_button.setToolTip(f"Adicionar outra camada de {display_name}")
                        add_button.setProperty("layer_name", name)
                        add_button.clicked.connect(self.duplicate_layer)
                        row_layout.addWidget(add_button)

                row_layout.addStretch()
                uncategorized_layout.addWidget(row_widget)

                # Criar contêiner para duplicatas
                if self.edit_mode:
                    duplicates_container = QWidget()
                    duplicates_layout = QVBoxLayout(duplicates_container)
                    duplicates_layout.setContentsMargins(20, 0, 0, 0)
                    self.duplicated_widgets[name] = duplicates_container
                    uncategorized_layout.addWidget(duplicates_container)

    def update_original_name(self, new_text):
        """Atualiza o nome customizado de uma camada original"""
        sender = self.sender()
        layer_name = sender.property("layer_name")
    
        if layer_name in self.checkboxes:
            # Armazenar o novo nome personalizado
            if not hasattr(self, 'originalCustomNames'):
                self.originalCustomNames = {}
            self.originalCustomNames[layer_name] = new_text
            self.checkboxes[layer_name].setText(new_text)
    
    def duplicate_layer(self):
        """Adiciona uma camada duplicada do tipo selecionado"""
        sender = self.sender()
        layer_name = sender.property("layer_name")
        
        # Determinar o próximo índice a usar
        if self.removedIndices[layer_name]:
            # Se houver índices removidos, use o menor deles
            next_index = min(self.removedIndices[layer_name])
            self.removedIndices[layer_name].remove(next_index)
        else:
            # Caso contrário, use o próximo índice sequencial
            next_index = self.nextIndex[layer_name]
            self.nextIndex[layer_name] += 1
            
        # Criar um novo ID único para a camada duplicada
        new_layer_name = f"{layer_name}_{next_index}"
        display_name = self.get_display_name(layer_name)
        
        # Criar o widget para a camada duplicada
        duplicate_widget = QWidget()
        duplicate_layout = QHBoxLayout(duplicate_widget)
        duplicate_layout.setContentsMargins(0, 0, 0, 0)
        
        # Checkbox para a camada duplicada
        duplicate_checkbox = QCheckBox(f"{display_name} {next_index}")
        duplicate_checkbox.setChecked(True)
        duplicate_checkbox.setProperty("layer_name", new_layer_name)
        duplicate_checkbox.setProperty("is_duplicate", True)
        duplicate_checkbox.setProperty("original_layer", layer_name)
        duplicate_checkbox.setProperty("index", next_index)  # Armazenar o índice usado
        self.checkboxes[new_layer_name] = duplicate_checkbox
        duplicate_layout.addWidget(duplicate_checkbox)
        
        # Campo para renomear a camada
        rename_field = QLineEdit(f"{display_name} {next_index}")
        rename_field.setPlaceholderText("Nome personalizado")
        rename_field.setProperty("layer_name", new_layer_name)
        rename_field.textChanged.connect(self.update_duplicate_name)
        duplicate_layout.addWidget(rename_field)
        
        # Botão para remover a camada duplicada
        remove_button = QPushButton("×")
        remove_button.setMaximumWidth(30)
        remove_button.setToolTip("Remover esta camada")
        remove_button.setProperty("layer_name", new_layer_name)
        remove_button.setProperty("index", next_index)
        remove_button.clicked.connect(self.remove_duplicate)
        duplicate_layout.addWidget(remove_button)
        
        # Adicionar ao contêiner de duplicatas
        duplicates_container = self.duplicated_widgets[layer_name]
        duplicates_container.layout().addWidget(duplicate_widget)
        
        # Armazenar a camada duplicada
        if layer_name not in self.duplicatedLayers:
            self.duplicatedLayers[layer_name] = []
        self.duplicatedLayers[layer_name].append({
            'new_name': new_layer_name,
            'widget': duplicate_widget,
            'rename_field': rename_field,
            'index': next_index
        })
    
    def update_duplicate_name(self, new_text):
        """Atualiza o texto do checkbox quando o usuário altera o nome"""
        sender = self.sender()
        layer_name = sender.property("layer_name")
        
        if layer_name in self.checkboxes:
            self.checkboxes[layer_name].setText(new_text)
    
    def remove_duplicate(self):
        """Remove uma camada duplicada"""
        sender = self.sender()
        layer_name = sender.property("layer_name")
        index = sender.property("index")
        
        # Encontrar o widget da camada duplicada
        for original_layer, duplicates in self.duplicatedLayers.items():
            for i, duplicate in enumerate(duplicates):
                if duplicate['new_name'] == layer_name:
                    # Remover o widget
                    duplicate['widget'].deleteLater()
                    # Remover o checkbox do dicionário
                    if layer_name in self.checkboxes:
                        del self.checkboxes[layer_name]
                    # Remover da lista de duplicatas
                    self.duplicatedLayers[original_layer].pop(i)
                    # Adicionar o índice à lista de índices removidos para reutilização
                    self.removedIndices[original_layer].append(index)
                    return
    
    def categorize_layers(self):
        """
        Versão atualizada que organiza camadas incluindo prefixos [EXISTENTE] e [TEMPLATE]
        """
        categories = {
            "Camadas Existentes - Principais": [],
            "Camadas Existentes - Limites e Linhas": [],
            "Camadas Existentes - Símbolos": [],
            "Template - Coordenação e Apoio": [],
            "Template - Eixos e Direções": [],
            "Template - Fortificações": [],
            "Template - Limites e Controles": [],
            "Template - Símbolos e Pontos": [],
            "Template - Outras": [],
            "Camadas Raster": [],
        }

        for name in self.layerNames:
            # Extrair nome limpo e fonte
            original_name = name
            is_existing = False
            is_template = False

            if 'barragem_grupo_concentracao' in name or 'barreiras' in name or 'redes' in name or name == 'fortificacoes_ot':
                continue

            if name.startswith("[EXISTENTE] "):
                original_name = name.replace("[EXISTENTE] ", "")
                is_existing = True
            elif name.startswith("[TEMPLATE] "):
                original_name = name.replace("[TEMPLATE] ", "")
                is_template = True

            name_lower = original_name.lower()

            # Categorizar camadas raster
            if original_name.startswith("raster_"):
                categories["Camadas Raster"].append(name)
                continue
            
            # Determinar categoria base
            category_base = None

            # Coordenação e Apoio de Fogo
            if any(keyword in name_lower for keyword in ['coord', 'apoio', 'fogo']):
                if is_existing:
                    category_base = "Camadas Existentes - Principais"
                elif is_template:
                    category_base = "Template - Coordenação e Apoio"

            # Eixos e Direções
            elif any(keyword in name_lower for keyword in ['eixo', 'direç', 'direcao']):
                if is_existing:
                    category_base = "Camadas Existentes - Principais"
                elif is_template:
                    category_base = "Template - Eixos e Direções"

            # Fortificações
            elif any(keyword in name_lower for keyword in ['fortificaç', 'pontos', 'fortes', 'pf']):
                if is_existing:
                    category_base = "Camadas Existentes - Principais"
                elif is_template:
                    category_base = "Template - Fortificações"

            # Limites e Controles
            elif any(keyword in name_lower for keyword in ['limite', 'linha', 'controle', 'fraç', 'obstáculo', 'obstaculos', 'obstáculos', 'obstaculo']):
                if is_existing:
                    category_base = "Camadas Existentes - Limites e Linhas"
                elif is_template:
                    category_base = "Template - Limites e Controles"

            # Símbolos e Pontos
            elif any(keyword in name_lower for keyword in ['símbolo', 'simbolo', 'seta', 'situação', 'situacao']):
                if is_existing:
                    category_base = "Camadas Existentes - Símbolos"
                elif is_template:
                    category_base = "Template - Símbolos e Pontos"

            # Fallback para nomes técnicos conhecidos
            elif original_name in [
                'coord_ap_fogo', 'eixo_de_direcao', 'fortificacoes_pf',
                'limite_entre_fracoes', 'linha_de_controle', 'seta_situacao', 'simbolos_pontos', 'obstaculos'
            ]:
                if is_existing:
                    category_base = "Camadas Existentes - Principais"
                elif is_template:
                    if 'coord' in original_name or 'fogo' in original_name:
                        category_base = "Template - Coordenação e Apoio"
                    elif 'eixo' in original_name:
                        category_base = "Template - Eixos e Direções"
                    elif 'fortificacoes' in original_name:
                        category_base = "Template - Fortificações"
                    elif 'limite' in original_name or 'linha' in original_name:
                        category_base = "Template - Limites e Controles"
                    elif 'seta' in original_name or 'simbolos' in original_name:
                        category_base = "Template - Símbolos e Pontos"

            # Categoria padrão se não foi classificado
            if not category_base:
                if is_template:
                    category_base = "Template - Outras"
                else:
                    # Sem prefixo, assumir template
                    category_base = "Template - Outras"

            # Adicionar à categoria
            if category_base:
                categories[category_base].append(name)

        # Remover categorias vazias e ordenar
        filtered_categories = {}
        for category, layers in categories.items():
            if layers:
                filtered_categories[category] = sorted(layers)

        print(f"Categorias criadas: {list(filtered_categories.keys())}")
        for cat, layers in filtered_categories.items():
            print(f"  {cat}: {len(layers)} camadas")

        return filtered_categories
    
    def get_display_name(self, name):
        """
        Versão atualizada que lida com prefixos [EXISTENTE] e [TEMPLATE]
        Agora com melhor suporte para as "outras camadas"
        """
        print(f"Gerando nome de exibição para: {name}")

        # Primeiro, remover prefixos se existirem e extrair o tipo
        original_name = name
        layer_source = None

        if name.startswith("[EXISTENTE] "):
            original_name = name.replace("[EXISTENTE] ", "")
            layer_source = "EXISTENTE"
        elif name.startswith("[TEMPLATE] "):
            original_name = name.replace("[TEMPLATE] ", "")
            layer_source = "TEMPLATE"

        # Para camadas raster, remover o prefixo 'raster_'
        if original_name.startswith("raster_"):
            display_name = "Raster: " + original_name[7:]

        # Se o nome já parece ser um nome personalizado/amigável 
        elif any(char in original_name for char in [' ', '-', 'ç', 'ã', 'õ', 'á', 'é', 'í', 'ó', 'ú']):
            display_name = original_name

        # Verificar camadas com numeração direta (ex: fortificacoes_pf_2)
        elif '_' in original_name and original_name.split('_')[-1].isdigit():
            number = original_name.split('_')[-1]
            base_name = '_'.join(original_name.split('_')[:-1])

            try:
                listName = BaseDeDados().listName
                if base_name in listName:
                    display_name = f"{listName[base_name]} {number}"
                else:
                    display_name = f"{base_name.replace('_', ' ').title()} {number}"
            except:
                display_name = f"{base_name.replace('_', ' ').title()} {number}"

        # Verificar se há um nome amigável no dicionário para camadas regulares
        else:
            try:
                listName = BaseDeDados().listName
                if original_name in listName:
                    display_name = listName[original_name]
                else:
                    display_name = original_name.replace('_', ' ').title()
            except:
                display_name = original_name.replace('_', ' ').title()

        # Adicionar indicador de origem se aplicável
        if layer_source == "EXISTENTE":
            display_name = f"{display_name}"  # Emoji de pasta para existentes
        elif layer_source == "TEMPLATE":
            display_name = f"{display_name}"  # Emoji de prancheta para template

        print(f"Nome de exibição final: {display_name}")
        return display_name
    
    def selectAll(self):
        """Seleciona todas as camadas"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
            
    def unselectAll(self):
        """Desmarca todas as camadas"""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
            
    def acceptSelection(self):
        """Confirma a seleção de camadas"""
        # Obter a lista de camadas selecionadas usando o nome original armazenado
        selected_layers = []
        custom_names = {}  # Para mapear nomes customizados
        display_names = []  # Lista para verificar nomes duplicados na interface
        
        for name, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                is_duplicate = checkbox.property("is_duplicate")

                if not self.edit_mode:
                    # Simplesmente adicionar à lista de selecionados
                    selected_layers.append(name)
                    continue

                if is_duplicate:
                    display_name = checkbox.text()  # Nome exibido na interface
                else:
                    # Para originais, usar o valor do campo de texto ou o nome padrão
                    if hasattr(self, 'originalCustomNames') and name in self.originalCustomNames:
                        display_name = self.originalCustomNames[name]
                    else:
                        display_name = self.get_display_name(name)
                
                # Verificar se o nome de exibição já existe na lista
                if display_name in display_names:
                    if display_name == "''":
                        continue
                    # Nome duplicado encontrado na interface - mostrar aviso
                    QMessageBox.warning(
                        self, 
                        u"Aviso", 
                        u"Não é possível prosseguir!\n\n"
                        f"A camada '{display_name}' aparece mais de uma vez na sua seleção.\n"
                        u"Por favor, renomeie uma das camadas ou desmarque uma das ocorrências."
                    )
                    return  # Impedir que o diálogo seja fechado
                
                display_names.append(display_name)
                
                if is_duplicate:
                    # Para camadas duplicadas, armazenar o nome original e o texto personalizado
                    original_layer = checkbox.property("original_layer")
                    custom_name = checkbox.text()
                    selected_layers.append(name)
                    custom_names[name] = {
                        'original_layer': original_layer,
                        'custom_name': custom_name
                    }
                else:
                    # Camadas normais
                    selected_layers.append(name)
                    if hasattr(self, 'originalCustomNames') and name in self.originalCustomNames:
                        custom_name = self.originalCustomNames[name]
                        custom_names[name] = {
                            'original_layer': name,
                            'custom_name': custom_name,
                            'is_original_renamed': True
                        }
                    
        if not selected_layers:
            QMessageBox.warning(self, u"Aviso", u"Nenhuma camada selecionada. Selecione pelo menos uma camada.")
            return
        
        # Armazenar os resultados
        self.selectedLayers = selected_layers
        self.customNames = custom_names
        
        self.layersSelected.emit(self.selectedLayers)
        self.accept()
        
    def get_duplicate_info(self):
        """Retorna informações sobre as camadas duplicadas e seus nomes personalizados"""
        duplicate_info = self.customNames if hasattr(self, 'customNames') else {}

        if hasattr(self, 'originalCustomNames'):
            for layer_name, custom_name in self.originalCustomNames.items():
                # Verificar se a camada foi selecionada (está no self.selectedLayers)
                if layer_name in self.selectedLayers:
                    duplicate_info[layer_name] = {
                        'original_layer': layer_name,
                        'custom_name': custom_name,
                        'is_original_renamed': True
                    }

        return duplicate_info
    
    def setEditMode(self, edit_mode=True):
        """Define se todas as camadas devem ser editáveis"""
        self.edit_mode = edit_mode
        self.setup_ui()