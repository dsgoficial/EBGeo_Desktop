# -*- coding: utf-8 -*-
"""Regressão do aborto após OK: executar com python-qgis.bat, em processo separado."""
import os
import subprocess
import sys
import unittest


class TestEncerramento(unittest.TestCase):
    def test_exportador_encerra_com_zero(self):
        # O menu liga/desliga guardiões; a árvore reutiliza a memória antes da destruição
        # das camadas. Cada classe isolada passava, mas a sequência abortava após o OK.
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_exportador.py')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        proc = subprocess.run([sys.executable, '-X', 'faulthandler', script,
                               'TestAlgoritmo.test_acao_do_menu', 'TestArvore'],
                              env=env, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=180)
        self.assertEqual(proc.returncode, 0, proc.stdout[-4000:] + proc.stderr[-4000:])
        self.assertIn('Ran 3 tests', proc.stderr)
        self.assertNotIn('skipped', proc.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
