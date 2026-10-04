# -*- coding: utf-8 -*-
"""
Leitor do arquivo .ebgeo do EBGeo Web, em Python puro (sem QGIS).

O .ebgeo é um ZIP com data.json e uma pasta images/, mascarado por XOR 0xAA
atrás do cabeçalho em claro EBGXOR (o ZIP puro também é aceito). Este módulo
abre, valida e normaliza o documento como o próprio Web faz ao importar
(frontend/src/js/import_export/ebgeo-file-gate.js e
store/repository.utils.js, ensureMapDataShape). Não grava nada.

Regras que valem para todo o importador:
- o BALDE decide o tipo da feição, nunca properties.source (processed_los
  traz source "los");
- a identidade da feição é properties.id; o id de topo é ignorado;
- seções fora do recorte (360, 3D, briefing, temporal, comentários) não são
  interpretadas, mas o data.json inteiro segue no Documento.texto_json.
"""
import hashlib
import io
import json
import logging
import os
import re
import zipfile

from .. import schema

CABECALHO = b'EBGXOR'
CHAVE_XOR = 0xAA
VERSAO_RE = re.compile(r'^\d+\.\d+(\.\d+)?$')
VERSAO_MIN = '1.3'
VERSAO_MAX = '3.0'
# Proteção contra bomba de ZIP: soma dos tamanhos descompactados declarados.
TETO_DESCOMPACTADO = 512 * 2 ** 20
TETO_ARQUIVO = 1024 * 2 ** 20
IMAGEM_RE = re.compile(r'^images/([^/]+)\.(png|jpe?g|svg|webp)$', re.IGNORECASE)

BALDES_IGNORADOS = {'coordenadas'}
BALDE_LEGADO_BARREIRA = 'barrier_lines'
# Padrões da Linha de Coordenação para a Linha de Barreira da 2.2
# (COORDINATION_LINE_FALLBACKS em repository.utils.js).
PADROES_BARREIRA = {
    'symbol_code': '290199',
    'symbol_size': 0.5,
    'symbol_spacing': 1.5,
    'createdAtZoom': 0,
    'zoomCorrectionEnabled': True,
}
# normalizeLegacyDeclinationProperties: aliases e tela inicial da ferramenta.
ALIASES_DECLINACAO = (('declinacao', 'declination'), ('convergencia', 'convergence'))
PADROES_DECLINACAO = {'width': 400, 'height': 500, 'size': 0.6, 'opacity': 1}

CAMADA_PADRAO = {'id': 'default', 'name': 'Padrão', 'visible': True, 'locked': False,
                 'opacity': 1, 'order': 0}

_log = logging.getLogger('EBGeo.Calco.importador')


class ErroEbgeo(Exception):
    """Arquivo .ebgeo recusado. A mensagem é a que o operador lê."""


class Documento:
    """O .ebgeo aberto: data.json interpretado, texto original e imagens do ZIP."""

    def __init__(self, arquivo, sha256, data, texto_json, imagens, avisos):
        self.arquivo = arquivo          # nome do arquivo de origem (sem pasta)
        self.sha256 = sha256            # do arquivo inteiro, como está no disco
        self.data = data                # data.json interpretado
        self.texto_json = texto_json    # data.json original, para preservar
        self.imagens = imagens          # id -> (bytes, mime farejado)
        self.avisos = avisos            # mensagens não fatais da abertura

    @property
    def versao(self):
        return self.data.get('version')


def _tupla_versao(v):
    partes = [int(x) for x in v.split('.')]
    return tuple(partes + [0] * (3 - len(partes)))


def farejar_mime(b):
    """MIME pelos bytes mágicos; a extensão engana (JPEG gravado como .png antes de 2026-08-24)."""
    if b[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if b[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if b[:4] == b'RIFF' and b[8:12] == b'WEBP':
        return 'image/webp'
    inicio = b[:256].lstrip().lower()
    if inicio.startswith(b'<svg') or (inicio.startswith(b'<?xml') and b'<svg' in b[:2048].lower()):
        return 'image/svg+xml'
    return None


_MIME_EXT = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
             'svg': 'image/svg+xml', 'webp': 'image/webp'}


def desmascarar(raw):
    """Tira o cabeçalho EBGXOR e o XOR do corpo; ZIP puro passa intacto."""
    if raw[:len(CABECALHO)] == CABECALHO:
        return bytes(b ^ CHAVE_XOR for b in raw[len(CABECALHO):])
    return raw


def abrir(caminho):
    """Abre e valida o .ebgeo. Devolve um Documento ou levanta ErroEbgeo."""
    nome = os.path.basename(caminho)
    try:
        tamanho = os.path.getsize(caminho)
    except OSError as e:
        raise ErroEbgeo('Não foi possível ler o arquivo {}: {}'.format(nome, e))
    if tamanho > TETO_ARQUIVO:
        raise ErroEbgeo('O arquivo {} tem {:.0f} MB, acima do limite de {:.0f} MB do importador.'.format(
            nome, tamanho / 2 ** 20, TETO_ARQUIVO / 2 ** 20))
    with open(caminho, 'rb') as fh:
        raw = fh.read()
    return abrir_bytes(raw, nome)


def abrir_bytes(raw, nome='arquivo.ebgeo'):
    sha = hashlib.sha256(raw).hexdigest()
    corpo = desmascarar(raw)
    try:
        z = zipfile.ZipFile(io.BytesIO(corpo))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError) as e:
        raise ErroEbgeo(
            'O arquivo {} não é um .ebgeo válido ou está corrompido (talvez truncado). '
            'Exporte-o de novo no EBGeo Web. Detalhe: {}'.format(nome, e))

    with z:
        infos = z.infolist()
        total = sum(i.file_size for i in infos)
        if total > TETO_DESCOMPACTADO:
            raise ErroEbgeo(
                'O arquivo {} descompactado teria {:.0f} MB, acima do limite de {:.0f} MB. '
                'O importador recusou para não esgotar a memória.'.format(
                    nome, total / 2 ** 20, TETO_DESCOMPACTADO / 2 ** 20))
        try:
            ruim = z.testzip()
        except (zipfile.BadZipFile, EOFError, OSError, ValueError) as e:
            raise ErroEbgeo('O arquivo {} está corrompido (falha ao descompactar): {}'.format(nome, e))
        if ruim is not None:
            raise ErroEbgeo('O arquivo {} está corrompido: o conteúdo de "{}" não confere com o CRC.'.format(
                nome, ruim))

        nomes = z.namelist()
        if 'data.json' not in nomes:
            raise ErroEbgeo('Arquivo data.json não encontrado no .ebgeo ({}).'.format(nome))

        avisos = []
        imagens = {}
        for n in nomes:
            if n.endswith('/'):
                continue
            m = IMAGEM_RE.match(n)
            if not m:
                continue
            ident, ext = m.group(1), m.group(2).lower()
            if ident in imagens:
                raise ErroEbgeo(
                    'Arquivo .ebgeo ambíguo: mais de uma imagem usa o ID {}.'.format(ident))
            b = z.read(n)
            mime = farejar_mime(b)
            if mime is None:
                mime = _MIME_EXT.get(ext, 'image/png')
                avisos.append('imagem {} sem assinatura reconhecida; assumido {}'.format(n, mime))
            elif mime != _MIME_EXT.get(ext):
                avisos.append('imagem {} é {} apesar da extensão .{}'.format(n, mime, ext))
            imagens[ident] = (b, mime)

        bruto = z.read('data.json')
    try:
        texto = bruto.decode('utf-8-sig')
        data = json.loads(texto)
    except (UnicodeDecodeError, ValueError) as e:
        raise ErroEbgeo('O data.json do arquivo {} é inválido: {}'.format(nome, e))
    if not isinstance(data, dict):
        raise ErroEbgeo('O data.json do arquivo {} não é um objeto JSON.'.format(nome))

    validar(data)
    return Documento(nome, sha, data, texto, imagens, avisos)


def validar(data):
    """Espelho de importVersionRefusal (ebgeo-file-gate.js). Levanta ErroEbgeo."""
    if not data.get('version'):
        raise ErroEbgeo('Arquivo .ebgeo sem informação de versão. '
                        'Use a versão mais recente do EBGeo Web para gerar o arquivo.')
    atlas = data.get('atlas') if isinstance(data.get('atlas'), dict) else {}
    for chave, v in (('version', data.get('version')), ('schemaVersion', data.get('schemaVersion')),
                     ('atlas.schemaVersion', atlas.get('schemaVersion'))):
        if v is None:
            continue
        if not isinstance(v, str) or not VERSAO_RE.match(v):
            raise ErroEbgeo('Arquivo .ebgeo com informação de versão inválida ({} = {!r}).'.format(chave, v))
        t = _tupla_versao(v)
        if t < _tupla_versao(VERSAO_MIN):
            raise ErroEbgeo('Arquivo .ebgeo incompatível. Versão do arquivo: {}, versão mínima aceita: {}.'.format(
                v, VERSAO_MIN))
        if t > _tupla_versao(VERSAO_MAX):
            raise ErroEbgeo(
                'Arquivo .ebgeo incompatível: versão {} é mais nova que o plugin (máxima aceita: {}). '
                'Atualize o EBGeo Desktop.'.format(v, VERSAO_MAX))

    def objeto(x):
        return isinstance(x, dict)

    if not objeto(data.get('maps')):
        raise ErroEbgeo('Arquivo .ebgeo inválido: a coleção de mapas está ausente ou corrompida.')
    for nome, mapa in data['maps'].items():
        if not objeto(mapa) or (mapa.get('features') is not None and not objeto(mapa.get('features'))):
            raise ErroEbgeo('Arquivo .ebgeo inválido: estrutura do mapa "{}" corrompida.'.format(nome))
        for lista in (mapa.get('features') or {}).values():
            if not isinstance(lista, list) or any(not objeto(f) for f in lista):
                raise ErroEbgeo('Arquivo .ebgeo inválido: coleção de feições do mapa "{}" corrompida.'.format(nome))
    for chave in ('layers', 'groups', 'mapNotes'):
        if data.get(chave) is not None and not objeto(data[chave]):
            raise ErroEbgeo('Arquivo .ebgeo inválido: seção {} corrompida.'.format(chave))
    for chave in ('customIcons', 'mapOrder'):
        if data.get(chave) is not None and not isinstance(data[chave], list):
            raise ErroEbgeo('Arquivo .ebgeo inválido: seção {} corrompida.'.format(chave))
    for camadas in (data.get('layers') or {}).values():
        if not isinstance(camadas, list) or any(not objeto(c) for c in camadas):
            raise ErroEbgeo('Arquivo .ebgeo inválido: camadas corrompidas.')
    for grupos in (data.get('groups') or {}).values():
        if not objeto(grupos) or any(not objeto(g) or (g.get('features') is not None and not isinstance(
                g.get('features'), list)) for g in grupos.values()):
            raise ErroEbgeo('Arquivo .ebgeo inválido: grupos corrompidos.')
    if any(not objeto(i) or not isinstance(i.get('id'), str) or not i.get('id')
           for i in data.get('customIcons') or []):
        raise ErroEbgeo('Arquivo .ebgeo inválido: ícones personalizados corrompidos.')


def _adotar_barreira(ft):
    """Linha de Barreira 2.2 vira Linha de Coordenação 290199 (adoptBarrierLine)."""
    p = dict(ft.get('properties') or {})
    p['source'] = 'coordination_line'
    for k, v in PADROES_BARREIRA.items():
        if p.get(k) is None:
            p[k] = v
    g = ft.get('geometry') or {}
    if p.get('baseCoordinates') is None and g.get('type') == 'LineString' and len(g.get('coordinates') or []) >= 2:
        p['baseCoordinates'] = [[c[0], c[1]] for c in g['coordinates']]
    novo = dict(ft)
    novo['properties'] = p
    return novo


def _normalizar_declinacao(ft):
    p = ft.get('properties')
    if not isinstance(p, dict):
        return ft
    if not any(_numero(p.get(old)) for old, _new in ALIASES_DECLINACAO):
        return ft
    p = dict(p)
    for old, new in ALIASES_DECLINACAO:
        if new not in p and _numero(p.get(old)):
            p[new] = p[old]
    for k, v in PADROES_DECLINACAO.items():
        p.setdefault(k, v)
    novo = dict(ft)
    novo['properties'] = p
    return novo


def _numero(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) != float('inf')


def normalizar_baldes(features, mapa='', log=None):
    """
    Baldes do mapa -> {tipo: [feição]}, no espelho de ensureMapDataShape.
    Balde desconhecido é ignorado com aviso; 'coordenadas' é efêmero e sai calado.
    """
    log = log or _log
    saida = {}
    for balde, lista in (features or {}).items():
        if balde in BALDES_IGNORADOS:
            continue
        if balde == BALDE_LEGADO_BARREIRA:
            adotadas = [_adotar_barreira(f) for f in lista or [] if isinstance(f, dict)]
            if adotadas:
                log.info('mapa "%s": %d Linha(s) de Barreira 2.2 adotada(s) como Linha de Coordenação 290199',
                         mapa, len(adotadas))
            saida.setdefault('coordination_line', []).extend(adotadas)
            continue
        tipo = schema.BALDE_PARA_TIPO.get(balde)
        if tipo is None:
            if lista:
                log.warning('mapa "%s": balde desconhecido "%s" com %d feição(ões) ignorado', mapa, balde, len(lista))
            continue
        if tipo == 'magnetic_declination':
            lista = [_normalizar_declinacao(f) for f in lista]
        # coordination_lines nativas vêm antes das adotadas, como no Web
        saida[tipo] = list(lista) + saida.get(tipo, [])
    return saida


def ordem_mapas(data):
    """mapOrder unido às chaves de maps (mapOrder pode vir vazio ou incompleto)."""
    mapas = data.get('maps') or {}
    vistos = []
    for n in data.get('mapOrder') or []:
        if isinstance(n, str) and n in mapas and n not in vistos:
            vistos.append(n)
    return vistos + [n for n in mapas if n not in vistos]


def mapa_atual(data):
    ordem = ordem_mapas(data)
    atual = data.get('currentMap')
    if isinstance(atual, str) and atual in (data.get('maps') or {}):
        return atual
    return ordem[0] if ordem else None


def camadas_do_mapa(data, mapa):
    """Camadas EBGeo do mapa; sem a lista (ou sem 'default'), a Padrão entra."""
    camadas = [dict(c) for c in ((data.get('layers') or {}).get(mapa) or []) if isinstance(c, dict)]
    if not any(c.get('id') == 'default' for c in camadas):
        padrao = dict(CAMADA_PADRAO)
        padrao['order'] = max([c.get('order', 0) or 0 for c in camadas] + [-1]) + 1 if camadas else 0
        camadas.append(padrao)
    return camadas


def iterar_feicoes(doc, log=None):
    """(mapa, tipo, feição) de todo o documento, na ordem dos mapas."""
    for nome in ordem_mapas(doc.data):
        m = doc.data['maps'][nome]
        for tipo, lista in normalizar_baldes(m.get('features'), nome, log).items():
            for ft in lista:
                yield nome, tipo, ft


def contar_por_tipo(doc):
    """{tipo: n} do arquivo, depois da normalização (para conferência)."""
    c = {}
    for _m, tipo, _f in iterar_feicoes(doc, logging.getLogger('silencioso')):
        c[tipo] = c.get(tipo, 0) + 1
    return c
