// Las pestañas del dashboard (las filas del grupo DASHBOARD de la barra): cuáles se ven y en qué orden, con ✓ para
// mostrar u ocultar y ↑↓ para mover. Se guarda en `[dashboard]` (`telar config --pestanas`).

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import type { FabricaSeccion } from './seccion';

export const pestanas: FabricaSeccion = ctx => {
    let aviso = '';
    const enOrden = () => {
        const todas = ctx.dashboard.pestanas();
        const { orden } = ctx.dashboard.orden();
        const pos = (c: string) => { const i = orden.indexOf(c); return i < 0 ? orden.length + todas.findIndex(x => x.clave === c) : i; };
        return [...todas].sort((a, b) => pos(a.clave) - pos(b.clave));
    };

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
                h.push(`<div class="fila${ve ? '' : ' dim'}"><a data-accion="pest-ver" data-valor="${esc(clave)}" title="${ve ? 'ocultarla' : 'mostrarla'}">${ve ? '✓' : '·'}</a> `
                    + `${esc(nombre)}${deModulo.has(clave) ? ' <span class="dim">· módulo</span>' : ''}<span class="der">`
                    + `<a data-accion="pest-subir" data-valor="${esc(clave)}" title="un lugar antes">↑</a> `
                    + `<a data-accion="pest-bajar" data-valor="${esc(clave)}" title="un lugar después">↓</a></span></div>`);
            }
            h.push('<div class="fila dim">Una pestaña oculta sigue respondiendo a su tecla.</div>');
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
