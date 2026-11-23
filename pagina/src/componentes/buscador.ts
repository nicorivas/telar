// El buscador: el campo con que se busca o se filtra una lista. Uno solo para toda la página, con una regla: delante, la
// lupa (`I.buscar`), que dice «aquí se busca», y nada más: el campo no dibuja texto de ayuda adentro (18-nov-2026: «el
// placeholder es innecesario»). **En qué** se busca, sin el verbo («hilos», «tareas», «lo que te espera»), el componente lo
// sigue pidiendo (`placeholder`), pero va solo en el `aria-label` y al comienzo de la ayuda al pasar el mouse, junto a por
// qué campos busca y qué hacen ⏎ y ⎋ (`ayuda`). Entre la lupa y el primer carácter, un hueco del ancho de un carácter
// (--buscador-lupa-hueco, 1ch: el espacio de la grilla), igual en todos. La tecla
// que lo enfoca (`atajo`, «/») va al final, tenue, mientras está vacío y sin el foco. Con `cuenta`, lo que el filtro dejó
// («4 de 30») va al final, tenue: el componente pone el lugar y la vista lo llena al escribir (o lo trae puesto, `texto`).
// Con algo escrito, al final un ✕ que lo borra (web/buscadores.ts lo atiende en toda la página: vacía el campo y le avisa a
// la vista con un `input`, como si se hubiera borrado a mano).
//
// Sus estados se ven solo con color, sin mover nada: vacío (la lupa tenue), con el foco (la lupa en el acento),
// escribiendo y con el filtro puesto (lo escrito, en el color del texto, la lupa en el acento y el ✕).
//
// Cuando es una fila propia —arriba de la lista que busca, como bajo HILOS o en lo alto de una ventana— va en una barra
// (`barraBuscar`): del alto de las barras (`--pantalla-barra-alto`), con el aire de una pantalla y su línea abajo de borde a
// borde, que la aparta de la lista y toma el acento mientras se escribe. El campo no lleva borde propio (se eligió entre
// cuatro: el catálogo los muestra, «buscador › bordes»). Lo que acompaña la búsqueda (el orden, ver las máquinas) va a la
// derecha en la misma barra, en sus celdas.
//
// Lo que hace (filtrar sin redibujar, ⎋ borra, ⏎ abre el primero, conservar el foco al repintar) lo atiende la vista que lo
// usa, por el `id`, la `clase` o el `grupo` que le da. Cómo se ve: media/css/buscador.css, sobre los tokens --buscador-….

import { esc } from '../estilo';
import { I } from '../web/iconos';

export interface PropsBuscador {
    /** en qué se busca, sin el verbo (la lupa ya lo dice): «hilos», «tareas», «lo que te espera». No se dibuja en el
     *  campo: va en el `aria-label` y al comienzo de la ayuda al pasar el mouse */
    placeholder: string;
    /** de qué lista es: va en `data-grupo` */
    grupo?: string;
    /** el `id` con que la vista lo encuentra para restaurar su texto y su foco al repintar */
    id?: string;
    /** clases de la vista, además de `buscar` (la vista las usa para encontrarlo) */
    clase?: string;
    /** otros `data-…` (el bloque al que pertenece) */
    datos?: Record<string, string>;
    /** lo que ya está escrito (la vista que se repinta lo devuelve) */
    valor?: string;
    /** la tecla que lo enfoca: al final, tenue, mientras está vacío y sin el foco (la tecla en sí la atiende la vista) */
    atajo?: string;
    /** lo que dice al pasar el mouse: por qué campos busca y qué hacen ⏎ y ⎋ */
    ayuda?: string;
    /** el lugar de la cuenta: su `id` y su clase, para que la vista lo llene; o `texto`, ya puesta */
    cuenta?: { id?: string; clase?: string; texto?: string };
    /** dibujarlo con el foco, quieto (el catálogo: muestra el estado sin poner el foco de verdad) */
    enfocado?: boolean;
}

export interface PropsBarraBuscar extends PropsBuscador {
    /** HTML ya armado: lo que va a la derecha, en la misma barra (el grupo de ordenar, ver las máquinas, un botón) */
    herramientas?: string;
    /** clases de la barra, además de `buscador-barra` (la que la corre en un submenú, la que la vista busca) */
    claseBarra?: string;
    /** el estilo de la barra (un `--lugar`, un `--buscador-margen` propio) */
    estilo?: string;
}

/** La marca que lleva el ✕: web/buscadores.ts la atiende en toda la página. */
export const BORRAR = 'data-buscador-borrar';

/** El campo: la lupa, lo escrito, y al final la cuenta, la tecla y el ✕. */
export function buscador(p: PropsBuscador): string {
    const at = (k: string, v: string | undefined): string => v === undefined ? '' : ` ${k}="${esc(v)}"`;
    // en qué se busca: no se dibuja. El placeholder del input es un espacio, que no se ve pero deja `:placeholder-shown`,
    // con que el CSS sabe si hay algo escrito
    const en = p.placeholder.trim();
    const globo = [en, p.ayuda].filter(Boolean).join(' · ') || undefined;
    const campo = `<input class="buscar${p.clase ? ` ${esc(p.clase)}` : ''}" type="text"${at('id', p.id)}${at('data-grupo', p.grupo)}`
        + Object.entries(p.datos ?? {}).map(([k, v]) => at(`data-${k}`, v)).join('')
        + `${at('value', p.valor)} placeholder=" "${at('aria-label', en || p.ayuda || undefined)} spellcheck="false" autocomplete="off">`;
    const cuenta = p.cuenta
        ? `<span class="buscador-cuenta${p.cuenta.clase ? ` ${esc(p.cuenta.clase)}` : ''}"${at('id', p.cuenta.id)}>${esc(p.cuenta.texto ?? '')}</span>`
        : '';
    const atajo = p.atajo ? `<span class="buscador-atajo" title="${esc(`${p.atajo}: buscar aquí`)}">${esc(p.atajo)}</span>` : '';
    return `<label class="buscador${p.enfocado ? ' enfocado' : ''}"${at('title', globo)}>`
        + `<span class="buscador-lupa i">${I.buscar}</span>${campo}${cuenta}${atajo}`
        + `<span class="buscador-borrar i" ${BORRAR} title="borrar lo escrito · ⎋">${I.cerrar}</span></label>`;
}

/** El buscador como fila propia: una barra con el campo y, a la derecha, sus herramientas. */
export function barraBuscar(p: PropsBarraBuscar): string {
    const { herramientas, claseBarra, estilo, ...campo } = p;
    return `<div class="buscador-barra${claseBarra ? ` ${esc(claseBarra)}` : ''}"${estilo ? ` style="${esc(estilo)}"` : ''}>${buscador(campo)}`
        + (herramientas ? `<span class="buscador-herramientas">${herramientas}</span>` : '') + '</div>';
}

/** Las maneras de dibujar el campo dentro de su barra que se probaron (el catálogo las pone una al lado de otra). La
 *  elegida es la de buscador.css; las otras viven solo en el catálogo (catalogo.css, `.borde-…`). */
export const BORDES: { clave: string; nombre: string; nota: string; elegida?: boolean }[] = [
    { clave: 'linea', nombre: 'su línea', nota: 'como era: el campo con su propia línea abajo, que toma el acento con el foco; con la de la barra, dos líneas' },
    { clave: 'fondo', nombre: 'otro fondo', nota: 'sin borde: el campo en un fondo un poco más claro, del alto de la barra; con el foco, más claro' },
    { clave: 'foco', nombre: 'la línea con el foco', nota: 'sin borde ni fondo: la lupa y el texto; con el foco, la línea de la barra toma el acento, de borde a borde', elegida: true },
    { clave: 'desnudo', nombre: 'solo la lupa', nota: 'sin borde ni fondo, y la línea de la barra no cambia: el foco lo dicen la lupa en el acento y el cursor' },
];
