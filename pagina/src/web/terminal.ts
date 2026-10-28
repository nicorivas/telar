// La terminal de un hilo: xterm.js conectado por WebSocket a `telar mirar` en un PTY de la máquina (`/pty`,
// telar.terminal); la de un hilo de otra máquina, reenviada por la página de aquí a la de allá. Abajo, una caja
// para escribirle sin el viaje de ida y vuelta de cada tecla (lo escrito va entero al apretar ⏎). Se dibuja en un
// elemento de la página; sus estilos, en media/css/terminal.css (con @scope, en `.v-terminal`).
//
// Un archivo arrastrado y soltado aquí deja su ruta en el chat, como en la terminal de VS Code: en la caja, donde
// está el cursor; en la terminal, pegada, sin ⏎. Si el hilo es de otra máquina, o el arrastre no trae la ruta (solo
// el archivo), el archivo va antes a la carpeta de entrada de la máquina del hilo y se escribe la ruta de allá
// (`recibirArrastres`; lo que se lee del arrastre, en web/arrastre.ts).
//
// xterm.js lo sirve telar.api_web en `/estatico/xterm` (copiado de node_modules, y guardado una semana en el
// navegador): se carga una vez, la primera vez que se abre una terminal.

import { alCambiar, aspecto, fondoDe, leer } from './aspecto-terminal';
import type { Terminal } from '@xterm/xterm';
import type { FitAddon } from '@xterm/addon-fit';

import * as cli from '../cli';
import { modelo } from '../modelo';
import { conEco } from '../navegador/eco/entrada';
import { insertar, juntar, rutasDe, tamano, traeArchivos } from './arrastre';
import { abrirHipervinculo, enlazarTerminal, maquinaDe } from './rutas-agente';
import * as ui from './ui';
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
    raiz.innerHTML = '<div class="caja"><div class="t"></div></div>'
        + '<form class="escribir"><div class="soltar" hidden></div><textarea rows="1" placeholder="escríbele al hilo · ⏎ envía, ⇧⏎ línea nueva"></textarea>'
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

/** Lo que un programa de la terminal manda al portapapeles con OSC 52 («c;<base64>»): el texto, o nada si es una
 *  consulta («?»). Las consultas no se contestan: nada de lo que corre en la terminal lee el portapapeles. */
export function textoOsc52(datos: string): string | undefined {
    const b64 = datos.slice(datos.indexOf(';') + 1);
    if (!datos.includes(';') || !b64 || b64 === '?') return undefined;
    try { return new TextDecoder().decode(Uint8Array.from(atob(b64), c => c.charCodeAt(0))); } catch { return undefined; }
}

/** Escribe en el portapapeles de la persona. La página suele servirse por http (no es un «contexto seguro»), y ahí
 *  el navegador no da `navigator.clipboard`: se copia como lo haría ⌘C, desde un campo escondido, lo que el
 *  navegador permite solo poco después de un clic o una tecla de la persona. */
async function alPortapapeles(texto: string): Promise<boolean> {
    if (window.isSecureContext && navigator.clipboard) {
        try { await navigator.clipboard.writeText(texto); return true; } catch { /* sigue con el campo */ }
    }
    const antes = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const campo = document.createElement('textarea');
    campo.value = texto;
    campo.setAttribute('readonly', '');
    campo.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
    document.body.appendChild(campo);
    campo.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    campo.remove();
    antes?.focus();
    return ok;
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
    // sin parpadeo: Claude Code dibuja su propio cursor, y uno que además parpadea molesta al escribir. Un hipervínculo
    // (OSC 8) a una web abre una pestaña nueva, sin el confirm() que xterm pone de fábrica; uno file://, el visor.
    // ⌥ y arrastrar selecciona aquí aunque el programa (el tmux de otra máquina) tenga el mouse
    const term = new window.Terminal!({ fontFamily: t('letra') || 'Menlo, monospace', fontSize: parseInt(t('tam'), 10) || 13, cursorBlink: false, allowProposedApi: false,
        macOptionClickForcesSelection: true,
        linkHandler: { activate: (_e, uri) => abrirHipervinculo(uri, rutas), allowNonHttpProtocols: true },
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

    // lo que copia el programa de la terminal, al portapapeles de la persona. En un hilo de otra máquina el mouse lo
    // tiene el tmux de allá (o Claude Code, que selecciona él): lo que se selecciona arrastrando queda allá, y vuelve
    // con OSC 52. Si el navegador no deja copiarlo (por http, solo unos segundos después del clic que empezó a
    // arrastrar, y un párrafo largo más el viaje al servidor tarda más), se pregunta con un botón: apretarlo es un
    // clic nuevo, y entonces sí. Mientras, también vale ⌘C en la terminal
    let porCopiar = '', preguntando = false;
    const copiado = (texto: string) => ui.estado(`copiado: ${texto.length} ${texto.length === 1 ? 'carácter' : 'caracteres'}`, 2500);
    const preguntar = async () => {
        if (preguntando) return;
        preguntando = true;
        const muestra = porCopiar.replace(/\s+/g, ' ').trim();
        const r = await ui.info(`Lo que seleccionaste (${porCopiar.length} caracteres) no pasó solo al portapapeles: el navegador`
            + ` solo deja copiar justo después de un clic.\n«${muestra.length > 70 ? `${muestra.slice(0, 70)}…` : muestra}»`, 'Copiar');
        preguntando = false;
        if (r === 'Copiar' && porCopiar && await alPortapapeles(porCopiar)) { copiado(porCopiar); porCopiar = ''; }
        term.focus();
    };
    const osc52 = term.parser.registerOscHandler(52, datos => {
        const texto = textoOsc52(datos);
        if (!texto) return true;
        void alPortapapeles(texto).then(ok => {
            if (ok) { porCopiar = ''; copiado(texto); return; }
            porCopiar = texto;
            void preguntar();
        });
        return true;
    });
    deshacer.push(() => osc52.dispose());
    const alCopiar = (e: ClipboardEvent) => {
        if (!porCopiar || term.hasSelection() || !e.clipboardData) return;
        e.clipboardData.setData('text/plain', porCopiar);
        e.preventDefault(); e.stopImmediatePropagation();
        porCopiar = '';
        ui.estado('copiado', 2500);
    };
    marco.addEventListener('copy', alCopiar, true);
    deshacer.push(() => marco.removeEventListener('copy', alCopiar, true));

    // el tamaño: todo el alto, y de ancho lo que quepa hasta las columnas de `[terminal]` (130 de fábrica: más ancho
    // se lee mal; 0, todo), donde diga su posición. La ventana del hilo toma este tamaño (la vista se lo da a tmux),
    // así que no sobra nada que rellenar
    const columnas = () => aspecto().columnas || 10000;
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
        const cols = Math.max(20, Math.min(columnas(), Math.floor((caja.clientWidth - barra - 2 * c.width) / c.width)));
        const rows = Math.max(5, Math.floor((caja.clientHeight - arriba) / c.height));
        marco.style.width = `${Math.ceil(cols * c.width + barra)}px`;
        // una línea en cada lado donde entre la terminal y lo de al lado hay fondo: pegada a la barra de hilos, a la
        // ficha o al borde, no (la barra y la ficha ya traen la suya, y dos líneas juntas se ven gruesas)
        const izq = marco.offsetLeft > 1, der = marco.offsetLeft + marco.offsetWidth < caja.clientWidth - 1;
        marco.classList.toggle('borde-izq', izq);
        marco.classList.toggle('borde-der', der);
        if (cols !== term.cols || rows !== term.rows) {
            term.resize(cols, rows);
            if (ws?.readyState === 1) ws.send(JSON.stringify({ r: [cols, rows] }));
        } else {
            term.refresh(0, term.rows - 1);   // vuelve a verse con el mismo tamaño: se redibuja igual
            // y se le recuerda a tmux, por si otra vista del mismo hilo lo dejó en otro tamaño
            if (reenviar && ws?.readyState === 1) ws.send(JSON.stringify({ r: [cols, rows] }));
        }
        reenviar = false;
    };
    // medir de nuevo cuando la disposición se asienta: en el cuadro siguiente y otra vez un poco después. La caja
    // avisa sola cuando cambia de tamaño (su ResizeObserver), pero no siempre llega: la pestaña estaba atrás cuando
    // apareció la barra de Chrome, o el modo cambió varias cosas a la vez
    let reenviar = false, cuadro = 0;
    const asentar = () => {
        reenviar = true;
        cancelAnimationFrame(cuadro);
        cuadro = requestAnimationFrame(() => { ajustar(); setTimeout(() => { reenviar = true; ajustar(); }, 250); });
    };
    escuchar(window, 'resize', asentar);
    if (window.visualViewport) escuchar(window.visualViewport, 'resize', asentar);
    escuchar(document, 'visibilitychange', () => { if (!document.hidden) asentar(); });
    escuchar(document, 'fullscreenchange', asentar);
    ajustar();
    // la posición y el fondo, de `[terminal]`; cuando ⚙ terminal los cambia, se vuelven a aplicar aquí mismo
    let pararFondo: (() => void) | undefined;
    let dibujado = '';
    const aplicar = () => {
        const a = aspecto();
        caja.style.justifyContent = { izquierda: 'flex-start', centro: 'center', derecha: 'flex-end' }[a.posicion] ?? 'center';
        const f = fondoDe(a);
        const clave = `${f.tipo}|${f.valor}`;
        if (clave !== dibujado) {
            dibujado = clave;
            pararFondo?.(); pararFondo = undefined;
            caja.querySelector('.fondo')?.remove();
            caja.style.background = '';
            if (f.tipo === 'telar') {
                const lienzo = document.createElement('canvas');
                lienzo.className = 'fondo'; lienzo.setAttribute('aria-hidden', 'true');
                caja.prepend(lienzo);
                pararFondo = fondo(raiz, lienzo, t);
            } else if (f.tipo === 'color') {
                caja.style.background = f.valor;
            } else if (f.tipo === 'imagen') {
                caja.style.background = `center / cover no-repeat url("${f.valor.replace(/"/g, '%22')}")`;
            } else if (f.tipo === 'modulo') {
                // la página de un módulo, aislada: sin el origen de esta (no ve la página ni la API) y sin clics
                const hoja = document.createElement('iframe');
                hoja.className = 'fondo'; hoja.setAttribute('aria-hidden', 'true'); hoja.tabIndex = -1;
                hoja.setAttribute('sandbox', 'allow-scripts');
                hoja.src = f.valor;
                caja.prepend(hoja);
            }
        }
        ajustar();
    };
    aplicar();
    deshacer.push(alCambiar(() => { aplicar(); asentar(); }), () => pararFondo?.());
    void leer();

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
    // un archivo soltado: en la caja, la ruta donde está el cursor (se sigue escribiendo y se manda con ⏎); en la
    // terminal, como un pegado pero sin el ⏎ (quien escribe decide cuándo mandarlo), con un espacio para seguir
    deshacer.push(recibirArrastres(raiz, rutas, {
        caja: s => {
            const r = insertar(texto.value, texto.selectionStart, texto.selectionEnd, s);
            texto.value = r.valor; texto.setSelectionRange(r.cursor, r.cursor); crecer(); texto.focus();
        },
        terminal: s => { teclear(`\u001b[200~${s} \u001b[201~`); term.focus(); },
    }));
    const observador = new ResizeObserver(ajustar);
    observador.observe(caja);
    deshacer.push(() => observador.disconnect());
    return { term, eco, deshacer };
}

/** Lo que se arrastra a la vista y se suelta. Si el arrastre trae la ruta, se usa; si no, se pregunta y se sube;
 *  nunca se adivina una ruta ni se navega al archivo (lo que el navegador hace de fábrica). La ruta va a `caja` si
 *  se soltó sobre la caja de abajo, y a `terminal` si sobre la terminal. Con el hilo en otra máquina, la ruta de
 *  aquí no le sirve: el archivo se copia a su carpeta de entrada (`POST /api/archivos/entrada`) y se escribe la de
 *  allá. El aviso (lo que se copia, o la pregunta de si subir) va en una franja sobre la caja. Devuelve cómo
 *  dejar de escuchar. */
function recibirArrastres(raiz: HTMLElement, rutas: RutasVista, a: { caja(s: string): void; terminal(s: string): void }): () => void {
    const form = raiz.querySelector<HTMLFormElement>('form.escribir')!;
    const franja = raiz.querySelector<HTMLElement>('.soltar')!;
    // mientras copia o sube, otro archivo soltado espera (una pregunta sin contestar, en cambio, la reemplaza el nuevo)
    let ocupada = false;
    const avisar = (html: string, tenue: boolean) => {
        franja.innerHTML = html; franja.classList.toggle('tenue', tenue); franja.hidden = false;
    };
    const cerrar = () => { franja.hidden = true; franja.textContent = ''; ocupada = false; };
    const esc = (t: string) => t.replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);
    /** Las rutas de allá de cada archivo, en orden; si uno falla, se dice y se sigue con los demás. */
    const llevar = async (pedidos: (() => Promise<cli.Respuesta<cli.JsonEntrada>>)[]): Promise<string[]> => {
        const hechas: string[] = [];
        for (const pedir of pedidos) {
            const r = await pedir();
            if (r.datos) hechas.push(r.datos.ruta);
            else void ui.falla(`no se copió: ${r.error ?? 'sin respuesta'}`);
        }
        return hechas;
    };

    const sobre = (e: DragEvent) => {
        if (!e.dataTransfer || !traeArchivos(e.dataTransfer.types)) return;
        e.preventDefault();   // sin esto no hay drop, y el navegador abre el archivo
        e.dataTransfer.dropEffect = 'copy';
    };
    const soltar = (e: DragEvent) => {
        const dt = e.dataTransfer;
        if (!dt) return;
        const enCaja = form.contains(e.target as Node);
        const dar = enCaja ? a.caja : a.terminal;
        const traidas = rutasDe(dt), archivos = [...dt.files];
        if (!traidas.length && !archivos.length) {
            // un texto o un enlace, no un archivo: en la caja lo pone el navegador; en la terminal, pegado (y no se
            // navega al enlace)
            if (enCaja) return;
            e.preventDefault();
            const t = dt.getData('text/plain').trim();
            if (t) dar(t);
            return;
        }
        e.preventDefault();
        if (ocupada) { void ui.aviso('todavía estoy con lo anterior: suéltalo de nuevo cuando termine'); return; }
        const maquina = maquinaDe(rutas), alla = maquina && maquina !== modelo.aqui ? maquina : '';
        if (traidas.length && !alla) { dar(juntar(traidas)); return; }
        if (traidas.length) {
            ocupada = true;
            // la ruta es de aquí y el hilo, de otra máquina: se copia allá, y mientras, un aviso tenue
            const nombres = traidas.map(r => r.split(/[\\/]/).pop()).join(', ');
            avisar(`copiando ${esc(nombres)} a ~/telar-entrada de ${esc(alla)}…`, true);
            void llevar(traidas.map(r => () => cli.entradaPorRuta(rutas.hilo, alla, r)))
                .then(hechas => { if (hechas.length) dar(juntar(hechas)); }).finally(cerrar);
            return;
        }
        // solo el archivo, sin su ruta: se pregunta antes de subirlo (puede ser grande, y queda guardado allá)
        const destino = `~/telar-entrada de ${alla || modelo.aqui || 'esta máquina'}`;
        const total = archivos.reduce((n, f) => n + f.size, 0);
        const que = archivos.length === 1 ? esc(archivos[0].name) : `${archivos.length} archivos (${esc(archivos.map(f => f.name).join(', '))})`;
        avisar(`<span>¿guardar ${que} · ${tamano(total)} en ${esc(destino)}?</span>`
            + '<button type="button" class="si">guardar</button><button type="button" class="no">no</button>', false);
        franja.querySelector<HTMLButtonElement>('.si')!.focus();
        franja.querySelector('.no')!.addEventListener('click', cerrar);
        franja.querySelector('.si')!.addEventListener('click', () => {
            ocupada = true;
            avisar(`subiendo ${que} a ${esc(destino)}…`, true);
            void llevar(archivos.map(f => () => cli.entradaSubida(rutas.hilo, alla, f)))
                .then(hechas => { if (hechas.length) dar(juntar(hechas)); }).finally(cerrar);
        });
    };
    raiz.addEventListener('dragover', sobre);
    raiz.addEventListener('drop', soltar);
    return () => { raiz.removeEventListener('dragover', sobre); raiz.removeEventListener('drop', soltar); };
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
