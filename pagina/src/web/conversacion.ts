// Un hilo leído como conversación (la vista del celular): los últimos turnos (`/api/hilos/leer`, releídos cada
// pocos segundos), una caja para escribirle y las teclas para contestarle una pregunta (⏎, ⎋, 1-3, ↑↓). A un
// hilo de aquí, lo escrito va por el mismo canal que la terminal (`/pty`, una vista de `telar mirar`): es teclear
// en el hilo, con la misma llave. A uno de otra máquina, como mensaje de la persona (`/api/mensajes`, por el bus).
// Se dibuja en un elemento de la página; sus estilos, en media/css/conversacion.css (con @scope, en
// `.v-conversacion`).

import MarkdownIt from 'markdown-it';
import { atenderClics, enlazar } from './rutas-agente';
import type { RutasVista, Vista } from './vistas-hilo';

interface Mensaje { quien: string; texto?: string }
interface Leido { error?: string; fuente?: string; texto?: string; turnos?: Mensaje[][]; total_turnos?: number; recortado?: boolean }

/** el markdown del agente (el HTML que traiga se escapa) */
const md = new MarkdownIt({ html: false, linkify: true });

const QUIEN: Record<string, string> = { usuario: 'tú', agente: 'agente', herramienta: '·' };
/** las teclas de abajo: lo que mandan a la terminal */
const TECLAS: [string, string][] = [['⏎', '\r'], ['⎋', '\u001b'], ['1', '1'], ['2', '2'], ['3', '3'], ['↑', '\u001b[A'], ['↓', '\u001b[B']];

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
        + '<form class="escribir"><textarea rows="2"></textarea><button type="submit">enviar</button></form><p class="dijo nada"></p></footer>';
    const $ = <T extends HTMLElement>(s: string) => raiz.querySelector<T>(s)!;
    const turnos = $('.turnos'), texto = $<HTMLTextAreaElement>('textarea'), dijo = $('.dijo'), form = $<HTMLFormElement>('.escribir');
    const teclas = $('.teclas');
    teclas.hidden = porMensaje;

    atenderClics(turnos, { hilo, maquina });
    const abajo = () => turnos.scrollHeight - turnos.scrollTop - turnos.clientHeight < 40;
    let ultimo = '', leido = false;
    const pintar = (d: Leido) => {
        const firma = JSON.stringify(d);
        if (firma === ultimo) return;
        ultimo = firma;
        const seguir = abajo() || !leido;
        turnos.textContent = '';
        if (d.error) { turnos.appendChild(el('p', 'nada', d.error)); return; }
        if (d.fuente === 'panel') turnos.appendChild(el('pre', 'panel', d.texto ?? ''));
        else {
            if (d.recortado || (d.total_turnos ?? 0) > (d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'turnos anteriores sin mostrar'));
            for (const turno of d.turnos ?? []) {
                const t = el('section', 'turno');
                for (const m of turno) {
                    const f = el('div', `msj ${m.quien}`);
                    if (m.quien !== 'herramienta') f.appendChild(el('span', 'quien', QUIEN[m.quien] ?? m.quien));
                    const cuerpo = el('div', m.quien === 'agente' ? 'cuerpo md' : 'cuerpo', m.quien === 'agente' ? undefined : m.texto ?? '');
                    if (m.quien === 'agente') cuerpo.innerHTML = md.render(m.texto ?? '');
                    f.appendChild(cuerpo);
                    t.appendChild(f);
                }
                turnos.appendChild(t);
            }
            if (!(d.turnos ?? []).length) turnos.appendChild(el('p', 'nada', 'todavía no hay conversación'));
        }
        // las rutas que escribió el agente, como enlaces al visor
        enlazar(turnos);
        leido = true;
        if (seguir) turnos.scrollTop = turnos.scrollHeight;
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
        nuevo.onopen = () => { for (const d of cola.splice(0)) nuevo.send(JSON.stringify({ d })); };
        nuevo.onclose = () => { if (ws === nuevo) ws = null; };
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
        if (porMensaje) {
            // por el bus, como la persona; le llega al hilo al terminar su turno (o al tiro si espera)
            try {
                const r = await fetch('/api/mensajes', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ para: hilo, texto: t, tipo: 'persona', de: 'el panel' }),
                });
                const d = await r.json() as { detail?: string };
                dijo.textContent = r.ok ? 'enviado: le llega al terminar su turno, o al tiro si te espera' : (d.detail || 'no llegó');
                if (r.ok) { texto.value = ''; pronto = Date.now() + 30000; setTimeout(() => void leer(), 3000); }
            } catch {
                dijo.textContent = 'sin conexión con telar';
            }
            return;
        }
        // como un pegado (para que un salto de línea no envíe antes de tiempo), y después ⏎
        teclear(`\u001b[200~${t}\u001b[201~`);
        setTimeout(() => teclear('\r'), 120);
        texto.value = '';
        setTimeout(() => void leer(), 1200);
    });
    for (const [nombre, envia] of TECLAS) {
        const b = el('button', '', nombre);
        b.type = 'button';
        b.addEventListener('click', () => { teclear(envia); setTimeout(() => void leer(), 800); });
        teclas.appendChild(b);
    }

    return {
        mostrada: () => void leer(),
        cerrar: () => { clearTimeout(espera); ws?.close(); ws = null; },
    };
}
