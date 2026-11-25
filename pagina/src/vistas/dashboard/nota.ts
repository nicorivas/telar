// Lo que dice una nota de la casa, sacado de su markdown con sus palabras, sin generar nada: su título, su resumen y su
// comienzo, para las tarjetas de «conexiones» de una lectura (relaciones.ts, leer.ts). Y cuál es el documento de una
// carpeta, con la misma regla que el servidor. Sin nada de la página (ni DOM ni almacén): lo prueba
// pruebas/nota.mjs en Node.

import * as frontmatter from '../../web/frontmatter';

/** Un texto en markdown cortado a `n` letras, en el último espacio y sin dejar un `código` o una **negrita** abiertos. */
function corto(t: string, n: number): string {
    if (t.length <= n) return t;
    return cerrar(t.slice(0, n).replace(/\s+\S*$/, ''));
}

/** Un texto en markdown cortado a `n` palabras, como `corto`. */
function cortoEnPalabras(t: string, n: number): string {
    const m = [...t.matchAll(/\S+/g)];
    return m.length <= n ? t : cerrar(t.slice(0, m[n - 1].index + m[n - 1][0].length));
}

/** Lo cortado, sin un `código` ni una **negrita** abiertos, y con «…». */
function cerrar(c: string): string {
    if ((c.match(/`/g) ?? []).length % 2) c = c.slice(0, c.lastIndexOf('`'));
    if ((c.match(/\*\*/g) ?? []).length % 2) c = c.slice(0, c.lastIndexOf('**'));
    return `${c.trimEnd().replace(/[\s,;:·—–-]+$/, '')}…`;
}

/** Cuántas palabras del comienzo de una nota se leen en su tarjeta expandida. */
const PALABRAS = 180;
/** Una línea de metadatos: `**Estado**: borrador`, `**Fecha:** 2026-02-24`, `- **Autor**: …` (corta: una que sigue
 *  como un párrafo es texto). */
const META = /^\s*(?:[-*]\s+)?\*\*[^*\n]{1,40}?(?::\*\*|\*\*\s*:)/;
const esMeta = (p: string) => p.split('\n').every(l => META.test(l) && l.length <= 120);
/** Un bloque que no es texto para leer: una tabla, HTML, una imagen sola. */
const NO_TEXTO = /^(\||<|!\[)/;
/** Las secciones que escribe el grafo (sus aristas y su espejo): sus conexiones se leen aparte. */
const DEL_GRAFO = /^#{2,6}\s+(conexiones|referido por)\s*$/i;

const esTitulo = (b: string) => /^\*\*[^*]*\*\*$/.test(b);

/** Lo de markdown que no se dibuja aquí, fuera: un enlace queda en su texto, una imagen y un HTML, nada. */
const llanoMd = (t: string) => t
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
    .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, a: string, b?: string) => b ?? a)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<\/?[a-z][^>]*>/gi, '')
    .replace(/^>\s?/gm, '');

/** Lo que dice una nota, de su markdown: su título (el `titulo:` de su frontmatter, YAML o TOML, o su primer `#`), su resumen (la
 *  línea `>` bajo el título, o su primer párrafo de verdad) y su comienzo (sus primeros párrafos, hasta `PALABRAS`). Sin
 *  el frontmatter, los comentarios, el código, las tablas, las imágenes ni los párrafos de metadatos; un título de
 *  sección va como una línea en negrita, y las secciones del grafo cierran el comienzo. */
export function deLaNota(md: string): { titulo: string; resumen: string; comienzo: string; sigue: boolean } {
    let texto = md.replace(/\r\n?/g, '\n');
    let titulo = '';
    const fm = frontmatter.leer(texto);
    if (fm) {
        titulo = fm.datos.find(([k]) => /^(titulo|title)$/i.test(k))?.[1].split('\n')[0] ?? '';
        texto = texto.slice(fm.largo);
    }
    // fuera los comentarios, el código y las rayas; cada título, en un bloque propio (una lista pegada a su título es
    // texto, no parte del título)
    texto = texto.replace(/<!--[\s\S]*?-->/g, '').replace(/^(```|~~~)[^\n]*\n[\s\S]*?^\1[^\n]*$/gm, '')
        .replace(/^[ \t]*([-*_])([ \t]*\1){2,}[ \t]*$/gm, '').replace(/^(#{1,6}\s.*)$/gm, '\n\n$1\n\n');
    let resumen = '', bajoTitulo = false, palabras = 0, sigue = false;
    const comienzo: string[] = [];
    for (const bloque of texto.split(/\n\s*\n/).map(x => x.trim()).filter(Boolean)) {
        if (/^#\s/.test(bloque)) {
            if (!titulo) titulo = bloque.split('\n')[0].replace(/^#\s+/, '').replace(/[*`\\]/g, '').trim();
            bajoTitulo = true;
            continue;
        }
        const cita = /^>/.test(bloque);
        if (bajoTitulo && cita && !resumen && !comienzo.length && !esMeta(llanoMd(bloque))) {
            // la línea `>` bajo el título es el resumen de la nota: va plegada, y no se repite al leerla
            resumen = llanoMd(bloque);
            continue;
        }
        bajoTitulo = false;
        if (/^#{2,6}\s/.test(bloque)) {
            if (DEL_GRAFO.test(bloque.split('\n')[0])) { sigue = true; break; }
            // un título de sección, recién cuando ya hay texto (antes no ordena nada), y uno vacío lo reemplaza el siguiente
            if (comienzo.length && esTitulo(comienzo[comienzo.length - 1])) comienzo.pop();
            if (comienzo.length) comienzo.push(`**${bloque.split('\n')[0].replace(/^#+\s+/, '').replace(/\*\*/g, '')}**`);
            continue;
        }
        if (NO_TEXTO.test(bloque)) continue;
        const llano = llanoMd(bloque).trim();
        if (!llano || esMeta(llano)) continue;
        if (palabras >= PALABRAS) { sigue = true; break; }
        if (!resumen) resumen = llano;
        const n = (llano.match(/\S+/g) ?? []).length;
        comienzo.push(palabras + n > PALABRAS ? cortoEnPalabras(llano, PALABRAS - palabras) : llano);
        if (palabras + n > PALABRAS) sigue = true;
        palabras += n;
    }
    // un título de sección sin texto debajo no se deja al final
    while (comienzo.length && esTitulo(comienzo[comienzo.length - 1])) comienzo.pop();
    // plegado, en una línea: los ítems de una lista, separados por «·»
    resumen = resumen.replace(/^\s*[-*]\s+/, '').replace(/\n\s*[-*]\s+/g, ' · ').replace(/\s+/g, ' ');
    return { titulo, resumen: corto(resumen, 320), comienzo: comienzo.join('\n\n'), sigue };
}

/** El documento de una carpeta, por lo que tiene (los nombres de sus archivos; una subcarpeta, con su barra): su
 *  README.md; si no, su index.md; si no, el único .md que tenga (sin contar los ocultos); si no, ninguno (''). La misma
 *  regla que el servidor (telar.servicios.tareas, `documento_de`), que revisa contra ella lo que se conecta. */
export function documentoDeCarpeta(archivos: string[]): string {
    const mds = archivos.filter(n => !n.endsWith('/') && !n.startsWith('.') && /\.md$/i.test(n)).sort();
    return mds.find(n => n.toLowerCase() === 'readme.md') ?? mds.find(n => n.toLowerCase() === 'index.md') ?? (mds.length === 1 ? mds[0] : '');
}
