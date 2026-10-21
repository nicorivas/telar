// Qué se le dice al agente al pinchar una reunión y al abrir un proyecto de la lista (`[agente] reunion` y
// `proyecto`): cambiarlo, o volver al de fábrica. Se guarda con `telar config --reunion` / `--proyecto`.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

export const agente: FabricaSeccion = ctx => {
    let aviso = '';

    /** Cambiar (o restablecer, con `restablecer`) uno de los dos mensajes. */
    const cambiar = async (cual: 'reunion' | 'proyecto', restablecer: boolean) => {
        let texto = '';
        if (!restablecer) {
            const actual = ctx.config()?.agente[cual] ?? '';
            const nuevo = await ui.campo(cual === 'reunion'
                ? { titulo: 'Qué decirle al agente al preparar una reunión', valor: actual,
                    ayuda: 'Marcadores: {titulo} {hora} {fecha} {enlace} {proyecto}. Una skill (/nombre …) o una instrucción en prosa.' }
                : { titulo: 'Qué decirle al agente al abrir un proyecto', valor: actual,
                    ayuda: 'Marcadores: {nombre} {ruta} {carpeta} {documento}. Una skill (/nombre …) o una instrucción en prosa.' });
            if (nuevo === undefined || nuevo.trim() === actual) return;
            texto = nuevo.trim();
        }
        const r = await (cual === 'reunion' ? cli.plantillaReunion(texto) : cli.plantillaProyecto(texto));
        aviso = r.ok ? '' : (r.err.trim().split('\n').pop() || 'no pude guardar el mensaje');
        await ctx.releerConfig();
        seccion.pintar();
    };

    const seccion = {
        clave: 'agente',
        nombre: 'agente',
        ayuda: 'qué se le dice al agente al pinchar una reunión o abrir un proyecto',
        abrir: async () => seccion.pintar(),
        pintar(): void {
            const a = ctx.config()?.agente;
            const h = aviso ? [`<div class="fila falla">${esc(aviso)}</div>`] : [];
            if (a) {
                const propia = a.reunion !== a.reunion_por_defecto;
                h.push('<h2>Reuniones<small>al pinchar una reunión</small></h2>');
                h.push(`<div class="fila"><code>${esc(a.reunion)}</code>`
                    + '<span class="der"><a data-accion="plantilla" data-valor="cambiar">cambiar…</a>'
                    + (propia ? ' · <a data-accion="plantilla" data-valor="restablecer">volver a la de flow</a>' : '') + '</span></div>');
                h.push('<div class="fila dim">Se abre un tab «◷ hora reunión» con '
                    + `<b>${esc(a.nombre || 'ningún agente')}</b> y se le escribe esto. Marcadores: `
                    + '<code>{titulo}</code> <code>{hora}</code> <code>{fecha}</code> <code>{enlace}</code> <code>{proyecto}</code>. '
                    + 'El proyecto es la carpeta que comparte palabras con el título; si no hay, la cola «· proyecto:» se quita.</div>');
                if (!propia) h.push('<div class="fila dim">Es la de flow: supone la skill <code>/preparar-reunion</code> instalada en Claude Code.</div>');

                const propiaP = a.proyecto !== a.proyecto_por_defecto;
                h.push('<h2>Proyectos<small>al abrir un proyecto de la lista</small></h2>');
                h.push(`<div class="fila"><code>${esc(a.proyecto)}</code>`
                    + '<span class="der"><a data-accion="plantilla-proyecto" data-valor="cambiar">cambiar…</a>'
                    + (propiaP ? ' · <a data-accion="plantilla-proyecto" data-valor="restablecer">volver a la de fábrica</a>' : '') + '</span></div>');
                h.push('<div class="fila dim">Se abre un tab con el nombre de la carpeta, vinculado a ella, y se le escribe esto. Marcadores: '
                    + '<code>{nombre}</code> <code>{ruta}</code> <code>{carpeta}</code> <code>{documento}</code>.</div>');
            }
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            if (accion === 'plantilla') await cambiar('reunion', valor === 'restablecer');
            else if (accion === 'plantilla-proyecto') await cambiar('proyecto', valor === 'restablecer');
            else return false;
            return true;
        },
    };
    return seccion;
};
