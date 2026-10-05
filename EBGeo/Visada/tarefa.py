# -*- coding: utf-8 -*-
"""
Cálculo de visibilidade em segundo plano (QgsTask), com progresso e cancelamento.

O Mapa de visibilidade e a Análise de Visibilidade por setor chamavam o motor (nucleo.py) na
linha da interface, e o QGIS ficava sem resposta durante o cálculo. A tarefa roda a função do
motor no gerenciador de tarefas do QGIS (barra de progresso e botão de cancelar no rodapé), e o
que mexe no projeto (camada, estilo, avisos) roda depois, na linha da interface, no `concluir`.

A função recebe `progresso(p)` (0 a 100) e `cancelado()`; o motor os repassa ao GDAL.
"""
from qgis.core import QgsApplication, QgsTask

from . import nucleo


class TarefaVisada(QgsTask):
    """Roda `funcao(progresso, cancelado)` fora da linha da interface.

    `concluir(resultado, erro)` roda na linha da interface ao fim: `resultado` é o que a função
    devolveu (None se falhou ou foi cancelada) e `erro` é a mensagem de ErroVisada, 'cancelado'
    ou a de uma exceção inesperada.
    """

    #: tarefas vivas: o QgsTask só fica no gerenciador enquanto o Python guarda a referência
    vivas = []

    def __init__(self, descricao, funcao, concluir):
        super().__init__(descricao, QgsTask.Flag.CanCancel)
        self.funcao = funcao
        self.concluir = concluir
        self.resultado = None
        self.erro = None
        self.terminou = False
        #: o último progresso, legível depois que o gerenciador apaga a tarefa do C++
        self.avanco = 0.0

    def _progresso(self, p):
        self.avanco = float(p)
        self.setProgress(self.avanco)

    def run(self):
        try:
            self.resultado = self.funcao(self._progresso, self.isCanceled)
        except nucleo.Cancelado:
            self.erro = 'cancelado'
            return False
        except nucleo.ErroVisada as e:
            self.erro = str(e)
            return False
        except Exception as e:  # noqa: BLE001 - a mensagem vai ao operador, e o QGIS não cai
            if self.isCanceled():
                self.erro = 'cancelado'
            else:
                self.erro = 'Erro inesperado no cálculo de visibilidade: {}'.format(e)
            return False
        if self.isCanceled():
            self.erro = 'cancelado'
            return False
        return True

    def finished(self, ok):
        try:
            self.concluir(self.resultado if ok else None, None if ok else (self.erro or 'cancelado'))
        finally:
            self.terminou = True
            if self in TarefaVisada.vivas:
                TarefaVisada.vivas.remove(self)

    @classmethod
    def iniciar(cls, descricao, funcao, concluir):
        t = cls(descricao, funcao, concluir)
        cls.vivas.append(t)
        QgsApplication.taskManager().addTask(t)
        return t
