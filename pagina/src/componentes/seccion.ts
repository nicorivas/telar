// La sección de lista: lo que va entre la cabecera de un grupo y sus filas. Esta primera pieza arma lo que la barra de hilos
// escribía a mano: el separador entre grupos, la banda de herramientas (la barra del buscador, con el orden y lo que se le
// sume a la derecha: buscador.ts, `barraBuscar`) y la fila «nada calza» que la vista muestra cuando el filtro no deja nada.
// La cabecera y las filas son ítems (item.ts). Cómo se ve: media/css/seccion.css. Falta: que `seccion({ cabecera,
// herramientas, filas, vacia })` arme el grupo entero (paso 6, lo que sigue).

import { barraBuscar } from './buscador';
import { orden, type PropsOrden } from './orden';

export interface PropsHerramientas {
    /** de qué lista es: va en el buscador, en el orden y en la fila «nada calza» (`data-grupo`) */
    grupo: string;
    /** en qué busca el buscador, sin el verbo (la lupa ya lo dice): «hilos» */
    placeholder: string;
    /** lo que dice el buscador al pasar el mouse */
    ayuda: string;
    /** el grupo de ordenar; sin él, la banda es solo el buscador */
    orden?: Omit<PropsOrden, 'grupo'>;
    /** lo que va después del orden (ya armado: en HILOS, ver las máquinas) */
    extra?: string;
    /** el estilo inline de la banda y de su fila «nada calza» */
    estilo?: string;
    /** lo que dice la fila cuando el filtro no deja nada */
    vacia?: string;
}

/** Entre un grupo y el siguiente: el aire bajo el de arriba; la línea es la de arriba de la cabecera que sigue (seccion.css). */
export function separador(): string { return '<div class="sep"></div>'; }

/** La banda de herramientas (la barra del buscador, con el orden y lo extra a la derecha) y, tras ella, la fila oculta
 *  «nada calza» que la vista muestra al filtrar. */
export function herramientas(p: PropsHerramientas): string {
    const estilo = p.estilo ? ` style="${p.estilo}"` : '';
    const lo = (p.orden ? orden({ grupo: p.grupo, ...p.orden }) : '') + (p.extra ?? '');
    return barraBuscar({ grupo: p.grupo, placeholder: p.placeholder, ayuda: p.ayuda, claseBarra: 'herram', estilo: p.estilo,
        herramientas: lo || undefined })
        + `<div class="vacia"${estilo} data-grupo="${p.grupo}" hidden>${p.vacia ?? 'nada calza'}</div>`;
}
