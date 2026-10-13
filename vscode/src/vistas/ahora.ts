// La pantalla «ahora»: el bloque del día en que se está (o el próximo) y solo lo que conviene mirar en
// él. La decide el cruce del calendario con el plan del día: un bloque estratégico muestra el foco y su
// proyecto; una reunión, su ficha, la preparación, la minuta anterior y su proyecto. Lo que no se sabe
// mostrar no se muestra: el bloque y el foco, no una lista larga.

import * as cli from '../cli';
import { esc, normalizar } from '../estilo';
import { Pendiente, seccion } from './dia';
import { EventoCal, Plan } from './plan';
import { filaPendiente } from './proyectos';

export type Clase = 'reunion' | 'estrategico' | 'comercial' | 'correo' | 'reserva' | 'almuerzo' | 'cierre' | 'personal' | 'bloque';

const NOMBRE: Record<Clase, string> = {
    reunion: 'reunión', estrategico: 'estratégico', comercial: 'comercial', correo: 'correo y mensajes', reserva: 'reserva',
    almuerzo: 'almuerzo', cierre: 'cierre', personal: 'personal', bloque: 'bloque',
};

/** De qué clase es un bloque: lo que dice el plan (`clase`), o se deduce del tipo y del título
 *  («Estratégico: …», «Comercial: …», «Correo y mensajes», «Reserva»). Lo del calendario es reunión. */
export function claseDe(e: EventoCal): Clase {
    const p: Plan = e.plan ?? {};
    const dicha = String(p.clase ?? '').toLowerCase();
    if (['estrategico', 'comercial', 'correo', 'reserva', 'personal', 'cierre'].includes(dicha)) return dicha as Clase;
    if (!e.soloPlan && p.tipo !== 'bloque' && p.tipo !== 'almuerzo' && p.tipo !== 'cierre') return 'reunion';
    if (p.tipo === 'almuerzo') return 'almuerzo';
    if (p.tipo === 'cierre') return 'cierre';
    if (p.estrategico) return 'estrategico';
    const t = normalizar(e.titulo);
    if (t.startsWith('estrateg')) return 'estrategico';
    if (t.startsWith('comercial')) return 'comercial';
    if (t.startsWith('correo')) return 'correo';
    if (t.startsWith('reserva')) return 'reserva';
    if (t.startsWith('almuerzo')) return 'almuerzo';
    if (t.startsWith('cierre')) return 'cierre';
    return p.tipo === 'reunion' ? 'reunion' : 'bloque';
}

/** El bloque que toca: el que contiene la hora; si no hay, el próximo; si el día terminó, el último.
 *  Entre dos que se pisan, el que empezó más tarde (la reunión que corta un bloque propio). */
export function bloqueActual(evs: EventoCal[], ahora: number): number {
    const en = evs.map((e, i) => [e, i] as const).filter(([e]) => e.inicio <= ahora && ahora < e.fin);
    if (en.length) return en.sort((a, b) => b[0].inicio - a[0].inicio)[0][1];
    const proximo = evs.findIndex(e => e.inicio > ahora);
    return proximo >= 0 ? proximo : evs.length - 1;
}

/** El proyecto de un bloque propio sin `proyecto` en el plan: el que nombra su título por el cliente
 *  («Comercial: Acme 2.0» → el de Acme). Si dos calzan, ninguno. */
export function proyectoDelTitulo(titulo: string, proyectos: cli.JsonProyecto[]): string {
    const t = ` ${normalizar(titulo.replace(/^[^:]*:\s*/, ''))} `;
    const calzan = proyectos.filter(p => !/cerrad/i.test(p.arquetipo) && p.cliente && p.cliente.length >= 4
        && t.includes(` ${normalizar(p.cliente)} `));
    // con varios del mismo cliente, el que tiene hilo, y si no, el tocado más recientemente
    calzan.sort((a, b) => Number(!!b.hilo) - Number(!!a.hilo) || (b.modificado ?? '').localeCompare(a.modificado ?? ''));
    return calzan[0]?.ruta ?? '';
}

export interface Contexto {
    proyecto?: cli.JsonProyecto;
    /** el «## Estado» del README, ya en html; "" si no tiene */
    estado: string;
    pendientes: Pendiente[];
    /** las tareas que nombra el bloque (`tareas: [Tnn]`) */
    tareas: Pendiente[];
    preparacion?: { ruta: string; html: string };
    /** de la minuta anterior, lo que dejó «para la próxima preparación» */
    minuta?: { ruta: string; html: string };
    /** si el proyecto de una reunión no se pudo deducir */
    sinProyecto?: string;
}

function hm(ms: number): string { return new Date(ms).toTimeString().slice(0, 5); }

function cuando(e: EventoCal, ahora: number): string {
    if (e.inicio <= ahora && ahora < e.fin) return `en curso · quedan ${Math.round((e.fin - ahora) / 60000)} min`;
    if (e.inicio > ahora) {
        const min = Math.round((e.inicio - ahora) / 60000);
        return min < 60 ? `empieza en ${min} min` : `empieza en ${Math.floor(min / 60)} h ${min % 60} min`;
    }
    return 'ya pasó';
}

function lista(xs: unknown): string {
    return Array.isArray(xs) && xs.length ? '<ul>' + xs.map(x => `<li>${esc(String(x))}</li>`).join('') + '</ul>' : '';
}

function foco(plan: Plan | undefined, entero: boolean): string {
    const f: Plan = plan?.foco ?? {};
    if (!f.paso && !f.prioridad) return '';
    if (!entero) return `<div class="ahora-foco corto"><span class="dim">foco del día:</span> ${esc(String(f.paso ?? f.prioridad ?? ''))}</div>`;
    return '<div class="ahora-foco">'
        + (f.prioridad ? `<div class="dim">${esc(String(f.prioridad))}${f.bloque ? ` · ${esc(String(f.bloque))}` : ''}</div>` : '')
        + (f.paso ? `<div class="paso">${esc(String(f.paso))}</div>` : '')
        + (f.terminado ? `<div><b>terminado:</b> ${esc(String(f.terminado))}</div>` : '')
        + (f.pregunta ? `<div class="dim">${esc(String(f.pregunta))}</div>` : '')
        + '</div>';
}

function proyecto(c: Contexto | undefined, cargando: boolean): string {
    if (cargando) return '<div class="vacio">leyendo el proyecto…</div>';
    if (!c?.proyecto) return c?.sinProyecto ? `<div class="vacio">${esc(c.sinProyecto)}</div>` : '';
    const p = c.proyecto;
    const h = [`<h4>${esc(p.nombre)} <a data-accion="proy-ir" data-valor="${esc(p.ruta)}" class="dim">ver en proyectos</a></h4>`];
    if (c.estado) h.push(`<div class="ahora-estado proy-readme">${c.estado}</div>`);
    const MAX = 6;
    if (c.pendientes.length) {
        h.push(`<div class="dim">pendientes del proyecto · ${c.pendientes.length}</div>`, ...c.pendientes.slice(0, MAX).map(filaPendiente));
        if (c.pendientes.length > MAX) h.push(`<div class="dim">+ ${c.pendientes.length - MAX} más en <a data-accion="proy-ir" data-valor="${esc(p.ruta)}">proyectos</a></div>`);
    }
    return h.join('');
}

/** La pantalla entera: la barra para moverse entre bloques, y el bloque con lo suyo. */
export function htmlAhora(o: {
    evs: EventoCal[]; i: number; ahora: number; fijo: boolean; plan?: Plan; contexto?: Contexto; cargando: boolean;
    urgentes: Pendiente[]; propuestas: Pendiente[]; aviso: string;
    /** «ahora» corrido a otro momento para ver qué mostraría: no es el reloj */
    simulado?: boolean; cargandoDia?: boolean;
    /** el calendario desplegado para elegir el momento (html de la columna del día), y ese día */
    elegir?: string; fechaElegir?: string;
}): string[] {
    const h: string[] = [seccion('ahora', 'amarillo', '', '')];
    if (o.aviso) h.push(`<div class="vacio falla">${esc(o.aviso)}</div>`);
    // el momento que se mira: el reloj, o uno elegido en el calendario para ver qué mostraría entonces
    const dias = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
    const fecha = new Date(o.ahora);
    const momento = `<a class="ahora-cuando${o.simulado ? ' simulado' : ''}" data-accion="ahora-elegir" title="elegir en el calendario otro momento: qué mostraría entonces">`
        + `${o.simulado ? `simulando ${dias[fecha.getDay()]} ${fecha.getDate()} · ${hm(o.ahora)}` : 'elegir momento'} ${o.elegir !== undefined ? '▴' : '▾'}</a>`;
    // el calendario del día, desplegado bajo la barra: un clic en un bloque mueve «ahora» a ese momento
    const desplegable = o.elegir === undefined ? '' : '<div class="ahora-elegir">'
        + `<div class="cal-nav"><a data-accion="ahora-dia" data-valor="-1" title="día anterior">‹</a>`
        + `<span class="cal-fecha">${esc(o.fechaElegir ?? '')}</span><a data-accion="ahora-dia" data-valor="1" title="día siguiente">›</a></div>`
        + o.elegir + '</div>';
    const e = o.evs[o.i];
    if (o.cargandoDia) { h.push(`<div class="ahora-nav">${momento}</div>${desplegable}<div class="vacio">leyendo ese día…</div></section>`); return h; }
    if (!e) { h.push(`<div class="ahora-nav">${momento}${o.simulado ? '<a data-accion="ahora-soltar">↺ volver a ahora</a>' : ''}</div>${desplegable}<div class="vacio">nada en el calendario ni en el plan de ese día</div></section>`); return h; }
    const clase = claseDe(e);
    const p: Plan = e.plan ?? {};
    h.push('<div class="ahora-nav">'
        + `<a data-accion="ahora-mover" data-valor="-1" title="el bloque anterior">‹</a>`
        + `<span class="dim">${o.i + 1} de ${o.evs.length}</span>`
        + `<a data-accion="ahora-mover" data-valor="1" title="el bloque siguiente">›</a>`
        + (o.fijo || o.simulado ? '<a data-accion="ahora-soltar" title="volver a lo que toca ahora; la vista sigue al reloj">↺ volver a ahora</a>'
            : '<a data-accion="ahora-fijar" title="que la vista no cambie sola al pasar al bloque siguiente">fijar</a>')
        + momento + '</div>' + desplegable);
    h.push(`<div class="ahora-bloque"><span class="clase c-${clase}">${esc(NOMBRE[clase])}</span>`
        + `<h3>${esc(e.titulo)}</h3><div class="dim">${hm(e.inicio)}–${hm(e.fin)} · ${esc(cuando(e, o.ahora))}${e.lugar ? ` · ${esc(e.lugar)}` : ''}</div>`
        + (p.nota ? `<div>${esc(String(p.nota))}</div>` : '') + '</div>');

    const tareas = o.contexto?.tareas?.length ? `<h4>tareas del bloque</h4>${o.contexto.tareas.map(filaPendiente).join('')}` : '';
    if (clase === 'estrategico') {
        // lo estratégico: el foco y lo suyo, nada de lo táctico ni de otros proyectos
        h.push(foco(o.plan, true), tareas, proyecto(o.contexto, o.cargando));
    } else if (clase === 'reunion') {
        const f: Plan = p.ficha ?? {};
        const ficha = [
            f.decision ? `<div><b>decidir:</b> ${esc(String(f.decision))}</div>` : '',
            f.resultado ? `<div><b>resultado buscado:</b> ${esc(String(f.resultado))}</div>` : '',
            (f.llevar ?? []).length ? `<div><b>llevar</b>${lista(f.llevar)}</div>` : '',
            (f.pedir ?? []).length ? `<div><b>pedir</b>${lista(f.pedir)}</div>` : '',
            f.riesgo ? `<div class="dim"><b>riesgo:</b> ${esc(String(f.riesgo))}</div>` : '',
            f.nota ? `<div class="dim">${esc(String(f.nota))}</div>` : '',
        ].join('');
        const acciones = [
            e.url ? `<a class="enlace" data-url="${esc(e.url)}">entrar ↗</a>` : '',
            !e.soloPlan ? `<a data-accion="reunion" data-valor="${esc(JSON.stringify([e.titulo, hm(e.inicio), e.url, e.id, e.asistentes]))}">${e.fin <= o.ahora ? 'procesar la minuta' : 'preparar o minuta'}</a>` : '',
        ].filter(Boolean).join('');
        h.push(acciones ? `<div class="acciones-ev">${acciones}</div>` : '');
        if (ficha) h.push(`<div class="ahora-ficha">${ficha}</div>`);
        if (e.asistentes.length) h.push(`<div class="dim">con ${esc(e.asistentes.map(a => a.replace(/\s*<.*>/, '')).slice(0, 8).join(', '))}${e.asistentes.length > 8 ? '…' : ''}</div>`);
        if (o.contexto?.preparacion) h.push(`<h4>preparación <a data-accion="abrir-ruta" data-valor="${esc(o.contexto.preparacion.ruta)}" class="dim">abrir</a></h4><div class="proy-readme ahora-doc">${o.contexto.preparacion.html}</div>`);
        if (o.contexto?.minuta) h.push(`<h4>de la minuta anterior <a data-accion="abrir-ruta" data-valor="${esc(o.contexto.minuta.ruta)}" class="dim">abrir</a></h4><div class="proy-readme ahora-doc">${o.contexto.minuta.html}</div>`);
        h.push(tareas, proyecto(o.contexto, o.cargando), foco(o.plan, false));
    } else if (clase === 'comercial') {
        h.push(tareas, proyecto(o.contexto, o.cargando), foco(o.plan, false));
    } else if (clase === 'reserva' || clase === 'almuerzo') {
        // tiempo libre: casi nada, lo más urgente por si sobra
        h.push('<div class="vacio">tiempo libre: no hay nada agendado aquí.</div>');
        if (o.urgentes.length) h.push('<h4>si sobra, lo más urgente</h4>', ...o.urgentes.slice(0, 3).map(filaPendiente));
    } else if (clase === 'cierre') {
        const r: Plan = o.plan?.retrospectiva ?? {};
        const res = (o.plan?.resultados ?? []) as Plan[];
        if (res.length) h.push('<h4>los resultados del día</h4>' + res.map((x, k) => `<div>${esc(String(x.texto ?? ''))}`
            + `${r.resultados?.[k] ? ` <span class="dim">· ${esc(String(r.resultados[k]))}</span>` : ''}</div>`).join(''));
        if (o.propuestas.length) h.push(`<h4>lo que dejaron los agentes para decidir · ${o.propuestas.length}</h4>`, ...o.propuestas.slice(0, 6).map(filaPendiente));
    } else {
        h.push(tareas, proyecto(o.contexto, o.cargando), foco(o.plan, false));
    }
    h.push('</section>');
    return h;
}

/** Lo de una sección «Para la próxima preparación» (o «para la próxima») de una minuta, en markdown. */
export function paraLaProxima(md: string): string {
    const lineas = md.split('\n');
    const i = lineas.findIndex(l => /^#{2,4}\s+.*para la pr[oó]xima/i.test(l));
    if (i < 0) return '';
    const nivel = (lineas[i].match(/^#+/) ?? ['##'])[0].length;
    const fin = lineas.findIndex((l, k) => k > i && new RegExp(`^#{1,${nivel}}\\s`).test(l));
    return lineas.slice(i + 1, fin < 0 ? undefined : fin).join('\n').trim();
}

/** El «## Estado» de un README (no el «## Estado PMO»), en markdown; "" si no tiene. */
export function estadoDe(md: string): string {
    const lineas = md.split('\n');
    const i = lineas.findIndex(l => /^##\s+Estado\s*$/.test(l));
    if (i < 0) return '';
    const fin = lineas.findIndex((l, k) => k > i && /^##?\s/.test(l));
    return lineas.slice(i + 1, fin < 0 ? undefined : fin).join('\n').trim().slice(0, 1500);
}

export const CSS_AHORA = `
  .ahora-nav { display: flex; gap: 2ch; align-items: baseline; margin: .3lh 0 .6lh; }
  .ahora-nav a { color: var(--dim); }
  .ahora-cuando { margin-left: auto; } .ahora-nav a.ahora-cuando.simulado { color: var(--amarillo); }
  .ahora-elegir { border: 1px solid var(--linea); padding: .3lh 1ch .6lh; margin: 0 0 .8lh; max-width: 70ch; }
  .ahora-elegir .cal { margin-top: .5lh; } .ahora-nav a:hover { color: var(--fg); text-decoration: none; background: var(--hover); }
  .ahora-bloque { margin-bottom: .8lh; } .ahora-bloque h3 { margin: .1lh 0; }
  .ahora-bloque .clase { font-size: .85em; text-transform: uppercase; color: var(--dim); }
  .ahora-bloque .c-estrategico { color: var(--amarillo); } .ahora-bloque .c-reunion { color: var(--azul); }
  .ahora-bloque .c-comercial { color: var(--verde); }
  .ahora-foco { border-left: 2px solid var(--amarillo); padding: .2lh 1ch; margin: .5lh 0; }
  .ahora-foco .paso { font-size: 1.05em; margin: .2lh 0; } .ahora-foco.corto { border-left-color: var(--linea); }
  .ahora-ficha { border-left: 2px solid var(--azul); padding: .2lh 1ch; margin: .5lh 0; }
  .ahora-ficha ul { margin: 0; padding-left: 3ch; }
  #dia h4 { margin: 1lh 0 .3lh; font-size: 1em; text-transform: uppercase; color: var(--dim); font-weight: normal; }
  .ahora-doc { max-height: 22lh; overflow-y: auto; }
  .ahora-estado { border-top: none; }
`;

