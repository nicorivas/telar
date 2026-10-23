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
/** la máquina del hilo que se ve ("" si es esta): a ella van encargar, rotar y cancelar */
let maquinaActual = '';
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
        ['residente', { siempre: 'siempre: el nodo lo mantiene abierto', 'a-pedido': 'a pedido: se abre cuando le llega algo',
            no: 'no: lo que le llega espera en su casilla' }[a.presencia ?? (a.residente ? 'a-pedido' : 'no')] ?? ''],
        ...(a.politica && Object.values(a.politica).some(v => v?.length)
            ? [['política', Object.entries(a.politica).filter(([, v]) => v?.length).map(([k, v]) => `${k}: ${v!.join(', ')}`).join(' · ')] as [string, string]] : []),
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
    h.push('<div class="lado-acciones"><a data-lado="encargar" title="un encargo: queda con su estado, y el resultado te llega">encargar</a>'
        + ' · <a data-lado="rotar" title="que escriba su relevo y empiece otra conversación">rotar con relevo</a></div>');
    const encargos = ficha.encargos ?? [];
    if (encargos.length) {
        const abiertos = encargos.filter(e => !['hecho', 'falló', 'cancelado'].includes(e.estado));
        h.push(`<details class="lado-sec"${abiertos.length ? ' open' : ''}><summary>encargos <span class="dim">${abiertos.length} abiertos</span></summary>`
            + encargos.map(e => {
                const dir = `encargo:${e.id}${maquinaActual ? `@${maquinaActual}` : ''}`;
                const abierto = abiertos.includes(e);
                return `<div class="${abierto ? '' : 'dim'}">${esc(e.estado)} · ${esc((e.texto ?? '').split(/\s+/).join(' ').slice(0, 80))}`
                    + (abierto ? ` · <a data-lado="cancelar" data-dir="${esc(dir)}">cancelar</a>` : '')
                    + (!abierto && e.resultado ? `<div class="dim">→ ${esc(e.resultado.slice(0, 120))}</div>` : '') + '</div>';
            }).join('') + '</details>');
    }
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
    maquinaActual = maquina;
    if (que === actual && Date.now() - leida < CADA) { pintar(); return; }
    if (que !== actual) { ficha = undefined; pintar(); }
    actual = que;
    const r = await cli.fichaAgente(hilo, maquina);
    if (actual !== que) return;  // ya se fue a otro
    leida = Date.now();
    ficha = r.datos ?? undefined;
    pintar();
}

async function encargar(): Promise<void> {
    if (!ficha) return;
    const a = ficha.agente;
    const escrito = await ui.escribir({ titulo: `encargarle a ${a.nombre}`, placeholder: '¿qué le encargas?',
        ayuda: `${a.para || 'un encargo'} · queda como encargo:e-…; el resultado te llega. ⌘⏎ envía.` });
    if (!escrito?.texto.trim()) return;
    const r = await cli.encargar(a.clave, escrito.texto);
    if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
    void ui.estado(`telar: encargado a ${a.nombre}`, 4000);
    leida = 0;
    await mostrar(actual, true);
}

async function rotar(): Promise<void> {
    if (!ficha) return;
    const a = ficha.agente;
    if (await ui.aviso(`¿Rotar la conversación de ${a.nombre} ahora? Escribe su relevo y la siguiente empieza leyéndolo.`, 'Rotar') !== 'Rotar') return;
    const r = await cli.rotarAgente(a.nombre, maquinaActual);
    if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
    void ui.estado(`telar: ${r.datos.hecho ?? 'pedido'}`, 5000);
    leida = 0;
    await mostrar(actual, true);
}

async function cancelar(direccion: string): Promise<void> {
    if (await ui.aviso(`¿Cancelar ${direccion}?`, 'Cancelar el encargo') !== 'Cancelar el encargo') return;
    const r = await cli.accionObjeto(direccion, 'cancelar', { motivo: 'lo canceló su persona desde la página' });
    if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
    leida = 0;
    await mostrar(actual, true);
}

/** Los clics de la barra (plegar, abrir, encargar, rotar, cancelar). Una vez, al arrancar. */
export function montar(): void {
    lado()?.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-lado]');
        if (!a) return;
        const que = a.dataset.lado;
        if (que === 'plegar' || que === 'abrir') plegar(que === 'plegar');
        else if (que === 'encargar') void encargar();
        else if (que === 'rotar') void rotar();
        else if (que === 'cancelar' && a.dataset.dir) void cancelar(a.dataset.dir);
    });
    // mientras se ve el mismo hilo, la ficha se mantiene al día (el peso de la conversación, la rotación)
    setInterval(() => { if (actual && !document.hidden) void mostrar(actual, true); }, CADA);
}
