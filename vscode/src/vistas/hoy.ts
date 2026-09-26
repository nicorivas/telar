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
import * as vscode from 'vscode';

import { irAHilo, mostrarTerminal } from '../acciones';
import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, esc, hace, haceCorto, hhmm, marco, normalizar, nuevoNonce } from '../estilo';
import { modelo } from '../modelo';
import { CSS_DIA, Dia, SCRIPT_DIA, atajo, dia, htmlPendientes, olvidarDia, pendientes, pista, plazo, seccion } from './dia';
import { llevarPendiente } from './tareas';

export class PanelHoy {
    panel?: vscode.WebviewPanel;
    private datos?: Dia;
    private pantalla: 'dia' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'correo' | 'tarea' | 'revisar' = 'dia';
    /** de qué pestaña se abrió la ficha: ⎋ vuelve ahí, y ahí queda marcada */
    private fichaDesde: 'dia' | 'revisar' = 'dia';
    /** la ficha abierta: de qué proveedor, su id y su ref (con la que se lleva al hilo) */
    private ficha?: { proveedor: string; id: string; ref: string; pagina?: cli.JsonPagina; aviso?: string };
    /** las propuestas ya decididas en esta pasada: ← → las saltan aunque el día no se haya releído */
    private decididas = new Set<string>();
    /** el correo con cuerpos, leído al entrar a la pantalla; y el filtro elegido */
    private buzones?: cli.JsonBuzon[];
    private filtroCorreo: 'todas' | 'mias' | 'sin' = 'todas';
    /** la sección abierta y su página; la conversación que se está leyendo */
    private seccion = '';
    private pagina?: cli.JsonPagina;
    private charla?: cli.JsonConversacion;
    /** el nonce del CSP del panel: los lienzos lo necesitan para que corran sus scripts */
    private nonce = nuevoNonce();
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
            this.panel.webview.html = marco(this.panel.webview, CSS_DIA,
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
            : this.pantalla === 'seccion' ? `seccion:${this.seccion}` : this.pantalla === 'tarea' ? this.fichaDesde : this.pantalla;
        const aRevisar = this.propuestas().length;
        const pestanas: [string, string, string, string, string][] = [  // clave, acción, valor, nombre, tecla
            ['dia', 'dia', '', 'hoy', ''],
            ['revisar', 'revisar', '', aRevisar ? `revisar ${aRevisar}` : 'revisar', 'v'],
            ['proyectos', 'proyectos', '', 'proyectos', 'p'],
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
            const valor = esc(JSON.stringify([e.texto, hhmm(cuando), url]));
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
        const r = await cli.atajo(tecla);
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
        if (!this.panel) this.abrir();
        if (this.pantalla === 'revisar' || this.pantalla === 'dia') this.fichaDesde = this.pantalla;
        this.pantalla = 'tarea';
        this.ficha = { proveedor, id, ref };
        this.pintar([`<div id="ficha-tarea"><div class="subcab"><b>${esc(id)}</b></div><div class="fila dim">leyendo…</div></div>`]);
        const r = await cli.tarea(id, proveedor);
        if (this.pantalla !== 'tarea' || this.ficha?.id !== id) return;
        this.ficha.pagina = r.datos;
        this.ficha.aviso = r.datos ? '' : (r.error ?? 'la ficha no contestó');
        this.renderTarea();
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
        const h = ['<div id="revisar">', seccion('revisar', 'cian', lista.length ? String(lista.length) : '', lista.length ? pista('⏎', 'la primera') : '')];
        if (!lista.length) h.push('<div class="vacio">nada que decidir: lo que un agente proponga aparece aquí</div>');
        lista.forEach((p, i) => {
            const [todo] = (p.fila.avance ?? '').split(' ');
            const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
            h.push(`<div class="tarea" data-accion="tarea" data-valor="${valor}" title="clic: leerla y decidir">`
                + `<span class="id">${esc(p.ref)}</span><span class="pri"></span>`
                + `<span class="desc"><span class="av av-${esc(p.avance)}">${esc(todo.replace(':', ' '))}</span>${esc(p.texto)}</span>`
                + `<span class="meta">${plazo(p.dias)}<span class="destino"></span></span></div>`);
        });
        h.push('</section></div>');
        this.pintar(h);
    }

    /** Las tareas con propuesta, en el orden del día, sin las ya decididas (salvo la abierta). */
    private propuestas(): { proveedor: string; id: string; ref: string }[] {
        if (!this.datos) return [];
        return pendientes(this.datos)
            .filter(p => p.avance && p.fila.ficha && (!this.decididas.has(p.fila.id || p.ref) || (p.fila.id || p.ref) === this.ficha?.id))
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
            p.subtitulo ? `<div class="fila dim">${esc(p.subtitulo)}</div>` : '',
            botones.length ? `<div class="acciones-t">${botones.join('')}</div>` : '',
            ...this.htmlBloques(p.bloques), '</div>']);
    }

    private async accionTarea(k: number): Promise<void> {
        const f = this.ficha;
        const a = f?.pagina?.acciones?.[k];
        if (!f || !a) return;
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(f.ref, false); return; }
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
        const r = await cli.accionTarea(f.id, f.proveedor, k, texto);
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
        const releida = await cli.tarea(f.id, f.proveedor);
        const sigueViva = !!releida.datos?.bloques.some(b => b.destacado);
        olvidarDia();
        void this.actualizar(true);
        if (eraPropuesta && !sigueViva) {
            this.decididas.add(f.id);
            if (await this.otraPropuesta(1)) return;
            // era la última: de vuelta a la lista de donde se vino, que ahora dice «nada que decidir»
            if (this.fichaDesde === 'revisar') { await this.abrirRevisar(); return; }
        }
        if (this.pantalla === 'tarea' && this.ficha?.id === f.id) {
            this.ficha.pagina = releida.datos ?? this.ficha.pagina;
            this.renderTarea();
        }
    }

    /** Los bloques de una página (una sección, la ficha de una tarea), en HTML. */
    private htmlBloques(bloques: cli.JsonPagina['bloques']): string[] {
        const h: string[] = [];
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
        const previo = `<script nonce="${this.nonce}">(function(){var p=${datos};window.lienzo={params:p};`
            + `var q=new URLSearchParams(p).toString();`
            + `if(q){try{history.replaceState(null,'','about:srcdoc?'+q)}catch(e){}}})()</script>`;
        doc = previo + doc.replace(/<script(?![^>]*\bnonce=)/gi, `<script nonce="${this.nonce}"`);
        return `<iframe class="lienzo" sandbox="allow-scripts" srcdoc="${esc(doc)}" style="height:${alto}px"></iframe>`;
    }

    /** El correo entre agentes: las conversaciones de todas las máquinas remotas, con sus
     *  textos (se piden al entrar, no en el refresco: pueden ser muchos). */
    private async abrirCorreo(): Promise<void> {
        this.pantalla = 'correo';
        this.pintar(['<div class="subcab"><b>Correo entre agentes</b></div>', '<div class="fila dim">leyendo por ssh…</div>']);
        const r = await cli.correo(true);
        if (this.pantalla !== 'correo') return;
        this.buzones = r.datos?.remotos;
        if (!r.datos) {
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
    private async preparar(titulo: string, hora: string, enlace: string): Promise<void> {
        const r = await cli.reunion(titulo, hora, enlace);
        if (!r.datos) {
            void vscode.window.showWarningMessage(`telar: ${r.error ?? 'no pude abrir la reunión'}`);
            return;
        }
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

    private async mensaje(m: { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string }): Promise<void> {
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
                const [titulo, hora, enlace] = JSON.parse(m.valor ?? '[]') as string[];
                if (titulo && hora) await this.preparar(titulo, hora, enlace ?? '');
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
                if (m.nuevo) { const [, , ref] = JSON.parse(m.valor) as string[]; await llevarPendiente(ref, false); }
                else await this.abrirTarea(m.valor);
                break;
            case 'accion-tarea': if (m.valor) await this.accionTarea(Number(m.valor)); break;
            case 'tarea-principal': {
                const i = (this.ficha?.pagina?.acciones ?? []).findIndex(a => a.principal);
                if (i >= 0) await this.accionTarea(i);
                break;
            }
            case 'tarea-siguiente': await this.otraPropuesta(1); break;
            case 'revisar': await this.abrirRevisar(); break;
            case 'volver-ficha': if (this.fichaDesde === 'revisar') await this.abrirRevisar(); else { this.pantalla = 'dia'; this.render(); } break;
            case 'tarea-anterior': await this.otraPropuesta(-1); break;
            case 'abrir-enlace': if (m.valor) await abrirEnlace(m.valor); break;
            case 'tareas': await vscode.commands.executeCommand('telar.tareas'); break;
            case 'recargar-seccion': this.pagina = undefined; if (this.seccion) await this.abrirSeccion(this.seccion); break;
            case 'volver-seccion': if (this.seccion && this.pagina) { this.pantalla = 'seccion'; this.renderSeccion(); } else { this.pantalla = 'dia'; this.render(); } break;
            case 'conversacion': if (m.valor) await this.abrirConversacion(m.valor); break;
            case 'correo': await this.abrirCorreo(); break;
            case 'filtro-correo': this.filtroCorreo = (m.valor as 'todas' | 'mias' | 'sin') || 'todas'; this.renderCorreo(); break;
            case 'conv-correo': if (m.valor) this.verConvCorreo(m.valor); break;
            case 'volver-correo': this.renderCorreo(); break;
            case 'retomar-charla':
                if (this.charla?.hilo) {
                    const vivo = modelo.porNombre(this.charla.hilo)?.vivo;
                    await vscode.commands.executeCommand(vivo ? 'telar.ir' : 'telar.retomar', { hilo: this.charla.hilo });
                }
                break;
            case 'calendario': await this.elegirCalendario(m.valor ?? ''); break;
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
