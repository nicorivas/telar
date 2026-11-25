// El frontmatter de un markdown: los datos que van arriba, antes del texto, entre dos rayas. YAML entre `---` y `---`, o
// TOML entre `+++` y `+++`, siempre desde la primera línea (una raya más abajo es una raya). Lo leen la tarjeta de una nota
// (vistas/dashboard/nota.ts: su `titulo:`) y el visor de un documento (web/fuente.ts lo saca antes de dibujar, y la barra
// de la derecha lo muestra en «datos»). Sin DOM: se prueba en Node (pruebas/nota.mjs, pruebas/documento.mjs).
//
// No es un lector de YAML ni de TOML: cada clave de arriba con su valor como está escrito (sin las comillas que lo
// envuelven). Lo que sigue en las líneas de abajo (una lista, un mapa anidado, un arreglo de varias líneas) va con su
// clave, tal cual. En TOML, una tabla (`[autor]`) le pone su nombre delante a las claves que siguen: `autor.nombre`.

export interface Frontmatter {
    formato: 'yaml' | 'toml';
    /** cada clave con su valor, en el orden del archivo */
    datos: [string, string][];
    /** cuántas líneas ocupa, con sus dos rayas: el texto empieza en esa línea (desde 0) */
    lineas: number;
    /** el largo de lo que ocupa, en unidades del string (con el salto de línea de la raya de cierre) */
    largo: number;
}

const RAYA: Record<string, Frontmatter['formato']> = { '---': 'yaml', '+++': 'toml' };

/** El frontmatter al principio de `texto`, o undefined si no empieza con uno (o no se cierra). */
export function leer(texto: string): Frontmatter | undefined {
    const bom = texto.startsWith('﻿') ? 1 : 0;
    const primera = /^(---|\+\+\+)[ \t]*\r?\n/.exec(texto.slice(bom));
    if (!primera) return undefined;
    const raya = primera[1];
    const formato = RAYA[raya];
    let i = bom + primera[0].length, n = 1;
    const dentro: string[] = [];
    while (i <= texto.length) {
        const salto = texto.indexOf('\n', i);
        const fin = salto < 0 ? texto.length : salto;
        const linea = texto.slice(i, fin).replace(/\r$/, '');
        n++;
        if (linea.trimEnd() === raya) {
            return { formato, datos: formato === 'yaml' ? deYaml(dentro) : deToml(dentro), lineas: n, largo: salto < 0 ? fin : salto + 1 };
        }
        dentro.push(linea);
        if (salto < 0) break;
        i = salto + 1;
    }
    return undefined;
}

/** El texto sin su frontmatter (el mismo, si no tiene). */
export function sinFrontmatter(texto: string): string {
    const f = leer(texto);
    return f ? texto.slice(f.largo) : texto;
}

/** Un valor sin las comillas que lo envuelven. */
const sinComillas = (v: string): string => v.replace(/^(["'])([\s\S]*)\1$/, '$2');
/** Un valor de una línea: entre comillas, lo de adentro; si no, sin el comentario del final. */
const valor = (v: string): string => (/^["']/.test(v.trim()) ? sinComillas(v.trim()) : v.replace(/\s+#.*$/, '').trim());

function deYaml(lineas: string[]): [string, string][] {
    const r: [string, string][] = [];
    for (const l of lineas) {
        const m = /^([^\s#:][^:]*?)\s*:(?:\s+(.*)|\s*)$/.exec(l);
        if (m && !/^\s/.test(l) && !l.startsWith('- ')) {
            r.push([sinComillas(m[1].trim()), valor(m[2] ?? '')]);
        } else if (r.length && l.trim() && !/^\s*#/.test(l)) {
            // lo que sigue de la clave de arriba: una lista, un mapa, un texto de varias líneas
            const ultimo = r[r.length - 1];
            ultimo[1] = ultimo[1] ? `${ultimo[1]}\n${l}` : l;
        }
    }
    return r.map(([k, v]) => [k, sangriaComun(v)]);
}

function deToml(lineas: string[]): [string, string][] {
    const r: [string, string][] = [];
    let tabla = '';
    for (const l of lineas) {
        const t = /^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(?:#.*)?$/.exec(l);
        if (t) { tabla = t[1]; continue; }
        const m = /^\s*([A-Za-z0-9_."'-]+)\s*=\s*(.*)$/.exec(l);
        if (m) {
            const clave = m[1].split('.').map(x => sinComillas(x.trim())).join('.');
            r.push([tabla ? `${tabla}.${clave}` : clave, valor(m[2])]);
        } else if (r.length && l.trim() && !/^\s*#/.test(l)) {
            const ultimo = r[r.length - 1];
            ultimo[1] = `${ultimo[1]}\n${l}`;
        }
    }
    return r.map(([k, v]) => [k, sangriaComun(v)]);
}

/** Las líneas de un valor de varias, sin la sangría que tienen todas las de abajo. */
function sangriaComun(v: string): string {
    const ls = v.split('\n');
    if (ls.length < 2) return v;
    const resto = ls.slice(1).filter(l => l.trim());
    const s = Math.min(...resto.map(l => /^\s*/.exec(l)![0].length));
    return [ls[0], ...ls.slice(1).map(l => l.slice(s))].join('\n').trim();
}
