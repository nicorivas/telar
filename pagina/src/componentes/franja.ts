// La franja de avisos: una fila arriba de la barra de hilos, del alto de la barra de la pantalla de al lado (sus líneas
// de abajo calzan), con el estado del sistema y de los hilos: la conexión con telar, una fuente que no se pudo leer, una
// terminal reconectándose, una página o una versión nueva. No el trabajo: lo que espera a la persona tiene su lugar
// (Táctica, «te esperan») y aquí no se repite.
//
//   ┌ franja ─────────────────────────┐
//   │ ⚡ sin conexión con telar  +2  ‹ │   ← lo más grave, en su color y con su ícono; «+N», los demás; ‹ pliega la barra
//   ├─────────────────────────────────┤
//   │ ⌄ DASHBOARD                     │
//
// Tranquila, sin avisos, dice en tenue cuándo se leyó la lista por última vez («al día · 18:42»). Un clic abre la lista
// entera: cada aviso con qué pasó, qué hacer cuando se sabe, sus acciones y adónde lleva. A la derecha, en su celda
// cuadrada, el ‹ que pliega la barra entera (es de la barra, no de una sección: por eso va en su primera fila; en el
// teléfono la barra no se pliega y no está). Con la barra plegada queda solo el ícono del aviso; donde no hay barra a la
// vista (el teléfono viendo un hilo, foco), un punto en el color del aviso junto al botón que la abre (`punto`).
//
// Los niveles, de lo más grave a lo menos, cada uno en su color: sin conexión (rojo, y calla lo que necesita a telar), un
// problema (rojo también: algo que un programa declara mal, `[avisos]`), una falla (cuidado), un aviso (el acento) y una
// nota (tenue: lo que se dice sin pedir nada, como una máquina apagada).
//
// Da HTML, como el resto de la página; un clic lleva `data-accion` (`franja-abrir`, `franja-ir`, `franja-accion`,
// `franja-plegar`) y
// `data-clave` (el aviso) y `data-valor` (la acción), que atiende quien la pone (web/franja.ts; el catálogo, solo dice
// qué haría). Lo que se avisa y cuándo se va lo lleva web/avisos.ts. Cómo se ve: media/css/franja.css.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { circulo, type Movimiento } from './circulo';
import * as S from './senales';

export type Nivel = 'conexion' | 'problema' | 'falla' | 'aviso' | 'nota';

/** Los niveles, de lo más grave a lo menos; su nombre, para el globo y la lista. */
export const NIVELES: readonly { nivel: Nivel; nombre: string }[] = [
    { nivel: 'conexion', nombre: 'sin conexión' },
    { nivel: 'problema', nombre: 'problema' },
    { nivel: 'falla', nombre: 'falla' },
    { nivel: 'aviso', nombre: 'aviso' },
    { nivel: 'nota', nombre: 'nota' },
];

/** Una acción de un aviso (reintentar, recargar, instalar, dar por visto): su botón en la lista, con su globo si lo
 *  trae (`ayuda`). */
export interface AccionAviso { id: string; texto: string; ayuda?: string }

/** Un aviso, como se dibuja. */
export interface AvisoFranja {
    /** único: dos avisos con la misma clave son el mismo, y el nuevo reemplaza al de antes */
    clave: string;
    nivel: Nivel;
    /** qué clase de aviso es (la conexión, una fuente, una versión): un ícono de la letra (web/iconos.ts) */
    icono: string;
    /** lo que pasa, corto: va en la franja */
    texto: string;
    /** qué pasó, en una o dos frases (en la lista) */
    detalle?: string;
    /** qué hacer, si se sabe (en la lista) */
    hacer?: string;
    /** desde cuándo, ya dicho («desde las 18:42», «hace 3 min») */
    cuando?: string;
    /** adónde lleva (el hilo, la pestaña, ⚙ versión), dicho: un clic en el aviso va ahí */
    ir?: string;
    acciones?: AccionAviso[];
    /** algo en curso (instalando): en vez del ícono, el círculo de su movimiento */
    curso?: Movimiento;
}

const orden = (n: Nivel) => NIVELES.findIndex(x => x.nivel === n);

/** De lo más grave a lo menos; a igual nivel, como llegaron. */
export function ordenar(avisos: readonly AvisoFranja[]): AvisoFranja[] {
    return avisos.map((a, i) => ({ a, i })).sort((x, y) => orden(x.a.nivel) - orden(y.a.nivel) || x.i - y.i).map(x => x.a);
}

/** Lo que dice la franja: el más grave y cuántos más. */
export function masGrave(avisos: readonly AvisoFranja[]): { aviso?: AvisoFranja; mas: number } {
    const l = ordenar(avisos);
    return { aviso: l[0], mas: Math.max(0, l.length - 1) };
}

export interface Franja {
    avisos: readonly AvisoFranja[];
    /** sin avisos, lo que dice en tenue («al día · 18:42»), y su globo */
    calma?: string;
    calmaAyuda?: string;
    /** la lista desplegada, debajo */
    abierta?: boolean;
    /** la barra plegada: solo el ícono del más grave (la lista se abre igual, más ancha que ella) */
    plegada?: boolean;
    /** con el ‹ que pliega la barra, a la derecha (abierta: plegada, la barra se abre desde su franja angosta) */
    plegable?: boolean;
}

/** El ‹ que pliega la barra: en su celda cuadrada, al final de la franja. */
const plegar = `<a class="franja-plegar" data-accion="franja-plegar" title="plegar la barra de hilos"><span class="i">${I.atras}</span></a>`;

// en su ranura (del ancho de las de la barra, medida en la letra del texto), el ícono o el círculo de lo que está en curso
const icono = (a: AvisoFranja) => `<span class="franja-icono">${a.curso ? circulo({ mov: a.curso }) : `<span class="i">${esc(a.icono)}</span>`}</span>`;
const nombreNivel = (n: Nivel) => NIVELES.find(x => x.nivel === n)?.nombre ?? n;

/** La franja: tranquila, o el aviso más grave con «+N». Con `abierta`, la lista debajo (`lista`). */
export function franja(f: Franja): string {
    const { aviso, mas } = masGrave(f.avisos);
    const plegada = f.plegada ? ' plegada' : '';
    const pliegue = f.plegable && !f.plegada ? plegar : '';
    if (!aviso) {
        return `<div class="franja calma${plegada}"${f.calmaAyuda ? ` title="${esc(f.calmaAyuda)}"` : ''}>`
            + (f.plegada ? '' : `<span class="franja-texto">${esc(f.calma ?? '')}</span>${pliegue}`) + '</div>';
    }
    const ayuda = `${aviso.texto}${aviso.cuando ? ` · ${aviso.cuando}` : ''}${mas ? `\ny ${mas} ${mas === 1 ? 'aviso más' : 'avisos más'}` : ''}\nclic: ${f.abierta ? 'cerrar la lista' : 'qué pasa y qué hacer'}`;
    return `<div class="franja nivel-${aviso.nivel}${plegada}${f.abierta ? ' abierta' : ''}" data-accion="franja-abrir" role="button" aria-expanded="${!!f.abierta}" title="${esc(ayuda)}">`
        + icono(aviso)
        + (f.plegada ? '' : `<span class="franja-texto">${esc(aviso.texto)}</span>${mas ? `<span class="franja-mas">+${mas}</span>` : ''}${pliegue}`)
        + '</div>'
        + (f.abierta ? lista(f.avisos) : '');
}

/** La lista entera, de lo más grave a lo menos: cada aviso con su ícono y lo que pasa (un clic va a su lugar, si tiene
 *  uno), desde cuándo, qué pasó, qué hacer y sus acciones. */
export function lista(avisos: readonly AvisoFranja[]): string {
    const filas = ordenar(avisos).map(a => {
        const clave = ` data-clave="${esc(a.clave)}"`;
        const titulo = `${icono(a)}<span class="franja-aviso-texto">${esc(a.texto)}</span>`
            + (a.cuando ? `<span class="franja-cuando">${esc(a.cuando)}</span>` : '');
        const acciones = [
            ...(a.acciones ?? []).map(x => `<a class="franja-boton" data-accion="franja-accion"${clave} data-valor="${esc(x.id)}"${x.ayuda ? ` title="${esc(x.ayuda)}"` : ''}>${esc(x.texto)}</a>`),
            ...(a.ir ? [`<a class="franja-boton ir" data-accion="franja-ir"${clave} title="ir: ${esc(a.ir)}">${esc(a.ir)} ›</a>`] : []),
        ];
        return `<div class="franja-aviso nivel-${a.nivel}"${clave}>`
            + (a.ir ? `<a class="franja-aviso-tit" data-accion="franja-ir"${clave} title="${esc(nombreNivel(a.nivel))} · clic: ${esc(a.ir)}">${titulo}</a>`
                : `<div class="franja-aviso-tit" title="${esc(nombreNivel(a.nivel))}">${titulo}</div>`)
            + (a.detalle ? `<div class="franja-aviso-det">${esc(a.detalle)}</div>` : '')
            + (a.hacer ? `<div class="franja-aviso-hacer"><span class="franja-que">qué hacer</span> ${esc(a.hacer)}</div>` : '')
            + (acciones.length ? `<div class="franja-aviso-acc">${acciones.join('')}</div>` : '')
            + '</div>';
    });
    return `<div class="franja-lista" role="dialog" aria-label="avisos">${filas.join('') || '<div class="franja-vacia">sin avisos</div>'}</div>`;
}

/** Donde la franja no se ve (el teléfono viendo un hilo, foco): un punto en el color del aviso más grave (componentes/
 *  senales.ts), para ir dentro del botón que la muestra («‹ hilos», salir de foco). Nada si no hay avisos, o si lo más
 *  grave es una nota (no pide nada). */
export function punto(avisos: readonly AvisoFranja[]): string {
    const { aviso, mas } = masGrave(avisos);
    if (!aviso || aviso.nivel === 'nota') return '';
    return `<span class="franja-punto">${S.enLinea(S.avisoSistema(aviso.nivel, `${aviso.texto}${mas ? ` (y ${mas} más)` : ''}`))}</span>`;
}
