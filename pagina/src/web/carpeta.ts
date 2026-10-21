// La carpeta de un hilo y uno de sus archivos (`/api/hilos/documento`), o un archivo cualquiera del repositorio
// (`arch:<ruta>`): la lista de archivos arriba, y el elegido abajo. Una ruta de otra máquina («servidor:docs/x.md»)
// o con `~` se lee sola, sin su carpeta (`/api/archivos`, que se la pide a esa máquina por el bus). Un .html se ve
// dibujado, en un iframe aislado (`/api/archivos/ver`: sus scripts corren en un origen propio, sin la llave ni la
// API de la página), con su código a un clic. Solo lee. Se dibuja en un elemento de la página; sus estilos, en
// media/css/documento.css (con @scope, en `.v-documento`).

import { esc } from '../estilo';
import { modelo } from '../modelo';
import * as rutas from '../rutas';

/** La carpeta de un hilo y uno de sus archivos, como la da `/api/hilos/documento`. */
export interface Documento {
    hilo: string; titulo: string; error?: string;
    carpeta?: string; archivo?: string; subir?: string;
    archivos?: { nombre: string; ruta: string }[];
    /** el archivo, ya convertido (markdown) o como texto */
    html?: string; texto?: string;
    /** la ruta del archivo cuando no se muestra (un binario, uno grande): se ofrece bajarlo */
    descarga?: string;
    /** lo que hay que saber de lo que se muestra (que se cortó) */
    aviso?: string;
    /** un .html, para verlo dibujado: su ruta como la entiende `/api/archivos/ver` (con «máquina:» si es de otra) */
    ver?: string;
}

const ES_HTML = /\.html?$/i;

/** La máquina delante de una ruta («servidor:» en «servidor:docs/x.md»), como la entiende `/api/archivos`. */
const MAQUINA = /^[A-Za-z0-9][\w-]*:(?!\/\/)/;

/** El HTML de la carpeta y su archivo. Los enlaces a otro archivo (o a la carpeta de arriba) llevan su hilo y
 *  su ruta en `data-*`: los atiende `montar`, sin navegar. */
function html(d: Documento): string {
    const enlace = (ruta: string, texto: string, clase = '') =>
        `<a class="${clase}" data-hilo="${esc(d.hilo)}" data-archivo="${esc(ruta)}">${esc(texto)}</a>`;
    const cuerpo = d.error ? `<p class="nada">${esc(d.error)}</p>`
        : (d.archivos ? `<nav class="carpeta"><div class="donde">${esc(d.carpeta ?? '.')}</div>`
            + (d.subir !== undefined ? enlace(d.subir, '../', 'dir') : '')
            + d.archivos.map(a => enlace(a.ruta, a.nombre, `${a.nombre.endsWith('/') ? 'dir' : ''}${a.ruta === d.archivo ? ' sel' : ''}`)).join('')
            + `</nav>` : '')
            + (d.aviso ? `<p class="nada">${esc(d.aviso)}</p>` : '')
            + (d.archivo ? `<article><div class="donde">${esc(d.archivo)}${d.ver ? '<a class="alternar" title="ver el código del .html, o de vuelta dibujado">código</a>' : ''}</div>`
                + (d.ver ? `<iframe sandbox="allow-scripts allow-popups" src="/api/archivos/ver?ruta=${encodeURIComponent(d.ver)}" title="${esc(d.archivo)}"></iframe><pre hidden>${esc(d.texto ?? '')}</pre>`
                    : d.html ? `<div class="md">${d.html}</div>` : `<pre>${esc(d.texto ?? '')}</pre>`)
                + (d.descarga ? `<p><a href="/api/archivos/bajar?ruta=${encodeURIComponent(d.descarga)}" download>bajar ${esc(d.archivo.split('/').pop() ?? '')}</a></p>` : '')
                + '</article>' : '');
    return `<h1>${esc(d.titulo)}</h1>${cuerpo}`;
}

/** Lee la carpeta (de `hilo`) o el archivo y la dibuja en `el`; un clic en otro archivo la vuelve a leer ahí.
 *  `markdown`: cómo se convierte un .md a HTML. */
export async function montar(el: HTMLElement, hilo: string, archivo: string, markdown: (texto: string) => string): Promise<void> {
    el.classList.add('v-documento');
    el.dataset.hilo = hilo;
    el.dataset.archivo = archivo;
    if (!el.dataset.atendido) {
        el.dataset.atendido = '1';
        el.addEventListener('click', e => {
            const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
            if (!a) return;
            // un .html: dibujado o su código
            if (a.classList.contains('alternar')) {
                e.preventDefault();
                const marco = a.closest('article')?.querySelector('iframe'), codigo = a.closest('article')?.querySelector('pre');
                if (!marco || !codigo) return;
                const verCodigo = codigo.hidden;
                codigo.hidden = !verCodigo; marco.hidden = verCodigo;
                a.textContent = verCodigo ? 'dibujado' : 'código';
                return;
            }
            if (a.dataset.archivo !== undefined) {
                e.preventDefault();
                void montar(el, a.dataset.hilo ?? '', a.dataset.archivo, markdown);
                return;
            }
            // un enlace del documento: uno de afuera, en otra pestaña; uno relativo (otro archivo del repositorio),
            // aquí mismo, desde la carpeta del que se está leyendo
            const href = a.getAttribute('href') ?? '';
            if (!a.closest('.md') || !href || href.startsWith('#') || a.hasAttribute('download')) return;
            e.preventDefault();
            if (/^[a-z][a-z0-9+.-]*:/i.test(href)) { window.open(href, '_blank', 'noopener'); return; }
            const destino = decodeURIComponent(href.split('#')[0]);
            const actual = el.dataset.archivo ?? '';
            const base = actual.includes('/') ? actual.slice(0, actual.lastIndexOf('/')) : '';
            // en un documento de otra máquina, también lo absoluto es de allá
            const maquina = MAQUINA.exec(actual)?.[0] ?? '';
            void montar(el, el.dataset.hilo ?? '', destino.startsWith('/') ? maquina + destino : rutas.unir(base, destino), markdown);
        });
    }
    let d: Documento;
    if (!hilo && (MAQUINA.test(archivo) || archivo.startsWith('~'))) d = await leerSolo(archivo, markdown);
    else try {
        const r = await fetch(`/api/hilos/documento?hilo=${encodeURIComponent(hilo)}&archivo=${encodeURIComponent(archivo)}`, { cache: 'no-store' });
        const j = await r.json() as Documento & { markdown?: string; detail?: string };
        d = r.ok ? { ...j, html: j.markdown ? markdown(j.markdown) : undefined, subir: j.subir ?? undefined }
            : { hilo, titulo: hilo, error: typeof j.detail === 'string' ? j.detail : `la API respondió ${r.status}` };
    } catch (e) {
        d = { hilo, titulo: hilo, error: `la API no respondió: ${(e as Error).message}` };
    }
    // un .html que se pudo leer se ve dibujado. La ruta de uno de la carpeta de un hilo es relativa a ella, y
    // `/api/archivos/ver` la quiere desde la raíz o absoluta («no existe» es lo que dice la API de uno que no está)
    if (d.archivo && d.texto !== undefined && d.texto !== 'no existe' && !d.descarga && ES_HTML.test(d.archivo))
        d.ver = !hilo || MAQUINA.test(d.archivo) ? d.archivo : rutas.unir(modelo.porNombre(hilo)?.ruta ?? '', d.archivo);
    // desde dónde se resuelven los enlaces relativos del documento: el archivo que se muestra, como lo dice la API
    el.dataset.archivo = d.archivo ?? archivo;
    el.innerHTML = html(d);
    el.scrollTop = 0;
}

/** Un archivo solo, sin su carpeta: el de otra máquina («servidor:docs/x.md») o uno con `~`. */
async function leerSolo(archivo: string, markdown: (texto: string) => string): Promise<Documento> {
    try {
        const r = await fetch(`/api/archivos?ruta=${encodeURIComponent(archivo)}`, { cache: 'no-store' });
        const j = await r.json() as { ruta?: string; texto?: string; recortado?: boolean; maquina?: string; detail?: string };
        if (!r.ok) return { hilo: '', titulo: archivo, error: typeof j.detail === 'string' ? j.detail : `la API respondió ${r.status}` };
        const ruta = j.maquina ? `${j.maquina}:${j.ruta}` : j.ruta ?? archivo;
        const esMd = /\.(md|markdown)$/i.test(j.ruta ?? archivo);
        const nombre = (j.ruta ?? archivo).split('/').pop() ?? archivo;
        return { hilo: '', titulo: j.maquina ? `${nombre} · en ${j.maquina}` : nombre, archivo: ruta,
                 html: esMd ? markdown(j.texto ?? '') : undefined, texto: esMd ? undefined : j.texto ?? '',
                 aviso: j.recortado ? 'el archivo es más largo: se muestra hasta donde alcanza' : undefined };
    } catch (e) {
        return { hilo: '', titulo: archivo, error: `la API no respondió: ${(e as Error).message}` };
    }
}
