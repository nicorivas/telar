// La ola: el efecto de hover de fábrica (componentes/arte.ts, `registrarEfecto`). Cuando el mouse o el foco entra en una
// tarjeta, una ola de letras cruza su arte una vez, de izquierda a derecha: la cresta va adelante arriba, ondula, y a su
// paso cambia las letras del dibujo por las suyas (▓ ▒ ░ y la espuma ~) y se las devuelve. Sirve sobre cualquier arte
// (de fábrica, registrado o de un archivo) sin que el arte la programe. Es pura: el mismo cuadro y el mismo instante dan
// lo mismo.
//
//       _.-''''-._            _.~~░▒▒▓░_
//     .' .  '    ·'.   →    .' ~~░▒▒▓  ·'.
//   .----/ ~~ ≈≈  ~~~~ ≈\    .----/ ~~~░▒▒▓░~~~ ≈\

import { registrarEfecto } from '../arte';

/** cuánto tarda en cruzar, en segundos */
export const OLA_DURA = .95;
/** su perfil, desde la cresta hacia atrás: lo que va en cada columna detrás del frente */
const PERFIL = ['▓', '▒', '▒', '░', '~', '~'];
/** cuántas columnas se adelanta la cresta por cada fila hacia arriba (una letra es casi el doble de alta que ancha) */
const INCLINA = .7;

export function ola(cuadro: string, t: number, ancho: number, alto: number): string {
    const filas = cuadro.split('\n').map(l => [...l]);
    const u = Math.max(0, Math.min(1, t / OLA_DURA));
    // el frente en la fila de abajo (arriba va adelantado): empieza con la cresta de arriba recién entrando por la
    // izquierda y termina con la cola de abajo saliendo por la derecha
    const adelanto = INCLINA * (alto - 1);
    const x0 = -2 - adelanto + u * (ancho + PERFIL.length + adelanto + 4);
    for (let y = 0; y < filas.length; y++) {
        const f = filas[y];
        const frente = x0 + INCLINA * (alto - 1 - y) + 1.3 * Math.sin(y * .9 - t * 9);
        for (let x = 0; x < f.length; x++) {
            const d = frente - x;
            if (d < -1 || d >= PERFIL.length) continue;
            const tinta = f[x] !== ' ';
            if (d < 0) { if (tinta) f[x] = '░'; continue; }
            const c = PERFIL[Math.floor(d)];
            // la espuma deja ver el dibujo: solo moja la tinta, y en lo blanco, una de cada tres
            if (c === '~') { if (tinta || (x + y) % 3 === 0) f[x] = '~'; continue; }
            f[x] = c;
        }
    }
    return filas.map(f => f.join('')).join('\n');
}

registrarEfecto('ola', {
    nombre: 'ola',
    que: 'una ola de letras que cruza el arte una vez y se lo devuelve',
    dura: OLA_DURA,
    fps: 40,
    aplicar: ola,
});
