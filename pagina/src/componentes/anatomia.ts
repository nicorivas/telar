// La anatomía del ítem (componentes/item.ts), de la tarjeta (componentes/tarjeta.ts) y de la sección de lista
// (componentes/seccion.ts), para las láminas del catálogo (/componentes): sus tres secciones y cada pieza, con su nombre, la prop que la pone y para qué está. La lámina dibuja
// el ejemplo, separa sus piezas y las nombra con esto; la prueba (pruebas/componentes.mjs) revisa que nombre todas las
// que dibuja el componente y que el ejemplo las tenga todas: si gana una pieza, la lámina la pide.

import { I } from '../web/iconos';
import * as S from './senales';
import type { Accion, Item } from './item';
import type { PropsSeccion } from './seccion';
import type { Tarjeta } from './tarjeta';

export interface Parte {
    /** dónde está en el ítem dibujado (un selector) y, si son varias, cuál (`n`) o todas juntas (`todas`) */
    selector: string;
    n?: number;
    todas?: boolean;
    nombre: string;
    /** la prop de item() que la pone */
    prop: string;
    intencion: string;
}

/** Una sección: dónde está (un selector; `todas`, si son varios elementos juntos), su nombre, qué responde y sus piezas. */
export interface Seccion { clave: string; selector: string; todas?: boolean; nombre: string; pregunta: string; intencion: string; partes: Parte[] }

export const SECCIONES: Seccion[] = [
    {
        clave: 'inicio', selector: '.item-inicio', nombre: 'inicio', pregunta: '¿cómo está y dónde?',
        intencion: 'Círculos en ranuras de ancho fijo: lo que se lee sin leer (la prioridad, si su agente trabaja, te espera o '
            + 'terminó, si vive en otra máquina). Una ranura vacía ocupa su lugar igual, así los títulos de una lista empiezan todos en la misma columna. '
            + 'Lo que está en curso también se dice aquí, con un círculo que se mueve en su ranura (se vacía al cerrarse, gira al viajar): el texto queda quieto.',
        partes: [
            { selector: '.item-ranura', n: 0, nombre: 'ranura', prop: 'inicio[0]', intencion: 'un círculo en su color; en un hilo, la prioridad (chica: acompaña al estado)' },
            { selector: '.item-ranura', n: 1, nombre: 'ranura vacía', prop: 'inicio[1] = null', intencion: 'nada que decir, pero guarda el lugar' },
            { selector: '.item-ranura', n: 2, nombre: 'ranura', prop: 'inicio[2]', intencion: 'en un hilo, dónde vive (o el nombre de la máquina, en una ancha)' },
        ],
    },
    {
        clave: 'texto', selector: '.item-texto', nombre: 'texto', pregunta: '¿qué es?',
        intencion: 'El nombre y lo que lo califica. Es lo único que se estira: con poco ancho se corta con «…» antes de pisar el fin.',
        partes: [
            { selector: '.item-prefijo', nombre: 'prefijo', prop: 'prefijo', intencion: 'de qué tipo es: el ícono de su agente, ↳ de un hijo' },
            { selector: '.item-titulo', nombre: 'título', prop: 'titulo', intencion: 'el nombre' },
            { selector: '.item-sufijo', nombre: 'sufijo', prop: 'sufijo', intencion: 'una marca chica después: público (dos aros que se cruzan), una cuenta' },
        ],
    },
    {
        clave: 'fin', selector: '.item-fin', nombre: 'fin', pregunta: '¿qué tiene y qué le hago?',
        intencion: 'Pegado a la derecha, en columna con las otras filas: primero lo que se mira (el aviso, la meta), después lo que '
            + 'se aprieta. Las acciones de a mano no ocupan lugar: al pasar el mouse se despliegan desde la derecha sobre el final, tras un '
            + 'separador tenue que las aparta del texto (aquí, al lado, para verlas). El ⋯ va siempre al último; en el teléfono, que no tiene mouse, es lo único que queda.',
        partes: [
            { selector: '.item-aviso', nombre: 'aviso', prop: 'aviso', intencion: 'algo nuevo que pide mirarlo: un punto si hay sin leer, ⚠ abierto en dos' },
            { selector: '.item-meta', nombre: 'meta', prop: 'meta', intencion: 'un dato tenue que no se aprieta: hace cuánto, su tecla' },
            { selector: '.item-fin > .item-accion', nombre: 'fija', prop: 'fijas', intencion: 'una acción que se ve siempre: ▷ abrir el hilo de un agente que no lo tiene, ≡ ver todos los agentes' },
            { selector: '.item-menu', nombre: 'menú ⋯', prop: 'menu', intencion: 'todo lo que se le puede hacer; siempre el último, y en el teléfono lo único a la vista' },
            { selector: '.item-acciones > .item-accion:not(.item-menu)', todas: true, nombre: 'acciones', prop: 'acciones', intencion: 'las de a mano: se despliegan al pasar el mouse, tras un separador (archivar, descartar)' },
        ],
    },
];

/** El ítem de la lámina: un hilo con todas las piezas (y una ranura vacía). */
export const EJEMPLO: Item = {
    inicio: [S.prioridad(1, false, 'prioridad alta'), null, S.remoto('vive en servidor')],
    prefijo: [{ texto: 'A', tono: 'agente', ayuda: 'de agente:archivista' }], titulo: 'faro', sufijo: [S.publico('público')],
    aviso: S.nuevo('algo nuevo'), meta: { texto: '49m' },
    fijas: [{ accion: 'abrir-agente', id: 'archivista', icono: I.correr, ayuda: 'abrir su hilo' }],
    menu: { accion: 'menu', id: 'faro', icono: I.menu, ayuda: 'más' },
    acciones: [{ accion: 'archivar', id: 'faro', icono: I.archivar, ayuda: 'archivar' }, { accion: 'cerrar', id: 'faro', icono: I.descartar, peligro: true, ayuda: 'descartar' }],
    accion: 'ir', id: 'faro',
};

/** La tarjeta: un ítem que no se corta, en tres partes (como la de shadcn/ui: cabecera con su acción, contenido, pie).
 *  Dice lo que es cada parte para cualquier cosa que vaya en una tarjeta; el ejemplo es una tarea, porque es lo que hoy
 *  la usa (foco). */
export const SECCIONES_TARJETA: Seccion[] = [
    {
        clave: 'cabecera', selector: '.tarjeta-cabecera', nombre: 'cabecera', pregunta: '¿qué es y qué le hago?',
        intencion: 'Lo que se lee primero y lo que se aprieta. Sus círculos, a la altura de la primera línea; el título, entero, que es lo único '
            + 'que se estira; y sus acciones arriba a la derecha, en su propia columna: el título se parte antes de llegar a ellas y nunca queda '
            + 'tapado. Las acciones se ven al pasar el mouse y en la elegida; en el teléfono, solo el ⋯.',
        partes: [
            { selector: '.tarjeta-cabecera > .item-inicio', nombre: 'inicio', prop: 'inicio', intencion: 'las ranuras, de ancho fijo: los títulos de varias tarjetas empiezan en la misma columna' },
            { selector: '.item-ranura', n: 0, nombre: 'ranura', prop: 'inicio[0]', intencion: 'un círculo chico, que matiza al estado (cuánto importa)' },
            { selector: '.item-ranura', n: 1, nombre: 'ranura', prop: 'inicio[1]', intencion: 'el estado, grande: algo pasa ahora, te espera, terminó; vacía si no hay nada que decir' },
            { selector: '.item-prefijo', nombre: 'prefijo', prop: 'prefijo', intencion: 'antes del título, en su línea: de qué clase es o lo que le pasó, en una palabra' },
            { selector: '.tarjeta-titulo > .item-titulo', nombre: 'título', prop: 'titulo', intencion: 'su nombre, o lo que dice: entero, hasta tres líneas (holgada, sin tope)' },
            { selector: '.tarjeta-acciones > .item-accion:not(.item-menu)', todas: true, nombre: 'acciones', prop: 'acciones', intencion: 'las de todos los días, cada una en su celda cuadrada' },
            { selector: '.item-menu', nombre: 'menú ⋯', prop: 'menu', intencion: 'todo lo que se le puede hacer; siempre el último, y en el teléfono lo único a la vista' },
        ],
    },
    {
        clave: 'cuerpo', selector: '.tarjeta-cuerpo', nombre: 'cuerpo', pregunta: '¿qué más dice?',
        intencion: 'Si tiene: lo que se lee además del título (un resumen, una nota, lo que dejó quien la trabajó), tenue y donde empieza el '
            + 'título. Sin cuerpo, el pie sube.',
        partes: [{ selector: '.tarjeta-cuerpo', nombre: 'cuerpo', prop: 'cuerpo', intencion: 'texto corrido, tenue' }],
    },
    {
        clave: 'pie', selector: '.tarjeta-pie', nombre: 'pie', pregunta: '¿de dónde es y qué tiene?',
        intencion: 'Sus datos, en una línea y tenues; cada uno con su color solo si dice algo (un lugar al que se va, algo que falta). Pegados a '
            + 'la derecha, bajo las acciones, el aviso y la meta. Lo que no cabe se corta con «…»; lo de la derecha, nunca.',
        partes: [
            { selector: '.tarjeta-dato', n: 0, nombre: 'dato', prop: 'datos[0]', intencion: 'un dato, tenue (un código, de quién es)' },
            { selector: '.tarjeta-dato', n: 1, nombre: 'dato', prop: 'datos[1]', intencion: 'un lugar al que se va con un clic, en el acento' },
            { selector: '.tarjeta-dato', n: 2, nombre: 'dato', prop: 'datos[2]', intencion: 'algo que falta o no cuadra, en el color de su alerta' },
            { selector: '.tarjeta-fin', nombre: 'fin', prop: 'aviso · meta', intencion: 'pegado a la derecha, bajo las acciones' },
            { selector: '.item-aviso', nombre: 'aviso', prop: 'aviso', intencion: 'una marca, un círculo: señalada, algo nuevo' },
            { selector: '.item-meta', nombre: 'meta', prop: 'meta', intencion: 'un dato que no se aprieta: una fecha, hace cuánto, una cuenta; en su color si dice algo' },
        ],
    },
];

const accionesEjemplo: Accion[] = [
    { accion: 'estrella', icono: I.sinEstrella, ayuda: 'ponerle estrella' }, { accion: 'fecha', icono: I.fecha, ayuda: 'otra fecha' },
    { accion: 'instruccion', icono: I.instruccion, tono: 'agente', ayuda: 'instrucción' }, { accion: 'hecha', icono: I.hecha, ayuda: 'marcarla hecha' },
];

/** La tarjeta de la lámina: una tarea con todas las piezas. */
export const EJEMPLO_TARJETA: Tarjeta = {
    inicio: [S.prioridad(1, false, 'prioridad alta'), S.atencion('espera', false, 'te espera')],
    prefijo: [{ texto: 'pregunta', tono: 'atencion' }],
    titulo: 'Contestarle a Ana cómo seguimos con las plataformas de cursos y coordinar la reunión para acordar cuál',
    acciones: accionesEjemplo, menu: { accion: 'menu', icono: I.menu, ayuda: 'más' },
    cuerpo: 'Propone la segunda: cuesta menos en un año y soporte ya la conoce.',
    datos: [{ texto: 'T457' }, { texto: 'faro', tono: 'acento' }, { texto: 'sin tamaño', tono: 'atencion' }],
    aviso: S.estrella('con estrella'), meta: { texto: '-2d', tono: 'peligro' },
};

// ── la sección de lista (componentes/seccion.ts) ──

export const SECCIONES_LISTA: Seccion[] = [
    {
        clave: 'cabecera', selector: '.item.cabecera', nombre: 'cabecera', pregunta: '¿qué grupo es y qué le hago?',
        intencion: 'Un ítem en la tinta de las cabeceras. Un clic en toda la fila abre o pliega la sección, y así queda: se recuerda como la '
            + 'dejó la persona, también al recargar. Plegada, es lo único que se ve del grupo.',
        partes: [
            { selector: '.item.cabecera .item-ranura', nombre: 'flecha', prop: 'abierta', intencion: 'si está abierta o plegada' },
            { selector: '.item.cabecera .item-titulo', nombre: 'título', prop: 'titulo', intencion: 'como se escribe: las mayúsculas las pone el tema' },
            { selector: '.item.cabecera .item-sufijo', nombre: 'cuenta', prop: 'cuenta', intencion: 'cuántas cosas tiene, tenue; en cero, nada' },
            { selector: '.item.cabecera .item-accion', n: 0, nombre: 'acciones', prop: 'acciones', intencion: 'lo que se hace con el grupo, siempre a la vista' },
            { selector: '.item.cabecera .item-accion', n: 1, nombre: 'nuevo', prop: 'nuevo', intencion: 'el «+», al último: en la misma columna en todas' },
        ],
    },
    {
        clave: 'herramientas', selector: '.herram', nombre: 'herramientas', pregunta: '¿cómo encuentro una?',
        intencion: 'La barra del buscador, con su línea abajo de borde a borde. Es opcional: un grupo corto no la lleva. Con ella viene la fila '
            + '«nada calza», oculta hasta que el filtro no deja nada.',
        partes: [
            { selector: '.herram .buscador', nombre: 'buscador', prop: 'herramientas.placeholder', intencion: 'filtra las filas del grupo, también las de sus submenús' },
            { selector: '.herram .orden', nombre: 'orden', prop: 'herramientas.orden', intencion: 'también el de sus submenús' },
            { selector: '.herram .extra-de-muestra', nombre: 'extra', prop: 'herramientas.extra', intencion: 'lo que sume la lista' },
        ],
    },
    {
        clave: 'filas', selector: '.item:not(.cabecera)', todas: true, nombre: 'filas', pregunta: '¿qué hay?',
        intencion: 'Ítems, en una sola grilla; al final puede venir un submenú, que es una fila más. Sin ninguna, la fila que lo dice. Solo se '
            + 'arman si la sección está abierta.',
        partes: [
            { selector: '.item:not(.cabecera)', n: 0, nombre: 'fila', prop: 'filas()', intencion: 'un ítem; si no hay ninguna, el de `vacia`' },
            { selector: '.item.submenu', nombre: 'submenú', prop: 'submenu()', intencion: 'una sección adentro, con su propio plegado' },
        ],
    },
];

/** El ejemplo de la lámina: con todo lo que puede tener. Las filas son de mentira. */
export const EJEMPLO_LISTA: Omit<PropsSeccion, 'filas'> = {
    clave: 'ejemplo', titulo: 'hilos', cuenta: 2, ayuda: 'los hilos abiertos', abierta: true,
    acciones: [{ accion: 'cmd', id: 'lista', icono: I.lista, ayuda: 'verlos todos' }],
    nuevo: { accion: 'cmd', id: 'nuevo', icono: I.nuevo, ayuda: 'hilo nuevo' },
    herramientas: { grupo: 'muestra', placeholder: 'hilos', ayuda: 'buscar por nombre',
        orden: { activa: 'nombre', opciones: [{ clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre' }, { clave: 'reciente', icono: I.reloj, ayuda: 'reciente' }] },
        extra: `<span class="ord i extra-de-muestra">${I.maquinas}</span>` },
};
