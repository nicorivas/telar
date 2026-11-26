// Abrir una dirección de afuera en una pestaña nueva: los enlaces de la terminal de un hilo (web/rutas-agente.ts), los de
// la página (web/ui.ts `abrirExterno`) y los del visor (web/carpeta.ts).
//
// Safari abre una pestaña solo dentro del gesto que la pide: el clic o la tecla, lo que corre en ese mismo evento (xterm
// activa un enlace al soltar el mouse, y vale), sus microtareas y un setTimeout corto. Después de un fetch, o de un
// setTimeout de 1,5 s, la bloquea sin decir nada. Medido con el WebKit de macOS 26 y el bloqueo de ventanas de Safari
// puesto (el clic en la terminal y lo de después de un fetch quedaron en `npm run prueba:abrir-safari`); Chrome y Firefox
// dejan unos segundos. Por eso todo se abre aquí, sin `await` antes.
//
// Sin `noopener` en las opciones de window.open: con él devuelve null siempre, abra o no, y no se sabe si Safari la
// bloqueó. Se abre vacía (la pestaña nueva es de esta página por un momento), se le corta el `opener` y la dirección se
// carga desde ella con un enlace `noreferrer`: la de afuera no recibe ni esta página ni su dirección, que puede traer la
// llave. Si el navegador no la abrió, un aviso lo dice y ofrece un botón que la abre en su mismo clic.

import * as interfaz from './interfaz';

const WEB = /^https?:\/\//i;

/** Abre `url` en una pestaña nueva ahora mismo (en el gesto que llama). True si el navegador la abrió. Una dirección
 *  que no es web (`mailto:`, `vscode:`) se le pasa al navegador como antes, sin saber si abrió; `javascript:` y `data:`,
 *  nunca. */
export function abrirYa(url: string): boolean {
    if (!WEB.test(url)) {
        if (/^(javascript|data|vbscript):/i.test(url.trim())) return false;
        window.open(url, '_blank', 'noopener,noreferrer');
        return true;
    }
    let w: Window | null = null;
    try { w = window.open('', '_blank'); } catch { w = null; }
    if (!w) return false;
    llenar(w, url);
    return true;
}

/** La pestaña recién abierta (vacía, de esta página): sin acceso de vuelta a esta, y con la dirección cargada desde ella
 *  sin referencia. Si algo de eso no se puede, la dirección igual. */
function llenar(w: Window, url: string): void {
    try { w.opener = null; } catch { /* algunos navegadores no lo dejan escribir: la de afuera es de otro origen igual */ }
    try {
        const a = w.document.createElement('a');
        a.href = url;
        a.rel = 'noreferrer';
        (w.document.body ?? w.document.documentElement).appendChild(a);
        a.click();
    } catch { w.location.replace(url); }
}

/** Abre `url` en una pestaña nueva; si el navegador no deja (Safari fuera del gesto), un aviso con un botón «Abrir» que
 *  la abre en su mismo clic (o ⏎). True si quedó abierta. Lo primero corre sin `await`: llamarla en el evento del clic. */
export async function abrir(url: string): Promise<boolean> {
    if (abrirYa(url)) return true;
    let abierta = false;
    const corta = url.length > 90 ? `${url.slice(0, 90)}…` : url;
    const b = await interfaz.preguntar(`El navegador no dejó abrir la pestaña. Para abrirla, aprieta Abrir (o ⏎).\n${corta}`, ['Abrir'],
        { enElClic: x => { if (x === 'Abrir') abierta = abrirYa(url); } });
    if (b !== 'Abrir') return false;
    if (!abierta) interfaz.avisar(`El navegador tampoco la dejó abrir así. La dirección: ${url}`, 'falla', 15000);
    return abierta;
}
