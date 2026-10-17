// El anfitrión de VS Code: cada pedido del dashboard, con la API de VS Code. Es lo que el
// dashboard hacía antes directamente; ver anfitrion.ts.

import * as vscode from 'vscode';

import { irAHilo, mostrarTerminal } from './acciones';
import { usarAjustes } from './cli';
import { usarLetra } from './estilo';
import type { Anfitrion, Opcion, OpcionesAviso, OpcionesMenu } from './anfitrion';

type Boton = string | OpcionesAviso;

/** Los botones y las opciones de un aviso, en el orden que pide VS Code (opciones primero). */
function partir(botones: Boton[]): [vscode.MessageOptions | undefined, string[]] {
    const opciones = botones.find((b): b is OpcionesAviso => typeof b !== 'string');
    return [opciones, botones.filter((b): b is string => typeof b === 'string')];
}

function avisar(f: typeof vscode.window.showWarningMessage, texto: string, botones: Boton[]): Promise<string | undefined> {
    const [opciones, nombres] = partir(botones);
    return Promise.resolve(opciones ? f(texto, opciones, ...nombres) : f(texto, ...nombres));
}

export const anfitrionVscode: Anfitrion = {
    aviso: (t, ...b) => avisar(vscode.window.showWarningMessage, t, b),
    falla: (t, ...b) => avisar(vscode.window.showErrorMessage, t, b),
    info: (t, ...b) => avisar(vscode.window.showInformationMessage, t, b),
    estado: (t, ms = 5000) => { vscode.window.setStatusBarMessage(t, ms); },
    progreso: (o, trabajo) => Promise.resolve(vscode.window.withProgress(
        { location: o.ventana ? vscode.ProgressLocation.Window : vscode.ProgressLocation.Notification, title: o.title }, trabajo)),
    campo: o => Promise.resolve(vscode.window.showInputBox(o)),
    elegir: async <T extends Opcion>(opciones: T[], menu?: OpcionesMenu) => {
        // el separador de VS Code es un `kind`; aquí, una marca en el ítem
        const items = opciones.map(o => ({ ...o, kind: o.separador ? vscode.QuickPickItemKind.Separator : undefined, _o: o }));
        const e = await vscode.window.showQuickPick(items, menu);
        return e?._o;
    },
    abrirExterno: async url => { await vscode.env.openExternal(vscode.Uri.parse(url)); },
    abrirArchivo: async (ruta, linea) => {
        const doc = await vscode.workspace.openTextDocument(ruta);
        const pos = new vscode.Position(Math.max(0, (linea ?? 1) - 1), 0);
        await vscode.window.showTextDocument(doc, linea ? { selection: new vscode.Range(pos, pos) } : {});
    },
    mostrarCarpeta: async ruta => { await vscode.commands.executeCommand('revealInExplorer', vscode.Uri.file(ruta)); },
    copiar: async t => { await vscode.env.clipboard.writeText(t); },
    markdown: async t => (await vscode.commands.executeCommand<string>('markdown.api.render', t)) ?? '',
    irAHilo: (hilo, crear, remoto) => irAHilo(hilo, crear, remoto),
    mostrarTerminal: () => mostrarTerminal(),
    orden: (id, ...args) => Promise.resolve(vscode.commands.executeCommand(id, ...args)),
};

/** Lo que solo VS Code sabe y el dashboard necesita: su letra de terminal y los ajustes `telar.*`. */
export function conectarVscode(): void {
    usarAjustes((clave, porDefecto) => vscode.workspace.getConfiguration('telar').get(clave) ?? porDefecto);
    usarLetra(() => {
        const term = vscode.workspace.getConfiguration('terminal.integrated');
        const editor = vscode.workspace.getConfiguration('editor');
        return {
            familia: term.get<string>('fontFamily') || editor.get<string>('fontFamily') || 'Menlo, Consolas, monospace',
            tam: term.get<number>('fontSize') || editor.get<number>('fontSize') || 12,
            peso: String(term.get<string | number>('fontWeight') ?? 'normal'),
            altoLinea: term.get<number>('lineHeight') || 1,
        };
    });
}
