# -*- coding: utf-8 -*-
"""
Azimute e Distância: a ferramenta de mapa e o controlador.

A ferramenta só recebe o clique do ponto de referência (com atração, se ligada no projeto); o
resto é o painel (painel.py). O preview desenha no mapa, enquanto se digita, a mesma geometria
que vai ser gravada: vértices da rota ou da área no círculo máximo e os pontos do modo ponto.
Selecionar uma feição feita pela ferramenta (ou importada do .ebgeo com a construção) abre o
painel em modo edição.
"""
from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsMapTool, QgsRubberBand, QgsSnapIndicator
from qgis.PyQt.QtCore import QObject, Qt, QTimer
from qgis.PyQt.QtGui import QColor

from . import geometria as G
from . import gravacao
from .painel import CRIAR, EDITAR, PainelAzimute

WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')
VERDE = QColor(22, 163, 74)


class FerramentaAzimute(QgsMapTool):
    """Clique esquerdo: ponto de referência. Esc: cancela."""

    def __init__(self, canvas, controlador):
        super().__init__(canvas)
        self.controlador = controlador
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.indicador = QgsSnapIndicator(canvas)

    def _ponto(self, e):
        m = self.canvas().snappingUtils().snapToMap(e.pos())
        self.indicador.setMatch(m)
        return m.point() if m.isValid() else self.toMapCoordinates(e.pos())

    def canvasMoveEvent(self, e):
        self._ponto(e)

    def canvasReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        p = self._ponto(e)
        crs = self.canvas().mapSettings().destinationCrs()
        if crs != WGS84:
            p = QgsCoordinateTransform(crs, WGS84, QgsProject.instance()).transform(QgsPointXY(p))
        self.controlador.clique_no_mapa(p.x(), p.y())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.controlador.cancelar()
            e.accept()

    def deactivate(self):
        self.indicador.setMatch(type(self.indicador.match())())
        super().deactivate()


class AzimuteDistancia(QObject):
    """A ação do menu, a ferramenta, o painel e o preview."""

    def __init__(self, iface, garantir_calco=None):
        super().__init__()
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.garantir_calco = garantir_calco
        self.acao = None
        self.painel = None
        self.ferramenta = FerramentaAzimute(self.canvas, self)
        self.bandas = {}
        self._camada_sel = None
        # (camada, fid, no_buffer) da edição aberta pelo dock de propriedades: o Salvar dela entra
        # no buffer do dock (Descartar volta). None na ferramenta solta, que grava direto.
        self._do_dock = None
        iface.currentLayerChanged.connect(self._camada_mudou)
        self._camada_mudou(iface.activeLayer())

    # ------------------------------------------------------------------ ciclo de vida
    def initGui(self, acao):
        self.acao = acao
        self.ferramenta.setAction(acao)

    def unload(self):
        try:
            self.iface.currentLayerChanged.disconnect(self._camada_mudou)
        except (TypeError, RuntimeError):
            pass
        self._desligar_selecao()
        if self.canvas.mapTool() is self.ferramenta:
            self.canvas.unsetMapTool(self.ferramenta)
        self._limpar_preview()
        if self.painel is not None:
            self.iface.removeDockWidget(self.painel)
            self.painel.deleteLater()
            self.painel = None

    def _calco(self):
        from ..calco import calco_ativo
        c = calco_ativo()
        if c is None and self.garantir_calco is not None:
            c = self.garantir_calco()
        if c is None:
            self.iface.messageBar().pushWarning('EBGeo', 'Crie ou abra um calco antes de usar o Azimute e Distância.')
        return c

    def _painel(self):
        if self.painel is None:
            self.painel = PainelAzimute(self.iface.mainWindow())
            self.painel.estadoMudou.connect(self._preview)
            self.painel.pedirCliqueMapa.connect(self._ligar_ferramenta)
            self.painel.criarPedido.connect(self.criar)
            self.painel.salvarPedido.connect(self.salvar)
            self.painel.cancelarPedido.connect(self.cancelar)
            self.painel.novaPedida.connect(self.nova)
            self.painel.visibilityChanged.connect(self._painel_visivel)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.painel)
        return self.painel

    def ativar(self, *_):
        """A ação do menu: abre o painel (em edição, se uma construção estiver selecionada) e a ferramenta."""
        if self._calco() is None:
            if self.acao is not None:
                self.acao.setChecked(False)
            return False
        p = self._painel()
        alvo = self._construcao_selecionada()
        if alvo is not None:
            self._abrir_edicao(*alvo)
        elif p.modo == EDITAR or not p.isVisible():
            p.novo()
        p.show()
        p.raise_()
        self._ligar_ferramenta()
        return True

    def _ligar_ferramenta(self):
        if self.canvas.mapTool() is not self.ferramenta:
            self.canvas.setMapTool(self.ferramenta)
        if self.acao is not None:
            self.acao.setChecked(True)

    def _painel_visivel(self, visivel):
        if visivel:
            if self.painel is not None:
                self._preview(self.painel.estado_publico())
            return
        self._limpar_preview()
        if self.canvas.mapTool() is self.ferramenta:
            self.canvas.unsetMapTool(self.ferramenta)

    # ------------------------------------------------------------------ mapa
    def clique_no_mapa(self, lon, lat):
        p = self.painel
        if p is None or not p.isVisible():
            return
        if not p.aguardando_clique:
            # como no Web: depois do primeiro clique, o ponto só muda pelo botão "Clicar no mapa"
            self.iface.messageBar().pushInfo('EBGeo', 'Use "Clicar no mapa" no painel para mudar o ponto de referência.')
            return
        p.definir_ponto(lon, lat)

    def cancelar(self):
        if self.painel is not None:
            if self.painel.modo == EDITAR:
                # descarta a edição: volta ao que está gravado
                alvo = self.painel.alvo
                if alvo is not None:
                    self._abrir_edicao(*alvo)
                    return
            self.painel.hide()
        if self.canvas.mapTool() is self.ferramenta:
            self.canvas.unsetMapTool(self.ferramenta)

    def nova(self):
        self._painel().novo()
        self._ligar_ferramenta()

    # ------------------------------------------------------------------ preview
    def _banda(self, nome, tipo):
        b = self.bandas.get(nome)
        if b is None:
            b = QgsRubberBand(self.canvas, tipo)
            b.setColor(QColor(VERDE.red(), VERDE.green(), VERDE.blue(), 220))
            b.setFillColor(QColor(VERDE.red(), VERDE.green(), VERDE.blue(), 50))
            b.setWidth(3)
            if tipo == Qgis.GeometryType.Point:
                b.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
                b.setIconSize(10)
            b.tipo_ebgeo = tipo
            self.bandas[nome] = b
        return b

    def _limpar_preview(self):
        for b in self.bandas.values():
            b.reset(b.tipo_ebgeo)
            b.setVisible(False)

    def _mostrar(self, nome, tipo, geometria):
        b = self._banda(nome, tipo)
        b.reset(tipo)
        b.setToGeometry(geometria, WGS84)
        # o reset() esconde a banda (QGIS 4.0.0): mostra de volta depois de montar
        b.setVisible(True)
        b.update()

    def _preview(self, estado):
        self._limpar_preview()
        if self.painel is None or not self.painel.isVisible():
            return
        ponto = estado.get('referencePoint')
        if not ponto:
            return
        marca = self._banda('origem', Qgis.GeometryType.Point)
        marca.setIcon(QgsRubberBand.IconType.ICON_CROSS)
        marca.setIconSize(16)
        self._mostrar('origem', Qgis.GeometryType.Point, QgsGeometry.fromPointXY(QgsPointXY(ponto[0], ponto[1])))
        vertices = G.calcular_vertices(ponto, estado['legs'], estado['magneticDeclination'], estado['northReference'],
                                       estado['angularUnit'], estado['distanceUnit'], G.resolver_convergencia(estado))
        modo = estado.get('outputMode')
        if modo == G.PONTO:
            if len(vertices) > 1:
                g = QgsGeometry.fromMultiPointXY([QgsPointXY(x, y) for x, y in vertices])
                self._mostrar('pontos', Qgis.GeometryType.Point, g)
            return
        geo = G.gerar_geometria(vertices, modo)
        if geo is None:
            return
        if geo['type'] == 'LineString':
            self._mostrar('linha', Qgis.GeometryType.Line,
                          QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in geo['coordinates']]))
        else:
            self._mostrar('area', Qgis.GeometryType.Polygon,
                          QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in geo['coordinates'][0]]]))
        if len(vertices) > 1:
            self._mostrar('pontos', Qgis.GeometryType.Point,
                          QgsGeometry.fromMultiPointXY([QgsPointXY(x, y) for x, y in vertices[1:]]))

    # ------------------------------------------------------------------ gravar
    def criar(self, estado):
        c = self._calco()
        if c is None:
            return None
        from .. import zoom
        z, _lat = zoom.zoom_do_canvas(self.canvas)
        lyr, ids = gravacao.criar(c, estado, z)
        if not ids:
            self.iface.messageBar().pushCritical('EBGeo', 'Não foi possível gravar a construção no calco.')
            return None
        self.iface.messageBar().pushSuccess('EBGeo', '{}: {} feição(ões) criada(s) no calco.'.format(
            G.ROTULO_MODO[estado['outputMode']], len(ids)))
        # seleciona o que nasceu: o painel passa a editar a construção, como o painel do Web
        self.iface.setActiveLayer(lyr)
        if self._camada_sel is not lyr:
            self._camada_mudou(lyr)
        sel = [f.id() for f in lyr.getFeatures('"ebgeo_id" IN ({})'.format(','.join("'{}'".format(i) for i in ids)))]
        if sel:
            self._painel().novo()
            lyr.selectByIds(sel[-1:])
            self._abrir_edicao(lyr, sel[-1])
        return lyr, ids

    def salvar(self, estado):
        alvo = self.painel.alvo if self.painel else None
        if alvo is None:
            return False
        layer, fid = alvo
        do_dock = self._do_dock if self._do_dock and self._do_dock[:2] == (layer, fid) else None
        if do_dock is not None:
            # no buffer do dock: o _editar da gravação não fecha a edição que o dock abriu
            res = []
            do_dock[2](lambda: res.append(gravacao.atualizar(layer, fid, estado)), 'Calco: Azimute e Distância')
            ok = bool(res and res[0])
        else:
            ok = gravacao.atualizar(layer, fid, estado)
        if not ok:
            self.iface.messageBar().pushCritical('EBGeo', 'Azimute e Distância: não foi possível gravar as alterações.')
            return False
        self.iface.messageBar().pushSuccess('EBGeo', 'Construção atualizada no painel do calco: Salvar grava, Descartar volta.'
                                            if do_dock else 'Construção atualizada.')
        f = layer.getFeature(fid)
        if f.isValid():
            self._abrir_edicao(layer, fid)
            self._do_dock = do_dock
        return True

    # ------------------------------------------------------------------ seleção
    def _desligar_selecao(self):
        if self._camada_sel is not None:
            try:
                self._camada_sel.selectionChanged.disconnect(self._selecao_mudou)
            except (TypeError, RuntimeError):
                pass
        self._camada_sel = None

    def _camada_mudou(self, layer):
        self._desligar_selecao()
        from ..calco import tipo_da_camada
        if isinstance(layer, QgsVectorLayer) and tipo_da_camada(layer) in gravacao.MODO_DO_TIPO:
            self._camada_sel = layer
            layer.selectionChanged.connect(self._selecao_mudou)

    def _construcao_selecionada(self):
        lyr = self._camada_sel
        if lyr is None:
            return None
        sel = lyr.selectedFeatureIds()
        if len(sel) != 1:
            return None
        f = lyr.getFeature(sel[0])
        if not f.isValid() or gravacao.construcao_da_feicao(f) is None:
            return None
        return lyr, sel[0]

    def _selecao_mudou(self, *_):
        p = self.painel
        if p is None or not p.isVisible():
            return
        alvo = self._construcao_selecionada()
        if alvo is None:
            return
        if self._criando(p):
            return
        # adiado: o sinal de seleção pode vir de dentro de um widget que o painel redesenha
        QTimer.singleShot(0, lambda a=alvo: self._edicao_adiada(a))

    @staticmethod
    def _criando(p):
        """Construção nova em andamento: a seleção não a descarta (o Web faz igual)."""
        return p.modo == CRIAR and bool(p.estado.get('referencePoint'))

    def _edicao_adiada(self, alvo):
        # a guarda vale de novo na hora: entre o sinal e agora o operador pode ter começado outra
        p = self.painel
        if p is None or not p.isVisible() or self._criando(p) or self._construcao_selecionada() != alvo:
            return
        self._abrir_edicao(*alvo)

    def editar_feicao(self, layer, fid, no_buffer=None):
        """
        Abre o painel em edição para a construção da feição (o "Editar pernas..." do dock de
        propriedades). Não troca a ferramenta do mapa: "Clicar no mapa", no painel, a liga.
        Com `no_buffer` (o PainelCalco._no_buffer do dock), o Salvar do painel grava num comando
        do buffer do dock, e o Salvar e o Descartar do dock decidem. Devolve False quando a feição
        não tem construção.
        """
        if layer is None or fid is None:
            return False
        if self._camada_sel is not layer:
            self._camada_mudou(layer)
        if not self._abrir_edicao(layer, fid):
            return False
        self._do_dock = (layer, fid, no_buffer) if no_buffer is not None else None
        self.painel.show()
        self.painel.raise_()
        return True

    def _abrir_edicao(self, layer, fid):
        self._do_dock = None  # aberta pela seleção ou pela criação: ferramenta solta
        f = layer.getFeature(fid)
        polar = gravacao.construcao_da_feicao(f)
        if polar is None:
            return False
        p = self._painel()
        i = f.fields().indexOf('nome')
        p.editar(layer, fid, polar, f.attribute(i) if i >= 0 else '')
        return True
