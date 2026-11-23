// Las conexiones que una lectura puede llevar al grafo de conocimiento (la ficha de una pestaña de lectura, leer.ts):
// una sola lista en el margen, «conexiones», con una tarjeta por cada una (componentes/tarjeta.ts), cada una una arista
// de la lectura a una nota de la casa. Arriba, las que propone la ficha (`conexiones`), con su tipo, su porqué y la
// frase del texto en que se apoya (`ancla`). Abajo, las demás notas que nombra el texto (una ruta escrita como código,
// o la `nota` de un tema), sin tipo ni porqué. Nada más que eso: no se busca ni se agrega una nota cualquiera, y así el
// grafo queda chico.
//
// La tarjeta sigue el orden en que se decide: qué es esa nota, qué dice, cómo se relaciona con esta lectura, y
// conectarla. Plegada, su título es el de la nota (el de su documento; si no tiene, su nombre), y debajo va lo que dice
// la nota con sus palabras (su resumen: leer.ts lo saca del documento) y, si ya tiene una, la relación en una línea: el
// tipo en su color y su porqué. Al pie, un punto por cada conexión que la nota ya tiene (se ve cuál ya es un centro que
// no necesita más). Al inicio, el círculo: lleno, en el color de su tipo, entra; un aro, no. Ninguna entra si la
// persona no la elige.
//
// Un clic la expande en su lugar, una a la vez, y las demás siguen a la vista, plegadas. Adentro, primero la nota para
// leerla (su comienzo, y «seguir leyendo» la abre entera en el visor) y sus conexiones en el grafo (leer.ts); al final,
// la relación para crearla: el tipo (eligiendo del vocabulario que trae la ficha, `tipos`, que parte en el de ahora y
// muestra entero qué es cada uno y en qué se distingue del más cercano, porque elegir el tipo obliga a hacerse la
// pregunta), el porqué en un campo ahí mismo (el propuesto, para corregirlo), dónde se apoya en el texto (un clic lleva
// ahí), y «conectar», que es lo mismo que llenar el círculo y solo se puede con tipo y porqué. Conectada, lo dice, y se
// quita. Una nombrada parte sin tipo ni porqué; su tipo, en el que más usan las propuestas de la ficha.
//
// Una nota que no se puede leer no se puede conectar, y la tarjeta lo dice en vez de mostrarla vacía: una ruta que no
// está en el repositorio, o una carpeta sin documento (`documentoDeCarpeta`: la misma regla que el servidor). Al pasar
// por una, se ilumina en el texto su frase (la de una nombrada, donde se la nombra), en el color de su tipo. Lo elegido
// viaja con la acción que lleva `{conexiones}` en su comando («guardar en la biblioteca»), y lo que se va eligiendo
// sobrevive a recargar la página (web/guardado.ts).

import * as cli from '../../cli';
import { circulo } from '../../componentes/circulo';
import type { Pieza } from '../../componentes/item';
import { listaTarjetas, tarjeta } from '../../componentes/tarjeta';
import { esc } from '../../estilo';
import * as guardado from '../../web/guardado';
import * as ui from '../../web/ui';

/** Una relación propuesta, o una nota que nombra el texto, con lo que la persona decidió sobre ella. */
export interface Relacion {
    /** el destino de la arista: una ruta desde la raíz; de una carpeta nombrada, su documento (`documentoDeCarpeta`),
     *  que se sabe al leerla: hasta entonces, vacío */
    nota: string; titulo: string; tipo: string; porque: string; ancla: string;
    /** si entra al grafo; por defecto, no */
    entra: boolean;
    /** no la propone la ficha: la nombra el texto, y entra recién con tipo y porqué */
    nombrada?: boolean;
    /** cómo la escribe el texto, o la ficha (una carpeta, con su barra) */
    ruta: string;
    /** por qué no se puede leer ni conectar: no está en el repositorio, o es una carpeta sin documento */
    ilegible?: string;
}

/** Una nota que nombra el texto, como la escribe, y si se la nombra en el texto (no solo en los temas): entonces es su
 *  frase, la que se ilumina. */
export interface Nombrada { ruta: string; enTexto: boolean }

/** Lo que la tarjeta muestra de su nota, cuando ya se leyó (leer.ts): su título, y lo que dice, en HTML. */
export interface DeLaNota {
    titulo?: string;
    /** plegada: su resumen, con sus palabras */
    resumen?: string;
    /** expandida: su comienzo y sus conexiones en el grafo */
    nota?: string;
    /** cuántas conexiones tiene ya en el grafo; undefined si no se sabe */
    conexiones?: number;
}

export const esCarpeta = (ruta: string) => ruta.endsWith('/');

export { documentoDeCarpeta } from './nota';

export const nombreDe = (ruta: string) => (ruta.replace(/\/$/, '').split('/').pop() ?? ruta).replace(/\.(md|markdown)$/i, '');

/** Cuántas conexiones se dibujan como puntos bajo una nota; las demás se cuentan. */
const TOPE_PUNTOS = 30;

type Guardada = { ruta?: string; nota: string; entra: boolean; tipo: string; porque: string };

/** Las de la ficha y, después, las otras notas que nombra el texto (`nombradas`, las que no van ya propuestas), con lo
 *  que se eligió aquí antes de guardar (si quedó: sobrevive a recargar la página). */
export function leer(p: cli.JsonPagina, clave: string, nombradas: Nombrada[] = []): Relacion[] {
    const guardadas = guardado.leer<Guardada[]>(`${clave}:relaciones`) ?? [];
    const de = (ruta: string) => guardadas.find(x => (x.ruta ?? x.nota) === ruta);
    const propuestas: Relacion[] = (p.conexiones ?? []).map(c => {
        const g = de(c.nota);
        return { nota: c.nota, ruta: c.nota, titulo: c.titulo || nombreDe(c.nota), ancla: c.ancla ?? '', tipo: g?.tipo ?? c.tipo,
            porque: g?.porque ?? c.porque ?? '', entra: g ? g.entra : c.elegida === true };
    });
    // una carpeta nombrada que resulta ser el documento de otra ya se quita al leerla (leer.ts)
    const vistas = new Set(propuestas.map(r => r.ruta));
    const otras = nombradas.filter(n => !vistas.has(n.ruta) && (vistas.add(n.ruta), true))
        .map(n => {
            const g = de(n.ruta);
            return { nota: esCarpeta(n.ruta) ? '' : n.ruta, ruta: n.ruta, titulo: nombreDe(n.ruta), ancla: n.enTexto ? n.ruta : '',
                tipo: g?.tipo ?? '', porque: g?.porque ?? '', entra: !!g?.entra, nombrada: true };
        });
    return [...propuestas, ...otras];
}

/** Si se puede conectar: se sabe su documento y se puede leer. */
const conectable = (r: Relacion) => !!r.nota && !r.ilegible;
/** Si ya puede entrar: conectable, con tipo y porqué. */
const completa = (r: Relacion) => conectable(r) && !!r.tipo && !!r.porque.trim();
/** Lo que le falta para entrar, en palabras («el tipo y el porqué»); '' si nada. */
const faltaDe = (r: Relacion) => [r.tipo ? '' : 'el tipo', r.porque.trim() ? '' : 'el porqué'].filter(Boolean).join(' y ');

function anotar(rels: Relacion[], clave: string): void {
    guardado.guardar(`${clave}:relaciones`, rels.map(r => ({ ruta: r.ruta, nota: r.nota, entra: r.entra, tipo: r.tipo, porque: r.porque })));
}

/** Lo que viaja en `{conexiones}`: solo las elegidas; de una nombrada, también su título (la ficha no lo sabe). */
export const elegidas = (rels: Relacion[]) => rels.filter(r => r.entra && completa(r))
    .map(r => ({ nota: r.nota, tipo: r.tipo, porque: r.porque.trim(), ...(r.nombrada ? { titulo: r.titulo } : {}) }));

const tipoDe = (tipos: cli.JsonTipoArista[], t: string) => tipos.find(x => x.tipo === t);
/** El color de un tipo: el que dice su vocabulario, o violeta (el de las conexiones en el resto de la página). */
export const colorDe = (tipos: cli.JsonTipoArista[], t: string) => tipoDe(tipos, t)?.color || 'violeta';

/** Las conexiones, en HTML: una tarjeta por cada una. `notas`: lo que se sabe de la nota de cada una (leer.ts).
 *  `fuera`: las que traen una frase que no está en el texto de la ficha (la sacaron del original): esa frase va citada,
 *  porque no hay dónde iluminarla. `abierta`: la expandida (-1: ninguna). */
export function html(rels: Relacion[], tipos: cli.JsonTipoArista[], notas: (r: Relacion) => DeLaNota, fuera = new Set<number>(),
    abierta = -1): string {
    if (!rels.length) return '';
    const n = elegidas(rels).length;
    const total = rels.filter(r => !r.ilegible).length;
    const cuenta = n ? `entran ${n} de ${total}` : `ninguna de ${total}, todavía`;
    const tarjetas = rels.map((r, i) => tarjetaDe(r, i, tipos, notas(r), fuera.has(i), i === abierta));
    return `<section class="relaciones"><div class="rotulo">conexiones <span class="cuenta-rel">${cuenta}</span></div>`
        + `${listaTarjetas(tarjetas, 'lista-rel')}</section>`;
}

/** Un punto por cada conexión que la nota ya tiene en el grafo (hasta un tope; las demás, contadas). */
function puntos(k: number | undefined): Pieza[] {
    if (k === undefined) return [];
    return [{ texto: k ? '•'.repeat(Math.min(k, TOPE_PUNTOS)) + (k > TOPE_PUNTOS ? ` +${k - TOPE_PUNTOS}` : '') : 'sin conexiones',
        ayuda: k ? `ya tiene ${k} ${k === 1 ? 'conexión' : 'conexiones'} en el grafo` : 'todavía sin conexiones en el grafo' }];
}

/** El círculo del inicio: lleno en el color de su tipo, entra; un aro, no. Un clic lo cambia (si le falta algo, abre
 *  la tarjeta para ponérselo). */
function marca(r: Relacion, i: number, tipos: cli.JsonTipoArista[]): string {
    const entra = r.entra && completa(r);
    const ayuda = entra ? 'conectada: un clic, y no entra al grafo'
        : completa(r) ? 'un clic: conectarla (entra al grafo al guardar)'
        : `para conectarla le falta ${faltaDe(r)}: un clic la abre`;
    return `<a class="marca-rel" data-rel-marcar="${i}" title="${esc(ayuda)}" style="color: var(--${entra ? esc(colorDe(tipos, r.tipo)) : 'dim'})">`
        + `${circulo({ lleno: entra ? 1 : 0 })}</a>`;
}

/** La relación en una línea: el tipo en su color y su porqué. */
function enUnaLinea(r: Relacion, tipos: cli.JsonTipoArista[]): string {
    if (!r.tipo) return '';
    return `<div class="linea-rel"><span class="tipo-rel" style="color: var(--${esc(colorDe(tipos, r.tipo))})">${esc(r.tipo)}</span>`
        + `${r.porque.trim() ? ` <span class="porque-rel">${esc(r.porque.trim())}</span>` : ''}</div>`;
}

/** Una conexión, como tarjeta. Plegada: el círculo, el título de la nota, lo que dice y la relación en una línea, y los
 *  puntos al pie. Expandida: la nota para leerla, y la relación para crearla. Una que no se puede leer, solo lo dice. */
function tarjetaDe(r: Relacion, i: number, tipos: cli.JsonTipoArista[], de: DeLaNota, fuera: boolean, abierta: boolean): string {
    if (r.ilegible) {
        // una carpeta que está (sin documento) se puede mirar en el visor; una ruta que no está, no
        const ruta = esCarpeta(r.ruta) && !/no está/.test(r.ilegible)
            ? `<a class="ruta-rel" data-abrir-nota="${esc(r.ruta)}" title="mirarla en el visor">${esc(r.ruta)}</a>` : `<span class="ruta-rel">${esc(r.ruta)}</span>`;
        return tarjeta({
            inicio: [{ circulo: { lleno: 0 }, tono: 'atencion', ayuda: `${r.ilegible}: no se puede conectar` }],
            titulo: de.titulo || r.titulo,
            cuerpoHtml: `<div class="ilegible-rel">${esc(r.ilegible)}</div>${ruta}`,
            clases: ['rel', 'ilegible', r.nombrada ? 'nombrada' : ''],
            datosHtml: { rel: String(i) },
        });
    }
    const plegada = (de.resumen ? `<div class="resumen-rel">${de.resumen}</div>` : '') + enUnaLinea(r, tipos);
    return tarjeta({
        inicio: [{ html: marca(r, i, tipos) }],
        titulo: de.titulo || r.titulo,
        cuerpoHtml: abierta ? (de.nota ?? '<div class="ayuda">leyendo la nota…</div>') + detalle(r, i, tipos, fuera) : plegada,
        datos: abierta ? [] : puntos(de.conexiones),
        activa: abierta,
        holgada: abierta,
        clases: ['rel', r.entra && completa(r) ? 'entra' : '', r.nombrada ? 'nombrada' : '', abierta ? 'abierta' : ''],
        datosHtml: { rel: String(i), 'rel-abrir': String(i) },
    });
}

/** «conectar», o, conectada, que lo está y «quitar». Sin tipo o sin porqué, «conectar» dice qué le falta. */
function accionRel(r: Relacion, i: number, tipos: cli.JsonTipoArista[]): string {
    const col = esc(colorDe(tipos, r.tipo));
    if (r.entra && completa(r)) {
        return `<div class="accion-rel"><span class="conectada" style="color: var(--${col})" title="entra al grafo al guardar">conectada</span>`
            + ` <a class="quitar-rel" data-rel-marcar="${i}" title="que no entre al grafo">quitar</a></div>`;
    }
    const falta = faltaDe(r);
    return `<div class="accion-rel"><a class="conectar-rel${falta ? ' incompleta' : ''}" data-rel-conectar="${i}" style="--c: var(--${col})"`
        + ` title="${falta ? `le falta ${esc(falta)}` : 'entra al grafo al guardar'}">conectar</a>`
        + `${falta ? ` <span class="falta-rel">falta ${esc(falta)}</span>` : ''}</div>`;
}

/** Lo de la relación, al final de la tarjeta expandida: el tipo (un clic lo cambia), el porqué en su campo, dónde se
 *  apoya en el texto, y conectarla. */
function detalle(r: Relacion, i: number, tipos: cli.JsonTipoArista[], fuera: boolean): string {
    const t = tipoDe(tipos, r.tipo);
    const fila = (rotulo: string, valor: string) => `<div class="fila-rel"><span class="rotulo-rel">${rotulo}</span>${valor}</div>`;
    const tipo = r.tipo
        ? `<a class="tipo-detalle" data-rel-tipo="${i}" style="color: var(--${esc(colorDe(tipos, r.tipo))})" title="${esc(t?.que ?? '')}${t?.que ? '\n' : ''}un clic: otro tipo">${esc(r.tipo)}</a>`
        : `<a class="por-elegir" data-rel-tipo="${i}" title="cómo se relaciona esta lectura con la nota: elegirlo del vocabulario">elegir el tipo</a>`;
    const porque = `<textarea class="porque-campo" data-rel-campo="${i}" data-guarda rows="2" spellcheck="true" style="--c: var(--${esc(colorDe(tipos, r.tipo))})"`
        + ` placeholder="por qué se relacionan, en una línea: el matiz va aquí, no en otro tipo">${esc(r.porque)}</textarea>`;
    // la frase en que se apoya: un clic lleva a ella; la que no está en el texto de la ficha, citada
    const ancla = !r.ancla ? ''
        : fuera ? fila('en el original', `<span class="ancla-rel">«${esc(r.ancla.replace(/`/g, ''))}»</span>`)
        : r.nombrada ? fila('en el texto', `<a data-rel-ir="${i}" title="llevarme ahí">donde la nombra</a>`)
        : fila('en el texto', `<a class="ancla-rel" data-rel-ir="${i}" title="llevarme ahí">«${esc(r.ancla.replace(/`/g, ''))}»</a>`);
    return `<div class="detalle-rel">${fila('relación', tipo)}<div class="fila-rel campo-rel"><span class="rotulo-rel">por qué</span>${porque}</div>`
        + `${ancla}${accionRel(r, i, tipos)}</div>`;
}

/** El rango de la frase en el texto de la ficha (sus párrafos y sus ítems), o undefined si no está. */
function rango(raiz: HTMLElement, ancla: string): Range | undefined {
    // en el texto dibujado, un `código` ya no lleva sus comillas
    const buscada = ancla.replace(/`/g, '').replace(/\s+/g, ' ').trim();
    if (!buscada) return undefined;
    for (const p of raiz.querySelectorAll<HTMLElement>('.texto-leer .prosa p, .texto-leer .prosa li')) {
        const nodos: { n: Text; desde: number }[] = [];
        let todo = '';
        const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
        for (let n = w.nextNode() as Text | null; n; n = w.nextNode() as Text | null) { nodos.push({ n, desde: todo.length }); todo += n.data; }
        const i = todo.indexOf(buscada);
        if (i < 0) continue;
        const en = (k: number) => {
            const x = [...nodos].reverse().find(y => y.desde <= k) ?? nodos[0];
            return { n: x.n, o: Math.min(k - x.desde, x.n.length) };
        };
        const a = en(i), b = en(i + buscada.length);
        const r = document.createRange();
        r.setStart(a.n, a.o); r.setEnd(b.n, b.o);
        return r;
    }
    return undefined;
}

/** Las relaciones propuestas cuya frase no está en el texto de la ficha (por su índice). */
export const fueraDelTexto = (raiz: HTMLElement, rels: Relacion[]) =>
    new Set(rels.flatMap((r, i) => (!r.nombrada && r.ancla && !rango(raiz, r.ancla) ? [i] : [])));

/** La frase del texto en que se apoya una relación, iluminada en el color de su tipo (con el CSS Custom Highlight; un
 *  navegador sin él no la ilumina). `ir`: además, se lleva a la vista. Sin `ancla`, se apaga la que hubiera. */
export function iluminar(raiz: HTMLElement, ancla: string, color = 'violeta', ir = false): void {
    const reg = (CSS as unknown as { highlights?: Map<string, unknown> }).highlights;
    const H = (window as unknown as { Highlight?: new (...r: Range[]) => unknown }).Highlight;
    if (!reg || !H) return;
    for (const c of ['verde', 'rojo', 'amarillo', 'azul', 'cian', 'magenta', 'violeta']) reg.delete(`ancla-${c}`);
    const r = rango(raiz, ancla);
    if (!r) return;
    reg.set(`ancla-${color}`, new H(r));
    if (ir) {
        const caja = r.getBoundingClientRect();
        raiz.closest<HTMLElement>('.v-dia')?.scrollBy({ top: caja.top - window.innerHeight / 3, behavior: 'smooth' });
    }
}

/** Atiende un clic en las conexiones: marcar, conectar, cambiar el tipo, o ir a su frase. Devuelve si era suyo;
 *  `repintar` las dibuja de nuevo con lo cambiado, que ya quedó guardado, y `abrir` expande una tarjeta. */
export function clic(e: MouseEvent, raiz: HTMLElement, rels: Relacion[], tipos: cli.JsonTipoArista[], clave: string,
    repintar: () => void, abrir: (i: number) => void): boolean {
    const t = e.target as Element;
    const listo = () => { e.preventDefault(); e.stopPropagation(); };
    const cambio = () => { anotar(rels, clave); repintar(); };
    // el campo del porqué es para escribir: un clic ahí no pliega ni abre nada
    if (t.closest('[data-rel-campo]')) { e.stopPropagation(); return true; }
    const tp = t.closest<HTMLElement>('[data-rel-tipo]');
    if (tp) {
        listo();
        const r = rels[Number(tp.dataset.relTipo)];
        void cambiarTipo(r, rels, tipos).then(si => { if (si) cambio(); });
        return true;
    }
    const cn = t.closest<HTMLElement>('[data-rel-conectar]');
    if (cn) {
        listo();
        const i = Number(cn.dataset.relConectar);
        const r = rels[i];
        if (completa(r)) { r.entra = true; cambio(); return true; }
        // le falta algo: lo que falta, primero el tipo
        if (!r.tipo) void cambiarTipo(r, rels, tipos).then(si => { if (si) { cambio(); enfocarPorque(raiz, i); } });
        else enfocarPorque(raiz, i);
        return true;
    }
    const m = t.closest<HTMLElement>('[data-rel-marcar]');
    if (m) {
        listo();
        const i = Number(m.dataset.relMarcar);
        const r = rels[i];
        // a una que no tiene con qué entrar, el círculo la abre para ponérselo
        if (!completa(r)) { abrir(i); return true; }
        r.entra = !r.entra;
        cambio();
        return true;
    }
    const ir = t.closest<HTMLElement>('[data-rel-ir]');
    if (ir) {
        listo();
        const r = rels[Number(ir.dataset.relIr)];
        iluminar(raiz, r.ancla, colorDe(tipos, r.tipo), true);
        return true;
    }
    return false;
}

const enfocarPorque = (raiz: HTMLElement, i: number) => raiz.querySelector<HTMLTextAreaElement>(`[data-rel-campo="${i}"]`)?.focus();

/** Lo que se escribe en el campo del porqué: queda (sobrevive a recargar), y la tarjeta dice al tiro si ya se puede
 *  conectar, sin dibujarse de nuevo (el campo no pierde el cursor). ⏎ no parte la línea: conecta, si se puede.
 *  `cambio`: cuando cambia si entra (lo cuenta la acción que guarda). */
export function escribir(raiz: HTMLElement, rels: Relacion[], tipos: cli.JsonTipoArista[], clave: string, cambio: () => void): void {
    const de = (e: Event) => {
        const c = (e.target as Element).closest<HTMLTextAreaElement>('[data-rel-campo]');
        return c ? { c, i: Number(c.dataset.relCampo) } : undefined;
    };
    const alDia = (i: number) => {
        const tj = raiz.querySelector<HTMLElement>(`.rel[data-rel="${i}"]`);
        const r = rels[i];
        if (!tj || !r) return;
        tj.querySelector('.accion-rel')?.replaceWith(dom(accionRel(r, i, tipos)));
        tj.querySelector('.marca-rel')?.replaceWith(dom(marca(r, i, tipos)));
        tj.classList.toggle('entra', r.entra && completa(r));
    };
    raiz.addEventListener('input', e => {
        const x = de(e);
        if (!x) return;
        const r = rels[x.i];
        const antes = r.entra && completa(r);
        r.porque = x.c.value.replace(/\s*\n\s*/g, ' ');
        anotar(rels, clave);
        alDia(x.i);
        if (antes !== (r.entra && completa(r))) cambio();
    });
    raiz.addEventListener('keydown', e => {
        const x = de(e);
        if (!x || e.key !== 'Enter' || e.isComposing) return;
        // es del campo: el ⏎ del dashboard (la acción principal de la ficha) no lo ve
        e.preventDefault();
        e.stopPropagation();
        const r = rels[x.i];
        if (!r.entra && completa(r)) { r.entra = true; anotar(rels, clave); cambio(); }
    });
}

/** Un trozo de HTML de la página, como nodo. */
function dom(html: string): Element {
    const t = document.createElement('template');
    t.innerHTML = html;
    return t.content.firstElementChild!;
}

/** Desde qué tipo parte el selector de una nombrada que todavía no tiene: el que más usan las propuestas de la ficha
 *  (el primero de ellos, si empatan). Sin propuestas, desde el comienzo del vocabulario. */
function tipoInicial(rels: Relacion[]): string {
    const cuantas = new Map<string, number>();
    for (const r of rels) if (!r.nombrada && r.tipo) cuantas.set(r.tipo, (cuantas.get(r.tipo) ?? 0) + 1);
    let mejor = '';
    for (const [t, k] of cuantas) if (k > (cuantas.get(mejor) ?? 0)) mejor = t;
    return mejor;
}

/** El vocabulario por grupos, partiendo en el tipo de ahora, con lo que es cada uno y en qué se distingue. Devuelve si
 *  quedó un tipo elegido. */
async function cambiarTipo(r: Relacion, rels: Relacion[], tipos: cli.JsonTipoArista[]): Promise<boolean> {
    if (!tipos.length) { void ui.aviso('telar: la ficha no trae el vocabulario de tipos'); return false; }
    const opciones: (ui.Opcion & { tipo?: string })[] = [];
    let grupo = '';
    for (const x of tipos) {
        if (x.grupo && x.grupo !== grupo) { grupo = x.grupo; opciones.push({ label: x.grupo, separador: true }); }
        opciones.push({ label: x.tipo, description: x.que, detail: x.distingue ? `distingue: ${x.distingue.replace(/`/g, '')}` : '', color: x.color || 'violeta', tipo: x.tipo });
    }
    const desde = r.tipo || tipoInicial(rels);
    const inicial = opciones.findIndex(o => o.tipo === desde);
    const elegido = await ui.elegir(opciones, { titulo: `cómo se relaciona esta lectura con «${r.titulo}»`,
        placeholder: 'el tipo de relación: lo que es cada uno, y en qué se distingue', ...(inicial >= 0 ? { inicial } : {}) });
    if (!elegido?.tipo) return false;
    r.tipo = elegido.tipo;
    return true;
}
