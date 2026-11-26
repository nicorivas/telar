// La pantalla de proyectos responde en qué estamos: qué proyectos hay en ejecución y cómo van, cuáles parten pronto, y
// cuántos negocios vienen detrás. A la izquierda, la lista de los proyectos (qué es un proyecto lo dice el modo:
// `proyectos`, los arquetipos del perfil), en secciones por su estado efectivo (en ejecución, por partir, en cierre,
// pausado, terminado, cerrado): el que se corrigió a mano en su documento, o el de su plazo, o el que dice su documento.
// Lo que está en su fase de cierre sale de «en ejecución». Cada fila es un ítem (componentes/item.ts) y cada sección una
// seccion(), las piezas de la barra de hilos: cómo va cada uno sale de su plazo (`telar fechas`, clase plazo: el de un
// gestor de proyectos o su cronograma): la fase, de a cuartos, en un círculo (componentes/senales.ts, `fase`), la etapa,
// el fin y lo que no cuadra. Arriba, el buscador con el orden (como en «tareas») y la fila de filtros (el área y los
// cerrados); el ↔ la muestra como tabla extendida, con sus columnas en palabras. A la derecha, el elegido: arriba cómo
// va, y abajo tres pestañas: el resumen (lo que pide atención antes que lo que explica, sacado de los títulos de su
// README: readme.ts), sus pendientes (las viñetas de su documento y las tareas que dicen ser suyas) y su README plegado
// por secciones, que se abren con un clic. Como el calendario, dos columnas; la derecha se cambia sola (un mensaje
// `parcial`), sin repintar la lista, que no debe perder ni el scroll ni lo buscado. Debajo de los proyectos, aparte, las
// iniciativas (el trabajo propio, sin cliente: las unidades que el modo llama `iniciativas`), por programa
// (iniciativas.ts); el → de su cabecera las deja solas. Arriba se dibuja; abajo, PantallaProyectos, el estado y las
// acciones.

import { barraBuscar } from '../../componentes/buscador';
import { filtros, type GrupoFiltro } from '../../componentes/filtros';
import { item, type Pieza } from '../../componentes/item';
import { orden, type OpcionOrden } from '../../componentes/orden';
import { seccion, separador } from '../../componentes/seccion';
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
import { esc, haceCorto, limpiarMd, normalizar } from '../../estilo';
import { barra, type VistaDePantalla } from '../../componentes/pantalla';
import { modelo } from '../../modelo';
import * as rutas from '../../rutas';
import { Dia, Pendiente, conLoSalido, esMia, generacionDeAhora, olvidarDia, pendientes, yo } from './dia';
import { htmlNegocios } from './negocios';
import { type Accion, type EnBarra, type Pantalla, type Tablero, abrirEnlace } from './pantalla';
import { elegirDueno } from './tareas';
import { filaTarea } from './fila-tarea';
import * as readme from './readme';
import { sinCasa, unidadDe } from './unidad';
import { pestanas } from '../../componentes/pestanas';
import { type Proximo, type Vocabulario, SIN_VOCABULARIO, cerradaIniciativa, claseDe, comoVaIniciativa, estadoDe, filtrosIniciativas, htmlIniciativas, programas,
    agrupar, vocabularioDe } from './iniciativas';
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

/** Lo que se lee de un proyecto para su fila (la de la lista y la de la tabla): su señal de fase, por qué está en su
 *  sección, su plazo, lo que no cuadra, el cliente y lo que ordena cada columna. */
function deFila(p: cli.JsonProyecto, sec: Seccion, hoy: string) {
    const pl = p.plazo;
    const aviso = pl?.aviso ?? '';
    const pq = porQue(p, sec, hoy);
    const cuando = cuandoDe(sec, pl, aManoDesde(p), hoy);
    // del aviso, lo que no dice ya el plazo («venció 22-oct» está en su fecha)
    const avisoX = aviso.split(' · ').filter(a => !/^venci/.test(a)).join(' · ');
    // el cliente adelante; lo demás del nombre, después. El de la casa (`internos`) no: va el nombre sin él
    const cliente = p.cliente && !p.interno && p.nombre.startsWith(p.cliente) ? p.cliente : '';
    const fecha = p.modificado ?? '';
    return {
        pl, aviso, avisoX, pq, cuando, cliente,
        resto: cliente ? p.nombre.slice(cliente.length).replace(/^\s+/, '') : sinCasa(p),
        ayuda: `${p.ruta}${fecha ? `\nmodificado ${fecha.slice(0, 16).replace('T', ' ')}` : ''}${p.hilo ? `\nhilo: ${p.hilo}${p.vivo ? '' : ' (dormido)'}` : ''}${aviso ? `\n${aviso}` : ''}`,
        // lo que ordena cada columna (vista.ts, `aplicarProyectos`): el nombre, la fase (de 0 a 1), la fecha que se ve,
        // cuántos pendientes; y lo que se busca
        datos: (pend: number | undefined, orden: number): Record<string, string> => ({
            valor: p.ruta, unidad: areaDe(p), pend: pend ? String(pend) : '',
            texto: normalizar(`${p.nombre} ${p.ruta} ${p.arquetipo} ${NOMBRE[sec]} ${pl?.etapa ?? ''} ${p.estado ?? ''} ${p.area ?? ''}`),
            sec, orden: String(orden), nombre: normalizar(p.nombre), fase: typeof pl?.avance === 'number' ? String(pl.avance) : '', plazo: cuando.iso,
        }),
    };
}

/** Una fila de la lista, un ítem (componentes/item.ts): en sus ranuras, la fase (el círculo: cómo va, y por qué está en
 *  su sección) y la etapa (un ícono, qué clase de trabajo; la palabra, al pasar); el cliente adelante y el nombre, que
 *  se lleva lo que sobra; al final, lo que no cuadra, el plazo y cuántos pendientes tiene, que ceden antes que el nombre
 *  cuando la lista se angosta (proyectos.css), y su ⋯, que aparece al pasar el mouse. El estado no va: lo dice la
 *  cabecera de su sección. */
function filaProyecto(p: cli.JsonProyecto, sec: Seccion, sel: string, pend: number | undefined, hoy: string, orden: number): string {
    const f = deFila(p, sec, hoy);
    const senal = senalFase(sec, f.pl, p.estado_completo);
    const fase: Pieza | null = senal ? { ...senal, ayuda: [NOMBRE[sec], senal.ayuda, f.pq.ayuda].filter(Boolean).join('\n') } : null;
    const etapa: Pieza | null = f.pl?.etapa ? { icono: iconoEtapa(f.pl.etapa), tono: 'tenue', ayuda: `etapa: ${f.pl.etapa}` } : null;
    const c = f.cuando;
    return item({
        clases: ['proy', ...sec === 'cerrado' ? ['cerrado'] : []],
        accion: 'proy-sel',
        datos: f.datos(pend, orden),
        activa: p.ruta === sel,
        apagada: sec === 'cerrado',
        ayuda: f.ayuda,
        inicio: [fase, etapa],
        prefijo: f.cliente ? [{ texto: f.cliente, ayuda: `cliente: ${f.cliente}` }] : [],
        // con cliente, lo demás del nombre va tenue: lo que distingue a uno de otro es el cliente
        ...f.cliente ? { tituloHtml: `<span class="tono-tenue">${esc(f.resto)}</span>` } : { titulo: f.resto },
        aviso: f.avisoX ? { icono: I.alerta, tono: 'atencion', ayuda: f.avisoX } : undefined,
        meta: { html: `<span class="cuando-p${c.vencido ? ' tono-atencion' : ''}" title="${esc(c.ayuda)}">${esc(c.texto)}</span>`
            + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${pend || ''}</span>` },
        menu: { accion: 'proy-menu', icono: I.menu, datos: { valor: p.ruta }, ayuda: 'acciones de este proyecto' },
    });
}

/** Una fila de la tabla extendida (el ↔ de las herramientas): a lo ancho, sin el detalle, con todas las columnas y en
 *  palabras: la fase, el nombre, el estado efectivo (tenue si nadie lo confirma), la etapa, cuándo partió, el plazo, el
 *  área, lo que no cuadra, cuántos pendientes y su ⋯. Las columnas, una grilla que comparten las filas (proyectos.css). */
function filaTabla(p: cli.JsonProyecto, sec: Seccion, sel: string, pend: number | undefined, hoy: string, orden: number): string {
    const f = deFila(p, sec, hoy);
    const senal = senalFase(sec, f.pl, p.estado_completo);
    const marca = senal?.circulo
        ? `<span class="senal${senal.tono ? ` tono-${senal.tono}` : ''}"${senal.ayuda ? ` title="${esc(senal.ayuda)}"` : ''}>${circulo(senal.circulo)}</span>` : '';
    const datos = Object.entries(f.datos(pend, orden)).map(([k, v]) => ` data-${k}="${esc(v)}"`).join('');
    const nombre = f.cliente ? `<span class="cliente">${esc(f.cliente)}</span> <span class="resto">${esc(f.resto)}</span>` : esc(f.resto);
    const c = f.cuando;
    return `<div class="fila clic proy${p.ruta === sel ? ' activa' : ''}${sec === 'cerrado' ? ' cerrado' : ''}" data-accion="proy-sel"${datos} title="${esc(f.ayuda)}">`
        + `<span class="at">${marca}</span><span class="que">${nombre}</span>`
        + `<span class="estado-p${f.pq.supuesto ? ' tenue' : ''}" title="${esc(f.pq.ayuda)}">${esc(NOMBRE[sec])}</span>`
        + `<span class="etapa">${esc(f.pl?.etapa ?? '')}</span>`
        + `<span class="inicio-p">${f.pl ? esc(diaCorto(f.pl.inicio)) : ''}</span>`
        + `<span class="cuando-p${c.vencido ? ' tono-atencion' : ''}" title="${esc(c.ayuda)}">${esc(c.texto)}</span>`
        + `<span class="area-p">${esc(p.area ?? '')}</span><span class="aviso-p tono-atencion">${esc(f.avisoX)}</span>`
        + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${pend || ''}</span>`
        + `<span class="menu-fila menu-col" data-accion="proy-menu" data-valor="${esc(p.ruta)}" title="acciones de este proyecto">${I.menu}</span></div>`;
}

/** La primera casilla abierta (`- [ ]` o `- [>]`) de un documento, fuera de los bloques de código, sin el markdown de
 *  sus marcas; "" si no tiene. */
export function primeraCasilla(md: string): string {
    let codigo = false;
    for (const l of md.split('\n')) {
        if (/^\s*(```|~~~)/.test(l)) { codigo = !codigo; continue; }
        if (codigo) continue;
        const m = /^\s*[-*+]\s+\[[ >]\]\s+(.+)$/.exec(l);
        if (m) return limpiarMd(m[1]).replace(/<!--.*?-->/g, '').trim().slice(0, 300);
    }
    return '';
}

/** Las subvistas de proyectos, las pestañas de su barra: los proyectos de clientes, los negocios por cerrar y las
 *  iniciativas propias. Su ícono y lo que dice su globo. */
export type Subvista = 'clientes' | 'comercial' | 'interno';
export const SUBVISTA: Record<Subvista, [string, string]> = {
    clientes: [I.tabla, 'los proyectos, por cómo van, con su plazo'],
    comercial: [I.etiqueta, 'los negocios por cerrar, por cómo van según su documento'],
    interno: [I.casa, 'las iniciativas: el trabajo propio, sin cliente, por grupo'],
};
const esSubvista = (v: string | undefined): v is Subvista => !!v && v in SUBVISTA;

/** Las columnas de la tabla extendida que se ordenan: la clave (el `data-` de cada fila que la ordena), su nombre y cómo
 *  ordena. Por estado es el orden de siempre: en secciones, y dentro de cada una, el suyo (`ordenar`). */
export const COLUMNAS_P: [string, string, string][] = [
    ['nombre', 'proyecto', 'nombre, alfabético'], ['estado', 'estado', 'estado efectivo, en secciones (el orden de siempre)'],
    ['fase', 'etapa', 'etapa, de la primera a la última'], ['plazo', 'plazo', 'la fecha que se ve: lo más antiguo arriba'],
    ['pend', 'tareas', 'pendientes: los que más tienen arriba'],
];

/** El orden de la lista (componentes/orden.ts), en la barra del buscador: las mismas columnas que la tabla, cada una un
 *  ícono. Otro clic en la que rige vuelve al orden de siempre, por estado y en secciones. */
const ORDENES_P: OpcionOrden[] = [
    { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre, alfabético' },
    { clave: 'fase', icono: I.etapa, ayuda: 'etapa, de la primera a la última' },
    { clave: 'plazo', icono: I.fecha, ayuda: 'la fecha que se ve: lo más antiguo arriba' },
    { clave: 'pend', icono: I.lista, ayuda: 'pendientes: los que más tienen arriba' },
];

/** Lo que dice la cabecera de cada sección al pasar el mouse. */
const AYUDA_SECCION: Record<Seccion, string> = {
    curso: 'en ejecución: su plazo va, o su documento lo dice', partir: 'por partir: su plazo empieza más adelante',
    cierre: 'en cierre: su plazo está en la fase de cierre', pausado: 'pausados', terminado: 'terminados: les falta cerrarse',
    cerrado: 'cerrados: se ven con el filtro «cerrados» o buscando',
};

/** Los filtros de la lista (componentes/filtros.ts), en su fila bajo el buscador: el área que declara cada documento
 *  (aparece con al menos dos), plegada como en «tareas» (se elige una vez y se deja): se ve lo que rige, «todas» si no
 *  rige ninguna, y en su menú «todas» primero y las áreas en el orden del perfil (`areas`), las que no nombra después,
 *  por cuántas tienen; y junto a ella, «cerrados», que los muestra. Qué rige y cuántas deja cada opción lo pone la
 *  página (vista.ts, `aplicarProyectos`). */
export function filtrosProyectos(lista: cli.JsonProyecto[], areas: string[], cerrados: number): string {
    const valores = contar(lista.map(areaDe));
    const orden = [...areas, 'sin área'];
    const lugar = (v: string) => { const i = orden.indexOf(v); return i < 0 ? orden.length : i; };
    const grupos: GrupoFiltro[] = [];
    if (valores.size >= 2) {
        grupos.push({ clave: 'area', nombre: 'área', activa: '', siempre: '', plegado: true, opciones: [
            { clave: '', nombre: 'todas', cuenta: lista.length, ayuda: 'todas las áreas' },
            ...[...valores].sort((a, b) => lugar(a[0]) - lugar(b[0]) || b[1] - a[1])
                .map(([v, n]) => ({ clave: v, nombre: v, cuenta: n, ayuda: v === 'sin área' ? 'los que no declaran área' : `los del área ${v}` })),
        ] });
    }
    if (cerrados) grupos.push({ clave: 'cerrados', nombre: 'cerrados', activa: '', opciones: [{ clave: 'si', nombre: 'cerrados', cuenta: cerrados, ayuda: 'mostrar los cerrados' }] });
    return filtros({ accion: 'proy-filtro', clase: 'proy-filtros', grupos });
}

/** La lista de la izquierda: las herramientas (buscar y el orden), los filtros y las filas, cada
 *  sección (seccion(): en ejecución, por partir…) con su cabecera. Buscar, filtrar, ordenar, plegar una sección y
 *  mostrar los cerrados ocurre en la página (`aplicarProyectos`, vista.ts); elegir una fila pide su detalle. `tabla`: la
 *  tabla extendida, con los nombres de sus columnas y sus filas a lo ancho. */
export function htmlListaProyectos(lista: cli.JsonProyecto[], sel: string, cuentas?: Map<string, number>, areas: string[] = [],
    buscables = lista.length, tabla = false): string[] {
    const hoy = hoyIso();
    const por = new Map<Seccion, cli.JsonProyecto[]>(SECCIONES.map(([k]) => [k, []]));
    for (const p of lista) por.get(seccionDe(p, hoy))!.push(p);
    const cerrados = por.get('cerrado')!.length;
    const h: string[] = [barraBuscar({ id: 'buscar-p', atajo: '/', placeholder: buscables > lista.length ? 'proyectos e iniciativas' : 'proyectos',
        ayuda: `buscar en los ${buscables} · ⏎ abre el primero · ⎋ borra`, cuenta: { id: 'proyectos-cuenta' }, claseBarra: 'proy-herr',
        herramientas: orden({ grupo: 'proyectos', accion: 'proy-orden', opciones: ORDENES_P, activa: '' }) }),
    filtrosProyectos(lista, areas, cerrados),
    '<div id="proyectos">'];
    if (tabla) {
        // los nombres de las columnas, alineados con las filas: el clic ordena por esa (la que ordena, en el acento); otro
        // clic, o «estado», vuelve al orden de siempre
        const col = (k: string, clase: string) => {
            const [, nombre, como] = COLUMNAS_P.find(c => c[0] === k)!;
            return `<span class="${clase}" data-orden-p="${k}" title="${esc(`ordenar por ${como}${k === 'estado' ? '' : ' (otra vez: por estado)'}`)}">${nombre}</span>`;
        };
        const solo = (clase: string, nombre: string, ayuda: string) => `<span class="${clase}" title="${esc(ayuda)}">${nombre}</span>`;
        h.push(`<div class="fila proy-cab proy-cols"><span class="at"></span>${col('nombre', 'que')}${col('estado', 'estado-p')}${col('fase', 'etapa')}`
            + solo('inicio-p', 'inicio', 'cuándo partió (o parte)') + col('plazo', 'cuando-p') + solo('area-p', 'área', 'el área que declara su documento')
            + solo('aviso-p', 'aviso', 'lo que no cuadra, según su fuente') + `${col('pend', 'tareas-p')}<span class="menu-col"></span></div>`);
    }
    // cada sección con su cabecera adelante, y todas las filas con su lugar de siempre (`data-orden`): ordenadas por una
    // columna, van sueltas, sin secciones
    const fila = tabla ? filaTabla : filaProyecto;
    let orden_ = 0;
    for (const [sec, titulo] of SECCIONES) {
        const xs = ordenarSeccion(sec, por.get(sec)!, p => p.plazo, p => p.nombre);
        if (!xs.length) continue;
        h.push(separador({ sec, orden: String(orden_++) }));
        h.push(seccion({ clave: sec, titulo, cuenta: xs.length, ayuda: AYUDA_SECCION[sec], abierta: true, accion: 'proy-seccion',
            clases: ['proy-sec-cab'], datos: { sec, orden: String(orden_++) },
            filas: () => xs.map(p => fila(p, sec, sel, cuentas?.get(p.ruta), hoy, orden_++)).join('') }));
    }
    h.push('<div id="proyectos-vacio" class="vacio" hidden></div></div>');
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

/** Cuántas iniciativas vivas hay, en cuántos grupos y cuántas no van (terminadas o descartadas), para el globo de la
 *  barra: «28 iniciativas en 2 programas · 4 terminadas o descartadas, fuera». */
export function textoIniciativas(inis: readonly cli.JsonProyecto[], campo: string, voc: Vocabulario = SIN_VOCABULARIO): string {
    const vivas = inis.filter(p => !cerradaIniciativa(p, voc));
    const n = vivas.length, fuera = inis.length - n;
    const ps = campo ? programas(agrupar(vivas, campo)) : 0;
    const grupo = campo === 'programa' ? 'programa' : 'grupo';
    return `${n} iniciativa${n === 1 ? '' : 's'}${ps ? ` en ${ps} ${grupo}${ps === 1 ? '' : 's'}` : ''}`
        + `${fuera ? ` · ${fuera} terminada${fuera === 1 ? '' : 's'} o descartada${fuera === 1 ? '' : 's'}, fuera` : ''}`;
}

/** Una fila de pendiente en el detalle de un proyecto y en «ahora»: la misma de «tareas» (fila-tarea.ts), sin la
 *  columna del proyecto. */
export function filaPendiente(t: Pendiente): string {
    return filaTarea(t);
}

/** Las filas de pendientes de una lista del detalle: la ranura del código solo si alguna lo tiene (una tarea de un
 *  proveedor); si son todas casillas del documento, sin ella. */
function filasPendientes(ps: readonly Pendiente[]): string[] {
    const sinCodigo = !ps.some(t => !!t.fila.ficha || !!t.fila.proveedor);
    return ps.map(t => filaTarea(t, { sinCodigo }));
}

/** Una sección del README ya dibujada para el detalle: su clave (con ella, la página recuerda si estaba abierta al
 *  repintar), su título, su texto propio en html, lo que se lee de ella plegada, si no tiene contenido propio, qué es
 *  para el resumen (readme.claseDe) y las suyas. */
export interface ParteVista { k: string; titulo: string; html: string; vistazo: string; vacia: boolean; clase: readme.Clase; subs: ParteVista[]; resumen?: string }

/** El README dibujado: su entrada (el título y lo que va antes de la primera sección, el resumen del documento), sus
 *  secciones, los datos de su ficha (campo y valor, en html) y el documento entero, sin su frontmatter (`todo`: la pestaña
 *  «documento»). `falla`: no se pudo leer. */
export interface ReadmeVisto { entrada: ParteVista | null; partes: ParteVista[]; datos: [string, string][]; falla?: string; todo?: string }

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
        todo: bloque(texto.replace(/^\uFEFF?---\r?\n[\s\S]*?\r?\n---\r?\n/, '')),
    };
}

/** Cómo va, la primera fila del cuerpo del detalle, en una línea (entera en su globo): el círculo de su fase, en su
 *  ranura como en la lista, y su estado efectivo (y si es a mano, desde cuándo) y su plazo: la etapa, de cuándo a cuándo,
 *  lo que no cuadra y el enlace a su fuente. De una iniciativa, lo suyo (iniciativas.ts, `comoVaIniciativa`). */
function htmlComoVa(p: cli.JsonProyecto, iniciativa?: { campo: string; voc?: Vocabulario }): string {
    let marca: string, dice: string[];
    if (iniciativa) {
        const c = comoVaIniciativa(p, iniciativa.campo, iniciativa.voc);
        [marca, dice] = [c.peso, c.partes];
    } else {
        const sec = seccionDe(p);
        const mano = /a mano[^·]*/.exec(p.estado_completo ?? '')?.[0]?.trim() ?? '';
        const pl = p.plazo;
        const senal = typeof pl?.avance === 'number' ? S.fase(pl.avance, pl.aviso ?? '') : null;
        marca = senal?.circulo ? `<span class="senal${senal.tono ? ` tono-${senal.tono}` : ''}">${circulo(senal.circulo)}</span>` : '';
        dice = [`<b>${esc(NOMBRE[sec])}</b>${mano ? ` <span class="dim">${esc(mano)}</span>` : ''}`];
        if (!pl) dice.push(`<span class="dim">sin plazo${p.estado_completo && !efectivo(p.estado ?? '') ? `; su documento dice «${esc(p.estado_completo)}»` : ''}</span>`);
        else {
            if (pl.etapa) dice.push(esc(pl.etapa));
            dice.push(pl.fin > pl.inicio ? `${esc(diaCorto(pl.inicio))} → ${esc(diaCorto(pl.fin))}` : `desde ${esc(diaCorto(pl.inicio))}`);
            if (pl.aviso) dice.push(`<span class="tono-atencion">${esc(pl.aviso)}</span>`);
            if (pl.enlace) dice.push(`<a data-accion="proy-enlace" data-valor="${esc(pl.enlace)}" title="${esc(pl.enlace)}">${esc(pl.fuente || 'su fuente')}</a>`);
        }
    }
    const html = dice.join(' · ');
    const entero = html.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&');
    return `<div class="det-va"><span class="det-va-marca">${marca}</span><span class="det-va-texto" title="${esc(entero)}">${html}</span></div>`;
}

/** Las pestañas del detalle. Cuál se ve lo recuerda la página (vista.ts, `pd`): al elegir otro proyecto, la misma. */
const PESTANAS = ['resumen', 'pendientes', 'documento'] as const;

/** Un texto del resumen, recortado a unas líneas; «más» lo muestra entero (vista.ts lo muestra solo si no cabe). */
const recorte = (k: string, html: string, base: string): string =>
    `<div class="det-md recorte" data-k="${esc(k)}" data-base="${esc(base)}">${html}</div><a class="mas" hidden>más</a>`;

/** Una sección con las suyas, seguida (en el resumen no se pliega). */
const entera = (x: ParteVista): string => (x.resumen ?? x.html) + x.subs.map(s => `<h5>${esc(s.titulo)}</h5>${entera(s)}`).join('');

/** Una sección del resumen, como las de una pantalla (dia.css, `h2.sec`: las de la barra de hilos): una línea arriba, de
 *  borde a borde, y su título en la tinta de las cabeceras, con su cuenta tenue al lado. */
const seccionResumen = (titulo: string, cuerpo: string, cuenta = ''): string =>
    `<div class="bloque det-r"><h2 class="sec">${esc(titulo)}${cuenta ? ` <span class="cuenta">${esc(cuenta)}</span>` : ''}</h2>${cuerpo}</div>`;

/** El resumen: lo que pide atención antes que lo que explica. Cómo va según su documento, lo próximo, lo que espera
 *  de otros, qué es, sus datos y dónde está. Lo que no tiene, no se muestra. */
function htmlResumen(d: DetalleProyecto): string {
    const { p } = d;
    const r = d.readme || undefined;
    const h: string[] = ['<div class="det-pane" data-pane="resumen">'];
    const deClase = (c: readme.Clase) => (r?.partes ?? []).filter(x => x.clase === c && !x.vacia).slice(0, 2);
    for (const x of deClase('estado')) h.push(seccionResumen(x.titulo, recorte(`r${x.k}`, entera(x), p.ruta)));
    const pend = d.pendientes;
    // lo próximo: los tres primeros (todos, en su pestaña, que dice cuántos son)
    h.push(seccionResumen('próximos', pend === null ? '<div class="vacio">leyendo…</div>' : !pend.length ? '<div class="vacio">nada pendiente</div>'
        : filasPendientes(pend.slice(0, 3)).join(''), pend && pend.length > 3 ? `3 de ${pend.length}` : ''));
    for (const x of deClase('abierto')) h.push(seccionResumen(x.titulo, recorte(`r${x.k}`, entera(x), p.ruta)));
    if (d.readme === null) h.push(seccionResumen('qué es', '<div class="vacio">leyendo…</div>'));
    else if (r?.falla) h.push(`<div class="vacio falla">${esc(r.falla)}</div>`);
    else if (r?.entrada) h.push(seccionResumen('qué es', recorte('re', r.entrada.html, p.ruta)));
    if (r?.datos.length) {
        const dl = (xs: [string, string][]) => `<dl class="det-datos" data-base="${esc(p.ruta)}">${xs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
        h.push(seccionResumen('datos', dl(r.datos.slice(0, 6))
            + (r.datos.length > 6 ? `<details class="det-mas" data-k="datos"><summary>${r.datos.length - 6} más</summary>${dl(r.datos.slice(6))}</details>` : '')));
    }
    h.push(`<div class="det-pie">${[p.area, p.arquetipo, p.ruta].filter(Boolean).map(x => esc(x ?? '')).join(' · ')}`
        + `${p.modificado ? ` · tocado ${esc(haceCorto(p.modificado))}` : ''}</div></div>`);
    return h.join('');
}

/** Los pendientes: todos (pedirle a un agente que revise cuáles ya se hicieron es un ícono de la barra). */
function htmlPendientes(d: DetalleProyecto): string {
    const h: string[] = ['<div class="det-pane" data-pane="pendientes">'];
    if (d.aviso) h.push(`<div class="vacio falla">${esc(d.aviso)}</div>`);
    if (d.pendientes === null) h.push('<div class="vacio">leyendo…</div>');
    else if (!d.pendientes.length) h.push('<div class="vacio">nada pendiente</div>');
    else h.push(...filasPendientes(d.pendientes));
    h.push('</div>');
    return h.join('');
}

/** El documento: su README entero, con la prosa compartida (media/css/prosa.css, la del visor y la lectura de un hilo: la
 *  decidió la persona el 26-nov), para leerlo de corrido. Sin su frontmatter. */
function htmlDocumento(d: DetalleProyecto): string {
    const r = d.readme, base = d.p.ruta;
    const cuerpo = r === null ? '<div class="vacio">leyendo…</div>' : !r ? '<div class="vacio">sin README</div>'
        : r.falla ? `<div class="vacio falla">${esc(r.falla)}</div>`
        : r.todo ? `<div class="prosa prosa-md det-doc" data-base="${esc(base)}">${r.todo}</div>` : '<div class="vacio">vacío</div>';
    return `<div class="det-pane" data-pane="documento">${cuerpo}</div>`;
}

/** La columna derecha: arriba, quedándose, su barra (componentes/pantalla.ts: el nombre, tal cual y cortado con «…»,
 *  entero en su globo; a la derecha, íconos: ir a su hilo o retomarlo, consolidar sus pendientes, abrir su README y su
 *  ⋯), cómo va en una línea y las pestañas; abajo, la pestaña que se ve: el resumen, los pendientes o el documento. */
export function htmlDetalleProyecto(d: DetalleProyecto | undefined, que = 'un proyecto'): string {
    if (!d) return `<div class="vacio det-vacio">elige ${que} a la izquierda</div>`;
    const { p } = d;
    const n = d.pendientes?.length ?? 0;
    const ir = p.vivo ? 'ir a su hilo' : p.hilo ? 'retomar su hilo' : 'abrir con el agente';
    const ayudaIr = p.hilo ? `${ir}: «${p.hilo}»${p.vivo ? '' : ' (dormido)'}` : `${ir}: un hilo nuevo, con el agente cargando el proyecto`;
    // en una columna (el teléfono) el detalle es una pantalla propia: «‹» vuelve a la lista (en dos, no se ve: proyectos.css)
    const cab = barra({ volver: { accion: 'proy-volver', icono: I.atras, ayuda: 'volver a la lista (⎋)' },
        nombre: p.nombre, literal: true, ayuda: `${p.nombre}\n${p.ruta}`, acciones: [
        { accion: 'proyecto', valor: p.ruta, icono: I.agente, tono: C.agente, ayuda: ayudaIr },
        { accion: 'proy-consolidar', valor: p.ruta, icono: I.consolidar, tono: C.hecho,
          ayuda: 'consolidar sus pendientes: un agente revisa cada uno abierto del README, busca si ya se hizo y marca lo hecho con su prueba (/consolidar)' },
        { accion: 'abrir-ruta', valor: `${p.ruta}/README.md`, icono: I.documento, tono: C.ir, ayuda: 'abrir su README' },
        { accion: 'proy-menu', valor: p.ruta, icono: I.menu, ayuda: 'más: la carpeta, copiar la ruta, archivar su hilo' },
    ] });
    return `<div class="det-cab" data-mismo="${esc(p.ruta)}">${cab}${htmlComoVa(p, d.iniciativa)}`
        // sus pestañas (componentes/pestanas.ts): la abierta la marca la página (vista.ts, `aplicarDetalle`), sin repintar
        + pestanas({ nombre: 'proyecto', activa: '', clases: ['det-pest'],
            pestanas: PESTANAS.map(k => ({ valor: k, nombre: k, datos: { pest: k }, ...(k === 'pendientes' && n ? { cuenta: n } : {}) })) }) + '</div>'
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
    /** la subvista que se ve (`subvistas`): los proyectos (clientes), los negocios (comercial) o las iniciativas
     *  (interno). Con un modo que no declara negocios ni iniciativas, o un mundo que no tiene ninguno, una sola lista */
    private vista: Subvista = 'clientes';
    /** la primera casilla abierta del README de cada iniciativa (su próximo paso, si no tiene otro): se leen al ver
     *  «interno», una vez por entrada a la pantalla */
    private casillas = new Map<string, string>();
    /** la tabla extendida (↔, una vista de la barra): a lo ancho, sin el detalle; elegir un proyecto vuelve a la lista */
    private tabla = false;

    readonly acciones: Record<string, Accion> = {
        // la pestaña: la subvista que se veía
        'proyectos': () => this.abrir(),
        // una subvista (las pestañas de su barra): clientes, comercial o interno; desde otra (gantt), la abre
        // o la tabla extendida, una vista más de los proyectos (como gantt)
        'proy-vista': v => {
            if (v === 'tabla') { this.vista = 'clientes'; this.tabla = true; } else if (esSubvista(v)) { this.vista = v; this.tabla = false; } else return;
            return this.t.pantalla === 'proyectos' ? this.pintar() : this.abrir();
        },
        'proyecto': v => v && this.abrirProyecto(v),
        'proy-sel': v => { if (!v) return; if (this.tabla) { this.tabla = false; this.sel = v; this.pintar(); } return this.ver(v); },
        // ir a uno desde otra pantalla: a la subvista donde está
        'proy-ir': v => { if (v) { this.sel = v; this.vista = this.subvistaDe(v); return this.abrir(); } },
        // las iniciativas, desde otra pantalla (todo): su subvista
        'proy-iniciativas': () => { this.vista = 'interno'; return this.abrir(); },
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
        this.casillas.clear();
        // recargada (un despliegue): la lista de antes mientras llega la de ahora, en vez de la pantalla vacía
        const antes = this.lista ? undefined : cli.proyectosRecordados();
        if (antes) { this.lista = antes.proyectos; this.areas = antes.areas ?? []; this.vocabulario = vocabularioDe(antes.iniciativas); }
        if (!this.lista) this.pintar('leyendo los proyectos…');
        else if (antes) this.pintar();
        // los pendientes de los documentos se piden en paralelo: la lista no los espera
        const desde = generacionDeAhora();
        const repo = cli.pendientesRepo().then(r => {
            this.pendRepo = r.datos?.pendientes ?? [];
            this.pendRepoDesde = desde;
            this.pendRepoAviso = r.datos ? '' : (r.error ?? 'telar pendientes no contestó');
            if (this.t.pantalla !== 'proyectos') return;
            // la lista ya está pintada: solo se le dan las cuentas, para filtrar «con pendientes»; las iniciativas se
            // repintan, que su próximo paso sale de esas tareas y casillas
            const cuentas = this.cuentasPendientes();
            if (this.visible() === 'interno') this.pintar();
            else if (cuentas) this.t.panel?.cuentasProyectos(Object.fromEntries(cuentas));
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
            ...this.esIniciativa(ruta) ? { iniciativa: { campo: modos.campoIniciativas(this.iniciativas()), voc: this.vocabulario } } : {} };
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
            await ui.copiar(ruta, `telar: copiado ${ruta}`);
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

    /** Las subvistas que hay en el modo y el mundo puestos: los proyectos (clientes) siempre; los negocios (comercial)
     *  si el modo los declara y el mundo puesto tiene alguno; las iniciativas (interno), igual. Una sola: null, y la
     *  pantalla es una lista, sin pestañas. Cuenta el mundo puesto aunque el modo sea todo (donde el mundo ordena y no
     *  esconde): en el mundo personal, proyectos es una lista, aunque todo deje ver los negocios del trabajo. */
    private hay(): Subvista[] | null {
        const del = (xs: cli.JsonProyecto[]) => xs.some(p => mundo.enElPuesto(p.mundo));
        const hay: Subvista[] = ['clientes', ...del(this.negocios()) ? ['comercial' as const] : [], ...del(this.iniciativas()) ? ['interno' as const] : []];
        return hay.length > 1 ? hay : null;
    }

    /** La que se ve: la elegida, si la hay en este modo y este mundo; si no, la de los proyectos. */
    private visible(): Subvista { return this.hay()?.includes(this.vista) ? this.vista : 'clientes'; }

    /** Las pestañas de su barra (panel.ts, `vistasDeBarra`, antes de las de los módulos que van dentro: gantt), con la
     *  que se ve marcada si `activa` (la pantalla de proyectos, y no un módulo): las subvistas que hay (o, si es una sola
     *  lista, «proyectos») y la tabla extendida (↔), otra forma de mirar los proyectos. */
    subvistas(activa: boolean): VistaDePantalla[] {
        const hay = this.hay();
        const ve = this.visible();
        const tabla = this.tabla && ve === 'clientes';
        const vistas: VistaDePantalla[] = hay
            ? hay.map(k => ({ accion: 'proy-vista', valor: k, nombre: k, icono: SUBVISTA[k][0], ayuda: SUBVISTA[k][1], si: activa && !tabla && ve === k }))
            : [{ accion: 'proy-vista', valor: 'clientes', nombre: 'proyectos', icono: SUBVISTA.clientes[0], ayuda: SUBVISTA.clientes[1], si: activa && !tabla }];
        return [...vistas, { accion: 'proy-vista', valor: 'tabla', nombre: 'tabla', icono: I.ancho, si: activa && tabla,
            ayuda: 'los proyectos a lo ancho, sin el detalle, con todas las columnas y en palabras (elegir uno vuelve a la lista)' }];
    }

    /** En qué subvista está una unidad. */
    private subvistaDe(ruta: string): Subvista {
        const p = this.lista?.find(x => x.ruta === ruta);
        const a = p?.arquetipo.toLowerCase() ?? '';
        return modos.tipos('iniciativas').includes(a) ? 'interno' : modos.tipos('negocios').includes(a) ? 'comercial' : 'clientes';
    }

    /** El próximo paso de cada iniciativa (iniciativas.ts, `Proximo`): lo próximo por decidir; si no, su tarea abierta más
     *  urgente; si no, su casilla pendiente más urgente (las de su sección de pendientes) o, si no tiene, la primera
     *  abierta de su README; si no tiene ninguno, vacío. Lo que todavía no se lee (las tareas y casillas, su README)
     *  queda sin decir. */
    private proximos(inis: readonly cli.JsonProyecto[]): Map<string, Proximo> {
        const m = new Map<string, Proximo>();
        for (const p of inis) {
            const dec = (p.frontmatter?.proxima_decision ?? '').trim();
            if (dec) { m.set(p.ruta, { texto: dec, de: 'decisión' }); continue; }
            const ps = this.pendientesDe(p.ruta);
            const t = ps?.find(x => !!x.fila.proveedor) ?? ps?.[0];
            if (t) { m.set(p.ruta, { texto: limpiarMd(t.texto), de: t.fila.proveedor ? 'tarea' : 'casilla' }); continue; }
            const c = this.casillas.get(p.ruta);
            if (ps && c !== undefined) m.set(p.ruta, { texto: c, de: c ? 'casilla' : '' });
        }
        return m;
    }

    /** La primera casilla abierta del README de cada iniciativa que todavía no se leyó; al terminar, si alguna cambió y se
     *  ve «interno», se repinta. */
    private async leerCasillas(inis: readonly cli.JsonProyecto[]): Promise<void> {
        const faltan = inis.filter(p => !this.casillas.has(p.ruta));
        if (!faltan.length || !modelo.raiz) return;
        await Promise.all(faltan.map(async p => {
            const crudo = await disco().leer(rutas.unir(modelo.raiz!, p.ruta, 'README.md')).catch(() => undefined);
            this.casillas.set(p.ruta, crudo === undefined ? '' : primeraCasilla(crudo));
        }));
        if (this.t.pantalla === 'proyectos' && this.visible() === 'interno') this.pintar();
    }

    /** Todas las filas van a la página de una vez; buscar y ordenar ocurre allá, sin ir y
     *  volver por cada letra. Ver `aplicarProyectos` en vista.ts. */
    pintar(cargando = ''): void {
        if (!this.t.panel) return;
        this.t.teclas.clear();
        const vista = this.visible();
        const lista = this.proyectos();
        const h: string[] = [];
        const barra: EnBarra = {
            ayuda: vista === 'interno' ? textoIniciativas(this.iniciativas(), modos.campoIniciativas(this.iniciativas()), this.vocabulario)
                : this.lista ? textoNegocios(this.lista) || undefined : undefined,
        };
        if (this.aviso) h.push(`<div class="fila falla">${esc(this.aviso)}</div>`);
        if (this.fallas.length && vista === 'clientes') h.push(`<div class="fila falla" title="${esc(this.fallas.join('\n'))}">sin plazos de: ${esc(this.fallas.map(f => f.split(':')[0]).join(', '))}</div>`);
        if (cargando) { h.push(`<div class="fila dim">${esc(cargando)}</div>`); this.t.pintar(h, barra); return; }
        const cuentas = this.cuentasPendientes();
        let izquierda: string[];
        let que = 'un proyecto';
        if (vista === 'interno') {
            const inis = this.iniciativas();
            const campo = modos.campoIniciativas(inis);
            const o = { sel: this.sel, cuentas, voc: this.vocabulario, esMia, ...this.pendRepo ? { proximos: this.proximos(inis) } : {} };
            void this.leerCasillas(inis);
            const vivas = htmlIniciativas(inis, campo, o);
            izquierda = [barraBuscar({ id: 'buscar-p', atajo: '/', placeholder: 'iniciativas', ayuda: `buscar en las ${inis.length} · ⏎ abre la primera · ⎋ borra`,
                cuenta: { id: 'proyectos-cuenta' }, claseBarra: 'proy-herr' }), filtrosIniciativas(inis, campo, o),
                vivas || '<div class="vacio">ninguna iniciativa viva en este mundo</div>'];
            que = 'una iniciativa';
        } else if (vista === 'comercial') {
            izquierda = htmlNegocios(this.negocios(), this.sel, cuentas);
            que = 'un negocio';
        } else izquierda = htmlListaProyectos(lista, this.sel, cuentas, this.areas, lista.length, this.tabla);
        const tabla = this.tabla && vista === 'clientes';
        const det = this.sel && this.subvistaDe(this.sel) === vista ? this.det : undefined;
        // entre la lista y el detalle, el divisor: una línea propia, de alto completo (proyectos.css)
        h.push(`<div class="proy-dos${tabla ? ' extendida' : ''}" data-vista="${vista}"><div class="proy-lista">`, ...izquierda,
            `</div><div class="proy-divisor"></div><div id="proy-det">${htmlDetalleProyecto(det, que)}</div></div>`);
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

    /** Los negocios: las unidades de los arquetipos que el modo llama así (`negocios`), del mundo puesto. */
    negocios(): cli.JsonProyecto[] {
        const tipos = modos.tipos('negocios');
        return tipos.length ? (this.lista ?? []).filter(p => tipos.includes(p.arquetipo.toLowerCase()) && mundo.seVe(p.mundo)) : [];
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
