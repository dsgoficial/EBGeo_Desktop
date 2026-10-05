# -*- coding: utf-8 -*-
"""
Exportador do calco (GeoPackage) para o arquivo .ebgeo do EBGeo Web, o caminho de volta do
importador.

- montador: lê o GeoPackage e monta o data.json e as imagens (Python puro com OGR);
- arquivo: grava o .ebgeo (ZIP com data.json e images/, mascarado por XOR atrás de EBGXOR);
- desenho: a geometria desenhada da Seta e da Frente Ocupada pelo estilo do calco (QGIS);
- algoritmo: o algoritmo de Processing "Exportar arquivo .ebgeo".

Ver a seção 12 (Exportador .ebgeo) de EBGeo/Calco/ARQUITETURA.md.
"""
