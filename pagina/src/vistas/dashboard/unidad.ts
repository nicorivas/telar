// Lo que varias pantallas preguntan de una unidad del perfil (`telar proyectos`): de cuál es una carpeta y cómo se la
// nombra en corto. Puro, sin la página: lo usan proyectos.ts, tareas.ts, foco.ts y tactica.ts (y su prueba).

/** Lo que hace falta de una unidad para nombrarla. */
export interface UnidadConNombre { ruta: string; nombre: string; cliente?: string; interno?: boolean }

/** De qué unidad es una carpeta: la más honda de `rutas` que la contiene. Una tarea de
 *  `empresa/operacion/ia/x` es de `empresa/operacion/ia`, no de `empresa`, aunque las dos la contengan. */
export function unidadDe(carpeta: string, rutas: readonly string[]): string {
    let mejor = '';
    for (const r of rutas) if ((carpeta === r || carpeta.startsWith(`${r}/`)) && r.length > mejor.length) mejor = r;
    return mejor;
}

/** Su nombre sin el cliente delante cuando ese cliente es la casa misma (`internos` del perfil: el servidor la marca
 *  `interno`): «Taller · Plan anual» es «Plan anual». Uno de afuera, o sin cliente, queda como está. */
export function sinCasa(p: UnidadConNombre): string {
    if (!p.cliente || !p.interno || !p.nombre.startsWith(p.cliente)) return p.nombre;
    return p.nombre.slice(p.cliente.length).replace(/^\s*·\s*/, '') || p.nombre;
}

/** Cómo se nombra en corto de quién es algo: su cliente, si lo tiene y no es la casa misma; si no, su nombre (sin el
 *  cliente de la casa delante). */
export const nombreCorto = (p: UnidadConNombre): string => (p.cliente && !p.interno ? p.cliente : sinCasa(p));
