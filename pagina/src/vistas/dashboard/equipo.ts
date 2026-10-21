// Lo que el equipo deja en tu bandeja (`telar equipo`): una sección de la barra lateral; pinchar una fila abre su
// página en el dashboard (PantallaEquipo, abajo). Aquí viven también el encargo a Gestión y las decisiones.

import * as ui from '../../web/ui';
import * as cli from '../../cli';
import { esc, fechaCorta } from '../../estilo';
import { modelo } from '../../modelo';
import { atajo } from './dia';
import type { Pantalla, Tablero } from './pantalla';

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
    if (!r.datos) { void ui.falla(`telar: no pude encargárselo a Gestión: ${r.error ?? 'sin respuesta'}`); return; }
    await cli.equipoRevisando(modelo.equipoRemoto, x.id);
    void ui.estado('telar: Gestión está revisando el pedido', 5000);
    await modelo.leerEquipo();
}

export async function decidir(x: Sugerencia, verbo: 'aceptar' | 'rechazar' | 'existe', tarea = ''): Promise<void> {
    let nota = '';
    if (verbo !== 'aceptar') {
        const dicha = await ui.campo({
            ayuda: verbo === 'existe' ? `Qué le agregas al estado de ${tarea} (opcional)` : `Qué verá ${x.persona} (opcional)`,
            placeholder: verbo === 'existe' ? 'va para el jueves' : 'ahora no, porque…' });
        if (dicha === undefined) return;   // Escape: no se decide nada
        nota = dicha;
    }
    const r = await cli.equipoResolver(modelo.equipoRemoto, verbo, x.id, nota, tarea);
    if (!r.datos) void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`);
    else if (verbo === 'aceptar' && x.tipo === 'tarea') {
        void ui.info(`telar: agregada${r.datos.sugerencia.tarea ? ` como ${r.datos.sugerencia.tarea}` : ''}`);
    }
    await modelo.leerEquipo();
}

/** Cuál entrada abrir: la que se pidió, la única que hay, o la que se elija de una lista corta. "" si no hay ninguna o no se eligió. */
export async function elegirEntrada(id?: string): Promise<string> {
    await modelo.leerEquipo();
    const lista = modelo.sugerencias;
    if (!lista.length) { void ui.info('telar: el equipo no tiene nada esperando'); return ''; }
    if (id && lista.some(y => y.id === id)) return id;
    if (lista.length === 1) return lista[0].id;
    const e = await ui.elegir(lista.map(y => ({
        label: `${y.persona}: ${y.titulo.slice(0, 80)}`, description: y.tipo === 'tarea' ? 'pide una tarea' : `subir ${y.tarea}`, id: y.id })),
        { titulo: 'Lo que pide el equipo', placeholder: 'elige una entrada' });
    return e?.id ?? '';
}

/** La página de una entrada del equipo (un pedido de tarea, o una sugerencia de prioridad) en el dashboard, con lo
 *  que se puede hacer con ella. */
export class PantallaEquipo implements Pantalla {
    readonly pantallas = ['equipo'] as const;
    readonly conReloj = ['equipo'] as const;
    /** la entrada que se muestra */
    private id = '';
    readonly acciones = { 'equipo-accion': (v: string) => this.accion(v) };

    constructor(private readonly t: Tablero) {}

    /** La página de una entrada del equipo (un pedido de tarea, o una sugerencia de prioridad), con lo que se puede hacer con ella. */
    async abrir(id: string): Promise<void> {
        this.t.abrir();
        this.t.ir('equipo');
        this.id = id;
        this.pintar();
        await modelo.leerEquipo();
        if (this.t.pantalla === 'equipo') this.pintar();
    }

    pintar(): void {
        this.t.teclas.clear();
        const x = modelo.sugerencias.find(y => y.id === this.id);
        const volver = '<div class="fila"><a data-accion="dia">← volver al dashboard</a></div>';
        if (!x) {
            this.t.pintar(['<div class="subcab"><b>Equipo</b></div>', '<div class="fila dim">esa entrada ya se resolvió, o no está.</div>', volver]);
            return;
        }
        const pedido = x.tipo === 'tarea';
        const h: string[] = [`<div class="subcab"><b>${esc(x.persona)}</b> ${pedido ? 'te pide una tarea' : 'sugiere subir una prioridad'}`
            + `<span class="der dim">${esc(fechaCorta(x.cuando))}</span></div>`];
        if (pedido) {
            h.push(`<h2>«${esc(x.titulo)}»${x.vence ? `<small>para el ${esc(x.vence)}</small>` : ''}</h2>`);
        } else {
            const nueva = x.prioridad === null ? '' : ` · hoy P${x.prioridad}, subiría a P${Math.max(0, x.prioridad - 1)}`;
            h.push(`<h2>${esc(x.tarea)} · ${esc(x.titulo)}<small>${esc(nueva.replace(/^ · /, ''))}</small></h2>`);
        }
        if (x.motivo) h.push(`<div class="md-pag"><p style="white-space:pre-wrap">${esc(x.motivo)}</p></div>`);
        if (x.revisando) h.push(`<div class="fila dim">${esc(x.revisando.quien)} la revisa desde ${esc(fechaCorta(x.revisando.desde))}: te contesta en una línea cuando decida.</div>`);
        const parecidas = x.similares ?? [];
        if (parecidas.length) {
            h.push('<h2>¿ya existe?<small>tareas tuyas que parecen lo mismo</small></h2>');
            for (const t of parecidas) {
                h.push(`<div class="item-pag"><div class="fila"><b>${esc(t.id)}</b> ${esc(t.titulo)}</div>`
                    + `<div class="fila dim">${esc(t.estado)}${t.prioridad === null ? '' : ` · P${t.prioridad}`}${t.vence ? ` · vence ${esc(t.vence)}` : ''}`
                    + `${t.avance ? ` · ${esc(t.avance)}` : ''}${t.compartida ? '' : ' · no compartida'}</div>`
                    + `<div class="fila"><a data-accion="equipo-accion" data-valor="${esc(`existe|${x.id}|${t.id}`)}" title="no se agrega nada: ${esc(x.persona)} recibe el estado de esa tarea">es esta: contestarle su estado</a></div></div>`);
            }
        }
        const botones: [string, string, string, string][] = [
            ['1', x.revisando ? 'preguntarle de nuevo a Gestión' : 'preguntarle a Gestión', `gestion|${x.id}`, 'Gestión revisa si ya existe y decide: nueva, actualizar una existente o no corresponde'],
            ...(pedido ? [['2', 'agregar como tarea', `aceptar|${x.id}`, 'P2, etiquetada equipo' + (x.vence ? `, para el ${x.vence}` : '')] as [string, string, string, string]]
                : [['2', `subir la prioridad de ${x.tarea}`, `aceptar|${x.id}`, 'un nivel, con el CLI de tareas'] as [string, string, string, string]]),
            ['3', pedido ? 'descartar' : 'rechazar', `rechazar|${x.id}`, `puedes dejarle una nota a ${x.persona}`],
        ];
        h.push('<h2>qué hacer</h2><div class="acciones-t fila-botones">' + botones.map(([k, n, v, t]) => atajo(k, n, 'equipo-accion', v, t)).join('') + '</div>');
        for (const [k, , v] of botones) this.t.teclas.set(k, () => this.accion(v));
        h.push(volver);
        this.t.pintar(h);
    }

    private async accion(valor: string): Promise<void> {
        const [verbo, id, tarea = ''] = valor.split('|');
        const x = modelo.sugerencias.find(y => y.id === id);
        if (!x) return;
        if (verbo === 'gestion') await preguntarAGestion(x);
        else await decidir(x, verbo as 'aceptar' | 'rechazar' | 'existe', tarea);
        if (this.t.pantalla === 'equipo') this.pintar();
    }
}
