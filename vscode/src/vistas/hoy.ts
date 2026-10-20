// El dashboard: el día entero en un panel del área central (por dentro, `telar hoy`).
//
// Tiene tres pantallas. La del día; la de proyectos, que son todas las unidades del perfil
// —tengan hilo o no—, buscables y ordenables, y un clic abre un hilo con el agente
// cargándola; y la de configuración, que dice de dónde sale cada cosa —hoy, la agenda—, si
// está funcionando, y deja elegir otra fuente sin editar archivos.
//
// Tres cosas y en este orden, el mismo de `telar hoy` en la terminal: lo que ya tiene hora,
// quién te espera, y lo que está por hacer. Nada más. Lo que saldría de un proveedor que no
// está declarado no aparece porque no existe, y eso se dice en vez de dejar un hueco.

import * as ui from '../web/ui';
import type { Opcion } from '../web/ui';
import * as cli from '../cli';
import { disco } from '../disco';
import { GLIFO, NOMBRE_ATENCION, esc, hace, haceCorto, hhmm, limpiarMd, llaveAlAzar, normalizar } from '../estilo';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import { Dia, atajo, datosDueno, leidoProveedores, dia, diaDe, filtroAreas, filtroDuenos, olvidarDia, pendientes, pista, plazo, seccion, yo } from './dia';
import { columnaCalendario, eventosDelDia, htmlCalendario, htmlPlan, notasDe } from './plan';
import { DetalleProyecto, esServicio, htmlDetalleProyecto, htmlListaProyectos, unidadDe } from './proyectos';
import { Contexto, bloqueActual, claseDe, estadoDe, htmlAhora, paraLaProxima, proyectoDelTitulo } from './ahora';
import type { EventoCal } from './plan';
import { type MensajeDia, montarDia, type VistaDia } from './dashboard';
import { decidir, preguntarAGestion } from './equipo';
import { alternarEquipo, alternarEstrella, asignar, elegirDueno, elegirFecha, llevarPendiente, marcarHecha, reagendar } from './tareas';

export class PanelHoy {
    /** el dashboard en la página, ya montado (vistas/dashboard.ts); hasta abrirlo, nada */
    panel?: VistaDia;
    /** dónde se dibuja (un elemento de la página) y cómo se lo trae al frente: los da la página (src/navegador) */
    donde?: () => HTMLElement;
    mostrarme?: () => void;
    private datos?: Dia;
    private pantalla: 'ahora' | 'bloque' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'correo' | 'equipo' | 'tarea' | 'revisar' | 'pestana' | 'periodicos' | 'plan' | 'calendario' = 'ahora';
    /** el bloque (`[bloques.x]`) que muestra la pestaña 'bloque' */
    private bloqueSel = '';
    /** las pestañas: en qué orden van y cuáles no se muestran (`[dashboard]`, se cambia en ⚙) */
    private dashOrden: string[] = [];
    private dashOcultas: string[] = [];
    private modulosCfg: NonNullable<Awaited<ReturnType<typeof cli.config>>['datos']>['modulos'] = [];
    /** el detalle de los ítems abiertos (el cuerpo de un correo), por «<bloque>:<id>»; y cuáles se ven enteros */
    private cuerpos = new Map<string, { texto?: string; error?: string }>();
    private cuerposAbiertos = new Set<string>();
    /** los bloques donde se ven solo los ítems con alguna tarea pendiente */
    private soloPendientes = new Set<string>();
    /** las conversaciones desplegadas en los bloques («correo:<grupo>») */
    private gruposAbiertos = new Set<string>();
    /** el ítem del bloque que se está mirando (un correo y sus tareas), si alguno */
    private itemSel?: number;
    /** el bloque y la hora de lo leído que la pestaña pintó la última vez (ver `renderBloque`) */
    private bloquePintado = '';
    /** el plan del día que se está mirando (`telar resultado plan`), y el error si no llegó */
    private plan?: cli.JsonResultado;
    private planError = '';
    private planCargando = false;
    /** las notas de los eventos de hoy, y el evento elegido en el calendario */
    private notas?: cli.JsonNotas;
    /** el agente que recibe lo que no tiene proyecto: a quién le escribe el calendario */
    private general?: { clave: string; nombre: string };
    private notasAviso = '';
    private eventoSel = '';
    /** la pestaña de los procesos periódicos: la lista leída y el abierto (con su log), si hay uno */
    private periodicos?: cli.JsonPeriodicos;
    private periodicosError = '';
    private periodico?: { nombre: string; log: string };
    /** el formulario de crear o editar un proceso: `original` es el nombre si se edita */
    private formPer?: { original: string; p: cli.JsonPeriodico; skills?: cli.JsonSkill[]; skillsDe?: string };
    /** de qué pestaña se abrió la ficha: ⎋ vuelve ahí, y ahí queda marcada. `pestana:<n>` es
     *  la de un proveedor con pestaña propia (un feed) */
    private fichaDesde = 'revisar';
    /** la pestaña de proveedor abierta (`pestana` del proveedor: «leer») */
    private pestana = '';
    /** fichas ya pedidas: una pestaña de proveedor puede estar lejos (el feed se pide por ssh
     *  a otro continente, ~0,5 s cada una), así que se piden antes de que se abran */
    private fichas = new Map<string, { pagina: cli.JsonPagina; hora: number }>();
    /** cuándo se lanzó cada atajo, para no encargar lo mismo dos veces sin querer */
    private atajosLanzados = new Map<string, number>();
    /** las pestañas de proveedor declaradas y su tecla (`telar config --json`) */
    private pestanasCfg: cli.JsonPestana[] = [];
    /** la ficha abierta: de qué proveedor, su id y su ref (con la que se lleva al hilo) */
    private ficha?: { proveedor: string; id: string; ref: string; pagina?: cli.JsonPagina; aviso?: string };
    /** las propuestas ya decididas en esta pasada: ← → las saltan aunque el día no se haya releído */
    private decididas = new Set<string>();
    /** los mensajes entre hilos por el bus (undefined: sin bus o sin leer) */
    private mensajesBus?: cli.JsonMensajeBus[];
    private abiertoMsg = new Set<string>();
    /** la entrada del equipo que muestra la pantalla «equipo» */
    private equipoId = '';
    /** la sección abierta y su página; la conversación que se está leyendo */
    private seccion = '';
    private pagina?: cli.JsonPagina;
    private charla?: cli.JsonConversacion;
    /** las memorias de los lienzos pintados: una llave al azar por lienzo → el archivo que declaró
     *  su página. El lienzo solo escribe ese archivo, y lo nombra con la llave, nunca con una ruta. */
    private memorias = new Map<string, string>();
    private proyectos?: cli.JsonProyecto[];
    private avisoProyectos = '';
    /** «ahora»: el bloque que se mira si no es el que toca (al moverse o fijar), y el contexto de cada uno */
    private ahoraSel = '';
    private ahoraFijo = false;
    private ahoraCtx = new Map<string, Contexto>();
    private ahoraCargando = '';
    /** «ahora» corrido a otro momento (ms), para ver qué mostraría; y el día y el plan de ese momento */
    private ahoraSim?: number;
    private ahoraDia?: Dia;
    private ahoraPlan?: Record<string, unknown>;
    private ahoraDiaCargando = false;
    /** el calendario desplegado en «ahora» para elegir el momento */
    private ahoraElegir = false;
    /** el proyecto elegido en la lista, y lo que se muestra de él a la derecha */
    private proySel = '';
    private proyDet?: DetalleProyecto;
    /** las viñetas pendientes de todos los documentos: se leen una vez por entrada a la pantalla */
    private pendRepo?: cli.JsonFila[];
    private pendRepoAviso = '';
    /** las teclas que declara `[atajos]`; se leen al abrir el panel y al volver de la configuración */
    private atajos: cli.JsonAtajo[] = [];
    /** los bloques del día declarados, y lo último que mostró cada uno */
    private bloquesCfg: cli.JsonBloque[] = [];
    private bloquesDatos = new Map<string, { pagina?: cli.JsonPagina; error: string; hora: number }>();
    private calendario?: cli.JsonCalendario;
    private agenteConfig?: cli.JsonAgenteConfig;
    private hilosConfig?: { directorios: string[]; tope: number };
    private avisoConfig = '';
    private enCurso = false;
    private teclas = new Map<string, () => Promise<unknown> | unknown>();
    /** el día que muestra el calendario si no es hoy (AAAA-MM-DD), con sus datos y si están cargando */
    private calFecha = '';
    private calDatos?: Dia;
    private calCargando = false;

    /** ⌥H: si el dashboard ya está al frente, devuelve el teclado al terminal. */
    /** Se le avisa cuando el dashboard gana o pierde el foco (la lista de hilos marca su fila). */
    alCambiarFoco?: (activo: boolean) => void;

    alternar(): void {
        if (this.panel?.visible) { void ui.mostrarTerminal(); return; }
        this.abrir();
    }

    abrir(): void {
        if (this.panel) { this.mostrarme?.(); void this.actualizar(); return; }
        if (!this.donde) throw new Error('telar: el dashboard no sabe dónde dibujarse (donde)');
        this.panel = montarDia(this.donde(), m => void this.mensaje(m));
        void this.leerAtajos();
        this.alCambiarFoco?.(true);
        void this.mensaje({ tipo: 'listo' });
    }

    /** La app que el panel muestra ahora, o "": la lista de la izquierda marca su fila. */
    get appActual(): string {
        return this.pantalla === 'seccion' && this.seccion.startsWith('app:') ? this.seccion.slice(4) : '';
    }

    /** Una app (`[apps.x]`): su página, en el panel. */
    async abrirApp(clave: string): Promise<void> {
        await this.abrirSeccion(`app:${clave}`);
        this.alCambiarFoco?.(true);
    }

    async actualizar(conRed = false): Promise<void> {
        if (!this.panel || this.enCurso) return;
        this.enCurso = true;
        try {
            if (conRed) olvidarDia();
            this.datos = await dia(conRed ? 0 : 45000, conRed);
            this.render();
            void this.leerBloques(conRed);
        } finally { this.enCurso = false; }
    }

    /** Redibuja con lo que hay: la marca «ahora» y los «hace» se mueven solos cada minuto. */
    render(): void {
        if (this.panel && this.pantalla === 'config') { this.renderConfig(); return; }
        if (this.panel && this.pantalla === 'revisar') { this.renderRevisar(); return; }
        if (this.panel && this.pantalla === 'pestana') { this.renderPestana(); return; }
        if (this.panel && this.pantalla === 'periodicos') { if (!this.formPer) this.renderPeriodicos(); return; }
        if (this.panel && this.pantalla === 'plan') { this.renderPlan(); return; }
        if (this.panel && this.pantalla === 'calendario') { this.renderCalendario(); return; }
        if (this.panel && this.pantalla === 'ahora') { this.renderAhora(); return; }
        // la lista de proyectos no cambia con el reloj: repintarla cada minuto solo movería el scroll
        if (this.panel && this.pantalla === 'proyectos') return;
        // lo mismo con la página de una sección y una conversación: no dependen del reloj
        if (this.panel && (this.pantalla === 'seccion' || this.pantalla === 'conversacion' || this.pantalla === 'correo' || this.pantalla === 'tarea')) return;
        if (this.panel && this.pantalla === 'equipo') { this.renderEquipo(); return; }
        if (this.panel && this.pantalla === 'bloque') this.renderBloque();
    }

    /** Un bloque (`[bloques.x]`) en su pestaña: lo que imprime su comando, con sus atajos. */
    private renderBloque(): void {
        this.teclas.clear();
        const b = this.bloquesCfg.find(x => x.clave === this.bloqueSel);
        const leido = b ? this.bloquesDatos.get(b.clave) : undefined;
        const item = this.itemSel !== undefined ? (leido?.pagina?.bloques ?? []).flatMap(x => x.items ?? [])[this.itemSel] : undefined;
        if (b && item) { this.bloquePintado = ''; this.pintar(this.htmlItem(b, item, this.itemSel!)); return; }
        // un bloque con lienzo no se repinta si no cambió: el refresco de cada minuto rehace el
        // iframe (el gráfico parpadea y pierde el mouse). Sin lienzo, sí, para que el reloj avance
        const firma = `${this.bloqueSel}:${leido?.hora ?? 0}`;
        if (leido?.pagina?.bloques.some(x => x.lienzo) && firma === this.bloquePintado) return;
        this.bloquePintado = firma;
        this.pintar(b ? this.bloques([b]) : ['<div class="vacio">ese bloque ya no está en la configuración</div>']);
    }

    /** Abre la pestaña de un bloque y lo relee si tiene más de 5 minutos. */
    private async abrirBloque(clave: string, item?: number): Promise<void> {
        this.pantalla = 'bloque';
        this.bloquePintado = '';
        this.itemSel = item;
        // un ítem abierto con `id`: su detalle (el cuerpo de un correo) se pide ahora, una vez
        const x = item === undefined ? undefined : (this.bloquesDatos.get(clave)?.pagina?.bloques ?? []).flatMap(b => b.items ?? [])[item];
        if (x?.id && !this.cuerpos.has(`${clave}:${x.id}`)) {
            const llave = `${clave}:${x.id}`;
            this.cuerpos.set(llave, {});
            void cli.bloqueItem(clave, x.id).then(r => {
                this.cuerpos.set(llave, r.datos ? { texto: r.datos.texto } : { error: r.error ?? 'no pude leerlo' });
                if (this.pantalla === 'bloque' && this.bloqueSel === clave && this.itemSel === item) this.render();
            });
        }
        this.bloqueSel = clave;
        this.render();
        await this.leerBloques();
    }

    /** Todas las pestañas que puede haber (sin ⚙), en su orden de siempre: las fijas, las de los
     *  bloques y las de los proveedores. Cada una: [clave, acción, valor, nombre, tecla]. */
    private todasLasPestanas(): Pestana[] {
        const d = this.datos;
        // las pestañas de los proveedores que las declaran (un feed), con cuántos ítems tienen
        const deProveedores = [...new Set((d?.pendientes ?? []).map(f => f.pestana ?? '').filter(Boolean))]
            .map(n => [`pestana:${n}`, 'pestana', n, `${n} ${d ? pendientes(d, n).length : ''}`.trim(),
                this.pestanasCfg.find(x => x.nombre === n)?.tecla ?? ''] as Pestana);
        const aRevisar = this.propuestas('').length;
        const todas: Pestana[] = [  // clave, acción, valor, nombre, tecla
            ['ahora', 'ahora', '', 'ahora', 'n'],
            ['revisar', 'revisar', '', aRevisar ? `tareas ◆${aRevisar}` : 'tareas', 'v'],
            // cada bloque sin `en` es su propia pestaña (el correo de hoy)
            ...this.bloquesCfg.filter(b => !b.en).map(b =>
                [`bloque:${b.clave}`, 'bloque', b.clave, b.nombre, b.tecla ?? ''] as Pestana),
            ...deProveedores,
            ['proyectos', 'proyectos', '', 'proyectos', 'p'],
            ['plan', 'plan', '', 'plan', 'd'],
            ['calendario', 'calendario', '', 'calendario', 'a'],
            ['periodicos', 'periodicos', '', 'periódicos', 'o'],
            ...(modelo.hayRemotos ? [['correo', 'correo', '', 'agentes', 'c'] as Pestana] : []),
            // las secciones (los agentes, babel) no: a su página se llega desde su fila en la lista de la izquierda
        ];
        return todas;
    }

    /** Las que se ven, en el orden elegido en ⚙ (`[dashboard] orden`); las que no se nombran van
     *  después, en su orden de siempre, así una pestaña nueva (un módulo) aparece sola. */
    private pestanasVisibles(todas = this.todasLasPestanas()): Pestana[] {
        const pos = (c: string) => { const i = this.dashOrden.indexOf(c); return i < 0 ? this.dashOrden.length + todas.findIndex(x => x[0] === c) : i; };
        return todas.filter(x => !this.dashOcultas.includes(x[0])).sort((a, b) => pos(a[0]) - pos(b[0]));
    }

    /** Mostrar u ocultar una pestaña, o moverla un lugar, y guardarlo (`telar config --pestanas`). */
    private async cambiarPestanas(accion: string, clave: string): Promise<void> {
        const todas = this.todasLasPestanas();
        const pos = (c: string) => { const i = this.dashOrden.indexOf(c); return i < 0 ? this.dashOrden.length + todas.findIndex(x => x[0] === c) : i; };
        const orden = todas.map(x => x[0]).sort((a, b) => pos(a) - pos(b));
        let ocultas = [...this.dashOcultas];
        const i = orden.indexOf(clave);
        if (i < 0) return;
        if (accion === 'ver') ocultas = ocultas.includes(clave) ? ocultas.filter(x => x !== clave) : [...ocultas, clave];
        else {
            const j = i + (accion === 'subir' ? -1 : 1);
            if (j < 0 || j >= orden.length) return;
            [orden[i], orden[j]] = [orden[j], orden[i]];
        }
        const r = await cli.configPestanas(orden.map(c => (ocultas.includes(c) ? '-' : '') + c).join(','));
        if (!r.datos) { this.avisoConfig = r.error ?? 'no pude guardar las pestañas'; this.renderConfig(); return; }
        this.dashOrden = r.datos.dashboard.orden;
        this.dashOcultas = r.datos.dashboard.ocultas;
        this.avisoConfig = '';
        this.renderConfig();
    }

    /** La barra de arriba, igual en todas las pestañas y fija al desplazarse: la marca, el
     *  reloj y las pestañas. Cambiar de pestaña es un clic; no hay que «volver» a ninguna parte. */
    private nav(): string {
        const d = this.datos;
        const ahora = new Date();
        const activa = this.pantalla === 'conversacion' ? `seccion:${this.seccion}`
            : this.pantalla === 'seccion' ? `seccion:${this.seccion}` : this.pantalla === 'tarea' ? this.fichaDesde.replace(/^(bloque:[^:]*):.*$/, '$1')
            : this.pantalla === 'pestana' ? `pestana:${this.pestana}`
            : this.pantalla === 'bloque' ? `bloque:${this.bloqueSel}` : this.pantalla;
        // los atajos que no son de ninguna pestaña (`en = "hoy"`) y el terminal: en la barra, en todas
        const generales = this.atajos.filter(a => (a.en ?? 'hoy') === 'hoy')
            .map(a => atajo(a.tecla, a.nombre, 'atajo', a.tecla, a.descripcion || a.mensaje)).join('')
            + atajo('⎋', 'terminal', 'volver', '', 'volver al terminal');
        // un proveedor caído se dice en todas las pestañas (el calendario, además, en la suya)
        const caidos = (d?.fallas ?? []).filter(f => !f.startsWith('calendario'));
        const pestanas = [...this.pestanasVisibles(), ['config', 'config', '', '⚙', ''] as Pestana];
        return '<div class="fijo"><header class="top"><div class="marca-t"><span class="logo">telar</span>'
            + (d ? `<span class="fecha">${esc(fechaLarga(d.nombreDia, d.fecha))}</span>` : '')
            + `<span class="reloj">${ahora.toTimeString().slice(0, 5)}</span>${d?.semana ? `<span class="sem">s${d.semana}</span>` : ''}</div>`
            + `<span class="generales">${generales}</span>`
            + atajo('r', 'recargar', 'refrescar', '', 'recargar, proveedores incluidos') + '</header>'
            + '<nav class="tabs">' + pestanas.map(([clave, accion, valor, nombre, tecla]) =>
                `<a class="tab${clave === activa ? ' activa' : ''}" data-accion="${accion}"${valor ? ` data-valor="${esc(valor)}"` : ''}>`
                + `${tecla ? `<kbd>${tecla}</kbd> ` : ''}${esc(nombre)}</a>`).join('') + '</nav>'
            + caidos.map(f => `<div class="fila falla">caído · ${esc(f)}</div>`).join('')
            + '<div class="regla"></div></div>';
    }


    private async leerAtajos(): Promise<void> {
        const r = await cli.config();
        this.atajos = r.datos?.atajos ?? [];
        this.bloquesCfg = r.datos?.bloques ?? [];
        this.pestanasCfg = r.datos?.pestanas ?? [];
        this.dashOrden = r.datos?.dashboard?.orden ?? [];
        this.dashOcultas = r.datos?.dashboard?.ocultas ?? [];
        this.modulosCfg = r.datos?.modulos ?? [];
        yo.persona = r.datos?.persona ?? '';
        yo.nombres = r.datos?.persona_nombres ?? [];
        this.general = r.datos?.agente_general?.clave ? { clave: r.datos.agente_general.clave, nombre: r.datos.agente_general.nombre ?? r.datos.agente_general.clave } : undefined;
        this.render();
        void this.leerBloques();
    }

    /** Los bloques del día (`[bloques.<clave>]`): una sección cada uno, con su color, su cuenta
     *  y en el título los atajos que dicen `en = "<clave>"`. Lo que muestran lo pide
     *  `leerBloques`, aparte y con el ritmo de la red: un comando lento no frena el día. */
    private bloques(cuales: cli.JsonBloque[], soloConAlgo = false): string[] {
        const h: string[] = [];
        for (const b of cuales) {
            const leido = this.bloquesDatos.get(b.clave);
            if (soloConAlgo && !(leido?.pagina?.bloques ?? []).some(x => x.items?.length)) continue;
            const itemsB = (leido?.pagina?.bloques ?? []).flatMap(x => x.items ?? []);
            const conTareasB = itemsB.some(x => Array.isArray(x.tareas));
            const solo = this.soloPendientes.has(b.clave);
            // con tareas en sus filas (los correos), un interruptor: solo las que tienen alguna pendiente
            const filtro = !conTareasB ? '' : `<a class="solo-pend${solo ? ' si' : ''}" data-accion="solo-pendientes" data-valor="${esc(b.clave)}"`
                + ` title="${solo ? 'mostrar todos' : 'mostrar solo los que tienen alguna tarea pendiente'}">${solo ? '☑' : '☐'} con tareas pendientes</a>`;
            const suyos = this.atajos.filter(a => a.en === b.clave)
                .map(a => atajo(a.tecla, a.nombre, 'atajo', a.tecla, a.descripcion || a.mensaje)).join('') + filtro;
            h.push(seccion(b.nombre, b.color, leido?.pagina?.subtitulo ?? '', suyos));
            if (!leido) h.push('<div class="vacio">leyendo…</div>');
            else if (leido.error) h.push(`<div class="vacio falla">${esc(leido.error)}</div>`);
            else {
                // un bloque puede traer, además de filas, un lienzo (un gráfico) y texto, como una página
                for (const x of leido.pagina?.bloques ?? []) {
                    if (x.lienzo) h.push(this.htmlLienzo(x.lienzo));
                    if (x.texto) h.push(`<div class="md-pag">${mdSimple(x.texto)}</div>`);
                }
                const items = (leido.pagina?.bloques ?? []).flatMap(x => x.items ?? []);
                const otros = (leido.pagina?.bloques ?? []).some(x => x.lienzo || x.texto);
                if (!items.length && !otros) h.push('<div class="vacio">nada</div>');
                // si el bloque dice las tareas de sus ítems (un correo), van en una columna propia, a la derecha
                const conTareas = items.some(x => Array.isArray(x.tareas));
                // ¿sigue pendiente? Lo dice la lista de tareas de ahora (el estado que trae el ítem
                // puede ser de antes); sin ella todavía, el estado del ítem
                const vivas = this.datos ? new Set(pendientes(this.datos).filter(q => !this.decididas.has(q.fila.id || q.ref))
                    .map(q => `${q.fila.proveedor}:${q.fila.id || q.ref}`)) : undefined;
                const pendiente = (t: { proveedor: string; id: string; estado?: string }) =>
                    vivas ? vivas.has(`${t.proveedor}:${t.id}`) : !/^(hecha|cerrada|descartada|cancelada)$/.test(t.estado ?? '');
                // un ítem es una fila; un clic lo muestra con sus tareas (procesarlo en un hilo es un botón de ahí)
                type Extra = { hijo?: boolean; cuantos?: number; abierta?: boolean; llave?: string; ts?: NonNullable<cli.JsonPaginaItem['tareas']>; nuevo?: boolean; marca?: string };
                const fila = (x: cli.JsonPaginaItem, i: number, e: Extra = {}) => {
                    const clic = x.mensaje || x.tareas?.length ? ` data-accion="ver-item" data-valor="${esc(b.clave)}:${i}"` : '';
                    const ts = e.ts ?? x.tareas ?? [];
                    // las cerradas, apagadas: de un vistazo, si al correo le queda algo por hacer
                    const tareas = !conTareas ? '' : `<span class="tar" title="${esc(ts.map(t => `${t.id} ${pendiente(t) ? (t.estado || 'pendiente') : 'cerrada'}`).join('\n') || 'sin tareas')}">`
                        + (ts.length ? ts.map(t => `<span class="${pendiente(t) ? 'abierta' : 'cerrada'}">${esc(t.id)}</span>`).join(', ') : '—') + '</span>';
                    // una conversación: ▸ con cuántos son, que la despliega
                    const plegar = e.cuantos ? `<span class="plegar" data-accion="grupo-item" data-valor="${esc(e.llave!)}" title="${e.abierta ? 'plegar' : `ver los ${e.cuantos} de esta conversación`}">${e.abierta ? '▾' : '▸'}${e.cuantos}</span> ` : '';
                    const nuevo = e.nuevo ?? x.destacado;
                    return `<div class="cr${conTareas ? ' con-t' : ''}${e.hijo ? ' hijo' : ''}${nuevo ? ' nuevo' : ''}${clic ? ' clic' : ''}"${clic}`
                        + ` title="${esc(clic ? `clic: ${x.tareas?.length ? 'sus tareas' : 'verlo'}${x.mensaje ? ', y procesarlo en un hilo' : ''}` : x.titulo)}"><span class="mk">${esc(e.marca ?? x.marca ?? '·')}</span>`
                        + `<span class="hora" title="${esc((x.fecha ?? '').replace('T', ' '))}">${esc(cuandoCorto(x.fecha ?? ''))}</span>`
                        + `<span class="de">${esc(conTareas ? (x.texto ?? '').replace(/ · tareas: .*$/, '') : x.texto ?? '')}</span><span class="que">${plegar}${esc(x.titulo)}</span>${tareas}</div>`;
                };
                // los de una misma conversación (`grupo`), anidados bajo el más reciente, como Gmail; el
                // orden es el de la lista: cada conversación va donde aparece su primer ítem
                const grupos = new Map<string, number[]>();
                items.forEach((x, i) => { const g = x.grupo || `#${i}`; if (!grupos.has(g)) grupos.set(g, []); grupos.get(g)!.push(i); });
                let mostrados = 0;
                for (const [g, idx] of grupos) {
                    const x = items[idx[0]];
                    if (solo && !idx.some(k => (items[k].tareas ?? []).some(pendiente))) continue;
                    mostrados++;
                    if (idx.length === 1) { h.push(fila(x, idx[0])); continue; }
                    const llave = `${b.clave}:${g}`;
                    const abierta = this.gruposAbiertos.has(llave);
                    const todos = idx.map(k => items[k]);
                    const ts = [...new Map(todos.flatMap(y => y.tareas ?? []).map(t => [t.id, t])).values()];
                    // la conversación está sin procesar si alguno de sus correos lo está
                    const nuevo = todos.some(y => y.destacado);
                    h.push(fila(x, idx[0], { cuantos: idx.length, abierta, llave, ts, nuevo, marca: nuevo ? (todos.find(y => y.destacado)?.marca ?? x.marca) : x.marca }));
                    if (abierta) idx.slice(1).forEach(k => h.push(fila(items[k], k, { hijo: true })));
                }
                if (solo && items.length && !mostrados) h.push('<div class="vacio">ningún correo con tareas pendientes</div>');
            }
            h.push('</section>');
        }
        return h;
    }

    /** Pide lo que muestra cada bloque. Sin `forzar`, solo los que tienen más de 5 minutos. */
    private async leerBloques(forzar = false): Promise<void> {
        const ahora = Date.now();
        await Promise.all(this.bloquesCfg.map(async b => {
            const antes = this.bloquesDatos.get(b.clave);
            if (!forzar && antes && ahora - antes.hora < 5 * 60 * 1000) return;
            const r = await cli.bloque(b.clave);
            await this.precargarLienzos(r.datos?.bloques);
            this.bloquesDatos.set(b.clave, { pagina: r.datos, error: r.datos ? '' : (r.error ?? 'no contestó'), hora: Date.now() });
            if (this.pantalla === 'bloque' || this.pantalla === 'plan') this.render();
        }));
    }

    /** Un ítem de un bloque, solo: lo que dice, las tareas que nacieron de él (cada una abre su
     *  ficha) y, si trae `mensaje`, el botón para procesarlo en un hilo. */
    private htmlItem(b: cli.JsonBloque, x: cli.JsonPaginaItem, i: number): string[] {
        // el título lleva al original (la conversación en Gmail), en su pestaña si ya está abierta
        const titulo = x.enlace ? `<a class="titulo-item" data-accion="item-enlace" data-valor="${esc(b.clave)}:${i}" title="${esc(`abrirlo: ${x.enlace}`)}"><b>${esc(x.titulo)}</b> ↗</a>` : `<b>${esc(x.titulo)}</b>`;
        const h = [`<div class="subcab"><a data-accion="item-volver" title="volver a la lista">‹ ${esc(b.nombre)}</a>&nbsp; ${titulo}`
            + `<span class="dim">${esc((x.texto ?? '').replace(/ · tareas: .*$/, ''))}${x.fecha ? ` · ${esc(x.fecha.slice(0, 16).replace('T', ' '))}` : ''}</span></div>`];
        // el cuerpo: cinco líneas, y «ver todo» lo despliega
        if (x.id) {
            const llave = `${b.clave}:${x.id}`;
            const c = this.cuerpos.get(llave);
            if (!c || (!c.texto && !c.error)) h.push('<div class="fila dim">leyendo el correo…</div>');
            else if (c.error) h.push(`<div class="fila dim">sin el cuerpo: ${esc(c.error)}</div>`);
            else {
                const abierto = this.cuerposAbiertos.has(llave);
                const largo = c.texto!.split('\n').length > 5 || c.texto!.length > 600;
                h.push(`<div class="cuerpo${abierto || !largo ? '' : ' plegado'}">${esc(c.texto!)}</div>`);
                if (largo) h.push(`<div class="fila"><a data-accion="cuerpo-alternar" data-valor="${esc(llave)}">${abierto ? '▴ plegar' : '▾ ver todo'}</a></div>`);
            }
        }
        h.push('<h2>Tareas<small>las que nacieron de este correo o de otro mensaje de su conversación</small></h2>');
        if (!x.tareas?.length) h.push('<div class="fila dim">ninguna</div>');
        // las pendientes, con la misma fila que «tareas» (✓ ◉ ▶ ⋯, fecha, responsable): se responde en
        // Gmail y se vuelve aquí a cerrarla. Las que ya no están pendientes, en una línea, a su ficha
        const vivas = (this.datos ? pendientes(this.datos) : []).filter(q => !this.decididas.has(q.fila.id || q.ref));
        h.push('<div class="tareas-sueltas">');
        for (const t of x.tareas ?? []) {
            const p = vivas.find(q => q.fila.proveedor === t.proveedor && (q.fila.id === t.id || q.ref === t.id));
            if (p) { h.push(this.filaTarea(p, !!p.avance && !!p.fila.ficha, false)); continue; }
            const valor = esc(JSON.stringify([t.proveedor, t.id, t.id]));
            h.push(`<div class="fila clic" data-accion="tarea" data-valor="${valor}" title="clic: su ficha">`
                + `<span class="dim">${esc(t.id)}</span>&nbsp; <span class="dim">ya no está pendiente</span></div>`);
        }
        h.push('</div>');
        if (x.mensaje) {
            h.push('<h2>Procesar</h2>');
            h.push(`<div class="fila"><a data-accion="abrir-item" data-valor="${esc(b.clave)}:${i}" title="${esc(x.mensaje)}">▶ procesarlo en un hilo</a>`
                + `&nbsp;<span class="dim">abre un hilo con <code>${esc(x.mensaje)}</code></span></div>`);
        }
        return h;
    }

    /** Un clic en «procesar» de un ítem que trae `mensaje`: un hilo nuevo para ese ítem. */
    private async abrirItem(valor: string): Promise<void> {
        const corte = valor.lastIndexOf(':');
        const clave = valor.slice(0, corte);
        const x = (this.bloquesDatos.get(clave)?.pagina?.bloques ?? []).flatMap(b => b.items ?? [])[Number(valor.slice(corte + 1))];
        if (!x?.mensaje) return;
        const r = await cli.abrirItem(clave, x.mensaje, x.nombre || x.titulo);
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir el hilo'}`);
            return;
        }
        await modelo.sondear();
        await ui.mostrarTerminal();
    }

    private async lanzarAtajo(tecla: string): Promise<void> {
        const nombre = this.atajos.find(a => a.tecla === tecla)?.nombre ?? tecla;
        // apretarla dos veces seguidas encargaba lo mismo dos veces (y el agente lo hacía dos veces)
        const antes = this.atajosLanzados.get(tecla);
        if (antes && Date.now() - antes < 120000) {
            const si = await ui.aviso(`«${nombre}» ya se encargó hace ${Math.round((Date.now() - antes) / 1000)} s. ¿Otra vez?`, 'Sí');
            if (si !== 'Sí') { await ui.mostrarTerminal(); return; }
        }
        const r = await ui.progreso({ titulo: `telar: ${nombre}…` }, () => cli.atajo(tecla));
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir el atajo'}`);
            return;
        }
        this.atajosLanzados.set(tecla, Date.now());
        const estado = (r.datos as { encargo?: string }).encargo;
        void ui.estado(`telar: ${nombre} → ${r.datos.hilo}${estado ? ` (${estado})` : ''}`, 8000);
        await modelo.sondear();
        await ui.mostrarTerminal();
    }

    /** La página de una sección: la pide a `telar seccion`, que corre su `home`. Abre el
     *  panel si hace falta; el refresco del día no la pisa (ver `render`). */
    async abrirSeccion(clave: string): Promise<void> {
        this.abrir();
        const antes = this.appActual;
        this.pantalla = 'seccion';
        if (this.seccion !== clave) { this.seccion = clave; this.pagina = undefined; }
        if (antes !== this.appActual) this.alCambiarFoco?.(true);
        // «app:<clave>» es una app (`telar app`); lo demás, una sección o un agente (`telar seccion`)
        const app = clave.startsWith('app:') ? clave.slice(4) : '';
        const nombre = (app ? modelo.apps.find(a => a.clave === app)?.nombre : modelo.secciones.find(s => s.clave === clave)?.nombre) ?? clave;
        if (!this.pagina) this.pintar([`<div class="subcab"><b>${esc(nombre)}</b></div>`, '<div class="fila dim">leyendo…</div>']);
        const r = app ? await cli.app(app) : await cli.seccion(clave);
        await this.precargarLienzos(r.datos?.bloques);
        if (this.pantalla !== 'seccion' || this.seccion !== clave) return;
        if (!r.datos) {
            this.pintar([`<div class="subcab"><b>${esc(nombre)}</b></div>`,
                `<div class="fila falla">${esc(r.error ?? 'el home no contestó')}</div>`]);
            return;
        }
        this.pagina = r.datos;
        this.renderSeccion();
    }

    /** La ficha de una tarea: leerla y decidir sin abrir un agente. La arma el proveedor
     *  (`telar tarea`): su propuesta arriba, el contexto, la historia y los botones. */
    async abrirTarea(valor: string): Promise<void> {
        const [proveedor, id, ref] = JSON.parse(valor) as string[];
        // desde la barra el dashboard puede existir tapado por otra pestaña: se trae al frente,
        // en su columna y sin recargar (abrir() la movería a la activa y pediría el día de nuevo)
        if (!this.panel) this.abrir();
        else if (!this.panel.visible) this.mostrarme?.();
        if (this.pantalla === 'revisar') this.fichaDesde = this.pantalla;
        // desde un ítem de un bloque (un correo): al cerrar la ficha se vuelve a ese ítem
        if (this.pantalla === 'bloque') this.fichaDesde = `bloque:${this.bloqueSel}:${this.itemSel ?? ''}`;
        if (this.pantalla === 'pestana' || this.fichaDesde.startsWith('pestana:')) this.fichaDesde = `pestana:${this.pestana}`;
        this.pantalla = 'tarea';
        this.ficha = { proveedor, id, ref };
        const guardada = this.fichas.get(`${proveedor}:${id}`);
        if (guardada && Date.now() - guardada.hora < 5 * 60 * 1000) {
            this.ficha.pagina = guardada.pagina;
            this.renderTarea();
            void this.precargar();
            return;
        }
        this.pintar([`<div id="ficha-tarea"><div class="subcab"><b>${esc(id)}</b></div><div class="fila dim">leyendo…</div></div>`]);
        const r = await cli.tarea(id, proveedor);
        if (r.datos) this.fichas.set(`${proveedor}:${id}`, { pagina: r.datos, hora: Date.now() });
        if (this.pantalla !== 'tarea' || this.ficha?.id !== id) return;
        this.ficha.pagina = r.datos;
        this.ficha.aviso = r.datos ? '' : (r.error ?? 'la ficha no contestó');
        this.renderTarea();
        void this.precargar();
    }

    /** Pide por adelantado las fichas de la lista que se está recorriendo (hasta 10, cuatro a
     *  la vez): al apretar → la siguiente ya está. Las que ya se tienen no se vuelven a pedir. */
    private async precargar(): Promise<void> {
        const faltan = this.propuestas()
            .filter(p => { const g = this.fichas.get(`${p.proveedor}:${p.id}`); return !g || Date.now() - g.hora > 5 * 60 * 1000; })
            .slice(0, 10);
        const pedir = async () => {
            for (let p = faltan.shift(); p; p = faltan.shift()) {
                const r = await cli.tarea(p.id, p.proveedor);
                if (r.datos) this.fichas.set(`${p.proveedor}:${p.id}`, { pagina: r.datos, hora: Date.now() });
            }
        };
        await Promise.all([pedir(), pedir(), pedir(), pedir()]);
    }

    /** La pestaña «tareas»: todas, con lo que un agente dejó para decidir arriba (◆), y filtros para
     *  ver solo eso, lo vencido, lo de la semana… Un clic abre la ficha; ← → pasa de una propuesta a
     *  otra y al decidir salta a la siguiente. */
    private async abrirRevisar(): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'revisar';
        this.fichaDesde = 'revisar';
        if (!this.datos) this.datos = await dia();
        this.renderRevisar();
        // los nombres de los proyectos (para la columna): si no estaban, se piden y se repinta
        if (!this.proyectos) {
            const r = await cli.proyectos();
            if (r.datos) { this.proyectos = r.datos.proyectos; if (this.pantalla === 'revisar') this.renderRevisar(); }
        }
    }

    /** De qué proyecto es un pendiente: la carpeta que dice la tarea, o la del documento de donde salió,
     *  llevada a la unidad más honda que la contiene. */
    private proyectoDe(f: cli.JsonFila): cli.JsonProyecto | undefined {
        const carpeta = f.proyecto || f.ruta;
        if (!carpeta || !this.proyectos) return undefined;
        const ruta = unidadDe(carpeta, this.proyectos.map(p => p.ruta));
        return this.proyectos.find(p => p.ruta === ruta);
    }

    private renderRevisar(): void {
        const d = this.datos;
        if (!d) return;
        this.teclas.clear();
        this.pintar(this.tablaTareas(d));
    }

    /** La tabla de tareas: la de la pestaña «tareas» y la de «hoy» son la misma (filtros, columnas,
     *  orden, ⋯). Lo que se elija en una (el modo, lo buscado, el orden) se ve igual en la otra. */
    /** Una fila de tarea, la misma en «tareas» y donde se muestren tareas sueltas (un correo y las
     *  suyas): código, estrella, proyecto, responsable, texto, fecha, ✓ ◉ ▶ y ⋯. `rev`: espera una
     *  decisión; `semana`: va en «esta semana». */
    private filaTarea(p: ReturnType<typeof pendientes>[number], rev: boolean, semana: boolean): string {
        const esRev = (_p: unknown) => rev;
        const deLaSemana = (_p: unknown) => semana;
        const [todo] = (p.fila.avance ?? '').split(' ');
        const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
        const ficha = !!p.fila.ficha;
        const proy = this.proyectoDe(p.fila);
        // el proyecto en pocas letras: su cliente, o su nombre; entero en el globo
        // («Brinca» o «Interno» como cliente no dice nada: ahí va el nombre sin ese prefijo)
        const interno = !proy?.cliente || /^(brinca|interno)$/i.test(proy.cliente);
        const proyCorto = !proy ? '' : interno ? proy.nombre.replace(/^(brinca|interno)\s*·\s*/i, '') : proy.cliente!;
        const buscable = normalizar([p.ref, p.texto, p.hilo, p.fila.ruta ?? '', p.fila.proyecto ?? '', proy?.nombre ?? '', p.fila.avance ?? '', p.fila.dueno ?? ''].join(' '));
        const accion = ficha ? `data-accion="tarea" data-valor="${valor}" title="clic: leerla y decidir"`
            : `data-accion="pendiente" data-valor="${esc(p.ref)}" title="clic: ${p.hilo ? `llevarlo a «${esc(p.hilo)}»` : 'abrir un hilo donde trabajarlo'}"`;
        const dueno = p.fila.dueno ?? '';
        const persona = yo.persona ? yo.persona[0].toUpperCase() + yo.persona.slice(1) : 'tú';
        // el responsable: el dueño, o la persona en gris (es suya porque nadie la tomó); con ficha, un clic lo cambia
        // una viñeta de un documento: su responsable si lo dice (@owner(…) o «@Nombre:»), sin cambiarlo desde aquí
        const resp = !ficha ? (dueno ? `<span class="resp fijo" title="${esc(`responsable: ${dueno}\n(lo dice el documento)`)}">${esc(dueno)}</span>`
                : '<span class="resp dim" title="la viñeta no dice quién la hace">sin responsable</span>')
            : `<span class="resp${dueno ? '' : ' defecto'}" data-accion="dueno-tarea" data-valor="${esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref, dueno]))}"`
                + ` title="${esc(dueno ? `responsable: ${dueno}\nclic: cambiarlo` : `sin asignar: es tuya por defecto\nclic: asignarla`)}">${esc(dueno || persona)}</span>`;
        return `<div class="tarea${p.enCurso ? ' encurso' : ''}" ${accion} data-area="${esc(p.fila.area ?? '')}"${datosDueno(dueno, ficha || !!p.fila.proveedor)}`
            + ` data-rev="${esRev(p) ? 1 : 0}" data-dias="${p.dias ?? ''}" data-encurso="${p.enCurso ? 1 : 0}" data-texto="${esc(buscable)}"`
            + ` data-sem="${deLaSemana(p) ? 1 : 0}" data-estrella="${p.fila.estrella ? 1 : 0}" data-est="${p.fila.estrella ? 'a' : ''}"`
            + ` data-orden="${p.urgencia}" data-ref="${esc(p.ref)}" data-alfa="${esc(normalizar(limpiarMd(p.texto)))}"`
            + ` data-proy="${esc(normalizar(proyCorto))}" data-resp="${esc(normalizar(dueno || (ficha ? persona : '')))}">`
            + `<span class="id">${esc(ficha || p.fila.proveedor ? p.ref : '·')}</span>`
            // la estrella: con ficha, un clic la pone o la quita (la guarda el proveedor, en la tarea)
            + (ficha ? `<span class="estr${p.fila.estrella ? ' on' : ''}" data-accion="estrella-tarea" data-valor="${valor}" title="${p.fila.estrella ? 'quitar la estrella' : 'marcar con estrella: va siempre en «esta semana»'}">${p.fila.estrella ? '★' : '☆'}</span>` : '<span></span>')
            + `<span class="pri">${p.enCurso ? '●' : ''}</span>`
            + (proy ? `<span class="proy-t" data-accion="proy-ir" data-valor="${esc(proy.ruta)}" title="${esc(`${proy.nombre}\nclic: verlo en proyectos`)}">${esc(proyCorto)}</span>`
                : '<span class="proy-t dim">—</span>') + resp
            + `<span class="desc">${esRev(p) ? `<span class="av av-${esc(p.avance)}">${esc(todo.replace(':', ' '))}</span>` : ''}`
            + `${esc(limpiarMd(p.texto))}</span>`
            // el atraso es un botón: reagendar lo que venció sin abrir la ficha
            + `<span class="meta">${ficha ? `<span class="plazo-clic" data-accion="reagendar" data-valor="${valor}" title="clic: nueva fecha">${p.dias === null ? '<span class="dim">fecha</span>' : plazo(p.dias)}</span>` : plazo(p.dias)}`
            // las acciones de la tarea sin abrir la ficha: cerrar, nota, esperar… directo, sin la IA
            + `<span class="destino"></span>${this.rapidas(p.fila, p.ref, p.texto, valor, ficha)}${ficha ? `<span class="menu-fila" data-accion="menu-tarea" data-valor="${valor}" title="acciones de esta tarea">⋯</span>`
                : `<span class="menu-fila" data-accion="menu-vineta" data-valor="${esc(JSON.stringify([p.ref, p.texto, p.hilo, dueno]))}" title="acciones de este pendiente">⋯</span>`}</span></div>`;
    }

    /** Las acciones de todos los días, a un clic, antes del ⋯: ✓ marcarla hecha, ◉/○ compartirla con
     *  el equipo (solo una tarea con ficha, y si hay equipo) y ▶ llevarla a un hilo. En una viñeta de
     *  un README, ✓ marca su casilla. */
    private rapidas(fila: cli.JsonFila, ref: string, texto: string, valor: string, ficha: boolean): string {
        const compartida = !!fila.etiquetas?.includes('equipo');
        const hecha = ficha ? `<span class="rap ok" data-accion="hecha-fila" data-valor="${valor}" title="marcarla hecha">✓</span>`
            : !fila.proveedor ? `<span class="rap ok" data-accion="hecha-vineta" data-valor="${esc(JSON.stringify([ref, texto]))}" title="marcarla hecha: [ ] → [x] en su documento">✓</span>`
            : '<span class="rap"></span>';
        const eq = ficha && modelo.equipoRemoto
            ? `<span class="rap eq${compartida ? ' on' : ''}" data-accion="equipo-tarea" data-valor="${valor}" title="${compartida ? 'compartida con el equipo: clic para dejar de compartirla' : 'compartirla con el equipo (verán título, estado y prioridad; pueden sugerir subirla)'}">${compartida ? '◉' : '○'}</span>`
            : '<span class="rap"></span>';
        // una tarea con ficha va a su hilo (el de su proyecto, o el agente general) con /tarea <id>,
        // enviado: el agente la empieza con su contexto cargado. Una casilla de un README, escrita
        const hilo = `<span class="rap ir" data-accion="hilo-fila" data-valor="${esc(JSON.stringify([fila.proveedor, ref, ficha ? fila.id || ref : '']))}"`
            + ` title="${ficha ? `trabajarla: /tarea ${esc(fila.id || ref)} en ${fila.hilo ? `«${esc(fila.hilo)}»` : 'su hilo'}` : fila.hilo ? `llevarla a «${esc(fila.hilo)}»` : 'abrirla en un hilo'}">▶</span>`;
        return `<span class="rapidas">${hecha}${eq}${hilo}</span>`;
    }

    private tablaTareas(d: Dia): string[] {
        const lista = pendientes(d).filter(p => !this.decididas.has(p.fila.id || p.ref));
        const esRev = (p: (typeof lista)[number]) => !!p.avance && !!p.fila.ficha;
        const cuenta = (f: (p: (typeof lista)[number]) => boolean) => lista.filter(f).length;
        // cada filtro con su cuenta: lo que decide qué mirar es cuánto hay
        // «esta semana», lo que se ve de entrada: lo vencido o que vence en 7 días, lo destacado (P0 o con
        // estrella) y lo que espera una decisión con fecha en 14 días. Lo demás, detrás de «ver todas»
        const deLaSemana = (p: (typeof lista)[number]) => (p.dias !== null && p.dias <= 7) || !!p.fila.destacada
            || (esRev(p) && p.dias !== null && p.dias <= 14);
        const modos: [string, string, number][] = [
            ['semana', 'esta semana', cuenta(deLaSemana)], ['todas', 'todas', lista.length], ['revisar', '◆ por revisar', cuenta(esRev)],
            ['vencidas', 'vencidas', cuenta(p => p.dias !== null && p.dias < 0)],
            ['estrella', '★', cuenta(p => !!p.fila.estrella)],
            ['encurso', 'en curso', cuenta(p => p.enCurso)], ['sinfecha', 'sin fecha', cuenta(p => p.dias === null)],
        ];
        // cuándo se leyeron: el proveedor se consulta solo cada 5 minutos, y «actualizar» lo fuerza ya
        const leido = leidoProveedores();
        const hace = leido ? Math.round((Date.now() - leido) / 60000) : -1;
        const actualizar = `<a data-accion="refrescar" title="volver a leer las tareas ahora (también r)">↻ actualizar</a>`
            + `<span class="dim"> · ${hace < 0 ? 'sin leer' : hace === 0 ? 'leídas recién' : `leídas hace ${hace} min`}</span>`;
        const h = ['<div id="revisar">', seccion('tareas', 'cian', String(lista.length), actualizar),
            '<div class="titulo-tareas"><span class="modos">'
            + modos.map(([k, n, c]) => `<button data-modo-t="${k}"${c ? '' : ' class="vacio-m"'}>${esc(n)} ${c}</button>`).join('')
            + `<input id="buscar-t" type="text" placeholder="/ buscar" spellcheck="false" autocomplete="off"><span id="tareas-t-cuenta"></span></span></div>`,
            filtroAreas(lista.map(p => p.fila.area ?? '')), filtroDuenos(lista.map(p => [p.fila.dueno ?? '', !!p.fila.proveedor] as [string, boolean]))];
        if (!lista.length) h.push('<div class="vacio">nada pendiente</div>');
        // el nombre de cada columna: el clic ordena por ella (la que ordena, en azul), otro clic vuelve al orden de
        // siempre (urgencia). La fecha va sobre las fechas: la cabecera repite la grilla de lo que hay a la derecha
        const col = (k: string, nombre: string, por: string) =>
            `<span data-orden-c="${k}" title="${esc(`ordenar por ${por} (otra vez: por urgencia)`)}">${nombre}</span>`;
        h.push(`<div class="tareas-cab">${col('ref', 'código', 'código, lo más nuevo arriba')}${col('est', '★', 'estrella')}<span></span>`
            + `${col('proy', 'proyecto', 'proyecto')}${col('resp', 'responsable', 'responsable')}${col('alfa', 'tarea', 'el texto, alfabético')}`
            + `<span class="meta">${col('dias', 'fecha', 'fecha límite: lo más vencido arriba, lo sin fecha al final')}<span></span><span></span><span></span></span></div>`);
        h.push('<div id="tareas-t">');
        for (const p of lista) h.push(this.filaTarea(p, esRev(p), deLaSemana(p)));
        h.push('<div id="tareas-t-vacio" class="vacio" hidden></div><div id="tareas-t-mas" class="vacio clic" hidden></div></div></section></div>');
        return h;
    }

    // ── el plan del día y el calendario ────────────────────────────────────────

    /** El plan de un día (vacío es hoy), leído de la máquina donde lo escribe la skill. */
    private async abrirPlan(diaPedido: string): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'plan';
        this.planCargando = true;
        this.renderPlan();
        const r = await cli.resultado('plan', diaPedido);
        this.planCargando = false;
        this.plan = r.datos?.ok ? r.datos : undefined;
        this.planError = r.datos?.ok ? '' : (r.datos?.error ?? r.error ?? 'no contestó');
        if (this.pantalla === 'plan') this.renderPlan();
    }

    private renderPlan(): void {
        this.teclas.clear();
        // arriba, los bloques que van en el plan (la retro de la tarde), si traen algo
        this.pintar([...this.bloques(this.bloquesCfg.filter(b => b.en === 'plan'), true),
            ...htmlPlan(this.plan, this.planError, this.planCargando)]);
    }

    /** El día que muestra el calendario: hoy, u otro al que se navegó (`calFecha`). */
    private diaCal(): Dia | undefined {
        return this.calFecha && this.calFecha !== this.datos?.fecha ? this.calDatos : this.datos;
    }

    /** El calendario de un día (vacío es hoy): los eventos, los bloques del plan y las notas de cada uno. */
    private async abrirCalendario(fecha = ''): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'calendario';
        if (!this.datos) this.datos = await dia();
        const hoyIso = this.datos.fecha;
        this.calFecha = fecha === hoyIso ? '' : fecha;
        const iso = this.calFecha || hoyIso;
        this.calCargando = !!this.calFecha && this.calDatos?.fecha !== iso;
        if (this.calCargando) { this.calDatos = { ...this.datos, fecha: iso, agenda: [], pendientes: [], error: undefined }; this.notas = undefined; }
        this.renderCalendario();
        const [otro, plan, notas] = await Promise.all([
            this.calFecha ? diaDe(iso) : Promise.resolve(this.datos),
            this.plan?.dia === iso ? Promise.resolve({ datos: this.plan }) : cli.resultado('plan', this.calFecha ? iso : ''),
            cli.notasEventos(this.calFecha ? iso : ''),
        ]);
        if ((this.calFecha || hoyIso) !== iso) return;  // se cambió de día mientras esto cargaba
        if (this.calFecha) this.calDatos = otro;
        this.calCargando = false;
        if (plan.datos?.ok) this.plan = plan.datos;
        this.notas = notas.datos?.ok ? notas.datos : undefined;
        this.notasAviso = notas.datos?.aviso ?? (notas.datos?.ok ? '' : (notas.datos?.error ?? notas.error ?? ''));
        if (this.pantalla === 'calendario') this.renderCalendario();
    }

    /** ‹ › y «hoy» del calendario: `valor` es «hoy» o cuántos días moverse. */
    private async moverDiaCal(valor: string): Promise<void> {
        const hoyIso = this.datos?.fecha;
        if (!hoyIso) return;
        if (valor === 'hoy') { this.eventoSel = ''; return this.abrirCalendario(''); }
        const f = new Date(`${this.calFecha || hoyIso}T12:00:00`);
        f.setDate(f.getDate() + (Number(valor) || 0));
        const dos = (n: number) => String(n).padStart(2, '0');
        this.eventoSel = '';
        await this.abrirCalendario(`${f.getFullYear()}-${dos(f.getMonth() + 1)}-${dos(f.getDate())}`);
    }

    private renderCalendario(): void {
        const d = this.diaCal();
        if (!d) return;
        this.teclas.clear();
        this.teclas.set('[', () => this.moverDiaCal('-1'));
        this.teclas.set(']', () => this.moverDiaCal('1'));
        const plan = this.plan?.dia === d.fecha && this.plan.formato === 'json' ? this.plan.contenido as Record<string, unknown> : undefined;
        this.pintar(htmlCalendario(d, eventosDelDia(d, plan), this.notas, this.eventoSel, new Date(), this.notasAviso,
            this.general?.nombre ?? '', this.datos?.fecha ?? d.fecha, this.calCargando));
    }

    /** Lo que la persona le escribe al agente general sobre una reunión, con todo el contexto que el
     *  agente necesita para no preguntar: la reunión, su proyecto, lo que dicen el plan y las notas. */
    /** Un comentario sobre el plan de un día: lo atiende la máquina donde vive el plan, que abre un hilo
     *  con un agente; ese agente actualiza el plan, y la pestaña lo relee en un rato. */
    private async comentarPlan(dia: string, texto: string): Promise<void> {
        const r = await ui.progreso({ titulo: 'telar: mandando el comentario sobre el plan…' }, () => cli.comentarResultado('plan', dia, texto));
        if (!r.ok) { void ui.falla(`telar: el comentario no llegó: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.info(r.abrio ? `telar: se abrió «${r.abrio}» para atender el comentario` : 'telar: comentario recibido');
        setTimeout(() => { this.plan = undefined; void this.actualizar(true); }, 30000);
    }

    private async escribirSobreEvento(id: string, texto: string): Promise<void> {
        const d = this.diaCal();
        if (!texto.trim() || !d) return;
        if (!this.general) { void ui.aviso('telar: no hay un agente que reciba lo sin proyecto ([agentes] sin_proyecto)'); return; }
        const plan = this.plan?.dia === d.fecha && this.plan.formato === 'json' ? this.plan.contenido as Record<string, unknown> : undefined;
        const e = eventosDelDia(d, plan).find(x => x.id === id);
        if (!e) return;
        const hm = (ms: number) => new Date(ms).toTimeString().slice(0, 5);
        // de qué proyecto es: lo que telar recuerda para la serie o lo que deduce (sin hacer nada)
        let proyecto = '';
        if (!e.soloPlan) {
            const r = await cli.reunion(e.titulo, hm(e.inicio), e.url, e.id, { asistentes: e.asistentes, preguntar: true, donde: true });
            if (r.datos?.destino && r.datos.destino !== 'gestion') proyecto = `Proyecto: ${r.datos.destino}${r.datos.recordado ? ' (elegido por Nico para esta serie)' : ' (deducido)'}.`;
            else if (r.datos?.candidatos?.length) proyecto = `Proyecto: no está claro; candidatos: ${r.datos.candidatos.slice(0, 3).map(c => `${c.ruta} (${c.motivos.join(', ')})`).join('; ')}.`;
            else proyecto = 'Proyecto: ninguno deducido.';
        }
        const notas = notasDe(e, this.notas).map(n => `${n.de}: ${n.texto}`);
        const lineas = [
            `[Nico, desde el calendario del dashboard] ${texto.trim()}`,
            '',
            `Contexto. La reunión: «${e.titulo}», ${d.fecha} de ${hm(e.inicio)} a ${hm(e.fin)}${e.lugar ? `, ${e.lugar}` : ''}${e.soloPlan ? ' (bloque del plan del día, no está en el calendario)' : ''}.`,
            e.asistentes.length ? `Asistentes: ${e.asistentes.join(', ')}.` : '',
            proyecto,
            e.plan?.nota ? `El plan del día dice: ${e.plan.nota}` : '',
            e.plan?.ficha?.decision ? `Decisión que pide el plan: ${e.plan.ficha.decision}` : '',
            notas.length ? `Notas del evento: ${notas.join(' | ')}` : '',
            `Id del evento: ${e.id}. Si lo que hagas es de esta reunión, déjale una nota: telar evento nota "${e.id}" "…" --de ${this.general.clave} --titulo "${e.titulo}" --inicio ${hm(e.inicio)} --dia ${d.fecha}`,
        ].filter(Boolean);
        const r = await ui.progreso({ titulo: `telar: escribiéndole a ${this.general.nombre}…` },
            () => cli.encargar(this.general!.clave, lineas.join('\n')));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${this.general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        // queda constancia en el evento: lo que se pidió y a quién
        await cli.notaEvento(e.id, `A ${this.general.nombre}: ${texto.trim()}`, e.titulo, hm(e.inicio), d.fecha);
        const n = await cli.notasEventos(d.fecha);
        if (n.datos?.ok) this.notas = n.datos;
        this.eventoSel = id;
        void ui.estado(`telar: enviado a ${this.general.nombre} (${r.datos.estado ?? ''})`, 6000);
        if (this.pantalla === 'calendario') this.renderCalendario();
    }

    /** Una nota de la persona sobre un evento: se guarda donde viven las notas (`telar evento nota`). */
    private async notaEvento(valor: string): Promise<void> {
        const [id, titulo, inicio, fecha] = JSON.parse(valor) as string[];
        const texto = await ui.campo({ titulo: `Nota para «${titulo}»`, ayuda: 'Se guarda junto al evento y la ven las skills' });
        if (!texto?.trim()) return;
        const r = await cli.notaEvento(id, texto.trim(), titulo, inicio, fecha);
        if (!r.datos?.ok) { void ui.falla(`telar: la nota no se guardó: ${r.datos?.error ?? r.error ?? 'sin respuesta'}`); return; }
        this.eventoSel = id;
        const notas = await cli.notasEventos(fecha);
        if (notas.datos?.ok) this.notas = notas.datos;
        if (this.pantalla === 'calendario') this.renderCalendario();
    }

    // ── procesos periódicos ────────────────────────────────────────────────────

    /** La pestaña de los procesos que corren solos: de esta máquina, o de la de `[periodicos] en`. */
    private async abrirPeriodicos(): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'periodicos';
        if (!this.periodicos) this.pintar(['<div class="vacio">leyendo los procesos periódicos…</div>']);
        const r = await cli.periodicos();
        this.periodicos = r.datos ?? this.periodicos;
        this.periodicosError = r.datos ? '' : (r.error ?? 'no contestó');
        if (this.pantalla === 'periodicos') this.renderPeriodicos();
    }

    private renderPeriodicos(): void {
        const d = this.periodicos;
        this.teclas.clear();
        this.teclas.set('+', () => this.nuevoPeriodico());
        if (this.formPer) { this.renderFormPer(); return; }
        if (this.periodico) { this.renderPeriodico(); return; }
        const lista = d?.procesos ?? [];
        const activos = lista.filter(p => p.activo).length;
        const h = [seccion(`periódicos${d?.maquina ? ` · ${d.maquina}` : ''}`, 'amarillo', lista.length ? `${activos}/${lista.length}` : '',
            atajo('+', 'nuevo', 'per-nuevo', '', 'un proceso nuevo: un comando de shell o un prompt para el agente'))];
        if (this.periodicosError) h.push(`<div class="vacio falla">${esc(this.periodicosError)}</div>`);
        if (d && !lista.length) h.push(`<div class="vacio">ninguno todavía · <a data-accion="per-nuevo">crear uno</a> · se guardan en ${esc(d.archivo)}</div>`);
        for (const p of lista) {
            const [marca, color, dice] = estadoPeriodico(p);
            const que = p.tipo === 'mensaje' ? `✦ ${p.mensaje}` : p.comando;
            const cuando = p.activo ? (p.proxima ? `en ${enCuanto(p.proxima)}` : '—') : 'pausado';
            const ultima = p.ultima.inicio ? `hace ${haceCorto(p.ultima.inicio)}` : 'nunca';
            h.push(`<div class="fila clic per${p.activo ? '' : ' dim'}" data-accion="per-ver" data-valor="${esc(p.nombre)}" title="${esc(`${p.descripcion ? p.descripcion + '\n' : ''}${dice}\nclic: su ficha y su log`)}">`
                + `<span style="color: var(--${color})">${marca}</span><b>${esc(p.nombre)}</b>`
                + `<code class="dim">${esc(p.cuando)}</code><span class="que">${esc(que)}</span>`
                + `<span class="der dim">${esc(cuando)} · ${esc(ultima)}</span></div>`);
        }
        h.push('</section>');
        if (d) h.push(`<div class="vacio dim">${esc(d.archivo)}${d.zona ? ` · hora de ${esc(d.zona)}` : ''}</div>`);
        this.pintar(h);
    }

    private async verPeriodico(nombre: string): Promise<void> {
        this.periodico = { nombre, log: 'leyendo…' };
        this.renderPeriodicos();
        const r = await cli.periodicosLog(nombre);
        if (this.periodico?.nombre !== nombre) return;
        this.periodico.log = r.datos ? (r.datos.log || '(todavía no ha corrido)') : (r.error ?? 'no contestó');
        if (this.pantalla === 'periodicos') this.renderPeriodicos();
    }

    private renderPeriodico(): void {
        const actual = this.periodico;
        const p = this.periodicos?.procesos.find(x => x.nombre === actual?.nombre);
        if (!actual || !p) { this.periodico = undefined; this.renderPeriodicos(); return; }
        const [marca, color, dice] = estadoPeriodico(p);
        const orden = (args: string[]) => esc(JSON.stringify(args));
        const botones = [
            `<a class="atajo principal" data-accion="per-orden" data-valor="${orden(['ahora', p.nombre])}"><kbd>⏎</kbd><span>correr ahora</span></a>`,
            `<a class="atajo" data-accion="per-orden" data-valor="${orden([p.activo ? 'pausar' : 'activar', p.nombre])}"><kbd>1</kbd><span>${p.activo ? '⏸ pausar' : '▶ activar'}</span></a>`,
            `<a class="atajo" data-accion="per-editar" data-valor="${esc(p.nombre)}"><kbd>2</kbd><span>✎ editar</span></a>`,
            `<a class="atajo" data-accion="per-orden" data-valor="${orden(['borrar', p.nombre])}"><kbd>3</kbd><span>✕ borrar</span></a>`,
            `<a class="atajo" data-accion="periodicos"><kbd>⎋</kbd><span>volver</span></a>`,
        ];
        this.teclas.set('⏎', () => this.ordenPeriodico(['ahora', p.nombre]));
        this.teclas.set('1', () => this.ordenPeriodico([p.activo ? 'pausar' : 'activar', p.nombre]));
        this.teclas.set('2', () => this.editarPeriodico(p.nombre));
        this.teclas.set('3', () => this.ordenPeriodico(['borrar', p.nombre]));
        const filas: [string, string][] = [
            ['cuándo', `${p.cuando}${p.proxima ? ` · la próxima ${p.proxima.slice(5, 16).replace('T', ' ')} (en ${enCuanto(p.proxima)})` : ''}`],
            p.tipo === 'mensaje' ? ['prompt', p.mensaje] : ['comando', p.comando],
            ...(p.tipo === 'mensaje' ? [['hilo', `${p.hilo || p.nombre} · hasta ${p.max_abiertos} abierto(s)`] as [string, string]] : []),
            ...(p.argumentos.length ? [['argumentos', p.argumentos.join(' ')] as [string, string]] : []),
            ...(p.carpeta ? [['carpeta', p.carpeta] as [string, string]] : []),
            ['última', p.ultima.inicio ? `${p.ultima.inicio.slice(5, 16).replace('T', ' ')} · ${p.ultima.resultado ?? 'corriendo'}${p.ultima.hilo ? ` · «${p.ultima.hilo}»` : ''}` : 'nunca'],
        ];
        this.pintar([`<div id="ficha-per" style="--c: var(--${color})">`,
            `<div class="subcab"><b>${marca} ${esc(p.nombre)}</b><span class="der dim">${esc(dice)}</span></div>`,
            p.descripcion ? `<div class="sub-ficha dim">${esc(p.descripcion)}</div>` : '',
            `<div class="acciones-t">${botones.join('')}</div>`,
            ...filas.map(([k, v]) => `<div class="fila"><span class="dim" style="min-width: 11ch">${esc(k)}</span><span class="que">${esc(v)}</span></div>`),
            `<h2 class="sec">log</h2><pre class="log">${esc(actual.log)}</pre></div>`]);
    }

    /** Corre una orden de `telar periodicos` y relee: la lista cambia (o el log, si se corrió). */
    private async ordenPeriodico(args: string[]): Promise<void> {
        if (args[0] === 'borrar') {
            const si = await ui.aviso(`¿Borrar el proceso «${args[1]}»? Deja de correr; el archivo anterior queda en periodicos.toml.anterior.`, 'Borrar');
            if (si !== 'Borrar') return;
        }
        const r = await cli.periodicosOrden(args);
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? 'no se pudo'}`); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        if (args[0] === 'borrar') this.periodico = undefined;
        await this.abrirPeriodicos();
        if (this.periodico) {
            // «ahora» corre suelto: el log se relee en unos segundos, cuando ya escribió algo
            const nombre = this.periodico.nombre;
            setTimeout(() => { if (this.periodico?.nombre === nombre) void this.abrirPeriodicos().then(() => this.verPeriodico(nombre)); }, args[0] === 'ahora' ? 4000 : 0);
        }
    }

    /** Un proceso nuevo: el formulario, con lo que suelen llevar los que ya hay (carpeta, argumentos). */
    private async nuevoPeriodico(): Promise<void> {
        const hay = this.periodicos?.procesos ?? [];
        const modelo = hay.find(x => x.tipo === 'mensaje');
        const p: cli.JsonPeriodico = {
            nombre: '', cuando: '0 9 * * 1-5', tipo: 'mensaje', comando: '', mensaje: '', hilo: '', max_abiertos: 1,
            argumentos: modelo?.argumentos ?? ['--permission-mode', 'acceptEdits'], carpeta: modelo?.carpeta ?? '',
            descripcion: '', activo: true, proxima: '', ultima: {},
        };
        await this.abrirFormPer('', p);
    }

    private async editarPeriodico(nombre: string): Promise<void> {
        const p = this.periodicos?.procesos.find(x => x.nombre === nombre);
        if (p) await this.abrirFormPer(nombre, { ...p, argumentos: [...p.argumentos] });
    }

    private async abrirFormPer(original: string, p: cli.JsonPeriodico): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'periodicos';
        this.formPer = { original, p };
        this.renderPeriodicos();
        await Promise.all([this.previaHorario(p.cuando), this.cargarSkills(p.carpeta)]);
    }

    private renderFormPer(): void {
        const f = this.formPer;
        if (!f) return;
        const p = f.p;
        this.teclas.clear();
        const campo = (etiqueta: string, html: string, ayuda = '') =>
            `<label class="campo"><span class="etiqueta">${esc(etiqueta)}</span><span class="control">${html}`
            + `${ayuda ? `<span class="ayuda dim">${esc(ayuda)}</span>` : ''}</span></label>`;
        const presets: [string, string][] = [['0 9 * * *', 'todos los días 9:00'], ['0 9 * * 1-5', 'lun–vie 9:00'],
            ['0 8-20/2 * * *', 'cada 2 h, 8–20'], ['0 * * * *', 'cada hora'], ['*/30 * * * *', 'cada 30 min'],
            ['30 18 * * 5', 'viernes 18:30'], ['0 9 1 * *', 'el 1 de cada mes']];
        this.pintar([`<div id="form-per" class="tipo-${p.tipo}">`,
            seccion(f.original ? `editar «${f.original}»` : 'un proceso periódico nuevo', 'amarillo', this.periodicos?.maquina ?? ''),
            campo('nombre', `<input id="per-nombre" value="${esc(p.nombre)}" placeholder="resumen-diario" spellcheck="false"${f.original ? ' disabled' : ''}>`,
                f.original ? 'el nombre no se cambia' : 'minúsculas, números, - y _'),
            campo('para qué', `<input id="per-desc" value="${esc(p.descripcion)}" placeholder="en una línea, para acordarte">`),
            campo('qué hace', `<span class="opciones"><a class="opcion-t${p.tipo === 'mensaje' ? ' activa' : ''}" data-per-tipo="mensaje">✦ prompt para el agente</a>`
                + `<a class="opcion-t${p.tipo === 'comando' ? ' activa' : ''}" data-per-tipo="comando">$ comando de shell</a></span>`),
            `<div class="solo-mensaje">`,
            campo('skill', `<input id="per-skill-filtro" placeholder="buscar una skill…" spellcheck="false" autocomplete="off">`
                + `<div id="per-skills" class="skills">${this.htmlSkills()}</div>`, 'elegir una la pone como prompt; después puedes agregarle texto'),
            campo('prompt', `<textarea id="per-mensaje" rows="4" placeholder="/correo, o lo que quieras pedirle" spellcheck="false">${esc(p.mensaje)}</textarea>`),
            campo('hilo', `<input id="per-hilo" value="${esc(p.hilo)}" placeholder="${esc(p.nombre || 'el nombre del proceso')}">`, 'su nombre; se le agrega la fecha y la hora'),
            campo('abiertos', `<input id="per-max" type="number" min="1" value="${p.max_abiertos}">`, 'con tantos sin cerrar, esa vez no abre otro'),
            campo('argumentos', `<textarea id="per-args" rows="3" spellcheck="false">${esc(p.argumentos.join('\n'))}</textarea>`, 'para el agente, uno por línea (permisos, herramientas)'),
            `</div><div class="solo-comando">`,
            campo('comando', `<input id="per-comando" value="${esc(p.comando)}" placeholder="~/bin/resumen --corto" spellcheck="false">`, 'una línea de bash; su salida queda en el log'),
            `</div>`,
            campo('cuándo', `<input id="per-cuando" value="${esc(p.cuando)}" spellcheck="false">`
                + `<span class="presets">${presets.map(([c, n]) => `<a data-per-horario="${esc(c)}" title="${esc(c)}">${esc(n)}</a>`).join('')}</span>`
                + `<div id="per-previa" class="dim">…</div>`, 'cron: minuto hora día-del-mes mes día-de-la-semana'),
            campo('carpeta', `<input id="per-carpeta" value="${esc(p.carpeta)}" placeholder="~ (el hogar)" spellcheck="false">`, 'dónde corre; las skills de la lista son las de ahí'),
            campo('activo', `<input id="per-activo" type="checkbox"${p.activo ? ' checked' : ''}>`),
            `<div id="per-error" class="falla"></div>`,
            `<div class="acciones-t fila-botones"><a class="atajo principal" data-accion="per-guardar"><kbd>⌘⏎</kbd><span>${f.original ? 'guardar' : 'crear'}</span></a>`
            + `<a class="atajo" data-accion="per-cancelar"><kbd>⎋</kbd><span>cancelar</span></a></div>`,
            '</section></div>']);
    }

    private htmlSkills(): string {
        const f = this.formPer;
        if (!f?.skills) return '<div class="dim">leyendo las skills de allá…</div>';
        if (!f.skills.length) return '<div class="dim">no hay skills en esa carpeta</div>';
        return f.skills.map(x => `<a class="skill" data-skill="${esc(x.nombre)}" data-texto="${esc(normalizar(`${x.nombre} ${x.descripcion}`))}" title="${esc(x.descripcion)}">`
            + `<b>/${esc(x.nombre)}</b><span class="dim">${esc(x.descripcion)}</span></a>`).join('');
    }

    /** Las próximas corridas de lo que se está escribiendo, o por qué no se entiende. */
    private async previaHorario(cuando: string): Promise<void> {
        const r = await cli.periodicosHorario(cuando);
        const d = r.datos;
        const html = !d ? `<span class="falla">${esc(r.error ?? 'no contestó')}</span>`
            : !d.valido ? `<span class="falla">${esc(d.error)}</span>`
            : 'las próximas: ' + d.proximas.map(x => `<b>${esc(diaHora(x))}</b>`).join(' · ')
              + (d.proximas[0] ? ` <span class="dim">(en ${esc(enCuanto(d.proximas[0]))})</span>` : '');
        this.parcial('per-previa', html);
    }

    private async cargarSkills(carpeta: string): Promise<void> {
        const f = this.formPer;
        if (!f) return;
        if (f.skills && f.skillsDe === carpeta) return;
        f.skills = undefined;
        this.parcial('per-skills', this.htmlSkills());
        const r = await cli.periodicosSkills(carpeta);
        if (this.formPer !== f) return;
        f.skills = r.datos?.skills ?? [];
        f.skillsDe = carpeta;
        this.parcial('per-skills', r.datos ? this.htmlSkills() : `<div class="falla">${esc(r.error ?? 'no contestó')}</div>`);
    }

    /** Cambia un pedazo de la página sin repintarla: lo escrito en el formulario no se pierde. */
    private parcial(id: string, html: string): void {
        this.panel?.parcial(id, html);
    }

    private async guardarFormPer(valor: string): Promise<void> {
        const f = this.formPer;
        if (!f) return;
        const d = JSON.parse(valor) as { nombre: string; descripcion: string; tipo: string; mensaje: string; comando: string;
            hilo: string; max: string; args: string; cuando: string; carpeta: string; activo: boolean };
        const nombre = f.original || d.nombre.trim();
        const args = d.args.split('\n').map(x => x.trim()).filter(Boolean);
        const lista = [f.original ? 'editar' : 'nuevo', nombre, '--cuando', d.cuando.trim(), '--descripcion', d.descripcion.trim(),
            '--carpeta', d.carpeta.trim()];
        if (d.tipo === 'mensaje') {
            lista.push('--mensaje', d.mensaje.trim(), '--hilo', d.hilo.trim(), '--max', d.max.trim() || '1');
            if (args.length) lista.push(...args.map(a => `--arg=${a}`));
            else if (f.original) lista.push('--sin-args');
        } else {
            lista.push('--comando', d.comando.trim());
            if (f.original) lista.push('--sin-args');
        }
        if (f.original) lista.push('--activo', d.activo ? 'si' : 'no');
        else if (!d.activo) lista.push('--pausado');
        this.parcial('per-error', '<span class="dim">guardando…</span>');
        const r = await cli.periodicosOrden(lista);
        if (!r.datos) { this.parcial('per-error', esc(r.error ?? 'no se pudo')); return; }
        ui.estado(`telar: ${r.datos.hecho}`, 5000);
        this.formPer = undefined;
        this.periodico = { nombre, log: '' };
        await this.abrirPeriodicos();
        await this.verPeriodico(nombre);
    }

    /** La pestaña de un proveedor que la declara (un feed): sus ítems en una lista, con la
     *  misma ficha y las mismas flechas que «revisar». */
    private async abrirPestana(nombre: string): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'pestana';
        this.pestana = nombre;
        this.fichaDesde = `pestana:${nombre}`;
        if (!this.datos) this.datos = await dia();
        void this.precargar();   // todas las de la pestaña, mientras se abre la primera
        // la pestaña no es una lista: entra directo al primer ítem; la lista queda para cuando
        // no hay nada (o para el arnés)
        const primero = pendientes(this.datos, nombre).find(p => p.fila.ficha && !this.decididas.has(p.fila.id || p.ref));
        if (primero) { await this.abrirTarea(JSON.stringify([primero.fila.proveedor, primero.fila.id || primero.ref, primero.ref])); return; }
        this.renderPestana();
    }

    private renderPestana(): void {
        const d = this.datos;
        if (!d) return;
        this.teclas.clear();
        const lista = pendientes(d, this.pestana).filter(p => !this.decididas.has(p.fila.id || p.ref));
        const h = ['<div id="revisar">', seccion(this.pestana, 'magenta', lista.length ? String(lista.length) : '', lista.length ? pista('⏎', 'el primero') : '')];
        if (!lista.length) h.push('<div class="vacio">nada por ahora</div>');
        for (const p of lista) {
            const [palabra] = (p.fila.avance ?? '').split(' ');
            const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
            h.push(`<div class="tarea" data-accion="tarea" data-valor="${valor}" title="clic: leerlo">`
                + `<span class="id"></span><span class="pri"></span>`
                + `<span class="desc">${palabra ? `<span class="av"${p.fila.color ? ` style="color: var(--${esc(p.fila.color)})"` : ''}>${esc(palabra)}</span>` : ''}${esc(p.texto)}</span>`
                + `<span class="meta">${plazo(p.dias)}<span class="destino"></span></span></div>`);
        }
        h.push('</section></div>');
        this.pintar(h);
    }

    /** Las tareas con propuesta, en el orden del día, sin las ya decididas (salvo la abierta).
     *  Si la ficha se abrió desde una pestaña de proveedor, los ítems de esa pestaña. */
    private propuestas(desde = this.fichaDesde.startsWith('pestana:') ? this.fichaDesde.slice(8) : ''): { proveedor: string; id: string; ref: string }[] {
        if (!this.datos) return [];
        return pendientes(this.datos, desde)
            .filter(p => (desde || p.avance) && p.fila.ficha && (!this.decididas.has(p.fila.id || p.ref) || (p.fila.id || p.ref) === this.ficha?.id))
            .map(p => ({ proveedor: p.fila.proveedor, id: p.fila.id || p.ref, ref: p.ref }));
    }

    private async otraPropuesta(paso: number): Promise<boolean> {
        const lista = this.propuestas();
        const i = lista.findIndex(p => p.id === this.ficha?.id);
        const otra = lista[i < 0 ? 0 : i + paso];
        if (!otra || otra.id === this.ficha?.id) return false;
        await this.abrirTarea(JSON.stringify([otra.proveedor, otra.id, otra.ref]));
        return true;
    }

    private renderTarea(): void {
        const f = this.ficha;
        if (!f) return;
        const p = f.pagina;
        if (!p) {
            this.pintar([`<div id="ficha-tarea"><div class="subcab"><b>${esc(f.id)}</b></div>`,
                `<div class="fila falla">${esc(f.aviso ?? '')}</div></div>`]);
            return;
        }
        const lista = this.propuestas();
        const i = lista.findIndex(x => x.id === f.id);
        // «← 1/3 →»: cuál de las propuestas es y cómo pasar a otra (también con las flechas)
        const donde = i >= 0 && lista.length > 1
            ? `<span class="pasar"><a data-accion="tarea-anterior" title="la anterior (←)">←</a>`
              + `<span class="dim">${i + 1}/${lista.length}</span><a data-accion="tarea-siguiente" title="la siguiente (→)">→</a></span>` : '';
        // ⏎ es la principal; las demás van numeradas en orden, y el número es su tecla
        this.teclas.clear();
        let n = 0;
        const botones = (p.acciones ?? []).map((a, k) => {
            const tecla = a.principal ? '⏎' : String(++n);
            if (!a.principal) this.teclas.set(tecla, () => this.accionTarea(k));
            return `<a class="atajo${a.principal ? ' principal' : ''}" data-accion="accion-tarea" data-valor="${k}"`
                + ` title="${esc(a.pide ? `${a.nombre}: pide ${a.pide}` : a.nombre)}"><kbd>${tecla}</kbd><span>${esc(a.nombre)}</span></a>`;
        });
        // la ficha toma el color de la propuesta (cian cerrar, verde preparado…): botón principal incluido
        const color = p.bloques.find(b => b.destacado)?.color;
        this.pintar([`<div id="ficha-tarea"${color ? ` style="--c: var(--${esc(color)})"` : ''}>`,
            `<div class="subcab"><b>${esc(p.titulo)}</b><span class="der">${donde}</span></div>`,
            p.subtitulo ? `<div class="sub-ficha dim">${esc(p.subtitulo)}</div>` : '',
            botones.length ? `<div class="acciones-t">${botones.join('')}</div>` : '',
            ...this.htmlBloques(p.bloques), '</div>']);
    }

    private async accionTarea(k: number): Promise<void> {
        const f = this.ficha;
        const a = f?.pagina?.acciones?.[k];
        if (!f || !a) return;
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(f.ref, false, f.proveedor); return; }
        if (tipo === 'abrir') { if (a.enlace) await abrirEnlace(a.enlace); return; }
        let texto = '';
        if (a.rol === 'dueno') {
            // quién la hace: el equipo para elegir, no un campo de texto
            const quien = await elegirDueno(`${f.id} ${f.pagina?.titulo ?? ''}`.trim(), '', a.opciones ?? [], yo.persona);
            if (!quien) return;
            texto = quien;
        } else if (a.rol === 'fecha') {
            // cambiar la fecha: el selector de fechas, no un campo de texto
            const fecha = await elegirFecha(`${f.id} ${f.pagina?.titulo ?? ''}`.trim());
            if (!fecha) return;
            texto = fecha;
        } else if (a.pide) {
            const escrito = await ui.campo({ ayuda: `${f.id} · ${a.nombre}`, placeholder: a.pide });
            if (escrito === undefined) return;
            texto = escrito;
        }
        if (a.confirmar) {
            const si = await ui.aviso(`¿${a.nombre}? ${f.pagina?.titulo ?? f.id}`, 'Sí');
            if (si !== 'Sí') return;
        }
        // una acción que lleva un mensaje a un hilo (el de la tarea, Gestión) toma unos segundos: se avisa
        // con la versión de la ficha que se está mirando: si la tarea cambió desde entonces, no se hace
        const version = f.pagina?.version ?? '';
        const r = a.mensaje
            ? await ui.progreso({ titulo: `telar: ${a.nombre} · ${f.id}…` },
                () => cli.accionTarea(f.id, f.proveedor, k, texto, version))
            : await cli.accionTarea(f.id, f.proveedor, k, texto, version);
        if (!r.datos) {
            // la tarea cambió mientras se miraba: la ficha guardada ya no sirve, y se vuelve a leer
            if (/cambió desde que se leyó/.test(r.error ?? '')) this.fichas.delete(f.id);
            void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`);
            return;
        }
        // abrió un hilo (hecha y procesar ahora): se va a él, que es donde sigue el trabajo
        if (r.datos.hilo) {
            this.decididas.add(f.id);
            olvidarDia();
            void this.actualizar(true);
            await modelo.sondear();
            await ui.mostrarTerminal();
            return;
        }
        // se decidió sobre la propuesta: la siguiente, si hay; si no, se relee la ficha
        const eraPropuesta = !!f.pagina?.bloques.some(b => b.destacado);
        // la acción la cambió: la guardada ya no vale
        this.fichas.delete(`${f.proveedor}:${f.id}`);
        const releida = await cli.tarea(f.id, f.proveedor);
        if (releida.datos) this.fichas.set(`${f.proveedor}:${f.id}`, { pagina: releida.datos, hora: Date.now() });
        // en un feed, correr una acción es decidir sobre el ítem: pasa al siguiente
        const sigueViva = !this.fichaDesde.startsWith('pestana:') && !!releida.datos?.bloques.some(b => b.destacado);
        olvidarDia();
        void this.actualizar(true);
        if (eraPropuesta && !sigueViva) {
            this.decididas.add(f.id);
            if (await this.otraPropuesta(1)) return;
            // era la última: de vuelta a la lista de donde se vino, que ahora dice «nada que decidir»
            if (this.fichaDesde === 'revisar') { await this.abrirRevisar(); return; }
            if (this.fichaDesde.startsWith('pestana:')) { await this.abrirPestana(this.fichaDesde.slice(8)); return; }
        }
        if (this.pantalla === 'tarea' && this.ficha?.id === f.id) {
            this.ficha.pagina = releida.datos ?? this.ficha.pagina;
            this.renderTarea();
        }
    }

    /** Las acciones de una tarea en un menú, desde la lista: se corren sin abrir la ficha. Si después
     *  la tarea ya no tiene una propuesta esperando, se da por decidida y sale de «revisar». */
    private async menuTarea(valor: string): Promise<void> {
        const [proveedor, id, ref] = JSON.parse(valor) as string[];
        const guardada = this.fichas.get(`${proveedor}:${id}`);
        const pagina = guardada?.pagina ?? (await ui.progreso({ discreto: true, titulo: `telar: ${id}` }, () => cli.tarea(id, proveedor))).datos;
        const acciones = pagina?.acciones ?? [];
        if (!acciones.length) { void ui.aviso(`telar: ${id} no tiene acciones`); return; }
        const items = acciones.map((a, k) => ({
            label: a.nombre, k,
            description: [a.rol === 'fecha' ? 'elige la fecha' : a.pide ? `pide ${a.pide}` : '', a.confirmar ? 'pide confirmación' : '',
                a.tipo === 'hilo' ? 'abre su hilo' : a.mensaje ? 'le escribe a Claude' : ''].filter(Boolean).join(' · '),
        }));
        const elegida = await ui.elegir(items, { titulo: `${id} · ${pagina?.titulo ?? ''}`, placeholder: 'qué hacer con esta tarea' });
        if (!elegida) return;
        const a = acciones[elegida.k];
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(ref, false, proveedor); return; }
        if (tipo === 'abrir') { if (a.enlace) await abrirEnlace(a.enlace); return; }
        let texto = '';
        if (a.rol === 'fecha') {
            const fecha = await elegirFecha(`${id} ${pagina?.titulo ?? ''}`.trim());
            if (!fecha) return;
            texto = fecha;
        } else if (a.pide) {
            const escrito = await ui.campo({ ayuda: `${id} · ${a.nombre}`, placeholder: a.pide });
            if (escrito === undefined) return;
            texto = escrito;
        }
        if (a.confirmar) {
            const si = await ui.aviso(`¿${a.nombre}? ${pagina?.titulo ?? id}`, 'Sí');
            if (si !== 'Sí') return;
        }
        const r = await ui.progreso({ titulo: `telar: ${a.nombre} · ${id}…` },
            () => cli.accionTarea(id, proveedor, elegida.k, texto));
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`); return; }
        this.fichas.delete(`${proveedor}:${id}`);
        olvidarDia();
        if (r.datos.hilo) {
            this.decididas.add(id);
            void this.actualizar(true);
            await modelo.sondear();
            await ui.mostrarTerminal();
            return;
        }
        const releida = await cli.tarea(id, proveedor);
        if (releida.datos) this.fichas.set(`${proveedor}:${id}`, { pagina: releida.datos, hora: Date.now() });
        if (!releida.datos?.bloques.some(b => b.destacado)) this.decididas.add(id);
        ui.estado(`${id}: ${a.nombre}`, 5000);
        await this.actualizar(true);
        if (this.pantalla === 'revisar') this.renderRevisar();
    }

    /** Los bloques de una página (una sección, la ficha de una tarea), en HTML. */
    /** La página y la memoria de los lienzos de una página, leídas del disco (o de la API, en el navegador)
     *  antes de dibujarla: el HTML se arma sin esperar. */
    private lienzos = new Map<string, string>();
    private async precargarLienzos(bloques: cli.JsonPagina['bloques'] | undefined): Promise<void> {
        const rutas = (bloques ?? []).flatMap(b => b.lienzo ? [b.lienzo.archivo, ...(b.lienzo.memoria ? [b.lienzo.memoria] : [])] : []);
        await Promise.all(rutas.map(async r => {
            const t = await disco().leer(r);
            if (t !== undefined) this.lienzos.set(r, t); else this.lienzos.delete(r);
        }));
    }

    private htmlBloques(bloques: cli.JsonPagina['bloques']): string[] {
        const h: string[] = [];
        this.memorias.clear();   // los iframes de antes se reemplazan: sus llaves ya no valen
        bloques.forEach((b, i) => {
            if (b.lienzo) h.push(this.htmlLienzo(b.lienzo));
            if (b.marco) h.push(htmlMarco(b.marco));
            if (b.destacado) h.push(`<div class="prop" style="--c: var(--${esc(b.color ?? 'azul')})">`);
            if (b.titulo) h.push(`<h2>${esc(b.titulo)}</h2>`);
            else if (i > 0 && !b.destacado) h.push('<div class="sep-pag"></div>');
            if (b.texto) h.push(`<div class="md-pag">${mdSimple(b.texto)}</div>`);
            for (const x of b.items ?? []) {
                const clic = x.conversacion ? ` data-accion="conversacion" data-valor="${esc(x.conversacion)}"`
                    : x.hilo ? ` data-accion="ir" data-valor="${esc(x.hilo)}"`
                    : x.enlace ? ` data-accion="abrir-enlace" data-valor="${esc(x.enlace)}"` : '';
                const fecha = x.fecha ? x.fecha.slice(0, 16).replace('T', ' ').replace(' 00:00', '') : '';
                h.push(`<div class="item-pag${clic ? ' clic' : ''}"${clic}`
                    + ` title="${esc(x.conversacion ? 'clic: leer la conversación entera' : x.hilo ? `clic: ir a «${x.hilo}»` : x.enlace ? `clic: abrir ${x.enlace}` : '')}">`
                    + `<div class="fila"><b>${esc(x.titulo)}</b><span class="der dim">${esc(fecha)}</span></div>`
                    + (x.texto ? `<div class="texto-pag">${mdSimple(x.texto)}</div>` : '') + '</div>');
            }
            if (b.destacado) h.push('</div>');
        });
        return h;
    }

    private renderSeccion(): void {
        const p = this.pagina;
        if (!p) return;
        const h: string[] = [`<div class="subcab"><b>${esc(p.titulo)}</b>${p.subtitulo ? `<span class="dim">${esc(p.subtitulo)}</span>` : ''}`
            + '<span class="der">' + this.atajos.filter(a => a.en === `seccion:${this.seccion}`)
                .map(a => atajo(a.tecla, a.nombre, 'atajo', a.tecla, a.descripcion || a.mensaje)).join('')
            // los enlaces de la página (una app servida: abrirla en el navegador) van junto al ↻
            + (p.acciones ?? []).filter(a => a.tipo === 'abrir' && a.enlace)
                .map(a => `<a class="atajo" data-accion="abrir-enlace" data-valor="${esc(a.enlace!)}" title="${esc(a.enlace!)}"><span>↗</span> ${esc(a.nombre)}</a>`).join('')
            + '<a class="atajo" data-accion="recargar-seccion" title="volver a pedir la página"><span>↻</span></a>'
            + '</span></div>'];
        h.push(...this.htmlBloques(p.bloques));
        this.pintar(h);
    }

    /** Un lienzo va como `srcdoc`: su página la lee la API (es un archivo del repositorio), no se sirve. Como
     *  srcdoc no tiene query string, un script previo deja los params en la URL (`about:srcdoc?…`) y en
     *  `window.lienzo`. El sandbox sin allow-same-origin deja correr sus scripts sin alcanzar la página, y su
     *  política de contenido (POLITICA_LIENZO), sin red: lo que promete docs/contratos.md. */
    private htmlLienzo(l: cli.JsonLienzo): string {
        // lo que necesita (su página y su memoria) se leyó antes, al llegar la página (precargarLienzos)
        let doc = this.lienzos.get(l.archivo);
        if (doc === undefined) return `<div class="fila falla">no pude leer ${esc(l.archivo)}</div>`;
        const params: Record<string, string> = {};
        for (const [k, v] of Object.entries(l.params ?? {})) params[k] = String(v);
        const datos = JSON.stringify(params).replace(/</g, '\\u003c');
        // con `memoria`, el lienzo recibe lo que guardó la vez anterior y una función para guardar:
        // el iframe no tiene almacenamiento propio (sandbox sin allow-same-origin)
        let memoria = '';
        if (l.memoria) {
            const llave = llaveAlAzar();
            this.memorias.set(llave, l.memoria);
            let leida = 'null';
            try { const t = this.lienzos.get(l.memoria); if (t !== undefined) { JSON.parse(t); leida = t; } } catch { /* todavía no guardó nada */ }
            memoria = `window.lienzo.memoria=${leida.replace(/</g, '\\u003c')};window.lienzo.guardar=function(d){`
                + `parent.postMessage({lienzo:'guardar',llave:${JSON.stringify(llave)},datos:JSON.stringify(d)},'*')};`;
        }
        const previo = `<meta http-equiv="Content-Security-Policy" content="${POLITICA_LIENZO}"><script>(function(){var p=${datos};window.lienzo={params:p};${memoria}`
            + `var q=new URLSearchParams(p).toString();`
            + `if(q){try{history.replaceState(null,'','about:srcdoc?'+q)}catch(e){}}})()</script>`;
        doc = previo + doc;
        return `<iframe class="lienzo${l.alto === 'lleno' ? ' lleno' : ''}" sandbox="allow-scripts" srcdoc="${esc(doc)}"${estiloAlto(l.alto)}></iframe>`;
    }

    /** La página de una entrada del equipo (un pedido de tarea, o una sugerencia de prioridad), con lo que se puede hacer con ella. */
    async abrirEquipo(id: string): Promise<void> {
        this.abrir();
        this.pantalla = 'equipo';
        this.equipoId = id;
        this.renderEquipo();
        await modelo.leerEquipo();
        if (this.pantalla === 'equipo') this.renderEquipo();
    }

    private renderEquipo(): void {
        this.teclas.clear();
        const x = modelo.sugerencias.find(y => y.id === this.equipoId);
        const volver = '<div class="fila"><a data-accion="dia">← volver al dashboard</a></div>';
        if (!x) {
            this.pintar(['<div class="subcab"><b>Equipo</b></div>', '<div class="fila dim">esa entrada ya se resolvió, o no está.</div>', volver]);
            return;
        }
        const pedido = x.tipo === 'tarea';
        const h: string[] = [`<div class="subcab"><b>${esc(x.persona)}</b> ${pedido ? 'te pide una tarea' : 'sugiere subir una prioridad'}`
            + `<span class="der dim">${esc(fechaCorta(x.cuando))}</span></div>`];
        if (pedido) {
            h.push(`<h2>«${esc(x.titulo)}»${x.vence ? `<small>para el ${esc(x.vence)}</small>` : ''}</h2>`);
        } else {
            const nueva = x.prioridad === null ? '' : ` · hoy P${x.prioridad}, subiría a P${Math.max(0, x.prioridad - 1)}`;
            h.push(`<h2>${esc(x.tarea)} · ${esc(x.titulo)}<small>${esc(nueva.replace(/^ · /, ''))}</small></h2>`);
        }
        if (x.motivo) h.push(`<div class="md-pag"><p style="white-space:pre-wrap">${esc(x.motivo)}</p></div>`);
        if (x.revisando) h.push(`<div class="fila dim">${esc(x.revisando.quien)} la revisa desde ${esc(fechaCorta(x.revisando.desde))}: te contesta en una línea cuando decida.</div>`);
        const parecidas = x.similares ?? [];
        if (parecidas.length) {
            h.push('<h2>¿ya existe?<small>tareas tuyas que parecen lo mismo</small></h2>');
            for (const t of parecidas) {
                h.push(`<div class="item-pag"><div class="fila"><b>${esc(t.id)}</b> ${esc(t.titulo)}</div>`
                    + `<div class="fila dim">${esc(t.estado)}${t.prioridad === null ? '' : ` · P${t.prioridad}`}${t.vence ? ` · vence ${esc(t.vence)}` : ''}`
                    + `${t.avance ? ` · ${esc(t.avance)}` : ''}${t.compartida ? '' : ' · no compartida'}</div>`
                    + `<div class="fila"><a data-accion="equipo-accion" data-valor="${esc(`existe|${x.id}|${t.id}`)}" title="no se agrega nada: ${esc(x.persona)} recibe el estado de esa tarea">es esta: contestarle su estado</a></div></div>`);
            }
        }
        const botones: [string, string, string, string][] = [
            ['1', x.revisando ? 'preguntarle de nuevo a Gestión' : 'preguntarle a Gestión', `gestion|${x.id}`, 'Gestión revisa si ya existe y decide: nueva, actualizar una existente o no corresponde'],
            ...(pedido ? [['2', 'agregar como tarea', `aceptar|${x.id}`, 'P2, etiquetada equipo' + (x.vence ? `, para el ${x.vence}` : '')] as [string, string, string, string]]
                : [['2', `subir la prioridad de ${x.tarea}`, `aceptar|${x.id}`, 'un nivel, con el CLI de tareas'] as [string, string, string, string]]),
            ['3', pedido ? 'descartar' : 'rechazar', `rechazar|${x.id}`, `puedes dejarle una nota a ${x.persona}`],
        ];
        h.push('<h2>qué hacer</h2><div class="acciones-t fila-botones">' + botones.map(([k, n, v, t]) => atajo(k, n, 'equipo-accion', v, t)).join('') + '</div>');
        for (const [k, , v] of botones) this.teclas.set(k, () => this.accionEquipo(v));
        h.push(volver);
        this.pintar(h);
    }

    private async accionEquipo(valor: string): Promise<void> {
        const [verbo, id, tarea = ''] = valor.split('|');
        const x = modelo.sugerencias.find(y => y.id === id);
        if (!x) return;
        if (verbo === 'gestion') await preguntarAGestion(x);
        else await decidir(x, verbo as 'aceptar' | 'rechazar' | 'existe', tarea);
        if (this.pantalla === 'equipo') this.renderEquipo();
    }

    /** Los mensajes entre hilos, por el bus: lo que se dijeron y lo retenido. */
    private async abrirCorreo(): Promise<void> {
        this.pantalla = 'correo';
        this.pintar(['<div class="subcab"><b>Mensajes entre hilos</b></div>', '<div class="fila dim">leyendo…</div>']);
        const bus = await cli.mensajesBus();
        if (this.pantalla !== 'correo') return;
        this.mensajesBus = bus.datos?.mensajes;
        if (!this.mensajesBus) {
            this.pintar(['<div class="subcab"><b>Mensajes entre hilos</b></div>',
                `<div class="fila falla">${esc(bus.error ?? 'no pude leer el registro del bus')}</div>`]);
            return;
        }
        this.renderCorreo();
    }

    private renderCorreo(): void {
        const h: string[] = ['<div class="subcab"><b>Mensajes entre hilos</b>'
            + '<span class="der dim"><a data-accion="correo" title="volver a leer">↻</a></span></div>'];
        if (this.mensajesBus) h.push(...this.htmlMensajesBus(this.mensajesBus));
        this.pintar(h);
    }

    /** Lo que se dijeron los hilos por el bus, lo más nuevo arriba. Lo retenido (cadena larga,
     *  demasiados por hora) espera aquí a que la persona lo suelte. */
    private htmlMensajesBus(lista: cli.JsonMensajeBus[]): string[] {
        const soltados = new Set(lista.filter(m => m.estado !== 'retenido').map(m => m.id));
        const retenidos = lista.filter(m => m.estado === 'retenido' && !soltados.has(m.id));
        const h = [`<h2>entre hilos<small>por el bus · ${lista.length} último${lista.length === 1 ? '' : 's'}`
            + `${retenidos.length ? ` · ${retenidos.length} retenido${retenidos.length === 1 ? '' : 's'}` : ''}</small></h2>`];
        if (!lista.length) h.push('<div class="fila dim">nada todavía</div>');
        const fila = (m: cli.JsonMensajeBus, retenido: boolean) => {
            const abierto = this.abiertoMsg.has(m.id);
            const texto = abierto ? m.texto : m.texto.split(/\s+/).join(' ').slice(0, 140);
            return `<div class="item-pag clic" data-accion="ver-msg" data-valor="${esc(m.id)}" title="clic: ${abierto ? 'acortar' : 'el texto entero'}">`
                + `<div class="fila">${retenido ? '<span class="falla">⏸ </span>' : ''}<b>${esc(m.de)}</b><span class="dim"> → </span><b>${esc(m.para)}</b>`
                + `<span class="dim"> · ${esc(m.tipo)}${m.saltos ? ` · salto ${m.saltos}` : ''}</span>`
                + `<span class="der dim">${esc(fechaCorta(m.creado))}`
                + (retenido ? ` · <a data-accion="soltar-msg" data-valor="${esc(m.id)}" title="mandarlo igual: lo decides tú">soltar</a>` : '')
                + '</span></div>'
                + (retenido && m.motivo ? `<div class="fila falla">${esc(m.motivo)}</div>` : '')
                + `<div class="fila${abierto ? '' : ' dim'}" style="white-space:pre-wrap">${esc(texto)}</div></div>`;
        };
        for (const m of retenidos) h.push(fila(m, true));
        for (const m of [...lista].reverse()) if (m.estado !== 'retenido') h.push(fila(m, false));
        return h;
    }

    private async soltarMensaje(id: string): Promise<void> {
        const r = await cli.soltarMensaje(id);
        if (!r.datos) { void ui.falla(`telar: no se soltó: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: soltado, en la casilla de «${r.datos.para}»`, 4000);
        await this.abrirCorreo();
    }

    /** Una conversación entera: lo que se dijo, y una línea por herramienta. */
    private async abrirConversacion(id: string): Promise<void> {
        this.pantalla = 'conversacion';
        this.pintar(['<div class="fila dim">leyendo la conversación…</div>']);
        const r = await cli.conversacion(id);
        if (this.pantalla !== 'conversacion') return;
        if (!r.datos) {
            this.pintar([`<div class="fila falla">${esc(r.error ?? 'no pude leerla')}</div>`,
                '<div class="fila"><a data-accion="volver-seccion">← volver</a></div>']);
            return;
        }
        this.charla = r.datos;
        const c = r.datos;
        const hilo = c.hilo && modelo.porNombre(c.hilo);
        const h: string[] = [`<div class="subcab"><b>Conversación</b><span class="dim">${esc(c.conversacion.slice(0, 8))}`
            + `${c.hilo ? ` · ${esc(c.hilo)}` : ''} · ${c.mensajes.length} mensajes</span>`
            + '<span class="der dim">'
            + (hilo ? `<a data-accion="retomar-charla" title="volver a esta conversación en su hilo">▶ retomar</a> · ` : '')
            + (this.seccion ? '<a data-accion="volver-seccion">← ' + esc(modelo.secciones.find(x => x.clave === this.seccion)?.nombre ?? 'volver') + '</a>' : '')
            + '</span></div>'];
        for (const m of c.mensajes) {
            const hora = m.hora ? horaLocal(m.hora) : '';
            if (m.quien === 'herramienta') {
                h.push(`<div class="herr dim">› ${esc(m.texto)}</div>`);
            } else {
                h.push(`<div class="msg ${m.quien}"><div class="quien">${m.quien === 'usuario' ? 'tú' : 'agente'}`
                    + `<span class="dim"> ${esc(hora)}</span></div><div class="md-pag">${mdSimple(m.texto)}</div></div>`);
            }
        }
        this.pintar(h);
    }


    /** Un hilo con el agente preparando la reunión, y el teclado ahí. Lo que se le dice
     *  al agente lo decide `[agente] reunion` en la configuración de telar, no la página. */
    private async preparar(titulo: string, hora: string, enlace: string, evento = '', asistentes: string[] = []): Promise<void> {
        const pedir = (opciones: { proyecto?: string; preguntar?: boolean }) => ui.progreso({ titulo: `telar: ${titulo}…` },
            () => cli.reunion(titulo, hora, enlace, evento, { asistentes, ...opciones }));
        let r = await pedir({ preguntar: true });
        if (r.datos?.hecho === 'preguntar') {
            const eleccion = await this.elegirProyecto(titulo, hora, r.datos);
            if (!eleccion) return;
            r = await pedir({ proyecto: eleccion });
        }
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir la reunión'}`);
            return;
        }
        void ui.estado(`telar: «${titulo}» → ${r.datos.hilo}: ${r.datos.hecho}`, 6000);
        await modelo.sondear();
        await ui.mostrarTerminal();
    }

    /** De qué proyecto es una reunión que no se pudo deducir: los sugeridos con su porqué, Gestión
     *  siempre, un proyecto nuevo con su nombre, y todos los proyectos para buscar. La elección se
     *  recuerda para la serie (`telar reunion --proyecto`). */
    private async elegirProyecto(titulo: string, hora: string, r: cli.JsonReunion): Promise<string | undefined> {
        type Item = Opcion & { valor?: string };
        const sep = (label: string): Item => ({ label, separador: true });
        const items: Item[] = [];
        const sugeridos = r.candidatos ?? [];
        if (sugeridos.length) {
            items.push(sep('sugeridos'));
            for (const c of sugeridos) items.push({ label: c.nombre, description: c.ruta, detail: c.motivos.join(' · '), valor: c.ruta });
        }
        items.push(sep('otros destinos'));
        items.push({ label: r.gestion || 'Gestión', description: 'el agente de lo que no tiene proyecto', valor: 'gestion' });
        items.push({ label: 'Proyecto nuevo…', description: 'se le pide al agente crearlo con su nombre', valor: 'nuevo' });
        const todos = await cli.proyectos();
        if (todos.datos) {
            items.push(sep('todos los proyectos'));
            const vistos = new Set(sugeridos.map(c => c.ruta));
            const lista = [...todos.datos.proyectos].filter(x => !vistos.has(x.ruta) && !esServicio(x))
                .sort((a, b) => (b.modificado ?? '').localeCompare(a.modificado ?? ''));
            for (const x of lista) items.push({ label: x.nombre, description: `${x.ruta} · ${x.arquetipo}`, valor: x.ruta });
        }
        const elegido = await ui.elegir(items, {
            titulo: `¿De qué proyecto es «${titulo}» (${hora})?`,
            placeholder: 'escribe para buscar un proyecto; la elección se recuerda para esta reunión',
        });
        if (!elegido?.valor) return undefined;
        if (elegido.valor !== 'nuevo') return elegido.valor;
        const nombre = await ui.campo({ titulo: 'Proyecto nuevo', ayuda: 'El nombre del proyecto' });
        return nombre?.trim() ? `nuevo:${nombre.trim()}` : undefined;
    }

    /** La pantalla de proyectos. La lista se pide cada vez que se entra: es barata (medio
     *  segundo con 179 unidades) y así un proyecto recién creado aparece sin recargar. */
    private async abrirProyectos(): Promise<void> {
        this.pantalla = 'proyectos';
        this.avisoProyectos = '';
        this.pendRepo = undefined;
        if (!this.proyectos) this.renderProyectos('leyendo los proyectos…');
        // los pendientes de los documentos se piden en paralelo: la lista no los espera
        const repo = cli.pendientesRepo().then(r => {
            this.pendRepo = r.datos?.pendientes ?? [];
            this.pendRepoAviso = r.datos ? '' : (r.error ?? 'telar pendientes no contestó');
            if (this.pantalla !== 'proyectos') return;
            // la lista ya está pintada: solo se le dan las cuentas, para filtrar «con pendientes»
            const cuentas = this.cuentasPendientes();
            if (cuentas) this.panel?.cuentasProyectos(Object.fromEntries(cuentas));
            if (this.proySel) void this.verProyecto(this.proySel, false);
        });
        const r = await cli.proyectos();
        if (r.datos) this.proyectos = r.datos.proyectos;
        else this.avisoProyectos = r.error ?? 'telar proyectos no contestó';
        if (this.proySel && !this.proyectos?.some(p => p.ruta === this.proySel)) { this.proySel = ''; this.proyDet = undefined; }
        if (this.pantalla === 'proyectos') this.renderProyectos();
        if (this.proySel) void this.verProyecto(this.proySel);
        await repo;
    }

    /** Los pendientes de un proyecto: las viñetas de su documento y las tareas de un proveedor que
     *  dicen ser de esa carpeta (o de algo adentro). null mientras se leen los del documento. */
    private pendientesDe(ruta: string): ReturnType<typeof pendientes> | null {
        const filas = this.filasPorProyecto()?.get(ruta);
        if (!filas) return this.pendRepo ? [] : null;
        return pendientes({ ...(this.datos ?? { fecha: '' }), pendientes: filas } as Dia);
    }

    /** Las filas pendientes de cada proyecto: las viñetas de su documento, y cada tarea de un
     *  proveedor en el proyecto más hondo que contiene la carpeta que dice ser suya. */
    private filasPorProyecto(): Map<string, cli.JsonFila[]> | null {
        if (!this.pendRepo) return null;
        const rutas = (this.proyectos ?? []).map(p => p.ruta);
        const m = new Map<string, cli.JsonFila[]>();
        const sumar = (r: string, f: cli.JsonFila) => { if (r) m.set(r, [...(m.get(r) ?? []), f]); };
        for (const f of this.pendRepo) if (!f.proveedor && !f.hecho) sumar(f.ruta, f);
        for (const f of this.datos?.pendientes ?? []) {
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
    private async verProyecto(ruta: string, releer = true): Promise<void> {
        const p = this.proyectos?.find(x => x.ruta === ruta);
        if (!p || !this.panel) return;
        this.proySel = ruta;
        const previo = this.proyDet?.p.ruta === ruta ? this.proyDet.readme : null;
        this.proyDet = { p, pendientes: this.pendientesDe(ruta), aviso: this.pendRepoAviso, readme: releer ? null : previo };
        this.pintarDetalleProyecto();
        if (!releer && previo !== null) return;
        const readme = await this.readmeHtml(ruta);
        if (this.proySel !== ruta || !this.proyDet) return;
        this.proyDet.readme = readme;
        this.pintarDetalleProyecto();
    }

    private pintarDetalleProyecto(): void {
        this.panel?.parcial('proy-det', htmlDetalleProyecto(this.proyDet));
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
    private personas?: string[];
    private async personasConocidas(): Promise<string[]> {
        if (!this.personas) {
            const unaTarea = this.datos?.pendientes.find(f => f.ficha && f.proveedor);
            const ficha = unaTarea ? await cli.tarea(unaTarea.id || unaTarea.ref, unaTarea.proveedor) : undefined;
            this.personas = ficha?.datos?.acciones?.find(a => a.rol === 'dueno')?.opciones ?? [];
        }
        const vistos = [...(this.datos?.pendientes ?? []), ...(this.pendRepo ?? [])].map(f => f.dueno ?? '').filter(Boolean);
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
            await this.actualizar(true);
            if (this.pantalla === 'revisar') this.renderRevisar();
            else if (this.pantalla === 'proyectos') await this.abrirProyectos();
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

    // ── ahora ──────────────────────────────────────────────────────────────────

    /** La pantalla «ahora»: el bloque que toca y lo que conviene mirar en él (ver `vistas/ahora.ts`). */
    private async abrirAhora(): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'ahora';
        if (!this.datos) this.datos = await dia();
        this.renderAhora();
        // lo que hace falta para el contexto: el plan de hoy, los proyectos y sus pendientes
        const [plan, proys, repo] = await Promise.all([
            this.plan?.dia === this.datos?.fecha ? Promise.resolve(undefined) : cli.resultado('plan', ''),
            this.proyectos ? Promise.resolve(undefined) : cli.proyectos(),
            this.pendRepo ? Promise.resolve(undefined) : cli.pendientesRepo(),
        ]);
        if (plan?.datos?.ok) this.plan = plan.datos;
        if (proys?.datos) this.proyectos = proys.datos.proyectos;
        if (repo?.datos) this.pendRepo = repo.datos.pendientes;
        this.ahoraCtx.clear();
        if (this.pantalla === 'ahora') this.renderAhora();
    }

    /** El día que se mira: hoy, o el del momento simulado (con su calendario y su plan). */
    private diaAhora(): { d?: Dia; plan?: Record<string, unknown> } {
        if (this.ahoraSim !== undefined && this.ahoraDia) return { d: this.ahoraDia, plan: this.ahoraPlan };
        const d = this.datos;
        const plan = d && this.plan?.dia === d.fecha && this.plan.formato === 'json' ? this.plan.contenido as Record<string, unknown> : undefined;
        return { d, plan };
    }

    private eventosAhora(): EventoCal[] {
        const { d, plan } = this.diaAhora();
        return d ? eventosDelDia(d, plan) : [];
    }

    /** El índice del bloque que se mira en `evs`: el elegido, o el que toca a esa hora. Sobre la misma
     *  lista que se dibuja: `eventosDelDia` arma objetos nuevos cada vez, y buscar uno de una lista en
     *  otra no lo encuentra nunca (la vista quedaba en «nada en el calendario»). */
    private indiceAhora(evs: EventoCal[]): number {
        const i = this.ahoraSel ? evs.findIndex(e => e.id === this.ahoraSel) : -1;
        return i >= 0 ? i : bloqueActual(evs, this.ahoraSim ?? Date.now());
    }

    private eventoAhora(): EventoCal | undefined {
        const evs = this.eventosAhora();
        return evs[this.indiceAhora(evs)];
    }

    /** Un bloque elegido en el calendario desplegado: «ahora» pasa a su comienzo y se lo mira a él. */
    private ahoraAlEvento(id: string): void {
        const e = this.eventosAhora().find(x => x.id === id);
        if (!e) return;
        this.ahoraSim = e.inicio + 60000;
        this.ahoraSel = e.id;
        this.ahoraElegir = false;
        this.renderAhora();
    }

    /** ‹ › del calendario desplegado: otro día, a la misma hora (con su calendario y su plan). */
    private async ahoraOtroDia(paso: number): Promise<void> {
        const base = new Date(this.ahoraSim ?? Date.now());
        base.setDate(base.getDate() + paso);
        const local = new Date(base.getTime() - base.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        await this.simularAhora(local);
    }

    /** Mover «ahora» a otro momento (`AAAA-MM-DDTHH:MM`): qué mostraría entonces. Otro día trae su
     *  calendario y su plan; el mismo día de hoy usa lo que ya hay. */
    private async simularAhora(valor: string): Promise<void> {
        const ms = Date.parse(valor);
        if (Number.isNaN(ms)) return;
        this.ahoraSim = ms;
        this.ahoraSel = '';
        this.ahoraFijo = false;
        const fecha = valor.slice(0, 10);
        if (fecha === this.datos?.fecha) { this.ahoraDia = undefined; this.ahoraPlan = undefined; this.renderAhora(); return; }
        this.ahoraDiaCargando = true;
        this.renderAhora();
        const [d, plan] = await Promise.all([diaDe(fecha), cli.resultado('plan', fecha)]);
        if (this.ahoraSim !== ms) return;  // se eligió otro momento mientras tanto
        this.ahoraDia = d;
        this.ahoraPlan = plan.datos?.ok && plan.datos.formato === 'json' ? plan.datos.contenido as Record<string, unknown> : undefined;
        this.ahoraDiaCargando = false;
        if (this.pantalla === 'ahora') this.renderAhora();
    }

    /** ‹ ›: moverse a otro bloque deja la vista fija ahí hasta «volver a ahora». */
    private moverAhora(paso: number): void {
        const evs = this.eventosAhora();
        const actual = this.eventoAhora();
        const i = Math.max(0, Math.min(evs.length - 1, evs.findIndex(e => e.id === actual?.id) + paso));
        this.ahoraSel = evs[i]?.id ?? '';
        this.ahoraFijo = true;
        this.renderAhora();
    }

    private renderAhora(): void {
        const d = this.datos;
        if (!this.panel || !d) return;
        this.teclas.clear();
        this.teclas.set('[', () => this.moverAhora(-1));
        this.teclas.set(']', () => this.moverAhora(1));
        // lo elegido se mantiene si está fijo o si se está simulando otro momento; si no, manda el reloj
        if (!this.ahoraFijo && this.ahoraSim === undefined) this.ahoraSel = '';
        const evs = this.eventosAhora();
        const i = evs.length ? this.indiceAhora(evs) : -1;
        const e = i >= 0 ? evs[i] : undefined;
        const { d: diaVisto, plan } = this.diaAhora();
        const momento = new Date(this.ahoraSim ?? Date.now());
        const ctx = e ? this.ahoraCtx.get(e.id) : undefined;
        if (e && !ctx && this.ahoraCargando !== e.id) void this.cargarContexto(e, plan);
        const todas = pendientes(d);
        this.pintar(htmlAhora({
            evs, i, ahora: this.ahoraSim ?? Date.now(), fijo: this.ahoraFijo, plan, contexto: ctx, cargando: !!e && !ctx,
            simulado: this.ahoraSim !== undefined, cargandoDia: this.ahoraDiaCargando,
            elegir: this.ahoraElegir && diaVisto ? columnaCalendario(diaVisto, evs, e?.id ?? '', momento, undefined, 'ahora-evento') : undefined,
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
        this.ahoraCargando = e.id;
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
            if (!ruta && clase !== 'reunion' && this.proyectos) ruta = proyectoDelTitulo(e.titulo, this.proyectos.filter(p => !esServicio(p)));
            ctx.proyecto = this.proyectos?.find(x => x.ruta === ruta);
            const ids = new Set(((p.tareas ?? []) as string[]).map(String));
            if (ids.size && this.datos) {
                ctx.tareas = pendientes({ ...this.datos, pendientes: this.datos.pendientes.filter(f => ids.has(f.id)) } as Dia);
            }
            if (ctx.proyecto && modelo.raiz) {
                const carpeta = rutas.unir(modelo.raiz, ctx.proyecto.ruta);
                ctx.pendientes = this.pendientesDe(ctx.proyecto.ruta) ?? [];
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
        this.ahoraCtx.set(e.id, ctx);
        this.ahoraCargando = '';
        if (this.pantalla === 'ahora') this.renderAhora();
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

    /** Pedirle al agente general que consolide los pendientes del README de un proyecto (`/consolidar`):
     *  que marque hecho, con su prueba, lo que ya se hizo. Corre donde vive el agente (el servidor). */
    private async consolidarProyecto(ruta: string): Promise<void> {
        const p = this.proyectos?.find(x => x.ruta === ruta);
        if (!this.general) { void ui.aviso('telar: no hay un agente general ([agentes] sin_proyecto) que lo haga'); return; }
        const n = this.pendientesDe(ruta)?.filter(t => !t.fila.proveedor).length;
        const si = await ui.info(
            `¿Consolidar los pendientes de «${p?.nombre ?? ruta}»?`,
            { detalle: `${this.general.nombre} revisa ${n ?? 'cada'} pendiente${n === 1 ? '' : 's'} abierto${n === 1 ? '' : 's'} del README, busca si ya se hizo y marca lo hecho con su prueba. Lo dudoso te lo pregunta.` },
            'Consolidar');
        if (si !== 'Consolidar') return;
        const r = await ui.progreso({ titulo: `telar: encargándoselo a ${this.general.nombre}…` },
            () => cli.encargar(this.general!.clave, `/consolidar ${ruta}`));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${this.general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: ${this.general.nombre} consolida ${p?.nombre ?? ruta} (${r.datos.estado ?? ''})`, 8000);
    }

    /** El ⋯ de un proyecto: lo que se puede hacer con él sin abrirlo. */
    private async menuProyecto(ruta: string): Promise<void> {
        const p = this.proyectos?.find(x => x.ruta === ruta);
        if (!p) return;
        const carpeta = modelo.raiz ? rutas.unir(modelo.raiz, ruta) : '';
        type Item = Opcion & { hacer: () => Promise<unknown> | unknown };
        const items: Item[] = [
            { label: p.vivo ? 'Ir a su hilo' : p.hilo ? 'Retomar su hilo' : 'Abrir con el agente',
              description: p.hilo ? `«${p.hilo}»` : 'un hilo nuevo cargando el proyecto', hacer: () => this.abrirProyecto(ruta) },
        ];
        if (this.general) {
            items.push({ label: 'Consolidar sus pendientes', description: `${this.general.nombre} marca lo hecho con su prueba (/consolidar)`,
                         hacer: () => this.consolidarProyecto(ruta) });
            items.push({ label: `Escribirle a ${this.general.nombre} sobre este proyecto…`, description: 'le llega con el proyecto y lo pendiente',
                         hacer: () => this.escribirSobreProyecto(p) });
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
                await this.abrirProyectos();
            } });
        }
        const elegida = await ui.elegir(items, { titulo: p.nombre, placeholder: 'qué hacer con este proyecto' });
        if (elegida) await elegida.hacer();
    }

    /** Lo que la persona le escribe al agente general sobre un proyecto, con lo que necesita para no
     *  preguntar: cuál es, dónde está, en qué estado, y lo pendiente. */
    private async escribirSobreProyecto(p: cli.JsonProyecto): Promise<void> {
        if (!this.general) return;
        const texto = await ui.campo({ titulo: `A ${this.general.nombre} · ${p.nombre}`, ayuda: 'qué hacer con este proyecto' });
        if (!texto?.trim()) return;
        const pend = this.pendientesDe(p.ruta) ?? [];
        const lineas = [
            `[Nico, desde los proyectos del dashboard] ${texto.trim()}`,
            '',
            `Contexto. El proyecto: «${p.nombre}» (${p.arquetipo}${p.estado_completo ? `, estado: ${p.estado_completo}` : ''}), en ${p.ruta}; su README es ${p.ruta}/README.md.`,
            p.hilo ? `Tiene un hilo: «${p.hilo}»${p.vivo ? ' (abierto)' : ' (dormido)'}; si el trabajo es suyo, pásaselo con telar mensaje.` : 'No tiene hilo abierto.',
            pend.length ? `Pendiente: ${pend.slice(0, 12).map(t => `${t.fila.proveedor ? `${t.ref} ` : ''}${t.texto}`).join(' | ')}` : '',
        ].filter(Boolean);
        const r = await ui.progreso({ titulo: `telar: escribiéndole a ${this.general.nombre}…` },
            () => cli.encargar(this.general!.clave, lineas.join('\n')));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${this.general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: enviado a ${this.general.nombre} (${r.datos.estado ?? ''})`, 6000);
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
     *  volver por cada letra. Ver `aplicarProyectos` en vistas/dashboard.ts. */
    private renderProyectos(cargando = ''): void {
        if (!this.panel) return;
        this.teclas.clear();
        // sin los servicios: no son proyectos (sí se usan para decir de qué es una tarea)
        const lista = (this.proyectos ?? []).filter(p => !esServicio(p));
        const h: string[] = [`<div class="subcab"><b>Proyectos</b><span class="dim">${lista.length || ''}</span>`
            + '</div>'];
        if (this.avisoProyectos) h.push(`<div class="fila falla">${esc(this.avisoProyectos)}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.pintar(h); return; }
        h.push('<div class="proy-dos"><div class="proy-lista">', ...htmlListaProyectos(lista, this.proySel, this.cuentasPendientes()),
            `</div><div id="proy-det">${htmlDetalleProyecto(this.proySel ? this.proyDet : undefined)}</div></div>`);
        this.pintar(h);
    }

    /** Un hilo con el agente cargando el proyecto, o el que ya había; y el teclado ahí. Lo
     *  que se le dice al agente lo decide `[agente] proyecto`, no la página. */
    private async abrirProyecto(ruta: string): Promise<void> {
        const r = await cli.abrirProyecto(ruta);
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir el proyecto'}`);
            return;
        }
        await modelo.sondear();
        await ui.mostrarTerminal();
    }

    private async cambiarPlantillaProyecto(restablecer: boolean): Promise<void> {
        let texto = '';
        if (!restablecer) {
            const actual = this.agenteConfig?.proyecto ?? '';
            const nuevo = await ui.campo({
                titulo: 'Qué decirle al agente al abrir un proyecto',
                ayuda: 'Marcadores: {nombre} {ruta} {carpeta} {documento}. Una skill (/nombre …) o una instrucción en prosa.',
                valor: actual,
            });
            if (nuevo === undefined || nuevo.trim() === actual) return;
            texto = nuevo.trim();
        }
        const r = await cli.plantillaProyecto(texto);
        if (!r.ok) this.avisoConfig = r.err.trim().split('\n').pop() || 'no pude guardar el mensaje';
        await this.abrirConfig();
    }

    private async abrirConfig(): Promise<void> {
        this.pantalla = 'config';
        this.avisoConfig = '';
        this.renderConfig('leyendo la configuración…');
        const r = await cli.config();
        this.calendario = r.datos?.calendario;
        this.agenteConfig = r.datos?.agente;
        this.hilosConfig = r.datos?.hilos;
        if (!r.datos) this.avisoConfig = r.error ?? 'telar config no contestó';
        this.renderConfig();
    }

    private async elegirCalendario(valor: string): Promise<void> {
        if (valor === 'ics') {
            await ui.orden('telar.conectarCalendario');
        } else {
            const r = await cli.elegirCalendario(valor);
            if (!r.ok) {
                this.avisoConfig = r.err.trim().split('\n').pop() || 'no pude cambiar el calendario';
                this.renderConfig();
                return;
            }
        }
        olvidarDia();
        await this.abrirConfig();
        await this.actualizar(true);
        this.renderConfig();
    }

    private async cambiarDirectorios(): Promise<void> {
        const actual = (this.hilosConfig?.directorios ?? []).join(', ');
        const nuevo = await ui.campo({
            titulo: 'De qué carpetas salen los hilos',
            ayuda: 'Relativas a la raíz del repositorio, separadas por coma, en el orden en que se abren. Vacío: las unidades del perfil.',
            placeholder: 'operacion/proyectos, negocio/pipeline',
            valor: actual,
        });
        if (nuevo === undefined || nuevo.trim() === actual) return;
        const r = await cli.directoriosHilos(nuevo.trim());
        if (!r.ok) {
            this.avisoConfig = r.err.trim().split('\n').pop() || 'no pude guardar las carpetas';
            await this.abrirConfig();
            return;
        }
        await this.abrirConfig();
        // cada hilo abre un agente: se ofrece, no se hace
        const si = await ui.info(
            'Carpetas guardadas. ¿Abrir ahora los hilos que falten? Cada uno arranca su agente.', 'Abrir ahora');
        if (si === 'Abrir ahora') {
            const t = await cli.tejer(true);
            if (!t.ok) void ui.aviso(`telar: ${t.err.trim().split('\n').pop() ?? 'no pude abrirlos'}`);
            await modelo.sondear();
        }
    }

    private async cambiarPlantilla(restablecer: boolean): Promise<void> {
        let texto = '';
        if (!restablecer) {
            const actual = this.agenteConfig?.reunion ?? '';
            const nuevo = await ui.campo({
                titulo: 'Qué decirle al agente al preparar una reunión',
                ayuda: 'Marcadores: {titulo} {hora} {fecha} {enlace} {proyecto}. Una skill (/nombre …) o una instrucción en prosa.',
                valor: actual,
            });
            if (nuevo === undefined || nuevo.trim() === actual) return;
            texto = nuevo.trim();
        }
        const r = await cli.plantillaReunion(texto);
        if (!r.ok) this.avisoConfig = r.err.trim().split('\n').pop() || 'no pude guardar el mensaje';
        await this.abrirConfig();
    }

    /** La pantalla de configuración: de dónde sale la agenda, si funciona, y las otras opciones. */
    /** En ⚙: cada pestaña con ✓ si se ve, y ↑↓ para moverla; debajo, los módulos instalados. */
    private htmlPestanasConfig(): string[] {
        const todas = this.todasLasPestanas();
        const pos = (c: string) => { const i = this.dashOrden.indexOf(c); return i < 0 ? this.dashOrden.length + todas.findIndex(x => x[0] === c) : i; };
        const h = ['<h2>Pestañas<small>cuáles se ven y en qué orden; las de un módulo nuevo aparecen solas</small></h2>'];
        [...todas].sort((a, b) => pos(a[0]) - pos(b[0])).forEach(([clave, , , nombre]) => {
            const ve = !this.dashOcultas.includes(clave);
            const modulo = clave.startsWith('bloque:') && this.modulosCfg?.some(m => m.nombre === clave.slice(7)) ? ' <span class="dim">· módulo</span>' : '';
            h.push(`<div class="fila${ve ? '' : ' dim'}"><a data-accion="pest-ver" data-valor="${esc(clave)}" title="${ve ? 'ocultarla' : 'mostrarla'}">${ve ? '✓' : '·'}</a> `
                + `${esc(nombre.replace(/ ◆\d+$/, ''))}${modulo}<span class="der">`
                + `<a data-accion="pest-subir" data-valor="${esc(clave)}" title="un lugar antes">↑</a> `
                + `<a data-accion="pest-bajar" data-valor="${esc(clave)}" title="un lugar después">↓</a></span></div>`);
        });
        h.push('<div class="fila dim">⚙ va siempre al final.</div>');
        h.push('<h2>Módulos<small>una carpeta con modulo.toml; se instalan en <code>[modulos]</code> de la configuración</small></h2>');
        if (!this.modulosCfg?.length) h.push('<div class="fila dim">ninguno instalado</div>');
        for (const m of this.modulosCfg ?? []) {
            h.push(`<div class="fila"><b>${esc(m.nombre)}</b>&nbsp;<span class="dim">${esc(m.descripcion)}</span></div>`
                + `<div class="fila dim">aporta ${esc(m.aporta.join(', ') || 'nada')} · ${esc(m.carpeta)}</div>`);
        }
        return h;
    }

    private renderConfig(cargando = ''): void {
        if (!this.panel) return;
        this.teclas.clear();
        const h: string[] = ['<div class="subcab"><b>Configuración</b>'
            + '</div>'];
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.pintar(h); return; }
        if (this.avisoConfig) h.push(`<div class="fila falla">${esc(this.avisoConfig)}</div>`);
        h.push(...this.htmlPestanasConfig());
        const c = this.calendario;
        h.push('<h2>Calendario<small>de dónde sale la agenda</small></h2>');
        if (!c) { this.pintar(h); return; }

        const falla = this.datos?.fallas.find(f => f.startsWith('calendario'));
        const estado = c.tipo === 'ninguno' ? 'sin conectar'
            : falla ? `no responde (${falla.split(': ').pop()})`
            : this.datos?.agenda ? 'funcionando' : 'todavía sin consultar';
        const nombre: Record<string, string> = { gws: 'Google Workspace (gws)', ics: 'iCal', comando: 'un comando', ninguno: 'ninguno' };
        h.push(`<div class="fila">En uso: <b>${esc(nombre[c.tipo] ?? c.tipo)}</b> · `
            + `<span class="${falla ? 'falla' : 'dim'}">${esc(estado)}</span></div>`);

        const opcion = (tipo: string, titulo: string, boton: string, lineas: string[]) => {
            const activa = c.tipo === tipo;
            h.push(`<div class="opcion${activa ? ' activa' : ''}"><div class="fila"><b>${activa ? '●' : '○'} ${titulo}</b>`
                + (activa && tipo !== 'ics' ? '' : ` <span class="der"><a data-accion="calendario" data-valor="${tipo}">${boton}</a></span>`)
                + '</div>' + lineas.map(l => `<div class="fila dim">${l}</div>`).join('') + '</div>');
        };
        opcion('gws', 'Google Workspace (gws)', 'usar', [
            'Lee tu calendario con la CLI <code>gws</code>, con la cuenta que ya tenga conectada. '
                + 'No hay dirección que pegar ni secreto que guardar, y sirve aunque el administrador del dominio haya desactivado iCal.',
            !c.gws ? 'No está instalado en esta máquina.'
                : c.gws_conectado ? `Conectado como <b>${esc(c.gws_cuenta || 'una cuenta')}</b>.`
                : 'Instalado pero sin sesión: corre <code>gws auth login</code> en un terminal.',
        ]);
        opcion('ics', 'iCal', c.tipo === 'ics' ? 'cambiar dirección…' : 'usar…', [
            'Una dirección de calendario en formato .ics. En Google Calendar: Configuración › tu calendario › '
                + '«Dirección <b>secreta</b> en formato iCal».',
            ...(c.tipo === 'ics' && c.fuente ? [`Guardada: <code>${esc(c.fuente)}</code> (la parte secreta no se muestra).`] : []),
            ...(c.tipo === 'ics' && c.publica ? ['<span class="falla">Es la dirección <b>pública</b>: solo funciona si el calendario '
                + 'está publicado para todo internet. Usa la secreta.</span>'] : []),
        ]);
        opcion('ninguno', 'Ninguno', 'desconectar', ['El dashboard no muestra agenda.']);

        const hc = this.hilosConfig;
        if (hc) {
            h.push('<h2>Hilos<small>de qué carpetas salen los de la lista</small></h2>');
            h.push('<div class="fila">' + (hc.directorios.length
                ? hc.directorios.map(d => `<code>${esc(d)}</code>`).join(' · ')
                : 'las unidades del perfil, en su orden')
                + '<span class="der"><a data-accion="directorios">cambiar…</a></span></div>');
            h.push(`<div class="fila dim">Al tejer la sesión se abren hasta ${hc.tope}, repartidos por turnos: uno de cada carpeta. `
                + 'Los archivados no se reabren solos: ⏸ en la lista archiva uno y guarda su conversación, ▶ lo retoma.</div>');
        }

        const a = this.agenteConfig;
        if (a) {
            const propia = a.reunion !== a.reunion_por_defecto;
            h.push('<h2>Reuniones<small>qué se le dice al agente al pinchar una reunión</small></h2>');
            h.push(`<div class="fila"><code>${esc(a.reunion)}</code>`
                + '<span class="der"><a data-accion="plantilla" data-valor="cambiar">cambiar…</a>'
                + (propia ? ' · <a data-accion="plantilla" data-valor="restablecer">volver a la de flow</a>' : '') + '</span></div>');
            h.push('<div class="fila dim">Se abre un tab «◷ hora reunión» con '
                + `<b>${esc(a.nombre || 'ningún agente')}</b> y se le escribe esto. Marcadores: `
                + '<code>{titulo}</code> <code>{hora}</code> <code>{fecha}</code> <code>{enlace}</code> <code>{proyecto}</code>. '
                + 'El proyecto es la carpeta que comparte palabras con el título; si no hay, la cola «· proyecto:» se quita.</div>');
            if (!propia) h.push('<div class="fila dim">Es la de flow: supone la skill <code>/preparar-reunion</code> instalada en Claude Code.</div>');

            const propiaP = a.proyecto !== a.proyecto_por_defecto;
            h.push('<h2>Proyectos<small>qué se le dice al agente al abrir un proyecto de la lista</small></h2>');
            h.push(`<div class="fila"><code>${esc(a.proyecto)}</code>`
                + '<span class="der"><a data-accion="plantilla-proyecto" data-valor="cambiar">cambiar…</a>'
                + (propiaP ? ' · <a data-accion="plantilla-proyecto" data-valor="restablecer">volver a la de fábrica</a>' : '') + '</span></div>');
            h.push('<div class="fila dim">Se abre un tab con el nombre de la carpeta, vinculado a ella, y se le escribe esto. Marcadores: '
                + '<code>{nombre}</code> <code>{ruta}</code> <code>{carpeta}</code> <code>{documento}</code>.</div>');
        }
        this.pintar(h);
    }

    private pintar(h: string[]): void {
        this.panel?.pintar(this.nav() + h.join('\n'));
    }

    /** Lo que un lienzo pide guardar, en el archivo que declaró su página. Se escribe entero
     *  (temporal y rename): un corte a medias no deja un JSON roto que el lienzo no pueda leer. */
    private guardarLienzo(llave: string, datos: string): void {
        const ruta = this.memorias.get(llave);
        if (!ruta || datos.length > 4_000_000) return;
        try { JSON.parse(datos); } catch { return; }
        // sin permiso o sin disco: el lienzo sigue, sin memoria
        void disco().escribir(ruta, datos).then(ok => { if (ok) this.lienzos.set(ruta, datos); });
    }

    private async mensaje(m: MensajeDia): Promise<void> {
        if (m.tipo === 'lienzo-guardar') { this.guardarLienzo(m.valor ?? '', m.datos ?? ''); return; }
        if (m.tipo === 'per-horario') { await this.previaHorario(m.valor ?? ''); return; }
        if (m.tipo === 'per-skills') { await this.cargarSkills(m.valor ?? ''); return; }
        if (m.tipo === 'listo') {
            // un panel recién abierto para una sección pierde lo que se le mandó antes de estar listo
            if (this.pantalla === 'seccion' && this.pagina) this.renderSeccion();
            // el dashboard abre en «ahora»: su contexto (el plan, los proyectos) se pide aquí
            if (this.pantalla === 'ahora') void this.abrirAhora();
            this.render(); void this.actualizar(); return;
        }
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await ui.abrirExterno(m.url); return; }
        if (m.tipo === 'tecla' && m.k) {
            // las de la pestaña primero; p, c y r valen en todas
            const globales: Record<string, () => Promise<unknown>> = {
                p: () => this.abrirProyectos(), r: () => this.actualizar(true), v: () => this.abrirRevisar(),
                o: () => this.abrirPeriodicos(), d: () => this.abrirPlan(''), a: () => this.abrirCalendario(), n: () => this.abrirAhora(),
                ...Object.fromEntries(this.pestanasCfg.filter(x => x.tecla).map(x => [x.tecla, () => this.abrirPestana(x.nombre)])),
                ...Object.fromEntries(this.bloquesCfg.filter(b => !b.en && b.tecla).map(b => [b.tecla!, () => this.abrirBloque(b.clave)])),
                ...(modelo.hayRemotos ? { c: () => this.abrirCorreo() } : {}),
                ...Object.fromEntries(this.atajos.map(a => [a.tecla, () => this.lanzarAtajo(a.tecla)])),
            };
            await (this.teclas.get(m.k) ?? globales[m.k])?.();
            return;
        }
        if (m.tipo !== 'accion') return;
        switch (m.accion) {
            case 'pendiente': if (m.valor) await llevarPendiente(m.valor, !!m.nuevo); break;
            case 'ir': if (m.valor) await ui.irAHilo(m.valor); break;
            case 'refrescar': await this.actualizar(true); break;
            case 'volver': void ui.mostrarTerminal(); break;
            case 'reunion': {
                const [titulo, hora, enlace, evento, asistentes] = JSON.parse(m.valor ?? '[]') as [string, string, string?, string?, string[]?];
                if (titulo && hora) await this.preparar(titulo, hora, enlace ?? '', evento ?? '', asistentes ?? []);
                break;
            }
            case 'config': await this.abrirConfig(); break;
            case 'proyectos': await this.abrirProyectos(); break;
            case 'seccion': if (m.valor) await this.abrirSeccion(m.valor); break;
            case 'proyecto': if (m.valor) await this.abrirProyecto(m.valor); break;
            case 'proy-sel': if (m.valor) await this.verProyecto(m.valor); break;
            case 'ahora': await this.abrirAhora(); break;
            case 'ahora-mover': this.moverAhora(Number(m.valor) || 0); break;
            case 'ahora-fijar': this.ahoraFijo = true; this.ahoraSel = this.eventoAhora()?.id ?? ''; this.renderAhora(); break;
            case 'ahora-soltar': this.ahoraFijo = false; this.ahoraSel = ''; this.ahoraSim = undefined; this.ahoraDia = undefined; this.ahoraPlan = undefined; this.ahoraElegir = false; this.renderAhora(); break;
            case 'ahora-elegir': this.ahoraElegir = !this.ahoraElegir; this.renderAhora(); break;
            case 'ahora-evento': if (m.valor) this.ahoraAlEvento(m.valor); break;
            case 'ahora-dia': if (m.valor) await this.ahoraOtroDia(Number(m.valor) || 0); break;
            case 'equipo-tarea': if (m.valor && await alternarEquipo(m.valor)) {
                await this.actualizar(true);
                if (this.pantalla === 'revisar') this.renderRevisar();
            } break;
            case 'estrella-tarea': if (m.valor && await alternarEstrella(m.valor)) {
                await this.actualizar(true);
                if (this.pantalla === 'revisar') this.renderRevisar();
            } break;
            case 'dueno-tarea': if (m.valor) {
                const [proveedor, id, ref, actual] = JSON.parse(m.valor) as string[];
                if (await asignar(JSON.stringify([proveedor, id, ref]), actual ?? '', yo.persona)) {
                    await this.actualizar(true);
                    if (this.pantalla === 'revisar') this.renderRevisar();
                }
            } break;
            case 'proy-ir': if (m.valor) { this.proySel = m.valor; await this.abrirProyectos(); } break;
            case 'proy-menu': if (m.valor) await this.menuProyecto(m.valor); break;
            case 'menu-vineta': if (m.valor) await this.menuVineta(m.valor); break;
            case 'proy-consolidar': if (m.valor) await this.consolidarProyecto(m.valor); break;
            case 'proy-enlace': if (m.valor) await this.enlaceReadme(m.valor, String(m.datos ?? '')); break;
            case 'plantilla-proyecto': await this.cambiarPlantillaProyecto(m.valor === 'restablecer'); break;
            case 'bloque': if (m.valor) await this.abrirBloque(m.valor); break;
            case 'pest-ver': case 'pest-subir': case 'pest-bajar':
                if (m.valor) await this.cambiarPestanas(m.accion.slice(5), m.valor);
                break;
            case 'atajo': if (m.valor) await this.lanzarAtajo(m.valor); break;
            case 'abrir-item': if (m.valor) await this.abrirItem(m.valor); break;
            case 'ver-item': if (m.valor) {
                const corte = m.valor.lastIndexOf(':');
                await this.abrirBloque(m.valor.slice(0, corte), Number(m.valor.slice(corte + 1)));
            } break;
            case 'item-volver': await this.abrirBloque(this.bloqueSel); break;
            case 'solo-pendientes': if (m.valor) {
                if (this.soloPendientes.has(m.valor)) this.soloPendientes.delete(m.valor); else this.soloPendientes.add(m.valor);
                this.render();
            } break;
            case 'cuerpo-alternar': if (m.valor) {
                if (this.cuerposAbiertos.has(m.valor)) this.cuerposAbiertos.delete(m.valor); else this.cuerposAbiertos.add(m.valor);
                this.render();
            } break;
            case 'item-enlace': if (m.valor) {
                const corte = m.valor.lastIndexOf(':');
                const x = (this.bloquesDatos.get(m.valor.slice(0, corte))?.pagina?.bloques ?? []).flatMap(y => y.items ?? [])[Number(m.valor.slice(corte + 1))];
                if (x?.enlace) await abrirEnlace(x.enlace);
            } break;
            case 'grupo-item': if (m.valor) {
                if (this.gruposAbiertos.has(m.valor)) this.gruposAbiertos.delete(m.valor); else this.gruposAbiertos.add(m.valor);
                this.render();
            } break;
            case 'tarea':
                if (!m.valor) break;
                // ⌘-clic: como antes, al hilo donde se trabaja; clic: la ficha
                if (m.nuevo) { const [proveedor, , ref] = JSON.parse(m.valor) as string[]; await llevarPendiente(ref, false, proveedor); }
                else await this.abrirTarea(m.valor);
                break;
            case 'accion-tarea': if (m.valor) await this.accionTarea(Number(m.valor)); break;
            case 'hecha-fila': if (m.valor) {
                // la fila ya está tachada (lo hace la vista al clic); hecha, sale de la lista al tiro y
                // la lista se relee por detrás (son ~6 s que no hay por qué esperar)
                if (await marcarHecha(m.valor)) this.decididas.add((JSON.parse(m.valor) as string[])[1]);
                this.render();
                void this.actualizar(true);
            } break;
            case 'hecha-vineta': if (m.valor) {
                const [ref, texto] = JSON.parse(m.valor) as string[];
                const r = await cli.vineta(ref, texto, ['--hecho']);
                if (!r.datos) void ui.aviso(`telar: ${r.error ?? 'no pude marcarla'}`);
                else { ui.estado(`✓ ${texto.slice(0, 60)}`, 5000); olvidarDia(); void this.actualizar(true); }
            } break;
            case 'hilo-fila': if (m.valor) {
                const [proveedor, ref, id] = JSON.parse(m.valor) as string[];
                await llevarPendiente(ref, false, proveedor, id ? `/tarea ${id}` : '', !!id);
            } break;
            case 'hecha':
                if (!m.valor) break;
                await marcarHecha(m.valor);
                void this.actualizar(true);
                break;
            case 'tarea-principal': {
                const i = (this.ficha?.pagina?.acciones ?? []).findIndex(a => a.principal);
                if (i >= 0) await this.accionTarea(i);
                break;
            }
            case 'tarea-siguiente': await this.otraPropuesta(1); break;
            case 'revisar': await this.abrirRevisar(); break;
            case 'periodicos': this.periodico = undefined; this.formPer = undefined; await this.abrirPeriodicos(); break;
            case 'per-ver': if (m.valor) await this.verPeriodico(m.valor); break;
            case 'per-nuevo': await this.nuevoPeriodico(); break;
            case 'per-editar': if (m.valor) await this.editarPeriodico(m.valor); break;
            case 'per-guardar': if (m.valor) await this.guardarFormPer(m.valor); break;
            case 'per-cancelar': this.formPer = undefined; this.renderPeriodicos(); break;
            case 'per-orden': if (m.valor) await this.ordenPeriodico(JSON.parse(m.valor) as string[]); break;
            case 'pestana': if (m.valor) await this.abrirPestana(m.valor); break;
            case 'volver-ficha':
                if (this.fichaDesde === 'revisar') await this.abrirRevisar();
                else if (this.fichaDesde.startsWith('pestana:')) await this.abrirPestana(this.fichaDesde.slice(8));
                else if (this.fichaDesde.startsWith('bloque:')) {
                    const [, clave, item] = this.fichaDesde.split(':');
                    await this.abrirBloque(clave, item === '' ? undefined : Number(item));
                }
                else await this.abrirAhora();
                break;
            case 'tarea-anterior': await this.otraPropuesta(-1); break;
            case 'abrir-enlace': if (m.valor) await abrirEnlace(m.valor); break;
            case 'abrir-ruta':
                // una ruta relativa a la raíz de telar (la que traen las notas de un evento)
                if (m.valor && !m.valor.includes('..') && modelo.raiz) await abrirEnlace(rutas.unir(modelo.raiz, m.valor));
                break;
            case 'recargar-seccion': this.pagina = undefined; if (this.seccion) await this.abrirSeccion(this.seccion); break;
            case 'volver-seccion': if (this.seccion && this.pagina) { this.pantalla = 'seccion'; this.renderSeccion(); } else await this.abrirAhora(); break;
            case 'conversacion': if (m.valor) await this.abrirConversacion(m.valor); break;
            case 'correo': await this.abrirCorreo(); break;
            case 'equipo-accion': if (m.valor) await this.accionEquipo(m.valor); break;
            case 'ver-msg':
                if (m.valor) { if (this.abiertoMsg.has(m.valor)) this.abiertoMsg.delete(m.valor); else this.abiertoMsg.add(m.valor); this.renderCorreo(); }
                break;
            case 'soltar-msg': if (m.valor) await this.soltarMensaje(m.valor); break;
            case 'retomar-charla':
                if (this.charla?.hilo) {
                    const vivo = modelo.porNombre(this.charla.hilo)?.vivo;
                    await ui.orden(vivo ? 'telar.ir' : 'telar.retomar', { hilo: this.charla.hilo });
                }
                break;
            case 'calendario':
                // desde la configuración elige de dónde sale la agenda; desde una pestaña, la abre
                if (this.pantalla === 'config') await this.elegirCalendario(m.valor ?? ''); else await this.abrirCalendario();
                break;
            case 'plan': await this.abrirPlan(''); break;
            case 'plan-dia': await this.abrirPlan(m.valor ?? ''); break;
            case 'evento-sel': if (m.valor) { this.eventoSel = m.valor; this.renderCalendario(); } break;
            case 'cal-dia': if (m.valor) await this.moverDiaCal(m.valor); break;
            case 'nota-evento': if (m.valor) await this.notaEvento(m.valor); break;
            case 'menu-tarea': if (m.valor) await this.menuTarea(m.valor); break;
            case 'reagendar':
                if (m.valor && await reagendar(m.valor)) { await this.actualizar(true); if (this.pantalla === 'revisar') this.renderRevisar(); }
                break;
            case 'ev-escribir': if (m.valor) await this.escribirSobreEvento(m.valor, m.datos ?? ''); break;
            case 'plan-comentar': if (m.valor && m.datos?.trim()) await this.comentarPlan(m.valor, m.datos); break;
            case 'plantilla': await this.cambiarPlantilla(m.valor === 'restablecer'); break;
            case 'directorios': await this.cambiarDirectorios(); break;
        }
    }
}

/** El markdown que cabe en una página de sección: párrafos, **negrita**, `código` y listas
 *  con «- ». Nada más: la página la escribe un comando ajeno, y lo que no se entiende se
 *  muestra como texto, nunca como HTML. */
function mdSimple(texto: string): string {
    const linea = (t: string) => esc(t)
        .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
        .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g, '$1<i>$2</i>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
    const esItem = (l: string) => /^\s*[-*] /.test(l);
    return texto.trim().split(/\n\s*\n/).map(parrafo => {
        // un párrafo puede abrir con una frase y seguir con una lista: cada tramo es lo suyo
        const salida: string[] = [];
        let texto: string[] = [], items: string[] = [];
        const cerrar = () => {
            if (texto.length) salida.push(`<p>${texto.map(linea).join(' ')}</p>`);
            if (items.length) salida.push('<ul>' + items.map(l => `<li>${linea(l.replace(/^\s*[-*] /, ''))}</li>`).join('') + '</ul>');
            texto = []; items = [];
        };
        for (const l of parrafo.split('\n')) {
            if (esItem(l)) { if (texto.length) cerrar(); items.push(l); }
            else if (items.length && /^\s+\S/.test(l)) items[items.length - 1] += ' ' + l.trim();
            else { if (items.length) cerrar(); texto.push(l); }
        }
        cerrar();
        return salida.join('');
    }).join('');
}

/** Una hora ISO en la hora local, HH:MM. */
function horaLocal(iso: string): string {
    const t = Date.parse(iso);
    return Number.isNaN(t) ? '' : new Date(t).toTimeString().slice(0, 5);
}

/** Una fecha de correo (RFC 2822) como «24-sep 12:19»; si no se entiende, tal cual. */
function fechaCorta(fecha: string): string {
    const t = Date.parse(fecha);
    if (Number.isNaN(t)) return fecha;
    const d = new Date(t);
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    return `${d.getDate()}-${meses[d.getMonth()]} ${d.toTimeString().slice(0, 5)}`;
}

/** «viernes», «2026-09-25» → «vie 25 sep». */
function fechaLarga(nombreDia: string, fecha: string): string {
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const [, m, d] = fecha.split('-').map(Number);
    return `${nombreDia.slice(0, 3)} ${d || ''} ${meses[(m || 1) - 1]}`.trim();
}

/** Abre un enlace de una página: una URL en una pestaña nueva, una ruta de la máquina en la vista de
 *  carpeta de la página. */
async function abrirEnlace(enlace: string): Promise<void> {
    if (/^https?:\/\//.test(enlace)) {
        await ui.abrirExterno(enlace);
        return;
    }
    if (enlace.startsWith('/')) {
        await ui.abrirArchivo(enlace);
        return;
    }
    void ui.aviso(`telar: no sé abrir ${enlace}`);
}

/** La marca, el color y la frase del estado de un proceso: pausado, corriendo, falló, bien. */
function estadoPeriodico(p: cli.JsonPeriodico): [string, string, string] {
    if (p.ultima.corriendo) return ['◐', 'azul', 'corriendo ahora'];
    if (!p.activo) return ['⏸', 'dim', 'pausado: no corre hasta que lo actives'];
    if (p.ultima.codigo !== undefined && p.ultima.codigo !== 0) return ['✗', 'rojo', `la última vez: ${p.ultima.resultado ?? 'falló'}`];
    if (p.ultima.inicio) return ['●', 'verde', `la última vez: ${p.ultima.resultado ?? 'bien'}`];
    return ['○', 'dim', 'todavía no ha corrido'];
}

/** «2 h 10», «35 min», «3 d»: cuánto falta hasta esa hora. */
function enCuanto(iso: string): string {
    const min = Math.max(0, Math.round((Date.parse(iso) - Date.now()) / 60000));
    if (min < 60) return `${min} min`;
    if (min < 60 * 24) return `${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60}` : ''}`;
    return `${Math.round(min / 1440)} d`;
}

/** «vie 2 10:00»: una corrida, corta. */
function diaHora(iso: string): string {
    const d = new Date(iso);
    return `${['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'][d.getDay()]} ${d.getDate()} ${iso.slice(11, 16)}`;
}

/** El origen de una dirección (`http://telar:8790`), o "" si no se entiende. */
/** Lo que puede un lienzo: sus scripts y estilos en línea, e imágenes; ni red, ni `<script src>`, ni `eval`. */
const POLITICA_LIENZO = "default-src 'none'; img-src https: data: blob:; style-src 'unsafe-inline'; script-src 'unsafe-inline'";

/** El alto de un lienzo o un marco: píxeles, o «lleno» (lo que queda del panel, por la clase). */
function estiloAlto(alto: number | 'lleno' | undefined): string {
    return alto === 'lleno' ? '' : ` style="height:${Math.round(alto ?? 240)}px"`;
}

/** Una página servida dentro del panel. Su sandbox le deja su propio origen (necesita sus
 *  cookies y su almacenamiento), pero no alcanzar el panel: es otro origen. */
function htmlMarco(m: cli.JsonMarco): string {
    return `<iframe class="lienzo${m.alto === 'lleno' ? ' lleno' : ''}" src="${esc(m.url)}"`
        + ` sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-downloads"${estiloAlto(m.alto)}></iframe>`;
}

/** Una pestaña del dashboard: [clave, acción, valor, nombre, tecla]. */
type Pestana = [string, string, string, string, string];

/** La hora de un ítem si es de hoy; si no, el día («21 sep»): en la bandeja hay correos de semanas atrás. */
function cuandoCorto(fecha: string): string {
    const hoy = new Date();
    const dia = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`;
    if (!fecha || fecha.slice(0, 10) === dia) return fecha.slice(11, 16);
    const [, m, d] = fecha.slice(0, 10).split('-').map(Number);
    return `${d} ${['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][(m || 1) - 1]}`;
}
