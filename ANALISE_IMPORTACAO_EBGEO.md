# Importar o `.ebgeo` no EBGeo Desktop (QGIS 4): análise

Análise de 2026-10-04 para o branch `qgis4` do plugin EBGeo Desktop (dsgoficial/EBGeo_Desktop). O objetivo é abrir no QGIS 4 o arquivo `.ebgeo` exportado pelo EBGeo Web (1cgeo/ebgeo_web, privado) e reconstruir as feições desenhadas no mapa 2D com a aparência e a organização que o operador vê no navegador. O documento irmão, `ANALISE_SIMBOLOGIA_MILITAR_QGIS4.md`, trata dos renderizadores da simbologia militar, e os dois partilham o mesmo modelo de dados: o importador escreve nas mesmas tabelas em que as ferramentas de desenho escrevem.

**Recorte.** Entram só as feições do mapa 2D (MapLibre). Ficam fora 360, 3D (Cesium e 3D Tiles), briefings e slides, o módulo temporal, a primeira pessoa e os comentários. Essas seções são preservadas cruas para não perder dado, mas não viram camada.

**Como foi feito.** Quatro análises paralelas: o código do `ebgeo_web` no branch `main` (EBGeo 3.0) e no branch `ebgeo2.0` (linha 2.x congelada); as cinco fixtures reais do repositório de dados de teste, abertas em Python; o plugin no branch `qgis4`; e o estado da arte do QGIS. As medidas que decidem a arquitetura foram refeitas no Python do próprio QGIS 4.0.0 (seção 11). Caminhos de código são relativos à raiz de cada repositório.

---

## 1. Resumo para decisão

1. **O formato é simples e estável.** É um ZIP mascarado por XOR com `data.json` e uma pasta `images/`. Um leitor em Python puro cabe em cerca de 60 linhas, e as cinco fixtures (2.2, 2.3 e 2.4) abrem sem erro. Não existe fixture 3.0: o que se diz do 3.0 vem do código.
2. **O problema difícil é o conceito de camada, não o formato.** No EBGeo a camada do usuário é um atributo de pertinência (`properties.layerId`) sobre feições de qualquer tipo e geometria, e a pilha de desenho é por TIPO, fixa. No QGIS a camada vetorial tem uma geometria e um esquema. Na fixture mais completa, 14 das 20 camadas EBGeo com feição misturam ponto, linha e polígono, e a camada "Padrão" de um mapa tem 21 tipos.
3. **Recomendação: armazenar por tipo, apresentar por camada.** Um GeoPackage por `.ebgeo`, uma tabela por tipo de feição com as colunas `mapa` e `camada_id`. Na árvore de camadas, um grupo por mapa (mutuamente exclusivo, porque o EBGeo mostra um mapa por vez), um subgrupo por camada EBGeo e, dentro dele, uma camada QGIS por tipo não vazio, filtrada por `subsetString`. A ordem de desenho é imposta com `setHasCustomLayerOrder` na pilha por tipo do EBGeo. Assim a árvore se parece com o EBGeo e o desenho também.
4. **Nenhum tipo militar depende do PNG do arquivo para ser redesenhado.** Símbolo militar, medida de coordenação, engenharia e declinação vêm com as propriedades completas e um PNG que é só cache. As quatro linhas táticas (Linha de Limite, Linha de Coordenação, Seta, Frente Ocupada) guardam o eixo em `properties.baseCoordinates` e a geometria gravada é o desenho num zoom. Só a feição `image` e os ícones personalizados existem apenas como blob.
5. **Dá para entregar em duas ondas.** Onda 1: importar tudo, com os bitmaps do próprio arquivo como marcador raster `base64:` (provado no QGIS 4) e as linhas táticas pela geometria gravada. Onda 2: trocar pelos renderizadores vivos do documento irmão, que redesenham a partir das propriedades e acompanham a edição.

---

## 2. O contêiner

| Item | Valor | Onde |
|---|---|---|
| Cabeçalho | 6 bytes ASCII `EBGXOR`, em claro | `frontend/src/js/import_export/export-import.service.js:680-686` |
| Corpo | ZIP inteiro, cada byte XOR `0xAA` | idem; leitura em `ebgeo-file-gate.js:98-103` |
| Sem máscara | ZIP puro também é aceito pelo leitor | `ebgeo-file-gate.js:98-103` |
| `data.json` | raiz, UTF-8 sem BOM, DEFLATE 9 | `export-import.service.js:656` |
| `images/<id>.<ext>` | um blob por dono (feição, ícone, foto), extensão pelo MIME (png, jpg, webp, svg) | `:239-253`, `:664` |
| Fotos anexas | até a 2.4, inline no JSON como data URL em `properties.images[].data`; na 3.0 também por referência, bytes em `images/<id>` | `user_data/photo-refs.js` |
| Nome | `atlas-<ISO>.ebgeo` (3.0), `projeto-<ISO>.ebgeo` (2.x) | `:697` |

Decodificação correta (o README das fixtures aplica o XOR ao arquivo inteiro e só funciona porque o `zipfile` tolera lixo no início):

```python
raw = Path(p).read_bytes()
body = bytes(b ^ 0xAA for b in raw[6:]) if raw[:6] == b"EBGXOR" else raw
z = zipfile.ZipFile(io.BytesIO(body))
data = json.loads(z.read("data.json").decode("utf-8"))
```

Fixtures medidas:

| Fixture | Versão | Bytes | `data.json` | Imagens | Feições |
|---|---|---|---|---|---|
| 01-completo | 2.2 | 21.916 | 127.495 | 5 png | 262 |
| 02-minimo | 2.2 | 735 | 1.164 | 0 | 1 |
| 03-completo-2.4 | 2.4 | 1.223.201 | 986.847 | 145 png + 4 jpg | 805 |
| 04-completo-2.3 | 2.3 | 990.612 | 958.640 | 127 png + 4 jpg | 787 |
| 05-completo-2.2 | 2.2 | 659.837 | 919.756 | 127 png + 4 jpg | 776 |

A 01 é o pior caso de propósito: propriedades com nomes que o app não lê (`cor`, `espessura`), círculo, elipse e setor gravados como Point, seta como LineString e símbolos sem PNG. O importador tem de sobreviver a ela com os padrões de cada ferramenta.

### 2.1 Versões

- `data.version` é string `"X.Y"`. O portão da 3.0 (`importVersionRefusal`, `ebgeo-file-gate.js:150-203`) aceita de `MIN_SCHEMA_VERSION='1.3'` (`store/repository.utils.js:37`) a `ATLAS_SCHEMA_VERSION='3.0'` (`store/atlas/atlas.entity.js:29`), no padrão `^\d+\.\d+(\.\d+)?$`, e aplica a mesma regra a `schemaVersion` e `atlas.schemaVersion` quando existem.
- A linha 2.x recusa acima de 2.4: o `.ebgeo` 3.0 é mão única.
- As migrações `store/migration/*` são do IndexedDB, não do arquivo. O arquivo passa só por dois normalizadores: `migrateImportDataToV2` (carimba metadados de sync) e `normalizeMapDataForCurrentVersion` com `ensureMapDataShape` (`repository.utils.js:317`), que garante baldes e adota os legados.
- `MAX_SCHEMA_VERSION='1.7'` (`repository.utils.js:40`) não tem leitor e não limita o `.ebgeo`.

**O importador aceita de 1.3 a 3.0** e recusa o resto com mensagem clara ("versão mais nova que o plugin: atualize o EBGeo Desktop").

Diferenças que importam ao leitor, por versão:

| Versão | O que muda para o importador |
|---|---|
| 2.2 | pode trazer o balde legado `barrier_lines`; sem `coordination_lines`; PNG de símbolo quadrado com faixas transparentes (69 de 93) |
| 2.3 | `coordination_lines` aparece; PNG ainda quadrado |
| 2.4 | `bitmapVersion: 2`, PNG recortado (91 de 93 retangulares); `anchor` e `iconOffset` na medida de coordenação |
| 3.0 | balde `engineering_symbols`; `iconOffset` também no símbolo militar; foto por referência; seções `gridStyle`, `comments`, `mapLocks`, `mapBadgeColors` (fora do recorte) |

---

## 3. O que interessa no `data.json`

### 3.1 Raiz e mapa

| Chave | Uso no importador |
|---|---|
| `version` | validar |
| `currentMap` | nome do mapa que abre ligado |
| `mapOrder` | ordem dos mapas; **pode vir vazio** (a 02 tem `[]` com 1 mapa): unir com a ordem das chaves de `maps`, como `prepare-ebgeo-scope.js:97` |
| `maps{nome}` | o mapa: `baseLayer` (id de catálogo do servidor), `features{balde: [Feature]}`, `zoom`/`center_*` (null nas cinco fixtures) |
| `layers{nome: [camada]}` | camadas do usuário: `{id, name, visible, locked, opacity, order}`; o id `default` não é UUID |
| `groups{nome: {gid: grupo}}` | `{id, name, visible, locked, features:[{type, id}]}`; `type` é o `source` singular e `id` é `properties.id` |
| `mapNotes{nome}` | `{title, description}`, vira resumo do grupo do mapa |
| `customIcons[]` | `{id, name, thumbnail, type}`, blob em `images/<id>.png`, usado por ponto com `markerSymbol: "custom:<id>"` |
| fora do recorte | `cesium3d`, `streetview360`, `briefings`, `temporal`, `comments`, `gridStyle`, `colorUsage`, `mapLocks`, `mapBadgeColors`, `catalogLayers`, `analysisLayers`, `hillshadeEnabled`; preservar cru na tabela `ebgeo_documento` |

**O nome do mapa é chave** em todas as seções por mapa. É uma string arbitrária (o app usa `Object.create(null)` porque pode ser até `__proto__`). Não usar como nome de tabela; a proposta abaixo guarda numa coluna.

### 3.2 Feição

GeoJSON `{type, id, properties, geometry}` em EPSG:4326, `[lon, lat]`, 6 casas decimais (`roundCoordinates`, `export-import.service.js:186`; valor não finito vira `null`).

- **A identidade é `properties.id`** (UUID). O `id` de topo é instável (int do MapLibre ou string) e deve ser ignorado. Exceção: `processed_*` usa `<uuid>-visible` e `<uuid>-obstructed`.
- **O balde decide o tipo, nunca o `source`.** `processed_los` traz `source: "los"` e `processed_visibility` traz `"visibility"` (6 de 6 em cada fixture): ler pelo `source` funde resultado com insumo.
- Campos comuns: `id`, `source`, `nome`, `descricao`, `visivel`, `bloqueado`, `layerId` (ausente vale `default`), `attributes` (dict de strings com chaves livres, acento e espaço), `images` (fotos), `createdAt`, `updatedAt`, `version`.

### 3.3 Baldes, contagem e geometria (contagem 01 / 02 / 03 / 04 / 05)

| Balde | Tipo | Geometria guardada | Contagem |
|---|---|---|---|
| points | point | Point | 168/1/381/381/381 |
| lines | line | LineString | 42/0/80/80/80 |
| polygons | polygon | Polygon | 7/0/68/68/68 |
| texts | text | Point | 2/0/19/19/19 |
| images | image | Point | 4/0/11/11/11 |
| circles | circle | Polygon de 65 vértices (01: Point) | 22/0/42/42/42 |
| ellipses | ellipse | Polygon de 65 vértices | 1/0/5/5/5 |
| rectangles | rectangle | Polygon de 5 vértices | 1/0/5/5/5 |
| setores | sector | Polygon | 1/0/6/6/6 |
| brushes | brush | LineString | 1/0/5/5/5 |
| arrows | arrow | Polygon e MultiPolygon | 1/0/8/8/8 |
| boundarys | boundary | MultiLineString | 1/0/7/7/7 |
| occupied_fronts | occupied_front | MultiLineString | 1/0/4/4/4 |
| coordination_lines | coordination_line | MultiLineString e MultiPolygon | 0/0/11/11/ausente |
| military_symbols | military_symbol | Point | 6/0/93/93/93 |
| coordination_measures | coordination_measure | Point | 1/0/38/20/20 |
| engineering_symbols | engineering_symbol | Point (só 3.0, sem fixture) | ausente |
| magnetic_declinations | magnetic_declination | Point | 1/0/4/4/4 |
| los | los | MultiLineString | 1/0/3/3/3 |
| visibility | visibility | MultiPolygon | 1/0/3/3/3 |
| processed_los | processed_los | LineString | 0/0/6/6/6 |
| processed_visibility | processed_visibility | MultiPolygon | 0/0/6/6/6 |
| coordenadas | efêmero | descartar | 0 |
| barrier_lines | legado 2.2 | adotar como coordination_line 290199 | vazio na 05 |

O nome `boundarys`, com "y", é a grafia real do código. Nem por tipo a geometria guardada é única (arrows, coordination_lines), o que obriga a promover a Multi* ou converter (seção 5).

### 3.4 Propriedades por tipo (as que o estilo lê)

**Formas desenhadas.**
- `point`: `fillColor`, `lineColor`, `lineWidth`, `size`, `opacity`, `markerSymbol` (circle, square, diamond, triangle, star, cross, x-mark; ícones car, drone, fire, gun, news, plane, supply; ou `custom:<iconId>`; `draw_tools/point_tool/point-marker-symbols.js:14-38`), `sizeZoomCorrectionEnabled`, `sizeCreatedAtZoom`, rótulo `showLabel`, `labelText`, `labelColor`, `labelSize`, `labelOutlineColor`, `labelOutlineWidth`, `labelCreatedAtZoom`, `labelZoomCorrectionEnabled`.
- `line`: `lineColor`, `lineWidth`, `opacity`, `lineStyle` (solid, dashed, dotted, dash-dot, long-dash, short-dash, dot-dot-dash, com traço em unidades da largura, `layers/styles/layer.helpers.js:115-124`).
- `polygon`, `circle`, `ellipse`, `rectangle`, `sector`: `fillColor`, `lineColor`, `lineWidth`, `lineStyle`, `opacity` (vale **só para o preenchimento**, o contorno sai com opacidade 1, `polygon.layers.js:72,113`), hachura `hatchEnabled`, `hatchType` (none, diagonal-right, diagonal-left, horizontal, vertical, cross, cross-diagonal, dots), `hatchColor`, `hatchSpacing`, `hatchLineWidth`, os campos de rótulo, e os parâmetros: círculo `center`, `radius` (m); elipse `center`, `majorRadius`, `minorRadius`, `bearing`; retângulo `corner1`, `corner2`, `center`, `width`, `height` (m), `bearing`, `borderRadius`; setor `center`, `radius` (m), `aperture`, `bearing`.
- `text`: `text`, `size` (px), `color`, `backgroundColor` (é a cor do halo), `textHaloWidth`, `rotation` (gira com o mapa), `justify`, caixa `showBackground`, `backgroundFillColor`, `backgroundFillOpacity`, `backgroundBorderColor`, `backgroundBorderOpacity`, `backgroundBorderWidth`, `createdAtZoom`, `zoomCorrectionEnabled`. Fonte Noto Sans Regular; rótulos de ponto e polígono em Noto Sans Bold.
- `image`: `size`, `rotation`, `opacity`, `width`, `height` (px do arquivo), `createdAtZoom`, `zoomCorrectionEnabled`; blob `images/<properties.id>`.
- `brush`: `lineColor`, `lineWidth` (escala com o zoom), `createdAtZoom`, `zoomCorrectionEnabled`.

**Tipos táticos.** O detalhe de cada um, com fórmulas, está no documento irmão. Para o importador bastam:
- `arrow`: `baseCoordinates`, `width` (metros, largura do corpo), `fillColor`, `lineColor`, `lineWidth`, `fillOpacity`, `lineOpacity`, `headLengthRatio`, `showArrowHead`, `doubleHeaded`, `airmobile`, `airmobilePosition`; seta combinada com `isMerged` e `branches[]`.
- `boundary`: `baseCoordinates`, `echelon` (string de `X`, `I`, `o`), `symbol_instances[{ratio, showLabels}]`, `symbol_size` (km), `text_top`, `text_bottom`, `text_size`, `text_distance_ratio`, `text_north_facing`, `color`, `lineWidth`, `opacity`, `createdAtZoom`, `zoomCorrectionEnabled`; legado `symbol_position_ratio`.
- `occupied_front`: `baseCoordinates` (três pontos), `color`, `lineWidth`, `opacity`.
- `coordination_line`: `baseCoordinates`, `symbol_code` (290100, 290199, 290202, 290302, 290303, 290307, 290308, 290309, 290999-01, 290999-02), `symbol_size` e `symbol_spacing` (km), `color`, `lineWidth`, `opacity`, `createdAtZoom`, `zoomCorrectionEnabled`.
- `military_symbol`: `sidc` (30 dígitos, com a extensão brasileira `076` nos dígitos 21 a 30), os 16 amplificadores de texto, `specialModifier`, `isCommand`, `fillColor`, `size`, `rotation`, `opacity`, `createdAtZoom`, `zoomCorrectionEnabled`, e os derivados `width`, `height`, `iconOffset`, `bitmapVersion`.
- `coordination_measure`: `pointCode`, `echelonCode`, os campos de texto (`tipo`, `identificacao`, `gdhIni`, `gdhFim`, `numero`, `classeSuprimento`, `status`, `numeroConcentracao`, `altitude`), `fillColor`, `size`, `rotation`, `opacity`, e os derivados `anchor`, `iconOffset`, `pixelRatio`.
- `engineering_symbol`: `pointCode`, `engineering{variant, values}`, `fillColor`, `size`, `rotation`, `opacity`.
- `magnetic_declination`: `declination`, `convergence`, `inclination`, `intensity`, `latitude`, `longitude`, `calculationDate`, `fillColor`, `size`; aliases legados `declinacao` e `convergencia`.

**Análise.** `los` e `visibility` com os parâmetros do cálculo; `processed_*` com `color` (#00FF00 visível, #FF0000 obstruído). A entrada `los` é desenhada com opacidade zero no app: importar oculta.

---

## 4. O conceito de camada

### 4.1 Como o EBGeo organiza

```
atlas (o arquivo)
 └─ mapa (chave por nome; o app mostra UM por vez)
     ├─ camada do usuário  ← atributo properties.layerId de cada feição
     ├─ grupo              ← lista de membros em groups[mapa][gid].features
     └─ balde por tipo     ← a unidade de DESENHO (uma fonte MapLibre por balde)
```

- **A unidade de desenho é o balde.** Cada balde é uma fonte MapLibre com camadas de estilo fixas, e a pilha é por tipo (`layers/layer_setup.js:702-721`), de baixo para cima: images, polygons, ellipses, circles, rectangles, setores, arrows, visibility, occupied_fronts, coordination_lines, boundarys, lines, brushes, los, points, military_symbols, coordination_measures, engineering_symbols, magnetic_declinations, texts.
- **A camada do usuário é um filtro, não uma pilha.** Ela vale três coisas: filtro de visibilidade (`layers/visibility-filter.js:209`), multiplicador de opacidade por `match` em `layerId` (`layers/layer-opacity-applier.js:142-150`) e ordem de LISTA no painel (`layers/layer.manager.js:80`). Um ponto da última camada sempre fica acima de um polígono da primeira.
- **O grupo é ortogonal à camada.** A pertinência mora no grupo, não na feição (`properties.groupId` está no typedef, mas 0 feições o usam nas fixtures). Grupo atravessa tipos e grupo oculto esconde os membros (`applyGroupVisibility`, `layer_setup.js:613`).

### 4.2 Medido nas fixtures

| Fixture | Mapas | Camadas EBGeo | Camadas com feição que misturam famílias de geometria | Máximo de tipos numa camada |
|---|---|---|---|---|
| 01 | 11 | 17 | 6 de 15 | 18 |
| 03 | 14 | 21 | 14 de 20 | 21 |
| 04 | 14 | 21 | 14 de 20 | 20 |
| 05 | 14 | 21 | 14 de 20 | 19 |

As fixtures foram geradas para cobrir o formato, então exageram a mistura. Mesmo num atlas real de operador, a camada "Inteligência (S2)" do mapa "10 Camadas" da 03 tem círculo, linha, ponto, polígono e texto: é o uso normal.

### 4.3 Quantas camadas QGIS cada estratégia produz

| Estratégia | 01 | 02 | 03 | 04 | 05 |
|---|---|---|---|---|---|
| (a) uma por tipo, arquivo inteiro, campo `mapa` | 18 | 1 | 21 | 21 | 20 |
| (a') tipo × mapa | 39 | 1 | 75 | 73 | 71 |
| (b) mapa × camada EBGeo × família de geometria | 24 a 25 | 1 | 44 | 44 | 44 |
| (c) três genéricas (ponto, linha, polígono), campo `tipo` | 3 | 1 | 3 | 3 | 3 |
| (c') família × mapa | 19 a 20 | 1 | 29 | 29 | 29 |
| (e) mapa × camada EBGeo × tipo | 44 | 1 | 94 | 92 | 90 |
| (e) só do mapa ativo, pior mapa | | | 24 | | |

Na 01, (b) dá 24 contando a geometria guardada e 25 contando a geometria QGIS proposta (a seta gravada como LineString vira polígono), e (c') dá 19 e 20 pelo mesmo motivo.

### 4.4 Prós e contras

| Estratégia | A favor | Contra |
|---|---|---|
| (a) por tipo | esquema e QML fixos por tipo; reproduz a pilha do EBGeo | o operador não vê a camada dele; visibilidade e opacidade por camada viram regra |
| (b) camada × geometria | é o que o operador reconhece | cada camada de ponto mistura marcador, texto, bitmap e símbolo, então o renderer é por regra sobre `tipo` com esquema união de ~90 campos; **inverte a pilha** (polígono da camada A sobre ponto da camada B) |
| (c) três genéricas | o mínimo de camadas | esquema esparso enorme; renderer do tamanho do produto; perde camada e mapa; editar com as ferramentas do QGIS fica confuso |
| (e) camada × tipo | fiel às duas coisas | 94 camadas na 03 se criar tudo |

### 4.5 Recomendação: armazenar por tipo, apresentar por camada

1. **Armazenamento (a).** Um GeoPackage por `.ebgeo`, uma tabela por tipo (até 22), cada uma com geometria única e as colunas `mapa` e `camada_id`. O QML de cada tipo é fixo e lê as colunas por propriedade definida por dado. É o mesmo esquema das ferramentas de desenho do documento irmão: o que se importa se edita com as mesmas ferramentas.
2. **Apresentação (e), preguiçosa.**
   - Grupo do atlas com `setIsMutuallyExclusive(True)`: o EBGeo mostra um mapa por vez, e o `currentMap` abre ligado.
   - Um grupo por mapa, na ordem de `mapOrder` unida às chaves.
   - Um subgrupo por camada EBGeo, na ordem crescente de `order` de cima para baixo. `visible` é o check do subgrupo, `opacity` vira `setOpacity` das camadas filhas, `locked` vira `setReadOnly`.
   - Dentro do subgrupo, uma `QgsVectorLayer` por tipo não vazio, apontando para a tabela do tipo com `setSubsetString('"mapa" = ... AND "camada_id" = ...')`.
   - Para não criar 94 camadas, materializar só o mapa ativo (24 na 03, no pior mapa) e criar os demais ao ligar o grupo do mapa (sinal `visibilityChanged` do nó). Mapa nunca aberto fica como grupo vazio com um marcador "carregar".
3. **Ordem de desenho.** `QgsProject.layerTreeRoot().setHasCustomLayerOrder(True)` e `setCustomLayerOrder(...)` montada pela pilha por tipo da seção 4.1. A árvore mostra a organização do operador, e o desenho segue o EBGeo.
4. **Grupos EBGeo.** Não viram `QgsLayerTreeGroup`, porque não são contêiner de desenho. Ficam nas tabelas `ebgeo_grupo` e `ebgeo_grupo_membro` e numa coluna `grupos` na feição. Grupo oculto vira exclusão na regra raiz do renderer (`NOT array_contains(string_to_array("grupos"), ...)`) gerada pelo plugin, ou uma ação "mostrar/ocultar grupo".
5. **Por feição.** `visivel = false` vira regra raiz `"visivel" IS NOT false`. `bloqueado` não tem equivalente por feição no QGIS: preservar o campo e respeitá-lo nas ferramentas do plugin.

**Alternativa para revisar com o chefe:** se o uso principal for consultar e imprimir, e não editar, a estratégia (a) pura com uma camada por tipo e filtro de mapa é mais simples (21 camadas, nenhuma lógica de árvore) e perde só a camada EBGeo como unidade visível. Ela pode ser a primeira entrega e a (e) preguiçosa a segunda, sem mudar o armazenamento.

---

## 5. Geometria guardada contra geometria QGIS

**Regra geral.** Onde o tipo guarda `baseCoordinates`, a geometria QGIS sai dele e a guardada vai para a coluna `geom_desenho` (WKB) como reserva. Onde a geometria guardada já é a forma real (os polígonos paramétricos), usa-se a guardada e os parâmetros viram colunas.

| Tipo | Guardado | Tabela QGIS | Observação |
|---|---|---|---|
| point, image, military_symbol, coordination_measure, engineering_symbol, magnetic_declination | Point | Point | |
| text | Point | Point | renderer vazio e só rótulo |
| line, brush | LineString | LineString | |
| los | MultiLineString | MultiLineString | importar oculta |
| processed_los | LineString | LineString | |
| polygon | Polygon | MultiPolygon | promover |
| circle, ellipse, rectangle, sector | Polygon pronto + parâmetros | MultiPolygon | na 01 vêm como Point: regenerar do `center` e `radius` com geodésica (pyproj `Geod`) |
| visibility, processed_visibility | MultiPolygon | MultiPolygon | |
| arrow | contorno calculado (Polygon/MultiPolygon) + `baseCoordinates` | LineString do eixo | renderer de seta do documento irmão; a 01 traz LineString; seta combinada usa `branches[]` |
| boundary | MultiLineString (espinha com vãos + traços do escalão no zoom de criação) | LineString do eixo | os círculos `o` e os rótulos não estão no arquivo |
| occupied_front | MultiLineString de 8 a 10 partes | LineString de 3 vértices | |
| coordination_line | MultiLineString (espinha + glifos) ou MultiPolygon (fosso) | LineString do eixo | o glifo é renderização, não dado |
| barrier_lines (legado) | | coordination_line | `symbol_code='290199'`, `symbol_size=0.5`, `symbol_spacing=1.5`, `createdAtZoom=0`, `zoomCorrectionEnabled=true`, `baseCoordinates` só se a geometria for LineString (`repository.utils.js:199-244`) |

**Onda 1 sem renderizador vivo.** Para entregar a importação antes dos renderizadores do documento irmão, as quatro linhas táticas podem ser exibidas por uma camada auxiliar somente leitura com a `geom_desenho`, estilizada por cor, largura e opacidade. Fica fiel ao zoom de salvamento e não acompanha edição; ao chegar a onda 2, a camada auxiliar some.

**Antimeridiano.** A fixture 03 tem `[179.9, 10] → [-179.9, 10]`. O QGIS desenha atravessando o mundo: detectar salto de longitude acima de 180° e desembrulhar ou cortar.

---

## 6. Esquema do GeoPackage

### 6.1 Colunas comuns a toda tabela de feição

`fid`, `ebgeo_id` (único, de `properties.id`), `tipo` (o balde), `mapa`, `camada_id`, `nome`, `descricao`, `visivel`, `bloqueado`, `grupos`, `criado_em`, `atualizado_em`, `atributos` (JSON das chaves livres; a 03 tem dezenas de chaves distintas com espaço e acento, que não viram coluna), `props` (JSON das propriedades originais inteiras, para round-trip e para exportar de volta), `geom_desenho` (WKB, só nos tipos táticos).

### 6.2 Colunas promovidas (só o que o QML ou a ferramenta lê)

| Família | Colunas |
|---|---|
| ponto | `fill_color`, `line_color`, `line_width`, `size`, `opacity`, `marker_symbol`, `zoom_corr`, `created_zoom`, `label_*` |
| linha | `line_color`, `line_width`, `opacity`, `line_style` |
| formas | `fill_color`, `line_color`, `line_width`, `line_style`, `opacity`, `hatch_*`, `label_*`, `center_x`, `center_y`, `radius_m`, `major`, `minor`, `bearing`, `aperture`, `width_m`, `height_m` |
| texto | `text`, `size`, `color`, `halo_color`, `halo_width`, `rotation`, `justify`, `bg_*`, `zoom_corr`, `created_zoom` |
| bitmap e símbolos | `size`, `rotation`, `opacity`, `fill_color`, `zoom_corr`, `created_zoom`, `bitmap` (BLOB), `bitmap_mime`, `width_px`, `height_px`, `pixel_ratio`, `anchor`, `icon_offset_x`, `icon_offset_y`, `svg` (texto, preenchido pelo renderizador vivo) |
| símbolo militar | + `sidc` e os 16 amplificadores de texto, `special_modifier`, `is_command` |
| medida e engenharia | + `point_code`, `echelon_code`, os campos de texto; `engineering` (JSON) |
| linhas táticas | + `symbol_code`, `symbol_size_km`, `symbol_spacing_km`, `echelon`, `symbol_instances` (JSON), `text_top`, `text_bottom`, `text_size`, `text_distance_ratio`, `text_north_facing`, `arrow_width_m`, `head_length_ratio`, `show_arrow_head`, `double_headed`, `airmobile`, `airmobile_position` |

### 6.3 Tabelas de apoio

| Tabela | Conteúdo |
|---|---|
| `ebgeo_documento` | versão, sha256 e nome do arquivo de origem, `data.json` original inteiro (inclusive as seções fora do recorte) |
| `ebgeo_mapa` | nome, ordem, `baseLayer`, notas, se é o `currentMap` |
| `ebgeo_camada` | mapa, id, nome, visível, bloqueada, opacidade, ordem |
| `ebgeo_grupo`, `ebgeo_grupo_membro` | grupos e membros (`tipo`, `ebgeo_id`) |
| `ebgeo_icone` | `customIcons` com o blob |
| `ebgeo_foto` | feição, id, nome, mime, bytes, miniatura; 2.x inline em base64, 3.0 por referência |

O QML de cada tipo vai para `layer_styles` do próprio GPKG como estilo padrão. A medida da seção 11 provou que um GPKG assim reabre no QGIS 4 com o estilo, sem código do plugin.

---

## 7. Estilo

- **Um QML fixo por tipo**, com propriedades definidas por dado lendo as colunas promovidas: cor, largura, opacidade, padrão de traço, hachura (`QgsLinePatternFillSymbolLayer` por regra de `hatch_type`; `dots` por `QgsPointPatternFillSymbolLayer`), rótulos (`QgsPalLayerSettings` com texto, tamanho, cor e buffer definidos por dado).
- **Marcador de ponto.** As formas mapeiam para `QgsSimpleMarkerSymbolLayer`; os ícones car, drone, fire, gun, news, plane e supply são desenhados em canvas pelo app (`point-marker-symbols.js`) e precisam virar SVG embarcado no plugin; `custom:<id>` vira marcador raster do blob em `ebgeo_icone`.
- **Bitmap.** Marcador raster com caminho definido por dado `'base64:' || to_base64("bitmap")`, ou coluna texto com o base64 pronto. Provado no QGIS 4 com os PNGs reais da fixture 03 (seção 11). Âncora pelo `anchor` e deslocamento por `icon_offset_x/y`, rotação horária por `rotation`.
- **Texto.** Camada com renderer vazio (`QgsNullSymbolRenderer`) e rótulo: `text`, `size`, `color`, buffer `halo_color` e `halo_width`, rotação, alinhamento, fundo por `QgsTextBackgroundSettings`.
- **Tamanho e zoom.** No EBGeo, com `zoomCorrectionEnabled` ligado o tamanho é fixo NO TERRENO: `px = base × 2^(zoom − createdAtZoom)`, teto 10× para ícone (`layers/styles/zoom-expression.js:349-382`). Desligado, é fixo na tela. No QGIS: ligado vira unidade de mapa ou metros, `metros = px × 78271,517 × cos(lat) / 2^createdAtZoom` (mundo MapLibre de 512 px no zoom 0); desligado vira pixels. A fórmula é dedução do código e precisa de medida lado a lado (seção 12): o `ebgeo_web` usa a convenção de 256 px (`156543,03392`) no KMZ e no clipboard, e só uma das duas reproduz a tela.
- **`lineWidth`** de linha e de contorno é sempre px fixo na tela no EBGeo: `RenderPixels` no QGIS.
- **Opacidade da camada EBGeo** multiplica a da feição: `setOpacity` da camada QGIS faz isso de graça.

---

## 8. Armadilhas

1. **O balde decide o tipo**, nunca o `source` (`processed_*`).
2. **`barrier_lines`** legado: adotar como Linha de Coordenação 290199 (seção 5). População real zero, mas o arquivo forjado existe.
3. **Balde ausente ou vazio é normal** (`coordination_lines` não existe na 01 nem na 02). Balde desconhecido: ignorar com log. `coordenadas`: descartar.
4. **MIME pela extensão engana**: arquivos de antes de 2026-08-24 podiam ter JPEG gravado como `.png`. Farejar os bytes mágicos (PNG `89504E47`, JPEG `FFD8FF`). Nas fixtures, 149 de 149 batem.
5. **Id de imagem duplicado** entre extensões: o leitor do app recusa (`ebgeo-file-gate.js:119-126`); fazer igual.
6. **Bitmap ausente** em símbolo, medida e declinação é normal (6, 1 e 1 na 01): regenerar ou marcador de erro. Ausência de feição `image`, ícone ou foto é perda: avisar.
7. **PNG quadrado da 2.2 e 2.3** tem faixas transparentes: a âncora central funciona, mas a caixa fica maior que o desenho.
8. **Nome de mapa** arbitrário e chave em tudo; **`mapOrder`** pode vir vazio ou incompleto.
9. **Coordenada `null`** (não finita): validar por feição e descartar com log, sem derrubar o arquivo.
10. **Unidade de `majorRadius` e `minorRadius`** da elipse: km, inferido do atributo "Eixo maior (km)" e de uma medida (2,4 → 2394 m), não lido no gerador.
11. **Proteção contra bomba de ZIP**: somar `file_size` antes de extrair; referência de teto do servidor, 200 mapas por importação (`backend/src/config.js:350`).
12. **Unidade temporal minúscula** (`dia`) na 01: só importa se o temporal entrar um dia.

---

## 9. Esqueleto do leitor

```python
import io, json, re, zipfile
from pathlib import Path

MAGIC, KEY = b"EBGXOR", 0xAA
VER_RE = re.compile(r"^\d+\.\d+(\.\d+)?$")
MIN_V, MAX_V = (1, 3, 0), (3, 0, 0)
BUCKET_TYPE = {
    "points": "point", "lines": "line", "polygons": "polygon", "texts": "text", "images": "image",
    "circles": "circle", "rectangles": "rectangle", "ellipses": "ellipse", "brushes": "brush",
    "setores": "sector", "arrows": "arrow", "boundarys": "boundary", "occupied_fronts": "occupied_front",
    "coordination_lines": "coordination_line", "military_symbols": "military_symbol",
    "coordination_measures": "coordination_measure", "engineering_symbols": "engineering_symbol",
    "magnetic_declinations": "magnetic_declination", "los": "los", "visibility": "visibility",
    "processed_los": "processed_los", "processed_visibility": "processed_visibility",
}
IGNORED_BUCKETS = {"coordenadas"}
BITMAP_TYPES = {"image", "military_symbol", "coordination_measure", "engineering_symbol", "magnetic_declination"}
MAX_UNCOMPRESSED = 512 * 2**20


class EbgeoError(Exception):
    pass


def vtuple(v):
    if not isinstance(v, str) or not VER_RE.match(v):
        raise EbgeoError(f"versão inválida: {v!r}")
    p = [int(x) for x in v.split(".")]
    return tuple(p + [0] * (3 - len(p)))


def sniff_mime(b):
    if b[:4] == b"\x89PNG": return "image/png"
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return "image/webp"
    if b.lstrip()[:4] in (b"<svg", b"<?xm"): return "image/svg+xml"
    return None


def open_ebgeo(path):
    raw = Path(path).read_bytes()
    body = bytes(b ^ KEY for b in raw[6:]) if raw[:6] == MAGIC else raw
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile:
        raise EbgeoError("não é um .ebgeo válido ou está corrompido")
    if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
        raise EbgeoError("arquivo grande demais")
    if z.testzip() is not None:
        raise EbgeoError("CRC inválido")
    if "data.json" not in z.namelist():
        raise EbgeoError("data.json ausente")
    data = json.loads(z.read("data.json").decode("utf-8"))
    images = {}
    for n in z.namelist():
        m = re.match(r"^images/([^/]+)\.(png|jpe?g|svg|webp)$", n, re.I)
        if not m:
            continue
        if m[1] in images:
            raise EbgeoError(f"id de imagem duplicado: {m[1]}")
        b = z.read(n)
        images[m[1]] = (b, sniff_mime(b) or "image/png")
    return data, images


def validate(data):
    if not data.get("version"):
        raise EbgeoError("sem versão")
    for v in (data.get("version"), data.get("schemaVersion"), (data.get("atlas") or {}).get("schemaVersion")):
        if v is None:
            continue
        t = vtuple(v)
        if t < MIN_V:
            raise EbgeoError(f"versão {v} anterior a 1.3")
        if t > MAX_V:
            raise EbgeoError(f"versão {v} mais nova que o plugin: atualize o EBGeo Desktop")
    if not isinstance(data.get("maps"), dict):
        raise EbgeoError("coleção de mapas ausente")


def normalize_features(features):  # espelho de ensureMapDataShape
    f = dict(features or {})
    f.setdefault("coordination_lines", [])
    for ft in f.pop("barrier_lines", None) or []:
        p = dict(ft.get("properties") or {})
        p["source"] = "coordination_line"
        for k, v in {"symbol_code": "290199", "symbol_size": 0.5, "symbol_spacing": 1.5,
                     "createdAtZoom": 0, "zoomCorrectionEnabled": True}.items():
            if p.get(k) is None:
                p[k] = v
        g = ft.get("geometry") or {}
        if p.get("baseCoordinates") is None and g.get("type") == "LineString":
            p["baseCoordinates"] = [c[:2] for c in g["coordinates"]]
        f["coordination_lines"].append({**ft, "properties": p})
    for ft in f.get("magnetic_declinations", []):
        p = ft.setdefault("properties", {})
        for old, new in (("declinacao", "declination"), ("convergencia", "convergence")):
            if new not in p and isinstance(p.get(old), (int, float)):
                p[new] = p[old]
    return f


def map_order(data):
    order = [n for n in data.get("mapOrder") or [] if n in data["maps"]]
    return order + [n for n in data["maps"] if n not in order]


def import_ebgeo(path, gpkg_path, log):
    data, images = open_ebgeo(path)
    validate(data)
    w = GpkgWriter(gpkg_path)            # cria as tabelas por tipo e as de apoio
    w.save_document(path, data)          # data.json inteiro, inclusive o que está fora do recorte
    for icon in data.get("customIcons") or []:
        w.add_icon(icon, images.get(icon.get("id")))
    for order, name in enumerate(map_order(data)):
        m = data["maps"][name]
        w.add_map(name, order, m.get("baseLayer"), (data.get("mapNotes") or {}).get(name),
                  current=(name == data.get("currentMap")))
        w.add_layers(name, (data.get("layers") or {}).get(name) or [DEFAULT_LAYER])
        w.add_groups(name, (data.get("groups") or {}).get(name) or {})
        for bucket, feats in normalize_features(m.get("features")).items():
            if bucket in IGNORED_BUCKETS:
                continue
            ftype = BUCKET_TYPE.get(bucket)
            if ftype is None:
                log.warning("balde desconhecido %s (%d feições)", bucket, len(feats))
                continue
            for ft in feats:
                p = ft.get("properties") or {}
                geom = qgis_geometry(ftype, ft.get("geometry"), p)   # seção 5
                if geom is None:
                    log.warning("geometria inválida em %s %s", ftype, p.get("id"))
                    continue
                blob = images.get(p.get("id")) if ftype in BITMAP_TYPES else None
                w.add_feature(ftype, name, p.get("layerId") or "default", geom, p,
                              bitmap=blob, desenho=ft.get("geometry"))
                for foto in p.get("images") or []:
                    w.add_photo(p.get("id"), foto, images.get(foto.get("id")))
    w.close()
    build_layer_tree(gpkg_path, current=data.get("currentMap"))     # seção 4.5
```

---

## 10. Onde entra no plugin

- **Ponto de entrada.** Um algoritmo novo no provider de Processing existente (`EBGeo/Processings/provider.py`, id `EBGeoProvider`), com parâmetros arquivo `.ebgeo`, GeoPackage de saída e "carregar no projeto", mais uma ação no menu EBGeo que abre o diálogo do algoritmo (`processing.execAlgorithmDialog`), como já fazem Mosaico, Moldura e Linha de Visada em `EBGeo/ebgeo.py`. Arrastar o `.ebgeo` para o canvas é um ganho de uso: um `QgsCustomDropHandler` registrado pelo plugin chama o mesmo algoritmo.
- **Padrões que já existem no plugin.** O desempacotamento de ZIP em pasta temporária e o encadeamento por `processing.run` em `Processings/convertEDGVzipToMASACODE.py:84-107`; o mapeamento "uma classe por tipo de camada" em `insertMASACODE.py` (`AbstractEDGVClass`); a cópia de template e a aplicação de estilo em `MilitarySimbologyTools/model/baseDeDados.py`.
- **Não existe hoje** nenhum leitor de `.ebgeo`, KML ou GeoJSON no plugin (grep em todo `EBGeo/`).
- **Exportar de volta** (`.ebgeo` a partir do GPKG) fica fácil por causa da coluna `props` e da tabela `ebgeo_documento`, mas não foi pedido. Se vier, respeitar a mão única: exportar com `version` igual à de origem e nunca acima de 3.0.

---

## 11. Medidas feitas nesta análise

Feitas no Python do QGIS 4.0.0 instalado (PyQt6, Python 3.12), com scripts de bancada fora do repositório.

| Medida | Resultado | Pior caso que reprova |
|---|---|---|
| Abrir as 5 fixtures com `raw[6:]` XOR `0xAA` | 5 de 5 abrem, cabeçalho `EBGXOR` em todas | |
| Contagem de camadas QGIS por estratégia | tabela da seção 4.3 | |
| PNG de símbolo militar da 03 como marcador raster `base64:` vindo de campo | 6 feições desenhadas, 646 pixels de tinta na amostra | mesma camada com caminho vazio: 0 pixels |
| SVG de símbolo gerado (milsymbol) num campo do GPKG, marcador SVG `'base64:' \|\| "svg"`, estilo salvo em `layer_styles` | reabre como `SvgMarker` com a expressão, sem código do plugin | antes de salvar o estilo, a camada reabria como `SimpleMarker` |
| Enums no QGIS 4 | enums QGIS sem escopo (`QgsWkbTypes.Polygon`, `QgsVectorFileWriter.NoError`) ainda funcionam; enums Qt sem escopo (`QEvent.MouseMove`, `QLineEdit.Normal`, `QFont.Bold`) dão `AttributeError` | |
| Bibliotecas no Python do QGIS 4 | pyproj 3.7.2, shapely 2.1.2, numpy 2.4.2, GDAL 3.12.2 | |

---

## 12. O que não foi confirmado

- **Esquema 3.0 em arquivo real.** Não há fixture 3.0. As chaves `engineering_symbols`, foto por referência e `iconOffset` no símbolo militar foram lidas só do código. Próximo passo: exportar um `.ebgeo` pela `main` com símbolo de engenharia, foto anexa e Linha de Coordenação, e incluí-lo nas fixtures.
- **Arquivo v1.x real.** Nenhum na mesa. O `frontend/public/docs/exemplos/exemplo-tutorial.ebgeo` é JSON puro sem versão, recusado pelo portão atual, e não precisa ser aceito.
- **Fator px para metros** (512 contra 256). Medir lado a lado: o mesmo `.ebgeo` aberto no EBGeo Web e no QGIS no mesmo zoom, comparando o tamanho de um símbolo na tela.
- **Unidade da elipse** (km, por inferência).
- **Feição em dois grupos** ou grupo com membros de camadas distintas: 0 casos nas fixtures; a regra do app não foi lida.

---

## 13. Plano de implementação sugerido

A implementação vai direto no branch `qgis4` (decisão do chefe, 2026-10-04), sem branch de feature.

| Fase | Entrega | Pronto quando |
|---|---|---|
| 1 | Leitor (`ebgeo_reader.py`) sem dependência de QGIS, com testes nas 5 fixtures | contagem por balde igual à da seção 3.3 nas 5 fixtures; arquivo truncado, versão 3.1 e ZIP sem `data.json` recusados com a mensagem certa |
| 2 | Escritor GPKG por tipo + tabelas de apoio + QML por tipo das formas comuns (ponto, linha, polígono, círculo, elipse, retângulo, setor, pincel, texto, imagem) | reabrir o GPKG num QGIS sem o plugin e ver as formas estilizadas; conferir campo a campo 1 feição por tipo contra o `data.json` |
| 3 | Bitmaps (símbolo, medida, engenharia, declinação, ícones) como marcador raster `base64:` com âncora e deslocamento; linhas táticas pela `geom_desenho` | comparação visual com o EBGeo Web no mesmo zoom em 3 mapas da 03 |
| 4 | Árvore de camadas (seção 4.5): grupo exclusivo por mapa, subgrupo por camada, ordem customizada, materialização preguiçosa | mapa "10 Camadas" da 03 com camada oculta, bloqueada e semitransparente se comportando como no web |
| 5 | Troca dos bitmaps e da `geom_desenho` pelos renderizadores vivos do documento irmão | editar uma Linha de Limite importada com a ferramenta do plugin e ver o escalão acompanhar |

---

## 14. Achados fora do escopo

- O PROJECT.md do projeto de transição para o EBGeo 3.0, no vault de gestão, diz que o import direto ao servidor "entrega os baldes crus ao mapeador". O código atual já normaliza (`frontend/src/js/import_export/local-atlas-to-server.js:450`).
- O README das fixtures chama de `main` a linha 2.4 (nomes de branch anteriores a 2026-10-02) e aplica o XOR ao cabeçalho junto com o corpo.
- `frontend/public/docs/exemplos/exemplo-tutorial.ebgeo` é arquivo morto, sem referência no código.
