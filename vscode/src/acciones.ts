// Las acciones que comparten las vistas: ir a un hilo, y devolver el teclado al terminal.

import * as vscode from 'vscode';

import * as cli from './cli';
import { modelo } from './modelo';

/** El terminal donde corre la sesión, al frente y con el teclado.
 *
 *  Se busca por nombre: el que se llame como la sesión, o «telar». Si no hay ninguno, el
 *  activo, que es lo más probable que sea. Esto no abre nada: mover el foco a un terminal
 *  que la persona no pidió es peor que no moverlo. */
export function mostrarTerminal(): void {
    const sesion = modelo.sesion || 'telar';
    const suyo = vscode.window.terminals.find(t => t.name === sesion || /telar/i.test(t.name));
    (suyo ?? vscode.window.activeTerminal)?.show(false);
}

/** `telar ir`. Con `crear`, lo abre si no está vivo. */
export async function irAHilo(hilo: string, crear = false): Promise<void> {
    const r = await cli.ir(hilo, crear);
    if (!r.ok) {
        void vscode.window.showWarningMessage(`telar: ${r.err.trim().split('\n').pop() ?? `no pude ir a «${hilo}»`}`);
        return;
    }
    await modelo.sondear();
    mostrarTerminal();
}
