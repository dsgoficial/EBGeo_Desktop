# -*- coding: utf-8 -*-
"""
Ponte entre a feição do calco e o motor de símbolos pontuais.

- props_web_de_atributos(tipo, atributos): colunas do GeoPackage -> propriedades do EBGeo Web;
- assinatura(tipo, atributos): hash dos campos que DESENHAM, recalculável por expressão nativa
  do QGIS (expressao_assinatura), para o estilo acusar SVG velho sem o plugin;
- renderizar(tipo, atributos): as colunas de desenho prontas para gravar (svg em base64,
  svg_assinatura, largura_px, altura_px, ancora_dx, ancora_dy);
- RegeneradorSvg(layer, tipo): regrava essas colunas quando a feição nasce ou um campo que
  desenha muda, na camada em edição.

A ideia da assinatura é a de layers/bitmap-drawing-signature.js do Web (assinatura igual,
pixels iguais), com uma diferença deliberada: aqui entra a lista FECHADA dos campos que o
gerador lê (e não "tudo menos uma lista de exclusão"), porque a assinatura tem de caber numa
expressão do estilo que o QGIS avalia sem o plugin. A versão do bundle não entra: regerar
depois de atualizar o motor é ação explícita (regenerar_camada).
"""
import base64
import hashlib
import json

from . import schema

TIPOS_SVG = ('military_symbol', 'coordination_measure', 'engineering_symbol', 'magnetic_declination')

# Versão do formato da assinatura: muda se a lista ou a escrita dos campos mudar.
VERSAO_ASSINATURA = 'a1'

# Campos que o gerador de cada tipo lê, na ordem em que entram na assinatura.
CAMPOS_DESENHO = {
    'military_symbol': ['sidc'] + [c for c, _w in schema.AMPLIFICADORES] + ['fill_color'],
    'coordination_measure': ['point_code', 'echelon_code'] + [c for c, _w in schema.TEXTOS_MEDIDA] + ['fill_color'],
    'engineering_symbol': ['point_code', 'engineering', 'fill_color'],
    'magnetic_declination': ['declination', 'convergence', 'fill_color'],
}

# Colunas que o renderizador escreve; mudança nelas nunca dispara regeneração.
COLUNAS_SAIDA = ('svg', 'svg_assinatura', 'largura_px', 'altura_px', 'ancora_dx', 'ancora_dy')


def _tipo_coluna(tipo, coluna):
    for nome, tp, _padrao, _web in schema.campos(tipo):
        if nome == coluna:
            return tp
    raise KeyError('{}.{}'.format(tipo, coluna))


def _vazio(valor):
    if valor is None:
        return True
    try:  # QVariant nulo do PyQt5 (QGIS 3)
        from qgis.PyQt.QtCore import QVariant
        if isinstance(valor, QVariant):
            return valor.isNull()
    except ImportError:  # pragma: no cover
        pass
    return False


# ---------------------------------------------------------------------------------------------
# Atributos -> propriedades do Web
# ---------------------------------------------------------------------------------------------

def _valor_web(tp, valor):
    if _vazio(valor):
        return None
    if tp == 'bool':
        return bool(valor)
    if tp == 'real':
        return float(valor)
    if tp == 'int':
        return int(valor)
    if tp == 'json':
        if isinstance(valor, str):
            try:
                return json.loads(valor) if valor.strip() else None
            except ValueError:
                return None
        return valor
    return valor if isinstance(valor, str) else str(valor)


def props_web_de_atributos(tipo, atributos):
    """
    Propriedades com os nomes do Web a partir das colunas (schema.mapa_web). Só entram as
    colunas que vêm do Web; nulos ficam de fora, como propriedade ausente.
    """
    props = {}
    for web, coluna in schema.mapa_web(tipo).items():
        if coluna not in atributos:
            continue
        v = _valor_web(_tipo_coluna(tipo, coluna), atributos[coluna])
        if v is not None:
            props[web] = v
    return props


# ---------------------------------------------------------------------------------------------
# Assinatura
# ---------------------------------------------------------------------------------------------

def _real_como_qgis(valor):
    # to_string() do QGIS escreve o double mais curto que o reconstrói, sem ".0" final e com
    # zero sem sinal; o repr do Python dá os mesmos dígitos (medido em 8 valores, test_estilos).
    v = float(valor)
    if v == 0:
        return '0'
    s = repr(v)
    return s[:-2] if s.endswith('.0') else s


def _texto_assinatura(tp, valor):
    if _vazio(valor):
        return ''
    if tp == 'bool':
        return '1' if valor else '0'
    if tp == 'real':
        return _real_como_qgis(valor)
    if tp == 'json':
        return _json_canonico(valor)
    return valor if isinstance(valor, str) else str(valor)


def _json_canonico(valor):
    """
    JSON como o to_json() do QGIS escreve a coluna JSON lida do GeoPackage: compacto, chaves em
    ordem, sem escapar acento. O texto gravado na coluna pode ter outro espaçamento ou ordem
    (json.dumps do importador), e compará-lo cru com o to_json acendia o aviso de SVG velho em
    todo símbolo de engenharia importado.
    """
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            return valor
    return json.dumps(_inteiros(valor), ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _inteiros(v):
    """O to_json do QGIS escreve 1.0 como 1; o json do Python escreveria 1.0."""
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, dict):
        return {k: _inteiros(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_inteiros(x) for x in v]
    return v


def texto_assinatura(tipo, atributos):
    """O texto que vai para o md5, exposto para teste e depuração."""
    partes = [VERSAO_ASSINATURA, tipo]
    for coluna in CAMPOS_DESENHO[tipo]:
        partes.append(_texto_assinatura(_tipo_coluna(tipo, coluna), atributos.get(coluna)))
    return '|'.join(partes)


def assinatura(tipo, atributos):
    """md5 dos campos que desenham; a expressao_assinatura(tipo) dá o mesmo valor no QGIS."""
    return hashlib.md5(texto_assinatura(tipo, atributos).encode('utf-8')).hexdigest()


def _termo_expressao(tp, coluna):
    c = '"{}"'.format(coluna)
    if tp == 'bool':
        return "if({}, '1', '0')".format(c)
    if tp == 'real':
        return "coalesce(to_string({}), '')".format(c)
    if tp == 'json':
        # a coluna JSON chega como texto ou como mapa conforme a camada; to_json(texto) dá nulo
        return "coalesce(to_json(from_json({c})), to_json({c}), '')".format(c=c)
    return "coalesce(to_string({}), '')".format(c)


def expressao_assinatura(tipo):
    """Expressão nativa do QGIS que reproduz assinatura(tipo, atributos) por feição."""
    termos = ["'{}|{}'".format(VERSAO_ASSINATURA, tipo)]
    for coluna in CAMPOS_DESENHO[tipo]:
        termos.append(_termo_expressao(_tipo_coluna(tipo, coluna), coluna))
    return 'md5(' + " || '|' || ".join(termos) + ')'


# ---------------------------------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------------------------------

def _b64(svg):
    return base64.b64encode(svg.encode('utf-8')).decode('ascii')


def gerar_desenho(tipo, atributos):
    """Resultado bruto do gerador (svg, svgWeb, largura, altura, ancoraX, ancoraY, valido...)."""
    props = props_web_de_atributos(tipo, atributos)
    if tipo == 'magnetic_declination':
        from .motor import declinacao
        return declinacao.renderizar(props.get('declination') or 0.0, props.get('convergence') or 0.0,
                                     props.get('fillColor'))
    from .motor.motor import Motor
    motor = Motor.instancia()
    if tipo == 'military_symbol':
        return motor.simbolo_militar(props)
    if tipo == 'coordination_measure':
        return motor.medida(props)
    if tipo == 'engineering_symbol':
        return motor.engenharia(props)
    raise ValueError('Tipo sem desenho SVG: {}'.format(tipo))


def renderizar(tipo, atributos, detalhes=False):
    """
    Colunas de desenho para gravar na feição. Com detalhes=True devolve (colunas, resultado),
    em que resultado traz valido e avisos do gerador.
    """
    r = gerar_desenho(tipo, atributos)
    colunas = {
        'svg': _b64(r['svg']),
        'svg_assinatura': assinatura(tipo, atributos),
        'largura_px': float(r['largura']),
        'altura_px': float(r['altura']),
        'ancora_dx': float(r['ancoraX']),
        'ancora_dy': float(r['ancoraY']),
    }
    return (colunas, r) if detalhes else colunas


def deslocamento_do_centro(anchor, icon_offset, largura, altura):
    """
    Deslocamento do CENTRO do desenho em relação ao ponto, em px lógicos (direita e baixo
    positivos): o icon-offset do MapLibre mais a distância do centro ao ponto que o
    icon-anchor põe na coordenada. É a mesma regra de gerarMedida no bundle.
    """
    dx, dy = (float(icon_offset[0]), float(icon_offset[1])) if icon_offset else (0.0, 0.0)
    a = anchor or 'center'
    if 'bottom' in a:
        dy -= altura / 2
    if 'top' in a:
        dy += altura / 2
    if 'left' in a:
        dx += largura / 2
    if 'right' in a:
        dx -= largura / 2
    return round(dx, 2) + 0.0, round(dy, 2) + 0.0


def _icon_offset_de(valor):
    if _vazio(valor) or valor in ('', None):
        return None
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            return None
    if isinstance(valor, (list, tuple)) and len(valor) == 2:
        return [float(valor[0]), float(valor[1])]
    return None


def colunas_do_bitmap_web(tipo, props, png_b64, png_largura=None, png_altura=None, mime='image/png'):
    """
    Colunas do caminho RASTER para um símbolo que veio de um .ebgeo com o PNG gerado pelo Web.

    O tamanho lógico é o do Web (props width e height; sem eles, pixels do PNG divididos por
    props pixelRatio, que vale 1 quando ausente). A posição vem de props iconOffset e anchor.
    Símbolo militar de bitmapVersion menor que 3 não tem iconOffset (o Web passou a ancorar no
    milsymbol na versão 3 e regenera os antigos ao abrir): aí a âncora sai do motor, do mesmo
    SIDC, escalada para o tamanho do PNG, para o raster cair onde o Web de hoje o desenha.

    Para os tipos que o motor desenha (militar, medida, declinação), o importador deve gravar
    TAMBÉM o svg (renderizar): o Web redesenha ao abrir todo bitmap com bitmapVersion menor
    que 4, e um PNG de gerador antigo pode ser outro desenho (medido na fixture 03: um símbolo
    com amplificadores de texto tem 475 px lógicos no PNG e 443 no gerador atual). O raster
    fica como reserva.
    """
    razao = float(props.get('pixelRatio') or 1)
    largura = props.get('width') or (png_largura / razao if png_largura else None)
    altura = props.get('height') or (png_altura / razao if png_altura else None)
    if not largura or not altura:
        raise ValueError('Bitmap sem tamanho: informe width/height ou o tamanho do PNG')
    largura, altura = float(largura), float(altura)
    offset = _icon_offset_de(props.get('iconOffset'))
    if offset is None and tipo == 'military_symbol' and props.get('sidc'):
        try:
            r = gerar_desenho(tipo, {c: props.get(w) for w, c in schema.mapa_web(tipo).items()})
            if r.get('iconOffset'):
                offset = [r['iconOffset'][0] * largura / r['largura'], r['iconOffset'][1] * altura / r['altura']]
        except Exception:  # sem motor: fica o centro, como o Web antes da versão 3
            offset = None
    anchor = props.get('anchor') if tipo != 'military_symbol' else 'center'
    dx, dy = deslocamento_do_centro(anchor, offset, largura, altura)
    return {'bitmap_b64': png_b64, 'bitmap_mime': mime, 'largura_px': largura, 'altura_px': altura,
            'ancora_dx': dx, 'ancora_dy': dy}


def svg_de_coluna(valor):
    """Decodifica o conteúdo da coluna svg (base64) de volta ao texto do SVG."""
    if _vazio(valor) or not valor:
        return None
    return base64.b64decode(valor).decode('utf-8')


# ---------------------------------------------------------------------------------------------
# Regeneração por sinal
# ---------------------------------------------------------------------------------------------

try:
    from qgis.PyQt.QtCore import QObject, QTimer
    from qgis.core import Qgis, QgsMessageLog
except ImportError:  # pragma: no cover - uso sem QGIS (schema e assinatura continuam testáveis)
    QObject = object
    QTimer = None


class RegeneradorSvg(QObject):
    """
    Mantém svg, svg_assinatura, largura_px, altura_px, ancora_dx e ancora_dy em dia na camada
    em edição. Os sinais só ANOTAM a feição; a regeneração roda depois, num único passe por
    volta do laço de eventos, e por isso uma edição em lote (calculadora de campo, colar 500
    feições) vira um passe só. Antes do commit, o que ficou pendente é processado.

    A recursão é cortada em dois pontos: mudança em coluna de saída nunca anota, e durante a
    própria gravação os sinais são ignorados. A gravação usa changeAttributeValues, que entra
    na pilha de desfazer como uma edição comum; desfazer o SIDC regenera de novo pelo sinal.
    """

    def __init__(self, layer, tipo, parent=None):
        super().__init__(parent or layer)
        if tipo not in TIPOS_SVG:
            raise ValueError('Tipo sem desenho SVG: {}'.format(tipo))
        self.layer = layer
        self.tipo = tipo
        self._pendentes = set()
        self._gravando = False
        self._agendado = False
        self.erros = []
        self.regeneradas = 0
        nomes = layer.fields().names()
        self._idx_desenho = {layer.fields().indexOf(c) for c in CAMPOS_DESENHO[tipo] if c in nomes}
        self._idx_saida = {c: layer.fields().indexOf(c) for c in COLUNAS_SAIDA if c in nomes}
        layer.featureAdded.connect(self._ao_adicionar)
        layer.attributeValueChanged.connect(self._ao_mudar_atributo)
        layer.beforeCommitChanges.connect(self.processar)

    def desconectar(self):
        for sinal, slot in ((self.layer.featureAdded, self._ao_adicionar),
                            (self.layer.attributeValueChanged, self._ao_mudar_atributo),
                            (self.layer.beforeCommitChanges, self.processar)):
            try:
                sinal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    def _anotar(self, fid):
        if self._gravando:
            return
        self._pendentes.add(fid)
        if QTimer is not None and not self._agendado:
            self._agendado = True
            QTimer.singleShot(0, self.processar)

    def _ao_adicionar(self, fid):
        self._anotar(fid)

    def _ao_mudar_atributo(self, fid, idx, _valor):
        if idx in self._idx_desenho:
            self._anotar(fid)

    def processar(self, *_args):
        """Regenera as feições anotadas. Devolve quantas foram regravadas."""
        self._agendado = False
        if not self._pendentes or not self.layer.isEditable():
            self._pendentes.clear()
            return 0
        pendentes, self._pendentes = self._pendentes, set()
        feitas = 0
        for fid in sorted(pendentes):
            f = self.layer.getFeature(fid)
            if not f.isValid():
                continue
            if self.regenerar_feicao(f):
                feitas += 1
        self.regeneradas += feitas
        return feitas

    def regenerar_feicao(self, feicao, forcar=False):
        atributos = {n: feicao[n] for n in feicao.fields().names()}
        nova = assinatura(self.tipo, atributos)
        if not forcar and atributos.get('svg_assinatura') == nova and not _vazio(atributos.get('svg')):
            return False
        try:
            colunas = renderizar(self.tipo, atributos)
        except Exception as erro:  # o motor rejeitou (SIDC inválido etc.): o aviso do estilo fica
            self.erros.append((feicao.id(), str(erro)))
            try:
                QgsMessageLog.logMessage('Símbolo não regenerado (fid {}): {}'.format(feicao.id(), erro),
                                         'EBGeo', Qgis.MessageLevel.Warning)
            except Exception:  # pragma: no cover
                pass
            return False
        valores = {self._idx_saida[c]: v for c, v in colunas.items() if c in self._idx_saida}
        self._gravando = True
        try:
            ok = self.layer.changeAttributeValues(feicao.id(), valores)
        finally:
            self._gravando = False
        return bool(ok)

    def regenerar_camada(self, forcar=True):
        """Regenera todas as feições da camada em edição (depois de atualizar o motor)."""
        feitas = 0
        for f in self.layer.getFeatures():
            if self.regenerar_feicao(f, forcar=forcar):
                feitas += 1
        self.regeneradas += feitas
        return feitas
