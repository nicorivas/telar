// Las rutas de archivo que escribe el agente de un hilo (en su terminal, su respuesta, su conversación), como
// enlaces al visor de documentos (`arch:`, web/carpeta.ts), en la máquina del hilo. Una ruta absoluta o con `~`
// se abre tal cual; una relativa es de donde arrancó su agente, que según `[agente] carpeta` es la carpeta del hilo
// o la raíz (un agente residente, la suya). Como la página no lo sabe, prueba las dos. La de un hilo de otra
// máquina va como «máquina:ruta», y el backend se la pide a esa máquina por el bus (`/api/archivos?ruta=…`): con
// su raíz, que no es la de aquí, así que la carpeta va relativa a esa raíz. Una dirección web (`https://…`) se abre
// en una pestaña nueva de este navegador, que es el de la persona, viva donde viva el hilo. La dirección de un objeto
// de telar (`tarea:T366`, `hilo:Telar`, la de un tipo de un módulo) la abre la página donde se ve ese objeto.

import type { IDisposable, ILink, Terminal } from '@xterm/xterm';

import * as cli from '../cli';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import { buscar, hallar, RUTA, usarTipos } from './enlaces';
import * as ui from './ui';
import type { RutasVista } from './vistas-hilo';

/** Los tipos de dirección que sabe esta máquina (los de sus módulos también): se piden una vez, y mientras no
 *  llegan valen los de telar. */
let tiposPedidos = false;
function pedirTipos(): void {
    if (tiposPedidos) return;
    tiposPedidos = true;
    void fetch('/api/objetos/tipos', { cache: 'no-store' })
        .then(r => (r.ok ? r.json() as Promise<{ tipos?: { tipo: string }[] }> : undefined))
        .then(j => { if (j?.tipos) usarTipos(j.tipos.map(t => t.tipo)); })
        .catch(() => undefined);
}

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

/** Las rutas y las direcciones de objetos de un texto ya dibujado (`raiz`), como enlaces `a.ruta[data-ruta]` y
 *  `a.ruta[data-direccion]` (con `rutas` en false, solo las direcciones): en los nodos de texto que no están ya en
 *  un enlace. Uno que el markdown hizo de una ruta (`README.md` parece un dominio de Moldavia, y el
 *  linkify lo vuelve `http://README.md`) también pasa a ser de la ruta. */
export function enlazar(raiz: HTMLElement, rutas = true): void {
    pedirTipos();
    if (rutas) for (const a of raiz.querySelectorAll<HTMLAnchorElement>('a[href^="http://"]')) {
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
        // las webs de un texto ya las hizo enlaces el markdown
        const hallados = buscar(texto).filter(h => h.tipo === 'direccion' || (rutas && h.tipo === 'ruta'));
        if (!hallados.length) continue;
        const trozos = document.createDocumentFragment();
        let desde = 0;
        for (const h of hallados) {
            trozos.append(texto.slice(desde, h.i));
            const a = document.createElement('a');
            a.className = 'ruta'; a.textContent = h.texto; a.title = `abrir ${h.texto}`;
            if (h.tipo === 'direccion') a.dataset.direccion = h.texto; else a.dataset.ruta = h.texto;
            trozos.append(a);
            desde = h.j;
        }
        trozos.append(texto.slice(desde));
        nodo.replaceWith(trozos);
    }
}

/** Un clic en una ruta de `raiz` (las de `enlazar`, y un enlace relativo del markdown: `[la guía](docs/x.md)`)
 *  la abre en el visor en vez de navegar la página; uno a una web, en una pestaña nueva (no se va de la página); una
 *  dirección, donde se ve su objeto. */
export function atenderClics(raiz: HTMLElement, vista: RutasVista): void {
    raiz.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
        if (!a || !raiz.contains(a)) return;
        if (a.dataset.direccion) { e.preventDefault(); void ui.abrirDireccion(a.dataset.direccion); return; }
        const href = a.getAttribute('href') ?? '';
        if (/^https?:\/\//i.test(href)) { e.preventDefault(); void ui.abrirExterno(href); return; }
        const ruta = a.dataset.ruta ?? (href && !href.startsWith('#') && !/^[a-z][a-z0-9+.-]*:/i.test(href) ? decodeURIComponent(href.split('#')[0]) : '');
        if (!ruta) return;
        e.preventDefault();
        void abrirRuta(ruta, vista);
    });
}

/** Las rutas, las direcciones web y las de objetos de la terminal de un hilo, como enlaces de xterm (subrayadas al
 *  pasar; un clic las abre). Una larga que se partió en varias filas se encuentra entera (enlaces.ts). */
export function enlazarTerminal(term: Terminal, vista: RutasVista): IDisposable {
    pedirTipos();
    const abrir = (h: { tipo: string; texto: string }) => (h.tipo === 'web' ? ui.abrirExterno(h.texto)
        : h.tipo === 'direccion' ? ui.abrirDireccion(h.texto) : abrirRuta(h.texto, vista));
    return term.registerLinkProvider({
        provideLinks(y, listo) {
            const enlaces = hallar(term.buffer.active, term.cols, y).map((h): ILink => ({
                range: { start: h.desde, end: h.hasta }, text: h.texto, activate: () => void abrir(h),
            }));
            listo(enlaces.length ? enlaces : undefined);
        },
    });
}
