// La barra de la derecha (#lado), al ver un hilo. Tiene dos hojas: la **ficha** del hilo de un agente residente (quién
// es: para, modelo, si es residente, dónde vive; cuánto pesa su conversación contra el tope de rotación, su último
// relevo y su CLAUDE.md, para leer) y los **códigos** que nombra el hilo (web/codigos.ts: `H3`, `PEN-07`, `T84`, con
// lo que es cada uno). Aparece si el hilo tiene alguna de las dos; con las dos, se elige arriba. Se pliega con sus
// flechas (un cambio en el modo puesto, web/modos.ts); el modo también la oculta. En el celular no está.

import * as cli from '../cli';
import * as codigos from './codigos';
import { esc, fechaCorta } from '../estilo';
import * as glifos from './glifos';
import * as modos from './modos';
import { modelo } from '../modelo';
import * as ui from './ui';
import { I } from './iconos';

/** cada cuánto se relee la ficha mientras se ve el mismo hilo */
const CADA = 30 * 1000;

let actual = '';
/** la máquina del hilo que se ve ("" si es esta): a ella van encargar, rotar y cancelar */
let maquinaActual = '';
let ficha: cli.JsonFichaAgente | undefined;
let leida = 0;
/** la hoja elegida cuando hay las dos (la ficha y los códigos) */
let hoja: 'ficha' | 'codigos' = 'ficha';

const lado = () => document.getElementById('lado') as HTMLElement | null;

/** Plegada, abierta u oculta: lo dice el modo puesto (web/modos.ts); plegarla a mano es un cambio en él. */
const plegado = (): boolean => modos.valor('lado') === 'plegado';

function plegar(si: boolean): void {
    modos.poner('lado', si ? 'plegado' : 'abierto');   // avisa, y alCambiar la redibuja
}

const mb = (b: number) => `${(b / (1024 * 1024)).toFixed(b < 10 * 1024 * 1024 ? 1 : 0).replace('.', ',')} MB`;

const PLEGAR = `<a class="lado-pliegue i" data-lado="plegar" title="plegar la barra">${I.plegado}</a>`;

function pintar(): void {
    const el = lado();
    if (!el) return;
    const hayFicha = !!ficha, hayCodigos = codigos.hay();
    if ((!hayFicha && !hayCodigos) || modos.valor('lado') === 'oculto') { el.hidden = true; return; }
    el.hidden = false;
    const p = plegado();
    el.classList.toggle('plegado', p);
    const cual = hayFicha && hayCodigos ? hoja : hayFicha ? 'ficha' : 'codigos';
    if (p) {
        const rotulo = cual === 'ficha' && ficha ? ficha.agente.nombre : 'códigos';
        el.innerHTML = `<a class="lado-pliegue i" data-lado="abrir" title="mostrar la barra">${I.atras}</a>`
            + `<div class="lado-vertical" data-lado="abrir">${esc(rotulo)}</div>`;
        return;
    }
    // la caja de buscar de los códigos no pierde el foco ni lo escrito cuando la hoja se redibuja (se relee sola)
    const caja = document.activeElement instanceof HTMLInputElement && el.contains(document.activeElement)
        ? { desde: document.activeElement.selectionStart, hasta: document.activeElement.selectionEnd } : undefined;
    const hojas = hayFicha && hayCodigos
        ? `<div class="lado-hojas"><a data-lado="hoja" data-hoja="ficha"${cual === 'ficha' ? ' class="sel"' : ''}>${I.ficha} ficha</a>`
            + `<a data-lado="hoja" data-hoja="codigos"${cual === 'codigos' ? ' class="sel"' : ''}>${I.codigos} códigos <span class="dim">${codigos.cuantos()}</span></a>${PLEGAR}</div>`
        : '';
    if (cual === 'codigos') {
        el.innerHTML = (hojas || `<div class="lado-cab"><b>${I.codigos} códigos</b>${PLEGAR}</div>`) + codigos.html();
    } else {
        el.innerHTML = htmlFicha(!hojas, hojas);
        glifos.pintarEn(el);
    }
    if (caja) {
        const input = el.querySelector<HTMLInputElement>('.cod-buscar input');
        input?.focus();
        input?.setSelectionRange(caja.desde, caja.hasta);
    }
}

/** La ficha del agente; `conPliegue`, si su cabecera lleva la flecha de plegar (sin las pestañas de las hojas). */
function htmlFicha(conPliegue: boolean, hojas: string): string {
    if (!ficha) return '';
    const a = ficha.agente;
    // con los glifos prendidos, su sello: el glifo del hilo, grande, con su estado (web/glifos)
    const nombre = actual.startsWith('rem:') ? actual.slice(actual.indexOf(':', 4) + 1) : actual;
    const at = modelo.porNombre(nombre)?.atencion ?? 'ninguna';
    const sello = glifos.prendidos() && nombre
        ? `<div class="lado-sello">${glifos.htmlSello(nombre, at === 'termino' || at === 'trabajando' || at === 'espera' ? at : 'ninguna')}</div>` : '';
    const h: string[] = [`${hojas}${sello}<div class="lado-cab"><b>${esc(a.nombre)}</b><span class="dim"> · agente:${esc(a.clave)}</span>`
        + (conPliegue ? PLEGAR : '') + '</div>'];
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
        h.push(`<div class="lado-rota">${I.releer} rotando: ${esc(fase[ficha.rotacion] ?? ficha.rotacion)}</div>`);
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
    return h.join('');
}

/** Lo que se ve cambió: `que` es la clave de la página («Faro», «rem:telar:Gestión», «dashboard», «doc:…»). La
 *  barra aparece si es el hilo de un agente o si su hilo nombra códigos, y se va si no. `deFondo`: la relectura de
 *  cada tanto, que redibuja solo si algo cambió (así no se cierra lo que se abrió ni se pierde lo escrito). */
export async function mostrar(que: string, esHilo: boolean, deFondo = false): Promise<void> {
    if (!esHilo) { actual = ''; ficha = undefined; void codigos.cargar('', '', ''); pintar(); return; }
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const i = remoto.indexOf(':');
    const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
    maquinaActual = maquina;
    const nuevo = que !== actual;
    if (nuevo) ficha = undefined;
    actual = que;
    // los códigos, a la par de la ficha: cada uno redibuja al llegar (y cargar olvida al instante los del hilo de antes)
    const deCodigos = codigos.cargar(que, hilo, maquina).then(cambio => { if (actual === que && cambio) pintar(); });
    if (!deFondo) pintar();
    if (!nuevo && Date.now() - leida < CADA) { await deCodigos; return; }
    const r = await cli.fichaAgente(hilo, maquina);
    if (actual !== que) return;  // ya se fue a otro
    leida = Date.now();
    const antes = JSON.stringify(ficha ?? null);
    ficha = r.datos ?? undefined;
    if (!deFondo || JSON.stringify(ficha ?? null) !== antes) pintar();
    await deCodigos;
}

/** Un código del hilo que se ve, desde su enlace en la terminal o la conversación (web/rutas-agente.ts): la barra se
 *  abre en la hoja de códigos (si estaba plegada, se despliega), con ese código abierto y a la vista. */
export function abrirCodigo(codigo: string): void {
    hoja = 'codigos';
    codigos.enfocar(codigo);
    if (plegado()) plegar(false);   // alCambiar la redibuja
    else pintar();
    requestAnimationFrame(() => document.querySelector('#lado .cod-fila.sel')?.scrollIntoView({ block: 'nearest' }));
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
    modos.alCambiar(() => pintar());
    const el = lado();
    // lo de la hoja de códigos: sus clics, su caja de buscar y sus clases que se abren y se pliegan
    el?.addEventListener('input', e => { codigos.atender(e); });
    el?.addEventListener('keydown', e => { codigos.atender(e); });
    el?.addEventListener('toggle', e => { codigos.atender(e); }, true);
    el?.addEventListener('click', e => {
        if (codigos.atender(e)) return;
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-lado]');
        if (!a) return;
        const que = a.dataset.lado;
        if (que === 'plegar' || que === 'abrir') plegar(que === 'plegar');
        else if (que === 'hoja' && (a.dataset.hoja === 'ficha' || a.dataset.hoja === 'codigos')) { hoja = a.dataset.hoja; pintar(); }
        else if (que === 'encargar') void encargar();
        else if (que === 'rotar') void rotar();
        else if (que === 'cancelar' && a.dataset.dir) void cancelar(a.dataset.dir);
    });
    // mientras se ve el mismo hilo, la ficha se mantiene al día (el peso de la conversación, la rotación)
    setInterval(() => { if (actual && !document.hidden) void mostrar(actual, true, true); }, CADA);
}
