// Lo que comparten «tareas» y «hoy»: de dónde salen los datos del día y cómo se dibuja una
// lista de pendientes.
//
// Todo viene de `telar hoy --json`, que junta los pendientes de los documentos con lo que
// digan los proveedores declarados en la configuración (una agenda, un gestor de tareas).
// Ninguno viene de fábrica: sin proveedores declarados no hay agenda, y eso se dice en vez
// de dejar un hueco. La página no sale a la red por su cuenta jamás: todo es la API.
//
// Dos ritmos, como en la terminal: `--local` no consulta a nadie y contesta en lo que tarda
// leer unos archivos; sin `--local` se consulta a los proveedores, que pueden tardar. Lo
// caro se pide cada pocos minutos y lo barato cada vez.
//
// El orden y el filtro pasan en la página (vistas/dashboard/vista.ts): la lista ya está en pantalla, y
// filtrarla ahí es instantáneo mientras que volver a preguntar tarda lo que tarde el proveedor.

import * as cli from '../../cli';
import { esc, limpiarMd, normalizar } from '../../estilo';
import { I } from '../../web/iconos';
import * as avisos from '../../web/avisos';
import * as ui from '../../web/ui';
import type { GrupoFiltro } from '../../componentes/filtros';

// ───────────────────────── los datos ─────────────────────────

export interface Dia {
    ahora: string;
    fecha: string;            // AAAA-MM-DD
    nombreDia: string;        // «viernes»
    semana: number;
    agenda: cli.JsonFila[] | null;   // null: no se consultó, o no hay proveedor
    pendientes: cli.JsonFila[];
    declarados: string[];
    fallas: string[];
    error?: string;
    /** de cuándo es lo leído: la generación (`olvidarDia`) con que empezó su lectura. Lo que salió de lo pendiente
     *  después (`salio`) no lo sabe: `conLoSalido` se lo pone. Sin ella (un día de mentira), lo salido no se le pone */
    generacion?: number;
}

const VACIO: Dia = {
    ahora: '', fecha: '', nombreDia: '', semana: 0,
    agenda: null, pendientes: [], declarados: [], fallas: [],
};

let cache: { dia: Dia; hora: number } | undefined;
/** La agenda cuesta una consulta a la red: se guarda aparte y se reusa entre lecturas locales. */
let agenda: { filas: cli.JsonFila[] | null; hora: number; fecha: string } = { filas: null, hora: 0, fecha: '' };
/** Lo mismo con los pendientes que traen los proveedores (las tareas de un gestor): una
 *  lectura local no los trae, y si se tomara su lista tal cual desaparecerían hasta la
 *  próxima consulta a la red. Los de los documentos sí se releen en cada lectura. */
let deProveedores: cli.JsonFila[] = [];

const CADA_RED = 5 * 60 * 1000;

/** Cuántas veces se olvidó lo leído (`olvidarDia`: una acción cambió una tarea, una fecha, el calendario). Cada lectura
 *  recuerda con cuál empezó: si al volver ya es otra, trae lo de antes de ese cambio, y no se guarda ni se entrega (una
 *  tarea recién cerrada volvía con ella, y quedaba pegada en `deProveedores` hasta la próxima consulta a la red). */
let generacion = 0;

/** La lectura en curso, si la hay: las vistas piden el día por su cuenta, y una consulta a un proveedor no se hace dos
 *  veces porque dos paneles la quisieron a la vez. Sirve a quien pide solo si empezó después del último cambio y trae
 *  lo que se pide (con red, si toca la red). */
let enCurso: { promesa: Promise<Dia>; red: boolean; generacion: number } | undefined;

/** Lo que salió de lo pendiente desde esta página (una tarea marcada hecha, descartada, una viñeta tachada) y que su
 *  proveedor ya confirmó: `proveedor\nid` → la generación en que salió. Lo leído antes no lo sabe, y lo que se ve sale
 *  de ahí hasta que llega la relectura (con red, unos 10 s): `conLoSalido`. */
const salidas = new Map<string, number>();
const claveSalida = (proveedor: string, id: string): string => `${proveedor}\n${id}`;
/** la generación de lo último que salió: lo leído desde entonces ya lo sabe todo */
let ultimaSalida = -1;

/** Una tarea salió de lo pendiente, y su proveedor ya lo dijo (`marcarHecha`, tareas.ts): lo leído hasta ahora ya no
 *  sirve (se olvida, y la próxima lectura va a la red), y mientras llega lo nuevo, lo que se ve ya no la tiene. Una
 *  lectura que empiece después manda: si la tarea sigue ahí (alguien la reabrió), se ve. `id`: el de su fila, o su
 *  `ref` si no tiene (una viñeta de un documento, sin proveedor). */
export function salio(proveedor: string, id: string): void {
    olvidarDia();
    salidas.set(claveSalida(proveedor, id), generacion);
    ultimaSalida = generacion;
}

/** La generación de ahora: lo que se empiece a leer aquí ya sabe lo que salió hasta ahora (para lo que se lee aparte del
 *  día, como las viñetas de todos los documentos de proyectos, y se le pone con `conLoSalido`). */
export const generacionDeAhora = (): number => generacion;

/** El día con lo que salió después de leerlo (`salio`) ya hecho: lo que se ve (Dashboard.dia) no la vuelve a mostrar
 *  mientras se relee. El mismo día si no le falta nada (lo de siempre: leído después de lo último que salió). */
export function conLoSalido(d: Dia, salido: ReadonlyMap<string, number> = salidas): Dia {
    const de = d.generacion;
    if (de === undefined || !salido.size || de >= (salido === salidas ? ultimaSalida : Math.max(...salido.values()))) return d;
    const sale = (f: cli.JsonFila) => !f.hecho && (salido.get(claveSalida(f.proveedor ?? '', f.id || f.ref)) ?? -1) > de;
    return d.pendientes.some(sale) ? { ...d, pendientes: d.pendientes.map(f => (sale(f) ? { ...f, hecho: true } : f)) } : d;
}

/** El proveedor de una tarea por su dirección (`tarea:T84`), de lo que ya se leyó (sin leer de nuevo): el de su fila
 *  del día; si no está, «tareas», el de siempre (como abre su dirección la página: navegador/app.ts). */
export function proveedorDe(direccion: string): string {
    return cache?.dia.pendientes.find(f => f.direccion === direccion)?.proveedor || 'tareas';
}

/** Cuándo se consultó por última vez a los proveedores (las tareas, el calendario); 0 si nunca. */
export function leidoProveedores(): number { return agenda.hora; }

/** La fecha de hoy aquí (AAAA-MM-DD), para saber si lo guardado es de otro día. */
function hoyAqui(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** El día. `conRed` consulta a los proveedores; sin él se lee solo lo que hay en disco. Lo guardado de
 *  otro día no sirve: pasada la medianoche (o al despertar el laptop) se pide de nuevo, con la agenda. */
export function dia(maxEdad = 45000, conRed = false): Promise<Dia> {
    const hoy = hoyAqui();
    const tocaRed = conRed || Date.now() - agenda.hora > CADA_RED || agenda.fecha !== hoy;
    if (!tocaRed && cache && cache.dia.fecha === hoy && Date.now() - cache.hora < maxEdad) return Promise.resolve(cache.dia);
    // la que va sirve si empezó después del último cambio y trae lo que se pide; si no, otra (la de antes, al volver, se
    // descarta y entrega esta: `leer`)
    if (enCurso && enCurso.generacion === generacion && (enCurso.red || !tocaRed)) return enCurso.promesa;
    const lectura = { red: tocaRed, generacion, promesa: leer(tocaRed, generacion) };
    enCurso = lectura;
    void lectura.promesa.finally(() => { if (enCurso === lectura) enCurso = undefined; });
    return lectura.promesa;
}

async function leer(tocaRed: boolean, desde: number): Promise<Dia> {
    const r = await cli.hoy(!tocaRed);
    // algo cambió mientras se leía (una tarea marcada hecha: olvidarDia): lo leído puede ser de antes, y guardarlo la
    // devolvía a la lista; lo que sirve es una lectura que empezó después (la que ya va, o una nueva con red)
    if (desde !== generacion) return dia(0, true);
    if (!r.datos) {
        // si no se pudo leer, lo de antes sirve solo si es de hoy: el día de ayer mostrado como hoy engaña
        // («ahora» marcaba el último bloque de ayer); mejor decir que no se pudo
        const previo = cache?.dia.fecha === hoyAqui() ? cache.dia : { ...VACIO, fecha: hoyAqui() };
        const d: Dia = { ...previo, error: r.error };
        cache = { dia: d, hora: Date.now() };
        return d;
    }
    const j = r.datos;
    if (tocaRed) {
        agenda = { filas: j.agenda ?? null, hora: Date.now(), fecha: j.fecha ?? '' };
        deProveedores = (j.pendientes ?? []).filter(f => f.proveedor);
        avisarProveedores(j.proveedores?.fallas ?? []);
    }
    // la agenda guardada es de su fecha: en una lectura local de otro día no se mezcla
    const agendaDeHoy = agenda.fecha === (j.fecha ?? '');
    const propios = (j.pendientes ?? []).filter(f => !f.proveedor);
    const d: Dia = {
        ahora: j.ahora ?? new Date().toISOString(),
        fecha: j.fecha ?? '',
        nombreDia: j.dia ?? '',
        semana: j.semana ?? 0,
        agenda: tocaRed ? (j.agenda ?? null) : agendaDeHoy ? agenda.filas : null,
        pendientes: tocaRed || !agendaDeHoy ? (j.pendientes ?? []) : [...propios, ...deProveedores],
        declarados: j.proveedores?.declarados ?? [],
        fallas: j.proveedores?.fallas ?? [],
        generacion: desde,
    };
    cache = { dia: d, hora: Date.now() };
    return d;
}

/** Los proveedores que no contestaron (el calendario, el correo…), en la franja de avisos (web/avisos.ts): una fuente que
 *  falla. Solo con lo que se les preguntó (una lectura con red): la de disco no los consulta. Los que vuelven a contestar
 *  se van. Antes, «caído · …» arriba de cada pantalla del dashboard. */
function avisarProveedores(fallas: string[]): void {
    const ICONO: Record<string, string> = { calendario: I.fecha, correo: I.correo };
    avisos.soloEstos('fuente:proveedor:', fallas.map(f => {
        const i = f.indexOf(': ');
        const nombre = i > 0 ? f.slice(0, i) : f, motivo = i > 0 ? f.slice(i + 2) : '';
        const calendario = nombre.startsWith('calendario');
        return { clave: `fuente:proveedor:${nombre}`, nivel: 'falla' as const, icono: ICONO[nombre] ?? I.alerta, conConexion: true,
            texto: `no se pudo leer ${calendario ? 'el calendario' : nombre}`,
            detalle: `${nombre}${motivo ? `: ${motivo.replace(/[.]$/, '')}` : ''}.${calendario ? ' La agenda es la de la última vez.' : ' Lo demás del día sí se leyó.'}`,
            hacer: `Se vuelve a pedir solo${calendario ? '; si sigue, revisa de dónde sale la agenda' : ' cada pocos minutos'}.`,
            ir: calendario ? { texto: '⚙ calendario', hacer: () => void ui.orden('telar.pestana', 'config', 'calendario') } : undefined };
    }));
}

/** Otro día (la agenda de esa fecha, para el calendario): se consulta a los proveedores y se guarda unos minutos. */
const otros = new Map<string, { dia: Dia; hora: number }>();
export async function diaDe(fecha: string): Promise<Dia> {
    const guardado = otros.get(fecha);
    if (guardado && Date.now() - guardado.hora < CADA_RED) return guardado.dia;
    const desde = generacion;
    const r = await cli.hoy(false, fecha);
    const j = r.datos;
    const d: Dia = j ? {
        ahora: j.ahora ?? new Date().toISOString(), fecha: j.fecha ?? fecha, nombreDia: j.dia ?? '', semana: j.semana ?? 0,
        agenda: j.agenda ?? null, pendientes: j.pendientes ?? [], declarados: j.proveedores?.declarados ?? [],
        fallas: j.proveedores?.fallas ?? [],
    } : { ...VACIO, fecha, error: r.error };
    // lo leído antes de un cambio no se guarda: la próxima vez se pide de nuevo
    if (j && desde === generacion) otros.set(fecha, { dia: d, hora: Date.now() });
    return d;
}

/** Lo leído ya no sirve (algo cambió): la próxima lectura va a la red, y la que ya iba se descarta al volver. */
export function olvidarDia(): void {
    generacion++;
    otros.clear(); cache = undefined; agenda = { filas: null, hora: 0, fecha: '' }; deProveedores = [];
}

// ───────────────────────── la urgencia ─────────────────────────

export interface Pendiente {
    fila: cli.JsonFila;
    ref: string;
    texto: string;
    hilo: string;
    cuando: string;
    dias: number | null;      // los que faltan; negativo si venció
    enCurso: boolean;
    /** lo que dejó un agente trabajando solo («cerrar», «preparado»…), o "" */
    avance: string;
    urgencia: number;
    urgente: boolean;
}

/** Cuántos días vencida pasa a ser deuda: lo que venció hace más ya no es de esta semana ni de lo urgente del día (va
 *  junto, en el filtro «deuda» de «tareas»), y sigue en «todas» y en «vencidas». Vale para tareas y casillas. */
export const DEUDA_DIAS = 30;
/** Si lo que vence en `dias` (negativo: venció) es deuda. */
export const esDeuda = (dias: number | null): boolean => dias !== null && dias < -DEUDA_DIAS;

/** Lo que está por hacer, lo más urgente arriba.
 *
 *  Primero la prioridad (P0 arriba, P3 abajo; lo que no la dice, como una viñeta de un documento, cuenta como
 *  P2, la de una tarea a la que nadie se la puso) y, a igual prioridad, la fecha: lo vencido primero (días
 *  negativos), después lo que vence pronto, y lo que no tiene fecha al final de su prioridad. Lo que está en
 *  curso se adelanta medio día: ya se empezó, y dejarlo a medias cuesta más que no haberlo empezado. Lo que un
 *  agente dejó listo para decidir va arriba de todo. */
export function pendientes(d: Dia, pestana = ''): Pendiente[] {
    const hoy = Date.parse(`${d.fecha || new Date().toISOString().slice(0, 10)}T00:00:00`);
    // lo de un proveedor con pestaña propia (un feed) no es un pendiente: va a su pestaña
    return d.pendientes
        .filter(f => !f.hecho && (f.pestana ?? '') === pestana)
        .map(f => {
            const cuando = f.cuando ?? '';
            const dias = cuando ? Math.round((Date.parse(cuando.slice(0, 10) + 'T00:00:00') - hoy) / 86400000) : null;
            const enCurso = !!f.en_curso;
            // lo que un agente dejó listo para decidir va arriba de todo: es lo más rápido de
            // despachar, y esperando se pudre
            const avance = (f.avance ?? '').split(' ')[0].split(':')[0];
            return {
                fila: f, ref: f.ref || f.id, texto: f.texto, hilo: f.hilo ?? '', cuando, dias, enCurso, avance,
                // la prioridad manda (de a 100.000 días); la fecha solo desempata dentro de ella
                urgencia: avance ? -1e9 + (dias ?? 0) / 1000
                    : (f.prioridad ?? 2) * 1e5 + (dias === null ? 5e4 : Math.max(-4e4, Math.min(4e4, dias))) - (enCurso ? 0.5 : 0),
                urgente: avance ? true : dias !== null ? dias <= 7 : enCurso,
            };
        })
        // en una pestaña de proveedor (un feed) manda el orden del proveedor, que sabe cuál va primero
        .sort((a, b) => pestana ? 0 : a.urgencia - b.urgencia || a.ref.localeCompare(b.ref));
}

/** ¿Lo dejó la persona misma? `de` con uno de sus nombres (esMia), o «yo». Vacío no: no se sabe quién. */
export const delaPersona = (de: string | undefined): boolean => !!de?.trim() && (normalizar(de) === 'yo' || esMia(de));

/** El orden de una pestaña de lectura (un feed: un proveedor con `vista = "lectura"`): primero lo que se mandó la persona
 *  misma (`de`), después por prioridad (alta, media, baja, sin prioridad) y, dentro de cada una, lo más nuevo arriba
 *  (`fecha`; lo que no la dice, después, en el orden del proveedor). Si ninguna fila dice quién la dejó ni su prioridad,
 *  el orden del proveedor, tal cual. No corta nada: todo lo que el proveedor entrega. */
export function ordenLectura(lista: Pendiente[]): Pendiente[] {
    if (!lista.some(p => !!p.fila.de?.trim() || (p.fila.prioridad !== undefined && p.fila.prioridad !== null))) return lista;
    const clave = (p: Pendiente) => ({
        suya: delaPersona(p.fila.de) ? 0 : 1,
        pri: typeof p.fila.prioridad === 'number' ? p.fila.prioridad : 9,
        fecha: p.fila.fecha ?? '',
    });
    // sort es estable: a igual clave, el orden del proveedor
    return lista.map(p => ({ p, k: clave(p) }))
        .sort((a, b) => a.k.suya - b.k.suya || a.k.pri - b.k.pri
            || (a.k.fecha === b.k.fecha ? 0 : !a.k.fecha ? 1 : !b.k.fecha ? -1 : b.k.fecha.localeCompare(a.k.fecha)))
        .map(x => x.p);
}

// ───────────────────────── el dibujo ─────────────────────────

/** Abre una sección del dashboard: su color, su nombre, una cuenta y, a la derecha, sus
 *  atajos y pistas (html de `atajo`/`pista`). Se cierra con `</section>`. El color va en
 *  `--c`, y lo heredan sus filas y el hover de sus atajos. */
export function seccion(nombre: string, color: string, cuenta = '', derecha = ''): string {
    return `<section class="bloque" style="--c: var(--${color})"><h2 class="sec"><span class="marca"></span>`
        + `${esc(nombre)}${cuenta ? `<span class="cuenta">${esc(cuenta)}</span>` : ''}`
        + `${derecha ? `<span class="acciones">${derecha}</span>` : ''}</h2>`;
}

/** Abre el cuerpo de una pantalla entera: una sección sin cabecera, porque su nombre, lo que resume y sus acciones van
 *  en la barra (componentes/pantalla.ts, la pone el núcleo). La tinta en `--c` la heredan sus filas y el hover de sus
 *  atajos. Se cierra con `</section>`. */
export function cuerpo(color: string): string {
    return `<section class="bloque" style="--c: var(--${color})">`;
}

/** Un atajo: la tecla y lo que hace, clicable. El mismo en todas partes: en la cabecera, en
 *  los títulos de sección, arriba del día y en las pestañas de sección. */
export function atajo(tecla: string, nombre: string, accion: string, valor = '', titulo = ''): string {
    // sin tecla (la suya es de otra cosa): solo con un clic
    return `<a class="atajo" data-accion="${esc(accion)}"${valor ? ` data-valor="${esc(valor)}"` : ''}`
        + `${titulo ? ` title="${esc(titulo)}"` : ''}>${tecla ? `<kbd>${esc(tecla)}</kbd>` : ''}<span>${esc(nombre)}</span></a>`;
}

/** Lo mismo, pero solo dice: una tecla que funciona sin ser un botón (`/`, `1–9`). */
export function pista(tecla: string, nombre: string): string {
    return `<span class="atajo pista"><kbd>${esc(tecla)}</kbd><span>${esc(nombre)}</span></span>`;
}

/** El filtro por dueño: «todas», «mías» (sin dueño) y «de otros» (con dueño), con su cuenta. Si
 *  ninguna tarea tiene dueño no hay nada que separar y no se dibuja. */
/** Quién es la persona de esta máquina (`telar config --json`): una tarea sin dueño es suya, y una
 *  asignada a su nombre también. La pone la vista al leer la configuración. */
export const yo = { persona: '', nombres: [] as string[] };

/** Cómo se nombra la persona de esta máquina en lo que la página les escribe a los agentes y en sus notas: su
 *  primer nombre («Ana», de git o de `[persona] nombre`), o su nombre en el bus con mayúscula. */
export const miNombre = (): string =>
    yo.nombres.find(Boolean)?.split(' ')[0] ?? (yo.persona ? yo.persona[0].toUpperCase() + yo.persona.slice(1) : 'la persona');

/** ¿Es mía? Sin dueño, o con uno de mis nombres: la primera palabra basta («Ana» y «Ana Pérez»,
 *  «Anabel» con el nombre de git «Anabel Pérez»), pero entera («Anastasia» no es «Ana»). */
export function esMia(dueno: string): boolean {
    if (!dueno.trim()) return true;
    const primera = (t: string) => normalizar(t).split(/\s+/)[0] ?? '';
    const d = primera(dueno);
    return [yo.persona, ...yo.nombres].some(n => !!n && primera(n) === d);
}

/** ¿Es mía? `vacioEsMio`: una tarea sin dueño es de la persona; una viñeta de un documento sin
 *  responsable no es de nadie (está «sin responsable»). */
function mia(dueno: string, vacioEsMio: boolean): boolean {
    return dueno.trim() ? esMia(dueno) : vacioEsMio;
}

/** Los atributos de una fila para el filtro por dueño: mía y sin responsable. */
export function datosDueno(dueno: string, vacioEsMio = true): string {
    return Object.entries(duenoDe(dueno, vacioEsMio)).map(([k, v]) => ` data-${k}="${esc(v)}"`).join('');
}

/** Lo mismo, como los `datos` de un ítem (componentes/item.ts). */
export function duenoDe(dueno: string, vacioEsMio = true): Record<string, string> {
    // «sin responsable» es lo de un documento que no dice quién: una tarea sin dueño es de la persona, no está sin responsable
    return { dueno, mia: mia(dueno, vacioEsMio) ? '1' : '0', sin: !dueno.trim() && !vacioEsMio ? '1' : '0' };
}

/** El grupo «responsable» de los filtros de una lista (componentes/filtros.ts), cada fila como [dueño, si vacío es mía]:
 *  las mías, las de otros y las sin responsable, cada una con su cuenta. Sin «todas»: otro clic en la que rige la
 *  suelta. Si todas son mías no hay nada que filtrar: null. */
export function grupoDuenos(filas: [string, boolean][]): GrupoFiltro | null {
    const otros = filas.filter(([d]) => d.trim() && !esMia(d)).length;
    const sin = filas.filter(([d, v]) => !d.trim() && !v).length;
    if (!otros && !sin) return null;
    const mias = filas.filter(([d, v]) => mia(d, v)).length;
    return { clave: 'dueno', nombre: 'responsable', activa: '', opciones: [
        { clave: 'mias', nombre: 'mías', cuenta: mias, ayuda: 'las mías: mis tareas sin dueño y lo que está a mi nombre' },
        { clave: 'otros', nombre: 'de otros', cuenta: otros, ayuda: 'de otros: a nombre de otra persona (a quién empujar)' },
        { clave: 'sin', nombre: 'sin responsable', cuenta: sin,
            ayuda: 'sin responsable: pendientes de un proyecto que no dicen quién (tus tareas sin dueño son tuyas)' },
    ] };
}

/** El grupo «área» de los filtros de una lista de tareas: cada área con su cuenta, la más grande primero. Con una sola
 *  área no hay nada que filtrar: null. El script lo aplica a toda `.tarea` con `data-area` de la vista. */
export function grupoAreas(areas: string[]): GrupoFiltro | null {
    const cuenta = new Map<string, number>();
    for (const a of areas) if (a) cuenta.set(a, (cuenta.get(a) ?? 0) + 1);
    if (cuenta.size < 2) return null;
    return { clave: 'area', nombre: 'área', activa: '',
        opciones: [...cuenta].sort((a, b) => b[1] - a[1]).map(([a, n]) => ({ clave: a, nombre: a, cuenta: n, ayuda: `del área «${a}»` })) };
}

/** Una fecha relativa en pocas letras: `-39d` vencida, `hoy`, `mañana`, `3d`. */
export function plazo(dias: number | null): string {
    if (dias === null) return '<span></span>';  // la celda va igual: sin ella, lo de al lado se corre
    if (dias < 0) return `<span class="venc">${dias}d</span>`;
    if (dias === 0) return '<span class="pronto">hoy</span>';
    if (dias === 1) return '<span class="pronto">mañana</span>';
    return `<span class="dim">${dias}d</span>`;
}
