// La gramática visual de telar: de qué está hecho el diseño y qué quiere decir cada forma. Lo que el catálogo muestra en
// «fundamentos», como datos.
//
// Hay cuatro clases de signos y cada una dice una sola cosa: el círculo dice cómo está algo (su estado); el rectángulo,
// dónde va (el orden); el ícono de la letra, qué se le hace o qué clase de cosa es (una acción, un agente); el texto, su
// nombre y sus datos. Un estado nunca es un ícono de la letra, ni una acción un círculo.
//
// Lo redondo y lo recto se describen por sus variables, como las variables visuales de Bertin: cada variable responde
// una sola pregunta, y cada valor tiene un solo concepto. Así se separan (dos variables no dicen lo mismo), cada cosa
// se dice de una sola manera, y lo que se necesite decir sale de combinarlas: un hilo que terminó es «relación: dentro,
// con algo lleno» (con contenido) · «tamaño: grande» (lo principal) · «color: de estado» · «tono: pleno» (sin ver).
//
// Los conceptos son generales a propósito: un valor sirve para todo lo que comparte su sentido (el aro es «falta»: te
// espera, por hacer, pausado). Lo que usa una vista sale de aquí (derivadas, y su código en componentes/senales.ts); si
// algo no cabe en ningún valor, se agrega el concepto aquí antes de dibujarlo. La prueba (pruebas/componentes.mjs)
// revisa que cada figura del círculo tenga su concepto, que ningún concepto se repita, que cada derivada apunte a uno
// que existe y que nada pida un cuarto tamaño.

import type { Circulo } from './circulo';
import type { Pieza, Tono } from './item';
import * as S from './senales';

/** Un círculo dibujado, con su color. */
export type Trazo = Circulo & { tono?: Tono };
const de = (p: Pieza | null): Trazo => ({ ...p?.circulo, tono: p?.tono });

/** Un valor de una variable: su concepto, en una o dos palabras, y para qué sirve, de lo general a lo particular. */
export interface Valor {
    clave: string;
    nombre: string;
    dice: string;
    sirve: string[];
    /** cómo se ve (lo redondo); lo recto lo dibuja el catálogo por su clave */
    dibujo?: Trazo[];
}
/** Una variable: la única pregunta que responde y sus valores. */
export interface Variable { clave: string; nombre: string; pregunta: string; que: string; valores: Valor[] }

/** Las clases de signos, cada una con su trabajo. */
export const SIGNOS: { nombre: string; dice: string; ejemplo: string }[] = [
    { nombre: 'círculo', dice: 'cómo está algo', ejemplo: 'trabajando, te espera, terminó, su prioridad, si vive en otra máquina' },
    { nombre: 'rectángulo', dice: 'dónde va', ejemplo: 'la fila, la sección, la ventana, la ranura, un separador' },
    { nombre: 'ícono de la letra', dice: 'qué se le hace, o qué clase de cosa es', ejemplo: 'archivar, plegar, el ⋯, el + de crear; la A de un agente' },
    { nombre: 'texto', dice: 'su nombre y sus datos', ejemplo: 'faro, 12m, → servidor' },
];

export const REDONDO: Variable[] = [
    {
        clave: 'llenado', nombre: 'llenado', pregunta: '¿cuánto hay?',
        que: 'Lo que hay de algo, de nada a todo, de a cuartos. Es la única variable de cantidad.',
        valores: [
            { clave: 'aro', nombre: 'aro', dice: 'falta', sirve: ['te toca: falta lo tuyo (te espera)', 'por hacer', 'detenido, pausado, sin conexión'], dibujo: [{ lleno: 0 }] },
            { clave: 'parte', nombre: 'en parte', dice: 'cuánto', sirve: ['cuánto importa (la prioridad)', 'cuánto avanzó, cuánto queda'], dibujo: [{ lleno: .25 }, { lleno: .5 }, { lleno: .75 }] },
            { clave: 'lleno', nombre: 'lleno', dice: 'hay', sirve: ['algo pasa ahora (trabajando)', 'hecho, completo', 'encendido, conectado'], dibujo: [{}] },
        ],
    },
    {
        clave: 'tamano', nombre: 'tamaño', pregunta: '¿qué rango tiene el signo?',
        que: 'Cuánto pesa frente a los que tiene al lado: qué se lee primero. Tres y ninguno más; para decir más, no se agranda: se compone.',
        valores: [
            { clave: 'grande', nombre: 'grande', dice: 'lo principal', sirve: ['el estado de una fila', 'una figura (ocupa lo de uno grande)'], dibujo: [{}] },
            { clave: 'chico', nombre: 'chico', dice: 'acompaña', sirve: ['lo que matiza al principal: la prioridad junto al estado', 'las partes de una figura o de una serie'], dibujo: [{ tam: 'chico' }] },
            { clave: 'punto', nombre: 'punto', dice: 'solo está', sirve: ['hay algo, sin cuánto (sin prioridad)', 'algo nuevo, que no interrumpe', 'una marca sobre una línea o en una esquina'], dibujo: [{ tam: 'punto' }] },
        ],
    },
    {
        clave: 'relacion', nombre: 'relación', pregunta: '¿con qué se relaciona?',
        que: 'Cómo se junta con otros círculos: de a dos en una figura, o varios en fila. Lo que dice una figura sale de su relación y de lo que dice cada parte: dentro de un aro, un punto lo señala, algo lleno es su contenido, otro aro lo hace contenedor.',
        valores: [
            { clave: 'sola', nombre: 'sola', dice: 'en sí', sirve: ['lo que la cosa es, sin otra'], dibujo: [{}] },
            { clave: 'centro', nombre: 'dentro: un punto', dice: 'señalado', sirve: ['el elegido entre varios (una opción marcada)', 'el que está puesto: el modo, el tema'], dibujo: [{ figura: 'centro' }] },
            { clave: 'diana', nombre: 'dentro: algo lleno', dice: 'con contenido', sirve: ['terminó y dejó algo que ver', 'tiene algo adentro: un borrador, un adjunto'], dibujo: [{ figura: 'diana' }] },
            { clave: 'doble', nombre: 'dentro: otro aro', dice: 'contenedor', sirve: ['un lugar que contiene: una máquina, un grupo, un espacio'], dibujo: [{ figura: 'doble' }] },
            { clave: 'satelite', nombre: 'afuera: un punto', dice: 'en otra parte', sirve: ['vive en otra máquina (aquí no está: el aro; allá sí: el punto)', 'viene de afuera'], dibujo: [{ figura: 'satelite' }] },
            { clave: 'enlace', nombre: 'cruce', dice: 'comparte', sirve: ['lo ven otros (público)', 'lo mismo en dos lugares (abierto en dos, sincronizado)'], dibujo: [{ figura: 'enlace' }] },
            { clave: 'serie', nombre: 'serie', dice: 'varios', sirve: ['cuántos de cuántos, cada uno con su llenado', 'varias cosas juntas, cada una con su estado'], dibujo: [{ tam: 'chico' }, { tam: 'chico' }, { tam: 'chico', lleno: 0 }, { tam: 'chico', lleno: 0 }] },
        ],
    },
    {
        clave: 'movimiento', nombre: 'movimiento', pregunta: '¿está cambiando?',
        que: 'Solo una transición que termina pronto, en su lugar y de a cuartos; nada más se mueve, ni el texto ni el color. Lo que dura (trabajar) es un estado y va quieto.',
        valores: [
            { clave: 'quieto', nombre: 'quieto', dice: 'no cambia', sirve: ['todo estado, aunque dure: trabajando, te espera'], dibujo: [{ lleno: .5 }] },
            { clave: 'vacia', nombre: 'se vacía', dice: 'se va', sirve: ['cerrar, archivar, descartar'], dibujo: [{ mov: 'vacia' }] },
            { clave: 'llena', nombre: 'se llena', dice: 'llega', sirve: ['marcar hecha una tarea', 'instalar una versión'], dibujo: [{ mov: 'llena' }] },
            { clave: 'gira', nombre: 'gira', dice: 'en camino', sirve: ['viajar a otra máquina (gira el satélite)', 'enviar, hacer una acción'], dibujo: [{ mov: 'gira' }, { figura: 'satelite', mov: 'gira' }] },
        ],
    },
    {
        clave: 'color', nombre: 'color', pregunta: '¿de qué tipo es?',
        que: 'El matiz dice la clase. Acompaña a la forma: en blanco y negro, cada forma sigue diciendo lo suyo.',
        valores: [
            { clave: 'de-estado', nombre: 'de estado', dice: 'qué le pasa', sirve: ['trabajando, te espera, terminó'], dibujo: [{ tono: 'trabajando' }, { lleno: 0, tono: 'espera' }, { figura: 'diana', tono: 'termino' }] },
            { clave: 'de-prioridad', nombre: 'de prioridad', dice: 'su prioridad', sirve: ['alta, media, baja'], dibujo: [{ tam: 'chico', tono: 'p1' }, { tam: 'chico', lleno: .5, tono: 'p2' }, { tam: 'chico', lleno: 0, tono: 'p3' }] },
            { clave: 'de-lugar', nombre: 'de lugar o de dueño', dice: 'de dónde o de quién', sirve: ['lo remoto', 'lo de un agente'], dibujo: [{ figura: 'satelite', tono: 'remoto' }, { tono: 'agente' }] },
            { clave: 'de-alerta', nombre: 'de alerta', dice: 'bien, cuidado o mal', sirve: ['algo nuevo, bueno', 'un cuidado', 'falló'], dibujo: [{ tam: 'punto', tono: 'exito' }, { lleno: 0, tono: 'atencion' }, { lleno: 0, tono: 'peligro' }] },
        ],
    },
    {
        clave: 'tono', nombre: 'tono', pregunta: '¿sigue vigente?',
        que: 'La luz del color: pleno es ahora, tenue es lo que ya pasó, apagado es lo que no se puede usar.',
        valores: [
            { clave: 'pleno', nombre: 'pleno', dice: 'ahora', sirve: ['lo que está pasando', 'terminó y no lo has visto'], dibujo: [{ tono: 'trabajando' }] },
            { clave: 'tenue', nombre: 'tenue', dice: 'ya pasó', sirve: ['archivado, cerrándose', 'lo que se deja ver aunque ya no esté vigente'], dibujo: [{ tono: 'tenue' }] },
            { clave: 'apagado', nombre: 'apagado', dice: 'no disponible', sirve: ['lo que no se puede elegir', 'lo que no aplica aquí'], dibujo: [{ tono: 'apagado' }] },
        ],
    },
];

export const RECTO: Variable[] = [
    {
        clave: 'superficie', nombre: 'superficie', pregunta: '¿qué es este rectángulo?',
        que: 'Un rectángulo entero: con un fondo, con marco o reservado; sin nada, es parte del flujo. El fondo es escaso: en una lista solo lo lleva la selección, y lo demás se parte con líneas y aire (cómo se parte, abajo).',
        valores: [
            { clave: 'seleccion', nombre: 'selección', dice: 'aquí estás', sirve: ['la fila donde estás, la pestaña abierta', 'con el matiz del acento (los de nivel son solo luz); no cuenta como nivel'] },
            { clave: 'marco', nombre: 'marco', dice: 'aparte', sirve: ['una cosa que se abre y se cierra, encima de lo demás: una ventana, un menú'] },
            { clave: 'ranura', nombre: 'ranura', dice: 'un lugar reservado', sirve: ['el de un círculo, del mismo ancho en cada fila: así todo se alinea'] },
        ],
    },
    {
        clave: 'linea', nombre: 'línea', pregunta: '¿qué separa?',
        que: 'Una línea de un píxel. Entera en un lado, el lado dice qué separa; corta (la mitad del alto) entre dos cosas de una fila, las aparta sin partir la fila.',
        valores: [
            { clave: 'arriba', nombre: 'arriba', dice: 'empieza otra parte', sirve: ['el separador entre secciones'] },
            { clave: 'abajo', nombre: 'abajo', dice: 'aquí se escribe', sirve: ['un campo, un buscador'] },
            { clave: 'izquierda', nombre: 'a la izquierda', dice: 'cuelga de', sirve: ['lo que depende de lo de arriba: un hijo bajo su padre', 'un recorrido, con sus momentos encima'] },
            { clave: 'derecha', nombre: 'a la derecha', dice: 'hasta aquí', sirve: ['el borde de una columna: la barra, la lista'] },
            { clave: 'corta', nombre: 'corta, entre dos', dice: 'aparta', sirve: ['un grupo de acciones de lo que tiene al lado: las que aparecen en un ítem, el grupo de ordenar (una a cada lado, en su púrpura)', 'al medio de su propia celda cuadrada (un corte); del color de su tipo, si lo tiene; si no, apenas se ve'] },
        ],
    },
    {
        clave: 'lugar', nombre: 'lugar del círculo', pregunta: '¿de qué habla el círculo?',
        que: 'Dónde está un círculo en lo recto dice de qué es su estado. Adentro, con aire, o justo sobre una línea; nunca a medio pegar.',
        valores: [
            { clave: 'en-ranura', nombre: 'en su ranura', dice: 'el estado de la fila', sirve: ['cómo está un hilo: trabajando, te espera, terminó'], dibujo: [{ tono: 'trabajando' }] },
            { clave: 'en-esquina', nombre: 'en la esquina', dice: 'le pasó algo', sirve: ['algo nuevo en una pestaña o en una sección plegada', 'un aviso sobre una ventana'], dibujo: [{ tam: 'punto', tono: 'exito' }] },
            { clave: 'en-linea', nombre: 'sobre una línea', dice: 'un momento', sirve: ['lo que pasó, en orden: una historia', 'dónde va ahora, entre un principio y un fin'], dibujo: [{ tam: 'chico' }, { tam: 'chico' }, { tam: 'chico', lleno: 0 }] },
            { clave: 'en-riel', nombre: 'en un riel', dice: 'sí o no', sirve: ['el interruptor: aro a la izquierda, no; lleno a la derecha, sí'], dibujo: [{ tam: 'chico', lleno: 0, tono: 'tenue' }, { tam: 'chico', tono: 'acento' }] },
        ],
    },
];

/** Las reglas: lo que vale para todo lo de arriba. */
/** Cómo se parte un rectángulo en otros: qué es cada parte respecto de las de al lado y de la que la contiene, y con qué
 *  (un solo medio) se marca. De afuera hacia adentro. */
export interface Parte { clave: string; nombre: string; es: string; marca: string; ejemplo: string }
export const PARTES: Parte[] = [
    { clave: 'pantalla', nombre: 'pantalla', es: 'lo que llena la columna de la derecha: un hilo o una app del dashboard', marca: 'su barra arriba, de borde a borde: el fondo de barra y una línea abajo. El cuerpo, sin margen propio: sus líneas tocan la columna de al lado', ejemplo: 'un hilo; ahora, tareas, proyectos, la pestaña de un módulo' },
    { clave: 'columna', nombre: 'columna', es: 'una zona al lado de otra, que conviven', marca: 'una línea a la derecha (o a la izquierda): hasta aquí', ejemplo: 'la barra de hilos; la hoja de la derecha' },
    { clave: 'seccion', nombre: 'sección', es: 'otra parte, de la misma clase que la de arriba', marca: 'una línea arriba, y su cabecera', ejemplo: 'DASHBOARD, AGENTES, HILOS, APPS' },
    { clave: 'submenu', nombre: 'submenú', es: 'una sección dentro de otra, de sus mismas filas', marca: 'nada propio: su cabecera es una fila más, con la flecha de plegar justo antes de su nombre, en la tinta de las cabeceras; sus filas, en la grilla de las de arriba', ejemplo: 'archivo, dentro de HILOS' },
    { clave: 'banda', nombre: 'banda', es: 'una parte de otra clase dentro de una sección: no es su contenido, obra sobre él', marca: 'nada propio: la dice lo que trae (el campo con su línea abajo, los íconos); sin fondo ni línea', ejemplo: 'las herramientas de una lista: buscar, ordenar, las máquinas' },
    { clave: 'grupo', nombre: 'grupo', es: 'unas piezas que hacen una sola cosa, dentro de una banda o de una fila', marca: 'un corte a cada lado (una línea corta al medio de una celda cuadrada), del color de su tipo si lo tiene', ejemplo: 'el grupo de ordenar: su ícono padre y las opciones, entre dos líneas púrpura' },
    { clave: 'fila', nombre: 'fila', es: 'una de varias iguales', marca: 'nada: la separa su alto', ejemplo: 'un hilo, una tarea' },
    { clave: 'tarjeta', nombre: 'tarjeta', es: 'una fila que no se corta: una cosa entera que se mira y se decide de a una, entre pocas', marca: 'nada propio: aire entre una y otra (ni marco ni fondo); la elegida, el fondo de la selección', ejemplo: 'una tarea en foco' },
    { clave: 'ranura', nombre: 'ranura', es: 'un lugar que alinea', marca: 'nada: es invisible', ejemplo: 'el lugar del estado, el de la prioridad' },
    { clave: 'ventana', nombre: 'ventana', es: 'una cosa aparte, encima de todo: se abre y se cierra', marca: 'un marco', ejemplo: '⌘K, elegir, confirmar' },
];

/** Las reglas de cómo se parte. */
export const REGLAS_PARTIR: string[] = [
    'Toda pantalla lleva su barra (componentes/pantalla.ts): el nombre, las vistas, lo que resume y las acciones de la pantalla van ahí y en ningún otro lugar. Su cuerpo no tiene margen: el aire va dentro de cada fila y las líneas van de borde a borde.',
    'Cada corte se marca con un solo medio: una línea, un fondo o un marco. Nunca dos para lo mismo.',
    'Lo de la misma clase se separa con lo mínimo: las filas, con su alto; las secciones, con una línea arriba.',
    'El fondo es escaso: en una lista lo lleva solo la selección («aquí estás»). Lo demás se parte con líneas y aire: una banda no lleva marca propia (la dice lo que trae); un grupo, una línea corta a cada lado.',
    'Un fondo nunca va dentro de otro, salvo la selección, que va sobre cualquiera. Si una zona entera (una columna) necesita su fondo, es uno, de borde a borde.',
    'Un grupo se ajusta a lo que agrupa; a cada lado, un corte en su celda cuadrada, con una línea de la mitad del alto de la fila y el color de su tipo.',
    'Nunca un marco dentro de otro, ni un marco para algo que no se abre aparte. Una tarjeta no es una caja: es una fila más alta, y se aparta de la siguiente con aire.',
    'Lo de adentro guarda sus propias marcas: el buscador, en su banda, sigue con su línea abajo.',
];

export const REGLAS: string[] = [
    'Cada clase de signo hace lo suyo: el círculo, el estado; el rectángulo, el orden; el ícono de la letra, la acción o la clase de cosa; el texto, el nombre. Un estado nunca es un ícono de la letra.',
    'Cada variable responde una sola pregunta y cada valor tiene un solo concepto. Lo que no cabe en ninguno se agrega aquí antes de dibujarlo.',
    'Tres tamaños de círculo (punto, chico, grande) y ninguno más. Un punto no lleva llenado ni figura: es demasiado chico para decir cuánto.',
    'Una figura junta dos círculos, no más. La serie es otra cosa: varios iguales, en fila.',
    'Lo recto no entra en lo redondo: un círculo nunca lleva adentro una línea, una letra ni un rectángulo. Y no se deforma: ni óvalos ni arcos sueltos.',
    'Sin nada que decir, la ranura queda vacía: no se pone un punto por poner. La prioridad es la excepción, siempre se dice, salvo en un hijo, que hereda la de su padre.',
    'Se mueve solo lo que está cambiando, y en una fila, a lo más una cosa a la vez.',
    'Sobre un fondo lleno (la selección), el círculo se cala: toma el color de la página.',
    'Lo recto: líneas de un píxel, ángulos rectos, fondos enteros. Sin esquinas redondeadas, sombras, diagonales ni degradados.',
    'El color acompaña a la forma: en blanco y negro, cada forma tiene que seguir diciendo lo suyo.',
    'El tamaño de la letra no dice qué importa más: eso lo dicen la forma, el rango del círculo y el color.',
    'La grilla: todo se mide en celdas, como en una letra monoespaciada. Las letras van en la celda de la fuente (rectangular); los íconos, los símbolos y los espacios entre grupos, en celdas cuadradas del alto de la fila. Entre dos grupos de una fila va una celda cuadrada, vacía o con su corte, y entre dos columnas de una tabla, una vacía; dentro de un grupo, las celdas van juntas, salvo entre íconos.',
    'Entre dos íconos seguidos, siempre un espacio cuadrado: el vacío entre uno y otro mide el alto de la fila, también dentro de un grupo (las vistas de una pantalla, sus acciones, las opciones del orden). Si son botones, cada uno en su celda, las celdas se apartan en el ancho de un ícono (--entre-celdas); sueltos, en un cuadrado (--entre-iconos).',
    'Un botón de ícono ocupa una celda cuadrada, la misma para todos: del alto de la fila, con el ícono al medio. Nada de palabras ni signos de distinto ancho en su lugar («a-z», «!», «‹»): si hace falta una palabra, es un botón de palabra, aparte («home»).',
    'Todo lo que ordena una lista, sea un grupo de íconos (orden) o los encabezados de una tabla (cabecera de tabla), se rige igual: un clic en la opción que rige vuelve al orden de siempre, y la que rige se marca con un solo color (propuesto: --orden-activa).',
];

/** Lo que telar dice con todo eso: para qué, con qué conceptos (claves de valores), por qué, y qué usaba antes. */
export interface Derivada { uso: string; conceptos: string[]; dibujo: Trazo[]; por: string; antes: string; explorar?: boolean }

export const DERIVADAS: Derivada[] = [
    { uso: 'trabajando', conceptos: ['lleno', 'grande', 'de-estado'], dibujo: [de(S.atencion('trabajando'))], por: 'hay: algo pasa ahora', antes: 'un círculo de la letra' },
    { uso: 'te espera', conceptos: ['aro', 'grande', 'de-estado'], dibujo: [de(S.atencion('espera'))], por: 'falta: lo tuyo', antes: 'una campana' },
    { uso: 'terminó, sin ver', conceptos: ['diana', 'de-estado', 'pleno'], dibujo: [de(S.atencion('termino'))], por: 'con contenido: dejó algo que ver', antes: 'un visto bueno verde' },
    { uso: 'terminó, ya visto', conceptos: [], dibujo: [], por: 'nada que decir: la ranura queda vacía (las reglas)', antes: 'el visto bueno, tenue, a la vista siempre' },
    { uso: 'la prioridad', conceptos: ['parte', 'chico', 'de-prioridad'], dibujo: [1, 2, 3].map(p => de(S.prioridad(p))), por: 'cuánto importa; chica, porque acompaña al estado', antes: 'círculos de la letra, del tamaño del estado' },
    { uso: 'crear uno nuevo en una sección', conceptos: [], dibujo: [], por: 'una acción: el + de la letra, sin la palabra; la última de la cabecera de su sección, en el borde derecho (componentes/acciones.ts)', antes: '«+ nuevo» en palabras, en distinto lugar según la cabecera' },
    { uso: 'un hijo (cuelga de otro hilo o de un agente)', conceptos: [], dibujo: [], por: 'hereda la prioridad de su padre: su ranura queda vacía', antes: 'su propia prioridad, repetida bajo la del padre' },
    { uso: 'la fase de un proyecto', conceptos: ['aro', 'parte', 'lleno', 'grande'], dibujo: [0, .25, .5, .75, 1].map(a => de(S.fase(a))), por: 'cuánto avanzó, de a cuartos: en preparación un aro, en desarrollo a medias, cerrado lleno y tenue', antes: 'su estado en palabras («Activo»), en color' },
    { uso: 'el estado de una iniciativa', conceptos: ['punto', 'parte', 'aro', 'lleno', 'chico', 'de-estado', 'de-alerta', 'tenue', 'apagado'],
        dibujo: [...S.CLASES_ESTADO.map(c => de(S.estadoIniciativa(c))), de(S.estadoIniciativa(undefined, true))],
        por: 'cuánto avanzó y si sigue, junto a su palabra: idea un punto, en preparación un cuarto, en curso a medias (pasa ahora), en pausa un aro tenue, terminada llena y verde, descartada llena y apagada; uno fuera del vocabulario, un aro de cuidado',
        antes: 'su estado en palabras, como lo escribiera cada ficha' },
    { uso: 'un proyecto pausado', conceptos: ['aro', 'tenue'], dibujo: [de(S.pausado())], por: 'falta: detenido; tenue, porque no está vigente', antes: 'la palabra «Pausado»' },
    { uso: 'un proyecto terminado que falta cerrar', conceptos: ['lleno', 'pleno'], dibujo: [de(S.terminado())], por: 'hay: hecho; pleno, porque todavía pide el cierre (cerrado es lleno y tenue)', antes: '«Activo» aunque estuviera entregado' },
    { uso: 'un proyecto con algo que no cuadra', conceptos: ['parte', 'de-alerta'], dibujo: [de(S.fase(.75, 'venció'))], por: 'un cuidado: venció sin cerrarse, o lleva más horas que las del plan; lo dice su ayuda', antes: 'nada: «Activo» igual' },
    { uso: 'la etapa de un proyecto (su columna)', conceptos: [], dibujo: [], por: 'qué clase de trabajo hay en ella, un ícono de la letra: preparar (la lista), partir (el cohete), desarrollar (las herramientas), cerrar (el paquete: se entrega), cerrado (el doble visto). Cuánto avanzó lo dice el círculo de su fase; la palabra, al pasar y en la tabla extendida', antes: 'la etapa en palabras, en una columna de 11 letras' },
    { uso: 'sin prioridad', conceptos: ['punto'], dibujo: [de(S.prioridad(0))], por: 'está, sin cuánto', antes: 'un punto de la letra' },
    { uso: 'un hilo dormido (su agente se cerró por estar quieto; abrirlo o escribirle lo despierta)', conceptos: ['aro', 'grande', 'tenue', 'diana'],
        dibujo: [de(S.dormido()), de(S.dormido(true))],
        por: 'falta: detenido, como un proyecto pausado; tenue, porque su agente no corre. Si terminó y no lo has visto, su diana, tenue: lo que dejó se sigue diciendo',
        antes: 'nada: el agente quedaba abierto' },
    { uso: 'en otra máquina', conceptos: ['satelite', 'de-lugar'], dibujo: [de(S.remoto())], por: 'en otra parte', antes: 'dos flechas' },
    { uso: 'viajando a otra máquina', conceptos: ['satelite', 'gira'], dibujo: [de(S.viaja())], por: 'en otra parte, en camino: el punto da la vuelta', antes: 'medio círculo que gira' },
    { uso: 'cerrándose, archivándose', conceptos: ['vacia', 'tenue'], dibujo: [de(S.sale())], por: 'se va', antes: 'lo mismo' },
    { uso: 'público', conceptos: ['enlace', 'tenue'], dibujo: [de(S.publico())], por: 'comparte: lo ven otros', antes: 'un rombo' },
    { uso: 'algo nuevo', conceptos: ['punto', 'de-alerta', 'pleno'], dibujo: [de(S.nuevo())], por: 'está, sin interrumpir', antes: 'un círculo de texto' },
    { uso: 'alguien que está, o sin noticias', conceptos: ['lleno', 'aro', 'chico'], dibujo: [de(S.presente(true)), de(S.presente(false))], por: 'hay, o falta; chico, porque lo principal es su nombre', antes: 'círculos de la letra' },
    { uso: 'algo nuevo en una pestaña o sección plegada', conceptos: ['punto', 'en-esquina'], dibujo: [de(S.nuevo())], por: 'le pasó algo, al rectángulo entero', antes: 'nada', explorar: true },
    { uso: 'falló, necesita tu mano', conceptos: ['aro', 'de-alerta'], dibujo: [{ lleno: 0, tono: 'peligro' }], por: 'falta lo tuyo, porque algo falló', antes: 'texto rojo', explorar: true },
    { uso: 'abierto en dos', conceptos: ['enlace', 'de-alerta'], dibujo: [{ figura: 'enlace', tono: 'atencion' }], por: 'lo mismo en dos lugares, y es un cuidado', antes: 'un triángulo de aviso', explorar: true },
    { uso: 'el elegido entre varios (el modo, el tema)', conceptos: ['centro'], dibujo: [{ figura: 'centro', tono: 'acento' }, { lleno: 0, tono: 'tenue' }], por: 'señalado, entre aros que se pueden elegir', antes: 'un chip lleno', explorar: true },
    { uso: 'un interruptor', conceptos: ['en-riel'], dibujo: [{ tam: 'chico', tono: 'acento' }], por: 'sí o no, y se cambia', antes: 'por revisar (configuración)', explorar: true },
    { uso: 'una máquina', conceptos: ['doble'], dibujo: [{ figura: 'doble', tono: 'remoto' }], por: 'un lugar que contiene hilos', antes: 'su nombre, en texto', explorar: true },
    { uso: 'una tarea en curso (un hilo la trabaja)', conceptos: ['lleno', 'grande', 'de-estado'], dibujo: [de(S.atencion('trabajando'))], por: 'hay: algo pasa ahora, como un hilo trabajando', antes: 'su código en azul' },
    { uso: 'una tarea que te espera (un agente dejó algo para decidir)', conceptos: ['aro', 'grande', 'de-estado'], dibujo: [de(S.atencion('espera'))], por: 'falta: lo tuyo, como un hilo que te espera; la palabra de lo que dejó («pregunta», «preparado») va antes del texto', antes: 'solo la palabra, en negrita' },
    { uso: 'la urgente (P0) de una tarea', conceptos: ['lleno', 'chico', 'de-alerta'], dibujo: [de(S.urgente())], por: 'cuánto importa: todo, y es un cuidado', antes: 'un círculo de la letra, en rojo y en negrita' },
    { uso: 'una tarea con estrella', conceptos: ['centro', 'de-alerta'], dibujo: [de(S.estrella())], por: 'señalada: la elegiste entre las demás (va siempre en «esta semana»)', antes: 'una estrella de la letra, amarilla, en su columna' },
    { uso: 'una tarjeta (una tarea en foco)', conceptos: [], dibujo: [], por: 'una fila que no se corta, en tres partes: la cabecera (sus círculos, el título entero y sus acciones arriba a la derecha), el cuerpo si tiene y el pie (sus datos y la meta); aire entre una y otra, sin marco ni fondo; la elegida, con el de la selección. Lo que no cuadra va en el color de su alerta', antes: 'un recuadro con el fondo de la barra; la elegida, con borde azul y una raya; la vencida, con una raya roja a la izquierda' },
    { uso: 'lo que se le hace a la tarjeta elegida (las casillas de foco)', conceptos: ['corta'], dibujo: [], por: 'una banda de íconos arriba de las tarjetas, cada uno en el color de lo que hace, en grupos entre cortes; lo que se elige casi siempre (hoy, el viernes, rápida, bloquear tiempo), en palabras junto a la suya; arrastrando una tarjeta, cada una dice su nombre', antes: 'cajas punteadas con la palabra, en una columna a la derecha' },
    { uso: 'una tarea: por hacer, a medias, hecha', conceptos: ['aro', 'parte', 'lleno'], dibujo: [{ lleno: 0 }, { lleno: .5 }, {}], por: 'falta, cuánto, hay', antes: 'casillas de la letra', explorar: true },
    { uso: 'un hijo bajo su padre', conceptos: ['izquierda'], dibujo: [], por: 'cuelga de: una línea a la izquierda', antes: 'una flecha ↳', explorar: true },
    { uso: 'las herramientas de una lista (la barra de filtros)', conceptos: ['abajo'], dibujo: [], por: 'una banda (cómo se parte): sin fondo ni línea, la dicen su campo (su línea abajo) y sus íconos', antes: 'un fondo de banda, que con la selección y el grupo eran demasiados fondos' },
    { uso: 'el grupo de ordenar', conceptos: ['corta'], dibujo: [], por: 'aparta: una línea corta a cada lado, en púrpura (el matiz dice el tipo)', antes: 'un fondo púrpura; antes, íconos sueltos' },
    { uso: 'las acciones que aparecen en un ítem', conceptos: ['corta'], dibujo: [], por: 'aparta las acciones del texto: una línea corta, que apenas se ve', antes: 'lo mismo' },
    { uso: 'el nombre de una app (su pantalla)', conceptos: [], dibujo: [], por: 'en la barra de su pantalla, en su tinta y con el peso de una cabecera: el mismo nombre que su fila en la barra de hilos', antes: 'un título distinto en cada pantalla: con raya y cuenta en un fondo, «‹ leer», «Proyectos», ninguno' },
    { uso: 'las vistas de una pantalla (foco y lista, el día y la semana, la terminal y la lectura)', conceptos: [], dibujo: [], por: 'íconos en su barra, después del nombre; la que se ve, en violeta', antes: 'subpestañas en palabras, en una fila subrayada; «día · semana» en un recuadro' },
    { uso: 'mandarle algo a un hilo o a un agente (la instrucción)', conceptos: [], dibujo: [], por: 'un solo ícono de la letra, el de la instrucción, en el violeta del agente, y una sola ventana: a quién (su hilo, uno nuevo, otro, un agente), la skill y lo pedido, con el contexto de donde se pidió', antes: 'cinco maneras con su palabra: «con Claude», «empezar ahora», «Acción…», «encargar» y «escribirle a Secretaría»' },
    { uso: 'una sección dentro de una pantalla (el foco, la agenda del plan)', conceptos: ['arriba'], dibujo: [], por: 'empieza otra parte: una línea arriba, de borde a borde, y su cabecera en su tinta, con la cuenta tenue', antes: 'una raya de color y la cuenta en un fondo lleno' },
    { uso: 'la fila donde estás', conceptos: ['seleccion'], dibujo: [], por: 'aquí estás: el matiz del acento', antes: 'gris, como un fondo de nivel' },
    { uso: 'un buscador', conceptos: ['abajo'], dibujo: [], por: 'aquí se escribe', antes: 'cinco, cada uno a su manera', explorar: true },
    { uso: 'una corrida de un proceso periódico, en su hora', conceptos: ['en-linea', 'chico', 'lleno', 'aro', 'tenue'], dibujo: ['bien', 'proxima'].map(e => de(S.corrida(e))), por: 'un momento sobre la línea de su proceso: lo que ya corrió, lleno y tenue (hecho, ya pasó); lo que viene, un aro (por hacer)', antes: 'una lista con «en 2 h · hace 3 h»' },
    { uso: 'una corrida que falló, o que le tocaba y no corrió', conceptos: ['aro', 'de-alerta'], dibujo: ['fallo', 'falto'].map(e => de(S.corrida(e))), por: 'falta, en rojo si falló; en el color de cuidado si no hay rastro de ella', antes: 'una cruz roja, solo de la última' },
    { uso: 'una corrida que llega a la casilla de un agente junto con otra', conceptos: ['aro', 'de-alerta'], dibujo: [de(S.corrida('proxima', true))], por: 'por hacer, con cuidado: si el agente sigue con la anterior, espera su turno', antes: 'nada: no se veía' },
    { uso: 'una hora del horario de la que no hay registro', conceptos: ['punto', 'apagado'], dibujo: [de(S.corrida('sin-registro'))], por: 'solo está: estaba en el horario; de cómo salió no se sabe', antes: 'nada' },
    { uso: 'un aviso del sistema, donde su franja no se ve (el teléfono viendo un hilo, foco)', conceptos: ['punto', 'de-alerta'], dibujo: [de(S.avisoSistema('conexion')), de(S.avisoSistema('falla')), de(S.avisoSistema('aviso'))], por: 'está, en el color de lo más grave: sin conexión o un problema rojo, una falla el de cuidado, un aviso el acento; junto al botón que muestra la franja', antes: 'nada: sin la barra a la vista, no se sabía' },
    { uso: 'lo que usa lo que deja otro proceso', conceptos: ['en-linea'], dibujo: [], por: 'un recorrido: líneas de un píxel en ángulo recto, desde la corrida de la que sale hasta la que la usa (al elegir el proceso)', antes: 'nada: no se declaraba' },
    { uso: 'un proceso periódico (su última corrida)', conceptos: ['lleno', 'aro', 'tenue', 'de-alerta'], dibujo: [de(S.periodico({ activo: true, ultima: { inicio: 'x' } })), de(S.periodico({ activo: false, ultima: {} })), de(S.periodico({ activo: true, ultima: { inicio: 'x', codigo: 1 } }))], por: 'salió bien, lleno y tenue (ya pasó); pausado, un aro tenue; falló, un aro rojo; corriendo, lleno como trabajando', antes: 'íconos de la letra: pausa, cruz, círculos' },
];
