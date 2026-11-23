// La ficha de lo que se contesta: lo que hace recordar de qué se trata, a la izquierda de la ventana de contestar
// (componentes/contestar.ts). Las personas somos malas recordando: la ventana responde, sin abrir otra cosa, cuatro
// preguntas, en este orden:
//
//   ¿De qué se trata?        el contexto de la tarea, entero; si no tiene, su título y «sin contexto escrito»
//   ¿Cómo llegamos aquí?     la historia como línea de tiempo, con fecha y quién (tú, el agente, una reunión): la creación
//                            y las últimas cuatro a la vista, lo del medio plegado con su conteo. Lo que contestaste y lo
//                            que el agente aplicó se distinguen por ícono y color
//   ¿Qué está en juego?      el peso con su porqué, quién espera, la fecha y si es dura, el tamaño y lo que bloquea
//   ¿Qué hay relacionado?    lo que dejó hecho, de dónde salió y dónde se trabaja (enlaces que se abren en la página), el
//                            proyecto con su estado y las otras tareas abiertas del proyecto
//
// De una pregunta de un módulo: su resumen entero, su porqué y su detalle (que antes se plegaban), y su archivo.
//
// Todo es puro: recibe la espera, la tarea entera (`GET /tipos/tarea/<id>`, cuando llega), su proyecto y las otras
// tareas del proyecto, y da la ficha y su HTML. Las opciones de la decisión no van aquí: van enteras a la derecha
// (contestar.ts). Lo lee y lo arma web/contestar.ts (`completar`); sus estilos, media/css/contestar.css.

import type { JsonCambio, JsonEspera, JsonProyecto, JsonTarea } from '../cli';
import { esc } from '../estilo';
import { I } from '../web/iconos';
// un texto en párrafos, con `código`, **negrita** y enlaces (los web, en una pestaña nueva)
import { parrafos } from './en-linea';
import { diasA } from '../vistas/dashboard/esperas';
import { declarado, declaradoDe } from '../vistas/dashboard/urgencia';

/** Quién hizo cada cosa de la historia: lo dice su ícono y su color. */
export type Quien = 'persona' | 'agente' | 'aplico' | 'reunion' | 'creada' | 'nota' | 'cambio';

/** Una línea de la historia, ya leída: cuándo, quién, qué (una palabra) y lo que dice. */
export interface Hito { fecha: string; hora: string; quien: Quien; que: string; texto: string }

/** Un enlace que se abre en la página (la dirección de un archivo, un proyecto, una tarea) o, si es web, aparte. */
export interface Enlace { texto: string; direccion: string; titulo?: string }

/** Un dato de lo que está en juego o de lo relacionado: su ícono, lo que dice, un enlace, una nota tenue y, si es una
 *  lista (las otras tareas del proyecto), sus enlaces y cuántas más quedan. `tono`: solo lo que pide atención (una fecha
 *  dura, una persona que espera). */
export interface Dato {
    icono: string;
    texto: string;
    enlace?: Enlace;
    nota?: string;
    tono?: 'atencion';
    lista?: Enlace[];
    mas?: number;
    /** un párrafo largo (el porqué de una pregunta): va como texto, debajo */
    parrafo?: string;
}

/** La ficha: las cuatro preguntas. `estado`: lista, o todavía leyendo la tarea, o no se pudo leer. */
export interface Ficha {
    estado: 'lista' | 'leyendo' | 'falla';
    falla?: string;
    trata: { texto: string; escrito: boolean; partes: { titulo: string; texto: string }[] };
    historia: Hito[];
    juego: Dato[];
    relacion: Dato[];
}

/** Las últimas que se ven de entrada (además de la creación); las del medio se pliegan con su conteo. */
export const HITOS_A_LA_VISTA = 4;
/** Las otras tareas abiertas del proyecto que se nombran (las demás, se cuentan). */
export const OTRAS_A_LA_VISTA = 3;

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
/** `2026-11-24` → «24-nov». */
export const diaCorto = (f: string): string => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(f ?? '');
    return m ? `${Number(m[3])}-${MESES[Number(m[2]) - 1]}` : f ?? '';
};
const texto = (v: unknown): string => (typeof v === 'string' ? v : v === undefined || v === null ? '' : String(v));

/** «en 13 d», «hoy», «mañana», «hace 17 d»: cuánto falta (o pasó) hasta una fecha. */
export function cuantoFalta(fecha: string, ahora = Date.now()): string {
    const d = diasA(fecha, ahora);
    if (d === null) return '';
    if (d === 0) return 'hoy';
    if (d === 1) return 'mañana';
    if (d === -1) return 'ayer';
    return d > 0 ? `en ${d} d` : `hace ${-d} d`;
}

/** Lo corto de una ruta, para leerla: su carpeta y su archivo («reuniones/2026-09-15-minuta.md»). */
export function rutaCorta(ruta: string): string {
    const p = ruta.replace(/\/+$/, '').split('/').filter(Boolean);
    return p.slice(-2).join('/');
}

const ES_REUNION = /\b(minuta|reuni[oó]n|meet|transcripci[oó]n)\b|\/reuniones\//i;
/** Lo que dice de dónde salió una creación que no es una reunión: entonces gana sobre la carpeta de su origen. */
const OTRA_FUENTE = /\b(whatsapp|correo|e-?mail|mail|chat)\b/i;
const APLIQUE = /^\s*apliqu[eé]\s*:\s*/i;
/** La fecha con que un agente empieza lo que escribe («16-nov 16:40: », «14-sep, »): la línea ya la dice. */
const sinFecha = (t: string): string => t.replace(/^\d{1,2}-[a-zé]{3,5}\.?(?:\s+\d{1,2}:\d{2})?\s*[:,]\s*/i, '');

/** Una línea de la historia, leída: quién la dejó y qué dice, sin lo que declara el agente delante. `origen`: de dónde
 *  salió la tarea (si es la minuta de una reunión, la creación es de una reunión). */
export function hito(c: JsonCambio, origen = ''): Hito {
    const base = { fecha: c.fecha ?? '', hora: c.hora ?? '' };
    const t = sinFecha((c.texto ?? '').trim());
    switch (c.tipo) {
        case 'respuesta':
            return { ...base, quien: 'persona', que: 'tú', texto: t };
        case 'avance': {
            // «pregunta: pide=decidir · peso=… · Decidir si…»: la marca y lo que dice, sin lo declarado
            const m = /^([\w:]+):\s+(.*)$/s.exec(t);
            const marca = m ? m[1].split(':')[0] : '';
            const resto = declarado(m ? m[2] : t).resto || (m ? m[2] : t);
            return { ...base, quien: 'agente', que: marca || 'propone', texto: sinFecha(resto) };
        }
        case 'nota':
            return APLIQUE.test(t) ? { ...base, quien: 'aplico', que: 'aplicó', texto: t.replace(APLIQUE, '') }
                : { ...base, quien: 'nota', que: 'nota', texto: t };
        case 'creada':
            // de una reunión: si lo dice su línea, o si no dice otra fuente y su origen es la minuta de una
            return { ...base, quien: ES_REUNION.test(t) || (!OTRA_FUENTE.test(t) && ES_REUNION.test(origen)) ? 'reunion' : 'creada', que: 'creada', texto: t };
        case 'mover': {
            const m = /^(\d{4}-\d{2}-\d{2})?\s*→\s*(\d{4}-\d{2}-\d{2})?$/.exec(t);
            return { ...base, quien: 'cambio', que: 'fecha', texto: m ? `vence ${m[1] ? diaCorto(m[1]) : 'sin fecha'} → ${m[2] ? diaCorto(m[2]) : 'sin fecha'}` : t };
        }
        case 'edita':
            return { ...base, quien: 'cambio', que: 'editó', texto: t };
        default:
            return { ...base, quien: 'cambio', que: c.tipo, texto: t };
    }
}

/** Las conexiones de una tarea, leídas: «- `bloquea` [T276](T276.md) · por qué» → bloquea, T276 y su porqué. */
export function conexion(linea: string): { tipo: string; id: string; porque: string } | null {
    const m = /^\s*-?\s*`?([\w-]+)`?\s+\[([A-Za-z]+\d+)\]\([^)]*\)\s*(?:·\s*(.*))?$/.exec(linea);
    if (!m) return null;
    return { tipo: m[1].replace(/_/g, ' '), id: m[2], porque: (m[3] ?? '').trim() };
}

/** El estado de un proyecto en una línea: su estado escrito, su etapa y hasta cuándo, y lo que no cuadra. */
export function estadoDeProyecto(p: JsonProyecto | undefined): string {
    if (!p) return '';
    const partes = [p.estado || p.estado_completo || '', p.plazo?.etapa ?? '', p.plazo?.fin ? `hasta el ${diaCorto(p.plazo.fin)}` : '',
        p.plazo?.aviso ?? ''].map(x => x.trim()).filter(Boolean);
    return partes.length ? partes.join(' · ') : 'sin estado escrito';
}

/** Un enlace a un archivo del repositorio, o (si es web) a su dirección. */
const aArchivo = (ruta: string): Enlace => (/^https?:\/\//.test(ruta)
    ? { texto: ruta.replace(/^https?:\/\/(www\.)?/, '').slice(0, 60), direccion: ruta, titulo: ruta }
    : { texto: rutaCorta(ruta), direccion: `archivo:${ruta}`, titulo: ruta });

/** Las otras tareas abiertas del proyecto, de la que vence antes a la sin fecha (y, a igual, la de más prioridad). */
export function otrasDelProyecto(id: string, tareas: readonly JsonTarea[]): JsonTarea[] {
    const p = (t: JsonTarea) => (t.prioridad ? t.prioridad : 9);
    return tareas.filter(t => t.id !== id && !['hecha', 'caduca', 'descartada'].includes(t.estado))
        .sort((a, b) => (a.vence || '9999').localeCompare(b.vence || '9999') || p(a) - p(b) || a.id.localeCompare(b.id, 'es', { numeric: true }));
}

/** Lo que trae la ventana para armar la ficha de una tarea: la tarea entera, su proyecto y las otras del proyecto (lo
 *  que falta, todavía no llegó); `falla`: no se pudo leer la tarea. */
export interface DeTarea { tarea?: JsonTarea; proyecto?: JsonProyecto; otras?: JsonTarea[]; falla?: string }

/** La ficha de una tarea que espera: de la espera (lo que declaró el agente al proponer) y de la tarea entera. */
export function fichaDeTarea(e: JsonEspera, de: DeTarea = {}, ahora = Date.now()): Ficha {
    const c = e.campos ?? {};
    const t = de.tarea;
    const d = declaradoDe(e);
    const contexto = (t?.contexto ?? '').trim();
    const trata = { texto: contexto || t?.titulo || e.titulo, escrito: !!contexto, partes: [] };

    const historia = (t?.historia ?? []).map(x => hito(x, t?.origen ?? ''));

    const juego: Dato[] = [];
    if (d.peso) juego.push({ icono: I.urgencia, texto: `peso ${d.peso}`, nota: d.porque });
    if (d.persona) juego.push({ icono: I.persona, texto: `${d.persona} espera la respuesta`, tono: 'atencion' });
    if (d.dura) juego.push({ icono: I.fecha, texto: `fecha dura: ${diaCorto(d.dura)}`, nota: `${cuantoFalta(d.dura, ahora)} · no se mueve`, tono: 'atencion' });
    const vence = t?.vence || texto(c.vence);
    if (vence) {
        const pasada = (diasA(vence, ahora) ?? 0) < 0;
        juego.push({ icono: I.fecha, texto: `${pasada ? 'venció' : 'vence'} el ${diaCorto(vence)}`,
            // se mueve con la barra de la ventana; con una fecha dura, esa no: es de afuera
            nota: [cuantoFalta(vence, ahora), d.dura ? 'se puede mover (la dura no: es externa)' : 'se puede mover'].filter(Boolean).join(' · ') });
    } else if (t) juego.push({ icono: I.fecha, texto: 'sin fecha' });
    const prio = t?.prioridad ?? (typeof c.prioridad === 'number' ? c.prioridad : 0);
    const tam = t?.tamano ?? '';
    if (prio || tam) juego.push({ icono: I.tamano, texto: [prio ? `prioridad ${prio}` : '', tam ? `tamaño ${tam}` : ''].filter(Boolean).join(' · ') });
    for (const linea of t?.conexiones ?? []) {
        const x = conexion(linea);
        if (x) juego.push({ icono: I.enlace, texto: x.tipo, enlace: { texto: x.id, direccion: `tarea:${x.id}` }, nota: x.porque });
        else if (linea.trim()) juego.push({ icono: I.enlace, texto: linea.replace(/^\s*-\s*/, '').replace(/[`*]/g, '') });
    }

    const relacion: Dato[] = [];
    if (d.artefacto) relacion.push({ icono: I.documento, texto: 'lo que dejó hecho', enlace: aArchivo(d.artefacto) });
    if (t?.origen) relacion.push({ icono: I.archivo, texto: 'de dónde salió', enlace: aArchivo(t.origen) });
    if (t?.trabajo) relacion.push({ icono: I.irArchivo, texto: 'dónde se trabaja', enlace: aArchivo(t.trabajo) });
    const ruta = t?.proyecto || (e.enlaces.find(x => x.startsWith('proyecto:')) ?? '').slice('proyecto:'.length).replace(/@[\w-]+$/, '');
    if (ruta) {
        const p = de.proyecto;
        relacion.push({ icono: I.carpeta, texto: 'proyecto', enlace: { texto: p?.nombre || rutaCorta(ruta), direccion: `proyecto:${ruta}`, titulo: ruta },
            nota: p ? estadoDeProyecto(p) : '' });
        if (de.otras) {
            const otras = otrasDelProyecto(t?.id ?? '', de.otras);
            relacion.push(otras.length ? {
                icono: I.lista, texto: `${otras.length === 1 ? 'otra tarea abierta' : `${otras.length} tareas abiertas más`} en el proyecto`,
                lista: otras.slice(0, OTRAS_A_LA_VISTA).map(o => ({ texto: `${o.id} ${o.titulo}`, direccion: `tarea:${o.id}`,
                    titulo: o.vence ? `vence el ${diaCorto(o.vence)}` : 'sin fecha' })),
                mas: Math.max(0, otras.length - OTRAS_A_LA_VISTA),
            } : { icono: I.lista, texto: 'ninguna otra tarea abierta en el proyecto' });
        }
    }
    if (t?.etiquetas?.length) relacion.push({ icono: I.etiqueta, texto: t.etiquetas.join(' · ') });

    return { estado: t ? 'lista' : de.falla ? 'falla' : 'leyendo', falla: de.falla, trata, historia, juego, relacion };
}

/** La ficha de una pregunta de un módulo: su resumen entero (de qué se trata), su porqué (lo que está en juego), su
 *  detalle, su archivo y quién la dejó. */
export function fichaDePregunta(e: JsonEspera, ahora = Date.now()): Ficha {
    const c = e.campos ?? {};
    const sec = (c.secciones ?? {}) as Record<string, string>;
    const d = declaradoDe(e);
    const resumen = (d.resto || sec.resumen || e.resumen || '').trim();
    const juego: Dato[] = [];
    if (d.peso) juego.push({ icono: I.urgencia, texto: `peso ${d.peso}`, nota: d.porque });
    const urg = texto(c.urgencia);
    if (urg) juego.push({ icono: I.urgencia, texto: `urgencia ${urg}` });
    if (d.persona) juego.push({ icono: I.persona, texto: `${d.persona} espera la respuesta`, tono: 'atencion' });
    if (d.dura) juego.push({ icono: I.fecha, texto: `fecha dura: ${diaCorto(d.dura)}`, nota: `${cuantoFalta(d.dura, ahora)} · no se mueve`, tono: 'atencion' });
    const vence = texto(c.vence);
    if (vence) juego.push({ icono: I.fecha, texto: `${(diasA(vence, ahora) ?? 0) < 0 ? 'venció' : 'vence'} el ${diaCorto(vence)}`, nota: cuantoFalta(vence, ahora) });
    if (sec.por_que?.trim()) juego.push({ icono: I.razonamiento, texto: 'por qué', parrafo: sec.por_que.trim() });

    const relacion: Dato[] = [];
    const archivo = e.enlaces.find(x => x.startsWith('archivo:'));
    if (archivo) relacion.push({ icono: I.archivo, texto: 'la pregunta', enlace: { texto: rutaCorta(archivo.slice('archivo:'.length)), direccion: archivo, titulo: archivo.slice('archivo:'.length) } });
    const de = texto(c.de);
    if (de) relacion.push({ icono: de.startsWith('hilo:') ? I.terminal : I.agente, texto: `la dejó ${de.replace(/^(agente|hilo):/, '')}`,
        ...de.startsWith('hilo:') ? { enlace: { texto: 'su hilo', direccion: de } } : {} });
    if (c.repo) relacion.push({ icono: I.carpeta, texto: `en ${texto(c.repo)}` });
    return {
        estado: 'lista',
        trata: { texto: resumen || e.titulo, escrito: !!resumen, partes: sec.detalle?.trim() ? [{ titulo: 'detalle', texto: sec.detalle.trim() }] : [] },
        historia: [], juego, relacion,
    };
}

// ───────────────────────── el HTML ─────────────────────────

/** Lo que va cambiando de la ficha mientras está abierta: si lo del medio de la historia está desplegado. */
export interface EstadoFicha { historia?: boolean }

const ICONO: Record<Quien, string> = {
    persona: I.persona, agente: I.agente, aplico: I.hecha, reunion: I.llamada, creada: I.nuevo, nota: I.escribir, cambio: I.editar,
};
const QUIEN: Record<Quien, string> = { persona: 'tú', agente: 'agente', aplico: 'agente', reunion: 'reunión', creada: 'creada', nota: 'nota', cambio: '' };


/** Un enlace: los de la página se abren en su lugar (cerrando la ventana); los web, aparte. */
function enlace(x: Enlace): string {
    if (/^https?:\/\//.test(x.direccion)) {
        return `<a class="ficha-enlace" href="${esc(x.direccion)}" target="_blank" rel="noopener" title="${esc(x.titulo ?? x.direccion)}">${esc(x.texto)}</a>`;
    }
    return `<a class="ficha-enlace" data-contestar="ir" data-valor="${esc(x.direccion)}" title="${esc(x.titulo ?? x.direccion)}">${esc(x.texto)}</a>`;
}

function hitoHtml(h: Hito): string {
    // quién, en una palabra (un cambio de telar, lo que cambió); lo que fue, si dice más, delante del texto
    const quien = QUIEN[h.quien] || h.que;
    const que = h.que && h.que !== quien && h.que !== 'tú' ? h.que : '';
    return `<li class="ficha-hito quien-${h.quien}">`
        + `<span class="ficha-cuando">${esc(diaCorto(h.fecha))}${h.hora ? ` ${esc(h.hora)}` : ''}</span>`
        + `<span class="ficha-quien"><span class="i">${ICONO[h.quien]}</span> ${esc(quien)}</span>`
        + `<span class="ficha-texto">${que ? `<span class="ficha-que">${esc(que)}:</span> ` : ''}${esc(h.texto)}</span></li>`;
}

function datoHtml(d: Dato): string {
    const lista = d.lista?.length
        ? `<ul class="ficha-lista">${d.lista.map(x => `<li>${enlace(x)}${x.titulo ? ` <span class="ficha-nota">${esc(x.titulo)}</span>` : ''}</li>`).join('')}`
            + `${d.mas ? `<li class="ficha-nota">y ${d.mas} más</li>` : ''}</ul>`
        : '';
    return `<li class="ficha-dato${d.tono ? ` ${d.tono}` : ''}"><span class="i">${d.icono}</span>`
        + `<span class="ficha-dato-txt"><span>${esc(d.texto)}${d.enlace ? ` ${enlace(d.enlace)}` : ''}</span>`
        + `${d.nota ? `<span class="ficha-nota">${esc(d.nota)}</span>` : ''}`
        + `${d.parrafo ? `<span class="ficha-parrafo">${parrafos(d.parrafo)}</span>` : ''}${lista}</span></li>`;
}

const seccion = (clase: string, titulo: string, cuerpo: string): string =>
    `<section class="ficha-seccion ${clase}"><div class="ficha-titulo">${esc(titulo)}</div>${cuerpo}</section>`;

/** La historia: la creación, lo del medio plegado con su conteo y las últimas a la vista; con pocas, todas. */
function historiaHtml(h: Hito[], s: EstadoFicha): string {
    if (h.length <= HITOS_A_LA_VISTA + 2) return `<ol class="ficha-historia">${h.map(hitoHtml).join('')}</ol>`;
    const medio = h.slice(1, -HITOS_A_LA_VISTA);
    return `<ol class="ficha-historia">${hitoHtml(h[0])}</ol>`
        + `<details class="ficha-mas"${s.historia ? ' open' : ''}><summary><span class="i abierto">${I.abierto}</span><span class="i plegado">${I.plegado}</span> `
        + `${medio.length} ${medio.length === 1 ? 'cosa más' : 'cosas más'} en el medio</summary><ol class="ficha-historia">${medio.map(hitoHtml).join('')}</ol></details>`
        + `<ol class="ficha-historia">${h.slice(-HITOS_A_LA_VISTA).map(hitoHtml).join('')}</ol>`;
}

/** La ficha entera: las cuatro preguntas, cada una solo si tiene algo (la primera, siempre). */
export function fichaHtml(f: Ficha, s: EstadoFicha = {}): string {
    const h: string[] = [];
    const trata = f.estado === 'leyendo' && !f.trata.escrito
        ? '<p class="ficha-nota">leyendo la tarea…</p>'
        : `${f.trata.escrito ? parrafos(f.trata.texto) : `<p>${esc(f.trata.texto)}</p><p class="ficha-nota">sin contexto escrito</p>`}`
            + f.trata.partes.map(p => `<div class="ficha-parte"><div class="ficha-parte-titulo">${esc(p.titulo)}</div>${parrafos(p.texto)}</div>`).join('');
    h.push(seccion('ficha-trata', 'De qué se trata', trata
        + (f.estado === 'falla' ? `<p class="ficha-falla">No pude leer la tarea entera${f.falla ? `: ${esc(f.falla)}` : ''}. Esto es lo que trajo la espera.</p>` : '')));
    if (f.historia.length) h.push(seccion('ficha-como', 'Cómo llegamos aquí', historiaHtml(f.historia, s)));
    if (f.juego.length) h.push(seccion('ficha-juego', 'Qué está en juego', `<ul class="ficha-datos">${f.juego.map(datoHtml).join('')}</ul>`));
    if (f.relacion.length) h.push(seccion('ficha-relacion', 'Qué hay relacionado', `<ul class="ficha-datos">${f.relacion.map(datoHtml).join('')}</ul>`));
    return `<div class="contestar-ficha">${h.join('')}</div>`;
}
