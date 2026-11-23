// Las acciones que se repiten en las vistas, armadas una vez. En la gramática visual (componentes/gramatica.ts) una
// acción es un ícono de la letra, nunca un círculo (los círculos dicen un estado) y sin la palabra: lo que hace lo dice
// su ayuda. Aquí está el de cada una y dónde va.

import { I } from '../web/iconos';
import type { Accion } from './item';

/** Crear uno nuevo en una sección: el «+», sin la palabra «nuevo»; la ayuda dice qué crea («hilo nuevo: …»). Va en
 *  la cabecera de su sección, como su última acción: en el borde derecho y en la misma columna en todas las
 *  cabeceras (vistas/hilos.ts, `cabecera`). El ‹ que pliega la barra entera no va aquí: es de la barra, y va en su
 *  franja de avisos (componentes/franja.ts). */
export const nuevo = (orden: Pick<Accion, 'accion' | 'id'>, ayuda: string): Accion => ({ ...orden, icono: I.nuevo, ayuda });
