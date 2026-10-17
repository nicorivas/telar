// `telar panel`: la barra de hilos y el dashboard de VS Code, en un navegador.
//
//   node out/web/servidor.js [--puerto 8770] [--host 127.0.0.1]
//
// Son la misma barra (vistas/hilos.ts) y el mismo dashboard (vistas/hoy.ts), corriendo en Node
// fuera de VS Code, cada uno en su marco de una sola página (`/`): arman las mismas
// páginas con lo que da la CLI y responde a los mismos clics. Lo que en VS Code era su API pasa
// por el anfitrión web de abajo (avisos, campos, menús: mensajes a la página, que los dibuja
// con pagina.ts). La página habla con este servidor por un WebSocket en vez de postMessage.
//
// Se entra con una llave: la primera vez, con `?k=<llave>` (la imprime al arrancar); después
// queda en una cookie. La llave vive en ~/.config/telar/panel.llave. Solo escucha en la
// dirección que se le dé (por defecto, esta máquina): para el celular, la de Tailscale.
// Ver docs/propuestas/dashboard-fuera-de-vscode.md.

import { execFile, spawn } from 'child_process';
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as http from 'http';
import * as os from 'os';
import * as path from 'path';

import MarkdownIt = require('markdown-it');
import * as pty from 'node-pty';
import { WebSocket, WebSocketServer } from 'ws';

import { type Anfitrion, type Opcion, type OpcionesAviso, usar } from '../anfitrion';
import * as cli from '../cli';
import { modelo } from '../modelo';
import type { CrearSuperficie, Superficie } from '../superficie';
import { BarraHilos, type Guardado, type SuperficieBarra } from '../vistas/hilos';
import { PanelHoy } from '../vistas/hoy';
import { CSS_WEB, SCRIPT_WEB, paginaCasa, paginaTerminal } from './pagina';

function argumento(nombre: string, porDefecto: string): string {
    const i = process.argv.indexOf(`--${nombre}`);
    return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : porDefecto;
}
const PUERTO = Number(argumento('puerto', '8770'));
const HOST = argumento('host', '127.0.0.1');

// ── la llave ──────────────────────────────────────────────────────────────────

const RUTA_LLAVE = path.join(os.homedir(), '.config', 'telar', 'panel.llave');
function llave(): string {
    try { const k = fs.readFileSync(RUTA_LLAVE, 'utf8').trim(); if (k.length >= 32) return k; } catch { /* la primera vez */ }
    const k = crypto.randomBytes(24).toString('base64url');
    fs.mkdirSync(path.dirname(RUTA_LLAVE), { recursive: true });
    fs.writeFileSync(RUTA_LLAVE, k + '\n', { mode: 0o600 });
    return k;
}
const LLAVE = llave();
const COOKIE = 'telar_panel';

function conLlave(req: http.IncomingMessage): boolean {
    const galletas = Object.fromEntries((req.headers.cookie ?? '').split(';').map(c => c.trim().split('=')).filter(p => p.length === 2));
    const dada = galletas[COOKIE] ?? '';
    return dada.length === LLAVE.length && crypto.timingSafeEqual(Buffer.from(dada), Buffer.from(LLAVE));
}

// ── las dos páginas y los que las miran ───────────────────────────────────────

type Vista = 'dash' | 'barra';
const clientes: Record<Vista, Set<WebSocket>> = { dash: new Set(), barra: new Set() };
/** el último que hizo algo: a él se le preguntan los campos y los menús (si es la barra, que es
 *  angosta, al dashboard) */
let ultimo: WebSocket | undefined;
const paginas: Record<Vista, string> = { dash: '<!DOCTYPE html><p>leyendo…</p>', barra: '<!DOCTYPE html><p>leyendo…</p>' };

function a(vista: Vista, m: unknown): void {
    const s = JSON.stringify(m);
    for (const c of clientes[vista]) if (c.readyState === WebSocket.OPEN) c.send(s);
}
/** los avisos van al dashboard (es donde hay espacio); sin dashboard abierto, a la barra */
const aTodos = (m: unknown) => a(clientes.dash.size ? 'dash' : 'barra', m);
const a2 = a;

/** Una página con lo que necesita el navegador: el script del WebSocket y la interfaz (pagina.ts),
 *  con el mismo nonce del CSP que pone `estilo.marco`. */
function paginaWeb(vista: Vista): string {
    const pagina = paginas[vista];
    const nonce = /'nonce-([^']+)'/.exec(pagina)?.[1] ?? '';
    return pagina
        .replace('</style>', `${CSS_WEB}</style>`)
        .replace('<body', `<script nonce="${nonce}">${SCRIPT_WEB}</script><body`);
}

const superficieWeb: CrearSuperficie = avisos => {
    avisosPanel = avisos;
    const s: Superficie = {
        cspSource: "'self'",
        cspConectar: "'self'",
        get visible() { return clientes.dash.size > 0; },
        get activa() { return clientes.dash.size > 0; },
        html: p => { paginas.dash = p; a('dash', { __recargar: true }); },
        enviar: m => a('dash', m),
        revelar: () => { /* en la web, la pestaña la trae al frente quien la mira */ },
    };
    return s;
};
let avisosPanel: Parameters<CrearSuperficie>[0] | undefined;

const superficieBarra: SuperficieBarra = {
    cspSource: "'self'",
    cspConectar: "'self'",
    get visible() { return clientes.barra.size > 0; },
    html: p => { paginas.barra = p; a('barra', { __recargar: true }); },
    enviar: m => a('barra', m),
    cabecera: () => { /* el título y la cuenta: la lista ya los dice */ },
};

/** Lo que la barra recuerda (el orden de cada grupo): un archivo, en vez del globalState de VS Code. */
const RUTA_GUARDADO = path.join(os.homedir(), '.config', 'telar', 'panel-estado.json');
const guardado: Guardado = {
    get: <T>(clave: string) => {
        try { return (JSON.parse(fs.readFileSync(RUTA_GUARDADO, 'utf8')) as Record<string, T>)[clave]; } catch { return undefined; }
    },
    update: async (clave, valor) => {
        let todo: Record<string, unknown> = {};
        try { todo = JSON.parse(fs.readFileSync(RUTA_GUARDADO, 'utf8')); } catch { /* todavía no hay nada */ }
        todo[clave] = valor;
        fs.writeFileSync(RUTA_GUARDADO, JSON.stringify(todo, null, 1));
    },
};

// ── lo que el dashboard le pide a la interfaz ──────────────────────────────────

const pendientes = new Map<string, (valor: unknown) => void>();
/** Una pregunta a la página (un campo, un menú, un aviso con botones) y su respuesta. */
function preguntar(m: Record<string, unknown>): Promise<unknown> {
    const enDash = (c?: WebSocket) => !!c && clientes.dash.has(c) && c.readyState === WebSocket.OPEN;
    const destino = enDash(ultimo) ? ultimo : [...clientes.dash][0] ?? [...clientes.barra][0];
    if (!destino) return Promise.resolve(null);
    const id = crypto.randomUUID();
    return new Promise(resolve => {
        pendientes.set(id, resolve);
        destino.send(JSON.stringify({ ...m, __ui: id }));
        // nadie contesta en 10 minutos: como cancelar
        setTimeout(() => { if (pendientes.delete(id)) resolve(null); }, 10 * 60 * 1000);
    });
}

function avisoCon(nivel: string) {
    return async (texto: string, ...botones: (string | OpcionesAviso)[]): Promise<string | undefined> => {
        const nombres = botones.filter((b): b is string => typeof b === 'string');
        if (!nombres.length) { aTodos({ __aviso: texto, nivel }); return undefined; }
        const r = await preguntar({ tipo: 'aviso', texto, botones: nombres });
        return typeof r === 'string' ? r : undefined;
    };
}

const md = new MarkdownIt({ html: false, linkify: true });

function abrirEnEstaMaquina(cosa: string): void {
    const programa = process.platform === 'darwin' ? 'open' : 'xdg-open';
    spawn(programa, [cosa], { detached: true, stdio: 'ignore' }).unref();
}

const anfitrionWeb: Anfitrion = {
    aviso: avisoCon('aviso'),
    falla: avisoCon('falla'),
    info: avisoCon('info'),
    estado: (texto, ms) => aTodos({ __aviso: texto, nivel: 'info', ms: ms ?? 4000 }),
    progreso: async (o, trabajo) => {
        if (!o.ventana) aTodos({ __aviso: `${o.title}`, nivel: 'info', ms: 2500 });
        return trabajo();
    },
    campo: async o => {
        let problema = '';
        let valor = o.value ?? '';
        // la validación corre aquí: si lo escrito no sirve, se vuelve a preguntar con el porqué
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
    abrirExterno: async url => { aTodos({ __abrir: url }); },
    // un archivo o una carpeta: se abren en la máquina del servidor (el laptop), no en el navegador
    abrirArchivo: async (ruta, linea) => {
        execFile('code', ['-g', linea ? `${ruta}:${linea}` : ruta], error => { if (error) abrirEnEstaMaquina(ruta); });
    },
    mostrarCarpeta: async ruta => abrirEnEstaMaquina(ruta),
    copiar: async texto => { aTodos({ __copiar: texto }); },
    markdown: async texto => md.render(texto),
    irAHilo: async (hilo, crear, remoto) => {
        const r = await cli.ir(hilo, !!crear, remoto ?? '');
        if (!r.ok) aTodos({ __aviso: `telar: ${r.err.trim() || `no pude ir a «${hilo}»`}`, nivel: 'falla' });
        else aTodos({ __aviso: `→ ${hilo}, en la terminal`, nivel: 'info', ms: 2500 });
    },
    mostrarTerminal: async () => { /* la terminal es otra ventana */ },
    orden: async (id, ...args) => {
        const f = ordenes[id];
        if (f) return f(...args);
        aTodos({ __aviso: `«${id}» todavía es solo de VS Code`, nivel: 'aviso' });
        return undefined;
    },
};

// ── las órdenes: lo que en VS Code son comandos de la extensión ────────────────

/** A la derecha: el dashboard o la terminal de un hilo. La barra marca su fila. */
function mostrar(que: string): void {
    if (!que) return;
    a2('barra', { __mostrar: que });
    barra.dashboardActivo = que === 'dashboard';
    barra.mostrado = que === 'dashboard' ? '' : que;
    if (que !== 'dashboard') barra.appActiva = '';
    barra.refrescar(true);
}

let hoy: PanelHoy;
let barra: BarraHilos;
const hiloDe = (a: unknown): string => typeof a === 'string' ? a : (a as { hilo?: string } | undefined)?.hilo ?? '';

/** `telar hilo <verbo>` sobre un hilo, y la lista al día. */
async function sobreHilo(a: unknown, verbo: string, extra: string[] = []): Promise<boolean> {
    const hilo = hiloDe(a);
    if (!hilo) return false;
    const r = await cli.hilo(verbo, hilo, undefined, extra);
    if (!r.ok) { aTodos({ __aviso: `telar: ${r.err.trim().split('\n').pop() || `«telar hilo ${verbo}» falló`}`, nivel: 'falla' }); return false; }
    modelo.invalidar();
    await modelo.sondear();
    return true;
}

const ordenes: Record<string, (...args: any[]) => unknown> = {
    // en la web, ir a un hilo es mostrar su terminal a la derecha (no mover la ventana de tmux de nadie)
    'telar.ir': a => mostrar(hiloDe(a)),
    'telar.retomar': async a => { if (await sobreHilo(a, 'retomar')) mostrar(hiloDe(a)); },
    'telar.archivar': a => sobreHilo(a, 'archivar', ['--cerrar']),
    'telar.cerrar': a => sobreHilo(a, 'cerrar'),
    'telar.archivo': () => barra.alternarArchivo(),
    'telar.equipoVer': (id?: string) => id ? hoy.abrirEquipo(id) : undefined,
    'telar.seccion': (clave?: string) => { if (clave) { mostrar('dashboard'); return hoy.abrirSeccion(clave); } },
    'telar.app': (clave?: string) => { if (clave) { mostrar('dashboard'); return hoy.abrirApp(clave); } },
    'telar.tarea': (valor?: string) => valor ? hoy.abrirTarea(valor) : undefined,
    'telar.hoy': () => mostrar('dashboard'),
    'telar.actualizar': () => modelo.sondear(true),
    'telar.tejer': async () => { await cli.tejer(); await modelo.sondear(); },
    'telar.nuevo': async () => {
        const nombre = (await anfitrionWeb.campo({ prompt: 'Nombre del hilo nuevo', placeHolder: 'faro' }))?.trim();
        if (!nombre) return;
        const remotos = (await cli.config()).datos?.remotos ?? [];
        let remoto = '';
        if (remotos.length) {
            const e = await anfitrionWeb.elegir([{ label: 'Local', description: 'en esta máquina', remoto: '' },
                ...remotos.map(r => ({ label: `Remoto: ${r.nombre}`, description: r.destino, remoto: r.nombre }))],
                { placeHolder: `¿Dónde vive el agente de «${nombre}»?` });
            if (!e) return;
            remoto = e.remoto;
        }
        await anfitrionWeb.irAHilo(nombre, true, remoto);
    },
    // la lista de tareas de la barra lateral es de VS Code: aquí las tareas están en el dashboard
    'telar.tareas': () => undefined,
    'telar.tareasActualizar': () => undefined,
};

// ── las terminales ─────────────────────────────────────────────────────────────

/** xterm.js, servido desde su paquete: la página de la terminal lo carga de aquí (no hay red). */
const ESTATICOS: Record<string, string> = {
    '/xterm/xterm.js': require.resolve('@xterm/xterm/lib/xterm.js'),
    '/xterm/xterm.css': require.resolve('@xterm/xterm/css/xterm.css'),
    '/xterm/addon-fit.js': require.resolve('@xterm/addon-fit/lib/addon-fit.js'),
};

/** La terminal de un hilo: `telar mirar <hilo>` en un PTY de esta máquina, conectado a la página.
 *  Mirar arma una sesión agrupada fija en la ventana del hilo: escribir aquí es escribir en el hilo,
 *  pero no mueve lo que ven los demás. Al cerrarse la página, el PTY muere, tmux suelta la vista y
 *  la borra (destroy-unattached). */
function terminal(ws: WebSocket, params: URLSearchParams): void {
    const hilo = params.get('hilo') ?? '';
    const cols = Math.max(20, Math.min(400, Number(params.get('cols')) || 100));
    const rows = Math.max(5, Math.min(200, Number(params.get('rows')) || 30));
    if (!hilo) { ws.close(); return; }
    const vista = `ver-web-${crypto.randomBytes(3).toString('hex')}`;
    const p = pty.spawn(cli.programa(), ['mirar', hilo, '--vista', vista], {
        name: 'xterm-256color', cols, rows, cwd: os.homedir(),
        env: { ...process.env, PATH: cli.pathResuelto(), TERM: 'xterm-256color', LANG: process.env.LANG || 'es_CL.UTF-8' },
    });
    p.onData(d => { if (ws.readyState === WebSocket.OPEN) ws.send(d); });
    p.onExit(() => { if (ws.readyState === WebSocket.OPEN) ws.close(); });
    ws.on('message', datos => {
        let m: { d?: string; r?: [number, number] };
        try { m = JSON.parse(String(datos)); } catch { return; }
        if (typeof m.d === 'string') p.write(m.d);
        if (Array.isArray(m.r)) { try { p.resize(Math.max(20, m.r[0]), Math.max(5, m.r[1])); } catch { /* ya murió */ } }
    });
    ws.on('close', () => { try { p.kill(); } catch { /* ya murió */ } });
    latir(ws);
}

/** Un navegador que se cierra de golpe no avisa: el WebSocket queda abierto y la terminal viva. Cada
 *  15 s un ping; sin respuesta, se corta (y el cierre mata la terminal y tmux borra la vista). */
function latir(ws: WebSocket): void {
    let vivo = true;
    ws.on('pong', () => { vivo = true; });
    const latido = setInterval(() => {
        if (!vivo) { ws.terminate(); return; }
        vivo = false;
        try { ws.ping(); } catch { ws.terminate(); }
    }, 15 * 1000);
    ws.on('close', () => clearInterval(latido));
}

// ── arrancar ──────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
    usar(anfitrionWeb);
    await cli.resolverPath();

    hoy = new PanelHoy();
    hoy.crearSuperficie = superficieWeb;
    barra = new BarraHilos();
    barra.estado = guardado;
    barra.dashboardActivo = true;   // al abrir, a la derecha está el dashboard
    barra.mostrado = '';
    barra.conectar(superficieBarra);
    // la barra marca la app que muestra el dashboard, como en VS Code
    hoy.alCambiarFoco = () => {
        const app = hoy.appActual;
        if (barra.appActiva === app) return;
        barra.appActiva = app;
        barra.refrescar(true);
    };
    modelo.cambio.event(() => barra.refrescar());

    const servidor = http.createServer((req, res) => {
        const u = new URL(req.url ?? '/', 'http://x');
        if (u.searchParams.get('k') === LLAVE) {
            // la llave en la dirección se cambia por una cookie, y la dirección queda limpia
            res.writeHead(302, { 'Set-Cookie': `${COOKIE}=${LLAVE}; HttpOnly; SameSite=Strict; Path=/; Max-Age=31536000`, Location: '/' });
            res.end();
            return;
        }
        if (!conLlave(req)) { res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('telar panel: falta la llave (?k=…)'); return; }
        // xterm.js, tal como viene en su paquete
        const estatico = ESTATICOS[u.pathname];
        if (estatico) {
            res.writeHead(200, { 'Content-Type': estatico.endsWith('.css') ? 'text/css' : 'text/javascript', 'Cache-Control': 'max-age=86400' });
            fs.createReadStream(estatico).pipe(res);
            return;
        }
        // el dashboard se arma la primera vez que alguien lo pide
        if (u.pathname === '/dashboard' && !hoy.panel) hoy.abrir();
        const nonce = crypto.randomBytes(12).toString('base64url');
        const pagina = u.pathname === '/' ? paginaCasa(nonce)
            : u.pathname === '/dashboard' ? paginaWeb('dash')
            : u.pathname === '/barra' ? paginaWeb('barra')
            : u.pathname === '/terminal' ? paginaTerminal(nonce) : null;
        if (pagina === null) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
        res.end(pagina);
    });

    const wss = new WebSocketServer({ noServer: true });
    servidor.on('upgrade', (req, socket, cabeza) => {
        const u = new URL(req.url ?? '/', 'http://x');
        if (u.pathname === '/pty' && conLlave(req)) {
            wss.handleUpgrade(req, socket, cabeza, ws => terminal(ws, u.searchParams));
            return;
        }
        if (u.pathname !== '/ws' || !conLlave(req)) { socket.destroy(); return; }
        const vista: Vista = u.searchParams.get('v') === 'barra' ? 'barra' : 'dash';
        wss.handleUpgrade(req, socket, cabeza, ws => {
            clientes[vista].add(ws);
            if (vista === 'dash') { ultimo = ws; avisosPanel?.cambio(true, true); }
            ws.on('message', datos => {
                ultimo = ws;
                let m: { __ui_r?: string; valor?: unknown };
                try { m = JSON.parse(String(datos)); } catch { return; }
                if (m.__ui_r) { const r = pendientes.get(m.__ui_r); pendientes.delete(m.__ui_r); r?.(m.valor); return; }
                if (vista === 'barra') barra.mensaje(m as { tipo: string });
                else avisosPanel?.mensaje(m);
            });
            ws.on('close', () => { clientes[vista].delete(ws); if (ultimo === ws) ultimo = undefined; });
            latir(ws);
        });
    });

    // lo mismo que la extensión: el modelo se sondea, y el día se relee cada minuto mientras alguien mira
    const sondear = async () => {
        await modelo.sondear().catch(() => undefined);
        setTimeout(sondear, modelo.error || !modelo.viva ? 5000 : Math.max(Number(cli.ajuste('intervalo', 2000)), 1000));
    };
    void modelo.sondear(true).catch(() => undefined).then(sondear);
    setInterval(() => { if (clientes.dash.size) void hoy.actualizar(); }, 60 * 1000);
    // «las tareas cambiaron» (telar cambio tareas): se relee al tiro
    let marcaTareas = '', visto = 0;
    void cli.config().then(r => { if (r.datos?.estado) marcaTareas = path.join(r.datos.estado, 'cambios', 'tareas'); });
    setInterval(() => {
        if (!marcaTareas) return;
        let mtime = 0;
        try { mtime = fs.statSync(marcaTareas).mtimeMs; } catch { return; }
        if (!visto) { visto = mtime; return; }
        if (mtime > visto) { visto = mtime; if (clientes.dash.size) void hoy.actualizar(true); }
    }, 15 * 1000);

    servidor.listen(PUERTO, HOST, () => {
        console.log(`telar panel: http://${HOST === '0.0.0.0' ? os.hostname() : HOST}:${PUERTO}/?k=${LLAVE}`);
    });
}

void main();
