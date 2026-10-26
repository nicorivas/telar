// La semana del calendario del dashboard: de lunes a viernes, cada día en su columna, y arriba en qué se va la
// jornada de la semana. Lo que se dibuja separa lo que no se mueve de lo que la persona se reservó: una cita (con
// otras personas) va llena; un bloque propio, rayado y del color de su clase (estratégico, comercial, correo…); la
// rutina (almuerzo, traslado), apenas una línea; y una cita sin aceptar, solo con su borde (qué es cada cosa lo dice
// clases.ts). El balance cuenta las horas de la jornada por clase, lo libre incluido, y lo estratégico bloque por
// bloque, con los que pisa una cita. Cada día sale de lo mismo que el calendario de un día (plan.ts: su agenda con
// lo que dice su plan); la pestaña, lo que se lee y las acciones están en PantallaPlan.

import type * as cli from '../../cli';
import { esc } from '../../estilo';
import { type Clase, NOMBRE, type Visto, cruces, vistos } from './clases';
import type { Dia } from './dia';
import { type EventoCal, carriles, notasDe } from './eventos';
import type { Plan } from './plan';

/** La jornada que cuenta el balance, en horas del día: lo de antes y lo de después no es tiempo libre. */
export const JORNADA: readonly [number, number] = [8.5, 18];
/** Alto de una hora en la semana, en píxeles (en el día es más). */
const ALTO_HORA = 44;
/** Cada cuántos minutos se mira qué ocupa la jornada, para contarla. */
const PASO = 5;

const DIAS_CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** Un día de la semana, con lo que se leyó de él: su agenda, su plan (si hay), sus notas y sus eventos ya cruzados. */
export interface DiaSemana { fecha: string; dia?: Dia; plan?: Plan; notas?: cli.JsonNotas; evs: EventoCal[] }

/** Las partes en que se reparte la jornada, en el orden en que se dibujan: las citas, los bloques de cada clase, la
 *  rutina y lo libre. */
type Parte = 'reunion' | 'estrategico' | 'comercial' | 'bloque' | 'personal' | 'correo' | 'reserva' | 'rutina' | 'libre';
const PARTES: Parte[] = ['reunion', 'estrategico', 'comercial', 'bloque', 'personal', 'correo', 'reserva', 'rutina', 'libre'];
const NOMBRE_PARTE: Record<Parte, string> = {
    reunion: 'citas', estrategico: 'estratégico', comercial: 'comercial', bloque: 'otros bloques', personal: 'personal',
    correo: 'correo y mensajes', reserva: 'reserva', rutina: 'almuerzo y traslados', libre: 'libre',
};

function parteDe(clase: Clase): Parte {
    return clase === 'almuerzo' || clase === 'cierre' || clase === 'traslado' ? 'rutina' : clase;
}

const dos = (n: number) => String(n).padStart(2, '0');
export const isoDe = (f: Date) => `${f.getFullYear()}-${dos(f.getMonth() + 1)}-${dos(f.getDate())}`;
const hm = (ms: number) => new Date(ms).toTimeString().slice(0, 5);

/** El lunes de la semana de un día; el sábado y el domingo miran la semana que viene, la que se planifica. */
export function lunesDe(iso: string): string {
    const f = new Date(`${iso}T12:00:00`);
    const d = f.getDay();
    f.setDate(f.getDate() + (d === 0 ? 1 : d === 6 ? 2 : 1 - d));
    return isoDe(f);
}

/** Los cinco días de la semana que empieza ese lunes, más `semanas` semanas. */
export function diasDe(lunes: string, semanas = 0): string[] {
    const f = new Date(`${lunes}T12:00:00`);
    f.setDate(f.getDate() + 7 * semanas);
    return [0, 1, 2, 3, 4].map(k => { const x = new Date(f); x.setDate(f.getDate() + k); return isoDe(x); });
}

function corto(iso: string, mes = true): string {
    const f = new Date(`${iso}T12:00:00`);
    return `${DIAS_CORTOS[f.getDay()]} ${f.getDate()}${mes ? ` ${MESES_CORTOS[f.getMonth()]}` : ''}`;
}

/** Minutos como se leen, sin redondear: «45 min», «2 h», «1,5 h», «1 h 45 min». */
function horas(min: number): string {
    const m = Math.round(min);
    if (m < 60) return `${m} min`;
    if (m % 30 === 0) return `${String(m / 60).replace('.', ',')} h`;
    return `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** Un momento del día, `min` minutos después de su medianoche (con la hora local, aunque cambie el horario). */
function momento(fecha: string, min: number): number {
    const f = new Date(`${fecha}T00:00:00`);
    f.setMinutes(min);
    return f.getTime();
}

/** En qué se va la jornada de un día, en minutos por parte. Cada tramo es de lo que lo ocupa: una cita aceptada
 *  manda sobre un bloque (se comió ese tiempo), un bloque sobre una cita por aceptar, y todo sobre la rutina; sin
 *  nada, es libre. */
export function balanceDia(fecha: string, vs: Visto[]): Map<Parte, number> {
    const m = new Map<Parte, number>();
    for (const [, v] of tramos(fecha, vs)) {
        const parte = v ? parteDe(v.clase) : 'libre';
        m.set(parte, (m.get(parte) ?? 0) + PASO);
    }
    return m;
}

/** De quién es cada tramo de la jornada (su momento y lo que lo ocupa, o nada). Entre dos bloques, el que empezó
 *  más tarde: corta al otro, como la reunión que cae sobre un bloque. */
function tramos(fecha: string, vs: Visto[]): [number, Visto | undefined][] {
    const peso = (v: Visto) => v.tipo === 'cita' ? (v.pendiente ? 1 : 3) : v.tipo === 'bloque' ? 2 : 0;
    const salida: [number, Visto | undefined][] = [];
    for (let min = JORNADA[0] * 60; min < JORNADA[1] * 60; min += PASO) {
        const t = momento(fecha, min + PASO / 2);
        let mejor: Visto | undefined;
        for (const v of vs) if (v.e.inicio <= t && t < v.e.fin
            && (!mejor || peso(v) > peso(mejor) || (peso(v) === peso(mejor) && v.e.inicio > mejor.e.inicio))) mejor = v;
        salida.push([t, mejor]);
    }
    return salida;
}

/** Lo que un bloque pierde dentro de la jornada, en minutos: lo que se lleva una cita y lo que se lleva otro bloque. */
export function perdido(fecha: string, vs: Visto[], b: Visto): { citas: number; bloques: number } {
    const p = { citas: 0, bloques: 0 };
    for (const [t, v] of tramos(fecha, vs)) {
        if (t < b.e.inicio || t >= b.e.fin || !v || v === b) continue;
        if (v.tipo === 'cita') p.citas += PASO; else if (v.tipo === 'bloque') p.bloques += PASO;
    }
    return p;
}

/** Una barra con las partes de la jornada, cada una de su ancho: llena la de las citas, rayada la de los bloques. */
function barra(m: Map<Parte, number>, clase = ''): string {
    const total = [...m.values()].reduce((a, b) => a + b, 0) || 1;
    return `<span class="barra${clase ? ` ${clase}` : ''}">` + PARTES.filter(p => m.get(p)).map(p => {
        const min = m.get(p) ?? 0;
        const tipo = p === 'reunion' ? 'cita' : p === 'rutina' ? 'rutina' : p === 'libre' ? 'libre' : 'bloque';
        return `<span class="seg t-${tipo} c-${p}" style="flex:${min}" title="${esc(`${NOMBRE_PARTE[p]}: ${horas(min)} (${Math.round(100 * min / total)} %)`)}"></span>`;
    }).join('') + '</span>';
}

/** Lo estratégico de la semana, bloque por bloque: cuándo, cuánto, de qué línea (la prioridad del foco del plan,
 *  si es su bloque), con qué se cruza y cuánto pierde. */
function estrategicos(dias: DiaSemana[]): { fecha: string; e: EventoCal; linea: string; cruza: { titulo: string; cita: boolean }[];
    pierde: { citas: number; bloques: number } }[] {
    return dias.flatMap(d => {
        const vs = vistos(d.evs);
        const cr = cruces(vs);
        const foco: Plan = d.plan?.foco ?? {};
        return vs.filter(v => v.clase === 'estrategico').map(v => ({
            fecha: d.fecha, e: v.e, cruza: cr.get(v.e.id) ?? [], pierde: perdido(d.fecha, vs, v),
            linea: foco.prioridad && String(foco.bloque ?? '') === hm(v.e.inicio) ? String(foco.prioridad) : '',
        }));
    });
}

/** Arriba de la semana: en qué se va su jornada, por partes, y lo estratégico aparte. */
function htmlBalance(dias: DiaSemana[]): string {
    const total = new Map<Parte, number>();
    for (const d of dias) for (const [p, min] of balanceDia(d.fecha, vistos(d.evs))) total.set(p, (total.get(p) ?? 0) + min);
    const jornada = dias.length * (JORNADA[1] - JORNADA[0]) * 60;
    const desde = `${dos(Math.floor(JORNADA[0]))}:${dos((JORNADA[0] % 1) * 60)}`, hasta = `${dos(Math.floor(JORNADA[1]))}:${dos((JORNADA[1] % 1) * 60)}`;
    const leyenda = PARTES.filter(p => total.get(p)).map(p => {
        const tipo = p === 'reunion' ? 'cita' : p === 'rutina' ? 'rutina' : p === 'libre' ? 'libre' : 'bloque';
        return `<span class="ley c-${p} t-${tipo}"><i></i>${esc(NOMBRE_PARTE[p])} <b>${esc(horas(total.get(p) ?? 0))}</b></span>`;
    }).join('');
    const est = estrategicos(dias);
    const minEst = est.reduce((a, x) => a + (x.e.fin - x.e.inicio) / 60000, 0);
    // lo que se le va: a las citas, y a otros bloques reservados a la misma hora
    const aCitas = est.reduce((a, x) => a + x.pierde.citas, 0), aBloques = est.reduce((a, x) => a + x.pierde.bloques, 0);
    const pierde = [aCitas ? `las citas le quitan ${horas(aCitas)}` : '', aBloques ? `otros bloques, ${horas(aBloques)}` : ''].filter(Boolean);
    const conQue = (x: (typeof est)[number]) => x.cruza.some(c => c.cita) ? 'lo pisa una cita' : x.cruza.length ? 'se le cruza otro bloque' : '';
    const lineaEst = est.length
        ? `<span><b>${esc(horas(minEst))}</b> en ${est.length} ${est.length === 1 ? 'bloque' : 'bloques'}`
            + `${pierde.length ? `, <span class="sin-est">${esc(pierde.join(' y '))}</span>` : ''}</span>` + est.map(x =>
            `<a class="est${x.cruza.length ? ' pisado' : ''}" data-accion="sem-evento" data-valor="${esc(`${x.fecha}|${x.e.id}`)}"`
            + ` title="${esc(`${x.e.titulo}${x.linea ? `\n${x.linea}` : ''}${x.cruza.length ? `\nse cruza con: ${x.cruza.map(c => c.titulo).join(', ')}` : ''}`)}">`
            + `${esc(corto(x.fecha, false))} ${esc(hm(x.e.inicio))} · ${esc(horas((x.e.fin - x.e.inicio) / 60000))}`
            + `${x.linea ? ` · ${esc(x.linea.split(/[.:]/)[0])}` : ''}${conQue(x) ? ` · ${conQue(x)}` : ''}</a>`).join('')
        : '<span class="sin-est">ningún bloque estratégico esta semana</span>';
    const sinPlan = dias.filter(d => !d.plan).map(d => corto(d.fecha, false));
    return '<div class="sem-balance">'
        + `<div class="b-titulo"><b>la jornada de la semana</b><span class="dim">${esc(horas(jornada))}, de lunes a viernes de ${desde} a ${hasta}</span></div>`
        + barra(total, 'grande')
        + `<div class="leyenda">${leyenda}</div>`
        + `<div class="b-est"><span class="k">estratégico</span><span class="v">${lineaEst}</span></div>`
        + '<div class="b-clave dim"><span><i class="t-cita c-reunion"></i>lleno: una cita, no se mueve sola</span>'
        + '<span><i class="t-bloque c-bloque"></i>rayado: tiempo tuyo, se puede mover</span>'
        + '<span><i class="pendiente c-reunion"></i>solo el borde: sin aceptar</span>'
        + '<span>◇ la organizas tú</span><span class="rojo">⚠ se cruza con una cita u otro bloque</span></div>'
        + (sinPlan.length ? `<div class="b-nota dim">sin plan del día: ${esc(sinPlan.join(', '))}. Lo que se ve es el calendario: sus bloques propios no están</div>` : '')
        + '</div>';
}

/** La cabeza de un día: su nombre (un clic lo abre en la vista del día), el tipo de día que dice su plan y en qué se
 *  le va la jornada. */
function htmlCabeza(d: DiaSemana, hoy: string): string {
    const m = balanceDia(d.fecha, vistos(d.evs));
    const tipo = String(d.plan?.resumen?.tipo ?? '');
    const libre = m.get('libre') ?? 0;
    return `<a class="sem-dia${d.fecha === hoy ? ' hoy' : ''}${d.fecha < hoy ? ' pasado' : ''}" data-accion="cal-ver-dia" data-valor="${esc(d.fecha)}" title="ver el ${esc(corto(d.fecha))} en la vista del día">`
        + `<span class="uno"><span class="n">${esc(corto(d.fecha, false))}</span><span class="tipo">${esc(tipo || (d.plan ? '' : 'sin plan'))}</span></span>`
        + barra(m)
        + `<span class="uno cifras"><span>${esc(horas(m.get('reunion') ?? 0))} citas</span><span${libre ? '' : ' class="sin-est"'}>${libre ? `${esc(horas(libre))} libre` : 'sin libre'}</span></span></a>`;
}

/** Un evento en la columna de su día, o en la lista. */
function clasesDe(v: Visto, ahora: number, sel: boolean, pisado: boolean): string {
    return [`t-${v.tipo}`, `c-${v.clase}`, v.pendiente ? 'pendiente' : '', v.organiza ? 'organiza' : '', v.e.fin <= ahora ? 'pasado' : '',
        sel ? 'sel' : '', pisado ? 'pisado' : ''].filter(Boolean).join(' ');
}

function titulo(v: Visto, pisado: string[]): string {
    // pisado: con qué se cruza
    return [`${hm(v.e.inicio)}–${hm(v.e.fin)} · ${v.tipo === 'cita' ? 'cita' : NOMBRE[v.clase]}${v.pendiente ? ', sin aceptar' : ''}${v.organiza ? ', la organizas tú: la puedes mover' : ''}`,
        v.e.titulo, pisado.length ? `se cruza con: ${pisado.join(', ')}` : ''].filter(Boolean).join('\n');
}

/** La columna de un día: la jornada sombreada, las horas, la línea de «ahora» si es hoy, el cierre del día como una
 *  raya y cada evento en su alto. */
function htmlColumna(d: DiaSemana, i: number, desde: number, hasta: number, sel: string, ahora: Date): string {
    const base = momento(d.fecha, 0);
    const y = (ms: number) => ((ms - base) / 3600000 - desde) * ALTO_HORA;
    const vs = vistos(d.evs);
    const pis = new Map([...cruces(vs)].map(([id, xs]) => [id, xs.map(x => x.titulo)]));
    // lo que no dura (el cierre del día) es una raya; lo demás, un recuadro en su carril. Los bloques y la rutina
    // van a lo ancho; una cita que cae sobre uno se corre a la derecha y queda encima, y así se ve lo que pisa
    const conAlto = vs.filter(v => v.e.fin - v.e.inicio >= 60000 && v.clase !== 'cierre');
    const propios = conAlto.filter(v => v.tipo !== 'cita'), citas = conAlto.filter(v => v.tipo === 'cita');
    const lanes = new Map([...carriles(propios.map(v => v.e)), ...carriles(citas.map(v => v.e))]);
    const sobre = (v: Visto) => v.tipo === 'cita' && propios.some(b => b.e.inicio < v.e.fin && v.e.inicio < b.e.fin);
    const CORRIDA = 30;
    const t0 = ahora.getTime();
    // cada día en su columna de la rejilla, fija: el globo del detalle va encima de otras dos
    const h: string[] = [`<div class="sem-col" style="grid-area:1 / ${i + 2};height:${(hasta - desde) * ALTO_HORA}px">`,
        `<div class="fuera" style="top:0;height:${(JORNADA[0] - desde) * ALTO_HORA}px"></div>`,
        `<div class="fuera" style="top:${(JORNADA[1] - desde) * ALTO_HORA}px;bottom:0"></div>`];
    for (let hh = desde + 1; hh < hasta; hh++) h.push(`<div class="cal-linea" style="top:${(hh - desde) * ALTO_HORA}px"></div>`);
    if (t0 >= base + desde * 3600000 && t0 <= base + hasta * 3600000) h.push(`<div class="cal-ahora" style="top:${y(t0)}px"></div>`);
    for (const v of vs.filter(x => !conAlto.includes(x)))
        h.push(`<div class="sem-raya" style="top:${y(v.e.inicio)}px" title="${esc(`${hm(v.e.inicio)} · ${v.e.titulo}`)}"><span>${esc(NOMBRE[v.clase])} ${esc(hm(v.e.inicio))}</span></div>`);
    for (const v of conAlto) {
        const [k, n] = lanes.get(v.e.id) ?? [0, 1];
        const alto = Math.max(16, y(v.e.fin) - y(v.e.inicio) - 2);
        const valor = `${d.fecha}|${v.e.id}`;
        const nota = notasDe(v.e, d.notas).length > 0 || !!v.e.plan?.nota;
        const desdeIzq = sobre(v) ? CORRIDA : 0, ancho = (100 - desdeIzq) / n;
        h.push(`<div class="cal-ev ${clasesDe(v, t0, valor === sel, !!pis.get(v.e.id))}${alto < 30 ? ' corto' : ''}${desdeIzq ? ' encima' : ''}" data-accion="sem-evento" data-valor="${esc(valor)}"`
            + ` title="${esc(titulo(v, pis.get(v.e.id) ?? []))}"`
            + ` style="top:${y(v.e.inicio)}px;height:${alto}px;left:calc(${desdeIzq + ancho * k}% + 1px);width:calc(${ancho}% - 2px)">`
            + `<span class="t"><span class="h">${esc(hm(v.e.inicio))}${nota ? '✎' : ''}</span> ${v.organiza ? '◇ ' : ''}${esc(v.e.titulo)}</span></div>`);
    }
    h.push('</div>');
    return h.join('');
}

/** La semana en una lista, día por día: lo que se ve en una pantalla angosta, donde no caben cinco columnas. */
function htmlLista(dias: DiaSemana[], hoy: string, sel: string, ahora: Date): string {
    return '<div class="sem-lista">' + dias.map(d => {
        const vs = vistos(d.evs);
        const pis = new Map([...cruces(vs)].map(([id, xs]) => [id, xs.map(x => x.titulo)]));
        const filas = vs.filter(v => v.clase !== 'cierre').map(v => {
            const valor = `${d.fecha}|${v.e.id}`;
            return `<div class="sem-fila ${clasesDe(v, ahora.getTime(), valor === sel, !!pis.get(v.e.id))}" data-accion="sem-evento" data-valor="${esc(valor)}" title="${esc(titulo(v, pis.get(v.e.id) ?? []))}">`
                + `<span class="h">${esc(hm(v.e.inicio))}–${esc(hm(v.e.fin))}</span><i></i><span class="t">${v.organiza ? '◇ ' : ''}${esc(v.e.titulo)}</span></div>`;
        }).join('');
        return `${htmlCabeza(d, hoy)}${filas || '<div class="vacio">nada con hora</div>'}`;
    }).join('') + '</div>';
}

/** El detalle del evento elegido, en un globo junto a su día: a la derecha en lunes, martes y miércoles, a la izquierda
 *  en jueves y viernes, a la altura del evento (y en la lista, debajo de todo). */
function htmlGlobo(dias: DiaSemana[], sel: string, detalle: string, desde: number, hasta: number): string {
    const [fecha] = sel.split('|');
    const i = dias.findIndex(d => d.fecha === fecha);
    const e = dias[i]?.evs.find(x => `${fecha}|${x.id}` === sel);
    if (!e || !detalle) return '';
    const arriba = Math.max(0, Math.min(((e.inicio - momento(fecha, 0)) / 3600000 - desde) * ALTO_HORA, (hasta - desde) * ALTO_HORA - 420));
    const columna = i <= 2 ? i + 3 : i;
    return `<div class="sem-globo" style="grid-column:${columna} / span 2;margin-top:${arriba}px">`
        + `<a class="cerrar" data-accion="sem-cerrar" title="cerrar">×</a>${detalle}</div>`;
}

/** La semana entera: el balance, y debajo los cinco días en columnas (o en una lista, si no caben), con el detalle
 *  del evento elegido en un globo. */
export function htmlSemana(dias: DiaSemana[], o: { hoy: string; ahora: Date; sel: string; detalle: string }): string {
    const horasDe = dias.flatMap(d => {
        const base = momento(d.fecha, 0);
        return d.evs.flatMap(e => [(e.inicio - base) / 3600000, (e.fin - base) / 3600000]);
    });
    const desde = Math.max(0, Math.min(Math.floor(JORNADA[0]), ...horasDe.map(Math.floor)));
    const hasta = Math.min(24, Math.max(Math.ceil(JORNADA[1]), ...horasDe.map(Math.ceil)));
    const completos = dias.map(d => (d.dia?.agenda ?? []).filter(e => e.todo_el_dia).map(e => `<span title="${esc(e.texto)}">${esc(e.texto)}</span>`).join(''));
    const reloj: string[] = [];
    for (let hh = desde + 1; hh < hasta; hh++) reloj.push(`<div class="cal-hora" style="top:${(hh - desde) * ALTO_HORA}px">${dos(hh)}:00</div>`);
    const globo = htmlGlobo(dias, o.sel, o.detalle, desde, hasta);
    return '<div class="sem">'
        + htmlBalance(dias)
        + `<div class="sem-fila-cab"><span></span>${dias.map(d => htmlCabeza(d, o.hoy)).join('')}</div>`
        + (completos.some(Boolean) ? `<div class="sem-fila-cab completos"><span class="dim">todo el día</span>${completos.map(c => `<div class="sem-completo">${c}</div>`).join('')}</div>` : '')
        + `<div class="sem-cuerpo"><div class="sem-reloj" style="grid-area:1 / 1;height:${(hasta - desde) * ALTO_HORA}px">${reloj.join('')}</div>`
        + dias.map((d, i) => htmlColumna(d, i, desde, hasta, o.sel, o.ahora)).join('') + globo + '</div>'
        + htmlLista(dias, o.hoy, o.sel, o.ahora)
        + (o.detalle ? `<div class="sem-det-lista">${o.detalle}</div>` : '')
        + '</div>';
}

/** «‹ lun 19 – vie 23 oct ›» sobre la semana, y «esta semana» para volver cuando se está en otra. */
export function htmlNavSemana(lunes: string, estaSemana: string, cargando: boolean): string {
    const [ini, , , , fin] = diasDe(lunes);
    const mismoMes = ini.slice(5, 7) === fin.slice(5, 7);
    return `<a data-accion="cal-semana" data-valor="-1" title="semana anterior ([)">‹</a>`
        + `<span class="cal-fecha">${esc(corto(ini, !mismoMes))} – ${esc(corto(fin))}${cargando ? ' …' : ''}</span>`
        + `<a data-accion="cal-semana" data-valor="1" title="semana siguiente (])">›</a>`
        + (lunes !== estaSemana ? '<a data-accion="cal-semana" data-valor="hoy">esta semana</a>' : '');
}
