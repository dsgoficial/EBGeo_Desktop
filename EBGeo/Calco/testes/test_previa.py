# -*- coding: utf-8 -*-
"""
Prévia do símbolo no formulário, como no painel do Web.

  - Nativo, num processo NOVO e SEM o plugin: nos pontuais com SVG (militar, engenharia,
    declinação, medida), o elemento de texto no topo da primeira aba desenha o SVG gravado na
    feição (imagem data:), sem código. Pior caso: a feição sem SVG nem PNG não desenha nada, e a
    régua (pixels do símbolo no rótulo) o reprova.
  - Dock: a mesma prévia desenhada do SVG do buffer, que muda quando o SIDC muda (o guardião
    redesenha no mesmo comando); nas linhas, áreas, táticos e comuns, a amostra com o estilo da
    camada e os atributos da feição, que muda quando a cor muda no buffer.
  - Nativo das linhas, áreas, táticos e comuns: não há expressão que desenhe o estilo da camada
    numa imagem; fica só no dock.

Capturas em EBGEO_TESTE_SAIDA (padrão: temporária).
    python-qgis.bat EBGeo/Calco/testes/test_previa.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
RAIZ_REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, PLUGIN)
sys.path.insert(0, AQUI)

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import schema  # noqa: E402
from Calco.calco import PROP_CAMINHO, PROP_TIPO  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_previa_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
FIXTURES = os.path.abspath(os.environ.get('EBGEO_FIXTURES') or os.path.join(RAIZ_REPO, '..', '_ebgeo_dados_teste'))
FIXTURE_06 = os.path.join(FIXTURES, '06-completo-3.0.ebgeo')
MEDIDAS = []
TIPOS_SVG = ('military_symbol', 'engineering_symbol', 'magnetic_declination')

SCRIPT = r'''
import sys, os, json
gp, saida, pasta, tabelas = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
from qgis.core import QgsApplication, QgsVectorLayer
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm
from qgis.PyQt.QtWidgets import QLabel
QgsGui.editorWidgetRegistry().initEditors()
res = {}
for t in tabelas:
    L = QgsVectorLayer(gp + '|layername=' + t, t, 'ogr')
    for f in L.getFeatures():
        form = QgsAttributeForm(L, f); form.resize(480, 640); form.show(); app.processEvents()
        alvo = [lb for lb in form.findChildren(QLabel) if 'data:image/' in lb.text() or lb.objectName() == 'previa']
        rotulos = [lb for lb in form.findChildren(QLabel) if lb.isVisibleTo(form) and lb.text().startswith('<img')]
        px = 0
        for lb in rotulos:
            im = lb.grab().toImage()
            fundo = im.pixel(0, 0)
            px += sum(1 for y in range(0, im.height(), 2) for x in range(0, im.width(), 2) if im.pixel(x, y) != fundo)
        res['{}|{}'.format(t, f['nome'])] = {'rotulos_img': len(rotulos), 'pixels': px}
        if pasta:
            form.grab().save(os.path.join(pasta, 'nativo_previa_{}_{}.png'.format(t, f['nome']).replace(' ', '_')))
        form.close(); form.deleteLater(); app.processEvents()
with open(saida, 'w', encoding='utf-8') as fh:
    json.dump(res, fh, ensure_ascii=False)
'''


def rodar_sem_plugin(caminho, tabelas, pasta=''):
    script = os.path.join(TMP, 'previa_sem_plugin.py')
    with open(script, 'w', encoding='utf-8') as fh:
        fh.write(SCRIPT)
    saida = os.path.join(TMP, 'res_{}.json'.format(uuid.uuid4().hex[:8]))
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    exe = os.path.join(os.path.dirname(sys.executable), 'python-qgis.bat')
    exe = exe if os.path.exists(exe) else sys.executable
    args = [exe, script, caminho, saida, pasta] + list(tabelas)
    subprocess.run(args, capture_output=True, env=env, cwd=TMP, shell=exe.endswith('.bat'), timeout=300)
    with open(saida, encoding='utf-8') as fh:
        return json.load(fh)


class TesteNativo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_formulario_militar as TM
        cls.caminho = os.path.join(TMP, 'militar.gpkg')
        TM.criar_calco(cls.caminho)
        cls.res = rodar_sem_plugin(cls.caminho, TIPOS_SVG, SAIDA)

    def test_especificacao_tem_a_previa_no_topo(self):
        for tipo in TIPOS_SVG + ('coordination_measure',):
            primeira = esp.formulario(tipo).abas[0].filhos[0]
            self.assertIsInstance(primeira, esp.Texto, tipo)
            self.assertEqual(primeira.nome, esp.NOME_PREVIA, tipo)

    def test_sem_plugin_desenha_o_simbolo(self):
        vistos = 0
        for chave, r in self.res.items():
            self.assertEqual(r['rotulos_img'], 1, chave)
            self.assertGreater(r['pixels'], 40, chave)  # o diagrama de nortes é de traço fino
            vistos += 1
        self.assertGreaterEqual(vistos, 8)
        MEDIDAS.append('nativo sem o plugin: {} feições com a prévia desenhada ({} a {} pixels do símbolo)'.format(
            vistos, min(r['pixels'] for r in self.res.values()), max(r['pixels'] for r in self.res.values())))

    def test_pior_caso_sem_svg_reprova(self):
        import shutil
        from osgeo import ogr
        caminho = os.path.join(TMP, 'sem_svg.gpkg')
        shutil.copy(self.caminho, caminho)
        ds = ogr.Open(caminho, 1)  # pelo OGR: os gatilhos do GeoPackage pedem as funções ST_ dele
        ds.ExecuteSQL("UPDATE military_symbol SET svg = NULL, bitmap_b64 = NULL WHERE nome = 'Militar 10'")
        ds = None
        res = rodar_sem_plugin(caminho, ('military_symbol',))
        self.assertEqual(res['military_symbol|Militar 10']['pixels'], 0)
        self.assertGreater(res['military_symbol|Militar 15']['pixels'], 200)


@unittest.skipUnless(os.path.exists(FIXTURE_06), 'fixture 06-completo-3.0.ebgeo ausente')
class TesteDock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.testing.mocked import get_iface
        from Calco.importador import arvore, escritor
        from Calco.ui.painel import PainelCalco
        import test_formulario_militar as TM
        cls.caminho = os.path.join(TMP, 'dock.gpkg')
        escritor.importar(FIXTURE_06, cls.caminho)
        arvore.salvar_estilos(cls.caminho)
        cls.militar = os.path.join(TMP, 'dock_militar.gpkg')
        TM.criar_calco(cls.militar)
        cls.iface = get_iface()
        cls.painel = PainelCalco(cls.iface)
        cls.painel.setParent(None)
        cls.painel.resize(440, 980)
        cls.painel.show()

    def tearDown(self):
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.isEditable():
                lyr.rollBack()
        _app.processEvents()

    def _camada(self, caminho, tipo):
        vl = QgsVectorLayer('{}|layername={}'.format(caminho, schema.TIPOS[tipo]['tabela']), schema.TIPOS[tipo]['nome_pt'], 'ogr')
        vl.setCustomProperty(PROP_CAMINHO, caminho)
        vl.setCustomProperty(PROP_TIPO, tipo)
        QgsProject.instance().addMapLayer(vl)
        return vl

    def _mostrar(self, vl, fid):
        self.painel._camada_mudou(vl)
        vl.selectByIds([fid])
        self.painel._selecao_mudou()
        _app.processEvents()

    def _esperar_amostra(self, w, desenhos):
        import time
        fim = time.time() + 20
        while w.desenhos < desenhos and time.time() < fim:
            _app.processEvents()
            time.sleep(0.05)
        return w.desenhos >= desenhos

    def test_previa_do_simbolo_segue_o_sidc(self):
        from qgis.PyQt.QtWidgets import QLabel
        vl = self._camada(self.militar, 'military_symbol')
        f = next(vl.getFeatures("\"nome\" = 'Militar 10'"))
        self._mostrar(vl, f.id())
        prev = self.painel.findChild(QLabel, 'EBGeoPreviaSimbolo')
        self.assertIsNotNone(prev)
        antes = prev.pixmap().toImage()
        self.assertFalse(antes.isNull())
        self.painel.grab().save(os.path.join(SAIDA, 'dock_previa_militar_antes.png'))
        sidc_novo = '10061000001211000000'  # outro ícone no mesmo conjunto
        self.painel._mudou('sidc', sidc_novo)
        self.painel._gravar_pendentes()
        _app.processEvents()
        depois = prev.pixmap().toImage()
        self.assertFalse(depois.isNull())
        self.assertNotEqual(antes, depois, 'a prévia devia mudar com o SIDC no buffer')
        self.painel.grab().save(os.path.join(SAIDA, 'dock_previa_militar_depois.png'))

    def test_amostra_nas_linhas_areas_taticos_e_comuns(self):
        from qgis.PyQt.QtWidgets import QLabel
        vistos = []
        for tipo in ('line', 'polygon', 'coordination_line', 'coordination_area', 'boundary', 'arrow'):
            vl = self._camada(self.caminho, tipo)
            f = next(vl.getFeatures(), None)
            if f is None:
                continue
            import time
            t0 = time.perf_counter()
            self.painel._camada_mudou(vl)
            vl.selectByIds([f.id()])
            self.painel._selecao_mudou()  # a montagem: a amostra só começa na volta ao laço de eventos
            ms = (time.perf_counter() - t0) * 1000
            _app.processEvents()
            w = self.painel.findChild(QLabel, 'EBGeoPreviaAmostra')
            self.assertIsNotNone(w, tipo)
            self.assertLess(ms, 1500, 'o desenho da amostra não pode entrar na montagem do dock')
            self.assertTrue(self._esperar_amostra(w, 1), tipo)
            # o que o redesenho custa à linha da interface (o resto roda no job paralelo)
            w._chave = None
            t0 = time.perf_counter()
            w.desenhar()
            ms_linha = (time.perf_counter() - t0) * 1000
            self.assertTrue(self._esperar_amostra(w, 2), tipo)
            img = w.pixmap().toImage()
            cheios = sum(1 for y in range(0, img.height(), 2) for x in range(0, img.width(), 2) if img.pixelColor(x, y).alpha() > 0)
            self.assertGreater(cheios, 50, tipo)
            vistos.append((tipo, cheios, '{:.0f} ms de montagem, {:.0f} ms de redesenho na interface'.format(ms, ms_linha)))
            self.painel.grab().save(os.path.join(SAIDA, 'dock_amostra_{}.png'.format(tipo)))
            # o passo entre os campos de uma linha é o mesmo em cada seção (botão de cor e caixa de
            # marcar com a altura da caixa de texto)
            _app.processEvents()
            from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit
            from qgis.gui import QgsColorButton
            por_secao = {}
            for el, _c, fl, w, _r in self.painel._linhas:
                if isinstance(w, (QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QgsColorButton)) and w.isVisibleTo(self.painel):
                    por_secao.setdefault(id(fl), []).append((w.mapTo(self.painel, w.rect().topLeft()).y(), w.height()))
            for linhas in por_secao.values():
                linhas.sort()
                self.assertEqual(len({h for _y, h in linhas}), 1, (tipo, linhas))
        MEDIDAS.append('dock, amostras com o estilo da camada: {}'.format(vistos))
        self.assertGreaterEqual(len(vistos), 5)

    def test_amostra_do_texto_inteira(self):
        """O texto cabe na amostra: nada pintado nas bordas esquerda e direita (o texto cortado reprova)."""
        from qgis.PyQt.QtWidgets import QLabel
        vl = self._camada(self.caminho, 'text')
        f = next(f for f in vl.getFeatures() if len(str(f['text'] or '')) > 15)
        self._mostrar(vl, f.id())
        w = self.painel.findChild(QLabel, 'EBGeoPreviaAmostra')
        self.assertTrue(self._esperar_amostra(w, 1))
        img = w.pixmap().toImage()
        borda = [(x, y) for x in (0, 1, img.width() - 2, img.width() - 1) for y in range(img.height())
                 if img.pixelColor(x, y).alpha() > 40]
        self.assertEqual(borda[:5], [], 'o texto da amostra sai cortado nas bordas')
        self.assertLessEqual(img.width(), 320)
        self.painel.grab().save(os.path.join(SAIDA, 'dock_amostra_text.png'))

    def test_amostra_segue_a_cor_no_buffer(self):
        from qgis.PyQt.QtWidgets import QLabel
        vl = self._camada(self.caminho, 'line')
        f = next(vl.getFeatures())
        self._mostrar(vl, f.id())
        w = self.painel.findChild(QLabel, 'EBGeoPreviaAmostra')
        self.assertTrue(self._esperar_amostra(w, 1))
        antes = w.pixmap().toImage()
        n = w.desenhos
        self.painel._mudou('line_color', '#ff00ff')
        self.painel._gravar_pendentes()
        self.assertTrue(self._esperar_amostra(w, n + 1))
        depois = w.pixmap().toImage()
        magenta = sum(1 for y in range(0, depois.height(), 2) for x in range(0, depois.width(), 2)
                      if depois.pixelColor(x, y).red() > 200 and depois.pixelColor(x, y).blue() > 200
                      and depois.pixelColor(x, y).green() < 80 and depois.pixelColor(x, y).alpha() > 200)
        self.assertNotEqual(antes, depois)
        self.assertGreater(magenta, 20)


def cor_da_tinta(img, cx, cy, r=20):
    """
    (cor, cobertura) da janela (2r+1)² em volta de (cx, cy): a cor mais frequente, composta sobre
    branco e sem os pixels quase brancos (o preenchimento liso, ou o miolo do traço da hachura;
    branco puro quando a janela não tem tinta), e a fração da janela com tinta (1 no liso, menos
    na hachura).
    """
    from collections import Counter
    cont = Counter()
    total = 0
    for y in range(max(0, cy - r), min(img.height(), cy + r + 1)):
        for x in range(max(0, cx - r), min(img.width(), cx + r + 1)):
            c = img.pixelColor(x, y)
            a = c.alphaF()
            rgb = tuple(int(round(a * v + (1 - a) * 255)) for v in (c.red(), c.green(), c.blue()))
            total += 1
            if min(rgb) < 248:
                cont[rgb] += 1
    return (cont.most_common(1)[0][0] if cont else (255, 255, 255)), sum(cont.values()) / max(1, total)


class TesteAmostraDoPoligono(unittest.TestCase):
    """
    A amostra no topo do dock do polígono tem, no centro, a cor que o mapa desenha na mesma feição,
    em TODOS os casos de hachura: caixa marcada, desmarcada e nula, vezes os tipos da lista e o
    nulo, com o preenchimento semitransparente (#00897b a 50 %, que o mapa desenha #7fc4bd sobre
    branco). O desenho em paralelo com fundo branco transparente branqueava o preenchimento
    (convencoes.FUNDO_AMOSTRA), e o pior caso o devolve e tem de reprovar.
    """
    COR, OPACIDADE = '#00897b', 0.5

    @classmethod
    def setUpClass(cls):
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
        from qgis.testing.mocked import get_iface
        from Calco import calco as C, gpkg
        from Calco.formulario.tipos import comuns as CM
        from Calco.ui.painel import PainelCalco
        cls.caminho = os.path.join(TMP, 'amostra_poligono.gpkg')
        gpkg.criar_calco(cls.caminho, ['polygon'])
        vl = QgsVectorLayer('{}|layername=polygon'.format(cls.caminho), 'Polígono', 'ogr')
        vl.setCustomProperty(PROP_CAMINHO, cls.caminho)
        vl.setCustomProperty(PROP_TIPO, 'polygon')
        cls.casos = [(ligada, tipo_h) for ligada in (True, False, None) for tipo_h in [v for v, _r in CM.HACHURAS] + [None]]
        vl.startEditing()
        for k, (ligada, tipo_h) in enumerate(cls.casos):
            a = dict(schema.padroes('polygon'), ebgeo_id=str(uuid.uuid4()), nome='{} {}'.format(ligada, tipo_h),
                     fill_color=cls.COR, opacity=cls.OPACIDADE, hatch_enabled=ligada, hatch_type=tipo_h)
            f = QgsFeature(vl.fields())
            for col, v in schema.atributos_para_qgis('polygon', a).items():
                if vl.fields().indexOf(col) >= 0:
                    f.setAttribute(vl.fields().indexOf(col), v)
            x, y = -43.0 + (k % 6) * 0.1, -22.9 - (k // 6) * 0.1
            anel = [QgsPointXY(x, y), QgsPointXY(x + 0.04, y), QgsPointXY(x + 0.04, y + 0.04), QgsPointXY(x, y + 0.04),
                    QgsPointXY(x, y)]
            f.setGeometry(QgsGeometry.fromMultiPolygonXY([[anel]]))
            vl.addFeature(f)
        assert vl.commitChanges(), vl.commitErrors()
        C.aplicar_estilo(vl, 'polygon')
        C.aplicar_formulario(vl, 'polygon')
        QgsProject.instance().addMapLayer(vl)
        cls.vl = vl
        cls.painel = PainelCalco(get_iface())
        cls.painel.setParent(None)
        cls.painel.resize(440, 980)
        cls.painel.show()

    @classmethod
    def tearDownClass(cls):
        cls.painel.hide()
        cls.painel.deleteLater()
        QgsProject.instance().removeMapLayer(cls.vl.id())
        _app.processEvents()

    def _no_mapa(self, f):
        """A cor no centro da feição desenhada pelo estilo da camada sobre branco, na resolução da amostra."""
        from qgis.core import (QgsExpressionContext, QgsExpressionContextUtils, QgsMapRendererParallelJob,
                               QgsMapSettings)
        from qgis.PyQt.QtCore import QSize
        from qgis.PyQt.QtGui import QColor
        from Calco.ui.blocos.previa import LARGURA_AMOSTRA
        ms = QgsMapSettings()
        ms.setLayers([self.vl])
        ms.setDestinationCrs(self.vl.crs())
        ms.setOutputSize(QSize(300, 300))
        ms.setOutputDpi(LARGURA_AMOSTRA / (40.0 / 25.4))  # a da amostra: o traço da hachura com o mesmo miolo
        ms.setBackgroundColor(QColor('white'))
        ms.setExtent(f.geometry().boundingBox())
        ctx = QgsExpressionContext()
        ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
        ms.setExpressionContext(ctx)
        job = QgsMapRendererParallelJob(ms)
        job.start()
        job.waitForFinished()
        img = job.renderedImage()
        return cor_da_tinta(img, img.width() // 2, img.height() // 2) + (img,)

    def _na_amostra(self, f):
        from qgis.PyQt.QtWidgets import QLabel
        from Calco.ui.blocos.previa import esperar
        self.painel._camada_mudou(self.vl)
        self.vl.selectByIds([f.id()])
        self.painel._selecao_mudou()
        _app.processEvents()
        w = self.painel.findChild(QLabel, 'EBGeoPreviaAmostra')
        self.assertIsNotNone(w)
        esperar(self.painel)
        img = w.pixmap().toImage()
        return cor_da_tinta(img, img.width() // 2, img.height() // 2)

    def divergencias(self, capturar=False):
        """
        [(caso, cor na amostra, cor no mapa)] que diferem mais de 3 num canal, ou em que um é liso
        e o outro hachurado (cobertura acima ou abaixo de 95 %); e as medidas.
        """
        from Calco.ui.blocos import previa
        erros, medidas = [], []
        previa._JOBS.clear()
        for f in self.vl.getFeatures():
            caso = f['nome']
            mapa, cob_mapa, img = self._no_mapa(f)
            amostra, cob_amostra = self._na_amostra(f)
            medidas.append('{}: amostra {} ({:.0%}) mapa {} ({:.0%})'.format(
                caso, '#%02x%02x%02x' % amostra, cob_amostra, '#%02x%02x%02x' % mapa, cob_mapa))
            if max(abs(a - b) for a, b in zip(amostra, mapa)) > 3 or (cob_amostra > 0.95) != (cob_mapa > 0.95):
                erros.append((caso, amostra, mapa, round(cob_amostra, 2), round(cob_mapa, 2)))
            if capturar and caso in ('True none', 'False cross', 'True cross', 'None None'):
                rot = caso.replace(' ', '_')
                self.painel.grab().save(os.path.join(SAIDA, 'dock_amostra_poligono_{}.png'.format(rot)))
                img.save(os.path.join(SAIDA, 'mapa_poligono_{}.png'.format(rot)))
        return erros, medidas

    def test_centro_da_amostra_igual_ao_mapa_em_todos_os_casos_de_hachura(self):
        erros, medidas = self.divergencias(capturar=True)
        self.assertEqual(len(medidas), len(self.casos))
        self.assertEqual(erros, [], '\n'.join(medidas))
        # o liso é o que o chefe mediu no mapa (#7fc4bd), e a hachura desenhada põe a mesma cor no traço
        self.assertTrue(any(m.startswith('False none:') and 'mapa #7fc4bd' in m for m in medidas), medidas)
        # a caixa marcada com 'none' não preenche, como o Web (estilos_formas.COND_LISO)
        self.assertTrue(any(m.startswith('True none:') and 'mapa #ffffff (0%)' in m for m in medidas), medidas)
        hachurados = [m for m in medidas if m.startswith('True ') and m.split(':')[0].split(' ')[1] in ('diagonal-right', 'cross', 'dots')]
        self.assertTrue(all('(100%)' not in m for m in hachurados), hachurados)  # a régua separa o liso da hachura
        MEDIDAS.append('amostra do polígono contra o mapa, {} casos de hachura: '.format(len(medidas)) + '; '.join(medidas))

    def test_pior_caso_fundo_branco_transparente_reprova(self):
        from qgis.PyQt.QtGui import QColor
        from Calco import convencoes
        original = convencoes.FUNDO_AMOSTRA
        convencoes.FUNDO_AMOSTRA = QColor(255, 255, 255, 0)
        try:
            erros, _m = self.divergencias()
        finally:
            convencoes.FUNDO_AMOSTRA = original
        # nenhum caso com tinta sai certo com o fundo de antes (a caixa marcada com 'none' não pinta nada)
        nomes = {'{} {}'.format(ligada, tipo_h) for ligada, tipo_h in self.casos}
        self.assertEqual(sorted(nomes - {e[0] for e in erros}), ['True none'], erros)
        MEDIDAS.append('pior caso (fundo branco transparente): {} de {} casos divergem, ex. {}'.format(
            len(erros), len(self.casos), erros[0]))


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('capturas em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
