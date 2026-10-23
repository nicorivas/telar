// Lo que se dicen los agentes de los hilos por el bus (`telar mensaje --registro`): lo más nuevo arriba, y lo
// retenido (una cadena muy larga, demasiados por hora) esperando a que la persona lo suelte. Solo con más de una
// máquina: sin bus no hay registro.

import * as cli from '../../../cli';
import { esc, fechaCorta } from '../../../estilo';
import { modelo } from '../../../modelo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

export const agentes: FabricaSeccion = ctx => {
    let lista: cli.JsonMensajeBus[] | undefined;
    let error = '';
    /** los que se ven enteros */
    const abiertos = new Set<string>();

    const leer = async () => {
        if (!lista) ctx.pintar(['<div class="fila dim">leyendo…</div>']);
        const r = await cli.mensajesBus();
        lista = r.datos?.mensajes ?? lista;
        error = r.datos ? '' : (r.error ?? 'no pude leer el registro del bus');
        if (ctx.seVe('agentes')) seccion.pintar();
    };

    const soltar = async (id: string) => {
        const r = await cli.soltarMensaje(id);
        if (!r.datos) { void ui.falla(`telar: no se soltó: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: soltado, en la casilla de «${r.datos.para}»`, 4000);
        await leer();
    };

    const fila = (m: cli.JsonMensajeBus, retenido: boolean) => {
        const abierto = abiertos.has(m.id);
        const texto = abierto ? m.texto : m.texto.split(/\s+/).join(' ').slice(0, 140);
        return `<div class="item-pag clic" data-accion="ver-msg" data-valor="${esc(m.id)}" title="clic: ${abierto ? 'acortar' : 'el texto entero'}">`
            + `<div class="fila">${retenido ? '<span class="falla">⏸ </span>' : ''}<b>${esc(m.de)}</b><span class="dim"> → </span><b>${esc(m.para)}</b>`
            + `<span class="dim"> · ${esc(m.tipo)}${m.saltos ? ` · salto ${m.saltos}` : ''}</span>`
            + `<span class="der dim">${esc(fechaCorta(m.creado))}`
            + (retenido ? ` · <a data-accion="soltar-msg" data-valor="${esc(m.id)}" title="mandarlo igual: lo decides tú">soltar</a>` : '')
            + '</span></div>'
            + (retenido && m.motivo ? `<div class="fila falla">${esc(m.motivo)}</div>` : '')
            + `<div class="fila${abierto ? '' : ' dim'}" style="white-space:pre-wrap">${esc(texto)}</div></div>`;
    };

    const seccion = {
        clave: 'agentes',
        nombre: 'mensajes',
        ayuda: 'lo que se dicen los hilos por el bus, y lo retenido (los agentes residentes: ≡ en AGENTES, en la barra)',
        visible: () => modelo.hayBus,
        abrir: () => leer(),
        pintar(): void {
            const todos = lista ?? [];
            const soltados = new Set(todos.filter(m => m.estado !== 'retenido').map(m => m.id));
            const retenidos = todos.filter(m => m.estado === 'retenido' && !soltados.has(m.id));
            const h = [`<div class="fila"><span class="dim">${todos.length} último${todos.length === 1 ? '' : 's'}`
                + `${retenidos.length ? ` · ${retenidos.length} retenido${retenidos.length === 1 ? '' : 's'}` : ''}</span>`
                + '<span class="der"><a data-accion="agentes-leer" title="volver a leer">↻</a></span></div>'];
            if (error) h.push(`<div class="fila falla">${esc(error)}</div>`);
            if (lista && !todos.length) h.push('<div class="fila dim">nada todavía</div>');
            for (const m of retenidos) h.push(fila(m, true));
            for (const m of [...todos].reverse()) if (m.estado !== 'retenido') h.push(fila(m, false));
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'agentes-leer': await leer(); return true;
                case 'soltar-msg': if (valor) await soltar(valor); return true;
                case 'ver-msg':
                    if (valor) { if (abiertos.has(valor)) abiertos.delete(valor); else abiertos.add(valor); seccion.pintar(); }
                    return true;
            }
            return false;
        },
    };
    return seccion;
};
