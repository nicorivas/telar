// Las casillas: lo que se le hace a la tarjeta elegida de una lista (hoy, las tareas de foco), que es también donde se
// suelta una tarjeta arrastrada. Cada casilla es una acción: un ícono de la letra en el color de lo que hace (web/iconos.ts,
// C: ir azul, cambiar amarillo, el agente violeta, hecho verde, quitar rojo, lo demás cian), sin marco, y su nombre en el
// globo (el `title`). Algunas traen sus **rápidas** al lado, a un clic: lo que la ventana de esa casilla elegiría casi
// siempre (junto a «nueva fecha», hoy, un día más, el viernes, el lunes; junto a «instrucción», trabajarla y bloquear tiempo). Una
// casilla **padre** solo dice de qué son sus rápidas, como el ícono padre del orden (el tamaño: rápida, larga). Las
// casillas van en grupos, por lo que hacen, apartados por un corte (una línea corta en su celda cuadrada).
//
// Al arrastrar no hay globo (el navegador no lo muestra mientras se arrastra): las casillas dicen su nombre mientras dure
// el arrastre, y la que está debajo se marca como «donde caería» (`.encima`, con la marca de `.destino` del ítem).
//
// Van en una banda, una fila de íconos arriba de las tarjetas, como la banda de herramientas de una lista (decidido el
// 13-nov-2026 con la persona, entre tres formas: docs/propuestas/componentes.md, «Las casillas»). En un celular, la
// misma fila, abajo (lo pone la vista).
//
// Da HTML, como el resto de la página: cada casilla y cada rápida lleva `data-accion` (la orden), `data-valor` (lo que
// hace) y `data-suelta` (lo mismo, para cuando se suelta una tarjeta encima). Cómo se ve: media/css/casillas.css. Su
// página en /componentes, «casillas».

import { esc } from '../estilo';

/** Una rápida: lo que la casilla elegiría casi siempre, a un clic y al lado de ella. Una palabra corta («vie 20»,
 *  «larga», «bloquear tiempo»), en el color de su casilla; su nombre entero y lo que hace, en el globo. */
export interface Rapida {
    valor: string;
    /** lo que se ve */
    texto: string;
    /** su nombre, para el globo («el viernes») */
    nombre: string;
    ayuda: string;
}

export interface Casilla {
    /** lo que hace: va en `data-valor` y en `data-suelta` */
    valor: string;
    nombre: string;
    icono: string;
    /** el color de lo que hace, de C (web/iconos.ts): azul, amarillo, violeta, verde, rojo, cian */
    color: string;
    ayuda: string;
    rapidas?: Rapida[];
    /** solo dice de qué son sus rápidas (el tamaño: rápida, larga), como el ícono padre del orden: no se aprieta */
    padre?: boolean;
}

export interface PropsCasillas {
    /** las casillas, en grupos: entre un grupo y otro, un corte */
    grupos: Casilla[][];
    /** la orden de la página que cumple un clic (o soltar una tarjeta) */
    accion: string;
    /** mientras una acción va a telar: no se aprietan, y `haciendo` dice qué pasa (HTML: un círculo que gira y el texto) */
    ocupadas?: boolean;
    haciendo?: string;
    // ── solo para mostrarlas (el catálogo); en la página lo hace el arrastre de verdad ──
    /** se está arrastrando una tarjeta: los nombres a la vista */
    arrastrando?: boolean;
    /** el valor de la casilla (o la rápida) donde caería */
    encima?: string;
    /** el valor de la que tiene el mouse encima */
    hover?: string;
}

const atributo = (nombre: string, valor: string | undefined): string =>
    valor === undefined || valor === '' ? '' : ` ${nombre}="${esc(valor)}"`;

/** Lo que lleva cada casilla y cada rápida: la orden, lo que hace, dónde se suelta, su globo y su color. */
function marca(p: PropsCasillas, clase: string, valor: string, color: string, globo: string): string {
    const clases = [clase, p.encima === valor ? 'encima' : '', p.hover === valor ? 'hover' : ''].filter(Boolean).join(' ');
    return `<a class="${clases}" data-accion="${esc(p.accion)}" data-valor="${esc(valor)}" data-suelta="${esc(valor)}"`
        + ` style="--casilla-c: var(--${esc(color)})"${atributo('title', globo)}>`;
}

function rapida(p: PropsCasillas, c: Casilla, r: Rapida): string {
    return `${marca(p, 'casilla-rapida', r.valor, c.color, `${r.nombre}: ${r.ayuda}`)}${esc(r.texto)}</a>`;
}

function casilla(p: PropsCasillas, c: Casilla): string {
    const dentro = `<span class="i">${c.icono}</span><span class="casilla-nombre">${esc(c.nombre)}</span>`;
    const boton = c.padre
        ? `<span class="casilla padre" style="--casilla-c: var(--${esc(c.color)})"${atributo('title', `${c.nombre}: ${c.ayuda}`)}>${dentro}</span>`
        : `${marca(p, 'casilla', c.valor, c.color, `${c.nombre}: ${c.ayuda}`)}${dentro}</a>`;
    if (!c.rapidas?.length) return boton;
    return `<span class="casilla-con-rapidas">${boton}<span class="casilla-rapidas">${c.rapidas.map(r => rapida(p, c, r)).join('')}</span></span>`;
}

/** Las casillas, en HTML. */
export function casillas(p: PropsCasillas): string {
    const clases = ['casillas', p.ocupadas ? 'ocupadas' : '', p.arrastrando ? 'arrastrando' : ''].filter(Boolean).join(' ');
    const grupos = p.grupos.filter(g => g.length)
        .map(g => `<span class="casillas-grupo">${g.map(c => casilla(p, c)).join('')}</span>`)
        .join('<span class="corte casillas-corte"></span>');
    const haciendo = p.haciendo ? `<span class="casillas-haciendo">${p.haciendo}</span>` : '';
    return `<div class="${clases}">${grupos}${haciendo}</div>`;
}
