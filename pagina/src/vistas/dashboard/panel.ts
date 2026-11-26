// El dashboard: el día entero en el área central de la página (por dentro, `telar hoy`).
//
// Este archivo es el núcleo: monta la vista (vista.ts), lee la configuración y el día, lleva las pestañas, las
// teclas y los atajos de [atajos], y le pasa cada acción de la página a la pantalla que la tiene. Cada pantalla
// vive en su archivo de esta carpeta, con su estado, su HTML y sus acciones; lo que el núcleo les da está en
// pantalla.ts (el Tablero). La configuración (⚙) vive en config/.
//
// Tres cosas y en este orden, el mismo de `telar hoy` en la terminal: lo que ya tiene hora,
// quién te espera, y lo que está por hacer. Nada más. Lo que saldría de un proveedor que no
// está declarado no aparece porque no existe, y eso se dice en vez de dejar un hueco.

import * as entidades from '../../web/entidades';
import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { hace } from '../../estilo';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, conLoSalido, dia, diaGuardado, olvidarDia, seccion, yo } from './dia';
import { PantallaCalendario } from './plan';
import { PantallaProyectos } from './proyectos';
import { PantallaFoco } from './foco';
import { PantallaAhora } from './ahora';
import { Configuracion } from './config/configuracion';
import { type Accion, BARRA_DE, type EnBarra, ICONO_VISTA, type NombrePantalla, type Pantalla, type Tablero, abrirEnlace, PESTANA_DE_SECCION, SECCION_DE_PANTALLA, SUBPESTANAS } from './pantalla';
import { type AccionDePantalla, barra as barraPantalla, type VistaDePantalla } from '../../componentes/pantalla';
import { I } from '../../web/iconos';
import { type MensajeDia, montarDia, type VistaDia } from './vista';
import { PantallaEquipo } from './equipo';
import { PantallaAgentes } from './agentes';
import { Paginas } from './pagina';
import { atender as atenderLocal, nombreDeDestino, type PedidoDeLienzo } from './pedidos-locales';
import { PantallaTareas } from './tareas';
import { PantallaBloques } from './bloques';
import { PantallaSecciones } from './secciones';
import { PantallaEsperas } from './esperas';
import { PantallaEsperando } from './esperando';
import { PantallaTactica } from './tactica';
import { PantallaTodo } from './todo';
import { delModo, ordenarPestanas } from './orden-pestanas';
import * as modos from '../../web/modos';
import * as mundo from '../../web/mundo';

export class Dashboard implements Tablero {
    /** el dashboard en la página, ya montado (vista.ts); hasta abrirlo, nada */
    panel?: VistaDia;
    /** dónde se dibuja (un elemento de la página) y cómo se lo trae al frente: los da la página (src/navegador) */
    donde?: () => HTMLElement;
    mostrarme?: () => void;
    private datos?: Dia;
    private actual: NombrePantalla = 'ahora';
    /** recién abierto, sin que se haya pedido ninguna pestaña: al estar listo va a la del modo */
    private deEntrada = true;
    /** la pantalla que se ve, y cambiarla (Tablero) */
    get pantalla(): NombrePantalla { return this.actual; }
    ir(p: NombrePantalla): void { this.actual = p; }
    /** las pestañas: en qué orden van y cuáles no se muestran (`[dashboard]`, se cambia en ⚙) */
    private dashOrden: string[] = [];
    private dashOcultas: string[] = [];
    /** el agente que recibe lo que no tiene proyecto: a quién le escribe el calendario */
    private agenteGeneral?: { clave: string; nombre: string };
    /** la configuración resuelta, leída al abrir (`/config`) */
    private cfg?: cli.JsonConfig;
    /** cuándo se lanzó cada atajo, para no encargar lo mismo dos veces sin querer */
    private atajosLanzados = new Map<string, number>();
    /** las pestañas de proveedor declaradas y su tecla (`telar config --json`) */
    private pestanasCfg: cli.JsonPestana[] = [];
    /** la primera lectura de la configuración (`leerAtajos`, al montar): las pestañas de los módulos salen de ahí */
    private configLeida: Promise<void> = Promise.resolve();
    /** las teclas que declara `[atajos]`; se leen al montar el dashboard (`leerAtajos`) */
    private atajos: cli.JsonAtajo[] = [];
    readonly teclas = new Map<string, () => Promise<unknown> | unknown>();
    /** las pantallas que viven en su archivo, con sus acciones (pantalla.ts) */
    private readonly equipo = new PantallaEquipo(this);
    private readonly agentesVista = new PantallaAgentes(this);
    readonly planes: PantallaCalendario = new PantallaCalendario(this);
    readonly proyectos: PantallaProyectos = new PantallaProyectos(this);
    /** cómo se dibuja una página de bloques (una sección, una app, la ficha de una tarea), con sus lienzos */
    readonly paginas = new Paginas();
    readonly tareas: PantallaTareas = new PantallaTareas(this);
    /** los bloques del día (`[bloques.x]`): su pestaña, y los que van arriba de otra */
    readonly bloques: PantallaBloques = new PantallaBloques(this);
    /** la página de una sección, un agente o una app, y la conversación que se lee desde ella */
    private readonly secciones = new PantallaSecciones(this);
    /** «ahora», donde abre el dashboard */
    private readonly ahora = new PantallaAhora(this);
    /** «foco»: lo urgente e importante, de a cinco tarjetas para decidir (foco.ts) */
    private readonly foco = new PantallaFoco(this);
    /** «te esperan»: lo que espera una decisión de la persona, junto (esperas.ts); su fila en la barra lleva el número */
    private readonly esperas = new PantallaEsperas(this);
    /** «tareas › esperando»: lo que otros le deben a la persona, por persona (esperando.ts) */
    private readonly esperando = new PantallaEsperando(this);
    /** «táctica»: la vista de partida del orden por modos (tactica.ts), por ahora una pestaña más; el pie nombra las
     *  pestañas de las fuentes */
    private readonly tactica = new PantallaTactica(this, () => this.pestanas());
    /** «todo»: ver y buscar todo, la vista del modo todo (todo.ts): cada pestaña entera, y el buscador sobre todo junto */
    private readonly todoVista = new PantallaTodo(this, () => this.pestanas(), () => this.esperas.todas());
    private get modulos(): Pantalla[] { return [this.ahora, this.foco, this.tareas, this.bloques, this.proyectos, this.planes, this.secciones, this.equipo, this.agentesVista, this.esperas, this.esperando, this.tactica, this.todoVista]; }
    private tablaAcciones?: Record<string, Accion>;
    /** las acciones de todas, por nombre: cada nombre es de una sola (si dos lo reclaman, falla al tiro) */
    private acciones(): Record<string, Accion> {
        if (this.tablaAcciones) return this.tablaAcciones;
        const tabla: Record<string, Accion> = {};
        for (const p of this.modulos) {
            for (const [nombre, f] of Object.entries(p.acciones)) {
                if (nombre in tabla) throw new Error(`telar: la acción «${nombre}» es de dos pantallas del dashboard`);
                tabla[nombre] = f;
            }
        }
        this.tablaAcciones = tabla;
        return tabla;
    }

    /** ⚙: el menú de la configuración y sus secciones (config/) */
    private readonly configuracion = new Configuracion({
        pintar: h => this.pintar(h),
        parcial: (id, html) => this.parcial(id, html),
        teclas: this.teclas,
        paginas: this.paginas,
        dashboard: {
            dia: () => this.datos,
            actualizar: conRed => this.actualizar(conRed),
            pestanas: () => this.todasLasPestanas().map(([clave]) => ({ clave, nombre: this.nombrePestana(clave) })),
            orden: () => ({ orden: this.dashOrden, ocultas: this.dashOcultas }),
            usarOrden: d => { this.dashOrden = d.orden; this.dashOcultas = d.ocultas; this.alPintar?.(); },
        },
    });

    /** Se le avisa cuando el dashboard gana o pierde el foco (la lista de hilos marca su fila). */
    alCambiarFoco?: (activo: boolean) => void;
    /** Se le avisa cada vez que pinta: la barra pone al día sus pestañas (sus cuentas, la que se ve). */
    alPintar?: () => void;

    /** ⌥H: si el dashboard ya está al frente, devuelve el teclado al terminal. */
    alternar(): void {
        if (this.panel?.visible) { void ui.mostrarTerminal(); return; }
        this.abrir();
    }

    /** Montarlo si todavía no está, sin traerlo al frente ni releer (Tablero). */
    montar(): void { if (!this.panel) this.abrir(); }

    /** Traerlo al frente si otra pestaña lo tapa, en su columna y sin releer (abrir() lo movería a la activa y
     *  pediría el día de nuevo). */
    alFrente(): void { if (!this.panel) this.abrir(); else if (!this.panel.visible) this.mostrarme?.(); }

    /** La pantalla que dibuja lo que se ve, si vive en su archivo. */
    private duena(): Pantalla | undefined { return this.modulos.find(p => p.pantallas.includes(this.actual)); }

    abrir(): void {
        if (this.panel) { this.mostrarme?.(); void this.actualizar(); return; }
        if (!this.donde) throw new Error('telar: el dashboard no sabe dónde dibujarse (donde)');
        this.panel = montarDia(this.donde(), m => void this.mensaje(m));
        this.configLeida = this.leerAtajos();
        // los bloques con aviso (un punto en su fila: chats sin leer) se releen de fondo, se vea o no el dashboard
        setInterval(() => {
            if (!document.hidden) void this.bloques.leerAvisos().then(cambio => { if (cambio) this.alPintar?.(); });
        }, 60 * 1000);
        // lo que te espera, para el número de su fila: se lee ya y cada tanto, se vea o no su pestaña
        this.esperas.vigilar(() => this.alPintar?.());
        this.alCambiarFoco?.(true);
        void this.mensaje({ tipo: 'listo' });
    }

    /** La app que el panel muestra ahora, o "": la lista de la izquierda marca su fila. */
    get appActual(): string { return this.secciones.app; }

    /** Una app (`[apps.x]`): su página, en el panel. */
    async abrirApp(clave: string): Promise<void> {
        await this.secciones.abrir(`app:${clave}`);
        this.alCambiarFoco?.(true);
    }

    /** Releer el día y redibujar. No se salta aunque ya vaya otra: la que se pide después de marcar una tarea hecha se
     *  perdía tras una que iba desde antes y la traía abierta, y quedaba así hasta recargar. Las lecturas las junta
     *  dia.ts, que entrega a todos la que empezó después del último cambio. */
    async actualizar(conRed = false): Promise<void> {
        if (!this.panel) return;
        if (conRed) olvidarDia();
        // al abrir (o al recargar con un despliegue), lo que ya se sabe del día mientras llega la lectura
        if (!this.datos && (this.datos = diaGuardado())) this.render();
        this.datos = await dia(conRed ? 0 : 45000, conRed);
        this.render();
        void this.bloques.leer(conRed);
    }

    /** Redibuja la pantalla que se ve, sea o no de las que cambian con el reloj: cambió el mundo puesto (web/mundo.ts), y
     *  con él lo que se ve en todas. */
    repintar(): void {
        const duena = this.duena();
        if (!this.panel) return;
        if (duena) duena.pintar();
        else this.render();
        this.alPintar?.();
    }

    /** Redibuja con lo que hay: la marca «ahora» y los «hace» se mueven solos cada minuto. */
    render(): void {
        const duena = this.duena();
        if (duena) { if (this.panel && duena.conReloj.includes(this.actual)) duena.pintar(); return; }
        if (this.panel && this.pantalla === 'config') { this.configuracion.pintar(); return; }
    }

    /** Todas las pestañas que puede haber (sin ⚙), en su orden de siempre: las fijas, las de los
     *  bloques y las de los proveedores. Cada una: [clave, acción, valor, nombre, tecla]. */
    private todasLasPestanas(): Pestana[] {
        const d = this.datos;
        // las pestañas de los proveedores que las declaran (un feed), sin cuenta, como «tareas»: cuántos ítems tiene un
        // feed no es algo que haya que hacer
        const deProveedores = [...new Set((d?.pendientes ?? []).map(f => f.pestana ?? '').filter(Boolean))]
            .map(n => [`pestana:${n}`, 'pestana', n, n, this.pestanasCfg.find(x => x.nombre === n)?.tecla ?? ''] as Pestana);
        const todas: Pestana[] = [  // clave, acción, valor, nombre, tecla
            // ver y buscar todo (todo.ts): la vista del modo todo, primera en él; los demás modos no la nombran en sus
            // `filas`, y se llega por su modo (la cabecera, ⌥⇧4) o por «ver todo»
            ['todo', 'todo', '', 'todo', ''],
            // la vista de partida del orden por modos (tactica.ts): primera, sin reemplazar todavía a «ahora», foco ni
            // «te esperan» (lo decide el paso 2). Sin tecla; `[dashboard] orden` la mueve y ⚙ pestañas la oculta
            ['tactica', 'tactica', '', 'táctica', ''],
            ['ahora', 'ahora', '', 'ahora', 'n'],
            // lo que espera una decisión tuya (esperas.ts): su fila lleva cuántas preguntan. Va tras «ahora» aunque
            // `[dashboard] orden` no la nombre (orden-pestanas.ts)
            ['esperas', 'esperas', '', 'te esperan', 't'],
            // sin cuenta: con los filtros de la pestaña (esta semana, por revisar, vencidas…), un número solo confunde.
            // Abre en foco, su primera subpestaña; la lista entera es la segunda
            ['revisar', 'foco', '', 'tareas', 'v'],
            // cada bloque sin `dentro` es su propia pestaña (el correo de hoy)
            ...this.bloques.declarados.filter(b => !b.dentro).map(b =>
                [`bloque:${b.clave}`, 'bloque', b.clave, b.nombre, b.tecla ?? ''] as Pestana),
            ...deProveedores,
            ['proyectos', 'proyectos', '', 'proyectos', 'p'],
            ['calendario', 'calendario', '', 'calendario', 'a'],
            // las secciones (los agentes, babel) no: a su página se llega desde su fila en la lista de la izquierda. Los
            // periódicos y los mensajes entre agentes están en ⚙ (config/)
        ];
        return todas;
    }

    /** Las que se ven, en el orden elegido en ⚙ (`[dashboard] orden`), y de ellas, las del modo puesto (su ajuste
     *  `filas`, en su orden; `*` todas). Lo que no nombra el orden (orden-pestanas.ts): una de fábrica, tras la que la
     *  precede en el orden de siempre; la de un módulo o un proveedor, al final. */
    private pestanasVisibles(todas = this.todasLasPestanas()): Pestana[] {
        const visibles = ordenarPestanas(todas, x => x[0], this.dashOrden).filter(x => !this.dashOcultas.includes(x[0]));
        return delModo(visibles, x => x[0], modos.filas());
    }

    /** Buscar en todo (⌘K, su última fila): el modo todo, con eso escrito en su buscador. */
    buscarEnTodo(q: string): void {
        this.todoVista.preparar(q);
        if (!modos.cambiar('todo')) void ui.estado('telar: este mundo no tiene el modo todo (⚙ mundos › modos)', 4000);
    }

    /** La vista del modo puesto: la pestaña de su primera fila en DASHBOARD (táctica; proyectos en estrategia; todo). Si
     *  el modo no tiene ninguna que se vea, la de siempre. */
    async irAModo(): Promise<void> {
        const [primera] = this.pestanasVisibles();
        if (primera) await this.irAPestana(primera[1], primera[2]);
        else this.alFrente();
    }

    /** La pestaña que se ve (su clave): la ficha de una tarea es de la pestaña de donde se abrió, una conversación
     *  de su sección. La barra marca su fila. */
    pestanaActiva(): string {
        const marcada = this.duena()?.pestanaMarcada?.();
        if (marcada) return marcada;
        return this.pantalla;
    }

    /** Las pestañas del dashboard, en el orden y sin las ocultas de `[dashboard]`: las filas del grupo DASHBOARD de
     *  la barra: su nombre y la tecla que la abre con el dashboard a la vista. */
    pestanas(): { clave: string; accion: string; valor: string; nombre: string; tecla: string; aviso: string; cuenta?: number; cuentaAyuda?: string }[] {
        return this.pestanasVisibles().map(([clave, accion, valor, nombre, tecla]) =>
            ({ clave, accion, valor, nombre, tecla, aviso: accion === 'bloque' ? this.bloques.aviso(valor) : '',
                ...(clave === 'esperas' ? { cuenta: this.esperas.cuenta(), cuentaAyuda: this.esperas.cuentaAyuda() } : {}) }));
    }

    /** Las secciones de ⚙ que se ven (para el buscador). */
    seccionesConfig(): { clave: string; nombre: string; ayuda: string }[] { return this.configuracion.lista(); }

    /** ⚙: la configuración, en la sección `clave` (o en la última que se miró). */
    private async abrirConfig(clave = ''): Promise<void> {
        this.montar();
        this.ir('config');
        await this.configuracion.abrir(clave);
    }

    /** «táctica» con un día de mentira (componentes/muestras-tactica.ts), sin leer nada ni contestar nada: el ensayo de
     *  `window.telar.ensayoTactica` (navegador/app.ts). ↻ o su pestaña vuelven a lo de verdad. */
    async ensayoTactica(datos: Parameters<PantallaTactica['ensayo']>[0]): Promise<void> {
        await this.irAPestana('tactica');
        this.tactica.ensayo(datos);
    }

    /** Ir a una pestaña (una fila del grupo DASHBOARD, o el ⚙ de la cabecera): el dashboard a la vista, en ella. */
    async irAPestana(accion: string, valor = ''): Promise<void> {
        if (!this.panel) this.abrir(); else this.mostrarme?.();
        await this.mensaje({ tipo: 'accion', accion, valor });
    }

    /** Ir a una pestaña por su nombre o su clave (`calendario`, `tareas`, la de un módulo: `gantt` o `bloque:gantt`):
     *  la dirección `pestana:<nombre>` (`?abrir=pestana:gantt`, para que un ícono del teléfono abra una pestaña). Las de
     *  los módulos salen de la configuración y las de los proveedores, del día: se espera a leerlos. `callado`: si no
     *  está, nada (retomar la que se miraba al recargar: web/recarga.ts). */
    async irAPestanaNombrada(nombre: string, callado = false, item = ''): Promise<void> {
        this.montar();
        const buscar = () => this.pestanas().find(x => x.nombre === nombre || x.clave === nombre || (!!x.valor && x.valor === nombre));
        await this.configLeida;
        if (!buscar() && !this.datos) await this.actualizar();
        let p: { accion: string; valor: string } | undefined = buscar();
        if (!p && item) {
            // abrirla en un ítem suyo (el chat de una ventana de foco) vale aunque el modo puesto no la muestre: se pidió esa
            const t = this.todasLasPestanas().find(x => x[3] === nombre || x[0] === nombre || (!!x[2] && x[2] === nombre));
            if (t) p = { accion: t[1], valor: t[2] };
        }
        if (!p) { if (!callado) ui.estado(`telar: no hay una pestaña «${nombre}» en el dashboard`, 6000); return; }
        // abrirla en un ítem suyo (el chat de una ventana de foco): su lienzo lo recibe (Paginas.darItem)
        if (item && p.accion === 'bloque') this.paginas.darItem(`bloque:${p.valor}`, item);
        await this.irAPestana(p.accion, p.valor);
    }

    /** La configuración resuelta (`telar config`): los atajos, los bloques, las pestañas y su orden, quién es la
     *  persona y el agente general. Se lee al montar el dashboard. */
    private async leerAtajos(): Promise<void> {
        const r = await cli.config();
        this.cfg = r.datos ?? this.cfg;
        this.atajos = r.datos?.atajos ?? [];
        this.bloques.declarados = r.datos?.bloques ?? [];
        this.pestanasCfg = r.datos?.pestanas ?? [];
        this.dashOrden = r.datos?.dashboard?.orden ?? [];
        this.dashOcultas = r.datos?.dashboard?.ocultas ?? [];
        yo.persona = r.datos?.persona ?? '';
        yo.nombres = r.datos?.persona_nombres ?? [];
        this.agenteGeneral = r.datos?.agente_general?.clave ? { clave: r.datos.agente_general.clave, nombre: r.datos.agente_general.nombre ?? r.datos.agente_general.clave } : undefined;
        this.render();
        void this.bloques.leer();
    }

    /** Las teclas de las pestañas y de lo que vale en todas (r recarga, c el correo): mandan sobre las de
     *  [atajos]. */
    private teclasDePestanas(): Record<string, () => Promise<unknown>> {
        return {
            p: () => this.proyectos.abrir(), r: () => this.actualizar(true), v: () => this.tareas.abrirRevisar(),
            o: () => this.abrirConfig('periodicos'), a: () => this.planes.abrirCalendario(), n: () => this.ahora.abrir(),
            t: () => this.esperas.abrir(),
            ...Object.fromEntries(this.pestanasCfg.filter(x => x.tecla).map(x => [x.tecla, () => this.tareas.abrirPestana(x.nombre)])),
            ...Object.fromEntries(this.bloques.declarados.filter(b => b.tecla).map(b => [b.tecla!, () => this.bloques.abrir(b.clave)])),
            ...(modelo.hayBus ? { c: () => this.abrirConfig('agentes') } : {}),
        };
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

    /** Cambia un pedazo de la página sin repintarla: lo escrito en un formulario no se pierde. */
    parcial(id: string, html: string): void {
        this.panel?.parcial(id, html);
    }

    /** La página de una entrada del equipo (la abre su fila en la barra). */
    abrirEquipo(id: string): Promise<void> { return this.equipo.abrir(id); }

    /** Todos los agentes, con su estado y sus encargos (≡ en AGENTES, en la barra). */
    abrirAgentes(): Promise<void> { return this.agentesVista.abrir(); }

    /** La página de una sección o un agente (la abre su fila en la barra). */
    abrirSeccion(clave: string): Promise<void> { return this.secciones.abrir(clave); }

    /** La ficha de una tarea (la abre una orden de la barra, `telar.tarea`). */
    abrirTarea(valor: string, desde?: { nombre: string; ir: () => void }): Promise<void> { return this.tareas.abrirTarea(valor, desde); }

    /** El día, con lo del mundo puesto (web/mundo.ts): sus pendientes y sus eventos, y lo sin clasificar; con ambos o en
     *  todo, entero. Así lo filtran todas las pantallas que lo leen (tareas, foco, táctica, el calendario). Y con
     *  lo que salió de lo pendiente después de leerlo (dia.ts, `salio`): una tarea marcada hecha no vuelve mientras se relee. */
    dia(): Dia | undefined { return this.delMundo(this.datos && conLoSalido(this.datos)); }
    async diaLeido(): Promise<Dia> { return this.delMundo(conLoSalido(this.datos ??= diaGuardado() ?? await dia()))!; }
    private filtrado?: { de: Dia; mundo: string; dia: Dia };
    private delMundo(d: Dia | undefined): Dia | undefined {
        if (!d) return d;
        const clave = mundo.filtrando();
        if (!clave) return d;
        if (this.filtrado?.de === d && this.filtrado.mundo === clave) return this.filtrado.dia;
        const dia = { ...d, pendientes: d.pendientes.filter(f => mundo.seVe(f.mundo)), agenda: d.agenda?.filter(f => mundo.seVe(f.mundo)) ?? null };
        this.filtrado = { de: d, mundo: clave, dia };
        return dia;
    }
    async accion(accion: string, valor = ''): Promise<void> { await this.mensaje({ tipo: 'accion', accion, valor }); }
    bloqueAbierto(): string { return this.bloques.abierto(); }
    /** El nombre de una pestaña. */
    nombrePestana(clave: string): string { return this.todasLasPestanas().find(x => x[0] === clave)?.[3] ?? clave; }
    /** Los atajos que van en un bloque o una sección (`en = "<clave>"`), como acciones de su barra. */
    atajosEnBarra(en: string): AccionDePantalla[] {
        const deLasPestanas = this.teclasDePestanas();
        return this.atajos.filter(a => a.en === en).map(a => {
            // si su tecla es de una pestaña, va sin tecla (se lanza con un clic): el ícono del agente
            const ocupada = a.tecla in deLasPestanas;
            const ayuda = `${a.nombre}: ${a.descripcion || a.mensaje}${ocupada ? `\n(su tecla, «${a.tecla}», es de una pestaña: este atajo va con un clic)` : ` (${a.tecla})`}`;
            return { accion: 'atajo', valor: a.tecla, tecla: ocupada ? undefined : a.tecla, icono: ocupada ? I.agente : undefined, tono: 'violeta', ayuda };
        });
    }
    general(): { clave: string; nombre: string } | undefined { return this.agenteGeneral; }
    config(): cli.JsonConfig | undefined { return this.cfg; }

    /** Dibuja la pantalla que se ve: su barra (componentes/pantalla.ts) y su cuerpo. La barra lleva el nombre y la tinta
     *  de la pestaña (o lo que diga la pantalla: la ficha de una tarea, un bloque), y a la derecha sus vistas (las
     *  subpestañas), sus acciones y ↻. Nada más: lo que la pantalla resume va en el globo del título. */
    pintar(h: string[], b: EnBarra = {}): void {
        // la pestaña de un módulo dentro de una fija («gantt» en proyectos) es una vista de esa: la barra es la de ella
        const dentro = this.actual === 'bloque' ? this.bloques.dentroDelAbierto() : '';
        const deFija = dentro ? BARRA_DE[PESTANA_DE_SECCION[dentro] as NombrePantalla] ?? [dentro, ''] : undefined;
        const [nombre, color] = deFija ?? [b.nombre ?? BARRA_DE[this.actual]?.[0] ?? '', b.color ?? BARRA_DE[this.actual]?.[1] ?? ''];
        // la configuración no se relee: lo que se ve es lo que se escribe
        const releer = b.sinReleer || this.actual === 'config' ? []
            : [{ accion: 'refrescar', icono: I.releer, ayuda: `volver a leer lo que se ve (r)${b.leido ? `\n${b.leido}` : ''}` }];
        const html = barraPantalla({
            volver: b.volver,
            nombre,
            color,
            vistas: b.vistas ?? this.vistasDeBarra(),
            ayuda: b.ayuda,
            acciones: [...(b.acciones ?? []), ...releer],
        });
        // un proveedor caído ya no va arriba de cada pantalla: lo dice la franja de avisos (dashboard/dia.ts)
        this.panel?.pintar(h.join('\n'), html);
        this.alPintar?.();
    }

    /** Las vistas de la pestaña fija que se ve, en su barra: las de fábrica (tareas: foco y lista) o la fija misma, y
     *  cada bloque que dice `dentro` de ella («proyectos · gantt»), marcada la que se ve. Solo en la pantalla de la
     *  pestaña o de uno de sus bloques: la ficha de una tarea abierta desde ahí no las lleva. */
    private vistasDeBarra(): VistaDePantalla[] {
        const seccion = this.actual === 'bloque' ? this.bloques.dentroDelAbierto() : SECCION_DE_PANTALLA[this.actual] ?? '';
        const suyos = seccion ? this.bloques.declarados.filter(b => b.dentro === seccion) : [];
        const propias = SUBPESTANAS[seccion] ?? [];
        if (!suyos.length && !propias.length && seccion !== 'proyectos') return [];
        const fija = PESTANA_DE_SECCION[seccion];
        const abierto = this.actual === 'bloque' ? this.bloques.abierto().split(':')[0] : '';
        const vista = (accion: string, valor: string, nombre: string, si: boolean): VistaDePantalla =>
            ({ accion, valor, nombre, si, icono: ICONO_VISTA[nombre]?.[0], ayuda: ICONO_VISTA[nombre]?.[1] });
        // las de fábrica de la sección (tareas: foco y lista), las de proyectos (clientes, comercial, interno: las que hay en
        // el modo y el mundo puestos; y la tabla extendida), o la fija con el nombre de la sección
        const deProyectos = seccion === 'proyectos' ? this.proyectos.subvistas(!abierto && this.actual === 'proyectos') : null;
        const primeras = deProyectos ?? (propias.length ? propias.map(([accion, nombre, p]) => vista(accion, '', nombre, !abierto && this.actual === p))
            : [vista(fija, '', seccion, !abierto)]);
        return [...primeras, ...suyos.map(b => vista('bloque', b.clave, b.nombre, b.clave === abierto))];
    }

    /** La ventana de la instrucción que pide el lienzo de un módulo (`window.lienzo.pedir("instruccion")`), con su
     *  contexto, que va entero, y de dónde viene (la pestaña o la app, que pone la página: el lienzo no lo elige). A
     *  quién: el que pidió el lienzo, o el de la configuración (`[instruccion] destino`); sin ninguno, como abre sin
     *  entidad. Lo que recibe el lienzo: a quién llegó y cómo, o null si se canceló. */
    private async instruccionDeLienzo(p: PedidoDeLienzo, llave: string): Promise<unknown> {
        const [tipo, ...resto] = this.paginas.origenDe(llave).split(':');
        const clave = resto.join(':');
        const nombre = tipo === 'bloque' ? this.bloques.declarados.find(b => b.clave === clave)?.nombre ?? clave
            : tipo === 'app' ? modelo.apps.find(a => a.clave === clave)?.nombre ?? clave : clave;
        const desde = !nombre ? '' : tipo === 'bloque' ? `la pestaña «${nombre}»` : tipo === 'app' ? `la app «${nombre}»` : `«${nombre}»`;
        const agentes = modelo.secciones.filter(x => x.grupo === 'agentes');
        let a = p.destino ? nombreDeDestino(p.destino, agentes) : modelo.instruccionA;
        if (a && !agentes.some(x => x.nombre === a) && !modelo.hilos.some(h => h.nombre === a)) {
            ui.estado(`no encuentro a «${a}» (${p.destino ? 'lo pidió la pestaña' : '[instruccion] destino'}): elige a quién`, 6000);
            a = '';
        }
        const { texto, titulo, direccion } = p.contexto;
        const { abrir } = await import('../../web/instruccion');
        const r = await abrir({
            ...(texto.trim() ? { contexto: { texto, titulo, origen: desde } } : {}),
            ...(direccion ? { direccion } : {}), ...(titulo ? { titulo, nombre: titulo } : {}),
            ...(a ? { a } : {}), ...(p.texto ? { texto: p.texto } : {}),
        });
        return r ? { destino: r.destino, como: r.como, maquina: r.maquina ?? '' } : null;
    }

    /** Lo que manda la página: teclas, clics (acciones) y lo que guarda un lienzo. Cada acción es de la pantalla
     *  que la declara; aquí quedan las de todas (ir a un hilo, ⚙, un atajo, abrir un enlace). */
    private async mensaje(m: MensajeDia): Promise<void> {
        // ir a una pestaña antes de que el panel esté listo (retomar la que se miraba al recargar) gana sobre la de partida
        if (m.tipo === 'accion') this.deEntrada = false;
        if (m.tipo === 'lienzo-guardar') { this.paginas.guardar(m.valor ?? '', m.datos ?? ''); return; }
        if (m.tipo === 'lienzo-aviso') {
            // el de su pestaña, o el de su configuración (cambiar qué avisa cambia el punto de su pestaña)
            const origen = this.paginas.origenDe(m.valor ?? '');
            const clave = origen.startsWith('bloque:') ? origen.slice(7) : origen.startsWith('config:') ? origen.slice(7) : '';
            if (clave && this.bloques.ponerAviso(clave, m.datos ?? '')) this.alPintar?.();
            return;
        }
        if (m.tipo === 'lienzo-pedir') {
            const { id, datos } = JSON.parse(m.datos ?? '{}') as { id: string; datos: unknown };
            // el menú de una entidad, abrirla y la instrucción no se le piden a telar ni piden permiso: solo muestran;
            // lo que se elige en el menú o se manda en la instrucción, se elige y se manda aquí (pedidos-locales.ts)
            const local = atenderLocal(m.accion ?? '', datos, m.donde,
                { menu: (d, donde) => entidades.menuDe(d, donde), abrir: d => ui.abrirDireccion(d),
                    instruccion: p => this.instruccionDeLienzo(p, m.valor ?? ''),
                    // el menú de la casa con lo que trae el lienzo (sus pestañas que no caben, un filtro plegado): el índice
                    opciones: async (p, donde) => (await ui.menu(p.opciones.map((o, i) => ({ ...o, i })), donde, p.titulo))?.i },
                r => this.panel?.responderLienzo(id, r));
            if (local) { await local; return; }
            const respuesta = await this.paginas.pedir(m.valor ?? '', m.accion ?? '', datos);
            this.panel?.responderLienzo(id, respuesta);
            return;
        }
        // un enlace, antes que nada que espere: Safari abre la pestaña solo en el gesto del clic (web/abrir.ts)
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await ui.abrirExterno(m.url); return; }
        // lo de una sección de ⚙ (sus acciones, sus formularios) lo atiende ella
        if (this.pantalla === 'config' && m.tipo !== 'tecla' && m.tipo !== 'listo' && await this.configuracion.atender(m)) return;
        if (m.tipo === 'listo') {
            // un panel recién abierto para una sección pierde lo que se le mandó antes de estar listo
            if (this.pantalla === 'seccion') this.secciones.pintar();
            // el dashboard abre en la vista del modo puesto (táctica, la de partida: docs/propuestas/orden-por-modos.md),
            // salvo que ya se haya pedido otra; si se queda en «ahora», su contexto (el plan, los proyectos) se pide aquí
            if (this.deEntrada && this.pantalla === 'ahora') { this.deEntrada = false; void this.irAModo(); }
            else if (this.pantalla === 'ahora') void this.ahora.abrir();
            this.render(); void this.actualizar(); return;
        }
        if (m.tipo === 'tecla' && m.k) {
            // las de la pantalla primero; después las de las pestañas, que valen en todas; y al final los atajos de
            // [atajos]: uno con la tecla de una pestaña no la pisa (ir a «ahora» con la n no puede lanzar /sincronizar)
            const globales: Record<string, () => Promise<unknown>> = {
                ...Object.fromEntries(this.atajos.map(a => [a.tecla, () => this.lanzarAtajo(a.tecla)])),
                ...this.teclasDePestanas(),
            };
            await (this.teclas.get(m.k) ?? globales[m.k])?.();
            return;
        }
        if (m.tipo !== 'accion') return;
        const deUna = this.acciones()[m.accion ?? ''];
        if (deUna) { await deUna(m.valor ?? '', m); return; }
        switch (m.accion) {
            case 'ir': if (m.valor) await ui.irAHilo(m.valor); break;
            case 'refrescar': await this.actualizar(true); break;
            case 'volver': void ui.mostrarTerminal(); break;
            case 'config': await this.abrirConfig(m.valor ?? ''); break;
            case 'atajo': if (m.valor) await this.lanzarAtajo(m.valor); break;
            case 'abrir-enlace': if (m.valor) await abrirEnlace(m.valor); break;
            case 'abrir-ruta':
                // una ruta relativa a la raíz de telar (la que traen las notas de un evento)
                if (m.valor && !m.valor.includes('..') && modelo.raiz) await abrirEnlace(rutas.unir(modelo.raiz, m.valor));
                break;
        }
    }
}

/** Una pestaña del dashboard: [clave, acción, valor, nombre, tecla]. */
type Pestana = [string, string, string, string, string];
