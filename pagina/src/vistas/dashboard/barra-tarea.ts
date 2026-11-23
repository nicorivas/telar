// La barra de una tarea: lo que se le hace con un ícono, la misma en la ficha de la tarea (tareas.ts, `pintarFicha`) y en el
// encabezado de la ventana de Contestar cuando contesta una tarea (componentes/contestar.ts, web/contestar.ts):
//
//   · las acciones de su proveedor cuyo `rol` se conoce (ROL_ICONO): esperar a, prioridad, quién la hace, la fecha, el
//     tamaño, hecha y descartar, cada una con su ícono, el color de lo que hace (web/iconos.ts, C) y su globo;
//   · la estrella y compartir, junto al título: su ícono es el estado de ahora (★ con estrella, ◉ compartida);
//   · la instrucción (la arma quien la pone: en Contestar, «conversarlo» ya lo hace).
//
// Aquí se decide qué va y cómo se ve; correr cada una es de tareas.ts (`correrAccion`). Puro: lo prueban
// pruebas/contestar.mjs y pruebas/componentes.mjs en Node.

import type * as cli from '../../cli';
import { esc } from '../../estilo';
import { C, I, PRIO_I } from '../../web/iconos';

/** Las acciones del proveedor cuyo `rol` se conoce: un ícono con su globo, en vez de un botón con palabra (las que no
 *  tienen rol, o uno que no está aquí, siguen como botón). El color, por lo que hace: cambiarla, en el de cambiar; hecha,
 *  verde; descartar, rojo. Los mismos íconos que foco y que el ⋯ de una tarea. */
export const ROL_ICONO: Record<string, { icono: string; tono: string; ayuda: string }> = {
    espera: { icono: I.pausa, tono: C.cambiar, ayuda: 'esperar a otra persona: queda detenida hasta que responda' },
    prioridad: { icono: I.urgencia, tono: C.cambiar, ayuda: 'cambiar la prioridad' },
    dueno: { icono: I.persona, tono: C.cambiar, ayuda: 'cambiar quién la hace' },
    fecha: { icono: I.fecha, tono: C.cambiar, ayuda: 'cambiar la fecha' },
    tamano: { icono: I.tamano, tono: C.cambiar, ayuda: 'su tamaño: rápida, media hora o menos; larga, horas o días' },
    hecha: { icono: I.hecha, tono: C.hecho, ayuda: 'marcarla hecha' },
    descartar: { icono: I.descartar, tono: C.quitar, ayuda: 'descartarla: no se va a hacer' },
};

/** Las que van junto al título, como en la lista de tareas: la estrella y compartir. */
export const ICONOS = ['estrella', 'equipo'];

/** «escribirle a Claude» del proveedor (un mensaje a su hilo que pide qué decirle): es la instrucción, y la hace su
 *  ventana (web/instruccion.ts), con /tarea y lo que haya quedado escrito. */
export const esEscribir = (a: cli.JsonAccionPagina): boolean => !!(a.al_hilo && a.mensaje && a.pide);

/** Una acción de la barra: la `k` de la ficha, con su rol, su ícono, su color y su globo. */
export interface IconoDeTarea { k: number; rol: string; icono: string; tono: string; ayuda: string }

/** Las acciones de la barra, en el orden de la ficha: las de un rol conocido que no son la principal, menos las que van
 *  en otro lado (`fuera`: las del subtítulo de la ficha, lo que Contestar ya hace a su manera). El globo dice si pide
 *  confirmación. */
export function deBarra(acciones: readonly cli.JsonAccionPagina[], fuera: ReadonlySet<string> = new Set()): IconoDeTarea[] {
    return acciones.map((a, k) => ({ a, k })).filter(({ a }) => !a.principal && ROL_ICONO[a.rol ?? ''] && !fuera.has(a.rol ?? '') && !esEscribir(a))
        .map(({ a, k }) => {
            const r = ROL_ICONO[a.rol!];
            return { k, rol: a.rol!, icono: r.icono, tono: r.tono, ayuda: `${r.ayuda}${a.confirmar ? ' · pide confirmación' : ''}` };
        });
}

/** La estrella o compartir, junto al título: su ícono es el estado de ahora, que el proveedor pone al comienzo del nombre
 *  de la acción que lo cambia («★ quitar la estrella»); lo que sigue es lo que hace un clic. */
export interface IconoDeTitulo { k: number; rol: string; icono: string; on: boolean; ayuda: string }

export function deTitulo(acciones: readonly cli.JsonAccionPagina[]): IconoDeTitulo[] {
    return acciones.map((a, k) => ({ a, k })).filter(({ a }) => ICONOS.includes(a.rol ?? '')).map(({ a, k }) => {
        const [glifo, ...resto] = a.nombre.split(' ');
        // en la página, los íconos de la letra de íconos; el proveedor los dice con sus símbolos
        const icono = ({ '★': I.estrella, '☆': I.sinEstrella, '◉': I.compartir, '○': PRIO_I[3] } as Record<string, string>)[glifo] ?? glifo;
        return { k, rol: a.rol!, icono, on: glifo === '★' || glifo === '◉', ayuda: resto.join(' ') };
    });
}

/** Uno junto al título, en HTML; `datos`, los atributos con que lo atiende quien lo pone (`data-accion="accion-tarea"` en
 *  la ficha, `data-contestar="tarea"` en Contestar). */
export const iconoDeTitulo = (x: IconoDeTitulo, datos: string): string =>
    `<a class="icono-t ${esc(x.rol)}${x.on ? ' on' : ''}" ${datos} data-valor="${x.k}" title="${esc(x.ayuda)}">${esc(x.icono)}</a>`;
