// La superficie de VS Code: un panel con un webview, como siempre (ver superficie.ts).

import * as vscode from 'vscode';

import type { CrearSuperficie } from './superficie';

export const superficieVscode: CrearSuperficie = avisos => {
    const panel = vscode.window.createWebviewPanel('telar.hoy', 'dashboard',
        { viewColumn: vscode.ViewColumn.Active, preserveFocus: false },
        { enableScripts: true, retainContextWhenHidden: true, localResourceRoots: [] });
    panel.iconPath = new vscode.ThemeIcon('calendar');
    panel.webview.onDidReceiveMessage(m => avisos.mensaje(m));
    panel.onDidDispose(() => avisos.cerrada());
    panel.onDidChangeViewState(e => avisos.cambio(e.webviewPanel.visible, e.webviewPanel.active));
    return {
        get cspSource() { return panel.webview.cspSource; },
        get visible() { return panel.visible; },
        get activa() { return panel.active; },
        html: pagina => { panel.webview.html = pagina; },
        enviar: m => { void panel.webview.postMessage(m); },
        // al frente, en su columna: en la activa, el dashboard saltaría de lugar a cada clic
        revelar: () => panel.reveal(undefined, false),
    };
};
