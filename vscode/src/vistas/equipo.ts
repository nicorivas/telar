// Lo que el equipo deja en tu bandeja (`telar equipo`): una sección de la barra lateral; pinchar una fila abre su
// página en el dashboard (`PanelHoy.abrirEquipo`). Aquí viven el encargo a Gestión y las decisiones.

import { type Opcion, ui } from '../anfitrion';
import * as cli from '../cli';
import { modelo } from '../modelo';

type Sugerencia = cli.JsonSugerencia;

const fecha = (iso: string) => iso.replace('T', ' ').slice(0, 16);

/** El texto que se le manda a Gestión para que revise un pedido y decida: nueva, ya existe, o actualizar una existente. */
export function encargoParaGestion(x: Sugerencia): string {
    const parecidas = (x.similares ?? []).map(t => `  · ${t.id} «${t.titulo}» (${t.estado}${t.prioridad === null ? '' : `, P${t.prioridad}`}${t.vence ? `, vence ${t.vence}` : ''}${t.compartida ? '' : ', no compartida'})`);
    return [
        `[del equipo, a pedido de Nico] ${x.persona} le pide a Nico una tarea. Entrada ${x.id} de la bandeja (\`telar equipo sugerencias\`):`,
        `  Pide: «${x.titulo}»${x.vence ? ` · para el ${x.vence}` : ''}`,
        ...(x.motivo ? [`  Contexto que dio: ${x.motivo}`] : []),
        ...(parecidas.length ? ['Tareas que el sistema ve parecidas:', ...parecidas] : []),
        '',
        'Encárgate de procesarla, con tu criterio:',
        '1. Revisa si ya existe algo: `todo search`, las tareas abiertas y las cerradas hace poco (no te quedes con las parecidas de arriba).',
        '2. Decide, y ejecuta lo que corresponda:',
        `   · es nueva → \`telar equipo aceptar ${x.id}\` (la agrega como tarea, P2, etiquetada equipo). Si conviene otra prioridad, cámbiala después con \`todo edit\`.`,
        `   · ya existe y el pedido aporta algo (fecha, contexto, urgencia) → actualiza esa tarea (\`todo nota\`, \`todo edit --due\`…) y cierra la entrada con \`telar equipo existe ${x.id} --tarea T123 --nota "…"\`.`,
        `   · ya existe y no hay nada que agregar → solo \`telar equipo existe ${x.id} --tarea T123 --nota "…"\`.`,
        `   · no corresponde (no es de Nico, no es accionable, es de otro hilo) → \`telar equipo rechazar ${x.id} --nota "motivo"\`.`,
        `3. La nota la lee ${x.persona}: escribe solo estado y lo que sirva para su pedido, sin detalles privados de Nico ni de otras personas.`,
        '4. Contéstame en una línea qué decidiste y por qué.',
    ].join('\n');
}

export async function preguntarAGestion(x: Sugerencia): Promise<void> {
    const r = await cli.encargar('gestion', encargoParaGestion(x));
    if (!r.datos) { void ui().falla(`telar: no pude encargárselo a Gestión: ${r.error ?? 'sin respuesta'}`); return; }
    await cli.equipoRevisando(modelo.equipoRemoto, x.id);
    void ui().estado('telar: Gestión está revisando el pedido', 5000);
    await modelo.leerEquipo();
}

export async function decidir(x: Sugerencia, verbo: 'aceptar' | 'rechazar' | 'existe', tarea = ''): Promise<void> {
    let nota = '';
    if (verbo !== 'aceptar') {
        const dicha = await ui().campo({
            prompt: verbo === 'existe' ? `Qué le agregas al estado de ${tarea} (opcional)` : `Qué verá ${x.persona} (opcional)`,
            placeHolder: verbo === 'existe' ? 'va para el jueves' : 'ahora no, porque…', ignoreFocusOut: true });
        if (dicha === undefined) return;   // Escape: no se decide nada
        nota = dicha;
    }
    const r = await cli.equipoResolver(modelo.equipoRemoto, verbo, x.id, nota, tarea);
    if (!r.datos) void ui().falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`);
    else if (verbo === 'aceptar' && x.tipo === 'tarea') {
        void ui().info(`telar: agregada${r.datos.sugerencia.tarea ? ` como ${r.datos.sugerencia.tarea}` : ''}`);
    }
    await modelo.leerEquipo();
}

/** Cuál entrada abrir: la que se pidió, la única que hay, o la que se elija de una lista corta. "" si no hay ninguna o no se eligió. */
export async function elegirEntrada(id?: string): Promise<string> {
    await modelo.leerEquipo();
    const lista = modelo.sugerencias;
    if (!lista.length) { void ui().info('telar: el equipo no tiene nada esperando'); return ''; }
    if (id && lista.some(y => y.id === id)) return id;
    if (lista.length === 1) return lista[0].id;
    const e = await ui().elegir(lista.map(y => ({
        label: `${y.persona}: ${y.titulo.slice(0, 80)}`, description: y.tipo === 'tarea' ? 'pide una tarea' : `subir ${y.tarea}`, id: y.id })),
        { title: 'Lo que pide el equipo', placeHolder: 'elige una entrada' });
    return e?.id ?? '';
}
