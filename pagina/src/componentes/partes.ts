// Las partes: un total partido en lo que lo forma, en una franja. Cada parte es un rectángulo con el ancho de lo que pesa
// y el color de lo que es (la gramática visual: el color dice el tipo), en el orden en que se nombran abajo; entre dos,
// una raya del fondo. Lo que pesa tan poco que no se vería ocupa igual una raya: está, aunque no se mida.
//
//   ┌────────────┬──────┬─┬──────────────┬──────────────────────────────┐
//   │  claude    │inicio│ │    leído     │         conversación         │
//   └────────────┴──────┴─┴──────────────┴──────────────────────────────┘
//
// La usa la hoja «contexto» de la barra de la derecha (web/carga.ts): cuánto pesa cada grupo de lo que carga un hilo.
// Un clic en una parte lleva `data-accion` y `data-id`, como el ítem. Cómo se ve: media/css/partes.css; en el catálogo
// (/componentes#partes), en sus estados.

import { esc } from '../estilo';

export interface Parte {
    /** lo que es (va en `data-id`) */
    clave: string;
    /** cuánto pesa: el ancho sale de su parte en la suma */
    valor: number;
    /** su color: el nombre de un token (`carga-inicio` es `var(--carga-inicio)`) */
    tinta: string;
    ayuda?: string;
    /** la que está abierta abajo: se marca con una raya del texto debajo */
    activa?: boolean;
}

export interface Partes {
    partes: Parte[];
    /** lo que un clic en una parte corre (`data-accion`); sin él, no se aprietan */
    accion?: string;
    ayuda?: string;
}

/** Las partes, en HTML. Una sin valor no se dibuja. */
export function partes(p: Partes): string {
    const vivas = p.partes.filter(x => x.valor > 0);
    const suma = vivas.reduce((s, x) => s + x.valor, 0);
    if (!suma) return `<span class="partes vacia"${p.ayuda ? ` title="${esc(p.ayuda)}"` : ''}></span>`;
    const tramos = vivas.map(x => {
        const pct = (100 * x.valor) / suma;
        const ayuda = x.ayuda ?? `${x.clave}: ${Math.round(pct)}%`;
        return `<span class="parte${x.activa ? ' activa' : ''}" style="flex-grow: ${x.valor}; --parte: var(--${esc(x.tinta)})"`
            + `${p.accion ? ` data-accion="${esc(p.accion)}" data-id="${esc(x.clave)}"` : ''} title="${esc(ayuda)}"></span>`;
    }).join('');
    return `<span class="partes${p.accion ? ' con-accion' : ''}"${p.ayuda ? ` title="${esc(p.ayuda)}"` : ''}>${tramos}</span>`;
}
