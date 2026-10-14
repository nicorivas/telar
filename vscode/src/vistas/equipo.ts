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
            label: `${y.persona} · ${y.titulo}`, description: y.tipo === 'tarea' ? 'te pide una tarea' : `sugiere subir ${y.tarea}`, id: y.id })),
            { title: 'Lo que pide el equipo', placeHolder: 'elige una' });
        x = lista.find(y => y.id === e?.id);
    }
    if (!x) return;
    const pedido = x.tipo === 'tarea';
    type Item = vscode.QuickPickItem & { accion?: () => Promise<void> };
    const items: Item[] = [];
    if (x.motivo) items.push({ label: x.motivo.replace(/\s+/g, ' ').slice(0, 300), kind: vscode.QuickPickItemKind.Separator });
    const revisando = x.revisando ? ` · ${x.revisando.quien} la revisa desde ${fecha(x.revisando.desde)}` : '';
    items.push({
        label: `$(comment-discussion) Preguntarle a Gestión${pedido ? ': ¿ya existe? que lo procese y decida' : ''}`,
        description: x.revisando ? `ya se le encargó${revisando}` : 'revisa si existe, y decide si es nueva, actualiza una existente o no corresponde',
        accion: () => preguntarAGestion(x!) });
    if (pedido) {
        items.push({ label: '$(add) Agregar como tarea', description: 'P2, etiquetada equipo' + (x.vence ? `, para el ${x.vence}` : ''), accion: () => decidir(x!, 'aceptar') });
        for (const t of x.similares ?? []) {
            items.push({ label: `$(link) Es ${t.id}: contestarle su estado`, description: `${t.titulo.slice(0, 70)} · ${t.estado}${t.compartida ? '' : ' · no compartida'}`,
                accion: () => decidir(x!, 'existe', t.id) });
        }
        items.push({ label: '$(trash) Descartar…', description: 'no se agrega nada; puedes dejarle una nota', accion: () => decidir(x!, 'rechazar') });
    } else {
        const nueva = x.prioridad === null ? '' : ` (P${x.prioridad} → P${Math.max(0, x.prioridad - 1)})`;
        items.push({ label: `$(arrow-up) Subir la prioridad de ${x.tarea}${nueva}`, accion: () => decidir(x!, 'aceptar') });
        items.push({ label: '$(close) Rechazar…', description: 'puedes dejarle una nota', accion: () => decidir(x!, 'rechazar') });
    }
    const elegido = await vscode.window.showQuickPick(items, {
        title: pedido ? `${x.persona} te pide: ${x.titulo}${x.vence ? ` (para el ${x.vence})` : ''}` : `${x.persona} sugiere subir ${x.tarea} · ${x.titulo}`,
        placeHolder: fecha(x.cuando) + revisando, ignoreFocusOut: true });
    await elegido?.accion?.();
}
