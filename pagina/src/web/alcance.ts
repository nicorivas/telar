// Una máquina fuera de línea vista desde la página (telar.alcance): «laptop fuera de línea desde 14:02», sus hilos
// inalcanzables (ni vivos ni dormidos: lo que se sabe de ellos es de antes de que se fuera), lo que les espera en cola
// y lo que se hizo de esa cola al volver.
//
// Una máquina está fuera de línea cuando su foto (`GET /espejos`) envejeció y el nodo de aquí está al día con el bus
// (`al_dia`): con el de aquí sin noticias, todas las fotos envejecen y la que se fue es esta (eso lo dice otro aviso).
// Despertar a uno de sus hilos, o escribirle, no se pierde: el mensaje espera en su casilla del bus, y despertarlo
// queda en cola aquí hasta que vuelva (`POST /despertar` con `cola`).
//
// Solo arma textos y HTML: quien lo pone en la página (web/vigia.ts, vistas/hilos.ts, web/terminal.ts) atiende los
// botones. Así lo prueba pruebas/alcance.mjs, en Node.

import { pieBotones, type Boton } from '../componentes/boton';
import { esc } from '../estilo';
import { C, I } from './iconos';

/** Lo que espera en cola para una máquina (`cola` de su foto): despertar a un hilo cuando vuelva. `cuando`, en segundos. */
export interface Pendiente { id: string; hilo: string; texto?: string; por?: string; cuando: number; intentos?: number }
/** Lo que se hizo de la cola (`hechos`): con su resultado y cuándo (`hecho_en`, en segundos). */
export interface Hecho extends Pendiente { ok: boolean; resultado: string; hecho_en: number }

/** Una de las otras máquinas, como la lee la página: `fuera`, si se sabe que está fuera de línea. */
export interface MaquinaAlcance {
    nombre: string;
    en_linea: boolean;
    edad: number | null;
    fuera?: boolean;
    cola?: Pendiente[];
    hechos?: Hecho[];
}

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const dos = (n: number) => String(n).padStart(2, '0');

/** Desde cuándo, corto, como lo dice telar: «14:02» hoy, «ayer 14:02», «el 20-nov 14:02». `ms`, en milisegundos. */
export function desdeTexto(ms: number | undefined, ahora = Date.now()): string {
    if (!ms) return '?';
    const d = new Date(ms), hoy = new Date(ahora);
    const hora = `${dos(d.getHours())}:${dos(d.getMinutes())}`;
    const dia = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    if (dia(d) === dia(hoy)) return hora;
    if (dia(d) === dia(new Date(dia(hoy) - 12 * 3600 * 1000))) return `ayer ${hora}`;
    return `el ${d.getDate()}-${MESES[d.getMonth()]} ${hora}`;
}

/** Cuándo llegó su última foto, con el reloj de este navegador (la edad la mide el servidor: un teléfono con la hora
 *  corrida no cambia lo que se dice). */
export const desdeDe = (m: Pick<MaquinaAlcance, 'edad'>, ahora = Date.now()): number | undefined =>
    m.edad === null || m.edad === undefined ? undefined : ahora - m.edad * 1000;

/** «laptop fuera de línea desde 14:02». */
export const fueraDeLinea = (m: MaquinaAlcance, ahora = Date.now()): string => `${m.nombre} fuera de línea desde ${desdeTexto(desdeDe(m, ahora), ahora)}`;

/** La máquina `nombre` entre las otras, si se sabe que está fuera de línea; undefined si contesta o no se sabe. */
export const fueraDe = (nombre: string, otras: readonly MaquinaAlcance[]): MaquinaAlcance | undefined =>
    otras.find(m => m.nombre === nombre && m.fuera);

/** Lo que se sabía de un hilo cuando su máquina se fue, en palabras: «dormía», «trabajaba»… ("" si nada que decir). */
export function antes(x: { vivo?: boolean; dormido?: boolean | object | null; atencion?: string }): string {
    if (!x.vivo) return '';
    if (x.dormido) return 'dormía';
    return ({ trabajando: 'trabajaba', espera: 'te esperaba', termino: 'había terminado' } as Record<string, string>)[x.atencion ?? ''] ?? '';
}

/** La ayuda de un hilo inalcanzable: dónde vive, desde cuándo no se sabe de él, y qué se puede hacer igual. */
export function ayudaInalcanzable(m: MaquinaAlcance, x: { vivo?: boolean; dormido?: boolean | object | null; atencion?: string }, ahora = Date.now()): string {
    const a = antes(x);
    return `${fueraDeLinea(m, ahora)}: inalcanzable${a ? ` (cuando se fue, ${a})` : ''}.`
        + '\nDespertarlo o escribirle queda en cola y se hace cuando vuelva.';
}

/** Una línea por lo que espera en cola: «en cola desde 14:05: despertar a Catedral, con un texto». */
export const lineaCola = (p: Pendiente, ahora = Date.now()): string =>
    `en cola desde ${desdeTexto(p.cuando * 1000, ahora)}: despertar a «${p.hilo}»${p.texto ? ', con un texto' : ''}`;

/** Lo que dice la franja de una máquina fuera de línea (web/avisos.ts, sin sus botones): una nota, con sus hilos
 *  abiertos cuando se fue y lo que les espera en cola. null si no hay nada que decir (sin hilos abiertos ni cola). */
export function avisoFuera(m: MaquinaAlcance & { hilos: { vivo?: boolean }[] }, ahora = Date.now()):
    { clave: string; nivel: 'nota'; icono: string; texto: string; detalle: string; hacer: string; desde?: number } | null {
    const vivos = m.hilos.filter(x => x.vivo).length, cola = m.cola ?? [];
    if (!vivos && !cola.length) return null;
    const hilos = vivos === 1 ? 'Su hilo abierto' : `Sus ${vivos} hilos abiertos`;
    return {
        clave: `maquina:${m.nombre}`, nivel: 'nota', icono: I.remoto, desde: desdeDe(m, ahora),
        texto: fueraDeLinea(m, ahora),
        detalle: (vivos ? `${hilos} cuando se fue se ven como estaban, inalcanzables: no se sabe si siguen vivos o dormidos. ` : '')
            + (cola.length ? `${cola.map(p => lineaCola(p, ahora)).join('; ')}.` : ''),
        hacer: 'Despertar a uno, o escribirle, queda en cola y se hace cuando vuelva. Si debería estar encendida, revisa su red y su telar serve.',
    };
}

/** Lo que se hizo de la cola de una máquina en la última media hora, como notas de la franja: que la persona sepa que
 *  lo que pidió con la máquina apagada se hizo (o no). */
export function avisosHechos(m: MaquinaAlcance, ahora = Date.now(), dura = 30 * 60 * 1000):
    { clave: string; nivel: 'nota' | 'falla'; icono: string; texto: string; detalle: string; desde: number }[] {
    return (m.hechos ?? []).filter(h => ahora - h.hecho_en * 1000 < dura).map(h => ({
        clave: `cola:${m.nombre}:${h.id}`, nivel: h.ok ? 'nota' as const : 'falla' as const, icono: h.ok ? I.retomar : I.alerta,
        desde: h.hecho_en * 1000,
        texto: h.ok ? `«${h.hilo}» despertó en ${m.nombre} al volver` : `«${h.hilo}» no se pudo despertar en ${m.nombre}`,
        detalle: `Lo pediste ${desdeTexto(h.cuando * 1000, ahora) === desdeTexto(h.hecho_en * 1000, ahora) ? 'recién' : `a las ${desdeTexto(h.cuando * 1000, ahora)}`}, con ${m.nombre} fuera de línea: ${h.resultado}.`,
    }));
}

/** El cuadro de un hilo de una máquina fuera de línea, en su terminal (o, con `conversacion`, en su conversación, la
 *  vista del teléfono): qué pasa, lo que le espera en cola y la banda de botones (componentes/boton.ts: «la tecla en el
 *  pie», con el ícono de cada uno en el lugar de la tecla). Los botones llevan `data-accion`: `despertar` (en cola para
 *  cuando vuelva) y, en la terminal, `escribirle` (su conversación, que tiene la caja) y `reintentar`. */
export function panelFuera(hilo: string, m: MaquinaAlcance, ahora = Date.now(), o: { conversacion?: boolean } = {}): string {
    const suyos = (m.cola ?? []).filter(p => p.hilo === hilo);
    const enCola = suyos.length > 0;
    const botones: Boton[] = [
        { texto: enCola ? 'ya en cola' : 'despertar al volver', accion: 'despertar', icono: I.retomar, color: C.hecho,
            ayuda: enCola ? 'ya espera en cola: se despierta cuando vuelva' : `que se despierte cuando ${m.nombre} vuelva (queda en cola aquí)`,
            ...(enCola ? { estado: 'deshabilitado' as const } : {}) },
        ...o.conversacion ? [] : [
            { texto: 'escribirle', accion: 'escribirle', icono: I.conversacion, color: C.ir,
                ayuda: 'su conversación, con la caja para escribirle: el mensaje espera en el bus y le llega al volver' },
            { texto: 'reintentar', accion: 'reintentar', icono: I.retomar, color: C.otro, ayuda: 'volver a abrir su terminal' }],
    ];
    const que = o.conversacion
        ? `«${esc(hilo)}» vive allá: su conversación se ve cuando vuelva ${esc(m.nombre)}. Lo que le escribas abajo espera en el bus y le llega al volver.`
        : `«${esc(hilo)}» vive allá: su terminal vuelve cuando vuelva ${esc(m.nombre)}. Lo que se sabe de él es de antes de que se fuera.`;
    return `<div class="titulo"><span class="i">${esc(I.remoto)}</span> ${esc(fueraDeLinea(m, ahora))}</div>`
        + `<div class="motivo">${que}</div>`
        + suyos.map(p => `<div class="motivo cola">${esc(lineaCola(p, ahora))}</div>`).join('')
        + pieBotones(botones);
}
