// O que o EBGeo Web desenha de cada feição de um .ebgeo, lido pelo próprio código do Web em node:
// o arquivo entra pelo portão e pela normalização de import_export; cada feição é avaliada nas
// camadas MapLibre que o Web registra (setup*Layers num mapa falso), com o compilador de
// expressões do MapLibre (@maplibre/maplibre-gl-style-spec), na fonte da feição, na fonte de
// rótulo (labelFeatureFor) e nas fontes derivadas (buildAreaDecorations; generate e layout da
// Linha de Coordenação, do Limite, da Seta e da Frente; o SVG da declinação). Das fontes derivadas
// entram a geometria e as camadas avaliadas, não as propriedades copiadas, que não desenham. A saída é, por id, as propriedades
// normalizadas e a assinatura do desenho (um texto: duas feições com a mesma assinatura desenham
// igual no Web, salvo o bitmap do símbolo pontual, que o chamador acrescenta).
import { register, createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join, basename } from 'node:path';
import { tmpdir } from 'node:os';

const [frontend, arquivo, saida, zoomTxt] = process.argv.slice(2);
const ZOOM = Number(zoomTxt || 13);
const src = join(frontend, 'src');
const js = join(src, 'js');
const dir = mkdtempSync(join(tmpdir(), 'ebgeo-web-assin-'));
const req = createRequire(join(frontend, 'package.json'));
const ALIAS = { '@js/': js, '@css/': join(src, 'css'), '@store/': join(js, 'store'), '@state/': join(js, 'state'),
  '@utils/': join(js, 'utilities'), '@tools/': join(js, 'tool_manager'), '@toolbar/': join(js, 'toolbar'),
  '@modals/': join(js, 'modals'), '@sidebar/': join(js, 'sidebar'), '@layers/': join(js, 'layers'),
  '@catalog/': join(js, 'catalog'), '@ui/': join(js, 'ui'), '@events/': join(js, 'events'), '@/': src };
const hooks = join(dir, 'hooks.mjs');
writeFileSync(hooks, `
import { pathToFileURL, fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { statSync } from 'node:fs';
const ALIAS = ${JSON.stringify(ALIAS)};
const JSZIP = ${JSON.stringify(pathToFileURL(req.resolve('jszip')).href)};
const VAZIO = 'data:text/javascript,export default ""';
const MAPLIBRE = 'data:text/javascript,' + encodeURIComponent('export const Map = class {}; export const Popup = class {}; export const Marker = class {}; export const LngLat = class {}; export const LngLatBounds = class {}; export const setWorkerUrl = () => {}; export const addProtocol = () => {}; export const config = {}; export default {}');
function existe(u) { try { return statSync(fileURLToPath(u)); } catch { return null; } }
function pasta(url) {
  if (!url.startsWith('file:')) return url;
  const s = existe(url);
  if (s && s.isDirectory()) return url + '/index.js';
  if (!s && existe(url + '.js')) return url + '.js';
  return url;
}
export async function resolve(spec, ctx, next) {
  if (spec === 'jszip') return { url: JSZIP, shortCircuit: true };
  if (spec.includes('?worker') || spec.endsWith('?raw') || spec.endsWith('?url') || /\\.(css|png|svg)$/.test(spec)) return { url: VAZIO, shortCircuit: true };
  if (spec === 'maplibre-gl') return { url: MAPLIBRE, shortCircuit: true };
  for (const [p, d] of Object.entries(ALIAS)) {
    if (spec === p.slice(0, -1)) return { url: pasta(pathToFileURL(d).href), shortCircuit: true };
    if (spec.startsWith(p)) return { url: pasta(pathToFileURL(join(d, spec.slice(p.length))).href), shortCircuit: true };
  }
  if ((spec.startsWith('./') || spec.startsWith('../')) && ctx.parentURL) {
    const u = new URL(spec, ctx.parentURL).href;
    const p = pasta(u);
    if (p !== u) return { url: p, shortCircuit: true };
  }
  return next(spec, ctx);
}
`);
register(pathToFileURL(hooks).href);
globalThis.window = globalThis;
globalThis.localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
const turfMod = await import(pathToFileURL(req.resolve('@turf/turf')).href);
globalThis.turf = { ...(turfMod.default ?? turfMod) };
const spec = await import(pathToFileURL(req.resolve('@maplibre/maplibre-gl-style-spec')).href);
const imp = (p) => import(pathToFileURL(join(js, ...p.split('/'))).href);

const gate = await imp('import_export/ebgeo-file-gate.js');
const norm = await imp('import_export/import-normalize.js');
const estilos = await imp('layers/styles/index.js');
const rotulo = await imp('tool_manager/helpers/label-tab.helpers.js');
const area = await imp('military_tools/coordination_area_tool/coordination_area_drawing.js');
const CL = (await imp('military_tools/coordination_line_tool/add_coordination_line_geometry.js')).default;
const BD = (await imp('military_tools/boundary_tool/add_boundary_geometry.js')).default;
const AR = (await imp('military_tools/arrow_tool/add_arrow_geometry.js')).default;
const OF = (await imp('military_tools/occupied_front_tool/add_occupied_front_geometry.js')).default;
const decl = await imp('military_tools/declination_tool/declination_svg_generator.js');
const cl = new CL(), bd = new BD(), ar = new AR(), of = new OF();
const { CoordinationMeasureGenerator } = await imp('military_tools/coordination_measure_tool/coordination_measure_generator.js');
const { codigoDesenhavel } = await imp('military_tools/coordination_measure_tool/familias-de-escalao.js');
const { applyGeneratedBitmap, bitmapStampChanges } = await imp('layers/bitmap-version.js');

// O Web abre o arquivo e redesenha o bitmap da Medida: a importação não guarda o registro de
// desenho local (getLocalBitmap), registerFromDisk de layer_setup.js não serve, e
// restoreGeneratedBitmap chama o regenerador (_regenerateRemote do controle), que carimba o
// resultado do gerador na feição (stampRegeneratedBitmap: applyGeneratedBitmap, com a âncora do
// catálogo). O gerador é o do Web, sem a rasterização, que node não tem; o tamanho e o
// deslocamento do bitmap entram pela assinatura do gerador que o chamador acrescenta. O gerador
// que recusa deixa a feição como veio, e o Web guarda o bitmap do arquivo. Sem isto a camada era
// avaliada com a âncora do arquivo, e a âncora da Medida parecia lida só pelo Web.
const geradorMedida = new CoordinationMeasureGenerator();
geradorMedida.convertToPngBlob = async (_svg, largura, altura) => ({ blob: {}, imagem: null, width: largura, height: altura });
async function redesenhoAoAbrir(balde, f) {
  if (balde !== 'coordination_measures') return;
  const p = f.properties;
  let r;
  try { r = await geradorMedida.generate(codigoDesenhavel(p.pointCode, p.echelonCode), p); } catch { return; }
  if (r && bitmapStampChanges(p, r)) applyGeneratedBitmap(p, r);
}

// O Web desenha uma feição montando as fontes e as camadas pelas próprias funções setup*Layers:
// cada uma recebe o balde, passa as feições pelo que as prepara (pointSourceFeatures,
// symbolSourceFeatures, boundarySourceFeatures, coordinationLineSourceFeatures, a fonte de rótulo
// de syncLabelSource...) e escreve a fonte. Aqui cada feição ganha um mapa falso novo, e o que se
// avalia é o que ficou em cada fonte, com as camadas daquela fonte.
const BALDES = ['points', 'lines', 'polygons', 'circles', 'ellipses', 'rectangles', 'setores', 'texts', 'images',
  'brushes', 'los', 'visibility', 'processed_los', 'processed_visibility', 'arrows', 'boundarys', 'occupied_fronts',
  'coordination_lines', 'coordination_areas', 'military_symbols', 'coordination_measures', 'engineering_symbols',
  'magnetic_declinations'];
function mapaFalso() {
  const camadas = [];
  const fontes = new Map();
  const mapa = {
    getSource: (id) => fontes.get(id) || null,
    addSource(id, s) { fontes.set(id, { ...s, setData(d) { this.data = d; }, updateData() {}, getData: async () => this.data }); },
    removeSource(id) { fontes.delete(id); },
    getLayer: (id) => camadas.find((c) => c.id === id) || null,
    addLayer(def) { camadas.push(def); }, removeLayer() {}, moveLayer() {}, setLayoutProperty() {}, setPaintProperty() {},
    setFilter() {}, hasImage: () => true, addImage() {}, on() {}, off() {}, once() {}, getZoom: () => ZOOM,
    getBearing: () => 0, getStyle: () => ({ layers: camadas }), style: {}, loaded: () => true,
    isStyleLoaded: () => true, triggerRepaint() {}, getCanvas: () => ({ style: {} }),
  };
  return { mapa, camadas, fontes };
}
function montar(balde, feicao) {
  const m = mapaFalso();
  const feats = Object.fromEntries(BALDES.map((b) => [b, b === balde ? [feicao] : []]));
  for (const [nome, f] of Object.entries(estilos)) {
    if (typeof f === 'function' && nome.startsWith('setup')) {
      try { f(feats, m.mapa); } catch { /* os auxiliares pedem um mapa de verdade e não desenham feição */ }
    }
  }
  return m;
}
let porFonte = {};
function desenhoNoWeb(balde, feicao) {
  const m = montar(balde, feicao);
  porFonte = {};
  for (const c of m.camadas) (porFonte[c.source] ||= []).push(c);
  const out = {};
  for (const [id, fonte] of m.fontes) {
    if (/feedback|edit-handles|measurement/.test(id)) continue;
    // só a feição que alguma camada desenha entra (o ponto de rótulo sem texto não desenha nada)
    const desenhadas = [];
    for (const x of fonte.data?.features || []) {
      const cam = camadasDe(id, [x]);
      if (Object.values(cam).some((l) => l.some((r) => !('filtro' in r)))) desenhadas.push({ geometria: x.geometry, cam });
    }
    if (desenhadas.length) out[id] = desenhadas;
  }
  return out;
}

const TIPO_GEOM = { Point: 1, MultiPoint: 1, LineString: 2, MultiLineString: 2, Polygon: 3, MultiPolygon: 3 };
const compiladas = new Map();
function compilar(valor, especificacao, raiz) {
  const chave = JSON.stringify(valor) + '|' + JSON.stringify(especificacao?.type);
  if (!compiladas.has(chave)) {
    let e;
    try { e = spec.normalizePropertyExpression(valor, raiz, especificacao); } catch (err) { e = { erro: String(err.message) }; }
    compiladas.set(chave, e);
  }
  return compiladas.get(chave);
}
function serial(v) {
  if (v === undefined) return null;
  if (v && typeof v === 'object') {
    if (typeof v.toString === 'function' && v.constructor && /Color|Formatted|ResolvedImage|Padding/.test(v.constructor.name)) {
      return v.constructor.name + ':' + (v.constructor.name === 'Formatted' ? JSON.stringify(v.sections.map((s) => s.text)) : (v.toString?.() ?? JSON.stringify(v)));
    }
  }
  return v;
}
const filtros = new Map();
function filtroDe(c) {
  if (!filtros.has(c.id)) filtros.set(c.id, spec.featureFilter(c.filter, `layers.${c.id}.filter`));
  return filtros.get(c.id);
}
function avaliarCamada(c, feicao) {
  const f = { type: TIPO_GEOM[feicao.geometry?.type] ?? 1, properties: feicao.properties || {}, id: feicao.properties?.id,
              geometry: [] };
  const glob = { zoom: ZOOM };
  if (c.filter) {
    let passa;
    try { passa = filtroDe(c).filter(glob, f); } catch (err) { passa = 'erro:' + err.message; }
    if (passa !== true) return { filtro: passa };
  }
  const out = {};
  for (const grupo of ['paint', 'layout']) {
    for (const [prop, valor] of Object.entries(c[grupo] || {})) {
      const especificacao = spec.latest[`${grupo}_${c.type}`]?.[prop];
      if (!especificacao) { out[prop] = 'sem-spec'; continue; }
      const e = compilar(valor, especificacao, `layers.${c.id}.${grupo}.${prop}`);
      if (e?.erro) { out[prop] = 'erro:' + e.erro; continue; }
      try { out[prop] = serial(e.evaluate(glob, f, {}, undefined, [])); } catch (err) { out[prop] = 'erro:' + err.message; }
    }
  }
  // camada de texto sem ícone e com texto vazio não desenha nada
  if (c.type === 'symbol' && !c.layout?.['icon-image'] && out['text-field'] === 'Formatted:[""]') return { filtro: false };
  return out;
}
function camadasDe(fonte, feicoes) {
  const out = {};
  for (const c of porFonte[fonte] || []) {
    if (/feedback|edit-handles|preview|measurement/.test(c.id)) continue;
    out[c.id] = feicoes.map((f) => avaliarCamada(c, f));
  }
  return out;
}


function derivadas(balde, f) {
  const p = f.properties;
  const coords = p.baseCoordinates;
  try {
    if (balde === 'coordination_areas') {
      const deco = area.buildAreaDecorations(f, ZOOM);
      return { deco: deco.map((x) => x.geometry), camadas: camadasDe('coordination-area-decorations', deco) };
    }
    if (balde === 'coordination_lines' && coords) {
      const q = { ...p, baseCoordinates: coords };
      const g = { type: 'Feature', geometry: cl.generate(q, ZOOM), properties: q };
      const extras = typeof cl.buildAllExtras === 'function' ? cl.buildAllExtras([g], ZOOM, 0) : [];
      return { geom: g.geometry, layout: cl.describeLayout(q, ZOOM), extras: extras.map((x) => x.geometry), camadas: camadasDe('coordination-line-extras', extras) };
    }
    if (balde === 'boundarys' && coords) {
      const q = { ...p, baseCoordinates: coords };
      const g = { type: 'Feature', properties: { id: 'x', ...q } };
      const circ = bd.generateBoundaryCircles(g, ZOOM), txt = bd.generateBoundaryTexts(g, ZOOM, 0);
      return { geom: bd.generate(q, ZOOM), circ: circ.map((x) => x.geometry), txt: txt.map((x) => x.geometry), camadasC: camadasDe('boundary-circles', circ), camadasT: camadasDe('boundary-texts', txt) };
    }
    if (balde === 'arrows' && coords) return { geom: ar.generate(coords, p) };
    if (balde === 'occupied_fronts' && coords) return { geom: of.generate(coords) };
    if (balde === 'magnetic_declinations') {
      // generateDeclinationBitmap: a guarda e a chamada, como no Web (sem a rasterização)
      if (!Number.isFinite(p.declination) || !Number.isFinite(p.convergence ?? 0)) return { svg: 'recusa: preserva o bitmap' };
      return { svg: decl.generateDeclinationSvg(p.declination, p.convergence ?? 0, p.fillColor) };
    }
  } catch (err) {
    return { erro: String(err.message) };
  }
  return null;
}

const { data } = await gate.readEbgeoArchive(new File([readFileSync(arquivo)], basename(arquivo)));
const out = {};
for (const m of Object.values(data.maps)) {
  const r = norm.normalizeMapDataForCurrentVersion(structuredClone(m), (l) => ({ processed: l, unavailableCount: 0 }));
  for (const [balde, lista] of Object.entries(r.mapData.features || {})) {
    for (const f of lista || []) {
      await redesenhoAoAbrir(balde, f);
      const assin = { fontes: desenhoNoWeb(balde, f) };
      const d = derivadas(balde, f);
      if (d) assin.derivadas = d;
      // a identidade não é desenho: a variante assina com o id da base (o ícone e o rótulo o leem)
      const idv = String(f.properties.id);
      const idBase = idv.split('§')[0];
      out[idv] = { balde, props: f.properties, assinatura: JSON.stringify(assin).split(idv).join(idBase) };
    }
  }
}
writeFileSync(saida, JSON.stringify(out));
console.log('feições', Object.keys(out).length);
