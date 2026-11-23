// Qué agentes residentes se ven en un modo (el ajuste `agentes` de `[modos.<n>]`, telar.modos): las carpetas de los que
// se ven, separadas por coma; vacío, todos (como antes de que existiera); «-», ninguno. No se hereda: cada modo dice los
// suyos. Lo elige la grilla de ⚙ modos (vistas/dashboard/config/modos.ts) y lo aplica la sección AGENTES de la barra
// (vistas/hilos.ts). Sin DOM ni red: la prueba es `npm run prueba:modos`.

/** el valor de un modo que no muestra ningún agente (vacío es todos) */
export const NINGUNO = '-';
/** el prefijo de la dirección de un agente (`agente:vigia`), que es también la clave de su sección en la barra */
const PREFIJO = 'agente:';

/** La carpeta de un agente, que es lo que nombra `agentes`, desde su dirección o la clave de su sección. */
export const carpeta = (clave: string): string => clave.startsWith(PREFIJO) ? clave.slice(PREFIJO.length) : clave;

/** Los que nombra un valor de `agentes`; null si son todos. */
export function elegidos(valor: unknown): Set<string> | null {
    const partes = String(valor ?? '').split(',').map(x => carpeta(x.trim())).filter(Boolean);
    if (!partes.length || partes.includes('*')) return null;
    return new Set(partes.filter(x => x !== NINGUNO));
}

/** Si ese agente (su carpeta o su dirección) se ve con ese valor de `agentes`. */
export function seVe(valor: unknown, agente: string): boolean {
    const e = elegidos(valor);
    return !e || e.has(carpeta(agente));
}

/** El valor de `agentes` tras prender o apagar uno, con todos los que hay en su orden: si quedan todos prendidos es
 *  vacío (todos, también los que vengan), y si no queda ninguno, «-». Los que nombraba y ya no están, se van. */
export function alternar(valor: unknown, agente: string, todos: readonly string[]): string {
    const lista = todos.map(carpeta);
    const quien = carpeta(agente);
    const prendidos = new Set(lista.filter(a => seVe(valor, a)));
    if (prendidos.has(quien)) prendidos.delete(quien); else prendidos.add(quien);
    const quedan = lista.filter(a => prendidos.has(a));
    if (quedan.length === lista.length) return '';
    return quedan.length ? quedan.join(', ') : NINGUNO;
}
