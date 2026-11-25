// Los comentarios de un archivo, en el visor (web/carpeta.ts): la persona selecciona texto y escribe lo que hay que hacer ahí,
// para que un agente lo lea y trabaje en ello. Se guardan al lado del archivo, en `.<nombre>.marginalia.json`
// (docs/contratos.md, «Los comentarios de un archivo»; `GET /api/comentarios` y `POST /api/comentarios`), y el documento no
// se toca. Están pensados para la IA: un autor, sin menciones ni avisos.
//
// · En el texto, solo la marca: el tramo comentado con un fondo tenue en la tinta de los comentarios (el texto no cambia de
//   color: se lee igual que el resto) y, al final del tramo, su número chico. Lo resuelto, más tenue, con su número.
// · En la barra de la derecha (web/documento-lado.ts, la hoja «comentarios»), la lista en el orden del documento: cada uno
//   con su número (el mismo del texto), su estado, la cita corta y lo que dice; al final, los que perdieron su lugar («sin
//   ancla»). Un clic en uno lo abre ahí mismo (lo respondido, y responder, resolver o reabrir, editar y borrar) y lleva el
//   documento a su tramo; un clic en un tramo (o en su número) abre la barra en él. Pasar el mouse por uno enciende el
//   otro.
// · Comentar: al seleccionar texto aparece «comentar» junto a la selección (y la tecla c hace lo mismo). La barra se abre
//   en comentarios con la caja nueva arriba, lo seleccionado queda marcado en el texto mientras se escribe, y ⌘⏎ lo guarda.
//   La selección es sobre lo dibujado, pero el ancla va contra el texto fuente (web/fuente.ts): las líneas de los bloques
//   acotan dónde buscar, y la búsqueda por letras y números calza la cita aunque haya ** o enlaces de por medio.
//
// Uno abierto a la vez; ⎋ lo cierra (y la siguiente ⎋, el visor).

import { esc } from '../estilo';
import { boton, pieBotones } from '../componentes/boton';
import type { Cuenta } from './documento-lado';
import * as fuente from './fuente';
import { C, I } from './iconos';
import * as ui from './ui';

/** Un hilo, como lo da la API: ubicado en el texto de hoy (telar.servicios.comentarios). */
export interface Hilo {
    id: string; estado: string; cita: string; antes: string; despues: string; creado: string;
    anclado: boolean; metodo: string | null; confianza: number | null;
    linea: number | null; linea_fin: number | null; inicio: number | null; fin: number | null; actual: string | null;
    comentarios: { id: string; autor: string; cuerpo: string; fecha: string }[];
}
export interface Comentarios { ruta: string; archivo: string; lateral: string; maquina: string; autor: string; hilos: Hilo[]; hecho: string }

/** Lo que el visor le da a la capa: dónde está cada cosa y qué archivo es. */
export interface PartesCapa {
    /** el visor, el que se desplaza, y lo dibujado del archivo (`.md` o el `<pre>` de un texto) */
    visor: HTMLElement; cuerpo: HTMLElement; contenido: HTMLElement;
    /** la ruta del archivo como la entiende la API (desde la raíz, entera, o con «máquina:» delante) y su texto fuente */
    ruta: string; fuente: string;
    /** si es markdown (si no, lo que se ve es la fuente tal cual) */
    md: boolean;
    /** la hoja de comentarios de la barra (donde va la lista), y la barra: abrirla, su cuenta y con qué abre */
    lista: HTMLElement;
    lado: { mostrar(): void; cuenta(c: Cuenta): void; decidir(abiertos: number): void };
    markdown: (texto: string) => string;
}

/** Cómo se dice que el ancla no fue exacta (cuando lo fue, no se dice nada). */
export function notaDe(h: Pick<Hilo, 'metodo' | 'confianza' | 'anclado'>): string {
    if (!h.anclado) return 'sin ancla: lo comentado ya no está';
    switch (h.metodo) {
        case 'contexto': return 'reanclado entre repeticiones';
        case 'normalizado': return 'reanclado tras el reflujo de líneas';
        case 'aproximado': return `reanclado por parecido (${Math.round((h.confianza ?? 0) * 100)}%): el texto cambió`;
        case 'vecindario': return 'lo comentado ya no está: anclado por lo que lo rodeaba';
        default: return '';
    }
}

/** Los hilos en el orden del documento (por dónde empiezan; a la par, el más viejo primero), y al final los sin ancla
 *  (el más viejo primero). Su número es su lugar aquí, desde 1: el mismo en el texto y en la barra. */
export function ordenar<T extends Pick<Hilo, 'anclado' | 'inicio' | 'creado'>>(hilos: T[]): T[] {
    const lugar = (h: T) => (h.anclado && h.inicio !== null ? h.inicio : Number.POSITIVE_INFINITY);
    return [...hilos].sort((a, b) => lugar(a) - lugar(b) || (a.creado < b.creado ? -1 : a.creado > b.creado ? 1 : 0));
}

/** La cuenta de la pestaña: los abiertos, en la tinta de los comentarios; sin abiertos, cuántos hay, tenue. */
export function cuentaDe(hilos: Pick<Hilo, 'estado'>[]): Cuenta {
    const abiertos = hilos.filter(h => h.estado === 'abierto').length;
    return { n: abiertos || hilos.length, tinta: abiertos > 0,
        ayuda: `comentarios: ${abiertos} ${abiertos === 1 ? 'abierto' : 'abiertos'} de ${hilos.length}\ncomentar: selecciona texto y c` };
}

/** Una fecha ISO, corta: «23 nov 14:12». */
function cuando(iso: string): string {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const mes = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][d.getMonth()];
    return `${d.getDate()} ${mes} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

const recorte = (s: string, n = 90): string => { const l = s.replace(/\s+/g, ' ').trim(); return l.length > n ? `${l.slice(0, n - 1)}…` : l; };

/** Los nodos de texto de `raiz` (en orden), sin los del botón de comentar ni los números de los tramos. */
function textos(raiz: Node, dentro?: (n: Text) => boolean): Text[] {
    const r: Text[] = [];
    const w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {
        acceptNode: n => (n.parentElement?.closest('.coment-tarjeta, .coment-flota, .coment-n') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    for (let n = w.nextNode(); n; n = w.nextNode()) if (!dentro || dentro(n as Text)) r.push(n as Text);
    return r;
}

/** El texto de un tramo de la página, sin el de los números. */
function textoDe(rango: Range): string {
    let s = '';
    for (const t of textos(rango.commonAncestorContainer.nodeType === Node.TEXT_NODE ? rango.commonAncestorContainer.parentNode! : rango.commonAncestorContainer,
        n => rango.intersectsNode(n))) {
        const a = t === rango.startContainer ? rango.startOffset : 0;
        const b = t === rango.endContainer ? rango.endOffset : t.data.length;
        s += t.data.slice(a, b);
    }
    return s;
}

/** Envuelve en marcas (`hacer` da una) el tramo de las piezas `nodos` desde `de` hasta `a` ([pieza, posición]): una por nodo
 *  de texto que toca. Sin ancho, una marca vacía antes de `de`. */
function envolver(nodos: Text[], de: [number, number], a: [number, number], hacer: () => HTMLElement): HTMLElement[] {
    if (de[0] === a[0] && de[1] === a[1]) {
        const t = nodos[de[0]], m = hacer();
        m.classList.add('vacia');
        t.parentNode!.insertBefore(m, de[1] > 0 ? t.splitText(de[1]) : t);
        return [m];
    }
    const marcas: HTMLElement[] = [];
    for (let k = de[0]; k <= a[0]; k++) {
        let t = nodos[k];
        const s = k === de[0] ? de[1] : 0, f = k === a[0] ? a[1] : t.data.length;
        if (f <= s) continue;
        if (f < t.data.length) t.splitText(f);
        if (s > 0) t = t.splitText(s);
        const m = hacer();
        t.parentNode!.insertBefore(m, t);
        m.appendChild(t);
        marcas.push(m);
    }
    return marcas;
}

/** Saca las marcas y los números, dejando el texto donde estaba. */
function desenvolver(raiz: HTMLElement): void {
    const padres = new Set<Node>();
    for (const n of [...raiz.querySelectorAll('sup.coment-n')]) { if (n.parentNode) padres.add(n.parentNode); n.remove(); }
    for (const m of [...raiz.querySelectorAll('mark.coment')]) {
        const p = m.parentNode;
        if (!p) continue;
        while (m.firstChild) p.insertBefore(m.firstChild, m);
        m.remove();
        padres.add(p);
    }
    for (const p of padres) p.normalize();
}

/** Lo seleccionado para comentar: su tramo en la fuente y lo que se vio. */
interface Nuevo { inicio: number; fin: number; cita: string; antes: string; despues: string }

const porHilo = (id: string) => `[data-hilo="${CSS.escape(id)}"]`;

export class Capa {
    /** en el orden del documento: su número es su lugar + 1 */
    private hilos: Hilo[] = [];
    /** el hilo abierto en la barra; «+», el de uno nuevo */
    private abierta = '';
    /** el comentario que se está editando, en el hilo abierto */
    private editando = '';
    private nuevo?: Nuevo;
    private flota?: HTMLElement;
    private suelta = false;
    private enviando = false;
    private readonly ini: number[];
    private readonly fuera: [number, number][];
    private readonly alSeleccionar = () => this.mirarSeleccion();
    private readonly alClic = (e: MouseEvent) => this.clic(e);
    private readonly alPasar = (e: MouseEvent) => this.pasar(e);
    private readonly alSalir = (e: MouseEvent) => { if (!(e.relatedTarget as Element | null)?.closest?.('[data-hilo]')) this.encender(''); };

    constructor(private readonly p: PartesCapa) {
        this.ini = fuente.inicios(p.fuente);
        this.fuera = p.md ? fuente.ocultos(p.fuente) : [];
        document.addEventListener('selectionchange', this.alSeleccionar);
        for (const x of [p.cuerpo, p.lista]) {
            x.addEventListener('click', this.alClic);
            x.addEventListener('mouseover', this.alPasar);
            x.addEventListener('mouseout', this.alSalir);
        }
    }

    /** Deja de mirar la selección y saca lo suyo del visor (se cierra, o muestra otro archivo). */
    soltar(): void {
        this.suelta = true;
        document.removeEventListener('selectionchange', this.alSeleccionar);
        for (const x of [this.p.cuerpo, this.p.lista]) {
            x.removeEventListener('click', this.alClic);
            x.removeEventListener('mouseover', this.alPasar);
            x.removeEventListener('mouseout', this.alSalir);
        }
        this.flota?.remove();
    }

    async cargar(): Promise<void> {
        try {
            const r = await fetch(`/api/comentarios?ruta=${encodeURIComponent(this.p.ruta)}`, { cache: 'no-store' });
            const j = await r.json() as Comentarios & { detail?: string };
            if (this.suelta) return;
            if (!r.ok) { this.problema(typeof j.detail === 'string' ? j.detail : `la API respondió ${r.status}`); return; }
            this.recibir(j);
            this.p.lado.decidir(this.hilos.filter(h => h.estado === 'abierto').length);
        } catch (e) {
            if (!this.suelta) this.problema(`la API no respondió: ${(e as Error).message}`);
        }
    }

    private recibir(c: Comentarios, enfocar = false): void {
        this.hilos = ordenar(c.hilos);
        this.pintar(enfocar);
    }

    /** Lo que no se pudo con los comentarios: en su hoja (el documento se lee igual). */
    private problema(texto: string): void {
        this.p.lista.innerHTML = `<p class="nada">los comentarios: ${esc(texto)}</p>`;
        this.p.lado.cuenta({ n: null });
        this.p.lado.decidir(0);
    }

    /** El número de un hilo: su lugar en el orden del documento. */
    numero(id: string): number { return this.hilos.findIndex(h => h.id === id) + 1; }

    // ── lo que se ve ────────────────────────────────────────────────────────────────────────────────────────────

    /** Las marcas, la lista y la cuenta, como dicen los hilos (`enfocar`: con el foco en el campo del abierto, después de
     *  mandar algo desde él). */
    private pintar(enfocar = false): void {
        if (this.abierta && this.abierta !== '+' && !this.hilos.some(h => h.id === this.abierta)) { this.abierta = ''; this.editando = ''; }
        this.marcar();
        this.pintarLista(enfocar);
        this.p.lado.cuenta(cuentaDe(this.hilos));
    }

    /** La lista de la barra: la caja de uno nuevo arriba (si se está comentando), y cada hilo con su número; el abierto,
     *  entero. */
    private pintarLista(enfocar = false): void {
        const l = this.p.lista;
        const nuevo = this.abierta === '+' && this.nuevo ? this.htmlNuevo(this.nuevo) : '';
        const anclados = this.hilos.filter(h => h.anclado), sueltos = this.hilos.filter(h => !h.anclado);
        const filas = (hs: Hilo[]) => hs.map(h => this.htmlFila(h)).join('');
        l.innerHTML = nuevo
            + (this.hilos.length ? `<div class="coment-filas">${filas(anclados)}`
                + (sueltos.length ? `<div class="coment-grupo">sin ancla <span class="n">${sueltos.length}</span></div>${filas(sueltos)}` : '')
                + '</div>'
                : nuevo ? '' : '<p class="nada">ninguno todavía. Para comentar, selecciona texto en el documento y aprieta c</p>');
        this.activar();
        // el foco: en la caja de lo que se escribe (salvo en el teléfono al abrir uno, que abriría el teclado); si no, que
        // no quede en la nada, que ⎋ ya no cerraría lo abierto sino el visor
        const campo = this.editando
            ? l.querySelector<HTMLTextAreaElement>(`[data-comentario="${CSS.escape(this.editando)}"] textarea`)
            : l.querySelector<HTMLTextAreaElement>('.coment-tarjeta textarea.coment-campo');
        if (campo && (enfocar || this.abierta === '+' || this.editando || !document.body.classList.contains('angosto'))) {
            campo.focus({ preventScroll: true });
            campo.setSelectionRange(campo.value.length, campo.value.length);
        } else if (!this.p.visor.contains(document.activeElement)) this.p.cuerpo.focus({ preventScroll: true });
    }

    /** La caja para comentar lo seleccionado: la cita y el campo. */
    private htmlNuevo(n: Nuevo): string {
        return '<div class="coment-tarjeta nuevo">'
            + `<div class="coment-cabeza"><span class="coment-estado nuevo">nuevo</span></div>`
            + `<div class="coment-cita">«${esc(recorte(n.cita, 200))}»</div>`
            + '<textarea class="coment-campo" rows="3" placeholder="qué hay que hacer aquí (lo lee un agente)"></textarea>'
            + '<p class="coment-problema"></p>'
            + pieBotones([{ texto: 'comentar', tecla: '⌘⏎', datos: { coment: 'guardar' } },
                { texto: 'cancelar', tecla: '⎋', tono: 'callado', datos: { coment: 'cerrar' } }])
            + '</div>';
    }

    /** Un hilo en la lista: su número, su estado, la cita corta y lo que dice; abierto, todo lo respondido y lo que se le
     *  hace. */
    private htmlFila(h: Hilo): string {
        const n = this.numero(h.id), resuelto = h.estado === 'resuelto', abierto = h.id === this.abierta;
        const estado = !h.anclado ? '<span class="coment-estado suelto">sin ancla</span>'
            : `<span class="coment-estado ${resuelto ? 'resuelto' : 'abierto'}">${resuelto ? 'resuelto' : 'abierto'}</span>`;
        const resp = h.comentarios.length - 1;
        const cab = `<div class="coment-fila-cab"><span class="coment-num">${n}</span>${estado}`
            + `${h.linea ? `<span class="coment-linea">línea ${h.linea}</span>` : ''}`
            + (!abierto && resp > 0 ? `<span class="coment-resp">${resp === 1 ? '1 respuesta' : `${resp} respuestas`}</span>` : '') + '</div>';
        const clase = `coment-fila ${!h.anclado ? 'suelto' : resuelto ? 'resuelto' : 'abierto'}${abierto ? ' activa' : ''}`;
        const ayuda = `${h.id} · ${h.estado}${notaDe(h) ? ` · ${notaDe(h)}` : ''}`;
        if (!abierto) {
            const primero = h.comentarios[0];
            return `<div class="${clase}" data-hilo="${esc(h.id)}" title="${esc(ayuda)}">${cab}`
                + `<div class="coment-cita">«${esc(recorte(h.cita, 120))}»</div>`
                + (primero ? `<div class="coment-texto">${esc(recorte(primero.cuerpo, 240))}</div>` : '')
                + '</div>';
        }
        return `<div class="${clase}" data-hilo="${esc(h.id)}">${cab}${this.htmlAbierto(h)}</div>`;
    }

    /** Lo de un hilo abierto: dónde se lo encontró si no fue exacto, lo que se dijo, y responder, resolver o reabrir,
     *  editar y borrar. */
    private htmlAbierto(h: Hilo): string {
        const nota = notaDe(h);
        const cita = h.metodo && h.metodo !== 'exacto' || !h.anclado
            ? `<div class="coment-cita">comentó «${esc(recorte(h.cita, 200))}»${h.actual ? `; hoy dice «${esc(recorte(h.actual, 200))}»` : ''}</div>`
            : `<div class="coment-cita">«${esc(recorte(h.cita, 200))}»</div>`;
        const comentarios = h.comentarios.map((c, k) => `<div class="coment-uno" data-comentario="${esc(c.id)}">`
            + `<div class="coment-quien"><span class="coment-autor">${esc(c.autor)}</span> <span class="coment-fecha">${esc(cuando(c.fecha))}</span>`
            + (this.editando ? '' : '<span class="coment-iconos">'
                + `<a class="coment-icono" data-coment="editar" data-comentario="${esc(c.id)}" title="editar"><span class="i">${I.editar}</span></a>`
                + `<a class="coment-icono peligro" data-coment="borrar" data-comentario="${esc(c.id)}" title="${k === 0 ? 'borrar el comentario y sus respuestas' : 'borrar esta respuesta'}"><span class="i">${I.descartar}</span></a>`
                + '</span>')
            + '</div>'
            + (this.editando === c.id ? `<textarea class="coment-campo" rows="3">${esc(c.cuerpo)}</textarea>`
                : `<div class="coment-cuerpo">${this.p.markdown(c.cuerpo)}</div>`)
            + '</div>').join('');
        const resuelto = h.estado === 'resuelto';
        const pie = this.editando
            ? pieBotones([{ texto: 'guardar', tecla: '⌘⏎', datos: { coment: 'guardar-edicion' } },
                { texto: 'cancelar', tecla: '⎋', tono: 'callado', datos: { coment: 'cancelar-edicion' } }])
            : pieBotones([{ texto: 'responder', tecla: '⌘⏎', datos: { coment: 'responder' } },
                resuelto ? { texto: 'reabrir', icono: I.retomar, color: C.cambiar, datos: { coment: 'reabrir' }, ayuda: 'volver a abrirlo: no está hecho' }
                    : { texto: 'resolver', icono: I.hecha, color: C.hecho, datos: { coment: 'resolver' }, ayuda: 'está hecho (con lo escrito como respuesta, si hay)' },
                { texto: 'cerrar', tecla: '⎋', tono: 'callado', datos: { coment: 'cerrar' } }]);
        return `<div class="coment-tarjeta hilo ${resuelto ? 'resuelto' : 'abierto'}" data-hilo="${esc(h.id)}">`
            + (nota ? `<div class="coment-nota">${esc(nota)}</div>` : '')
            + cita + comentarios
            + (this.editando ? '' : `<textarea class="coment-campo" rows="2" placeholder="${resuelto ? 'responder…' : 'responder (o lo que se hizo, para resolver)…'}"></textarea>`)
            + '<p class="coment-problema"></p>' + pie + '</div>';
    }

    /** Los bloques dibujados que vienen de las líneas [l0, l1] de la fuente: los de más afuera. */
    private bloques(l0: number, l1: number): HTMLElement[] {
        const todos = [...this.p.contenido.querySelectorAll<HTMLElement>('[data-src]')];
        if (this.p.contenido.dataset.src) todos.unshift(this.p.contenido);
        const tocan = todos.filter(b => { const r = fuente.lineas(b.dataset.src); return !!r && r[0] <= l1 && r[1] > l0; });
        return tocan.filter(b => !tocan.some(o => o !== b && o.contains(b)));
    }

    /** La línea (desde 0) de una posición de la fuente. */
    private linea(i: number): number {
        let a = 0, b = this.ini.length - 2;
        while (a < b) { const m = (a + b + 1) >> 1; if (this.ini[m] <= i) a = m; else b = m - 1; }
        return a;
    }

    /** Las marcas de cada hilo con lugar, sobre lo dibujado, con su número al final del tramo; y lo que se está por
     *  comentar. */
    private marcar(): void {
        desenvolver(this.p.contenido);
        // los resueltos primero: uno abierto encima de uno resuelto queda por fuera, y se ve
        const orden = [...this.hilos].sort((a, b) => (a.estado === 'resuelto' ? 0 : 1) - (b.estado === 'resuelto' ? 0 : 1));
        for (const h of orden) {
            if (!h.anclado || h.inicio === null || h.fin === null) continue;
            const estado = h.estado === 'resuelto' ? 'resuelto' : 'abierto';
            const ayuda = `${this.numero(h.id)} · ${h.comentarios[0]?.autor ?? ''}: ${recorte(h.comentarios[0]?.cuerpo ?? '', 200)}`;
            const marcas = this.envolverTramo(h.inicio, h.fin, () => {
                const m = document.createElement('mark');
                m.className = `coment ${estado}`;
                m.dataset.hilo = h.id;
                m.title = ayuda;
                return m;
            });
            const ultima = marcas.at(-1);
            if (!ultima) continue;
            const n = document.createElement('sup');
            n.className = `coment-n ${estado}`;
            n.dataset.hilo = h.id;
            n.title = ayuda;
            n.textContent = String(this.numero(h.id));
            ultima.after(n);
        }
        if (this.nuevo && this.abierta === '+') this.envolverTramo(this.nuevo.inicio, this.nuevo.fin, () => {
            const m = document.createElement('mark');
            m.className = 'coment nuevo';
            return m;
        });
        this.activar();
    }

    /** Envuelve en marcas el tramo [inicio, fin) de la fuente, donde se ve. */
    private envolverTramo(inicio: number, fin: number, hacer: () => HTMLElement): HTMLElement[] {
        const l0 = this.linea(inicio), l1 = this.linea(Math.max(inicio, fin - 1));
        const bloques = this.bloques(l0, l1);
        if (!bloques.length) return [];
        const desde = fuente.lineas(bloques[0].dataset.src)![0];
        const nodos = bloques.flatMap(b => textos(b));
        const lugar = fuente.ubicarEnPiezas(this.p.fuente, inicio, fin, nodos.map(n => ({ texto: n.data })), this.ini[desde] ?? 0, this.fuera);
        return lugar ? envolver(nodos, lugar.de, lugar.a, hacer) : [];
    }

    /** El hilo abierto, marcado en el texto y en la lista. */
    private activar(): void {
        for (const x of this.p.contenido.querySelectorAll<HTMLElement>('mark.coment[data-hilo], sup.coment-n')) x.classList.toggle('activa', x.dataset.hilo === this.abierta);
    }

    /** Enciende un hilo (el que está bajo el mouse) en el texto y en la lista; '' los apaga. */
    private encender(id: string): void {
        for (const raiz of [this.p.contenido, this.p.lista]) {
            for (const x of raiz.querySelectorAll<HTMLElement>('mark.coment[data-hilo], sup.coment-n, .coment-fila[data-hilo]')) x.classList.toggle('encendida', !!id && x.dataset.hilo === id);
        }
    }

    private pasar(e: MouseEvent): void {
        const x = (e.target as HTMLElement).closest?.<HTMLElement>('mark.coment[data-hilo], sup.coment-n, .coment-fila[data-hilo]');
        this.encender(x?.dataset.hilo ?? '');
    }

    // ── comentar lo seleccionado ────────────────────────────────────────────────────────────────────────────────

    /** Lo seleccionado, si está en lo dibujado del archivo. */
    private seleccion(): Range | undefined {
        const sel = getSelection();
        if (!sel || sel.isCollapsed || !sel.rangeCount) return undefined;
        const r = sel.getRangeAt(0);
        const dentro = (n: Node) => { const e = n.nodeType === Node.ELEMENT_NODE ? n as Element : n.parentElement; return !!e && this.p.contenido.contains(e) && !e.closest('.coment-tarjeta'); };
        return dentro(r.startContainer) && dentro(r.endContainer) && textoDe(r).trim() ? r : undefined;
    }

    /** El botón de comentar, junto a lo seleccionado; se va si no hay selección. */
    private mirarSeleccion(): void {
        if (this.suelta) return;
        const r = this.seleccion();
        if (!r || this.abierta === '+') { this.flota?.remove(); this.flota = undefined; return; }
        if (!this.flota) {
            this.flota = document.createElement('div');
            this.flota.className = 'coment-flota';
            this.flota.innerHTML = boton({ texto: 'comentar', tecla: 'c', datos: { coment: 'comentar' }, color: C.cambiar,
                ayuda: 'comentar lo seleccionado: lo lee un agente' });
            // que el clic no se lleve la selección antes de leerla
            this.flota.addEventListener('mousedown', e => e.preventDefault());
            this.p.cuerpo.appendChild(this.flota);
        }
        const rects = r.getClientRects(), ultimo = rects[rects.length - 1] ?? r.getBoundingClientRect();
        const caja = this.p.cuerpo.getBoundingClientRect();
        const x = Math.max(0, Math.min(ultimo.right - caja.left + this.p.cuerpo.scrollLeft - this.flota.offsetWidth / 2,
            this.p.cuerpo.clientWidth - this.flota.offsetWidth));
        this.flota.style.left = `${x}px`;
        this.flota.style.top = `${ultimo.bottom - caja.top + this.p.cuerpo.scrollTop + 4}px`;
    }

    /** Dónde está en la fuente lo seleccionado: las líneas de sus bloques, lo que se ve antes en el primero y lo que dice. */
    private anclaDe(r: Range): Nuevo | undefined {
        const bloque = (n: Node) => ((n.nodeType === Node.ELEMENT_NODE ? n as Element : n.parentElement)?.closest<HTMLElement>('[data-src]'))
            ?? (this.p.contenido.dataset.src ? this.p.contenido : null);
        const b0 = bloque(r.startContainer), b1 = bloque(r.endContainer);
        const l0 = fuente.lineas(b0?.dataset.src), l1 = fuente.lineas(b1?.dataset.src);
        const lineas: [number, number] | undefined = l0 && l1 ? [Math.min(l0[0], l1[0]), Math.max(l0[1], l1[1])] : undefined;
        let previo = '';
        if (b0) { const antes = document.createRange(); antes.setStart(b0, 0); antes.setEnd(r.startContainer, r.startOffset); previo = textoDe(antes); }
        const t = fuente.ubicarSeleccion(this.p.fuente, textoDe(r), lineas, previo, this.fuera);
        if (!t) return undefined;
        const [i, f] = t, s = this.p.fuente;
        return { inicio: i, fin: f, cita: s.slice(i, f), antes: s.slice(Math.max(0, i - 48), i), despues: s.slice(f, f + 48) };
    }

    /** Abre la barra en comentarios con la caja para comentar lo seleccionado, que queda marcado en el texto. False si no
     *  hay nada seleccionado en el archivo. */
    comentarSeleccion(): boolean {
        const r = this.seleccion();
        if (!r) return false;
        const n = this.anclaDe(r);
        if (!n) { ui.estado('no encuentro eso en el texto del archivo: selecciona un poco menos, o solo texto'); return true; }
        getSelection()?.removeAllRanges();
        this.nuevo = n;
        this.abierta = '+';
        this.editando = '';
        this.flota?.remove(); this.flota = undefined;
        this.p.lado.mostrar();
        this.marcar();
        this.pintarLista();
        this.p.lista.scrollTop = 0;
        return true;
    }

    // ── abrir y cerrar uno ──────────────────────────────────────────────────────────────────────────────────────

    /** Abre un hilo en la barra (y la barra, si estaba plegada). `desde`: de dónde vino el clic; del texto, la lista lo
     *  muestra; de la lista, el documento va a su tramo. */
    abrir(id: string, desde: 'texto' | 'lista' = 'lista'): void {
        if (!this.hilos.some(h => h.id === id)) return;
        if (this.abierta === '+') { this.nuevo = undefined; this.marcar(); }
        const ya = this.abierta === id;
        this.abierta = id;
        this.editando = '';
        this.p.lado.mostrar();
        if (!ya) this.pintarLista();
        this.activar();
        if (desde === 'texto') this.p.lista.querySelector(`.coment-fila${porHilo(id)}`)?.scrollIntoView({ block: 'nearest' });
        else this.p.contenido.querySelector(`mark.coment${porHilo(id)}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }

    /** Cierra el abierto (o la caja de uno nuevo). False si no había (⎋ es entonces del visor). */
    cerrarTarjeta(): boolean {
        if (!this.abierta) return false;
        const eraNuevo = this.abierta === '+';
        this.abierta = ''; this.editando = ''; this.nuevo = undefined;
        if (eraNuevo) this.marcar();
        this.pintarLista();
        this.p.cuerpo.focus({ preventScroll: true });
        return true;
    }

    // ── lo que se hace ──────────────────────────────────────────────────────────────────────────────────────────

    private clic(e: MouseEvent): void {
        const t = e.target as HTMLElement;
        const b = t.closest<HTMLElement>('[data-coment]');
        if (b && (this.p.cuerpo.contains(b) || this.p.lista.contains(b))) { e.preventDefault(); e.stopPropagation(); void this.hacer(b.dataset.coment ?? '', b); return; }
        // un tramo (o su número) abre su hilo; si es un enlace, el enlace manda
        const m = t.closest<HTMLElement>('mark.coment[data-hilo], sup.coment-n');
        if (m && this.p.contenido.contains(m) && (m.tagName === 'SUP' || !t.closest('a')) && !getSelection()?.toString()) {
            e.preventDefault(); e.stopPropagation();
            this.abrir(m.dataset.hilo!, 'texto');
            return;
        }
        // una fila de la lista (no lo de adentro del abierto, que es para escribir y apretar)
        const f = t.closest<HTMLElement>('.coment-fila[data-hilo]');
        if (f && this.p.lista.contains(f) && !t.closest('.coment-tarjeta')) {
            e.preventDefault(); e.stopPropagation();
            this.abrir(f.dataset.hilo!, 'lista');
        }
    }

    private tarjeta(): HTMLElement | null { return this.p.lista.querySelector<HTMLElement>('.coment-tarjeta'); }

    private async hacer(que: string, b: HTMLElement): Promise<void> {
        const tarjeta = this.tarjeta();
        const id = tarjeta?.dataset.hilo ?? '';
        const campo = () => (tarjeta?.querySelector<HTMLTextAreaElement>('textarea.coment-campo')?.value ?? '').trim();
        switch (que) {
            case 'comentar': this.comentarSeleccion(); return;
            case 'cerrar': this.cerrarTarjeta(); return;
            case 'editar': this.editando = b.dataset.comentario ?? ''; this.pintarLista(); return;
            case 'cancelar-edicion': this.editando = ''; this.pintarLista(); return;
            case 'guardar': {
                if (!this.nuevo) return;
                if (!campo()) { this.decir('¿qué hay que hacer aquí? Escríbelo para el agente'); return; }
                await this.mandar({ accion: 'comentar', texto: campo(), ...this.nuevo }, h => { this.nuevo = undefined; this.abierta = h; });
                return;
            }
            case 'guardar-edicion':
                if (!campo()) { this.decir('quedaría vacío: para quitarlo, bórralo'); return; }
                await this.mandar({ accion: 'editar', hilo: id, comentario: this.editando, texto: campo() }, () => { this.editando = ''; });
                return;
            case 'responder':
                if (!campo()) { this.decir('¿qué respondes?'); return; }
                await this.mandar({ accion: 'responder', hilo: id, texto: campo() });
                return;
            case 'resolver':
            case 'reabrir':
                await this.mandar({ accion: que, hilo: id, texto: campo() });
                return;
            case 'borrar': {
                const h = this.hilos.find(x => x.id === id), c = b.dataset.comentario ?? '';
                if (!h) return;
                const primero = h.comentarios[0]?.id === c;
                const resp = h.comentarios.length - 1;
                const texto = primero ? `¿Borrar el comentario «${recorte(h.comentarios[0].cuerpo, 80)}»${resp ? ` y sus ${resp === 1 ? 'una respuesta' : `${resp} respuestas`}` : ''}?`
                    : `¿Borrar la respuesta de ${h.comentarios.find(x => x.id === c)?.autor ?? ''}?`;
                if (await ui.aviso(texto, 'Borrar', { destruye: true }) !== 'Borrar') return;
                await this.mandar({ accion: 'borrar', hilo: id, comentario: primero ? '' : c }, () => { if (primero) this.abierta = ''; });
                return;
            }
        }
    }

    private decir(texto: string): void {
        const p = this.tarjeta()?.querySelector<HTMLElement>('.coment-problema');
        if (p) p.textContent = texto;
    }

    /** Manda un cambio y pinta cómo quedó. `luego(hecho)`: antes de pintar, con el hilo que se creó o cambió. */
    private async mandar(pedido: Record<string, unknown>, luego?: (hecho: string) => void): Promise<void> {
        if (this.enviando) return;
        this.enviando = true;
        const botones = [...this.p.lista.querySelectorAll<HTMLButtonElement>('.coment-tarjeta button.boton')];
        for (const x of botones) x.disabled = true;
        try {
            const r = await fetch('/api/comentarios', { method: 'POST', headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ ruta: this.p.ruta, ...pedido }) });
            const j = await r.json() as Comentarios & { detail?: unknown };
            if (this.suelta) return;
            if (!r.ok) {
                this.decir(typeof j.detail === 'string' ? j.detail : `no se pudo (la API respondió ${r.status})`);
                for (const x of botones) x.disabled = false;
                return;
            }
            luego?.(j.hecho);
            this.recibir(j, true);
        } catch (e) {
            this.decir(`la API no respondió: ${(e as Error).message}`);
            for (const x of botones) x.disabled = false;
        } finally {
            this.enviando = false;
        }
    }
}
