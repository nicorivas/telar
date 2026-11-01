// El glifo de un hilo: calculado de su nombre (el mismo nombre, siempre el mismo glifo), y su estado encima. La forma
// dice qué hilo es; el movimiento y el brillo, cómo está: trabajando gira de a 45° con rebote, te espera es un anillo de
// puntos amarillos que se llena en cadena, terminó es un punto verde en la esquina, lo ya visto va tenue, y sin
// atención queda solo su contorno.

import { TAU, backOut, hashTexto, rng } from './azar';
import { revelar } from './gestos';
import { type Impresion, type Mezcla, PALETAS, type Paleta, pintarGlifo } from './impresion';
import { type Pieza, glifo } from './piezas';

export interface ParamHilo { paleta: Paleta; capas: number; variedad: number; mezcla: Mezcla; desregistro: number; grano: number }
/** Lo elegido el 31-oct-2026: Mocha, color por nombre, tres piezas de tintas libres, sin desregistro ni grano. */
export const HILO: ParamHilo = { paleta: 'mocha', capas: 3, variedad: 1, mezcla: 'luz', desregistro: 0, grano: 0 };

export interface ParamEstados { trabajando: 'giro' | 'armado'; espera: 'cadena' | 'parpadeo'; tenue: number; ritmo: number }
export const ESTADOS: ParamEstados = { trabajando: 'giro', espera: 'cadena', tenue: .3, ritmo: 1.5 };

/** Los estados que se dibujan: los de la atención de telar, con «terminó» partido en sin ver y ya visto. */
export type Estado = 'trabajando' | 'espera' | 'termino' | 'visto' | 'ninguna';
/** Los que se mueven: los demás se pintan una vez. */
export const ANIMADOS = new Set<Estado>(['trabajando', 'espera']);

/** Los colores de estado de telar, después de las tintas de la paleta: azul, amarillo, verde, tenue. */
const EXTRA = ['#89b4fa', '#f9e2af', '#a6e3a1', '#6c7086'];

const cache = new Map<string, Pieza[]>();
/** Las piezas del glifo de un nombre. */
export function glifoHilo(nombre: string, p: ParamHilo = HILO): Pieza[] {
    const llave = `${p.paleta}|${p.capas}|${p.variedad}|${nombre}`;
    let piezas = cache.get(llave);
    if (!piezas) {
        const nT = PALETAS[p.paleta].length, s = hashTexto(nombre), r = rng(s ^ 0x9e37);
        piezas = glifo(s, .3 + r() * .7, s % nT, [...Array(nT).keys()], p.capas, p.variedad);
        cache.set(llave, piezas);
    }
    return piezas;
}

/** Las piezas con el estado encima, a los `tau` segundos. */
export function conEstado(piezas: Pieza[], estado: Estado, tau: number, q: ParamEstados, nT: number): Pieza[] {
    const fase = tau / q.ritmo;
    const out = piezas.map(z => ({ ...z }));
    const AM = nT + 1, VE = nT + 2, TE = nT + 3;
    if (estado === 'trabajando') {
        if (q.trabajando === 'giro') {
            const k = Math.floor(fase), f = fase - k, ang = (k + backOut(Math.min(1, f * 2.5), 1.2)) * TAU / 8;
            out.forEach((z, i) => { if (i > 0 || out.length === 1) z.rot = (z.rot || 0) + ang * (i % 2 ? 1 : -1); });
        } else {
            const n = out.length, L = n * .8 + 1.8, u = fase % L;
            if (u > n * .8 + 1) return [];
            out.forEach((z, i) => revelar(z, Math.min(1, Math.max(0, u - i * .8))));
        }
    } else if (estado === 'espera') {
        if (q.espera === 'cadena') out.push({ k: 'puntos12', t: AM, s: 1.22, u: Math.min(1, fase % 1.4) });
        else if (fase % 1 < .5) out.push({ k: 'puntos12', t: AM, s: 1.22 });
    } else if (estado === 'termino') {
        out.push({ k: 'punto', t: VE, dx: .95, dy: -.95, s: 1.2 });
    } else if (estado === 'visto') {
        out.forEach(z => { z.a = q.tenue; });
    } else {
        return [{ ...out[0], t: TE, a: .9 }];
    }
    return out;
}

/** Cómo se imprime un glifo de hilo de `tam` px. */
export function impresionHilo(p: ParamHilo, tam: number): Impresion {
    return { tintas: [...PALETAS[p.paleta], ...EXTRA], fondo: '', mezcla: p.mezcla, intensidad: 1, desregistro: p.desregistro / 100 * tam,
        grano: p.grano, papel: 0 };
}

/** Pinta en `cv` el glifo del hilo `nombre` en su `estado`, de `tam` px, a los `tau` segundos. */
export function pintarHilo(cv: HTMLCanvasElement, tam: number, nombre: string, estado: Estado, tau: number,
    p: ParamHilo = HILO, q: ParamEstados = ESTADOS): void {
    const nT = PALETAS[p.paleta].length;
    pintarGlifo(cv, tam, conEstado(glifoHilo(nombre, p), estado, tau, q, nT), impresionHilo(p, tam), .34);
}
