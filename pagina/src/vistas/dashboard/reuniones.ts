// Preparar una reunión desde el dashboard («ahora», el calendario): un hilo con el agente de su proyecto. Si no se
// sabe de qué proyecto es, se pregunta, y la elección se recuerda para la serie (`telar reunion`).

import * as ui from '../../web/ui';
import type { Opcion } from '../../web/ui';
import * as cli from '../../cli';
import { modelo } from '../../modelo';
import { esServicio } from './proyectos';

/** Un hilo con el agente preparando la reunión, y el teclado ahí. Lo que se le dice
 *  al agente lo decide `[agente] reunion` en la configuración de telar, no la página. */
export async function prepararReunion(titulo: string, hora: string, enlace: string, evento = '', asistentes: string[] = []): Promise<void> {
    const pedir = (opciones: { proyecto?: string; preguntar?: boolean }) => ui.progreso({ titulo: `telar: ${titulo}…` },
        () => cli.reunion(titulo, hora, enlace, evento, { asistentes, ...opciones }));
    let r = await pedir({ preguntar: true });
    if (r.datos?.hecho === 'preguntar') {
        const eleccion = await elegirProyecto(titulo, hora, r.datos);
        if (!eleccion) return;
        r = await pedir({ proyecto: eleccion });
    }
    if (!r.datos) {
        void ui.aviso(`telar: ${r.error ?? 'no pude abrir la reunión'}`);
        return;
    }
    void ui.estado(`telar: «${titulo}» → ${r.datos.hilo}: ${r.datos.hecho}`, 6000);
    await modelo.sondear();
    await ui.mostrarTerminal();
}

/** De qué proyecto es una reunión que no se pudo deducir: los sugeridos con su porqué, Gestión
 *  siempre, un proyecto nuevo con su nombre, y todos los proyectos para buscar. La elección se
 *  recuerda para la serie (`telar reunion --proyecto`). */
async function elegirProyecto(titulo: string, hora: string, r: cli.JsonReunion): Promise<string | undefined> {
    type Item = Opcion & { valor?: string };
    const sep = (label: string): Item => ({ label, separador: true });
    const items: Item[] = [];
    const sugeridos = r.candidatos ?? [];
    if (sugeridos.length) {
        items.push(sep('sugeridos'));
        for (const c of sugeridos) items.push({ label: c.nombre, description: c.ruta, detail: c.motivos.join(' · '), valor: c.ruta });
    }
    items.push(sep('otros destinos'));
    items.push({ label: r.gestion || 'Gestión', description: 'el agente de lo que no tiene proyecto', valor: 'gestion' });
    items.push({ label: 'Proyecto nuevo…', description: 'se le pide al agente crearlo con su nombre', valor: 'nuevo' });
    const todos = await cli.proyectos();
    if (todos.datos) {
        items.push(sep('todos los proyectos'));
        const vistos = new Set(sugeridos.map(c => c.ruta));
        const lista = [...todos.datos.proyectos].filter(x => !vistos.has(x.ruta) && !esServicio(x))
            .sort((a, b) => (b.modificado ?? '').localeCompare(a.modificado ?? ''));
        for (const x of lista) items.push({ label: x.nombre, description: `${x.ruta} · ${x.arquetipo}`, valor: x.ruta });
    }
    const elegido = await ui.elegir(items, {
        titulo: `¿De qué proyecto es «${titulo}» (${hora})?`,
        placeholder: 'escribe para buscar un proyecto; la elección se recuerda para esta reunión',
    });
    if (!elegido?.valor) return undefined;
    if (elegido.valor !== 'nuevo') return elegido.valor;
    const nombre = await ui.campo({ titulo: 'Proyecto nuevo', ayuda: 'El nombre del proyecto' });
    return nombre?.trim() ? `nuevo:${nombre.trim()}` : undefined;
}
