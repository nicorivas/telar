// Lo que el dashboard, la barra y las órdenes le piden a la página: avisos y diálogos (web/interfaz.ts), abrir
// un enlace, copiar, convertir markdown, y mostrar algo a la derecha (un hilo, una carpeta, una orden `telar.*`).
// Lo de mostrar lo sabe src/navegador/app.ts, que lo pone al arrancar (`usarNavegacion`).

import MarkdownIt from 'markdown-it';

import * as cli from '../cli';
import { modelo } from '../modelo';
import * as interfaz from './interfaz';

/** Un ítem de un menú para elegir. `separador`: un título de grupo, no se elige. */
export interface Opcion {
    label: string;
    description?: string;
    detail?: string;
    separador?: boolean;
}

export interface PedidoCampo {
    titulo?: string;
    /** lo que se explica debajo del título */
    ayuda?: string;
    placeholder?: string;
    valor?: string;
    password?: boolean;
    /** el problema si lo escrito no sirve (se muestra y se sigue escribiendo); undefined si sirve */
    validar?: (texto: string) => string | undefined;
}

/** Un aviso con botones: `detalle`, lo que va debajo del texto. */
export interface OpcionesAviso { detalle?: string }

function avisoCon(nivel: interfaz.Nivel) {
    /** Un aviso que se va solo; con botones, una caja que espera y devuelve el elegido (undefined si se cerró). */
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        const detalle = botones.find((b): b is OpcionesAviso => typeof b === 'object')?.detalle;
        if (!nombres.length) { interfaz.avisar(detalle ? `${texto}\n${detalle}` : texto, nivel); return undefined; }
        return interfaz.preguntar(detalle ? `${texto}\n\n${detalle}` : texto, nombres);
    };
}
export const aviso = avisoCon('aviso');
export const falla = avisoCon('falla');
export const info = avisoCon('info');

/** Una línea que se va sola. */
export function estado(texto: string, ms = 4000): void { interfaz.avisar(texto, 'info', ms); }

/** Mientras corre `trabajo`, se dice que algo pasa (salvo `discreto`: lo que corre no necesita aviso). */
export async function progreso<T>(o: { titulo: string; discreto?: boolean }, trabajo: () => Promise<T>): Promise<T> {
    if (!o.discreto) interfaz.avisar(o.titulo, 'info', 2500);
    return trabajo();
}

/** Un campo para escribir: lo escrito, o undefined si se canceló. Con `validar`, no sale hasta que sirva. */
export async function campo(o: PedidoCampo): Promise<string | undefined> {
    let problema = '';
    let valor = o.valor ?? '';
    for (;;) {
        const r = await interfaz.campo({ titulo: o.titulo, ayuda: o.ayuda, placeholder: o.placeholder, valor, password: o.password, problema });
        if (r === undefined) return undefined;
        problema = o.validar?.(r) ?? '';
        if (!problema) return r;
        valor = r;
    }
}

/** Un menú para elegir uno: el ítem elegido, o undefined. */
export async function elegir<T extends Opcion>(opciones: T[], menu: { titulo?: string; placeholder?: string } = {}): Promise<T | undefined> {
    const i = await interfaz.elegir(opciones, menu);
    return i === undefined ? undefined : opciones[i];
}

/** Una dirección de afuera, en una pestaña nueva: sin acceso a esta página (`noopener`) ni la dirección de esta, que
 *  puede traer la llave (`noreferrer`). */
export async function abrirExterno(url: string): Promise<void> { window.open(url, '_blank', 'noopener,noreferrer'); }

export async function copiar(texto: string): Promise<void> {
    try { await navigator.clipboard.writeText(texto); } catch { /* sin permiso */ }
}

const md = new MarkdownIt({ html: false, linkify: true });
/** Markdown a HTML (sin el HTML que traiga: se escapa). */
export const markdown = (texto: string): string => md.render(texto);

// ── mostrar algo a la derecha: lo sabe la página (src/navegador/app.ts) ──

interface Navegacion {
    /** «dashboard», un hilo, «rem:<máquina>:<hilo>», «doc:<hilo>», «arch:<ruta>» */
    mostrar(que: string): void;
    /** las órdenes `telar.*` (web/ordenes.ts) */
    ordenes: Record<string, (...args: any[]) => unknown>;
}
let nav: Navegacion | undefined;
export function usarNavegacion(n: Navegacion): void { nav = n; }

/** Un archivo o una carpeta del repositorio: en la vista de carpeta (`arch:<ruta>`); lo que no es texto trae un
 *  enlace para bajarlo. */
export async function abrirArchivo(ruta: string): Promise<void> { nav?.mostrar(`arch:${ruta}`); }
export const mostrarCarpeta = abrirArchivo;

/** Ir a un hilo: telar lo crea o lo revive si hace falta (`POST /ir`), y la página lo muestra a la derecha. */
export async function irAHilo(hilo: string, crear = false, remoto = ''): Promise<void> {
    const r = await cli.ir(hilo, crear, remoto);
    if (!r.ok) { interfaz.avisar(`telar: ${r.err.trim() || `no pude ir a «${hilo}»`}`, 'falla'); return; }
    await modelo.sondear().catch(() => undefined);
    nav?.mostrar(remoto ? `rem:${remoto}:${hilo}` : hilo);
}

/** «Ir a la terminal» después de abrir un hilo o encargarle algo: el que quedó al frente en tmux (el que la acción
 *  acaba de abrir), mostrado en la página. */
export async function mostrarTerminal(): Promise<void> {
    await modelo.sondear().catch(() => undefined);
    const activo = modelo.activo;
    if (activo) nav?.mostrar(activo.nombre);
}

/** Una orden `telar.*` (web/ordenes.ts): el menú de un hilo, ir a uno, abrir una sección… */
export async function orden(id: string, ...args: unknown[]): Promise<unknown> {
    const f = nav?.ordenes[id];
    if (f) return f(...args);
    interfaz.avisar(`«${id}» todavía no está en el navegador`, 'aviso');
    return undefined;
}
