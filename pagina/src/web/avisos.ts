// Los avisos de la página: el estado del sistema y de los hilos que la franja de arriba de la barra muestra
// (componentes/franja.ts, web/franja.ts). Quien sabe algo lo pone y lo quita: la conexión con telar y la sesión
// (web/vigia.ts), una fuente que no se pudo leer (el día, lo que espera, un bloque del dashboard), una terminal
// reconectándose (web/terminal.ts), una página o una versión nueva (web/version.ts).
//
// Lo que se resuelve solo se va solo: quien lo puso lo quita apenas deja de pasar (reconectó, la fuente volvió a
// contestar). Un aviso es uno por clave: ponerlo otra vez lo cambia y conserva desde cuándo pasa.
//
// Una cosa, un lugar: lo que está aquí no se dice además en otra parte de la página. Los toasts (web/interfaz.ts) siguen
// siendo para responder a lo que se aprieta; aquí va lo que pasa aunque nadie apriete nada.
//
// No toca la página: solo guarda y avisa (`alCambiar`). Así lo usan el catálogo y las pruebas.

import type { AvisoFranja, Nivel } from '../componentes/franja';

/** Un aviso con lo que hacen sus botones. `desde` lo pone el almacén la primera vez (o quien sabe desde cuándo pasa). */
export interface Aviso extends Omit<AvisoFranja, 'cuando' | 'acciones' | 'ir'> {
    desde?: number;
    /** cómo decir desde cuándo: «desde las 18:42» (lo que dura: una caída) o «hace 3 min» (lo que pasó); de fábrica, desde */
    cuando?: 'desde' | 'hace' | 'nada';
    /** adónde lleva, dicho, y cómo ir */
    ir?: { texto: string; hacer: () => void };
    acciones?: { id: string; texto: string; ayuda?: string; hacer: () => void }[];
    /** solo vale con conexión: mientras no la hay, no se dice (lo dice el de la conexión: la falla es la misma) */
    conConexion?: boolean;
}

const avisos = new Map<string, Aviso>();
const oyentes = new Set<() => void>();
let firma = '';

/** Lo que se dibuja de un aviso: si cambia, se avisa (un sondeo que pone lo mismo no redibuja). */
const firmaDe = (a: Aviso) => JSON.stringify([a.clave, a.nivel, a.icono, a.texto, a.detalle, a.hacer, a.desde, a.cuando, a.ir?.texto,
    a.acciones?.map(x => [x.id, x.texto, x.ayuda]), a.curso, a.conConexion]);

function avisar(): void {
    const f = [...avisos.values()].map(firmaDe).join('\n');
    if (f === firma) return;
    firma = f;
    for (const o of [...oyentes]) o();
}

/** Poner un aviso (o cambiarlo, si ya estaba: conserva desde cuándo, salvo que el nuevo diga otro). */
export function poner(a: Aviso): void {
    const antes = avisos.get(a.clave);
    avisos.set(a.clave, { ...a, desde: a.desde ?? antes?.desde ?? Date.now() });
    avisar();
}

/** Quitarlo: dejó de pasar. */
export function quitar(clave: string): void {
    if (avisos.delete(clave)) avisar();
}

/** Los avisos de un grupo (`fuente:`), dejando los de `siguen`: los demás dejaron de pasar. Para quien lee varias cosas
 *  de una vez (las fuentes de un día, de lo que espera) y sabe cuáles fallan ahora. */
export function soloEstos(prefijo: string, siguen: Aviso[]): void {
    const nuevas = new Set(siguen.map(a => a.clave));
    for (const k of [...avisos.keys()]) if (k.startsWith(prefijo) && !nuevas.has(k)) avisos.delete(k);
    for (const a of siguen) {
        const antes = avisos.get(a.clave);
        avisos.set(a.clave, { ...a, desde: a.desde ?? antes?.desde ?? Date.now() });
    }
    avisar();
}

export const hay = (clave: string): boolean => avisos.has(clave);
export const de = (clave: string): Aviso | undefined => avisos.get(clave);

/** Los avisos que valen ahora: sin conexión, los que solo valen con ella se callan (la falla es la misma). `ocultos`:
 *  las claves que el modo puesto no muestra. */
export function vigentes(ocultos: (clave: string) => boolean = () => false): Aviso[] {
    const sinConexion = [...avisos.values()].some(a => a.nivel === 'conexion');
    return [...avisos.values()].filter(a => !(sinConexion && a.conConexion) && !ocultos(a.clave));
}

/** Avisar cuando cambia algo. Devuelve cómo dejar de escuchar. */
export function alCambiar(f: () => void): () => void {
    oyentes.add(f);
    return () => { oyentes.delete(f); };
}

/** La hora, «18:42». */
export const hora = (t: number): string => new Date(t).toTimeString().slice(0, 5);

/** «hace 3 min», «hace 2 h», «hace 3 d». */
export function haceCuanto(t: number, ahora = Date.now()): string {
    const s = Math.max(0, Math.round((ahora - t) / 1000));
    if (s < 60) return 'recién';
    if (s < 3600) return `hace ${Math.round(s / 60)} min`;
    if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
    return `hace ${Math.round(s / 86400)} d`;
}

/** Lo que dibuja la franja de un aviso: desde cuándo, ya dicho, y sus botones sin lo que hacen. */
export function paraDibujar(a: Aviso, ahora = Date.now()): AvisoFranja {
    const desde = a.desde ?? ahora;
    // lo de hoy, con la hora; lo de otro día, cuánto hace
    const hoy = new Date(desde).toDateString() === new Date(ahora).toDateString();
    const cuando = a.cuando === 'nada' ? undefined
        : a.cuando === 'hace' || !hoy ? haceCuanto(desde, ahora) : `desde las ${hora(desde)}`;
    return { clave: a.clave, nivel: a.nivel, icono: a.icono, texto: a.texto, detalle: a.detalle, hacer: a.hacer, curso: a.curso,
        cuando, ir: a.ir?.texto, acciones: a.acciones?.map(x => ({ id: x.id, texto: x.texto, ...(x.ayuda ? { ayuda: x.ayuda } : {}) })) };
}

/** Hacer lo de un botón de la lista: una acción (`id`) o ir a su lugar (sin `id`). Devuelve si había qué hacer. */
export function hacer(clave: string, id?: string): boolean {
    const a = avisos.get(clave);
    const f = id ? a?.acciones?.find(x => x.id === id)?.hacer : a?.ir?.hacer;
    if (!f) return false;
    f();
    return true;
}

export type { Nivel };
