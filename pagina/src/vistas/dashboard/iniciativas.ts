// Las iniciativas en la pantalla de proyectos: el trabajo propio, sin cliente, aparte de los proyectos y los negocios. Qué
// es una iniciativa lo dice el modo (`iniciativas`, los arquetipos del perfil), y con qué se agrupan, también
// (`agrupar_iniciativas`, un campo del frontmatter: el programa al que pertenecen). De cada una se lee su frontmatter
// (`telar proyectos --json`, su `frontmatter`): quién la lleva (`dueno`), cómo va (`estado`), lo próximo que hay que
// decidir (`proxima_decision`) y cuánto importa (`peso`: alto, medio o bajo, el círculo de Táctica).
//
//   INICIATIVAS 6                                   ← su sección; un clic la deja sola (y la barra vuelve)
//      iniciativa              dueño   estado       próxima decisión
//   ●  Club de lectura  2      Ana     ◑ en curso   ¿abrimos en marzo?         ← la del programa: encabeza su grupo
//   ◐    Canales del club      Ana     ○ piloto     ¿el de novedades?          ← fuera del vocabulario: marcado
//   ○    Boletín                       • idea         fuente: Sheet  ← la manda otra fuente: no se cambia
//      otro-programa                                                           ← un programa sin la suya: su nombre
//   ◐    …
//      sin programa  1                                                         ← sin programa ni hijas, al final
//   ◐    Inventario anual      Bruno   ◔ diseño
//
// El estado de cada una se ve con su círculo y su color (componentes/senales.ts, `estadoIniciativa`), y se cambia con un
// clic en él: un menú con el vocabulario cerrado de `[iniciativas] estados` (en `GET /proyectos`, `iniciativas`), que
// escribe `estado:` y `estado_desde:` en su ficha (`POST /proyectos/estado`). Un sinónimo (`sinonimos`: «activo» vale
// como «en curso») se ve y se cuenta como el suyo, sin reescribir el archivo; uno que no está en el vocabulario se ve tal
// cual, marcado, y al cambiarlo se ofrece el vocabulario. Con vocabulario, el estado es el de su frontmatter y nada más
// (una ficha sin `estado:` está sin estado, y se le pone uno; ni el Estado de su tabla ni el de su programa cuentan). La
// ficha dice si su estado lo manda otra fuente (`estado_fuente: sheet`; `fuentes` dice cómo se nombra cada una): esas
// dicen «fuente: Sheet» y no tienen el menú. Por qué está en su estado (`estado_nota:`) va al pasar el mouse y en el
// detalle. Sin vocabulario, el estado se ve como lo escribe cada ficha (o su tabla) y no se cambia aquí.
//
// La que encabeza un grupo es la iniciativa cuya carpeta se llama como el valor con que se agrupan las otras (el slug al
// que apuntan): no lleva programa ella misma. Las que no dicen programa ni encabezan uno van en «sin programa». Sin
// `agrupar_iniciativas`, van todas juntas, sin grupos. Todo puro: lo usa la pantalla (proyectos.ts) y lo prueba
// npm run prueba:componentes («iniciativas»).

import type * as cli from '../../cli';
import { circulo } from '../../componentes/circulo';
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
        ...sueltas.length ? [{ clave: '', nombre: 'sin programa', hijas: [...sueltas].sort(orden) }] : [],
    ];
}

/** Cuántos programas hay (los grupos con nombre, sin «sin programa»). */
export const programas = (gs: readonly Grupo[]): number => gs.filter(g => g.clave).length;

/** El círculo de su peso, en su ranura: alto lleno, medio a medias, bajo un aro; sin peso, nada. */
export function marcaPeso(peso?: Peso): string {
    return peso ? `<span class="senal" title="${esc(`peso ${peso}`)}">${circulo({ tam: 'chico', lleno: LLENO_PESO[peso] })}</span>` : '';
}

/** Una fila: el peso, el nombre, quién la lleva, cómo va, lo próximo por decidir, cuántos pendientes y su ⋯. La que
 *  encabeza su grupo lleva además cuántas tiene; las de un grupo van corridas una celda. Lleva lo de las filas de los
 *  proyectos (`proy`, `proy-sel`, `data-valor`), así que se elige, se abre y cuenta sus pendientes igual. */
export function filaIniciativa(p: cli.JsonProyecto, campo: string,
    o: { sel?: string; pend?: number; grupo: string; cabeza?: number; hija?: boolean; voc?: Vocabulario }): string {
    const voc = o.voc ?? SIN_VOCABULARIO;
    const d = deIniciativa(p, campo, voc);
    const e = d.visto;
    // el estado: con vocabulario y sin otra fuente, un clic lo cambia (`ini-estado`, en vez de elegir la fila)
    const estado = `<span class="estado-p ini-estado${e.cambia ? ' cambia' : ''}${e.fuera ? ' fuera' : ''}"`
        + (e.cambia ? ` data-accion="ini-estado" data-valor="${esc(p.ruta)}"` : '')
        + ` data-estado="${esc(e.valor)}"${e.clase ? ` data-clase="${e.clase}"` : ''} title="${esc(ayudaEstado(e, voc))}">${htmlEstado(e, voc)}</span>`;
    const fuente = `<span class="ini-fuente" title="${esc(e.fuente ? `su estado lo manda ${e.fuente}: se cambia allá` : '')}">${e.fuente ? `fuente: ${esc(e.fuente)}` : ''}</span>`;
    const texto = normalizar(`${p.nombre} ${p.ruta} ${d.dueno} ${d.estado} ${e.escrito} ${e.fuente} ${d.proxima} ${d.grupo} ${p.area ?? ''}`);
    const clases = ['fila', 'clic', 'proy', 'ini', ...p.ruta === o.sel ? ['sel'] : [], ...o.cabeza !== undefined ? ['ini-cabeza'] : [], ...o.hija ? ['ini-hija'] : []];
    const n = o.cabeza ? `<span class="ini-n" title="${o.cabeza} en este programa">${o.cabeza}</span>` : '';
    return `<div class="${clases.join(' ')}" data-accion="proy-sel" data-valor="${esc(p.ruta)}" data-grupo="${esc(o.grupo)}"`
        + ` data-unidad="${esc(p.area || 'sin área')}" data-pend="${o.pend || ''}" data-texto="${esc(texto)}"`
        + ` title="${esc(`${p.ruta}${d.programa && o.cabeza === undefined ? `\nprograma: ${d.programa}` : ''}${p.hilo ? `\nhilo: ${p.hilo}${p.vivo ? '' : ' (dormido)'}` : ''}`)}">`
        + `<span class="at">${marcaPeso(d.peso)}</span><span class="que"><span class="ini-nombre">${esc(p.nombre)}</span>${n}</span>`
        // en el teléfono, lo que sigue al salto va en una segunda línea (proyectos.css)
        + '<span class="ini-salto"></span>'
        + `<span class="dueno-i" title="${esc(d.dueno ? `dueño: ${d.dueno}` : 'sin dueño')}">${esc(d.dueno)}</span>`
        + estado + fuente
        + `<span class="prox-i" title="${esc(d.proxima ? `próxima decisión: ${d.proxima}` : 'sin próxima decisión')}">${esc(d.proxima)}</span>`
        + `<span class="tareas-p" title="pendientes: sus tareas y las casillas de su documento">${o.pend || ''}</span>`
        + `<span class="menu-fila menu-col" data-accion="proy-menu" data-valor="${esc(p.ruta)}" title="acciones de esta iniciativa">${I.menu}</span></div>`;
}

/** La sección entera: su cabecera (en la lista con los proyectos; un clic la deja sola), los nombres de sus columnas y
 *  cada grupo: la que lo encabeza (o su nombre, si no hay una) y las suyas. `solo`: es lo único que se ve (sin su
 *  cabecera: la barra dice «iniciativas»). */
export function htmlIniciativas(lista: readonly cli.JsonProyecto[], campo: string,
    o: { sel?: string; cuentas?: ReadonlyMap<string, number>; solo?: boolean; voc?: Vocabulario } = {}): string {
    if (!lista.length) return '';
    const voc = o.voc ?? SIN_VOCABULARIO;
    const gs = agrupar(lista, campo);
    // el ancho del estado y de la fuente, el de lo más largo que muestran (con su círculo y su marca), para que la columna
    // calce en todas las filas sin quitarle al nombre más de lo que hace falta; la de la fuente, solo si alguna la tiene
    const vistos = lista.map(p => estadoDe(p, voc));
    const anchoEstado = Math.min(18, Math.max(8, ...vistos.map(e => (e.valor || 'sin estado').length + (e.valor ? 2 : 0) + (e.fuera ? 2 : 0))));
    const anchoFuente = Math.min(20, Math.max(0, ...vistos.map(e => (e.fuente ? `fuente: ${e.fuente}`.length : 0))));
    const h: string[] = [`<div id="iniciativas"${anchoFuente ? ' class="con-fuente"' : ''} style="--ini-estado: ${anchoEstado + 1}ch${anchoFuente ? `; --ini-fuente: ${anchoFuente + 1}ch` : ''}">`];
    if (!o.solo) {
        const ps = programas(gs);
        h.push(`<div class="fila proy-sec-cab ini-sec-cab clic" data-accion="proy-iniciativas" title="verlas solas, por ${campo ? 'programa' : 'nombre'}">`
            + `<span class="at"></span><span class="que">iniciativas <span class="proy-sec-n">${lista.length}</span>`
            + `${ps ? ` <span class="ini-programas">· ${ps} programa${ps === 1 ? '' : 's'}</span>` : ''}</span><span class="i">${I.adelante}</span></div>`);
    }
    h.push('<div class="fila proy-cab ini-cols"><span class="at"></span><span class="que">iniciativa</span><span class="dueno-i">dueño</span>'
        + `<span class="estado-p" title="${esc(voc.estados.length ? `estado: ${voc.estados.join(', ')}. Clic en uno: cambiarlo` : 'estado: el de su ficha')}">estado</span>`
        + '<span class="ini-fuente"></span><span class="prox-i">próxima decisión</span><span class="tareas-p">tareas</span><span class="menu-col"></span></div>');
    for (const g of gs) {
        if (g.cabeza) h.push(filaIniciativa(g.cabeza, campo, { sel: o.sel, pend: o.cuentas?.get(g.cabeza.ruta), grupo: g.clave, cabeza: g.hijas.length, voc }));
        else if (g.nombre) {
            h.push(`<div class="fila ini-grupo${g.clave ? '' : ' ini-sueltas'}" data-grupo="${esc(g.clave)}"`
                + ` title="${esc(g.clave ? `programa «${g.clave}»: ninguna iniciativa se llama así` : 'sin programa ni iniciativas que dependan de ellas')}">`
                + `<span class="at"></span><span class="que"><span class="ini-nombre">${esc(g.nombre)}</span><span class="ini-n">${g.hijas.length}</span></span></div>`);
        }
        for (const p of g.hijas) h.push(filaIniciativa(p, campo, { sel: o.sel, pend: o.cuentas?.get(p.ruta), grupo: g.clave, hija: !!g.clave, voc }));
    }
    h.push('</div>');
    return h.join('');
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
