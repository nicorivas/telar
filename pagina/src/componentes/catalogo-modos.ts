// El prototipo de los modos y los mundos en el catálogo (/componentes#modos-mundos; docs/propuestas/orden-por-modos.md, paso 2):
// dónde se cambian (tres variantes), qué cambia cada modo, Todo, el mundo y cómo se pasa de los modos de hoy. Con datos
// inventados (componentes/muestras-modos.ts). `#modos-mundos/ver/<variante>/<modo>/<escena>[/<más>]` dibuja la página entera al
// ancho de la ventana: así se sacan las capturas. Lo de adentro de Táctica es del prototipo de Táctica
// (componentes/tactica.ts); Estrategia abre en proyectos (su pantalla no se prototipa aquí): solo el marco y el cambio entre
// modos.
//
// El catálogo (catalogo.ts) le pasa lo suyo con `usar` (el tema elegido y cómo avisar) y le pregunta antes de
// pintar (`antesDePintar`: la barra de mentira con el mundo puesto), al montar cada barra (`prepararBarra`) y en cada clic
// (`atender`).

import { esc } from '../estilo';
import { modelo } from '../modelo';
import type { BarraHilos } from '../vistas/hilos';
import { I } from '../web/iconos';
import { item } from './item';
import { barra as barraPantalla } from './pantalla';
import { jornada } from './jornada';
import { tactica, barraTactica } from './tactica';
import { BARRA, DIA_EJEMPLO, JORNADA_EJEMPLO } from './muestras';
import { todo, barraTodo, type PropsTodo } from './todo';
import {
    MODOS, VARIANTES, SIN_CLASIFICAR, modo as modoDe, modosEnFila, mundoBoton, opcionesMundo, opcionesModo, decirMundo,
    decirTramo, tintaMundo, mundoAhora, leerTramo, cuando, type ClaveModo, type Variante, type MundoPuesto,
} from './modos-mundos';
import {
    MUNDOS, FUERA, ESCENAS, escena as escenaDe, puestoEn, barraEn, FILAS, FUENTES, HALLADAS, BUSCADO, TAREAS, DIA_PERSONAL, tacticaEn,
    type Escena,
} from './muestras-modos';

// ── lo que da el catálogo ──

export interface Contexto { tema: () => string; avisar: (t: string) => void }
let ctx: Contexto = { tema: () => 'telar', avisar: () => undefined };
export const usar = (c: Contexto): void => { ctx = c; };

/** Los anchos que se comparan: la columna de la derecha de un laptop de 1440 (la barra de hilos ocupa 22vw) y un teléfono. */
const ANCHO_LAPTOP = 1120, ANCHO_TELEFONO = 412;
/** La que se eligió (17-nov): la banda bajo la cabecera. Las páginas de las otras secciones se dibujan con ella. */
const ELEGIDA: Variante = 'b';

// ── una página: el modo, el mundo (su escena) y lo que se ve ──

/** Lo que pide la dirección para la página entera: #modos-mundos/ver/<variante>/<modo>/<escena>[/<más>]. */
export interface Ruta { variante: Variante; modo: ClaveModo; escena: string; mas: string }
export function entera(): Ruta | null {
    const m = /^#modos-mundos\/ver\/([abc])\/([a-z]+)\/([a-z-]+)(?:\/([a-z]+))?/.exec(decodeURIComponent(location.hash));
    if (!m || !MODOS.some(x => x.clave === m[2])) return null;
    return { variante: m[1] as Variante, modo: m[2] as ClaveModo, escena: m[3], mas: m[4] ?? '' };
}
const direccion = (r: Ruta) => `#modos-mundos/ver/${r.variante}/${r.modo}/${r.escena}${r.mas ? `/${r.mas}` : ''}`;

interface Vista { r: Ruta; e: Escena; puesto: MundoPuesto; tel: boolean }
const vistaDe = (r: Ruta, tel: boolean): Vista => {
    const e = escenaDe(r.escena);
    return { r, e, puesto: e.sinMundos ? { mundo: '', por: 'sin-horario' } : puestoEn(e), tel };
};
const mundosDe = (v: Vista) => (v.e.sinMundos ? [] : MUNDOS);
const minutos = (d: Date) => d.getHours() * 60 + d.getMinutes();

/** El día en la cabecera, del mundo puesto: el del trabajo (la jornada de las muestras), o la tarde de lo personal. */
function diaDe(v: Vista): string {
    const ahora = minutos(v.e.hora);
    if (v.puesto.mundo === 'personal') return jornada({ desde: 19 * 60, hasta: 23 * 60 + 30, ahora, tramos: DIA_PERSONAL });
    return jornada({ ...JORNADA_EJEMPLO, ahora, tramos: DIA_EJEMPLO });
}

const logo = '<span class="logo"><span class="logo-t">t</span><span class="logo-resto">elar</span></span><span class="dim cab-corre">0.13.0</span>';
const botones = (mas = '') => `<div class="cab-der">${mas}<a class="config i" title="apps">${I.apps}</a><a class="config i" title="máquinas">${I.maquinas}</a>`
    + `<a class="config i" title="configuración">${I.config}</a></div>`;

/** Lo que dice la cabecera al medio: la máquina y, si se mira un hilo, cuál. */
const donde = (visto = '') => `<div class="cab-donde"><b class="cab-aqui">laptop</b>${visto ? `<span class="cab-icono">:</span><span class="cab-visto">${esc(visto)}</span>` : ''}</div>`;

/** El modo y el mundo en una sola marca (la cabecera de la variante C, y el teléfono): el ícono del modo en violeta y el
 *  nombre del mundo en su color. Un clic abre el menú de los modos. */
function marca(v: Vista): string {
    const m = modoDe(v.r.modo);
    const mu = MUNDOS.find(x => x.clave === v.puesto.mundo);
    return `<a class="modos-marca" data-accion="modos-menu" title="${esc(`${m.nombre}: ${m.que} · clic: otro modo`)}"><span class="i">${m.icono}</span>`
        + `<span class="txt"> ${esc(m.nombre)}</span></a>`
        + (mundosDe(v).length ? `<a class="mundo-boton solo-nombre${mu ? '' : ' ambos'}" data-accion="modos-mundo"${tintaMundo(mu)} title="${esc(decirMundo(v.puesto, MUNDOS, v.e.hora).ayuda)}">`
            + `<span class="mundo-nombre">${esc(mu?.nombre ?? 'ambos')}</span></a>` : '');
}

/** La cabecera de la página con los controles donde los pone cada variante; la línea de abajo, la de siempre. */
function cabecera(v: Vista, visto = ''): string {
    const mundos = mundosDe(v);
    const abre = `<header class="cabecera cat-cab modos-cab var-${v.r.variante}${v.tel && visto ? ' en-detalle' : ''}"><div class="cab-fila">`;
    const mundo = mundos.length ? mundoBoton(v.puesto, mundos, v.e.hora, 'cab-mundo') : '';
    const volver = `<a class="cab-volver"><span class="i">${I.atras}</span><span class="txt"> hilos</span></a>`;
    if (v.r.variante === 'a') {
        return `${abre}<div class="cab-izq">${logo}${volver}${modosEnFila(v.r.modo, { clase: 'cab-modos' })}</div>`
            + `${v.tel ? '' : donde(visto)}<div class="cab-jornada">${diaDe(v)}</div>${botones(mundo)}</div></header>`;
    }
    if (v.r.variante === 'b') {
        // la banda, adentro de la cabecera: su segundo nivel (como en la página, src/telar/web/indice.html)
        return `${abre}<div class="cab-izq">${logo}${volver}</div>${donde(visto)}<div class="cab-jornada">${diaDe(v)}</div>${botones()}</div>`
            + `${banda(v)}</header>`;
    }
    return `${abre}<div class="cab-izq">${logo}${volver}</div>${donde(visto)}<div class="cab-jornada">${diaDe(v)}</div>${botones(marca(v))}</div></header>`;
}

/** La banda de la variante B, el segundo nivel de la cabecera: los modos a la izquierda y el mundo a la derecha (su
 *  nombre, hasta cuándo; un clic, su menú). Las mismas clases que la de la página. */
function banda(v: Vista): string {
    const mundos = mundosDe(v);
    return `<div class="cab-banda">${modosEnFila(v.r.modo, { clase: 'banda-modos' })}`
        + `${mundos.length ? `<span class="banda-mundo">${mundoBoton(v.puesto, mundos, v.e.hora, 'banda-mundo-boton')}</span>` : ''}</div>`;
}

/** Arriba de la barra de hilos (la variante C): el mundo, en una fila, y los modos. */
function arribaDeLaBarra(v: Vista): string {
    const mundos = mundosDe(v);
    const mu = MUNDOS.find(x => x.clave === v.puesto.mundo);
    const d = decirMundo(v.puesto, mundos, v.e.hora);
    const filaMundo = mundos.length ? item({ accion: 'modos-mundo', clases: ['modos-fila-mundo'], ayuda: d.ayuda,
        inicio: [{ html: `<span class="mundo-raya"${tintaMundo(mu)}></span>` }],
        tituloHtml: `<span class="mundo-nombre${mu ? '' : ' ambos'}"${tintaMundo(mu)}>${esc(d.nombre)}</span>`,
        sufijo: d.como ? [{ texto: `· ${d.como}`, tono: 'tenue' }] : [], fijas: [{ accion: 'modos-mundo', icono: I.abierto, ayuda: 'elegir otro mundo' }] }) : '';
    return `<div class="modos-arriba">${filaMundo}${modosEnFila(v.r.modo, { clase: 'barra-modos' })}</div>`;
}

/** Lo que el mundo deja afuera de la barra: una fila al final de HILOS, plegada, que lo cuenta (y lo abre). */
function loDeOtros(v: Vista): string {
    const { fuera } = barraEn(v.puesto.mundo);
    const otros = MUNDOS.filter(m => m.clave !== v.puesto.mundo);
    if (!fuera || !v.puesto.mundo) return '';
    return `<div class="modos-otros">${item({ variante: 'submenu', accion: 'modos-otros', ayuda: 'los hilos de los otros mundos: abrirlos aquí, sin cambiar el mundo',
        inicio: [null, null, { icono: I.plegado }], tituloHtml: `de <span class="mundo-nombre"${tintaMundo(otros[0])}>${esc(otros.length === 1 ? otros[0].nombre : 'otros mundos')}</span>`,
        sufijo: [{ texto: String(fuera), tono: 'tenue' }] })}</div>`;
}

/** Estrategia: abre en proyectos, la primera de sus filas (la pantalla «estrategia» se sacó el 19-nov-2026); aquí, su
 *  marco: la barra de proyectos y, apagado, lo que lleva cada una de sus pestañas. */
function cuerpoEstrategia(v: Vista): string {
    const secciones: [string, string][] = [
        ['proyectos', 'cada uno con su fase, lo que no cuadra y lo que viene; las iniciativas, por programa'],
        ['tablero', 'el del módulo: los números de la semana, enteros'],
        ['decisiones', 'la del módulo registro: las decisiones y las hipótesis por revisar'],
    ];
    const mu = MUNDOS.find(x => x.clave === v.puesto.mundo);
    return barraPantalla({ nombre: 'proyectos', color: 'verde', resumen: `${mu ? `${mu.nombre} · ` : ''}lo que se gestiona`,
        acciones: [{ accion: 'modos-nada', icono: I.releer, ayuda: 'volver a leer (r)' }] })
        + '<div>' + secciones.map(([n, que]) => `<section class="tac-bloque"><div class="tac-cab"><span class="tac-nombre">${esc(n)}</span></div>`
            + item({ apagada: true, inicio: [null], titulo: que, sufijo: [{ texto: '· su pestaña, la de siempre', tono: 'apagado' }] }) + '</section>').join('')
        + '</div>';
}

/** Lo que llena la columna de la derecha en cada modo. */
function cuerpo(v: Vista): string {
    if (v.r.modo === 'tactica') {
        const t = tacticaEn(v.puesto.mundo, v.e.hora);
        return barraPantalla(barraTactica(t)) + tactica(t);
    }
    if (v.r.modo === 'estrategia') return cuerpoEstrategia(v);
    const p = propsTodo(v);
    return barraPantalla(barraTodo(p)) + todo(p);
}

function propsTodo(v: Vista): PropsTodo {
    const base = { fuentes: FUENTES, mundos: mundosDe(v), puesto: v.puesto.mundo };
    if (v.r.mas === 'buscar') return { ...base, buscado: BUSCADO, halladas: HALLADAS };
    if (v.r.mas === 'tareas') return { ...base, abierta: { fuente: 'tareas', cosas: TAREAS.filter(x => !v.puesto.mundo || x.mundo === v.puesto.mundo || x.mundo === SIN_CLASIFICAR),
        total: FUENTES.find(f => f.clave === 'tareas')!.cuenta[v.puesto.mundo || 'trabajo'] + 3 } };
    return base;
}

/** Foco: solo la terminal, al centro, sin cabecera ni barra; arriba a la derecha, el modo y el mundo (vuelve al de antes). */
function paginaFoco(v: Vista): string {
    const mu = MUNDOS.find(x => x.clave === v.puesto.mundo);
    const lineas = [
        ['dim', '> arma el índice del informe con las tres primeras secciones'],
        ['', ''],
        ['ok', '● Leí el borrador y las notas de la reunión del lunes.'],
        ['', '  El índice queda así:'],
        ['', '    1. Lo que se vendió en noviembre, por sección'],
        ['', '    2. La vitrina: qué funcionó y qué no'],
        ['', '    3. La feria del libro: costos y lo que dejó'],
        ['', ''],
        ['ok', '● Escribí las tres secciones en informe/borrador.md (1.840 palabras).'],
        ['', ''],
        ['dim', '  ¿Sigo con las conclusiones o lo revisas primero?'],
    ];
    return `<div class="muestra modos-pagina modos-foco${v.tel ? ' angosto' : ''}" data-tema="${ctx.tema()}" data-densidad="${v.tel ? 'amplia' : 'compacta'}"${tintaMundo(mu)}>`
        + `<a class="modos-salir" data-accion="modos-modo" data-id="tactica" title="salir de foco (⌥⇧F): vuelve a táctica"><span class="i">${I.foco}</span>`
        + `${mu ? ` <span class="mundo-nombre">${esc(mu.nombre)}</span>` : ''}</a>`
        + `<div class="modos-terminal">${lineas.map(([c, t]) => `<div class="${c}">${esc(t) || '&nbsp;'}</div>`).join('')}<div class="cursor">&gt; <span>█</span></div></div></div>`;
}

/** La página entera, a lo ancho de la ventana (para las capturas). En un laptop, la cabecera, la barra de hilos (la de
 *  verdad, con el mundo puesto) y la columna del modo; en un teléfono, el detalle (o la lista, con `/lista`). */
export function pagina(r: Ruta): string {
    const tel = window.innerWidth <= 700;
    const v = vistaDe(r, tel);
    if (r.modo === 'foco') return paginaFoco(v);
    const lista = tel && r.mas === 'lista';
    const barra = `<div class="muestra barra-de-muestra modos-barra" data-modos="${r.modo}"><div class="lista-de-muestra"></div>${loDeOtros(v)}</div>`;
    const conBarra = r.variante === 'c' ? `<div class="modos-con-barra">${arribaDeLaBarra(v)}${barra}</div>` : barra;
    const columna = `<div class="modos-columna">${cuerpo(v)}</div>`;
    const mitad = tel ? (lista ? conBarra : columna) : `${conBarra}${columna}`;
    return `<div class="muestra modos-pagina var-${r.variante}${tel ? ' angosto' : ''}" data-tema="${ctx.tema()}" data-densidad="${tel ? 'amplia' : 'compacta'}">`
        + cabecera(v)
        + `<div class="modos-cuerpo${tel ? ' uno' : ''}">${mitad}</div>`
        + '</div>';
}

// ── el modelo de la barra: los hilos del mundo puesto ──

/** Antes de pintar: la barra de mentira con el mundo de la página entera (o entera, en el catálogo). */
export function antesDePintar(): void {
    const r = entera();
    const b = barraEn(r ? vistaDe(r, false).puesto.mundo : '');
    modelo.hilos = r ? b.hilos : BARRA.hilos;
    modelo.secciones = r ? b.secciones : BARRA.secciones;
}

/** Una barra de una página de modos: las filas de DASHBOARD de su modo (la de su vista, marcada) y lo de las otras
 *  máquinas, con el mundo puesto. Devuelve false si la barra no es de aquí. */
export function prepararBarra(el: HTMLElement, b: BarraHilos): boolean {
    const de = el.closest<HTMLElement>('[data-modos]');
    const r = entera();
    if (!de || !r) return false;
    const m = de.dataset.modos as ClaveModo;
    b.pestanasDashboard = () => FILAS[m];
    b.dashboardActivo = true;
    b.pestanaActiva = FILAS[m][0]?.clave ?? '';
    b.otras = barraEn(vistaDe(r, false).puesto.mundo).otras;
    return true;
}

// ── las páginas del catálogo ──

const parrafo = (html: string) => `<p class="dim">${html}</p>`;

/** Una cabecera (y lo que la acompaña en su variante) en un marco de un ancho dado. */
function marcoCabecera(r: Ruta, px: number): string {
    const tel = px <= 700;
    const v = vistaDe(r, tel);
    const extra = r.variante === 'c' ? `<div class="modos-c-muestra">${arribaDeLaBarra(v)}</div>` : '';
    return `<div class="muestra modos-marco${tel ? ' angosto' : ''}" style="width: ${px}px" data-tema="${ctx.tema()}" data-densidad="${tel ? 'amplia' : 'compacta'}">`
        + `${cabecera(v)}${extra}</div>`;
}

/** El enlace a la página entera, para abrirla en una ventana de ese ancho. */
const enlace = (r: Ruta, texto = 'pantalla completa') => `<a href="${direccion(r)}" target="_blank" title="la página entera: abrirla en una ventana de 1440 o de 412 px de ancho">${esc(texto)}</a>`;

function figura(r: Ruta, px: number, nombre: string): string {
    return `<figure class="modos-fig"><figcaption class="dim">${esc(nombre)} · ${px}px · ${enlace(r)}</figcaption>${marcoCabecera(r, px)}</figure>`;
}

export function seccionControles(): string {
    const h = ['<section class="cat-modos">',
        parrafo('<b>Elegida: B</b>, la banda bajo la cabecera (17-nov), y así está en la página. La página tiene dos ejes que se combinan (<code>docs/propuestas/orden-por-modos.md</code>, paso 2; '
            + '<code>componentes/modos-mundos.ts</code>, <code>media/css/modos.css</code>). <b>El modo</b> es una actitud: táctica (decidir y hacer, la de '
            + 'partida), estrategia (mirar con calma), foco (solo la terminal) y todo (ver y buscar todo, nunca la de partida). <b>El mundo</b> es una parte '
            + 'de la vida (<code>[mundos]</code>): trabajo, personal o ambos; cambia solo con su horario y a mano, y filtra la página entera.'),
        parrafo('Los modos se distinguen por su ícono, y el puesto va en violeta (como la vista que se ve en la barra de una pantalla): un modo es una '
            + 'forma de mirar la página. El mundo se distingue por su color: su nombre va en él (la línea bajo la cabecera, la de siempre). Táctica lleva el único número '
            + 'de la página (cuántas decisiones esperan) junto a su ícono cuando no es la que se ve. Los tres lugares que se miraron; con el día inventado, '
            + 'martes 11:45, en táctica y en el mundo del trabajo (por su horario). Un clic en un modo o en el mundo, en «pantalla completa», los cambia.')];
    for (const vv of VARIANTES) {
        const r: Ruta = { variante: vv.clave, modo: 'tactica', escena: 'trabajo', mas: '' };
        h.push(`<h3 class="cat-tac-h">${esc(vv.nombre)}${vv.clave === ELEGIDA ? ' <span class="cat-tac-reco">· la elegida</span>' : ''}</h3>`,
            parrafo(esc(vv.que)),
            `<div class="modos-figs">${figura(r, ANCHO_LAPTOP + 320, 'laptop')}${figura(r, ANCHO_TELEFONO, 'teléfono')}`
            + `${vv.clave === 'c' ? figura({ ...r, mas: 'lista' }, ANCHO_TELEFONO, 'teléfono, en la lista') : ''}</div>`,
            `<p class="dim">las páginas enteras: ${MODOS.map(m => enlace({ ...r, modo: m.clave }, m.nombre)).join(' · ')}${vv.clave === 'c' ? ` · ${enlace({ ...r, mas: 'lista' }, 'la lista (teléfono)')}` : ''}</p>`);
    }
    h.push('<h3 class="cat-tac-h">las teclas</h3>',
        '<div class="modos-tabla dos"><b>tecla</b><b>qué hace</b>'
        + MODOS.map(m => `<div><kbd>⌥⇧${m.tecla}</kbd></div><div>${esc(m.nombre)}: ${esc(m.que)}</div>`).join('')
        + '<div><kbd>⌥⇧F</kbd></div><div>foco, y de vuelta al de antes (como hoy)</div>'
        + '<div><kbd>⌥⇧M</kbd></div><div>el modo siguiente (como hoy)</div>'
        + '<div><kbd>⌥⇧0</kbd></div><div>el mundo siguiente: trabajo → personal → ambos → de vuelta al horario</div>'
        + '<div><kbd>⌘K</kbd></div><div>el buscador de siempre (ir a una cosa); su última fila, «buscar … en todo», abre Todo con lo escrito</div></div>',
        parrafo('En el teléfono no hay teclas: en A, los cuatro íconos siempre a la vista arriba (el puesto, con su nombre); en B, igual pero en la '
            + 'banda, una línea bajo la cabecera; en C, arriba de la lista. El mundo es una palabra (cortada si no cabe), y un toque abre su menú.'), '</section>');
    return h.join('');
}

/** Qué cambia cada modo: una fila por cosa que cambia. */
const CAMBIA: [string, Record<ClaveModo, string>][] = [
    ['lo que se ve', { tactica: 'Táctica: Ahora, Decidir y Hacer (su prototipo)', estrategia: 'proyectos, la primera de sus pestañas', foco: 'la terminal del hilo que se mira, sola', todo: 'el buscador sobre todo junto y las fuentes, cada una entera a un clic' }],
    ['DASHBOARD', { tactica: 'táctica · día', estrategia: 'proyectos · tablero · decisiones (las de los módulos, si están); los encargos van a AGENTES y la deuda a tareas', foco: '— (no hay barra)', todo: 'todo · te esperan · tareas · casillas · correo · mensajes · lecturas · calendario · proyectos · periódicos · los de los módulos' }],
    ['la barra de hilos', { tactica: 'abierta: AGENTES y HILOS del mundo', estrategia: 'abierta, con HILOS plegada: se mira, no se atiende', foco: 'oculta', todo: 'abierta, con el archivo abierto' }],
    ['la terminal', { tactica: 'la de [terminal]', estrategia: 'la de [terminal]', foco: '110 columnas, al centro, sin fondo', todo: 'la de [terminal]' }],
    ['los avisos', { tactica: 'todos', estrategia: 'urgentes', foco: 'urgentes', todo: 'todos' }],
    ['el número', { tactica: 'cuántas decisiones esperan, en su barra (el único de la página)', estrategia: 'ninguno', foco: 'ninguno', todo: 'ninguno; las cuentas de Todo son tenues' }],
    ['la cabecera', { tactica: 'con el día en una línea', estrategia: 'con el día en una línea', foco: 'oculta: arriba a la derecha, el modo y el mundo (salir)', todo: 'con el día en una línea' }],
    ['al abrir la página', { tactica: 'la de partida', estrategia: 'sigue en estrategia', foco: 'sigue en foco', todo: 'vuelve a táctica: Todo nunca es la de partida' }],
];

export function seccionCambia(): string {
    const r = (m: ClaveModo, e = 'trabajo', mas = ''): Ruta => ({ variante: ELEGIDA, modo: m, escena: e, mas });
    return '<section class="cat-modos">'
        + parrafo('Cada modo dice lo que se ve a la derecha, qué filas tiene DASHBOARD, cómo va la barra de hilos, la terminal y los avisos: lo mismo que '
            + 'decía un modo de hoy (<code>telar.modos</code>, sus ajustes), más su contenido. Los ajustes siguen siendo de la configuración '
            + '(<code>[modos.tactica]</code>, <code>[modos.estrategia]</code>…): cambiar la barra o la terminal de un modo es lo de siempre. El mundo es aparte '
            + 'y vale en todos: filtra la barra (los hilos y los agentes de los otros mundos se cuentan en una fila plegada al final de HILOS), el número, '
            + 'las listas y el día.')
        + `<div class="modos-tabla cinco"><b></b>${MODOS.map(m => `<b><span class="i">${m.icono}</span> ${esc(m.nombre)}</b>`).join('')}`
        + CAMBIA.map(([que, por]) => `<div class="dim">${esc(que)}</div>${MODOS.map(m => `<div>${esc(por[m.clave])}</div>`).join('')}`).join('')
        + '</div>'
        + `<p class="dim">las páginas enteras, en el trabajo: ${MODOS.map(m => enlace(r(m.clave), m.nombre)).join(' · ')}; `
        + `en lo personal: ${MODOS.map(m => enlace(r(m.clave, 'noche'), m.nombre)).join(' · ')}; con ambos: ${enlace(r('tactica', 'ambos'), 'táctica')}</p>`
        + '</section>';
}

/** Todo en un marco: su pantalla con el mundo puesto. */
function marcoTodo(mas: string, px: number, e = 'trabajo'): string {
    const tel = px <= 700;
    const v = vistaDe({ variante: ELEGIDA, modo: 'todo', escena: e, mas }, tel);
    const p = propsTodo(v);
    return `<div class="muestra modos-marco-todo${tel ? ' angosto' : ''}" style="width: ${px}px" data-tema="${ctx.tema()}" data-densidad="${tel ? 'amplia' : 'compacta'}">`
        + `${barraPantalla(barraTodo(p))}${todo(p)}</div>`;
}

export function seccionTodo(): string {
    const estados: [string, string, string][] = [
        ['', 'sin buscar', 'las fuentes, cada una con lo que tiene en el mundo puesto y, a la derecha, lo que queda en el otro (en su color). Un clic la abre entera'],
        ['buscar', 'buscando «vitrina»', 'lo hallado del mundo puesto, por fuente (hasta 4 de cada una; «+N más» abre la fuente con lo buscado); arriba, cuántas de cada fuente, para quedarse con una; y al final, lo de los otros mundos: el mundo ordena, no esconde. Lo sin clasificar va con su marca'],
        ['tareas', 'una fuente entera', 'las tareas, todas: sin filtros ni topes, con la deuda y lo que no tiene fecha; lo hecho, al final y tenue. «‹» vuelve a Todo'],
    ];
    const h = ['<section class="cat-modos">',
        parrafo('<b>Todo</b> (<code>componentes/todo.ts</code>; el paso 5 de la propuesta) es ver y buscar todo, sin filtros ni topes: todas las tareas, '
            + 'todos los correos, todas las esperas, con un buscador sobre todo junto. Nunca es la vista de partida, pero siempre está a un paso: su ícono '
            + 'en la banda bajo la cabecera, <kbd>⌥⇧4</kbd>, «ver todo» y «+N más» en Táctica, y <kbd>⌘K</kbd>, que va a una cosa (su última fila abre Todo con lo escrito).'),
        parrafo('Con un mundo puesto, Todo cuenta lo de los otros en vez de esconderlo: la persona pidió poder ver todo y buscar sobre todo, y un resultado '
            + 'que falta porque es de otro mundo se pierde sin que se note. Falta el buscador de verdad: una búsqueda en el servidor sobre todas las fuentes '
            + '(o, de a poco, en la página sobre lo que ya lee).')];
    for (const [mas, nombre, nota] of estados) {
        const r: Ruta = { variante: ELEGIDA, modo: 'todo', escena: 'trabajo', mas };
        h.push(`<h3 class="cat-tac-h">${esc(nombre)}</h3>`, parrafo(esc(nota)),
            `<div class="modos-figs"><figure class="modos-fig"><figcaption class="dim">laptop · ${ANCHO_LAPTOP}px · ${enlace(r)}</figcaption>${marcoTodo(mas, ANCHO_LAPTOP)}</figure>`
            + `<figure class="modos-fig"><figcaption class="dim">teléfono · ${ANCHO_TELEFONO}px</figcaption>${marcoTodo(mas, ANCHO_TELEFONO)}</figure></div>`);
    }
    h.push('</section>');
    return h.join('');
}

/** A qué hora, qué mundo: lo que dice `mundoAhora` en la semana de las muestras. */
function tablaHorario(): string {
    const d = (dia: number, hh: number, mm = 0) => new Date(2026, 10, 16 + dia, hh, mm);
    const filas: [string, Date, { mundo: string; desde: Date } | undefined][] = [
        ['martes 8:30', d(1, 8, 30), undefined], ['martes 11:45', d(1, 11, 45), undefined], ['martes 11:45, personal a mano a las 11:40', d(1, 11, 45), { mundo: 'personal', desde: d(1, 11, 40) }],
        ['martes 19:10, el de a mano ya venció', d(1, 19, 10), { mundo: 'personal', desde: d(1, 11, 40) }], ['martes 20:30', d(1, 20, 30), undefined],
        ['viernes 18:00, ambos a mano', d(4, 18), { mundo: '', desde: d(4, 17, 50) }], ['sábado 11:00', d(5, 11), undefined],
    ];
    const nombre = (k: string | undefined) => (k === undefined ? '—' : MUNDOS.find(m => m.clave === k)?.nombre ?? 'ambos');
    const POR = { horario: 'su horario', fuera: 'fuera de todo horario', 'a-mano': 'a mano', 'sin-horario': 'no hay horarios' };
    return '<div class="modos-tabla cinco"><b>a qué hora</b><b>el mundo</b><b>por</b><b>hasta</b><b>después</b>'
        + filas.map(([que, f, aMano]) => {
            const p = mundoAhora(MUNDOS, f, { fuera: FUERA, aMano });
            const mu = MUNDOS.find(m => m.clave === p.mundo);
            return `<div>${esc(que)}</div><div><span class="mundo-nombre${mu ? '' : ' ambos'}"${tintaMundo(mu)}>${esc(nombre(p.mundo))}</span></div>`
                + `<div class="dim">${esc(POR[p.por])}</div><div>${p.hasta ? esc(cuando(p.hasta, f)) : '—'}</div><div>${esc(nombre(p.luego))}</div>`;
        }).join('') + '</div>';
}

export function seccionMundo(): string {
    const h = ['<section class="cat-modos">',
        parrafo('<b>El mundo</b> (<code>[mundos]</code>, ya en los datos: cada espera y cada tarea traen el suyo) filtra la página entera: la barra (hilos y '
            + 'agentes), el número de Táctica, las listas y el día. Se ve en una palabra en su color; con ambos, la palabra va en el '
            + 'color del texto. La línea bajo la cabecera es la de siempre, con o sin mundo. Las escenas, en la banda (la variante B), con el día inventado:')];
    for (const e of ESCENAS) {
        const r: Ruta = { variante: ELEGIDA, modo: 'tactica', escena: e.clave, mas: '' };
        h.push(`<h3 class="cat-tac-h">${esc(e.nombre)}</h3>`, parrafo(esc(e.nota).replace(/`([^`]+)`/g, '<code>$1</code>')),
            `<div class="modos-figs">${figura(r, ANCHO_LAPTOP + 320, 'laptop')}${figura(r, ANCHO_TELEFONO, 'teléfono')}</div>`);
    }
    const ejemplo = `[mundos]
fuera = "personal"                       # el mundo fuera de todo horario; sin esto, ambos

[mundos.trabajo]
areas = ["equipo", "cliente"]
rutas = ["empresa/", "clientes/"]
horario = "lun-vie 9:00-19:00"           # o una lista: ["lun-vie 9:00-13:00", "lun-vie 14:00-19:00"]
color = "cian"                           # opcional: una tinta del tema; sin esto, una por orden

[mundos.personal]
areas = ["personal"]
rutas = ["casa/"]`;
    h.push('<h3 class="cat-tac-h">el menú del mundo</h3>',
        parrafo('Un clic en el mundo lo abre (en «pantalla completa», de verdad; aquí: '
            + '<a data-accion="modos-mundo" data-escena="trabajo">por horario</a> · <a data-accion="modos-mundo" data-escena="a-mano">a mano</a>): cada mundo con su '
            + 'horario, ambos, «volver al horario» si se eligió a mano, cuántas cosas no son de ningún mundo y «editar los mundos…». En el teléfono, lo mismo.'),
        '<h3 class="cat-tac-h">el horario</h3>',
        parrafo('Se declara en cada mundo, con días y horas; fuera de todo horario rige el de <code>fuera</code> (o ambos). Cambiar a mano dura hasta el '
            + 'próximo cambio del horario: a las 19:00 vuelve solo, y la cabecera lo dice («a mano, hasta las 19:00»). Así un cambio a mano no se queda puesto '
            + 'sin querer. El cálculo es una función pura (<code>mundoAhora</code>, con su prueba), con la hora de esta máquina:'),
        `<pre class="modos-config">${esc(ejemplo)}</pre>`, tablaHorario(),
        parrafo(`Tramos que entiende: ${['lun-vie 9:00-19:00', 'sáb-dom', 'lun,mié,vie 8:30-12', '20:00-23:00', 'vie 22:00-2:00'].map(t => `«${esc(t)}» → ${esc(decirTramo(leerTramo(t)))}`).join(' · ')}.`),
        '<h3 class="cat-tac-h">lo sin clasificar</h3>',
        parrafo('Lo que no calza en ningún mundo (ni por su área ni por su carpeta) <b>se ve en todos</b>, con su marca: esconderlo sería perder lo que '
            + 'espera sin que se note. El menú del mundo dice cuántas cosas hay así, y «editar los mundos…» lleva a declararlas. En la barra, el hilo sin '
            + 'clasificar de las muestras («Investigación sobre la memoria de los ríos del sur») se ve en trabajo y en personal.'),
        '</section>');
    return h.join('');
}

/** Cómo se pasa de los modos de hoy: lo que se lee igual, lo que cambia de lugar. */
const MIGRA: [string, string][] = [
    ['«estándar» (el de fábrica)', 'es táctica: <code>[modos.estandar]</code> se lee como <code>[modos.tactica]</code>, y lo que este navegador tenía puesto («telar.modo»: estandar) pasa a táctica'],
    ['«foco»', 'sigue igual: <code>[modos.foco]</code>, ⌥⇧F y el ◧ de salir (que ahora dice también el mundo)'],
    ['un modo propio con <code>etiquetas</code>', 'su filtro es un mundo: si hay un <code>[mundos.&lt;etiqueta&gt;]</code>, ponerlo pone táctica con ese mundo; si no, sigue filtrando los hilos por etiqueta, como hoy, y ⚙ modos ofrece pasarlo a <code>[mundos]</code>'],
    ['las etiquetas de un hilo', 'siguen (<code>telar hilo etiquetas</code>), y un mundo puede declararlas (<code>[mundos.trabajo] etiquetas = ["trabajo"]</code>): un hilo con esa etiqueta es de ese mundo aunque su carpeta no lo diga. Así lo que hoy está etiquetado a mano no se pierde'],
    ['<code>sin_etiqueta</code>', 'lo que dice es lo de lo sin clasificar: «se-ven» es la regla de siempre (se ve en todos los mundos); «no-se-ven» deja de tener efecto, y ⚙ modos lo dice'],
    ['un modo propio sin <code>etiquetas</code>', 'sigue en el selector, bajo los cuatro, como una variante: dice sobre cuál se arma (<code>base = "tactica"</code>; sin eso, táctica) y sus ajustes'],
    ['<code>proyectos</code>, <code>negocios</code>', 'son de la pantalla de proyectos, la primera de estrategia (y en todo): se leen de <code>[modos.estrategia]</code> o del modo que los diga, como hoy'],
    ['⌥⇧M y el selector «◧»', '⌥⇧M pasa al siguiente de los cuatro (y los propios, después); el ◧ de la cabecera se va: los modos están a la vista'],
];

export function seccionMigracion(): string {
    const antes = `[modos.oficina]
nombre = "oficina"
etiquetas = "trabajo"
barra = "plegada"

[modos.casa]
etiquetas = "personal"`;
    const despues = `[mundos.trabajo]
rutas = ["empresa/"]
etiquetas = ["trabajo"]          # lo etiquetado a mano sigue siendo de trabajo
horario = "lun-vie 9:00-19:00"

[mundos.personal]
etiquetas = ["personal"]

[modos.tactica]
barra = "plegada"                # lo que «oficina» cambiaba de la disposición`;
    return '<section class="cat-modos">'
        + parrafo('Los modos de hoy (<code>[modos]</code>, <code>docs/propuestas/modos.md</code>) son un nombre con valores para la disposición, la terminal y los '
            + 'avisos, más un filtro de hilos por etiqueta. Los cuatro nuevos son lo mismo, con su contenido; el filtro pasa al mundo, que filtra la página '
            + 'entera y no solo los hilos. <b>La configuración vieja sigue valiendo</b>: nada se borra ni se reescribe solo.')
        + '<div class="modos-tabla dos"><b>lo de hoy</b><b>con modos y mundos</b>' + MIGRA.map(([a, b]) => `<div>${a}</div><div>${b}</div>`).join('') + '</div>'
        + '<div class="modos-figs"><figure class="modos-fig"><figcaption class="dim">antes</figcaption>'
        + `<pre class="modos-config">${esc(antes)}</pre></figure><figure class="modos-fig"><figcaption class="dim">después (lo que ⚙ modos propondría escribir)</figcaption>`
        + `<pre class="modos-config">${esc(despues)}</pre></figure></div>`
        + parrafo('En el selector, los modos propios que se migran se ven así mientras tanto: «oficina = táctica · trabajo». Lo que queda por decidir al '
            + 'implementarlo: si <code>[modos.estandar]</code> se renombra solo la primera vez que se guarda un modo, o se deja hasta que la persona lo cambie.')
        + '</section>';
}

// ── los clics ──

/** Lo que dice un clic que no hace nada de verdad. */
const DICE: Record<string, (id: string) => string> = {
    'todo-abrir': id => `abriría ${id} donde vive`,
    'todo-filtro': id => `dejaría solo ${id.split(':')[1]}`,
    'todo-releer': () => 'volvería a leer',
    'modos-otros': () => 'abriría aquí los hilos de los otros mundos, sin cambiar el mundo',
    'modos-nada': () => 'es el marco: el contenido es el de cada pestaña',
};

/** Un clic del prototipo: true si era suyo. En la página entera, cambiar de modo o de mundo la cambia. */
export function atender(el: HTMLElement): boolean {
    const accion = el.dataset.accion ?? '';
    if (!accion.startsWith('modos-') && !accion.startsWith('todo-')) return false;
    const id = el.dataset.valor ?? el.dataset.id ?? '';
    const r = entera();
    const ir = (cambio: Partial<Ruta>) => { if (r) location.hash = direccion({ ...r, ...cambio }); };
    if (accion === 'modos-modo') {
        if (!r) { ctx.avisar(`pondría el modo ${modoDe(id).nombre}`); return true; }
        // de Todo se sale sin lo buscado; al volver a Todo, sin buscar
        ir({ modo: id as ClaveModo, mas: '' });
        return true;
    }
    if (accion === 'modos-menu') {
        const p = el.getBoundingClientRect();
        void import('../web/interfaz').then(async m => {
            const ops = opcionesModo(r?.modo ?? 'tactica');
            const i = await m.menu(ops, { x: p.left, y: p.bottom + 4 }, { titulo: 'modo' });
            if (i !== undefined) { if (r) ir({ modo: ops[i].id as ClaveModo, mas: '' }); else ctx.avisar(`pondría el modo ${ops[i].label}`); }
        });
        return true;
    }
    if (accion === 'modos-mundo') {
        const escena = r?.escena ?? el.dataset.escena ?? 'trabajo';
        const e = escenaDe(escena);
        const puesto = e.sinMundos ? { mundo: '', por: 'sin-horario' as const } : puestoEn(e);
        const poner = (k: string) => {
            // de vuelta al horario a las 11:45 es trabajo; elegir a mano, la escena de a mano (o ambos)
            const destino = k === '__horario' || k === 'trabajo' ? 'trabajo' : k === 'personal' ? 'a-mano' : k === '' ? 'ambos' : '';
            if (k === '__editar') { ctx.avisar('abriría ⚙ mundos: qué es de cada uno y su horario'); return; }
            if (k === '__sin') { ctx.avisar('mostraría en Todo lo que no es de ningún mundo, para clasificarlo'); return; }
            if (r && destino) ir({ escena: destino }); else ctx.avisar(`pondría ${k ? k : 'ambos'}${k === '__horario' ? ' (el del horario)' : ''}`);
        };
        const p = el.getBoundingClientRect();
        void import('../web/interfaz').then(async m => {
            const ops = opcionesMundo(puesto, MUNDOS, 13, FUERA);
            const i = await m.menu(ops, { x: Math.min(p.left, innerWidth - 320), y: p.bottom + 4 }, { titulo: `mundo · ${decirMundo(puesto, MUNDOS, e.hora).como || 'sin horario'}` });
            if (i !== undefined) poner(ops[i].id);
        });
        return true;
    }
    if (accion === 'todo-fuente') {
        if (r && id === 'tareas') ir({ modo: 'todo', mas: 'tareas' });
        else ctx.avisar(`abriría ${FUENTES.find(f => f.clave === id)?.nombre ?? id}, entera`);
        return true;
    }
    if (accion === 'todo-volver') { if (r) ir({ mas: '' }); else ctx.avisar('volvería a Todo'); return true; }
    ctx.avisar(DICE[accion]?.(id) ?? `haría «${accion}»${id ? ` con ${id}` : ''}`);
    return true;
}

/** En la página entera, las teclas de los modos y del mundo (⌥⇧1–4, ⌥⇧F, ⌥⇧M, ⌥⇧0), como serían. */
export function tecla(e: KeyboardEvent): boolean {
    const r = entera();
    if (!r || !e.altKey || !e.shiftKey || e.metaKey || e.ctrlKey) return false;
    const n = /^Digit([0-4])$/.exec(e.code)?.[1];
    const i = MODOS.findIndex(m => m.clave === r.modo);
    let cambio: Partial<Ruta> | undefined;
    if (n === '0') {
        const ciclo = ['trabajo', 'a-mano', 'ambos'];
        cambio = { escena: ciclo[(ciclo.indexOf(r.escena) + 1) % ciclo.length] };
    } else if (n) cambio = { modo: MODOS[Number(n) - 1].clave, mas: '' };
    else if (e.code === 'KeyF') cambio = { modo: r.modo === 'foco' ? 'tactica' : 'foco', mas: '' };
    else if (e.code === 'KeyM') cambio = { modo: MODOS[(i + 1) % MODOS.length].clave, mas: '' };
    if (!cambio) return false;
    e.preventDefault();
    location.hash = direccion({ ...r, ...cambio });
    return true;
}

/** El título de la pestaña del navegador, para la página entera. */
export const titulo = (r: Ruta): string => `telar · modos · ${r.variante} · ${modoDe(r.modo).nombre} · ${escenaDe(r.escena).nombre}${r.mas ? ` · ${r.mas}` : ''}`;
