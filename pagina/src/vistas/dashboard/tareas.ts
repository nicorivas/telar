// Las acciones sobre una tarea —llevarla a su hilo, marcarla hecha, reagendarla, asignarla,
// la estrella, compartirla— que usa el dashboard. Lo que piden a la interfaz va a la página (web/ui.ts).
// Abajo, PantallaTareas: la pestaña «tareas», la ficha de una tarea y las pestañas de proveedor.

import { barraBuscar } from '../../componentes/buscador';
import { filtros, type GrupoFiltro, type OpcionFiltro } from '../../componentes/filtros';
import { orden, type OpcionOrden } from '../../componentes/orden';
import type { AccionDePantalla } from '../../componentes/pantalla';
import { C, I } from '../../web/iconos';
import * as ui from '../../web/ui';
import type { Opcion } from '../../web/ui';
import * as cli from '../../cli';
import { esc, limpiarMd } from '../../estilo';
import { DESTRUYE } from '../../componentes/boton';
import { modelo } from '../../modelo';
import { DEUDA_DIAS, Dia, esDeuda, grupoAreas, grupoDuenos, leidoProveedores, olvidarDia, ordenLectura, pendientes, salio, yo, type Pendiente } from './dia';
import { ICONOS, ROL_ICONO, deBarra, deTitulo, esEscribir, iconoDeTitulo } from './barra-tarea';
import { fechasDeSiempre, filaTarea, iso } from './fila-tarea';
import * as leer from './leer';
import { nombreCorto } from './unidad';
import { type Accion, BARRA_DE, type EnBarra, type Pantalla, type Tablero, abrirEnlace } from './pantalla';

// La barra de la ficha (las acciones con un rol conocido como íconos, la estrella y compartir junto al título) es la
// misma de Contestar: barra-tarea.ts. Las del subtítulo salen de ella solo si `subtituloFicha` las pudo poner ahí.

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

/** Una fecha nueva para una tarea: las de siempre a un clic, u otra escrita a mano. Devuelve
 *  AAAA-MM-DD (o +Nd, que el proveedor cuenta desde su fecha), o undefined si se cancela. */
export async function elegirFecha(titulo: string, o: { conHoy?: boolean } = {}): Promise<string | undefined> {
    const dias = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const f = fechasDeSiempre();
    const hoy = f.hoy;
    const con = (label: string, d: Date, conDia = true) => ({ label, description: `${conDia ? `${dias[d.getDay()]} ` : ''}${iso(d)}`, valor: iso(d) });
    const opciones: (Opcion & { valor: string })[] = [
        // «hoy»: en foco, una vencida que sí va hoy (si no, una fecha de verdad)
        ...(o.conHoy ? [con('hoy', hoy)] : []),
        con('mañana', f.manana), con('pasado mañana', f.pasado), con('el próximo lunes', f.lunes, false),
        con('en una semana', f.semana), con('fin de mes', f.finDeMes),
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

/** La acción de una tarea por su `rol`, en un viaje. Un telar de antes (el de otra máquina sin actualizar) no conoce
 *  --rol: entonces, como siempre, la ficha primero para saber su número. */
async function porRol(id: string, proveedor: string, rol: string, texto: string): Promise<cli.Respuesta<unknown>> {
    const r = await cli.accionPorRol(id, proveedor, rol, texto);
    if (r.datos || !/--rol|unrecognized|argumentos/i.test(r.error ?? '')) return r;
    const ficha = await cli.tarea(id, proveedor);
    const k = ficha.datos?.acciones?.findIndex(a => a.rol === rol) ?? -1;
    return k < 0 ? { error: ficha.error ?? `${id}: su proveedor no ofrece eso` } : cli.accionTarea(id, proveedor, k, texto);
}

/** Mover la fecha de una tarea: la acción con rol «fecha» de su proveedor, que deja «vence X → Y» en su historia. Con la
 *  fecha dada (un botón de los de siempre) o con la que se elija aquí (elegirFecha; sin `titulo`, se lee su ficha, que lo
 *  da y dice antes si su proveedor no ofrece cambiarla). La misma en la lista de tareas, foco y las filas de Táctica (en
 *  Contestar, la fecha es la de la barra de la tarea: `correrAccion`, como en su ficha).
 *  Devuelve la fecha puesta, o undefined si se canceló o no se pudo (y lo dice). */
export async function reagendar(valor: string, o: { fecha?: string; titulo?: string; conHoy?: boolean } = {}): Promise<string | undefined> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    let fecha = o.fecha;
    if (!fecha) {
        let titulo = o.titulo;
        if (titulo === undefined) {
            const ficha = await cli.tarea(id, proveedor);
            if (!ficha.datos?.acciones?.some(a => a.rol === 'fecha')) {
                void ui.aviso(`telar: ${ficha.error ?? `${id}: su proveedor no ofrece cambiar la fecha`}`);
                return undefined;
            }
            titulo = ficha.datos.titulo;
        }
        fecha = await elegirFecha(nombreTarea(id, titulo), { conHoy: o.conHoy });
        if (!fecha) return undefined;
    }
    const r = await porRol(id, proveedor, 'fecha', fecha);
    olvidarDia();
    if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude mover ${id}`}`); return undefined; }
    ui.estado(`${id} → ${fecha}`, 5000);
    return fecha;
}

/** Correr la acción `k` de la ficha de una tarea (`p`, la que se mira), como en su ficha: con su selector si su rol lo
 *  tiene (la fecha en elegirFecha, quién la hace, a quién espera, la prioridad), lo que pide escrito (o `escrito`, si ya
 *  se escribió), y su confirmación; sobre la versión de esa ficha (si la tarea cambió desde entonces, no se hace).
 *  undefined si se canceló; si no, lo que contestó y lo que se le dio. La usan la ficha (PantallaTareas) y la barra de la
 *  tarea en Contestar (web/contestar.ts). Una que va a un hilo (`tipo: hilo`) o se abre (`abrir`), no: eso es de quien la
 *  pone. */
export async function correrAccion(id: string, proveedor: string, p: cli.JsonPagina, k: number, o: { escrito?: string; conexiones?: string } = {}) {
    const a = p.acciones?.[k];
    if (!a) return undefined;
    let texto = '';
    // la fecha, quién la hace, a quién espera, la prioridad: con su selector, no un campo de texto
    const elegido = await elegirPorRol(a, nombreTarea(id, p.titulo), p.subtitulo ?? '');
    if (elegido === undefined) return undefined;
    if (elegido !== null) {
        texto = elegido;
    } else if (a.pide && o.escrito !== undefined) {
        texto = o.escrito;
    } else if (a.pide) {
        const escrito = await ui.campo({ ayuda: `${id} · ${a.nombre}`, placeholder: a.pide });
        if (escrito === undefined) return undefined;
        texto = escrito;
    }
    if (a.confirmar) {
        // el botón dice la acción (descartar, posponer…); si su verbo destruye, en el de peligro con ⌘⌫
        const si = await ui.aviso(`¿${a.nombre}? ${p.titulo ?? id}`, a.nombre, { foco: 'cancelar', destruye: DESTRUYE.test(a.nombre) });
        if (si !== a.nombre) return undefined;
    }
    // una acción que lleva un mensaje a un hilo (el de la tarea, o el de un agente) toma unos segundos: se avisa
    const version = p.version ?? '';
    const r = a.mensaje
        ? await ui.progreso({ titulo: `telar: ${a.nombre} · ${id}…` }, () => cli.accionTarea(id, proveedor, k, texto, version, o.conexiones))
        : await cli.accionTarea(id, proveedor, k, texto, version, o.conexiones);
    return { r, texto };
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

/** Las acciones de una tarea que la sacan de lo pendiente, por su rol (las del proveedor `tareas`: completar, y cerrar
 *  como descartada): hechas, la tarea sale del día que se ve (dia.ts, `salio`) sin esperar la relectura. */
const CIERRAN: ReadonlySet<string> = new Set(['hecha', 'descartar']);

/** El ✓ de la lista: corre la acción que el proveedor declara con `rol: "hecha"`, sin abrir
 *  la ficha ni preguntar (se deshace reabriéndola). Si el proveedor no declara una, lo dice. Hecha, sale del día que
 *  se ve en todas las vistas al tiro (dia.ts, `salio`), sin esperar la relectura; si no, queda y se dice por qué. */
export async function marcarHecha(valor: string): Promise<boolean> {
    const [proveedor, id] = JSON.parse(valor) as string[];
    // un viaje: la acción por su rol. Un telar de antes (el de otra máquina sin actualizar) no
    // conoce --rol: entonces, como siempre, la ficha primero para saber su número
    const directo = await ui.progreso({ discreto: true, titulo: `${I.hecha} ${id}…` },
        () => cli.accionPorRol(id, proveedor, 'hecha'));
    if (directo.datos) {
        salio(proveedor, id);
        ui.estado(`${I.hecha} ${id} hecha`, 5000);
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
    if (!r.datos) { olvidarDia(); void ui.aviso(`telar: ${r.error ?? `no pude marcar ${id}`}`); return false; }
    salio(proveedor, id);
    ui.estado(`${I.hecha} ${id} hecha`, 5000);
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
    /** en una pestaña de lectura: lo que se respondió a cada ítem en esta pasada («✓ me interesa: …»), mientras su
     *  ficha no lo diga (`estado`), y la fila de cada ítem que se leyó (respondido, puede salir de la lista) */
    private readonly anotadas = new Map<string, string>();
    private readonly filasLeidas = new Map<string, cli.JsonFila>();
    /** lo que dibuja la ficha de lectura abierta (leer.Contexto): la instrucción lo manda como contexto */
    private lectura: leer.Contexto | null = null;
    /** la próxima relectura de una ficha que se está volviendo a procesar */
    private releerProcesando = 0;
    /** lo que la lista pone en su barra (cuántas y cuándo se leyeron): lo arma tablaTareas */
    private barraLista: EnBarra = {};
    /** fichas ya pedidas: una pestaña de proveedor puede estar lejos (el feed se pide por ssh
     *  a otro continente, ~0,5 s cada una), así que se piden antes de que se abran */
    private readonly fichas = new Map<string, { pagina: cli.JsonPagina; hora: number }>();
    /** la ficha abierta: de qué proveedor, su id y su ref (con la que se lleva al hilo) */
    private ficha?: { proveedor: string; id: string; ref: string; pagina?: cli.JsonPagina; aviso?: string };
    /** las propuestas ya decididas en esta pasada: ← → las saltan aunque el día no se haya releído (los bloques
     *  tampoco las muestran vivas) */
    readonly decididas = new Set<string>();

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
        // la instrucción: mandársela a su hilo, a uno nuevo, a otro o a un agente (web/instruccion.ts)
        'instruccion-ficha': () => this.instruccionFicha(),
        'accion-tarea': v => v && this.accionTarea(Number(v)),
        'tarea-principal': () => {
            const i = (this.ficha?.pagina?.acciones ?? []).findIndex(a => a.principal);
            if (i >= 0) return this.accionTarea(i);
        },
        'tarea-siguiente': () => this.otraPropuesta(1),
        'tarea-anterior': () => this.otraPropuesta(-1),
        'menu-tarea': (v, m) => v && this.menuTarea(v, m.donde),
        // la instrucción desde una fila de cualquier lista de tareas (fila-tarea.ts): la misma ventana que la ficha
        'instruccion-fila': v => {
            if (!v) return;
            const [proveedor, id, ref] = JSON.parse(v) as string[];
            return this.instruccionFila(proveedor, id, ref);
        },
        // las de una fila, sin abrir la ficha
        'pendiente': (v, m) => v && llevarPendiente(v, !!m.nuevo),
        // el ✓ de una fila de tarea, en cualquier lista (tareas, Táctica, los bloques, proyectos): la fila ya está tachada (lo
        // hace la vista al clic); hecha, sale del día que se ve (marcarHecha) y se redibuja sin ella al tiro, y el día se
        // relee por detrás (con red, ~10 s que no hay por qué esperar). Si no se pudo, se redibuja con ella y se dice
        'hecha-fila': v => this.hecha(v),
        'hecha': v => this.hecha(v),
        // el de una viñeta de un documento (sin proveedor): [ ] → [x] en su archivo, y lo mismo
        'hecha-vineta': async v => {
            if (!v) return;
            const [ref, texto] = JSON.parse(v) as string[];
            const r = await cli.vineta(ref, texto, ['--hecho']);
            if (!r.datos) void ui.aviso(`telar: ${r.error ?? 'no pude marcarla'}`);
            else { ui.estado(`${I.hecha} ${texto.slice(0, 60)}`, 5000); salio('', ref); }
            this.t.render();
            if (r.datos) void this.t.actualizar(true);
        },
        'reagendar': async v => { if (v && await reagendar(v)) await this.releer(); },
        'equipo-tarea': async v => { if (v && await alternarEquipo(v)) await this.releer(); },
        'estrella-tarea': async v => { if (v && await alternarEstrella(v)) await this.releer(); },
    };

    constructor(private readonly t: Tablero) {}

    /** El ✓ de una fila de tarea (`[proveedor, id, ref]`). */
    private async hecha(v: string): Promise<void> {
        if (!v) return;
        await marcarHecha(v);
        this.t.render();
        // también si no se pudo: lo que diga el proveedor ahora es lo que se ve
        void this.t.actualizar(true);
    }

    pintar(): void {
        if (this.t.pantalla === 'revisar') this.pintarLista();
        else if (this.t.pantalla === 'pestana') this.pintarPestana();
        else this.pintarFicha();
    }

    /** Con la ficha abierta se marca la pestaña de donde se abrió; con un feed, el suyo. */
    pestanaMarcada(): string {
        // abierta desde «esperando», una subpestaña de tareas: se marca la fila de tareas
        if (this.t.pantalla === 'tarea') return this.fichaDesde === 'esperando' ? 'revisar' : this.fichaDesde.replace(/^(bloque:[^:]*):.*$/, '$1');
        if (this.t.pantalla === 'pestana') return `pestana:${this.pestana}`;
        return this.t.pantalla;
    }

    /** Releer el día después de cambiar una tarea desde su fila, y repintar la lista si es lo que se ve. */
    private async releer(): Promise<void> {
        await this.t.actualizar(true);
        if (this.t.pantalla === 'revisar') this.pintarLista();
    }

    /** La instrucción sobre la tarea de la ficha: la ventana (web/instruccion.ts) con /tarea sugerida y lo que haya
     *  quedado escrito sin mandar. Lo mandado queda en su historia: la ficha se relee para mostrarlo. */
    private async instruccionFicha(): Promise<void> {
        const f = this.ficha;
        if (!f) return;
        if (this.esLectura()) { await this.instruccionLectura(); return; }
        const d = this.t.dia();
        const fila = d ? pendientes(d).find(q => q.fila.proveedor === f.proveedor && (q.fila.id || q.ref) === f.id)?.fila : undefined;
        const { abrir } = await import('../../web/instruccion');
        const r = await abrir({ direccion: fila?.direccion || f.pagina?.direccion || '',
            fila: fila ?? { ref: f.ref, id: f.id, proveedor: f.proveedor, texto: f.pagina?.titulo ?? f.id },
            titulo: nombreTarea(f.id, f.pagina?.titulo), skill: 'tarea' });
        if (r) await this.releerFicha(f.proveedor, f.id);
    }

    /** La instrucción sobre la lectura de la ficha: la misma ventana, con «un hilo nuevo» elegido y llamado como ella,
     *  y lo que la ficha tiene (el enlace, de dónde viene, el resumen, el porqué, lo respondido y lo escrito en «tu
     *  lectura») como contexto libre (leer.paraUnHilo). Si se abrió un hilo, se va a él, como al procesar un ítem de un
     *  bloque. */
    private async instruccionLectura(): Promise<void> {
        const f = this.ficha, c = this.lectura;
        // la de la ficha que se ve: mientras se lee otra, la anterior no va
        if (!f || !c || c.clave !== `leer:${f.proveedor}:${f.id}`) { ui.estado('la lectura todavía se está leyendo', 3000); return; }
        const escrito = (document.getElementById('leer-porque') as HTMLTextAreaElement | null)?.value ?? '';
        const nombre = this.t.nombrePestana(this.fichaDesde) || this.pestana;
        const { abrir, NUEVO } = await import('../../web/instruccion');
        const r = await abrir({ ...leer.paraUnHilo(c, escrito, nombre), a: NUEVO });
        if (r?.como === 'abierto') await ui.mostrarTerminal();
    }

    /** La instrucción desde la fila de una tarea (su ícono, o «instrucción…» en su ⋯), en cualquier lista. */
    private async instruccionFila(proveedor: string, id: string, ref: string): Promise<void> {
        const d = this.t.dia();
        const p = d ? pendientes(d).find(q => q.ref === ref) : undefined;
        const { abrir } = await import('../../web/instruccion');
        const r = await abrir({ direccion: p?.fila.direccion ?? '', fila: p?.fila ?? { ref, id, proveedor, texto: id },
            titulo: `${p?.fila.proveedor ? `${ref} · ` : ''}${limpiarMd(p?.texto ?? id)}`, skill: p?.fila.ficha ? 'tarea' : undefined });
        if (r) this.fichas.delete(`${proveedor}:${id}`);  // su historia cambió
    }

    /** Se le mandó una instrucción a una tarea desde otra pantalla (foco): su historia cambió y la ficha guardada ya no
     *  vale (apretar una acción en ella daría un 409). */
    olvidarFicha(proveedor: string, id: string): void { void this.releerFicha(proveedor, id); }

    /** La tarea cambió por fuera de sus botones (una instrucción, que queda en su historia): la ficha guardada ya no
     *  vale, y si es la que se ve, se relee. */
    private async releerFicha(proveedor: string, id: string): Promise<void> {
        this.fichas.delete(`${proveedor}:${id}`);
        if (this.t.pantalla !== 'tarea' || this.ficha?.id !== id) return;
        const r = await cli.tarea(id, proveedor);
        if (!r.datos) return;
        this.fichas.set(`${proveedor}:${id}`, { pagina: r.datos, hora: Date.now() });
        if (this.t.pantalla === 'tarea' && this.ficha?.id === id) {
            this.ficha.pagina = r.datos;
            this.pintarFicha();
        }
    }

    /** ⎋ en la ficha: a la lista, el feed o el ítem de donde se abrió, o a la vista de afuera; si no, a «ahora». */
    private async volver(): Promise<void> {
        if (this.fichaDesde === 'fuera' && this.fuera) this.fuera.ir();
        else if (this.fichaDesde === 'revisar') await this.abrirRevisar();
        else if (this.fichaDesde === 'esperando') await this.t.accion('esperando');
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
        if (this.t.pantalla === 'esperando') this.fichaDesde = 'esperando';
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
        this.t.pintar(...this.marcoFicha([`<div class="subcab"><b>${esc(id)}</b></div>`, '<div class="fila dim">leyendo…</div>']));
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
        this.t.pintar(this.tablaTareas(d), this.barraLista);
    }

    /** Una fila de tarea en «tareas» y donde se muestren tareas sueltas (un correo y las suyas), con la columna de su
     *  proyecto (fila-tarea.ts). `rev`: espera una decisión; `semana`: va en «esta semana». */
    filaTarea(p: ReturnType<typeof pendientes>[number], rev: boolean, semana: boolean): string {
        const proy = this.t.proyectos.deFila(p.fila);
        // el proyecto en pocas letras: su cliente, o su nombre; entero en el globo. Un cliente que es la casa
        // misma (`internos` del perfil: el servidor lo marca `interno`) no dice nada: ahí va el nombre sin él
        const corto = proy ? nombreCorto(proy) : '';
        return filaTarea(p, { proyecto: proy ? { nombre: proy.nombre, corto, ruta: proy.ruta } : null, rev, semana });
    }

    /** La tabla de tareas: la de la pestaña «tareas» y la de «hoy» son la misma (filtros, columnas,
     *  orden, ⋯). Lo que se elija en una (el modo, lo buscado, el orden) se ve igual en la otra. */
    private tablaTareas(d: Dia): string[] {
        const lista = pendientes(d).filter(p => !this.decididas.has(p.fila.id || p.ref));
        const esRev = (p: (typeof lista)[number]) => !!p.avance && !!p.fila.ficha;
        const cuenta = (f: (p: (typeof lista)[number]) => boolean) => lista.filter(f).length;
        // cada filtro con su cuenta: lo que decide qué mirar es cuánto hay
        // «esta semana», lo que se ve de entrada: lo vencido o que vence en 7 días, lo destacado (P0 o con
        // estrella) y lo que espera una decisión con fecha en 14 días. Lo demás, detrás de «ver todas». La deuda (lo
        // vencido hace más de 30 días, dia.ts) no: va en su filtro; salvo con estrella, que la pone la persona y dice
        // «siempre en esta semana»
        const deLaSemana = (p: (typeof lista)[number]) => (!esDeuda(p.dias) || !!p.fila.estrella)
            && ((p.dias !== null && p.dias <= 7) || !!p.fila.destacada || (esRev(p) && p.dias !== null && p.dias <= 14));
        const modos: OpcionFiltro[] = [
            { clave: 'semana', nombre: 'esta semana', cuenta: cuenta(deLaSemana),
                ayuda: 'esta semana: lo vencido o que vence en 7 días, lo destacado y lo que espera una decisión en 14' },
            { clave: 'todas', nombre: 'todas', cuenta: lista.length, ayuda: 'todas las pendientes' },
            { clave: 'revisar', nombre: 'por revisar', cuenta: cuenta(esRev), ayuda: 'por revisar: un agente las dejó listas para decidir' },
            { clave: 'vencidas', nombre: 'vencidas', cuenta: cuenta(p => p.dias !== null && p.dias < 0) },
            { clave: 'deuda', nombre: 'deuda', cuenta: cuenta(p => esDeuda(p.dias)),
                ayuda: `deuda: lo vencido hace más de ${DEUDA_DIAS} días, tareas y casillas. No va en «esta semana» ni en lo urgente del día; sigue en «todas» y en «vencidas»` },
            { clave: 'estrella', nombre: I.estrella, cuenta: cuenta(p => !!p.fila.estrella), ayuda: 'con estrella' },
            { clave: 'encurso', nombre: 'en curso', cuenta: cuenta(p => p.enCurso), ayuda: 'en curso: un hilo la está trabajando' },
            { clave: 'sinfecha', nombre: 'sin fecha', cuenta: cuenta(p => p.dias === null) },
        ];
        // los filtros (componentes/filtros.ts), en una fila: el modo a la vista, porque se cambia seguido; el área y el
        // responsable plegados (lo que rige y un ⌄, el resto en un menú), porque se eligen una vez y se dejan. Lo que
        // rige lo pone la vista con lo recordado (vista.ts, `aplicarTareas`)
        const plegar = (g: GrupoFiltro | null): GrupoFiltro[] => g ? [{ ...g, plegado: true }] : [];
        const grupos: GrupoFiltro[] = [{ clave: 'modo', nombre: 'qué mirar', opciones: modos, activa: 'semana', siempre: 'semana' },
            ...plegar(grupoAreas(lista.map(p => p.fila.area ?? ''))),
            ...plegar(grupoDuenos(lista.map(p => [p.fila.dueno ?? '', !!p.fila.proveedor] as [string, boolean])))];
        // cuándo se leyeron: el proveedor se consulta solo cada 5 minutos, y «actualizar» lo fuerza ya
        const leido = leidoProveedores();
        const hace = leido ? Math.round((Date.now() - leido) / 60000) : -1;
        // en la barra, nada de eso a la vista: cuántas, en el globo del título (el buscador las cuenta); cuándo, en el de ↻
        this.barraLista = { ayuda: `${lista.length} tareas`, leido: hace < 0 ? 'sin leer' : hace === 0 ? 'leídas recién' : `leídas hace ${hace} min` };
        // arriba, las herramientas de la lista (buscar y ordenar, como en la barra de hilos); debajo, los filtros, cada
        // opción con su cuenta. Las filas son ítems (fila-tarea.ts): ya no hay columnas con nombre, el orden va en su grupo
        const ordenes: OpcionOrden[] = [
            { clave: 'dias', icono: I.fecha, ayuda: 'fecha límite: lo más vencido arriba, lo sin fecha al final' },
            { clave: 'pri', icono: I.urgencia, ayuda: 'prioridad, la más alta arriba' },
            { clave: 'est', icono: I.estrella, ayuda: 'estrella: las señaladas arriba' },
            { clave: 'proy', icono: I.carpeta, ayuda: 'proyecto' },
            { clave: 'resp', icono: I.persona, ayuda: 'responsable' },
            { clave: 'ref', icono: I.etiqueta, ayuda: 'código, lo más nuevo arriba' },
            { clave: 'alfa', icono: I.alfabetico, ayuda: 'el texto, alfabético' },
        ];
        const h = ['<div id="revisar" class="lista-tareas">',
            barraBuscar({ id: 'buscar-t', placeholder: 'tareas', atajo: '/', cuenta: { id: 'tareas-t-cuenta' }, claseBarra: 'herram',
                ayuda: 'buscar en el código, el texto, el proyecto y el responsable · ⏎ abre la primera · ⎋ borra',
                herramientas: orden({ grupo: 'tareas', opciones: ordenes, activa: '' }) }),
            filtros({ grupos })];
        if (!lista.length) h.push('<div class="vacio">nada pendiente</div>');
        h.push('<div id="tareas-t">');
        for (const p of lista) h.push(this.filaTarea(p, esRev(p), deLaSemana(p)));
        h.push('<div id="tareas-t-vacio" class="vacio" hidden></div><div id="tareas-t-mas" class="vacio clic" hidden></div></div></div>');
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
        const primero = this.dePestana(d, nombre).find(p => p.fila.ficha && !this.decididas.has(p.fila.id || p.ref));
        if (primero) { await this.abrirTarea(JSON.stringify([primero.fila.proveedor, primero.fila.id || primero.ref, primero.ref])); return; }
        this.pintarPestana();
    }

    private pintarPestana(): void {
        const d = this.t.dia();
        if (!d) return;
        this.t.teclas.clear();
        // todo lo que entrega el proveedor, sin tope ni «ver más»: en una de lectura, en su orden (ordenLectura)
        const lista = this.dePestana(d, this.pestana).filter(p => !this.decididas.has(p.fila.id || p.ref));
        // la prioridad y «tuya», en su ranura, si alguna fila las dice (si no, la fila de siempre)
        const marcas = lista.some(p => !!p.fila.de?.trim() || (p.fila.prioridad !== undefined && p.fila.prioridad !== null));
        const h = ['<div id="revisar" class="lista-tareas">'];
        if (!lista.length) h.push('<div class="vacio">nada por ahora</div>');
        for (const p of lista) h.push(filaTarea(p, { lectura: true, marcas, rev: !!p.fila.avance, color: p.fila.color }));
        h.push('</div>');
        this.t.pintar(h, { nombre: this.pestana, color: 'magenta', ayuda: lista.length ? `${lista.length} · ⏎ abre la primera` : undefined });
    }

    /** Las tareas con propuesta, en el orden del día, sin las ya decididas (salvo la abierta).
     *  Si la ficha se abrió desde una pestaña de proveedor, los ítems de esa pestaña. */
    private propuestas(desde = this.fichaDesde.startsWith('pestana:') ? this.fichaDesde.slice(8) : ''): { proveedor: string; id: string; ref: string }[] {
        const d = this.t.dia();
        if (!d) return [];
        return (desde ? this.dePestana(d, desde) : pendientes(d))
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
            this.t.pintar(...this.marcoFicha([`<div class="subcab"><b>${esc(f.id)}</b></div>`, `<div class="fila falla">${esc(f.aviso ?? '')}</div>`]));
            return;
        }
        if (this.esLectura()) { this.pintarLectura(p); return; }
        const lista = this.propuestas();
        const i = lista.findIndex(x => x.id === f.id);
        // «1/3», con ← y →: cuál de las propuestas es y cómo pasar a otra (también con las flechas), en la barra
        const donde = i >= 0 && lista.length > 1 ? { i, n: lista.length } : undefined;
        // lo que se cambia donde se ve no va en la lista: la prioridad, la fecha, a quién espera y quién la hace se
        // pinchan en el subtítulo (si lo dice), y la estrella y compartir son íconos junto al título, como en la lista
        // de tareas. Las demás con un rol conocido (hecha, descartar, esperar a…, tamaño…) son íconos en la barra, con
        // su globo; «escribirle a Claude» es el ícono de la instrucción. ⏎ es la principal; las demás van numeradas en
        // orden (primero las de palabra, después las de ícono), y el número es su tecla
        const puestas = new Set(ICONOS);
        const subtitulo = p.subtitulo ? this.subtituloFicha(p, puestas) : '';
        this.t.teclas.clear();
        let n = 0;
        const acciones = (p.acciones ?? []).map((a, k) => ({ a, k }));
        const sueltas = acciones.filter(({ a }) => !puestas.has(a.rol ?? '') && !esEscribir(a));
        const conIcono = deBarra(p.acciones ?? [], puestas);
        const botones = sueltas.filter(({ k }) => !conIcono.some(x => x.k === k)).map(({ a, k }) => {
            const tecla = a.principal ? '⏎' : String(++n);
            if (!a.principal) this.t.teclas.set(tecla, () => this.accionTarea(k));
            return `<a class="atajo${a.principal ? ' principal' : ''}" data-accion="accion-tarea" data-valor="${k}"`
                + ` title="${esc(a.pide ? `${a.nombre}: pide ${a.pide}` : a.nombre)}"><kbd>${tecla}</kbd><span>${esc(a.nombre)}</span></a>`;
        });
        const enBarra: AccionDePantalla[] = conIcono.map(({ k, icono, tono, ayuda }) => {
            const tecla = String(++n);
            this.t.teclas.set(tecla, () => this.accionTarea(k));
            return { accion: 'accion-tarea', valor: String(k), icono, tono, ayuda: `${ayuda} (${tecla})` };
        });
        // la estrella y compartir, junto al título: su ícono es el estado de ahora
        const iconos = deTitulo(p.acciones ?? []).map(x => iconoDeTitulo(x, 'data-accion="accion-tarea"'));
        // la ficha toma el color de la propuesta (cian cerrar, verde preparado…): botón principal incluido
        const color = p.bloques.find(b => b.destacado)?.color;
        this.t.pintar(...this.marcoFicha([`<div class="subcab">${iconos.length ? `<span class="iconos-t">${iconos.join('')}</span>` : ''}<b>${esc(p.titulo)}</b></div>`,
            subtitulo ? `<div class="sub-ficha dim">${subtitulo}</div>` : '',
            botones.length ? `<div class="acciones-t">${botones.join('')}</div>` : '',
            ...this.t.paginas.html(p.bloques)], color, donde, enBarra));
    }

    /** Si la ficha abierta es de una pestaña de lectura (un proveedor con `vista = "lectura"`): se dibuja para leerla
     *  (vistas/dashboard/leer.ts), no como una tarea. */
    private esLectura(): boolean {
        return this.fichaDesde.startsWith('pestana:') && this.pestanaDeLectura(this.fichaDesde.slice(8));
    }

    private pestanaDeLectura(nombre: string): boolean {
        return this.t.config()?.pestanas?.find(x => x.nombre === nombre)?.vista === 'lectura';
    }

    /** Lo de la pestaña `nombre` de un proveedor, entero (sin tope): en una de lectura, lo que se mandó la persona
     *  primero, después por prioridad y lo más nuevo arriba (dia.ts, `ordenLectura`); en las demás, el orden del
     *  proveedor. La lista, la ficha, ← → y «sigue» van en este orden. */
    private dePestana(d: Dia, nombre: string): Pendiente[] {
        const lista = pendientes(d, nombre);
        return this.pestanaDeLectura(nombre) ? ordenLectura(lista) : lista;
    }

    /** La ficha de una lectura (vistas/dashboard/leer.ts): el texto para leerlo con calma, al lado lo que puede ir al grafo, la
     *  respuesta al final y lo que sigue. En la barra no va «1/8»: no es una cola por despachar; ← → siguen pasando de
     *  una a otra. La fila del ítem se guarda al pintarla: respondido, puede salir de la lista del proveedor y su ficha
     *  sigue a la vista. */
    private pintarLectura(p: cli.JsonPagina): void {
        const f = this.ficha!;
        const d = this.t.dia();
        const lista = this.propuestas();
        const i = lista.findIndex(x => x.id === f.id);
        const filaDe = (id: string) => (d ? pendientes(d, this.pestana).find(q => (q.fila.id || q.ref) === id) : undefined);
        const fila = filaDe(f.id)?.fila ?? this.filasLeidas.get(f.id);
        if (fila) this.filasLeidas.set(f.id, fila);
        // la que sigue: la de después en la lista, o si esta ya salió de ella (respondida), la primera que queda
        const sig = i >= 0 ? lista[i + 1] : lista.find(x => x.id !== f.id), ant = i > 0 ? lista[i - 1] : undefined;
        const ctx: leer.Contexto = {
            pagina: p, fila,
            siguiente: sig ? { titulo: filaDe(sig.id)?.texto ?? sig.id } : undefined,
            anterior: ant ? { titulo: filaDe(ant.id)?.texto ?? ant.id } : undefined,
            anotado: this.anotadas.get(f.id),
            clave: `leer:${f.proveedor}:${f.id}`,
        };
        this.lectura = ctx;
        this.t.teclas.clear();
        // las acciones de solo ícono (volver a procesar), en la barra, con su ayuda; mientras corre, tenue
        const iconos: AccionDePantalla[] = (p.acciones ?? []).map((a, k) => ({ a, k })).filter(({ a }) => a.solo_icono).map(({ a, k }) => ({
            accion: 'accion-tarea', valor: String(k), icono: (I as Record<string, string>)[a.icono ?? ''] ?? I.accion, tono: 'violeta', si: !!p.procesando,
            ayuda: p.procesando ? `${a.nombre}: ya va, desde las ${p.procesando}` : (a.ayuda || a.nombre) }));
        const [cuerpo, barra] = this.marcoFicha([leer.html(ctx)], '', i >= 0 && lista.length > 1 ? { i, n: lista.length } : undefined, iconos);
        this.t.pintar(cuerpo, barra);
        const raiz = document.getElementById('ficha-tarea');
        if (raiz) leer.montar(raiz, ctx, (k, texto, conexiones) => void this.accionTarea(k, texto, conexiones));
        // volviendo a procesar (un agente rehace la ficha, y tarda minutos): se relee sola hasta que termina
        clearTimeout(this.releerProcesando);
        if (p.procesando) this.releerProcesando = window.setTimeout(() => void this.releerFicha(f.proveedor, f.id), 10000);
    }

    /** La ficha en su marco: arriba, volver a la lista de donde se abrió (lo mismo que ⎋), las acciones de la tarea que
     *  son íconos (`iconos`, y la instrucción) y pasar a otra propuesta; abajo, todo lo de la tarea. Igual mientras se
     *  lee y si no se pudo leer. */
    private marcoFicha(cuerpo: string[], color = '', donde?: { i: number; n: number }, iconos: AccionDePantalla[] = []): [string[], EnBarra] {
        const origen = this.fichaDesde === 'fuera' && this.fuera ? this.fuera.nombre
            : this.t.nombrePestana(this.fichaDesde.replace(/^(bloque:[^:]*):.*$/, '$1'));
        // la tinta de la pestaña de donde se abrió: la de un feed (leer), la de un bloque (el correo), la de tareas
        const bloque = this.fichaDesde.startsWith('bloque:') ? this.fichaDesde.split(':')[1] : '';
        const tinta = this.fichaDesde.startsWith('pestana:') ? 'magenta'
            : bloque ? this.t.config()?.bloques?.find(b => b.clave === bloque)?.color ?? '' : this.fichaDesde === 'fuera' ? '' : BARRA_DE.revisar?.[1] ?? '';
        const barra: EnBarra = {
            volver: { accion: 'volver-ficha', icono: I.atras, ayuda: `volver a ${origen} (⎋)` },
            // desde una subpestaña de tareas (esperando), el nombre es el de la app: tareas
            nombre: this.fichaDesde === 'esperando' ? 'tareas' : origen, color: tinta,
            acciones: [
                ...iconos,
                // en una lectura no hay «su hilo»: abre uno nuevo con ella (o se la manda a otro), con lo que dice la ficha
                ...(this.ficha ? [{ accion: 'instruccion-ficha', icono: I.instruccion, tono: 'violeta' as const,
                    ayuda: this.esLectura() ? 'instrucción: abrir un hilo con esta lectura (o mandársela a otro o a un agente), con una skill o lo que le pidas'
                        : 'instrucción: mandársela a su hilo, a uno nuevo, a otro o a un agente, con una skill o lo que le pidas' }] : []),
                ...(donde ? [
                    // cuál de cuántas, en su globo: la barra no lleva cuentas
                    { accion: 'tarea-anterior', icono: I.anterior, ayuda: `la anterior (←) · esta es la ${donde.i + 1} de ${donde.n}` },
                    { accion: 'tarea-siguiente', icono: I.adelante, ayuda: `la siguiente (→) · esta es la ${donde.i + 1} de ${donde.n}` },
                ] : []),
            ],
        };
        // sin recuadro: la ficha no se abre aparte, es la pantalla (la gramática visual: un marco es para una ventana)
        return [[`<div id="ficha-tarea"${color ? ` style="--c: var(--${esc(color)})"` : ''}>`, ...cuerpo, '</div>'], barra];
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

    /** Corre la acción `k` de la ficha abierta. `escrito`: lo que ya se escribió para ella (el porqué de una lectura,
     *  aunque sea nada), y entonces no se pide. */
    private async accionTarea(k: number, escrito?: string, conexiones?: string): Promise<void> {
        const f = this.ficha;
        const a = f?.pagina?.acciones?.[k];
        if (!f || !a) return;
        const tipo = a.tipo ?? 'comando';
        if (tipo === 'hilo') { await llevarPendiente(f.ref, false, f.proveedor); return; }
        if (tipo === 'abrir') { if (a.enlace) await abrirEnlace(a.enlace); return; }
        if (esEscribir(a)) { await this.instruccionFicha(); return; }
        // con la versión de la ficha que se está mirando: si la tarea cambió desde entonces, no se hace
        const hecho = await correrAccion(f.id, f.proveedor, f.pagina!, k, { escrito, conexiones });
        if (!hecho) return;
        const { r, texto } = hecho;
        if (!r.datos) {
            // la tarea cambió mientras se miraba (una instrucción desde foco, que quedó en su historia): la ficha
            // guardada ya no sirve, y se vuelve a leer para decidir sobre lo de ahora
            if (/cambió desde que se leyó/.test(r.error ?? '')) void this.releerFicha(f.proveedor, f.id);
            void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`);
            return;
        }
        if (CIERRAN.has(a.rol ?? '')) salio(f.proveedor, f.id);
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
        // una lectura respondida no se va: queda a la vista con lo anotado, y abajo, lo que sigue (sin apuro). Una de solo
        // ícono (volver a procesar) no es una respuesta: la ficha se relee y nada más
        if (this.esLectura()) {
            if (!a.solo_icono) {
                this.anotadas.set(f.id, `${a.nombre}${texto ? `: ${texto}` : ''}`);
                this.decididas.add(f.id);
                leer.olvidarBorrador(`leer:${f.proveedor}:${f.id}`);
            }
            olvidarDia();
            void this.t.actualizar(true);
            if (this.t.pantalla === 'tarea' && this.ficha?.id === f.id) {
                this.ficha.pagina = releida.datos ?? this.ficha.pagina;
                this.pintarFicha();
            }
            return;
        }
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
        // el ícono y el color, por lo que hace: su rol (los mismos de la barra de la ficha) o su tipo (un hilo, un enlace)
        const iconoDe = (a: typeof acciones[number]): [string, string] => ROL_ICONO[a.rol ?? '']
            ? [ROL_ICONO[a.rol ?? ''].icono, ROL_ICONO[a.rol ?? ''].tono]
            : a.tipo === 'hilo' ? [I.agente, C.agente] : a.tipo === 'abrir' ? [I.enlace, C.ir]
            : a.mensaje ? [I.escribir, C.agente] : a.confirmar ? [I.cerrar, C.quitar] : [I.abrir, C.otro];
        // «escribirle a Claude» es la instrucción: su ventana, con su nombre y su ícono
        const items = acciones.map((a, k) => esEscribir(a)
            ? { label: 'instrucción…', k, icono: I.instruccion, color: C.agente, description: 'mandársela a su hilo, a uno nuevo, a otro o a un agente' }
            : {
                label: a.nombre, k, icono: iconoDe(a)[0], color: iconoDe(a)[1],
                description: [a.rol === 'fecha' ? 'elige la fecha' : a.opciones?.length ? 'elige de una lista' : a.pide ? `pide ${a.pide}` : '', a.confirmar ? 'pide confirmación' : '',
                    a.tipo === 'hilo' ? 'abre su hilo' : a.mensaje ? 'le escribe a Claude' : ''].filter(Boolean).join(' · '),
            });
        const elegida = await ui.menu(items, donde, nombreTarea(id, pagina?.titulo));
        if (!elegida) return;
        const a = acciones[elegida.k];
        if (esEscribir(a)) { await this.instruccionFila(proveedor, id, ref); return; }
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
            const si = await ui.aviso(`¿${a.nombre}? ${pagina?.titulo ?? id}`, a.nombre, { foco: 'cancelar', destruye: DESTRUYE.test(a.nombre) });
            if (si !== a.nombre) return;
        }
        const r = await ui.progreso({ titulo: `telar: ${a.nombre} · ${id}…` },
            () => cli.accionTarea(id, proveedor, elegida.k, texto));
        if (!r.datos) { void ui.aviso(`telar: ${r.error ?? `no pude: ${a.nombre}`}`); return; }
        this.fichas.delete(`${proveedor}:${id}`);
        // la cerró: sale de lo que se ve al tiro, en la lista de donde se abrió el menú (Táctica, un bloque…)
        if (CIERRAN.has(a.rol ?? '')) { salio(proveedor, id); this.t.render(); } else olvidarDia();
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
