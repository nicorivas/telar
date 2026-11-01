// Los glifos de risografía de la página: un campo de glifos que cambia de escala (detrás de una pantalla o en una banda
// arriba) y un glifo por hilo, con su estado, en la barra. Todo se prende y se apaga desde los modos (web/modos.ts,
// telar.modos), así que cada modo puede tener lo suyo:
//
//   glifos    no | si                  el interruptor de todo: «no» deja la página como siempre
//   iconos    simbolos | glifos         los íconos de la barra de hilos
//   campo     "ahora=banda, plan=fondo 0.15, *=nada"   dónde va el campo en cada pantalla (`pantalla=lugar [intensidad]`)
//
// Las piezas son módulos sueltos: piezas.ts (los trazos y cómo se arma un glifo), gestos.ts (girar, brotar, latir…),
// impresion.ts (las tintas en capas, el grano, la mezcla), campo.ts (la cuadrícula que cambia de escala) e hilo.ts (el
// glifo de un nombre y sus estados). Este archivo solo los pone en la página: mide, pinta, anima lo visible a 30 cuadros
// por segundo como mucho, se detiene con la pestaña oculta y, con «reducir movimiento», pinta una vez y no anima.
//
// La idea viene de «riso glyph expansion», de cnrd.art: tintas de risografía, glifos simétricos y una cuadrícula que
// cambia de escala por zonas. Las piezas, el código y los parámetros son propios.

import * as modos from '../modos';
import { CAMPO, type CacheCampo, type ParamCampo, generarCampo, impresionDe } from './campo';
import { ajustar, pintarRiso } from './impresion';
import { ANIMADOS, type Estado, pintarHilo } from './hilo';

export { CAMPO } from './campo';
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

// ── el campo: un lienzo que se mueve entre la banda de la pantalla que se ve y el fondo de las vistas ──

interface Vivo { cv: HTMLCanvasElement; p: ParamCampo; cache: CacheCampo; fase: number; tau: number; w: number; h: number }
let vivo: Vivo | null = null;

/** El lienzo del campo, creado la primera vez. */
function lienzo(): Vivo {
    if (!vivo) {
        const cv = document.createElement('canvas');
        cv.className = 'campo-glifos';
        cv.setAttribute('aria-hidden', 'true');
        vivo = { cv, p: { ...CAMPO }, cache: {}, fase: .3, tau: 0, w: 0, h: 0 };
        new ResizeObserver(() => medir()).observe(cv);
    }
    return vivo;
}

function medir(): void {
    if (!vivo) return;
    vivo.w = vivo.cv.clientWidth; vivo.h = vivo.cv.clientHeight;
    pintarCampo();
}

function pintarCampo(): void {
    if (!vivo?.cv.isConnected || !vivo.w || !vivo.h) return;
    // de fondo, a un píxel por píxel de CSS: es grande, va tenue y el grano lo disimula (con pantalla retina, la
    // cuarta parte del trabajo)
    ajustar(vivo.cv, vivo.w, vivo.h, vivo.cv.dataset.lugar === 'fondo' ? 1 : undefined);
    pintarRiso(vivo.cv, vivo.w, vivo.h, generarCampo(vivo.p, vivo.w, vivo.h, vivo.fase, vivo.tau, vivo.cache), impresionDe(vivo.p));
}

/** Pone el campo en la pantalla que se ve, según el modo: `seccion`, la vista a la vista (la banda va al principio de
 *  ella); `fondo`, el contenedor de las vistas (el fondo va detrás de todas). Sin campo para ella, lo saca. */
export function ubicar(pantalla: string, seccion: HTMLElement | undefined, fondo: HTMLElement): void {
    const u = prendidos() && pantalla ? campoPara(pantalla) : null;
    if (!u || !seccion) { vivo?.cv.remove(); return; }
    const v = lienzo();
    v.cv.dataset.lugar = u.lugar;
    v.p = { ...CAMPO, intensidad: CAMPO.intensidad * u.intensidad, fondo: u.lugar === 'fondo' ? 'ninguno' : CAMPO.fondo };
    const padre = u.lugar === 'banda' ? seccion : fondo;
    if (v.cv.parentElement !== padre || padre.firstElementChild !== v.cv) padre.prepend(v.cv);
    medir();
    andar();
}

// ── los glifos de los hilos: cada <canvas class="glifo-hilo" data-nombre data-estado> de la página ──

const TAM_BARRA = 15;

/** El lienzo de un glifo de hilo, para meterlo en el HTML (la barra lo pinta después con `pintarEn`). */
export function htmlHilo(nombre: string, estado: Estado, tam = TAM_BARRA): string {
    const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
    return `<canvas class="glifo-hilo" data-nombre="${esc(nombre)}" data-estado="${estado}" data-tam="${tam}" aria-hidden="true"></canvas>`;
}

let iconos: HTMLCanvasElement[] = [];
const tau0 = performance.now();
const tau = () => (performance.now() - tau0) / 1000;

function pintarIcono(cv: HTMLCanvasElement): void {
    const tam = Number(cv.dataset.tam) || TAM_BARRA;
    cv.style.width = cv.style.height = `${tam}px`;
    pintarHilo(cv, tam, cv.dataset.nombre ?? '', (cv.dataset.estado ?? 'ninguna') as Estado, tau());
}

/** Pinta los glifos de hilo que hay en `raiz` (después de cada pintada de la barra) y anima los que se mueven. */
export function pintarEn(raiz: HTMLElement): void {
    const todos = [...raiz.querySelectorAll<HTMLCanvasElement>('canvas.glifo-hilo')];
    for (const cv of todos) pintarIcono(cv);
    iconos = [...iconos.filter(c => c.isConnected && !raiz.contains(c)), ...todos.filter(c => ANIMADOS.has(c.dataset.estado as Estado))];
    if (iconos.length) andar();
}

// ── el reloj: un solo requestAnimationFrame, a 30 cuadros, solo con algo que mover ──

let andando = false, ultimo = 0;
function andar(): void {
    if (andando || QUIETO.matches) return;
    andando = true;
    ultimo = performance.now();
    requestAnimationFrame(cuadro);
}
function cuadro(ahora: number): void {
    const campo = vivo?.cv.isConnected ? vivo : null;
    iconos = iconos.filter(c => c.isConnected);
    if ((!campo && !iconos.length) || QUIETO.matches) { andando = false; return; }
    if (!document.hidden && ahora - ultimo >= CUADRO - 4) {
        const dt = Math.min(.1, (ahora - ultimo) / 1000);
        ultimo = ahora;
        if (campo) { campo.fase = (campo.fase + dt / campo.p.ciclo) % 1; campo.tau += dt; pintarCampo(); }
        for (const cv of iconos) if (cv.offsetParent) pintarIcono(cv);
    } else if (document.hidden) ultimo = ahora;
    requestAnimationFrame(cuadro);
}
QUIETO.addEventListener?.('change', () => { if (!QUIETO.matches) andar(); });
