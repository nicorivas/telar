// Lo que hace el buscador (componentes/buscador.ts) en cualquier lugar de la página, sin que cada vista lo repita: el ✕
// que aparece con algo escrito lo borra. Vacía el campo, le devuelve el foco y dispara un `input` que sube, como si se
// hubiera borrado a mano: la vista que lo usa filtra de nuevo con lo que ya escucha (la barra de hilos, el dashboard, una
// ventana). Lo demás (⎋, ⏎, la tecla que lo enfoca, guardar lo buscado) sigue siendo de la vista.
//
// Y `barraDeBuscar`, para quien arma su ventana con elementos (web/interfaz.ts, web/instruccion.ts, web/compartir.ts):
// la barra del componente, ya en el DOM, y su campo.

import { BORRAR, barraBuscar, type PropsBarraBuscar } from '../componentes/buscador';

/** El ✕ de un buscador: vacía su campo y avisa con un `input`. Devuelve si era uno. */
export function borrar(objetivo: EventTarget | null): boolean {
    const x = (objetivo as Element | null)?.closest?.(`[${BORRAR}]`);
    const campo = x?.closest('.buscador')?.querySelector<HTMLInputElement>('input.buscar');
    if (!campo) return false;
    campo.value = '';
    campo.focus();
    campo.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
}

let atendiendo = false;

/** Atiende el ✕ de todos los buscadores de la página (una vez, al arrancar). El clic va en la captura, antes que lo que
 *  escuche la fila de abajo; el `mousedown`, para que el campo no pierda el foco al apretarlo. */
export function atender(doc: Document = document): void {
    if (atendiendo) return;
    atendiendo = true;
    doc.addEventListener('mousedown', e => { if ((e.target as Element | null)?.closest?.(`[${BORRAR}]`)) e.preventDefault(); }, true);
    doc.addEventListener('click', e => { if (borrar(e.target)) { e.preventDefault(); e.stopPropagation(); } }, true);
}

/** La barra de un buscador como elemento, y su campo: para quien arma su caja con `createElement`. */
export function barraDeBuscar(p: PropsBarraBuscar): { barra: HTMLElement; campo: HTMLInputElement } {
    const t = document.createElement('template');
    t.innerHTML = barraBuscar(p);
    const barra = t.content.firstElementChild as HTMLElement;
    return { barra, campo: barra.querySelector<HTMLInputElement>('input.buscar')! };
}
