// Los eventos de un día para el calendario: los del calendario de la persona cruzados con lo que dice el plan del
// día (un bloque del plan que no está en el calendario es un evento más), sus notas, y cómo se reparten en carriles
// los que se pisan. Lo usan el día y la semana del calendario (plan.ts, semana.ts) y «ahora».

import type * as cli from '../../cli';
import type { Dia } from './dia';
import type { Plan } from './plan';

/** Lo que dura un evento sin fin declarado, en minutos. */
const SIN_FIN = 30;

/** Un evento del calendario: del calendario de la persona, o un bloque que propuso el plan. */
export interface EventoCal {
    id: string; titulo: string; inicio: number; fin: number; lugar: string; url: string; asistentes: string[];
    /** lo que el plan dice de este evento, o el bloque mismo si no está en el calendario */
    plan?: Plan;
    /** un bloque del plan que no está en el calendario */
    soloPlan: boolean;
}

function aMs(fecha: string, hhmm: string): number {
    return Date.parse(`${fecha}T${hhmm.length === 5 ? hhmm : hhmm.slice(0, 5)}:00`);
}

function normal(s: string): string {
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function parecidos(a: string, b: string): boolean {
    const x = new Set(normal(a).split(' ').filter(w => w.length > 3));
    const y = normal(b).split(' ').filter(w => w.length > 3);
    return y.some(w => x.has(w));
}

/** Los eventos del día con lo que el plan dice de cada uno. Un ítem del plan se pega al evento que
 *  empieza a la misma hora (±10 min) y comparte alguna palabra con su título; si no hay, es un bloque
 *  propio del plan y se dibuja aparte. */
export function eventosDelDia(d: Dia, plan?: Plan): EventoCal[] {
    const evs: EventoCal[] = (d.agenda ?? []).filter(e => e.cuando && !e.todo_el_dia).map(e => {
        const ini = Date.parse(e.cuando ?? '');
        const fin = e.fin ? Date.parse(e.fin) : NaN;
        return { id: e.id || `${e.cuando}:${e.texto}`, titulo: e.texto, inicio: ini, fin: Number.isNaN(fin) ? ini + SIN_FIN * 60000 : fin,
            lugar: e.lugar ?? '', url: e.url ?? '', asistentes: e.asistentes ?? [], soloPlan: false };
    });
    for (const x of (plan?.agenda ?? []) as Plan[]) {
        if (!x.inicio) continue;
        const ini = aMs(d.fecha, String(x.inicio));
        if (Number.isNaN(ini)) continue;
        const par = (x.evento ? evs.find(e => e.id === x.evento && !e.plan) : undefined)
            ?? evs.find(e => !e.plan && !e.soloPlan && Math.abs(e.inicio - ini) <= 10 * 60000 && parecidos(e.titulo, String(x.titulo ?? '')));
        if (par) { par.plan = x; continue; }
        const fin = x.fin ? aMs(d.fecha, String(x.fin)) : NaN;
        evs.push({ id: `plan:${x.inicio}:${x.titulo}`, titulo: String(x.titulo ?? ''), inicio: ini,
            fin: Number.isNaN(fin) ? ini + SIN_FIN * 60000 : fin, lugar: '', url: '', asistentes: [], plan: x, soloPlan: true });
    }
    return evs.sort((a, b) => a.inicio - b.inicio || a.fin - b.fin);
}

/** Las notas de un evento: por su id, o por hora y título si el id cambió. */
export function notasDe(e: EventoCal, notas?: cli.JsonNotas): cli.JsonNota[] {
    const ev = notas?.eventos ?? {};
    if (ev[e.id]) return ev[e.id].notas;
    const hm = new Date(e.inicio).toTimeString().slice(0, 5);
    const otro = Object.values(ev).find(x => x.inicio === hm && x.titulo && parecidos(x.titulo, e.titulo));
    return otro?.notas ?? [];
}

/** Carriles: eventos que se pisan van lado a lado. */
export function carriles(evs: EventoCal[]): Map<string, [number, number]> {
    const salida = new Map<string, [number, number]>();
    let grupo: EventoCal[] = [];
    let finGrupo = -Infinity;
    const cerrar = () => {
        const fines: number[] = [];
        const de = new Map<string, number>();
        for (const e of grupo) {
            let k = fines.findIndex(f => f <= e.inicio);
            if (k < 0) { k = fines.length; fines.push(0); }
            fines[k] = e.fin;
            de.set(e.id, k);
        }
        for (const e of grupo) salida.set(e.id, [de.get(e.id) ?? 0, fines.length]);
        grupo = [];
        finGrupo = -Infinity;
    };
    for (const e of evs) {
        if (grupo.length && e.inicio >= finGrupo) cerrar();
        grupo.push(e);
        finGrupo = Math.max(finGrupo, e.fin);
    }
    if (grupo.length) cerrar();
    return salida;
}
