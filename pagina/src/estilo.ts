// El estilo: la letra, los colores y las piezas de texto que todas las vistas comparten. La letra es
// monoespaciada a propósito: esto se mira al lado de la terminal y tiene que leerse como una continuación
// suya, no como otro programa. Los colores, en media/css/tokens.css.

/** Cómo se dibuja cada atención. Las cuatro palabras son las de `telar atencion`. */
export const GLIFO: Record<string, string> = { trabajando: '●', espera: '○', termino: '✓' };

/** Prioridad 1 alta, 2 media, 3 baja; 0 es sin prioridad, que también se ve. */
export const PRIORIDAD: Record<number, string> = { 0: '·', 1: '●', 2: '◐', 3: '○' };

export const NOMBRE_ATENCION: Record<string, string> = {
    trabajando: 'trabajando', espera: 'te espera', termino: 'terminó',
};

export function esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** Un recuadro (media/css/componentes.css): lo que va junto, dentro de un borde. */
export function recuadro(contenido: string): string {
    return `<section class="recuadro">${contenido}</section>`;
}

/** La fila de arriba de un recuadro: «‹ adónde», que corre `accion`, y a la derecha `der` (cómo pasar a otro). */
export function volver(accion: string, adonde: string, der = '', ayuda = `volver a ${adonde}`): string {
    return `<div class="volver"><a data-accion="${esc(accion)}" title="${esc(ayuda)}">‹ ${esc(adonde)}</a>`
        + (der ? `<span class="der">${der}</span>` : '') + '</div>';
}

/** `5400` → `1h30`. Vacío si no hay nada que decir, igual que en la terminal. */
export function duracion(segundos: number | undefined): string {
    const minutos = Math.floor((segundos ?? 0) / 60);
    if (minutos <= 0) return '';
    return minutos >= 60 ? `${Math.floor(minutos / 60)}h${String(minutos % 60).padStart(2, '0')}` : `${minutos}m`;
}

/** «hace cuánto», en palabras. */
export function hace(iso: string | null | undefined): string {
    if (!iso) return '';
    const ms = Date.now() - Date.parse(iso);
    if (Number.isNaN(ms)) return '';
    const min = Math.round(ms / 60000);
    if (min < 60) return `${min} min`;
    if (min < 60 * 24) return `${Math.round(min / 60)} h`;
    return `${Math.round(min / 1440)} d`;
}

/** Lo mismo, corto, para una columna alineada: `49m`, `2h`, `4d`. */
export function haceCorto(iso: string | null | undefined): string {
    return hace(iso).replace(/ min$/, 'm').replace(/ h$/, 'h').replace(/ d$/, 'd');
}

export const hhmm = (iso: string): string => iso.slice(11, 16);

/** Una fecha de correo (RFC 2822) o ISO como «24-sep 12:19»; si no se entiende, tal cual. */
export function fechaCorta(fecha: string): string {
    const t = Date.parse(fecha);
    if (Number.isNaN(t)) return fecha;
    const d = new Date(t);
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    return `${d.getDate()}-${meses[d.getMonth()]} ${d.toTimeString().slice(0, 5)}`;
}

export const limpiarMd = (t: string): string => t.replace(/\*\*/g, '').replace(/`/g, '');

/** Para buscar sin acentos ni mayúsculas. */
export const normalizar = (t: string): string =>
    t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Una llave al azar: la que nombra la memoria de un lienzo (el lienzo la usa para guardar, nunca una ruta). */
export function llaveAlAzar(): string {
    return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}
