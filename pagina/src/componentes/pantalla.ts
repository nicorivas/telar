// La pantalla: lo que llena la columna de la derecha, sea un hilo o una app del dashboard (ahora, tareas, proyectos, la
// pestaña de un módulo). Tiene siempre dos partes, una encima de la otra:
//
//   ┌ barra ────────────────────────────────────────────────────────────────────────────┐
//   │ ‹ NOMBRE                                        [vistas: ◎ ≡]  [acciones: ↻ ⚙ ⧉]   │
//   ├ cuerpo ───────────────────────────────────────────────────────────────────────────┤
//   │ lo de la app, pegado a los bordes: sus líneas llegan a la línea de la columna     │
//   └───────────────────────────────────────────────────────────────────────────────────┘
//
// · la barra: una fila, con el fondo de barra de borde a borde y una línea abajo. A la izquierda, solo el título: «‹»
//   si se vino de otra pantalla (la ficha de una tarea vuelve a su lista) y el nombre de la app en su color, con su
//   ícono si lo tiene (en un hilo no va: lo dice la cabecera de la página). A la derecha, los botones: sus vistas, las
//   formas de mirar lo mismo (foco y lista, el día y la semana, la terminal y la lectura), la que se ve en violeta, y
//   sus acciones; cada uno un ícono en su celda cuadrada. Una palabra va solo donde un ícono no alcanza (la carpeta de
//   un hilo, que es una ruta).
//   Nada más: ni una cuenta, ni la fecha, ni «leyendo…», ni un estado. La barra no los acepta (no hay dónde ponerlos:
//   `Barra` no tiene resumen). Lo que la persona necesita va en la pantalla misma (una línea en la lista, su pie) o,
//   si es para quien lo busque, en el globo del título (`ayuda`) o en el de un botón (el ↻ dice cuándo se leyó). La
//   prueba de la página (prueba:pantalla) revisa que no lleve otro texto; en la página, `window.telar.revisarBarra()`.
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
    /** su ícono (web/iconos.ts), antes del nombre */
    icono?: string;
    /** su tinta (`amarillo`, `cian`): la del nombre; sin ella, la de los títulos */
    color?: string;
    /** el globo del título: lo que la pantalla resume, para quien lo busque («31 servicios · 3 ideas», la ruta de un
     *  archivo). Nunca a la vista: la barra lleva solo el título y los botones */
    ayuda?: string;
    /** el nombre tal cual se escribe (el de un archivo), tenue y sin las letras de una cabecera */
    literal?: boolean;
    vistas?: VistaDePantalla[];
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

/** La barra de una pantalla, en HTML: a la izquierda el título, a la derecha los botones. Lee solo lo que `Barra`
 *  declara: lo que traiga además (un `resumen` de antes, pasado sin tipo) no se dibuja. */
export function barra(b: Barra): string {
    const vistas = b.vistas?.length ? `<span class="pantalla-vistas">${b.vistas.map(vistaDePantalla).join('')}</span>` : '';
    const acciones = b.acciones?.length ? `<span class="pantalla-acciones">${b.acciones.map(a => accionDePantalla(a)).join('')}</span>` : '';
    const titulo = b.nombre ? `<span class="pantalla-nombre${b.literal ? ' literal' : ''}"${atributo('title', b.ayuda)}>`
        + (b.icono ? `<span class="i">${b.icono}</span> ` : '') + `${esc(b.nombre)}</span>` : '';
    return `<nav class="pantalla-barra"${b.color ? ` style="--pantalla-c: var(--${esc(b.color)})"` : ''}>`
        + (b.volver ? accionDePantalla(b.volver) : '')
        + titulo
        + '<span class="pantalla-lleno"></span>'
        + vistas
        + acciones
        + '</nav>';
}

/** Lo que una barra ya dibujada lleva fuera de su título y sus botones (el texto suelto, o un elemento que no es
 *  ninguno de los dos): lo que la regla de la barra prohíbe. Vacío si está bien. Lo usan la prueba de la página y
 *  medir (`--js`), sobre la barra de cada pantalla. */
export function fueraDeLaBarra(nav: Element): string[] {
    const fuera: string[] = [];
    const permitido = (el: Element): boolean => el.classList.contains('pantalla-nombre') || el.classList.contains('pantalla-lleno')
        || el.classList.contains('pantalla-boton')
        || ((el.classList.contains('pantalla-vistas') || el.classList.contains('pantalla-acciones'))
            && [...el.children].every(h => h.classList.contains('pantalla-boton'))
            && [...el.childNodes].every(n => n.nodeType !== 3 || !(n.textContent ?? '').trim()));
    for (const n of nav.childNodes) {
        if (n.nodeType === 3) { if ((n.textContent ?? '').trim()) fuera.push((n.textContent ?? '').trim()); continue; }
        if (n.nodeType !== 1) continue;
        const el = n as Element;
        if (!permitido(el)) fuera.push(`${el.className || el.tagName.toLowerCase()}: ${(el.textContent ?? '').trim()}`);
    }
    if (nav.querySelectorAll('.pantalla-nombre').length > 1) fuera.push('más de un título');
    return fuera;
}
