// «hoy»: el día entero en un panel del área central.
//
// Tres cosas y en este orden, el mismo de `telar hoy` en la terminal: lo que ya tiene hora,
// quién te espera, y lo que está por hacer. Nada más. Lo que saldría de un proveedor que no
// está declarado no aparece porque no existe, y eso se dice en vez de dejar un hueco.

import * as vscode from 'vscode';

import { irAHilo, mostrarTerminal } from '../acciones';
import { GLIFO, NOMBRE_ATENCION, esc, hace, hhmm, marco } from '../estilo';
import { modelo } from '../modelo';
import { CSS_DIA, Dia, SCRIPT_DIA, dia, htmlPendientes, olvidarDia } from './dia';
import { llevarPendiente } from './tareas';

export class PanelHoy {
    panel?: vscode.WebviewPanel;
    private datos?: Dia;
    private enCurso = false;
    private teclas = new Map<string, () => Promise<unknown> | unknown>();

    /** ⌥H: si «hoy» ya está al frente, devuelve el teclado al terminal. */
    alternar(): void {
        if (this.panel?.active) { void mostrarTerminal(); return; }
        this.abrir();
    }

    abrir(): void {
        if (this.panel) { this.panel.reveal(vscode.ViewColumn.Active, false); void this.actualizar(); return; }
        const panel = vscode.window.createWebviewPanel('telar.hoy', 'hoy',
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
        const d = this.datos;
        if (!this.panel || !d) return;
        this.teclas.clear();
        const ahora = new Date();
        const h: string[] = [];
        h.push(`<div class="cab"><b>${esc(d.nombreDia)} ${esc(d.fecha)}</b>`
            + `<span class="dim">${ahora.toTimeString().slice(0, 5)}${d.semana ? ` · semana ${d.semana}` : ''}</span>`
            + '<span class="der dim"><a data-accion="refrescar" title="volver a preguntar, proveedores incluidos (r)">↻ recargar</a></span></div>');
        h.push(...this.agenda(d, ahora), ...this.hilos(), ...htmlPendientes(d, false), ...this.fallas(d));
        h.push('<div class="pie">⎋ vuelve al terminal · / busca · r recarga · t la vista de tareas · letra: llevar ese pendiente a su hilo</div>');
        for (const [k, f] of [['r', () => this.actualizar(true)],
            ['t', () => vscode.commands.executeCommand('telar.tareas')]] as const) {
            if (!this.teclas.has(k)) this.teclas.set(k, f);
        }
        void this.panel.webview.postMessage({ tipo: 'dia', html: h.join('\n') });
    }

    private agenda(d: Dia, ahora: Date): string[] {
        const h = ['<h2>Agenda<small>número o clic: entrar</small></h2>'];
        if (d.error) return [...h, `<div class="fila dim">(${esc(d.error)})</div>`];
        if (d.agenda === null) {
            const pista = d.declarados.length
                ? 'todavía no se ha consultado a los proveedores (r)'
                : 'ningún proveedor declarado: telar no sabe de tu calendario hasta que lo nombres en <code>[proveedores.…]</code>';
            return [...h, `<div class="fila dim">${pista}</div>`];
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
            if (tecla && url) this.teclas.set(tecla, () => vscode.env.openExternal(vscode.Uri.parse(url)));
            let falta = '';
            if (e === proxima) {
                const min = Math.floor((Date.parse(cuando) - t) / 60000);
                falta = `<span class="cuando">← ${min <= 0 ? 'ahora' : min < 90 ? `en ${min} min`
                    : `en ${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')}`}</span>`;
            }
            h.push(`<div class="fila${e === proxima ? ' proxima' : ''}${url ? ' clic' : ''}"${url ? ` data-url="${esc(url)}"` : ''}>`
                + `<span class="tecla">${tecla && url ? `[${tecla}]` : ''}</span><span class="hora">${esc(hhmm(cuando))}</span>`
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
        if (!d.fallas.length) return [];
        return ['<h2>Proveedores</h2>', ...d.fallas.map(f => `<div class="fila dim">caído · ${esc(f)}</div>`)];
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
        }
    }
}