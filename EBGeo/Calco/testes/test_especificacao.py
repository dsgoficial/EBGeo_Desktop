# -*- coding: utf-8 -*-
"""
Especificação do formulário (formulario/especificacao.py), piloto da Linha de Coordenação:
  - as condições geradas do CATALOGO_LINHA mostram, para cada um dos 14 símbolos (e para o
    código desconhecido e o nulo, que desenham como a 290199), exatamente os campos que o dock
    mostrava antes do piloto (RETRATO_DOCK, medido no dock de 0ea790b em 2026-10-05);
  - a expressão QGIS de cada condição dá o mesmo que a regra em Python, avaliada pelo QGIS;
  - toda coluna do esquema está no formulário ou entre os ocultos, e só há widgets nativos.
Cada régua é provada contra a especificação real degradada, que ela tem de reprovar.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_especificacao.py
"""
import copy
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication, QgsExpression, QgsExpressionContext, QgsFeature, QgsField, QgsFields  # noqa: E402
from qgis.PyQt.QtCore import QMetaType  # noqa: E402

_app = QgsApplication.instance() or QgsApplication([], True)
_app.initQgis()

from Calco import schema, estilos_taticos as et  # noqa: E402
from Calco.formulario import especificacao as esp  # noqa: E402

# Os campos que só aparecem conforme o símbolo, e o que o dock de 0ea790b mostrava de cada um
# (o painel montado para uma feição de cada código, lidos os widgets visíveis). Os demais
# campos do dock (nome, descrição, símbolo, cor, espessura, opacidade e zoom) apareciam sempre.
CONDICIONAIS = ('symbol_size_km', 'symbol_spacing_km', 'tipo', 'identificacao', 'gdh_ini', 'gdh_fim',
                'numero_concentracao', 'text_size', 'text_north_facing', 'enemy_color')
SEMPRE = ('nome', 'descricao', 'symbol_code', 'color', 'line_width', 'opacity', 'zoom_corr', 'created_zoom')
_GLIFO = {'symbol_size_km', 'symbol_spacing_km'}
RETRATO_DOCK = {
    '290100': _GLIFO, '290199': _GLIFO, '290202': {'symbol_size_km'}, '290302': _GLIFO, '290303': _GLIFO,
    '290307': _GLIFO, '290308': _GLIFO, '290309': _GLIFO, '290500': _GLIFO,
    '290999-01': {'symbol_size_km'}, '290999-02': {'symbol_size_km'},
    '140000': {'tipo', 'identificacao', 'gdh_ini', 'gdh_fim', 'text_size', 'text_north_facing'},
    '140200': {'symbol_size_km', 'enemy_color'},
    '240701': {'symbol_size_km', 'numero_concentracao', 'text_size', 'text_north_facing'},
    '999999': _GLIFO, None: _GLIFO,
}
# Rótulo da cor e aviso do lado inimigo, no mesmo retrato: só a 140200 os muda.
ROTULO_COR = {c: ('Cor do lado amigo' if c == '140200' else 'Cor') for c in RETRATO_DOCK}
AVISO = {c: c == '140200' for c in RETRATO_DOCK}


def divergencias(spec):
    """[(código, esperado, obtido)] onde a especificação discorda do retrato do dock."""
    erros = []
    for codigo, condicionais in RETRATO_DOCK.items():
        attrs = {'symbol_code': codigo}
        vistos = {c for c in CONDICIONAIS + SEMPRE if spec.visivel(c, attrs)}
        esperado = set(condicionais) | set(SEMPRE)
        if vistos != esperado:
            erros.append((codigo, sorted(esperado), sorted(vistos)))
        rotulo = spec.campo('color').rotulo_para(attrs)
        if rotulo != ROTULO_COR[codigo]:
            erros.append((codigo, ROTULO_COR[codigo], rotulo))
        aviso = [all(c.avaliar(attrs) for c in conds) for el, conds in spec.percorrer()
                 if isinstance(el, esp.Texto) and el.nome == 'aviso_lado_inimigo']
        if aviso != [AVISO[codigo]]:
            erros.append((codigo, 'aviso', aviso))
    return erros


def condicoes(spec):
    """Todas as condições da especificação (de campo, grupo, aba e rótulo), sem repetir."""
    vistas = []

    def junta(c):
        if c is not None and c not in vistas:
            vistas.append(c)
    for el, conds in spec.percorrer():
        for c in conds:
            junta(c)
        if isinstance(el, esp.Campo) and el.rotulo_se:
            junta(el.rotulo_se[0])
    return vistas


def feicao(codigo, bloqueado=None):
    campos = QgsFields()
    campos.append(QgsField('symbol_code', QMetaType.Type.QString))
    campos.append(QgsField('bloqueado', QMetaType.Type.Bool))
    f = QgsFeature(campos)
    f.setAttribute(0, codigo)
    f.setAttribute(1, bloqueado)
    return f


def avaliar_no_qgis(expressao, f):
    ctx = QgsExpressionContext()
    ctx.setFeature(f)
    e = QgsExpression(expressao)
    v = e.evaluate(ctx)
    assert not e.hasEvalError(), (expressao, e.evalErrorString())
    return v


class TesteEspecificacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = esp.formulario('coordination_line')

    def test_retrato_cobre_o_catalogo(self):
        self.assertEqual(set(RETRATO_DOCK) - {'999999', None}, set(et.CATALOGO_LINHA))
        self.assertEqual(len(et.CATALOGO_LINHA), 14)

    def test_condicoes_mostram_o_que_o_dock_mostrava(self):
        self.assertEqual(divergencias(self.spec), [])

    def test_regua_reprova_especificacao_degradada(self):
        # pior caso 1: a condição real da cor inimiga perde a 140200
        ruim = copy.deepcopy(self.spec)
        c = ruim.campo('enemy_color')
        c.condicao = esp.Condicao(c.condicao.coluna, c.condicao.valores - {'140200'}, c.condicao.negar)
        self.assertTrue(any(e[0] == '140200' for e in divergencias(ruim)))
        # pior caso 2: a do espaçamento com o lado trocado (o desconhecido cai do lado errado)
        ruim = copy.deepcopy(self.spec)
        c = ruim.campo('symbol_spacing_km')
        c.condicao = esp.Condicao(c.condicao.coluna, c.condicao.valores, not c.condicao.negar)
        self.assertGreaterEqual(len(divergencias(ruim)), 14)
        # pior caso 3: a aba Textos sem condição mostra os textos na 290199
        ruim = copy.deepcopy(self.spec)
        [a for a in ruim.abas if a.nome == 'Textos'][0].condicao = None
        self.assertTrue(any(e[0] == '290199' for e in divergencias(ruim)))

    def test_expressao_qgis_igual_a_regra_python(self):
        conds = condicoes(self.spec)
        self.assertGreaterEqual(len(conds), 7)
        for cond in conds:
            for codigo in list(RETRATO_DOCK) + ['']:
                for bloq in (None, False, True):
                    f = feicao(codigo, bloq)
                    py = cond.avaliar({'symbol_code': codigo, 'bloqueado': bloq})
                    qg = bool(avaliar_no_qgis(cond.expressao(), f))
                    self.assertEqual(py, qg, (cond.expressao(), codigo, bloq))
            if cond.expressao() not in ('TRUE', 'FALSE'):
                self.assertNotEqual(QgsExpression(cond.expressao()).hasParserError(), True)
        # o rótulo por dados dá o mesmo texto que o rótulo em Python
        campo = self.spec.campo('color')
        for codigo in RETRATO_DOCK:
            self.assertEqual(avaliar_no_qgis(campo.expressao_rotulo(), feicao(codigo)),
                             campo.rotulo_para({'symbol_code': codigo}))

    def test_regua_qgis_reprova_expressao_degradada(self):
        cond = self.spec.campo('enemy_color').condicao
        ruim = cond.expressao().replace("'140200'", "'140201'")
        self.assertNotEqual(bool(avaliar_no_qgis(ruim, feicao('140200'))), cond.avaliar({'symbol_code': '140200'}))

    def test_toda_coluna_no_formulario_ou_oculta(self):
        colunas = [c.coluna for c in self.spec.campos()]
        self.assertEqual(len(colunas), len(set(colunas)), 'coluna repetida no formulário')
        esquema = set(schema.nomes_campos('coordination_line'))
        ocultos = set(self.spec.ocultos)
        self.assertFalse(set(colunas) & ocultos)
        self.assertEqual(esquema - set(colunas) - ocultos, set())
        self.assertEqual(set(colunas) - esquema, set())
        self.assertIn('fid', ocultos)

    def test_so_widgets_nativos(self):
        for c in self.spec.campos():
            self.assertIn(c.widget.tipo, esp.WIDGETS_NATIVOS, c.coluna)
        for c in [c for c in self.spec.campos() if c.rico]:
            self.assertIn(c.rico, ('simbolo_linha', 'km_em_m'))

    def test_lista_de_simbolos_com_os_14(self):
        mapa = self.spec.campo('symbol_code').widget.config['map']
        self.assertEqual([list(d.values())[0] for d in mapa], list(et.CATALOGO_LINHA))
        self.assertIn('Manobra: Linha de Contato (140200)', [list(d)[0] for d in mapa])

    def test_tipos_sem_especificacao_ficam_de_fora(self):
        # na escala cada frente registra o seu tipo; o tipo sem construtor segue sem especificação
        self.assertIn('coordination_line', esp.TIPOS_COM_FORMULARIO)
        self.assertNotIn('tipo_sem_formulario', esp.TIPOS_COM_FORMULARIO)
        self.assertIsNone(esp.formulario('tipo_sem_formulario'))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
