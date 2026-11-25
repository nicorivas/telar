// Las pestañas: una barra horizontal para elegir qué se ve debajo, entre pocas cosas hermanas (gestión y concentración
// en foco; los comentarios, las conexiones y los datos del visor; estados y anatomía en el catálogo). Es una fila del alto
// de las barras (--pantalla-barra-alto, como la barra de una pantalla, la de un buscador y la franja de avisos), con su
// línea abajo de borde a borde:
//
//   ┌ pestanas ──────────────────────────────────────────────────────────────────────┐
//   │ [◎ gestión 50] [≡ concentración 16]                                    [fin: ↻] │
//   └─────────────────────────────────────────────────────────────── línea de borde ──┘
//
// · la abierta lleva la superficie de la selección (la gramática visual: «la fila donde estás, la pestaña abierta»), la
//   misma del ítem activo (--item-fondo-activa y la marca del tema), y el texto en su color; las demás, tenues, con el
//   fondo del hover al pasar. Se distinguen por color y por la superficie, nunca por el tamaño ni el peso de la letra.
// · cada una: un ícono (opcional, en su tinta si la tiene), su nombre y su cuenta (tenue, o en el de cuidado). Algo nuevo
//   en una, un punto en la esquina (la gramática: «en la esquina, le pasó algo»).
// · si no caben (web/pestanas.ts, `acomodar`): las que caben, enteras (ícono, nombre y cuenta); las demás, a un «⋯» al
//   final de la fila, que abre un menú con cada una (su ícono, su nombre y su cuenta). La abierta siempre se ve: si es de
//   las que no caben, toma el lugar de la última que cabía. Una que no se ve y tiene algo nuevo (o una cuenta que pide)
//   se nota en el «⋯». Nunca corre de lado.
//
//   ┌ pestanas, angosta ─────────────────────────────────┐
//   │ [◎ ficha] [✎ notas 2] [⋯•]                    [‹]  │   (códigos y contexto, en el menú del «⋯»; el punto: algo
//   └────────────────────────────────────────────────────┘    nuevo en una de ellas)
//
// · el teclado: son un `tablist` de ARIA, con una sola en el orden del tabulador (la abierta). Con el foco en una, ← →
//   pasan a la de al lado y la abren, Inicio y Fin a la primera y la última; el «⋯» es una más en el recorrido, y ⏎,
//   espacio o ↓ abren su menú (web/pestanas.ts, `atender`).
//
// Da HTML, como el resto de la página: cada pestaña lleva la orden de quien la pone (`data-accion` y `data-valor`, que el
// dashboard atiende; o un `href`, en el catálogo). Cómo se ve: media/css/pestanas.css, sobre los tokens --pestana-…
// (tokens.css). Su página en /componentes, «pestañas».

import { esc } from '../estilo';
import { circulo } from './circulo';
import { I } from '../web/iconos';

export interface Pestana {
    /** lo que elige: va en `data-valor` */
    valor: string;
    nombre: string;
    /** un ícono de la letra (web/iconos.ts), antes del nombre */
    icono?: string;
    /** la tinta de su ícono (`azul`, `verde`…: web/iconos.ts, C); sin ella, la del texto */
    color?: string;
    /** cuántas hay debajo: tenue, después del nombre */
    cuenta?: number | string;
    /** la cuenta pide atención (lo que te espera): en el de cuidado */
    cuentaAtencion?: boolean;
    /** algo nuevo en ella: un punto en la esquina, en este tono (`exito`, `atencion`, `acento`, `peligro`, `termino`) */
    nuevo?: string;
    /** lo que dice el globo (además del nombre) */
    ayuda?: string;
    /** se ve, apagada, y no se elige: la ayuda dice por qué (por hacer, sin permiso) */
    apagada?: boolean;
    /** un enlace en vez de una orden (el catálogo: `#item/anatomia`) */
    href?: string;
    /** lo que además lleva, como `data-*` (con qué la reconoce quien la atiende: `{ hoja: 'codigos' }`) */
    datos?: Record<string, string>;
}

export interface PropsPestanas {
    pestanas: Pestana[];
    /** el `valor` de la abierta; '' si la marca quien la pone después (`marcar`, en web/pestanas.ts) */
    activa: string;
    /** la orden de un clic (`data-accion`, que el dashboard atiende), con el valor de la pestaña en `data-valor` */
    accion?: string;
    /** con qué atributo la atiende quien la pone: `accion` (de fábrica: `data-accion`) u otro (`data-contestar`) */
    dato?: string;
    /** de qué son, para un lector de pantalla (`aria-label`) y para volver a encontrarlas al repintar */
    nombre: string;
    /** lo que va al otro extremo de la fila (sus acciones: ↻, un filtro), HTML de confianza */
    fin?: string;
    clases?: string[];
}

const atributo = (nombre: string, valor: string | undefined): string =>
    valor === undefined || valor === '' ? '' : ` ${nombre}="${esc(valor)}"`;

/** Una pestaña: su ícono, su nombre, su cuenta y, si hay algo nuevo, el punto. */
export function pestana(p: PropsPestanas, x: Pestana, enElOrden = x.valor === p.activa): string {
    const si = x.valor === p.activa;
    const clases = ['pestana', si ? 'si' : '', x.icono ? 'con-icono' : '', x.apagada ? 'apagada' : ''].filter(Boolean).join(' ');
    const cuenta = x.cuenta === undefined || x.cuenta === '' ? ''
        : `<span class="pestana-cuenta${x.cuentaAtencion ? ' atencion' : ''}">${esc(String(x.cuenta))}</span>`;
    const globo = [x.nombre + (x.cuenta !== undefined && x.cuenta !== '' ? ` (${x.cuenta})` : ''), x.ayuda].filter(Boolean).join(': ');
    const orden = x.apagada ? '' : x.href ? atributo('href', x.href)
        : `${atributo(`data-${p.dato ?? 'accion'}`, p.accion)}${atributo('data-valor', x.valor)}`;
    const datos = Object.entries(x.datos ?? {}).map(([k, v]) => atributo(`data-${k}`, v)).join('');
    // en el orden del tabulador, solo una: la abierta (o la primera, si todavía no hay)
    return `<a class="${clases}" role="tab" aria-selected="${si}"${x.apagada ? ' aria-disabled="true"' : ''} tabindex="${enElOrden ? 0 : -1}"`
        + datos
        + `${orden}${atributo('title', globo)}${x.color ? ` data-color="${esc(x.color)}" style="--pestana-c: var(--${esc(x.color)})"` : ''}>`
        + (x.icono ? `<span class="i pestana-icono">${x.icono}</span>` : '')
        + `<span class="pestana-nombre">${esc(x.nombre)}</span>${cuenta}`
        + (x.nuevo ? `<span class="pestana-nuevo tono-${esc(x.nuevo)}" aria-label="algo nuevo">${circulo({ tam: 'punto' })}</span>` : '')
        + '</a>';
}

/** El «⋯» de las que no caben: escondido hasta que web/pestanas.ts mida que hace falta (y entonces dice cuáles lleva). */
export const MAS = `<a class="pestanas-mas" role="button" aria-haspopup="menu" tabindex="-1" hidden title="las que no caben">`
    + `<span class="i pestana-icono">${I.menu}</span></a>`;

/** Las pestañas, en HTML: la fila entera, con su «⋯» y lo de su extremo. */
export function pestanas(p: PropsPestanas): string {
    const clases = ['pestanas', ...(p.clases ?? [])].join(' ');
    return `<nav class="${clases}" data-pestanas="${esc(p.nombre)}">`
        + `<span class="pestanas-lista" role="tablist" aria-label="${esc(p.nombre)}">`
        + `${p.pestanas.map((x, i) => pestana(p, x, p.pestanas.some(y => y.valor === p.activa) ? x.valor === p.activa : i === 0)).join('')}</span>`
        + MAS
        + (p.fin ? `<span class="pestanas-fin">${p.fin}</span>` : '')
        + '</nav>';
}
