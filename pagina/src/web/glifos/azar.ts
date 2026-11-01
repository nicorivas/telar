// Azar determinista, ruido y curvas: lo que usan las piezas, los glifos y el campo (web/glifos/index.ts).
// Todo sale de una semilla: el mismo nombre de hilo da siempre el mismo glifo, y el campo, la misma cuadrícula.

export const TAU = Math.PI * 2;

const h32 = (a: number): number => {
    a = Math.imul(a ^ (a >>> 16), 0x7feb352d);
    a = Math.imul(a ^ (a >>> 15), 0x846ca68b);
    return (a ^ (a >>> 16)) >>> 0;
};

/** Un número en [0, 1) que depende solo de sus argumentos. */
export function hash(a: number, b = 0, c = 0, d = 0): number {
    let h = h32((a | 0) + 0x9e3779b9);
    h = h32(h ^ (b | 0)); h = h32(h ^ Math.imul(c | 0, 0x27d4eb2d)); h = h32(h ^ Math.imul(d | 0, 0x165667b1));
    return h / 4294967296;
}

/** Una sucesión de números en [0, 1) a partir de una semilla (mulberry32). */
export function rng(semilla: number): () => number {
    let a = semilla >>> 0;
    return () => {
        a = (a + 0x6D2B79F5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

/** La semilla de un texto (FNV-1a, mezclado). */
export function hashTexto(s: string): number {
    let h = 2166136261;
    for (const ch of s) { h ^= ch.codePointAt(0) ?? 0; h = Math.imul(h, 16777619); }
    return h32(h);
}

export const suave = (t: number): number => t * t * (3 - 2 * t);
export const lim = (v: number, a: number, b: number): number => Math.min(b, Math.max(a, v));
export const estirar = (v: number, k: number): number => lim((v - .5) * k + .5, 0, 1);
export const backOut = (t: number, c = 1.70158): number => 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
/** Aparecer por tamaño, con un leve rebote: nunca un fundido. */
export const pop = (t: number): number => (t <= 0 ? 0 : t >= 1 ? 1 : backOut(t));

/** Ruido de valor en 2D (con período `P`, para texturas que se repiten sin costura). */
export function vruido(x: number, y: number, s: number, P = 0): number {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const m = P ? (v: number) => ((v % P) + P) % P : (v: number) => v;
    const a = hash(m(xi), m(yi), s), b = hash(m(xi + 1), m(yi), s), c = hash(m(xi), m(yi + 1), s), d = hash(m(xi + 1), m(yi + 1), s);
    const u = suave(xf), v = suave(yf);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

/** Dos octavas de ruido. */
export const fbm = (x: number, y: number, s: number): number => vruido(x, y, s) * .62 + vruido(x * 2.03 + 17.1, y * 2.03 + 5.3, s + 1) * .38;
