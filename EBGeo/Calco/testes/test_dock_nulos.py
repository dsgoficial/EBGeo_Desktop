# -*- coding: utf-8 -*-
"""
O dock mostra, na coluna numérica NULA, o valor que o estilo desenha, sem gravá-lo, em TODO tipo
com especificação (esp.TIPOS_COM_FORMULARIO) e em TODO campo numérico que o dock edita.

Antes o dock mostrava o mínimo da faixa da caixa giratória: o espaçamento da hachura nulo aparecia
como 1 px e o estilo desenhava 8, a espessura da hachura 0,5 px contra 2, a largura da Seta 10 m
contra 1000, a rotação -360° contra 0. Agora o número vem do próprio estilo da camada
(ui/padrao_estilo.py); quando o estilo não dá número ao nulo (a coluna que ele não lê, o zoom de
criação que as formas tratam como "sem âncora"), a caixa diz "Não definido".

A régua é o DESENHO, não a regra: para cada campo, a feição com a coluna nula e a feição com o
valor que o dock mostra desenham os mesmos pixels, e a mesma feição com outro valor da faixa
desenha outros (o campo foi exercitado na configuração do caso: hachura ligada, rótulo à mostra,
aeromóvel, fundo do texto, Setor de Tiro). O pior caso é a saída REAL de antes, o mínimo da faixa,
que a régua tem de reprovar. Abrir a feição no dock não grava nada, e salvar só o nome pelo dock
não muda coluna nem pixel.

TesteDockLogicosNulos faz o mesmo com as caixas de marcar das colunas lógicas: a nula mostra o estado
que o estilo desenha, ou o terceiro estado, "Não definido", quando o estilo não a lê.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_dock_nulos.py
Variáveis: EBGEO_TESTE_SAIDA (capturas do dock; padrão: temporária).
"""
import base64
import os
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpressionContext,
    QgsExpressionContextUtils, QgsGeometry, QgsMapRendererSequentialJob, QgsMapSettings, QgsPointXY,
    QgsProject, QgsReadWriteContext, QgsRectangle, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QImage  # noqa: E402
from qgis.PyQt.QtXml import QDomDocument  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from qgis.testing.mocked import get_iface  # noqa: E402

from Calco import calco as C, gpkg, schema  # noqa: E402
from Calco.calco import PROP_CAMINHO, PROP_TIPO  # noqa: E402
from Calco.ferramentas import gravar_feicao  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402
from Calco.formulario.tipos import medida as m  # noqa: E402
from Calco.ui import painel as P  # noqa: E402
from Calco.ui.padrao_estilo import TEXTO_NULO  # noqa: E402

SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_dock_nulos_')
os.makedirs(SAIDA, exist_ok=True)
TMP = tempfile.mkdtemp(prefix='ebgeo_dock_nulos_calco_')
MEDIDAS = []
TIPOS = sorted(esp.TIPOS_COM_FORMULARIO)
NUMERICOS = ('num', 'km_em_m', 'area_pct', 'medida_rotacao', 'medida_dir_secundaria')
FORMAS = ('polygon', 'circle', 'ellipse', 'rectangle', 'sector')


def _png_b64():
    img = QImage(16, 12, QImage.Format.Format_ARGB32)
    img.fill(QColor('#d32f2f'))
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, 'PNG')
    return base64.b64encode(bytes(ba)).decode('ascii')


def _codigo_medida(chave):
    """Um point_code do catálogo da medida com a chave (direcao, setorDeTiro)."""
    for codigo, e in m.catalogo()['porCodigo'].items():
        if e.get(chave):
            return codigo
    return None


# O que liga, em cada tipo, o desenho do campo (sem isto o campo não desenha e o caso não prova nada).
ATIVADORES = {
    'coordination_area': dict(symbol_code='151203', escalao='II', tipo='PF', identificacao='X', opacity=1.0,
                              hatch_type='diagonal-right', hatch_enabled=True, fill_color='#ff0000'),
    'coordination_line': dict(symbol_code='140000', tipo='LCAF', identificacao='X'),
    'boundary': dict(text_top='ALFA', text_bottom='BRAVO'),
    'arrow': dict(airmobile=True),
    'text': dict(text='TEXTO', show_background=True, bg_fill_color='#ff0000', bg_border_color='#0000ff'),
    'image': dict(bitmap_mime='image/png', largura_px=16.0, altura_px=12.0),
    # o contorno do rótulo é branco por padrão, e branco sobre o fundo branco não desenha
    'point': dict(show_label=True, label_text='ROTULO', label_outline_color='#0000ff'),
}
for _t in FORMAS:
    ATIVADORES[_t] = dict(show_label=True, label_text='ROTULO', label_outline_color='#0000ff', hatch_enabled=True,
                          hatch_type='diagonal-right', hatch_color='#ff0000', opacity=1.0)
# Configurações a mais de um campo: (rótulo, colunas)
EXTRAS = {
    ('coordination_area', 'opacity'): [('sem hachura', dict(hatch_type='none', hatch_enabled=False))],
    ('coordination_line', 'symbol_size_km'): [('290199', dict(symbol_code='290199'))],
    ('coordination_line', 'symbol_spacing_km'): [('290199', dict(symbol_code='290199'))],
}


def casos():
    """(tipo, coluna, rótulo da configuração, atributos de base) de todo campo numérico do dock."""
    out = []
    setor, direcao = _codigo_medida('setorDeTiro'), _codigo_medida('direcao')
    for tipo in TIPOS:
        tps = {c: tp for c, tp, _p, _w in schema.campos(tipo)}
        for campo in esp.formulario(tipo).campos():
            if tps.get(campo.coluna) not in ('real', 'int') or campo.somente_leitura:
                continue
            if P._spec_do_campo(campo)[0] not in NUMERICOS:
                continue
            base = dict(schema.padroes(tipo))
            base.update(ATIVADORES.get(tipo, {}))
            if tipo == 'image':
                base['bitmap_b64'] = _png_b64()
            confs = [('', base)] + [(r, dict(base, **x)) for r, x in EXTRAS.get((tipo, campo.coluna), [])]
            if tipo == 'coordination_measure' and campo.coluna == 'rotation':
                confs += [('direção ' + direcao, dict(base, point_code=direcao)),
                          ('Setor de Tiro ' + setor, dict(base, point_code=setor))]
            if tipo == 'coordination_measure' and campo.coluna == 'angulo_secundario':
                confs = [('Setor de Tiro ' + setor, dict(base, point_code=setor))]
            out += [(tipo, campo.coluna, rot, a) for rot, a in confs]
    return out


def geometria(tipo):
    g = schema.TIPOS[tipo]['geometria']
    x0, y0 = -47.0, -15.0
    if g == 'Point':
        return QgsGeometry.fromPointXY(QgsPointXY(x0 + 0.01, y0 + 0.007))
    if 'Line' in g:
        return QgsGeometry.fromPolylineXY([QgsPointXY(x0, y0), QgsPointXY(x0 + 0.02, y0 + 0.004),
                                           QgsPointXY(x0 + 0.025, y0 + 0.015)])
    return QgsGeometry.fromPolygonXY([[QgsPointXY(x0, y0), QgsPointXY(x0 + 0.02, y0), QgsPointXY(x0 + 0.02, y0 + 0.015),
                                       QgsPointXY(x0, y0 + 0.015), QgsPointXY(x0, y0)]])


def renderizar(lyr, qml, eid, arquivo=None):
    """A feição sozinha, com o estilo da camada, numa janela fixa (zoom perto de 13)."""
    vl = QgsVectorLayer(lyr.source(), 'r', 'ogr')
    vl.importNamedStyle(qml)
    vl.setSubsetString('"ebgeo_id" = \'{}\''.format(eid))
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(500, 360))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), ms.destinationCrs(), QgsProject.instance())
    c = tr.transform(QgsPointXY(-46.99, -14.993))
    ms.setExtent(QgsRectangle(c.x() - 3500, c.y() - 2500, c.x() + 3500, c.y() + 2500))
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.globalScope())
    ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererSequentialJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    if arquivo:
        img.save(os.path.join(SAIDA, arquivo))
    return img


def pixels_diferentes(a, b):
    import numpy as np
    a = a.convertToFormat(QImage.Format.Format_ARGB32)
    b = b.convertToFormat(QImage.Format.Format_ARGB32)
    na = np.frombuffer(a.constBits().asarray(a.sizeInBytes()), dtype=np.uint32)
    nb = np.frombuffer(b.constBits().asarray(b.sizeInBytes()), dtype=np.uint32)
    return int((na != nb).sum())


def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


def _expandir(painel):
    """Abre os grupos recolhidos do dock para a captura (ele recolhe a Correção de Zoom na volta ao laço)."""
    import time
    from qgis.gui import QgsCollapsibleGroupBoxBasic
    for _ in range(10):
        _app.processEvents()
        caixas = painel.form_host.findChildren(QgsCollapsibleGroupBoxBasic)
        for caixa in caixas:
            caixa.setCollapsed(False)
        _app.processEvents()
        if all(not c.isCollapsed() for c in caixas):
            return
        time.sleep(0.05)


def _montar(cls, nome):
    """
    O calco com uma camada por tipo, estilizada como o importador a deixa (o estilo do tipo e a regra
    de "visivel" do atlas, arvore.esconder_por_regra), e o dock solto e à mostra.
    """
    from Calco.importador import arvore
    cls.caminho = os.path.join(TMP, nome + '.gpkg')
    gpkg.criar_calco(cls.caminho, TIPOS)
    cls.camadas, cls.qml = {}, {}
    for tipo in TIPOS:
        vl = QgsVectorLayer(gpkg.uri_camada(cls.caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
        vl.setCustomProperty(PROP_CAMINHO, cls.caminho)
        vl.setCustomProperty(PROP_TIPO, tipo)
        assert C.aplicar_estilo(vl, tipo), tipo
        arvore.esconder_por_regra(vl, arvore.COND_VISIVEL)
        C.aplicar_formulario(vl, tipo)
        QgsProject.instance().addMapLayer(vl)
        cls.camadas[tipo] = vl
        doc = QDomDocument()
        vl.exportNamedStyle(doc, QgsReadWriteContext())
        cls.qml[tipo] = doc
    cls.painel = P.PainelCalco(get_iface())
    cls.painel.setParent(None)
    cls.painel.resize(440, 980)
    cls.painel.show()


class TesteDockNulos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _montar(cls, 'dock_nulos')
        cls.resultados = cls._medir_todos()

    @classmethod
    def _nova(cls, tipo, attrs):
        a = dict(attrs, ebgeo_id=str(uuid.uuid4()))
        lyr = cls.camadas[tipo]
        eid = gravar_feicao(lyr, tipo, geometria(tipo), a)
        assert eid, (tipo, attrs)
        return eid

    @classmethod
    def _abrir(cls, tipo, eid):
        lyr = cls.camadas[tipo]
        cls.painel._camada_mudou(lyr)
        cls.painel.mostrar_feicao(lyr, eid)
        cls.painel._selecao_mudou()

    @classmethod
    def _mostrado(cls, col):
        """O valor que o dock mostra, na unidade da coluna; None quando diz "Não definido"."""
        w, kind = cls.painel.widgets[col], cls.painel._tipos_widget[col]
        w = getattr(w, 'spin', w)
        if w.specialValueText() and w.value() == w.minimum():
            assert w.specialValueText() == TEXTO_NULO
            return None
        v = float(w.value())
        if kind == 'km_em_m':
            return v / 1000.0
        if kind == 'area_pct':
            return v / 100.0
        if col == 'angulo_secundario' and cls.painel._setor is not None:  # o dock mostra o azimute
            return P.normalizar_relativo(v - cls.painel._setor[0])
        return v

    @classmethod
    def _faixa(cls, col):
        """(mínimo, máximo) da caixa do campo na unidade da coluna, sem o passo de "Não definido"."""
        w, kind = cls.painel.widgets[col], cls.painel._tipos_widget[col]
        w = getattr(w, 'spin', w)
        lo = w.minimum() + (w.singleStep() if w.property('ebgeo_nulo') else 0)
        hi = w.maximum()
        f = 1000.0 if kind == 'km_em_m' else 100.0 if kind == 'area_pct' else 1.0
        if col == 'angulo_secundario':
            return -180.0, 180.0
        return lo / f, hi / f

    @classmethod
    def _medir_todos(cls):
        res = []
        for tipo, col, rot, base in casos():
            a = dict(base, nome='nulo')
            a[col] = None
            eid = cls._nova(tipo, a)
            cls._abrir(tipo, eid)
            lyr = cls.camadas[tipo]
            visivel = col in cls.painel.campos_visiveis()
            v = cls._mostrado(col)
            lo, hi = cls._faixa(col)
            # abrir no dock não grava nada
            f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
            gravou = not _nulo(f[col]) or lyr.isEditable()
            img_nulo = renderizar(lyr, cls.qml[tipo], eid)
            r = dict(tipo=tipo, col=col, conf=rot, mostrado=v, visivel=visivel, gravou=gravou, faixa=(lo, hi))
            if v is not None:
                eid_v = cls._nova(tipo, dict(base, nome='mostrado', **{col: v}))
                r['dif_mostrado'] = pixels_diferentes(img_nulo, renderizar(lyr, cls.qml[tipo], eid_v))
            # outro valor da faixa que desenhe outra coisa: o campo foi exercitado nesta configuração
            r['outro'], r['dif_outro'] = None, 0
            for frac in (0.37, 0.71, 0.13, 0.9, 0.04, 0.01, 0.004):
                cand = round(lo + frac * (hi - lo), 2)
                if v is not None and abs(cand - v) <= 1e-6:
                    continue
                eid_alt = cls._nova(tipo, dict(base, nome='outro', **{col: cand}))
                d = pixels_diferentes(img_nulo, renderizar(lyr, cls.qml[tipo], eid_alt))
                r['outro'], r['dif_outro'] = cand, d
                if d:
                    break
            eid_min = cls._nova(tipo, dict(base, nome='mínimo', **{col: lo}))
            r['dif_minimo'] = pixels_diferentes(img_nulo, renderizar(lyr, cls.qml[tipo], eid_min))
            res.append(r)
        return res

    def test_o_dock_mostra_o_que_o_estilo_desenha(self):
        erros, nao_definidos = [], []
        for r in self.resultados:
            nome = '{} {} {}'.format(r['tipo'], r['col'], r['conf']).strip()
            self.assertFalse(r['gravou'], nome + ': abrir no dock gravou')
            if r['mostrado'] is None:
                nao_definidos.append(nome)
                continue
            if r['dif_mostrado'] != 0:
                erros.append((nome, r['mostrado'], r['dif_mostrado']))
        MEDIDAS.append('{} campos numéricos em {} tipos ({} configurações): {} com o número do estilo, {} "Não definido" ({})'.format(
            len({(r['tipo'], r['col']) for r in self.resultados}), len({r['tipo'] for r in self.resultados}),
            len(self.resultados), len(self.resultados) - len(nao_definidos), len(nao_definidos), ', '.join(nao_definidos)))
        self.assertEqual(erros, [])

    def test_cada_campo_exercitado(self):
        """
        Outro valor da faixa desenha outra coisa: o caso prova o campo. Ficam de fora o campo oculto
        na configuração (o tamanho do glifo da Linha de Coordenação 140000, que não tem glifo; a
        290199 o exercita) e a coluna que o estilo não lê, em que o dock diz "Não definido".
        """
        exercitados = {(r['tipo'], r['col']) for r in self.resultados if r['dif_outro'] > 0}
        sem_leitura = {(r['tipo'], r['col']) for r in self.resultados if r['mostrado'] is None and r['dif_outro'] == 0}
        faltam = sorted({(r['tipo'], r['col']) for r in self.resultados} - exercitados - sem_leitura)
        self.assertEqual(faltam, [])
        visiveis_sem_prova = sorted('{} {} {}'.format(r['tipo'], r['col'], r['conf']).strip() for r in self.resultados
                                    if r['visivel'] and r['dif_outro'] == 0 and (r['tipo'], r['col']) not in sem_leitura)
        self.assertEqual(visiveis_sem_prova, [])
        MEDIDAS.append('exercitados {} campos; o estilo não lê: {}'.format(
            len(exercitados), ', '.join(' '.join(x) for x in sorted(sem_leitura))))

    def test_nao_definido_so_onde_o_minimo_mentiria_ou_o_estilo_nao_le(self):
        """
        "Não definido" só onde não há número do estilo: o mínimo da faixa desenharia outra coisa (o
        zoom de criação das formas, que o estilo lê como "sem âncora") ou a coluna não desenha.
        """
        for r in self.resultados:
            if r['mostrado'] is None:
                self.assertTrue(r['dif_minimo'] > 0 or r['dif_outro'] == 0, r)

    def test_regua_reprova_o_minimo_da_faixa(self):
        """
        Pior caso, a saída REAL de antes: o mínimo da faixa no lugar do nulo. A régua o reprova nos
        campos em que o mínimo não é o que o estilo desenha.
        """
        reprovados = sorted('{} {}'.format(r['tipo'], r['col']) for r in self.resultados
                            if r['mostrado'] is not None and r['dif_minimo'] > 0)
        MEDIDAS.append('o mínimo da faixa (o dock de antes) desenharia outra coisa em {} de {} casos'.format(
            len(reprovados), sum(1 for r in self.resultados if r['mostrado'] is not None)))
        # (na Área, o espaçamento 2 desenha como o 8 do nulo: abaixo do piso o período dobra)
        for esperado in ['{} hatch_spacing'.format(t) for t in FORMAS] + \
                ['{} hatch_line_width'.format(t) for t in FORMAS + ('coordination_area',)] + \
                ['arrow width_m', 'coordination_line line_width', 'military_symbol size', 'text size']:
            self.assertIn(esperado, reprovados)
        self.assertGreater(len(reprovados), 60)

    def test_opacidade_da_area_com_e_sem_hachura(self):
        """Na Área a opacidade nula é 1 na hachura e 0 no preenchimento: o dock mostra a da feição."""
        vistos = {r['conf']: r['mostrado'] for r in self.resultados
                  if (r['tipo'], r['col']) == ('coordination_area', 'opacity')}
        self.assertEqual(vistos, {'': 1.0, 'sem hachura': 0.0})

    def test_nao_definido_grava_nulo_e_o_minimo_grava_o_minimo(self):
        tipo = 'point'
        lyr = self.camadas[tipo]
        a = dict(schema.padroes(tipo), nome='zoom')
        a['created_zoom'] = None
        eid = self._nova(tipo, a)
        self._abrir(tipo, eid)
        w = self.painel.widgets['created_zoom']
        self.assertEqual(w.text(), TEXTO_NULO)
        w.setValue(w.minimum() + w.singleStep())   # o mínimo da faixa: zoom 0
        self.painel._gravar_pendentes()
        self.assertEqual(lyr.getFeature(self.painel.fid)['created_zoom'], 0.0)
        w.setValue(w.minimum())                     # de volta a "Não definido"
        self.painel._gravar_pendentes()
        self.assertTrue(_nulo(lyr.getFeature(self.painel.fid)['created_zoom']))
        self.assertTrue(self.painel.descartar())

    def test_salvar_so_o_nome_pelo_dock_nao_muda_coluna_nem_pixel(self):
        mudancas = {}
        for tipo in TIPOS:
            lyr = self.camadas[tipo]
            a = dict(schema.padroes(tipo), nome='antes')
            a.update(ATIVADORES.get(tipo, {}))
            for col, tp, _p, _w in schema.campos(tipo):
                if tp in ('real', 'int') and col not in ('largura_px', 'altura_px', 'ancora_dx', 'ancora_dy'):
                    a[col] = None
            if tipo == 'image':
                a['bitmap_b64'] = _png_b64()
            eid = self._nova(tipo, a)
            antes_img = renderizar(lyr, self.qml[tipo], eid)
            antes = next(QgsVectorLayer(lyr.source(), 'd', 'ogr').getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
            self._abrir(tipo, eid)
            ed = self.painel.widgets['nome']
            ed.setText('depois')
            ed.editingFinished.emit()
            self.painel._gravar_pendentes()
            self.assertTrue(self.painel.salvar(), tipo)
            depois = next(QgsVectorLayer(lyr.source(), 'd', 'ogr').getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
            self.assertEqual(depois['nome'], 'depois', tipo)
            for campo in antes.fields().names():
                if campo in ('nome', 'atualizado_em', 'fid'):
                    continue
                va, vd = antes[campo], depois[campo]
                if _nulo(va) and _nulo(vd):
                    continue
                if va != vd:
                    mudancas.setdefault(tipo, {})[campo] = (va, vd)
            d = pixels_diferentes(antes_img, renderizar(lyr, self.qml[tipo], eid))
            if d:
                mudancas.setdefault(tipo, {})['pixels'] = d
        self.assertEqual(mudancas, {})

    def test_capturas(self):
        """Capturas do dock com nulos (lidas a olho): a hachura do Polígono, a Seta e o zoom do Ponto."""
        for tipo, extra, arquivo in (
                ('polygon', dict(hatch_spacing=None, hatch_line_width=None, line_width=None, opacity=None),
                 'dock_nulos_poligono_hachura.png'),
                ('arrow', dict(width_m=None, head_length_ratio=None, line_width=None, fill_opacity=None),
                 'dock_nulos_seta.png'),
                ('point', dict(created_zoom=None, size=None, label_size=None), 'dock_nulos_ponto_zoom.png'),
                ('coordination_area', dict(opacity=None, hatch_spacing=None, hatch_line_width=None, text_size=None,
                                           line_width=None), 'dock_nulos_area.png')):
            a = dict(schema.padroes(tipo), nome='nulos')
            a.update(ATIVADORES.get(tipo, {}))
            a.update(extra)
            eid = self._nova(tipo, a)
            self._abrir(tipo, eid)
            from Calco.ui.blocos.previa import esperar
            from qgis.gui import QgsCollapsibleGroupBoxBasic
            self.painel.resize(440, 1500)
            _expandir(self.painel)
            esperar(self.painel)
            self.painel.grab().save(os.path.join(SAIDA, arquivo))
            self.painel.resize(440, 980)
            for col in extra:
                if col in self.painel.widgets:
                    w = getattr(self.painel.widgets[col], 'spin', self.painel.widgets[col])
                    self.assertNotEqual(w.text(), '', col)


# Configurações a mais de um campo lógico: (rótulo, colunas)
EXTRAS_LOGICOS = {
    ('coordination_area', 'text_north_facing'): [('150000 sobre a borda', dict(
        symbol_code='150000', text_position='borda', tipo='Obj', identificacao='BAGRE', hatch_type='none',
        hatch_enabled=False))],
    ('coordination_area', 'portoes_ocultos'): [('170999-01 com portão', dict(
        symbol_code='170999-01', tipo='VAB', identificacao='CONDOR', hatch_type='none', hatch_enabled=False,
        portoes='[{"ratio": 0.3, "nome": "PORTÃO ALFA"}]'))],
}


def casos_logicos():
    """(tipo, coluna, rótulo da configuração, atributos de base) de todo campo lógico que o dock edita."""
    out = []
    for tipo in TIPOS:
        tps = {c: tp for c, tp, _p, _w in schema.campos(tipo)}
        for campo in esp.formulario(tipo).campos():
            if tps.get(campo.coluna) != 'bool' or campo.somente_leitura:
                continue
            base = dict(schema.padroes(tipo))
            base.update(ATIVADORES.get(tipo, {}))
            if tipo == 'image':
                base['bitmap_b64'] = _png_b64()
            # a correção de zoom só desenha com um zoom de referência longe do zoom da janela (~13)
            if campo.coluna == 'zoom_corr' and 'created_zoom' in tps:
                base['created_zoom'] = 10.0
            if campo.coluna == 'label_zoom_corr':
                base['label_created_zoom'] = 10.0
            confs = [('', base)] + [(r, dict(base, **x)) for r, x in EXTRAS_LOGICOS.get((tipo, campo.coluna), [])]
            out += [(tipo, campo.coluna, rot, a) for rot, a in confs]
    return out


class TesteDockLogicosNulos(unittest.TestCase):
    """
    A caixa de marcar da coluna lógica NULA mostra o que o estilo desenha, sem gravar (o
    "mostrar no mapa" nulo é mostrar, a Correção de Zoom nula é corrigir, o texto da Área nulo fica
    para o norte), lido do próprio estilo (ui/padrao_estilo.py); sem forma no estilo, o terceiro
    estado, "Não definido". Antes a caixa nula aparecia desmarcada (salvo o "mostrar no mapa" e as
    caixas da Seta, do Limite e da Frente, que liam o padrão do .exp). Mesma régua dos números:
    nulo e estado mostrado desenham os mesmos pixels, o outro estado desenha outros, e o desmarcado
    de antes é reprovado onde o estilo desenha o nulo como marcado.
    """

    @classmethod
    def setUpClass(cls):
        _montar(cls, 'dock_logicos_nulos')
        cls.resultados = []
        for tipo, col, rot, base in casos_logicos():
            a = dict(base, nome='nulo')
            a[col] = None
            eid = cls._nova(tipo, a)
            lyr = cls.camadas[tipo]
            cls._anular(lyr, eid, col)
            cls._abrir(tipo, eid)
            w = cls.painel.widgets[col]
            estado = w.checkState()
            v = None if estado == Qt.CheckState.PartiallyChecked else estado == Qt.CheckState.Checked
            if v is None:
                assert w.text() == TEXTO_NULO, (tipo, col)
            f = next(lyr.getFeatures('"ebgeo_id" = \'{}\''.format(eid)))
            r = dict(tipo=tipo, col=col, conf=rot, mostrado=v, visivel=col in cls.painel.campos_visiveis(),
                     gravou=not _nulo(f[col]) or lyr.isEditable())
            img = renderizar(lyr, cls.qml[tipo], eid)
            for chave, x in (('dif_verdadeiro', True), ('dif_falso', False)):
                e = cls._nova(tipo, dict(base, nome=chave, **{col: x}))
                r[chave] = pixels_diferentes(img, renderizar(lyr, cls.qml[tipo], e))
            cls.resultados.append(r)

    @staticmethod
    def _anular(lyr, eid, col):
        """A coluna nula no disco: a gravação da Seta põe falso nas caixas nulas (o calco antigo as tem nulas)."""
        filtro = '"ebgeo_id" = \'{}\''.format(eid)
        f = next(lyr.getFeatures(filtro))
        if not _nulo(f[col]):
            assert lyr.dataProvider().changeAttributeValues({f.id(): {lyr.fields().indexOf(col): None}})
            lyr.reload()
        assert _nulo(next(lyr.getFeatures(filtro))[col]), col

    _nova = TesteDockNulos.__dict__['_nova']  # o classmethod, ligado a esta classe
    _abrir = TesteDockNulos.__dict__['_abrir']

    def _nome(self, r):
        return '{} {} {}'.format(r['tipo'], r['col'], r['conf']).strip()

    def test_a_caixa_mostra_o_que_o_estilo_desenha(self):
        erros, nao_definidos = [], []
        for r in self.resultados:
            self.assertFalse(r['gravou'], self._nome(r) + ': abrir no dock gravou')
            if r['mostrado'] is None:
                nao_definidos.append(self._nome(r))
                continue
            d = r['dif_verdadeiro'] if r['mostrado'] else r['dif_falso']
            if d:
                erros.append((self._nome(r), r['mostrado'], d))
        MEDIDAS.append('{} campos lógicos em {} tipos ({} configurações): {} com o estado do estilo, {} "Não definido" ({})'.format(
            len({(r['tipo'], r['col']) for r in self.resultados}), len({r['tipo'] for r in self.resultados}),
            len(self.resultados), len(self.resultados) - len(nao_definidos), len(nao_definidos), ', '.join(nao_definidos)))
        self.assertEqual(erros, [])

    def test_cada_campo_exercitado(self):
        """O outro estado desenha outra coisa em ao menos uma configuração; fora disso, só o que o estilo não lê."""
        exercitados = {(r['tipo'], r['col']) for r in self.resultados if r['dif_verdadeiro'] or r['dif_falso']}
        sem_leitura = {(r['tipo'], r['col']) for r in self.resultados
                       if r['mostrado'] is None and not (r['dif_verdadeiro'] or r['dif_falso'])}
        faltam = sorted({(r['tipo'], r['col']) for r in self.resultados} - exercitados - sem_leitura)
        self.assertEqual(faltam, [])
        # "Não definido" só onde nenhum estado desenha como o nulo, ou nenhum desenha diferente
        for r in self.resultados:
            if r['mostrado'] is None:
                self.assertTrue((r['dif_verdadeiro'] and r['dif_falso']) or not (r['dif_verdadeiro'] or r['dif_falso']), r)
        MEDIDAS.append('lógicos exercitados: {}; o estilo não lê: {}'.format(
            len(exercitados), ', '.join(' '.join(x) for x in sorted(sem_leitura))))

    def test_regua_reprova_o_desmarcado_de_antes(self):
        """
        Pior caso, a saída REAL de antes: a caixa nula desmarcada (o "mostrar no mapa" marcado). A
        régua a reprova onde o estilo desenha o nulo como marcado.
        """
        reprovados = sorted({'{} {}'.format(r['tipo'], r['col']) for r in self.resultados
                             if (r['dif_verdadeiro'] if r['col'] == 'visivel' else r['dif_falso'])})
        MEDIDAS.append('a caixa de antes desenharia outra coisa em: ' + ', '.join(reprovados))
        for esperado in ['military_symbol zoom_corr', 'coordination_measure zoom_corr', 'engineering_symbol zoom_corr',
                         'magnetic_declination zoom_corr', 'coordination_line zoom_corr',
                         'coordination_area zoom_corr', 'coordination_area text_north_facing']:
            self.assertIn(esperado, reprovados)

    def test_terceiro_estado_grava_nulo(self):
        tipo = 'point'
        lyr = self.camadas[tipo]
        a = dict(schema.padroes(tipo), nome='caixa')
        a['label_zoom_corr'] = None
        eid = self._nova(tipo, a)
        self._abrir(tipo, eid)
        w = self.painel.widgets['label_zoom_corr']
        self.assertEqual((w.checkState(), w.text()), (Qt.CheckState.PartiallyChecked, TEXTO_NULO))
        w.setCheckState(Qt.CheckState.Checked)
        self.painel._gravar_pendentes()
        self.assertIs(lyr.getFeature(self.painel.fid)['label_zoom_corr'], True)
        self.assertEqual(w.text(), '')
        w.setCheckState(Qt.CheckState.PartiallyChecked)
        self.painel._gravar_pendentes()
        self.assertTrue(_nulo(lyr.getFeature(self.painel.fid)['label_zoom_corr']))
        self.assertTrue(self.painel.descartar())

    def test_captura(self):
        """
        O Ponto com as caixas nulas: "Mostrar no mapa" marcada (a regra do atlas mostra a nula), a
        Correção de Zoom do marcador marcada (o estilo das formas lê a nula como ligada, como o Web) e a do
        rótulo "Não definido" (o estilo não a lê).
        """
        tipo = 'point'
        a = dict(schema.padroes(tipo), nome='caixas nulas', zoom_corr=None, label_zoom_corr=None, visivel=None,
                 created_zoom=10.0)
        a.update(ATIVADORES[tipo])
        eid = self._nova(tipo, a)
        for col in ('zoom_corr', 'label_zoom_corr', 'visivel'):
            self._anular(self.camadas[tipo], eid, col)
        self._abrir(tipo, eid)
        from Calco.ui.blocos.previa import esperar
        from qgis.gui import QgsCollapsibleGroupBoxBasic
        self.painel.resize(440, 1500)
        _expandir(self.painel)
        esperar(self.painel)
        self.painel.grab().save(os.path.join(SAIDA, 'dock_nulos_ponto_caixas.png'))
        self.painel.resize(440, 980)
        self.assertEqual(self.painel.widgets['zoom_corr'].checkState(), Qt.CheckState.Checked)
        self.assertEqual(self.painel.widgets['visivel'].checkState(), Qt.CheckState.Checked)
        self.assertEqual(self.painel.widgets['label_zoom_corr'].checkState(), Qt.CheckState.PartiallyChecked)


def tearDownModule():
    print('\n--- medidas ---')
    for t in MEDIDAS:
        print(t)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
