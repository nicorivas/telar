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

/** Elegir quién hace una tarea: la persona (que es lo de siempre, sin asignar), ella misma asignada a
 *  propósito, el equipo que ofrece el proveedor, u otro nombre escrito. Devuelve el texto para la
 *  acción («none» para dejarla sin asignar), o undefined si se cancela. */
export async function elegirDueno(titulo: string, actual: string, opciones: string[], persona: string,
    vineta = false): Promise<string | undefined> {
    type Item = vscode.QuickPickItem & { valor?: string };
    const yo = persona ? persona[0].toUpperCase() + persona.slice(1) : 'yo';
    const items: Item[] = [
        // una viñeta de un documento sin responsable no es de nadie; una tarea sin dueño es de la persona
        vineta ? { label: 'Sin responsable', description: 'la viñeta no dice quién la hace', valor: 'none' }
            : { label: `${yo} (sin asignar)`, description: 'lo de siempre: una tarea sin dueño es tuya', valor: 'none' },
        { label: yo, description: 'asignada a ti a propósito', valor: yo },
        { label: '', kind: vscode.QuickPickItemKind.Separator },
        ...opciones.filter(o => o.toLowerCase() !== yo.toLowerCase()).map(o => ({ label: o, valor: o })),
        { label: '', kind: vscode.QuickPickItemKind.Separator },
        { label: 'otra persona…', valor: '' },
    ];
    for (const it of items) if (it.valor !== undefined && it.valor && (it.valor === actual || (it.valor === 'none' && !actual))) it.description = `${it.description ?? ''} ← ahora`.trim();
    const e = await vscode.window.showQuickPick(items, { title: titulo, placeHolder: 'quién hace esta tarea' });
    if (!e) return undefined;
    if (e.valor) return e.valor;
    const escrito = await vscode.window.showInputBox({ title: titulo, prompt: 'el nombre de quien la hace', ignoreFocusOut: true });
    return escrito?.trim() || undefined;
}

/** El responsable de una tarea, desde su fila: la acción del proveedor con `rol: dueno`. */
export async function asignar(valor: string, actual: string, persona: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const acciones = ficha.datos?.acciones ?? [];
    const k = acciones.findIndex(a => a.rol === 'dueno');
    if (k < 0) {
        void vscode.window.showWarningMessage(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar el responsable`}`);
        return false;
    }
    const quien = await elegirDueno(`${id} ${ficha.datos?.titulo ?? ''}`.trim(), actual, acciones[k].opciones ?? [], persona);
    if (!quien) return false;
    const r = await cli.accionTarea(id, proveedor, k, quien);
    olvidarDia();
    if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude asignar ${id}`}`); return false; }
    vscode.window.setStatusBarMessage(`${id} → ${quien === 'none' ? 'sin asignar' : quien}`, 5000);
    return true;
}

/** Correr la acción de una tarea que tiene ese `rol` (estrella, equipo…) sin abrir su ficha. */
async function alternarPorRol(valor: string, rol: string, queEs: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === rol) ?? -1;
    if (k < 0) {
        void vscode.window.showWarningMessage(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece ${queEs}`}`);
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k, '');
    olvidarDia();
    if (!r.datos) { void vscode.window.showWarningMessage(`telar: ${r.error ?? `no pude cambiar ${queEs} de ${id}`}`); return false; }
    vscode.window.setStatusBarMessage(`${id}: ${ficha.datos?.acciones?.[k].nombre ?? queEs}`, 4000);
    return true;
}

/** Poner o quitar la estrella de una tarea: la acción del proveedor con `rol: estrella`. */
export const alternarEstrella = (valor: string) => alternarPorRol(valor, 'estrella', 'la estrella');

/** Compartir una tarea con el equipo, o dejar de hacerlo: la acción con `rol: equipo` (`telar equipo`). */
export async function alternarEquipo(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // la acción dice qué hará: «○ compartir…» la comparte, «◉ dejar de compartir…» la deja
    const antes = (await cli.tarea(id, proveedor)).datos?.acciones?.find(a => a.rol === 'equipo')?.nombre ?? '';
    if (!await alternarPorRol(valor, 'equipo', 'compartir con el equipo')) return false;
    const compartida = antes.startsWith('○');
    void vscode.window.showInformationMessage(compartida
        ? `telar: ${id} ahora la ve el equipo (título, estado, prioridad y fecha); pueden sugerir subirla.`
        : `telar: ${id} dejó de compartirse con el equipo.`);
    return true;
}

export async function marcarHecha(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // un viaje: la acción por su rol. Un telar de antes (el de otra máquina sin actualizar) no
    // conoce --rol: entonces, como siempre, la ficha primero para saber su número
    const directo = await vscode.window.withProgress({ location: vscode.ProgressLocation.Window, title: `✓ ${id}…` },
        () => cli.accionPorRol(id, proveedor, 'hecha'));
    if (directo.datos) {
        olvidarDia();
        vscode.window.setStatusBarMessage(`✓ ${id} hecha`, 5000);
        return true;
    }
    if (!/--rol|unrecognized|argumentos/i.test(directo.error ?? '')) {
        void vscode.window.showWarningMessage(`telar: ${directo.error ?? `no pude marcar ${id}`}`);
        olvidarDia();
        return false;
    }
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
