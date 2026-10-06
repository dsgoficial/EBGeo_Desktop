# -*- coding: utf-8 -*-
"""
Memória da auditoria de chaves (test_chaves_ausentes.py), que morria em silêncio rodando junto de
outras suítes.

Rodar com o Python do QGIS 4, da raiz do repositório:
    python-qgis.bat EBGeo/Calco/testes/test_auditoria_memoria.py

Causa, medida em 2026-10-05: cada troca do filtro (setSubsetString) de uma camada OGR seguida de
uma leitura abre um dataset novo no pool de conexões do QGIS, que só o solta depois de 60 s
ociosos, por um QTimer; sem laço de eventos nada é solto. A auditoria trocava o filtro duas vezes
por variante (a extensão e o desenho) em 3.548 variantes, de 1,7 MB por troca no polígono a
5,2 MB na Área de Coordenação: a suíte passava de 16 GB privados ainda na fase dos desenhos, e
duas rodando juntas (ou ela e outras suítes) esgotavam a memória da máquina de 32 GB. Com a
extensão numa consulta só e o laço de eventos a cada desenho, a fase dos desenhos fica plana em
3 GB e a suíte tem pico de 5,4 GB (o que ainda cresce depois é a ida e volta pelo exportador).

O que se prova, num GeoPackage sintético, com a função da própria auditoria:
    TesteTrocasDeFiltro  no máximo uma troca de filtro por variante (mais uma por base), e o laço
                         de eventos rodando a cada desenho; o código de antes trocava duas vezes e
                         nunca rodava o laço;
    TestePoolSolta       o mecanismo: as trocas sem laço de eventos seguram a memória, e o laço de
                         eventos a devolve depois do prazo do pool (lento: 70 s; só com
                         EBGEO_TESTE_LENTO=1).
"""
import ctypes
import os
import sys
import tempfile
import time
import unittest
from ctypes import wintypes
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import test_chaves_ausentes as T  # noqa: E402  (inicia o QGIS e traz a função da auditoria)
from osgeo import ogr, osr  # noqa: E402
from qgis.core import QgsVectorLayer  # noqa: E402
from qgis.PyQt.QtCore import QCoreApplication  # noqa: E402


class _Memoria(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                                       'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
                                       'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def memoria_privada_mb():
    if os.name != 'nt':
        return None
    k = ctypes.WinDLL('kernel32')
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Memoria), wintypes.DWORD]
    m = _Memoria()
    m.cb = ctypes.sizeof(m)
    k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(m), m.cb)
    return m.PrivateUsage / 2 ** 20


def gpkg_sintetico(n_bases=6, por_base=25):
    """Um ponto por variante, na tabela do tipo `point`, com o ebgeo_id da auditoria."""
    caminho = os.path.join(tempfile.mkdtemp(prefix='ebgeo_aud_mem_'), 'sintetico.gpkg')
    ds = ogr.GetDriverByName('GPKG').CreateDataSource(caminho)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    lyr = ds.CreateLayer(T.schema.TIPOS['point']['tabela'], srs, ogr.wkbPoint)
    lyr.CreateField(ogr.FieldDefn('ebgeo_id', ogr.OFTString))
    ids = {}
    for b in range(n_bases):
        for v in range(por_base):
            vid = 'base{}§chave§v{}'.format(b, v)
            f = ogr.Feature(lyr.GetLayerDefn())
            f.SetField('ebgeo_id', vid)
            f.SetGeometry(ogr.CreateGeometryFromWkt('POINT ({} {})'.format(-43.2 + b * 0.01, -22.9)))
            lyr.CreateFeature(f)
            ids[vid] = ('point', 'base{}'.format(b), 'chave', 'v{}'.format(v), None)
    ds = None
    return caminho, ids


class TesteTrocasDeFiltro(unittest.TestCase):
    def test_uma_troca_por_variante_e_o_laco_a_cada_desenho(self):
        caminho, ids = gpkg_sintetico()
        trocas = []
        original = QgsVectorLayer.setSubsetString

        class Camada(QgsVectorLayer):
            def setSubsetString(self, filtro):
                if filtro != self.subsetString():
                    trocas.append(filtro)
                return original(self, filtro)

        laco = mock.Mock(wraps=QCoreApplication.processEvents)
        m0 = memoria_privada_mb()
        with mock.patch.object(T, 'QgsVectorLayer', Camada), \
                mock.patch.object(QCoreApplication, 'processEvents', laco):
            out = T.desktop_assinaturas(caminho, ids)
        m1 = memoria_privada_mb()
        bases = len({b for _t, b, *_r in ids.values()})
        print('\n{} variantes em {} bases: {} trocas de filtro, {} voltas ao laço de eventos{}'.format(
            len(ids), bases, len(trocas), laco.call_count,
            '' if m0 is None else ', {:+.0f} MB privados'.format(m1 - m0)))
        self.assertEqual(len(out), len(ids))
        self.assertLessEqual(len(trocas), len(ids) + bases)
        self.assertGreaterEqual(laco.call_count, len(ids))


@unittest.skipUnless(os.environ.get('EBGEO_TESTE_LENTO') and os.name == 'nt', 'lento (EBGEO_TESTE_LENTO=1), Windows')
class TestePoolSolta(unittest.TestCase):
    def test_o_laco_de_eventos_devolve_a_memoria_das_trocas(self):
        caminho, ids = gpkg_sintetico(1, 300)
        vl = QgsVectorLayer(T.gpkg.uri_camada(caminho, 'point'), 'ponto', 'ogr')
        m0 = memoria_privada_mb()
        for vid in ids:
            vl.setSubsetString('"ebgeo_id" = \'{}\''.format(vid))
            for f in vl.getFeatures():
                f.geometry()
        m1 = memoria_privada_mb()
        t0 = time.time()
        while time.time() - t0 < 70:
            QCoreApplication.processEvents()
            time.sleep(0.02)
        m2 = memoria_privada_mb()
        print('\n300 trocas: {:+.0f} MB; depois de 70 s de laço de eventos: {:+.0f} MB'.format(m1 - m0, m2 - m0))
        self.assertGreater(m1 - m0, 100)
        self.assertLess(m2 - m0, 0.8 * (m1 - m0))


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
