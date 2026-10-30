// Las acciones sobre una tarea —llevarla a su hilo, marcarla hecha, reagendarla, asignarla,
// la estrella, compartirla— que usa el dashboard. Lo que piden a la interfaz va a la página (web/ui.ts).
// Abajo, PantallaTareas: la pestaña «tareas», la ficha de una tarea y las pestañas de proveedor.

import { C, I } from '../../web/iconos';
import * as ui from '../../web/ui';
import type { Opcion } from '../../web/ui';
import * as cli from '../../cli';
import { PRIORIDAD, esc, limpiarMd, normalizar, recuadro, volver } from '../../estilo';
import { modelo } from '../../modelo';
import { Dia, datosDueno, filtroAreas, filtroDuenos, leidoProveedores, olvidarDia, pendientes, pista, plazo, seccion, yo } from './dia';
import { type Accion, type Pantalla, type Tablero, abrirEnlace } from './pantalla';

/** Las acciones de la ficha que siempre se hacen donde se ve lo que cambian, como íconos junto al título; las del
 *  subtítulo salen de la lista solo si `subtituloFicha` las pudo poner ahí (ver `pintarFicha`). */
const ICONOS = ['estrella', 'equipo'];

/** Cómo se nombra una tarea en lo que se le pregunta a la persona: el título de su ficha ya empieza con el id
 *  («T309 · …»); si no, el id va delante. */
function nombreTarea(id: string, titulo = ''): string {
    return titulo.startsWith(id) ? titulo : `${id} ${titulo}`.trim();
}

/** `texto` y `enviar`: lo que se le dice al agente del hilo, y mandarlo (no solo escribirlo). Con `ir: false` no
 *  se va a la terminal al terminar (foco sigue con la siguiente). Devuelve el hilo adonde fue, o undefined. */
export async function llevarPendiente(ref: string, nuevo: boolean, proveedor = '', texto = '', enviar = false,
    o: { ir?: boolean; fila?: cli.JsonFila } = {}): Promise<string | undefined> {
    // buscar el hilo, retomarlo o encargárselo a un agente del servidor toma unos segundos:
    // una notificación lo dice mientras tanto, para que el Enter no parezca perdido
    const r = await ui.progreso({ titulo: `telar: llevando ${ref} a su hilo…`, discreto: o.ir === false },
        () => cli.pendiente(ref, nuevo, proveedor, texto, enviar, o.fila));
    if (!r.datos) {
        void ui.aviso(`telar: ${r.error ?? `no pude llevar «${ref}»`}`);
        return undefined;
    }
    await modelo.sondear();
    if (o.ir !== false) void ui.mostrarTerminal();
    return (r.datos as { destino?: string }).destino || ref;
}

/** El ✓ de la lista: corre la acción que el proveedor declara con `rol: "hecha"`, sin abrir
 *  la ficha ni preguntar (se deshace reabriéndola). Si el proveedor no declara una, lo dice. */
/** Una fecha nueva para una tarea: las de siempre a un clic, u otra escrita a mano. Devuelve
 *  AAAA-MM-DD (o +Nd, que el proveedor cuenta desde su fecha), o undefined si se cancela. */
export async function elegirFecha(titulo: string, o: { conHoy?: boolean } = {}): Promise<string | undefined> {
    const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const desde = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d; };
    const dias = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const hoy = new Date();
    const lunes = desde(((8 - hoy.getDay()) % 7) || 7);
    const finDeMes = new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0);
    const opciones: (Opcion & { valor: string })[] = [
        // «hoy»: en foco, una vencida que sí va hoy (si no, una fecha de verdad)
        ...(o.conHoy ? [{ label: 'hoy', description: `${dias[hoy.getDay()]} ${iso(hoy)}`, valor: iso(hoy) }] : []),
        { label: 'mañana', description: `${dias[desde(1).getDay()]} ${iso(desde(1))}`, valor: iso(desde(1)) },
        { label: 'pasado mañana', description: `${dias[desde(2).getDay()]} ${iso(desde(2))}`, valor: iso(desde(2)) },
        { label: 'el próximo lunes', description: iso(lunes), valor: iso(lunes) },
        { label: 'en una semana', description: `${dias[desde(7).getDay()]} ${iso(desde(7))}`, valor: iso(desde(7)) },
        { label: 'fin de mes', description: `${dias[finDeMes.getDay()]} ${iso(finDeMes)}`, valor: iso(finDeMes) },
        { label: 'otra fecha…', description: 'AAAA-MM-DD, 15-10, 15-oct o +10d', valor: '' },
    ];
    const elegida = await ui.elegir(opciones, { titulo: `Nueva fecha · ${titulo}`, placeholder: 'para cuándo queda' });
    if (!elegida) return undefined;
    if (elegida.valor) return elegida.valor;
    const meses = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const leer = (t: string): string => {
        t = t.trim().toLowerCase();
        if (/^\+\d+d$/.test(t) || /^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
        const m = t.match(/^(\d{1,2})[-/ ](\d{1,2}|[a-zé]{3,})$/);
        if (!m) return '';
        const mes = /^\d+$/.test(m[2]) ? Number(m[2]) : meses.indexOf(m[2].slice(0, 3)) + 1;
        if (mes < 1 || mes > 12) return '';
        let d = new Date(hoy.getFullYear(), mes - 1, Number(m[1]));
        if (d.getDate() !== Number(m[1])) return '';  // un día que ese mes no tiene (31-feb)
        if (d < new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate())) d = new Date(hoy.getFullYear() + 1, mes - 1, Number(m[1]));
        return iso(d);
    };
    const escrita = await ui.campo({ titulo: `Nueva fecha · ${titulo}`, ayuda: 'AAAA-MM-DD, 15-10, 15-oct o +10d',
        validar: t => (t.trim() && !leer(t) ? 'no entiendo esa fecha' : undefined) });
    return escrita?.trim() ? leer(escrita) || undefined : undefined;
}

/** Lo que dice de `rol` el subtítulo de la ficha de una tarea («activa · P1 · vence … · espera a Ana · la hace
 *  Leo»), sin la palabra de adelante: la prioridad, a quién espera, quién la hace. '' si no lo dice. */
function enSubtitulo(subtitulo: string, rol: string): string {
    const partes = subtitulo.split(' · ');
    if (rol === 'prioridad') return partes.find(x => /^P\d$/.test(x)) ?? '';
    const antes = ({ espera: 'espera a ', dueno: 'la hace ' } as Record<string, string>)[rol];
    const x = antes ? partes.find(y => y.startsWith(antes)) : undefined;
    return x ? x.slice(antes.length) : '';
}

/** El valor de una acción que se elige en vez de escribirse, según su `rol`: la fecha en el calendario, quién la
 *  hace o a quién espera de la lista de personas, la prioridad de las que ofrece el proveedor. Lo de ahora sale
 *  del subtítulo de la ficha. undefined si se cancela; null si esa acción no tiene selector. */
async function elegirPorRol(a: cli.JsonAccionPagina, titulo: string, subtitulo: string): Promise<string | undefined | null> {
    const actual = enSubtitulo(subtitulo, a.rol ?? '');
    switch (a.rol) {
        case 'fecha': return elegirFecha(titulo);
        case 'dueno': return elegirDueno(titulo, actual, a.opciones ?? [], yo.persona);
        case 'espera': return elegirEspera(titulo, actual, a.opciones ?? []);
        case 'prioridad': return elegirPrioridad(titulo, actual, a.opciones ?? []);
        default: return null;
    }
}

/** Reagendar una tarea desde la lista: la acción con rol «fecha» de su proveedor, con la fecha elegida. */
export async function reagendar(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'fecha') ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar la fecha`}`);
        return false;
    }
    const fecha = await elegirFecha(nombreTarea(id, ficha.datos?.titulo));
    if (!fecha) return false;
    const r = await cli.accionTarea(id, proveedor, k, fecha);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude mover ${id}`}`); return false; }
    ui.estado(`${id} → ${fecha}`, 5000);
    return true;
}

/** Elegir quién hace una tarea: la persona (que es lo de siempre, sin asignar), ella misma asignada a
 *  propósito, el equipo que ofrece el proveedor, u otro nombre escrito. Devuelve el texto para la
 *  acción («none» para dejarla sin asignar), o undefined si se cancela. */
export async function elegirDueno(titulo: string, actual: string, opciones: string[], persona: string,
    vineta = false): Promise<string | undefined> {
    type Item = Opcion & { valor?: string };
    const yo = persona ? persona[0].toUpperCase() + persona.slice(1) : 'yo';
    const items: Item[] = [
        // una viñeta de un documento sin responsable no es de nadie; una tarea sin dueño es de la persona
        vineta ? { label: 'Sin responsable', description: 'la viñeta no dice quién la hace', valor: 'none' }
            : { label: `${yo} (sin asignar)`, description: 'lo de siempre: una tarea sin dueño es tuya', valor: 'none' },
        { label: yo, description: 'asignada a ti a propósito', valor: yo },
        { label: '', separador: true },
        ...opciones.filter(o => o.toLowerCase() !== yo.toLowerCase()).map(o => ({ label: o, valor: o })),
        { label: '', separador: true },
        { label: 'otra persona…', valor: '' },
    ];
    for (const it of items) if (it.valor !== undefined && it.valor && (it.valor === actual || (it.valor === 'none' && !actual))) it.description = `${it.description ?? ''} ← ahora`.trim();
    const e = await ui.elegir(items, { titulo: titulo, placeholder: 'quién hace esta tarea' });
    if (!e) return undefined;
    if (e.valor) return e.valor;
    const escrito = await ui.campo({ titulo: titulo, ayuda: 'el nombre de quien la hace' });
    return escrito?.trim() || undefined;
}

/** A quién espera una tarea: nadie (deja de esperar, y vuelve a ser de la persona), alguien del equipo que ofrece
 *  el proveedor, u otro nombre escrito. Devuelve el texto para la acción («none»: nadie), o undefined si se cancela. */
async function elegirEspera(titulo: string, actual: string, opciones: string[]): Promise<string | undefined> {
    type Item = Opcion & { valor?: string };
    const items: Item[] = [
        { label: 'nadie', description: actual ? 'deja de esperar: vuelve a ser tuya' : 'no espera a nadie ← ahora', valor: 'none' },
        { label: '', separador: true },
        ...opciones.map(o => ({ label: o, valor: o, description: o === actual ? '← ahora' : undefined })),
        { label: '', separador: true },
        { label: 'otra persona…', valor: '' },
    ];
    const e = await ui.elegir(items, { titulo, placeholder: 'a quién espera esta tarea' });
    if (!e) return undefined;
    if (e.valor) return e.valor;
    const escrito = await ui.campo({ titulo, ayuda: 'a quién espera' });
    return escrito?.trim() || undefined;
}

/** La prioridad de una tarea, de las que ofrece el proveedor, de la más alta a la más baja (P0 … P3). */
async function elegirPrioridad(titulo: string, actual: string, opciones: string[]): Promise<string | undefined> {
    const items = opciones.map((o, i) => ({
        label: o, valor: o,
        description: [i === 0 ? 'la más alta' : i === opciones.length - 1 ? 'la más baja' : '', o === actual ? '← ahora' : ''].filter(Boolean).join(' '),
    }));
    return (await ui.elegir(items, { titulo, placeholder: 'qué prioridad tiene' }))?.valor;
}

/** El responsable de una tarea, desde su fila: la acción del proveedor con `rol: dueno`. */
export async function asignar(valor: string, actual: string, persona: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const acciones = ficha.datos?.acciones ?? [];
    const k = acciones.findIndex(a => a.rol === 'dueno');
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar el responsable`}`);
        return false;
    }
    const quien = await elegirDueno(nombreTarea(id, ficha.datos?.titulo), actual, acciones[k].opciones ?? [], persona);
    if (!quien) return false;
    const r = await cli.accionTarea(id, proveedor, k, quien);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude asignar ${id}`}`); return false; }
    ui.estado(`${id} → ${quien === 'none' ? 'sin asignar' : quien}`, 5000);
    return true;
}

/** Correr la acción de una tarea que tiene ese `rol` (estrella, equipo…) sin abrir su ficha. */
async function alternarPorRol(valor: string, rol: string, queEs: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === rol) ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece ${queEs}`}`);
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k, '');
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude cambiar ${queEs} de ${id}`}`); return false; }
    ui.estado(`${id}: ${ficha.datos?.acciones?.[k].nombre ?? queEs}`, 4000);
    return true;
}

/** La prioridad de una tarea en su fila, con los íconos de la prioridad de los hilos (● alta, ◐ media, ○ baja; P0, la
 *  urgente, es ● en rojo). Con ficha es un botón: el clic la baja un nivel (● → ◐ → ○ → ●); P0 se pone desde ⋯. */
export function iconoPrioridad(fila: cli.JsonFila, ref: string, ficha: boolean): string {
    const n = fila.prioridad ?? null;
    const icono = n === null ? '·' : n === 0 ? '●' : PRIORIDAD[n] ?? '·';
    const nombre = n === null ? 'sin prioridad' : `P${n} · ${['urgente', 'alta', 'media', 'baja'][n]}`;
    if (!ficha) return `<span class="pri pt${n ?? ''}"${n === null ? '' : ` title="${esc(nombre)}"`}>${n === null ? '' : icono}</span>`;
    const valor = esc(JSON.stringify([fila.proveedor, fila.id || ref, n ?? '']));
    return `<span class="pri pt${n ?? ''} clic" data-accion="prioridad-tarea" data-valor="${valor}"`
        + ` title="${esc(`${nombre}\nclic: ${n === null ? 'P1 alta' : `P${siguientePrioridad(n)} ${['', 'alta', 'media', 'baja'][siguientePrioridad(n)]}`}${n === 0 ? '' : '\nP0 (urgente): desde ⋯'}`)}">${icono}</span>`;
}

/** El clic sobre la prioridad: un nivel más abajo, y de la más baja vuelve a la alta. P0 baja a P1. */
const siguientePrioridad = (n: number | null): number => n === null || n >= 3 ? 1 : n + 1;

/** Cambiar la prioridad desde la fila: la acción del proveedor con `rol: prioridad`, en un viaje. */
export async function cambiarPrioridad(valor: string): Promise<number | null> {
    const [proveedor, id, actual] = JSON.parse(valor) as [string, string, number | ''];
    const nueva = siguientePrioridad(actual === '' ? null : actual);
    const r = await cli.accionPorRol(id, proveedor, 'prioridad', `P${nueva}`);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude cambiar la prioridad de ${id}`}`); return null; }
    ui.estado(`${id} → P${nueva} ${['', 'alta', 'media', 'baja'][nueva]}`, 3000);
    return nueva;
}

/** Poner o quitar la estrella de una tarea: la acción del proveedor con `rol: estrella`. */
export const alternarEstrella = (valor: string) => alternarPorRol(valor, 'estrella', 'la estrella');

/** Compartir una tarea con el equipo, o dejar de hacerlo: la acción con `rol: equipo` (`telar equipo`). */
export async function alternarEquipo(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // la acción dice qué hará: «○ compartir…» la comparte, «◉ dejar de compartir…» la deja
    const antes = (await cli.tarea(id, proveedor)).datos?.acciones?.find(a => a.rol === 'equipo')?.nombre ?? '';
    if (!await alternarPorRol(valor, 'equipo', 'compartir con el equipo')) return false;
    const compartida = antes.startsWith('○');
    void ui.info(compartida
        ? `telar: ${id} ahora la ve el equipo (título, estado, prioridad y fecha); pueden sugerir subirla.`
        : `telar: ${id} dejó de compartirse con el equipo.`);
    return true;
}

export async function marcarHecha(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // un viaje: la acción por su rol. Un telar de antes (el de otra máquina sin actualizar) no
    // conoce --rol: entonces, como siempre, la ficha primero para saber su número
    const directo = await ui.progreso({ discreto: true, titulo: `✓ ${id}…` },
        () => cli.accionPorRol(id, proveedor, 'hecha'));
    if (directo.datos) {
        olvidarDia();
        ui.estado(`✓ ${id} hecha`, 5000);
        return true;
    }
    if (!/--rol|unrecognized|argumentos/i.test(directo.error ?? '')) {
        void ui.aviso(`telar: ${directo.error ?? `no pude marcar ${id}`}`);
        olvidarDia();
        return false;
    }
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === 'hecha') ?? -1;
    if (k < 0) {
        void ui.aviso(`telar: ${ficha.error ?? `${id} no se puede marcar hecha desde la lista: ábrela`}`);
        olvidarDia();
        return false;
    }
    const r = await cli.accionTarea(id, proveedor, k);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude marcar ${id}`}`); return false; }
    ui.estado(`✓ ${id} hecha`, 5000);
    return true;
}

/** La pestaña «tareas», la ficha de una tarea y las pestañas de proveedor (un feed): la lista, la ficha abierta y
 *  las propuestas decididas en esta pasada. También las acciones de una fila de tarea, donde sea que se muestre. */
export class PantallaTareas implements Pantalla {
    readonly pantallas = ['revisar', 'tarea', 'pestana'] as const;
    /** la ficha no: lo escrito en ella se perdería cada minuto */
    readonly conReloj = ['revisar', 'pestana'] as const;
    /** de qué pestaña se abrió la ficha: ⎋ vuelve ahí, y ahí queda marcada. `pestana:<n>` es
     *  la de un proveedor con pestaña propia (un feed); `bloque:<clave>:<ítem>`, un ítem de un bloque */
    private fichaDesde = 'revisar';
    /** con `fichaDesde` en 'fuera': la ficha se abrió desde otra vista de la página (la dirección de una tarea en una
     *  conversación), y «‹» vuelve allá */
    private fuera: { nombre: string; ir: () => void } | null = null;
    /** la pestaña de proveedor abierta (`pestana` del proveedor: «leer») */
    private pestana = '';
    /** fichas ya pedidas: una pestaña de proveedor puede estar lejos (el feed se pide por ssh
     *  a otro continente, ~0,5 s cada una), así que se piden antes de que se abran */
    private readonly fichas = new Map<string, { pagina: cli.JsonPagina; hora: number }>();
    /** la ficha abierta: de qué proveedor, su id y su ref (con la que se lleva al hilo) */
    private ficha?: { proveedor: string; id: string; ref: string; pagina?: cli.JsonPagina; aviso?: string };
    /** las propuestas ya decididas en esta pasada: ← → las saltan aunque el día no se haya releído (los bloques
     *  tampoco las muestran vivas) */
    readonly decididas = new Set<string>();
    /** lo que se le estaba escribiendo a Claude sobre cada tarea y no se mandó, y a quién si ya se intentó (ver
     *  `escribirA`) */
    private readonly borradores = new Map<string, { texto: string; destino?: string }>();

    readonly acciones: Record<string, Accion> = {
        'revisar': () => this.abrirRevisar(),
        'pestana': v => v && this.abrirPestana(v),
        'tarea': (v, m) => {
            if (!v) return;
            // ⌘-clic: como antes, al hilo donde se trabaja; clic: la ficha
            if (m.nuevo) { const [proveedor, , ref] = JSON.parse(v) as string[]; return llevarPendiente(ref, false, proveedor); }
            return this.abrirTarea(v);
        },
        'volver-ficha': () => this.volver(),
        'accion-tarea': v => v && this.accionTarea(Number(v)),
        'tarea-principal': () => {
            const i = (this.ficha?.pagina?.acciones ?? []).findIndex(a => a.principal);
            if (i >= 0) return this.accionTarea(i);
        },
        'tarea-siguiente': () => this.otraPropuesta(1),
        'tarea-anterior': () => this.otraPropuesta(-1),
        'menu-tarea': (v, m) => v && this.menuTarea(v, m.donde),
        // las de una fila, sin abrir la ficha
        'pendiente': (v, m) => v && llevarPendiente(v, !!m.nuevo),
        'hilo-fila': v => {
            if (!v) return;
            const [proveedor, ref, id] = JSON.parse(v) as string[];
            return llevarPendiente(ref, false, proveedor, id ? `/tarea ${id}` : '', !!id);
        },
        'hecha-fila': async v => {
            if (!v) return;
            // la fila ya está tachada (lo hace la vista al clic); hecha, sale de la lista al tiro y
            // la lista se relee por detrás (son ~6 s que no hay por qué esperar)
            if (await marcarHecha(v)) this.decididas.add((JSON.parse(v) as string[])[1]);
            this.t.render();
            void this.t.actualizar(true);
        },
        'hecha-vineta': async v => {
            if (!v) return;
            const [ref, texto] = JSON.parse(v) as string[];
            const r = await cli.vineta(ref, texto, ['--hecho']);
            if (!r.datos) void ui.aviso(`telar: ${r.error ?? 'no pude marcarla'}`);
            else { ui.estado(`✓ ${texto.slice(0, 60)}`, 5000); olvidarDia(); void this.t.actualizar(true); }
        },
        'hecha': async v => {
            if (!v) return;
            await marcarHecha(v);
            void this.t.actualizar(true);
        },
        'reagendar': async v => { if (v && await reagendar(v)) await this.releer(); },
        'equipo-tarea': async v => { if (v && await alternarEquipo(v)) await this.releer(); },
        'estrella-tarea': async v => { if (v && await alternarEstrella(v)) await this.releer(); },
        'prioridad-tarea': async v => { if (v && await cambiarPrioridad(v) !== null) await this.releer(); },
        'dueno-tarea': async v => {
            if (!v) return;
            const [proveedor, id, ref, actual] = JSON.parse(v) as string[];
            if (await asignar(JSON.stringify([proveedor, id, ref]), actual ?? '', yo.persona)) await this.releer();
        },
    };

    constructor(private readonly t: Tablero) {}

    pintar(): void {
        if (this.t.pantalla === 'revisar') this.pintarLista();
        else if (this.t.pantalla === 'pestana') this.pintarPestana();
        else this.pintarFicha();
    }

    /** Con la ficha abierta se marca la pestaña de donde se abrió; con un feed, el suyo. */
    pestanaMarcada(): string {
        if (this.t.pantalla === 'tarea') return this.fichaDesde.replace(/^(bloque:[^:]*):.*$/, '$1');
        if (this.t.pantalla === 'pestana') return `pestana:${this.pestana}`;
        return this.t.pantalla;
    }

    /** Releer el día después de cambiar una tarea desde su fila, y repintar la lista si es lo que se ve. */
    private async releer(): Promise<void> {
        await this.t.actualizar(true);
        if (this.t.pantalla === 'revisar') this.pintarLista();
    }

    /** ⎋ en la ficha: a la lista, el feed o el ítem de donde se abrió, o a la vista de afuera; si no, a «ahora». */
    private async volver(): Promise<void> {
        if (this.fichaDesde === 'fuera' && this.fuera) this.fuera.ir();
        else if (this.fichaDesde === 'revisar') await this.abrirRevisar();
        else if (this.fichaDesde.startsWith('pestana:')) await this.abrirPestana(this.fichaDesde.slice(8));
        else if (this.fichaDesde.startsWith('bloque:')) {
            const [, clave, item] = this.fichaDesde.split(':');
            await this.t.accion(item === '' ? 'bloque' : 'ver-item', item === '' ? clave : `${clave}:${item}`);
        }
        else await this.t.accion('ahora');
    }

    /** La ficha de una tarea: leerla y decidir sin abrir un agente. La arma el proveedor
     *  (`telar tarea`): su propuesta arriba, el contexto, la historia y los botones. `desde`: la vista de afuera
     *  del dashboard de donde se abrió (una conversación), adonde vuelve «‹». */
    async abrirTarea(valor: string, desde?: { nombre: string; ir: () => void }): Promise<void> {
        const [proveedor, id, ref] = JSON.parse(valor) as string[];
        if (this.fichaDesde === 'fuera') this.fichaDesde = 'revisar';
        // desde la barra el dashboard puede existir tapado por otra pestaña: se trae al frente,
        // en su columna y sin recargar (abrir() la movería a la activa y pediría el día de nuevo)
        this.t.alFrente();
        if (this.t.pantalla === 'revisar') this.fichaDesde = 'revisar';
        // desde un ítem de un bloque (un correo): al cerrar la ficha se vuelve a ese ítem
        if (this.t.pantalla === 'bloque') this.fichaDesde = `bloque:${this.t.bloqueAbierto()}`;
        if (this.t.pantalla === 'pestana' || this.fichaDesde.startsWith('pestana:')) this.fichaDesde = `pestana:${this.pestana}`;
        if (desde) { this.fichaDesde = 'fuera'; this.fuera = desde; }
        this.t.ir('tarea');
        this.ficha = { proveedor, id, ref };
        const guardada = this.fichas.get(`${proveedor}:${id}`);
        if (guardada && Date.now() - guardada.hora < 5 * 60 * 1000) {
            this.ficha.pagina = guardada.pagina;
            this.pintarFicha();
            void this.precargar();
            return;
        }
        this.t.pintar(this.marcoFicha([`<div class="subcab"><b>${esc(id)}</b></div>`, '<div class="fila dim">leyendo…</div>']));
        const r = await cli.tarea(id, proveedor);
        if (r.datos) this.fichas.set(`${proveedor}:${id}`, { pagina: r.datos, hora: Date.now() });
        if (this.t.pantalla !== 'tarea' || this.ficha?.id !== id) return;
        this.ficha.pagina = r.datos;
        this.ficha.aviso = r.datos ? '' : (r.error ?? 'la ficha no contestó');
        this.pintarFicha();
        void this.precargar();
    }

    /** Pide por adelantado las fichas de la lista que se está recorriendo (hasta 10, cuatro a
     *  la vez): al apretar → la siguiente ya está. Las que ya se tienen no se vuelven a pedir. */
    private async precargar(): Promise<void> {
        const faltan = this.propuestas()
            .filter(p => { const g = this.fichas.get(`${p.proveedor}:${p.id}`); return !g || Date.now() - g.hora > 5 * 60 * 1000; })
            .slice(0, 10);
        const pedir = async () => {
            for (let p = faltan.shift(); p; p = faltan.shift()) {
                const r = await cli.tarea(p.id, p.proveedor);
                if (r.datos) this.fichas.set(`${p.proveedor}:${p.id}`, { pagina: r.datos, hora: Date.now() });
            }
        };
        await Promise.all([pedir(), pedir(), pedir(), pedir()]);
    }

    /** La pestaña «tareas»: todas, con lo que un agente dejó para decidir arriba (◆), y filtros para
     *  ver solo eso, lo vencido, lo de la semana… Un clic abre la ficha; ← → pasa de una propuesta a
     *  otra y al decidir salta a la siguiente. */
    async abrirRevisar(): Promise<void> {
        this.t.montar();
        this.t.ir('revisar');
        this.fichaDesde = 'revisar';
        await this.t.diaLeido();
        this.pintarLista();
        // los nombres de los proyectos (para la columna): si no estaban, se piden y se repinta
        if (await this.t.proyectos.asegurar() && this.t.pantalla === 'revisar') this.pintarLista();
    }

    private pintarLista(): void {
        const d = this.t.dia();
        if (!d) return;
        this.t.teclas.clear();
        this.t.pintar(this.tablaTareas(d));
    }

    /** Una fila de tarea, la misma en «tareas» y donde se muestren tareas sueltas (un correo y las
     *  suyas): código, estrella, proyecto, responsable, texto, fecha, ✓ ◉ ▶ y ⋯. `rev`: espera una
     *  decisión; `semana`: va en «esta semana». */
    filaTarea(p: ReturnType<typeof pendientes>[number], rev: boolean, semana: boolean): string {
        const esRev = (_p: unknown) => rev;
        const deLaSemana = (_p: unknown) => semana;
        const [todo] = (p.fila.avance ?? '').split(' ');
        const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
        const ficha = !!p.fila.ficha;
        const proy = this.t.proyectos.deFila(p.fila);
        // el proyecto en pocas letras: su cliente, o su nombre; entero en el globo. Un cliente que es la casa
        // misma (`internos` del perfil: el servidor lo marca `interno`) no dice nada: ahí va el nombre sin él
        const interno = !proy?.cliente || (proy.interno ?? false);
        const proyCorto = !proy ? '' : !interno ? proy.cliente!
            : proy.cliente && proy.nombre.startsWith(proy.cliente) ? proy.nombre.slice(proy.cliente.length).replace(/^\s*·\s*/, '') : proy.nombre;
        const buscable = normalizar([p.ref, p.texto, p.hilo, p.fila.ruta ?? '', p.fila.proyecto ?? '', proy?.nombre ?? '', p.fila.avance ?? '', p.fila.dueno ?? ''].join(' '));
        const accion = ficha ? `data-accion="tarea" data-valor="${valor}" title="clic: leerla y decidir"`
            : `data-accion="pendiente" data-valor="${esc(p.ref)}" title="clic: ${p.hilo ? `llevarlo a «${esc(p.hilo)}»` : 'abrir un hilo donde trabajarlo'}"`;
        const dueno = p.fila.dueno ?? '';
        const persona = yo.persona ? yo.persona[0].toUpperCase() + yo.persona.slice(1) : 'tú';
        // el responsable: el dueño, o la persona en gris (es suya porque nadie la tomó); con ficha, un clic lo cambia
        // una viñeta de un documento: su responsable si lo dice (@owner(…) o «@Nombre:»), sin cambiarlo desde aquí
        const resp = !ficha ? (dueno ? `<span class="resp fijo" title="${esc(`responsable: ${dueno}\n(lo dice el documento)`)}">${esc(dueno)}</span>`
                : '<span class="resp dim" title="la viñeta no dice quién la hace">sin responsable</span>')
            : `<span class="resp${dueno ? '' : ' defecto'}" data-accion="dueno-tarea" data-valor="${esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref, dueno]))}"`
                + ` title="${esc(dueno ? `responsable: ${dueno}\nclic: cambiarlo` : `sin asignar: es tuya por defecto\nclic: asignarla`)}">${esc(dueno || persona)}</span>`;
        return `<div class="tarea${p.enCurso ? ' encurso' : ''}" ${accion} data-area="${esc(p.fila.area ?? '')}"${datosDueno(dueno, ficha || !!p.fila.proveedor)}`
            + ` data-rev="${esRev(p) ? 1 : 0}" data-dias="${p.dias ?? ''}" data-encurso="${p.enCurso ? 1 : 0}" data-texto="${esc(buscable)}"`
            + ` data-pri="${p.fila.prioridad ?? ''}" data-sem="${deLaSemana(p) ? 1 : 0}" data-estrella="${p.fila.estrella ? 1 : 0}" data-est="${p.fila.estrella ? 'a' : ''}"`
            + ` data-orden="${p.urgencia}" data-ref="${esc(p.ref)}" data-alfa="${esc(normalizar(limpiarMd(p.texto)))}"`
            + ` data-proy="${esc(normalizar(proyCorto))}" data-resp="${esc(normalizar(dueno || (ficha ? persona : '')))}">`
            + `<span class="id">${esc(ficha || p.fila.proveedor ? p.ref : '·')}</span>`
            // la estrella: con ficha, un clic la pone o la quita (la guarda el proveedor, en la tarea)
            + (ficha ? `<span class="estr${p.fila.estrella ? ' on' : ''}" data-accion="estrella-tarea" data-valor="${valor}" title="${p.fila.estrella ? 'quitar la estrella' : 'marcar con estrella: va siempre en «esta semana»'}">${p.fila.estrella ? '★' : '☆'}</span>` : '<span></span>')
            + iconoPrioridad(p.fila, p.ref, ficha)
            + (proy ? `<span class="proy-t" data-accion="proy-ir" data-valor="${esc(proy.ruta)}" title="${esc(`${proy.nombre}\nclic: verlo en proyectos`)}">${esc(proyCorto)}</span>`
                : '<span class="proy-t dim">—</span>') + resp
            + `<span class="desc">${esRev(p) ? `<span class="av av-${esc(p.avance)}">${esc(todo.replace(':', ' '))}</span>` : ''}`
            + `${esc(limpiarMd(p.texto))}</span>`
            // el atraso es un botón: reagendar lo que venció sin abrir la ficha
            + `<span class="meta">${ficha ? `<span class="plazo-clic" data-accion="reagendar" data-valor="${valor}" title="clic: nueva fecha">${p.dias === null ? '<span class="dim">fecha</span>' : plazo(p.dias)}</span>` : plazo(p.dias)}`
            // las acciones de la tarea sin abrir la ficha: cerrar, nota, esperar… directo, sin la IA
            + `<span class="destino"></span>${this.rapidas(p.fila, p.ref, p.texto, valor, ficha)}${ficha ? `<span class="menu-fila" data-accion="menu-tarea" data-valor="${valor}" title="acciones de esta tarea">⋯</span>`
                : `<span class="menu-fila" data-accion="menu-vineta" data-valor="${esc(JSON.stringify([p.ref, p.texto, p.hilo, dueno]))}" title="acciones de este pendiente">⋯</span>`}</span></div>`;
    }

    /** Las acciones de todos los días, a un clic, antes del ⋯: ✓ marcarla hecha, ◉/○ compartirla con
     *  el equipo (solo una tarea con ficha, y si hay equipo) y ▶ llevarla a un hilo. En una viñeta de
     *  un README, ✓ marca su casilla. */
    private rapidas(fila: cli.JsonFila, ref: string, texto: string, valor: string, ficha: boolean): string {
        const compartida = !!fila.etiquetas?.includes('equipo');
        const hecha = ficha ? `<span class="rap ok" data-accion="hecha-fila" data-valor="${valor}" title="marcarla hecha">✓</span>`
            : !fila.proveedor ? `<span class="rap ok" data-accion="hecha-vineta" data-valor="${esc(JSON.stringify([ref, texto]))}" title="marcarla hecha: [ ] → [x] en su documento">✓</span>`
            : '<span class="rap"></span>';
        const eq = ficha && modelo.equipoRemoto
            ? `<span class="rap eq${compartida ? ' on' : ''}" data-accion="equipo-tarea" data-valor="${valor}" title="${compartida ? 'compartida con el equipo: clic para dejar de compartirla' : 'compartirla con el equipo (verán título, estado y prioridad; pueden sugerir subirla)'}">${compartida ? '◉' : '○'}</span>`
            : '<span class="rap"></span>';
        // una tarea con ficha va a su hilo (el de su proyecto, o el agente general) con /tarea <id>,
        // enviado: el agente la empieza con su contexto cargado. Una casilla de un README, escrita
        const hilo = `<span class="rap ir" data-accion="hilo-fila" data-valor="${esc(JSON.stringify([fila.proveedor, ref, ficha ? fila.id || ref : '']))}"`
            + ` title="${ficha ? `trabajarla: /tarea ${esc(fila.id || ref)} en ${fila.hilo ? `«${esc(fila.hilo)}»` : 'su hilo'}` : fila.hilo ? `llevarla a «${esc(fila.hilo)}»` : 'abrirla en un hilo'}">▶</span>`;
        return `<span class="rapidas">${hecha}${eq}${hilo}</span>`;
    }

    /** La tabla de tareas: la de la pestaña «tareas» y la de «hoy» son la misma (filtros, columnas,
     *  orden, ⋯). Lo que se elija en una (el modo, lo buscado, el orden) se ve igual en la otra. */
    private tablaTareas(d: Dia): string[] {
        const lista = pendientes(d).filter(p => !this.decididas.has(p.fila.id || p.ref));
        const esRev = (p: (typeof lista)[number]) => !!p.avance && !!p.fila.ficha;
        const cuenta = (f: (p: (typeof lista)[number]) => boolean) => lista.filter(f).length;
        // cada filtro con su cuenta: lo que decide qué mirar es cuánto hay
        // «esta semana», lo que se ve de entrada: lo vencido o que vence en 7 días, lo destacado (P0 o con
        // estrella) y lo que espera una decisión con fecha en 14 días. Lo demás, detrás de «ver todas»
        const deLaSemana = (p: (typeof lista)[number]) => (p.dias !== null && p.dias <= 7) || !!p.fila.destacada
            || (esRev(p) && p.dias !== null && p.dias <= 14);
        const modos: [string, string, number][] = [
            ['semana', 'esta semana', cuenta(deLaSemana)], ['todas', 'todas', lista.length], ['revisar', '◆ por revisar', cuenta(esRev)],
            ['vencidas', 'vencidas', cuenta(p => p.dias !== null && p.dias < 0)],
            ['estrella', '★', cuenta(p => !!p.fila.estrella)],
            ['encurso', 'en curso', cuenta(p => p.enCurso)], ['sinfecha', 'sin fecha', cuenta(p => p.dias === null)],
        ];
        // cuándo se leyeron: el proveedor se consulta solo cada 5 minutos, y «actualizar» lo fuerza ya
        const leido = leidoProveedores();
        const hace = leido ? Math.round((Date.now() - leido) / 60000) : -1;
        const actualizar = `<a data-accion="refrescar" title="volver a leer las tareas ahora (también r)">↻ actualizar</a>`
            + `<span class="dim"> · ${hace < 0 ? 'sin leer' : hace === 0 ? 'leídas recién' : `leídas hace ${hace} min`}</span>`;
        const h = ['<div id="revisar">', seccion('tareas', 'cian', String(lista.length), actualizar),
            '<div class="titulo-tareas"><span class="modos">'
            + modos.map(([k, n, c]) => `<button data-modo-t="${k}"${c ? '' : ' class="vacio-m"'}>${esc(n)} ${c}</button>`).join('')
            + `<input id="buscar-t" type="text" placeholder="/ buscar" spellcheck="false" autocomplete="off"><span id="tareas-t-cuenta"></span></span></div>`,
            filtroAreas(lista.map(p => p.fila.area ?? '')), filtroDuenos(lista.map(p => [p.fila.dueno ?? '', !!p.fila.proveedor] as [string, boolean]))];
        if (!lista.length) h.push('<div class="vacio">nada pendiente</div>');
        // el nombre de cada columna: el clic ordena por ella (la que ordena, en azul), otro clic vuelve al orden de
        // siempre (urgencia). La fecha va sobre las fechas: la cabecera repite la grilla de lo que hay a la derecha
        const col = (k: string, nombre: string, por: string) =>
            `<span data-orden-c="${k}" title="${esc(`ordenar por ${por} (otra vez: por urgencia)`)}">${nombre}</span>`;
        h.push(`<div class="tareas-cab">${col('ref', 'código', 'código, lo más nuevo arriba')}${col('est', '★', 'estrella')}${col('pri', '●', 'prioridad, la más alta arriba')}`
            + `${col('proy', 'proyecto', 'proyecto')}${col('resp', 'responsable', 'responsable')}${col('alfa', 'tarea', 'el texto, alfabético')}`
            + `<span class="meta">${col('dias', 'fecha', 'fecha límite: lo más vencido arriba, lo sin fecha al final')}<span></span><span></span><span></span></span></div>`);
        h.push('<div id="tareas-t">');
        for (const p of lista) h.push(this.filaTarea(p, esRev(p), deLaSemana(p)));
        h.push('<div id="tareas-t-vacio" class="vacio" hidden></div><div id="tareas-t-mas" class="vacio clic" hidden></div></div></section></div>');
        return h;
    }

    /** La pestaña de un proveedor que la declara (un feed): sus ítems en una lista, con la
     *  misma ficha y las mismas flechas que «revisar». */
    async abrirPestana(nombre: string): Promise<void> {
        this.t.montar();
        this.t.ir('pestana');
        this.pestana = nombre;
        this.fichaDesde = `pestana:${nombre}`;
        const d = await this.t.diaLeido();
        void this.precargar();   // todas las de la pestaña, mientras se abre la primera
        // la pestaña no es una lista: entra directo al primer ítem; la lista queda para cuando
        // no hay nada (o para el arnés)
        const primero = pendientes(d, nombre).find(p => p.fila.ficha && !this.decididas.has(p.fila.id || p.ref));
        if (primero) { await this.abrirTarea(JSON.stringify([primero.fila.proveedor, primero.fila.id || primero.ref, primero.ref])); return; }
        this.pintarPestana();
    }

    private pintarPestana(): void {
        const d = this.t.dia();
        if (!d) return;
        this.t.teclas.clear();
        const lista = pendientes(d, this.pestana).filter(p => !this.decididas.has(p.fila.id || p.ref));
        const h = ['<div id="revisar">', seccion(this.pestana, 'magenta', lista.length ? String(lista.length) : '', lista.length ? pista('⏎', 'el primero') : '')];
        if (!lista.length) h.push('<div class="vacio">nada por ahora</div>');
        for (const p of lista) {
            const [palabra] = (p.fila.avance ?? '').split(' ');
            const valor = esc(JSON.stringify([p.fila.proveedor, p.fila.id || p.ref, p.ref]));
            h.push(`<div class="tarea" data-accion="tarea" data-valor="${valor}" title="clic: leerlo">`
                + `<span class="id"></span><span class="pri"></span>`
                + `<span class="desc">${palabra ? `<span class="av"${p.fila.color ? ` style="color: var(--${esc(p.fila.color)})"` : ''}>${esc(palabra)}</span>` : ''}${esc(p.texto)}</span>`
                + `<span class="meta">${plazo(p.dias)}<span class="destino"></span></span></div>`);
        }
        h.push('</section></div>');
        this.t.pintar(h);
    }

    /** Las tareas con propuesta, en el orden del día, sin las ya decididas (salvo la abierta).
     *  Si la ficha se abrió desde una pestaña de proveedor, los ítems de esa pestaña. */
    private propuestas(desde = this.fichaDesde.startsWith('pestana:') ? this.fichaDesde.slice(8) : ''): { proveedor: string; id: string; ref: string }[] {
        const d = this.t.dia();
        if (!d) return [];
        return pendientes(d, desde)
            .filter(p => (desde || p.avance) && p.fila.ficha && (!this.decididas.has(p.fila.id || p.ref) || (p.fila.id || p.ref) === this.ficha?.id))
            .map(p => ({ proveedor: p.fila.proveedor, id: p.fila.id || p.ref, ref: p.ref }));
    }

    private async otraPropuesta(paso: number): Promise<boolean> {
        const lista = this.propuestas();
        const i = lista.findIndex(p => p.id === this.ficha?.id);
        const otra = lista[i < 0 ? 0 : i + paso];
        if (!otra || otra.id === this.ficha?.id) return false;
        await this.abrirTarea(JSON.stringify([otra.proveedor, otra.id, otra.ref]));
        return true;
    }

    private pintarFicha(): void {
        const f = this.ficha;
        if (!f) return;
        const p = f.pagina;
        if (!p) {
            this.t.pintar(this.marcoFicha([`<div class="subcab"><b>${esc(f.id)}</b></div>`, `<div class="fila falla">${esc(f.aviso ?? '')}</div>`]));
            return;
        }
        const lista = this.propuestas();
        const i = lista.findIndex(x => x.id === f.id);
        // «← 1/3 →»: cuál de las propuestas es y cómo pasar a otra (también con las flechas)
        const donde = i >= 0 && lista.length > 1
            ? `<span class="pasar"><a data-accion="tarea-anterior" title="la anterior (←)">←</a>`
              + `<span class="dim">${i + 1}/${lista.length}</span><a data-accion="tarea-siguiente" title="la siguiente (→)">→</a></span>` : '';
        // lo que se cambia donde se ve no va en la lista: la prioridad, la fecha, a quién espera y quién la hace se
        // pinchan en el subtítulo (si lo dice), y la estrella y compartir son íconos junto al título, como en la lista
        // de tareas. ⏎ es la principal; las demás van numeradas en orden, y el número es su tecla
        const puestas = new Set(ICONOS);
        const subtitulo = p.subtitulo ? this.subtituloFicha(p, puestas) : '';
        this.t.teclas.clear();
        let n = 0;
        const acciones = (p.acciones ?? []).map((a, k) => ({ a, k }));
        const botones = acciones.filter(({ a }) => !puestas.has(a.rol ?? '')).map(({ a, k }) => {
            const tecla = a.principal ? '⏎' : String(++n);
            if (!a.principal) this.t.teclas.set(tecla, () => this.accionTarea(k));
            return `<a class="atajo${a.principal ? ' principal' : ''}" data-accion="accion-tarea" data-valor="${k}"`
                + ` title="${esc(a.pide ? `${a.nombre}: pide ${a.pide}` : a.nombre)}"><kbd>${tecla}</kbd><span>${esc(a.nombre)}</span></a>`;
        });
        // el ícono es el estado de ahora (★ con estrella, ◉ compartida), que el proveedor pone al comienzo del nombre
        // de la acción que la cambia («★ quitar la estrella»); lo que sigue es lo que hace un clic
        const iconos = acciones.filter(({ a }) => a.rol === 'estrella' || a.rol === 'equipo').map(({ a, k }) => {
            const [glifo, ...resto] = a.nombre.split(' ');
            const on = glifo === '★' || glifo === '◉';
            return `<a class="icono-t ${a.rol}${on ? ' on' : ''}" data-accion="accion-tarea" data-valor="${k}" title="${esc(resto.join(' '))}">${esc(glifo)}</a>`;
        });
        // la ficha toma el color de la propuesta (cian cerrar, verde preparado…): botón principal incluido
        const color = p.bloques.find(b => b.destacado)?.color;
        this.t.pintar(this.marcoFicha([`<div class="subcab">${iconos.length ? `<span class="iconos-t">${iconos.join('')}</span>` : ''}<b>${esc(p.titulo)}</b></div>`,
            subtitulo ? `<div class="sub-ficha dim">${subtitulo}</div>` : '',
            botones.length ? `<div class="acciones-t">${botones.join('')}</div>` : '',
            ...this.t.paginas.html(p.bloques)], color, donde));
    }

    /** La ficha en su marco: arriba, volver a la lista de donde se abrió (lo mismo que ⎋) y pasar a otra propuesta;
     *  abajo, en un recuadro, todo lo de la tarea. Igual mientras se lee y si no se pudo leer. */
    private marcoFicha(cuerpo: string[], color = '', donde = ''): string[] {
        const origen = this.fichaDesde === 'fuera' && this.fuera ? this.fuera.nombre
            : this.t.nombrePestana(this.fichaDesde.replace(/^(bloque:[^:]*):.*$/, '$1'));
        return [`<div id="ficha-tarea"${color ? ` style="--c: var(--${esc(color)})"` : ''}>`,
            volver('volver-ficha', origen, donde, `volver a ${origen} (⎋)`), recuadro(cuerpo.join('\n')), '</div>'];
    }

    /** El subtítulo de la ficha, con lo que se cambia ahí mismo como botón si el proveedor deja cambiarlo (sus acciones
     *  con `rol`): la prioridad («P1», `prioridad`), la fecha («vence …», `fecha`), a quién espera («espera a …»,
     *  `espera`) y quién la hace («la hace …», `dueno`). La fecha y quién la hace, si el subtítulo no los nombra, van
     *  al final («sin fecha», «sin asignar»); a quién espera, no: si no espera a nadie, «esperar a…» sigue en la
     *  lista. Los roles que quedaron puestos se suman a `puestas`. */
    private subtituloFicha(p: cli.JsonPagina, puestas: Set<string>): string {
        let texto = esc(p.subtitulo ?? '');
        const f = this.ficha;
        const d = this.t.dia();
        const fila = f && d ? pendientes(d).find(q => q.fila.proveedor === f.proveedor && (q.fila.id || q.ref) === f.id) : undefined;
        /** `dicho`: cómo lo escribe el proveedor, si se sabe; `otro`: lo que va al final si no aparece */
        const pinchar = (rol: string, dicho: string, otro: string, ayuda: string) => {
            const k = (p.acciones ?? []).findIndex(a => a.rol === rol);
            const i = dicho ? texto.indexOf(dicho) : -1;
            if (k < 0 || (i < 0 && !otro)) return;
            puestas.add(rol);
            const boton = (que: string) => `<a class="plazo-clic" data-accion="accion-tarea" data-valor="${k}" title="${ayuda}">${que}</a>`;
            texto = i >= 0 ? texto.slice(0, i) + boton(dicho) + texto.slice(i + dicho.length) : `${texto}${texto ? ' · ' : ''}${boton(otro)}`;
        };
        pinchar('prioridad', enSubtitulo(p.subtitulo ?? '', 'prioridad'), '', 'cambiar la prioridad');
        const fecha = fila?.cuando.slice(0, 10) ?? '';
        pinchar('fecha', fecha && `vence ${fecha}`, !fila ? 'cambiar la fecha' : fecha ? `vence ${fecha}` : 'sin fecha', 'cambiar la fecha');
        const espera = esc(enSubtitulo(p.subtitulo ?? '', 'espera'));
        pinchar('espera', espera && `espera a ${espera}`, '', 'cambiar a quién espera');
        const dueno = esc(fila?.fila.dueno ?? '');
        pinchar('dueno', dueno && `la hace ${dueno}`, !fila ? 'responsable…' : dueno ? `la hace ${dueno}` : 'sin asignar', 'cambiar quién la hace');
        return texto;
    }

    /** Lo que se le escribe a Claude sobre la tarea abierta, en varias líneas, y a qué hilo: de entrada el agente
     *  general (Gestión); también el hilo de la tarea y cualquiera de la lista. Lo escrito queda como borrador de
     *  la tarea hasta que se manda, y si un envío falló, también a quién iba: se reintenta al mismo. */
    private async escribirA(a: cli.JsonAccionPagina): Promise<{ texto: string; destino: string } | undefined> {
        const f = this.ficha;
        if (!f) return undefined;
        const d = this.t.dia();
        const suyo = (d ? pendientes(d).find(q => q.fila.proveedor === f.proveedor && (q.fila.id || q.ref) === f.id) : undefined)?.hilo ?? '';
        const general = this.t.general();
        const destinos: { valor: string; nombre: string }[] = [];
        const sumar = (valor: string, nombre: string) => { if (valor && !destinos.some(x => x.valor === valor)) destinos.push({ valor, nombre }); };
        if (general) sumar(general.nombre, `${general.nombre} · el agente general`);
        if (suyo) sumar(suyo, `${suyo} · el hilo de la tarea`);
        for (const h of modelo.enLista) sumar(h.nombre, h.remoto ? `${h.nombre} · en ${h.remoto}` : h.nombre);
        const b = this.borradores.get(f.id);
        const escrito = await ui.escribir({
            titulo: `${a.nombre} · ${nombreTarea(f.id, f.pagina?.titulo)}`, ayuda: a.pide,
            destinos, destino: destinos.some(x => x.valor === b?.destino) ? b?.destino : destinos[0]?.valor,
            valor: b?.texto ?? '', borrador: texto => this.borradores.set(f.id, { ...this.borradores.get(f.id), texto }),
        });
        if (escrito) this.borradores.set(f.id, escrito);
        return escrito;
    }

    private async accionTarea(k: number): Promise<void> {
        const f = this.ficha;
        const a = f?.pagina?.acciones?.[k];
        if (!f || !a) return;
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(f.ref, false, f.proveedor); return; }
        if (tipo === 'abrir') { if (a.enlace) await abrirEnlace(a.enlace); return; }
        let texto = '';
        let hilo = '';
        // la fecha, quién la hace, a quién espera, la prioridad: con su selector, no un campo de texto
        const elegido = await elegirPorRol(a, nombreTarea(f.id, f.pagina?.titulo), f.pagina?.subtitulo ?? '');
        if (elegido === undefined) return;
        if (elegido !== null) {
            texto = elegido;
        } else if (a.pide && a.mensaje && a.al_hilo) {
            // un mensaje a un hilo («escribirle a Claude»): puede ser largo, y se elige a quién
            const escrito = await this.escribirA(a);
            if (!escrito) return;
            texto = escrito.texto;
            hilo = escrito.destino;
        } else if (a.pide) {
            const escrito = await ui.campo({ ayuda: `${f.id} · ${a.nombre}`, placeholder: a.pide });
            if (escrito === undefined) return;
            texto = escrito;
        }
        if (a.confirmar) {
            const si = await ui.aviso(`¿${a.nombre}? ${f.pagina?.titulo ?? f.id}`, 'Sí');
            if (si !== 'Sí') return;
        }
        // una acción que lleva un mensaje a un hilo (el de la tarea, Gestión) toma unos segundos: se avisa
        // con la versión de la ficha que se está mirando: si la tarea cambió desde entonces, no se hace
        const version = f.pagina?.version ?? '';
        const r = a.mensaje
            ? await ui.progreso({ titulo: `telar: ${a.nombre} · ${f.id}…` },
                () => cli.accionTarea(f.id, f.proveedor, k, texto, version, hilo))
            : await cli.accionTarea(f.id, f.proveedor, k, texto, version, hilo);
        if (r.datos && hilo) this.borradores.delete(f.id);
        if (!r.datos) {
            // la tarea cambió mientras se miraba: la ficha guardada ya no sirve, y se vuelve a leer
            if (/cambió desde que se leyó/.test(r.error ?? '')) this.fichas.delete(f.id);
            void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`);
            return;
        }
        // abrió un hilo (hecha y procesar ahora): se va a él, que es donde sigue el trabajo
        if (r.datos.hilo) {
            this.decididas.add(f.id);
            olvidarDia();
            void this.t.actualizar(true);
            await modelo.sondear();
            await ui.mostrarTerminal();
            return;
        }
        // se decidió sobre la propuesta: la siguiente, si hay; si no, se relee la ficha
        const eraPropuesta = !!f.pagina?.bloques.some(b => b.destacado);
        // la acción la cambió: la guardada ya no vale
        this.fichas.delete(`${f.proveedor}:${f.id}`);
        const releida = await cli.tarea(f.id, f.proveedor);
        if (releida.datos) this.fichas.set(`${f.proveedor}:${f.id}`, { pagina: releida.datos, hora: Date.now() });
        // en un feed, correr una acción es decidir sobre el ítem: pasa al siguiente
        const sigueViva = !this.fichaDesde.startsWith('pestana:') && !!releida.datos?.bloques.some(b => b.destacado);
        olvidarDia();
        void this.t.actualizar(true);
        // abierta desde afuera, no se pasa a la siguiente propuesta: se queda en esta
        if (eraPropuesta && !sigueViva && this.fichaDesde !== 'fuera') {
            this.decididas.add(f.id);
            if (await this.otraPropuesta(1)) return;
            // era la última: de vuelta a la lista de donde se vino, que ahora dice «nada que decidir»
            if (this.fichaDesde === 'revisar') { await this.abrirRevisar(); return; }
            if (this.fichaDesde.startsWith('pestana:')) { await this.abrirPestana(this.fichaDesde.slice(8)); return; }
        }
        if (this.t.pantalla === 'tarea' && this.ficha?.id === f.id) {
            this.ficha.pagina = releida.datos ?? this.ficha.pagina;
            this.pintarFicha();
        }
    }

    /** Las acciones de una tarea en un menú, desde la lista: se corren sin abrir la ficha. Si después
     *  la tarea ya no tiene una propuesta esperando, se da por decidida y sale de «revisar». */
    private async menuTarea(valor: string, donde?: { x: number; y: number }): Promise<void> {
        const [proveedor, id, ref] = JSON.parse(valor) as string[];
        const guardada = this.fichas.get(`${proveedor}:${id}`);
        const pagina = guardada?.pagina ?? (await ui.progreso({ discreto: true, titulo: `telar: ${id}` }, () => cli.tarea(id, proveedor))).datos;
        const acciones = pagina?.acciones ?? [];
        if (!acciones.length) { void ui.aviso(`telar: ${id} no tiene acciones`); return; }
        // el ícono y el color, por lo que hace: su rol (hecha, fecha, dueño) o su tipo (un hilo, un enlace)
        const iconoDe = (a: typeof acciones[number]): [string, string] => a.rol === 'hecha' ? [I.hecha, C.hecho]
            : a.rol === 'fecha' ? [I.fecha, C.cambiar] : a.rol === 'dueno' ? [I.persona, C.cambiar]
            : a.tipo === 'hilo' ? [I.agente, C.agente] : a.tipo === 'abrir' ? [I.enlace, C.ir]
            : a.mensaje ? [I.escribir, C.agente] : a.confirmar ? [I.cerrar, C.quitar] : [I.abrir, C.otro];
        const items = acciones.map((a, k) => ({
            label: a.nombre, k, icono: iconoDe(a)[0], color: iconoDe(a)[1],
            description: [a.rol === 'fecha' ? 'elige la fecha' : a.opciones?.length ? 'elige de una lista' : a.pide ? `pide ${a.pide}` : '', a.confirmar ? 'pide confirmación' : '',
                a.tipo === 'hilo' ? 'abre su hilo' : a.mensaje ? 'le escribe a Claude' : ''].filter(Boolean).join(' · '),
        }));
        const elegida = await ui.menu(items, donde, nombreTarea(id, pagina?.titulo));
        if (!elegida) return;
        const a = acciones[elegida.k];
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(ref, false, proveedor); return; }
        if (tipo === 'abrir') { if (a.enlace) await abrirEnlace(a.enlace); return; }
        let texto = '';
        const elegido = await elegirPorRol(a, nombreTarea(id, pagina?.titulo), pagina?.subtitulo ?? '');
        if (elegido === undefined) return;
        if (elegido !== null) {
            texto = elegido;
        } else if (a.pide) {
            const escrito = await ui.campo({ ayuda: `${id} · ${a.nombre}`, placeholder: a.pide });
            if (escrito === undefined) return;
            texto = escrito;
        }
        if (a.confirmar) {
            const si = await ui.aviso(`¿${a.nombre}? ${pagina?.titulo ?? id}`, 'Sí');
            if (si !== 'Sí') return;
        }
        const r = await ui.progreso({ titulo: `telar: ${a.nombre} · ${id}…` },
            () => cli.accionTarea(id, proveedor, elegida.k, texto));
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`); return; }
        this.fichas.delete(`${proveedor}:${id}`);
        olvidarDia();
        if (r.datos.hilo) {
            this.decididas.add(id);
            void this.t.actualizar(true);
            await modelo.sondear();
            await ui.mostrarTerminal();
            return;
        }
        const releida = await cli.tarea(id, proveedor);
        if (releida.datos) this.fichas.set(`${proveedor}:${id}`, { pagina: releida.datos, hora: Date.now() });
        if (!releida.datos?.bloques.some(b => b.destacado)) this.decididas.add(id);
        ui.estado(`${id}: ${a.nombre}`, 5000);
        await this.t.actualizar(true);
        if (this.t.pantalla === 'revisar') this.pintarLista();
    }
}
