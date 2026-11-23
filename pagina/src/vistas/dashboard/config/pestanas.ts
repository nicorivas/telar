// Las pestañas del dashboard (las filas del grupo DASHBOARD de la barra): cuáles se ven y en qué orden, con ✓ para
// mostrar u ocultar y ↑↓ para mover. Se guarda en `[dashboard]` (`telar config --pestanas`). Vale para todos los modos:
// una oculta aquí no se ve en ninguno, y este es el orden de un modo que las ve todas. Cuáles ve cada modo lo dice su
// fila en ⚙ modos (`filas`, web/modos-pestanas.ts), y un modo que nombra las suyas las muestra en su orden.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import type { Contexto, FabricaSeccion } from './seccion';
import { elegidas } from '../../../web/modos-pestanas';
import { ordenarPestanas } from '../orden-pestanas';
import { I } from '../../../web/iconos';

/** Las pestañas que hay, en el orden de ⚙ pestañas (`[dashboard] orden`), con su nombre y si ⚙ pestañas la oculta. */
export function pestanasEnOrden(ctx: Contexto): { clave: string; nombre: string; oculta: boolean }[] {
    const { orden, ocultas } = ctx.dashboard.orden();
    return ordenarPestanas(ctx.dashboard.pestanas(), x => x.clave, orden).map(p => ({ ...p, oculta: ocultas.includes(p.clave) }));
}

/** Los nombres de unas pestañas, como se muestran («todas», si son todas). */
export function decirPestanas(valor: unknown, hay: readonly { clave: string; nombre: string }[]): string {
    const e = elegidas(valor);
    if (!e) return 'todas';
    return e.map(k => hay.find(x => x.clave === k)?.nombre ?? k).join(', ');
}

export const pestanas: FabricaSeccion = ctx => {
    let aviso = '';
    // el mismo orden de la barra (orden-pestanas.ts): lo que no se nombra, donde la barra lo pone
    const enOrden = () => ordenarPestanas(ctx.dashboard.pestanas(), x => x.clave, ctx.dashboard.orden().orden);

    /** Mostrar u ocultar una, o moverla un lugar, y guardarlo. */
    const cambiar = async (como: string, clave: string) => {
        const orden = enOrden().map(x => x.clave);
        let ocultas = [...ctx.dashboard.orden().ocultas];
        const i = orden.indexOf(clave);
        if (i < 0) return;
        if (como === 'ver') ocultas = ocultas.includes(clave) ? ocultas.filter(x => x !== clave) : [...ocultas, clave];
        else {
            const j = i + (como === 'subir' ? -1 : 1);
            if (j < 0 || j >= orden.length) return;
            [orden[i], orden[j]] = [orden[j], orden[i]];
        }
        const r = await cli.configPestanas(orden.map(c => (ocultas.includes(c) ? '-' : '') + c).join(','));
        aviso = r.datos ? '' : (r.error ?? 'no pude guardar las pestañas');
        if (r.datos) ctx.dashboard.usarOrden(r.datos.dashboard);
        seccion.pintar();
    };

    const seccion = {
        clave: 'pestanas',
        nombre: 'pestañas',
        ayuda: 'cuáles se ven en la barra y en qué orden; las de un módulo nuevo aparecen solas',
        abrir: async () => seccion.pintar(),
        pintar(): void {
            const ocultas = ctx.dashboard.orden().ocultas;
            const deModulo = new Set((ctx.config()?.modulos ?? []).map(m => `bloque:${m.nombre}`));
            const h = aviso ? [`<div class="fila falla">${esc(aviso)}</div>`] : [];
            for (const { clave, nombre } of enOrden()) {
                const ve = !ocultas.includes(clave);
                h.push(`<div class="fila${ve ? '' : ' dim'}"><a data-accion="pest-ver" data-valor="${esc(clave)}" title="${ve ? 'ocultarla' : 'mostrarla'}">${ve ? I.hecha : I.punto}</a> `
                    + `${esc(nombre)}${deModulo.has(clave) ? ' <span class="dim">· módulo</span>' : ''}<span class="der">`
                    + `<a data-accion="pest-subir" data-valor="${esc(clave)}" title="un lugar antes">↑</a> `
                    + `<a data-accion="pest-bajar" data-valor="${esc(clave)}" title="un lugar después">↓</a></span></div>`);
            }
            h.push('<div class="fila dim">Una pestaña oculta sigue respondiendo a su tecla.</div>');
            // cómo se combina con los modos: aquí, el orden y lo que no se ve en ninguno; en ⚙ modos, cuáles ve cada uno
            h.push('<div class="fila dim">Esto vale para todos los modos: una oculta aquí no se ve en ninguno, y este es el orden de un modo '
                + 'que las ve todas. Cuáles ve cada modo, en <a data-accion="config" data-valor="modos">⚙ modos › pestañas</a>; un modo que '
                + 'nombra las suyas las muestra en el orden en que las nombra.</div>');
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            if (!accion.startsWith('pest-') || !valor) return false;
            await cambiar(accion.slice(5), valor);
            return true;
        },
    };
    return seccion;
};
