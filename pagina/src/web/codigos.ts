// La hoja «códigos» de la barra de la derecha (#lado, web/lado.ts): los códigos que nombra el hilo que se ve (`H3`,
// `PEN-07`, `T84`) y lo que es cada uno (docs/propuestas/codigos.md, `GET /api/codigos`). Arriba, los de su
// conversación, el último nombrado primero; abajo, los de su carpeta, por clase («Pendientes», «Hipótesis»); una caja
// para buscar por código o por texto; y al hacer clic en uno, su detalle: lo que dice su definición, el archivo (se
// abre en el visor), dónde más se nombra y lo último que dijo de él la conversación. Una tarea se ve como la da
// `telar objeto`. Los códigos los calcula la máquina donde vive el hilo; si sus tareas viven en otra, sus títulos se
// piden aparte, de a poco.

import * as cli from '../cli';
import { esc } from '../estilo';
import { modelo } from '../modelo';
import { I } from './iconos';
import * as ui from './ui';

/** cada cuánto se releen mientras se ve el mismo hilo */
const CADA = 30 * 1000;
/** cuántas tareas de otra máquina se piden de entrada (las últimas nombradas); las demás, con «más» */
const TAREAS_ALLA = 12;
/** una clase con más códigos que estos empieza plegada */
const PLEGADA_DESDE = 12;
/** en el detalle, cuántos de los archivos que lo nombran se ven */
const NOMBRADO_EN_VISIBLES = 8;
/** cuántos de la conversación se ven antes de «más» (los últimos nombrados) */
const CONVERSACION_VISIBLES = 12;

let clave = '';
let hilo = '', maquina = '';
let datos: cli.JsonCodigos | undefined;
let leida = 0;
let consulta = '';
/** el código abierto (su detalle se ve debajo de su fila) */
let abierto = '';
/** si se ven todos los de la conversación, no solo los últimos */
let todaLaConversacion = false;
const detalles = new Map<string, cli.JsonDetalleCodigo | cli.JsonObjeto | 'cargando' | string>();
/** las tareas de otra máquina: su título y estado, o null si no existe */
const tareas = new Map<string, { titulo: string; estado: string } | null | 'cargando'>();
/** las clases que se abrieron o se plegaron a mano (prefijo → abierta) */
const aMano = new Map<string, boolean>();

/** La máquina donde vive el hilo: la de «rem:máquina:hilo», o la de uno de la lista cuyo agente vive en otra. */
function maquinaDe(h: string, m: string): string {
    if (m) return m;
    const x = modelo.porNombre(h);
    return x?.remoto && x.remoto !== '?' && x.remoto !== modelo.aqui ? x.remoto : '';
}

/** Si hay algo que mostrar del hilo que se ve. */
export function hay(): boolean { return !!datos && (datos.codigos.length > 0 || datos.conversacion.some(visible)); }

/** Cuántos hay (para la pestaña). */
export function cuantos(): number { return datos ? datos.codigos.length + datos.conversacion.filter(x => x.tipo === 'tarea' && visible(x)).length : 0; }

/** Lo que se ve cambió: carga los códigos del hilo (`que`, la clave de la página) si no están o están viejos. True si
 *  cambió lo que hay que mostrar. */
export async function cargar(que: string, h: string, m: string): Promise<boolean> {
    if (!que) { const habia = !!datos; clave = ''; datos = undefined; return habia; }
    if (que !== clave) {
        clave = que; datos = undefined; consulta = ''; abierto = ''; leida = 0; todaLaConversacion = false;
        detalles.clear(); tareas.clear(); aMano.clear();
    }
    if (Date.now() - leida < CADA) return false;
    hilo = h; maquina = maquinaDe(h, m);
    leida = Date.now();
    const r = await cli.codigos(hilo, maquina);
    if (clave !== que) return false;  // ya se fue a otro
    const antes = JSON.stringify(datos ?? null);
    datos = r.datos ?? undefined;
    if (datos?.tareas_en) pedirTareas(todaLaConversacion ? Infinity : TAREAS_ALLA);
    return JSON.stringify(datos ?? null) !== antes;
}

/** Las tareas que nombra la conversación y viven en otra máquina: su título, de a una (`telar objeto`). */
function pedirTareas(cuantas = TAREAS_ALLA): void {
    const que = clave;
    const pendientes = (datos?.conversacion ?? []).filter(x => x.tipo === 'tarea' && !x.titulo);
    const faltan = pendientes.slice(0, cuantas).filter(x => !tareas.has(x.codigo));
    for (const x of faltan) {
        tareas.set(x.codigo, 'cargando');
        void cli.objeto(x.direccion ?? `tarea:${x.codigo}`).then(r => {
            if (clave !== que) return;
            tareas.set(x.codigo, r.datos ? { titulo: r.datos.titulo, estado: r.datos.estado ?? '' } : null);
            repintarLista();
        });
    }
}

/** Si un código de la conversación se muestra: una tarea de otra máquina que no existe, no. */
function visible(x: cli.JsonCodigoNombrado): boolean {
    if (x.tipo !== 'tarea' || x.titulo) return true;
    const t = tareas.get(x.codigo);
    return t !== null && t !== undefined;
}

function tituloDe(x: cli.JsonCodigoNombrado): { titulo: string; estado: string } {
    if (x.titulo) return { titulo: x.titulo, estado: x.estado ?? '' };
    const t = tareas.get(x.codigo);
    return t && t !== 'cargando' ? t : { titulo: '…', estado: '' };
}

const sinTildes = (s: string): string => s.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();

/** Si todas las palabras de la consulta están en esos textos. */
function calza(...textos: (string | undefined)[]): boolean {
    const palabras = sinTildes(consulta).split(/\s+/).filter(Boolean);
    if (!palabras.length) return true;
    const junto = sinTildes(textos.filter(Boolean).join(' '));
    return palabras.every(p => junto.includes(p));
}

/** La ruta de un archivo de la carpeta del hilo, como la abre el visor (con «máquina:» si es de otra). */
function ruta(archivo: string): string {
    const r = `${datos?.carpeta ?? ''}/${archivo}`;
    return maquina ? `${maquina}:${r}` : r;
}

function fila(codigo: string, titulo: string, extra = ''): string {
    const sel = codigo === abierto;
    return `<a class="cod-fila${sel ? ' sel' : ''}" data-cod="ver" data-c="${esc(codigo)}" title="${esc(titulo)}">`
        + `<span class="cod-c">${esc(codigo)}</span><span class="cod-t">${esc(titulo)}</span>${extra}</a>`
        + (sel ? `<div class="cod-det">${detalle(codigo)}</div>` : '');
}

/** El detalle del código abierto: lo que dice su definición, dónde está y dónde más se nombra; o la tarea. */
function detalle(codigo: string): string {
    const d = detalles.get(codigo);
    if (d === undefined || d === 'cargando') return '<div class="dim">cargando…</div>';
    if (typeof d === 'string') return `<div class="falla">${esc(d)}</div>`;
    if ('id' in d) {
        // una tarea (telar objeto)
        const o = d as cli.JsonObjeto;
        return `<div class="cod-def-cab"><b>${esc(o.titulo)}</b>${o.estado ? ` <span class="dim">· ${esc(o.estado)}</span>` : ''}</div>`
            + (o.resumen ? `<div class="cod-texto">${esc(o.resumen)}</div>` : '')
            + `<a class="cod-ir" data-cod="objeto" data-dir="${esc(o.direccion)}">${I.abrir} abrir ${esc(o.direccion)}</a>`;
    }
    const x = d as cli.JsonDetalleCodigo;
    const h: string[] = [];
    const [primera, ...otras] = x.definiciones ?? [];
    if (primera) {
        h.push(`<a class="cod-ir" data-cod="archivo" data-ruta="${esc(primera.archivo)}" title="abrirlo en el visor">${I.irArchivo} ${esc(primera.archivo)}:${primera.linea}</a>`
            + (primera.seccion ? ` <span class="dim">· ${esc(primera.seccion)}</span>` : ''));
        if (primera.campos && Object.keys(primera.campos).length) {
            h.push('<dl class="cod-campos">' + Object.entries(primera.campos).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('') + '</dl>');
        } else if (primera.texto) {
            h.push(`<div class="cod-texto md-pag">${ui.markdown(primera.texto)}</div>`);
        }
    }
    if (otras.length) {
        h.push(`<div class="cod-otras"><span class="dim">otras definiciones:</span> ` + otras.map(o =>
            `<a data-cod="archivo" data-ruta="${esc(o.archivo)}" title="${esc(o.titulo)}">${esc(o.archivo)}:${o.linea}</a>`).join(' · ') + '</div>');
    }
    if (x.nombrado_en?.length) {
        // por su nombre, con la ruta entera al pasar encima; los primeros, y cuántos más
        const vistos = x.nombrado_en.slice(0, NOMBRADO_EN_VISIBLES);
        const mas = x.nombrado_en.length - vistos.length;
        h.push(`<div class="cod-otras"><span class="dim">se nombra en:</span> ` + vistos.map(n =>
            `<a data-cod="archivo" data-ruta="${esc(n.archivo)}" title="${esc(n.archivo)}:${n.lineas[0]}">${esc(n.archivo.split('/').pop() ?? n.archivo)}:${n.lineas[0]}</a>`).join(' · ')
            + (mas > 0 ? ` <span class="dim">y ${mas}${x.nombrado_en.length >= 30 ? ' o más' : ''} más</span>` : '') + '</div>');
    }
    if (x.conversacion) {
        h.push(`<div class="cod-dijo"><span class="dim">${I.conversacion} lo último que dijo la conversación (${x.conversacion.veces} ${x.conversacion.veces === 1 ? 'vez' : 'veces'}):</span>`
            + `<div>${esc(x.conversacion.extracto)}</div></div>`);
    }
    return h.join('');
}

/** La lista: los de la conversación y los de la carpeta, por clase, con lo que calza con la consulta. */
function lista(): string {
    if (!datos) return '';
    const h: string[] = [];
    const conv = datos.conversacion.filter(x => visible(x) && calza(x.codigo, tituloDe(x).titulo, x.extracto));
    if (conv.length) {
        // los últimos nombrados; los demás, con «más» (al buscar, todos los que calzan). Las tareas de otra máquina
        // que no se pidieron todavía cuentan entre las de «más»: se piden al apretarlo
        const sinPedir = todaLaConversacion ? 0
            : datos.conversacion.filter(x => x.tipo === 'tarea' && !x.titulo && !tareas.has(x.codigo)).length;
        const corta = !todaLaConversacion && !consulta.trim() && (conv.length > CONVERSACION_VISIBLES || sinPedir > 0);
        const vistos = corta ? conv.slice(0, CONVERSACION_VISIBLES) : conv;
        if (corta && abierto && !vistos.some(x => x.codigo === abierto)) {
            const x = conv.find(y => y.codigo === abierto);
            if (x) vistos.push(x);
        }
        const mas = conv.length - vistos.length + sinPedir;
        h.push(`<div class="cod-sec"><div class="cod-tit">${I.conversacion} en esta conversación <span class="dim">${conv.length + sinPedir}</span></div>`
            + vistos.map(x => {
                const t = tituloDe(x);
                const extra = x.tipo === 'tarea' ? `<span class="cod-e">${esc(t.estado || 'tarea')}</span>` : '';
                return fila(x.codigo, t.titulo, extra);
            }).join('')
            + (corta && mas > 0 ? `<a class="cod-mas" data-cod="mas">${I.abierto} ${mas} más, nombrados antes</a>` : '')
            + '</div>');
    }
    const nombres = new Map(datos.clases.map(k => [k.prefijo, k]));
    const porClase = new Map<string, cli.JsonCodigo[]>();
    for (const c of datos.codigos) {
        if (!calza(c.codigo, c.titulo, c.resumen, nombres.get(c.clase)?.nombre)) continue;
        porClase.set(c.clase, [...(porClase.get(c.clase) ?? []), c]);
    }
    const buscando = consulta.trim() !== '';
    for (const k of datos.clases) {
        const cs = porClase.get(k.prefijo);
        if (!cs?.length) continue;
        const abierta = buscando || (aMano.get(k.prefijo) ?? k.cuantos <= PLEGADA_DESDE) || cs.some(c => c.codigo === abierto);
        h.push(`<details class="cod-sec" data-clase="${esc(k.prefijo)}"${abierta ? ' open' : ''}>`
            + `<summary class="cod-tit" title="${esc(k.archivo)}"><b>${esc(k.prefijo)}</b> ${esc(k.nombre || '')} <span class="dim">${cs.length}</span></summary>`
            + cs.map(c => fila(c.codigo, c.titulo)).join('') + '</details>');
    }
    if (!h.length) h.push(`<div class="dim">${buscando ? `nada calza con «${esc(consulta)}»` : 'ningún código'}</div>`);
    return h.join('');
}

/** La hoja entera (sin la cabecera de la barra, que es de web/lado.ts). */
export function html(): string {
    if (!datos) return '';
    const pie = datos.carpeta
        ? `<div class="cod-pie dim" title="${esc(datos.carpeta)}">${datos.codigos.length} códigos de ${datos.archivos} documentos de ${esc(datos.carpeta.split('/').pop() ?? '')}</div>`
        : '';
    return `<div class="cod-buscar"><span class="i">${I.buscar}</span><input type="search" placeholder="código o texto" spellcheck="false" value="${esc(consulta)}"></div>`
        + (datos.aviso ? `<div class="cod-aviso dim">${esc(datos.aviso)}</div>` : '')
        + `<div class="cod-lista">${lista()}</div>` + pie;
}

/** Solo la lista (al escribir en la caja, al llegar el título de una tarea): la caja no pierde el foco. */
function repintarLista(): void {
    const el = document.querySelector<HTMLElement>('#lado .cod-lista');
    if (el) el.innerHTML = lista();
}

async function abrir(codigo: string): Promise<void> {
    abierto = abierto === codigo ? '' : codigo;
    repintarLista();
    if (!abierto || (detalles.has(codigo) && detalles.get(codigo) !== 'cargando')) return;
    detalles.set(codigo, 'cargando');
    const que = clave;
    const x = datos?.conversacion.find(y => y.codigo === codigo);
    if (x?.tipo === 'tarea') {
        const r = await cli.objeto(x.direccion ?? `tarea:${codigo}`);
        if (clave !== que) return;
        detalles.set(codigo, r.datos ?? `no pude leer la tarea: ${r.error ?? 'sin respuesta'}`);
    } else {
        const r = await cli.codigos(hilo, maquina, codigo);
        if (clave !== que) return;
        detalles.set(codigo, r.datos?.detalle ?? `no pude leer ${codigo}: ${r.error ?? 'sin respuesta'}`);
    }
    repintarLista();
}

/** Los clics y lo que se escribe en la hoja; true si era suyo. Lo llama web/lado.ts. */
export function atender(e: Event): boolean {
    const t = e.target as HTMLElement;
    if (e.type === 'keydown' && (e as KeyboardEvent).key === 'Escape' && t.matches('.cod-buscar input')) {
        // ⎋ borra la búsqueda (y si ya está vacía, suelta la caja)
        if (consulta) { (t as HTMLInputElement).value = ''; consulta = ''; repintarLista(); } else (t as HTMLInputElement).blur();
        e.preventDefault(); e.stopPropagation();
        return true;
    }
    if (e.type === 'input' && t.matches('.cod-buscar input')) {
        consulta = (t as HTMLInputElement).value;
        repintarLista();
        return true;
    }
    if (e.type === 'toggle') {
        const d = t.closest<HTMLDetailsElement>('details[data-clase]');
        if (d?.dataset.clase) aMano.set(d.dataset.clase, d.open);
        return !!d;
    }
    if (e.type !== 'click') return false;
    const a = t.closest<HTMLElement>('[data-cod]');
    if (!a) return false;
    e.preventDefault();
    const que = a.dataset.cod;
    if (que === 'ver' && a.dataset.c) void abrir(a.dataset.c);
    else if (que === 'mas') { todaLaConversacion = true; pedirTareas(Infinity); repintarLista(); }
    else if (que === 'archivo' && a.dataset.ruta) void ui.abrirArchivo(ruta(a.dataset.ruta));
    else if (que === 'objeto' && a.dataset.dir) void ui.abrirDireccion(a.dataset.dir);
    return true;
}

/** Para las pruebas y la consola: lo que se cargó. */
export const _datos = (): cli.JsonCodigos | undefined => datos;
