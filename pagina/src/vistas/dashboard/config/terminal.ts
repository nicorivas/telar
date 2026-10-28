// Cómo se ve la terminal de cada hilo (`[terminal]`): su ancho en columnas, dónde va (izquierda, centro, derecha) y
// su fondo (el telar tenue de siempre, nada, un color, una imagen o un módulo que trae `[fondo]`). Cada cambio se
// escribe en la configuración de esta máquina y se ve al tiro en las terminales abiertas (web/aspecto-terminal.ts).

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as aspectoTerminal from '../../../web/aspecto-terminal';
import * as modos from '../../../web/modos';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const POSICIONES = ['izquierda', 'centro', 'derecha'] as const;

export const terminal: FabricaSeccion = ctx => {
    let datos: cli.JsonFondos | undefined;
    let error = '';

    const leer = async () => {
        const r = await cli.fondosTerminal();
        if (r.datos) { datos = r.datos; error = ''; aspectoTerminal.cambiar({ ...aspectoTerminal.aspecto(), ...r.datos.actual }); }
        else error = r.error ?? 'no pude leer cómo se ve la terminal';
        if (ctx.seVe('terminal')) seccion.pintar();
    };

    const poner = async (clave: 'columnas' | 'posicion' | 'fondo', valor: string | number) => {
        // en otro modo que estándar, el modo manda sobre `[terminal]`: el cambio es de ese modo (a mano, hasta
        // cambiar de modo; ⚙ modos lo guarda en él)
        if (modos.puesto().clave !== 'estandar') {
            modos.poner(clave, valor);
            void ui.estado(`telar: en «${modos.puesto().nombre}», hasta cambiar de modo (⚙ modos lo guarda en él)`, 5000);
            if (ctx.seVe('terminal')) seccion.pintar();
            return;
        }
        const r = await cli.ajusteTerminal(clave, valor);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        const actual = { ...aspectoTerminal.aspecto(), [clave]: r.datos.valor } as aspectoTerminal.Aspecto;
        aspectoTerminal.cambiar(actual);
        if (datos) datos.actual = actual;
        void modos.leer();   // «estándar» toma la terminal de `[terminal]`
        void ui.estado('telar: listo, ya se ve en las terminales', 3000);
        if (ctx.seVe('terminal')) seccion.pintar();
    };

    const ancho = async () => {
        const v = (await ui.campo({
            titulo: 'Ancho de la terminal', valor: String(aspectoTerminal.aspecto().columnas || 'todo'), placeholder: '130',
            ayuda: 'hasta cuántas columnas (40 a 400), o «todo» para el ancho entero. Con más de ~140 se lee peor.',
            validar: t => /^\s*(todo|\d{2,3})\s*$/i.test(t) ? undefined : 'un número de 40 a 400, o «todo»',
        }))?.trim();
        if (v) await poner('columnas', /^todo$/i.test(v) ? 0 : Number(v));
    };

    const color = async () => {
        const v = (await ui.campo({
            titulo: 'Fondo: un color', placeholder: '#11111b', ayuda: 'en hexadecimal: #rgb o #rrggbb',
            validar: t => /^#([0-9a-f]{3}){1,2}$/i.test(t.trim()) ? undefined : 'como #11111b',
        }))?.trim();
        if (v) await poner('fondo', v);
    };

    const imagen = async () => {
        const v = (await ui.campo({
            titulo: 'Fondo: una imagen', placeholder: '~/fondos/nebulosa.jpg o https://…',
            ayuda: 'una ruta de esta máquina (png, jpg, gif, webp, svg) o una dirección https://. Se ajusta al alto y al ancho.',
        }))?.trim();
        if (v) await poner('fondo', `imagen:${v}`);
    };

    const opcion = (accion: string, valor: string, texto: string, activa: boolean, ayuda = '') =>
        `<a class="${activa ? 'si' : ''}" data-accion="${accion}" data-valor="${esc(valor)}"${ayuda ? ` title="${esc(ayuda)}"` : ''}>${esc(texto)}</a>`;

    const seccion = {
        clave: 'terminal',
        nombre: 'terminal',
        ayuda: 'el ancho de la terminal de los hilos, dónde va y qué hay alrededor',
        abrir: () => { seccion.pintar(); return leer(); },
        pintar(): void {
            const a = aspectoTerminal.aspecto();
            const h: string[] = [];
            if (error) h.push(`<div class="fila falla">${esc(error)}</div>`);
            h.push('<h2>ancho<small>cuánto se abre la terminal; la ventana del hilo toma ese tamaño</small></h2>');
            h.push(`<div class="fila">${a.columnas ? `hasta ${a.columnas} columnas` : 'todo el ancho'}<span class="der">`
                + '<a data-accion="terminal-ancho">cambiar</a></span></div>');
            h.push('<h2>posición<small>dónde va, si sobra espacio</small></h2>');
            h.push(`<div class="fila">${POSICIONES.map(p => opcion('terminal-posicion', p, p, a.posicion === p)).join(' · ')}</div>`);
            h.push('<h2>fondo<small>lo que se ve alrededor</small></h2>');
            const fondos = datos?.fondos ?? [];
            for (const f of fondos) {
                h.push(`<div class="fila">${opcion('terminal-fondo', f.valor, f.nombre, a.fondo === f.valor, f.descripcion)}`
                    + `<span class="dim">${f.tipo === 'modulo' ? ` · del módulo ${esc(f.valor)}` : ''}${f.descripcion ? ` · ${esc(f.descripcion)}` : ''}</span></div>`);
            }
            const propio = a.fondo.startsWith('#') ? `un color (${a.fondo})` : a.fondo.startsWith('imagen:') ? `una imagen (${a.fondo.slice(7)})` : '';
            h.push(`<div class="fila">${opcion('terminal-color', '', 'un color…', a.fondo.startsWith('#'))} · `
                + `${opcion('terminal-imagen', '', 'una imagen…', a.fondo.startsWith('imagen:'))}`
                + (propio ? `<span class="dim"> · ahora: ${esc(propio)}</span>` : '') + '</div>');
            h.push('<div class="fila dim">un módulo puede ser un fondo: <code>[fondo] archivo = "fondo.html"</code> en su modulo.toml (docs/modulos.md)</div>');
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'terminal-ancho': await ancho(); return true;
                case 'terminal-posicion': if (valor) await poner('posicion', valor); return true;
                case 'terminal-fondo': if (valor) await poner('fondo', valor); return true;
                case 'terminal-color': await color(); return true;
                case 'terminal-imagen': await imagen(); return true;
            }
            return false;
        },
    };
    return seccion;
};
