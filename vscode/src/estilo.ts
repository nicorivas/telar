// El estilo: la letra y los colores del terminal, y las piezas de texto que todas las
// vistas comparten.
//
// Las cinco vistas son webviews y no árboles nativos por una sola razón: la API de VS Code
// no deja cambiarle la letra a un `TreeView`, y aquí la letra importa —esto se mira al lado
// del terminal y tiene que leerse como una continuación suya, no como otro programa—. Los
// colores salen de las variables `--vscode-terminal-*` del tema, así que la vista sigue al
// tema sin saber cuál es; la letra sale de la configuración del terminal, que no se expone
// como variable CSS.

import * as vscode from 'vscode';

/** Cómo se dibuja cada atención. Las cuatro palabras son las de `telar atencion`. */
export const GLIFO: Record<string, string> = { trabajando: '●', espera: '○', termino: '✓' };

/** Prioridad 1 alta, 2 media, 3 baja. Sin prioridad, nada. */
export const PRIORIDAD: Record<number, string> = { 1: '●', 2: '◐', 3: '○' };

export const NOMBRE_ATENCION: Record<string, string> = {
    trabajando: 'trabajando', espera: 'te espera', termino: 'terminó',
};

export function esc(s: string): string {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** `5400` → `1h30`. Vacío si no hay nada que decir, igual que en la terminal. */
export function duracion(segundos: number | undefined): string {
    const minutos = Math.floor((segundos ?? 0) / 60);
    if (minutos <= 0) return '';
    return minutos >= 60 ? `${Math.floor(minutos / 60)}h${String(minutos % 60).padStart(2, '0')}` : `${minutos}m`;
}

/** «hace cuánto», en palabras. */
export function hace(iso: string | null | undefined): string {
    if (!iso) return '';
    const ms = Date.now() - Date.parse(iso);
    if (Number.isNaN(ms)) return '';
    const min = Math.round(ms / 60000);
    if (min < 60) return `${min} min`;
    if (min < 60 * 24) return `${Math.round(min / 60)} h`;
    return `${Math.round(min / 1440)} d`;
}

/** Lo mismo, corto, para una columna alineada: `49m`, `2h`, `4d`. */
export function haceCorto(iso: string | null | undefined): string {
    return hace(iso).replace(/ min$/, 'm').replace(/ h$/, 'h').replace(/ d$/, 'd');
}

export const hhmm = (iso: string): string => iso.slice(11, 16);

export const limpiarMd = (t: string): string => t.replace(/\*\*/g, '').replace(/`/g, '');

/** Para buscar sin acentos ni mayúsculas. */
export const normalizar = (t: string): string =>
    t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** La letra y los colores del terminal de VS Code, como variables CSS. */
export function estiloBase(): string {
    const term = vscode.workspace.getConfiguration('terminal.integrated');
    const editor = vscode.workspace.getConfiguration('editor');
    const familia = (term.get<string>('fontFamily') || editor.get<string>('fontFamily') || 'Menlo, Consolas, monospace')
        .replace(/[<>{};]/g, '');
    const tam = term.get<number>('fontSize') || editor.get<number>('fontSize') || 12;
    const peso = String(term.get<string | number>('fontWeight') ?? 'normal').replace(/[<>{};]/g, '');
    const alto = (term.get<number>('lineHeight') || 1) * 1.3;
    return `
  :root {
    --fg: var(--vscode-terminal-foreground, var(--vscode-foreground));
    --bg: var(--vscode-terminal-background, var(--vscode-panel-background, var(--vscode-editor-background)));
    --dim: var(--vscode-terminal-ansiBrightBlack, #6c7086);
    --linea: color-mix(in srgb, var(--fg) 16%, transparent);
    --sel: var(--vscode-terminal-selectionBackground, rgba(128,128,128,.25));
    --hover: color-mix(in srgb, var(--fg) 7%, transparent);
    --azul: var(--vscode-terminal-ansiBlue); --amarillo: var(--vscode-terminal-ansiYellow);
    --verde: var(--vscode-terminal-ansiGreen); --rojo: var(--vscode-terminal-ansiRed);
    --magenta: var(--vscode-terminal-ansiBrightMagenta); --cian: var(--vscode-terminal-ansiCyan);
  }
  html, body { background: var(--bg); }
  body { color: var(--fg); font-family: ${familia}, monospace; font-size: ${tam}px; font-weight: ${peso};
         line-height: ${alto.toFixed(2)}; margin: 0; -webkit-font-smoothing: antialiased; }
  a { color: var(--azul); text-decoration: none; cursor: pointer; } a:hover { text-decoration: underline; }
  .dim { color: var(--dim); }
  .aviso { color: var(--dim); padding: 1.5em 1.5ch; }
  .aviso code { color: var(--verde); }
  [hidden] { display: none !important; }   /* .fila y .tarea son flex: sin esto, hidden no oculta */
`;
}

/** El HTML completo de una vista: política de contenido cerrada, estilo, cuerpo y script. */
export function marco(_webview: vscode.Webview, css: string, cuerpo: string, script: string): string {
    const nonce = Math.random().toString(36).slice(2);
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${_webview.cspSource} https: data:; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<style>${estiloBase()}${css}</style></head>
<body data-vscode-context='{"preventDefaultContextMenuItems": true}'>${cuerpo}
<script nonce="${nonce}">const vscode = acquireVsCodeApi();
${script}</script></body></html>`;
}
