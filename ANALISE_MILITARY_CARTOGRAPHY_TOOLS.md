# Military Cartography Tools: o que vale trazer para o EBGeo Desktop e o EBGeo Web

Análise de 2026-10-04 do plugin QGIS Military Cartography Tools (MCT, https://github.com/kattapraveen/MilitaryCartographyTools, commit d21995c de 2026-09-30, versão 1.5.0, GPL-2.0+, QGIS 3.44 a 4.99), lido por dois agentes em paralelo (simbologia; demais ferramentas) e conferido por amostragem no código. Comparação com o EBGeo Desktop no `qgis4` (`eb760ab`) e com o `ebgeo_web` na `main`.

**Licença.** O EBGeo Desktop é GPL-2: pode incorporar código do MCT com crédito (autor e arquivo de origem) e marcando a modificação. O EBGeo Web é privado e distribuído ao navegador: dele só se aproveita a IDEIA, reimplementada a partir da norma (Apêndice H do MIL-STD-2525D) e de medida própria. Isto é leitura técnica, não parecer jurídico.

---

## 1. O retrato em uma tela

| | MCT | EBGeo (Desktop e Web) |
|---|---|---|
| Gráficos táticos | 463 tipos de medida de controle do Apêndice H (136 linhas, 85 áreas, 242 pontos), mais leque de alcance, anéis QBRN, curvas de dose | 8 ferramentas: símbolo por SIDC com extensão brasileira, 130 medidas de coordenação, 34 de engenharia, Linha de Limite, 10 linhas do MD33, Seta, Frente Ocupada, Declinação. **Nenhuma área tática nem linha de controle com sigla** |
| Arquitetura | tudo passa por funções Python `mct_*` no estilo: sem o plugin, o ponto vira marcador de reserva e a linha construída some | "nativo e assado": abre num QGIS sem o plugin |
| Captura | nenhuma ferramenta de mapa: digitaliza-se com as ferramentas do QGIS, e o número de pontos é convenção | gesto do Web (clique direito finaliza), tamanhos iniciais pelo zoom, painel e construtor de SIDC |
| Paridade com outra plataforma | não há | byte a byte com o EBGeo Web; importa o `.ebgeo` |
| Terreno | viewshed só GDAL com recorte e reprojeção automáticos, **cobertura de radar com alvo em altitude fixa**, Tanaka, tinta hipsométrica, sombreado multidirecional | viewshed por GRASS, análise por setor com soma de observadores (melhor que a deles), linha de visada em polilinha |
| Grade e layout | grade MGRS no canvas (GZD, 100 km, 10/5/1 km), moldura com dígitos principais, layout militar com classificação, série de folhas | molduras da articulação sistemática (MI), BDGEx, mosaico |
| Testes | 2.018 testes headless | 110 no Calco; o resto do plugin sem testes |

**Leitura:** a arquitetura deles não serve (perde o desenho sem o plugin), mas o CATÁLOGO e várias RECEITAS servem, porque quase todas viram expressão nativa. A maior lacuna doutrinária nossa, no Desktop e no Web, são as **áreas táticas e as linhas de controle com sigla**.

---

## 2. Prioridades recomendadas

Custo: P (até um dia), M (alguns dias), G (semana ou mais). Nomes e siglas do EB entre parênteses ainda não conferidos no MD33-M-02.

### Simbologia militar

| # | Item | O que é | Receita (nativa, abre sem o plugin) | Desktop | Web | Valor |
|---|---|---|---|---|---|---|
| S1 | Linhas de controle com sigla | LP, LC, linha de fase, LimAv, LAADA, LP/LC, LCF; status planejado tracejado | linha simples, sigla nas pontas por âncora estrita do rótulo (0 % e 100 %), caixa alta, tracejado por status | P | M | Alto |
| S2 | Áreas táticas | Z Reu, Obj, A Eng, P Atq, Z Aç, ZPH, Z Lanç, área de interesse | polígono, "PREFIXO NOME" no polo de inacessibilidade (`pole_of_inaccessibility()`, conferido no 4.0.0), escalão no perímetro com vão | P | M | Alto |
| S3 | Coordenação de apoio de fogo | linhas FSCL, RFL, NFL, CFL; áreas de fogo proibido (hachurada), livre, restrita, ACA, PAA | hachura nativa, rótulos por âncora, PAA pelo ponto médio de cada lado | P | M | Alto (Art) |
| S4 | Setor de tiro e leque de alcance | arma coletiva, Art, AAAe, radar; até 5 anéis com azimutes e alcance | `wedge_buffer(centro, azimute, abertura, externo, interno)` (área conferida no 4.0.0), na projeção local que já usamos | M | M | Alto |
| S5 | Campos de minas | AP, AC, misto, suspeito, simulado; minado dinâmico | polígono, SVG de mina do nosso catálogo no polo de inacessibilidade; dinâmico por preenchimento aleatório semeado sobre `buffer(-d)` | M | M | Alto (Eng) |
| S6 | Pontos de controle que faltam | P Ct, P Pas, P Jç, P Reu, P Lib, P Inic, P Ctt | já gerados por SIDC no motor; faltam no catálogo das 130 medidas | P | P | Médio-alto |
| S7 | Posição defensiva e ponto forte | "(P)", ponto forte dentado para fora | reaproveita o dente contínuo da Linha de Coordenação no anel orientado | M | M | Médio-alto |
| S8 | Tarefas táticas | Destruir, Bloquear, Fixar, Canalizar, Conter, Reter, Ocupar, Isolar, Retardar, Retrair, Cobertura, C Atq, Conquistar... | uma expressão por glifo, de 2 a 3 pontos, entregue uma a uma | G (M cada) | G | Médio-alto |
| S9 | Variantes da Seta | ataque principal, secundário, finta (tracejado), inimigo em vermelho | atributo `variante` e trecho de expressão | P a M | P a M | Médio |
| S10 | Rotas | estrada principal de suprimento, alternativa, mão única, dupla | linha, rótulo e seta no centro, sempre de pé | P | P | Médio |
| S11 | Alvos e barragem | alvo linear, FPF, fumaça; barragem com largura real por arma (ideia do branch apagado) | traço perpendicular nas pontas, largura em metros | P a M | P a M | Médio (Art) |
| S12 | Símbolo no layout | quadro de convenções do calco | figura a partir do `svg` já gravado na feição | P | não se aplica | Médio |

**Achado a conferir antes de tudo:** o MCT documenta que o milsymbol 3.0.4 sem `setStandard` desenha oito modificadores 1 de Unidade (01, 47, 56, 58, 71, 72, 73, 74) diferentes da tabela D-VI impressa do 2525D (`THIRD_PARTY_NOTICES.md` do MCT). Web e Desktop usam o mesmo milsymbol do mesmo jeito; a nossa extensão brasileira já substitui o 01 e o 47. Os outros seis precisam ser conferidos contra o MD33.

### Demais ferramentas

| # | Item | O que é | Desktop | Web | Valor |
|---|---|---|---|---|---|
| F1 | WMM2025 no Desktop | o modelo magnético da ferramenta de declinação é o WMM-2020, vencido; diferença medida de até 0,24° no Rio (4 milésimos) contra o 2025, e o Web e a carta já usam o 2025 | P (o Calco já traz o `WMM2025.COF`) | já tem | Alto |
| F2 | Cobertura de radar ou sensor em altitude fixa | onde uma aeronave a Z m é vista: `gdal_viewshed -om DEM`, k = 0,25, fusão das coberturas por afiliação, regenera ao gravar | M | M (sobre a varredura por raios que o Web já faz) | Alto (AAAe, contra-drone) |
| F3 | Azimute de três nortes | dois cliques: verdadeiro, de quadrícula e magnético, mais distância geodésica e log | P | P (conferir o de quadrícula) | Alto |
| F4 | GPX/KML de pontos com nome em MGRS | para GPS de mão e ATAK; importa acrescentando o MGRS | P | P (hoje o Garmin é raster) | Alto |
| F5 | Viewshed sem GRASS | gdal:viewshed com recorte e reprojeção automáticos e guarda de extensão do MDE, mantendo a nossa soma de observadores por setor | M | não precisa | Médio |
| F6 | k de refração único | hoje três ferramentas usam três valores (0,13; 0,14286; o padrão do GDAL) | P | conferir | Médio |
| F7 | Grade MGRS e moldura com dígitos principais | GZD, 100 km, 10/5/1 km no canvas e no layout | M | rótulo do quadrado de 100 km no PDF, P a M | Médio-alto |
| F8 | Funções de expressão | MGRS, declinação e convergência ao vivo em rótulo e layout | P | não se aplica | Médio |
| F9 | Linha de visada em qualquer SRC | dois cliques, reprojeção automática, mantendo a nossa polilinha e a nossa cor | P | já tem | Médio |
| F10 | Sombreado multidirecional e tinta hipsométrica | com classes FIXAS, não esticadas por execução como as deles | P | tinta por `color-relief` do MapLibre, P | Médio |
| F11 | Série de folhas | atlas sobre as molduras MI | M | já tem mosaico | Médio |

### Engenharia do projeto

- Testes headless com o Python do QGIS (`QT_QPA_PLATFORM=offscreen`, um `QgsApplication` por processo) para o resto do plugin, começando por declinação, linha de visada e viewshed, com MDE sintético e testes que reprovam o defeito anterior.
- Empacotamento por lista branca (hoje o pacote leva pyqtgraph, geopy com cerca de 30 geocodificadores e módulos desativados) e atualizar o `release.yml` (Python 3.8, `checkout@v2`).
- Uma base só para QGIS 3.44 a 4.x é possível, mas o QJSEngine do Calco no 3.44 precisa ser medido antes.
- **Não copiar deles:** processamento síncrono sem `QgsTask` (a cobertura de sensores congela a interface a cada gravação), rampa hipsométrica esticada por execução, cota negativa forçada a 0 m, cor por amostra na linha de visada.

---

## 2b. Revisão com o chefe e contra o MD33-C-01 (2026-10-04)

O chefe lembrou que o catálogo brasileiro já está quase todo implementado. Conferi o capítulo VII (Símbolos de Medidas de Coordenação, p. 183 a 200 do MD33-C-01, 1ª edição/2021) código a código contra o `ebgeo_web`:

- **Pontos:** todos os pontos do capítulo VII estão no catálogo das 130 medidas (movimento e manobra, passagens, concentração de fogos, destruições, fortificações, minas, campo minado e área minada, QBRN, ponto de suprimento, controle aéreo, controle marítimo), **exceto o Arame de tração (290500)**.
- **Linhas e áreas com traçado próprio que já existem:** Limite (110100), Frente ocupada (152200), Direção de ataque e direção aeromóvel (Seta), os 10 obstáculos e fortificações lineares (Linha de Coordenação).
- **O que o capítulo VII tem e ainda não implementamos** (todos de linha, corredor ou área):

| Código | Símbolo | Página |
|---|---|---|
| 140000 | Linha de manobra genérica (com a sigla, para LP, LC, Linha de Cabeça de Praia, pelas regras do MD33-M-02) | 184, 188 |
| 140200 | Linha de Contato | 184 |
| 152000 | Base de fogos | 184 |
| 151400 | Corredor genérico (e Eixo de Progressão, pelas regras do MD33-M-02) | 185, 188 |
| 140699-01 | Ficar em condições de prosseguir | 185 |
| 149900-01 | Corredor de Mobilidade | 185 |
| 150000 | Área genérica, com a descrição sobre a borda, interna ou externa (Objetivo, Zona de Desembarque, Região de Interesse para a Inteligência) | 186, 188, 189 |
| 151100 / 151199-01 | Terreno Restritivo / Terreno Impeditivo | 186 |
| 151203 | Ponto Forte (área) | 186, 189 |
| 151000 | Zona fortificada | 192 |
| 240701 | Concentração de fogos em alvo linear | 189 |
| 140500 | Setor de Tiro (seta reforçada principal, tracejada secundária) | 190 |
| 290500 | Arame de tração | 193 |
| 170000 / 170999-01 | Corredor aéreo / Volume de aproximação de base | 196 |

Hoje a área genérica com descrição interna se faz com o polígono comum e rótulo. A linha comum do Web não tem rótulo, então a linha de manobra com sigla não se faz. FSCL, áreas de fogo proibido e afins NÃO estão no MD33-C-01: o item S3 da tabela acima cai. A exportação GPX/KML (F4) foi descartada pelo chefe. O azimute de três nortes (F3) já existe em parte: o Web dá o verdadeiro ou o magnético e o Desktop calcula declinação e convergência; falta só o de quadrícula no Web.

## 3. Sugestão de ordem

1. **F1** (WMM2025 no Desktop): FEITO em 2026-10-04 (`0792270`): diferença contra o Web caiu de 0,232 para 0,004 grau.
2. **As lacunas do capítulo VII do MD33-C-01** (tabela da seção 2b), no Web e no Desktop juntos, com o mesmo esquema no `.ebgeo`: linha de manobra com sigla, linha de contato, base de fogos, corredores, áreas com descrição, terreno restritivo e impeditivo, ponto forte e zona fortificada, setor de tiro, alvo linear, arame de tração, corredor aéreo.
3. **F2** (cobertura de radar ou sensor em altitude fixa), se houver demanda de AAAe ou contra-drone.
4. As receitas do MCT servem de técnica para o item 2 (sigla nas pontas por âncora, rótulo no polo de inacessibilidade, setor anelar por `wedge_buffer`).

## 4. Não confirmado

- As famílias simples do MCT desenhando sem o plugin (lido no código, não testado).
- A máscara seletiva de rótulo sobrevivendo ao estilo salvo no GeoPackage em outro projeto (ela referencia o id da camada).
- Desenho do Geometry Generator em unidade de página.
- Os nomes e siglas do EB na tabela de simbologia, a conferir no MD33-M-02.
- Se o Web já rotula o quadrado MGRS de 100 km e dá o azimute de quadrícula.
- Se `grass7:r.viewshed` ainda resolve no QGIS 4.

## 5. Achados de passagem no nosso código

- `EBGeo/ZoomCoordenadas/mgrs.py:394` ainda tem `letters[1] in [invalid]`, que desliga a validação UPS (só afeta os polos); o MCT corrigiu o mesmo defeito do mesmo motor.
- `EBGeo/auxiliar/auxDeclConv.py:71` e `:83` chamam `mapRenderer()`, que não existe desde o QGIS 3 (parece código morto).
