// El estilo: la letra y los colores del terminal, y las piezas de texto que todas las
// vistas comparten.
//
// Las cinco vistas son webviews y no árboles nativos por una sola razón: la API de VS Code
// no deja cambiarle la letra a un `TreeView`, y aquí la letra importa —esto se mira al lado
// del terminal y tiene que leerse como una continuación suya, no como otro programa—. Los
// colores salen de las variables `--vscode-terminal-*` del tema, así que la vista sigue al
// tema sin saber cuál es; la letra sale de la configuración del terminal, que no se expone
// como variable CSS.


import * as fs from 'fs';
import * as path from 'path';

/** Cómo se dibuja cada atención. Las cuatro palabras son las de `telar atencion`. */
export const GLIFO: Record<string, string> = { trabajando: '●', espera: '○', termino: '✓' };

/** Prioridad 1 alta, 2 media, 3 baja; 0 es sin prioridad, que también se ve. */
export const PRIORIDAD: Record<number, string> = { 0: '·', 1: '●', 2: '◐', 3: '○' };

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

/** La letra de las vistas: la del terminal de VS Code (la da su anfitrión), o una monoespaciada. */
export interface Letra { familia: string; tam: number; peso: string; altoLinea: number }
let leerLetra: () => Letra = () => ({ familia: 'Menlo, Consolas, monospace', tam: 13, peso: 'normal', altoLinea: 1 });
export function usarLetra(f: () => Letra): void { leerLetra = f; }

/** La letra y los colores del terminal de VS Code, como variables CSS. Fuera de VS Code, las
 *  variables `--vscode-*` no existen y rigen los colores de respaldo (los de la página web). */
export function estiloBase(): string {
    const l = leerLetra();
    const limpio = (t: string) => t.replace(/[<>{};]/g, '');
    // lo único calculado: la letra de la terminal, como variables; lo demás está en media/css
    return `:root { --letra: ${limpio(l.familia)}; --tam: ${l.tam}px; --peso: ${limpio(String(l.peso))}; --alto: ${((l.altoLinea || 1) * 1.3).toFixed(2)}; }
@layer base { ${estilo('tokens')}
${estilo('base')} }`;
}

/** Los estilos viven en media/css/<nombre>.css (se leen una vez y quedan en memoria): archivos de
 *  CSS de verdad, con su resaltado y su linter, que VS Code y la web usan igual. */
const estilos = new Map<string, string>();
let carpetaCss = '';
/** En el navegador no hay archivos que leer: los estilos llegan empaquetados (src/navegador). */
export function usarEstilos(css: Record<string, string>): void {
    for (const [nombre, texto] of Object.entries(css)) estilos.set(nombre, texto);
}
export function estilo(nombre: string): string {
    const guardado = estilos.get(nombre);
    if (guardado !== undefined) return guardado;
    if (!carpetaCss) {
        // de out/, out/vistas o out/web hacia arriba, hasta la carpeta de la extensión
        let d = __dirname;
        while (!fs.existsSync(path.join(d, 'media', 'css')) && path.dirname(d) !== d) d = path.dirname(d);
        carpetaCss = path.join(d, 'media', 'css');
    }
    let css = '';
    try { css = fs.readFileSync(path.join(carpetaCss, `${nombre}.css`), 'utf8'); } catch { /* sin archivo, sin estilo: se nota y se arregla */ }
    estilos.set(nombre, css);
    return css;
}

/** Un nonce para el CSP de una vista. Quien necesite marcar scripts propios (un lienzo) lo
 *  genera antes y se lo pasa a `marco`. */
export function nuevoNonce(): string {
    return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}

/** El HTML completo de una vista: política de contenido cerrada, estilo, cuerpo y script.
 *  `marcos`: los orígenes, además del propio, que la vista deja enmarcar (las apps con `url`). */
export function marco(_webview: { cspSource: string; cspConectar?: string }, css: string, cuerpo: string, script: string,
    nonce = nuevoNonce(), marcos: string[] = []): string {
    return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${_webview.cspSource} https: data:; frame-src ${[_webview.cspSource, ...marcos].join(' ')}; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';${_webview.cspConectar ? ` connect-src ${_webview.cspConectar};` : ''}">
<style>@layer base, vistas;\n${estiloBase()}\n@layer vistas { ${css} }</style></head>
<body data-vscode-context='{"preventDefaultContextMenuItems": true}'>${cuerpo}
<script nonce="${nonce}">const vscode = acquireVsCodeApi();
${script}</script></body></html>`;
}
