# -*- coding: utf-8 -*-
"""
Guardião de camada do calco: com o plugin carregado, cada camada do calco ganha um objeto que
aplica as regras de troca (regras.py) e respeita o `bloqueado` do EBGeo Web em QUALQUER caminho
de edição, não só no dock: formulário nativo, tabela de atributos, calculadora de campo e dock.

Como funciona:
  - Toda edição desses caminhos é um comando de edição do QGIS (beginEditCommand ...
    endEditCommand). O guardião anota as mudanças que chegam DENTRO do comando e, quando ele
    termina, compara com o valor ANTERIOR da feição (o formulário nativo grava vários campos de
    uma vez) e aplica o que as regras pedem num comando próprio, que o Ctrl+Z desfaz.
  - Mudança fora de comando (desfazer, refazer, gravação direta pela API) só atualiza o retrato
    das feições: desfazer não reaplica regra.
  - Feição bloqueada: a edição é revertida (o formulário nativo e o dock já a mostram só para
    leitura; a tabela de atributos não respeita o "editável" por dados, medido). Desbloquear
    pela tabela é permitido e vale na mesma edição.
  - `atualizado_em`: o formulário assado traz o valor padrão `now()` aplicado na atualização,
    que o QGIS renova em qualquer caminho, com ou sem o plugin. Na camada sem esse padrão
    (estilo do operador), o guardião o renova no comando dele.

O retrato guarda só as colunas que as regras leem, mais a linha inteira das feições bloqueadas.
"""
from datetime import datetime, timezone

from qgis.core import QgsFeatureRequest, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QObject

from . import regras

TIPOS_GUARDADOS = regras.TIPOS_COM_REGRAS
COLUNA_ATUALIZADO = 'atualizado_em'


def _nulo(v):
    return v is None or (hasattr(v, 'isNull') and v.isNull())


def _verdade(v):
    return False if _nulo(v) else bool(v)


class Guardiao(QObject):
    def __init__(self, layer, tipo):
        super().__init__(layer)
        self.setObjectName('EBGeoGuardiao')
        self.layer = layer
        self.tipo = tipo
        self.vigiados = tuple(regras.CAMPOS_VIGIADOS.get(tipo, ())) + ('bloqueado',)
        self._anterior = {}
        self._travadas = {}
        self._mudancas = {}
        self._aplicando = False
        self.aplicadas = 0
        self.revertidas = 0
        self._conexoes = [
            (layer.editCommandStarted, self._comando_comecou),
            (layer.editCommandEnded, self._comando_terminou),
            (layer.editCommandDestroyed, self._comando_destruido),
            (layer.attributeValueChanged, self._atributo_mudou),
            (layer.featureAdded, self._feicao_adicionada),
            (layer.afterRollBack, self.recarregar),
            (layer.afterCommitChanges, self.recarregar),
            (layer.updatedFields, self.recarregar),
        ]
        for sinal, slot in self._conexoes:
            sinal.connect(slot)
        self.recarregar()

    def desconectar(self):
        for sinal, slot in self._conexoes:
            try:
                sinal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

    # ---------- retrato ----------
    def recarregar(self, *_):
        self._anterior, self._travadas = {}, {}
        nomes = self.layer.fields().names()
        req = QgsFeatureRequest().setFlags(QgsFeatureRequest.Flag.NoGeometry)
        for f in self.layer.getFeatures(req):
            self._retratar(f, nomes)

    def _retratar(self, f, nomes):
        self._anterior[f.id()] = {c: regras.valor(f[c]) for c in self.vigiados if c in nomes}
        if 'bloqueado' in nomes and _verdade(f['bloqueado']):
            self._travadas[f.id()] = {n: f[n] for n in nomes}
        else:
            self._travadas.pop(f.id(), None)

    def _feicao_adicionada(self, fid):
        f = self.layer.getFeature(fid)
        if f.isValid():
            self._retratar(f, self.layer.fields().names())

    def _atualizar(self, fid, col, valor):
        if col in self.vigiados:
            self._anterior.setdefault(fid, {})[col] = valor
        if col == 'bloqueado':
            if _verdade(valor):
                f = self.layer.getFeature(fid)
                self._travadas[fid] = {n: f[n] for n in self.layer.fields().names()}
            else:
                self._travadas.pop(fid, None)
        elif fid in self._travadas:
            self._travadas[fid][col] = valor

    # ---------- sinais ----------
    def _comando_comecou(self, *_):
        if not self._aplicando:
            self._mudancas = {}

    def _comando_destruido(self, *_):
        if not self._aplicando:
            self._mudancas = {}

    def _atributo_mudou(self, fid, idx, valor):
        col = self.layer.fields().at(idx).name()
        if regras.nao_definido(valor):
            return
        valor = regras.valor(valor)
        if self._aplicando or not self.layer.isEditCommandActive():
            self._atualizar(fid, col, valor)
            return
        self._mudancas.setdefault(fid, {})[col] = valor

    def _comando_terminou(self, *_):
        if self._aplicando or not self._mudancas:
            return
        mudancas, self._mudancas = self._mudancas, {}
        reverter, extras = {}, {}
        sem_padrao = not self._atualizado_nativo()
        for fid, muds in mudancas.items():
            desbloqueio = 'bloqueado' in muds and not _verdade(muds['bloqueado'])
            if fid in self._travadas and not desbloqueio:
                reverter[fid] = ({c: self._travadas[fid].get(c) for c in muds}, muds)
                continue
            anterior = dict(self._anterior.get(fid) or {})
            for col, valor in muds.items():
                self._atualizar(fid, col, valor)
            ex = regras.ao_mudar(self.tipo, anterior, muds)
            if sem_padrao and COLUNA_ATUALIZADO not in muds:
                ex[COLUNA_ATUALIZADO] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            if ex:
                extras[fid] = ex
        if reverter or extras:
            self._aplicar(reverter, extras)

    def _atualizado_nativo(self):
        i = self.layer.fields().indexOf(COLUNA_ATUALIZADO)
        return i < 0 or self.layer.defaultValueDefinition(i).applyOnUpdate()

    def _aplicar(self, reverter, extras):
        idx = self.layer.fields().indexOf
        self._aplicando = True
        try:
            self.layer.beginEditCommand('Calco: regras da feição')
            for fid, (valores, novos) in reverter.items():
                # sem valores padrão: atualizado_em também volta ao que era
                self.layer.changeAttributeValues(fid, {idx(c): v for c, v in valores.items() if idx(c) >= 0},
                                                 {idx(c): v for c, v in novos.items() if idx(c) >= 0}, True)
                self.revertidas += 1
            for fid, ex in extras.items():
                self.layer.changeAttributeValues(fid, {idx(c): v for c, v in ex.items() if idx(c) >= 0})
                self.aplicadas += 1
            self.layer.endEditCommand()
        finally:
            self._aplicando = False
        if reverter:
            msg = 'Feição bloqueada no EBGeo Web: a edição de {} feição(ões) foi desfeita.'.format(len(reverter))
            QgsMessageLog.logMessage(msg, 'EBGeo', Qgis.MessageLevel.Warning)
            try:
                from qgis.utils import iface
                if iface is not None:
                    iface.messageBar().pushWarning('EBGeo', msg)
            except Exception:
                pass
        self.layer.triggerRepaint()


# ---------- registro por camada ----------
_GUARDIOES = {}
_PROJETO = []


def guardiao_de(layer):
    return _GUARDIOES.get(layer.id()) if layer is not None else None


def garantir(layer, tipo=None):
    """O guardião da camada, criado na primeira vez; None para camada que não é de tipo guardado."""
    if layer is None:
        return None
    if tipo is None:
        from .calco import tipo_da_camada
        tipo = tipo_da_camada(layer)
    if tipo not in TIPOS_GUARDADOS:
        return None
    g = _GUARDIOES.get(layer.id())
    if g is None:
        g = Guardiao(layer, tipo)
        _GUARDIOES[layer.id()] = g
        lid = layer.id()
        layer.willBeDeleted.connect(lambda lid=lid: _GUARDIOES.pop(lid, None))
    return g


def _camadas_adicionadas(camadas):
    for lyr in camadas:
        try:
            garantir(lyr)
        except Exception as e:  # camada estranha não derruba a carga do projeto
            QgsMessageLog.logMessage('Guardião não ligado em {}: {}'.format(lyr.name(), e), 'EBGeo',
                                     Qgis.MessageLevel.Warning)


def ligar_projeto(projeto):
    """Liga o guardião nas camadas do calco que já estão no projeto e nas que entrarem."""
    projeto.layersAdded.connect(_camadas_adicionadas)
    _PROJETO.append(projeto)
    _camadas_adicionadas(list(projeto.mapLayers().values()))


def desligar_todos():
    for projeto in _PROJETO:
        try:
            projeto.layersAdded.disconnect(_camadas_adicionadas)
        except (TypeError, RuntimeError):
            pass
    del _PROJETO[:]
    for g in list(_GUARDIOES.values()):
        try:
            g.desconectar()
            g.deleteLater()
        except RuntimeError:
            pass
    _GUARDIOES.clear()
