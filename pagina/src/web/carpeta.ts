// El visor de un documento: un archivo que la página puede leer, en una ventana encima de lo que se estaba mirando (la
// conversación, la lectura o la terminal de un hilo, el dashboard). Se abre con `abrir` (lo que la página llama `arch:<ruta>`
// y `doc:<hilo>`: navegador/app.ts), y se cierra con la ✕ de arriba a la derecha o con ⎋: queda todo como estaba, con el
// foco donde estaba. Es una ventana de verdad (`abrirVentana`, web/ventana.ts), como ⌘K o el menú ⋯; en el teléfono ocupa
// la pantalla entera.
//
// Lo que se ve: la primera fila es la barra de una pantalla (componentes/pantalla.ts), del alto de siempre, con el nombre
// del archivo en gris y, a la derecha, lo que se le puede hacer (el modo lectura, el código de un .html) y la ✕; abajo, el
// contenido, que se desplaza solo, y a su derecha la barra del documento (web/documento-lado.ts: sus comentarios, sus
// conexiones y, si es un .md con frontmatter, sus datos, cada uno en su pestaña, plegable). Un clic en un enlace a otro
// archivo lo abre aquí mismo; «‹», delante del nombre (o ⌫), vuelve al anterior. De qué está hecho:
//
// · Un archivo, de esta máquina o de otra («servidor:docs/x.md»: el backend se la pide por el bus, y sus enlaces siguen
//   allá), de un hilo (`/api/hilos/documento`, relativo a su carpeta) o de lo que la página puede leer (`arch:<ruta>`). Un
//   .md, dibujado (sin su frontmatter: va en la pestaña «datos» de la barra); un .html, en un iframe aislado
//   (`/api/archivos/ver`: sus scripts corren en un origen propio, sin la llave ni la API de la página), con su código a un clic («código» en la barra); el resto, como texto; un binario o uno
//   grande, para bajarlo.
// · Una carpeta (la de un proyecto, la de un hilo sin documento), como la lista de lo que tiene, uno por línea.
// · Varios que se llaman igual (una ruta que nombró un agente), para elegir uno.
// · Sus comentarios (web/comentarios.ts): en el texto, el tramo marcado apenas y su número; en la barra, la lista en el
//   orden del documento, con su estado y lo respondido. Se comenta seleccionando texto (la tecla c o el botón que
//   aparece). Un .md y un texto; un .html no.
// · El modo lectura (el modo revisión): un .md en la prosa (media/css/prosa.css, la misma de la lectura de un hilo), con
//   serifa, más grande y en una columna al medio de una ventana más grande; los comentarios, iguales, y la barra a la
//   derecha sin correr la columna si cabe. En el modo foco va de entrada; fuera de él, la letra de la página. Su ícono en
//   la barra (o la tecla l) lo pone y lo saca, y cada uno (foco, lo demás) recuerda lo último que se eligió en este
//   navegador.
// · Sus conexiones en el grafo de conocimiento (el módulo «grafo», si la máquina del archivo lo tiene: GRAFO.md en la
//   raíz): lo que sale y lo que llega, en su pestaña de la barra.
//
// Solo lee el archivo: lo único que escribe es el de sus comentarios, al lado. Sus estilos, en media/css/documento.css (con
// @scope, en `.v-documento`).

import { esc } from '../estilo';
import { modelo } from '../modelo';
import * as rutas from '../rutas';
import { barra as barraPantalla } from '../componentes/pantalla';
import { ofrecidosPara } from './candidatos';
import { Capa } from './comentarios';
import { Lado } from './documento-lado';
import * as frontmatter from './frontmatter';
import * as fuente from './fuente';
import { I } from './iconos';
import { abrirVentana } from './ventana';

/** La carpeta de un hilo y uno de sus archivos, como la da `/api/hilos/documento`. */
export interface Documento {
    hilo: string; titulo: string; error?: string;
    carpeta?: string; archivo?: string; subir?: string;
    archivos?: { nombre: string; ruta: string }[];
    /** el archivo, como lo da la API: su markdown (sin convertir) o su texto */
    markdown?: string; texto?: string;
    /** la ruta del archivo cuando no se muestra (un binario, uno grande): se ofrece bajarlo */
    descarga?: string;
    /** lo que hay que saber de lo que se muestra (que se cortó) */
    aviso?: string;
    /** un .html, para verlo dibujado: su ruta como la entiende `/api/archivos/ver` (con «máquina:» si es de otra) */
    ver?: string;
    maquina?: string;
}

/** Adónde vuelve la vista de un objeto (web/objeto.ts): cómo se nombra («Telar · conversación») y cómo se va. */
export interface Vuelta { nombre: string; ir: () => void }

const ES_HTML = /\.html?$/i;
/** La máquina delante de una ruta («servidor:» en «servidor:docs/x.md»), como la entiende `/api/archivos`. */
const MAQUINA = /^[A-Za-z0-9][\w-]*:(?!\/\/)/;

/** Cómo se nombra un documento en una línea: su archivo, sin la carpeta ni `.md`. */
const nombreDe = (ruta: string): string => (ruta.split('/').pop() ?? ruta).replace(/\.(md|markdown)$/i, '');

/** Lo que sabe cada visor dibujado: lo que muestra, por dónde pasó (para volver), cómo cerrarlo y sus comentarios. */
interface Estado {
    hilo: string; archivo: string;
    historial: { hilo: string; archivo: string }[];
    markdown: (texto: string) => string;
    cerrar?: () => void;
    capa?: Capa;
    /** la barra de la derecha (sus comentarios y sus conexiones): una por visor, que sigue de un archivo al otro */
    lado?: Lado;
    /** el número de la lectura que va: una que llega tarde (se pidió otro mientras) no se dibuja */
    n: number;
}
const estados = new WeakMap<HTMLElement, Estado>();

/** Una conexión del grafo (`/api/modulos/grafo/vecinos`): «origen —tipo→ destino», con dónde del destino (`locus`)
 *  y por qué. Las rutas `_abs` son de la máquina del documento. */
interface Arista {
    origen: string; tipo: string; destino: string; titulo_destino?: string; titulo_origen?: string;
    locus?: string; porque?: string; estado: 'ok' | 'roto' | 'externo'; origen_abs?: string; destino_abs?: string;
}

/** Las máquinas que no tienen el módulo «grafo» ('' esta): no se les vuelve a preguntar. */
const sinGrafo = new Set<string>();

// ── el modo lectura ───────────────────────────────────────────────────────────────────────────────────────────────

/** Si se lee en la prosa: lo elegido en este navegador para el modo puesto (foco, o lo demás); sin elegir, en foco sí. */
const enFoco = (): boolean => (globalThis.document?.body?.dataset.modo ?? '') === 'foco';
const llaveLectura = (): string => `telar.visor.lectura.${enFoco() ? 'foco' : 'otro'}`;
export function lecturaPuesta(): boolean {
    try {
        const v = globalThis.localStorage?.getItem(llaveLectura());
        if (v === 'si' || v === 'no') return v === 'si';
    } catch { /* sin almacén */ }
    return enFoco();
}
function recordarLectura(si: boolean): void {
    try { globalThis.localStorage?.setItem(llaveLectura(), si ? 'si' : 'no'); } catch { /* sin almacén */ }
}

/** Pone o saca el modo lectura en el visor que se ve: la prosa en el markdown, la ventana más grande, el ícono encendido. */
function ponerLectura(el: HTMLElement, si: boolean): void {
    el.classList.toggle('lectura', si);
    el.closest('dialog')?.classList.toggle('lectura', si);
    el.closest('.ventana')?.classList.toggle('lectura', si);
    el.querySelector('.md')?.classList.toggle('prosa', si);
    el.querySelector('.md')?.classList.toggle('prosa-md', si);
    el.querySelector('[data-accion="doc-lectura"]')?.classList.toggle('si', si);
}

// ── la ventana ────────────────────────────────────────────────────────────────────────────────────────────────────

/** Lo de adentro del visor: la primera fila; abajo, el contenido y la barra de la derecha. */
export const ESQUELETO = '<div class="v-documento"><div class="doc-barra"></div><div class="doc-medio">'
    + '<div class="doc-cuerpo" tabindex="-1"></div><aside class="doc-lado" hidden></aside></div></div>';

/** El visor abierto, si hay uno: se abre uno solo, y abrir otro archivo con él abierto lo muestra en el mismo. */
let abierto: { el: HTMLElement; cerrar: (devolverFoco: boolean) => void } | undefined;

/** Abre el archivo (`archivo`, de la carpeta de `hilo`, o sin hilo, uno que la página puede leer) en el visor: en una
 *  ventana nueva, o en la que ya está abierta (y «‹» vuelve al que se veía). `markdown`: cómo se convierte el markdown de
 *  lo que no es el documento (el porqué de una conexión). */
export function abrir(hilo: string, archivo: string, markdown: (texto: string) => string): void {
    if (abierto) { ir(abierto.el, hilo, archivo); return; }
    // lo que tenía el foco: vuelve ahí al cerrar (la terminal, la caja de escribir, una fila del dashboard)
    const antes = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    let devolver = true;
    // seleccionar arrastrando (para comentar) y soltar fuera de la ventana no es un clic fuera: no la cierra
    let desdeAdentro = false;
    void abrirVentana({ clase: 'ventana-documento', cuerpo: ESQUELETO }, {
        clase: 'ventana-documento',
        foco: '.doc-cuerpo',
        puedeCerrar: () => { const si = !desdeAdentro; desdeAdentro = false; return si; },
        montar: (d, cerrar) => {
            d.addEventListener('pointerdown', e => { desdeAdentro = !!(e.target as Element).closest?.('.ventana'); }, true);
            d.addEventListener('keydown', () => { desdeAdentro = false; }, true);
            const el = d.querySelector<HTMLElement>('.v-documento')!;
            abierto = { el, cerrar: f => { devolver = f; cerrar(undefined); } };
            void montar(el, hilo, archivo, markdown, { cerrar: () => cerrar(undefined) });
            return () => {
                estados.get(el)?.capa?.soltar();
                if (abierto?.el === el) abierto = undefined;
            };
        },
    }).then(() => { if (devolver && antes?.isConnected) antes.focus({ preventScroll: true }); });
}

/** Cierra el visor, si está abierto. `devolverFoco`: false cuando la página se va a otra parte (un hilo, el dashboard), que
 *  pone el foco donde corresponde. */
export function cerrar(devolverFoco = true): void { abierto?.cerrar(devolverFoco); }

/** Si el visor está abierto. */
export const estaAbierto = (): boolean => !!abierto;

// ── lo de adentro ─────────────────────────────────────────────────────────────────────────────────────────────────

/** Otro archivo, desde el que se muestra: se anota este para volver. */
function ir(el: HTMLElement, hilo: string, archivo: string): void {
    const st = estados.get(el);
    if (!st) return;
    st.historial.push({ hilo: st.hilo, archivo: st.archivo });
    void montar(el, hilo, archivo, st.markdown);
}

/** Al anterior; false si no hay. */
function atras(el: HTMLElement): boolean {
    const st = estados.get(el);
    const previo = st?.historial.pop();
    if (!st || !previo) return false;
    void montar(el, previo.hilo, previo.archivo, st.markdown);
    return true;
}

/** Dónde se dibuja: la barra y el cuerpo del visor (o el visor entero, si no los tiene: una prueba). */
function partes(el: HTMLElement): { barra?: HTMLElement; cuerpo?: HTMLElement } {
    return { barra: el.querySelector?.<HTMLElement>('.doc-barra') ?? undefined, cuerpo: el.querySelector?.<HTMLElement>('.doc-cuerpo') ?? undefined };
}

function poner(el: HTMLElement, barra: string, cuerpo: string): void {
    const p = partes(el);
    if (p.barra && p.cuerpo) {
        p.barra.innerHTML = barra;
        p.cuerpo.innerHTML = cuerpo;
        p.cuerpo.scrollTop = 0;
    } else {
        el.innerHTML = barra + `<div class="doc-cuerpo">${cuerpo}</div>`;
    }
}

/** La primera fila: «‹» si hay a qué volver, el nombre del archivo (gris, con su ruta entera al pasar el mouse) y, a la
 *  derecha, lo que se le hace y la ✕. */
function barra(nombre: string, ruta: string, previo: { hilo: string; archivo: string } | undefined, o: { html?: boolean; md?: boolean } = {}): string {
    const volver = previo ? { accion: 'doc-atras', icono: I.atras, ayuda: `volver a ${nombreDe(previo.archivo) || previo.hilo || 'lo anterior'} (⌫)` } : undefined;
    return barraPantalla({
        volver,
        resumenHtml: `<span class="doc-nombre" title="${esc(ruta || nombre)}">${esc(nombre)}</span>`,
        acciones: [
            ...(o.html ? [{ accion: 'doc-codigo', texto: 'código', ayuda: 'ver el código del .html, o de vuelta dibujado' }] : []),
            ...(o.md ? [{ accion: 'doc-lectura', icono: I.lectura, tono: 'violeta', si: lecturaPuesta(),
                ayuda: 'leer cómodo (l): la letra y el ancho de la lectura de un hilo, en una columna al medio; de entrada en el modo foco' }] : []),
            { accion: 'doc-cerrar', icono: I.cerrar, ayuda: 'cerrar (⎋)' },
        ],
    });
}

/** Cómo se nombra lo que se muestra en la primera fila: el archivo (de otra máquina, con ella delante), o la carpeta. */
function nombreVisible(ruta: string): string {
    const maquina = MAQUINA.exec(ruta)?.[0] ?? '', sin = ruta.slice(maquina.length).replace(/\/$/, '');
    return maquina + (sin.split('/').pop() || sin || '.');
}

/** El HTML de los candidatos a una ruta: cada uno con su carpeta tenue y su nombre, en una columna. */
function htmlCandidatos(ruta: string, { candidatos, mas }: { candidatos: string[]; mas: boolean }): string {
    const filas = candidatos.map(c => {
        const sin = c.slice((MAQUINA.exec(c)?.[0] ?? '').length), i = sin.lastIndexOf('/');
        return `<a data-hilo="" data-archivo="${esc(c)}" title="${esc(c)}"><span class="dir">${esc(sin.slice(0, i + 1))}</span>${esc(sin.slice(i + 1))}</a>`;
    }).join('');
    return `<nav class="candidatos"><p class="nada">hay ${candidatos.length}${mas ? ' o más' : ''}`
        + ` archivos que se llaman así, los más cercanos primero. ¿Cuál?</p>${filas}</nav>`;
}

/** El contenido: el archivo (o la carpeta, o el error). Los enlaces a otro archivo (o a la carpeta de arriba) llevan su
 *  hilo y su ruta en `data-*`: los atiende el visor, sin navegar. */
function contenido(d: Documento): string {
    const enlace = (ruta: string, texto: string, clase = '') =>
        `<a class="${clase}" data-hilo="${esc(d.hilo)}" data-archivo="${esc(ruta)}">${esc(texto)}</a>`;
    if (d.error) return `<p class="nada">${esc(d.error)}</p>`;
    const aviso = d.aviso ? `<p class="nada">${esc(d.aviso)}</p>` : '';
    if (!d.archivo) {
        // una carpeta: lo que tiene, uno por línea (las carpetas primero, y la de arriba)
        return aviso + `<nav class="carpeta">${d.subir !== undefined ? enlace(d.subir, '../', 'dir') : ''}`
            + (d.archivos ?? []).map(a => enlace(a.ruta, a.nombre, a.nombre.endsWith('/') ? 'dir' : '')).join('')
            + (d.archivos?.length ? '' : '<p class="nada">vacía</p>') + '</nav>';
    }
    const archivo = d.ver ? `<iframe sandbox="allow-scripts allow-popups" src="/api/archivos/ver?ruta=${encodeURIComponent(d.ver)}" title="${esc(d.archivo)}"></iframe><pre class="doc-texto" hidden>${esc(d.texto ?? '')}</pre>`
        : d.markdown !== undefined && d.markdown !== '' ? `<div class="md doc-contenido${lecturaPuesta() ? ' prosa prosa-md' : ''}">${fuente.dibujar(d.markdown)}</div>`
        : `<pre class="doc-texto doc-contenido" data-src="0-${(d.texto ?? '').split('\n').length}">${esc(d.texto ?? '')}</pre>`;
    return aviso + `<article${d.ver ? ' class="con-iframe"' : ''}>${archivo}`
        + (d.descarga ? `<p><a href="/api/archivos/bajar?ruta=${encodeURIComponent(d.descarga)}" download>bajar ${esc(d.archivo.split('/').pop() ?? '')}</a></p>` : '')
        + '</article>';
}

/** Lee el archivo (o la carpeta) y lo dibuja en el visor `el`. Sin `o`, sigue en el que estaba (un clic adentro); con él,
 *  empieza de nuevo (sin a qué volver), y `o.cerrar` es la ✕. */
export async function montar(el: HTMLElement, hilo: string, archivo: string, markdown: (texto: string) => string,
    o?: { cerrar?: () => void }): Promise<void> {
    el.classList.add('v-documento');
    let st = estados.get(el);
    if (!st || o) {
        st?.capa?.soltar();
        st = { hilo, archivo, historial: [], markdown, cerrar: o?.cerrar, n: 0, lado: st?.lado };
        estados.set(el, st);
    }
    const aside = el.querySelector?.<HTMLElement>('aside.doc-lado');
    if (aside && !st.lado) st.lado = new Lado(aside, entornoLado(), el);
    st.capa?.soltar();
    st.capa = undefined;
    st.hilo = hilo; st.archivo = archivo;
    const n = ++st.n;
    if (!el.dataset.atendido) atender(el);
    el.dataset.hilo = hilo;
    el.dataset.archivo = archivo;
    delete el.dataset.listo;
    const previo = st.historial.at(-1);
    // una ruta que nombró un agente y tiene varios candidatos: se elige uno, sin pedir nada
    const ofrecido = !hilo ? ofrecidosPara(archivo) : undefined;
    if (ofrecido) {
        st.lado?.ocultar();
        poner(el, barra(nombreVisible(archivo), archivo, previo), htmlCandidatos(archivo, ofrecido));
        el.dataset.listo = '1';
        return;
    }
    if (partes(el).cuerpo) poner(el, barra(nombreVisible(archivo || hilo), archivo, previo), '<p class="nada">leyendo…</p>');
    let d: Documento;
    try {
        const r = await fetch(`/api/hilos/documento?hilo=${encodeURIComponent(hilo)}&archivo=${encodeURIComponent(archivo)}`, { cache: 'no-store' });
        const j = await r.json() as Documento & { detail?: string };
        d = r.ok ? { ...j, subir: j.subir ?? undefined } : { hilo, titulo: hilo, error: typeof j.detail === 'string' ? j.detail : `la API respondió ${r.status}` };
    } catch (e) {
        d = { hilo, titulo: hilo, error: `la API no respondió: ${(e as Error).message}` };
    }
    if (st.n !== n) return;
    // la ruta del archivo desde la raíz, o entera (con `~`, o con «máquina:» si es de otra), que es como la quieren
    // `/api/archivos/ver`, los comentarios y el grafo: la de uno de la carpeta de un hilo (`doc:`) es relativa a ella. «no
    // existe» es lo que dice la API de uno que no está
    const existe = !!d.archivo && !d.error && d.texto !== 'no existe';
    const enRaiz = !d.archivo ? '' : !hilo || MAQUINA.test(d.archivo) ? d.archivo : rutas.unir(modelo.porNombre(hilo)?.ruta ?? '', d.archivo);
    // un .html que se pudo leer se ve dibujado
    if (existe && d.texto !== undefined && !d.descarga && ES_HTML.test(d.archivo ?? '')) d.ver = enRaiz;
    // desde dónde se resuelven los enlaces relativos del documento: el archivo que se muestra, como lo dice la API
    st.archivo = d.archivo || d.carpeta || archivo;
    el.dataset.archivo = st.archivo;
    const visible = d.archivo ? nombreVisible(d.archivo) : `${nombreVisible(d.carpeta && d.carpeta !== '.' ? d.carpeta : d.titulo || archivo)}/`;
    const esMd = !!d.markdown && !d.error;
    poner(el, barra(visible, d.archivo || d.carpeta || archivo, previo, { html: !!d.ver, md: esMd }), contenido(d));
    if (partes(el).cuerpo) ponerLectura(el, esMd && lecturaPuesta());
    // la barra de la derecha: con un archivo que se ve; no con una carpeta ni un error
    const lado = st.lado;
    if (lado && existe) lado.empezar(); else lado?.ocultar();
    if (lado && existe && esMd) datos(lado, d.markdown!);
    el.dataset.listo = '1';
    // sus comentarios: un .md o un texto que se muestra entero
    const cont = partes(el).cuerpo?.querySelector<HTMLElement>('.doc-contenido');
    if (lado && existe && cont && !d.descarga && !d.ver) {
        const texto = d.markdown || d.texto || '';
        st.capa = new Capa({ visor: el, cuerpo: partes(el).cuerpo!, contenido: cont, ruta: enRaiz, fuente: texto, md: !!d.markdown,
            lista: lado.lugar('comentarios'), markdown, lado: {
                mostrar: () => lado.mostrar('comentarios'),
                cuenta: c => lado.cuenta('comentarios', c),
                decidir: abiertos => lado.decidir(abiertos),
            } });
        void st.capa.cargar();
    } else if (lado && existe) {
        lado.lugar('comentarios').innerHTML = `<p class="nada">${d.ver ? 'un .html dibujado no se comenta: el texto que se ve no es el del archivo'
            : 'este archivo no se muestra entero: no se comenta'}</p>`;
        lado.decidir(0);
    }
    if (existe) void conexiones(el, enRaiz, markdown, n);
}

/** Los datos del frontmatter de un .md (web/frontmatter.ts), en su hoja de la barra: cada clave con su valor, como está
 *  escrito. Sin frontmatter, la hoja no aparece. */
function datos(lado: Lado, texto: string): void {
    const fm = frontmatter.leer(texto);
    lado.tener('datos', !!fm);
    if (!fm) return;
    lado.lugar('datos').innerHTML = !fm.datos.length ? `<p class="nada">el frontmatter (${fm.formato.toUpperCase()}) no tiene datos</p>`
        : `<dl class="doc-datos" data-formato="${fm.formato}">${fm.datos.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
    lado.cuenta('datos', { n: fm.datos.length, ayuda: `los datos del frontmatter (${fm.formato.toUpperCase()}): ${fm.datos.length}` });
}

/** Lo de la página que usa la barra de la derecha. */
function entornoLado(): ConstructorParameters<typeof Lado>[1] {
    let almacen: Storage | null = null;
    try { almacen = globalThis.localStorage ?? null; } catch { almacen = null; }
    return { body: document.body, almacen,
        pantalla: () => ({ width: window.screen?.width ?? window.innerWidth, height: window.screen?.height ?? window.innerHeight }) };
}

/** Los clics y las teclas del visor: una vez por elemento. */
function atender(el: HTMLElement): void {
    el.dataset.atendido = '1';
    el.addEventListener('keydown', e => {
        const st = estados.get(el);
        if (e.key === 'Escape' && st?.capa?.cerrarTarjeta()) { e.preventDefault(); e.stopPropagation(); return; }
        if (e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;
        const t = e.target as HTMLElement;
        if (t.closest('input, textarea, select, [contenteditable]')) return;
        if (e.key === 'Backspace' && atras(el)) { e.preventDefault(); return; }
        if ((e.key === 'l' || e.key === 'L') && el.querySelector('[data-accion="doc-lectura"]')) { e.preventDefault(); alternarLectura(el); return; }
        if ((e.key === 'c' || e.key === 'C') && st?.capa?.comentarSeleccion()) e.preventDefault();
    });
    el.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLElement>('a, [data-accion]');
        if (!a || !el.contains(a)) return;
        const st = estados.get(el);
        // lo de la barra (y lo de los comentarios, que lo atiende su capa): nunca sigue a la ventana, que se cerraría
        const accion = a.dataset.accion;
        if (accion) {
            e.preventDefault();
            if (accion === 'doc-cerrar') st?.cerrar?.();
            else if (accion === 'doc-atras') atras(el);
            else if (accion === 'doc-codigo') alternarCodigo(el, a);
            else if (accion === 'doc-lectura') alternarLectura(el);
            return;
        }
        // una conexión: el otro documento, aquí (con su máquina delante si es de otra)
        if (a.dataset.conexion) { e.preventDefault(); ir(el, '', a.dataset.conexion); return; }
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
                ir(el, '', maquina + (dest.startsWith('/') ? dest : rutas.unir(sin.slice(0, sin.lastIndexOf('/')), dest)));
            }
            return;
        }
        if (a.dataset.archivo !== undefined) {
            e.preventDefault();
            ir(el, a.dataset.hilo ?? '', a.dataset.archivo);
            return;
        }
        // un enlace del documento (o de un comentario): uno de afuera, en otra pestaña; uno relativo (otro archivo del
        // repositorio), aquí mismo, desde la carpeta del que se está leyendo
        const href = a.getAttribute('href') ?? '';
        if (!a.closest('.md, .coment-cuerpo') || !href || a.hasAttribute('download')) return;
        e.preventDefault();
        if (href.startsWith('#')) return;
        if (/^[a-z][a-z0-9+.-]*:/i.test(href)) { window.open(href, '_blank', 'noopener'); return; }
        const destino = decodeURIComponent(href.split('#')[0]);
        // en un documento de otra máquina, lo relativo y lo absoluto también son de allá
        const actual = el.dataset.archivo ?? '';
        const maquina = MAQUINA.exec(actual)?.[0] ?? '', sin = actual.slice(maquina.length);
        const base = sin.includes('/') ? sin.slice(0, sin.lastIndexOf('/')) : '';
        ir(el, el.dataset.hilo ?? '', maquina + (destino.startsWith('/') ? destino : rutas.unir(base, destino)));
    });
}

/** El modo lectura, al revés de como está; se recuerda para el modo puesto. La selección y las marcas no cambian: es la
 *  misma página con otra letra. */
function alternarLectura(el: HTMLElement): void {
    const si = !el.classList.contains('lectura');
    recordarLectura(si);
    ponerLectura(el, si);
}

/** Un .html: dibujado o su código. */
function alternarCodigo(el: HTMLElement, a: HTMLElement): void {
    const marco = el.querySelector<HTMLIFrameElement>('article iframe'), codigo = el.querySelector<HTMLElement>('article pre');
    if (!marco || !codigo) return;
    const verCodigo = codigo.hidden;
    codigo.hidden = !verCodigo; marco.hidden = verCodigo;
    el.querySelector('article')?.classList.toggle('con-iframe', !verCodigo);
    const txt = a.querySelector('.txt');
    if (txt) txt.textContent = verCodigo ? 'dibujado' : 'código';
}

/** Pide al grafo las conexiones del archivo que muestra `el` (`ruta`, desde la raíz o absoluta, con «máquina:» si es
 *  de otra) y las pone en su pestaña de la barra, con su cuenta. Llegan después del archivo (el grafo lee el repositorio
 *  entero, y tarda): si para entonces el visor ya muestra otro, no se ponen. Sin el módulo, o sin conexiones, la hoja lo
 *  dice y la pestaña no cuenta. */
async function conexiones(el: HTMLElement, ruta: string, markdown: (texto: string) => string, n: number): Promise<void> {
    const maquina = MAQUINA.exec(ruta)?.[0].slice(0, -1) ?? '';
    const lado = estados.get(el)?.lado;
    const vigente = () => estados.get(el)?.n === n;
    const decir = (texto: string) => { if (lado && vigente()) { lado.lugar('conexiones').innerHTML = `<p class="nada">${esc(texto)}</p>`; lado.cuenta('conexiones', { n: null }); } };
    const SIN = `${maquina ? `${maquina} no tiene` : 'esta máquina no tiene'} el grafo de conocimiento (el módulo «grafo»)`;
    if (sinGrafo.has(maquina)) { decir(SIN); return; }
    let r: Response;
    try {
        r = await fetch(`/api/modulos/grafo/vecinos?ruta=${encodeURIComponent(ruta.slice(maquina ? maquina.length + 1 : 0))}`
            + (maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''), { cache: 'no-store' });
    } catch (e) { decir(`el grafo no respondió: ${(e as Error).message}`); return; }
    if (r.status === 404) { sinGrafo.add(maquina); decir(SIN); return; }
    if (!vigente() || !lado) return;
    const lugar = lado.lugar('conexiones');
    if (!r.ok) { decir(`el grafo no pudo leer las conexiones (${r.status})`); return; }
    const v = await r.json() as { nodo?: { titulo?: string }; salientes?: Arista[]; entrantes?: Arista[] };
    const salen = v.salientes ?? [], llegan = v.entrantes ?? [];
    if (!vigente()) return;
    if (!salen.length && !llegan.length) { decir('ninguna conexión en el grafo: nada sale de este documento ni llega a él'); lado.cuenta('conexiones', { n: 0 }); return; }
    const en = (abs: string) => (maquina ? `${maquina}:${abs}` : abs);
    // el nombre que el otro le da a este documento, si dice algo más que su título o su archivo («mapa — el Fork»)
    const llano = (t: string) => t.toLowerCase().normalize('NFD').replace(/[^\p{L}\p{N}]/gu, '');
    const propios = new Set([llano(v.nodo?.titulo ?? ''), llano(nombreDe(ruta))]);
    // las de un lado, una entrada por documento (el otro), con sus aristas debajo
    const grupo = (titulo: string, aristas: Arista[], sale: boolean): string => {
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
    lugar.innerHTML = `<div class="conexiones">${grupo('salen →', salen, true)}${grupo('llegan ←', llegan, false)}</div>`;
    const total = salen.length + llegan.length;
    lado.cuenta('conexiones', { n: total, ayuda: `conexiones en el grafo: ${salen.length} salen, ${llegan.length} llegan` });
}
