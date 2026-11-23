// Prueba del orden de una pestaña de lectura (un proveedor con `pestana` y `vista = "lectura"`: el feed «leer"):
// src/vistas/dashboard/dia.ts (`ordenLectura`, lo que usa tareas.ts, `dePestana`, para la lista, la ficha, ← → y
// «sigue»), la fila del ítem (fila-tarea.ts, `marcas`) y el encabezado de su ficha (leer.ts). Con un proveedor de
// mentira: las filas de `telar hoy` de esa pestaña.
//
// - primero lo que se mandó la persona misma (`de`), después por prioridad (alta, media, baja, sin), y dentro de cada
//   una lo más nuevo arriba (`fecha`);
// - sin tope: todo lo que entrega el proveedor, también si es largo;
// - sin `de` ni `prioridad` en ninguna fila, el orden del proveedor, tal cual (el de hoy), y la fila de siempre;
// - la prioridad y «tuya» se ven en la fila y en la ficha.
// Corre en Node: npm run prueba:leer
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'leer-orden-'));
const entrada = path.join(dir, 'entrada.ts');
const src = path.join(aqui, '..', 'src');
const de = (...r) => JSON.stringify(path.join(src, ...r));
writeFileSync(entrada, [
    `export { pendientes, ordenLectura, yo } from ${de('vistas', 'dashboard', 'dia.ts')};`,
    `export { filaTarea } from ${de('vistas', 'dashboard', 'fila-tarea.ts')};`,
    `export { html as fichaLectura } from ${de('vistas', 'dashboard', 'leer.ts')};`,
].join('\n'));
const salida = path.join(dir, 'leer.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning',
    loader: { '.css': 'text' } });
const nodo = () => ({ addEventListener() {}, removeEventListener() {}, appendChild() {}, append() {}, remove() {}, setAttribute() {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, style: {}, dataset: {}, querySelector: () => null,
    querySelectorAll: () => [], children: [], className: '', textContent: '' });
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
globalThis.document ??= { addEventListener() {}, visibilityState: 'visible', hidden: false, body: nodo(), documentElement: nodo(),
    createElement: nodo, getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
const L = require(salida);
L.yo.persona = 'ana';

// el proveedor de mentira: filas de `telar hoy` de la pestaña «leer» (lo demás del día no entra)
const fila = (id, extra = {}) => ({ texto: `pieza ${id}`, hecho: false, en_curso: false, id, ref: id, origen: 'lecturas', proveedor: 'lecturas',
    ficha: true, cuando: null, url: '', hilo: '', ruta: '', pestana: 'leer', ...extra });
const dia = filas => ({ ahora: '2026-11-18T10:00:00', fecha: '2026-11-18', nombreDia: 'miércoles', semana: 47, agenda: [], declarados: ['lecturas'],
    fallas: [], pendientes: [...filas, { texto: 'una tarea', hecho: false, en_curso: false, id: 'T1', ref: 'T1', origen: 'tareas', proveedor: 'tareas',
        cuando: null, url: '', hilo: '', ruta: '' }] });
const ids = d => L.ordenLectura(L.pendientes(d, 'leer')).map(p => p.fila.id);

// 1. el orden: lo de la persona, después alta (P1), media (P2), baja (P3), sin; y en cada una, lo más nuevo arriba
{
    const d = dia([
        fila('baja-vieja', { prioridad: 3, de: 'correo', fecha: '2026-11-01' }),
        fila('sin-nueva', { prioridad: null, de: 'correo', fecha: '2026-11-18' }),
        fila('alta-vieja', { prioridad: 1, de: 'correo', fecha: '2026-11-02' }),
        fila('ana-baja', { prioridad: 3, de: 'ana', fecha: '2026-11-18' }),
        fila('media', { prioridad: 2, de: 'huerto', fecha: '2026-11-10' }),
        fila('alta-nueva', { prioridad: 1, de: 'correo', fecha: '2026-11-17' }),
        fila('ana-alta-vieja', { prioridad: 1, de: 'Ana', fecha: '2026-11-05' }),
        fila('alta-sin-fecha', { prioridad: 1, de: 'correo' }),
        fila('ana-sin-pri', { de: 'ana', fecha: '2026-11-12' }),
        fila('baja-nueva', { prioridad: 3, fecha: '2026-11-15' }),
    ]);
    assert.deepEqual(ids(d), [
        'ana-alta-vieja', 'ana-baja', 'ana-sin-pri',
        'alta-nueva', 'alta-vieja', 'alta-sin-fecha',
        'media',
        'baja-nueva', 'baja-vieja',
        'sin-nueva',
    ], 'lo de la persona primero; después prioridad; y en cada una lo más nuevo arriba (lo sin fecha al final de la suya)');
    // la tarea del día no es de la pestaña
    assert.ok(!ids(d).includes('T1'));
}

// 2. sin tope: 60 piezas entran las 60, y la alta más nueva queda primera aunque el proveedor la dé al final
{
    const muchas = Array.from({ length: 60 }, (_, i) => fila(`p${i}`, { prioridad: 3, de: 'correo', fecha: `2026-10-${String(1 + (i % 28)).padStart(2, '0')}` }));
    muchas.push(fila('la-alta', { prioridad: 1, de: 'correo', fecha: '2026-09-01' }));
    const orden = ids(dia(muchas));
    assert.equal(orden.length, 61, 'todo lo que entrega el proveedor');
    assert.equal(orden[0], 'la-alta', 'lo de prioridad alta, arriba de todo');
    // y la lista de la pestaña dibuja una fila por cada una
    const html = L.ordenLectura(L.pendientes(dia(muchas), 'leer')).map(p => L.filaTarea(p, { lectura: true, marcas: true })).join('');
    assert.equal((html.match(/class="item tarea/g) ?? []).length, 61);
}

// 3. sin `de` ni `prioridad` en ninguna fila: el orden del proveedor, tal cual, aunque traigan fecha
{
    const d = dia([fila('2026-11-09-a', { fecha: '2026-11-09' }), fila('2026-11-18-b', { fecha: '2026-11-18' }), fila('2026-11-12-c', { fecha: '2026-11-12' })]);
    assert.deepEqual(ids(d), ['2026-11-09-a', '2026-11-18-b', '2026-11-12-c']);
    const sin = dia([fila('x'), fila('y'), fila('z')]);
    assert.deepEqual(ids(sin), ['x', 'y', 'z']);
    // y la fila de siempre: sin las ranuras de la prioridad y «tuya»
    const [p] = L.pendientes(sin, 'leer');
    assert.ok(!L.filaTarea(p, { lectura: true }).includes('item-inicio'));
}

// 4. se ve: en la fila, la prioridad (el círculo en su color) y «tuya»; sin prioridad, su ranura vacía
{
    const [ana, sinPri] = L.pendientes(dia([fila('a', { prioridad: 1, de: 'ana' }), fila('b', { de: 'correo' })]), 'leer');
    const h = L.filaTarea(ana, { lectura: true, marcas: true });
    assert.match(h, /item-inicio/);
    assert.match(h, /tono-p1/, 'la alta, en su color');
    assert.match(h, /tuya: te la mandaste tú/);
    const h2 = L.filaTarea(sinPri, { lectura: true, marcas: true });
    assert.match(h2, /item-inicio/, 'las dos ranuras igual, para que la lista alinee');
    assert.doesNotMatch(h2, /tono-p\d|tuya/);
    // y en la ficha, arriba: «alta» y «tuya»
    const ficha = L.fichaLectura({ pagina: { titulo: 'una lectura', bloques: [], acciones: [] }, fila: ana.fila, clave: 'leer:x' });
    assert.match(ficha, /class="marca tono-p1"[^>]*>.*alta<\/span>/);
    assert.match(ficha, /class="marca tono-acento"[^>]*>.* tuya<\/span>/);
    const fichaSin = L.fichaLectura({ pagina: { titulo: 'otra', bloques: [], acciones: [] }, fila: sinPri.fila, clave: 'leer:y' });
    assert.doesNotMatch(fichaSin, /class="marca/);
}

console.log('leer-orden: ok');
