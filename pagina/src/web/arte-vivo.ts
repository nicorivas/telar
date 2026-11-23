// El arte vivo: anima los dibujos de letras (componentes/arte.ts) que hay dentro de un elemento, cada uno en su
// `[data-arte]`. Lo usa la ventana de mundos (web/mundos-ventana.ts) y el catálogo (/componentes#mundos).
//
//   const vivo = animar(dialogo);      // al abrir
//   vivo.parar();                      // al cerrar: ni un cuadro más
//
// · Un solo requestAnimationFrame para todos, y solo mientras hace falta: con la pestaña escondida se detiene (y vuelve
//   al mostrarse), y `parar` lo corta del todo. Cerrada la ventana no queda nada corriendo.
// · Cada arte lleva su reloj. Corre al ritmo de siempre y, con el mouse o el foco encima de su caja (`[data-arte-caja]`,
//   o la tarjeta que lo contiene), acelera de a poco hasta su ritmo de hover (y frena igual al salir): sin saltos. Un arte
//   con escena de hover la cambia al entrar.
// · El DOM se toca solo cuando cambia el cuadro (a los fps del arte, no a 60): el resto lo hace el CSS en el compositor.
// · Con «reducir movimiento» (o `reducido`), el primer cuadro, quieto: ningún requestAnimationFrame.

import { aceleracion, alRegistrar, arte, cuadro, indice, type Arte } from '../componentes/arte';

export interface Vivo {
    /** deja de animar y suelta todo lo que escuchaba */
    parar(): void;
    /** si hay un cuadro pedido al navegador ahora (para las pruebas: cerrada la ventana, nunca) */
    corriendo(): boolean;
    /** vuelve a buscar los artes adentro (si se repintó lo de adentro) */
    releer(): void;
    /** cómo va cada uno: su arte, su reloj, su ritmo y si tiene el mouse o el foco encima (para las pruebas) */
    estado(): { arte: string; reloj: number; vel: number; hover: boolean }[];
}

interface Estado { el: HTMLElement; arte: Arte; reloj: number; vel: number; ultimo: string; dibujado: string; hover: boolean }

/** Si la persona pidió menos movimiento. */
export const pideQuieto = (): boolean => {
    try { return !!globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
};

/** cuánto tarda en llegar a su ritmo de hover (y en volver): segundos para recorrer casi todo el camino */
const ACELERAR = .35;

export function animar(raiz: HTMLElement, o: { reducido?: boolean; caja?: string } = {}): Vivo {
    const reducido = o.reducido ?? pideQuieto();
    const caja = o.caja ?? '[data-arte-caja], .mt-tarjeta';
    let estados: Estado[] = [];
    let pedido = 0, antes = 0, parado = false;

    const leer = () => {
        const previos = new Map(estados.map(e => [e.el, e]));
        estados = [...raiz.querySelectorAll<HTMLElement>('[data-arte]')].flatMap(el => {
            const a = arte(el.dataset.arte);
            if (!a) return [];
            const ya = previos.get(el);
            if (ya && ya.arte === a) return [ya];
            return [{ el, arte: a, reloj: 0, vel: 1, ultimo: '', dibujado: el.textContent ?? '', hover: !!ya?.hover }];
        });
        for (const e of estados) dibujar(e, true);
    };
    const dibujar = (e: Estado, siempre = false) => {
        const clave = `${e.hover && e.arte.alHover.cuadros ? 'h' : ''}${indice(e.arte, e.reloj, e.hover)}`;
        if (!siempre && clave === e.ultimo) return;
        e.ultimo = clave;
        const texto = cuadro(e.arte, reducido ? 0 : e.reloj, { hover: e.hover && !reducido });
        if (texto !== e.dibujado) { e.el.textContent = texto; e.dibujado = texto; }
    };
    const paso = (ahora: number) => {
        pedido = 0;
        if (parado) return;
        const dt = antes ? Math.min(.1, Math.max(0, (ahora - antes) / 1000)) : 0;
        antes = ahora;
        const k = 1 - Math.exp(-dt * 3 / ACELERAR);
        for (const e of estados) {
            const objetivo = e.hover ? aceleracion(e.arte) : 1;
            e.vel += (objetivo - e.vel) * k;
            e.reloj += dt * e.vel;
            dibujar(e);
        }
        pedir();
    };
    const pedir = () => {
        if (parado || reducido || pedido || !estados.length) return;
        if (globalThis.document?.visibilityState === 'hidden') return;
        if (!raiz.isConnected && raiz.isConnected !== undefined) { parar(); return; }
        pedido = requestAnimationFrame(paso);
    };
    const visible = () => {
        if (document.visibilityState === 'hidden') {
            if (pedido) { cancelAnimationFrame(pedido); pedido = 0; }
        } else { antes = 0; pedir(); }
    };
    // el mouse o el foco: el arte que está dentro de esa caja
    const marcar = (blanco: EventTarget | null, si: boolean) => {
        const c = (blanco as HTMLElement | null)?.closest?.(caja);
        if (!c) return;
        for (const e of estados) if (c.contains(e.el)) {
            if (e.hover === si) continue;
            e.hover = si;
            if (e.arte.alHover.cuadros || reducido) dibujar(e, true);
        }
    };
    const entra = (ev: Event) => marcar(ev.target, true);
    const sale = (ev: Event) => {
        const hacia = (ev as FocusEvent | PointerEvent).relatedTarget as HTMLElement | null;
        const c = (ev.target as HTMLElement | null)?.closest?.(caja);
        if (c && hacia && c.contains(hacia)) return;
        // el foco y el mouse son dos: con el foco todavía adentro, sigue encendido
        if (ev.type === 'pointerout' && c && c.contains(document.activeElement)) return;
        if (ev.type === 'focusout' && c?.matches?.(':hover')) return;
        marcar(ev.target, false);
    };
    const parar = () => {
        if (parado) return;
        parado = true;
        if (pedido) cancelAnimationFrame(pedido);
        pedido = 0;
        raiz.removeEventListener('pointerover', entra);
        raiz.removeEventListener('pointerout', sale);
        raiz.removeEventListener('focusin', entra);
        raiz.removeEventListener('focusout', sale);
        document.removeEventListener('visibilitychange', visible);
        soltarRegistro();
    };

    raiz.addEventListener('pointerover', entra);
    raiz.addEventListener('pointerout', sale);
    raiz.addEventListener('focusin', entra);
    raiz.addEventListener('focusout', sale);
    document.addEventListener('visibilitychange', visible);
    // un arte que llega después (los de la raíz, `GET /arte`): se toma al tiro
    const soltarRegistro = alRegistrar(() => { if (!parado) { leer(); pedir(); } });
    leer();
    pedir();
    return { parar, corriendo: () => !!pedido, releer: () => { leer(); pedir(); },
        estado: () => estados.map(e => ({ arte: e.arte.clave, reloj: e.reloj, vel: e.vel, hover: e.hover })) };
}
