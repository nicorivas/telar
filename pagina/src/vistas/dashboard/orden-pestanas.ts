// En qué orden van las pestañas del dashboard (las filas del grupo DASHBOARD de la barra y la lista de ⚙ pestañas):
// lo que dice `[dashboard] orden` y, para lo que no nombra, una regla. La usan el núcleo (panel.ts) y ⚙ (config/), así
// que las dos muestran lo mismo. La prueba: npm run prueba:pestanas.

/** Las de un módulo o un proveedor: un bloque (`bloque:<clave>`) o la pestaña de un proveedor (`pestana:<nombre>`). */
const deModulo = (clave: string): boolean => /^(bloque|pestana):/.test(clave);

/** `todas`, en el orden de siempre (el de fábrica), ordenadas según `orden`: las que nombra, en ese orden. Una de fábrica
 *  que no nombra (una que llegó con una versión nueva, como «te esperan») va tras la que la precede en el orden de
 *  siempre, o primera si no la precede ninguna: así entra donde se pensó y no al final, tras los módulos. Las de los
 *  módulos y los proveedores que no nombra van al final, en su orden: la de un módulo nuevo aparece sola. Sin `orden`,
 *  el de siempre. Las ocultas también se ordenan: quien las muestra decide si se ven. */
export function ordenarPestanas<T>(todas: T[], clave: (x: T) => string, orden: string[]): T[] {
    if (!orden.length) return [...todas];
    const puestas = [...new Set(orden)].map(c => todas.find(x => clave(x) === c)).filter((x): x is T => x !== undefined);
    todas.forEach((x, i) => {
        if (puestas.includes(x) || deModulo(clave(x))) return;
        const antes = todas.slice(0, i).reverse().find(y => puestas.includes(y));
        puestas.splice(antes === undefined ? 0 : puestas.indexOf(antes) + 1, 0, x);
    });
    return [...puestas, ...todas.filter(x => !puestas.includes(x))];
}

/** Los nombres con que un modo puede nombrar una pestaña en `filas`, además de su clave: «tareas» es la de clave
 *  «revisar» (la que abre en foco). */
const ALIAS_FILA: Record<string, string> = { tareas: 'revisar' };

/** Las pestañas de un modo (su ajuste `filas`, web/modos.ts): las que nombra, en el orden en que las nombra y sin las que
 *  no hay (una de un módulo que no se instaló, la de un modo que todavía no llega); `null`, todas, en su orden. */
export function delModo<T>(visibles: T[], clave: (x: T) => string, filas: string[] | null): T[] {
    if (!filas) return visibles;
    return [...new Set(filas.map(f => ALIAS_FILA[f] ?? f))].map(f => visibles.find(x => clave(x) === f)).filter((x): x is T => x !== undefined);
}
