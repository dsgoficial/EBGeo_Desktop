# Build do motor de símbolos pontuais

Gera, a partir de um checkout do EBGeo Web (1cgeo/ebgeo_web), os artefatos que o plugin carrega:

| Arquivo | O que é |
|---|---|
| `../ebgeo-simbologia.js` | bundle IIFE minificado (global `EBGeoSimbologia`) com o milsymbol 3.0.4, a extensão brasileira (`brazilian_*`), o mapeamento de amplificadores, a âncora (`military-symbol-anchor.js`) e o gerador e o catálogo das medidas de coordenação, para o `QJSEngine` |
| `../catalogos.json` | dados da interface: 11 conjuntos com ícones, modificadores 1 e 2 (nomes em português e extensões), listas fixas, campos de texto por conjunto, as 132 medidas por categoria (com a cor padrão, a direção da Base de fogos e o par de direções do Setor de Tiro) |
| `../WMM2025.COF` | coeficientes do World Magnetic Model 2025 (NOAA, domínio público), reescritos do pacote `geomagnetism` que o Web usa |

## Gerar

Precisa de node (testado com o 24) e do `frontend/node_modules` do ebgeo_web instalado. O bundler é o rolldown que o Vite do Web já traz; nada é instalado neste repositório.

```
node build.mjs --web <raiz do ebgeo_web>
# ou: EBGEO_WEB=<raiz do ebgeo_web> node build.mjs
```

O ebgeo_web é privado e este repositório é público: o bundle sai minificado, sem source map e sem os comentários do fonte (o build reprova se achar comentário, `sourceMappingURL` ou caminho de máquina). Ficam só o aviso de licença MIT do milsymbol e uma linha com o commit do Web de origem. O alvo é ES2016 com polyfills (`polyfills.js`) porque o V4 do Qt 6.8.1 não tem espalhamento de objeto, `Object.fromEntries`, `Object.hasOwn`, `globalThis` nem `console`.

## O que o bundle faz diferente do Web

- Nada no desenho: o `svgWeb` devolvido é o SVG que o Web rasteriza, byte a byte (prova em `testes/test_motor.py`), inclusive nas medidas que montam o desenho pelas propriedades (`montarSvg`: Setor de Tiro e campo minado).
- O `svg` devolvido é o `svgWeb` com uma correção para o `QSvgRenderer`, que ignora `dominant-baseline`: o atributo sai e o `y` desce pelo deslocamento que o Chromium aplica, medido com Arial (middle 0,2592, central 0,35, hanging 0,728 do font-size).
- O tamanho lógico é o do canvas do Web sem rasterizar: `fitDrawSize` sobre o tamanho natural do SVG arredondado para inteiro, como o `naturalWidth` do Chromium.
- Na medida, `ancoraX`/`ancoraY` já somam o `icon-anchor` (`bottom` sobe meia altura) ao `iconOffset`, porque o marcador do QGIS é centrado.

## Paridade

`build.mjs --paridade <pasta> --apenas-paridade` gera o arnês `paridade-web.js` (o `MilitarySymbolGenerator`, o `CoordinationMeasureGenerator`, o gerador de declinação e o WMM do Web, intactos), e `paridade.mjs` o roda no Chromium do Playwright do ebgeo_web. Os testes fazem isso sozinhos quando `EBGEO_WEB` está definida.

## Símbolos de engenharia (C 5-36, 23 itens, 34 variantes)

O `engineering_generator.js` e o `engineering_drawing.js` do Web entram intactos e rodam sobre `dom-minimo.js`, que o bundle instala só durante a chamada (o milsymbol nunca vê um `document`). O DOM mínimo cobre o que esses dois módulos usam: `DOMParser` e `XMLSerializer` de SVG, `querySelector(All)` com tag e `[atributo]`, `cloneNode`, `prepend`, `insertAdjacentHTML('beforeend')`, `dataset` (por `Proxy`, que o V4 tem), `classList` e `textContent`. O `getBBox` é calculado no próprio bundle (caminho com extremos de curva quadrática, cúbica e arco; círculo, elipse, linha, retângulo, polígono). O texto é medido pelo Python: `MedidorTexto` (em `motor.py`) com `QFontMetricsF`, fonte em 2048 px sem hinting e escalada, injetado como `__ebgeoMedidor`. A caixa do texto segue o Chromium, medido em 10 tamanhos: altura `round(0,9053 fs) + round(0,2119 fs)`, largura do advance unida à tinta do glifo, texto vazio fora da união.

Diferença que sobra: o Chromium soma à caixa a tinta do glifo hintado em tamanho pequeno, e o Qt mede sem hinting. O viewBox difere até 0,8 unidade nos 60 casos de teste, e o tamanho lógico até 0,5 px (ver `testes/test_motor.py`, `TestEngenharia`). O padrão de pontos do item 15 sai mais claro no QSvgRenderer que no Chromium em escala abaixo de 1; acima de 1,4 os pontos aparecem nítidos.
