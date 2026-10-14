// Lo que comparten «tareas» y «hoy»: de dónde salen los datos del día y cómo se dibuja una
// lista de pendientes.
//
// Todo viene de `telar hoy --json`, que junta los pendientes de los documentos con lo que
// digan los proveedores declarados en la configuración (una agenda, un gestor de tareas).
// Ninguno viene de fábrica: sin proveedores declarados no hay agenda, y eso se dice en vez
// de dejar un hueco. La extensión no sale a la red por su cuenta jamás.
//
// Dos ritmos, como en la terminal: `--local` no consulta a nadie y contesta en lo que tarda
// leer unos archivos; sin `--local` se consulta a los proveedores, que pueden tardar. Lo
// caro se pide cada pocos minutos y lo barato cada vez.
//
// El orden y el filtro pasan en el webview: la lista ya está en pantalla, y filtrarla ahí
// es instantáneo mientras que volver a preguntar tarda lo que tarde el proveedor.

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

/** La lista de pendientes: ancha en «hoy», en una línea en la barra (`compacto`). El modo
 *  (urgentes / todos), la búsqueda y las letras las maneja el webview. */
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

/** La lista de pendientes: ancha en «hoy», en una línea en la barra (`compacto`). El modo
 *  (urgentes / todos), la búsqueda y las letras las maneja el webview. */
export function htmlPendientes(d: Dia, compacto: boolean): string[] {
    const lista = pendientes(d);
    const urgentes = lista.filter(t => t.urgente).length;
    const propuestas = lista.filter(t => t.avance).length;
    const h = compacto ? [] : [seccion('pendientes', 'verde', `${urgentes}/${lista.length}`)];
    h.push(`<div class="titulo-tareas${compacto ? ' estrecho' : ''}">`
        + '<span class="modos">'
        // en la barra, angosta, íconos en vez de palabras; la palabra queda en el globo
        + (propuestas ? `<button data-modo-tareas="propuestas" title="propuestas: lo que un agente dejó para que decidas">${compacto ? '◆' : 'propuestas'} ${propuestas}</button>` : '')
        + `<button data-modo-tareas="urgentes" title="urgentes: vencidos, próximos 7 días y en curso">${compacto ? '▲' : 'urgentes'} ${urgentes}</button>`
        + `<button data-modo-tareas="todos" title="todos, lo urgente arriba">${compacto ? '≡' : 'todos'} ${lista.length}</button>`
        + `<input id="buscar" type="text" placeholder="/ buscar" spellcheck="false" autocomplete="off">`
        + '<span id="tareas-cuenta"></span></span>'
        + '<span class="modos ordenes">'
        + '<button data-orden-t="urgencia" title="lo vencido arriba">urgencia</button>'
        + '<button data-orden-t="codigo" title="por código, de mayor a menor">código</button>'
        + '<button data-orden-t="alfa" title="por el texto">a-z</button></span></div>');
    const areas = filtroAreas(lista.map(t => t.fila.area ?? ''), compacto);
    if (areas) h.push(areas);
    const duenos = filtroDuenos(lista.map(t => [t.fila.dueno ?? '', !!t.fila.proveedor] as [string, boolean]), compacto);
    if (duenos) h.push(duenos);
    const cerrar = compacto ? [] : ['</section>'];
    if (d.error) return [...h, `<div class="vacio falla">${esc(d.error)}</div>`, ...cerrar];
    if (!lista.length) return [...h, '<div class="vacio">nada pendiente</div>', ...cerrar];
    h.push('<div id="tareas">');
    for (const t of lista) {
        const destino = compacto ? '' : `<span class="destino">${t.hilo ? '→' : '+'}</span>`;
        const buscable = normalizar([t.ref, t.texto, t.hilo, t.fila.ruta ?? '', t.fila.proveedor ?? '', t.fila.avance ?? '', t.fila.dueno ?? ''].join(' '));
        // lo que dejó un agente: una palabra con color antes del texto (preparado, cerrar, pregunta, choca)
        const [avanceTodo, avanceFecha] = (t.fila.avance ?? '').split(' ');
        const avance = t.avance;
        const marcaAvance = avance ? `<span class="av av-${esc(avance)}"${t.fila.color ? ` style="color: var(--${esc(t.fila.color)})"` : ''}>${esc(avanceTodo.replace(':', ' '))}</span>` : '';
        // con ficha, el clic la abre (leer y decidir, sin agente); ⌘-clic la lleva a su hilo
        const accion = t.fila.ficha
            ? `data-accion="tarea" data-valor="${esc(JSON.stringify([t.fila.proveedor, t.fila.id || t.ref, t.ref]))}"`
            : `data-accion="pendiente" data-valor="${esc(t.ref)}"`;
        h.push(`<div class="tarea${compacto ? ' compacta' : ''}${t.enCurso ? ' encurso' : ''}" ${accion} data-propuesta="${avance ? 1 : 0}" data-area="${esc(t.fila.area ?? '')}"${datosDueno(t.fila.dueno ?? '', !!t.fila.proveedor)}`
            + ` data-orden="${t.urgencia}" data-ref="${esc(t.ref)}" data-alfa="${esc(normalizar(limpiarMd(t.texto)))}" data-urgente="${t.urgente ? 1 : 0}" data-texto="${esc(buscable)}"`
            // el texto entero va en un globo propio (ver `globo` en el script): el `title` nativo
            // no siempre se muestra dentro de una vista de la barra
            + ` data-completo="${esc(`${t.ref} · ${limpiarMd(t.texto)}${avance ? `\n\nagente, ${avanceFecha}: ${avance}` : ''}\n\n${t.fila.ficha ? `clic: leerla y decidir · ⌘-clic: ${t.hilo ? `llevarla a «${t.hilo}»` : 'un hilo para trabajarla'}` : `clic: ${t.hilo ? `llevarlo a «${t.hilo}»` : 'abrir un hilo donde trabajarlo'}, escrito y sin enviar`}`)}">`
            // sin letras: la fila se clica. `+` abre un hilo nuevo, `→` lo lleva al que ya existe
            // (el globo dice cuál); `●` en la columna angosta, que ya se trabaja
            + `<span class="id">${esc(t.ref)}</span><span class="pri">${t.enCurso ? '●' : ''}</span>`
            // al final, después del plazo: con ficha, al pasar el mouse un ✓ la marca hecha sin abrir nada
            + `<span class="desc">${marcaAvance}${t.fila.dueno ? `<span class="dueno">→ ${esc(t.fila.dueno)}</span>` : ''}${esc(limpiarMd(t.texto))}</span><span class="meta">${plazo(t.dias)}${destino}`
            + (t.fila.ficha
                ? `<span class="marcar" data-accion="hecha" data-valor="${esc(JSON.stringify([t.fila.proveedor, t.fila.id || t.ref, t.ref]))}" title="marcarla hecha"></span>`
                : '<span></span>') + '</span></div>');
    }
    h.push('<div id="tareas-vacio" class="vacio" hidden></div><div id="tareas-mas" class="vacio clic" hidden></div></div>');
    return [...h, ...cerrar];
}

export const CSS_DIA = `
  body { padding: 1lh 3ch 3lh; }
  #dia { max-width: 120ch; }
  .cab { display: flex; gap: 1ch; align-items: baseline; }
  .cab .der { margin-left: auto; }
  h2 { font-size: 1em; font-weight: bold; text-transform: uppercase; margin: 1lh 0 0; }
  h2 small { font-weight: normal; text-transform: none; color: var(--dim); margin-left: 1ch; }
  .fila { display: flex; gap: 1ch; align-items: baseline; padding: 0 1ch; white-space: nowrap; }
  .fila.clic { cursor: pointer; } .fila.clic:hover { background: var(--hover); }
  .fila code { color: var(--verde); }
  .falla { color: var(--rojo); }
  .opcion { margin: 1lh 0; padding-left: 1ch; border-left: 2px solid transparent; }
  .opcion.activa { border-left-color: var(--azul); }
  .opcion .fila.dim { white-space: normal; }
  .tecla { flex: none; width: 3ch; color: var(--dim); }
  .hora { flex: none; color: var(--dim); }
  .pasada, .pasada .que { color: var(--dim); }
  .proxima .que, .proxima .hora { color: var(--fg); font-weight: bold; }
  .que { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .cuando { color: var(--amarillo); flex: none; }
  .enlace { flex: none; color: var(--azul); }
  .titulo-tareas { display: flex; align-items: baseline; gap: 2ch; margin: 1lh 0 0; flex-wrap: wrap; }
  .titulo-tareas h2 { margin: 0; }
  .titulo-tareas.estrecho { flex-direction: column; align-items: stretch; gap: 0; margin-top: 0; }
  .estrecho .modos { margin-left: 0; }
  .modos.ordenes { gap: 2ch; }
  .areas-t .modos, .duenos-t .modos { margin-left: 0; flex-wrap: wrap; gap: 0 2ch; }
  .modos { display: flex; gap: 2ch; align-items: baseline; margin-left: auto; }
  .modos button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; white-space: nowrap; }
  .modos button:hover { color: var(--fg); }
  /* el seleccionado va solo en color: un subrayado se pegaba a la línea de abajo */
  .modos button.activo { color: var(--c, var(--verde)); }
  #buscar { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
            width: 28ch; max-width: 100%; padding: 0 1ch; outline: none; flex: 1 1 12ch; }
  #buscar:focus { border-bottom-color: var(--azul); }
  #buscar::placeholder { color: var(--dim); }
  .ayuda { color: var(--dim); margin: 0 0 0 1ch; }
  #tareas-cuenta { color: var(--dim); }
  .tarea { display: flex; gap: 1ch; align-items: baseline; padding: 0 1ch; cursor: pointer; }
  .tarea.compacta .desc { -webkit-line-clamp: 1; }
  .tarea.compacta .meta { font-size: .95em; }
  .tarea.compacta .id { width: auto; min-width: 4ch; }
  .compacta + #tareas-mas, #dia > .titulo-tareas { margin-top: 0; }
  .tarea:hover { background: var(--hover); }
  .tarea .desc { flex: 1; min-width: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .id, .pri { flex: none; color: var(--dim); } .id { width: 12ch; overflow: hidden; }
  .meta { flex: none; color: var(--dim); text-align: right; }
  .venc { color: var(--rojo); } .pronto { color: var(--amarillo); } .espera { color: var(--cian); }
  .destino { color: var(--magenta); }
  .at { flex: none; width: 1ch; } .at.trabajando { color: var(--azul); } .at.espera { color: var(--amarillo); } .at.termino { color: var(--verde); }
  .nombre { min-width: 20ch; }
  #globo { position: fixed; z-index: 10; pointer-events: none; white-space: pre-wrap; max-width: min(60ch, calc(100vw - 3ch));
           padding: 0 1ch; background: var(--vscode-editorHoverWidget-background, #1e1e2e);
           color: var(--vscode-editorHoverWidget-foreground, var(--fg));
           border: 1px solid var(--vscode-editorHoverWidget-border, var(--linea));
           box-shadow: 0 2px 8px rgba(0,0,0,.35); }
  .md-pag p { margin: 0 0; white-space: normal; } .md-pag ul { margin: 0 0; padding-left: 2ch; }
  .md-pag code, .texto-pag code { color: var(--verde); }
  .lienzo { display: block; width: 100%; border: 0; margin: 0 0 1lh; background: transparent; }
  .sep-pag { border-top: 1px solid var(--linea); margin: 1lh 0; }
  .item-pag { padding: 0 1ch; margin: 0 0; border-left: 2px solid var(--linea); }
  .item-pag.clic { cursor: pointer; } .item-pag.clic:hover { background: var(--hover); border-left-color: var(--azul); }
  .texto-pag { color: var(--dim); display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .texto-pag p { margin: 0 0; }
  .msg { margin: 1lh 0 0; } .msg .quien { font-weight: bold; } .msg.usuario .quien { color: var(--azul); }
  .msg.agente .quien { color: var(--verde); }
  .herr { padding-left: 2ch; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ── el dashboard: terminal con color ─────────────────────────────────
     Reglas de terminal: un solo tamaño de letra y sin espaciado entre letras; lo
     horizontal en caracteres enteros (ch) y lo vertical en renglones enteros (lh); nada
     que decore ocupa lugar (bordes → outline o sombra; teclas en video inverso). */
  #dia { container-type: inline-size; }
  #dia, #dia * { font-size: inherit !important; letter-spacing: 0 !important; }
  small, code, kbd, button, input, b, i { font: inherit; }
  /* una tecla: marco fino y borde de abajo más grueso, como una tecla de verdad. El marco
     es outline y sombra (no ocupa lugar) y el relleno es medio carácter por lado: la tecla
     ocupa exactamente dos celdas y la grilla no se corre. */
  kbd { padding: 0 .5ch; color: var(--fg); background: color-mix(in srgb, var(--fg) 6%, transparent);
        outline: 1px solid var(--linea); outline-offset: -1px; box-shadow: inset 0 -2px 0 var(--linea); }
  .top { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 0 2ch; }
  .top .marca-t { display: flex; align-items: baseline; gap: 0 2ch; flex-wrap: wrap; }
  .logo { font-weight: bold; color: transparent;
          background: linear-gradient(90deg, var(--azul), var(--violeta), var(--rojo), var(--amarillo), var(--verde), var(--cian), var(--azul));
          background-size: 480px 100%; -webkit-background-clip: text; background-clip: text; animation: flujo 9s linear infinite; }
  .fecha { color: var(--fg); } .reloj { color: var(--amarillo); } .sem { color: var(--dim); }
  .regla { height: 2px; margin: 0;
           background: linear-gradient(90deg, var(--azul), var(--violeta), var(--rojo), var(--amarillo), var(--verde), var(--cian), var(--azul));
           background-size: 480px 100%; animation: flujo 9s linear infinite; }
  @keyframes flujo { from { background-position: 0 0; } to { background-position: 480px 0; } }

  .bloque { margin: 1lh 0 0; }
  h2.sec { display: flex; align-items: baseline; gap: 1ch; margin: 0; text-transform: uppercase; color: var(--c); font-weight: bold; }
  .sec .marca { width: 1ch; align-self: stretch; background: var(--c); }
  .sec .cuenta { color: var(--bg); background: var(--c); padding: 0 1ch; }
  .bloque > .ag, .bloque > .hl, .bloque #tareas, .bloque > .vacio, .bloque > .titulo-tareas {
      box-shadow: inset 1px 0 0 color-mix(in srgb, var(--c) 35%, transparent); }
  .vacio { color: var(--dim); padding: 0 2ch; }
  .clic { cursor: pointer; }

  /* agenda: tecla · hora · qué · lo de al lado */
  .plazo-clic { cursor: pointer; } .plazo-clic:hover { text-decoration: underline; }
  .menu-fila { cursor: pointer; color: var(--dim); text-align: center; } .menu-fila:hover { color: var(--fg); background: var(--hover); }
  .ag { display: grid; grid-template-columns: 7ch minmax(0, 1fr) auto; gap: 1ch; align-items: baseline; padding: 0 1ch; }
  .ag .hora { color: var(--c); }
  .ag .que { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ag .extra { display: flex; gap: 2ch; align-items: baseline; white-space: nowrap; color: var(--dim); }
  .ag.pasada { color: var(--dim); } .ag.pasada .hora { color: var(--dim); } .ag.pasada .que { text-decoration: line-through; text-decoration-color: var(--linea); }
  .ag.clic:hover, .hl.clic:hover, .tarea:hover { background: var(--hover); box-shadow: inset 2px 0 0 var(--c); }
  .ag.proxima { background: color-mix(in srgb, var(--c) 12%, transparent); box-shadow: inset 2px 0 0 var(--c); }
  .ag.proxima .que { color: var(--fg); font-weight: bold; }
  .punto { font-style: normal; color: var(--c); animation: latido 1.6s ease-in-out infinite; }
  .falta { color: var(--bg); background: var(--amarillo); padding: 0 1ch; font-weight: bold; }
  .ag .enlace { color: var(--azul); }
  @keyframes latido { 50% { opacity: .2; } }

  /* esperan: estado · hilo · hace cuánto */
  .hl { display: grid; grid-template-columns: 1ch minmax(0, 1fr) 4ch; gap: 1ch; align-items: baseline; padding: 0 1ch; }
  .hl .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
  .hl .cuando { text-align: right; color: var(--dim); }
  .hl .at { width: auto; font-weight: bold; } .hl .at.espera { animation: pulso 2.4s ease-in-out infinite; }
  @keyframes pulso { 50% { opacity: .45; } }

  /* atajos: teclas-botón */
  /* los atajos se ven como el resto de las teclas (pestañas, pie): tecla y nombre, sin marco */

  /* pendientes: tecla · código · casilla · texto · plazo */
  .bloque .titulo-tareas { margin: 0; padding: 0 1ch; gap: 0 2ch; }
  .bloque .titulo-tareas .modos:first-child { margin-left: 0; }
  .bloque .modos button.activo { color: var(--c); }
  .tarea { display: grid; grid-template-columns: 6ch 1ch minmax(0, 1fr) auto; gap: 1ch; align-items: baseline; padding: 0 1ch; }
  .tarea.compacta { grid-template-columns: 5ch 1ch minmax(0, 1fr) auto; padding: 0; }
  .tarea .id { width: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dim); }
  .tarea.encurso .pri { color: var(--azul); }
  .tarea:hover .marcar::after { content: '✓'; color: var(--dim); }
  .tarea .marcar:hover::after { color: var(--verde); font-weight: bold; }
  .tarea .dueno { color: var(--magenta); margin-right: 1ch; }
  .tarea.marcada { opacity: .4; text-decoration: line-through; pointer-events: none; }
  .av { font-weight: bold; margin-right: 1ch; }
  /* la ficha de una tarea: la propuesta del agente con el color de su estado, y los botones */
  #ficha-tarea { --c: var(--verde); }
  /* la pestaña de procesos periódicos: una fila por proceso, y su ficha con el log */
  .fila.per { display: grid; grid-template-columns: 2ch 22ch 16ch minmax(0, 1fr) max-content; }
  .fila.per b, .fila.per .que, .fila.per code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .fila.per.dim b { color: var(--dim); }
  #ficha-per .fila { white-space: normal; } #ficha-per .fila .que { overflow-wrap: anywhere; }
  #ficha-per pre.log { white-space: pre-wrap; overflow-wrap: anywhere; color: var(--dim); max-height: 60vh; overflow: auto;
    box-shadow: inset 2px 0 0 var(--linea); padding: 0 2ch; margin: 0; }
  /* el formulario de un periódico: etiqueta a la izquierda, control a la derecha */
  #form-per .campo { display: grid; grid-template-columns: 12ch minmax(0, 1fr); gap: 2ch; align-items: baseline; margin: .5lh 0; }
  #form-per .etiqueta { color: var(--dim); text-align: right; }
  #form-per .control { display: flex; flex-direction: column; gap: .25lh; min-width: 0; }
  #form-per input:not([type=checkbox]), #form-per textarea { font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--linea);
    padding: 0 1ch; outline: none; width: 100%; max-width: 80ch; box-sizing: border-box; resize: vertical; }
  #form-per input:focus, #form-per textarea:focus { border-color: var(--amarillo); }
  #form-per input:disabled { color: var(--dim); }
  #form-per input[type=number] { width: 8ch; }
  #form-per input[type=checkbox] { align-self: flex-start; margin: 0; accent-color: var(--amarillo); }
  #form-per .ayuda { font-size: .9em; }
  #form-per .opciones, #form-per .presets { display: flex; flex-wrap: wrap; gap: 0 2ch; }
  #form-per .opcion-t, #form-per .presets a { cursor: pointer; color: var(--dim); }
  #form-per .opcion-t.activa { color: var(--amarillo); font-weight: bold; }
  #form-per .opcion-t:hover, #form-per .presets a:hover { color: var(--fg); }
  #form-per.tipo-mensaje .solo-comando, #form-per.tipo-comando .solo-mensaje { display: none; }
  #form-per .skills { max-height: 14lh; overflow: auto; max-width: 80ch; box-shadow: inset 2px 0 0 var(--linea); }
  #form-per .skill { display: grid; grid-template-columns: 22ch minmax(0, 1fr); gap: 1ch; padding: 0 1ch; cursor: pointer; }
  #form-per .skill span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #form-per .skill:hover { background: var(--hover); } #form-per .skill.activa b { color: var(--amarillo); }
  #form-per .skill[hidden] { display: none; }
  #form-per #per-error { margin: .5lh 0 0 14ch; white-space: pre-wrap; }
  #form-per .fila-botones { grid-auto-flow: column; justify-content: start; gap: 3ch; margin-left: 14ch; }
  @media (max-width: 90ch) { .fila.per { grid-template-columns: 2ch minmax(0, 1fr) max-content; } .fila.per code, .fila.per .que { display: none; } }
  .prop { box-shadow: inset 2px 0 0 var(--c); padding: 0 2ch; margin: 1lh 0; }
  .sub-ficha { white-space: normal; overflow-wrap: anywhere; }
  .prop h2 { color: var(--c); }
  /* una acción por fila: la tecla en su columna, el nombre en la otra */
  .acciones-t { display: grid; grid-template-columns: max-content; margin: 1lh 0; }
  .acciones-t .atajo { gap: 1ch; }
  .pasar { display: inline-flex; gap: 1ch; } .pasar a { color: var(--c); cursor: pointer; } .pasar a:hover { text-decoration: none; color: var(--fg); }
  .acciones-t .atajo.principal span { color: var(--c); font-weight: bold; }
  .acciones-t .atajo.principal kbd { outline-color: var(--c); box-shadow: inset 0 -2px 0 var(--c); color: var(--c); }
  .av-preparado { color: var(--verde); } .av-cerrar { color: var(--cian); }
  .av-pregunta { color: var(--amarillo); } .av-choca { color: var(--rojo); }
  .tarea .meta { display: grid; grid-template-columns: 5ch 1ch 1ch; gap: 2ch; white-space: nowrap; }
  .tarea .meta > :first-child { text-align: right; }
  .tarea.compacta .meta { grid-template-columns: 5ch 1ch; gap: 1ch; }
  .tarea .destino { color: var(--magenta); overflow: hidden; text-overflow: ellipsis; text-align: left; }
  #tareas-mas { color: var(--c); padding: 0 1ch; }

  /* la barra de arriba: fija, igual en todas las pestañas */
  .fijo { position: sticky; top: 0; z-index: 5; background: var(--bg); padding: 1lh 0 0; margin-top: -1lh; }
  .top .recargar { color: var(--dim); } .top .recargar:hover { color: var(--fg); text-decoration: none; }
  .tabs { display: flex; flex-wrap: wrap; gap: 0; margin-top: 1lh; }
  .tab { padding: 0 1ch; color: var(--dim); white-space: nowrap; }
  .tab:hover { color: var(--fg); text-decoration: none; background: var(--hover); }
  .tab.activa { color: var(--bg); background: var(--t, var(--azul)); font-weight: bold; }
  .tab.activa kbd { color: var(--bg); background: transparent; outline-color: var(--bg); box-shadow: inset 0 -2px 0 var(--bg); }
  .tab[data-accion="dia"] { --t: var(--amarillo); } .tab[data-accion="proyectos"] { --t: var(--cian); }
  .tab[data-accion="correo"] { --t: var(--magenta); } .tab[data-accion="seccion"] { --t: var(--violeta); }
  .tab[data-accion="config"] { --t: var(--verde); }
  .fijo::after { content: ""; display: block; height: 1lh; }
  .subcab { display: flex; gap: 0 2ch; align-items: baseline; flex-wrap: wrap; margin: 0 0 1lh; }
  .subcab b { color: var(--fg); } .subcab .der { margin-left: auto; }

  /* el atajo: uno solo en todo el dashboard. Tecla y nombre; al pasar el mouse, los dos
     toman el color de su sección (--c) */
  .atajo { display: inline-flex; gap: 1ch; align-items: baseline; color: var(--fg); white-space: nowrap; cursor: pointer; }
  .atajo:hover { color: var(--c, var(--azul)); text-decoration: none; }
  .atajo:hover kbd { color: var(--c, var(--azul)); outline-color: var(--c, var(--azul)); box-shadow: inset 0 -2px 0 var(--c, var(--azul)); }
  .atajo.pista { color: var(--dim); cursor: default; }
  .atajo.pista:hover, .atajo.pista:hover kbd { color: var(--dim); outline-color: var(--linea); box-shadow: inset 0 -2px 0 var(--linea); }
  .sec .acciones { margin-left: auto; display: flex; flex-wrap: wrap; gap: 0 3ch; text-transform: none; font-weight: normal; }
  .sec .leyenda { color: var(--dim); }
  .generales { display: flex; flex-wrap: wrap; gap: 0 3ch; --c: var(--cian); }
  .top .atajo { color: var(--dim); } .top .atajo:hover { color: var(--c, var(--azul)); }
  .subcab { --c: var(--violeta); } .subcab .der { display: flex; gap: 0 3ch; }

  /* un bloque del día (el correo): marca · hora · de · qué */
  .cr { display: grid; grid-template-columns: 1ch 5ch 20ch minmax(0, 1fr); gap: 1ch; align-items: baseline; padding: 0 1ch;
        box-shadow: inset 1px 0 0 color-mix(in srgb, var(--c) 35%, transparent); color: var(--dim); }
  .cr .mk { color: var(--dim); } .cr .hora { color: var(--dim); }
  .cr .de { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cr .que { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cr.nuevo { color: var(--fg); } .cr.nuevo .mk { color: var(--c); } .cr.nuevo .hora { color: var(--c); }
  .cr:hover { background: var(--hover); } .cr.clic { cursor: pointer; } .cr.clic:hover .que { color: var(--c); }

  /* angosto: lo secundario se va, lo principal nunca */
  @container (max-width: 620px) {
    .ag .extra .hilo-ag { display: none; }
    .tarea .meta { grid-template-columns: 5ch 1ch 1ch; }
    .tarea:not(.compacta) { grid-template-columns: 5ch minmax(0, 1fr) auto; } .tarea:not(.compacta) .pri { display: none; }
    .ag { grid-template-columns: 7ch minmax(0, 1fr); } .ag .extra { grid-column: 2; }
    .ag:not(.proxima) .extra { display: none; }
    .cr { grid-template-columns: 1ch 5ch minmax(0, 1fr); } .cr .de { display: none; }
    .sec .acciones .pista { display: none; }  /* abajo solo va lo de la próxima: el resto sería un renglón vacío */
  }
  @media (prefers-reduced-motion: reduce) { .logo, .regla, .punto, .hl .at.espera { animation: none; } }
  #revisar #tareas-t .tarea, #revisar .tareas-cab { grid-template-columns: 6ch 2ch 1ch 18ch 14ch minmax(0, 1fr) auto; }
  #revisar .estr { cursor: pointer; color: var(--dim); opacity: 0; } #revisar .tarea:hover .estr { opacity: 1; }
  #revisar .estr.on { color: var(--amarillo); opacity: 1; } #revisar .estr:hover { color: var(--amarillo); }
  #revisar .eq { cursor: pointer; color: var(--dim); opacity: .35; } #revisar .tarea:hover .eq { opacity: 1; }
  #revisar .eq.on { color: var(--cian); opacity: 1; font-weight: 700; } #revisar .eq:hover { color: var(--cian); }
  #tareas-t-mas { margin-top: .5lh; color: var(--azul); }
  #revisar .tareas-cab { display: grid; gap: 1ch; padding: 0 1ch; color: var(--dim); margin-top: .5lh; }
  #revisar .tareas-cab [data-orden-c] { cursor: pointer; } #revisar .tareas-cab [data-orden-c]:hover { color: var(--fg); }
  #revisar .tareas-cab .activo { color: var(--azul); }
  #revisar .resp { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--amarillo); cursor: pointer; }
  #revisar .resp:hover { text-decoration: underline; } #revisar .resp.defecto { color: var(--dim); }
  #revisar .resp.dim, #revisar .resp.fijo { cursor: default; text-decoration: none; } #revisar .resp.dim { color: var(--dim); }
  #revisar .proy-t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--azul); cursor: pointer; }
  #revisar .proy-t:hover { text-decoration: underline; } #revisar .proy-t.dim { color: var(--dim); cursor: default; text-decoration: none; }
  #buscar-t { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
              width: 20ch; padding: 0 1ch; outline: none; }
  #buscar-t:focus { border-bottom-color: var(--azul); }
  #tareas-t-cuenta { color: var(--dim); }
  .modos button.vacio-m { opacity: .5; }
  #buscar-p { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
              width: 28ch; max-width: 100%; padding: 0 1ch; outline: none; flex: 1 1 12ch; }
  #buscar-p:focus { border-bottom-color: var(--azul); }
  #buscar-p::placeholder { color: var(--dim); }
  #proyectos-cuenta { color: var(--dim); }
  .proy .que { flex: 1; }
  .proy .tipo { flex: none; width: 9ch; overflow: hidden; text-overflow: ellipsis; }
  .proy .cuando-p { flex: none; width: 4ch; text-align: right; }
  .proy.primera { background: var(--hover); }
`;

/** El mismo script para las dos vistas: filtra, ordena y avisa a la
 *  extensión. El estado (modo y búsqueda) sobrevive a que la vista se esconda. */
export const SCRIPT_DIA = `
const raiz = document.getElementById('dia');
let estado = Object.assign({ modo: 'urgentes', q: '', todas: false, pq: '', po: 'fecha', to: 'urgencia', area: '', dueno: '', pc: false, pf: {}, ordenP: '' }, vscode.getState() || {});
// antes, «area» filtraba por la carpeta de la raíz (brinca, nico…); ahora es el área del documento
// «tareas» abre en «esta semana» (8-oct): lo que estaba guardado como «todas» pasa una vez a ese modo
if (!estado.tmv) { if (!estado.tm || estado.tm === 'todas') estado.tm = 'semana'; estado.tmv = 1; }
if (!estado.pfv) { estado.pf = Object.assign({}, estado.pf || {}); if (estado.pf.area) { estado.pf.raiz = estado.pf.area; estado.pf.area = ''; } estado.pfv = 2; }
// el área y el dueño filtran antes que todo lo demás: lo que queda fuera ni se cuenta
function pasa(f) { return pasaArea(f, estado.area) && pasaDueno(f, estado.dueno); }
function pasaArea(f, area) { return !area || f.dataset.area === area; }
function pasaDueno(f, dueno) {
  if (dueno === 'mias' && f.dataset.mia === '0') return false;
  if (dueno === 'otros' && (f.dataset.mia !== '0' || f.dataset.sin === '1')) return false;
  if (dueno === 'sin' && f.dataset.sin !== '1') return false;
  return true;
}
// código de mayor a menor, con los números como números (T130 antes que T81): lo más nuevo
// arriba, como el orden «número descendente» de flow. El texto, sin tildes.
function comparar(a, b) {
  if (estado.to === 'codigo') return b.dataset.ref.localeCompare(a.dataset.ref, undefined, { numeric: true });
  if (estado.to === 'alfa') return a.dataset.alfa.localeCompare(b.dataset.alfa);
  return Number(a.dataset.orden) - Number(b.dataset.orden);
}
function guardar() { vscode.setState(estado); }
function norm(t) { return t.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase(); }
function filas() { const c = document.getElementById('tareas'); return c ? Array.prototype.slice.call(c.querySelectorAll('.tarea')) : []; }
function visibles() { return filas().filter(function (f) { return !f.hidden; }); }
function aplicar() {
  aplicarArea();   // también en «revisar», que no tiene la lista de hoy
  const c = document.getElementById('tareas'); if (!c) return;
  // el área filtra antes que todo lo demás: lo de otra área ni se cuenta
  const todas = filas().filter(pasa);
  filas().forEach(function (f) { if (todas.indexOf(f) < 0) f.hidden = true; });
  const partes = norm(estado.q).split(/\\s+/).filter(Boolean);
  let lista = todas;
  if (partes.length) lista = todas.filter(function (f) { return partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); });
  else if (estado.modo === 'urgentes') lista = todas.filter(function (f) { return f.dataset.urgente === '1'; });
  else if (estado.modo === 'propuestas') lista = todas.filter(function (f) { return f.dataset.propuesta === '1'; });
  lista.sort(comparar);
  const limite = partes.length || estado.todas || estado.modo === 'propuestas' ? lista.length : (estado.modo === 'urgentes' ? 8 : 15);
  todas.forEach(function (f) { f.hidden = true; });
  const mas = document.getElementById('tareas-mas');
  lista.forEach(function (f, i) {
    c.insertBefore(f, mas);
    f.hidden = i >= limite;
  });
  const resto = lista.length - Math.min(limite, lista.length);
  mas.hidden = resto <= 0;
  mas.textContent = '+ ' + resto + ' más';
  const vacio = document.getElementById('tareas-vacio');
  vacio.hidden = lista.length > 0;
  vacio.textContent = partes.length ? 'sin resultados' : estado.modo === 'propuestas' ? 'nada que decidir' : 'nada urgente';
  document.querySelectorAll('[data-orden-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenT === estado.to); });
  document.querySelectorAll('[data-modo-tareas]').forEach(function (b) { b.classList.toggle('activo', !partes.length && b.dataset.modoTareas === estado.modo); });
  aplicarArea();
  const cuenta = document.getElementById('tareas-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? lista.length + ' de ' + todas.length : '';
}
// el filtro por área fuera de la lista de hoy (la pestaña «revisar») y el botón activo
function aplicarArea() {
  aplicarTareas();
  document.querySelectorAll('[data-area-filtro]').forEach(function (b) { b.classList.toggle('activo', b.dataset.areaFiltro === estado.area); });
  document.querySelectorAll('[data-dueno-filtro]').forEach(function (b) { b.classList.toggle('activo', b.dataset.duenoFiltro === (estado.dueno || '')); });
}
// la pestaña «tareas»: todas, filtradas por modo (por revisar, vencidas…), área, dueño y lo buscado
function enModo(f, modo) {
  const m = modo || estado.tm || 'semana', d = f.dataset.dias === '' ? null : Number(f.dataset.dias);
  if (m === 'revisar') return f.dataset.rev === '1';
  if (m === 'vencidas') return d !== null && d < 0;
  if (m === 'semana') return f.dataset.sem === '1';
  if (m === 'estrella') return f.dataset.estrella === '1';
  if (m === 'encurso') return f.dataset.encurso === '1';
  if (m === 'sinfecha') return d === null;
  return true;
}
// el orden de la columna elegida en «tareas»; sin elegir, la urgencia. Lo vacío siempre al final
function compararColumna(a, b) {
  const k = estado.ordenC || '';
  if (!k) return Number(a.dataset.orden) - Number(b.dataset.orden);
  const x = a.dataset[k] || '', y = b.dataset[k] || '';
  if (x !== y) {
    if (!x || !y) return x ? -1 : 1;
    if (k === 'dias') return Number(x) - Number(y);
    // el código, de mayor a menor con los números como números (lo más nuevo arriba)
    if (k === 'ref') return y.localeCompare(x, undefined, { numeric: true });
    return x.localeCompare(y);
  }
  return Number(a.dataset.orden) - Number(b.dataset.orden);
}
function aplicarTareas() {
  const c = document.getElementById('tareas-t'); if (!c) return;
  const todas = Array.prototype.slice.call(c.querySelectorAll('.tarea'));
  const partes = norm(estado.tq || '').split(/\s+/).filter(Boolean);
  const vacio = document.getElementById('tareas-t-vacio');
  todas.sort(compararColumna);
  document.querySelectorAll('.tareas-cab [data-orden-c]').forEach(function (s) {
    const es = s.dataset.ordenC === (estado.ordenC || '');
    s.classList.toggle('activo', es);
    s.textContent = es ? (s.dataset.ordenC === 'ref' ? '▼' : '▲') : '↕';
  });
  let n = 0;
  todas.forEach(function (f) {
    c.insertBefore(f, vacio);
    f.hidden = !(pasa(f) && enModo(f) && partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }));
    if (!f.hidden) n += 1;
  });
  vacio.hidden = n > 0 || !todas.length;
  vacio.textContent = partes.length ? 'sin resultados' : 'nada aquí';
  // en «esta semana», lo demás queda plegado detrás de «ver todas»: cuántas más hay con los otros filtros
  const mas = document.getElementById('tareas-t-mas');
  if (mas) {
    const resto = (estado.tm || 'semana') === 'semana'
      ? todas.filter(function (f) { return f.hidden && pasa(f) && partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); }).length : 0;
    mas.hidden = resto === 0;
    mas.textContent = 'ver todas (' + resto + ' más)';
    c.appendChild(mas);
  }
  document.querySelectorAll('[data-modo-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.modoT === (estado.tm || 'semana')); });
  // cada botón dice cuántas quedarían si se lo eligiera, con lo demás que está filtrado (la búsqueda y
  // las otras filas de filtros): el del filtro activo es lo que se ve
  const conTexto = function (f) { return partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; }); };
  const cuantas = function (cond) { return todas.filter(function (f) { return conTexto(f) && cond(f); }).length; };
  const poner = function (b, n) { b.textContent = b.textContent.replace(/\\s*\\d+$/, '') + ' ' + n; b.classList.toggle('vacio-m', n === 0); };
  document.querySelectorAll('#revisar [data-modo-t]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f, b.dataset.modoT) && pasaArea(f, estado.area) && pasaDueno(f, estado.dueno); }));
  });
  document.querySelectorAll('#revisar [data-area-filtro]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f) && pasaArea(f, b.dataset.areaFiltro) && pasaDueno(f, estado.dueno); }));
  });
  document.querySelectorAll('#revisar [data-dueno-filtro]').forEach(function (b) {
    poner(b, cuantas(function (f) { return enModo(f) && pasaArea(f, estado.area) && pasaDueno(f, b.dataset.duenoFiltro); }));
  });
  document.querySelectorAll('[data-orden-t]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenT === estado.to); });
  const cuenta = document.getElementById('tareas-t-cuenta');
  if (cuenta) cuenta.textContent = partes.length || (estado.tm || 'semana') !== 'todas' ? n + ' de ' + todas.length : '';
}
// la pantalla de proyectos: filtrar por todas las palabras, ordenar por nombre o por fecha
function proyectosVisibles() { const c = document.getElementById('proyectos'); return c ? Array.prototype.slice.call(c.querySelectorAll('.proy')).filter(function (f) { return !f.hidden; }) : []; }
function aplicarProyectos() {
  const c = document.getElementById('proyectos'); if (!c) return;
  const todas = Array.prototype.slice.call(c.querySelectorAll('.proy'));
  const partes = norm(estado.pq).split(/\\s+/).filter(Boolean);
  // por defecto: por estado (en marcha arriba, cerrado y sin estado abajo) y después por nombre. Una
  // columna elegida ordena por ella en su sentido natural (lo reciente y lo con hilo primero); lo vacío al final
  const k = estado.ordenP || '';
  const porNombre = function (a, b) { return a.dataset.nombre.localeCompare(b.dataset.nombre); };
  todas.sort(function (a, b) {
    if (!k || k === 'estado') return (Number(a.dataset.rango) - Number(b.dataset.rango)) || porNombre(a, b);
    const x = a.dataset[k] || '', y = b.dataset[k] || '';
    if (x !== y) {
      if (!x || !y) return x ? -1 : 1;
      return k === 'fecha' || k === 'hilo' ? (x < y ? 1 : -1) : x.localeCompare(y);
    }
    return porNombre(a, b);
  });
  document.querySelectorAll('.proy-cab [data-orden-p]').forEach(function (s) {
    const es = s.dataset.ordenP === k;
    s.classList.toggle('activo', es);
    s.textContent = es ? (k === 'fecha' || k === 'hilo' ? '▼' : '▲') : '↕';
  });
  const vacio = document.getElementById('proyectos-vacio');
  let n = 0;
  todas.forEach(function (f) {
    c.insertBefore(f, vacio);
    // los cerrados se esconden salvo que se pidan, o que se los busque por nombre
    const pf = estado.pf || {};
    f.hidden = !partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; })
      || (f.dataset.cerrado === '1' && !estado.pc && !partes.length && pf.tipo !== f.dataset.tipo)
      || (!!pf.raiz && f.dataset.raiz !== pf.raiz) || (!!pf.area && f.dataset.unidad !== pf.area)
      || (!!pf.tipo && f.dataset.tipo !== pf.tipo)
      || (!!pf.hilo && f.dataset.hilo === '0') || (!!pf.pend && !(Number(f.dataset.pend) > 0));
    f.classList.toggle('primera', !f.hidden && n === 0 && partes.length > 0);
    if (!f.hidden) n += 1;
  });
  vacio.hidden = n > 0;
  vacio.textContent = 'sin resultados';
  const cuenta = document.getElementById('proyectos-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? n + ' de ' + todas.length : '';
  const vc = document.getElementById('ver-cerrados');
  if (vc) vc.classList.toggle('activo', !!estado.pc);
  document.querySelectorAll('[data-pf]').forEach(function (b) {
    const v = (estado.pf || {})[b.dataset.pf] || '';
    b.classList.toggle('activo', v === b.dataset.pv);
  });
}
// elegir un proyecto: se marca al tiro y se pide su detalle (la derecha la cambia la extensión)
function elegirProy(f) {
  if (!f) return;
  document.querySelectorAll('.proy.sel').forEach(function (x) { x.classList.remove('sel'); });
  f.classList.add('sel');
  f.scrollIntoView({ block: 'nearest' });
  vscode.postMessage({ tipo: 'accion', accion: 'proy-sel', valor: f.dataset.valor });
}
function moverProy(paso) {
  const vis = proyectosVisibles(); if (!vis.length) return;
  const i = vis.findIndex(function (f) { return f.classList.contains('sel'); });
  elegirProy(vis[i < 0 ? 0 : Math.max(0, Math.min(vis.length - 1, i + paso))]);
}
// el globo: el texto entero de una tarea al detenerse sobre ella, cuando la fila lo corta
const globo = document.createElement('div'); globo.id = 'globo'; globo.hidden = true; document.body.appendChild(globo);
let globoEspera = null;
function esconderGlobo() { clearTimeout(globoEspera); globo.hidden = true; }
document.addEventListener('mouseover', function (e) {
  const f = e.target.closest && e.target.closest('[data-completo]');
  if (!f) return esconderGlobo();
  if (!globo.hidden && globo.dataset.de === f.dataset.valor) return;
  esconderGlobo();
  globoEspera = setTimeout(function () {
    globo.textContent = f.dataset.completo; globo.dataset.de = f.dataset.valor; globo.hidden = false;
    const r = f.getBoundingClientRect(), g = globo.getBoundingClientRect();
    const x = Math.max(4, Math.min(r.left + 12, window.innerWidth - g.width - 4));
    const abajo = r.bottom + 4 + g.height <= window.innerHeight;
    globo.style.left = x + 'px';
    globo.style.top = (abajo ? r.bottom + 4 : Math.max(4, r.top - g.height - 4)) + 'px';
  }, 350);
});
document.addEventListener('mouseleave', esconderGlobo);
document.addEventListener('scroll', esconderGlobo, true);
// un lienzo que pide guardar su memoria: solo se acepta de un iframe de lienzo de este panel, y
// la extensión decide el archivo (el que declaró la página), nunca el lienzo
window.addEventListener('message', function (e) {
  const d = e.data;
  if (!d || d.lienzo !== 'guardar' || typeof d.llave !== 'string' || typeof d.datos !== 'string') return;
  const propio = Array.prototype.some.call(document.querySelectorAll('iframe.lienzo'), function (f) { return f.contentWindow === e.source; });
  if (propio) vscode.postMessage({ tipo: 'lienzo-guardar', valor: d.llave, datos: d.datos });
});
window.addEventListener('message', function (e) {
  // un pedazo de la página (el formulario de un periódico): se cambia sin tocar lo escrito
  if (!e.data || typeof e.data !== 'object') return;
  if (e.data.tipo === 'proy-pend') {   // cuántos pendientes tiene cada proyecto: llega después de la lista
    const c = e.data.cuentas || {}; let n = 0;
    document.querySelectorAll('.proy').forEach(function (f) { const k = c[f.dataset.valor] || 0; f.dataset.pend = String(k); if (k) n += 1; });
    const cp = document.getElementById('cuenta-pend'); if (cp) cp.textContent = String(n);
    return aplicarProyectos();
  }
  if (e.data.tipo === 'parcial') { const el = document.getElementById(e.data.id); if (el) { el.innerHTML = e.data.html; filtrarSkills(); } return; }
  if (e.data.tipo !== 'dia') return;
  esconderGlobo();
  const activo = document.activeElement, id = activo && activo.id;
  const pos = id === 'buscar' || id === 'buscar-p' || id === 'buscar-t' ? activo.selectionStart : 0;
  // lo que se está escribiendo sobre una reunión sobrevive al repintado de cada minuto
  const ta = document.getElementById('ev-texto');
  const previo = ta ? { ev: ta.dataset.evento, v: ta.value, foco: activo === ta, s: ta.selectionStart } : null;
  raiz.innerHTML = e.data.html;
  const nt = document.getElementById('ev-texto');
  if (previo && nt && nt.dataset.evento === previo.ev) { nt.value = previo.v; if (previo.foco) { nt.focus(); nt.setSelectionRange(previo.s, previo.s); } }
  const nb = document.getElementById('buscar');
  if (nb) { nb.value = estado.q; if (id === 'buscar') { nb.focus(); nb.setSelectionRange(pos, pos); } }
  const nt2 = document.getElementById('buscar-t');
  if (nt2) { nt2.value = estado.tq || ''; if (id === 'buscar-t') { nt2.focus(); nt2.setSelectionRange(pos, pos); } }
  const np = document.getElementById('buscar-p');
  if (np) { np.value = estado.pq; if (id === 'buscar-p' || id !== 'buscar') { np.focus(); np.setSelectionRange(pos || np.value.length, pos || np.value.length); } }
  aplicar(); aplicarProyectos();
});
// ── el formulario de un proceso periódico ──
let esperaHorario = 0;
function filtrarSkills() {
  const f = document.getElementById('per-skill-filtro');
  if (!f) return;
  const q = (f.value || '').normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
  document.querySelectorAll('#per-skills .skill').forEach(function (x) { x.hidden = !!q && x.dataset.texto.indexOf(q) < 0; });
}
function formPer() {
  const v = function (id) { const el = document.getElementById(id); return el ? el.value : ''; };
  const form = document.getElementById('form-per');
  return { nombre: v('per-nombre'), descripcion: v('per-desc'), tipo: form.classList.contains('tipo-comando') ? 'comando' : 'mensaje',
    mensaje: v('per-mensaje'), comando: v('per-comando'), hilo: v('per-hilo'), max: v('per-max'), args: v('per-args'),
    cuando: v('per-cuando'), carpeta: v('per-carpeta'), activo: !!(document.getElementById('per-activo') || {}).checked };
}
function guardarPer() { vscode.postMessage({ tipo: 'accion', accion: 'per-guardar', valor: JSON.stringify(formPer()) }); }
document.addEventListener('input', function (e) {
  if (e.target.id === 'per-cuando') { clearTimeout(esperaHorario); const c = e.target.value; esperaHorario = setTimeout(function () { vscode.postMessage({ tipo: 'per-horario', valor: c }); }, 350); return; }
  if (e.target.id === 'per-skill-filtro') return filtrarSkills();
});
document.addEventListener('change', function (e) {
  if (e.target.id === 'per-carpeta') vscode.postMessage({ tipo: 'per-skills', valor: e.target.value.trim() });
});
document.addEventListener('click', function (e) {
  // guardar lleva lo escrito: se adelanta al manejador general, que mandaría la acción vacía
  if (e.target.closest('[data-accion="per-guardar"]')) { e.preventDefault(); e.stopPropagation(); return guardarPer(); }
  const t = e.target.closest('[data-per-tipo]');
  if (t) { const f = document.getElementById('form-per'); f.classList.remove('tipo-mensaje', 'tipo-comando'); f.classList.add('tipo-' + t.dataset.perTipo);
    document.querySelectorAll('[data-per-tipo]').forEach(function (x) { x.classList.toggle('activa', x === t); }); return; }
  const h = e.target.closest('[data-per-horario]');
  if (h) { const c = document.getElementById('per-cuando'); c.value = h.dataset.perHorario; vscode.postMessage({ tipo: 'per-horario', valor: c.value }); return; }
  const sk = e.target.closest('[data-skill]');
  if (sk) {
    const m = document.getElementById('per-mensaje');
    // la skill reemplaza a la que hubiera al principio; lo escrito después se queda
    const resto = m.value.replace(/^\\/[\\w:.-]+\\s*/, '');
    m.value = '/' + sk.dataset.skill + ' ' + resto;
    document.querySelectorAll('#per-skills .skill').forEach(function (x) { x.classList.toggle('activa', x === sk); });
    const hilo = document.getElementById('per-hilo'), nombre = document.getElementById('per-nombre');
    if (nombre && !nombre.value && !nombre.disabled) nombre.value = sk.dataset.skill.replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
    if (hilo && !hilo.value) hilo.placeholder = sk.dataset.skill;
    m.focus(); m.setSelectionRange(m.value.length, m.value.length);
  }
}, true);
document.addEventListener('input', function (e) {
  if (e.target.id === 'buscar-p') { estado.pq = e.target.value; guardar(); return aplicarProyectos(); }
  if (e.target.id === 'buscar-t') { estado.tq = e.target.value; guardar(); return aplicarTareas(); }
  if (e.target.id !== 'buscar') return;
  estado.q = e.target.value; estado.todas = false; guardar(); aplicar();
});
document.addEventListener('click', function (e) {
  const u = e.target.closest('[data-url]');
  if (u) { e.preventDefault(); e.stopPropagation(); return vscode.postMessage({ tipo: 'url', url: u.dataset.url }); }
  const ot = e.target.closest('[data-orden-t]');
  if (ot) { estado.to = ot.dataset.ordenT; guardar(); return aplicar(); }
  const oc = e.target.closest('[data-orden-c]');
  if (oc) { estado.ordenC = estado.ordenC === oc.dataset.ordenC ? '' : oc.dataset.ordenC; guardar(); return aplicarTareas(); }
  if (e.target.closest('#tareas-t-mas')) { estado.tm = 'todas'; guardar(); return aplicarTareas(); }
  const mt = e.target.closest('[data-modo-t]');
  if (mt) { estado.tm = mt.dataset.modoT; guardar(); return aplicarTareas(); }
  const op = e.target.closest('[data-orden-p]');
  // una flecha ordena por su columna; otra vez, vuelve al orden por defecto (estado y nombre)
  if (op) { estado.ordenP = estado.ordenP === op.dataset.ordenP ? '' : op.dataset.ordenP; guardar(); return aplicarProyectos(); }
  if (e.target.closest('#ver-cerrados')) { estado.pc = !estado.pc; guardar(); return aplicarProyectos(); }
  // un filtro de la lista de proyectos: área y tipo eligen uno; «con hilo» y «con pendientes» se prenden y apagan
  const bf = e.target.closest('[data-pf]');
  if (bf) { const pf = Object.assign({}, estado.pf || {}), k = bf.dataset.pf;
    pf[k] = pf[k] === bf.dataset.pv && (k === 'hilo' || k === 'pend') ? '' : bf.dataset.pv;
    estado.pf = pf; guardar(); return aplicarProyectos(); }
  const fp = e.target.closest('.proy[data-accion="proy-sel"]');
  // el ⋯ de una fila: la elige y abre el menú de acciones (lo manda el manejador general)
  if (fp && e.target.closest('.menu-fila')) elegirProy(fp);
  else if (fp) { e.preventDefault(); return elegirProy(fp); }
  // un enlace del README: lo abre la extensión (un archivo del repositorio o el navegador)
  const ln = e.target.closest('.proy-readme a[href]');
  if (ln) { e.preventDefault(); const base = ln.closest('.proy-readme').dataset.base || '';
    return vscode.postMessage({ tipo: 'accion', accion: 'proy-enlace', valor: ln.getAttribute('href'), datos: base }); }
  const ar = e.target.closest('[data-area-filtro]');
  if (ar) { estado.area = ar.dataset.areaFiltro; guardar(); aplicar(); return aplicarArea(); }
  const du = e.target.closest('[data-dueno-filtro]');
  if (du) { estado.dueno = du.dataset.duenoFiltro; guardar(); aplicar(); return aplicarArea(); }
  const m = e.target.closest('[data-modo-tareas]');
  if (m) { estado.modo = m.dataset.modoTareas; estado.q = ''; estado.todas = false; guardar(); const b = document.getElementById('buscar'); if (b) b.value = ''; return aplicar(); }
  if (e.target.closest('#tareas-mas')) { estado.todas = true; guardar(); return aplicar(); }
  const a = e.target.closest('[data-accion]');
  // el ✓ tacha la fila al tiro: la lista se relee cuando el proveedor termine
  if (a && a.dataset.accion === 'hecha') { const f = a.closest('.tarea'); if (f) f.classList.add('marcada'); }
  // un botón que manda lo escrito en un campo (el de escribirle al agente sobre una reunión)
  const campo = a && a.dataset.campo ? document.getElementById(a.dataset.campo) : null;
  if (campo && !campo.value.trim()) { campo.focus(); return; }
  if (a) vscode.postMessage({ tipo: 'accion', accion: a.dataset.accion, valor: a.dataset.valor, nuevo: e.metaKey || e.ctrlKey, datos: campo ? campo.value : undefined });
  if (campo) campo.value = '';
});
document.addEventListener('keydown', function (e) {
  // escribiéndole al agente sobre una reunión: las letras son del campo; ⌘⏎ envía, ⎋ sale del campo
  const activo = document.activeElement;
  if (activo && activo.id === 'ev-texto') {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); const b = document.getElementById('ev-enviar'); if (b) b.click(); return; }
    if (e.key === 'Escape') { e.preventDefault(); activo.blur(); }
    return;
  }
  // escribiendo en el formulario de un periódico: las letras son del campo, no atajos
  if (document.getElementById('form-per')) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); return guardarPer(); }
    const el = document.activeElement;
    const escribiendo = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT');
    if (e.key === 'Escape') { e.preventDefault(); if (escribiendo) return el.blur(); return vscode.postMessage({ tipo: 'accion', accion: 'per-cancelar' }); }
    if (escribiendo) return;
  }
  const bp = document.getElementById('buscar-p');
  if (bp && document.activeElement === bp) {         // en proyectos: ⏎ abre el primero que calza
    if (e.key === 'Escape') { e.preventDefault(); if (bp.value) { bp.value = ''; estado.pq = ''; guardar(); aplicarProyectos(); } else vscode.postMessage({ tipo: 'accion', accion: 'dia' }); }
    else if (e.key === 'Enter') { e.preventDefault(); const vis = proyectosVisibles(); const f = vis.find(function (x) { return x.classList.contains('sel'); }) || vis[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); moverProy(e.key === 'ArrowDown' ? 1 : -1); }
    return;
  }
  if (bp && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'j' || e.key === 'k')) { e.preventDefault(); return moverProy(e.key === 'ArrowDown' || e.key === 'j' ? 1 : -1); }
  if (bp && e.key === 'Enter') { const f = document.querySelector('.proy.sel'); if (f && !f.hidden) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); } }
  if (bp && e.key === 'Escape') { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'dia' }); }
  if (bp && e.key === '/') { e.preventDefault(); bp.focus(); return; }
  const b = document.getElementById('buscar');
  if (b && document.activeElement === b) {           // escribiendo: las letras son de la búsqueda
    if (e.key === 'Escape') { e.preventDefault(); if (b.value) { b.value = ''; estado.q = ''; guardar(); aplicar(); } else b.blur(); }
    else if (e.key === 'Enter') { e.preventDefault(); const f = visibles()[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor, nuevo: e.metaKey || e.ctrlKey }); }
    return;
  }
  // la ficha de una tarea: ⏎ la acción principal, ← → la propuesta anterior o siguiente, ⎋ vuelve a hoy
  if (document.getElementById('ficha-tarea') && !e.metaKey && !e.ctrlKey && !e.altKey) {
    const acc = { Enter: 'tarea-principal', ArrowRight: 'tarea-siguiente', ArrowLeft: 'tarea-anterior', Escape: 'volver-ficha' }[e.key];
    if (acc) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: acc }); }
  }
  // en la ficha de un proceso periódico: ⏎ lo corre ahora, ⎋ vuelve a la lista
  if (document.getElementById('ficha-per') && !e.metaKey && !e.ctrlKey && !e.altKey) {
    if (e.key === 'Enter') { e.preventDefault(); return vscode.postMessage({ tipo: 'tecla', k: '⏎' }); }
    if (e.key === 'Escape') { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'periodicos' }); }
  }
  // en el calendario, ← → cambian de día
  if (document.getElementById('cal-nav') && !e.metaKey && !e.ctrlKey && !e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
    e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'cal-dia', valor: e.key === 'ArrowLeft' ? '-1' : '1' });
  }
  // en «tareas»: escribir en la búsqueda; ⏎ abre la primera que se ve; / va a buscar
  const bt = document.getElementById('buscar-t');
  if (bt && document.activeElement === bt) {
    if (e.key === 'Escape') { e.preventDefault(); if (bt.value) { bt.value = ''; estado.tq = ''; guardar(); aplicarTareas(); } else bt.blur(); return; }
    if (e.key !== 'Enter') return;
  }
  if (bt && e.key === '/') { e.preventDefault(); bt.focus(); return; }
  if (document.getElementById('revisar') && e.key === 'Enter') {
    const f = document.querySelector('#revisar .tarea:not([hidden])');
    if (f) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: f.dataset.accion, valor: f.dataset.valor }); }
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;    // los atajos con modificador son de VS Code
  if (e.key === '/') { e.preventDefault(); if (b) b.focus(); return; }
  if (e.key === 'Escape') return vscode.postMessage({ tipo: 'accion', accion: 'volver' });
  if (e.key.length === 1) { e.preventDefault(); vscode.postMessage({ tipo: 'tecla', k: e.key }); }
});
vscode.postMessage({ tipo: 'listo' });
`;
