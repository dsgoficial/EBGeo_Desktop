# -*- coding: utf-8 -*-
"""
Validação da segunda letra do MGRS nas zonas polares (UPS).

Na referência do MGRS (GeoTrans da NGA, Convert_MGRS_To_UPS, reproduzido no mgrs.c do
driver NITF do GDAL), a segunda letra de uma coordenada UPS não pode ser D, E, M, N, V nem W,
além de ter de estar na faixa da zona (A: J a Z; B: A a R; Y: J a Z; Z: A a J). O teste antigo
`letters[1] in [invalid]` comparava a letra com uma lista que continha a lista, nunca casava, e
deixava passar coordenada polar inválida.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/ZoomCoordenadas/testes/test_mgrs_ups.py
"""
import importlib.util
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location('mgrs_ebgeo', os.path.join(os.path.dirname(AQUI), 'mgrs.py'))
mgrs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mgrs)


class TestMgrsUps(unittest.TestCase):

    def test_segunda_letra_proibida_reprova(self):
        # Cada letra proibida dentro da faixa da zona: sem o filtro, todas convertiam.
        casos = ['ZDA1234567890', 'ZEA1234567890',   # Z: faixa A a J
                 'BMA1234567890', 'BNA1234567890',   # B: faixa A a R
                 'YVA1234567890', 'YWA1234567890',   # Y: faixa J a Z
                 'AMA1234567890', 'AWA1234567890']   # A: faixa J a Z
        for c in casos:
            with self.subTest(mgrs=c):
                with self.assertRaises(mgrs.MgrsException):
                    mgrs.toWgs(c)

    def test_par_valido_segue_passando(self):
        # Ida e volta em pontos polares dos dois hemisférios e dos dois lados do meridiano.
        for lat, lon in [(85.0, 30.0), (85.0, -120.0), (-85.0, 45.0), (-85.0, -60.0), (88.0, 0.5)]:
            with self.subTest(lat=lat, lon=lon):
                m = mgrs.toMgrs(lat, lon).strip()
                self.assertIn(m[0], 'ABYZ')
                lat2, lon2 = mgrs.toWgs(m)
                self.assertAlmostEqual(lat2, lat, places=4)
                self.assertAlmostEqual(((lon2 - lon + 180) % 360) - 180, 0, places=3)

    def test_letra_valida_vizinha_da_proibida_passa(self):
        # F e L são válidas e vizinhas de E e M: o filtro não pode pegar a vizinha.
        for c in ['ZFA1234567890', 'ZCC7772818959', 'BLL1234567890', 'BFR9276792767', 'YXK1895977728']:
            with self.subTest(mgrs=c):
                lat, lon = mgrs.toWgs(c)
                self.assertGreater(abs(lat), 80)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
