// Un objeto de telar por su dirección (`tipo:id[@máquina]`, GET /api/objetos/<dirección>): su título, su estado, su
// resumen, sus campos, sus enlaces (otras direcciones, que se abren igual) y sus acciones, que se corren aquí mismo
// pidiendo lo que necesitan (POST /api/objetos/<dirección>/acciones/<acción>). Es la vista de los tipos que no tienen
// una propia, como los de un módulo; una tarea, un archivo, un proyecto o un hilo se abren en la suya
// (navegador/app.ts, `abrirDireccion`). Va en un recuadro con «‹ …» arriba, que vuelve a la vista de donde se vino,
// como el visor de documentos. Se dibuja en un elemento de la página; sus estilos, en media/css/objeto.css (con
// @scope, en `.v-objeto`).

import * as cli from '../cli';
import { esc, recuadro, volver } from '../estilo';
import type { Vuelta } from './carpeta';
import { enlazar } from './rutas-agente';
import * as ui from './ui';
import { teclaParaLaVista } from './vistas-hilo';

/** Una dirección partida: su tipo, su id y la máquina de `@máquina` ('' si no la dice). */
export function partir(direccion: string): { tipo: string; id: string; maquina: string } {
    const i = direccion.indexOf(':');
    let id = direccion.slice(i + 1), maquina = '';
    const m = /@([A-Za-z0-9][\w-]*)$/.exec(id);
    if (m) { maquina = m[1]; id = id.slice(0, m.index); }
    return { tipo: direccion.slice(0, i), id, maquina };
}

/** La vuelta de cada vista de objeto: la pone `montar` cuando la página la muestra. */
const vueltas = new WeakMap<HTMLElement, Vuelta | null>();
/** El objeto que muestra cada vista, para correr sus acciones. */
const mostrados = new WeakMap<HTMLElement, cli.JsonObjeto>();

/** Un valor de un campo, como texto: una lista con comas, un objeto como JSON, y las direcciones como enlaces. */
function valor(v: unknown): string {
    if (Array.isArray(v)) return v.map(valor).join(', ');
    if (v !== null && typeof v === 'object') return esc(JSON.stringify(v));
    return esc(String(v));
}

function html(o: cli.JsonObjeto, vuelta: Vuelta | null | undefined, markdown: (texto: string) => string): string {
    const campos = Object.entries(o.campos ?? {}).filter(([, v]) => v !== '' && v !== null && v !== undefined
        && !(Array.isArray(v) && !v.length));
    const donde = [o.tipo, o.estado, o.maquina ? `en ${o.maquina}` : ''].filter((x): x is string => !!x).map(esc).join(' · ');
    const cuerpo = `<h1>${esc(o.titulo || o.direccion)}</h1>`
        + `<div class="donde">${donde} · <code>${esc(o.direccion)}</code></div>`
        + (o.resumen ? `<div class="resumen md">${markdown(o.resumen)}</div>` : '')
        + (campos.length ? `<dl class="campos">${campos.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${valor(v)}</dd>`).join('')}</dl>` : '')
        + (o.enlaces?.length ? `<h2>enlaces</h2><ul class="enlaces">${o.enlaces.map(d =>
            `<li><a data-direccion="${esc(d)}" title="abrir ${esc(d)}">${esc(d)}</a></li>`).join('')}</ul>` : '')
        + (o.acciones?.length ? `<h2>acciones</h2><div class="acciones">${o.acciones.map(a =>
            `<a data-accion-obj="${esc(a.nombre)}" title="${esc(a.descripcion || a.nombre)}">${esc(a.nombre)}</a>`).join('')}</div>` : '');
    return (vuelta ? volver('volver-obj', vuelta.nombre, '', `volver a ${vuelta.nombre} (⎋)`) : '') + recuadro(cuerpo);
}

/** Lee el objeto de `direccion` y lo dibuja en `el`. `vuelta`: adónde lleva «‹ …» (y ⎋); null, a ninguna parte; sin
 *  ella, la que ya tenía. */
export async function montar(el: HTMLElement, direccion: string, markdown: (texto: string) => string,
    vuelta?: Vuelta | null): Promise<void> {
    el.classList.add('v-objeto');
    el.dataset.direccion = direccion;
    if (vuelta !== undefined) vueltas.set(el, vuelta);
    if (!el.dataset.atendido) {
        el.dataset.atendido = '1';
        window.addEventListener('keydown', e => {
            if (e.key !== 'Escape' || !teclaParaLaVista(e, el)) return;
            const v = vueltas.get(el);
            if (v) { e.preventDefault(); v.ir(); }
        });
        el.addEventListener('click', e => {
            const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a');
            if (!a) return;
            if (a.dataset.accion === 'volver-obj') { e.preventDefault(); vueltas.get(el)?.ir(); return; }
            if (a.dataset.direccion) { e.preventDefault(); void ui.abrirDireccion(a.dataset.direccion); return; }
            const o = mostrados.get(el);
            if (a.dataset.accionObj && o) { e.preventDefault(); void correr(el, o, a.dataset.accionObj, markdown); return; }
            // un enlace del resumen a una web: en otra pestaña, sin llevarse la página
            const href = a.getAttribute('href') ?? '';
            if (/^https?:\/\//i.test(href)) { e.preventDefault(); void ui.abrirExterno(href); }
        });
    }
    el.innerHTML = `<div class="nada">leyendo ${esc(direccion)}…</div>`;
    const r = await cli.objeto(direccion);
    if (el.dataset.direccion !== direccion) return;
    if (r.datos) dibujar(el, r.datos, markdown);
    else {
        mostrados.delete(el);
        const v = vueltas.get(el);
        el.innerHTML = (v ? volver('volver-obj', v.nombre, '', `volver a ${v.nombre} (⎋)`) : '')
            + recuadro(`<h1>${esc(direccion)}</h1><p class="nada">${esc(r.error ?? 'no se pudo leer')}</p>`);
    }
}

function dibujar(el: HTMLElement, o: cli.JsonObjeto, markdown: (texto: string) => string): void {
    mostrados.set(el, o);
    el.innerHTML = html(o, vueltas.get(el), markdown);
    // las direcciones del resumen y de los campos, enlaces también
    for (const parte of el.querySelectorAll<HTMLElement>('.resumen, .campos')) enlazar(parte, false);
    el.scrollTop = 0;
}

/** Corre una acción del objeto: pide cada parámetro (con su valor de entrada), o si no lleva ninguno, que se confirme;
 *  y después dibuja el objeto como quedó. Si falló (o cambió desde que se leyó), lo dice y lo vuelve a leer. */
async function correr(el: HTMLElement, o: cli.JsonObjeto, nombre: string, markdown: (texto: string) => string): Promise<void> {
    const a = o.acciones?.find(x => x.nombre === nombre);
    if (!a) return;
    const params: Record<string, string> = {};
    const pide = Object.entries(a.params ?? {});
    for (const [k, defecto] of pide) {
        const v = await ui.campo({ titulo: `${a.nombre} · ${o.titulo || o.direccion}`, ayuda: a.descripcion || k, placeholder: k, valor: defecto });
        if (v === undefined) return;
        params[k] = v;
    }
    if (!pide.length && await ui.aviso(`¿${a.nombre}? ${o.titulo || o.direccion}`, 'Sí') !== 'Sí') return;
    const r = await ui.progreso({ titulo: `telar: ${a.nombre} · ${o.direccion}…` },
        () => cli.accionObjeto(o.direccion, a.nombre, params, o.version ?? ''));
    if (el.dataset.direccion !== o.direccion) return;
    if (!r.datos) {
        void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`);
        await montar(el, o.direccion, markdown);
        return;
    }
    const hecho = typeof r.datos.resultado === 'string' && r.datos.resultado ? r.datos.resultado : `${a.nombre}: hecho`;
    ui.estado(hecho);
    if (r.datos.objeto) dibujar(el, r.datos.objeto, markdown);
    else await montar(el, o.direccion, markdown);
}
