// La pantalla de proyectos: a la izquierda todas las unidades del perfil, con búsqueda; a la derecha,
// la elegida: sus pendientes (las viñetas de su documento y las tareas que dicen ser suyas) y su
// README. Como el calendario, dos columnas; la derecha se cambia sola (un mensaje `parcial`), sin
// repintar la lista, que es larga y no debe perder ni el scroll ni lo buscado.
// Arriba se dibuja; abajo, PantallaProyectos, el estado y las acciones.

import * as ui from '../../web/ui';
import type { Opcion } from '../../web/ui';
import * as cli from '../../cli';
import { disco } from '../../disco';
import { esc, haceCorto, limpiarMd, normalizar } from '../../estilo';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, Pendiente, olvidarDia, pendientes, plazo, yo } from './dia';
import { type Accion, type Pantalla, type Tablero, abrirEnlace } from './pantalla';
import { elegirDueno, llevarPendiente } from './tareas';


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

/** Una fila de botones que filtra la lista por un campo (`data-pf`); la página marca el activo. */
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

/** La lista de la izquierda. Buscar, ordenar y mostrar los cerrados ocurre en la página
 *  (`aplicarProyectos`, vista.ts); elegir una fila pide su detalle. */
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

/** La pestaña de proyectos: la lista, el elegido y su detalle, y las viñetas pendientes de los documentos. Las
 *  otras pantallas le preguntan de qué proyecto es algo y qué tiene pendiente («ahora», la columna de «tareas»). */
export class PantallaProyectos implements Pantalla {
    readonly pantallas = ['proyectos'] as const;
    /** la lista no cambia con el reloj: repintarla cada minuto solo movería el scroll */
    readonly conReloj = [] as const;
    /** todas las unidades del perfil (`telar proyectos`), y el aviso si no llegaron */
    lista?: cli.JsonProyecto[];
    private aviso = '';
    /** el proyecto elegido en la lista, y lo que se muestra de él a la derecha */
    private sel = '';
    private det?: DetalleProyecto;
    /** las viñetas pendientes de todos los documentos: se leen una vez por entrada a la pantalla */
    private pendRepo?: cli.JsonFila[];
    private pendRepoAviso = '';
    /** las personas que ofrece el proveedor de tareas como responsables (ver `personasConocidas`) */
    private personas?: string[];

    readonly acciones: Record<string, Accion> = {
        'proyectos': () => this.abrir(),
        'proyecto': v => v && this.abrirProyecto(v),
        'proy-sel': v => v && this.ver(v),
        'proy-ir': v => { if (v) { this.sel = v; return this.abrir(); } },
        'proy-menu': v => v && this.menu(v),
        'proy-consolidar': v => v && this.consolidar(v),
        'proy-enlace': (v, m) => v && this.enlaceReadme(v, String(m.datos ?? '')),
        'menu-vineta': v => v && this.menuVineta(v),
    };

    constructor(private readonly t: Tablero) {}

    /** La lista, si todavía no se leyó: true si se leyó ahora (quien la pidió repinta). */
    async asegurar(): Promise<boolean> {
        if (this.lista) return false;
        const r = await cli.proyectos();
        if (r.datos) this.lista = r.datos.proyectos;
        return !!r.datos;
    }

    /** Las viñetas pendientes de los documentos, si todavía no se leyeron. */
    async asegurarPendientes(): Promise<void> {
        if (this.pendRepo) return;
        const r = await cli.pendientesRepo();
        if (r.datos) this.pendRepo = r.datos.pendientes;
    }

    /** La pantalla de proyectos. La lista se pide cada vez que se entra: es barata (medio
     *  segundo con 179 unidades) y así un proyecto recién creado aparece sin recargar. */
    async abrir(): Promise<void> {
        this.t.ir('proyectos');
        this.aviso = '';
        this.pendRepo = undefined;
        if (!this.lista) this.pintar('leyendo los proyectos…');
        // los pendientes de los documentos se piden en paralelo: la lista no los espera
        const repo = cli.pendientesRepo().then(r => {
            this.pendRepo = r.datos?.pendientes ?? [];
            this.pendRepoAviso = r.datos ? '' : (r.error ?? 'telar pendientes no contestó');
            if (this.t.pantalla !== 'proyectos') return;
            // la lista ya está pintada: solo se le dan las cuentas, para filtrar «con pendientes»
            const cuentas = this.cuentasPendientes();
            if (cuentas) this.t.panel?.cuentasProyectos(Object.fromEntries(cuentas));
            if (this.sel) void this.ver(this.sel, false);
        });
        const r = await cli.proyectos();
        if (r.datos) this.lista = r.datos.proyectos;
        else this.aviso = r.error ?? 'telar proyectos no contestó';
        if (this.sel && !this.lista?.some(p => p.ruta === this.sel)) { this.sel = ''; this.det = undefined; }
        if (this.t.pantalla === 'proyectos') this.pintar();
        if (this.sel) void this.ver(this.sel);
        await repo;
    }

    /** Los pendientes de un proyecto: las viñetas de su documento y las tareas de un proveedor que
     *  dicen ser de esa carpeta (o de algo adentro). null mientras se leen los del documento. */
    pendientesDe(ruta: string): ReturnType<typeof pendientes> | null {
        const filas = this.filasPorProyecto()?.get(ruta);
        if (!filas) return this.pendRepo ? [] : null;
        return pendientes({ ...(this.t.dia() ?? { fecha: '' }), pendientes: filas } as Dia);
    }

    /** Las filas pendientes de cada proyecto: las viñetas de su documento, y cada tarea de un
     *  proveedor en el proyecto más hondo que contiene la carpeta que dice ser suya. */
    private filasPorProyecto(): Map<string, cli.JsonFila[]> | null {
        if (!this.pendRepo) return null;
        const rutas = (this.lista ?? []).map(p => p.ruta);
        const m = new Map<string, cli.JsonFila[]>();
        const sumar = (r: string, f: cli.JsonFila) => { if (r) m.set(r, [...(m.get(r) ?? []), f]); };
        for (const f of this.pendRepo) if (!f.proveedor && !f.hecho) sumar(f.ruta, f);
        for (const f of this.t.dia()?.pendientes ?? []) {
            if (f.proveedor && f.clase !== 'evento' && !f.hecho && !f.pestana && f.proyecto) sumar(unidadDe(f.proyecto, rutas), f);
        }
        return m;
    }

    private cuentasPendientes(): Map<string, number> | undefined {
        const m = this.filasPorProyecto();
        return m ? new Map([...m].map(([r, fs]) => [r, fs.length])) : undefined;
    }

    /** Elegir un proyecto de la lista: su detalle a la derecha, sin repintar la lista. El README se
     *  dibuja con el Markdown de la página (web/ui.ts); `releer` vuelve a leerlo (al cambiar de proyecto). */
    private async ver(ruta: string, releer = true): Promise<void> {
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!p || !this.t.panel) return;
        this.sel = ruta;
        const previo = this.det?.p.ruta === ruta ? this.det.readme : null;
        this.det = { p, pendientes: this.pendientesDe(ruta), aviso: this.pendRepoAviso, readme: releer ? null : previo };
        this.pintarDetalle();
        if (!releer && previo !== null) return;
        const readme = await this.readmeHtml(ruta);
        if (this.sel !== ruta || !this.det) return;
        this.det.readme = readme;
        this.pintarDetalle();
    }

    private pintarDetalle(): void {
        this.t.parcial('proy-det', htmlDetalleProyecto(this.det));
    }

    /** El README de una unidad como html, sin su encabezado YAML. "" si no tiene. */
    private async readmeHtml(ruta: string): Promise<string> {
        if (!modelo.raiz || ruta.includes('..')) return '';
        let crudo: string | undefined;
        for (const n of ['README.md', 'readme.md']) { crudo = await disco().leer(rutas.unir(modelo.raiz, ruta, n)); if (crudo !== undefined) break; }
        if (crudo === undefined) return '';
        try {
            let texto = crudo.slice(0, 300_000);
            texto = texto.replace(/^---\n[\s\S]*?\n---\n/, '');
            return await ui.markdown(texto) ?? '';
        } catch (e) {
            return `<p class="falla">no pude leer el README: ${esc(String(e))}</p>`;
        }
    }

    /** Las personas para elegir como responsable: las que ofrece el proveedor de tareas (se pide la
     *  ficha de una tarea cualquiera, una vez) y todos los que ya son responsables de algo. */
    private async personasConocidas(): Promise<string[]> {
        if (!this.personas) {
            const unaTarea = this.t.dia()?.pendientes.find(f => f.ficha && f.proveedor);
            const ficha = unaTarea ? await cli.tarea(unaTarea.id || unaTarea.ref, unaTarea.proveedor) : undefined;
            this.personas = ficha?.datos?.acciones?.find(a => a.rol === 'dueno')?.opciones ?? [];
        }
        const vistos = [...(this.t.dia()?.pendientes ?? []), ...(this.pendRepo ?? [])].map(f => f.dueno ?? '').filter(Boolean);
        return [...new Set([...this.personas, ...vistos])].sort((a, b) => a.localeCompare(b));
    }

    /** El ⋯ de una casilla de un documento (un README): llevarla a su hilo, abrirla donde está,
     *  marcarla hecha o decir quién la hace. Lo que cambia el documento cambia esa línea y nada más. */
    private async menuVineta(valor: string): Promise<void> {
        const [ref, texto, hilo, dueno] = JSON.parse(valor) as string[];
        type Item = Opcion & { hacer: () => Promise<unknown> };
        const despues = async (r: { datos?: cli.JsonVineta; error?: string }) => {
            if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no pude cambiarla'}`); return; }
            void ui.estado(`telar: ${r.datos.relativa}:${r.datos.linea} · ${r.datos.hecho} (sin commitear)`, 6000);
            olvidarDia();
            this.pendRepo = undefined;
            await this.t.actualizar(true);
            if (this.t.pantalla === 'revisar') this.t.render();
            else if (this.t.pantalla === 'proyectos') await this.abrir();
        };
        const items: Item[] = [
            { label: hilo ? `Llevarla a «${hilo}»` : 'Llevarla a un hilo', description: 'escrita y sin enviar', hacer: () => llevarPendiente(ref, false) },
            { label: 'Un hilo nuevo para ella', hacer: () => llevarPendiente(ref, true) },
            { label: 'Abrir el README en esa línea', hacer: async () => {
                const r = await cli.vineta(ref, texto, ['--linea']);
                if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no la encontré'}`); return; }
                await ui.abrirArchivo(r.datos.archivo);
            } },
            { label: 'Marcar hecha', description: '[ ] → [x] en el README', hacer: async () => {
                const si = await ui.aviso(`¿Marcar hecha? ${texto.slice(0, 90)}`, 'Marcar hecha');
                if (si === 'Marcar hecha') await despues(await cli.vineta(ref, texto, ['--hecho']));
            } },
            { label: 'Responsable…', description: dueno ? `ahora: ${dueno}` : 'ahora: sin responsable', hacer: async () => {
                const quien = await elegirDueno(texto.slice(0, 80), dueno, await this.personasConocidas(), yo.persona, true);
                if (quien) await despues(await cli.vineta(ref, texto, ['--responsable', quien]));
            } },
        ];
        const e = await ui.elegir(items, { titulo: texto.slice(0, 100), placeholder: 'qué hacer con este pendiente' });
        if (e) await e.hacer();
    }

    /** De qué proyecto es un pendiente: la carpeta que dice la tarea, o la del documento de donde salió,
     *  llevada a la unidad más honda que la contiene. */
    deFila(f: cli.JsonFila): cli.JsonProyecto | undefined {
        const carpeta = f.proyecto || f.ruta;
        if (!carpeta || !this.lista) return undefined;
        const ruta = unidadDe(carpeta, this.lista.map(p => p.ruta));
        return this.lista.find(p => p.ruta === ruta);
    }

    /** Pedirle al agente general que consolide los pendientes del README de un proyecto (`/consolidar`):
     *  que marque hecho, con su prueba, lo que ya se hizo. Corre donde vive el agente (el servidor). */
    async consolidar(ruta: string): Promise<void> {
        const general = this.t.general();
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!general) { void ui.aviso('telar: no hay un agente general ([agentes] sin_proyecto) que lo haga'); return; }
        const n = this.pendientesDe(ruta)?.filter(t => !t.fila.proveedor).length;
        const si = await ui.info(
            `¿Consolidar los pendientes de «${p?.nombre ?? ruta}»?`,
            { detalle: `${general.nombre} revisa ${n ?? 'cada'} pendiente${n === 1 ? '' : 's'} abierto${n === 1 ? '' : 's'} del README, busca si ya se hizo y marca lo hecho con su prueba. Lo dudoso te lo pregunta.` },
            'Consolidar');
        if (si !== 'Consolidar') return;
        const r = await ui.progreso({ titulo: `telar: encargándoselo a ${general.nombre}…` },
            () => cli.encargar(general.clave, `/consolidar ${ruta}`));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: ${general.nombre} consolida ${p?.nombre ?? ruta} (${r.datos.estado ?? ''})`, 8000);
    }

    /** El ⋯ de un proyecto: lo que se puede hacer con él sin abrirlo. */
    private async menu(ruta: string): Promise<void> {
        const general = this.t.general();
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!p) return;
        const carpeta = modelo.raiz ? rutas.unir(modelo.raiz, ruta) : '';
        type Item = Opcion & { hacer: () => Promise<unknown> | unknown };
        const items: Item[] = [
            { label: p.vivo ? 'Ir a su hilo' : p.hilo ? 'Retomar su hilo' : 'Abrir con el agente',
              description: p.hilo ? `«${p.hilo}»` : 'un hilo nuevo cargando el proyecto', hacer: () => this.abrirProyecto(ruta) },
        ];
        if (general) {
            items.push({ label: 'Consolidar sus pendientes', description: `${general.nombre} marca lo hecho con su prueba (/consolidar)`,
                         hacer: () => this.consolidar(ruta) });
            items.push({ label: `Escribirle a ${general.nombre} sobre este proyecto…`, description: 'le llega con el proyecto y lo pendiente',
                         hacer: () => this.escribirSobre(p) });
        }
        if (carpeta) {
            items.push(
                { label: 'Abrir el README', description: `${ruta}/README.md`, hacer: () => abrirEnlace(rutas.unir(carpeta, 'README.md')) },
                { label: 'Mostrar la carpeta en el explorador', hacer: () => ui.mostrarCarpeta(carpeta) },
            );
        }
        items.push({ label: 'Copiar la ruta', description: ruta, hacer: async () => {
            await ui.copiar(ruta);
            void ui.estado(`telar: copiado ${ruta}`, 3000);
        } });
        if (p.hilo) {
            items.push({ label: 'Archivar su hilo', description: `cierra «${p.hilo}» y lo guarda; ▶ lo retoma`, hacer: async () => {
                const si = await ui.aviso(`¿Archivar «${p.hilo}»? Se cierra su ventana; su conversación queda para retomarla.`, 'Archivar');
                if (si !== 'Archivar') return;
                const r = await cli.hilo('archivar', p.hilo, undefined, ['--cerrar']);
                if (!r.ok) void ui.falla(`telar: ${r.err.trim() || 'no pude archivarlo'}`);
                await this.abrir();
            } });
        }
        const elegida = await ui.elegir(items, { titulo: p.nombre, placeholder: 'qué hacer con este proyecto' });
        if (elegida) await elegida.hacer();
    }

    /** Lo que la persona le escribe al agente general sobre un proyecto, con lo que necesita para no
     *  preguntar: cuál es, dónde está, en qué estado, y lo pendiente. */
    async escribirSobre(p: cli.JsonProyecto): Promise<void> {
        const general = this.t.general();
        if (!general) return;
        const texto = await ui.campo({ titulo: `A ${general.nombre} · ${p.nombre}`, ayuda: 'qué hacer con este proyecto' });
        if (!texto?.trim()) return;
        const pend = this.pendientesDe(p.ruta) ?? [];
        const lineas = [
            `[Nico, desde los proyectos del dashboard] ${texto.trim()}`,
            '',
            `Contexto. El proyecto: «${p.nombre}» (${p.arquetipo}${p.estado_completo ? `, estado: ${p.estado_completo}` : ''}), en ${p.ruta}; su README es ${p.ruta}/README.md.`,
            p.hilo ? `Tiene un hilo: «${p.hilo}»${p.vivo ? ' (abierto)' : ' (dormido)'}; si el trabajo es suyo, pásaselo con telar mensaje.` : 'No tiene hilo abierto.',
            pend.length ? `Pendiente: ${pend.slice(0, 12).map(t => `${t.fila.proveedor ? `${t.ref} ` : ''}${t.texto}`).join(' | ')}` : '',
        ].filter(Boolean);
        const r = await ui.progreso({ titulo: `telar: escribiéndole a ${general.nombre}…` },
            () => cli.encargar(general.clave, lineas.join('\n')));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: enviado a ${general.nombre} (${r.datos.estado ?? ''})`, 6000);
    }

    /** Un enlace del README: una ruta relativa se abre como archivo; una dirección, en el navegador. */
    private async enlaceReadme(href: string, base: string): Promise<void> {
        if (/^[a-z][a-z0-9+.-]*:/i.test(href)) { await ui.abrirExterno(href); return; }
        if (!modelo.raiz || href.startsWith('#')) return;
        const destino = rutas.unir(modelo.raiz, base, decodeURIComponent(href.split('#')[0]));
        if (!destino.startsWith(modelo.raiz)) return;
        await abrirEnlace(destino);
    }

    /** Todas las filas van a la página de una vez; buscar y ordenar ocurre allá, sin ir y
     *  volver por cada letra. Ver `aplicarProyectos` en vista.ts. */
    pintar(cargando = ''): void {
        if (!this.t.panel) return;
        this.t.teclas.clear();
        // sin los servicios: no son proyectos (sí se usan para decir de qué es una tarea)
        const lista = (this.lista ?? []).filter(p => !esServicio(p));
        const h: string[] = [`<div class="subcab"><b>Proyectos</b><span class="dim">${lista.length || ''}</span>`
            + '</div>'];
        if (this.aviso) h.push(`<div class="fila falla">${esc(this.aviso)}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.t.pintar(h); return; }
        h.push('<div class="proy-dos"><div class="proy-lista">', ...htmlListaProyectos(lista, this.sel, this.cuentasPendientes()),
            `</div><div id="proy-det">${htmlDetalleProyecto(this.sel ? this.det : undefined)}</div></div>`);
        this.t.pintar(h);
    }

    /** Un hilo con el agente cargando el proyecto, o el que ya había; y el teclado ahí. Lo
     *  que se le dice al agente lo decide `[agente] proyecto`, no la página. */
    async abrirProyecto(ruta: string): Promise<void> {
        const r = await cli.abrirProyecto(ruta);
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir el proyecto'}`);
            return;
        }
        await modelo.sondear();
        await ui.mostrarTerminal();
    }
}
