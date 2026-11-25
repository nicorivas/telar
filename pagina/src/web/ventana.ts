// Abrir una ventana (componentes/ventana.ts) en la página: lo de DOM que el componente deja a quien lo usa. Crea el
// <dialog> con lo que da `ventana(props)` adentro, lo abre (`showModal` si es `centrada` o `arriba`: con fondo, y el foco
// atrapado adentro; `show` si va `junto` al clic: sin fondo, y la página sigue), pone el foco, la cierra con ⎋ y con un
// clic fuera, y devuelve una promesa con lo elegido (undefined si se cerró sin elegir).
//
//   const r = await abrirVentana({ titulo: 'proyecto nuevo', campo, pie: pieVentana([...]) }, {
//       montar: (d, cerrar) => { … d.querySelector('input')… cerrar(valor) },
//   });
//
// `quieta`: una ventana que sale sola (la que pide un módulo cuando llega algo, web/ventanas.ts) y no puede quitarle el
// teclado a quien escribe en otra parte: se abre sin `show()` (con el atributo `open`), sin fondo ni foco, y pasa a modal (fondo, foco adentro) con un
// clic en ella o cuando quien la abrió lo pide (`tomar-foco`, un evento en el <dialog>).
//
// Un clic en un `[data-accion]` de adentro (los botones de `pieVentana`) la cierra con esa acción, si `montar` no lo
// atendió antes (con `preventDefault`). Las teclas de esos botones (la de cada celda, y ⏎ el del foco) las atiende
// web/botonera.ts. Es la pieza decidida para todas las ventanas (docs/propuestas/componentes.md, «Las
// ventanas»); las que ya existen (⌘K, `caja()` de interfaz.ts, el menú ⋯, la instrucción) se migran aparte.

import { ventana, type PropsVentana } from '../componentes/ventana';
import { teclasDeBotones } from './botonera';

export interface OpcionesVentana<T> {
    /** dónde cae una ventana `junto`: el punto del clic, o el elemento junto al que se abre */
    junto?: { x: number; y: number } | Element;
    /** lo que recibe el foco al abrirse: un selector de adentro. Sin él, el primer campo; si no hay, la ventana */
    foco?: string;
    /** clases del <dialog>, además de `ventana-dialogo` */
    clase?: string;
    /** después de ponerla en la página y antes de abrirla: lo de adentro se cablea aquí. `cerrar(valor)` la cierra con
     *  eso. Lo que devuelve, si es una función, corre al cerrarse */
    montar?: (d: HTMLDialogElement, cerrar: (valor?: T) => void) => void | (() => void);
    /** antes de cerrarse por ⎋ o por un clic fuera: false la deja abierta (algo se está mandando) */
    puedeCerrar?: () => boolean;
    /** sin quitar el foco de donde está: abierta sin modal (sin fondo; la página sigue recibiendo lo que se escribe)
     *  hasta un clic en ella o un evento `tomar-foco` en el <dialog>, que la vuelven modal con el foco adentro */
    quieta?: boolean;
}

/** Abre la ventana y espera lo elegido. */
export function abrirVentana<T = string>(props: PropsVentana, o: OpcionesVentana<T> = {}): Promise<T | undefined> {
    return new Promise(listo => {
        const lugar = props.lugar ?? 'centrada';
        const d = document.createElement('dialog');
        d.className = `ventana-dialogo ${lugar}${o.clase ? ` ${o.clase}` : ''}`;
        d.innerHTML = ventana({ ...props, lugar });
        document.body.appendChild(d);
        let hecho = false, alCerrar: void | (() => void);
        const cerrar = (valor?: T) => {
            if (hecho) return;
            hecho = true;
            document.removeEventListener('pointerdown', fuera, true);
            try { if (typeof alCerrar === 'function') alCerrar(); } finally {
                if (d.open) d.close();
                d.remove();
                listo(valor);
            }
        };
        const intentar = () => { if (!o.puedeCerrar || o.puedeCerrar()) cerrar(undefined); };
        // cerrada por el navegador sin pasar por aquí (un ⎋ cuyo `cancel` no se deja cancelar, sin un gesto antes en la
        // página): que no quede un <dialog> cerrado esperando. Pasar de quieta a modal la cierra y la abre al tiro: ahí sigue
        // abierta cuando llega el evento
        let pasando = false;
        d.addEventListener('close', () => { if (!pasando) setTimeout(() => { if (!d.open) cerrar(undefined); }); });
        // ⎋: el navegador manda `cancel` (con showModal) o nada (con show): se atiende igual en los dos
        d.addEventListener('cancel', e => { e.preventDefault(); intentar(); });
        d.addEventListener('keydown', e => {
            if (e.key === 'Escape' && !e.defaultPrevented) { e.preventDefault(); intentar(); }
        });
        // un clic fuera: con fondo (modal), el clic cae en el <dialog> mismo, fuera de su caja; sin fondo, en la página
        d.addEventListener('click', e => {
            if (e.target !== d) return;
            const r = (d.firstElementChild ?? d).getBoundingClientRect();
            if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) intentar();
        });
        const fuera = (e: Event) => { if (!d.contains(e.target as Node)) intentar(); };
        // los botones del pie (`pieVentana`): la cierran con su acción, si nadie lo atendió antes
        d.addEventListener('click', e => {
            const a = (e.target as HTMLElement).closest<HTMLElement>('[data-accion]');
            if (a && d.contains(a) && !e.defaultPrevented) { e.preventDefault(); cerrar(a.dataset.accion as T); }
        });
        // las teclas de los botones del pie (⌘⌫, ⌘⏎, 1 2…; ⏎ el del foco, nunca uno sostenido): antes que las de `montar`
        teclasDeBotones(d);
        alCerrar = o.montar?.(d, cerrar);
        const enfocar = () => {
            const foco = (o.foco ? d.querySelector<HTMLElement>(o.foco) : null)
                ?? d.querySelector<HTMLElement>('input, textarea, select') ?? d.querySelector<HTMLElement>('.ventana');
            if (foco) {
                if (!foco.matches('input, textarea, select, button, a[href], [tabindex]')) foco.tabIndex = -1;
                foco.focus({ preventScroll: true });
            }
        };
        if (lugar === 'junto') {
            // junto a algo de una ventana modal (el «⋯» de las pestañas del visor): modal también, sin fondo, o quedaría
            // debajo de ella (la capa de arriba es solo de las modales)
            const sobreModal = o.junto instanceof Element && !!o.junto.closest('dialog')?.matches(':modal');
            if (sobreModal) { d.classList.add('sobre-modal'); d.showModal(); } else d.show();
            colocar(d, o.junto);
            // el clic que la abrió no la cierra: se escucha desde el próximo
            setTimeout(() => document.addEventListener('pointerdown', fuera, true));
        } else if (o.quieta) {
            // sin fondo y sin el foco: lo que se escribe sigue yendo adonde iba. Un clic en ella, o `tomar-foco`, la vuelve
            // modal: el fondo, y el foco adentro
            d.classList.add('quieta');
            // el atributo, no `show()`: `show()` corre los pasos de foco del <dialog> y se llevaría el teclado a su caja
            d.setAttribute('open', '');
            const tomar = () => {
                if (hecho || !d.classList.contains('quieta')) return;
                d.classList.remove('quieta');
                pasando = true;
                try { if (d.open) d.close(); d.showModal(); } finally { pasando = false; }
                enfocar();
            };
            d.addEventListener('pointerdown', tomar, true);
            d.addEventListener('tomar-foco', tomar);
            return;
        } else {
            d.showModal();
        }
        enfocar();
    });
}

/** Una ventana `junto`: debajo y a la derecha del punto (o del elemento); si no cabe abajo, arriba; sin salirse de la pantalla. */
function colocar(d: HTMLDialogElement, junto: OpcionesVentana<unknown>['junto']): void {
    const caja = d.getBoundingClientRect();
    let x = 0, y = 0;
    if (junto instanceof Element) { const r = junto.getBoundingClientRect(); x = r.left; y = r.bottom; }
    else if (junto) { x = junto.x; y = junto.y; }
    const margen = 8;
    // si no cabe debajo, va encima del punto (o del elemento), no encima de él
    if (y + caja.height + margen > innerHeight) y = (junto instanceof Element ? junto.getBoundingClientRect().top : y) - caja.height;
    x = Math.max(margen, Math.min(x, innerWidth - caja.width - margen));
    y = Math.max(margen, Math.min(y, innerHeight - caja.height - margen));
    d.style.position = 'fixed';
    d.style.margin = '0';
    d.style.left = `${x}px`;
    d.style.top = `${y}px`;
}
