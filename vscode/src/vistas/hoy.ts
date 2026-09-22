// El dashboard: el día entero en un panel del área central (por dentro, `telar hoy`).
//
// Tiene dos pantallas. La del día, y la de configuración, que dice de dónde sale cada cosa
// —hoy, la agenda—, si está funcionando, y deja elegir otra fuente sin editar archivos.
//
// Tres cosas y en este orden, el mismo de `telar hoy` en la terminal: lo que ya tiene hora,
// quién te espera, y lo que está por hacer. Nada más. Lo que saldría de un proveedor que no
// está declarado no aparece porque no existe, y eso se dice en vez de dejar un hueco.

import * as vscode from 'vscode';

import { irAHilo, mostrarTerminal } from '../acciones';
import * as cli from '../cli';
import { GLIFO, NOMBRE_ATENCION, esc, hace, hhmm, marco } from '../estilo';
import { modelo } from '../modelo';
import { CSS_DIA, Dia, SCRIPT_DIA, dia, htmlPendientes, olvidarDia } from './dia';
import { llevarPendiente } from './tareas';

export class PanelHoy {
    panel?: vscode.WebviewPanel;
    private datos?: Dia;
    private pantalla: 'dia' | 'config' = 'dia';
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
        panel.iconPath = new vscode.ThemeIcon('calendar');
        panel.webview.onDidReceiveMessage(m => void this.mensaje(m));
        panel.onDidDispose(() => { this.panel = undefined; });
        panel.onDidChangeViewState(e => { if (e.webviewPanel.visible) void this.actualizar(); });
        this.pintarMarco();
    }

    pintarMarco(): void {
        if (this.panel) {
            this.panel.webview.html = marco(this.panel.webview, CSS_DIA,
                '<div id="dia"><div class="aviso">leyendo el día…</div></div>', SCRIPT_DIA);
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
        const d = this.datos;
        if (!this.panel || !d) return;
        this.teclas.clear();
        const ahora = new Date();
        const h: string[] = [];
        h.push(`<div class="cab"><b>${esc(d.nombreDia)} ${esc(d.fecha)}</b>`
            + `<span class="dim">${ahora.toTimeString().slice(0, 5)}${d.semana ? ` · semana ${d.semana}` : ''}</span>`
            + '<span class="der dim"><a data-accion="refrescar" title="volver a preguntar, proveedores incluidos (r)">↻ recargar</a>'
            + ' · <a data-accion="config" title="de dónde sale cada cosa">⚙ configuración</a></span></div>');
        h.push(...this.agenda(d, ahora), ...this.hilos(), ...htmlPendientes(d, false), ...this.fallas(d));
        h.push('<div class="pie">⎋ vuelve al terminal · / busca · r recarga · t la vista de tareas · letra: llevar ese pendiente a su hilo</div>');
        for (const [k, f] of [['r', () => this.actualizar(true)],
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
                + `<span class="nombre">${esc(x.nombre)}</span>`
                + `<span class="dim">${esc(NOMBRE_ATENCION[x.atencion] ?? x.atencion)}${x.visto ? `, hace ${hace(x.visto)}` : ''}</span></div>`);
        }
        return h;
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
        }
        this.pintar(h);
    }

    private pintar(h: string[]): void {
        void this.panel?.webview.postMessage({ tipo: 'dia', html: h.join('\n') });
    }

    private async mensaje(m: { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string }): Promise<void> {
        if (m.tipo === 'listo') { this.render(); void this.actualizar(); return; }
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
            case 'dia': this.pantalla = 'dia'; this.render(); break;
            case 'calendario': await this.elegirCalendario(m.valor ?? ''); break;
            case 'plantilla': await this.cambiarPlantilla(m.valor === 'restablecer'); break;
            case 'directorios': await this.cambiarDirectorios(); break;
        }
    }
}