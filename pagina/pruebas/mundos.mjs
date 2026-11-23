// Prueba de los mundos vistos desde la configuración (src/web/mundos-agentes.ts): qué agentes salen con un mundo elegido
// (lo suyo y lo sin clasificar; con ambos, todos; en el modo todo, el mundo no esconde nada), por qué un agente es de su
// mundo, y lo que ⚙ mundos revisa antes de escribir (lo mismo que dice la configuración al leer `[mundos]`: un área, una
// ruta o una etiqueta en dos mundos no se puede; un horario que no se entiende, tampoco; el nombre de uno nuevo).
// Corre en Node: npm run prueba:mundos
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'mundos-')), 'mundos-agentes.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'mundos-agentes.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { seVeEn, porQue, leerLista, leerHorarioEscrito, choque, nombreNuevo } = require(salida);

// 1. qué sale con un mundo elegido: lo suyo y lo sin clasificar; con ambos, todo; en el modo todo, todo
assert.ok(seVeEn('trabajo', 'trabajo'));
assert.ok(!seVeEn('personal', 'trabajo'));
assert.ok(seVeEn('', 'trabajo'), 'sin clasificar: en todos');
assert.ok(seVeEn('personal', ''), 'ambos: todos');
assert.ok(seVeEn('personal', 'trabajo', true), 'en todo el mundo ordena y no esconde');

// 2. por qué: la etiqueta de su hilo, la ruta que calza con su carpeta, o nada
assert.match(porQue({ clave: 'vigia', mundo: 'trabajo', por: 'etiqueta', valor: 'oficina' }), /etiqueta «oficina» de su hilo/);
const porRuta = porQue({ clave: 'huerta', carpeta: 'agentes/huerta/', mundo: 'personal', por: 'ruta', valor: 'agentes/' });
assert.match(porRuta, /^de personal por su carpeta \(agentes\/huerta\/\): calza con la ruta «agentes\/»$/);
assert.match(porQue({ clave: 'suelto', carpeta: 'agentes/suelto/', mundo: '', por: '', valor: '' }), /^sin clasificar.*se ve en todos$/);
assert.match(porQue(undefined), /^sin clasificar/, 'uno que no vino en la lista: no se sabe de cuál es');
// lo que declara su agente.toml (`mundo = "personal"`) le gana a la carpeta y a las etiquetas, y se dice así
assert.match(porQue({ clave: 'jardin', carpeta: 'agentes/jardin/', mundo: 'personal', por: 'agente.toml', valor: 'mundo = "personal"' }),
    /^de personal: lo declara su agente\.toml \(mundo = "personal"\)/);

// 3. las listas de un campo: por coma, sin espacios a los lados ni repetidos; vacío, ninguna
assert.deepEqual(leerLista(' casa , jardin/,casa,, '), ['casa', 'jardin/']);
assert.deepEqual(leerLista('  '), []);

// 4. el horario: por «;» (un tramo lleva comas), cada tramo como lo lee la configuración; vacío, solo a mano
assert.deepEqual(leerHorarioEscrito('lun-vie 9:00-13:00; lun,mié 14-18 ;'), ['lun-vie 9:00-13:00', 'lun,mié 14-18']);
assert.deepEqual(leerHorarioEscrito(''), []);
assert.throws(() => leerHorarioEscrito('lun-vie 9-13; lunes a viernes'), /lunes a viernes/);
assert.throws(() => leerHorarioEscrito('lun 9-9'), /misma hora/);

// 5. lo que ya es de otro mundo, dicho desde el que se edita; lo propio sí; las rutas, con o sin la barra final
const MUNDOS = [
    { nombre: 'trabajo', areas: ['equipo'], rutas: ['empresa/', 'agentes/oficina/'], etiquetas: ['trabajo'] },
    { nombre: 'personal', areas: ['personal'], rutas: ['casa'], etiquetas: [] },
];
assert.equal(choque(MUNDOS, 'personal', 'rutas', ['casa/', 'empresa']), '«empresa» ya es de «trabajo»');
assert.equal(choque(MUNDOS, 'trabajo', 'rutas', ['empresa/', 'casa/']), '«casa/» ya es de «personal»');
assert.equal(choque(MUNDOS, 'trabajo', 'rutas', ['empresa/', 'agentes/oficina/', 'clientes/']), '');
assert.equal(choque(MUNDOS, 'personal', 'etiquetas', ['trabajo']), '«trabajo» ya es de «trabajo»');
assert.equal(choque(MUNDOS, 'personal', 'areas', ['personal', 'casa']), '');
assert.equal(choque(MUNDOS, 'trabajo', 'areas', ['personal']), '«personal» ya es de «personal»');
assert.match(choque(MUNDOS, 'trabajo', 'rutas', ['../afuera/']), /no puede subir/);
// «empresa-x» no es «empresa/»: solo la barra final se iguala
assert.equal(choque(MUNDOS, 'personal', 'rutas', ['empresa-x']), '');

// 6. el nombre de uno nuevo: una palabra, que no sea de telar ni de otro
assert.equal(nombreNuevo('estudio', ['trabajo']), '');
assert.match(nombreNuevo('trabajo', ['trabajo']), /ya hay/);
for (const malo of ['mi mundo', 'a.b', 'a/b', 'a,b', 'x:y', '', 'x"y']) assert.notEqual(nombreNuevo(malo, []), '', malo);
for (const de of ['sin-clasificar', 'fuera']) assert.match(nombreNuevo(de, []), /es de telar/);

// 4. qué pasa con un agente fuera de su mundo (`fuera_de_su_mundo` en su agente.toml), en la grilla de ⚙ mundos: las tres,
// la elegida marcada (sin la línea, al-final); uno sin mundo no tiene qué elegir. Un clic escribe por `PUT
// /mundos/agentes/<clave>` y lo que vuelve se aplica al tiro: `fueraDe` lo dice
{
    globalThis.localStorage ??= { getItem: () => null, setItem() {}, removeItem() {} };
    const salidaC = path.join(path.dirname(salida), 'config-mundos.cjs');
    await build({ stdin: { contents: "export { selectorFuera, FUERA } from './vistas/dashboard/config/mundos'; export * as mundo from './web/mundo';",
        resolveDir: path.join(aqui, '..', 'src'), loader: 'ts' }, bundle: true, platform: 'node', format: 'cjs', outfile: salidaC, logLevel: 'warning' });
    const C = require(salidaC);
    const jardin = { clave: 'jardin', nombre: 'Jardín', carpeta: 'agentes/jardin/', mundo: 'personal', por: 'agente.toml', valor: '' };
    const elegido = h => [...h.matchAll(/<a class="(si)?" data-accion="mundo-agente-fuera" data-valor="([^"]+)"/g)].filter(m => m[1]).map(m => m[2]);
    assert.deepEqual(elegido(C.selectorFuera(jardin)), ['jardin al-final'], 'sin la línea, al-final');
    const h = C.selectorFuera({ ...jardin, fuera_de_su_mundo: 'esconder' });
    assert.deepEqual(elegido(h), ['jardin esconder']);
    assert.deepEqual([...h.matchAll(/data-valor="jardin ([a-z-]+)"/g)].map(m => m[1]), ['al-final', 'esconder', 'ver'], 'las tres, en ese orden');
    assert.match(h, />al final</);
    assert.match(h, /ni en el modo todo/, 'esconder dice qué hace');
    assert.doesNotMatch(C.selectorFuera({ ...jardin, mundo: '' }), /mundo-agente-fuera/, 'sin mundo: sale en todos, nada que elegir');
    const pedidos = [];
    globalThis.fetch = async (url, o = {}) => {
        pedidos.push([o.method, String(url).replace(/^.*?(\/mundos)/, '$1'), JSON.parse(o.body ?? 'null')]);
        return { ok: true, status: 200, json: async () => ({ ok: true, mundos: [{ nombre: 'trabajo', color: '', horario: [], areas: [], rutas: [], etiquetas: [], color_propio: '' },
            { nombre: 'personal', color: '', horario: [], areas: [], rutas: [], etiquetas: [], color_propio: '' }], fuera: 'trabajo', tintas: [],
            agentes: [{ ...jardin, fuera_de_su_mundo: 'esconder' }] }) };
    };
    assert.equal(C.mundo.fueraDe('jardin'), 'al-final');
    assert.equal(await C.mundo.ponerFueraDeSuMundo('agente:jardin', 'esconder'), '');
    assert.deepEqual(pedidos, [['PUT', '/mundos/agentes/jardin', { fuera_de_su_mundo: 'esconder' }]], 'un pedido, con la clave de su carpeta');
    assert.equal(C.mundo.fueraDe('jardin'), 'esconder', 'lo que vuelve se aplica al tiro');
}

console.log('prueba:mundos ok');
