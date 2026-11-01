// El campo: una cuadrícula de glifos que cambia de escala por zonas. Es un árbol de cuatro hijos por nodo: cada nodo
// quiere estar a una escala según un ruido y la fase del ciclo, y al cambiar, los cuatro hijos se recogen al centro y
// el padre brota desde ahí (`absorber`), encogen en su lugar (`tamano`) o cambian de golpe (`directa`). Nunca se ven
// dos escalas a la vez. Los nodos se calculan una vez y quedan en caché; lo que cae fuera del lienzo no se recorre.

import { TAU, estirar, fbm, hash, lim, suave } from './azar';
import { type Vida, animar } from './gestos';
import { type Impresion, FONDOS, type Mezcla, PALETAS, type Paleta, type Puesto } from './impresion';
import { type Pieza, glifo } from './piezas';

export interface ParamCampo extends Vida {
    paleta: Paleta;
    /** cuántas de sus tintas (2 a 7) */
    tintas: number;
    mezcla: Mezcla;
    fondo: keyof typeof FONDOS;
    intensidad: number;
    desregistro: number;
    grano: number;
    papel: number;
    /** el lado de la celda más chica, en px */
    celda: number;
    /** cuántas escalas sobre la chica (0 a 4) */
    niveles: number;
    /** piezas por glifo (1 a 3) */
    capas: number;
    /** tintas por glifo (0: una, 1: cada pieza la suya) */
    variedad: number;
    /** la fracción de celdas vacías */
    huecos: number;
    /** cuánto se desfasan las zonas (0: todas a la vez) */
    onda: number;
    /** el tamaño de las zonas, como fracción del lado mayor */
    ruido: number;
    /** segundos de un ciclo de escalas */
    ciclo: number;
    semilla: number;
    transicion: 'absorber' | 'tamano' | 'directa';
    /** qué fracción del camino entre dos escalas dura el cambio */
    corte: number;
}

/** El campo elegido el 31-oct-2026: riso fluo, mezcla máximo sobre crust, celda de 8 px, cinco escalas. La
 *  transición y la vida son las del prototipo, sin confirmar. */
export const CAMPO: ParamCampo = {
    paleta: 'fluo', tintas: 7, mezcla: 'maximo', fondo: 'crust', intensidad: 1, desregistro: 0, grano: .1, papel: .27, celda: 8,
    niveles: 4, capas: 3, variedad: 0, huecos: 0, onda: 1, ruido: .61, ciclo: 18.5,
    semilla: 11, transicion: 'absorber', corte: .35,
    actividad: .3, periodo: 4, duracion: .9, saltos: .2, rueda: .25,
};

interface Nodo { n: number; semilla: number; piezas: Pieza[] | null }
export interface CacheCampo { firma?: string; nodos?: Map<number, Nodo> }

/** Los glifos del campo en W×H, en la fase `t` (0 a 1) del ciclo y a los `tau` segundos (sus gestos). */
export function generarCampo(p: ParamCampo, W: number, H: number, t: number, tau: number, cache: CacheCampo): Puesto[] {
    const nT = Math.min(PALETAS[p.paleta].length, p.tintas);
    const L = p.niveles, C = p.celda * 2 ** L;
    const cols = Math.ceil(W / C) + 1, rows = Math.ceil(H / C) + 1;
    const ox = (W - cols * C) / 2, oy = (H - rows * C) / 2;
    const esc = Math.max(W, H) * p.ruido, s = p.semilla;
    const firma = [p.paleta, nT, s, p.ruido, p.capas, p.variedad, p.celda, L, p.huecos, W, H].join('|');
    if (cache.firma !== firma || !cache.nodos) { cache.firma = firma; cache.nodos = new Map(); }
    const nodos = cache.nodos;
    const todas = [...Array(nT).keys()];
    const out: Puesto[] = [];
    const nodoDe = (lv: number, ix: number, iy: number, cx: number, cy: number): Nodo => {
        const key = (lv * 4096 + iy) * 4096 + ix;
        let nd = nodos.get(key);
        if (!nd) {
            const hueco = p.huecos > 0 && hash(ix, iy, lv, s + 3) < p.huecos * (.25 + fbm(cx / esc * 1.6 + 31, cy / esc * 1.6 + 7, s + 5));
            const base = Math.min(nT - 1, Math.floor(estirar(fbm(cx / esc * .9 + 11, cy / esc * .9 + 3, s + 11), 2.3) * nT));
            const peso = lim(estirar(fbm(cx / esc + 5, cy / esc + 19, s + 21), 1.9) + lv * .1, 0, 1);
            const semilla = (hash(lv, ix, iy, s) * 4294967296) >>> 0;
            nd = { n: fbm(cx / esc, cy / esc, s), semilla, piezas: hueco ? null : glifo(semilla, peso, base, todas, p.capas, p.variedad) };
            nodos.set(key, nd);
        }
        return nd;
    };
    const deseado = (nd: Nodo): number => {
        if (L === 0) return 0;
        const w = .5 - .5 * Math.cos(TAU * (t - nd.n * p.onda * 1.5));
        const d = L * suave(lim((w - .12) / .76, 0, 1));
        const k = Math.floor(d);
        return k + lim((d - k - .5) / p.corte + .5, 0, 1);  // el cambio se concentra en una fracción corta
    };
    type Tr = { k: number; ox: number; oy: number; enc?: number };
    const emitir = (nd: Nodo, cx: number, cy: number, sz: number, tr: Tr, nacer: number | null) => {
        if (!nd.piezas) return;
        const R = sz * .45 * tr.k * (tr.enc ?? 1);
        if (R < .3) return;
        out.push({ piezas: animar(nd.piezas, nd.semilla, tau, p, nT, nacer), cx: cx * tr.k + tr.ox, cy: cy * tr.k + tr.oy, R, a: 1 });
    };
    const visitar = (lv: number, ix: number, iy: number, x: number, y: number, sz: number, tr: Tr): void => {
        const bx = x * tr.k + tr.ox, by = y * tr.k + tr.oy, bs = sz * tr.k;
        if (bx > W || by > H || bx + bs < 0 || by + bs < 0) return;
        const cx = x + sz / 2, cy = y + sz / 2;
        const nd = nodoDe(lv, ix, iy, cx, cy), dd = deseado(nd);
        if (lv === 0 || dd >= lv) { emitir(nd, cx, cy, sz, tr, null); return; }
        let trH = tr;
        if (dd > lv - 1) {
            const f = dd - (lv - 1);
            if (f >= .5) { emitir(nd, cx, cy, sz, tr, p.transicion === 'directa' ? null : (f - .5) * 2); return; }
            if (p.transicion !== 'directa') {
                const g = f * 2, k = 1 - g * g * g;
                if (k <= .02) return;
                trH = p.transicion === 'absorber'
                    ? { k: tr.k * k, ox: tr.ox + tr.k * cx * (1 - k), oy: tr.oy + tr.k * cy * (1 - k), enc: tr.enc }
                    : { ...tr, enc: (tr.enc ?? 1) * k };
            }
        }
        const m = sz / 2;
        visitar(lv - 1, ix * 2, iy * 2, x, y, m, trH); visitar(lv - 1, ix * 2 + 1, iy * 2, x + m, y, m, trH);
        visitar(lv - 1, ix * 2, iy * 2 + 1, x, y + m, m, trH); visitar(lv - 1, ix * 2 + 1, iy * 2 + 1, x + m, y + m, m, trH);
    };
    const tr0: Tr = { k: 1, ox: 0, oy: 0 };
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) visitar(L, i, j, ox + i * C, oy + j * C, C, tr0);
    return out;
}

/** Cómo se imprime el campo de estos parámetros. */
export function impresionDe(p: ParamCampo): Impresion {
    const pal = PALETAS[p.paleta];
    return { tintas: pal.slice(0, Math.min(pal.length, p.tintas)), fondo: FONDOS[p.fondo] ?? '', mezcla: p.mezcla, intensidad: p.intensidad,
        desregistro: p.desregistro, grano: p.grano, papel: p.papel };
}

