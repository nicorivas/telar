// De dónde sale la agenda: Google Workspace (gws), una dirección iCal o ninguno; cuál está en uso y si responde.
// Se cambia con `telar config --calendario` (por la API); conectar uno iCal lo pide la orden telar.conectarCalendario.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as ui from '../../../web/ui';
import { olvidarDia } from '../dia';
import type { FabricaSeccion } from './seccion';

const NOMBRE: Record<string, string> = { gws: 'Google Workspace (gws)', ics: 'iCal', comando: 'un comando', ninguno: 'ninguno' };

export const calendario: FabricaSeccion = ctx => {
    let aviso = '';

    const elegir = async (valor: string) => {
        if (valor === 'ics') {
            await ui.orden('telar.conectarCalendario');
        } else {
            const r = await cli.elegirCalendario(valor);
            if (!r.ok) { aviso = r.err.trim().split('\n').pop() || 'no pude cambiar el calendario'; seccion.pintar(); return; }
        }
        aviso = '';
        olvidarDia();
        await ctx.releerConfig();
        await ctx.dashboard.actualizar(true);
        seccion.pintar();
    };

    const seccion = {
        clave: 'calendario',
        nombre: 'calendario',
        ayuda: 'de dónde sale la agenda',
        abrir: async () => seccion.pintar(),
        pintar(): void {
            const c = ctx.config()?.calendario;
            const h = aviso ? [`<div class="fila falla">${esc(aviso)}</div>`] : [];
            if (!c) { ctx.pintar(h); return; }
            const dia = ctx.dashboard.dia();
            const falla = dia?.fallas.find(f => f.startsWith('calendario'));
            const estado = c.tipo === 'ninguno' ? 'sin conectar'
                : falla ? `no responde (${falla.split(': ').pop()})`
                : dia?.agenda ? 'funcionando' : 'todavía sin consultar';
            h.push(`<div class="fila">En uso: <b>${esc(NOMBRE[c.tipo] ?? c.tipo)}</b> · <span class="${falla ? 'falla' : 'dim'}">${esc(estado)}</span></div>`);
            const opcion = (tipo: string, titulo: string, boton: string, lineas: string[]) => {
                const activa = c.tipo === tipo;
                h.push(`<div class="opcion${activa ? ' activa' : ''}"><div class="fila"><b>${activa ? '●' : '○'} ${titulo}</b>`
                    + (activa && tipo !== 'ics' ? '' : ` <span class="der"><a data-accion="calendario" data-valor="${tipo}">${boton}</a></span>`)
                    + '</div>' + lineas.map(l => `<div class="fila dim">${l}</div>`).join('') + '</div>');
            };
            opcion('gws', 'Google Workspace (gws)', 'usar', [
                'Lee tu calendario con la CLI <code>gws</code>, con la cuenta que ya tenga conectada. '
                    + 'No hay dirección que pegar ni secreto que guardar, y sirve aunque el administrador del dominio haya desactivado iCal.',
                !c.gws ? 'No está instalado en esta máquina.'
                    : c.gws_conectado ? `Conectado como <b>${esc(c.gws_cuenta || 'una cuenta')}</b>.`
                    : 'Instalado pero sin sesión: corre <code>gws auth login</code> en un terminal.',
            ]);
            opcion('ics', 'iCal', c.tipo === 'ics' ? 'cambiar dirección…' : 'usar…', [
                'Una dirección de calendario en formato .ics. En Google Calendar: Configuración › tu calendario › '
                    + '«Dirección <b>secreta</b> en formato iCal».',
                ...(c.tipo === 'ics' && c.fuente ? [`Guardada: <code>${esc(c.fuente)}</code> (la parte secreta no se muestra).`] : []),
                ...(c.tipo === 'ics' && c.publica ? ['<span class="falla">Es la dirección <b>pública</b>: solo funciona si el calendario '
                    + 'está publicado para todo internet. Usa la secreta.</span>'] : []),
            ]);
            opcion('ninguno', 'Ninguno', 'desconectar', ['El dashboard no muestra agenda.']);
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            if (accion !== 'calendario') return false;
            await elegir(valor);
            return true;
        },
    };
    return seccion;
};
