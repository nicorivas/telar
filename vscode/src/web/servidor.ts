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
import { CSS_WEB, SCRIPT_WEB, paginaCasa, paginaCompartir, paginaConversacion, paginaDocumento, paginaTerminal } from './pagina';

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
/** los avisos van a la página que se está mirando (ver `destinatario`) */
const aTodos = (m: unknown) => { const c = destinatario(); if (c) c.send(JSON.stringify(m)); };
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
/** Cuánto se ve cada página (lo dice ella al abrir y al cambiar de tamaño): 0 si está oculta, y si
 *  ocupa toda la pantalla (la barra en un celular). */
const medidas = new WeakMap<WebSocket, { ancho: number; llena: boolean }>();
/** A quién se le muestra algo (un menú, un aviso): a la página que hizo algo, si se ve y tiene espacio
 *  (el dashboard, o la barra cuando ocupa la pantalla); si no, al dashboard que se vea, a la barra que se
 *  vea, y al final a cualquiera. La barra al lado del dashboard es angosta: ahí, al dashboard. */
function destinatario(): WebSocket | undefined {
    const abierta = (c: WebSocket) => c.readyState === WebSocket.OPEN;
    const visible = (c: WebSocket) => abierta(c) && (medidas.get(c)?.ancho ?? 1) > 0;
    const conEspacio = (c: WebSocket) => visible(c) && (clientes.dash.has(c) || !!medidas.get(c)?.llena);
    if (ultimo && conEspacio(ultimo)) return ultimo;
    const todas = [...clientes.dash, ...clientes.barra];
    return todas.find(conEspacio) ?? todas.find(visible) ?? todas.find(abierta);
}
/** Una pregunta a la página (un campo, un menú, un aviso con botones) y su respuesta. */
function preguntar(m: Record<string, unknown>): Promise<unknown> {
    const destino = destinatario();
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
async function sobreHilo(a: unknown, verbo: string, extra: string[] = [], valor?: string): Promise<boolean> {
    const hilo = hiloDe(a);
    if (!hilo) return false;
    const r = await cli.hilo(verbo, hilo, valor, extra);
    if (!r.ok) { aTodos({ __aviso: `telar: ${r.err.trim().split('\n').pop() || `«telar hilo ${verbo}» falló`}`, nivel: 'falla' }); return false; }
    modelo.invalidar();
    await modelo.sondear();
    return true;
}

/** El menú de un hilo, que en VS Code es su menú contextual: lo que se puede hacer con él, según esté
 *  vivo, archivado o vinculado. Cada acción es una orden `telar hilo …`. */
async function menuHilo(a: unknown): Promise<void> {
    const hilo = hiloDe(a);
    const h = modelo.porNombre(hilo);
    if (!hilo || !h) return;
    type Fila = Opcion & { hacer?: () => Promise<unknown> };
    const prioridad = (n: string, nombre: string): Fila => ({ label: `prioridad ${nombre}`, description: String(h.prioridad ?? '') === n ? 'la que tiene' : '',
        hacer: () => sobreHilo(hilo, 'prioridad', [], n) });
    const filas: Fila[] = [
        { label: h.archivado || !h.vivo ? 'retomar' : 'ver', description: h.archivado || !h.vivo ? 'reabre su tab con su conversación' : '',
            hacer: async () => { if (h.archivado || !h.vivo) { if (await sobreHilo(hilo, 'retomar')) mostrar(hilo); } else mostrar(hilo); } },
        { label: 'renombrar', description: 'se mueve con él lo que telar sabía', hacer: async () => {
            const nombre = await anfitrionWeb.campo({ title: `Nombre nuevo para «${hilo}»`, value: hilo });
            if (nombre && nombre !== hilo) await sobreHilo(hilo, 'renombrar', [], nombre);
        } },
        ...(h.vinculado ? [{ label: 'ver su carpeta y documento', description: h.relativa || h.ruta, hacer: async () => mostrar(`doc:${hilo}`) }] : []),
        { label: 'vincular a un proyecto', description: h.relativa ? `hoy: ${h.relativa}` : 'sin carpeta', hacer: () => vincularWeb(hilo) },
        ...(h.vinculado ? [{ label: 'desvincular', description: 'soltar su carpeta', hacer: () => sobreHilo(hilo, 'desvincular') }] : []),
        { label: 'prioridad', separador: true },
        prioridad('1', 'alta'), prioridad('2', 'media'), prioridad('3', 'baja'), prioridad('ninguna', 'ninguna'),
        { label: 'guardar o cerrar', separador: true },
        ...(h.archivado ? [{ label: 'desarchivar', description: 'volver a la lista sin abrirlo', hacer: () => sobreHilo(hilo, 'desarchivar') }]
            : [{ label: 'archivar', description: 'cierra el tab y guarda su conversación', hacer: () => sobreHilo(hilo, 'archivar', ['--cerrar']) }]),
        ...(h.vivo ? [{ label: 'cerrar', description: 'cierra el tab y lo saca de la lista', hacer: () => sobreHilo(hilo, 'cerrar') }] : []),
        ...(!h.remoto ? [{ label: 'llevar a otra máquina', description: 'su conversación viaja; los archivos no', hacer: () => llevarWeb(hilo) }] : []),
        { label: 'olvidar', description: 'telar pierde su carpeta, su prioridad y su atención', hacer: async () => {
            const si = await anfitrionWeb.aviso(`¿Que telar olvide «${hilo}»? Pierde su carpeta, su prioridad y su atención.`, { modal: true }, 'Olvidar');
            if (si === 'Olvidar') await sobreHilo(hilo, 'olvidar');
        } },
    ];
    const elegida = await anfitrionWeb.elegir(filas, { title: hilo });
    await elegida?.hacer?.();
}

/** Vincular desde la web: se elige entre los proyectos del perfil, o se escribe una ruta. */
async function vincularWeb(hilo: string): Promise<void> {
    const r = await cli.proyectos();
    const otra = { label: 'otra carpeta…', description: 'escribir su ruta', ruta: '' };
    const filas = [...(r.datos?.proyectos ?? []).map(p => ({ label: p.nombre, description: p.ruta, ruta: String(p.ruta) })), otra];
    const elegida = await anfitrionWeb.elegir(filas, { title: `Vincular «${hilo}» a…`, placeHolder: 'filtrar' });
    if (!elegida) return;
    const ruta = elegida.ruta || await anfitrionWeb.campo({ title: `La carpeta de «${hilo}»`, prompt: 'relativa a la raíz del repositorio, o absoluta' });
    if (ruta) await sobreHilo(hilo, 'vincular', [], ruta);
}

/** Llevar un hilo a otra máquina de [remotos]: si aquí hay trabajo sin subir, se pregunta antes. */
async function llevarWeb(hilo: string): Promise<void> {
    const remotos = (await cli.config()).datos?.remotos ?? [];
    if (!remotos.length) { aTodos({ __aviso: 'telar: no hay máquinas en [remotos]', nivel: 'aviso' }); return; }
    const elegida = remotos.length === 1 ? remotos[0]
        : (await anfitrionWeb.elegir(remotos.map(x => ({ label: x.nombre, description: x.destino, x })), { title: `¿A qué máquina llevo «${hilo}»?` }))?.x;
    if (!elegida) return;
    aTodos({ __aviso: `llevando «${hilo}» a ${elegida.nombre}…`, nivel: 'info', ms: 4000 });
    let r = await cli.hilo('llevar', hilo, elegida.nombre);
    if (!r.ok && /sin subir/.test(r.err)) {
        const lista = r.out.split('\n').filter(l => l.trim().startsWith('·')).map(l => l.trim()).join('\n');
        const si = await anfitrionWeb.aviso(`La conversación de «${hilo}» viaja, los archivos no. Aquí hay trabajo que allá no va a estar:\n${lista}`, { modal: true }, 'Llevar igual');
        if (si !== 'Llevar igual') return;
        r = await cli.hilo('llevar', hilo, elegida.nombre, ['--si']);
    }
    if (!r.ok) { aTodos({ __aviso: `telar: ${r.err.trim().split('\n').pop() || 'no se llevó'}`, nivel: 'falla' }); return; }
    modelo.invalidar();
    await modelo.sondear();
}

const ordenes: Record<string, (...args: any[]) => unknown> = {
    'telar.menuHilo': a => menuHilo(a),
    // un hilo de otra máquina: se lee como conversación y se le escribe por el bus (aquí no hay su terminal)
    'telar.irRemoto': (id?: string) => { const [maq, ...resto] = String(id ?? '').split('|'); if (maq && resto.length) mostrar(`rem:${maq}:${resto.join('|')}`); },
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
/** Lo que deja instalar el panel como app (y recibir lo que comparte el teléfono): el manifiesto, los
 *  íconos y un service worker. Se sirven sin llave: no dicen nada de nadie, y el navegador los pide sin
 *  la cookie. */
const CARPETA_APP = path.join(__dirname, '..', '..', 'media', 'app');
const APP: Record<string, string> = {
    '/manifest.webmanifest': 'application/manifest+json', '/sw.js': 'text/javascript', '/apple-touch-icon.png': 'image/png',
    '/icono-192.png': 'image/png', '/icono-512.png': 'image/png', '/icono-maskable-192.png': 'image/png', '/icono-maskable-512.png': 'image/png',
};

/** La carpeta de un hilo y uno de sus archivos (su documento, si no se pide otro), ya listos para la
 *  página: nada fuera de la carpeta del hilo, nada oculto, y un tope de tamaño. */
async function documento(hilo: string, archivo: string): Promise<import('./pagina').Documento> {
    const r = await cli.telar(['ficha', hilo, '--json'], 20000);
    let h: { ruta?: string; vinculado?: boolean; ficha?: { documento?: string; titulo?: string } } = {};
    try { h = JSON.parse(r.out).hilo ?? {}; } catch { /* sin ficha */ }
    const base = h.vinculado && h.ruta ? path.resolve(h.ruta) : '';
    if (!base || !fs.existsSync(base)) return { hilo, titulo: hilo, error: `«${hilo}» no tiene una carpeta en esta máquina` };
    const elegido = archivo ? path.resolve(base, archivo) : (h.ficha?.documento ? path.resolve(h.ficha.documento) : '');
    if (elegido && elegido !== base && !elegido.startsWith(base + path.sep)) return { hilo, titulo: hilo, error: 'ese archivo no es de la carpeta del hilo' };
    // y de verdad: un enlace simbólico de adentro puede apuntar afuera
    const real = (x: string) => { try { return fs.realpathSync(x); } catch { return x; } };
    const baseReal = real(base);
    if (elegido && real(elegido) !== baseReal && !real(elegido).startsWith(baseReal + path.sep)) return { hilo, titulo: hilo, error: 'ese archivo apunta fuera de la carpeta del hilo' };
    // la carpeta que se lista: la del archivo elegido (si es una carpeta, ella misma)
    const esCarpeta = !!elegido && fs.statSync(elegido, { throwIfNoEntry: false })?.isDirectory();
    const dir = esCarpeta ? elegido : elegido ? path.dirname(elegido) : base;
    const archivos = (fs.readdirSync(dir, { withFileTypes: true }) as fs.Dirent[])
        .filter(e => !e.name.startsWith('.') && e.name !== 'node_modules')
        .map(e => ({ nombre: e.name + (e.isDirectory() ? '/' : ''), ruta: path.relative(base, path.join(dir, e.name)) }))
        .sort((a, b) => Number(b.nombre.endsWith('/')) - Number(a.nombre.endsWith('/')) || a.nombre.localeCompare(b.nombre));
    const subir = dir !== base ? path.relative(base, path.dirname(dir)) || '.' : undefined;
    let html = '', texto = '';
    if (elegido && !esCarpeta) {
        const st = fs.statSync(elegido, { throwIfNoEntry: false });
        if (!st) texto = 'no existe';
        else if (st.size > 1 << 20) texto = `pesa ${Math.round(st.size / 1024)} KB: no se muestra aquí`;
        else {
            const crudo = fs.readFileSync(elegido);
            if (crudo.includes(0)) texto = 'es un archivo binario: no se muestra aquí';
            else if (/\.md$/i.test(elegido)) html = md.render(crudo.toString('utf8'));
            else texto = crudo.toString('utf8');
        }
    }
    return { hilo, titulo: h.ficha?.titulo || hilo, carpeta: path.relative(base, dir) || '.', archivo: elegido && !esCarpeta ? path.relative(base, elegido) : '',
        archivos, subir, html, texto };
}

/** Que un pedido que escribe (un POST, un WebSocket) venga de una página de este mismo servidor: una
 *  página ajena no puede fingir el `Origin`. Sin `Origin` (curl, la CLI), se acepta: la llave sigue mandando. */
function mismoOrigen(req: http.IncomingMessage): boolean {
    const origen = req.headers.origin;
    if (!origen) return true;
    try { return new URL(origen).host === req.headers.host; } catch { return false; }
}

/** El cuerpo JSON de un POST, con tope. */
function leerCuerpo(req: http.IncomingMessage, tope = 32 * 1024): Promise<Record<string, unknown> | null> {
    return new Promise(listo => {
        let datos = '';
        req.on('data', (c: Buffer) => { datos += c; if (datos.length > tope) { listo(null); req.destroy(); } });
        req.on('end', () => { try { const d = JSON.parse(datos); listo(d && typeof d === 'object' ? d : null); } catch { listo(null); } });
        req.on('error', () => listo(null));
    });
}

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
    // los hilos de otras máquinas que aquí no se ven (en el servidor, los del laptop): de sus fotos, cada
    // 30 s. Una máquina cuyos hilos ya trae la lista (los remotos de [remotos]) no se repite
    const otras = async () => {
        const r = await cli.espejos().catch(() => undefined);
        const yaEstan = new Set(modelo.hilos.map(h => h.remoto).filter(Boolean));
        const nuevas = (r?.datos?.espejos ?? []).filter(e => !e.error && !yaEstan.has(e.nombre))
            .map(e => ({ nombre: e.nombre, en_linea: e.en_linea, edad: e.edad, hilos: e.hilos }));
        if (JSON.stringify(nuevas) !== JSON.stringify(barra.otras)) { barra.otras = nuevas; barra.refrescar(true); }
    };
    void otras();
    setInterval(() => void otras(), 30 * 1000);

    const servidor = http.createServer((req, res) => {
        const u = new URL(req.url ?? '/', 'http://x');
        if (APP[u.pathname]) {
            res.writeHead(200, { 'Content-Type': APP[u.pathname], 'Cache-Control': 'max-age=3600' });
            fs.createReadStream(path.join(CARPETA_APP, u.pathname.slice(1))).on('error', () => res.end()).pipe(res);
            return;
        }
        if (u.searchParams.get('k') === LLAVE) {
            // la llave en la dirección se cambia por una cookie, y la dirección queda limpia. Lax (no Strict): el
            // teléfono abre la app al compartirle algo, y esa navegación tiene que llevar la cookie; lo que escribe
            // (POST, WebSocket) además exige que venga de una página de aquí (`mismoOrigen`)
            res.writeHead(302, { 'Set-Cookie': `${COOKIE}=${LLAVE}; HttpOnly; SameSite=Lax; Path=/; Max-Age=31536000`, Location: '/' });
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
        // compartir desde el teléfono: a dónde se puede llevar, y llevarlo (`telar compartir`)
        if (u.pathname === '/api/compartir/destinos') {
            void cli.telar(['compartir', '--destinos', '--json'], 15000).then(r => {
                let proveedores: unknown[] = [];
                try { proveedores = JSON.parse(r.out).destinos ?? []; } catch { /* sin destinos propios */ }
                const hilos = modelo.hilos.filter(h => !h.archivado).map(h => ({ destino: `hilo:${h.nombre}`, nombre: cli.nombreVisible(h), tipo: 'hilo' }));
                res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
                res.end(JSON.stringify({ destinos: [...proveedores, ...hilos] }));
            });
            return;
        }
        if (u.pathname === '/api/compartir') {
            if (req.method !== 'POST' || !mismoOrigen(req)) { res.writeHead(403); res.end(); return; }
            void leerCuerpo(req).then(async d => {
                const texto = (k: string) => (typeof d?.[k] === 'string' ? String(d[k]) : '');
                const r = !d ? { ok: false, error: 'el pedido no se entiende' }
                    : await cli.telar(['compartir', '--a', texto('a'), '--url', texto('url'), '--texto', texto('texto'), '--titulo', texto('titulo'), '--json'], 40000)
                        .then(x => { try { return JSON.parse(x.out); } catch { return { ok: false, error: x.err.trim().split('\n').pop() || 'no respondió' }; } });
                res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
                res.end(JSON.stringify(r));
            });
            return;
        }
        // la carpeta de un hilo y su documento (o un archivo de ella), para leerlos en la web
        if (u.pathname === '/documento') {
            const nonce = crypto.randomBytes(12).toString('base64url');
            void documento(u.searchParams.get('hilo') ?? '', u.searchParams.get('archivo') ?? '').then(d => {
                res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
                res.end(paginaDocumento(nonce, d));
            });
            return;
        }
        // escribirle a un hilo de otra máquina, por el bus, como la persona (`telar mensaje --tipo persona`)
        if (u.pathname === '/api/remoto/enviar') {
            if (req.method !== 'POST' || !mismoOrigen(req)) { res.writeHead(403); res.end(); return; }
            void leerCuerpo(req).then(async d => {
                const hilo = typeof d?.hilo === 'string' ? d.hilo : '', texto = typeof d?.texto === 'string' ? d.texto.trim() : '';
                const r = !hilo || !texto ? { ok: false, error: 'faltan el hilo o el texto' }
                    : texto.length > 8000 ? { ok: false, error: 'pasa de 8000 caracteres' }
                    : await cli.escribirComoPersona(hilo, texto, 'el panel');
                res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
                res.end(JSON.stringify({ ok: r.ok !== false && !r.error, error: r.error }));
            });
            return;
        }
        // lo último de un hilo, para leerlo como conversación (el celular): `telar hilo leer`; de otra
        // máquina (`maquina`), por el bus
        if (u.pathname === '/api/leer') {
            const hilo = u.searchParams.get('hilo') ?? '';
            const maquina = u.searchParams.get('maquina') ?? '';
            const n = String(Math.max(1, Math.min(30, Number(u.searchParams.get('n')) || 8)));
            void cli.telar(['hilo', 'leer', hilo, '--ultimos', n, ...(maquina ? ['--maquina', maquina] : []), '--json'], 35000).then(r => {
                let cuerpo: string;
                try {
                    // lo que dicen la persona y el agente va en markdown: se manda también convertido (sin HTML
                    // crudo: markdown-it con html:false lo escapa), y la página lo pinta así
                    const d = JSON.parse(r.out) as { turnos?: { quien: string; texto?: string; html?: string }[][] };
                    for (const turno of d.turnos ?? []) for (const m of turno) if (m.quien !== 'herramienta' && m.texto) m.html = md.render(m.texto);
                    cuerpo = JSON.stringify(d);
                } catch { cuerpo = JSON.stringify({ error: (r.err || 'no pude leer el hilo').trim().split('\n').pop() }); }
                res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
                res.end(cuerpo);
            });
            return;
        }
        // el dashboard se arma la primera vez que alguien lo pide
        if (u.pathname === '/dashboard' && !hoy.panel) hoy.abrir();
        const nonce = crypto.randomBytes(12).toString('base64url');
        const pagina = u.pathname === '/' ? paginaCasa(nonce)
            : u.pathname === '/dashboard' ? paginaWeb('dash')
            : u.pathname === '/barra' ? paginaWeb('barra')
            : u.pathname === '/terminal' ? paginaTerminal(nonce)
            : u.pathname === '/conversacion' ? paginaConversacion(nonce)
            : u.pathname === '/compartir' ? paginaCompartir(nonce) : null;
        if (pagina === null) { res.writeHead(404); res.end(); return; }
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
        res.end(pagina);
    });

    const wss = new WebSocketServer({ noServer: true });
    servidor.on('upgrade', (req, socket, cabeza) => {
        const u = new URL(req.url ?? '/', 'http://x');
        // un WebSocket escribe (en la terminal de un hilo, en el dashboard): solo desde una página de aquí
        if (!mismoOrigen(req)) { socket.destroy(); return; }
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
                let m: { __ui_r?: string; valor?: unknown; __ancho?: number; __llena?: boolean };
                try { m = JSON.parse(String(datos)); } catch { return; }
                if (typeof m.__ancho === 'number') { medidas.set(ws, { ancho: m.__ancho, llena: !!m.__llena }); return; }
                ultimo = ws;
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
