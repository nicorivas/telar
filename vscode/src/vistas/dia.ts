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

export function olvidarDia(): void { cache = undefined; agenda = { filas: null, hora: 0 }; deProveedores = []; }

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
export function pendientes(d: Dia): Pendiente[] {
    const hoy = Date.parse(`${d.fecha || new Date().toISOString().slice(0, 10)}T00:00:00`);
    return d.pendientes
        .filter(f => !f.hecho)
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
        .sort((a, b) => a.urgencia - b.urgencia || a.ref.localeCompare(b.ref));
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
        + (propuestas ? `<button data-modo-tareas="propuestas" title="lo que un agente dejó para que decidas">propuestas ${propuestas}</button>` : '')
        + `<button data-modo-tareas="urgentes" title="vencidos, próximos 7 días y en curso">urgentes ${urgentes}</button>`
        + `<button data-modo-tareas="todos" title="todos, lo urgente arriba">todos ${lista.length}</button>`
        + `<input id="buscar" type="text" placeholder="/ buscar" spellcheck="false" autocomplete="off">`
        + '<span id="tareas-cuenta"></span></span>'
        + '<span class="modos ordenes">'
        + '<button data-orden-t="urgencia" title="lo vencido arriba">urgencia</button>'
        + '<button data-orden-t="codigo" title="por código, de mayor a menor">código</button>'
        + '<button data-orden-t="alfa" title="por el texto">a-z</button></span></div>');
    const cerrar = compacto ? [] : ['</section>'];
    if (d.error) return [...h, `<div class="vacio falla">${esc(d.error)}</div>`, ...cerrar];
    if (!lista.length) return [...h, '<div class="vacio">nada pendiente</div>', ...cerrar];
    h.push('<div id="tareas">');
    for (const t of lista) {
        const destino = compacto ? '' : `<span class="destino">${t.hilo ? '→' : '+'}</span>`;
        const buscable = normalizar([t.ref, t.texto, t.hilo, t.fila.ruta ?? '', t.fila.proveedor ?? '', t.fila.avance ?? ''].join(' '));
        // lo que dejó un agente: una palabra con color antes del texto (preparado, cerrar, pregunta, choca)
        const [avanceTodo, avanceFecha] = (t.fila.avance ?? '').split(' ');
        const avance = t.avance;
        const marcaAvance = avance ? `<span class="av av-${esc(avance)}">${esc(avanceTodo.replace(':', ' '))}</span>` : '';
        // con ficha, el clic la abre (leer y decidir, sin agente); ⌘-clic la lleva a su hilo
        const accion = t.fila.ficha
            ? `data-accion="tarea" data-valor="${esc(JSON.stringify([t.fila.proveedor, t.fila.id || t.ref, t.ref]))}"`
            : `data-accion="pendiente" data-valor="${esc(t.ref)}"`;
        h.push(`<div class="tarea${compacto ? ' compacta' : ''}${t.enCurso ? ' encurso' : ''}" ${accion} data-propuesta="${avance ? 1 : 0}"`
            + ` data-orden="${t.urgencia}" data-ref="${esc(t.ref)}" data-alfa="${esc(normalizar(limpiarMd(t.texto)))}" data-urgente="${t.urgente ? 1 : 0}" data-texto="${esc(buscable)}"`
            // el texto entero va en un globo propio (ver `globo` en el script): el `title` nativo
            // no siempre se muestra dentro de una vista de la barra
            + ` data-completo="${esc(`${t.ref} · ${limpiarMd(t.texto)}${avance ? `\n\nagente, ${avanceFecha}: ${avance}` : ''}\n\n${t.fila.ficha ? `clic: leerla y decidir · ⌘-clic: ${t.hilo ? `llevarla a «${t.hilo}»` : 'un hilo para trabajarla'}` : `clic: ${t.hilo ? `llevarlo a «${t.hilo}»` : 'abrir un hilo donde trabajarlo'}, escrito y sin enviar`}`)}">`
            // sin letras: la fila se clica. `+` abre un hilo nuevo, `→` lo lleva al que ya existe
            // (el globo dice cuál); `●` en la columna angosta, que ya se trabaja
            + `<span class="id">${esc(t.ref)}</span><span class="pri">${t.enCurso ? '●' : ''}</span>`
            + `<span class="desc">${marcaAvance}${esc(limpiarMd(t.texto))}</span><span class="meta">${plazo(t.dias)}${destino}</span></div>`);
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
  .modos { display: flex; gap: 2ch; align-items: baseline; margin-left: auto; }
  .modos button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; white-space: nowrap; }
  .modos button:hover { color: var(--fg); }
  .modos button.activo { color: var(--fg); text-decoration: underline; text-underline-offset: 3px; }
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
  .bloque .modos button.activo { color: var(--c); text-decoration-color: var(--c); }
  .tarea { display: grid; grid-template-columns: 6ch 1ch minmax(0, 1fr) auto; gap: 1ch; align-items: baseline; padding: 0 1ch; }
  .tarea.compacta { grid-template-columns: 5ch 1ch minmax(0, 1fr) auto; padding: 0; }
  .tarea .id { width: auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dim); }
  .tarea.encurso .pri { color: var(--azul); }
  .av { font-weight: bold; margin-right: 1ch; }
  /* la ficha de una tarea: la propuesta del agente con el color de su estado, y los botones */
  #ficha-tarea { --c: var(--verde); }
  .prop { box-shadow: inset 2px 0 0 var(--c); padding: 0 2ch; margin: 1lh 0; }
  .prop h2 { color: var(--c); }
  /* una acción por fila: la tecla en su columna, el nombre en la otra */
  .acciones-t { display: grid; grid-template-columns: max-content; margin: 1lh 0; }
  .acciones-t .atajo { gap: 1ch; }
  .pasar { display: inline-flex; gap: 1ch; } .pasar a { color: var(--c); cursor: pointer; } .pasar a:hover { text-decoration: none; color: var(--fg); }
  .acciones-t .atajo.principal span { color: var(--c); font-weight: bold; }
  .acciones-t .atajo.principal kbd { outline-color: var(--c); box-shadow: inset 0 -2px 0 var(--c); color: var(--c); }
  .av-preparado { color: var(--verde); } .av-cerrar { color: var(--cian); }
  .av-pregunta { color: var(--amarillo); } .av-choca { color: var(--rojo); }
  .tarea .meta { display: grid; grid-template-columns: 5ch 1ch; gap: 2ch; white-space: nowrap; }
  .tarea .meta > :first-child { text-align: right; }
  .tarea.compacta .meta { grid-template-columns: 5ch; }
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
    .tarea .meta { grid-template-columns: 5ch 1ch; }
    .tarea:not(.compacta) { grid-template-columns: 5ch minmax(0, 1fr) auto; } .tarea:not(.compacta) .pri { display: none; }
    .ag { grid-template-columns: 7ch minmax(0, 1fr); } .ag .extra { grid-column: 2; }
    .ag:not(.proxima) .extra { display: none; }
    .cr { grid-template-columns: 1ch 5ch minmax(0, 1fr); } .cr .de { display: none; }
    .sec .acciones .pista { display: none; }  /* abajo solo va lo de la próxima: el resto sería un renglón vacío */
  }
  @media (prefers-reduced-motion: reduce) { .logo, .regla, .punto, .hl .at.espera { animation: none; } }
  #buscar-p { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
              width: 28ch; max-width: 100%; padding: 0 1ch; outline: none; flex: 1 1 12ch; }
  #buscar-p:focus { border-bottom-color: var(--azul); }
  #buscar-p::placeholder { color: var(--dim); }
  #proyectos-cuenta { color: var(--dim); }
  .proy .que { flex: 1; }
  .proy .tipo { flex: none; width: 18ch; overflow: hidden; text-overflow: ellipsis; }
  .proy .cuando-p { flex: none; width: 4ch; text-align: right; }
  .proy.primera { background: var(--hover); }
`;

/** El mismo script para las dos vistas: filtra, ordena y avisa a la
 *  extensión. El estado (modo y búsqueda) sobrevive a que la vista se esconda. */
export const SCRIPT_DIA = `
const raiz = document.getElementById('dia');
let estado = Object.assign({ modo: 'urgentes', q: '', todas: false, pq: '', po: 'fecha', to: 'urgencia' }, vscode.getState() || {});
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
  const c = document.getElementById('tareas'); if (!c) return;
  const todas = filas();
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
  const cuenta = document.getElementById('tareas-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? lista.length + ' de ' + todas.length : '';
}
// la pantalla de proyectos: filtrar por todas las palabras, ordenar por nombre o por fecha
function proyectosVisibles() { const c = document.getElementById('proyectos'); return c ? Array.prototype.slice.call(c.querySelectorAll('.proy')).filter(function (f) { return !f.hidden; }) : []; }
function aplicarProyectos() {
  const c = document.getElementById('proyectos'); if (!c) return;
  const todas = Array.prototype.slice.call(c.querySelectorAll('.proy'));
  const partes = norm(estado.pq).split(/\\s+/).filter(Boolean);
  todas.sort(function (a, b) {
    if (estado.po === 'fecha' && a.dataset.fecha !== b.dataset.fecha) return a.dataset.fecha < b.dataset.fecha ? 1 : -1;
    return a.dataset.nombre.localeCompare(b.dataset.nombre);
  });
  const vacio = document.getElementById('proyectos-vacio');
  let n = 0;
  todas.forEach(function (f) {
    c.insertBefore(f, vacio);
    f.hidden = !partes.every(function (p) { return f.dataset.texto.indexOf(p) >= 0; });
    f.classList.toggle('primera', !f.hidden && n === 0 && partes.length > 0);
    if (!f.hidden) n += 1;
  });
  vacio.hidden = n > 0;
  vacio.textContent = 'sin resultados';
  document.querySelectorAll('[data-orden-p]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenP === estado.po); });
  const cuenta = document.getElementById('proyectos-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? n + ' de ' + todas.length : '';
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
window.addEventListener('message', function (e) {
  if (e.data.tipo !== 'dia') return;
  esconderGlobo();
  const activo = document.activeElement, id = activo && activo.id;
  const pos = id === 'buscar' || id === 'buscar-p' ? activo.selectionStart : 0;
  raiz.innerHTML = e.data.html;
  const nb = document.getElementById('buscar');
  if (nb) { nb.value = estado.q; if (id === 'buscar') { nb.focus(); nb.setSelectionRange(pos, pos); } }
  const np = document.getElementById('buscar-p');
  if (np) { np.value = estado.pq; if (id === 'buscar-p' || id !== 'buscar') { np.focus(); np.setSelectionRange(pos || np.value.length, pos || np.value.length); } }
  aplicar(); aplicarProyectos();
});
document.addEventListener('input', function (e) {
  if (e.target.id === 'buscar-p') { estado.pq = e.target.value; guardar(); return aplicarProyectos(); }
  if (e.target.id !== 'buscar') return;
  estado.q = e.target.value; estado.todas = false; guardar(); aplicar();
});
document.addEventListener('click', function (e) {
  const u = e.target.closest('[data-url]');
  if (u) { e.preventDefault(); e.stopPropagation(); return vscode.postMessage({ tipo: 'url', url: u.dataset.url }); }
  const ot = e.target.closest('[data-orden-t]');
  if (ot) { estado.to = ot.dataset.ordenT; guardar(); return aplicar(); }
  const op = e.target.closest('[data-orden-p]');
  if (op) { estado.po = op.dataset.ordenP; guardar(); return aplicarProyectos(); }
  const m = e.target.closest('[data-modo-tareas]');
  if (m) { estado.modo = m.dataset.modoTareas; estado.q = ''; estado.todas = false; guardar(); const b = document.getElementById('buscar'); if (b) b.value = ''; return aplicar(); }
  if (e.target.closest('#tareas-mas')) { estado.todas = true; guardar(); return aplicar(); }
  const a = e.target.closest('[data-accion]');
  if (a) vscode.postMessage({ tipo: 'accion', accion: a.dataset.accion, valor: a.dataset.valor, nuevo: e.metaKey || e.ctrlKey });
});
document.addEventListener('keydown', function (e) {
  const bp = document.getElementById('buscar-p');
  if (bp && document.activeElement === bp) {         // en proyectos: ⏎ abre el primero que calza
    if (e.key === 'Escape') { e.preventDefault(); if (bp.value) { bp.value = ''; estado.pq = ''; guardar(); aplicarProyectos(); } else vscode.postMessage({ tipo: 'accion', accion: 'dia' }); }
    else if (e.key === 'Enter') { e.preventDefault(); const f = proyectosVisibles()[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: 'proyecto', valor: f.dataset.valor }); }
    return;
  }
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
  // en «revisar», ⏎ abre la primera propuesta
  if (document.getElementById('revisar') && e.key === 'Enter') {
    const f = document.querySelector('#revisar .tarea');
    if (f) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'tarea', valor: f.dataset.valor }); }
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;    // los atajos con modificador son de VS Code
  if (e.key === '/') { e.preventDefault(); if (b) b.focus(); return; }
  if (e.key === 'Escape') return vscode.postMessage({ tipo: 'accion', accion: 'volver' });
  if (e.key.length === 1) { e.preventDefault(); vscode.postMessage({ tipo: 'tecla', k: e.key }); }
});
vscode.postMessage({ tipo: 'listo' });
`;
