// Prueba de los temas (src/componentes/temas.ts, media/css/temas.css) y del tema de un mundo (src/web/modos.ts con
// src/web/mundo.ts).
//
// 1. Los colores, calculados de los archivos de verdad: cada tema está en los tres lugares (temas.ts, el CSS y
//    `telar.modos.TEMAS`); en todos, el texto se lee sobre su fondo; y los de la noche (brasa, rescoldo, ámbar) cumplen lo
//    que prometen: cada color de texto y cada tinta a 4,5:1 o más sobre el fondo, las barras y la fila activa; las tintas
//    con significado distintas entre sí (el rojo del peligro, más); el tenue distinto del texto; oscuros, cálidos y con
//    menos luz azul que el de fábrica.
//    El acento de los de la noche no es azul (una salvia, que combina con lo cálido) y no se confunde con lo tenue.
// 2. El tema de un mundo en la página, con un DOM, un reloj y una API de mentira: el mundo pone su tema al entrar (a su
//    hora y a mano) y lo saca al salir; sin tema, el del modo; elegido a mano, dura en ese mundo hasta entrar a otro con
//    tema; un cambio en ⚙ mundos se ve al tiro; y al volver a abrir la página, el del mundo desde el principio.
// 3. El color propio de una tinta (`[temas.<tema>]`, web/colores.ts, ⚙ temas): la paleta de cada tinta de cada tema se
//    lee bien; los avisos dicen lo que se lee mal o se confunde (y nada con los de fábrica); la hoja que los pone; y en la
//    página, que llegan de la API, se prueban sin escribir, se escriben con PATCH, avisan a quien escucha (la terminal) y
//    al volver a abrir la página están desde el principio, antes de que conteste la API.
// 4. Los fondos y las líneas, y los temas propios (`[temas.<nombre>] base`): los avisos de un fondo (las letras que deja
//    mal, solo las que eran suyas; el texto sobre la selección; una línea que no se ve), los colores con transparencia,
//    el nombre de uno nuevo (no pisa uno de fábrica ni uno que hay), la copia de las reglas de su base y la hoja; en la
//    página, uno que llega de la API se puede poner (un mundo lo lleva), está en la grilla de ⚙ temas, en el selector de
//    ⚙ mundos y en la barra de temas del catálogo, se ve en la vista previa mientras se prueba un fondo, vuelve a su base
//    (PATCH con null) o a la de fábrica (DELETE), se crea (PUT) y se borra, y al volver a abrir la página está desde el
//    principio.
// 5. Dónde vive cada tema (en la raíz, `<raiz>/.telar/temas.toml`, para todas las máquinas, o solo esta): lo que dice `GET /temas`
//    llega a web/colores.ts (`donde`, `raiz`), y ⚙ temas lo dice en palabras y al lado de cada color propio.
// Corre en Node: npm run prueba:temas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const dir = mkdtempSync(path.join(tmpdir(), 'temas-'));
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export * as temas from ${JSON.stringify(path.join(src, 'componentes', 'temas.ts'))};`,
    `export * as modos from ${JSON.stringify(path.join(src, 'web', 'modos.ts'))};`,
    `export * as mundo from ${JSON.stringify(path.join(src, 'web', 'mundo.ts'))};`,
    `export * as colores from ${JSON.stringify(path.join(src, 'web', 'colores.ts'))};`,
    `export { vistaPrevia, grillaTemas, razonDe, textoDonde, marcaDonde } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'config', 'temas.ts'))};`,
    `export { selectorTemas } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'config', 'mundos.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'temas.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning',
    loader: { '.css': 'empty' } });

// ── lo justo de la página, sin DOM: el <html> con su data-tema, un almacén que dura entre dos cargas, un reloj que la
// prueba mueve, el setInterval que la prueba dispara y la API ──
const nodo = () => ({ dataset: {}, style: { setProperty() {} }, addEventListener() {}, appendChild() {}, replaceChildren() {},
    append() {}, remove() {}, setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} }, title: '', textContent: '' });
const almacen = new Map();
globalThis.localStorage = { getItem: k => (almacen.has(k) ? almacen.get(k) : null), setItem: (k, v) => almacen.set(k, String(v)),
    removeItem: k => almacen.delete(k) };
let relojes = [];
globalThis.setInterval = f => { relojes.push(f); return relojes.length; };
globalThis.window = { addEventListener() {}, removeEventListener() {} };
/** los elementos con id que la página puso en el documento (la hoja de los colores propios) */
let porId = new Map();
function pagina() {
    porId = new Map();
    const raiz = { ...nodo(), appendChild: el => { if (el.id) porId.set(el.id, el); } };
    globalThis.document = { documentElement: raiz, body: nodo(), createElement: nodo, getElementById: id => porId.get(id) ?? null,
        querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, hidden: false };
    globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
    relojes = [];
}
const RealDate = Date;
let ahora = new RealDate(2026, 10, 18, 18, 0).getTime();   // miércoles 18-nov, 18:00 (la hora de aquí)
globalThis.Date = class extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(ahora); }
    static now() { return ahora; }
};
const a = (dia, h, m = 0) => { ahora = new RealDate(2026, 10, dia, h, m).getTime(); for (const f of relojes) f(); };

// la API: los modos (uno propio con tema) y los mundos (trabajo de 9 a 19 sin tema; personal fuera de horario, con
// brasa). Con `retener`, los mundos no contestan hasta soltarlos (la página recién abierta)
const TACTICA = { barra: 'abierta', lado: 'abierto', cabecera: 'visible', acciones: 'visible', escribir: 'oculta', avisos: 'todos',
    aviso_version: 'visible', tema: 'telar', densidad: 'auto', filas: 'tactica', mundo: '', etiquetas: '' };
const MODOS = { modos: [
    { clave: 'tactica', nombre: 'táctica', base: 'tactica', de_fabrica: true, cambiado: false, valores: TACTICA },
    { clave: 'lectura', nombre: 'lectura', base: 'tactica', de_fabrica: false, cambiado: true, valores: { ...TACTICA, tema: 'papel' } },
], catalogo: [] };
const tramo = { texto: 'lun-vie 9:00-19:00', dias: [1, 2, 3, 4, 5], desde: 540, hasta: 1140 };
let personal = { nombre: 'personal', areas: [], rutas: ['casa/'], etiquetas: [], color: 'magenta', color_propio: '', horario: [], tema: 'brasa' };
const trabajo = { nombre: 'trabajo', areas: [], rutas: ['empresa/'], etiquetas: [], color: 'cian', color_propio: '', horario: [tramo], tema: '' };
const MUNDOS = () => ({ mundos: [trabajo, personal], fuera: 'personal', tintas: [], temas: [], agentes: [] });
let retener = false;
const retenidos = [];
// los colores propios de la configuración (`GET /temas`); PATCH los cambia como lo haría telar.temas.ajustar, PUT crea uno
// propio (`basesApi`: nombre → base) y DELETE quita la tabla (de uno propio, el tema)
let propiosApi = {};
let basesApi = {};
const pedidosTemas = [];
const FABRICA = ['telar', 'latte', 'riso', 'papel', 'brasa', 'rescoldo', 'ambar'];
const TEMAS_API = () => ({ temas: [...FABRICA.map(clave => ({ clave, propios: propiosApi[clave] ?? {}, base: '', de_fabrica: true })),
    ...Object.entries(basesApi).map(([clave, base]) => ({ clave, propios: propiosApi[clave] ?? {}, base, de_fabrica: false }))],
    tintas: ['fg', 'dim', 'amarillo', 'azul', 'violeta', 'verde', 'cian', 'magenta', 'rojo'], fondos: ['bg', 'bg-barra', 'linea', 'sel'] });
const json = c => new Response(JSON.stringify(c), { status: 200, headers: { 'Content-Type': 'application/json' } });
globalThis.fetch = async (url, o = {}) => {
    const u = String(url);
    if (u.startsWith('/api/modos')) return json(MODOS);
    if (u.startsWith('/api/mundos')) return retener ? new Promise(r => retenidos.push(() => r(json(MUNDOS())))) : json(MUNDOS());
    if (u.startsWith('/api/temas')) {
        const tema = decodeURIComponent(u.split('/').pop());
        if (o.method === 'PATCH') {
            const { valores } = JSON.parse(o.body);
            pedidosTemas.push({ tema, valores });
            const nuevo = { ...(propiosApi[tema] ?? {}) };
            for (const [k, v] of Object.entries(valores)) if (v === null) delete nuevo[k]; else nuevo[k] = v;
            propiosApi = { ...propiosApi, [tema]: nuevo };
        }
        if (o.method === 'PUT') {
            const { base } = JSON.parse(o.body);
            pedidosTemas.push({ tema, crear: base });
            basesApi = { ...basesApi, [tema]: basesApi[base] ?? base };
            if (propiosApi[base] && basesApi[base]) propiosApi = { ...propiosApi, [tema]: { ...propiosApi[base] } };
        }
        if (o.method === 'DELETE') {
            pedidosTemas.push({ tema, borrar: true });
            propiosApi = Object.fromEntries(Object.entries(propiosApi).filter(([k]) => k !== tema));
            basesApi = Object.fromEntries(Object.entries(basesApi).filter(([k]) => k !== tema));
        }
        return retener ? new Promise(r => retenidos.push(() => r(json(TEMAS_API())))) : json({ ok: true, ...TEMAS_API() });
    }
    return json({});
};
const pasar = async () => { for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r)); };

pagina();
const P = require(salida);
const { temas: T } = P;

// ── 1. los colores ──
const css = readFileSync(path.join(aqui, '..', 'media', 'css', 'temas.css'), 'utf8');
const tokens = readFileSync(path.join(aqui, '..', 'media', 'css', 'tokens.css'), 'utf8');
/** los colores que un bloque de CSS dice en hexadecimal (`--fg: #…;`) */
const colores = bloque => Object.fromEntries([...bloque.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{3,8})\s*;/g)].map(m => [m[1], m[2]]));
const bloques = { telar: colores(/\[data-tema="telar"\]\s*\{([^}]*)\}/.exec(tokens)[1]) };
for (const m of css.matchAll(/\[data-tema="([\w-]+)"\]\s*\{([^}]*)\}/g)) bloques[m[1]] = { ...bloques.telar, ...colores(m[2]) };

{
    // cada tema, en los tres lugares
    const python = /^TEMAS = \(([^)]*)\)/m.exec(readFileSync(path.join(aqui, '..', '..', 'src', 'telar', 'modos.py'), 'utf8'))[1]
        .split(',').map(x => x.trim().replace(/"/g, '')).filter(Boolean);
    assert.deepEqual(T.TEMAS.map(t => t.clave), python, 'temas.ts y telar.modos.TEMAS dicen los mismos, en el mismo orden');
    assert.deepEqual(Object.keys(bloques).sort(), [...python].sort(), 'cada tema tiene su bloque en el CSS, y ninguno sobra');
    assert.deepEqual(T.TEMAS.filter(t => t.noche).map(t => t.clave), ['brasa', 'rescoldo', 'ambar']);
}

const texto = m => m.contrastes.map(c => `${c.texto}/${c.fondo} ${c.razon.toFixed(2)}`).join(', ');
const de = T.medir(bloques.telar);
for (const t of T.TEMAS) {
    const m = T.medir(bloques[t.clave]);
    // en todos: el texto, sobre su fondo
    for (const c of m.contrastes.filter(x => x.texto === 'fg' && x.fondo !== 'fila activa')) {
        assert.ok(c.razon >= T.MINIMO, `${t.clave}: el texto sobre ${c.fondo} a ${c.razon.toFixed(2)}:1`);
    }
    if (!t.noche) continue;
    const c = bloques[t.clave];
    const rgb = k => T.rgb(c[k]);
    // cada color de texto y cada tinta, sobre cada fondo donde va
    const bajos = m.contrastes.filter(x => x.razon < T.MINIMO);
    assert.deepEqual(bajos, [], `${t.clave}: bajo ${T.MINIMO}:1: ${texto({ contrastes: bajos })}`);
    // las tintas con significado, distintas: más que lo más cercano del de fábrica (el verde y el cian, a 7); el peligro, más
    for (const p of m.pares) {
        const minimo = [p.a, p.b].includes('rojo') ? 11 : 8;
        assert.ok(p.distancia >= minimo, `${t.clave}: ${p.a} y ${p.b} a ${p.distancia.toFixed(1)} (al menos ${minimo})`);
    }
    // el texto tenue se ve tenue, y el texto no se confunde con los títulos (el amarillo)
    assert.ok(T.distancia(rgb('fg'), rgb('dim')) >= 14, `${t.clave}: el tenue, lejos del texto`);
    assert.ok(T.distancia(rgb('fg'), rgb('amarillo')) >= 8, `${t.clave}: los títulos, distintos del texto`);
    // el acento (los enlaces, la fila activa, lo que trabaja) no se confunde con lo tenue, y no es azul: entre lo cálido, un
    // azul (aunque apagado) desentona; es una salvia, un verde gris (su tono en OKLCH, de 140° a 200°, no de 210° a 290°)
    assert.ok(T.distancia(rgb('azul'), rgb('dim')) >= 7, `${t.clave}: el acento, lejos de lo tenue (${T.distancia(rgb('azul'), rgb('dim')).toFixed(1)})`);
    {
        const [, , tono] = T.oklch(rgb('azul'));
        assert.ok(tono >= 140 && tono <= 200, `${t.clave}: el acento, una salvia y no un azul (tono ${tono.toFixed(0)}°)`);
    }
    // con los de fábrica, ninguna tinta que se pueda cambiar tiene un aviso
    for (const e of T.EDITABLES) assert.deepEqual(T.avisos(c, e.tinta), [], `${t.clave}: ${e.tinta} sin avisos de fábrica`);
    // oscuro y cálido: el fondo casi negro; el fondo, las barras y el texto con algo de color, y ese color entre el rojo y
    // el amarillo (su tono en OKLCH, de 20° a 110°: terracota, ámbar), no hacia el azul
    assert.ok(T.luminancia(rgb('bg')) < 0.03, `${t.clave}: oscuro`);
    for (const k of ['bg', 'bg-barra', 'fg', 'dim']) {
        const [, x, y] = T.oklab(rgb(k));
        const tono = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
        assert.ok(Math.hypot(x, y) > 0.005 && tono >= 20 && tono <= 110, `${t.clave}: --${k} tira a ámbar (tono ${tono.toFixed(0)}°)`);
    }
    // poca luz azul: el fondo y el texto (casi toda la pantalla) con menos azul que el de fábrica, y por debajo de un
    // tercio (un gris); el azul y el cian, más apagados que los del de fábrica y dando menos luz azul (su canal azul)
    assert.ok(m.luzAzul.fondo < de.luzAzul.fondo && m.luzAzul.fondo < 0.3, `${t.clave}: luz azul del fondo ${m.luzAzul.fondo.toFixed(2)}`);
    assert.ok(m.luzAzul.texto < de.luzAzul.texto && m.luzAzul.texto < 0.3, `${t.clave}: luz azul del texto ${m.luzAzul.texto.toFixed(2)}`);
    for (const k of ['azul', 'cian']) {
        const croma = x => Math.hypot(T.oklab(x)[1], T.oklab(x)[2]);
        assert.ok(croma(rgb(k)) < croma(T.rgb(bloques.telar[k])), `${t.clave}: --${k} más apagado que en telar`);
        const azul = x => (x[2] <= 0.04045 ? x[2] / 12.92 : ((x[2] + 0.055) / 1.055) ** 2.4);
        assert.ok(azul(rgb(k)) < azul(T.rgb(bloques.telar[k])), `${t.clave}: --${k} con menos luz azul que en telar`);
    }
}
// las cuentas, contra valores conocidos: negro y blanco a 21:1, y un gris a sí mismo a 1
assert.equal(T.contraste([0, 0, 0], [1, 1, 1]).toFixed(1), '21.0');
assert.equal(T.contraste(T.rgb('#777'), T.rgb('#777777')), 1);
assert.deepEqual(T.rgb('rgb(255, 0, 0)'), [1, 0, 0]);
assert.ok(Math.abs(T.luzAzul([1, 1, 1]) - 1 / 3) < 1e-9);

// OKLCH de ida y vuelta, y un color recortado a la gama
for (const h of ['#7dae9a', '#e2d7c7', '#1f1812', '#f4afc4']) assert.equal(T.hex(T.desdeOklch(...T.oklch(T.rgb(h)))), h, `${h} de ida y vuelta`);
assert.equal(T.hex([1.2, -0.1, 0.5]), '#ff0080');

// ── 3a. el color propio de una tinta: la paleta, los avisos y la hoja ──
{
    // las tintas que se pueden cambiar: las mismas de telar.temas.TINTAS (las revisa pruebas/test_temas.py), cada una un
    // texto que se mide
    assert.deepEqual(T.EDITABLES.map(e => e.tinta), ['fg', 'dim', 'amarillo', 'azul', 'violeta', 'verde', 'cian', 'magenta', 'rojo']);
    for (const e of T.EDITABLES) assert.ok(T.TEXTOS.includes(e.tinta) && e.nombre && e.para, e.tinta);
    // la paleta de cada tinta de cada tema: opciones distintas, cada una a 4,5:1 o más sobre el fondo, las barras y la fila
    // activa, y ninguna que se confunda con otra tinta (esas dicen otra cosa: no se ofrecen); en los de la noche, apagadas
    // (terrosas: poco croma), y en brasa, el de partida, al menos cuatro por tinta
    for (const t of T.TEMAS) {
        const c = bloques[t.clave];
        for (const e of T.EDITABLES) {
            const p = T.paleta(c, e.tinta, !!t.noche);
            if (t.clave === 'brasa') assert.ok(p.length >= 4, `brasa/${e.tinta}: ${p.length} opciones`);
            assert.equal(new Set(p.map(o => o.color)).size, p.length, `${t.clave}/${e.tinta}: sin repetidas`);
            for (const o of p) {
                assert.match(o.color, /^#[0-9a-f]{6}$/);
                const con = { ...c, [e.tinta]: o.color };
                const razon = Math.min(...T.medir(con).contrastes.filter(x => x.texto === e.tinta).map(x => x.razon));
                assert.ok(razon >= T.MINIMO, `${t.clave}/${e.tinta}: ${o.nombre} ${o.color} a ${razon.toFixed(2)}:1`);
                assert.deepEqual(T.avisos(con, e.tinta).filter(a => a.tipo === 'parecido'), [], `${t.clave}/${e.tinta}: ${o.nombre} no se confunde`);
                if (t.noche) assert.ok(T.oklch(T.rgb(o.color))[1] <= 0.1, `${t.clave}/${e.tinta}: ${o.nombre} apagado`);
            }
        }
    }
    // con otros colores puestos, la paleta se mide contra ellos: si el verde es casi el rojo, no se ofrece lo que se
    // confunde con ese verde
    assert.ok(T.paleta(bloques.brasa, 'azul', true, { ...bloques.brasa, verde: '#7dae9a' }).every(o => o.nombre !== 'salvia'));
    // los avisos: lo que se lee mal (con su razón), lo que se confunde (con cuál), y lo que el acento le hace a la fila activa
    const brasa = bloques.brasa;
    const oscuro = T.avisos({ ...brasa, azul: '#5b4c40' }, 'azul');
    assert.equal(oscuro[0].tipo, 'contraste');
    assert.ok(oscuro[0].razon < T.MINIMO && /sobre/.test(oscuro[0].texto), oscuro[0].texto);
    assert.deepEqual(T.avisos({ ...brasa, azul: brasa.verde }, 'azul').filter(a => a.tipo === 'parecido').map(a => a.con), ['verde']);
    assert.deepEqual(T.avisos({ ...brasa, dim: '#d8cdbd' }, 'dim').map(a => a.con), ['fg'], 'el tenue, casi el texto');
    assert.ok(T.avisos({ ...brasa, azul: '#f4f0e8' }, 'azul').some(a => /fila activa/.test(a.texto) && /tenue/.test(a.texto)),
        'un acento claro tiñe la fila activa y deja mal lo que va encima');
    // lo que ya se leía mal sobre el fondo no es cosa del acento (el tenue de telar, de fábrica, a 3,7:1)
    assert.ok(!T.avisos(bloques.telar, 'azul').some(a => /deja mal/.test(a.texto)), 'telar: el acento no tiene la culpa');
    // la hoja: un bloque por tema, más específico que el de temas.css; solo tintas conocidas y colores #rrggbb
    assert.equal(T.css({ brasa: { violeta: '#d19fb6', azul: '#7DAE9A' } }),
        '[data-tema="brasa"]:not([data-fabrica]) { --azul: #7dae9a; --violeta: #d19fb6; }', 'en el orden de EDITABLES, en minúsculas');
    assert.equal(T.css({ neon: { azul: '#000000' }, brasa: { naranjo: '#000000', azul: 'rojo' }, telar: {} }), '');
}

// ── 4a. los fondos y las líneas, y los temas propios: las cuentas y la hoja ──
{
    // lo que se puede cambiar: los fondos y después las tintas (las mismas de telar.temas.FONDOS y TINTAS, que revisa
    // pruebas/test_temas.py)
    assert.deepEqual(T.FONDOS.map(e => e.tinta), ['bg', 'bg-barra', 'linea', 'sel']);
    assert.deepEqual(T.COLORES.map(e => e.tinta), [...T.FONDOS, ...T.EDITABLES].map(e => e.tinta));
    assert.ok(T.esFondo('linea') && !T.esFondo('fg'));
    // los colores con transparencia (las líneas y la selección de fábrica, como las da el navegador), puestos sobre el fondo
    assert.deepEqual(T.rgba('color(srgb 0.8 0.84 0.96 / 0.16)'), [0.8, 0.84, 0.96, 0.16]);
    assert.deepEqual(T.rgba('rgba(128, 128, 128, 0.25)').map(x => +x.toFixed(3)), [0.502, 0.502, 0.502, 0.25]);
    assert.deepEqual(T.rgba('rgb(76 79 105 / 14%)')[3], 0.14);
    assert.deepEqual(T.rgba('#ffffff80').map(x => +x.toFixed(2)), [1, 1, 1, 0.5]);
    assert.equal(T.hex(T.opaco('rgba(255, 255, 255, 0.5)', [0, 0, 0])), '#808080');
    assert.equal(T.hex(T.opaco('#1f1812', [1, 1, 1])), '#1f1812', 'lo opaco queda igual');
    // la hoja: los fondos primero, y con un fondo, si es claro u oscuro (las barras de desplazamiento, el selector)
    assert.equal(T.css({ brasa: { azul: '#7dae9a', bg: '#101010' } }),
        '[data-tema="brasa"]:not([data-fabrica]) { --bg: #101010; --azul: #7dae9a; color-scheme: dark; }');
    assert.match(T.css({ brasa: { bg: '#f4efe6' } }), /color-scheme: light;/);
    assert.equal(T.css({ latte: { linea: '#cccccc', sel: '#dddddd', 'bg-barra': '#eeeeee' } }),
        '[data-tema="latte"]:not([data-fabrica]) { --bg-barra: #eeeeee; --linea: #cccccc; --sel: #dddddd; }');

    // los avisos de un fondo: las letras que sobre él se leen mal, con su razón
    const brasa = { ...bloques.brasa, linea: '#3e372f', sel: '#3c352d' };
    const claro = T.avisos({ ...brasa, bg: '#e8dccb' }, 'bg');
    assert.equal(claro.length, 1);
    assert.match(claro[0].texto, /«texto»/);
    assert.ok(claro[0].razon < T.MINIMO);
    assert.match(T.avisos({ ...brasa, 'bg-barra': '#d9cbb8' }, 'bg-barra')[0].texto, /sobre ellas se leen bajo 4,5:1 «texto»/);
    assert.deepEqual(T.avisos(brasa, 'bg'), [], 'el de fábrica, sin avisos');
    // con los de fábrica, solo lo que es suyo: un tenue cambiado que ya se leía mal sobre el fondo de fábrica no es del fondo
    const conTenue = { ...brasa, dim: '#3a3028' };
    assert.deepEqual(T.avisos({ ...conTenue, bg: '#241c16' }, 'bg', brasa), [], 'el tenue es cosa suya');
    assert.ok(T.avisos({ ...conTenue, bg: '#241c16' }, 'bg').some(a => /tenue/.test(a.texto)), 'sin los de fábrica, se dice');
    // la selección: el texto sobre ella; las líneas: si casi no se ven
    assert.match(T.avisos({ ...brasa, sel: '#d8cdbd' }, 'sel')[0].texto, /el texto se lee a .*:1 sobre ella/);
    assert.deepEqual(T.avisos(brasa, 'sel'), []);
    assert.match(T.avisos({ ...brasa, linea: '#1f1812' }, 'linea')[0].texto, /casi no se ve/);
    assert.deepEqual(T.avisos(brasa, 'linea'), []);
    // lo que un fondo le hace a una letra que no se tocó: lo que de fábrica se leía bien y ya no
    assert.equal(T.empeora({ ...brasa, bg: '#8a7a6a' }, brasa, 'dim')[0].tipo, 'contraste');
    assert.deepEqual(T.empeora(bloques.telar, bloques.telar, 'dim'), [], 'el tenue de telar ya era así');
    // lo que mide cada fila de ⚙ temas: una letra, su peor contraste; un fondo, el texto sobre él; las líneas, contra el fondo
    assert.ok(Math.abs(P.razonDe(brasa, 'bg').razon - T.contraste(T.rgb(brasa.fg), T.rgb(brasa.bg))) < 1e-9);
    assert.equal(P.razonDe(brasa, 'linea').minimo, T.LINEA_MINIMA);

    // el nombre de uno nuevo: lo escrito, arreglado; y lo que no sirve
    assert.equal(T.aNombre('  Noche Azul '), 'noche-azul');
    assert.equal(T.aNombre('Ámbar_claro'), 'ambar-claro');
    assert.match(T.problemaNombre(T.aNombre('Ámbar')), /de fábrica/);
    assert.match(T.problemaNombre('telar'), /de fábrica/);
    assert.match(T.problemaNombre('1noche'), /minúsculas/);
    assert.match(T.problemaNombre('a'.repeat(25)), /minúsculas/);
    assert.equal(T.problemaNombre('noche-azul'), '');

    // registrar los propios: valen donde vale uno de fábrica; lo que no es uno, no
    assert.equal(T.registrar([{ clave: 'noche-azul', base: 'brasa' }, { clave: 'brasa', base: 'latte' }, { clave: 'Mal', base: 'latte' },
        { clave: 'huerfano', base: 'neon' }]), true);
    assert.deepEqual(T.todos().map(t => t.clave), [...FABRICA, 'noche-azul']);
    assert.ok(T.existe('noche-azul') && !T.esDeFabrica('noche-azul') && T.baseDe('noche-azul') === 'brasa' && T.de('noche-azul').noche);
    assert.match(T.problemaNombre('noche-azul'), /ya hay/);
    assert.deepEqual(T.queRige({ mundo: 'noche-azul', modo: 'latte' }), { clave: 'noche-azul', por: 'mundo' });
    assert.equal(T.registrar([{ clave: 'noche-azul', base: 'brasa' }]), false, 'lo mismo: nada cambió');
    // las reglas de su base, de las hojas de la página (dentro de una capa también), copiadas con su nombre; una hoja que
    // no se deja leer no importa
    const hojas = [{ get cssRules() { throw new Error('otro origen'); } },
        { cssRules: [{ selectorText: ':root, [data-tema="telar"]', style: { cssText: '--bg: #1e1e2e;' } },
            { cssRules: [{ selectorText: '[data-tema="brasa"]', style: { cssText: 'color-scheme: dark; --bg: #1f1812; --sel: color-mix(in srgb, var(--fg) 15%, transparent);' } }] },
            { selectorText: '[data-tema="brasa"] .algo', style: { cssText: 'color: red;' } }] }];
    assert.deepEqual(T.reglasDe(hojas, 'telar'), ['--bg: #1e1e2e;']);
    assert.equal(T.reglasDe(hojas, 'brasa').length, 1);
    assert.equal(T.css({ 'noche-azul': { bg: '#141820' } }, { reglas: b => T.reglasDe(hojas, b) }),
        '[data-tema="noche-azul"] { color-scheme: dark; --bg: #1f1812; --sel: color-mix(in srgb, var(--fg) 15%, transparent); }\n'
        + '[data-tema="noche-azul"]:not([data-fabrica]) { --bg: #141820; color-scheme: dark; }');
    // sin colores, igual es su base con su nombre; en /componentes (soloPropios), los de fábrica quedan como vienen
    assert.equal(T.css({}, { reglas: () => ['--bg: #1f1812;'] }), '[data-tema="noche-azul"] { --bg: #1f1812; }');
    assert.equal(T.css({ brasa: { azul: '#7dae9a' }, 'noche-azul': { azul: '#88aacc' } }, { reglas: () => [], soloPropios: true }),
        '[data-tema="noche-azul"]:not([data-fabrica]) { --azul: #88aacc; }');

    // los selectores: la grilla de ⚙ temas, el de ⚙ mundos y la barra del catálogo (temas.todos()) lo llevan, pintado con
    // sus colores (data-tema); la vista previa, con su nombre
    const grilla = P.grillaTemas('noche-azul', 'brasa', t => t === 'noche-azul');
    assert.match(grilla, /class="mu-tema si propio" data-tema="noche-azul"/);
    assert.equal((grilla.match(/data-accion="tema-elegir"/g) ?? []).length, FABRICA.length + 1);
    assert.match(P.selectorTemas('personal', 'noche-azul'), /data-valor="personal noche-azul"[^>]*data-tema="noche-azul"/);
    const catalogo = readFileSync(path.join(src, 'componentes', 'catalogo.ts'), 'utf8');
    assert.match(catalogo, /todosLosTemas\(\)\.map\(t => chip\(/, 'la barra de temas del catálogo, con los propios');
    assert.match(catalogo, /colores\.montar\(\{ soloPropios: true \}\)/, 'y el catálogo los lee, sin tocar los de fábrica');
    const previa = P.vistaPrevia('noche-azul');
    assert.match(previa, /^<div class="te-previa" data-tema="noche-azul"/);
    for (const c of ['te-p-barra', 'te-p-fila activa', 'te-p-fila sel', 'var(--violeta)', 'var(--rojo)']) assert.ok(previa.includes(c), c);
    T.registrar([]);
}

// ── la regla: a mano, el mundo, el modo ──
assert.deepEqual(T.queRige({ modo: 'latte' }), { clave: 'latte', por: 'modo' });
assert.deepEqual(T.queRige({ mundo: 'brasa', modo: 'latte' }), { clave: 'brasa', por: 'mundo' });
assert.deepEqual(T.queRige({ aMano: 'riso', mundo: 'brasa', modo: 'latte' }), { clave: 'riso', por: 'a-mano' });
assert.deepEqual(T.queRige({ aMano: 'nada', mundo: 'otro', modo: 'tampoco' }), { clave: 'telar', por: 'modo' }, 'lo que no se conoce no cuenta');

// ── 2. el tema de un mundo, en la página ──
const { modos, mundo } = P;
const tema = () => document.documentElement.dataset.tema;
let avisos = 0;
modos.alCambiar(() => avisos++);
mundo.montar();
modos.montar();
await pasar();

// miércoles 18:00: rige trabajo, sin tema: el del modo
assert.equal(mundo.puesto().mundo, 'trabajo');
assert.equal(tema(), 'telar');
assert.deepEqual(modos.tema(), { clave: 'telar', por: 'modo' });

// 19:01: el horario pone personal, que tiene el suyo, y quien escucha se entera (la terminal toma sus colores)
avisos = 0;
a(18, 19, 1);
assert.equal(mundo.puesto().mundo, 'personal');
assert.equal(tema(), 'brasa');
assert.deepEqual(modos.tema(), { clave: 'brasa', por: 'mundo' });
assert.ok(avisos > 0, 'los que escuchan al modo se enteran de los colores nuevos');
// un minuto después, nada cambia y nadie se entera de nada
avisos = 0;
a(18, 19, 2);
assert.equal(avisos, 0);

// a mano: trabajo, el del modo; ambos, el del modo; volver al horario, el del mundo
mundo.poner('trabajo');
assert.equal(tema(), 'telar');
mundo.poner('');
assert.equal(tema(), 'telar', 'con ambos, el del modo');
mundo.volverAlHorario();
assert.equal(tema(), 'brasa');

// un modo con su tema: en un mundo con tema, el del mundo; en uno sin, el del modo
modos.cambiar('lectura');
assert.equal(tema(), 'brasa');
mundo.poner('trabajo');
assert.equal(tema(), 'papel');
modos.cambiar('tactica');
assert.equal(tema(), 'telar');

// elegido a mano en trabajo (sin tema): vale ahí; al entrar a personal, el del mundo, y lo de a mano se olvida
modos.poner('tema', 'latte');
assert.deepEqual(modos.tema(), { clave: 'latte', por: 'a-mano' });
mundo.volverAlHorario();   // 19:02: personal
assert.equal(tema(), 'brasa');
assert.equal('tema' in modos.cambiosAMano(), false, 'lo de a mano de otro mundo se olvida al entrar a uno con tema');
a(19, 9, 1);               // jueves 9:01: trabajo de nuevo, con el del modo
assert.equal(mundo.puesto().mundo, 'trabajo');
assert.equal(tema(), 'telar');

// elegido a mano en personal: le gana a su tema mientras se esté ahí, aunque sea el mismo del modo
a(19, 20, 0);
assert.equal(tema(), 'brasa');
modos.poner('tema', 'telar');
assert.deepEqual(modos.tema(), { clave: 'telar', por: 'a-mano' });
// y cambiar de modo lo suelta
modos.cambiar('tactica');
assert.equal(tema(), 'brasa');

// ⚙ mundos le cambia el tema: se ve al tiro; sin tema, el del modo
personal = { ...personal, tema: 'ambar' };
mundo.recibirDetalle(MUNDOS());
assert.equal(tema(), 'ambar');
personal = { ...personal, tema: '' };
mundo.recibirDetalle(MUNDOS());
assert.equal(tema(), 'telar');
personal = { ...personal, tema: 'ambar' };
mundo.recibirDetalle(MUNDOS());
assert.equal(tema(), 'ambar');

// al volver a abrir la página (de noche, en personal): mientras los mundos no llegan, el que puso el mundo la última vez,
// y no el del modo: los colores no saltan
retener = true;
pagina();
const otra = path.join(dir, 'temas-de-nuevo.cjs');
writeFileSync(otra, readFileSync(salida));
const Q = require(otra);
Q.mundo.montar();
Q.modos.montar();
await pasar();
assert.equal(Q.mundo.conocidos(), false);
assert.equal(tema(), 'ambar', 'antes de que lleguen los mundos, el de la última vez');
for (const r of retenidos.splice(0)) r();
await pasar();
assert.equal(Q.mundo.conocidos(), true);
assert.equal(Q.mundo.puesto().mundo, 'personal');
assert.equal(tema(), 'ambar');

// y si en ese mundo se había elegido otro a mano, ese, también antes de que lleguen los mundos
Q.modos.poner('tema', 'latte');
assert.equal(tema(), 'latte');
pagina();
const otraMas = path.join(dir, 'temas-otra-vez.cjs');
writeFileSync(otraMas, readFileSync(salida));
const R = require(otraMas);
R.mundo.montar();
R.modos.montar();
await pasar();
assert.equal(R.mundo.conocidos(), false);
assert.equal(tema(), 'latte', 'lo de a mano en el mundo de la última vez');
for (const r of retenidos.splice(0)) r();
await pasar();
assert.equal(tema(), 'latte');

// ── 3b. el color propio de una tinta, en la página (web/colores.ts) ──
{
    const C = R.colores;
    for (const r of retenidos.splice(0)) r();
    retener = false;
    const hoja = () => porId.get('temas-propios')?.textContent ?? '';
    let oidos = 0;
    R.modos.alCambiar(() => oidos++);
    // llegan de la API: la hoja los pone, este navegador los guarda, y quien escucha al modo (la terminal) se entera
    propiosApi = { brasa: { azul: '#9aa982' } };
    await C.leer();
    assert.equal(hoja(), '[data-tema="brasa"]:not([data-fabrica]) { --azul: #9aa982; }');
    assert.deepEqual(JSON.parse(almacen.get('telar.temas.propios')), { brasa: { azul: '#9aa982' } });
    assert.ok(oidos > 0, 'la terminal toma los colores nuevos');
    // lo mismo otra vez: nada cambia y nadie se entera
    oidos = 0;
    await C.leer();
    assert.equal(oidos, 0);
    // probar: solo en esta página, sin escribir; soltarlo vuelve a lo de la configuración
    C.probar('brasa', 'violeta', '#d19fb6');
    assert.match(hoja(), /--violeta: #d19fb6;/);
    assert.deepEqual(C.de('brasa'), { azul: '#9aa982' }, 'probar no escribe');
    assert.equal(pedidosTemas.length, 0);
    assert.ok(oidos > 0);
    C.probar('brasa', 'violeta', undefined);
    assert.equal(hoja(), '[data-tema="brasa"]:not([data-fabrica]) { --azul: #9aa982; }');
    // escribir: un PATCH con solo esa tinta; lo que se probaba se suelta y queda lo que devuelve la API
    C.probar('brasa', 'amarillo', '#e5b96a');
    assert.equal(await C.ajustar('brasa', { violeta: '#d19fb6' }), '');
    assert.deepEqual(pedidosTemas.at(-1), { tema: 'brasa', valores: { violeta: '#d19fb6' } });
    assert.deepEqual(C.de('brasa'), { azul: '#9aa982', violeta: '#d19fb6' });
    assert.doesNotMatch(hoja(), /amarillo/, 'lo que se probaba se suelta');
    // volver a la de fábrica: null
    await C.ajustar('brasa', { azul: null });
    assert.equal(hoja(), '[data-tema="brasa"]:not([data-fabrica]) { --violeta: #d19fb6; }');
    // al volver a abrir la página, los de la última vez desde el principio, antes de que conteste la API
    retener = true;
    pagina();
    const otraVez = path.join(dir, 'temas-colores.cjs');
    writeFileSync(otraVez, readFileSync(salida));
    const S = require(otraVez);
    S.mundo.montar();
    S.modos.montar();
    assert.equal(hoja(), '[data-tema="brasa"]:not([data-fabrica]) { --violeta: #d19fb6; }', 'sin esperar a la API');
    propiosApi = {};
    for (const r of retenidos.splice(0)) r();
    await pasar();
    assert.equal(hoja(), '', 'y lo que diga la API, cuando llega');
    retener = false;
}

// ── 4b. los temas propios en la página: llegan, se ponen, se prueban, vuelven a su base, se crean y se borran ──
{
    // otro navegador: nada elegido a mano, nada guardado
    almacen.clear();
    pagina();
    // las hojas de la página, con las reglas de los temas de fábrica: de ahí se copia la base de uno propio
    document.styleSheets = [{ cssRules: [
        { selectorText: ':root, [data-tema="telar"]', style: { cssText: '--bg: #1e1e2e; --fg: #cdd6f4;' } },
        { selectorText: '[data-tema="brasa"]', style: { cssText: 'color-scheme: dark; --bg: #1f1812; --fg: #e2d7c7;' } }] }];
    const otra = path.join(dir, 'temas-propios.cjs');
    writeFileSync(otra, readFileSync(salida));
    const U = require(otra);
    const C = U.colores;
    const hoja = () => porId.get('temas-propios')?.textContent ?? '';
    // personal (el mundo de la noche) lleva uno propio que todavía no existe: hasta que llegue, el del modo
    personal = { ...personal, tema: 'noche-azul' };
    propiosApi = {};
    basesApi = {};
    U.mundo.montar();
    U.modos.montar();
    await pasar();
    assert.equal(U.mundo.puesto().mundo, 'personal');
    assert.equal(tema(), 'telar', 'uno que no se conoce no cuenta');
    let oidos = 0;
    U.modos.alCambiar(() => oidos++);
    // se crea (PUT con su base): está en la lista, su hoja es la de brasa con su nombre, y el mundo lo pone al tiro
    assert.equal(await C.crear('noche-azul', 'brasa'), '');
    assert.deepEqual(pedidosTemas.at(-1), { tema: 'noche-azul', crear: 'brasa' });
    assert.ok(U.temas.existe('noche-azul'));
    assert.equal(hoja(), '[data-tema="noche-azul"] { color-scheme: dark; --bg: #1f1812; --fg: #e2d7c7; }');
    assert.equal(tema(), 'noche-azul', 'el mundo que lo llevaba lo pone apenas existe');
    assert.ok(oidos > 0, 'la terminal toma sus colores');
    assert.deepEqual(JSON.parse(almacen.get('telar.temas.bases')), { 'noche-azul': 'brasa' });
    // sus colores, como los de uno de fábrica
    assert.equal(await C.ajustar('noche-azul', { bg: '#141820', linea: '#2a3446' }), '');
    assert.match(hoja(), /\[data-tema="noche-azul"\]:not\(\[data-fabrica\]\) \{ --bg: #141820; --linea: #2a3446; color-scheme: dark; \}/);
    // la vista previa en vivo: probar un fondo lo pone en la hoja sin escribirlo; soltarlo, vuelve
    const antes = pedidosTemas.length;
    C.probar('noche-azul', 'bg', '#000000');
    assert.match(hoja(), /--bg: #000000;/);
    C.probar('noche-azul', 'sel', '#203040');
    assert.match(hoja(), /--sel: #203040;/);
    assert.equal(pedidosTemas.length, antes, 'probar no escribe');
    C.soltar();
    assert.match(hoja(), /--bg: #141820;/);
    assert.doesNotMatch(hoja(), /--sel/);
    // otro propio que parte de este: con su base (brasa) y sus colores
    assert.equal(await C.crear('noche-mas', 'noche-azul'), '');
    assert.deepEqual(C.de('noche-mas'), { bg: '#141820', linea: '#2a3446' });
    assert.equal(U.temas.baseDe('noche-mas'), 'brasa');
    assert.deepEqual(U.temas.todos().slice(-2).map(t => t.clave), ['noche-azul', 'noche-mas']);
    // todo de fábrica: de uno propio, sus colores en null (PATCH; el tema queda, igual a su base); de uno de fábrica, DELETE
    assert.equal(await C.deFabrica('noche-azul'), '');
    assert.deepEqual(pedidosTemas.at(-1), { tema: 'noche-azul', valores: { bg: null, linea: null } });
    assert.ok(U.temas.existe('noche-azul'));
    assert.doesNotMatch(hoja(), /noche-azul"\]:not/);
    propiosApi = { ...propiosApi, brasa: { azul: '#9aa982' } };
    await C.leer();
    assert.equal(await C.deFabrica('brasa'), '');
    assert.deepEqual(pedidosTemas.at(-1), { tema: 'brasa', borrar: true });
    assert.deepEqual(C.de('brasa'), {});
    // al volver a abrir la página, el propio está desde el principio (su base, guardada en el navegador): los colores no
    // saltan al del modo mientras la API no contesta
    retener = true;
    pagina();
    document.styleSheets = [{ cssRules: [{ selectorText: '[data-tema="brasa"]', style: { cssText: '--bg: #1f1812;' } }] }];
    const otraVez = path.join(dir, 'temas-propios-de-nuevo.cjs');
    writeFileSync(otraVez, readFileSync(salida));
    const V = require(otraVez);
    V.mundo.montar();
    V.modos.montar();
    assert.equal(tema(), 'noche-azul', 'sin esperar a la API');
    assert.match(hoja(), /\[data-tema="noche-azul"\] \{ --bg: #1f1812; \}/);
    for (const r of retenidos.splice(0)) r();
    await pasar();
    retener = false;
    // borrarlo (DELETE): deja de existir, y el mundo que lo llevaba vuelve al del modo
    assert.equal(await V.colores.borrar('noche-azul'), '');
    assert.deepEqual(pedidosTemas.at(-1), { tema: 'noche-azul', borrar: true });
    assert.ok(!V.temas.existe('noche-azul'));
    assert.equal(tema(), 'telar');
    assert.doesNotMatch(hoja(), /noche-azul/);
    personal = { ...personal, tema: 'ambar' };
}

// ── 5. dónde vive cada tema ──
{
    const { colores: C } = P;
    C.recibir({ temas: [
        { clave: 'brasa', propios: { azul: '#7dae9a', violeta: '#cc99aa' }, base: '', de_fabrica: true, vive: 'mixto', en_raiz: ['violeta'], en_maquina: ['azul'] },
        { clave: 'latte', propios: {}, base: '', de_fabrica: true, vive: '' },
        { clave: 'mio', propios: { bg: '#fafafa' }, base: 'latte', de_fabrica: false, vive: 'maquina', en_raiz: [], en_maquina: ['bg'] },
    ], raiz: '/home/ana/casa/.telar/temas.toml' });
    assert.equal(C.raiz(), '/home/ana/casa/.telar/temas.toml');
    assert.deepEqual(C.donde('brasa'), { vive: 'mixto', enRaiz: ['violeta'], enMaquina: ['azul'] });
    assert.deepEqual(C.donde('latte'), { vive: '', enRaiz: [], enMaquina: [] });
    const brasa = P.textoDonde(C.donde('brasa'), C.raiz(), 'brasa');
    assert.match(brasa, /^lo que cambias queda en casa y vale en todas las máquinas/);
    assert.match(brasa, /solo en esta máquina: acento \(pisa lo de casa; cambiarlo lo lleva a casa\)/);
    assert.match(P.textoDonde(C.donde('mio'), C.raiz(), 'mio'), /hoy está solo en esta máquina: al cambiarlo pasa a casa/);
    assert.equal(P.textoDonde(C.donde('latte'), C.raiz(), 'latte'), 'lo que cambias queda en casa y vale en todas las máquinas');
    assert.match(P.marcaDonde(C.donde('brasa'), C.raiz(), 'azul'), /class="te-donde solo"[^>]*>solo aquí</);
    assert.match(P.marcaDonde(C.donde('brasa'), C.raiz(), 'violeta'), /class="te-donde"[^>]*>en casa</);
    // sin raíz: todo en la máquina, como antes, y ninguna marca
    C.recibir({ temas: [{ clave: 'brasa', propios: { azul: '#7dae9a' }, base: '', de_fabrica: true, vive: 'maquina', en_raiz: [], en_maquina: ['azul'] }] });
    assert.equal(C.raiz(), '');
    assert.equal(P.textoDonde(C.donde('brasa'), C.raiz(), 'brasa'), 'lo que cambias queda en [temas.brasa] de esta máquina');
    assert.equal(P.marcaDonde(C.donde('brasa'), C.raiz(), 'azul'), '');
}

console.log('prueba:temas ok');
