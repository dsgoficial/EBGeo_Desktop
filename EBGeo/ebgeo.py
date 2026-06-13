# -*- coding: utf-8 -*-
import os, sys, webbrowser
from qgis.utils import iface
currentPath = os.path.dirname(__file__)
sys.path.append(os.path.abspath(currentPath))
from qgis.core import QgsMapLayer, QgsProject, QgsApplication, QgsProject
from qgis.PyQt.QtWidgets import QMessageBox, QMenu, QDockWidget
from qgis.PyQt.QtGui import QIcon, QAction
from .BDGEx.bdgexGuiManager import BDGExGuiManager
from .Processings.pluginProvider import pluginProvider
from .VisibilityAnalysis.visibilityAnalysis import VisibilityAnalysis as Main_VisibilityAnalisys
from .ZoomCoordenadas.main import ZoomToDockWidget
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import pyqtSignal, QObject, Qt
from qgis.core import QgsVectorLayer, Qgis


# sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),'auxiliar'))

class EBGeo(QObject):

	editingStarted = pyqtSignal()
	editingStopped = pyqtSignal()

	def __init__(self, iface: QgisInterface):
		super(EBGeo, self).__init__()
		self.iface = iface
		self.currentLayer = None
		self.resetCurrentLayerSignals()
		self.iface.currentLayerChanged.connect(self.resetCurrentLayerSignals)
		self.actions = []
		self.toolbar = self.iface.addToolBar("EBGeo")
    	
	def initGui(self):
		self.initVariables()
		self.loadTools()
		pluginProvider.initProcessing(self)
		self.initiateToolsSignals()

	def initPlugin(self):
		pass

	def initVariables(self):
		self.menuBar = self.iface.mainWindow().menuBar()
		self.ebGeo = QMenu(self.iface.mainWindow())
		self.ebGeo.setObjectName(u'EBGeo')
		self.ebGeo.setTitle('EBGeo')
		self.fieldToolbox = None
		self.menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.ebGeo)

	def unload(self):
		self.iface.currentLayerChanged.disconnect(self.resetCurrentLayerSignals)
		for tool in [
			self.measureTool,
		]:
			# connect current layer changed signal to all tools that use it
			self.iface.currentLayerChanged.disconnect(tool.setToolEnabled)
			# connect editing started/stopped signals to all tools that use it
			self.editingStarted.disconnect(tool.setToolEnabled)
			self.editingStopped.disconnect(tool.setToolEnabled)
			# connect edit button toggling signal to all tools that use it
			self.iface.actionToggleEditing().triggered.disconnect(tool.setToolEnabled)
		QgsApplication.processingRegistry().removeProvider(self.provider)
		for action in self.actions:
			self.iface.removePluginMenu(u'EBGeo',	action)
			self.iface.removeToolBarIcon(action)
			self.iface.unregisterMainWindowAction(action)
			del action
		if hasattr(self, "qgisLightPlugin"):
			try:
				self.qgisLightPlugin.unload()
			except Exception as e:
				QgsApplication.messageLog().logMessage(
                f"Erro ao descarregar QGISLight: {e}", "EBGeo"
            )
		if self.ebGeo is not None:
			self.menuBar.removeAction(self.ebGeo.menuAction())
		del self.toolbar
		del self.ebGeo


	def addMenu(self, name, title, icon_file, parentMenu = None):
		self.menuList = []
		child = QMenu(self.ebGeo)
		child.setObjectName(name)
		child.setTitle(title)
		child.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icons', icon_file)))
		if parentMenu:
			parentMenu.addMenu(child)
		else:
			self.ebGeo.addMenu(child)
		self.menuList.append(child)
		return child

	def add_action(self,
				icon_path,
				text,
				callback,
				enabled_flag=True,
				add_to_menu=True,
				add_to_toolbar=True,
				status_tip=None,
				whats_this=None,
				parent=None):
        
		icon = QIcon(icon_path)
		action = QAction(icon, text, parent)
		action.triggered.connect(callback)
		action.setEnabled(enabled_flag)

		if status_tip is not None:
			action.setStatusTip(status_tip)

		if whats_this is not None:
			action.setWhatsThis(whats_this)

		if add_to_toolbar:
			self.toolbar.addAction(action)

		if add_to_menu:
			self.iface.addPluginToMenu(
				self.menu,
				action)

		self.actions.append(action)

		return action

	def loadTools(self):
		pass

		self.bdgexGuiManager = BDGExGuiManager(self, self.iface, self.ebGeo, toolbar = None)
		self.bdgexGuiManager.initGui()

		self.ms_action = self.add_action(
		 	os.path.join(os.path.dirname(__file__), 'icons', 'militarySimbology.png'),
		 	text=u'Simbologia Militar',
		 	callback=self.loadMilitarySimbology,
		 	parent=self.ebGeo,
		 	add_to_menu=False,
		 	add_to_toolbar=False)
		self.ebGeo.addAction(self.ms_action)

		self.nd_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'numericaldigitize.png'),
			text=u'Criação de pontos por coordenadas',
			callback=self.loadNumericalDigitize,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.nd_action)

		self.az_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'azimuth.png'),
			text=u'Criação de pontos por azimute e distância',
			callback=self.loadAzimuthTool,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.az_action.setCheckable(True)
		self.ebGeo.addAction(self.az_action)
		from .AzimuthDistance.azimuthTool import AzimuthTool as Main_AzimuthTool
		self.mainAzimuthTool = Main_AzimuthTool(iface)

		self.mv_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'numericalvertexedit.png'),
			text=u'Movimentação de pontos por coordenadas',
			callback=self.loadMoveVertex,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.mv_action)

		self.azgen_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'azimuthgen.png'),
			text=u'Quadro Auxiliar de Navegação (QAN)',
			callback=self.loadAzimuthGenerator,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.azgen_action)
		from .AzimuthGenerator.main import Main as Main_AzimuthGen
		self.mainAzimuthGen = Main_AzimuthGen(iface)

		self.ar_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'arearange.png'),
			text=u'Alcance de armamento',
			callback=self.loadAreaRange,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ar_action.setCheckable(True)
		self.ebGeo.addAction(self.ar_action)
		from .AreaRange.areaRange import AreaRange as Main_AreaRange
		self.mainAreaRange = Main_AreaRange(iface)

		# self.pt_action = self.add_action(
		# 	os.path.join(os.path.dirname(__file__), 'icons', 'profileIcon.png'),
		# 	text=u'Gerador de perfil do terreno',
		# 	callback=self.loadProfileTool,
		# 	parent=self.ebGeo,
		# 	add_to_menu=False,
		# 	add_to_toolbar=False)
		# self.ebGeo.addAction(self.pt_action)
		# from .ProfileTool.profileplugin import ProfilePlugin as Main_ProfileTool
		# self.mainProfileTool = Main_ProfileTool(iface)

		self.vis_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'visib.png'),
			text=u'Mapa de visibilidade',
			callback=self.loadVisibility,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.vis_action)
		from .Visibility.main import Main as Main_Visib
		self.mainVisib = Main_Visib(iface)

		self.los_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'visib.png'),
			text=u'Linha de Visada',
			callback=self.loadLineOfSight,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.los_action)

		self.mosaic_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'mosaic.png'),
			text=u'Gerador de Mosaicos',
			callback=self.loadMakeMosaic,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.mosaic_action)

		self.frame_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'GerarMoldura.png'),
			text=u'Grid (grade) de coordenadas da carta',
			callback=self.loadMakeFrame,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.frame_action)

		self.sd_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'shaderIcon.png'),
			text=u'Sombreador do terreno',
			callback=self.loadShaderTool,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.sd_action)
		from .Shader.main import Main as Main_Shader
		self.mainShaderTool = Main_Shader(iface)
		
		self.auc_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'convang.png'),
			text=u'Conversor de unidades angulares',
			callback=self.loadAngleUnitConverter,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.auc_action)

		from .measureTool.measureTool import MeasureTool as Main_MeasureTool
		self.measureTool = Main_MeasureTool(iface)
		self.mt_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'measuretool.png'),
			text=u'Medição durante aquisição vetorial',
			callback=self.measureTool.activateTool,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.measureTool.setAction(self.mt_action)
		self.ebGeo.addAction(self.mt_action)

		self.miA_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'findmiarea.png'),
			text=u'Download de Cartas do BDGEx',
			callback=self.loadDeterminarMIArea,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.miA_action)
		from .DeterminarMIArea.main import Main as Main_MIArea
		self.mainMIArea = Main_MIArea(iface)

		self.vfaction = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'dimensionsvf.png'),
			text=u'Calculadora de Coordenadas e Dimensões',
			callback=self.loadVirtualFieldGenerator,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.vfaction)
        
		self.dec_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'declconv.png'),
			text=u'Calculadora de Declinação magnética e convergência meridiana',
			callback=self.loadDeclinacaoConvergencia,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.dec_action)
		from .DeclinacaoConvergencia.main import Main as Main_DecConv
		self.mainDecConv = Main_DecConv(iface)
		
		self.visibilityAnalysisToolBox = None
		self.mt_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'visibilityAnalisis.png'),
			text=u'Análise de Visibilidade',
			callback=self.visibilityAnalysis,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.mt_action)

		# self.geo_action = self.add_action(
		#  	os.path.join(os.path.dirname(__file__), 'icons', 'geocoder.png'),
		#  	text=u'Geocodificação',
		#  	callback=self.loadGeocoding,
		#  	parent=self.ebGeo,
		#  	add_to_menu=False,
		#  	add_to_toolbar=False)
		# self.ebGeo.addAction(self.geo_action)
		# from .QuickGeocoder.geocoder import QuickGeocoder as Main_Geocoding
		# self.mainGeocoding = Main_Geocoding(iface)

		# self.rd_action = self.add_action(
		# 	os.path.join(os.path.dirname(__file__), 'icons', 'rendezvous.png'),
		# 	text=u'Plano de chamada',
		# 	callback=self.loadRendezvous,
		# 	parent=self.ebGeo,
		# 	add_to_menu=False,
		# 	add_to_toolbar=False)
		# self.ebGeo.addAction(self.rd_action)
		# from .Rendezvous.main import Main as Main_Rendezvous
		# self.mainRendezvous = Main_Rendezvous(iface)

		self.labelPointsaLongLines = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'distanciaLinha.png'),
			text=u'Distância ao longo da linha',
			callback=self.loadPontosNaLinha,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.labelPointsaLongLines)

		from .FrzSarp.frz_button import FrzPlugin as Main_FRZ
		self.mainFRZ = Main_FRZ(iface)
		self.mt_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'frzsarp.png'),
			text=u'Criar Zonas de Restrição de Voo para Drones entorno de Aeródromos',
			callback=self.mainFRZ.run_zonas,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.mt_action)

		self.zoom_to = None
		self.zoom_to_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'zoom_to.png'),
			text=u'Zoom para coordenada',
			callback=self.loadZoomTool,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False)
		self.ebGeo.addAction(self.zoom_to_action)

		self.simplifyInterface_action = self.add_action(
			os.path.join(os.path.dirname(__file__), 'icons', 'hide.png'),
			text=u'Simplificar Interface',
			callback=self.loadSimplifyInterface,
			parent=self.ebGeo,
			add_to_menu=False,
			add_to_toolbar=False
		)
		self.simplifyInterface_action.setCheckable(True)
		self.ebGeo.addAction(self.simplifyInterface_action)

		# self.hidde_action = self.add_action(
		# 	os.path.join(os.path.dirname(__file__), 'icons', 'hide.png'),
		# 	text=u'Ocultar Barra de Ferramentas',
		# 	callback=self.loadHideToolbar,
		# 	parent=self.ebGeo,
		# 	add_to_menu=False,
		# 	add_to_toolbar=False
		# )
		# self.hidde_action.setCheckable(True)
		# self.ebGeo.addAction(self.hidde_action)

		self.ms_action = self.add_action(
		 	os.path.join(os.path.dirname(__file__), 'icons', 'help.png'),
		 	text=u'Ajuda',
		 	callback=self.loadHelp,
		 	parent=self.ebGeo,
		 	add_to_menu=False,
		 	add_to_toolbar=False)
		self.ebGeo.addAction(self.ms_action)

		self.ms_action = self.add_action(
		 	os.path.join(os.path.dirname(__file__), 'icons', 'dsg.png'),
		 	text=u'Sobre',
		 	callback=self.loadAbout,
		 	parent=self.ebGeo,
		 	add_to_menu=False,
		 	add_to_toolbar=False)
		self.ebGeo.addAction(self.ms_action)



	def loadDeterminarMIArea(self):
		"""
        Finds topographic chart within a user-defined box
        """
		if self.mainMIArea.isOpen == False:
			self.mainMIArea.initGui()
    
	def loadMoveVertex(self):
		"""
        Moves points to a new user-input location
        """
		from .numericalVertexEdit.numericalvertexedit import NumericalVertexEdit as Main_MoveVertex
		self.mainMoveVertex = Main_MoveVertex(iface)
		self.mainMoveVertex.initGui()
		self.mainMoveVertex.run()
        
	def loadNumericalDigitize(self):
		"""
        Creates points by user input of coordinates
        """
		from .numericalDigitize.numericalDigitize import NumericalDigitize as Main_NumericalDigitize
		self.mainNumericalDigitize = Main_NumericalDigitize(iface)
		self.mainNumericalDigitize.initGui()
		self.mainNumericalDigitize.run()
    
	def loadDeclinacaoConvergencia(self):
		"""
        Computes magnetic heading and meridian convergence
        """
		if self.mainDecConv.isOpen == False:
			self.mainDecConv.initGui()

	def loadPontosNaLinha(self):
		"""
        Computes magnetic heading and meridian convergence
        """
		from .LineLabelsPerDistance.view.LineLabelsPerDistanceInterface import LineLabelsPerDistance
		dlg = LineLabelsPerDistance()
		if dlg:
			dlg.mapLayerSelection.setFilters(Qgis.LayerFilter.LineLayer)
			dlg.exec()
    
	def loadAngleUnitConverter(self):
		"""
        Convert units from degrees to milliradian
        """
		from .AngleUnitConverter.main import Main
		dialogBoxAng = Main(iface)
		dialogBoxAng.exec()

	def loadGeocoding(self):
		"""
        Geocode and reverse geocode dock
        """
		if self.mainGeocoding.pluginIsActive == False:
			self.mainGeocoding.run()

	def loadMilitarySimbology(self):
		"""
        Shows the Military Simbology Dock
        """
		from .MilitarySimbologyTools.main import Main
		main = Main()
		dlg = main.getFrame()
		dlg.setGeometry(700, 500, 100, 50)
		if dlg:
			dlg.show()
        
	def loadProfileTool(self):
		"""
        Generates terrain profile
        """
		hasRaster = False
		for l in QgsProject.instance().mapLayers().values():
			if l.type() == QgsMapLayer.LayerType.RasterLayer:
				hasRaster = True
				break
		if hasRaster == False:
			msgBox = QMessageBox(QMessageBox.Icon.Information, u"Informação", u"Não há camadas raster para traçar o perfil.", QMessageBox.StandardButton.Ok)
			msgBox.exec()
			return
		if self.mainProfileTool.dockOpened == False:
			self.mainProfileTool.run()
        
	def loadVirtualFieldGenerator(self):
		"""
        Computes geometries dimensions and centroids
        """
		from .VirtualFieldGenerator.virtualFieldGenerator import VirtualFieldGenerator
		dialogVFG = VirtualFieldGenerator(iface)
		dialogVFG.exec()
	
	def loadMakeMosaic(self):
		from qgis import processing
		processing.execAlgorithmDialog('EBGeoProvider:mosaic')

	def loadMakeFrame(self):
		from qgis import processing
		processing.execAlgorithmDialog('EBGeoProvider:frame')

	def loadLineOfSight(self):
		"""
		Abre o algoritmo de Linha de Visada (perfil de visibilidade entre vértices de linhas sobre um MDE)
		"""
		from qgis import processing
		processing.execAlgorithmDialog('EBGeoProvider:lineofsight')

	def loadShaderTool(self):
		"""
		Terrain shading based on sun positon on given time and given observer position
		"""
		if self.mainShaderTool.isOpen == False:
			self.mainShaderTool.initGui()

	def loadAzimuthTool(self):
		"""
        Adds icons to toolbar for creating points from given point, distance and azymuth
        """
		if self.az_action.isChecked():
			self.mainAzimuthTool.initGui(self.az_action)
		else:
			self.mainAzimuthTool.unload()
			
	def loadAreaRange(self):
		"""
        Adds icons to toolbar for generating gun range area
        """
		if self.ar_action.isChecked():
			self.mainAreaRange.initGui(self.ar_action)
		else:
			self.mainAreaRange.unload()

	def loadAzimuthGenerator(self):
		"""
        Create azimuth and distance list for given geometries or set of points
        """
		if self.mainAzimuthGen.isOpen == False:
			self.mainAzimuthGen.initGui()

	def loadRendezvous(self):
		"""
		From given set os points create Voronoi diagrams and its centroids
		"""
		if self.mainRendezvous.isOpen == False:
			self.mainRendezvous.initGui()

	def loadMobPath(self):
		"""
		Creates raster with paths available from restriction vector layers and slope ranges
		"""
		from .MobilityPath.mobilityPath import MobilityPath
		dialogMobPath = MobilityPath(iface)
		dialogMobPath.exec()
		
	def loadVisibility(self):
		"""
        Creates visibility from given point and observer height 
        """
		if self.mainVisib.isOpen == False:
			self.mainVisib.initGui()

	def loadSimplifyInterface(self):
		from .SimplifyInterface.simplify_interface import SimplifyInterface
		if not hasattr(self, "simplifyInterface"):	
			self.simplifyInterface = SimplifyInterface(self.iface)
		if getattr(self.simplifyInterface, "is_active", False):
			self.simplifyInterface.disable()
			self.simplifyInterface.is_active = False
			self.simplifyInterface_action.setChecked(False)
		else:
			self.simplifyInterface.enable(store=True)
			self.simplifyInterface.is_active = True
			self.simplifyInterface_action.setChecked(True)

	def loadHideToolbar(self):
		from .HideToolbar.hideToolbar import HideToolbar
		if not hasattr(self, 'hide_toolbar'):
			self.hide_toolbar = HideToolbar(self.iface)
		if not self.hide_toolbar.active:
			self.hide_toolbar.enable()
			self.hidde_action.setChecked(True) 
		else:
			self.hide_toolbar.disable()
			self.hidde_action.setChecked(False)

	def loadHelp(self):
		"""
        Open "help" window
        """
		from .Help.help import Help
		dialogHelp = Help()
		dialogHelp.exec()

	def loadAbout(self):
		"""
        Open "about" window
        """
		from .About.about import About
		dialogAbout = About()
		dialogAbout.exec()
	
	def loadZoomTool(self):
		if self.zoom_to:
			self.iface.removeDockWidget(self.zoom_to)
			self.zoom_to=None
		else:
			self.zoom_to = ZoomToDockWidget(self.iface, plugin=self)
			self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.zoom_to)

	def initiateToolsSignals(self):
		"""
        Connects all maptools' signals.
        """
		for tool in [ #adicionar mapTools
            self.measureTool, 
        ]:
            # connect current layer changed signal to all tools that use it
			self.iface.currentLayerChanged.connect(tool.setToolEnabled)
			# connect editing started/stopped signals to all tools that use it
			self.editingStarted.connect(tool.setToolEnabled)
			self.editingStopped.connect(tool.setToolEnabled)
			# connect edit button toggling signal to all tools that use it
			self.iface.actionToggleEditing().triggered.connect(tool.setToolEnabled)

	def resetCurrentLayerSignals(self):
		"""
		Resets all signals used from current layer connected to maptools to current selection.
		"""
		if isinstance(self.currentLayer, QgsVectorLayer):
			# disconnect previous selection's signals, if any
			try:
				self.currentLayer.editingStarted.disconnect(self.editingStarted)
				self.currentLayer.editingStopped.disconnect(self.editingStopped)
			except:
				pass
		# now retrieve current selection and reset signal connection
		self.currentLayer = self.iface.mapCanvas().currentLayer()
		if isinstance(self.currentLayer, QgsVectorLayer):
			self.currentLayer.editingStarted.connect(self.editingStarted)
			self.currentLayer.editingStopped.connect(self.editingStopped)
		
	def visibilityAnalysis(self):
		if self.visibilityAnalysisToolBox is not None:
			self.iface.removeDockWidget(self.visibilityAnalysisToolBox)
		else:
			self.visibilityAnalysisToolBox = Main_VisibilityAnalisys(
				self.iface
			)
		self.iface.addDockWidget(
			Qt.DockWidgetArea.RightDockWidgetArea, self.visibilityAnalysisToolBox
		)
