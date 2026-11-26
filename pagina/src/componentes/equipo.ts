// Equipo (prototipo): la vista de gerencia de las personas del equipo. Una fila por persona y, al abrirla, su ficha: el
// 1:1 (el último y el próximo), los compromisos en las dos direcciones, la capacidad y los proyectos; y, en una pestaña
// aparte, las apreciaciones de sus 1:1, que son de la capa privada. La pidió un agente de la persona; la
// propuesta, con de dónde sale cada dato y las reglas de privacidad, en docs/propuestas/equipo.md.
//
//   laptop                                              teléfono
//   ┌ barra: EQUIPO ──────────────────────────── ↻ ┐     ┌ EQUIPO ────── ↻ ┐   ┌ ‹ EQUIPO ──────── ↻ ┐
//   ├ lista ──────────┬ ficha ─────────────────────┤     │ ◐ Ana    1:1 mar│   │ Ana · analista…     │
//   │ ◐ Ana   1:1 mar │ Ana · analista · 100%      │     │ ● Bruno sin 1:1 │   │ [ficha] [aprec. ◇]  │
//   │ ● Bruno sin 1:1 │ [ficha] [apreciaciones ◇]  │     │ …               │   │ 1:1 · compromisos…  │
//   │ …               │ 1:1 · compromisos ·        │     └─────────────────┘   └─────────────────────┘
//   │                 │ capacidad · proyectos      │
//   └─────────────────┴────────────────────────────┘
//
// Las apreciaciones no son parte de `Persona` a propósito: no viven en el modelo de la página. Llegan como
// `EstadoApreciaciones`, que la vista de verdad arma solo después del clic en «traer del Drive» y que vuelve a «sin traer» al
// cambiar de persona, de pestaña o de mundo (o a los diez minutos). Su contenedor lleva `data-privado`: lo que indexa o
// copia la página (el buscador ⌘K, la búsqueda del modo todo) lo salta.
//
// Da HTML, como el resto de la página, con las piezas de la casa: la barra de la pantalla (pantalla.ts), el ítem (item.ts),
// la sección y el submenú (seccion.ts), las pestañas (pestanas.ts), las partes (partes.ts), la tarjeta (tarjeta.ts) y el
// botón (boton.ts). Los clics llevan `data-accion` (`eq-…`) y `data-id` o `data-valor`. Cómo se ve: media/css/equipo.css.
// Por ahora lo dibuja solo el catálogo (/componentes#equipo), con datos inventados (muestras-equipo.ts).

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { boton } from './boton';
import { circulo } from './circulo';
import { item, type Item, type Pieza } from './item';
import type { Barra } from './pantalla';
import { partes } from './partes';
import { pestanas } from './pestanas';
import { seccion, secciones } from './seccion';
import * as S from './senales';
import { listaTarjetas, tarjeta } from './tarjeta';

// ── los datos de una persona (sin las apreciaciones) ──

export interface UnoAUno {
    /** la serie del calendario: el evento recurrente de los 1:1 con esa persona */
    serie: string;
    cadencia: string;
    /** cada cuántos días toca: con esto se ve si se atrasó */
    dias: number;
    /** el último que ocurrió (AAAA-MM-DD) */
    ultimo?: string;
    /** el próximo agendado (AAAA-MM-DDTHH:MM) */
    proximo?: string;
}

/** Un compromiso: una tarea del CLI de tareas. `espera`: estado espera, a ella (te debe); `delegada`: la hace ella
 *  (`dueño`), sin estado de espera (te debe, distinta); `tuya`: tuya, con ella como quien la espera (le debes). */
export type ClaseCompromiso = 'espera' | 'delegada' | 'tuya';
export interface Compromiso {
    id: string;
    titulo: string;
    clase: ClaseCompromiso;
    desde: string;
    vence?: string;
    /** lo último que pasó: la última línea de su historia */
    ultimo?: string;
}

/** Lo que pidió por la bandeja del equipo (`telar equipo sugerencias`): lo que hoy abre la página de un pedido. */
export interface Pedido { id: string; titulo: string; cuando: string }

export interface Capacidad {
    /** la semana de la planilla de horas que se muestra */
    semana: string;
    /** sus horas de la semana, por su dedicación */
    horas: number;
    /** las que cargó en el planner; sin cargar, no viene */
    cargadas?: number;
    porProyecto: { proyecto: string; horas: number }[];
    /** las cuatro semanas de antes, en % de sus horas (la más vieja primero) */
    previas: number[];
}

export interface ProyectoDe {
    ruta: string;
    nombre: string;
    /** lo que hace en él: lidera, apoya */
    rol: string;
    clase: S.ClaseEstado;
    plazo?: string;
}

export interface Persona {
    clave: string;
    nombre: string;
    rol: string;
    /** cuánto de su tiempo es del área («100% del área») */
    dedicacion: string;
    /** desde cuándo está, si llegó hace poco */
    desde?: string;
    unoAUno: UnoAUno;
    teDebe: Compromiso[];
    leDebes: Compromiso[];
    pedidos: Pedido[];
    capacidad?: Capacidad;
    proyectos: ProyectoDe[];
}

// ── las apreciaciones: aparte, y solo después del clic ──

export interface Apreciacion { fecha: string; texto: string }
export type EstadoApreciaciones =
    | { estado: 'sin-traer' }
    | { estado: 'trayendo' }
    | { estado: 'traidas'; lista: Apreciacion[]; a: string }
    | { estado: 'falla'; error: string };

export const SIN_TRAER: EstadoApreciaciones = { estado: 'sin-traer' };
/** Cuánto duran a la vista, traídas: después se olvidan solas. */
export const OLVIDAR_MIN = 10;

export type PestanaFicha = 'ficha' | 'apreciaciones';

export interface PropsEquipo {
    personas: Persona[];
    /** el día y la hora de ahora (AAAA-MM-DDTHH:MM): con eso se dice «hace 9 d», «vence hoy» */
    ahora: string;
    /** la persona abierta ('' : ninguna) */
    elegida: string;
    pestana: PestanaFicha;
    apreciaciones: EstadoApreciaciones;
    /** el teléfono: una cosa a la vez (la lista, o la ficha de la elegida) */
    angosto?: boolean;
}

// ── las fechas, cortas ──

const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fecha = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00`);
/** «mar 1-dic» */
export const dia = (iso: string): string => { const d = fecha(iso); return `${DIAS[d.getDay()]} ${d.getDate()}-${MESES[d.getMonth()]}`; };
/** «17-nov» */
const diaSolo = (iso: string): string => { const d = fecha(iso); return `${d.getDate()}-${MESES[d.getMonth()]}`; };
const hora = (iso: string) => (iso.length > 10 ? iso.slice(11, 16) : '');
/** Días de `a` a `b` (positivo si `b` es después). */
export const entre = (a: string, b: string): number => Math.round((fecha(b).getTime() - fecha(a).getTime()) / 86400000);

// ── lo que se calcula: nada se infiere, solo se cuenta ──

/** Cómo va el 1:1: agendado, hoy, sin agendar (y si ya tocaba), o el primero. */
export function estadoUnoAUno(u: UnoAUno, ahora: string): { corto: string; tono?: Pieza['tono']; ayuda: string } {
    if (u.proximo) {
        const n = entre(ahora, u.proximo);
        if (n === 0) return { corto: `1:1 hoy ${hora(u.proximo)}`, ayuda: `${u.serie}: hoy a las ${hora(u.proximo)}` };
        return { corto: `1:1 ${dia(u.proximo)}`, ayuda: `${u.serie}: el ${dia(u.proximo)} a las ${hora(u.proximo)}${u.ultimo ? '' : ' (el primero)'}` };
    }
    if (!u.ultimo) return { corto: 'sin 1:1', tono: 'atencion', ayuda: `todavía no hay ninguno: la serie «${u.serie}» no tiene fecha` };
    const tocaba = new Date(fecha(u.ultimo).getTime() + u.dias * 86400000).toISOString().slice(0, 10);
    const atraso = entre(tocaba, ahora);
    return { corto: 'sin 1:1 agendado', tono: 'atencion',
        ayuda: `el último fue el ${dia(u.ultimo)}; con la cadencia ${u.cadencia}${atraso > 0 ? `, tocaba el ${dia(tocaba)}` : `, toca el ${dia(tocaba)}`}` };
}

/** El plazo de un compromiso: vencido y hoy, en el de cuidado; sin plazo, desde cuándo. */
export function plazo(c: Compromiso, ahora: string): Pieza {
    if (!c.vence) return { texto: `desde ${diaSolo(c.desde)}`, tono: 'tenue', ayuda: `sin fecha; desde el ${dia(c.desde)}` };
    const n = entre(ahora, c.vence);
    if (n < 0) return { texto: `venció hace ${-n} d`, tono: 'atencion', ayuda: `vencía el ${dia(c.vence)}` };
    if (n === 0) return { texto: 'vence hoy', tono: 'atencion', ayuda: `vence hoy, ${dia(c.vence)}` };
    return { texto: `vence ${dia(c.vence)}`, ayuda: `en ${n} d` };
}

export const vencidos = (p: Persona, ahora: string): number => p.teDebe.filter(c => c.vence && entre(ahora, c.vence) < 0).length;
export const abiertos = (p: Persona): number => p.teDebe.length + p.leDebes.length + p.pedidos.length;
/** La carga de la semana, de 0 a lo que sea (1 = sus horas); sin cargar, null. */
export const carga = (c: Capacidad | undefined): number | null => (c?.cargadas === undefined ? null : c.cargadas / c.horas);
const pct = (x: number) => `${Math.round(x * 100)}%`;
/** Sobre esto, la carga va en el de peligro. */
export const SOBRECARGA = 1.1;

// ── la barra ──

export function barraEquipo(p: PropsEquipo): Barra {
    const enFicha = !!p.angosto && !!p.elegida;
    return {
        ...(enFicha ? { volver: { accion: 'eq-lista', icono: I.atras, ayuda: 'volver a la lista' } } : {}),
        nombre: 'equipo', icono: I.persona,
        ayuda: `${p.personas.length} personas · solo en el mundo trabajo, y solo tú la ves`,
        acciones: [{ accion: 'eq-releer', icono: I.actualizar,
            ayuda: 'leer de nuevo el calendario, las tareas, la planilla de horas y los proyectos (las apreciaciones no: esas, solo con su botón)' }],
    };
}

// ── la lista ──

/** Una persona en la lista: la carga en un círculo, su nombre, cuántos compromisos abiertos, y el próximo 1:1. */
export function filaPersona(x: Persona, p: PropsEquipo): string {
    const c = carga(x.capacidad);
    const ranura: Pieza = c === null
        ? { circulo: { lleno: 0 }, tono: 'tenue', ayuda: 'sin horas cargadas esta semana' }
        : { circulo: { lleno: Math.min(1, c) }, ...(c > SOBRECARGA ? { tono: 'peligro' as const } : {}),
            ayuda: `esta semana: ${x.capacidad!.cargadas} de ${x.capacidad!.horas} h (${pct(c)})` };
    const u = estadoUnoAUno(x.unoAUno, p.ahora);
    const n = abiertos(x), v = vencidos(x, p.ahora);
    return item({
        accion: 'eq-persona', id: x.clave, activa: !p.angosto && x.clave === p.elegida,
        ayuda: [`${x.nombre} · ${x.rol} · ${x.dedicacion}`, n ? `${n} compromisos abiertos${v ? `, ${v} vencido${v > 1 ? 's' : ''}` : ''}` : 'nada pendiente entre los dos',
            u.ayuda, 'clic: su ficha'].join('\n'),
        inicio: [ranura], titulo: x.nombre,
        sufijo: n ? [{ texto: String(n), tono: 'tenue' }] : [],
        ...(v ? { aviso: { circulo: { tam: 'punto' }, tono: 'atencion', ayuda: `te debe ${v} vencido${v > 1 ? 's' : ''}` } as Pieza } : {}),
        meta: { texto: u.corto, ...(u.tono ? { tono: u.tono } : {}), ayuda: u.ayuda },
    });
}

export const listaEquipo = (p: PropsEquipo): string =>
    `<div class="eq-lista">${p.personas.map(x => filaPersona(x, p)).join('')}</div>`;

// ── la ficha ──

const vacia = (titulo: string): Item => ({ titulo, apagada: true, inicio: [null] });

function filasUnoAUno(x: Persona, ahora: string): string {
    const u = x.unoAUno, e = estadoUnoAUno(u, ahora);
    const ultimo = u.ultimo
        ? item({ inicio: [{ icono: I.llamada, tono: 'tenue' }], titulo: `último · ${dia(u.ultimo)}`,
            meta: { texto: `hace ${entre(u.ultimo, ahora)} d` }, accion: 'eq-evento', id: `${x.clave}|ultimo`,
            ayuda: `${u.serie}, ${dia(u.ultimo)}: clic, abrirlo en el calendario (y su minuta, si tiene)` })
        : item({ ...vacia('último · todavía no hay uno'), inicio: [{ icono: I.llamada, tono: 'tenue' }] });
    const proximo = u.proximo
        ? item({ inicio: [{ icono: I.fecha }], titulo: `próximo · ${dia(u.proximo)} ${hora(u.proximo)}`,
            meta: { texto: entre(ahora, u.proximo) === 0 ? 'hoy' : `en ${entre(ahora, u.proximo)} d` }, accion: 'eq-evento', id: `${x.clave}|proximo`,
            ayuda: e.ayuda, acciones: [{ accion: 'eq-preparar', id: x.clave, icono: I.listado,
                ayuda: 'prepararlo: /preparar-reunion con esta serie (la última minuta, los compromisos de aquí)' }] })
        : item({ inicio: [{ icono: I.fecha, tono: 'atencion' }], titulo: 'próximo · sin agendar', meta: { texto: e.corto === 'sin 1:1' ? 'el primero' : 'ya toca', tono: 'atencion', ayuda: e.ayuda },
            ayuda: e.ayuda, fijas: [{ accion: 'eq-agendar', id: x.clave, texto: 'agendar', ayuda: 'buscar un hueco en las dos agendas y proponerlo (no envía nada sin ti)' }] });
    const cadencia = item({ inicio: [null], apagada: true, titulo: `${u.cadencia} · «${u.serie}»`, ayuda: 'la serie del calendario de donde salen el último y el próximo' });
    return ultimo + proximo + cadencia;
}

function filaCompromiso(c: Compromiso, ahora: string): string {
    const inicio: Pieza = c.clase === 'espera' ? S.atencion('espera', false, 'en espera: la tarea está a su nombre')!
        : c.clase === 'delegada' ? { icono: I.persona, tono: 'tenue', ayuda: 'delegada: la hace ella o él (dueño), sin estado de espera' }
        : { icono: I.hecha, tono: 'tenue', ayuda: 'tuya: la esperan' };
    return item({ accion: 'eq-tarea', id: c.id, inicio: [inicio], titulo: c.titulo, meta: plazo(c, ahora),
        ayuda: [`${c.id} · ${c.clase === 'espera' ? 'en espera' : c.clase === 'delegada' ? 'delegada' : 'tuya'} desde el ${dia(c.desde)}`, c.ultimo ? `lo último: ${c.ultimo}` : '', 'clic: la tarea']
            .filter(Boolean).join('\n') });
}

/** Un grupo de compromisos: su cabecera de submenú (la tinta de los submenús, con su cuenta) y sus filas. La flecha va en
 *  la primera ranura, no en la tercera como en la barra: aquí las filas llevan una sola, y así los títulos calzan. Siempre
 *  abierto: son pocos. */
const grupo = (titulo: string, cuantas: number, ayuda: string, filas: string): string =>
    item({ variante: 'submenu', inicio: [{ icono: I.abierto, tono: 'tenue' }], titulo, sufijo: [{ texto: String(cuantas), tono: 'tenue' }], ayuda }) + filas;

function filasCompromisos(x: Persona, ahora: string): string {
    const h: string[] = [];
    // te debe: primero lo que está en espera (lo que hoy muestra «tareas › esperando»), después lo delegado
    const teDebe = [...x.teDebe.filter(c => c.clase === 'espera'), ...x.teDebe.filter(c => c.clase === 'delegada')];
    if (teDebe.length) h.push(grupo('te debe', teDebe.length, 'lo que esperas de ella o él: las tareas en espera a su nombre y las delegadas',
        teDebe.map(c => filaCompromiso(c, ahora)).join('')));
    if (x.leDebes.length) h.push(grupo('le debes', x.leDebes.length, 'tus tareas que ella o él espera', x.leDebes.map(c => filaCompromiso(c, ahora)).join('')));
    if (x.pedidos.length) h.push(grupo('te pide', x.pedidos.length, 'lo que pidió en la bandeja del equipo, sin resolver todavía', x.pedidos.map(d => item({
        accion: 'eq-pedido', id: d.id, inicio: [{ icono: I.pedido, tono: 'tenue' }], titulo: d.titulo, meta: { texto: `hace ${Math.max(1, entre(d.cuando, ahora))} d`, tono: 'tenue' },
        ayuda: 'clic: su página, la de hoy (preguntarle a Gestión, agregarla, descartar)' })).join('')));
    return h.join('');
}

const TINTAS = ['azul', 'verde', 'amarillo', 'cian', 'violeta'];

function filasCapacidad(x: Persona): string {
    const c = x.capacidad;
    if (!c || c.cargadas === undefined) return item(vacia(`sin horas cargadas en la planilla de horas${c ? ` de la semana del ${c.semana}` : ''}`));
    const k = carga(c)!;
    const total = item({ inicio: [{ circulo: { lleno: Math.min(1, k) }, ...(k > SOBRECARGA ? { tono: 'peligro' as const } : {}) }],
        titulo: `semana del ${c.semana} · ${c.cargadas} de ${c.horas} h`, meta: { texto: pct(k), ...(k > SOBRECARGA ? { tono: 'peligro' as const } : {}) },
        ayuda: `lo que cargó en la planilla de horas contra sus horas (${x.dedicacion})` });
    const libre = Math.max(0, c.horas - c.cargadas);
    const franja = `<div class="eq-partes">${partes({ ayuda: 'cada proyecto, por sus horas; lo gris, lo que no cargó', partes: [
        ...c.porProyecto.map((y, i) => ({ clave: y.proyecto, valor: y.horas, tinta: TINTAS[i % TINTAS.length], ayuda: `${y.proyecto}: ${y.horas} h` })),
        ...(libre ? [{ clave: 'sin cargar', valor: libre, tinta: 'linea', ayuda: `sin cargar: ${libre} h` }] : [])] })}</div>`;
    const cada = c.porProyecto.map((y, i) => item({ inicio: [{ html: `<span class="eq-tinta" style="--parte: var(--${TINTAS[i % TINTAS.length]})"></span>` }],
        titulo: y.proyecto, meta: { texto: `${y.horas} h`, tono: 'tenue' } })).join('');
    const antes = item({ inicio: [null], apagada: true, titulo: `las cuatro de antes · ${c.previas.map(v => `${v}%`).join(' · ')}`,
        ayuda: 'las horas cargadas de las cuatro semanas anteriores, en % de las suyas' });
    return total + franja + cada + antes;
}

function filasProyectos(x: Persona, ahora: string): string {
    return x.proyectos.map(y => item({ accion: 'eq-proyecto', id: y.ruta, inicio: [S.estadoIniciativa(y.clase)], titulo: y.nombre,
        sufijo: [{ texto: y.rol, tono: 'tenue' }],
        ...(y.plazo ? { meta: { texto: `al ${diaSolo(y.plazo)}`, tono: 'tenue' as const, ayuda: `plazo del PMO: ${dia(y.plazo)}, en ${entre(ahora, y.plazo)} d` } } : {}),
        ayuda: `${y.nombre}: ${y.rol}\nclic: abrirlo en proyectos` })).join('');
}

/** La pestaña «ficha»: el 1:1, los compromisos, la capacidad y los proyectos, una sección tras otra. */
export function ficha(x: Persona, ahora: string): string {
    return `<div class="eq-secciones">${secciones([
        seccion({ clave: 'eq-1a1', titulo: '1:1', abierta: true, ayuda: 'el último y el próximo, de la serie del calendario', filas: () => filasUnoAUno(x, ahora) }),
        seccion({ clave: 'eq-compromisos', titulo: 'compromisos', cuenta: abiertos(x), abierta: true, ayuda: 'en las dos direcciones, de las tareas',
            filas: () => filasCompromisos(x, ahora), vacia: vacia('nada pendiente entre los dos') }),
        seccion({ clave: 'eq-capacidad', titulo: 'capacidad', abierta: true, ayuda: 'las horas de la semana, de la planilla de horas', filas: () => filasCapacidad(x) }),
        seccion({ clave: 'eq-proyectos', titulo: 'proyectos', cuenta: x.proyectos.length, abierta: true, ayuda: 'donde está, del PMO',
            filas: () => filasProyectos(x, ahora), vacia: vacia('en ningún proyecto') }),
    ])}</div>`;
}

/** La pestaña «apreciaciones»: sin traer, el botón; traídas, una tarjeta por 1:1 y cómo se olvidan. */
export function apreciaciones(x: Persona, e: EstadoApreciaciones): string {
    const abre = `<div class="eq-privado" data-privado="apreciaciones">`;
    if (e.estado === 'sin-traer' || e.estado === 'falla') {
        return abre + '<p class="eq-explica">Lo que anotaste en tus 1:1 con ' + esc(x.nombre) + '. Vive en tu Drive, no en telar: se trae solo '
            + 'cuando lo pides, no queda guardado en la página, ni en el repositorio, ni en el estado de telar, y se olvida al cambiar de '
            + `persona, de pestaña o de mundo, o a los ${OLVIDAR_MIN} minutos.</p>`
            + (e.estado === 'falla' ? `<p class="eq-explica tono-peligro">no se pudo leer el Drive: ${esc(e.error)}</p>` : '')
            + `<div class="eq-traer">${boton({ texto: 'traer del Drive', accion: 'eq-traer', valor: x.clave, icono: I.traer,
                ayuda: `leer ahora las apreciaciones de ${x.nombre} de tu Drive, solo para mirarlas aquí` })}</div></div>`;
    }
    if (e.estado === 'trayendo') {
        return `${abre}<p class="eq-explica">${circulo({ mov: 'gira' })} leyendo tu Drive…</p></div>`;
    }
    const tarjetas = e.lista.map(a => tarjeta({ titulo: `1:1 del ${dia(a.fecha)}`, cuerpo: a.texto, holgada: true }));
    return abre
        + (tarjetas.length ? listaTarjetas(tarjetas, 'eq-tarjetas') : item(vacia('no hay apreciaciones anotadas todavía')))
        + `<p class="eq-explica">traídas de tu Drive a las ${esc(hora(e.a))}: se olvidan al salir de aquí o a los ${OLVIDAR_MIN} minutos. `
        + `<a data-accion="eq-olvidar" data-valor="${esc(x.clave)}" title="sacarlas de la página ya">olvidar ahora</a></p></div>`;
}

/** La ficha de una persona: quién es, las dos pestañas y la que se ve. */
export function fichaPersona(p: PropsEquipo): string {
    const x = p.personas.find(y => y.clave === p.elegida);
    if (!x) return '<div class="eq-ficha"><div class="eq-nada">elige a alguien a la izquierda</div></div>';
    const quien = [x.rol, x.dedicacion, x.desde ? `desde el ${dia(x.desde)}` : ''].filter(Boolean).join(' · ');
    return `<div class="eq-ficha" data-persona="${esc(x.clave)}"><div class="eq-cab"><b>${esc(x.nombre)}</b> <span class="eq-quien">${esc(quien)}</span></div>`
        + pestanas({ nombre: `ficha de ${x.nombre}`, activa: p.pestana, accion: 'eq-pestana', clases: ['eq-pest'], pestanas: [
            { valor: 'ficha', nombre: 'ficha', icono: I.ficha },
            { valor: 'apreciaciones', nombre: 'apreciaciones', icono: I.privado,
                ayuda: 'lo que anotaste en sus 1:1, de tu Drive: se trae solo con un clic y se olvida al salir' }] })
        + (p.pestana === 'apreciaciones' ? apreciaciones(x, p.apreciaciones) : ficha(x, p.ahora))
        + '</div>';
}

/** El cuerpo de la pantalla: en el laptop, la lista y la ficha lado a lado; en el teléfono, la lista o la ficha. */
export function equipo(p: PropsEquipo): string {
    if (p.angosto) return `<div class="equipo angosto">${p.elegida ? fichaPersona(p) : listaEquipo(p)}</div>`;
    return `<div class="equipo eq-dos">${listaEquipo(p)}${fichaPersona(p)}</div>`;
}
