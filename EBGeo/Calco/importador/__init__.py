# -*- coding: utf-8 -*-
"""
Importador do arquivo .ebgeo (EBGeo Web) para o calco em GeoPackage.

- leitor: abre e valida o .ebgeo (Python puro);
- escritor: grava o GeoPackage por tipo (GDAL/OGR, sem QGIS);
- arvore: monta a árvore de camadas no projeto QGIS;
- algoritmo: o algoritmo de Processing "Importar arquivo .ebgeo".

Ver ANALISE_IMPORTACAO_EBGEO.md na raiz do repositório.
"""
