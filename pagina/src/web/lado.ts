// La barra de la derecha (#lado), al ver un hilo. Sus hojas, cada una en su pestaña (componentes/pestanas.ts): la
// **ficha** del hilo de un agente residente (quién es: para, modelo, si es residente, dónde vive; cuánto pesa su
// conversación contra el tope de rotación, su último relevo y su CLAUDE.md, para leer), sus **notas** (web/borradores.ts:
// los próximos prompts que la persona le escribe mientras su agente trabaja, para mandárselos cuando le toque), los
// **códigos** que nombra el hilo (web/codigos.ts: `H3`, `PEN-07`, `T84`, con lo que es cada uno) y lo que carga su
// **contexto** (web/carga.ts: los archivos generales, lo que leyó, lo que se repite, con lo que pesa cada cosa). Aparece
// en todo hilo: las notas y el contexto valen para cualquiera.
//
//   ┌ #lado ─────────────────────────────────────────┐
//   │ [◎ ficha] [✎ notas 2•] [⌗ códigos 12] [⋯]  [›] │  las pestañas, del alto de la barra de al lado; las que no caben,
//   ├────────────────────────────────────────────────┤  al «⋯» (web/pestanas.ts). El punto en «notas»: el hilo terminó
//   │ la hoja abierta (se desplaza)                  │  su turno con notas guardadas
//   └────────────────────────────────────────────────┘
//
// La hoja de las notas no se redibuja con las demás: su caja guarda lo escrito y el foco (web/borradores.ts la arma una
// vez y la mantiene). Se pliega con su flecha (un cambio en el modo puesto, web/modos.ts); el modo también la oculta.
// Plegada, dice cuántas notas tiene (y si el hilo terminó su turno con ellas); un clic va a la caja. En el celular no
// está: las notas, en su ventana.

import * as cli from '../cli';
import * as borradores from './borradores';
import * as carga from './carga';
import * as codigos from './codigos';
import { esc, fechaCorta } from '../estilo';
import * as glifos from './glifos';
import * as modos from './modos';
import { modelo } from '../modelo';
import * as ui from './ui';
import { I } from './iconos';
import { pestanas, type Pestana } from '../componentes/pestanas';
import { acomodar } from './pestanas';

/** cada cuánto se relee la ficha mientras se ve el mismo hilo */
const CADA = 30 * 1000;

let actual = '';
/** la máquina del hilo que se ve ("" si es esta): a ella van encargar, rotar y cancelar */
let maquinaActual = '';
let ficha: cli.JsonFichaAgente | undefined;
let leida = 0;
type Hoja = 'ficha' | 'notas' | 'codigos' | 'contexto';
/** la hoja elegida (si la elegida no está en el hilo que se ve, la primera que haya) */
let hoja: Hoja = 'ficha';
const HOJAS: Hoja[] = ['ficha', 'notas', 'codigos', 'contexto'];

const lado = () => document.getElementById('lado') as HTMLElement | null;
/** arriba, las pestañas (o, plegada, nada) */
const cabezaEl = () => document.querySelector<HTMLElement>('#lado > .lado-cabeza');
/** la hoja abierta (ficha, códigos o contexto), que se redibuja y se desplaza; plegada, la franja */
const hojaEl = () => document.querySelector<HTMLElement>('#lado > .lado-hoja');
/** la hoja de las notas: la arma web/borradores.ts una vez, y aquí solo se muestra o se esconde */
const notasEl = () => document.querySelector<HTMLElement>('#lado > .lado-notas');

/** Plegada, abierta u oculta: lo dice el modo puesto (web/modos.ts); plegarla a mano es un cambio en él. */
const plegado = (): boolean => modos.valor('lado') === 'plegado';

function plegar(si: boolean): void {
    modos.poner('lado', si ? 'plegado' : 'abierto');   // avisa, y alCambiar la redibuja
}

const mb = (b: number) => `${(b / (1024 * 1024)).toFixed(b < 10 * 1024 * 1024 ? 1 : 0).replace('.', ',')} MB`;

const PLEGAR = `<a class="lado-pliegue i" data-lado="plegar" title="plegar la barra">${I.plegado}</a>`;

/** Las hojas que tiene el hilo que se ve, en orden. */
function hojasDelHilo(): Hoja[] {
    return HOJAS.filter(h => h === 'ficha' ? !!ficha : h === 'notas' ? true : h === 'codigos' ? codigos.hay() : carga.hay());
}

/** Cada hoja en su pestaña (componentes/pestanas.ts): su ícono, su nombre y, tenue, lo que cuenta (cuántos códigos,
 *  cuántas notas). Las que no caben van al «⋯» (web/pestanas.ts); el peso del contexto lo dice su hoja. Las notas, si el
 *  hilo terminó su turno con guardadas, el punto de algo nuevo en el color de lo que terminó. */
const PESTANA: Record<Hoja, () => Pestana> = {
    ficha: () => ({ valor: 'ficha', nombre: 'ficha', icono: I.ficha, ayuda: 'el agente del hilo: qué es, sus datos, encargarle' }),
    notas: () => {
        const n = borradores.cuantos(), recuerda = borradores.recordando();
        return { valor: 'notas', nombre: 'notas', icono: I.borrador, cuenta: n || undefined, nuevo: recuerda ? 'termino' : undefined,
            ayuda: `${recuerda ? 'terminó su turno: ¿le mandas la siguiente? · ' : ''}los próximos prompts que le guardas, para mandárselos cuando le toque (⌥B)` };
    },
    codigos: () => ({ valor: 'codigos', nombre: 'códigos', icono: I.codigos, cuenta: codigos.cuantos(), ayuda: 'los códigos que dejó la conversación' }),
    contexto: () => ({ valor: 'contexto', nombre: 'contexto', icono: I.carga, ayuda: 'lo que carga el contexto del hilo' }),
};

/** Plegada, los borradores del hilo se dicen debajo del rótulo: cuántos, y si terminó su turno con guardados. */
function htmlBorradoresPlegado(): string {
    const n = borradores.cuantos();
    if (!n) return '';
    const recuerda = borradores.recordando();
    return `<a class="lado-bor${recuerda ? ' recuerda' : ''}" data-lado="borrador" title="${n} ${n === 1 ? 'borrador' : 'borradores'}`
        + `${recuerda ? ': terminó su turno' : ''} (⌥B)"><span class="i">${I.borrador}</span>${n}</a>`;
}

/** Las pestañas de arriba: se redibujan solo si cambiaron (el foco con el teclado no se pierde a cada relectura). */
function pintarCabeza(cual: Hoja | undefined, hay: Hoja[]): void {
    const cabeza = cabezaEl();
    if (!cabeza) return;
    const h = cual ? pestanas({ nombre: 'hojas del hilo', dato: 'lado', accion: 'hoja', activa: cual, clases: ['lado-hojas'], fin: PLEGAR,
        pestanas: hay.map(x => ({ ...PESTANA[x](), datos: { hoja: x } })) }) : '';
    if (cabeza.dataset.html !== h) {
        const foco = document.activeElement instanceof HTMLElement && cabeza.contains(document.activeElement)
            ? document.activeElement.dataset.valor ?? (document.activeElement.classList.contains('pestanas-mas') ? '⋯' : '') : '';
        cabeza.innerHTML = h;
        cabeza.dataset.html = h;
        if (foco) cabeza.querySelector<HTMLElement>(foco === '⋯' ? '.pestanas-mas' : `.pestana[data-valor="${CSS.escape(foco)}"]`)?.focus();
    }
    const fila = cabeza.querySelector('.pestanas');
    if (fila) acomodar(fila);
}

function pintar(): void {
    const el = lado(), arriba = hojaEl(), notas = notasEl(), cabeza = cabezaEl();
    if (!el || !arriba || !notas || !cabeza) return;
    const hay = hojasDelHilo();
    if (!actual || modos.valor('lado') === 'oculto') { el.hidden = true; return; }
    el.hidden = false;
    const p = plegado();
    el.classList.toggle('plegado', p);
    const cual = hay.includes(hoja) ? hoja : hay[0];
    if (p) {
        const rotulo = cual === 'ficha' && ficha ? ficha.agente.nombre : cual === 'codigos' ? 'códigos' : cual ?? 'notas';
        cabeza.hidden = true; notas.hidden = true; arriba.hidden = false;
        arriba.innerHTML = `<div class="lado-barra"><a class="lado-pliegue i" data-lado="abrir" title="mostrar la barra">${I.atras}</a></div>`
            + htmlBorradoresPlegado() + `<div class="lado-vertical" data-lado="abrir">${esc(rotulo)}</div>`;
        return;
    }
    cabeza.hidden = false;
    pintarCabeza(cual, hay);
    notas.hidden = cual !== 'notas';
    arriba.hidden = cual === 'notas';
    if (cual === 'notas') { borradores.alMostrar(); return; }
    // la caja de buscar de los códigos no pierde el foco ni lo escrito cuando la hoja se redibuja (se relee sola)
    const caja = document.activeElement instanceof HTMLInputElement && arriba.contains(document.activeElement)
        ? { desde: document.activeElement.selectionStart, hasta: document.activeElement.selectionEnd } : undefined;
    if (cual === 'codigos') arriba.innerHTML = codigos.html();
    else if (cual === 'contexto') arriba.innerHTML = `<div class="carga">${carga.html()}</div>`;
    else { arriba.innerHTML = htmlFicha(); glifos.pintarEn(arriba); }
    if (caja) {
        const input = arriba.querySelector<HTMLInputElement>('.cod-buscar input');
        input?.focus();
        input?.setSelectionRange(caja.desde, caja.hasta);
    }
}

/** La ficha del agente: su sello (con los glifos prendidos), su nombre y lo demás. */
function htmlFicha(): string {
    if (!ficha) return '';
    const a = ficha.agente;
    // con los glifos prendidos, su sello: el glifo del hilo, grande, con su estado (web/glifos)
    const nombre = actual.startsWith('rem:') ? actual.slice(actual.indexOf(':', 4) + 1) : actual;
    const at = modelo.porNombre(nombre)?.atencion ?? 'ninguna';
    const sello = glifos.prendidos() && nombre
        ? `<div class="lado-sello">${glifos.htmlSello(nombre, at === 'termino' || at === 'trabajando' || at === 'espera' ? at : 'ninguna')}</div>` : '';
    const cab = `<div class="lado-cab"><b>${esc(a.nombre)}</b><span class="dim"> · agente:${esc(a.clave)}</span></div>`;
    const h: string[] = [`${sello}${cab}`];
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

/** El nombre del hilo en una clave de la página («Faro», o «rem:telar:Secretaría» para uno de otra máquina). */
const nombreDe = (que: string): string => {
    if (!que.startsWith('rem:')) return que;
    const resto = que.slice(4);
    return resto.slice(resto.indexOf(':') + 1);
};

/** Lo que se ve cambió: `que` es la clave de la página («Faro», «rem:telar:Secretaría», «dashboard», «doc:…»). La
 *  barra aparece en todo hilo (su contexto) y se va si no es un hilo. `deFondo`: la relectura de cada tanto, que
 *  redibuja solo si algo cambió (así no se cierra lo que se abrió ni se pierde lo escrito). */
export async function mostrar(que: string, esHilo: boolean, deFondo = false): Promise<void> {
    // el que se deja y el que se abre ya se vieron: la barra lo dice al tiro, sin esperar a que el servidor lo cuente
    if (actual && que !== actual) modelo.ver(nombreDe(actual));
    if (!esHilo) {
        actual = ''; ficha = undefined; void codigos.cargar('', '', ''); void carga.cargar('', '', ''); void borradores.cargar('', '', '');
        pintar(); return;
    }
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const i = remoto.indexOf(':');
    const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
    maquinaActual = maquina;
    const nuevo = que !== actual;
    if (nuevo) { ficha = undefined; modelo.ver(hilo); }
    actual = que;
    // los códigos y el contexto, a la par de la ficha: cada uno redibuja al llegar (y cargar olvida al instante los del
    // hilo de antes)
    const deCodigos = codigos.cargar(que, hilo, maquina).then(cambio => { if (actual === que && cambio) pintar(); });
    const deCarga = carga.cargar(que, hilo, maquina).then(cambio => { if (actual === que && cambio) pintar(); });
    void borradores.cargar(que, hilo, maquina);
    if (!deFondo) pintar();
    if (!nuevo && Date.now() - leida < CADA) { await Promise.all([deCodigos, deCarga]); return; }
    const r = await cli.fichaAgente(hilo, maquina);
    if (actual !== que) return;  // ya se fue a otro
    leida = Date.now();
    const antes = JSON.stringify(ficha ?? null);
    ficha = r.datos ?? undefined;
    if (!deFondo || JSON.stringify(ficha ?? null) !== antes) pintar();
    await Promise.all([deCodigos, deCarga]);
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

/** Encargarle algo al agente del hilo que se ve: la ventana de la instrucción (web/instruccion.ts), solo a él, con
 *  sus skills. Queda como encargo:e-…, y el resultado llega. */
async function encargar(): Promise<void> {
    if (!ficha) return;
    const { abrir } = await import('./instruccion');
    if (!await abrir({ a: ficha.agente.nombre, solo: true })) return;
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
    if (await ui.aviso(`¿Cancelar ${direccion}?`, 'Cancelar el encargo', { destruye: true }) !== 'Cancelar el encargo') return;
    const r = await cli.accionObjeto(direccion, 'cancelar', { motivo: 'lo canceló su persona desde la página' });
    if (!r.datos) { void ui.falla(`telar: no se pudo: ${r.error ?? 'sin respuesta'}`); return; }
    leida = 0;
    await mostrar(actual, true);
}

/** Los clics de la barra (plegar, abrir, encargar, rotar, cancelar). Una vez, al arrancar. */
export function montar(): void {
    modos.alCambiar(() => pintar());
    const el = lado();
    // arriba las pestañas; debajo la hoja abierta (lo que cambia y se desplaza) o la de las notas (web/borradores.ts),
    // que se arma una vez
    const cabeza = document.createElement('div');
    cabeza.className = 'lado-cabeza';
    const arriba = document.createElement('div');
    arriba.className = 'lado-hoja';
    const notas = document.createElement('section');
    notas.className = 'lado-notas';
    notas.hidden = true;
    el?.replaceChildren(cabeza, arriba, notas);
    borradores.montarEn(notas);
    borradores.montar();
    // ⌥B, ⌘K y el botón de la barra del hilo: la barra abierta, en las notas
    borradores.alPedir(() => {
        hoja = 'notas';
        if (plegado()) plegar(false);   // alCambiar la redibuja
        else pintar();
    });
    // la cuenta de las notas y el «terminó» van en su pestaña (plegada, en la franja): al cambiar, se redibuja eso
    window.addEventListener('telar:borradores', () => {
        if (!actual || el?.hidden) return;
        if (plegado()) { pintar(); return; }
        const hay = hojasDelHilo();
        pintarCabeza(hay.includes(hoja) ? hoja : hay[0], hay);
    });
    cabeza.addEventListener('click', e => {
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-lado]');
        if (!a) return;
        if (a.dataset.lado === 'plegar') plegar(true);
        else if (a.dataset.lado === 'hoja' && HOJAS.includes(a.dataset.hoja as Hoja)) {
            hoja = a.dataset.hoja as Hoja;
            if (hoja === 'notas') borradores.visto();
            pintar();
        }
    });
    // lo de la hoja de códigos: sus clics, su caja de buscar y sus clases que se abren y se pliegan
    arriba.addEventListener('input', e => { codigos.atender(e); });
    arriba.addEventListener('keydown', e => { codigos.atender(e); });
    arriba.addEventListener('toggle', e => { codigos.atender(e); }, true);
    arriba.addEventListener('click', e => {
        if (codigos.atender(e) || carga.atender(e)) return;
        const a = (e.target as HTMLElement).closest<HTMLElement>('[data-lado]');
        if (!a) return;
        const que = a.dataset.lado;
        if (que === 'plegar' || que === 'abrir') plegar(que === 'plegar');
        else if (que === 'encargar') void encargar();
        else if (que === 'rotar') void rotar();
        else if (que === 'cancelar' && a.dataset.dir) void cancelar(a.dataset.dir);
        else if (que === 'borrador') borradores.enfocar();
    });
    // mientras se ve el mismo hilo, la ficha se mantiene al día (el peso de la conversación, la rotación), y su contexto
    setInterval(() => { if (actual && !document.hidden) void mostrar(actual, true, true); }, CADA);
}
