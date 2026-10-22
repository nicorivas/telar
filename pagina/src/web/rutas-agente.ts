// Las rutas de archivo que escribe el agente de un hilo (en su terminal, su respuesta, su conversación), como
// enlaces al visor de documentos (`arch:`, web/carpeta.ts), en la máquina del hilo. Una ruta absoluta o con `~`
// se abre tal cual; una relativa es de donde arrancó su agente, que según `[agente] carpeta` es la carpeta del hilo
// o la raíz (un agente residente, la suya). Como la página no lo sabe, prueba las dos. La de un hilo de otra
// máquina va como «máquina:ruta», y el backend se la pide a esa máquina por el bus (`/api/archivos?ruta=…`): con
// su raíz, que no es la de aquí, así que la carpeta va relativa a esa raíz. Una dirección web (`https://…`) se abre
// en una pestaña nueva de este navegador, que es el de la persona, viva donde viva el hilo.

import type { IDisposable, ILink, Terminal } from '@xterm/xterm';

import * as cli from '../cli';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import { hallar, RUTA } from './enlaces';
import * as ui from './ui';
import type { RutasVista } from './vistas-hilo';

/** Un hipervínculo que llegó a la terminal por OSC 8 (el texto va aparte de la dirección): una web, en una pestaña
 *  nueva; un `file://`, en el visor, en la máquina del hilo; otro, nada. */
export function abrirHipervinculo(uri: string, vista: RutasVista): void {
    let u: URL;
    try { u = new URL(uri); } catch { return; }
    if (u.protocol === 'http:' || u.protocol === 'https:') void ui.abrirExterno(u.href);
    else if (u.protocol === 'file:') void abrirRuta(decodeURIComponent(u.pathname), vista);
}

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

/** Abre en el visor una ruta que escribió el agente de un hilo. Una relativa, desde la carpeta del hilo si ahí
 *  existe y si no desde la raíz: en ese orden porque un nombre corto (`README.md`) existe también en la raíz, y una
 *  ruta larga desde la raíz casi nunca existe además bajo la carpeta del hilo. Si no está en ninguna, la del hilo,
 *  para que el visor diga que no está. */
export async function abrirRuta(ruta: string, vista: RutasVista): Promise<void> {
    const limpia = ruta.replace(/(?::\d+){1,2}$/, '');
    const { maquina, carpeta } = await lugarDe(vista);
    const en = (r: string): string => (maquina ? `${maquina}:${r}` : r);
    if (limpia.startsWith('/') || limpia.startsWith('~')) { await ui.abrirArchivo(en(limpia)); return; }
    const candidatas = [...new Set([rutas.unir(carpeta, limpia), limpia])].map(en);
    let elegida = candidatas[0];
    for (const c of candidatas) if (await existe(c)) { elegida = c; break; }
    await ui.abrirArchivo(elegida);
}

/** Si el backend encuentra el archivo (aquí, o en la máquina de «máquina:ruta»). */
async function existe(ruta: string): Promise<boolean> {
    try { return (await fetch(`/api/archivos?ruta=${encodeURIComponent(ruta)}`, { cache: 'no-store' })).ok; }
    catch { return false; }
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
 *  la abre en el visor en vez de navegar la página; uno a una web, en una pestaña nueva (no se va de la página). */
export function atenderClics(raiz: HTMLElement, vista: RutasVista): void {
    raiz.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
        if (!a || !raiz.contains(a)) return;
        const href = a.getAttribute('href') ?? '';
        if (/^https?:\/\//i.test(href)) { e.preventDefault(); void ui.abrirExterno(href); return; }
        const ruta = a.dataset.ruta ?? (href && !href.startsWith('#') && !/^[a-z][a-z0-9+.-]*:/i.test(href) ? decodeURIComponent(href.split('#')[0]) : '');
        if (!ruta) return;
        e.preventDefault();
        void abrirRuta(ruta, vista);
    });
}

/** Las rutas y las direcciones web de la terminal de un hilo, como enlaces de xterm (subrayadas al pasar; un clic
 *  las abre). Una larga que se partió en varias filas se encuentra entera (enlaces.ts). */
export function enlazarTerminal(term: Terminal, vista: RutasVista): IDisposable {
    return term.registerLinkProvider({
        provideLinks(y, listo) {
            const enlaces = hallar(term.buffer.active, term.cols, y).map((h): ILink => ({
                range: { start: h.desde, end: h.hasta }, text: h.texto,
                activate: () => void (h.tipo === 'web' ? ui.abrirExterno(h.texto) : abrirRuta(h.texto, vista)),
            }));
            listo(enlaces.length ? enlaces : undefined);
        },
    });
}
