// Prueba de la semana del calendario (src/vistas/dashboard/semana.ts y clases.ts): qué semana se mira, qué es cada
// evento (una cita, un bloque propio, la rutina), cómo se cuenta la jornada, que es lo que dice el balance, y qué
// bloque toca en «ahora». Corre en Node, sin página: npm run prueba:semana
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
const { lunesDe, diasDe, queEs, vistos, cruces, balanceDia, perdido, bloqueActual } = require(salida);

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
const que = e => { const q = queEs(e); return `${q.tipo} ${q.clase}${q.pendiente ? ' pendiente' : ''}${q.organiza ? ' organiza' : ''}${q.rechazada ? ' rechazada' : ''}`; };
assert.equal(que(ev('09:00', '10:00', 'Daily', { asistentes: ['a@x.cl'] })), 'cita reunion', 'con invitados');
assert.equal(que(ev('09:00', '10:00', 'Llamada', { url: 'https://meet.google.com/x' })), 'cita reunion', 'con dónde conectarse');
assert.equal(que(ev('09:00', '11:00', 'Estrategia')), 'bloque estrategico', 'propio, por su título');
assert.equal(que(ev('09:00', '11:00', 'Pensar el deck')), 'bloque bloque', 'propio, sin clase');
assert.equal(que(ev('13:00', '14:00', 'Almuerzo')), 'rutina almuerzo', 'el almuerzo propio');
assert.equal(que(ev('12:00', '12:30', 'Correo y mensajes', { soloPlan: true, plan: { tipo: 'bloque', clase: 'correo' } })), 'bloque correo', 'del plan');
assert.equal(que(ev('10:00', '11:00', 'Kick off', { asistentes: ['a@x.cl'], plan: { tipo: 'reunion', estado: 'sin aceptar' } })), 'cita reunion pendiente', 'sin aceptar');
assert.equal(que(ev('10:00', '11:00', 'Demo', { asistentes: ['a@x.cl'], plan: { tipo: 'reunion', estado: 'la organizas' } })), 'cita reunion organiza', 'la organiza');
assert.equal(que(ev('17:00', '17:00', 'Cierre del día', { soloPlan: true, plan: { tipo: 'cierre' } })), 'rutina cierre', 'el cierre');
// lo que respondió a la invitación (del calendario) manda sobre el plan, que se escribió la noche anterior
const invitada = (respuesta, plan) => ev('10:00', '11:00', 'Comité', { asistentes: ['a@x.cl'], respuesta, ...(plan ? { plan } : {}) });
assert.equal(que(invitada('sin_responder')), 'cita reunion pendiente', 'sin responder: sin aceptar, aunque el plan no lo diga');
assert.equal(que(invitada('aceptada', { tipo: 'reunion', estado: 'sin aceptar' })), 'cita reunion', 'aceptada: ya no, aunque el plan lo diga');
assert.equal(que(invitada('rechazada')), 'cita reunion rechazada', 'rechazada');
assert.equal(que(invitada('rechazada', { tipo: 'reunion', estado: 'sin aceptar' })), 'cita reunion rechazada', 'rechazada, aunque el plan diga sin aceptar');
assert.equal(que(invitada('tentativa', { tipo: 'reunion', estado: 'tentativa' })), 'cita reunion pendiente', 'tentativa: lo que diga el plan');
assert.equal(que(invitada('tentativa')), 'cita reunion', 'tentativa sin plan: firme, como en la línea del día');
assert.equal(que(invitada('', { tipo: 'reunion', estado: 'sin aceptar' })), 'cita reunion pendiente', 'sin respuesta: lo del plan');

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

// 6. una cita rechazada no pisa a nadie, nadie la pisa y no suma a las citas; una sin responder es «sin aceptar»
{
    const estr = ev('09:30', '11:00', 'Estratégico: presupuesto', { soloPlan: true, plan: { tipo: 'bloque', clase: 'estrategico' } });
    const rechazada = ev('09:00', '10:30', 'Taller', { asistentes: ['a@x.cl'], respuesta: 'rechazada' });
    const aceptada = ev('10:00', '11:00', 'Comité', { asistentes: ['b@x.cl'], respuesta: 'aceptada' });
    const sinResponder = ev('15:00', '16:00', 'Presentación', { asistentes: ['c@x.cl'], respuesta: 'sin_responder' });
    const vs = vistos([rechazada, estr, aceptada, sinResponder]);
    const p = cruces(vs);
    assert.equal(p.get(rechazada.id), undefined, 'a la rechazada no la pisa nada');
    assert.deepEqual(p.get(aceptada.id), undefined, 'la rechazada no pisa a la aceptada');
    assert.deepEqual(p.get(estr.id), [{ titulo: 'Comité', cita: true }], 'al bloque lo pisa solo la aceptada');
    assert.equal(p.get(sinResponder.id), undefined, 'la sin responder, como la sin aceptar');
    // la aceptada 60 (10:00-11:00) y la sin responder 60; el bloque, 30 (9:30-10:00); la rechazada, nada
    assert.deepEqual(Object.fromEntries(balanceDia(DIA, vs)), { libre: 420, estrategico: 30, reunion: 120 });
    assert.deepEqual(perdido(DIA, vs, vs[1]), { citas: 60, bloques: 0 }, 'el bloque pierde solo lo de la aceptada');
}

// 7. el bloque que toca en «ahora»: el que contiene la hora (entre dos, el que empezó después), si no el próximo, y
// pasado todo, el último; una cita rechazada nunca: durante ella, lo que haya debajo o lo que viene
{
    const foco = ev('09:00', '11:00', 'Foco');
    const taller = ev('10:00', '13:00', 'Taller', { asistentes: ['a@x.cl'], respuesta: 'rechazada' });
    const comite = ev('12:00', '13:00', 'Comité', { asistentes: ['b@x.cl'], respuesta: 'sin_responder' });
    const tarde = ev('16:00', '17:00', 'Revisión', { asistentes: ['c@x.cl'], respuesta: 'rechazada' });
    const evs = [foco, taller, comite, tarde];
    const toca = hhmm => evs[bloqueActual(evs, ms(hhmm))]?.titulo ?? null;
    assert.equal(toca('09:30'), 'Foco', 'el que contiene la hora');
    assert.equal(toca('10:30'), 'Foco', 'sobre el bloque, la rechazada no lo corta');
    assert.equal(toca('11:30'), 'Comité', 'en la rechazada sola, lo que viene');
    assert.equal(toca('12:30'), 'Comité', 'la sin responder, sí');
    assert.equal(toca('16:30'), 'Comité', 'pasado todo (la última, rechazada), el último que vale');
    assert.equal(toca('08:00'), 'Foco', 'temprano, el próximo');
    assert.equal(bloqueActual([taller, tarde], ms('10:30')), -1, 'solo rechazadas: nada');
    assert.equal(bloqueActual([], ms('10:30')), -1, 'sin nada: nada');
    const daily = ev('09:30', '10:00', 'Daily', { asistentes: ['d@x.cl'], respuesta: 'aceptada' });
    assert.equal([foco, daily][bloqueActual([foco, daily], ms('09:45'))].titulo, 'Daily', 'entre dos, el que empezó después');
}

console.log('semana: bien');
