# Defeitos conhecidos

Lista de 2026-10-05 dos defeitos conhecidos do EBGeo Desktop no QGIS 4 (branch `qgis4`), achados durante a implementação do Calco, do formulário das feições, do exportador `.ebgeo` e da visibilidade sem GRASS. Cada item diz o sintoma, onde mora e o conserto sugerido. A arquitetura está em `EBGeo/Calco/ARQUITETURA.md`; o par do EBGeo Web tem a sua própria lista.

## K1 Seta combinada: todos os ramos com as propriedades da feição inteira

**Sintoma.** Uma Seta combinada vinda do EBGeo Web, em que cada ramo tem propriedades próprias (por exemplo, ponta dupla só num ramo), aparece no QGIS com todos os ramos iguais, usando as propriedades da feição.

**Onde.** O estilo nativo da Seta (`EBGeo/Calco/estilos_taticos.py` e `EBGeo/Calco/expressoes/seta.exp`) lê as colunas da feição; o esquema não tem coluna por ramo. O exportador já desenha ramo a ramo (`EBGeo/Calco/exportador/desenho.py`), então o arquivo que volta ao Web sai certo; só o desenho no QGIS diverge.

**Conserto sugerido.** Guardar as propriedades por ramo numa coluna JSON e fazer a expressão escolher, por parte da geometria (`@geometry_part_num`), as propriedades daquele ramo.

## K2 Linha de Limite com escalão em círculo vai ao `.ebgeo` sem o vão

**Sintoma.** Um Limite com escalão `o`, `oo` ou `ooo` criado ou editado no Desktop sai no `.ebgeo` com o eixo inteiro, sem o vão em volta do símbolo; o Web só o redesenha quando a ferramenta de Limite carrega.

**Onde.** `EBGeo/Calco/exportador/desenho.py`, que calcula o desenho dos táticos a partir do estilo.

**Conserto sugerido.** Recortar o vão no desenho exportado como o Web faz (`add_boundary_geometry.js` do Web), conferindo contra a geometria gravada pelo Web numa fixture.

## K3 Desenho num atlas importado, num tipo que o mapa ainda não tem

**Sintoma.** Sem uma camada daquele tipo selecionada, a ferramenta cria o grupo "Calco: nome" fora da árvore do atlas, e a feição nova não fica no mapa e na camada do EBGeo esperados.

**Onde.** `EBGeo/Calco/ferramentas.py` (`mapa_e_camada`) e a árvore do importador (`EBGeo/Calco/importador/arvore.py`).

**Conserto sugerido.** Quando o calco ativo é um atlas importado, criar a camada do tipo dentro do mapa e da camada do EBGeo ativos na árvore.

## K4 Formas de centro e raio editadas vértice a vértice

**Sintoma.** Círculo, elipse, retângulo e setor editados vértice a vértice no QGIS saem no `.ebgeo` como desenhados, com aviso; o Web os edita pelo centro e pelo raio, e a forma pode deixar de ser editável lá como forma.

**Onde.** `EBGeo/Calco/exportador/montador.py`.

**Conserto sugerido.** Recalcular centro, raios e ângulo a partir da geometria editada quando ela ainda é a forma (ajuste por mínimos quadrados com tolerância), e manter o aviso só quando não for.

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

## Menores

- **Fator de 512 px do zoom:** o tamanho com correção de zoom usa a convenção do MapLibre (78271,517 m/px no zoom 0, tiles de 512 px) e ainda não foi medido lado a lado com a tela do Web.
- **Alças de edição do Web** (mover a instância do escalão, largura da seta, distância do texto) não existem no Desktop.
- **Calco importado antes de 2026-10-05:** não tem a tabela `ebgeo_imagem`, e o `.ebgeo` exportado sai sem os bytes das fotos de 3D e 360 e das figuras de slide; a exportação avisa. Reimportar o arquivo original resolve.
- **Âncora do Naval (modificador 1, código 46):** vem do milsymbol pelo motor do Web; as pontas saem em seta cheia e o desenho fica cerca de 21 % mais largo que o recorte do MD33-C-01.
- **Rótulos de 1 ou 2 letras no setor 1 de Unidades:** cerca de 6 % menores que no manual, pelo leiaute do milsymbol, igual no Web.
- **Texto externo da Área num polígono côncavo:** a linha de chamada pode cruzar o braço do U (`EBGeo/Calco/expressoes/_area_externa.exp`), mesmo algoritmo do Web.
- **`icons/dsg.png`:** o ícone antigo segue listado no `resources.qrc` compilado; sair exige recompilar os recursos.
