// Un hilo leído como conversación (la vista del celular): los últimos turnos (`/api/hilos/leer`, releídos cada
// pocos segundos), una caja para escribirle y las teclas para contestarle una pregunta (⏎, ⎋, 1-3, ↑↓). A un
// hilo de aquí, lo escrito va por el mismo canal que la terminal (`/pty`, una vista de `telar mirar`): es teclear
// en el hilo, con la misma llave. A uno de otra máquina, como mensaje de la persona (`/api/mensajes`, por el bus).
// Se dibuja en un elemento de la página; sus estilos, en media/css/conversacion.css (con @scope, en
// `.v-conversacion`).

import MarkdownIt from 'markdown-it';
import { modelo } from '../modelo';
import { C, I } from './iconos';
import * as ui from './ui';
import { atenderClics, enlazar } from './rutas-agente';
import type { RutasVista, Vista } from './vistas-hilo';

interface Mensaje { quien: string; texto?: string }
interface Leido { error?: string; fuente?: string; texto?: string; turnos?: Mensaje[][]; total_turnos?: number; recortado?: boolean }

/** el markdown del agente (el HTML que traiga se escapa) */
const md = new MarkdownIt({ html: false, linkify: true });

const QUIEN: Record<string, string> = { usuario: 'tú', agente: 'agente', herramienta: '·' };

/** Un turno «tuyo» que no escribió la persona: lo que tecleó el nodo para que entrara un mensaje del bus («↯ mensaje
 *  nuevo · mensaje de Mobile: …», telar.casilla `aviso`). Su etiqueta dice de quién vino; null si es de la persona (o
 *  «tu persona: …», lo que ella mandó desde otra parte). */
function delBus(texto: string): string | null {
    if (!texto.startsWith('↯ mensaje nuevo')) return null;
    const m = /^↯ mensaje nuevo · (?:(?:mensaje|encargo) de (.+?)|(tu persona)): /.exec(texto);
    if (m?.[2]) return null;
    return m?.[1] ? `↯ ${m[1]}` : '↯ mensaje';
}
/** las teclas de abajo: lo que mandan a la terminal */
/** Las teclas de abajo, para lo que el agente pregunta con opciones: lo que muestran, lo que envían y su ayuda. */
const TECLAS: [string, string, string][] = [['⏎', '\r', 'enter: acepta lo marcado'], ['⎋', '\u001b', 'escape: cancela o interrumpe'],
    ['1', '1', 'la opción 1'], ['2', '2', 'la opción 2'], ['3', '3', 'la opción 3'], ['↑', '\u001b[A', 'subir'], ['↓', '\u001b[B', 'bajar']];

/** Lo que se le escribió y todavía no aparece en la conversación: su texto y en qué va. */
interface Pendiente { texto: string; desde: number }
/** Para reconocer lo escrito en la conversación: sin espacios de más y sin el aviso del bus. */
const comparable = (t: string) => t.replace(/\s+/g, ' ').trim().slice(0, 60);

function el<K extends keyof HTMLElementTagNameMap>(tag: K, clase = '', texto?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto !== undefined) e.textContent = texto;
    return e;
}

/** La dirección de un WebSocket de esta página (`/pty?…`). */
function enchufe(ruta: string): string {
    const u = new URL(ruta, location.href);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.href;
}

export function montar(raiz: HTMLElement, { hilo, maquina }: RutasVista): Vista {
    // un hilo de otra máquina se lee por la API y se le escribe como mensaje (por el bus): sin terminal, no hay
    // teclas que apretar
    const porMensaje = !!maquina;
    raiz.classList.add('v-conversacion');
    raiz.innerHTML = '<main class="turnos"><p class="nada">leyendo…</p></main><footer><div class="teclas"></div>'
        + `<form class="escribir"><textarea rows="1" placeholder="escríbele · ⏎ envía · ⇧⏎ línea nueva"></textarea>`
        + `<button type="submit" class="enviar" title="enviar (⏎)"><span class="i">${I.enviar}</span></button></form>`
        + '<p class="dijo" aria-live="polite"></p></footer>';
    const $ = <T extends HTMLElement>(s: string) => raiz.querySelector<T>(s)!;
    const turnos = $('.turnos'), texto = $<HTMLTextAreaElement>('textarea'), dijo = $('.dijo'), form = $<HTMLFormElement>('.escribir');
    const boton = $<HTMLButtonElement>('button.enviar');
    // la caja crece con lo escrito, hasta ocho líneas; vacía, una
    const crecer = () => { texto.style.height = 'auto'; texto.style.height = `${Math.min(texto.scrollHeight, 8 * parseFloat(getComputedStyle(texto).lineHeight || '20') + 16)}px`; };
    texto.addEventListener('input', () => { crecer(); boton.classList.toggle('listo', !!texto.value.trim()); });

    /** En qué va lo último que se envió, abajo de la caja: su ícono y su color dicen si va, si llegó o si falló. */
    const decir = (estado: '' | 'enviando' | 'llego' | 'cola' | 'error', que = '') => {
        dijo.className = `dijo ${estado}`;
        dijo.textContent = '';
        if (!estado) return;
        const ic = el('span', 'i', { enviando: I.viaja, llego: I.hecha, cola: I.reloj, error: I.alerta }[estado]);
        dijo.append(ic, document.createTextNode(` ${que}`));
    };
    let pendiente: Pendiente | null = null;
    /** Lo enviado, al final de la conversación y tenue, hasta que aparece de verdad en ella. */
    const ponerPendiente = () => {
        turnos.querySelector('.msj.pendiente')?.remove();
        if (!pendiente) return;
        const f = el('div', 'msj usuario pendiente');
        f.append(el('span', 'quien', 'tú · enviando'), el('div', 'cuerpo', pendiente.texto));
        turnos.appendChild(f);
    };
    const teclas = $('.teclas');
    teclas.hidden = porMensaje;

    // archivado o cerrado: no hay agente que lea, así que no hay caja para escribirle; en su lugar, retomarlo
    const h = maquina ? undefined : modelo.porNombre(hilo);
    if (h && (!h.vivo || h.archivado)) {
        form.hidden = true;
        teclas.hidden = true;
        const aviso = document.createElement('div');
        aviso.className = 'dormido';
        const que = document.createElement('span');
        que.textContent = `${h.archivado ? 'archivado' : 'cerrado'}: esto es lo que conversó, sin el agente abierto`;
        const retomar = document.createElement('a');
        retomar.style.setProperty('--c', `var(--${C.hecho})`);
        const ic = document.createElement('span'); ic.className = 'i'; ic.textContent = I.retomar;
        retomar.append(ic, document.createTextNode(' retomar'));
        retomar.title = 'abre el agente con esta conversación, en su terminal';
        retomar.addEventListener('click', () => void ui.orden('telar.retomar', { hilo }));
        aviso.append(que, retomar);
        form.before(aviso);
    }

    atenderClics(turnos, { hilo, maquina });
    const abajo = () => turnos.scrollHeight - turnos.scrollTop - turnos.clientHeight < 40;
    let ultimo = '', leido = false;
    const pintar = (d: Leido) => {
        const firma = JSON.stringify(d);
        if (firma === ultimo) return;
        ultimo = firma;
        const seguir = abajo() || !leido;
        turnos.textContent = '';
        if (d.error) {
            const sinConversacion = /no tiene conversación/.test(d.error);
            turnos.appendChild(el('p', 'nada', sinConversacion
                ? 'este hilo no dejó una conversación en esta máquina (se cerró sin mensajes, o la tuvo en otra)' : d.error));
            return;
        }
        if (d.fuente === 'panel') turnos.appendChild(el('pre', 'panel', d.texto ?? ''));
        else {
            if (d.recortado || (d.total_turnos ?? 0) > (d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'turnos anteriores sin mostrar'));
            for (const turno of d.turnos ?? []) {
                const t = el('section', 'turno');
                for (const m of turno) {
                    const bus = m.quien === 'usuario' ? delBus(m.texto ?? '') : null;
                    const f = el('div', `msj ${bus ? 'bus' : m.quien}`);
                    if (m.quien !== 'herramienta') f.appendChild(el('span', 'quien', bus ?? QUIEN[m.quien] ?? m.quien));
                    const cuerpo = el('div', m.quien === 'agente' ? 'cuerpo md' : 'cuerpo', m.quien === 'agente' ? undefined : m.texto ?? '');
                    if (m.quien === 'agente') cuerpo.innerHTML = md.render(m.texto ?? '');
                    f.appendChild(cuerpo);
                    t.appendChild(f);
                }
                turnos.appendChild(t);
            }
            if (!(d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'todavía no hay conversación'));
        }
        // lo enviado: si ya aparece entre lo que dijo la persona, llegó; si no, sigue abajo, tenue
        if (pendiente) {
            const buscado = comparable(pendiente.texto);
            const llego = (d.turnos ?? []).some(t => t.some(m => m.quien === 'usuario' && comparable(m.texto ?? '').includes(buscado)));
            if (llego) { pendiente = null; decir('llego', 'llegó: está en la conversación'); }
            else if (Date.now() - pendiente.desde > 25000) decir('cola', 'enviado; todavía no aparece (si el agente está trabajando, lo lee al terminar)');
        }
        ponerPendiente();
        // las rutas que escribió el agente, como enlaces al visor
        enlazar(turnos, true, hilo);
        leido = true;
        if (seguir || pendiente) turnos.scrollTop = turnos.scrollHeight;
    };

    let leyendo = false, pronto = 0;
    const leer = async () => {
        if (leyendo) return;
        leyendo = true;
        try {
            const r = await fetch(`/api/hilos/leer?hilo=${encodeURIComponent(hilo)}&ultimos=8${maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''}`, { cache: 'no-store' });
            const d = await r.json() as Leido & { detail?: string };
            pintar(r.ok ? d : { error: d.detail || `la API respondió ${r.status}` });
        } catch { /* sin conexión: se reintenta en la vuelta */ }
        leyendo = false;
    };
    // cada 4 s mientras se mira (1,5 justo después de escribirle); escondida, cada 20
    let espera = 0;
    const vuelta = () => {
        void leer();
        espera = window.setTimeout(vuelta, Date.now() < pronto ? 1500 : (document.hidden || raiz.hidden ? 20000 : 4000));
    };
    vuelta();

    // escribir: una vista de la terminal del hilo, abierta la primera vez que hace falta
    let ws: WebSocket | null = null;
    const cola: string[] = [];
    const canal = () => {
        if (ws && ws.readyState <= 1) return ws;
        const nuevo = new WebSocket(enchufe(`/pty?hilo=${encodeURIComponent(hilo)}&cols=100&rows=30`));
        let abrio = false;
        nuevo.onopen = () => { abrio = true; for (const d of cola.splice(0)) nuevo.send(JSON.stringify({ d })); };
        nuevo.onclose = () => {
            if (ws === nuevo) ws = null;
            // se cerró sin haber abierto: lo que esperaba en la cola no salió
            if (!abrio && cola.length) {
                cola.length = 0;
                if (pendiente) { texto.value ||= pendiente.texto; crecer(); pendiente = null; ponerPendiente(); }
                decir('error', 'no se pudo abrir su terminal: no se envió (quedó en la caja)');
            }
        };
        ws = nuevo;
        return nuevo;
    };
    const teclear = (d: string) => {
        const c = canal();
        if (c.readyState === 1) c.send(JSON.stringify({ d })); else cola.push(d);
        pronto = Date.now() + 20000;
    };
    // ⏎ envía; ⇧⏎ es una línea nueva (y mientras se compone una letra con acento, ⏎ es de la composición)
    texto.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    form.addEventListener('submit', async e => {
        e.preventDefault();
        const t = texto.value.replace(/\s+$/, '');
        if (!t) return;
        pendiente = { texto: t, desde: Date.now() };
        texto.value = ''; crecer(); boton.classList.remove('listo');
        decir('enviando', 'enviando…');
        ponerPendiente();
        turnos.scrollTop = turnos.scrollHeight;
        if (porMensaje) {
            // por el bus, como la persona; le llega al hilo al terminar su turno (o al tiro si espera)
            try {
                const r = await fetch('/api/mensajes', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ para: hilo, texto: t, tipo: 'persona', de: 'el panel' }),
                });
                const d = await r.json() as { detail?: string; despertado?: string; sin_despertar?: string };
                if (r.ok) { decir('cola', d.despertado ? `estaba ${d.despertado}: lo retomé con su conversación, y lo lee ahora`
                    : d.sin_despertar ? `en su casilla; no está abierto y no pude retomarlo (${d.sin_despertar}): le llega cuando lo retomes`
                    : 'en su casilla: le llega al terminar su turno, o al tiro si te espera'); pronto = Date.now() + 30000; setTimeout(() => void leer(), 3000); }
                else { texto.value = t; crecer(); pendiente = null; ponerPendiente(); decir('error', `no se envió: ${d.detail || `telar respondió ${r.status}`}`); }
            } catch {
                texto.value = t; crecer(); pendiente = null; ponerPendiente();
                decir('error', 'sin conexión con telar: no se envió (quedó en la caja)');
            }
            return;
        }
        // como un pegado (para que un salto de línea no envíe antes de tiempo), y después ⏎
        teclear(`\u001b[200~${t}\u001b[201~`);
        setTimeout(() => teclear('\r'), 120);
        setTimeout(() => void leer(), 1200);
    });
    for (const [nombre, envia, ayuda] of TECLAS) {
        const b = el('button', '', nombre);
        b.type = 'button';
        b.title = ayuda;
        b.addEventListener('click', () => { teclear(envia); setTimeout(() => void leer(), 800); });
        teclas.appendChild(b);
    }

    return {
        mostrada: () => void leer(),
        cerrar: () => { clearTimeout(espera); ws?.close(); ws = null; },
    };
}
