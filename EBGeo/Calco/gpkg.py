# -*- coding: utf-8 -*-
"""
Criação e abertura do GeoPackage do calco, só com GDAL/OGR (sem QGIS),
a partir do esquema em schema.py.
"""
import os

from osgeo import ogr, osr

from . import schema

ogr.UseExceptions()

_OGR_TIPO = {
    'str': (ogr.OFTString, None),
    'json': (ogr.OFTString, ogr.OFSTJSON),
    'real': (ogr.OFTReal, None),
    'int': (ogr.OFTInteger, None),
    'bool': (ogr.OFTInteger, ogr.OFSTBoolean),
    'datetime': (ogr.OFTDateTime, None),
}

_OGR_GEOM = {
    'Point': ogr.wkbPoint,
    'LineString': ogr.wkbLineString,
    'MultiLineString': ogr.wkbMultiLineString,
    'MultiPolygon': ogr.wkbMultiPolygon,
}


def _campo_ogr(nome, tipo, padrao=None):
    t, sub = _OGR_TIPO[tipo]
    fd = ogr.FieldDefn(nome, t)
    if sub is not None:
        fd.SetSubType(sub)
    if padrao is not None and tipo != 'json':
        if tipo == 'bool':
            fd.SetDefault('1' if padrao else '0')
        elif tipo == 'str':
            fd.SetDefault("'" + str(padrao).replace("'", "''") + "'")
        else:
            fd.SetDefault(str(padrao))
    return fd


def _srs():
    s = osr.SpatialReference()
    s.ImportFromEPSG(4326)
    s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return s


def abrir_ou_criar(caminho):
    """Abre o GeoPackage para escrita, criando-o se não existir."""
    if os.path.exists(caminho):
        return ogr.Open(caminho, 1)
    drv = ogr.GetDriverByName('GPKG')
    return drv.CreateDataSource(caminho)


def garantir_tabela_tipo(ds, tipo):
    """Cria a tabela do tipo se faltar; acrescenta colunas que faltarem. Devolve a camada OGR."""
    d = schema.TIPOS[tipo]
    lyr = ds.GetLayerByName(d['tabela'])
    if lyr is None:
        lyr = ds.CreateLayer(d['tabela'], _srs(), _OGR_GEOM[d['geometria']],
                             options=['GEOMETRY_NAME=geom', 'FID=fid', 'SPATIAL_INDEX=YES'])
    existentes = {lyr.GetLayerDefn().GetFieldDefn(i).GetName()
                  for i in range(lyr.GetLayerDefn().GetFieldCount())}
    for nome, tp, padrao, _web in schema.campos(tipo):
        if nome not in existentes:
            lyr.CreateField(_campo_ogr(nome, tp, padrao))
    _comentarios(lyr, tipo)
    return lyr


def _comentarios(lyr, tipo):
    """
    A dica de cada campo (a do Web, formulario/especificacao.dicas) como comentário da coluna: o
    formulário nativo a mostra no rótulo, sem código e sem o plugin (medido no QGIS 4.0.0; o
    GeoPackage a guarda em gpkg_data_columns). Coluna já com a dica fica como está.
    """
    try:
        from .formulario.especificacao import dicas
        por_coluna = dicas(tipo)
    except Exception:  # especificação indisponível: a tabela segue sem dicas
        return
    defn = lyr.GetLayerDefn()
    for coluna, dica in por_coluna.items():
        i = defn.GetFieldIndex(coluna)
        if i < 0 or not hasattr(ogr, 'ALTER_COMMENT_FLAG'):
            continue
        atual = defn.GetFieldDefn(i)
        if atual.GetComment() == dica:
            continue
        fd = ogr.FieldDefn(atual.GetName(), atual.GetType())
        fd.SetComment(dica)
        lyr.AlterFieldDefn(i, fd, ogr.ALTER_COMMENT_FLAG)


def garantir_tabela_apoio(ds, nome):
    lyr = ds.GetLayerByName(nome)
    if lyr is None:
        lyr = ds.CreateLayer(nome, geom_type=ogr.wkbNone, options=['FID=fid'])
    existentes = {lyr.GetLayerDefn().GetFieldDefn(i).GetName()
                  for i in range(lyr.GetLayerDefn().GetFieldCount())}
    for col, tp in schema.TABELAS_APOIO[nome]:
        if col not in existentes:
            lyr.CreateField(_campo_ogr(col, tp))
    return lyr


def criar_calco(caminho, tipos=None, apoio=True):
    """
    Cria (ou completa) um calco com as tabelas dos tipos pedidos.
    tipos=None cria as tabelas dos tipos militares.
    """
    tipos = list(tipos) if tipos is not None else list(schema.TIPOS_MILITARES)
    ds = abrir_ou_criar(caminho)
    for t in tipos:
        garantir_tabela_tipo(ds, t)
    if apoio:
        for nome in schema.TABELAS_APOIO:
            garantir_tabela_apoio(ds, nome)
    ds.FlushCache()
    ds = None
    return caminho


def tabelas_presentes(caminho):
    ds = ogr.Open(caminho)
    try:
        return [ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())]
    finally:
        ds = None


def uri_camada(caminho, tipo, mapa=None, camada_id=None):
    """URI do provedor ogr do QGIS para a tabela do tipo, com filtro opcional."""
    uri = '{}|layername={}'.format(caminho, schema.TIPOS[tipo]['tabela'])
    filtros = []
    if mapa is not None:
        filtros.append('"mapa" = \'{}\''.format(mapa.replace("'", "''")))
    if camada_id is not None:
        filtros.append('"camada_id" = \'{}\''.format(camada_id.replace("'", "''")))
    if filtros:
        uri += '|subset=' + ' AND '.join(filtros)
    return uri
