// El telar tejiendo (el arte de «trabajo»): los hilos de la urdimbre bajan desde el peine, la lanzadera cruza de un lado
// al otro dejando la trama, y la tela, con su rombo, crece hacia abajo una pasada a la vez. Al pasar el mouse, teje más
// rápido. Es una función del tiempo (componentes/arte.ts): el mismo instante da siempre el mismo cuadro.

import { registrarArte } from '../arte';

/** cuánto dura una pasada de la lanzadera, en segundos de su reloj */
const PASADA = 1.8;

/** Las bandas de la tela, de arriba abajo, como en un kilim: una raya, una fila de rombos (uno tramado, el otro no) y
 *  una de puntos. Cada pasada teje una fila; la que se ve arriba es la última. */
const BANDAS = ['════', ' ╱╲ ', '╱▒▒╲', '╲▒▒╱', ' ╲╱ ', ' ·  '];
const BANDAS_VACIAS = ['════', ' ╱╲ ', '╱  ╲', '╲  ╱', ' ╲╱ ', '   ·'];

/** La tela en la fila `f` (contada desde la primera pasada: las más nuevas, arriba) y la columna `c`. Los rombos se
 *  alternan, tramado y vacío, y cada vuelta de bandas se corre dos columnas: la tela que baja no se repite igual. */
function tela(f: number, c: number): string {
    const n = BANDAS.length;
    const i = ((-f % n) + n) % n;
    const vuelta = Math.floor(-f / n);
    const x = c + (vuelta % 2 ? 2 : 0);
    const banda = Math.floor(x / 4) % 2 ? BANDAS_VACIAS : BANDAS;
    return banda[i][((x % 4) + 4) % 4];
}

function dibujar(t: number, ancho: number, alto: number): string {
    const p = Math.floor(t / PASADA);
    const u = (t % PASADA) / PASADA;
    // la lanzadera va y vuelve: de izquierda a derecha en las pasadas pares
    const ida = p % 2 === 0;
    const x = Math.round(u * (ancho + 6)) - 3;
    const en = ida ? x : ancho - 1 - x;
    const filas: string[] = [];
    // el peine, arriba
    filas.push(Array.from({ length: ancho }, (_, c) => (c % 2 ? '┬' : '─')).join(''));
    // la urdimbre abierta: los hilos de una pasada suben y los otros bajan (la calada), y se cruzan al cambiar de pasada
    const calada = alto - 7;
    for (let k = 0; k < calada; k++) {
        filas.push(Array.from({ length: ancho }, (_, c) => {
            if (c % 2 === 0) return ' ';
            const arriba = ((c >> 1) + p) % 2 === 0;
            if (k < calada - 1) return '│';
            return arriba ? '╵' : '│';
        }).join(''));
    }
    // la pasada que se teje: detrás de la lanzadera, la trama nueva; delante, la urdimbre sola
    filas.push(Array.from({ length: ancho }, (_, c) => {
        const d = ida ? en - c : c - en;
        if (d === 0) return '◆';
        if (d === 1 || d === -1) return d === 1 ? (ida ? '═' : '═') : (ida ? '▶' : '◀');
        if (d > 1) return tela(p, c);
        return c % 2 ? '│' : ' ';
    }).join(''));
    // la tela ya tejida: la pasada de recién arriba, las viejas abajo
    for (let k = 1; k <= 4; k++) filas.push(Array.from({ length: ancho }, (_, c) => tela(p - k, c)).join(''));
    // el enjulio, donde se enrolla
    filas.push('▀'.repeat(ancho));
    return filas.slice(0, alto).join('\n');
}

registrarArte('telar', {
    nombre: 'telar',
    que: 'un telar tejiendo: la lanzadera cruza y la tela crece, con su rombo',
    cuadros: dibujar,
    fps: 14,
    alHover: { fps: 42 },
    para: ['trabajo'],
});
