// Los modos de la página (web/modos.ts, telar.modos): cuál está puesto, lo que dice cada uno, y cambiarlo. Un clic en
// un ajuste lo cambia a mano en el modo puesto (vale hasta cambiar de modo); «guardar en este modo» lo deja escrito en
// la configuración (`[modos.<n>]`). «nuevo modo…» guarda lo que se ve ahora con otro nombre.
//
// Qué agentes residentes se ven en cada modo es aparte: una grilla con un agente por fila y un modo por columna, todos
// a la vez, donde un clic prende o apaga uno y lo guarda al tiro en ese modo (`agentes`, web/modos-agentes.ts), sin
// pasar por los cambios a mano. En el teléfono no cabe: se elige el modo arriba y se ven sus agentes, uno por fila.
// Con `[mundos]`, la grilla cruza los dos ejes: junto a cada agente, la raya del color de su mundo (⚙ mundos dice por
// qué), y arriba se elige un mundo (de entrada, el puesto): lo que ese mundo deja afuera se apaga, salvo en un modo
// todo, donde el mundo no esconde nada. Así se lee «en este modo y este mundo se ven estos».
//
// Qué pestañas de DASHBOARD ve cada modo, también aparte (`filas`, web/modos-pestanas.ts): una fila por modo, con cada
// pestaña con su ícono y ✓, y «todas» al final, como los modos de un mundo en ⚙ mundos. Un clic la prende o la apaga y lo
// guarda al tiro en ese modo; si es el puesto, la barra cambia sin recargar. Arriba de cada fila dice de dónde salen
// (de fábrica, de su base o propias del modo) y, si son propias, a cuáles vuelve. ⚙ pestañas manda sobre ellas: el orden de
// un modo con todas, y las que no se ven en ningún modo.

import * as cli from '../../../cli';
import { esc } from '../../../estilo';
import { modelo } from '../../../modelo';
import * as modos from '../../../web/modos';
import * as agentesModo from '../../../web/modos-agentes';
import * as mundo from '../../../web/mundo';
import * as temas from '../../../componentes/temas';
import * as ma from '../../../web/mundos-agentes';
import { rayaMundo, selectorMundos } from './mundos';
import * as ui from '../../../web/ui';
import { MODOS as ACTITUDES } from '../../../componentes/modos-mundos';
import type { FabricaSeccion, Contexto } from './seccion';
import { I } from '../../../web/iconos';
import * as filasModo from '../../../web/modos-pestanas';
import { decirPestanas, pestanasEnOrden } from './pestanas';

const mostrarValor = (clave: string, v: modos.Valor | undefined): string => {
    if (clave === 'etiquetas') return v ? String(v).split(',').join(', ') : 'todos los hilos';
    if (clave === 'campo') return v ? String(v) : 'en ninguna pantalla';
    if (clave === 'proyectos') return v ? String(v).split(',').join(', ') : 'todas las unidades';
    if (clave === 'negocios') return v ? String(v).split(',').join(', ') : 'no los cuenta';
    if (clave === 'iniciativas') return v ? String(v).split(',').join(', ') : 'sin sección de iniciativas';
    if (clave === 'agrupar_iniciativas') return v ? String(v) : 'sin agrupar';
    if (v === undefined || v === '') return '—';
    if (clave === 'sin_etiqueta') return String(v).replace(/-/g, ' ');
    if (clave === 'tema') return temas.nombre(String(v));
    if (clave === 'columnas') return v === 0 ? 'todo el ancho' : `${v} columnas`;
    return String(v).replace(/^si$/, 'sí');
};

/** Una línea que resume un modo: lo que más cambia de cómo se ve. */
const resumen = (m: modos.Modo): string => {
    const v = m.valores;
    return [`barra ${v.barra}`, `cabecera ${v.cabecera}`, `terminal ${v.columnas === 0 ? 'todo el ancho' : `${v.columnas} col`} ${v.posicion}`,
        `fondo ${v.fondo}`, `avisos ${v.avisos}`, ...(v.etiquetas ? [`hilos de ${String(v.etiquetas).split(',').join(', ')}`] : []),
        ...(v.glifos === 'si' ? [`glifos${v.iconos === 'glifos' ? ' en la barra' : ''}${v.campo ? `, campo ${v.campo}` : ''}`] : [])]
        .filter(x => !x.includes('undefined')).join(' · ');
};

/** Los agentes residentes, en el orden de la barra (sus secciones del grupo «agentes»). */
const residentes = () => modelo.secciones.filter(s => s.grupo === 'agentes');

/** El ícono de un modo: el de su actitud (uno propio, el de su base), como en la cabecera. */
const iconoDe = (m: modos.Modo): string => ACTITUDES.find(a => a.clave === modos.base(m))?.icono ?? I.modo;

/** Qué agentes se ven en cada modo. En un computador, la grilla (un agente por fila, un modo por columna, el puesto en
 *  violeta); en el teléfono, que no cabe, los modos arriba para elegir uno y sus agentes debajo. Cada marca es un clic.
 *  Con mundos, cada agente lleva la raya de su mundo y se elige uno arriba (`verMundo`, "" ambos): lo que deja afuera,
 *  apagado (lo sin clasificar se ve en todos; en un modo todo, el mundo no esconde nada). */
function grillaAgentes(verModo: string, verMundo: string): string[] {
    const agentes = residentes();
    const lista = modos.lista();
    const puesto = modos.puesto();
    const h = ['<h2>agentes<small>cuáles salen en AGENTES, en cada modo; un clic lo cambia y queda guardado en ese modo</small></h2>'];
    if (!agentes.length) return [...h, '<div class="fila dim">no hay agentes residentes</div>'];
    const conMundos = mundo.declarados().length > 0;
    const suMundo = (a: { clave: string }) => mundo.delAgente(a.clave)?.mundo ?? '';
    /** si el mundo elegido lo deja afuera en ese modo (sin modo: en alguno que no es todo) */
    const afuera = (a: { clave: string }, m?: modos.Modo) => conMundos && !ma.seVeEn(suMundo(a), verMundo, !!m && modos.base(m) === 'todo');
    const marca = (m: modos.Modo, a: { clave: string; nombre: string }, clase: string, texto = '') => {
        const si = modos.seVeAgente(a.clave, m);
        const fuera = afuera(a, m) ? ` · ${mundo.declarados().find(x => x.clave === verMundo)?.nombre ?? ''} lo deja afuera` : '';
        return `<a class="${clase}${si ? '' : ' no'}${fuera ? ' fuera' : ''}" data-accion="modo-agente" data-valor="${esc(`${m.clave} ${a.clave}`)}" `
            + `title="${esc(`${a.nombre} ${si ? 'sale' : 'no sale'} en «${m.nombre}»${fuera}: un clic lo ${si ? 'esconde' : 'muestra'}`)}">`
            + `<span class="i">${si ? I.hecha : I.punto}</span>${texto}</a>`;
    };
    /** el agente: la raya de su mundo (por qué, al pasar el mouse) y su nombre, apagado si el mundo elegido lo deja afuera */
    const nombre = (a: { clave: string; nombre: string }) => (conMundos
        ? `<span class="ma-agente${afuera(a) ? ' fuera' : ''}" title="${esc(`${a.nombre}: ${ma.porQue(mundo.delAgente(a.clave))}`)}">${rayaMundo(suMundo(a))}${esc(a.nombre)}</span>`
        : `<span class="ma-agente">${esc(a.nombre)}</span>`);
    // arriba, el mundo con que se lee
    if (conMundos) h.push(selectorMundos(verMundo, 'modo-agentes-mundo', 'leer la grilla con este mundo: lo que deja afuera, apagado'));
    // la grilla
    h.push(`<div class="ma-grilla" style="--fijas: ${lista.length - 1}"><div class="ma-fila ma-cab"><span></span>`);
    for (const m of lista) {
        h.push(`<span class="ma-modo${m.clave === puesto.clave ? ' si' : ''}" title="${esc(`«${m.nombre}»${m.clave === puesto.clave ? ', el puesto' : ''}`)}">`
            + `<span class="i">${iconoDe(m)}</span>${esc(m.nombre)}</span>`);
    }
    h.push('</div>');
    for (const a of agentes) {
        h.push(`<div class="ma-fila">${nombre(a)}${lista.map(m => marca(m, a, 'ma-celda')).join('')}</div>`);
    }
    h.push('</div>');
    // en el teléfono: el modo arriba, sus agentes debajo
    const visto = lista.find(m => m.clave === verModo) ?? puesto;
    h.push('<div class="ma-telefono"><div class="ma-modos">' + lista.map(m => `<a data-accion="modo-agentes-ver" data-valor="${esc(m.clave)}"`
        + `${m.clave === visto.clave ? ' class="si"' : ''}><span class="i">${iconoDe(m)}</span>${esc(m.nombre)}</a>`).join('') + '</div>');
    for (const a of agentes) h.push(marca(visto, a, 'fila ma-linea', `${conMundos ? rayaMundo(suMundo(a)) : ''}${esc(a.nombre)}`));
    h.push('</div>');
    h.push('<div class="fila dim">Un modo con todos marcados muestra también los agentes que vengan; en los otros, uno nuevo sale cuando se marca.</div>');
    return h;
}

/** De dónde salen las pestañas de un modo, en una línea: de fábrica, de otro modo (táctica, su base), o propias (y a
 *  cuáles vuelve sin su línea). */
function origenFilas(m: modos.Modo, hay: readonly { clave: string; nombre: string }[]): string {
    const o = modos.origen(m, 'filas');
    const nombre = (k: string) => modos.lista().find(x => x.clave === k)?.nombre ?? k;
    const de = o === 'fabrica' ? 'de fábrica' : `de ${nombre(o)}`;
    if (modos.deDonde(m, 'filas') === 'heredado') {
        const ayuda = o === 'fabrica' ? 'las que trae de fábrica' : `las de «${nombre(o)}»: este modo no dice las suyas`;
        return `<span class="dim" title="${esc(ayuda)}">${esc(de)}</span>`;
    }
    const heredado = m.heredados?.filas;
    return `<span class="dim">propias del modo · </span><a data-accion="modo-filas-heredar" data-valor="${esc(m.clave)}" `
        + `title="${esc(`quitar la línea: vuelve a las ${de}${heredado !== undefined ? ` (${decirPestanas(heredado, hay)})` : ''}`)}">volver a las ${esc(de)}</a>`;
}

/** Las pestañas de DASHBOARD de cada modo: una fila por modo, cada pestaña con su ícono y ✓ (las que ve), y «todas» al
 *  final; las que oculta ⚙ pestañas, apagadas (no se ven en ningún modo). Cada una es un clic. */
function pestanasDeModos(ctx: Contexto): string[] {
    const hay = pestanasEnOrden(ctx);
    const h = ['<h2>pestañas<small>cuáles de DASHBOARD ve cada modo, en el orden en que las nombra; un clic la cambia y queda guardado en ese modo</small></h2>'];
    if (!hay.length) return [...h, '<div class="fila dim">leyendo las pestañas…</div>'];
    const puesto = modos.puesto();
    for (const m of modos.lista()) {
        const filas = modos.filasDe(m);
        h.push(`<div class="fila dim"><span class="i">${iconoDe(m)}</span>${esc(m.nombre)}`
            + `${m.clave === puesto.clave ? '<span class="dim"> · el puesto</span>' : ''}<span class="der">${origenFilas(m, hay)}</span></div>`);
        const opcion = (clave: string, texto: string, si: boolean, ayuda: string, icono: string, oculta = false) =>
            `<a class="mu-modo${si ? ' si' : ''}${oculta ? ' oculta' : ''}" data-accion="modo-fila" data-valor="${esc(`${m.clave} ${clave}`)}" title="${esc(ayuda)}">`
            + `<span class="i">${si ? I.hecha : ''}</span><span class="i">${icono}</span>${esc(texto)}</a>`;
        const todas = !filasModo.elegidas(filas);
        const primera = filasModo.elegidas(filas)?.find(k => hay.some(x => x.clave === k && !x.oculta));
        h.push(`<div class="mu-modos">${hay.map(p => {
            const si = filasModo.ve(filas, p.clave);
            const ayuda = p.oculta ? `${p.nombre}: oculta en ⚙ pestañas, no se ve en ningún modo; un clic la ${si ? 'quita de' : 'agrega a'} «${m.nombre}» igual`
                : todas ? `«${m.nombre}» las ve todas: un clic la quita`
                    : si ? `${p.clave === primera ? 'la primera: a la que lleva poner el modo · ' : ''}un clic la quita`
                        : 'un clic la agrega, tras la que la precede en ⚙ pestañas';
            return opcion(p.clave, p.nombre, si, ayuda, filasModo.icono(p.clave), p.oculta);
        }).join('')}${opcion('*', 'todas', todas, 'todas, también las de los módulos que vengan, en el orden de ⚙ pestañas', I.lista)}</div>`);
    }
    h.push('<div class="fila dim">⚙ pestañas manda sobre esto: lo que oculta ahí no se ve en ningún modo (aquí, apagado), y un modo con '
        + 'todas las ve en su orden. Un modo que nombra las suyas las muestra en el orden en que las nombra: una que se agrega entra tras '
        + 'la que la precede en ⚙ pestañas. <a data-accion="config" data-valor="pestanas">⚙ pestañas</a></div>');
    return h;
}

export const modosSeccion: FabricaSeccion = ctx => {
    const pintarSiSeVe = () => { if (ctx.seVe('modos')) seccion.pintar(); };
    modos.alCambiar(pintarSiSeVe);
    mundo.alCambiar(pintarSiSeVe);
    /** en el teléfono, el modo cuyos agentes se ven ("": el puesto) */
    let verModo = '';
    /** el mundo con que se lee la grilla de agentes ("" ambos; undefined: el puesto) */
    let verMundo: string | undefined;

    /** Prender o apagar una pestaña en un modo (o «todas», `*`): se ve al tiro y se guarda en él. */
    const alternarFila = async (valor: string) => {
        const i = valor.indexOf(' ');
        const m = modos.lista().find(x => x.clave === valor.slice(0, i));
        const pestana = valor.slice(i + 1);
        if (i <= 0 || !m || !pestana) return;
        const heredado = m.heredados?.filas ?? modos.filasDe(m);
        const r = pestana === '*' ? filasModo.todas(heredado)
            : filasModo.alternar(modos.filasDe(m), pestanasEnOrden(ctx).map(p => p.clave), pestana, heredado);
        if (r.error) { void ui.estado(`telar: ${r.error}`, 4000); return; }
        // ya es eso (todas con todas): nada que escribir
        if (r.filas !== null && r.filas === modos.filasDe(m) && modos.deDonde(m, 'filas') === 'propio') return;
        if (r.filas === null && modos.deDonde(m, 'filas') === 'heredado') return;
        const error = await modos.guardarFilas(m.clave, r.filas);
        if (error) void ui.falla(`telar: no se guardó: ${error}`);
    };

    /** Prender o apagar un agente en un modo: se ve al tiro y se guarda en él. */
    const alternarAgente = async (valor: string) => {
        const [clave, agente] = [valor.slice(0, valor.indexOf(' ')), valor.slice(valor.indexOf(' ') + 1)];
        const m = modos.lista().find(x => x.clave === clave);
        if (!m || !agente) return;
        const nuevo = agentesModo.alternar(modos.agentesDe(m), agente, residentes().map(s => s.clave));
        const error = await modos.guardarAgentes(clave, nuevo);
        if (error) void ui.falla(`telar: no se guardó: ${error}`);
    };

    const elegirValor = async (a: modos.Ajuste) => {
        const actual = modos.valor(a.clave);
        if (a.opciones.length) {
            // de un tema, además, cómo es; y los temas son los de la página, con los propios (⚙ temas)
            const como = (o: string) => (a.clave === 'tema' ? temas.de(o)?.descripcion ?? '' : '');
            const opciones = a.clave === 'tema' ? temas.todos().map(t => t.clave) : a.opciones;
            const e = await ui.elegir(opciones.map(o => ({ label: mostrarValor(a.clave, o),
                description: [o === actual ? '← ahora' : '', como(o)].filter(Boolean).join(' · '), id: o })),
                { titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, placeholder: a.ayuda || 'para este modo, hasta cambiar de modo' });
            if (e) modos.poner(a.clave, e.id);
            return;
        }
        if (a.clave === 'etiquetas') {
            // separadas por coma; vacío: el modo no filtra
            const t = await ui.campo({ titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, valor: String(actual ?? '').split(',').join(', '),
                placeholder: 'trabajo', ayuda: `${a.ayuda}. Separadas por coma; a un hilo se le ponen desde su menú (${I.menu} › etiquetas…)` });
            if (t === undefined) return;
            const lista = t.toLowerCase().split(/[,\s]+/).map(e => e.replace(/^#/, '')).filter(Boolean);
            if (lista.some(e => !/^[a-z0-9áéíóúüñ][a-z0-9áéíóúüñ-]{0,23}$/.test(e))) { void ui.falla('telar: minúsculas, números y guiones; hasta 24 letras cada una'); return; }
            modos.poner('etiquetas', [...new Set(lista)].join(','));
            return;
        }
        if (a.clave === 'proyectos' || a.clave === 'negocios' || a.clave === 'iniciativas') {
            // nombres de arquetipos del perfil, separados por coma (llevan espacios: «proyecto cerrado»); vacío vale
            const t = await ui.campo({ titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, valor: String(actual ?? '').split(',').join(', '),
                placeholder: { proyectos: 'proyecto, proyecto propio', negocios: 'deal', iniciativas: 'iniciativa' }[a.clave], ayuda: `${a.ayuda}. Separados por coma` });
            if (t === undefined) return;
            const lista = t.toLowerCase().split(',').map(x => x.trim().replace(/\s+/g, ' ')).filter(Boolean);
            modos.poner(a.clave, [...new Set(lista)].join(','));
            return;
        }
        if (a.clave === 'agrupar_iniciativas') {
            // un campo del frontmatter de cada iniciativa; vacío: sin agrupar
            const t = await ui.campo({ titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, valor: String(actual ?? ''),
                placeholder: '{frontmatter:programa}', ayuda: a.ayuda,
                validar: t => !t.trim() || /^\{?\s*(?:frontmatter\s*:\s*)?[A-Za-z_][\w-]*\s*\}?$/.test(t.trim()) ? undefined
                    : 'un campo del frontmatter: {frontmatter:<clave>}' });
            if (t === undefined) return;
            const clave = /([A-Za-z_][\w-]*)\s*\}?$/.exec(t.trim())?.[1];
            modos.poner('agrupar_iniciativas', clave ? `{frontmatter:${clave}}` : '');
            return;
        }
        if (a.clave === 'campo') {
            // vacío: en ninguna pantalla. Las claves son las de las pestañas (⚙ pestañas) y las vistas de un hilo
            const t = await ui.campo({ titulo: `${a.nombre} · en «${modos.puesto().nombre}»`, valor: String(actual ?? ''),
                placeholder: 'ahora=banda, calendario=fondo 0.15',
                ayuda: `${a.ayuda}. Pantallas: ${ctx.dashboard.pestanas().map(p => p.clave).join(', ')}, conversacion, lectura; * las demás`,
                validar: t => t.split(',').every(x => !x.trim() || /^\s*[^=\s]+\s*=\s*(banda|fondo|nada)(\s+\d*\.?\d+)?\s*$/.test(x)) ? undefined
                    : 'cada una «pantalla=banda|fondo|nada [intensidad]», separadas por coma' });
            if (t !== undefined) modos.poner('campo', t.split(',').map(x => x.trim()).filter(Boolean).join(', '));
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
        // armado sobre la misma actitud que el puesto: hecho en estrategia, sigue siendo de estrategia
        const r = await cli.guardarModo(nombre, valores, nombre, modos.baseDeNuevo(nombre));
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        modos.recibir(r.datos.modos);
        void ui.estado(modos.cambiar(nombre) ? `telar: modo «${nombre}» guardado y puesto`
            : `telar: modo «${nombre}» guardado; este mundo no lo tiene, así que no se puso (⚙ mundos › modos)`, 5000);
    };

    const borrar = async (clave: string) => {
        const m = modos.lista().find(x => x.clave === clave);
        if (!m) return;
        const texto = m.de_fabrica ? `¿Volver «${m.nombre}» a como viene de fábrica?` : `¿Borrar el modo «${m.nombre}»?`;
        const boton = m.de_fabrica ? 'Volver' : 'Borrar';
        if (await ui.aviso(texto, boton, { destruye: true }) !== boton) return;
        const r = await cli.borrarModo(clave);
        if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
        modos.recibir(r.datos.modos);
    };

    const seccion = {
        clave: 'modos',
        nombre: 'modos',
        ayuda: 'los modos de la página (táctica, estrategia, foco, todo): qué dice cada uno, cambiarlos, uno nuevo',
        // de qué mundo es cada agente (`GET /mundos`), para el cruce de la grilla: llega aparte y repinta solo
        abrir: () => { seccion.pintar(); void mundo.leerDetalle(); return modos.leer(); },
        pintar(): void {
            const puesto = modos.puesto();
            const cambios = modos.cambiosAMano();
            const h: string[] = ['<div class="fila dim">⌥⇧F foco y vuelta · ⌥⇧M el siguiente · su ícono arriba, para elegir</div>'];
            h.push('<h2>modos<small>uno a la vez; cuál está puesto es de este navegador</small></h2>');
            for (const m of modos.lista()) {
                const es = m.clave === puesto.clave;
                const acciones = [
                    es ? '<span class="dim">puesto</span>' : modos.permitido(m.clave) ? `<a data-accion="modo-poner" data-valor="${esc(m.clave)}">poner</a>`
                        : `<span class="dim" title="${esc(`${mundo.mundo()?.nombre ?? 'ambos'} no lo tiene: ⚙ mundos › modos`)}">no es de ${esc(mundo.mundo()?.nombre ?? 'ambos')}</span>`,
                    m.cambiado ? `<a data-accion="modo-borrar" data-valor="${esc(m.clave)}" title="${m.de_fabrica ? 'quitar lo cambiado en la configuración' : 'borrarlo de la configuración'}">${m.de_fabrica ? 'de fábrica' : 'borrar'}</a>` : '',
                ].filter(Boolean).join(' · ');
                h.push(`<div class="item-pag"><div class="fila"><b>${esc(m.nombre)}</b>${m.cambiado && m.de_fabrica ? '<span class="dim"> · cambiado</span>' : ''}`
                    + `<span class="der">${acciones}</span></div><div class="fila dim">${esc(resumen(m))}</div></div>`);
            }
            h.push(`<div class="fila"><a data-accion="modo-nuevo">nuevo modo…</a><span class="dim"> · con lo que se ve ahora</span></div>`);
            h.push(...grillaAgentes(verModo, verMundo ?? mundo.puesto().mundo));
            h.push(...pestanasDeModos(ctx));

            const n = Object.keys(cambios).length;
            h.push(`<h2>«${esc(puesto.nombre)}», ahora<small>un clic cambia un ajuste en este modo, hasta cambiar de modo</small></h2>`);
            if (n) {
                h.push(`<div class="fila">${n === 1 ? 'un cambio' : `${n} cambios`} a mano<span class="der">`
                    + '<a data-accion="modo-guardar" title="dejarlos escritos en este modo">guardar en este modo</a> · '
                    + '<a data-accion="modo-descartar" title="volver a lo que dice el modo">descartar</a></span></div>');
            }
            let grupo = '';
            // qué agentes y qué pestañas se ven no van aquí: lo dicen la grilla y las filas de arriba, para todos los modos
            for (const a of modos.ajustes().filter(x => x.clave !== 'agentes' && x.clave !== 'filas')) {
                if (a.grupo !== grupo) { grupo = a.grupo; h.push(`<div class="fila dim">${esc(grupo)}</div>`); }
                const cambiado = a.clave in cambios;
                h.push(`<div class="fila">&nbsp;&nbsp;${esc(a.nombre)}<span class="der">`
                    + `<a data-accion="modo-ajuste" data-valor="${esc(a.clave)}" title="${esc(a.ayuda || 'cambiarlo en este modo')}">${esc(mostrarValor(a.clave, modos.valor(a.clave)))}</a>`
                    + `${cambiado ? '<span class="dim"> · a mano</span>' : ''}`
                    // el tema del mundo le gana al del modo: se dice cuál se ve y por qué
                    + `${a.clave === 'tema' && modos.tema().por === 'mundo' ? `<span class="dim" title="lo declara el mundo (⚙ mundos); elegir uno aquí vale mientras sigas en este mundo"> · se ve ${esc(mostrarValor('tema', modos.tema().clave))}, el de «${esc(mundo.puesto().mundo)}»</span>` : ''}`
                    // los temas y las densidades, lado a lado y en todos los estados: el catálogo de componentes (/componentes)
                    + `${a.clave === 'tema' || a.clave === 'densidad' ? ' · <a href="/componentes" target="_blank" title="el catálogo de componentes: uno al lado del otro">verlos</a>' : ''}`
                    // el color de cada tinta del tema que se ve: ⚙ temas
                    + `${a.clave === 'tema' ? ` · <a data-accion="config" data-valor="temas" title="el color de cada tinta del tema que ves (⚙ temas)">colores…</a>` : ''}</span></div>`);
            }
            if (!modos.ajustes().length) h.push('<div class="fila dim">leyendo…</div>');
            ctx.pintar(h);
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'modo-poner':
                    if (valor && !modos.cambiar(valor)) void ui.estado('telar: este mundo no tiene ese modo (⚙ mundos › modos)', 4000);
                    return true;
                case 'modo-borrar': if (valor) await borrar(valor); return true;
                case 'modo-nuevo': await nuevo(); return true;
                case 'modo-guardar': {
                    const error = await modos.guardarCambios();
                    if (error) void ui.falla(`telar: no se pudo: ${error}`);
                    else void ui.estado(`telar: guardado en «${modos.puesto().nombre}»`, 4000);
                    return true;
                }
                case 'modo-descartar': modos.cambiar(modos.puesto().clave); return true;
                case 'modo-agente': if (valor) await alternarAgente(valor); return true;
                case 'modo-fila': if (valor) await alternarFila(valor); return true;
                case 'modo-filas-heredar': {
                    const m = modos.lista().find(x => x.clave === valor);
                    if (m && modos.deDonde(m, 'filas') === 'propio') {
                        const error = await modos.guardarFilas(m.clave, null);
                        if (error) void ui.falla(`telar: no se guardó: ${error}`);
                    }
                    return true;
                }
                case 'modo-agentes-ver': verModo = valor; seccion.pintar(); return true;
                case 'modo-agentes-mundo': verMundo = valor; seccion.pintar(); return true;
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
