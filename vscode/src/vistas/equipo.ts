// Lo que el equipo deja en tu bandeja (`telar equipo`): una sección de la barra lateral, y un menú por entrada.
// Aquí no hay pantalla propia: pinchar una fila abre una lista de acciones sobre ella.

import * as vscode from 'vscode';
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

async function preguntarAGestion(x: Sugerencia): Promise<void> {
    const r = await cli.encargar('gestion', encargoParaGestion(x));
    if (!r.datos) { void vscode.window.showErrorMessage(`telar: no pude encargárselo a Gestión: ${r.error ?? 'sin respuesta'}`); return; }
    await cli.equipoRevisando(modelo.equipoRemoto, x.id);
    void vscode.window.setStatusBarMessage('telar: Gestión está revisando el pedido', 5000);
    await modelo.leerEquipo();
}

async function decidir(x: Sugerencia, verbo: 'aceptar' | 'rechazar' | 'existe', tarea = ''): Promise<void> {
    let nota = '';
    if (verbo !== 'aceptar') {
        const dicha = await vscode.window.showInputBox({
            prompt: verbo === 'existe' ? `Qué le agregas al estado de ${tarea} (opcional)` : `Qué verá ${x.persona} (opcional)`,
            placeHolder: verbo === 'existe' ? 'va para el jueves' : 'ahora no, porque…', ignoreFocusOut: true });
        if (dicha === undefined) return;   // Escape: no se decide nada
        nota = dicha;
    }
    const r = await cli.equipoResolver(modelo.equipoRemoto, verbo, x.id, nota, tarea);
    if (!r.datos) void vscode.window.showErrorMessage(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`);
    else if (verbo === 'aceptar' && x.tipo === 'tarea') {
        void vscode.window.showInformationMessage(`telar: agregada${r.datos.sugerencia.tarea ? ` como ${r.datos.sugerencia.tarea}` : ''}`);
    }
    await modelo.leerEquipo();
}

/** El menú de una entrada: lo que se puede hacer con ella. Sin `id`, se elige primero cuál. */
export async function verEntrada(id?: string): Promise<void> {
    await modelo.leerEquipo();
    const lista = modelo.sugerencias;
    if (!lista.length) { void vscode.window.showInformationMessage('telar: el equipo no tiene nada esperando'); return; }
    let x = lista.find(y => y.id === id);
    if (!x && lista.length === 1) x = lista[0];
    if (!x) {
        const e = await vscode.window.showQuickPick(lista.map(y => ({
            label: `${y.persona}: ${y.titulo.slice(0, 80)}`, description: y.tipo === 'tarea' ? 'pide una tarea' : `subir ${y.tarea}`, id: y.id })),
            { title: 'Lo que pide el equipo', placeHolder: 'elige una entrada' });
        x = lista.find(y => y.id === e?.id);
    }
    if (!x) return;
    const pedido = x.tipo === 'tarea';
    // el detalle en un diálogo: se lee entero (un menú desplegable corta el texto y confunde un dato con una acción)
    const cuando = fecha(x.cuando);
    const parecidas = (x.similares ?? []).map(t =>
        `  · ${t.id} «${t.titulo.slice(0, 90)}» — ${t.estado}${t.prioridad === null ? '' : `, P${t.prioridad}`}${t.vence ? `, vence ${t.vence}` : ''}${t.compartida ? '' : ' (no compartida)'}`);
    const detalle = [
        pedido ? `«${x.titulo}»${x.vence ? `\nPara el ${x.vence}.` : ''}`
               : `Tarea ${x.tarea} «${x.titulo}»${x.prioridad === null ? '' : ` (hoy P${x.prioridad}; subiría a P${Math.max(0, x.prioridad - 1)})`}`,
        ...(x.motivo ? [`${pedido ? 'Contexto' : 'Motivo'}: ${x.motivo.replace(/\s+/g, ' ')}`] : []),
        ...(parecidas.length ? ['¿Ya existe?', ...parecidas] : []),
        ...(x.revisando ? [`${x.revisando.quien} la revisa desde ${fecha(x.revisando.desde)}.`] : []),
    ].join('\n\n');
    const GESTION = x.revisando ? 'Preguntarle de nuevo a Gestión' : 'Preguntarle a Gestión';
    const botones = pedido
        ? [GESTION, 'Agregar como tarea', ...(parecidas.length ? ['Ya existe…'] : []), 'Descartar…']
        : [GESTION, `Subir prioridad de ${x.tarea}`, 'Rechazar…'];
    const elegido = await vscode.window.showInformationMessage(
        `${x.persona} ${pedido ? 'te pide una tarea' : 'sugiere subir una prioridad'} · ${cuando}`,
        { modal: true, detail: detalle }, ...botones);
    if (!elegido) return;
    if (elegido === GESTION) await preguntarAGestion(x);
    else if (elegido === 'Agregar como tarea' || elegido.startsWith('Subir prioridad')) await decidir(x, 'aceptar');
    else if (elegido === 'Descartar…' || elegido === 'Rechazar…') await decidir(x, 'rechazar');
    else if (elegido === 'Ya existe…') {
        const t = await vscode.window.showQuickPick((x.similares ?? []).map(y => ({ label: y.id, description: `${y.titulo.slice(0, 80)} · ${y.estado}`, id: y.id })),
            { title: 'Contestarle el estado de cuál tarea', placeHolder: x.persona + ' recibirá su estado' });
        if (t) await decidir(x, 'existe', t.id);
    }
}
