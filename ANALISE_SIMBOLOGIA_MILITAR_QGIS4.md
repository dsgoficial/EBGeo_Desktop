# Simbologia militar no EBGeo Desktop (QGIS 4): análise

Análise de 2026-10-04 para o branch `qgis4` do plugin EBGeo Desktop (dsgoficial/EBGeo_Desktop). O objetivo é dar ao QGIS 4 a capacidade de DESENHAR a simbologia militar que hoje existe no EBGeo Web (1cgeo/ebgeo_web, privado): símbolo militar por SIDC, Linha de Limite, medidas de coordenação, símbolos de engenharia, Linha de Coordenação, e as companheiras Seta, Frente Ocupada e Declinação Magnética. O documento irmão, `ANALISE_IMPORTACAO_EBGEO.md`, trata de abrir o `.ebgeo` no QGIS, e os dois partilham o mesmo modelo de dados: o que se importa se edita com as mesmas ferramentas, e o que se desenha no Desktop pode um dia voltar ao Web.

**Como foi feito.** Quatro análises paralelas: o código das 8 ferramentas militares do `ebgeo_web` (branch `main`, 33.076 linhas em 78 arquivos de `frontend/src/js/military_tools/`, catálogos contados importando os módulos em node); o plugin no branch `qgis4` e nos branches `master`, `feature/military_simbology_tools` e `qgis2.18`; o formato `.ebgeo`; e o estado da arte do QGIS, com fontes na web. As medidas que decidem a arquitetura foram refeitas no Python do QGIS 4.0.0 instalado (seção 10). Caminhos de código são relativos à raiz de cada repositório.

---

## 1. Resumo para decisão

1. **O plugin não desenha simbologia militar hoje.** O módulo `EBGeo/MilitarySimbologyTools` cria um GeoPackage com camadas vazias e estilos QML. Os símbolos pontuais são um PNG externo apontado por caminho de arquivo (`caminho_imagem`), sem SIDC; a imagem quebra em outra máquina. Há defeitos de leitura nos estilos (campos que não existem) e não há ferramenta de captura.
2. **As duas peças difíceis já estão provadas no QGIS 4.0.0.**
   - **Símbolo pontual:** o milsymbol 3.0.4, o mesmo motor do EBGeo Web, roda no `QJSEngine` do PyQt6 que vem com o QGIS 4 (carga 0,25 s; 76 ms no primeiro símbolo e 4 a 10 ms nos seguintes). O SVG gerado, gravado num campo do GeoPackage e desenhado por um marcador SVG nativo com caminho `'base64:' || "svg"`, reabre num QGIS sem o plugin com o estilo salvo no próprio arquivo.
   - **Linha com glifo repetido:** uma expressão nativa de Geometry Generator reproduz a Linha de Barreiras (290199) do Web com as mesmas regras: losangos que interrompem a linha, padrão centrado, tamanho no máximo metade do espaçamento, teto de 120 glifos e linha pura quando o glifo não cabe. Sem Python, sem plugin, e o desenho acompanha a edição de vértices feita com as ferramentas nativas do QGIS.
3. **Recomendação: "nativo e assado".** Linhas táticas desenhadas por estilo nativo (expressões) a partir do eixo e dos atributos; símbolos pontuais gerados pelo plugin e "assados" como SVG num campo. Tudo persiste no GeoPackage com `layer_styles`, abre em qualquer QGIS sem o plugin, sai vetorial no PDF e não depende de instalar nada no Windows.
4. **Uma fonte de verdade entre Web e Desktop.** Os geradores de símbolo pontual do Web (milsymbol mais o pós-processamento brasileiro, e o gerador das medidas de coordenação) podem rodar no `QJSEngine` empacotados num único arquivo JS gerado a partir do `ebgeo_web`. Assim a extensão brasileira não é portada à mão nem diverge.
5. **O custo está nos detalhes, não na arquitetura.** O que pesa: os 23 itens de engenharia (medem texto no DOM), a interface do construtor de SIDC (504 ícones, 225 modificadores 1, 99 modificadores 2 e o catálogo brasileiro) e as alças de edição do Web (mover o escalão ao longo do limite, largura da seta).

---

## 2. O que existe no plugin hoje

### 2.1 Arquitetura

- Entrada em `EBGeo/__init__.py` (`classFactory`) e `EBGeo/ebgeo.py`. O `ebgeo.py:5` faz `sys.path.append` da pasta do plugin, por isso há imports absolutos (`from MilitarySimbologyTools.view...`): funciona, mas é frágil.
- Um menu "EBGeo" com ~24 ações e uma toolbar "EBGeo" vazia. Ferramentas de mapa derivam de `QgsMapToolEmitPoint`, `QgsMapToolIdentifyFeature` ou `QgsMapTool`; diálogos e docks por `uic.loadUiType` (28 `.ui`).
- Um provider de Processing (`EBGeo/Processings/provider.py`, id `EBGeoProvider`, 11 algoritmos), que é o lugar natural do importador `.ebgeo` e de algoritmos de lote.
- Vários módulos são importados já no `loadTools`: um erro de import em qualquer um derruba o plugin inteiro.

### 2.2 MilitarySimbologyTools no `qgis4`

Fluxo: uma janela solta (não um dock) com três botões, Criar, Adicionar em existente e Abrir existente, e um link para o Portal de Simbologia Militar. Criar copia o template `model/templates/dataBase.gpkg` (3,3 MB, EPSG:3857, estilos em `layer_styles`), deixa o usuário escolher e duplicar camadas e aplica o QML de `model/styles/`.

| Camada | Geometria | O que o estilo desenha |
|---|---|---|
| `limite_entre_fracoes` | Linha | escalão no meio da linha por FontMarker Arial (`X X X`, `I I`), 7 escalões, vão aberto com `difference(buffer(...))`, rótulos de cada lado |
| `linha_de_controle` | Linha | 38 tipos (LP, LC, LCt, LAADA, LAT, LAPA, LET, LCP, praia, saída de praia, região de lançamento...), ganchos nas pontas, 41 rótulos |
| `coord_ap_fogo` | Linha | 6 tipos (LSAA, LCAF, Área de Fogo Livre, LCF, ACF, Área de Fogo Proibido) |
| `eixo_de_direcao` | Linha | 6 tipos (eixo de progressão, direção de ataque principal e secundária, EPS, aeromóvel, eixo de helicópteros), ArrowLine |
| `fortificacoes_pf` | Polígono | zona fortificada e ponto forte com escalão (22 escalões, 67 Geometry Generators) |
| `obstaculos` | Linha | 7 tipos: cerca simples e dupla, linha de barreiras, concertina simples, dupla e tripla, sapa; MarkerLine a cada 150 m |
| `seta_situacao` | Linha | frente ocupada, sentido de deslocamento, provável mudança de direção |
| `simbolos_pontos` | Ponto | **PNG externo** pelo caminho em `caminho_imagem` (`TEXT(30)`), senão um ponto de interrogação |

Defeitos conferidos no código:

- `style_limite_entre_fracoes.qml` usa os campos `Rot_ESQ` (12 vezes) e `Rot_DIR`, que não existem na tabela.
- `style_fort_pontos_fortes.qml` filtra por `"escalao"` (25 vezes) e o campo é `Escalão`; usa `Borda`, que a tabela não tem. Quebra provável, lida no XML e não renderizada.
- `Processings/simbmilLoader.py:62` grava em `indexFromName('path')`, mas o campo é `caminho_imagem`: o algoritmo "Carregar Simbologia Militar" não grava nada.
- `MilitarySimbologyTools/resources.py` e `resources.qrc` têm marcadores de conflito de merge (`<<<<<<<`); não são importados por ninguém.
- As distâncias dos Geometry Generators (110, 175, 200, 300, 500, 700) estão em unidades do SRC: o vão do escalão é fixo em metros e fica errado fora da escala para a qual foi desenhado.
- `selectLayersInterface.py:407` põe `simbolos_pontos` na categoria "Fortificações" porque o nome contém "pontos".
- "Abrir existente" faz `QgsProject.instance().read(...)` quando o GPKG tem projeto embutido, o que substitui o projeto aberto sem perguntar (`baseDeDados.py:113-142`).

### 2.3 Acervo legado nos outros branches

- **Commit 9a2f17e (2023-09-05):** o template tinha 26 camadas de calco, entre elas `tropa_a/tropa_i`, um símbolo de unidade montado 100% por QML (arma com 46 valores, especialidade 49, escalão 24, designação, subordinação; 126 regras, 42 SVG embutidos). Foi trocado em c93afb7 (2023-09-12) pelo PNG. Usava fontes Bodoni MT e Dingbats, não portáveis.
- **`feature/military_simbology_tools`** (enginesam, 2 commits de 2024-11-14 e 2024-11-21 sobre `634631f`, PR #43 aberto e nunca mergeado; **apagado em 2026-10-04**, ponta `0c4a2fbcfffa7b44d9d34ae06bdf01959728cf2b`, recuperável pelo `refs/pull/43/head`). Mudava só o `listName` de `baseDeDados.py` e trocava o template por outro de 15 camadas vazias (EPSG:3857, exceto `simbolos` em 4326), com estilos em `layer_styles`. Esquema incompatível com o `qgis4` (`limite`, `coord_apoio_fogo`, campos `Buffer`/`Width` no lugar de `Borda`). O que ele trazia e o que fica dele:

  | Camada do branch | Conteúdo | Destino |
  |---|---|---|
  | `alvos` (Point) | concentração, explosão nuclear e **barragens com largura real no terreno**: Br Gp 155 mm = 629, Br Gp 105 mm = 415, Br Bia 155 mm / Pel Mrt P ou Me (6 peças) = 307,5, Br Bia 105 mm / Pel Mrt Me (4 peças) = 200, em unidades de mapa do EPSG:3857 | **ideia boa, sem par no Web nem no `qgis4`**: barragem como marcador em metros de terreno pelo tipo de arma. Os valores precisam ser conferidos no manual de artilharia e convertidos de unidade 3857 para metro (em 3857 o metro vale `1/cos(lat)` unidades, então 629 desenha cerca de 545 m a 30° S) |
  | `minas` (5 tipos: qualquer, antipessoal, anticarro, arame de tração, armadilha), `campos_minados` (3) | SVG embutido de tamanho fixo em mm | o Web já cobre (catálogo de medidas: mina de qualquer tipo, antipessoal, anticarro, armadilha, área minada, indicação pontual de campo minado); só **arame de tração** falta no Web |
  | `ponto_coordenacao` (coordenação, controle, ligação, junção, outros) | marcadores simples | o Web tem Ponto de Coordenação e Ponto de Ligação; **Ponto de Junção** e Ponto de Controle terrestre faltam no Web |
  | `fortificacoes` (1,7 MB de QML, 322 Geometry Generators, 615 marcadores) | ponto forte com escalão e zona fortificada, cada regra triplicada por faixa de escala | não aproveitar: é o mesmo conteúdo do `fortificacoes_pf` do `qgis4` |
  | `fumaca`, `objetivo`, `barreiras`, `obstaculos` (Point) | um SVG fixo cada, sem atributo de tipo | não aproveitar: marcadores provisórios |
  | todas as linhas | regras repetidas para 0 a 25.000, 25.000 a 50.000 e acima de 50.000, com tamanhos diferentes em cada faixa | **ideia ruim, a evitar**: três degraus de escala triplicam o estilo e ainda saltam de tamanho; a seção 5.4 resolve com tamanho em terreno ou `@map_scale` contínuo |
- **`qgis2.18`:** 191 SVGs de símbolos MD33 em `MilitarySimbologyTools/model/symbols/`.

**Leitura:** o desenho por estilo QML nativo, que o plugin já usa nas linhas, é o caminho certo e o mesmo que o estado da arte recomenda. O que falta é (a) ligar o tamanho à escala de forma correta, (b) trocar o PNG externo por SIDC gerado e (c) dar paridade com o modelo de dados do Web.

### 2.4 Estado do porte para o QGIS 4 (relevante para o trabalho novo)

Medido no QGIS 4.0.0:

- Enums QGIS sem escopo (`QgsWkbTypes.Polygon`, `QgsVectorFileWriter.NoError`, `QgsLayerTreeNode.NodeGroup`) **ainda funcionam**.
- Enums Qt sem escopo **quebram** com `AttributeError`: `QEvent.MouseMove`, `QLineEdit.Normal`, `QFont.Bold`. Ocorrem em `measureTool/measureTool.py:157-184`, `AreaRange/areaRange.py:96,105,121,150`, `AzimuthDistance/azimuthTool.py:63,73`, `Processings/launchNOAA.py:307`, `HideToolbar/hideToolbar.py:64,68` e `Protector/protector.py:9`. Alcance de armamento, Azimute e distância, Medição durante aquisição, Simplificar Interface e o Lançamento Paraquedista NOAA falham ao chegar nessas linhas.
- `qgis.PyQt.QtQml` **não existe** no shim; é preciso `from PyQt6.QtQml import QJSEngine` (com fallback para PyQt5 se o plugin quiser rodar no QGIS 3).
- Não há `pyrcc6`. O `resources_rc.py` gerado pelo pyrcc5 ainda carrega, mas não se regenera: ícone novo vai por caminho de arquivo.
- `metadata.txt` usa `version=2.3.1`, a mesma do `master` (QGIS 3); o guia de migração recomenda `qgisMaximumVersion=4.99`, e `supportsQt6` deixou de ser usado.
- `.dev/setup_dev_windows.bat` aponta para o perfil `QGIS3`. Para desenvolver no QGIS 4 o plugin foi ligado por junção em `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\EBGeo`, apontando para `EBGeo_Desktop/EBGeo` (mesmo padrão do DsgTools).

---

## 3. Como o EBGeo Web desenha (o alvo da paridade)

O grupo "Militar" da barra (`frontend/src/js/toolbar/toolbar.constants.js:150-170`) tem 8 ferramentas. Não há ferramenta própria de eixo de progressão (é a Seta), de área tática (é o polígono comum com hachura) nem de calco.

| Ferramenta (atalho) | Tipo / balde | Geometria guardada | Fonte do desenho | Família de render |
|---|---|---|---|---|
| Símbolo Militar (M) | `military_symbol` / `military_symbols` | Point | `sidc` (30 dígitos) e 16 amplificadores | bitmap gerado |
| Medida de Coordenação (K) | `coordination_measure` / `coordination_measures` | Point | `pointCode`, `echelonCode`, 7 textos, `status` | bitmap gerado |
| Símbolos de Engenharia | `engineering_symbol` / `engineering_symbols` | Point | `pointCode`, `engineering{variant, values}` | bitmap gerado |
| Declinação Magnética (W) | `magnetic_declination` / `magnetic_declinations` | Point | ângulos WMM e convergência | bitmap gerado |
| Linha de Limite (D) | `boundary` / `boundarys` | MultiLineString | `baseCoordinates`, `echelon`, `symbol_instances` | geometria derivada (turf) |
| Linha de Coordenação (Y) | `coordination_line` / `coordination_lines` | MultiLineString ou MultiPolygon | `baseCoordinates`, `symbol_code` | geometria derivada |
| Seta (S) | `arrow` / `arrows` | Polygon ou MultiPolygon | `baseCoordinates`, `width` (m) | geometria derivada |
| Frente Ocupada (F) | `occupied_front` / `occupied_fronts` | MultiLineString | `baseCoordinates` (3 pontos) | geometria derivada |

Registro de tipos em `frontend/src/js/store/feature-type.registry.js:114-271`; atalhos em `keyboard/keyboard-shortcuts.js:286-308`.

**A regra que organiza o porte:** nos quatro bitmaps, o PNG é cache e as propriedades bastam para regenerar; nas quatro linhas, a fonte é o eixo `baseCoordinates` e a geometria gravada é só o desenho num zoom. No QGIS, portanto, a camada guarda o EIXO e os atributos, e o desenho é estilo.

### 3.1 Âncora de zoom (vale para quase todas)

- Par `createdAtZoom` (uma casa decimal) e `zoomCorrectionEnabled` (padrão `true`).
- **Ligada, o desenho fica preso ao TERRENO**: o ícone vale `min(10, size × 2^(zoom − createdAtZoom))` (`layers/styles/zoom-expression.js:349-382`), e nas linhas o traço e o texto crescem por `2^(z − z0)` enquanto os glifos, medidos em km, ficam fixos no chão (`tool_manager/helpers/boundary-zoom.model.js`, `coordination-line-zoom.model.js:144-171`).
- **Desligada, preso à TELA**: o ícone fica em `size`, e os km dos glifos encolhem por `2^(z0 − z)`.
- `createdAtZoom = 0` significa "nunca ancorado".
- O manual do operador (`frontend/public/docs/README.md`) descreve a correção de zoom ao contrário do código ("manter o tamanho visual constante ligando"), o que vale corrigir no Web.

**No QGIS:** ligada vira tamanho em metros no terreno (`RenderMetersInMapUnits` ou expressão em unidades de mapa); desligada vira milímetros na página (`RenderMillimeters`, ou metros por `mm × @map_scale / 1000` dentro de uma expressão). As duas cabem numa expressão só: `if("zoom_corr", "tamanho_km" * 1000, "tamanho_mm" * @map_scale / 1000)`.

Para converter o `size` de um ícone vindo do Web em metros: `metros = size × largura_px × 78271,517 × cos(lat) / 2^createdAtZoom`, pela convenção de 512 px do MapLibre. O `ebgeo_web` usa a convenção de 256 px (`156543,03392`) no KMZ e no clipboard (`import_export/kmz/kml-geometry.js:201,442`). **Qual reproduz a tela não foi medido** (seção 11).

### 3.2 Símbolo Militar

- **Arquivos:** `military_symbol_tool/add_military_symbol_control.js` (padrões `:177-219`), `military_symbol_generator.js`, `brazilian_sidc_extension.js`, `brazilian_svg_postprocessing.js`, `brazilian_extension_catalog.js`, `military-symbol-anchor.js`, `text-modifiers-mapping.js`.
- **SIDC de 20 dígitos** (formato "10"): versão, contexto, identidade, conjunto, status, QG/FT/simulado, escalão, ícone (6), modificador 1 (2), modificador 2 (2). O `buildSIDC` fixa o contexto em "0".
- **Extensão brasileira, dígitos 21 a 30:** `"076"` mais 7 dígitos de um campo de 23 bits: `valor = entityExtension<<14 | isCommand<<13 | specialModifier<<10 | mod1Extension<<5 | mod2Extension` (`brazilian_sidc_extension.js:28-104`). Sem extensão, `0760000000`.
- **Render** (`generateSymbol`, `military_symbol_generator.js:212-304`):
  1. zera os códigos "falsos" brasileiros (terminados em 99) antes de chamar o milsymbol;
  2. `new ms.Symbol(sidc, {size: 50, frame: true, fill: true, strokeWidth: 3, colorMode: 'Light', fillColor?})`; o código nunca chama `ms.setStandard`, então desenha no padrão 2525 (o manual diz "App-6/2525");
  3. com amplificadores, redesenha e amplia a caixa pelo crescimento do viewBox, para o texto não encolher o quadro;
  4. pós-processamento brasileiro por substituição de texto no SVG: `graphicAdaptations` (101 de ícone, 8 de mod1, 9 de mod2), `labelMappings` (74, 57, 18; ex.: `SF` vira `Cmdos`), extensões anexadas (25 ícones com 62 variantes, 4 mod1 com 40, 3 mod2 com 17), modificadores especiais (Blindado, Mecanizado, Motorizado, Defesa Aérea), linha de Comando, cores da barra de engajamento;
  5. rasteriza com razão de pixel 2 e calcula `iconOffset` pela âncora do milsymbol (`getAnchor`, `getSize`): o pé do mastro no Posto de Comando.
- **Catálogo do seletor** (`military_symbol_tool/data/*.js`): 11 conjuntos, **504 ícones, 225 modificadores 1, 99 modificadores 2**; chave (código, extensão).
- **Interface:** um clique cria; modal com abas Símbolo, Texto e Engajamento, SIDC digitado com validação, cor, galeria "Símbolos do Mapa"; painel com Tamanho 0,5 a 3, Correção de Zoom, Zoom de Referência, Opacidade, Rotação.

### 3.3 Medida de Coordenação

- **Arquivos:** `coordination_measure_tool/coordination_measure_generator.js`, `coordination_points_catalog.js`, `familias-de-escalao.js`.
- **Catálogo:** **130 entradas** (66 pontos-base, 12 de suprimento, 52 de escalão: 13 escalões × Núcleo, Núcleo FT, Escalão, Escalão FT), em 15 categorias. Cada entrada traz o SVG pronto; o catálogo carrega sem DOM.
- **Render:** SVG do catálogo; branco vira `fill="none"`; com `fillColor`, preto vira a cor; Núcleo não ocupado ganha `stroke-dasharray="58,22"` no contorno; textos em posições fixas com largura ESTIMADA (`n × fs × 0,6`, ou 0,7 em negrito), sem DOM; âncora `center` (114) ou `bottom` (16) e `iconOffset`.

### 3.4 Símbolos de Engenharia (C 5-36, tabela 6-4)

- **Arquivos:** `engineering_symbol_tool/engineering_catalog.js` (23 itens, 34 variantes), `engineering_generator.js`, `engineering_drawing.js`, `engineering_fields.js`. O controle herda o da medida. Não existe no branch `ebgeo2.0`.
- **Render:** corpo SVG por variante num viewBox 240×200; rampas com número de marcas por faixa de declividade; vau e balsa procedurais; folhagem; fundo branco opcional. **Mede texto no DOM** (`getComputedTextLength` para reduzir a fonte, `getBBox` para sublinhado e recorte): é o único gerador que não roda puro.

### 3.5 Linha de Coordenação (MD33)

- **Arquivos:** `coordination_line_tool/coordination_line_catalog.js` (`LINEAR_SYMBOLS`, `:53-149`), `add_coordination_line_geometry.js`, modelo de zoom.
- **Catálogo: 10 símbolos** (o manual do operador lista 5):

| Código | Nome | Glifo | Interrompe a linha | Extras |
|---|---|---|---|---|
| 290100 | Linha de obstáculos | peak | sim | |
| 290199 | Linha de barreiras (padrão) | diamond | sim | |
| 290202 | Fosso anticarro | dente contínuo | sim | preenchido, profundidade 0,82 |
| 290302 | Cerca de arame | asterisk | não | |
| 290303 | Cerca de arame dupla | double-asterisk | não | span 1,6 |
| 290307 | Concertina | coil | não | span 0,8 |
| 290308 | Concertina dupla | coil-double | não | trilho, gap 0,7 |
| 290309 | Concertina tripla | coil-triple | não | trilho, gap 1,35 |
| 290999-01 | Sapa | zigue-zague contínuo | sim | profundidade 0,6 |
| 290999-02 | Trincheira | zigue-zague contínuo | sim | profundidade 0,7, patamar 0,41 |

- **Layout** (`resolveGlyphLayout`, modelo `:228-257`): `footprint = size × spanRatio`; `espaçamento = max(pedido, footprint / 0,5)` (tamanho no máximo metade do espaçamento, senão a linha some); `n = floor((L − footprint) / espaçamento) + 1`; teto de 120 glifos, que alarga o passo; início centrado `(L − (n−1) × espaçamento) / 2`; `footprint > L` desenha só o eixo. Contínuos: `n = max(1, round(L / período))`.
- **Glifo:** moldura pela corda entre `along(c − s/2)` e `along(c + s/2)`; "esquerda" é `rumo − 90°` (por isso "Inverter Linha" troca o lado). Trilhos por deslocamento geodésico na bissetriz com miter até 4.
- **Corte do eixo:** sempre por distância, semântica de `turf.lineSliceAlong`.
- **Criação:** `symbol_size = max(0,03, 2^(16−z) × 0,03)` km e `symbol_spacing = 3 × size`; o painel mostra metros e guarda km.

### 3.6 Linha de Limite

- **Arquivos:** `boundary_tool/add_boundary_geometry.js`, `add_boundary_control.js` (padrões `:165-195`), `boundary-split.js`.
- **Dados:** `echelon` é uma string de glifos `X`, `I`, `o` (12 opções de `XXXXXX` a `o`; o código não associa letra a escalão nominal); `symbol_instances[{ratio, showLabels}]` (1 a 6 repetições); `symbol_size` em km (criação `max(0,05, 2^(16−z) × 0,05)`); `text_top`, `text_bottom`, `text_size` (35 px), `text_distance_ratio` (0,9), `text_north_facing`.
- **Render:** tamanho efetivo limitado a `L × 0,5 / (instâncias × glifos × 1,8)`; vão de `n × size × 1,5 × 1,2` centrado em `L × ratio`, vãos sobrepostos fundidos; glifos espaçados `1,5 × size`: `X` são duas retas a ±45° do rumo, `I` é um traço perpendicular de `±size/1,5`, `o` é um círculo de raio `size/4`; rótulos à esquerda e à direita a `size × text_distance_ratio`, girados com a linha e mantidos de pé, ou voltados ao norte. Os círculos e rótulos não são gravados no arquivo.
- **Interface:** alças para mover cada instância ao longo da linha, mudar o tamanho e a distância do texto; "Cortar Linha de Limite".

### 3.7 Seta

- **Dados:** `baseCoordinates`, `width` em **metros** (criação `max(50, 2^(16−z) × 25)`, depois fixa), `headLengthRatio` 1,5, `showArrowHead`, `doubleHeaded`, `airmobile`, `airmobilePosition` 0,7, cores e opacidades; seta combinada com `branches[]`.
- **Render:** dois trilhos a `±width/2`; ponta com base `2,5 × width` e comprimento `base × headLengthRatio` na direção do último segmento; duas pontas limitadas ao comprimento do eixo; aeromóvel cortado em `L × airmobilePosition` com trilhos cruzados; combinada por união.

### 3.8 Frente Ocupada

- `baseCoordinates = [p1, p2, p3]`, p3 nasce a `rumo(p1→p2) + 50°`. Cada braço: reta até 60 %, gancho de `0,1 × d` a 225°, reta até a ponta, ponta com dois traços de `0,1 × d` a ±150°. São segmentos retos (o manual diz "curvas").

### 3.9 Declinação Magnética

- WMM pelo pacote `geomagnetism` (WMM2025) e convergência meridiana UTM; SVG 400×500 com setas NV, NQ e NM e legenda. O plugin já tem um WMM em Python (`EBGeo/auxiliar/geomag`), mas com o coeficiente **WMM-2020** (`WMM.COF`), vencido: trocar pelo WMM2025.

---

## 4. Estado da arte no QGIS

### 4.1 Plugins existentes

| Plugin | Licença / atividade | QGIS 4 | Abordagem | Táticos |
|---|---|---|---|---|
| **Military Cartography Tools** (github.com/kattapraveen/MilitaryCartographyTools) | GPL-2.0, último push 2026-09-30 | sim, 3.44 a 4.99 | milsymbol 3.0.4 vendorizado no `QJSEngine`, `@qgsfunction` `mct_sidc_svg` devolvendo `base64:` | sim, boa parte do 2525D/E Apêndice H, por Geometry Generator com 105 funções Python `mct_*` |
| QGIS APP-6(D) (intelligeo) | GPL-2, 0.1.7 de 2026-05 | não declara | milsymbol no `QJSEngine` + renderer Python + SVG em pasta temporária | não |
| MIL-STD-2525 (planetfederal) | GPL-2.0, parado desde 2020 | não | renderer Python compondo ~3.795 SVGs DISA | não |
| QGIS-Military-Symbols (nwroyer) | MIT, 2025-04 | não | symbol layer Python + pacote PyPI `military-symbol` | não |
| THW Toolbox | | | 983 SVGs, renderer categorizado nativo, "pacote portátil" GPKG + SVG | referência de portabilidade |

O Military Cartography Tools é a melhor referência de código para estudar e valida a escolha do `QJSEngine`. O ponto fraco dele é o mesmo que a recomendação deste documento evita: sem o plugin, as funções `mct_*` somem e o desenho some junto.

### 4.2 Motores de símbolo

- **milsymbol (JS, MIT, 3.0.4):** 2525C/D/E e APP-6 B/D/E, amplificadores de texto, `addIconParts` para extensões nacionais. É o motor do Web, então dá paridade.
- **milsymbol no PyPI (0.2.0):** tabela congelada sem amplificadores nem extensões; não serve.
- **military-symbol no PyPI (2.0.8):** só APP-6, só pontos, várias dependências que exigem `pip`.
- **QtWebEngine:** as DLLs do Qt estão no instalador standalone do QGIS 4.0.0, mas os bindings `PyQt6.QtWebEngine*` não (conferido na pasta do PyQt6). Descartado.
- **mil-sym-ts / mil-sym-java (Apache-2.0, v2.10.5 de 2026-09-18):** implementação de referência das "draw rules" do 2525D/E (AXIS1, AXIS2, LINE, AREA...) para gráficos táticos. O bundle web não carrega direto no `QJSEngine` (class fields, `async`); transpilado com esbuild para ES2016 e com um shim de medição de texto, carregou em 0,3 s e devolveu GeoJSON de eixo e de cercas, sem conferência de exatidão. A saída depende de escala e caixa, e os glifos vêm explodidos em segmentos.

### 4.3 Mecanismos de renderização no QGIS 4

| Mecanismo | Sem o plugin | Medido |
|---|---|---|
| Marcador SVG com caminho `base64:` vindo de campo | desenha | sim, nesta análise |
| Marcador raster com caminho `base64:` vindo de campo | desenha | sim, com os PNGs reais do `.ebgeo` |
| Geometry Generator com expressão nativa | desenha | sim, Linha de Barreiras completa |
| Função Python `@qgsfunction` no caminho do SVG | cai no marcador de reserva | sim (pesquisa) |
| Função Python no Geometry Generator | não desenha nada | sim (pesquisa) |
| Symbol layer Python customizado | **descartado em silêncio** ao recarregar (`QgsSymbolLayerUtils::loadSymbolLayer` devolve nulo) | sim (pesquisa) |
| Renderer Python customizado | volta ao renderer padrão | código-fonte |
| Project functions (Python no projeto) | só se o usuário habilitar macros | documentação |
| Blank segments por feição (novo no 4.0) | desenha | documentação |

Arrow, Marker Line e Hashed Line com intervalo, vértices e ângulo médio, `line_interpolate_point`, `line_interpolate_angle`, `line_substring`, `offset_curve`, `project`, `azimuth`, `make_polygon`, `buffer(..., 'flat')`, `generate_series` e `array_foreach` cobrem tudo o que as linhas do Web fazem.

---

## 5. Arquitetura recomendada: "nativo e assado"

### 5.1 Princípios

1. **A camada guarda o que o operador decidiu; o estilo deriva o desenho.** Linha tática guarda o eixo (LineString) e os atributos; símbolo pontual guarda o ponto, o SIDC e os amplificadores.
2. **Abrir sem o plugin é requisito.** O calco vai para outra OM por GeoPackage. Nada que desenha pode depender de código Python em tempo de renderização.
3. **Uma fonte de verdade com o Web.** Mesmos nomes de atributo do `.ebgeo` (no `props` e nas colunas promovidas), mesmos catálogos, mesmos geradores de símbolo pontual quando possível.
4. **Funciona offline e sem instalação.** Só o que vem no QGIS 4: `QJSEngine`, `QSvgRenderer`, pyproj, shapely, numpy, GDAL.

### 5.2 Modelo de dados (o "calco")

Um calco é um GeoPackage com uma tabela por tipo, o mesmo esquema do importador:

| Tabela | Geometria | Colunas específicas |
|---|---|---|
| `simbolo_militar` | Point | `sidc`, 16 amplificadores, `special_modifier`, `is_command`, `fill_color`, `size`, `rotation`, `opacity`, `zoom_corr`, `created_zoom`, `svg`, `svg_assinatura`, `ancora_dx`, `ancora_dy` |
| `medida_coordenacao` | Point | `point_code`, `echelon_code`, 7 textos, `status`, `fill_color`, ..., `svg`, `svg_assinatura` |
| `simbolo_engenharia` | Point | `point_code`, `engineering` (JSON), ..., `svg`, `svg_assinatura` |
| `declinacao_magnetica` | Point | `declination`, `convergence`, `calculation_date`, ..., `svg` |
| `linha_limite` | LineString (eixo) | `echelon`, `symbol_instances` (JSON) ou `ratio_1..6`, `symbol_size_km`, `text_top`, `text_bottom`, `text_size`, `text_distance_ratio`, `text_north_facing`, `color`, `line_width`, `opacity`, `zoom_corr`, `created_zoom` |
| `linha_coordenacao` | LineString (eixo) | `symbol_code`, `symbol_size_km`, `symbol_spacing_km`, `color`, `line_width`, `opacity`, `zoom_corr`, `created_zoom` |
| `seta` | LineString ou MultiLineString (eixo, um ramo por parte) | `width_m`, `head_length_ratio`, `show_arrow_head`, `double_headed`, `airmobile`, `airmobile_position`, `fill_color`, `line_color`, `line_width`, `fill_opacity`, `line_opacity` |
| `frente_ocupada` | LineString de 3 vértices | `color`, `line_width`, `opacity` |

Mais as colunas comuns do documento irmão (`ebgeo_id`, `mapa`, `camada_id`, `nome`, `descricao`, `visivel`, `bloqueado`, `props`). O CRS do GeoPackage é EPSG:4326, como o `.ebgeo`; as expressões projetam internamente (seção 5.4). Os QML ficam em `layer_styles` como estilo padrão.

### 5.3 Símbolos pontuais: gerar no plugin, assar no campo

```
SIDC + amplificadores ──► ebgeo-simbologia.js no QJSEngine ──► SVG ──► campo "svg" (base64)
                                                                        │
                                       marcador SVG nativo ◄── 'base64:' || "svg"
```

- **Motor:** um arquivo `ebgeo-simbologia.js` gerado a partir do `ebgeo_web` (esbuild, IIFE, alvo ES2016) com o milsymbol 3.0.4, `brazilian_sidc_extension.js`, `brazilian_svg_postprocessing.js`, o catálogo brasileiro, `military-symbol-anchor.js` e o gerador e catálogo das medidas de coordenação, expondo funções puras `gerarSimboloMilitar(props) → {svg, ancora}` e `gerarMedida(props) → {svg, ancora}`. O plugin carrega o arquivo uma vez num `QJSEngine` por sessão. Os catálogos do seletor (`data/*.js`) saem do mesmo bundle ou exportados para JSON no build.
- **Gatilho:** sinais `featureAdded` e `attributeValueChanged` da camada regeneram `svg` e `svg_assinatura` (hash dos campos que desenham, a mesma lista de exclusão de `layers/bitmap-drawing-signature.js`). Sem o plugin, o SVG fica velho se alguém editar o SIDC à mão: uma regra do estilo compara a assinatura e desenha um aviso (contorno vermelho) quando diverge.
- **Âncora:** o deslocamento do marcador SVG (`offset` definido por dado) recebe `ancora_dx`, `ancora_dy` calculados pelo `getAnchor` do milsymbol, para o pé do mastro do PC cair no ponto.
- **Tamanho:** `size` em metros quando `zoom_corr`, senão em mm; ver 3.1.
- **Engenharia:** é o único gerador que mede texto no DOM. Duas saídas: (a) injetar no `QJSEngine` um objeto Python com `medirTexto(texto, fonte, tamanho)` implementado com `QFontMetricsF` e trocar as chamadas `getComputedTextLength` e `getBBox` por ele no bundle; (b) portar os 23 itens para Python. A (a) mantém a fonte única.
- **Declinação:** gerador SVG simples (setas, arcos, legenda), portável para Python; WMM2025 no `auxiliar/geomag` existente.
- **Armadilha medida:** o `QSvgRenderer` ignora `dominant-baseline` e `dy`; só `transform` desloca o texto. Os trechos SVG da extensão brasileira usam `dominant-baseline="middle"` (13 ocorrências em `military_tools/`): o bundle precisa reescrever esses textos com o `y` ajustado (cerca de `+0,35 × font-size`) antes de entregar o SVG. O milsymbol só emite `dominant-baseline` quando o texto pede `alignmentBaseline`.
- **Saída vetorial:** o marcador SVG sai vetorial no PDF do layout.

### 5.4 Linhas táticas: estilo nativo a partir do eixo

Cada tipo tem um QML com Geometry Generators que leem o eixo e os atributos. A edição de vértices com as ferramentas nativas do QGIS redesenha tudo, e o arquivo abre sem o plugin.

**Projeção dentro da expressão.** O GeoPackage é EPSG:4326 e as distâncias do Web são geodésicas em km. A expressão projeta para EPSG:3857, onde o comprimento vale `metros / cos(lat)`, e corrige com `k = 1 / cos(lat do centroide)`. Para calcos de até dezenas de km o erro é desprezível; para linhas de centenas de km, trocar pela projeção UTM local ou aceitar o erro.

**Linha de Barreiras (290199), testada no QGIS 4.0.0:**

```
with_variable('k', 1 / cos(radians(y(centroid($geometry)))),
with_variable('g', transform($geometry, 'EPSG:4326', 'EPSG:3857'),
with_variable('L', length(@g),
with_variable('s', "symbol_size_km" * 1000 * @k,
with_variable('sp', max("symbol_spacing_km" * 1000 * @k, @s / 0.5),
with_variable('n', if(@s > @L, 0, min(120, floor((@L - @s) / @sp) + 1)),
with_variable('sp2', if(@n > 1 and floor((@L - @s) / @sp) + 1 > 120, (@L - @s) / (@n - 1), @sp),
with_variable('c0', (@L - (@n - 1) * @sp2) / 2,
transform(
  if(@n = 0, @g,
    collect_geometries(array_cat(
      array_filter(array_foreach(generate_series(0, @n),
        line_substring(@g,
          if(@element = 0, 0, @c0 + (@element - 1) * @sp2 + @s / 2),
          if(@element = @n, @L, @c0 + @element * @sp2 - @s / 2))), length(@element) > 0),
      array_foreach(generate_series(0, @n - 1),
        with_variable('a', line_interpolate_point(@g, @c0 + @element * @sp2 - @s / 2),
        with_variable('b', line_interpolate_point(@g, @c0 + @element * @sp2 + @s / 2),
        with_variable('az', azimuth(@a, @b),
        with_variable('m', make_point((x(@a) + x(@b)) / 2, (y(@a) + y(@b)) / 2),
        with_variable('h', distance(@a, @b) / 2,
          make_line(@a, project(@m, @h, @az - pi() / 2), @b, project(@m, @h, @az + pi() / 2), @a)))))))
    ))),
  'EPSG:3857', 'EPSG:4326')
))))))))
```

Resultado medido: linha de 20,41 km com glifo de 0,5 km e espaçamento de 1,5 km dá 14 losangos (o modelo do Web prevê 14); linha de 0,10 km dá só o eixo (prevê 0); linha de 1.925 km dá exatamente 120 losangos (teto). A primeira versão deixava duas peças de comprimento zero no caso do teto, e o `array_filter` as removeu. Desenho conferido em imagem: losangos interrompendo a linha, padrão centrado.

**Os outros símbolos lineares** seguem o mesmo esqueleto, trocando só a forma do glifo e o "interrompe ou não":

| Glifo | Expressão do glifo, a partir de `@a`, `@b`, `@m`, `@h`, `@az` |
|---|---|
| peak (290100) | `make_line(@a, project(@m, @h, @az - pi()/2), @b)` |
| asterisk (290302) | três `make_line` de raio `@h` a 0°, 60° e 120° do rumo, centrados em `@m` |
| double-asterisk (290303) | dois asteriscos a 27 % e 73 % do vão, raio `0,45 × @h` |
| coil (290307) | `make_ellipse(project(@m, 1.4*@h, @az - pi()/2), @h, 1.4*@h, degrees(@az), 16)` como anel |
| coil-double e coil-triple (290308, 290309) | o eixo mais trilhos por `offset_curve(@g, gap)`, com o laço entre eles |
| dentes contínuos (290202, 290999-01, 290999-02) | `generate_series` sobre o período `L / round(L / p)` com o V a `@az + pi()/2`; o fosso fecha o anel e vai num Geometry Generator de polígono |

Uma regra por `symbol_code` no renderer escolhe o Geometry Generator. Quando o glifo não interrompe, o primeiro termo do `array_cat` vira só `@g`.

**Linha de Limite.** Geometry Generator de linha para o eixo com os vãos (mesmo esqueleto, com o vão de `n × size × 1,5 × 1,2` centrado em cada `ratio`), outro para os traços `X` e `I` a partir de `line_interpolate_point` e `line_interpolate_angle`, e um de polígono para os `o` (`buffer(ponto, size/4)`). Os rótulos `text_top` e `text_bottom` vão por rotulagem com Geometry Generator de rótulo (ponto deslocado por `project(..., az ± pi()/2)`) e rotação definida por dado, mantida de pé. As instâncias (1 a 6) vêm de um array JSON lido por `from_json("symbol_instances")`. Isso substitui o estilo atual de `limite_entre_fracoes`, que tem o vão fixo em metros e campos inexistentes.

**Seta.** Geometry Generator de polígono: corpo por `offset_curve(@g, ±width/2)` unidos em anel, ponta por `project` do último vértice com base `2,5 × width` e comprimento `base × head_length_ratio`, segunda ponta se `double_headed`, X aeromóvel cortando em `airmobile_position`. Seta combinada: uma parte do MultiLineString por ramo e `collect_geometries` dos polígonos (ou `union`). A Arrow nativa do QGIS cobre os casos simples, mas não a cabeça de base `2,5 × width` nem o aeromóvel.

**Frente Ocupada.** Expressão direta sobre os 3 vértices: dois braços com reta até 60 %, gancho a 225°, reta até a ponta e os dois traços a ±150°.

**Unidades e escala.** Glifos e vãos em km de terreno quando `zoom_corr` (o padrão do Web). Para o modo preso à tela, a mesma expressão com `@s = "symbol_size_mm" * @map_scale / 1000 * @k`. Largura do traço em mm (`RenderMillimeters`), com conversão de px do Web por 0,26 mm/px.

**Custo.** O teto de 120 glifos protege o desenho. A expressão é avaliada por feição a cada renderização; não foi medido o tempo com centenas de linhas longas. Se pesar, o recurso de reserva é o mesmo do Web: o plugin calcula a geometria em Python (porte de `add_coordination_line_geometry.js` com `pyproj.Geod`) e grava numa coluna `geom_desenho`, e o estilo desenha a coluna.

### 5.5 Ferramentas de captura (a interface)

A ferramenta de captura só existe para dar a experiência do Web. O desenho em si vem do estilo.

- **Toolbar "Simbologia Militar"** com as 8 ferramentas e os atalhos do Web (M, K, D, Y, S, F, W) onde não colidirem com o QGIS.
- **Ferramentas lineares:** subclasse de `QgsMapToolDigitizeFeature` (ou captura nativa da camada com valores padrão por expressão). Na criação, preenche `created_zoom` a partir de `@map_scale`, `symbol_size_km = max(0,03, 2^(16 − z) × 0,03)` e o espaçamento como no Web. Clique direito finaliza, como no Web e no QGIS.
- **Ferramentas pontuais:** um clique cria com o SIDC padrão e abre o construtor.
- **Construtor de SIDC:** diálogo Qt com as abas do Web (Símbolo, Texto, Engajamento), campo SIDC com validação de 20 e 30 dígitos, galeria por categoria lida dos catálogos do bundle e pré-visualização pelo próprio `QSvgRenderer`. É a maior peça de interface.
- **Painel de propriedades:** dock que espelha os painéis do Web (tamanho, correção de zoom, rotação, opacidade, escalão, repetições, rótulos, símbolo da linha).
- **Alças do Web** (mover a instância do escalão, largura da seta, distância do texto): fase posterior, por `QgsMapTool` próprio sobre a feição selecionada. A edição de vértices já sai de graça pelo QGIS.
- **Converter e inverter:** "Inverter Linha" é inverter a ordem dos vértices (`reverse($geometry)` num campo calculado ou ação); "Converter para" troca a feição de tabela.

### 5.6 O que fazer com o módulo atual

O pedido do chefe é paridade com as ferramentas do Web. As camadas que só o Desktop tem (`linha_de_controle` com 38 tipos, `coord_ap_fogo`, `fortificacoes_pf`, `seta_situacao`) não têm par no Web. Três caminhos, para decisão:

| Caminho | Custo | Efeito |
|---|---|---|
| Substituir o módulo pelo calco novo | baixo | perde os 38 tipos de linha de controle e o apoio de fogo, que hoje funcionam parcialmente |
| Manter as camadas exclusivas no template, corrigindo os defeitos da seção 2.2 e trocando o vão fixo em metros pela regra de escala | médio | Desktop fica com mais tipos que o Web |
| Levar esses tipos também ao Web | alto | paridade total, fora deste pedido |

A recomendação é o segundo caminho: o calco novo cobre as 8 ferramentas do Web, e as camadas exclusivas do Desktop entram no mesmo GeoPackage, consertadas.

---

## 6. Alternativas descartadas

| Alternativa | Motivo |
|---|---|
| Symbol layer ou renderer Python customizado | some sem o plugin, ou é descartado em silêncio ao salvar; custo de Python por feição na renderização |
| Estilo vivo com `@qgsfunction` (como o MCT) | sem o plugin, ponto vira marcador de reserva e Geometry Generator não desenha |
| QtWebEngine ou Node embarcado | bindings ausentes no instalador standalone do QGIS 4; processo externo |
| SVGs estáticos Esri/DISA | repositório arquivado em 2024, só 2525D/APP-6D, composição de partes trabalhosa, sem amplificador de texto livre nem extensão brasileira |
| Pacotes PyPI (`milsymbol`, `military-symbol`) | sem amplificadores ou só APP-6, e exigem `pip` |
| mil-sym-ts para todos os táticos | bundle de 7,7 MB, shim de texto, geometria presa à escala, glifos explodidos; fica como referência normativa e como opção para gráficos complexos fora da paridade com o Web |
| Fonte TTF de símbolos (abordagem antiga, Bodoni MT e Dingbats) | não portável |

---

## 7. Riscos

| Risco | Mitigação |
|---|---|
| A extensão brasileira faz substituição exata de texto no SVG do milsymbol e quebra se o milsymbol mudar | travar a versão no bundle (3.0.4, a do Web) e testar o bundle com uma amostra de SIDCs brasileiros contra PNGs de referência gerados no Web |
| `QSvgRenderer` ignora `dominant-baseline` e `dy` | reescrever o `y` no bundle; teste visual com `labelMappings` |
| SVG velho sem o plugin | `svg_assinatura` e regra de aviso no estilo |
| Desempenho de expressão por feição | teto de 120 glifos; medir com centenas de linhas; reserva `geom_desenho` |
| Fator px para metros entre Web e QGIS (512 contra 256) | medir lado a lado antes de fixar a conversão |
| Projeção 3857 com fator `cos(lat)` em linhas muito longas | aceitar ou trocar por UTM local na expressão |
| Construtor de SIDC grande | reaproveitar os catálogos do bundle; entregar primeiro com SIDC digitado e galeria simples |

---

## 8. Plano de implementação sugerido

A implementação vai direto no branch `qgis4` (decisão do chefe, 2026-10-04), sem branch de feature.

| Fase | Entrega | Pronto quando |
|---|---|---|
| 0 | Base do QGIS 4: corrigir os enums Qt da seção 2.4, `metadata.txt`, script de dev para o perfil QGIS4, carga preguiçosa das ferramentas | todas as ações do menu abrem no QGIS 4.0.0 sem `AttributeError` |
| 1 | Template do calco (seção 5.2) e os QML de Linha de Coordenação (10 símbolos), Linha de Limite, Seta e Frente Ocupada | cada estilo comparado em imagem com o Web no mesmo trecho; GeoPackage reaberto num QGIS sem o plugin desenha igual |
| 2 | Bundle `ebgeo-simbologia.js` gerado do `ebgeo_web`, ponte `QJSEngine`, campo `svg` e regeneração por sinal, para símbolo militar e medida de coordenação | 50 SIDCs (incluindo extensões brasileiras e amplificadores) com SVG igual ao do Web; editar um amplificador regenera |
| 3 | Ferramentas de captura e painel de propriedades das 8 ferramentas | desenhar cada tipo pela toolbar e editar pelo painel |
| 4 | Construtor de SIDC e seletor de medida | montar um SIDC com extensão brasileira só pela interface |
| 5 | Engenharia (medição de texto por `QFontMetricsF`) e Declinação (WMM2025) | 34 variantes de engenharia comparadas com o Web |
| 6 | Alças de edição do Web, conversões e inversão | mover o escalão de uma Linha de Limite pela alça |

A fase 1 não depende da 2: as linhas táticas podem chegar ao usuário antes do construtor de SIDC. O importador do documento irmão entra depois da fase 2, ou antes com bitmaps do arquivo.

---

## 9. Divergências entre a documentação do Web e o código

Encontradas no caminho; valem para corrigir o manual do operador do `ebgeo_web`:

1. Linha de Coordenação: o manual lista 5 símbolos e o código tem 10; o manual diz que os cursores são em km e a interface mostra metros; o manual e um comentário em `toolbar.constants.js` dizem que não há atalho, e o código usa Y.
2. Linha de Limite: o manual lista de XXXX a •, o painel tem 12 opções, inclusive XXXXX e XXXXXX.
3. Frente Ocupada: o manual diz "curvas", o código desenha retas.
4. Símbolo Militar: o manual diz "App-6/2525", o código desenha em 2525 (não chama `setStandard`).
5. Correção de zoom: a frase do manual está invertida em relação ao código.
6. Seta: o manual não menciona "Seta nas Duas Pontas" e diz que a largura acompanha o zoom, o que só vale na criação.
7. Engenharia: `docs/wiki/simbolos-engenharia.md` diz razão de pixel 4, o código usa 2 desde 2026-09-28.

---

## 10. Medidas feitas nesta análise

Feitas no Python do QGIS 4.0.0 instalado (PyQt6, Python 3.12), com scripts de bancada fora do repositório.

| Medida | Resultado | Pior caso que reprova |
|---|---|---|
| milsymbol 3.0.4 no `QJSEngine` | carga 0,25 s; 4 SIDCs (unidade amiga com amplificadores, SIDC de 15 caracteres, hostil, medida de controle) geram SVG válido no `QSvgRenderer` em 4 a 76 ms; imagem conferida | SIDC `XXXX` sai `isValid() = false` |
| SVG gerado num campo do GPKG + marcador SVG `'base64:' \|\| "svg"` + estilo em `layer_styles` | 3 símbolos desenhados; reabre como `SvgMarker` com a expressão, sem código do plugin | antes de salvar o estilo, reabria como `SimpleMarker` |
| PNG de símbolo do `.ebgeo` como marcador raster `base64:` | 6 feições, 646 pixels de tinta na amostra | caminho vazio: 0 pixels |
| Expressão nativa da Linha de Barreiras 290199 | 14 de 14 glifos (20,41 km), 0 de 0 (0,10 km), 120 de 120 no teto (1.925 km); imagem conferida | a linha curta e o teto exercitam os dois limites do layout |
| turf 7 no `QJSEngine` | carrega em 0,68 s, `lineSliceAlong` e `length` corretos | |
| `QSvgRenderer` e alinhamento de texto | ignora `dominant-baseline` (middle, central, hanging) e `dy`; `transform` desloca | as quatro variantes desenharam no mesmo lugar |
| Enums no QGIS 4 | QGIS sem escopo funciona; Qt sem escopo dá `AttributeError` | |
| Bibliotecas no Python do QGIS 4 | pyproj 3.7.2, shapely 2.1.2, numpy 2.4.2, GDAL 3.12.2; `PyQt6.QtQml` e `QtSvg` presentes; `qgis.PyQt.QtQml` ausente; bindings do WebEngine ausentes | |

---

## 11. O que não foi confirmado

- **Fator px para metros** (512 contra 256) entre o MapLibre e o QGIS. Medir com o mesmo símbolo aberto nos dois no mesmo zoom.
- **Os outros 9 símbolos lineares, a Linha de Limite, a Seta e a Frente Ocupada** em expressão nativa: só a 290199 foi escrita e medida; as demais estão descritas a partir do algoritmo do Web.
- **Desempenho** das expressões com centenas de feições longas.
- **O bundle `ebgeo-simbologia.js`:** o milsymbol e o turf rodam no `QJSEngine`; o pós-processamento brasileiro e o gerador de medidas não foram empacotados nem rodados aqui (o agente que leu o código confirmou que o catálogo de medidas carrega em node sem DOM).
- **Os defeitos de render** do `style_fort_pontos_fortes.qml` e do `style_limite_entre_fracoes.qml`: lidos no XML, não renderizados.
- **mil-sym-ts:** carregou transpilado, mas a geometria não foi conferida.
- **Licença e versão** do plugin MIL-STD-2525 renderer de Alexander Bruy (repositório restrito).

---

## 12. Achados fora do escopo

- Ferramentas atuais que quebram no QGIS 4 por enum Qt sem escopo (seção 2.4): Alcance de armamento, Azimute e distância, Medição durante aquisição, Simplificar Interface, Lançamento Paraquedista NOAA.
- `EBGeo/BDGEx/bdgexGuiManager.py:49` usa ícones com prefixo `:/plugins/DsgTools/icons/`: sem o DSGTools, o ícone sai vazio.
- Lacunas no Web reveladas pelo branch apagado: barragens de artilharia com largura real, arame de tração, Ponto de Junção e Ponto de Controle terrestre (seção 2.3).
- `metadata.txt` do `qgis4` com a mesma versão do `master`: risco de colisão no repositório oficial de plugins.
- `.github/workflows/release.yml` usa `actions/checkout@v2`, `setup-python@v1` e Python 3.8, obsoletos.
- O WMM do plugin é o 2020 (vencido); o Web usa o 2025.
