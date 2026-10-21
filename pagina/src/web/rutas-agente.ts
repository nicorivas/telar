// Las rutas de archivo que escribe el agente de un hilo (en su terminal, su respuesta, su conversación), como
// enlaces al visor de documentos (`arch:`, web/carpeta.ts), en la máquina del hilo. Una ruta absoluta o con `~`
// se abre tal cual; una relativa es de la carpeta del hilo, que es desde donde la escribió su agente. La de un
// hilo de otra máquina va como «máquina:ruta», y el backend se la pide a esa máquina por el bus
// (`/api/archivos?ruta=…`): con su raíz, que no es la de aquí, así que la carpeta va relativa a esa raíz.

import type { IDisposable, ILink, Terminal } from '@xterm/xterm';

import * as cli from '../cli';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import * as ui from './ui';
import type { RutasVista } from './vistas-hilo';

/** Las extensiones que se reconocen: las de los archivos de texto que el visor muestra. */
const EXTENSIONES = 'md|markdown|txt|toml|ya?ml|json|py|ts|js|mjs|sh|css|html|csv';

/** Una ruta a un archivo de texto: `/…`, `~/…` o relativa, con letras con tilde (`métodos/`), y quizás con
 *  `:línea` o `:línea:columna` detrás (se ignoran). No la de una dirección (`https://…/x.md`): lo de antes no puede
 *  ser parte de una ruta ni `:`. */
export const RUTA = new RegExp(String.raw`(?<![\p{L}\p{N}_/.~:@+-])(?:~?\/)?(?:[\p{L}\p{N}_.@+-]+\/)*[\p{L}\p{N}_@+-][\p{L}\p{N}_.@+-]*\.(?:${EXTENSIONES})(?::\d+){0,2}(?![\p{L}\p{N}_/-])`, 'gu');

/** Dónde vive lo que escribe un hilo: su máquina ('' esta) y su carpeta (aquí, absoluta; en otra máquina,
 *  relativa a su raíz). Se averigua al abrir, no al dibujar: la lista de hilos puede no haber llegado. */
async function lugarDe({ hilo, maquina }: RutasVista): Promise<{ maquina: string; carpeta: string }> {
    const h = maquina ? undefined : modelo.porNombre(hilo);
    // un hilo de otra máquina (rem:), o uno de la lista cuyo agente vive en otra (Gestión, en el servidor)
    const alla = maquina || (h?.remoto && h.remoto !== '?' && h.remoto !== modelo.aqui ? h.remoto : '');
    if (!alla) return { maquina: '', carpeta: h?.ruta ?? '' };
    // su carpeta, de la foto que publica esa máquina: la lista de aquí no la sabe (dice «/»)
    const r = await cli.espejos();
    const x = r.datos?.espejos.find(e => e.nombre === alla)?.hilos.find(y => y.nombre === hilo);
    return { maquina: alla, carpeta: x?.relativa ?? '' };
}

/** Abre en el visor una ruta que escribió el agente de un hilo. */
export async function abrirRuta(ruta: string, vista: RutasVista): Promise<void> {
    const limpia = ruta.replace(/(?::\d+){1,2}$/, '');
    const { maquina, carpeta } = await lugarDe(vista);
    const junta = limpia.startsWith('/') || limpia.startsWith('~') ? limpia : rutas.unir(carpeta, limpia);
    await ui.abrirArchivo(maquina ? `${maquina}:${junta}` : junta);
}

/** Las rutas de un texto ya dibujado (`raiz`), como enlaces `a.ruta[data-ruta]`: en los nodos de texto que no
 *  están ya en un enlace. Uno que el markdown hizo de una ruta (`README.md` parece un dominio de Moldavia, y el
 *  linkify lo vuelve `http://README.md`) también pasa a ser de la ruta. */
export function enlazar(raiz: HTMLElement): void {
    for (const a of raiz.querySelectorAll<HTMLAnchorElement>('a[href^="http://"]')) {
        const t = a.textContent ?? '';
        if (a.getAttribute('href') === `http://${t}` && new RegExp(`^${RUTA.source}$`, 'u').test(t)) {
            a.removeAttribute('href'); a.classList.add('ruta'); a.dataset.ruta = t;
        }
    }
    const caminante = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
        acceptNode: n => (n.parentElement?.closest('a') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    const nodos: Text[] = [];
    for (let n = caminante.nextNode(); n; n = caminante.nextNode()) nodos.push(n as Text);
    for (const nodo of nodos) {
        const texto = nodo.data;
        const hallados = [...texto.matchAll(RUTA)];
        if (!hallados.length) continue;
        const trozos = document.createDocumentFragment();
        let desde = 0;
        for (const m of hallados) {
            trozos.append(texto.slice(desde, m.index));
            const a = document.createElement('a');
            a.className = 'ruta'; a.dataset.ruta = m[0]; a.textContent = m[0]; a.title = `abrir ${m[0]}`;
            trozos.append(a);
            desde = m.index + m[0].length;
        }
        trozos.append(texto.slice(desde));
        nodo.replaceWith(trozos);
    }
}

/** Un clic en una ruta de `raiz` (las de `enlazar`, y un enlace relativo del markdown: `[la guía](docs/x.md)`)
 *  la abre en el visor en vez de navegar la página. */
export function atenderClics(raiz: HTMLElement, vista: RutasVista): void {
    raiz.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
        if (!a || !raiz.contains(a)) return;
        const href = a.getAttribute('href') ?? '';
        const ruta = a.dataset.ruta ?? (href && !href.startsWith('#') && !/^[a-z][a-z0-9+.-]*:/i.test(href) ? decodeURIComponent(href.split('#')[0]) : '');
        if (!ruta) return;
        e.preventDefault();
        void abrirRuta(ruta, vista);
    });
}

/** Las rutas de la terminal de un hilo, como enlaces de xterm (subrayadas al pasar; un clic las abre). Se
 *  buscan en la línea lógica: una ruta larga se parte al ancho de la terminal, y sus pedazos se juntan. */
export function enlazarTerminal(term: Terminal, vista: RutasVista): IDisposable {
    return term.registerLinkProvider({
        provideLinks(y, listo) {
            const buf = term.buffer.active;
            let ini = y - 1, fin = y - 1;
            while (ini > 0 && buf.getLine(ini)?.isWrapped) ini--;
            while (buf.getLine(fin + 1)?.isWrapped) fin++;
            // el texto de esas filas, con la celda de cada letra (una letra ancha ocupa dos celdas)
            let texto = '';
            const celdas: { x: number; y: number }[] = [];
            for (let fila = ini; fila <= fin; fila++) {
                const linea = buf.getLine(fila);
                if (!linea) continue;
                for (let x = 0; x < linea.length; x++) {
                    const c = linea.getCell(x);
                    if (!c || c.getWidth() === 0) continue;
                    const letras = c.getChars() || ' ';
                    texto += letras;
                    for (let k = 0; k < letras.length; k++) celdas.push({ x: x + 1, y: fila + 1 });
                }
            }
            const enlaces: ILink[] = [];
            for (const m of texto.matchAll(RUTA)) {
                const start = celdas[m.index], end = celdas[m.index + m[0].length - 1];
                if (!start || !end || start.y > y || end.y < y) continue;
                enlaces.push({ range: { start, end }, text: m[0], activate: () => void abrirRuta(m[0], vista) });
            }
            listo(enlaces.length ? enlaces : undefined);
        },
    });
}
