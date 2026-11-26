// Prueba de «tareas › esperando» (src/vistas/dashboard/esperando.ts): qué tareas entran (las que esperan a alguien y las
// delegadas; las de la persona no), cómo se juntan las personas (un nombre de pila con el entero que empieza así, si hay
// uno solo), el orden (la persona que debe hace más primero; en cada una, las que esperan antes que las delegadas), lo que
// dice la meta (plazo · antigüedad), la fila de lo último que pasó, el cuerpo entero (una sección por persona, plegada o
// no, los filtros con sus cuentas, «leyendo» antes de tener las tareas) y que sea una subpestaña de tareas.
// Corre en Node: npm run prueba:esperando
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'esperando-')), 'esperando.cjs');
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
await build({ stdin: { contents: "export * from './vistas/dashboard/esperando'; export { yo } from './vistas/dashboard/dia';"
    + " export { SUBPESTANAS, SECCION_DE_PANTALLA, ICONO_VISTA, BARRA_DE } from './vistas/dashboard/pantalla';",
    resolveDir: path.join(aqui, '..', 'src'), loader: 'ts' }, bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const E = require(salida);
const { compromisos, claves, deudores, metaDe, filas, cuerpo, resumen, yo } = E;

yo.persona = 'ana';
yo.nombres = ['Ana Pérez'];
const AHORA = Date.parse('2026-11-26T12:00:00');
// una tarea como la entrega pendientes() (dia.ts): la fila del proveedor y los días al plazo
const tarea = (id, mas = {}, dias = null) => ({
    fila: { texto: `lo de ${id}`, hecho: false, en_curso: false, id, origen: 'tareas', ref: id, hilo: '', ruta: '', proveedor: 'tareas',
        cuando: dias === null ? null : '2026-11-30', url: '', ficha: true, prioridad: 2, ...mas },
    ref: id, texto: `lo de ${id}`, hilo: '', cuando: dias === null ? '' : '2026-11-30', dias, enCurso: false, avance: '', urgencia: 0, urgente: false,
});
const LISTA = [
    tarea('T1', { espera: '@Inés Rojas', desde: '2026-10-15 16:59', ultimo: { fecha: '2026-11-12 10:00', tipo: 'nota', texto: 'llegaron los **repos**' } }, -38),
    tarea('T2', { espera: 'Inés Rojas', dueno: 'Tomás', desde: '2026-10-22 13:11' }),
    tarea('T3', { dueno: 'Leo', desde: '2026-11-03 09:10', ultimo: { fecha: '2026-11-03 09:10', tipo: 'edita', texto: 'dueño Leo' } }, 4),
    tarea('T4', { dueno: 'Leo Martín', desde: '2026-11-10 12:00' }, -1),
    tarea('T5', { dueno: 'Ana' }),            // a nombre de la persona: suya
    tarea('T6', {}),                          // sin dueño: suya
    tarea('T7', { espera: 'legal', desde: '2026-09-02' }),
    tarea('T8', { dueno: 'Carla' }),          // un telar de antes: sin desde ni lo último
    tarea('T9', { espera: 'Inés Rojas', dueno: 'ana pérez', desde: '2026-11-01' }),  // espera, y la hace la persona: no lo dice
];

// 1. qué entra: lo que espera a alguien (por a quién) y lo delegado (por quién la hace); lo de la persona, no
{
    const cs = compromisos(LISTA);
    assert.deepEqual(cs.map(c => [c.p.ref, c.clase, c.persona]), [
        ['T1', 'espera', 'Inés Rojas'], ['T2', 'espera', 'Inés Rojas'], ['T3', 'delegada', 'Leo'], ['T4', 'delegada', 'Leo Martín'],
        ['T7', 'espera', 'legal'], ['T8', 'delegada', 'Carla'], ['T9', 'espera', 'Inés Rojas']]);
    // la que espera y la hace otro lo dice; la que la hace la persona, no
    assert.equal(cs.find(c => c.p.ref === 'T2').dueno, 'Tomás');
    assert.equal(cs.find(c => c.p.ref === 'T9').dueno, '');
    // desde, en ISO de este reloj (Safari no lee la fecha con espacio)
    assert.equal(cs[0].desde, '2026-10-15T16:59');
    assert.equal(cs.find(c => c.p.ref === 'T8').desde, '');
}

// 2. las personas: «Leo» va con «Leo Martín» (hay uno solo que empieza así); con dos, queda aparte
{
    const m = claves(['Leo', 'Leo Martín', 'Raúl', 'Raúl Soto', 'Raúl Vera', 'legal']);
    assert.equal(m.get('Leo').nombre, 'Leo Martín');
    assert.equal(m.get('Leo').clave, m.get('Leo Martín').clave);
    assert.equal(m.get('Raúl').nombre, 'Raúl');
    assert.equal(m.get('legal').clave, 'legal');
}

// 3. el orden: la persona que debe hace más primero; en cada una, las que esperan antes que las delegadas, de la más
// vieja a la más nueva; lo que no dice desde cuándo, al final
{
    const ds = deudores(compromisos(LISTA));
    assert.deepEqual(ds.map(d => d.nombre), ['legal', 'Inés Rojas', 'Leo Martín', 'Carla']);
    assert.deepEqual(ds[1].compromisos.map(c => c.p.ref), ['T1', 'T2', 'T9']);
    assert.deepEqual(ds[2].compromisos.map(c => c.p.ref), ['T3', 'T4']);
    const mezcla = deudores(compromisos([tarea('A', { dueno: 'Leo', desde: '2026-10-01' }), tarea('B', { espera: 'Leo', desde: '2026-11-01' })]));
    assert.deepEqual(mezcla[0].compromisos.map(c => c.clase), ['espera', 'delegada']);
}

// 4. la meta: el plazo (lo vencido en rojo, como en tareas) y la antigüedad; sin plazo, solo la antigüedad; sin nada, nada
{
    const cs = compromisos(LISTA);
    const m1 = metaDe(cs[0], AHORA);
    assert.match(m1.html, /tono-peligro[^>]*>-38d<\/span> · 5sem/);
    assert.match(m1.ayuda, /espera desde 2026-10-15 16:59/);
    assert.deepEqual([metaDe(cs[1], AHORA).texto, metaDe(cs[1], AHORA).tono], ['4sem', 'tenue']);
    assert.equal(metaDe(cs.find(c => c.p.ref === 'T8'), AHORA), undefined);
}

// 5. las filas: la tarea (reloj o persona, en su tinta; el código; abre la ficha) y, debajo, lo último que pasó
{
    const cs = compromisos(LISTA);
    const h = filas(cs[0], 'ines rojas', AHORA);
    assert.equal((h.match(/class="item /g) ?? []).length, 2);
    assert.match(h, /class="item tarea compromiso" data-accion="tarea" data-valor="\[&quot;tareas&quot;,&quot;T1&quot;,&quot;T1&quot;\]"/);
    assert.match(h, /data-clase="espera" data-persona="ines rojas" data-vencida="1"/);
    assert.match(h, /tono-atencion" title="espera a Inés Rojas desde 2026-10-15 16:59"/);
    // lo último: tenue, corrido, sin el markdown, con cuánto hace; también abre la ficha
    assert.match(h, /class="item apagada hondo1 compromiso compromiso-ultimo" data-accion="tarea"/);
    assert.match(h, /<span class="item-titulo">llegaron los repos<\/span>/);
    assert.match(h, /item-meta tono-tenue" title="2026-11-12 10:00">2sem/);
    // lo que se busca va en las dos filas: lo último también se encuentra
    assert.match(h, /data-busca="[^"]*llegaron los \*\*repos\*\*/);
    // la delegada: la persona en la tinta de lo que es de otro
    assert.match(filas(cs[2], 'leo martin', AHORA), /tono-remoto" title="delegada: la hace Leo desde 2026-11-03 09:10"/);
    // la que espera y la hace otro lo dice tras el título
    assert.match(filas(cs[1], 'ines rojas', AHORA), /· la hace Tomás/);
    // sin lo último (un telar de antes), una fila sola
    assert.equal((filas(cs.find(c => c.p.ref === 'T8'), 'carla', AHORA).match(/class="item /g) ?? []).length, 1);
}

// 6. el cuerpo: buscador, filtros con sus cuentas, una sección por persona (plegada: solo su cabecera) y los vacíos
{
    const cs = compromisos(LISTA);
    const h = cuerpo(cs, k => k !== 'carla', { ahora: AHORA }).join('');
    assert.match(h, /id="buscar-esperando"/);
    assert.match(h, /data-total="7" data-n-espera="4" data-n-delegada="3" data-n-vencida="2"/);
    assert.match(h, /data-id="cuales:espera"[^>]*>.*esperan<\/span> <span class="filtros-cuenta">4</);
    assert.deepEqual([...h.matchAll(/class="grupo-esperando" data-persona="([^"]+)"/g)].map(m => m[1]), ['legal', 'ines rojas', 'leo martin', 'carla']);
    // la cabecera es la de una sección (componentes/seccion.ts): su clave, su cuenta y la flecha
    assert.match(h, /class="item cabecera" data-accion="seccion" data-id="ines rojas"/);
    const carla = h.slice(h.indexOf('data-persona="carla"'));
    assert.doesNotMatch(carla.slice(0, carla.indexOf('</div>')), /compromiso/);
    assert.match(cuerpo([], () => true, { leyendo: true }).join(''), /leyendo las tareas…/);
    assert.match(cuerpo([], () => true).join(''), /nadie te debe nada/);
    assert.equal(resumen(cs), '7 que tiene otro (4 esperan, 3 delegadas) · 4 personas');
}

// 7. es una subpestaña de tareas: tras foco y lista, con su ícono y su globo, y la barra de tareas
{
    assert.deepEqual(E.SUBPESTANAS.tareas.map(x => x[1]), ['foco', 'lista', 'esperando']);
    assert.equal(E.SECCION_DE_PANTALLA.esperando, 'tareas');
    assert.ok(E.ICONO_VISTA.esperando[0]);
    assert.deepEqual(E.BARRA_DE.esperando, ['tareas', 'cian']);
}

console.log('esperando: ok');
