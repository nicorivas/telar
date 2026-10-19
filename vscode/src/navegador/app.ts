// El dashboard de telar, corriendo en el navegador: el mismo `PanelHoy` que en VS Code y en el panel en
// Node, sin Node. Lo que en el panel en Node hacía el servidor (hablar con la CLI, mandar la página por un
// WebSocket, preguntarle cosas a quien mira) aquí lo hace esta página:
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
import { modelo } from '../modelo';
import type { AvisosSuperficie, CrearSuperficie, Superficie } from '../superficie';
import { PanelHoy } from '../vistas/hoy';
import { SCRIPT_NAVEGADOR } from '../web/pagina';


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

// ── el iframe donde se dibuja el dashboard ────────────────────────────────────

let marco: HTMLIFrameElement | undefined;
let avisosPanel: AvisosSuperficie | undefined;
const pendientes = new Map<string, (valor: unknown) => void>();

function aLaPagina(m: unknown): void {
    marco?.contentWindow?.postMessage({ __telarPadre: m }, location.origin);
}

/** La página del dashboard con el guion de interfaz, con el mismo nonce del CSP que pone `estilo.marco`. */
function conInterfaz(pagina: string): string {
    const nonce = /'nonce-([^']+)'/.exec(pagina)?.[1] ?? '';
    return pagina
        .replace('</style>', `${web}</style>`)
        .replace('<body', `<script nonce="${nonce}">${SCRIPT_NAVEGADOR}</script><body`);
}

window.addEventListener('message', e => {
    if (e.source !== marco?.contentWindow || typeof e.data?.__telarHijo !== 'string') return;
    let m: Record<string, unknown>;
    try { m = JSON.parse(e.data.__telarHijo); } catch { return; }
    if (typeof m.__ui_r === 'string') {
        const listo = pendientes.get(m.__ui_r);
        if (listo) { pendientes.delete(m.__ui_r); listo(m.valor); }
        return;
    }
    if ('__ancho' in m) return;
    avisosPanel?.mensaje(m);
});

const superficie: CrearSuperficie = avisos => {
    avisosPanel = avisos;
    const s: Superficie = {
        cspSource: "'self'",
        get visible() { return !document.hidden; },
        get activa() { return document.hasFocus(); },
        html: p => {
            if (!marco) {
                marco = document.createElement('iframe');
                marco.id = 'dashboard';
                marco.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-forms allow-popups allow-modals');
                document.getElementById('vista')!.replaceChildren(marco);
            }
            marco.srcdoc = conInterfaz(p);
        },
        enviar: m => aLaPagina(m),
        revelar: () => { /* ya está al frente */ },
    };
    document.addEventListener('visibilitychange', () => avisos.cambio(!document.hidden, document.hasFocus()));
    return s;
};

// ── lo que el dashboard le pide a la interfaz (su anfitrión) ──────────────────

function preguntar(m: Record<string, unknown>): Promise<unknown> {
    const id = crypto.randomUUID();
    return new Promise(resolve => {
        pendientes.set(id, resolve);
        aLaPagina({ ...m, __ui: id });
        setTimeout(() => { if (pendientes.delete(id)) resolve(null); }, 10 * 60 * 1000);
    });
}

function avisoCon(nivel: string) {
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        if (!nombres.length) { aLaPagina({ __aviso: texto, nivel }); return undefined; }
        const r = await preguntar({ tipo: 'aviso', texto, botones: nombres });
        return typeof r === 'string' ? r : undefined;
    };
}

const md = new MarkdownIt({ html: false, linkify: true });

const anfitrion: Anfitrion = {
    aviso: avisoCon('aviso'),
    falla: avisoCon('falla'),
    info: avisoCon('info'),
    estado: (texto, ms) => aLaPagina({ __aviso: texto, nivel: 'info', ms: ms ?? 4000 }),
    progreso: async (o, trabajo) => {
        if (!o.ventana) aLaPagina({ __aviso: o.title, nivel: 'info', ms: 2500 });
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
    orden: async id => {
        aLaPagina({ __aviso: `«${id}» todavía no está en el navegador`, nivel: 'aviso' });
        return undefined;
    },
};

// ── arrancar: una pantalla más en el menú de la página ────────────────────────

usar(anfitrion);
const hoy = new PanelHoy();
hoy.crearSuperficie = superficie;

declare global { interface Window { telar?: { registrar(nombre: string, f: () => Promise<void>): void } } }
window.telar?.registrar('dashboard', async () => {
    if (!hoy.panel) hoy.abrir();
    else if (marco) document.getElementById('vista')!.replaceChildren(marco);
});
setInterval(() => { if (hoy.panel && !document.hidden) void hoy.actualizar(); }, 60 * 1000);
// lo mismo que el panel en Node: el modelo (los hilos, su atención) se sondea mientras la página se mira
const sondear = async () => {
    if (!document.hidden) await modelo.sondear().catch(() => undefined);
    setTimeout(sondear, modelo.error || !modelo.viva ? 5000 : 3000);
};
void modelo.sondear(true).catch(() => undefined).then(sondear);
