// La impresión de risografía sobre fondo oscuro: cada tinta en su propia capa, con grano, un leve corrimiento
// (desregistro) y mezclada con las otras por luz (donde dos tintas se cruzan, aclaran). Las texturas se arman la
// primera vez que se pinta: con los glifos apagados no se crea nada.

import { lim, rng, vruido } from './azar';
import { type Pieza, TRAZOS } from './piezas';

/** Las paletas: siete tintas en el mismo orden (rosa, azul, verde, amarillo, violeta, cian, clara). */
export const PALETAS = {
    mocha: ['#f38ba8', '#89b4fa', '#a6e3a1', '#f9e2af', '#cba6f7', '#94e2d5', '#cdd6f4'],
    fluo: ['#ff48b0', '#3a8cf0', '#1fb874', '#ffe800', '#9d7af5', '#5ec8e5', '#f2efe6'],
    apagado: ['#e0789f', '#5b8fd6', '#5fb88a', '#e3c66a', '#a493e6', '#6cc3c0', '#d8d2c4'],
} as const;
export type Paleta = keyof typeof PALETAS;
export const FONDOS = { base: '#1e1e2e', barra: '#181825', crust: '#11111b', ninguno: '' } as const;
const MEZCLA = { luz: 'screen', maximo: 'lighten', suma: 'lighter', opaca: 'source-over' } as const;
export type Mezcla = keyof typeof MEZCLA;

/** Cómo se imprime: las tintas, el fondo ('' transparente), la mezcla y la textura. */
export interface Impresion {
    tintas: readonly string[];
    fondo: string;
    mezcla: Mezcla;
    intensidad: number;
    /** corrimiento de cada tinta, en px */
    desregistro: number;
    /** cuánta tinta se come el grano (0 a 1) */
    grano: number;
    /** el papel: motas claras sobre el fondo (0 a 1) */
    papel: number;
}

/** Un glifo puesto: sus piezas, su centro, su radio y su brillo. */
export interface Puesto { piezas: Pieza[]; cx: number; cy: number; R: number; a: number }

function textura(tam: number, fn: (i: number, j: number) => [number, number]): HTMLCanvasElement {
    const c = document.createElement('canvas');
    c.width = c.height = tam;
    const x = c.getContext('2d')!, im = x.createImageData(tam, tam);
    for (let j = 0; j < tam; j++) for (let i = 0; i < tam; i++) {
        const k = (j * tam + i) * 4, [v, a] = fn(i, j);
        im.data[k] = im.data[k + 1] = im.data[k + 2] = v;
        im.data[k + 3] = a;
    }
    x.putImageData(im, 0, 0);
    return c;
}
let texturas: { grano: HTMLCanvasElement; papel: HTMLCanvasElement } | null = null;
function lasTexturas() {
    if (!texturas) {
        const r = rng(7);
        texturas = {
            grano: textura(160, (i, j) => { const n = vruido(i / 8, j / 8, 3, 20), w = r(); return [0, lim(Math.pow(w, 2.4) * 220 + (n - .42) * 250, 0, 255)]; }),
            papel: textura(160, () => [255, Math.pow(r(), 9) * 255]),
        };
    }
    return texturas;
}

/** Las capas de tinta: unos lienzos fuera de la página que se reusan (crecen al más grande que se pidió). */
interface Capa { cv: HTMLCanvasElement; x: CanvasRenderingContext2D; grano: CanvasPattern | null }
const CAPAS: Capa[] = [];
function capa(i: number, pw: number, ph: number): Capa {
    let c = CAPAS[i];
    if (!c) {
        const cv = document.createElement('canvas');
        cv.width = pw; cv.height = ph;
        c = CAPAS[i] = { cv, x: cv.getContext('2d')!, grano: null };
    }
    if (c.cv.width < pw || c.cv.height < ph) {
        c.cv.width = Math.max(c.cv.width, pw); c.cv.height = Math.max(c.cv.height, ph);
        c.grano = null;
    }
    if (!c.grano) {
        c.grano = c.x.createPattern(lasTexturas().grano, 'repeat');
        try { c.grano?.setTransform(new DOMMatrix().translateSelf((i * 37) % 160, (i * 53) % 160)); } catch { /* sin desfase de grano */ }
    }
    return c;
}
const DESFASE = Array.from({ length: 12 }, (_, i) => (i === 0 ? [0, 0] : [Math.cos(i * 2.4 + .6), Math.sin(i * 2.4 + .6)]));
const papeles = new WeakMap<CanvasRenderingContext2D, CanvasPattern | null>();

function dibujarPieza(x: CanvasRenderingContext2D, z: Pieza, g: Puesto, d: number): void {
    const R = g.R * (z.s ?? 1);
    if (R <= .05) return;
    const rot = z.rot || 0, cx = g.cx + (z.dx || 0) * g.R, cy = g.cy + (z.dy || 0) * g.R;
    const c = Math.cos(rot) * R * d, s = Math.sin(rot) * R * d;
    x.setTransform(c, s, -s, c, cx * d, cy * d);
    x.beginPath();
    TRAZOS[z.k](x, z.u);
    x.fill();
}

/** Pinta `glifos` en `cv` (de W×H px de CSS): una capa por tinta y después todas juntas, con su mezcla. */
export function pintarRiso(cv: HTMLCanvasElement, W: number, H: number, glifos: Puesto[], o: Impresion): void {
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    const pw = cv.width, ph = cv.height, d = pw / W, n = o.tintas.length;
    const capas: Capa[] = [];
    for (let i = 0; i < n; i++) {
        const c = capa(i, pw, ph), x = c.x;
        x.setTransform(1, 0, 0, 1, 0, 0); x.globalCompositeOperation = 'source-over'; x.globalAlpha = 1;
        x.clearRect(0, 0, pw, ph); x.fillStyle = o.tintas[i];
        capas.push(c);
    }
    for (const g of glifos) for (const z of g.piezas) {
        const a = g.a * (z.a ?? 1);
        if (a < .01) continue;
        const c = capas[z.t % n];
        c.x.globalAlpha = a;
        dibujarPieza(c.x, z, g, d);
    }
    if (o.grano > 0) for (const c of capas) {
        const x = c.x;
        x.setTransform(d, 0, 0, d, 0, 0); x.globalCompositeOperation = 'destination-out'; x.globalAlpha = o.grano;
        if (c.grano) { x.fillStyle = c.grano; x.fillRect(0, 0, W, H); }
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    if (o.fondo) { ctx.fillStyle = o.fondo; ctx.fillRect(0, 0, pw, ph); } else ctx.clearRect(0, 0, pw, ph);
    if (o.papel > 0) {
        if (!papeles.has(ctx)) papeles.set(ctx, ctx.createPattern(lasTexturas().papel, 'repeat'));
        const papel = papeles.get(ctx);
        if (papel) {
            ctx.setTransform(d, 0, 0, d, 0, 0); ctx.globalCompositeOperation = 'screen'; ctx.globalAlpha = o.papel * .3;
            ctx.fillStyle = papel; ctx.fillRect(0, 0, W, H);
            ctx.setTransform(1, 0, 0, 1, 0, 0);
        }
    }
    ctx.globalCompositeOperation = MEZCLA[o.mezcla] ?? 'screen';
    const k = o.mezcla === 'opaca' ? .85 : 1;
    for (let i = 0; i < n; i++) {
        const f = DESFASE[i % DESFASE.length];
        ctx.globalAlpha = o.intensidad * k;
        ctx.drawImage(capas[i].cv, 0, 0, pw, ph, f[0] * o.desregistro * d, f[1] * o.desregistro * d, pw, ph);
    }
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
}

/** La densidad de píxeles, hasta 2 (más no se nota y cuesta). */
export const DPR = (): number => Math.min(2, window.devicePixelRatio || 1);

/** Ajusta el tamaño en píxeles de `cv` a w×h de CSS, con `d` píxeles por cada uno de CSS. */
export function ajustar(cv: HTMLCanvasElement, w: number, h: number, d = DPR()): void {
    const pw = Math.max(1, Math.round(w * d)), ph = Math.max(1, Math.round(h * d));
    if (cv.width !== pw || cv.height !== ph) { cv.width = pw; cv.height = ph; }
}

/** Un glifo solo, centrado en un cuadrado de `tam` px; `Rf`, su radio como fracción del lado. */
export function pintarGlifo(cv: HTMLCanvasElement, tam: number, piezas: Pieza[], o: Impresion, Rf: number): void {
    ajustar(cv, tam, tam);
    pintarRiso(cv, tam, tam, [{ piezas, cx: tam / 2, cy: tam / 2, R: tam * Rf, a: 1 }], o);
}
