# Calco: arquitetura

O Calco é a simbologia militar do EBGeo Web no QGIS 4 e o importador do arquivo `.ebgeo`. Ferramentas de desenho e importador escrevem no mesmo GeoPackage, com o mesmo esquema: o que se importa se edita com as mesmas ferramentas, e o que se desenha guarda as propriedades com os nomes do Web. Caminhos aqui são relativos a `EBGeo/Calco/`.

## 1. Princípios

1. **A camada guarda o que o operador decidiu, e o estilo deriva o desenho.** Linha tática guarda o eixo e os atributos; símbolo pontual guarda o ponto, o código (SIDC, `point_code`) e os amplificadores. O desenho do Web gravado no `.ebgeo` (geometria derivada, PNG) é cache, nunca fonte.
2. **Abrir sem o plugin é requisito.** O calco vai para outra OM por GeoPackage, e nada que desenha depende de Python em tempo de renderização: linhas e áreas são expressões nativas (Geometry Generator), símbolos pontuais são SVG "assados" num campo, e o estilo fica no `layer_styles` do próprio arquivo. É a arquitetura "nativo e assado".
3. **Uma fonte de verdade com o Web.** Mesmos nomes de propriedade, mesmos catálogos e, nos símbolos pontuais, os próprios geradores do Web num bundle JS, para a extensão brasileira não ser portada à mão.
4. **Offline e sem instalação.** Só o que vem no QGIS 4: `QJSEngine`, `QSvgRenderer`, pyproj, GDAL/OGR.

## 2. Modelo de dados e camadas

**Esquema único.** `schema.py` é o contrato entre ferramentas, estilos e importador, e não importa QGIS. `TIPOS` dá, por tipo do Web, o balde do `.ebgeo`, a tabela, a geometria e os campos `(coluna, tipo, padrão, propriedade_web)`. `gpkg.py` cria e completa o GeoPackage só com OGR (a coluna que faltar é acrescentada). CRS EPSG:4326, como o `.ebgeo`.

**Colunas comuns** (`CAMPOS_COMUNS`): `ebgeo_id` (de `properties.id`), `mapa`, `camada_id` (`layerId`, ausente vale `default`), `nome`, `descricao`, `visivel`, `bloqueado`, `grupos` (JSON dos grupos EBGeo da feição), `criado_em`, `atualizado_em`, `atributos` (JSON das chaves livres) e `props` (as propriedades originais, para o caminho de volta).

**Colunas promovidas** são só as que estilo ou ferramenta leem, com o nome do Web em snake_case e sufixo de unidade quando o Web não a diz (`symbol_size_km`, `width_m`). Os `attributes` livres viram também colunas `attr_<chave saneada>`, com a chave original como alias. Tabelas de apoio (`TABELAS_APOIO`): `ebgeo_documento` (com o `data.json` original inteiro, inclusive o que está fora do recorte), `ebgeo_mapa`, `ebgeo_camada`, `ebgeo_grupo`, `ebgeo_grupo_membro`, `ebgeo_icone`, `ebgeo_foto`.

**Geometria guardada contra geometria QGIS** (`importador/escritor.py`, `geometria_qgis`):

| Tipo | No `.ebgeo` | Na tabela |
|---|---|---|
| `boundary`, `coordination_line`, `occupied_front` | desenho num zoom e o eixo em `baseCoordinates` | LineString do eixo |
| `arrow` | contorno e `baseCoordinates` | MultiLineString, um ramo por parte (`branches[]`) |
| formas e `coordination_area` | Polygon pronto e os parâmetros | MultiPolygon, parâmetros em `parametros` |
| pontuais, `point`, `text`, `image` | Point | Point |
| `los`, `processed_los` | MultiLineString, LineString | MultiLineString |

Nos táticos, o desenho do Web vai para `geom_desenho` (WKT) só como reserva. Forma paramétrica gravada como Point (arquivo antigo) é regenerada pelo centro e pelos parâmetros com `pyproj.Geod`.

**Camada: armazenar por tipo, apresentar por camada.** No EBGeo a camada do usuário é um atributo (`layerId`) sobre feições de qualquer tipo e geometria, e a pilha de desenho é fixa por TIPO; no QGIS a camada tem uma geometria e um esquema. O armazenamento é uma tabela por tipo, e `importador/arvore.py` apresenta o que o operador vê:

- grupo do atlas mutuamente exclusivo (o Web mostra um mapa por vez; o `currentMap` abre ligado);
- um grupo por mapa (`mapOrder` unido às chaves de `maps`) e um subgrupo por camada EBGeo em ordem de `order`: `visible` é o check, `opacity` vira `setOpacity` (multiplica a da feição, como no Web), `locked` vira `setReadOnly`;
- no subgrupo, uma camada por tipo não vazio, apontando para a tabela do tipo com `subset` de `mapa` e `camada_id`;
- só o mapa ativo nasce com camadas; os outros ficam "(carregar)" e se criam ao ligar (`religar` refaz o sinal ao reabrir o projeto);
- ordem de desenho customizada pela pilha do Web, `schema.PILHA_DESENHO` (`reordenar`).

Grupo EBGeo não vira grupo da árvore, porque não é contêiner de desenho: grupo oculto e `visivel` falso viram condição na regra raiz do renderer e do rótulo (`condicao_exibir`). `bloqueado` por feição não tem par no QGIS e é só preservado.

## 3. Símbolos pontuais (motor)

Símbolo militar, medida de coordenação, símbolo de engenharia e declinação magnética.

- **Motor.** `motor/ebgeo-simbologia.js` é um bundle gerado do ebgeo_web (milsymbol 3.0.4, extensão brasileira, âncora, medidas, engenharia), carregado uma vez por sessão num `QJSEngine` (`motor/motor.py`; exige uma `QGuiApplication` viva). Build e diferenças em relação ao Web: `motor/build/README.md`. A engenharia mede texto no DOM no Web: roda intacta sobre `motor/build/dom-minimo.js`, com o texto medido pelo Python (`MedidorTexto`, `QFontMetricsF`). A declinação é Python (`motor/declinacao.py`, WMM2025).
- **Assado no campo.** `simbolos.renderizar` grava `svg` (base64), `largura_px`, `altura_px`, `ancora_dx`, `ancora_dy` e `svg_assinatura`. O estilo (`estilos_pontuais.py`) desenha um marcador SVG `'base64:' || "svg"`; sem `svg`, um marcador raster `'base64:' || "bitmap_b64"` (o PNG do `.ebgeo`, reserva do importador).
- **Assinatura.** md5 da lista FECHADA de campos que o gerador lê (`CAMPOS_DESENHO`), calculável por expressão nativa (`expressao_assinatura`): sem o plugin, SIDC editado à mão acende um retângulo e um x vermelhos. Com o plugin, `RegeneradorSvg` regrava em `featureAdded` e `attributeValueChanged`. Campo novo de desenho entra em `CAMPOS_DESENHO_OPCIONAIS`, para o calco antigo não acender o aviso. A versão do bundle não entra: regerar depois de atualizar o motor é ação explícita (`regenerar_camada`).
- **Âncora.** O marcador do QGIS é centrado; `ancora_dx` e `ancora_dy` deslocam o centro do desenho (pé do mastro no PC), girados com o símbolo como o `icon-offset` do MapLibre.

## 4. Linhas e áreas (expressões)

`estilos_taticos.py` (Linha de Coordenação, Linha de Limite, Seta, Frente Ocupada) e `estilos_area.py` (Área de Coordenação) montam Geometry Generators e rótulos a partir de `expressoes/*.exp`, que portam o algoritmo do Web. Editar vértices com as ferramentas nativas redesenha tudo.

- **Compositor.** Os `.exp` usam `@@NOME@@` para trechos comuns e blocos `@@SEJA@@ ... @@EM@@ ... @@FIM@@` com ligações (`:=` calculada uma vez, `::=` inlinada), compilados num único `with_variable`: o parse do QGIS dobra a cada nível de função aninhada (0,035 s com 16 `with_variable`, 9,2 s com 24) e se repete a cada clone do símbolo.
- **Catálogo** em `CATALOGO_LINHA` (glifo, se interrompe a linha, `span`, contínuo, cor padrão; obstáculo nasce verde).
- **Layout dos glifos**, como `resolveGlyphLayout` do Web: `footprint = tamanho × span`; espaçamento `max(pedido, footprint / 0,5)`; `n = floor((L − footprint) / espaçamento) + 1`, teto de 120 que alarga o passo; padrão centrado; `footprint > L` desenha só o eixo; contínuos com `n = max(1, round(L / período))`.
- **Linha de Limite:** tamanho efetivo limitado a `L × 0,5 / (instâncias × glifos × 1,8)`, vão centrado em cada `ratio` de `symbol_instances`.

## 5. Importador `.ebgeo`

`importador/leitor.py` (Python puro), `importador/escritor.py` (OGR), `importador/arvore.py` (projeto QGIS) e `importador/algoritmo.py`, o algoritmo de Processing "Importar arquivo .ebgeo": a gravação roda no processamento, e estilo e árvore no `postProcessAlgorithm`, na thread principal. Entram só as feições do mapa 2D; 360, 3D, briefings, temporal e comentários seguem crus em `ebgeo_documento`.

**Contêiner.** Cabeçalho `EBGXOR` (6 bytes em claro) e o ZIP com cada byte XOR `0xAA`; ZIP puro também é aceito. Dentro, `data.json` e `images/<id>.<ext>`, um blob por dono (feição, ícone, foto). Foto até a 2.4 vem inline como data URL; na 3.0 também por referência em `images/`.

**Versões.** Aceita de 1.3 a 3.0 em `version`, `schemaVersion` e `atlas.schemaVersion`, espelho do portão do Web, e recusa acima pedindo para atualizar o plugin. A 2.2 pode trazer o balde legado `barrier_lines`; a 2.3 traz `coordination_lines`; a 2.4 grava `anchor` e `iconOffset` na medida; a 3.0 traz `engineering_symbols`, `iconOffset` no símbolo militar e foto por referência.

**Regras e armadilhas:**

- o BALDE decide o tipo, nunca `properties.source` (`processed_los` traz `source: "los"`); a identidade é `properties.id`, e o `id` de topo é instável;
- `barrier_lines` vira Linha de Coordenação 290199; balde ausente é normal, desconhecido é ignorado com aviso, `coordenadas` é efêmero;
- `mapOrder` pode vir vazio; nome de mapa é string arbitrária e chave em tudo, por isso é coluna, nunca nome de tabela;
- MIME pelos bytes mágicos (JPEG gravado como `.png` antes de 2026-08-24); id de imagem duplicado recusa o arquivo;
- bitmap ausente em símbolo é normal (o motor redesenha); ausência de `image`, ícone ou foto é perda e vira aviso;
- coordenada nula ou não finita descarta a feição com log; salto de longitude acima de 180° é desembrulhado;
- teto contra bomba de ZIP: 512 MB descompactados, 1 GB de arquivo;
- o raio da elipse é tratado em km, unidade inferida das fixtures e não lida no gerador do Web;
- a conferência relê o GeoPackage gravado, nunca o `Relatorio` do escritor.

## 6. Unidades e zoom

- **Âncora de zoom do Web:** `createdAtZoom` (`created_zoom`) e `zoomCorrectionEnabled` (`zoom_corr`, padrão ligado). Ligada, o desenho fica preso ao TERRENO (ícone `min(10, size × 2^(zoom − createdAtZoom))`); desligada, à TELA. `created_zoom` nulo ou 0 é "sem âncora".
- **Pixel do Web** vira 0,2646 mm de papel (`MM_POR_PX`, 96 dpi); `lineWidth` é px fixo na tela.
- **Metros por pixel no zoom z:** `78271,517 × cos(lat) / 2^z` (`zoom.py`, mundo de 512 px do MapLibre). Em aberto: o KMZ do ebgeo_web usa a convenção de 256 px, e falta medir lado a lado qual reproduz a tela.
- **Escala de terreno** (`expressoes/_escala_terreno.exp`): `@map_scale` está nas unidades do SRC do mapa (em EPSG:3857 é a de terreno dividida por `cos(lat)`, 8 % a 23° S), então a expressão mede o fator do SRC na feição, e em SRC geográfico desfaz a conta do `QgsScaleCalculator`. Táticos, áreas e pontuais independem do SRC do projeto.
- **Projeção dos táticos:** Transversa de Mercator local esférica (R do turf, 6.371.008,8 m) no centroide arredondado a 0,1° (`expressoes/_projecao.exp`), onde 1 m do plano é 1 m de terreno. A variante EPSG:3857 com `k = 1 / cos(lat)` segue em `PROJECAO = '3857'`.
- **Formas comuns** (`estilos_formas.py`): com âncora, metros (`MetersInMapUnits`); sem âncora, mm. A opacidade da forma vale só para o preenchimento.
- **Na criação** (`ferramentas.py`), o zoom equivalente do canvas (`zoom.zoom_do_canvas`) dá os tamanhos iniciais do Web: glifo da Linha de Coordenação `max(0,03, 2^(16−z) × 0,03)` km, da Linha de Limite `max(0,05, 2^(16−z) × 0,05)` km, seta `max(50, 2^(16−z) × 25)` m.

## 7. Estilo salvo e atualização ao abrir

O estilo de cada tabela vai como padrão para o `layer_styles` do GeoPackage, e é isso que o faz abrir desenhado sem o plugin. Ele fica velho quando o código dos estilos muda, então `calco.py` grava na descrição a marca `EBGeo Desktop: estilo do calco` e a impressão digital do estilo gerado (md5 do QML de simbologia e rótulos, sem as chaves aleatórias). Ao abrir, `Calco.atualizar_estilo` refaz e regrava o estilo do plugin de impressão diferente; estilo do operador (outro nome, outra descrição ou sem a regra de `visivel`) e camada com estilo mudado no projeto ficam intocados. `DESCRICOES_ANTIGAS` reconhece o que o plugin gravava antes da marca. Não há número de versão para subir.

## 8. Armadilhas do QGIS 4

- Enums do QGIS sem escopo funcionam; enums do Qt sem escopo (`QEvent.MouseMove`, `QFont.Bold`) dão `AttributeError`.
- `qgis.PyQt.QtQml` não existe: importe `PyQt6.QtQml`. Não há `pyrcc6`: ícone novo vai por caminho de arquivo (`icones/`).
- `QSvgRenderer` ignora `dominant-baseline` e `dy`; o bundle reescreve o `y`.
- Coluna JSON gravada pelo QGIS: passe o objeto, não o texto, ou sai uma string JSON escapada (`schema.valor_json_para_qgis`). Na leitura ela chega como lista na camada do importador e como texto na aberta à mão, e `from_json` de uma lista dá nulo sem erro: as expressões testam `array_length` antes.

## 9. Alternativas descartadas

| Alternativa | Por quê |
|---|---|
| Symbol layer ou renderer Python | sem o plugin some, ou é descartado em silêncio ao recarregar |
| Estilo vivo com `@qgsfunction` | sem o plugin o ponto vira marcador de reserva e o Geometry Generator não desenha |
| QtWebEngine ou Node embarcado | bindings ausentes no instalador do QGIS 4; processo externo |
| SVGs estáticos (Esri, DISA) | sem amplificador de texto livre nem extensão brasileira |
| Pacotes PyPI (`milsymbol`, `military-symbol`) | sem amplificadores ou só APP-6, e exigem `pip` |
| mil-sym-ts para os táticos | bundle de 7,7 MB, geometria presa à escala, glifos explodidos |
| Fonte TTF ou PNG externo por caminho | não portáveis |
| Regras por faixa de escala | triplicam o estilo e o símbolo salta de tamanho |
| Camada QGIS por camada EBGeo e geometria | inverte a pilha do Web e exige esquema união |
| Portar a engenharia para Python | duplicaria a fonte; o DOM mínimo roda o código do Web |

## 10. Testes

Com o Python do QGIS 4 (o `python-qgis.bat` da pasta `bin` da instalação), da raiz do repositório:

```
python-qgis.bat EBGeo/Calco/testes/test_importador.py
```

Cada `testes/test_*.py` roda sozinho, e o cabeçalho diz o que prova. A conferência relê o que foi gravado, e cada régua é provada contra um pior caso que tem de reprovar.

| Variável | Uso |
|---|---|
| `EBGEO_FIXTURES` | fixtures `.ebgeo` (01 a 05 da linha 2.x, a 01 é o pior caso; 06 da 3.0); padrão `../_ebgeo_dados_teste` ao lado do repositório |
| `EBGEO_WEB` | checkout do ebgeo_web: build e paridade do motor (`test_motor.py`, Chromium do Playwright), azimute, estilos pontuais; `test_area_coordenacao.py` aceita esta ou a seguinte |
| `EBGEO_WEB_DIR` | ebgeo_web para a paridade de geometria das linhas (`test_estilos_taticos.py`, `test_linha_coordenacao_vii.py`) |
| `EBGEO_NODE` | executável do node, quando o `python-qgis.bat` o tira do PATH |
| `EBGEO_TESTE_SAIDA` | pasta dos PNG de conferência (padrão: temporária) |

Sem as variáveis do Web, os testes de paridade são pulados e os demais rodam.
