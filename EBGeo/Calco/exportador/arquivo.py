# -*- coding: utf-8 -*-
"""
Gravação e conferência do arquivo .ebgeo, em Python puro.

O contêiner é o do exportador do Web (export-import.service.js, handleExport): ZIP com
data.json e images/<id>.<ext>, cada byte do ZIP com XOR 0xAA, atrás do cabeçalho em claro
EBGXOR. A extensão vem do MIME farejado dos bytes (getBlobExtension do Web).
"""
import io
import json
import os
import tempfile
import zipfile

from ..importador import leitor
from .montador import EXTENSAO, ErroExportacao

_XOR = bytes(i ^ leitor.CHAVE_XOR for i in range(256))


def bytes_ebgeo(data, imagens):
    """O .ebgeo em bytes: ZIP (DEFLATE nível 9) mascarado, com o cabeçalho."""
    try:
        texto = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    except ValueError as e:
        raise ErroExportacao('O documento tem um número inválido (NaN ou infinito) e o Web o recusaria: {}'.format(e))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr('data.json', texto.encode('utf-8'))
        for ident, (b, mime) in imagens.items():
            z.writestr('images/{}.{}'.format(ident, EXTENSAO.get(mime, 'png')), b)
    return leitor.CABECALHO + buf.getvalue().translate(_XOR)


def gravar(caminho, data, imagens):
    """Grava o .ebgeo por arquivo temporário e troca no fim (um arquivo pela metade não fica)."""
    raw = bytes_ebgeo(data, imagens)
    pasta = os.path.dirname(os.path.abspath(caminho)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.ebgeo_', suffix='.tmp', dir=pasta)
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(raw)
        os.replace(tmp, caminho)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise ErroExportacao('Não foi possível gravar {}: {}'.format(caminho, e))
    return len(raw)


def conferir(caminho, data, imagens):
    """
    Relê o arquivo GRAVADO pelo leitor do importador (o mesmo portão de versão e estrutura do
    Web) e compara com o que se quis gravar: o data.json inteiro e os bytes de cada imagem.
    Devolve a lista de divergências (vazia = conferido).
    """
    try:
        doc = leitor.abrir(caminho)
    except leitor.ErroEbgeo as e:
        return ['o arquivo gravado não abre: {}'.format(e)]
    erros = []
    if doc.data != json.loads(json.dumps(data, ensure_ascii=False)):
        erros.append('o data.json relido difere do montado')
    if set(doc.imagens) != set(imagens):
        faltam = sorted(set(imagens) - set(doc.imagens))
        sobram = sorted(set(doc.imagens) - set(imagens))
        erros.append('imagens: {} faltando, {} sobrando'.format(len(faltam), len(sobram)))
    for ident, (b, _mime) in imagens.items():
        if ident in doc.imagens and doc.imagens[ident][0] != b:
            erros.append('imagem {} com bytes diferentes'.format(ident))
    return erros
