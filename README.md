# EBGeo
### Ferramentas para utilização da geoinformação digital pelo Exército Brasileiro.
#### DSG - Diretoria de Serviço Geográfico

---
O EBGeo tem a finalidade facilitar o uso da geoinformação digital pelas OM de Corpo de Tropa do Exército Brasileiro, servindo de ferramenta básica para atuar nos PCI de geoinformação e futuramente no Estágio de Geoinformação para Corpo de Tropa.

---
### Ferramentas atuais

1. **BDGEx** - Carrega camadas do BDGEx para o QGIS como imagem (serviço)
2. **Simbologia Militar** - Cria ou carrega banco de dados com simbologia militar prevista no manual MD33-M-02. Visa substituir o calco impresso pelos planos de informação do QGIS. (Ferramenta ainda em desenvolvimento, nem todos os símbolos previstos estão implementados).
3. **Criação de pontos por coordenadas** - Cria um ponto num arquivo existente, a partir de suas coordenadas.
4. **Criação de pontos por azimute/distância** - Permite criar novas feições pontuais em camadas vetoriais de pontos a partir de um ponto predefinido e um azimute e distância a partir do mesmo.
5. **Movimentação de pontos por coordenadas** - Ao selecionar um ponto existente, movê-lo para outra posição a partir das coordenadas da nova posição.
6. **Cálculo de azimutes e distâncias (tabela)** - Seleciona-se vários pontos, ou uma linha ou um polígono e é gerado uma tabela com as coordenadas do primeiro ponto e o azimute e distância para os demais pontos.
7. **Geração de área de alcance do armamento** - Gera buffers de alcance de armamento com base em valor definido pelo usuário, valendo-se também de um azimute de tiro e uma angulação de visada/atuação da peça.
8. **Geração de Mapa de Visibilidade** - Gera um mapa de visibilidade com base num ponto escolhido pelo o usuário conforme o Modelo Digital de Elevação escolhido e altura do observador.
9. **Gerador de Mosaicos** - Mosaica as camadas raster selecionadas com base na moldura fornecida ou automaticamente (moldura automática gerada em Sirgas 2000 EPSG:4674)
10. **Gerador de Molduras** - Gera moldura sistemática relacionada à camada de polígono selecionada baseada na escala selecionada (sistema de referência da moldura igual ao da camada de entrada)
11. **Sombreamento do terreno** - A partir da posição, data e hora indicados, a ferramento calcula a posição do Sol e então gera uma representação visual das sombras no terreno devidas ao relevo.
12. **Conversão de unidades angulares** - Dado um campo da tabela de atributos com ângulos em graus, gera um campo com os ângulos em milésimos.
13. **Medição durante aquisição vetorial** - Apresenta ao usuário as medidas da feição sendo desenhada (distância parcial/acumulada para linhas, área para polígonos) como uma tooltip junto ao cursor.
14. **Determinação do MI (Índice de Nomenclatura) da carta** - Ao clicar em uma região da tela que esteja dentro do Brasil aparecerá qual carta engloba aquela região, nas diversas escalas, sendo possível baixar as cartas na região escolhida.
15. **Calculadora de coordenadas e dimensões** - Calcula automaticamente as coordenadas geográficas e planas de uma camada de pontos. Importante na interação da tropa terrestre com apoio aéreo.
16. **Calculadora de declinação magnética e convergência meridiana** - Selecionando-se um ponto, linha ou polígono são apresentadas a Declinação Magnética e Convergência Meridiana do dado selecionado.
17. **Distância ao longo da linha** - Gera pontos ao longo das linhas de uma camada linha selecionada espaçados pela distância definida pelo usuário.

---

### Processings
1. **Inserir MASACODE** - É um processo, acessado atráves da Caixa de Ferramentas de Processamento, que permite criar uma coluna de atributos associando uma feição de terreno a um código utilizado pelo simulador COMBATER.

---
## Créditos
1. **Declinação magnética** - valor obtido por meio do geomag.py por Christopher Weiss cmweiss@gmail.com, https://github.com/cmweiss/geomag.  Utilizando modelo de coeficientes WMM 2020.0 do NOAA.
NCEI Geomagnetic Modeling Team and British Geological Survey. 2019. World Magnetic Model 2020. NOAA National Centers for Environmental Information. doi: 10.25921/11v3-da71, 2020, 01/14/2020.
2. **Criação de pontos por coordenadas** - adaptação do Trace Digitize Action Copyright (C) 2010  Cédric Möri, with stuff from Stefan Ziegler EMAIL: cmoe@geoing.ch. WEB: www.geoing.ch
3. **Sombreamento do terreno** - valores de posição solar obtidos a partir do sunposition.py por Samuel Bear Powell, https://github.com/s-bear/sun-position.

---
Última versão estável no QGIS: 3.34
