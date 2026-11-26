// La sección de lista: un grupo de una lista, entero. Su **cabecera** (un ítem con la flecha de plegar, el título, la
// cuenta y sus acciones, con el «+» de crear al final) y, si está abierta, las **herramientas** (la barra del buscador, con
// el orden y lo que se le sume a la derecha: buscador.ts, `barraBuscar`; y la fila «nada calza» que la vista muestra
// cuando el filtro no deja nada) y las **filas**, o lo que dice cuando no tiene ninguna. Un **submenú** es una sección
// dentro de otra. Entre dos secciones, el **separador** (`secciones`). Y el **plegado**: cómo dejó la persona cada
// cabecera. Da HTML plano, sin un elemento que envuelva el grupo: la cabecera y las filas son hermanas (item.ts), y de
// eso viven el CSS del separador y el arrastre. Cómo se ve: media/css/seccion.css y item.css.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { barraBuscar } from './buscador';
import { item, type Accion, type Item, type Pieza } from './item';
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

/** Entre un grupo y el siguiente: el aire bajo el de arriba; la línea es la de arriba de la cabecera que sigue (seccion.css).
 *  `datos`: más `data-*`, de quien la usa (una lista que se reordena en la página, la de proyectos, la mueve con ellos). */
export function separador(datos: Record<string, string> = {}): string {
    return `<div class="sep"${Object.entries(datos).map(([k, v]) => ` data-${k}="${esc(v)}"`).join('')}></div>`;
}

/** La banda de herramientas (la barra del buscador, con el orden y lo extra a la derecha) y, tras ella, la fila oculta
 *  «nada calza» que la vista muestra al filtrar. */
export function herramientas(p: PropsHerramientas): string {
    const estilo = p.estilo ? ` style="${p.estilo}"` : '';
    const lo = (p.orden ? orden({ grupo: p.grupo, ...p.orden }) : '') + (p.extra ?? '');
    return barraBuscar({ grupo: p.grupo, placeholder: p.placeholder, ayuda: p.ayuda, claseBarra: 'herram', estilo: p.estilo,
        herramientas: lo || undefined })
        + `<div class="vacia"${estilo} data-grupo="${p.grupo}" hidden>${p.vacia ?? 'nada calza'}</div>`;
}

export interface PropsCabecera {
    /** qué sección es: va en `data-id` y es con lo que se recuerda su plegado */
    clave: string;
    /** como se escribe («hilos»): las mayúsculas las pone el tema */
    titulo: string;
    /** cuántas cosas tiene, tenue, tras el título; sin ella o en cero, nada */
    cuenta?: number;
    /** qué es la sección; la cabecera le agrega «: abrir o cerrar» */
    ayuda: string;
    abierta: boolean;
    /** lo que se hace con la sección, siempre a la vista, al final de su cabecera */
    acciones?: Accion[];
    /** el «+» de crear una (acciones.ts, `A.nuevo`): la última acción, para que quede en la misma columna en todas */
    nuevo?: Accion;
    /** el `id` del elemento, para saltar a ella */
    ancla?: string;
    /** lo que hace un clic en ella: de fábrica, `seccion` (la barra la pliega); en el dashboard, donde `seccion` es otra
     *  cosa, la suya (`proy-seccion`) */
    accion?: string;
    /** más `data-*` y clases, de quien la usa (en proyectos: qué sección es y su lugar, para reordenar en la página) */
    datos?: Record<string, string>;
    clases?: string[];
}

export interface PropsSeccion extends PropsCabecera {
    /** la banda bajo la cabecera; sin ella, las filas van pegadas */
    herramientas?: PropsHerramientas;
    /** las filas, ya armadas. Una función: solo se llama si la sección está abierta */
    filas: () => string;
    /** la fila que dice que no hay ninguna, cuando `filas` no da nada */
    vacia?: Item;
}

export interface PropsSubmenu extends Omit<PropsCabecera, 'acciones' | 'nuevo'> {
    /** el ancho en letras de su ranura de la flecha, si en la lista esa columna es ancha (la de las máquinas) */
    ancho?: number;
    /** cuántas ranuras tienen las filas de la lista: la flecha va en la última, justo antes de los nombres (de fábrica,
     *  3: las de HILOS) */
    ranuras?: number;
    filas: () => string;
}

const flecha = (abierta: boolean): Pieza => ({ icono: abierta ? I.abierto : I.plegado });
const cuantas = (n: number | undefined): Pieza[] => n ? [{ texto: String(n), tono: 'tenue' }] : [];
/** Lo que comparten la cabecera de una sección y la de un submenú: un clic en toda la fila la abre o la pliega. */
const deCabecera = (p: Omit<PropsCabecera, 'acciones' | 'nuevo'>): Item => ({ ancla: p.ancla, accion: p.accion ?? 'seccion', id: p.clave,
    ayuda: `${p.ayuda}: abrir o cerrar`, titulo: p.titulo, sufijo: cuantas(p.cuenta), ...p.datos ? { datos: p.datos } : {},
    ...p.clases ? { clases: p.clases } : {} });

/** La cabecera de una sección: un ítem con la flecha de plegar en su primera ranura. */
export function cabecera(p: PropsCabecera): string {
    return item({ ...deCabecera(p), variante: 'cabecera', inicio: [flecha(p.abierta)],
        fijas: [...p.acciones ?? [], ...p.nuevo ? [p.nuevo] : []] });
}

/** Una sección entera: la cabecera y, abierta, las herramientas y las filas (o la que dice que no hay). */
export function seccion(p: PropsSeccion): string {
    if (!p.abierta) return cabecera(p);
    const banda = p.herramientas ? herramientas(p.herramientas) : '';
    return cabecera(p) + banda + (p.filas() || (p.vacia ? item(p.vacia) : ''));
}

/** Una sección dentro de otra (ARCHIVO dentro de HILOS), va entre sus filas. Su cabecera es una fila más de la lista: la
 *  flecha en la tercera ranura, justo antes de los nombres. Sin herramientas propias, y no lleva otra adentro. */
export function submenu(p: PropsSubmenu): string {
    const vacias: null[] = Array.from({ length: Math.max(0, (p.ranuras ?? 3) - 1) }, () => null);
    const cab = item({ ...deCabecera(p), variante: 'submenu', inicio: [...vacias, { ...flecha(p.abierta), ancho: p.ancho }] });
    return p.abierta ? cab + p.filas() : cab;
}

/** Las secciones de una lista, una tras otra, con el separador entre ellas (no antes de la primera ni tras la última);
 *  las vacías (`''`) no cuentan. */
export function secciones(grupos: string[]): string {
    return grupos.filter(Boolean).join(separador());
}

// ── el plegado ──

/** Donde se guarda lo que se recuerda entre sesiones (la página: el localStorage del navegador). */
export interface Memoria {
    get<T>(clave: string): T | undefined;
    update(clave: string, valor: unknown): PromiseLike<void>;
}

/** Cómo dejó la persona cada cabecera de una lista. Se guardan solo las que están al revés de como empiezan: la que
 *  vuelve a como empieza se olvida (si cambia cómo empieza, la sigue). */
export class Plegado {
    private cambiadas?: Record<string, boolean>;
    /** cómo empieza cada cabecera que ya se preguntó: para dar vuelta una que la persona no ha tocado */
    private porDefecto = new Map<string, boolean>();

    /** `donde`: dónde se guarda, si ya lo hay (una función: la lista puede recibirlo después de armarse) */
    constructor(private readonly donde: () => Memoria | undefined, private readonly llave: string) {}

    private recordadas(): Record<string, boolean> {
        if (!this.cambiadas) {
            const g = this.donde()?.get<Record<string, boolean>>(this.llave);
            this.cambiadas = g && typeof g === 'object' ? { ...g } : {};
        }
        return this.cambiadas;
    }

    abierta(clave: string, porDefecto: boolean): boolean {
        this.porDefecto.set(clave, porDefecto);
        const r = this.recordadas()[clave];
        return typeof r === 'boolean' ? r : porDefecto;
    }

    /** Abrirla o plegarla, y recordarlo. */
    alternar(clave: string): void {
        const porDefecto = this.porDefecto.get(clave) ?? true;
        const r = this.recordadas(), abierta = !this.abierta(clave, porDefecto);
        if (abierta === porDefecto) delete r[clave]; else r[clave] = abierta;
        void this.donde()?.update(this.llave, r);
    }
}
