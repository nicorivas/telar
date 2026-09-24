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
import { CSS_DIA, Dia, SCRIPT_DIA, dia, htmlPendientes, olvidarDia } from './dia';
import { llevarPendiente } from './tareas';

export class PanelHoy {
    panel?: vscode.WebviewPanel;
    private datos?: Dia;
    private pantalla: 'dia' | 'config' | 'proyectos' | 'seccion' | 'conversacion' | 'correo' = 'dia';
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
        } finally { this.enCurso = false; }
    }

    /** Redibuja con lo que hay: la marca «ahora» y los «hace» se mueven solos cada minuto. */
    render(): void {
        if (this.panel && this.pantalla === 'config') { this.renderConfig(); return; }
        // la lista de proyectos no cambia con el reloj: repintarla cada minuto solo movería el scroll
        if (this.panel && this.pantalla === 'proyectos') return;
        // lo mismo con la página de una sección y una conversación: no dependen del reloj
        if (this.panel && (this.pantalla === 'seccion' || this.pantalla === 'conversacion' || this.pantalla === 'correo')) return;
        const d = this.datos;
        if (!this.panel || !d) return;
        this.teclas.clear();
        const ahora = new Date();
        const h: string[] = [];
        h.push(`<div class="cab"><b>${esc(d.nombreDia)} ${esc(d.fecha)}</b>`
            + `<span class="dim">${ahora.toTimeString().slice(0, 5)}${d.semana ? ` · semana ${d.semana}` : ''}</span>`
            + '<span class="der dim">'
            + (modelo.hayRemotos ? '<a data-accion="correo" title="el correo entre agentes de las máquinas remotas (c)">✉ correo</a> · ' : '')
            + '<a data-accion="proyectos" title="todos los proyectos: buscar y abrir uno (p)">▤ proyectos</a>'
            + ' · <a data-accion="refrescar" title="volver a preguntar, proveedores incluidos (r)">↻ recargar</a>'
            + ' · <a data-accion="config" title="de dónde sale cada cosa">⚙ configuración</a></span></div>');
        h.push(...this.agenda(d, ahora), ...this.hilos(), ...this.htmlAtajos(), ...htmlPendientes(d, false), ...this.fallas(d));
        const teclasAtajos = this.atajos.map(a => ` · ${esc(a.tecla)} ${esc(a.nombre)}`).join('');
        h.push(`<div class="pie">⎋ vuelve al terminal · / busca · r recarga · p proyectos · t la vista de tareas${teclasAtajos} · letra: llevar ese pendiente a su hilo</div>`);
        for (const a of this.atajos) this.teclas.set(a.tecla, () => this.lanzarAtajo(a.tecla));
        if (modelo.hayRemotos && !this.teclas.has('c')) this.teclas.set('c', () => this.abrirCorreo());
        for (const [k, f] of [['r', () => this.actualizar(true)], ['p', () => this.abrirProyectos()],
            ['t', () => vscode.commands.executeCommand('telar.tareas')]] as const) {
            if (!this.teclas.has(k)) this.teclas.set(k, f);
        }
        void this.panel.webview.postMessage({ tipo: 'dia', html: h.join('\n') });
    }

    private agenda(d: Dia, ahora: Date): string[] {
        const h = ['<h2>Agenda<small>número o clic: preparar la reunión · entrar: la videollamada</small></h2>'];
        if (d.error) return [...h, `<div class="fila dim">(${esc(d.error)})</div>`];
        const falla = d.fallas.find(f => f.startsWith('calendario'));
        if (falla) {
            const motivo = falla.split(': ').pop() ?? falla;
            return [...h, `<div class="fila falla">El calendario no respondió (${esc(motivo)}) · `
                + '<a data-accion="config">configurar</a></div>'];
        }
        if (d.agenda === null) {
            if (d.declarados.length) {
                return [...h, '<div class="fila dim">todavía no se consultó el calendario (r)</div>'];
            }
            return [...h, '<div class="fila dim">No hay calendario conectado · '
                + '<a data-accion="config" title="elegir de dónde sale la agenda">conectar</a></div>'];
        }
        if (!d.agenda.length) return [...h, '<div class="fila dim">nada con hora</div>'];
        const t = ahora.getTime();
        const proxima = d.agenda.find(e => Date.parse(e.cuando ?? '') > t);
        let n = 0;
        for (const e of d.agenda) {
            const cuando = e.cuando ?? '';
            const url = e.url ?? '';
            const entrar = url ? `<a class="enlace" data-url="${esc(url)}" title="${esc(url)}">entrar</a>` : '';
            const hilo = e.hilo ? `<span class="dim">${esc(e.hilo)}</span>` : '';
            if (Date.parse(cuando) <= t) {
                h.push(`<div class="fila pasada"><span class="tecla"></span><span class="hora">${esc(hhmm(cuando))}</span>`
                    + `<span class="que">${esc(e.texto)}</span>${hilo}</div>`);
                continue;
            }
            n += 1;
            const tecla = n <= 9 ? String(n) : '';
            if (tecla) this.teclas.set(tecla, () => this.preparar(e.texto, hhmm(cuando), url));
            let falta = '';
            if (e === proxima) {
                const min = Math.floor((Date.parse(cuando) - t) / 60000);
                falta = `<span class="cuando">← ${min <= 0 ? 'ahora' : min < 90 ? `en ${min} min`
                    : `en ${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')}`}</span>`;
            }
            const valor = esc(JSON.stringify([e.texto, hhmm(cuando), url]));
            h.push(`<div class="fila clic${e === proxima ? ' proxima' : ''}" data-accion="reunion" data-valor="${valor}"`
                + ` title="preparar esta reunión con el agente${tecla ? ` (${tecla})` : ''}">`
                + `<span class="tecla">${tecla ? `[${tecla}]` : ''}</span><span class="hora">${esc(hhmm(cuando))}</span>`
                + `<span class="que">${esc(e.texto)}</span>${hilo}${entrar}${falta}</div>`);
        }
        return h;
    }

    private hilos(): string[] {
        const orden: Record<string, number> = { espera: 0, termino: 1, trabajando: 2 };
        const filas = modelo.enLista
            .filter(x => x.atencion in orden)
            .sort((a, b) => orden[a.atencion] - orden[b.atencion] || a.nombre.localeCompare(b.nombre));
        const h = ['<h2>Te esperan<small>clic: ir al hilo</small></h2>'];
        if (!filas.length) return [...h, '<div class="fila dim">nadie</div>'];
        for (const x of filas) {
            h.push(`<div class="fila clic" data-accion="ir" data-valor="${esc(x.nombre)}">`
                + `<span class="at ${x.atencion}">${GLIFO[x.atencion]}</span>`
                + `<span class="nombre">${esc(cli.nombreVisible(modelo.hilos.find(y => y.nombre === x.nombre) ?? x))}</span>`
                + `<span class="dim">${esc(NOMBRE_ATENCION[x.atencion] ?? x.atencion)}${x.visto ? `, hace ${hace(x.visto)}` : ''}</span></div>`);
        }
        return h;
    }

    private async leerAtajos(): Promise<void> {
        const r = await cli.config();
        this.atajos = r.datos?.atajos ?? [];
        this.render();
    }

    /** Los atajos como una fila de enlaces: lo que se hace varias veces al día y no es de
     *  ningún proyecto. La tecla hace lo mismo que el clic. */
    private htmlAtajos(): string[] {
        if (!this.atajos.length) return [];
        return ['<h2>Atajos<small>tecla o clic: un hilo nuevo con el agente haciéndolo</small></h2>',
            '<div class="fila">' + this.atajos.map(a =>
                `<a data-accion="atajo" data-valor="${esc(a.tecla)}" title="${esc(`${a.descripcion ? a.descripcion + '\n' : ''}le dice: ${a.mensaje}`)}">`
                + `[${esc(a.tecla)}] ${esc(a.nombre)}</a>`).join('<span class="dim"> · </span>') + '</div>'];
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
        if (!this.pagina) this.pintar([`<div class="cab"><b>${esc(nombre)}</b></div>`, '<div class="fila dim">leyendo…</div>']);
        const r = await cli.seccion(clave);
        if (this.pantalla !== 'seccion' || this.seccion !== clave) return;
        if (!r.datos) {
            this.pintar([`<div class="cab"><b>${esc(nombre)}</b><span class="der dim"><a data-accion="dia">← volver al dashboard</a></span></div>`,
                `<div class="fila falla">${esc(r.error ?? 'el home no contestó')}</div>`]);
            return;
        }
        this.pagina = r.datos;
        this.renderSeccion();
    }

    private renderSeccion(): void {
        const p = this.pagina;
        if (!p) return;
        const h: string[] = [`<div class="cab"><b>${esc(p.titulo)}</b>${p.subtitulo ? `<span class="dim">${esc(p.subtitulo)}</span>` : ''}`
            + '<span class="der dim"><a data-accion="recargar-seccion" title="volver a pedir la página">↻</a>'
            + ' · <a data-accion="dia">← volver al dashboard</a></span></div>'];
        p.bloques.forEach((b, i) => {
            if (b.lienzo) h.push(this.htmlLienzo(b.lienzo));
            if (b.titulo) h.push(`<h2>${esc(b.titulo)}</h2>`);
            else if (i > 0) h.push('<div class="sep-pag"></div>');
            if (b.texto) h.push(`<div class="md-pag">${mdSimple(b.texto)}</div>`);
            for (const x of b.items ?? []) {
                const clic = x.conversacion ? ` data-accion="conversacion" data-valor="${esc(x.conversacion)}"`
                    : x.hilo ? ` data-accion="ir" data-valor="${esc(x.hilo)}"` : '';
                const fecha = x.fecha ? x.fecha.slice(0, 16).replace('T', ' ') : '';
                h.push(`<div class="item-pag${clic ? ' clic' : ''}"${clic}`
                    + ` title="${esc(x.conversacion ? 'clic: leer la conversación entera' : x.hilo ? `clic: ir a «${x.hilo}»` : '')}">`
                    + `<div class="fila"><b>${esc(x.titulo)}</b><span class="der dim">${esc(fecha)}</span></div>`
                    + (x.texto ? `<div class="texto-pag">${mdSimple(x.texto)}</div>` : '') + '</div>');
            }
        });
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
        this.pintar(['<div class="cab"><b>Correo entre agentes</b></div>', '<div class="fila dim">leyendo por ssh…</div>']);
        const r = await cli.correo(true);
        if (this.pantalla !== 'correo') return;
        this.buzones = r.datos?.remotos;
        if (!r.datos) {
            this.pintar(['<div class="cab"><b>Correo entre agentes</b><span class="der dim"><a data-accion="dia">← volver</a></span></div>',
                `<div class="fila falla">${esc(r.error ?? 'no pude leer el correo')}</div>`]);
            return;
        }
        this.renderCorreo();
    }

    private renderCorreo(): void {
        const filtros: [string, string][] = [['todas', 'todas'], ['mias', 'mías'], ['sin', 'sin entregar']];
        const h: string[] = ['<div class="cab"><b>Correo entre agentes</b>'
            + '<span class="der dim"><a data-accion="correo" title="volver a leer">↻</a> · <a data-accion="dia">← volver al dashboard</a></span></div>',
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
        const h: string[] = [`<div class="cab"><b>${esc(c.asunto || '(sin asunto)')}</b><span class="dim">${esc(c.participantes.join(', '))}</span>`
            + '<span class="der dim"><a data-accion="volver-correo">← volver</a></span></div>',
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
        const h: string[] = [`<div class="cab"><b>Conversación</b><span class="dim">${esc(c.conversacion.slice(0, 8))}`
            + `${c.hilo ? ` · ${esc(c.hilo)}` : ''} · ${c.mensajes.length} mensajes</span>`
            + '<span class="der dim">'
            + (hilo ? `<a data-accion="retomar-charla" title="volver a esta conversación en su hilo">▶ retomar</a> · ` : '')
            + (this.seccion ? '<a data-accion="volver-seccion">← volver</a>' : '<a data-accion="dia">← volver al dashboard</a>')
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
        const h: string[] = [`<div class="cab"><b>Proyectos</b><span class="dim">${lista.length || ''}</span>`
            + '<span class="der dim"><a data-accion="dia" title="volver al día">← volver al dashboard</a></span></div>'];
        if (this.avisoProyectos) h.push(`<div class="fila falla">${esc(this.avisoProyectos)}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.pintar(h); return; }
        h.push('<div class="titulo-tareas">'
            + `<input id="buscar-p" type="text" placeholder="/ buscar en los ${lista.length}" spellcheck="false" autocomplete="off">`
            + '<span class="modos"><span id="proyectos-cuenta"></span>'
            + '<button data-orden-p="alfa" title="por nombre">a-z</button>'
            + '<button data-orden-p="fecha" title="lo tocado más recientemente primero">recientes</button></span></div>');
        h.push('<div class="ayuda">clic o ⏎: abrir un hilo con el agente cargando el proyecto · ● ya tiene hilo abierto: se va a él</div>');
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
        const h: string[] = ['<div class="cab"><b>Configuración</b>'
            + '<span class="der dim"><a data-accion="dia" title="volver al día (⎋)">← volver al dashboard</a></span></div>'];
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
        void this.panel?.webview.postMessage({ tipo: 'dia', html: h.join('\n') });
    }

    private async mensaje(m: { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string }): Promise<void> {
        if (m.tipo === 'listo') {
            // un panel recién abierto para una sección pierde lo que se le mandó antes de estar listo
            if (this.pantalla === 'seccion' && this.pagina) this.renderSeccion();
            this.render(); void this.actualizar(); return;
        }
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await vscode.env.openExternal(vscode.Uri.parse(m.url)); return; }
        if (m.tipo === 'tecla' && m.k) { await this.teclas.get(m.k)?.(); return; }
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
            case 'proyecto': if (m.valor) await this.abrirProyecto(m.valor); break;
            case 'plantilla-proyecto': await this.cambiarPlantillaProyecto(m.valor === 'restablecer'); break;
            case 'dia': this.pantalla = 'dia'; void this.leerAtajos(); break;
            case 'atajo': if (m.valor) await this.lanzarAtajo(m.valor); break;
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

