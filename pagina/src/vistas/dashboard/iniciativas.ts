// Las iniciativas en la pantalla de proyectos: el trabajo propio, sin cliente, aparte de los proyectos y los negocios. Qué
// es una iniciativa lo dice el modo (`iniciativas`, los arquetipos del perfil), y con qué se agrupan, también
// (`agrupar_iniciativas`, un campo del frontmatter: el programa al que pertenecen). De cada una se lee su frontmatter
// (`telar proyectos --json`, su `frontmatter`): quién la lleva (`dueno`), cómo va (`estado`), lo próximo que hay que
// decidir (`proxima_decision`) y cuánto importa (`peso`: alto, medio o bajo, el círculo de Táctica).
//
//   ▽ me toca 2   sin próximo paso 5                          ← los filtros (proyectos › interno)
//   ⌄ CLUB DE LECTURA  4                                       ← cada grupo, una sección (seccion())
//   ●  ◑ Club de lectura  ¿abrimos en marzo?     lo llevo  2   ← la que lo encabeza, primera; mi papel
//   ◐  ○ Canales del club  sin próximo paso  ⚠   Ana           ← fuera del vocabulario: marcado
//   ○  • Boletín  T12 · llamar al proveedor  ↗   sin definir   ← la manda otra fuente: no se cambia aquí
//      › ideas 2                                               ← sus ideas, en un submenú que empieza plegado
//   ⌄ SIN PROGRAMA  1
//   ◐  ◔ Inventario anual  P-03 · el presupuesto     Bruno
//
// Es la subvista «interno» de proyectos (proyectos.ts): cada fila es un ítem (componentes/item.ts): el peso y el estado
// en sus ranuras, el nombre con su próximo paso detrás (tenue: se corta antes que él; «sin próximo paso», en el color de
// cuidado) y al final mi papel (de su dueño: «lo llevo», quién la lleva, «sin definir») y cuántos pendientes tiene, que
// ceden antes que el nombre cuando la lista se angosta (proyectos.css). Las terminadas y las descartadas no van.
//
// El estado de cada una se ve con su círculo y su color (componentes/senales.ts, `estadoIniciativa`), y se cambia con un
// clic en él: un menú con el vocabulario cerrado de `[iniciativas] estados` (en `GET /proyectos`, `iniciativas`), que
// escribe `estado:` y `estado_desde:` en su ficha (`POST /proyectos/estado`). Un sinónimo (`sinonimos`: «activo» vale
// como «en curso») se ve y se cuenta como el suyo, sin reescribir el archivo; uno que no está en el vocabulario se ve tal
// cual, marcado, y al cambiarlo se ofrece el vocabulario. Con vocabulario, el estado es el de su frontmatter y nada más
// (una ficha sin `estado:` está sin estado, y se le pone uno; ni el Estado de su tabla ni el de su programa cuentan). La
// ficha dice si su estado lo manda otra fuente (`estado_fuente: sheet`; `fuentes` dice cómo se nombra cada una): esas
// llevan ↗ y «fuente: Sheet» al pasar, y no tienen el menú. Por qué está en su estado (`estado_nota:`) va al pasar el mouse y en el
// detalle. Sin vocabulario, el estado se ve como lo escribe cada ficha (o su tabla) y no se cambia aquí.
//
// La que encabeza un grupo es la iniciativa cuya carpeta se llama como el valor con que se agrupan las otras (el slug al
// que apuntan): no lleva programa ella misma. Las que no dicen programa ni encabezan uno van en «sin programa». Sin
// `agrupar_iniciativas`, van todas juntas, sin grupos. Todo puro: lo usa la pantalla (proyectos.ts) y lo prueba
// npm run prueba:componentes («iniciativas»).

import type * as cli from '../../cli';
import { circulo } from '../../componentes/circulo';
import { item, type Pieza } from '../../componentes/item';
import { filtros, type GrupoFiltro } from '../../componentes/filtros';
import { seccion, separador, submenu } from '../../componentes/seccion';
import { type ClaseEstado, CLASES_ESTADO, enLinea, estadoIniciativa } from '../../componentes/senales';
import { LLENO_PESO } from '../../componentes/tactica';
import { esc, normalizar } from '../../estilo';
import { I } from '../../web/iconos';

export type Peso = keyof typeof LLENO_PESO;
const PESOS = Object.keys(LLENO_PESO) as Peso[];
/** El orden de un peso: alto primero; sin peso, después de bajo. */
const RANGO: Record<string, number> = { alto: 0, medio: 1, bajo: 2 };

// ───────────────────────── el estado y su vocabulario ─────────────────────────

/** El vocabulario de estados (`[iniciativas]` de la configuración, en `GET /proyectos`: `iniciativas`). */
export interface Vocabulario {
    /** el vocabulario cerrado, en su orden; vacío: no hay, y el estado no se cambia aquí */
    estados: string[];
    /** lo escrito → el estado al que vale («activo» → «en curso») */
    sinonimos: Record<string, string>;
    /** la clase de un estado cuyo nombre no la dice (`claseDe`) */
    clases: Record<string, string>;
    /** cómo se nombra cada fuente externa: lo que dice `estado_fuente` en una ficha → su nombre («sheet» → «Sheet») */
    fuentes: Record<string, string>;
}
export const SIN_VOCABULARIO: Vocabulario = { estados: [], sinonimos: {}, clases: {}, fuentes: {} };

/** El de `GET /proyectos`, con lo que falte vacío (un telar más viejo no lo trae). */
export const vocabularioDe = (j?: Partial<Vocabulario> | null): Vocabulario => ({
    estados: j?.estados ?? [], sinonimos: j?.sinonimos ?? {}, clases: j?.clases ?? {}, fuentes: j?.fuentes ?? {},
});

const norma = (t: string): string => normalizar(t.trim()).replace(/\s+/g, ' ');

/** La clase de un estado: la que declara `clases`, o la que dice su nombre; undefined si no se sabe. */
export function claseDe(estado: string, voc: Vocabulario = SIN_VOCABULARIO): ClaseEstado | undefined {
    const n = norma(estado);
    const declarada = Object.entries(voc.clases).find(([e]) => norma(e) === n)?.[1];
    if (declarada && (CLASES_ESTADO as readonly string[]).includes(declarada)) return declarada as ClaseEstado;
    if (/^ideas?(?![a-z])/.test(n)) return 'idea';
    if (/^(disen|prepar|planific|por (partir|empezar|iniciar|comenzar)|evaluand|explorand)/.test(n)) return 'preparacion';
    if (/^(en curso|activ|en ejecucion|en marcha|en desarrollo|implementand)/.test(n)) return 'curso';
    if (/(^|\s)(pausad|en pausa|detenid|congelad|suspendid|en espera|bloquead)/.test(n)) return 'pausa';
    if (/^(terminad|hech|complet|cerrad|finalizad|entregad|lanzad|cumplid)/.test(n)) return 'terminada';
    if (/^(descartad|cancelad|abandonad|desistid)/.test(n)) return 'descartada';
    return undefined;
}

/** La fuente externa que manda el estado de una iniciativa: la que dice su ficha (`estado_fuente`), con el nombre que le
 *  da `fuentes` (una que no nombra, tal cual); "" si no dice: se cambia aquí. */
export function fuenteDe(fm: Record<string, string> | undefined, voc: Vocabulario = SIN_VOCABULARIO): string {
    const escrita = String(fm?.estado_fuente ?? '').trim();
    return escrita ? Object.entries(voc.fuentes).find(([d]) => norma(d) === norma(escrita))?.[1] ?? escrita : '';
}

/** El estado de una iniciativa como se ve y se cuenta. */
export interface EstadoVisto {
    /** como está escrito: su `estado` (sin vocabulario, si no lo dice, el Estado de su tabla); "" sin estado */
    escrito: string;
    /** como se ve y se cuenta: el del vocabulario (un sinónimo, el suyo), o lo escrito si no está */
    valor: string;
    /** escrito y fuera del vocabulario (si hay vocabulario) */
    fuera: boolean;
    clase?: ClaseEstado;
    /** la fuente externa que lo manda: no se cambia aquí; "" si se cambia aquí */
    fuente: string;
    /** si se cambia desde la lista: hay vocabulario y no lo manda otra fuente */
    cambia: boolean;
    /** por qué está en su estado (`estado_nota`), si lo dice */
    nota?: string;
}

export function estadoDe(p: cli.JsonProyecto, voc: Vocabulario = SIN_VOCABULARIO): EstadoVisto {
    const fm = p.frontmatter ?? {};
    // con vocabulario, el de su frontmatter y nada más; sin él, como antes: si no lo dice, el Estado de su tabla
    const escrito = (fm.estado ?? '').trim() || (voc.estados.length ? '' : (p.estado ?? '').trim());
    const nota = (fm.estado_nota ?? '').trim();
    const n = norma(escrito);
    const delVoc = n ? voc.estados.find(e => norma(e) === n) ?? Object.entries(voc.sinonimos).find(([d]) => norma(d) === n)?.[1] : undefined;
    const valor = delVoc ?? escrito;
    const fuera = !!escrito && !!voc.estados.length && delVoc === undefined;
    const clase = fuera || !valor ? undefined : claseDe(valor, voc);
    const fuente = fuenteDe(fm, voc);
    return { escrito, valor, fuera, ...clase ? { clase } : {}, fuente, cambia: !!voc.estados.length && !fuente, ...nota ? { nota } : {} };
}

/** Lo que dice el estado al pasar el mouse: su nota, cómo está escrito si no es igual, si está fuera del vocabulario, de
 *  qué fuente es y qué hace el clic. */
export function ayudaEstado(e: EstadoVisto, voc: Vocabulario = SIN_VOCABULARIO): string {
    const lineas = [e.valor ? `estado: ${e.valor}` : 'sin estado'];
    if (e.nota) lineas.push(e.nota);
    if (e.fuera) lineas.push(`fuera del vocabulario: ${voc.estados.join(', ')}`);
    else if (e.escrito && e.escrito !== e.valor && norma(e.escrito) !== norma(e.valor)) lineas.push(`su ficha dice «${e.escrito}», que vale como «${e.valor}»`);
    if (e.fuente) lineas.push(`fuente: ${e.fuente}: se cambia allá, no aquí`);
    else if (e.cambia) lineas.push(`clic: ${e.fuera || !e.valor ? 'elegir uno' : 'cambiarlo'}`);
    return lineas.join('\n');
}

/** El estado en HTML: su círculo y su palabra (fuera del vocabulario, marcada; sin estado, tenue). `fuerte`: la palabra en
 *  negrita (el detalle). */
export function htmlEstado(e: EstadoVisto, voc: Vocabulario = SIN_VOCABULARIO, fuerte = false): string {
    const senal = e.valor ? enLinea(estadoIniciativa(e.clase, e.fuera)) : '';
    const palabra = esc(e.valor || 'sin estado');
    return `${senal}<span class="ini-e-txt${e.fuera ? ' tono-atencion' : e.valor ? '' : ' dim'}">${fuerte && e.valor ? `<b>${palabra}</b>` : palabra}</span>`
        + (e.fuera ? `<span class="i ini-fuera tono-atencion" title="${esc(`fuera del vocabulario: ${voc.estados.join(', ')}`)}">${I.alerta}</span>` : '');
}

/** Lo que se lee de una iniciativa, de su frontmatter. */
export interface DeIniciativa {
    dueno: string;
    /** su estado como se ve y se cuenta (`estadoDe`): el del vocabulario, o lo escrito (su `estado`; si no lo dice, el
     *  Estado de su tabla de campos) */
    estado: string;
    visto: EstadoVisto;
    proxima: string;
    peso?: Peso;
    /** el valor con que se agrupa (su programa), normalizado para comparar; "" si no lo dice o no se agrupan */
    grupo: string;
    /** el mismo, como está escrito */
    programa: string;
}

/** La carpeta de una unidad: el final de su ruta, en minúsculas (con lo que se compara el programa de las otras). */
export const slugDe = (ruta: string): string => normalizar(ruta.split('/').filter(Boolean).pop() ?? ruta);

export function deIniciativa(p: cli.JsonProyecto, campo: string, voc: Vocabulario = SIN_VOCABULARIO): DeIniciativa {
    const fm = p.frontmatter ?? {};
    const peso = normalizar(fm.peso ?? '') as Peso;
    const visto = estadoDe(p, voc);
    return {
        dueno: (fm.dueno ?? fm['dueño'] ?? fm.responsable ?? '').trim(),
        estado: visto.valor,
        visto,
        proxima: (fm.proxima_decision ?? '').trim(),
        ...PESOS.includes(peso) ? { peso } : {},
        grupo: campo ? normalizar((fm[campo] ?? '').trim()) : '',
        programa: campo ? (fm[campo] ?? '').trim() : '',
    };
}

/** Un grupo: su clave (el valor con que se agrupan; "" las sin programa), cómo se llama, la iniciativa que lo encabeza (si
 *  hay una con su nombre de carpeta) y las suyas, en su orden. */
export interface Grupo { clave: string; nombre: string; cabeza?: cli.JsonProyecto; hijas: cli.JsonProyecto[] }

/** Lo de más peso primero; empatadas, por nombre. */
function porPeso(campo: string): (a: cli.JsonProyecto, b: cli.JsonProyecto) => number {
    const r = (p: cli.JsonProyecto) => RANGO[deIniciativa(p, campo).peso ?? ''] ?? 3;
    return (a, b) => r(a) - r(b) || a.nombre.localeCompare(b.nombre);
}

/** Las iniciativas en sus grupos, por `campo` del frontmatter: primero los programas con la suya (por su peso y su
 *  nombre), después los que no la tienen (por nombre), y al final «sin programa». Sin `campo`, un solo grupo sin nombre. */
export function agrupar(lista: readonly cli.JsonProyecto[], campo: string): Grupo[] {
    const orden = porPeso(campo);
    if (!campo) return lista.length ? [{ clave: '', nombre: '', hijas: [...lista].sort(orden) }] : [];
    const grupos = new Map<string, Grupo>();
    for (const p of lista) {
        const { grupo: g, programa } = deIniciativa(p, campo);
        if (!g) continue;
        if (!grupos.has(g)) grupos.set(g, { clave: g, nombre: programa, hijas: [] });
        grupos.get(g)!.hijas.push(p);
    }
    // la que se llama como un programa lo encabeza (y no va dentro de él, aunque diga serlo)
    const cabezas = new Set<string>();
    for (const p of lista) {
        const g = grupos.get(slugDe(p.ruta));
        if (!g || g.cabeza) continue;
        g.cabeza = p;
        g.nombre = p.nombre;
        g.hijas = g.hijas.filter(x => x !== p);
        cabezas.add(p.ruta);
    }
    const sueltas = lista.filter(p => !cabezas.has(p.ruta) && !deIniciativa(p, campo).grupo);
    const conCabeza = [...grupos.values()].filter(g => g.cabeza);
    const sin = [...grupos.values()].filter(g => !g.cabeza);
    for (const g of grupos.values()) g.hijas.sort(orden);
    return [
        ...conCabeza.sort((a, b) => orden(a.cabeza!, b.cabeza!)),
        ...sin.sort((a, b) => a.nombre.localeCompare(b.nombre)),
        ...sueltas.length ? [{ clave: '', nombre: `sin ${campo === 'funcion' ? 'función' : campo}`, hijas: [...sueltas].sort(orden) }] : [],
    ];
}

/** Cuántos programas hay (los grupos con nombre, sin «sin programa»). */
export const programas = (gs: readonly Grupo[]): number => gs.filter(g => g.clave).length;

/** El círculo de su peso, en su ranura: alto lleno, medio a medias, bajo un aro; sin peso, nada. */
export function marcaPeso(peso?: Peso): string {
    return peso ? `<span class="senal" title="${esc(`peso ${peso}`)}">${circulo({ tam: 'chico', lleno: LLENO_PESO[peso] })}</span>` : '';
}

/** El peso, como pieza de su ranura: alto lleno, medio a medias, bajo un aro; sin peso, nada. */
const piezaPeso = (peso?: Peso): Pieza | null => peso ? { circulo: { tam: 'chico', lleno: LLENO_PESO[peso] }, ayuda: `peso ${peso}` } : null;

/** El estado, como pieza de su ranura: su círculo en el color de su clase y, al pasar, la palabra, su nota y su fuente.
 *  Con vocabulario y sin otra fuente, un clic en él lo cambia (`ini-estado`, en vez de elegir la fila). */
function piezaEstado(p: cli.JsonProyecto, e: EstadoVisto, voc: Vocabulario): Pieza {
    const senal = estadoIniciativa(e.clase, e.fuera);
    const ayuda = ayudaEstado(e, voc);
    if (!e.cambia) return { ...senal, ayuda };
    return { html: `<span class="ini-estado cambia" data-accion="ini-estado" data-valor="${esc(p.ruta)}" data-estado="${esc(e.valor)}"`
        + `${e.clase ? ` data-clase="${e.clase}"` : ''}>${senal.circulo ? circulo(senal.circulo) : ''}</span>`, tono: senal.tono, ayuda };
}

/** El próximo paso de una iniciativa: lo próximo por decidir (`proxima_decision`); si no lo dice, su tarea abierta más
 *  urgente; si no tiene, su casilla pendiente más urgente (las de su documento). Texto vacío: no tiene ninguno («sin
 *  próximo paso»). Lo arma la pantalla (proyectos.ts), que tiene las tareas y las casillas. */
export interface Proximo { texto: string; de: 'decisión' | 'tarea' | 'casilla' | '' }

/** Mi papel en una iniciativa, de su dueño (`dueno`): la llevo (es de la persona), la sigo (es de otro) o sin definir
 *  (no tiene). «La dirijo» no sale de ningún campo. */
export type Papel = 'llevo' | 'sigo' | 'sin';
export const papelDe = (dueno: string, esMia: (d: string) => boolean): Papel => !dueno ? 'sin' : esMia(dueno) ? 'llevo' : 'sigo';

/** Lo que dice la columna del papel: «lo llevo», quién la lleva (la sigo) o «sin definir». */
function piezaPapel(papel: Papel, dueno: string): string {
    const [texto, ayuda, tono] = papel === 'llevo' ? ['lo llevo', `mi papel: la llevo (dueño: ${dueno})`, '']
        : papel === 'sigo' ? [dueno, `mi papel: la sigo; la lleva ${dueno}`, ' tono-tenue'] : ['sin definir', 'mi papel: sin definir (no dice dueño)', ' tono-apagado'];
    return `<span class="dueno-i${tono}" title="${esc(ayuda)}">${esc(texto)}</span>`;
}

/** Una fila, un ítem (componentes/item.ts): el peso y el estado en sus ranuras, el nombre y, tras él y tenue, su próximo
 *  paso (se corta antes que el nombre; «sin próximo paso», en el color de cuidado); al final, lo que no cuadra (un estado
 *  fuera del vocabulario, uno que manda otra fuente), mi papel (o quién la lleva) y cuántos pendientes tiene (ceden antes
 *  que el nombre: proyectos.css), y su ⋯. Lleva lo de las filas de los proyectos (`proy`, `proy-sel`, `data-valor`), así
 *  que se elige, se abre y cuenta sus pendientes igual. La que encabeza su grupo va primera en él (`ini-cabeza`). Sin
 *  `proximo` (todavía se leen las tareas), lo próximo por decidir si lo dice; sin `papel`, quién la lleva. */
export function filaIniciativa(p: cli.JsonProyecto, campo: string,
    o: { sel?: string; pend?: number; grupo: string; cabeza?: boolean; voc?: Vocabulario; proximo?: Proximo; papel?: Papel; idea?: boolean }): string {
    const voc = o.voc ?? SIN_VOCABULARIO;
    const d = deIniciativa(p, campo, voc);
    const e = d.visto;
    const prox = o.proximo ?? (d.proxima ? { texto: d.proxima, de: 'decisión' as const } : undefined);
    const texto = normalizar(`${p.nombre} ${p.ruta} ${d.dueno} ${d.estado} ${e.escrito} ${e.fuente} ${prox?.texto ?? ''} ${d.grupo} ${p.area ?? ''}`);
    const aviso: Pieza | undefined = e.fuera ? { icono: I.alerta, tono: 'atencion', ayuda: `fuera del vocabulario: ${voc.estados.join(', ')}` }
        : e.fuente ? { icono: I.externo, tono: 'tenue', ayuda: `su estado lo manda ${e.fuente}: se cambia allá` } : undefined;
    const pend = o.pend || 0;
    const sufijo: Pieza[] = !prox ? []
        : prox.texto ? [{ texto: prox.texto, tono: 'tenue', ayuda: `próximo paso (${prox.de === 'decisión' ? 'lo próximo por decidir' : `su ${prox.de} más urgente`}): ${prox.texto}` }]
        : [{ texto: 'sin próximo paso', tono: 'atencion', ayuda: 'ni próxima decisión, ni una tarea abierta, ni una casilla pendiente' }];
    const quien = o.papel ? piezaPapel(o.papel, d.dueno)
        : `<span class="dueno-i" title="${esc(d.dueno ? `dueño: ${d.dueno}` : 'sin dueño')}">${esc(d.dueno)}</span>`;
    return item({
        clases: ['proy', 'ini', ...o.cabeza ? ['ini-cabeza'] : []],
        accion: 'proy-sel',
        datos: { valor: p.ruta, grupo: o.grupo, unidad: p.area || 'sin área', pend: pend ? String(pend) : '', texto,
            ...o.papel ? { papel: o.papel } : {}, ...prox && !prox.texto ? { proximo: 'sin' } : {}, ...o.idea ? { idea: '1' } : {} },
        activa: p.ruta === o.sel,
        ayuda: `${p.ruta}${d.programa && !o.cabeza ? `\n${campo}: ${d.programa}` : ''}${p.hilo ? `\nhilo: ${p.hilo}${p.vivo ? '' : ' (dormido)'}` : ''}`,
        inicio: [piezaPeso(d.peso), piezaEstado(p, e, voc)],
        titulo: p.nombre,
        sufijo,
        aviso,
        meta: { html: quien + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${pend || ''}</span>` },
        menu: { accion: 'proy-menu', icono: I.menu, datos: { valor: p.ruta }, ayuda: 'acciones de esta iniciativa' },
    });
}

/** Lo que pide la vista de las iniciativas (proyectos › interno): la elegida, cuántos pendientes tiene cada una, el
 *  vocabulario de su estado, el próximo paso de cada una (si ya se leyeron sus tareas) y quién es la persona (su papel). */
export interface OpcionesIniciativas {
    sel?: string;
    cuentas?: ReadonlyMap<string, number>;
    voc?: Vocabulario;
    proximos?: ReadonlyMap<string, Proximo>;
    esMia?: (dueno: string) => boolean;
}

/** Si una iniciativa ya no está viva: terminada o descartada (no van en la vista). */
export const cerradaIniciativa = (p: cli.JsonProyecto, voc: Vocabulario = SIN_VOCABULARIO): boolean => {
    const c = estadoDe(p, voc).clase;
    return c === 'terminada' || c === 'descartada';
};

/** Las filas de un grupo: la que lo encabeza, primero, y las suyas, sin las ideas (`ideas`: solo las ideas). */
function filasGrupo(g: Grupo, campo: string, o: OpcionesIniciativas, ideas = false): string {
    const voc = o.voc ?? SIN_VOCABULARIO;
    const esIdea = (p: cli.JsonProyecto) => estadoDe(p, voc).clase === 'idea';
    const fila = (p: cli.JsonProyecto, cabeza = false) => filaIniciativa(p, campo, { sel: o.sel, pend: o.cuentas?.get(p.ruta), grupo: g.clave, cabeza, voc,
        ...o.proximos ? { proximo: o.proximos.get(p.ruta) } : {}, ...o.esMia ? { papel: papelDe(deIniciativa(p, campo, voc).dueno, o.esMia) } : {}, idea: ideas });
    const xs = (g.cabeza ? [g.cabeza] : []).concat(g.hijas).filter(p => esIdea(p) === ideas);
    return xs.map(p => fila(p, p === g.cabeza)).join('');
}

/** Lo que dice un grupo al pasar el mouse. */
const ayudaGrupo = (g: Grupo, campo: string): string => !g.clave ? `sin ${campo || 'grupo'}`
    : g.cabeza ? `${campo} «${g.nombre}»: la primera es la que lo encabeza` : `${campo} «${g.clave}»: ninguna iniciativa se llama así`;

/** Las iniciativas, su propia vista (proyectos › interno), con las piezas de la casa (componentes/seccion.ts): cada grupo
 *  (su función o su programa: `agrupar_iniciativas`) una sección, del alto de las barras y en la tinta de las cabeceras,
 *  con cuántas tiene, y con su separador; dentro, las vivas y, al final, sus ideas en un submenú que empieza plegado. Las
 *  terminadas y las descartadas no van. Abrir o plegar cada una lo hace la página (vista.ts, `proy-seccion`): se
 *  recuerda, y buscando o filtrando se abre lo que calza. */
export function htmlIniciativas(lista: readonly cli.JsonProyecto[], campo: string, o: OpcionesIniciativas = {}): string {
    const voc = o.voc ?? SIN_VOCABULARIO;
    const vivas = lista.filter(p => !cerradaIniciativa(p, voc));
    if (!vivas.length) return '';
    const esIdea = (p: cli.JsonProyecto) => estadoDe(p, voc).clase === 'idea';
    const grupos = agrupar(vivas, campo).map(g => {
        const todas = (g.cabeza ? [g.cabeza] : []).concat(g.hijas);
        const ideas = todas.filter(esIdea).length;
        const sec = `ini:${g.clave}`;
        return separador() + seccion({ abierta: true, accion: 'proy-seccion', clave: sec, titulo: g.nombre || 'iniciativas', cuenta: todas.length,
            ayuda: ayudaGrupo(g, campo), clases: ['ini-grupo'], datos: { grupo: g.clave, sec },
            filas: () => filasGrupo(g, campo, o) + (ideas ? submenu({ abierta: true, accion: 'proy-seccion', clave: `ideas:${g.clave}`, titulo: 'ideas',
                cuenta: ideas, ayuda: 'sus ideas: empiezan plegadas', ranuras: 2, clases: ['ini-ideas'],
                datos: { grupo: g.clave, sec: `ideas:${g.clave}`, plegada: '1' }, filas: () => filasGrupo(g, campo, o, true) }) : '') });
    });
    return `<div id="iniciativas">${grupos.join('')}</div>`;
}

/** Los filtros de las iniciativas (componentes/filtros.ts), bajo el buscador: «me toca» (las que llevo) y «sin próximo
 *  paso». Cada uno se prende y se apaga; qué rige y cuántas deja lo pone la página (vista.ts). */
export function filtrosIniciativas(lista: readonly cli.JsonProyecto[], campo: string, o: OpcionesIniciativas): string {
    const voc = o.voc ?? SIN_VOCABULARIO;
    const vivas = lista.filter(p => !cerradaIniciativa(p, voc));
    const grupos: GrupoFiltro[] = [];
    if (o.esMia) {
        const mias = vivas.filter(p => papelDe(deIniciativa(p, campo, voc).dueno, o.esMia!) === 'llevo').length;
        grupos.push({ clave: 'papel', nombre: 'mi papel', activa: '', opciones: [{ clave: 'llevo', nombre: 'me toca', cuenta: mias, ayuda: 'las que llevo: su dueño soy yo' }] });
    }
    if (o.proximos) {
        const sin = vivas.filter(p => o.proximos!.get(p.ruta)?.texto === '').length;
        grupos.push({ clave: 'proximo', nombre: 'próximo paso', activa: '', opciones: [{ clave: 'sin', nombre: 'sin próximo paso', cuenta: sin,
            ayuda: 'las que no tienen ni próxima decisión, ni una tarea abierta, ni una casilla pendiente' }] });
    }
    return filtros({ accion: 'proy-filtro', clase: 'proy-filtros', grupos });
}

/** Cómo va una iniciativa, para el detalle: su estado, quién la lleva, lo próximo por decidir, su peso y su programa. */
export function comoVaIniciativa(p: cli.JsonProyecto, campo: string, voc: Vocabulario = SIN_VOCABULARIO): { peso: string; partes: string[] } {
    const d = deIniciativa(p, campo, voc);
    const e = d.visto;
    const desde = (p.frontmatter?.estado_desde ?? '').trim();
    return {
        peso: marcaPeso(d.peso),
        partes: [
            // el estado, como en la fila (y un clic lo cambia), desde cuándo, y la fuente que lo manda
            (e.cambia ? `<a class="ini-estado cambia" data-accion="ini-estado" data-valor="${esc(p.ruta)}" title="${esc(ayudaEstado(e, voc))}">`
                : `<span class="ini-estado" title="${esc(ayudaEstado(e, voc))}">`)
                + `${htmlEstado(e, voc, true)}${e.cambia ? '</a>' : '</span>'}`
                + (desde ? ` <span class="dim">desde ${esc(desde)}</span>` : '')
                + (e.nota ? ` <span class="dim ini-nota">(${esc(e.nota)})</span>` : ''),
            ...e.fuente ? [`<span class="dim" title="${esc(`su estado lo manda ${e.fuente}: se cambia allá`)}">fuente: ${esc(e.fuente)}</span>`] : [],
            d.dueno ? `${esc(d.dueno)}` : '<span class="dim">sin dueño</span>',
            ...d.proxima ? [`próxima decisión: ${esc(d.proxima)}`] : [],
            ...d.peso ? [`peso ${d.peso}`] : [],
            ...d.programa ? [`programa ${esc(d.programa)}`] : [],
        ],
    };
}
