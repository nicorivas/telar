// La pantalla de proyectos responde en qué estamos: qué proyectos hay en ejecución y cómo van, cuáles parten pronto, y
// cuántos negocios vienen detrás. A la izquierda, una tabla de los proyectos (qué es un proyecto lo dice el modo:
// `proyectos`, los arquetipos del perfil) con su estado efectivo (en ejecución, por partir, en cierre, pausado,
// terminado, cerrado): el que se corrigió a mano en su documento, o el de su plazo, o el que dice su documento.
// La columna estado dice a qué poner atención: lo que está en su fase de cierre sale de «en ejecución». Cómo va cada uno
// sale de su plazo (`telar fechas`, clase plazo: el de un gestor de proyectos o su cronograma): la fase, de a cuartos,
// en un círculo (componentes/senales.ts, `fase`), el fin y lo que no cuadra. El nombre de cada columna ordena por ella,
// como en «tareas»; por estado, el orden de siempre, va en secciones. A la derecha, el elegido: arriba cómo va, y
// abajo tres pestañas: el resumen (lo que pide atención antes que lo que explica, sacado de los títulos de su README:
// readme.ts), sus pendientes (las viñetas de su documento y las tareas que dicen ser suyas) y su README plegado por
// secciones, que se abren con un clic. Como el calendario, dos columnas; la derecha se cambia sola (un mensaje
// `parcial`), sin repintar la lista, que no debe perder ni el scroll ni lo buscado. Debajo de los proyectos, aparte, las
// iniciativas (el trabajo propio, sin cliente: las unidades que el modo llama `iniciativas`), por programa
// (iniciativas.ts); un clic en su cabecera las deja solas. Arriba se dibuja; abajo, PantallaProyectos, el estado y las
// acciones.

import { barraBuscar } from '../../componentes/buscador';
import { C, ETAPA_I, I } from '../../web/iconos';
import { circulo } from '../../componentes/circulo';
import * as S from '../../componentes/senales';
import * as entidades from '../../web/entidades';
import * as modos from '../../web/modos';
import * as mundo from '../../web/mundo';
import * as ui from '../../web/ui';
import type { Opcion } from '../../web/ui';
import * as cli from '../../cli';
import { disco } from '../../disco';
import { esc, haceCorto, normalizar } from '../../estilo';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, Pendiente, conLoSalido, generacionDeAhora, olvidarDia, pendientes, yo } from './dia';
import { type Accion, type EnBarra, type Pantalla, type Tablero, abrirEnlace } from './pantalla';
import { elegirDueno } from './tareas';
import { filaTarea } from './fila-tarea';
import * as readme from './readme';
import { sinCasa, unidadDe } from './unidad';
import { type Vocabulario, SIN_VOCABULARIO, claseDe, comoVaIniciativa, estadoDe, htmlIniciativas, programas, agrupar, vocabularioDe } from './iniciativas';
import { type Seccion, NOMBRE_SECCION as NOMBRE, SECCIONES, aManoDesde, cuandoDe, diaCorto, efectivo, enCierre, esCerrado, hoyIso, ordenarSeccion, porQue,
    seccionDe, senalFase } from './plazo-proyecto';

// lo del estado efectivo y el plazo vive en plazo-proyecto.ts (puro, con su prueba); lo de siempre, desde aquí
export { type Seccion, SECCIONES, diaCorto, enCierre, esCerrado, seccionDe } from './plazo-proyecto';


/** El color del estado según de qué tipo es: en marcha, por ganar, trabado o terminado. */
function claseEstado(estado: string): string {
    const e = normalizar(estado);
    if (/^(activo|ganado|en curso|en ejecucion)/.test(e)) return 'e-activo';
    if (/^(prospecto|propuesta|negociacion|entendimiento|poc|lead|diagnostico)/.test(e)) return 'e-abierto';
    if (/pausa|vencido|perdido|trabado|bloquead/.test(e)) return 'e-trabado';
    return '';
}

/** El lugar de un estado en el orden por defecto: lo que está en marcha arriba, después lo que se
 *  está ganando (de lo más cerca a lo más lejos), lo trabado, lo cerrado, y lo sin estado al final. */
export function rangoEstado(estado: string): number {
    const e = normalizar(estado);
    if (!e) return 9;
    const orden: [RegExp, number][] = [
        [/^(activo|ganado|en curso|en ejecucion)/, 0], [/^negociacion/, 1], [/^propuesta/, 2],
        [/^(entendimiento|poc|diagnostico)/, 3], [/^(prospecto|lead)/, 4], [/pausa/, 5],
        [/^(vencido|perdido|trabado|bloquead)/, 6], [/^(cerrado|terminado|finalizado)/, 7],
    ];
    return orden.find(([re]) => re.test(e))?.[1] ?? 8;
}

/** Un servicio (lo que se vende, no un proyecto con cliente): no va en la lista de proyectos ni se ofrece
 *  al elegir uno. Sí sirve para decir de qué es una tarea, así que la lista completa se guarda igual. */
export const esServicio = (p: cli.JsonProyecto): boolean => p.arquetipo === 'servicio';

/** De qué carpeta de la raíz es una unidad: la primera de su ruta (trabajo, personal, consultoria…). */
export const raizDe = (ruta: string): string => ruta.split('/')[0] || ruta;

/** El área que declara su documento (`area:` en el frontmatter), o «sin área». */
export const areaDe = (p: cli.JsonProyecto): string => p.area || 'sin área';

/** De qué unidad es una carpeta (unidad.ts): la más honda que la contiene. */
export { unidadDe } from './unidad';

/** Una fila de botones que filtra la lista por un campo (`data-pf`); la página marca el activo. */
function filtro(campo: string, todos: string, valores: Map<string, number>, orden: string[] = []): string {
    if (valores.size < 2) return '';
    // con `orden`, ese orden (lo que no está en él, después); si no, lo más común primero
    const lugar = (v: string) => { const i = orden.indexOf(v); return i < 0 ? orden.length : i; };
    return `<div class="titulo-tareas areas-t"><span class="modos"><button data-pf="${campo}" data-pv="">${esc(todos)}</button>`
        + [...valores].sort((a, b) => lugar(a[0]) - lugar(b[0]) || b[1] - a[1])
            .map(([v, n]) => `<button data-pf="${campo}" data-pv="${esc(v)}">${esc(v)} ${n}</button>`).join('')
        + '</span></div>';
}

function contar(xs: string[]): Map<string, number> {
    const m = new Map<string, number>();
    for (const x of xs) if (x) m.set(x, (m.get(x) ?? 0) + 1);
    return m;
}

/** El ícono de una etapa (web/iconos.ts, ETAPA_I): por su palabra, con o sin tilde; una que no conoce, el de etapa. */
export function iconoEtapa(etapa: string): string {
    const e = normalizar(etapa);
    const clave = /^prepar/.test(e) ? 'preparacion' : /^inici/.test(e) ? 'inicio' : /^desarroll/.test(e) ? 'desarrollo'
        : enCierre(e) ? 'cierre' : /^(cerrad|hecho|terminad)/.test(e) ? 'cerrado' : '';
    return ETAPA_I[clave] ?? I.etapa;
}

/** Una fila: la fase (el círculo), el nombre, el estado efectivo, la etapa (un ícono; la palabra, al pasar), el plazo,
 *  cuántos pendientes tiene y su ⋯. En la tabla extendida (`.extendida`, el botón ↔ de la banda), la etapa en palabras
 *  y las columnas `solo-x`: el inicio, el área y el aviso. Lleva en `data-` lo que ordena cada columna
 *  (vista.ts, `aplicarProyectos`) y `data-orden`, su lugar de siempre. */
function filaProyecto(p: cli.JsonProyecto, sec: Seccion, sel: string, pend: number | undefined, hoy: string, orden: number): string {
    const pl = p.plazo;
    const aviso = pl?.aviso ?? '';
    const senal = senalFase(sec, pl, p.estado_completo);
    const marca = senal?.circulo
        ? `<span class="senal${senal.tono ? ` tono-${senal.tono}` : ''}"${senal.ayuda ? ` title="${esc(senal.ayuda)}"` : ''}>${circulo(senal.circulo)}</span>` : '';
    // el estado efectivo, y al pasar, de dónde sale; tenue si nadie lo confirma
    const pq = porQue(p, sec, hoy);
    const estado = `<span class="estado-p${pq.supuesto ? ' tenue' : ''}" title="${esc(pq.ayuda)}">${esc(NOMBRE[sec])}</span>`;
    // la etapa: la fase del plazo, un ícono (qué clase de trabajo) y su palabra al pasar; en la tabla extendida, la
    // palabra. Sin plazo, nada (el estado del documento ya está en su columna)
    const etapa = pl?.etapa
        ? `<span class="etapa" title="${esc(`etapa: ${pl.etapa}`)}"><span class="i solo-c">${iconoEtapa(pl.etapa)}</span><span class="solo-x">${esc(pl.etapa)}</span></span>`
        : `<span class="etapa" title="${pl ? 'su fuente no dice la etapa' : 'sin plazo'}"></span>`;
    // lo que solo se ve en la tabla extendida: cuándo partió, su área y lo que no cuadra (cuánto avanzó ya lo dicen el
    // círculo y la etapa)
    const extras = `<span class="inicio-p solo-x">${pl ? esc(diaCorto(pl.inicio)) : ''}</span>`;
    // del aviso, lo que no dice ya el plazo («venció 22-oct» está en su columna)
    const avisoX = aviso.split(' · ').filter(a => !/^venci/.test(a)).join(' · ');
    const extras2 = `<span class="area-p solo-x">${esc(p.area ?? '')}</span>`
        + `<span class="aviso-p solo-x tono-atencion">${esc(avisoX)}</span>`;
    const { texto: cuando, iso: cuandoIso, vencido, ayuda: plazoAyuda } = cuandoDe(sec, pl, aManoDesde(p), hoy);
    const clase = vencido ? ' tono-atencion' : '';
    const texto = normalizar(`${p.nombre} ${p.ruta} ${p.arquetipo} ${NOMBRE[sec]} ${pl?.etapa ?? ''} ${p.estado ?? ''} ${p.area ?? ''}`);
    // el cliente adelante y en color; lo demás del nombre, apagado. El de la casa (`internos`) no: va el nombre sin él
    const cliente = p.cliente && !p.interno && p.nombre.startsWith(p.cliente) ? p.cliente : '';
    const nombre = cliente ? `<span class="cliente">${esc(cliente)}</span><span class="resto">${esc(p.nombre.slice(cliente.length))}</span>`
        : esc(sinCasa(p));
    const fecha = p.modificado ?? '';
    // lo que ordena cada columna: el nombre, la fase (de 0 a 1), la fecha que se ve y cuántos pendientes
    const fase = typeof pl?.avance === 'number' ? String(pl.avance) : '';
    return `<div class="fila clic proy${p.ruta === sel ? ' sel' : ''}${sec === 'cerrado' ? ' cerrado' : ''}" data-accion="proy-sel"`
        + ` data-valor="${esc(p.ruta)}" data-unidad="${esc(areaDe(p))}" data-pend="${pend || ''}" data-texto="${esc(texto)}"`
        + ` data-sec="${sec}" data-orden="${orden}" data-nombre="${esc(normalizar(p.nombre))}" data-fase="${fase}" data-plazo="${cuandoIso}"`
        + ` title="${esc(`${p.ruta}${fecha ? `\nmodificado ${fecha.slice(0, 16).replace('T', ' ')}` : ''}${p.hilo ? `\nhilo: ${p.hilo}${p.vivo ? '' : ' (dormido)'}` : ''}${aviso ? `\n${aviso}` : ''}`)}">`
        + `<span class="at">${marca}</span><span class="que">${nombre}</span>${estado}${etapa}${extras}`
        + `<span class="cuando-p${clase}" title="${esc(plazoAyuda)}">${esc(cuando)}</span>${extras2}`
        + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${pend ? pend : ''}</span>`
        + `<span class="menu-fila menu-col" data-accion="proy-menu" data-valor="${esc(p.ruta)}" title="acciones de este proyecto">${I.menu}</span></div>`;
}

/** Las columnas de la tabla que se ordenan: la clave (el `data-` de cada fila que la ordena), su nombre y cómo ordena.
 *  Por estado es el orden de siempre: en secciones, y dentro de cada una, el suyo (`ordenar`). */
export const COLUMNAS_P: [string, string, string][] = [
    ['nombre', 'proyecto', 'nombre, alfabético'], ['estado', 'estado', 'estado efectivo, en secciones (el orden de siempre)'],
    ['fase', 'etapa', 'etapa, de la primera a la última'], ['plazo', 'plazo', 'la fecha que se ve: lo más antiguo arriba'],
    ['pend', 'tareas', 'pendientes: los que más tienen arriba'],
];

/** La lista de la izquierda: la banda de herramientas (buscar, el área, ver los cerrados, la tabla extendida), los
 *  nombres de las columnas y las filas, con la cabecera de cada sección entre ellas. Buscar, filtrar, ordenar por una
 *  columna, mostrar los cerrados y extender la tabla ocurre en la página (`aplicarProyectos`, vista.ts); elegir una
 *  fila pide su detalle. */
export function htmlListaProyectos(lista: cli.JsonProyecto[], sel: string, cuentas?: Map<string, number>, areas: string[] = [],
    buscables = lista.length): string[] {
    const hoy = hoyIso();
    const por = new Map<Seccion, cli.JsonProyecto[]>(SECCIONES.map(([k]) => [k, []]));
    for (const p of lista) por.get(seccionDe(p, hoy))!.push(p);
    const cerrados = por.get('cerrado')!.length;
    const h: string[] = [barraBuscar({ id: 'buscar-p', atajo: '/', placeholder: buscables > lista.length ? 'proyectos e iniciativas' : 'proyectos',
        ayuda: `buscar en los ${buscables} · ⏎ abre el primero · ⎋ borra`, cuenta: { id: 'proyectos-cuenta' }, claseBarra: 'proy-herr',
        herramientas: '<span class="modos">'
            + (cerrados ? `<button id="ver-cerrados" title="mostrar u ocultar los cerrados">cerrados ${cerrados}</button>` : '')
            + `<button id="ver-extendida" title="la tabla extendida: a lo ancho, sin el detalle, con todas las columnas y en palabras (otra vez, o elegir un proyecto: volver)"><span class="i">${I.ancho}</span></button>`
            + '</span>' }),
    // el área que declara cada documento: aparece cuando hay al menos dos distintas; en el orden del perfil
    // (`areas`), y las que no nombra, después, por cuántas tienen
    filtro('area', 'todas las áreas', contar(lista.map(areaDe)), [...areas, 'sin área']),
    '<div id="proyectos">'];
    // los nombres de las columnas, alineados con las filas: el clic ordena por esa (la que ordena, en azul); otro clic,
    // o «estado», vuelve al orden de siempre. Lo mismo que el orden de «tareas» (componentes/orden.ts)
    // la etapa, como en sus filas: un ícono, y en la tabla extendida su nombre
    const col = (k: string, clase: string) => {
        const [, nombre, como] = COLUMNAS_P.find(c => c[0] === k)!;
        const ayuda = `${k === 'fase' ? 'etapa: la fase de su plazo. Clic: ' : ''}ordenar por ${como}${k === 'estado' ? '' : ' (otra vez: por estado)'}`;
        const texto = k === 'fase' ? `<span class="i solo-c">${I.etapa}</span><span class="solo-x">${nombre}</span>` : nombre;
        return `<span class="${clase}" data-orden-p="${k}" title="${esc(ayuda)}">${texto}</span>`;
    };
    const solo = (clase: string, nombre: string, ayuda: string) => `<span class="${clase} solo-x" title="${esc(ayuda)}">${nombre}</span>`;
    h.push(`<div class="fila proy-cab proy-cols"><span class="at"></span>${col('nombre', 'que')}${col('estado', 'estado-p')}${col('fase', 'etapa')}`
        + solo('inicio-p', 'inicio', 'cuándo partió (o parte)')
        + `${col('plazo', 'cuando-p')}` + solo('area-p', 'área', 'el área que declara su documento') + solo('aviso-p', 'aviso', 'lo que no cuadra, según su fuente')
        + `${col('pend', 'tareas-p')}<span class="menu-col"></span></div>`);
    // las filas, sueltas en una sola lista: cada sección con su cabecera adelante, todas con su lugar de siempre
    let orden = 0;
    for (const [sec, titulo] of SECCIONES) {
        const xs = ordenarSeccion(sec, por.get(sec)!, p => p.plazo, p => p.nombre);
        if (!xs.length) continue;
        h.push(`<div class="fila proy-sec-cab" data-sec="${sec}" data-orden="${orden++}"><span class="at"></span>`
            + `<span class="que">${titulo} <span class="proy-sec-n">${xs.length}</span></span></div>`);
        for (const p of xs) h.push(filaProyecto(p, sec, sel, cuentas?.get(p.ruta), hoy, orden++));
    }
    h.push('<div id="proyectos-vacio" class="fila dim" hidden></div></div>');
    return h;
}

/** Cuántos negocios vienen: los de los arquetipos que el modo llama negocios (`negocios`), en negociación y con
 *  propuesta, según el estado que dice su documento. "" si el modo no cuenta negocios. */
export function textoNegocios(todas: cli.JsonProyecto[]): string {
    const tipos = modos.tipos('negocios');
    if (!tipos.length) return '';
    const negocios = todas.filter(p => tipos.includes(p.arquetipo.toLowerCase()));
    const negociacion = negocios.filter(p => rangoEstado(p.estado ?? '') === 1).length;
    const propuesta = negocios.filter(p => rangoEstado(p.estado ?? '') === 2).length;
    const n = negociacion + propuesta;
    return n ? `se vienen ${n} negocio${n === 1 ? '' : 's'}: ${negociacion} en negociación, ${propuesta} con propuesta` : 'ningún negocio en propuesta ni en negociación';
}

/** Cuántas iniciativas hay y en cuántos programas, para la barra: «6 iniciativas en 2 programas». */
export function textoIniciativas(inis: readonly cli.JsonProyecto[], campo: string): string {
    const n = inis.length;
    const ps = campo ? programas(agrupar(inis, campo)) : 0;
    return `${n} iniciativa${n === 1 ? '' : 's'}${ps ? ` en ${ps} programa${ps === 1 ? '' : 's'}` : ''}`;
}

/** Una fila de pendiente en el detalle de un proyecto y en «ahora»: la misma de «tareas» (fila-tarea.ts), sin la
 *  columna del proyecto. */
export function filaPendiente(t: Pendiente): string {
    return filaTarea(t);
}

/** Una sección del README ya dibujada para el detalle: su clave (con ella, la página recuerda si estaba abierta al
 *  repintar), su título, su texto propio en html, lo que se lee de ella plegada, si no tiene contenido propio, qué es
 *  para el resumen (readme.claseDe) y las suyas. */
export interface ParteVista { k: string; titulo: string; html: string; vistazo: string; vacia: boolean; clase: readme.Clase; subs: ParteVista[]; resumen?: string }

/** El README dibujado: su entrada (el título y lo que va antes de la primera sección, el resumen del documento), sus
 *  secciones y los datos de su ficha (campo y valor, en html). `falla`: no se pudo leer. */
export interface ReadmeVisto { entrada: ParteVista | null; partes: ParteVista[]; datos: [string, string][]; falla?: string }

export interface DetalleProyecto {
    p: cli.JsonProyecto;
    /** es una iniciativa (de los arquetipos que el modo llama así): cómo va lo dice su frontmatter, con este campo de
     *  programa y el vocabulario de sus estados (iniciativas.ts) */
    iniciativa?: { campo: string; voc?: Vocabulario };
    pendientes: Pendiente[] | null;   // null: todavía leyendo
    aviso: string;
    readme: ReadmeVisto | null | '';   // null: todavía leyendo; "": no tiene
}

/** Un README, partido (readme.ts) y dibujado con el markdown de la página: `bloque` para un texto, `linea` para el
 *  valor de un dato. */
export function verReadme(texto: string, bloque: (md: string) => string, linea: (md: string) => string): ReadmeVisto {
    const r = readme.partir(texto);
    const vista = (p: readme.Parte, k: string): ParteVista => ({
        k, titulo: p.titulo, html: p.md ? bloque(p.md) : '', vistazo: readme.vistazo(p), vacia: readme.vacia(p),
        clase: readme.claseDe(p), subs: p.subs.map((s, i) => vista(s, `${k}.${i}`)),
        // en el resumen, lo que espera de otros va sin la cita del comienzo si trae algo más: en una plantilla, la
        // ayuda de qué va ahí
        resumen: readme.claseDe(p) === 'abierto' && p.md ? bloque(readme.sinAyuda(p.md)) : undefined,
    });
    const entrada: readme.Parte = { titulo: r.titulo || 'entrada', md: r.intro, subs: [] };
    const ficha = r.partes.find(p => readme.claseDe(p) === 'datos');
    return {
        // la entrada no está nunca vacía: si es solo una cita, la cita es el resumen del documento
        entrada: r.intro ? { ...vista(entrada, 'e'), vacia: false } : null,
        partes: r.partes.map((p, i) => vista(p, String(i))),
        // el estado ya está arriba, en palabras de la página
        datos: ficha ? readme.datos(ficha, ['estado']).map(([k, v]): [string, string] => [esc(k), linea(v)]) : [],
    };
}

/** Cómo va: el círculo de su fase (va antes del nombre, como en la lista) y una línea bajo el nombre con su estado
 *  efectivo (y si es a mano, desde cuándo) y su plazo: la etapa, de cuándo a cuándo, lo que no cuadra y el enlace a
 *  su fuente. */
function htmlComoVa(p: cli.JsonProyecto, iniciativa?: { campo: string; voc?: Vocabulario }): [string, string] {
    if (iniciativa) {
        const c = comoVaIniciativa(p, iniciativa.campo, iniciativa.voc);
        return [`<span class="at">${c.peso}</span>`, `<div class="det-va">${c.partes.join(' · ')}</div>`];
    }
    const sec = seccionDe(p);
    const mano = /a mano[^·]*/.exec(p.estado_completo ?? '')?.[0]?.trim() ?? '';
    const pl = p.plazo;
    const senal = typeof pl?.avance === 'number' ? S.fase(pl.avance, pl.aviso ?? '') : null;
    const marca = senal?.circulo ? `<span class="senal${senal.tono ? ` tono-${senal.tono}` : ''}">${circulo(senal.circulo)}</span>` : '';
    const dice = [`<b>${esc(NOMBRE[sec])}</b>${mano ? ` <span class="dim">${esc(mano)}</span>` : ''}`];
    if (!pl) dice.push(`<span class="dim">sin plazo${p.estado_completo && !efectivo(p.estado ?? '') ? `; su documento dice «${esc(p.estado_completo)}»` : ''}</span>`);
    else {
        if (pl.etapa) dice.push(esc(pl.etapa));
        dice.push(pl.fin > pl.inicio ? `${esc(diaCorto(pl.inicio))} → ${esc(diaCorto(pl.fin))}` : `desde ${esc(diaCorto(pl.inicio))}`);
        if (pl.aviso) dice.push(`<span class="tono-atencion">${esc(pl.aviso)}</span>`);
        if (pl.enlace) dice.push(`<a data-accion="proy-enlace" data-valor="${esc(pl.enlace)}" title="${esc(pl.enlace)}">${esc(pl.fuente || 'su fuente')}</a>`);
    }
    return [`<span class="at">${marca}</span>`, `<div class="det-va">${dice.join(' · ')}</div>`];
}

/** Las pestañas del detalle. Cuál se ve lo recuerda la página (vista.ts, `pd`): al elegir otro proyecto, la misma. */
const PESTANAS = ['resumen', 'pendientes', 'documento'] as const;

/** Un texto del resumen, recortado a unas líneas; «más» lo muestra entero (vista.ts lo muestra solo si no cabe). */
const recorte = (k: string, html: string, base: string): string =>
    `<div class="det-md recorte" data-k="${esc(k)}" data-base="${esc(base)}">${html}</div><a class="mas" hidden>más</a>`;

/** Una sección con las suyas, seguida (en el resumen no se pliega). */
const entera = (x: ParteVista): string => (x.resumen ?? x.html) + x.subs.map(s => `<h5>${esc(s.titulo)}</h5>${entera(s)}`).join('');

/** El resumen: lo que pide atención antes que lo que explica. Cómo va según su documento, lo próximo, lo que espera
 *  de otros, qué es, sus datos y dónde está. Lo que no tiene, no se muestra. */
function htmlResumen(d: DetalleProyecto): string {
    const { p } = d;
    const r = d.readme || undefined;
    const h: string[] = ['<div class="det-pane" data-pane="resumen">'];
    const deClase = (c: readme.Clase) => (r?.partes ?? []).filter(x => x.clase === c && !x.vacia).slice(0, 2);
    for (const x of deClase('estado')) h.push(`<h4>${esc(x.titulo)}</h4>`, recorte(`r${x.k}`, entera(x), p.ruta));
    const pend = d.pendientes;
    h.push(`<h4>próximos${pend && pend.length > 3 ? ` <span class="n">3 de ${pend.length}</span>` : ''}</h4>`);
    if (pend === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!pend.length) h.push('<div class="vacio">nada pendiente</div>');
    else {
        h.push(...pend.slice(0, 3).map(filaPendiente));
        if (pend.length > 3) h.push(`<a class="det-ver" data-pest="pendientes">los ${pend.length} pendientes</a>`);
    }
    for (const x of deClase('abierto')) h.push(`<h4>${esc(x.titulo)}</h4>`, recorte(`r${x.k}`, entera(x), p.ruta));
    if (d.readme === null) h.push('<h4>qué es</h4><div class="vacio">leyendo…</div>');
    else if (r?.falla) h.push(`<div class="vacio falla">${esc(r.falla)}</div>`);
    else if (r?.entrada) h.push('<h4>qué es</h4>', recorte('re', r.entrada.html, p.ruta));
    if (r?.datos.length) {
        const dl = (xs: [string, string][]) => `<dl class="det-datos" data-base="${esc(p.ruta)}">${xs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
        h.push('<h4>datos</h4>', dl(r.datos.slice(0, 6)));
        if (r.datos.length > 6) h.push(`<details class="det-mas" data-k="datos"><summary>${r.datos.length - 6} más</summary>${dl(r.datos.slice(6))}</details>`);
    }
    h.push(`<div class="det-pie">${[p.area, p.arquetipo].filter(Boolean).map(x => esc(x ?? '')).join(' · ')} · `
        + `<a data-accion="abrir-ruta" data-valor="${esc(`${p.ruta}/README.md`)}" title="abrir su README">${esc(p.ruta)}</a>`
        + `${p.modificado ? ` · tocado ${esc(haceCorto(p.modificado))}` : ''}</div></div>`);
    return h.join('');
}

/** Los pendientes: todos, y pedirle a un agente que revise cuáles ya se hicieron. */
function htmlPendientes(d: DetalleProyecto): string {
    const h: string[] = ['<div class="det-pane" data-pane="pendientes">'];
    if (d.aviso) h.push(`<div class="vacio falla">${esc(d.aviso)}</div>`);
    if (d.pendientes === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!d.pendientes.length) h.push('<div class="vacio">nada pendiente</div>');
    else h.push(...d.pendientes.map(filaPendiente));
    h.push(`<div class="det-pie"><a data-accion="proy-consolidar" data-valor="${esc(d.p.ruta)}" title="/consolidar">consolidar pendientes</a>:`
        + ' un agente revisa cada uno abierto del README, busca si ya se hizo y marca lo hecho con su prueba</div></div>');
    return h.join('');
}

/** Una sección plegada: su título y lo que se lee de ella; el clic la abre, con las suyas también plegadas. */
function htmlParte(x: ParteVista, base: string): string {
    return `<details class="det-sec${x.vacia ? ' vacia' : ''}" data-k="d${esc(x.k)}"><summary>`
        + `<span class="i plegado">${I.plegado}</span><span class="i abierto">${I.abierto}</span>`
        + `<span class="tit">${esc(x.titulo)}</span><span class="vistazo">${esc(x.vacia ? 'sin contenido' : x.vistazo)}</span></summary>`
        + `<div class="det-sec-cuerpo">${x.html ? `<div class="det-md" data-base="${esc(base)}">${x.html}</div>` : ''}`
        + `${x.subs.map(s => htmlParte(s, base)).join('')}</div></details>`;
}

/** El documento, por secciones plegadas en su orden; las que no tienen contenido propio (la plantilla sin llenar),
 *  al final y apagadas. */
function htmlDocumento(d: DetalleProyecto): string {
    const h: string[] = ['<div class="det-pane" data-pane="documento">'];
    const r = d.readme, base = d.p.ruta;
    if (r === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!r) h.push('<div class="vacio">sin README</div>');
    else if (r.falla) h.push(`<div class="vacio falla">${esc(r.falla)}</div>`);
    else if (!r.partes.length) h.push(r.entrada ? `<div class="det-md" data-base="${esc(base)}">${r.entrada.html}</div>` : '<div class="vacio">vacío</div>');
    else {
        if (r.entrada) h.push(htmlParte(r.entrada, base));
        h.push(...r.partes.filter(x => !x.vacia).map(x => htmlParte(x, base)), ...r.partes.filter(x => x.vacia).map(x => htmlParte(x, base)));
    }
    h.push(`<div class="det-pie"><a data-accion="abrir-ruta" data-valor="${esc(`${base}/README.md`)}">abrir el README</a></div></div>`);
    return h.join('');
}

/** La columna derecha: arriba, quedándose, el nombre, cómo va, ir a su hilo, sus acciones y las pestañas; abajo, la
 *  pestaña que se ve: el resumen, los pendientes o el documento. */
export function htmlDetalleProyecto(d: DetalleProyecto | undefined, que = 'un proyecto'): string {
    if (!d) return `<div class="vacio">elige ${que} a la izquierda</div>`;
    const { p } = d;
    const n = d.pendientes?.length ?? 0;
    const cliente = p.cliente && !p.interno && p.nombre.startsWith(p.cliente) ? p.cliente : '';
    const nombre = cliente ? `<span class="cliente">${esc(cliente)}</span>${esc(p.nombre.slice(cliente.length))}` : esc(sinCasa(p));
    const ir = p.vivo ? 'ir a su hilo' : p.hilo ? 'retomar su hilo' : 'abrir con el agente';
    const ayudaIr = p.hilo ? `su hilo: «${p.hilo}»${p.vivo ? '' : ' (dormido)'}` : 'un hilo con el agente cargando el proyecto';
    const [marca, va] = htmlComoVa(p, d.iniciativa);
    return `<div class="det-cab" data-mismo="${esc(p.ruta)}"><div class="det-titulo">${marca}<h3>${nombre}</h3>`
        + `<a class="det-ir" data-accion="proyecto" data-valor="${esc(p.ruta)}" title="${esc(ayudaIr)}">${ir}</a>`
        + `<span class="menu-fila" data-accion="proy-menu" data-valor="${esc(p.ruta)}" title="acciones de este proyecto">${I.menu}</span></div>`
        + va
        + `<div class="subpest det-pest">${PESTANAS.map(k => `<a data-pest="${k}">${k}${k === 'pendientes' && n ? ` <span class="n">${n}</span>` : ''}</a>`).join('')}</div></div>`
        + htmlResumen(d) + htmlPendientes(d) + htmlDocumento(d);
}

/** La pestaña de proyectos: la lista, el elegido y su detalle, y las viñetas pendientes de los documentos. Las
 *  otras pantallas le preguntan de qué proyecto es algo y qué tiene pendiente («ahora», la columna de «tareas»). */
export class PantallaProyectos implements Pantalla {
    readonly pantallas = ['proyectos'] as const;
    /** la lista no cambia con el reloj: repintarla cada minuto solo movería el scroll */
    readonly conReloj = [] as const;
    /** todas las unidades del perfil (`telar proyectos`), y el aviso si no llegaron */
    lista?: cli.JsonProyecto[];
    /** el orden de las áreas (`areas` del perfil) */
    private areas: string[] = [];
    /** el vocabulario de estados de las iniciativas (`[iniciativas]`): con él, su estado se cambia desde la lista */
    vocabulario: Vocabulario = SIN_VOCABULARIO;
    private aviso = '';
    /** las fuentes de fechas que no contestaron: sin ellas, esos proyectos van sin plazo */
    private fallas: string[] = [];
    /** el proyecto elegido en la lista, y lo que se muestra de él a la derecha */
    private sel = '';
    private det?: DetalleProyecto;
    /** las viñetas pendientes de todos los documentos: se leen una vez por entrada a la pantalla */
    private pendRepo?: cli.JsonFila[];
    private pendRepoAviso = '';
    /** de cuándo son (dia.ts, `generacionDeAhora`): una viñeta tachada después ya no se cuenta mientras se releen */
    private pendRepoDesde = 0;
    /** las personas que ofrece el proveedor de tareas como responsables (ver `personasConocidas`) */
    private personas?: string[];
    /** solo las iniciativas: un clic en su cabecera (o venir de todo); la barra vuelve a todo */
    private solo = false;

    readonly acciones: Record<string, Accion> = {
        // la pestaña: los proyectos, con las iniciativas debajo (las solas son de su cabecera y de todo)
        'proyectos': () => { this.solo = false; return this.abrir(); },
        'proyecto': v => v && this.abrirProyecto(v),
        'proy-sel': v => v && this.ver(v),
        'proy-ir': v => { if (v) { this.sel = v; this.solo = this.solo && this.esIniciativa(v); return this.abrir(); } },
        // la sección de las iniciativas, sola (o de vuelta con los proyectos); con valor, ir a ella desde otra pantalla
        'proy-iniciativas': v => { this.solo = v === 'solas' || (!v && !this.solo); return this.t.pantalla === 'proyectos' && v !== 'solas' ? this.pintar() : this.abrir(); },
        'proy-menu': (v, m) => v && entidades.menuDe(`proyecto:${v}`, m.donde),
        // el estado de una iniciativa: un menú con el vocabulario, junto a donde se hizo clic
        'ini-estado': (v, m) => v && this.cambiarEstado(v, m.donde),
        'proy-consolidar': v => v && this.consolidar(v),
        'proy-enlace': (v, m) => v && this.enlaceReadme(v, String(m.datos ?? '')),
        'menu-vineta': (v, m) => v && this.menuVineta(v, m.donde),
    };

    constructor(private readonly t: Tablero) {
        entidades.registrar('proyecto', ruta => this.accionesDe(ruta));
        // el modo dice qué son proyectos y negocios: al cambiarlo, la lista se rehace
        modos.alCambiar(() => { if (this.t.pantalla === 'proyectos' && this.lista) this.pintar(); });
        mundo.alCambiar(() => { if (this.t.pantalla === 'proyectos' && this.lista) this.pintar(); });
    }

    /** El orden de las áreas (`areas` del perfil): el del filtro de área. */
    areasDelPerfil(): string[] { return this.areas; }

    /** La lista, si todavía no se leyó: true si se leyó ahora (quien la pidió repinta). */
    async asegurar(): Promise<boolean> {
        if (this.lista) return false;
        const r = await cli.proyectos();
        if (r.datos) { this.lista = r.datos.proyectos; this.areas = r.datos.areas ?? []; this.vocabulario = vocabularioDe(r.datos.iniciativas); }
        return !!r.datos;
    }

    /** Las viñetas pendientes de los documentos, si todavía no se leyeron. */
    async asegurarPendientes(): Promise<void> {
        if (this.pendRepo) return;
        const desde = generacionDeAhora();
        const r = await cli.pendientesRepo();
        if (r.datos) { this.pendRepo = r.datos.pendientes; this.pendRepoDesde = desde; }
    }

    /** La pantalla de proyectos. La lista se pide cada vez que se entra: es barata (medio
     *  segundo con 179 unidades) y así un proyecto recién creado aparece sin recargar. */
    async abrir(): Promise<void> {
        this.t.ir('proyectos');
        this.aviso = '';
        this.pendRepo = undefined;
        if (!this.lista) this.pintar('leyendo los proyectos…');
        // los pendientes de los documentos se piden en paralelo: la lista no los espera
        const desde = generacionDeAhora();
        const repo = cli.pendientesRepo().then(r => {
            this.pendRepo = r.datos?.pendientes ?? [];
            this.pendRepoDesde = desde;
            this.pendRepoAviso = r.datos ? '' : (r.error ?? 'telar pendientes no contestó');
            if (this.t.pantalla !== 'proyectos') return;
            // la lista ya está pintada: solo se le dan las cuentas, para filtrar «con pendientes»
            const cuentas = this.cuentasPendientes();
            if (cuentas) this.t.panel?.cuentasProyectos(Object.fromEntries(cuentas));
            if (this.sel) void this.ver(this.sel, false);
        });
        const r = await cli.proyectos();
        if (r.datos) {
            this.lista = r.datos.proyectos; this.areas = r.datos.areas ?? []; this.fallas = r.datos.fallas ?? [];
            this.vocabulario = vocabularioDe(r.datos.iniciativas);
        }
        else this.aviso = r.error ?? 'telar proyectos no contestó';
        if (this.sel && !this.lista?.some(p => p.ruta === this.sel)) { this.sel = ''; this.det = undefined; }
        if (this.t.pantalla === 'proyectos') this.pintar();
        if (this.sel) void this.ver(this.sel);
        await repo;
    }

    /** Los pendientes de un proyecto: las viñetas de su documento y las tareas de un proveedor que
     *  dicen ser de esa carpeta (o de algo adentro). null mientras se leen los del documento. */
    pendientesDe(ruta: string): ReturnType<typeof pendientes> | null {
        const filas = this.filasPorProyecto()?.get(ruta);
        if (!filas) return this.pendRepo ? [] : null;
        return pendientes({ ...(this.t.dia() ?? { fecha: '' }), pendientes: filas } as Dia);
    }

    /** Las filas pendientes de cada proyecto: las viñetas de su documento, y cada tarea de un
     *  proveedor en el proyecto más hondo que contiene la carpeta que dice ser suya. */
    private filasPorProyecto(): Map<string, cli.JsonFila[]> | null {
        if (!this.pendRepo) return null;
        const rutas = (this.lista ?? []).map(p => p.ruta);
        const m = new Map<string, cli.JsonFila[]>();
        const sumar = (r: string, f: cli.JsonFila) => { if (r) m.set(r, [...(m.get(r) ?? []), f]); };
        const repo = conLoSalido({ fecha: '', pendientes: this.pendRepo, generacion: this.pendRepoDesde } as Dia).pendientes;
        for (const f of repo) if (!f.proveedor && !f.hecho) sumar(f.ruta, f);
        for (const f of this.t.dia()?.pendientes ?? []) {
            if (f.proveedor && f.clase !== 'evento' && !f.hecho && !f.pestana && f.proyecto) sumar(unidadDe(f.proyecto, rutas), f);
        }
        return m;
    }

    private cuentasPendientes(): Map<string, number> | undefined {
        const m = this.filasPorProyecto();
        return m ? new Map([...m].map(([r, fs]) => [r, fs.length])) : undefined;
    }

    /** Elegir un proyecto de la lista: su detalle a la derecha, sin repintar la lista. El README se
     *  dibuja con el Markdown de la página (web/ui.ts); `releer` vuelve a leerlo (al cambiar de proyecto). */
    private async ver(ruta: string, releer = true): Promise<void> {
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!p || !this.t.panel) return;
        this.sel = ruta;
        const previo = this.det?.p.ruta === ruta ? this.det.readme : null;
        this.det = { p, pendientes: this.pendientesDe(ruta), aviso: this.pendRepoAviso, readme: releer ? null : previo,
            ...this.esIniciativa(ruta) ? { iniciativa: { campo: modos.campoIniciativas(), voc: this.vocabulario } } : {} };
        this.pintarDetalle();
        if (!releer && previo !== null) return;
        const readme = await this.readmeHtml(ruta);
        if (this.sel !== ruta || !this.det) return;
        this.det.readme = readme;
        this.pintarDetalle();
    }

    private pintarDetalle(): void {
        this.t.parcial('proy-det', htmlDetalleProyecto(this.det));
    }

    /** El README de una unidad, partido por secciones y dibujado (verReadme). "" si no tiene. */
    private async readmeHtml(ruta: string): Promise<ReadmeVisto | ''> {
        if (!modelo.raiz || ruta.includes('..')) return '';
        let crudo: string | undefined;
        for (const n of ['README.md', 'readme.md']) { crudo = await disco().leer(rutas.unir(modelo.raiz, ruta, n)); if (crudo !== undefined) break; }
        if (crudo === undefined) return '';
        try {
            return verReadme(crudo.slice(0, 300_000), ui.markdown, ui.markdownLinea);
        } catch (e) {
            return { entrada: null, partes: [], datos: [], falla: `no pude leer el README: ${String(e)}` };
        }
    }

    /** Las personas para elegir como responsable: las que ofrece el proveedor de tareas (se pide la
     *  ficha de una tarea cualquiera, una vez) y todos los que ya son responsables de algo. */
    private async personasConocidas(): Promise<string[]> {
        if (!this.personas) {
            const unaTarea = this.t.dia()?.pendientes.find(f => f.ficha && f.proveedor);
            const ficha = unaTarea ? await cli.tarea(unaTarea.id || unaTarea.ref, unaTarea.proveedor) : undefined;
            this.personas = ficha?.datos?.acciones?.find(a => a.rol === 'dueno')?.opciones ?? [];
        }
        const vistos = [...(this.t.dia()?.pendientes ?? []), ...(this.pendRepo ?? [])].map(f => f.dueno ?? '').filter(Boolean);
        return [...new Set([...this.personas, ...vistos])].sort((a, b) => a.localeCompare(b));
    }

    /** El ⋯ de una casilla de un documento (un README): llevarla a su hilo, abrirla donde está,
     *  marcarla hecha o decir quién la hace. Lo que cambia el documento cambia esa línea y nada más. */
    private async menuVineta(valor: string, donde?: { x: number; y: number }): Promise<void> {
        const [ref, texto, hilo, dueno] = JSON.parse(valor) as string[];
        type Item = Opcion & { hacer: () => Promise<unknown> };
        const despues = async (r: { datos?: cli.JsonVineta; error?: string }) => {
            if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no pude cambiarla'}`); return; }
            void ui.estado(`telar: ${r.datos.relativa}:${r.datos.linea} · ${r.datos.hecho} (sin commitear)`, 6000);
            olvidarDia();
            this.pendRepo = undefined;
            await this.t.actualizar(true);
            if (this.t.pantalla === 'revisar') this.t.render();
            else if (this.t.pantalla === 'proyectos') await this.abrir();
        };
        const items: Item[] = [
            // a su hilo, a uno nuevo, a otro o a un agente, con una skill o lo que se le pida (web/instruccion.ts)
            { label: 'instrucción…', icono: I.instruccion, color: C.agente, description: hilo ? `a «${hilo}», a uno nuevo o a otro` : 'a su hilo, a uno nuevo o a otro',
              hacer: async () => {
                  const fila = [...(this.t.dia()?.pendientes ?? []), ...(this.pendRepo ?? [])].find(f => f.ref === ref);
                  const { abrir } = await import('../../web/instruccion');
                  await abrir({ direccion: fila?.direccion ?? '', fila: fila ?? { ref, texto, hilo }, titulo: texto });
              } },
            { label: 'Abrir el README en esa línea', icono: I.documento, color: C.ir, hacer: async () => {
                const r = await cli.vineta(ref, texto, ['--linea']);
                if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no la encontré'}`); return; }
                await ui.abrirArchivo(r.datos.archivo);
            } },
            { label: 'Marcar hecha', icono: I.hecha, color: C.hecho, description: '[ ] → [x] en el README', hacer: async () => {
                const si = await ui.aviso(`¿Marcar hecha? ${texto.slice(0, 90)}`, 'Marcar hecha');
                if (si === 'Marcar hecha') await despues(await cli.vineta(ref, texto, ['--hecho']));
            } },
            { label: 'Responsable…', icono: I.persona, color: C.cambiar, description: dueno ? `ahora: ${dueno}` : 'ahora: sin responsable', hacer: async () => {
                const quien = await elegirDueno(texto.slice(0, 80), dueno, await this.personasConocidas(), yo.persona, true);
                if (quien) await despues(await cli.vineta(ref, texto, ['--responsable', quien]));
            } },
        ];
        const e = await ui.menu(items, donde, texto.slice(0, 100));
        if (e) await e.hacer();
    }

    /** Cambiar el estado de una iniciativa: un menú con el vocabulario (el de ahora, marcado), y lo elegido se escribe en
     *  su ficha (`estado:` y `estado_desde:`, sin commitear). Una que manda otra fuente no lo ofrece: lo dice. Lo escrito
     *  se pone en la lista que ya está, sin volver a leerla: la fila y el detalle se repintan al tiro. */
    async cambiarEstado(ruta: string, donde?: { x: number; y: number }): Promise<void> {
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!p) return;
        const voc = this.vocabulario;
        const e = estadoDe(p, voc);
        const nombre = sinCasa(p);
        if (e.fuente) { void ui.estado(`telar: el estado de «${nombre}» lo manda ${e.fuente}: se cambia allá`, 6000); return; }
        if (!voc.estados.length) { void ui.estado('telar: no hay un vocabulario de estados ([iniciativas] estados, en la configuración)', 6000); return; }
        type Item = Opcion & { estado: string };
        const actual = e.fuera ? '' : e.valor;
        const items: Item[] = voc.estados.map(x => ({
            label: x, estado: x, senal: S.enLinea(S.estadoIniciativa(claseDe(x, voc))),
            ...x === actual ? { description: e.escrito && e.escrito !== x ? `ahora (su ficha dice «${e.escrito}»)` : 'ahora' } : {},
        }));
        const titulo = `estado de ${nombre}${e.fuera ? ` · dice «${e.escrito}», fuera del vocabulario` : ''}`;
        const elegido = await ui.menu(items, donde, titulo);
        if (!elegido || elegido.estado === actual) return;
        const r = await cli.estadoIniciativa(ruta, elegido.estado);
        if (!r.datos) { void ui.falla(`telar: ${r.error ?? 'no pude cambiar su estado'}`); return; }
        const d = r.datos;
        void ui.estado(d.cambio ? `telar: ${d.archivo} · estado: ${d.antes || '—'} → ${d.estado} (sin commitear)` : `telar: ya estaba en «${d.estado}»`, 6000);
        if (d.cambio) p.frontmatter = { ...p.frontmatter, estado: d.estado, estado_desde: d.estado_desde };
        if (this.t.pantalla !== 'proyectos') return;
        this.pintar();
        if (this.sel === ruta) void this.ver(ruta, false);
    }

    /** De qué proyecto es un pendiente: la carpeta que dice la tarea, o la del documento de donde salió,
     *  llevada a la unidad más honda que la contiene. */
    deFila(f: cli.JsonFila): cli.JsonProyecto | undefined {
        const carpeta = f.proyecto || f.ruta;
        if (!carpeta || !this.lista) return undefined;
        const ruta = unidadDe(carpeta, this.lista.map(p => p.ruta));
        return this.lista.find(p => p.ruta === ruta);
    }

    /** Pedirle al agente general que consolide los pendientes del README de un proyecto (`/consolidar`):
     *  que marque hecho, con su prueba, lo que ya se hizo. Corre donde vive el agente (el servidor). */
    async consolidar(ruta: string): Promise<void> {
        const general = this.t.general();
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!general) { void ui.aviso('telar: no hay un agente general ([agentes] sin_proyecto) que lo haga'); return; }
        const n = this.pendientesDe(ruta)?.filter(t => !t.fila.proveedor).length;
        const si = await ui.info(
            `¿Consolidar los pendientes de «${p?.nombre ?? ruta}»?`,
            { detalle: `${general.nombre} revisa ${n ?? 'cada'} pendiente${n === 1 ? '' : 's'} abierto${n === 1 ? '' : 's'} del README, busca si ya se hizo y marca lo hecho con su prueba. Lo dudoso te lo pregunta.` },
            'Consolidar');
        if (si !== 'Consolidar') return;
        const r = await ui.progreso({ titulo: `telar: encargándoselo a ${general.nombre}…` },
            () => cli.encargar(general.clave, `/consolidar ${ruta}`));
        if (!r.datos) { void ui.falla(`telar: no llegó a ${general.nombre}: ${r.error ?? 'sin respuesta'}`); return; }
        void ui.estado(`telar: ${general.nombre} consolida ${p?.nombre ?? ruta} (${r.datos.estado ?? ''})`, 8000);
    }

    /** Lo que se puede hacer con un proyecto sin abrirlo: su menú (web/entidades.ts), desde su fila, el Gantt o donde
     *  se lo nombre. */
    private async accionesDe(ruta: string): Promise<{ titulo: string; acciones: entidades.AccionEntidad[] } | undefined> {
        const general = this.t.general();
        await this.asegurar();
        const p = this.lista?.find(x => x.ruta === ruta);
        if (!p) return undefined;
        const carpeta = modelo.raiz ? rutas.unir(modelo.raiz, ruta) : '';
        type Item = Opcion & { hacer: () => Promise<unknown> | unknown };
        const items: Item[] = [
            { label: p.vivo ? 'Ir a su hilo' : p.hilo ? 'Retomar su hilo' : 'Abrir con el agente', icono: I.agente, color: C.agente,
              description: p.hilo ? `«${p.hilo}»` : 'un hilo nuevo cargando el proyecto', hacer: () => this.abrirProyecto(ruta) },
        ];
        if (general) {
            items.push({ label: 'Consolidar sus pendientes', icono: I.consolidar, color: C.hecho, description: `${general.nombre} marca lo hecho con su prueba (/consolidar)`,
                         hacer: () => this.consolidar(ruta) });
            // escribirle a él sobre el proyecto es «instrucción…», arriba en el menú (con su contexto), eligiéndolo
        }
        if (carpeta) {
            items.push(
                { label: 'Abrir el README', icono: I.documento, color: C.ir, description: `${ruta}/README.md`, hacer: () => abrirEnlace(rutas.unir(carpeta, 'README.md')) },
                { label: 'Mostrar la carpeta en el explorador', icono: I.carpeta, color: C.ir, hacer: () => ui.mostrarCarpeta(carpeta) },
            );
        }
        items.push({ label: 'Copiar la ruta', icono: I.copiar, color: C.otro, description: ruta, hacer: async () => {
            await ui.copiar(ruta);
            void ui.estado(`telar: copiado ${ruta}`, 3000);
        } });
        if (p.hilo) {
            items.push({ label: 'Archivar su hilo', icono: I.archivar, color: C.quitar, description: `cierra «${p.hilo}» y lo guarda; ${I.retomar} lo retoma`, hacer: async () => {
                const si = await ui.aviso(`¿Archivar «${p.hilo}»? Se cierra su ventana; su conversación queda para retomarla.`, 'Archivar');
                if (si !== 'Archivar') return;
                const r = await cli.hilo('archivar', p.hilo, undefined, ['--cerrar']);
                if (!r.ok) void ui.falla(`telar: ${r.err.trim() || 'no pude archivarlo'}`);
                await this.abrir();
            } });
        }
        return { titulo: p.nombre, acciones: items };
    }

    /** Un enlace del README: una ruta relativa se abre como archivo; una dirección, en el navegador. */
    private async enlaceReadme(href: string, base: string): Promise<void> {
        if (/^[a-z][a-z0-9+.-]*:/i.test(href)) { await ui.abrirExterno(href); return; }
        if (!modelo.raiz || href.startsWith('#')) return;
        const destino = rutas.unir(modelo.raiz, base, decodeURIComponent(href.split('#')[0]));
        if (!destino.startsWith(modelo.raiz)) return;
        await abrirEnlace(destino);
    }

    /** Todas las filas van a la página de una vez; buscar y ordenar ocurre allá, sin ir y
     *  volver por cada letra. Ver `aplicarProyectos` en vista.ts. */
    pintar(cargando = ''): void {
        if (!this.t.panel) return;
        this.t.teclas.clear();
        const lista = this.proyectos();
        const inis = this.iniciativas();
        const campo = modos.campoIniciativas();
        if (!modos.tipos('iniciativas').length) this.solo = false;
        const h: string[] = [];
        const barra: EnBarra = this.solo
            ? { volver: { accion: 'proy-iniciativas', icono: I.atras, ayuda: 'volver a los proyectos' }, nombre: 'iniciativas',
                resumen: textoIniciativas(inis, campo) }
            : { resumen: this.lista ? textoNegocios(this.lista) : '' };
        if (this.aviso) h.push(`<div class="fila falla">${esc(this.aviso)}</div>`);
        if (this.fallas.length && !this.solo) h.push(`<div class="fila falla" title="${esc(this.fallas.join('\n'))}">sin plazos de: ${esc(this.fallas.map(f => f.split(':')[0]).join(', '))}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.t.pintar(h, barra); return; }
        const cuentas = this.cuentasPendientes();
        const izquierda = this.solo
            ? [barraBuscar({ id: 'buscar-p', atajo: '/', placeholder: 'iniciativas', ayuda: `buscar en las ${inis.length} · ⏎ abre la primera · ⎋ borra`,
                cuenta: { id: 'proyectos-cuenta' }, claseBarra: 'proy-herr' }),
                inis.length ? htmlIniciativas(inis, campo, { sel: this.sel, cuentas, solo: true, voc: this.vocabulario }) : '<div class="vacio">ninguna iniciativa en este mundo</div>']
            : [...htmlListaProyectos(lista, this.sel, cuentas, this.areas, lista.length + inis.length),
                htmlIniciativas(inis, campo, { sel: this.sel, cuentas, voc: this.vocabulario })];
        h.push(`<div class="proy-dos${this.solo ? ' ini-solas' : ''}"><div class="proy-lista">`, ...izquierda,
            `</div><div id="proy-det">${htmlDetalleProyecto(this.sel && (!this.solo || this.esIniciativa(this.sel)) ? this.det : undefined, this.solo ? 'una iniciativa' : undefined)}</div></div>`);
        this.t.pintar(h, barra);
    }

    /** Los proyectos que muestra la lista: los arquetipos que el modo llama proyectos (`proyectos`); si no dice,
     *  todas las unidades menos los servicios (no son proyectos; sí sirven para decir de qué es una tarea). Las
     *  iniciativas van aparte, en su sección, aunque `proyectos` también las nombre. Con un mundo puesto, los suyos y los
     *  sin clasificar (web/mundo.ts). */
    private proyectos(): cli.JsonProyecto[] {
        const tipos = modos.tipos('proyectos');
        const inis = modos.tipos('iniciativas');
        return (this.lista ?? []).filter(p => (tipos.length ? tipos.includes(p.arquetipo.toLowerCase()) : !esServicio(p))
            && !inis.includes(p.arquetipo.toLowerCase()) && mundo.seVe(p.mundo));
    }

    /** Las iniciativas: las unidades de los arquetipos que el modo llama así (`iniciativas`), del mundo puesto. */
    iniciativas(): cli.JsonProyecto[] {
        const tipos = modos.tipos('iniciativas');
        return tipos.length ? (this.lista ?? []).filter(p => tipos.includes(p.arquetipo.toLowerCase()) && mundo.seVe(p.mundo)) : [];
    }

    private esIniciativa(ruta: string): boolean {
        const p = this.lista?.find(x => x.ruta === ruta);
        return !!p && modos.tipos('iniciativas').includes(p.arquetipo.toLowerCase());
    }

    /** Un hilo con el agente cargando el proyecto, o el que ya había; y el teclado ahí. Lo
     *  que se le dice al agente lo decide `[agente] proyecto`, no la página. */
    async abrirProyecto(ruta: string): Promise<void> {
        const r = await cli.abrirProyecto(ruta);
        if (!r.datos) {
            void ui.aviso(`telar: ${r.error ?? 'no pude abrir el proyecto'}`);
            return;
        }
        await modelo.sondear();
        await ui.mostrarTerminal();
    }
}
