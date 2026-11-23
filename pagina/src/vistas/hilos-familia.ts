// Quién se ve en la barra de hilos y cómo se anida: lo que vistas/hilos.ts decide antes de dibujar, sin tocar la página
// (así se prueba en Node: npm run prueba:barra).
//
// Un hilo va en HILOS si el modo puesto lo deja ver (por sus etiquetas, o las de su padre si no tiene) y el mundo puesto
// también; si el modo lo deja y el mundo no, va en la fila plegada del final de HILOS («de personal 7»); si el modo no
// lo deja, no se ve. El que se está mirando (el mostrado) se ve siempre, y con él su familia: su cadena de padres, para
// que quede anidado bajo ellos y no suelto, y sus descendientes (hijos, nietos), para que no se queden en «de personal»
// ni escondidos por el modo. Sus hermanos, no: siguen donde los pone su mundo.
//
// Dentro de cada lista, cada hilo va justo bajo su padre (`anidar`), en HILOS y en «de personal» por igual.

/** Lo que separa a un agente del resto en el nombre de un hilo hijo suyo («Secretaría › T454 …», telar.hijos). */
export const HIJO = ' › ';

/** Dónde va un hilo: «lista», HILOS (o su sección, o el archivo); «fuera», la fila plegada de lo que el mundo puesto deja
 *  afuera; «», ninguna: el modo puesto lo esconde. */
export type Lugar = 'lista' | 'fuera' | '';

/** El mostrado, sus padres hasta arriba y sus descendientes, según `padres` (nombre → el del que cuelga; "" o ausente, de
 *  ninguno). Sin mostrado, nadie. Un ciclo de padres no la cuelga. */
export function familiaDe(mostrado: string | undefined, padres: ReadonlyMap<string, string>): Set<string> {
    const familia = new Set<string>();
    if (!mostrado) return familia;
    familia.add(mostrado);
    for (let p = padres.get(mostrado) ?? ''; p && !familia.has(p); p = padres.get(p) ?? '') familia.add(p);
    const hijos = new Map<string, string[]>();
    for (const [n, p] of padres) if (p && p !== n) hijos.set(p, [...hijos.get(p) ?? [], n]);
    const cola = [mostrado];
    for (let n = cola.shift(); n !== undefined; n = cola.shift()) {
        for (const x of hijos.get(n) ?? []) if (!familia.has(x)) { familia.add(x); cola.push(x); }
    }
    return familia;
}

/** Las etiquetas con que el modo mira un hilo: las suyas (`propias`, o las que se saben de él); sin ninguna, las de su
 *  padre, y así hacia arriba (hasta ocho pasos). */
export function heredadas(n: string, propias: readonly string[] | undefined, etiquetas: ReadonlyMap<string, readonly string[]>,
    padres: ReadonlyMap<string, string>): readonly string[] {
    let et = propias ?? etiquetas.get(n) ?? [], x = n;
    for (let i = 0; !et.length && i < 8; i++) { x = padres.get(x) ?? ''; if (!x) break; et = etiquetas.get(x) ?? []; }
    return et;
}

/** Lo que hace falta para repartir los hilos. */
export interface Criterio {
    /** el hilo cuya terminal se muestra */
    mostrado?: string;
    /** nombre → el hilo del que cuelga (su `padre`), de esta máquina y de las otras */
    padres: ReadonlyMap<string, string>;
    /** nombre → sus etiquetas propias */
    etiquetas: ReadonlyMap<string, readonly string[]>;
    /** los nombres de los hilos de los agentes residentes: «Secretaría › T454» cuelga de «Secretaría» (ahí se dibuja) */
    agentes?: readonly string[];
    /** si el modo puesto deja ver estas etiquetas (web/modos.ts, `seVe`) */
    modo: (etiquetas: readonly string[]) => boolean;
    /** si el mundo puesto deja ver este mundo (web/mundo.ts, `seVe`) */
    mundo: (mundo: string | undefined) => boolean;
}

export interface Reparto {
    /** el mostrado y su familia: se ven siempre */
    familia: Set<string>;
    /** dónde va un hilo, con sus etiquetas propias (si no, las que se saben de él) y su mundo */
    donde(nombre: string, etiquetas?: readonly string[], mundo?: string): Lugar;
}

export function repartir(c: Criterio): Reparto {
    // para la familia, el hijo de un agente cuelga del agente, que es bajo quien se dibuja (diga lo que diga su `padre`)
    const agenteDe = (n: string) => c.agentes?.find(a => n.startsWith(`${a}${HIJO}`)) ?? '';
    const padres = new Map([...c.padres].map(([n, p]) => [n, agenteDe(n) || p] as [string, string]));
    if (c.mostrado && !padres.has(c.mostrado)) padres.set(c.mostrado, agenteDe(c.mostrado));
    const familia = familiaDe(c.mostrado, padres);
    return {
        familia,
        donde: (n, et, mu) => familia.has(n) ? 'lista' : !c.modo(heredadas(n, et, c.etiquetas, c.padres)) ? '' : c.mundo(mu) ? 'lista' : 'fuera',
    };
}

/** Una fila puesta bajo su padre: `hondo`, cuántos niveles cuelga; `padre`, la fila de la que cuelga (si quedó bajo ella). */
export interface Anidada<T> { fila: T; hondo: number; padre?: T }

/** Cada fila justo bajo su padre, sangrada, y entre hermanas en el orden de `filas`: el orden manda solo entre las de
 *  arriba (así un hijo nuevo con prioridad 0 no queda lejos de quien lo abrió). El padre de una fila (`padreDe`) cuenta si
 *  está entre `filas` y no es ella misma; si no, la fila va arriba. Lo que queda en un ciclo de padres va al final,
 *  colgado un nivel. Dos filas con el mismo nombre: la primera. */
export function anidar<T>(filas: readonly T[], nombreDe: (f: T) => string, padreDe: (f: T) => string | undefined): Anidada<T>[] {
    const presentes = new Set(filas.map(nombreDe));
    const padre = (f: T) => { const p = padreDe(f) || ''; return p && p !== nombreDe(f) && presentes.has(p) ? p : ''; };
    const hijos = new Map<string, T[]>();
    for (const f of filas) { const p = padre(f); if (p) hijos.set(p, [...hijos.get(p) ?? [], f]); }
    const puestos = new Set<string>(), salida: Anidada<T>[] = [];
    const poner = (f: T, hondo: number, de?: T) => {
        if (puestos.has(nombreDe(f))) return;
        puestos.add(nombreDe(f));
        salida.push(de ? { fila: f, hondo, padre: de } : { fila: f, hondo });
        for (const x of hijos.get(nombreDe(f)) ?? []) poner(x, hondo + 1, f);
    };
    for (const f of filas) if (!padre(f)) poner(f, 0);
    for (const f of filas) poner(f, 1);
    return salida;
}
