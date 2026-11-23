// La binaria (el arte de «ambos»): dos mundos que giran uno alrededor del otro, sobre su órbita punteada, el que va
// adelante tapa al de atrás. Al pasar el mouse, giran más rápido. Es una función del tiempo (componentes/arte.ts): el
// mismo instante da siempre el mismo cuadro.

import { registrarArte } from '../arte';
import { azar, lienzo } from './comun';

/** el mundo grande y el chico, dibujados a mano; un espacio aquí no tapa lo de atrás */
const GRANDE = [' .-. ', '(   )', ' \'-\' '];
const CHICO = ['(o)'];

function dibujar(t: number, ancho: number, alto: number): string {
    const l = lienzo(ancho, alto);
    const cx = ancho / 2, cy = alto / 2;
    const A = 10.5, B = 2.6, inclina = -.5;
    // unas estrellas quietas, que titilan despacio
    const az = azar(5);
    for (let i = 0; i < 5; i++) {
        const x = Math.floor(az() * ancho), y = Math.floor(az() * alto), fase = az() * 6;
        l.poner(x, y, Math.sin(t * .9 + fase) > .55 ? '*' : '+');
    }
    // la órbita, punteada a trechos parejos; el centro de los dos, una cruz
    for (let k = 0; k < 18; k++) {
        const a = (k / 18) * 2 * Math.PI;
        l.poner(cx + Math.cos(a) * A, cy + Math.sin(a) * B + Math.cos(a) * inclina, '·');
    }
    l.poner(cx, cy, '◦');
    // los dos, en lados opuestos: una vuelta cada 8 segundos; primero el de atrás
    const a = t * (2 * Math.PI / 8);
    const cuerpos = [
        { a, dibujo: GRANDE, r: 1 },
        { a: a + Math.PI, dibujo: CHICO, r: 1 },
    ].map(c => ({ ...c, x: cx + Math.cos(c.a) * A * c.r, y: cy + Math.sin(c.a) * B * c.r + Math.cos(c.a) * inclina, delante: Math.sin(c.a) }));
    for (const c of cuerpos.sort((p, q) => p.delante - q.delante)) {
        const ox = Math.round(c.x - c.dibujo[0].length / 2 + .5), oy = Math.round(c.y - (c.dibujo.length - 1) / 2);
        c.dibujo.forEach((fila, y) => [...fila].forEach((ch, x) => {
            // el borde se dibuja; adentro del grande, el vacío tapa lo de atrás
            if (ch !== ' ' || (c.dibujo === GRANDE && y === 1 && x > 0 && x < 4)) l.poner(ox + x, oy + y, ch);
        }));
    }
    return l.texto();
}

registrarArte('binaria', {
    nombre: 'binaria',
    que: 'dos mundos que giran uno alrededor del otro: el de «ambos»',
    cuadros: dibujar,
    fps: 8,
    alHover: { fps: 24 },
});
