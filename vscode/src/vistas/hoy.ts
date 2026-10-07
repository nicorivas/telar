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

import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

import { irAHilo, mostrarTerminal } from '../acciones';
import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, esc, hace, haceCorto, hhmm, marco, normalizar, nuevoNonce } from '../estilo';
import { modelo } from '../modelo';
import { CSS_DIA, Dia, SCRIPT_DIA, atajo, dia, filtroAreas, filtroDuenos, htmlPendientes, olvidarDia, pendientes, pista, plazo, seccion } from './dia';
import { CSS_PLAN, eventosDelDia, htmlCalendario, htmlPlan } from './plan';
import { llevarPendiente, marcarHecha } from './tareas';

export class PanelHoy {
    panel?: vscode.WebviewPanel;
    private datos?: Dia;
    private pantalla: 'dia' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'correo' | 'tarea' | 'revisar' | 'pestana' | 'periodicos' | 'plan' | 'calendario' = 'dia';
    /** el plan del día que se está mirando (`telar resultado plan`), y el error si no llegó */
    private plan?: cli.JsonResultado;
    private planError = '';
    private planCargando = false;
    /** las notas de los eventos de hoy, y el evento elegido en el calendario */
    private notas?: cli.JsonNotas;
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
    private fichaDesde = 'dia';
    /** la pestaña de proveedor abierta (`pestana` del proveedor: «leer») */
    private pestana = '';
    /** fichas ya pedidas: una pestaña de proveedor puede estar lejos (el feed se pide por ssh
     *  a otro continente, ~0,5 s cada una), así que se piden antes de que se abran */
    private fichas = new Map<string, { pagina: cli.JsonPagina; hora: number }>();
    /** las pestañas de proveedor declaradas y su tecla (`telar config --json`) */
    private pestanasCfg: cli.JsonPestana[] = [];
    /** la ficha abierta: de qué proveedor, su id y su ref (con la que se lleva al hilo) */
    private ficha?: { proveedor: string; id: string; ref: string; pagina?: cli.JsonPagina; aviso?: string };
    /** las propuestas ya decididas en esta pasada: ← → las saltan aunque el día no se haya releído */
    private decididas = new Set<string>();
    /** el correo con cuerpos, leído al entrar a la pantalla; y el filtro elegido */
    private buzones?: cli.JsonBuzon[];
    /** los mensajes entre hilos por el bus (undefined: sin bus o sin leer) */
    private mensajesBus?: cli.JsonMensajeBus[];
    private abiertoMsg = new Set<string>();
    private filtroCorreo: 'todas' | 'mias' | 'sin' = 'todas';
    /** la sección abierta y su página; la conversación que se está leyendo */
    private seccion = '';
    private pagina?: cli.JsonPagina;
    private charla?: cli.JsonConversacion;
    /** el nonce del CSP del panel: los lienzos lo necesitan para que corran sus scripts */
    private nonce = nuevoNonce();
    /** las memorias de los lienzos pintados: una llave al azar por lienzo → el archivo que declaró
     *  su página. El lienzo solo escribe ese archivo, y lo nombra con la llave, nunca con una ruta. */
    private memorias = new Map<string, string>();
    private proyectos?: cli.JsonProyecto[];
    private avisoProyectos = '';
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

    /** ⌥H: si el dashboard ya está al frente, devuelve el teclado al terminal. */
    alternar(): void {
        if (this.panel?.active) { void mostrarTerminal(); return; }
        this.abrir();
    }

    abrir(): void {
        if (this.panel) { this.panel.reveal(vscode.ViewColumn.Active, false); void this.actualizar(); return; }
        const panel = vscode.window.createWebviewPanel('telar.hoy', 'dashboard',
            { viewColumn: vscode.ViewColumn.Active, preserveFocus: false },
            { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [] });
        this.panel = panel;
        void this.leerAtajos();
        panel.iconPath = new vscode.ThemeIcon('calendar');
        panel.webview.onDidReceiveMessage(m => void this.mensaje(m));
        panel.onDidDispose(() => { this.panel = undefined; });
        panel.onDidChangeViewState(e => { if (e.webviewPanel.visible) void this.actualizar(); });
        this.pintarMarco();
    }

    pintarMarco(): void {
        if (this.panel) {
            this.nonce = nuevoNonce();
            this.panel.webview.html = marco(this.panel.webview, CSS_DIA + CSS_PLAN,
                '<div id="dia"><div class="aviso">leyendo el día…</div></div>', SCRIPT_DIA, this.nonce);
        }
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
        // la lista de proyectos no cambia con el reloj: repintarla cada minuto solo movería el scroll
        if (this.panel && this.pantalla === 'proyectos') return;
        // lo mismo con la página de una sección y una conversación: no dependen del reloj
        if (this.panel && (this.pantalla === 'seccion' || this.pantalla === 'conversacion' || this.pantalla === 'correo' || this.pantalla === 'tarea')) return;
        const d = this.datos;
        if (!this.panel || !d) return;
        this.teclas.clear();
        const ahora = new Date();
        const h: string[] = [];
        // arriba, lo general: los atajos que no son de ninguna sección, las tareas y el terminal
        h.push('<div class="generales">' + this.atajos.filter(a => (a.en ?? 'hoy') === 'hoy')
            .map(a => atajo(a.tecla, a.nombre, 'atajo', a.tecla, a.descripcion || a.mensaje)).join('')
            + atajo('t', 'tareas', 'tareas', '', 'la vista de tareas') + atajo('⎋', 'terminal', 'volver', '', 'volver al terminal') + '</div>');
        h.push(...this.agenda(d, ahora), ...this.bloques(), ...this.hilos(), ...htmlPendientes(d, false), ...this.fallas(d));
        for (const [k, f] of [['r', () => this.actualizar(true)], ['p', () => this.abrirProyectos()],
            ['t', () => vscode.commands.executeCommand('telar.tareas')]] as const) {
            if (!this.teclas.has(k)) this.teclas.set(k, f);
        }
        this.pintar(h);
    }

    /** La barra de arriba, igual en todas las pestañas y fija al desplazarse: la marca, el
     *  reloj y las pestañas. Cambiar de pestaña es un clic; no hay que «volver» a ninguna parte. */
    private nav(): string {
        const d = this.datos;
        const ahora = new Date();
        const activa = this.pantalla === 'conversacion' ? `seccion:${this.seccion}`
            : this.pantalla === 'seccion' ? `seccion:${this.seccion}` : this.pantalla === 'tarea' ? this.fichaDesde
            : this.pantalla === 'pestana' ? `pestana:${this.pestana}` : this.pantalla;
        // las pestañas de los proveedores que las declaran (un feed), con cuántos ítems tienen
        const deProveedores = [...new Set((d?.pendientes ?? []).map(f => f.pestana ?? '').filter(Boolean))]
            .map(n => [`pestana:${n}`, 'pestana', n, `${n} ${d ? pendientes(d, n).length : ''}`.trim(),
                this.pestanasCfg.find(x => x.nombre === n)?.tecla ?? ''] as [string, string, string, string, string]);
        const aRevisar = this.propuestas('').length;
        const pestanas: [string, string, string, string, string][] = [  // clave, acción, valor, nombre, tecla
            ['dia', 'dia', '', 'hoy', ''],
            ['revisar', 'revisar', '', aRevisar ? `revisar ${aRevisar}` : 'revisar', 'v'],
            ...deProveedores,
            ['proyectos', 'proyectos', '', 'proyectos', 'p'],
            ['plan', 'plan', '', 'plan', 'd'],
            ['calendario', 'calendario', '', 'calendario', 'a'],
            ['periodicos', 'periodicos', '', 'periódicos', 'o'],
            ...(modelo.hayRemotos ? [['correo', 'correo', '', 'agentes', 'c'] as [string, string, string, string, string]] : []),
            ...modelo.secciones.filter(x => x.home).map(x =>
                [`seccion:${x.clave}`, 'seccion', x.clave, x.nombre.toLowerCase(), ''] as [string, string, string, string, string]),
            ['config', 'config', '', '⚙', ''],
        ];
        return '<div class="fijo"><header class="top"><div class="marca-t"><span class="logo">telar</span>'
            + (d ? `<span class="fecha">${esc(fechaLarga(d.nombreDia, d.fecha))}</span>` : '')
            + `<span class="reloj">${ahora.toTimeString().slice(0, 5)}</span>${d?.semana ? `<span class="sem">s${d.semana}</span>` : ''}</div>`
            + atajo('r', 'recargar', 'refrescar', '', 'recargar, proveedores incluidos') + '</header>'
            + '<nav class="tabs">' + pestanas.map(([clave, accion, valor, nombre, tecla]) =>
                `<a class="tab${clave === activa ? ' activa' : ''}" data-accion="${accion}"${valor ? ` data-valor="${esc(valor)}"` : ''}>`
                + `${tecla ? `<kbd>${tecla}</kbd> ` : ''}${esc(nombre)}</a>`).join('') + '</nav>'
            + '<div class="regla"></div></div>';
    }

    private agenda(d: Dia, ahora: Date): string[] {
        const t = ahora.getTime();
        const filas = d.agenda ?? [];
        const quedan = filas.filter(e => Date.parse(e.cuando ?? '') > t).length;
        const h = [seccion('agenda', 'azul', d.agenda?.length ? `${quedan}/${filas.length}` : '')];
        const fin = (x: string) => [...h, x, '</section>'];
        if (d.error) return fin(`<div class="vacio falla">${esc(d.error)}</div>`);
        const falla = d.fallas.find(f => f.startsWith('calendario'));
        if (falla) return fin(`<div class="vacio falla">calendario caído · <a data-accion="config">configurar</a></div>`);
        if (d.agenda === null) {
            return fin(d.declarados.length ? '<div class="vacio">sin consultar · <kbd>r</kbd></div>'
                : '<div class="vacio">sin calendario · <a data-accion="config">conectar</a></div>');
        }
        if (!filas.length) return fin('<div class="vacio">nada con hora</div>');
        const proxima = filas.find(e => Date.parse(e.cuando ?? '') > t);
        for (const e of filas) {
            const cuando = e.cuando ?? '';
            const url = e.url ?? '';
            const hilo = e.hilo ? `<span class="hilo-ag">${esc(e.hilo)}</span>` : '';
            // un clic en cualquier evento abre su hilo; telar decide qué skill según si ya
            // empezó (preparar o minuta) y las reglas de `[agenda]`
            const valor = esc(JSON.stringify([e.texto, hhmm(cuando), url, e.id]));
            if (Date.parse(cuando) <= t) {
                h.push(`<div class="ag pasada clic" data-accion="reunion" data-valor="${valor}" title="clic: la minuta">`
                    + `<span class="hora">${esc(hhmm(cuando))}</span>`
                    + `<span class="que">${esc(e.texto)}</span><span class="extra">${hilo}</span></div>`);
                continue;
            }
            const esProxima = e === proxima;
            let falta = '';
            if (esProxima) {
                const min = Math.floor((Date.parse(cuando) - t) / 60000);
                falta = `<span class="falta">${min <= 0 ? 'ahora' : min < 90 ? `${min}m` : `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`}</span>`;
            }
            const entrar = url ? `<a class="enlace" data-url="${esc(url)}" title="${esc(url)}">entrar ↗</a>` : '';
            h.push(`<div class="ag clic${esProxima ? ' proxima' : ''}" data-accion="reunion" data-valor="${valor}" title="clic: preparar">`
                + `<span class="hora">${esProxima ? '<i class="punto">●</i>' : ''}${esc(hhmm(cuando))}</span>`
                + `<span class="que">${esc(e.texto)}</span><span class="extra">${hilo}${falta}${entrar}</span></div>`);
        }
        return [...h, '</section>'];
    }

    private hilos(): string[] {
        const orden: Record<string, number> = { espera: 0, termino: 1, trabajando: 2 };
        const filas = modelo.enLista
            .filter(x => x.atencion in orden)
            .sort((a, b) => orden[a.atencion] - orden[b.atencion] || a.nombre.localeCompare(b.nombre));
        const esperan = filas.filter(x => x.atencion === 'espera').length;
        const h = [seccion('esperan', 'amarillo', filas.length ? `${esperan}/${filas.length}` : '',
            '<span class="leyenda">○ espera  ✓ listo  ● trabaja</span>')];
        if (!filas.length) return [...h, '<div class="vacio">nadie</div>', '</section>'];
        for (const x of filas) {
            h.push(`<div class="hl clic" data-accion="ir" data-valor="${esc(x.nombre)}" title="${esc(NOMBRE_ATENCION[x.atencion] ?? x.atencion)}">`
                + `<span class="at ${x.atencion}">${GLIFO[x.atencion]}</span>`
                + `<span class="nombre">${esc(cli.nombreVisible(modelo.hilos.find(y => y.nombre === x.nombre) ?? x))}</span>`
                + `<span class="cuando">${esc(haceCorto(x.visto))}</span></div>`);
        }
        return [...h, '</section>'];
    }

    private async leerAtajos(): Promise<void> {
        const r = await cli.config();
        this.atajos = r.datos?.atajos ?? [];
        this.bloquesCfg = r.datos?.bloques ?? [];
        this.pestanasCfg = r.datos?.pestanas ?? [];
        this.render();
        void this.leerBloques();
    }

    /** Los bloques del día (`[bloques.<clave>]`): una sección cada uno, con su color, su cuenta
     *  y en el título los atajos que dicen `en = "<clave>"`. Lo que muestran lo pide
     *  `leerBloques`, aparte y con el ritmo de la red: un comando lento no frena el día. */
    private bloques(): string[] {
        const h: string[] = [];
        for (const b of this.bloquesCfg) {
            const leido = this.bloquesDatos.get(b.clave);
            const suyos = this.atajos.filter(a => a.en === b.clave)
                .map(a => atajo(a.tecla, a.nombre, 'atajo', a.tecla, a.descripcion || a.mensaje)).join('');
            h.push(seccion(b.nombre, b.color, leido?.pagina?.subtitulo ?? '', suyos));
            if (!leido) h.push('<div class="vacio">leyendo…</div>');
            else if (leido.error) h.push(`<div class="vacio falla">${esc(leido.error)}</div>`);
            else {
                const items = (leido.pagina?.bloques ?? []).flatMap(x => x.items ?? []);
                if (!items.length) h.push('<div class="vacio">nada</div>');
                items.forEach((x, i) => {
                    const clic = x.mensaje ? ` data-accion="abrir-item" data-valor="${esc(b.clave)}:${i}"` : '';
                    h.push(`<div class="cr${x.destacado ? ' nuevo' : ''}${clic ? ' clic' : ''}"${clic}`
                        + ` title="${esc(x.mensaje ? `clic: un hilo para esto (${x.mensaje})` : x.titulo)}"><span class="mk">${esc(x.marca ?? '·')}</span>`
                        + `<span class="hora">${esc((x.fecha ?? '').slice(11, 16))}</span>`
                        + `<span class="de">${esc(x.texto ?? '')}</span><span class="que">${esc(x.titulo)}</span></div>`);
                });
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
            this.bloquesDatos.set(b.clave, { pagina: r.datos, error: r.datos ? '' : (r.error ?? 'no contestó'), hora: Date.now() });
            if (this.pantalla === 'dia') this.render();
        }));
    }

    /** Un clic en una fila de un bloque que trae `mensaje`: un hilo nuevo para esa fila. */
    private async abrirItem(valor: string): Promise<void> {
        const corte = valor.lastIndexOf(':');
        const clave = valor.slice(0, corte);
        const x = (this.bloquesDatos.get(clave)?.pagina?.bloques ?? []).flatMap(b => b.items ?? [])[Number(valor.slice(corte + 1))];
        if (!x?.mensaje) return;
        const r = await cli.abrirItem(clave, x.mensaje, x.nombre || x.titulo);
        if (!r.datos) {
            void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no pude abrir el hilo'}`);
            return;
        }
        await modelo.sondear();
        await mostrarTerminal();
    }

    private async lanzarAtajo(tecla: string): Promise<void> {
        const nombre = this.atajos.find(a => a.tecla === tecla)?.nombre ?? tecla;
        const r = await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: `telar: ${nombre}…` }, () => cli.atajo(tecla));
        if (!r.datos) {
            void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no pude abrir el atajo'}`);
            return;
        }
        await modelo.sondear();
        await mostrarTerminal();
    }

    /** La página de una sección: la pide a `telar seccion`, que corre su `home`. Abre el
     *  panel si hace falta; el refresco del día no la pisa (ver `render`). */
    async abrirSeccion(clave: string): Promise<void> {
        this.abrir();
        this.pantalla = 'seccion';
        if (this.seccion !== clave) { this.seccion = clave; this.pagina = undefined; }
        const nombre = modelo.secciones.find(s => s.clave === clave)?.nombre ?? clave;
        if (!this.pagina) this.pintar([`<div class="subcab"><b>${esc(nombre)}</b></div>`, '<div class="fila dim">leyendo…</div>']);
        const r = await cli.seccion(clave);
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
        else if (!this.panel.visible) this.panel.reveal(undefined, false);
        if (this.pantalla === 'revisar' || this.pantalla === 'dia') this.fichaDesde = this.pantalla;
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

    /** La pestaña «revisar»: lo que un agente dejó para decidir, entero y en una lista. Un clic
     *  abre la ficha; ← → pasa de una a otra y al decidir salta a la siguiente. */
    private async abrirRevisar(): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'revisar';
        this.fichaDesde = 'revisar';
        if (!this.datos) this.datos = await dia();
        this.renderRevisar();
    }

    private renderRevisar(): void {
        const d = this.datos;
        if (!d) return;
        this.teclas.clear();
        const lista = pendientes(d).filter(p => p.avance && p.fila.ficha && !this.decididas.has(p.fila.id || p.ref));
        const h = ['<div id="revisar">', seccion('revisar', 'cian', lista.length ? String(lista.length) : '', lista.length ? pista('⏎', 'la primera') : ''),
            filtroAreas(lista.map(p => p.fila.area ?? '')), filtroDuenos(lista.map(p => p.fila.dueno ?? ''))];
        if (!lista.length) h.push('<div class="vacio">nada que decidir: lo que un agente proponga aparece aquí</div>');
        lista.forEach((p, i) => {
            const [todo] = (p.fila.avance ?? '').split(' ');
            const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
            h.push(`<div class="tarea" data-accion="tarea" data-valor="${valor}" data-area="${esc(p.fila.area ?? '')}" data-dueno="${esc(p.fila.dueno ?? '')}" title="clic: leerla y decidir">`
                + `<span class="id">${esc(p.ref)}</span><span class="pri"></span>`
                + `<span class="desc"><span class="av av-${esc(p.avance)}">${esc(todo.replace(':', ' '))}</span>${esc(p.texto)}</span>`
                + `<span class="meta">${plazo(p.dias)}<span class="destino"></span></span></div>`);
        });
        h.push('</section></div>');
        this.pintar(h);
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
        this.pintar(htmlPlan(this.plan, this.planError, this.planCargando));
    }

    /** El calendario de hoy: los eventos, los bloques del plan y las notas de cada uno. */
    private async abrirCalendario(): Promise<void> {
        if (!this.panel) this.abrir();
        this.pantalla = 'calendario';
        if (!this.datos) this.datos = await dia();
        this.renderCalendario();
        const hoyIso = this.datos.fecha;
        const [plan, notas] = await Promise.all([
            this.plan?.dia === hoyIso ? Promise.resolve({ datos: this.plan }) : cli.resultado('plan', ''),
            cli.notasEventos(''),
        ]);
        if (plan.datos?.ok) this.plan = plan.datos;
        this.notas = notas.datos?.ok ? notas.datos : undefined;
        this.notasAviso = notas.datos?.aviso ?? (notas.datos?.ok ? '' : (notas.datos?.error ?? notas.error ?? ''));
        if (this.pantalla === 'calendario') this.renderCalendario();
    }

    private renderCalendario(): void {
        const d = this.datos;
        if (!d) return;
        this.teclas.clear();
        const plan = this.plan?.dia === d.fecha && this.plan.formato === 'json' ? this.plan.contenido as Record<string, unknown> : undefined;
        this.pintar(htmlCalendario(d, eventosDelDia(d, plan), this.notas, this.eventoSel, new Date(), this.notasAviso));
    }

    /** Una nota de la persona sobre un evento: se guarda donde viven las notas (`telar evento nota`). */
    private async notaEvento(valor: string): Promise<void> {
        const [id, titulo, inicio, fecha] = JSON.parse(valor) as string[];
        const texto = await vscode.window.showInputBox({ title: `Nota para «${titulo}»`, prompt: 'Se guarda junto al evento y la ven las skills', ignoreFocusOut: true });
        if (!texto?.trim()) return;
        const r = await cli.notaEvento(id, texto.trim(), titulo, inicio, fecha);
        if (!r.datos?.ok) { void vscode.window.showErrorMessage(`telar: la nota no se guardó: ${r.datos?.error ?? r.error ?? 'sin respuesta'}`); return; }
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
            const si = await vscode.window.showWarningMessage(`¿Borrar el proceso «${args[1]}»? Deja de correr; el archivo anterior queda en periodicos.toml.anterior.`, { modal: true }, 'Borrar');
            if (si !== 'Borrar') return;
        }
        const r = await cli.periodicosOrden(args);
        if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no se pudo'}`); return; }
        vscode.window.setStatusBarMessage(`telar: ${r.datos.hecho}`, 5000);
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
        void this.panel?.webview.postMessage({ tipo: 'parcial', id, html });
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
        vscode.window.setStatusBarMessage(`telar: ${r.datos.hecho}`, 5000);
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
        if (a.pide) {
            const escrito = await vscode.window.showInputBox({ prompt: `${f.id} · ${a.nombre}`, placeHolder: a.pide, ignoreFocusOut: true });
            if (escrito === undefined) return;
            texto = escrito;
        }
        if (a.confirmar) {
            const si = await vscode.window.showWarningMessage(`¿${a.nombre}? ${f.pagina?.titulo ?? f.id}`, { modal: true }, 'Sí');
            if (si !== 'Sí') return;
        }
        // una acción que lleva un mensaje a un hilo (el de la tarea, Gestión) toma unos segundos: se avisa
        const r = a.mensaje
            ? await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: `telar: ${a.nombre} · ${f.id}…` },
                () => cli.accionTarea(f.id, f.proveedor, k, texto))
            : await cli.accionTarea(f.id, f.proveedor, k, texto);
        if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude: ${a.nombre}`}`); return; }
        // abrió un hilo (hecha y procesar ahora): se va a él, que es donde sigue el trabajo
        if (r.datos.hilo) {
            this.decididas.add(f.id);
            olvidarDia();
            void this.actualizar(true);
            await modelo.sondear();
            await mostrarTerminal();
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

    /** Los bloques de una página (una sección, la ficha de una tarea), en HTML. */
    private htmlBloques(bloques: cli.JsonPagina['bloques']): string[] {
        const h: string[] = [];
        this.memorias.clear();   // los iframes de antes se reemplazan: sus llaves ya no valen
        bloques.forEach((b, i) => {
            if (b.lienzo) h.push(this.htmlLienzo(b.lienzo));
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
            + '<a class="atajo" data-accion="recargar-seccion" title="volver a pedir la página"><span>↻</span></a>'
            + '</span></div>'];
        h.push(...this.htmlBloques(p.bloques));
        this.pintar(h);
    }

    /** Un lienzo va como `srcdoc` y no como `src`: un iframe hacia un recurso del webview no
     *  carga (el service worker que los sirve no atiende la navegación de un iframe de otro
     *  origen), y queda en blanco. Con srcdoc el documento hereda el CSP del panel, así que
     *  sus `<script>` llevan el nonce del panel; y como srcdoc no tiene query string, un
     *  script previo deja los params en la URL (`about:srcdoc?…`) y en `window.lienzo`.
     *  El sandbox sin allow-same-origin deja correr sus scripts sin alcanzar el panel. */
    private htmlLienzo(l: cli.JsonLienzo): string {
        const alto = Math.round(l.alto ?? 240);
        let doc: string;
        try { doc = fs.readFileSync(l.archivo, 'utf8'); }
        catch (e) { return `<div class="fila falla">no pude leer ${esc(l.archivo)}: ${esc(String(e))}</div>`; }
        const params: Record<string, string> = {};
        for (const [k, v] of Object.entries(l.params ?? {})) params[k] = String(v);
        const datos = JSON.stringify(params).replace(/</g, '\\u003c');
        // con `memoria`, el lienzo recibe lo que guardó la vez anterior y una función para guardar:
        // el iframe no tiene almacenamiento propio (sandbox sin allow-same-origin)
        let memoria = '';
        if (l.memoria) {
            const llave = nuevoNonce();
            this.memorias.set(llave, l.memoria);
            let leida = 'null';
            try { const t = fs.readFileSync(l.memoria, 'utf8'); JSON.parse(t); leida = t; } catch { /* todavía no guardó nada */ }
            memoria = `window.lienzo.memoria=${leida.replace(/</g, '\\u003c')};window.lienzo.guardar=function(d){`
                + `parent.postMessage({lienzo:'guardar',llave:${JSON.stringify(llave)},datos:JSON.stringify(d)},'*')};`;
        }
        const previo = `<script nonce="${this.nonce}">(function(){var p=${datos};window.lienzo={params:p};${memoria}`
            + `var q=new URLSearchParams(p).toString();`
            + `if(q){try{history.replaceState(null,'','about:srcdoc?'+q)}catch(e){}}})()</script>`;
        doc = previo + doc.replace(/<script(?![^>]*\bnonce=)/gi, `<script nonce="${this.nonce}"`);
        return `<iframe class="lienzo" sandbox="allow-scripts" srcdoc="${esc(doc)}" style="height:${alto}px"></iframe>`;
    }

    /** El correo entre agentes: las conversaciones de todas las máquinas remotas, con sus
     *  textos (se piden al entrar, no en el refresco: pueden ser muchos). */
    private async abrirCorreo(): Promise<void> {
        this.pantalla = 'correo';
        this.pintar(['<div class="subcab"><b>Correo entre agentes</b></div>', '<div class="fila dim">leyendo…</div>']);
        const [r, bus] = await Promise.all([cli.correo(true), cli.mensajesBus()]);
        if (this.pantalla !== 'correo') return;
        this.mensajesBus = bus.datos?.mensajes;
        this.buzones = r.datos?.remotos;
        if (!r.datos && !this.mensajesBus) {
            this.pintar(['<div class="subcab"><b>Correo entre agentes</b></div>',
                `<div class="fila falla">${esc(r.error ?? 'no pude leer el correo')}</div>`]);
            return;
        }
        this.renderCorreo();
    }

    private renderCorreo(): void {
        const filtros: [string, string][] = [['todas', 'todas'], ['mias', 'mías'], ['sin', 'sin entregar']];
        const h: string[] = ['<div class="subcab"><b>Correo entre agentes</b>'
            + '<span class="der dim"><a data-accion="correo" title="volver a leer">↻</a></span></div>',
            '<div class="titulo-tareas"><span class="modos">' + filtros.map(([k, t]) =>
                `<button data-accion="filtro-correo" data-valor="${k}" class="${this.filtroCorreo === k ? 'activo' : ''}">${t}</button>`).join('')
            + '</span></div>'];
        if (this.mensajesBus) h.push(...this.htmlMensajesBus(this.mensajesBus));
        for (const b of this.buzones ?? []) {
            h.push(`<h2>${esc(b.remoto)}<small>${esc(b.usuario)}${b.archivo_comun ? ' · con el archivo común' : ' · solo tu casilla'}</small></h2>`);
            if (b.error) { h.push(`<div class="fila falla">${esc(b.error)}</div>`); continue; }
            if (b.cartero === false) h.push('<div class="fila dim">sin cartero: el correo de este usuario no se entrega a sus agentes, queda en su casilla</div>');
            else if (!b.sabe_pendientes) h.push('<div class="fila dim">el cartero de esa máquina no anota qué entregó: no se sabe qué quedó sin entregar</div>');
            const convs = b.conversaciones.filter(c => this.filtroCorreo === 'todas'
                || (this.filtroCorreo === 'mias' && c.participantes.includes(b.usuario))
                || (this.filtroCorreo === 'sin' && (c.estado === 'sin sesión' || c.estado === 'retenido')));
            if (!convs.length) h.push('<div class="fila dim">nada</div>');
            convs.forEach(c => {
                const i = b.conversaciones.indexOf(c);
                h.push(`<div class="item-pag clic" data-accion="conv-correo" data-valor="${esc(`${b.remoto}|${i}`)}">`
                    + `<div class="fila"><b>${esc(c.asunto || '(sin asunto)')}</b><span class="der dim">${esc(fechaCorta(c.ultima))}</span></div>`
                    + `<div class="fila dim">${esc(c.participantes.join(', '))} · ${c.mensajes} mensaje${c.mensajes === 1 ? '' : 's'}`
                    + `${c.estado ? ` · ${esc(c.estado)}` : ''}</div></div>`);
            });
        }
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
        if (!r.datos) { void vscode.window.showErrorMessage(`telar: no se soltó: ${r.error ?? 'sin respuesta'}`); return; }
        void vscode.window.setStatusBarMessage(`telar: soltado, en la casilla de «${r.datos.para}»`, 4000);
        await this.abrirCorreo();
    }

    private verConvCorreo(valor: string): void {
        const corte = valor.lastIndexOf('|');
        const remoto = valor.slice(0, corte), i = valor.slice(corte + 1);
        const c = this.buzones?.find(b => b.remoto === remoto)?.conversaciones[Number(i)];
        if (!c) return;
        const h: string[] = [`<div class="subcab"><b>${esc(c.asunto || '(sin asunto)')}</b><span class="dim">${esc(c.participantes.join(', '))}</span>`
            + '<span class="der dim"><a data-accion="volver-correo">← correo</a></span></div>',
            '<div class="fila dim">el remitente es el usuario que lo mandó según el servidor (verificado), no el campo From</div>'];
        for (const m of c.correos) {
            h.push(`<div class="msg"><div class="quien">${esc(m.de || '(sistema)')} <span class="dim">→ ${esc(m.para)} · ${esc(fechaCorta(m.fecha))}`
                + `${m.estado ? ` · ${esc(m.estado)}` : ''}</span></div><div class="md-pag"><p style="white-space:pre-wrap">${esc(m.cuerpo ?? '')}</p></div></div>`);
        }
        this.pintar(h);
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

    /** Un proveedor caído no apaga el telar: se dice cuál se cayó y el resto sigue. */
    private fallas(d: Dia): string[] {
        const otras = d.fallas.filter(f => !f.startsWith('calendario'));
        if (!otras.length) return [];
        return ['<h2>Proveedores</h2>', ...otras.map(f => `<div class="fila dim">caído · ${esc(f)}</div>`)];
    }

    /** Un hilo con el agente preparando la reunión, y el teclado ahí. Lo que se le dice
     *  al agente lo decide `[agente] reunion` en la configuración de telar, no la extensión. */
    private async preparar(titulo: string, hora: string, enlace: string, evento = ''): Promise<void> {
        const r = await vscode.window.withProgress(
            { location: vscode.ProgressLocation.Notification, title: `telar: ${titulo}…` }, () => cli.reunion(titulo, hora, enlace, evento));
        if (!r.datos) {
            void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no pude abrir la reunión'}`);
            return;
        }
        // con un agente que recibe lo sin proyecto (Gestión), se le encargó a él: se dice a quién
        if (r.datos.hecho.startsWith('encargado')) void vscode.window.setStatusBarMessage(`telar: «${titulo}» ${r.datos.hecho}`, 6000);
        await modelo.sondear();
        await mostrarTerminal();
    }

    /** La pantalla de proyectos. La lista se pide cada vez que se entra: es barata (medio
     *  segundo con 179 unidades) y así un proyecto recién creado aparece sin recargar. */
    private async abrirProyectos(): Promise<void> {
        this.pantalla = 'proyectos';
        this.avisoProyectos = '';
        if (!this.proyectos) this.renderProyectos('leyendo los proyectos…');
        const r = await cli.proyectos();
        if (r.datos) this.proyectos = r.datos.proyectos;
        else this.avisoProyectos = r.error ?? 'telar proyectos no contestó';
        if (this.pantalla === 'proyectos') this.renderProyectos();
    }

    /** Todas las filas van al webview de una vez; buscar y ordenar ocurre allá, sin ir y
     *  volver por cada letra. Ver `aplicarProyectos` en el script del día. */
    private renderProyectos(cargando = ''): void {
        if (!this.panel) return;
        this.teclas.clear();
        const lista = this.proyectos ?? [];
        const h: string[] = [`<div class="subcab"><b>Proyectos</b><span class="dim">${lista.length || ''}</span>`
            + '</div>'];
        if (this.avisoProyectos) h.push(`<div class="fila falla">${esc(this.avisoProyectos)}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.pintar(h); return; }
        h.push('<div class="titulo-tareas">'
            + `<input id="buscar-p" type="text" placeholder="/ buscar en los ${lista.length}" spellcheck="false" autocomplete="off">`
            + '<span class="modos"><span id="proyectos-cuenta"></span>'
            + '<button data-orden-p="alfa" title="por nombre">a-z</button>'
            + '<button data-orden-p="fecha" title="lo tocado más recientemente primero">recientes</button></span></div>');
        h.push('<div class="ayuda">⏎ · abrir con el agente   ● · ya abierto</div>');
        h.push('<div id="proyectos">');
        for (const p of lista) {
            const marca = p.vivo ? '●' : p.hilo ? '·' : '';
            const texto = normalizar(`${p.nombre} ${p.ruta} ${p.arquetipo}`);
            const fecha = p.modificado ?? '';
            h.push(`<div class="fila clic proy" data-accion="proyecto" data-valor="${esc(p.ruta)}"`
                + ` data-texto="${esc(texto)}" data-nombre="${esc(normalizar(p.nombre))}" data-fecha="${esc(fecha)}"`
                + ` title="${esc(`${p.ruta}${fecha ? `\nmodificado ${fecha.slice(0, 16).replace('T', ' ')}` : ''}${p.hilo ? `\nhilo: ${p.hilo}` : ''}`)}">`
                + `<span class="at">${marca}</span><span class="que">${esc(p.nombre)}</span>`
                + `<span class="dim tipo">${esc(p.arquetipo)}</span><span class="dim cuando-p">${esc(haceCorto(fecha))}</span></div>`);
        }
        h.push('<div id="proyectos-vacio" class="fila dim" hidden></div></div>');
        this.pintar(h);
    }

    /** Un hilo con el agente cargando el proyecto, o el que ya había; y el teclado ahí. Lo
     *  que se le dice al agente lo decide `[agente] proyecto`, no la extensión. */
    private async abrirProyecto(ruta: string): Promise<void> {
        const r = await cli.abrirProyecto(ruta);
        if (!r.datos) {
            void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no pude abrir el proyecto'}`);
            return;
        }
        await modelo.sondear();
        await mostrarTerminal();
    }

    private async cambiarPlantillaProyecto(restablecer: boolean): Promise<void> {
        let texto = '';
        if (!restablecer) {
            const actual = this.agenteConfig?.proyecto ?? '';
            const nuevo = await vscode.window.showInputBox({
                title: 'Qué decirle al agente al abrir un proyecto',
                prompt: 'Marcadores: {nombre} {ruta} {carpeta} {documento}. Una skill (/nombre …) o una instrucción en prosa.',
                value: actual, ignoreFocusOut: true,
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
            await vscode.commands.executeCommand('telar.conectarCalendario');
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
        const nuevo = await vscode.window.showInputBox({
            title: 'De qué carpetas salen los hilos',
            prompt: 'Relativas a la raíz del repositorio, separadas por coma, en el orden en que se abren. Vacío: las unidades del perfil.',
            placeHolder: 'operacion/proyectos, negocio/pipeline',
            value: actual, ignoreFocusOut: true,
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
        const si = await vscode.window.showInformationMessage(
            'Carpetas guardadas. ¿Abrir ahora los hilos que falten? Cada uno arranca su agente.', 'Abrir ahora');
        if (si === 'Abrir ahora') {
            const t = await cli.telar(['tejer', '--sumar'], 60000);
            if (!t.ok) void vscode.window.showWarningMessage(`telar: ${t.err.trim().split('\n').pop() ?? 'no pude abrirlos'}`);
            await modelo.sondear();
        }
    }

    private async cambiarPlantilla(restablecer: boolean): Promise<void> {
        let texto = '';
        if (!restablecer) {
            const actual = this.agenteConfig?.reunion ?? '';
            const nuevo = await vscode.window.showInputBox({
                title: 'Qué decirle al agente al preparar una reunión',
                prompt: 'Marcadores: {titulo} {hora} {fecha} {enlace} {proyecto}. Una skill (/nombre …) o una instrucción en prosa.',
                value: actual, ignoreFocusOut: true,
            });
            if (nuevo === undefined || nuevo.trim() === actual) return;
            texto = nuevo.trim();
        }
        const r = await cli.plantillaReunion(texto);
        if (!r.ok) this.avisoConfig = r.err.trim().split('\n').pop() || 'no pude guardar el mensaje';
        await this.abrirConfig();
    }

    /** La pantalla de configuración: de dónde sale la agenda, si funciona, y las otras opciones. */
    private renderConfig(cargando = ''): void {
        if (!this.panel) return;
        this.teclas.clear();
        const h: string[] = ['<div class="subcab"><b>Configuración</b>'
            + '</div>'];
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.pintar(h); return; }
        if (this.avisoConfig) h.push(`<div class="fila falla">${esc(this.avisoConfig)}</div>`);
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
        void this.panel?.webview.postMessage({ tipo: 'dia', html: this.nav() + h.join('\n') });
    }

    /** Lo que un lienzo pide guardar, en el archivo que declaró su página. Se escribe entero
     *  (temporal y rename): un corte a medias no deja un JSON roto que el lienzo no pueda leer. */
    private guardarLienzo(llave: string, datos: string): void {
        const ruta = this.memorias.get(llave);
        if (!ruta || datos.length > 4_000_000) return;
        try { JSON.parse(datos); } catch { return; }
        try {
            fs.mkdirSync(path.dirname(ruta), { recursive: true });
            const tmp = `${ruta}.${process.pid}.tmp`;
            fs.writeFileSync(tmp, datos);
            fs.renameSync(tmp, ruta);
        } catch { /* sin permiso o sin disco: el lienzo sigue, sin memoria */ }
    }

    private async mensaje(m: { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string; datos?: string }): Promise<void> {
        if (m.tipo === 'lienzo-guardar') { this.guardarLienzo(m.valor ?? '', m.datos ?? ''); return; }
        if (m.tipo === 'per-horario') { await this.previaHorario(m.valor ?? ''); return; }
        if (m.tipo === 'per-skills') { await this.cargarSkills(m.valor ?? ''); return; }
        if (m.tipo === 'listo') {
            // un panel recién abierto para una sección pierde lo que se le mandó antes de estar listo
            if (this.pantalla === 'seccion' && this.pagina) this.renderSeccion();
            this.render(); void this.actualizar(); return;
        }
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await vscode.env.openExternal(vscode.Uri.parse(m.url)); return; }
        if (m.tipo === 'tecla' && m.k) {
            // las de la pestaña primero; p, c y r valen en todas
            const globales: Record<string, () => Promise<unknown>> = {
                p: () => this.abrirProyectos(), r: () => this.actualizar(true), v: () => this.abrirRevisar(),
                o: () => this.abrirPeriodicos(), d: () => this.abrirPlan(''), a: () => this.abrirCalendario(),
                ...Object.fromEntries(this.pestanasCfg.filter(x => x.tecla).map(x => [x.tecla, () => this.abrirPestana(x.nombre)])),
                t: () => Promise.resolve(vscode.commands.executeCommand('telar.tareas')),
                ...(modelo.hayRemotos ? { c: () => this.abrirCorreo() } : {}),
                ...Object.fromEntries(this.atajos.map(a => [a.tecla, () => this.lanzarAtajo(a.tecla)])),
            };
            await (this.teclas.get(m.k) ?? globales[m.k])?.();
            return;
        }
        if (m.tipo !== 'accion') return;
        switch (m.accion) {
            case 'pendiente': if (m.valor) await llevarPendiente(m.valor, !!m.nuevo); break;
            case 'ir': if (m.valor) await irAHilo(m.valor); break;
            case 'refrescar': await this.actualizar(true); break;
            case 'volver': void mostrarTerminal(); break;
            case 'reunion': {
                const [titulo, hora, enlace, evento] = JSON.parse(m.valor ?? '[]') as string[];
                if (titulo && hora) await this.preparar(titulo, hora, enlace ?? '', evento ?? '');
                break;
            }
            case 'config': await this.abrirConfig(); break;
            case 'proyectos': await this.abrirProyectos(); break;
            case 'seccion': if (m.valor) await this.abrirSeccion(m.valor); break;
            case 'proyecto': if (m.valor) await this.abrirProyecto(m.valor); break;
            case 'plantilla-proyecto': await this.cambiarPlantillaProyecto(m.valor === 'restablecer'); break;
            case 'dia': this.pantalla = 'dia'; void this.leerAtajos(); break;
            case 'atajo': if (m.valor) await this.lanzarAtajo(m.valor); break;
            case 'abrir-item': if (m.valor) await this.abrirItem(m.valor); break;
            case 'tarea':
                if (!m.valor) break;
                // ⌘-clic: como antes, al hilo donde se trabaja; clic: la ficha
                if (m.nuevo) { const [proveedor, , ref] = JSON.parse(m.valor) as string[]; await llevarPendiente(ref, false, proveedor); }
                else await this.abrirTarea(m.valor);
                break;
            case 'accion-tarea': if (m.valor) await this.accionTarea(Number(m.valor)); break;
            case 'hecha':
                if (!m.valor) break;
                await marcarHecha(m.valor);
                void this.actualizar(true);
                void vscode.commands.executeCommand('telar.tareasActualizar');
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
                else { this.pantalla = 'dia'; this.render(); }   // de una pestaña de proveedor, a hoy
                break;
            case 'tarea-anterior': await this.otraPropuesta(-1); break;
            case 'abrir-enlace': if (m.valor) await abrirEnlace(m.valor); break;
            case 'abrir-ruta':
                // una ruta relativa a la raíz de telar (la que traen las notas de un evento)
                if (m.valor && !m.valor.includes('..') && modelo.raiz) await abrirEnlace(path.join(modelo.raiz, m.valor));
                break;
            case 'tareas': await vscode.commands.executeCommand('telar.tareas'); break;
            case 'recargar-seccion': this.pagina = undefined; if (this.seccion) await this.abrirSeccion(this.seccion); break;
            case 'volver-seccion': if (this.seccion && this.pagina) { this.pantalla = 'seccion'; this.renderSeccion(); } else { this.pantalla = 'dia'; this.render(); } break;
            case 'conversacion': if (m.valor) await this.abrirConversacion(m.valor); break;
            case 'correo': await this.abrirCorreo(); break;
            case 'filtro-correo': this.filtroCorreo = (m.valor as 'todas' | 'mias' | 'sin') || 'todas'; this.renderCorreo(); break;
            case 'conv-correo': if (m.valor) this.verConvCorreo(m.valor); break;
            case 'volver-correo': this.renderCorreo(); break;
            case 'ver-msg':
                if (m.valor) { if (this.abiertoMsg.has(m.valor)) this.abiertoMsg.delete(m.valor); else this.abiertoMsg.add(m.valor); this.renderCorreo(); }
                break;
            case 'soltar-msg': if (m.valor) await this.soltarMensaje(m.valor); break;
            case 'retomar-charla':
                if (this.charla?.hilo) {
                    const vivo = modelo.porNombre(this.charla.hilo)?.vivo;
                    await vscode.commands.executeCommand(vivo ? 'telar.ir' : 'telar.retomar', { hilo: this.charla.hilo });
                }
                break;
            case 'calendario':
                // desde la configuración elige de dónde sale la agenda; desde una pestaña, la abre
                if (this.pantalla === 'config') await this.elegirCalendario(m.valor ?? ''); else await this.abrirCalendario();
                break;
            case 'plan': await this.abrirPlan(''); break;
            case 'plan-dia': await this.abrirPlan(m.valor ?? ''); break;
            case 'evento-sel': if (m.valor) { this.eventoSel = m.valor; this.renderCalendario(); } break;
            case 'nota-evento': if (m.valor) await this.notaEvento(m.valor); break;
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

/** Abre un enlace de una página: una URL en el navegador, una ruta local en el editor. */
async function abrirEnlace(enlace: string): Promise<void> {
    if (/^https?:\/\//.test(enlace)) { await vscode.env.openExternal(vscode.Uri.parse(enlace)); return; }
    if (enlace.startsWith('/') && fs.existsSync(enlace)) {
        await vscode.commands.executeCommand('vscode.open', vscode.Uri.file(enlace));
        return;
    }
    void vscode.window.showWarningMessage(`telar: no sé abrir ${enlace}`);
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
