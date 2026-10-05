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
  - Símbolos pontuais desenhados por SVG (simbolos.TIPOS_SVG: militar, medida, engenharia e
    declinação): quando a edição muda um campo que desenha (ou a regra o muda), ou a feição nasce
    dentro de um comando (adicionar feição, colar), o guardião regrava o SVG e as colunas de
    desenho no MESMO comando das regras, se a assinatura não bate; o Ctrl+Z desfaz o desenho
    junto com a regra, e desfazer a edição volta o desenho gravado antes. Antes de gravar a
    camada, a feição mudada no buffer com assinatura divergente é redesenhada (edição pela API
    fora de comando). O motor que rejeita o símbolo (SIDC inválido) deixa o desenho como estava,
    e o estilo mostra o aviso vermelho. Nesses tipos, o "valor padrão do provedor" que o
    formulário nativo grava no campo igual ao DEFAULT da coluna volta a ser o valor, no mesmo
    comando (sem isso, o SIDC padrão acendia o aviso até o commit).

O retrato guarda só as colunas que as regras leem, mais a linha inteira das feições bloqueadas.
"""
from datetime import datetime, timezone

from qgis.core import QgsFeatureRequest, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import QObject

from . import regras, schema, simbolos

TIPOS_GUARDADOS = regras.TIPOS_COM_REGRAS | frozenset(simbolos.TIPOS_SVG)
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
        self._novas = set()
        self._indefinidos = {}
        self._aplicando = False
        self.aplicadas = 0
        self.revertidas = 0
        self.svg = tipo in simbolos.TIPOS_SVG
        self.desenho = frozenset(simbolos.campos_que_desenham(tipo)) if self.svg else frozenset()
        self.regeneradas = 0
        self.erros_svg = []
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
        if self.svg:
            self._conexoes.append((layer.beforeCommitChanges, self._antes_de_gravar))
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
        if self.svg and not self._aplicando and self.layer.isEditCommandActive():
            self._novas.add(fid)

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
            self._mudancas, self._novas, self._indefinidos = {}, set(), {}

    def _comando_destruido(self, *_):
        if not self._aplicando:
            self._mudancas, self._novas, self._indefinidos = {}, set(), {}

    def _atributo_mudou(self, fid, idx, valor):
        col = self.layer.fields().at(idx).name()
        if regras.nao_definido(valor):
            # só nos campos que desenham, e com DEFAULT de verdade: a descrição vazia (DEFAULT '')
            # o provedor grava '' no commit, mas defaultValue() a dá nula
            if self.svg and col in self.desenho and not self._aplicando and self.layer.isEditCommandActive()                     and valor.defaultValueClause():
                self._indefinidos.setdefault(fid, set()).add(col)
            return
        valor = regras.valor(valor)
        if self._aplicando or not self.layer.isEditCommandActive():
            self._atualizar(fid, col, valor)
            return
        self._mudancas.setdefault(fid, {})[col] = valor

    def _comando_terminou(self, *_):
        if self._aplicando or not (self._mudancas or self._novas or self._indefinidos):
            return
        mudancas, self._mudancas = self._mudancas, {}
        novas, self._novas = self._novas, set()
        indefinidos, self._indefinidos = self._indefinidos, {}
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
        if self.svg:
            # O formulário nativo grava "valor padrão do provedor" (QgsUnsetAttributeValue) no campo
            # cujo valor é igual ao DEFAULT da coluna (o SIDC padrão, o tamanho 1), ao salvar
            # qualquer mudança. No buffer, o estilo o lê como vazio (o SIDC padrão acendia o aviso
            # vermelho até o commit); aqui ele volta a ser o valor, o mesmo que o commit gravaria.
            for fid, cols in indefinidos.items():
                if fid in reverter or fid in self._travadas:
                    continue
                for col in cols:
                    i = self.layer.fields().indexOf(col)
                    if col not in extras.get(fid, {}) and i >= 0:
                        extras.setdefault(fid, {})[col] = self.layer.dataProvider().defaultValue(i)
            for fid in (set(mudancas) | novas) - set(reverter):
                desenhou = fid in novas or bool(self.desenho & (set(mudancas.get(fid, ())) | set(extras.get(fid, ()))))
                cols = self._desenho(fid, extras.get(fid, {}), manter_bitmap=fid in novas) if desenhou else {}
                if cols:
                    extras.setdefault(fid, {}).update(cols)
        if reverter or extras:
            self._aplicar(reverter, extras)

    # ---------- desenho dos símbolos pontuais ----------
    def _desenho(self, fid, extras, manter_bitmap=False):
        """
        As colunas de desenho novas da feição (com as mudanças `extras` por cima), ou {} quando a
        assinatura gravada já bate. Com `manter_bitmap`, a feição só com o PNG do Web (sem SVG)
        fica com ele: a que nasceu colada e a que chega ao commit sem mudança vista no desenho.
        """
        f = self.layer.getFeature(fid)
        if not f.isValid():
            return {}
        atributos = {n: f[n] for n in f.fields().names()}
        for i, n in enumerate(f.fields().names()):
            if regras.nao_definido(atributos[n]):
                atributos[n] = self.layer.dataProvider().defaultValue(i)
        atributos.update(extras)
        sem_svg = _nulo(atributos.get('svg')) or not atributos.get('svg')
        if not sem_svg and simbolos.assinatura_em_dia(self.tipo, atributos):
            return {}
        if sem_svg and manter_bitmap and not _nulo(atributos.get('bitmap_b64')) and atributos.get('bitmap_b64'):
            return {}
        try:
            colunas = simbolos.renderizar(self.tipo, atributos)
        except Exception as erro:  # o motor rejeitou: o desenho fica e o estilo acusa a divergência
            self.erros_svg.append((fid, str(erro)))
            QgsMessageLog.logMessage('Símbolo não redesenhado (fid {}): {}'.format(fid, erro), 'EBGeo',
                                     Qgis.MessageLevel.Warning)
            return {}
        self.regeneradas += 1
        return colunas

    def _antes_de_gravar(self):
        """Redesenha, antes do commit, a feição do buffer cujo desenho ficou para trás."""
        buf = self.layer.editBuffer()
        if self._aplicando or buf is None:
            return
        fids = (set(buf.changedAttributeValues()) | set(buf.addedFeatures())) - set(self._travadas)
        extras = {}
        for fid in sorted(fids):
            cols = self._desenho(fid, {}, manter_bitmap=True)
            if cols:
                extras[fid] = cols
        if extras:
            self._aplicar({}, extras)

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
                # cor em minúsculas e JSON como objeto (schema.atributos_para_qgis), como as outras gravações
                ex = schema.atributos_para_qgis(self.tipo, ex)
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
