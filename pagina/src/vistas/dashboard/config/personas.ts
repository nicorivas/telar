// Quién entra al bus (telar.personas): los pedidos de entrada esperando, con aprobar y rechazar; las cuentas con
// su rol (dueño, admin, miembro), con cambiarlo y quitarla. Solo para el dueño del bus y los admin: a un miembro
// la API le dice que no (403) y la sección se esconde. Lo mismo, en la terminal: `telar bus personas|pedidos|…`.

import * as cli from '../../../cli';
import { esc, fechaCorta } from '../../../estilo';
import { modelo } from '../../../modelo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const fecha = (s: number) => fechaCorta(new Date(s * 1000).toISOString());

export const personas: FabricaSeccion = ctx => {
    let datos: cli.JsonPersonas | undefined;
    let error = '';
    /** false si la API dijo que esta persona no administra el bus: la sección no va en el menú */
    let administra: boolean | undefined;

    const leer = async () => {
        if (!datos) ctx.pintar(['<div class="fila dim">leyendo…</div>']);
        const r = await cli.personas();
        if (r.datos) { datos = r.datos; error = ''; administra = true; }
        else {
            error = r.error ?? 'no pude leer las cuentas del bus';
            if (/no administras|no administra el bus/.test(error)) administra = false;
        }
        if (ctx.seVe('personas')) seccion.pintar();
    };

    const hacer = async (accion: 'aprobar' | 'rechazar' | 'quitar' | 'rol', d: { pedido?: string; nombre?: string; rol?: string }) => {
        const r = await cli.personasAccion(accion, d);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        datos = r.datos;
        if (r.datos.falta) void ui.aviso(`telar: ${r.datos.hecho ?? 'hecho'}, pero falta recargar el bus: ${r.datos.falta}`);
        else void ui.estado(`telar: ${r.datos.hecho ?? 'hecho'}`, 5000);
        if (ctx.seVe('personas')) seccion.pintar();
    };

    const aprobar = async (pid: string) => {
        const p = datos?.pedidos.find(x => x.id === pid);
        if (!p) return;
        const e = await ui.elegir([
            { label: `aprobar a ${p.persona} como miembro`, description: 'su cuenta y nada más', id: 'miembro' },
            { label: `aprobar a ${p.persona} como admin`, description: 'aprueba pedidos y maneja cuentas, como tú', id: 'admin' },
        ], { titulo: `${p.persona} pide entrar`, placeholder: 'con qué rol entra' });
        if (e) await hacer('aprobar', { pedido: pid, rol: e.id });
    };

    const quitar = async (nombre: string) => {
        const e = await ui.elegir([
            { label: `sí, quitarle la cuenta a ${nombre}`, description: 'su telar deja de conectarse al bus; para volver, pide entrar de nuevo', id: 'si' },
            { label: 'no', description: '', id: 'no' },
        ], { titulo: `¿quitarle la cuenta a ${nombre}?` });
        if (e?.id === 'si') await hacer('quitar', { nombre });
    };

    const pedido = (p: cli.JsonPedidoEntrada) => {
        const pendiente = p.estado === 'pendiente';
        const de = [p.tailscale, p.desde, p.equipo ? `equipo ${p.equipo}` : ''].filter(Boolean).join(' · ');
        return `<div class="item-pag"><div class="fila"><b>${esc(p.persona)}</b>`
            + `<span class="dim"> · ${pendiente ? 'pide entrar' : `${esc(p.estado)}${p.por ? ` por ${esc(p.por)}` : ''}`}</span>`
            + `<span class="der dim">${esc(fecha(pendiente ? p.cuando : (p.decidido ?? p.cuando)))}</span></div>`
            + `<div class="fila dim">${esc(de)}</div>`
            + (pendiente ? `<div class="fila"><a data-accion="personas-aprobar" data-valor="${esc(p.id)}" title="su cuenta entra al bus y su telar se conecta solo">aprobar</a>`
                + ` · <a data-accion="personas-rechazar" data-valor="${esc(p.id)}" title="no entra; puede pedirlo de nuevo">rechazar</a></div>` : '')
            + '</div>';
    };

    const cuenta = (c: cli.JsonCuenta) => {
        const yo = c.nombre === datos?.quien;
        const acciones = c.rol === 'dueño' ? '<span class="dim">corre el bus</span>'
            : [c.rol === 'admin'
                ? `<a data-accion="personas-rol" data-valor="${esc(`${c.nombre}|miembro`)}" title="deja de administrar el bus">hacer miembro</a>`
                : `<a data-accion="personas-rol" data-valor="${esc(`${c.nombre}|admin`)}" title="aprueba pedidos y maneja cuentas, salvo la del dueño">hacer admin</a>`,
            yo ? '' : `<a data-accion="personas-quitar" data-valor="${esc(c.nombre)}" title="cerrarle la cuenta en el bus">quitar</a>`]
                .filter(Boolean).join(' · ');
        return `<div class="fila"><b>${esc(c.nombre)}</b>${yo ? '<span class="dim"> (tú)</span>' : ''}`
            + `<span class="dim"> · ${esc(c.rol)}</span><span class="der">${acciones}</span></div>`;
    };

    const seccion = {
        clave: 'personas',
        get nombre(): string {
            const n = datos?.pedidos.filter(p => p.estado === 'pendiente').length ?? 0;
            return n ? `personas (${n})` : 'personas';
        },
        ayuda: 'quién tiene cuenta en el bus, con qué rol, y quién pidió entrar',
        visible: () => modelo.hayBus && administra !== false,
        abrir: () => leer(),
        pintar(): void {
            const h = [`<div class="fila"><span class="dim">${datos ? `el bus de ${esc(datos.dueno)} · tú eres ${esc(datos.rol)}` : ''}</span>`
                + '<span class="der"><a data-accion="personas-leer" title="volver a leer">↻</a></span></div>'];
            if (error) h.push(`<div class="fila falla">${esc(error)}</div>`);
            if (datos) {
                const pendientes = datos.pedidos.filter(p => p.estado === 'pendiente');
                const decididos = datos.pedidos.filter(p => p.estado !== 'pendiente');
                h.push(`<h2>pedidos de entrada<small>${pendientes.length ? `${pendientes.length} esperando` : 'nadie esperando'}</small></h2>`);
                if (!pendientes.length) h.push('<div class="fila dim">quien quiera entrar corre <code>telar instalar --unirse</code> en el repositorio del equipo</div>');
                for (const p of pendientes) h.push(pedido(p));
                h.push(`<h2>cuentas<small>${datos.personas.length}</small></h2>`);
                for (const c of datos.personas) h.push(cuenta(c));
                if (decididos.length) {
                    h.push('<h2>decididos<small>las últimas dos semanas</small></h2>');
                    for (const p of decididos) h.push(pedido(p));
                }
            }
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'personas-leer': await leer(); return true;
                case 'personas-aprobar': if (valor) await aprobar(valor); return true;
                case 'personas-rechazar': if (valor) await hacer('rechazar', { pedido: valor }); return true;
                case 'personas-quitar': if (valor) await quitar(valor); return true;
                case 'personas-rol': {
                    const [nombre, rol] = valor.split('|');
                    if (nombre && rol) await hacer('rol', { nombre, rol });
                    return true;
                }
            }
            return false;
        },
    };
    return seccion;
};
