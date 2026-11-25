// Las pestañas en el catálogo (/componentes#pestanas): en cada estado y tema, y dónde está cada fila de pestañas de la
// página (el catastro del 24-nov-2026: cuáles ya son este componente, cuáles faltan y cuáles se parecen y no lo son).
// Con datos de mentira: un clic en una dice qué haría.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { pestanas, type Pestana, type PropsPestanas } from './pestanas';

/** una muestra del catálogo, con el tema y la densidad de su columna (catalogo.ts, `celda`) */
type Celda<C> = (c: C, html: string, clase?: string) => string;

const PLEGAR = `<span class="i" title="plegar la barra">${I.plegado}</span>`;
const fila = (p: Omit<PropsPestanas, 'nombre'> & { nombre?: string }, ancho = '') =>
    `<div class="cat-pestanas-muestra"${ancho ? ` style="width: ${ancho}"` : ''}>${pestanas({ nombre: 'muestra', accion: 'pestana', ...p })}</div>`;

const FOCO: Pestana[] = [
    { valor: 'gestion', nombre: 'gestión', icono: I.hecha, cuenta: 50, ayuda: 'lo rápido (media hora o menos)' },
    { valor: 'concentracion', nombre: 'concentración', icono: I.consolidar, cuenta: 16, ayuda: 'lo largo (horas o días)' },
];
const HOJAS: Pestana[] = [
    { valor: 'ficha', nombre: 'ficha', icono: I.ficha },
    { valor: 'notas', nombre: 'notas', icono: I.borrador, cuenta: 2 },
    { valor: 'codigos', nombre: 'códigos', icono: I.codigos, cuenta: 12 },
    { valor: 'contexto', nombre: 'contexto', icono: I.carga },
];
const DOCUMENTO: Pestana[] = [
    { valor: 'comentarios', nombre: 'comentarios', icono: I.escribir, cuenta: 3, cuentaAtencion: true, ayuda: '3 abiertos' },
    { valor: 'conexiones', nombre: 'conexiones', icono: I.enlace, cuenta: 7, nuevo: 'exito', ayuda: 'una nueva desde que lo abriste' },
    { valor: 'datos', nombre: 'datos', icono: I.etiqueta },
];
const MUCHAS: Pestana[] = [
    { valor: 'resumen', nombre: 'resumen', icono: I.resumen },
    { valor: 'pendientes', nombre: 'pendientes', icono: I.lista, cuenta: 9 },
    { valor: 'documento', nombre: 'documento', icono: I.documento },
    { valor: 'historia', nombre: 'historia', icono: I.reloj },
    { valor: 'conexiones', nombre: 'conexiones', icono: I.enlace, cuenta: 4 },
];

/** Las escenas de «estados»: [nombre, nota, html]. */
export function escenas(): [string, string, string][] {
    return [
        ['con ícono y cuenta', 'foco: gestión y concentración, con cuántas hay en cada una; la abierta, con la superficie de la selección',
            fila({ pestanas: FOCO, activa: 'gestion' })],
        ['sin ícono', 'el catálogo: solo el nombre; una por hacer, apagada (no se aprieta, su globo dice qué falta)',
            fila({ pestanas: [{ valor: 'estados', nombre: 'estados' }, { valor: 'anatomia', nombre: 'anatomía', apagada: true, ayuda: 'por hacer' },
                { valor: 'donde', nombre: 'dónde está' }], activa: 'estados' })],
        ['con lo del extremo', 'las hojas de un hilo: lo de la fila (aquí, plegar la barra) va al otro extremo, quieto aunque la lista corra',
            fila({ pestanas: HOJAS, activa: 'codigos', fin: PLEGAR })],
        ['algo nuevo, y una cuenta que pide', 'el documento: los comentarios abiertos, en el de cuidado; algo nuevo en conexiones, un punto en su esquina',
            fila({ pestanas: DOCUMENTO, activa: 'comentarios' })],
        ['mouse encima, y con el foco', 'el fondo del hover en «concentración»; con el teclado, la línea de abajo en el acento sobre la abierta (← → pasan de una a otra)',
            fila({ pestanas: FOCO, activa: 'gestion' }).replace('class="pestana si con-icono"', 'class="pestana si con-icono es-foco"')
                .replace('class="pestana con-icono"', 'class="pestana con-icono es-hover"')],
        ['no caben: al «⋯»', 'las que caben, enteras; las demás, al «⋯» justo después de la última que se ve (un clic, o ⏎ con el foco en él, abre su menú con cada una, su ícono y su cuenta). Arrastra el borde de la columna: se reacomoda en vivo',
            fila({ pestanas: MUCHAS, activa: 'resumen' }, '36ch')],
        ['no caben: la abierta, escondida', '«historia» está abierta y no cabía: toma el lugar de la última que cabía, y la que desplaza va al «⋯»',
            fila({ pestanas: MUCHAS, activa: 'historia' }, '36ch')],
        ['no caben: algo nuevo, escondido', 'las hojas de un hilo, angostas: las notas terminaron su turno (el punto) y quedaron en el «⋯», que lleva el punto; una cuenta que pide, escondida, pone el «⋯» en el de cuidado',
            fila({ pestanas: [HOJAS[0], HOJAS[2], HOJAS[3], { ...HOJAS[1], nuevo: 'termino' }], activa: 'ficha', fin: PLEGAR }, '30ch')],
    ];
}

/** El catastro: cada fila de pestañas de la página, si ya es el componente y, si no, por qué. */
export interface Lugar { lugar: string; archivo: string; estado: 'migrada' | 'falta' | 'no'; por: string }
export const LUGARES: Lugar[] = [
    { lugar: 'foco: gestión y concentración', archivo: 'vistas/dashboard/foco.ts', estado: 'migrada', por: 'era un chip azul lleno sin línea; ahora la fila del alto de las barras' },
    { lugar: 'las pestañas de un componente del catálogo', archivo: 'componentes/catalogo.ts', estado: 'migrada', por: 'subrayado de acento; ahora la de la página, con enlaces (#item/anatomia)' },
    { lugar: 'las hojas de un hilo (ficha, notas, códigos, contexto)', archivo: 'web/lado.ts', estado: 'migrada', por: 'en violeta, sin teclado; la flecha de plegar va en su extremo. Las notas eran un bloque fijo al pie («próximos prompts»): ahora una hoja más' },
    { lugar: 'el detalle de un proyecto (resumen, pendientes, documento)', archivo: 'vistas/dashboard/proyectos.ts', estado: 'migrada', por: 'la abierta la marca la página sin repintar (vista.ts, `marcar`)' },
    { lugar: 'la barra del visor (comentarios, conexiones, datos)', archivo: 'web/documento-lado.ts', estado: 'migrada', por: 'abierta, la fila de la casa (en violeta antes; los nombres que no cabían, por un @container); plegada sigue siendo su franja vertical (en el teléfono, una fila abajo), que no es una fila de pestañas' },
    { lugar: '⚙ modos en el teléfono (cada modo)', archivo: 'vistas/dashboard/config/modos.ts', estado: 'falta', por: 'solo existe en el teléfono (un @container); con la sección de ⚙ modos' },
    { lugar: '⚙ el mundo que se mira (selectorMundos)', archivo: 'vistas/dashboard/config/mundos.ts', estado: 'falta', por: 'cada opción con el color de su mundo y una raya en vez de ícono: pide `color` en la abierta, no solo en el ícono' },
    { lugar: 'las vistas de una pantalla (foco y lista, día y semana, terminal y lectura)', archivo: 'componentes/pantalla.ts', estado: 'no', por: 'son íconos dentro de la barra de la pantalla, con su nombre, su resumen y sus acciones: ya son su componente (la gramática: «la que se ve, en violeta»)' },
    { lugar: 'la banda de modos (táctica, estrategia, foco, todo)', archivo: 'componentes/modos-mundos.ts', estado: 'no', por: 'cambia el modo de toda la página, no lo de abajo; con sus teclas (⌥⇧1–4) y su menú' },
    { lugar: 'el menú de ⚙', archivo: 'vistas/dashboard/config/configuracion.ts', estado: 'no', por: 'una columna vertical, como la barra de hilos (solo en el teléfono es una fila)' },
    { lugar: 'día, semana y lista de los periódicos', archivo: 'vistas/dashboard/config/periodicos.ts', estado: 'no', por: 'son vistas de lo mismo, como día y semana del calendario: van a la barra de la pantalla' },
    { lugar: 'los filtros (qué mirar, cuáles, fuente) y el área de proyectos', archivo: 'componentes/filtros.ts', estado: 'no', por: 'filtran: un clic en la que rige la suelta, se pliegan y pueden ir varias' },
];

/** «dónde está»: la tabla del catastro. */
export function seccionDonde(): string {
    const estado = { migrada: 'ya es el componente', falta: 'falta migrarla', no: 'no es una pestaña' };
    const codigo = (t: string) => esc(t).replace(/`([^`]+)`/g, '<code>$1</code>');
    return '<section><p class="dim">Cada fila de pestañas de la página (el catastro del 24-nov-2026). Las rutas, relativas a <code>pagina/src</code>; '
        + '<code>npm run prueba:componentes</code> revisa que las que dicen «ya es el componente» lo usen.</p>'
        + '<table class="gr-tabla cat-tabla"><tr><th>dónde</th><th>archivo</th><th>estado</th><th>por qué</th></tr>'
        + LUGARES.map(l => `<tr><td>${esc(l.lugar)}</td><td><code>${esc(l.archivo)}</code></td><td>${estado[l.estado]}</td><td>${codigo(l.por)}</td></tr>`).join('')
        + '</table></section>';
}

/** «estados»: cada escena, en cada columna. */
export function seccionEstados<C>(columnas: C[], celda: Celda<C>, titulos: string, grilla: string): string {
    const h = ['<section>',
        '<p class="dim">Una barra horizontal para elegir qué se ve debajo, entre pocas cosas hermanas (<code>componentes/pestanas.ts</code>, '
        + '<code>media/css/pestanas.css</code>, tokens <code>--pestana-…</code>; lo que hace, <code>web/pestanas.ts</code>). Es una <b>fila del alto de las '
        + 'barras</b> (<code>--pantalla-barra-alto</code>), con su <b>línea abajo de borde a borde</b>. La abierta lleva la <b>superficie de la selección</b> '
        + '(la del ítem activo, con la marca del tema: la gramática, «la fila donde estás, la pestaña abierta»); las demás, tenues, y al pasar el mouse '
        + 'el fondo del hover: se distinguen por color y superficie, nunca por el tamaño de la letra. Cada una, un ícono opcional, su nombre y su cuenta. '
        + '<b>El teclado</b>: con el foco en una (⇥ llega a la abierta), ← → pasan a la de al lado y la abren, Inicio y Fin a la primera y la última; '
        + 'el «⋯» es una más del recorrido, y ⏎, espacio o ↓ abren su menú (el de la casa: ↑ ↓, ⏎, ⎋). '
        + '<b>Si no caben</b>: las que caben, enteras (ícono, nombre y cuenta); las demás, al menú del «⋯», después de la última que se ve. La abierta '
        + 'siempre se ve: si no cabía, toma el lugar de la última que cabía. Algo nuevo en una escondida, su punto en el «⋯»; una cuenta que pide, el «⋯» '
        + 'en el de cuidado. Nunca corre de lado. Se mide con un ResizeObserver: al cambiar el ancho (la ventana, el borde de una columna) se reacomoda en '
        + 'vivo, sin saltos.</p>',
        `<div class="cat-grilla" style="${grilla}">${titulos}`];
    for (const [nombre, nota, html] of escenas()) {
        h.push(`<div class="cat-nombre" title="${esc(nota)}">${esc(nombre)}<span class="dim"> · ${esc(nota)}</span></div>`);
        for (const c of columnas) h.push(celda(c, html));
    }
    h.push('</div></section>');
    return h.join('');
}
