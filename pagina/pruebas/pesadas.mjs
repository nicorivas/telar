// Prueba de cómo la página pide al abrirse (src/cli.ts): que lo pesado no tape lo esencial, que la configuración que
// piden varios a la vez salga una sola vez, y que lo último leído vuelva al recargar la pestaña (un despliegue). Antes,
// al abrirla salían juntos el día, las esperas, los bloques y los proyectos, y la lista de hilos esperaba en la cola del
// navegador (seis conexiones) detrás de ellos; y al recargar, la página quedaba en blanco hasta que todo contestaba de
// nuevo (26-nov-2026). Con un fetch de mentira que la prueba contesta cuando quiere: nada sale.
// Corre en Node: npm run prueba:pesadas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'pesadas-'));
const src = path.join(aqui, '..', 'src');
const entrada = path.join(dir, 'entrada.ts');
writeFileSync(entrada, [
    `export * as cli from ${JSON.stringify(path.join(src, 'cli.ts'))};`,
    `export { dia, diaGuardado } from ${JSON.stringify(path.join(src, 'vistas', 'dashboard', 'dia.ts'))};`,
].join('\n'));
const salida = path.join(dir, 'pesadas.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });

// lo de la página que se toca al cargar: lo justo, sin DOM
const nodo = () => ({ addEventListener() {}, removeEventListener() {}, appendChild() {}, append() {}, remove() {}, setAttribute() {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, style: {}, dataset: {}, querySelector: () => null,
    querySelectorAll: () => [], children: [], className: '', textContent: '' });
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
globalThis.document ??= { addEventListener() {}, visibilityState: 'visible', hidden: false, body: nodo(), documentElement: nodo(),
    createElement: nodo, getElementById: () => null, querySelector: () => null, querySelectorAll: () => [] };
globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
// el almacén de la pestaña: sobrevive a «recargar» (volver a cargar el módulo), como en el navegador
const almacen = new Map();
globalThis.sessionStorage = { getItem: k => almacen.get(k) ?? null, setItem: (k, v) => { almacen.set(k, String(v)); }, removeItem: k => { almacen.delete(k); } };

// el fetch de mentira: cada pedido queda esperando hasta que la prueba lo contesta
const pedidos = [];
globalThis.fetch = (url, init = {}) => new Promise(resolver => {
    pedidos.push({ url: String(url), metodo: init.method ?? 'GET',
        contestar: (cuerpo, estado = 200) => resolver(new Response(JSON.stringify(cuerpo), { status: estado, headers: { 'Content-Type': 'application/json' } })) });
});
const pasar = () => new Promise(r => setTimeout(r, 0));
/** cargar la página de nuevo: el módulo desde cero, con el almacén de la pestaña como quedó */
const cargar = () => { delete require.cache[require.resolve(salida)]; return require(salida); };
const de = prefijo => pedidos.filter(p => p.url.startsWith(`/api${prefijo}`));

const HOY = (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; })();
const dia = texto => ({ ahora: `${HOY}T10:00:00`, dia: 'jueves', fecha: HOY, semana: 48,
    pendientes: [{ texto, hecho: false, en_curso: false, id: '', ref: 'faro:1', origen: 'faro/README.md' }], proveedores: { declarados: [], fallas: [] } });

let P = cargar();
const { cli } = P;

// 1. lo pesado va de a PESADAS; lo esencial sale al tiro aunque esperen
{
    assert.equal(cli.esPesada('/hoy?local=true'), true);
    assert.equal(cli.esPesada('/bloques/correo'), true);
    assert.equal(cli.esPesada('/bloques/correo/items/abc'), false, 'el detalle de un ítem es un clic: no espera');
    assert.equal(cli.esPesada('/hilos?orden=mux'), false);
    assert.equal(cli.esPesada('/tipos/tarea/T84'), false, 'la ficha de una tarea es un clic: no espera');
    assert.equal(cli.esPesada('/hoyx'), false);

    const pesadas = ['correo', 'registro', 'productos', 'whatsapp', 'tablero'].map(b => cli.bloque(b));
    assert.equal(de('/bloques/').length, cli.PESADAS, 'solo PESADAS salen a la vez');
    const hilos = cli.hilos(false, 'mux');
    assert.equal(de('/hilos').length, 1, 'la lista de hilos sale aunque lo pesado espere');
    de('/hilos')[0].contestar({ hilos: [] });
    assert.ok((await hilos).datos);
    // una pesada que termina deja pasar a la siguiente, en orden
    de('/bloques/')[0].contestar({ html: '' });
    await pasar();
    assert.deepEqual(de('/bloques/').map(p => p.url), ['/api/bloques/correo', '/api/bloques/registro', '/api/bloques/productos', '/api/bloques/whatsapp']);
    // una que falla también suelta su lugar
    de('/bloques/')[1].contestar({ detail: 'no' }, 500);
    await pasar();
    assert.equal(de('/bloques/').length, 5);
    for (const p of de('/bloques/').slice(2)) p.contestar({ html: '' });
    await Promise.all(pesadas);
    // ya sin nada en curso: las siguientes PESADAS salen al tiro, sin esperar una vuelta
    pedidos.length = 0;
    const otras = [cli.esperas(), cli.periodicos(), cli.pendientesRepo()];
    assert.equal(pedidos.length, 3);
    for (const p of pedidos) p.contestar({ esperas: [], periodicos: [], pendientes: [] });
    await Promise.all(otras);
    pedidos.length = 0;
}

// 2. la configuración que piden varios a la vez sale una vez; cada uno con su copia; después de un cambio, otra
{
    const a = cli.config(), b = cli.config(), c = cli.config();
    assert.equal(de('/config').length, 1, 'tres a la vez: un solo /config');
    de('/config')[0].contestar({ secciones: [{ clave: 's', nombre: 'S', hilos: [] }] });
    const [ra, rb, rc] = await Promise.all([a, b, c]);
    assert.deepEqual(ra.datos, rb.datos);
    ra.datos.secciones.push('cambiada');
    assert.equal(rb.datos.secciones.length, 1, 'cada uno con su copia: lo que uno cambia no le llega al otro');
    assert.equal(rc.datos.secciones.length, 1);
    // terminada, la siguiente sale de nuevo (no se guarda: solo se comparte la que va)
    const d = cli.config();
    assert.equal(de('/config').length, 2);
    // un cambio mientras va (un POST): la que iba puede traer lo de antes, y la siguiente sale aparte
    void cli.encargar('Cartero', 'algo');
    const e = cli.config();
    assert.equal(de('/config').length, 3, 'después de un POST, la configuración se pide de nuevo');
    for (const p of de('/config').slice(1)) p.contestar({ secciones: [] });
    for (const p of de('/encargos')) p.contestar({ hilo: 'Cartero' });
    await Promise.all([d, e]);
    pedidos.length = 0;
}

// 3. lo último leído vuelve al recargar la pestaña: el día y los proyectos, mientras se leen de nuevo
{
    assert.equal(P.diaGuardado(), undefined, 'sin nada leído, nada guardado');
    const d = P.dia(0, true);
    de('/hoy')[0].contestar(dia('la viñeta de antes'));
    assert.equal((await d).pendientes[0].texto, 'la viñeta de antes');
    const p = cli.proyectos();
    de('/proyectos')[0].contestar({ raiz: '/r', proyectos: [{ ruta: 'faro', nombre: 'Faro' }], areas: ['Norte'] });
    await p;
    assert.equal(cli.proyectosRecordados().proyectos[0].nombre, 'Faro');
    pedidos.length = 0;

    // recarga: el módulo desde cero, con el almacén de la pestaña
    P = cargar();
    const guardado = P.diaGuardado();
    assert.ok(guardado, 'al recargar, el día de antes está');
    assert.equal(guardado.pendientes[0].texto, 'la viñeta de antes');
    assert.equal(pedidos.length, 0, 'mostrarlo no pide nada');
    assert.deepEqual(P.cli.proyectosRecordados().proyectos.map(x => x.ruta), ['faro']);
    assert.deepEqual(P.cli.proyectosRecordados().areas, ['Norte']);
    // lo de otro día no sirve: el de ayer mostrado como hoy engaña
    const clave = 'telar.recordado.dia';
    const viejo = JSON.parse(almacen.get(clave));
    viejo.valor.cache.dia.fecha = '2020-01-01';
    almacen.set(clave, JSON.stringify(viejo));
    P = cargar();
    assert.equal(P.diaGuardado(), undefined, 'el día guardado de otra fecha no se muestra');
    // sin almacén (o lleno), nada se rompe
    const antes = globalThis.sessionStorage;
    globalThis.sessionStorage = { getItem() { throw new Error('sin almacén'); }, setItem() { throw new Error('lleno'); }, removeItem() {} };
    P = cargar();
    assert.equal(P.diaGuardado(), undefined);
    P.cli.recordar('x', { a: 1 });
    assert.equal(P.cli.recordado('x'), undefined);
    globalThis.sessionStorage = antes;
}

console.log('pesadas: ok');
