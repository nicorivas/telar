// Los módulos instalados (`[modulos]`): una carpeta con modulo.toml que trae una pestaña, una app, periódicos…
// Aquí solo se ven; se instalan en la configuración (docs/configuracion.md, «Módulos»).

import { esc } from '../../../estilo';
import type { FabricaSeccion } from './seccion';

export const modulos: FabricaSeccion = ctx => {
    const seccion = {
        clave: 'modulos',
        nombre: 'módulos',
        ayuda: 'una carpeta con modulo.toml; se instalan en [modulos] de la configuración',
        abrir: async () => seccion.pintar(),
        pintar(): void {
            const lista = ctx.config()?.modulos ?? [];
            const h = lista.length ? [] : ['<div class="fila dim">ninguno instalado</div>'];
            for (const m of lista) {
                h.push(`<div class="fila"><b>${esc(m.nombre)}</b>&nbsp;<span class="dim">${esc(m.descripcion)}</span></div>`
                    + `<div class="fila dim">aporta ${esc(m.aporta.join(', ') || 'nada')} · ${esc(m.carpeta)}</div>`);
            }
            ctx.pintar(h);
        },
    };
    return seccion;
};
