// Prueba del prototipo de «tareas › rutinas» (src/componentes/catalogo-rutinas.ts, /componentes#rutinas): cuándo vuelve
// a tocar cada cadencia, el estado que calcula la vista (atrasada, toca hoy, esta semana, al día, sin prueba definida),
// que el ✓ de marcar a mano esté solo donde no hay prueba, y el cuerpo (una sección por estado, al día plegada, el filtro
// de quién). Corre en Node: npm run prueba:rutinas
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const salida = path.join(mkdtempSync(path.join(tmpdir(), 'rutinas-')), 'rutinas.cjs');
await build({ entryPoints: [path.join(aqui, '..', 'src', 'componentes', 'catalogo-rutinas.ts')], bundle: true,
    platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const R = require(salida);
const { HOY, RUTINAS, toca, estado, domingo, cuerpo, filas, cadaTexto } = R;

const r = (cada, ultima, mas = {}) => ({ clave: 'x', nombre: 'X', cada, quien: { tipo: 'yo', nombre: 'tú' },
    prueba: { tipo: 'archivo', donde: 'x/' }, ultima, ...mas });

// 1. el día del prototipo es un jueves, y su domingo, el 29
assert.equal(new Date(`${HOY}T12:00:00Z`).getUTCDay(), 4);
assert.equal(domingo(HOY), '2026-11-29');

// 2. cuándo vuelve a tocar, por cadencia
assert.equal(toca(r({ tipo: 'habil' }, '2026-11-27')), '2026-11-30');       // del viernes, al lunes
assert.equal(toca(r({ tipo: 'semana', dia: 1 }, '2026-11-23')), '2026-11-30'); // el lunes siguiente
assert.equal(toca(r({ tipo: 'dias', n: 14 }, '2026-11-12')), '2026-11-26');
assert.equal(toca(r({ tipo: 'meses', n: 1 }, '2026-10-24')), '2026-11-24');
assert.equal(toca(r({ tipo: 'calendario', serie: 'x' }, '2026-11-19', { proxima: '2026-12-03' })), '2026-12-03');
assert.equal(toca(r({ tipo: 'dias', n: 7 }, null)), HOY);                     // nunca hecha: hoy

// 3. el estado contra hoy
assert.equal(estado(r({ tipo: 'semana', dia: 5 }, '2026-11-13')), 'atrasada');
assert.equal(estado(r({ tipo: 'dias', n: 14 }, '2026-11-12')), 'hoy');
assert.equal(estado(r({ tipo: 'semana', dia: 0 }, '2026-11-22')), 'semana');
assert.equal(estado(r({ tipo: 'semana', dia: 1 }, '2026-11-23')), 'aldia');
// lo de cada día, hecho hoy, está al día (que toque mañana no es «esta semana»)
assert.equal(estado(r({ tipo: 'habil' }, HOY)), 'aldia');
// sin prueba no se calcula, aunque tocara
assert.equal(estado(r({ tipo: 'semana', dia: 5 }, '2026-11-01', { prueba: undefined })), 'sinprueba');

// 4. las inventadas cubren los cinco estados, y las del inventario están (sin nombres de verdad)
{
    const por = e => RUTINAS.filter(x => estado(x) === e).map(x => x.clave);
    assert.deepEqual(por('atrasada'), ['horas', '1a1-carla', 'retro-metodo']);
    assert.deepEqual(por('hoy'), ['daily', 'lideres', '1a1-leo']);
    assert.deepEqual(por('semana'), ['plan-semana', 'diagnostico']);
    assert.deepEqual(por('sinprueba'), ['retro-dia', 'semanal', 'decisiones', 'trimestre']);
    assert.equal(por('aldia').length, 6);
    assert.equal(cadaTexto({ tipo: 'dias', n: 14 }), 'cada dos semanas');
}

// 5. marcar a mano solo donde no hay prueba; ver la prueba solo donde la hay
{
    const conPrueba = filas(RUTINAS.find(x => x.clave === 'plan-dia'));
    const sinPrueba = filas(RUTINAS.find(x => x.clave === 'semanal'));
    assert.doesNotMatch(conPrueba, /rutinas-marcar/);
    assert.match(conPrueba, /data-accion="rutinas-prueba"/);
    assert.match(sinPrueba, /data-accion="rutinas-marcar"/);
    assert.doesNotMatch(sinPrueba, /rutinas-prueba/);
    // debajo, tenue, la prueba (o por qué no tiene) y lo que la prepara
    assert.match(conPrueba, /prueba: el archivo del día en planes\/ · la prepara el periódico planear/);
    assert.match(sinPrueba, /sin prueba: falta decir con qué se sabe que se hizo/);
}

// 6. el cuerpo: una sección por estado, en su orden, al día plegada; el filtro de quién deja solo las suyas
{
    const h = cuerpo();
    assert.deepEqual([...h.matchAll(/class="grupo-rutinas" data-estado="([a-z]+)"/g)].map(m => m[1]),
        ['atrasada', 'hoy', 'semana', 'aldia', 'sinprueba']);
    const aldia = h.slice(h.indexOf('data-estado="aldia"'), h.indexOf('data-estado="sinprueba"'));
    assert.doesNotMatch(aldia, /class="item rutina"/);
    assert.match(cuerpo(RUTINAS, { plegadas: new Set(['aldia']) }), /data-estado="aldia">.*class="item rutina"/s);
    // de agentes son tres: la de al día queda en su sección plegada (con su cuenta), las otras dos a la vista
    const agentes = cuerpo(RUTINAS, { filtro: 'agente' });
    assert.equal((agentes.match(/class="item rutina" /g) ?? []).length, 2);
    assert.match(agentes, /data-id="rutinas:aldia"[^>]*>.*?<span class="item-sufijo tono-tenue">1<\/span>/s);
}

console.log('rutinas: ok');
