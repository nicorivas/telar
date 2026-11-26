// El catálogo de componentes (/componentes, src/telar/web/componentes.html): la vista de desarrollo de la página.
// Cada componente en todos sus estados, con cada tema y cada densidad al lado, para cambiar un token o una regla y
// verlo al tiro (con `scripts/dev.py` se recarga sola). A la izquierda, la lista de componentes en orden jerárquico
// (PAGINAS: de lo que se arma con nada a lo que se arma con todo); cada uno tiene su página, con las mismas pestañas
// en todos: «estados» (el componente, en cada estado) y «anatomía» (sus partes nombradas, y para qué está cada una).
// La dirección dice cuál: #item, #item/anatomia. Los que faltan hacer están en la lista, con su paso del orden de
// trabajo y dónde se usan hoy; una pestaña que falta sale apagada.
//
// Arriba se eligen los temas y las densidades que se comparan (una columna por cada par), el ancho (el de la barra, o
// el de un teléfono, donde no hay mouse) y si se dibujan los bordes de cada sección del ítem sobre las muestras. Lo
// que se aprieta aquí no hace nada: dice qué haría.

import { modelo } from '../modelo';
import { BarraHilos, type Guardado, type PestanaDashboard } from '../vistas/hilos';
import { esc } from '../estilo';
import { item, type Accion, type Item, type Pieza } from './item';
import { BARRA, HISTORIAS } from './muestras';
import { ATENCION_I, C, I, PRIO_I } from '../web/iconos';
import { MINIMO, TEMAS, TEXTOS, medir, todos as todosLosTemas, type Tema } from './temas';
import * as colores from '../web/colores';
import { DENSIDADES, type Densidad } from './densidades';
import { EJEMPLO, EJEMPLO_LISTA, EJEMPLO_TARJETA, SECCIONES, SECCIONES_LISTA, SECCIONES_TARJETA, type Parte, type Seccion } from './anatomia';
import { circulo, FIGURAS, MOVIMIENTOS, TAMANOS, type Circulo } from './circulo';
import { DERIVADAS, PARTES, RECTO, REDONDO, REGLAS, REGLAS_PARTIR, SIGNOS, type Trazo, type Valor, type Variable } from './gramatica';
import * as S from './senales';
import * as A from './acciones';
import { orden, type OpcionOrden } from './orden';
import { BORDES, barraBuscar } from './buscador';
import * as BU from './catalogo-buscador';
import { cabecera as cabeceraDeSeccion, herramientas, seccion, secciones, separador, submenu } from './seccion';
import { ventana, paleta, pieVentana } from './ventana';
import { APROBAR, contestable, estadoInicial, ventanaContestar, type EstadoContestar } from './contestar';
import { detallesDeMuestra, esperasDeMuestra } from './muestras-contestar';
import { filtros, type GrupoFiltro } from './filtros';
import { barra as barraPantalla } from './pantalla';
import { pestanas as filaPestanas } from './pestanas';
import { listaTarjetas, tarjeta, type Tarjeta } from './tarjeta';
import { casillas, type Casilla } from './casillas';
import { partes, type Parte as ParteDeTotal } from './partes';
import { jornada } from './jornada';
import { DIA_EJEMPLO, JORNADA_EJEMPLO, MOMENTOS } from './muestras';
import { DISPOSICIONES, TOPE_DECIDIR, TOPE_HACER, barraTactica, tactica, type Disposicion, type Tactica } from './tactica';
import { ESTADOS as ESTADOS_TACTICA, esperaDe, tablaUrgencia } from './muestras-tactica';
import * as MM from './catalogo-modos';
import * as AV from './catalogo-avisos';
import * as BT from './catalogo-botones';
import * as CM from './catalogo-mundos';
import * as CP from './catalogo-pestanas';
import * as CMS from './catalogo-mensaje';
import * as RU from './catalogo-rutinas';
import * as EQ from './catalogo-equipo';
import { alPintar as mensajesAlPintar } from '../web/mensaje';
import { atender as atenderPestanas, acomodarTodas } from '../web/pestanas';

interface Opciones { temas: string[]; densidades: string[]; ancho: 'barra' | 'telefono'; anatomia: boolean }
const CLAVE = 'telar.catalogo';
const ANCHOS = { barra: 300, telefono: 390 } as const;

function leer(): Opciones {
    const de = { temas: TEMAS.map(t => t.clave), densidades: ['compacta'], ancho: 'barra', anatomia: false } as Opciones;
    try { return { ...de, ...JSON.parse(localStorage.getItem(CLAVE) ?? '{}') as Partial<Opciones> }; } catch { return de; }
}
let op = leer();
const guardar = () => { try { localStorage.setItem(CLAVE, JSON.stringify(op)); } catch { /* sin almacén */ } };
/** Las columnas que se comparan: cada tema elegido con cada densidad elegida. */
interface Columna { tema: Tema; densidad: Densidad }
const columnasElegidas = (): Columna[] => todosLosTemas().filter(t => op.temas.includes(t.clave))
    .flatMap(tema => DENSIDADES.filter(d => op.densidades.includes(d.clave)).map(densidad => ({ tema, densidad })));
const nombreColumna = (c: Columna) => op.densidades.length > 1 || c.densidad.clave !== 'compacta' ? `${c.tema.nombre} · ${c.densidad.nombre}` : c.tema.nombre;

// ── los hilos de mentira, en el modelo que lee la barra ──
modelo.viva = true;
modelo.sesion = 'telar';
modelo.hilos = BARRA.hilos;
modelo.secciones = BARRA.secciones;
modelo.apps = BARRA.apps;
for (const [h, m] of BARRA.mudando) modelo.mudando.set(h, m);
for (const [h, s] of BARRA.saliendo) modelo.saliendo.set(h, s);

/** Lo que una barra recuerda (el orden de cada grupo, la columna de máquinas): aquí, solo mientras dura la página. */
function memoria(): Guardado {
    const m = new Map<string, unknown>();
    return { get: <T>(k: string) => m.get(k) as T | undefined, update: (k, v) => { m.set(k, v); return Promise.resolve(); } };
}

const barras: BarraHilos[] = [];

function cabecera(): string {
    const chip = (activo: boolean, datos: string, texto: string, ayuda = '') =>
        `<a class="chip${activo ? ' si' : ''}" ${datos}${ayuda ? ` title="${esc(ayuda)}"` : ''}>${esc(texto)}</a>`;
    return '<header class="cat-cabecera"><span><b>telar</b> <span class="dim">componentes</span></span>'
        + '<span class="cat-controles"><span class="dim">temas</span>'
        + todosLosTemas().map(t => chip(op.temas.includes(t.clave), `data-tema-sel="${t.clave}"`, t.nombre, t.descripcion)).join('')
        + '<span class="dim">densidad</span>'
        + DENSIDADES.map(d => chip(op.densidades.includes(d.clave), `data-dens-sel="${d.clave}"`, d.nombre, d.descripcion)).join('')
        + '<span class="dim">ancho</span>'
        + chip(op.ancho === 'barra', 'data-ancho="barra"', 'barra', `la barra de hilos en un computador: ${ANCHOS.barra}px`)
        + chip(op.ancho === 'telefono', 'data-ancho="telefono"', 'teléfono', `un teléfono (${ANCHOS.telefono}px): sin mouse, el ⋯ siempre a la vista (con densidad «auto», ahí va amplia)`)
        + chip(op.anatomia, 'data-anatomia', 'bordes', 'los bordes de cada sección del ítem sobre las muestras: inicio, texto, fin')
        + '</span></header>';
}

/** Una celda con un tema y una densidad: lo de adentro se ve con sus colores y sus medidas. */
const celda = (c: Columna, html: string, clase = '') =>
    `<div class="muestra barra-de-muestra${op.ancho === 'telefono' ? ' angosto' : ''}${clase ? ` ${clase}` : ''}" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${html}</div>`;

/** Las columnas de una grilla: el nombre de cada fila (si lleva) y un par tema · densidad en cada una. */
function columnas(conNombre = true): string {
    return `grid-template-columns: ${conNombre ? 'minmax(18ch, 24ch) ' : ''}repeat(${columnasElegidas().length}, ${ANCHOS[op.ancho]}px)`;
}
const titulos = (conNombre = true) => `${conNombre ? '<div></div>' : ''}${columnasElegidas()
    .map(c => `<div class="cat-tema" title="${esc(`${c.tema.descripcion} · ${c.densidad.descripcion}`)}">${esc(nombreColumna(c))}</div>`).join('')}`;

// los íconos, por su nombre en web/iconos.ts (en la letra de la página son un cuadro)
const NOMBRE_ICONO = new Map<string, string>([
    ...Object.entries(I).map(([k, v]) => [v, `I.${k}`] as [string, string]),
    ...Object.entries(PRIO_I).map(([k, v]) => [v, `PRIO_I[${k}]`] as [string, string]),
    ...Object.entries(ATENCION_I).map(([k, v]) => [v, `ATENCION_I.${k}`] as [string, string]),
]);

/** Las props de un ítem, una por línea, como se escribirían. */
function props(p: object): string {
    const json = (v: unknown) => JSON.stringify(v, (_, x) => typeof x === 'string' && NOMBRE_ICONO.has(x) ? `@@${NOMBRE_ICONO.get(x)}@@` : x)
        .replace(/"@@([^@]+)@@"/g, '$1').replace(/"(\w+)":/g, '$1: ').replace(/,(?=[{"\w])/g, ', ');
    return `{\n${Object.entries(p).map(([k, v]) => `  ${k}: ${json(v)},`).join('\n')}\n}`;
}

// ── la lámina: el componente grande, sus secciones arriba y cada pieza nombrada abajo ──

/** Las láminas que hay: qué dibuja cada una y con qué partes (componentes/anatomia.ts). */
const LAMINAS: Record<string, { dibujo: () => string; secciones: Seccion[]; funcion: string; apiladas?: boolean }> = {
    item: { dibujo: () => item(EJEMPLO), secciones: SECCIONES, funcion: 'item()' },
    // las de la tarjeta van una debajo de otra: su corchete, a la izquierda
    tarjeta: { dibujo: () => tarjeta(EJEMPLO_TARJETA), secciones: SECCIONES_TARJETA, funcion: 'tarjeta()', apiladas: true },
    // la sección no es un elemento sino varios hermanos: `lamina-entero` los junta, y es el contorno del que salen las guías
    seccion: { dibujo: () => `<div class="lamina-entero">${seccion({ ...EJEMPLO_LISTA,
        filas: () => item({ inicio: [S.prioridad(1), S.atencion('trabajando'), null], titulo: 'faro', meta: { texto: '3m' } })
            + submenu({ clave: 'archivo', titulo: 'archivo', cuenta: 4, ayuda: 'los archivados', abierta: false, filas: () => '' }) })}</div>`,
        secciones: SECCIONES_LISTA, funcion: 'seccion()', apiladas: true },
};

function seccionAnatomia(de = 'item'): string {
    const c = columnasElegidas()[0];
    const l = LAMINAS[de];
    return '<section>'
        + `<p class="dim">Sus partes, separadas: arriba las tres secciones; abajo cada pieza, con la prop de <code>${l.funcion}</code> que la pone y `
        + `para qué está. Con ${esc(nombreColumna(c))} (la primera columna elegida); lo que dice sale de <code>componentes/anatomia.ts</code>.</p>`
        + '<div class="lamina-marco">'
        + `<div class="muestra lamina ver-anatomia" data-de="${de}" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}"><div class="lamina-dibujo">${l.dibujo()}</div></div>`
        + '</div><div class="lamina-leyenda">'
        + l.secciones.map(s => `<div><b class="sec-${s.clave}">${esc(s.nombre)}</b> · ${esc(s.pregunta)}<p class="dim">${esc(s.intencion)}</p></div>`).join('')
        + '</div></section>';
}

type Caja = { x: number; y: number; w: number; h: number };

/** Dónde está una pieza en el dibujo, relativo a la lámina: la que dice `n`, o todas juntas. */
function caja(dibujo: HTMLElement, base: DOMRect, p: Pick<Parte, 'selector' | 'n' | 'todas'>): Caja | null {
    const els = [...dibujo.querySelectorAll<HTMLElement>(p.selector)];
    const rs = (p.todas ? els : els.slice(p.n ?? 0, (p.n ?? 0) + 1)).map(e => e.getBoundingClientRect());
    if (!rs.length) return null;
    const izq = Math.min(...rs.map(r => r.left)), der = Math.max(...rs.map(r => r.right));
    const arr = Math.min(...rs.map(r => r.top)), aba = Math.max(...rs.map(r => r.bottom));
    return { x: izq - base.left, y: arr - base.top, w: der - izq, h: aba - arr };
}

/** Las secciones, con un corchete arriba de cada una; las piezas, cada una con su guía hasta su rótulo, en escalera: la
 *  de más a la derecha en el primer renglón, así ninguna guía cruza un rótulo. */
function trazar(lamina: HTMLElement): void {
    for (const t of lamina.querySelectorAll('.lamina-traza')) t.remove();
    lamina.style.paddingBottom = '';
    lamina.style.width = '';
    const dibujo = lamina.querySelector<HTMLElement>('.lamina-dibujo');
    const fila = dibujo?.querySelector<HTMLElement>('.lamina-entero') ?? dibujo?.querySelector<HTMLElement>('.item');
    if (!dibujo || !fila) return;
    const l = LAMINAS[lamina.dataset.de ?? 'item'] ?? LAMINAS.item;
    const lh = parseFloat(getComputedStyle(lamina).lineHeight) || 17;
    // secciones una debajo de otra: el corchete a la izquierda, con su nombre al lado (hace falta lugar)
    const largo = Math.max(...l.secciones.map(s => s.nombre.length));
    lamina.style.paddingLeft = l.apiladas ? `max(${6 * lh}px, ${largo + 4}ch)` : '';
    const base = lamina.getBoundingClientRect();
    const trazos: string[] = [];
    const secciones = l.secciones;
    const borde = fila.getBoundingClientRect().left - base.left;  // el corchete de una apilada, afuera del componente
    for (const s of secciones) {
        const r = caja(dibujo, base, { selector: s.selector, todas: s.todas });
        if (!r) continue;
        trazos.push(l.apiladas
            ? `<div class="lamina-traza lamina-seccion apilada sec-${s.clave}" style="left: ${borde - .7 * lh}px; top: ${r.y}px; width: ${.4 * lh}px; height: ${r.h}px">`
                + `<span>${esc(s.nombre)}</span></div>`
            : `<div class="lamina-traza lamina-seccion sec-${s.clave}" style="left: ${r.x}px; top: ${r.y - .55 * lh}px; width: ${r.w}px; height: ${.4 * lh}px">`
                + `<span>${esc(s.nombre)}</span></div>`);
    }
    const piezas: { clave: string; p: Parte; r: Caja }[] = [];
    for (const s of secciones) for (const p of s.partes) {
        const r = caja(dibujo, base, p);
        if (r) piezas.push({ clave: s.clave, p, r });
    }
    piezas.sort((a, b) => (b.r.x + b.r.w / 2) - (a.r.x + a.r.w / 2));
    const bajo = fila.getBoundingClientRect().bottom - base.top;
    piezas.forEach(({ clave, p, r }, i) => {
        const x = r.x + r.w / 2, desde = r.y + r.h + 2, medio = bajo + (i + 1.2) * lh;
        trazos.push(`<div class="lamina-traza lamina-guia sec-${clave}" style="left: ${x}px; top: ${desde}px; height: ${medio - desde}px"></div>`
            + `<div class="lamina-traza lamina-rotulo" style="left: calc(${x}px + 1.5ch); top: ${medio - lh / 2}px">`
            + `<b class="sec-${clave}">${esc(p.nombre)}</b> <code>${esc(p.prop)}</code> <span class="dim">${esc(p.intencion)}</span></div>`);
    });
    lamina.insertAdjacentHTML('beforeend', trazos.join(''));
    lamina.style.paddingBottom = `${(piezas.length + 1.4) * lh}px`;
    const der = Math.max(base.width, ...[...lamina.querySelectorAll('.lamina-rotulo')].map(e => e.getBoundingClientRect().right - base.left));
    lamina.style.width = `${Math.ceil(der + 2 * lh)}px`;
}

const trazarLaminas = () => { for (const l of document.querySelectorAll<HTMLElement>('.lamina')) trazar(l); };

// ── el círculo: la familia, y cómo se mueve lo que está en curso ──

function seccionCirculo(): string {
    const fila = (nombre: string, nota: string, html: string, clase = 'circulos') => [
        `<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}${nota ? `<span class="dim"> · ${esc(nota)}</span>` : ''}</div>`,
        ...columnasElegidas().map(c => celda(c, html, clase)),
    ].join('');
    const varios = (cs: Circulo[], tono = '') => `<span class="cat-circulos${tono ? ` tono-${tono}` : ''}">${cs.map(circulo).join('')}</span>`;
    const llenados = [0, .25, .5, .75, 1];
    const TONO: Record<string, string> = { vacia: 'tenue', llena: 'exito', gira: 'remoto' };
    const h = ['<section>',
        '<p class="dim">La firma de los estados (<code>componentes/circulo.ts</code>, <code>media/css/circulo.css</code>): quieto, dice con '
        + 'su tamaño y cuánto está lleno; en curso, se mueve en su ranura de a cuartos y nada más se mueve (ni el texto, ni el color). '
        + 'Se vacía lo que se va, se llena lo que se completa, gira lo que va en camino.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`,
        '<div class="cat-grupo">quieto</div>',
        fila('tamaños', 'punto, chico, grande', varios(TAMANOS.map(tam => ({ tam })))),
        fila('llenado', 'grande: aro, ¼, ½, ¾, lleno', varios(llenados.map(lleno => ({ lleno })))),
        fila('llenado, chico', '', varios(llenados.map(lleno => ({ lleno, tam: 'chico' as const })))),
        '<div class="cat-grupo">en curso</div>',
        ...MOVIMIENTOS.map(m => fila(m.nombre, m.cuando, varios(TAMANOS.map(tam => ({ tam, mov: m.mov })), TONO[m.mov]))),
        '<div class="cat-grupo">figuras: lo que dicen, en fundamentos › composición</div>',
        fila('compuestas', FIGURAS.map(f => f.nombre).join(', '), varios(FIGURAS.map(f => ({ figura: f.figura })))),
        fila('satélite girando', 'va en camino', varios([{ figura: 'satelite', mov: 'gira' }], 'remoto')),
        '</div></section>',
    ];
    return h.join('');
}

// ── la gramática visual (componentes/gramatica.ts): lo cualitativo de fundamentos ──

/** Una muestra con el tema y la densidad de la primera columna elegida: adentro, los colores son los de ese tema. */
function enTema(html: string, clase = ''): string {
    const c = columnasElegidas()[0];
    return `<div class="muestra${clase ? ` ${clase}` : ''}" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${html}</div>`;
}
const trazo = (t: Trazo): string => `<span class="gr-trazo${t.tono ? ` tono-${t.tono}` : ''}">${circulo(t)}</span>`;
const dibujo = (ts: Trazo[]): string => `<span class="gr-dibujo">${ts.map(trazo).join('')}</span>`;
const vinetas = (xs: string[]): string => `<ul class="gr-sirve">${xs.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
const ficha = (v: Valor, demo: string): string =>
    `<div class="gr-ficha">${demo}<div><b>${esc(v.nombre)}</b> <span class="gr-dice">${esc(v.dice)}</span></div>${vinetas(v.sirve)}</div>`;
const intro = (html: string): string => `<p class="gr-intro">${html}</p>`;

/** Cada variable: su pregunta, qué es y sus valores, cada uno en su ficha. */
const variable = (x: Variable, demo: (v: Valor) => string): string =>
    `<h3 id="v-${x.clave}">${esc(x.nombre)} <span class="gr-pregunta">${esc(x.pregunta)}</span></h3><p>${esc(x.que)}</p>`
    + enTema(`<div class="gr-fichas">${x.valores.map(v => ficha(v, demo(v))).join('')}</div>`, 'gr-hoja');

/** Dónde vive cada concepto: su variable y la página que la muestra. */
const CONCEPTOS = new Map<string, { valor: Valor; variable: Variable; pagina: string }>([
    ...REDONDO.flatMap(x => x.valores.map(v => [v.clave, { valor: v, variable: x, pagina: 'redondo' }] as const)),
    ...RECTO.flatMap(x => x.valores.map(v => [v.clave, { valor: v, variable: x, pagina: 'recto' }] as const)),
]);

function seccionForma(): string {
    const tres = TAMANOS.map(tam => `<span class="gr-tam">${circulo({ tam })}<span class="dim">${tam}</span></span>`).join('');
    const juego = [
        item({ inicio: [S.prioridad(1), S.atencion('trabajando'), null], titulo: 'faro', meta: { texto: '3m' } }),
        item({ inicio: [S.prioridad(2), S.atencion('espera'), null], titulo: 'molino', meta: { texto: '1h' } }),
        item({ inicio: [S.prioridad(3), S.atencion('termino'), S.remoto()], titulo: 'cosecha', meta: { texto: '20m' } }),
        item({ inicio: [S.prioridad(0), null, null], titulo: 'cuaderno', meta: { texto: '12m' } }),
    ].join('');
    const tabla = (titulo: string, pagina: string, xs: Variable[]) => `<tr><th colspan="3">${titulo}</th></tr>`
        + xs.map(x => `<tr><td><a href="#${pagina}">${esc(x.nombre)}</a></td><td class="gr-pregunta">${esc(x.pregunta)}</td>`
            + `<td>${x.valores.map(v => `${esc(v.nombre)} <span class="gr-dice">${esc(v.dice)}</span>`).join(' · ')}</td></tr>`).join('');
    return '<section class="gr">'
        + intro('telar se dibuja con dos figuras: el <b>rectángulo</b> y el <b>círculo</b>. Lo recto ordena: dice dónde va cada cosa. '
            + 'Lo redondo dice cómo está. El diseño es el juego entre los dos.')
        + intro('Funciona como una lengua. Cada clase de signo hace un solo trabajo; lo redondo y lo recto se describen por sus '
            + '<b>variables</b>, y cada variable responde una sola pregunta, con valores que tienen un solo concepto cada uno. Lo que '
            + 'una vista necesita decir se arma combinándolos (las <a href="#derivadas">derivadas</a>): no se inventa un signo aparte.')
        + '<h3>las clases de signos</h3><table class="gr-tabla gr-signos"><tbody>'
        + SIGNOS.map(s => `<tr><td><b>${esc(s.nombre)}</b></td><td class="gr-dice">${esc(s.dice)}</td><td class="dim">${esc(s.ejemplo)}</td></tr>`).join('')
        + '</tbody></table>'
        + '<h3>las variables</h3><table class="gr-tabla gr-variables"><tbody>'
        + tabla('lo redondo', 'redondo', REDONDO) + tabla('lo recto', 'recto', RECTO)
        + '</tbody></table>'
        + '<div class="gr-par">'
        + `<div><h3>lo redondo, en tres tamaños</h3><p>Lo único curvo. Tres tamaños y ninguno más.</p>${enTema(`<div class="gr-tres">${tres}</div>`, 'gr-hoja')}</div>`
        + '<div><h3>el juego</h3><p>El círculo vive dentro de un rectángulo: cada ranura del ítem es un cuadro de ancho fijo con su círculo '
        + `adentro, y por eso los títulos de una lista empiezan todos en la misma columna.</p>${enTema(juego, 'ver-anatomia gr-juego')}</div>`
        + '</div>'
        + `<h3>las reglas</h3><ol class="gr-reglas">${REGLAS.map(r => `<li>${esc(r)}</li>`).join('')}</ol>`
        + '</section>';
}

function seccionRedondo(): string {
    return '<section class="gr">'
        + intro('Las seis variables del círculo. Un círculo tiene siempre un valor de cada una (aunque sea el de siempre: sola, quieto, '
            + 'pleno), y lo que dice es la suma: un hilo que terminó y no has visto es <i>dentro: algo lleno</i> · <i>grande</i> · '
            + '<i>de estado</i> · <i>pleno</i>.')
        + REDONDO.map(x => variable(x, v => dibujo(v.dibujo ?? []))).join('')
        + '</section>';
}

/** Cómo se ve cada valor de lo recto, y cada lugar de un círculo en él. */
function demoRecto(v: Valor): string {
    const t = (v.dibujo ?? []).map(trazo);
    switch (v.clave) {
        case 'en-ranura': return `<div class="gr-demo ver-anatomia">${item({ inicio: [S.atencion('trabajando')], titulo: 'faro', meta: { texto: '3m' } })}</div>`;
        case 'en-esquina': return `<div class="gr-demo"><span class="gr-esquina">mensajes<span class="gr-sobre">${t[0]}</span></span></div>`;
        case 'en-linea': return `<div class="gr-demo"><div class="gr-linea">${['abrió', 'trabajó', 'falta'].map((x, i) => `<div><span class="gr-sobre">${t[i]}</span>${x}</div>`).join('')}</div></div>`;
        case 'en-riel': return `<div class="gr-demo gr-rieles"><span class="gr-riel">${t[0]}</span><span class="dim">no</span><span class="gr-riel si">${t[1]}</span><span class="dim">sí</span></div>`;
    }
    return `<div class="gr-demo"><div class="gr-r gr-r-${v.clave}">${v.clave === 'ranura' ? '' : 'faro'}</div></div>`;
}

/** Una sección de la barra armada con las reglas de cómo se parte: la línea entre secciones, la banda de herramientas con
 *  su grupo de ordenar, las filas (una elegida) y la siguiente sección. */
function seccionPartida(): string {
    const nuevo = A.nuevo({ accion: 'nuevo' }, 'hilo nuevo');
    return '<div class="pt">'
        + `<div class="pt-seccion">${item({ variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo: 'hilos', sufijo: [{ texto: '14', tono: 'tenue' }], fijas: [nuevo] })}`
        + '<div class="pt-banda"><span class="pt-campo">buscar</span>'
        + `<span class="corte de-orden"></span><span class="pt-grupo" title="ordenar"><span class="i pt-padre pt-celda-c">${I.ordenar}</span>`
        + `<span class="i pt-celda-c">${I.urgencia}</span><span class="i pt-celda-c">${I.alfabetico}</span><span class="i pt-celda-c">${I.reloj}</span></span>`
        + '<span class="corte de-orden"></span>'
        + `<span class="i pt-celda-c">${I.maquinas}</span></div>`
        + item({ inicio: [S.prioridad(1), S.atencion('trabajando'), null], titulo: 'faro', meta: { texto: '3m' } })
        + item({ inicio: [S.prioridad(2), S.atencion('espera'), null], titulo: 'molino', meta: { texto: '1h' }, activa: true })
        + item({ inicio: [S.prioridad(0), S.atencion('termino'), S.remoto()], titulo: 'cosecha', meta: { texto: '20m' } })
        + item({ variante: 'submenu', inicio: [null, null, { icono: I.plegado }], titulo: 'archivo', sufijo: [{ texto: '2', tono: 'tenue' }] })
        + `</div><div class="pt-seccion">${item({ variante: 'cabecera', inicio: [{ icono: I.plegado }], titulo: 'equipo' })}</div>`
        + '</div>';
}

function seccionRecto(): string {
    const filas = PARTES.map(p => `<tr><td><b>${esc(p.nombre)}</b></td><td>${esc(p.es)}</td><td class="gr-dice-simple">${esc(p.marca)}</td><td class="dim">${esc(p.ejemplo)}</td></tr>`).join('');
    return '<section class="gr">'
        + intro('Las variables de lo recto: qué es un rectángulo, qué separa una línea según su lado, y de qué habla un círculo según '
            + 'dónde esté en ellos. Y abajo, cómo se parte un rectángulo en otros.')
        + RECTO.map(x => variable(x, demoRecto)).join('')
        + '<h3 id="partir">cómo se parte <span class="gr-pregunta">¿qué es esta parte respecto de las de al lado?</span></h3>'
        + '<p>Cada parte se marca según lo que es frente a sus vecinas y a la que la contiene, con un solo medio, y el fondo es '
        + 'escaso: en una lista lo lleva solo la selección. La barra de filtros de una lista, por ejemplo, es una <b>banda</b>: no '
        + 'lleva marca propia, la dicen su campo y sus íconos; adentro, el grupo de ordenar es un <b>grupo</b>, entre dos líneas '
        + 'cortas en su púrpura.</p>'
        + `<table class="gr-tabla gr-partes"><thead><tr><th>parte</th><th>qué es</th><th>cómo se marca</th><th>ejemplo</th></tr></thead><tbody>${filas}</tbody></table>`
        + `<div class="cat-grilla gr-partida" style="${columnas(false)}">${titulos(false)}${columnasElegidas().map(c => celda(c, seccionPartida(), 'pt-celda')).join('')}</div>`
        + `<ol class="gr-reglas">${REGLAS_PARTIR.map(r => `<li>${esc(r)}</li>`).join('')}</ol>`
        + '</section>';
}

function seccionDerivadas(): string {
    const concepto = (k: string) => {
        const c = CONCEPTOS.get(k);
        return c ? `<a href="#${c.pagina}" title="${esc(`${c.variable.nombre}: ${c.valor.dice}`)}">${esc(c.valor.nombre)}</a>` : esc(k);
    };
    const filas = (xs: typeof DERIVADAS) => xs.map(d => `<tr class="${d.explorar ? 'explorar' : ''}"><td>${esc(d.uso)}</td>`
        + `<td>${d.dibujo.length ? enTema(dibujo(d.dibujo), 'gr-celda') : ''}</td>`
        + `<td>${d.conceptos.map(concepto).join(' · ')}</td><td>${esc(d.por)}</td><td class="dim">${esc(d.antes)}</td></tr>`).join('');
    const cab = '<thead><tr><th>uso</th><th>señal</th><th>conceptos</th><th>por qué</th><th>antes</th></tr></thead>';
    return '<section class="gr">'
        + intro('Lo que telar dice, armado con los conceptos: para qué, con qué valores y por qué esos. Las de arriba ya están en la '
            + 'página (su código, en <code>componentes/senales.ts</code>: la <a href="#barra">barra de hilos</a>, el <a href="#item">ítem</a>, '
            + 'el dashboard); las de abajo, apagadas, son para cuando se hagan sus componentes.')
        + `<h3>en uso</h3><table class="gr-tabla">${cab}<tbody>${filas(DERIVADAS.filter(d => !d.explorar))}</tbody></table>`
        + `<h3>por hacer</h3><table class="gr-tabla">${cab}<tbody>${filas(DERIVADAS.filter(d => d.explorar))}</tbody></table>`
        + '</section>';
}

// ── contestar lo que te espera: la ventana de «te esperan» (componentes/contestar.ts) ──

function seccionContestar(): string {
    const M = esperasDeMuestra();
    const con = (clase: string, estado?: (s: EstadoContestar) => EstadoContestar, cambiar?: (e: typeof M.decide) => typeof M.decide) => {
        const c = contestable(cambiar ? cambiar(M[clase]) : M[clase]);
        const s = estadoInicial(c);
        return ventanaContestar(c, estado ? estado(s) : s);
    };
    const elegida = (id: string) => (s: EstadoContestar): EstadoContestar => ({ ...s, elegidas: [[id]] });
    const dos = (e: typeof M.decide) => ({ ...e, campos: { hilo: 'Vitrina', pregunta: 'p-2', preguntas: [
        { pregunta: '¿Qué foto va en la vitrina?', encabezado: 'Foto', varias: false, opciones: [{ etiqueta: 'La del árbol de libros' }, { etiqueta: 'La de la feria' }] },
        { pregunta: '¿Qué carteles le pongo?', encabezado: 'Carteles', varias: true, opciones: [{ etiqueta: 'Los precios' }, { etiqueta: 'Los autores' }] },
    ] } });
    // una tarea como queda cuando llega lo que se lee después de abrirla (la tarea entera, su proyecto, las otras del proyecto)
    const leida = (e: typeof M.decide) => {
        const d = detallesDeMuestra()[e.direccion];
        return d ? { ...e, campos: { ...e.campos, tarea: d.tarea, proyecto_ficha: d.proyecto, otras: d.otras } } : e;
    };
    const muestra: [string, string, string, string][] = [
        ['tarea, una decisión con historia', 'a la izquierda la ficha: de qué se trata (su contexto entero), cómo llegamos aquí (la creación y '
            + 'las últimas cuatro; lo del medio, plegado con su conteo; tú, el agente, lo que aplicó y una reunión, por ícono y color), qué '
            + 'está en juego y qué hay relacionado (enlaces que se abren en la página); a la derecha, lo que se pide y las opciones enteras',
            'decision', con('decision', undefined, leida)],
        ['tarea, para aprobar', 'lo que dejó hecho, en lo relacionado; la fecha dura y el peso, en lo que está en juego', 'aprobar', con('aprobar', undefined, leida)],
        ['tarea, sin contexto escrito', 'su título y «sin contexto escrito»; el proyecto sin estado escrito y sin otras tareas', 'sin-contexto',
            con('sin-contexto', undefined, leida)],
        ['tarea, leyendo', 'recién abierta: lo que trajo la espera, mientras se lee la tarea entera', '', con('decision')],
        ['decide', 'la pregunta de un módulo: a la izquierda su resumen entero, su porqué, su detalle y su archivo; a la derecha las '
            + 'opciones con la recomendada y lo que hará cada una, «Otra cosa…»', 'decide', con('decide')],
        ['decide, elegida', 'un clic elige (el círculo, con su centro) y el botón de abajo se enciende: el segundo clic responde', '', con('decide', elegida('boletin'))],
        ['decide, cambió', 'la contestaron o la editaron mientras la mirabas (409): se relee, se dice y no se manda nada', 'decide',
            con('decide', s => ({ ...elegida('boletin')(s), aviso: { tono: 'falla', texto: 'Cambió mientras la mirabas: esto es lo de ahora. No se mandó nada; míralo y vuelve a responder.' } }))],
        ['decide, mandando', 'mientras se manda: nada se aprieta y el círculo del botón gira', '', con('decide', s => ({ ...elegida('boletin')(s), enviando: true }))],
        ['tarea, propone cerrarla', 'el avance de una tarea: cerrarla como propone el agente, u «Otra cosa…» (responder; no le avisa)', 'tarea', con('tarea', undefined, leida)],
        ['tarea, otra cosa', 'lo escrito es la respuesta: queda en la historia de la tarea', '', con('tarea', s => ({ ...s, abierta: 0, otras: ['Espera: falta pagar la factura; la cierro yo el viernes.'] }), leida)],
        ['tarea, para el agente', 'plegado bajo la respuesta, lo que se le deja al agente (una nota para esta tarea, para la próxima '
            + 'revisión o «hazte cargo ya», y cómo trabajar las de este tipo), y a quién le llega; se manda con la respuesta, o solo', 'tarea',
            con('tarea', s => ({ ...s, elegidas: [['cerrar']], agente: { cuando: 'ya', abierto: true, nota: 'Antes de cerrarla, pídele a la imprenta la factura con el RUT nuevo.',
                meta: 'En las de compras, pon el número de la factura en el resumen: así se cierra sin abrir la carpeta.' } }),
            e => leida({ ...e, campos: { ...e.campos, de: 'agente:compras' } }))],
        ['tarea, pregunta', 'sin opciones: la respuesta escrita, abierta de entrada', '',
            con('tarea', undefined, e => ({ ...e, clase: 'avance:pregunta', campos: { texto: '¿La parto en dos: pedir y pagar?', version: 'v' } }))],
        ['retenido', 'un mensaje que el freno de cadenas retuvo: entero, tal cual; soltarlo o descartarlo (pregunta antes)', 'retenido', con('retenido')],
        ['retenido, descartarlo', 'elegido descartarlo: el botón de abajo va en el rojo de quitar; al hacerlo, pregunta con el foco en «cancelar»', '',
            con('retenido', elegida('descartar'))],
        ['en vivo', 'la pregunta en vivo de un hilo: sus opciones con lo que dicen de sí, otra respuesta e ir al hilo', 'en-vivo', con('en-vivo', elegida('La de la feria'))],
        ['en vivo, dos preguntas', 'varias preguntas, una de varias opciones: cada una con su enunciado', '', con('en-vivo', s => ({ ...s, elegidas: [[], []] }), dos)],
        ['permiso', 'un permiso de la terminal: no se contesta aquí, y se ofrece ir al hilo', 'permiso', con('permiso')],
    ];
    const h = ['<section class="cat-contestar">',
        '<p class="dim">Contestar lo que te espera, desde «te esperan» (<code>componentes/contestar.ts</code>, <code>media/css/contestar.css</code>; '
        + 'la abre <code>web/contestar.ts</code> con <code>abrirVentana</code>). Una sola ventana para todas las clases de espera: arriba el resumen, '
        + 'después lo que se pliega, las opciones como filas que se eligen y «Otra cosa…»; de una tarea o una pregunta de un módulo, su <b>ficha</b> '
        + 'a la izquierda (<code>componentes/ficha-contestar.ts</code>: de qué se trata, cómo llegamos aquí, qué está en juego, qué hay relacionado); '
        + 'abajo, <b>conversarlo</b> (la instrucción, de entrada al que '
        + 'preguntó) o <b>ir al hilo</b>, cancelar y el botón que hace lo elegido. <b>Dos clics</b>: uno elige, el otro responde. Con datos de mentira; '
        + '«abrir» la abre de verdad, sin contestar nada (dice qué haría).</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, abrir, html] of muestra) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}`
            + `${abrir ? ` <a class="cat-abrir" data-ensayo-contestar="${esc(abrir)}"${nombre.endsWith('cambió') ? ' data-cambio="1"' : ''} title="abrirla de verdad, sin contestar nada">abrir</a>` : ''}`
            + `<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

// ── la ventana: el marco de lo que se abre aparte (docs/propuestas/componentes.md, «Las ventanas») ──

function seccionVentana(): string {
    const filas = (n: number) => ['abrir el hilo faro', 'nueva tarea', 'ir a proyectos', 'cambiar de tema'].slice(0, n)
        .map(t => ({ titulo: t, inicio: [{ icono: I.documento }] as Item['inicio'], meta: { texto: '↵' } }));
    const muestra: [string, string, string][] = [
        ['centrada', 'un campo o un aviso con botones: titulo, ayuda, lo que pide y cómo se contesta',
            ventana({ titulo: 'cerrar «faro»', ayuda: 'se archiva y su tab se cierra; vuelve desde ARCHIVO',
                pie: pieVentana([{ texto: 'cerrar', tecla: '⏎', accion: 'x', color: C.cambiar }, { texto: 'cancelar', tecla: '⎋', accion: 'x', tono: 'callado' }]) })],
        ['paleta, arriba', 'campo + filas filtrables (↑ ↓ ⏎ ⎋): ⌘K', paleta({ lugar: 'arriba', placeholder: 'hilos, tareas, proyectos…', filas: filas(4), sel: 1 })],
        ['paleta, junto al clic', 'el menú ⋯: chica, sin fondo detrás', paleta({ lugar: 'junto', placeholder: 'acciones', titulo: 'faro', filas: filas(3), sel: 0 })],
        ['sin resultados', 'lo que dice cuando el filtro no deja nada', paleta({ lugar: 'arriba', placeholder: 'opciones', filas: [], vacia: 'nada calza' })],
        ['con detalle', 'la marcada, entera, bajo la lista (elegir una skill)', paleta({ lugar: 'arriba', filas: filas(3), sel: 2, detalle: 'cambiar de tema: pone el tema y la densidad de la página, sin recargar' })],
    ];
    const h = ['<section>',
        '<p class="dim">Lo que se abre aparte, encima de la página, para decidir o elegir (<code>componentes/ventana.ts</code>, '
        + '<code>media/css/ventana.css</code>). Es el <b>marco</b>, no el <code>&lt;dialog&gt;</code>: cabecera (título y ayuda), campo, cuerpo y pie, cada '
        + 'parte solo si se pide; abrirlo, el foco, ⎋ y el clic fuera los atiende quien la usa. Es lo <b>único con marco</b> de la gramática visual '
        + '(un marco es de lo que se abre aparte), con el fondo de las barras. Tres lugares (<code>centrada</code>, <code>arriba</code>, <code>junto</code>) '
        + 'que solo cambian dónde cae y cuánto ocupa. <code>paleta()</code> es la ventana de campo + filas (ítems): ⌘K, «elegir» y el menú ⋯ son ese mismo patrón '
        + 'con CSS distinto. La abre de verdad <code>abrirVentana</code> (<code>web/ventana.ts</code>); la primera que la usa es <a href="#contestar">contestar</a>, y las de antes se migran aparte.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, html] of muestra) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

// ── los botones con texto (catalogo-botones.ts): «la tecla en el pie», en las ventanas de confirmar ──

/** Las columnas de los botones: más anchas que la barra, para que quepa una ventana de confirmar. */
const ANCHO_BOTONES = () => (op.ancho === 'telefono' ? ANCHOS.telefono : 420);
/** Las columnas de lo que va de borde a borde de una pantalla (las pestañas, la barra de mensaje): más anchas que la barra. */
const anchas = () => `grid-template-columns: minmax(18ch, 24ch) repeat(${columnasElegidas().length}, ${op.ancho === 'telefono' ? ANCHOS.telefono : 640}px)`;
const columnasBotones = () => `grid-template-columns: minmax(18ch, 24ch) repeat(${columnasElegidas().length}, ${ANCHO_BOTONES()}px)`;
const probarBoton = (cual: string, texto = 'probar') =>
    `<a class="cat-abrir" data-probar-boton="${esc(cual)}" title="abrirla de verdad, con el tema de la primera columna: ⏎, ⇥, ⎋, su tecla y el mouse; no hace nada">${esc(texto)}</a>`;

function seccionBotones(): string {
    const h = ['<section class="cat-botones">',
        '<p class="dim">Los botones con texto: lo que se aprieta para contestar una ventana (borrar, archivar, cancelar). Es <b>la tecla en el pie</b> '
        + '(<code>componentes/boton.ts</code>, <code>media/css/boton.css</code>, tokens <code>--boton-…</code>), la forma que se eligió el 22-nov de las '
        + 'cuatro propuestas: el pie de la ventana es una banda, a una línea vacía del contenido y tras una línea de borde a borde, partida en '
        + 'celdas; cada celda dice la tecla que la hace y la palabra, y se aprieta entera; en el teléfono (el ancho «teléfono» de arriba) se reparten '
        + 'el ancho y la tecla se calla. El color es el de lo que hace (lo que destruye, el de peligro; archivar, el amarillo de «cambiar», como en el '
        + 'menú ⋯; cancelar, el del texto). La usan todas las confirmaciones (<code>preguntar</code>, <code>pieVentana</code>, contestar, escribir, la '
        + 'instrucción, la mudanza, soltar en la terminal) y ⚙ temas. Cada escena, con «probar» si es una ventana de <code>preguntar</code>: la abre de verdad.</p>',
        `<div class="cat-grilla" style="${columnasBotones()}">${titulos()}`];
    const probables: Record<string, string> = { borrar: 'borrar', archivar: 'archivar', varias: 'varias' };
    for (const e of BT.ESCENAS) {
        h.push(`<div class="cat-nombre" title="${esc(e.nota)}">${esc(e.nombre)}${probables[e.clave] ? ` ${probarBoton(probables[e.clave])}` : ''}`
            + `<span class="dim"> · ${esc(e.nota).replace(/`([^`]+)`/g, '<code>$1</code>')}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, e.html()));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionBotonesEstados(): string {
    const h = ['<section class="cat-botones">',
        '<p class="dim">Sus estados, con los tres colores al lado: lo que destruye (borrar), lo que hace sin destruir (archivar, en el color de su '
        + 'clase) y lo que no hace nada (cancelar). Al pasar el mouse y con el foco van puestos a mano (<code>es-hover</code>, <code>es-foco</code>); en '
        + '«normal» se pueden probar de verdad, con el mouse y con ⇥. Apagado es un <code>&lt;button disabled&gt;</code>.</p>',
        `<div class="cat-grilla" style="${columnasBotones()}">${titulos()}`];
    for (const e of BT.filasEstados()) {
        h.push(`<div class="cat-nombre" title="${esc(e.nota)}">${esc(e.nombre)}<span class="dim"> · ${esc(e.nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, e.html));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionBotonesFoco(): string {
    return '<section class="cat-botones"><p class="dim">En una ventana de confirmar, ⏎ es lo más rápido y lo más peligroso: lo que se aprieta sin mirar. '
        + 'Así quedó (lo atiende <code>web/botonera.ts</code> en cada ventana; lo revisa <code>npm run prueba:confirmar</code>).</p>'
        + '<table class="gr-tabla cat-tabla"><tr><th>regla</th><th>por qué</th></tr>'
        + BT.REGLAS_FOCO.map(r => `<tr><td>${esc(r.regla)}</td><td>${esc(r.por).replace(/`([^`]+)`/g, '<code>$1</code>')}</td></tr>`).join('')
        + '</table></section>';
}

function seccionBotonesHoy(): string {
    const clase: Record<string, string> = { destruye: 'destruye: ⌘⌫, foco en cancelar', mira: 'pide mirar: foco en cancelar', hace: 'hace: foco en lo que hace' };
    const tabla = (titulo: string, cabeza: string[], filas: string[][]) =>
        `<h3>${esc(titulo)}</h3><table class="gr-tabla cat-tabla"><tr>${cabeza.map(c => `<th>${esc(c)}</th>`).join('')}</tr>`
        + filas.map(f => `<tr>${f.map(x => `<td>${esc(x).replace(/`([^`]+)`/g, '<code>$1</code>')}</td>`).join('')}</tr>`).join('') + '</table>';
    return '<section class="cat-botones"><p class="dim">Qué confirmaciones destruyen, y qué hace cada una (22-nov-2026). Las rutas, relativas a '
        + '<code>pagina/src</code>; <code>npm run prueba:confirmar</code> revisa que cada archivo con una confirmación esté aquí, y que cada una que dice '
        + 'un verbo que destruye lo trate como tal.</p>'
        + tabla('las confirmaciones', ['dónde', 'qué pregunta', 'botones', 'clase', 'por qué'],
            BT.CONFIRMACIONES.map(c => [c.archivo, c.que, c.botones, clase[c.clase], c.por]))
        + tabla('las formas descartadas', ['forma', 'cómo era', 'por qué no'], BT.DESCARTADAS.map(f => [f.nombre, f.como, f.por]))
        + `<p class="dim">${esc(BT.NOTA_HOY)}</p></section>`;
}

// ── nuevo: el + de crear uno, y su lugar en la cabecera ──

function seccionNuevo(): string {
    const verTodos: Accion = { accion: 'cmd', id: 'telar.agentesVer', icono: I.lista, ayuda: 'todos los agentes' };
    const agente = A.nuevo({ accion: 'cmd', id: 'telar.agenteNuevo' }, 'agente nuevo: un agente residente');
    const cab = (titulo: string, cuenta: number, fijas: Accion[]) => item({ variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo,
        sufijo: cuenta ? [{ texto: String(cuenta), tono: 'tenue' }] : [], fijas });
    const filas: [string, string, string][] = [
        ['solo', 'la sección no tiene otra acción', cab('hilos', 14, [A.nuevo({ accion: 'cmd', id: 'telar.nuevo' }, 'hilo nuevo: un tab con su agente')])],
        ['con otras', 'las suyas antes, el + al final (el ‹ que pliega la barra entera no va aquí: es de la barra, y va en su franja de avisos)', cab('agentes', 0, [verTodos, agente])],
    ];
    const h = ['<section>',
        '<p class="dim">Crear uno nuevo en una sección (<code>componentes/acciones.ts</code>): el <b>+</b> de la letra, sin la palabra '
        + '«nuevo»; lo que crea lo dice su ayuda. Va en la cabecera de su sección, como su última acción: en el borde derecho, en la '
        + 'misma columna en todas las cabeceras. Es una acción, así que es un ícono de la letra y no un círculo.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionPartes(): string {
    // lo que carga el contexto de un hilo (web/carga.ts): cada grupo con el color de su token, --carga-<grupo>
    const g = (clave: string, valor: number, activa = false): ParteDeTotal => ({ clave, valor, tinta: `carga-${clave}`, activa, ayuda: `${clave}: ${valor} k` });
    const contexto = [g('claude', 37), g('inicio', 30), g('carpetas', 2), g('leido', 51), g('repetido', 4), g('hilos', 1), g('conversacion', 240)];
    const filas: [string, string, string][] = [
        ['un total y sus partes', 'el contexto de un hilo: lo de Claude Code, lo que carga al empezar, al entrar a carpetas, lo que leyó, '
            + 'lo que se repite, lo de otros hilos y la conversación', partes({ partes: contexto, accion: 'abrir' })],
        ['con una abierta', 'la que se ve abajo (un grupo abierto) lleva la raya del texto debajo',
            partes({ partes: contexto.map(x => ({ ...x, activa: x.clave === 'inicio' })), accion: 'abrir' })],
        ['partes chicas', 'lo que pesa tan poco que no se vería ocupa igual una raya: está, aunque no se mida',
            partes({ partes: [g('inicio', 1), g('leido', 1), g('conversacion', 400)] })],
        ['sin nada', 'todavía no hay qué partir: la franja, en la línea', partes({ partes: [] })],
    ];
    const h = ['<section>',
        '<p class="dim">Las <b>partes</b> de un total, en una franja (<code>componentes/partes.ts</code>, <code>media/css/partes.css</code>): '
        + 'cada parte es un rectángulo con el ancho de lo que pesa y el color de lo que es (el color dice el tipo), en el orden en que se '
        + 'nombran abajo, con una raya del fondo entre dos. Sin esquinas: es un rectángulo partido. Un clic en una parte lleva '
        + '<code>data-accion</code> y <code>data-id</code>, como el ítem. Su alto es <code>--partes-alto</code> (tokens.css). '
        + 'La usa la hoja «contexto» de la barra de la derecha.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

// ── el día en una línea: la jornada, sola y en la cabecera de la página ──

/** El día de mentira a una hora. */
const diaDeMuestra = (ahora: number, tramos = DIA_EJEMPLO) => jornada({ ...JORNADA_EJEMPLO, ahora, tramos });

/** La cabecera de la página, armada con sus clases (marco.css) y la jornada adentro: como se vería a ese ancho. Con
 *  `visto`, viendo un hilo; en un teléfono, eso es «‹» en vez de la marca. */
function cabeceraDeMuestra(px: number, html: string, visto = ''): string {
    const c = columnasElegidas()[0];
    return `<div class="muestra cat-cab-marco" style="width: ${px}px" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">`
        + `${cabeceraInterna(html, visto, !!visto && px <= 700)}</div>`;
}

/** La cabecera misma, sin su marco: la marca (o «‹ hilos», en el detalle de un teléfono), la máquina y lo que se ve, la
 *  jornada y los botones. */
function cabeceraInterna(html: string, visto: string, detalle: boolean, punto = ''): string {
    return `<header class="cabecera cat-cab${detalle ? ' en-detalle' : ''}"><div class="cab-fila">`
        + `<div class="cab-izq"><span class="logo"><span class="logo-t">t</span><span class="logo-resto">elar</span></span><span class="dim cab-corre">0.13.0</span>`
        + `<a class="cab-volver"><span class="i">${I.atras}</span><span class="txt"> hilos</span>${punto ? `<span class="franja-punto-lugar">${punto}</span>` : ''}</a></div>`
        + `<div class="cab-donde"><b class="cab-aqui">laptop</b>${visto ? '<span class="cab-icono">:</span>' : ''}<span class="cab-visto">${esc(visto)}</span></div>`
        + `<div class="cab-jornada">${html}</div>`
        + `<div class="cab-der"><a class="config i">${I.apps}</a><a class="config i">${I.modo}</a><a class="config i">${I.maquinas}</a><a class="config i">${I.config}</a></div>`
        + '</div></header>';
}

function seccionJornadaEnCabecera(): string {
    const h = ['<section>',
        '<p class="dim">En la cabecera de la página (<code>web/jornada.ts</code> le pone la agenda de hoy), a la derecha, antes de los '
        + 'botones. Es lo primero que cede: pide su ancho y, si no cabe, se resume antes que la máquina, lo que se ve y la marca, hasta '
        + 'quedar en cuánto falta («1h 20»); eso no lo suelta. Los botones, nunca. Un clic lleva al calendario. Con el día de mentira de '
        + '«estados»: libre a las 10:10, en una reunión a las 11:45.</p>'];
    for (const [nombre, ahora] of [['libre', MOMENTOS[0].ahora], ['en una reunión', MOMENTOS[2].ahora]] as [string, number][]) {
        h.push(`<h3>${esc(nombre)}</h3><div class="cat-cabs">`
            + `<div class="cat-tema">laptop · 1440px, viendo un hilo</div>${cabeceraDeMuestra(1440, diaDeMuestra(ahora), 'Informe')}`
            + `<div class="cat-tema">teléfono · 412px, en la lista y viendo un hilo</div>${cabeceraDeMuestra(412, diaDeMuestra(ahora))}`
            + `${cabeceraDeMuestra(412, diaDeMuestra(ahora), 'Informe')}</div>`);
    }
    h.push('</section>');
    return h.join('');
}

function seccionJornada(): string {
    const c = columnasElegidas()[0];
    const anchos: [string, string][] = [['con holgura', '84ch'], ['menos', '50ch'], ['poco', '30ch'], ['muy poco', '16ch'], ['lo mínimo', '7ch']];
    const h = ['<section>',
        '<p class="dim">El día en una línea (<code>componentes/jornada.ts</code>, <code>media/css/jornada.css</code>): una barra fina que es '
        + 'la jornada entera, como una barra de carga (lo que ya pasó se llena; las reuniones en su azul, lo propio tenue; ahora, una '
        + 'raya), y el texto de lo de ahora. Cuenta como reunión lo que es con otras personas; lo propio y el almuerzo no cortan lo '
        + 'libre. De una invitación importa lo que la persona respondió (<code>respuesta</code>, de <code>telar hoy</code>): la '
        + 'rechazada no se dibuja ni cuenta; la aceptada, la tentativa y la que organiza ella son reuniones; y la que no ha '
        + 'respondido también corta lo libre, pero va solo con su borde y el texto dice «(sin responder)». Lo que se ve lo decide su ancho: con menos, se va lo que viene más tarde, después el nombre de lo que sigue, después '
        + 'la barra, después hasta cuándo. Un día de mentira: Daily a las 9:00, un bloque propio, Revisión de diseño a las 11:30, el '
        + 'almuerzo, Comité a las 15:00 pegado a una llamada y el cierre a las 17:15, en una jornada de 8:30 a 18:00. Los cinco '
        + 'últimos, con las respuestas: el Daily aceptado, una revisión del trimestre rechazada a las 10:30, la Revisión de diseño '
        + 'tentativa, una presentación al equipo sin responder a las 14:00, el Comité que organiza ella y la llamada aceptada.</p>',
        `<div class="cat-grilla" style="grid-template-columns: minmax(18ch, 24ch) ${anchos.map(([, w]) => w).join(' ')}">`,
        `<div></div>${anchos.map(([n, w]) => `<div class="cat-tema">${esc(n)} · ${w}</div>`).join('')}`];
    for (const m of MOMENTOS) {
        const html = diaDeMuestra(m.ahora, m.tramos) || '<span class="dim">(nada)</span>';
        h.push(`<div class="cat-nombre" title="${esc(m.nota)}">${esc(m.nombre)}<span class="dim"> · ${esc(m.nota)}</span></div>`
            + anchos.map(() => `<div class="muestra cat-jornada" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${html}</div>`).join(''));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionOrden(): string {
    const opciones: OpcionOrden[] = [
        { clave: 'urgencia', icono: I.urgencia, ayuda: 'urgencia: prioridad alta primero' },
        { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre, alfabético' },
        { clave: 'reciente', icono: I.reloj, ayuda: 'última modificación' },
    ];
    const filas: [string, string, string][] = [
        ['como lo da telar', 'ninguna opción rige', orden({ grupo: 'muestra', opciones, activa: '' })],
        ['una rige', 'la de la marca; otro clic en ella vuelve al orden de telar', orden({ grupo: 'muestra', opciones, activa: 'nombre' })],
        ['dos opciones', 'el grupo se ajusta a lo que ordena', orden({ grupo: 'muestra', opciones: opciones.slice(0, 2), activa: 'urgencia' })],
    ];
    const h = ['<section>',
        '<p class="dim">El grupo que ordena una lista (<code>componentes/orden.ts</code>, <code>media/css/orden.css</code>): un ícono '
        + '<b>padre</b> (<code>I.ordenar</code>) que dice «lo que sigue ordena», y sus opciones, cada una un ícono en su celda cuadrada, '
        + 'entre dos cortes en el púrpura del orden (<code>--orden-linea</code>). En la gramática visual es un <b>grupo</b> dentro de la banda '
        + 'de herramientas (la barra de hilos, en su página); sus opciones son acciones (íconos de la letra), no círculos. Lo usa la barra de hilos; las columnas del '
        + 'dashboard (proyectos, tareas) aún ordenan a su manera.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionBuscador(): string {
    const h = ['<section>',
        '<p class="dim">El campo con que se busca o se filtra una lista (<code>componentes/buscador.ts</code>, <code>media/css/buscador.css</code>, '
        + 'tokens <code>--buscador-…</code>), uno solo para toda la página. <b>Una regla</b>: delante, la lupa, que dice «aquí se busca», y nada '
        + 'escrito adentro (sin placeholder). <b>En qué</b> se busca, sin el verbo («hilos», «tareas», «lo que te espera»), va en el '
        + '<code>aria-label</code> y, con por qué campos y qué hacen ⏎ y ⎋, al pasar el mouse. Entre la lupa y el primer carácter, un carácter '
        + '(<code>--buscador-lupa-hueco</code>, 1ch), igual en todos. La tecla que lo enfoca, al final y tenue; lo que el filtro dejó, al final; con algo escrito, el ✕ que lo borra. '
        + 'Los estados se ven solo con color. Cuando es una <b>fila propia</b> (bajo HILOS, arriba de una lista del dashboard, en lo alto de una '
        + 'ventana) va en su <b>barra</b> (<code>barraBuscar()</code>): del alto de las demás barras, con el aire de una pantalla y su línea abajo '
        + 'de borde a borde, con lo que lo acompaña a la derecha. El campo no lleva borde: «bordes» muestra por qué. Lo que hace (filtrar, ⎋, ⏎, '
        + 'la tecla) lo atiende la vista; el ✕, <code>web/buscadores.ts</code>. Aquí no se escribe: lo escrito y el foco van puestos.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const f of BU.filasEstados()) {
        h.push(`<div class="cat-nombre" title="${esc(f.nota)}">${esc(f.nombre)}<span class="dim"> · ${esc(f.nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, f.html));
    }
    h.push('</div></section>');
    return h.join('');
}

/** Las cuatro maneras de dibujar el campo dentro de su barra, una al lado de otra, en un trozo de la barra de hilos. Una
 *  grilla por tema elegido arriba. */
function seccionBordesBuscador(): string {
    const h = ['<section>', BU.notaBordes()];
    for (const c of columnasElegidas()) {
        // las cuatro, una al lado de otra (un poco más angostas que la barra, para que quepan); cada estado, con su nombre arriba
        h.push(`<div class="cat-tema cat-bordes-tema">${esc(nombreColumna(c))}</div>`,
            `<div class="cat-grilla cat-bordes" style="grid-template-columns: repeat(${BORDES.length}, 280px)">`
            + BORDES.map(b => `<div class="cat-tema" title="${esc(b.nota)}">${esc(b.nombre)}${b.elegida ? ' · <span class="cat-elegida">la elegida</span>' : ''}</div>`).join(''));
        for (const f of BU.filasBordes()) {
            h.push(`<div class="cat-nombre cat-bordes-estado" title="${esc(f.nota)}">${esc(f.nombre)}<span class="dim"> · ${esc(f.nota)}</span></div>`);
            for (const b of BORDES) h.push(celda(c, f.html, `borde-${b.clave}`));
        }
        h.push('</div>');
    }
    h.push('</section>');
    return h.join('');
}

/** Sus partes, en una tabla: qué dice cada una, la prop que la pone y su token. */
function seccionAnatomiaBuscador(): string {
    const c = columnasElegidas()[0];
    const grande = barraBuscar({ placeholder: 'hilos', ayuda: 'buscar por nombre', valor: 'far', enfocado: true, cuenta: { texto: '2 de 14' },
        herramientas: orden({ grupo: 'muestra', activa: '', opciones: [{ clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre' }] }) });
    return '<section><p class="dim">El buscador escribiendo, en su barra, y lo que es cada parte.</p>'
        + `<div class="muestra barra-de-muestra cat-buscador-grande" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${grande}</div>`
        + '<table class="gr-tabla cat-tabla"><tr><th>parte</th><th>qué dice</th><th>la pone</th><th>sus tokens</th></tr>'
        + BU.PARTES.map(p => `<tr><td>${esc(p.parte)}</td><td>${esc(p.dice)}</td><td><code>${esc(p.prop)}</code></td><td><code>${esc(p.token)}</code></td></tr>`).join('')
        + '</table></section>';
}

/** Dónde se usa: cada buscador de la página, cómo era antes y cómo es ahora. */
function seccionDondeBuscador(): string {
    return '<section><p class="dim">Cada campo de buscar o de filtrar por texto que tenía la página, cómo se veía antes (18-nov-2026) y '
        + 'cómo es ahora: todos son este componente, en su barra.</p>'
        + '<table class="gr-tabla cat-tabla"><tr><th>dónde</th><th>de dónde sale</th><th>antes</th><th>ahora</th></tr>'
        + BU.DONDE.map(d => `<tr><td>${esc(d.lugar)}</td><td><code>${esc(d.archivo)}</code></td><td>${esc(d.antes)}</td><td>${esc(d.ahora)}</td></tr>`).join('')
        + '</table></section>';
}

/** Los filtros de mentira: los de la pestaña «tareas», con nombres que no son de nadie. */
function gruposMuestra(o: { modo?: string; area?: string; dueno?: string; plegar?: string[] } = {}): GrupoFiltro[] {
    const pl = (k: string) => o.plegar?.includes(k) ?? false;
    return [
        { clave: 'modo', nombre: 'cuáles', activa: o.modo ?? 'semana', siempre: 'semana', plegado: pl('modo'), opciones: [
            { clave: 'semana', nombre: 'esta semana', cuenta: 67 }, { clave: 'todas', nombre: 'todas', cuenta: 159 },
            { clave: 'revisar', nombre: 'por revisar', cuenta: 51 }, { clave: 'vencidas', nombre: 'vencidas', cuenta: 42 },
            { clave: 'deuda', nombre: 'deuda', cuenta: 31 },
            { clave: 'estrella', nombre: I.estrella, cuenta: 0, ayuda: 'con estrella' }, { clave: 'encurso', nombre: 'en curso', cuenta: 0 },
            { clave: 'sinfecha', nombre: 'sin fecha', cuenta: 86 }] },
        { clave: 'area', nombre: 'área', activa: o.area ?? '', plegado: pl('area'), opciones: [
            { clave: 'trabajo', nombre: 'trabajo', cuenta: 52 }, { clave: 'personal', nombre: 'personal', cuenta: 13 },
            { clave: 'cliente', nombre: 'cliente', cuenta: 2 }, { clave: 'estudio', nombre: 'estudio', cuenta: 0 }] },
        { clave: 'dueno', nombre: 'responsable', activa: o.dueno ?? '', plegado: pl('dueno'), opciones: [
            { clave: 'mias', nombre: 'mías', cuenta: 39 }, { clave: 'otros', nombre: 'de otros', cuenta: 13 },
            { clave: 'sin', nombre: 'sin responsable', cuenta: 15 }] },
    ];
}

function seccionFiltros(): string {
    const filas: [string, string, string][] = [
        ['como abre', 'como en «tareas»: «esta semana» a la vista; área y responsable plegados, sin filtrar',
            filtros({ grupos: gruposMuestra({ plegar: ['area', 'dueno'] }) })],
        ['dos rigen', 'la de cada grupo en el acento, también plegada; un clic en ella la suelta',
            filtros({ grupos: gruposMuestra({ modo: 'vencidas', area: 'trabajo', plegar: ['area', 'dueno'] }) })],
        ['a la vista', 'sin plegar: todas las opciones con su cuenta; si no cabe, baja el grupo entero',
            filtros({ grupos: gruposMuestra({ area: 'personal' }) })],
        ['plegados', 'todo plegado, para una columna angosta: lo que rige, o el nombre del grupo; un clic abre su menú',
            filtros({ grupos: gruposMuestra({ area: 'personal', plegar: ['modo', 'area', 'dueno'] }) })],
    ];
    const h = ['<section>',
        '<p class="dim">Los grupos de opciones que eligen qué filas de una lista se ven (<code>componentes/filtros.ts</code>, '
        + '<code>media/css/filtros.css</code>): cada opción, una palabra con su cuenta (cuántas filas dejaría, con lo demás que está '
        + 'filtrado); la que rige, en el acento, y otro clic en ella la suelta. En una fila tras el ícono padre (<code>I.filtro</code>), '
        + 'los grupos apartados por más aire que sus opciones; si no cabe, baja el grupo entero. Una cuenta en cero, apagada. '
        + 'Un grupo plegado dice solo lo que rige (o su nombre) y un ⌄, y sus opciones van en un menú: se pliega lo que se elige '
        + 'una vez y se deja (el área), y queda a la vista lo que se cambia seguido (el modo).</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

/** Cómo van en «tareas», bajo su barra: las herramientas (buscar y ordenar), los filtros y las primeras filas, en tres
 *  anchos. Se eligió entre tres maneras (docs/propuestas/componentes.md, «Las listas de tareas»). */
function seccionFiltrosEnTareas(): string {
    const c = columnasElegidas()[0];
    const herram = barraBuscar({ grupo: 'muestra', placeholder: 'tareas', atajo: '/', cuenta: { texto: '67 de 159' }, ayuda: 'buscar', claseBarra: 'cat-herram',
        herramientas: orden({ grupo: 'muestra', activa: '', opciones: [
            { clave: 'dias', icono: I.fecha, ayuda: 'fecha' }, { clave: 'pri', icono: I.urgencia, ayuda: 'prioridad' },
            { clave: 'est', icono: I.estrella, ayuda: 'estrella' }, { clave: 'proy', icono: I.carpeta, ayuda: 'proyecto' },
            { clave: 'resp', icono: I.persona, ayuda: 'responsable' }, { clave: 'ref', icono: I.etiqueta, ayuda: 'código' },
            { clave: 'alfa', icono: I.alfabetico, ayuda: 'alfabético' }] }) });
    const filas = ['T375 · Preparar la propuesta del taller y mandarla a revisión', 'T433 · Revisar el informe de octubre con el equipo',
        'T454 · Pagar la cuenta de la luz']
        .map(t => `<div class="cat-tarea">${esc(t)}</div>`).join('');
    const lista = `${herram}<div class="cat-filtros">${filtros({ grupos: gruposMuestra({ area: 'trabajo', plegar: ['area', 'dueno'] }) })}</div>${filas}`;
    const anchos: [string, number][] = [['el dashboard en el computador', 1100], ['media pantalla', 620], ['teléfono', 390]];
    const h = ['<section><p class="dim">En la lista de «tareas», bajo sus herramientas: el modo a la vista, en palabras con su cuenta, '
        + 'porque se cambia seguido; el área y el responsable plegados, porque se eligen una vez y se dejan. Una fila en el computador; '
        + 'en el teléfono se parte por grupos. Aquí, «área: trabajo» está elegida.</p><div class="cat-anchos">'];
    for (const [que, px] of anchos) h.push(`<div><div class="cat-tema">${esc(que)} · ${px}px</div>`
        + `<div class="muestra cat-lista-tareas" style="width:${px}px" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${lista}</div></div>`);
    h.push('</div></section>');
    return h.join('');
}

function seccionItem(): string {
    const h: string[] = ['<section>',
        '<p class="dim">La fila de una lista (<code>componentes/item.ts</code>, <code>media/css/item.css</code>): '
        + '<b class="sec-inicio">inicio</b> con ranuras de íconos de ancho fijo, <b class="sec-texto">texto</b> (prefijo, título, sufijo) '
        + 'y <b class="sec-fin">fin</b> (aviso, meta, acciones fijas y las que aparecen al pasar el mouse). Un clic en el nombre de un '
        + 'estado muestra sus props.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    let grupo = '';
    HISTORIAS.forEach((x, i) => {
        if (x.grupo !== grupo) { grupo = x.grupo; h.push(`<div class="cat-grupo">${esc(grupo)}</div>`); }
        h.push(`<div class="cat-nombre" data-props="${i}" title="${esc(x.nota ?? '')}">${esc(x.nombre)}${x.nota ? `<span class="dim"> · ${esc(x.nota)}</span>` : ''}</div>`);
        for (const c of columnasElegidas()) h.push(celda(c, item(x.props)));
        h.push(`<pre class="cat-props" data-props-de="${i}" hidden>${esc(props(x.props))}</pre>`);
    });
    h.push('</div></section>');
    return h.join('');
}

function seccionTarjeta(): string {
    // tareas de mentira, como las de foco
    const corto = 'Revisar con Ana el borrador del informe mensual antes de mandarlo';
    const medio = 'Contestarle a Ana cómo seguimos con las plataformas de generación de cursos y coordinar la reunión para acordar la recomendación';
    const largo = `${medio} entre las dos que quedaron, con lo que cuesta cada una en un año, lo que pide soporte para operarla y qué pasa con los cursos que ya están hechos en la otra`;
    const datos = (codigo: string, proyecto: string, ...mas: Pieza[]): Pieza[] => [{ texto: codigo }, { texto: proyecto, tono: 'acento' }, ...mas];
    const acciones: Accion[] = [
        { accion: 'x', icono: I.sinEstrella, ayuda: 'ponerle estrella' }, { accion: 'x', icono: I.fecha, ayuda: 'otra fecha' },
        { accion: 'x', icono: I.instruccion, tono: 'agente', ayuda: 'instrucción' }, { accion: 'x', icono: I.hecha, ayuda: 'marcarla hecha' },
    ];
    const menu: Accion = { accion: 'x', icono: I.menu, ayuda: 'más' };
    const base: Tarjeta = { inicio: [S.prioridad(1), null], titulo: medio, datos: datos('T457', 'faro'), meta: { texto: '3d' }, acciones, menu };
    const espera: Tarjeta = { inicio: [S.prioridad(2), S.atencion('espera')], prefijo: [{ texto: 'pregunta', tono: 'atencion' }] };
    const filas: [string, string, string][] = [
        ['quieta', 'la cabecera (sus círculos, el título entero, sus acciones escondidas) y el pie, con sus datos y la meta', tarjeta(base)],
        ['te espera', 'un aro en la ranura del estado, y lo que le pasó en una palabra antes del título',
            tarjeta({ ...base, ...espera })],
        ['con cuerpo', 'lo que se lee además del título, tenue y donde empieza el título', tarjeta({ ...base, ...espera,
            cuerpo: 'Propone la segunda: cuesta menos en un año y soporte ya la conoce. Falta saber qué pasa con los cursos hechos en la otra.' })],
        ['en curso', 'algo pasa ahora: lleno, como un hilo trabajando', tarjeta({ ...base, inicio: [S.prioridad(1), S.atencion('trabajando')], titulo: corto })],
        ['elegida', 'el fondo de la selección, como el ítem donde estás, y sus acciones a la vista', tarjeta({ ...base, activa: true })],
        ['al pasar el mouse', 'sus acciones aparecen arriba a la derecha, en su columna: el título no queda tapado; el ⋯ al último', tarjeta({ ...base, clases: ['hover'] })],
        ['con alertas', 'lo que no cuadra, en el color de su alerta: aquí, la meta vencida en rojo y un dato que falta. Ni rayas ni bordes de color',
            tarjeta({ ...base, inicio: [S.urgente(), null], datos: datos('T454', 'faro', { texto: 'sin tamaño', tono: 'atencion' }), meta: { texto: '-14d', tono: 'peligro' } })],
        ['señalada', 'un aro con un punto, en el aviso', tarjeta({ ...base, aviso: S.estrella('con estrella') })],
        ['larga', 'el título se corta con «…» a las tres líneas; entero al pasar el mouse', tarjeta({ ...base, titulo: largo, ayuda: largo })],
        ['holgada', 'de a pocas, para leerlas enteras: más aire y el título sin tope', tarjeta({ ...base, titulo: largo, holgada: true })],
        ['arrastrándose', 'tenue mientras va a donde se suelta', tarjeta({ ...base, titulo: corto, clases: ['arrastrando'] })],
        ['una lista', 'varias, una debajo de otra, apartadas con aire; la del medio, elegida', listaTarjetas([
            tarjeta({ ...base, titulo: corto, datos: datos('T405', 'faro'), meta: { texto: '-4d', tono: 'peligro' } }),
            tarjeta({ ...base, activa: true, ...espera }),
            tarjeta({ ...base, inicio: [S.prioridad(3), null], titulo: 'Pagar la factura vencida antes de que corten el servicio', datos: datos('T503', 'casa', { texto: 'sin tamaño', tono: 'atencion' }), meta: { texto: 'hoy', tono: 'atencion' } }),
        ])],
    ];
    const ancho = op.ancho === 'telefono' ? ANCHOS.telefono : 480;
    const h = ['<section>',
        '<p class="dim">Una cosa entera que se mira y se decide de a una, entre pocas; hoy, las tareas de foco (<code>componentes/tarjeta.ts</code>, '
        + '<code>media/css/tarjeta.css</code>). Es un <b>ítem que no se corta</b>: las mismas ranuras de círculos al inicio, las mismas acciones al '
        + 'pasar el mouse y el ⋯, pero en tres partes: la <b>cabecera</b> (los círculos, el título entero en varias líneas y las acciones arriba a la '
        + 'derecha, en su columna), el <b>cuerpo</b> si tiene, y el <b>pie</b> con sus datos y la meta. En la gramática es una '
        + '<b>fila</b> más alta, no una caja: <b>sin marco</b> (un marco es de lo que se abre aparte, una ventana) <b>ni fondo propio</b>; las tarjetas '
        + 'se apartan con aire (<code>--tarjeta-aire</code>), la elegida lleva el fondo de la selección, y lo que dice cada una (su estado, cuánto importa, '
        + 'lo que no cuadra) lo dicen sus piezas, nunca un borde o una raya de color.</p>',
        `<div class="cat-grilla" style="grid-template-columns: minmax(18ch, 24ch) repeat(${columnasElegidas().length}, ${ancho}px)">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}

// ── las casillas de foco (docs/propuestas/componentes.md, «Las casillas») ──

/** Las casillas de una tarea de foco, como las arma foco.ts: en grupos, por lo que hacen. */
function casillasDeMentira(o: { concentracion?: boolean; vencida?: boolean; sinTamano?: boolean }): Casilla[][] {
    const fecha: Casilla = { valor: 'fecha', nombre: 'nueva fecha', icono: I.fecha, color: 'amarillo', ayuda: 'hoy, mañana, el lunes…: cuándo de verdad',
        rapidas: [
            ...(o.vencida ? [{ valor: 'hoy', texto: 'hoy', nombre: 'va hoy', ayuda: 'la haces hoy: su fecha pasa a hoy' }] : []),
            { valor: 'aplazar:+1', texto: '+1 · sáb 14', nombre: 'un día más', ayuda: '2026-11-14' },
            { valor: 'aplazar:vie', texto: 'vie 20', nombre: 'el viernes', ayuda: '2026-11-20' },
            { valor: 'aplazar:lun', texto: 'lun 16', nombre: 'el lunes', ayuda: '2026-11-16' },
        ] };
    const instruccion: Casilla = { valor: 'instruccion', nombre: 'instrucción', icono: I.instruccion, color: 'violeta',
        ayuda: 'mandársela a su hilo, a uno nuevo, a otro o a un agente, con una skill o lo que le pidas',
        rapidas: [{ valor: 'trabajar', texto: 'trabajarla', nombre: 'trabajar en un hilo',
            ayuda: 'a su hilo, con «Veamos …» escrito: te lleva a él para trabajarla ahí' },
            ...(o.concentracion ? [{ valor: 'bloque', texto: 'bloquear tiempo', nombre: 'bloquear tiempo',
                ayuda: 'una instrucción hecha, a su hilo: /tarea con «busca un bloque de 2 a 3 horas en mi calendario y créalo»' }] : [])] };
    const rapida = { valor: 'rapida', texto: 'rápida', nombre: 'es rápida', ayuda: 'media hora o menos: va en gestión' };
    const larga = { valor: 'larga', texto: 'larga', nombre: 'es larga', ayuda: 'horas o días: va en concentración' };
    const tamano: Casilla = { valor: 'tamano', nombre: 'tamaño', icono: I.tamano, color: 'amarillo', padre: true,
        ayuda: 'cuánto toma: rápida, media hora o menos (gestión); larga, horas o días (concentración)',
        rapidas: o.sinTamano ? [rapida, larga] : o.concentracion ? [rapida] : [larga] };
    return [
        [{ valor: 'ver', nombre: 'ver el detalle', icono: I.documento, color: 'azul', ayuda: 'su ficha entera: el contexto, la historia y todas sus acciones' }],
        [{ valor: 'hecha', nombre: 'hecha', icono: I.hecha, color: 'verde', ayuda: 'ya está: se marca hecha' }],
        [fecha, tamano],
        [instruccion, { valor: 'asignar', nombre: 'de otra persona', icono: I.persona, color: 'amarillo', ayuda: 'asignarla: sale de tu foco' }],
        [...(o.concentracion ? [{ valor: 'paso', nombre: 'sacar el primer paso', icono: I.nuevo, color: 'verde', ayuda: 'una tarea rápida que la empieza: va a gestión; esta espera su bloque' }] : []),
            { valor: 'unir', nombre: 'es la misma que…', icono: I.unir, color: 'cian', ayuda: 'otra tarea dice lo mismo: esta se le une y se descarta' }],
        [{ valor: 'descartar', nombre: 'descartar', icono: I.descartar, color: 'rojo', ayuda: 'no se va a hacer: sale de la lista' }],
    ];
}

function seccionCasillas(): string {
    const t = (pri: number, titulo: string, codigo: string, proyecto: string, meta: Pieza, mas: Partial<Tarjeta> = {}): Tarjeta => ({
        inicio: [S.prioridad(pri), null], titulo, datos: [{ texto: codigo }, { texto: proyecto, tono: 'acento' }], meta,
        acciones: [{ accion: 'x', icono: I.sinEstrella, ayuda: 'ponerle estrella' }, { accion: 'x', icono: I.fecha, ayuda: 'otra fecha' },
            { accion: 'x', icono: I.instruccion, tono: 'agente', ayuda: 'instrucción' }, { accion: 'x', icono: I.hecha, ayuda: 'marcarla hecha' }],
        menu: { accion: 'x', icono: I.menu, ayuda: 'más' }, ...mas });
    const gestion = (o: { activa?: number; arrastrada?: number } = {}) => listaTarjetas([
        t(1, 'Contestarle a Ana cómo seguimos con las plataformas de cursos y coordinar la reunión', 'T454', 'faro', { texto: '-9d', tono: 'peligro' },
            { inicio: [S.prioridad(1), S.atencion('espera')], prefijo: [{ texto: 'pregunta', tono: 'atencion' }] }),
        t(2, 'Revisar con Ana el borrador del informe mensual antes de mandarlo', 'T405', 'faro', { texto: '-4d', tono: 'peligro' }),
        t(3, 'Pagar la factura vencida antes de que corten el servicio', 'T503', 'casa', { texto: 'hoy', tono: 'atencion' },
            { datos: [{ texto: 'T503' }, { texto: 'casa', tono: 'acento' }, { texto: 'sin tamaño', tono: 'atencion' }] }),
    ].map((x, i) => tarjeta({ ...x, activa: i === (o.activa ?? 0), clases: i === o.arrastrada ? ['arrastrando'] : [] })));
    const concentracion = () => listaTarjetas([
        tarjeta({ ...t(1, 'Escribir la propuesta de gobierno de datos con lo que salió del diagnóstico y lo que cuesta operarla', 'T433', 'faro',
            { texto: 'vie' }), activa: true, holgada: true }),
        tarjeta({ ...t(2, 'Preparar el taller de la próxima semana: el temario, los ejercicios y la invitación', 'T375', 'academia', { texto: '6d' }), holgada: true }),
    ]);
    const gira = `${circulo({ mov: 'gira' })} marcándola hecha…`;
    const base = { accion: 'foco-soltar' };
    const filas: [string, string, string][] = [
        ['gestión, vencida', 'la elegida venció: «hoy» va con los aplazamientos, junto a nueva fecha; «larga» junto al tamaño',
            casillas({ ...base, grupos: casillasDeMentira({ vencida: true }) }) + gestion()],
        ['sin tamaño', 'el reloj del tamaño trae las dos: rápida y larga',
            casillas({ ...base, grupos: casillasDeMentira({ sinTamano: true }) }) + gestion({ activa: 2 })],
        ['mouse encima', 'el globo dice su nombre y qué hace (aquí, el fondo del hover sobre hecha)',
            casillas({ ...base, grupos: casillasDeMentira({ vencida: true }), hover: 'hecha' }) + gestion()],
        ['arrastrando', 'la del medio va hacia «hecha»: mientras dura, cada casilla dice su nombre; donde caería, marcada',
            casillas({ ...base, grupos: casillasDeMentira({ vencida: true }), arrastrando: true, encima: 'hecha' }) + gestion({ arrastrada: 1 })],
        ['concentración', 'bloquear tiempo es una instrucción hecha: va junto a la instrucción, en su violeta; y sacar el primer paso',
            casillas({ ...base, grupos: casillasDeMentira({ concentracion: true }) }) + concentracion()],
        ['haciendo', 'mientras una acción va a telar: lo dice, y no se aprietan',
            casillas({ ...base, grupos: casillasDeMentira({ vencida: true }), ocupadas: true, haciendo: gira }) + gestion()],
    ];
    const ancho = op.ancho === 'telefono' ? ANCHOS.telefono : 760;
    const h = ['<section>',
        '<p class="dim">Las acciones de foco (<code>componentes/casillas.ts</code>, <code>media/css/casillas.css</code>): lo que se le hace a la '
        + 'tarjeta elegida, y donde se suelta una arrastrada. Van en una <b>banda arriba de las tarjetas</b>, como la de herramientas de una lista; '
        + 'en el celular, la misma fila, abajo (elige «teléfono» arriba). Cada una, un <b>ícono en el color de lo que hace</b> (ir azul, cambiar '
        + 'amarillo, el agente violeta, hecho verde, quitar rojo, lo demás cian), <b>sin marco</b>, y su nombre en el <b>globo</b>. Van en grupos '
        + 'por lo que hacen, apartados por un corte, en el mismo orden en los dos modos (la mano aprende dónde está cada una): ver · hecha · '
        + 'la fecha y el tamaño · pasarla (instrucción, otra persona) · el primer paso y unirla · descartar. Las <b>rápidas</b> van junto a la '
        + 'suya, a un clic: hoy (si venció) y los aplazamientos junto a nueva fecha; rápida o larga junto al reloj del tamaño (el de la ficha), '
        + 'que solo dice de qué son (un <b>padre</b>, como el del orden: no se aprieta); junto a la instrucción, trabajarla (a su hilo, y te '
        + 'lleva a él) y, en concentración, bloquear tiempo, porque es una instrucción hecha. Arrastrando no hay globo: mientras dura, cada casilla dice su nombre.</p>',
        `<div class="cat-grilla" style="grid-template-columns: minmax(18ch, 24ch) repeat(${columnasElegidas().length}, ${ancho}px)">${titulos()}`];
    for (const [nombre, nota, html] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, `<div class="cat-foco">${html}</div>`));
    }
    h.push('</div></section>');
    return h.join('');
}

// ── submenú: una sección dentro de otra, con su cabecera plegable (decidido el 13-nov-2026) ──

/** HILOS con su submenú ARCHIVO, plegado o abierto, y APPS debajo para comparar con una cabecera grande. */
function listaSubmenu(abierto: boolean): string {
    const ordenes: OpcionOrden[] = [{ clave: 'urgencia', icono: I.urgencia, ayuda: 'urgencia' },
        { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre' }, { clave: 'reciente', icono: I.reloj, ayuda: 'reciente' }];
    const menu = (id: string): Accion => ({ accion: 'menu', id, icono: I.menu, ayuda: 'más' });
    const hilo = (titulo: string, inicio: (Pieza | null)[], meta: string, o: Partial<Parameters<typeof item>[0]> = {}) =>
        item({ inicio, titulo, meta: { texto: meta }, menu: menu(titulo), ...o });
    const archivados = () => hilo('puente', [S.prioridad(1, true), null, null], '2d', { apagada: true })
        + hilo('huerto', [S.prioridad(0, true), null, S.remoto('vive en servidor')], '5d', { apagada: true })
        + hilo('ensayo', [S.prioridad(2, true), null, null], '3sem', { apagada: true })
        + hilo('riego', [S.prioridad(0, true), null, null], '2m', { apagada: true });
    return secciones([seccion({ clave: '__hilos', titulo: 'hilos', cuenta: 4, ayuda: 'los hilos abiertos', abierta: true,
        nuevo: A.nuevo({ accion: 'nuevo' }, 'hilo nuevo'),
        herramientas: { grupo: 'hilos', placeholder: 'hilos', ayuda: 'buscar, también en el archivo', orden: { opciones: ordenes, activa: '' } },
        filas: () => hilo('faro', [S.prioridad(1), S.atencion('trabajando'), null], '3m')
            + hilo('molino', [S.prioridad(2), S.atencion('espera'), null], '1h', { activa: true })
            + hilo('bitácora', [null, S.atencion('termino'), null], '25m', { hondo: 1, prefijo: [{ icono: I.hijo }] })
            + hilo('cosecha', [S.prioridad(0), null, S.remoto('vive en servidor')], '1d')
            + submenu({ clave: '__archivo', titulo: 'archivo', cuenta: 4, ayuda: 'los hilos archivados', abierta: abierto, filas: archivados }) }),
    cabeceraDeSeccion({ clave: '__equipo', titulo: 'equipo', ayuda: 'las otras personas', abierta: false })]);
}

// ── el grupo entero: seccion() en cada estado ──

function seccionGrupo(): string {
    const c = columnasElegidas()[0];
    const nuevo = A.nuevo({ accion: 'nuevo' }, 'agente nuevo');
    const base = { clave: 'muestra', titulo: 'agentes', ayuda: 'los agentes', nuevo };
    const filas = () => item({ variante: 'agente', inicio: [null, S.atencion('trabajando'), null], titulo: 'Archivista', meta: { texto: '3m' } })
        + item({ variante: 'agente', apagada: true, inicio: [null, null, null], titulo: 'Cartero' });
    const vacia: Item = { apagada: true, inicio: [null], titulo: 'no tienes agentes residentes' };
    const conBanda = { grupo: 'muestra', placeholder: 'agentes', ayuda: 'buscar por nombre' };
    const muestras: [string, string, string][] = [
        ['abierta', 'la cabecera y sus filas', seccion({ ...base, cuenta: 2, abierta: true, filas })],
        ['plegada', 'solo la cabecera: las filas ni se arman', seccion({ ...base, cuenta: 2, abierta: false, filas })],
        ['con herramientas', 'la banda del buscador entre la cabecera y las filas', seccion({ ...base, cuenta: 2, abierta: true, herramientas: conBanda, filas })],
        ['vacía', 'sin filas, la fila que lo dice; sin cuenta', seccion({ ...base, abierta: true, filas: () => '', vacia })],
        ['dos seguidas', 'secciones(): el separador entre ellas; tras una plegada, nada de aire',
            secciones([seccion({ ...base, cuenta: 2, abierta: true, filas }), seccion({ ...base, titulo: 'equipo', nuevo: undefined, abierta: false, filas }),
                seccion({ ...base, titulo: 'pedidos', nuevo: undefined, abierta: true, filas: () => '', vacia: { ...vacia, titulo: 'nada esperando' } })])],
    ];
    const h = ['<section>',
        '<p class="dim">Un grupo de una lista, entero (<code>componentes/seccion.ts</code>): <code>seccion({ clave, titulo, cuenta?, ayuda, abierta, '
        + 'acciones?, nuevo?, herramientas?, filas, vacia? })</code>. Cómo dejó la persona cada cabecera lo lleva <code>Plegado</code> '
        + '(<code>plegado.abierta(clave, comoEmpieza)</code>, <code>plegado.alternar(clave)</code>), que recuerda solo las que están al revés de como '
        + 'empiezan. Da HTML plano, sin un elemento que envuelva el grupo. La barra de hilos arma así todas sus secciones. Aquí no se pliegan.</p><div class="cat-anchos">'];
    for (const [nombre, nota, html] of muestras) {
        h.push(`<div><div class="cat-tema">${esc(nombre)} · ${esc(nota)}</div>`
            + `<div class="muestra barra-de-muestra" style="width:${ANCHOS.barra}px" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${html}</div></div>`);
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionHerramientas(): string {
    const c = columnasElegidas()[0];
    const ordenes: OpcionOrden[] = [{ clave: 'urgencia', icono: I.urgencia, ayuda: 'urgencia' }, { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre' }];
    const ayuda = 'buscar por nombre', placeholder = 'hilos';
    const muestras: [string, string, string][] = [
        ['con buscador y orden', 'lo de siempre bajo la cabecera de un grupo', herramientas({ grupo: 'muestra', placeholder, ayuda, orden: { opciones: ordenes, activa: 'nombre' } })],
        ['solo el buscador', 'sin orden: la banda es el campo', herramientas({ grupo: 'muestra', placeholder, ayuda })],
        ['nada calza', 'la fila que la vista muestra cuando el filtro no deja nada (aquí, sin ocultar)', herramientas({ grupo: 'muestra', placeholder, ayuda }).replace(' hidden>', '>')],
        ['el separador', 'el aire bajo un grupo y, de borde a borde, la línea de arriba de la cabecera que sigue, en el borde de su fondo',
            item({ inicio: [null], titulo: 'la última fila de un grupo' }) + separador() + item({ variante: 'cabecera', inicio: [{ icono: I.plegado }], titulo: 'equipo' })],
    ];
    const h = ['<section>',
        '<p class="dim">Lo que va entre la cabecera de un grupo y sus filas (<code>componentes/seccion.ts</code>, <code>media/css/seccion.css</code>): '
        + 'la <b>banda de herramientas</b> (la barra del buscador, con el orden y lo que se le sume a la derecha), la fila <b>«nada calza»</b> que la vista muestra al filtrar, y el '
        + '<b>separador</b>. Lo usa la barra de hilos. Aquí no se escribe: la página real guardaría lo buscado.</p><div class="cat-anchos">'];
    for (const [nombre, nota, html] of muestras) {
        h.push(`<div><div class="cat-tema">${esc(nombre)} · ${esc(nota)}</div>`
            + `<div class="muestra barra-de-muestra" style="width:${ANCHOS.barra}px" data-tema="${c.tema.clave}" data-densidad="${c.densidad.clave}">${html}</div></div>`);
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionSubmenu(): string {
    const c = columnasElegidas()[0];
    // en tres anchos: la barra (plegado y abierto), la barra angosta y el teléfono (plegado y abierto), este con la
    // densidad del dedo
    const anchos: { que: string; px: number; abierto: boolean; densidad?: string; angosto?: boolean }[] = [
        { que: 'plegado', px: ANCHOS.barra, abierto: false }, { que: 'abierto', px: ANCHOS.barra, abierto: true },
        { que: 'barra angosta', px: 240, abierto: true },
        { que: 'teléfono, plegado', px: ANCHOS.telefono, abierto: false, densidad: 'amplia', angosto: true },
        { que: 'teléfono, abierto', px: ANCHOS.telefono, abierto: true, densidad: 'amplia', angosto: true },
    ];
    const h = ['<section class="submenu-pagina">',
        '<p class="dim">Un <b>submenú</b> es una sección dentro de otra, con su cabecera plegable: ARCHIVO dentro de HILOS, porque los '
        + 'archivados también son hilos (<code>item({ variante: \'submenu\' })</code>, <code>.item.submenu</code> en <code>item.css</code>, '
        + 'el token <code>--item-submenu</code>). Su cabecera es <b>una fila más</b> de la lista: la flecha de plegar en la última ranura, '
        + 'justo antes de los nombres, y su nombre en la columna de los nombres, en la tinta de las cabeceras, en minúscula y sin '
        + 'negrita. Ni línea ni sangría nuevas: se ve que es parte de la sección porque está en su grilla.</p><ul class="dim">'
        + '<li><b>sus filas</b> van en la misma grilla que las de arriba (la prioridad, el estado, dónde vive y el nombre, en las mismas '
        + 'columnas): son hilos. Los archivados, tenues. No se sangran: la sangría con ↳ sigue queriendo decir «hijo de».</li>'
        + '<li><b>su cuenta</b>, tenue, después del título, como en las cabeceras grandes.</li>'
        + '<li><b>se pliega</b> con un clic en toda su fila; empieza plegado; al plegar HILOS se pliega con ella. Como toda cabecera, se '
        + 'recuerda como la dejó la persona, también al recargar.</li>'
        + '<li><b>sin herramientas propias</b>: el buscar y el orden de la sección valen para él (dos buscadores en la misma '
        + 'sección confundían). Con algo escrito, se ve abierto con solo lo que calza, y esa cuenta; al borrarlo, vuelve a como '
        + 'lo dejó la persona. La cuenta de HILOS es la de los abiertos.</li>'
        + '<li><b>un solo nivel</b>: un submenú no lleva submenús adentro.</li></ul>'
        + '<p class="dim">Se eligió entre tres maneras (docs/propuestas/componentes.md, «Los submenús»); las otras eran una cabecera como las '
        + `grandes, en gris y un paso adentro, y una fila con el ícono de lo que es y la flecha al final. Aquí, con el tema «${esc(c.tema.nombre)}» `
        + '(el primero elegido arriba).</p><div class="cat-anchos">'];
    for (const a of anchos) {
        h.push(`<div><div class="cat-tema">${esc(a.que)} · ${a.px}px</div>`
            + `<div class="muestra barra-de-muestra sub-muestra${a.angosto ? ' angosto' : ''}" style="width:${a.px}px" data-ancho="${esc(a.que)}"`
            + ` data-tema="${c.tema.clave}" data-densidad="${a.densidad ?? c.densidad.clave}">${listaSubmenu(a.abierto)}</div></div>`);
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionBarra(): string {
    return '<section>'
        + '<p class="dim">La de verdad (<code>vistas/hilos.ts</code>) con hilos de mentira: agentes con y sin hilo, hijos, de otra máquina, '
        + 'viajando, abierto en dos, cerrándose, archivados. Las cabeceras se pliegan; lo demás dice qué haría.</p>'
        + `<div class="cat-grilla" style="${columnas(false)}">${titulos(false)}`
        + `${columnasElegidas().map(c => celda(c, '<div class="lista-de-muestra"></div>', 'barra-completa')).join('')}</div></section>`;
}

function seccionAvisos(): string {
    const h = ['<section>',
        '<p class="dim">La franja de avisos (<code>componentes/franja.ts</code>, <code>media/css/franja.css</code>; en la página, '
        + '<code>web/franja.ts</code>): arriba de la barra de hilos, del alto de la barra de una pantalla, así que su línea de abajo calza con la de '
        + 'la pantalla de al lado. El estado del sistema y de los hilos, no el trabajo: lo más grave en su color (rojo solo sin conexión) y con su '
        + 'ícono, «+N» los demás, y un clic abre la lista. Los avisos de mentira, en <code>componentes/muestras-avisos.ts</code>.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const f of AV.filasEstados()) {
        h.push(`<div class="cat-nombre" title="${esc(f.nota)}">${esc(f.nombre)}<span class="dim"> · ${esc(f.nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, f.html, f.alto ? 'cat-franja-alta' : 'cat-franja'));
    }
    h.push('</div></section>');
    return h.join('');
}

function seccionPantalla(): string {
    // una pantalla de mentira: su barra (la de verdad, componentes/pantalla.ts) y un cuerpo con una sección y sus filas
    const cuerpo = '<div class="cat-pantalla-cuerpo">'
        + '<div class="fila">lo de la app, con el aire dentro de cada fila</div><div class="fila dim">una fila tenue</div>'
        + '<div class="cat-pantalla-sec"><b>otra sección</b> <span class="dim">3</span></div>'
        + '<div class="fila">su línea llega a los bordes</div></div>';
    const filas: [string, string, string][] = [
        ['una app', 'su nombre en su tinta a la izquierda; a la derecha sus vistas (la que se ve, en violeta) y sus acciones', barraPantalla({
            nombre: 'tareas', color: 'cian', ayuda: '56 tareas',
            vistas: [{ accion: 'x', icono: I.foco, nombre: 'foco', si: true }, { accion: 'x', icono: I.lista, nombre: 'lista' }],
            acciones: [{ accion: 'x', icono: I.filtro, ayuda: 'un filtro', tono: 'amarillo' }, { accion: 'x', icono: I.config, ayuda: 'configurar' },
                { accion: 'x', icono: I.releer, ayuda: 'releer (r)' }] })],
        ['la de un módulo', 'una vista sin ícono propio va con su nombre; un atajo, con su tecla', barraPantalla({
            nombre: 'proyectos', color: 'verde', ayuda: '86 proyectos',
            vistas: [{ accion: 'x', icono: I.tabla, nombre: 'proyectos' }, { accion: 'x', nombre: 'gantt', si: true }],
            acciones: [{ accion: 'x', tecla: 'm', ayuda: 'un atajo: lanza un agente', tono: 'violeta' }, { accion: 'x', icono: I.releer, ayuda: 'releer (r)' }] })],
        ['una ficha', '«‹» vuelve a de donde se vino; ← → pasan a otra (cuál de cuántas, en su globo)', barraPantalla({
            volver: { accion: 'x', icono: I.atras, ayuda: 'volver a leer (⎋)' }, nombre: 'leer', color: 'magenta',
            acciones: [{ accion: 'x', icono: I.anterior, ayuda: 'la anterior (←) · 1 de 10' }, { accion: 'x', icono: I.adelante, ayuda: 'la siguiente (→) · 1 de 10' }] })],
        ['un archivo', 'el visor: su nombre tal cual, tenue (la ruta, en su globo)', barraPantalla({
            nombre: 'README.md', literal: true, ayuda: 'casa/vitrina/README.md',
            acciones: [{ accion: 'x', icono: I.lectura, tono: 'violeta', ayuda: 'leer cómodo (l)' }, { accion: 'x', icono: I.cerrar, ayuda: 'cerrar (⎋)' }] })],
        ['un hilo', 'sin nombre (lo dice la cabecera de la página): sus vistas y su carpeta, que es una ruta', barraPantalla({
            vistas: [{ accion: 'x', icono: I.terminal, nombre: 'terminal', si: true }, { accion: 'x', icono: I.lectura, nombre: 'lectura' },
                { accion: 'x', icono: I.conversacion, nombre: 'conversación' }],
            acciones: [{ accion: 'x', icono: I.carpeta, texto: 'proyectos/faro', tono: 'azul', ayuda: 'la carpeta del hilo' }] })],
    ];
    const h = ['<section>',
        '<p class="dim">Lo que llena la columna de la derecha, sea un hilo o una app del dashboard (<code>componentes/pantalla.ts</code>, '
        + '<code>pantalla.css</code>): siempre una barra arriba y su cuerpo abajo. La barra, de borde a borde con el fondo de barra y una '
        + 'línea abajo, lleva a la izquierda solo el nombre de la app en su tinta, y a la derecha sus vistas y sus acciones, con íconos en '
        + 'su celda cuadrada y una palabra solo donde un ícono no alcanza (una ruta). Nada más: ni una cuenta, ni la fecha, ni un estado '
        + '(lo que resume va en el globo del título; lo que se necesita ver, en la pantalla). El cuerpo no tiene margen propio: el aire va dentro de cada '
        + 'fila (<code>--pantalla-margen</code>, el mismo de la barra de hilos) y las líneas llegan a los bordes. La página de un módulo '
        + 'va en el cuerpo, de borde a borde, y recibe los tokens del tema (<code>docs/contratos.md</code>).</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [nombre, nota, barra] of filas) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnasElegidas()) h.push(celda(c, `<div class="cat-pantalla">${barra}${cuerpo}</div>`));
    }
    h.push('</div></section>');
    return h.join('');
}

const TOKENS: [string, string[]][] = [
    ['primitivos', ['bg', 'bg-barra', 'fg', 'dim', 'azul', 'amarillo', 'verde', 'rojo', 'magenta', 'cian', 'violeta', 'negro', 'blanco', 'blanco-claro', 'cursor']],
    ['semánticos', ['superficie', 'texto', 'texto-tenue', 'texto-apagado', 'acento', 'titulo', 'exito', 'atencion', 'peligro', 'remoto', 'agente',
        'estado-trabajando', 'estado-espera', 'estado-termino', 'prioridad-alta', 'prioridad-media', 'prioridad-baja', 'linea', 'hover', 'sel', 'seleccion']],
    ['ítem', ['item-fondo', 'item-fondo-hover', 'item-fondo-activa', 'item-enlace', 'item-agente', 'item-meta', 'item-accion', 'item-cabecera', 'item-submenu', 'item-destino']],
    ['pantalla', ['pantalla-barra-fondo', 'pantalla-nombre', 'pantalla-boton', 'pantalla-boton-hover', 'pantalla-vista-si', 'pantalla-literal']],
    ['medidas (la densidad)', ['item-alto', 'item-pad-x', 'item-ranura', 'item-texto-sangria', 'item-hondo', 'item-hueco', 'item-accion-pad', 'pantalla-margen']],
];
const MEDIDAS = new Set(TOKENS[TOKENS.length - 1][1]);

function seccionTokens(): string {
    const h = ['<section><p class="dim">Los colores de cada tema (<code>media/css/tokens.css</code>, '
        + '<code>temas.css</code>): los primitivos, lo que significa cada uno, y los del ítem; y las medidas del ítem, que son de la densidad '
        + '(<code>densidades.css</code>). El valor es el que resuelve cada columna.</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    for (const [grupo, nombres] of TOKENS) {
        h.push(`<div class="cat-grupo">${esc(grupo)}</div>`);
        for (const n of nombres) {
            h.push(`<div class="cat-nombre"><code>--${n}</code></div>`);
            const muestra = MEDIDAS.has(n) ? '' : `<span class="color" style="background: var(--${n})"></span>`;
            for (const c of columnasElegidas()) h.push(celda(c, `${muestra}<span class="valor" data-token="${n}"></span>`, 'token'));
        }
    }
    h.push('</div></section>');
    return h.join('');
}

// ── el contraste de cada tema: lo que mide `npm run prueba:temas`, con las mismas cuentas (componentes/temas.ts) ──

const FONDOS_CONTRASTE = ['bg', 'bg-barra', 'fila activa'];

function seccionContraste(): string {
    const h = ['<section><p class="dim">Cuánto se lee cada color de texto sobre los fondos donde va: el de la página (<code>--bg</code>), el de '
        + 'las barras y las ventanas (<code>--bg-barra</code>) y la fila activa (el acento al 16% sobre el fondo). Es el contraste de WCAG, '
        + `de 1 a 21; el texto normal pide ${String(MINIMO).replace('.', ',')}:1 o más (✓; si no, ✗ en rojo). Debajo, las tintas con significado `
        + '(el peligro, la atención, el éxito, el acento, lo remoto, lo de un agente, y las de los mundos y las acciones) más parecidas '
        + 'entre sí: su distancia en OKLab, por 100 (bajo 2 no se distinguen; las más cercanas del de fábrica, el verde y el cian, '
        + 'están a 7). Y cuánto de la luz del fondo y del texto es azul (un gris, un tercio). Los temas de la noche (brasa, rescoldo, '
        + 'ámbar) tienen que cumplir todo esto: lo revisa <code>npm run prueba:temas</code>, con las mismas cuentas '
        + '(<code>componentes/temas.ts</code>, <code>medir</code>).</p>',
        `<div class="cat-grilla" style="${columnas()}">${titulos()}`];
    const fila = (nombre: string, muestra: string, dato: string) => {
        h.push(`<div class="cat-nombre">${nombre}</div>`);
        for (const c of columnasElegidas()) h.push(celda(c, `${muestra}<span class="valor" data-contraste="${dato}"></span>`, 'token'));
    };
    h.push(`<div class="cat-grupo">texto sobre ${FONDOS_CONTRASTE.join(' · ')}</div>`);
    for (const t of TEXTOS) fila(`<code>--${t}</code>`, `<span class="color" style="background: var(--${t})"></span>`, `texto:${t}`);
    h.push('<div class="cat-grupo">las tintas más parecidas</div>');
    for (const i of [0, 1, 2]) fila(`${i + 1}.ª`, '', `par:${i}`);
    h.push('<div class="cat-grupo">luz azul</div>');
    fila('fondo · texto', '', 'azul');
    h.push('</div></section>');
    return h.join('');
}

/** Llena las celdas de «contraste» con lo que mide el tema de cada una (sus colores, como los resuelve). */
function llenarContraste(raiz: ParentNode): void {
    const claves = ['bg', 'bg-barra', ...TEXTOS];
    for (const v of raiz.querySelectorAll<HTMLElement>('[data-contraste]')) {
        const css = getComputedStyle(v);
        let m;
        try { m = medir(Object.fromEntries(claves.map(k => [k, css.getPropertyValue(`--${k}`).trim()]))); } catch (e) { v.textContent = String(e); continue; }
        const [que, cual] = v.dataset.contraste!.split(':');
        if (que === 'texto') {
            const razones = m.contrastes.filter(x => x.texto === cual).map(x => x.razon);
            const bien = Math.min(...razones) >= MINIMO;
            v.innerHTML = `<span class="i" style="color: var(--${bien ? 'exito' : 'peligro'})">${bien ? I.hecha : I.cerrar}</span> `
                + razones.map(r => r.toFixed(1).replace('.', ',')).join(' · ');
        } else if (que === 'par') {
            const p = m.pares[Number(cual)];
            v.innerHTML = p ? `<span style="color: var(--${p.a})">${p.a}</span> / <span style="color: var(--${p.b})">${p.b}</span> `
                + p.distancia.toFixed(1).replace('.', ',') : '';
        } else {
            const pc = (x: number) => `${Math.round(x * 100)}%`;
            v.textContent = `${pc(m.luzAzul.fondo)} · ${pc(m.luzAzul.texto)}`;
        }
    }
}

// ── táctica: el prototipo de la vista de partida (componentes/tactica.ts, docs/propuestas/orden-por-modos.md, paso 3) ──

/** La disposición que se recomienda a la persona (la primera que se ve en «estados»). */
const RECOMENDADA: Disposicion = 'lado';
/** Los anchos que se comparan: la columna de la derecha de un laptop de 1440 (la barra de hilos ocupa 22vw) y un
 *  teléfono. */
const ANCHO_LAPTOP = 1120, ANCHO_TELEFONO = 412;
/** Lo que se eligió en el catálogo: la disposición de «estados» y si la franja está abierta (solo mientras dura la página). */
let dispEstados: Disposicion = RECOMENDADA;
let franjaAbierta = false;
/** Las cuentas de Decidir desplegadas en el catálogo (sus claves; las mismas en todas las muestras). */
const cuentasAbiertas = new Set<string>();

/** Táctica en un marco: su pantalla (la barra con el número y el cuerpo), con el primer tema elegido; en el teléfono, la
 *  densidad amplia (la que pone «auto» con el dedo), y en el laptop la compacta. */
function marcoTactica(t: Tactica, px: number): string {
    const c = columnasElegidas()[0];
    const tel = px <= 700;
    return `<div class="muestra cat-tac-marco${tel ? ' angosto' : ''}" style="width: ${px}px" data-tema="${c.tema.clave}" data-densidad="${tel ? 'amplia' : 'compacta'}">`
        + `${barraPantalla(barraTactica(t))}${tactica({ ...t, abierta: franjaAbierta })}</div>`;
}

/** Una fila de muestras: el laptop y el teléfono, cada uno con su rótulo y su enlace a pantalla completa. */
function parDeMarcos(disp: Disposicion, estado: string): string {
    const e = ESTADOS_TACTICA.find(x => x.clave === estado) ?? ESTADOS_TACTICA[0];
    const t = e.tactica(disp, [...cuentasAbiertas]);
    const fig = (px: number, nombre: string) => `<figure class="cat-tac-fig"><figcaption class="dim">${esc(nombre)} · ${px}px · `
        + `<a href="#tactica/ver/${disp}/${e.clave}" target="_blank" title="la página entera, con la cabecera${px > 700 ? ' y la barra de hilos' : ''}: abrirla en una ventana de ${px}px de ancho">pantalla completa</a></figcaption>`
        + `${marcoTactica(t, px)}</figure>`;
    return `<div class="cat-tac-par">${fig(ANCHO_LAPTOP, 'laptop')}${fig(ANCHO_TELEFONO, 'teléfono')}</div>`;
}

const parrafo = (html: string) => `<p class="dim">${html}</p>`;

function seccionTactica(): string {
    const h = ['<section class="cat-tactica">',
        parrafo('<b>Prototipo.</b> Táctica es la vista de partida: contesta «¿qué hago ahora?» (<code>componentes/tactica.ts</code>, '
            + '<code>media/css/tactica.css</code>; la propuesta, <code>docs/propuestas/orden-por-modos.md</code>, paso 3). Absorbe «ahora», el foco de '
            + 'tareas y «te esperan»: <b>Ahora</b> (el bloque en curso: una reunión con su ficha, un bloque del plan con su paso, o lo libre y lo que '
            + 'cabe en ello); lo que un agente espera de la persona en <b>tres vías</b>, cada una con su tecla (1 a 3: la recorre en «Contestar»): '
            + '<b>decidir</b> (con las opciones a la vista y la recomendada marcada), <b>aprobar</b> (lo que dejó hecho, y enviar, editar o '
            + 'descartar) y <b>cerrar</b> (con su prueba); lo que el agente no dijo qué pide, <b>sin clasificar</b>, al final. En cada vía, por '
            + `cuenta (hasta ${TOPE_DECIDIR}) y por peso, con la más pesada de cada cuenta a la vista y las demás al desplegar; cada fila dice lo que `
            + 'hay que decidir, no el título. Debajo, lo contestado y lo que hizo el agente con eso. Al lado, <b>Hacer</b> (4): primero lo que un '
            + `agente pide que hagas (destraba a alguien), por cuenta y por peso; después lo de hoy (hasta ${TOPE_HACER}: la reunión si hay algo `
            + 'que preparar, el bloque del plan y las tareas, con su tamaño). Al pie, los mensajes retenidos entre hilos y todo lo demás. En toda la '
            + 'página hay <b>un solo número</b>, en la barra. El orden lo da la urgencia (pestaña «la urgencia»); el color, solo una fecha dura y '
            + 'una persona que espera hoy.'),
        parrafo('Con un día inventado, a las 11:45, en una reunión. Un clic en una fila abre la ventana de «Contestar» de verdad, sin '
            + 'contestar nada (dice qué haría); lo demás solo dice qué haría. «pantalla completa» abre la página entera (con la cabecera y su '
            + 'línea del día): para verla como se vería, en una ventana de ese ancho.')];
    for (const d of DISPOSICIONES) {
        h.push(`<h3 class="cat-tac-h">${esc(d.nombre)}${d.clave === RECOMENDADA ? ' <span class="cat-tac-reco">· la que recomiendo</span>' : ''}</h3>`,
            parrafo(esc(d.que)), parDeMarcos(d.clave, 'reunion'));
    }
    h.push('</section>');
    return h.join('');
}

function seccionTacticaEstados(): string {
    const chips = DISPOSICIONES.map(d => `<a class="chip${d.clave === dispEstados ? ' si' : ''}" data-tactica-disp="${d.clave}" title="${esc(d.que)}">${esc(d.nombre)}</a>`).join(' ');
    const h = ['<section class="cat-tactica">',
        parrafo('Táctica en cada momento del día inventado (la jornada de 8:30 a 18:00 de «el día en una línea»), con la disposición que se elija '
            + 'aquí arriba. La cabecera de la página dice la hora y lo que viene; Ahora dice lo que ella no: la ficha, el paso, lo que cabe.'),
        `<p class="cat-tac-chips"><span class="dim">disposición</span> ${chips}</p>`];
    for (const e of ESTADOS_TACTICA) {
        h.push(`<h3 class="cat-tac-h">${esc(e.nombre)}</h3>`, parrafo(esc(e.nota)), parDeMarcos(dispEstados, e.clave));
    }
    h.push('</section>');
    return h.join('');
}

function seccionTacticaUrgencia(): string {
    const si = (x: boolean | undefined) => (x ? '<span class="tono-espera">sí</span>' : '<span class="dim">—</span>');
    const o = (x: string | number | null | undefined) => (x === null || x === undefined || x === '' ? '<span class="dim">—</span>' : esc(String(x)));
    const filas = tablaUrgencia().map(f => {
        const s = f.senales;
        return `<div>${esc(f.espera.titulo)}</div><div class="dim">${esc(f.espera.clase)}</div><div>${si(s.espera)}</div><div>${o(s.peso)}</div>`
            + `<div>${o(s.persona)}</div><div>${o(s.dura)}</div><div>${o(s.dias)}</div><div>${si(s.plan)}</div>`
            + `<div class="dim">${esc(f.espera.desde.replace('T', ' ').slice(0, 16))}</div><div>${esc(f.porque)}</div>`;
    }).join('');
    return '<section class="cat-tactica">'
        + parrafo('<b>La urgencia</b> (<code>vistas/dashboard/urgencia.ts</code>) ordena con lo que declara el agente al proponer (en una tarea, al '
            + 'principio de su línea <code>[avance]</code>: <code>pide=aprobar · peso=alto (porqué) · …</code>; en una pregunta, '
            + '<code>peso: alto (porqué)</code> en su resumen; los nombres, en <code>CAMPOS</code>) y después con lo que ya sabía telar: '
            + '<b>0.</b> un hilo detenido en su turno · <b>1.</b> el peso (alto, medio, bajo; sin peso, como medio) · <b>2.</b> una persona espera · '
            + '<b>3.</b> la fecha dura más próxima · <b>4.</b> el orden de siempre: vence hoy (o venció hace 30 días o menos), el plan la puso hoy, '
            + 'vence esta semana, lo demás; y a igual cosa, lo que espera hace más. Sin nada declarado, queda el orden de siempre. Ni la prioridad de '
            + 'una tarea ni la <code>urgencia</code> de una pregunta cuentan. Lo vencido hace más de 30 días es deuda y no entra (va al filtro «deuda» de tareas), '
            + 'salvo con estrella, si alguien espera, con peso alto o con fecha dura.')
        + parrafo('Las esperas del día inventado a las 11:45, con lo que declaran sus agentes, en el orden que salen:')
        + '<div class="cat-tac-tabla"><b>qué</b><b>clase</b><b>un hilo espera</b><b>peso</b><b>persona</b><b>días a la dura</b><b>días al vence</b>'
        + `<b>el plan, hoy</b><b>desde</b><b>por qué</b>${filas}</div></section>`;
}

/** Un modo a pantalla completa (#<modo>/ver/…): su nombre en la cabecera, la hora del día inventado, su pantalla (la barra
 *  y el cuerpo) y su pestaña en DASHBOARD, la que se ve, con las que absorbe fuera de la lista. */
interface ModoEntero {
    nombre: string;
    /** la hora del día de muestra, en minutos: la dice la línea del día de la cabecera */
    ahora: number;
    /** la barra de su pantalla y su cuerpo, ya armados */
    pantalla: string;
    titulo: string;
    /** las pestañas de DASHBOARD en la barra de hilos de muestra, y la que se ve (la suya) */
    pestanas: PestanaDashboard[];
    activa: string;
    /** arriba de la barra, la franja de avisos (componentes/franja.ts), ya armada; y su punto, en «‹ hilos» del teléfono */
    franja?: string;
    punto?: string;
    /** la barra plegada (sin montar la de verdad: plegarla cambiaría el modo de la página de verdad) */
    plegada?: boolean;
    /** en el teléfono, la lista (la barra) en vez del detalle */
    lista?: boolean;
}

/** La página entera de un modo, a lo ancho de la ventana (para las capturas): la cabecera con su línea del día y, en un
 *  laptop, la barra de hilos (la de verdad, con hilos de mentira) a la izquierda de la pantalla del modo; en un teléfono,
 *  el detalle (o la lista). */
function paginaDeModo(m: ModoEntero, tel: boolean): string {
    const c = columnasElegidas()[0];
    const lista = tel && !!m.lista;
    const filas = m.plegada
        ? '<div class="lista-plegada"><div id="lista"><div class="plegada" data-accion="franja-desplegar" title="mostrar la barra de hilos"><span class="pliegue-barra">›</span><span class="vertical">hilos</span></div></div></div>'
        : '<div class="lista-de-muestra"></div>';
    const barra = `<div class="muestra barra-de-muestra cat-tac-barra" data-modo-entero="1">${m.franja ?? ''}${filas}</div>`;
    return `<div class="muestra cat-tac-pagina${tel ? ' angosto' : ''}${m.plegada && !tel ? ' con-plegada' : ''}" data-tema="${c.tema.clave}" data-densidad="${tel ? 'amplia' : 'compacta'}">`
        + cabeceraInterna(diaDeMuestra(m.ahora), lista ? '' : m.nombre, tel && !lista, tel && !lista ? m.punto : '')
        + `<div class="cat-tac-cuerpo">${!tel || lista ? barra : ''}`
        + `${lista ? '' : `<div class="cat-tac-columna">${m.pantalla}</div>`}</div></div>`;
}

/** La pestaña de Táctica en DASHBOARD, la primera: absorbe «ahora» y «te esperan». */
const PESTANA_TACTICA: PestanaDashboard = { clave: 'tactica', accion: 'pantalla', valor: 'tactica', nombre: 'táctica', tecla: 'a' };
const pestanasSin = (...fuera: string[]) => BARRA.pestanas.filter(x => !fuera.includes(x.clave));

/** Los modos que se ven a pantalla completa: cada uno arma lo suyo con lo que sigue a #<modo>/ver/ (`null`, si no le
 *  sirve). */
const MODOS_ENTEROS: Record<string, (resto: string[]) => ModoEntero | null> = {
    // #tactica/ver/<disposición>/<estado>
    tactica: ([disp, estado]) => {
        if (!DISPOSICIONES.some(d => d.clave === disp)) return null;
        const e = ESTADOS_TACTICA.find(x => x.clave === estado) ?? ESTADOS_TACTICA[0];
        const t = { ...e.tactica(disp as Disposicion, [...cuentasAbiertas]), abierta: franjaAbierta };
        const hora = new Date(e.datos.ahora);
        return { nombre: 'táctica', ahora: hora.getHours() * 60 + hora.getMinutes(), pantalla: `${barraPantalla(barraTactica(t))}${tactica(t)}`,
            titulo: `táctica · ${disp} · ${e.clave}`, pestanas: [PESTANA_TACTICA, ...pestanasSin('ahora', 'esperas')], activa: 'tactica' };
    },
};

// #avisos/ver/<escena>[/abierta|/plegada|/hilo]: la página entera con la franja de avisos de una escena, y Táctica (en una
// reunión) a la derecha. En el teléfono, la lista con la franja arriba; con «/hilo», un hilo a la vista y el punto en «‹ hilos»
MODOS_ENTEROS.avisos = ([clave, extra = '']) => {
    const f = AV.enLaPagina(clave, extra);
    const tac = MODOS_ENTEROS.tactica(['lado', 'reunion']);
    if (!f || !tac) return null;
    return { ...tac, titulo: `avisos · ${f.nombre}${extra ? ` · ${extra}` : ''}`, franja: f.franja, punto: f.punto,
        plegada: extra === 'plegada', lista: extra !== 'hilo' };
};

// #rutinas/ver/vista: «tareas › rutinas» (prototipo, catalogo-rutinas.ts) como la página entera, el jueves inventado a las
// 10:30: en un laptop con la barra de hilos, en un teléfono la pantalla sola
MODOS_ENTEROS.rutinas = () => ({ nombre: 'tareas', ahora: RU.AHORA_MIN, pantalla: `<div class="cat-rut-pantalla">${RU.pantalla()}</div>`,
    titulo: 'tareas · rutinas (prototipo)', pestanas: BARRA.pestanas, activa: 'tareas' });

/** «tareas › rutinas» en un marco (catalogo-rutinas.ts), como Táctica: el primer tema elegido; en el teléfono, la densidad
 *  amplia. */
function marcoRutinas(html: string, px: number): string {
    const c = columnasElegidas()[0];
    const tel = px <= 700;
    return `<div class="muestra cat-tac-marco cat-rut-pantalla${tel ? ' angosto' : ''}" style="width: ${px}px" data-tema="${c.tema.clave}" data-densidad="${tel ? 'amplia' : 'compacta'}">${html}</div>`;
}

// #equipo/ver/<persona|lista>/<ficha|apreciaciones>[/traidas]: el prototipo de la vista «equipo» (catalogo-equipo.ts), con
// su pestaña en DASHBOARD
const PESTANA_EQUIPO: PestanaDashboard = { clave: 'equipo', accion: 'pantalla', valor: 'equipo', nombre: 'equipo', tecla: '' };
MODOS_ENTEROS.equipo = resto => {
    const e = conEquipo(() => EQ.entera(resto, window.innerWidth <= 700));
    return e ? { nombre: 'equipo', ahora: 11 * 60 + 40, pantalla: e.pantalla, titulo: e.titulo, pestanas: [...BARRA.pestanas, PESTANA_EQUIPO], activa: 'equipo' } : null;
};

/** Lo que pide la dirección para la página entera de un modo: #<modo>/ver/…. */
function modoEntero(): ModoEntero | null {
    const m = /^#([a-z]+)\/ver\/(.*)$/.exec(decodeURIComponent(location.hash));
    return m ? MODOS_ENTEROS[m[1]]?.(m[2].split('/')) ?? null : null;
}

/** Lo que dice un clic en Táctica que no abre nada de verdad. */
const DICE_TACTICA: Record<string, (id: string) => string> = {
    'tactica-todo': id => `iría a Todo${id ? ` (${id})` : ''}: sin filtros ni topes, con un buscador`,
    'tactica-ver': id => `abriría ${id} donde vive`,
    'tactica-tarea': id => `abriría la ficha de ${id}`,
    'tactica-hecha': id => `marcaría ${id} hecha`,
    'tactica-evento': () => 'abriría la reunión en el calendario, con su preparación',
    'tactica-ahora': () => 'abriría lo de ahora: la reunión en el calendario, con su ficha entera',
    'tactica-entrar': () => 'entraría a la llamada',
    'tactica-preparacion': () => 'abriría la preparación',
    'tactica-minuta': () => 'abriría la minuta anterior',
    'tactica-trabajar': () => 'llevaría el bloque a su hilo, con el paso escrito',
    'tactica-releer': () => 'volvería a leer',
    'tactica-fecha': v => `elegiría otra fecha para ${(/"([A-Za-z]+\d+)"/.exec(v) ?? [])[1] ?? 'la tarea'} (la lista de siempre)`,
    'tactica-ensayo': () => 'ensayo: no se hizo nada',
    'tactica-revisar': id => `le encargaría ${id} ahora al agente que escribe los avances, sin esperar la próxima pasada (en la tarea queda «prompt: revisar ya»)`,
    'tactica-via': via => `recorrería ${via === 'sin-clasificar' ? 'lo sin clasificar' : via === 'hacer-tu' ? 'lo que te piden hacer' : `la vía «${via}»`} en «Contestar», una tras otra (también con su tecla)`,
};

/** Lo que llega elegido en «Contestar» desde lo que va bajo una fila de Táctica (una opción, enviar/editar/descartar,
 *  confirmar un cierre), como en la página. */
function inicialDe(accion: string, valor: string): { id: string; inicial: { opcion?: string; otra?: boolean } } | null {
    const [id, que] = accion === 'tactica-cerrar' ? [valor, 'cerrar'] : (JSON.parse(valor) as string[]);
    if (accion === 'tactica-opcion' || accion === 'tactica-cerrar') return { id, inicial: { opcion: que } };
    if (accion === 'tactica-aprobar') return { id, inicial: que === 'editar' ? { otra: true } : { opcion: que === 'descartar' ? APROBAR.descartar : APROBAR.enviar } };
    return null;
}

/** Un clic en Táctica: una fila de una vía abre «Contestar» de verdad, en ensayo (no contesta nada); la franja se abre y
 *  se cierra, y una cuenta se despliega; lo demás dice qué haría. */
function atenderTactica(el: HTMLElement): void {
    const accion = el.dataset.accion ?? '', id = el.dataset.id ?? el.dataset.valor ?? '';
    if (accion === 'tactica-franja') { franjaAbierta = id === 'abrir'; pintar(); return; }
    if (accion === 'tactica-cuenta') { if (cuentasAbiertas.has(id)) cuentasAbiertas.delete(id); else cuentasAbiertas.add(id); pintar(); return; }
    const desdeFila = inicialDe(accion, id);
    if (accion === 'tactica-contestar' || desdeFila) {
        const dir = desdeFila?.id ?? id;
        if (dir.startsWith('cuenta:')) { avisar('abriría «Contestar» con las de la cuenta, una tras otra'); return; }
        if (dir.startsWith('via:')) { avisar(DICE_TACTICA['tactica-via'](dir.slice(4))); return; }
        const e = esperaDe(dir);
        if (!e) { avisar(`abriría «Contestar» con ${dir}`); return; }
        void import('../web/contestar').then(m => m.abrirContestar(e, m.hacerDeEnsayo({ decir: avisar }), Date.now(), desdeFila?.inicial ?? {}))
            .then(dice => { if (dice) avisar(dice); });
        return;
    }
    avisar(DICE_TACTICA[accion]?.(id) ?? `haría «${accion}»${id ? ` con ${id}` : ''}`);
}

// ── la lista de componentes, en orden jerárquico: cada uno se arma con los de arriba ──

/** Una pestaña de la página de un componente; sin `dibujar`, está por hacer (`falta` dice qué mostrará). */
interface Pestana { clave: string; nombre: string; dibujar?: () => string; falta?: string }
interface Pagina {
    clave: string; nombre: string; grupo: string;
    /** dentro de qué página va en la lista (se ve con sangría) */
    padre?: string;
    /** lo que hay: sus pestañas (se abre la primera que está hecha). Sin esto, el componente está por hacer. */
    pestanas?: Pestana[];
    /** por hacer: el paso del «Orden de trabajo» (docs/propuestas/componentes.md) y lo que hoy hace su trabajo */
    paso?: number; hoy?: string;
}
/** Las de todo componente: él en cada estado, y sus partes. */
const estados = (dibujar: () => string): Pestana => ({ clave: 'estados', nombre: 'estados', dibujar });
const anatomia = (dibujar?: () => string, falta?: string): Pestana => ({ clave: 'anatomia', nombre: 'anatomía', dibujar, falta });
const GRUPOS: [string, string][] = [
    ['fundamentos', 'de qué está hecho el diseño: la gramática visual (rectángulos y círculos, qué dice cada forma), el círculo y los valores'],
    ['piezas', 'lo más chico con función propia'],
    ['compuestos', 'piezas juntas: el ítem, y lo que se arma con él'],
    ['secciones', 'un trozo de lista, con su fondo y su separador'],
    ['contenedores', 'lo que sostiene secciones: la barra, la pantalla (un hilo, una app), las ventanas'],
];
const PAGINAS: Pagina[] = [
    { clave: 'forma', nombre: 'gramática visual', grupo: 'fundamentos', pestanas: [{ clave: 'forma', nombre: 'forma', dibujar: seccionForma }] },
    { clave: 'redondo', nombre: 'lo redondo', grupo: 'fundamentos', padre: 'forma', pestanas: [{ clave: 'redondo', nombre: 'lo redondo', dibujar: seccionRedondo }] },
    { clave: 'recto', nombre: 'lo recto', grupo: 'fundamentos', padre: 'forma', pestanas: [{ clave: 'recto', nombre: 'lo recto', dibujar: seccionRecto }] },
    { clave: 'derivadas', nombre: 'derivadas', grupo: 'fundamentos', padre: 'forma', pestanas: [{ clave: 'derivadas', nombre: 'derivadas', dibujar: seccionDerivadas }] },
    { clave: 'circulo', nombre: 'círculo', grupo: 'fundamentos', pestanas: [estados(seccionCirculo), anatomia(undefined, 'tamaño, llenado, figura y movimiento: cómo se dibuja cada uno')] },
    { clave: 'tokens', nombre: 'tokens', grupo: 'fundamentos', pestanas: [{ clave: 'valores', nombre: 'valores', dibujar: seccionTokens },
        { clave: 'contraste', nombre: 'contraste', dibujar: seccionContraste }] },
    { clave: 'icono', nombre: 'ícono', grupo: 'piezas', paso: 2, hoy: 'la letra de íconos de `web/iconos.ts`; sin página propia todavía' },
    { clave: 'accion', nombre: 'acción', grupo: 'piezas', paso: 5, hoy: 'las acciones del ítem (`.item-accion`) y los enlaces `data-accion` de las hojas' },
    { clave: 'botones', nombre: 'botones', grupo: 'piezas', pestanas: [{ clave: 'forma', nombre: 'la tecla en el pie', dibujar: seccionBotones },
        estados(seccionBotonesEstados), { clave: 'foco', nombre: 'el foco y ⏎', dibujar: seccionBotonesFoco },
        { clave: 'hoy', nombre: 'las que destruyen', dibujar: seccionBotonesHoy }] },
    { clave: 'chip', nombre: 'chip', grupo: 'piezas', paso: 2, hoy: '`.chip` del propio catálogo; falta ver si las pestañas del dashboard son lo mismo' },
    { clave: 'campo', nombre: 'campo', grupo: 'piezas', paso: 4, hoy: 'el input subrayado repetido seis veces en `dia.css`, `hilos.css` y `configuracion.css`' },
    { clave: 'interruptor', nombre: 'interruptor', grupo: 'piezas', paso: 2, hoy: 'por revisar en la configuración' },
    { clave: 'nuevo', nombre: 'nuevo (+)', grupo: 'piezas', pestanas: [estados(seccionNuevo), anatomia(undefined, 'el + y su lugar en la cabecera')] },
    { clave: 'partes', nombre: 'partes', grupo: 'piezas', pestanas: [estados(seccionPartes), anatomia(undefined, 'la franja, cada parte, su raya y la abierta')] },
    { clave: 'jornada', nombre: 'el día en una línea', grupo: 'compuestos', pestanas: [estados(seccionJornada),
        { clave: 'cabecera', nombre: 'en la cabecera', dibujar: seccionJornadaEnCabecera }, anatomia(undefined, 'la barra, la raya de ahora y el texto')] },
    { clave: 'item', nombre: 'ítem', grupo: 'compuestos', pestanas: [estados(seccionItem), anatomia(seccionAnatomia)] },
    { clave: 'tarjeta', nombre: 'tarjeta', grupo: 'compuestos', pestanas: [estados(seccionTarjeta), anatomia(() => seccionAnatomia('tarjeta'))] },
    { clave: 'buscador', nombre: 'buscador', grupo: 'compuestos', pestanas: [estados(seccionBuscador),
        { clave: 'bordes', nombre: 'bordes', dibujar: seccionBordesBuscador }, anatomia(seccionAnatomiaBuscador),
        { clave: 'donde', nombre: 'dónde está', dibujar: seccionDondeBuscador }] },
    { clave: 'casillas', nombre: 'casillas', grupo: 'compuestos', pestanas: [estados(seccionCasillas)] },
    { clave: 'pestanas', nombre: 'pestañas', grupo: 'compuestos', pestanas: [estados(() => CP.seccionEstados(columnasElegidas(), celda, titulos(), anchas())),
        { clave: 'donde', nombre: 'dónde está', dibujar: CP.seccionDonde }, anatomia(undefined, 'la fila, cada pestaña (ícono, nombre, cuenta, lo nuevo) y su extremo')] },
    { clave: 'mensaje', nombre: 'barra de mensaje', grupo: 'compuestos', pestanas: [estados(() => CMS.seccionEstados(columnasElegidas(), celda, titulos(), anchas())),
        { clave: 'lista', nombre: 'la lista', dibujar: () => CMS.seccionLista(columnasElegidas(), celda, titulos(), anchas()) },
        { clave: 'donde', nombre: 'dónde va', dibujar: CMS.seccionDonde }, anatomia(undefined, 'el destino, el campo, enviar y lo último que pasó')] },
    { clave: 'orden', nombre: 'orden', grupo: 'compuestos', pestanas: [estados(seccionOrden), anatomia(undefined, 'el ícono padre, las opciones y los dos cortes')] },
    { clave: 'filtros', nombre: 'filtros', grupo: 'compuestos', pestanas: [estados(seccionFiltros),
        { clave: 'tareas', nombre: 'en «tareas»', dibujar: seccionFiltrosEnTareas }, anatomia(undefined, 'el ícono padre, los grupos y sus opciones')] },
    { clave: 'seccion', nombre: 'sección de lista', grupo: 'secciones', pestanas: [{ clave: 'grupo', nombre: 'el grupo', dibujar: seccionGrupo },
        anatomia(() => seccionAnatomia('seccion')), { clave: 'submenu', nombre: 'submenú', dibujar: seccionSubmenu },
        { clave: 'herramientas', nombre: 'herramientas', dibujar: seccionHerramientas }] },
    { clave: 'avisos', nombre: 'franja de avisos', grupo: 'secciones', pestanas: [estados(seccionAvisos),
        { clave: 'pagina', nombre: 'en la página', dibujar: AV.seccionPagina }, { clave: 'fuentes', nombre: 'de dónde sale', dibujar: AV.seccionFuentes }] },
    { clave: 'barra', nombre: 'barra de hilos', grupo: 'contenedores', pestanas: [estados(seccionBarra), anatomia(undefined, 'sus secciones, una tras otra (cada una, en «sección de lista»)')] },
    { clave: 'pantalla', nombre: 'pantalla', grupo: 'contenedores', pestanas: [estados(seccionPantalla)] },
    { clave: 'ventana', nombre: 'ventana (modal)', grupo: 'contenedores', pestanas: [estados(seccionVentana), anatomia(undefined, 'cabecera, campo, cuerpo y pie; los tres lugares')] },
    { clave: 'mundos', nombre: 'ventana de mundos', grupo: 'contenedores', padre: 'ventana', pestanas: [
        estados(() => CM.seccionEstados(columnasElegidas(), celda, nombreColumna)),
        { clave: 'artes', nombre: 'los artes', dibujar: () => CM.seccionArtes(columnasElegidas()[0], celda) },
        { clave: 'probar', nombre: 'probar uno', dibujar: () => CM.seccionProbar(columnasElegidas()[0], celda) }] },
    { clave: 'contestar', nombre: 'contestar', grupo: 'contenedores', padre: 'ventana', pestanas: [estados(seccionContestar), anatomia(undefined, 'resumen, lo plegado, las opciones, «Otra cosa…» y el pie')] },
    { clave: 'tactica', nombre: 'táctica (prototipo)', grupo: 'contenedores', pestanas: [{ clave: 'disposiciones', nombre: 'disposiciones', dibujar: seccionTactica },
        estados(seccionTacticaEstados), { clave: 'urgencia', nombre: 'la urgencia', dibujar: seccionTacticaUrgencia }] },
    { clave: 'rutinas', nombre: 'rutinas (prototipo)', grupo: 'contenedores', pestanas: [
        { clave: 'vista', nombre: 'la vista', dibujar: () => RU.seccionVista(marcoRutinas) },
        { clave: 'calculo', nombre: 'cómo se calcula', dibujar: RU.seccionCalculo },
        { clave: 'archivo', nombre: 'el archivo', dibujar: RU.seccionArchivo }] },
    { clave: 'equipo', nombre: 'equipo (prototipo)', grupo: 'contenedores', pestanas: [
        { clave: 'vista', nombre: 'la vista', dibujar: () => conEquipo(EQ.seccionVista) },
        estados(() => conEquipo(EQ.seccionEstados)),
        { clave: 'privacidad', nombre: 'privacidad', dibujar: () => conEquipo(EQ.seccionPrivacidad) },
        { clave: 'fuentes', nombre: 'de dónde sale', dibujar: () => conEquipo(EQ.seccionFuentes) },
        { clave: 'donde', nombre: 'dónde vive', dibujar: () => conEquipo(EQ.seccionDonde) }] },
    { clave: 'modos-mundos', nombre: 'modos y mundos (prototipo)', grupo: 'contenedores', pestanas: [
        { clave: 'controles', nombre: 'dónde se cambian', dibujar: () => conModos(MM.seccionControles) },
        { clave: 'cambia', nombre: 'qué cambia cada modo', dibujar: () => conModos(MM.seccionCambia) },
        { clave: 'todo', nombre: 'todo', dibujar: () => conModos(MM.seccionTodo) },
        { clave: 'mundo', nombre: 'el mundo', dibujar: () => conModos(MM.seccionMundo) },
        { clave: 'migracion', nombre: 'los modos de hoy', dibujar: () => conModos(MM.seccionMigracion) }] },
];
// las direcciones de antes de las pestañas
const ANTES: Record<string, string> = {
    anatomia: 'item/anatomia', 'circulo/decidir': 'derivadas', palabras: 'redondo', composicion: 'redondo', modos: 'redondo', rectangulos: 'recto',
    'filtros/propuesta': 'filtros/tareas', 'jornada/propuesta': 'jornada/cabecera',
};

/** Lo que pide la dirección: #componente o #componente/pestaña (sin pestaña, o una por hacer: la primera hecha). */
function elegida(): { pag: Pagina; pes?: Pestana } {
    const h = decodeURIComponent(location.hash.slice(1));
    const [k, p] = (ANTES[h] ?? h).split('/');
    const pag = PAGINAS.find(x => x.clave === k) ?? PAGINAS.find(x => x.clave === 'item')!;
    const hechas = pag.pestanas?.filter(x => x.dibujar) ?? [];
    return { pag, pes: hechas.find(x => x.clave === p) ?? hechas[0] };
}

function lista(actual: Pagina): string {
    return '<nav class="cat-lista">' + GRUPOS.map(([g, que]) =>
        `<div class="cat-lista-grupo" title="${esc(que)}">${esc(g)}</div>`
        + PAGINAS.filter(x => x.grupo === g).map(x =>
            `<a href="#${x.clave}" class="${x === actual ? 'si' : ''}${x.pestanas ? '' : ' falta'}${x.padre ? ' n2' : ''}"${x.pestanas ? '' : ` title="por hacer: paso ${x.paso}"`}>${esc(x.nombre)}</a>`).join('')
    ).join('') + '</nav>';
}

/** Las pestañas de un componente, si tiene más de una (componentes/pestanas.ts, la de la página); las por hacer,
 *  apagadas. */
function pestanas(pag: Pagina, actual: Pestana): string {
    if ((pag.pestanas?.length ?? 0) < 2) return '';
    return filaPestanas({ nombre: `pestañas de ${pag.nombre}`, activa: actual.clave, clases: ['cat-pestanas'],
        pestanas: pag.pestanas!.map(p => ({ valor: p.clave, nombre: p.nombre, href: `#${pag.clave}/${p.clave}`,
            ...(p.dibujar ? {} : { apagada: true, ayuda: `por hacer${p.falta ? `: ${p.falta}` : ''}` }) })) });
}

/** La página de un componente: su nombre, sus pestañas y la elegida; o, si falta, lo que se sabe de él. */
const pagina = (pag: Pagina, pes?: Pestana): string => pes?.dibujar
    ? `<h2>${esc(pag.nombre)}</h2>${pestanas(pag, pes)}${pes.dibujar()}`
    : porHacer(pag);

/** La página de un componente que falta: qué es, en qué paso se hace y qué hace hoy su trabajo. */
function porHacer(p: Pagina): string {
    return `<section><h2>${esc(p.nombre)}</h2><p class="dim">Por hacer: paso ${p.paso} del orden de trabajo (<code>docs/propuestas/componentes.md</code>).</p>`
        + `<p>Hoy: ${esc(p.hoy ?? '').replace(/`([^`]+)`/g, '<code>$1</code>')}.</p>`
        + `<p class="dim">Su inventario completo, con dónde aparece cada variante, está en la sección «Inventario» de la propuesta.</p></section>`;
}

function pintar(): void {
    const raiz = document.getElementById('catalogo')!;
    // la barra lleva a la vista su fila marcada: aquí eso movería la página entera, así que se vuelve adonde estaba
    const y = window.scrollY;
    barras.length = 0;
    // modos y mundos a pantalla completa (#modos-mundos/ver/…, catalogo-modos.ts): la barra, con el mundo puesto
    MM.antesDePintar();
    if (MM.entera()) { pintarModos(MM.entera()!); return; }
    // un modo a pantalla completa (#<modo>/ver/…): la página entera, sin el catálogo alrededor
    const entera = modoEntero();
    document.body.classList.toggle('cat-entera', !!entera);
    if (entera) {
        raiz.innerHTML = `${paginaDeModo(entera, window.innerWidth <= 700)}<div id="cat-aviso" hidden></div>`;
        document.title = `telar · ${entera.titulo}`;
    } else {
        const { pag, pes } = elegida();
        raiz.innerHTML = cabecera()
            + `<div class="cat-cuerpo">${lista(pag)}<main class="${op.anatomia ? 'ver-anatomia' : ''}">${pagina(pag, pes)}</main></div>`
            + '<div id="cat-aviso" hidden></div>';
        document.title = `telar · componentes · ${pag.nombre}${pes && (pag.pestanas?.length ?? 0) > 1 ? ` · ${pes.nombre}` : ''}`;
    }
    // las barras de verdad, una por tema; la de un modo a pantalla completa, con su pestaña a la vista en DASHBOARD (la de
    // Táctica absorbe «ahora» y «te esperan»)
    for (const el of raiz.querySelectorAll<HTMLElement>('.lista-de-muestra')) {
        const b = new BarraHilos();
        b.estado = memoria();
        b.aqui = BARRA.aqui;
        b.mostrado = BARRA.mostrado;
        b.otras = BARRA.otras;
        b.pestanasDashboard = () => BARRA.pestanas;
        if (entera && el.closest('[data-modo-entero]')) {
            b.pestanasDashboard = () => entera.pestanas;
            b.dashboardActivo = true;
            b.pestanaActiva = entera.activa;
        }
        b.montar(el);
        barras.push(b);
    }
    window.scrollTo(0, y);
    // las pestañas que no caben (las de la página y las de muestra que no las fuerzan) y el alto de cada barra de mensaje
    acomodarTodas(raiz);
    mensajesAlPintar(raiz);
    // la lámina se traza con el ítem ya dibujado, y de nuevo cuando llega la letra de los íconos (cambia los anchos)
    trazarLaminas();
    void document.fonts?.ready.then(trazarLaminas);
    // el valor de cada token, como lo resuelve su tema
    for (const v of raiz.querySelectorAll<HTMLElement>('[data-token]')) {
        v.textContent = getComputedStyle(v).getPropertyValue(`--${v.dataset.token}`).trim();
    }
    // y lo que mide cada tema: su contraste, sus tintas más parecidas, su luz azul
    llenarContraste(raiz);
    // el arte de la ventana de mundos, vivo (y el de antes, quieto)
    CM.despuesDePintar(raiz);
}

let avisoHasta = 0;
function avisar(texto: string): void {
    const a = document.getElementById('cat-aviso');
    if (!a) return;
    a.textContent = texto;
    a.hidden = false;
    avisoHasta = Date.now() + 2500;
    setTimeout(() => { if (Date.now() >= avisoHasta) a.hidden = true; }, 2600);
}

// lo que la barra hace sola (plegar un grupo, ordenar, la columna de máquinas) se deja pasar; lo demás (ir a un hilo,
// archivar, plegar la barra, que cambiaría el modo de la página de verdad) se para aquí y se dice
const DE_LA_BARRA = new Set(['seccion', 'orden-grupo', 'ver-maquina']);

document.addEventListener('click', e => {
    const t = e.target as HTMLElement;
    const sel = t.closest<HTMLElement>('[data-tema-sel]');
    if (sel) {
        const k = sel.dataset.temaSel!;
        op.temas = op.temas.includes(k) ? op.temas.filter(x => x !== k) : todosLosTemas().map(x => x.clave).filter(x => x === k || op.temas.includes(x));
        if (!op.temas.length) op.temas = [k];
        guardar(); pintar(); return;
    }
    const dens = t.closest<HTMLElement>('[data-dens-sel]');
    if (dens) {
        const k = dens.dataset.densSel!;
        op.densidades = op.densidades.includes(k) ? op.densidades.filter(x => x !== k) : DENSIDADES.map(x => x.clave).filter(x => x === k || op.densidades.includes(x));
        if (!op.densidades.length) op.densidades = [k];
        guardar(); pintar(); return;
    }
    const ancho = t.closest<HTMLElement>('[data-ancho]');
    if (ancho) { op.ancho = ancho.dataset.ancho as Opciones['ancho']; guardar(); pintar(); return; }
    if (t.closest('[data-anatomia]')) { op.anatomia = !op.anatomia; guardar(); pintar(); return; }
    const props = t.closest<HTMLElement>('[data-props]');
    if (props) {
        const pre = document.querySelector<HTMLElement>(`[data-props-de="${props.dataset.props}"]`);
        if (pre) pre.hidden = !pre.hidden;
        return;
    }
    // la ventana de contestar, de verdad, con una espera de mentira: no contesta nada, dice qué haría
    const ensayo = t.closest<HTMLElement>('[data-ensayo-contestar]');
    if (ensayo) {
        const clase = ensayo.dataset.ensayoContestar ?? 'decide', cambio = !!ensayo.dataset.cambio;
        void import('../web/contestar').then(m => m.abrirContestar(esperasDeMuestra()[clase], m.hacerDeEnsayo({ cambio, decir: avisar })))
            .then(dice => { if (dice) avisar(dice); });
        return;
    }
    // una ventana de confirmar de verdad (`preguntar`): no hace nada, dice qué se apretó
    const pb = t.closest<HTMLElement>('[data-probar-boton]');
    if (pb) {
        const c = columnasElegidas()[0];
        void BT.probar(pb.dataset.probarBoton ?? 'borrar', c.tema.clave, c.densidad.clave, avisar);
        return;
    }
    const disp = t.closest<HTMLElement>('[data-tactica-disp]');
    if (disp) { dispEstados = disp.dataset.tacticaDisp as Disposicion; pintar(); return; }
    const fr = t.closest<HTMLElement>('[data-accion^="franja-"]');
    if (fr?.closest('.muestra')) {
        e.stopPropagation(); e.preventDefault();
        // en la página entera, la franja se abre y se cierra de verdad (en la dirección: /abierta)
        const m = /^#avisos\/ver\/([^/]+)(?:\/([a-z]+))?$/.exec(decodeURIComponent(location.hash));
        if (m && fr.dataset.accion === 'franja-abrir') { history.replaceState(null, '', `#avisos/ver/${m[1]}${m[2] === 'abierta' ? '' : '/abierta'}`); pintar(); return; }
        // y la barra se pliega con el ‹ de la franja y se abre con su franja angosta (en la dirección: /plegada)
        if (m && (fr.dataset.accion === 'franja-plegar' || fr.dataset.accion === 'franja-desplegar')) {
            history.replaceState(null, '', `#avisos/ver/${m[1]}${fr.dataset.accion === 'franja-plegar' ? '/plegada' : ''}`); pintar(); return;
        }
        avisar(AV.dice(fr));
        return;
    }
    // la ventana de mundos: una tarjeta o un botón de muestra dicen qué harían; «probar» la abre de verdad
    if (CM.atender(t, avisar)) { e.stopPropagation(); e.preventDefault(); return; }
    // una barra de mensaje de muestra: enviar, elegir a quién y abrir a quién fue dicen qué harían
    const ms = CMS.dice(t);
    if (ms) { e.stopPropagation(); e.preventDefault(); avisar(ms); return; }
    const eq = t.closest<HTMLElement>('[data-accion^="eq-"]');
    if (eq?.closest('.muestra') && conEquipo(() => EQ.atender(eq))) { e.stopPropagation(); e.preventDefault(); return; }
    const tac = t.closest<HTMLElement>('[data-accion^="tactica-"]');
    if (tac?.closest('.muestra')) { e.stopPropagation(); e.preventDefault(); atenderTactica(tac); return; }
    // las rutinas (prototipo): una sección se pliega y el filtro rige; lo demás dice qué haría
    if (t.closest('.muestra') && RU.atender(t, avisar, pintar)) { e.stopPropagation(); e.preventDefault(); return; }
    const mm = t.closest<HTMLElement>('[data-accion^="modos-"],[data-accion^="todo-"]');
    if (mm && conModos(() => MM.atender(mm))) { e.stopPropagation(); e.preventDefault(); return; }
    const muestra = t.closest('.muestra');
    if (!muestra) return;
    const f = t.closest<HTMLElement>('[data-hilo],[data-accion]');
    const accion = f?.dataset.accion;
    if (accion && DE_LA_BARRA.has(accion) && muestra.classList.contains('barra-completa')) {
        // el archivo se abre con una orden de la página: aquí, en todas las barras
        if (accion === 'seccion' && f?.dataset.id === '__archivo') { e.stopPropagation(); for (const b of barras) b.alternarArchivo(); }
        return;
    }
    e.stopPropagation();
    e.preventDefault();
    if (f) avisar(accion ? `haría «${accion}»${f.dataset.id ? ` con ${f.dataset.id}` : ''}` : `iría al hilo ${f.dataset.hilo}`);
}, true);

// el menú del clic derecho, arrastrar y escribir en un buscador: no aquí (escribir guardaría lo buscado en la página de verdad)
for (const ev of ['contextmenu', 'dragstart', 'input', 'keydown']) {
    document.addEventListener(ev, e => {
        if (!(e.target as HTMLElement).closest?.('.muestra')) return;
        e.stopPropagation();
        if (ev !== 'keydown') e.preventDefault();
    }, true);
}

// los temas propios de esta máquina (⚙ temas) también se comparan, con sus colores; los de fábrica, como vienen. Cuando
// llegan de la configuración (o cambian), la barra de temas y las columnas se rehacen
colores.alCambiar(() => pintar());
colores.montar({ soloPropios: true });
// las pestañas de cada componente, con ← → (web/pestanas.ts, el mismo de la página)
atenderPestanas();
pintar();
window.addEventListener('hashchange', () => { pintar(); window.scrollTo(0, 0); });
// un modo a pantalla completa: el laptop o el teléfono los decide el ancho de la ventana
let anchoAntes = window.innerWidth;
window.addEventListener('resize', () => {
    const cruzo = (anchoAntes <= 700) !== (window.innerWidth <= 700);
    anchoAntes = window.innerWidth;
    if (cruzo && modoEntero()) pintar();
});

// ── equipo (prototipo, catalogo-equipo.ts): lo suyo, con el tema elegido, el aviso y cómo repintar ──

function conEquipo<T>(hacer: () => T): T {
    EQ.usar({ tema: () => columnasElegidas()[0].tema.clave, avisar, pintar });
    return hacer();
}

// ── modos y mundos (prototipo, catalogo-modos.ts): lo suyo, con el tema elegido y el aviso del catálogo ──

function conModos<T>(hacer: () => T): T {
    MM.usar({ tema: () => columnasElegidas()[0].tema.clave, avisar });
    return hacer();
}

/** La página entera de un modo: la de catalogo-modos.ts, con la barra de verdad (las filas de DASHBOARD del modo y los
 *  hilos del mundo puesto). */
function pintarModos(r: MM.Ruta): void {
    const raiz = document.getElementById('catalogo')!;
    document.body.classList.add('cat-entera');
    raiz.innerHTML = `${conModos(() => MM.pagina(r))}<div id="cat-aviso" hidden></div>`;
    document.title = MM.titulo(r);
    for (const el of raiz.querySelectorAll<HTMLElement>('.lista-de-muestra')) {
        const b = new BarraHilos();
        b.estado = memoria();
        b.aqui = BARRA.aqui;
        b.mostrado = BARRA.mostrado;
        MM.prepararBarra(el, b);
        b.montar(el);
        barras.push(b);
    }
}

// las teclas de los modos (⌥⇧1–4, ⌥⇧F, ⌥⇧M, ⌥⇧0), en la página entera; y el laptop o el teléfono, por el ancho
window.addEventListener('keydown', e => { if (MM.tecla(e)) e.stopPropagation(); }, true);
let anchoModos = window.innerWidth;
window.addEventListener('resize', () => {
    const cruzo = (anchoModos <= 700) !== (window.innerWidth <= 700);
    anchoModos = window.innerWidth;
    if (cruzo && MM.entera()) pintar();
});
