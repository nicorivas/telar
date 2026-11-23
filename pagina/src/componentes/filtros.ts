// Los filtros: los grupos de opciones que eligen qué filas de una lista se ven (las de esta semana, las de un área, las
// mías). Cada opción es una palabra con su cuenta (cuántas filas quedarían si se la eligiera, con lo demás que está
// filtrado), y la que rige va en el acento. Un clic en la que rige la suelta: el grupo vuelve a lo de siempre (su
// `siempre`, o ninguna), como el orden. Todo en una fila, tras el ícono padre (`I.filtro`) que dice «lo que sigue filtra»;
// entre un grupo y otro, más aire que entre sus opciones (un corte quedaba colgando cuando la fila se parte). Si no cabe,
// se parte por grupos: el que no cabe baja entero al renglón siguiente.
//
// Un grupo plegado muestra solo lo que rige (o su nombre, si no rige ninguna) y un ⌄; sus opciones siguen en el HTML,
// escondidas (y con sus cuentas al día), y un clic en él las abre en un menú: quien lo usa lo atiende
// (`data-accion="filtro-abrir"`, con `data-id` el grupo) y lee lo que va en el menú con `leerGrupo`. Plegado va lo que
// se elige una vez y se deja (el área); a la vista, lo que se cambia seguido (el modo).
//
// Un grupo de varias (`activas`) deja elegir más de una a la vez: rigen todas las que están en el acento, y un clic prende
// o apaga una sin tocar las demás. Quién lo usa decide qué
// pasa si no queda ninguna; su `siempre` es la opción que las suelta todas («todas»).
//
// Este componente es la marca; lo que hace (esconder filas, recontar, recordar lo elegido) lo atiende la vista que lo
// usa: le llega `data-accion` (`filtro`) con `data-id` (`grupo:clave`), y con `marcarFiltros` y `contarFiltro` pone la
// que rige y las cuentas sin redibujar. Cómo se ve: media/css/filtros.css. Su página, en /componentes: «filtros».

import { esc } from '../estilo';
import { I } from '../web/iconos';

/** Una opción: su clave, su palabra (o un ícono de la letra) y cuántas filas deja. */
export interface OpcionFiltro {
    clave: string;
    nombre: string;
    cuenta?: number;
    /** lo que dice el globo: qué filas deja */
    ayuda?: string;
}

export interface GrupoFiltro {
    clave: string;
    /** cómo se llama el grupo: el globo, y lo que dice plegado cuando no rige ninguna («área») */
    nombre: string;
    opciones: OpcionFiltro[];
    /** la clave que rige ahora, o '' si ninguna */
    activa: string;
    /** un grupo de varias: las que rigen ahora (manda sobre `activa`) */
    activas?: readonly string[];
    /** la que rige si se suelta la activa ('' si ninguna: el grupo no filtra) */
    siempre?: string;
    /** plegado: solo lo que rige, y sus opciones en un menú */
    plegado?: boolean;
}

export interface PropsFiltros {
    grupos: GrupoFiltro[];
    /** la orden de la página que cumple un clic en una opción */
    accion?: string;
    /** clases de la vista, además de `filtros` */
    clase?: string;
}

const opcion = (g: GrupoFiltro, o: OpcionFiltro, accion: string): string => {
    const si = g.activas ? g.activas.includes(o.clave) : o.clave === g.activa;
    const suelta = si && o.clave !== (g.siempre ?? '') ? ' (clic: soltarlo)' : g.activas && !si && o.clave !== (g.siempre ?? '') ? ' (clic: sumarlo)' : '';
    return `<button type="button" class="filtros-op${si ? ' si' : ''}${o.cuenta === 0 ? ' cero' : ''}" data-accion="${esc(accion)}"`
        + ` data-id="${esc(`${g.clave}:${o.clave}`)}" aria-pressed="${si}" title="${esc(`${o.ayuda ?? o.nombre}${suelta}`)}">`
        + `<span class="filtros-op-nombre">${esc(o.nombre)}</span>${o.cuenta === undefined ? '' : ` <span class="filtros-cuenta">${o.cuenta}</span>`}</button>`;
};

export function filtros(p: PropsFiltros): string {
    const accion = p.accion ?? 'filtro';
    const grupos = p.grupos.filter(g => g.opciones.length);
    if (!grupos.length) return '';
    // el padre va dentro del primer grupo: si la fila se parte, no queda solo en su renglón
    const padre = `<span class="filtros-padre i" title="filtrar la lista">${I.filtro}</span>`;
    const grupo = (g: GrupoFiltro, i: number): string => {
        const ops = (i ? '' : padre) + (g.plegado ? `<span class="filtros-nombre">${esc(g.nombre)}</span>` : '')
            + g.opciones.map(o => opcion(g, o, accion)).join('') + (g.plegado ? `<span class="filtros-abrir i">${I.abierto}</span>` : '');
        if (!g.plegado) return `<span class="filtros-grupo" data-grupo="${esc(g.clave)}">${ops}</span>`;
        return `<span class="filtros-grupo plegado" data-grupo="${esc(g.clave)}" data-accion="filtro-abrir" data-id="${esc(g.clave)}"`
            + ` title="${esc(`${g.nombre}: elegir`)}">${ops}</span>`;
    };
    return `<div class="filtros${p.clase ? ` ${esc(p.clase)}` : ''}">${grupos.map(grupo).join('')}</div>`;
}

/** Pone la que rige en un grupo, sin redibujar: la marca, `aria-pressed` y lo que dice su globo. */
export function marcarFiltros(raiz: ParentNode, grupo: string, activa: string, siempre = ''): void {
    for (const b of raiz.querySelectorAll<HTMLElement>(`.filtros-grupo[data-grupo="${CSS.escape(grupo)}"] .filtros-op`)) {
        const k = (b.dataset.id ?? '').slice(grupo.length + 1), si = k === activa;
        b.classList.toggle('si', si);
        b.setAttribute('aria-pressed', String(si));
        b.title = b.title.replace(/ \(clic: soltarlo\)$/, '') + (si && k !== siempre ? ' (clic: soltarlo)' : '');
    }
}

/** Lo que dice un grupo ahora (su nombre, sus opciones con la que rige y sus cuentas al día): lo que muestra el menú
 *  de uno plegado. */
export function leerGrupo(g: HTMLElement): { nombre: string; opciones: { id: string; nombre: string; cuenta?: number; ayuda: string; si: boolean }[] } {
    return {
        nombre: g.querySelector('.filtros-nombre')?.textContent ?? '',
        opciones: [...g.querySelectorAll<HTMLElement>('.filtros-op')].map(b => {
            const c = b.querySelector('.filtros-cuenta')?.textContent;
            return { id: b.dataset.id ?? '', nombre: b.querySelector('.filtros-op-nombre')?.textContent ?? '', cuenta: c ? Number(c) : undefined,
                ayuda: b.title.replace(/ \(clic: soltarlo\)$/, ''), si: b.classList.contains('si') };
        }),
    };
}

/** Cambia la cuenta de una opción (lo que dejaría con lo demás que está filtrado); en cero, apagada. */
export function contarFiltro(b: HTMLElement, n: number): void {
    const c = b.querySelector('.filtros-cuenta');
    if (c) c.textContent = String(n);
    b.classList.toggle('cero', n === 0);
}
