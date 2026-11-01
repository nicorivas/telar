// Los glifos de risografía de la página: un campo de glifos que cambia de escala (detrás de una pantalla o en una banda
// arriba) y un glifo por hilo, con su estado, en la barra. Todo se prende y se apaga desde los modos (web/modos.ts,
// telar.modos), así que cada modo puede tener lo suyo:
//
//   glifos    no | si                  el interruptor de todo: «no» deja la página como siempre
//   estilo    base | <otro>             cuál de `[glifos.<estilo>]` (estilo.ts): tintas, vida, gestos, glifo, estados
//   iconos    simbolos | glifos         los íconos de la barra de hilos
//   campo     "ahora=banda, plan=fondo 0.15, *=nada"   dónde va el campo en cada pantalla (`pantalla=lugar [intensidad]`)
//
// Todo eso se cambia también en ⚙ glifos (vistas/dashboard/config/glifos.ts), con una vista previa.
//
// Las piezas son módulos sueltos: piezas.ts (los trazos y cómo se arma un glifo), gestos.ts (girar, brotar, latir…),
// impresion.ts (las tintas en capas, el grano, la mezcla), campo.ts (la cuadrícula que cambia de escala) e hilo.ts (el
// glifo de un nombre y sus estados). Este archivo solo los pone en la página: mide, pinta, anima lo visible a 30 cuadros
// por segundo como mucho, se detiene con la pestaña oculta y, con «reducir movimiento», pinta una vez y no anima.
//
// La idea viene de «riso glyph expansion», de cnrd.art: tintas de risografía, glifos simétricos y una cuadrícula que
// cambia de escala por zonas. Las piezas, el código y los parámetros son propios.

import * as modos from '../modos';
import { type CacheCampo, type ParamCampo, generarCampo, impresionDe } from './campo';
import * as estilo from './estilo';
import { ajustar, pintarRiso } from './impresion';
import { ANIMADOS, type Estado, pintarHilo } from './hilo';

export { estilo };
export type { Estado } from './hilo';

const CUADRO = 1000 / 30;
const QUIETO = matchMedia('(prefers-reduced-motion: reduce)');

/** Si están prendidos en el modo puesto. */
export const prendidos = (): boolean => modos.valor('glifos') === 'si';
/** Si la barra de hilos lleva glifos en vez de los símbolos. */
export const enLaBarra = (): boolean => prendidos() && modos.valor('iconos') === 'glifos';

export type Lugar = 'banda' | 'fondo' | 'nada';
export interface Ubicacion { lugar: Lugar; intensidad: number }

/** Lo que dice `campo` para una pantalla (su clave: «ahora», «revisar», «pestana:leer», «conversacion»…; `*` vale para
 *  las que no se nombran). */
export function campoPara(pantalla: string, texto = String(modos.valor('campo') ?? '')): Ubicacion | null {
    let comodin: Ubicacion | null = null;
    for (const parte of texto.split(',')) {
        const m = /^\s*([^=\s]+)\s*=\s*(banda|fondo|nada)(?:\s+([\d.]+))?\s*$/.exec(parte);
        if (!m) continue;
        const u: Ubicacion = { lugar: m[2] as Lugar, intensidad: Math.min(1, Math.max(.05, Number(m[3] ?? (m[2] === 'fondo' ? .15 : 1)))) };
        if (m[1] === pantalla) return u.lugar === 'nada' ? null : u;
        if (m[1] === '*') comodin = u;
    }
    return comodin?.lugar === 'nada' ? null : comodin;
}

// ── campos: un lienzo que cambia de escala; el de la página (en la banda o el fondo) y los de muestra (⚙ glifos) ──

/** Un campo vivo: su lienzo, de qué estilo y con qué intensidad, y su reloj. */
interface Vivo { cv: HTMLCanvasElement; estilo: string; intensidad: number; fondo: boolean; p: ParamCampo; cache: CacheCampo; fase: number; tau: number; w: number; h: number }
const campos = new Set<Vivo>();

function vivo(cv: HTMLCanvasElement): Vivo {
    for (const v of campos) if (v.cv === cv) return v;
    const v: Vivo = { cv, estilo: 'base', intensidad: 1, fondo: false, p: estilo.campo(), cache: {}, fase: .3, tau: 0, w: 0, h: 0 };
    campos.add(v);
    new ResizeObserver(() => { v.w = cv.clientWidth; v.h = cv.clientHeight; pintarCampo(v); }).observe(cv);
    return v;
}

/** Los parámetros del campo según su estilo y su lugar (de fondo, sin papel de fondo). */
function rehacer(v: Vivo): void {
    const p = estilo.campo(estilo.valores(v.estilo));
    v.p = { ...p, intensidad: p.intensidad * v.intensidad, fondo: v.fondo ? 'ninguno' : p.fondo };
}

function pintarCampo(v: Vivo): void {
    if (!v.cv.isConnected || !v.w || !v.h) return;
    // de fondo, a un píxel por píxel de CSS: es grande, va tenue y el grano lo disimula (con pantalla retina, la
    // cuarta parte del trabajo)
    ajustar(v.cv, v.w, v.h, v.fondo ? 1 : undefined);
    pintarRiso(v.cv, v.w, v.h, generarCampo(v.p, v.w, v.h, v.fase, v.tau, v.cache), impresionDe(v.p));
}

let pagina: HTMLCanvasElement | null = null;

/** Pone el campo en la pantalla que se ve, según el modo: `seccion`, la vista a la vista (la banda va al principio de
 *  ella); `fondo`, el contenedor de las vistas (el fondo va detrás de todas). Sin campo para ella, lo saca. */
export function ubicar(pantalla: string, seccion: HTMLElement | undefined, fondo: HTMLElement): void {
    const u = prendidos() && pantalla ? campoPara(pantalla) : null;
    if (!u || !seccion) { pagina?.remove(); return; }
    void estilo.leer();
    if (!pagina) {
        pagina = document.createElement('canvas');
        pagina.className = 'campo-glifos';
        pagina.setAttribute('aria-hidden', 'true');
    }
    pagina.dataset.lugar = u.lugar;
    const padre = u.lugar === 'banda' ? seccion : fondo;
    if (pagina.parentElement !== padre || padre.firstElementChild !== pagina) padre.prepend(pagina);
    const v = vivo(pagina);
    Object.assign(v, { estilo: estilo.puesto(), intensidad: u.intensidad, fondo: u.lugar === 'fondo' });
    rehacer(v);
    v.w = pagina.clientWidth; v.h = pagina.clientHeight;
    pintarCampo(v);
    andar();
}

/** Un campo de muestra en `cv` (⚙ glifos), del estilo `de`: se mueve mientras esté en la página. */
export function muestra(cv: HTMLCanvasElement, de: string): void {
    const v = vivo(cv);
    v.estilo = de;
    rehacer(v);
    v.w = cv.clientWidth; v.h = cv.clientHeight;
    pintarCampo(v);
    andar();
}

// ── los glifos de los hilos: cada <canvas class="glifo-hilo" data-nombre data-estado> de la página ──

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');

/** El lienzo de un glifo de hilo, para meterlo en el HTML (se pinta después con `pintarEn`). `tam`: sus px (si no, el
 *  de la barra del estilo); `de`: el estilo (si no, el del modo). */
export function htmlHilo(nombre: string, estado: Estado, tam = 0, de = ''): string {
    return `<canvas class="glifo-hilo" data-nombre="${esc(nombre)}" data-estado="${estado}"${tam ? ` data-tam="${tam}"` : ''}`
        + `${de ? ` data-estilo="${esc(de)}"` : ''} aria-hidden="true"></canvas>`;
}
/** El sello de un hilo: su glifo grande, para la ficha. */
export const htmlSello = (nombre: string, estado: Estado): string => htmlHilo(nombre, estado, estilo.tam().sello);

let iconos: HTMLCanvasElement[] = [];
const tau0 = performance.now();
const tau = () => (performance.now() - tau0) / 1000;

function pintarIcono(cv: HTMLCanvasElement): void {
    const vs = estilo.valores(cv.dataset.estilo || estilo.puesto());
    const tam = Number(cv.dataset.tam) || estilo.tam(vs).barra;
    cv.style.width = cv.style.height = `${tam}px`;
    pintarHilo(cv, tam, cv.dataset.nombre ?? '', (cv.dataset.estado ?? 'ninguna') as Estado, tau(), estilo.hilo(vs), estilo.estados(vs));
}

/** Pinta los glifos de hilo que hay en `raiz` (después de pintarla) y anima los que se mueven. */
export function pintarEn(raiz: HTMLElement): void {
    const todos = [...raiz.querySelectorAll<HTMLCanvasElement>('canvas.glifo-hilo')];
    if (todos.length) void estilo.leer();
    for (const cv of todos) pintarIcono(cv);
    iconos = [...iconos.filter(c => c.isConnected && !raiz.contains(c)), ...todos.filter(c => ANIMADOS.has(c.dataset.estado as Estado))];
    if (iconos.length) andar();
}

// un estilo que cambia (se leyó, se afina en ⚙ o se guardó): todo lo que está a la vista se rehace con él
estilo.alCambiar(() => {
    for (const v of campos) { if (!v.cv.isConnected) { campos.delete(v); continue; } rehacer(v); v.cache = {}; pintarCampo(v); }
    for (const cv of document.querySelectorAll<HTMLCanvasElement>('canvas.glifo-hilo')) pintarIcono(cv);
});

// ── el reloj: un solo requestAnimationFrame, a 30 cuadros, solo con algo que mover ──

let andando = false, ultimo = 0;
function andar(): void {
    if (andando || QUIETO.matches) return;
    andando = true;
    ultimo = performance.now();
    requestAnimationFrame(cuadro);
}
function cuadro(ahora: number): void {
    for (const v of campos) if (!v.cv.isConnected) campos.delete(v);
    iconos = iconos.filter(c => c.isConnected);
    if ((!campos.size && !iconos.length) || QUIETO.matches) { andando = false; return; }
    if (!document.hidden && ahora - ultimo >= CUADRO - 4) {
        const dt = Math.min(.1, (ahora - ultimo) / 1000);
        ultimo = ahora;
        for (const v of campos) { if (!v.cv.offsetParent) continue; v.fase = (v.fase + dt / v.p.ciclo) % 1; v.tau += dt; pintarCampo(v); }
        for (const cv of iconos) if (cv.offsetParent) pintarIcono(cv);
    } else if (document.hidden) ultimo = ahora;
    requestAnimationFrame(cuadro);
}
QUIETO.addEventListener?.('change', () => { if (!QUIETO.matches) andar(); });
