// Las notas del hilo que se ve: los próximos prompts que la persona escribe mientras su agente trabaja, para mandárselos
// cuando le toque (telar.borradores; `GET|POST|DELETE /api/hilos/borradores`). Son una pestaña de la barra de la derecha
// (#lado, web/lado.ts: «notas», con su ícono y su cuenta); en el teléfono, donde esa barra no está, una ventana que abre su
// botón de la barra del hilo (o ⌥B).
//
//   ┌ [◎ ficha] [✎ notas 2•] [⌗ códigos] … ───────┐  la pestaña: cuántas, y si el hilo terminó su turno con guardadas,
//   │ 1  revisa el plan y…       ▷ ✎ ⧉ ✕          │  el punto (sin ventana ni sonido)
//   │ 2  después: el README  ◷   ▷ ✎ ⧉ ✕          │  la lista, en orden: un clic en una fila la edita; ◷ sale al terminar
//   │ ┌─────────────────────────────────────────┐ │  la caja: lo escrito se guarda solo (en el estado de la máquina del
//   │ │ el próximo prompt…                      │ │  hilo, no en el navegador: sobrevive a una recarga y se ve desde el
//   │ └─────────────────────────────────────────┘ │  teléfono)
//   │ guardado 11:42    ＋  ⌥⏎ dejarlo  ⌘⏎ enviar │  el pie: si se guardó, y los botones (sobre la caja, si terminó su
//                                                     turno o si trabaja)
//   └──────────────────────────────────────────────┘
//
// Mandar una la deja escrita en la entrada de Claude Code de su hilo, sin ⏎, para revisarla ahí (⌥⏎, o ▷); con ⌘⏎ (o ⌘ y
// clic en ▷) la envía. Sale de la lista. Si el agente trabaja (o te pregunta algo), no se mezcla con su turno: lo dice y
// ofrece esperar a que termine; en espera, sale sola al terminar el turno (lo hace telar, aunque la página esté cerrada).
//
// Lo que se escribe en la caja no llega a los atajos del dashboard ni a la terminal (⌘ y ⌃ sí: ⌘K); ⎋ la suelta.

import * as cli from '../cli';
import { esc } from '../estilo';
import { item } from '../componentes/item';
import { boton } from '../componentes/boton';
import { maquinaDe } from './codigos';
import { I } from './iconos';
import { modelo } from '../modelo';
import * as modos from './modos';
import * as recarga from './recarga';
import * as ui from './ui';
import { copiarEnElGesto } from './portapapeles';

/** cada cuánto se relee la lista mientras se ve (lo que cambió en otro lado: el teléfono, la CLI, lo que salió solo) */
const CADA = 15 * 1000;
/** cuánto se espera después de la última tecla para guardar */
const GUARDAR_TRAS = 600;
/** hasta cuántas líneas crece la caja */
const LINEAS = 10;

let clave = '';
let hilo = '', maquina = '';
let lista: cli.JsonBorrador[] = [];
let ocupado = '';
let leida = 0;
let cargado = false;
let error = '';
/** El borrador que está en la caja: su id ("" mientras lo escrito no se guarda: uno nuevo). Un objeto, y uno nuevo cada
 *  vez que la caja pasa a otro (nuevo, editar otro, mandarlo, otro hilo): lo que se guarda aparte sabe a cuál va,
 *  aunque la caja ya tenga otro, y un nuevo que se está creando recibe su id ahí. */
interface Ranura { id: string }
let ranura: Ranura = { id: '' };
/** lo último guardado de lo que está en la caja: si la caja dice otra cosa, falta guardar */
let guardado = '';
let estado = '';
/** terminó su turno y tiene guardados: la cabecera lo recuerda hasta que la persona haga algo aquí, o empiece otro */
let recuerda = false;
/** lo que se estaba editando en cada hilo, al dejarlo: al volver, la caja sigue en el mismo */
const editandoEn = new Map<string, Ranura>();
let cola: Promise<unknown> = Promise.resolve();
let espera = 0;
const raices = new Set<HTMLElement>();

/** Lo que abre la pestaña de las notas (la pone web/lado.ts): ⌥B, ⌘K y el botón de la barra del hilo pasan por aquí. */
let pedir: () => void = () => undefined;
export function alPedir(f: () => void): void { pedir = f; }

/** Cuántos tiene el hilo que se ve (para la barra plegada). */
export const cuantos = (): number => lista.length;
/** Si recuerda que el hilo terminó con guardados. */
export const recordando = (): boolean => recuerda && lista.length > 0;
/** El hilo que se ve, si hay uno. */
export const deHilo = (): string => hilo;
/** La persona abrió la pestaña: el «terminó» queda visto. */
export function visto(): void { if (recuerda) { recuerda = false; pintar(); } }
/** La pestaña se ve: la caja, que estaba escondida, se mide de nuevo. */
export function alMostrar(): void { const c = campoDe(); if (c) crecer(c); }

const primeraLinea = (t: string): string => t.split('\n').find(l => l.trim())?.trim() ?? '';

/** Sobre la caja, cómo está su agente, si importa para mandar: terminó su turno con notas guardadas, o trabaja (lo que
 *  mandes espera a que termine). */
function htmlTurno(): string {
    return recordando() ? `<span class="bor-recuerda"><span class="i">${I.campana}</span> terminó su turno: ¿le mandas la siguiente?</span>`
        : ocupado === 'trabajando' ? 'trabajando: lo que le mandes espera a que termine su turno' : '';
}

function htmlLista(): string {
    if (error && !lista.length) return `<div class="falla bor-nota">${esc(error)}</div>`;
    return lista.map((b, i) => {
        const titulo = primeraLinea(b.texto);
        const mas = b.texto.trim().split('\n').length - 1;
        const espera = b.al_terminar
            ? { icono: I.reloj, tono: 'atencion' as const, ayuda: `sale cuando termine su turno${b.al_terminar === 'enviar' ? ', con ⏎' : ', sin ⏎'}: clic para que no` }
            : undefined;
        return item({
            accion: 'bor-editar', id: b.id, activa: b.id === ranura.id, apagada: !titulo,
            ayuda: `${b.texto.slice(0, 600)}${b.texto.length > 600 ? '…' : ''}\nclic: editarlo`,
            inicio: [{ texto: String(i + 1), tono: 'tenue' }],
            titulo: titulo || '(vacío)',
            sufijo: mas > 0 ? [{ texto: `+${mas}`, tono: 'tenue', ayuda: `${mas + 1} líneas` }] : [],
            aviso: espera,
            fijas: [
                { accion: 'bor-mandar', id: b.id, icono: I.enviar, tono: 'acento', ayuda: 'dejarlo escrito en su entrada, sin ⏎ (⌘ y clic: y enviarlo)' },
                { accion: 'bor-editar', id: b.id, icono: I.editar, ayuda: 'editarlo en la caja' },
                { accion: 'bor-copiar', id: b.id, icono: I.copiar, ayuda: 'copiarlo' },
                { accion: 'bor-borrar', id: b.id, icono: I.descartar, peligro: true, ayuda: 'borrarlo (pregunta antes)' },
            ],
        });
    }).join('');
}

function htmlPie(): string {
    const hay = !!campoDe()?.value.trim();
    return `<span class="botonera-izq bor-estado">${esc(estado)}</span>`
        + boton({ texto: 'nuevo', accion: 'bor-nuevo', tono: 'callado', icono: I.nuevo, ayuda: 'guardar este y empezar otro', estado: hay ? 'normal' : 'deshabilitado' })
        + boton({ texto: 'dejarlo', accion: 'bor-dejar', tecla: '⌥⏎', ayuda: 'escribirlo en la entrada de su hilo, sin ⏎: lo revisas y lo mandas tú', estado: hay ? 'normal' : 'deshabilitado' })
        + boton({ texto: 'enviar', accion: 'bor-enviar', tecla: '⌘⏎', ayuda: 'escribirlo en la entrada de su hilo y enviarlo', estado: hay ? 'normal' : 'deshabilitado' });
}

/** El esqueleto de una raíz: lista, caja y pie. */
function armar(raiz: HTMLElement): void {
    raiz.classList.add('borradores');
    raiz.innerHTML = '<div class="bor-cuerpo"><div class="bor-lista"></div><div class="bor-turno" hidden></div>'
        + '<div class="bor-caja"><textarea class="bor-campo" rows="2" spellcheck="true" aria-label="la próxima nota"'
        + ' placeholder="el próximo prompt: se guarda solo (⌥B)"></textarea></div><div class="bor-pie botonera"></div></div>';
}

const campoDe = (): HTMLTextAreaElement | null => {
    for (const r of raices) { const c = r.querySelector<HTMLTextAreaElement>('.bor-campo'); if (c && r.isConnected) return c; }
    return null;
};

function crecer(c: HTMLTextAreaElement): void {
    // sin dibujar (plegada, en otra pestaña) no tiene alto que medir: el de su CSS, hasta que se vea
    if (!c.isConnected || !c.getClientRects().length) { c.style.height = ''; return; }
    c.style.height = 'auto';
    const alto = parseFloat(getComputedStyle(c).lineHeight) || 17;
    c.style.height = `${Math.min(c.scrollHeight + 2, alto * LINEAS + 8)}px`;
}

/** Redibuja todo menos lo escrito en la caja. */
function pintar(): void {
    for (const r of raices) {
        if (!hilo) continue;
        r.classList.toggle('recuerda', recordando());
        const lis = r.querySelector<HTMLElement>('.bor-lista'), pie = r.querySelector<HTMLElement>('.bor-pie'),
            turno = r.querySelector<HTMLElement>('.bor-turno');
        const l = htmlLista(), p = htmlPie(), t = htmlTurno();
        if (turno && turno.innerHTML !== t) { turno.innerHTML = t; turno.hidden = !t; }
        if (lis && lis.dataset.html !== l) { lis.innerHTML = l; lis.dataset.html = l; }
        if (pie && pie.innerHTML !== p) pie.innerHTML = p;
        const campo = r.querySelector<HTMLTextAreaElement>('.bor-campo');
        if (campo) crecer(campo);
    }
    window.dispatchEvent(new CustomEvent('telar:borradores', { detail: { hilo, cuantos: lista.length, recuerda: recordando() } }));
}

function ponerEnLaCaja(texto: string): void {
    for (const r of raices) {
        const c = r.querySelector<HTMLTextAreaElement>('.bor-campo');
        if (c) { c.value = texto; crecer(c); }
    }
}

/** Lo que se ve cambió: carga los borradores del hilo (`que`, la clave de la página) si no están o están viejos. El
 *  cambio de hilo es sincrónico (lo que faltaba guardar del de antes se guarda en ese, aparte): dos cambios seguidos
 *  quedan en el orden en que se pidieron. */
export async function cargar(que: string, h: string, m: string, forzar = false): Promise<void> {
    if (que !== clave) {
        soltarHilo();
        clave = que; hilo = que ? h : ''; maquina = que ? maquinaDe(h, m) : '';
        lista = []; ocupado = ''; leida = 0; cargado = false; error = ''; recuerda = false;
        ranura = editandoEn.get(que) ?? { id: '' };
        guardado = ''; estado = '';
        ponerEnLaCaja('');
        pintar();
    }
    if (!que || (!forzar && Date.now() - leida < CADA)) return;
    leida = Date.now();
    const v = cambios;
    const r = await cli.borradores(hilo, maquina);
    // otro hilo, o algo cambió aquí mientras se leía (lo leído es de antes): la próxima lectura lo trae
    if (clave !== que || v !== cambios) return;
    if (!r.datos) { error = r.error ?? 'no se pudieron leer'; pintar(); return; }
    error = '';
    const antes = ocupado;
    lista = r.datos.borradores;
    ocupado = r.datos.ocupado ?? '';
    if (antes && !ocupado && cargado && lista.length) recuerda = true;
    if (ocupado) recuerda = false;
    // lo que está en la caja: si se mandó o se borró en otra parte, la caja queda como nueva; si cambió allá y aquí no
    // hay nada por guardar, se trae
    const enCaja = lista.find(b => b.id === ranura.id);
    const c = campoDe();
    if (ranura.id && !enCaja) { ranura = { id: '' }; editandoEn.delete(clave); if (c && c.value === guardado) { ponerEnLaCaja(''); guardado = ''; } }
    else if (enCaja && c && (c.value === guardado || !cargado) && document.activeElement !== c) { ponerEnLaCaja(enCaja.texto); guardado = enCaja.texto; }
    cargado = true;
    pintar();
}

/** Al dejar un hilo: lo que falta guardar se guarda en ese (aparte), y se recuerda cuál estaba en la caja. */
function soltarHilo(): void {
    if (!clave) return;
    window.clearTimeout(espera);
    const c = campoDe();
    if (c && c.value !== guardado) void guardar();
    editandoEn.set(clave, ranura);
}

/** cuántas veces cambió aquí la lista: una lectura que empezó antes de un cambio no lo pisa */
let cambios = 0;

/** Guardar lo que dice la caja ahora, en orden (un nuevo espera su id antes del siguiente), en el hilo de ahora aunque
 *  después se vaya a otro. */
function guardar(): Promise<unknown> {
    const c = campoDe();
    if (!c || !clave) return cola;
    const h = hilo, m = maquina, k = clave, texto = c.value, mia = ranura;
    cola = cola.then(async () => {
        // sigue a la vista: el mismo hilo y el mismo borrador en la caja
        const aLaVista = () => k === clave && mia === ranura;
        if (aLaVista() && texto === guardado) return;
        if (!mia.id && !texto.trim()) { if (aLaVista()) guardado = texto; return; }
        if (aLaVista()) { estado = 'guardando…'; pintar(); }
        cambios++;
        let r = await cli.guardarBorrador(h, m, texto, mia.id);
        // se mandó o se borró en otra parte mientras se escribía: lo escrito queda como uno nuevo
        if (!r.datos && r.estado === 404 && mia.id) { mia.id = ''; r = await cli.guardarBorrador(h, m, texto, ''); }
        cambios++;
        if (!r.datos) { if (aLaVista()) { estado = `no se guardó: ${r.error ?? '?'}`; pintar(); } return; }
        const b = r.datos;
        mia.id = b.id;
        if (k !== clave) return;
        const i = lista.findIndex(x => x.id === b.id);
        if (i >= 0) lista[i] = b; else lista.push(b);
        if (mia !== ranura) { pintar(); return; }
        guardado = texto;
        estado = `guardado ${new Date().toTimeString().slice(0, 5)}`;
        pintar();
    }).catch(() => undefined);
    return cola;
}

function alEscribir(c: HTMLTextAreaElement): void {
    crecer(c);
    if (recuerda) { recuerda = false; pintar(); }
    window.clearTimeout(espera);
    espera = window.setTimeout(() => { void guardar(); }, GUARDAR_TRAS);
    // el pie (sus botones se encienden con algo escrito), sin esperar a guardar
    for (const r of raices) { const pie = r.querySelector<HTMLElement>('.bor-pie'); const p = htmlPie(); if (pie && pie.innerHTML !== p) pie.innerHTML = p; }
}

/** La caja pasa a otro borrador (`id`; "" uno nuevo): lo que tenía se guarda en el suyo, aparte, y si quedó vacío se va. */
function pasarA(id: string, texto: string): void {
    window.clearTimeout(espera);
    void guardar();
    const deja = ranura;
    ranura = { id }; guardado = texto;
    editandoEn.set(clave, ranura);
    ponerEnLaCaja(texto);
    void cola.then(() => quitarSiVacio(deja.id));
}

/** Empezar uno nuevo: el de la caja queda guardado (si está vacío, se va). */
function nuevo(): void {
    pasarA('', '');
    pintar();
    campoDe()?.focus();
}

async function quitarSiVacio(id: string): Promise<void> {
    const b = lista.find(x => x.id === id);
    if (!id || !b || b.texto.trim()) return;
    const r = await cli.borrarBorrador(hilo, maquina, id);
    if (r.datos || r.estado === 404) { cambios++; lista = lista.filter(x => x.id !== id); pintar(); }
}

function editar(id: string): void {
    if (id === ranura.id) { campoDe()?.focus(); return; }
    const b = lista.find(x => x.id === id);
    if (!b) return;
    pasarA(id, b.texto);
    recuerda = false;
    pintar();
    const c = campoDe();
    if (c) { c.focus(); c.setSelectionRange(c.value.length, c.value.length); }
}

async function borrar(id: string): Promise<void> {
    const b = lista.find(x => x.id === id);
    if (!b) return;
    const muestra = primeraLinea(b.texto).slice(0, 80) || '(vacío)';
    if (b.texto.trim() && await ui.aviso(`¿Borrar el borrador «${muestra}»?`, 'Borrar', { destruye: true }) !== 'Borrar') return;
    const r = await cli.borrarBorrador(hilo, maquina, id);
    if (!r.datos && r.estado !== 404) { void ui.falla(`no se borró: ${r.error ?? '?'}`); return; }
    cambios++;
    lista = lista.filter(x => x.id !== id);
    if (id === ranura.id) { ranura = { id: '' }; guardado = ''; editandoEn.delete(clave); ponerEnLaCaja(''); }
    pintar();
}

/** Mandárselo a su hilo: escrito en su entrada, sin ⏎ (o con `enviar`). Ocupado, pregunta si esperar a que termine. */
async function mandar(id: string, enviar: boolean, esperar = false): Promise<void> {
    const h = hilo, m = maquina, k = clave;
    const r = await cli.mandarBorrador(h, m, id, { enviar, esperar });
    if (k !== clave) return;
    if (!r.datos) {
        const que = r.cuerpo?.ocupado;
        if (r.estado === 409 && (que === 'trabajando' || que === 'espera') && !esperar) {
            const dice = que === 'trabajando'
                ? `«${h}» está trabajando: si se lo mandas ahora, se mezcla con su turno.`
                : `«${h}» te está preguntando algo: lo que le escribas ahora caería en su pregunta.`;
            const si = await ui.aviso(dice, 'Esperar a que termine', {
                detalle: enviar ? 'Sale con ⏎ apenas termine su turno (aunque cierres la página).'
                    : 'Queda escrito en su entrada apenas termine su turno, sin ⏎ (aunque cierres la página).' });
            if (si === 'Esperar a que termine') await mandar(id, enviar, true);
            return;
        }
        void ui.falla(`no se mandó: ${r.error ?? '?'}`);
        void cargar(clave, hilo, maquina, true);
        return;
    }
    const d = r.datos;
    cambios++;
    if (d.como === 'en espera') {
        const b = lista.find(x => x.id === id);
        if (b) b.al_terminar = d.al_terminar;
        void ui.estado(`sale cuando «${h}» termine su turno${enviar ? ', con ⏎' : ''}`);
    } else {
        lista = lista.filter(x => x.id !== id);
        if (id === ranura.id) { ranura = { id: '' }; guardado = ''; editandoEn.delete(clave); ponerEnLaCaja(''); }
        void ui.estado(d.como === 'enviado' ? `enviado a «${h}»` : `quedó escrito en la entrada de «${h}», sin ⏎: revísalo y mándalo ahí`);
    }
    recuerda = false;
    pintar();
}

/** Lo de la caja: se guarda primero (si falta) y se manda el que es. */
async function mandarLaCaja(enviar: boolean): Promise<void> {
    const c = campoDe();
    if (!c?.value.trim()) return;
    window.clearTimeout(espera);
    await guardar();
    if (ranura.id) await mandar(ranura.id, enviar);
}

async function noEsperar(id: string): Promise<void> {
    const r = await cli.mandarBorrador(hilo, maquina, id, { no_esperar: true });
    if (!r.datos) { void ui.falla(`no se pudo: ${r.error ?? '?'}`); return; }
    const b = lista.find(x => x.id === id);
    if (b) b.al_terminar = '';
    pintar();
}

/** Los clics y las teclas de una raíz. */
function atender(raiz: HTMLElement): void {
    raiz.addEventListener('click', e => {
        const t = e.target as HTMLElement;
        if (t.closest('.bor-campo')) return;
        const a = t.closest<HTMLElement>('[data-accion]');
        if (!a || !raiz.contains(a)) return;
        // una ventana (la del teléfono) se cerraría con el clic en un [data-accion]: es de aquí
        e.preventDefault(); e.stopPropagation();
        const id = a.dataset.id ?? '';
        switch (a.dataset.accion) {
            case 'bor-editar': editar(id); break;
            case 'bor-mandar': void mandar(id, e.metaKey || e.ctrlKey); break;
            case 'bor-copiar': {
                const b = lista.find(x => x.id === id);
                if (b) void copiarEnElGesto(b.texto).then(ok => ui.estado(ok ? 'copiado' : 'no se pudo copiar'));
                break;
            }
            case 'bor-borrar': void borrar(id); break;
            case 'bor-nuevo': nuevo(); break;
            case 'bor-dejar': void mandarLaCaja(false); break;
            case 'bor-enviar': void mandarLaCaja(true); break;
        }
    });
    // el reloj de uno en espera (el aviso de su fila): un clic le quita la espera, en vez de editarlo
    raiz.addEventListener('click', e => {
        const aviso = (e.target as HTMLElement).closest<HTMLElement>('.bor-lista .item-aviso');
        const id = aviso?.closest<HTMLElement>('.item')?.dataset.id;
        if (id) { e.preventDefault(); e.stopPropagation(); void noEsperar(id); }
    }, true);
    raiz.addEventListener('input', e => { const t = e.target as HTMLElement; if (t.matches('.bor-campo')) alEscribir(t as HTMLTextAreaElement); });
    raiz.addEventListener('focusout', e => { if ((e.target as HTMLElement).matches('.bor-campo')) { window.clearTimeout(espera); void guardar(); } });
    raiz.addEventListener('keydown', e => {
        const t = e.target as HTMLElement;
        if (!t.matches('.bor-campo')) return;
        if (e.key === 'Enter' && !e.isComposing && (e.metaKey || e.ctrlKey)) { e.preventDefault(); e.stopPropagation(); void mandarLaCaja(true); return; }
        if (e.key === 'Enter' && !e.isComposing && e.altKey) { e.preventDefault(); e.stopPropagation(); void mandarLaCaja(false); return; }
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); (t as HTMLTextAreaElement).blur(); return; }
        // lo demás es escribir: no sigue a los atajos de la página ni a la terminal (⌘ y ⌃ sí: ⌘K, ⌘M)
        if (!e.metaKey && !e.ctrlKey) e.stopPropagation();
    });
}

/** Pone las notas en `raiz` (la hoja de #lado, o la de la ventana del teléfono). Devuelve cómo sacarlo. */
export function montarEn(raiz: HTMLElement): () => void {
    armar(raiz);
    atender(raiz);
    raices.add(raiz);
    const c = raiz.querySelector<HTMLTextAreaElement>('.bor-campo');
    const enLaCaja = lista.find(b => b.id === ranura.id);
    if (c) { c.value = enLaCaja ? enLaCaja.texto : ''; crecer(c); }
    pintar();
    return () => { raices.delete(raiz); };
}

/** Ir a la caja del hilo que se ve (⌥B, ⌘K, el botón de la barra del hilo): la pestaña de las notas, abierta, con el
 *  foco en la caja. Si ya está ahí, vuelve a donde estaba. Sin la barra (el teléfono, o un modo que la oculta), en su
 *  ventana. */
let antes: HTMLElement | null = null;
export function enfocar(): void {
    if (!hilo) return;
    const c = campoDe();
    if (c && document.activeElement === c) { c.blur(); antes?.focus?.(); antes = null; return; }
    antes = document.activeElement as HTMLElement | null;
    if (document.body.classList.contains('angosto') || modos.valor('lado') === 'oculto') { void abrirEnVentana(); return; }
    recuerda = false;
    pedir();
    pintar();
    requestAnimationFrame(() => {
        const x = campoDe();
        if (!x) return;
        x.focus();
        x.setSelectionRange(x.value.length, x.value.length);
    });
}

/** En el teléfono: el bloque en una ventana. */
async function abrirEnVentana(): Promise<void> {
    const { abrirVentana } = await import('./ventana');
    await abrirVentana({ titulo: `notas · ${hilo}`, cuerpo: '<section class="bor-en-ventana"></section>', clase: 'bor-ventana' }, {
        foco: '.bor-campo',
        montar: d => {
            const r = d.querySelector<HTMLElement>('.bor-en-ventana');
            if (!r) return;
            const soltar = montarEn(r);
            return () => { window.clearTimeout(espera); void guardar(); soltar(); };
        },
    });
}

/** Una vez, al arrancar: ⌥B desde cualquier parte (antes que la terminal, que se lo comería), y que el hilo que se ve
 *  terminando su turno con guardados lo recuerde al tiro (sin esperar a la relectura). */
export function montar(): void {
    window.addEventListener('keydown', e => {
        if (!e.altKey || e.metaKey || e.ctrlKey || e.shiftKey || e.code !== 'KeyB' || !hilo) return;
        e.preventDefault(); e.stopPropagation();
        enfocar();
    }, true);
    let antesAtencion = '';
    modelo.cambio.event(() => {
        if (!hilo || maquina) return;
        const h = modelo.porNombre(hilo);
        const at = h?.atencion ?? '';
        if (antesAtencion === 'trabajando' && at !== 'trabajando' && at !== 'espera') {
            // terminó un turno: lo que estaba en espera salió (o no), y se relee
            void cargar(clave, hilo, maquina, true).then(() => { if (lista.length) { recuerda = true; pintar(); } });
        } else if ((h?.borradores ?? 0) !== lista.length && cargado && document.activeElement !== campoDe()) {
            void cargar(clave, hilo, maquina, true);
        }
        if (at === 'trabajando' && recuerda) { recuerda = false; pintar(); }
        antesAtencion = at;
    });
    // recargar la página no pierde lo que falta guardar (web/recarga.ts)
    recarga.enUso(() => { const c = campoDe(); return !!c && c.value !== guardado; });
}
