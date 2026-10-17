// La pantalla de proyectos: a la izquierda todas las unidades del perfil, con búsqueda; a la derecha,
// la elegida: sus pendientes (las viñetas de su documento y las tareas que dicen ser suyas) y su
// README. Como el calendario, dos columnas; la derecha se cambia sola (un mensaje `parcial`), sin
// repintar la lista, que es larga y no debe perder ni el scroll ni lo buscado.

import * as cli from '../cli';
import { esc, haceCorto, limpiarMd, normalizar, estilo } from '../estilo';
import { Pendiente, plazo } from './dia';

export const CSS_PROY = estilo('proyectos');

/** El color del estado según de qué tipo es: en marcha, por ganar, trabado o terminado. */
function claseEstado(estado: string): string {
    const e = normalizar(estado);
    if (/^(activo|ganado|en curso|en ejecucion)/.test(e)) return 'e-activo';
    if (/^(prospecto|propuesta|negociacion|entendimiento|poc|lead|diagnostico)/.test(e)) return 'e-abierto';
    if (/pausa|vencido|perdido|trabado|bloquead/.test(e)) return 'e-trabado';
    return '';
}

/** El lugar de un estado en el orden por defecto: lo que está en marcha arriba, después lo que se
 *  está ganando (de lo más cerca a lo más lejos), lo trabado, lo cerrado, y lo sin estado al final. */
export function rangoEstado(estado: string): number {
    const e = normalizar(estado);
    if (!e) return 9;
    const orden: [RegExp, number][] = [
        [/^(activo|ganado|en curso|en ejecucion)/, 0], [/^negociacion/, 1], [/^propuesta/, 2],
        [/^(entendimiento|poc|diagnostico)/, 3], [/^(prospecto|lead)/, 4], [/pausa/, 5],
        [/^(vencido|perdido|trabado|bloquead)/, 6], [/^(cerrado|terminado|finalizado)/, 7],
    ];
    return orden.find(([re]) => re.test(e))?.[1] ?? 8;
}

/** Un servicio (lo que se vende, no un proyecto con cliente): no va en la lista de proyectos ni se ofrece
 *  al elegir uno. Sí sirve para decir de qué es una tarea, así que la lista completa se guarda igual. */
export const esServicio = (p: cli.JsonProyecto): boolean => p.arquetipo === 'servicio';

/** Una unidad se da por cerrada por su arquetipo («proyecto cerrado»): se esconde salvo que se pidan. */
export const esCerrado = (p: cli.JsonProyecto): boolean => /cerrad/i.test(p.arquetipo);

/** De qué carpeta de la raíz es una unidad: la primera de su ruta (brinca, nico, consultoria…). */
export const raizDe = (ruta: string): string => ruta.split('/')[0] || ruta;

/** Las áreas en el orden en que se muestran; una que no esté aquí va después, por cuántas tiene. */
const AREAS = ['PIA', 'EIC', 'GT', 'Upskill', 'Brinca', 'Otro'];

/** El área que declara su documento (`area:` en el frontmatter), o «sin área». */
export const areaDe = (p: cli.JsonProyecto): string => p.area || 'sin área';

/** De qué unidad es una carpeta: la más honda de `rutas` que la contiene. Una tarea de
 *  `brinca/operacion/ia/x` es de `brinca/operacion/ia`, no de `brinca`, aunque las dos la contengan. */
export function unidadDe(carpeta: string, rutas: string[]): string {
    let mejor = '';
    for (const r of rutas) if ((carpeta === r || carpeta.startsWith(`${r}/`)) && r.length > mejor.length) mejor = r;
    return mejor;
}

/** Una fila de botones que filtra la lista por un campo (`data-pf`); el webview marca el activo. */
function filtro(campo: string, todos: string, valores: Map<string, number>, orden: string[] = []): string {
    if (valores.size < 2) return '';
    // con `orden`, ese orden (lo que no está en él, después); si no, lo más común primero
    const lugar = (v: string) => { const i = orden.indexOf(v); return i < 0 ? orden.length : i; };
    return `<div class="titulo-tareas areas-t"><span class="modos"><button data-pf="${campo}" data-pv="">${esc(todos)}</button>`
        + [...valores].sort((a, b) => lugar(a[0]) - lugar(b[0]) || b[1] - a[1])
            .map(([v, n]) => `<button data-pf="${campo}" data-pv="${esc(v)}">${esc(v)} ${n}</button>`).join('')
        + '</span></div>';
}

function contar(xs: string[]): Map<string, number> {
    const m = new Map<string, number>();
    for (const x of xs) if (x) m.set(x, (m.get(x) ?? 0) + 1);
    return m;
}

/** La lista de la izquierda. Buscar, ordenar y mostrar los cerrados ocurre en el webview
 *  (`aplicarProyectos`); elegir una fila pide su detalle. */
export function htmlListaProyectos(lista: cli.JsonProyecto[], sel: string, cuentas?: Map<string, number>): string[] {
    const cerrados = lista.filter(esCerrado).length;
    const conHilo = lista.filter(p => p.hilo).length;
    const conPend = cuentas ? lista.filter(p => (cuentas.get(p.ruta) ?? 0) > 0).length : 0;
    const h: string[] = ['<div class="titulo-tareas">'
        + `<input id="buscar-p" type="text" placeholder="/ buscar en los ${lista.length}" spellcheck="false" autocomplete="off">`
        + '<span class="modos"><span id="proyectos-cuenta"></span>'
        + (cerrados ? `<button id="ver-cerrados" title="mostrar u ocultar los proyectos cerrados">cerrados ${cerrados}</button>` : '')
        + '</span></div>',
    filtro('raiz', 'todas las carpetas', contar(lista.map(p => raizDe(p.ruta)))),
    // el área que declara cada documento: aparece cuando hay al menos dos distintas
    filtro('area', 'todas las áreas', contar(lista.map(areaDe)), [...AREAS, 'sin área']),
    filtro('tipo', 'todos los tipos', contar(lista.map(p => p.arquetipo))),
    '<div class="titulo-tareas areas-t"><span class="modos">'
        + `<button data-pf="hilo" data-pv="1" title="solo los que tienen un hilo (● abierto, · dormido)">con hilo ${conHilo}</button>`
        + `<button data-pf="pend" data-pv="1" title="solo los que tienen algo pendiente">con pendientes <span id="cuenta-pend">${cuentas ? conPend : '…'}</span></button>`
        + '</span></div>',
    // un ícono sobre cada columna: el clic ordena por ella, otro clic da vuelta el orden
    '<div class="fila proy-cab">'
        + '<span class="at" data-orden-p="hilo" title="ordenar: con hilo primero (otra vez: por estado y nombre)">↕</span>'
        + '<span class="que" data-orden-p="nombre" title="ordenar por nombre (otra vez: por estado y nombre)">↕</span>'
        + '<span class="estado" data-orden-p="estado" title="ordenar por estado (otra vez: por estado y nombre)">↕</span>'
        + '<span class="tipo" data-orden-p="tipo" title="ordenar por tipo (otra vez: por estado y nombre)">↕</span>'
        + '<span class="cuando-p" data-orden-p="fecha" title="ordenar por cuándo se tocó (otra vez: por estado y nombre)">↕</span><span class="menu-col"></span></div>',
    '<div id="proyectos">'];
    for (const p of lista) {
        const marca = p.vivo ? '●' : p.hilo ? '·' : '';
        const texto = normalizar(`${p.nombre} ${p.ruta} ${p.arquetipo} ${p.estado ?? ''} ${p.area ?? ''}`);
        // el cliente adelante y en color; lo demás del nombre, apagado
        const cliente = p.cliente && p.nombre.startsWith(p.cliente) ? p.cliente : '';
        const nombre = cliente ? `<span class="cliente">${esc(cliente)}</span><span class="resto">${esc(p.nombre.slice(cliente.length))}</span>`
            : esc(p.nombre);
        const estado = p.estado ?? '';
        const fecha = p.modificado ?? '';
        h.push(`<div class="fila clic proy${p.ruta === sel ? ' sel' : ''}${esCerrado(p) ? ' cerrado' : ''}" data-accion="proy-sel"`
            + ` data-valor="${esc(p.ruta)}" data-cerrado="${esCerrado(p) ? 1 : 0}" data-raiz="${esc(raizDe(p.ruta))}" data-unidad="${esc(areaDe(p))}"`
            + ` data-tipo="${esc(p.arquetipo)}" data-estado="${esc(normalizar(estado))}" data-rango="${rangoEstado(estado)}" data-hilo="${p.vivo ? 2 : p.hilo ? 1 : 0}" data-pend="${cuentas ? cuentas.get(p.ruta) ?? 0 : ''}"`
            + ` data-texto="${esc(texto)}" data-nombre="${esc(normalizar(p.nombre))}" data-fecha="${esc(fecha)}"`
            + ` title="${esc(`${p.ruta}${fecha ? `\nmodificado ${fecha.slice(0, 16).replace('T', ' ')}` : ''}${p.hilo ? `\nhilo: ${p.hilo}` : ''}`)}">`
            + `<span class="at">${marca}</span><span class="que">${nombre}</span>`
            + `<span class="estado ${claseEstado(estado)}" title="${esc(p.estado_completo || estado)}">${esc(estado)}</span>`
            + `<span class="dim tipo">${esc(p.arquetipo)}</span><span class="dim cuando-p">${esc(haceCorto(fecha))}</span>`
            + `<span class="menu-fila menu-col" data-accion="proy-menu" data-valor="${esc(p.ruta)}" title="acciones de este proyecto">⋯</span></div>`);
    }
    h.push('<div id="proyectos-vacio" class="fila dim" hidden></div></div>');
    return h;
}

/** Una fila de pendiente, con la misma acción que en el día: con ficha, el clic la abre; si no, la
 *  lleva al hilo del proyecto. */
export function filaPendiente(t: Pendiente): string {
    const accion = t.fila.ficha
        ? `data-accion="tarea" data-valor="${esc(JSON.stringify([t.fila.proveedor, t.fila.id || t.ref, t.ref]))}"`
        : `data-accion="pendiente" data-valor="${esc(t.ref)}"`;
    const ref = t.fila.proveedor ? t.ref : '·';
    return `<div class="tarea${t.enCurso ? ' encurso' : ''}" ${accion} data-completo="${esc(`${t.ref} · ${limpiarMd(t.texto)}`)}">`
        + `<span class="id">${esc(ref)}</span><span class="pri">${t.enCurso ? '●' : ''}</span>`
        + `<span class="desc">${t.fila.dueno ? `<span class="dueno">→ ${esc(t.fila.dueno)}</span>` : ''}${esc(limpiarMd(t.texto))}</span>`
        + `<span class="meta">${plazo(t.dias)}${t.fila.proveedor ? '<span></span>'
            : `<span class="menu-fila" data-accion="menu-vineta" data-valor="${esc(JSON.stringify([t.ref, t.texto, t.hilo, t.fila.dueno ?? '']))}" title="acciones de este pendiente">⋯</span>`}</span></div>`;
}

export interface DetalleProyecto {
    p: cli.JsonProyecto;
    pendientes: Pendiente[] | null;   // null: todavía leyendo
    aviso: string;
    readme: string | null;             // html ya armado; null: todavía leyendo; "": no tiene
}

/** La columna derecha: qué es, qué falta, y el README. */
export function htmlDetalleProyecto(d: DetalleProyecto | undefined): string {
    if (!d) return '<div class="vacio">elige un proyecto a la izquierda</div>';
    const { p } = d;
    const h: string[] = [`<h3>${esc(p.nombre)}</h3>`,
        `<div class="proy-meta">${p.area ? `${esc(p.area)} · ` : ''}${esc(p.arquetipo)} · <a data-accion="abrir-ruta" data-valor="${esc(`${p.ruta}/README.md`)}" title="abrir el README">${esc(p.ruta)}</a>`
        + `${p.modificado ? ` · tocado ${esc(haceCorto(p.modificado))}` : ''}${p.hilo ? ` · hilo «${esc(p.hilo)}»${p.vivo ? '' : ' (dormido)'}` : ''}</div>`,
        `<div class="acciones-ev"><a data-accion="proyecto" data-valor="${esc(p.ruta)}" title="un hilo con el agente cargando el proyecto, o el que ya hay">`
        + `${p.vivo ? 'ir a su hilo' : 'abrir con el agente'}</a>`
        + `<a data-accion="proy-consolidar" data-valor="${esc(p.ruta)}" title="un agente revisa cada pendiente abierto del README, busca si ya se hizo y lo marca con su prueba (/consolidar)">consolidar pendientes</a></div>`];
    const n = d.pendientes?.length;
    h.push(`<h4>pendientes${n ? ` · ${n}` : ''}</h4>`);
    if (d.aviso) h.push(`<div class="vacio falla">${esc(d.aviso)}</div>`);
    if (d.pendientes === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!d.pendientes.length) h.push('<div class="vacio">nada pendiente</div>');
    else h.push(...d.pendientes.map(filaPendiente));
    h.push('<h4>README</h4>');
    if (d.readme === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!d.readme) h.push('<div class="vacio">sin README</div>');
    else h.push(`<div class="proy-readme" data-base="${esc(p.ruta)}">${d.readme}</div>`);
    return h.join('');
}
