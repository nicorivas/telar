// De qué es cada cosa del calendario, para dibujarla y para contar las horas. Su tipo: una cita (con otras
// personas, que no se mueve sola), un bloque propio (tiempo que la persona se reservó para algo, y que puede mover)
// o la rutina (el almuerzo, un traslado, el cierre del día). Y su clase: la que dice el plan del día, o la que se
// deduce del título. Lo usan el calendario (el día y la semana, en plan.ts y semana.ts) y «ahora» (también el
// bloque que toca, `bloqueActual`).

import { normalizar } from '../../estilo';
import type { EventoCal } from './eventos';
import type { Plan } from './plan';

export type Clase = 'reunion' | 'estrategico' | 'comercial' | 'correo' | 'reserva' | 'almuerzo' | 'cierre' | 'personal'
    | 'traslado' | 'bloque';

export const NOMBRE: Record<Clase, string> = {
    reunion: 'reunión', estrategico: 'estratégico', comercial: 'comercial', correo: 'correo y mensajes', reserva: 'reserva',
    almuerzo: 'almuerzo', cierre: 'cierre', personal: 'personal', traslado: 'traslado', bloque: 'bloque',
};

/** Las clases que dice el título de un bloque propio: «Estratégico: …», «Comercial: …», «Correo y mensajes». */
function claseDelTitulo(titulo: string): Clase | undefined {
    const t = normalizar(titulo);
    for (const c of ['estrateg', 'comercial', 'correo', 'reserva', 'almuerzo', 'cierre', 'traslado'] as const)
        if (t.startsWith(c)) return c === 'estrateg' ? 'estrategico' : c;
    return undefined;
}

/** De qué clase es un bloque: lo que dice el plan (`clase`), o se deduce del tipo y del título
 *  («Estratégico: …», «Comercial: …», «Correo y mensajes», «Reserva»). Lo del calendario es reunión. */
export function claseDe(e: EventoCal): Clase {
    const p: Plan = e.plan ?? {};
    const dicha = String(p.clase ?? '').toLowerCase();
    if (['estrategico', 'comercial', 'correo', 'reserva', 'personal', 'cierre'].includes(dicha)) return dicha as Clase;
    if (!e.soloPlan && p.tipo !== 'bloque' && p.tipo !== 'almuerzo' && p.tipo !== 'cierre' && p.tipo !== 'traslado') return 'reunion';
    if (p.tipo === 'almuerzo') return 'almuerzo';
    if (p.tipo === 'cierre') return 'cierre';
    if (p.tipo === 'traslado') return 'traslado';
    if (p.estrategico) return 'estrategico';
    return claseDelTitulo(e.titulo) ?? (p.tipo === 'reunion' ? 'reunion' : 'bloque');
}

export type Tipo = 'cita' | 'bloque' | 'rutina';

/** Lo que es un evento en el calendario: su tipo, su clase, y de una cita si todavía no está aceptada, si la rechazó
 *  o si la organiza la persona (entonces la puede mover ella). Un evento del calendario sin nada del plan es una cita
 *  si tiene invitados o dónde conectarse; si no, es un bloque que la persona se puso a sí misma.
 *
 *  Lo que respondió a la invitación (`respuesta`, del calendario) manda sobre lo que dice el plan, que se escribió la
 *  noche anterior: sin responder es «sin aceptar» aunque el plan no lo diga, aceptada ya no lo es aunque el plan lo
 *  diga, y rechazada es rechazada (no pisa a nadie ni suma a las citas). Sin respuesta (un calendario que no la
 *  sabe, o una que organiza ella), lo del plan: «sin aceptar», «tentativa». */
export function queEs(e: EventoCal): { tipo: Tipo; clase: Clase; pendiente: boolean; organiza: boolean; rechazada: boolean } {
    const p: Plan = e.plan ?? {};
    const estado = normalizar(String(p.estado ?? ''));
    const respuesta = e.respuesta ?? '';
    const rechazada = respuesta === 'rechazada';
    const pendiente = !rechazada && (respuesta === 'sin_responder'
        || (respuesta !== 'aceptada' && /^(sin aceptar|sin responder|tentativa)/.test(estado)));
    const organiza = estado.startsWith('la organizas');
    let clase = claseDe(e);
    if (clase === 'reunion' && !e.soloPlan && !p.tipo && !e.asistentes.length && !e.url) clase = claseDelTitulo(e.titulo) ?? 'bloque';
    const tipo: Tipo = clase === 'reunion' ? 'cita' : ['almuerzo', 'cierre', 'traslado'].includes(clase) ? 'rutina' : 'bloque';
    return { tipo, clase, pendiente: tipo === 'cita' && pendiente, organiza: tipo === 'cita' && organiza, rechazada: tipo === 'cita' && rechazada };
}

/** Un evento con lo que es, para no preguntarlo dos veces. */
export type Visto = { e: EventoCal } & ReturnType<typeof queEs>;
export const vistos = (evs: EventoCal[]): Visto[] => evs.map(e => ({ e, ...queEs(e) }));

/** Lo que se cruza en un día: el bloque que tiene encima una cita aceptada (perdió ese tiempo), dos citas aceptadas a
 *  la misma hora, y dos bloques propios a la misma hora (el tiempo se reservó dos veces). La rutina y las citas sin
 *  aceptar o rechazadas no cuentan. Por cada uno (su id), con qué se cruza y si es una cita. */
export function cruces(vs: Visto[]): Map<string, { titulo: string; cita: boolean }[]> {
    const m = new Map<string, { titulo: string; cita: boolean }[]>();
    const firme = (v: Visto) => v.tipo === 'bloque' || (v.tipo === 'cita' && !v.pendiente && !v.rechazada);
    for (const a of vs) for (const b of vs) {
        if (a === b || a.e.inicio >= b.e.fin || b.e.inicio >= a.e.fin || !firme(a) || !firme(b)) continue;
        // a una cita solo la pisa otra cita: que un bloque propio caiga encima no le quita nada
        if (a.tipo === 'cita' && b.tipo !== 'cita') continue;
        m.set(a.e.id, [...(m.get(a.e.id) ?? []), { titulo: b.e.titulo, cita: b.tipo === 'cita' }]);
    }
    return m;
}

/** El bloque que toca, para «ahora» (ahora.ts): el que contiene la hora; si no hay, el próximo; si el día terminó, el
 *  último. Entre dos que se pisan, el que empezó más tarde (la reunión que corta un bloque propio). Una cita que la
 *  persona rechazó no es en lo que está (sigue en el calendario, y se puede elegir ahí): durante ella toca lo que haya
 *  debajo, o lo que viene. -1 si no hay nada que tocar. */
export function bloqueActual(evs: EventoCal[], ahora: number): number {
    const vale = evs.map((e, i) => [e, i] as const).filter(([e]) => !queEs(e).rechazada);
    const en = vale.filter(([e]) => e.inicio <= ahora && ahora < e.fin);
    if (en.length) return en.sort((a, b) => b[0].inicio - a[0].inicio)[0][1];
    const proximo = vale.find(([e]) => e.inicio > ahora);
    return proximo ? proximo[1] : vale.length ? vale[vale.length - 1][1] : -1;
}
