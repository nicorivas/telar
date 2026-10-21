// De qué carpetas salen los hilos de la lista (`[hilos] directorios`), y cuántos se abren al tejer la sesión.
// Se cambia con `telar config --directorios`; después se ofrece abrir los que falten (cada uno arranca su agente).

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import { modelo } from '../../../modelo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

export const carpetas: FabricaSeccion = ctx => {
    let aviso = '';

    const cambiar = async () => {
        const actual = (ctx.config()?.hilos.directorios ?? []).join(', ');
        const nuevo = await ui.campo({
            titulo: 'De qué carpetas salen los hilos',
            ayuda: 'Relativas a la raíz del repositorio, separadas por coma, en el orden en que se abren. Vacío: las unidades del perfil.',
            placeholder: 'operacion/proyectos, negocio/pipeline',
            valor: actual,
        });
        if (nuevo === undefined || nuevo.trim() === actual) return;
        const r = await cli.directoriosHilos(nuevo.trim());
        aviso = r.ok ? '' : (r.err.trim().split('\n').pop() || 'no pude guardar las carpetas');
        await ctx.releerConfig();
        seccion.pintar();
        if (!r.ok) return;
        // cada hilo abre un agente: se ofrece, no se hace
        const si = await ui.info('Carpetas guardadas. ¿Abrir ahora los hilos que falten? Cada uno arranca su agente.', 'Abrir ahora');
        if (si === 'Abrir ahora') {
            const t = await cli.tejer(true);
            if (!t.ok) void ui.aviso(`telar: ${t.err.trim().split('\n').pop() ?? 'no pude abrirlos'}`);
            await modelo.sondear();
        }
    };

    const seccion = {
        clave: 'hilos',
        nombre: 'hilos',
        ayuda: 'de qué carpetas salen los de la lista',
        abrir: async () => seccion.pintar(),
        pintar(): void {
            const hc = ctx.config()?.hilos;
            const h = aviso ? [`<div class="fila falla">${esc(aviso)}</div>`] : [];
            if (hc) {
                h.push('<div class="fila">' + (hc.directorios.length
                    ? hc.directorios.map(d => `<code>${esc(d)}</code>`).join(' · ')
                    : 'las unidades del perfil, en su orden')
                    + '<span class="der"><a data-accion="directorios">cambiar…</a></span></div>');
                h.push(`<div class="fila dim">Al tejer la sesión se abren hasta ${hc.tope}, repartidos por turnos: uno de cada carpeta. `
                    + 'Los archivados no se reabren solos: ⏸ en la lista archiva uno y guarda su conversación, ▶ lo retoma.</div>');
            }
            ctx.pintar(h);
        },
        async accion(accion: string): Promise<boolean> {
            if (accion !== 'directorios') return false;
            await cambiar();
            return true;
        },
    };
    return seccion;
};
