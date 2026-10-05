# -*- coding: utf-8 -*-
"""
Testes do motor de símbolos pontuais (EBGeo/Calco/motor).

Rodar com o Python do QGIS 4 (PowerShell):
    & 'C:\\Program Files\\QGIS 4.0.0\\bin\\python-qgis.bat' -m unittest -v EBGeo/Calco/testes/test_motor.py
ou direto:
    & '...\\python-qgis.bat' EBGeo/Calco/testes/test_motor.py

A PROVA DE PARIDADE precisa de node e de um checkout do EBGeo Web com node_modules instalados
(rolldown e @playwright/test com o Chromium baixado): defina EBGEO_WEB com a raiz do ebgeo_web.
Sem ela, os testes de paridade são pulados e os demais rodam. As imagens de conferência vão
para EBGEO_TESTE_SAIDA (ou uma pasta temporária, impressa no fim).
"""
import base64
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(os.path.dirname(AQUI))  # .../EBGeo
if PACOTE not in sys.path:
    sys.path.insert(0, PACOTE)

from qgis.core import QgsApplication  # noqa: E402
from qgis.PyQt.QtCore import QByteArray, QRectF, QSize, Qt  # noqa: E402
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from qgis.PyQt.QtSvg import QSvgRenderer  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], False)
    _APP.initQgis()

from Calco.motor import declinacao  # noqa: E402
from Calco.motor.motor import ErroMotor, Motor  # noqa: E402

MOTOR_BUILD = os.path.join(os.path.dirname(AQUI), 'motor', 'build')
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo-motor-')
os.makedirs(SAIDA, exist_ok=True)


# ---------------------------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------------------------

def extensao(entidade=0, comando=False, especial=0, m1=0, m2=0):
    """BrazilianSIDCExtension.encode, reescrito aqui para o teste não depender do bundle."""
    valor = (entidade << 14) | (int(bool(comando)) << 13) | (especial << 10) | (m1 << 5) | m2
    return '076' + str(valor).zfill(7)


def sidc(conjunto='10', identidade='3', icone='121100', escalao='16', status='0', qg='0',
         m1='00', m2='00', ext='0760000000'):
    return '10' + '0' + identidade + conjunto + status + qg + escalao + icone + m1 + m2 + ext


def casos_simbolo():
    cat = Motor.instancia().catalogos()['militar']['porConjunto']
    casos = []

    def add(nome, **props):
        casos.append((nome, props))

    # Dois ícones de cada um dos 11 conjuntos, com o escalão/mobilidade quando o conjunto tem.
    for conjunto, dados in sorted(cat.items()):
        icones = [i['codigo'] for i in dados['icones'] if i['codigo'] != '000000' and not i['codigo'].endswith('99')]
        for icone in icones[:2]:
            esc = '16' if conjunto == '10' else ('33' if conjunto == '15' else '00')
            add('conjunto {} ícone {}'.format(conjunto, icone), sidc=sidc(conjunto, icone=icone, escalao=esc))
    # Identidades, status, QG/FT.
    for ident in '0123456':
        add('identidade ' + ident, sidc=sidc(identidade=ident))
    add('planejado', sidc=sidc(status='1'))
    add('posto de comando', sidc=sidc(qg='2'))
    add('força-tarefa', sidc=sidc(qg='4'))
    add('PC de força-tarefa hostil', sidc=sidc(identidade='6', qg='6', escalao='18'))
    # Extensões brasileiras de ícone.
    for e in (0, 1):
        add('121899 ext {}'.format(e), sidc=sidc(icone='121899', ext=extensao(entidade=e)))
    for e in (0, 1, 5, 10):
        add('163499 ext {}'.format(e), sidc=sidc(icone='163499', ext=extensao(entidade=e)))
    for e in (0, 2):
        add('141299 ext {}'.format(e), sidc=sidc(icone='141299', ext=extensao(entidade=e)))
    for e in (0, 3, 11):
        add('20/111299 ext {}'.format(e), sidc=sidc('20', icone='111299', escalao='00', ext=extensao(entidade=e)))
    add('20/111299 ext 4 hostil', sidc=sidc('20', identidade='6', icone='111299', escalao='00', ext=extensao(entidade=4)))
    add('20/111999 ext 8', sidc=sidc('20', icone='111999', escalao='00', ext=extensao(entidade=8)))
    add('30/130199 ext 2', sidc=sidc('30', icone='130199', escalao='00', ext=extensao(entidade=2)))
    add('40/139900 ext 1', sidc=sidc('40', icone='139900', escalao='00', ext=extensao(entidade=1)))
    add('121899 em SIDC de 20 dígitos', sidc=sidc(icone='121899')[:20])
    # Extensões de modificador 1 e 2 (código 99).
    for e in (1, 7, 16):
        add('mod1 99 ext {}'.format(e), sidc=sidc(m1='99', ext=extensao(m1=e)))
    for e in (1, 12):
        add('mod2 99 ext {}'.format(e), sidc=sidc(m2='99', ext=extensao(m2=e)))
    add('20 mod2 99 ext 3', sidc=sidc('20', icone='110000', escalao='00', m2='99', ext=extensao(m2=3)))
    # Rótulos e adaptações gráficas do catálogo brasileiro.
    for icone in ('121700', '121800', '110200', '162800'):
        add('rótulo ' + icone, sidc=sidc(icone=icone))
    add('escudo 200700', sidc=sidc(icone='200700'))
    add('rádio 111001 hostil', sidc=sidc(identidade='6', icone='111001'))
    # Modificador especial e comando.
    for sm in (1, 2, 3, 4):
        add('modificador especial {}'.format(sm), sidc=sidc(ext=extensao(especial=sm)), specialModifier=str(sm))
    add('modificador especial 1 hostil', sidc=sidc(identidade='6', ext=extensao(especial=1)))
    add('equipamento blindado', sidc=sidc('15', icone='120100', escalao='33', ext=extensao(especial=1)))
    add('comando amigo', sidc=sidc(ext=extensao(comando=True)), isCommand=True)
    add('comando hostil', sidc=sidc(identidade='6', ext=extensao(comando=True)), isCommand=True)
    add('comando + especial + 163499', sidc=sidc(icone='163499', ext=extensao(entidade=3, comando=True, especial=2)))
    # Amplificadores de texto.
    add('designação e escalão superior', sidc=sidc(), uniqueDesignation='1', higherFormation='3 BIB')
    add('todos os textos', sidc=sidc(), uniqueDesignation='A', higherFormation='2 Bda', quantity='3',
        reinforcedReduced='(+)', additionalInformation='Info', credibility='A1', type='Tipo',
        iffSif='4523', dateTimeGroup='121400Z JUN', altitudeDepth='850 m', location='Local',
        speed='20 km/h', specialHeadquarters='QG', direction='45', equipmentTeardownTime='10 min')
    add('quantidade zero', sidc=sidc(), quantity=0)
    add('texto com escape <&>', sidc=sidc(), uniqueDesignation='A&B <C>')
    add('texto + extensão brasileira', sidc=sidc(icone='163499', ext=extensao(entidade=2)), uniqueDesignation='1',
        higherFormation='Gpt Log')
    # Barra de engajamento e cor.
    add('barra de engajamento', sidc=sidc('01', icone='110000', escalao='00'), engagementBar='ENG:M:1')
    add('barra de engajamento com cor', sidc=sidc('01', icone='110000', escalao='00'), engagementBar='ENG:M:1',
        fillColor='#11FF00')
    add('cor de preenchimento', sidc=sidc(), fillColor='#FF8800')
    add('cor curta inválida', sidc=sidc(), fillColor='#fff')
    add('cor com extensão', sidc=sidc(icone='121899', ext=extensao(entidade=1)), fillColor='#3366CC')
    # SIDC que o milsymbol não reconhece (20 dígitos com letra).
    add('SIDC com letra', sidc='1003100016121100000X')
    # Correções de 2026-10-04 do MD33-C-01 (simbologia-md33-correcoes.test.js do Web).
    add('rótulo Mil 30/110000', sidc=sidc('30', icone='110000', escalao='00'))
    add('rótulo RbAM 30/130113', sidc=sidc('30', icone='130113', escalao='00'))
    add('rótulo Res 20/120801', sidc=sidc('20', icone='120801', escalao='00'))
    for ident in ('3', '6'):
        add('20/112202 asterisco SI ' + ident, sidc=sidc('20', identidade=ident, icone='112202', escalao='00'))
        add('15/209906 SISCOMIS SI ' + ident, sidc=sidc('15', identidade=ident, icone='209906', escalao='00'))
    add('20/112202 mod1 99 ext 2', sidc=sidc('20', icone='112202', escalao='00', m1='99', ext=extensao(m1=2)))
    add('20/111999 mod2 99 ext 3', sidc=sidc('20', icone='111999', escalao='00', m2='99', ext=extensao(m2=3)))
    add('20/111999 ext 4 mod2 02 hostil', sidc=sidc('20', identidade='6', icone='111999', escalao='00', m2='02',
                                                    ext=extensao(entidade=4)))
    add('27/110000 militar genérico', sidc=sidc('27', icone='110000', escalao='00'))
    add('27/120000 civil genérico', sidc=sidc('27', icone='120000', escalao='00'))
    add('02/110000 mod 01', sidc=sidc('02', icone='110000', escalao='00', m1='01', m2='01'))
    add('36/110000 mod 01', sidc=sidc('36', icone='110000', escalao='00', m1='01', m2='01'))
    return casos


def casos_medida():
    motor = Motor.instancia()
    casos = [('catálogo ' + c, {'pointCode': c}) for c in motor.codigos_de_medida()]
    casos += [
        ('130100 com textos', {'pointCode': '130100', 'tipo': 'P Lib', 'identificacao': 'ALFA',
                               'gdhIni': '121400Z JUN', 'gdhFim': 'Mdt O'}),
        ('130500 número 0', {'pointCode': '130500', 'numero': 0}),
        ('240601 concentração', {'pointCode': '240601', 'numeroConcentracao': 'HA 107'}),
        ('núcleo de tela', {'pointCode': 'ECHELON', 'echelonCode': 'ECHELON_18', 'identificacao': '1 Bda',
                            'status': 'preparado'}),
        ('núcleo FT incoerente', {'pointCode': 'ECHELON_FT', 'echelonCode': 'ECHELON_21'}),
        ('escalão FT', {'pointCode': 'ESCALAO_FT', 'echelonCode': 'ESCALAO_FT_15'}),
        ('cor', {'pointCode': '130600', 'fillColor': '#CC0000'}),
        ('cor no núcleo', {'pointCode': 'ECHELON_16', 'fillColor': '#0055AA', 'status': 'preparado-nao-ocupado',
                           'identificacao': 'X'}),
        ('290800 cor (máscara)', {'pointCode': '290800', 'fillColor': '#00AA00'}),
        ('texto com escape', {'pointCode': '130100', 'identificacao': 'A&B "C"'}),
        # Capítulo VII do MD33-C-01 (2026-10-04): a direção é a rotation, fora do desenho.
        ('152000 girada', {'pointCode': '152000', 'rotation': 120}),
        ('140500 secundária +70', {'pointCode': '140500', 'anguloSecundario': 70}),
        ('140500 secundária -170', {'pointCode': '140500', 'anguloSecundario': -170, 'fillColor': '#CC0000'}),
        ('140500 secundária 0', {'pointCode': '140500', 'anguloSecundario': 0}),
        ('270701 ac/qualquer/vazia', {'pointCode': '270701', 'mina1': 'ac', 'mina2': 'qualquer', 'mina3': 'vazia'}),
        ('270701 tudo vazia', {'pointCode': '270701', 'mina1': 'vazia', 'mina2': 'vazia', 'mina3': 'vazia'}),
        ('270701 mina inválida', {'pointCode': '270701', 'mina1': 'xx', 'mina2': 'ap', 'fillColor': '#00B04E'}),
        ('271204 verde', {'pointCode': '271204', 'fillColor': '#00B04E'}),
    ]
    return casos


def casos_engenharia():
    """As 34 variantes com os valores padrão, mais valores que exercitam texto, fundo e acesso."""
    itens = Motor.instancia().catalogos()['engenharia']['itens']
    casos = [('{} v{} {}'.format(it['codigo'], v['indice'], v['rotulo']),
              {'pointCode': it['codigo'], 'engineering': {'variant': v['indice'], 'values': {}}})
             for it in itens for v in it['variantes']]

    def add(nome, codigo, valores, variante=0, **extra):
        casos.append((nome, dict({'pointCode': codigo, 'engineering': {'variant': variante, 'values': valores}}, **extra)))

    for inc in ('3', '9', '12', '20', '?'):
        add('5 rampa ' + inc, '5', {'inclination': inc})
    add('2 fundo', '2', {'order': '15', 'fillBackground': True})
    add('7 curvas', '7', {'count': '3', 'radius': '12,5'})
    add('8 completo', '8', {'order': '12', 'wheelsTwo': '150', 'wheelsOne': '1000', 'clearance': '4,5',
                            'length': '1250', 'width': '12,5', 'railway': True, 'underClearance': True,
                            'underLength': True, 'underWidth': True, 'fillBackground': True})
    add('8 textos longos', '8', {'order': '123456789', 'length': '123456789012', 'width': '99,99'})
    add('9 fundo', '9', {'class': '100', 'order': '7', 'fillBackground': True})
    add('9 texto vazio', '9', {'class': ''})
    add('13 acesso nos dois', '13', {'access': 'both', 'speed': '1,5', 'material': 'R'})
    add('13 acesso à direita', '13', {'access': 'right', 'type': 'P'}, variante=1)
    add('14 acesso nos dois', '14', {'access': 'both', 'weight': '12,5', 'class': '100', 'order': '123'})
    add('14 sem acesso', '14', {'access': 'none'})
    add('15 larguras', '15', {'width': '3,5', 'length': '1200'})
    add('16 gabaritos iguais', '16', {'minimum': '3,5', 'maximum': '3,5'})
    add('16 gabaritos diferentes', '16', {'minimum': '3', 'maximum': '5,25'})
    add('17 portal', '17', {'roadWidth': '4,5', 'totalWidth': '7', 'clearance': '5'})
    add('18 túnel', '18', {'order': '2', 'length': '1500', 'roadWidth': '6', 'totalWidth': '8'})
    add('19 altura ?', '19', {'height': '?'})
    add('20 permanente', '20', {'foliage': 'permanent'}, variante=1)
    add('21 permanente', '21', {'foliage': 'permanent'}, variante=1)
    add('27 fundo', '27', {'fillBackground': True})
    add('28 fundo e cor', '28', {'fillBackground': True}, fillColor='#AA0000')
    add('9 cor', '9', {}, fillColor='#0055AA')
    return casos


def casos_declinacao():
    return [
        {'declination': -21.25, 'convergence': 0.62, 'fillColor': '#0077CC'},
        {'declination': 21.25, 'convergence': -1.15, 'fillColor': '#AA0000'},
        {'declination': 0.05, 'convergence': 0, 'fillColor': None},
        {'declination': -0.07, 'convergence': 9.5, 'fillColor': 'vermelho'},
        {'declination': 45.678, 'convergence': -12.3, 'fillColor': '#123456'},
        {'declination': 190, 'convergence': 0.001, 'fillColor': '#0077cc'},
    ]


def casos_wmm():
    return [
        {'lat': -15.79, 'lon': -47.88, 'data': '2026-10-04T12:00:00Z'},
        {'lat': -3.1, 'lon': -60.02, 'data': '2025-06-30T00:00:00Z'},
        {'lat': -30.03, 'lon': -51.23, 'data': '2027-01-01T00:00:00Z'},
        {'lat': -22.9, 'lon': -43.2, 'data': '2029-11-01T00:00:00Z'},
        {'lat': 0, 'lon': 0, 'data': '2026-01-01T00:00:00Z'},
        {'lat': 89.9, 'lon': 120, 'data': '2026-03-15T06:00:00Z'},
        {'lat': -80, 'lon': 179.9, 'data': '2026-03-15T06:00:00Z'},
        {'lat': 40.71, 'lon': -74.0, 'data': '2028-07-04T00:00:00Z'},
        {'lat': 51.5, 'lon': -0.12, 'data': '2025-02-01T00:00:00Z'},
        {'lat': -33.86, 'lon': 151.2, 'data': '2026-10-04T00:00:00Z'},
    ]


# ---------------------------------------------------------------------------------------------
# Referência do Web (Chromium via Playwright)
# ---------------------------------------------------------------------------------------------

_REFERENCIA = {}


def node_executavel():
    """EBGEO_NODE, o node do PATH, ou o instalador padrão do Windows (o .bat do QGIS troca o PATH)."""
    candidatos = [os.environ.get('EBGEO_NODE'), shutil.which('node')]
    for var in ('ProgramFiles', 'ProgramW6432'):
        if os.environ.get(var):
            candidatos.append(os.path.join(os.environ[var], 'nodejs', 'node.exe'))
    return next((c for c in candidatos if c and os.path.exists(c)), None)


def referencia_web():
    """Gera o arnês e roda todos os casos no Chromium uma vez; None se não houver EBGEO_WEB."""
    if 'r' in _REFERENCIA:
        return _REFERENCIA['r']
    web = os.environ.get('EBGEO_WEB')
    node = node_executavel()
    if not web or not node:
        _REFERENCIA['r'] = None
        return None
    pasta = tempfile.mkdtemp(prefix='ebgeo-paridade-')
    subprocess.run([node, os.path.join(MOTOR_BUILD, 'build.mjs'), '--web', web, '--paridade', pasta,
                    '--apenas-paridade'], check=True, capture_output=True, text=True)
    lista = ([{'tipo': 'simbolo', 'props': p} for _n, p in casos_simbolo()]
             + [{'tipo': 'medida', 'props': p} for _n, p in casos_medida()]
             + [{'tipo': 'engenharia', 'props': p} for _n, p in casos_engenharia()]
             + [{'tipo': 'declinacao', 'props': p} for p in casos_declinacao()]
             + [{'tipo': 'wmm', 'props': p} for p in casos_wmm()])
    entrada = os.path.join(pasta, 'casos.json')
    saida = os.path.join(pasta, 'saida.json')
    with open(entrada, 'w', encoding='utf-8') as f:
        json.dump(lista, f, ensure_ascii=False)
    t = time.perf_counter()
    r = subprocess.run([node, os.path.join(MOTOR_BUILD, 'paridade.mjs'), '--web', web,
                        '--arnes', os.path.join(pasta, 'paridade-web.js'), '--casos', entrada, '--saida', saida],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('paridade.mjs falhou: ' + r.stderr[-2000:])
    with open(saida, encoding='utf-8') as f:
        dados = json.load(f)
    print('\n[paridade] {} ({:.1f} s)'.format(r.stdout.strip(), time.perf_counter() - t))
    res = iter(dados['resultados'])
    ref = {
        'simbolo': [next(res) for _ in casos_simbolo()],
        'medida': [next(res) for _ in casos_medida()],
        'engenharia': [next(res) for _ in casos_engenharia()],
        'declinacao': [next(res) for _ in casos_declinacao()],
        'wmm': [next(res) for _ in casos_wmm()],
        'baseline': dados['baseline'],
    }
    _REFERENCIA['r'] = ref
    return ref


def comparar(nosso, web, chaves_offset='ancoraX'):
    """Diferenças entre a saída do QJSEngine e a do Web (lista vazia = paridade)."""
    if 'erro' in web:
        return ['web falhou: ' + web['erro']]
    dif = []
    if nosso['svgWeb'] != web['svg']:
        n, w = nosso['svgWeb'], web['svg']
        i = next((k for k in range(min(len(n), len(w))) if n[k] != w[k]), min(len(n), len(w)))
        dif.append('svg difere a partir do caractere {}: nosso ...{!r} web ...{!r}'.format(i, n[i:i + 60], w[i:i + 60]))
    for a, b in (('largura', 'largura'), ('altura', 'altura')):
        if abs(float(nosso[a]) - float(web[b])) > 1e-9:
            dif.append('{}: nosso {} web {}'.format(a, nosso[a], web[b]))
    if (nosso.get('iconOffset') or None) != (web.get('iconOffset') or None):
        dif.append('iconOffset: nosso {} web {}'.format(nosso.get('iconOffset'), web.get('iconOffset')))
    return dif


# ---------------------------------------------------------------------------------------------
# Utilidades de render
# ---------------------------------------------------------------------------------------------

def render_svg(svg, largura=200, altura=200):
    r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    img = QImage(QSize(largura, altura), QImage.Format.Format_ARGB32)
    img.fill(0)
    if r.isValid():
        p = QPainter(img)
        r.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        r.render(p, QRectF(0, 0, largura, altura))
        p.end()
    return r.isValid(), img


def pixels_tinta(img, passo=1):
    n = 0
    for y in range(0, img.height(), passo):
        for x in range(0, img.width(), passo):
            if img.pixelColor(x, y).alpha() > 0:
                n += 1
    return n


def caixa_tinta(img):
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).alpha() > 40:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def grade(itens, arquivo, celula=170, colunas=8):
    """PNG com a grade de desenhos (svg, rótulo) para conferência visual."""
    linhas = (len(itens) + colunas - 1) // colunas
    img = QImage(QSize(colunas * celula, linhas * (celula + 16)), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setFont(QFont('Arial', 7))
    for k, (svg, rotulo) in enumerate(itens):
        cx, cy = (k % colunas) * celula, (k // colunas) * (celula + 16)
        r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
        r.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        r.render(p, QRectF(cx + 8, cy + 4, celula - 16, celula - 16))
        p.setPen(QColor(0, 0, 0))
        p.drawText(QRectF(cx, cy + celula - 10, celula, 24), Qt.AlignmentFlag.AlignHCenter, rotulo[:34])
        p.setPen(QColor(220, 220, 220))
        p.drawRect(cx, cy, celula - 1, celula + 15)
    p.end()
    img.save(arquivo)
    return arquivo


# ---------------------------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------------------------

class TestCarga(unittest.TestCase):
    def test_carga_e_versao(self):
        Motor.descartar()
        t = time.perf_counter()
        m = Motor.instancia()
        carga = time.perf_counter() - t
        print('\n[desempenho] carga do bundle: {:.3f} s ({:.0f} KiB)'.format(
            carga, os.path.getsize(os.path.join(os.path.dirname(MOTOR_BUILD), 'ebgeo-simbologia.js')) / 1024))
        self.assertEqual(m.versao['milsymbol'], '3.0.4')
        self.assertIs(Motor.instancia(), m)
        self.assertLess(carga, 3.0)

    def test_catalogos(self):
        c = Motor.instancia().catalogos()
        conj = c['militar']['porConjunto']
        self.assertEqual(len(conj), 11)
        # 504 até 2026-10-04, mais o Terminal do SISCOMIS (15) e os genéricos Militar e Civil (27).
        self.assertEqual(sum(len(v['icones']) for v in conj.values()), 507)
        self.assertEqual(sum(len(v['mod1']) for v in conj.values()), 225)
        self.assertEqual(sum(len(v['mod2']) for v in conj.values()), 99)
        self.assertEqual(conj['10']['extensoes']['icone']['163499'], list(range(11)))
        self.assertTrue(conj['10']['aplicavel']['comando'])
        self.assertTrue(conj['10']['camposTexto']['fields'])
        # 130 até 2026-10-04, mais a Base de fogos (152000) e o Setor de Tiro (140500).
        self.assertEqual(len(c['medida']['porCodigo']), 132)
        self.assertEqual(sum(len(v) for v in c['medida']['categorias'].values()), 132)
        self.assertEqual(len(c['militar']['identidades']), 7)

    def test_bundle_sem_comentario_nem_mapa(self):
        with open(os.path.join(os.path.dirname(MOTOR_BUILD), 'ebgeo-simbologia.js'), encoding='utf-8') as f:
            texto = f.read()
        self.assertNotIn('sourceMappingURL', texto)
        self.assertNotIn('@fileoverview', texto)
        self.assertNotIn('military_tools/', texto)
        # Um único comentário de bloco de licença (milsymbol, MIT) e a linha de origem do build.
        self.assertEqual(texto.count('/*'), 2, 'comentários no bundle: {}'.format(texto.count('/*')))


class TestSimboloMilitar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motor = Motor.instancia()

    def test_paridade_com_o_web(self):
        ref = referencia_web()
        if ref is None:
            self.skipTest('EBGEO_WEB ou node ausente: paridade não medida')
        casos = casos_simbolo()
        self.assertGreaterEqual(len(casos), 50)
        iguais_svg = iguais_tudo = 0
        falhas = []
        for (nome, props), web in zip(casos, ref['simbolo']):
            nosso = self.motor.simbolo_militar(props)
            dif = comparar(nosso, web)
            if not dif:
                iguais_tudo += 1
            if 'erro' not in web and nosso['svgWeb'] == web['svg']:
                iguais_svg += 1
            if dif:
                falhas.append('{}: {}'.format(nome, '; '.join(dif)))
        print('\n[paridade] símbolo militar: {} casos, SVG byte a byte {}, SVG+tamanho+âncora {}'.format(
            len(casos), iguais_svg, iguais_tudo))
        for f in falhas:
            print('  DIFERENÇA ' + f)
        self.assertEqual(falhas, [])

    def test_pior_caso_sem_pos_processamento_reprova(self):
        """O comparador tem de acusar um SIDC brasileiro desenhado sem a extensão."""
        ref = referencia_web()
        casos = casos_simbolo()
        alvos = [i for i, (n, _p) in enumerate(casos) if n in ('163499 ext 5', 'rótulo 121700', 'comando amigo',
                                                               '20/111299 ext 3', 'modificador especial 2')]
        self.assertEqual(len(alvos), 5)
        for i in alvos:
            nome, props = casos[i]
            nosso = self.motor.simbolo_militar(props)
            # Degradação da saída REAL: o mesmo SIDC, com os códigos zerados como o gerador faz,
            # mas sem applyBrazilianModifications.
            s30 = nosso['sidc']
            render = s30[:20]
            if s30[10:16] in ('163499', '111299'):
                render = render[:10] + '000000' + render[16:]
            bruto = self.motor.svg_milsymbol_bruto(render)
            degradado = dict(nosso, svgWeb=bruto)
            alvo = {'svg': nosso['svgWeb'], 'largura': nosso['largura'], 'altura': nosso['altura'],
                    'iconOffset': nosso['iconOffset']}
            if ref is not None:
                alvo = ref['simbolo'][i]
            self.assertNotEqual(comparar(degradado, alvo), [], nome + ': o comparador aprovou o desenho sem extensão')
            self.assertEqual(comparar(nosso, alvo), [], nome)

    def test_sidc_invalido(self):
        with self.assertRaises(ErroMotor):
            self.motor.simbolo_militar({'sidc': 'XXXX'})
        with self.assertRaises(ErroMotor):
            self.motor.simbolo_militar({})
        r = self.motor.simbolo_militar({'sidc': '1003100016121100000X'})
        self.assertFalse(r['valido'])
        r = self.motor.simbolo_militar({'sidc': '10031000161211000000'})
        self.assertTrue(r['valido'])

    def test_baseline_corrigida(self):
        """Texto com dominant-baseline sai com y deslocado e sem o atributo."""
        r = self.motor.simbolo_militar({'sidc': sidc(icone='121700')})  # SF vira Cmdos
        self.assertIn('Cmdos', r['svg'])
        self.assertIn('dominant-baseline', r['svgWeb'])
        self.assertNotIn('dominant-baseline', r['svg'])
        ref = referencia_web()
        if ref is not None:
            b = ref['baseline']
            print('\n[baseline] Chromium: middle {} central {} hanging {}'.format(
                b['bold/middle'], b['bold/central'], b['bold/hanging']))
            self.assertAlmostEqual(b['bold/middle'], 0.2592, places=3)
            self.assertAlmostEqual(b['bold/central'], 0.35, places=3)
        # Prova no QSvgRenderer: o texto corrigido desce em relação ao original.
        _ok, a = render_svg(r['svgWeb'], 300, 300)
        _ok, c = render_svg(r['svg'], 300, 300)
        self.assertNotEqual(a, c)

    def test_svg_valido_no_qsvgrenderer(self):
        ruins = []
        for nome, props in casos_simbolo():
            r = self.motor.simbolo_militar(props)
            ok, img = render_svg(r['svg'], 120, 120)
            if not ok or pixels_tinta(img, 3) == 0:
                ruins.append(nome)
        self.assertEqual(ruins, [])

    def test_desempenho_1000_simbolos(self):
        casos = casos_simbolo()
        t = time.perf_counter()
        for k in range(1000):
            self.motor.simbolo_militar(casos[k % len(casos)][1])
        dt = time.perf_counter() - t
        print('\n[desempenho] 1000 símbolos militares: {:.2f} s ({:.2f} ms cada)'.format(dt, dt))
        self.assertLess(dt, 60)
        medidas = casos_medida()
        t = time.perf_counter()
        for k in range(1000):
            self.motor.medida(medidas[k % len(medidas)][1])
        dt = time.perf_counter() - t
        print('[desempenho] 1000 medidas de coordenação: {:.2f} s ({:.2f} ms cada)'.format(dt, dt))

    def test_grade_de_simbolos(self):
        itens = []
        for nome, props in casos_simbolo():
            r = self.motor.simbolo_militar(props)
            itens.append((r['svg'], nome))
        arq = grade(itens, os.path.join(SAIDA, 'grade_simbolos.png'))
        print('\n[render] ' + arq)
        self.assertTrue(os.path.exists(arq))


class TestMedida(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motor = Motor.instancia()

    def test_132_entradas_validas_no_qsvgrenderer(self):
        codigos = self.motor.codigos_de_medida()
        self.assertEqual(len(codigos), 132)
        validas = 0
        ruins = []
        for c in codigos:
            r = self.motor.medida({'pointCode': c})
            ok, img = render_svg(r['svg'], 120, 120)
            if ok and pixels_tinta(img, 2) > 0:
                validas += 1
            else:
                ruins.append(c)
        print('\n[medida] {} de {} entradas do catálogo com SVG válido e tinta no QSvgRenderer'.format(validas, len(codigos)))
        self.assertEqual(ruins, [])

    def test_paridade_com_o_web(self):
        ref = referencia_web()
        if ref is None:
            self.skipTest('EBGEO_WEB ou node ausente')
        falhas = []
        iguais = 0
        casos = casos_medida()
        for (nome, props), web in zip(casos, ref['medida']):
            nosso = self.motor.medida(props)
            dif = comparar(nosso, web)
            if web.get('anchor') != nosso['anchor']:
                dif.append('anchor')
            if dif:
                falhas.append('{}: {}'.format(nome, '; '.join(dif)))
            else:
                iguais += 1
        print('\n[paridade] medida: {} casos ({} do catálogo), iguais em SVG, tamanho e âncora: {}'.format(
            len(casos), len(self.motor.codigos_de_medida()), iguais))
        for f in falhas:
            print('  DIFERENÇA ' + f)
        self.assertEqual(falhas, [])

    def test_ancora_bottom_vira_deslocamento_do_centro(self):
        r = self.motor.medida({'pointCode': '130100'})
        self.assertEqual(r['anchor'], 'bottom')
        self.assertAlmostEqual(r['ancoraY'], round(-r['altura'] / 2 + r['iconOffset'][1], 2))

    def test_codigo_inexistente(self):
        with self.assertRaises(ErroMotor):
            self.motor.medida({'pointCode': 'NAO_EXISTE'})

    def test_grade_de_medidas(self):
        itens = []
        for nome, props in casos_medida():
            r = self.motor.medida(props)
            itens.append((r['svg'], nome.replace('catálogo ', '')))
        arq = grade(itens, os.path.join(SAIDA, 'grade_medidas.png'), celula=130, colunas=12)
        print('\n[render] ' + arq)


def view_box(svg):
    import re
    raiz = re.search(r'<svg\b[^>]*>', svg).group(0)
    return [float(v) for v in re.search(r'viewBox="([^"]+)"', raiz).group(1).split()]


def raster_no_espaco_do_usuario(svg, k=3, margem=30, largura=300, altura=260):
    """Rasteriza o SVG com a unidade do desenho fixa (k px) e a origem fixa: dois SVGs do mesmo
    desenho com viewBox um pouco diferentes caem pixel sobre pixel."""
    x, y, w, h = view_box(svg)
    img = QImage(QSize(largura * k, altura * k), QImage.Format.Format_ARGB32)
    img.fill(0)
    r = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    p = QPainter(img)
    r.render(p, QRectF((x + margem) * k, (y + margem) * k, w * k, h * k))
    p.end()
    return r.isValid(), img


def _alfa(img):
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    largura, altura = img.width(), img.height()
    bits = img.constBits()
    bits.setsize(img.sizeInBytes())
    dados = bytes(bits)
    passo = img.bytesPerLine()
    return [dados[y * passo + 3:y * passo + 4 * largura:4] for y in range(altura)]


def diferenca_de_tinta(a, b, limiar=96, folga=0):
    """(pixels que diferem, pixels de tinta na união). Com folga=1, um pixel de um lado só conta
    se o outro não tiver tinta em nenhum vizinho a 1 px (absorve o serrilhado entre renderizadores)."""
    A, B = _alfa(a), _alfa(b)
    h, w = min(len(A), len(B)), min(len(A[0]), len(B[0]))

    def tem(M, x, y):
        for yy in range(max(0, y - folga), min(h, y + folga + 1)):
            linha = M[yy]
            for xx in range(max(0, x - folga), min(w, x + folga + 1)):
                if linha[xx] > limiar:
                    return True
        return False
    dif = uniao = 0
    for y in range(h):
        la, lb = A[y], B[y]
        for x in range(w):
            ta, tb = la[x] > limiar, lb[x] > limiar
            if ta or tb:
                uniao += 1
                if ta != tb and not (folga and ((ta and tem(B, x, y)) or (tb and tem(A, x, y)))):
                    dif += 1
    return dif, uniao


class TestEngenharia(unittest.TestCase):
    """Os 23 itens / 34 variantes do C 5-36 pelo gerador do Web sobre o DOM mínimo."""

    # Limites. O texto é a única fonte de diferença entre o Chromium e o Qt: (a) a caixa do
    # texto no Chromium soma ao advance a tinta do glifo HINTADO em tamanho pequeno (medido:
    # '4 / V / ? / Y' a 21 px tem caixa de 104,50 e advance de 103,52), e o Qt mede sem hinting,
    # então o viewBox pode diferir até cerca de 1 unidade; (b) largura e altura lógicas são esse
    # viewBox × 0,7 mais o arredondamento do canvas do Web (até 0,5 px); (c) a tinta, rasterizada
    # pelo MESMO renderizador no MESMO espaço do desenho, só muda onde o texto foi reduzido a
    # data-max-width com advances que diferem em centésimos. Valores finais conferidos nas
    # medidas impressas pelo teste.
    LIMITE_CAIXA = 1.5
    LIMITE_TAMANHO = 1.6
    LIMITE_ANCORA = 1.1
    LIMITE_TINTA = 0.01

    @classmethod
    def setUpClass(cls):
        cls.motor = Motor.instancia()

    def test_34_variantes_validas_no_qsvgrenderer(self):
        cat = self.motor.catalogos()['engenharia']
        self.assertEqual(len(cat['itens']), 23)
        self.assertEqual(cat['totalVariantes'], 34)
        validas, ruins, itens = 0, [], []
        for nome, props in casos_engenharia()[:34]:
            r = self.motor.engenharia(props)
            ok, img = render_svg(r['svg'], 160, 160)
            if ok and pixels_tinta(img, 2) > 0 and not r['avisos']:
                validas += 1
            else:
                ruins.append((nome, r['avisos']))
            itens.append((r['svg'], nome))
        print('\n[engenharia] {} de 34 variantes com SVG válido e tinta no QSvgRenderer'.format(validas))
        grade(itens, os.path.join(SAIDA, 'grade_engenharia.png'), celula=150, colunas=7)
        self.assertEqual(ruins, [])

    def _comparar(self, nosso, web):
        vb_n, vb_w = view_box(nosso['svg']), view_box(web['svg'])
        caixa = max(abs(a - b) for a, b in zip(vb_n, vb_w))
        tam = max(abs(nosso['largura'] - web['largura']), abs(nosso['altura'] - web['altura']))
        anc = max(abs(a - b) for a, b in zip(nosso['iconOffset'], web['iconOffset']))
        _ok, a = raster_no_espaco_do_usuario(nosso['svg'])
        _ok, b = raster_no_espaco_do_usuario(web['svg'])
        dif, uniao = diferenca_de_tinta(a, b)
        return caixa, tam, anc, dif / max(1, uniao)

    def _chrome_contra_qt(self, nosso, web):
        """Informativo: PNG do Chromium contra o nosso SVG rasterizado pelo Qt no MESMO tamanho."""
        chrome = QImage.fromData(base64.b64decode(web['png']))
        qt = QImage(chrome.size(), QImage.Format.Format_ARGB32)
        qt.fill(0)
        p = QPainter(qt)
        QSvgRenderer(QByteArray(nosso['svg'].encode('utf-8'))).render(p, QRectF(0, 0, chrome.width(), chrome.height()))
        p.end()
        dif, uniao = diferenca_de_tinta(chrome, qt, folga=1)
        return chrome, dif / max(1, uniao)

    def test_paridade_com_o_web(self):
        ref = referencia_web()
        if ref is None:
            self.skipTest('EBGEO_WEB ou node ausente')
        casos = casos_engenharia()
        linhas, falhas, iguais = [], [], 0
        piores = [0, 0, 0, 0, 0]
        mosaico = []
        for (nome, props), web in zip(casos, ref['engenharia']):
            self.assertNotIn('erro', web, nome)
            nosso = self.motor.engenharia(props)
            if nosso['svg'] == web['svg']:
                iguais += 1
            m = self._comparar(nosso, web)
            chrome, dif_chrome = self._chrome_contra_qt(nosso, web)
            m = m + (dif_chrome,)
            piores = [max(a, b) for a, b in zip(piores, m)]
            linha = '{:<34} caixa {:.3f} tamanho {:.2f} âncora {:.2f} tinta {:.4f} (Chromium x Qt {:.4f})'.format(nome, *m)
            linhas.append(linha)
            if (m[0] > self.LIMITE_CAIXA or m[1] > self.LIMITE_TAMANHO or m[2] > self.LIMITE_ANCORA
                    or m[3] > self.LIMITE_TINTA):
                falhas.append(linha)
            mosaico.append((chrome, nosso['svg'], nome))
        print('\n[engenharia] paridade com o Web em {} casos: SVG idêntico byte a byte {}; pior caixa {:.3f} un., '
              'pior tamanho {:.2f} px, pior âncora {:.2f} px, pior tinta {:.4f}, pior Chromium x Qt {:.4f}'.format(
                  len(casos), iguais, *piores))
        for linha in linhas:
            print('  ' + linha)
        self._mosaico_chrome_qt(mosaico)
        self.assertEqual(falhas, [])

    def _mosaico_chrome_qt(self, itens, colunas=4):
        """Chromium (PNG do Web) e Qt (nosso SVG) no mesmo tamanho, lado a lado."""
        lado = 150
        linhas = (len(itens) + colunas - 1) // colunas
        img = QImage(QSize(colunas * 2 * lado, linhas * (lado + 14)), QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        p.setFont(QFont('Arial', 7))
        for k, (chrome, svg, nome) in enumerate(itens):
            x0, y0 = (k % colunas) * 2 * lado, (k // colunas) * (lado + 14)
            esc = min((lado - 8) / max(1, chrome.width()), (lado - 8) / max(1, chrome.height()))
            w, h = chrome.width() * esc, chrome.height() * esc
            p.drawImage(QRectF(x0 + 4, y0 + 4, w, h), chrome)
            QSvgRenderer(QByteArray(svg.encode('utf-8'))).render(p, QRectF(x0 + lado + 4, y0 + 4, w, h))
            p.setPen(QColor(0, 0, 0))
            p.drawText(QRectF(x0, y0 + lado - 2, 2 * lado, 14), Qt.AlignmentFlag.AlignHCenter,
                       'Chromium | Qt: ' + nome[:30])
            p.setPen(QColor(220, 220, 220))
            p.drawRect(x0, y0, 2 * lado - 1, lado + 13)
        p.end()
        arq = os.path.join(SAIDA, 'engenharia_chromium_qt.png')
        img.save(arq)
        print('[render] ' + arq)

    def test_pior_caso_reprova(self):
        """A régua tem de reprovar: (1) sem o medidor de texto do Qt; (2) o desenho real sem uma parte."""
        ref = referencia_web()
        if ref is None:
            self.skipTest('EBGEO_WEB ou node ausente')
        casos = casos_engenharia()
        indice = {n: i for i, (n, _p) in enumerate(casos)}
        # Alvos onde o texto DECIDE o desenho: é o extremo da caixa (26, 15, 16, 18, 8 completo)
        # ou é reduzido a data-max-width (8 textos longos, 14 acesso). Onde o texto fica no miolo
        # do desenho, trocar a fonte muda menos que a tolerância e a régua, por construção, aceita.
        alvos = ('26 v0 Exemplo', '15 larguras', '16 gabaritos diferentes', '18 túnel', '8 completo',
                 '8 textos longos', '14 acesso nos dois')
        # (1) Medidor na fonte errada (máquina sem Arial, caindo em serifada): a régua tem de
        # reprovar os itens cujo texto define a caixa ou é reduzido a data-max-width.
        from Calco.motor.motor import MedidorTexto, QJSValue

        class MedidorErrado(MedidorTexto):
            def _de(self, familia):
                return super()._de('Times New Roman')

        certos = [self.motor.engenharia(p) for _n, p in casos]
        g = self.motor._engine.globalObject()
        original = g.property('__ebgeoMedidor')
        errado = MedidorErrado()
        g.setProperty('__ebgeoMedidor', self.motor._engine.newQObject(errado))
        try:
            reprovados, mudaram, reprovados_todos = [], 0, 0
            for (nome, props), web, certo in zip(casos, ref['engenharia'], certos):
                errado_ = self.motor.engenharia(props)
                if errado_['svg'] == certo['svg']:
                    continue
                mudaram += 1
                m = self._comparar(errado_, web)
                if m[0] > self.LIMITE_CAIXA or m[1] > self.LIMITE_TAMANHO or m[3] > self.LIMITE_TINTA:
                    reprovados_todos += 1
                    if nome in alvos:
                        reprovados.append(nome)
            # Informativo: sem medidor algum, a estimativa de 0,556 fs por caractere é a largura
            # exata dos algarismos na Arial, e a régua só acusa os textos com letras.
            g.setProperty('__ebgeoMedidor', QJSValue())
            sem = [nome for nome in alvos
                   if self._comparar(self.motor.engenharia(casos[indice[nome]][1]), ref['engenharia'][indice[nome]])[0]
                   > self.LIMITE_CAIXA]
        finally:
            g.setProperty('__ebgeoMedidor', original)
        print('\n[engenharia] pior caso medidor em Times: alvos reprovados {} de {}; no geral, {} de {} casos que '
              'mudaram; sem medidor (informativo): {} de {} alvos'.format(
                  len(reprovados), len(alvos), reprovados_todos, mudaram, len(sem), len(alvos)))
        self.assertEqual(len(reprovados), len(alvos))
        # (2) A saída real degradada: o zigue-zague direito do acesso difícil do vau some.
        import re
        nome = '13 acesso nos dois'
        nosso = self.motor.engenharia(casos[indice[nome]][1])
        degradado = dict(nosso, svg=re.sub(r'<path data-part="ford-access-right"[^>]*/>', '', nosso['svg'], count=1))
        self.assertNotEqual(degradado['svg'], nosso['svg'])
        m = self._comparar(degradado, ref['engenharia'][indice[nome]])
        print('[engenharia] pior caso sem o zigue-zague direito: tinta {:.4f}'.format(m[3]))
        self.assertGreater(m[3], self.LIMITE_TINTA)

    def test_formulario(self):
        cat = self.motor.catalogos()['engenharia']
        item8 = next(i for i in cat['itens'] if i['codigo'] == '8')
        self.assertEqual(item8['rascunhoPadrao']['values']['order'], '3')
        self.assertTrue(any(c['tipo'] == 'checkbox' for c in item8['campos']))
        r = self.motor.engenharia_rascunho('13', {'variant': 9, 'values': {'type': 'X', 'order': 'a' * 50}})
        self.assertEqual(r['variant'], 0)            # variante inexistente volta a 0
        self.assertEqual(r['values']['type'], 'V')  # opção fora da lista é ignorada
        self.assertEqual(len(r['values']['order']), 40)
        self.assertEqual(self.motor.engenharia_erros('16', {'width': '4', 'minimum': '5', 'maximum': '4'})[0]['key'],
                         'maximum')
        self.assertEqual(self.motor.engenharia_erros('6', {'radius': '-2'})[0]['key'], 'radius')
        self.assertEqual(self.motor.engenharia_erros('6', {'radius': '2,5'}), [])

    def test_ponte_para_colunas(self):
        """simbolos.renderizar grava as colunas do calco a partir de point_code e engineering (JSON)."""
        from Calco import simbolos
        atributos = {'point_code': '9', 'engineering': json.dumps({'variant': 0, 'values': {'class': '60', 'order': '12'}}),
                     'fill_color': '#AA0000'}
        col, r = simbolos.renderizar('engineering_symbol', atributos, detalhes=True)
        svg = simbolos.svg_de_coluna(col['svg'])
        self.assertIn('>60</text>', svg)
        self.assertIn('color="#AA0000"', svg)
        self.assertEqual(col['largura_px'], r['largura'])
        self.assertEqual(col['svg_assinatura'], simbolos.assinatura('engineering_symbol', atributos))

    def test_desempenho(self):
        casos = casos_engenharia()
        t = time.perf_counter()
        for k in range(200):
            self.motor.engenharia(casos[k % len(casos)][1])
        dt = time.perf_counter() - t
        print('\n[desempenho] 200 símbolos de engenharia: {:.2f} s ({:.2f} ms cada)'.format(dt, dt * 5))


class TestDeclinacao(unittest.TestCase):
    def test_js_num(self):
        for v, esperado in ((200.0, '200'), (1e-7, '1e-7'), (0.00001, '0.00001'), (1e21, '1e+21'),
                            (123456789012345680000.0, '123456789012345680000'), (-0.5, '-0.5'),
                            (200.00000000000003, '200.00000000000003'), (0.1 + 0.2, '0.30000000000000004')):
            self.assertEqual(declinacao.js_num(v), esperado)
        self.assertEqual(declinacao.js_to_fixed(21.25, 1), '21.3')  # empate exato: JS sobe
        self.assertEqual(declinacao.js_to_fixed(0.05, 1), '0.1')    # 0.05 é 0.05000000000000000277

    def test_paridade_svg_e_wmm(self):
        ref = referencia_web()
        if ref is None:
            self.skipTest('EBGEO_WEB ou node ausente')
        iguais = 0
        for p, web in zip(casos_declinacao(), ref['declinacao']):
            nosso = declinacao.gerar_svg(p['declination'], p['convergence'], p['fillColor'])
            self.assertEqual(nosso, web['svg'], p)
            iguais += 1
        for p, web in zip(casos_wmm(), ref['wmm']):
            data = datetime.datetime.fromisoformat(p['data'].replace('Z', '+00:00'))
            nosso = declinacao.calcular_declinacao(p['lat'], p['lon'], 0, data)
            for k in ('declination', 'inclination', 'intensity'):
                self.assertEqual(nosso[k], web[k], (p, k, nosso[k], web[k]))
            self.assertEqual(declinacao.calcular_convergencia(p['lat'], p['lon']), web['convergence'], p)
        print('\n[paridade] declinação: {} SVG iguais; WMM {} pontos iguais (2 casas)'.format(iguais, len(casos_wmm())))

    def test_qsvgrenderer_desenha_as_pontas(self):
        """O SVG do Web vai sem mudança: o Qt 6.8 desenha o <marker>. Pior caso: sem ele, a ponta some."""
        svg = declinacao.renderizar(-21.3, 0.6)['svg']
        self.assertEqual(svg, declinacao.gerar_svg(-21.3, 0.6))
        sem = svg.replace(' marker-end="url(#arrowHead)"', '')
        _ok, img = render_svg(svg, 400, 500)
        _ok, img_sem = render_svg(sem, 400, 500)

        def ponta(im):  # região da ponta NM
            return sum(1 for x in range(70, 110) for y in range(80, 120) if im.pixelColor(x, y).alpha() > 0)
        print('\n[declinação] tinta na ponta NM: com marker {}, sem marker {}'.format(ponta(img), ponta(img_sem)))
        self.assertGreater(ponta(img), 1.5 * ponta(img_sem))
        grade([(svg, 'declinação -21,3 / conv. 0,6'), (declinacao.gerar_svg(21.25, -1.15, '#AA0000'), '21,25 / -1,15')],
              os.path.join(SAIDA, 'declinacao.png'), celula=300, colunas=2)

    def test_wmm2025_coeficientes(self):
        # Valor de controle: g(1,0) do WMM2025 publicado pela NOAA.
        with open(declinacao.ARQUIVO_COF, encoding='ascii') as f:
            linhas = f.read().splitlines()
        self.assertIn('WMM-2025', linhas[0])
        self.assertTrue(linhas[1].split()[:3] == ['1', '0', '-29351.8'])


class TestCapituloVII(unittest.TestCase):
    """
    O que o bundle tem de trazer do Web de 2026-10-04 (capítulo VII do MD33-C-01 e as correções
    de símbolo), conferido no próprio desenho, sem depender da paridade com o Chromium.
    """

    @classmethod
    def setUpClass(cls):
        cls.motor = Motor.instancia()
        cls.cat = cls.motor.catalogos()['medida']

    @staticmethod
    def _textos(svg):
        import re
        return re.findall(r'<text[^>]*>([^<]+)</text>', svg)

    def test_base_de_fogos_e_setor_de_tiro(self):
        base = self.motor.medida({'pointCode': '152000'})
        self.assertIn('M 100,100 V 58.6', base['svgWeb'])
        # O ponto é o meio da linha base (anchorSvg 100,100), não o centro do quadro.
        self.assertNotEqual((base['ancoraX'], base['ancoraY']), (0, 0))
        padrao = self.motor.medida({'pointCode': '140500'})
        aberto = self.motor.medida({'pointCode': '140500', 'anguloSecundario': 70})
        self.assertNotEqual(padrao['svgWeb'], aberto['svgWeb'])
        # Sem valor, a secundária sai a -45 graus (ANGULO_SECUNDARIO_PADRAO do Web).
        self.assertEqual(padrao['svgWeb'], self.motor.medida({'pointCode': '140500', 'anguloSecundario': -45})['svgWeb'])
        self.assertIn('stroke-dasharray="7,4"', aberto['svgWeb'])
        # A seta tem 100 unidades a 0,75 px cada em qualquer abertura: o tamanho não encolhe.
        self.assertGreaterEqual(max(aberto['largura'], aberto['altura']), 75)
        self.assertEqual(self.cat['porCodigo']['152000']['direcao'], {'rotulo': 'Direção dos fogos'})
        self.assertTrue(self.cat['porCodigo']['140500']['setorDeTiro'])

    def test_campo_minado_por_tipo_de_mina(self):
        padrao = self.motor.medida({'pointCode': '270701'})['svgWeb']
        self.assertEqual(padrao.count('<ellipse'), 3)
        self.assertEqual(padrao.count('<path'), 3)  # as antenas das três antipessoal
        r = self.motor.medida({'pointCode': '270701', 'mina1': 'ac', 'mina2': 'qualquer', 'mina3': 'vazia'})['svgWeb']
        self.assertEqual(r.count('<ellipse'), 2)
        self.assertNotIn('<path', r)
        self.assertEqual(self.cat['porCodigo']['270701']['campos'], ['mina1', 'mina2', 'mina3'])
        defs = self.cat['definicoesCampos']['mina1']
        self.assertEqual(defs['options'], ['ap', 'ac', 'qualquer', 'vazia'])
        self.assertEqual(defs['defaultValue'], 'ap')

    def test_area_minada_fora_do_seletor_e_destruicoes_verdes(self):
        lista = [i['code'] for i in self.cat['lista']]
        self.assertNotIn('270800', lista)
        self.assertIn('270800', self.cat['porCodigo'])  # a feição antiga continua desenhando
        self.assertTrue(self.motor.medida({'pointCode': '270800'})['svg'])
        for codigo in ('152000', '140500'):
            self.assertIn(codigo, lista)
        for codigo in ('271201', '271203', '271204'):
            self.assertEqual(self.cat['porCodigo'][codigo]['corPadrao'], '#00B04E', codigo)
        self.assertIsNone(self.cat['porCodigo']['130100'].get('corPadrao'))

    def test_correcoes_de_simbolo(self):
        m = self.motor
        for conj, icone, de, para in (('30', '110000', 'MIL', 'Mil'), ('30', '130113', 'AT', 'RbAM'),
                                      ('20', '120801', 'RES', 'Res')):
            t = self._textos(m.simbolo_militar({'sidc': sidc(conj, icone=icone, escalao='00')})['svgWeb'])
            self.assertIn(para, t, (conj, icone))
            self.assertNotIn(de, t, (conj, icone))
        aster = m.simbolo_militar({'sidc': sidc('20', icone='112202', escalao='00')})['svgWeb']
        self.assertIn('scale(0.5)', aster)
        siscomis = m.simbolo_militar({'sidc': sidc('15', icone='209906', escalao='00')})['svgWeb']
        self.assertNotIn('m 94.8206,78.1372', siscomis)
        self.assertIn('M 79.5,136.3 Q 100,119.1 120.5,136.3', siscomis)
        tenda = m.simbolo_militar({'sidc': sidc('20', icone='111999', escalao='00', m2='99', ext=extensao(m2=3))})['svgWeb']
        self.assertRegex(tenda, r'<text[^>]* y="140"[^>]*>Col</text>')
        icones27 = {i['codigo']: i['nome'] for i in m.catalogos()['militar']['porConjunto']['27']['icones']}
        self.assertEqual(icones27.get('110000'), 'Militar genérico')
        self.assertEqual(icones27.get('120000'), 'Civil genérico')
        icones15 = {i['codigo']: i['nome'] for i in m.catalogos()['militar']['porConjunto']['15']['icones']}
        self.assertEqual(icones15.get('209906'), 'Terminal do SISCOMIS')
        for conj in ('02', '36'):
            r = m.simbolo_militar({'sidc': sidc(conj, icone='110000', escalao='00', m1='01', m2='01')})
            self.assertEqual(r['avisos'], [], conj)


if __name__ == '__main__':
    unittest.main(verbosity=2, exit=False)
    print('\nImagens em: ' + SAIDA)
