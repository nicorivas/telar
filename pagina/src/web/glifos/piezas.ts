// Las piezas con que se arman los glifos (anillos, puntos, cruces, píxeles…) y cómo se elige un glifo: hasta tres
// piezas (contorno, cuerpo, centro), cada una de su tinta. Cada pieza se dibuja en un cuadrado de -1 a 1; `u` es cuánto
// apareció (0 nada, 1 entera) para las que brotan por partes.

import { TAU, pop, rng } from './azar';

type Ctx = CanvasRenderingContext2D;

/** Una pieza puesta en un glifo: su forma, su tinta y, mientras hace un gesto, su giro, escala, avance y brillo. */
export interface Pieza {
    k: Forma;
    /** el índice de su tinta */
    t: number;
    rot?: number;
    /** escala (1: entera) */
    s?: number;
    /** avance de su aparición, para las que brotan por partes */
    u?: number;
    /** brillo (1: pleno) */
    a?: number;
    /** corrimiento desde el centro, en radios */
    dx?: number;
    dy?: number;
}

const P = (u: number | undefined, a: number, b: number): number => (u === undefined ? 1 : pop((u - a) / b));
function anillo(x: Ctx, r: number, w: number): void { x.moveTo(r, 0); x.arc(0, 0, r, 0, TAU, false); x.moveTo(r - w, 0); x.arc(0, 0, r - w, 0, TAU, true); }
function circulo(x: Ctx, cx: number, cy: number, r: number): void { x.moveTo(cx + r, cy); x.arc(cx, cy, r, 0, TAU); }
function puntos(x: Ctx, n: number, R: number, r: number, a0: number, u?: number): void {
    for (let i = 0; i < n; i++) {
        const k = P(u, i / n * .65, .35);
        if (k <= 0) continue;
        const a = a0 + i * TAU / n;
        circulo(x, Math.cos(a) * R, Math.sin(a) * R, r * k);
    }
}
function rombo(x: Ctx, cx: number, cy: number, r: number): void { x.moveTo(cx, cy - r); x.lineTo(cx + r, cy); x.lineTo(cx, cy + r); x.lineTo(cx - r, cy); x.closePath(); }
function rombos(x: Ctx, n: number, R: number, r: number, a0: number, u?: number): void {
    for (let i = 0; i < n; i++) {
        const k = P(u, i / n * .65, .35);
        if (k <= 0) continue;
        const a = a0 + i * TAU / n;
        rombo(x, Math.cos(a) * R, Math.sin(a) * R, r * k);
    }
}
function barra(x: Ctx, a: number, L: number, w: number): void {
    const c = Math.cos(a), s = Math.sin(a), px = -s * w, py = c * w;
    x.moveTo(-L * c + px, -L * s + py); x.lineTo(L * c + px, L * s + py); x.lineTo(L * c - px, L * s - py); x.lineTo(-L * c - px, -L * s - py); x.closePath();
}
/** Una figura de píxeles en una grilla de 5×5: aparecen por anillos, del centro hacia afuera. */
function pixeles(x: Ctx, f: (i: number, j: number) => boolean, s: number, u?: number): void {
    const e = .006;
    for (let j = -2; j <= 2; j++) for (let i = -2; i <= 2; i++) {
        if (!f(i, j)) continue;
        const k = P(u, Math.max(Math.abs(i), Math.abs(j)) * .22, .4);
        if (k <= 0) continue;
        const h = s * k;
        x.rect(i * s - h / 2 - e, j * s - h / 2 - e, h + 2 * e, h + 2 * e);
    }
}

export const TRAZOS = {
    anillo: (x: Ctx) => anillo(x, .84, .16),
    aro: (x: Ctx) => anillo(x, .88, .075),
    dobleAnillo: (x: Ctx, u?: number) => { const a = P(u, 0, .6), b = P(u, .3, .7); if (b > 0) anillo(x, .88 * b, .11 * b); if (a > 0) anillo(x, .56 * a, .11 * a); },
    disco: (x: Ctx) => circulo(x, 0, 0, .9),
    puntos8: (x: Ctx, u?: number) => puntos(x, 8, .72, .12, 0, u),
    puntos12: (x: Ctx, u?: number) => puntos(x, 12, .8, .075, 0, u),
    puntos4: (x: Ctx, u?: number) => puntos(x, 4, .5, .2, TAU / 8, u),
    cruz: (x: Ctx, u?: number) => { const k = P(u, 0, 1); if (k > 0) { barra(x, 0, .8 * k, .15); barra(x, TAU / 4, .8 * k, .15); } },
    cruzGruesa: (x: Ctx, u?: number) => { const k = P(u, 0, 1); if (k > 0) { barra(x, 0, .92 * k, .23); barra(x, TAU / 4, .92 * k, .23); } },
    equis: (x: Ctx, u?: number) => { const k = P(u, 0, 1); if (k > 0) { barra(x, TAU / 8, .82 * k, .15); barra(x, -TAU / 8, .82 * k, .15); } },
    asterisco: (x: Ctx, u?: number) => { for (let i = 0; i < 4; i++) { const k = P(u, i * .15, .55); if (k > 0) barra(x, i * TAU / 8, .8 * k, .055); } },
    romboPixel: (x: Ctx, u?: number) => pixeles(x, (i, j) => Math.abs(i) + Math.abs(j) === 2, .3, u),
    damero: (x: Ctx, u?: number) => pixeles(x, (i, j) => Math.abs(i) + Math.abs(j) <= 2 && (i + j) % 2 === 0, .3, u),
    cruzPixel: (x: Ctx, u?: number) => pixeles(x, (i, j) => (i === 0 || j === 0) && (i !== 0 || j !== 0), .3, u),
    rombos4: (x: Ctx, u?: number) => rombos(x, 4, .5, .24, TAU / 8, u),
    rombos8: (x: Ctx, u?: number) => rombos(x, 8, .72, .13, 0, u),
    triangulo: (x: Ctx) => { x.moveTo(0, -.78); x.lineTo(.7, .44); x.lineTo(-.7, .44); x.closePath(); },
    cuartos: (x: Ctx, u?: number) => {
        const k = P(u, 0, 1);
        if (k <= 0) return;
        const a = TAU / 4 * k;
        x.moveTo(0, 0); x.arc(0, 0, .9, -TAU / 4, -TAU / 4 + a); x.closePath();
        x.moveTo(0, 0); x.arc(0, 0, .9, TAU / 4, TAU / 4 + a); x.closePath();
    },
    punto: (x: Ctx) => circulo(x, 0, 0, .17),
    anilloChico: (x: Ctx) => anillo(x, .38, .13),
    romboChico: (x: Ctx) => rombo(x, 0, 0, .27),
} satisfies Record<string, (x: Ctx, u?: number) => void>;

export type Forma = keyof typeof TRAZOS;

/** Las que brotan por partes; las demás brotan creciendo enteras. */
export const REVELA = new Set<Forma>(['dobleAnillo', 'puntos8', 'puntos12', 'puntos4', 'cruz', 'cruzGruesa', 'equis', 'asterisco',
    'romboPixel', 'damero', 'cruzPixel', 'rombos4', 'rombos8', 'cuartos']);
/** Las redondas: girarlas no se ve. */
export const REDONDAS = new Set<Forma>(['anillo', 'aro', 'dobleAnillo', 'disco', 'punto', 'anilloChico']);
/** Cuánto gira cada una en un gesto: lo que la deja igual que antes. */
export const SIMETRIA: Partial<Record<Forma, number>> = {
    cuartos: TAU / 2, cruz: TAU / 4, cruzGruesa: TAU / 4, equis: TAU / 4, triangulo: TAU / 3, rombos4: TAU / 4, rombos8: TAU / 8,
    puntos8: TAU / 8, puntos12: TAU / 12, puntos4: TAU / 4, asterisco: TAU / 8, romboPixel: TAU / 4, damero: TAU / 4, cruzPixel: TAU / 4,
    romboChico: TAU / 4,
};

/** Tres juegos según el peso: livianos (puntos, aros), medios y pesados (discos, cruces gruesas). */
const JUEGOS: { cont: Forma[]; cuerpo: Forma[]; centro: Forma[] }[] = [
    { cont: ['puntos8', 'puntos12', 'aro', 'rombos8'], cuerpo: ['puntos4', 'asterisco', 'romboPixel', 'damero', 'rombos4'], centro: ['punto', 'anilloChico'] },
    { cont: ['anillo', 'aro', 'puntos8', 'dobleAnillo', 'rombos8'], cuerpo: ['cruz', 'equis', 'romboPixel', 'damero', 'asterisco', 'cuartos', 'rombos4'], centro: ['punto', 'anilloChico', 'romboChico'] },
    { cont: ['disco', 'anillo', 'dobleAnillo', 'cuartos'], cuerpo: ['cruzGruesa', 'equis', 'cruzPixel', 'triangulo', 'cuartos', 'damero', 'cruz'], centro: ['punto', 'romboChico', 'anilloChico'] },
];

/** Un glifo: hasta `capasMax` piezas, la primera de la tinta `base` y las demás, con probabilidad `variedad`, de
 *  otra de `permitidas` (sin repetir mientras haya libres). */
export function glifo(semilla: number, peso: number, base: number, permitidas: number[], capasMax: number, variedad: number): Pieza[] {
    const r = rng(semilla);
    const J = JUEGOS[peso < .36 ? 0 : peso < .68 ? 1 : 2];
    const elegir = <T>(a: T[]): T => a[Math.floor(r() * a.length)];
    const giro = () => (r() < .5 ? 0 : TAU / 8);
    const p: Omit<Pieza, 't'>[] = [];
    if (r() < .85) p.push({ k: elegir(J.cont), rot: giro() });
    if (r() < .8 || !p.length) p.push({ k: elegir(J.cuerpo), rot: giro() });
    if (r() < .45) p.push({ k: elegir(J.centro), rot: 0 });
    while (p.length > capasMax) p.splice(r() < .5 ? 0 : p.length - 1, 1);
    const usadas: number[] = [];
    const salida = p.map((z, i) => {
        let t = (i === 0 || r() > variedad) ? base : permitidas[Math.floor(r() * permitidas.length)];
        if (usadas.includes(t)) {
            const libres = permitidas.filter(q => !usadas.includes(q));
            if (libres.length) t = libres[Math.floor(r() * libres.length)];
        }
        usadas.push(t);
        return { ...z, t };
    });
    // un disco o unos cuartos taparían a otra pieza de su misma tinta
    if ((salida[0].k === 'disco' || salida[0].k === 'cuartos') && salida.slice(1).some(z => z.t === salida[0].t)) salida[0].k = 'anillo';
    return salida;
}
