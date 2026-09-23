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
            return {
                fila: f, ref: f.ref || f.id, texto: f.texto, hilo: f.hilo ?? '', cuando, dias, enCurso,
                urgencia: (dias ?? 30) - (enCurso ? 0.5 : 0),
                urgente: dias !== null ? dias <= 7 : enCurso,
            };
        })
        .sort((a, b) => a.urgencia - b.urgencia || a.ref.localeCompare(b.ref));
}

// ───────────────────────── el dibujo ─────────────────────────

/** La lista de pendientes: ancha en «hoy», en una línea en la barra (`compacto`). El modo
 *  (urgentes / todos), la búsqueda y las letras las maneja el webview. */
export function htmlPendientes(d: Dia, compacto: boolean): string[] {
    const lista = pendientes(d);
    const urgentes = lista.filter(t => t.urgente).length;
    const h = [`<div class="titulo-tareas${compacto ? ' estrecho' : ''}">${compacto ? '' : '<h2>Pendientes</h2>'}`
        + `<span class="modos"><button data-modo-tareas="urgentes" title="vencidos, los próximos 7 días y lo que está en curso">urgentes ${urgentes}</button>`
        + `<button data-modo-tareas="todos" title="todos, lo más urgente arriba">todos ${lista.length}</button>`
        + `<input id="buscar" type="text" placeholder="/ buscar${compacto ? '' : ` en los ${lista.length}`}" spellcheck="false" autocomplete="off">`
        + '<span id="tareas-cuenta"></span></span>'
        + '<span class="modos ordenes"><span class="dim">orden</span>'
        + '<button data-orden-t="urgencia" title="lo vencido y lo próximo arriba">urgencia</button>'
        + '<button data-orden-t="codigo" title="por código, de mayor a menor: T130 antes que T81">código</button>'
        + '<button data-orden-t="alfa" title="por el texto de la tarea">a-z</button></span></div>'];
    if (!compacto) h.push('<div class="ayuda">letra o clic: llevarlo a su hilo (se escribe, no se envía) · ⌘clic: hilo nuevo · ↩ en la búsqueda: el primero</div>');
    if (d.error) return [...h, `<div class="fila dim">(${esc(d.error)})</div>`];
    if (!lista.length) {
        return [...h, '<div class="fila dim">nada que los documentos declaren pendiente. '
            + 'La sección la nombra el perfil del repositorio; un proveedor declarado suma las suyas.</div>'];
    }
    h.push('<div id="tareas">');
    for (const t of lista) {
        let fecha = '';
        if (t.dias !== null) {
            fecha = t.dias < 0 ? `<span class="venc">${compacto ? `hace ${-t.dias}d` : `venció hace ${-t.dias} d`}</span>`
                : t.dias === 0 ? `<span class="pronto">${compacto ? 'hoy' : 'vence hoy'}</span>`
                    : t.dias === 1 ? `<span class="pronto">${compacto ? 'mañana' : 'vence mañana'}</span>`
                        : `<span class="dim">${compacto ? `${t.dias}d` : `en ${t.dias} d`}</span>`;
        }
        const origen = !compacto && t.fila.proveedor ? `<span class="espera">${esc(t.fila.proveedor)}</span>` : '';
        const destino = compacto ? '' : (t.hilo ? `<span class="destino">→ ${esc(t.hilo)}</span>`
            : t.fila.ruta ? `<span class="dim">${esc(t.fila.ruta)}</span>` : '<span class="dim">hilo nuevo</span>');
        const meta = [fecha, origen, destino].filter(Boolean).join(' · ');
        const buscable = normalizar([t.ref, t.texto, t.hilo, t.fila.ruta ?? '', t.fila.proveedor ?? ''].join(' '));
        h.push(`<div class="tarea${compacto ? ' compacta' : ''}" data-accion="pendiente" data-valor="${esc(t.ref)}"`
            + ` data-orden="${t.urgencia}" data-ref="${esc(t.ref)}" data-alfa="${esc(normalizar(limpiarMd(t.texto)))}" data-urgente="${t.urgente ? 1 : 0}" data-texto="${esc(buscable)}"`
            + ` title="${esc(t.texto)}\n\nclic: ${t.hilo ? `llevarlo a «${t.hilo}»` : 'abrir un hilo donde trabajarlo'}, escrito y sin enviar">`
            // en la barra no van letras: es angosta, y un atajo invisible es una trampa
            + `${compacto ? '' : '<span class="tecla"></span>'}<span class="id">${esc(t.ref.slice(0, 12))}</span>`
            + `<span class="pri">${t.enCurso ? '▣' : '☐'}</span>`
            + `<span class="desc">${esc(limpiarMd(t.texto))}</span><span class="meta">${meta}</span></div>`);
    }
    h.push('<div id="tareas-vacio" class="fila dim" hidden></div><div id="tareas-mas" class="fila clic dim" hidden></div></div>');
    return h;
}

export const CSS_DIA = `
  body { padding: 1.2em 3ch 3em; }
  #dia { max-width: 120ch; }
  .cab { display: flex; gap: 1ch; align-items: baseline; }
  .cab .der { margin-left: auto; }
  h2 { font-size: 1em; font-weight: bold; text-transform: uppercase; margin: 1.4em 0 .2em; }
  h2 small { font-weight: normal; text-transform: none; color: var(--dim); margin-left: 1ch; }
  .fila { display: flex; gap: 1ch; align-items: baseline; padding: 0 .5ch; white-space: nowrap; }
  .fila.clic { cursor: pointer; } .fila.clic:hover { background: var(--hover); }
  .fila code { color: var(--verde); }
  .falla { color: var(--rojo); }
  .opcion { margin: .7em 0; padding-left: 1ch; border-left: 2px solid transparent; }
  .opcion.activa { border-left-color: var(--azul); }
  .opcion .fila.dim { white-space: normal; }
  .tecla { flex: none; width: 3ch; color: var(--dim); }
  .hora { flex: none; color: var(--dim); }
  .pasada, .pasada .que { color: var(--dim); }
  .proxima .que, .proxima .hora { color: var(--fg); font-weight: bold; }
  .que { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .cuando { color: var(--amarillo); flex: none; }
  .enlace { flex: none; color: var(--azul); }
  .titulo-tareas { display: flex; align-items: baseline; gap: 2ch; margin: 1.4em 0 .3em; flex-wrap: wrap; }
  .titulo-tareas h2 { margin: 0; }
  .titulo-tareas.estrecho { flex-direction: column; align-items: stretch; gap: .2em; margin-top: 0; }
  .estrecho .modos { margin-left: 0; }
  .modos.ordenes { gap: 1.5ch; }
  .modos { display: flex; gap: 2ch; align-items: baseline; margin-left: auto; }
  .modos button { font: inherit; background: none; border: 0; padding: 0; color: var(--dim); cursor: pointer; white-space: nowrap; }
  .modos button:hover { color: var(--fg); }
  .modos button.activo { color: var(--fg); text-decoration: underline; text-underline-offset: 3px; }
  #buscar { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
            width: 28ch; max-width: 100%; padding: 0 .5ch; outline: none; flex: 1 1 12ch; }
  #buscar:focus { border-bottom-color: var(--azul); }
  #buscar::placeholder { color: var(--dim); }
  .ayuda { color: var(--dim); margin: 0 0 .3em .5ch; }
  #tareas-cuenta { color: var(--dim); }
  .tarea { display: flex; gap: 1ch; align-items: baseline; padding: .1em .5ch; cursor: pointer; }
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
  .pie { margin-top: 2em; color: var(--dim); }
  .md-pag p { margin: .4em 0; white-space: normal; } .md-pag ul { margin: .3em 0; padding-left: 2.5ch; }
  .md-pag code, .texto-pag code { color: var(--verde); }
  .lienzo { display: block; width: 100%; border: 0; margin: .4em 0 .8em; background: transparent; }
  .sep-pag { border-top: 1px solid var(--linea); margin: 1em 0; }
  .item-pag { padding: .3em .5ch; margin: .2em 0; border-left: 2px solid var(--linea); }
  .item-pag.clic { cursor: pointer; } .item-pag.clic:hover { background: var(--hover); border-left-color: var(--azul); }
  .texto-pag { color: var(--dim); display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .texto-pag p { margin: .2em 0; }
  .msg { margin: 1em 0 .4em; } .msg .quien { font-weight: bold; } .msg.usuario .quien { color: var(--azul); }
  .msg.agente .quien { color: var(--verde); }
  .herr { padding-left: 2ch; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #buscar-p { font: inherit; color: var(--fg); background: transparent; border: 0; border-bottom: 1px solid var(--linea);
              width: 28ch; max-width: 100%; padding: 0 .5ch; outline: none; flex: 1 1 12ch; }
  #buscar-p:focus { border-bottom-color: var(--azul); }
  #buscar-p::placeholder { color: var(--dim); }
  #proyectos-cuenta { color: var(--dim); }
  .proy .que { flex: 1; }
  .proy .tipo { flex: none; width: 18ch; overflow: hidden; text-overflow: ellipsis; }
  .proy .cuando-p { flex: none; width: 4ch; text-align: right; }
  .proy.primera { background: var(--hover); }
`;

/** El mismo script para las dos vistas: filtra, ordena, numera con letras y avisa a la
 *  extensión. El estado (modo y búsqueda) sobrevive a que la vista se esconda. */
export const SCRIPT_DIA = `
const raiz = document.getElementById('dia');
const LETRAS = 'abdefghi';
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
  lista.sort(comparar);
  const limite = partes.length || estado.todas ? lista.length : (estado.modo === 'urgentes' ? 8 : 15);
  todas.forEach(function (f) { f.hidden = true; });
  const mas = document.getElementById('tareas-mas');
  lista.forEach(function (f, i) {
    c.insertBefore(f, mas);
    f.hidden = i >= limite;
    const t = f.querySelector('.tecla');
    if (t) t.textContent = i < LETRAS.length && i < limite ? '[' + LETRAS[i] + ']' : '';
  });
  const resto = lista.length - Math.min(limite, lista.length);
  mas.hidden = resto <= 0;
  mas.textContent = '… y ' + resto + ' más · clic: mostrarlos';
  const vacio = document.getElementById('tareas-vacio');
  vacio.hidden = lista.length > 0;
  vacio.textContent = partes.length ? 'nada calza con «' + estado.q + '»' : 'nada urgente';
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
  vacio.textContent = 'nada calza con «' + estado.pq + '»';
  document.querySelectorAll('[data-orden-p]').forEach(function (b) { b.classList.toggle('activo', b.dataset.ordenP === estado.po); });
  const cuenta = document.getElementById('proyectos-cuenta');
  if (cuenta) cuenta.textContent = partes.length ? n + ' de ' + todas.length : '';
}
window.addEventListener('message', function (e) {
  if (e.data.tipo !== 'dia') return;
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
    else if (e.key === 'Enter') { e.preventDefault(); const f = visibles()[0]; if (f) vscode.postMessage({ tipo: 'accion', accion: 'pendiente', valor: f.dataset.valor, nuevo: e.metaKey || e.ctrlKey }); }
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;    // los atajos con modificador son de VS Code
  if (e.key === '/') { e.preventDefault(); if (b) b.focus(); return; }
  if (e.key === 'Escape') return vscode.postMessage({ tipo: 'accion', accion: 'volver' });
  const i = document.querySelector('.tarea .tecla') ? LETRAS.indexOf(e.key) : -1;
  if (i >= 0) { const f = visibles()[i]; if (f) { e.preventDefault(); return vscode.postMessage({ tipo: 'accion', accion: 'pendiente', valor: f.dataset.valor }); } }
  if (e.key.length === 1) { e.preventDefault(); vscode.postMessage({ tipo: 'tecla', k: e.key }); }
});
vscode.postMessage({ tipo: 'listo' });
`;
