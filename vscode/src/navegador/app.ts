// El dashboard de telar, corriendo en el navegador: el mismo `PanelHoy` que en VS Code, sin Node. Lo que
// en el panel en Node (retirado el 19-oct-2026) hacía su servidor (hablar con la CLI, mandar la página por
// un WebSocket, preguntarle cosas a quien mira) aquí lo hace esta página:
//
//   - la API, por `fetch` a `/api` (la misma de `telar serve`, detrás de la llave de esta página);
//   - el dashboard se dibuja en un iframe, con el mismo guion de interfaz que en Node (web/pagina.ts) pero
//     hablándole a esta página por postMessage;
//   - los avisos, campos y menús que pide el dashboard (su anfitrión) los muestra ese iframe.
//
// Se empaqueta con esbuild (scripts/navegador.mjs) en src/telar/web/app.js, que sirve `telar serve --web`.

// primero: los estilos (las vistas arman su CSS al cargarse, y tienen que encontrarlos)
import { web } from './estilos';

import MarkdownIt from 'markdown-it';

import { type Anfitrion, type Opcion, type OpcionesAviso, usar } from '../anfitrion';
import * as cli from '../cli';
import { usarDisco } from '../disco';
import { modelo } from '../modelo';
import { BarraHilos, type Guardado, type SuperficieBarra } from '../vistas/hilos';
import { crearOrdenes } from '../web/ordenes';
import type { AvisosSuperficie, CrearSuperficie, Superficie } from '../superficie';
import { PanelHoy } from '../vistas/hoy';
import { type Documento, paginaCompartir, paginaConversacion, paginaDocumento, paginaTerminal, SCRIPT_NAVEGADOR } from '../web/pagina';


// ── la API: fetch a /api ───────────────────────────────────────────────────────

cli.usarTransporte(async (metodo, ruta, timeout, cuerpo) => {
    let r: Response;
    try {
        r = await fetch(`/api${ruta}`, {
            method: metodo, cache: 'no-store', signal: AbortSignal.timeout(timeout),
            headers: cuerpo === undefined ? {} : { 'Content-Type': 'application/json' },
            body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        });
    } catch (e) {
        return { error: `la API no respondió: ${(e as Error).message}` };
    }
    let json: unknown;
    try { json = await r.json(); } catch { json = undefined; }
    const detalle = (json as { detail?: unknown } | undefined)?.detail;
    if (r.ok && json !== undefined) return { datos: json };
    // la ruta no existe todavía: como sin API (y sin CLI, en el navegador eso es un error que se dice)
    if (r.status === 404 && detalle === 'Not Found') return undefined;
    return { error: typeof detalle === 'string' ? detalle : `la API respondió ${r.status}` };
});

// ── los ajustes: en VS Code son suyos; aquí salen del servidor (/config) ──

const ajustes: Record<string, unknown> = {};
cli.usarAjustes(<T>(clave: string, porDefecto: T): T => (clave in ajustes ? ajustes[clave] as T : porDefecto));
void cli.config().then(r => {
    // la bandeja del equipo: la del servidor que sirve la página («aqui») o la de la máquina que diga
    if (r.datos?.equipo) { ajustes.equipoRemoto = r.datos.equipo; void modelo.leerEquipo(); }
});

// ── el disco: los archivos de la máquina, por la API (que pone los límites: telar.servicios.archivos) ──

usarDisco({
    leer: async ruta => {
        try {
            const r = await fetch(`/api/archivos?ruta=${encodeURIComponent(ruta)}`, { cache: 'no-store' });
            return r.ok ? ((await r.json()) as { texto: string }).texto : undefined;
        } catch { return undefined; }
    },
    buscarMd: async (carpeta, hondo) => {
        try {
            const r = await fetch(`/api/archivos/md?carpeta=${encodeURIComponent(carpeta)}&hondo=${hondo}`, { cache: 'no-store' });
            return r.ok ? ((await r.json()) as { archivos: { ruta: string; mtime: number }[] }).archivos : [];
        } catch { return []; }
    },
    escribir: async (ruta, texto) => {
        try {
            const r = await fetch('/api/archivos', {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ruta, texto }),
            });
            return r.ok;
        } catch { return false; }
    },
});

// ── los marcos: la barra a la izquierda; a la derecha, el dashboard o la conversación de un hilo ──

const marcos = () => document.getElementById('marcos')!;
let marco: HTMLIFrameElement | undefined;       // el del dashboard
let marcoBarra: HTMLIFrameElement | undefined;
let avisosPanel: AvisosSuperficie | undefined;
const pendientes = new Map<string, (valor: unknown) => void>();
let actual = 'dashboard';

function nuevoMarco(clave: string, donde: HTMLElement): HTMLIFrameElement {
    const f = document.createElement('iframe');
    f.dataset.p = clave;
    f.title = clave;
    f.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
    donde.appendChild(f);
    return f;
}

function a(f: HTMLIFrameElement | undefined, m: unknown): void {
    f?.contentWindow?.postMessage({ __telarPadre: m }, location.origin);
}
const aLaPagina = (m: unknown) => a(marco, m);

/** A quién se le muestra un menú o un aviso: al dashboard si se ve; si no (una conversación, el celular
 *  con la lista), a la barra. */
function destino(): HTMLIFrameElement | undefined {
    const angosto = document.body.classList.contains('angosto');
    const enLista = document.body.classList.contains('en-lista');
    if (marco && !marco.hidden && !(angosto && enLista)) return marco;
    return marcoBarra ?? marco;
}
const aQuienMira = (m: unknown) => a(destino(), m);

/** Una página con el guion de interfaz, con el mismo nonce del CSP que pone `estilo.marco`. */
function conInterfaz(pagina: string): string {
    const nonce = /'nonce-([^']+)'/.exec(pagina)?.[1] ?? '';
    return pagina
        .replace('</style>', `${web}</style>`)
        .replace('<body', `<script nonce="${nonce}">${SCRIPT_NAVEGADOR}</script><body`);
}

window.addEventListener('message', e => {
    const desdeBarra = !!marcoBarra && e.source === marcoBarra.contentWindow;
    if (!desdeBarra && e.source !== marco?.contentWindow) return;
    if (typeof e.data?.__telarHijo !== 'string') return;
    let m: Record<string, unknown>;
    try { m = JSON.parse(e.data.__telarHijo); } catch { return; }
    if (typeof m.__ui_r === 'string') {
        const listo = pendientes.get(m.__ui_r);
        if (listo) { pendientes.delete(m.__ui_r); listo(m.valor); }
        return;
    }
    if ('__ancho' in m) return;
    if (desdeBarra) barra.mensaje(m as { tipo: string });
    else avisosPanel?.mensaje(m);
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
        enviar: m => aLaPagina(m),
        revelar: () => mostrar('dashboard'),
    };
    document.addEventListener('visibilitychange', () => avisos.cambio(!document.hidden, document.hasFocus()));
    return s;
};

const superficieBarra: SuperficieBarra = {
    cspSource: "'self'",
    get visible() { return !document.hidden; },
    html: p => {
        if (!marcoBarra) marcoBarra = nuevoMarco('barra', document.getElementById('barra')!);
        marcoBarra.srcdoc = conInterfaz(p);
    },
    enviar: m => a(marcoBarra, m),
    cabecera: () => { /* el título y la cuenta: la lista ya los dice */ },
};

/** Lo que la barra recuerda (el orden de cada grupo): en este navegador. */
const guardado: Guardado = {
    get: <T>(clave: string) => {
        try { return JSON.parse(localStorage.getItem(`telar.barra.${clave}`) ?? 'null') ?? undefined as T | undefined; } catch { return undefined; }
    },
    update: async (clave, valor) => { try { localStorage.setItem(`telar.barra.${clave}`, JSON.stringify(valor)); } catch { /* sin almacén */ } },
};

/** Cómo se ve un hilo: su terminal (xterm.js sobre `/pty`; la de uno de otra máquina, reenviada por la página
 *  de aquí a la de allá) o su conversación (la que se lee en el celular). En pantalla ancha, terminal; en
 *  angosta, conversación; el botón de arriba cambia. */
const modo: Record<string, 'term' | 'conv'> = {};
const angosto = () => document.body.classList.contains('angosto');
function forma(que: string): '' | 'term' | 'conv' {
    if (que === 'dashboard' || que === 'compartir' || que.startsWith('doc:')) return '';
    return modo[que] ?? (angosto() ? 'conv' : 'term');
}
/** las terminales que se miraron hace poco: cada una es una vista de tmux abierta, y se cierran las viejas */
const TOPE = 8;
const usadas: string[] = [];

/** A la derecha: «dashboard», un hilo de aquí (su terminal o su conversación), «rem:<máquina>:<hilo>» (uno de
 *  otra máquina: su terminal reenviada, o su conversación por el bus), «doc:<hilo>» (su carpeta y su documento) o «compartir» (lo
 *  que el teléfono le compartió a la app: la página se abrió en /compartir). */
function mostrar(que: string): void {
    if (!que) return;
    actual = que;
    let f: HTMLIFrameElement | undefined;
    if (que === 'dashboard') {
        if (!hoy.panel) hoy.abrir();
        f = marco;
    } else {
        const como = forma(que), llave = como ? `${como}:${que}` : que;
        f = [...marcos().querySelectorAll('iframe')].find(x => x.dataset.p === llave);
        if (que.startsWith('doc:') || que === 'compartir') {
            f ??= nuevoMarco(llave, marcos());
            if (que === 'compartir') f.srcdoc = paginaCompartir(Math.random().toString(36).slice(2), { consulta: location.search });
            else void verDocumento(f, que.slice(4), '');
        } else if (!f) {
            const remoto = que.startsWith('rem:') ? que.slice(4) : '';
            const i = remoto.indexOf(':');
            const hilo = remoto ? remoto.slice(i + 1) : que, maquina = remoto ? remoto.slice(0, i) : '';
            const nonce = Math.random().toString(36).slice(2);
            f = nuevoMarco(llave, marcos());
            f.srcdoc = como === 'term' ? paginaTerminal(nonce, { hilo, maquina })
                : paginaConversacion(nonce, { hilo, maquina });
        }
        if (como === 'term') {
            const j = usadas.indexOf(llave);
            if (j >= 0) usadas.splice(j, 1);
            usadas.push(llave);
            while (usadas.length > TOPE) [...marcos().querySelectorAll('iframe')].find(x => x.dataset.p === usadas[0])?.remove(), usadas.shift();
        }
    }
    for (const x of marcos().querySelectorAll('iframe')) x.hidden = x !== f;
    const botonModo = document.getElementById('modo');
    if (botonModo) {
        botonModo.hidden = !forma(que);
        botonModo.textContent = forma(que) === 'term' ? 'conversación' : 'terminal';
    }
    if (forma(que) === 'term' && !angosto()) f?.contentWindow?.focus();
    // lo que se ve, como se nombra un hilo: «hilo» si es de esta máquina, «máquina:hilo» si es de otra (como
    // `scp máquina:ruta`; con la persona sería «nico@laptop:Telar»). Lo muestra la cabecera (indice.html)
    const remoto = que.startsWith('rem:') ? que.slice(4) : '';
    const nombre = remoto ? remoto
        : que.startsWith('doc:') ? `${que.slice(4)} · carpeta` : que;
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

function preguntar(m: Record<string, unknown>): Promise<unknown> {
    // randomUUID solo existe en páginas seguras (https, localhost): un id que sirve en las dos
    const id = Math.random().toString(36).slice(2) + Date.now().toString(36);
    return new Promise(resolve => {
        pendientes.set(id, resolve);
        aQuienMira({ ...m, __ui: id });
        setTimeout(() => { if (pendientes.delete(id)) resolve(null); }, 10 * 60 * 1000);
    });
}

function avisoCon(nivel: string) {
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        if (!nombres.length) { aQuienMira({ __aviso: texto, nivel }); return undefined; }
        const r = await preguntar({ tipo: 'aviso', texto, botones: nombres });
        return typeof r === 'string' ? r : undefined;
    };
}

const md = new MarkdownIt({ html: false, linkify: true });

const anfitrion: Anfitrion = {
    aviso: avisoCon('aviso'),
    falla: avisoCon('falla'),
    info: avisoCon('info'),
    estado: (texto, ms) => aQuienMira({ __aviso: texto, nivel: 'info', ms: ms ?? 4000 }),
    progreso: async (o, trabajo) => {
        if (!o.ventana) aQuienMira({ __aviso: o.title, nivel: 'info', ms: 2500 });
        return trabajo();
    },
    campo: async o => {
        let problema = '';
        let valor = o.value ?? '';
        for (;;) {
            const r = await preguntar({ tipo: 'campo', titulo: o.title ?? '', ayuda: o.prompt ?? '', placeholder: o.placeHolder ?? '',
                valor, password: !!o.password, problema });
            if (typeof r !== 'string') return undefined;
            problema = o.validateInput?.(r) ?? '';
            if (!problema) return r;
            valor = r;
        }
    },
    elegir: async <T extends Opcion>(opciones: T[], menu?: { title?: string; placeHolder?: string }) => {
        const r = await preguntar({ tipo: 'elegir', titulo: menu?.title ?? '', placeholder: menu?.placeHolder ?? '',
            opciones: opciones.map(o => ({ label: o.label, description: o.description, detail: o.detail, separador: !!o.separador })) });
        return typeof r === 'number' ? opciones[r] : undefined;
    },
    abrirExterno: async url => { window.open(url, '_blank', 'noopener'); },
    // un archivo o una carpeta viven en la máquina, no en el navegador: por ahora se dice
    abrirArchivo: async ruta => { aLaPagina({ __aviso: `${ruta}: abrir archivos desde el navegador viene después`, nivel: 'aviso' }); },
    mostrarCarpeta: async ruta => { aLaPagina({ __aviso: `${ruta}: abrir carpetas desde el navegador viene después`, nivel: 'aviso' }); },
    copiar: async texto => { try { await navigator.clipboard.writeText(texto); } catch { /* sin permiso */ } },
    markdown: async texto => md.render(texto),
    irAHilo: async (hilo, crear, remoto) => {
        const r = await cli.ir(hilo, !!crear, remoto ?? '');
        if (!r.ok) aLaPagina({ __aviso: `telar: ${r.err.trim() || `no pude ir a «${hilo}»`}`, nivel: 'falla' });
        else aLaPagina({ __aviso: `→ ${hilo}, en la terminal`, nivel: 'info', ms: 2500 });
    },
    mostrarTerminal: async () => { /* la terminal es otra ventana */ },
    orden: async (id, ...args) => {
        const f = ordenes[id];
        if (f) return f(...args);
        aQuienMira({ __aviso: `«${id}» todavía no está en el navegador`, nivel: 'aviso' });
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
const ordenes = crearOrdenes({ hoy, barra, anfitrion, avisar: aQuienMira, mostrar });
barra.conectar(superficieBarra);
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

/** La carpeta de un hilo y uno de sus archivos (`/api/hilos/documento`), en su marco. Los enlaces de la
 *  página (a otro archivo, a la carpeta de arriba) no navegan: se leen aquí y se vuelve a dibujar. */
async function verDocumento(f: HTMLIFrameElement, hilo: string, archivo: string): Promise<void> {
    let d: Documento;
    try {
        const r = await fetch(`/api/hilos/documento?hilo=${encodeURIComponent(hilo)}&archivo=${encodeURIComponent(archivo)}`, { cache: 'no-store' });
        const j = await r.json() as Documento & { markdown?: string; detail?: string };
        d = r.ok ? { ...j, html: j.markdown ? md.render(j.markdown) : undefined, subir: j.subir ?? undefined }
            : { hilo, titulo: hilo, error: typeof j.detail === 'string' ? j.detail : `la API respondió ${r.status}` };
    } catch (e) {
        d = { hilo, titulo: hilo, error: `la API no respondió: ${(e as Error).message}` };
    }
    f.onload = () => {
        f.contentDocument?.addEventListener('click', e => {
            const a = (e.target as HTMLElement).closest?.('a');
            const href = a?.getAttribute('href') ?? '';
            if (!href.startsWith('/documento')) return;
            e.preventDefault();
            const q = new URLSearchParams(href.slice(href.indexOf('?') + 1));
            void verDocumento(f, q.get('hilo') ?? hilo, q.get('archivo') ?? '');
        });
    };
    f.srcdoc = paginaDocumento(Math.random().toString(36).slice(2), d);
}

/** El botón de arriba: el hilo que se ve, de terminal a conversación o al revés. */
function cambiarModo(): void {
    const como = forma(actual);
    if (!como) return;
    modo[actual] = como === 'term' ? 'conv' : 'term';
    mostrar(actual);
}

declare global {
    interface Window {
        telar?: {
            mostrar?: (que: string) => void; cambiarModo?: () => void;
            donde?: (lo: { texto: string; otraMaquina: boolean } | null) => void;
        };
    }
}
window.telar = { ...(window.telar ?? {}), mostrar, cambiarModo };
// abierta por «compartir» del teléfono (share_target del manifiesto): eso primero
mostrar(location.pathname === '/compartir' ? 'compartir' : 'dashboard');
// en el celular se empieza por la lista
if (document.body.classList.contains('angosto')) { document.body.classList.remove('en-detalle'); document.body.classList.add('en-lista'); }

setInterval(() => { if (hoy.panel && !document.hidden && actual === 'dashboard') void hoy.actualizar(); }, 60 * 1000);
// como en VS Code: el modelo (los hilos, su atención) se sondea mientras la página se mira
const sondear = async () => {
    if (!document.hidden) await modelo.sondear().catch(() => undefined);
    setTimeout(sondear, modelo.error || !modelo.viva ? 5000 : 3000);
};
void modelo.sondear(true).catch(() => undefined).then(sondear);
