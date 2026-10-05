# -*- coding: utf-8 -*-
"""
Aba Fotos do formulário de feição: as fotos e imagens que o EBGeo Web anexa a uma feição
(properties.images), que o importador grava na tabela `ebgeo_foto` do GeoPackage, ligadas pelo
`ebgeo_id` (schema.TABELAS_APOIO).

Peça reutilizável por qualquer tipo: `aba_fotos()` devolve a Aba da especificação, e os dois
consumidores a montam assim:

  - formulário nativo (sem código): um elemento de TEXTO com expressão, que lista as miniaturas e
    os nomes das fotos da feição lidas da tabela `ebgeo_foto` do MESMO GeoPackage carregada no
    projeto (achada pelo caminho do arquivo, com qualquer nome de camada: "Fotos anexas" no
    importador, "ebgeo_foto" quando o operador abre a tabela à mão). A aba só aparece quando há
    foto. Sem relação do projeto: a relação gravada no estilo (relação fraca) só volta quando a
    tabela de fotos é aberta antes da camada (aberta depois, a relação não se forma; aberta
    antes, o QGIS ainda carrega uma segunda cópia da camada pelo nome gravado) e guarda o caminho
    absoluto do arquivo, e o elemento HTML não avaliou a expressão com @layers (medido no QGIS
    4.0.0 sem o plugin, 2026-10-05); o elemento de texto avalia e desenha a imagem `data:`;
  - dock do plugin (ui/blocos/comuns.py): lê as fotos direto do GeoPackage (`fotos_da_feicao`),
    mostra a miniatura e abre a foto no visualizador do sistema, sem apagar nada.

Este módulo não importa QGIS.
"""
import base64
import os
import sqlite3
from dataclasses import dataclass

from . import especificacao as esp

TABELA = 'ebgeo_foto'
NOME_ABA = 'Fotos'
LARGURA_MINIATURA = 120

# A camada da tabela de fotos do mesmo GeoPackage da camada do formulário, ou nulo.
EXPRESSAO_CAMADA = (
    "array_first(array_filter(@layers, layer_property(@element, 'path') = layer_property(@layer, 'path') "
    "AND regexp_match(layer_property(@element, 'source'), 'layername={}([|]|$)') > 0))".format(TABELA))
_FILTRO = "\"ebgeo_id\" = attribute(@parent, 'ebgeo_id')"
_CONTAGEM = "coalesce(aggregate(layer_property(@fotos, 'id'), 'count', \"fid\", {}), 0)".format(_FILTRO)


def _linha_html():
    """A linha da tabela HTML de uma foto: miniatura (ou a foto, sem miniatura) e o nome."""
    return ("'<tr><td><img width=\"{w}\" src=\"data:' || coalesce(\"mime\", 'image/png') || ';base64,' || "
            "coalesce(\"miniatura_b64\", \"bitmap_b64\", '') || '\"/></td><td>' || "
            "replace(coalesce(\"nome\", ''), '<', '&lt;') || '</td></tr>'").format(w=LARGURA_MINIATURA)


EXPRESSAO_LISTA = (
    "[% with_variable('fotos', " + EXPRESSAO_CAMADA + ", if(@fotos IS NULL, '', "
    "'<p>' || " + _CONTAGEM + " || ' foto(s) anexa(s) à feição no EBGeo Web.</p><table>' || "
    "coalesce(aggregate(layer_property(@fotos, 'id'), 'concatenate', " + _linha_html() + ", " + _FILTRO + ", "
    "concatenator:='', order_by:=\"fid\"), '') || '</table>')) %]")


@dataclass(frozen=True)
class TemFotos:
    """
    A feição tem foto anexa na tabela de fotos do mesmo GeoPackage carregada no projeto. Em
    Python (testes), `avaliar` lê a contagem na chave CHAVE_CONTAGEM dos atributos.
    """
    CHAVE_CONTAGEM = '__fotos__'

    def expressao(self):
        return "with_variable('fotos', {}, @fotos IS NOT NULL AND {} > 0)".format(EXPRESSAO_CAMADA, _CONTAGEM)

    def avaliar(self, atributos):
        return bool(atributos.get(self.CHAVE_CONTAGEM))


@dataclass
class TextoFotos(esp.Texto):
    """O Texto da lista de fotos: o nativo avalia a expressão; o dock troca-o pelo bloco rico."""
    rico: str = 'fotos'


def aba_fotos():
    return esp.Aba(NOME_ABA, [TextoFotos('fotos_anexas', EXPRESSAO_LISTA)], condicao=TemFotos())


# ---------------------------------------------------------------------------------------------
# Leitura direta do GeoPackage (dock)
# ---------------------------------------------------------------------------------------------

EXTENSAO = {'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/png': '.png', 'image/gif': '.gif',
            'image/webp': '.webp', 'image/bmp': '.bmp', 'image/svg+xml': '.svg', 'image/tiff': '.tif'}


def caminho_do_gpkg(fonte):
    """O arquivo da fonte OGR de uma camada ('arquivo.gpkg|layername=...')."""
    return (fonte or '').split('|')[0]


def fotos_da_feicao(caminho, ebgeo_id):
    """
    [{'foto_id', 'nome', 'mime', 'bitmap_b64', 'miniatura_b64'}] da feição, na ordem de gravação;
    lista vazia quando o arquivo não tem a tabela de fotos ou a feição não tem foto. Só lê.
    """
    if not ebgeo_id or not caminho or not os.path.isfile(caminho):
        return []
    try:
        con = sqlite3.connect('file:{}?mode=ro'.format(caminho.replace('\\', '/')), uri=True)
    except sqlite3.Error:
        return []
    try:
        if con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABELA,)).fetchone() is None:
            return []
        linhas = con.execute('SELECT foto_id, nome, mime, bitmap_b64, miniatura_b64 FROM "{}" '
                             'WHERE ebgeo_id = ? ORDER BY fid'.format(TABELA), (str(ebgeo_id),)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [dict(zip(('foto_id', 'nome', 'mime', 'bitmap_b64', 'miniatura_b64'), l)) for l in linhas]


def bytes_da_foto(foto, miniatura=False):
    """Os bytes da foto (ou da miniatura, que cai na foto quando falta), ou None."""
    b64 = (foto.get('miniatura_b64') if miniatura else None) or foto.get('bitmap_b64')
    if not b64:
        return None
    try:
        return base64.b64decode(b64)
    except (ValueError, TypeError):
        return None


def nome_de_arquivo(foto):
    """Nome de arquivo seguro para abrir a foto: o nome do Web, com a extensão do tipo quando falta."""
    nome = os.path.basename(str(foto.get('nome') or foto.get('foto_id') or 'foto'))
    nome = ''.join(c for c in nome if c not in '<>:"/\\|?*').strip() or 'foto'
    ext = EXTENSAO.get(str(foto.get('mime') or '').lower(), '')
    if ext and not nome.lower().endswith(ext) and os.path.splitext(nome)[1] == '':
        nome += ext
    return nome
