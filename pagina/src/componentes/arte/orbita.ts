// La órbita (el arte de un mundo que no tiene uno): un planeta con anillo, con sus bandas que giran, y una luna que le da
// la vuelta, por delante y por detrás. Es el planeta del ícono de los mundos. Al pasar el mouse, todo gira más rápido. Es
// una función del tiempo (componentes/arte.ts): el mismo instante da siempre el mismo cuadro.

import { registrarArte } from '../arte';
import { azar, lienzo } from './comun';

// el planeta, dibujado a mano: `~` es su superficie (ahí van las bandas), y la fila del anillo que pasa por delante lo
// cruza de lado a lado
const PLANETA = [
    '                              ',
    '           _.-\'\'\'\'-._         ',
    '         .\'~~~~~~~~~~\'.       ',
    '   .----/~~~~~~~~~~~~~~\\----. ',
    '  (    |~~~~~~~~~~~~~~~~|    )',
    '   \'----\\--------------/----\' ',
    '         \'.~~~~~~~~~~.\'       ',
    '           \'-.,____,.-\'       ',
    '                              ',
];
/** las bandas de cada fila: lo que se ve de la superficie, que corre hacia la izquierda a su ritmo (el ecuador, más rápido) */
const BANDAS: Record<number, { dibujo: string; ritmo: number }> = {
    2: { dibujo: ' .   \'   ·    .  \'    ·   . ', ritmo: 1.2 },
    3: { dibujo: '≈≈  ~~~ ≈≈≈   ~~ ≈≈  ~~~~ ≈ ', ritmo: 2.1 },
    4: { dibujo: '  ·  :  .   ·   :   .  ·  : ', ritmo: 2.8 },
    6: { dibujo: ' ·   .  \'   ·   .   \'  ·   ', ritmo: 1.4 },
};

function dibujar(t: number, ancho: number, alto: number): string {
    const l = lienzo(ancho, alto);
    const dx = Math.floor((ancho - PLANETA[0].length) / 2), dy = Math.floor((alto - PLANETA.length) / 2);
    // unas estrellas quietas, atrás, que titilan despacio
    const az = azar(3);
    for (let i = 0; i < 9; i++) {
        const x = Math.floor(az() * ancho), y = Math.floor(az() * alto), fase = az() * 6;
        l.poner(x, y, Math.sin(t * 1.1 + fase) > .6 ? '+' : '·');
    }
    // el planeta, con su superficie que gira
    PLANETA.forEach((fila, y) => [...fila].forEach((c, x) => {
        if (c === ' ') return;
        if (c !== '~') { l.poner(x + dx, y + dy, c); return; }
        const b = BANDAS[y];
        const d = b ? b.dibujo[(((x + Math.floor(t * b.ritmo)) % b.dibujo.length) + b.dibujo.length) % b.dibujo.length] : ' ';
        l.poner(x + dx, y + dy, d);
    }));
    // la luna: una vuelta cada 7 segundos, en una elipse más ancha que el anillo; por detrás del planeta cuando va arriba
    const a = t * (2 * Math.PI / 7);
    const x = ancho / 2 + Math.cos(a) * 14, y = alto / 2 + Math.sin(a) * 3.6 - Math.cos(a) * .6;
    const delante = Math.sin(a) > 0;
    const cubre = (PLANETA[Math.round(y) - dy] ?? '')[Math.round(x) - dx] ?? ' ';
    if (delante || cubre === ' ') l.poner(x, y, delante ? '●' : '•');
    return l.texto();
}

registrarArte('orbita', {
    nombre: 'órbita',
    que: 'un planeta con anillo, sus bandas que giran y una luna que le da la vuelta: el de un mundo sin arte',
    cuadros: dibujar,
    fps: 8,
    alHover: { fps: 24 },
});
