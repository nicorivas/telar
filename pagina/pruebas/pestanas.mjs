// Prueba del orden de las pestañas del dashboard (src/vistas/dashboard/orden-pestanas.ts): lo que nombra
// `[dashboard] orden` va en ese orden; una de fábrica que no nombra («te esperan», que llegó después), tras la que la
// precede en el orden de siempre; las de los módulos y los proveedores que no nombra, al final; sin orden, el de siempre.
// Corre en Node: npm run prueba:pestanas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'pestanas-')), 'pestanas.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'vistas', 'dashboard', 'orden-pestanas.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { ordenarPestanas, delModo } = require(salida);

// el orden de siempre (panel.ts, todasLasPestanas): las fijas, los bloques y las de los proveedores, y otra vez fijas
const FABRICA = ['ahora', 'esperas', 'revisar', 'bloque:correo', 'bloque:productos', 'bloque:tablero', 'pestana:leer',
    'proyectos', 'calendario'];
const ordenar = orden => ordenarPestanas(FABRICA, x => x, orden);

// 1. sin orden, el de siempre
assert.deepEqual(ordenar([]), FABRICA);

// 2. lo que se nombra, en ese orden; «te esperan», que no se nombra, tras «ahora» (la que la precede de fábrica), y no
// al final; los módulos que no se nombran, al final, en su orden. «plan» (la pestaña que se sacó el 18-nov-2026) sigue en
// órdenes de antes: no cuenta
assert.deepEqual(ordenar(['ahora', 'revisar', 'bloque:correo', 'calendario', 'pestana:leer', 'proyectos', 'plan']),
    ['ahora', 'esperas', 'revisar', 'bloque:correo', 'calendario', 'pestana:leer', 'proyectos', 'bloque:productos', 'bloque:tablero']);

// 3. las nombradas guardan su orden entre ellas; una fija que no se nombra se mete junto a su vecina de fábrica, aunque
// quede entre dos nombradas («proyectos» y «calendario» tras «tareas»)
assert.deepEqual(ordenar(['revisar', 'esperas', 'ahora']),
    ['revisar', 'proyectos', 'calendario', 'esperas', 'ahora', 'bloque:correo', 'bloque:productos', 'bloque:tablero', 'pestana:leer']);

// 4. tras la que la precede, esté donde esté; si esa tampoco se nombra, tras la anterior que sí; si no hay ninguna, primera
{
    const l = ordenar(['revisar', 'ahora']);
    assert.deepEqual(l.slice(0, 1), ['revisar']);
    assert.equal(l.indexOf('esperas'), l.indexOf('ahora') + 1);
}
assert.deepEqual(ordenar(['proyectos']).slice(0, 4), ['ahora', 'esperas', 'revisar', 'proyectos']);
// una fija que no se nombra tras un bloque nombrado: después de él
assert.deepEqual(ordenar(['bloque:correo', 'calendario']), ['ahora', 'esperas', 'revisar', 'bloque:correo', 'proyectos',
    'calendario', 'bloque:productos', 'bloque:tablero', 'pestana:leer']);

// 5. lo que se nombra y no existe (una pestaña que ya no está), o dos veces, no cuenta
assert.deepEqual(ordenar(['ahora', 'periodicos', 'ahora', 'revisar']).slice(0, 3), ['ahora', 'esperas', 'revisar']);
assert.equal(ordenar(['ahora', 'ahora']).length, FABRICA.length);

// 6. «táctica» (panel.ts) es la primera de fábrica: con un `[dashboard] orden` que no la nombra, va primera, porque no la
// precede ninguna; y si se la nombra, donde se la ponga
{
    const conTactica = ['tactica', ...FABRICA];
    const orden = ['ahora', 'revisar', 'bloque:correo', 'calendario', 'pestana:leer', 'proyectos', 'plan'];
    assert.deepEqual(ordenarPestanas(conTactica, x => x, orden).slice(0, 3), ['tactica', 'ahora', 'esperas']);
    const l = ordenarPestanas(conTactica, x => x, ['ahora', 'tactica']);
    assert.ok(l.indexOf('tactica') > l.indexOf('ahora'), 'nombrada tras «ahora», va después');
}

// 7. un orden de antes que nombra pestañas que se sacaron («estrategia», «plan»): no cuentan, y las demás quedan en el
// suyo
{
    const orden = ['estrategia', 'ahora', 'revisar', 'bloque:correo', 'calendario', 'pestana:leer', 'proyectos', 'plan'];
    assert.deepEqual(ordenarPestanas(['tactica', ...FABRICA], x => x, orden).slice(0, 3), ['tactica', 'ahora', 'esperas']);
    assert.ok(!ordenarPestanas(['tactica', ...FABRICA], x => x, orden).includes('estrategia'));
}

// las de un modo (`filas`): las que nombra, en su orden («tareas» es «revisar»), sin las que no hay; null, todas
assert.deepEqual(delModo(FABRICA, x => x, ['calendario', 'tareas', 'estrategia', 'calendario', 'plan', 'bloque:tablero']), ['calendario', 'revisar', 'bloque:tablero']);
assert.deepEqual(delModo(FABRICA, x => x, null), FABRICA);
assert.deepEqual(delModo(FABRICA, x => x, []), []);

console.log('pestanas: ok');
