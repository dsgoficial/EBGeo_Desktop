# -*- coding: utf-8 -*-
"""
Blocos ricos do dock para as feições comuns do mapa 2D (formulario/tipos/comuns.py) e para a aba
Fotos de qualquer tipo (formulario/fotos.py). ui/painel.py chama `elemento_rico` ao montar um
Texto da especificação; os que não são deste bloco seguem o caminho de sempre.

  - Fotos: as fotos anexas à feição, lidas do próprio GeoPackage (tabela ebgeo_foto, mesmo sem a
    camada de fotos no projeto), com miniatura, nome e o botão Abrir, que grava uma cópia numa
    pasta temporária e a abre no visualizador do sistema. Nada se apaga: nem a foto do calco,
    nem a cópia aberta (o visualizador pode estar com ela).
  - Azimute e Distância: o resumo da construção polar e o botão "Editar pernas...", que abre o
    painel do Azimute (azimute/painel.py) em edição para a feição do dock.
"""
import os
import tempfile

from qgis.PyQt.QtCore import QTimer, QUrl, Qt
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...formulario import fotos as F
from ...formulario.tipos import comuns as C

PASTA_ABERTAS = 'ebgeo_fotos'
LADO_MINIATURA = 96


class _Rico:
    """Marca na lista de linhas do painel: o elemento rico só segue a condição (sem texto a avaliar)."""
    def __init__(self, nome):
        self.nome = nome


class _Fixa:
    """Condição já decidida pelo dock (a expressão é a constante)."""
    def __init__(self, vale):
        self.vale = bool(vale)

    def expressao(self):
        return 'TRUE' if self.vale else 'FALSE'

    def avaliar(self, _atributos):
        return self.vale


def elemento_rico(painel, fl, el, conds, attrs, travada):
    """Monta o bloco rico do Texto da especificação; devolve False quando ele não é deste bloco."""
    rico = getattr(el, 'rico', None)
    if rico == 'fotos':
        w = bloco_fotos(painel, attrs, conds)
    elif rico == 'azimute':
        w = bloco_azimute(painel, attrs, travada)
    else:
        return False
    fl.addRow(w)
    painel._linhas.append((_Rico(el.nome), list(conds), fl, w, None))
    return True


# ---------------------------------------------------------------------------------------------
# Fotos
# ---------------------------------------------------------------------------------------------

def fotos_do_painel(painel, attrs):
    caminho = F.caminho_do_gpkg(painel.layer.source()) if painel.layer is not None else ''
    return F.fotos_da_feicao(caminho, attrs.get('ebgeo_id'))


def bloco_fotos(painel, attrs, conds):
    lista = fotos_do_painel(painel, attrs)
    # A seção Fotos segue as fotos lidas do arquivo, e não a expressão do nativo (que precisa da
    # camada de fotos no projeto): a condição da aba, compartilhada com a seção, vira a constante.
    conds[:] = [_Fixa(bool(lista))]
    caixa = QWidget()
    caixa.setObjectName('EBGeoFotos')
    v = QVBoxLayout(caixa)
    v.setContentsMargins(0, 4, 0, 4)
    cab = QLabel('{} foto(s) anexa(s) à feição no EBGeo Web.'.format(len(lista)))
    cab.setWordWrap(True)
    v.addWidget(cab)
    caixa.botoes_abrir = []
    for foto in lista:
        linha = QWidget()
        h = QHBoxLayout(linha)
        h.setContentsMargins(0, 2, 0, 2)
        mini = QLabel()
        mini.setFixedSize(LADO_MINIATURA, LADO_MINIATURA)
        mini.setAlignment(Qt.AlignmentFlag.AlignCenter)
        px = QPixmap()
        dados = F.bytes_da_foto(foto, miniatura=True)
        if dados and px.loadFromData(dados):
            mini.setPixmap(px.scaled(LADO_MINIATURA, LADO_MINIATURA, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        else:
            mini.setText('sem imagem')
        h.addWidget(mini)
        nome = QLabel('{}\n{}'.format(foto.get('nome') or foto.get('foto_id') or 'Foto', foto.get('mime') or ''))
        nome.setWordWrap(True)
        h.addWidget(nome, 1)
        b = QPushButton('Abrir')
        b.setToolTip('Abre a foto no visualizador do sistema (uma cópia temporária; a foto do calco não muda).')
        b.setEnabled(F.bytes_da_foto(foto) is not None)
        b.clicked.connect(lambda _=False, f=foto: abrir_foto(painel, f))
        h.addWidget(b)
        caixa.botoes_abrir.append(b)
        v.addWidget(linha)
    caixa.fotos = lista
    return caixa


def abrir_foto(painel, foto):
    """Grava a foto numa pasta temporária e a abre no visualizador do sistema. Devolve o caminho."""
    dados = F.bytes_da_foto(foto)
    if dados is None:
        painel.iface.messageBar().pushWarning('EBGeo', 'A foto não tem bytes no calco.')
        return None
    pasta = os.path.join(tempfile.gettempdir(), PASTA_ABERTAS, str(foto.get('foto_id') or 'foto'))
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, F.nome_de_arquivo(foto))
    with open(caminho, 'wb') as fh:
        fh.write(dados)
    if not QDesktopServices.openUrl(QUrl.fromLocalFile(caminho)):
        painel.iface.messageBar().pushWarning('EBGeo', 'Nenhum programa abriu a foto {}.'.format(os.path.basename(caminho)))
    return caminho


# ---------------------------------------------------------------------------------------------
# Azimute e Distância
# ---------------------------------------------------------------------------------------------

def resumo_azimute(polar):
    """O mesmo resumo do nativo (tipos/comuns.expressao_resumo_azimute), escrito em Python."""
    if not polar:
        return ''
    modos, nortes = dict(C.MODOS_AZIMUTE), dict(C.NORTES_AZIMUTE)
    pernas = polar.get('legs') or []
    ref = polar.get('referencePoint') or [None, None]
    partes = ['<b>{}</b>: {} perna(s), azimutes em {} no {}, distâncias em {}.'.format(
        modos.get(polar.get('outputMode'), 'Construção'), len(pernas),
        'milésimos' if polar.get('angularUnit') == 'mils' else 'graus',
        nortes.get(polar.get('northReference'), 'Norte Verdadeiro (NV)'),
        'km' if polar.get('distanceUnit') == 'kilometers' else 'm')]
    try:
        partes.append('Ponto de referência (lat, lon): {:.6f}, {:.6f}; declinação magnética {:.2f}°.'.format(
            float(ref[1]), float(ref[0]), float(polar.get('magneticDeclination') or 0)))
    except (TypeError, ValueError, IndexError):
        pass
    if polar.get('isReferencePoint'):
        partes.append('Este ponto é o ponto de referência.')
    elif polar.get('waypointIndex') is not None:
        partes.append('Este ponto é o fim da perna {}.'.format(polar.get('waypointIndex')))
    linhas = ''.join('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
        i + 1, p.get('azimuth', ''), p.get('distance', ''), str(p.get('observation') or '').replace('<', '&lt;'))
        for i, p in enumerate(pernas) if isinstance(p, dict))
    return '<br/>'.join(partes) + ('<table><tr><th>Perna</th><th>Azimute</th><th>Distância</th><th>Observação</th></tr>'
                                   '{}</table>'.format(linhas))


def construcao(painel):
    from ...azimute import gravacao
    if painel.layer is None or painel.fid is None:
        return None
    return gravacao.construcao_da_feicao(painel.layer.getFeature(painel.fid))


def bloco_azimute(painel, attrs, travada):
    caixa = QWidget()
    caixa.setObjectName('EBGeoResumoAzimute')
    v = QVBoxLayout(caixa)
    v.setContentsMargins(0, 4, 0, 4)
    lb = QLabel(resumo_azimute(construcao(painel)))
    lb.setWordWrap(True)
    v.addWidget(lb)
    b = QPushButton('Editar pernas...')
    b.setToolTip('Abre o painel Azimute e Distância com a construção desta feição.')
    b.setEnabled(not travada)
    b.clicked.connect(lambda *_: editar_pernas(painel))
    v.addWidget(b)
    caixa.resumo, caixa.botao = lb, b
    return caixa


def controlador_azimute():
    """O Azimute e Distância do plugin carregado (EBGeo.azimuteDistancia), ou None."""
    try:
        from qgis.utils import plugins
    except ImportError:
        return None
    for p in list(plugins.values()):
        c = getattr(p, 'azimuteDistancia', None)
        if c is not None:
            return c
    return None


def _no_buffer_e_remonta(painel, camada, acao, texto):
    """
    O Salvar do Azimute no buffer do dock, que se remonta com o resumo novo. Se o dock já mostra
    outra camada, a sessão dele não é desta: grava como a ferramenta solta.
    """
    if painel.layer is not camada:
        acao()
        return True
    ok = painel._no_buffer(acao, texto)
    QTimer.singleShot(0, painel._selecao_mudou)
    return ok


def editar_pernas(painel):
    """Abre o painel do Azimute em edição para a feição do dock. Devolve True quando abriu."""
    c = controlador_azimute()
    if c is None:
        painel.iface.messageBar().pushWarning('EBGeo', 'O Azimute e Distância não está carregado no plugin.')
        return False
    if not c.editar_feicao(painel.layer, painel.fid, no_buffer=lambda acao, texto, camada=painel.layer: _no_buffer_e_remonta(painel, camada, acao, texto)):
        painel.iface.messageBar().pushWarning('EBGeo', 'A feição não tem construção do Azimute e Distância.')
        return False
    return True
