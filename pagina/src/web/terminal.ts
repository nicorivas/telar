// La terminal de un hilo: xterm.js conectado por WebSocket a `telar mirar` en un PTY de la máquina (`/pty`,
// telar.terminal); la de un hilo de otra máquina, reenviada por la página de aquí a la de allá. Abajo, una caja
// para escribirle sin el viaje de ida y vuelta de cada tecla (lo escrito va entero al apretar ⏎). Se dibuja en un
// elemento de la página; sus estilos, en media/css/terminal.css (con @scope, en `.v-terminal`).
//
// xterm.js lo sirve telar.api_web en `/estatico/xterm` (copiado de node_modules, y guardado una semana en el
// navegador): se carga una vez, la primera vez que se abre una terminal.

import type { Terminal } from '@xterm/xterm';
import type { FitAddon } from '@xterm/addon-fit';

import { conEco } from '../navegador/eco/entrada';
import { enlazarTerminal } from './rutas-agente';
import type { RutasVista, Vista } from './vistas-hilo';

declare global {
    interface Window {
        Terminal?: typeof Terminal;
        FitAddon?: { FitAddon: typeof FitAddon };
        /** la terminal que se mira, y su eco: para revisarlos desde la consola (el buffer, `__eco.estado()`) */
        __terminal?: Terminal;
        __eco?: ReturnType<typeof conEco>;
    }
}

const XTERM = '/estatico/xterm';
let cargando: Promise<void> | undefined;

/** xterm.js, su addon-fit y su CSS, una sola vez. */
function cargarXterm(): Promise<void> {
    cargando ??= new Promise((listo, falla) => {
        const css = document.createElement('link');
        css.rel = 'stylesheet'; css.href = `${XTERM}/xterm.css`;
        document.head.appendChild(css);
        const script = (src: string) => new Promise<void>((ok, mal) => {
            const s = document.createElement('script');
            s.src = src; s.onload = () => ok(); s.onerror = () => mal(new Error(`no pude cargar ${src}`));
            document.head.appendChild(s);
        });
        script(`${XTERM}/xterm.js`).then(() => script(`${XTERM}/addon-fit.js`)).then(listo, falla);
    });
    return cargando;
}

/** La dirección de un WebSocket de esta página (`/pty?…`). */
function enchufe(ruta: string): string {
    const u = new URL(ruta, location.href);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    return u.href;
}

export function montar(raiz: HTMLElement, rutas: RutasVista): Vista {
    raiz.classList.add('v-terminal');
    raiz.innerHTML = '<div class="caja"><canvas class="fondo" aria-hidden="true"></canvas><div class="t"></div></div>'
        + '<form class="escribir"><textarea rows="1" placeholder="escríbele al hilo · ⏎ envía, ⇧⏎ línea nueva"></textarea>'
        + '<span class="ayuda" title="con la caja vacía, ⏎ ⎋ ↑ ↓ van directo a la terminal; un clic en la terminal teclea en ella">vacía: ⏎ ⎋ ↑↓ directo</span></form>';
    let cerrada = false;
    let deshacer: (() => void)[] = [];
    let term: Terminal | undefined, eco: ReturnType<typeof conEco> | undefined;
    const vista: Vista = {
        mostrada: () => {
            if (!term) return;
            window.__terminal = term; window.__eco = eco;
            // al volver a esta terminal, se escribe en ella (con el eco, sin esperar); la caja queda a un clic. En
            // un celular no: el teclado en pantalla taparía la mitad
            if (!document.body.classList.contains('angosto')) term.focus();
        },
        cerrar: () => { cerrada = true; for (const f of deshacer) f(); deshacer = []; term?.dispose(); },
    };
    cargarXterm().then(() => {
        if (cerrada) return;
        const t = arrancar(raiz, rutas);
        term = t.term; eco = t.eco; deshacer = t.deshacer;
        if (!raiz.hidden) vista.mostrada?.();
    }, e => {
        raiz.querySelector('.t')!.textContent = `telar: ${(e as Error).message}`;
    });
    return vista;
}

/** La terminal ya con xterm cargado: su tamaño, su conexión, la caja de abajo y el fondo. Devuelve lo que hay
 *  que deshacer al cerrarla. */
function arrancar(raiz: HTMLElement, rutas: RutasVista): { term: Terminal; eco: ReturnType<typeof conEco>; deshacer: (() => void)[] } {
    const deshacer: (() => void)[] = [];
    const escuchar = (donde: EventTarget, evento: string, f: () => void) => {
        donde.addEventListener(evento, f);
        deshacer.push(() => donde.removeEventListener(evento, f));
    };
    // los colores, de los tokens (media/css/tokens.css): los mismos del resto de la página
    const css = getComputedStyle(document.documentElement);
    const t = (nombre: string) => css.getPropertyValue(`--${nombre}`).trim();
    // sin parpadeo: Claude Code dibuja su propio cursor, y uno que además parpadea molesta al escribir
    const term = new window.Terminal!({ fontFamily: t('letra') || 'Menlo, monospace', fontSize: parseInt(t('tam'), 10) || 13, cursorBlink: false, allowProposedApi: false,
        theme: { background: t('bg'), foreground: t('fg'), cursor: t('cursor'), selectionBackground: t('negro'),
            black: t('negro'), red: t('rojo'), green: t('verde'), yellow: t('amarillo'), blue: t('azul'), magenta: t('magenta'), cyan: t('cian'), white: t('blanco'),
            brightBlack: t('dim'), brightRed: t('rojo'), brightGreen: t('verde'), brightYellow: t('amarillo'), brightBlue: t('azul'), brightMagenta: t('magenta'), brightCyan: t('cian'), brightWhite: t('blanco-claro') } });
    const fit = new window.FitAddon!.FitAddon(); term.loadAddon(fit);
    // el eco (como mosh): lo tecleado en la terminal aparece al tiro, tenue, hasta que el servidor lo muestra
    // (src/navegador/eco). Lo que llega pasa por él, y le avisa lo que se teclea
    const eco = conEco(term);
    const caja = raiz.querySelector<HTMLElement>('.caja')!, marco = raiz.querySelector<HTMLElement>('.t')!;
    marco.textContent = '';
    term.open(marco);
    const { hilo, maquina } = rutas;
    // las rutas que escribe el agente, como enlaces al visor (en la máquina del hilo)
    const enlaces = enlazarTerminal(term, rutas);
    deshacer.push(() => enlaces.dispose());

    // el tamaño: todo el alto, y de ancho lo que quepa hasta COLUMNAS (más ancho se lee mal), centrada. La ventana
    // del hilo toma este tamaño (la vista se lo da a tmux), así que no sobra nada que rellenar
    let COLUMNAS = 130;
    try { COLUMNAS = Number(localStorage.getItem('telar.columnas')) || COLUMNAS; } catch { /* sin almacén */ }
    const celda = () => {
        const d = (term as unknown as { _core?: { _renderService?: { dimensions?: { css?: { cell?: { width: number; height: number } } } } } })._core?._renderService?.dimensions;
        const c = d?.css?.cell;
        if (c?.width && c.height) return c;
        const p = fit.proposeDimensions();   // sin medidas todavía: las de lo que propondría llenar todo
        return p ? { width: (caja.clientWidth - 24) / p.cols, height: caja.clientHeight / p.rows } : null;
    };
    let ws: WebSocket | null = null;
    const ajustar = () => {
        // escondida (otra vista, otro hilo) mide 0: no se toca el tamaño (si no, la ventana del hilo quedaba de
        // 20×5 para todos); al volver a verse, el ResizeObserver la mide de nuevo y se redibuja
        if (!caja.clientWidth || !caja.clientHeight) return;
        const c = celda();
        if (!c) return;
        const arriba = parseFloat(getComputedStyle(marco).paddingTop) || 0, barra = 14;
        const cols = Math.max(20, Math.min(COLUMNAS, Math.floor((caja.clientWidth - barra - 2 * c.width) / c.width)));
        const rows = Math.max(5, Math.floor((caja.clientHeight - arriba) / c.height));
        marco.style.width = `${Math.ceil(cols * c.width + barra)}px`;
        if (cols !== term.cols || rows !== term.rows) {
            term.resize(cols, rows);
            if (ws?.readyState === 1) ws.send(JSON.stringify({ r: [cols, rows] }));
        } else {
            term.refresh(0, term.rows - 1);   // vuelve a verse con el mismo tamaño: se redibuja igual
        }
    };
    ajustar();
    deshacer.push(fondo(raiz, raiz.querySelector<HTMLCanvasElement>('.fondo')!, t));

    // cada conexión abre una vista nueva del hilo, con el tamaño de ahora
    const direccion = () => enchufe(`/pty?hilo=${encodeURIComponent(hilo)}&cols=${term.cols}&rows=${term.rows}`
        + (maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''));
    // si la conexión se corta (el laptop durmió, cambió la red, se reinició telar), se reconecta sola: al segundo, y
    // después cada vez más espaciado, hasta cada 15 s; al volver a la pestaña o a la red, al tiro
    const esperas = [1000, 2000, 5000, 10000, 15000];
    let intento = 0, pendiente = 0, conectada = false, cerrada = false;
    // para desarrollar (docs/desarrollar.md): localStorage['telar.latencia'] = ms simula esa latencia, la mitad a la
    // ida y la mitad a la vuelta (probar el eco sin depender de la red)
    let simulada = 0;
    try { simulada = Number(localStorage.getItem('telar.latencia')) || 0; } catch { /* sin almacén */ }
    const luego = (f: () => void) => { if (simulada > 0) setTimeout(f, simulada / 2); else f(); };
    const conectar = () => {
        clearTimeout(pendiente); pendiente = 0;
        if (cerrada || (ws && ws.readyState <= 1)) return;
        const nuevo = new WebSocket(direccion());
        ws = nuevo;
        nuevo.onopen = () => {
            // la vista nueva redibuja la pantalla entera: lo de antes se borra para que no quede mezclado
            if (intento) { term.reset(); eco.reiniciar(); }
            intento = 0; conectada = true;
        };
        nuevo.onmessage = e => { luego(() => eco.escribir(e.data as string)); };
        nuevo.onclose = () => {
            if (ws !== nuevo || cerrada) return;
            if (conectada) term.write('\r\n\x1b[2m[se cortó la conexión con la terminal: reconectando…]\x1b[0m');
            conectada = false;
            pendiente = window.setTimeout(conectar, esperas[Math.min(intento++, esperas.length - 1)]);
        };
    };
    conectar();
    deshacer.push(() => { cerrada = true; clearTimeout(pendiente); ws?.close(); ws = null; });
    escuchar(document, 'visibilitychange', () => { if (!document.hidden && !conectada) { intento = 0; conectar(); } });
    escuchar(window, 'online', () => { if (!conectada) { intento = 0; conectar(); } });
    const teclear = (d: string) => { luego(() => { if (ws?.readyState === 1) ws.send(JSON.stringify({ d })); }); };
    term.onData(d => { eco.tecleado(d); teclear(d); });

    // la caja, a un clic: se escribe aquí entero, sin que Claude redibuje con cada letra; ⏎ lo manda como un
    // pegado, y después un ⏎. Con la caja vacía, ⏎ ⎋ ↑ ↓ van directo (los diálogos de Claude, interrumpirlo)
    const texto = raiz.querySelector<HTMLTextAreaElement>('textarea')!;
    const crecer = () => { texto.style.height = 'auto'; texto.style.height = `${texto.scrollHeight}px`; ajustar(); };
    texto.addEventListener('input', crecer);
    texto.addEventListener('keydown', e => {
        if (e.isComposing) return;
        const vacia = texto.value === '';
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (vacia) { teclear('\r'); return; }
            teclear(`\u001b[200~${texto.value.replace(/\s+$/, '')}\u001b[201~`);
            setTimeout(() => teclear('\r'), 120);
            texto.value = ''; crecer();
        } else if (e.key === 'Escape') {
            e.preventDefault(); teclear('\u001b');
        } else if (vacia && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
            e.preventDefault(); teclear(e.key === 'ArrowUp' ? '\u001b[A' : '\u001b[B');
        }
    });
    const observador = new ResizeObserver(ajustar);
    observador.observe(caja);
    deshacer.push(() => observador.disconnect());
    return { term, eco, deshacer };
}

/** Alrededor de la terminal, un telar muy tenue: la urdimbre quieta y, de vez en cuando, un hilo de trama que
 *  cruza despacio y se apaga. Quieto si quien mira pidió menos movimiento, y sin dibujar mientras no se ve.
 *  Devuelve cómo pararlo. */
function fondo(raiz: HTMLElement, lienzo: HTMLCanvasElement, t: (nombre: string) => string): () => void {
    const ctx = lienzo.getContext('2d')!;
    const muestra = document.createElement('i'); raiz.appendChild(muestra);
    const color = (n: string) => { muestra.style.color = `var(--${n})`; return getComputedStyle(muestra).color; };
    const URDIMBRE = color('linea'), PALETA = ['violeta', 'azul', 'cian', 'verde', 'amarillo', 'magenta'].map(color);
    muestra.remove();
    let cw = 8, ch = 16, cols = 0, filas = 0;
    let tramas: { y: number; dir: number; x: number; vida: number; color: string }[] = [];
    const medir = () => {
        const dpr = window.devicePixelRatio || 1;
        lienzo.width = lienzo.clientWidth * dpr; lienzo.height = lienzo.clientHeight * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.font = `${t('tam') || '13px'} ${t('letra') || 'monospace'}`; ctx.textBaseline = 'top';
        cw = Math.ceil(ctx.measureText('─').width); ch = Math.ceil(cw * 1.9);
        cols = Math.ceil(lienzo.clientWidth / cw); filas = Math.ceil(lienzo.clientHeight / ch);
    };
    const dibujar = () => {
        ctx.clearRect(0, 0, lienzo.clientWidth, lienzo.clientHeight);
        ctx.globalAlpha = 0.45; ctx.fillStyle = URDIMBRE;
        for (let y = 0; y < filas; y++) for (let c = 0; c < cols; c += 2) ctx.fillText('│', c * cw, y * ch);
        for (const h of tramas) {
            ctx.globalAlpha = Math.max(0, 0.5 - h.vida / 160); ctx.fillStyle = h.color;
            const desde = h.dir > 0 ? 0 : h.x, hasta = h.dir > 0 ? h.x : cols;
            for (let c = desde; c < hasta; c++) ctx.fillText(c % 2 ? '─' : '┼', c * cw, h.y * ch);
        }
        ctx.globalAlpha = 1;
    };
    const paso = () => {
        if (raiz.hidden || document.hidden) return;
        if (Math.random() < 0.02 && tramas.length < 3) {
            const dir = Math.random() < 0.5 ? 1 : -1;
            tramas.push({ y: Math.floor(Math.random() * filas), dir, x: dir > 0 ? 0 : cols, vida: 0, color: PALETA[Math.floor(Math.random() * PALETA.length)] });
        }
        for (const h of tramas) { h.x += h.dir; h.vida++; }
        tramas = tramas.filter(h => h.vida < 160);   // cruza mientras se apaga
        dibujar();
    };
    const observador = new ResizeObserver(() => { medir(); dibujar(); });
    observador.observe(lienzo);
    medir(); dibujar();
    const reloj = matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : window.setInterval(paso, 90);
    return () => { clearInterval(reloj); observador.disconnect(); };
}
