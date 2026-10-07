// El plan del día y el calendario del dashboard: lo que deja una skill de planificación
// (`telar resultado plan`) y la agenda del día con las notas de cada evento (`telar evento`).
// Aquí solo se dibuja; el estado y las acciones viven en `hoy.ts`.

import * as cli from '../cli';
import { esc } from '../estilo';
import { Dia, seccion } from './dia';

/** El plan, tal como lo escribe la skill: telar no fija su forma, se dibuja lo que trae. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Plan = Record<string, any>;

/** Alto de una hora en el calendario, en píxeles. */
const ALTO_HORA = 56;
/** Lo que dura un evento sin fin declarado, en minutos. */
const SIN_FIN = 30;

export const CSS_PLAN = `
  .plan-nav { display: flex; gap: 2ch; align-items: baseline; padding: 0 1ch .5lh; color: var(--dim); }
  .plan-nav a { color: var(--azul); }
  .plan-txt { padding: .2lh 1ch; } .plan-txt p { margin: .2lh 0; }
  .plan-riesgo { color: var(--rojo); }
  .plan-fila { display: grid; grid-template-columns: 12ch minmax(0, 1fr); gap: 1ch; padding: .15lh 1ch; }
  .plan-fila .k { color: var(--dim); }
  .plan-fila .sub { color: var(--dim); display: block; }
  .plan-fila.estrategico .v { font-weight: bold; }
  .cal-dos { display: grid; grid-template-columns: minmax(28ch, 1fr) minmax(32ch, 1.2fr); gap: 2ch; align-items: start; }
  .cal { position: relative; margin: 1lh 0 1lh 6ch; border-left: 1px solid var(--linea); }
  .cal-hora { position: absolute; left: -6ch; width: 5ch; text-align: right; color: var(--dim); font-size: .85em; transform: translateY(-.6em); }
  .cal-linea { position: absolute; left: 0; right: 0; border-top: 1px solid var(--linea); }
  .cal-ahora { position: absolute; left: 0; right: 0; border-top: 2px solid var(--rojo); z-index: 3; }
  .cal-ev { position: absolute; box-sizing: border-box; padding: 2px 6px; overflow: hidden; cursor: pointer;
            background: color-mix(in srgb, var(--azul) 22%, transparent); border-left: 3px solid var(--azul); }
  .cal-ev:hover { background: color-mix(in srgb, var(--azul) 34%, transparent); }
  .cal-ev.plan { background: transparent; border: 1px dashed var(--amarillo); border-left: 3px solid var(--amarillo); }
  .cal-ev.pasado { opacity: .55; }
  .cal-ev.sel { outline: 2px solid var(--fg); z-index: 2; }
  .cal-ev .h { color: var(--dim); font-size: .85em; } .cal-ev .t { display: block; }
  .cal-ev.corto { white-space: nowrap; text-overflow: ellipsis; } .cal-ev.corto .t { display: inline; margin-left: .5ch; }
  .cal-ev .marca-nota { color: var(--amarillo); }
  .cal-dia-completo { padding: .2lh 1ch; color: var(--dim); }
  .cal-det { position: sticky; top: 4lh; padding: .5lh 1ch; border-left: 1px solid var(--linea); text-align: left; }
  .cal-det h3 { margin: 0 0 .3lh; }
  .cal-det .cal-meta { color: var(--dim); margin-bottom: .5lh; }
  .cal-det .acciones-ev { display: flex; gap: 2ch; margin: .3lh 0 .7lh; }
  .cal-nota { padding: .3lh 0; border-top: 1px solid var(--linea); }
  .cal-nota .de { color: var(--dim); font-size: .85em; }
  .cal-escribir { margin-top: 1lh; display: flex; flex-direction: column; gap: .4lh; }
  .cal-escribir textarea { font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--linea); padding: .3lh 1ch; resize: vertical; }
  .cal-escribir textarea:focus { outline: none; border-color: var(--amarillo); }
  .cal-escribir a { align-self: flex-end; }
`;

function t(s: unknown): string {
    return esc(String(s ?? '')).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}

function fila(k: unknown, v: string, clase = ''): string {
    return `<div class="plan-fila${clase ? ' ' + clase : ''}"><span class="k">${t(k)}</span><span class="v">${v}</span></div>`;
}

/** La pestaña del plan: lo que dejó la skill ese día, con flechas para ir a otros días. */
export function htmlPlan(r: cli.JsonResultado | undefined, error: string, cargando: boolean): string[] {
    const h: string[] = [];
    if (!r) {
        h.push(seccion('plan del día', 'amarillo'));
        h.push(`<div class="vacio${error ? ' falla' : ''}">${esc(error || (cargando ? 'leyendo el plan…' : 'sin plan'))}</div></section>`);
        return h;
    }
    const dias = [...(r.dias ?? [])].sort();
    const i = dias.indexOf(r.dia);
    const antes = i > 0 ? dias[i - 1] : (i < 0 ? dias.filter(x => x < r.dia).pop() : undefined);
    const despues = i >= 0 && i < dias.length - 1 ? dias[i + 1] : (i < 0 ? dias.find(x => x > r.dia) : undefined);
    const nav = `<div class="plan-nav">`
        + (antes ? `<a data-accion="plan-dia" data-valor="${esc(antes)}">‹ ${esc(antes)}</a>` : '<span></span>')
        + `<b>${esc(r.dia)}</b>`
        + (despues ? `<a data-accion="plan-dia" data-valor="${esc(despues)}">${esc(despues)} ›</a>` : '')
        + `<a data-accion="plan-dia" data-valor="">hoy</a>`
        + `<span>${r.desde && r.desde !== 'aquí' ? `leído de ${esc(r.desde)}` : 'leído aquí'}</span></div>`;
    h.push(seccion(r.nombre || 'plan del día', 'amarillo', '', ''));
    h.push(nav);
    if (r.aviso) h.push(`<div class="vacio falla">${esc(r.aviso)}</div>`);
    if (r.contenido === null || r.contenido === undefined) {
        h.push(`<div class="vacio">no hay plan del ${esc(r.dia)}</div></section>`);
        return h;
    }
    if (r.formato === 'md') {
        h.push(`<div class="plan-txt"><p style="white-space:pre-wrap">${esc(String(r.contenido))}</p></div></section>`);
        return h;
    }
    const p = r.contenido as Plan;
    const re = p.resumen ?? {};
    if (re.texto || re.riesgo) {
        const carga = re.carga ? `${re.carga.reuniones_h ?? '?'} h de reuniones, ${re.carga.enfocado_min ?? '?'} min enfocados (tope ${re.carga.tope_min ?? '?'})` : '';
        h.push(`<div class="plan-txt"><p>${t(re.texto)}</p>${re.riesgo ? `<p class="plan-riesgo">${t(re.riesgo)}</p>` : ''}`
            + `${carga ? `<p class="dim">${esc(carga)}</p>` : ''}${p.borrador ? '<p class="dim">borrador: las prioridades de la semana no están aprobadas</p>' : ''}</div>`);
    }
    h.push('</section>');
    const fo = p.foco ?? {};
    if (fo.paso || fo.prioridad) {
        h.push(seccion('foco estratégico', 'magenta', fo.bloque ?? ''));
        if (fo.prioridad) h.push(fila('prioridad', t(fo.prioridad)));
        if (fo.paso) h.push(fila('el paso', t(fo.paso)));
        if (fo.terminado) h.push(fila('terminado si', t(fo.terminado)));
        h.push('</section>');
    }
    const res: Plan[] = p.resultados ?? [];
    if (res.length) {
        h.push(seccion('resultados', 'verde', String(res.length)));
        res.forEach((x, k) => {
            const estado = p.retrospectiva?.resultados?.[k];
            h.push(fila(x.tipo, `${t(x.texto)}${x.logrado_si ? `<span class="sub">logrado si: ${t(x.logrado_si)}</span>` : ''}`
                + `${estado ? `<span class="sub">retro: ${t(estado)}</span>` : ''}`));
        });
        h.push('</section>');
    }
    const ag: Plan[] = p.agenda ?? [];
    if (ag.length) {
        h.push(seccion('agenda', 'azul', String(ag.length), '<a data-accion="calendario">ver en el calendario</a>'));
        for (const x of ag) {
            h.push(fila(`${x.inicio ?? ''}${x.fin ? '–' + x.fin : ''}`,
                `${t(x.titulo)}${x.nota ? `<span class="sub">${t(x.nota)}</span>` : ''}${x.ficha?.decision ? `<span class="sub">decidir: ${t(x.ficha.decision)}</span>` : ''}`,
                x.estrategico ? 'estrategico' : ''));
        }
        h.push('</section>');
    }
    const tac = p.tacticos ?? {};
    const hoy: Plan[] = tac.hoy ?? [];
    if (hoy.length || (tac.no_hoy ?? []).length) {
        h.push(seccion('tácticos', 'cian', String(hoy.length)));
        for (const x of hoy) h.push(fila(x.ref ?? '', `${t(x.texto)}${x.donde ? `<span class="sub">${t(x.donde)}</span>` : ''}`));
        for (const x of (tac.no_hoy ?? []) as Plan[]) h.push(fila(`no hoy ${x.ref ?? ''}`, `<span class="dim">${t(x.texto ?? x)}</span>`));
        h.push('</section>');
    }
    const listas: [string, string, Plan[], (x: Plan) => [string, string]][] = [
        ['personas', 'violeta', p.personas ?? [], x => [x.quien, t(x.para)]],
        ['personal', 'verde', p.personal ?? [], x => [x.ref ?? '', t(x.texto)]],
        ['los próximos días', 'azul', p.proximos ?? [], x => [x.dia, t(x.texto)]],
    ];
    for (const [nombre, color, lista, par] of listas) {
        if (!lista.length) continue;
        h.push(seccion(nombre, color, String(lista.length)));
        for (const x of lista) { const [k, v] = par(x); h.push(fila(k, v)); }
        h.push('</section>');
    }
    const rt = p.retrospectiva;
    if (rt) {
        h.push(seccion('retrospectiva', 'dim'));
        if (rt.imprevistos) h.push(fila('imprevistos', t(rt.imprevistos)));
        if (rt.energia !== undefined) h.push(fila('energía', t(rt.energia)));
        if (rt.nota) h.push(fila('nota', t(rt.nota)));
        h.push('</section>');
    }
    const huecos: unknown[] = p.huecos ?? [];
    if (huecos.length) {
        h.push(seccion('lo que la skill no pudo ver', 'dim', String(huecos.length)));
        huecos.forEach((x, k) => h.push(fila(String(k + 1), `<span class="dim">${t(x)}</span>`)));
        h.push('</section>');
    }
    return h;
}

/** Un evento del calendario: del calendario de la persona, o un bloque que propuso el plan. */
export interface EventoCal {
    id: string; titulo: string; inicio: number; fin: number; lugar: string; url: string; asistentes: string[];
    /** lo que el plan dice de este evento, o el bloque mismo si no está en el calendario */
    plan?: Plan;
    /** un bloque del plan que no está en el calendario */
    soloPlan: boolean;
}

function aMs(fecha: string, hhmm: string): number {
    return Date.parse(`${fecha}T${hhmm.length === 5 ? hhmm : hhmm.slice(0, 5)}:00`);
}

function normal(s: string): string {
    return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
}

function parecidos(a: string, b: string): boolean {
    const x = new Set(normal(a).split(' ').filter(w => w.length > 3));
    const y = normal(b).split(' ').filter(w => w.length > 3);
    return y.some(w => x.has(w));
}

/** Los eventos del día con lo que el plan dice de cada uno. Un ítem del plan se pega al evento que
 *  empieza a la misma hora (±10 min) y comparte alguna palabra con su título; si no hay, es un bloque
 *  propio del plan y se dibuja aparte. */
export function eventosDelDia(d: Dia, plan?: Plan): EventoCal[] {
    const evs: EventoCal[] = (d.agenda ?? []).filter(e => e.cuando && !e.todo_el_dia).map(e => {
        const ini = Date.parse(e.cuando ?? '');
        const fin = e.fin ? Date.parse(e.fin) : NaN;
        return { id: e.id || `${e.cuando}:${e.texto}`, titulo: e.texto, inicio: ini, fin: Number.isNaN(fin) ? ini + SIN_FIN * 60000 : fin,
            lugar: e.lugar ?? '', url: e.url ?? '', asistentes: e.asistentes ?? [], soloPlan: false };
    });
    for (const x of (plan?.agenda ?? []) as Plan[]) {
        if (!x.inicio) continue;
        const ini = aMs(d.fecha, String(x.inicio));
        if (Number.isNaN(ini)) continue;
        const par = (x.evento ? evs.find(e => e.id === x.evento && !e.plan) : undefined)
            ?? evs.find(e => !e.plan && !e.soloPlan && Math.abs(e.inicio - ini) <= 10 * 60000 && parecidos(e.titulo, String(x.titulo ?? '')));
        if (par) { par.plan = x; continue; }
        const fin = x.fin ? aMs(d.fecha, String(x.fin)) : NaN;
        evs.push({ id: `plan:${x.inicio}:${x.titulo}`, titulo: String(x.titulo ?? ''), inicio: ini,
            fin: Number.isNaN(fin) ? ini + SIN_FIN * 60000 : fin, lugar: '', url: '', asistentes: [], plan: x, soloPlan: true });
    }
    return evs.sort((a, b) => a.inicio - b.inicio || a.fin - b.fin);
}

/** Las notas de un evento: por su id, o por hora y título si el id cambió. */
export function notasDe(e: EventoCal, notas?: cli.JsonNotas): cli.JsonNota[] {
    const ev = notas?.eventos ?? {};
    if (ev[e.id]) return ev[e.id].notas;
    const hm = new Date(e.inicio).toTimeString().slice(0, 5);
    const otro = Object.values(ev).find(x => x.inicio === hm && x.titulo && parecidos(x.titulo, e.titulo));
    return otro?.notas ?? [];
}

/** Carriles: eventos que se pisan van lado a lado. */
function carriles(evs: EventoCal[]): Map<string, [number, number]> {
    const salida = new Map<string, [number, number]>();
    let grupo: EventoCal[] = [];
    let finGrupo = -Infinity;
    const cerrar = () => {
        const fines: number[] = [];
        const de = new Map<string, number>();
        for (const e of grupo) {
            let k = fines.findIndex(f => f <= e.inicio);
            if (k < 0) { k = fines.length; fines.push(0); }
            fines[k] = e.fin;
            de.set(e.id, k);
        }
        for (const e of grupo) salida.set(e.id, [de.get(e.id) ?? 0, fines.length]);
        grupo = [];
        finGrupo = -Infinity;
    };
    for (const e of evs) {
        if (grupo.length && e.inicio >= finGrupo) cerrar();
        grupo.push(e);
        finGrupo = Math.max(finGrupo, e.fin);
    }
    if (grupo.length) cerrar();
    return salida;
}

/** El calendario en dos columnas: a la izquierda el día con todos sus eventos, a la derecha el
 *  detalle y las notas del que se eligió. */
export function htmlCalendario(d: Dia, evs: EventoCal[], notas: cli.JsonNotas | undefined, sel: string, ahora: Date, aviso: string, general = ''): string[] {
    const h: string[] = [seccion('calendario', 'azul', d.fecha, '<a data-accion="plan">plan del día</a>')];
    if (aviso) h.push(`<div class="vacio falla">${esc(aviso)}</div>`);
    const completos = (d.agenda ?? []).filter(e => e.todo_el_dia);
    for (const e of completos) h.push(`<div class="cal-dia-completo">todo el día: ${esc(e.texto)}</div>`);
    if (!evs.length) {
        h.push(`<div class="vacio">${d.agenda === null ? 'sin calendario consultado · <kbd>r</kbd>' : 'nada con hora hoy'}</div></section>`);
        return h;
    }
    const base = new Date(`${d.fecha}T00:00:00`).getTime();
    const horaDe = (ms: number) => (ms - base) / 3600000;
    const desde = Math.min(8, Math.floor(Math.min(...evs.map(e => horaDe(e.inicio)))));
    const hasta = Math.max(19, Math.ceil(Math.max(...evs.map(e => horaDe(e.fin)))));
    const y = (ms: number) => (horaDe(ms) - desde) * ALTO_HORA;
    const lanes = carriles(evs);
    const elegido = evs.find(e => e.id === sel) ?? evs.find(e => e.fin > ahora.getTime()) ?? evs[0];
    const col: string[] = [`<div class="cal" style="height:${(hasta - desde) * ALTO_HORA}px">`];
    for (let hh = desde; hh <= hasta; hh++) {
        col.push(`<div class="cal-linea" style="top:${(hh - desde) * ALTO_HORA}px"></div>`
            + `<div class="cal-hora" style="top:${(hh - desde) * ALTO_HORA}px">${String(hh).padStart(2, '0')}:00</div>`);
    }
    const t0 = ahora.getTime();
    if (horaDe(t0) >= desde && horaDe(t0) <= hasta) col.push(`<div class="cal-ahora" style="top:${y(t0)}px"></div>`);
    for (const e of evs) {
        const [k, n] = lanes.get(e.id) ?? [0, 1];
        const alto = Math.max(20, y(e.fin) - y(e.inicio) - 2);
        const hm = new Date(e.inicio).toTimeString().slice(0, 5);
        const tieneNotas = notasDe(e, notas).length > 0 || !!e.plan?.nota;
        const clases = ['cal-ev', e.soloPlan ? 'plan' : '', e.fin <= t0 ? 'pasado' : '', e === elegido ? 'sel' : '',
            alto < 40 ? 'corto' : ''].filter(Boolean).join(' ');
        col.push(`<div class="${clases}" data-accion="evento-sel" data-valor="${esc(e.id)}" title="${esc(e.titulo)}"`
            + ` style="top:${y(e.inicio)}px;height:${alto}px;left:calc(${(100 * k) / n}% + 2px);width:calc(${100 / n}% - 4px)">`
            + `<span class="h">${esc(hm)}${tieneNotas ? ' <span class="marca-nota">✎</span>' : ''}</span><span class="t">${esc(e.titulo)}</span></div>`);
    }
    col.push('</div>');
    h.push(`<div class="cal-dos"><div>${col.join('')}</div><div class="cal-det">${htmlDetalle(elegido, notas, d.fecha)}${htmlEscribir(elegido, general)}</div></div></section>`);
    return h;
}

/** Las rutas de un documento (`carpeta/archivo.md`, relativas a la raíz de telar) se vuelven un enlace
 *  que abre el archivo. Recibe texto ya escapado. */
function conRutas(html: string): string {
    return html.replace(/(^|[\s(:])((?:[\w.-]+\/)+[\w.-]+\.(?:md|json|html))(?=$|[\s).,;])/g,
        (_, antes: string, ruta: string) => `${antes}<a data-accion="abrir-ruta" data-valor="${ruta}" title="abrir ${ruta}">${ruta}</a>`);
}

/** El campo para escribirle al agente general sobre la reunión elegida (⌘⏎ envía). */
function htmlEscribir(e: EventoCal, general: string): string {
    if (!general) return '';
    return `<div class="cal-escribir"><textarea id="ev-texto" data-evento="${esc(e.id)}" rows="3" spellcheck="false"`
        + ` placeholder="Escríbele a ${esc(general)} sobre esta reunión. Le llega con la reunión, su proyecto y las notas (⌘⏎ envía)"></textarea>`
        + `<a id="ev-enviar" data-accion="ev-escribir" data-campo="ev-texto" data-valor="${esc(e.id)}">enviar a ${esc(general)}</a></div>`;
}

function htmlDetalle(e: EventoCal, notas: cli.JsonNotas | undefined, fecha: string): string {
    const hm = (ms: number) => new Date(ms).toTimeString().slice(0, 5);
    const h: string[] = [`<h3>${esc(e.titulo)}</h3>`,
        `<div class="cal-meta">${esc(hm(e.inicio))}–${esc(hm(e.fin))}${e.lugar ? ` · ${esc(e.lugar)}` : ''}${e.soloPlan ? ' · bloque del plan' : ''}</div>`];
    const acciones: string[] = [];
    if (e.url) acciones.push(`<a class="enlace" data-url="${esc(e.url)}" title="${esc(e.url)}">entrar ↗</a>`);
    if (!e.soloPlan) acciones.push(`<a data-accion="reunion" data-valor="${esc(JSON.stringify([e.titulo, hm(e.inicio), e.url, e.id, e.asistentes]))}">preparar o minuta</a>`);
    acciones.push(`<a data-accion="nota-evento" data-valor="${esc(JSON.stringify([e.id, e.titulo, hm(e.inicio), fecha]))}">+ nota</a>`);
    h.push(`<div class="acciones-ev">${acciones.join('')}</div>`);
    const p = e.plan;
    if (p) {
        const f: Plan = p.ficha ?? {};
        const lista = (xs: unknown) => Array.isArray(xs) && xs.length ? '<ul>' + xs.map(x => `<li>${t(x)}</li>`).join('') + '</ul>' : '';
        const datos = [p.con?.length ? `con ${(p.con as string[]).join(', ')}` : '', p.estado ?? '', p.accion ? `propone: ${p.accion}` : '']
            .filter(Boolean).join(' · ');
        const partes = [
            datos ? `<div class="dim">${t(datos)}</div>` : '',
            p.nota ? `<div>${t(p.nota)}</div>` : '',
            f.decision ? `<div><b>decidir:</b> ${t(f.decision)}</div>` : '',
            (f.opciones ?? []).length ? lista((f.opciones as Plan[]).map(o => o.texto)) : '',
            f.recomendacion ? `<div><b>recomendación:</b> ${t(f.recomendacion)}</div>` : '',
            f.resultado ? `<div><b>resultado buscado:</b> ${t(f.resultado)}</div>` : '',
            (f.llevar ?? []).length ? `<div><b>llevar</b>${lista(f.llevar)}</div>` : '',
            (f.pedir ?? []).length ? `<div><b>pedir</b>${lista(f.pedir)}</div>` : '',
            f.riesgo ? `<div class="plan-riesgo">${t(f.riesgo)}</div>` : '',
            f.nota ? `<div class="dim">${t(f.nota)}</div>` : '',
            f.borrador ? `<div class="dim">borrador: ${t(f.borrador)}</div>` : '',
        ].filter(Boolean);
        if (partes.length) h.push(`<div class="cal-nota"><div class="de">del plan del día</div>${partes.join('')}</div>`);
    }
    for (const n of notasDe(e, notas)) {
        h.push(`<div class="cal-nota"><div class="de">${esc(n.de)} · ${esc((n.creado ?? '').slice(11, 16))}</div>`
            + `<div style="white-space:pre-wrap">${conRutas(t(n.texto))}</div></div>`);
    }
    if (!e.plan && !notasDe(e, notas).length) h.push('<div class="dim">sin notas</div>');
    return h.join('');
}
