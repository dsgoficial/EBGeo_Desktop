# -*- coding: utf-8 -*-
"""
Construtor de SIDC: codificação da extensão brasileira e ida e volta SIDC <-> controles.

Rodar com o Python do QGIS 4:
    python-qgis.bat EBGeo/Calco/testes/test_construtor_sidc.py
"""
import os
import sys
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))

from qgis.core import QgsApplication  # noqa: E402

_app = QgsApplication([], True)
_app.initQgis()

from Calco.ui.construtor_sidc import (  # noqa: E402
    ConstrutorSidc, catalogos, codificar_extensao, decodificar_extensao, desmontar_sidc,
)


class TesteExtensao(unittest.TestCase):
    def test_exemplos_medidos_no_web(self):
        # referências tiradas do BrazilianSIDCExtension.encode do Web, rodado em node
        self.assertEqual(codificar_extensao(entidade=1), '0760016384')
        self.assertEqual(codificar_extensao(comando=True), '0760008192')
        self.assertEqual(codificar_extensao(especial=1), '0760001024')
        self.assertEqual(codificar_extensao(), '0760000000')
        self.assertEqual(codificar_extensao(31, True, 7, 31, 31), '0760524287')
        self.assertEqual(codificar_extensao(5, True, 3, 12, 7), '0760093575')

    def test_ida_e_volta(self):
        for args in [(0, False, 0, 0, 0), (5, True, 3, 12, 7), (31, False, 7, 0, 31)]:
            d = decodificar_extensao(codificar_extensao(*args))
            self.assertEqual((d['entidade'], d['comando'], d['especial'], d['ext_mod1'], d['ext_mod2']), args)


class TesteDialogo(unittest.TestCase):
    def test_sidc_volta_igual_pelos_controles(self):
        """Para cada conjunto, ícones com e sem extensão: aplicar o SIDC e reler dá o mesmo SIDC."""
        cat = catalogos()['militar']['porConjunto']
        dlg = ConstrutorSidc()
        casos = 0
        for conj, c in cat.items():
            icones = c['icones']
            amostra = icones[:2] + [i for i in icones if i.get('extensao') is not None][:2]
            for ic in amostra:
                ext = ic.get('extensao') or 0
                sidc = '1003{}0000{}0000'.format(conj, ic['codigo']) + codificar_extensao(entidade=ext)
                self.assertTrue(dlg.aplicar_sidc(sidc), sidc)
                self.assertEqual(dlg.sidc_atual(), sidc, 'conjunto {} ícone {}'.format(conj, ic))
                casos += 1
        print('\n[construtor] SIDCs em ida e volta:', casos)
        self.assertGreater(casos, 30)

    def test_pior_caso_sidc_invalido(self):
        dlg = ConstrutorSidc()
        self.assertFalse(dlg.aplicar_sidc('123'))
        self.assertTrue(dlg.aviso.text())

    def test_previa_desenha(self):
        dlg = ConstrutorSidc()
        dlg.aplicar_sidc('10031000161211000000')
        pm = dlg.previa.pixmap()
        self.assertFalse(pm is None or pm.isNull())
        img = pm.toImage()
        tinta = sum(1 for x in range(0, img.width(), 4) for y in range(0, img.height(), 4)
                    if img.pixelColor(x, y).alpha() > 0)
        self.assertGreater(tinta, 50)

    def test_valores_tem_amplificadores_e_comando(self):
        dlg = ConstrutorSidc()
        dlg.aplicar_sidc('10031000161211000000' + codificar_extensao(comando=True, especial=2))
        dlg.textos['uniqueDesignation'].setText('1 BIB')
        v = dlg.valores()
        self.assertEqual(v['unique_designation'], '1 BIB')
        self.assertTrue(v['is_command'])
        self.assertEqual(v['special_modifier'], '2')
        self.assertEqual(desmontar_sidc(v['sidc'])['especial'], 2)


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if r.wasSuccessful() else 1)
