// El cielo de noche (el arte de «personal»): la luna creciente, estrellas que titilan cada una a su ritmo, una estrella
// fugaz de vez en cuando y, abajo, los cerros con una casa que tiene la luz prendida. Al pasar el mouse, todo va más
// rápido y caen más estrellas fugaces. Es una función del tiempo (componentes/arte.ts): el mismo instante da siempre el
// mismo cuadro.

import { registrarArte } from '../arte';
import { azar, lienzo } from './comun';

/** el brillo de una estrella, de apagada a la más fuerte */
const BRILLO = [' ', '·', '·', '+', '*', '+', '·'];

function dibujar(t: number, ancho: number, alto: number, o: { hover: boolean }): string {
    const l = lienzo(ancho, alto);
    const suelo = alto - 2;

    // los cerros: una silueta suave de dos filas, en octavos de letra (▁▂▃…█)
    const cerro = (c: number) => 7.5 + 4.6 * Math.sin(c / 4.4 + .9) + 2.2 * Math.sin(c / 1.9 + 2.1);
    const BLOQUES = ' ▁▂▃▄▅▆▇█';
    const altura = (c: number) => Math.max(1, Math.min(16, Math.round(cerro(c))));
    for (let c = 0; c < ancho; c++) {
        const h = altura(c);
        l.poner(c, alto - 1, BLOQUES[Math.min(8, h)]);
        if (h > 8) l.poner(c, alto - 2, BLOQUES[h - 8]);
    }
    // la casa, en un cerro bajo, con la ventana prendida (titila apenas)
    const casa = 3;
    const piso = alto - 1 - (altura(casa + 1) >= 8 ? 1 : 0);
    for (const [dx, c] of [[0, '╱'], [1, '▔'], [2, '╲']] as const) l.poner(casa + dx, piso - 1, c);
    l.poner(casa, piso, '▏');
    l.poner(casa + 1, piso, Math.sin(t * 1.3) > -.9 ? '▘' : ' ');
    l.poner(casa + 2, piso, '▕');

    // la luna: una esfera alumbrada desde la izquierda, que se apaga hacia su lado de sombra (░ ▒ ▓ █ por cuánto le
    // llega la luz); unas manchas, los mares
    const lx = ancho - 6, ly = 2.3, r = 2.05;
    const LUZ = [' ', '░', '▒', '▓', '█'];
    for (let y = 0; y < suelo; y++) {
        for (let x = ancho - 12; x < ancho; x++) {
            // una letra es casi el doble de alta que ancha: en filas, una columna mide .52
            const px = (x + .5 - lx) * .52 / r, py = (y + .5 - ly) / r;
            const d2 = px * px + py * py;
            if (d2 > 1) continue;
            const pz = Math.sqrt(1 - d2);
            const luz = Math.max(0, -.75 * px - .2 * py + .62 * pz);
            const mar = (px + .25) ** 2 + (py + .15) ** 2 < .06 || (px - .05) ** 2 + (py - .4) ** 2 < .03 ? .55 : 1;
            const k = Math.min(4, Math.round(luz * mar * 4.6));
            if (k) l.poner(x, y, LUZ[k]);
        }
    }

    // las estrellas: lugares fijos (la misma semilla), cada una con su ritmo
    const r1 = azar(7);
    for (let i = 0; i < 22; i++) {
        const x = Math.floor(r1() * ancho), y = Math.floor(r1() * (suelo - .5));
        const ritmo = .6 + r1() * 1.6, fase = r1() * 7;
        if (l.leer(x, y) !== ' ') continue;
        const b = Math.floor(((t * ritmo + fase) % BRILLO.length + BRILLO.length) % BRILLO.length);
        l.poner(x, y, BRILLO[b]);
    }

    // la estrella fugaz: cada tanto cruza bajando hacia la derecha, con su cola
    const cada = o.hover ? 1.6 : 5.5, dura = 1.1;
    const n = Math.floor(t / cada), u = (t % cada) / dura;
    if (u < 1) {
        const r2 = azar(100 + n);
        const x0 = Math.floor(r2() * (ancho * .45)), y0 = Math.floor(r2() * 2);
        const cabeza = Math.floor(u * (ancho * .7));
        const COLA = ['*', '─', '─', '-', '·', '·'];
        for (let k = 0; k < COLA.length; k++) {
            const d = cabeza - k;
            if (d < 0) continue;
            const x = x0 + d, y = y0 + Math.floor(d / 4);
            if (y < suelo && l.leer(x, y) === ' ' || k === 0) if (y < suelo) l.poner(x, y, COLA[k]);
        }
    }
    return l.texto();
}

registrarArte('cielo', {
    nombre: 'cielo',
    que: 'el cielo de noche: luna, estrellas que titilan, una fugaz y la casa con la luz prendida',
    cuadros: dibujar,
    fps: 8,
    alHover: { fps: 24 },
    para: ['personal'],
});
