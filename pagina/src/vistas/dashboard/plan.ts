// El calendario del dashboard: la agenda con las notas de cada evento (`telar evento`) y los bloques del plan del día
// que deja una skill de planificación (`telar resultado plan`; el plan como texto no tiene pestaña: lo usan táctica y
// «ahora»). Tiene dos vistas, el día y la semana (semana.ts), con el mismo dibujo: una cita va llena, un bloque propio
// rayado y del color de su clase (clases.ts).
// Arriba se dibuja; abajo, PantallaCalendario, el estado y las acciones de la pestaña, y el plan leído.

import * as cli from '../../cli';
import { esc } from '../../estilo';
import * as ui from '../../web/ui';
import { NOMBRE, cruces, queEs, vistos } from './clases';
import { Dia, cuerpo, diaDe, miNombre, seccion } from './dia';
import { type EventoCal, carriles, eventosDelDia, notasDe } from './eventos';
import type { Accion, EnBarra, Pantalla, Tablero } from './pantalla';
import type { AccionDePantalla, VistaDePantalla } from '../../componentes/pantalla';
import { type DiaSemana, corto, diasDe, htmlSemana, isoDe, lunesDe } from './semana';
import { I } from '../../web/iconos';

/** El plan, tal como lo escribe la skill: telar no fija su forma, se dibuja lo que trae. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Plan = Record<string, any>;

/** Alto de una hora en el calendario, en píxeles. */
const ALTO_HORA = 56;


function t(s: unknown): string {
    return esc(String(s ?? '')).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}

/** El calendario en dos columnas: a la izquierda el día con todos sus eventos, a la derecha el
 *  detalle y las notas del que se eligió. */
const DIAS_CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

/** Las dos vistas del calendario, como pestañas: el día y la semana (la tecla del calendario cambia de una a otra). */
/** Las vistas del calendario, en su barra: el día y la semana (a: cambiar). */
function vistasCal(vista: VistaCal): VistaDePantalla[] {
    return [
        { accion: 'cal-vista', valor: 'dia', icono: I.dia, nombre: 'el día', ayuda: 'a: cambiar', si: vista === 'dia' },
        { accion: 'cal-vista', valor: 'semana', icono: I.semana, nombre: 'la semana, de lunes a viernes', ayuda: 'a: cambiar', si: vista === 'semana' },
    ];
}

/** Un día como se lee: «mié 8 oct». */
export function diaLegible(fecha: string): string {
    const f = new Date(`${fecha}T12:00:00`);
    return isNaN(f.getTime()) ? fecha : `${DIAS_CORTOS[f.getDay()]} ${f.getDate()} ${MESES_CORTOS[f.getMonth()]}`;
}

/** La barra del calendario en el día: sus vistas y moverse (‹ ›, hoy). Qué día se mira lo dice el globo del título y,
 *  si no es hoy, la primera línea del día (htmlCalendario): la barra no lleva la fecha. */
export function barraDia(fecha: string, hoyIso: string): EnBarra {
    const acciones: AccionDePantalla[] = [
        { accion: 'cal-dia', valor: '-1', icono: I.atras, ayuda: 'el día anterior ([ o ←)' },
        { accion: 'cal-dia', valor: '1', icono: I.siguiente, ayuda: 'el día siguiente (] o →)' },
    ];
    if (fecha !== hoyIso) acciones.push({ accion: 'cal-dia', valor: 'hoy', icono: I.casa, ayuda: 'hoy' });
    return { vistas: vistasCal('dia'), ayuda: diaLegible(fecha), acciones };
}

/** La barra del calendario en la semana: sus vistas y moverse (‹ ›, esta semana). Qué semana es, en el globo del título
 *  (sus días ya van en la cabeza de cada columna). */
function barraSemana(lunes: string, estaSemana: string): EnBarra {
    const [ini, , , , fin] = diasDe(lunes);
    const mismoMes = ini.slice(5, 7) === fin.slice(5, 7);
    const acciones: AccionDePantalla[] = [
        { accion: 'cal-semana', valor: '-1', icono: I.atras, ayuda: 'la semana anterior ([)' },
        { accion: 'cal-semana', valor: '1', icono: I.siguiente, ayuda: 'la semana siguiente (])' },
    ];
    if (lunes !== estaSemana) acciones.push({ accion: 'cal-semana', valor: 'hoy', icono: I.casa, ayuda: 'esta semana' });
    return { vistas: vistasCal('semana'), ayuda: `semana ${numeroSemana(lunes)} · ${corto(ini, !mismoMes)} – ${corto(fin)}`, acciones };
}

export function htmlCalendario(d: Dia, evs: EventoCal[], notas: cli.JsonNotas | undefined, sel: string, ahora: Date, aviso: string,
    general = '', hoyIso = d.fecha, cargando = false): string[] {
    // el cuerpo del día; su id le dice a la página que ← y → cambian de día (dashboard/vista.ts)
    const h: string[] = ['<section class="bloque" id="cal-dia" style="--c: var(--azul)">'];
    // otro día que hoy: lo dice su primera línea (la barra no lleva la fecha); hoy no hace falta
    if (d.fecha !== hoyIso) h.push(`<div class="cal-dia-fecha">${esc(diaLegible(d.fecha))}</div>`);
    if (aviso) h.push(`<div class="vacio falla">${esc(aviso)}</div>`);
    if (d.error) h.push(`<div class="vacio falla">${esc(d.error)}</div>`);
    const completos = (d.agenda ?? []).filter(e => e.todo_el_dia);
    for (const e of completos) h.push(`<div class="cal-dia-completo">todo el día: ${esc(e.texto)}</div>`);
    if (!evs.length) {
        const nada = d.fecha === hoyIso ? 'nada con hora hoy' : 'nada con hora ese día';
        h.push(`<div class="vacio">${cargando ? 'cargando…' : d.agenda === null ? 'sin calendario consultado · <kbd>r</kbd>' : nada}</div></section>`);
        return h;
    }
    const elegido = evs.find(e => e.id === sel) ?? evs.find(e => e.fin > ahora.getTime()) ?? evs[0];
    h.push(`<div class="cal-dos"><div>${columnaCalendario(d, evs, elegido.id, ahora, notas)}</div><div class="cal-det">${htmlDetalle(elegido, notas, d.fecha)}${htmlEscribir(elegido, general)}</div></div></section>`);
    return h;
}

/** La columna del día: las horas, la línea de «ahora» y los eventos en su alto. Un clic en un evento
 *  manda `accion` con su id (el calendario lo muestra al lado; «ahora» mueve el reloj a ese momento). */
export function columnaCalendario(d: Dia, evs: EventoCal[], sel: string, ahora: Date, notas?: cli.JsonNotas,
    accion = 'evento-sel'): string {
    if (!evs.length) return '<div class="vacio">nada con hora ese día</div>';
    const base = new Date(`${d.fecha}T00:00:00`).getTime();
    const horaDe = (ms: number) => (ms - base) / 3600000;
    const desde = Math.min(8, Math.floor(Math.min(...evs.map(e => horaDe(e.inicio)))));
    const hasta = Math.max(19, Math.ceil(Math.max(...evs.map(e => horaDe(e.fin)))));
    const y = (ms: number) => (horaDe(ms) - desde) * ALTO_HORA;
    const lanes = carriles(evs.filter(e => e.fin - e.inicio >= 60000 && queEs(e).clase !== 'cierre'));
    const pis = new Map([...cruces(vistos(evs))].map(([id, xs]) => [id, xs.map(x => x.titulo)]));
    const elegido = evs.find(e => e.id === sel);
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
        const q = queEs(e);
        // lo que no dura (el cierre del día) es una raya, no un recuadro
        if (e.fin - e.inicio < 60000 || q.clase === 'cierre') {
            col.push(`<div class="sem-raya" data-accion="${accion}" data-valor="${esc(e.id)}" style="top:${y(e.inicio)}px" title="${esc(`${hm} · ${e.titulo}`)}"><span>${esc(NOMBRE[q.clase])} ${esc(hm)}</span></div>`);
            continue;
        }
        const pisa = pis.get(e.id) ?? [];
        const clases = ['cal-ev', `t-${q.tipo}`, `c-${q.clase}`, q.pendiente ? 'pendiente' : '', q.rechazada ? 'rechazada' : '', e.fin <= t0 ? 'pasado' : '', e === elegido ? 'sel' : '',
            alto < 40 ? 'corto' : '', pisa.length ? 'pisado' : ''].filter(Boolean).join(' ');
        const que = `${q.tipo === 'cita' ? 'cita' : NOMBRE[q.clase]}${q.pendiente ? ', sin aceptar' : ''}${q.rechazada ? ', rechazada: no cuenta' : ''}${q.organiza ? ', la organizas tú: la puedes mover' : ''}`;
        col.push(`<div class="${clases}" data-accion="${accion}" data-valor="${esc(e.id)}" title="${esc(`${que}\n${e.titulo}${pisa.length ? `\nse cruza con: ${pisa.join(', ')}` : ''}`)}"`
            + ` style="top:${y(e.inicio)}px;height:${alto}px;left:calc(${(100 * k) / n}% + 2px);width:calc(${100 / n}% - 4px)">`
            + `<span class="h">${esc(hm)}${tieneNotas ? ` <span class="marca-nota">${I.editar}</span>` : ''}</span><span class="t">${q.organiza ? `${I.persona} ` : ''}${esc(e.titulo)}</span></div>`);
    }
    col.push('</div>');
    return col.join('');
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
    if (e.url) acciones.push(`<a class="enlace" data-url="${esc(e.url)}" title="${esc(e.url)}">entrar ${I.externo}</a>`);
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

/** Las dos vistas del calendario. */
type VistaCal = 'dia' | 'semana';
/** Dónde se recuerda la vista elegida, en este navegador. */
const LLAVE_VISTA = 'telar.calendario.vista';
/** Cuánto vale un plan leído de otro día de la semana antes de volver a pedirlo, en milisegundos. */
const PLAN_VALE = 5 * 60000;

function vistaGuardada(): VistaCal {
    try { return localStorage.getItem(LLAVE_VISTA) === 'semana' ? 'semana' : 'dia'; } catch { return 'dia'; }
}

/** El número de la semana (ISO 8601) del lunes `iso`. */
function numeroSemana(iso: string): number {
    const f = new Date(`${iso}T12:00:00`);
    f.setDate(f.getDate() + 3 - ((f.getDay() + 6) % 7));
    const enero = new Date(f.getFullYear(), 0, 4);
    return 1 + Math.round(((f.getTime() - enero.getTime()) / 86400000 - 3 + ((enero.getDay() + 6) % 7)) / 7);
}

/** La pestaña del calendario: el plan leído (lo usan también táctica y «ahora»), las notas de los eventos, el día al
 *  que se navegó y la semana que se mira. */
export class PantallaCalendario implements Pantalla {
    readonly pantallas = ['calendario'] as const;
    readonly conReloj = ['calendario'] as const;
    /** el último plan de un día que se leyó (`telar resultado plan`) */
    plan?: cli.JsonResultado;
    /** las notas de los eventos del día del calendario, y el evento elegido */
    private notas?: cli.JsonNotas;
    private notasAviso = '';
    private eventoSel = '';
    /** el día que muestra el calendario si no es hoy (AAAA-MM-DD), con sus datos y si están cargando */
    private calFecha = '';
    private calDatos?: Dia;
    private calCargando = false;
    /** la vista del calendario: el día o la semana; la recuerda el navegador */
    private vista: VistaCal = vistaGuardada();
    /** la semana que se mira (su lunes), lo leído de cada día, si está cargando, y el evento elegido («día|id») */
    private semLunes = '';
    private semana?: { lunes: string; dias: DiaSemana[] };
    private semCargando = false;
    private semSel = '';
    /** el que se muestra al lado (el elegido o, si no se eligió ninguno, lo que viene): a él va lo que se escribe */
    private semMostrado = '';
    /** los planes de otros días que se leyeron para la semana (null: ese día no tiene), y cuándo */
    private readonly planes = new Map<string, { plan: Plan | null; hora: number }>();

    readonly acciones: Record<string, Accion> = {
        'calendario': () => this.abrirCalendario(),
        'cal-vista': v => (v === 'dia' || v === 'semana') && this.cambiarVista(v),
        'cal-semana': v => v && this.moverSemana(v),
        'cal-ver-dia': v => { if (v) { this.guardarVista('dia'); this.eventoSel = ''; return this.abrirDia(v); } },
        'sem-evento': v => { if (v) { this.semSel = v === this.semSel ? '' : v; this.pintarCalendario(); } },
        'sem-cerrar': () => { this.semSel = ''; this.pintarCalendario(); },
        'evento-sel': v => { if (v) { this.eventoSel = v; this.pintarCalendario(); } },
        'cal-dia': v => v && this.moverDiaCal(v),
        'nota-evento': v => v && this.notaEvento(v),
        'ev-escribir': (v, m) => v && this.escribirSobreEvento(v, m.datos ?? ''),
    };

    constructor(private readonly t: Tablero) {}

    pintar(): void {
        this.pintarCalendario();
    }

    /** El plan de un día, si es el que está leído o uno que leyó la semana, y viene en JSON (el que entiende el
     *  calendario). */
    planDe(fecha: string): Plan | undefined {
        if (this.plan?.dia === fecha) return this.plan.formato === 'json' ? this.plan.contenido as Plan : undefined;
        return this.planes.get(fecha)?.plan ?? undefined;
    }

    /** El día que muestra el calendario: hoy, u otro al que se navegó (`calFecha`). */
    private diaCal(): Dia | undefined {
        const hoy = this.t.dia();
        return this.calFecha && this.calFecha !== hoy?.fecha ? this.calDatos : hoy;
    }

    /** El calendario en la vista que se eligió la última vez: el día de hoy o esta semana. */
    async abrirCalendario(): Promise<void> {
        if (this.vista === 'semana') return this.abrirSemana('');
        return this.abrirDia('');
    }

    private guardarVista(v: VistaCal): void {
        this.vista = v;
        try { localStorage.setItem(LLAVE_VISTA, v); } catch { /* sin almacén: solo esta vez */ }
    }

    /** De una vista a la otra, sin perder dónde se estaba: la semana del día que se veía, o el día que se veía si
     *  es de esa semana (si no, su lunes; o hoy, si es la semana de hoy). */
    private async cambiarVista(v: VistaCal): Promise<void> {
        if (v === this.vista) return;
        this.guardarVista(v);
        const hoy = this.t.dia()?.fecha ?? '';
        if (v === 'semana') return this.abrirSemana(lunesDe(this.calFecha || hoy));
        const dias = diasDe(this.semLunes || lunesDe(hoy));
        const [fecha] = this.semSel.split('|');
        this.eventoSel = this.semSel.slice(fecha.length + 1);
        return this.abrirDia(dias.includes(hoy) && !fecha ? hoy : fecha || (dias.includes(hoy) ? hoy : dias[0]));
    }

    /** El calendario de un día (vacío es hoy): los eventos, los bloques del plan y las notas de cada uno. */
    async abrirDia(fecha = ''): Promise<void> {
        this.t.montar();
        this.t.ir('calendario');
        const hoy = await this.t.diaLeido();
        const hoyIso = hoy.fecha;
        this.calFecha = fecha === hoyIso ? '' : fecha;
        const iso = this.calFecha || hoyIso;
        this.calCargando = !!this.calFecha && this.calDatos?.fecha !== iso;
        if (this.calCargando) { this.calDatos = { ...hoy, fecha: iso, agenda: [], pendientes: [], error: undefined }; this.notas = undefined; }
        this.pintarCalendario();
        const [otro, plan, notas] = await Promise.all([
            this.calFecha ? diaDe(iso) : Promise.resolve(hoy),
            this.plan?.dia === iso ? Promise.resolve({ datos: this.plan }) : cli.resultado('plan', this.calFecha ? iso : ''),
            cli.notasEventos(this.calFecha ? iso : ''),
        ]);
        if ((this.calFecha || hoyIso) !== iso) return;  // se cambió de día mientras esto cargaba
        if (this.calFecha) this.calDatos = otro;
        this.calCargando = false;
        if (plan.datos?.ok) this.plan = plan.datos;
        this.notas = notas.datos?.ok ? notas.datos : undefined;
        this.notasAviso = notas.datos?.aviso ?? (notas.datos?.ok ? '' : (notas.datos?.error ?? notas.error ?? ''));
        if (this.t.pantalla === 'calendario') this.pintarCalendario();
    }

    /** ‹ › y «hoy» del calendario: `valor` es «hoy» o cuántos días moverse. */
    private async moverDiaCal(valor: string): Promise<void> {
        const hoyIso = this.t.dia()?.fecha;
        if (!hoyIso) return;
        if (valor === 'hoy') { this.eventoSel = ''; return this.abrirDia(''); }
        const f = new Date(`${this.calFecha || hoyIso}T12:00:00`);
        f.setDate(f.getDate() + (Number(valor) || 0));
        this.eventoSel = '';
        await this.abrirDia(isoDe(f));
    }

    /** El plan de un día de la semana: el que ya está leído, uno leído hace poco, o se pide a la máquina donde vive. */
    private async leerPlan(fecha: string): Promise<Plan | undefined> {
        if (this.plan?.dia === fecha) return this.planDe(fecha);
        const guardado = this.planes.get(fecha);
        if (guardado && Date.now() - guardado.hora < PLAN_VALE) return guardado.plan ?? undefined;
        const r = await cli.resultado('plan', fecha);
        const ok = r.datos?.ok && r.datos.dia === fecha && r.datos.formato === 'json' && r.datos.contenido;
        const plan = ok ? r.datos!.contenido as Plan : null;
        // si no contestó, no se recuerda que no hay: se vuelve a pedir la próxima vez
        if (r.datos?.ok) this.planes.set(fecha, { plan, hora: Date.now() });
        return plan ?? undefined;
    }

    /** La semana que empieza ese lunes (vacío es esta, o la que viene si hoy es sábado o domingo): de cada día, la
     *  agenda, el plan y las notas. Se dibuja al tiro con lo que haya, y otra vez cuando llega todo. */
    async abrirSemana(lunes: string): Promise<void> {
        this.t.montar();
        this.t.ir('calendario');
        const hoy = await this.t.diaLeido();
        const pedido = lunes || lunesDe(hoy.fecha);
        if (pedido !== this.semLunes) this.semSel = '';
        this.semLunes = pedido;
        this.semCargando = this.semana?.lunes !== pedido;
        this.pintarCalendario();
        const dias = await Promise.all(diasDe(pedido).map(async (fecha): Promise<DiaSemana> => {
            const [dia, plan, notas] = await Promise.all([
                fecha === hoy.fecha && hoy.agenda !== null ? Promise.resolve(hoy) : diaDe(fecha),
                this.leerPlan(fecha),
                cli.notasEventos(fecha),
            ]);
            return { fecha, dia, plan, notas: notas.datos?.ok ? notas.datos : undefined, evs: eventosDelDia(dia, plan) };
        }));
        if (this.semLunes !== pedido) return;  // se cambió de semana mientras esto cargaba
        this.semana = { lunes: pedido, dias };
        this.semCargando = false;
        if (this.t.pantalla === 'calendario' && this.vista === 'semana') this.pintarCalendario();
    }

    /** ‹ › y «esta semana»: `valor` es «hoy» o cuántas semanas moverse. */
    private async moverSemana(valor: string): Promise<void> {
        const hoy = this.t.dia()?.fecha;
        if (!hoy) return;
        if (valor === 'hoy') return this.abrirSemana('');
        return this.abrirSemana(diasDe(this.semLunes || lunesDe(hoy), Number(valor) || 0)[0]);
    }

    /** Un evento de la semana por su valor («día|id»), con su día. */
    private eventoSemana(valor: string): { d: DiaSemana; e: EventoCal } | undefined {
        const [fecha] = valor.split('|');
        const id = valor.slice(fecha.length + 1);
        const d = this.semana?.dias.find(x => x.fecha === fecha);
        const e = d?.evs.find(x => x.id === id);
        return d && e ? { d, e } : undefined;
    }

    private pintarSemana(): void {
        const hoy = this.t.dia()?.fecha ?? '';
        const lunes = this.semLunes || lunesDe(hoy);
        const dias: DiaSemana[] = this.semana?.lunes === lunes ? this.semana.dias : diasDe(lunes).map(fecha => ({ fecha, evs: [] }));
        this.t.teclas.clear();
        this.t.teclas.set('[', () => this.moverSemana('-1'));
        this.t.teclas.set(']', () => this.moverSemana('1'));
        this.t.teclas.set('a', () => this.cambiarVista('dia'));
        // el detalle, solo del que se eligió: la semana se ve entera hasta que se pincha algo
        const ahora = new Date();
        const elegido = this.eventoSemana(this.semSel);
        this.semMostrado = elegido ? this.semSel : '';
        const general = this.t.general()?.nombre ?? '';
        const detalle = elegido ? htmlDetalle(elegido.e, elegido.d.notas, elegido.d.fecha) + htmlEscribir(elegido.e, general) : '';
        const fallas = [...new Set(dias.map(d => d.dia?.error ?? '').filter(Boolean))];
        this.t.pintar([cuerpo('azul'),
            ...fallas.map(f => `<div class="vacio falla">${esc(f)}</div>`),
            this.semCargando && !this.semana ? '<div class="vacio">leyendo la semana…</div>' : '',
            htmlSemana(dias, { hoy, ahora, sel: this.semMostrado, detalle }),
            '</section>'], barraSemana(lunes, lunesDe(hoy)));
    }

    private pintarCalendario(): void {
        if (this.vista === 'semana') { this.pintarSemana(); return; }
        const d = this.diaCal();
        if (!d) return;
        this.t.teclas.clear();
        this.t.teclas.set('[', () => this.moverDiaCal('-1'));
        this.t.teclas.set(']', () => this.moverDiaCal('1'));
        this.t.teclas.set('a', () => this.cambiarVista('semana'));
        const plan = this.planDe(d.fecha);
        this.t.pintar(htmlCalendario(d, eventosDelDia(d, plan), this.notas, this.eventoSel, new Date(), this.notasAviso,
            this.t.general()?.nombre ?? '', this.t.dia()?.fecha ?? d.fecha, this.calCargando),
            barraDia(d.fecha, this.t.dia()?.fecha ?? d.fecha));
    }

    /** Lo que la persona le escribe al agente general sobre una reunión, con todo el contexto que el
     *  agente necesita para no preguntar: la reunión, su proyecto, lo que dicen el plan y las notas. */
    private async escribirSobreEvento(id: string, texto: string): Promise<void> {
        // en la semana, el evento es el que se muestra al lado (los bloques del plan se llaman igual todos los días)
        const deSemana = this.vista === 'semana' ? this.eventoSemana(this.semMostrado) : undefined;
        const d = deSemana?.d.dia ?? this.diaCal();
        const general = this.t.general();
        if (!texto.trim() || !d) return;
        if (!general) { void ui.aviso('telar: no hay un agente que reciba lo sin proyecto ([agentes] sin_proyecto)'); return; }
        const plan = this.planDe(d.fecha);
        const e = deSemana?.e.id === id ? deSemana.e : eventosDelDia(d, plan).find(x => x.id === id);
        const notasDelDia = deSemana ? deSemana.d.notas : this.notas;
        if (!e) return;
        const hm = (ms: number) => new Date(ms).toTimeString().slice(0, 5);
        // de qué proyecto es: lo que telar recuerda para la serie o lo que deduce (sin hacer nada)
        let proyecto = '';
        if (!e.soloPlan) {
            const r = await cli.reunion(e.titulo, hm(e.inicio), e.url, e.id, { asistentes: e.asistentes, preguntar: true, donde: true });
            if (r.datos?.destino && r.datos.destino !== 'gestion') proyecto = `Proyecto: ${r.datos.destino}${r.datos.recordado ? ` (elegido por ${miNombre()} para esta serie)` : ' (deducido)'}.`;
            else if (r.datos?.candidatos?.length) proyecto = `Proyecto: no está claro; candidatos: ${r.datos.candidatos.slice(0, 3).map(c => `${c.ruta} (${c.motivos.join(', ')})`).join('; ')}.`;
            else proyecto = 'Proyecto: ninguno deducido.';
        }
        const notas = notasDe(e, notasDelDia).map(n => `${n.de}: ${n.texto}`);
        const lineas = [
            `[${miNombre()}, desde el calendario del dashboard] ${texto.trim()}`,
            '',
            `Contexto. La reunión: «${e.titulo}», ${d.fecha} de ${hm(e.inicio)} a ${hm(e.fin)}${e.lugar ? `, ${e.lugar}` : ''}${e.soloPlan ? ' (bloque del plan del día, no está en el calendario)' : ''}.`,
            e.asistentes.length ? `Asistentes: ${e.asistentes.join(', ')}.` : '',
            proyecto,
            e.plan?.nota ? `El plan del día dice: ${e.plan.nota}` : '',
            e.plan?.ficha?.decision ? `Decisión que pide el plan: ${e.plan.ficha.decision}` : '',
            notas.length ? `Notas del evento: ${notas.join(' | ')}` : '',
            `Id del evento: ${e.id}. Si lo que hagas es de esta reunión, déjale una nota: telar evento nota "${e.id}" "…" --de ${general.clave} --titulo "${e.titulo}" --inicio ${hm(e.inicio)} --dia ${d.fecha}`,
        ].filter(Boolean);
        const r = await ui.progreso({ titulo: `telar: escribiéndole a ${general.nombre}…` },
            () => cli.encargar(general.clave, lineas.join('\n')));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        // queda constancia en el evento: lo que se pidió y a quién
        await cli.notaEvento(e.id, `A ${general.nombre}: ${texto.trim()}`, e.titulo, hm(e.inicio), d.fecha, miNombre());
        await this.releerNotas(d.fecha);
        if (!deSemana) this.eventoSel = id;
        void ui.estado(`telar: enviado a ${general.nombre} (${r.datos.estado ?? ''})`, 6000);
        if (this.t.pantalla === 'calendario') this.pintarCalendario();
    }

    /** Una nota de la persona sobre un evento: se guarda donde viven las notas (`telar evento nota`). */
    private async notaEvento(valor: string): Promise<void> {
        const [id, titulo, inicio, fecha] = JSON.parse(valor) as string[];
        const texto = await ui.campo({ titulo: `Nota para «${titulo}»`, ayuda: 'Se guarda junto al evento y la ven las skills' });
        if (!texto?.trim()) return;
        const r = await cli.notaEvento(id, texto.trim(), titulo, inicio, fecha, miNombre());
        if (!r.datos?.ok) { void ui.falla(`telar: la nota no se guardó: ${r.datos?.error ?? r.error ?? 'sin respuesta'}`); return; }
        if (this.vista === 'semana') this.semSel = `${fecha}|${id}`;
        else this.eventoSel = id;
        await this.releerNotas(fecha);
        if (this.t.pantalla === 'calendario') this.pintarCalendario();
    }

    /** Las notas de los eventos de un día, otra vez: las del día que se ve y las de ese día en la semana. */
    private async releerNotas(fecha: string): Promise<void> {
        const n = await cli.notasEventos(fecha);
        if (!n.datos?.ok) return;
        if ((this.calFecha || this.t.dia()?.fecha) === fecha) this.notas = n.datos;
        const d = this.semana?.dias.find(x => x.fecha === fecha);
        if (d) d.notas = n.datos;
    }
}
