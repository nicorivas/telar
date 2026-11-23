// Prueba de qué agentes residentes se ven en un modo (src/web/modos-agentes.ts): lo que dice `agentes` (vacío, todos;
// «-», ninguno; si no, los que nombra) y lo que deja un clic en la grilla de ⚙ modos. Un modo sin la clave se ve igual
// que antes de que existiera: con todos. Y sobre cuál se arma un modo nuevo (src/web/modos.ts, `baseDeNuevo`). Y qué
// pestañas de DASHBOARD ve un modo (src/web/modos-pestanas.ts): lo que dice `filas`, lo que deja un clic en su fila de
// ⚙ modos (y cuándo vuelve a lo heredado), y las que quedan en un mundo: la unión de las de sus modos.
// Corre en Node: npm run prueba:modos
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'modos-')), 'modos-agentes.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'modos-agentes.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { seVe, alternar, elegidos, carpeta, NINGUNO } = require(salida);
const salidaModos = path.join(path.dirname(salida), 'modos.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'modos.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salidaModos, logLevel: 'warning' });
const modos = require(salidaModos);

// las secciones de la barra: la clave de cada agente es su dirección
const TODOS = ['agente:vigia', 'agente:cartero', 'agente:archivista'];

// 1. sin la clave (o vacía, o *), todos: como antes
for (const v of [undefined, '', '  ', '*', 'vigia, *']) {
    assert.equal(elegidos(v), null, String(v));
    for (const a of TODOS) assert.ok(seVe(v, a), `${v} · ${a}`);
}

// 2. los que nombra, por su carpeta o su dirección; los demás no
assert.ok(seVe('vigia, cartero', 'agente:vigia'));
assert.ok(seVe('vigia, cartero', 'cartero'));
assert.ok(!seVe('vigia, cartero', 'agente:archivista'));
assert.ok(seVe('agente:vigia', 'agente:vigia'));
assert.equal(carpeta('agente:vigia'), 'vigia');

// 3. «-»: ninguno
assert.deepEqual([...elegidos(NINGUNO)], []);
for (const a of TODOS) assert.ok(!seVe(NINGUNO, a));

// 4. un clic: apagar uno con todos deja nombrados los demás, en el orden de la barra
assert.equal(alternar('', 'agente:cartero', TODOS), 'vigia, archivista');
// prender el que faltaba vuelve a «todos» (vacío: los que vengan también se ven)
assert.equal(alternar('vigia, archivista', 'agente:cartero', TODOS), '');
// apagar el último deja «ninguno», y prender uno desde ninguno lo nombra solo a él
assert.equal(alternar('vigia', 'agente:vigia', TODOS), NINGUNO);
assert.equal(alternar(NINGUNO, 'agente:archivista', TODOS), 'archivista');
// lo que nombraba y ya no está (un agente que se borró) se va al guardar
assert.equal(alternar('vigia, viejo', 'agente:cartero', TODOS), 'vigia, cartero');

// 5. sin agentes, nada que elegir: todos
assert.equal(alternar('', 'agente:vigia', []), '');

// 6. «nuevo modo…» se arma sobre la actitud del puesto: hecho en estrategia o en foco, sobre ella; en táctica, sin
// base (es la de siempre); en uno propio, sobre la base de ese. Si se llama como uno de fábrica, ninguna: no la lleva
{
    const de = clave => modos.lista().find(m => m.clave === clave);
    assert.equal(modos.baseDeNuevo('revision', de('estrategia')), 'estrategia');
    assert.equal(modos.baseDeNuevo('lectura', de('foco')), 'foco');
    assert.equal(modos.baseDeNuevo('lectura', de('tactica')), '');
    const propio = { clave: 'casa', nombre: 'casa', base: 'estrategia', valores: {}, de_fabrica: false, cambiado: true };
    assert.equal(modos.baseDeNuevo('casa-2', propio), 'estrategia');
    assert.equal(modos.baseDeNuevo('foco', de('estrategia')), '');
    assert.equal(modos.baseDeNuevo('estandar', de('estrategia')), '');
}

// 7. las pestañas de un modo (`filas`): las que nombra, en su orden («tareas» es «revisar»); `*` o nada, todas
{
    const salidaFilas = path.join(path.dirname(salida), 'modos-pestanas.cjs');
    await build({ entryPoints: [path.join(aqui, '..', 'src', 'web', 'modos-pestanas.ts')], bundle: true,
        platform: 'node', format: 'cjs', outfile: salidaFilas, logLevel: 'warning' });
    const f = require(salidaFilas);
    // las que hay, en el orden de ⚙ pestañas
    const HAY = ['todo', 'tactica', 'ahora', 'esperas', 'revisar', 'bloque:correo', 'proyectos', 'calendario'];
    const FABRICA = 'tactica, calendario';

    assert.deepEqual(f.elegidas('calendario , tactica,calendario'), ['calendario', 'tactica']);
    assert.deepEqual(f.elegidas('tareas, ahora'), ['revisar', 'ahora']);
    for (const v of ['*', '', undefined, 'ahora, *']) assert.equal(f.elegidas(v), null, String(v));
    assert.ok(f.ve('tareas', 'revisar') && f.ve('*', 'bloque:correo') && !f.ve(FABRICA, 'ahora'));

    // un clic en una que no ve: entra tras la que la precede en ⚙ pestañas («ahora», tras «tactica»), y las demás quedan
    // en el orden del modo
    assert.deepEqual(f.alternar(FABRICA, HAY, 'ahora', FABRICA), { filas: 'tactica, ahora, calendario', error: '' });
    assert.deepEqual(f.alternar('calendario, tactica', HAY, 'ahora', FABRICA), { filas: 'calendario, tactica, ahora', error: '' },
        'el orden del modo se respeta');
    // sin ninguna antes que ella entre las del modo, primera; y si así queda igual a lo de fábrica, se quita la línea
    assert.equal(f.alternar('calendario', HAY, 'tactica', FABRICA).filas, null);
    assert.deepEqual(f.alternar('proyectos', HAY, 'ahora', FABRICA).filas, 'ahora, proyectos');
    // quitar una: las demás en su orden; si queda igual a lo heredado, null (sin la línea: vuelve a lo de fábrica o de
    // su base)
    assert.deepEqual(f.alternar('tactica, ahora, calendario', HAY, 'ahora', FABRICA), { filas: null, error: '' });
    assert.deepEqual(f.alternar(FABRICA, HAY, 'calendario', FABRICA), { filas: 'tactica', error: '' });
    // la última no se quita: un modo ve al menos una
    const ultima = f.alternar('calendario', HAY, 'calendario', FABRICA);
    assert.equal(ultima.error, 'un modo ve al menos una pestaña');
    // con todas, un clic quita esa y nombra las demás, en el orden de ⚙ pestañas
    assert.equal(f.alternar('*', HAY, 'todo', FABRICA).filas, HAY.slice(1).join(', '));
    // marcarlas todas es `*` (también las que vengan); y si lo heredado ya era todas (el modo todo), sin la línea
    assert.equal(f.alternar(HAY.slice(1).join(', '), HAY, 'todo', FABRICA).filas, '*');
    assert.equal(f.alternar(HAY.slice(1).join(', '), HAY, 'todo', '*').filas, null);
    // lo que nombraba y hoy no hay (un módulo que se desinstaló) se conserva
    assert.equal(f.alternar('bloque:tablero', HAY, 'proyectos', 'proyectos').filas, 'proyectos, bloque:tablero');
    // una pestaña que se sacó del dashboard (estrategia, el plan) no: no cuenta, y escribir la fila la quita
    assert.deepEqual(f.elegidas('estrategia, proyectos, plan, bloque:tablero'), ['proyectos', 'bloque:tablero']);
    assert.equal(f.elegidas('estrategia'), null, 'solo retiradas: todas, como sin la línea');
    assert.equal(f.alternar('estrategia, bloque:registro', HAY, 'proyectos', 'proyectos, bloque:tablero, bloque:registro').filas,
        'proyectos, bloque:registro');
    // «todas»: `*`, o sin la línea si lo heredado ya es todas
    assert.deepEqual(f.todas(FABRICA), { filas: '*', error: '' });
    assert.deepEqual(f.todas('*'), { filas: null, error: '' });

    // las de un mundo: la unión de las de sus modos, en el orden de ⚙ pestañas y solo las que hay (sin las ocultas); si
    // un modo las ve todas, todas (null)
    assert.deepEqual(f.delMundo([FABRICA, 'estrategia, proyectos, bloque:tablero'], HAY), ['tactica', 'proyectos', 'calendario']);
    assert.deepEqual(f.delMundo([FABRICA, 'calendario, ahora'], HAY.filter(x => x !== 'ahora')), ['tactica', 'calendario'], 'la oculta no');
    assert.equal(f.delMundo([FABRICA, '*'], HAY), null);
    assert.deepEqual(f.delMundo([], HAY), []);

    // cada pestaña con su ícono: las fijas el suyo, un bloque el de los módulos (el correo, el suyo), un proveedor lectura
    for (const k of HAY) assert.ok(f.icono(k), k);
    assert.notEqual(f.icono('bloque:gantt'), f.icono('pestana:leer'));
    assert.equal(f.icono('tareas'), f.icono('revisar'));
}

console.log('prueba:modos ok');
