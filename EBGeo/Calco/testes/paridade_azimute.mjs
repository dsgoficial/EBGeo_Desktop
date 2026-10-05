// Paridade do Azimute e Distância: roda os casos no código do EBGeo Web (node, sem navegador) e
// devolve o que o Web calcula, para testes/test_azimute.py comparar com Calco/azimute/geometria.py.
//
// Uso: node paridade_azimute.mjs --web <raiz do ebgeo_web>  < casos.json  > saida.json
// Cada caso: { referencePoint, legs, outputMode, angularUnit, distanceUnit, northReference,
//              magneticDeclination, meridianConvergence? }
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const i = process.argv.indexOf('--web');
if (i < 0 || !process.argv[i + 1]) {
    console.error('uso: node paridade_azimute.mjs --web <raiz do ebgeo_web>');
    process.exit(2);
}
const web = process.argv[i + 1];
const front = join(web, 'frontend');
const require = createRequire(join(front, 'package.json'));
globalThis.turf = require('@turf/turf');

const src = (rel) => pathToFileURL(join(front, 'src', 'js', rel)).href;
const geo = await import(src('azimuth_distance_tool/azimuth_distance_geometry.js'));
const { calculateMeridianConvergence } = await import(src('utilities/geomagnetic/meridian_convergence.js'));

let entrada = '';
for await (const pedaco of process.stdin) entrada += pedaco;
const casos = JSON.parse(entrada);

const saida = casos.map((c) => {
    const convergencia = geo.resolveConvergence(c);
    const vertices = geo.calculateWaypoints(c.referencePoint, c.legs, c.magneticDeclination, c.northReference,
        c.angularUnit, c.distanceUnit, convergencia);
    const geometria = c.outputMode === 'point' ? null : geo.generateGeometry(vertices, c.referencePoint, c.outputMode);
    const feicao = c.outputMode === 'point' ? null : geo.generateFeature({
        ...c, meridianConvergence: c.meridianConvergence, style: {}, id: 'x', geoJsonId: 1, layerId: 'default', name: 'n',
    });
    const leituras = geo.legsInThreeNorths(c.legs, {
        angularUnit: c.angularUnit, northReference: c.northReference,
        declination: c.magneticDeclination, convergence: convergencia,
    });
    return {
        convergencia,
        convergenciaPonto: calculateMeridianConvergence(c.referencePoint[1], c.referencePoint[0]),
        vertices,
        geometria,
        polar: feicao ? feicao.properties.azimuthDistanceData : null,
        leituras,
        textos: leituras.map((r) => (r ? [geo.formatAngleReading(r.nv, c.angularUnit), geo.formatAngleReading(r.nq, c.angularUnit),
            geo.formatAngleReading(r.nm, c.angularUnit)] : null)),
        correcoes: [geo.formatCorrection(c.magneticDeclination), geo.formatCorrection(convergencia)],
        total: geo.formatTotalDistance(geo.calculateTotalDistance(c.legs), c.distanceUnit),
        podeCriar: geo.canCreateFeature(c.referencePoint, c.legs, c.outputMode),
    };
});
process.stdout.write(JSON.stringify(saida));
