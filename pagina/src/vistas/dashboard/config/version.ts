// La versión de telar: la que corre, la última en PyPI y cuándo se preguntó; «buscar ahora» le pregunta a PyPI sin
// esperar la hora, e «instalar» hace lo mismo que el aviso de arriba (web/version.ts). Para una instalación que no
// se actualiza desde aquí (la del repositorio), qué hacer a mano. Y cómo le fue a la última actualización.

import type * as cli from '../../../cli';
import { esc, fechaCorta } from '../../../estilo';
import * as version from '../../../web/version';
import type { FabricaSeccion } from './seccion';

const COMO: Record<string, string> = {
    uv: 'instalado con uv tool: se actualiza desde aquí',
    repo: 'instalado desde el repositorio (editable): se actualiza con git pull',
    otro: 'instalado con pip u otra cosa: se actualiza a mano',
};

export const versionSeccion: FabricaSeccion = ctx => {
    let buscando = false;

    const buscar = async (forzar: boolean) => {
        buscando = forzar;
        if (ctx.seVe('version')) seccion.pintar();
        await version.revisar(forzar);
        buscando = false;
        if (ctx.seVe('version')) seccion.pintar();
    };

    const progreso = (p: cli.JsonProgreso) => {
        const cuando = p.hasta ?? p.desde;
        const h = [`<h2>la última actualización<small>${esc(p.version ?? '')} · ${esc(p.estado ?? '')}`
            + `${cuando ? ` · ${esc(fechaCorta(new Date(cuando * 1000).toISOString()))}` : ''}</small></h2>`];
        if (p.error) h.push(`<div class="fila falla">${esc(p.error)}</div>`);
        if (p.log) h.push(`<pre class="dim" style="white-space:pre-wrap">${esc(p.log)}</pre>`);
        return h;
    };

    const seccion = {
        clave: 'version',
        nombre: 'versión',
        ayuda: 'qué versión de telar corre, si hay una nueva, y buscar o instalar',
        abrir: () => buscar(false),
        pintar(): void {
            const v = version.lo();
            const h: string[] = [];
            if (!v) {
                h.push(`<div class="fila dim">${buscando ? 'preguntando…' : 'no sé todavía'}</div>`);
            } else {
                h.push(`<div class="fila">corre la <b>${esc(v.corre)}</b><span class="dim"> · ${esc(COMO[v.como] ?? v.como)}</span></div>`);
                const consultado = v.consultado ? fechaCorta(new Date(v.consultado * 1000).toISOString()) : '';
                h.push(`<div class="fila">la última en PyPI: <b>${esc(v.ultima || '?')}</b>`
                    + `<span class="dim">${consultado ? ` · preguntado ${esc(consultado)}` : ''}</span></div>`);
                if (v.error) h.push(`<div class="fila falla">${esc(v.error)}</div>`);
                if (v.hay_nueva && v.notas) h.push(`<div class="fila"><a href="${esc(v.notas)}" target="_blank" rel="noopener">qué trae la ${esc(v.ultima)}</a></div>`);
                if (v.hay_nueva && !v.puede && v.a_mano) h.push(`<div class="fila">${esc(v.a_mano)}</div>`);
                if (!v.hay_nueva) h.push('<div class="fila dim">está al día</div>');
            }
            h.push('<div class="fila">'
                + `<a data-accion="version-buscar" title="preguntarle a PyPI ahora, sin esperar la hora">${buscando ? 'buscando…' : 'buscar ahora'}</a>`
                + (v?.puede ? ` · <a data-accion="version-instalar" title="instalarla y reiniciar el servicio">instalar la ${esc(v.ultima)}</a>` : '')
                + '</div>');
            if (v?.progreso?.estado) h.push(...progreso(v.progreso));
            ctx.pintar(h);
        },
        async accion(accion: string): Promise<boolean> {
            if (accion === 'version-buscar') { await buscar(true); return true; }
            if (accion === 'version-instalar') { await version.actualizar(); return true; }
            return false;
        },
    };
    return seccion;
};
