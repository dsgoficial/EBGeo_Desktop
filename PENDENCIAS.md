# Pendências

Lista de 2026-10-06 do que ficou em aberto depois de zerados os defeitos conhecidos do EBGeo Desktop no QGIS 4 (branch `qgis4`, commit `067398d`). Cada item diz o sintoma, onde mora e o que falta. A arquitetura está em `EBGeo/Calco/ARQUITETURA.md`; o par do EBGeo Web tem a sua própria lista (`DEFEITOS-CONHECIDOS.md` do ebgeo_web).

## P1 `test_exportador.py` sai com 0xC0000409 depois do OK

**Sintoma.** A suíte passa inteira (27 testes, `OK`) e o processo do Python do QGIS termina com o código -1073740791 (0xC0000409, o aborto rápido do Windows), depois de imprimir o resultado.

**Medido (2026-10-06).** 5 de 5 rodadas: 3 com o código de `067398d` e 2 com o de antes dele (`git stash`, 26 testes). Não vem daquele commit e não estava na lista de defeitos. As demais suítes do Calco tocadas por ele saem com 0.

**O que falta.** Isolar a causa como no K7 (`79ce98f`: um `QMessageBox()` sem pai, janela de topo viva destruída pelo sip no fim do processo): rodar com `-X faulthandler`, apagar os candidatos antes da saída um a um (janelas de topo, camadas e jobs de desenho do `exportador/desenho.GeradorDesenho`, o motor JS) e medir a taxa em série. A régua prende o código de saída 0 da suíte.

## P2 Âncora nula do tamanho do Ponto: esperar o conserto do Web

**Sintoma.** O Web desenha o Ponto com correção de zoom e `sizeCreatedAtZoom` ausente ou nulo como se tivesse sido criado no zoom 0, e o tamanho satura no teto de 500 px. O Desktop o desenha sem escala, como o rótulo do mesmo ponto nos dois.

**Onde.** É defeito do Web: `POINT_SIZE` com `anchorDefault: 0` (`frontend/src/js/layers/styles/point.layers.js`) e `sizeCreatedAtZoom || 0` em `add_point_control.js`. Está no D6 do `DEFEITOS-CONHECIDOS.md` do ebgeo_web, com a decisão do chefe de 2026-10-05 de corrigir lá. No Desktop, é a única divergência da auditoria de chaves (`PENDENTES` de `EBGeo/Calco/testes/test_chaves_ausentes.py`).

**O que falta.** Quando o Web for corrigido, a auditoria reprova de propósito: `test_desktop_desenha_como_o_web` cobra que a pendência que deixou de divergir saia da lista. Basta esvaziar `PENDENTES` e o comentário dele, e registrar a medida na seção 5 da arquitetura.

## P3 Zoom 0 gravado na âncora do Ponto: o Desktop não tem o teto de 500 px

**Sintoma.** Com `sizeCreatedAtZoom` igual a 0, os dois lados escalam a partir do zoom 0, mas o Web corta o tamanho em 500 px (`maxValue` de `POINT_SIZE`) e o Desktop não tem teto: o estilo do Ponto fixa o tamanho no terreno sempre que `created_zoom` não é nulo (`COND_ZOOM` e `_metros` de `EBGeo/Calco/estilos_formas.py`). Num zoom de trabalho, o ponto de tamanho 10 ancorado no zoom 0 tem uns 720 km no terreno no Desktop (10 x 78.271,517 m x cos 23°) e 500 px no Web.

**Onde.** A auditoria de chaves põe a referência 0 à parte, como regra de VALOR diferente, fora da comparação da chave ausente e da nula (`comparar` de `test_chaves_ausentes.py`; seção 5 da arquitetura). O Web trata o 0 como âncora legítima: `frontend/tests/integration/migracao-zoom-zero-de-ponto.repro.test.js`.

**O que falta.** Decisão do chefe: portar o teto de 500 px para o tamanho no terreno do Desktop (um `min` por pixel de tela, que depende da escala do mapa) ou deixar como está. Portado, a referência 0 volta à comparação da auditoria.
