// Los gestos de las piezas: girar, girar siempre (rueda), brotar del centro, latir, saltar de tinta. Nunca se funde:
// los cambios de color son de golpe y las apariciones, por tamaño con rebote. Cada pieza tiene el suyo (`GESTOS`).

import { TAU, backOut, hash, lim, pop } from './azar';
import { type Forma, type Pieza, REVELA, SIMETRIA } from './piezas';

export type Gesto = 'giro' | 'rueda' | 'brote' | 'latido' | 'salto' | 'quieta';

/** El gesto de cada pieza (el elegido el 31-oct-2026). */
export const GESTOS: Record<Forma, Gesto> = {
    anillo: 'latido', aro: 'latido', dobleAnillo: 'brote', disco: 'latido', puntos8: 'brote', puntos12: 'brote', puntos4: 'brote',
    cruz: 'giro', cruzGruesa: 'giro', equis: 'giro', asterisco: 'brote', romboPixel: 'brote', damero: 'brote', cruzPixel: 'brote',
    rombos4: 'giro', rombos8: 'giro', triangulo: 'giro', cuartos: 'rueda', punto: 'salto', anilloChico: 'latido', romboChico: 'giro',
};

/** Cuántos se mueven y cómo: `actividad` (la fracción que hace su gesto en cada período), cada cuánto (`periodo`, s),
 *  cuánto dura el gesto (s), la probabilidad de saltar de tinta y las vueltas por segundo de la rueda. */
export interface Vida { actividad: number; periodo: number; duracion: number; saltos: number; rueda: number; gestos?: Partial<Record<Forma, Gesto>> }

/** Brotar: las piezas que se arman por partes avanzan su `u`; las demás crecen enteras. */
export function revelar(z: Pieza, u: number): void {
    if (REVELA.has(z.k)) z.u = Math.min(z.u ?? 1, u);
    else z.s = (z.s ?? 1) * pop(u);
}

/** Latir: encoger de golpe hasta `min` y volver con rebote. */
export function latido(z: Pieza, u: number, min = 0): void {
    z.s = (z.s ?? 1) * (u < .2 ? 1 - (1 - min) * u / .2 : min + (1 - min) * pop((u - .2) / .8));
}

/** La pieza `z0` en el punto `u` (0 a 1; negativo: sin gesto ahora) de su gesto, a los `tau` segundos. */
export function gesto(z0: Pieza, modo: Gesto, u: number, tau: number, nT: number, v: Vida, semilla: number): Pieza {
    const z = { ...z0 };
    if (modo === 'rueda') z.rot = (z.rot || 0) + tau * v.rueda * TAU * (semilla & 1 ? 1 : -1);
    if (u >= 0) {
        if (modo === 'giro') z.rot = (z.rot || 0) + (SIMETRIA[z.k] ?? TAU / 4) * backOut(u, 1.2);
        else if (modo === 'brote') revelar(z, u);
        else if (modo === 'latido') latido(z, u);
        else if (modo === 'salto' && u > .08 && u < .92 && nT > 1) z.t = (z.t + 1 + (semilla % (nT - 1))) % nT;
    }
    return z;
}

/** Si a los `tau` segundos el glifo de `semilla` está haciendo su gesto: en qué punto (`u`) y en cuál de sus vueltas. */
function eventoDe(semilla: number, tau: number, v: Vida): { u: number; k: number } | null {
    if (v.actividad <= 0) return null;
    const per = v.periodo, tt = tau + hash(semilla, 7) * per, k = Math.floor(tt / per);
    if (hash(semilla, k, 91) >= v.actividad) return null;
    const u = (tt - k * per) / v.duracion;
    return u < 1 ? { u, k } : null;
}

/** Las piezas de un glifo a los `tau` segundos: cada una con su gesto, en cascada; `nacer` (0 a 1), mientras brota
 *  entero (al cambiar de escala). Sin nada que hacer, las mismas piezas, sin copiar. */
export function animar(piezas: Pieza[], semilla: number, tau: number, v: Vida, nT: number, nacer: number | null = null): Pieza[] {
    const n = piezas.length, gestos = { ...GESTOS, ...v.gestos };
    const ev = eventoDe(semilla, tau, v);
    const rueda = piezas.some(z => gestos[z.k] === 'rueda');
    if (nacer == null && !ev && !rueda) return piezas;
    const salta = !!ev && nT > 1 && ev.u > .1 && ev.u < .9 && hash(semilla, ev.k, 55) < v.saltos;
    return piezas.map((z0, i) => {
        const z = gesto(z0, gestos[z0.k], ev ? lim((ev.u - i * .1) / .8, 0, 1) : -1, tau, nT, v, semilla + i);
        if (salta) z.t = (z.t + 1 + ((semilla >>> 3) % (nT - 1))) % nT;
        if (nacer != null) {
            const j = n - 1 - i, span = Math.max(.001, 1 - .18 * (n - 1));
            revelar(z, lim((nacer - j * .18) / span, 0, 1));
        }
        return z;
    });
}
