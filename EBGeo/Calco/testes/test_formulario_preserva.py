# -*- coding: utf-8 -*-
"""
Salvar pelo formulário nativo preserva a feição, em TODO tipo que tem especificação
(esp.TIPOS_COM_FORMULARIO). Num processo NOVO e SEM o plugin, para cada feição: salvar sem mudar
não grava nada, e salvar só o nome grava só o nome. Relido o GeoPackage cru, nenhuma outra coluna
mudou (fora `atualizado_em`, que se renova, e a caixa da cor, que o GeoPackage guarda em
minúsculas), e o desenho da camada sai igual pixel a pixel.

Duas feições por tipo:
  web    valores que o Web, o importador e o plugin gravam e que um widget de faixa cortaria ou
         arredondaria: o zoom da criação cru (23,4 e 12,345678901234567), a opacidade
         0,30000000000000004 (fixture 06), espessura 2,5, texto de 100 px, tamanhos com 10 casas;
  nulos  toda coluna numérica e lógica nula (o calco antigo e o importado sem a chave), que o
         desenho lê como o padrão (`visivel` nulo é mostrar, `zoom_corr` nulo é corrigir).

No HEAD 86f7d3b a régua reprova a Linha de Coordenação (`visivel` nulo vira False, `created_zoom`
23,4 vira 22, `line_width` 2,5 vira 3). O pior caso é o estilo real degradado: a caixa sem o estado
nulo e o número como Range, que ela tem de reprovar.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_formulario_preserva.py
Variáveis: EBGEO_TESTE_SAIDA (imagens antes e depois; padrão: temporária).
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
import uuid

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, PLUGIN)
sys.path.insert(0, AQUI)

from qgis.core import (  # noqa: E402
    QgsApplication, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsExpressionContext,
    QgsExpressionContextUtils, QgsGeometry, QgsMapRendererParallelJob, QgsMapSettings, QgsPointXY, QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import calco as C, gpkg, schema  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402
import test_formulario_sem_plugin as tfs  # noqa: E402

TMP = tempfile.mkdtemp(prefix='ebgeo_preserva_')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or TMP
os.makedirs(SAIDA, exist_ok=True)
MEDIDAS = []
TIPOS = sorted(esp.TIPOS_COM_FORMULARIO)

# O que um widget de faixa ou de casas fixas cortaria (aplicado só onde a coluna existe).
VALORES_WEB = {
    'created_zoom': 23.4, 'label_created_zoom': 12.345678901234567, 'opacity': 0.30000000000000004,
    'fill_opacity': 0.30000000000000004, 'line_opacity': 0.7000000000000001, 'line_width': 2.5,
    'text_size': 100.0, 'size': 1.2345678901, 'symbol_size_km': 0.6103515625, 'symbol_spacing_km': 1.4400000000000002,
    'rotation': 12.345678901234567, 'width_m': 1234.5678, 'head_length_ratio': 1.8765432,
    'text_distance_ratio': 1.2345678901, 'airmobile_position': 0.43219876, 'hatch_line_width': 1.25,
    'hatch_spacing': 8.5, 'label_size': 13.5, 'text_ratio': 0.123456789,
}
# Colunas que só o plugin escreve (desenho do símbolo): ficam como a gravação as deixou.
TECNICAS = {'svg', 'svg_assinatura', 'largura_px', 'altura_px', 'ancora_dx', 'ancora_dy', 'bitmap_b64', 'bitmap_mime'}


def _geometria(tipo, k):
    g = schema.TIPOS[tipo]['geometria']
    x0, y0 = -47.0 + 0.03 * k, -15.0
    if g == 'Point':
        return QgsGeometry.fromPointXY(QgsPointXY(x0, y0))
    if 'Line' in g:
        return QgsGeometry.fromPolylineXY([QgsPointXY(x0, y0), QgsPointXY(x0 + 0.02, y0 + 0.004), QgsPointXY(x0 + 0.025, y0 + 0.015)])
    return QgsGeometry.fromPolygonXY([[QgsPointXY(x0, y0), QgsPointXY(x0 + 0.02, y0), QgsPointXY(x0 + 0.02, y0 + 0.015),
                                       QgsPointXY(x0, y0 + 0.015), QgsPointXY(x0, y0)]])


def atributos(tipo, chave):
    a = dict(schema.padroes(tipo))
    a.update(ebgeo_id=str(uuid.uuid4()), nome=chave, criado_em='2026-10-05T09:00:00+00:00',
             atualizado_em='2026-10-05T09:00:00+00:00')
    for col, tp, _p, _w in schema.campos(tipo):
        if col in TECNICAS:
            continue
        if chave == 'web' and col in VALORES_WEB:
            a[col] = VALORES_WEB[col]
        elif chave == 'nulos' and tp in ('real', 'int', 'bool'):
            a[col] = None
    return a


def criar_calco(caminho, tipos):
    from Calco.ferramentas import gravar_feicao
    gpkg.criar_calco(caminho, tipos)
    for tipo in tipos:
        lyr = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), schema.TIPOS[tipo]['nome_pt'], 'ogr')
        assert lyr.isValid(), tipo
        for k, chave in enumerate(('web', 'nulos')):
            assert gravar_feicao(lyr, tipo, _geometria(tipo, k), atributos(tipo, chave)), (tipo, chave)
        C.aplicar_estilo(lyr, tipo)
        C.salvar_estilo_padrao(lyr)


def linhas_cruas(caminho, tipo):
    con = sqlite3.connect(caminho)
    try:
        cur = con.execute('SELECT * FROM "{}"'.format(schema.TIPOS[tipo]['tabela']))
        nomes = [d[0] for d in cur.description]
        return {str(r[nomes.index('ebgeo_id')]): dict(zip(nomes, r)) for r in cur.fetchall()}
    finally:
        con.close()


def mudancas_cruas(antes, depois):
    out = {}
    for eid, a in antes.items():
        d = depois.get(eid, {})
        for col, va in a.items():
            if col in ('nome', 'atualizado_em'):
                continue
            vd = d.get(col)
            if isinstance(va, str) and isinstance(vd, str) and va.startswith('#') and va.lower() == vd.lower():
                continue
            if va != vd:
                out.setdefault(a.get('nome'), {})[col] = (va, vd)
    return out


def renderizar(caminho, tipo, arquivo=None):
    vl = QgsVectorLayer(gpkg.uri_camada(caminho, tipo), 'r', 'ogr')
    ms = QgsMapSettings()
    ms.setLayers([vl])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3857'))
    ms.setOutputSize(QSize(700, 360))
    ms.setOutputDpi(96)
    ms.setBackgroundColor(QColor('white'))
    ext = QgsCoordinateTransform(vl.crs(), ms.destinationCrs(), QgsProject.instance()).transformBoundingBox(vl.extent())
    ms.setExtent(ext.buffered(max(ext.width(), ext.height(), 2000) * 0.3))
    ctx = QgsExpressionContext()
    ctx.appendScope(QgsExpressionContextUtils.globalScope())
    ctx.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
    ctx.appendScope(QgsExpressionContextUtils.mapSettingsScope(ms))
    ms.setExpressionContext(ctx)
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    img = job.renderedImage()
    if arquivo:
        img.save(os.path.join(SAIDA, arquivo))
    return img


def pixels_diferentes(a, b):
    return sum(1 for y in range(a.height()) for x in range(a.width()) if a.pixel(x, y) != b.pixel(x, y))


# Processo novo, sem o plugin. argv: gpkg, json de saída, '' (sem capturas), tipos...
SCRIPT = r'''
import sys, os, json
gp, saida = sys.argv[1:3]
tipos = sys.argv[4:]
res = {'etapa': 'inicio', 'tipos': {}}
def gravar():
    with open(saida, 'w', encoding='utf-8') as fh:
        json.dump(res, fh, ensure_ascii=False)
from qgis.core import QgsApplication, QgsVectorLayer
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsGui, QgsAttributeForm, QgsEditorWidgetWrapper, QgsAttributeEditorContext
QgsGui.editorWidgetRegistry().initEditors()
res['modulos_ebgeo'] = []
for tabela in tipos:
    L = QgsVectorLayer(gp + '|layername=' + tabela, tabela, 'ogr')
    r = res['tipos'][tabela] = {'layout': L.editFormConfig().layout().name, 'feicoes': {}}
    L.startEditing()
    for f in L.getFeatures():
        chave = f['nome']
        res['etapa'] = '{} {}'.format(tabela, chave)
        gravar()
        form = QgsAttributeForm(L, f)
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        form.show(); app.processEvents()
        salvo = form.save()
        sem_mudar = sorted(L.fields().at(i).name() for i, v in L.editBuffer().changedAttributeValues().get(f.id(), {}).items()
                           if type(v).__name__ != 'QgsUnsetAttributeValue')
        form.close(); form.deleteLater(); app.processEvents()
        form = QgsAttributeForm(L, L.getFeature(f.id()))
        form.setMode(QgsAttributeEditorContext.Mode.SingleEditMode)
        achou = False
        for wr in form.findChildren(QgsEditorWidgetWrapper):
            if L.fields().at(wr.fieldIdx()).name() == 'nome':
                wr.setValues(chave + ' editada', []); wr.emitValueChanged(); achou = True
        form.save()
        mud = L.editBuffer().changedAttributeValues().get(f.id(), {})
        r['feicoes'][chave] = {'salvo': salvo, 'sem_mudar': sem_mudar, 'nome_no_formulario': achou,
                               'com_nome': {L.fields().at(i).name(): repr(v) for i, v in mud.items()
                                            if type(v).__name__ != 'QgsUnsetAttributeValue'}}
        form.close(); form.deleteLater(); app.processEvents()
    r['commit'] = L.commitChanges()
res['modulos_ebgeo'] = sorted(m for m in sys.modules if m.split('.')[0] in ('Calco', 'EBGeo'))
res['etapa'] = 'fim'
gravar()
'''


def rodar(caminho, tipos, timeout=300):
    """O SCRIPT sobre uma CÓPIA do calco (ele grava). Devolve (resultado, código, cópia)."""
    copia = os.path.join(TMP, 'rodada_{}.gpkg'.format(uuid.uuid4().hex[:8]))
    shutil.copy(caminho, copia)
    original = tfs.SCRIPT
    tfs.SCRIPT = SCRIPT
    try:
        res, codigo = tfs.rodar_sem_plugin(copia, [schema.TIPOS[t]['tabela'] for t in tipos], '', timeout=timeout)
    finally:
        tfs.SCRIPT = original
    return res, codigo, copia


def reprovacoes(res, codigo, caminho_antes, caminho_depois, tipos, imagens=False):
    """Tudo o que reprova; lista vazia é aprovação."""
    erros = []
    if codigo != 0 or res.get('etapa') != 'fim':
        erros.append('processo saiu com {} na etapa {}'.format(codigo, res.get('etapa')))
    if res.get('modulos_ebgeo'):
        erros.append('o plugin estava carregado')
    for tipo in tipos:
        r = (res.get('tipos') or {}).get(schema.TIPOS[tipo]['tabela'])
        if not r:
            erros.append('{}: não rodou'.format(tipo))
            continue
        if not r.get('commit'):
            erros.append('{}: não gravou'.format(tipo))
        for chave, fo in r['feicoes'].items():
            if not fo['salvo'] or fo['sem_mudar']:
                erros.append('{} {}: salvar sem mudar gravou {}'.format(tipo, chave, fo['sem_mudar']))
            if not fo['nome_no_formulario']:
                erros.append('{} {}: o nome não está no formulário'.format(tipo, chave))
        mud = mudancas_cruas(linhas_cruas(caminho_antes, tipo), linhas_cruas(caminho_depois, tipo))
        for chave, cols in sorted(mud.items()):
            erros.append('{} {}: salvar o nome mudou {}'.format(tipo, chave, cols))
        nomes = sorted(str(r_['nome']) for r_ in linhas_cruas(caminho_depois, tipo).values())
        if nomes != ['nulos editada', 'web editada']:
            erros.append('{}: nomes no disco {}'.format(tipo, nomes))
        a = renderizar(caminho_antes, tipo, '{}_antes.png'.format(tipo) if imagens else None)
        b = renderizar(caminho_depois, tipo, '{}_depois.png'.format(tipo) if imagens else None)
        dif = pixels_diferentes(a, b)
        if dif:
            erros.append('{}: o desenho mudou em {} pixels'.format(tipo, dif))
    return erros


class TesteSalvarPreserva(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caminho = os.path.join(TMP, 'calco_preserva.gpkg')
        criar_calco(cls.caminho, TIPOS)
        cls.res, cls.codigo, cls.depois = rodar(cls.caminho, TIPOS)

    def test_feicoes_de_teste(self):
        self.assertIn('coordination_line', TIPOS)
        for tipo in TIPOS:
            linhas = {str(r['nome']): r for r in linhas_cruas(self.caminho, tipo).values()}
            self.assertEqual(sorted(linhas), ['nulos', 'web'], tipo)
            self.assertIsNone(linhas['nulos']['visivel'], tipo)
            if 'created_zoom' in linhas['web']:
                self.assertEqual(linhas['web']['created_zoom'], 23.4, tipo)
                self.assertIsNone(linhas['nulos']['created_zoom'], tipo)

    def test_salvar_sem_mudar_e_so_o_nome_preservam(self):
        erros = reprovacoes(self.res, self.codigo, self.caminho, self.depois, TIPOS, imagens=True)
        MEDIDAS.append('{} tipos com especificação ({}), 2 feições cada: {} reprovações; imagens <tipo>_antes/depois.png'.format(
            len(TIPOS), ', '.join(TIPOS), len(erros)))
        self.assertEqual(erros, [], '\n'.join(erros))

    def test_pior_caso_caixa_sem_nulo_e_numero_range_reprova(self):
        """O estilo real da Linha com `visivel` sem o estado nulo e `created_zoom` e `line_width` como Range."""
        from qgis.core import QgsEditorWidgetSetup
        destino = os.path.join(TMP, 'pior_preserva.gpkg')
        shutil.copy(self.caminho, destino)
        vl = QgsVectorLayer(gpkg.uri_camada(destino, 'coordination_line'), 'Linha de Coordenação', 'ogr')
        i = vl.fields().indexOf
        cfg = dict(vl.editorWidgetSetup(i('visivel')).config())
        cfg.pop('AllowNullState', None)
        vl.setEditorWidgetSetup(i('visivel'), QgsEditorWidgetSetup('CheckBox', cfg))
        for col, mn, mx, casas in (('created_zoom', 0, 22, 1), ('line_width', 1, 10, 0)):
            vl.setEditorWidgetSetup(i(col), QgsEditorWidgetSetup('Range', {
                'Style': 'SpinBox', 'Min': mn, 'Max': mx, 'Step': 1, 'Precision': casas, 'Suffix': '', 'AllowNull': False}))
        vl.saveStyleToDatabaseV2(vl.name(), 'pior caso', True, '')
        res, codigo, depois = rodar(destino, ['coordination_line'])
        erros = reprovacoes(res, codigo, destino, depois, ['coordination_line'])
        MEDIDAS.append('pior caso (Linha, caixa sem nulo e Range): ' + ' | '.join(erros))
        texto = ' '.join(erros)
        self.assertIn("'visivel': (None, 0)", texto)
        self.assertIn("'created_zoom': (23.4, 22.0)", texto)
        self.assertIn("'line_width': (2.5, 3.0)", texto)


def tearDownModule():
    print('\n--- medidas ---')
    for m in MEDIDAS:
        print(m)
    print('imagens em', SAIDA)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
