// Las densidades de la página: cuánto aire lleva cada fila (media/css/tokens.css, la de fábrica, y densidades.css,
// las demás). Solo medidas, nunca colores: cualquier tema va con cualquier densidad. Una se pone en
// <html data-densidad>, y la elige el ajuste `densidad` del modo puesto (web/modos.ts). Los mismos nombres que
// `telar.modos.DENSIDADES`, que valida el ajuste y suma «auto»: amplia en una pantalla táctil, compacta con mouse.

export interface Densidad { clave: string; nombre: string; descripcion: string }

export const DENSIDADES: readonly Densidad[] = [
    { clave: 'compacta', nombre: 'compacta', descripcion: 'la de fábrica: una línea por fila, como la terminal' },
    { clave: 'comoda', nombre: 'cómoda', descripcion: 'más de media línea de aire por fila' },
    { clave: 'amplia', nombre: 'amplia', descripcion: 'para el dedo: filas de unos 40px y acciones más anchas' },
];

export const DE_FABRICA = 'compacta';
/** la que se elige sola: amplia si se apunta con el dedo, compacta con mouse */
export const AUTO = 'auto';
const TACTIL = '(pointer: coarse)';

/** La densidad que se ve con lo pedido: «auto» según el puntero; una que no se conoce, la de fábrica. */
export function resolver(clave: string): string {
    if (clave === AUTO) return typeof matchMedia === 'function' && matchMedia(TACTIL).matches ? 'amplia' : DE_FABRICA;
    return DENSIDADES.some(d => d.clave === clave) ? clave : DE_FABRICA;
}

let pedida = AUTO;

/** Poner una densidad en la página: los tokens de medida cambian solos. */
export function poner(clave: string): void {
    pedida = clave;
    const d = resolver(clave);
    if (document.documentElement.dataset.densidad !== d) document.documentElement.dataset.densidad = d;
}

// con «auto», si cambia el puntero (un teclado y un mouse que se conectan a una tableta), se rehace
if (typeof matchMedia === 'function') matchMedia(TACTIL).addEventListener?.('change', () => { if (pedida === AUTO) poner(AUTO); });
