# Defeitos conhecidos

Lista de 2026-10-05 dos defeitos conhecidos do EBGeo Desktop no QGIS 4 (branch `qgis4`), achados durante a implementação do Calco, do formulário das feições, do exportador `.ebgeo` e da visibilidade sem GRASS. Cada item diz o sintoma, onde mora e o conserto sugerido. A arquitetura está em `EBGeo/Calco/ARQUITETURA.md`; o par do EBGeo Web tem a sua própria lista.

## K3 Desenho num atlas importado, num tipo que o mapa ainda não tem

**Sintoma.** Sem uma camada daquele tipo selecionada, a ferramenta cria o grupo "Calco: nome" fora da árvore do atlas, e a feição nova não fica no mapa e na camada do EBGeo esperados.

**Onde.** `EBGeo/Calco/ferramentas.py` (`mapa_e_camada`) e a árvore do importador (`EBGeo/Calco/importador/arvore.py`).

**Conserto sugerido.** Quando o calco ativo é um atlas importado, criar a camada do tipo dentro do mapa e da camada do EBGeo ativos na árvore.

## K5 Sem o plugin, trocar o tipo no formulário nativo não aplica os padrões

**Sintoma.** Num QGIS sem o plugin, trocar o símbolo da Área de Coordenação, da Linha de Coordenação ou da Medida pelo formulário nativo grava só o código; a cor padrão, as minas e os demais padrões do tipo novo não são aplicados.

**Onde.** As regras de troca vivem no guardião (`EBGeo/Calco/regras.py`, `EBGeo/Calco/guardiao.py`), que só existe com o plugin; o formulário nativo é 100 % sem código por decisão de 2026-10-05.

**Conserto sugerido.** Não há conserto sem código no formulário; o caminho é aceitar e documentar, ou aplicar os padrões que couberem como valor padrão de campo por expressão.

## K6 Mapa de visibilidade e soma por setor travam a interface

**Sintoma.** Durante o cálculo, o QGIS fica sem resposta (só com o cursor de espera).

**Onde.** `EBGeo/Visibility/UI/interface_window.py` e `EBGeo/VisibilityAnalysis/visibilityAnalysis.py`, que chamam o motor de `EBGeo/Visada/nucleo.py` na linha da interface.

**Conserto sugerido.** Rodar como `QgsTask`, como a cobertura de radar (`EBGeo/Visada/cobertura_radar.py`).

## K7 Teste de visibilidade às vezes cai ao encerrar

**Sintoma.** `EBGeo/Visada/testes/test_visada.py` imprime OK e o processo sai com código 139 de vez em quando.

**Onde.** No encerramento do QGIS dentro do teste; a mesma classe de aborto do `exitQgis` já anotada nas suítes do Calco.

**Conserto sugerido.** Encerrar sem `exitQgis` e sair pelo `sys.exit` do resultado, como as suítes do Calco.

## K8 Formas com hachura ligada e tipo vazio não desenham a hachura

**Sintoma.** Polígono, círculo, elipse, retângulo ou setor vindo do Web com `hatchEnabled` verdadeiro e `hatchType` ausente ou nulo: o Web desenha hachura diagonal, o Desktop não desenha nenhuma.

**Onde.** `EBGeo/Calco/estilos_formas.py` (as camadas de padrão só ligam com um tipo desenhado) e as condições dos campos de hachura em `EBGeo/Calco/formulario/tipos/comuns.py`. A auditoria `EBGeo/Calco/testes/test_chaves_ausentes.py` mantém o caso na lista `PENDENTES`.

**Decisão do chefe (2026-10-05).** O Desktop passa a desenhar como o Web: tipo vazio com hachura ligada desenha diagonal, e os campos de espaçamento e espessura aparecem nesse caso.

**Conserto sugerido.** Tratar o tipo nulo como diagonal na expressão das camadas de padrão e na condição do formulário e do dock; tirar o caso de `PENDENTES` e conferir pela auditoria.

## K9 Chaves que o Web desenha e o Desktop ignora

**Sintoma.** Mudar o valor de 34 chaves muda o desenho no Web e não muda no Desktop. Exemplos: opacidade da Linha de Coordenação, da Frente Ocupada, da imagem e do ponto; textos da Linha de Coordenação; os campos de zoom do rótulo; `lineOpacity` da Seta. No sentido oposto, 3 chaves só mudam o Desktop: `width` da imagem e `visivel` das entradas de linha de visada e de visibilidade.

**Onde.** Medido pela auditoria `EBGeo/Calco/testes/test_chaves_ausentes.py` (com `web_assinatura.mjs`), que imprime a lista completa por tipo.

**Conserto sugerido.** Levar cada chave ao estilo nativo do tipo, uma família por vez, com a auditoria como régua.

## Menores

- **Fator de 512 px do zoom:** o tamanho com correção de zoom usa a convenção do MapLibre (78271,517 m/px no zoom 0, tiles de 512 px) e ainda não foi medido lado a lado com a tela do Web.
- **Forma girada no QGIS:** a ferramenta Girar gira em graus, na camada em EPSG:4326, e o círculo, a elipse, o retângulo ou o setor girado fora do equador deixa de ser a forma (0,6 a 10 % do tamanho a 15 a 24 graus de latitude): sai no `.ebgeo` como desenhado, com aviso (`EBGeo/Calco/exportador/formas.py`). Escalar e transladar voltam com os parâmetros.
- **Ramo da Seta combinada no dock:** o Web edita cada ramo (largura, ponta, ponta dupla, aeromóvel) no painel; o dock edita a seta inteira (vai a todos os ramos), e o ramo só se edita na coluna JSON `ramos` (oculta no formulário e na tabela), pela calculadora de campo. O desenho e o exportador já leem o ramo editado assim.
- **Âncora do Naval (modificador 1, código 46):** vem do milsymbol pelo motor do Web; as pontas saem em seta cheia e o desenho fica cerca de 21 % mais largo que o recorte do MD33-C-01.
- **Rótulos de 1 ou 2 letras no setor 1 de Unidades:** cerca de 6 % menores que no manual, pelo leiaute do milsymbol, igual no Web.
- **Auditoria de chaves em paralelo:** `EBGeo/Calco/testes/test_chaves_ausentes.py` parou em silêncio logo depois de carregar quando rodou junto com outras suítes; sozinho passa (cerca de 10 min). Causa não achada.
- **Ponto com zoom de referência vazio:** o Web o desenha no teto de 500 px (defeito do Web, a corrigir lá por decisão do chefe); o Desktop não escala, como o rótulo.
- **`icons/dsg.png`:** o ícone antigo segue listado no `resources.qrc` compilado; sair exige recompilar os recursos.
