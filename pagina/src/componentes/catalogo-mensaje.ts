// La barra de mensaje en el catálogo (/componentes#mensaje): en cada estado y tema, la lista para elegir a quién, y dónde
// se propone ponerla en vez de la ventana de la instrucción. Con datos de mentira: enviar y elegir dicen qué harían, nada
// sale.

import { esc } from '../estilo';
import { C, I } from '../web/iconos';
import { barraMensaje, type DestinoMensaje, type PropsMensaje } from './mensaje';
import { paleta } from './ventana';
import type { Item, Tono } from './item';

/** una muestra del catálogo, con el tema y la densidad de su columna (catalogo.ts, `celda`) */
type Celda<C> = (c: C, html: string, clase?: string) => string;

const FARO: DestinoMensaje = { valor: '', nombre: 'Faro', icono: I.lleno, color: C.ir, detalle: 'su hilo: se le escribe' };
const AGENTE: DestinoMensaje = { valor: 'Archivista', nombre: 'Archivista', icono: I.agente, color: C.agente, detalle: 'agente: se le encarga' };
const NUEVO: DestinoMensaje = { valor: '+nuevo', nombre: 'hilo nuevo', icono: I.nuevo, color: C.hecho, detalle: 'uno nuevo para esto, en casa' };
const base = (p: Partial<PropsMensaje> = {}): PropsMensaje => ({ llave: 'tarea:T84', destino: FARO,
    placeholder: 'escríbele a Faro sobre T84 · ⏎ envía, ⇧⏎ línea nueva', ...p });

/** Las escenas de «estados»: [nombre, nota, html]. */
export function escenas(): [string, string, string][] {
    return [
        ['su hilo, de fábrica', 'el de la tarea (el de su proyecto, que dice telar): un hilo, en azul, con el ícono que le pone ⌘K',
            barraMensaje(base())],
        ['buscando su hilo', 'mientras telar dice cuál es: «su hilo», tenue; enviar espera a que llegue',
            barraMensaje(base({ destino: { valor: '', nombre: 'su hilo', icono: I.lleno, color: C.ir, detalle: 'buscando cuál…' }, buscando: true,
                placeholder: 'escríbele a su hilo sobre T84 · ⏎ envía, ⇧⏎ línea nueva' }))],
        ['con algo escrito', 'enviar, en el acento (⏎ lo hace); lo escrito queda como borrador de la tarea, el mismo de la ventana de la instrucción',
            barraMensaje(base({ texto: 'revisa si el proveedor ya contestó y deja el resumen en su ficha' }))],
        ['a un agente', 'sin hilo propio, la tarea va al agente de los pendientes: se le encarga (en violeta, como en ⌘K)',
            barraMensaje(base({ destino: AGENTE, placeholder: 'escríbele a Archivista sobre T84 · ⏎ envía, ⇧⏎ línea nueva' }))],
        ['a un hilo nuevo', 'uno nuevo para la tarea, en la carpeta de su proyecto (en verde, el de crear)',
            barraMensaje(base({ destino: NUEVO, placeholder: 'escríbele a un hilo nuevo sobre T84 · ⏎ envía, ⇧⏎ línea nueva' }))],
        ['enviando', 'lo escrito sale del campo al tiro; arriba, a quién va, con el círculo que gira',
            barraMensaje(base({ dijo: { estado: 'enviando', destino: 'Faro', texto: '' } }))],
        ['enviado', 'a quién llegó (su nombre abre su hilo) y cómo, lo que dice telar',
            barraMensaje(base({ dijo: { estado: 'llego', destino: 'Faro', direccion: 'hilo:Faro@servidor', texto: 'en servidor · por el bus' } }))],
        ['no se envió', 'por qué, en el de peligro; lo escrito vuelve al campo',
            barraMensaje(base({ texto: 'revisa si el proveedor ya contestó', dijo: { estado: 'error', destino: 'Faro', texto: 'telar no contesta' } }))],
        ['varias líneas', '⇧⏎ es una línea nueva: el campo crece hasta ocho y después corre por dentro; el destino y enviar, al pie',
            barraMensaje(base({ texto: 'tres cosas:\n1. revisa si contestó\n2. si no, un borrador para insistir\n3. dime qué falta' }))],
    ];
}

/** La lista de a quién, como la abre un clic en el destino (ui.menu, junto a él): su hilo, uno nuevo, los hilos y los
 *  agentes del mundo puesto, en el orden y con los íconos de ⌘K. */
export function lista(): string {
    const fila = (titulo: string, icono: string, tono: Tono, detalle: string): Item => ({ titulo, inicio: [{ icono, tono }], sufijo: [{ texto: detalle }] });
    const sep = (titulo: string): Item => ({ titulo, variante: 'cabecera' });
    return paleta({ lugar: 'junto', titulo: 'a quién', placeholder: 'acciones', sel: 0, filas: [
        fila('su hilo · Faro', I.lleno, 'acento', 'su hilo: se le escribe'),
        fila('hilo nuevo', I.nuevo, 'exito', 'uno nuevo para esto, en casa'),
        sep('hilos'),
        fila('Plan de ventas', I.lleno, 'acento', 'trabajo/ventas'),
        fila('Informe mensual', I.vacio, 'acento', 'trabajo/informes · sin ventana'),
        fila('Pruebas', I.lleno, 'acento', 'en servidor'),
        sep('agentes'),
        fila('Archivista', I.agente, 'agente', 'agente: se le encarga'),
        fila('Cartero', I.agente, 'agente', 'agente: se le encarga'),
    ] });
}

/** Dónde se propone ponerla, en vez de la ventana de la instrucción (que no se quita todavía). */
export const DONDE: { lugar: string; archivo: string; por: string }[] = [
    { lugar: 'la ficha de una tarea', archivo: 'vistas/dashboard/tareas.ts', por: 'al pie de la ficha, como en foco: «escribirle a Claude» y la instrucción de su barra abren hoy la ventana' },
    { lugar: 'el detalle de un proyecto', archivo: 'vistas/dashboard/proyectos.ts', por: 'su hilo es el del proyecto: «escribirle a … sobre este proyecto» es hoy una ventana' },
    { lugar: 'la ventana de un chat de foco (los módulos)', archivo: 'componentes/ventana-modulo.ts', por: '«mandar a…» abre la instrucción encima de la ventana; la barra iría bajo la caja de responder, con el chat como contexto libre' },
    { lugar: 'la pestaña de un módulo (`window.lienzo.pedir("instruccion")`)', archivo: 'vistas/dashboard/panel.ts', por: 'al pie de la pestaña, con lo que muestra como contexto libre y `[instruccion] destino` de fábrica' },
    { lugar: 'una espera en «te esperan» y en Táctica', archivo: 'vistas/dashboard/esperas.ts', por: 'para escribirle al agente que espera sin abrir «contestar»: su hilo es el de la espera' },
    { lugar: 'el visor de un documento', archivo: 'web/documento-lado.ts', por: 'pedir algo sobre el archivo que se lee (el hilo de su carpeta) sin dejar el visor' },
    { lugar: 'la hoja de un agente («encargar»)', archivo: 'web/lado.ts', por: 'con el destino fijo en el agente: es la instrucción con `solo`' },
];

export function seccionDonde(): string {
    return '<section><p class="dim">Dónde se propone usarla en vez de la ventana modal de la instrucción (<code>web/instruccion.ts</code>, que no se quita '
        + 'todavía: la barra no tiene skill ni «dejarla escrita», y a un agente desde su hoja la ventana sigue siendo lo más claro). Hoy está solo en foco. '
        + 'Las rutas, relativas a <code>pagina/src</code>.</p>'
        + '<table class="gr-tabla cat-tabla"><tr><th>dónde</th><th>archivo</th><th>por qué</th></tr>'
        + DONDE.map(d => `<tr><td>${esc(d.lugar).replace(/`([^`]+)`/g, '<code>$1</code>')}</td><td><code>${esc(d.archivo)}</code></td><td>${esc(d.por)}</td></tr>`).join('')
        + '</table></section>';
}

/** «estados»: cada escena, en cada columna. */
export function seccionEstados<C>(columnas: C[], celda: Celda<C>, titulos: string, grilla: string): string {
    const h = ['<section>',
        '<p class="dim">Una fila para escribirle a un hilo o a un agente sobre lo que se mira, sin abrir una ventana (<code>componentes/mensaje.ts</code>, '
        + '<code>media/css/mensaje.css</code>, tokens <code>--mensaje-…</code>; lo que hace, <code>web/mensaje.ts</code>). Por dentro es la <b>instrucción</b> '
        + 'de siempre (<code>telar actuar</code>: el contexto de la cosa más lo escrito; su hilo lo dice telar); cambia la forma. Va <b>al pie de la '
        + 'pantalla</b>, del alto de las barras, con su línea arriba de borde a borde. A la izquierda, <b>a quién</b>, en la tinta de lo que es: un clic '
        + 'abre la lista (pestaña «la lista»). En el medio, el campo: <b>⏎ envía, ⇧⏎ es una línea nueva</b> (la regla de una caja en una fila, como la '
        + 'de la terminal), ⎋ lo suelta; no toma el foco solo. Después de enviar, arriba del campo, a quién fue (su nombre abre su hilo) y cómo. '
        + 'Aquí, enviar y elegir dicen qué harían.</p>',
        `<div class="cat-grilla" style="${grilla}">${titulos}`];
    for (const [nombre, nota, html] of escenas()) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnas) h.push(celda(c, `<div class="cat-mensaje">${html}</div>`));
    }
    h.push('</div></section>');
    return h.join('');
}

/** «la lista»: la de a quién, en cada columna. */
export function seccionLista<C>(columnas: C[], celda: Celda<C>, titulos: string, grilla: string): string {
    const h = ['<section>',
        '<p class="dim">Un clic en el destino abre esta lista junto a él (<code>ui.menu</code>: el filtro y filas <code>item()</code>; si no cabe abajo, '
        + 'encima). Primero <b>su hilo</b> y <b>uno nuevo</b> para la cosa (si telar dice que se le puede abrir); después, como en ⌘K y en su orden '
        + '(<code>web/buscador-hilos.ts</code>), los <b>hilos</b> (los abiertos y lo más reciente primero, en azul) y los <b>agentes</b> (en violeta). '
        + '<b>Solo los del mundo puesto</b>, también en el modo todo: ni hilos ni agentes de otro mundo, ni los de un agente que pide esconderse.</p>',
        `<div class="cat-grilla" style="${grilla}">${titulos}`];
    h.push('<div class="cat-nombre">la lista<span class="dim"> · su hilo, uno nuevo, los hilos, los agentes</span></div>');
    for (const c of columnas) h.push(celda(c, lista()));
    h.push('</div></section>');
    return h.join('');
}

/** Lo que haría un clic en una barra del catálogo; undefined si no es suyo. */
export function dice(t: Element): string | undefined {
    const m = t.closest<HTMLElement>('.muestra .mensaje');
    if (!m) return undefined;
    const destino = m.querySelector('.mensaje-destino-nombre')?.textContent ?? '';
    if (t.closest('[data-mensaje-destino]')) return `abriría la lista de a quién (ahora: ${destino})`;
    if (t.closest('[data-mensaje-enviar]')) {
        const texto = m.querySelector<HTMLTextAreaElement>('.mensaje-campo')?.value.trim() ?? '';
        return texto ? `enviaría a ${destino}: «${texto.slice(0, 60)}»` : 'sin nada escrito: el foco al campo';
    }
    const a = t.closest<HTMLElement>('[data-mensaje-abrir]');
    if (a) return `abriría ${a.dataset.mensajeAbrir}`;
    return undefined;
}
