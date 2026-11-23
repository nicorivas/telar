// La tarjeta: una cosa entera que se mira y se decide de a una, entre pocas. Es un ítem que no se corta, con sus mismas
// piezas repartidas en tres partes, como la tarjeta de shadcn/ui (CardHeader con su CardAction, CardContent,
// CardFooter). Su anatomía, con lo que responde cada parte, está en componentes/anatomia.ts (la lámina del catálogo):
//
//   ┌ .tarjeta-cabecera ─────────────────────────────────────────────────────────────────┐
//   │ inicio      título: entero, en varias líneas (hasta --tarjeta-lineas;     acciones ⋯ │
//   │ ● ○         holgada, sin tope), cortado con «…» si no cabe                           │
//   ├ .tarjeta-cuerpo (si tiene) ─────────────────────────────────────────────────────────┤
//   │             lo que se lee además del título                                          │
//   ├ .tarjeta-pie (si tiene) ────────────────────────────────────────────────────────────┤
//   │             dato   dato   dato                                        aviso   meta   │
//   └──────────────────────────────────────────────────────────────────────────────────────┘
//
// Las tres partes comparten las columnas de la tarjeta (inicio · contenido · acciones): el cuerpo y el pie empiezan donde
// empieza el título, y lo que va pegado a la derecha del pie queda bajo las acciones.
//
// En la gramática visual es una fila (una de varias iguales) más alta, no una caja: no lleva marco (un marco es de lo que
// se abre aparte, una ventana) ni fondo propio. Las tarjetas de una lista se apartan con aire (--tarjeta-aire); la elegida
// lleva el fondo de la selección, como el ítem activo. Lo que dice cada pieza sale de las señales (componentes/senales.ts):
// un estado es un círculo en su ranura, algo que no cuadra va en el color de su alerta; nunca una raya de color ni un borde.
//
// Da HTML, como el ítem, y lleva también su clase (`item`): toma de él el hover, la selección y el arrastre. Cómo se ve:
// media/css/tarjeta.css, sobre los tokens --tarjeta-… (tokens.css, densidades.css). Su página en /componentes,
// «tarjeta». La usa foco (vistas/dashboard/foco.ts), para las tareas.

import { esc } from '../estilo';
import { accion, pieza, type Accion, type Pieza } from './item';

export interface Tarjeta {
    // ── la cabecera: qué es y qué se le hace ──
    /** las ranuras del inicio, en orden, a la altura de la primera línea del título; `null` es una vacía */
    inicio?: (Pieza | null)[];
    /** antes del título, en su misma línea: de qué clase es, o lo que le pasó */
    prefijo?: Pieza[];
    /** el título, en texto (se escapa); o `tituloHtml`, ya armado */
    titulo?: string;
    tituloHtml?: string;
    /** las acciones, arriba a la derecha, en su columna; el ⋯ siempre al último */
    acciones?: Accion[];
    menu?: Accion;

    // ── el cuerpo, si tiene: lo que se lee además del título ──
    cuerpo?: string;
    cuerpoHtml?: string;

    // ── el pie: sus datos, y pegados a la derecha el aviso y la meta ──
    datos?: Pieza[];
    aviso?: Pieza;
    meta?: Pieza;

    // ── cómo está ──
    /** la elegida: el fondo de la selección, y sus acciones a la vista */
    activa?: boolean;
    /** con más aire y el título sin tope de líneas: de a pocas, para leerlas enteras */
    holgada?: boolean;
    apagada?: boolean;
    saliendo?: boolean;
    /** se puede arrastrar (a una casilla, a otra lista) */
    arrastrable?: boolean;

    // ── lo que hace y lo que lleva ──
    /** lo que hace un clic en ella (las acciones llevan el suyo) */
    accion?: string;
    id?: string;
    /** más `data-*` de quien la usa (el `valor` de su acción, lo que lleva al arrastrarla) */
    datosHtml?: Record<string, string>;
    ayuda?: string;
    clases?: string[];
}

const atributo = (nombre: string, valor: string | undefined): string =>
    valor === undefined || valor === '' ? '' : ` ${nombre}="${esc(valor)}"`;

/** La tarjeta, en HTML: su cabecera, su cuerpo si tiene y su pie si tiene. */
export function tarjeta(p: Tarjeta): string {
    const clases = ['item', 'tarjeta', p.activa ? 'activa' : '', p.holgada ? 'holgada' : '', p.apagada ? 'apagada' : '',
        p.saliendo ? 'saliendo' : '', ...(p.clases ?? [])].filter(Boolean).join(' ');
    const datos = Object.entries(p.datosHtml ?? {}).map(([k, v]) => atributo(`data-${k}`, v)).join('');
    const abre = `<div class="${clases}"${atributo('data-accion', p.accion)}${atributo('data-id', p.id)}${datos}`
        + `${p.arrastrable ? ' draggable="true"' : ''}${atributo('title', p.ayuda)}>`;
    return `${abre}${cabecera(p)}${cuerpo(p)}${pie(p)}</div>`;
}

/** La cabecera: el inicio (las ranuras), el título con su prefijo, y las acciones con el ⋯. */
function cabecera(p: Tarjeta): string {
    const inicio = p.inicio?.length
        ? `<span class="item-inicio">${p.inicio.map(r => r ? pieza(r, 'item-ranura') : '<span class="item-ranura"></span>').join('')}</span>` : '';
    const titulo = '<div class="tarjeta-titulo">'
        + (p.prefijo ?? []).map(x => `${pieza(x, 'item-prefijo')} `).join('')
        + `<span class="item-titulo">${p.tituloHtml ?? esc(p.titulo ?? '')}</span></div>`;
    const botones = [...(p.acciones ?? []).map(a => accion(a)), ...(p.menu ? [accion(p.menu, 'item-menu')] : [])];
    const acciones = botones.length ? `<span class="tarjeta-acciones">${botones.join('')}</span>` : '';
    return `<div class="tarjeta-cabecera">${inicio}${titulo}${acciones}</div>`;
}

/** El cuerpo, si tiene. */
function cuerpo(p: Tarjeta): string {
    const html = p.cuerpoHtml ?? (p.cuerpo ? esc(p.cuerpo) : '');
    return html ? `<div class="tarjeta-cuerpo">${html}</div>` : '';
}

/** El pie, si tiene: los datos, y al final (pegados a la derecha) el aviso y la meta. */
function pie(p: Tarjeta): string {
    const fin = (p.aviso ? pieza(p.aviso, 'item-aviso') : '') + (p.meta ? pieza(p.meta, 'item-meta') : '');
    if (!p.datos?.length && !fin) return '';
    return `<div class="tarjeta-pie">${(p.datos ?? []).map(x => pieza(x, 'tarjeta-dato')).join('')}`
        + `${fin ? `<span class="tarjeta-fin">${fin}</span>` : ''}</div>`;
}

/** Varias tarjetas, una debajo de otra, apartadas con aire. */
export const listaTarjetas = (tarjetas: string[], clase = ''): string =>
    `<div class="lista-tarjetas${clase ? ` ${clase}` : ''}">${tarjetas.join('')}</div>`;
