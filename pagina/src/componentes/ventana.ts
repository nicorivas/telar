// La ventana: lo que se abre aparte, encima de la página, para decidir algo o elegir entre cosas (⌘K, «elegir», el menú ⋯, la
// instrucción). Este componente es el **marco**: cabecera (título y ayuda), campo, cuerpo y pie, en ese orden y cada parte solo si
// se pide. Da el HTML de lo que va *dentro* de un `<dialog>` (o de una muestra del catálogo): abrirlo (showModal/show), el foco, ⎋ y
// el clic fuera lo atiende quien la usa. Tres variantes de lugar —`centrada`, `arriba` (⌘K) y `junto` al clic (el menú ⋯)— que solo
// cambian dónde se pone y cuánto ocupa (el CSS), no lo que lleva. `paleta` es la ventana con campo y una lista de filas (ítems):
// ⌘K, «elegir» y el menú ⋯ son ese mismo patrón con CSS distinto. Cómo se ve: media/css/ventana.css, sobre los tokens --ventana-….
// Abrirla de verdad (el <dialog>, el foco, ⎋, el clic fuera) es `abrirVentana`, en web/ventana.ts. La usa la de contestar lo que te
// espera (componentes/contestar.ts); las que ya existían se migran aparte (docs/propuestas/componentes.md, «Las ventanas»).

import { esc } from '../estilo';
import { item, type Item } from './item';
import { pieBotones, type Boton } from './boton';
import { barraBuscar } from './buscador';

export type LugarVentana = 'centrada' | 'arriba' | 'junto';

export interface PropsVentana {
    lugar?: LugarVentana;
    titulo?: string;
    /** lo que explica el título, tenue */
    ayuda?: string;
    /** HTML ya armado: junto al título, delante (el estado de lo que muestra: la estrella de una tarea) */
    iconos?: string;
    /** HTML ya armado: lo que se le hace a lo que muestra, a la derecha del título (la barra de una tarea, en Contestar) */
    herramientas?: string;
    /** HTML ya armado: el campo, de borde a borde bajo la cabecera (la barra de un buscador: `barraBuscar()`) */
    campo?: string;
    /** HTML ya armado: lo que la ventana lleva (una lista, un texto) */
    cuerpo?: string;
    /** HTML ya armado: lo que va abajo (las teclas, los botones) */
    pie?: string;
    /** clases de quien la usa, además de `ventana` */
    clase?: string;
}

/** Los botones de abajo (componentes/boton.ts, «la tecla en el pie»): una banda partida en celdas, tras una línea y un espacio
 *  que la apartan del contenido; lo que hace primero y «cancelar» (⎋) al último, en el borde derecho. */
export const pieVentana = (acciones: Boton[]): string => pieBotones(acciones);

export function ventana(p: PropsVentana): string {
    const parte = (clase: string, html: string | undefined) => html ? `<div class="ventana-${clase}">${html}</div>` : '';
    const titulo = p.titulo ? `<div class="ventana-titulo">${esc(p.titulo)}</div>` : '';
    // con íconos o herramientas, el título va en una línea con ellos: los íconos delante, las herramientas al final
    const linea = p.iconos || p.herramientas
        ? `<div class="ventana-linea">${p.iconos ? `<span class="ventana-iconos">${p.iconos}</span>` : ''}${titulo || '<span class="ventana-titulo"></span>'}`
            + `${p.herramientas ? `<span class="ventana-herramientas">${p.herramientas}</span>` : ''}</div>`
        : titulo;
    const cab = linea || p.ayuda
        ? `<div class="ventana-cabecera">${linea}${p.ayuda ? `<div class="ventana-ayuda">${esc(p.ayuda)}</div>` : ''}</div>`
        : '';
    return `<div class="ventana ${p.lugar ?? 'centrada'}${p.clase ? ` ${esc(p.clase)}` : ''}">${cab}${parte('campo', p.campo)}${parte('cuerpo', p.cuerpo)}${p.pie ?? ''}</div>`;
}

export interface PropsPaleta extends Omit<PropsVentana, 'campo' | 'cuerpo'> {
    /** en qué se busca, sin el verbo (buscador.ts) */
    placeholder?: string;
    /** las filas, como ítems; `sel` es la marcada (↑ ↓) */
    filas: Item[];
    sel?: number;
    /** lo que dice cuando el filtro no deja nada */
    vacia?: string;
    /** una explicación de la marcada, entera, bajo la lista */
    detalle?: string;
}

/** La ventana de campo + lista filtrable (↑ ↓ ⏎ ⎋): el campo es la barra de un buscador, las filas son ítems, la marcada
 *  es la `activa`. */
export function paleta(p: PropsPaleta): string {
    const { placeholder, filas, sel, vacia, detalle, ...resto } = p;
    const lista = filas.length
        ? filas.map((f, i) => item({ ...f, activa: i === sel })).join('')
        : `<div class="ventana-vacia">${esc(vacia ?? 'nada calza')}</div>`;
    return ventana({ ...resto, campo: barraBuscar({ placeholder: placeholder ?? 'opciones' }),
        cuerpo: `<div class="ventana-lista">${lista}</div>${detalle ? `<div class="ventana-detalle">${esc(detalle)}</div>` : ''}` });
}
