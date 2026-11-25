// Del markdown dibujado a su texto fuente, y de vuelta (web/comentarios.ts): lo que hace falta para comentar un archivo.
// La persona selecciona sobre lo dibujado, pero el ancla de un comentario va contra el texto fuente (docs/contratos.md,
// «Los comentarios de un archivo»): ahí los ** y los enlaces cambian el texto, y una lista o una tabla tienen marcas que
// no se ven. Dos piezas, sin DOM (se prueban en Node: pagina/pruebas/documento.mjs):
//
// · Las líneas de cada bloque. `dibujar` convierte el markdown como la página de siempre (markdown-it, sin HTML propio y con
//   los enlaces sueltos) y le pone a cada bloque (párrafo, título, ítem de una lista, fila de una tabla, bloque de código,
//   cita) las líneas de la fuente de donde salió: `data-src="3-5"` (desde la 3 hasta antes de la 5, desde 0). Una
//   selección se busca solo en las líneas de sus bloques.
// · La búsqueda tolerante. Lo que se ve de un trozo de fuente (`visible`) son sus letras y sus números, con lo que no se
//   dibuja fuera (el destino de un enlace, una imagen entera, la marca de un ítem, la línea de un bloque de código, una
//   entidad); y de cada uno, de qué posición de la fuente vino. Una selección se busca así, solo por sus letras y sus
//   números, y gana la que cae más cerca de donde se seleccionó. Lo encontrado se estira a los signos de la selección
//   (los «¿?», los paréntesis) que están pegados en la fuente, saltando las marcas de formato.
//
// Las posiciones son índices de un string de JavaScript (unidades UTF-16), como las guarda el archivo de los comentarios.

import MarkdownIt from 'markdown-it';
import * as frontmatter from './frontmatter';

const md = new MarkdownIt({ html: false, linkify: true });

/** Los bloques que llevan sus líneas: todo el que markdown-it abre con un mapa (y los que no se abren: código, regla). */
const CON_MAPA = (t: { nesting: number; map: [number, number] | null; type: string }) =>
    !!t.map && (t.nesting === 1 || t.type === 'fence' || t.type === 'code_block' || t.type === 'hr');

/** El markdown en HTML, con `data-src="desde-hasta"` (líneas de la fuente, desde 0, sin incluir `hasta`) en cada bloque.
 *  Sin su frontmatter (web/frontmatter.ts: no es texto, va en la barra), pero las líneas siguen siendo las del archivo
 *  entero: las de lo dibujado se corren en las que ocupa el frontmatter, para que un comentario se ancle igual. */
export function dibujar(texto: string): string {
    const fm = frontmatter.leer(texto);
    const env = {};
    const tokens = md.parse(fm ? texto.slice(fm.largo) : texto, env);
    const corre = fm?.lineas ?? 0;
    for (const t of tokens) if (CON_MAPA(t)) t.attrSet('data-src', `${t.map![0] + corre}-${t.map![1] + corre}`);
    return md.renderer.render(tokens, md.options, env);
}

/** `data-src` → [desde, hasta]; undefined si no es uno. */
export function lineas(dato: string | undefined): [number, number] | undefined {
    const m = /^(\d+)-(\d+)$/.exec(dato ?? '');
    return m ? [Number(m[1]), Number(m[2])] : undefined;
}

/** Dónde empieza cada línea del texto (y uno más: el largo, para la línea que no existe). */
export function inicios(texto: string): number[] {
    const r = [0];
    for (let i = 0; i < texto.length; i++) if (texto[i] === '\n') r.push(i + 1);
    r.push(texto.length);
    return r;
}

/** El tramo del texto que ocupan las líneas [desde, hasta). */
export function tramoDeLineas(texto: string, desde: number, hasta: number, ini = inicios(texto)): [number, number] {
    const a = ini[Math.max(0, Math.min(desde, ini.length - 1))];
    const b = ini[Math.max(0, Math.min(hasta, ini.length - 1))];
    return [a, Math.max(a, b)];
}

const LETRA = /[\p{L}\p{N}]/u;
/** Si una unidad del texto cuenta para buscar: una letra o un número. */
export const cuenta = (c: string): boolean => LETRA.test(c);

/** Las letras y los números de un texto, juntos: lo que se compara de una selección. */
export function solo(texto: string): string {
    let s = '';
    for (const c of texto) if (cuenta(c)) s += c;
    return s;
}

/** Lo que no se dibuja de la fuente, como tramos [inicio, fin) del texto entero: el destino de un enlace (`](…)` y la
 *  referencia de uno, `][id]`), una imagen entera, la marca de un ítem de una lista al principio de su línea (`- `, `1.`),
 *  la línea que abre o cierra un bloque de código (con su lenguaje), la definición de una referencia y una entidad. */
export function ocultos(texto: string): [number, number][] {
    const r: [number, number][] = [];
    const todos = (re: RegExp, grupo = 0) => {
        for (const m of texto.matchAll(re)) {
            const i = m.index! + (grupo ? m[0].indexOf(m[grupo]) : 0);
            r.push([i, i + m[grupo].length]);
        }
    };
    todos(/!\[[^\]\n]*\]\([^)\n]*\)/g);                         // ![alt](src): una imagen no tiene texto que seleccionar
    todos(/\]\((?:[^()\n]|\([^()\n]*\))*\)/g);                  // ](destino "título")
    todos(/\]\[[^\]\n]*\]/g);                                   // ][id]
    todos(/^[ \t]*\[[^\]\n]+\]:[^\n]*$/gm);                      // [id]: destino
    todos(/^[ \t]*(?:>[ \t]*)*(?:[-*+]|\d{1,9}[.)])(?=[ \t]|$)/gm); // la marca de un ítem (también dentro de una cita)
    todos(/^[ \t]*(?:`{3,}|~{3,})[^\n]*$/gm);                    // ```lenguaje
    todos(/&(?:#\d+|#x[\da-f]+|[a-z][a-z\d]*);/gi);              // &amp; &#8212;
    return r;
}

/** Lo que se ve del tramo [desde, hasta) del texto: sus letras y sus números (`texto`) y, de cada uno, su posición en el
 *  texto entero (`mapa`). */
export function visible(texto: string, desde = 0, hasta = texto.length, fuera = ocultos(texto)): { texto: string; mapa: number[] } {
    const tapado = new Uint8Array(Math.max(0, hasta - desde));
    for (const [a, b] of fuera) for (let i = Math.max(a, desde); i < Math.min(b, hasta); i++) tapado[i - desde] = 1;
    let s = '';
    const mapa: number[] = [];
    for (let i = desde; i < hasta; i++) {
        const c = texto[i];
        if (tapado[i - desde] || !cuenta(c)) continue;
        s += c;
        mapa.push(i);
    }
    return { texto: s, mapa };
}

/** De las apariciones de `aguja` en `pajar`, la que empieza más cerca de `cerca` (-1 si no hay ninguna). */
export function masCercana(pajar: string, aguja: string, cerca: number): number {
    if (!aguja) return -1;
    let mejor = -1, dist = Infinity;
    for (let i = pajar.indexOf(aguja); i !== -1; i = pajar.indexOf(aguja, i + 1)) {
        const d = Math.abs(i - cerca);
        if (d < dist) { mejor = i; dist = d; }
    }
    return mejor;
}

/** Las marcas de formato que se saltan al estirar un tramo a los signos de la selección. */
const MARCA = /[*_~`\\]/;

/** Estira [inicio, fin) del texto a los signos de la selección que lo rodean en la fuente: los de antes de su primera
 *  letra (`antes`, «¿(») hacia atrás y los de después de la última (`despues`, «?)») hacia adelante, saltando las marcas
 *  de formato que haya entre medio. Lo que no calza se deja: el tramo queda en las letras. */
export function estirar(texto: string, inicio: number, fin: number, antes: string, despues: string): [number, number] {
    let i = inicio;
    for (let k = antes.length - 1, j = inicio - 1; k >= 0; k--) {
        const c = antes[k];
        if (/\s/.test(c)) break;
        while (j >= 0 && MARCA.test(texto[j]) && texto[j] !== c) j--;
        if (j < 0 || texto[j] !== c) break;
        i = j--;
    }
    let f = fin;
    for (let k = 0, j = fin; k < despues.length; k++) {
        const c = despues[k];
        if (/\s/.test(c)) break;
        while (j < texto.length && MARCA.test(texto[j]) && texto[j] !== c) j++;
        if (j >= texto.length || texto[j] !== c) break;
        f = ++j;
    }
    return [i, f];
}

/** Dónde está en la fuente una selección hecha sobre lo dibujado.
 *
 *  - `seleccion`: el texto seleccionado, como se ve.
 *  - `lineas`: las de los bloques donde empieza y termina (de su `data-src`); sin ellas, el texto entero.
 *  - `previo`: lo que se ve desde el principio del primero de esos bloques hasta la selección: dice cuál de varias
 *    apariciones iguales es.
 *
 *  - `fuera`: lo que no se dibuja de la fuente (`ocultos`); en un texto que no es markdown, nada.
 *
 *  Primero tal cual (lo más común: un trozo de un párrafo sin formato); si no, por sus letras y sus números. Si no está
 *  en sus líneas, en el texto entero. undefined si no se encuentra o no tiene letras ni números. */
export function ubicarSeleccion(texto: string, seleccion: string, lineasDe?: [number, number], previo = '',
    fuera = ocultos(texto)): [number, number] | undefined {
    const ini = inicios(texto);
    const intentos: [number, number][] = lineasDe ? [tramoDeLineas(texto, lineasDe[0], lineasDe[1], ini), [0, texto.length]] : [[0, texto.length]];
    const s = seleccion.trim();
    for (const [a, b] of intentos) {
        const trozo = texto.slice(a, b);
        // tal cual: la que cae más cerca de lo que hay antes, contado en lo que se ve
        if (s) {
            const v = visible(texto, a, b, fuera);
            const cerca = solo(previo).length;
            let mejor = -1, dist = Infinity;
            for (let i = trozo.indexOf(s); i !== -1; i = trozo.indexOf(s, i + 1)) {
                const antes = v.mapa.findIndex(p => p >= a + i);
                const d = Math.abs((antes < 0 ? v.texto.length : antes) - cerca);
                if (d < dist) { mejor = i; dist = d; }
            }
            if (mejor >= 0) return [a + mejor, a + mejor + s.length];
        }
        // por sus letras y sus números
        const aguja = solo(s);
        if (!aguja) return undefined;
        const v = visible(texto, a, b, fuera);
        const j = masCercana(v.texto, aguja, solo(previo).length);
        if (j < 0) continue;
        // los signos de la selección antes de su primera letra y después de la última
        const antes = s.slice(0, s.search(LETRA));
        const despues = s.slice(ultimaLetra(s) + 1);
        const [i, f] = estirar(texto, v.mapa[j], v.mapa[j + aguja.length - 1] + 1, antes, despues);
        return fuera.length ? redondear(texto, i, f, fuera) : [i, f];
    }
    return undefined;
}

/** Que la cita no deje una marca a medias: si lleva una sola corrida de `*`, `_`, `~` o `` ` `` (cierra lo que se abrió
 *  antes, o abre lo que se cierra después), toma la que le falta pegada a un borde; si lleva un `[` sin su `]`, toma el
 *  destino del enlace que le sigue (`](…)`), y si lleva un `]` sin su `[`, el `[` de antes. Solo para que se lea entera:
 *  «**62%** de», no «62%** de». */
export function redondear(texto: string, inicio: number, fin: number, fuera = ocultos(texto)): [number, number] {
    let i = inicio, f = fin;
    for (const m of ['*', '_', '~', '`']) {
        const cita = texto.slice(i, f);
        const corridas = cita.match(new RegExp(`\\${m}+`, 'g')) ?? [];
        if (corridas.length % 2 === 0) continue;
        const run = (desde: number, paso: number) => { let k = desde; while (texto[k] === m) k += paso; return k; };
        if (texto[i - 1] === m) i = run(i - 1, -1) + 1;
        else if (texto[f] === m) f = run(f, 1);
    }
    const abre = (texto.slice(i, f).match(/\[/g) ?? []).length, cierra = (texto.slice(i, f).match(/\]/g) ?? []).length;
    if (abre > cierra) {
        const destino = fuera.find(([a]) => a === f);
        if (destino && texto[f] === ']') f = destino[1];
    } else if (cierra > abre && texto[i - 1] === '[') {
        i -= 1;
    }
    return [i, f];
}

/** La posición de la última letra o número de `s` (-1 si no tiene). */
function ultimaLetra(s: string): number {
    for (let i = s.length - 1; i >= 0; i--) if (cuenta(s[i])) return i;
    return -1;
}

/** Una pieza de lo que se ve en la página (un nodo de texto, o lo que sea): su texto. Para ubicar en lo dibujado un tramo
 *  de la fuente sin depender del DOM. */
export interface Pieza { texto: string }

/** Dónde está, en lo dibujado (`piezas`, en orden: los nodos de texto de los bloques del tramo), el tramo [inicio, fin)
 *  de la fuente: la pieza y la posición dentro de ella donde empieza y donde termina. `desde`: dónde empieza en la
 *  fuente lo que muestran las piezas (el primero de sus bloques), para elegir entre apariciones iguales. Un tramo sin
 *  ancho (una marca de «era por aquí») va antes de la primera letra que le sigue. undefined si no se encuentra. */
export function ubicarEnPiezas(texto: string, inicio: number, fin: number, piezas: Pieza[], desde = 0, fuera = ocultos(texto)):
    { de: [number, number]; a: [number, number] } | undefined {
    // lo que se ve de las piezas, con de qué pieza y posición vino cada letra
    let todo = '';
    const donde: [number, number][] = [];
    piezas.forEach((p, k) => {
        for (let i = 0; i < p.texto.length; i++) if (cuenta(p.texto[i])) { todo += p.texto[i]; donde.push([k, i]); }
    });
    const cerca = visible(texto, Math.min(desde, inicio), inicio, fuera).texto.length;
    if (fin <= inicio) {
        // sin ancho: antes de la primera letra que viene después en la fuente
        const sigue = visible(texto, inicio, Math.min(texto.length, inicio + 200), fuera).texto.slice(0, 12);
        const j = sigue ? masCercana(todo, sigue, cerca) : -1;
        if (j < 0) return undefined;
        return { de: donde[j], a: donde[j] };
    }
    const aguja = visible(texto, inicio, fin, fuera).texto;
    const j = masCercana(todo, aguja, cerca);
    if (j < 0) return undefined;
    const ultimo = donde[j + aguja.length - 1];
    return { de: donde[j], a: [ultimo[0], ultimo[1] + 1] };
}
