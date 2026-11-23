// Prueba de los modos de cada mundo (`[mundos.<n>] modos`): src/componentes/modos-mundos.ts (`modosDelMundo`,
// `modoAlEntrar`, la banda con `solo`), src/web/modos.ts con src/web/mundo.ts, y lo que deja un clic en la fila «modos»
// de ⚙ mundos (src/vistas/dashboard/config/mundos.ts, `alternarModo`).
//
// 1. Las cuentas: qué modos tiene el mundo puesto (el suyo, todos sin declarar, la unión con ambos), a cuál se entra, y la
//    banda solo con esos (y el puesto, siempre).
// 2. En la página, con un reloj y una API de mentira (trabajo de 9 a 19 con todos; personal fuera de horario, con todo y
//    foco): al entrar a personal desde táctica, todo; al volver a trabajo, táctica de nuevo; lo que la persona eligió en
//    un mundo y el otro también tiene, se queda; las teclas y el siguiente no ponen lo que el mundo no tiene; ⌥⇧F, nada en
//    un mundo sin foco; ⚙ mundos le quita al mundo el modo puesto y la página pasa al primero; al abrir la página en
//    personal, el de su lista; ambos, la unión.
// 3. Lo que deja un clic en la fila «modos» de ⚙ mundos: agregar al final, quitar, nunca ninguno, todos es no declararlos.
// 4. Las pestañas de un modo (la fila «pestañas» de ⚙ modos, `guardarFilas`): en el puesto se ven al tiro, sin esperar a la
//    API y por encima de un cambio a mano; se manda solo esa línea, y null la quita (vuelve a lo de fábrica).
// Corre en Node: npm run prueba:modos-mundo
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
const dir = mkdtempSync(path.join(tmpdir(), 'modos-mundo-'));
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export * as mm from ${JSON.stringify(path.join(src, 'componentes', 'modos-mundos.ts'))};`,
    `export * as modos from ${JSON.stringify(path.join(src, 'web', 'modos.ts'))};`,
    `export * as mundo from ${JSON.stringify(path.join(src, 'web', 'mundo.ts'))};`,
    `export { alternarModo, decirModos } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'config', 'mundos.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'modos-mundo.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning',
    loader: { '.css': 'empty' } });

// ── lo justo de la página, sin DOM (como en temas.mjs): un almacén que dura entre dos cargas, un reloj que la prueba
// mueve, las teclas que la prueba aprieta y la API ──
const nodo = () => ({ dataset: {}, style: { setProperty() {} }, addEventListener() {}, appendChild() {}, replaceChildren() {},
    append() {}, remove() {}, setAttribute() {}, classList: { add() {}, remove() {}, toggle() {} }, title: '', textContent: '' });
const almacen = new Map();
globalThis.localStorage = { getItem: k => (almacen.has(k) ? almacen.get(k) : null), setItem: (k, v) => almacen.set(k, String(v)),
    removeItem: k => almacen.delete(k) };
let relojes = [];
let teclas = [];
globalThis.setInterval = f => { relojes.push(f); return relojes.length; };
function pagina() {
    globalThis.window = { addEventListener: (t, f) => { if (t === 'keydown') teclas.push(f); }, removeEventListener() {} };
    globalThis.document = { documentElement: nodo(), body: nodo(), createElement: nodo, getElementById: () => null,
        querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, hidden: false };
    globalThis.getComputedStyle = () => ({ getPropertyValue: () => '' });
    relojes = [];
    teclas = [];
}
const RealDate = Date;
let ahora = new RealDate(2026, 10, 18, 18, 0).getTime();   // miércoles 18-nov, 18:00
globalThis.Date = class extends RealDate {
    constructor(...a) { if (a.length) super(...a); else super(ahora); }
    static now() { return ahora; }
};
const a = (dia, h, m = 0) => { ahora = new RealDate(2026, 10, dia, h, m).getTime(); for (const f of relojes) f(); };
const tecla = code => { for (const f of teclas) f({ altKey: true, shiftKey: true, metaKey: false, ctrlKey: false, code, preventDefault() {}, stopPropagation() {} }); };

const TACTICA = { barra: 'abierta', lado: 'abierto', cabecera: 'visible', acciones: 'visible', escribir: 'oculta', avisos: 'todos',
    aviso_version: 'visible', tema: 'telar', densidad: 'auto', filas: 'tactica', mundo: '', etiquetas: '' };
const modo = (clave, nombre, base, de_fabrica = true, valores = {}) => ({ clave, nombre, base, de_fabrica, cambiado: !de_fabrica, valores: { ...TACTICA, ...valores } });
const MODOS = { modos: [modo('tactica', 'táctica', 'tactica'), modo('estrategia', 'estrategia', 'estrategia'),
    modo('foco', 'foco', 'foco', true, { barra: 'oculta' }), modo('todo', 'todo', 'todo', true, { filas: '*' }),
    modo('lectura', 'lectura', 'foco', false)], catalogo: [] };
const tramo = { texto: 'lun-vie 9:00-19:00', dias: [1, 2, 3, 4, 5], desde: 540, hasta: 1140 };
let personal = { nombre: 'personal', areas: [], rutas: ['casa/'], etiquetas: [], color: 'magenta', color_propio: '', horario: [], tema: '', modos: ['todo', 'foco'] };
let trabajo = { nombre: 'trabajo', areas: [], rutas: ['empresa/'], etiquetas: [], color: 'cian', color_propio: '', horario: [tramo], tema: '', modos: [] };
const MUNDOS = () => ({ mundos: [trabajo, personal], fuera: 'personal', tintas: [], temas: [], agentes: [] });
const json = c => new Response(JSON.stringify(c), { status: 200, headers: { 'Content-Type': 'application/json' } });
globalThis.fetch = async url => {
    const u = String(url);
    if (u.startsWith('/api/modos')) return json(MODOS);
    if (u.startsWith('/api/mundos')) return json(MUNDOS());
    return json({});
};
const pasar = async () => { for (let i = 0; i < 5; i++) await new Promise(r => setImmediate(r)); };

pagina();
const P = require(salida);
const { mm } = P;

// ── 1. las cuentas ──
{
    const M = [{ clave: 'trabajo', modos: [] }, { clave: 'personal', modos: ['todo', 'foco'] }, { clave: 'estudio', modos: ['foco', 'lectura'] }];
    assert.equal(mm.modosDelMundo([], ''), null, 'sin mundos: todos');
    assert.equal(mm.modosDelMundo(M, 'trabajo'), null, 'sin declarar: todos');
    assert.deepEqual(mm.modosDelMundo(M, 'personal'), ['todo', 'foco'], 'los suyos, en su orden');
    assert.equal(mm.modosDelMundo(M, ''), null, 'ambos con uno que los tiene todos: todos');
    assert.deepEqual(mm.modosDelMundo(M.slice(1), ''), ['todo', 'foco', 'lectura'], 'ambos: la unión, en el orden de los mundos');
    assert.equal(mm.modosDelMundo(M, 'otro'), null, 'uno que no se declara: como ambos');

    const hay = ['tactica', 'estrategia', 'foco', 'todo'];
    const entrar = o => mm.modoAlEntrar({ existentes: hay, impuesto: false, entra: true, ...o });
    assert.deepEqual(entrar({ permitidos: ['todo', 'foco'], actual: 'tactica' }), { clave: 'todo', impuesto: true, previo: 'tactica' },
        'no lo tiene: el primero, y se sabe cuál estaba');
    assert.deepEqual(entrar({ permitidos: ['todo', 'foco'], actual: 'tactica', recordado: 'foco' }).clave, 'foco', 'no lo tiene: el que se tuvo ahí');
    assert.equal(entrar({ permitidos: ['todo', 'foco'], actual: 'tactica', recordado: 'estrategia' }).clave, 'todo',
        'el recordado que ya no tiene no vale');
    assert.deepEqual(entrar({ permitidos: null, actual: 'todo', recordado: 'tactica', impuesto: true, previo: 'estrategia' }),
        { clave: 'tactica', impuesto: false, previo: '' }, 'lo impuso el otro mundo: vuelve el que se tuvo aquí');
    assert.deepEqual(entrar({ permitidos: null, actual: 'todo', impuesto: true, previo: 'estrategia' }),
        { clave: 'estrategia', impuesto: false, previo: '' }, 'sin saber cuál se tuvo aquí: el que estaba antes de imponerlo');
    assert.equal(entrar({ permitidos: ['todo'], actual: 'foco', impuesto: true, previo: 'tactica' }).previo, 'tactica',
        'impuesto dos veces: se recuerda el de antes del primero');
    assert.deepEqual(entrar({ permitidos: null, actual: 'foco', recordado: 'tactica' }), { clave: 'foco', impuesto: false, previo: '' },
        'lo eligió la persona y este mundo lo tiene: se queda');
    assert.deepEqual(entrar({ permitidos: null, actual: 'todo', recordado: 'tactica', impuesto: true, previo: 'tactica', entra: false }),
        { clave: 'todo', impuesto: true, previo: 'tactica' }, 'sin entrar a otro mundo (la página recién abierta) no se vuelve a nada');

    // la banda: solo los del mundo, y el puesto aunque no sea de ellos
    const ids = html => [...html.matchAll(/data-id="([^"]+)"/g)].map(x => x[1]);
    assert.deepEqual(ids(mm.modosAdentro('todo', { solo: ['todo', 'foco'] })), ['foco', 'todo'], 'en el orden de la banda');
    assert.deepEqual(ids(mm.modosAdentro('tactica', { solo: ['todo', 'foco'] })), ['tactica', 'foco', 'todo'], 'el puesto, siempre');
    assert.deepEqual(ids(mm.modosAdentro('tactica', { solo: null })), ['tactica', 'estrategia', 'foco', 'todo']);
    assert.deepEqual(ids(mm.modosAdentro('tactica')), ['tactica', 'estrategia', 'foco', 'todo']);
}

// ── 2. en la página ──
const { modos, mundo } = P;
const puesto = () => modos.puesto().clave;
const vistas = [];
modos.alPoner((clave, o) => vistas.push([clave, o.porMundo]));
mundo.montar();
modos.montar();
await pasar();

// miércoles 18:00: rige trabajo, que los tiene todos
assert.equal(mundo.puesto().mundo, 'trabajo');
assert.equal(modos.delMundo(), null);
assert.equal(puesto(), 'tactica');
assert.equal(modos.permitidos().length, 5);

// 19:01: personal (todo y foco): la página pasa a todo, sin saltar a su vista (fue el horario, no la persona)
a(18, 19, 1);
assert.equal(mundo.puesto().mundo, 'personal');
assert.deepEqual(modos.delMundo(), ['todo', 'foco']);
assert.equal(puesto(), 'todo');
assert.equal(document.body.dataset.modo, 'todo');
assert.deepEqual(vistas, [['todo', true]], 'quien muestra la vista se entera de que lo puso el mundo (en un hilo, no salta)');
assert.deepEqual(modos.permitidos().map(m => m.clave), ['foco', 'todo']);

// lo que el mundo no tiene no se pone: ni un clic, ni su tecla
assert.equal(modos.cambiar('tactica'), false);
assert.equal(modos.cambiar('lectura'), false, 'un propio que el mundo no tiene, tampoco');
tecla('Digit1');
tecla('Digit2');
assert.equal(puesto(), 'todo', '⌥⇧1 y ⌥⇧2 no hacen nada en personal');

// jueves 9:01: trabajo de nuevo: vuelve táctica, lo que se tenía ahí (personal impuso todo)
a(19, 9, 1);
assert.equal(mundo.puesto().mundo, 'trabajo');
assert.equal(puesto(), 'tactica');
assert.equal(modos.delMundo(), null);
assert.equal(modos.cambiar('estrategia'), true);

// a mano a personal: el que se tuvo ahí la última vez (todo), y esta vez sí va a su vista
vistas.length = 0;
mundo.poner('personal');
assert.equal(puesto(), 'todo');
assert.deepEqual(vistas, [['todo', true]], 'también a mano');
// el siguiente, solo entre los suyos; foco y vuelta
tecla('KeyM');
assert.equal(puesto(), 'foco', '⌥⇧M: el siguiente de los suyos');
tecla('KeyM');
assert.equal(puesto(), 'todo', 'y de vuelta, sin pasar por los que no tiene');
tecla('Digit3');
assert.equal(puesto(), 'foco', '⌥⇧3 sí: foco es de personal');
tecla('KeyF');
assert.equal(puesto(), 'todo', '⌥⇧F sale de foco al de antes');
modos.cambiar('foco');
modos.alternarFoco();
assert.equal(puesto(), 'todo', 'si el de antes no es del mundo, al primero de los suyos que no es foco');
// en personal la persona elige foco; al volver a trabajo, que también lo tiene, se queda (lo eligió ella)
modos.cambiar('foco');
mundo.poner('trabajo');
assert.equal(puesto(), 'foco', 'lo elegido se respeta');
// y al volver a personal, foco sigue (es de los suyos)
mundo.poner('personal');
assert.equal(puesto(), 'foco');

// ambos: la unión; con trabajo, que los tiene todos, todos
mundo.poner('');
assert.equal(modos.delMundo(), null);
trabajo = { ...trabajo, modos: ['tactica', 'estrategia'] };
mundo.recibirDetalle(MUNDOS());
assert.deepEqual(modos.delMundo(), ['tactica', 'estrategia', 'todo', 'foco'], 'ambos: los de los dos');
assert.equal(puesto(), 'foco');
trabajo = { ...trabajo, modos: [] };
mundo.recibirDetalle(MUNDOS());

// ⚙ mundos le quita a personal el modo puesto: la página pasa al primero de su lista, al tiro
mundo.poner('personal');
personal = { ...personal, modos: ['todo'] };
mundo.recibirDetalle(MUNDOS());
assert.equal(puesto(), 'todo');
assert.equal(modos.cambiar('foco'), false);
tecla('KeyF');
assert.equal(puesto(), 'todo', '⌥⇧F no hace nada en un mundo sin foco');
// y al revés: sin modos, los tiene todos
personal = { ...personal, modos: [] };
mundo.recibirDetalle(MUNDOS());
assert.equal(modos.delMundo(), null);
assert.equal(modos.cambiar('tactica'), true);

// al volver a abrir la página de noche en personal: todo nunca es la de partida (táctica), pero personal no tiene
// táctica: al llegar los mundos, el último que se tuvo ahí
personal = { ...personal, modos: ['todo', 'foco'] };
mundo.recibirDetalle(MUNDOS());
assert.equal(puesto(), 'todo');
mundo.volverAlHorario();   // jueves 9:01: trabajo, y vuelve el que se tenía ahí (foco)
assert.equal(puesto(), 'foco');
a(19, 21, 0);
assert.equal(mundo.puesto().mundo, 'personal');
modos.cambiar('todo');
pagina();
const otra = path.join(dir, 'modos-mundo-de-nuevo.cjs');
writeFileSync(otra, readFileSync(salida));
const Q = require(otra);
Q.mundo.montar();
Q.modos.montar();
assert.equal(Q.modos.puesto().clave, 'tactica', 'antes de que lleguen los mundos, táctica, como siempre');
await pasar();
assert.equal(Q.mundo.puesto().mundo, 'personal');
assert.equal(Q.modos.puesto().clave, 'todo', 'en personal, el que se tuvo ahí');
// y a la mañana, trabajo vuelve a táctica: personal lo impuso
a(20, 9, 0);
assert.equal(Q.mundo.puesto().mundo, 'trabajo');
assert.equal(Q.modos.puesto().clave, 'foco', 'en trabajo, el último que se tuvo ahí');

// un navegador nuevo (nada recordado), abierto de noche: personal impone todo sobre táctica; a la mañana, trabajo vuelve
// a táctica, aunque nunca se estuvo ahí
pagina();   // (sin los relojes de las páginas de antes, que escribirían en el almacén)
almacen.clear();
a(20, 21, 0);
const nueva = path.join(dir, 'modos-mundo-nuevo.cjs');
writeFileSync(nueva, readFileSync(salida));
const N = require(nueva);
N.mundo.montar();
N.modos.montar();
await pasar();
assert.equal(N.mundo.puesto().mundo, 'personal');
assert.equal(N.modos.puesto().clave, 'todo');
a(23, 9, 0);   // lunes
assert.equal(N.mundo.puesto().mundo, 'trabajo');
assert.equal(N.modos.puesto().clave, 'tactica', 'el que estaba antes de que personal impusiera todo');

// ── 3. la fila «modos» de ⚙ mundos ──
{
    const { alternarModo, decirModos } = P;
    const hay = ['tactica', 'estrategia', 'foco', 'todo', 'lectura'];
    assert.deepEqual(alternarModo(['todo'], hay, 'foco'), { modos: ['todo', 'foco'], error: '' }, 'agregar: al final');
    assert.deepEqual(alternarModo(['todo', 'foco'], hay, 'todo'), { modos: ['foco'], error: '' }, 'quitar el primero: entra en el que sigue');
    assert.equal(alternarModo(['todo'], hay, 'todo').error, 'un mundo tiene al menos un modo');
    assert.deepEqual(alternarModo([], hay, 'estrategia'), { modos: ['tactica', 'foco', 'todo', 'lectura'], error: '' }, 'de todos, quitar uno');
    assert.deepEqual(alternarModo(['tactica', 'estrategia', 'foco', 'todo'], hay, 'lectura'), { modos: null, error: '' },
        'tenerlos todos es no declararlos');
    const H = [{ clave: 'todo', nombre: 'todo' }, { clave: 'foco', nombre: 'foco' }, { clave: 'tactica', nombre: 'táctica' }];
    assert.equal(decirModos([], H), 'todos');
    assert.equal(decirModos(['todo', 'foco'], H), 'todo, foco · entra en todo');
    assert.equal(decirModos(['tactica'], H), 'táctica');
}

// ── 4. las pestañas de un modo: al tiro en el puesto, y solo esa línea ──
{
    const pedidos = [];
    const antes = globalThis.fetch;
    globalThis.fetch = async (url, o = {}) => {
        if (o.method !== 'PATCH') return antes(url, o);
        const cuerpo = JSON.parse(o.body);
        pedidos.push([String(url), cuerpo]);
        const filas = cuerpo.valores.filas;
        return json({ ok: true, modos: MODOS.modos.map(m => (m.clave !== 'tactica' ? m : { ...m,
            valores: { ...m.valores, filas: filas ?? 'tactica' }, propios: filas === null ? [] : ['filas'],
            heredados: filas === null ? {} : { filas: 'tactica' } })) });
    };
    assert.equal(N.modos.puesto().clave, 'tactica');
    N.modos.poner('filas', 'proyectos');   // un cambio a mano de antes: la fila de ⚙ modos le gana
    let avisos = 0;
    N.modos.alCambiar(() => avisos++);
    const hecho = N.modos.guardarFilas('tactica', 'calendario, ahora');
    assert.deepEqual(N.modos.filas(), ['calendario', 'ahora'], 'al tiro, antes de que conteste la API');
    assert.ok(avisos > 0, 'la barra se entera y se redibuja');
    assert.equal(N.modos.deDonde(N.modos.puesto(), 'filas'), 'propio');
    assert.equal(await hecho, '');
    assert.deepEqual(pedidos, [['/api/modos/tactica', { valores: { filas: 'calendario, ahora' } }]], 'solo esa línea');
    assert.deepEqual(N.modos.cambiosAMano(), {}, 'el cambio a mano de filas se fue');
    // null: sin la línea, a lo de fábrica
    const vuelta = N.modos.guardarFilas('tactica', null);
    assert.deepEqual(N.modos.filas(), ['tactica'], 'a lo heredado, al tiro');
    assert.equal(await vuelta, '');
    assert.deepEqual(pedidos[1], ['/api/modos/tactica', { valores: { filas: null } }]);
    assert.equal(N.modos.deDonde(N.modos.puesto(), 'filas'), 'heredado');
    assert.equal(N.modos.origen(N.modos.puesto(), 'filas'), 'fabrica');
    globalThis.fetch = antes;
}

console.log('prueba:modos-mundo ok');
