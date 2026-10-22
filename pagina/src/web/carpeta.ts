// La carpeta de un hilo y uno de sus archivos (`/api/hilos/documento`), o un archivo cualquiera del repositorio
// (`arch:<ruta>`): la lista de archivos arriba, y el elegido abajo. Una ruta de otra máquina («servidor:docs/x.md»)
// o con `~` se lee sola, sin su carpeta (`/api/archivos`, que se la pide a esa máquina por el bus). Un .html se ve
// dibujado, en un iframe aislado (`/api/archivos/ver`: sus scripts corren en un origen propio, sin la llave ni la
// API de la página), con su código a un clic. Al lado del archivo, sus conexiones en el grafo de conocimiento (el
// módulo «grafo», si la máquina del archivo lo tiene: GRAFO.md en la raíz). Todo va en un recuadro, y arriba «‹ …»
// vuelve al documento anterior, y del primero a la vista de donde se vino (la conversación, la lectura o la terminal
// de un hilo, el dashboard), como en la ficha de una tarea. Solo lee. Se dibuja en un elemento de la página; sus
// estilos, en media/css/documento.css (con @scope, en `.v-documento`).

import { esc, recuadro, volver } from '../estilo';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import { teclaParaLaVista } from './vistas-hilo';

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

/** Adónde vuelve el visor: cómo se nombra («Telar · conversación») y cómo se va. */
export interface Vuelta { nombre: string; ir: () => void }

/** La vuelta de cada visor dibujado: la pone `montar` cuando la página lo muestra, y un archivo abierto desde otro
 *  (un clic adentro) se queda con la que había. */
const vueltas = new WeakMap<HTMLElement, Vuelta | null>();

/** Los documentos por los que se pasó en cada visor desde que la página lo mostró: «‹ …» vuelve al último antes que
 *  a la vista de donde se vino. */
const historiales = new WeakMap<HTMLElement, { hilo: string; archivo: string }[]>();

/** Una conexión del grafo (`/api/modulos/grafo/vecinos`): «origen —tipo→ destino», con dónde del destino (`locus`)
 *  y por qué. Las rutas `_abs` son de la máquina del documento. */
interface Arista {
    origen: string; tipo: string; destino: string; titulo_destino?: string; titulo_origen?: string;
    locus?: string; porque?: string; estado: 'ok' | 'roto' | 'externo'; origen_abs?: string; destino_abs?: string;
}

/** Las máquinas que no tienen el módulo «grafo» ('' esta): no se les vuelve a preguntar. */
const sinGrafo = new Set<string>();

/** La máquina delante de una ruta («servidor:» en «servidor:docs/x.md»), como la entiende `/api/archivos`. */
const MAQUINA = /^[A-Za-z0-9][\w-]*:(?!\/\/)/;

/** Cómo se nombra un documento en una línea: su archivo, sin la carpeta ni `.md`. */
const nombreDe = (ruta: string): string => (ruta.split('/').pop() ?? ruta).replace(/\.(md|markdown)$/i, '');

/** El HTML de la carpeta y su archivo, en un recuadro con la vuelta arriba (`atras`: adónde lleva). Los enlaces a
 *  otro archivo (o a la carpeta de arriba) llevan su hilo y su ruta en `data-*`: los atiende `montar`, sin navegar.
 *  Al lado del archivo, el lugar de sus conexiones, que llegan después (`conexiones`). */
function html(d: Documento, atras: string | null): string {
    const enlace = (ruta: string, texto: string, clase = '') =>
        `<a class="${clase}" data-hilo="${esc(d.hilo)}" data-archivo="${esc(ruta)}">${esc(texto)}</a>`;
    const cuerpo = d.error ? `<p class="nada">${esc(d.error)}</p>`
        : (d.archivos ? `<nav class="carpeta"><div class="donde">${esc(d.carpeta ?? '.')}</div>`
            + (d.subir !== undefined ? enlace(d.subir, '../', 'dir') : '')
            + d.archivos.map(a => enlace(a.ruta, a.nombre, `${a.nombre.endsWith('/') ? 'dir' : ''}${a.ruta === d.archivo ? ' sel' : ''}`)).join('')
            + `</nav>` : '')
            + (d.aviso ? `<p class="nada">${esc(d.aviso)}</p>` : '')
            + (d.archivo ? `<div class="cuerpo"><article><div class="donde">${esc(d.archivo)}${d.ver ? '<a class="alternar" title="ver el código del .html, o de vuelta dibujado">código</a>' : ''}</div>`
                + (d.ver ? `<iframe sandbox="allow-scripts allow-popups" src="/api/archivos/ver?ruta=${encodeURIComponent(d.ver)}" title="${esc(d.archivo)}"></iframe><pre hidden>${esc(d.texto ?? '')}</pre>`
                    : d.html ? `<div class="md">${d.html}</div>` : `<pre>${esc(d.texto ?? '')}</pre>`)
                + (d.descarga ? `<p><a href="/api/archivos/bajar?ruta=${encodeURIComponent(d.descarga)}" download>bajar ${esc(d.archivo.split('/').pop() ?? '')}</a></p>` : '')
                + '</article><aside class="conexiones" hidden></aside></div>' : '');
    return (atras ? volver('volver-doc', atras, '', `volver a ${atras} (⎋)`) : '')
        + recuadro(`<h1>${esc(d.titulo)}</h1>${cuerpo}`);
}

/** Lee la carpeta (de `hilo`) o el archivo y la dibuja en `el`; un clic en otro archivo la vuelve a leer ahí.
 *  `markdown`: cómo se convierte un .md a HTML. `vuelta`: adónde lleva «‹ …» (y ⎋); null, a ninguna parte (no se
 *  vino de una vista); sin ella, la que ya tenía. */
export async function montar(el: HTMLElement, hilo: string, archivo: string, markdown: (texto: string) => string,
    vuelta?: Vuelta | null): Promise<void> {
    el.classList.add('v-documento');
    el.dataset.hilo = hilo;
    el.dataset.archivo = archivo;
    if (vuelta !== undefined) { vueltas.set(el, vuelta); historiales.set(el, []); }
    // otro archivo, desde este: se anota este para volver
    const ir = (h: string, a: string) => {
        historiales.get(el)?.push({ hilo: el.dataset.hilo ?? '', archivo: el.dataset.archivo ?? '' });
        void montar(el, h, a, markdown);
    };
    if (!el.dataset.atendido) {
        el.dataset.atendido = '1';
        // al documento anterior, o si no hay, a la vista de donde se vino
        const atras = (): boolean => {
            const previo = historiales.get(el)?.pop();
            if (previo) { void montar(el, previo.hilo, previo.archivo, markdown); return true; }
            const v = vueltas.get(el);
            v?.ir();
            return !!v;
        };
        window.addEventListener('keydown', e => {
            if (e.key !== 'Escape' || !teclaParaLaVista(e, el)) return;
            if (atras()) e.preventDefault();
        });
        el.addEventListener('click', e => {
            const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
            if (!a) return;
            if (a.dataset.accion === 'volver-doc') { e.preventDefault(); atras(); return; }
            // una conexión: el otro documento, aquí (con su máquina delante si es de otra)
            if (a.dataset.conexion) { e.preventDefault(); ir('', a.dataset.conexion); return; }
            // un enlace en el porqué de una conexión: uno de afuera, en otra pestaña; uno relativo, desde el
            // documento donde está escrita la conexión (su origen)
            const origen = a.closest<HTMLElement>('.porque')?.dataset.base;
            if (origen !== undefined) {
                const href = a.getAttribute('href') ?? '';
                e.preventDefault();
                if (/^https?:\/\//i.test(href)) window.open(href, '_blank', 'noopener,noreferrer');
                else if (href && !href.startsWith('#') && !/^[a-z][a-z0-9+.-]*:/i.test(href)) {
                    const maquina = MAQUINA.exec(origen)?.[0] ?? '', sin = origen.slice(maquina.length);
                    const dest = decodeURIComponent(href.split('#')[0]);
                    ir('', maquina + (dest.startsWith('/') ? dest : rutas.unir(sin.slice(0, sin.lastIndexOf('/')), dest)));
                }
                return;
            }
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
                ir(a.dataset.hilo ?? '', a.dataset.archivo);
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
            ir(el.dataset.hilo ?? '', destino.startsWith('/') ? maquina + destino : rutas.unir(base, destino));
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
    // la ruta del archivo desde la raíz, o absoluta (con «máquina:» si es de otra), que es como la quieren
    // `/api/archivos/ver` y el grafo: la de uno de la carpeta de un hilo es relativa a ella. «no existe» es lo que
    // dice la API de uno que no está
    const existe = !!d.archivo && !d.error && d.texto !== 'no existe';
    const enRaiz = !d.archivo ? '' : !hilo || MAQUINA.test(d.archivo) ? d.archivo : rutas.unir(modelo.porNombre(hilo)?.ruta ?? '', d.archivo);
    // un .html que se pudo leer se ve dibujado
    if (existe && d.texto !== undefined && !d.descarga && ES_HTML.test(d.archivo ?? '')) d.ver = enRaiz;
    // desde dónde se resuelven los enlaces relativos del documento: el archivo que se muestra, como lo dice la API
    el.dataset.archivo = d.archivo ?? archivo;
    const previo = historiales.get(el)?.at(-1);
    el.innerHTML = html(d, previo ? nombreDe(previo.archivo) || previo.hilo : vueltas.get(el)?.nombre ?? null);
    el.scrollTop = 0;
    if (existe) void conexiones(el, enRaiz, markdown);
}

/** Pide al grafo las conexiones del archivo que muestra `el` (`ruta`, desde la raíz o absoluta, con «máquina:» si es
 *  de otra) y las pone a su lado. Llegan después del archivo (el grafo lee el repositorio entero, y tarda): si para
 *  entonces el visor ya muestra otro, no se ponen. Sin el módulo, o sin conexiones, no aparece nada. */
async function conexiones(el: HTMLElement, ruta: string, markdown: (texto: string) => string): Promise<void> {
    const maquina = MAQUINA.exec(ruta)?.[0].slice(0, -1) ?? '';
    if (sinGrafo.has(maquina)) return;
    const mostrado = el.dataset.archivo;
    let r: Response;
    try {
        r = await fetch(`/api/modulos/grafo/vecinos?ruta=${encodeURIComponent(ruta.slice(maquina ? maquina.length + 1 : 0))}`
            + (maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''), { cache: 'no-store' });
    } catch { return; }
    if (r.status === 404) { sinGrafo.add(maquina); return; }
    const aside = el.querySelector<HTMLElement>('aside.conexiones');
    if (el.dataset.archivo !== mostrado || !aside) return;
    if (!r.ok) { aside.innerHTML = `<p class="nada">el grafo no pudo leer las conexiones (${r.status})</p>`; aside.hidden = false; return; }
    const v = await r.json() as { nodo?: { titulo?: string }; salientes?: Arista[]; entrantes?: Arista[] };
    const salen = v.salientes ?? [], llegan = v.entrantes ?? [];
    if (el.dataset.archivo !== mostrado || (!salen.length && !llegan.length)) return;
    const en = (abs: string) => (maquina ? `${maquina}:${abs}` : abs);
    // el nombre que el otro le da a este documento, si dice algo más que su título o su archivo («mapa — el Fork»)
    const llano = (t: string) => t.toLowerCase().normalize('NFD').replace(/[^\p{L}\p{N}]/gu, '');
    const propios = new Set([llano(v.nodo?.titulo ?? ''), llano(nombreDe(ruta))]);
    // las de un lado, una entrada por documento (el otro), con sus aristas debajo
    const lado = (titulo: string, aristas: Arista[], sale: boolean): string => {
        if (!aristas.length) return '';
        const grupos = new Map<string, Arista[]>();
        for (const a of aristas) {
            const k = sale ? a.destino_abs ?? a.destino : a.origen_abs ?? a.origen;
            grupos.set(k, [...grupos.get(k) ?? [], a]);
        }
        const items = [...grupos].map(([abs, as]) => {
            const a = as[0], ruta = sale ? a.destino : a.origen;
            const nombre = (sale ? a.titulo_destino : a.titulo_origen) || nombreDe(ruta);
            const doc = sale && a.estado === 'roto' ? `<span class="roto" title="${esc(ruta)}: no existe">${esc(nombre)}</span>`
                : /^https?:\/\//i.test(ruta) ? `<a href="${esc(ruta)}" target="_blank" rel="noopener noreferrer">${esc(nombre)}</a>`
                : `<a data-conexion="${esc(en(abs))}" title="${esc(ruta)}">${esc(nombre)}</a>`;
            const aristasHtml = as.map(x => {
                // dónde del destino: en las que llegan, de este documento, con el nombre que le da el otro
                const aqui = !sale && x.titulo_destino && !propios.has(llano(x.titulo_destino)) ? x.titulo_destino : '';
                const donde = [x.locus, aqui].filter(Boolean).join(' · ');
                return `<div class="arista"><code>${esc(x.tipo)}</code>${donde ? ` <span class="locus">${esc(donde)}</span>` : ''}`
                    + (x.porque ? `<div class="porque" data-base="${esc(en(x.origen_abs ?? x.origen))}">${markdown(x.porque)}</div>` : '')
                    + '</div>';
            }).join('');
            return `<li>${doc}${aristasHtml}</li>`;
        }).join('');
        return `<h3>${titulo} <span class="n">${aristas.length}</span></h3><ul>${items}</ul>`;
    };
    aside.innerHTML = '<h2>conexiones</h2>' + lado('salen →', salen, true) + lado('llegan ←', llegan, false);
    aside.hidden = false;
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
