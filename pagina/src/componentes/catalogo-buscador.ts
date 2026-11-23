// El buscador en el catálogo (/componentes#buscador): sus estados (catalogo.ts los pone en la grilla de temas), las cuatro
// maneras de dibujar el campo dentro de su barra que se probaron (#buscador/bordes), sus partes y dónde se usa: cada buscador
// de la página, cómo era antes del 18-nov-2026 y cómo es ahora. Aquí no se escribe: lo escrito y el foco van puestos.

import { esc } from '../estilo';
import { I } from '../web/iconos';
import { BORDES, barraBuscar, buscador } from './buscador';
import { item } from './item';
import { orden } from './orden';
import { nuevo } from './acciones';
import { atencion, prioridad, remoto } from './senales';

const AYUDA = 'buscar por nombre, carpeta o máquina · ⏎ abre el primero · ⎋ borra';

/** Lo que va a la derecha en HILOS: el grupo de ordenar y ver las máquinas. */
function herramientasHilos(): string {
    return orden({ grupo: 'muestra', activa: 'nombre', opciones: [
        { clave: 'urgencia', icono: I.urgencia, ayuda: 'urgencia' }, { clave: 'nombre', icono: I.alfabetico, ayuda: 'nombre' },
        { clave: 'reciente', icono: I.reloj, ayuda: 'reciente' }] })
        + `<span class="ord i" title="ver en qué máquina vive cada hilo">${I.maquinas}</span>`;
}

/** Sus estados, de a uno por fila (cada uno en cada tema). */
export function filasEstados(): { nombre: string; nota: string; html: string }[] {
    const p = { placeholder: 'hilos', ayuda: AYUDA };
    return [
        { nombre: 'vacío', nota: 'solo la lupa, tenue: en qué se busca va al pasar el mouse; la línea de la barra, la de siempre', html: barraBuscar(p) },
        { nombre: 'con su tecla', nota: 'la que lo enfoca, al final y tenue, mientras está vacío y sin el foco', html: barraBuscar({ ...p, atajo: '/' }) },
        { nombre: 'con el foco', nota: 'la lupa y la línea de la barra, en el acento; la tecla se va', html: barraBuscar({ ...p, atajo: '/', enfocado: true }) },
        { nombre: 'escribiendo', nota: 'lo escrito en el color del texto; al final, lo que el filtro dejó y el ✕ que lo borra',
            html: barraBuscar({ ...p, atajo: '/', enfocado: true, valor: 'far', cuenta: { texto: '2 de 14' } }) },
        { nombre: 'con el filtro puesto', nota: 'sin el foco y con algo escrito: la lupa sigue en el acento (la lista está filtrada) y el ✕ a mano; la línea vuelve a la de siempre',
            html: barraBuscar({ ...p, atajo: '/', valor: 'far', cuenta: { texto: '2 de 14' } }) },
        { nombre: 'con herramientas', nota: 'lo que acompaña la búsqueda va a la derecha, en la misma barra y en sus celdas: en HILOS, el orden y las máquinas',
            html: barraBuscar({ ...p, herramientas: herramientasHilos() }) },
        { nombre: 'filtrando, con herramientas', nota: 'el ✕ en su celda, antes del corte del orden',
            html: barraBuscar({ ...p, valor: 'far', herramientas: herramientasHilos() }) },
        { nombre: 'sin barra', nota: 'el campo solo (buscador()), dentro de otra cosa: sin línea; el foco, en la lupa', html: `<div style="display:flex">${buscador(p)}</div>` },
    ];
}

/** Un trozo de la barra de hilos, para ver el buscador donde va: la cabecera de HILOS, su barra y tres hilos. */
function enHilos(barra: string): string {
    const hilo = (titulo: string, inicio: Parameters<typeof item>[0]['inicio'], meta: string) =>
        item({ inicio, titulo, meta: { texto: meta }, datos: { grupo: 'muestra' } });
    return item({ variante: 'cabecera', inicio: [{ icono: I.abierto }], titulo: 'hilos', sufijo: [{ texto: '13', tono: 'tenue' }],
        fijas: [nuevo({ accion: 'nuevo' }, 'hilo nuevo')] })
        + barra
        + hilo('faro', [prioridad(1), atencion('trabajando'), null], '3m')
        + hilo('molino', [prioridad(2), atencion('espera'), null], '1h')
        + hilo('cosecha', [prioridad(0), null, remoto('vive en servidor')], '1d');
}

/** Las filas de «bordes»: un estado por fila; cada celda, una manera (la clase `borde-…` va en la celda, catalogo.css). */
export function filasBordes(): { nombre: string; nota: string; html: string }[] {
    const p = { placeholder: 'hilos', ayuda: AYUDA, herramientas: herramientasHilos() };
    return [
        { nombre: 'en reposo', nota: 'vacío y sin el foco', html: enHilos(barraBuscar(p)) },
        { nombre: 'con el foco', nota: 'escribiendo', html: enHilos(barraBuscar({ ...p, enfocado: true, valor: 'far' })) },
        { nombre: 'con el filtro puesto', nota: 'algo escrito, sin el foco', html: enHilos(barraBuscar({ ...p, valor: 'far' })) },
    ];
}

/** El texto de arriba de «bordes»: qué se probó y por qué la elegida. */
export function notaBordes(): string {
    const elegida = BORDES.find(b => b.elegida)!;
    return '<p class="dim">Con la barra, el buscador ya tiene una línea abajo, de borde a borde, que lo aparta de la lista. El campo '
        + 'no necesita otra. Se probaron cuatro maneras de dibujarlo dentro de la barra, una al lado de otra, en la barra de hilos '
        + 'de verdad (la cabecera de HILOS, su barra y tres hilos):</p><ul class="dim">'
        + BORDES.map(b => `<li><b>${esc(b.nombre)}</b>${b.elegida ? ' (la elegida)' : ''}: ${esc(b.nota)}.</li>`).join('')
        + `</ul><p class="dim"><b>Se eligió «${esc(elegida.nombre)}»</b>: en reposo es lo más callado (solo la lupa, sin `
        + 'cajas ni dos líneas); con el foco, la única línea que hay toma el acento entera, de borde a borde, como las demás líneas de '
        + 'la página; y con el filtro puesto lo dicen la lupa en el acento y el ✕, solo con color. «Su línea» deja dos rayas paralelas '
        + 'y una corta que no llega a los bordes; «otro fondo» hace del campo una caja (lo único con marco es lo que se abre aparte); '
        + '«solo la lupa» casi no se nota al escribir. Es la de <code>buscador.css</code>; las otras viven solo aquí '
        + '(<code>catalogo.css</code>, <code>.borde-…</code>).</p>';
}

/** Sus partes: qué dice cada una, la prop que la pone y su token. */
export const PARTES: { parte: string; dice: string; prop: string; token: string }[] = [
    { parte: 'la lupa', dice: '«aquí se busca»; en el acento, con el foco o con algo escrito', prop: '(siempre)', token: '--buscador-lupa, --buscador-activo' },
    { parte: 'en qué se busca', dice: 'sin el verbo: «hilos», «tareas», «lo que te espera»; no se dibuja: va en el aria-label y al comienzo de la ayuda al pasar', prop: 'placeholder', token: '' },
    { parte: 'el hueco', dice: 'entre la lupa y el primer carácter: un carácter, igual en todos', prop: '(siempre)', token: '--buscador-lupa-hueco' },
    { parte: 'lo escrito', dice: 'el filtro', prop: 'valor', token: '--buscador-texto' },
    { parte: 'la cuenta', dice: 'lo que el filtro dejó («4 de 30»); la vista la llena', prop: 'cuenta', token: '--buscador-cuenta' },
    { parte: 'la tecla', dice: 'la que lo enfoca («/»), mientras está vacío y sin el foco', prop: 'atajo', token: '--buscador-ayuda' },
    { parte: 'el ✕', dice: 'borra lo escrito (como ⎋); solo con algo escrito', prop: '(siempre)', token: '--buscador-borrar, --buscador-borrar-hover' },
    { parte: 'la ayuda al pasar', dice: 'en qué se busca, y por qué campos y qué hacen ⏎ y ⎋', prop: 'ayuda', token: '' },
    { parte: 'la barra', dice: 'que es una fila propia: del alto de las barras, con el aire de una pantalla', prop: 'barraBuscar()', token: '--pantalla-barra-alto, --buscador-margen, --buscador-barra-fondo' },
    { parte: 'su línea', dice: 'la aparta de la lista, de borde a borde; en el acento mientras se escribe', prop: 'barraBuscar()', token: '--buscador-linea, --buscador-linea-foco' },
    { parte: 'las herramientas', dice: 'lo que acompaña la búsqueda (el orden, un botón), a la derecha y en sus celdas', prop: 'herramientas', token: '' },
];

/** Dónde se usa: cada buscador de la página, cómo era antes y cómo es ahora. */
export const DONDE: { lugar: string; archivo: string; antes: string; ahora: string }[] = [
    { lugar: 'barra de hilos: HILOS (también busca en ARCHIVO)', archivo: 'vistas/hilos.ts → componentes/seccion.ts',
        antes: '«buscar», sin lupa; su línea corta bajo el campo (acento con el foco), en una banda del alto de una fila sin línea propia',
        ahora: 'barra con su línea; «hilos», uno solo para los vivos y los archivados; el orden y las máquinas, a la derecha' },
    { lugar: 'dashboard · tareas', archivo: 'vistas/dashboard/tareas.ts', antes: '«/ buscar», sin lupa; línea bajo campo y cuenta; el orden pegado al campo',
        ahora: 'barra; «tareas», la tecla / y la cuenta al final; el orden a la derecha' },
    { lugar: 'dashboard · te esperan', archivo: 'vistas/dashboard/esperas.ts', antes: '«buscar en las 23», sin lupa; línea bajo campo y cuenta',
        ahora: 'barra; «lo que te espera», con su cuenta' },
    { lugar: 'dashboard · proyectos (e iniciativas)', archivo: 'vistas/dashboard/proyectos.ts', antes: '«/ buscar en los 139», sin lupa; línea bajo el campo; la cuenta y los botones aparte',
        ahora: 'barra; «proyectos e iniciativas» (o «iniciativas»), la cuenta en el campo; «cerrados» y ↔ a la derecha' },
    { lugar: 'dashboard · la bandeja (correo)', archivo: 'vistas/dashboard/bloques.ts', antes: '«/ buscar», sin lupa; línea bajo campo y cuenta, hasta 60 letras',
        ahora: 'barra; el nombre de la pestaña, la tecla / y la cuenta' },
    { lugar: 'todo', archivo: 'componentes/todo.ts', antes: '«/ buscar en todo: tareas, …», sin lupa; línea bajo campo y cuenta, con aire propio',
        ahora: 'barra; «todo: tareas, casillas, …» (o la fuente abierta), con su cuenta ya puesta' },
    { lugar: '⚙ módulos', archivo: 'vistas/dashboard/config/modulos.ts', antes: '«buscar por nombre, descripción o etiqueta», sin lupa; su línea, a todo el ancho de la fila',
        ahora: 'barra; «módulos para instalar»' },
    { lugar: '⚙ periódicos: la skill', archivo: 'vistas/dashboard/config/periodicos.ts', antes: '«buscar una skill…», sin lupa; una caja con borde entero, que se pone amarilla con el foco',
        ahora: 'barra sobre la lista de skills; «skills»' },
    { lugar: '⌘K', archivo: 'web/buscador.ts', antes: '«buscar: hilos, agentes, …», sin lupa; una franja con su línea abajo, sin cambio con el foco',
        ahora: 'barra; «hilos, agentes, el dashboard, …»' },
    { lugar: 'elegir (los menús con filtro)', archivo: 'web/interfaz.ts', antes: 'lo que pidiera quien lo abre, o «buscar»; su línea siempre azul',
        ahora: 'barra de borde a borde de la caja; en qué se elige, o «opciones»' },
    { lugar: 'el menú ⋯ (clic derecho)', archivo: 'web/interfaz.ts', antes: '«filtrar», sin lupa; su línea corta', ahora: 'barra; «acciones»' },
    { lugar: 'la instrucción: a quién y la skill', archivo: 'web/instruccion.ts', antes: '«buscar un hilo o un agente», «buscar una skill»; su línea',
        ahora: 'barra sobre cada lista; «hilos y agentes», «skills»' },
    { lugar: 'la ventana paleta', archivo: 'componentes/ventana.ts', antes: 'el campo con su línea, con margen', ahora: 'barra de borde a borde' },
    { lugar: 'el lado de un hilo: códigos', archivo: 'web/codigos.ts', antes: 'la única con lupa: «código o texto», de tipo search (con la ✕ del navegador)',
        ahora: 'barra de borde a borde del lado; «códigos o texto»' },
    { lugar: 'compartir (el teléfono)', archivo: 'web/compartir.ts', antes: '«filtrar destinos», sin lupa; una caja con borde entero', ahora: 'barra; «destinos» (la letra, de 16 px como la nota: el iPhone)' },
    { lugar: 'las pestañas de los módulos (whatsapp…)', archivo: 'sus repositorios (plantilla.html)', antes: 'cada una la suya: whatsapp, la lupa y «buscar en todos los mensajes ⏎», «chat…»',
        ahora: 'sin cambio: viven fuera de la página (en sus repositorios); el lienzo recibe los tokens, no las clases' },
];
