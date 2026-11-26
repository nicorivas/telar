// El prototipo de la vista «equipo» en el catálogo (/componentes#equipo; docs/propuestas/equipo.md): la vista que se
// aprieta (el laptop y el teléfono, con el mismo estado), sus estados fijos, las reglas de privacidad como requisitos de
// diseño, de dónde saldría cada dato y dónde viviría. Con datos inventados (muestras-equipo.ts).
// `#equipo/ver/<persona|lista>/<ficha|apreciaciones>[/traidas]` dibuja la página entera al ancho de la ventana: así se
// sacan las capturas. Lo que se aprieta aquí no hace nada fuera de la muestra: dice qué haría.
//
// El catálogo (catalogo.ts) le pasa lo suyo con `usar` (la columna elegida, cómo avisar y cómo repintar) y le pregunta en
// cada clic (`atender`).

import { esc } from '../estilo';
import { barra as barraPantalla } from './pantalla';
import {
    OLVIDAR_MIN, SIN_TRAER, barraEquipo, equipo, type EstadoApreciaciones, type PestanaFicha, type PropsEquipo,
} from './equipo';
import { AHORA, PERSONAS, apreciacionesDeMuestra } from './muestras-equipo';

// ── lo que da el catálogo ──

export interface Contexto { tema: () => string; avisar: (t: string) => void; pintar: () => void }
let ctx: Contexto = { tema: () => 'telar', avisar: () => undefined, pintar: () => undefined };
export const usar = (c: Contexto): void => { ctx = c; };

/** Los anchos que se comparan, los de Táctica: la columna de la derecha de un laptop de 1440 y un teléfono. */
const ANCHO_LAPTOP = 1120, ANCHO_TELEFONO = 412;

// ── el estado de la muestra que se aprieta (la misma en el laptop y en el teléfono) ──

let elegida = 'ana';
let pestana: PestanaFicha = 'ficha';
let apre: EstadoApreciaciones = SIN_TRAER;
/** el teléfono, en la ficha (si no, en la lista) */
let telEnFicha = false;
let olvido = 0;

/** Olvidarlas: lo que hace la vista al cambiar de persona, de pestaña o de mundo, o a los diez minutos. */
function olvidar(): void { apre = SIN_TRAER; clearTimeout(olvido); }

const props = (o: Partial<PropsEquipo> = {}): PropsEquipo =>
    ({ personas: PERSONAS, ahora: AHORA, elegida, pestana, apreciaciones: apre, ...o });

/** La pantalla en un marco: su barra y su cuerpo, con el tema de la primera columna; en el teléfono, la densidad amplia. */
function marco(p: PropsEquipo, px: number, cual: 'vivo' | 'fijo'): string {
    const tel = px <= 700;
    return `<div class="muestra cat-tac-marco cat-eq-marco${tel ? ' angosto' : ''}" data-eq-${cual}="1" style="width: ${px}px" data-tema="${esc(ctx.tema())}" `
        + `data-densidad="${tel ? 'amplia' : 'compacta'}">${barraPantalla(barraEquipo(p))}${equipo({ ...p, angosto: tel })}</div>`;
}

const fig = (nombre: string, px: number, html: string, ver = '') => `<figure class="cat-tac-fig"><figcaption class="dim">${esc(nombre)} · ${px}px`
    + `${ver ? ` · <a href="#equipo/ver/${ver}" target="_blank" title="la página entera, con la cabecera${px > 700 ? ' y la barra de hilos' : ''}: abrirla en una ventana de ${px}px de ancho">pantalla completa</a>` : ''}`
    + `</figcaption>${html}</figure>`;
const par = (...figs: string[]) => `<div class="cat-tac-par">${figs.join('')}</div>`;
const parrafo = (html: string) => `<p class="dim">${html}</p>`;
const h3 = (t: string) => `<h3 class="cat-tac-h">${esc(t)}</h3>`;

// ── las pestañas del catálogo ──

export function seccionVista(): string {
    const ver = `${elegida}/${pestana}${apre.estado === 'traidas' ? '/traidas' : ''}`;
    return '<section class="cat-tactica">'
        + parrafo('<b>Prototipo, con datos inventados.</b> La vista de gerencia de las personas del equipo (la pidió un agente de '
            + 'la persona; la propuesta, <code>docs/propuestas/equipo.md</code>). Una fila por '
            + 'persona, con su carga de la semana en el círculo (lleno: sus horas; en rojo, sobre 110%), cuántos compromisos abiertos hay entre '
            + 'los dos, un punto si te debe algo vencido y el próximo 1:1 (en el de cuidado, si no hay uno agendado). Al abrirla, su ficha: '
            + 'el <b>1:1</b> (el último y el próximo, de la serie del calendario), los <b>compromisos</b> en las dos direcciones (te debe: lo '
            + 'que está en espera a su nombre y lo delegado, distinto; le debes; y lo que te pidió en la bandeja), la <b>capacidad</b> (sus horas '
            + 'de la planilla de horas, por proyecto, y las cuatro semanas de antes) y los <b>proyectos</b>. Las <b>apreciaciones</b> de los 1:1 van '
            + 'en su propia pestaña: se traen del Drive solo con su botón y se olvidan al salir (pestaña «privacidad»).')
        + parrafo('Aquí se aprieta: un clic en una persona la abre (en el teléfono, su ficha; ‹ vuelve a la lista), las pestañas cambian y '
            + '«traer del Drive» trae las de mentira. Cambiar de persona o de pestaña las olvida, como en la de verdad. Lo demás (abrir una '
            + 'tarea, el calendario, un proyecto) dice qué haría.')
        + par(fig('laptop', ANCHO_LAPTOP, marco(props(), ANCHO_LAPTOP, 'vivo'), ver),
            fig('teléfono', ANCHO_TELEFONO, marco(props({ elegida: telEnFicha ? elegida : '' }), ANCHO_TELEFONO, 'vivo'), telEnFicha ? ver : 'lista/ficha'))
        + '</section>';
}

const traidas = (clave: string): EstadoApreciaciones => ({ estado: 'traidas', lista: apreciacionesDeMuestra(clave), a: AHORA });

/** Los estados fijos: lo que la vista dice en cada caso (no se aprietan). */
const ESTADOS: { nombre: string; nota: string; p: Partial<PropsEquipo>; tel?: Partial<PropsEquipo>; ver: string }[] = [
    { nombre: 'atrasado y sobrecargado', ver: 'bruno/ficha',
        nota: 'Bruno: el último 1:1 fue hace 28 días, con cadencia quincenal, y no hay otro agendado (en el de cuidado, con «agendar»); te debe una tarea vencida (el punto en la lista); cargó 26 de sus 20 horas (en rojo).',
        p: { elegida: 'bruno', pestana: 'ficha', apreciaciones: SIN_TRAER } },
    { nombre: 'recién llegada', ver: 'eva/ficha',
        nota: 'Eva: entró el 16-nov; el primer 1:1 es mañana, todavía no carga horas y no hay compromisos entre los dos.',
        p: { elegida: 'eva', pestana: 'ficha', apreciaciones: SIN_TRAER } },
    { nombre: 'apreciaciones, sin traer', ver: 'ana/apreciaciones',
        nota: 'Lo que se ve al abrir la pestaña: qué son, dónde viven y cómo se olvidan, y el botón. Antes del clic no hay nada de ellas en la página: ni su número.',
        p: { elegida: 'ana', pestana: 'apreciaciones', apreciaciones: SIN_TRAER } },
    { nombre: 'apreciaciones, traídas', ver: 'ana/apreciaciones/traidas',
        nota: 'Después del clic: una tarjeta por 1:1, la hora a la que se trajeron y «olvidar ahora». Los textos son inventados.',
        p: { elegida: 'ana', pestana: 'apreciaciones', apreciaciones: traidas('ana') } },
];

export function seccionEstados(): string {
    const h = ['<section class="cat-tactica">', parrafo('Cada caso con el laptop y el teléfono. No se aprietan: dicen qué harían.')];
    for (const e of ESTADOS) {
        const p = props(e.p);
        h.push(h3(e.nombre), parrafo(esc(e.nota)),
            par(fig('laptop', ANCHO_LAPTOP, marco(p, ANCHO_LAPTOP, 'fijo'), e.ver), fig('teléfono', ANCHO_TELEFONO, marco(p, ANCHO_TELEFONO, 'fijo'), e.ver)));
    }
    h.push(h3('el teléfono, en la lista'), parrafo('La primera pantalla en el teléfono: la lista entera; un toque abre la ficha.'),
        par(fig('teléfono', ANCHO_TELEFONO, marco(props({ elegida: '' }), ANCHO_TELEFONO, 'fijo'), 'lista/ficha')));
    h.push('</section>');
    return h.join('');
}

/** Las reglas de privacidad, como requisitos de diseño: cada una con cómo la cumple el código. */
export const REGLAS: { regla: string; como: string }[] = [
    { regla: 'Las apreciaciones se traen solo con un clic, sin caché, sin repositorio y sin estado.',
        como: 'Una ruta propia, GET /api/equipo/apreciaciones/<persona>, que lee el Drive en el momento y contesta con Cache-Control: no-store; '
            + 'no escribe a disco ni a un log. En la página viven en una variable de la ficha, nunca en el modelo ni en localStorage, y '
            + `vuelven a «sin traer» al cambiar de persona, de pestaña o de mundo, al esconderse la página y a los ${OLVIDAR_MIN} minutos.` },
    { regla: 'No salen en /buscar, ⌘K, telar equipo ni la búsqueda del modo todo.',
        como: 'Ninguna de esas búsquedas las ve: /buscar y ⌘K buscan en lo que telar indexa (las apreciaciones no se indexan), y su contenedor lleva '
            + 'data-privado, que lo que copia o junta texto de la página salta. telar equipo es otra cosa (lo que ve otra persona) y no lee esta ruta.' },
    { regla: 'Ninguna orden se las da a un agente.',
        como: 'No hay orden de la CLI ni un tipo:id que las nombre (telar objeto no llega), la ruta no se publica por el bus a otra máquina, y '
            + 'pide la llave de la persona: la de un agente (TELAR_HILO) no sirve. La ficha no tiene «llevar a un hilo» en esa pestaña.' },
    { regla: 'Solo la persona la ve, y solo en el mundo trabajo.',
        como: 'La pestaña «equipo» se registra solo para el dueño de la máquina (no para un alojado) y se esconde fuera del mundo trabajo, como '
            + 'las pestañas de un mundo; la ruta de las apreciaciones contesta 404 a un alojado y fuera del trabajo.' },
    { regla: 'Nada se infiere.',
        como: 'Todo lo que se ve se cuenta o se lee: fechas, tareas, horas, proyectos y el texto tal cual se anotó. No se lee el ánimo del '
            + 'sello de la planilla de horas, ni chats, ni correos, y ningún modelo resume a nadie.' },
];

export function seccionPrivacidad(): string {
    return '<section class="cat-tactica">'
        + parrafo('<b>Requisitos de diseño.</b> Las reglas que propuso un agente de la persona, que <b>todavía esperan la confirmación de la persona</b>. '
            + 'El prototipo las cumple en lo que dibuja (la pestaña aparte, sin número, el botón, olvidar); lo demás es del código de verdad, y '
            + 'cómo, en <code>docs/propuestas/equipo.md</code>.')
        + '<div class="cat-eq-reglas">' + REGLAS.map(r => `<div><b>${esc(r.regla)}</b></div><div class="dim">${esc(r.como)}</div>`).join('') + '</div>'
        + '</section>';
}

/** De dónde saldría cada dato real. */
export const FUENTES: { dato: string; fuente: string; como: string }[] = [
    { dato: 'la lista', fuente: 'la lista del equipo del área', como: 'nombre, rol y dedicación, de una lista corta (la persona decide dónde: pestaña «dónde vive»). Sin fichas.' },
    { dato: '1:1, el último y el próximo', fuente: 'el calendario de trabajo', como: 'la serie recurrente de cada persona («1:1 Ana»): la ocurrencia anterior a hoy y la siguiente; la cadencia, de su regla.' },
    { dato: 'te debe', fuente: 'las tareas (la misma de «tareas › esperando»)', como: 'estado espera con `espera` = la persona; las delegadas, con `dueño` = la persona, aparte y distintas.' },
    { dato: 'le debes', fuente: 'las tareas', como: 'tuyas y abiertas que la persona espera: hoy no hay un campo que lo diga (decisión de la persona).' },
    { dato: 'te pide', fuente: 'la bandeja del equipo (`telar equipo sugerencias`)', como: 'lo que pidió y sigue sin resolver; el clic abre la página del pedido de hoy.' },
    { dato: 'capacidad', fuente: 'la planilla de horas', como: 'las horas cargadas de la semana, por proyecto, y las de las cuatro anteriores. Solo las horas: el ánimo del sello, nunca.' },
    { dato: 'proyectos', fuente: 'el PMO (`telar proyectos`, `telar fechas`)', como: 'donde la persona está asignada, con su rol y el plazo.' },
    { dato: 'apreciaciones', fuente: 'el Drive de la persona (lo privado)', como: 'el documento de notas de los 1:1 de cada persona, leído solo al clic.' },
];

export function seccionFuentes(): string {
    return '<section class="cat-tactica">'
        + parrafo('De dónde saldría cada cosa en la vista de verdad. Nada de esto se leyó para el prototipo: todo es inventado.')
        + '<div class="cat-eq-tabla"><b>qué</b><b>de dónde</b><b>cómo</b>'
        + FUENTES.map(f => `<div>${esc(f.dato)}</div><div>${esc(f.fuente)}</div><div class="dim">${esc(f.como)}</div>`).join('')
        + '</div></section>';
}

export function seccionDonde(): string {
    return '<section class="cat-tactica">'
        + parrafo('<b>Hoy</b> hay una pantalla «equipo» (<code>vistas/dashboard/equipo.ts</code>, <code>PantallaEquipo</code>), pero es otra cosa: '
            + 'la página de un pedido que llega por la bandeja (lo que alguien del equipo te pide en su página, <code>telar equipo</code>), con '
            + 'preguntarle a Gestión, agregarla o descartarla. Se abre desde la sección «pedidos» de la barra. No tiene lista de personas.')
        + parrafo('<b>Propuesta: la extiende.</b> «equipo» pasa a ser la vista de las personas (una pestaña del dashboard, en el mundo trabajo), y '
            + 'la página del pedido queda debajo de ella, como el detalle de un «te pide» de la ficha: la misma clase, con su clave de pantalla '
            + 'renombrada a «pedido» (<code>equipo/pedido/&lt;id&gt;</code>). Lo de la bandeja no cambia: la sección «pedidos» de la barra sigue, y '
            + 'cada pedido aparece además en la ficha de quien lo pidió. Así no hay dos cosas llamadas «equipo», y el pedido se ve con el resto de '
            + 'lo que hay con esa persona.')
        + parrafo('La otra: reemplazarla (borrar la página del pedido y resolver los pedidos desde la ficha). Pierde la página que hoy abre la barra '
            + 'y mezcla una bandeja que es de todos (cualquiera del bus pide) con una vista de las personas del área. No la recomiendo.')
        + '</section>';
}

// ── la página entera (#equipo/ver/…) ──

export interface Entera { pantalla: string; titulo: string }

/** La página entera de la ruta: `<persona|lista>/<ficha|apreciaciones>[/traidas]`. `null` si no le sirve. */
export function entera(resto: string[], tel: boolean): Entera | null {
    const [quien = 'ana', pest = 'ficha', mas = ''] = resto;
    if (quien !== 'lista' && !PERSONAS.some(x => x.clave === quien)) return null;
    if (pest !== 'ficha' && pest !== 'apreciaciones') return null;
    const elegidaAqui = quien === 'lista' ? (tel ? '' : 'ana') : quien;
    const p = props({ elegida: elegidaAqui, pestana: pest, apreciaciones: mas === 'traidas' && elegidaAqui ? traidas(elegidaAqui) : SIN_TRAER, angosto: tel });
    return { pantalla: `<div data-eq-entera="1">${barraPantalla(barraEquipo(p))}${equipo(p)}</div>`, titulo: `equipo · ${resto.join(' · ')}` };
}

// ── los clics ──

const DICE: Record<string, (v: string) => string> = {
    'eq-tarea': v => `abriría la ficha de ${v}`,
    'eq-pedido': () => 'abriría la página del pedido (la de hoy: preguntarle a Gestión, agregarla, descartar)',
    'eq-proyecto': v => `abriría ${v} en proyectos`,
    'eq-evento': v => (v.endsWith('|ultimo') ? 'abriría el último 1:1 en el calendario, con su minuta si tiene' : 'abriría el próximo 1:1 en el calendario'),
    'eq-preparar': () => 'le encargaría /preparar-reunion para ese 1:1',
    'eq-agendar': () => 'buscaría un hueco en las dos agendas y te lo propondría (no envía nada)',
    'eq-releer': () => 'leería de nuevo el calendario, las tareas, la planilla de horas y los proyectos (no las apreciaciones)',
};

/** Un clic en el prototipo; true si era suyo. En la muestra que se aprieta cambia su estado; en la página entera, la
 *  dirección; en un estado fijo, solo dice qué haría. */
export function atender(el: HTMLElement): boolean {
    const accion = el.dataset.accion ?? '';
    if (!accion.startsWith('eq-')) return false;
    const v = el.dataset.id ?? el.dataset.valor ?? '';
    const vivo = !!el.closest('[data-eq-vivo]'), enEntera = !!el.closest('[data-eq-entera]');
    const cambia = ['eq-persona', 'eq-pestana', 'eq-lista', 'eq-traer', 'eq-olvidar'].includes(accion);
    if (cambia && enEntera) { irEntera(accion, v); return true; }
    if (cambia && vivo) { cambiar(accion, v, !!el.closest('.angosto')); return true; }
    if (cambia) { ctx.avisar(accion === 'eq-traer' ? 'traería las apreciaciones del Drive (aquí no: es un estado fijo)' : `haría «${accion}»${v ? ` con ${v}` : ''}`); return true; }
    ctx.avisar(DICE[accion]?.(v) ?? `haría «${accion}»${v ? ` con ${v}` : ''}`);
    return true;
}

function cambiar(accion: string, v: string, tel: boolean): void {
    if (accion === 'eq-persona') { if (v !== elegida) olvidar(); elegida = v; if (tel) telEnFicha = true; }
    else if (accion === 'eq-lista') { telEnFicha = false; olvidar(); }
    else if (accion === 'eq-pestana') { if (v !== pestana) olvidar(); pestana = v as PestanaFicha; }
    else if (accion === 'eq-olvidar') { olvidar(); ctx.avisar('olvidadas: ya no están en la página'); }
    else if (accion === 'eq-traer') {
        const quien = v;
        apre = { estado: 'trayendo' };
        setTimeout(() => {
            if (elegida !== quien || pestana !== 'apreciaciones' || apre.estado !== 'trayendo') return;
            apre = traidas(quien);
            clearTimeout(olvido);
            olvido = window.setTimeout(() => { olvidar(); ctx.pintar(); }, OLVIDAR_MIN * 60000);
            ctx.pintar();
        }, 600);
    }
    ctx.pintar();
}

function irEntera(accion: string, v: string): void {
    const m = /^#equipo\/ver\/([a-z]+)\/?([a-z]*)\/?([a-z]*)/.exec(decodeURIComponent(location.hash));
    let [quien, pest, mas] = [m?.[1] ?? 'ana', m?.[2] || 'ficha', m?.[3] ?? ''];
    if (accion === 'eq-persona') { if (v !== quien) mas = ''; quien = v; }
    else if (accion === 'eq-lista') { quien = 'lista'; mas = ''; }
    else if (accion === 'eq-pestana') { if (v !== pest) mas = ''; pest = v; }
    else if (accion === 'eq-traer') mas = 'traidas';
    else if (accion === 'eq-olvidar') mas = '';
    history.replaceState(null, '', `#equipo/ver/${quien}/${pest}${mas ? `/${mas}` : ''}`);
    ctx.pintar();
}
