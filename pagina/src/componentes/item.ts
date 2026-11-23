// El ítem de una lista: una fila en tres secciones, como el ítem de menú de una barra lateral (el Sidebar de shadcn/ui:
// SidebarMenuButton con su ícono y su texto, SidebarMenuBadge, SidebarMenuAction que aparece al pasar el mouse).
//
//   ┌ inicio ──────┬ texto ───────────────────────┬ fin ──────────────────────────────────┐
//   │ ●  ○  ⇄      │ [prefijo] título [sufijo]    │ [aviso] [meta] [fijas] [│ acciones ⋯] │
//   └──────────────┴──────────────────────────────┴───────────────────────────────────────┘
//
// · inicio: ranuras de íconos de ancho fijo (--item-ranura): el estado, el lugar, la prioridad. Una ranura vacía
//   ocupa su lugar igual, para que los títulos de una lista empiecen todos en la misma columna.
// · texto: el título, que se corta con «…»; antes, un prefijo (el ícono de un agente, «↳» de un hijo); después, un
//   sufijo (◇ público, una cuenta).
// · fin: pegado a la derecha: un aviso (● algo nuevo), la meta (texto tenue: «49m», una tecla), las acciones fijas
//   (▷ abrir, ‹ plegar) y, al pasar el mouse, las demás, que se despliegan desde la derecha y flotan sobre el final sin correrlo,
//   tras un separador tenue; el ⋯ va siempre al último, en el borde. En el celular (.angosto) no hay mouse: el ⋯ se ve
//   siempre y lo demás queda en su menú.
//
// Da HTML, como el resto de la página (la barra compara el que arma con el que tiene, para no redibujar de más). Un
// clic en la fila o en una acción lleva `data-accion` y `data-id`, que atiende quien la pone en la página.
// Cómo se ve: media/css/item.css, sobre los tokens --item-… (tokens.css): sus colores los cambia cada tema
// (temas.css) y sus medidas cada densidad (densidades.css). El catálogo (/componentes) lo muestra en todos sus estados,
// temas y densidades, y su anatomía en una lámina (anatomia.ts).

import { esc } from '../estilo';
import { circulo, type Circulo } from './circulo';

/** El color de una pieza, por lo que significa (los tokens semánticos): cada tema decide cuál es. */
export type Tono = 'tenue' | 'apagado' | 'acento' | 'titulo' | 'exito' | 'atencion' | 'peligro' | 'remoto' | 'agente'
    | 'trabajando' | 'espera' | 'termino' | 'p0' | 'p1' | 'p2' | 'p3';

/** Una pieza chica: un ícono (de la letra `iconos`, web/iconos.ts), un círculo (componentes/circulo.ts: lo que está en
 *  curso se dice con uno que se mueve en su lugar), un texto, o HTML ya armado (el lienzo de un glifo); con su color y
 *  su ayuda (el `title`). */
export interface Pieza {
    icono?: string;
    circulo?: Circulo;
    texto?: string;
    /** HTML de confianza (lo arma la página, nunca un dato): va tal cual */
    html?: string;
    tono?: Tono;
    ayuda?: string;
    /** en una ranura: su ancho en letras, para un texto (el nombre de una máquina) en vez de un ícono */
    ancho?: number;
}

/** Algo que se hace desde el ítem: su ícono o su palabra, y lo que corre (`data-accion`, `data-id`). */
export interface Accion {
    accion: string;
    id?: string;
    icono?: string;
    texto?: string;
    ayuda: string;
    /** su color quieto (si no, tenue); al pasar el mouse, el del texto */
    tono?: Tono;
    /** borra o cierra: al pasar el mouse, rojo */
    peligro?: boolean;
    /** más `data-*` de quien la usa (el `valor` que lleva la acción en el dashboard) */
    datos?: Record<string, string>;
}

/** Qué es la fila: cambia el color del texto (y la cabecera, también el peso). Un **submenú** es una sección dentro de
 *  otra (ARCHIVO dentro de HILOS): su cabecera es una fila más de la lista, con la flecha de plegar en la última ranura
 *  (justo antes de los nombres) y su nombre en la columna de los nombres, en la tinta de las cabeceras, en minúscula y
 *  sin negrita. Sus filas van en la misma grilla que las de la sección. Un solo nivel (docs/propuestas/componentes.md,
 *  «Los submenús»). */
export type Variante = 'normal' | 'enlace' | 'agente' | 'cabecera' | 'submenu';

export interface Item {
    /** el título, en texto (se escapa); o `tituloHtml`, ya armado */
    titulo?: string;
    tituloHtml?: string;
    prefijo?: Pieza[];
    sufijo?: Pieza[];
    /** las ranuras del inicio, en orden; `null` es una vacía (ocupa su lugar) */
    inicio?: (Pieza | null)[];
    aviso?: Pieza;
    meta?: Pieza;
    /** las acciones que se ven siempre, al final */
    fijas?: Accion[];
    /** el ⋯: siempre el último, en el borde derecho; lo único que queda a la vista en el celular */
    menu?: Accion;
    /** las que aparecen al pasar el mouse, antes del ⋯ */
    acciones?: Accion[];

    variante?: Variante;
    activa?: boolean;
    /** sin vida (un hilo cerrado, archivado, un agente sin hilo): el texto tenue */
    apagada?: boolean;
    saliendo?: boolean;
    /** cuántos niveles se corre el texto (un hijo bajo su padre), hasta 3 */
    hondo?: number;
    /** se puede arrastrar */
    arrastrable?: boolean;

    /** lo que hace un clic en la fila (las acciones llevan el suyo) */
    accion?: string;
    id?: string;
    /** más `data-*` de quien la usa (`hilo`, `grupo`, `busca`) */
    datos?: Record<string, string>;
    /** la ayuda de toda la fila */
    ayuda?: string;
    /** más clases, de quien la usa (para encontrarla: `remota`, `hijo`) */
    clases?: string[];
    /** el `id` del elemento */
    ancla?: string;
}

const atributo = (nombre: string, valor: string | undefined): string =>
    valor === undefined || valor === '' ? '' : ` ${nombre}="${esc(valor)}"`;

/** Lo de adentro de una pieza: el ícono en su letra, el círculo, el texto escapado, o el HTML tal cual. */
function contenido(p: Pieza): string {
    return (p.icono ? `<span class="i">${p.icono}</span>` : '') + (p.circulo ? circulo(p.circulo) : '') + (p.texto ? esc(p.texto) : '') + (p.html ?? '');
}

/** Una pieza en su span, con la clase de su lugar (`item-ranura`, `item-aviso`…). */
export function pieza(p: Pieza, clase: string): string {
    const clases = [clase, p.tono ? `tono-${p.tono}` : '', p.ancho ? 'ancha' : ''].filter(Boolean).join(' ');
    return `<span class="${clases}"${atributo('title', p.ayuda)}${p.ancho ? ` style="width: ${p.ancho}ch"` : ''}>${contenido(p)}</span>`;
}

export function accion(a: Accion, clase = ''): string {
    // solo un ícono: su celda es cuadrada, la misma para todos (item.css); con palabra, mide lo que la palabra
    const cuadrada = a.icono && !a.texto ? 'cuadrada' : '';
    const clases = ['item-accion', clase, cuadrada, a.tono ? `tono-${a.tono}` : '', a.peligro ? 'peligro' : ''].filter(Boolean).join(' ');
    const datos = Object.entries(a.datos ?? {}).map(([k, v]) => atributo(`data-${k}`, v)).join('');
    return `<span class="${clases}" data-accion="${esc(a.accion)}"${atributo('data-id', a.id)}${datos}${atributo('title', a.ayuda)}>`
        + `${a.icono ? `<span class="i">${a.icono}</span>` : ''}${a.texto ? esc(a.texto) : ''}</span>`;
}

/** El ítem, en HTML. */
export function item(p: Item): string {
    const clases = ['item', p.variante && p.variante !== 'normal' ? p.variante : '', p.activa ? 'activa' : '',
        p.apagada ? 'apagada' : '', p.saliendo ? 'saliendo' : '', p.hondo ? `hondo${Math.min(3, p.hondo)}` : '',
        ...(p.clases ?? [])].filter(Boolean).join(' ');
    const datos = Object.entries(p.datos ?? {}).map(([k, v]) => atributo(`data-${k}`, v)).join('');
    const abre = `<div class="${clases}"${atributo('id', p.ancla)}${atributo('data-accion', p.accion)}${atributo('data-id', p.id)}${datos}`
        + `${p.arrastrable ? ' draggable="true"' : ''}${atributo('title', p.ayuda)}>`;

    const inicio = p.inicio?.length
        ? `<span class="item-inicio">${p.inicio.map(r => r ? pieza(r, 'item-ranura') : '<span class="item-ranura"></span>').join('')}</span>` : '';

    const titulo = p.tituloHtml ?? esc(p.titulo ?? '');
    const texto = '<span class="item-texto">'
        + (p.prefijo ?? []).map(x => `${pieza(x, 'item-prefijo')} `).join('')
        + `<span class="item-titulo">${titulo}</span>`
        + (p.sufijo ?? []).map(x => ` ${pieza(x, 'item-sufijo')}`).join('')
        + '</span>';

    const flotan = [...(p.acciones ?? []).map(a => accion(a)), ...(p.menu ? [accion(p.menu, 'item-menu')] : [])];
    const fin = [
        p.aviso ? pieza(p.aviso, 'item-aviso') : '',
        p.meta ? pieza(p.meta, 'item-meta') : '',
        ...(p.fijas ?? []).map(a => accion(a)),
        flotan.length ? `<span class="item-acciones">${flotan.join('')}</span>` : '',
    ].join('');

    return `${abre}${inicio}${texto}${fin ? `<span class="item-fin">${fin}</span>` : ''}</div>`;
}
