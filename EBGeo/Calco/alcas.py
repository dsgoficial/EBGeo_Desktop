# -*- coding: utf-8 -*-
"""
Alças de edição do EBGeo Web nos táticos do calco, como ferramenta de mapa.

O Web edita no mapa, por alças, o que no Desktop só se edita por número no dock. Esta ferramenta
põe as mesmas alças, com o mesmo cálculo do Web, e grava no buffer do dock (Salvar e Descartar):

- Linha de Limite, a INSTÂNCIA do escalão (`symbol_handle` de add_boundary_geometry.js): uma alça
  por instância, no ponto do eixo a L x ratio; arrastada, a razão nova é a do ponto do eixo mais
  perto do cursor (turf.nearestPointOnLine), entre 0,01 e 0,99, e só a instância arrastada muda;
- Linha de Limite, a DISTÂNCIA DO TEXTO (`text_distance_handle`): uma alça, na instância mais à
  esquerda (a de menor razão), a tamanho x (text_distance_ratio || 0,8) do centro, à esquerda do
  eixo; arrastada, a razão nova é a distância do centro ao cursor sobre o tamanho efetivo do
  símbolo, entre 0,1 e 3. Só aparece com texto e alguma instância com rótulo;
- Seta, a LARGURA (`width` de add_arrow_geometry.js): uma alça por ramo, na ponta do último
  vértice, a |largura| x 2,5 / 2 para o lado rumo - 90 x sinal(largura); arrastada, a largura nova
  é a distância do cursor ao último segmento (turf.pointToLineDistance), negativa à esquerda dele.
  Na seta combinada o ramo arrastado muda na coluna `ramos` (e o desenho e o exportador o leem
  assim, seta_ramo.exp); na simples, `width_m`.

Duas esquisitices do Web, espelhadas de propósito: a alça da largura fica a 1,25 x a largura do
eixo, mas o arraste grava a distância do cursor ao eixo, então a largura salta para 1,25 x ao
pegar a alça; e a alça da distância do texto do Limite sem `text_distance_ratio` fica a 0,8 x o
tamanho, enquanto o rótulo é desenhado a 0,9.

A geometria das alças e do arraste é Python puro (o turf portado: along, length, distance,
destination, bearing) e é provada contra o próprio Web em node (testes/test_alcas.py). O preview
do arraste é o desenho do estilo da camada (o Geometry Generator do calco) avaliado na feição com
o valor novo, numa QgsRubberBand.
"""
import json
import math

R_TURF = 6371008.8

LIMITES = {'ratio': (0.01, 0.99), 'texto': (0.1, 3.0)}
ALCA_PX = 10  # raio de pega, em px


# ---------------------------------------------------------------- turf (esfera do turf, km)

def _rad(g):
    return g * math.pi / 180


def turf_distance(a, b):
    """turf.distance em km (haversine)."""
    la1, la2 = _rad(a[1]), _rad(b[1])
    h = math.sin((la2 - la1) / 2) ** 2 + math.sin(_rad(b[0] - a[0]) / 2) ** 2 * math.cos(la1) * math.cos(la2)
    return 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h)) * R_TURF / 1000


def turf_bearing(a, b):
    lo1, lo2, la1, la2 = _rad(a[0]), _rad(b[0]), _rad(a[1]), _rad(b[1])
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return math.degrees(math.atan2(y, x))


def turf_destination(o, km, rumo):
    la1, lo1, b = _rad(o[1]), _rad(o[0]), _rad(rumo)
    d = km * 1000 / R_TURF
    la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
    lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
    return [math.degrees(lo2), math.degrees(la2)]


def turf_length(coords):
    return sum(turf_distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def turf_along(coords, km):
    """turf.along: o ponto a `km` do início, voltando do vértice que passou."""
    andado = 0.0
    for i in range(len(coords)):
        if km >= andado and i == len(coords) - 1:
            break
        if andado >= km:
            excesso = km - andado
            if not excesso:
                return list(coords[i])
            return turf_destination(coords[i], excesso, turf_bearing(coords[i], coords[i - 1]) - 180)
        andado += turf_distance(coords[i], coords[i + 1])
    return list(coords[-1])


def _plano(o):
    """Projeção azimutal equidistante local (R do turf), metros: (ida, volta)."""
    from pyproj import Transformer
    crs = '+proj=aeqd +lat_0={} +lon_0={} +R={} +units=m +no_defs'.format(o[1], o[0], R_TURF)
    ida = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
    volta = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True)
    return (lambda p: ida.transform(p[0], p[1])), (lambda x, y: list(volta.transform(x, y)))


def ponto_mais_perto_km(coords, p):
    """A posição (km do início) do ponto do eixo mais perto de p (turf.nearestPointOnLine)."""
    ida, _v = _plano(p)
    alvo = ida(p)
    melhor, pos, andado = None, 0.0, 0.0
    for a, b in zip(coords[:-1], coords[1:]):
        (ax, ay), (bx, by) = ida(a), ida(b)
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((alvo[0] - ax) * dx + (alvo[1] - ay) * dy) / l2))
        d = math.hypot(ax + t * dx - alvo[0], ay + t * dy - alvo[1])
        seg = turf_distance(a, b)
        if melhor is None or d < melhor:
            melhor, pos = d, andado + t * seg
        andado += seg
    return pos


def distancia_ao_segmento_m(a, b, p):
    """turf.pointToLineDistance de p ao segmento a-b, em metros."""
    ida, _v = _plano(p)
    (ax, ay), (bx, by), (px, py) = ida(a), ida(b), ida(p)
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


# ---------------------------------------------------------------- Linha de Limite

def _limitar(v, nome):
    lo, hi = LIMITES[nome]
    return max(lo, min(hi, v))


def instancias(valor):
    """getSymbolInstances do Web: a lista de {ratio, showLabels}, nunca vazia."""
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            valor = None
    out = []
    if isinstance(valor, list):
        for i in valor:
            if isinstance(i, dict):
                r = i.get('ratio')
                r = _limitar(r, 'ratio') if isinstance(r, (int, float)) and not isinstance(r, bool) and math.isfinite(r) else 0.5
                out.append({'ratio': r, 'showLabels': i.get('showLabels') is not False})
    return out or [{'ratio': 0.5, 'showLabels': True}]


def centro_e_rumo(coords, L, ratio):
    """getCenterAndBearing: o ponto a L x ratio e o rumo entre os pontos a -/+ 10 m."""
    c = turf_along(coords, L * ratio)
    d1 = max(0.001, L * ratio - 0.01)
    d2 = min(L - 0.001, L * ratio + 0.01)
    return c, turf_bearing(turf_along(coords, d1), turf_along(coords, d2))


def alcas_limite(coords, props, tamanho_km):
    """[(tipo, índice, [lon, lat])] das alças do Limite: uma por instância e a da distância do texto."""
    L = turf_length(coords)
    if not L > 0.001:
        return []
    inst = instancias(props.get('symbol_instances'))
    out = [('instancia', i, turf_along(coords, L * x['ratio'])) for i, x in enumerate(inst)]
    if (props.get('text_top') or props.get('text_bottom')) and any(x['showLabels'] for x in inst):
        ancora = min(inst, key=lambda x: x['ratio'])
        c, rumo = centro_e_rumo(coords, L, ancora['ratio'])
        tdr = props.get('text_distance_ratio') or 0.8
        out.append(('texto', 0, turf_destination(c, tamanho_km * tdr, rumo - 90)))
    return out


def arrastar_instancia(coords, valor_instancias, indice, pos):
    """O symbol_instances com a instância `indice` na razão do ponto do eixo mais perto de pos."""
    L = turf_length(coords)
    inst = [dict(x) for x in instancias(valor_instancias)]
    i = indice if 0 <= indice < len(inst) else 0
    inst[i]['ratio'] = _limitar(ponto_mais_perto_km(coords, pos) / L, 'ratio')
    return inst


def arrastar_texto(coords, valor_instancias, tamanho_km, pos):
    """O text_distance_ratio da alça do texto em pos: distância ao centro da instância âncora / tamanho."""
    L = turf_length(coords)
    ancora = min(instancias(valor_instancias), key=lambda x: x['ratio'])
    c = turf_along(coords, L * ancora['ratio'])
    return _limitar(turf_distance(c, pos) / tamanho_km, 'texto')


# ---------------------------------------------------------------- Seta

def alca_largura(coords, largura):
    """O ponto da alça da largura de um ramo (createSingleHandles do Web)."""
    w = largura or 0
    ult, pen = coords[-1], coords[-2]
    rumo = turf_bearing(pen, ult)
    sinal = (w > 0) - (w < 0) or 1
    return turf_destination(ult, abs(w * 2.5) / 2 / 1000, rumo - 90 * sinal)


def arrastar_largura(coords, pos):
    """_applyWidthFromHandle: distância do cursor ao último segmento, negativa do lado esquerdo."""
    ult, pen = coords[-1], coords[-2]
    w = distancia_ao_segmento_m(pen, ult, pos)
    x1, y1, x2, y2 = pen[0], pen[1], ult[0], ult[1]
    if (pos[0] - x1) * (y2 - y1) - (pos[1] - y1) * (x2 - x1) > 0:
        w = -w
    return w


# ---------------------------------------------------------------- a ferramenta (QGIS)

def _ferramenta():
    """A classe da ferramenta, montada na primeira chamada (o resto do módulo não importa QGIS)."""
    from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpression, QgsExpressionContext,
                           QgsExpressionContextUtils, QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsRectangle,
                           QgsWkbTypes)
    from qgis.gui import QgsMapTool, QgsRubberBand
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor

    from . import estilos_taticos as et
    from . import schema
    from .calco import tipo_da_camada

    WGS84 = QgsCoordinateReferenceSystem('EPSG:4326')
    TEXTO_TAMANHO = et.finalizar(et.compor(None, _TEXTO='@@SEJA@@\n@@LIMITE@@\n@@EM@@\n@s / (@k)\n@@FIM@@',
                                           LIMITE=et.compor('_limite')))
    ROTULOS = [(et.expr_limite_rotulo(lado, False)['geometria'], et.expr_limite_rotulo(lado, True)['geometria'])
               for lado in ('top', 'bottom')]

    class FerramentaAlcas(QgsMapTool):
        """
        Alças do Web na feição selecionada da camada ativa (Linha de Limite ou Seta do calco). Clique
        numa feição seleciona; arrastar uma alça mostra o desenho novo e, ao soltar, grava no buffer do
        dock (`obter_painel` devolve o PainelCalco aberto). Sem o dock, grava num comando de edição da
        camada, como as ferramentas soltas.
        """

        TIPOS = ('boundary', 'arrow')

        def __init__(self, canvas, iface=None, obter_painel=None):
            super().__init__(canvas)
            self.iface = iface
            self.obter_painel = obter_painel
            self.camada = None
            self.fid = None
            self.alcas = []         # (tipo, índice, [lon, lat])
            self.arraste = None     # (tipo, índice)
            self.mudanca = None     # {coluna: valor} do arraste em curso
            self.banda_alcas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
            self.banda_alcas.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
            self.banda_alcas.setIconSize(12)
            self.banda_alcas.setColor(QColor('#ff6d00'))
            self.banda_alcas.setFillColor(QColor(255, 255, 255, 220))
            self.banda_alcas.setWidth(2)
            self.preview = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
            self.preview.setColor(QColor(255, 109, 0, 200))
            self.preview.setFillColor(QColor(255, 109, 0, 40))
            self.preview.setWidth(2)
            self.preview_texto = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
            self.preview_texto.setIcon(QgsRubberBand.IconType.ICON_X)
            self.preview_texto.setIconSize(14)
            self.preview_texto.setColor(QColor(255, 109, 0))
            self.preview_texto.setWidth(3)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        # ---- feição e alças
        def _ao_mapa(self):
            return QgsCoordinateTransform(WGS84, self.canvas().mapSettings().destinationCrs(), QgsProject.instance())

        def _do_mapa(self, ponto):
            tr = QgsCoordinateTransform(self.canvas().mapSettings().destinationCrs(), WGS84, QgsProject.instance())
            p = tr.transform(ponto)
            return [p.x(), p.y()]

        def _contexto(self, f):
            ctx = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(self.camada))
            ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(self.canvas().mapSettings()))
            ctx.setFeature(f)
            return ctx

        def _avaliar(self, texto, f):
            e = QgsExpression(texto)
            ctx = self._contexto(f)
            e.prepare(ctx)
            v = e.evaluate(ctx)
            return None if e.hasEvalError() else v

        def tamanho_km(self, f):
            """O tamanho efetivo do escalão como o estilo o desenha nesta escala (o @s de _limite.exp)."""
            v = self._avaliar(TEXTO_TAMANHO, f)
            return float(v) / 1000 if isinstance(v, (int, float)) and v > 0 else 1.0

        def _eixos(self, f):
            """As partes da feição em EPSG:4326, [[lon, lat], ...] por parte."""
            g = QgsGeometry(f.geometry())
            if self.camada.crs() != WGS84:
                g.transform(QgsCoordinateTransform(self.camada.crs(), WGS84, QgsProject.instance()))
            linhas = g.asMultiPolyline() if g.isMultipart() else [g.asPolyline()]
            return [[[p.x(), p.y()] for p in l] for l in linhas if len(l) >= 2]

        def selecionar(self, camada, fid):
            self.camada, self.fid = camada, fid
            self.mostrar_alcas()

        def mostrar_alcas(self):
            self.alcas = []
            if self.camada is not None and self.fid is not None:
                f = self.camada.getFeature(self.fid)
                if f.isValid():
                    self.alcas = self.calcular_alcas(f)
            self.banda_alcas.reset(QgsWkbTypes.GeometryType.PointGeometry)
            tr = self._ao_mapa()
            for _t, _i, p in self.alcas:
                self.banda_alcas.addPoint(tr.transform(QgsPointXY(*p)), False)
            self.banda_alcas.updatePosition()
            self.banda_alcas.update()
            self.banda_alcas.setVisible(bool(self.alcas))  # o reset esconde a banda (gotcha do QGIS 4)

        def calcular_alcas(self, f):
            tipo = tipo_da_camada(self.camada)
            eixos = self._eixos(f)
            if not eixos:
                return []
            if tipo == 'boundary':
                props = {c: f[c] for c in ('symbol_instances', 'text_top', 'text_bottom', 'text_distance_ratio')}
                return alcas_limite(eixos[0], props, self.tamanho_km(f))
            if tipo == 'arrow':
                ramos = self._ramos(f)
                out = []
                for i, e in enumerate(eixos):
                    out.append(('largura', i, alca_largura(e, self._largura_do_ramo(f, ramos, i))))
                return out
            return []

        @staticmethod
        def _ramos(f):
            v = f['ramos'] if f.fields().indexOf('ramos') >= 0 else None
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except ValueError:
                    v = None
            return v if isinstance(v, dict) and isinstance(v.get('ramos'), list) else None

        @staticmethod
        def _largura_do_ramo(f, ramos, i):
            """A largura que o estilo desenha no ramo i (a mesma regra de seta_ramo.exp)."""
            col = f['width_m']
            col = None if col is None or (hasattr(col, 'isNull') and col.isNull()) else float(col)
            base = col if col else 1000.0
            if ramos is not None and i < len(ramos['ramos']) and isinstance(ramos['ramos'][i], dict):
                topo = (ramos.get('topo') or {}).get('width')
                b = ramos['ramos'][i].get('width')
                if col == topo and isinstance(b, (int, float)) and b:
                    return float(b)
            return base

        # ---- eventos
        def canvasPressEvent(self, e):
            if e.button() != Qt.MouseButton.LeftButton:
                return
            alca = self._alca_em(e.pos())
            if alca is not None:
                self.arraste = alca
                return
            self._selecionar_no_clique(e)

        def _alca_em(self, pos):
            tr = self._ao_mapa()
            mupp = self.canvas().mapUnitsPerPixel()
            p = self.toMapCoordinates(pos)
            melhor = None
            for t, i, q in self.alcas:
                m = tr.transform(QgsPointXY(*q))
                d = math.hypot(m.x() - p.x(), m.y() - p.y()) / mupp
                if d <= ALCA_PX and (melhor is None or d < melhor[0]):
                    melhor = (d, (t, i))
            return melhor[1] if melhor else None

        def _selecionar_no_clique(self, e):
            camada = self.iface.activeLayer() if self.iface is not None else self.camada
            if camada is None or tipo_da_camada(camada) not in self.TIPOS:
                return
            p = self.toLayerCoordinates(camada, e.pos())
            r = self.canvas().mapUnitsPerPixel() * 6
            caixa = self.toLayerCoordinates(camada, QgsRectangle(self.toMapCoordinates(e.pos()).x() - r,
                                                                 self.toMapCoordinates(e.pos()).y() - r,
                                                                 self.toMapCoordinates(e.pos()).x() + r,
                                                                 self.toMapCoordinates(e.pos()).y() + r))
            alvo = None
            for f in camada.getFeatures(caixa):
                d = f.geometry().distance(QgsGeometry.fromPointXY(p))
                if alvo is None or d < alvo[0]:
                    alvo = (d, f.id())
            if alvo is not None:
                camada.selectByIds([alvo[1]])
                self.selecionar(camada, alvo[1])

        def canvasMoveEvent(self, e):
            if self.arraste is None:
                return
            pos = self._do_mapa(self.toMapCoordinates(e.pos()))
            f = self.camada.getFeature(self.fid)
            self.mudanca = self.mudanca_do_arraste(f, self.arraste, pos)
            self._preview(f, self.mudanca)

        def mudanca_do_arraste(self, f, alca, pos):
            """{coluna: valor} que a alça arrastada até pos (lon, lat) grava."""
            tipo, i = alca
            eixos = self._eixos(f)
            if tipo == 'instancia':
                return {'symbol_instances': arrastar_instancia(eixos[0], f['symbol_instances'], i, pos)}
            if tipo == 'texto':
                return {'text_distance_ratio': arrastar_texto(eixos[0], f['symbol_instances'], self.tamanho_km(f), pos)}
            w = arrastar_largura(eixos[i], pos)
            ramos = self._ramos(f)
            if ramos is not None and i < len(ramos['ramos']):
                novo = json.loads(json.dumps(ramos))
                if not isinstance(novo['ramos'][i], dict):
                    novo['ramos'][i] = {}
                novo['ramos'][i]['width'] = w
                return {'ramos': novo}
            return {'width_m': w}

        def _copia(self, f, mudanca):
            g = QgsFeature(f)
            for c, v in mudanca.items():
                g.setAttribute(self.camada.fields().indexOf(c), schema.valor_json_para_qgis(v) if isinstance(v, (list, dict)) else v)
            return g

        def _preview(self, f, mudanca):
            """O desenho do estilo com o valor novo, na banda (e o ponto do rótulo, no texto do Limite)."""
            g = self._copia(f, mudanca)
            tipo = tipo_da_camada(self.camada)
            self.preview_texto.reset(QgsWkbTypes.GeometryType.PointGeometry)
            if tipo == 'arrow':
                self.preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
                geo = self._avaliar(et.expr_seta(), g)
            else:
                self.preview.reset(QgsWkbTypes.GeometryType.LineGeometry)
                geo = self._avaliar(et.expr_limite_linhas(), g)
                norte = bool(g['text_north_facing'])
                for colado, ao_norte in ROTULOS:
                    r = self._avaliar(ao_norte if norte else colado, g)
                    if isinstance(r, QgsGeometry) and not r.isNull():
                        for parte in r.asGeometryCollection():
                            self.preview_texto.addPoint(self._ao_mapa().transform(parte.centroid().asPoint()), False)
                self.preview_texto.updatePosition()
                self.preview_texto.setVisible(True)
            if isinstance(geo, QgsGeometry) and not geo.isNull():
                self.preview.setToGeometry(geo, self.camada)
                self.preview.setVisible(True)

        def canvasReleaseEvent(self, e):
            if self.arraste is None:
                return
            self.canvasMoveEvent(e)
            mudanca, self.arraste, self.mudanca = self.mudanca, None, None
            self.preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            self.preview_texto.reset(QgsWkbTypes.GeometryType.PointGeometry)
            if mudanca:
                self.gravar(mudanca)
            self.mostrar_alcas()

        def gravar(self, mudanca):
            """Grava {coluna: valor} na feição, no buffer do dock (Salvar e Descartar) se houver dock."""
            camada, fid = self.camada, self.fid
            f = camada.getFeature(fid)
            idx = camada.fields().indexOf
            valores = {idx(c): v for c, v in schema.atributos_para_qgis(tipo_da_camada(camada), mudanca).items()
                       if idx(c) >= 0}

            def mudar():
                for i, v in valores.items():
                    camada.changeAttributeValue(fid, i, v)
            painel = self.obter_painel() if self.obter_painel is not None else None
            if painel is not None:
                if painel.layer is not camada or painel.fid != fid:
                    painel._camada_mudou(camada)
                    painel.mostrar_feicao(camada, f['ebgeo_id'])
                    painel._selecao_mudou()
                if painel.layer is camada and painel._no_buffer(mudar, 'Calco: alça do mapa'):
                    painel._selecao_mudou()   # os widgets do dock mostram o valor novo
                    return True
            abriu = not camada.isEditable()
            if abriu and not camada.startEditing():
                return False
            camada.beginEditCommand('Calco: alça do mapa')
            mudar()
            camada.endEditCommand()
            camada.triggerRepaint()
            return True

        def keyPressEvent(self, e):
            if e.key() == Qt.Key.Key_Escape and self.arraste is not None:
                self.arraste = self.mudanca = None
                self.preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
                self.preview_texto.reset(QgsWkbTypes.GeometryType.PointGeometry)

        def deactivate(self):
            self.banda_alcas.reset(QgsWkbTypes.GeometryType.PointGeometry)
            self.preview.reset(QgsWkbTypes.GeometryType.PolygonGeometry)
            self.preview_texto.reset(QgsWkbTypes.GeometryType.PointGeometry)
            self.arraste = None
            super().deactivate()

        def activate(self):
            super().activate()
            camada = self.iface.activeLayer() if self.iface is not None else self.camada
            if camada is not None and tipo_da_camada(camada) in self.TIPOS and len(camada.selectedFeatureIds()) == 1:
                self.selecionar(camada, camada.selectedFeatureIds()[0])

    return FerramentaAlcas


_CLASSE = []


def FerramentaAlcas(canvas, iface=None, obter_painel=None):
    """A ferramenta de mapa das alças (a classe é montada na primeira chamada)."""
    if not _CLASSE:
        _CLASSE.append(_ferramenta())
    return _CLASSE[0](canvas, iface, obter_painel)
