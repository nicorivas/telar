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
            if (m.nuevo) { const [proveedor, , ref] = JSON.parse(m.valor) as string[]; await llevarPendiente(ref, false, proveedor); }
            else await vscode.commands.executeCommand('telar.tarea', m.valor);
        }
    }
}

/** Un pendiente no se marca desde aquí: se va a trabajarlo. `telar pendiente` busca el hilo
 *  del proyecto al que le toca, le pone el foco y le deja la frase escrita al agente que ya
 *  está ahí —sin enviarla—. Con ⌘ se fuerza un hilo nuevo. */
export async function llevarPendiente(ref: string, nuevo: boolean, proveedor = ''): Promise<void> {
    // buscar el hilo, retomarlo o encargárselo a un agente del servidor toma unos segundos:
    // una notificación lo dice mientras tanto, para que el Enter no parezca perdido
    const r = await vscode.window.withProgress(
        { location: vscode.ProgressLocation.Notification, title: `telar: llevando ${ref} a su hilo…` },
        () => cli.pendiente(ref, nuevo, proveedor));
    if (!r.datos) {
        void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude llevar «${ref}»`}`);
        return;
    }
    await modelo.sondear();
    void mostrarTerminal();
}

/** El ✓ de la lista: corre la acción que el proveedor declara con `rol: "hecha"`, sin abrir
 *  la ficha ni preguntar (se deshace reabriéndola). Si el proveedor no declara una, lo dice. */
/** Una fecha nueva para una tarea: las de siempre a un clic, u otra escrita a mano. Devuelve
 *  AAAA-MM-DD (o +Nd, que el proveedor cuenta desde su fecha), o undefined si se cancela. */
export async function elegirFecha(titulo: string): Promise<string | undefined> {
    const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const desde = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d; };
    const dias = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const hoy = new Date();
    const lunes = desde(((8 - hoy.getDay()) % 7) || 7);
    const finDeMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);
    const opciones: (vscode.QuickPickItem & { valor: string })[] = [
        { label: 'mañana', description: `${dias[desde(1).getDay()]} ${iso(desde(1))}`, valor: iso(desde(1)) },
        { label: 'pasado mañana', description: `${dias[desde(2).getDay()]} ${iso(desde(2))}`, valor: iso(desde(2)) },
        { label: 'el próximo lunes', description: iso(lunes), valor: iso(lunes) },
        { label: 'en una semana', description: `${dias[desde(7).getDay()]} ${iso(desde(7))}`, valor: iso(desde(7)) },
        { label: 'fin de mes', description: `${dias[finDeMes.getDay()]} ${iso(finDeMes)}`, valor: iso(finDeMes) },
        { label: 'otra fecha…', description: 'AAAA-MM-DD, 15-10, 15-oct o +10d', valor: '' },
    ];
    const elegida = await vscode.window.showQuickPick(opciones, { title: `Nueva fecha · ${titulo}`, placeHolder: 'para cuándo queda', ignoreFocusOut: true });
    if (!elegida) return undefined;
    if (elegida.valor) return elegida.valor;
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const leer = (t: string): string => {
        t = t.trim().toLowerCase();
        if (/^\+\d+d$/.test(t) || /^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
        const m = t.match(/^(\d{1,2})[-/ ](\d{1,2}|[a-zé]{3,})$/);
        if (!m) return '';
        const mes = /^\d+$/.test(m[2]) ? Number(m[2]) : meses.indexOf(m[2].slice(0, 3)) + 1;
        if (mes < 1 || mes > 12) return '';
        let d = new Date(hoy.getFullYear(), mes - 1, Number(m[1]));
        if (d.getDate() !== Number(m[1])) return '';  // un día que ese mes no tiene (31-feb)
        if (d < new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())) d = new Date(hoy.getFullYear() + 1, mes - 1, Number(m[1]));
        return iso(d);
    };
    const escrita = await vscode.window.showInputBox({ title: `Nueva fecha · ${titulo}`, prompt: 'AAAA-MM-DD, 15-10, 15-oct o +10d', ignoreFocusOut: true,
        validateInput: t => (t.trim() && !leer(t) ? 'no entiendo esa fecha' : undefined) });
    return escrita?.trim() ? leer(escrita) || undefined : undefined;
}

/** Reagendar una tarea desde la lista: la acción con rol «fecha» de su proveedor, con la fecha elegida. */
export async function reagendar(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'fecha') ?? -1;
    if (k < 0) {
        void vscode.window.showWarningMessage(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar la fecha`}`);
        return false;
    }
    const fecha = await elegirFecha(`${id} ${ficha.datos?.titulo ?? ''}`.trim());
    if (!fecha) return false;
    const r = await cli.accionTarea(id, proveedor, k, fecha);
    olvidarDia();
    if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude mover ${id}`}`); return false; }
    vscode.window.setStatusBarMessage(`${id} → ${fecha}`, 5000);
    return true;
}

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
