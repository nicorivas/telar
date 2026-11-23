// Qué pestañas de DASHBOARD ve un modo (el ajuste `filas` de `[modos.<n>]`, telar.modos): sus claves separadas por coma,
// o `*`, todas. Lo elige la fila «pestañas» de cada modo en ⚙ modos (vistas/dashboard/config/modos.ts) y lo aplica la
// barra (vistas/dashboard/panel.ts, con orden-pestanas.ts); ⚙ mundos muestra la unión de las de sus modos. Sin DOM ni
// red: la prueba es `npm run prueba:modos`.
//
// Cómo se combina con ⚙ pestañas (`[dashboard] orden` y `ocultas`), que vale para todos los modos: una oculta ahí no se
// ve en ningún modo, aunque el modo la nombre; de las demás, cada modo ve las que nombra, en el orden en que las nombra
// (la primera es la vista del modo, a la que lleva ponerlo). Un modo con todas (`*`) las ve en el orden de ⚙ pestañas.

import { I } from './iconos';

/** Los otros nombres de una pestaña en `filas` (orden-pestanas.ts, ALIAS_FILA; telar.modos.ALIAS_PESTANA). */
const ALIAS: Record<string, string> = { tareas: 'revisar' };
const clave = (x: string): string => ALIAS[x] ?? x;

/** Las pestañas que se sacaron del dashboard (el plan, 18-nov-2026; estrategia, 19-nov-2026; telar.config.
 *  PESTANAS_RETIRADAS): un `filas` que todavía las nombra no las cuenta, y escribirlo de nuevo las quita. Un modo que solo
 *  nombraba esas las ve todas, como sin `filas`: así no queda sin ninguna. `telar doctor` lo avisa. */
export const RETIRADAS: readonly string[] = ['plan', 'estrategia'];

/** Lo que nombra un valor de `filas`, sin las retiradas: [] es todas (`*` o nada). */
export function partesDeFilas(valor: unknown): string[] {
    const partes = String(valor ?? '').split(',').map(x => x.trim()).filter(Boolean);
    const vigentes = partes.filter(x => !RETIRADAS.includes(x));
    return vigentes.includes('*') ? [] : vigentes;
}

/** Las que nombra un valor de `filas`, en su orden y sin repetir; null si son todas (`*`, o nada, o solo retiradas). */
export function elegidas(valor: unknown): string[] | null {
    const partes = partesDeFilas(valor);
    if (!partes.length) return null;
    return [...new Set(partes.map(clave))];
}

/** Si ese valor de `filas` muestra esa pestaña. */
export const ve = (valor: unknown, pestana: string): boolean => {
    const e = elegidas(valor);
    return !e || e.includes(clave(pestana));
};

/** Lo que se escribe para esas pestañas: «a, b», o `*`. */
const escribir = (lista: readonly string[] | null): string => (lista ? lista.join(', ') : '*');

/** Lo mismo, sin mirar espacios ni alias: para saber si dos valores dicen lo mismo. */
const igual = (a: unknown, b: unknown): boolean => {
    const x = elegidas(a), y = elegidas(b);
    return x === null || y === null ? x === y : x.join() === y.join();
};

/** El resultado de un clic: el valor de `filas` que queda (null: sin la línea, lo heredado) o, si no se puede, por qué. */
export interface Clic { filas: string | null; error: string }

/** Lo que queda tras un clic en una pestaña de la fila de un modo (`todas`: las que hay, en el orden de ⚙ pestañas):
 *  si la veía, sin ella (si era la última, no: un modo ve al menos una); si no, entra tras la que la precede en ese orden
 *  entre las suyas (o primera), y las demás quedan en su orden. Marcarlas todas es `*`: también las que vengan. Lo que
 *  nombraba y hoy no hay (la de un módulo que se desinstaló) se conserva. Si queda igual a lo heredado (`heredado`, lo
 *  de fábrica o de su base), se quita la línea: null. */
export function alternar(valor: unknown, todas: readonly string[], pestana: string, heredado: unknown): Clic {
    const p = clave(pestana);
    const antes = elegidas(valor) ?? [...todas];
    let despues: string[];
    if (antes.includes(p)) {
        despues = antes.filter(x => x !== p);
        if (!despues.length) return { filas: escribir(antes), error: 'un modo ve al menos una pestaña' };
    } else {
        const i = todas.indexOf(p);
        const previa = todas.slice(0, Math.max(0, i)).reverse().find(x => antes.includes(x));
        despues = [...antes];
        despues.splice(previa === undefined ? 0 : despues.indexOf(previa) + 1, 0, p);
    }
    const nuevo = todas.length && todas.every(x => despues.includes(x)) ? '*' : escribir(despues);
    return { filas: igual(nuevo, heredado) ? null : nuevo, error: '' };
}

/** Lo que deja un clic en «todas»: `*`, o sin la línea si lo heredado ya es todas. */
export const todas = (heredado: unknown): Clic => ({ filas: elegidas(heredado) === null ? null : '*', error: '' });

/** Las pestañas que se ven en un mundo: la unión de las de sus modos (`filas` de cada uno), en el orden de ⚙ pestañas
 *  (`hay`, sin las ocultas) y solo las que hay; null si alguno las ve todas. */
export function delMundo(filasDeSusModos: readonly unknown[], hay: readonly string[]): string[] | null {
    const juntas = new Set<string>();
    for (const f of filasDeSusModos) {
        const e = elegidas(f);
        if (!e) return null;
        e.forEach(x => juntas.add(x));
    }
    return hay.filter(x => juntas.has(x));
}

/** El ícono de una pestaña en la fila de un modo: el de su actitud (táctica, todo), el de lo que muestra, el
 *  correo de su bloque; la de otro bloque, el de los módulos; la de un proveedor, el de lectura. */
export function icono(pestana: string): string {
    const fijas: Record<string, string> = { todo: I.lista, tactica: I.correr, ahora: I.reloj, esperas: I.campana,
        revisar: I.listado, proyectos: I.tabla, calendario: I.fecha, 'bloque:correo': I.correo };
    return fijas[clave(pestana)] ?? (pestana.startsWith('bloque:') ? I.apps : pestana.startsWith('pestana:') ? I.lectura : I.punto);
}
