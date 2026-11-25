// La ventana de mundos en la página: la abre ⌘M (Ctrl+M fuera del Mac), un clic en el mundo de la banda y «cambiar de
// mundo» en ⌘K (navegador/app.ts). Lo que dibuja es componentes/mundos-ventana.ts; aquí, lo vivo:
//
// · las tarjetas salen de los mundos de la configuración (web/mundo.ts) y del que está puesto, a la hora de abrirla;
// · elegir una (un clic, un toque, su número o ⏎ con el foco en ella) la pone como la banda (`mundo.poner`); «volver al
//   horario» (h) suelta lo elegido a mano; «editar» (e) lleva a ⚙ mundos; ⎋ o un clic afuera la cierran sin cambiar nada;
// · los números: hasta nueve tarjetas, cada cifra elige al tiro. Con diez o más, una cifra que puede empezar otro número
//   (el 1 de 10, 11…) espera un momento la segunda (`numero`), con el foco ya en la suya: 1 y 1 es la 11, 1 sola es la 1;
// · son muchas: van en filas hacia abajo y la ventana se desplaza. ← → ↑ ↓ mueven el foco entre tarjetas (arriba y
//   abajo, de a una fila; en una sola fila o columna, de a una), y la que recibe el foco queda siempre a la vista (se
//   desplaza suave, o de golpe con «reducir movimiento»). Al abrir, a la vista la del mundo de ahora. El foco sigue al
//   mouse (sin desplazar nada): lo que se ilumina es lo que pone ⏎;
// · el arte se anima solo mientras está abierta y la pestaña se ve (web/arte-vivo.ts): cerrada, ningún cuadro más. Con
//   «reducir movimiento», quieto;
// · los artes de la raíz (`<raiz>/.telar/arte/*.txt`, `GET /arte`) se leen cada vez que se abre, sin esperarlos: si llegan
//   después, las tarjetas los toman al tiro.
//
// ⌘M otra vez, con ella abierta, la cierra (como ⌘K). En Chrome de macOS ⌘M es «minimizar» del menú Ventana, pero Chrome
// le pasa a la página primero las teclas con ⌘ que no son suyas, y la minimiza solo si la página no la toma
// (content/app_shim_remote_cocoa/render_widget_host_view_cocoa.mm, `performKeyEquivalent:`): por eso aquí se toma con
// `preventDefault`, y en cualquier otra pestaña ⌘M sigue minimizando.

import * as cli from '../cli';
import * as mundo from './mundo';
import { abrirVentana } from './ventana';
import { animar, pideQuieto, type Vivo } from './arte-vivo';
import { propsVentanaMundos, tarjetasDeMundos } from '../componentes/mundos-ventana';
import type { Mundo, MundoPuesto } from '../componentes/modos-mundos';
import { alRegistrar, registrarDeArchivos } from '../componentes/arte';
import '../componentes/arte/index';

/** la que está abierta (su <dialog> y cómo cerrarla): ⌘M otra vez la cierra */
let abierta: { d: HTMLDialogElement; cerrar: () => void } | null = null;

/** Si la ventana está abierta (y sigue en la página: un <dialog> que otro cerró por su cuenta ya no cuenta). */
export const estaAbierta = (): boolean => !!abierta && abierta.d.open !== false && abierta.d.isConnected !== false;
/** El arte vivo de la que está abierta (para las pruebas y el catálogo: cómo va cada uno). */
export const vivoAbierto = (): Vivo | undefined => vivoActual;
let vivoActual: Vivo | undefined;

/** Lo que dicen los artes de la raíz la última vez que se leyeron (por nombre: el error, si no se leyó). */
let erroresArte: Record<string, string> = {};
export const errores = (): Record<string, string> => erroresArte;

/** Leer los artes de la raíz y registrarlos (los que ya no están, se olvidan). Devuelve el error, o "". */
export async function leerArtes(): Promise<string> {
    const r = await cli.artesDeLaRaiz();
    if (!r.datos) return r.error ?? 'no se pudo';
    const { errores } = registrarDeArchivos(r.datos.artes ?? []);
    erroresArte = { ...(r.datos.errores ?? {}), ...errores };
    return '';
}

/** A qué tarjeta va una flecha, entre `n` en `cols` columnas: ← → de a una; ↑ ↓ de a una fila, salvo en una sola fila o
 *  columna (ahí también de a una). Da la vuelta en los bordes. */
export function vecina(i: number, tecla: string, n: number, cols: number): number {
    const filas = Math.ceil(n / Math.max(1, cols));
    const deAUna = filas <= 1 || cols <= 1;
    const paso = tecla === 'ArrowLeft' ? -1 : tecla === 'ArrowRight' ? 1
        : tecla === 'ArrowUp' ? (deAUna ? -1 : -cols) : tecla === 'ArrowDown' ? (deAUna ? 1 : cols) : 0;
    if (!paso) return i;
    const j = i + paso;
    if (Math.abs(paso) === 1) return (j + n) % n;
    // de a una fila: si se sale, a la misma columna de la otra punta (o la última, si esa fila es corta)
    if (j < 0) return Math.min(n - 1, (filas - 1) * cols + (i % cols));
    if (j >= n) return i % cols;
    return j;
}

/** Lo que hace una cifra, con `n` tarjetas y `antes` la cifra que espera (o ""): elegir la tarjeta `elegir` (1…n), o
 *  esperar la segunda con `espera` (la que se elige si no llega), o nada. Hasta nueve, cada cifra elige al tiro; con diez
 *  o más, una que puede empezar otro número espera. */
export function numero(antes: string, cifra: string, n: number): { elegir?: number; espera?: string } {
    if (antes) {
        const dos = Number(antes + cifra);
        if (dos >= 1 && dos <= n) return { elegir: dos };
    }
    const k = Number(cifra);
    if (!(k >= 1 && k <= n)) return {};
    return k * 10 <= n ? { espera: cifra } : { elegir: k };
}

/** cuánto espera la segunda cifra de un número (10, 11…), en ms */
export const ESPERA_CIFRA = 600;

/** Cuántas columnas tiene la grilla como se ve: las tarjetas que caen en la fila de la primera. */
function columnasVistas(tarjetas: HTMLElement[]): number {
    const arriba = tarjetas[0]?.offsetTop;
    if (arriba === undefined) return tarjetas.length || 1;
    return Math.max(1, tarjetas.filter(t => t.offsetTop === arriba).length);
}

export interface OpcionesMundos {
    /** «editar»: llevar a ⚙ mundos */
    editar?: () => void;
    /** lo que hace elegir (de fábrica, poner ese mundo o volver al horario); el catálogo lo cambia para no hacer nada */
    elegir?: (r: { mundo?: string; horario?: boolean }) => void;
    /** sin animar (de fábrica, lo que pida la persona: «reducir movimiento») */
    reducido?: boolean;
    /** de dónde salen las tarjetas (de fábrica, web/mundo.ts: los de la configuración y el puesto); el catálogo da unos de
     *  mentira */
    fuente?: () => { puesto: MundoPuesto; mundos: readonly Mundo[]; fuera: string; ahora?: Date };
}

/** Abre la ventana de mundos (o la cierra, si está abierta). Devuelve lo elegido: `mundo:<clave>` ("" ambos),
 *  `horario`, `editar`, o undefined si se cerró sin elegir. */
export async function abrir(o: OpcionesMundos = {}): Promise<string | undefined> {
    if (abierta && estaAbierta()) { abierta.cerrar(); return undefined; }
    if (abierta) { abierta.cerrar(); abierta = null; }
    const reducido = o.reducido ?? pideQuieto();
    void leerArtes();
    const datos = () => {
        const f = o.fuente?.() ?? { puesto: mundo.puesto(), mundos: mundo.declarados(), fuera: mundo.deFuera() };
        return { p: f.puesto, ts: tarjetasDeMundos(f.puesto, f.mundos, f.ahora ?? new Date(), f.fuera) };
    };
    const { p, ts } = datos();
    let vivo: Vivo | undefined;
    let mia: { d: HTMLDialogElement; cerrar: () => void } | null = null;
    const r = await abrirVentana<string>(propsVentanaMundos(ts, { aMano: p.por === 'a-mano' }), {
        clase: 'ventana-mundos-dialogo',
        foco: '.mt-tarjeta.puesto',
        montar: (d, cerrar) => {
            abierta = mia = { d, cerrar: () => cerrar(undefined) };
            const tarjetas = () => [...d.querySelectorAll<HTMLElement>('.mt-tarjeta')];
            const elegir = (t: HTMLElement | null | undefined) => { if (t) cerrar(`mundo:${t.dataset.mundo ?? ''}`); };
            // la que recibe el foco por teclado queda a la vista: suave, o de golpe con «reducir movimiento»
            const aLaVista = (t: HTMLElement | undefined, suave = !reducido) => t?.scrollIntoView?.({ block: 'nearest', inline: 'nearest', behavior: suave ? 'smooth' : 'auto' });
            const enfocar = (t: HTMLElement | undefined) => { if (!t) return; t.focus({ preventScroll: true }); aLaVista(t); };
            // la cifra que espera la segunda (10, 11…) y su reloj
            let cifra = '', reloj: ReturnType<typeof setTimeout> | undefined;
            const soltarCifra = () => { if (reloj) clearTimeout(reloj); reloj = undefined; cifra = ''; };
            // al abrir, la del mundo de ahora a la vista (abrirVentana le da el foco sin desplazar)
            const alAbrir = setTimeout(() => aLaVista(tarjetas().find(t => t.classList.contains('puesto')), false), 0);
            d.addEventListener('click', e => {
                const t = (e.target as HTMLElement).closest<HTMLElement>('.mt-tarjeta');
                if (!t || !d.contains(t)) return;
                e.preventDefault();
                elegir(t);
            });
            d.addEventListener('keydown', e => {
                if (e.defaultPrevented || e.isComposing || e.metaKey || e.ctrlKey || e.altKey) return;
                const ts = tarjetas();
                if (/^Arrow(Left|Right|Up|Down)$/.test(e.key)) {
                    e.preventDefault();
                    e.stopPropagation();
                    // sin foco en ninguna (en el pie), la flecha lleva a la de ahora
                    const ahora = ts.findIndex(t => t === document.activeElement);
                    const j = ahora < 0 ? Math.max(0, ts.findIndex(t => t.classList.contains('puesto'))) : vecina(ahora, e.key, ts.length, columnasVistas(ts));
                    soltarCifra();
                    enfocar(ts[j]);
                    return;
                }
                // ⏎ en una tarjeta la pone (el pie lo atiende web/botonera.ts: aquí no llega nada suyo); sostenido, no
                const enfocada = ts.find(t => t === document.activeElement);
                if (e.key === 'Enter' && enfocada) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (!e.repeat) elegir(enfocada);
                    return;
                }
                if (/^[0-9]$/.test(e.key)) {
                    const r = numero(cifra, e.key, ts.length);
                    if (r.elegir === undefined && r.espera === undefined) return;
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.repeat) return;
                    soltarCifra();
                    if (r.elegir !== undefined) { elegir(ts[r.elegir - 1]); return; }
                    // espera la segunda cifra, con el foco ya en la de la primera; si no llega, esa
                    cifra = r.espera!;
                    const k = Number(cifra);
                    enfocar(ts[k - 1]);
                    reloj = setTimeout(() => { soltarCifra(); elegir(ts[k - 1]); }, ESPERA_CIFRA);
                }
            });
            // el foco sigue al mouse (sin desplazar nada): lo que se ilumina es lo que pone ⏎
            d.addEventListener('pointermove', e => {
                const t = (e.target as HTMLElement).closest<HTMLElement>('.mt-tarjeta');
                if (t && document.activeElement !== t && e.pointerType === 'mouse') t.focus({ preventScroll: true });
            });
            vivo = vivoActual = animar(d, { reducido });
            // un arte de la raíz que llega con la ventana abierta: cada tarjeta toma el que le toca ahora
            const soltar = alRegistrar(() => {
                const nuevas = datos().ts;
                for (const t of tarjetas()) {
                    const m = nuevas.find(x => x.clave === (t.dataset.mundo ?? ''));
                    const el = t.querySelector<HTMLElement>('[data-arte]');
                    if (m && el && el.dataset.arte !== m.arte) el.dataset.arte = m.arte;
                }
                vivo?.releer();
            });
            return () => { clearTimeout(alAbrir); soltarCifra(); soltar(); vivo?.parar(); if (vivoActual === vivo) vivoActual = undefined; vivo = undefined; if (abierta === mia) abierta = null; };
        },
    });
    if (abierta === mia) abierta = null;
    const elegir = o.elegir ?? (x => { if (x.horario) mundo.volverAlHorario(); else if (x.mundo !== undefined) mundo.poner(x.mundo); });
    if (r?.startsWith('mundo:')) elegir({ mundo: r.slice('mundo:'.length) });
    else if (r === 'horario') elegir({ horario: true });
    else if (r === 'editar') o.editar?.();
    return r === 'no' ? undefined : r;
}

/** ⌘M (Ctrl+M fuera del Mac) abre o cierra la ventana, antes que la terminal se coma la tecla. */
export function montar(o: OpcionesMundos = {}): void {
    window.addEventListener('keydown', e => {
        const mac = /Mac|iPhone|iPad/.test(navigator.platform);
        if (e.code !== 'KeyM' || e.altKey || e.shiftKey || !(mac ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey)) return;
        if (!mundo.declarados().length) return;
        e.preventDefault();
        e.stopPropagation();
        if (!e.repeat) void abrir(o);
    }, true);
}
