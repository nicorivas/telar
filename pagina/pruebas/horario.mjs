// Prueba del horario de los mundos (⚙ mundos › horario): src/componentes/horario-editor.ts (cómo se escribe un tramo, la
// semana partida en pedazos, los choques y los huecos, lo que se revisa antes de guardar y el HTML de la vista previa y
// del editor) y la parte de src/vistas/dashboard/config/mundos.ts que lo usa, con un DOM, un reloj y una API de mentira:
// un clic en un día o un cambio de hora va al borrador y se ve al tiro en la semana; un choque se dice y no deja guardar;
// guardar manda solo el horario, como textos que el servidor lee igual, y la banda cambia al tiro si cambia el mundo que
// rige; un 422 del servidor se dice y el borrador queda; deshacer vuelve a lo guardado.
// Corre en Node: npm run prueba:horario
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(aqui, '..', 'src');
const dir = mkdtempSync(path.join(tmpdir(), 'horario-'));
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export * as hs from ${JSON.stringify(path.join(src, 'componentes', 'horario-editor.ts'))};`,
    `export { leerTramo } from ${JSON.stringify(path.join(src, 'componentes', 'modos-mundos.ts'))};`,
    `export * as mundo from ${JSON.stringify(path.join(src, 'web', 'mundo.ts'))};`,
    `export { mundosSeccion } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'config', 'mundos.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'horario.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning',
    loader: { '.css': 'empty' } });

// ── lo justo de la página: los avisos que se dicen, los <select> de lo último que se dibujó, un reloj y la API ──
const dichos = [];
const nodo = () => ({ dataset: {}, style: { setProperty() {} }, addEventListener() {}, appendChild: c => dichos.push(c.textContent),
    replaceChildren() {}, append() {}, remove() {}, setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} },
    title: '', textContent: '', isConnected: true });
let dibujado = '';
let selects = [];
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.setInterval = () => 0;
globalThis.window = { addEventListener() {}, removeEventListener() {} };
globalThis.document = { documentElement: nodo(), body: nodo(), getElementById: () => null, querySelector: () => null,
    createElement: () => { const n = nodo(); return n; }, addEventListener() {}, hidden: false,
    querySelectorAll: sel => (sel === 'select[data-horario]' ? selects : []) };
globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
const RealDate = Date;
let ahora = new RealDate(2026, 10, 23, 18, 30).getTime();   // lunes 23-nov, 18:30
globalThis.Date = class extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(ahora); }
    static now() { return ahora; }
};
const tramo = (texto, dias, desde, hasta) => ({ texto, dias, desde, hasta });
let trabajo = { nombre: 'trabajo', areas: [], rutas: ['empresa/'], etiquetas: [], color: 'cian', color_propio: '', tema: '', modos: [],
    horario: [tramo('lun-vie 9:00-19:00', [1, 2, 3, 4, 5], 540, 1140)], horario_vive: 'raiz' };
let personal = { nombre: 'personal', areas: [], rutas: ['casa/'], etiquetas: [], color: 'magenta', color_propio: '', tema: '', modos: [],
    horario: [], horario_vive: '' };
const MUNDOS = () => ({ mundos: [trabajo, personal], fuera: 'personal', fuera_vive: 'raiz', raiz: '/home/ana/casa/.telar/mundos.toml',
    tintas: ['cian', 'magenta'], temas: [], agentes: [], choques: [] });
const json = (c, status = 200) => new Response(JSON.stringify(c), { status, headers: { 'Content-Type': 'application/json' } });
const pedidos = [];
let respuesta = null;   // lo que contesta el próximo PATCH (null: escribirlo y devolver lo de siempre)
globalThis.fetch = async (url, o = {}) => {
    const u = String(url);
    if (o.method === 'PATCH' && u.startsWith('/api/mundos/')) {
        const cuerpo = JSON.parse(o.body);
        pedidos.push([u, cuerpo]);
        if (respuesta) { const r = respuesta; respuesta = null; return json(r.cuerpo, r.status); }
        const { leerTramo } = P;
        const h = cuerpo.valores.horario;
        const m = u.endsWith('/trabajo') ? trabajo : personal;
        m.horario = (h === null ? [] : h).map(t => ({ texto: t, ...leerTramo(t) }));
        m.horario_vive = h === null ? '' : 'raiz';
        return json({ ok: true, ...MUNDOS() });
    }
    if (u.startsWith('/api/mundos')) return json(MUNDOS());
    return json({});
};
const pasar = async () => { for (let i = 0; i < 8; i++) await new Promise(r => setImmediate(r)); };

const P = require(salida);
const { hs, mundo } = P;

// ── 1. las cuentas, sin página ──
{
    const t = (dias, desde, hasta) => ({ dias, desde, hasta });
    // cómo se escribe un tramo: y se lee igual
    const casos = [[t([1, 2, 3, 4, 5], 540, 1140), 'lun-vie 9:00-19:00'], [t([0, 6], 0, 1440), 'sáb-dom'],
        [t([1, 3, 5], 510, 720), 'lun,mié,vie 8:30-12:00'], [t([0, 1, 2, 3, 4, 5, 6], 1200, 1380), '20:00-23:00'],
        [t([0, 1, 2, 3, 4, 5, 6], 0, 1440), 'todos'], [t([5], 1320, 120), 'vie 22:00-2:00'], [t([0, 1, 6], 0, 1440), 'lun,sáb-dom'],
        [t([1, 2], 540, 1440), 'lun-mar 9:00-24:00']];
    for (const [tr, texto] of casos) {
        assert.equal(hs.escribirTramo(tr), texto);
        const leido = P.leerTramo(texto);
        assert.deepEqual([leido.dias, leido.desde, leido.hasta], [[...tr.dias].sort(), tr.desde, tr.hasta], `«${texto}» se lee igual`);
    }
    assert.deepEqual(hs.alternarDia(t([1, 2], 0, 60), 0).dias, [0, 1, 2]);
    assert.deepEqual(hs.alternarDia(t([1, 2], 0, 60), 1).dias, [2]);
    assert.equal(hs.problemaTramo(t([], 0, 60)), 'elige al menos un día');
    assert.equal(hs.problemaTramo(t([1], 60, 60)), 'empieza y termina a la misma hora');
    assert.deepEqual(hs.tramoNuevo([]), t([1, 2, 3, 4, 5], 540, 1080), 'el primero: de lunes a viernes, de 9 a 18');
    assert.deepEqual(hs.tramoNuevo([t([1, 2], 540, 780)]), t([1, 2], 780, 840), 'otro: lo que sigue al último');

    // la semana: el lunes, hueco, trabajo, choque, estudio, hueco; el domingo sigue la noche del sábado
    const H = [{ clave: 'trabajo', tramos: [t([1, 2, 3, 4, 5], 540, 1140)] }, { clave: 'estudio', tramos: [t([1], 1080, 1260)] },
        { clave: 'fiesta', tramos: [t([6], 1320, 120)] }];
    const lunes = hs.semana(H)[1].map(p => [p.desde, p.hasta, p.mundos.join('+')]);
    assert.deepEqual(lunes, [[0, 540, ''], [540, 1080, 'trabajo'], [1080, 1140, 'trabajo+estudio'], [1140, 1260, 'estudio'], [1260, 1440, '']]);
    assert.deepEqual(hs.semana(H)[0][0], { desde: 0, hasta: 120, mundos: ['fiesta'] }, 'la medianoche del sábado sigue el domingo');
    // los choques, como los cuenta y los dice el servidor (telar.horario.choques y decir_choque)
    assert.deepEqual(hs.choques(H), [{ mundos: ['trabajo', 'estudio'], dia: 1, desde: 1080, hasta: 1140 }]);
    assert.equal(hs.decirChoque(hs.choques(H)[0]), '«trabajo» y «estudio» se pisan el lunes de 18:00 a 19:00');
    assert.deepEqual(hs.choques([{ clave: 'a', tramos: [t([1], 540, 780), t([1], 720, 900)] }]), [], 'los de un mismo mundo no chocan');
    assert.equal(hs.horasDeHueco([H[0]]), 7 * 24 - 50);

    // revisar: lo que se escribe, o por qué no
    assert.deepEqual(hs.revisar('trabajo', [t([1, 2, 3, 4, 5], 540, 780), t([1, 2, 3, 4, 5], 840, 1140)], []),
        { textos: ['lun-vie 9:00-13:00', 'lun-vie 14:00-19:00'], error: '' });
    assert.match(hs.revisar('x', [t([1], 0, 60), t([], 0, 60)], []).error, /^el tramo 2: elige al menos un día/);
    assert.match(hs.revisar('estudio', H[1].tramos, H).error, /^«estudio» y «trabajo» se pisan el lunes de 18:00 a 19:00/);
    assert.deepEqual(hs.juntarChoques([{ mundos: ['a', 'b'], dia: 1, desde: 0, hasta: 60 }, { mundos: ['a', 'b'], dia: 2, desde: 0, hasta: 60 },
        { mundos: ['a', 'b'], dia: 3, desde: 0, hasta: 30 }]).map(hs.decirChoques),
    ['«a» y «b» se pisan los lun-mar de 0:00 a 1:00', '«a» y «b» se pisan el miércoles de 0:00 a 0:30']);
    assert.deepEqual(hs.revisar('trabajo', [], H).textos, [], 'vacío: sin horario');
    assert.ok(hs.iguales([t([2, 1], 0, 60)], [t([1, 2], 0, 60)]));

    // el HTML: la semana en orden de lunes a domingo, el choque rayado, el hueco en la tinta de fuera, la hora de ahora
    const M = [{ clave: 'trabajo', nombre: 'trabajo', color: 'cian' }, { clave: 'estudio', nombre: 'estudio', color: 'verde' },
        { clave: 'personal', nombre: 'personal', color: 'magenta' }];
    const html = hs.htmlSemana(H.slice(0, 2), M, 'personal', new Date());
    assert.deepEqual([...html.matchAll(/class="hs-nombre">([^<]*)</g)].map(x => x[1]).slice(0, 7), ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']);
    assert.match(html, /hs-choque" style="left: 75\.0000%; width: 4\.1667%"/);
    assert.match(html, /hs-hueco" style="left: 0\.0000%; width: 37\.5000%; --mundo-c: var\(--magenta\)"/);
    assert.match(html, /class="hs-dia hoy">.*?hs-ahora" style="left: 77\.0833%"/, 'lunes 18:30');
    assert.match(html, /se pisan: no rige ninguno/);
    const editor = hs.htmlEditor(M[0], [t([1, 2, 3, 4, 5], 540, 1140)], { cambiado: false, textos: ['lun-vie 9:00-19:00'], error: '', vive: 'en casa' });
    assert.equal([...editor.matchAll(/hs-dia-op si/g)].length, 5);
    assert.match(editor, /<select data-horario="trabajo 0 desde"[^>]*>.*<option value="540" selected>9:00<\/option>/);
    assert.match(editor, /<button type="button" class="boton tono-accion"[^>]*data-accion="horario-guardar"[^>]*disabled>/, 'nada cambió: guardar apagado');
    assert.match(editor, /guardado · en casa/);
    const roto = hs.htmlEditor(M[0], [t([], 540, 1140)], { cambiado: true, textos: [], error: 'elige al menos un día' });
    assert.match(roto, /hs-error.*elige al menos un día/);
    assert.match(roto, /data-accion="horario-guardar"[^>]*disabled/, 'con un problema: guardar apagado');
    // una hora que no cae en el paso (escrita a mano) no se pierde
    assert.match(hs.htmlEditor(M[0], [t([1], 490, 1140)], { cambiado: false, textos: [], error: '' }), /<option value="490" selected>8:10/);
}

// ── 2. en la página: ⚙ mundos › horario ──
const ctx = {
    pintar: h => {
        dibujado = h.join('');
        // los <select> de lo dibujado: la sección les ata el cambio
        selects = [...dibujado.matchAll(/<select data-horario="([^"]+)"/g)].map(x => {
            const s = { dataset: { horario: x[1] }, value: '', oyentes: [], addEventListener(t, f) { if (t === 'change') s.oyentes.push(f); } };
            return s;
        });
    },
    parcial() {}, teclas: new Map(), seVe: () => true, paginas: {}, config: () => undefined, releerConfig: async () => {},
    dashboard: { dia: () => undefined, actualizar: async () => {}, pestanas: () => [], orden: () => ({ orden: [], ocultas: [] }), usarOrden() {} },
};
mundo.montar();
await pasar();
assert.equal(mundo.puesto().mundo, 'trabajo', 'lunes 18:30: trabajo');
const seccion = P.mundosSeccion(ctx);
await seccion.abrir();
await pasar();
const franja = dia => dibujado.split('class="hs-dia').find(x => x.includes(`hs-nombre">${dia}<`));
const elegir = async (horario, valor) => {
    const s = selects.find(x => x.dataset.horario === horario);
    assert.ok(s, `hay un <select> ${horario}`);
    s.value = String(valor);
    for (const f of s.oyentes) f();
    await pasar();
};
assert.match(dibujado, /<h2>horario/);
assert.match(franja('lun'), /hs-mundo" style="left: 37\.5000%; width: 41\.6667%; --mundo-c: var\(--cian\)"/, 'trabajo, de 9 a 19');
assert.match(dibujado, /fuera de todo horario.*mundo-nombre/);
assert.doesNotMatch(dibujado, /data-accion="mundo-ajuste" data-valor="trabajo horario"/, 'el horario ya no se edita como texto en ajustes');

// un clic en el sábado: va al borrador, se ve al tiro en la semana, y guardar se prende
await seccion.accion('horario-dia', 'trabajo 0 6');
assert.match(franja('sáb'), /hs-mundo" style="left: 37\.5000%/, 'el sábado, en la vista previa');
assert.match(dibujado, /se escribe <code>horario = &quot;lun-sáb 9:00-19:00&quot;<\/code>/);
assert.doesNotMatch(dibujado.split('data-mundo="trabajo"')[1].split('hs-editor')[0], /data-accion="horario-guardar"[^>]*disabled/);
assert.equal(pedidos.length, 0, 'nada se manda todavía');
// otra vez: vuelve a lo guardado, y deja de ser borrador
await seccion.accion('horario-dia', 'trabajo 0 6');
assert.match(dibujado, /guardado · en casa: vale en todas las máquinas/);

// personal, de lunes a viernes de 18 a 22: choca con trabajo de 18 a 19; se dice en la semana y en su pie, y no se guarda
await seccion.accion('horario-tramo', 'personal');
await elegir('personal 0 desde', 1080);
await elegir('personal 0 hasta', 1320);
assert.match(franja('lun'), /hs-choque" style="left: 75\.0000%; width: 4\.1667%"/);
assert.match(dibujado, /«trabajo» y «personal» se pisan los lun-vie de 18:00 a 19:00: a esa hora rige personal/, 'los días, juntos');
const piePersonal = () => dibujado.split('data-mundo="personal"')[1];
assert.match(piePersonal(), /hs-error.*«personal» y «trabajo» se pisan los lun-vie de 18:00 a 19:00/);
assert.match(piePersonal(), /data-accion="horario-guardar"[^>]*disabled/);
await seccion.accion('horario-guardar', 'personal');
assert.equal(pedidos.length, 0, 'un choque no se manda');

// de 19 a 22 ya no choca: guardar manda solo el horario, como texto, y la banda pasa a personal (lunes 18:30 → 19:30)
await elegir('personal 0 desde', 1140);
assert.doesNotMatch(piePersonal(), /hs-error/);
ahora = new RealDate(2026, 10, 23, 19, 30).getTime();
await seccion.accion('horario-guardar', 'personal');
await pasar();
assert.deepEqual(pedidos.at(-1), ['/api/mundos/personal', { valores: { horario: ['lun-vie 19:00-22:00'] } }]);
assert.equal(mundo.puesto().mundo, 'personal', 'la banda cambia al tiro: rige personal por su horario');
assert.equal(mundo.puesto().por, 'horario');
assert.match(piePersonal(), /guardado · en casa/, 'ya no es borrador');
assert.ok(dichos.some(d => /horario de personal guardado en casa: ahora rige personal/.test(d)), dichos.join(' | '));

// un 422 del servidor (otro cambió el archivo entretanto): se dice, y el borrador queda
await seccion.accion('horario-quitar', 'trabajo 0');
assert.match(dibujado.split('data-mundo="trabajo"')[1], /se escribe <code>sin horario<\/code>/);
respuesta = { status: 422, cuerpo: { detail: 'mundos.trabajo.horario: «trabajo» y «estudio» se pisan el sábado de 9:00 a 10:00' } };
await seccion.accion('horario-guardar', 'trabajo');
await pasar();
assert.ok(dichos.some(d => /no se guardó: .*se pisan el sábado/.test(d)), dichos.join(' | '));
assert.match(dibujado.split('data-mundo="trabajo"')[1], /se escribe <code>sin horario<\/code>/, 'el borrador sigue');
// deshacer: vuelve a lo guardado
await seccion.accion('horario-deshacer', 'trabajo');
assert.match(dibujado.split('data-mundo="trabajo"')[1], /guardado/);
assert.match(franja('lun'), /--mundo-c: var\(--cian\)/);

console.log('prueba:horario ok');
process.exit(0);
