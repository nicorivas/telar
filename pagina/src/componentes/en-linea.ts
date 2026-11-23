// Lo que escribe un agente o un hilo en lo que pide (el resumen y el detalle de la ventana de contestar, la ficha de su
// tarea): párrafos con `código`, **negrita** y enlaces. Un enlace es un [texto](https://…) o una dirección web suelta,
// hallada con la misma búsqueda que el resto de la página (web/enlaces.ts, `buscar`: sin la puntuación que cierra la
// frase); se abre en una pestaña nueva, sin acceso a esta página ni su dirección (que puede traer la llave), como
// `ui.abrirExterno`. Lo demás va como texto. Puro: lo usan componentes/contestar.ts y componentes/ficha-contestar.ts, y
// lo prueba npm run prueba:contestar.

import { esc } from '../estilo';
import { buscar } from '../web/enlaces';

/** `código` o [texto](https://…): lo que se separa antes de escapar, para que lo de adentro no se toque. */
const TROZO = /`([^`]+)`|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g;

/** Un enlace a una dirección web, en una pestaña nueva. */
const enlace = (url: string, html: string): string =>
    `<a class="contestar-enlace" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="${esc(url)}">${html}</a>`;

/** Un texto suelto con sus direcciones web como enlaces (`enlaces`), o tal cual. */
function conWebs(t: string, enlaces: boolean): string {
    if (!enlaces) return esc(t);
    let html = '', desde = 0;
    for (const h of buscar(t).filter(x => x.tipo === 'web')) {
        html += esc(t.slice(desde, h.i)) + enlace(h.texto, esc(h.texto));
        desde = h.j;
    }
    return html + esc(t.slice(desde));
}

/** Una línea: `código`, **negrita** y, con `enlaces`, [texto](https://…) y las direcciones sueltas como enlaces. Sin
 *  `enlaces` (el texto de una opción, que es un botón: un enlace adentro no se podría apretar), un [texto](…) queda en su
 *  texto, con la dirección en el globo. */
export function enLinea(t: string, enlaces = true): string {
    let html = '', desde = 0;
    for (const m of t.matchAll(TROZO)) {
        html += conWebs(t.slice(desde, m.index), enlaces);
        if (m[1] !== undefined) html += `<code>${conWebs(m[1], enlaces)}</code>`;
        else html += enlaces ? enlace(m[3], esc(m[2])) : `<span title="${esc(m[3])}">${esc(m[2])}</span>`;
        desde = m.index + m[0].length;
    }
    html += conWebs(t.slice(desde), enlaces);
    // la negrita al final, sobre todo: puede envolver un código o un enlace
    return html.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}

/** Párrafos (separados por una línea en blanco; los saltos sueltos, espacios), cada uno con `enLinea`. */
export const parrafos = (t: string): string => t.trim().split(/\n\s*\n/).filter(Boolean)
    .map(p => `<p>${enLinea(p.replace(/\s*\n\s*/g, ' '))}</p>`).join('');
