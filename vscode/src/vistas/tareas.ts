// La vista «tareas» de la barra: los mismos pendientes de «hoy», en una columna estrecha.
//
// Los dibuja el mismo código (`dia.htmlPendientes`, con `compacto`), para que no se separen
// nunca: dos listas de pendientes que se ven distinto son dos listas, y una de ellas miente.

import * as vscode from 'vscode';

import { mostrarTerminal } from '../acciones';
import * as cli from '../cli';
import { marco } from '../estilo';
import { modelo } from '../modelo';
import { CSS_DIA, SCRIPT_DIA, dia, htmlPendientes, olvidarDia, pendientes } from './dia';

export class VistaTareas implements vscode.WebviewViewProvider {
    vista?: vscode.WebviewView;
    private listo = false;
    private ultimo = '';

    resolveWebviewView(v: vscode.WebviewView): void {
        this.vista = v;
        v.webview.options = { enableScripts: true };
        v.webview.onDidReceiveMessage(m => void this.mensaje(m));
        v.onDidChangeVisibility(() => { if (v.visible) void this.actualizar(); });
        v.onDidDispose(() => { this.vista = undefined; this.listo = false; });
        this.pintarMarco();
    }

    pintarMarco(): void {
        if (!this.vista) return;
        this.listo = false; this.ultimo = '';
        this.vista.webview.html = marco(this.vista.webview, CSS_DIA,
            '<div id="dia"><div class="aviso">leyendo el día…</div></div>', SCRIPT_DIA);
    }

    async actualizar(forzar = false): Promise<void> {
        if (!this.vista) return;
        if (forzar) olvidarDia();
        const d = await dia(forzar ? 0 : 45000, forzar);
        if (!this.listo) return;
        const html = htmlPendientes(d, true).join('\n');
        if (html === this.ultimo) return;
        this.ultimo = html;
        const urgentes = pendientes(d).filter(p => p.urgente).length;
        this.vista.description = d.error ? 'sin datos' : `${urgentes} urgentes`;
        void this.vista.webview.postMessage({ tipo: 'dia', html });
    }

    private async mensaje(m: { tipo: string; accion?: string; valor?: string; nuevo?: boolean; k?: string; url?: string }): Promise<void> {
        if (m.tipo === 'listo') { this.listo = true; void this.actualizar(); return; }
        if (m.tipo === 'url' && m.url && /^https:\/\//.test(m.url)) { await vscode.env.openExternal(vscode.Uri.parse(m.url)); return; }
        if (m.tipo === 'tecla' && m.k === 'r') { await this.actualizar(true); return; }
        if (m.tipo !== 'accion') return;
        if (m.accion === 'volver') { void mostrarTerminal(); return; }
        if (m.accion === 'pendiente' && m.valor) await llevarPendiente(m.valor, !!m.nuevo);
        if (m.accion === 'hecha' && m.valor) { await marcarHecha(m.valor); await this.actualizar(true); return; }
        // con ficha: el clic la abre en el dashboard para leerla y decidir; ⌘-clic, a su hilo
        if (m.accion === 'tarea' && m.valor) {
            if (m.nuevo) { const [, , ref] = JSON.parse(m.valor) as string[]; await llevarPendiente(ref, false); }
            else await vscode.commands.executeCommand('telar.tarea', m.valor);
        }
    }
}

/** Un pendiente no se marca desde aquí: se va a trabajarlo. `telar pendiente` busca el hilo
 *  del proyecto al que le toca, le pone el foco y le deja la frase escrita al agente que ya
 *  está ahí —sin enviarla—. Con ⌘ se fuerza un hilo nuevo. */
export async function llevarPendiente(ref: string, nuevo: boolean): Promise<void> {
    const r = await cli.pendiente(ref, nuevo);
    if (!r.datos) {
        void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude llevar «${ref}»`}`);
        return;
    }
    await modelo.sondear();
    void mostrarTerminal();
}

/** El ✓ de la lista: corre la acción que el proveedor declara con `rol: "hecha"`, sin abrir
 *  la ficha ni preguntar (se deshace reabriéndola). Si el proveedor no declara una, lo dice. */
export async function marcarHecha(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'hecha') ?? -1;
    if (k < 0) {
        void vscode.window.showWarningMessage(`telar: ${ficha.error ?? `${id} no se puede marcar hecha desde la lista: ábrela`}`);
        olvidarDia();
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k);
    olvidarDia();
    if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude marcar ${id}`}`); return false; }
    vscode.window.setStatusBarMessage(`✓ ${id} hecha`, 5000);
    return true;
}
