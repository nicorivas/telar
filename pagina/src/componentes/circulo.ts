// El círculo: la firma de telar para decir cómo está algo. Quieto, dice con su tamaño y con cuánto está lleno (la
// prioridad ya es así: ● alta, ◐ media, ○ baja, • sin). En curso, se mueve en su lugar y nada más: el texto de al lado
// no se corre ni cambia de color. Tres movimientos, por cómo termina lo que está pasando:
//
// · `vacia`, se vacía: algo se va (cerrar, archivar o descartar un hilo);
// · `llena`, se llena: algo se completa o llega (marcar hecha una tarea, instalar una versión);
// · `gira`, medio lleno, gira: algo va en camino (un hilo que viaja a otra máquina, un mensaje que se envía, una
//   acción que se está haciendo).
//
// De a cuartos, como los cuadros de un ícono (● ◕ ◑ ◔ ○), no un barrido continuo. El color es el de quien lo lleva (el
// tono de su pieza: tenue lo que se va, remoto lo que viaja). Va dibujado con CSS (media/css/circulo.css), no con la
// letra de íconos: así cabe cualquier tamaño y cualquier llenado. Con «reducir movimiento», queda quieto a medio
// llenar. El catálogo (/componentes) muestra la familia entera y los tres movimientos.

//
// Tres tamaños y ninguno más (punto, chico, grande). Para decir más que «cuánto», los círculos se componen, siempre con
// esos tres: uno dentro de otro, uno al borde de otro, dos que se cruzan (las figuras de abajo). Qué quiere decir cada
// forma está en la gramática visual (componentes/gramatica.ts, «fundamentos» en el catálogo); las figuras todavía no
// las usa ninguna vista.

export type Tam = 'punto' | 'chico' | 'grande';
export type Movimiento = 'vacia' | 'llena' | 'gira';
export type Figura = 'centro' | 'diana' | 'doble' | 'satelite' | 'enlace';

export interface Circulo {
    /** cuánto está lleno, de 0 (un aro) a 1; al vaciarse o llenarse, lo pone el movimiento */
    lleno?: number;
    tam?: Tam;
    mov?: Movimiento;
    /** una figura de varios círculos: ocupa lo de uno grande y no lleva `lleno` ni `tam` */
    figura?: Figura;
}

export const TAMANOS: readonly Tam[] = ['punto', 'chico', 'grande'];

/** Las figuras y cómo se dibujan; lo que dicen, en la gramática. */
export const FIGURAS: readonly { figura: Figura; nombre: string; dibujo: string }[] = [
    { figura: 'centro', nombre: 'centro', dibujo: 'un aro grande con un punto al medio' },
    { figura: 'diana', nombre: 'diana', dibujo: 'un aro grande con uno chico lleno adentro' },
    { figura: 'doble', nombre: 'doble', dibujo: 'un aro grande con un aro chico adentro' },
    { figura: 'satelite', nombre: 'satélite', dibujo: 'un aro chico con un punto afuera, en la esquina; gira' },
    { figura: 'enlace', nombre: 'enlace', dibujo: 'dos aros chicos que se cruzan' },
];

export const MOVIMIENTOS: readonly { mov: Movimiento; nombre: string; cuando: string }[] = [
    { mov: 'vacia', nombre: 'se vacía', cuando: 'algo se va: cerrar, archivar o descartar un hilo' },
    { mov: 'llena', nombre: 'se llena', cuando: 'algo se completa o llega: marcar hecha una tarea, instalar una versión' },
    { mov: 'gira', nombre: 'gira', cuando: 'algo va en camino: un hilo a otra máquina, un mensaje, una acción haciéndose' },
];

/** El círculo, en HTML. */
export function circulo(c: Circulo = {}): string {
    const mov = c.mov ? ` mov-${c.mov}` : '';
    // de las figuras, solo el satélite se mueve: gira, y su punto da la vuelta alrededor del aro (va en camino)
    if (c.figura) return `<span class="circulo tam-grande fig-${c.figura}${c.figura === 'satelite' && c.mov === 'gira' ? mov : ''}"></span>`;
    const clases = `circulo tam-${c.tam ?? 'grande'}${mov}`;
    // al vaciarse o llenarse, el llenado es del movimiento (y de «reducir movimiento»): no se escribe aquí
    if (c.mov === 'vacia' || c.mov === 'llena') return `<span class="${clases}"></span>`;
    const lleno = Math.round(Math.max(0, Math.min(1, c.lleno ?? (c.mov === 'gira' ? .5 : 1))) * 100);
    return `<span class="${clases}" style="--lleno: ${lleno}%"></span>`;
}
