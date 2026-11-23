// La pantalla: lo que llena la columna de la derecha, sea un hilo o una app del dashboard (ahora, tareas, proyectos, la
// pestaña de un módulo). Tiene siempre dos partes, una encima de la otra:
//
//   ┌ barra ────────────────────────────────────────────────────────────────────────────┐
//   │ ‹ NOMBRE  [vistas: ◎ ≡]  resumen                              [acciones: ↻ ⚙ ⧉]   │
//   ├ cuerpo ───────────────────────────────────────────────────────────────────────────┤
//   │ lo de la app, pegado a los bordes: sus líneas llegan a la línea de la columna     │
//   └───────────────────────────────────────────────────────────────────────────────────┘
//
// · la barra: una fila, con el fondo de barra de borde a borde y una línea abajo. Adelante, «‹» si se vino de otra
//   pantalla (la ficha de una tarea vuelve a su lista); el nombre de la app en su
//   color (en un hilo no va: lo dice la cabecera de la página); después, sus vistas, las formas de mirar lo mismo
//   (foco y lista, el día y la semana, la terminal y la lectura), cada una un ícono en su celda cuadrada, la que se ve
//   en violeta; después, lo que resume (una cuenta, la fecha), tenue; y a la derecha sus acciones, también íconos. Una
//   palabra va solo donde un ícono no alcanza (la carpeta de un hilo, que es una ruta).
// · el cuerpo: sin margen propio. Lo que trae va de borde a borde: un separador, la cabecera de una tabla o la línea
//   de una sección tocan la línea de la columna de la izquierda. El aire está dentro de cada fila (--pantalla-margen),
//   no alrededor.
//
// Da HTML, como el resto de la página: un clic en una vista o una acción lleva `data-accion` y `data-valor`, que
// atiende quien pone la barra (el dashboard, dashboard/vista.ts; un hilo, navegador/app.ts). Cómo se ve:
// media/css/pantalla.css, sobre los tokens --pantalla-… (tokens.css). El catálogo (/componentes) la muestra.

import { esc } from '../estilo';

/** Una vista de la pantalla: otra forma de mirar lo mismo. El ícono va solo; el nombre es su ayuda (y su texto si no
 *  tiene ícono: la pestaña de un módulo que no declara uno). */
export interface VistaDePantalla {
    accion: string;
    valor?: string;
    icono?: string;
    nombre: string;
    /** la que se ve */
    si?: boolean;
    /** lo que dice el globo, además del nombre (su atajo, qué muestra) */
    ayuda?: string;
}

/** Una acción de la barra: un ícono en su celda cuadrada (o una tecla, la de un atajo que lanza un agente), con su
 *  ayuda. `texto`, solo cuando un ícono no alcanza: va como botón de palabra, aparte. */
export interface AccionDePantalla {
    accion: string;
    valor?: string;
    icono?: string;
    /** una tecla en vez del ícono: un atajo de [atajos] (su letra lanza al agente) */
    tecla?: string;
    texto?: string;
    ayuda: string;
    /** su color, por lo que hace (web/iconos.ts, C): ir azul, cambiar amarillo, agente violeta, hecho verde… */
    tono?: string;
    /** encendida (un filtro puesto) */
    si?: boolean;
}

export interface Barra {
    /** «‹»: volver a de donde se vino (la ficha de una tarea, a su lista), antes del nombre */
    volver?: AccionDePantalla;
    /** el nombre de la app; en un hilo, nada */
    nombre?: string;
    /** su tinta (`amarillo`, `cian`): la del nombre; sin ella, la de los títulos */
    color?: string;
    vistas?: VistaDePantalla[];
    /** lo que resume la pantalla, tenue: «28 servicios · 3 ideas», la fecha */
    resumen?: string;
    /** lo mismo, ya armado (HTML de confianza, nunca un dato): un número en su color. Gana sobre `resumen` */
    resumenHtml?: string;
    acciones?: AccionDePantalla[];
}

const atributo = (nombre: string, valor: string | undefined): string =>
    valor === undefined || valor === '' ? '' : ` ${nombre}="${esc(valor)}"`;

/** Un botón de la barra (una vista o una acción): el ícono en su celda cuadrada, o la palabra. `dato`: con qué atributo
 *  lo atiende quien lo pone (`data-accion`, el dashboard; `data-contestar`, la ventana de Contestar). */
function boton(clase: string, accion: string, valor: string | undefined, ayuda: string, dentro: string, extra: string[], dato = 'accion'): string {
    const clases = ['pantalla-boton', clase, ...extra].filter(Boolean).join(' ');
    return `<a class="${clases}" data-${dato}="${esc(accion)}"${atributo('data-valor', valor)}${atributo('title', ayuda)}>${dentro}</a>`;
}

export function vistaDePantalla(v: VistaDePantalla): string {
    const ayuda = v.ayuda ? `${v.nombre}: ${v.ayuda}` : v.nombre;
    const dentro = v.icono ? `<span class="i">${v.icono}</span>` : esc(v.nombre);
    return boton('pantalla-vista', v.accion, v.valor, ayuda, dentro, [v.icono ? 'cuadrada' : 'palabra', v.si ? 'si' : '']);
}

export function accionDePantalla(a: AccionDePantalla, dato = 'accion'): string {
    // la palabra en su span (.txt): una vista angosta puede esconderla y dejar el ícono (la carpeta de un hilo, en el celular)
    const dentro = a.tecla ? `<kbd>${esc(a.tecla)}</kbd>` : (a.icono ? `<span class="i">${a.icono}</span>` : '') + (a.texto ? `<span class="txt">${a.icono ? ' ' : ''}${esc(a.texto)}</span>` : '');
    const forma = a.texto ? 'palabra' : 'cuadrada';
    return boton('pantalla-accion', a.accion, a.valor, a.ayuda, dentro, [forma, a.tono ? `tono-${a.tono}` : '', a.si ? 'si' : ''], dato);
}

/** La barra de una pantalla, en HTML. */
export function barra(b: Barra): string {
    const vistas = b.vistas?.length ? `<span class="pantalla-vistas">${b.vistas.map(vistaDePantalla).join('')}</span>` : '';
    const acciones = b.acciones?.length ? `<span class="pantalla-acciones">${b.acciones.map(a => accionDePantalla(a)).join('')}</span>` : '';
    return `<nav class="pantalla-barra"${b.color ? ` style="--pantalla-c: var(--${esc(b.color)})"` : ''}>`
        + (b.volver ? accionDePantalla(b.volver) : '')
        + (b.nombre ? `<span class="pantalla-nombre">${esc(b.nombre)}</span>` : '')
        + vistas
        + (b.resumenHtml || b.resumen ? `<span class="pantalla-resumen">${b.resumenHtml ?? esc(b.resumen ?? '')}</span>` : '')
        + '<span class="pantalla-lleno"></span>'
        + acciones
        + '</nav>';
}
