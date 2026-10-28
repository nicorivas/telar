// Los modos de la página (web/modos.ts, telar.modos): cuál está puesto, lo que dice cada uno, y cambiarlo. Un clic en
// un ajuste lo cambia a mano en el modo puesto (vale hasta cambiar de modo); «guardar en este modo» lo deja escrito en
// la configuración (`[modos.<n>]`). «nuevo modo…» guarda lo que se ve ahora con otro nombre.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import * as modos from '../../../web/modos';
import * as ui from '../../../web/ui';
import type { FabricaSeccion } from './seccion';

const mostrarValor = (clave: string, v: modos.Valor | undefined): string => {
    if (v === undefined || v === '') return '—';
    if (clave === 'columnas') return v === 0 ? 'todo el ancho' : `${v} columnas`;
    return String(v).replace(/^si$/, 'sí');
};

/** Una línea que resume un modo: lo que más cambia de cómo se ve. */
const resumen = (m: modos.Modo): string => {
    const v = m.valores;
    return [`barra ${v.barra}`, `cabecera ${v.cabecera}`, `terminal ${v.columnas === 0 ? 'todo el ancho' : `${v.columnas} col`} ${v.posicion}`,
        `fondo ${v.fondo}`, `avisos ${v.avisos}`].filter(x => !x.includes('undefined')).join(' · ');
};

export const modosSeccion: FabricaSeccion = ctx => {
    const pintarSiSeVe = () => { if (ctx.seVe('modos')) seccion.pintar(); };
    modos.alCambiar(pintarSiSeVe);

    const elegirValor = async (a: modos.Ajuste) => {
        const actual = modos.valor(a.clave);
        if (a.opciones.length) {
            const e = await ui.elegir(a.opciones.map(o => ({ label: mostrarValor(a.clave, o), description: o === actual ? '← ahora' : '', id: o })),
                { titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, placeholder: a.ayuda || 'para este modo, hasta cambiar de modo' });
            if (e) modos.poner(a.clave, e.id);
            return;
        }
        const texto = (await ui.campo({
            titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, valor: actual === 0 ? 'todo' : String(actual ?? ''),
            ayuda: a.ayuda,
        }))?.trim();
        if (!texto) return;
        if (a.clave === 'columnas') {
            const n = /^todo$/i.test(texto) ? 0 : Number(texto);
            if (!Number.isInteger(n) || (n !== 0 && (n < 40 || n > 400))) { void ui.falla('telar: un número de 40 a 400, o «todo»'); return; }
            modos.poner('columnas', n);
        } else modos.poner(a.clave, texto);
    };

    const nuevo = async () => {
        const nombre = (await ui.campo({
            titulo: 'Modo nuevo', placeholder: 'lectura',
            ayuda: 'con lo que se ve ahora (el modo puesto y lo cambiado a mano). En minúsculas, letras, números y guiones.',
            validar: t => /^[a-z][a-z0-9-]{0,23}$/.test(t.trim()) ? undefined : 'en minúsculas: letras, números y guiones',
        }))?.trim();
        if (!nombre) return;
        const valores: Record<string, modos.Valor> = {};
        for (const a of modos.ajustes()) { const v = modos.valor(a.clave); if (v !== undefined) valores[a.clave] = v; }
        const r = await cli.guardarModo(nombre, valores, nombre);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        modos.recibir(r.datos.modos);
        modos.cambiar(nombre);
        void ui.estado(`telar: modo «${nombre}» guardado y puesto`, 4000);
    };

    const borrar = async (clave: string) => {
        const m = modos.lista().find(x => x.clave === clave);
        if (!m) return;
        const texto = m.de_fabrica ? `¿Volver «${m.nombre}» a como viene de fábrica?` : `¿Borrar el modo «${m.nombre}»?`;
        const boton = m.de_fabrica ? 'Volver' : 'Borrar';
        if (await ui.aviso(texto, boton) !== boton) return;
        const r = await cli.borrarModo(clave);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        modos.recibir(r.datos.modos);
    };

    const seccion = {
        clave: 'modos',
        nombre: 'modos',
        ayuda: 'los modos de la página (estándar, foco…): qué dice cada uno, cambiarlos, uno nuevo',
        abrir: () => { seccion.pintar(); return modos.leer(); },
        pintar(): void {
            const puesto = modos.puesto();
            const cambios = modos.cambiosAMano();
            const h: string[] = ['<div class="fila dim">⌥⇧F foco y vuelta · ⌥⇧M el siguiente · ◧ arriba, para elegir</div>'];
            h.push('<h2>modos<small>uno a la vez; cuál está puesto es de este navegador</small></h2>');
            for (const m of modos.lista()) {
                const es = m.clave === puesto.clave;
                const acciones = [
                    es ? '<span class="dim">puesto</span>' : `<a data-accion="modo-poner" data-valor="${esc(m.clave)}">poner</a>`,
                    m.cambiado ? `<a data-accion="modo-borrar" data-valor="${esc(m.clave)}" title="${m.de_fabrica ? 'quitar lo cambiado en la configuración' : 'borrarlo de la configuración'}">${m.de_fabrica ? 'de fábrica' : 'borrar'}</a>` : '',
                ].filter(Boolean).join(' · ');
                h.push(`<div class="item-pag"><div class="fila"><b>${esc(m.nombre)}</b>${m.cambiado && m.de_fabrica ? '<span class="dim"> · cambiado</span>' : ''}`
                    + `<span class="der">${acciones}</span></div><div class="fila dim">${esc(resumen(m))}</div></div>`);
            }
            h.push(`<div class="fila"><a data-accion="modo-nuevo">nuevo modo…</a><span class="dim"> · con lo que se ve ahora</span></div>`);

            const n = Object.keys(cambios).length;
            h.push(`<h2>«${esc(puesto.nombre)}», ahora<small>un clic cambia un ajuste en este modo, hasta cambiar de modo</small></h2>`);
            if (n) {
                h.push(`<div class="fila">${n === 1 ? 'un cambio' : `${n} cambios`} a mano<span class="der">`
                    + '<a data-accion="modo-guardar" title="dejarlos escritos en este modo">guardar en este modo</a> · '
                    + '<a data-accion="modo-descartar" title="volver a lo que dice el modo">descartar</a></span></div>');
            }
            let grupo = '';
            for (const a of modos.ajustes()) {
                if (a.grupo !== grupo) { grupo = a.grupo; h.push(`<div class="fila dim">${esc(grupo)}</div>`); }
                const cambiado = a.clave in cambios;
                h.push(`<div class="fila">&nbsp;&nbsp;${esc(a.nombre)}<span class="der">`
                    + `<a data-accion="modo-ajuste" data-valor="${esc(a.clave)}" title="${esc(a.ayuda || 'cambiarlo en este modo')}">${esc(mostrarValor(a.clave, modos.valor(a.clave)))}</a>`
                    + `${cambiado ? '<span class="dim"> · a mano</span>' : ''}</span></div>`);
            }
            if (!modos.ajustes().length) h.push('<div class="fila dim">leyendo…</div>');
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'modo-poner': if (valor) modos.cambiar(valor); return true;
                case 'modo-borrar': if (valor) await borrar(valor); return true;
                case 'modo-nuevo': await nuevo(); return true;
                case 'modo-guardar': {
                    const error = await modos.guardarCambios();
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    else void ui.estado(`telar: guardado en «${modos.puesto().nombre}»`, 4000);
                    return true;
                }
                case 'modo-descartar': modos.cambiar(modos.puesto().clave); return true;
                case 'modo-ajuste': {
                    const a = modos.ajustes().find(x => x.clave === valor);
                    if (a) await elegirValor(a);
                    return true;
                }
            }
            return false;
        },
    };
    return seccion;
};
