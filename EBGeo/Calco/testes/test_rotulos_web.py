# -*- coding: utf-8 -*-
"""
Os rótulos e as dicas do formulário (nativo e dock) são os do EBGeo Web, lidos do código do Web.

  - Painéis de atributos do Web (`*_attributes_panel.js`): cada `label: '...'` cujo controle grava
    uma propriedade (`updateFeaturesProperty(..., 'prop')`, `set('prop')`, `{ key: 'prop', label }`)
    é o rótulo da coluna dessa propriedade (schema.py) no nativo e no dock, em todos os tipos.
  - Símbolo Militar: `text_modifiers_catalog.js`, por conjunto do SIDC. O rótulo é o do Web, sem a
    letra da norma ("Subordinação", não "Subordinação (B)"); a dica (tooltip) é a do conjunto no
    dock e, no nativo, a mais comum como comentário da coluna no GeoPackage, que o QGIS mostra no
    rótulo sem código e sem o plugin (medido no QGIS 4.0.0).

O pior caso é o retrato de antes (rótulos com unidade, caixa baixa e a letra da norma), que a
mesma régua reprova: ver a medida no fim.

Com EBGEO_WEB_DIR (ou EBGEO_WEB) apontando o checkout do ebgeo_web; sem ele, pula.
    python-qgis.bat EBGeo/Calco/testes/test_rotulos_web.py
"""
import os
import re
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, PLUGIN)

from qgis.core import QgsApplication, QgsVectorLayer  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import gpkg, schema  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402
from Calco.formulario.tipos import militar as M  # noqa: E402

WEB = os.environ.get('EBGEO_WEB_DIR') or os.environ.get('EBGEO_WEB') or ''
JS = os.path.join(WEB, 'frontend', 'src', 'js')
MEDIDAS = []

PAINEIS = {
    'point': 'draw_tools/point_tool/point_attributes_panel.js',
    'line': 'draw_tools/line_tool/line_attributes_panel.js',
    'polygon': 'draw_tools/polygon_tool/polygon_attributes_panel.js',
    'circle': 'draw_tools/circle_tool/circle_attributes_panel.js',
    'ellipse': 'draw_tools/ellipse_tool/ellipse_attributes_panel.js',
    'rectangle': 'draw_tools/rectangle_tool/rectangle_attributes_panel.js',
    'sector': 'draw_tools/sector_tool/sector_attributes_panel.js',
    'text': 'draw_tools/text_tool/text_attributes_panel.js',
    'image': 'draw_tools/image_tool/image_attributes_panel.js',
    'brush': 'draw_tools/brush_tool/brush_attributes_panel.js',
    'los': 'analysis_tools/los_tool/los_attributes_panel.js',
    'visibility': 'analysis_tools/visibility_tool/visibility_attributes_panel.js',
    'processed_los': 'analysis_tools/los_tool/los_attributes_panel.js',
    'processed_visibility': 'analysis_tools/visibility_tool/visibility_attributes_panel.js',
    'military_symbol': 'military_tools/military_symbol_tool/attributes/military_symbol_attributes_panel.js',
    'coordination_measure': 'military_tools/coordination_measure_tool/attributes/coordination_measure_attributes_panel.js',
    'engineering_symbol': 'military_tools/engineering_symbol_tool/engineering_attributes_panel.js',
    'magnetic_declination': 'military_tools/declination_tool/declination_attributes_panel.js',
    'coordination_line': 'military_tools/coordination_line_tool/coordination_line_attributes_panel.js',
    'coordination_area': 'military_tools/coordination_area_tool/coordination_area_attributes_panel.js',
    'boundary': 'military_tools/boundary_tool/boundary_attributes_panel.js',
    'arrow': 'military_tools/arrow_tool/arrow_attributes_panel.js',
    'occupied_front': 'military_tools/occupied_front_tool/occupied_front_attributes_panel.js',
}

RX_LABEL = re.compile(r"""\blabel:\s*(['"])((?:(?!\1).)*)\1""")
RX_PROP = re.compile(r"""(?:update\w*Propert\w*\(\s*(?:\w+\s*,\s*)?|\bset\(\s*)'(\w+)'""")
RX_CHAVE = re.compile(r"""\{\s*key:\s*'(\w+)',\s*label:\s*'([^']*)'""")


def pares_do_painel(caminho, trecho=None):
    """[(propriedade do Web, rótulo)] dos controles do painel que gravam uma propriedade."""
    with open(caminho, encoding='utf-8') as fh:
        s = fh.read()
    if trecho:
        s = s[s.index('const ' + trecho + ' ='):]
        s = s[:s.index('\n    };')]
    out = [(m.group(1), m.group(2)) for m in RX_CHAVE.finditer(s)]
    chaves = {m.start(2) for m in RX_CHAVE.finditer(s)}
    ms = list(RX_LABEL.finditer(s))
    for k, m in enumerate(ms):
        if m.start(2) in chaves or 'value:' in s[s.rfind('{', 0, m.start()):m.start()]:
            continue  # chave já lida, ou opção de uma lista ({ value, label })
        fim = ms[k + 1].start() if k + 1 < len(ms) else len(s)
        props = RX_PROP.findall(s[m.end():min(fim, m.end() + 1500)])
        # o interruptor da correção de zoom grava antes o zoom de referência: vale o que ele liga
        props = [p for p in props if p != 'createdAtZoom'] or props
        if props:
            out.append((props[0], m.group(2)))
    return out


def catalogo_textos(caminho):
    """{conjunto: [{'id', 'label', 'tooltip'}]} do text_modifiers_catalog.js do Web."""
    with open(caminho, encoding='utf-8') as fh:
        s = fh.read()
    corpo = s[s.index('TEXT_MODIFIERS_CATALOG'):]
    res = {}
    blocos = list(re.finditer(r"\n    '(\d\d)':\s*\{", corpo))
    for k, b in enumerate(blocos):
        trecho = corpo[b.end():blocos[k + 1].start() if k + 1 < len(blocos) else len(corpo)]
        campos = []
        for f in re.finditer(r"\{\s*id:\s*'(\w+)',\s*label:\s*'([^']*)',(.*?)\}", trecho, re.S):
            dica = re.search(r"tooltip:\s*'([^']*)'", f.group(3))
            campos.append({'id': f.group(1), 'label': f.group(2), 'tooltip': dica.group(1) if dica else None})
        res[b.group(1)] = campos
    return res


def divergencias_paineis(formulario=esp.formulario):
    """[(tipo, coluna, rótulo do Desktop no nativo, no dock, rótulo do Web)] que não batem; e o total visto."""
    ruins, vistos = [], 0
    for tipo, arq in PAINEIS.items():
        spec = formulario(tipo)
        col_de = {w: c for c, _t, _p, w in schema.campos(tipo) if w}
        campos = {c.coluna: c for c in spec.campos()}
        pares = [(p, r, {}) for p, r in pares_do_painel(os.path.join(JS, arq))]
        if tipo == 'coordination_area':
            # A mesma coluna tem dois rótulos no Web, conforme o símbolo e sua hachura.
            # Comparar todos contra atributos vazios cobrava ambos no mesmo estado.
            from Calco.formulario.tipos.area import HachuraDoTerreno
            condicionais = pares_do_painel(os.path.join(JS, arq), 'buildForcedHatch')
            pares = [(p, r, a) for p, r, a in pares if (p, r) not in condicionais]
            pares += [(p, r, {'symbol_code': codigo, 'hatch_type': hachura})
                      for codigo, hachura in HachuraDoTerreno.pares() for p, r in condicionais]
        for prop, rotulo, attrs in pares:
            c = campos.get(col_de.get(prop))
            if c is None:
                continue
            vistos += 1
            nativo, dock = c.rotulo_para(attrs), c.rotulo_para(attrs, rico=bool(c.rico))
            if nativo != rotulo or dock != rotulo:
                ruins.append((tipo, c.coluna, nativo, dock, rotulo))
    return ruins, vistos


def divergencias_militar(formulario=esp.formulario):
    cat = catalogo_textos(os.path.join(JS, 'military_tools', 'military_symbol_tool', 'text_modifiers_catalog.js'))
    col = {w: c for c, w in schema.AMPLIFICADORES}
    campos = {c.coluna: c for c in formulario('military_symbol').campos()}
    padrao = dict((c[0], c[2]) for c in schema.TIPOS['military_symbol']['campos'])['sidc']
    ruins, vistos = [], 0
    for conj, fields in cat.items():
        attrs = {'sidc': padrao[:4] + conj + padrao[6:]}
        for f in fields:
            c = campos[col[f['id']]]
            vistos += 1
            r = c.rotulo_para(attrs)
            d = c.dica_para(attrs)
            if r != f['label'] or (f['tooltip'] and d != f['tooltip']):
                ruins.append((conj, f['id'], r, d, f['label'], f['tooltip']))
    return ruins, vistos, cat


@unittest.skipUnless(WEB and os.path.isdir(JS), 'sem EBGEO_WEB_DIR (checkout do ebgeo_web)')
class TestRotulosDoWeb(unittest.TestCase):

    def test_rotulo_da_hachura_no_nativo_e_no_dock(self):
        from qgis.core import QgsExpression, QgsExpressionContext, QgsFeature
        camada = QgsVectorLayer('Point?field=symbol_code:string&field=hatch_type:string', 'area', 'memory')
        spec = esp.formulario('coordination_area')
        for codigo, hachura, forcada in (('151100', 'diagonal-right', True),
                                         ('151199-01', 'cross-diagonal', True),
                                         ('151100', 'cross', False), ('150000', 'diagonal-right', False),
                                         (None, None, False)):
            attrs = dict(symbol_code=codigo, hatch_type=hachura)
            f = QgsFeature(camada.fields())
            f.setAttributes([codigo, hachura])
            ctx = QgsExpressionContext()
            ctx.setFeature(f)
            for coluna, livre, terreno in (('fill_color', 'Preenchimento', 'Cor da hachura'),
                                           ('opacity', 'Opacidade do Preenchimento', 'Opacidade da hachura')):
                campo = spec.campo(coluna)
                esperado = terreno if forcada else livre
                self.assertEqual(campo.rotulo_para(attrs), esperado)
                self.assertEqual(QgsExpression(campo.expressao_rotulo()).evaluate(ctx), esperado)

    def test_paineis_de_todos_os_tipos(self):
        ruins, vistos = divergencias_paineis()
        MEDIDAS.append('painéis do Web: {} rótulos conferidos, {} divergentes'.format(vistos, len(ruins)))
        self.assertGreater(vistos, 80)
        self.assertEqual(ruins, [])

    def test_amplificadores_do_militar_por_conjunto(self):
        ruins, vistos, _cat = divergencias_militar()
        MEDIDAS.append('amplificadores do militar: {} (conjunto, campo) conferidos, {} divergentes'.format(vistos, len(ruins)))
        self.assertGreater(vistos, 50)
        self.assertEqual(ruins, [])

    def test_dica_no_nativo_sem_plugin(self):
        """A dica mais comum vira o comentário da coluna, e o QGIS a mostra no rótulo do formulário."""
        _ruins, _vistos, cat = divergencias_militar()
        cam = os.path.join(tempfile.mkdtemp(prefix='ebgeo_rotulos_'), 'calco.gpkg')
        gpkg.criar_calco(cam, ['military_symbol'])
        lyr = QgsVectorLayer(cam + '|layername=military_symbol', 'm', 'ogr')
        col = {w: c for c, w in schema.AMPLIFICADORES}
        dicas = M.dicas_amplificadores()
        for web, (_por, comum) in dicas.items():
            self.assertEqual(lyr.fields().field(col[web]).comment(), comum, web)
        self.assertEqual(lyr.fields().field('higher_formation').comment(), 'Designação do escalão enquadrante')
        # o calco antigo, sem a dica, a ganha ao ser completado (criar_calco de novo)
        from osgeo import ogr
        ds = ogr.Open(cam, 1)
        t = ds.GetLayerByName('military_symbol')
        i = t.GetLayerDefn().GetFieldIndex('higher_formation')
        fd = ogr.FieldDefn('higher_formation', ogr.OFTString)
        fd.SetComment('')
        t.AlterFieldDefn(i, fd, ogr.ALTER_COMMENT_FLAG)
        ds = None
        gpkg.criar_calco(cam, ['military_symbol'])
        lyr = QgsVectorLayer(cam + '|layername=military_symbol', 'm', 'ogr')
        self.assertEqual(lyr.fields().field('higher_formation').comment(), 'Designação do escalão enquadrante')


@unittest.skipUnless(WEB and os.path.isdir(JS), 'sem EBGEO_WEB_DIR (checkout do ebgeo_web)')
class TestZMedidas(unittest.TestCase):
    def test_medidas(self):
        print('\nMEDIDAS:\n  ' + '\n  '.join(MEDIDAS))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
