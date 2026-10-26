// Prueba de la semana del calendario (src/vistas/dashboard/semana.ts y clases.ts): qué semana se mira, qué es cada
// evento (una cita, un bloque propio, la rutina) y cómo se cuenta la jornada, que es lo que dice el balance. Corre en
// Node, sin página: npm run prueba:semana
import { build } from 'esbuild';
import { createRequire } from 'node:module';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const aqui = path.dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(path.join(tmpdir(), 'semana-'));
const entrada = path.join(dir, 'entrada.ts');
const src = path.join(aqui, '..', 'src', 'vistas', 'dashboard');
writeFileSync(entrada, `export * from ${JSON.stringify(path.join(src, 'semana.ts'))};\nexport * from ${JSON.stringify(path.join(src, 'clases.ts'))};\n`);
const salida = path.join(dir, 'semana.cjs');
await build({ entryPoints: [entrada], bundle: true, platform: 'node', format: 'cjs', outfile: salida, logLevel: 'warning' });
const { lunesDe, diasDe, queEs, vistos, cruces, balanceDia, perdido } = require(salida);

// 1. la semana de un día: la suya de lunes a viernes; el sábado y el domingo, la que viene
assert.equal(lunesDe('2026-10-22'), '2026-10-19', 'jueves');
assert.equal(lunesDe('2026-10-19'), '2026-10-19', 'lunes');
assert.equal(lunesDe('2026-10-24'), '2026-10-26', 'sábado');
assert.equal(lunesDe('2026-10-25'), '2026-10-26', 'domingo');
assert.deepEqual(diasDe('2026-10-26'), ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30']);
assert.equal(diasDe('2026-10-26', -1)[0], '2026-10-19', 'la anterior');

// 2. qué es cada evento
const DIA = '2026-10-22';
const ms = hhmm => Date.parse(`${DIA}T${hhmm}:00`);
let n = 0;
const ev = (ini, fin, titulo, o = {}) => ({ id: `e${++n}`, titulo, inicio: ms(ini), fin: ms(fin), lugar: '', url: '',
    asistentes: [], soloPlan: false, ...o });
const que = e => { const q = queEs(e); return `${q.tipo} ${q.clase}${q.pendiente ? ' pendiente' : ''}${q.organiza ? ' organiza' : ''}`; };
assert.equal(que(ev('09:00', '10:00', 'Daily', { asistentes: ['a@x.cl'] })), 'cita reunion', 'con invitados');
assert.equal(que(ev('09:00', '10:00', 'Llamada', { url: 'https://meet.google.com/x' })), 'cita reunion', 'con dónde conectarse');
assert.equal(que(ev('09:00', '11:00', 'Estrategia')), 'bloque estrategico', 'propio, por su título');
assert.equal(que(ev('09:00', '11:00', 'Pensar el deck')), 'bloque bloque', 'propio, sin clase');
assert.equal(que(ev('13:00', '14:00', 'Almuerzo')), 'rutina almuerzo', 'el almuerzo propio');
assert.equal(que(ev('12:00', '12:30', 'Correo y mensajes', { soloPlan: true, plan: { tipo: 'bloque', clase: 'correo' } })), 'bloque correo', 'del plan');
assert.equal(que(ev('10:00', '11:00', 'Kick off', { asistentes: ['a@x.cl'], plan: { tipo: 'reunion', estado: 'sin aceptar' } })), 'cita reunion pendiente', 'sin aceptar');
assert.equal(que(ev('10:00', '11:00', 'Demo', { asistentes: ['a@x.cl'], plan: { tipo: 'reunion', estado: 'la organizas' } })), 'cita reunion organiza', 'la organiza');
assert.equal(que(ev('17:00', '17:00', 'Cierre del día', { soloPlan: true, plan: { tipo: 'cierre' } })), 'rutina cierre', 'el cierre');

// 3. la jornada (08:30 a 18:00, 570 min): una cita aceptada se come el bloque que pisa, una sin aceptar no
{
    const estr = ev('09:30', '11:00', 'Estratégico: presupuesto', { soloPlan: true, plan: { tipo: 'bloque', clase: 'estrategico' } });
    const cita = ev('09:00', '10:00', 'Daily', { asistentes: ['a@x.cl'] });
    const porAceptar = ev('10:30', '11:30', 'Kick off', { asistentes: ['a@x.cl'], plan: { tipo: 'reunion', estado: 'sin aceptar' } });
    const almuerzo = ev('13:00', '14:00', 'Almuerzo', { soloPlan: true, plan: { tipo: 'almuerzo' } });
    const vs = vistos([cita, estr, porAceptar, almuerzo]);
    const m = Object.fromEntries(balanceDia(DIA, vs));
    // la cita, 60 (09:00-10:00) y la sin aceptar lo que no tapa el bloque, 30 (11:00-11:30); el bloque, 60 (10:00-11:00)
    assert.deepEqual(m, { reunion: 90, estrategico: 60, rutina: 60, libre: 360 });
    assert.equal(Object.values(m).reduce((a, b) => a + b, 0), 570, 'la jornada entera');
    const p = cruces(vs);
    assert.deepEqual(p.get(estr.id), [{ titulo: 'Daily', cita: true }], 'al bloque lo pisa la cita aceptada');
    assert.equal(p.get(porAceptar.id), undefined, 'la sin aceptar no pisa ni la pisan');
    assert.equal(p.get(cita.id), undefined, 'a la cita no la pisa un bloque');
    assert.deepEqual(perdido(DIA, vs, vs[1]), { citas: 30, bloques: 0 }, 'el bloque pierde la media hora de la cita');
}

// 4. dos citas aceptadas a la misma hora: las dos quedan pisadas
{
    const a = ev('11:00', '12:00', 'Demo', { asistentes: ['a@x.cl'] }), b = ev('11:30', '12:30', 'Co-diseño', { asistentes: ['b@x.cl'] });
    const p = cruces(vistos([a, b]));
    assert.deepEqual([p.get(a.id), p.get(b.id)], [[{ titulo: 'Co-diseño', cita: true }], [{ titulo: 'Demo', cita: true }]]);
}

// 5. dos bloques propios a la misma hora (el plan reservó encima de lo que la persona se puso): se cruzan, y el que
// empieza después se queda con el tramo; lo que pierde el otro no es de una cita
{
    const propio = ev('09:45', '12:00', 'Estrategia');
    const plan = ev('11:00', '12:00', 'Reserva', { soloPlan: true, plan: { tipo: 'bloque', clase: 'reserva' } });
    const vs = vistos([propio, plan]);
    assert.deepEqual(cruces(vs).get(propio.id), [{ titulo: 'Reserva', cita: false }]);
    assert.deepEqual(perdido(DIA, vs, vs[0]), { citas: 0, bloques: 60 });
    assert.deepEqual(Object.fromEntries(balanceDia(DIA, vs)), { libre: 435, estrategico: 75, reserva: 60 });
}

console.log('semana: bien');
