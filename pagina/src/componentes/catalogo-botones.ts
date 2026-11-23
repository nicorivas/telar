// Los botones con texto en el catálogo (/componentes#botones): «la tecla en el pie» (componentes/boton.ts), la forma
// elegida el 22-nov-2026 de las cuatro que se propusieron el 20 (docs/propuestas/componentes.md, «Los botones»). Muestra la
// forma en ventanas de confirmar (lo que destruye, con el mouse encima, lo que no, varias acciones, contenido largo), en cada
// tema elegido; sus estados; lo que hace ⏎ y dónde parte el foco; qué confirmaciones destruyen (el catastro de hoy); y las
// tres formas descartadas, con por qué. «probar» abre la ventana de verdad (`preguntar`, sin tocar nada) y dice qué haría.

import { esc } from '../estilo';
import { C, I } from '../web/iconos';
import { botonesDeAviso, preguntar } from '../web/interfaz';
import { ventana } from './ventana';
import { pieBotones, cancelar, type Boton, type EstadoBoton } from './boton';
import { circulo } from './circulo';

/** Lo que destruye, lo que hace sin destruir (en el color de su clase: archivar es «cambiar», amarillo, como en el menú ⋯) y
 *  lo que no hace nada. La tecla de cada uno: la que lo hace siempre, tenga o no el foco. */
export const BORRAR: Boton = { texto: 'borrar', accion: 'borrar', tono: 'peligro', tecla: '⌘⌫', ayuda: 'borra el estilo; no se puede deshacer' };
export const ARCHIVAR: Boton = { texto: 'archivar', accion: 'archivar', tono: 'accion', color: C.cambiar, tecla: '⏎', ayuda: 'lo guarda en ARCHIVO, para retomarlo' };
export const CANCELAR: Boton = cancelar('cancelar', 'cancelar');

const TEXTO_BORRAR = 'Los modos que lo usan (noche y lectura) vuelven a «base». No se puede deshacer.';
const TEXTO_ARCHIVAR = 'Se cierra su ventana; su conversación queda en ARCHIVO para retomarla.';
const LARGO = Array.from({ length: 14 }, (_, i) => `· pagina/src/archivo-${String(i + 1).padStart(2, '0')}.ts (sin subir)`).join('\n');

/** Una ventana de confirmar: el título dice qué se hace y a qué, el cuerpo qué pasa con eso, y abajo la banda de botones. */
export function confirmar(o: { titulo?: string; texto: string; botones: Boton[]; clase?: string }): string {
    return ventana({ titulo: o.titulo, cuerpo: `<p>${esc(o.texto)}</p>`, pie: pieBotones(o.botones), clase: `ventana-texto cat-confirmar${o.clase ? ` ${o.clase}` : ''}` });
}

const con = (b: Boton, estado: EstadoBoton): Boton => ({ ...b, estado });
/** Los botones de un aviso de verdad (`botonesDeAviso`, web/interfaz.ts), con el foco puesto a mano en el primero o en cancelar. */
const deAviso = (botones: string[], o: Parameters<typeof botonesDeAviso>[1], foco: 'primero' | 'cancelar'): Boton[] => {
    const bs = botonesDeAviso(botones, o);
    return bs.map((b, i) => (foco === 'cancelar' ? i === bs.length - 1 : i === 0) ? con(b, 'foco') : b);
};

/** Las escenas: la forma en las ventanas de confirmar que hay. */
export const ESCENAS: { clave: string; nombre: string; nota: string; html: () => string }[] = [
    { clave: 'borrar', nombre: 'lo que destruye', nota: 'en el de peligro, con ⌘⌫; el foco parte en cancelar, así que ⏎ cancela',
        html: () => confirmar({ titulo: 'borrar el estilo «nocturno»', texto: TEXTO_BORRAR, botones: [BORRAR, con(CANCELAR, 'foco')] }) },
    { clave: 'mouse', nombre: 'con el mouse encima', nota: 'el mouse sobre «borrar» (el gris del hover) y el foco en «cancelar» (el acento): se sabe cuál hace ⏎',
        html: () => confirmar({ titulo: 'borrar el estilo «nocturno»', texto: TEXTO_BORRAR, botones: [con(BORRAR, 'hover'), con(CANCELAR, 'foco')] }) },
    { clave: 'archivar', nombre: 'lo que no destruye', nota: 'el foco parte en lo que hace, con ⏎, en el color de su clase',
        html: () => confirmar({ titulo: 'archivar «faro»', texto: TEXTO_ARCHIVAR, botones: [con(ARCHIVAR, 'foco'), CANCELAR] }) },
    { clave: 'varias', nombre: 'varias acciones', nota: 'cada una con su número; lo que concede para siempre parte en cancelar (`foco: \'cancelar\'`)',
        html: () => confirmar({ texto: 'El módulo «whatsapp» pide leer tus chats.', botones: deAviso(['Permitir siempre', 'Solo esta vez', 'No'], { foco: 'cancelar' }, 'cancelar') }) },
    { clave: 'largo', nombre: 'contenido largo', nota: 'lo que no cabe se desplaza en el cuerpo; la banda queda abajo, siempre a una línea de lo de arriba',
        html: () => confirmar({ texto: `La conversación de «faro» viaja, los archivos no. En servidor hay trabajo que aquí no va a estar:\n${LARGO}`,
            botones: deAviso(['Traer igual'], {}, 'primero'), clase: 'cat-largo' }) },
];

/** Lo que hace ⏎ y dónde parte el foco: las reglas, como quedaron. */
export const REGLAS_FOCO: { regla: string; por: string }[] = [
    { regla: 'la tecla de cada celda la aprieta, tenga o no el foco',
        por: 'lo que dice la celda es lo que hace: ⌘⌫, ⌘⏎, 1 2 3, ⎋ (web/botonera.ts, que abrirVentana pone en cada ventana). En un campo, ⌫ y los números son del campo; ⌘⏎, del botón' },
    { regla: '⏎ hace el botón que tiene el foco, y solo ese',
        por: 'ningún botón se adueña de ⏎: la celda que dice ⏎ es la que parte con el foco; con ⇥ el foco (y ⏎) pasa a otra' },
    { regla: 'en lo que destruye, el foco parte en cancelar',
        por: 'un ⏎ distraído (el que abrió la ventana desde un menú, o uno de más) no hace nada; ⇥ lleva a «borrar», y ahí ⏎ ya es a propósito' },
    { regla: 'lo que destruye tiene su acorde, nunca ⏎ solo: ⌘⌫',
        por: '⌘⏎ ya es «enviar»; ⌘⌫ es el de macOS para mandar a la papelera (el Finder). boton.ts no deja que un botón de peligro diga ⏎' },
    { regla: 'lo que no destruye pero no se hace sin mirar, también parte en cancelar',
        por: 'conceder un permiso para siempre (la caja sale sola, a veces mientras se escribe), una acción que viene de afuera: sin rojo, con ⌘⏎ o su número' },
    { regla: 'una tecla sostenida no cuenta',
        por: 'un ⏎ (o un ⌘⌫) que llega con `repeat` viene de antes de abrirse la ventana: no aprieta nada' },
    { regla: 'el foco se ve desde que se abre',
        por: 'se marca con `:focus`, no con `:focus-visible`: si la ventana se abrió con un clic en un `<button>` o un `<a href>`, Chrome no marca el foco que pone el programa con `:focus-visible` (probado el 20-nov)' },
    { regla: 'el mouse y el foco nunca se ven iguales',
        por: 'al pasar, el gris del hover; con el foco, el color del botón tenue en la celda entera, y cancelar, que no tiene color propio, el del acento' },
    { regla: 'siempre el mismo orden: lo que hace, y cancelar al último, en el borde derecho',
        por: 'la mano aprende dónde está cada uno; «cancelar» es uno solo: ⎋, en el color del texto' },
    { regla: 'entre el contenido y la banda, una línea vacía',
        por: 'se pidió (22-nov): el contenido no se pega a los botones, tampoco cuando se desplaza (--boton-pie-aire)' },
    { regla: 'mientras se hace, no se aprieta otra vez',
        por: 'el botón se apaga y el círculo que gira toma el lugar de la tecla (contestar)' },
];

/** Los estados: una fila por estado, con lo que destruye, lo que no y cancelar al lado. */
export function filasEstados(): { nombre: string; nota: string; html: string }[] {
    const tres = (estado: EstadoBoton) => pieBotones([con(BORRAR, estado), con(ARCHIVAR, estado), con(CANCELAR, estado)]);
    return [
        { nombre: 'normal', nota: 'el color de lo que hace', html: tres('normal') },
        { nombre: 'al pasar el mouse', nota: 'el fondo del hover, gris, en la celda entera', html: tres('hover') },
        { nombre: 'con el foco', nota: 'lo que hace ⏎: su color tenue en la celda entera (cancelar, el acento)', html: tres('foco') },
        { nombre: 'apagado', nota: 'aún no se puede: más tenue que lo tenue', html: tres('deshabilitado') },
        { nombre: 'mientras se hace', nota: 'apagado, y el círculo que gira en el lugar de la tecla', html: pieBotones([{ ...ARCHIVAR, enCurso: circulo({ mov: 'gira' }) }, CANCELAR]) },
        { nombre: 'sin tecla', nota: 'un botón de la página, sin atajo: su ícono en el lugar de la tecla (⚙ temas, la terminal que no abre)', html: pieBotones([
            { texto: 'reintentar', icono: I.retomar, color: C.ir }, { texto: 'borrar tema', icono: I.descartar, tono: 'peligro' }]) },
    ];
}

/** Abre una confirmación de verdad (`preguntar`) con el tema de la primera columna, y dice qué se apretó (sin hacerlo). */
export async function probar(cual: string, tema: string, densidad: string, decir: (texto: string) => void): Promise<void> {
    const marcar = () => {
        const d = document.querySelector<HTMLElement>('dialog.ventana-dialogo[open]');
        if (d) { d.dataset.tema = tema; d.dataset.densidad = densidad; }
    };
    const r = cual === 'archivar' ? preguntar(`¿Archivar «faro»? ${TEXTO_ARCHIVAR}`, ['Archivar'])
        : cual === 'varias' ? preguntar('El módulo «whatsapp» pide leer tus chats.', ['Permitir siempre', 'Solo esta vez', 'No'], { foco: 'cancelar' })
        : preguntar(`¿Borrar el estilo «nocturno»? ${TEXTO_BORRAR}`, ['Borrar'], { destruye: true });
    marcar();
    const elegido = await r;
    decir(elegido ? `apretó «${elegido}» (no hace nada)` : 'cancelada: no hace nada');
}

/** Las tres formas que no se eligieron, y por qué (la propuesta entera, en docs/propuestas/componentes.md). */
export const DESCARTADAS: { nombre: string; como: string; por: string }[] = [
    { nombre: 'la palabra', como: 'la palabra sola, en su color; una línea abajo al pasar y con el foco',
        por: 'se lee como un enlace; el mouse y el foco se distinguían solo por el color de una línea de un píxel; en el teléfono el dedo no tenía dónde apretar' },
    { nombre: 'con borde', como: 'un marco de 1 px del color de la acción; con el foco, su color tenue de fondo',
        por: 'mete marcos dentro del marco (lo único con marco es lo que se abre aparte); el botón de cualquier otra app' },
    { nombre: 'ícono y palabra', como: 'el ícono de la gramática y la palabra, en su color',
        por: 'dos signos para lo mismo; cancelar necesitaba un ícono (el ✕ ya es cerrar); no enseña la tecla. De ella quedó el color de lo que se hace' },
];

// ── el catastro: qué confirmaciones destruyen (22-nov-2026) ──

/** La clase de una confirmación: destruye (peligro, ⌘⌫, foco en cancelar), pide mirar (foco en cancelar, sin rojo) o hace
 *  (el foco en lo que hace, con ⏎). */
export type ClaseConfirmacion = 'destruye' | 'mira' | 'hace';

/** Cada confirmación de la página, con su clase. `archivo` es la ruta desde `pagina/src` (pruebas/confirmar.mjs revisa que
 *  cada archivo con una confirmación esté aquí, para que una nueva no quede sin decidir). */
export const CONFIRMACIONES: { archivo: string; que: string; botones: string; clase: ClaseConfirmacion; por: string }[] = [
    { archivo: 'vistas/dashboard/config/glifos.ts', que: 'borrar un estilo de glifos', botones: '⌘⌫ borrar', clase: 'destruye', por: 'no se deshace: los modos que lo usan vuelven a «base»' },
    { archivo: 'vistas/dashboard/config/modos.ts', que: 'borrar un modo, o volver uno de fábrica', botones: '⌘⌫ borrar · ⌘⌫ volver', clase: 'destruye', por: 'lo cambiado en él se pierde' },
    { archivo: 'vistas/dashboard/config/mundos.ts', que: 'borrar un mundo', botones: '⌘⌫ borrar', clase: 'destruye', por: 'lo suyo queda sin clasificar' },
    { archivo: 'vistas/dashboard/config/periodicos.ts', que: 'borrar un proceso periódico', botones: '⌘⌫ borrar', clase: 'destruye', por: 'deja de correr (queda el .anterior, a mano)' },
    { archivo: 'vistas/dashboard/config/temas.ts', que: 'borrar un tema propio', botones: '⌘⌫ borrar', clase: 'destruye', por: 'se van sus colores' },
    { archivo: 'vistas/dashboard/config/modulos.ts', que: 'quitar un módulo', botones: '⌘⌫ quitar', clase: 'destruye', por: 'borra la carpeta que bajó telar' },
    { archivo: 'vistas/dashboard/config/personas.ts', que: 'quitarle la cuenta a alguien', botones: '⌘⌫ quitar la cuenta', clase: 'destruye', por: 'deja de conectarse; para volver, pide entrar de nuevo (era un «elegir» con el «no» marcado)' },
    { archivo: 'vistas/dashboard/esperas.ts', que: 'descartar mensajes retenidos (uno, o los del grupo)', botones: '⌘⌫ descartar', clase: 'destruye', por: 'los mensajes no llegan nunca' },
    { archivo: 'web/contestar.ts', que: 'descartar un retenido desde contestar', botones: '⌘⌫ descartar', clase: 'destruye', por: 'lo mismo; y el botón de contestar, si quita, también va en rojo con ⌘⌫ (⏎ no lo hace)' },
    { archivo: 'web/ordenes.ts', que: 'descartar un hilo (vivo o archivado)', botones: '⌘⌫ descartar', clase: 'destruye', por: 'ya no se retoma con un clic y telar lo olvida' },
    { archivo: 'web/ordenes.ts', que: 'eliminar un agente', botones: '⌘⌫ eliminar', clase: 'destruye', por: 'se recupera a mano, pero lo encargado queda sin hacer' },
    { archivo: 'vistas/dashboard/agentes.ts', que: 'cancelar un encargo', botones: '⌘⌫ cancelar el encargo', clase: 'destruye', por: 'lo pedido no se hace' },
    { archivo: 'web/lado.ts', que: 'cancelar un encargo, desde la hoja de un agente', botones: '⌘⌫ cancelar el encargo', clase: 'destruye', por: 'lo pedido no se hace' },
    { archivo: 'vistas/dashboard/tareas.ts', que: 'una acción de tarea que pide confirmar (`confirmar` en su proveedor)', botones: '⌘⌫ <verbo> si destruye; si no, ⌘⏎ <verbo>', clase: 'destruye', por: 'viene de afuera: el botón dice su nombre, y es de peligro si su verbo destruye (`DESTRUYE`, boton.ts); si no, pide mirar' },
    { archivo: 'web/objeto.ts', que: 'una acción de un objeto, sin parámetros', botones: '⌘⌫ <verbo> si destruye; si no, ⌘⏎ <verbo>', clase: 'mira', por: 'lo mismo: de afuera, con el foco en cancelar; en rojo solo si su verbo destruye (retirar, descartar…)' },
    { archivo: 'vistas/dashboard/pagina.ts', que: 'el permiso que pide un módulo', botones: '1 permitir siempre · 2 solo esta vez · 3 no', clase: 'mira', por: 'concede para siempre, y la caja sale sola, a veces mientras se escribe' },
    { archivo: 'vistas/dashboard/agentes.ts', que: 'rotar la conversación de un agente', botones: '⏎ rotar', clase: 'hace', por: 'su conversación queda en disco y la siguiente empieza leyendo su relevo' },
    { archivo: 'web/lado.ts', que: 'rotar, desde la hoja de un agente', botones: '⏎ rotar', clase: 'hace', por: 'lo mismo' },
    { archivo: 'vistas/dashboard/agentes.ts', que: 'archivar los hilos que abrió un agente', botones: '⏎ archivar', clase: 'hace', por: 'se retoman desde ARCHIVO' },
    { archivo: 'vistas/dashboard/proyectos.ts', que: 'archivar un hilo; marcar hecha una casilla del README; consolidar', botones: '⏎ archivar · ⏎ marcar hecha · ⏎ consolidar', clase: 'hace', por: 'se retoma; se desmarca; solo propone' },
    { archivo: 'web/ordenes.ts', que: 'archivar con sus hijos o solo él; traer igual; usar Claude Code', botones: '1 con sus hijos · 2 solo él · ⏎ traer igual · ⏎ usar claude code', clase: 'hace', por: 'nada se pierde: lo que no viaja sigue en la otra máquina' },
    { archivo: 'web/mudanza.ts', que: 'llevar igual (lo que allá llegaría a medias)', botones: '⏎ llevar igual · ⎋ no llevarlo', clase: 'hace', por: 'como traer igual; «no llevarlo» es cancelar (antes iba en rojo)' },
    { archivo: 'web/version.ts', que: 'instalar telar', botones: '⏎ instalar', clase: 'hace', por: 'reinicia el servicio; la versión anterior se vuelve a instalar' },
    { archivo: 'vistas/dashboard/config/modulos.ts', que: 'instalar un módulo', botones: '⏎ instalar', clase: 'hace', por: 'corre con tus permisos, pero lo acabas de pedir' },
    { archivo: 'vistas/dashboard/panel.ts', que: 'encargar otra vez lo recién encargado', botones: '⏎ sí', clase: 'hace', por: 'un encargo de más' },
    { archivo: 'vistas/dashboard/config/carpetas.ts', que: 'abrir los hilos que faltan', botones: '⏎ abrir ahora', clase: 'hace', por: 'abre, no cierra' },
    { archivo: 'modelo.ts', que: 'una tarea que te piden', botones: '1 ver · 2 agregar', clase: 'hace', por: 'nada se pierde' },
    { archivo: 'web/terminal.ts', que: 'copiar (no pasó al portapapeles); guardar lo soltado en la terminal', botones: '⏎ copiar · ⏎ guardar · ⎋ no', clase: 'hace', por: 'la franja de soltar es una banda, con ⎋' },
    { archivo: 'web/interfaz.ts', que: 'escribir un texto y mandarlo', botones: '⌘⏎ enviar', clase: 'hace', por: '⏎ es una línea más' },
    { archivo: 'web/instruccion.ts', que: 'la instrucción', botones: '⌘⏎ mandar', clase: 'hace', por: 'como escribir' },
];

export const NOTA_HOY = 'Antes (20-nov): lo que destruye iba en rojo solo en «contestar» y en la mudanza (y ahí el rojo era para no hacerlo); el '
    + '«eliminar» de agentes.ts se veía azul; «cancelar» iba en cuatro colores; había nueve formas de botón con texto; el foco de «cancelar» no '
    + 'se veía si la ventana se abrió con un clic; rotar, archivar, marcar hecha, «traer igual» e instalar abrían con el foco en lo que hacen. '
    + 'Hoy: todas las confirmaciones y los pies de ventana usan la banda; lo que destruye, en el de peligro con ⌘⌫; cancelar, uno solo. '
    + 'Siguen con su forma los botones que no son de una ventana: las teclas en caja de la ficha de una tarea y de periódicos, las '
    + 'palabras de táctica, los enlaces de ⚙, los chips y las opciones con círculo.';
