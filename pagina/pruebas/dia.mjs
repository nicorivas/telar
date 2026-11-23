// Prueba de lo que se ve después de marcar una tarea hecha (src/vistas/dashboard/dia.ts y el ✓ de tareas.ts,
// `marcarHecha`): que no vuelva. Antes volvía de dos maneras: el día que se ve era el de antes de marcarla (se redibujaba
// con ella hasta la relectura, ~10 s con red), y la relectura podía perderse tras una que iba desde antes y la traía
// abierta, que quedaba guardada (`deProveedores`) hasta la próxima consulta a la red: cinco minutos, o recargar. Con un
// fetch de mentira que la prueba contesta cuando quiere: nada sale.
// Corre en Node: npm run prueba:dia
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'dia-'));
const entrada = path.join(dir, 'entrada.ts');
const src = path.join(aqui, '..', 'src');
writeFileSync(entrada, [
    `export { dia, salio, conLoSalido, olvidarDia, pendientes, generacionDeAhora } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'dia.ts'))};`,
    `export { marcarHecha } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'tareas.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'dia.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
// lo de la página que se toca al cargar y al avisar: lo justo, sin DOM. Lo que se crea queda anotado: los avisos a la
// persona (web/interfaz.ts, `avisar`) son un div con su clase y su texto
const creados = [];
const nodo = () => {
    const n = { addEventListener() {}, removeEventListener() {}, appendChild() {}, append() {}, remove() {}, setAttribute() {},
        classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, style: {}, dataset: {}, querySelector: () => null,
        querySelectorAll: () => [], children: [], className: '', textContent: '' };
    creados.push(n);
    return n;
};
const avisosDichos = () => creados.filter(n => /^web-aviso (aviso|falla)$/.test(n.className)).map(n => n.textContent);
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
globalThis.document ??= { addEventListener() {}, visibilityState: 'visible', hidden: false, body: nodo(), documentElement: nodo(),
    createElement: nodo, getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };

// el fetch de mentira: cada pedido queda esperando hasta que la prueba lo contesta
const pedidos = [];
globalThis.fetch = (url, init = {}) => new Promise(resolver => {
    pedidos.push({ url: String(url), metodo: init.method ?? 'GET',
        contestar: (cuerpo, estado = 200) => resolver(new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } })) });
});
const D = require(salida);
const pendientesDe = url => pedidos.filter(p => p.url.startsWith(url));
// deja correr lo que espera a una promesa ya contestada
const pasar = () => new Promise(r => setTimeout(r, 0));

const HOY = (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; })();
const fila = (id, extra = {}) => ({ texto: `la tarea ${id}`, hecho: false, en_curso: false, id, ref: id, origen: 'tareas', proveedor: 'tareas',
    direccion: `tarea:${id}`, ficha: true, cuando: HOY, ...extra });
const vineta = { texto: 'la viñeta de faro', hecho: false, en_curso: false, id: '', ref: 'proyectos/faro:2', origen: 'proyectos/faro/README.md', proveedor: '' };
const hoy = pendientes => ({ ahora: `${HOY}T10:00:00`, dia: 'miércoles', fecha: HOY, semana: 47, pendientes,
    proveedores: { declarados: ['tareas'], fallas: [] } });
const abiertas = d => D.pendientes(d).map(p => p.ref);

// 1. el día que se ve, entre marcarla y la relectura: lo leído antes no la trae (conLoSalido), lo leído después manda
{
    const p = D.dia(0, true);
    pendientesDe('/api/hoy').at(-1).contestar(hoy([fila('T1'), fila('T2'), vineta]));
    const antes = await p;
    assert.deepEqual(abiertas(antes), ['T1', 'T2', 'proyectos/faro:2']);
    // nada salió: el mismo día, sin copiarlo
    assert.equal(D.conLoSalido(antes), antes);

    D.salio('tareas', 'T1');
    assert.deepEqual(abiertas(D.conLoSalido(antes)), ['T2', 'proyectos/faro:2']);
    // la viñeta de un documento: sin proveedor, por su ref
    D.salio('', 'proyectos/faro:2');
    assert.deepEqual(abiertas(D.conLoSalido(antes)), ['T2']);
    // otra tarea con el mismo número de otro proveedor no sale
    const otro = { ...antes, pendientes: [...antes.pendientes, fila('T1', { proveedor: 'lecturas', origen: 'lecturas' })] };
    assert.deepEqual(D.conLoSalido(otro).pendientes.filter(f => !f.hecho).map(f => `${f.proveedor}:${f.id || f.ref}`), ['tareas:T2', 'lecturas:T1']);
    // un día de mentira (sin generación: el ensayo de Táctica) no se toca
    const muestra = { ...antes, generacion: undefined };
    assert.equal(D.conLoSalido(muestra), muestra);

    // lo leído después de marcarla manda: si el proveedor la sigue trayendo (alguien la reabrió), se ve
    const p2 = D.dia(0, true);
    pendientesDe('/api/hoy').at(-1).contestar(hoy([fila('T1'), fila('T2')]));
    const despues = await p2;
    assert.ok(despues.generacion >= D.generacionDeAhora());
    assert.equal(D.conLoSalido(despues), despues);
    assert.deepEqual(abiertas(D.conLoSalido(despues)), ['T1', 'T2']);
}

// 2. la relectura después de marcarla no se pierde tras una que ya iba: lo que pasaba en Táctica («desaparece y vuelve; con
//    refresh, se va»). Va una lectura con red (volver a la pestaña tras cinco minutos); se marca hecha T3 mientras; la
//    que iba contesta con lo de antes (T3 abierta) después del cierre
{
    D.olvidarDia();
    const n = pedidos.length;
    const vieja = D.dia(0, true);
    assert.equal(pedidos.length, n + 1);
    const lecturaVieja = pedidos.at(-1);

    // el ✓: la acción por su rol, y el proveedor dice que sí
    const marcada = D.marcarHecha(JSON.stringify(['tareas', 'T3', 'T3']));
    await pasar();
    const accion = pedidos.at(-1);
    assert.equal(accion.metodo, 'POST');
    assert.equal(accion.url, '/api/tareas/T3/accion');
    accion.contestar({ tipo: 'comando', hecho: 'T3 hecha' });
    assert.equal(await marcada, true);

    // la relectura de después (actualizar(true) en el dashboard): no se cuelga de la que iba desde antes, es otra
    const nueva = D.dia(0, true);
    assert.equal(pedidos.length, n + 3, 'la relectura de después del cierre se hace, aunque ya fuera otra');
    const lecturaNueva = pedidos.at(-1);
    assert.equal(lecturaNueva.url, '/api/hoy');

    // la que iba vuelve con T3 abierta (la leyó antes del cierre): no se guarda ni se entrega
    lecturaVieja.contestar(hoy([fila('T3'), fila('T4')]));
    await pasar();
    lecturaNueva.contestar(hoy([fila('T4')]));
    const [a, b] = await Promise.all([vieja, nueva]);
    assert.deepEqual(abiertas(a), ['T4'], 'quien esperaba la de antes recibe la de después');
    assert.equal(a, b);

    // y lo que queda guardado es lo de después: una lectura local (la de cada minuto) tampoco la trae
    const local = D.dia(0, false);
    const pedidoLocal = pedidos.at(-1);
    assert.equal(pedidoLocal.url, '/api/hoy?local=true');
    pedidoLocal.contestar(hoy([vineta]));
    assert.deepEqual(abiertas(await local), ['T4', 'proyectos/faro:2']);
}

// 3. una lectura con red que se pide mientras va una local no se cuelga de ella (traería lo guardado, sin preguntarle al
//    proveedor), y una que se pide mientras va otra con red del mismo momento, sí (no se pide dos veces)
{
    const n = pedidos.length;
    const local = D.dia(0, false);
    const conRed = D.dia(0, true);
    const otraConRed = D.dia(0, true);
    assert.equal(pedidos.length, n + 2);
    assert.deepEqual(pedidos.slice(n).map(p => p.url), ['/api/hoy?local=true', '/api/hoy']);
    pedidos[n + 1].contestar(hoy([fila('T4'), fila('T5')]));
    pedidos[n].contestar(hoy([]));
    assert.equal(await conRed, await otraConRed);
    assert.deepEqual(abiertas(await conRed), ['T4', 'T5']);
    await local;
}

// 4. si el cierre falla, la tarea queda en lo que se ve (la fila vuelve) y se dice por qué
{
    const p = D.dia(0, true);
    pedidos.at(-1).contestar(hoy([fila('T6')]));
    const antes = await p;
    const marcada = D.marcarHecha(JSON.stringify(['tareas', 'T6', 'T6']));
    await pasar();
    const accion = pedidos.at(-1);
    assert.equal(accion.url, '/api/tareas/T6/accion');
    accion.contestar({ detail: 'T6: cambió desde que se leyó' }, 409);
    assert.equal(await marcada, false);
    assert.deepEqual(abiertas(D.conLoSalido(antes)), ['T6'], 'no se cerró: sigue en lo que se ve');
    assert.deepEqual(avisosDichos(), ['telar: T6: cambió desde que se leyó']);
}

console.log('dia: ok');
// los avisos se van solos a los segundos: no se los espera
process.exit(0);
