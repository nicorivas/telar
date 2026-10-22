// Dónde hay rutas de archivo, direcciones web y direcciones de objetos (`tarea:T366`) en un texto, y en lo que
// muestra la terminal de un hilo. Una línea
// larga llega a la terminal partida en filas de dos maneras: la parte la terminal al llegar al borde (xterm marca la
// fila de abajo `isWrapped`), o la parte el programa antes de escribirla, con saltos de línea de verdad. Claude Code
// hace lo segundo: su Ink corta el texto al ancho de la caja, y una palabra más larga que la caja (una dirección,
// una ruta) la reparte en pedazos, uno por fila. Esas filas se juntan aquí. Sin página ni API: lo usa
// rutas-agente.ts, que abre lo que se encuentra, y lo prueba pruebas/enlaces.mjs.

/** Las extensiones que se reconocen: las de los archivos de texto que el visor muestra. */
const EXTENSIONES = 'md|markdown|txt|toml|ya?ml|json|py|ts|js|mjs|sh|css|html|csv';

/** Una ruta a un archivo de texto: `/…`, `~/…` o relativa, con letras con tilde (`métodos/`), y quizás con
 *  `:línea` o `:línea:columna` detrás (se ignoran). No la de una dirección (`https://…/x.md`): lo de antes no puede
 *  ser parte de una ruta ni `:`. */
export const RUTA = new RegExp(String.raw`(?<![\p{L}\p{N}_/.~:@+-])(?:~?\/)?(?:[\p{L}\p{N}_.@+-]+\/)*[\p{L}\p{N}_@+-][\p{L}\p{N}_.@+-]*\.(?:${EXTENSIONES})(?::\d+){0,2}(?![\p{L}\p{N}_/-])`, 'gu');

/** Una dirección web escrita como texto. Lo que la cierra en una frase no es suyo: lo quita `sinCola`. */
const WEB = /\bhttps?:\/\/[^\s<>"'`]+/g;

/** Los tipos de objeto de una dirección (`tipo:id`, /api/objetos/tipos): los de telar hasta que la página sabe los
 *  de su máquina, que pueden traer más (los de sus módulos: `usarTipos`). */
let DIRECCION = direccion(['archivo', 'hilo', 'proyecto', 'tarea']);

/** La dirección de un objeto: un tipo conocido, «:» y su id hasta un espacio, una comilla, un paréntesis o una coma
 *  (con `@máquina`, quizás, al final). No pegada detrás de una letra, `/`, `.` o `@`: ni `subtarea:x` ni lo de una
 *  web (`https://x:y`). El punto que cierra la frase no es suyo (lo quita `buscar`). */
function direccion(tipos: string[]): RegExp {
    const nombres = [...tipos].sort((a, b) => b.length - a.length).map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    return new RegExp(String.raw`(?<![\p{L}\p{N}_/.@-])(?:${nombres}):[^\s"'()<>,\[\]{}\x60]+`, 'gu');
}

/** Los tipos de dirección que sabe la máquina de la página. */
export function usarTipos(tipos: string[]): void { if (tipos.length) DIRECCION = direccion(tipos); }

/** Una dirección sin la puntuación que la sigue en la frase: un punto, una coma, una comilla, o un paréntesis de
 *  cierre que no abrió adentro (el de `…/Borges_(escritor)` sí es suyo). */
function sinCola(url: string): string {
    const pares: Record<string, string> = { ')': '(', ']': '[', '}': '{' };
    let u = url;
    for (;;) {
        const c = u.at(-1) ?? '';
        const abre = pares[c];
        if (/[.,;:!?'"»”’]/u.test(c) || (abre && u.split(abre).length < u.split(c).length)) u = u.slice(0, -1);
        else return u;
    }
}

/** Lo que se lee de la pantalla de xterm (la de la página, y la de @xterm/headless en la prueba). */
export interface Pantalla {
    getLine(y: number): { readonly isWrapped: boolean; readonly length: number;
        getCell(x: number): { getChars(): string; getWidth(): number } | undefined } | undefined;
}

/** Una celda de la pantalla, contada desde 1, como en los enlaces de xterm. */
export interface Celda { x: number; y: number }

/** Una ruta o una dirección de la pantalla, y las celdas donde empieza y termina. */
export interface Hallazgo { tipo: 'ruta' | 'web' | 'direccion'; texto: string; desde: Celda; hasta: Celda }

/** Cuántas columnas puede dejar libres a la derecha una fila que sigue en la de abajo: la caja de Ink puede tener
 *  margen. */
const HOLGURA = 2;

/** Hasta cuántas filas arriba y abajo se busca cómo sigue una línea. */
const ALCANCE = 60;

/** Un texto sacado de filas seguidas, con la celda de cada letra (una letra ancha ocupa dos), y dónde se juntaron
 *  dos filas que el programa partió: `en`, la letra donde empieza la de abajo; `ancho`, cuánto cabe en esa fila. */
interface Tira { texto: string; celdas: Celda[]; juntas: { en: number; ancho: number }[] }

function fila(pantalla: Pantalla, i: number): (Tira & { partida: boolean }) | undefined {
    const linea = pantalla.getLine(i);
    if (!linea) return undefined;
    let texto = '';
    const celdas: Celda[] = [];
    for (let x = 0; x < linea.length; x++) {
        const c = linea.getCell(x);
        if (!c || c.getWidth() === 0) continue;
        const letras = c.getChars() || ' ';
        texto += letras;
        for (let k = 0; k < letras.length; k++) celdas.push({ x: x + 1, y: i + 1 });
    }
    return { texto, celdas, juntas: [], partida: linea.isWrapped };
}

/** Si la fila `b` sigue a la `a` aunque el programa haya puesto un salto entre ellas: `a` llega hasta el borde, y
 *  `b` tiene algo. Lo que se junta es `a` hasta su última letra con `b` desde la primera (sin la sangría). Que
 *  lleguen al borde no basta: una palabra corta también puede terminar justo ahí. Lo decide `hallar`. */
function junta(a: Tira, b: Tira, cols: number): { fin: number; ini: number; ancho: number } | undefined {
    const fin = a.texto.trimEnd().length, ini = b.texto.length - b.texto.trimStart().length;
    if (!fin || ini >= b.texto.length || a.celdas[fin - 1].x < cols - HOLGURA) return undefined;
    return { fin, ini, ancho: a.celdas[fin - 1].x - b.celdas[ini].x + 1 };
}

/** Las rutas y direcciones (web y de objetos) de un texto, con sus posiciones en él. Si dos se pisan, queda la más
 *  larga. */
export function buscar(texto: string): { tipo: Hallazgo['tipo']; texto: string; i: number; j: number }[] {
    const todas = [
        ...[...texto.matchAll(RUTA)].map(m => ({ tipo: 'ruta' as const, texto: m[0], i: m.index, j: m.index + m[0].length })),
        ...[...texto.matchAll(WEB)].map(m => {
            const url = sinCola(m[0]);
            return { tipo: 'web' as const, texto: url, i: m.index, j: m.index + url.length };
        }),
        ...[...texto.matchAll(DIRECCION)].map(m => {
            const d = m[0].replace(/[.;:!?…»”’]+$/u, '');
            return { tipo: 'direccion' as const, texto: d, i: m.index, j: m.index + d.length };
        }).filter(h => !h.texto.endsWith(':') && h.texto.indexOf(':') < h.texto.length - 1),
    ].sort((a, b) => (b.j - b.i) - (a.j - a.i));
    const quedan: typeof todas = [];
    for (const h of todas) if (!quedan.some(q => h.i < q.j && q.i < h.j)) quedan.push(h);
    return quedan.sort((a, b) => a.i - b.i);
}

/** Las rutas y direcciones que tocan la fila `y` (desde 1) de la pantalla, de `cols` columnas. Primero las de su
 *  línea como la armó la terminal. Después, juntando además las filas que llegan al borde, las que cruzan una de
 *  esas juntas y son más largas que lo que cabe en la fila de abajo: Ink solo parte una palabra que no cabe en una
 *  fila entera, y si no la parte, no la cortó él. Una de esas reemplaza a las de la línea que pisa (su pedazo). */
export function hallar(pantalla: Pantalla, cols: number, y: number): Hallazgo[] {
    // la línea de la terminal: las filas que ella partió
    let ini = y - 1, fin = y - 1;
    while (ini > 0 && pantalla.getLine(ini)?.isWrapped) ini--;
    while (pantalla.getLine(fin + 1)?.isWrapped) fin++;
    const filas = new Map<number, Tira & { partida: boolean }>();
    const leer = (i: number) => { if (!filas.has(i)) { const f = fila(pantalla, i); if (f) filas.set(i, f); } return filas.get(i); };
    const linea: Tira = { texto: '', celdas: [], juntas: [] };
    for (let i = ini; i <= fin; i++) { const f = leer(i); if (f) { linea.texto += f.texto; linea.celdas.push(...f.celdas); } }
    // y más allá, las que el programa partió: hacia arriba y hacia abajo, mientras sigan
    const sigue = (i: number) => { const a = leer(i), b = leer(i + 1); return !!a && !!b && (b.partida || !!junta(a, b, cols)); };
    while (ini > 0 && ini > y - 1 - ALCANCE && sigue(ini - 1)) ini--;
    while (fin < y - 1 + ALCANCE && sigue(fin)) fin++;
    const larga: Tira = { texto: '', celdas: [], juntas: [] };
    for (let i = ini; i <= fin; i++) {
        const f = leer(i)!, j = i > ini && !f.partida ? junta(leer(i - 1)!, f, cols) : undefined;
        if (j) {
            // la de arriba sin lo que sobra a la derecha, y esta sin su sangría
            const sobra = larga.texto.length - (larga.texto.trimEnd().length);
            larga.texto = larga.texto.slice(0, larga.texto.length - sobra); larga.celdas.length -= sobra;
            larga.juntas.push({ en: larga.texto.length, ancho: j.ancho });
            larga.texto += f.texto.slice(j.ini); larga.celdas.push(...f.celdas.slice(j.ini));
        } else { larga.texto += f.texto; larga.celdas.push(...f.celdas); }
    }
    const celdas = (t: Tira, h: ReturnType<typeof buscar>[number]): Hallazgo =>
        ({ tipo: h.tipo, texto: h.texto, desde: t.celdas[h.i], hasta: t.celdas[h.j - 1] });
    const juntados = buscar(larga.texto).filter(h => {
        const cruza = larga.juntas.filter(j => h.i < j.en && j.en < h.j);
        return cruza.length && cruza.every(j => h.j - h.i > j.ancho);
    }).map(h => celdas(larga, h));
    const orden = (c: Celda) => c.y * 1e5 + c.x;
    const pisa = (a: Hallazgo, b: Hallazgo) => orden(a.desde) <= orden(b.hasta) && orden(b.desde) <= orden(a.hasta);
    const sueltos = buscar(linea.texto).map(h => celdas(linea, h)).filter(h => !juntados.some(j => pisa(h, j)));
    return [...juntados, ...sueltos].filter(h => h.desde && h.hasta && h.desde.y <= y && h.hasta.y >= y);
}
