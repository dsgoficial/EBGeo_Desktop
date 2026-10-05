# -*- coding: utf-8 -*-
"""
Prévia do símbolo no dock, como no painel do Web.

  - Símbolos pontuais por SVG (militar, medida, engenharia, declinação): o SVG gravado na feição
    do buffer (ou o PNG do .ebgeo) desenhado no lugar do elemento de prévia da especificação
    (especificacao.previa_simbolo), renovado a cada mudança: o guardião redesenha o SVG no mesmo
    comando em que o SIDC, o código ou um amplificador muda.
  - Linhas, áreas, táticos e comuns: uma amostra desenhada com o estilo da própria camada e os
    atributos da feição (convencoes.amostras_png, a técnica do quadro de convenções), fora da linha
    da interface (o estilo tático leva até 2 s), começada ao mostrar a feição e refeita 300 ms
    depois da última mudança; com os mesmos atributos, não se redesenha.
"""
import base64

from qgis.PyQt.QtCore import QByteArray, QRectF, Qt, QTimer
from qgis.PyQt.QtGui import QImage, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QLabel

from ...formulario import especificacao as esp

ALTURA = esp.ALTURA_PREVIA
LARGURA_AMOSTRA = 300
# Janela da amostra em mm de papel, quando o tipo pede outra que a padrão de 40 x 20
JANELAS_MM = {'text': (160.0, 30.0)}


def _texto(v):
    return '' if v is None or (hasattr(v, 'isNull') and v.isNull()) else str(v)


def pixmap_do_simbolo(feat):
    """QPixmap do SVG (base64) da feição, na altura da prévia; o PNG do .ebgeo sem SVG; ou None."""
    svg = _texto(feat['svg']) if feat.fieldNameIndex('svg') >= 0 else ''
    if svg:
        from qgis.PyQt.QtSvg import QSvgRenderer
        r = QSvgRenderer(QByteArray(base64.b64decode(svg)))
        if not r.isValid():
            return None
        tam = r.defaultSize()
        largura = max(1, int(round(ALTURA * tam.width() / max(1, tam.height()))))
        img = QImage(largura, ALTURA, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        r.render(p, QRectF(0, 0, largura, ALTURA))
        p.end()
        return QPixmap.fromImage(img)
    png = _texto(feat['bitmap_b64']) if feat.fieldNameIndex('bitmap_b64') >= 0 else ''
    if png:
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(png))
        return pm.scaledToHeight(ALTURA, Qt.TransformationMode.SmoothTransformation) if not pm.isNull() else None
    return None


class PreviaSimbolo(QLabel):
    """O desenho do SVG da feição do buffer (símbolos pontuais)."""

    def __init__(self):
        super().__init__()
        self.setObjectName('EBGeoPreviaSimbolo')
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(ALTURA + 8)

    def atualizar(self, painel):
        if _sem_objeto(painel.layer) or painel.fid is None:
            return
        try:
            pm = pixmap_do_simbolo(painel.layer.getFeature(painel.fid))
        except Exception:  # SVG ilegível: a prévia fica vazia, o painel segue
            pm = None
        if pm is None:
            self.setText('Sem desenho gravado.')
        else:
            self.setPixmap(pm)


class PreviaAmostra(QLabel):
    """A amostra da feição desenhada com o estilo da camada (linhas, áreas, táticos e comuns)."""

    def __init__(self):
        super().__init__()
        self.setObjectName('EBGeoPreviaAmostra')
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(LARGURA_AMOSTRA // 2 + 8)
        self._painel = None
        self._chave = None
        self._job = None
        self._de_novo = False
        self.desenhos = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.desenhar)

    def atualizar(self, painel):
        """Agenda o desenho (as mudanças em sequência viram um desenho só)."""
        self._painel = painel
        self._timer.start(300)

    def desenhar(self):
        # roda num temporizador ou no fim de um desenho: exceção que escapa de um slot derruba o
        # QGIS (PyQt6), e a camada pode ter saído do projeto entre a mudança e o desenho
        try:
            self._iniciar()
        except Exception as e:  # amostra com defeito não derruba o painel
            self.setText('Amostra indisponível: {}'.format(e))

    def _iniciar(self):
        painel = self._painel
        if _sem_objeto(painel) or _sem_objeto(painel.layer) or painel.fid is None:
            return
        if self._job is not None:
            self._de_novo = True  # desenha de novo quando o atual terminar
            return
        feat = painel.layer.getFeature(painel.fid)
        if not feat.isValid():
            return
        chave = (painel.layer.id(), painel.fid, tuple(str(v) for v in feat.attributes()))
        if chave == self._chave:
            return  # os mesmos atributos: a amostra mostrada vale
        self._chave = chave
        from ... import convencoes
        # o desenho do estilo roda fora da linha da interface (até 2 s na Linha de Coordenação)
        # o texto sai em mm, como no mapa: a janela é larga para ele caber, e a imagem encolhe ao mostrar
        largura_mm, altura_mm = JANELAS_MM.get(painel.tipo, (40.0, 20.0))
        self._job = convencoes.amostras_png(painel.layer, painel.tipo, [feat], largura_mm=largura_mm, altura_mm=altura_mm,
                                            dpi=LARGURA_AMOSTRA / (40.0 / 25.4),
                                            geometria=convencoes.geometria_amostra_qualquer, pronto=self._pronto)
        if self._job is not None:
            _JOBS.add(self._job)

    def _pronto(self, lista):
        job, self._job = self._job, None
        _JOBS.discard(job)
        if _sem_objeto(self):
            return
        try:
            png = lista[0] if lista else None
            if png:
                pm = QPixmap()
                pm.loadFromData(base64.b64decode(png))
                if pm.width() > LARGURA_AMOSTRA:
                    pm = pm.scaledToWidth(LARGURA_AMOSTRA, Qt.TransformationMode.SmoothTransformation)
                self.setPixmap(pm)
            else:
                self.setText('')
            self.desenhos += 1
            if self._de_novo:
                self._de_novo = False
                self._timer.start(0)
        except Exception:  # o painel foi remontado no meio do desenho
            pass

    def desenhando(self):
        return self._job is not None or self._timer.isActive()


_JOBS = set()  # os desenhos em curso, vivos até o fim


def esperar(painel, limite_s=20):
    """Espera a amostra do dock terminar de desenhar (capturas e testes)."""
    import time
    from qgis.PyQt.QtWidgets import QApplication
    fim = time.time() + limite_s
    w = getattr(painel, '_amostra', None)
    while w is not None and not _sem_objeto(w) and w.desenhando() and time.time() < fim:
        QApplication.processEvents()
        time.sleep(0.02)


def _sem_objeto(obj):
    try:
        from qgis.PyQt import sip
    except ImportError:  # pragma: no cover
        import sip
    return obj is None or sip.isdeleted(obj)


def elemento_rico(painel, fl, el, conds, attrs, travada):
    """O elemento de prévia da especificação, no dock. Devolve True quando o tratou."""
    if not isinstance(el, esp.Texto) or el.nome != esp.NOME_PREVIA:
        return False
    w = PreviaSimbolo()
    fl.addRow(w)
    painel._linhas.append((el, conds, fl, w, None))
    w.atualizar(painel)
    return True


def amostra_no_topo(painel):
    """A amostra do tipo sem SVG, logo abaixo do cabeçalho do dock."""
    from ... import simbolos
    if painel.tipo in simbolos.TIPOS_SVG:
        return None
    w = PreviaAmostra()
    painel.form.addRow(w)
    w._painel = painel
    # na volta ao laço de eventos: o painel se remonta mais de uma vez ao trocar a seleção, e só a
    # amostra do último desenha; as mudanças seguintes esperam 300 ms
    w._timer.start(0)
    return w
