// La línea del pulso y su ventana: lo último que pasó en las pasadas que la persona no ha visto. Un agente corre una pasada
// cada hora (skill /pulso: revisa el correo, el WhatsApp y las minutas y avanza las tareas) y la deja como un resultado
// con pasadas (telar.pasadas, `pasadas = "pulso"`); telar lleva hasta cuál vio la persona.
//
//   ┌ franja ───────────────────────────────────┐
//   │ al día · 13:04                          ‹ │   ← el estado del sistema (componentes/franja.ts)
//   ├───────────────────────────────────────────┤
//   │ ∿  pulso 13:00 · 3 nuevas · 2 avanzadas +2 │   ← la última con cambios sin ver; +N, las demás con cambios
//   ├───────────────────────────────────────────┤
//   │ ⌄ DASHBOARD                               │
//
// El informe dice lo que cambió en cada pasada y qué lo causó: las tareas nuevas, avanzadas y cerradas y los borradores,
// cada uno con su causa (`por`: «correo de Beto», con el ícono de su fuente y su enlace, si viene). Lo que te espera y
// las vencidas sin propuesta se guardan en la pasada y no se muestran: lo que te espera está en Táctica.
//
// Va justo debajo de la franja, quieta como ella, y solo si hay pasadas con cambios sin ver. El ícono, en el color de los
// agentes (es trabajo de uno); una pasada en seco (que solo leyó y dijo lo que habría hecho), con el ícono tenue y «seco».
// Una fuente que falló se dice al final, en el color de cuidado. Un clic abre la ventana: las pasadas sin ver, la más nueva
// arriba, cada una con su resumen, lo que falló y sus cambios, cada uno con su causa debajo; la que no cambió nada, en una
// línea («sin cambios» y lo que llegó de cada fuente), y no cuenta. Lo que es una dirección (`tarea:T580`) se abre con un
// clic. Al cerrarla, quedan vistas (web/pulso.ts).
//
// Cada cosa trae su mundo (el que resolvió telar: el de su tarea, el que dijo el agente o "" sin clasificar) y cada pasada
// en qué mundos tiene algo sin ver (`sin_ver_en`). Con un mundo puesto, la línea y la ventana muestran solo lo de ese mundo
// y lo sin clasificar (`delMundo`, `paraMundo`): una pasada sin nada de eso no aparece ni cuenta, y las cuentas son las de
// lo que se ve. Con ambos, todo. El resumen de una de antes (sin `resumenes`) puede nombrar lo de cualquier mundo: con un
// mundo puesto, solo si la pasada no trae nada de otro.
//
// Da HTML, como el resto de la página: la línea lleva `data-accion="pulso-abrir"`; en la ventana, una dirección
// `data-direccion` y una web `data-web`, que atiende quien la abre. Cómo se ve: media/css/pulso.css.

import type { JsonCausa, JsonMarcaVisto, JsonPasada, JsonSinVer, JsonTareaPasada, JsonVisto } from '../cli';
import { esc } from '../estilo';
import { buscar } from '../web/enlaces';
import { I } from '../web/iconos';
import { pieVentana, type PropsVentana } from './ventana';

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** El día de antes de `dia` (AAAA-MM-DD). */
function anterior(dia: string): string {
    const d = new Date(`${dia}T12:00:00`);
    d.setDate(d.getDate() - 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Hoy, como AAAA-MM-DD, en la hora de aquí. */
export function hoyLocal(t = Date.now()): string {
    const d = new Date(t);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Un día dicho desde `hoy`: «hoy», «ayer», «mañana», «16-nov». */
export function diaCorto(dia: string, hoy: string): string {
    if (dia === hoy) return 'hoy';
    if (dia === anterior(hoy)) return 'ayer';
    if (anterior(dia) === hoy) return 'mañana';
    const mes = MESES[Number(dia.slice(5, 7)) - 1];
    return mes ? `${Number(dia.slice(8, 10))}-${mes}` : dia;
}

/** Cuándo empezó una pasada, dicho desde `hoy`: «13:00», «ayer 23:30», «16-nov 13:00». */
export function cuando(id: string, hoy: string): string {
    const dia = id.slice(0, 10), hm = id.slice(11, 16);
    return dia === hoy ? hm : `${diaCorto(dia, hoy)} ${hm}`;
}

/** Cuándo empezó y terminó: «13:00–13:12»; la de la noche que pasa la medianoche, «ayer 23:30–00:12». */
export function tramo(p: JsonPasada, hoy: string): string {
    const ini = cuando(p.id, hoy);
    const t = typeof p.termino === 'string' ? p.termino : '';
    return /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(t) ? `${ini}–${t.slice(11, 16)}` : ini;
}

const n = (l: unknown[] | undefined) => (Array.isArray(l) ? l.length : 0);
const plural = (k: number, una: string, varias: string) => `${k} ${k === 1 ? una : varias}`;

/** Las fuentes que fallaron (las que traen `error`). */
export const fallas = (p: JsonPasada): string[] => (p.fuentes ?? []).filter(f => f && typeof f.error === 'string' && f.error.trim()).map(f => f.fuente);

/** Si una pasada (o lo que se ve de ella) cambió algo: una tarea nueva, avanzada o cerrada, o un borrador. */
export function hayCambios(p: JsonPasada): boolean {
    const t = p.tareas ?? {};
    return n(t.nuevas) + n(t.avanzadas) + n(t.cerradas) + n(p.borradores) > 0;
}

/** Lo que cambió, en pocas palabras: las nuevas, las avanzadas, las cerradas y los borradores; si nada, «sin cambios». */
export function cuentas(p: JsonPasada): string[] {
    const t = p.tareas ?? {};
    const c = [
        n(t.nuevas) ? plural(n(t.nuevas), 'nueva', 'nuevas') : '',
        n(t.avanzadas) ? plural(n(t.avanzadas), 'avanzada', 'avanzadas') : '',
        n(t.cerradas) ? plural(n(t.cerradas), 'cerrada', 'cerradas') : '',
        n(p.borradores) ? plural(n(p.borradores), 'borrador', 'borradores') : '',
    ].filter(Boolean);
    return c.length ? c : ['sin cambios'];
}

/** Las marcas de una pasada: seco (solo leyó: lo de adentro es lo que habría hecho), de noche, pedida a mano. */
export function marcas(p: JsonPasada): string[] {
    return [p.seco ? 'seco' : '', p.modo === 'noche' ? 'noche' : '', p.pedida ? 'pedida' : ''].filter(Boolean);
}

// ── el mundo ────────────────────────────────────────────────────────────────

/** Si una cosa de ese mundo se ve con `mundo` puesto: lo suyo y lo sin clasificar; con ambos (""), todo (web/mundo.ts). */
export const veo = (de: string | undefined, mundo: string): boolean => !mundo || !de || de === mundo;

/** Si una pasada tiene algo sin ver con `mundo` puesto: de ese mundo o sin clasificar; con ambos, de cualquiera. Sin
 *  `sin_ver_en` (de un telar de antes), sí. */
export function sinVerCon(p: JsonPasada, mundo: string): boolean {
    if (!Array.isArray(p.sin_ver_en)) return true;
    return mundo ? p.sin_ver_en.some(k => veo(k, mundo)) : p.sin_ver_en.length > 0;
}

type ConMundo = { mundo?: string } | null | undefined;
/** Los mundos de las cosas de una pasada, si no los trae (`mundos`): [""] si no tiene ninguna. */
function mundosDe(p: JsonPasada): string[] {
    if (Array.isArray(p.mundos)) return p.mundos;
    const t = p.tareas ?? {};
    const cosas: ConMundo[] = [...(p.fuentes ?? []), ...(t.nuevas ?? []), ...(t.avanzadas ?? []), ...(t.cerradas ?? []),
        ...(p.te_esperan ?? []), ...(p.borradores ?? [])];
    const m = new Set([...cosas.map(x => x?.mundo ?? ''), ...Object.values(p.mundos_vencidas ?? {})]);
    return m.size ? [...m] : [''];
}

/** Lo que se ve de una pasada con `mundo` puesto ("" ambos: entera), como `pasadas.para_mundo`: lo que cambió de ese
 *  mundo y sin clasificar que todavía no se ha visto (`sin_ver_en`: lo de un mundo ya mirado con él, y lo sin clasificar
 *  ya visto con cualquiera, no vuelve), sus fuentes de ese mundo y sin clasificar, y sus resúmenes. Con `resumenes`, los
 *  de los mundos que se ven, y `resumen` (neutro: cuenta la pasada entera) solo con ambos y si nada de ella se vio; sin
 *  él (las de antes), el resumen queda solo si la pasada no trae nada de otro mundo. */
export function paraMundo(p: JsonPasada, mundo: string): JsonPasada {
    const sinVer = Array.isArray(p.sin_ver_en) ? p.sin_ver_en : null;
    if (!mundo && !sinVer) return p;
    const nuevo = (m: string | undefined) => veo(m, mundo) && (!sinVer || sinVer.includes(m ?? ''));
    const filtrar = (ve: (m: string | undefined) => boolean) => <T extends ConMundo>(l: T[] | undefined): T[] | undefined =>
        (Array.isArray(l) ? l.filter(x => !x || typeof x !== 'object' || ve(x.mundo)) : l);
    const solo = filtrar(m => veo(m, mundo)), cambio = filtrar(nuevo);
    const v: JsonPasada = { ...p, fuentes: solo(p.fuentes), te_esperan: solo(p.te_esperan), borradores: cambio(p.borradores) };
    if (p.tareas && typeof p.tareas === 'object') {
        v.tareas = { ...p.tareas, nuevas: cambio(p.tareas.nuevas), avanzadas: cambio(p.tareas.avanzadas), cerradas: cambio(p.tareas.cerradas) };
    }
    const de = p.mundos_vencidas ?? {};
    if (Array.isArray(p.vencidas_sin_propuesta)) v.vencidas_sin_propuesta = p.vencidas_sin_propuesta.filter(d => veo(de[d], mundo));
    if (p.resumenes && typeof p.resumenes === 'object') {
        v.resumenes = Object.fromEntries(Object.entries(p.resumenes).filter(([k]) => nuevo(k)));
        const entera = !sinVer || (p.mundos_cambios ?? []).every(m => sinVer.includes(m));
        if (mundo || !entera) v.resumen = '';
    } else if (mundo && mundosDe(p).some(m => m && m !== mundo)) v.resumen = '';
    return v;
}

/** Lo que se ve con `mundo` puesto ("" ambos) de lo que dio `GET /resultados/<clave>/visto`: las pasadas con algo sin ver
 *  de ese mundo o sin clasificar (las que no cambiaron nada, también), con solo lo que se ve de cada una; cuántas son
 *  (`total`) y cuántas cambiaron algo que se ve (`cambios`: `por_mundo` y `con_cambios` cuentan también las que no
 *  llegaron enteras); y hasta cuál vio (lo de ambos o lo de ese mundo, la más nueva). */
export function delMundo(d: JsonSinVer | undefined, mundo: string): { pasadas: JsonPasada[]; total: number; cambios: number; visto?: JsonMarcaVisto } {
    const todas = d?.pasadas ?? [];
    const pasadas = todas.filter(p => sinVerCon(p, mundo)).map(p => paraMundo(p, mundo));
    const conCambios = pasadas.filter(hayCambios).length;
    const dicho = mundo ? d?.por_mundo?.[mundo] : d?.con_cambios;
    // las que no llegaron enteras (más de 40 sin ver): con un mundo, a lo más esas
    const total = pasadas.length + Math.max((d?.total ?? todas.length) - todas.length, 0);
    const suyo = mundo ? d?.vistos?.[mundo] : undefined;
    const visto = suyo?.id && suyo.id > (d?.visto?.id ?? '') ? suyo : d?.visto;
    return { pasadas, total, cambios: Math.max(typeof dicho === 'number' ? dicho : conCambios, conCambios), visto };
}

/** Lo sin ver después de marcar vistas hasta `id` con `mundo` puesto ("" ambos), sin volver a leer: de las que llegan hasta
 *  esa, lo de ese mundo y lo sin clasificar deja de estar sin ver (con ambos, todo), y las que quedan sin nada se van. Las
 *  cuentas de los otros mundos guardan las que no llegaron enteras. `r`, lo que respondió la API. */
export function conVisto(d: JsonSinVer, id: string, mundo: string, r?: JsonVisto): JsonSinVer {
    const antes = d.pasadas ?? [];
    const pasadas = antes
        .map(p => (p.id > id ? p : { ...p, sin_ver_en: mundo ? (p.sin_ver_en ?? ['']).filter(k => k && k !== mundo) : [] }))
        .filter(p => (p.sin_ver_en ?? ['']).length > 0);
    // las que cambiaron algo sin ver que se ve con `m` ("" ambos)
    const cuenta = (l: JsonPasada[], m: string) => l.filter(p => hayCambios(p) && sinVerCon(p, m)).length;
    // las de `m` que no llegaron enteras siguen ahí si se marcó con otro mundo; con ese o con ambos, se vieron
    const queda = (antes: number | undefined, m: string) => (mundo && m !== mundo
        ? Math.max((antes ?? 0) - cuenta(d.pasadas ?? [], m) + cuenta(pasadas, m), cuenta(pasadas, m)) : cuenta(pasadas, m));
    const por_mundo = d.por_mundo && Object.fromEntries(Object.entries(d.por_mundo).map(([m, k]) => [m, queda(k, m)]));
    const total = mundo ? Math.max((d.total ?? antes.length) - (antes.length - pasadas.length), pasadas.length) : pasadas.length;
    return { ...d, pasadas, total, con_cambios: queda(d.con_cambios, ''), por_mundo, visto: r?.visto ?? d.visto, vistos: r?.vistos ?? d.vistos };
}

/** Los resúmenes de una pasada (lo que se ve: `paraMundo`): el suyo y el de cada mundo, en su orden. */
export function resumenes(p: JsonPasada): { mundo: string; texto: string }[] {
    const r = typeof p.resumen === 'string' && p.resumen.trim() ? [{ mundo: '', texto: p.resumen }] : [];
    for (const [m, t] of Object.entries(p.resumenes && typeof p.resumenes === 'object' ? p.resumenes : {})) {
        if (typeof t === 'string' && t.trim()) r.push({ mundo: m, texto: t });
    }
    return r;
}

export interface Linea {
    /** las sin ver, la más nueva primero (como las da `GET /resultados/<clave>/visto`), ya con lo que se ve (`delMundo`) */
    pasadas: readonly JsonPasada[];
    /** cuántas son sin ver (pueden ser más que las que llegaron enteras) */
    total?: number;
    /** cuántas de ellas cambiaron algo (las que cuentan en la línea) */
    cambios?: number;
    /** cómo se llama el resultado: «pulso» */
    nombre?: string;
    /** AAAA-MM-DD de hoy, para decir «ayer» */
    hoy: string;
    /** el mundo puesto ("" o nada: ambos): con ambos, el resumen de cada mundo va con su nombre */
    mundo?: string;
    /** la tinta de cada mundo (`trabajo` → `cian`), para su nombre */
    colores?: Readonly<Record<string, string>>;
}

/** Lo que se dice al cerrar, según el mundo puesto. */
const alCerrar = (mundo?: string) => (mundo ? `al cerrar, queda visto lo de ${mundo} y lo sin clasificar` : 'al cerrar, quedan vistas');

/** La línea: la última sin ver que cambió algo, lo que cambió y «+N» (las demás con cambios). Las que no cambiaron nada no
 *  cuentan; sin ninguna con cambios, nada. */
export function linea(l: Linea): string {
    const p = l.pasadas.find(hayCambios);
    if (!p) return '';
    const nombre = l.nombre || 'pulso';
    const mas = Math.max((l.cambios ?? l.pasadas.filter(hayCambios).length) - 1, 0);
    const m = marcas(p);
    const f = fallas(p);
    const ayuda = `la última pasada de ${nombre} con cambios que no has visto: ${tramo(p, l.hoy)}${m.length ? ` · ${m.join(' · ')}` : ''}`
        + resumenes(p).map(r => `\n${r.mundo && !l.mundo ? `${r.mundo}: ` : ''}${r.texto}`).join('')
        + (mas ? `\ny ${plural(mas, 'pasada más', 'pasadas más')} con cambios` : '')
        + `\nclic: verlas (${alCerrar(l.mundo)})`;
    return `<div class="pulso-linea${p.seco ? ' seco' : ''}" data-accion="pulso-abrir" role="button" title="${esc(ayuda)}">`
        + `<span class="pulso-icono"><span class="i">${I.pulso}</span></span>`
        + '<span class="pulso-texto">'
        + `<span class="pulso-nombre">${esc(`${nombre} ${cuando(p.id, l.hoy)}`)}</span>`
        + m.map(x => ` <span class="pulso-marca">${esc(x)}</span>`).join('')
        + cuentas(p).map(x => ` · ${esc(x)}`).join('')
        + (f.length ? ` · <span class="pulso-falla">falló ${esc(f.join(', '))}</span>` : '')
        + '</span>'
        + (mas ? `<span class="pulso-mas">+${mas}</span>` : '')
        + '</div>';
}

// ── la ventana ──────────────────────────────────────────────────────────────

/** Una dirección de objeto (de un tipo que la página conoce: `tarea:T580`), como enlace; lo demás («HABRIA tarea
 *  nueva», un id que todavía no existe), como texto tenue. Vacío, nada. Con `corto`, una web se dice por su sitio
 *  (`mail.google.com`), y entera al pasar encima. */
export function enlace(id: string, corto = false): string {
    const t = (id ?? '').trim();
    if (!t) return '';
    const h = buscar(t);
    if (h.length === 1 && h[0].i === 0 && h[0].j === t.length) {
        if (h[0].tipo === 'direccion') return `<a class="pulso-dir" data-direccion="${esc(t)}" title="abrir ${esc(t)}">${esc(t)}</a>`;
        if (h[0].tipo === 'web') {
            let sitio = t;
            try { if (corto) sitio = new URL(t).host || t; } catch { /* queda entera */ }
            return `<a class="pulso-dir" data-web="${esc(t)}" title="${corto ? esc(t) : 'abrir en otra pestaña'}">${esc(sitio)}</a>`;
        }
    }
    return `<span class="pulso-id">${esc(t)}</span>`;
}

const fila = (partes: string[], clase = '') => `<div class="pulso-fila${clase ? ` ${clase}` : ''}">${partes.filter(Boolean).join(' ')}</div>`;
const tenue = (t: string) => `<span class="pulso-tenue">${esc(t)}</span>`;

/** El ícono de una fuente (`fuente` de una causa o de las fuentes de la pasada): el correo, el WhatsApp, una minuta, lo
 *  que dijo la persona; otra, un punto. */
export function iconoFuente(fuente: string | undefined): string {
    const f = (fuente ?? '').toLowerCase();
    if (f.startsWith('correo')) return I.correo;
    if (f.startsWith('whatsapp')) return I.conversacion;
    if (f.startsWith('minuta')) return I.documento;
    if (/^(persona|respuesta|dictado)/.test(f)) return I.persona;
    return I.punto;
}

/** Lo que causó un cambio, debajo de él y tenue: el ícono de su fuente, `por` y su enlace (en un borrador, el enlace es el
 *  del borrador: va en su fila). Sin `por` (una pasada de antes de la causa), nada. */
function causa(c: JsonCausa, conEnlace = true): string {
    const por = typeof c.por === 'string' ? c.por.trim() : '';
    if (!por) return '';
    const titulo = typeof c.fuente === 'string' && c.fuente ? ` title="${esc(c.fuente)}"` : '';
    return `<div class="pulso-causa"><span class="i"${titulo}>${iconoFuente(c.fuente)}</span> ${esc(por)}`
        + (conEnlace && typeof c.enlace === 'string' && c.enlace.trim() ? ` ${enlace(c.enlace, true)}` : '') + '</div>';
}

const cambio = (fila_: string, causa_: string) => `<div class="pulso-cambio">${fila_}${causa_}</div>`;

function tareas(l: JsonTareaPasada[] | undefined, cerradas = false): string {
    return (l ?? []).map(t => cambio(fila([enlace(t.id), cerradas && t.como ? tenue(t.como) : '', esc(t.linea ?? '')]), causa(t))).join('');
}

function grupo(nombre: string, cuerpo: string): string {
    return cuerpo ? `<div class="pulso-grupo"><div class="pulso-grupo-nombre">${esc(nombre)}</div><div class="pulso-grupo-filas">${cuerpo}</div></div>` : '';
}

/** Un resumen: con ambos, el de un mundo con su nombre en su color. */
function resumen(r: { mundo: string; texto: string }, o: Pick<Linea, 'mundo' | 'colores'>): string {
    const color = r.mundo ? o.colores?.[r.mundo] : '';
    const rotulo = r.mundo && !o.mundo
        ? `<span class="pulso-mundo"${color ? ` style="--mundo-c: var(--${esc(color)})"` : ''}>${esc(r.mundo)}</span> ` : '';
    return `<div class="pulso-resumen">${rotulo}${esc(r.texto)}</div>`;
}

/** Lo que falló de cada fuente, con por qué. */
function fallos(p: JsonPasada): string {
    return (p.fuentes ?? []).filter(f => f && typeof f.error === 'string' && f.error.trim())
        .map(f => `<div class="pulso-fallo"><span class="pulso-falla">falló ${esc(f.fuente)}</span> ${tenue(f.error!.trim())}</div>`).join('');
}

const cabecera = (p: JsonPasada, hoy: string, mas = '') =>
    `<div class="pulso-cab"><span class="pulso-icono"><span class="i">${I.pulso}</span></span><span class="pulso-cuando">${esc(tramo(p, hoy))}</span>`
    + marcas(p).map(x => `<span class="pulso-marca">${esc(x)}</span>`).join('') + mas + '</div>';

/** Una pasada (lo que se ve: `paraMundo`). Con cambios: cuándo y sus marcas, los resúmenes, lo que falló y cada cambio con
 *  su causa debajo. Sin cambios, una línea: cuándo, «sin cambios» y lo que llegó de cada fuente (y lo que falló). */
export function pasada(p: JsonPasada, hoy: string, o: Pick<Linea, 'mundo' | 'colores'> = {}): string {
    if (!hayCambios(p)) {
        const llegaron = (p.fuentes ?? []).filter(f => f && f.fuente).map(f => `${f.fuente} ${Number(f.llegaron) || 0}`).join(' · ');
        const f = fallas(p);
        return `<section class="pulso-pasada sin-cambios${p.seco ? ' seco' : ''}">`
            + cabecera(p, hoy, `<span class="pulso-sin">sin cambios</span>${llegaron ? tenue(llegaron) : ''}`
                + (f.length ? `<span class="pulso-falla">falló ${esc(f.join(', '))}</span>` : ''))
            + '</section>';
    }
    const t = p.tareas ?? {};
    const borradores = (p.borradores ?? []).map(b => cambio(
        fila([esc(b.para), b.asunto ? `· ${esc(b.asunto)}` : '', enlace(b.enlace), enlace(b.tarea)]), causa(b, false))).join('');
    return `<section class="pulso-pasada${p.seco ? ' seco' : ''}">`
        + cabecera(p, hoy)
        + resumenes(p).map(r => resumen(r, o)).join('')
        + fallos(p)
        + grupo('nuevas', tareas(t.nuevas)) + grupo('avanzadas', tareas(t.avanzadas)) + grupo('cerradas', tareas(t.cerradas, true))
        + grupo('borradores', borradores)
        + '</section>';
}

export interface Ventana extends Linea {
    /** hasta cuál vio, si alguna */
    visto?: { id?: string };
}

/** La ventana con las pasadas sin ver, la más nueva arriba (`abrirVentana`, web/ventana.ts). El título cuenta las que
 *  cambiaron algo; con un mundo puesto, lo dice. */
export function ventanaPulso(v: Ventana): PropsVentana {
    const total = v.total ?? v.pasadas.length;
    const cambios = v.cambios ?? v.pasadas.filter(hayCambios).length;
    const nombre = v.nombre || 'pulso';
    const faltan = total - v.pasadas.length;
    const ayuda = [v.visto?.id ? `visto hasta ${cuando(v.visto.id, v.hoy)}` : '', alCerrar(v.mundo),
        faltan > 0 ? `aquí las ${v.pasadas.length} más nuevas de ${total}` : ''].filter(Boolean).join(' · ');
    return {
        lugar: 'centrada', clase: 'pulso',
        titulo: `${nombre}${v.mundo ? ` · ${v.mundo}` : ''} · ${plural(cambios, 'pasada con cambios', 'pasadas con cambios')}`,
        ayuda,
        cuerpo: v.pasadas.map(p => pasada(p, v.hoy, v)).join('') || '<div class="ventana-vacia">nada sin ver</div>',
        pie: pieVentana([{ texto: 'listo', tecla: '⎋', accion: 'listo', tono: 'callado' }]),
    };
}
