// Las rutas de la máquina que sirve la página (las de los archivos del repositorio), como texto: POSIX,
// sin tocar el disco. Lo que el dashboard arma con ellas lo lee la API.

/** Sin `.`, `..` ni barras de más. */
export function normalizar(p: string): string {
    const abs = p.startsWith('/');
    const partes: string[] = [];
    for (const x of p.split('/')) {
        if (!x || x === '.') continue;
        if (x === '..') { if (partes.length && partes[partes.length - 1] !== '..') partes.pop(); else if (!abs) partes.push('..'); }
        else partes.push(x);
    }
    return (abs ? '/' : '') + partes.join('/') || (abs ? '/' : '.');
}
export const unir = (...ps: string[]): string => normalizar(ps.filter(Boolean).join('/'));
export const esAbsoluta = (p: string): boolean => p.startsWith('/');
/** El último tramo: `a/b/c.md` → `c.md`. */
export const nombre = (p: string): string => normalizar(p).split('/').pop() ?? '';
/** Cómo se llega de `desde` a `hasta`. */
export function relativa(desde: string, hasta: string): string {
    const a = normalizar(desde).split('/').filter(Boolean), b = normalizar(hasta).split('/').filter(Boolean);
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    return [...a.slice(i).map(() => '..'), ...b.slice(i)].join('/');
}
