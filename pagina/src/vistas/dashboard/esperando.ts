// «tareas › esperando»: lo que otros le deben a la persona, agrupado por persona. Una subpestaña de «tareas», junto a
// foco y lista (pantalla.ts, SUBPESTANAS), con las pestañas de siempre en su barra.
//
//   tareas                                         foco · lista · esperando        ↻
//   buscar ___________                                                              ← la barra del buscador
//   ▽ esperan 4  delegadas 42  vencidas 9                                           ← los filtros
//   ▾ ANA PÉREZ  2                                                                  ← una sección por persona
//     ● ⏲ T379  Molino: esperar los accesos de TI                      -38d · 6sem  ← plazo · antigüedad
//               ↳ llegaron los repositorios; faltan las credenciales          2sem   ← lo último que pasó
//     ◐ 👤 T512  Faro: armar el temario                                   4d · 4sem  ← delegada: otro ícono y tinta
//   ▾ LEO  1
//
// De dónde sale: de las tareas, y de nada más (no hay una segunda base de compromisos). Entran dos clases:
// · **esperan**: en estado de espera (`todo espera`), agrupadas por a quién esperan (`espera`); el reloj en el color de
//   cuidado. Si además tienen dueño, el título lo dice («· la hace Leo»).
// · **delegadas**: activas con un dueño que no es la persona (`dueño`), agrupadas por su dueño; la persona, en la tinta
//   de lo que es de otro. Son lo que la persona le pidió a otro: también es lo que le deben, pero no está detenido.
// Lo de la persona (sin dueño, o a su nombre) no entra.
//
// La antigüedad es desde cuándo la tiene otro (`desde`: la línea de la historia que la puso a esperar o le dio dueño; sin
// ninguna, su creación). Lo último que pasó es la última línea de su historia que no edita campos sueltos (`ultimo`):
// las dos las pone el proveedor del tipo `tarea` (telar.proveedores.tareas, `de_otro`). Sin ellas (un telar de antes),
// la fila dice solo el plazo.
//
// Las personas van de la que debe hace más a la más reciente; dentro de cada una, las que esperan primero y, en cada
// clase, de la más vieja a la más nueva. Un nombre de pila suelto («Ana») se junta con el nombre entero que empieza así
// («Ana Pérez») si hay uno solo. Un clic en una fila abre la ficha de la tarea (⎋ vuelve aquí); al pasar el mouse, lo de
// todos los días de una tarea (fila-tarea.ts). El buscador y los filtros esconden filas sin repintar; cada persona se
// pliega y se recuerda (componentes/seccion.ts, Plegado).

import { barraBuscar } from '../../componentes/buscador';
import { contarFiltro, filtros, marcarFiltros } from '../../componentes/filtros';
import { item, pieza, type Pieza } from '../../componentes/item';
import { Plegado, seccion, type Memoria } from '../../componentes/seccion';
import { esc, limpiarMd, normalizar } from '../../estilo';
import { I } from '../../web/iconos';
import { esMia, leidoProveedores, pendientes, type Pendiente } from './dia';
import { edad } from './esperas';
import { fecha, piezasTarea } from './fila-tarea';
import type { Accion, Pantalla, Tablero } from './pantalla';

export type Clase = 'espera' | 'delegada';

/** Lo que alguien le debe a la persona: una tarea, de quién es y desde cuándo. */
export interface Compromiso {
    p: Pendiente;
    clase: Clase;
    /** a quién espera, o quién la hace (como está escrito) */
    persona: string;
    /** quién la hace, si espera a otro y además tiene dueño (no la persona) */
    dueno: string;
    /** desde cuándo la tiene otro, en ISO («2026-10-15T16:59»); '' si no se sabe */
    desde: string;
}

/** Una persona y lo que debe, en su orden. */
export interface Deudor { clave: string; nombre: string; compromisos: Compromiso[] }

/** «2026-10-15 16:59» como ISO de este reloj (Safari no lee la fecha con espacio). */
const iso = (t: string | undefined): string => (t ?? '').trim().replace(' ', 'T');

/** Las tareas que tiene otro: las que esperan a alguien y las delegadas (con dueño que no es la persona). */
export function compromisos(lista: Pendiente[]): Compromiso[] {
    const salida: Compromiso[] = [];
    for (const p of lista) {
        const f = p.fila;
        const espera = (f.espera ?? '').replace(/^@/, '').trim();
        const dueno = (f.dueno ?? '').trim();
        const ajeno = !!dueno && !esMia(dueno);
        if (espera) salida.push({ p, clase: 'espera', persona: espera, dueno: ajeno && normalizar(dueno) !== normalizar(espera) ? dueno : '', desde: iso(f.desde) });
        else if (ajeno) salida.push({ p, clase: 'delegada', persona: dueno, dueno: '', desde: iso(f.desde) });
    }
    return salida;
}

const primera = (n: string): string => normalizar(n).split(/\s+/)[0] ?? '';

/** La persona de cada compromiso, junta: la clave normalizada; un nombre de pila suelto va con el nombre entero que
 *  empieza así, si hay uno solo (con dos «Raúl …», queda aparte). */
export function claves(nombres: string[]): Map<string, { clave: string; nombre: string }> {
    const enteros = [...new Set(nombres.map(n => n.trim()).filter(n => /\s/.test(n)))];
    const salida = new Map<string, { clave: string; nombre: string }>();
    for (const n of nombres) {
        const limpio = n.trim();
        let nombre = limpio;
        if (!/\s/.test(limpio)) {
            const suyos = enteros.filter(e => primera(e) === normalizar(limpio));
            if (suyos.length === 1) nombre = suyos[0];
        }
        salida.set(n, { clave: normalizar(nombre), nombre });
    }
    return salida;
}

/** Lo más viejo primero; lo que no sabe desde cuándo, al final. */
const porDesde = (a: Compromiso, b: Compromiso): number => (a.desde || '9') < (b.desde || '9') ? -1 : (a.desde || '9') > (b.desde || '9') ? 1 : a.p.ref.localeCompare(b.p.ref);

/** Las personas con lo que deben: de la que debe hace más a la más reciente; en cada una, las que esperan primero. */
export function deudores(cs: Compromiso[]): Deudor[] {
    const nombres = claves(cs.map(c => c.persona));
    const grupos = new Map<string, Deudor>();
    for (const c of cs) {
        const { clave, nombre } = nombres.get(c.persona)!;
        const g = grupos.get(clave) ?? { clave, nombre, compromisos: [] };
        g.compromisos.push(c);
        grupos.set(clave, g);
    }
    const lista = [...grupos.values()];
    for (const g of lista) g.compromisos.sort((a, b) => (a.clase === b.clase ? 0 : a.clase === 'espera' ? -1 : 1) || porDesde(a, b));
    const masVieja = (g: Deudor) => g.compromisos.map(c => c.desde || '9').sort()[0];
    return lista.sort((a, b) => masVieja(a) < masVieja(b) ? -1 : masVieja(a) > masVieja(b) ? 1 : a.nombre.localeCompare(b.nombre));
}

/** El plazo y la antigüedad, en la meta de la fila: «-38d · 6sem» (el plazo como en «tareas»: lo vencido en rojo). */
export function metaDe(c: Compromiso, ahora = Date.now()): Pieza | undefined {
    const plazo = fecha(c.p.dias);
    const cuanto = edad(c.desde, ahora);
    const desde = c.desde ? `${c.clase === 'espera' ? 'espera' : 'la tiene'} desde ${c.desde.replace('T', ' ')}` : '';
    if (!plazo) return cuanto ? { texto: cuanto, tono: 'tenue', ayuda: `sin plazo · ${desde}` } : undefined;
    if (!cuanto) return plazo;
    return { html: `${pieza(plazo, 'item-vence')} · ${esc(cuanto)}`, ayuda: `${plazo.ayuda} (${c.p.cuando.slice(0, 10)}) · ${desde}` };
}

/** Lo que un compromiso lleva para el buscador y los filtros, en sus dos filas. */
function datos(c: Compromiso, clave: string): Record<string, string> {
    const u = c.p.fila.ultimo;
    return {
        busca: normalizar([c.p.ref, c.p.texto, c.persona, c.dueno, c.p.fila.proyecto ?? '', u?.texto ?? ''].join(' ')),
        clase: c.clase, persona: clave, vencida: c.p.dias !== null && c.p.dias < 0 ? '1' : '0',
    };
}

/** Un compromiso en sus filas (componentes/item.ts): la tarea, con su prioridad, de qué clase es (el reloj de la que
 *  espera, la persona de la delegada), su código, el título, el plazo y la antigüedad; y debajo, tenue y corrida, lo
 *  último que pasó, con cuánto hace. Las dos abren la ficha. */
export function filas(c: Compromiso, clave: string, ahora = Date.now()): string {
    const { valor, prioridad, acciones, menu, aviso } = piezasTarea(c.p);
    const d = datos(c, clave);
    const desde = c.desde ? ` desde ${c.desde.replace('T', ' ').slice(0, 16)}` : '';
    const clase: Pieza = c.clase === 'espera'
        ? { icono: I.reloj, tono: 'atencion', ayuda: `espera a ${c.persona}${desde}` }
        : { icono: I.persona, tono: 'remoto', ayuda: `delegada: la hace ${c.persona}${desde}` };
    const codigo: Pieza = { texto: c.p.ref, ancho: 5, tono: 'tenue' };
    const texto = limpiarMd(c.p.texto);
    const u = c.p.fila.ultimo;
    const principal = item({
        clases: ['tarea', 'compromiso'], accion: 'tarea', datos: { valor, ...d },
        ayuda: `${c.p.ref} · ${texto}\n${clase.ayuda}\nclic: leerla y decidir`,
        inicio: [prioridad, clase, codigo], titulo: texto,
        sufijo: c.dueno ? [{ texto: `· la hace ${c.dueno}`, tono: 'tenue' }] : [],
        aviso, meta: metaDe(c, ahora), acciones, menu,
    });
    if (!u?.texto) return principal;
    const cuando = iso(u.fecha);
    return principal + item({
        clases: ['compromiso', 'compromiso-ultimo'], accion: 'tarea', datos: { valor, ...d }, apagada: true, hondo: 1,
        ayuda: `lo último que pasó (${u.fecha}${u.tipo ? `, ${u.tipo}` : ''}):\n${u.texto}\nclic: leer la tarea`,
        inicio: [null, null, { texto: '', ancho: 5 }], prefijo: [{ texto: '↳', tono: 'tenue' }], titulo: limpiarMd(u.texto),
        meta: cuando ? { texto: edad(cuando, ahora), tono: 'tenue', ayuda: u.fecha } : undefined,
    });
}

/** Los filtros: qué clase (las que esperan, las delegadas) y lo vencido; cada uno con su cuenta. */
function grupoFiltro(cs: Compromiso[], activa: string) {
    const n = (f: (c: Compromiso) => boolean) => cs.filter(f).length;
    return { clave: 'cuales', nombre: 'cuáles', activa, opciones: [
        { clave: 'espera', nombre: 'esperan', cuenta: n(c => c.clase === 'espera'), ayuda: 'esperan: detenidas hasta que otro responda (estado de espera)' },
        { clave: 'delegada', nombre: 'delegadas', cuenta: n(c => c.clase === 'delegada'), ayuda: 'delegadas: las hace otro (tienen dueño); no están detenidas' },
        { clave: 'vencida', nombre: 'vencidas', cuenta: n(c => c.p.dias !== null && c.p.dias < 0), ayuda: 'vencidas: su plazo ya pasó' },
    ] };
}

/** El cuerpo de la subpestaña: la barra del buscador, los filtros y una sección por persona. */
export function cuerpo(cs: Compromiso[], abierta: (clave: string) => boolean, o: { filtro?: string; ahora?: number; leyendo?: boolean } = {}): string[] {
    const ahora = o.ahora ?? Date.now();
    // cuántas hay de cada una, también las de una persona plegada (sus filas no están en la página): las cuentas sin buscar
    const g = grupoFiltro(cs, o.filtro ?? '');
    const cuentas = g.opciones.map(x => ` data-n-${x.clave}="${x.cuenta}"`).join('');
    const h = [`<div id="esperando" class="lista-tareas lista-esperando" data-total="${cs.length}"${cuentas}>`,
        barraBuscar({ id: 'buscar-esperando', cuenta: { id: 'esperando-cuenta' }, claseBarra: 'herram', placeholder: 'lo que te deben',
            ayuda: 'buscar en el código, el texto, la persona y lo último que pasó · ⎋ borra' }),
        filtros({ accion: 'esperando-filtro', grupos: [g] })];
    const ds = deudores(cs);
    // sin las tareas de los proveedores todavía, no se sabe: no se dice que nadie debe nada
    if (!ds.length) h.push(item({ apagada: true, inicio: [null, null, null], titulo: o.leyendo ? 'leyendo las tareas…' : 'nadie te debe nada: ninguna tarea espera a otro ni la hace otro' }));
    for (const g of ds) {
        const n = g.compromisos.length;
        const esperan = g.compromisos.filter(c => c.clase === 'espera').length;
        h.push(`<div class="grupo-esperando" data-persona="${esc(g.clave)}">`, seccion({
            clave: g.clave, titulo: g.nombre, cuenta: n, abierta: abierta(g.clave),
            ayuda: `lo que ${g.nombre} te debe: ${esperan ? `${esperan} esperan` : ''}${esperan && n - esperan ? ', ' : ''}${n - esperan ? `${n - esperan} delegadas` : ''}`,
            filas: () => g.compromisos.map(c => filas(c, g.clave, ahora)).join(''),
        }), '</div>');
    }
    h.push('<div id="esperando-vacio" class="vacio" hidden>nada calza</div></div>');
    return h;
}

/** Lo que dice el globo del título: cuántas y de cuántas personas. */
export function resumen(cs: Compromiso[]): string {
    const personas = deudores(cs).length;
    const esperan = cs.filter(c => c.clase === 'espera').length;
    return `${cs.length} que tiene otro (${esperan} esperan, ${cs.length - esperan} delegadas) · ${personas} ${personas === 1 ? 'persona' : 'personas'}`;
}

/** El plegado de cada persona se recuerda en el navegador. */
const memoria: Memoria = {
    get<T>(clave: string): T | undefined { try { return JSON.parse(localStorage.getItem(clave) ?? 'null') ?? undefined; } catch { return undefined; } },
    update(clave: string, valor: unknown) { try { localStorage.setItem(clave, JSON.stringify(valor)); } catch { /* sin almacén: dura lo que la página */ } return Promise.resolve(); },
};

export class PantallaEsperando implements Pantalla {
    readonly pantallas = ['esperando'] as const;
    /** se repinta con cada lectura del día: una que cerró otro, o que dejó de esperar, sale sola */
    readonly conReloj = ['esperando'] as const;
    private q = '';
    private filtro = '';
    private readonly plegado = new Plegado(() => memoria, 'telar.esperando.plegado');

    readonly acciones: Record<string, Accion> = {
        esperando: () => this.abrir(),
    };

    constructor(private readonly t: Tablero) {}

    /** Es una subpestaña de «tareas»: la barra marca esa fila. */
    pestanaMarcada(): string { return 'revisar'; }

    private async abrir(): Promise<void> {
        this.t.montar();
        this.t.ir('esperando');
        await this.t.diaLeido();
        if (this.t.pantalla === 'esperando') this.pintar();
    }

    pintar(): void {
        const d = this.t.dia();
        if (!d) return;
        const activo = document.activeElement as HTMLInputElement | null;
        const cursor = activo?.id === 'buscar-esperando' ? activo.selectionStart ?? 0 : -1;
        const cs = compromisos(pendientes(d));
        const leido = leidoProveedores();
        const hace = leido ? Math.round((Date.now() - leido) / 60000) : -1;
        this.t.teclas.clear();
        this.t.pintar(cuerpo(cs, k => this.plegado.abierta(k, true), { filtro: this.filtro, leyendo: !leido }),
            { ayuda: resumen(cs), leido: hace < 0 ? 'sin leer' : hace === 0 ? 'leídas recién' : `leídas hace ${hace} min` });
        this.montar(cursor);
    }

    /** Después de pintar: lo buscado otra vez, el buscador que filtra sin repintar, el filtro y el plegado de cada
     *  persona (se atienden aquí, antes que el dashboard: sus `data-accion` son de otras listas). */
    private montar(cursor: number): void {
        const raiz = document.getElementById('esperando');
        const b = document.getElementById('buscar-esperando') as HTMLInputElement | null;
        if (!raiz || !b) return;
        b.value = this.q;
        if (cursor >= 0) { b.focus(); b.setSelectionRange(cursor, cursor); }
        b.addEventListener('input', () => { this.q = b.value; this.aplicar(); });
        b.addEventListener('keydown', e => {
            if (e.key !== 'Escape') return;
            e.preventDefault();
            if (b.value) { b.value = ''; this.q = ''; this.aplicar(); } else b.blur();
        });
        raiz.addEventListener('click', e => {
            const t = e.target as HTMLElement;
            const op = t.closest<HTMLElement>('.filtros-op');
            if (op) {
                e.stopPropagation();
                const k = (op.dataset.id ?? '').replace(/^cuales:/, '');
                this.filtro = this.filtro === k ? '' : k;
                this.aplicar();
                return;
            }
            const cab = t.closest<HTMLElement>('.item.cabecera[data-accion="seccion"]');
            if (cab) {
                e.stopPropagation();
                this.plegado.alternar(cab.dataset.id ?? '');
                this.pintar();
            }
        });
        this.aplicar();
    }

    /** Esconde lo que no calza con lo buscado ni con el filtro, y pone las cuentas. */
    private aplicar(): void {
        const raiz = document.getElementById('esperando');
        if (!raiz) return;
        const partes = normalizar(this.q).split(/\s+/).filter(Boolean);
        const busca = (f: HTMLElement) => partes.every(p => (f.dataset.busca ?? '').includes(p));
        const deja = (f: HTMLElement, filtro = this.filtro) => !filtro || (filtro === 'vencida' ? f.dataset.vencida === '1' : f.dataset.clase === filtro);
        let n = 0;
        for (const g of raiz.querySelectorAll<HTMLElement>('.grupo-esperando')) {
            const suyas = [...g.querySelectorAll<HTMLElement>('.item.compromiso')];
            let vistas = 0;
            for (const f of suyas) {
                f.hidden = !busca(f) || !deja(f);
                if (!f.hidden && !f.classList.contains('compromiso-ultimo')) vistas += 1;
            }
            // una persona plegada sigue a la vista sin buscar nada; filtrando, solo si algo suyo calza
            const plegada = !g.querySelector('.item.compromiso');
            g.hidden = (partes.length > 0 || !!this.filtro) && (plegada ? !this.calzaPlegada(g.dataset.persona ?? '', partes) : vistas === 0);
            n += vistas;
        }
        marcarFiltros(raiz, 'cuales', this.filtro);
        // sin buscar, las cuentas de todas (también las de una persona plegada); buscando, las que calzan
        for (const op of raiz.querySelectorAll<HTMLElement>('.filtros-op')) {
            const k = (op.dataset.id ?? '').replace(/^cuales:/, '');
            contarFiltro(op, partes.length ? [...raiz.querySelectorAll<HTMLElement>('.item.compromiso:not(.compromiso-ultimo)')].filter(f => busca(f) && deja(f, k)).length
                : Number(raiz.dataset[`n${k[0].toUpperCase()}${k.slice(1)}`] ?? 0));
        }
        // todas, también las de una persona plegada (sus filas no están en la página)
        const total = Number(raiz.dataset.total ?? 0);
        const cuenta = document.getElementById('esperando-cuenta');
        if (cuenta) cuenta.textContent = partes.length || this.filtro ? `${n} de ${total}` : '';
        const vacio = document.getElementById('esperando-vacio');
        if (vacio) vacio.hidden = n > 0 || (!partes.length && !this.filtro) || total === 0;
    }

    /** Una persona plegada no tiene sus filas en la página: calza si su nombre calza con lo buscado y no hay filtro. */
    private calzaPlegada(clave: string, partes: string[]): boolean {
        return !this.filtro && partes.every(p => clave.includes(p));
    }
}
