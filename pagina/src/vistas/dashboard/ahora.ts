// La pantalla «ahora»: el bloque del día en que se está (o el próximo) y solo lo que conviene mirar en
// él. La decide el cruce del calendario con el plan del día: un bloque estratégico muestra el foco y su
// proyecto; una reunión, su ficha, la preparación, la minuta anterior y su proyecto. Lo que no se sabe
// mostrar no se muestra: el bloque y el foco, no una lista larga.
// Arriba se dibuja; abajo, PantallaAhora, el estado y las acciones.

import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { disco } from '../../disco';
import { esc, normalizar } from '../../estilo';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, Pendiente, diaDe, pendientes, seccion } from './dia';
import { NOMBRE, claseDe } from './clases';
import { type EventoCal, eventosDelDia } from './eventos';
import { type Plan, columnaCalendario } from './plan';
import { esServicio, filaPendiente } from './proyectos';
import type { Accion, Pantalla, Tablero } from './pantalla';
import { prepararReunion } from './reuniones';

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

/** La pantalla «ahora»: el bloque que se mira (el que toca, o uno elegido o simulado) y el contexto de cada uno. */
export class PantallaAhora implements Pantalla {
    readonly pantallas = ['ahora'] as const;
    readonly conReloj = ['ahora'] as const;
    /** «ahora»: el bloque que se mira si no es el que toca (al moverse o fijar), y el contexto de cada uno */
    private sel = '';
    private fijo = false;
    private readonly contextos = new Map<string, Contexto>();
    private cargando = '';
    /** «ahora» corrido a otro momento (ms), para ver qué mostraría; y el día y el plan de ese momento */
    private sim?: number;
    private diaSim?: Dia;
    private planSim?: Record<string, unknown>;
    private diaSimCargando = false;
    /** el calendario desplegado en «ahora» para elegir el momento */
    private elegir = false;

    readonly acciones: Record<string, Accion> = {
        'ahora': () => this.abrir(),
        // «← volver al dashboard», ⎋ en el buscador de proyectos: a «ahora»
        'dia': () => this.abrir(),
        'ahora-mover': v => this.mover(Number(v) || 0),
        'ahora-fijar': () => { this.fijo = true; this.sel = this.evento()?.id ?? ''; this.pintar(); },
        'ahora-soltar': () => {
            this.fijo = false; this.sel = ''; this.sim = undefined; this.diaSim = undefined; this.planSim = undefined; this.elegir = false;
            this.pintar();
        },
        'ahora-elegir': () => { this.elegir = !this.elegir; this.pintar(); },
        'ahora-evento': v => v && this.alEvento(v),
        'ahora-dia': v => v && this.otroDia(Number(v) || 0),
        // preparar una reunión: desde aquí y desde el calendario
        'reunion': v => {
            const [titulo, hora, enlace, evento, asistentes] = JSON.parse(v || '[]') as [string, string, string?, string?, string[]?];
            if (titulo && hora) return prepararReunion(titulo, hora, enlace ?? '', evento ?? '', asistentes ?? []);
        },
    };

    constructor(private readonly t: Tablero) {}

    /** La pantalla «ahora»: el bloque que toca y lo que conviene mirar en él (ver `ahora.ts`). */
    async abrir(): Promise<void> {
        this.t.montar();
        this.t.ir('ahora');
        const d = await this.t.diaLeido();
        this.pintar();
        // lo que hace falta para el contexto: el plan de hoy, los proyectos y sus pendientes
        const [plan] = await Promise.all([
            this.t.planes.plan?.dia === d.fecha ? Promise.resolve(undefined) : cli.resultado('plan', ''),
            this.t.proyectos.asegurar(),
            this.t.proyectos.asegurarPendientes(),
        ]);
        if (plan?.datos?.ok) this.t.planes.plan = plan.datos;
        this.contextos.clear();
        if (this.t.pantalla === 'ahora') this.pintar();
    }

    /** El día que se mira: hoy, o el del momento simulado (con su calendario y su plan). */
    private elDia(): { d?: Dia; plan?: Record<string, unknown> } {
        if (this.sim !== undefined && this.diaSim) return { d: this.diaSim, plan: this.planSim };
        const d = this.t.dia();
        return { d, plan: d && this.t.planes.planDe(d.fecha) };
    }

    private eventos(): EventoCal[] {
        const { d, plan } = this.elDia();
        return d ? eventosDelDia(d, plan) : [];
    }

    /** El índice del bloque que se mira en `evs`: el elegido, o el que toca a esa hora. Sobre la misma
     *  lista que se dibuja: `eventosDelDia` arma objetos nuevos cada vez, y buscar uno de una lista en
     *  otra no lo encuentra nunca (la vista quedaba en «nada en el calendario»). */
    private indice(evs: EventoCal[]): number {
        const i = this.sel ? evs.findIndex(e => e.id === this.sel) : -1;
        return i >= 0 ? i : bloqueActual(evs, this.sim ?? Date.now());
    }

    private evento(): EventoCal | undefined {
        const evs = this.eventos();
        return evs[this.indice(evs)];
    }

    /** Un bloque elegido en el calendario desplegado: «ahora» pasa a su comienzo y se lo mira a él. */
    private alEvento(id: string): void {
        const e = this.eventos().find(x => x.id === id);
        if (!e) return;
        this.sim = e.inicio + 60000;
        this.sel = e.id;
        this.elegir = false;
        this.pintar();
    }

    /** ‹ › del calendario desplegado: otro día, a la misma hora (con su calendario y su plan). */
    private async otroDia(paso: number): Promise<void> {
        const base = new Date(this.sim ?? Date.now());
        base.setDate(base.getDate() + paso);
        const local = new Date(base.getTime() - base.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        await this.simular(local);
    }

    /** Mover «ahora» a otro momento (`AAAA-MM-DDTHH:MM`): qué mostraría entonces. Otro día trae su
     *  calendario y su plan; el mismo día de hoy usa lo que ya hay. */
    private async simular(valor: string): Promise<void> {
        const ms = Date.parse(valor);
        if (Number.isNaN(ms)) return;
        this.sim = ms;
        this.sel = '';
        this.fijo = false;
        const fecha = valor.slice(0, 10);
        if (fecha === this.t.dia()?.fecha) { this.diaSim = undefined; this.planSim = undefined; this.pintar(); return; }
        this.diaSimCargando = true;
        this.pintar();
        const [d, plan] = await Promise.all([diaDe(fecha), cli.resultado('plan', fecha)]);
        if (this.sim !== ms) return;  // se eligió otro momento mientras tanto
        this.diaSim = d;
        this.planSim = plan.datos?.ok && plan.datos.formato === 'json' ? plan.datos.contenido as Record<string, unknown> : undefined;
        this.diaSimCargando = false;
        if (this.t.pantalla === 'ahora') this.pintar();
    }

    /** ‹ ›: moverse a otro bloque deja la vista fija ahí hasta «volver a ahora». */
    private mover(paso: number): void {
        const evs = this.eventos();
        const actual = this.evento();
        const i = Math.max(0, Math.min(evs.length - 1, evs.findIndex(e => e.id === actual?.id) + paso));
        this.sel = evs[i]?.id ?? '';
        this.fijo = true;
        this.pintar();
    }

    pintar(): void {
        const d = this.t.dia();
        if (!this.t.panel || !d) return;
        this.t.teclas.clear();
        this.t.teclas.set('[', () => this.mover(-1));
        this.t.teclas.set(']', () => this.mover(1));
        // lo elegido se mantiene si está fijo o si se está simulando otro momento; si no, manda el reloj
        if (!this.fijo && this.sim === undefined) this.sel = '';
        const evs = this.eventos();
        const i = evs.length ? this.indice(evs) : -1;
        const e = i >= 0 ? evs[i] : undefined;
        const { d: diaVisto, plan } = this.elDia();
        const momento = new Date(this.sim ?? Date.now());
        const ctx = e ? this.contextos.get(e.id) : undefined;
        if (e && !ctx && this.cargando !== e.id) void this.cargarContexto(e, plan);
        const todas = pendientes(d);
        this.t.pintar(htmlAhora({
            evs, i, ahora: this.sim ?? Date.now(), fijo: this.fijo, plan, contexto: ctx, cargando: !!e && !ctx,
            simulado: this.sim !== undefined, cargandoDia: this.diaSimCargando,
            elegir: this.elegir && diaVisto ? columnaCalendario(diaVisto, evs, e?.id ?? '', momento, undefined, 'ahora-evento') : undefined,
            fechaElegir: diaVisto?.fecha,
            urgentes: todas.filter(t => t.dias !== null && t.dias <= 0 || !!t.fila.destacada),
            propuestas: todas.filter(t => t.avance && t.fila.ficha),
            aviso: plan ? '' : 'sin plan para ese día: se ve el calendario',
        }));
    }

    /** Lo que se muestra de un bloque: su proyecto (el que dice el plan; el de la reunión, como lo
     *  deduce `telar reunion`; o el que nombra el título), su Estado y pendientes, las tareas que nombra,
     *  y en una reunión la última preparación y lo que la minuta anterior dejó para la próxima. */
    private async cargarContexto(e: EventoCal, plan?: Record<string, unknown>): Promise<void> {
        this.cargando = e.id;
        const clase = claseDe(e);
        const p = (e.plan ?? {}) as Record<string, any>;
        const ctx: Contexto = { estado: '', pendientes: [], tareas: [] };
        try {
            let ruta = String(p.proyecto ?? '');
            if (!ruta && clase === 'reunion' && !e.soloPlan) {
                const hm = new Date(e.inicio).toTimeString().slice(0, 5);
                const r = await cli.reunion(e.titulo, hm, e.url, e.id, { asistentes: e.asistentes, preguntar: true, donde: true });
                if (r.datos?.destino && r.datos.destino !== 'gestion') ruta = r.datos.destino;
                else ctx.sinProyecto = r.datos?.candidatos?.length
                    ? `no sé de qué proyecto es: quizás ${r.datos.candidatos.slice(0, 3).map(c => c.nombre).join(', ')}`
                    : 'no sé de qué proyecto es esta reunión';
            }
            const lista = this.t.proyectos.lista;
            if (!ruta && clase !== 'reunion' && lista) ruta = proyectoDelTitulo(e.titulo, lista.filter(p => !esServicio(p)));
            ctx.proyecto = this.t.proyectos.lista?.find(x => x.ruta === ruta);
            const ids = new Set(((p.tareas ?? []) as string[]).map(String));
            const hoy = this.t.dia();
            if (ids.size && hoy) {
                ctx.tareas = pendientes({ ...hoy, pendientes: hoy.pendientes.filter(f => ids.has(f.id)) } as Dia);
            }
            if (ctx.proyecto && modelo.raiz) {
                const carpeta = rutas.unir(modelo.raiz, ctx.proyecto.ruta);
                ctx.pendientes = this.t.proyectos.pendientesDe(ctx.proyecto.ruta) ?? [];
                const readme = await disco().leer(rutas.unir(carpeta, 'README.md'));
                const est = readme !== undefined ? estadoDe(readme) : '';
                if (est) ctx.estado = await this.markdown(est);
                if (clase === 'reunion') {
                    const prep = await this.masReciente(carpeta, n => /preparaci[oó]n/i.test(n), e.titulo);
                    const textoPrep = prep ? await disco().leer(prep) : undefined;
                    if (prep && textoPrep !== undefined) ctx.preparacion = { ruta: rutas.relativa(modelo.raiz, prep), html: await this.markdown(textoPrep.slice(0, 12000)) };
                    const leidas = new Map<string, string>();
                    const minuta = await this.masReciente(carpeta, (n, r) => /minuta/i.test(n) || (/\/reuniones\//.test(r) && !/preparaci/i.test(n)), e.titulo,
                        async f => { const t = await disco().leer(f) ?? ''; leidas.set(f, t); return !!paraLaProxima(t); });
                    if (minuta) ctx.minuta = { ruta: rutas.relativa(modelo.raiz, minuta), html: await this.markdown(paraLaProxima(leidas.get(minuta) ?? '')) };
                }
            }
        } catch { /* sin contexto: el bloque y el foco igual se ven */ }
        this.contextos.set(e.id, ctx);
        this.cargando = '';
        if (this.t.pantalla === 'ahora') this.pintar();
    }

    private async markdown(texto: string): Promise<string> {
        try { return await ui.markdown(texto) ?? ''; } catch { return esc(texto); }
    }

    /** El .md más reciente de una carpeta (hasta tres niveles) que cumple `elegir`, prefiriendo los que
     *  comparten alguna palabra con el título de la reunión (su serie) sobre los demás. */
    private async masReciente(carpeta: string, elegir: (nombre: string, ruta: string) => boolean, titulo: string,
        ademas: (ruta: string) => Promise<boolean> = async () => true): Promise<string> {
        const hallados = (await disco().buscarMd(carpeta, 3)).filter(h => elegir(rutas.nombre(h.ruta), h.ruta));
        const palabras = normalizar(titulo).split(/\s+/).filter(w => w.length > 3);
        const deLaSerie = (r: string) => palabras.some(w => normalizar(rutas.nombre(r)).includes(w));
        hallados.sort((a, b) => Number(deLaSerie(b.ruta)) - Number(deLaSerie(a.ruta)) || b.mtime - a.mtime);
        for (const h of hallados) if (await ademas(h.ruta)) return h.ruta;
        return '';
    }
}
