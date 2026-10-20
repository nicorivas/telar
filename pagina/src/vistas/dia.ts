// Lo que comparten «tareas» y «hoy»: de dónde salen los datos del día y cómo se dibuja una
// lista de pendientes.
//
// Todo viene de `telar hoy --json`, que junta los pendientes de los documentos con lo que
// digan los proveedores declarados en la configuración (una agenda, un gestor de tareas).
// Ninguno viene de fábrica: sin proveedores declarados no hay agenda, y eso se dice en vez
// de dejar un hueco. La página no sale a la red por su cuenta jamás: todo es la API.
//
// Dos ritmos, como en la terminal: `--local` no consulta a nadie y contesta en lo que tarda
// leer unos archivos; sin `--local` se consulta a los proveedores, que pueden tardar. Lo
// caro se pide cada pocos minutos y lo barato cada vez.
//
// El orden y el filtro pasan en la página (vistas/dashboard.ts): la lista ya está en pantalla, y
// filtrarla ahí es instantáneo mientras que volver a preguntar tarda lo que tarde el proveedor.

import * as cli from '../cli';
import { esc, limpiarMd, normalizar } from '../estilo';

// ───────────────────────── los datos ─────────────────────────

export interface Dia {
    ahora: string;
    fecha: string;            // AAAA-MM-DD
    nombreDia: string;        // «viernes»
    semana: number;
    agenda: cli.JsonFila[] | null;   // null: no se consultó, o no hay proveedor
    pendientes: cli.JsonFila[];
    declarados: string[];
    fallas: string[];
    error?: string;
}

const VACIO: Dia = {
    ahora: '', fecha: '', nombreDia: '', semana: 0,
    agenda: null, pendientes: [], declarados: [], fallas: [],
};

let cache: { dia: Dia; hora: number } | undefined;
/** La agenda cuesta una consulta a la red: se guarda aparte y se reusa entre lecturas locales. */
let agenda: { filas: cli.JsonFila[] | null; hora: number } = { filas: null, hora: 0 };
/** Lo mismo con los pendientes que traen los proveedores (las tareas de un gestor): una
 *  lectura local no los trae, y si se tomara su lista tal cual desaparecerían hasta la
 *  próxima consulta a la red. Los de los documentos sí se releen en cada lectura. */
let deProveedores: cli.JsonFila[] = [];

const CADA_RED = 5 * 60 * 1000;

/** La lectura en curso, si la hay: las dos vistas piden el día por su cuenta y una consulta
 *  a un proveedor no se hace dos veces porque dos paneles la quisieron a la vez. */
let enCurso: Promise<Dia> | undefined;

/** Cuándo se consultó por última vez a los proveedores (las tareas, el calendario); 0 si nunca. */
export function leidoProveedores(): number { return agenda.hora; }

/** El día. `conRed` consulta a los proveedores; sin él se lee solo lo que hay en disco. */
export function dia(maxEdad = 45000, conRed = false): Promise<Dia> {
    const tocaRed = conRed || Date.now() - agenda.hora > CADA_RED;
    if (!tocaRed && cache && Date.now() - cache.hora < maxEdad) return Promise.resolve(cache.dia);
    if (!enCurso) enCurso = leer(tocaRed).finally(() => { enCurso = undefined; });
    return enCurso;
}

async function leer(tocaRed: boolean): Promise<Dia> {
    const r = await cli.hoy(!tocaRed);
    if (!r.datos) {
        const d: Dia = { ...(cache?.dia ?? VACIO), error: r.error };
        cache = { dia: d, hora: Date.now() };
        return d;
    }
    const j = r.datos;
    if (tocaRed) {
        agenda = { filas: j.agenda ?? null, hora: Date.now() };
        deProveedores = (j.pendientes ?? []).filter(f => f.proveedor);
    }
    const propios = (j.pendientes ?? []).filter(f => !f.proveedor);
    const d: Dia = {
        ahora: j.ahora ?? new Date().toISOString(),
        fecha: j.fecha ?? '',
        nombreDia: j.dia ?? '',
        semana: j.semana ?? 0,
        agenda: tocaRed ? (j.agenda ?? null) : agenda.filas,
        pendientes: tocaRed ? (j.pendientes ?? []) : [...propios, ...deProveedores],
        declarados: j.proveedores?.declarados ?? [],
        fallas: j.proveedores?.fallas ?? [],
    };
    cache = { dia: d, hora: Date.now() };
    return d;
}

/** Otro día (la agenda de esa fecha, para el calendario): se consulta a los proveedores y se guarda unos minutos. */
const otros = new Map<string, { dia: Dia; hora: number }>();
export async function diaDe(fecha: string): Promise<Dia> {
    const guardado = otros.get(fecha);
    if (guardado && Date.now() - guardado.hora < CADA_RED) return guardado.dia;
    const r = await cli.hoy(false, fecha);
    const j = r.datos;
    const d: Dia = j ? {
        ahora: j.ahora ?? new Date().toISOString(), fecha: j.fecha ?? fecha, nombreDia: j.dia ?? '', semana: j.semana ?? 0,
        agenda: j.agenda ?? null, pendientes: j.pendientes ?? [], declarados: j.proveedores?.declarados ?? [],
        fallas: j.proveedores?.fallas ?? [],
    } : { ...VACIO, fecha, error: r.error };
    if (j) otros.set(fecha, { dia: d, hora: Date.now() });
    return d;
}

export function olvidarDia(): void { otros.clear(); cache = undefined; agenda = { filas: null, hora: 0 }; deProveedores = []; }

// ───────────────────────── la urgencia ─────────────────────────

export interface Pendiente {
    fila: cli.JsonFila;
    ref: string;
    texto: string;
    hilo: string;
    cuando: string;
    dias: number | null;      // los que faltan; negativo si venció
    enCurso: boolean;
    /** lo que dejó un agente trabajando solo («cerrar», «preparado»…), o "" */
    avance: string;
    urgencia: number;
    urgente: boolean;
}

/** Lo que está por hacer, lo más urgente arriba.
 *
 *  El contrato de `pendientes` no trae prioridad —un pendiente es una viñeta de un
 *  documento, no una tarea de un gestor—, así que la urgencia es la fecha: lo vencido
 *  primero (días negativos), después lo que vence pronto, y lo que no tiene fecha al final,
 *  como si venciera en un mes. Lo que está en curso se adelanta medio día dentro de su
 *  grupo: ya se empezó, y dejarlo a medias cuesta más que no haberlo empezado. */
export function pendientes(d: Dia, pestana = ''): Pendiente[] {
    const hoy = Date.parse(`${d.fecha || new Date().toISOString().slice(0, 10)}T00:00:00`);
    // lo de un proveedor con pestaña propia (un feed) no es un pendiente: va a su pestaña
    return d.pendientes
        .filter(f => !f.hecho && (f.pestana ?? '') === pestana)
        .map(f => {
            const cuando = f.cuando ?? '';
            const dias = cuando ? Math.round((Date.parse(cuando.slice(0, 10) + 'T00:00:00') - hoy) / 86400000) : null;
            const enCurso = !!f.en_curso;
            // lo que un agente dejó listo para decidir va arriba de todo: es lo más rápido de
            // despachar, y esperando se pudre
            const avance = (f.avance ?? '').split(' ')[0].split(':')[0];
            return {
                fila: f, ref: f.ref || f.id, texto: f.texto, hilo: f.hilo ?? '', cuando, dias, enCurso, avance,
                urgencia: avance ? -1000 + (dias ?? 0) / 1000 : (dias ?? 30) - (enCurso ? 0.5 : 0),
                urgente: avance ? true : dias !== null ? dias <= 7 : enCurso,
            };
        })
        // en una pestaña de proveedor (un feed) manda el orden del proveedor, que sabe cuál va primero
        .sort((a, b) => pestana ? 0 : a.urgencia - b.urgencia || a.ref.localeCompare(b.ref));
}

// ───────────────────────── el dibujo ─────────────────────────

/** Abre una sección del dashboard: su color, su nombre, una cuenta y, a la derecha, sus
 *  atajos y pistas (html de `atajo`/`pista`). Se cierra con `</section>`. El color va en
 *  `--c`, y lo heredan sus filas y el hover de sus atajos. */
export function seccion(nombre: string, color: string, cuenta = '', derecha = ''): string {
    return `<section class="bloque" style="--c: var(--${color})"><h2 class="sec"><span class="marca"></span>`
        + `${esc(nombre)}${cuenta ? `<span class="cuenta">${esc(cuenta)}</span>` : ''}`
        + `${derecha ? `<span class="acciones">${derecha}</span>` : ''}</h2>`;
}

/** Un atajo: la tecla y lo que hace, clicable. El mismo en todas partes: en la cabecera, en
 *  los títulos de sección, arriba del día y en las pestañas de sección. */
export function atajo(tecla: string, nombre: string, accion: string, valor = '', titulo = ''): string {
    return `<a class="atajo" data-accion="${esc(accion)}"${valor ? ` data-valor="${esc(valor)}"` : ''}`
        + `${titulo ? ` title="${esc(titulo)}"` : ''}><kbd>${esc(tecla)}</kbd><span>${esc(nombre)}</span></a>`;
}

/** Lo mismo, pero solo dice: una tecla que funciona sin ser un botón (`/`, `1–9`). */
export function pista(tecla: string, nombre: string): string {
    return `<span class="atajo pista"><kbd>${esc(tecla)}</kbd><span>${esc(nombre)}</span></span>`;
}

/** El filtro por dueño: «todas», «mías» (sin dueño) y «de otros» (con dueño), con su cuenta. Si
 *  ninguna tarea tiene dueño no hay nada que separar y no se dibuja. */
/** Quién es la persona de esta máquina (`telar config --json`): una tarea sin dueño es suya, y una
 *  asignada a su nombre también. La pone la vista al leer la configuración. */
export const yo = { persona: '', nombres: [] as string[] };

/** ¿Es mía? Sin dueño, o con uno de mis nombres: la primera palabra basta («Nico» y «Nico Rivas»,
 *  «Nicolás» con el nombre de git «Nicolás Rivas»), pero entera («Nicole» no es «Nico»). */
export function esMia(dueno: string): boolean {
    if (!dueno.trim()) return true;
    const primera = (t: string) => normalizar(t).split(/\s+/)[0] ?? '';
    const d = primera(dueno);
    return [yo.persona, ...yo.nombres].some(n => !!n && primera(n) === d);
}

/** ¿Es mía? `vacioEsMio`: una tarea sin dueño es de la persona; una viñeta de un documento sin
 *  responsable no es de nadie (está «sin responsable»). */
function mia(dueno: string, vacioEsMio: boolean): boolean {
    return dueno.trim() ? esMia(dueno) : vacioEsMio;
}

/** Los atributos de una fila para el filtro por dueño: mía y sin responsable. */
export function datosDueno(dueno: string, vacioEsMio = true): string {
    // «sin responsable» es lo de un documento que no dice quién: una tarea sin dueño es de la persona, no está sin responsable
    return ` data-dueno="${esc(dueno)}" data-mia="${mia(dueno, vacioEsMio) ? 1 : 0}" data-sin="${!dueno.trim() && !vacioEsMio ? 1 : 0}"`;
}

/** El filtro por dueño de una lista: cada fila como [dueño, si vacío es mía]. */
export function filtroDuenos(filas: [string, boolean][], compacto = false): string {
    const duenos = filas.map(([d]) => d);
    const otros = filas.filter(([d]) => d.trim() && !esMia(d)).length;
    const sin = filas.filter(([d, v]) => !d.trim() && !v).length;
    if (!otros && !sin) return '';
    const mias = filas.filter(([d, v]) => mia(d, v)).length;
    return '<div class="titulo-tareas duenos-t"><span class="modos">'
        + `<button data-dueno-filtro="" title="todas, mías y de otros">${compacto ? '∗' : 'todas'} ${duenos.length}</button>`
        + `<button data-dueno-filtro="mias" title="las mías: mis tareas sin dueño y lo que está a mi nombre">${compacto ? 'yo' : 'mías'} ${mias}</button>`
        + `<button data-dueno-filtro="otros" title="de otros: a nombre de otra persona (a quién empujar)">${compacto ? '→' : 'de otros'} ${otros}</button>`
        + `<button data-dueno-filtro="sin" title="sin responsable: pendientes de un proyecto que no dicen quién (tus tareas sin dueño son tuyas)">${compacto ? '∅' : 'sin responsable'} ${sin}</button>`
        + '</span></div>';
}

/** El filtro por área de una lista de tareas: «todas» y cada área con su cuenta, la más
 *  grande primero. Con una sola área no hay nada que filtrar y no se dibuja. El script lo
 *  aplica a toda `.tarea` con `data-area` de la vista (hoy, revisar, la barra). */
export function filtroAreas(areas: string[], compacto = false): string {
    const cuenta = new Map<string, number>();
    for (const a of areas) if (a) cuenta.set(a, (cuenta.get(a) ?? 0) + 1);
    if (cuenta.size < 2) return '';
    return '<div class="titulo-tareas areas-t"><span class="modos"><button data-area-filtro="">todas</button>'
        + [...cuenta].sort((a, b) => b[1] - a[1])
            // en la barra, angosta, tres letras (la palabra entera queda en el globo)
            .map(([a, n]) => `<button data-area-filtro="${esc(a)}" title="${esc(a)}">${esc(compacto ? a.slice(0, 3) : a)} ${n}</button>`).join('')
        + '</span></div>';
}

/** Una fecha relativa en pocas letras: `-39d` vencida, `hoy`, `mañana`, `3d`. */
export function plazo(dias: number | null): string {
    if (dias === null) return '<span></span>';  // la celda va igual: sin ella, lo de al lado se corre
    if (dias < 0) return `<span class="venc">${dias}d</span>`;
    if (dias === 0) return '<span class="pronto">hoy</span>';
    if (dias === 1) return '<span class="pronto">mañana</span>';
    return `<span class="dim">${dias}d</span>`;
}
