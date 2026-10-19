// `path` en el navegador: lo poco que usa el dashboard, con rutas POSIX.
export const sep = '/';
export const delimiter = ':';
export function normalize(p: string): string {
    const abs = p.startsWith('/');
    const partes: string[] = [];
    for (const x of p.split('/')) {
        if (!x || x === '.') continue;
        if (x === '..') { if (partes.length && partes[partes.length - 1] !== '..') partes.pop(); else if (!abs) partes.push('..'); }
        else partes.push(x);
    }
    return (abs ? '/' : '') + partes.join('/') || (abs ? '/' : '.');
}
export const join = (...ps: string[]): string => normalize(ps.filter(Boolean).join('/'));
export const resolve = (...ps: string[]): string => normalize(ps.reduce((a, p) => (p.startsWith('/') ? p : `${a}/${p}`), ''));
export const dirname = (p: string): string => { const n = normalize(p); const i = n.lastIndexOf('/'); return i <= 0 ? (n.startsWith('/') ? '/' : '.') : n.slice(0, i); };
export const basename = (p: string, ext = ''): string => { const b = normalize(p).split('/').pop() ?? ''; return ext && b.endsWith(ext) ? b.slice(0, -ext.length) : b; };
export const extname = (p: string): string => { const b = basename(p); const i = b.lastIndexOf('.'); return i > 0 ? b.slice(i) : ''; };
export const isAbsolute = (p: string): boolean => p.startsWith('/');
export function relative(desde: string, hasta: string): string {
    const a = normalize(desde).split('/').filter(Boolean), b = normalize(hasta).split('/').filter(Boolean);
    let i = 0;
    while (i < a.length && i < b.length && a[i] === b[i]) i++;
    return [...a.slice(i).map(() => '..'), ...b.slice(i)].join('/');
}
export default { sep, delimiter, normalize, join, resolve, dirname, basename, extname, isAbsolute, relative };
