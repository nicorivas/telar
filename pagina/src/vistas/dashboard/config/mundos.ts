// Los mundos de la página (`[mundos]`, web/mundo.ts, telar.mundos): las partes de la vida que se miran por separado,
// con la misma forma que ⚙ modos. Arriba, los declarados y ambos: cuál está puesto y hasta cuándo, ponerlo a mano,
// borrarlo; y «nuevo mundo…», vacío. Debajo, de qué mundo es cada agente residente, en una grilla de solo lectura (un
// agente por fila, un mundo por columna, y por qué: la ruta que calza con su carpeta o la etiqueta de su hilo). Al final,
// lo que dice cada uno (color, tema, arte, etiquetas, áreas y rutas): un clic cambia uno y lo escribe al tiro en la
// configuración, solo esa línea (`PATCH /mundos/<n>`).
//
// El horario tiene su parte, debajo de los mundos (componentes/horario-editor.ts): la vista previa de la semana (un
// renglón por día, cada mundo en su color, los choques y los huecos), cuál rige fuera de todo horario y, por cada mundo,
// el editor de sus tramos (los días, un clic cada uno; desde y hasta, de a 15 minutos). Lo editado es un borrador: la
// vista previa lo muestra al tiro, y «guardar» lo escribe en la raíz (`<raiz>/.telar/mundos.toml`, para todas las máquinas:
// telar.mundos_raiz) si se puede; uno que se pisa con otro mundo no se guarda, y lo dice el pie (y, si igual llega, el
// servidor, 422). Al guardar, la banda cambia al tiro si cambia el mundo que rige. Lo que ya es de otro mundo no se
// escribe: la ventana lo dice antes de mandarlo, y si igual llega, lo dice el servidor. El tema se elige ahí mismo, de una
// fila con cada tema pintado con sus propios colores (`selectorTemas`): la página lo lleva mientras ese mundo rige. El
// arte (el dibujo de su tarjeta en la ventana de mundos, ⌘M), igual, de una fila con cada uno (`selectorArtes`). Los
// modos también, de una fila con cada modo (`selectorModos`): un clic agrega o quita uno; el primero es al que entra la
// página, y un mundo tiene al menos uno (todos, sin la línea). Bajo sus modos, solo para mirar, las pestañas de DASHBOARD
// que quedan en ese mundo: la unión de las de sus modos (⚙ modos › pestañas), sin las que oculta ⚙ pestañas.
//
// En el teléfono la grilla no cabe: se elige el mundo arriba y debajo van sus agentes, uno por fila (como ⚙ modos).
// `selectorMundos` y `rayaMundo` los usa también la grilla de ⚙ modos, para el cruce con los mundos.

import { esc } from '../../../estilo';
import * as cli from '../../../cli';
import * as mundo from '../../../web/mundo';
import * as ma from '../../../web/mundos-agentes';
import * as ui from '../../../web/ui';
import { decirMundo, decirTramo, tintaMundo, MODOS as ACTITUDES, type TramoHorario } from '../../../componentes/modos-mundos';
import * as hs from '../../../componentes/horario-editor';
import { arte, arteDeMundo, artes, alRegistrar } from '../../../componentes/arte';
import { leerArtes } from '../../../web/mundos-ventana';
import * as modosPagina from '../../../web/modos';
import * as temas from '../../../componentes/temas';
import { TINTAS } from '../../../componentes/temas';
import type { FabricaSeccion } from './seccion';
import { I } from '../../../web/iconos';
import * as filasModo from '../../../web/modos-pestanas';
import { pestanasEnOrden } from './pestanas';

/** La marca de un mundo: una raya corta de su color, en su celda; sin mundo (sin clasificar, ambos), la celda vacía. */
export function rayaMundo(clave: string): string {
    const m = mundo.declarados().find(x => x.clave === clave);
    return `<span class="mu-ranura">${m ? `<span class="mundo-raya"${tintaMundo(m)}></span>` : ''}</span>`;
}

/** Los mundos para elegir uno sobre una grilla (y ambos): el elegido, en su color; los demás, tenues, con su raya. */
export function selectorMundos(elegido: string, accion: string, ayuda: string): string {
    const opcion = (clave: string, nombre: string, estilo: string) =>
        `<a data-accion="${accion}" data-valor="${esc(clave)}"${clave === elegido ? ' class="si"' : ''}${estilo} title="${esc(ayuda)}">`
        + `${rayaMundo(clave)}${esc(nombre)}</a>`;
    return `<div class="mu-elegir">${mundo.declarados().map(m => opcion(m.clave, m.nombre, tintaMundo(m))).join('')}`
        + `${opcion('', 'ambos', '')}</div>`;
}

const lista = (v: readonly string[], nada: string) => (v.length ? v.join(', ') : nada);

/** El nombre de un tema, como se muestra (ámbar, con su tilde; uno propio, su clave). */
const nombreTema = (clave: string): string => temas.nombre(clave);

/** Los temas para elegir el de un mundo, cada uno con sus propios colores (su fondo, su texto y sus tintas, en una fila de
 *  cuadros): los de fábrica y los propios (⚙ temas), el elegido con ✓, y al final «el del modo», que es no tener uno.
 *  Cada uno es un clic. */
export function selectorTemas(nombre: string, elegido: string): string {
    const opcion = (clave: string, texto: string, ayuda: string, muestra: string) =>
        `<a class="mu-tema${clave === elegido ? ' si' : ''}" data-accion="mundo-tema" data-valor="${esc(`${nombre} ${clave}`)}"`
        + `${clave ? ` data-tema="${esc(clave)}"` : ''} title="${esc(ayuda)}"><span class="i">${clave === elegido ? I.hecha : ''}</span>`
        + `${esc(texto)}${muestra}</a>`;
    const tintas = `<span class="mu-tintas">${TINTAS.map(t => `<span style="color: var(--${t})">■</span>`).join('')}</span>`;
    return `<div class="mu-temas">${temas.todos().map(t => opcion(t.clave, t.nombre, t.descripcion, tintas)).join('')}`
        + `${opcion('', 'el del modo', 'sin tema propio: los colores del modo puesto (⚙ modos › tema)', '')}</div>`;
}

/** Los modos que puede tener un mundo: los que manda `GET /mundos` o, de un telar de antes, los que conoce la página. */
const modosQueHay = (d: cli.JsonMundos): { clave: string; nombre: string }[] =>
    d.modos ?? modosPagina.lista().map(m => ({ clave: m.clave, nombre: m.nombre }));

/** El ícono de un modo: el de su actitud (uno propio, el de aquella sobre la que se arma). */
const iconoModo = (clave: string): string => {
    const m = modosPagina.lista().find(x => x.clave === clave);
    return ACTITUDES.find(a => a.clave === (m ? modosPagina.base(m) : clave))?.icono ?? I.modo;
};

/** Los modos que tiene un mundo, dichos: «todos», o sus nombres en su orden y al que entra la página. */
export function decirModos(elegidos: readonly string[], hay: readonly { clave: string; nombre: string }[]): string {
    if (!elegidos.length) return 'todos';
    const nombre = (k: string) => hay.find(x => x.clave === k)?.nombre ?? k;
    return `${elegidos.map(nombre).join(', ')}${elegidos.length > 1 ? ` · entra en ${nombre(elegidos[0])}` : ''}`;
}

/** Los modos que quedan después de un clic en uno: si los tenía, sin él (si era el último, no: «» y el porqué); si no, al
 *  final de la lista. Sin la línea son todos: quitar uno deja los demás, y tenerlos todos de nuevo es no declararlos
 *  (null). */
export function alternarModo(elegidos: readonly string[], hay: readonly string[], clave: string): { modos: string[] | null; error: string } {
    const antes = elegidos.length ? [...elegidos] : [...hay];
    const despues = antes.includes(clave) ? antes.filter(k => k !== clave) : [...antes, clave];
    if (!despues.length) return { modos: [...antes], error: 'un mundo tiene al menos un modo' };
    return { modos: hay.every(k => despues.includes(k)) ? null : despues, error: '' };
}

/** Los modos para elegir los de un mundo: cada uno con su ícono, los suyos con ✓ (sin la línea, todos); y al final
 *  «todos», que es no declararlos. Cada uno es un clic. */
export function selectorModos(nombre: string, elegidos: readonly string[], hay: readonly { clave: string; nombre: string }[]): string {
    const opcion = (clave: string, texto: string, si: boolean, ayuda: string, icono: string) =>
        `<a class="mu-modo${si ? ' si' : ''}" data-accion="mundo-modo" data-valor="${esc(`${nombre} ${clave}`)}" title="${esc(ayuda)}">`
        + `<span class="i">${si ? I.hecha : ''}</span><span class="i">${icono}</span>${esc(texto)}</a>`;
    const primero = elegidos[0];
    return `<div class="mu-modos">${hay.map(m => {
        const si = !elegidos.length || elegidos.includes(m.clave);
        const ayuda = !elegidos.length ? `${nombre} tiene todos: un clic lo quita`
            : si ? `${m.clave === primero ? 'al que entra la página · ' : ''}un clic lo quita` : 'un clic lo agrega, al final';
        return opcion(m.clave, m.nombre, si, ayuda, iconoModo(m.clave));
    }).join('')}${opcion('', 'todos', !elegidos.length, 'sin la línea: todos los modos, también los propios que vengan', I.lista)}</div>`;
}

/** Los artes para elegir el de un mundo (componentes/arte.ts): los de fábrica y los de la raíz (`<raiz>/.telar/arte/`), el
 *  elegido con ✓, y al final «el que le toca» (sin `arte`: el que se llama como el mundo o lo sugiere, o la órbita).
 *  Cada uno es un clic. `toca`: el que lleva ahora. */
export function selectorArtes(nombre: string, elegido: string, toca: string): string {
    const opcion = (clave: string, texto: string, ayuda: string) =>
        `<a class="mu-tema${clave === elegido ? ' si' : ''}" data-accion="mundo-arte" data-valor="${esc(`${nombre} ${clave}`)}" title="${esc(ayuda)}">`
        + `<span class="i">${clave === elegido ? I.hecha : ''}</span>${esc(texto)}</a>`;
    return `<div class="mu-temas">${artes().map(a => opcion(a.clave, a.nombre, `${a.que || a.clave}${a.origen === 'archivo' ? ' (de la raíz)' : ''}`)).join('')}`
        + `${opcion('', 'el que le toca', `sin arte propio: ahora, ${arte(toca)?.nombre ?? toca}`)}</div>`;
}

/** Lo que dice un mundo, en una línea: su horario, sus etiquetas, su tema y cuánto suyo hay. */
function resumen(m: cli.JsonMundos['mundos'][number], fuera: string): string {
    const n = (k: number, una: string, varias: string) => (k ? `${k} ${k === 1 ? una : varias}` : '');
    return [
        m.horario.length ? m.horario.map(decirTramo).join(', ') : m.nombre === fuera ? '' : 'sin horario: solo a mano',
        m.nombre === fuera ? 'fuera de todo horario' : '',
        m.tema ? `tema ${nombreTema(m.tema)}` : '',
        m.modos?.length ? `modos ${m.modos.join(', ')}` : '',
        m.etiquetas.length ? `etiquetas ${m.etiquetas.join(', ')}` : '',
        [n(m.rutas.length, 'ruta', 'rutas'), n(m.areas.length, 'área', 'áreas')].filter(Boolean).join(', '),
    ].filter(Boolean).join(' · ') || 'todavía nada suyo: lo de abajo';
}

/** El nombre de un mundo, en su color; "" es ambos, en el del texto. */
const nombreEnColor = (clave: string): string => {
    const m = mundo.declarados().find(x => x.clave === clave);
    return m ? `<span class="mundo-nombre"${tintaMundo(m)}>${esc(m.nombre)}</span>` : 'ambos';
};

/** Qué pasa con un agente fuera de su mundo (`fuera_de_su_mundo` en su agente.toml), en palabras: lo que dice cada
 *  opción del selector de la grilla. */
export const FUERA: Record<cli.FueraDeSuMundo, { texto: string; ayuda: (mundo: string) => string }> = {
    'al-final': { texto: 'al final', ayuda: m => `con otro mundo puesto, la barra no lo muestra; ⌘K, la vista de agentes y la instrucción, solo en el modo todo, al final (el de fábrica). Lo de ${m}` },
    esconder: { texto: 'esconder', ayuda: m => `con otro mundo puesto no sale en ninguna parte, ni en el modo todo: ni él, ni sus hilos, ni lo que espera de él, ni lo de su carpeta; solo aquí, para configurarlo. Lo de ${m}` },
    ver: { texto: 'ver', ayuda: m => `sale en todos los mundos, como uno sin clasificar (lo suyo sigue siendo de ${m})` },
};

/** El selector de qué pasa con un agente fuera de su mundo: las tres, la elegida marcada; un clic escribe su agente.toml.
 *  Uno sin mundo sale en todos: no tiene qué elegir. */
export function selectorFuera(a: cli.JsonAgenteMundo): string {
    if (!a.mundo) return '<span class="mu-fuera dim" title="sin mundo: sale en todos">—</span>';
    const elegido = a.fuera_de_su_mundo ?? 'al-final';
    return `<span class="mu-fuera">${cli.FUERAS.map(f => `<a class="${f === elegido ? 'si' : ''}" data-accion="mundo-agente-fuera" `
        + `data-valor="${esc(`${a.clave} ${f}`)}" title="${esc(`${a.nombre}: ${FUERA[f].ayuda(a.mundo)}${f === elegido ? '' : ' · un clic lo escribe en su agente.toml'}`)}">`
        + `<span class="i">${f === elegido ? I.hecha : ''}</span>${esc(FUERA[f].texto)}</a>`).join('')}</span>`;
}

/** De qué mundo es cada agente: en un computador, la grilla (un agente por fila, un mundo por columna, por qué y, al
 *  final, qué pasa con él fuera de su mundo, que se elige ahí); en el teléfono, el mundo arriba y sus agentes debajo.
 *  Su mundo solo se mira: lo dice su carpeta o su hilo. */
function grillaAgentes(d: cli.JsonMundos, verMundo: string): string[] {
    const h = ['<h2>agentes<small>en qué mundo sale cada uno (lo dice la ruta que calza con su carpeta, o una etiqueta de su hilo) y qué pasa con él fuera de su mundo</small></h2>'];
    if (!d.agentes.length) return [...h, '<div class="fila dim">no hay agentes residentes</div>'];
    const declarados = mundo.declarados();
    const marca = (a: cli.JsonAgenteMundo, clave: string, clase: string, texto = '') => {
        const si = ma.seVeEn(a.mundo, clave);
        const suyo = !!a.mundo && a.mundo === clave;
        const m = declarados.find(x => x.clave === clave);
        return `<span class="${clase}${si ? suyo ? ' suyo' : '' : ' no'}"${suyo ? tintaMundo(m) : ''} title="${esc(`${a.nombre} ${si ? 'sale' : 'no sale'} en ${m?.nombre ?? 'ambos'}: ${ma.porQue(a)}`)}">`
            + `<span class="i">${si ? I.hecha : I.punto}</span>${texto}</span>`;
    };
    const por = (a: cli.JsonAgenteMundo) => `<span class="mu-por" title="${esc(ma.porQue(a))}">`
        + `<span class="i">${a.por === 'etiqueta' ? I.etiqueta : a.por === 'ruta' ? I.carpeta : a.por === 'agente.toml' ? I.agente : ''}</span>${esc(a.valor || 'sin clasificar')}</span>`;
    // la grilla: los mundos fijos y, a lo ancho, por qué
    h.push(`<div class="ma-grilla mu-grilla" style="--fijas: ${declarados.length}"><div class="ma-fila ma-cab"><span></span>`);
    for (const m of declarados) h.push(`<span class="ma-modo mu-mundo"${tintaMundo(m)}>${rayaMundo(m.clave)}${esc(m.nombre)}</span>`);
    h.push('<span></span><span class="ma-modo" title="qué pasa con él con otro mundo puesto: se escribe en su agente.toml">fuera de su mundo</span></div>');
    for (const a of d.agentes) {
        h.push(`<div class="ma-fila"><span class="ma-agente">${esc(a.nombre)}</span>${declarados.map(m => marca(a, m.clave, 'ma-celda')).join('')}${por(a)}${selectorFuera(a)}</div>`);
    }
    h.push('</div>');
    // en el teléfono: el mundo arriba, sus agentes debajo, cada uno con por qué
    h.push(`<div class="ma-telefono">${selectorMundos(verMundo, 'mundo-agentes-ver', 'sus agentes')}`);
    for (const a of d.agentes) {
        h.push(`<div class="fila ma-linea mu-linea">${marca(a, verMundo, 'mu-marca', esc(a.nombre))}${por(a)}</div>`);
        if (a.mundo) h.push(`<div class="fila mu-linea">&nbsp;&nbsp;fuera de ${esc(a.mundo)}${selectorFuera(a)}</div>`);
    }
    h.push('</div>');
    h.push('<div class="fila dim">Uno sin clasificar sale en todos. Para cambiar el de uno: una ruta de su mundo (abajo), o una etiqueta a su hilo (⋯ › etiquetas…).</div>');
    return h;
}

/** Los campos de un mundo, en el orden en que se muestran. */
const CAMPOS: { clave: cli.CampoMundo; nombre: string; ayuda: string }[] = [
    { clave: 'horario', nombre: 'horario', ayuda: 'cuándo se pone solo' },
    { clave: 'color', nombre: 'color', ayuda: 'su tinta en la página' },
    { clave: 'tema', nombre: 'tema', ayuda: 'los colores de la página mientras rige: le gana al tema del modo' },
    { clave: 'arte', nombre: 'arte', ayuda: 'el dibujo animado de su tarjeta en la ventana de mundos (⌘M)' },
    { clave: 'modos', nombre: 'modos', ayuda: 'los de la banda de modos que tiene mientras rige; el primero es al que entra la página' },
    { clave: 'etiquetas', nombre: 'etiquetas', ayuda: 'un hilo con una de estas es de este mundo, viva donde viva' },
    { clave: 'areas', nombre: 'áreas', ayuda: 'una tarea con una de estas áreas es de este mundo' },
    { clave: 'rutas', nombre: 'rutas', ayuda: 'lo que vive en estas carpetas es de este mundo' },
];

export const mundosSeccion: FabricaSeccion = ctx => {
    const pintarSiSeVe = () => { if (ctx.seVe('mundos')) seccion.pintar(); };
    mundo.alCambiar(pintarSiSeVe);
    // los artes de la raíz: se leen al montar la sección, y al llegar se repinta su fila
    alRegistrar(pintarSiSeVe);
    void leerArtes();
    // las pestañas de cada mundo salen de las de sus modos: si cambian (⚙ modos), se dice al tiro
    modosPagina.alCambiar(pintarSiSeVe);

    /** Las pestañas que quedan en un mundo, dichas: la unión de las de sus modos, en el orden de ⚙ pestañas. Solo se
     *  miran: se eligen en ⚙ modos. */
    const pestanasDelMundo = (claves: readonly string[]): string => {
        const hay = pestanasEnOrden(ctx).filter(p => !p.oculta);
        const susModos = modosPagina.lista().filter(x => !claves.length || claves.includes(x.clave));
        const union = filasModo.delMundo(susModos.map(modosPagina.filasDe), hay.map(p => p.clave));
        const ayuda = 'la unión de las de sus modos (⚙ modos › pestañas), sin las que oculta ⚙ pestañas; se eligen en ⚙ modos';
        const todas = susModos.find(x => !filasModo.elegidas(modosPagina.filasDe(x)));
        const texto = union === null ? `todas: «${todas?.nombre ?? ''}» las ve todas`
            : union.length ? union.map(k => hay.find(p => p.clave === k)?.nombre ?? k).join(', ') : 'ninguna';
        return `<div class="fila">&nbsp;&nbsp;pestañas<span class="der"><span class="dim" title="${esc(ayuda)}">${esc(texto)}</span>`
            + ' · <a data-accion="config" data-valor="modos" title="las de cada modo, en ⚙ modos › pestañas">elegirlas…</a></span></div>';
    };
    /** en el teléfono, el mundo cuyos agentes se ven (undefined: el puesto) */
    let verMundo: string | undefined;
    let error = '';
    /** el horario que se está editando de cada mundo, sin guardar todavía (lo que no está, es lo guardado) */
    const borradores = new Map<string, TramoHorario[]>();
    /** los mundos cuyo horario se está guardando */
    const guardando = new Set<string>();

    const falla = (e: string) => { if (e) void ui.falla(`telar: no se guardó: ${e}`); return !e; };

    /** el horario guardado de un mundo, como tramos */
    const guardado = (m: cli.JsonMundos['mundos'][number]): TramoHorario[] =>
        m.horario.map(t => ({ dias: [...t.dias], desde: t.desde, hasta: t.hasta }));
    /** el de cada mundo como se ve en la vista previa: el borrador, si hay; si no, el guardado */
    const delBorrador = (d: cli.JsonMundos) => d.mundos.map(m => ({ clave: m.nombre, tramos: borradores.get(m.nombre) ?? guardado(m) }));
    /** cambiar el borrador de un mundo (si queda igual a lo guardado, deja de ser borrador) y volver a dibujar */
    const cambiarBorrador = (nombre: string, f: (t: TramoHorario[]) => TramoHorario[]) => {
        const m = mundo.detalles()?.mundos.find(x => x.nombre === nombre);
        if (!m || guardando.has(nombre)) return;
        const nuevo = f((borradores.get(nombre) ?? guardado(m)).map(t => ({ ...t, dias: [...t.dias] })));
        if (hs.iguales(nuevo, guardado(m))) borradores.delete(nombre); else borradores.set(nombre, nuevo);
        seccion.pintar();
    };
    /** dónde vive un horario, en palabras: en la raíz (por el nombre de su carpeta) o solo aquí */
    const donde = (vive: string, d: cli.JsonMundos): string =>
        ({ raiz: `en ${cli.nombreRaiz(d.raiz)}: vale en todas las máquinas`, maquina: 'solo en esta máquina' } as Record<string, string>)[vive] ?? '';

    /** Guardar el horario de un mundo: lo revisa (como lo hará el servidor) y lo escribe; la banda lo toma al tiro. */
    const guardarHorario = async (nombre: string) => {
        const d = mundo.detalles();
        const tramos = borradores.get(nombre);
        if (!d || !tramos || guardando.has(nombre)) return;
        const otros = d.mundos.filter(x => x.nombre !== nombre).map(x => ({ clave: x.nombre, tramos: guardado(x) }));
        const r = hs.revisar(nombre, tramos, otros);
        if (r.error) { void ui.falla(`telar: no se guardó: ${r.error}`); return; }
        guardando.add(nombre);
        seccion.pintar();
        const antes = mundo.puesto().mundo;
        const e = await mundo.ajustar(nombre, { horario: r.textos.length ? r.textos : null });
        guardando.delete(nombre);
        if (!e) borradores.delete(nombre);
        if (ctx.seVe('mundos')) seccion.pintar();
        if (!falla(e)) return;
        const ahora = mundo.puesto();
        const nombreDe = (k: string) => k || 'ambos';
        void ui.estado(`telar: horario de ${nombre} guardado${d.raiz ? ` en ${cli.nombreRaiz(d.raiz)}` : ''}`
            + `${ahora.mundo !== antes ? `: ahora rige ${nombreDe(ahora.mundo)}` : ''}`, 4000);
    };

    /** La parte del horario: la semana (con lo editado), cuál rige fuera de todo horario y el editor de cada mundo. */
    const parteHorario = (d: cli.JsonMundos): string[] => {
        const h = ['<h2>horario<small>cuándo rige cada uno; lo que editas se ve al tiro en la semana, y se escribe al guardar</small></h2>'];
        if (d.error_raiz) h.push(`<div class="fila hs-error"><span class="i">${I.alerta}</span>${esc(`el archivo de ${cli.nombreRaiz(d.raiz)} no se lee, y no se aplica: ${d.error_raiz}`)}</div>`);
        for (const x of d.sobran_raiz ?? []) h.push(`<div class="fila hs-aviso"><span class="i">${I.alerta}</span>${esc(`en ${cli.nombreRaiz(d.raiz)} y no en esta máquina: ${x}`)}</div>`);
        const dibujo = d.mundos.map(m => ({ clave: m.nombre, nombre: m.nombre, color: m.color }));
        h.push(hs.htmlSemana(delBorrador(d), dibujo, d.fuera, new Date()));
        for (const c of hs.juntarChoques(hs.choques(delBorrador(d)))) {
            h.push(`<div class="fila hs-error"><span class="i">${I.alerta}</span>${esc(hs.decirChoques(c))}: a esa hora rige ${esc(d.fuera || 'ambos')} (fuera)</div>`);
        }
        const vive = d.fuera_vive ? ` · ${donde(d.fuera_vive, d)}` : '';
        h.push(`<div class="fila">&nbsp;&nbsp;fuera de todo horario<span class="der"><a data-accion="mundo-fuera" title="el que se pone cuando ningún horario rige${esc(vive)}">`
            + `${nombreEnColor(d.fuera)}</a></span></div>`);
        for (const m of d.mundos) {
            const tramos = borradores.get(m.nombre) ?? guardado(m);
            const otros = d.mundos.filter(x => x.nombre !== m.nombre).map(x => ({ clave: x.nombre, tramos: guardado(x) }));
            const r = hs.revisar(m.nombre, tramos, otros);
            const vive = m.horario_vive ? donde(m.horario_vive, d) : m.horario.length ? '' : 'sin horario';
            h.push(`<div class="fila">${rayaMundo(m.nombre)}<b class="mundo-nombre" style="--mundo-c: var(--${esc(m.color)})">${esc(m.nombre)}</b>`
                + `${tramos.length ? `<span class="der dim">${esc(tramos.map(t => decirTramo(t)).join(', '))}</span>` : ''}</div>`);
            h.push(hs.htmlEditor({ clave: m.nombre, nombre: m.nombre, color: m.color }, tramos,
                { cambiado: borradores.has(m.nombre), textos: r.textos, error: borradores.has(m.nombre) ? r.error : '',
                    guardando: guardando.has(m.nombre), vive }));
        }
        if (d.raiz && d.mundos.some(m => m.horario_vive === 'maquina')) {
            h.push(`<div class="fila dim hs-envuelve">lo que dice «solo en esta máquina» pasa a ${esc(cli.nombreRaiz(d.raiz))} con <code>telar mundos migrar</code>, o al guardarlo aquí</div>`);
        }
        return h;
    };

    /** Las horas de cada tramo son `<select>`: un cambio va al borrador. */
    const atarHoras = () => {
        for (const sel of document.querySelectorAll<HTMLSelectElement>('select[data-horario]')) {
            sel.addEventListener('change', () => {
                const [nombre, i, cual] = (sel.dataset.horario ?? '').split(' ');
                const n = Number(i), valor = Number(sel.value);
                if (!nombre || !Number.isInteger(n) || (cual !== 'desde' && cual !== 'hasta')) return;
                cambiarBorrador(nombre, ts => ts.map((t, k) => (k === n ? { ...t, [cual]: valor } : t)));
            });
        }
    };

    /** Cambiar un campo de un mundo: se pide en una ventana, se revisa ahí y se escribe al tiro. */
    const editar = async (nombre: string, campo: cli.CampoMundo) => {
        const d = mundo.detalles();
        const m = d?.mundos.find(x => x.nombre === nombre);
        if (!d || !m) return;
        const titulo = `${CAMPOS.find(c => c.clave === campo)?.nombre ?? campo} · ${nombre}`;
        // el tema, el arte y los modos se eligen en su fila, sin ventana; el horario, en su parte
        if (campo === 'tema' || campo === 'arte' || campo === 'modos' || campo === 'horario') return;
        if (campo === 'color') {
            // la de otro mundo se puede elegir, pero se dice: dos del mismo color no se distinguen
            const deOtro = (c: string) => d.mundos.find(x => x.nombre !== nombre && x.color === c)?.nombre;
            const opciones = [
                ...d.tintas.map(c => ({ id: c, label: c, color: c, icono: c === m.color_propio ? I.hecha : ' ',
                    description: deOtro(c) ? `la de ${deOtro(c)}` : '' })),
                { id: '', label: 'por orden', icono: m.color_propio ? ' ' : I.hecha,
                    description: `el primero libre${m.color_propio ? '' : `: ahora ${m.color}`}` },
            ];
            const inicial = Math.max(0, opciones.findIndex(o => o.id === m.color_propio));
            const e = await ui.elegir(opciones, { titulo, placeholder: 'su tinta: cada tema la pinta a su manera', inicial });
            if (e) falla(await mundo.ajustar(nombre, { color: e.id || null }));
            return;
        }
        // las listas: etiquetas, áreas y rutas, separadas por coma; lo que ya es de otro mundo, se dice antes de mandar
        const ayuda = {
            etiquetas: `las de un hilo (${I.menu} › etiquetas…): le ganan a su carpeta. Separadas por coma`,
            areas: 'el campo `area` de una tarea: le gana a la carpeta de su proyecto. Separadas por coma',
            rutas: 'carpetas relativas a la raíz (empresa/) o absolutas (~/worktrees/x-): con la barra final, esa carpeta y lo de '
                + 'dentro; sin ella, también lo que empieza igual. Si calzan varias, gana la más larga. Separadas por coma',
        }[campo];
        const t = await ui.campo({
            titulo, valor: m[campo].join(', '), ayuda,
            placeholder: { etiquetas: nombre, areas: nombre, rutas: `${nombre}/` }[campo],
            validar: t => {
                const v = ma.leerLista(t);
                if (campo === 'etiquetas' && v.some(e => !/^[a-z0-9áéíóúüñ][a-z0-9áéíóúüñ-]{0,23}$/.test(e))) return 'minúsculas, números y guiones; hasta 24 letras cada una';
                return ma.choque(d.mundos, nombre, campo, v) || undefined;
            },
        });
        if (t === undefined) return;
        const v = ma.leerLista(t);
        falla(await mundo.ajustar(nombre, { [campo]: v.length ? v : null }));
    };

    const elegirFuera = async () => {
        const fuera = mundo.deFuera();
        const opciones = [...mundo.declarados().map(m => ({ id: m.clave, label: m.nombre, color: m.color, icono: m.clave === fuera ? I.hecha : ' ' })),
            { id: '', label: 'ambos', icono: fuera ? ' ' : I.hecha, description: 'la página no filtra' }];
        const e = await ui.elegir(opciones, { titulo: 'fuera de todo horario', placeholder: 'el que se pone cuando ningún horario rige' });
        if (e) falla(await mundo.ponerFuera(e.id));
    };

    const nuevo = async () => {
        const hay = mundo.declarados().map(m => m.clave);
        const nombre = (await ui.campo({
            titulo: 'Mundo nuevo', placeholder: hay.length ? 'estudio' : 'trabajo',
            ayuda: 'vacío: lo suyo (horario, etiquetas, áreas, rutas) se le pone después. Una palabra, sin espacios ni signos.',
            validar: t => ma.nombreNuevo(t.trim(), hay) || undefined,
        }))?.trim();
        if (!nombre) return;
        if (falla(await mundo.crear(nombre))) void ui.estado(`telar: mundo «${nombre}» en la configuración; ponle lo suyo abajo`, 4000);
    };

    const borrar = async (nombre: string) => {
        const m = mundo.detalles()?.mundos.find(x => x.nombre === nombre);
        if (!m) return;
        const boton = 'Borrar';
        if (await ui.aviso(`¿Borrar el mundo «${nombre}»?`, boton, { destruye: true,
            detalle: 'Se quita de la configuración: lo que era suyo queda sin clasificar y se ve en todos los mundos.' }) !== boton) return;
        if (falla(await mundo.borrar(nombre))) void ui.estado(`telar: mundo «${nombre}» borrado`, 4000);
    };

    const seccion = {
        clave: 'mundos',
        nombre: 'mundos',
        ayuda: 'las partes de la vida (trabajo, personal…): cuál está puesto, qué es de cada una y su horario; uno nuevo',
        async abrir(): Promise<void> {
            seccion.pintar();
            error = await mundo.leerDetalle();
            if (ctx.seVe('mundos')) seccion.pintar();
        },
        pintar(): void {
            const d = mundo.detalles();
            const p = mundo.puesto();
            const ahora = new Date();
            const h: string[] = ['<div class="fila dim">⌥⇧0 el siguiente · su nombre arriba a la derecha, para elegir</div>'];
            h.push('<h2>mundos<small>uno a la vez, o ambos; lo pone su horario, y a mano dura hasta el próximo cambio del horario</small></h2>');
            if (!d) { ctx.pintar([...h, `<div class="fila dim">${error ? `no se pudieron leer: ${esc(error)}` : 'leyendo…'}</div>`]); return; }
            const como = decirMundo(p, mundo.declarados(), ahora).como;
            const item = (clave: string, nombre: string, linea: string, borrable: boolean) => {
                const es = p.mundo === clave;
                const m = mundo.declarados().find(x => x.clave === clave);
                const acciones = [
                    es ? `<span class="dim">puesto${como ? ` · ${esc(como)}` : ''}</span>` : `<a data-accion="mundo-poner" data-valor="${esc(clave)}" title="a mano: hasta el próximo cambio del horario">poner</a>`,
                    es && p.por === 'a-mano' ? '<a data-accion="mundo-horario" title="que lo ponga su horario">volver al horario</a>' : '',
                    borrable ? `<a data-accion="mundo-borrar" data-valor="${esc(clave)}" title="quitarlo de la configuración">borrar</a>` : '',
                ].filter(Boolean).join(' · ');
                return `<div class="item-pag"><div class="fila">${rayaMundo(clave)}<b class="mundo-nombre"${tintaMundo(m)}>${esc(nombre)}</b>`
                    + `<span class="der">${acciones}</span></div><div class="fila dim">${esc(linea)}</div></div>`;
            };
            if (!d.mundos.length) {
                h.push('<div class="fila dim">sin mundos: la página no filtra nada. Un mundo dice qué es suyo (sus carpetas, las áreas de las tareas, '
                    + 'las etiquetas de los hilos) y cuándo rige.</div>');
            }
            for (const m of d.mundos) h.push(item(m.nombre, m.nombre, resumen(m, d.fuera), true));
            if (d.mundos.length) h.push(item('', 'ambos', `todo junto: la página no filtra${d.fuera ? '' : ' · fuera de todo horario'}`, false));
            h.push('<div class="fila"><a data-accion="mundo-nuevo">nuevo mundo…</a><span class="dim"> · vacío: lo suyo se le pone abajo</span></div>');
            if (!d.mundos.length) { ctx.pintar(h); return; }

            h.push(...parteHorario(d));

            h.push(...grillaAgentes(d, verMundo ?? p.mundo));

            h.push('<h2>ajustes<small>un clic cambia uno y queda escrito en la configuración de esta máquina, en [mundos]</small></h2>');
            for (const m of d.mundos) {
                h.push(`<div class="fila dim">${rayaMundo(m.nombre)}${esc(m.nombre)}</div>`);
                for (const c of CAMPOS) {
                    // el horario se edita arriba, en su parte
                    if (c.clave === 'horario') continue;
                    if (c.clave === 'tema') {
                        // se elige ahí mismo: cada tema con sus colores, en una fila que baja si no cabe
                        h.push(`<div class="fila">&nbsp;&nbsp;tema<span class="der dim">${m.tema ? esc(nombreTema(m.tema)) : 'el del modo'}`
                            + ' · <a href="/componentes#tokens" target="_blank" title="el catálogo de componentes: los temas lado a lado, y su contraste">verlos</a>'
                            + `${m.tema ? ` · <a data-accion="config" data-valor="${esc(`temas:${m.tema}`)}" title="el color de cada tinta de ${esc(nombreTema(m.tema))} (⚙ temas)">colores…</a>` : ''}</span></div>`);
                        h.push(selectorTemas(m.nombre, m.tema ?? ''));
                        continue;
                    }
                    if (c.clave === 'arte') {
                        // se elige ahí mismo, de una fila con cada arte (los de fábrica y los de la raíz)
                        const suyo = arteDeMundo({ clave: m.nombre, arte: m.arte });
                        h.push(`<div class="fila">&nbsp;&nbsp;arte<span class="der dim" title="${esc(c.ayuda)}">${esc(suyo.nombre)}${m.arte ? '' : ' · el que le toca'}`
                            + ' · <a href="/componentes#mundos/artes" target="_blank" title="el catálogo: cada arte animado, y dónde probar uno nuevo">verlos</a></span></div>');
                        h.push(selectorArtes(m.nombre, m.arte ?? '', suyo.clave));
                        continue;
                    }
                    if (c.clave === 'modos') {
                        h.push(`<div class="fila">&nbsp;&nbsp;modos<span class="der dim" title="${esc(c.ayuda)}">${esc(decirModos(m.modos ?? [], modosQueHay(d)))}</span></div>`);
                        h.push(selectorModos(m.nombre, m.modos ?? [], modosQueHay(d)));
                        h.push(pestanasDelMundo(m.modos ?? []));
                        continue;
                    }
                    const valor = c.clave === 'color' ? `<span class="mundo-nombre" style="--mundo-c: var(--${esc(m.color)})">${esc(m.color)}</span>${m.color_propio ? '' : '<span class="dim"> · por orden</span>'}`
                            : lista(m[c.clave], 'ninguna');
                    h.push(`<div class="fila">&nbsp;&nbsp;${esc(c.nombre)}<span class="der">`
                        + `<a data-accion="mundo-ajuste" data-valor="${esc(`${m.nombre} ${c.clave}`)}" title="${esc(c.ayuda)}">${c.clave === 'color' ? valor : esc(valor)}</a></span></div>`);
                }
            }
            ctx.pintar(h);
            atarHoras();
        },
        async accion(accion: string, valor: string): Promise<boolean> {
            switch (accion) {
                case 'horario-dia': {
                    // «<mundo> <tramo> <día>»
                    const [nombre, i, dia] = valor.split(' ');
                    cambiarBorrador(nombre, ts => ts.map((t, k) => (k === Number(i) ? hs.alternarDia(t, Number(dia)) : t)));
                    return true;
                }
                case 'horario-quitar': {
                    const [nombre, i] = valor.split(' ');
                    cambiarBorrador(nombre, ts => ts.filter((_, k) => k !== Number(i)));
                    return true;
                }
                case 'horario-tramo': cambiarBorrador(valor, ts => [...ts, hs.tramoNuevo(ts)]); return true;
                case 'horario-deshacer': borradores.delete(valor); seccion.pintar(); return true;
                case 'horario-guardar': await guardarHorario(valor); return true;
                case 'mundo-poner': mundo.poner(valor); return true;
                case 'mundo-horario': mundo.volverAlHorario(); return true;
                case 'mundo-borrar': if (valor) await borrar(valor); return true;
                case 'mundo-nuevo': await nuevo(); return true;
                case 'mundo-fuera': await elegirFuera(); return true;
                case 'mundo-agentes-ver': verMundo = valor; seccion.pintar(); return true;
                case 'mundo-agente-fuera': {
                    // «<agente> <al-final|esconder|ver>»: se escribe en su agente.toml y se sube; la página lo aplica al tiro
                    const i = valor.lastIndexOf(' ');
                    const f = valor.slice(i + 1) as cli.FueraDeSuMundo;
                    if (i > 0 && cli.FUERAS.includes(f)) falla(await mundo.ponerFueraDeSuMundo(valor.slice(0, i), f));
                    return true;
                }
                case 'mundo-tema': {
                    // «<mundo> <tema>»; sin tema, «<mundo> »: el del modo
                    const i = valor.lastIndexOf(' ');
                    if (i > 0) falla(await mundo.ajustar(valor.slice(0, i), { tema: valor.slice(i + 1) || null }));
                    return true;
                }
                case 'mundo-arte': {
                    // «<mundo> <arte>»; sin arte, «<mundo> »: el que le toca
                    const i = valor.lastIndexOf(' ');
                    if (i > 0) falla(await mundo.ajustar(valor.slice(0, i), { arte: valor.slice(i + 1) || null }));
                    return true;
                }
                case 'mundo-modo': {
                    // «<mundo> <modo>»; sin modo, «<mundo> »: todos
                    const i = valor.lastIndexOf(' ');
                    const d = mundo.detalles();
                    const m = d?.mundos.find(x => x.nombre === valor.slice(0, i));
                    if (i <= 0 || !d || !m) return true;
                    const clave = valor.slice(i + 1);
                    if (!clave) { if (m.modos?.length) falla(await mundo.ajustar(m.nombre, { modos: null })); return true; }
                    const r = alternarModo(m.modos ?? [], modosQueHay(d).map(x => x.clave), clave);
                    if (r.error) { void ui.estado(`telar: ${r.error}`, 4000); return true; }
                    falla(await mundo.ajustar(m.nombre, { modos: r.modos }));
                    return true;
                }
                case 'mundo-ajuste': {
                    const i = valor.lastIndexOf(' ');
                    if (i > 0) await editar(valor.slice(0, i), valor.slice(i + 1) as cli.CampoMundo);
                    return true;
                }
            }
            return false;
        },
    };
    return seccion;
};
