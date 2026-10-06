# -*- coding: utf-8 -*-
"""
Recursos compilados do plugin (`EBGeo/resources.qrc` e `EBGeo/resources_rc.py`) no QGIS 4.

Rodar com o Python do QGIS 4, a partir da raiz do repositório:

    python-qgis.bat EBGeo/testes/test_recursos.py

O QGIS 4 não traz compilador de recursos (o PyQt6 não tem pyrcc, e a pasta do Qt6 do instalador
não tem o rcc); o `resources_rc.py` se gera com o rcc do Qt 6 (por exemplo o do pacote PySide6,
`rcc -g python --no-zstd resources.qrc`), trocando o `from PySide6 import QtCore` por
`from qgis.PyQt import QtCore`. O zstd fica de fora porque o Qt do QGIS pode não lê-lo.

O que se prova:
    TestRecursos   o compilado tem exatamente os arquivos do .qrc, byte a byte iguais aos do disco,
                   sem o ícone antigo `icons/dsg.png` (nem no .qrc, nem no disco, nem no código), e
                   todo caminho `:/plugins/EBGeo/...` citado no código existe no compilado;
    TestIcones     o plugin carregado: as ações do menu e do submenu do BDGEx têm ícone, e os
                   painéis que leem ícone do compilado (Análise de Visibilidade, Ir para
                   coordenada) o desenham; a folha dos ícones vai para EBGEO_TESTE_SAIDA (ou uma
                   pasta temporária) para conferência. A Calculadora de Declinação aberta não
                   deixa caixa de mensagem de topo solta (a causa da saída 139 do K7).
"""
import glob
import hashlib
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
PACOTE = os.path.dirname(AQUI)                 # .../EBGeo
RAIZ_REPO = os.path.dirname(PACOTE)
if RAIZ_REPO not in sys.path:
    sys.path.insert(0, RAIZ_REPO)

from qgis.core import QgsApplication  # noqa: E402

_APP = QgsApplication.instance()
if _APP is None:
    _APP = QgsApplication([], True)
    _APP.initQgis()
from qgis.testing.mocked import get_iface  # noqa: E402
import qgis.utils  # noqa: E402
IFACE = get_iface()
qgis.utils.iface = IFACE
sys.path.append(os.path.join(QgsApplication.prefixPath(), 'python', 'plugins'))
from processing.core.Processing import Processing  # noqa: E402
Processing.initialize()

from qgis.PyQt.QtCore import QDirIterator, QFile, QFileInfo, QIODevice, QSize  # noqa: E402
from qgis.PyQt.QtGui import QColor, QIcon, QImage, QPainter  # noqa: E402

PREFIXO = ':/plugins/EBGeo'
SAIDA = os.environ.get('EBGEO_TESTE_SAIDA') or tempfile.mkdtemp(prefix='ebgeo_recursos_')


def arquivos_do_qrc():
    raiz = ET.parse(os.path.join(PACOTE, 'resources.qrc')).getroot()
    arquivos = {}
    for q in raiz.iter('qresource'):
        prefixo = q.get('prefix', '/').rstrip('/')
        for f in q.iter('file'):
            arquivos[':' + prefixo + '/' + (f.get('alias') or f.text.strip())] = f.text.strip()
    return arquivos


def recursos_compilados():
    """Caminho -> md5 de todo arquivo sob o prefixo do plugin no compilado carregado."""
    from EBGeo import resources_rc  # noqa: F401  (registra os recursos)
    achados = {}
    it = QDirIterator(PREFIXO, QDirIterator.IteratorFlag.Subdirectories)
    while it.hasNext():
        caminho = it.next()
        if QFileInfo(caminho).isDir():
            continue
        f = QFile(caminho)
        if f.open(QIODevice.OpenModeFlag.ReadOnly):
            achados[caminho] = hashlib.md5(bytes(f.readAll())).hexdigest()
            f.close()
    return achados


def md5_disco(relativo):
    with open(os.path.join(PACOTE, relativo), 'rb') as fh:
        return hashlib.md5(fh.read()).hexdigest()


def citados_no_codigo():
    padrao = re.compile(r':/plugins/EBGeo/[A-Za-z0-9_./-]+')
    citados = {}
    for arq in glob.glob(os.path.join(PACOTE, '**', '*.py'), recursive=True) + \
            glob.glob(os.path.join(PACOTE, '**', '*.ui'), recursive=True):
        if os.path.basename(arq) == 'resources_rc.py' or os.path.abspath(arq) == os.path.abspath(__file__):
            continue
        with open(arq, encoding='utf-8', errors='replace') as fh:
            for m in padrao.findall(fh.read()):
                citados.setdefault(m, os.path.relpath(arq, PACOTE))
    return citados


class TestRecursos(unittest.TestCase):
    def test_compilado_igual_ao_qrc_e_ao_disco(self):
        qrc = arquivos_do_qrc()
        comp = recursos_compilados()
        self.assertEqual(sorted(set(comp) - set(qrc)), [], 'no compilado e fora do .qrc')
        self.assertEqual(sorted(set(qrc) - set(comp)), [], 'no .qrc e fora do compilado')
        diferentes = [c for c, rel in qrc.items() if comp[c] != md5_disco(rel)]
        self.assertEqual(diferentes, [], 'compilado diferente do arquivo em disco')

    def test_icone_dsg_saiu(self):
        self.assertNotIn(PREFIXO + '/icons/dsg.png', arquivos_do_qrc())
        self.assertNotIn(PREFIXO + '/icons/dsg.png', recursos_compilados())
        self.assertFalse(os.path.exists(os.path.join(PACOTE, 'icons', 'dsg.png')))
        citam = []
        for arq in glob.glob(os.path.join(PACOTE, '**', '*.*'), recursive=True):
            if arq.endswith(('.py', '.ui', '.qrc', '.txt', '.json', '.qml')) and \
                    os.path.basename(arq) != 'resources_rc.py' and os.path.abspath(arq) != os.path.abspath(__file__):
                with open(arq, encoding='utf-8', errors='replace') as fh:
                    if 'dsg.png' in fh.read():
                        citam.append(os.path.relpath(arq, PACOTE))
        self.assertEqual(citam, [])

    def test_caminho_citado_no_codigo_existe_no_compilado(self):
        comp = recursos_compilados()
        faltam = {c: a for c, a in citados_no_codigo().items() if c not in comp}
        self.assertEqual(faltam, {})


def folha(icones, nome):
    """Os ícones lado a lado em 32 px, para conferência por imagem."""
    lado = 40
    img = QImage(QSize(lado * max(1, len(icones)), lado), QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    for i, ic in enumerate(icones):
        p.drawPixmap(i * lado + 4, 4, ic.pixmap(32, 32))
    p.end()
    caminho = os.path.join(SAIDA, nome)
    img.save(caminho)
    return caminho


def desenha(icone):
    """Verdadeiro quando o ícone tem pixel não transparente em 32 px."""
    if icone.isNull():
        return False
    img = icone.pixmap(32, 32).toImage()
    return any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height()))


class TestIcones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qgis.PyQt.QtWidgets import QMenu, QToolBar
        IFACE.firstRightStandardMenu.return_value = QMenu()
        IFACE.addToolBar.side_effect = lambda nome: QToolBar(nome)
        from EBGeo.ebgeo import EBGeo
        cls.plugin = EBGeo(IFACE)
        cls.plugin.initGui()

    def test_acoes_do_menu_tem_icone(self):
        acoes = [a for a in self.plugin.ebGeo.actions() if a.menu() is None and not a.isSeparator()]
        self.assertGreater(len(acoes), 10)
        sem = [a.text() for a in acoes if not desenha(a.icon())]
        folha([a.icon() for a in acoes], 'recursos_acoes.png')
        self.assertEqual(sem, [])

    def test_acoes_do_bdgex_tem_icone(self):
        # as 29 do submenu do BDGEx apontavam para `:/plugins/DsgTools/icons/eb.png`, recurso de
        # outro plugin, e saíam sem ícone; o eb.png deste plugin está no compilado
        sub = [a.menu() for a in self.plugin.ebGeo.actions() if a.menu() is not None and a.menu().objectName() == 'bdgex']
        self.assertEqual(len(sub), 1)

        def folhas(menu):
            for a in menu.actions():
                if a.menu() is not None:
                    yield from folhas(a.menu())
                elif not a.isSeparator():
                    yield a
        acoes = list(folhas(sub[0]))
        self.assertEqual(len(acoes), 29)
        self.assertEqual([a.text() for a in acoes if not desenha(a.icon())], [])
        folha([a.icon() for a in acoes], 'recursos_bdgex.png')
        # o caminho de antes não desenha
        self.assertFalse(desenha(QIcon(':/plugins/DsgTools/icons/eb.png')))

    def test_declinacao_sem_caixa_de_mensagem_solta(self):
        # a Calculadora de Declinação criava um QMessageBox() sem pai que nada usava, a causa da
        # saída 139 do K7 (a janela de topo viva no fim do processo, destruída pelo sip em ordem
        # que varia de uma execução para outra)
        from qgis.PyQt.QtWidgets import QApplication, QMessageBox

        def soltas():
            return {id(w) for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox)}
        antes = soltas()
        IFACE.addDockWidget.reset_mock()
        acao = {a.text(): a for a in self.plugin.ebGeo.actions()}['Calculadora de Declinação magnética e convergência meridiana']
        acao.trigger()
        self.assertEqual(IFACE.addDockWidget.call_count, 1)
        self.assertIs(IFACE.addDockWidget.call_args[0][1], self.plugin.mainDecConv.dockWindow)
        self.assertEqual(soltas() - antes, set())

    def test_paineis_desenham_os_icones_do_compilado(self):
        from qgis.PyQt.QtWidgets import QAbstractButton
        acoes = {a.text(): a for a in self.plugin.ebGeo.actions()}
        acoes['Análise de Visibilidade'].trigger()
        self.plugin.loadZoomTool()
        icones = {}
        for painel in (self.plugin.visibilityAnalysisToolBox, self.plugin.zoom_to):
            for b in painel.findChildren(QAbstractButton):
                if not b.icon().isNull():
                    icones[type(painel).__name__ + '.' + b.objectName()] = b.icon()
        print('\nÍcones dos painéis: ' + ', '.join(sorted(icones)))
        # os cinco ícones do compilado que o código cita: reload e criarCamada (Análise de
        # Visibilidade), zoomtool, copyicon e converter (Ir para coordenada)
        self.assertGreaterEqual(len(icones), 5)
        self.assertEqual([n for n, ic in icones.items() if not desenha(ic)], [])
        print('Folha: ' + folha(list(icones.values()), 'recursos_paineis.png'))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    print('Imagens em', SAIDA)
    sys.exit(0 if r.wasSuccessful() else 1)
