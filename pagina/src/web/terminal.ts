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
import { C, I } from './iconos';
import { coloresTerminal } from '../componentes/temas';
import * as guardado from './guardado';
import * as avisos from './avisos';
import * as ui from './ui';
import * as portapapeles from './portapapeles';
import * as anchos from './anchos';
import type { RutasVista, Vista } from './vistas-hilo';
import { boton, cancelar } from '../componentes/boton';
import { fueraDe, panelFuera, type MaquinaAlcance } from './alcance';
import { dondeVive, type Donde } from './donde-vive';
import { teclasDeBotones } from './botonera';

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

/** La terminal ya con xterm cargado: su tamaño, su conexión, la caja de abajo y el fondo. Devuelve lo que hay
 *  que deshacer al cerrarla. */
function arrancar(raiz: HTMLElement, rutas: RutasVista): { term: Terminal; eco: ReturnType<typeof conEco>; deshacer: (() => void)[] } {
    const deshacer: (() => void)[] = [];
    const escuchar = (donde: EventTarget, evento: string, f: () => void) => {
        donde.addEventListener(evento, f);
        deshacer.push(() => donde.removeEventListener(evento, f));
    };
    // los colores, de los tokens del tema puesto (componentes/temas.ts): los mismos del resto de la página
    const css = getComputedStyle(document.documentElement);
    const t = (nombre: string) => css.getPropertyValue(`--${nombre}`).trim();
    // sin parpadeo: Claude Code dibuja su propio cursor, y uno que además parpadea molesta al escribir. Un hipervínculo
    // (OSC 8) a una web abre una pestaña nueva, sin el confirm() que xterm pone de fábrica; uno file://, el visor.
    // ⌥ y arrastrar selecciona aquí aunque el programa (el tmux de otra máquina) tenga el mouse
    const term = new window.Terminal!({ fontFamily: t('letra') || 'Menlo, monospace', fontSize: parseInt(t('tam'), 10) || 13, cursorBlink: false, allowProposedApi: false,
        macOptionClickForcesSelection: true,
        linkHandler: { activate: (_e, uri) => abrirHipervinculo(uri, rutas), allowNonHttpProtocols: true },
        theme: coloresTerminal() });
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

    // lo que copia el programa de la terminal, al portapapeles de la persona (web/portapapeles.ts). En un hilo de otra
    // máquina el mouse lo tiene el tmux de allá (o Claude Code, que selecciona él): lo que se selecciona arrastrando queda
    // allá, y vuelve con OSC 52, en un mensaje del WebSocket. Eso ya no es el gesto de la persona: Chrome lo deja copiar
    // unos segundos después del clic; Safari no. Por eso, al soltar el mouse después de arrastrar (o en un doble o triple
    // clic, que en tmux copian la palabra o la línea), se arma una escritura que espera lo que llegue (en contexto seguro:
    // https; Safari la acepta). Si nada de eso alcanza (Safari por http, un arrastre de más de unos segundos en Chrome),
    // un aviso con un botón que copia en su mismo clic. Mientras, también vale ⌘C en la terminal
    let porCopiar = '', preguntando = false, armada: portapapeles.Armada | undefined, desde: { x: number; y: number } | undefined;
    const copiado = (texto: string) => ui.estado(`copiado: ${texto.length} ${texto.length === 1 ? 'carácter' : 'caracteres'}`, 2500);
    const alBajar = (e: MouseEvent) => { desde = e.button === 0 && !e.altKey ? { x: e.clientX, y: e.clientY } : undefined; };
    const alSoltar = (e: MouseEvent) => {
        const d = desde;
        desde = undefined;
        if (!d || e.button !== 0) return;
        const arrastro = Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 3;
        if (!arrastro && e.detail < 2) return;
        armada?.soltar();
        armada = portapapeles.armar();
    };
    marco.addEventListener('mousedown', alBajar, true);
    document.addEventListener('mouseup', alSoltar, true);
    deshacer.push(() => { marco.removeEventListener('mousedown', alBajar, true); document.removeEventListener('mouseup', alSoltar, true); armada?.soltar(); });
    const preguntar = async () => {
        if (preguntando) return;
        preguntando = true;
        await ui.pedirCopiar(porCopiar, `Lo que seleccionaste (${porCopiar.length} caracteres) volvió del servidor y falta pasarlo al`
            + ' portapapeles: aprieta Copiar (o ⏎).', () => { copiado(porCopiar); porCopiar = ''; return true; });
        preguntando = false;
        term.focus();
    };
    const osc52 = term.parser.registerOscHandler(52, datos => {
        const texto = textoOsc52(datos);
        if (!texto) return true;
        const a = armada;
        armada = undefined;
        void portapapeles.copiarLoQueLlega(texto, a).then(ok => {
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

    // el tamaño: todo el alto, y de ancho lo que quepa hasta las columnas elegidas arrastrando su borde en esta pantalla
    // (web/anchos.ts), o si no, las de `[terminal]` (130 de fábrica: más ancho se lee mal; 0, todo), donde diga su
    // posición. La ventana del hilo toma este tamaño (la vista se lo da a tmux), así que no sobra nada que rellenar
    const barra = 14;   // la de desplazamiento de xterm, dentro del marco
    const borde = anchos.montarTerminal({ ...anchos.dePagina(), caja, marco, barra,
        celda: () => celda()?.width ?? null, posicion: () => aspecto().posicion });
    const columnas = () => (borde.columnas() ?? aspecto().columnas) || 10000;
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
        const arriba = parseFloat(getComputedStyle(marco).paddingTop) || 0;
        const cols = Math.max(20, Math.min(columnas(), anchos.caben(caja.clientWidth, c.width, barra)));
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
    // la posición y el fondo, de `[terminal]`; cuando ⚙ terminal los cambia, se vuelven a aplicar aquí mismo. Sin
    // fondo propio («ninguno»), lo de alrededor es el fondo del tema (terminal.css)
    let dibujado = '';
    const aplicar = () => {
        const a = aspecto();
        caja.style.justifyContent = { izquierda: 'flex-start', centro: 'center', derecha: 'flex-end' }[a.posicion] ?? 'center';
        borde.colocar();   // la franja del ancho, en el borde que no está pegado: el izquierdo si va a la derecha
        const f = fondoDe(a);
        const clave = `${f.tipo}|${f.valor}`;
        if (clave !== dibujado) {
            dibujado = clave;
            caja.querySelector('.fondo')?.remove();
            caja.style.background = '';
            if (f.tipo === 'color') {
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
    // otro tema (el modo puesto): los colores nuevos, sin cerrarla
    let colores = JSON.stringify(term.options.theme);
    deshacer.push(alCambiar(() => {
        const nuevos = coloresTerminal();
        if (JSON.stringify(nuevos) !== colores) { colores = JSON.stringify(nuevos); term.options.theme = nuevos; }
        aplicar(); asentar();
    }));
    void leer();

    // cada conexión abre una vista nueva del hilo, con el tamaño de ahora
    const direccion = () => enchufe(`/pty?hilo=${encodeURIComponent(hilo)}&cols=${term.cols}&rows=${term.rows}`
        + (maquina ? `&maquina=${encodeURIComponent(maquina)}` : ''));
    // si la conexión se corta (el laptop durmió, cambió la red, se reinició telar), se reconecta sola: al segundo, y
    // después cada vez más espaciado, hasta cada 15 s; al volver a la pestaña o a la red, al tiro
    const esperas = [1000, 2000, 5000, 10000, 15000];
    let intento = 0, pendiente = 0, conectada = false, cerrada = false;
    // si la terminal no se pudo abrir (el servidor cierra con 4001 y el motivo: el hilo no existe aquí, no tiene
    // ventana…), reconectar no lo arregla: se dice en un cuadro, una vez, en vez de que el error aparezca y se
    // borre cada segundo. Un telar de antes no manda el código: dos cierres seguidos al poco de abrir
    // cuentan igual (lo último que escribió es el motivo)
    let abierta = 0, rapidas = 0, cola = '', esperandoVentana = 0, reintentosAqui = 0;
    // cortada y reconectándose: lo dice la franja de avisos (web/avisos.ts), si no volvió en unos segundos (un reinicio de
    // telar, que dura menos, no se dice), y se va sola al volver. Sin conexión con telar no se dice: lo dice el de la
    // conexión
    const claveAviso = `terminal:${maquina ? `${maquina}|` : ''}${hilo}`;
    let porAvisar = 0;
    const avisarCorte = () => {
        clearTimeout(porAvisar);
        porAvisar = window.setTimeout(() => {
            if (conectada || cerrada) return;
            avisos.poner({ clave: claveAviso, nivel: 'falla', icono: I.desconectado, conConexion: true, cuando: 'hace',
                texto: `la terminal de «${hilo}»${maquina ? ` (${maquina})` : ''} se cortó`,
                detalle: 'Se reconecta sola, cada vez más espaciado (hasta cada 15 s).',
                ir: { texto: `el hilo ${hilo}`, hacer: () => void (maquina ? ui.orden('telar.irRemoto', `${maquina}|${hilo}`) : ui.orden('telar.ir', { hilo })) },
                acciones: [{ id: 'reconectar', texto: 'reconectar ahora', hacer: () => { intento = 0; conectar(); } }] });
        }, 4000);
    };
    const yaVolvio = () => { clearTimeout(porAvisar); avisos.quitar(claveAviso); };
    let aviso: HTMLElement | undefined;
    const quitarAviso = () => { aviso?.remove(); aviso = undefined; };
    /** Dónde vive ahora (web/donde-vive.ts): la lista de aquí, su registro en el bus (su dueño) y, sin él, las fotos de
     *  las otras máquinas. */
    const dondeAhora = async (): Promise<Donde> => {
        await modelo.sondear(true).catch(() => undefined);
        const [e, r] = await Promise.all([cli.espejos().catch(() => undefined), cli.registro(hilo).catch(() => undefined)]);
        return dondeVive(hilo, { aqui: modelo.aqui, local: modelo.porNombre(hilo), otras: e?.datos?.espejos ?? [],
            registro: r?.datos, mirando: maquina });
    };
    /** Un aviso tenue en la terminal mientras se espera, y otro intento en `ms`. */
    const esperar = (texto: string, ms = 3000) => {
        esperandoVentana++;
        term.reset(); eco.reiniciar();
        term.write(`\x1b[2m[${texto}]\x1b[0m`);
        rapidas = 0;
        pendiente = window.setTimeout(conectar, ms);
    };
    const mostrarFalla = async (motivo: string) => {
        // antes de dar por fallado, dónde vive ahora: se llevó a otra máquina (o volvió), y la página lo sigue sola; su
        // ventana de aquí se está reabriendo, o va en camino, y se espera. Lo de antes («vive en telar», «retómalo»)
        // venía de la lista de aquí sola: tras llevarlo, recordaba la máquina de donde salió
        if (esperandoVentana < 30) {
            const d = await dondeAhora();
            if (cerrada) return;
            // abierto aquí con su ventana (recién llegó, o fue un tropiezo): la de aquí; si se miraba en otra, se pasa a esta
            if (d.a === 'aqui' && maquina) { cerrada = true; void ui.orden('telar.ir', hilo); return; }
            // (unas pocas veces: si sigue sin abrir, la falla es otra y se dice abajo)
            if (d.a === 'aqui' && reintentosAqui < 3) { reintentosAqui++; esperar(`«${hilo}» está abierto aquí: conectándose…`, 1200); return; }
            // vive en otra máquina: allá (si es la que se miraba, la falla es de allá: se dice abajo)
            if (d.a === 'alla' && d.maquina !== maquina) { cerrada = true; void ui.orden('telar.irRemoto', `${d.maquina}|${hilo}`); return; }
            // un hilo de otra máquina sin su ventana de aquí (la que corre la conexión con allá): se cayó y el nodo la
            // reabre en su vuelta; allá todavía lo tiene. Se espera, en vez de dar por fallado algo que se arregla solo
            if (d.a === 'espejo' && !maquina) { esperar(`«${hilo}» vive en ${d.maquina} y su ventana de aquí se está reabriendo: esperándola…`); return; }
            if (d.a === 'viajando') { esperar(`«${hilo}» va en camino a ${d.maquina}: esperándolo…`); return; }
            // archivarlo (o cerrarlo) mientras se mira, también desde adentro («archívate»), es lo de siempre, no una
            // falla: se pasa a su conversación, que es como se ve un hilo archivado (con «retomar»)
            if (d.a === 'cerrado' && !maquina) {
                // sin archivar, puede estar abriéndose (uno que llega de otra máquina queda anotado un momento antes de
                // tener su ventana): un par de veces se espera
                if (!modelo.porNombre(hilo)?.archivado && reintentosAqui < 2) {
                    reintentosAqui++; esperar(`«${hilo}» no tiene ventana aquí: esperando un momento, por si se está abriendo…`, 2000); return;
                }
                cerrada = true; void ui.orden('telar.ir', hilo); return;
            }
        }
        quitarAviso();
        term.reset(); eco.reiniciar();
        // uno de una máquina fuera de línea (telar.alcance): no es una falla que se arregle aquí. Se dice desde cuándo, lo
        // que le espera en cola, y lo que se puede hacer igual: despertarlo cuando vuelva, o escribirle
        if (maquina && await mostrarFuera()) return;
        aviso = document.createElement('div');
        aviso.className = 'no-abre';
        const titulo = document.createElement('div');
        titulo.className = 'titulo';
        const ico = document.createElement('span'); ico.className = 'i'; ico.textContent = I.alerta;
        titulo.append(ico, document.createTextNode(` no se pudo abrir «${hilo}»${maquina ? ` en ${maquina}` : ''}`));
        const que = document.createElement('div'); que.className = 'motivo'; que.textContent = motivo;
        // lo que se puede hacer: la banda de botones (componentes/boton.ts), con el ícono de cada uno en el lugar de la tecla
        const botones = document.createElement('div'); botones.className = 'botonera';
        const poner = (nombre: string, icono: string, color: string, hacer: () => void) => {
            botones.insertAdjacentHTML('beforeend', boton({ texto: nombre, icono, color }));
            botones.lastElementChild!.addEventListener('click', hacer);
        };
        poner('reintentar', I.retomar, C.ir, () => { quitarAviso(); intento = 0; rapidas = 0; conectar(); });
        // lo que suele arreglarlo: retomarlo (si está dormido aquí) o volver a la lista, donde está lo que sí existe
        if (!maquina) poner('retomar', I.ver, C.hecho, () => { quitarAviso(); void ui.orden('telar.retomar', hilo); });
        aviso.append(titulo, que, botones);
        caja.appendChild(aviso);
    };
    /** El cuadro de una máquina fuera de línea (web/alcance.ts), si lo está: true si lo puso. */
    const mostrarFuera = async (): Promise<boolean> => {
        const r = await cli.espejos().catch(() => undefined);
        const otras: MaquinaAlcance[] = (r?.datos?.espejos ?? []).map(e => ({ ...e, fuera: !e.en_linea && !!r?.datos?.al_dia }));
        const m = fueraDe(maquina, otras);
        if (!m || cerrada) return false;
        quitarAviso();
        aviso = document.createElement('div');
        aviso.className = 'no-abre fuera';
        aviso.innerHTML = panelFuera(hilo, m);
        aviso.addEventListener('click', async e => {
            const b = (e.target as HTMLElement).closest<HTMLButtonElement>('button[data-accion]');
            if (!b || b.disabled) return;
            const que = b.dataset.accion;
            if (que === 'reintentar') { quitarAviso(); intento = 0; rapidas = 0; conectar(); return; }
            if (que === 'escribirle') { window.telar?.vista?.('conv'); return; }
            if (que === 'despertar') {
                b.disabled = true;
                const d = await cli.despertar(hilo, maquina, { cola: true });
                ui.estado(d.datos?.hecho || d.error || 'no se pudo', 8000);
                void mostrarFuera();
            }
        });
        caja.appendChild(aviso);
        return true;
    };
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
            intento = 0; conectada = true; abierta = Date.now(); cola = '';
            yaVolvio();
            // abrió de verdad (no se cerró al tiro): la espera de su ventana, si la hubo, terminó
            window.setTimeout(() => { if (conectada && ws === nuevo) esperandoVentana = reintentosAqui = 0; }, 3000);
        };
        nuevo.onmessage = e => {
            const d = e.data as string;
            if (Date.now() - abierta < 3000) cola = (cola + d).slice(-600);
            luego(() => eco.escribir(d));
        };
        nuevo.onclose = e => {
            if (ws !== nuevo || cerrada) return;
            const breve = conectada && Date.now() - abierta < 3000;
            rapidas = breve ? rapidas + 1 : 0;
            if (e.code === 4001 || rapidas >= 2) {
                conectada = false;
                // eslint-disable-next-line no-control-regex
                const ultima = cola.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '').split(/\r?\n/).map(x => x.trim()).filter(Boolean).pop() ?? '';
                yaVolvio();
                void mostrarFalla((e.reason || ultima || 'la terminal se cerró al abrirse').replace(/^telar: /, ''));
                return;
            }
            // la primera vez que se cierra al tiro no se dice nada: si vuelve a pasar es una falla, no un corte
            if (conectada && !breve) avisarCorte();
            conectada = false;
            pendiente = window.setTimeout(conectar, esperas[Math.min(intento++, esperas.length - 1)]);
        };
    };
    conectar();
    deshacer.push(() => { cerrada = true; clearTimeout(pendiente); ws?.close(); ws = null; quitarAviso(); yaVolvio(); });
    escuchar(document, 'visibilitychange', () => { if (!document.hidden && !conectada && !aviso) { intento = 0; conectar(); } });
    escuchar(window, 'online', () => { if (!conectada && !aviso) { intento = 0; conectar(); } });
    const teclear = (d: string) => { luego(() => { if (ws?.readyState === 1) ws.send(JSON.stringify({ d })); }); };
    term.onData(d => { eco.tecleado(d); teclear(d); });

    // la caja, a un clic: se escribe aquí entero, sin que Claude redibuje con cada letra; ⏎ lo manda como un
    // pegado, y después un ⏎. Con la caja vacía, ⏎ ⎋ ↑ ↓ van directo (los diálogos de Claude, interrumpirlo)
    const texto = raiz.querySelector<HTMLTextAreaElement>('textarea')!;
    const crecer = () => { texto.style.height = 'auto'; texto.style.height = `${texto.scrollHeight}px`; ajustar(); };
    texto.addEventListener('input', crecer);
    // lo escrito y no mandado, de antes de recargar la página (web/guardado.ts)
    const escrito = guardado.caja(texto, `term:${maquina}|${hilo}`);
    deshacer.push(escrito.soltar);
    if (texto.value) requestAnimationFrame(crecer);
    texto.addEventListener('keydown', e => {
        if (e.isComposing) return;
        const vacia = texto.value === '';
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (vacia) { teclear('\r'); return; }
            teclear(`\u001b[200~${texto.value.replace(/\s+$/, '')}\u001b[201~`);
            setTimeout(() => teclear('\r'), 120);
            texto.value = ''; escrito.anotar(); crecer();
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
            texto.value = r.valor; texto.setSelectionRange(r.cursor, r.cursor); escrito.anotar(); crecer(); texto.focus();
        },
        terminal: s => { teclear(`\u001b[200~${s} \u001b[201~`); term.focus(); },
    }));
    // mientras se arrastra el ancho de la barra, de la ficha o de la terminal misma (web/anchos.ts) no se mide: un resize a tmux por píxel. Al
    // soltar llega una vez anchos.EVENTO, con el ancho ya puesto, y se mide entonces (si el aviso del observador llega
    // después, encuentra el mismo tamaño y no manda nada)
    const observador = new ResizeObserver(() => { if (!anchos.arrastrando()) ajustar(); });
    escuchar(window, anchos.EVENTO, ajustar);
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
    // las teclas de sus botones (⏎ el del foco, ⎋ no): la franja no es una ventana, así que ⎋ también es suyo
    const soltarTeclas = teclasDeBotones(franja);
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
        // la pregunta, en la banda de botones (componentes/boton.ts): «⏎ guardar» con el foco, «⎋ no» al último
        avisar(`<div class="botonera"><span class="botonera-izq">¿guardar ${que} · ${tamano(total)} en ${esc(destino)}?</span>`
            + boton({ texto: 'guardar', datos: { soltar: 'si' }, color: C.cambiar, tecla: '⏎', ayuda: 'subirlo y dejar su ruta en el chat' })
            + boton({ ...cancelar('no', null), datos: { soltar: 'no' } }) + '</div>', false);
        franja.querySelector<HTMLButtonElement>('[data-soltar="si"]')!.focus();
        franja.querySelector('[data-soltar="no"]')!.addEventListener('click', cerrar);
        franja.querySelector('[data-soltar="si"]')!.addEventListener('click', () => {
            ocupada = true;
            avisar(`subiendo ${que} a ${esc(destino)}…`, true);
            void llevar(archivos.map(f => () => cli.entradaSubida(rutas.hilo, alla, f)))
                .then(hechas => { if (hechas.length) dar(juntar(hechas)); }).finally(cerrar);
        });
    };
    raiz.addEventListener('dragover', sobre);
    raiz.addEventListener('drop', soltar);
    return () => { raiz.removeEventListener('dragover', sobre); raiz.removeEventListener('drop', soltar); soltarTeclas(); };
}
