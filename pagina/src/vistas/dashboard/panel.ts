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

import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { esc, hace } from '../../estilo';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, atajo, dia, olvidarDia, pendientes, seccion, yo } from './dia';
import { PantallaPlan } from './plan';
import { PantallaProyectos } from './proyectos';
import { PantallaAhora } from './ahora';
import { Configuracion } from './config/configuracion';
import { type Accion, type NombrePantalla, type Pantalla, type Tablero, abrirEnlace } from './pantalla';
import { type MensajeDia, montarDia, type VistaDia } from './vista';
import { PantallaEquipo } from './equipo';
import { PantallaAgentes } from './agentes';
import { Paginas } from './pagina';
import { PantallaTareas } from './tareas';
import { PantallaBloques } from './bloques';
import { PantallaSecciones } from './secciones';

export class Dashboard implements Tablero {
    /** el dashboard en la página, ya montado (vista.ts); hasta abrirlo, nada */
    panel?: VistaDia;
    /** dónde se dibuja (un elemento de la página) y cómo se lo trae al frente: los da la página (src/navegador) */
    donde?: () => HTMLElement;
    mostrarme?: () => void;
    private datos?: Dia;
    private actual: NombrePantalla = 'ahora';
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
    /** las teclas que declara `[atajos]`; se leen al montar el dashboard (`leerAtajos`) */
    private atajos: cli.JsonAtajo[] = [];
    private enCurso = false;
    readonly teclas = new Map<string, () => Promise<unknown> | unknown>();
    /** las pantallas que viven en su archivo, con sus acciones (pantalla.ts) */
    private readonly equipo = new PantallaEquipo(this);
    private readonly agentesVista = new PantallaAgentes(this);
    readonly planes: PantallaPlan = new PantallaPlan(this);
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
    private get modulos(): Pantalla[] { return [this.ahora, this.tareas, this.bloques, this.proyectos, this.planes, this.secciones, this.equipo, this.agentesVista]; }
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
        dashboard: {
            dia: () => this.datos,
            actualizar: conRed => this.actualizar(conRed),
            // el nombre sin su cuenta («leer», no «leer 17»)
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
        void this.leerAtajos();
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

    async actualizar(conRed = false): Promise<void> {
        if (!this.panel || this.enCurso) return;
        this.enCurso = true;
        try {
            if (conRed) olvidarDia();
            this.datos = await dia(conRed ? 0 : 45000, conRed);
            this.render();
            void this.bloques.leer(conRed);
        } finally { this.enCurso = false; }
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
        // las pestañas de los proveedores que las declaran (un feed), con cuántos ítems tienen
        const deProveedores = [...new Set((d?.pendientes ?? []).map(f => f.pestana ?? '').filter(Boolean))]
            .map(n => [`pestana:${n}`, 'pestana', n, `${n} ${d ? pendientes(d, n).length : ''}`.trim(),
                this.pestanasCfg.find(x => x.nombre === n)?.tecla ?? ''] as Pestana);
        const todas: Pestana[] = [  // clave, acción, valor, nombre, tecla
            ['ahora', 'ahora', '', 'ahora', 'n'],
            // sin cuenta: con los filtros de la pestaña (esta semana, por revisar, vencidas…), un número solo confunde
            ['revisar', 'revisar', '', 'tareas', 'v'],
            // cada bloque sin `en` es su propia pestaña (el correo de hoy)
            ...this.bloques.declarados.filter(b => !b.en).map(b =>
                [`bloque:${b.clave}`, 'bloque', b.clave, b.nombre, b.tecla ?? ''] as Pestana),
            ...deProveedores,
            ['proyectos', 'proyectos', '', 'proyectos', 'p'],
            ['plan', 'plan', '', 'plan', 'd'],
            ['calendario', 'calendario', '', 'calendario', 'a'],
            // las secciones (los agentes, babel) no: a su página se llega desde su fila en la lista de la izquierda. Los
            // periódicos y los mensajes entre agentes están en ⚙ (config/)
        ];
        return todas;
    }

    /** Las que se ven, en el orden elegido en ⚙ (`[dashboard] orden`); las que no se nombran van
     *  después, en su orden de siempre, así una pestaña nueva (un módulo) aparece sola. */
    private pestanasVisibles(todas = this.todasLasPestanas()): Pestana[] {
        const pos = (c: string) => { const i = this.dashOrden.indexOf(c); return i < 0 ? this.dashOrden.length + todas.findIndex(x => x[0] === c) : i; };
        return todas.filter(x => !this.dashOcultas.includes(x[0])).sort((a, b) => pos(a[0]) - pos(b[0]));
    }

    /** Lo que va arriba de cada pantalla: un proveedor caído se dice en todas (el calendario, además, en la suya).
     *  Las pestañas están en la barra de la izquierda (el grupo DASHBOARD, vistas/hilos.ts), y la configuración en
     *  el ⚙ de la cabecera de la página. */
    private nav(): string {
        const caidos = (this.datos?.fallas ?? []).filter(f => !f.startsWith('calendario'));
        return caidos.map(f => `<div class="fila falla">caído · ${esc(f)}</div>`).join('');
    }

    /** La pestaña que se ve (su clave): la ficha de una tarea es de la pestaña de donde se abrió, una conversación
     *  de su sección. La barra marca su fila. */
    pestanaActiva(): string {
        const marcada = this.duena()?.pestanaMarcada?.();
        if (marcada) return marcada;
        return this.pantalla;
    }

    /** Las pestañas del dashboard, en el orden y sin las ocultas de `[dashboard]`: las filas del grupo DASHBOARD de
     *  la barra. El nombre lleva su cuenta («tareas ◆45»), y la tecla es la que la abre con el dashboard a la vista. */
    pestanas(): { clave: string; accion: string; valor: string; nombre: string; tecla: string }[] {
        return this.pestanasVisibles().map(([clave, accion, valor, nombre, tecla]) => ({ clave, accion, valor, nombre, tecla }));
    }

    /** Las secciones de ⚙ que se ven (para el buscador). */
    seccionesConfig(): { clave: string; nombre: string; ayuda: string }[] { return this.configuracion.lista(); }

    /** ⚙: la configuración, en la sección `clave` (o en la última que se miró). */
    private async abrirConfig(clave = ''): Promise<void> {
        this.montar();
        this.ir('config');
        await this.configuracion.abrir(clave);
    }

    /** Ir a una pestaña (una fila del grupo DASHBOARD, o el ⚙ de la cabecera): el dashboard a la vista, en ella. */
    async irAPestana(accion: string, valor = ''): Promise<void> {
        if (!this.panel) this.abrir(); else this.mostrarme?.();
        await this.mensaje({ tipo: 'accion', accion, valor });
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
            o: () => this.abrirConfig('periodicos'), d: () => this.planes.abrirPlan(''), a: () => this.planes.abrirCalendario(), n: () => this.ahora.abrir(),
            ...Object.fromEntries(this.pestanasCfg.filter(x => x.tecla).map(x => [x.tecla, () => this.tareas.abrirPestana(x.nombre)])),
            ...Object.fromEntries(this.bloques.declarados.filter(b => !b.en && b.tecla).map(b => [b.tecla!, () => this.bloques.abrir(b.clave)])),
            ...(modelo.hayBus ? { c: () => this.abrirConfig('agentes') } : {}),
        };
    }

    /** El botón de un atajo de [atajos]. Si su tecla es de una pestaña, va sin tecla: se lanza con un clic. */
    private botonAtajo(a: cli.JsonAtajo): string {
        const ocupada = a.tecla in this.teclasDePestanas();
        const ayuda = a.descripcion || a.mensaje;
        return atajo(ocupada ? '' : a.tecla, a.nombre, 'atajo', a.tecla,
            ocupada ? `${ayuda}\n(su tecla, «${a.tecla}», es de una pestaña: este atajo va con un clic)` : ayuda);
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

    dia(): Dia | undefined { return this.datos; }
    async diaLeido(): Promise<Dia> { return this.datos ??= await dia(); }
    async accion(accion: string, valor = ''): Promise<void> { await this.mensaje({ tipo: 'accion', accion, valor }); }
    bloqueAbierto(): string { return this.bloques.abierto(); }
    bloquesEn(en: string): string[] { return this.bloques.html(this.bloques.declarados.filter(b => b.en === en), true); }
    /** El nombre de una pestaña sin su cuenta («leer», no «leer 17»). */
    nombrePestana(clave: string): string {
        const p = this.todasLasPestanas().find(x => x[0] === clave);
        return !p ? clave : clave.startsWith('pestana:') ? p[2] : p[3];
    }
    /** Los botones de los atajos que van en un bloque o una sección (`en = "<clave>"`). */
    atajosEn(en: string): string { return this.atajos.filter(a => a.en === en).map(a => this.botonAtajo(a)).join(''); }
    general(): { clave: string; nombre: string } | undefined { return this.agenteGeneral; }
    config(): cli.JsonConfig | undefined { return this.cfg; }

    pintar(h: string[]): void {
        this.panel?.pintar(this.nav() + h.join('\n'));
        this.alPintar?.();
    }

    /** Lo que manda la página: teclas, clics (acciones) y lo que guarda un lienzo. Cada acción es de la pantalla
     *  que la declara; aquí quedan las de todas (ir a un hilo, ⚙, un atajo, abrir un enlace). */
    private async mensaje(m: MensajeDia): Promise<void> {
        if (m.tipo === 'lienzo-guardar') { this.paginas.guardar(m.valor ?? '', m.datos ?? ''); return; }
        // lo de una sección de ⚙ (sus acciones, sus formularios) lo atiende ella
        if (this.pantalla === 'config' && m.tipo !== 'tecla' && m.tipo !== 'listo' && await this.configuracion.atender(m)) return;
        if (m.tipo === 'listo') {
            // un panel recién abierto para una sección pierde lo que se le mandó antes de estar listo
            if (this.pantalla === 'seccion') this.secciones.pintar();
            // el dashboard abre en «ahora»: su contexto (el plan, los proyectos) se pide aquí
            if (this.pantalla === 'ahora') void this.ahora.abrir();
            this.render(); void this.actualizar(); return;
        }
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await ui.abrirExterno(m.url); return; }
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
