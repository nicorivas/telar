// El dashboard de telar, corriendo en el navegador: el `PanelHoy` de vistas/hoy.ts, sin Node. Lo que
// en el panel en Node (retirado el 19-oct-2026) hacía su servidor (hablar con la CLI, mandar la página por
// un WebSocket, preguntarle cosas a quien mira) aquí lo hace esta página:
//
//   - la API, por `fetch` a `/api` (la misma de `telar serve`, detrás de la llave de esta página);
//   - el dashboard se dibuja en un iframe, con el mismo guion de interfaz que en Node (web/pagina.ts) pero
//     hablándole a esta página por postMessage;
//   - los avisos, campos y menús que pide el dashboard (su anfitrión) los pone esta página, encima de todo
//     (web/interfaz.ts).
//
// Se empaqueta con esbuild (scripts/navegador.mjs) en src/telar/web/app.js, que sirve `telar serve --web`.

// primero: los estilos (las vistas arman su CSS al cargarse, y tienen que encontrarlos)
import './estilos';

import MarkdownIt from 'markdown-it';

import { type Anfitrion, type Opcion, type OpcionesAviso, usar } from '../anfitrion';
import * as cli from '../cli';
import { modelo } from '../modelo';
import { BarraHilos, type Guardado } from '../vistas/hilos';
import { crearOrdenes } from '../web/ordenes';
import type { AvisosSuperficie, CrearSuperficie, Superficie } from '../superficie';
import { PanelHoy } from '../vistas/hoy';
import { avisar, campo, elegir, type Nivel, preguntar } from '../web/interfaz';
import { montar as montarCarpeta } from '../web/carpeta';
import { montar as montarCompartir } from '../web/compartir';
import { SCRIPT_NAVEGADOR } from '../web/pagina';
import { type Vista, vista, VISTAS } from '../web/vistas-hilo';


// ── los ajustes: salen del servidor (/config) ──

const ajustes: Record<string, unknown> = {};
cli.usarAjustes(<T>(clave: string, porDefecto: T): T => (clave in ajustes ? ajustes[clave] as T : porDefecto));
void cli.config().then(r => {
    // la bandeja del equipo: la del servidor que sirve la página («aqui») o la de la máquina que diga
    if (r.datos?.equipo) { ajustes.equipoRemoto = r.datos.equipo; void modelo.leerEquipo(); }
});

// ── a la izquierda la barra (vistas/hilos.ts, sin marco); a la derecha, en marcos, el dashboard o un hilo ──

const marcos = () => document.getElementById('vistas')!;
let marco: HTMLIFrameElement | undefined;       // el del dashboard
let avisosPanel: AvisosSuperficie | undefined;
let actual = 'dashboard';

/** Lo que se ve a la derecha: un marco (el dashboard, las vistas de un hilo que todavía lo tienen) o una vista
 *  dibujada directo en la página (la carpeta, compartir), con su clave en `data-p`. */
const vistas = () => [...marcos().children] as HTMLElement[];

/** Las vistas de un hilo dibujadas en la página (la lectura, la conversación), por su clave: se les avisa al
 *  volver a verse. */
const montadas = new Map<string, Vista>();

/** Una vista dibujada directo en la página: un elemento que su módulo llena (web/carpeta.ts, web/compartir.ts,
 *  las vistas de un hilo). */
function nuevaVista(clave: string): HTMLElement {
    const s = document.createElement('section');
    s.dataset.p = clave;
    marcos().appendChild(s);
    return s;
}

function nuevoMarco(clave: string, donde: HTMLElement): HTMLIFrameElement {
    const f = document.createElement('iframe');
    f.dataset.p = clave;
    f.title = clave;
    f.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals allow-downloads');
    donde.appendChild(f);
    return f;
}

function a(f: HTMLIFrameElement | undefined, m: unknown): void {
    f?.contentWindow?.postMessage({ __telarPadre: m }, location.origin);
}

/** Una página con el guion que le da `acquireVsCodeApi` (web/pagina.ts), con el mismo nonce del CSP que pone
 *  `estilo.marco`. */
function conInterfaz(pagina: string): string {
    const nonce = /'nonce-([^']+)'/.exec(pagina)?.[1] ?? '';
    return pagina.replace('<body', `<script nonce="${nonce}">${SCRIPT_NAVEGADOR}</script><body`);
}

window.addEventListener('message', e => {
    if (e.source !== marco?.contentWindow) return;
    if (typeof e.data?.__telarHijo !== 'string') return;
    let m: Record<string, unknown>;
    try { m = JSON.parse(e.data.__telarHijo); } catch { return; }
    avisosPanel?.mensaje(m);
});

const superficie: CrearSuperficie = avisos => {
    avisosPanel = avisos;
    const s: Superficie = {
        cspSource: "'self'",
        get visible() { return !document.hidden && !!marco && !marco.hidden; },
        get activa() { return document.hasFocus(); },
        html: p => {
            if (!marco) marco = nuevoMarco('dashboard', marcos());
            marco.srcdoc = conInterfaz(p);
        },
        enviar: m => a(marco, m),
        revelar: () => mostrar('dashboard'),
    };
    document.addEventListener('visibilitychange', () => avisos.cambio(!document.hidden, document.hasFocus()));
    return s;
};

/** Lo que la barra recuerda (el orden de cada grupo): en este navegador. */
const guardado: Guardado = {
    get: <T>(clave: string) => {
        try { return JSON.parse(localStorage.getItem(`telar.barra.${clave}`) ?? 'null') ?? undefined as T | undefined; } catch { return undefined; }
    },
    update: async (clave, valor) => { try { localStorage.setItem(`telar.barra.${clave}`, JSON.stringify(valor)); } catch { /* sin almacén */ } },
};

/** Cómo se ve un hilo: una de sus vistas (web/vistas-hilo.ts): la terminal, la lectura, la conversación. En
 *  pantalla ancha empieza en la terminal; en angosta, en la conversación; la barra de arriba del hilo (y ⌥T,
 *  ⌥L, ⌥C) cambian. */
const modo: Record<string, string> = {};
const angosto = () => document.body.classList.contains('angosto');
const esHilo = (que: string) => !(que === 'dashboard' || que === 'compartir' || que.startsWith('doc:') || que.startsWith('arch:'));
function forma(que: string): string {
    if (!esHilo(que)) return '';
    return modo[que] ?? (angosto() ? 'conv' : 'term');
}
/** las terminales que se miraron hace poco: cada una es una vista de tmux abierta, y se cierran las viejas */
const TOPE = 8;
const usadas: string[] = [];
/** Cierra una vista de un hilo (su conexión, sus lecturas) y la saca de la página. */
function cerrarVista(llave: string): void {
    montadas.get(llave)?.cerrar();
    montadas.delete(llave);
    vistas().find(x => x.dataset.p === llave)?.remove();
}

/** A la derecha: «dashboard», un hilo de aquí (su terminal o su conversación), «rem:<máquina>:<hilo>» (uno de
 *  otra máquina: su terminal reenviada, o su conversación por el bus), «doc:<hilo>» (su carpeta y su documento) o «compartir» (lo
 *  que el teléfono le compartió a la app: la página se abrió en /compartir). */
function mostrar(que: string): void {
    if (!que) return;
    actual = que;
    let f: HTMLElement | undefined;
    if (que === 'dashboard') {
        if (!hoy.panel) hoy.abrir();
        f = marco;
    } else {
        const como = forma(que), llave = como ? `${como}:${que}` : que;
        f = vistas().find(x => x.dataset.p === llave);
        if (que.startsWith('doc:') || que.startsWith('arch:') || que === 'compartir') {
            f ??= nuevaVista(llave);
            if (que === 'compartir') montarCompartir(f, location.search);
            else if (que.startsWith('arch:')) void montarCarpeta(f, '', que.slice(5), t => md.render(t));
            else void montarCarpeta(f, que.slice(4), '', t => md.render(t));
        } else if (!f) {
            const remoto = que.startsWith('rem:') ? que.slice(4) : '';
            const i = remoto.indexOf(':');
            const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
            f = nuevaVista(llave);
            montadas.set(llave, (vista(como) ?? VISTAS[0]).montar(f, { hilo, maquina }, () => cambiarVista('term')));
        }
        if (como === 'term') {
            const j = usadas.indexOf(llave);
            if (j >= 0) usadas.splice(j, 1);
            usadas.push(llave);
            while (usadas.length > TOPE) cerrarVista(usadas.shift()!);
        }
    }
    for (const x of vistas()) x.hidden = x !== f;
    pintarAcciones(que);
    // ya a la vista: la terminal toma el teclado, la lectura y la conversación se releen
    if (f && forma(que)) montadas.get(f.dataset.p ?? '')?.mostrada?.();
    // lo que se ve, como se nombra un hilo: «hilo» si es de esta máquina, «máquina:hilo» si es de otra (como
    // `scp máquina:ruta`; con la persona sería «nico@laptop:Telar»). Lo muestra la cabecera (indice.html)
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const nombre = remoto ? remoto
        : que.startsWith('doc:') ? `${que.slice(4)} · carpeta`
        : que.startsWith('arch:') ? relativa(que.slice(5)) : que;
    window.telar?.donde?.(que === 'dashboard' ? null : { texto: nombre, otraMaquina: !!remoto });
    document.title = que === 'dashboard' ? 'telar' : `${nombre} · telar`;
    document.body.classList.remove('en-lista');
    document.body.classList.add('en-detalle');
    // la barra marca lo que se ve
    barra.dashboardActivo = que === 'dashboard';
    barra.mostrado = que === 'dashboard' ? '' : que;
    barra.refrescar(true);
}

// ── lo que el dashboard le pide a la interfaz (su anfitrión) ──────────────────

function avisoCon(nivel: Nivel) {
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        if (!nombres.length) { avisar(texto, nivel); return undefined; }
        return preguntar(texto, nombres);
    };
}

const md = new MarkdownIt({ html: false, linkify: true });

const anfitrion: Anfitrion = {
    aviso: avisoCon('aviso'),
    falla: avisoCon('falla'),
    info: avisoCon('info'),
    estado: (texto, ms) => avisar(texto, 'info', ms ?? 4000),
    progreso: async (o, trabajo) => {
        if (!o.ventana) avisar(o.title, 'info', 2500);
        return trabajo();
    },
    campo: async o => {
        let problema = '';
        let valor = o.value ?? '';
        for (;;) {
            const r = await campo({ titulo: o.title, ayuda: o.prompt, placeholder: o.placeHolder, valor, password: o.password, problema });
            if (r === undefined) return undefined;
            problema = o.validateInput?.(r) ?? '';
            if (!problema) return r;
            valor = r;
        }
    },
    elegir: async <T extends Opcion>(opciones: T[], menu?: { title?: string; placeHolder?: string }) => {
        const i = await elegir(opciones, { titulo: menu?.title, placeholder: menu?.placeHolder });
        return i === undefined ? undefined : opciones[i];
    },
    abrirExterno: async url => { window.open(url, '_blank', 'noopener'); },
    // un archivo o una carpeta del repositorio: en la página (la vista de carpeta, `arch:<ruta>`), sin salir de
    // la raíz; lo que no es texto trae un enlace para bajarlo
    abrirArchivo: async ruta => { mostrar(`arch:${ruta}`); },
    mostrarCarpeta: async ruta => { mostrar(`arch:${ruta}`); },
    copiar: async texto => { try { await navigator.clipboard.writeText(texto); } catch { /* sin permiso */ } },
    markdown: async texto => md.render(texto),
    // ir a un hilo: telar lo crea o lo revive si hace falta (`telar ir`), y la página lo muestra a la derecha
    irAHilo: async (hilo, crear, remoto) => {
        const r = await cli.ir(hilo, !!crear, remoto ?? '');
        if (!r.ok) { avisar(`telar: ${r.err.trim() || `no pude ir a «${hilo}»`}`, 'falla'); return; }
        await modelo.sondear().catch(() => undefined);
        mostrar(remoto ? `rem:${remoto}:${hilo}` : hilo);
    },
    // «ir a la terminal» después de abrir un hilo o encargarle algo: el que quedó al frente en tmux (el que la
    // acción acaba de abrir), mostrado en la página
    mostrarTerminal: async () => {
        await modelo.sondear().catch(() => undefined);
        const activo = modelo.activo;
        if (activo) mostrar(activo.nombre);
    },
    orden: async (id, ...args) => {
        const f = ordenes[id];
        if (f) return f(...args);
        avisar(`«${id}» todavía no está en el navegador`, 'aviso');
        return undefined;
    },
};

// ── arrancar ──────────────────────────────────────────────────────────────────

usar(anfitrion);
const hoy = new PanelHoy();
hoy.crearSuperficie = superficie;
const barra = new BarraHilos();
barra.estado = guardado;
barra.dashboardActivo = true;
barra.mostrado = '';
const ordenes = crearOrdenes({ hoy, barra, anfitrion, mostrar });
barra.montar(document.getElementById('barra')!);
hoy.alCambiarFoco = () => {
    const app = hoy.appActual;
    if (barra.appActiva === app) return;
    barra.appActiva = app;
    barra.refrescar(true);
};
modelo.cambio.event(() => barra.refrescar());

// los hilos de otras máquinas (sus fotos): en HILOS, cada uno con su máquina; y el nombre de esta, para la
// columna ancha
void fetch('/api/salud', { cache: 'no-store' }).then(r => r.json()).then((s: { maquina?: string }) => {
    barra.aqui = s.maquina ?? ''; barra.refrescar(true);
}).catch(() => undefined);
const otras = async () => {
    const r = await cli.espejos().catch(() => undefined);
    const nuevas = (r?.datos?.espejos ?? []).filter(e => !e.error)
        .map(e => ({ nombre: e.nombre, en_linea: e.en_linea, edad: e.edad, hilos: e.hilos.filter(h => !h.remoto) }));
    if (JSON.stringify(nuevas) !== JSON.stringify(barra.otras)) { barra.otras = nuevas; barra.refrescar(true); }
};
void otras();
setInterval(() => void otras(), 30 * 1000);

/** Una ruta, relativa a la raíz del repositorio si está adentro (para el título). */
function relativa(ruta: string): string {
    const raiz = (modelo.raiz || '').replace(/\/$/, '');
    return raiz && ruta.startsWith(raiz + '/') ? ruta.slice(raiz.length + 1) : ruta;
}

/** La barra de acciones de un hilo, arriba: sus vistas (con su atajo) y su carpeta. Solo con un hilo a la vista. */
function pintarAcciones(que: string): void {
    const barraH = document.getElementById('acciones')!;
    const como = forma(que);
    barraH.hidden = !como;
    if (!como) return;
    const local = !que.startsWith('rem:');
    barraH.innerHTML = VISTAS.map(v => `<a data-vista="${v.clave}" class="${v.clave === como ? 'si' : ''}" title="${v.ayuda}">${v.nombre} <span class="tecla">${v.atajo}</span></a>`).join('')
        + '<span class="lleno"></span>'
        + (local ? `<a data-carpeta="1" title="la carpeta del hilo y su documento">carpeta</a>` : '');
}

/** Cambiar la vista del hilo que se ve (la barra de acciones, o ⌥ y su letra desde adentro de una vista). */
function cambiarVista(clave: string): void {
    if (!forma(actual) || !vista(clave) || forma(actual) === clave) return;
    modo[actual] = clave;
    mostrar(actual);
}

document.getElementById('acciones')!.addEventListener('click', e => {
    const a = (e.target as HTMLElement).closest('a');
    if (!a) return;
    if (a.dataset.vista) cambiarVista(a.dataset.vista);
    else if (a.dataset.carpeta) mostrar(`doc:${actual}`);
});
// el atajo (⌥ y la letra), antes que nadie: la terminal se lo comería
window.addEventListener('keydown', e => {
    if (!e.altKey || e.metaKey || e.ctrlKey) return;
    const v = VISTAS.find(x => x.tecla === e.code);
    if (v && forma(actual)) { e.preventDefault(); e.stopPropagation(); cambiarVista(v.clave); }
}, true);

declare global {
    interface Window {
        telar?: {
            mostrar?: (que: string) => void;
            donde?: (lo: { texto: string; otraMaquina: boolean } | null) => void;
        };
    }
}
window.telar = { ...(window.telar ?? {}), mostrar };
// abierta por «compartir» del teléfono (share_target del manifiesto): eso primero, también en el celular
const compartiendo = location.pathname === '/compartir';
mostrar(compartiendo ? 'compartir' : 'dashboard');
// en el celular se empieza por la lista
if (document.body.classList.contains('angosto') && !compartiendo) { document.body.classList.remove('en-detalle'); document.body.classList.add('en-lista'); }

setInterval(() => { if (hoy.panel && !document.hidden && actual === 'dashboard') void hoy.actualizar(); }, 60 * 1000);
// el modelo (los hilos, su atención) se sondea mientras la página se mira
const sondear = async () => {
    if (!document.hidden) await modelo.sondear().catch(() => undefined);
    setTimeout(sondear, modelo.error || !modelo.viva ? 5000 : 3000);
};
void modelo.sondear(true).catch(() => undefined).then(sondear);
