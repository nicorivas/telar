// El modo lectura de un hilo: la respuesta del agente, para leerla con calma (letra con serifa, el markdown
// bien dibujado, un ancho de lectura). Una de las vistas de un hilo (web/vistas-hilo.ts): se dibuja en un
// elemento de la página; sus estilos, en media/css/lectura.css (con @scope, en `.v-lectura`).
//
// Lee la conversación de `/api/hilos/leer` (la misma de la vista conversación) y la dibuja con el renderizador
// de su fuente: cada asistente entrega su conversación a su manera, y cada forma tiene el suyo
// (RENDERIZADORES). Hoy: «conversacion» (turnos con lo que dijo cada uno, como la de Claude Code) y «panel»
// (solo el texto de su pantalla). Un asistente nuevo es un renderizador más.
//
// ← → recorren las respuestas; mientras se mira la última, lo que el agente va escribiendo aparece solo. ⎋ vuelve
// a la terminal.
import MarkdownIt from 'markdown-it';

import { atenderClics, enlazar } from './rutas-agente';
import { type Vista, teclaParaLaVista } from './vistas-hilo';

interface Mensaje { quien: string; texto?: string }
interface Lectura { fuente?: string; turnos?: Mensaje[][]; texto?: string; total_turnos?: number; recortado?: boolean; error?: string }

/** Cómo se dibuja la conversación de una fuente: cuántas respuestas hay, y el HTML de la `i`-ésima. */
interface Renderizador {
    cuantas(d: Lectura): number;
    dibujar(d: Lectura, i: number): string;
}

const md = new MarkdownIt({ html: false, linkify: true, typographer: true });
const esc = (t: string) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Los turnos que traen una respuesta del agente (los de solo herramientas no se leen). */
const conRespuesta = (d: Lectura) => (d.turnos ?? []).filter(t => t.some(m => m.quien === 'agente' && m.texto));

const RENDERIZADORES: Record<string, Renderizador> = {
    // turnos: lo que preguntó la persona, y la respuesta final del agente: lo que escribió después de su último
    // llamado a una herramienta. El proceso de antes (lo que fue diciendo entre herramientas, los diffs, los
    // llamados) no se lee aquí: para eso está la terminal
    conversacion: {
        cuantas: d => conRespuesta(d).length,
        dibujar(d, i) {
            const turno = conRespuesta(d)[i];
            const pregunta = turno.filter(m => m.quien === 'usuario').map(m => m.texto ?? '').join('\n\n').trim();
            const ultimaHerramienta = turno.map(m => m.quien).lastIndexOf('herramienta');
            let final = turno.slice(ultimaHerramienta + 1).filter(m => m.quien === 'agente' && m.texto);
            // si después de la última herramienta no escribió nada (todavía trabaja), lo último que dijo
            if (!final.length) final = turno.filter(m => m.quien === 'agente' && m.texto).slice(-1);
            const respuesta = final.map(m => md.render(m.texto ?? '')).join('\n');
            return (pregunta ? `<div class="pregunta">${esc(pregunta)}</div>` : '') + `<div class="respuesta">${respuesta}</div>`;
        },
    },
    // solo la pantalla del agente (uno que no deja su conversación): el texto tal cual, en una sola «respuesta»
    panel: {
        cuantas: d => (d.texto ? 1 : 0),
        dibujar: d => `<div class="respuesta"><pre>${esc(d.texto ?? '')}</pre></div>`,
    },
};

/** `raiz`: el elemento de la vista (el que se desplaza). `volver`: ⎋, a la terminal. */
export function montar(raiz: HTMLElement, rutas: { hilo: string; maquina?: string }, volver: () => void): Vista {
    raiz.classList.add('v-lectura');
    raiz.innerHTML = '<main class="lectura"><p class="nada">leyendo…</p></main>';
    const caja = raiz.querySelector<HTMLElement>('.lectura')!;
    let datos: Lectura = {};
    let indice = -1;          // la respuesta que se mira; -1: la última
    let firma = '';
    const url = `/api/hilos/leer?hilo=${encodeURIComponent(rutas.hilo)}&ultimos=20${rutas.maquina ? `&maquina=${encodeURIComponent(rutas.maquina)}` : ''}`;

    function pintar(): void {
        if (datos.error) { caja.innerHTML = `<p class="nada">${esc(datos.error)}</p>`; return; }
        const r = RENDERIZADORES[datos.fuente ?? 'conversacion'] ?? RENDERIZADORES.conversacion;
        const n = r.cuantas(datos);
        if (!n) { caja.innerHTML = '<p class="nada">todavía no hay una respuesta que leer</p>'; return; }
        const i = indice < 0 || indice >= n ? n - 1 : indice;
        const antes = datos.recortado || (datos.total_turnos ?? 0) > (datos.turnos ?? []).length ? 'hay respuestas anteriores que no se leen aquí · ' : '';
        caja.innerHTML = `<div class="pie-lectura"><span>${esc(rutas.hilo)} · respuesta ${i + 1} de ${n}${indice < 0 ? ' (la última)' : ''}</span>`
            + `<span>${antes}← → recorrer · ⎋ terminal</span></div>` + r.dibujar(datos, i);
        // las rutas que escribió el agente, como enlaces al visor
        enlazar(caja);
    }
    atenderClics(caja, { hilo: rutas.hilo, maquina: rutas.maquina ?? '' });

    async function leer(): Promise<void> {
        try {
            const r = await fetch(url, { cache: 'no-store' });
            const d = await r.json() as Lectura & { detail?: string };
            const nuevo: Lectura = r.ok ? d : { error: typeof d.detail === 'string' ? d.detail : `la API respondió ${r.status}` };
            const f = JSON.stringify(nuevo);
            if (f === firma) return;
            firma = f; datos = nuevo;
            // solo se redibuja si se mira la última (lo que va escribiendo el agente); si no, se lee tranquilo
            if (indice < 0 || !caja.dataset.leida) {
                const alFinal = raiz.scrollHeight - raiz.scrollTop - raiz.clientHeight < 40;
                pintar();
                if (alFinal && indice < 0 && caja.dataset.leida) raiz.scrollTop = raiz.scrollHeight;
                caja.dataset.leida = '1';
            }
        } catch { /* sin conexión: se reintenta en la vuelta */ }
    }

    const tecla = (e: KeyboardEvent) => {
        if (!teclaParaLaVista(e, raiz)) return;
        if (e.key === 'Escape') { e.preventDefault(); volver(); return; }
        const r = RENDERIZADORES[datos.fuente ?? 'conversacion'] ?? RENDERIZADORES.conversacion;
        const n = r.cuantas(datos);
        if (!n) return;
        const actual = indice < 0 ? n - 1 : indice;
        if (e.key === 'ArrowLeft' && actual > 0) { indice = actual - 1; pintar(); raiz.scrollTop = 0; }
        else if (e.key === 'ArrowRight' && actual < n - 1) { indice = actual + 1 === n - 1 ? -1 : actual + 1; pintar(); raiz.scrollTop = 0; }
    };
    window.addEventListener('keydown', tecla);

    // se relee cada 3 s mientras se mira; escondida (otra vista, otra pestaña), cada 20
    let espera = 0;
    const vuelta = () => { void leer(); espera = window.setTimeout(vuelta, document.hidden || raiz.hidden ? 20000 : 3000); };
    vuelta();
    return {
        mostrada: () => void leer(),
        cerrar: () => { clearTimeout(espera); window.removeEventListener('keydown', tecla); },
    };
}
