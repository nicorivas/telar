// Lo que trae un archivo arrastrado a la terminal de un hilo (web/terminal.ts), sin tocar la página: qué rutas
// vienen en el arrastre, cómo se escriben en el chat y cómo se dice su tamaño. La regla: si el arrastre trae la
// ruta, se usa; si no (solo `files`: Chrome con el Finder, el Explorador de Windows), se pregunta y se sube. Nunca
// se adivina una ruta, nunca se navega al archivo. Va aparte para probarlo sin navegador (pruebas/arrastre.mjs).
//
// Quién trae la ruta: VS Code (`text/uri-list` con `file://…`, y `text/plain` con la ruta), Safari con el Finder
// (`public.file-url`), una terminal (`text/plain`), Nautilus y Dolphin en Linux (`text/uri-list`).

/** Lo que se le pide a un arrastre: sus tipos y su contenido por tipo (un `DataTransfer`, o uno de prueba). */
export interface Arrastre {
    readonly types: readonly string[];
    getData(tipo: string): string;
}

/** Las líneas con algo de una lista (`text/uri-list` lleva comentarios con `#` y termina con CRLF). */
const lineas = (texto: string): string[] => texto.split(/\r?\n/).map(l => l.trim()).filter(l => l && !l.startsWith('#'));

/** Una dirección `file://` como ruta de esta máquina: sin `file://`, sin host (vacío o `localhost`: uno con otro
 *  nombre es de otra máquina, y no sirve aquí), decodificada (`%20` es un espacio). null si no es una. */
export function rutaDeUrl(url: string): string | null {
    const m = /^file:\/\/([^/]*)(\/.*)$/i.exec(url.trim());
    if (!m) return null;
    const host = m[1].toLowerCase();
    if (host && host !== 'localhost') return null;
    let ruta: string;
    try { ruta = decodeURIComponent(m[2]); } catch { return null; }
    // en Windows la unidad viene después de la barra (file:///C:/Users/…)
    return /^\/[A-Za-z]:\//.test(ruta) ? ruta.slice(1) : ruta;
}

/** Si un texto parece una ruta absoluta: `/…`, `~/…` o `C:\…`. Lo demás (una palabra, una frase) no lo es. */
export const pareceRuta = (texto: string): boolean => /^(\/|~\/|[A-Za-z]:[\\/])/.test(texto);

/** Las rutas que trae un arrastre, en orden; [] si no trae ninguna (entonces, si trae `files`, hay que subirlos).
 *  Se mira primero lo que es una dirección de archivo (`text/uri-list`, `public.file-url`) y después el texto, que
 *  cuenta solo si cada línea es una ruta absoluta o un `file://`: un texto cualquiera no es una ruta. Durante el
 *  arrastre el navegador no deja leer el contenido (solo los tipos): esto sirve al soltar. */
export function rutasDe(a: Arrastre): string[] {
    const de = (tipo: string): string[] => (a.types.includes(tipo) ? lineas(a.getData(tipo)) : []);
    for (const tipo of ['text/uri-list', 'public.file-url']) {
        const rutas = de(tipo).map(rutaDeUrl).filter((r): r is string => r !== null);
        if (rutas.length) return rutas;
    }
    const texto = de('text/plain');
    const rutas = texto.map(l => rutaDeUrl(l) ?? (pareceRuta(l) ? l : null));
    return texto.length && rutas.every(r => r !== null) ? rutas as string[] : [];
}

/** Si el arrastre podría traer archivos (se pregunta durante el arrastre, cuando solo se ven los tipos). */
export const traeArchivos = (tipos: readonly string[]): boolean =>
    ['Files', 'text/uri-list', 'public.file-url'].some(t => tipos.includes(t));

/** Una ruta como la escribe la terminal de VS Code al soltarla: tal cual si es solo de letras, números y `/._-~`
 *  y compañía; si no (un espacio, una comilla, un `$`), entre comillas simples, para que se lea entera. */
export function citar(ruta: string): string {
    if (/^[\w@%+=:,./~-]+$/.test(ruta)) return ruta;
    return `'${ruta.replace(/'/g, `'\\''`)}'`;
}

/** Varias rutas, citadas y separadas por un espacio. */
export const juntar = (rutas: readonly string[]): string => rutas.map(citar).join(' ');

/** Un tamaño legible: `512 B`, `3,4 KB`, `12 MB` (con coma, como el resto de la página). */
export function tamano(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    const [n, unidad] = bytes < 1024 * 1024 ? [bytes / 1024, 'KB'] : [bytes / (1024 * 1024), 'MB'];
    return `${n.toFixed(n < 10 ? 1 : 0).replace('.', ',')} ${unidad}`;
}

/** `texto` insertado en `valor` entre `desde` y `hasta` (la selección de una caja), con un espacio de cada lado si
 *  lo de al lado no lo tiene: la ruta no se pega a lo escrito. El valor nuevo y dónde queda el cursor. */
export function insertar(valor: string, desde: number, hasta: number, texto: string): { valor: string; cursor: number } {
    const antes = valor.slice(0, desde), despues = valor.slice(hasta);
    const pegado = (antes && !/\s$/.test(antes) ? ' ' : '') + texto + (despues && !/^\s/.test(despues) ? ' ' : '');
    return { valor: antes + pegado + despues, cursor: antes.length + pegado.length };
}
