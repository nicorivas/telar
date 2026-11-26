// Los componentes de telar en el lienzo de un módulo: las pestañas, el buscador y los filtros de la página, para que la
// pestaña de un módulo (un iframe aislado y sin red: docs/contratos.md, «telar seccion») se vea y se maneje como las de
// telar sin copiarlos. Es el mismo código de la página (componentes/*.ts arman el HTML, web/pestanas-fila.ts y
// web/buscadores.ts lo hacen andar), empaquetado aparte (scripts/navegador.mjs → src/telar/web/lienzo-componentes.js) y
// con sus estilos (→ lienzo-componentes.css). Un lienzo que declara `"componentes": true` los recibe en línea, antes de su
// propio HTML (vistas/dashboard/pagina.ts), con los tokens del tema que se ve; y los usa así:
//
//   const C = window.lienzo.componentes;            // undefined en un telar sin esto: el lienzo dibuja lo suyo
//   cabecera.innerHTML = C.pestanas({ nombre: 'vistas', accion: 'vista', activa: 'backlog', pestanas: [...] })
//       + C.barraBuscar({ placeholder: 'ideas', herramientas: C.filtros({ grupos: [...] }) });
//
// Lo que arman es HTML (las mismas props que en la página: componentes/pestanas.ts, buscador.ts, filtros.ts). Lo que
// hacen solos, sin que el lienzo lo repita: las pestañas que no caben van al «⋯» al dibujarse y al cambiar el ancho, con
// su teclado (← → Inicio Fin ⏎); el ✕ del buscador lo borra (y avisa con un `input`); el «⋯» y un grupo de filtros
// plegado abren el menú de la casa, que se le pide a la página (`window.lienzo.pedir("opciones")`). Lo demás (qué abre una
// pestaña, qué filtra un filtro, qué busca el buscador) es del lienzo: le llegan los clics con `data-accion` y `data-valor`
// (una pestaña) o `data-id` (`grupo:clave`, un filtro), como en la página.
//
// Y la prosa (media/css/prosa.css, la de la lectura de un hilo y el visor en modo lectura): `await C.prosa(markdown,
// {ruta})` da el HTML de un documento, dibujado por la página como en el visor (`window.lienzo.pedir("prosa")`: el
// markdown-it de la página, que así no va en cada lienzo), dentro de un `.prosa.prosa-md`. Sus enlaces andan solos: uno
// relativo abre ese archivo en el visor de la página, desde la carpeta de `ruta` (una carpeta, su README); uno a un título
// de la misma página (`#…`) baja hasta él; uno de afuera no se sigue (el lienzo no tiene red) y dice adónde va.

import { pestanas, pestana } from '../componentes/pestanas';
import { buscador, barraBuscar } from '../componentes/buscador';
import { filtros, marcarFiltros, contarFiltro, leerGrupo } from '../componentes/filtros';
import { I } from '../web/iconos';
import { acomodar, acomodarTodas, atender as atenderPestanas, marcar, usarMenu } from '../web/pestanas-fila';
import { atender as atenderBuscadores } from '../web/buscadores';
import { unir } from '../rutas';

/** La versión de lo que se entrega: sube cuando cambia lo que un lienzo puede pedir (no el aspecto). */
export const VERSION = 2;

/** Una opción del menú de la casa, como la pide el lienzo (vistas/dashboard/pedidos-locales.ts, `opciones`). */
interface Opcion { nombre: string; ayuda?: string; icono?: string; color?: string; apagada?: boolean }

interface Lienzo { pedir?: (orden: string, datos: unknown) => Promise<unknown>; componentes?: unknown }

const lienzo = (): Lienzo | undefined => (window as unknown as { lienzo?: Lienzo }).lienzo;

/** El menú de la casa, pedido a la página bajo `ancla`: el índice de la elegida, o undefined (sin elegir, o un lienzo
 *  que no puede pedir). */
export async function elegir(opciones: Opcion[], ancla: Element, titulo = ''): Promise<number | undefined> {
    const pedir = lienzo()?.pedir;
    if (typeof pedir !== 'function' || !opciones.length) return undefined;
    const r = ancla.getBoundingClientRect();
    try {
        const res = await pedir('opciones', { opciones, titulo, x: Math.round(r.left), y: Math.round(r.bottom) }) as { indice?: unknown } | null;
        return typeof res?.indice === 'number' ? res.indice : undefined;
    } catch { return undefined; }
}

/** Un grupo de filtros plegado: sus opciones en el menú (cada una con su cuenta; la que rige, con ✓ en el acento, y
 *  elegirla la suelta), como en la página (vistas/dashboard/vista.ts, `abrirFiltro`). Elegir una es como apretarla: el
 *  lienzo recibe el clic en su opción, con su `data-id`. */
async function abrirPlegado(g: HTMLElement): Promise<void> {
    const { nombre, opciones } = leerGrupo(g);
    const i = await elegir(opciones.map(o => ({
        nombre: o.nombre, ayuda: [o.cuenta ?? '', o.si ? 'clic: soltarlo' : ''].filter(x => x !== '').join(' · ') || undefined,
        icono: o.si ? I.hecha : ' ', ...(o.si ? { color: 'acento' } : {}),
    })), g, nombre || g.title);
    if (i !== undefined) g.querySelectorAll<HTMLElement>('.filtros-op')[i]?.click();
}

const esc = (t: string) => t.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));

/** Un documento en la prosa de telar: su markdown dibujado por la página (como en el visor), en un `.prosa.prosa-md`
 *  que sabe de qué archivo es (`ruta`, relativa a la raíz: de ahí salen sus enlaces relativos). Un lienzo que no puede
 *  pedir, o si la página no lo dibuja, el texto tal cual en la misma prosa: se lee igual, sin formato. */
export async function prosa(markdown: string, opciones: { ruta?: string } = {}): Promise<string> {
    const base = opciones.ruta ? ` data-base="${esc(opciones.ruta)}"` : '';
    const pedir = lienzo()?.pedir;
    if (typeof pedir === 'function') {
        try {
            const r = await pedir('prosa', { markdown }) as { html?: unknown } | null;
            if (typeof r?.html === 'string') return `<div class="prosa prosa-md"${base}>${r.html}</div>`;
        } catch { /* la página no lo dibujó: el texto tal cual */ }
    }
    return `<div class="prosa prosa-md"${base}><pre style="white-space: pre-wrap">${esc(markdown)}</pre></div>`;
}

/** Lo que es un título de la prosa, para un enlace `#así-se-llama`: sus letras y números, en minúsculas y con guiones. */
const ancla = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
    .replace(/[^\p{L}\p{N}\s-]/gu, '').replace(/\s+/g, '-');

/** Adónde lleva un enlace relativo de un documento de `ruta`: el archivo, desde su carpeta (una carpeta, su README). */
export function destinoDe(href: string, ruta: string): string {
    const limpio = decodeURIComponent(href.split('#')[0]);
    const carpeta = ruta.includes('/') ? ruta.slice(0, ruta.lastIndexOf('/')) : '';
    const destino = limpio.startsWith('/') ? limpio : unir(carpeta, limpio);
    return /\/$/.test(limpio) || !/\.[a-z0-9]+$/i.test(destino.split('/').pop() ?? '') ? unir(destino, 'README.md') : destino;
}

/** Un clic en un enlace de la prosa: lo que hace sin que el lienzo lo repita (arriba, en la cabecera). */
function clicEnProsa(e: MouseEvent): void {
    const a = (e.target as Element | null)?.closest?.<HTMLAnchorElement>('.prosa-md a[href]');
    if (!a || e.defaultPrevented) return;
    e.preventDefault();
    const href = a.getAttribute('href') ?? '';
    if (href.startsWith('#')) {
        const caja = a.closest('.prosa-md')!;
        const buscado = ancla(decodeURIComponent(href.slice(1)));
        const titulo = [...caja.querySelectorAll('h1, h2, h3, h4, h5, h6')].find(h => h.id === href.slice(1) || ancla(h.textContent ?? '') === buscado);
        titulo?.scrollIntoView({ block: 'start' });
        return;
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) { a.title = `${href} (afuera: el lienzo no tiene red)`; return; }
    const ruta = a.closest<HTMLElement>('[data-base]')?.dataset.base ?? '';
    const pedir = lienzo()?.pedir;
    if (typeof pedir === 'function') void pedir('abrir', { direccion: `archivo:${destinoDe(href, ruta)}` }).catch(() => undefined);
}

/** Las filas de pestañas ya acomodadas: una nueva (el lienzo repintó su cabecera) se acomoda al aparecer. */
const vistas = new WeakSet<Element>();

function acomodarNuevas(doc: Document): void {
    for (const f of doc.querySelectorAll('.pestanas')) if (!vistas.has(f)) { vistas.add(f); acomodar(f); }
}

/** Pone a andar lo que los componentes hacen solos en `doc`: una vez. */
export function atender(doc: Document = document): void {
    usarMenu(async (opciones, ancla, titulo) => {
        const i = await elegir(opciones.map(o => ({ nombre: o.label, ayuda: o.description, apagada: o.apagada,
            ...(o.icono ? { icono: o.icono } : {}), ...(o.color ? { color: o.color } : {}) })), ancla, titulo);
        return i === undefined ? undefined : opciones[i];
    });
    atenderPestanas(doc);
    atenderBuscadores(doc);
    doc.addEventListener('click', e => {
        const t = e.target as Element | null;
        // el clic que da `abrirPlegado` en una opción (las de un plegado no reciben el mouse) es del lienzo
        if (!t?.closest || t.closest('.filtros-op')) return;
        const g = t.closest<HTMLElement>('.filtros .filtros-grupo.plegado');
        if (!g) return;
        e.preventDefault(); e.stopPropagation();
        void abrirPlegado(g);
    }, true);
    doc.addEventListener('click', clicEnProsa);
    // lo que el lienzo dibuja después (su cabecera, cada vez que repinta): las pestañas nuevas, acomodadas al aparecer
    new MutationObserver(() => acomodarNuevas(doc)).observe(doc.documentElement, { childList: true, subtree: true });
    acomodarNuevas(doc);
}

/** Lo que recibe el lienzo en `window.lienzo.componentes`. */
export const componentes = {
    version: VERSION,
    pestanas, pestana, buscador, barraBuscar, filtros, marcarFiltros, contarFiltro, leerGrupo,
    /** las pestañas: acomodar una fila (o todas) al ancho que tiene, y marcar la abierta sin repintar */
    acomodar: (fila?: Element) => (fila ? acomodar(fila) : acomodarTodas(document)), marcar,
    /** el menú de la casa, para lo que el lienzo quiera elegir con él */
    elegir,
    /** un documento en la prosa de telar (async: lo dibuja la página), con sus enlaces andando */
    prosa,
    /** los íconos de la página (web/iconos.ts), en la letra `telar-iconos` */
    iconos: I,
};

// al cargarse en el lienzo (el iframe): queda en window.lienzo.componentes y se pone a andar
if (typeof window !== 'undefined' && typeof document !== 'undefined') {
    const w = window as unknown as { lienzo?: Lienzo };
    w.lienzo ??= {};
    w.lienzo.componentes = componentes;
    atender(document);
}
