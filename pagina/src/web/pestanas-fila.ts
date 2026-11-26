// Lo que hacen las pestañas (componentes/pestanas.ts) en cualquier lugar de la página, sin que cada vista lo repita:
//
// · el teclado: con el foco en una pestaña, ← → pasan a la de al lado (de la última, a la primera) y la abren, Inicio y
//   Fin a la primera y la última; ⏎ y espacio abren la que tiene el foco. Es el `tablist` de ARIA con activación al
//   moverse. El «⋯» de las que no caben es una más en el recorrido: las flechas llegan a él sin abrir nada, y ⏎, espacio
//   o ↓ abren su menú (el de la casa, ui.menu: ↑ ↓, ⏎, ⎋). Las teclas no siguen de largo (el dashboard tiene atajos de
//   una letra y ← → propias): solo cuando el foco está en una pestaña, así que no le quitan nada a la terminal ni a un
//   campo.
// · después de abrirla, la vista suele repintar: el foco vuelve a la pestaña del mismo nombre en la fila nueva, para
//   seguir con las flechas.
// · si no caben (`acomodar`): las que caben, enteras; las demás, al menú del «⋯», que aparece después de la última que
//   se ve; la abierta siempre se ve (si es de las que no caben, toma el lugar de la última que cabía). Una escondida con
//   algo nuevo pone su punto en el «⋯»; una con la cuenta que pide, el «⋯» en el de cuidado. Lo llama quien pinta (al
//   pintar, o `acomodarTodas`), y desde ahí un ResizeObserver mira la fila: cambiar el ancho (la ventana, arrastrar la
//   línea de una barra, web/anchos.ts) la reacomoda en vivo. Se mide en el mismo cuadro, antes de dibujar: sin saltos.
//
// Sin la página: el menú del «⋯» lo pone quien la usa (`usarMenu`). En la página es ui.menu (web/pestanas.ts lo pone); en
// el lienzo de un módulo, el mismo menú pedido a la página (src/lienzo/componentes.ts). Así esto entra en un lienzo sin
// arrastrar la página entera.

/** Una opción del menú del «⋯»: lo que muestra (como ui.menu) y la pestaña que abre. */
export interface OpcionMas { label: string; icono?: string; color?: string; description?: string; apagada: boolean; p: HTMLElement }
/** El menú del «⋯»: la opción elegida, o undefined. */
export type MenuMas = (opciones: OpcionMas[], ancla: HTMLElement, titulo: string) => Promise<OpcionMas | undefined>;

/** el menú que abre el «⋯»: sin uno puesto, nada */
let menuMas: MenuMas = async () => undefined;

/** Pone el menú que abre el «⋯» (en la página, ui.menu). */
export function usarMenu(m: MenuMas): void { menuMas = m; }

const LISTA = '.pestanas-lista[role="tablist"]';

/** Cuánto mide una pestaña o la lista: el ancho dibujado (las pruebas, sin dibujo, lo cambian). */
export const medir = { ancho: (el: Element): number => el.getBoundingClientRect().width };

/** Las pestañas de una fila, en orden (todas: las que no caben también). */
const delaFila = (fila: Element): HTMLElement[] => [...fila.querySelectorAll<HTMLElement>(`${LISTA} > .pestana[role="tab"]`)];

/** Lo que recorren las flechas: las que se ven y se pueden abrir, y el «⋯» si está. */
function recorrido(fila: Element): HTMLElement[] {
    const mas = fila.querySelector<HTMLElement>('.pestanas-mas');
    return [...delaFila(fila).filter(p => !p.classList.contains('apagada') && !p.classList.contains('fuera')),
        ...(mas && !mas.hidden ? [mas] : [])];
}

/** el ancho con que se acomodó cada fila: el ResizeObserver solo la vuelve a medir si cambió */
const medida = new WeakMap<Element, number>();
let observador: ResizeObserver | undefined;
const observadas = new Set<Element>();

function observar(fila: Element): void {
    if (typeof ResizeObserver === 'undefined') return;
    // las que ya no están en la página se sueltan (el observador las retendría)
    for (const f of observadas) if (!f.isConnected) { observador?.unobserve(f); observadas.delete(f); }
    if (observadas.has(fila)) return;
    observador ??= new ResizeObserver(es => {
        for (const e of es) if (Math.abs((medida.get(e.target) ?? -1) - e.contentRect.width) > 0.5) acomodar(e.target);
    });
    observador.observe(fila);
    observadas.add(fila);
}

/** El tono del punto que se ve en el «⋯» si una escondida tiene algo nuevo: el más urgente. */
const TONOS = ['peligro', 'atencion', 'termino', 'exito', 'acento'];

/** Acomoda la fila al ancho que tiene: las que no caben, al «⋯». Sincrónico: muestra todas, mide y esconde en el mismo
 *  cuadro, así que no se ve ningún salto. */
export function acomodar(fila: Element): void {
    const lista = fila.querySelector<HTMLElement>(LISTA);
    if (!lista) return;
    observar(fila);
    const mas = fila.querySelector<HTMLElement>('.pestanas-mas');
    const todas = delaFila(fila);
    for (const p of todas) p.classList.remove('fuera');
    // con el «⋯» a la vista, la lista se aprieta al lugar que le queda (nunca más que lo suyo)
    if (mas) mas.hidden = false;
    const ancho = medir.ancho(lista), anchoMas = mas ? medir.ancho(mas) : 0;
    const anchos = todas.map(p => medir.ancho(p));
    const total = anchos.reduce((a, b) => a + b, 0);
    medida.set(fila, medir.ancho(fila));
    if (!mas || total <= ancho + anchoMas + 0.5) { if (mas) pintarMas(mas, []); return; }
    // las que caben, en orden; la abierta, si no cabe, en lugar de las últimas que cabían
    let k = 0, usado = 0;
    while (k < todas.length && usado + anchos[k] <= ancho + 0.5) usado += anchos[k++];
    const abierta = todas.findIndex(p => p.classList.contains('si'));
    const ven = new Set(todas.slice(0, k));
    if (abierta >= k) {
        while (k > 0 && usado + anchos[abierta] > ancho + 0.5) usado -= anchos[--k];
        ven.clear();
        for (const p of todas.slice(0, k)) ven.add(p);
        ven.add(todas[abierta]);
    }
    const fuera = todas.filter(p => !ven.has(p));
    for (const p of fuera) p.classList.add('fuera');
    pintarMas(mas, fuera);
}

/** El «⋯»: escondido si no lleva ninguna; si lleva, su globo dice cuáles, y lo nuevo o lo que pide de ellas se nota. */
function pintarMas(mas: HTMLElement, fuera: HTMLElement[]): void {
    mas.hidden = !fuera.length;
    mas.querySelector('.pestana-nuevo')?.remove();
    mas.classList.toggle('atencion', fuera.some(p => p.querySelector('.pestana-cuenta.atencion')));
    if (!fuera.length) return;
    mas.title = `más: ${fuera.map(p => p.title || nombreDe(p)).join(' · ')}`;
    const puntos = fuera.map(p => p.querySelector<HTMLElement>('.pestana-nuevo')).filter((x): x is HTMLElement => !!x);
    if (!puntos.length) return;
    const rango = (x: HTMLElement) => { const i = TONOS.findIndex(t => x.classList.contains(`tono-${t}`)); return i < 0 ? TONOS.length : i; };
    mas.appendChild(puntos.reduce((a, b) => (rango(b) < rango(a) ? b : a)).cloneNode(true));
}

const nombreDe = (p: Element): string => p.querySelector('.pestana-nombre')?.textContent ?? '';

/** Marcar la abierta en una fila que ya está en la página (la que la vista cambia sin repintar: el detalle de un
 *  proyecto): su superficie, `aria-selected` y el lugar en el orden del tabulador. */
export function marcar(fila: Element, valor: string): void {
    const todas = [...fila.querySelectorAll<HTMLElement>('.pestana[role="tab"]')];
    const hay = todas.some(p => p.dataset.valor === valor);
    todas.forEach((p, i) => {
        const si = p.dataset.valor === valor;
        p.classList.toggle('si', si);
        p.setAttribute('aria-selected', String(si));
        p.tabIndex = (hay ? si : i === 0) ? 0 : -1;
    });
    acomodar(fila);
}

/** Todas las filas de pestañas de `raiz`. */
export const acomodarTodas = (raiz: ParentNode = document): void => { for (const f of raiz.querySelectorAll('.pestanas')) acomodar(f); };

/** El foco, de vuelta en la pestaña `valor` de la fila `nombre`, si la vista la repintó (y el foco se perdió). */
function volverAlFoco(nombre: string, valor: string, doc: Document, aunque = false): void {
    let veces = 0;
    const mirar = () => {
        const activo = doc.activeElement;
        const fila = [...doc.querySelectorAll<HTMLElement>('.pestanas')].find(f => f.dataset.pestanas === nombre);
        const p = fila ? delaFila(fila).find(x => x.dataset.valor === valor || x.getAttribute('href') === valor) : undefined;
        if (p && p !== activo && (aunque || !activo || activo === doc.body || !activo.isConnected)) { p.focus(); return; }
        if (p === activo || ++veces > 10) return;
        setTimeout(mirar, 30);
    };
    setTimeout(mirar, 0);
}

/** El menú del «⋯»: las que no caben, con su ícono, su nombre y su cuenta (la de cuidado y lo nuevo, dichos). Elegir
 *  una es como apretarla: su orden (su clic) la abre, y la fila la trae a la vista. */
export async function abrirMas(mas: HTMLElement, conTeclado = false): Promise<void> {
    const fila = mas.closest<HTMLElement>('.pestanas');
    if (!fila) return;
    const fuera = delaFila(fila).filter(p => p.classList.contains('fuera'));
    if (!fuera.length) return;
    const opciones: OpcionMas[] = fuera.map(p => {
        const cuenta = p.querySelector('.pestana-cuenta')?.textContent ?? '';
        const nuevo = p.querySelector('.pestana-nuevo') ? 'algo nuevo' : '';
        const apagada = p.classList.contains('apagada');
        return {
            label: nombreDe(p), icono: p.querySelector('.pestana-icono')?.textContent || undefined, color: p.dataset.color,
            description: apagada ? (p.title || 'no se puede') : [cuenta, nuevo].filter(Boolean).join(' · ') || undefined,
            apagada, p,
        };
    });
    const elegida = await menuMas(opciones, mas, fila.dataset.pestanas ?? '');
    if (!elegida) { if (conTeclado) mas.focus(); return; }
    const valor = elegida.p.dataset.valor ?? elegida.p.getAttribute('href') ?? '';
    elegida.p.click();
    if (fila.isConnected) acomodar(fila);
    if (conTeclado) volverAlFoco(fila.dataset.pestanas ?? '', valor, mas.ownerDocument, true);
}

let atendiendo = false;

/** Atiende las pestañas de toda la página (una vez, al arrancar). Las teclas van en la captura, antes que las del
 *  dashboard y las de la página, y solo si el foco está en una pestaña. */
export function atender(doc: Document = document): void {
    if (atendiendo) return;
    atendiendo = true;
    doc.addEventListener('keydown', e => {
        const p = (e.target as Element | null)?.closest?.<HTMLElement>('.pestana[role="tab"], .pestanas-mas');
        const fila = p?.closest<HTMLElement>('.pestanas');
        if (!p || !fila || e.metaKey || e.ctrlKey || e.altKey) return;
        const esMas = p.classList.contains('pestanas-mas');
        if (esMas && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
            e.preventDefault(); e.stopPropagation();
            void abrirMas(p, true);
            return;
        }
        const todas = recorrido(fila);
        const i = todas.indexOf(p);
        const destino = ({
            ArrowRight: todas[(i + 1) % todas.length], ArrowLeft: todas[(i - 1 + todas.length) % todas.length],
            Home: todas[0], End: todas[todas.length - 1],
            Enter: p, ' ': p,
        } as Record<string, HTMLElement | undefined>)[e.key];
        if (!destino) return;
        e.preventDefault();
        e.stopPropagation();
        destino.focus();
        // al «⋯» se llega sin abrir nada: su menú, con ⏎
        if (destino.classList.contains('pestanas-mas')) return;
        if (!destino.classList.contains('si') || e.key === 'Enter' || e.key === ' ') {
            destino.click();
            volverAlFoco(fila.dataset.pestanas ?? '', destino.dataset.valor ?? destino.getAttribute('href') ?? '', doc);
        }
    }, true);
    // el clic en el «⋯»: su menú
    doc.addEventListener('click', e => {
        const mas = (e.target as Element | null)?.closest?.<HTMLElement>('.pestanas-mas');
        if (!mas) return;
        e.preventDefault(); e.stopPropagation();
        void abrirMas(mas);
    }, true);
    // sin ResizeObserver (no debería), al cambiar el ancho de la ventana; y cuando llega la letra de los íconos, que
    // cambia lo que mide cada una
    if (typeof ResizeObserver === 'undefined') doc.defaultView?.addEventListener('resize', () => acomodarTodas(doc));
    void doc.fonts?.ready.then(() => acomodarTodas(doc));
}
