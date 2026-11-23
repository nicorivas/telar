// Lo que comparten los artes de fábrica que se dibujan con una función: un lienzo de letras donde poner y leer, y un
// azar con semilla (el mismo número da siempre la misma serie: el mismo instante, el mismo cuadro).

/** Un lienzo de `ancho` × `alto` letras, en blanco. */
export function lienzo(ancho: number, alto: number) {
    const filas = Array.from({ length: alto }, () => Array<string>(ancho).fill(' '));
    const dentro = (x: number, y: number) => x >= 0 && y >= 0 && x < ancho && y < alto;
    return {
        poner(x: number, y: number, c: string): void { x = Math.round(x); y = Math.round(y); if (dentro(x, y)) filas[y][x] = c; },
        leer(x: number, y: number): string { x = Math.round(x); y = Math.round(y); return dentro(x, y) ? filas[y][x] : ''; },
        texto: (): string => filas.map(f => f.join('')).join('\n'),
    };
}

/** Números entre 0 y 1, siempre los mismos para la misma semilla (mulberry32). */
export function azar(semilla: number): () => number {
    let a = semilla >>> 0;
    return () => {
        a = (a + 0x6d2b79f5) >>> 0;
        let t = a;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}
