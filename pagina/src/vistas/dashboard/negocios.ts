// «proyectos › comercial»: los negocios (las unidades que el modo llama `negocios`, los deals de un pipeline), en
// secciones por cómo van según su documento, con las mismas piezas que la lista de proyectos (proyectos.ts): cada fila un
// ítem y cada etapa una seccion(), en el mismo contenedor (`#proyectos`), así que buscar, ordenar y plegar los hace la
// página igual (vista.ts, `aplicarProyectos`).
//
//   ⌄ EN NEGOCIACIÓN  9
//   ◕  Cliente Uno · Asesoría de datos                      hace 3d    4  ⋯   ← el círculo: hasta dónde llegó
//   ⌄ CON PROPUESTA  11
//   ◑  Cliente Dos · Taller                                  hace 2sem       ← lo que dice su documento, al pasar
//   ⌄ PROSPECTOS  61
//
// La etapa sale del Estado (o la Etapa) de su tabla de campos, como lo lee `telar proyectos`: negociación, propuesta
// (también un borrador), diagnóstico (POC, entendimiento), prospecto (lead), en pausa, perdido (vencido) y ganado; lo que
// no se entiende, al final, con lo que dice. El círculo se llena con lo que avanzó por ese camino; en pausa, un aro tenue;
// perdido, apagado. Un negocio no tiene plazo: al final va cuándo se tocó su carpeta (lo que se enfría se ve) y cuántos
// pendientes tiene.

import type * as cli from '../../cli';
import { barraBuscar } from '../../componentes/buscador';
import { item, type Pieza } from '../../componentes/item';
import { orden, type OpcionOrden } from '../../componentes/orden';
import { seccion, separador } from '../../componentes/seccion';
import { esc, haceCorto, normalizar } from '../../estilo';
import { I } from '../../web/iconos';
import { sinCasa } from './unidad';

/** Dónde va un negocio, según lo que dice su documento. */
export type EtapaNegocio = 'negociacion' | 'propuesta' | 'diagnostico' | 'prospecto' | 'pausado' | 'perdido' | 'ganado' | 'otro';

/** Las secciones, en su orden: lo más cerca de cerrarse arriba. Su título y cuánto avanzó (el llenado del círculo). */
export const ETAPAS_NEGOCIO: [EtapaNegocio, string, number][] = [
    ['negociacion', 'en negociación', .75], ['propuesta', 'con propuesta', .5], ['diagnostico', 'en diagnóstico', .25],
    ['prospecto', 'prospectos', 0], ['pausado', 'en pausa', 0], ['perdido', 'perdidos', 0], ['ganado', 'ganados', 1],
    ['otro', 'sin etapa', 0],
];

/** La etapa de un negocio, de su Estado: «Negociación», «Propuesta enviada…», «Borrador de propuesta», «POC»… */
export function etapaNegocio(estado: string | undefined): EtapaNegocio {
    const e = normalizar(estado ?? '');
    if (/ganad|firmad|adjudicad/.test(e)) return 'ganado';
    if (/perdid|vencid|descartad|rechazad/.test(e)) return 'perdido';
    if (/paus|congelad|en espera/.test(e)) return 'pausado';
    if (/negociac/.test(e)) return 'negociacion';
    if (/propuesta|cotizac/.test(e)) return 'propuesta';
    if (/^(poc|piloto)|entendimiento|diagnostico/.test(e)) return 'diagnostico';
    if (/prospect|lead/.test(e)) return 'prospecto';
    return 'otro';
}

/** El círculo de un negocio: cuánto avanzó por el camino de la venta; en pausa, un aro tenue; perdido, apagado. */
function senal(etapa: EtapaNegocio, ayuda: string): Pieza {
    const lleno = ETAPAS_NEGOCIO.find(([k]) => k === etapa)?.[2] ?? 0;
    const tono = etapa === 'pausado' ? 'tenue' : etapa === 'perdido' ? 'apagado' : etapa === 'ganado' ? 'exito' : undefined;
    return { circulo: { lleno }, ...tono ? { tono } : {}, ayuda };
}

/** Una fila, un ítem: su círculo, el cliente adelante y el nombre, y al final cuándo se tocó y cuántos pendientes (ceden
 *  antes que el nombre, como en proyectos: proyectos.css); su ⋯, al pasar el mouse. */
function filaNegocio(p: cli.JsonProyecto, etapa: EtapaNegocio, sel: string, pend: number | undefined, orden: number): string {
    const cliente = p.cliente && !p.interno && p.nombre.startsWith(p.cliente) ? p.cliente : '';
    const resto = cliente ? p.nombre.slice(cliente.length).replace(/^\s+/, '') : sinCasa(p);
    const dice = p.estado_completo || p.estado || 'su documento no dice en qué va';
    const tocado = p.modificado ? haceCorto(p.modificado) : '';
    return item({
        clases: ['proy', 'negocio'],
        accion: 'proy-sel',
        datos: { valor: p.ruta, unidad: p.area || 'sin área', pend: pend ? String(pend) : '', sec: `neg:${etapa}`, orden: String(orden),
            nombre: normalizar(p.nombre), plazo: (p.modificado ?? '').slice(0, 16),
            texto: normalizar(`${p.nombre} ${p.ruta} ${p.arquetipo} ${p.estado_completo ?? ''} ${p.area ?? ''}`) },
        activa: p.ruta === sel,
        apagada: etapa === 'perdido',
        ayuda: `${p.ruta}\n${dice}${p.hilo ? `\nhilo: ${p.hilo}${p.vivo ? '' : ' (dormido)'}` : ''}`,
        inicio: [senal(etapa, dice)],
        prefijo: cliente ? [{ texto: cliente, ayuda: `cliente: ${cliente}` }] : [],
        ...cliente ? { tituloHtml: `<span class="tono-tenue">${esc(resto)}</span>` } : { titulo: resto },
        meta: { html: `<span class="cuando-p" title="${esc(p.modificado ? `su carpeta se tocó ${p.modificado.slice(0, 16).replace('T', ' ')}` : 'sin fecha')}">${esc(tocado ? `hace ${tocado}` : '')}</span>`
            + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${pend || ''}</span>` },
        menu: { accion: 'proy-menu', icono: I.menu, datos: { valor: p.ruta }, ayuda: 'acciones de este negocio' },
    });
}

/** El orden de la lista de negocios, en la barra del buscador: el nombre, cuándo se tocó (lo que se enfría, arriba) y
 *  cuántos pendientes. */
const ORDENES_N: OpcionOrden[] = [
    { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre, alfabético' },
    { clave: 'plazo', icono: I.fecha, ayuda: 'cuándo se tocó: lo más quieto arriba' },
    { clave: 'pend', icono: I.lista, ayuda: 'pendientes: los que más tienen arriba' },
];

/** La lista de negocios: el buscador con su orden y una sección por etapa, cada una con su separador y su cabecera
 *  (`neg:<etapa>`, lo que se pliega y se recuerda en la página). */
export function htmlNegocios(lista: readonly cli.JsonProyecto[], sel: string, cuentas?: ReadonlyMap<string, number>): string[] {
    const por = new Map<EtapaNegocio, cli.JsonProyecto[]>(ETAPAS_NEGOCIO.map(([k]) => [k, []]));
    // lo corto del Estado (lo de antes de la primera coma o el primer punto: «Prospecto · ya hubo propuesta» es un
    // prospecto), y si no dice, lo entero
    for (const p of lista) por.get(etapaNegocio(p.estado || p.estado_completo))!.push(p);
    const h: string[] = [barraBuscar({ id: 'buscar-p', atajo: '/', placeholder: 'negocios', ayuda: `buscar en los ${lista.length} · ⏎ abre el primero · ⎋ borra`,
        cuenta: { id: 'proyectos-cuenta' }, claseBarra: 'proy-herr', herramientas: orden({ grupo: 'proyectos', accion: 'proy-orden', opciones: ORDENES_N, activa: '' }) }),
    '<div id="proyectos" class="negocios">'];
    let n = 0;
    for (const [etapa, titulo] of ETAPAS_NEGOCIO) {
        const xs = [...por.get(etapa)!].sort((a, b) => (b.modificado ?? '').localeCompare(a.modificado ?? '') || a.nombre.localeCompare(b.nombre));
        if (!xs.length) continue;
        const sec = `neg:${etapa}`;
        h.push(separador({ sec, orden: String(n++) }));
        h.push(seccion({ clave: sec, titulo, cuenta: xs.length, ayuda: `${titulo}: según el Estado de su documento`, abierta: true, accion: 'proy-seccion',
            clases: ['proy-sec-cab'], datos: { sec, orden: String(n++) },
            filas: () => xs.map(p => filaNegocio(p, etapa, sel, cuentas?.get(p.ruta), n++)).join('') }));
    }
    if (!lista.length) h.push('<div class="vacio">ningún negocio en este mundo</div>');
    h.push('<div id="proyectos-vacio" class="vacio" hidden></div></div>');
    return h;
}
