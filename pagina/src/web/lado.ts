// La barra de la derecha (#lado), al ver el hilo de un agente residente: quién es (para, modelo, si es residente,
// dónde vive), cuánto pesa su conversación contra el tope de rotación, su último relevo y su CLAUDE.md, para leer.
// Se pliega con ›/‹ (y queda plegada o abierta para la próxima vez); con otro hilo, o en el celular, no está.

import * as cli from '../cli';
import { esc, fechaCorta } from '../estilo';
import * as ui from './ui';

const CLAVE_PLEGADO = 'telar.lado.plegado';
/** cada cuánto se relee la ficha mientras se ve el mismo hilo */
const CADA = 30 * 1000;

let actual = '';
let ficha: cli.JsonFichaAgente | undefined;
let leida = 0;

const lado = () => document.getElementById('lado') as HTMLElement | null;

function plegado(): boolean {
    try { return localStorage.getItem(CLAVE_PLEGADO) === '1'; } catch { return false; }
}

function plegar(si: boolean): void {
    try { localStorage.setItem(CLAVE_PLEGADO, si ? '1' : '0'); } catch { /* sin almacenamiento: solo esta vez */ }
    pintar();
}

const mb = (b: number) => `${(b / (1024 * 1024)).toFixed(b < 10 * 1024 * 1024 ? 1 : 0).replace('.', ',')} MB`;

function pintar(): void {
    const el = lado();
    if (!el) return;
    if (!ficha) { el.hidden = true; return; }
    el.hidden = false;
    const p = plegado();
    el.classList.toggle('plegado', p);
    const a = ficha.agente;
    if (p) {
        el.innerHTML = `<a class="lado-pliegue" data-lado="abrir" title="mostrar la ficha de ${esc(a.nombre)}">‹</a>`
            + `<div class="lado-vertical" data-lado="abrir">${esc(a.nombre)}</div>`;
        return;
    }
    const h: string[] = [`<div class="lado-cab"><b>${esc(a.nombre)}</b><span class="dim"> · agente:${esc(a.clave)}</span>`
        + '<a class="lado-pliegue" data-lado="plegar" title="plegar la ficha">›</a></div>'];
    if (a.para) h.push(`<p class="lado-para">${esc(a.para)}</p>`);
    const datos: [string, string][] = [
        ['residente', a.residente ? 'sí: se abre cuando le llega algo' : 'no: lo que le llega espera en su casilla'],
        ...(a.modelo ? [['modelo', a.modelo] as [string, string]] : []),
        ['vive en', a.en || 'esta máquina'],
        ['carpeta', a.carpeta],
        ...(a.hilos.length > 1 ? [['sus hilos', a.hilos.join(', ')] as [string, string]] : []),
    ];
    h.push('<dl class="lado-datos">' + datos.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('') + '</dl>');
    const c = ficha.conversacion;
    if (c && c.peso) {
        const pct = c.tope ? Math.min(100, Math.round((c.peso / c.tope) * 100)) : 0;
        h.push(`<div class="lado-peso" title="la conversación ${esc(c.id.slice(0, 8))}: al pasar el tope, rota con relevo">`
            + `<span>conversación ${esc(mb(c.peso))}${c.tope ? ` de ${esc(mb(c.tope))}` : ' (sin tope de rotación)'}</span>`
            + (c.tope ? `<span class="barra-peso"><span style="width:${pct}%"${pct >= 90 ? ' class="lleno"' : ''}></span></span>` : '')
            + '</div>');
    }
    if (ficha.rotacion) {
        const fase: Record<string, string> = { relevo: 'escribiendo su relevo', limpiar: 'relevo listo: por empezar otra conversación', retomar: 'conversación nueva, por leer su relevo' };
        h.push(`<div class="lado-rota">↻ rotando: ${esc(fase[ficha.rotacion] ?? ficha.rotacion)}</div>`);
    }
    if (!ficha.aqui) h.push('<div class="dim">vive en otra máquina: su relevo y el peso de su conversación están allá</div>');
    for (const x of a.problemas) h.push(`<div class="falla">${esc(x)}</div>`);
    if (ficha.relevo) {
        h.push(`<details class="lado-sec" open><summary>último relevo <span class="dim">${esc(fechaCorta(ficha.relevo.cuando))}</span></summary>`
            + `<div class="md-pag">${ui.markdown(ficha.relevo.texto)}</div></details>`);
    }
    h.push(`<details class="lado-sec" open><summary>CLAUDE.md</summary><div class="md-pag">${ficha.claude_md ? ui.markdown(ficha.claude_md) : '<p class="dim">vacío</p>'}</div></details>`);
    if (ficha.definicion_texto) {
        h.push(`<details class="lado-sec"><summary>agente.toml</summary><pre>${esc(ficha.definicion_texto)}</pre></details>`);
    }
    el.innerHTML = h.join('');
}

/** Lo que se ve cambió: `que` es la clave de la página («Faro», «rem:telar:Gestión», «dashboard», «doc:…»). La
 *  barra aparece si es el hilo de un agente, y se va si no. */
export async function mostrar(que: string, esHilo: boolean): Promise<void> {
    if (!esHilo) { actual = ''; ficha = undefined; pintar(); return; }
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const i = remoto.indexOf(':');
    const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
    if (que === actual && Date.now() - leida < CADA) { pintar(); return; }
    if (que !== actual) { ficha = undefined; pintar(); }
    actual = que;
    const r = await cli.fichaAgente(hilo, maquina);
    if (actual !== que) return;  // ya se fue a otro
    leida = Date.now();
    ficha = r.datos ?? undefined;
    pintar();
}

/** Los clics de la barra (plegar, abrir). Una vez, al arrancar. */
export function montar(): void {
    lado()?.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-lado]');
        if (a) plegar(a.dataset.lado === 'plegar');
    });
    // mientras se ve el mismo hilo, la ficha se mantiene al día (el peso de la conversación, la rotación)
    setInterval(() => { if (actual && !document.hidden) void mostrar(actual, true); }, CADA);
}
