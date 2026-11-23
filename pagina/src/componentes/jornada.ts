// La jornada: el día en una línea. Responde de un vistazo cuánto tiempo libre queda hasta la próxima reunión y qué
// viene después: una barra que es el día entero (como una barra de carga, con la hora de ahora marcada) y una línea de
// texto, «libre 1h 20 → 11:30 Daily · 13:00 Comité». Las unidades van pegadas al número: «1h 20», «45min».
//
//   ━━━━━━━━━━██━━━━━│━━━━━━███━━━━━███████━━━━━   libre 1h 20 → 11:30 Revisión de diseño · 15:00 Comité
//   lo que ya pasó   ahora     la próxima
//
// Cuenta como reunión solo lo que es con otras personas (una cita: `clase: 'reunion'`); un bloque propio o la rutina
// (el almuerzo) se dibujan, más tenues, pero no cortan lo libre. De una cita importa lo que la persona respondió a la
// invitación (`respuesta`, la de `telar hoy`): la rechazada no se dibuja ni cuenta (lo que llega solo para estar al
// tanto, lo rechaza, y no le ocupa el tiempo); la aceptada, la tentativa y la que organiza ella (sin respuesta) son
// reuniones. La que no ha respondido también corta lo libre (lo sin responder es lo que todavía no mira, no lo que
// no va a ir), pero se dibuja solo con su borde, como la cita sin aceptar del calendario, y el texto lo dice cuando
// es la de ahora o la próxima: «libre 40min → 11:30 Comité (sin responder)». Sin reuniones en el día, o con el día ya
// terminado (pasada la última reunión y el fin de la jornada), no dice nada: `leer` da null y `jornada` un texto vacío.
//
// Lo que se ve lo decide el ancho que le dan (es un contenedor: jornada.css): con holgura, la barra y el texto entero;
// después, sin lo que viene más tarde; después, «1h 20 → 11:30»; después, «1h 20»; y al final nada. En la cabecera de
// la página es lo primero que cede (marco.css). Los datos los pone quien la usa (en la página, web/jornada.ts, con la
// agenda de `telar hoy`); el componente no lee nada. En el catálogo, /componentes#jornada.
//
// La barra es fina y es el día entero: la pista es lo libre que viene, lo que ya pasó se llena (tenue), las reuniones
// van en su azul (lo propio, tenue) y ahora es una raya. Se eligió el 17-nov entre tres (una franja con las horas
// adentro y una en letras, de terminal): docs/propuestas/componentes.md, «El día en una línea».

import { esc } from '../estilo';

/** De qué es un tramo del día: una reunión (con otras personas), un bloque propio o la rutina. */
export type Clase = 'reunion' | 'bloque' | 'rutina';

/** Lo que la persona respondió a una invitación (el `respuesta` de `telar hoy`); vacío si no aplica: un evento propio,
 *  o uno que organiza ella. */
export type Respuesta = '' | 'aceptada' | 'rechazada' | 'tentativa' | 'sin_responder';

/** Un tramo del día, en minutos desde la medianoche. */
export interface Tramo { inicio: number; fin: number; titulo: string; clase: Clase; respuesta?: Respuesta }

/** Si se dibuja: todo menos lo rechazado. */
export const seDibuja = (t: Tramo): boolean => t.respuesta !== 'rechazada';

/** Si ocupa el tiempo de la persona, y corta lo libre: una reunión que no rechazó (la sin responder, también). */
export const ocupa = (t: Tramo): boolean => t.clase === 'reunion' && t.respuesta !== 'rechazada';

/** Una reunión que todavía no responde: se dibuja con su borde, y el texto lo dice. */
const sinResponder = (t?: Tramo): boolean => t?.clase === 'reunion' && t.respuesta === 'sin_responder';

/** Cómo se dibuja un tramo: su clase, y la reunión sin responder, además, con su marca. */
const comoSeDibuja = (t: Tramo): string => (sinResponder(t) ? 'reunion sin-responder' : t.clase);

export interface Jornada {
    /** la hora de ahora, en minutos desde la medianoche */
    ahora: number;
    /** lo que abarca la barra, en minutos: el comienzo y el fin de la jornada */
    desde: number;
    hasta: number;
    tramos: Tramo[];
}

/** Lo que dice el texto: cómo está ahora (libre, en una reunión, o sin más reuniones) y lo que sigue. */
export interface Lectura {
    estado: 'libre' | 'reunion' | 'fin';
    /** cuánto dura lo de ahora, en minutos: lo libre hasta la próxima, o lo que queda de la reunión */
    dura: number;
    /** hasta cuándo, en minutos */
    hasta: number;
    /** la reunión en curso */
    actual?: Tramo;
    /** la próxima reunión después de lo de ahora */
    siguiente?: Tramo;
    /** en una reunión: lo libre entre su fin y la siguiente (0: pegadas) */
    libreDespues?: number;
    /** las reuniones que vienen después de la siguiente (hasta dos) */
    resto: Tramo[];
}

/** Menos que esto libre, y se avisa: el color del cuidado. */
export const POCO = 10;

/** Cómo está el día ahora. Null si no hay nada que decir: ninguna reunión, o ya pasó la última y terminó la jornada. */
export function leer(j: Jornada): Lectura | null {
    // a la misma hora, primero la que respondió: es la que se nombra
    const rs = j.tramos.filter(t => ocupa(t) && t.fin > t.inicio)
        .sort((a, b) => a.inicio - b.inicio || Number(sinResponder(a)) - Number(sinResponder(b)) || a.fin - b.fin);
    if (!rs.length) return null;
    const ultima = Math.max(...rs.map(r => r.fin));
    if (j.ahora >= Math.max(j.hasta, ultima)) return null;
    const despuesDe = (m: number, incluida: boolean) => rs.find(r => (incluida ? r.inicio >= m : r.inicio > m));
    const restoDe = (s?: Tramo) => (s ? rs.filter(r => r.inicio > s.inicio).slice(0, 2) : []);
    const actual = rs.find(r => r.inicio <= j.ahora && j.ahora < r.fin);
    if (actual) {
        // las que se pisan con ella son un solo rato ocupado; la que empieza justo cuando termina, no: es lo que sigue
        let fin = actual.fin;
        for (const r of rs) if (r.inicio < fin && r.fin > fin) fin = r.fin;
        const siguiente = despuesDe(fin, true);
        return { estado: 'reunion', dura: fin - j.ahora, hasta: fin, actual, siguiente,
            libreDespues: siguiente ? siguiente.inicio - fin : undefined, resto: restoDe(siguiente) };
    }
    const siguiente = despuesDe(j.ahora, false);
    if (!siguiente) return { estado: 'fin', dura: Math.max(0, j.hasta - j.ahora), hasta: j.hasta, resto: [] };
    return { estado: 'libre', dura: siguiente.inicio - j.ahora, hasta: siguiente.inicio, siguiente, resto: restoDe(siguiente) };
}

/** «40min», «1h», «1h 20»: la unidad pegada al número. */
export function duracion(m: number): string {
    const n = Math.max(1, Math.round(m));
    if (n < 60) return `${n}min`;
    const h = Math.floor(n / 60), r = n % 60;
    return r ? `${h}h ${String(r).padStart(2, '0')}` : `${h}h`;
}

/** «9:00», «13:30». */
export function hora(m: number): string {
    const n = Math.round(m);
    return `${Math.floor(n / 60) % 24}:${String(n % 60).padStart(2, '0')}`;
}

const sp = (clase: string, html: string) => `<span class="${clase}">${html}</span>`;

/** El nombre de una reunión en el texto: su título y, si no ha respondido, «(sin responder)», tenue. */
const nombre = (t?: Tramo): string => `${esc(t?.titulo ?? '')}${sinResponder(t) ? sp('j-sin', ' (sin responder)') : ''}`;

/** La línea de texto: cada parte con su clase, para que el ancho decida cuáles quedan (jornada.css). */
export function texto(l: Lectura): string {
    const mas = l.resto.length ? sp('j-mas', l.resto.map(r => ` · ${sp('j-hora', hora(r.inicio))} ${esc(r.titulo)}`).join('')) : '';
    if (l.estado === 'fin') return sp('jornada-texto', sp('j-dura libre', 'libre') + sp('j-luego', ' el resto del día'));
    const hasta = sp('j-hasta', ` → ${sp('j-hora', hora(l.hasta))}`);
    if (l.estado === 'libre') {
        const dura = sp(`j-dura libre${l.dura < POCO ? ' poco' : ''}`, duracion(l.dura));
        return sp('jornada-texto', sp('j-que', 'libre ') + dura + hasta + sp('j-luego', ` ${nombre(l.siguiente)}`) + mas);
    }
    // en una reunión: cuánto le queda y, cuando termina, lo que sigue (otra pegada, un rato libre, o el resto del día)
    const dura = sp('j-dura reunion', duracion(l.dura));
    const luego = !l.siguiente ? ` ${sp('libre', 'libre')} el resto del día`
        : l.libreDespues ? ` ${sp(`libre${l.libreDespues < POCO ? ' poco' : ''}`, `libre ${duracion(l.libreDespues)}`)} → ${sp('j-hora', hora(l.siguiente.inicio))} ${nombre(l.siguiente)}`
            : ` ${nombre(l.siguiente)}`;
    return sp('jornada-texto', sp('j-que', `en ${nombre(l.actual)} `) + dura + hasta + sp('j-luego', luego) + mas);
}

/** Dónde cae un minuto en la barra, en %. */
const pct = (j: Jornada, m: number) => (100 * (Math.min(Math.max(m, j.desde), j.hasta) - j.desde)) / Math.max(1, j.hasta - j.desde);
const redondo = (x: number) => Math.round(x * 100) / 100;

/** Lo que se dice de un tramo en el globo, entre paréntesis: lo que es si no es una reunión, y de una reunión, si no
 *  está firme. */
const DE: Partial<Record<Respuesta, string>> = { sin_responder: 'sin responder', tentativa: 'tentativa' };
const nota = (t: Tramo) => (t.clase !== 'reunion' ? ` (${t.clase})` : DE[t.respuesta ?? ''] ? ` (${DE[t.respuesta ?? '']})` : '');

/** Lo que dice el globo de la barra: la jornada y cada tramo que se dibuja, con su hora. */
function ayuda(j: Jornada): string {
    const ts = j.tramos.filter(seDibuja).sort((a, b) => a.inicio - b.inicio);
    return `${hora(j.desde)}–${hora(j.hasta)} · ahora ${hora(j.ahora)}${ts.map(t => `\n${hora(t.inicio)}–${hora(t.fin)} ${t.titulo}${nota(t)}`).join('')}`;
}

/** La barra fina: la pista es lo libre que viene; se llena (tenue) lo que ya pasó; las reuniones en su color (la sin
 *  responder, solo su borde), lo propio tenue, lo rechazado no está; ahora, una raya. */
function barra(j: Jornada): string {
    const ahora = pct(j, j.ahora);
    const tramos = j.tramos.filter(t => seDibuja(t) && t.fin > j.desde && t.inicio < j.hasta).map(t => {
        const x = pct(j, t.inicio), w = pct(j, t.fin) - x;
        return `<span class="j-tramo ${comoSeDibuja(t)}${t.fin <= j.ahora ? ' pasado' : ''}" style="inset-inline-start: ${redondo(x)}%; inline-size: ${redondo(w)}%"></span>`;
    }).join('');
    return `<span class="jornada-barra" title="${esc(ayuda(j))}"><span class="j-hecho" style="inline-size: ${redondo(ahora)}%"></span>`
        + `${tramos}<span class="j-ahora" style="inset-inline-start: ${redondo(ahora)}%"></span></span>`;
}

/** El día en una línea, en HTML: la barra y el texto. Vacío si no hay nada que decir (ver `leer`). */
export function jornada(j: Jornada): string {
    const l = leer(j);
    if (!l) return '';
    return `<div class="jornada ${l.estado}"><div class="jornada-fila">${barra(j)}${texto(l)}</div></div>`;
}
