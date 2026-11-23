// El orden: el grupo de la banda de herramientas que ordena una lista. Un ícono padre (`I.ordenar`) que dice «lo que sigue
// ordena», y tras él las opciones, cada una un ícono en su celda cuadrada; todo entre dos cortes en el púrpura del orden
// (`--orden-linea`, tokens.css). En la gramática visual es un grupo (piezas que hacen una cosa dentro de una banda), y
// sus opciones son acciones: íconos de la letra, nunca círculos (un círculo dice un estado) ni palabras (ocuparían otro
// ancho que la celda). Un clic en la opción que ya rige vuelve al orden de telar (la que lo recibe decide qué hace).
// Cómo se ve: media/css/orden.css. Su página, en /componentes: «orden».

import { esc } from '../estilo';
import { I } from '../web/iconos';

/** Una forma de ordenar: su ícono y lo que ordena («nombre, alfabético»); la ayuda empieza con «ordenar por». */
export interface OpcionOrden { clave: string; icono: string; ayuda: string }

export interface PropsOrden {
    /** de qué lista es: va en el `data-id` de cada opción (`grupo:clave`) */
    grupo: string;
    opciones: OpcionOrden[];
    /** la clave que rige ahora, o '' si la lista va como la da telar */
    activa: string;
    /** la orden de la página que cumple un clic en una opción */
    accion?: string;
}

/** Si es un ícono de la letra (un carácter del área privada): va con su letra primero, no con la del texto (que en otra
 *  máquina puede traer su propio dibujo en ese lugar). */
export const esIcono = (g: string): boolean => {
    const c = g.codePointAt(0) ?? 0;
    return [...g].length === 1 && ((c >= 0xe000 && c <= 0xf8ff) || c >= 0xf0000);
};

/** El corte que aparta el grupo de lo de al lado, en su celda cuadrada y en el color del orden. */
export const CORTE_ORDEN = '<span class="corte de-orden"></span>';

export function orden(p: PropsOrden): string {
    const accion = p.accion ?? 'orden-grupo';
    const opcion = (o: OpcionOrden): string => {
        const si = o.clave === p.activa;
        return `<span class="ord${si ? ' si' : ''}${esIcono(o.icono) ? ' i' : ''}" data-accion="${esc(accion)}" data-id="${esc(`${p.grupo}:${o.clave}`)}"`
            + ` title="${esc(`ordenar por ${o.ayuda}${si ? ' (clic: volver al orden de telar)' : ''}`)}">${o.icono}</span>`;
    };
    return `${CORTE_ORDEN}<span class="orden" title="ordenar la lista"><span class="orden-padre i">${I.ordenar}</span>`
        + p.opciones.map(opcion).join('') + `</span>${CORTE_ORDEN}`;
}
