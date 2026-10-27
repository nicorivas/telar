// El servidor que aloja a otras personas (telar.alojamiento): cada alojado con sus topes de memoria y CPU, y los
// topes con que nacen los nuevos; «cambiar» los cambia (los de un alojado se aplican ya, sin cortar nada suyo).
// Solo para quien administra el bus: a los demás la API les dice que no y la sección se esconde. Aprobar, rechazar
// y quitar lugares sigue en «máquinas»; en la terminal, `telar servidor …`.

import * as cli from '../../../cli';
import { esc, fechaCorta } from '../../../estilo';
import { modelo } from '../../../modelo';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const ESTADO: Record<string, string> = {
    pendiente: 'pide un lugar', preparando: 'preparándose', activo: 'activo', 'falló': 'falló', rechazado: 'rechazado', quitado: 'quitado',
};

export const servidor: FabricaSeccion = ctx => {
    let datos: cli.JsonAlojamiento | undefined;
    let error = '';
    /** false si la API dijo que esta persona no administra el servidor (o no hay uno): la sección no va en el menú */
    let administra: boolean | undefined;
    let trabajando = '';

    const leer = async () => {
        if (!datos) ctx.pintar(['<div class="fila dim">leyendo…</div>']);
        const r = await cli.alojamiento();
        if (r.datos) { datos = r.datos; error = ''; administra = r.datos.administra; }
        else {
            error = r.error ?? 'no pude leer el servidor';
            if (/no administra|no hay bus|nadie atiende|no es el servidor/.test(error)) administra = false;
        }
        if (ctx.seVe('servidor')) seccion.pintar();
    };

    const cambiar = async (persona: string) => {
        const actual = persona ? datos?.alojamientos.find(a => a.persona === persona) : datos?.topes;
        const quien = persona || 'los alojados nuevos';
        const memoria = (await ui.campo({
            titulo: `Memoria · ${quien}`, valor: actual?.memoria ?? '2500M', placeholder: '2500M',
            ayuda: 'en M o G, entre 256M y 64G. El servidor tiene 8 GB entre todos.',
            validar: t => /^[1-9][0-9]*[KMGkmg]$/.test(t.trim()) ? undefined : 'como 2500M o 4G',
        }))?.trim();
        if (!memoria) return;
        const cpu = (await ui.campo({
            titulo: `CPU · ${quien}`, valor: actual?.cpu ?? '100%', placeholder: '100%',
            ayuda: 'en % de un núcleo: 100% es un núcleo entero, 200% dos (entre 10% y 800%).',
            validar: t => /^[1-9][0-9]*%?$/.test(t.trim()) ? undefined : 'como 100% o 50%',
        }))?.trim();
        if (!cpu) return;
        trabajando = persona || '__nuevos';
        seccion.pintar();
        const r = await cli.alojamientoTopes(persona, memoria, cpu);
        trabajando = '';
        if (!r.datos) void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`);
        else { datos = r.datos; void ui.estado(`telar: ${r.datos.hecho ?? 'hecho'}`, 5000); }
        if (ctx.seVe('servidor')) seccion.pintar();
    };

    const alojado = (a: cli.JsonAlojado) => {
        const activo = a.estado === 'activo';
        const accion = trabajando === a.persona ? '<span class="dim">…</span>'
            : activo ? `<a data-accion="servidor-topes" data-valor="${esc(a.persona)}" title="cambiar su memoria y su CPU: se aplica ya">cambiar</a>` : '';
        return `<div class="item-pag"><div class="fila"><b>${esc(a.persona)}</b><span class="dim"> · ${esc(ESTADO[a.estado] ?? a.estado)}</span>`
            + `<span class="der">${accion}</span></div>`
            + (activo ? `<div class="fila">${esc(a.memoria ?? '2500M')} de memoria · ${esc(a.cpu ?? '100%')} de CPU`
                + `${a.memoria ? '' : '<span class="dim"> (los de fábrica)</span>'}</div>` : '')
            + `<div class="fila dim">${a.maquina ? `pidió desde ${esc(a.maquina)} · ` : ''}${a.listo ? `desde ${esc(fechaCorta(new Date(a.listo * 1000).toISOString()))}` : ''}`
            + `${a.error ? ` · <span class="falla">${esc(a.error)}</span>` : ''}</div></div>`;
    };

    const seccion = {
        clave: 'servidor',
        nombre: 'servidor',
        ayuda: 'las personas alojadas en este servidor y sus topes de memoria y CPU',
        visible: () => modelo.hayBus && administra !== false,
        abrir: () => leer(),
        pintar(): void {
            const h = [`<div class="fila"><span class="dim">${datos ? `${esc(datos.servidor || 'el servidor')} · de ${esc(datos.dueno)}` : ''}</span>`
                + '<span class="der"><a data-accion="servidor-leer" title="volver a leer">↻</a></span></div>'];
            if (error) h.push(`<div class="fila falla">${esc(error)}</div>`);
            if (datos) {
                const t = datos.topes;
                h.push('<h2>para los nuevos<small>con esto nace cada lugar que apruebes</small></h2>');
                h.push(`<div class="fila">${esc(t?.memoria ?? '?')} de memoria · ${esc(t?.cpu ?? '?')} de CPU<span class="der">`
                    + (trabajando === '__nuevos' ? '<span class="dim">…</span>' : '<a data-accion="servidor-topes" data-valor="" title="los topes de los lugares que se aprueben desde ahora">cambiar</a>')
                    + '</span></div>');
                const lista = datos.alojamientos.filter(a => a.estado !== 'quitado' && a.estado !== 'rechazado');
                h.push(`<h2>alojados<small>${lista.length || 'nadie todavía'}</small></h2>`);
                for (const a of lista) h.push(alojado(a));
                h.push('<div class="fila dim">aprobar, rechazar y quitar lugares: en <a href="/maquinas">máquinas</a></div>');
            }
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'servidor-leer': await leer(); return true;
                case 'servidor-topes': await cambiar(valor); return true;
            }
            return false;
        },
    };
    return seccion;
};
