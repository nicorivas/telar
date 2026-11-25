// Lo que el dashboard, la barra y las órdenes le piden a la página: avisos y diálogos (web/interfaz.ts), abrir
// un enlace, copiar, convertir markdown, y mostrar algo a la derecha (un hilo, una carpeta, una orden `telar.*`).
// Lo de mostrar lo sabe src/navegador/app.ts, que lo pone al arrancar (`usarNavegacion`).

import MarkdownIt from 'markdown-it';

import * as cli from '../cli';
import { modelo } from '../modelo';
import * as interfaz from './interfaz';
import * as portapapeles from './portapapeles';

/** Un ítem de un menú para elegir. `separador`: un título de grupo, no se elige. */
export interface Opcion {
    label: string;
    description?: string;
    /** en un menú junto al puntero: su ícono (web/iconos.ts) y el color de lo que hace (web/iconos.ts, `C`) */
    icono?: string;
    color?: string;
    /** en lugar del ícono, una señal: el HTML de un círculo (componentes/senales.ts, `enLinea`), de confianza */
    senal?: string;
    detail?: string;
    separador?: boolean;
    /** se ve, apagada, y no se elige: su `description` dice por qué (una máquina fuera de línea, por ejemplo) */
    apagada?: boolean;
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

/** Un aviso con botones: `detalle`, lo que va debajo del texto. `destruye`: el primer botón destruye (borrar, quitar,
 *  descartar…): va en el de peligro con su acorde, ⌘⌫, y el foco parte en «cancelar», así que un ⏎ distraído no hace nada.
 *  `foco: 'cancelar'`, para lo que no destruye pero tampoco se hace sin mirar (conceder un permiso para siempre, una acción
 *  que viene de afuera): el foco en «cancelar» y la acción con ⌘⏎. pruebas/confirmar.mjs revisa que cada confirmación que
 *  destruye lo diga. */
export interface OpcionesAviso {
    detalle?: string; foco?: 'cancelar'; destruye?: boolean;
    /** corre dentro del evento del botón apretado: lo que solo se puede en un gesto (interfaz.ts, `preguntar`) */
    enElClic?: (boton: string) => void;
}

function avisoCon(nivel: interfaz.Nivel) {
    /** Un aviso que se va solo; con botones, una caja que espera y devuelve el elegido (undefined si se cerró). */
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        const opciones = botones.find((b): b is OpcionesAviso => typeof b === 'object');
        const detalle = opciones?.detalle;
        if (!nombres.length) { interfaz.avisar(detalle ? `${texto}\n${detalle}` : texto, nivel); return undefined; }
        return interfaz.preguntar(detalle ? `${texto}\n\n${detalle}` : texto, nombres, { foco: opciones?.foco, destruye: opciones?.destruye, enElClic: opciones?.enElClic });
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

/** Un texto largo y a quién mandarlo (web/interfaz.ts, `escribir`): lo escrito y el destino, o undefined. */
export const escribir = (o: interfaz.PedidoEscrito): Promise<{ texto: string; destino: string } | undefined> => interfaz.escribir(o);

/** El menú de una entidad junto a donde se hizo clic (web/interfaz.ts, `menu`), o junto a un elemento (debajo; si no
 *  cabe, encima de él); sin `donde` (una tecla, un comando),
 *  el menú con buscador en el centro, como siempre. El ítem elegido, o undefined. */
export async function menu<T extends Opcion>(opciones: T[], donde?: { x: number; y: number } | Element, titulo = ''): Promise<T | undefined> {
    if (!donde) return elegir(opciones, { titulo });
    const i = await interfaz.menu(opciones, donde, { titulo });
    return i === undefined ? undefined : opciones[i];
}

/** Un menú para elegir uno: el ítem elegido, o undefined. */
export async function elegir<T extends Opcion>(opciones: T[], menu: { titulo?: string; placeholder?: string; inicial?: number } = {}): Promise<T | undefined> {
    const i = await interfaz.elegir(opciones, menu);
    return i === undefined ? undefined : opciones[i];
}

/** Una dirección de afuera, en una pestaña nueva: sin acceso a esta página (`noopener`) ni la dirección de esta, que
 *  puede traer la llave (`noreferrer`). */
export async function abrirExterno(url: string): Promise<void> { window.open(url, '_blank', 'noopener,noreferrer'); }

/** Copia `texto` al portapapeles (web/portapapeles.ts) y lo dice abajo con `dice` (o «copiado: …»). Si el navegador
 *  no lo deja (por http, Safari ya fuera del clic que lo pidió), un aviso con el texto y un botón que copia en su mismo
 *  clic. True si quedó copiado. */
export async function copiar(texto: string, dice = ''): Promise<boolean> {
    const listo = () => { estado(dice || `copiado: ${texto.length > 60 ? `${texto.slice(0, 60)}…` : texto}`, 3000); return true; };
    if (await portapapeles.copiar(texto)) return listo();
    return pedirCopiar(texto, 'Para copiarlo, aprieta Copiar (o ⏎).', listo);
}

/** El aviso que copia en el clic de su botón: `texto` es lo que se copia, `pide` lo que se le dice a la persona (se le
 *  agrega el texto, cortado en `largo`). Si tampoco así (no debería), queda dicho que lo seleccione y lo copie a mano. */
export async function pedirCopiar(texto: string, pide: string, listo: () => boolean, largo = 70): Promise<boolean> {
    let copiado: Promise<boolean> = Promise.resolve(false);
    const muestra = texto.replace(/\s+/g, ' ').trim();
    const r = await info(`${pide}\n«${muestra.length > largo ? `${muestra.slice(0, largo)}…` : muestra}»`, 'Copiar',
        { enElClic: b => { if (b === 'Copiar') copiado = portapapeles.copiarEnElGesto(texto); } });
    if (r !== 'Copiar') return false;
    if (await copiado) return listo();
    void falla(`No quedó copiado. Selecciónalo y cópialo con ⌘C:\n${texto}`);
    return false;
}

const md = new MarkdownIt({ html: false, linkify: true });
/** Markdown a HTML (sin el HTML que traiga: se escapa). */
export const markdown = (texto: string): string => md.render(texto);
/** Markdown de una línea (el valor de un dato), sin párrafo alrededor. */
export const markdownLinea = (texto: string): string => md.renderInline(texto);

// ── mostrar algo a la derecha: lo sabe la página (src/navegador/app.ts) ──

interface Navegacion {
    /** «dashboard», un hilo, «rem:<máquina>:<hilo>», «doc:<hilo>», «arch:<ruta>», «obj:<dirección>» */
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

/** La dirección de un objeto de telar (`tarea:T366`, `hilo:Telar`, `archivo:x.md`, la de un tipo de un módulo): la
 *  página decide dónde se ve (navegador/app.ts). */
export async function abrirDireccion(direccion: string): Promise<void> { nav?.mostrar(`obj:${direccion}`); }

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
