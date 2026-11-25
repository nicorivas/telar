// El modelo: lo que hay ahora mismo, leído una vez y compartido por la barra y el dashboard.
//
// No guarda nada propio. Si la página se cierra, no se pierde un dato: el estado vive donde
// telar lo tenga, y aquí solo queda la última respuesta de `telar hilos --json`. Con una excepción
// que dura segundos: lo que esta página hizo (ver un hilo, cambiarle la prioridad) se pone encima
// de lo leído hasta que el servidor lo confirme, para que se vea al tiro y no al sondeo siguiente.
//
// Dos ritmos, porque leer los documentos es lo único caro de todo esto:
//   · el rápido (cada pocos segundos, lo pide la página) trae los hilos SIN ficha: quién está vivo,
//     cuál tiene el foco, qué dijo cada agente, cuánto lleva hoy;
//   · el lento (cada INTERVALO_FICHA) los trae CON ficha, que es lo que pone la línea de
//     estado bajo cada hilo.
// Entre uno y otro, la ficha conocida se conserva: vale más una línea de hace un minuto que
// ninguna, y se nota si queda vieja porque el documento se relee al tocarlo.

import * as cli from './cli';
import * as ui from './web/ui';

/** Cada cuánto se traen los hilos con su ficha (lo caro: leer los documentos). */
const INTERVALO_FICHA = 60000;
/** Cuánto vale lo que esta página hizo y el servidor todavía no cuenta (lo vio, le cambió la prioridad): pasado esto,
 *  manda lo que diga el servidor. Lo normal es que lo confirme en el sondeo siguiente. */
const LOCAL_MS = 60000;
/** Cuánto tiene que durar una caída de la API para decirla: un reinicio de telar (cada instalación) tarda menos. */
const CAIDO_MS = 15000;

/** Avisar a quien escucha que algo cambió (un EventEmitter chico). */
export class Emisor {
    private oyentes = new Set<() => void>();
    /** Escuchar; devuelve con qué dejar de hacerlo. */
    readonly event = (f: () => void): { dispose(): void } => {
        this.oyentes.add(f);
        return { dispose: () => { this.oyentes.delete(f); } };
    };
    fire(): void { for (const f of [...this.oyentes]) f(); }
}

export class Modelo {
    sesion = '';
    multiplexor = '';
    raiz = '';
    /** el nombre de la máquina que sirve esta página (`/api/salud`), para saber si un hilo vive en otra */
    aqui = '';
    viva = false;
    /** los pids de los clientes del multiplexor: qué terminales muestran la sesión */
    clientes: number[] = [];
    /** por qué no hay multiplexor, si no lo hay: lo dice telar, no lo adivinamos */
    aviso = '';
    /** el error de la última lectura, si la CLI no contestó */
    error = '';
    /** desde cuándo fallan las lecturas (0: la última salió bien) */
    fallaDesde = 0;
    /** si alguna lectura salió bien: hay una lista que seguir mostrando cuando la API no contesta */
    leido = false;
    /** cuándo salió bien la última lectura (la franja de avisos lo dice, tranquila: web/franja.ts) */
    leidoA = 0;
    /** si el error de la última lectura lo dijo telar (el código HTTP con que contestó): entonces no es la conexión */
    errorEstado = 0;
    hilos: cli.JsonHilo[] = [];
    /** las secciones de la configuración; se releen con el ritmo lento */
    secciones: cli.JsonSeccion[] = [];
    /** las apps de la configuración (`[apps]`), en su orden */
    apps: cli.JsonApp[] = [];
    /** los tipos de objeto de los módulos que también se buscan en ⌘K (`[objetos.<tipo>] buscador`: los chats de whatsapp) */
    buscables: { tipo: string; plural: string }[] = [];
    /** lo que el equipo sugiere y la persona no ha decidido (`telar equipo`); vacío si la función está apagada */
    sugerencias: cli.JsonSugerencia[] = [];
    private sugerenciasVistas: Set<string> | undefined;
    hayRemotos = false;
    /** las máquinas de `[remotos]` (por ssh): a dónde se puede llevar un hilo, además de las del bus */
    remotos: { nombre: string; destino: string }[] = [];
    /** si esta persona está en un bus (`[bus]`): lo que cruza entre máquinas y personas (los colegas, el
     *  registro de mensajes, la gestión de personas) depende de esto, no de `[remotos]` */
    hayBus = false;
    /** a quién va de entrada lo que manda la pestaña de un módulo con la instrucción (`[instruccion] destino`): el
     *  nombre que lo elige en la ventana; vacío sin declarar */
    instruccionA = '';
    /** la línea que le llega al agente con un contexto libre y nada pedido (la de telar, para mostrarla tal cual) */
    procesar = '';

    readonly cambio = new Emisor();
    /** los hilos que están viajando a otra máquina ahora (web/mudanza.ts): hilo → máquina. La barra lo dice en su fila */
    readonly mudando = new Map<string, string>();
    /** los hilos que se están cerrando o archivando (la orden va, quizás por el bus): su fila lo dice */
    readonly ocupados = new Map<string, string>();
    /** los que se mandaron a cerrar o archivar y todavía se ven (en otra máquina tarda unos segundos en llegar): su fila
     *  dice «cerrando…» hasta que desaparece, o hasta `hasta` */
    readonly saliendo = new Map<string, { texto: string; hasta: number }>();

    /** Lo que esta página pidió y el servidor todavía no dice (`telar hilo prioridad …`): hilo → los campos y cuándo. Se
     *  aplica sobre cada lectura, así se ve al tiro, hasta que el servidor diga lo mismo o pasen LOCAL_MS. */
    private readonly local = new Map<string, { cambios: Partial<cli.JsonHilo>; en: number }>();
    /** Los hilos que la página mostró, y cuándo: lo que terminó hasta entonces ya se vio, aunque el servidor (que lo
     *  anota al abrir y al dejar su terminal) todavía no lo cuente. */
    private readonly vistosAqui = new Map<string, number>();

    private fichas = new Map<string, cli.JsonFicha | null>();
    private firma = '';
    private enCurso = false;
    /** si se pidió leer mientras se leía (llegó un aviso del servidor a medio sondeo): se lee otra vez al terminar */
    private otraVez = false;
    private ultimaFicha = 0;

    get activo(): cli.JsonHilo | undefined { return this.hilos.find(h => h.activo); }
    /** Los hilos con ventana (aquí, o la de otra máquina). Uno sin ventana que no se archivó a propósito
     *  no queda en un limbo gris bajo los activos: va al archivo con los demás, que es lo que es. */
    get enLista(): cli.JsonHilo[] { return this.hilos.filter(h => !h.archivado && h.vivo); }
    get archivados(): cli.JsonHilo[] { return this.hilos.filter(h => h.archivado || !h.vivo); }
    get esperan(): number { return this.enLista.filter(h => h.atencion === 'espera').length; }

    /** los hilos de las otras personas del bus (`/directorio`), para la sección EQUIPO de la barra */
    colegas: cli.JsonDirectorio['personas'] = [];

    /** Lee el directorio de las otras personas; sin bus, o si no contesta, queda lo que había. */
    async leerColegas(): Promise<void> {
        if (!this.hayBus) { this.colegas = []; return; }
        const r = await cli.directorio();
        if (!r.datos) return;
        const antes = JSON.stringify(this.colegas);
        this.colegas = r.datos.personas;
        if (JSON.stringify(this.colegas) !== antes) { this.firma = ''; this.cambio.fire(); }
    }

    /** dónde vive la bandeja del equipo, vista desde aquí («aqui», otra máquina, o vacío: sin equipo). La pone
     *  la página con lo que dice `/config`. */
    equipoRemoto = '';

    /** Lee las sugerencias del equipo y avisa de las nuevas con una notificación que no se va sola:
     *  la primera lectura avisa de lo que ya esperaba, para que nada pendiente pase sin verse. */
    async leerEquipo(): Promise<void> {
        const remoto = this.equipoRemoto;
        if (!remoto) { this.sugerencias = []; return; }
        const r = await cli.equipoPendientes(remoto);
        if (!r.datos) return;
        const nuevas = r.datos.sugerencias.filter(x => !this.sugerenciasVistas?.has(x.id));
        const primera = this.sugerenciasVistas === undefined;
        this.sugerenciasVistas = new Set([...(this.sugerenciasVistas ?? []), ...r.datos.sugerencias.map(x => x.id)]);
        this.sugerencias = r.datos.sugerencias;
        this.firma = ''; this.cambio.fire();
        if (!nuevas.length) return;
        const uno = nuevas.length === 1 ? nuevas[0] : undefined;
        const texto = uno
            ? (uno.tipo === 'tarea'
                ? `${uno.persona} te pide una tarea: «${uno.titulo.slice(0, 80)}»${uno.vence ? ` (para el ${uno.vence})` : ''}${uno.similares?.length ? ` · ¿ya existe ${uno.similares[0].id}?` : ''}`
                : `${uno.persona} sugiere subir ${uno.tarea} «${uno.titulo.slice(0, 60)}»: ${uno.motivo.slice(0, 120)}`)
            : `${nuevas.length} cosas del equipo ${primera ? 'esperan' : 'nuevas'}: ${nuevas.map(x => x.tipo === 'tarea' ? `pedido de ${x.persona}` : x.tarea).join(', ')}`;
        void ui.aviso(`telar · ${texto}`, 'Ver', ...(uno ? [uno.tipo === 'tarea' ? 'Agregar' : 'Aceptar'] : [])).then(async eleccion => {
            if (eleccion === 'Ver') await ui.orden('telar.equipoVer', uno?.id);
            else if ((eleccion === 'Aceptar' || eleccion === 'Agregar') && uno) {
                const a = await cli.equipoResolver(remoto, 'aceptar', uno.id);
                void ui.info(!a.datos ? `telar: no se pudo: ${a.error ?? ''}`
                    : uno.tipo === 'tarea' ? `telar: agregada${a.datos.sugerencia.tarea ? ` como ${a.datos.sugerencia.tarea}` : ''}` : `telar: ${uno.tarea} sube de prioridad`);
                await this.leerEquipo();
            }
        });
    }

    /** La sección a la que pertenece un hilo, si alguna lo reclama. */
    seccionDe(hilo: string): cli.JsonSeccion | undefined { return this.secciones.find(s => cli.enSeccion(s, hilo)); }

    porNombre(nombre: string): cli.JsonHilo | undefined { return this.hilos.find(h => h.nombre === nombre); }
    porId(id: string): cli.JsonHilo | undefined { return this.hilos.find(h => h.id === id); }

    /** El orden lo aplica telar: el del multiplexor (cada grupo de la barra se ordena aparte, ahí). */
    readonly orden = 'mux';

    async sondear(conFicha = false): Promise<void> {
        if (this.enCurso) { this.otraVez = true; return; }
        this.enCurso = true;
        try {
            const toca = conFicha || Date.now() - this.ultimaFicha > INTERVALO_FICHA;
            const r = await cli.hilos(toca, this.orden);
            if (!r.datos) {
                this.error = r.error ?? '';
                this.errorEstado = r.estado ?? 0;
                this.fallaDesde ||= Date.now();
                this.anunciar(['error', this.error, this.caido()]);
                return;
            }
            this.error = ''; this.errorEstado = 0; this.fallaDesde = 0; this.leido = true; this.leidoA = Date.now();
            const d = r.datos;
            this.sesion = d.sesion; this.multiplexor = d.multiplexor; this.raiz = d.raiz;
            this.viva = d.viva; this.aviso = d.aviso; this.clientes = d.clientes ?? [];
            if (toca) {
                const c = await cli.config();
                if (c.datos) {
                    this.secciones = c.datos.secciones ?? [];
                    this.apps = c.datos.apps ?? [];
                    this.buscables = (c.datos.modulos ?? []).flatMap(m => m.buscables ?? []);
                    this.remotos = (c.datos.remotos ?? []).map(r => ({ nombre: r.nombre, destino: r.destino }));
                    this.hayRemotos = this.remotos.length > 0;
                    this.hayBus = !!c.datos.bus?.url;
                    this.instruccionA = c.datos.instruccion?.a ?? '';
                    this.procesar = c.datos.instruccion?.procesar ?? '';
                }
                void this.leerEquipo();
                void this.leerColegas();
                this.ultimaFicha = Date.now();
                this.fichas = new Map(d.hilos.map(h => [h.nombre, h.ficha ?? null]));
            }
            this.hilos = d.hilos.map(h => cli.conRutasAbsolutas(
                { ...h, ficha: h.ficha ?? this.fichas.get(h.nombre) ?? null }, d.raiz));
            this.aplicarLocal();
            this.anunciar(['ok', d.sesion, d.viva, d.aviso, this.hilos, this.secciones]);
        } finally {
            this.enCurso = false;
        }
        if (this.otraVez) { this.otraVez = false; await this.sondear(); }
    }

    /** Si la API lleva rato sin contestar (CAIDO_MS), no solo un momento: cada vez que se instala o se reinicia telar,
     *  la página se queda unos segundos sin API, y eso no se dice. Sin ninguna lectura buena, desde la primera falla. */
    caido(): boolean { return !!this.fallaDesde && (!this.leido || Date.now() - this.fallaDesde >= CAIDO_MS); }

    /** Redibujar solo si algo cambió: si no, la lista parpadea cada segundo. */
    private anunciar(estado: unknown[]): void {
        const firma = JSON.stringify(estado);
        if (firma === this.firma) return;
        this.firma = firma;
        this.cambio.fire();
    }

    /** Fuerza el próximo sondeo a releer los documentos (después de actuar sobre un hilo). */
    invalidar(): void { this.ultimaFicha = 0; }

    // ── lo local: lo que la página ya sabe antes que el servidor ──

    /** Que la página muestra un hilo, o acaba de dejarlo: lo que terminó en él ya se vio. Se ve al tiro. */
    ver(nombre: string): void {
        if (!nombre) return;
        this.vistosAqui.set(nombre, Date.now());
        this.aplicarLocal();
        this.firma = ''; this.cambio.fire();
    }

    /** Si un hilo (también uno de otra máquina, de su foto) se vio aquí después de que terminó (`desde`). */
    vistoAqui(nombre: string, desde?: string | null): boolean {
        const t = this.vistosAqui.get(nombre);
        if (t === undefined || Date.now() - t > LOCAL_MS) return false;
        return !desde || Date.parse(desde) <= t;
    }

    /** Un cambio que la página pidió y el servidor todavía no confirma: se ve al tiro. */
    cambiarLocal(nombre: string, cambios: Partial<cli.JsonHilo>): void {
        this.local.set(nombre, { cambios: { ...this.local.get(nombre)?.cambios, ...cambios }, en: Date.now() });
        this.aplicarLocal();
        this.firma = ''; this.cambio.fire();
    }

    /** El cambio no se pudo: se olvida, y se vuelve a leer lo que hay. */
    olvidarLocal(nombre: string): void {
        this.local.delete(nombre);
        void this.sondear();
    }

    /** Pone lo local sobre lo leído; olvida lo que el servidor ya confirmó o lo que venció. */
    private aplicarLocal(): void {
        const ahora = Date.now();
        for (const [n, l] of this.local) if (ahora - l.en > LOCAL_MS) this.local.delete(n);
        for (const [n, t] of this.vistosAqui) if (ahora - t > LOCAL_MS) this.vistosAqui.delete(n);
        if (!this.local.size && !this.vistosAqui.size) return;
        this.hilos = this.hilos.map(h => {
            let x = h;
            const l = this.local.get(h.nombre);
            if (l) {
                const dice = h as unknown as Record<string, unknown>;
                if (Object.entries(l.cambios).every(([k, v]) => dice[k] === v)) this.local.delete(h.nombre);
                else x = { ...x, ...l.cambios };
            }
            if (x.sin_ver && this.vistoAqui(h.nombre, h.atencion_desde)) x = { ...x, sin_ver: false };
            return x;
        });
    }
}

export const modelo = new Modelo();
