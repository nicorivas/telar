// El botón con texto: lo que se aprieta para contestar una ventana (borrar, archivar, cancelar) o hacer algo que un ícono solo
// no alcanza a decir. Es «la tecla en el pie», la forma elegida el 22-nov-2026 de las cuatro del catálogo
// (docs/propuestas/componentes.md, «Los botones»; las otras tres quedaron descartadas, y el catálogo dice por qué): el pie
// de una ventana es una banda, tras una línea de borde a borde y un espacio que la aparta del contenido, partida en celdas,
// una por botón; cada celda dice la tecla que lo hace y la palabra, y se aprieta entera. En el teléfono las celdas se
// reparten el ancho y la tecla se calla.
//
//   pieBotones([{ texto: 'borrar', accion: 'si', tono: 'peligro', tecla: '⌘⌫' }, CANCELAR])
//
// El color es el de lo que hace (`tono`): lo que destruye, en el de peligro; lo que hace sin destruir, en el de su clase
// (`color`, una tinta de `C` en web/iconos.ts, la misma del menú ⋯) o en el acento; lo que no hace nada (cancelar), en el
// del texto. Con el foco, la celda entera toma su color tenue (cancelar, el del acento: el foco de la página); al pasar el
// mouse, el gris del hover: nunca se ven iguales. Nunca otro tamaño de letra, ni esquinas redondeadas. El texto va en
// minúscula: la primera letra se baja aquí.
//
// Las teclas (las atiende web/botonera.ts, en cada ventana que abre abrirVentana): la de cada botón lo aprieta tenga o no
// el foco; ⏎ aprieta el que tiene el foco, y uno sostenido no aprieta nada. Lo que destruye lleva su acorde, ⌘⌫, nunca ⏎
// solo: aquí mismo, un botón de peligro con ⏎ pasa a ⌘⌫. Es un <button type="button">: ⇥ lo alcanza, espacio lo aprieta y
// `disabled` lo apaga. El foco se marca con `:focus`, no `:focus-visible`: en una ventana dice qué hace ⏎, y tiene que
// verse aunque se haya abierto con un clic. Cómo se ve: media/css/boton.css, sobre los tokens --boton-… de tokens.css.

import { esc } from '../estilo';

/** Lo que hace: destruye (peligro), hace algo sin destruir (accion), o nada (callado: cancelar, cerrar). */
export type TonoBoton = 'peligro' | 'accion' | 'callado';
/** Los estados que el catálogo pone a mano; en la página los dan :hover, :focus y `disabled`. */
export type EstadoBoton = 'normal' | 'hover' | 'foco' | 'deshabilitado';

export interface Boton {
    /** la palabra: en minúscula, como el resto de la página («borrar», «cancelar el encargo») */
    texto: string;
    /** lo que corre (`data-accion`): lo atiende quien lo pone, o `abrirVentana`, que se cierra con eso */
    accion?: string;
    /** con qué corre (`data-valor`), como un enlace con acción del dashboard */
    valor?: string;
    /** otros `data-*` (sin el prefijo), para quien atiende sus botones con otro atributo (contestar: `data-contestar`) */
    datos?: Record<string, string>;
    tono?: TonoBoton;
    /** una tinta (azul, amarillo, verde, violeta, cian, rojo: `C` de web/iconos.ts) en vez del color de su tono */
    color?: string;
    /** la tecla que lo hace siempre, tenga o no el foco (⎋, ⏎, ⌘⏎, ⌘⌫, 1): va delante de la palabra */
    tecla?: string;
    /** el ícono de la letra (web/iconos.ts) de lo que hace: en el lugar de la tecla, si no tiene (un botón de la página,
     *  sin atajo) */
    icono?: string;
    /** el ícono (web/iconos.ts) que va **en lugar de la palabra**, cuando lo que hace es obvio por su ícono (enviar, el
     *  basurero): la palabra pasa al `title` y al `aria-label`, y la tecla sigue delante. «Tecla + ícono» en vez de
     *  «tecla + palabra» */
    simbolo?: string;
    /** con `simbolo`: lo poco que se ve a su lado, lo que el ícono no dice (el plazo de aplazar: «15m») */
    corto?: string;
    /** HTML de la página (el círculo que gira) en el lugar de la tecla, mientras se hace: el botón va apagado */
    enCurso?: string;
    /** lo que explica, al pasar el mouse */
    ayuda?: string;
    estado?: EstadoBoton;
}

/** La primera letra, en minúscula («Borrar» → «borrar»; «T84» queda). */
export const minuscula = (t: string): string => /^\p{Lu}\p{Ll}/u.test(t) || /^\p{Lu}$/u.test(t) ? t.charAt(0).toLocaleLowerCase('es') + t.slice(1) : t;

/** La tecla de un botón: la pedida, salvo ⏎ en lo que destruye, que pasa a ⌘⌫ (⏎ es del foco, y lo que destruye no se
 *  hace con un ⏎ distraído). */
export const teclaDe = (b: Pick<Boton, 'tecla' | 'tono'>): string | undefined => (b.tono === 'peligro' && b.tecla === '⏎' ? '⌘⌫' : b.tecla);

/** Un botón con texto: una celda con la tecla (o su ícono) y la palabra. */
export function boton(b: Boton): string {
    const tono = b.tono ?? 'accion';
    const tecla = teclaDe(b);
    const estado = b.estado && b.estado !== 'normal' && b.estado !== 'deshabilitado' ? ` es-${b.estado}` : '';
    const apagado = b.estado === 'deshabilitado' || !!b.enCurso;
    const color = b.color ? ` style="--c: var(--${esc(b.color)})"` : '';
    const datos = Object.entries(b.datos ?? {}).map(([k, v]) => ` data-${esc(k)}="${esc(v)}"`).join('');
    const ranura = b.enCurso ? `<span class="boton-tecla boton-gira">${b.enCurso}</span>`
        : tecla ? `<span class="boton-tecla">${esc(tecla)}</span>`
        : b.icono && !b.simbolo ? `<span class="boton-tecla boton-icono i">${esc(b.icono)}</span>` : '';
    // con símbolo, la palabra es su nombre (al pasar el mouse y para un lector de pantalla), no lo que se ve
    const nombre = esc(minuscula(b.texto));
    const ayuda = b.ayuda ?? (b.simbolo ? minuscula(b.texto) : '');
    const texto = b.simbolo
        ? `<span class="boton-texto boton-simbolo"><span class="i">${esc(b.simbolo)}</span>${b.corto ? `<span class="boton-corto">${esc(b.corto)}</span>` : ''}</span>`
        : `<span class="boton-texto">${nombre}</span>`;
    return `<button type="button" class="boton tono-${tono}${estado}"${b.accion !== undefined ? ` data-accion="${esc(b.accion)}"` : ''}`
        + `${b.valor !== undefined ? ` data-valor="${esc(b.valor)}"` : ''}${datos}${color}`
        + `${tecla ? ` data-tecla="${esc(tecla)}" aria-keyshortcuts="${esc(atajo(tecla))}"` : ''}${b.simbolo ? ` aria-label="${nombre}"` : ''}`
        + `${ayuda ? ` title="${esc(ayuda)}"` : ''}${apagado ? ' disabled' : ''}>`
        + `${ranura}${texto}</button>`;
}

/** Una banda de botones: el pie de una ventana (lo que hace primero, cancelar al último, a la derecha), o una fila de la
 *  página con sus botones. `izq`: HTML de la página que va a la izquierda de la banda, antes de las celdas (contestar:
 *  conversarlo, ir al hilo; la instrucción: dejarla escrita). */
export function pieBotones(botones: Boton[], o: { izq?: string; clase?: string } = {}): string {
    return `<div class="ventana-pie botonera${o.clase ? ` ${esc(o.clase)}` : ''}">${o.izq ? `<span class="botonera-izq">${o.izq}</span>` : ''}`
        + `${botones.map(boton).join('')}</div>`;
}

/** Cancelar, siempre igual: al último, con ⎋, en el color del texto. `texto`: si se dice de otro modo («no», «cerrar»);
 *  `accion`: con la que cierra la ventana (null: sin `data-accion`, para quien lo atiende con `datos`). */
export const cancelar = (texto = 'cancelar', accion: string | null = 'no'): Boton =>
    ({ texto, ...(accion !== null ? { accion } : {}), tono: 'callado', tecla: '⎋', ayuda: 'cierra sin hacer nada' });

/** La tecla en palabras de `aria-keyshortcuts` (⌘⌫ → Meta+Backspace). */
function atajo(tecla: string): string {
    const nombres: Record<string, string> = { '⌘': 'Meta', '⌥': 'Alt', '⌃': 'Control', '⇧': 'Shift', '⏎': 'Enter', '⎋': 'Escape', '⌫': 'Backspace', '⇥': 'Tab' };
    return [...tecla].map(c => nombres[c] ?? c.toUpperCase()).join('+');
}

/** Los verbos que destruyen: un botón cuyo texto empieza con uno de ellos es de peligro (las acciones de una tarea o de un
 *  objeto, que vienen de afuera con su nombre). pruebas/confirmar.mjs revisa con la misma lista que cada confirmación que
 *  los dice lo trate como tal. */
export const DESTRUYE = /^(borrar|quitar|descartar|eliminar|cancelar el encargo|retirar|olvidar|vaciar)/i;
