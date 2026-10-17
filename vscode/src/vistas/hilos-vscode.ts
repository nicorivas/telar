// La barra de hilos en VS Code: una vista lateral (WebviewView) que dibuja BarraHilos.

import * as vscode from 'vscode';

import { mostrarTerminal } from '../acciones';
import { BarraHilos } from './hilos';

export class VistaHilos extends BarraHilos implements vscode.WebviewViewProvider {
    resolveWebviewView(v: vscode.WebviewView): void {
        v.webview.options = { enableScripts: true };
        v.webview.onDidReceiveMessage(m => this.mensaje(m));
        v.onDidDispose(() => this.desconectar());
        // Abrir la barra de telar es ir a trabajar en la sesión: el terminal que la muestra
        // pasa al frente, como cuando se elige con ⌃P. Solo si lo encuentra: sin terminal
        // de la sesión, abrir la barra no le quita el foco a nadie.
        const alFrente = () => { if (v.visible) void mostrarTerminal({ soloSuyo: true }); };
        v.onDidChangeVisibility(alFrente);
        alFrente();
        this.conectar({
            get cspSource() { return v.webview.cspSource; },
            get visible() { return v.visible; },
            html: pagina => { v.webview.html = pagina; },
            enviar: m => { void v.webview.postMessage(m); },
            cabecera: c => {
                v.title = c.titulo;
                v.description = c.descripcion;
                v.badge = c.insignia ? { value: c.insignia.valor, tooltip: c.insignia.ayuda } : undefined;
            },
        });
    }
}
