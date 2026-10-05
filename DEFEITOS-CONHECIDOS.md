# Defeitos conhecidos

Lista de 2026-10-05 dos defeitos conhecidos do EBGeo Desktop no QGIS 4 (branch `qgis4`), achados durante a implementação do Calco, do formulário das feições, do exportador `.ebgeo` e da visibilidade sem GRASS. Cada item diz o sintoma, onde mora e o conserto sugerido. A arquitetura está em `EBGeo/Calco/ARQUITETURA.md`; o par do EBGeo Web tem a sua própria lista.

## K5 Sem o plugin, trocar o tipo no formulário nativo não aplica os padrões

**Sintoma.** Num QGIS sem o plugin, trocar o símbolo da Área de Coordenação, da Linha de Coordenação ou da Medida pelo formulário nativo grava só o código; a cor padrão, as minas e os demais padrões do tipo novo não são aplicados.

**Onde.** As regras de troca vivem no guardião (`EBGeo/Calco/regras.py`, `EBGeo/Calco/guardiao.py`), que só existe com o plugin; o formulário nativo é 100 % sem código por decisão de 2026-10-05.

**Medido (2026-10-05).** O único mecanismo sem código, o valor padrão por expressão aplicado na atualização, roda depois da gravação, na feição já trocada: pelo formulário nativo, `"symbol_code"` e `get_feature_by_id(@layer, $id)` dão os dois o código novo (`TesteSemPluginSoValorNovo` de `EBGeo/Calco/testes/test_guardiao.py`). A ordem em que o QGIS 4.0.0 avalia vários desses padrões muda de um processo para outro (seis campos em cadeia, cinco processos, cinco ordens), o que descarta guardar o código anterior numa coluna de memória. As regras de troca dependem todas do valor anterior: a cor padrão só na linha que ainda veste a do símbolo anterior, os padrões da Área que ainda estão nos do tipo anterior, a cor e as escolhas de desenho da Medida. Uma versão sem o anterior, aplicada a cada gravação, regravaria a escolha do operador ao salvar só o nome. O escalão da Medida é função só dos valores atuais, mas sem o plugin a medida trocada não é redesenhada (o SVG assado acende o aviso de desenho velho), e o padrão o regravaria em toda gravação. Nada foi aplicado; a hachura que acompanha o tipo na Área segue como o único padrão sem código.

**Conserto.** Não há, sem código, no QGIS 4.0.0; fica documentado. Com o plugin, o guardião aplica as regras em qualquer caminho de edição.

## K9 Chaves que o Web desenha e o Desktop ignora

**Sintoma.** Mudar o valor de 34 chaves muda o desenho no Web e não muda no Desktop. Exemplos: opacidade da Linha de Coordenação, da Frente Ocupada, da imagem e do ponto; textos da Linha de Coordenação; os campos de zoom do rótulo; `lineOpacity` da Seta. No sentido oposto, 3 chaves só mudam o Desktop: `width` da imagem e `visivel` das entradas de linha de visada e de visibilidade.

**Onde.** Medido pela auditoria `EBGeo/Calco/testes/test_chaves_ausentes.py` (com `web_assinatura.mjs`), que imprime a lista completa por tipo.

**Conserto sugerido.** Levar cada chave ao estilo nativo do tipo, uma família por vez, com a auditoria como régua.

## Menores

- **Fator de 512 px do zoom:** o tamanho com correção de zoom usa a convenção do MapLibre (78271,517 m/px no zoom 0, tiles de 512 px) e ainda não foi medido lado a lado com a tela do Web.
- **Forma girada no QGIS:** a ferramenta Girar gira em graus, na camada em EPSG:4326, e o círculo, a elipse, o retângulo ou o setor girado fora do equador deixa de ser a forma (0,6 a 10 % do tamanho a 15 a 24 graus de latitude): sai no `.ebgeo` como desenhado, com aviso (`EBGeo/Calco/exportador/formas.py`). Escalar e transladar voltam com os parâmetros.
- **Ramo da Seta combinada no dock:** o Web edita cada ramo (largura, ponta, ponta dupla, aeromóvel) no painel; o dock edita a seta inteira (vai a todos os ramos), e o ramo só se edita na coluna JSON `ramos` (oculta no formulário e na tabela), pela calculadora de campo. O desenho e o exportador já leem o ramo editado assim.
- **Auditoria de chaves em paralelo:** `EBGeo/Calco/testes/test_chaves_ausentes.py` parou em silêncio logo depois de carregar quando rodou junto com outras suítes; sozinho passa (cerca de 10 min). Causa não achada.
- **Ponto com zoom de referência vazio:** o Web o desenha no teto de 500 px (defeito do Web, a corrigir lá por decisão do chefe); o Desktop não escala, como o rótulo.
